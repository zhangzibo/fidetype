---
title: P15-34 Calibration-inclusive T15 safe WPM with a safety-margin guard - pre-registration
type: experiment
task: P15-34
updated: 2026-11-20
---

# P15-34: a guard with a safety margin, interval over calibration draws (pre-registration)

Written and committed **before** any number of this item was computed. Gap 132 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P15-34](../../wiki/questions/roadmap-standard.md#p15-34-calibration-inclusive-t15-safe-wpm-lower-end-above-gaze-typing). Follow-up of [P15-29](../2026-11-20-p15-29-calibration-ci/plan.md) ([results](../2026-11-20-p15-29-calibration-ci/results.md)).

## Problem
P15-29 gives the T15 L1 safe WPM v0.1 with calibration draws (K = 40) as **5.18 [0.00, 6.99]**. Two draws are `above-alpha` on `val_eval` (wrong-commit 0.0556 and 0.0514) and earn 0.0. The 38 certified draws range from 3.50 to 6.82. So the lower end is not above the no-BCI reference 4.0153.

## Goal
Find out if a T15 guard exists whose calibration-inclusive lower end is above 4.0153, with the same credit rule and the same draw procedure as P15-29.

## Levers
| lever | used? | reason |
|---|---|---|
| (1) larger calibration set | **no** | T15 has labelled trials only in `train` (the decoder was trained on them, so its outputs there are not exchangeable with new data), `val_select` (722, the calibration set) and `val_eval` (701, the evaluation set). The competition test split has no labels. A larger calibration set needs `val_eval` trials, and the rules forbid that. |
| (2) a guard with a safety margin | **yes** | a lower target alpha' for the LTT step (alpha' < 0.05), a smaller delta' (delta' < 0.1), or both |

How a margin arm is calibrated: `fidetype.trust.calibrate(..., alpha=alpha', delta=delta', null_max_commit_rate=0.05)`. All other settings are as in P15-29 (learned commit score, commit gate, `null_trials` 300, pinned pipeline values, `stream_texts`). `null_max_commit_rate=0.05` keeps the null controls the same as in P15-29 (allowed 15 of 300).

