---
title: P5-09 drift test that detects a spread change at the same centre - plan
type: experiment
task: P5-09
updated: 2026-11-16
---

# P5-09: spread bets for the conformal drift test (plan)

Written and committed **before** the synthetic sweep and the permutation check run. Roadmap item: [P5-09](../../wiki/questions/roadmap-standard.md#p5-09-drift-test-that-detects-a-spread-change-at-the-same-centre). Gap 11 of the [open-gap list](../../wiki/questions/open-gaps.md). Follow-up of P5-01 ([results](../2026-11-16-p5-01-personal/results.md): a change sd 1 -> 2 at the same mean was never detected in 200 runs).

Development note: while we wrote the code, two smoke checks of 20 runs each (sd 1 -> 2) and the unit tests ran. They only checked that the code works. They are not part of the results.

## Change under test
`ConformalDriftTest(..., spread=True)` (`src/fidetype/trust/drift.py`). The Simple Jumper mixture gets two more betting components, `1 + eps * (|2p - 1| - 1/2)`, `eps` in {-1, 1}, next to the P5-01 components `1 + eps * (p - 1/2)`, `eps` in {-1, 0, 1}. Same jump rate (0.01), same smoothed conformal p-values. Under the null, `|2p - 1|` is uniform on [0, 1], so every factor has conditional mean 1 and is positive. The mixture is a test martingale; Ville's inequality gives `P(any alarm) <= level`. `spread=False` (default) is the P5-01 test, bit for bit (unit test).

Variants: **M** = `spread=False` (P5-01 bets), **MS** = `spread=True`. Both run on the same random streams and the same tie-break seed (paired).

## Part S: synthetic sweep (script `synth.py`, seed 20261117)
- **S1 false alarms.** Reference 200 N(0, 1), 2,000 live N(0, 1). Levels 0.01 and 0.05. 1,000 runs per cell. Pass: MS rate <= level + 3 SE (binomial SE at the level, n = 1,000) at both levels. M is reported for comparison.
- **S2 spread change at the same centre.** Level 0.01. Reference 200, 500 null live items, then N(0, sd) with sd 2.0 (the P5-01 gap) and sd 0.5 (narrower); report also sd 1.5 (no pass rule). At most 5,000 items after the change. 200 runs per cell. Pass: MS detects the change (alarm after the change, within 5,000 items) in at least 95 % of runs for sd 2.0 and at least 90 % for sd 0.5. Report median and 90th percentile delay, both variants.
- **S3 no loss on mean shifts beyond a margin.** Same setup, mean shift -0.25, -0.5, -1.0 sd (sd 1). Pass: for -0.5 and -1.0, median delay of MS <= 1.25 x median delay of M; for -0.25, the share of runs detected within 5,000 items of MS >= that of M - 0.10.
- An alarm before the change counts as "detected at delay 0" (as in P5-01) and is also counted and reported.

## Part P: real-data false-alarm check (script `synth.py`, part P)
- **S4.** T12 F1 / E2 pilot, frozen arm, 16 days, 6,720 items (the P5-01 replay input, read only; no text field read). For `p_top1` and for the guard risk: 200 random permutations of the item order (this makes the stream exchangeable); MS test with the first 48 items as reference and the rest as live items, level 0.05. Pass: alarm rate <= 0.05 + 3 SE (0.096) for both streams. M is reported.

## Decision rule for the default
The default stays `spread=False` in this task, whatever the results. Reasons: (1) backward compatibility of the P5-01 test and of saved results; (2) MS spends some power on a mean shift (S3 measures it); (3) a hidden rerun queue imports trust code on 2026-11-17. `DriftMonitor(spread=)` and `PersonalTrust(spread=)` expose the option. If S1 to S4 pass, the docs recommend `spread=True` for users who expect spread changes.

## Done when (roadmap)
All of S1, S2 and S4 pass. S3 is the stated margin; a fail of S3 is reported, and the item still closes on S1 + S2 + S4, with the cost written down.

## Outputs
`results/synth.json` (aggregates only), `results.md`. No participant data in the repository.
