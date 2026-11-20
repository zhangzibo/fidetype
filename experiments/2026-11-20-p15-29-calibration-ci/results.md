---
title: P15-29 Safe WPM interval that includes the calibration draw - results
type: experiment
task: P15-29
updated: 2026-11-20
---

# P15-29: a safe-WPM interval that includes the calibration draw (results)

Pre-registration: [plan.md](plan.md), commit `d7169cf`. It was committed and pushed before any number was computed. Code: [`run.py`](run.py) and [`launch.py`](launch.py). The library function `fidetype.benchmark.safe_wpm.calibration_draw_interval` and its tests are in commit `8180a30` (smoke run on calibration subsets only; full pytest 1654 passed, 11 skipped). Aggregates (no text): [`results/results.json`](results/results.json). Log: [`results/run.log`](results/run.log). Per-trial decisions (with text) are local only, in `C:\Users\zhang\bci-data\derived\p15-29\`.

Run details:
- Time: 2026-11-19 20:16 to 2026-11-20 02:56, detached.
- Resources: two worker processes, background class, 4 threads each, **CPU only**. Peak private memory 3.96 GB per worker.
- Code: the run used a `git archive` snapshot of `8180a30`, because another agent had uncommitted changes in `src/fidetype/trust/dropin.py`.
- Draws: all 40 T15 draws and all 20 T12 draws finished before the 06:00 cutoff. So K = K_max on both units. No draw was refused.

## Verdicts (pre-registered rules)

| unit | combined safe WPM v0.1 [95 % interval], calibration + trials | no-BCI | verdict |
|---|---|---|---|
| **T15** (primary), K = 40 | **5.18 [0.00, 6.99]** | 4.0153 | **above, but inside the combined interval**: the mean (5.18) is above 4.0153; the lower end (0.00) is **not** above it |
| T12 (secondary), K = 20 | 1.05 [0.00, 3.18] | 4.1140 | **not above** |

**Headline (fixed by the plan for this outcome):** the README must stop saying that the T15 interval is "clearly above" gaze typing, or that its lower end is above 4.02. Once the calibration draw is included, the T15 interval contains 4.02. The point value (5.18) stays above 4.02.

### Why the T15 lower end is 0.00
- 2 of the 40 T15 draws (k30, k38) are `above-alpha`. Their wrong-commit rate on `val_eval` is 0.0556 (39 / 701) and 0.0514 (36 / 701), both above alpha 0.05. By the pre-registered credit rule, such a draw earns 0.0. So 5 % of the pooled values are 0.0, and the 2.5th percentile is 0.0.
- These two draws commit the most (295 and 296 commits) and have the highest raw values (6.60, 6.88). They are the draws where the guard committed too much.
- The other 38 draws are `certified`. Their values have mean 5.45, SD 0.79 and range 3.50-6.82. Two certified draws are below 4.02 (k14 3.50, k35 3.87). 36 of the 40 draws are above 4.02.
- This fits the LTT guarantee: it allows a population wrong-commit rate above alpha in up to delta = 10 % of calibration draws. We observed 2 / 40 above alpha on the test set.

### Exploratory variants (NOT pre-registered; they show that the verdict does not depend on the credit rule)

| T15 variant | value [95 %] | lower end > 4.0153? |
|---|---|---|
| pre-registered (above-alpha draws earn 0.0) | 5.18 [0.00, 6.99] | no |
| above-alpha draws keep their value | 5.52 [3.61, 7.11] | no |
| certified draws only (K = 38) | 5.45 [3.60, 7.01] | no |

So in every variant, the lower end of the interval is about 3.6 or lower once calibration-sample variation is included.

## Cross-checks

| check | result |
|---|---|
| **X4 code check (must pass)** | **passes.** T15 z0 = the P15-22 decisions on 701 / 701 trials (4.91; 196 commits, 13 wrong); the library with K = 1 gives [4.25, 5.57] = the P15-22 CI. T12 z0 = the P15-26 L1 decisions on 400 / 400 trials (2.37 [1.34, 3.62]). |
| **X1 analytic (law of total variance)** | T15: between-draw SD 1.43 (0.79 without the two 0.0 draws), within-draw SD 0.35, normal interval [2.30, 8.06]. T12: SD 1.10 / 0.38, [−1.23, 3.33]. Between-draw variation is now **larger** than the trial-bootstrap variation (ratio 4.1 on T15). Without the two zeros it is 2.3 times larger. |
| **X2 P15-26 full-refit draws** (c0-c3, partition only, T / τ / λ refitted) | 5.43 [4.46, 6.50]; the lower end is above 4.0153. This uses K = 4 draws and changes only the fit / certify split, not the calibration sample. So it captures much less variation than the primary method. |
| **X3 pinned vs refitted pipeline values** (seeds 1-3, no resampling) | z1 5.46 vs c1 5.58 (−0.12); z2 5.85 vs c2 6.00 (−0.15); z3 5.26 vs c3 5.23 (+0.03). Pinning T, τ, λ changes the value by at most 0.15. This is small against the between-draw SD (0.79). |

## Details

### T15 draws (k01-k40; v0.1 value, commits / wrong, commit threshold)
- Values: 6.26, 6.23, 6.82, 5.60, 5.95, 5.41, 6.77, 5.68, 5.38, 5.47, 5.49, 6.30, 5.56, 3.50, 4.04, 4.32, 5.80, 5.49, 5.08, 5.24, 6.54, 5.41, 5.45, 6.34, 6.50, 4.72, 5.88, 5.75, 5.75, (6.60 above-alpha → 0.0), 4.82, 4.67, 5.46, 5.02, 3.87, 5.80, 4.75, (6.88 above-alpha → 0.0), 4.27, 5.76.
- Mean commits 222 (133-296), mean wrong commits 18.3. Commit thresholds 0.43-0.90. The value follows the threshold: a low threshold gives many commits and a high value, but the safety margin is small.
- Null controls: at most 1 of 300 commits per control (allowed 15) in every T15 draw (T12: at most 4 of 300).
- Each T15 draw took 12-32 min (T12 8-12 min). The null-control decodes are new in each draw; the real-trial decodes all came from the cache.

### T12 draws (k01-k20)
- 10 certified (1.68-2.72, mean 2.10), 6 `above-alpha` (wrong-commit 0.0525-0.0725), 4 `vacuous` (no certified threshold, 0 commits).
- On T12 the calibration is unstable. Half of the draws do not give a certified, safe guard. No draw is above 4.11.

## Hypotheses and expectations, answered honestly
- **Primary question: is the T15 lower end above 4.02 once the calibration draw is included? No.** It is 0.00 under the pre-registered rule and about 3.6 under both exploratory rules.
- **Is the T15 point value above 4.02? Yes.** The mean is 5.18 (median 5.48), and 36 of 40 draws are above 4.02.
- **T12 expectation (below 4.11): confirmed.** 1.05 [0.00, 3.18].
- **Stated during the run, not pre-registered:** at k19 I suspected that the bootstrap draws were biased upward (they averaged about 5.6, against about 5.4 for the draws without resampling). With all 40 draws this is **not** supported: the certified mean is 5.45 and the X2 mean is 5.43. The resampled draws spread more widely (SD 0.79 against 0.44). Part of this spread can come from duplicates in the resampled LTT part (limit (b) of the plan).
- **The P15-26 statement "stable over calibration draws"** held only for the split variation (c0-c3). With calibration-sample variation, the T15 value ranges from 3.50 to 6.88, and 2 of 40 draws fail safety on the test set.

## Notes and limits
- Pipeline values pinned (limit (a)): X3 shows that this effect is at most 0.15.
- Duplicates in the resampled LTT part (limit (b)): a single resampled draw does not give a valid certificate. The draws show only the sampling variation. They may over-state it a little.
- One participant per unit, one decoder checkpoint, and the same evaluation set in every draw.
- The library function is a **proposed** reporting addition ([docs section 6b](../../docs/safe-wpm.md#6b-proposed-reporting-addition-an-interval-over-calibration-draws-proposed-not-adopted)). It changes no `safe-wpm/0.1` rule or number. The user decides adoption.

> **Our take:** the T15 result is above gaze typing on average, but not with the margin the conditional CI showed. When the calibration sample is redrawn, about 1 in 10 guards is at or below the no-BCI reference: two draws give low values, and two are unsafe on the test set. The honest headline is "5.2 safe WPM on average, interval 0.0-7.0 including the calibration draw; above gaze typing on average, not reliably above". The cause is the size of the calibration set (271 LTT items). A larger calibration set, or a guard with a safety margin (for example a lower target alpha), should narrow the interval. Neither is tested here.
