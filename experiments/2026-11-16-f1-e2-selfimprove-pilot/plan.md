---
title: P15-01 (F1 / E2) CPU pilot - a decoder that learns from user feedback while the commit guarantee stays valid - plan
type: experiment
task: P15-01
updated: 2026-11-15
---

# P15-01: E2 CPU pilot, self-improving T12 replay with a guarded update loop (plan)

Written **before** the base decoder is trained and before any replay run. Frontier F1 ([north star](../../wiki/questions/north-star.md)): "a BCI that teaches itself from daily use while a stated error guarantee stays valid through every update". Roadmap item [P15-01](../../wiki/questions/roadmap-standard.md#p15-01-e2-cpu-pilot-self-improving-replay-on-t12). The pilot also gives a first version of the P15-02 hook (re-calibrate after each decoder update).

## Questions
1. **Q-learn:** does a small per-day input layer, updated only from simulated user feedback, lower the error of a frozen decoder over 16 later days?
2. **Q-guarantee:** does the realised wrong-commit rate (silent errors included) stay at or below alpha **while** the decoder changes every day?
3. **Q-compound:** does naive self-training on the decoder's own outputs (no user labels) compound errors (ALIGN 2026 warning)?
4. **Q-cost:** what does the guarantee cost (offer-only phases, fewer commits)?

## Why not the T12 v2 decoder or its logits
- The v2 decoder (M3-28) was trained on the train blocks of **all 24** sessions, with a per-session input layer for each. So its stored logits already contain the day adaptation. They cannot show learning on a new day.
- Its checkpoint lies under `C:\Users\zhang\bci-data\runs\`, which this task must not touch.
- So the pilot trains **its own small CPU decoder** on the first 7 sessions only, from the v2 per-session feature files (`derived/2026-11-13-confirmatory-t12-v2/t12.*.npz`, read only: causal rolling z-scored features, 512 channels, 20 ms bins, CMUdict phonemes). CPU torch (`C:\venvs\fidetype-rocm`, with `HIP_VISIBLE_DEVICES=-1`; no tensor goes to the GPU).
- The word route (n-best sentences) is the M3-28 v2 route unchanged (B2T '25 phoneme beam + word decoder, tuned `lm_weight 1.0, edit_penalty 12, word_bonus 3`, Tatoeba word trigram beta 2.0), as in P14-03.

## Data and time order (fixed now)
| part | sessions | use |
|---|---|---|
| base | S0-S6 (2022-04-28 .. 2022-06-02) | train the trunk + one day layer per session (train part); early stopping on their `val` part |
| tuning day | S7 (2022-06-07) | choose the adaptation settings, the sentence temperature and the ACI start threshold (grid below). Not used again |
| replay | S8-S23 (2022-06-14 .. 2022-08-25), 16 days, about 6,700 trials | the experiment. Inside a day: train part (file order) -> `val` (last train block) -> `pool` (test block). This is the recording order (prep.py asserts it) |

Items whose truth has an out-of-CMUdict word stay in the replay (the word truth is known); they give no phoneme label for adaptation and no PER. Licence: B2T '24 is CC0.

## Base decoder (fixed now; own code)
- Per-day input layer: 512 x 512 affine (identity init) + softsign, after a causal half-Gaussian smoother (SD 2 bins).
- Trunk: patch conv (kernel 32 bins, stride 4 -> 80 ms frames, 512 -> 384), 5 causal dilated conv blocks (kernel 3, dilation 1, 2, 4, 8, 16, 384 channels, GELU, residual, dropout 0.3), 1x1 conv to 41 CTC outputs (blank 0, SIL, 39 phonemes; the v2 order). Conv layers, not a GRU: the CPU GRU of this torch build is about 50 times slower than its oneDNN conv.
- Training: CTC, AdamW lr 1e-3 (cosine, warm-up 300 steps), batch 32, white noise SD 0.8 and offset SD 0.2 (v2 values), max 60 epochs, patience 10 on S0-S6 `val` greedy PER, checkpoint every epoch, resume from the latest checkpoint.
- Expected base quality: worse than v2 (PER 0.269 on 24 days with a 5-layer GRU 1024). We go on whatever the base PER is, and report it.

## Simulated user (fixed now; reusable code `fidetype.trust.adaptive.FeedbackUser`)
| system action | user | label the system gets | loss the system sees | true loss |
|---|---|---|---|---|
| OFFER (top 5 sentences) | accepts if the truth is in the list | the truth | 0 | 0 |
| OFFER, truth not in list | retypes with probability `p_retype` = 0.8, else rejects | truth (retype) / none (reject) | 0 | 0 |
| COMMIT, right | keeps it | the committed text (= truth) | 0 | 0 |
| COMMIT, wrong | corrects it with probability `p_notice` | the truth | 1 | 1 |
| COMMIT, wrong, not noticed | nothing: **silent error** | the wrong committed text (label noise) | 0 | **1** |

`p_notice` in {0.5, 0.9, 1.0}. No sloppy accepts (`p_sloppy` = 0) in this pilot. User seed 0.

## Guarded update loop (fixed now; reusable code `fidetype.trust.adaptive.GuardedUpdateLoop`)
Per replay day, for every arm:
1. **Phase A** (items 1-48): the champion decoder (yesterday's layer) runs **offer-only**. Labels come from feedback.
2. **Update 1:** fit today's layer from yesterday's layer on the phase-A labels (arm-specific label source, below). The result is a **new decoder version**. It may not commit yet.
3. **Phase B** (items 49-96, `n_check` = 48 >= `min_ltt_items(0.05, 0.1)` = 45): the new version runs offer-only. Its scores on these items, which it did **not** train on, form the fresh check block. Truth from accept / retype; items with unknown truth count as a wrong commit at every threshold where they would commit (pessimistic).
4. **Recalibrate:** `block_ltt` (alpha 0.05, delta 0.1) on the check block -> day threshold `lambda_day` (infinite = offer-only for the rest of the day). Null controls on the new version (below).
5. **Phase C** (items 97 .. end of day): COMMIT iff score >= max(`lambda_day`, `lambda_aci`), the text is not empty (commit gate) and today's `SessionRiskMonitor` (alpha 0.05, gamma 0.1) has not alarmed. An alarm switches the rest of the day to offer-only. `OnlineCommitRiskControl(method="aci", eta 0.05)` runs across all days on the phase-C items and is fed the **observed** loss (a silent error looks like 0).
6. **Nightly update:** fit the layer again on all labels of the day (start: today's update-1 layer). It is tomorrow's champion (phase A of the next day is offer-only, so it needs no check).

Guarantee statements (what is and is not covered):
- per day: `P(R_phaseC <= alpha) >= 1 - delta` if phase C is exchangeable with the check block (the decoder does not change inside phase C);
- long run: the ACI certificate `(1/T) sum L_obs <= alpha + (lambda_T+1 - lambda_1) / (eta T)` on the **observed** losses, any sequence, across all decoder updates;
- monitor: false alarm <= gamma per day;
- **silent errors are not covered** by any of them. We measure them and report the true rate next to the observed one.

Commit score: `p_top1` = softmax of the n-best sentence scores / `T_s`, top entry. Phase A/B never commit.

## Arms (fixed now)
| arm | decoder update labels | trust |
|---|---|---|
| `frozen` | none: S6 layer every day | guarded loop |
| `feedback-p0.5`, `feedback-p0.9`, `feedback-p1.0` | user feedback labels only (accepts, retypes, corrections; uncorrected commits as labels) | guarded loop |
| `oracle` | the true text of every item (same schedule) | guarded loop |
| `selftrain` | its own top-1 sentence of every item (no user labels); CORP-style | guarded loop (the trust layer still sees user feedback) |
| `shuffled-labels` (null) | true labels, permuted inside each training set (no real signal) | guarded loop |
| `feedback-p0.9-naive` (contrast) | as `feedback-p0.9` | **no** recalibration: commit from item 1 of each day at the tuning-day threshold (fixed CRC on S7), no monitor, no offer-only phases |

Null inputs (every arm, every day with a finite `lambda_day`, after recalibration): 20 uniform log-prob streams (length of a random real trial) and 20 frame-shuffled real trials (bins permuted in time) go through the current version, threshold and gate. They must not commit.

## Adaptation settings: chosen on the tuning day S7 only (grid fixed now)
- Optimiser Adam on the day layer only (trunk frozen), loss CTC + `l2 * ||W - W_init||^2` (and the same for the bias), noise augmentation as in training.
- Grid: lr in {1e-3, 3e-3}, steps for update 1 in {20, 50}, `l2` in {1e-3, 1e-2}. Nightly: 3 epochs over the day's labels, batch 16, same lr and `l2`.
- Rule: simulate S7 as a replay day with true labels (start: S6 layer); update 1 on S7 items 1-48; pick the setting with the lowest greedy PER on S7 items 97 .. end. Ties -> fewer steps.
- `T_s`: grid 1 .. 50 (step 1), minimum Brier score of "top-1 sentence right" on S7 items with the selected update-1 layer.
- ACI start `lambda_1`: the CRC threshold (alpha 0.05) on the S7 phase-C items with that layer; if CRC is infeasible, 1.0 (never commit at the start). This is also the fixed threshold of the naive arm.
- The chosen values are written to `results/tuning.json` and committed before the replay starts.

## Metrics (aggregate only in the repo)
Per arm and per day: greedy phoneme PER (serving decoder, phase-C items and all items), top-1 sentence WER and exact rate, offer hit rate (truth in top 5), commits, wrong commits (true), observed wrong commits, silent errors, realised wrong-commit rate (wrong commits / all items; CP95), day risk on phase C, alarms, `lambda_day` feasible days, ACI certificate, labels used and label noise (wrong labels), null-input commits, eWPM (secondary; `SimulatedUser(UserConfig.aac_gaze(chars_per_min=304.0, p_detect_error=p_notice))`, one attempt). Day-cluster bootstrap (2,000, seed 20261116) for PER differences.

## Pre-registered success criteria (fixed now)
| id | criterion | pass if |
|---|---|---|
| **S1** guarantee holds during adaptation | every guarded arm: true wrong-commit rate over all replay items | <= 0.05 |
| **S2** per-day | every guarded arm: share of days with true phase-C risk > 0.05 | <= 0.10 (at most 1 of 16 days) |
| **S3** certificate | every guarded arm: observed phase-C mean loss <= ACI certificate (a code check; must hold by construction) | always |
| **S4** learning from feedback | `feedback-p0.9` mean phase-C PER over the 16 days minus `frozen` | <= -0.03 and day-bootstrap 95 % CI below 0 |
| **S5** null inputs | every arm: uniform + shuffled null-input commits | 0 (fail if > 5 % of null inputs) |
| **S6** no fake learning | `shuffled-labels` PER minus `frozen` PER | > -0.01 (it must not "learn") and S1 holds for it |
| D1 (descriptive) | self-training vs feedback vs frozen PER per day; sign of the PER trend of `selftrain - frozen` | expectation: self-training worse than feedback |
| D2 (descriptive) | naive arm true risk vs 0.05; commits and eWPM per arm (cost of the guarantee) | — |
| D3 (descriptive) | oracle - feedback PER gap per `p_notice` | — |

**Vacuity rule:** a guarded arm with fewer than 10 commits over all 16 days passes S1 / S2 only "vacuously". We say so, and we do not call it evidence that the guarantee is useful.

## Run rules
- CPU only: `.venv/Scripts/python.exe -m fidetype.utils.isolation run --class background --threads 4 -- <cmd>`; RAM < 8 GB (one day of features in RAM at a time during the replay).
- Long runs detached and hidden (`launch_detached.py`: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB), log file, resume per day (state saved after each day).
- Outputs with per-trial content only in `C:\Users\zhang\bci-data\derived\f1-e2-pilot\`. The repo gets the plan, the code, aggregate tables and `tuning.json`. No per-trial or decoded text in the repo.
- Any change to this plan after the first replay run is listed under "Deviations" in `results.md`.