**Guarantee used for scoring (primary, "claimed").** LTT at (alpha', delta') certifies P(R <= alpha') >= 1 - delta'. Because alpha' <= 0.05, this implies P(R <= 0.05) >= 1 - delta'. So the score uses the guarantee of the sheet with alpha set to **0.05** (and delta = delta'). The credit rule is then the P15-29 rule: a draw earns its value only if its `safe-wpm/0.1` status is `certified` (measured wrong-commit rate <= 0.05, at least one commit, feasible). **Secondary ("strict"):** the same draws scored with the sheet alpha (alpha'), so a draw is `above-alpha` if its rate is above alpha'. Both are reported.

## Stage S: lever selection on calibration data only
Stage S never loads, decodes or scores a `val_eval` trial (the loader returns the evaluation split; the code deletes it at once and uses no part of it).

1. For each seed s in {0, 1, 2, 3}: run `calibrate` on `val_select` (722, no resampling) with seed s, alpha 0.05, delta 0.1, pinned values, `null_trials` 20 (the controls do not enter stage S).
2. Take the 271 LTT items of that seed (they are not used to fit the learned score). For each item compute, exactly as `_fit_commit_score` does: the learned score s_i (minus infinity if the commit gate blocks it), the loss l_i (top-1 text != truth), the words and characters of the truth, and the measured trial duration. **Check:** `ltt_threshold(s, l, 0.05, 0.1)` must equal the threshold of the guard. If not, stage S stops.
3. Bootstrap world: the population P_s is these 271 items. For each arm (alpha', delta') of the grid, R = 500 outer draws: resample 271 items of P_s with replacement (rng `default_rng` of the first 8 hex digits of SHA-256(`"p15-34|sel|<s>|<r>"`)), compute the threshold with `ltt_threshold(alpha', delta', binomial, default grid)`, then on P_s: commit = (s_i >= threshold), wrong-commit rate r = mean(commit and l_i). The draw value is the `safe-wpm/0.1` formula on P_s if r <= 0.05 and at least one commit, else 0.0. Inner level: B = 200 multinomial resamples of size 701 from P_s (rng `default_rng(1)`), the same for every draw and arm.
4. Grid: alpha' in {0.05, 0.045, 0.04, 0.035, 0.03, 0.025, 0.02}, delta' in {0.1, 0.05, 0.025, 0.01} (28 arms).
5. Predicted lower end of an arm = the 2.5th percentile of the pooled 4 x R x B values. Predicted mean and the failure fraction (r > 0.05) are also reported.

**Arm rule (fixed now):**
- **A1 (primary)** = the arm with the highest predicted lower end. Ties (difference < 0.01): the larger alpha', then the larger delta'.
- **A0 (reference)** = (0.05, 0.1), the P15-29 settings, on the new draws. It shows the trade-off and replicates P15-29.
- **A2** = the best arm with delta' = 0.1 and alpha' < 0.05 (alpha margin only). **A3** = the best arm with alpha' = 0.05 and delta' < 0.1 (delta margin only). If A1 equals A2 or A3, that slot takes the next arm of the full ranking that is not chosen yet.
- Stage S writes `results/selection.json`. A short addendum to this plan names the four arms. Both are committed **before** the main run starts.

Known limit of stage S: it leaves out the variation of the learned-score fit and uses the alpha 0.05 score for every arm (the real alpha' arms refit the pipeline with alpha'). It ranks arms; it does not predict the main result.

## Main run: two-level bootstrap (same procedure as P15-29)
- Evaluation set fixed: T15 `val_eval` (701). Calibration set: `val_select` (722).
- **New draws** k = 1 ... 40: calibrate seed = the first 8 hex digits of SHA-256(`"p15-34|t15|cal|<k>"`), bootstrap seed = SHA-256(`"p15-34|t15|boot|<k>"`). New seeds, so the draws are not the P15-29 draws whose test outcomes we know.
- Per draw: the P15-29 `draw_order` (split by `_split`, resample with replacement inside each part, input order so that `calibrate` sees these parts), pinned values (T 2.37015800035291, tau 0.06996627059278283, lambda 1.0, fluent -7.88165954200173), then all four arms on the same sample, in the order A0, A1, A2, A3 (paired design).
- Inner level: the same B = 2,000 trial resamples (`default_rng(0)`), as P15-29.
- **Credit rule:** as P15-29 (only `certified` draws add their values; refused, `not-certified`, `above-alpha`, `vacuous` add 0.0). Interval: the 2.5th and 97.5th percentiles of the pooled K x B values; point: the mean of the K draw values (`fidetype.benchmark.safe_wpm.calibration_draw_interval`).
- K = 40 for every arm. No cutoff: the run goes on until all 40 draws of all arms are done. If the job is killed for low memory, it is not restarted; the analysis then uses no arm with fewer than 40 draws.

## X4 code check (must pass)
Draw z0 = seed 0, no resampling, arm A0. It must reproduce the P15-22 L1 decisions on T15 (701 / 701 same action and text; safe WPM 4.91) and the library with K = 1 must give [4.25, 5.57]. Its commit threshold, commits and wrong commits must equal those of the P15-29 z0 (threshold 0.82, 196 commits, 13 wrong; P15-29 `results/run.log`). A failed check stops the analysis (no result).

## Decision rule
Reference: the no-BCI WPM of `val_eval`, **4.0153**.

| outcome for **A1** (primary, claimed guarantee) | verdict | gap 132 |
|---|---|---|
| pooled 2.5th percentile > 4.0153 | **clearly above after calibration uncertainty** | closed |
| mean > 4.0153 >= 2.5th percentile | above, but inside the combined interval | stays open |
| mean <= 4.0153 | not above | stays open |

**Several arms.** Only A1 can close gap 132. A2 and A3 are secondary: Bonferroni over m = 2, so a secondary arm is called "above" only if its pooled **1.25th** percentile is above 4.0153; this is descriptive and does not close the gap. A0 is the reference (no test). The strict-guarantee scores are descriptive.

Also reported per arm: statuses (certified / above-alpha / vacuous / not-certified / refused), the draw values (mean, median, SD, range), the fraction of draws above 4.0153, mean commits and wrong commits, the X1 law-of-total-variance decomposition, and per draw the paired difference to A0 (how many A0 `above-alpha` draws become `certified`, how much value a certified draw loses).

## Expectation (stated before any result; not a rule)
In P15-29 the 38 certified draws alone give [3.60, 7.01]. A margin lowers the number of commits, so it moves the draw values down. It removes the zero draws, but it probably does not narrow the spread. So we expect that A1 does **not** reach the criterion. In that case results.md says why, with numbers (the "or the numbers say why" branch of the roadmap item).

## Order, limits, outputs
1. Commit this plan, `run.py` and `launch.py`. Smoke run on calibration subsets only (`P1534_SMOKE=1`; it never reads `val_eval`).
2. Stage S (calibration only), then commit `results/selection.json` and the plan addendum.
3. Main run detached: `launch.py` starts two workers (`python -m fidetype.utils.isolation run --class background --threads 4 -- python -I run.py worker <w>`), CPU only, keep-awake, log, `DONE` file, stop file `C:\Users\zhang\bci-data\derived\p15-34\STOP` (a worker stops after its current draw). Worker 0 takes z0 and the odd k. Worker 1 takes the even k. Resumable: each finished (draw, arm) is saved and skipped later.
4. Derived data only in `C:\Users\zhang\bci-data\derived\p15-34\`. Read only: `derived/p15-22/`, `derived/p15-26/` (caches, P15-22 decisions), as P15-29 did. No P15-29 derived file is read; P15-29 code is copied into this folder (P15-29's folder is not changed).
5. The repo gets `results/selection.json`, `results/results.json` (aggregates, no text) and `results/run.log`. Peak RSS per worker is logged.
6. No change of the method, the arm rule, K, the reference or the decision rule after this commit. Any later variant is a new item.

Known limits (stated before any result): the P15-29 limits (a) pinned pipeline values, (b) duplicates in a resampled LTT part, (c) one participant and one decoder checkpoint, (d) the same evaluation set in every draw; and (e) the claimed guarantee of a margin arm is the weaker statement at alpha 0.05 that the stronger alpha' certificate implies.

## Addendum (2026-11-20 05:20): stage S result and the four arms (before the main run)
Stage S ran on `val_select` only (4 seeds, R = 500, B = 200; [results/selection.json](results/selection.json)). The check passed for all 4 seeds (recomputed LTT threshold = guard threshold: 0.82, 0.75, 0.69, 0.75). Arms by the rule above:

| arm | alpha' | delta' | predicted mean [2.5 %, 97.5 %] (bootstrap world) | predicted failure fraction |
|---|---|---|---|---|
| A0 reference | 0.05 | 0.1 | 5.07 [0.00, 7.00] | 0.055 |
| **A1 primary** | 0.05 | 0.025 | 4.86 [2.69, 6.78] | 0.013 |
| A2 alpha margin | 0.04 | 0.1 | 4.86 [2.69, 6.78] | 0.013 |
| A3 delta margin | 0.05 | 0.01 | 4.63 [2.67, 6.63] | 0.004 |

A1 ties with (0.045, 0.05) and (0.04, 0.1) (same thresholds in the bootstrap world); the tie rule picks the larger alpha'. A3 is (0.05, 0.01) because (0.05, 0.05) has a predicted lower end of 0.00. **No arm of the grid has a predicted lower end above 4.0153** (best 2.69). The main run goes on as pre-registered. Nothing else changes.
