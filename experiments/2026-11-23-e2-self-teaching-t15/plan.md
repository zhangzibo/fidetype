---
title: E2 self-teaching on T15 (and T12) with a wrong-commit bound through every decoder update - pre-registration
type: experiment-plan
task: proposed P15-49 (frontier direction 1, HORIZONTAL; the GPU part of P15-03)
updated: 2026-11-23
---

# E2 full run: does a strong speech decoder learn from simulated feedback while the commit bound holds through every update? (pre-registration)

Written and committed **before** any base decoder of this task is trained and before any replay runs. Nothing is launched by this commit. The only numbers below are stream sizes from the data (labels only).

Pillar F1 of the [north star](../../wiki/questions/north-star.md#f1-safe-self-improving-bci-e2). It is the GPU part of roadmap [P15-03](../../wiki/questions/roadmap-standard.md#p15-03-e2-full-runs-on-t12-and-t15). The six earlier steps (P15-01, P15-02, P15-03a, P15-13, P15-23, P15-24) are in the [E2 write-up](../../wiki/questions/frontier-e2-self-teaching.md): the loop, the default-deny gate and the re-calibration rule are ready; **learning from feedback on a strong decoder has never run**.

## Hypotheses
- **H-learn.** A decoder that adapts only from simulated accept / reject / retype / correct feedback has a lower word error rate on later T15 sessions than the same decoder frozen.
- **H-bound.** Through every accepted update, the long-run wrong-commit rate stays within the stated bound, and every accepted update passes its null controls.
- **H-control.** Self-training on the decoder's own output, and training on shuffled labels, give no gain over frozen; the gate keeps their damage out of the commits.

## Data and licence
| item | value |
|---|---|
| T15 | Brain-to-Text '25 (Card et al. 2024, Dryad doi:10.5061/dryad.dncjsxm85), **CC0 1.0**. Inputs (read only): `C:/Users/zhang/bci-data/derived/m4-01-02-lookahead/` (45 sessions, 2023-08-11 to 2025-04-13) |
| T12 (stage 2) | Brain-to-Text '24 (Willett et al. 2023, Dryad doi:10.5061/dryad.x69p8czpq; local copy from the Zenodo deposit of the same DOI), **CC0 1.0**. Inputs (read only): `derived/2026-11-13-confirmatory-t12-v2/` (24 sessions) |
| Word route | B2T '25 phoneme beam + CMUdict lexicon + Tatoeba word / char LMs (Tatoeba CC BY 2.0 FR), the tuned P14-03 settings (lm 1.0, edit 12, bonus 3), read only |
| Own outputs | `C:/Users/zhang/bci-data/derived/e2-t15/` and `derived/e2-t12/` only |
| **Copy to a rented cloud machine?** | **Yes, allowed.** CC0 (T15, T12) has no conditions; CC BY 2.0 FR (Tatoeba-derived LM files) needs attribution only, which the repo already gives. No names or identifiers are in the data (T15 and T12 are public code names). Delete the copy when the job ends |

## Splits and time order (fixed now)
| part | T15 sessions | trials (labelled) | use |
|---|---|---|---|
| base | S0-S7 (2023-08-11 .. 2023-09-03) | 1,965 train (+ 265 val) | train the base decoder; its `val` trials monitor training only |
| tuning day | S8 (2023-09-24) | 279 | choose the fit settings (grid below) and the start guard. Never used again |
| replay | S9-S44 (2023-09-29 .. 2025-04-13), 36 sessions | **6,979** (80-364 per session) | the experiment |
| last third (primary window) | S33-S44 (2024-04-28 .. 2025-04-13), 12 sessions | 1,866 | the primary metric |

Stream of one replay session: its labelled `train` trials in file order, then its labelled `val` trials in file order (the recording order inside a session is not fully known; stated limit). The `test` partition has no labels and is not used.

**Why a new base decoder.** M4-13 trained on the train trials of all 45 sessions with one day layer each, so it cannot show learning on a new day (the same reason P15-01 did not use the T12 v2 decoder).

## Base decoder (M4-13 recipe on S0-S7)
- Code: `experiments/2026-11-15-m4-13-long-train/train.py` / `t15.py`, imported unchanged; a wrapper filters `load_part("train")` to S0-S7 and sets the own run folder. Model: L 0, 768 x 5 GRU, 45 day layers (layers of unseen days stay at their identity init).
- **30,000 steps** x batch 64 (about the same number of passes per trial as M4-13: 115,000 x 1,965 / 8,065 = 28,000, rounded up), cosine LR 5e-3 to 1e-4, seed 0. Last step, no selection.
- **Base stop:** if the greedy PER on the S0-S7 `val` trials at the last step is > 0.30, stop: the decoder is too weak for a meaningful trust test (outcome N).

## Replay loop (per arm, per session; code: `GuardedUpdateLoop` + `TrustGuardUpdater`, unchanged)
Extends the P15-01 / P15-02 day schedule to T15 with the P15-13 gate and the P15-24 re-calibration rule.

1. **Start of session d:** the day layer of d is a copy of the live version's day layer of the last session.
2. **Phase A** (items 1-24): the live champion runs **offer-only**. Labels come from the simulated user.
3. **Update 1** (decoder change, `kind="decoder"`): fit the day layer of d only, from the champion, on the phase-A labels (100 steps). This is the challenger. It may not commit yet.
4. **Phase B** (items 25-69, `n_check` = 45 = `min_ltt_items(0.05, 0.1)`): champion and challenger both decode; the shown output is the champion's offer (offer-only). These items are **held back**: no version that is tested on them has trained on them.
5. **Gate:** `GuardedUpdateLoop(challenger_test="noninferiority", recalibration_rule="absolute")`, margins 0.1 / 0.1, level 0.05; unknown truth counts against the challenger; block LTT on the check block gives `lambda_session`; uniform and frame-shuffled null controls (100 each, pass iff <= 5 commits) on the version that will go live. A refused challenger leaves the champion live (a same-decoder re-calibration of the champion's guard is then proposed with `kind="recalibration"`).
6. **Phase C** (items 70 .. end): COMMIT iff score >= max(`lambda_session`, `lambda_aci`), the evidence commit gate passes and the session e-process monitor (alpha 0.05, gamma 0.1) has not alarmed. `OnlineCommitRiskControl(method="aci", eta 0.05)` runs across all sessions on the phase-C items, fed the **observed** loss.
7. **Nightly update:** fit the day layer of d + the last GRU layer + the output layer, on all labels of sessions <= d that the arm may use (300 steps). It becomes the challenger of session d + 1 at its phase B (it must pass the gate before it commits).

Every accepted version gets a new `config_id`, chained in the provenance ledger. Fits use the M4-13 CTC step (`collate`, `micro_chunks`, augmentation) with AdamW; phonemes from CMUdict; items with an out-of-lexicon word give no phoneme label.

## Arms
| arm | training labels | role |
|---|---|---|
| **F** frozen | none (the guard still re-calibrates through the gate) | baseline |
| **FB** feedback-only | what the simulated user gives: accepted offers, retypes, corrections, and kept commits (including silent errors, which are wrong labels) | **primary** |
| **OR** oracle | the true text of every item | upper bound |
| **ST** self-training | the decoder's own top-1 text on every item (no user labels) | negative control (confirmation bias) |
| **SH** shuffled labels | the FB labels, permuted at random inside each training set | negative control (no real signal) |

## Simulated users (`fidetype.trust.adaptive.FeedbackUser`; offer = top 5)
| user | `p_retype` | `p_notice` | role |
|---|---|---|---|
| **U1** | 0.3 | 0.9 | primary |
| **U2** | 0.1 | 0.5 | stress: little feedback, many silent errors |

`p_sloppy` 0. The user seed and the fit batch order follow the run seed. A personal-use acceptance calibration (P15-03 deliverable) is not part of this plan (`t15_personalUse.pkl` is not local).

## Fit-setting grid on S8 (chosen before the replay; never revisited)
Update-1 LR {1e-4, 3e-4} x nightly steps {150, 300}. Rule: the FB arm with U1, seed 0, on S8 only; choose the setting with the lowest phase-C WER of S8; ties to the smaller LR and fewer steps. The grid result is committed before the replay starts. (The step counts in "Replay loop" are the defaults; the chosen setting replaces them for all arms.)

## Seeds and runs
Seeds 0 and 1. 5 arms x 2 users x 2 seeds = **20 runs** (16 with fits; F has none). Run order (so the primary finishes first): F-U1-s0, FB-U1-s0, F-U1-s1, FB-U1-s1, SH-U1-s0/s1, ST-U1-s0/s1, OR-U1-s0/s1, then the same for U2.

## Primary metric
Phase-C WER of the **live** output (top-1 word text of the version that is live at that item, before the item is used for training) on the 12 sessions of the last third, arm FB minus arm F, user U1, per seed. Paired over items; CI95 by a **session-cluster bootstrap** (2,000 resamples of the 12 sessions, seed 0).

## Pass / fail rules (fixed now)
| id | rule | pass if |
|---|---|---|
| **P1 learn** (primary) | FB − F phase-C WER, last third, U1 | <= **−0.02** and CI95 upper < 0, on **2 / 2** seeds |
| **P2a bound (identity)** | every guarded run: observed long-run phase-C wrong-commit rate <= alpha + (lambda_{T+1} − lambda_1) / (eta T) (the `aci` bound G1 of the [guarantee scope](../../wiki/questions/f1-guarantee-scope.md)) | all 20 runs (a fail means a code fault) |
| **P2b realised rate** | true phase-C wrong-commit rate (silent errors included) over the whole replay | <= 0.05 in every U1 run (CP95 reported); U2 descriptive |
| **P3 nulls** | uniform and shuffled null controls of every **accepted** update | pass on 100 % of accepted updates, all runs |
| **P4 controls** | SH − F phase-C WER, last third, U1 | > −0.005 on both seeds (no fake learning), and P2b holds for SH and ST |
| P5 gate audit | ledgers verify; each proposal has a decision; the config changes on accept only | all runs |

## Reported, never claimed as covered
- **Silent errors:** per run, the count and rate of wrong commits the user did not correct, and the gap between the observed and the true wrong-commit rate. No guarantee covers them.
- **Guarantee scope** (as stated in the north star risks): only the long-run `aci` bound and the e-process alarm hold across updates. A per-session finite-sample statement holds only for phase C of a session, from its fresh check block, if phase C is exchangeable with it. We report the share of sessions whose phase-C true rate is > 0.05, without a claim.
- Selected labels: FB trains on what the trust layer chose to show. The SH and ST arms and the gate are the checks; ST is reported even if it looks good.
- Per run: accepted / refused updates and why, labels used, commit rate, precision, eWPM, safe WPM v0.2 (descriptive), PER and WER of the latest trained version regardless of the gate (the "learning" view), OR − FB gap.

## Outcomes and what each means
| outcome | condition | meaning |
|---|---|---|
| **A** | P1, P2a, P2b, P3, P4, P5 pass | The F1 claim on T15: the decoder learns from feedback and the stated bound holds through every accepted update (simulated user, one participant). Safe wording of the north star applies |
| **B** | P2-P5 pass, P1 fails | The bound holds, but feedback learning gives no reliable gain on T15 (drift may be small, or the gate refuses most updates). Report how many updates were refused and the OR − F gap: if OR also gives no gain, T15 has little drift to learn |
| **C** | P1 passes, P2b or P3 fails | Learning works, but the safety story fails: no F1 claim. The fault goes to the gate or the bound |
| **D** | P4 fails | The gain is not from feedback (shuffled labels also "learn"): P1 is not evidence |
| **X** | P2a or P5 fails | Code fault; no result until fixed and rerun |
| **N** | base stop, or the U1 F / FB runs of both seeds do not finish | Not determined |

## Stage 2: T12 (if feasible)
Same loop, arms, users, rules and seeds on T12 with the P15-01 time order (base S0-S6, tuning S7, replay S8-S23, 16 sessions) and the T12 v2 GRU recipe (`experiments/2026-11-13-confirmatory-t12-v2/train_decoder.py`, imported unchanged) on S0-S6 only. Primary window: the last 5 replay sessions. It starts only after the T15 U1 runs finish and if the GPU cap leaves at least 8 h. Its verdict is reported next to T15, never instead of it.

## Stop rules
- Base stop (above). Broken-fit stop: a fit with a non-finite loss is refused by the gate (counted), not retried.
- **GPU cap:** 30 h rented or 90 h local GPU time (sum over launches), checked before each run. At the cap: finish the current run, report the other runs "not run (cap)".
- No early stop on any value. No change of arms, users, rules, windows or the grid after this commit.

## Compute estimate
GPU steps: base 30,000 full steps; fits 16 runs x 36 sessions x (100 + 300) = 230,400 fit steps (+ 1,600 for the S8 grid).

| part | local RX 7800 XT (ROCm) | rented A100 / H100 class (CUDA) |
|---|---|---|
| base decoder | about 10.6 h (1.27 s / step, M4-13) | about 2.5-3.5 h, **our estimate** |
| fits (batch 24-32, 3 of 5 parameter groups trainable) | about 30-45 h (0.5-0.7 s / step, **our estimate**; the speed test measures it) | about 8-12 h, **our estimate** |
| forward passes of all versions + null controls | about 3-5 h | about 1 h |
| word decoding (CPU, about 0.5-1 s per decode; about 22,000 decodes per run) | about 60-120 CPU-core-h; with 4 workers 15-30 h wall | about 3-6 h wall on 32 vCPU |
| **total** | **about 45-60 GPU-h + CPU** (it blocks the local GPU for 2-3 days) | **about 12-17 GPU-h** (+ CPU on the same machine) |
| T12 stage 2 | about 15-25 h | about 4-7 h |

`tools/rental/speed_test.py` prints the measured projection for the GPU part before any rental is used for long.

## Where it may honestly fail
- T15 drift after the first months may be small (the published decoder keeps high accuracy with periodic retraining), so frozen stays good and P1 fails (outcome B). OR shows whether there was anything to learn.
- With U1 the gate may refuse most updates, because 45 check items give little power (P15-13: p 0.038 and 0.026 for a much better decoder). This is the safe direction, but slow.
- The base decoder on 8 sessions may be much weaker than M4-13, so few commits happen and the bound is close to vacuous (P15-01 lesson). We report commits per session.
- The simulated user is not a real user. One participant per dataset. Two seeds.
- Silent errors in U2 can push the true rate above 0.05 while the observed bound holds; that is a stated limit, not a pass.

## Order and outputs
1. Commit this plan (this commit). 2. Commit the wrapper, the replay script (it imports the P15-13 / P15-24 run structure, the P15-01 phase logic and the M4-13 training step; no re-implementation of the gate) and CPU tests; a dry run on S8 only with a small step count. 3. Base, grid, replay. 4. `results/results.json` (aggregates, no text), `results.md`. Ledgers and per-item outputs stay in the derived folder.
