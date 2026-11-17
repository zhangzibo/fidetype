---
title: P5-09 drift test that detects a spread change at the same centre - results
type: experiment
task: P5-09
updated: 2026-11-16
---

# P5-09: spread bets for the conformal drift test (results)

[Plan](plan.md) (committed in `3def17e` before the run, with the code). Code: `ConformalDriftTest(spread=True)` in `src/fidetype/trust/drift.py`; tests in `tests/test_trust_personal.py`. Numbers: [results/synth.json](results/synth.json). Run: `synth.py` (CPU, background class, 173 s). **M** = P5-01 bets (`spread=False`, default), **MS** = with spread bets. Same streams and seeds for both (paired).

## Outcome

| id | criterion | result |
|---|---|---|
| **S1** | MS false-alarm rate <= level + 3 SE (1,000 runs) | **pass**: 0.007 at 0.01 (limit 0.0194); 0.040 at 0.05 (limit 0.0707) |
| **S2** | MS detects sd 1 -> 2 in >= 95 % and sd 1 -> 0.5 in >= 90 % of 200 runs | **pass**: 200 / 200 and 200 / 200 |
| **S3** | mean-shift margin: median delay ratio <= 1.25 at -0.5 and -1.0 sd; detected share at -0.25 sd >= M - 0.10 | **fail** (one part): ratios 1.16 and 1.14 pass; at -0.25 sd MS detects 0.445 vs M 0.61 (loss 0.165 > 0.10) |
| **S4** | T12 permutation null, MS alarm rate <= 0.096 (200 permutations, level 0.05) | **pass**: `p_top1` 0.045, guard risk 0.030 |

The done-when of the roadmap holds (S1, S2, S4). The plan says that a fail of S3 does not block the item, and that we report its cost. The cost is real for **small** mean shifts. It is registered as a new gap (P5-12, below).

## Spread change at the same centre (level 0.01, 200 runs, 500 null items before the change)

| change | M detected | MS detected | MS median delay | MS 90th pct |
|---|---|---|---|---|
| sd 1 -> 2 (the P5-01 gap) | 4 / 200 (3 of them alarms before the change) | **200 / 200** | 75 | 111 |
| sd 1 -> 0.5 | 5 / 200 | **200 / 200** | 66 | 85 |
| sd 1 -> 1.5 (report only) | 1 / 200 | **200 / 200** | 163 | 323 |

## Mean shift (sd 1; the cost of the spread bets)

| shift | M detected / median | MS detected / median | ratio of medians |
|---|---|---|---|
| -0.25 sd | 122 / 200, 813.5 | 89 / 200, never (fewer than half) | - |
| -0.5 sd | 200 / 200, 109 | 200 / 200, 126 | 1.16 |
| -1.0 sd | 200 / 200, 44 | 200 / 200, 50 | 1.14 |

"Alarm before the change" (during the 500 null items, counted as delay 0, as in P5-01): M 0 to 3, MS 0 to 4 per cell of 200. These are false alarms inside the level.

## Why the small shift costs more
The mixture now has 5 components instead of 3, so each mean component starts with 1/5 of the capital instead of 1/3. The jump also moves capital into the two spread components at each step. For a large shift the mean component grows fast and the extra start cost (log(5/3), about 0.5 nats) is a few items. For a small shift the growth per item is small, the conformal bag fills with shifted items, and the p-values become uniform again before the capital reaches 1 / level. So the extra cost decides more runs.

> **Our take:** use `spread=True` when a change of spread is plausible (for example a noisier signal on a bad day gives a wider confidence spread). Keep the default (`spread=False`) when only small mean shifts matter. A better mixture (prior weights that favour the mean bets, or a separate spread test with its own level) can cut the cost; this is gap P5-12.

## Default
Unchanged (`spread=False`), as the plan fixed in advance. `DriftMonitor(spread=)` and `PersonalTrust(spread=)` expose it. Docs: [docs/trust-personalisation.md](../../docs/trust-personalisation.md) section 4.2.

## T12 replay with spread bets (from the P5-10 run)
Through `PersonalTrust` on the 16-day T12 replay ([P5-10 note](../2026-11-16-p5-01-personal/results.md#p5-10-guard-risk-test-through-personaltrust-2026-11-16)): with `spread=True` the `p_top1` test still never alarms. The guard-risk test alarms 2 times (items 1,799 and 2,157) instead of 4 (697, 1,794, 2,159, 6,647). On this data the guard-risk drift is mainly a shift of the centre, so the spread bets add nothing and cost two alarms.

## Limits
- Gaussian synthetic scores only; one jump rate (0.01); one reference size (200).
- The development smoke checks (20 runs, see the plan) are not part of these results.
