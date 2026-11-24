---
title: T15 decoder with a 2,216-trial calibration hold-out - calibration-inclusive safe WPM v0.2 against gaze typing - pre-registration
type: experiment-plan
task: proposed P15-48 (frontier direction 2, VERTICAL on our own safe-WPM metric)
updated: 2026-11-23
---

# T15 calibration hold-out retrain: is the certified pipeline reliably faster than gaze typing? (pre-registration)

Written and committed **before** any decoder of this task is trained and before any number of this task exists. Nothing is launched by this commit (the local GPU is busy; no GPU is rented). The only numbers below are split sizes from a data audit (`holdout.py audit`, text and labels only, no decoder output).

Direction 2 of the frontier plan (2026-11-23). Continues gap 160 ([P15-39](../../wiki/questions/roadmap-standard.md#p15-39-labelled-t15-like-calibration-data-for-the-calibration-inclusive-safe-wpm), `externally_blocked` on "new labelled data"). This plan makes the labelled data **ourselves**: we take it out of the decoder's training partition. Write-up context: [frontier safe WPM](../../wiki/questions/frontier-safe-wpm.md).

## Hypothesis
H. With a calibration pool of about 2,700 labelled T15 trials (3.7 x the 722 of `val_select`), the calibration-inclusive 95 % interval of the adopted safe WPM v0.2 has a lower end above gaze typing (4.0153 on `val_eval`).

Why it may be true: on T15 the between-draw SD of the safe WPM is 2-3 times the within-draw SD (P15-34, P15-37). The P15-40 fit gives SD proportional to n^-0.48 [0.12, 0.83] and n* about 2,520 [1,080, 460,000] calibration items. Why it may be false: the decoder loses 27.5 % of its training trials, so it gets weaker, and a weaker decoder commits less.

## Data and licence
| item | value |
|---|---|
| Dataset | Brain-to-Text '25, participant T15, `t15_copyTask_neuralData.zip` (Card et al. 2024, Dryad doi:10.5061/dryad.dncjsxm85) |
| Licence | **CC0 1.0** (Dryad). No conditions |
| Local inputs (read only) | `C:/Users/zhang/bci-data/derived/m4-01-02-lookahead/` (45 session NPZ files, `sessions.json`, `texts.json`; 9.9 GB; the M4-01/02 features and phonemes that M4-13 used) |
| Other inputs (read only) | CMUdict (BSD-2-Clause style licence), Tatoeba English corpus and our char / word LMs built from it (Tatoeba: CC BY 2.0 FR), Qwen2.5-1.5B-Instruct GGUF Q4_K_M (Apache-2.0) for the P15-22 LLM rescoring |
| Own outputs | `C:/Users/zhang/bci-data/derived/t15-calho/` only. The code refuses to write into `m4-01-02-lookahead` or `m4-13` |
| **Copy to a rented cloud machine?** | **Yes, allowed.** CC0 has no conditions. CC BY 2.0 FR (Tatoeba-derived LM files) and Apache-2.0 (Qwen) allow copies with attribution. The data hold no names; T15 is a public code name; session folder names are recording dates, which the public dataset already publishes. Delete the copy and the volume when the job ends (rental kit README) |

## Splits (fixed now; rule in [`holdout.py`](holdout.py), tests in [`test_holdout.py`](test_holdout.py))
Facts from the data (audit, 2026-11-23): `train` partition 8,072 trials, 8,065 with known phonemes; `val` partition 1,426 trials = `val_select` 722 (even index per session) + `val_eval` 704 (odd index; 701 labelled); the `test` partition has no labels and is not used. Of the 8,065 train trials, 1,418 belong to 653 sentences that occur more than once (copy-task sentences repeat by design). 81 of the 704 `val_eval` sentences also occur in `train`.

**Hold-out rule.** Group the labelled train trials by normalised sentence text. Hold out a whole group iff the first 16 hex digits of SHA-256(`fidetype-t15-calho-2026-11-23|group|<text>`) / 16^16 < 0.2727. Then the 250 held-out items with the smallest SHA-256(`...|tune|<key>`) form the **pipeline-tune set**; the rest of the hold-out joins the calibration pool.

| part | trials | use |
|---|---|---|
| decoder train (kept) | **5,849** (72.5 % of 8,065) | trains the new decoder; length filter of M4-13 applies |
| pipeline-tune set | **250** | fits the pipeline values only (frame temperature T, grounding tau, fluent threshold); never in a calibration draw |
| hold-out to calibration | **1,966** | calibration pool |
| `val_select` | **722** | calibration pool; also the training-curve monitor (no checkpoint selection, see below) |
| **calibration pool** | **2,688** | input of every calibration draw |
| `val_eval` | **701** | the evaluation set; decoded once per guard |

- Held-out share per session: 0.17 to 0.37 (45 / 45 sessions have held-out trials).
- **No held-out sentence is a training sentence** of the new decoder (0 overlaps, by construction). In `val_eval`, 81 sentences also occur in the original train partition. So the pool is, if anything, harder than `val_eval` for the decoder; this makes the guard more conservative, not less safe. We report the overlap counts of the final split.
- Known exchangeability risk: the pool mixes train-block trials (held out) and val-block trials (`val_select`), while `val_eval` is val-block only. We report, for the first draw's guard, the wrong-commit rate of the held-out part and of the `val_select` part separately (descriptive).

## Decoder (the M4-13 recipe, unchanged except the training set)
- Code: `experiments/2026-11-15-m4-13-long-train/train.py` and `t15.py`, imported unchanged. A thin wrapper (written after this plan) filters `load_part("train")` to the kept keys, sets the run folder to `derived/t15-calho/runs/m4-13-calho-s0` (the recipe asserts the `m4-13-` prefix), and does nothing else.
- Model `fidetype.decoders.lookahead_gru`, L 0 (causal), hidden 768 x 5 layers, 45 day layers; 115,000 steps x batch 64, cosine LR 5e-3 to 1e-4, same augmentation and seed 0.
- **Checkpoint: the last step** (no selection). M4-13 had best = last; this removes any use of `val_select` labels for selection, so `val_select` stays clean for calibration.
- Platform: either the local RX 7800 XT (ROCm, cuDNN off, as M4-13) or a rented NVIDIA GPU (CUDA). On CUDA the wrapper turns cuDNN on (the ROCm switch-off is a MIOpen bug workaround, not part of the recipe) and keeps TF32 off. The platform is recorded. Results are not bit-identical across platforms.
- Decode: log-probs of the tune set, the pool and `val_eval` with the M4-13 `decode.py` route, then the P15-05 / P15-22 n-best pipeline (B2T '25 word decoder, edit 12; LLM rescoring arm B1 with grounding; lambda pinned 1.0, `max_variants` 16, `demote_margin` 1.0). T, tau and the fluent threshold are fitted **on the 250 tune items only**, with the P15-05 fitting code.

## Arms (all on the same `val_eval` 701 trials)
| arm | decoder | calibration pool | role |
|---|---|---|---|
| **A** (primary) | new decoder | 2,688 | the test of H |
| **B** (pool-size control) | new decoder | `val_select` 722 only | isolates the effect of the pool size from the decoder change |
| **R** (reference) | M4-13 (`m4-13-long0`) with its pinned P15-22 values | `val_select` 722 | today's line under the same v0.2 / K = 120 protocol (CPU only; cached decodes) |

## Calibration-inclusive protocol (adopted v0.2 and section 6b)
- Guard: L1 of P15-22 (`calibrate(confidence="learned", confidence_l2=1.0)`, alpha 0.05, delta 0.1, the commit gate, `null_trials` 300, sentence commits).
- **K = 120 partition-only draws** per arm. Draw k: calibrate seed = first 8 hex digits of SHA-256(`t15-calho|<arm>|cal|<k>`); a new permutation of the pool; `_split(2,688)` = fit 672 / policy 1,008 / LTT 1,008 (arm B and R: 180 / 271 / 271). No resampling inside a part.
- Inner level: B = 2,000 multinomial trial resamples of `val_eval` (`default_rng(0)`), the same for all draws.
- Metric: **safe WPM v0.2 as adopted** (reading cost `aac-gaze-v1`: 0.5 s + 0.3 s per committed word per commit; measured trial durations; default correction rule). Credit rule: a draw that is refused, not certified, above alpha or vacuous adds 0.0. Code: `fidetype.benchmark.safe_wpm.calibration_draw_interval(..., draw_scheme="partition")` (it marks K >= 80 partition-only intervals as an adopted headline).
- Reference: gaze typing on `val_eval`, **4.0153** WPM (unchanged).

## Primary metric
The 2.5th percentile (lower end) of the pooled K x B safe-WPM v0.2 values of arm A.

## Pass / fail rules (fixed now)
| id | rule | pass if |
|---|---|---|
| **P1** (primary) | calibration-inclusive lower end, arm A, K = 120 | **> 4.0153** |
| P2 (decoder validity) | new decoder greedy PER on `val_eval` | <= 0.1410 (M4-13 0.1210 + 0.02) |
| P3 (controls) | per draw: both null controls of `calibrate` pass (else the draw credits 0 and is counted); the hallucination protocol 0.2 swapped-signal track on the draw-1 guard of arm A | >= 114 / 120 draws (95 %) pass both nulls, **and** swapped track verdict "pass" |
| S (safety) | mean test wrong-commit rate over the 120 draws of arm A; the count of draws above 0.05 | mean <= 0.05 (count reported) |

## Outcomes and what each means
| outcome | condition | meaning |
|---|---|---|
| **A** | P1, P2, P3, S pass | The certified T15 pipeline is above gaze typing after calibration uncertainty (v0.2, K = 120), with a decoder close to M4-13. A headline candidate. The user decides the public wording |
| **A'** | P1, P3, S pass; P2 fails | Above gaze typing after calibration uncertainty, but with a weaker decoder. The claim holds for this decoder; it does not replace the M4-13 numbers |
| **B** | P1 fails; mean of arm A > 4.0153 | Above on average, not reliably. Arm B vs A says how much the pool size helped; the between-draw SD of A tests the P15-40 projection |
| **C** | mean of arm A <= 4.0153 | The weaker decoder costs more than the larger pool gains. T15 needs more data, not more method |
| **X** | P3 or S fails | No claim from arm A. The cause (a control or the bound) is reported |
| **N** | fewer than 80 draws of arm A finish | Not determined |

A negative result is a valid result and is written up.

## Prediction (not a rule)
P15-40 (exponent 0.48) predicts a between-draw SD of about 0.884 x (722 / 2,688)^0.48 = **0.47** WPM for arm A if the decoder stays the same. We report the measured SD next to it.

## Stop rules
- **Broken-run stop (training).** If the `val_select` greedy PER at 25 % of the budget is > 0.20 (M4-13: 0.1392), or the loss is not finite for 100 consecutive steps, stop. Check the platform port. A restart is a new launch, listed as a deviation; no rule changes.
- **GPU cap.** 60 h local or 20 h rented GPU time (sum over launches). At the cap: stop, report "not run (cap)".
- **Draws.** Run all 120 draws per arm in a fixed order (A, then B, then R). No stop on any value. Minimum K for a verdict: 80.
- No change of split, arms, metric, rules or K after this commit. A variant is a new item with its own plan.

## Seeds
Decoder seed 0 (one training run; budget). Calibration draw seeds as above. Bootstrap seed 0.

## Compute estimate
| part | local RX 7800 XT (ROCm) | rented A100 / H100 class (CUDA) |
|---|---|---|
| training, 115,000 steps | **about 41 h** (M4-13 measured 1.27 s / step; the step cost does not depend on the number of trials) | **about 10-14 h, our estimate (3-4 x faster; unverified)**: run `tools/rental/speed_test.py` first; it prints the projection |
| log-probs of 3,639 trials | minutes | minutes |
| n-best + LLM rescoring of 3,639 trials (CPU) | about 1-3 h (4 threads) | about 0.5-1 h on 16+ vCPU |
| 3 arms x 120 draws (CPU; 12-32 min per draw in P15-29, mostly the null-control decodes) | about 70-190 CPU-process-h; with 2 workers x 4 threads about 1.5-4 days | about 10-25 h wall on 32 vCPU (8 workers) |
| **total rented** | - | **about 12-16 GPU-h + the CPU stage** (the CPU stage can also run locally for free) |

Recommended split: train on a rented GPU (or locally when free), run the CPU draws locally.

## Where it may honestly fail
- The decoder gets weaker with 72.5 % of the training trials, and the commit rate falls more than the interval tightens (outcome C).
- The pool mixes train-block and val-block trials. If they are not exchangeable with `val_eval`, the guard can be off in either direction. S and the per-part diagnostic show it.
- One participant, one decoder seed. The draws replicate the calibration, not the decoder training.
- The CUDA port can change the decoder slightly; the broken-run stop catches only large faults.
- The n* projection has a very wide CI ([1,080, 460,000]); 2,688 can still be too few.
- v0.2 adds a reading cost, so values are a little lower than the earlier v0.1 numbers (5.18 [0.00, 6.99], v0.1).

## Order and outputs
1. Commit this plan, `holdout.py` and its tests (this commit).
2. Commit the training wrapper, the decode / pipeline / draw scripts and their CPU tests; a smoke run on the tune set only (it never reads `val_eval`).
3. Train (local or rented). Decode. CPU stage. Write `results/results.json` (aggregates only, no text) and `results.md`.
4. Per-trial decisions with text stay in `derived/t15-calho/`. No weights, signals or texts in the repo.
