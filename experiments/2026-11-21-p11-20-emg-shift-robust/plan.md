---
title: P11-20 Shift-robust calibration for the EMG L-FL guard - pre-registration
type: experiment
task: P11-20
updated: 2026-11-21
---

# P11-20: shift-robust calibration for the EMG L-FL guard (pre-registration)

Written and committed **before** any number of this item was computed. Gap 164 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-20](../../wiki/questions/roadmap-standard.md#p11-20-shift-robust-calibration-for-the-emg-l-fl-guard). Source: [P11-18](../2026-11-21-p11-18-emg-above-alpha/plan.md) ([results](../2026-11-21-p11-18-emg-above-alpha/results.md)). Base: [P11-17](../2026-11-21-p11-17-emg-calibration-ci/plan.md), [P11-14](../2026-11-20-p11-14-emg-lm-confidence/plan.md) arm L-FL.

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates and per-draw counts only: no per-user value, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt files and log-probs stay in `C:\Users\zhang\bci-data\derived\p11-20\`. The P11-01, P11-09, P11-11, P11-14, P11-17 and P11-18 files are read only.

CPU only. At most 4 threads in total (inference: 1 process x 4 threads; draws: 4 workers x 1 thread, isolation class `background`). **No GPU.**

## Problem
P11-18 found a val -> test session shift. On the track-test session the wrong-commit rate of the L-FL guard is on average 1.26 points above the LTT in-sample rate (arm P, partition-only); without the shift (pooled arm E) the gap is -0.16 points (Welch p = 3.6e-10). 3 / 40 partition-only draws were above alpha = 0.05 on test, all at 62 / 1,221 wrong. LTT assumes that the calibration and test prompts are exchangeable. Across sessions they are not.

## How the split is defined (checked before this plan)
P11-01 `prep.py make_splits`: 8 test users. Per test user, the sessions in date order are: `train` (all but the last 4; personal fine-tuning), `val` (the 2 before the last 2; checkpoint selection of the personal model, `best.pt`), `test` (the last 2). The fidetype track and P11-09 use the two P11-01 `test` sessions: the earlier one is **track val** (j = 0, calibration, 1,224 prompts), the later one is **track test** (j = 1, evaluation, 1,221 prompts). So each user has one calibration session and one test session. Two earlier sessions per user exist that are in neither track split: the P11-01 personal `val` sessions. In this plan: session **a** = the earlier personal-val session (4th from last), session **b** = the later one (3rd from last). All 16 have a cached P11-01 feature file, a label file and the raw HDF5 file.

Session order per user: train ... < **a** < **b** < track val < track test.

## Idea
Estimate the size of a one-session risk shift on sessions that the track does not use (a -> b), and calibrate the guard on track val with a tighter LTT level alpha' = alpha - m. Then check on track test, which shaped nothing.

## Why the guarantee still holds (stated before any result)
Let g be the guard that LTT outputs from the track-val calibration prompts, R_val(g) its risk on the track-val session population and R_test(g) its risk on the track-test session population.
1. The margin m is a function of sessions a and b only (and of the pinned decoder, LM, lexicon and guard code). Its computation reads **no prompt and no window of track val or track test**: the margin draws use only session-a prompts for fitting and LTT, the automatic calibrate null controls built from session-a windows (no `null_inputs`), and session-b prompts for the evaluation. So m is fixed before, and independent of, the track-val LTT data. The track-test data are not touched until arm S is decided.
2. Given m, alpha' = alpha - m is a fixed level for the arm S calibration. LTT at alpha' then keeps its exact guarantee on the calibration population: P(R_val(g) > alpha') <= delta = 0.1 over the calibration draw (partition-only draws; no resampling, so no duplicate effect).
3. **Assumption (A), bounded shift:** R_test(g) <= R_val(g) + m. In words: one session step raises the risk of the guard by at most the amount that one earlier session step (a -> b) raised it for the same users. Under (A), P(R_test(g) > alpha) <= P(R_val(g) > alpha') <= delta.
4. (A) is an assumption, not a distribution-free fact. The track-test results of arm S are an honest check of (A), because no test number was used to choose m, alpha' or any rule. A margin read off the P11-18 test gap (+0.0126) is **not** used.

Known ways (A) can fail (limits, stated now): sessions a and b were the checkpoint-selection sessions of the personal models, so the decoder is slightly in-sample on both. The a -> b step can therefore be smaller than a step between two sessions that the model never saw. The drift can also grow with the distance from the training sessions (track test is two steps further away than b).

## Fixed parts (as P11-14 / P11-17 / P11-18, unchanged)
Data, windows (prompt frames + 20 tail frames), target, decoder FL, the no-signal gate, the OOV gate, the competitor set and the 10 signals; arm L-FL with the P11-14 model-fit rule (`Learned.fit`); `calibrate` settings (delta 0.1, LTT, `confidence="p_top1"`, `input_kind="logits"`, key-CTC vocabulary, `audit_text=False`, 300 automatic uniform and frame-shuffled null trials); safe WPM v0.1 with the default correction rule; no-BCI reference 3.09; the P11-17 credit rule (certified and V6 evaluation controls <= 5 %). Pinned: decoder weights, gate thresholds, LM, lexicon, arm choice.

## Stage 0: data for sessions a and b (and code checks)
- **Inference** (torch venv `C:\venvs\fidetype-rocm`, device cpu, 4 threads): the P11-01 personal model of each user (`best.pt`) -> causal log-probs of sessions a and b, with the P11-09 `stage_infer` code path (`emgdec.CRT`, `SessionStore`, `session_log_probs`). Real input only. Files: `derived\p11-20\lp\u<i>-a-real.npy`, `u<i>-b-real.npy`.
- **Prompts**: the P11-09 `stage_prompts` rule (P11-01 prompt-keep rule; key events of the prompt with a key class; >= 3 in-vocabulary keys; window [lo, min(hi + 20, n_frames)); windows shorter than 2 frames skipped). Truth = `intended_truth` of the key codes (P11-11).
- **C1 (must pass):** the same prompt builder, run on the 16 track sessions, reproduces the P11-09 `prompts.json` rows (fields i, j, session, k, lo, hi, end, codes) exactly.
- **C2 (must pass):** the same inference code, run on track-val session u0, reproduces the P11-09 file `u0-s0-real.npy`: max absolute probability difference <= 1e-3 and frame argmax agreement 1.0 (the P11-09 amendment-2 rule).
- If C1 or C2 fails, no margin and no arm S result are reported.

## Stage 1: the margin (draws M01-M40), sessions a -> b only
For j = 1 ... 40:
1. seed s_j = seed_of(`"p11-20|emg|m|<j>"`) (first 8 hex digits of SHA-256, as an integer).
2. Calibration list = all session-a prompts of the 8 users (P11-09 row order: user, then prompt). Partition-only draw: P11-17 `draw_order(n_a, s_j, None)` with `_split(n_a)` sizes; no resampling.
3. Refit the L model on the fit + policy parts (P11-17 `fit_model`).
4. `calibrate` at alpha = 0.05, delta = 0.1, seed s_j, `null_inputs=None` (automatic controls only).
5. Record the LTT in-sample risk r_LTT = wrong commits of the deployed guard on the draw's LTT prompts / n_LTT (same `same()` rule as the test), and the risk on session b: r_b = wrong commits on all session-b prompts / n_b (real windows).
6. One-step gap g_j = r_b - r_LTT.
7. Descriptive only (never used for a decision): the same guard on all track-val prompts (two-step gap a -> track val).

**Margin rule:** m = max(0, mean of g_j over the draws that produced a guard). alpha' = floor((0.05 - m) x 10^4) / 10^4.
- If fewer than 30 of 40 margin draws produce a guard, or m >= 0.05, arm S is not run and the item reports why.
- If m = 0, then alpha' = 0.05 and arm S equals P11-18 arm P by construction (same seeds, same partitions, same alpha). Then only S01 is run as an identity check, and the arm S numbers are the P11-18 arm P numbers.

## Arm S (primary): track val -> track test at alpha', K = 40 partition-only draws
For k = 1 ... 40: exactly the P11-18 arm P draw k (seed seed_of(`"p11-18|emg|cal|<k>"`), permutation of the 1,224 track-val prompts, `_split` = 306 / 459 / 459, no resampling, L model refit on fit + policy, 300 input-level time-shuffled null inputs of the P11-18 pick), with **one change: `calibrate(alpha=alpha')`**. Decide all 1,221 test prompts: real, time-shuffled, zero EMG. The draws are paired with P11-18 P01-P40 (same partition; only the LTT level differs).

Scoring: the claim is still alpha = 0.05 (the margin is part of the method). So safe WPM uses the sheet guarantee with `alpha` set to 0.05 (`ltt_alpha` = alpha' and m are recorded beside it). A draw is **above alpha** if test wrong commits / 1,221 > 0.05 (>= 62 wrong). Credit: the P11-17 rule.

## Arm P2 (secondary): more partition-only draws at alpha = 0.05
P41-P80: the P11-18 arm P procedure unchanged, seeds seed_of(`"p11-18|emg|cal|<k>"`) for k = 41 ... 80 (the same seed family). Pooled with the P11-18 P01-P40 draws (read only from `derived\p11-18\draw-P*.json` and the committed P11-18 results.json) -> K = 80 partition-only draws.

## Code check X5 (must pass)
Draw R01 = P11-18 P01 rerun by this item's code at alpha = 0.05: it must give the same threshold, commits, wrong commits and 1,221 / 1,221 identical real, time-shuffled and zero-EMG decisions as `derived\p11-18\draw-P01.json`. If X5 fails, no arm S or P2 result is reported. R01 is not one of the K draws.

## Metrics
- Stage 1: m, alpha'; mean / SD / range of g_j, r_LTT, r_b; draws with a guard; statuses; the descriptive two-step gap.
- Arm S: above-alpha fraction f_S (vs 0.05); also the fraction above alpha' (descriptive); significant exceedances (w >= 75, as P11-18); test rate, LTT in-sample rate and optimism gap (test - LTT in-sample) mean / SD / range; commits, wrong commits, thresholds; statuses; control counts.
- Arm S vs P11-18 arm P (paired by k): draws where the test wrong count goes down / stays / goes up; exact McNemar test on above-alpha (discordant pairs, two-sided binomial).
- Arm S calibration-inclusive interval: P11-17 primary procedure unchanged (40 draw values x the same B = 2,000 user-cluster weight vectors; non-credited draws earn 0.0; pooled 2.5 / 97.5 percentiles; point = mean); X1 decomposition; library `calibration_draw_interval` (secondary); variants V-a and V-b (descriptive). Verdict vs 3.09 with the P11-17 rule.
- Arm P2 / K = 80: x_80 = above-alpha draws of P01-P80; one-sided Fisher 9 / 40 (P11-17 bootstrap) > x_80 / 80; the K = 80 interval (descriptive) and optimism gap.

## Decision rules (fixed here)

**Primary (arm S, done-when):**

| f_S (of 40) | conclusion |
|---|---|
| 0 or 1 | **margin removes the excess** (f_S <= 2.5 %, as the no-shift arm E) |
| 2 to 4 | **within delta, excess not removed** |
| >= 5 | **margin not enough** (f_S > delta) |

Interval verdict vs 3.09: the P11-17 rule ("clearly above after calibration uncertainty" / "above, but inside the combined interval" / "not above").

**Assumption check:** (A) is "not contradicted on test" if the mean arm S test rate is <= 0.05 and f_S <= 4; else "(A) fails on test".

**Secondary (K = 80, P11-18 step 1 rule with n = 80; delta x 80 = 8):** one-sided Fisher tail values 9 / 40 vs x / 80: x = 6: 0.023; x = 7: 0.038; x = 8: 0.060; x = 9: 0.090.

| x_80 | conclusion |
|---|---|
| <= 7 (p < 0.05, <= delta) | **duplicates** (the P11-18 verdict becomes firm) |
| 8 (p = 0.060, <= delta) | **partly duplicates**, still inconclusive at K = 80 |
| >= 9 (> delta) | **noise + shift** (the excess stays without duplicates) |

Expectation (stated now, not a rule): the a -> b step may show a smaller shift than val -> test (both a and b are checkpoint-selection sessions), so m may be small and f_S may stay near 3 / 40.

## Gap rule
**Gap 164 closes** when results.md reports, under this plan with C1, C2 and X5 passed: m and alpha' from sessions a -> b; f_S with K = 40 partition-only draws; the arm S calibration-inclusive interval vs 3.09; and the K = 80 secondary result, whatever they are. If a check fails or arm S cannot run (margin rule), results.md says why, and the gap stays open.

## What was done before this plan (disclosure)
Reading of the gap 164 entry, the P11-20 roadmap row, the P11-18 plan / results / run.py / launch.py / test, the P11-17 run.py, the P11-09 `sessions`, `stage_infer`, `stage_prompts` and `Windows`, the P11-01 `make_splits` rule and checkpoint selection, `safe_wpm.certification`, `calibrate`'s signature. File existence checks for the 16 personal-val sessions (feature, label and HDF5 files exist). The Fisher tail values for 9 / 40 vs x / 80. No inference, no prompt count of sessions a / b, no draw, no guard and no score of this item was computed before this commit.

## Order, limits, outputs
1. Commit this plan. Then commit `run.py` (imports the P11-18 / P11-17 / P11-09 / P11-11 / P11-14 runners read only; writes only to `derived\p11-20\`), `launch.py` and a test on synthetic data.
2. Run detached from a `git archive` snapshot of the committed code, with keep-awake: stage 0 (`infer` in the torch venv, 4 threads; `prompts` with C1 / C2), then 4 workers x 1 thread for R01, M01-M40, P41-P80 (round robin), then `margin`, then 4 workers for S01-S40, then `analyse`. Log `results/run.log`; `DONE` file `C:\Users\zhang\bci-data\derived\p11-20\DONE`. Each worker keeps its own window memo (`derived\p11-20\feat-w<w>.pkl`, started from a copy of `derived\p11-18\feat-w<w>.pkl`, read only). Each finished draw is saved as `derived\p11-20\draw-<name>.json` and skipped on a rerun.
3. The repo gets `results/results.json` (aggregates and per-draw counts) and `results/run.log`.
4. No change of the arms, K, seeds, margin rule, metrics or decision rules after this commit. Any later variant is a new item.

Known limits (stated before any result):
- (a) Assumption (A) is not testable on calibration data alone; the a -> b step can under-state the val -> test step (checkpoint selection on a and b; growing distance from training).
- (b) One shift instance per user: m averages split variation over 40 draws, not session-to-session variation of the shift.
- (c) Pinned decoder, gate, LM, lexicon and arm choice were tuned on track-val prompts (as P11-17 limit (a)).
- (d) Arm S draws share the same 1,224 prompts: their spread shows split variation only (as P11-18 limit (c)).
- (e) The K = 80 Fisher test keeps the P11-17 bootstrap count at 9 / 40 (no new bootstrap draws).
