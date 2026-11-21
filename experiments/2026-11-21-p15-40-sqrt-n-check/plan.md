---
title: P15-40 Check the 1/sqrt(n) assumption of the P15-37 calibration-size projection - pre-registration
type: experiment
task: P15-40
updated: 2026-11-21
---

# P15-40: between-draw SD of the calibration-inclusive safe WPM at n = 361 / 481 / 722 (pre-registration)

Written and committed **before** any number of this item was computed. Gap 161 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P15-40](../../wiki/questions/roadmap-standard.md#p15-40-check-the-1n-assumption-of-the-calibration-size-projection). Follow-up of [P15-37](../2026-11-21-p15-37-multi-split/results.md). Base procedure: [P15-29](../2026-11-20-p15-29-calibration-ci/plan.md) (A0 settings).

## Problem
- P15-37 projected **n* ≈ 2,760** calibration items (exploratory, certified-only SD: about 1,580) from R120: mean 5.264, between-draw SD σ_b = 1.039, within-draw SD σ_w = 0.352, target σ_b* = 0.531.
- The projection assumes σ_b ∝ n^(-1/2) and that the mean and σ_w do not change with n. Both are unverified.
- Done when (gap 161): sub-sampling `val_select` (n = 361 / 481 / 722) reports the between-draw SD at each n, the fitted exponent and the revised n*.

## A design fact found while planning (stated before any result)
The P15-29 draw first cuts the 722 trials into parts (fit 180 / policy 271 / LTT 271) **without** replacement and then resamples each part **with** replacement. For a statistic that is a mean over one part of size m, the variance of the draw is about σ²/m × (2 − m/722): the "which trials are in the part" term (σ²/m × (1 − m/722)) plus the full resampling term (σ²/m). A fresh calibration set of size n, split at random by `calibrate`, has σ²/m only. So:
- at n = 722 the P15-29 draw can over-state the SD by up to √1.625 ≈ 1.27 (part-linear statistics; the real factor for the safe WPM is unknown);
- if the P15-29 draw is applied to a sub-sample of n distinct trials, the factor (2 − m/722) changes with n, and a statistic that truly follows n^(-1/2) shows an exponent of about **0.58** over n = 361 / 481 / 722 (log-log fit of √((2 − m/722)/m) at the LTT sizes m = 136 / 180 / 271), not 0.5.

For that reason this item runs two designs. D2 gives the clean test of the exponent; D1 is the literal sub-sampling of the gap and reuses the existing 722 draws.

## Designs

| design | draw of size n from the 722 `val_select` trials | 722 cell |
|---|---|---|
| **D2 (primary)** m-out-of-n bootstrap | draw n source trials **with** replacement (rng `default_rng(h8("p15-40\|d2\|boot\|<n>\|<k>"))`, `integers(0, 722, n)`); split the multiset into parts of sizes `_split(n)` by the grouped first-fit rule of P15-37 (`regroup`, key `"p15-40\|d2\|split\|<n>\|<k>"`; all copies of one source trial stay in one part, so the parts have disjoint source trials; up to 100 attempts) | new draws (K as below) |
| **D1 (secondary)** sub-sample + P15-29 draw | take the first n entries of the permutation `default_rng(h8("p15-40\|d1\|sub\|<n>\|<k>")).permutation(722)` (n **distinct** trials, without replacement); apply the P15-29 draw to them: split by the calibrate seed into `_split(n)` parts, resample with replacement inside each part (boot seed) | **reused**: R120 (P15-29 k01-k40 + P15-34 A0 k01-k40 + P15-37 A0 k01-k40); with n = 722 the D1 rule is exactly the P15-29 draw |

- h8(s) = the first 8 hex digits of SHA-256(s) as an integer (as P15-29 / P15-37).
- Calibrate seed s = h8(`"p15-40|<design>|cal|<n>|<k>"`); D1 boot seed b = h8(`"p15-40|d1|boot|<n>|<k>"`). The input order is set so that `calibrate(seed s)` sees exactly the planned parts (P15-29 `order_for`).
- Draws are **not nested**: every (design, n, k) cell uses its own seeds, so the SD estimates at different n are independent. This makes the bootstrap of the exponent simple (resample draws inside each cell).
- Sizes `_split(n)`: n = 361 → 90 / 135 / 136; n = 481 → 120 / 181 / 180; n = 722 → 180 / 271 / 271.

**Procedure per draw (A0 settings of P15-29 / P15-37 split 1):** one `fidetype.trust.calibrate` call at (α, δ) = (0.05, 0.1), pinned pipeline values (T 2.37015800035291, τ 0.06996627059278283, λ 1.0, fluent −7.88165954200173), `confidence="learned"`, commit gate, `stream_texts`, `null_max_commit_rate` 0.05; then `guard.decide` on the 701 `val_eval` trials and the `safe-wpm/0.1` score (P5-24 `score`).
- **One change from A0: `null_trials` = 20 (not 300)**, as the P15-37 splits 2-4. The controls only decide `refused`; in P15-37 none of the 164 split guards was refused (split 1 with 300 trials, splits 2-4 with 20) and no arm control exceeded 1 of 300. The split permutation is the first call of the calibrate random generator, before the controls, so the number of control trials does not change the split, the threshold or any decision on `val_eval` (check X1 below tests this). With 20 trials the allowed count is 1 per control. A refused draw earns 0.0 (credit rule).
- Credit rule (P15-29): only `certified` draws add their value; `refused`, `not-certified`, `above-alpha`, `vacuous` add 0.0. The "between-draw SD" of a cell is the SD (ddof 1) of its K draw values with these zeros (= `sd_between_draws` of `calibration_draw_interval`, the definition of the P15-37 projection). Within-draw SD and the cell interval: `calibration_draw_interval`, B = 2,000 trial resamples, `default_rng(0)`.

## K, order, time limit
- Target **K = 40** per cell. Cells: D2-361, D2-481, D2-722, D1-361, D1-481 (200 draws) plus 2 check draws (X1).
- Order (one worker): X1 first, then k-major: for k = 1..40: D2-361, D2-481, D2-722, D1-361, D1-481. So all cells grow together.
- Expected time per draw: about 1-3 min (one calibrate with cached decodes and 40 new control decodes, then 701 cached decisions). Expected total: 4-8 hours.
- **Time limit:** the worker starts no new draw after launch + 9 h (written to the log). Then each design uses K_d = the smallest finished count over its new cells (the first K_d draws of every cell). A design with K_d < 20 is reported but not decided. With K = 40 the SD of one cell has a relative standard error of about 11 % (normal case; more with zero draws); with K = 20 about 16 %.
- No restart after a memory kill except to resume finished draws (each draw is one file; finished draws are skipped).

## Fit and uncertainty
- Per design: ordinary least squares of log σ_b(n) on log n over the three cells (unweighted). Fitted exponent **b = −slope**. Under 1/√n: b = 0.5 (D2); b ≈ 0.58 (D1, design effect above).
- Uncertainty: B_fit = 2,000 bootstrap replicates (`default_rng(40)`): inside each cell, resample its K draw values with replacement, recompute the three SDs and the slope. 95 % percentile interval of b. Cell SDs equal to 0 in a replicate: that replicate is dropped and the count reported.
- Also reported (exploratory): the same fit with the certified-only SD; per cell the mean, σ_w, the statuses (zero draws), mean commits and wrong commits.

## Revised n*
Same target formula as P15-37: the needed between-draw SD is σ_b* = √(((μ − 4.0153) / 1.96)² − σ_w²), with μ and σ_w taken at n = 722 and kept fixed (the P15-37 assumption; the cells at 361 / 481 show whether it holds).
- **Primary (D2):** μ and σ_w from the D2-722 cell. n* = the n where the fitted D2 line reaches σ_b*: n* = exp((log σ_b* − a) / slope) (a = intercept). If slope ≥ 0 or no σ_b* > 0 exists, n* is "not reachable by size alone". 95 % interval: the same bootstrap (μ recomputed from the resampled D2-722 values, σ_w fixed).
- **Secondary (A, the direct revision of the P15-37 number):** P15-37's own σ_b = 1.039 and σ_b* = 0.531 (R120), with the measured D1 exponent: n*_A = 722 × (1.039 / 0.531)^(1 / b_D1). With b_D1 = 0.5 this is P15-37's 2,764.
- Also reported: n* from D2 anchored at its 722 cell, 722 × (σ_b,D2(722) / σ_b*)^(1 / b_D2); and the D2 and D1 values with b fixed at 0.5.
- The ratio σ_b,D1(722) / σ_b,D2(722) (R120 against D2-722) is reported as the measured size of the design effect.

## Code checks (must pass, else no result)
- **X1 (reuse of the 722 draws):** the D1 code at n = 722 with the P15-37 A0 seeds and boot seeds of k01 and k02 (and `null_trials` 20) must give the same `val_eval` decisions as the saved P15-37 A0 draws (701 / 701 action and text) and the same threshold. This shows that the D1 rule at 722 is the P15-29 draw and that `null_trials` does not change decisions.
- **C1:** every draw has disjoint source trials across its three parts and the sizes `_split(n)`; the sheet has n_ltt = `_split(n)[2]`, α 0.05, δ 0.1 and the pinned T.
- **C2:** the 701 truths of every draw equal those of the P15-37 z0 draw.
- **C3:** the cell SD from our own computation equals `sd_between_draws` of `calibration_draw_interval` (to 1e-9).

## Reading of the result (fixed now)
- "Consistent with 1/√n" if the 95 % interval of b_D2 contains 0.5. "Faster than 1/√n" if it is above 0.5; "slower" if below.
- D1: compared with 0.5 and with the design value 0.58 (descriptive).
- The revised n* is a rough estimate with stated assumptions, not a test. This item closes gap 161 when the SDs, b and n* are reported (done-when), whatever the values are.

## Expectation (stated before any result; not a rule)
- The zero draws (above-alpha, not-certified) can become more frequent at small n (LTT with 136 items is more conservative), and they inflate the all-draw SD; so b can come out above 0.5 for that reason too.
- The mean probably falls at small n (fewer LTT items give a higher threshold), so "mean fixed" is likely optimistic for n < 722 and neutral or slightly pessimistic for n > 722.
- We expect b_D1 near 0.5-0.6, b_D2 near 0.5, and σ_b,D2(722) smaller than R120's 1.039; if so, the primary n* is smaller than 2,760.

## Order, limits, outputs
1. Commit this plan (and push). Then commit `run.py` and `launch.py`; smoke run on calibration subsets only (`P1540_SMOKE=1`, it never loads `val_eval`).
2. Main run detached from a `git archive` snapshot of the committed code (other agents change `src/`), in `C:\Users\zhang\bci-data\derived\p15-40\snapshot\`: one worker, `python -m fidetype.utils.isolation run --class background --threads 2 -- python -I run.py worker`, then `run.py analyse`. **CPU only, no GPU**, keep-awake, log, `DONE` file `C:\Users\zhang\bci-data\derived\p15-40\DONE`, stop file `...\p15-40\STOP` (the worker stops after its current draw). Peak memory about 3 GB (P15-37: 2.8 GB per worker).
3. Derived data (per-trial decisions with text, caches) only in `C:\Users\zhang\bci-data\derived\p15-40\`. Read only: `derived/p15-22/`, `derived/p15-26/` (caches), `derived/p15-37/t15/draw-k01.json` and `draw-k02.json` (X1). R120 draw values come from the committed P15-37 `results/results.json`.
4. The repo gets `results/results.json` (aggregates, no text) and `results/run.log`.
5. No change of the designs, seeds, K rule, fit, n* formula or reading after this commit. Any later variant is a new item.

Known limits (stated before any result): (a) pinned pipeline values; (b) one participant, one decoder checkpoint, the same 701 evaluation trials in every draw; (c) a bootstrap from 722 trials cannot show the behaviour above n = 722, so n* > 722 is an extrapolation of a three-point line; (d) duplicates inside a part (both designs) make a single draw's certificate not valid; the draws show sampling variation only; (e) the grouped first-fit rule of D2 puts trials with many copies a little more often into later parts (no label is used); (f) `null_trials` 20 instead of 300 (decisions unchanged by X1; refusal chance slightly different).

## Addendum (2026-11-21, before the main run and before any `val_eval` number): K for D2 and the time limit
A synthetic check of the fit code (normal draw values with a true exponent 0.5, K = 40 per cell) gave a 95 % bootstrap interval of b of about [−0.10, 0.78]: with only a factor 2 in n (361 to 722), K = 40 per cell estimates the exponent poorly. Rough rule: the standard error of b is about 1 / √(2 (K − 1) × 0.2425), so ±0.45 (95 %) at K = 40 and ±0.28 at K = 100. To use the CPU budget for the primary design, the following changes are made now (no draw on `val_eval` has run):
- **K target: D2 cells 100 each, D1 cells 40 each** (D1 is secondary; its 722 cell already has K = 120).
- Order: for k = 1..100: D2-361, D2-481, D2-722, then D1-361, D1-481 only while k ≤ 40. X1 first, as before.
- **Time limit: launch + 8 h** (was 9 h), kept in `derived/p15-40/deadline.txt` so a resume keeps it. The rule for K_d (the smallest finished count over the new cells of a design) and the minimum K_d = 20 do not change.
- Expected: the smoke run (calibration subsets of 200 trials, 40 evaluation trials) took 40-60 s per draw. At full size about 1-2 min per draw: all 200 draws of k ≤ 40, then D2 to about k = 60-100 in the rest of the 8 h. The reached K and the resulting precision of b are reported. If K_d(D2) < 100, the interval of b is wider than ±0.28.
- Smoke only: K target 3 (D2) and 2 (D1).
