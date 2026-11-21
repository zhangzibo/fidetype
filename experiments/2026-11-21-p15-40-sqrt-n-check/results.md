---
title: P15-40 Check the 1/sqrt(n) assumption of the P15-37 calibration-size projection - results
type: experiment
task: P15-40
updated: 2026-11-21
---

# P15-40: between-draw SD of the calibration-inclusive safe WPM at n = 361 / 481 / 722 (results)

Pre-registration: [plan.md](plan.md), commit `f83397a`, committed and pushed before any number existed. Code and plan addendum (D2 K target 100, D1 K target 40, time limit 8 h): commit `1d64217`, before the main run. Aggregates (no text): [`results/results.json`](results/results.json). Log: [`results/run.log`](results/run.log). Per-trial decisions (with text) are local only, in `C:\Users\zhang\bci-data\derived\p15-40\`.

Run details:
- Smoke (calibration subsets only): 2026-11-21 08:12-08:20.
- Main run: 2026-11-21 08:21-14:37, detached, from a `git archive` snapshot of `1d64217`. One worker, background class, **2 threads, CPU only, no GPU**. Peak 2.80 GB. 55-64 s per draw.
- All 382 draws finished: X1 (2) + D2 3 × 100 + D1 2 × 40. The time limit (16:21) was not reached. So K_d = 100 (D2) and 40 (D1), the full targets.
- No draw was refused. No control committed (maximum 0 of 20 in every draw).

## Code checks

| check | result |
|---|---|
| X1: D1 code at n = 722 with P15-37 A0 seeds k01 / k02, `null_trials` 20 | **passes**: 701 / 701 same action and text in both; thresholds 0.87 / 0.86 the same. The D1 rule at 722 is the P15-29 draw, and `null_trials` does not change decisions. So R120 is the D1 722 cell. |
| C1 parts disjoint, sizes `_split(n)`, sheet α / δ / n_ltt / pinned T | passes |
| C2 701 truths = P15-37 z0 | passes |
| C3 own cell SD = `sd_between_draws` | passes |

## Cells (safe WPM v0.1, calibration + trials)

| cell | K | mean [95 %] | between-draw SD (all draws) | certified-only SD | within-draw SD | statuses | draws > 4.0153 | mean commits / wrong | mean threshold |
|---|---|---|---|---|---|---|---|---|---|
| D2-361 | 100 | 4.64 [1.92, 6.58] | **1.234** | 1.050 | 0.334 | 98 certified, 2 above-alpha | 76 % | 188.6 / 13.3 | 0.781 |
| D2-481 | 100 | 4.70 [1.97, 6.54] | **1.089** | 1.089 | 0.335 | 100 certified | 80 % | 185.5 / 12.5 | 0.790 |
| D2-722 | 100 | 5.19 [3.06, 6.77] | **0.884** | 0.884 | 0.349 | 100 certified | 89 % | 207.2 / 15.5 | 0.744 |
| D1-361 | 40 | 4.18 [0.00, 6.87] | **1.788** | 1.374 | 0.317 | 37 certified, 2 above-alpha, 1 vacuous | 62.5 % | 182.6 / 13.9 | 0.786 |
| D1-481 | 40 | 4.73 [2.11, 6.61] | **1.141** | 1.141 | 0.337 | 40 certified | 75 % | 187.3 / 12.9 | 0.794 |
| D1-722 = R120 (P15-37) | 120 | 5.26 [2.94, 6.90] | **1.039** | 0.785 | 0.352 | 118 certified, 2 above-alpha | - | - | - |

## Fit (pre-registered: OLS of log SD on log n, bootstrap over draws, B = 2,000)

| design | fitted exponent b | 95 % bootstrap interval | reading (plan rule) |
|---|---|---|---|
| **D2 (primary)** | **0.483** | [0.124, 0.826] | **consistent with 1/√n** (0.5 is inside) |
| D1 (secondary) | 0.746 | [0.205, 1.363] | consistent with 1/√n; also consistent with the design value 0.58 |
| D2, certified-only SD (exploratory) | 0.265 | [−0.023, 0.556] | 0.5 is inside, near the upper end |
| D1, certified-only SD (exploratory) | 0.815 | [0.412, 1.162] | 0.5 is inside |

- The interval of b_D2 is wide (±0.35), a little wider than the ±0.28 the addendum expected at K = 100. A factor 2 in n gives little leverage. The data do not reject 1/√n, but they also do not reject b = 0.15 or b = 0.8.
- In D1, the 361 cell has 3 zero draws (2 above-alpha, 1 vacuous). These zero draws drive most of its high SD (1.79 with zeros, 1.37 without). The steep D1 slope comes mostly from them.

## Revised n* (pre-registered formula: μ − 1.96 √(σ_b² + σ_w²) = 4.0153; μ and σ_w at 722 kept fixed)

| estimate | basis | needed σ_b* | n* | 95 % interval |
|---|---|---|---|---|
| **primary: D2 line** | D2 fit; μ 5.187, σ_w 0.349 (D2-722) | 0.485 | **≈ 2,520** | [1,080, 460,000] (0.6 % of replicates: not reachable) |
| D2 anchored at its 722 cell, fitted b | 0.884 at 722, b 0.483 | 0.485 | ≈ 2,500 | - |
| D2 anchored, b = 0.5 | 0.884 at 722 | 0.485 | ≈ 2,400 | - |
| secondary A: P15-37 figure with the D1 exponent | 1.039 / 0.531 (R120), b_D1 0.746 | 0.531 | ≈ 1,770 | [1,180, 19,200] (from the b interval) |
| P15-37 (b = 0.5, for comparison) | R120 | 0.531 | 2,764 | - |

- The primary revised n* is **about 2,500 calibration items** (3.5 times the 722 of `val_select`). This is close to P15-37's 2,760, because the measured exponent (0.48) is close to 0.5.
- The upper end of the interval is very large: with a slow exponent, size alone hardly reaches the target. The lower end (about 1,080) still needs 1.5 times `val_select`.

## The design effect at 722 (stated in the plan before any result)
- R120 SD (P15-29 draw) / D2-722 SD = 1.039 / 0.884 = **1.18**. That is below the upper bound of 1.27.
- But the full difference comes from the 2 above-alpha zero draws in R120. On certified draws only, D2-722 has the larger SD (0.884 against 0.785). The same settings in P15-37 A0 alone (40 new draws, no zeros) had 0.92.
- So the data do **not** show that the P15-29 draw over-states the spread of the certified draws. The mechanism in the plan holds for statistics that are means over one part. The safe WPM depends on an LTT threshold, and its spread is not dominated by that term.

## Assumptions of the P15-37 projection, answered
| assumption | result |
|---|---|
| σ_b ∝ n^(−1/2) | **not rejected** (b_D2 0.48 [0.12, 0.83]); poorly constrained |
| mean fixed in n | **does not hold below 722**: D2 mean 4.64 (361), 4.70 (481), 5.19 (722); commits 189 / 186 / 207. Fewer LTT items give a higher threshold and fewer commits. Above 722 the mean probably grows a little more, so "mean fixed" is likely conservative for n* > 722. |
| σ_w fixed in n | holds: 0.334 / 0.335 / 0.349 (D2) |
| zero draws (≤ δ at every n) | D2: 2 / 100 at 361, 0 at 481 and 722. D1: 3 / 40 at 361, 0 at 481. All within δ = 10 %. |

## Expectations (plan), answered honestly
- "b_D2 near 0.5": **confirmed** (0.48), with a wide interval.
- "b_D1 near 0.5-0.6": the point estimate is higher (0.75), but the interval contains both.
- "σ_b,D2(722) smaller than R120's 1.039": **confirmed** (0.884). The reason is different from the expectation: R120 has 2 zero draws, not a larger spread of certified draws.
- "primary n* smaller than 2,760": **confirmed**, but only a little (about 2,520).
- "zero draws more frequent at small n; mean lower at small n": both confirmed.

## Notes and limits
- (a) Pinned pipeline values; (b) one participant, one decoder checkpoint, the same 701 evaluation trials in every draw.
- (c) The bootstrap uses only the 722 `val_select` trials. n* > 722 extrapolates a three-point line over a factor 2 in n.
- (d) Duplicates inside parts: a single draw's certificate is not a valid certificate.
- (e) The grouped first-fit rule of D2 places trials with many copies a little more often into later parts.
- (f) `null_trials` 20 instead of 300. X1 shows that decisions do not change. No control committed in any draw.
- `docs/safe-wpm.md` is unchanged.

> **Our take:** the 1/√n assumption of P15-37 survives the check, and its order of magnitude holds. The T15 lower end would need about 2,500 labelled calibration trials (likely range 1,100 to several thousand) to clear the no-BCI 4.02 at the current mean. The exponent is poorly fixed by a factor-2 range of n. A tighter estimate needs more draws per cell (K ≈ 400 for ±0.15) or a wider n range, and only new data can give that range. Neither changes the decision of P15-37: size alone needs several times `val_select`, and T15 has no such data (gap 160).
