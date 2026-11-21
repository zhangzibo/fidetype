---
title: P11-23 Robustness of the EMG shift margin across session steps - pre-registration
type: experiment
task: P11-23
updated: 2026-11-21
---

# P11-23: robustness of the EMG shift margin across session steps (pre-registration)

Written and committed **before** any number of this item was computed. Gap 170 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-23](../../wiki/questions/roadmap-standard.md#p11-23-robustness-of-the-emg-shift-margin-across-session-steps). Source: [P11-20](../2026-11-21-p11-20-emg-shift-robust/plan.md) ([results](../2026-11-21-p11-20-emg-shift-robust/results.md)). Bases: [P11-18](../2026-11-21-p11-18-emg-above-alpha/plan.md), [P11-17](../2026-11-21-p11-17-emg-calibration-ci/plan.md), [P11-14](../2026-11-20-p11-14-emg-lm-confidence/plan.md) arm L-FL.

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates and per-draw counts only: no per-user value, no text, no prompt id, no signal, no weights. Per-user step sizes are reported only as unlabelled spread statistics (quantiles, SD). Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt and per-user files stay in `C:\Users\zhang\bci-data\derived\p11-23\`. The P11-01, P11-09, P11-11, P11-14, P11-17, P11-18 and P11-20 files are read only.

CPU only, **no GPU**. At most 2 threads in total: 2 workers x 1 thread, isolation class `background`. No new inference (the session a / b log-probs of P11-20 are reused, read only).

## Problem
P11-20 estimated the shift margin m = 0.0045 from one session step per user: calibrate on session a, evaluate on session b (40 partition-only draws, mean gap). The descriptive two-step gap a -> track val was -0.0044. So the step size changes between sessions, and one step can under-state or over-state the shift. Gap 170 asks for m from several session steps per user, the spread of the step sizes, and a re-check of arm S with a margin rule that covers that spread.

## Which sessions exist and which ones the models saw (checked before this plan)
P11-01 `prep.py make_splits` and `train.py`: per test user, sessions in date order are `train` = all but the last 4, `val` = the 2 before the last 2, `test` = the last 2. Train-session counts of the 8 users: 8, 7, 8, 8, 14, 6, 8, 8 (67 in total).
- **All** train sessions were used to fine-tune the personal model (`train_stage(..., ps["train"], ps["val"])`). No train session is unused.
- The 2 `val` sessions (**a** = earlier, **b** = later) selected the personal checkpoint (`best.pt`). They were also part of `generic_val`, which selected the generic checkpoint. They were never gradient-trained on.
- The 2 `test` sessions are track val (calibration) and track test (evaluation).

Session order per user: train ... < **a** < **b** < track val < track test.

**How training sessions are handled: they are excluded from the margin.** On a session that the decoder was fine-tuned on, the decoder is in-sample, so the guard's risk there is lower than on new data. A step train -> train compares two in-sample risks (shift under-stated, optimistic). A step train -> a or b compares an in-sample risk with a new-data risk (shift over-stated by the training effect). A step a or b -> train has the opposite sign. The size of this training effect is not known, and it cannot be separated from the session shift without held-out data. So no train session enters this item (also no inference of train sessions; this saves about 1 to 4 h of CPU).

So the session steps available without training sessions and without track data are, per user: **a -> b** (forward, distance 1) and **b -> a** (backward, distance 1). The guard is pooled over the 8 users, so each step direction is one pooled step with 8 user parts. This item gets several step-size estimates from these two directions and from the user parts (leave-one-user-out).

## Why the guarantee still holds (stated before any result)
Let g be the guard that LTT outputs from the track-val calibration prompts, R_val(g) its risk on the track-val session population and R_test(g) its risk on the track-test session population.
1. The margin m is a function of sessions a and b only (and of the pinned decoder, LM, lexicon and guard code). The draws that give m fit, calibrate and evaluate on session-a and session-b prompts only; the automatic calibrate null controls are built from the calibration session windows (`null_inputs=None`). Leave-one-user-out values reuse the same draws. So m reads **no prompt and no window of track val or track test**, and it is fixed before, and independent of, the track-val LTT data. The track-test data are not touched until arm S2 is decided. (The B draws also count their wrong commits on track val, as P11-20 did for a -> track val. This number is descriptive only and enters no rule.)
2. Given m, alpha'' = alpha - m is a fixed level for the arm S2 calibration. LTT at alpha'' keeps its exact guarantee on the calibration population: P(R_val(g) > alpha'') <= delta = 0.1 over the calibration draw.
3. **Assumption (A2), bounded shift:** R_test(g) <= R_val(g) + m, where m is an upper bound of the one-session-step shift over both step directions and over the user-composition spread. Under (A2), P(R_test(g) > alpha) <= P(R_val(g) > alpha'') <= delta.
4. (A2) is an assumption, not a distribution-free fact. The track-test results of arm S2 are an honest check of (A2): no test number was used to choose m, alpha'' or any rule. The P11-18 test gap (+0.0126) and the P11-20 arm S test results are **not** used.

Training sessions would break point 1 only in a weak way (they are not track data), but they would bias m (section above). That is why they are excluded, not because of the guarantee.

## Fixed parts (as P11-14 / P11-17 / P11-18 / P11-20, unchanged)
Data, windows (prompt frames + 20 tail frames), target, decoder FL, the no-signal gate, the OOV gate, the competitor set and the 10 signals; arm L-FL with the P11-14 model-fit rule (`Learned.fit`); `calibrate` settings (delta 0.1, LTT, `confidence="p_top1"`, `input_kind="logits"`, key-CTC vocabulary, `audit_text=False`); safe WPM v0.1 with the default correction rule; no-BCI reference 3.09; the P11-17 credit rule. Session a / b prompts and log-probs: the P11-20 files `derived\p11-20\prompts-ab.json` and `derived\p11-20\lp\u<i>-{a,b}-real.npy` (read only; P11-20 checks C1 and C2 passed on them). Pinned: decoder weights, gate thresholds, LM, lexicon, arm choice.

## Stage 1: step draws (sessions a and b only)
Two step directions d, each with J = 40 partition-only draws, exactly the P11-20 stage-1 procedure (P11-17 `draw_order(n, s, None)` with `_split(n)` sizes; L model refit on fit + policy; `calibrate` at alpha = 0.05, delta = 0.1, `null_inputs=None`):
- **A01-A40, d = a -> b**: calibrate on session a, evaluate on session b. Seeds seed_of(`"p11-20|emg|m|<j>"`), the same as P11-20 M01-M40. These are reruns of the P11-20 M draws; this item adds per-user counts.
- **B01-B40, d = b -> a**: calibrate on session b, evaluate on session a. Seeds seed_of(`"p11-23|emg|ba|<j>"`).

seed_of(tag) = first 8 hex digits of SHA-256(tag), as an integer.

For each draw with a guard, record pooled and per-user counts (per-user counts local only): LTT part of the calibration session (n, wrong commits of the deployed guard, same `same()` rule) and the whole evaluation session (n, commits, wrong commits). Descriptive only (B draws): wrong commits on all track-val prompts (two-step b -> track val).

**Code check X6 (must pass):** A01-A40 reproduce P11-20 M01-M40 (`derived\p11-20\draw-M<j>.json`): same status, threshold, LTT wrong count, commits and wrong count on session b, in 40 / 40 draws. If X6 fails, no margin and no arm S2 result are reported.

## Step sizes and the margin rule
For draw j of direction d, with L = LTT prompts of the calibration session and Y = the evaluation session:
- pooled gap g_{d,j} = wrong_Y / n_Y - wrong_L / n_L (as P11-20);
- leave-one-user-out gap g_{d,j}^{(-u)}: the same formula on the prompts of the other 7 users only (same guard).

Step-size estimates (means over the draws of d that produced a guard):
- s_d = mean_j g_{d,j} (2 values: a -> b, b -> a);
- s_{d,-u} = mean_j g_{d,j}^{(-u)} (16 values: 2 directions x 8 left-out users);
- per-user step sizes p_{d,u} = mean_j (wrong_{Y,u} / n_{Y,u} - wrong_{L,u} / n_{L,u}) (16 values; descriptive only, as unlabelled spread statistics; one user's step is not the pooled step of the guard).

User-composition spread of a direction: jackknife SE_d = sqrt((n - 1) / n x sum_u (s_{d,-u} - mean_u s_{d,-u})^2), n = 8.

**Primary margin rule (covers the spread):** U_d = s_d + t x SE_d with t = t_{0.95, 7} = 1.8946 (one-sided 95 % upper bound of the pooled step over users). **m2 = max(0, max_d U_d)** (the larger of the two directions). alpha'' = floor((0.05 - m2) x 10^4) / 10^4.

Why this rule: the per-draw spread of g is mainly calibration-split noise, which the LTT delta already covers, so it is not used for m2. The systematic parts are the direction (the sign and size of the session difference) and the user composition (each user's shift differs). The rule takes the worse direction and an upper bound over users.

- If fewer than 30 of 40 draws of a direction produce a guard, or m2 >= 0.05, arm S2 is not run and the item reports why.
- If alpha'' = 0.0455 (the P11-20 alpha'), arm S2 equals P11-20 arm S by construction (same seeds, same partitions, same level). Then only S01 is rerun as an identity check, and the arm S2 numbers are the P11-20 arm S numbers.

**Descriptive only (no rule, no arm run):** the max of the 18 values {s_d, s_{d,-u}}; mean, SD, quantiles (0.1, 0.5, 0.9) and range of g_{d,j} per direction and pooled over both directions; spread (min, quantiles 0.25 / 0.5 / 0.75, max, SD) of p_{d,u}; the difference s_{a->b} - s_{b->a}; the two-step gap b -> track val; the P11-20 m = 0.0045 for comparison.

**Spread verdict (fixed here):**

| alpha'' | conclusion |
|---|---|
| >= 0.0455 | **the one-step margin of P11-20 covers the spread** |
| < 0.0455 | **the one-step margin of P11-20 under-states the spread** |

## Arm S2 (primary): track val -> track test at alpha'', K = 40 partition-only draws
For k = 1 ... 40: exactly the P11-20 arm S draw k (= P11-18 arm P draw k: seed seed_of(`"p11-18|emg|cal|<k>"`), permutation of the 1,224 track-val prompts, `_split` = 306 / 459 / 459, no resampling, L model refit on fit + policy, 300 input-level time-shuffled null inputs of the P11-18 pick), with **one change: `calibrate(alpha=alpha'')`**. Decide all 1,221 test prompts: real, time-shuffled, zero EMG.

Scoring: the claim is alpha = 0.05 (the margin is part of the method). Safe WPM uses the sheet guarantee with `alpha` = 0.05 (`ltt_alpha` = alpha'' and m2 recorded beside it). A draw is **above alpha** if test wrong commits / 1,221 > 0.05 (>= 62 wrong). Credit: the P11-17 rule.

## Metrics
- Stage 1: X6; per direction: draws with a guard, statuses, s_d, SE_d, U_d, g_{d,j} statistics, LTT and evaluation rates, commits, thresholds, null-control commits; m2, alpha''; the descriptive values above.
- Arm S2: above-alpha fraction f_S2 (vs 0.05); fraction above alpha'' (descriptive); significant exceedances (w >= 75); test rate, LTT in-sample rate and optimism gap mean / SD / range; commits, wrong commits, thresholds; statuses; control counts.
- Arm S2 vs P11-20 arm S and vs P11-18 arm P (paired by k): wrong count down / same / up; exact McNemar on above-alpha.
- Arm S2 calibration-inclusive interval: P11-17 primary procedure unchanged (40 draw values x the same B = 2,000 user-cluster weight vectors; non-credited draws earn 0.0; pooled 2.5 / 97.5 percentiles; point = mean); X1 decomposition; library `calibration_draw_interval` (secondary). Verdict vs 3.09 with the P11-17 rule.

## Decision rules (fixed here)

**Primary (arm S2):**

| f_S2 (of 40) | conclusion |
|---|---|
| 0 or 1 | **margin removes the excess** |
| 2 to 4 | **within delta, excess not removed** |
| >= 5 | **margin not enough** |

Interval verdict vs 3.09: the P11-17 rule ("clearly above after calibration uncertainty" / "above, but inside the combined interval" / "not above").

**Assumption check:** (A2) is "not contradicted on test" if the mean arm S2 test rate is <= 0.05 and f_S2 <= 4; else "(A2) fails on test".

Expectation (stated now, not a rule): s_{b->a} may be negative if b is a harder session than a (then the backward step lowers the risk), and m2 will then come mostly from the a -> b direction plus the user spread. m2 may be larger than 0.0045, so the guard may commit less and safe WPM may fall.

## Gap rule
**Gap 170 closes** when results.md reports, under this plan with X6 passed: the step sizes of both directions and their spread (direction, leave-one-user-out, per-user, per-draw); m2 and alpha''; f_S2 with K = 40 partition-only draws; and the arm S2 calibration-inclusive interval vs 3.09, whatever they are. If X6 fails or arm S2 cannot run (margin rule), results.md says why, and the gap stays open.

## What was done before this plan (disclosure)
Reading of the gap 170 entry, the roadmap row, the P11-20 plan / results / run.py / launch.py / test, the P11-01 `make_splits` rule and the personal training call, the P11-14 `Analyser` memo key, the helper names of the P11-17 / P11-18 runners. Counting of the train sessions per user from `splits.json`. Reading of the P11-20 derived file list, `infer.json`, `margin.json` and one margin draw file (to learn the fields). **Known before this plan:** the P11-20 a -> b numbers (40 draws: mean gap +0.0045, SD 0.0085, range -0.0112 to +0.0229; per-draw values in the P11-20 log; a -> track val -0.0044). **Not known:** any per-user count, any b -> a number, any leave-one-user-out value, m2, alpha'', any arm S2 number. No draw, guard or score of this item was computed before this commit.

## Order, limits, outputs
1. Commit this plan. Then commit `run.py` (imports the P11-20 / P11-18 / P11-17 / P11-14 runners for pure helpers only, read only; writes only to `derived\p11-23\`), `launch.py` and a test on synthetic data.
2. Run detached from a `git archive` snapshot of the committed code, with keep-awake: 2 workers x 1 thread for A01-A40 and B01-B40 (interleaved), then `margin` (with X6), then 2 workers for S01-S40, then `analyse`. Log `results/run.log`; `DONE` file `C:\Users\zhang\bci-data\derived\p11-23\DONE`. Each worker keeps its own window memo (`derived\p11-23\feat-w<w>.pkl`), started from the union of the P11-20 memos (read only; window-content keys, so the union is exact). Each finished draw is saved as `derived\p11-23\draw-<name>.json` and skipped on a rerun.
3. The repo gets `results/results.json` (aggregates, per-draw pooled counts, unlabelled spread statistics) and `results/run.log`.
4. No change of the directions, J, K, seeds, margin rule, metrics or decision rules after this commit. Any later variant is a new item.

Known limits (stated before any result):
- (a) Only two step directions exist without training or track sessions, both between the same two sessions (a, b). The backward step b -> a is not a real time step; it measures the size of the a / b difference with the other sign.
- (b) Sessions a and b selected the checkpoints of the personal and generic models, so the decoder is slightly in-sample on both (P11-20 limit a).
- (c) The leave-one-user-out values keep the guard fixed (calibrated on all 8 users); they measure user-composition spread of the step, not a held-out user.
- (d) (A2) is not testable on calibration data alone; track test is two steps further from b than b is from a.
- (e) Pinned decoder, gate, LM, lexicon and arm choice were tuned on track-val prompts (P11-17 limit a).
- (f) Arm S2 draws share the same 1,224 prompts: their spread is split variation only.
- (g) Expected run time with 2 workers: about 2 h for stage 1 and about 1.1 h for arm S2.
