---
title: P5-10 PersonalTrust watches the guard risk - plan (addendum to P5-01)
type: experiment
task: P5-10
updated: 2026-11-16
---

# P5-10: guard-risk drift test in PersonalTrust (plan)

Written and committed **before** the replay runs. Roadmap item: [P5-10](../../wiki/questions/roadmap-standard.md#p5-10-personaltrust-watches-the-guard-risk). Gap 12 of the [open-gap list](../../wiki/questions/open-gaps.md). The P5-01 [plan](plan.md) and [results](results.md) stay as they are; the results get a dated note.

## Change under test
`PersonalTrust(..., guard_risk_test=True, level_guard_risk=0.005, on_guard_risk_drift="propose")` (`src/fidetype/trust/personal.py`). A third `ConformalDriftTest` watches `guard_risk` of each decision against `profile.reference_guard_risk` (now written by `calibration_stats`, same sampled items as the reference scores, rounded to 1e-4, no text). `P(any false alarm) <= level_scores + level_risk + level_guard_risk`.

**Default: unchanged (opt-in).** Turning the test on by default is not strictly safer: with the same per-test levels it raises the total false-alarm budget (0.010 -> 0.015), and with a fixed total budget it lowers the level of the two P5-01 tests (later alarms). Either is a behaviour change for existing users. The roadmap allows opt-in. Note: the roadmap text says "RiskDriftTest on the guard risk". The guard risk is a per-item score, not a loss with limit alpha, so we use the conformal score test on it, as the A2g arm of P5-01 did.

## Replay (script `replay_p5_10.py`, CPU, no decoding)
Same input as P5-01 part R (F1 / E2 pilot, frozen arm, 16 days, 6,720 items, read only, no text field).
1. **Reproduction.** Run the four P5-01 arms (A0, A1, A2, A2g) with the unchanged `replay.py` code and compare with the committed `results/replay.json`: commits, wrong commits, labels, proposals, accepted, offer-only items, days above alpha, tightenings, threshold changes outside `finish_update`, and the alarm list (test, item).
2. **New arms through `PersonalTrust`.** A stub guard replays the recorded decision of the P5-01 arm (the replay has no decoder inputs, so `PersonalTrust` cannot re-calibrate here; the unit tests cover that path). A new controller starts at each point where the P5-01 arm started new drift tests, with the same reference block, seed and levels, and gets the same items.
   - **A2p**: `guard_risk_test=True`, levels 0.0025 (scores) / 0.005 (risk) / 0.0025 (guard risk), segments of A2g.
   - **A2d**: default `PersonalTrust` (levels 0.005 / 0.005), segments of A2.
   - Report only: **A2ps** (A2d with `spread=True`, P5-09) and **A2gs** (A2p with `spread=True`).

## Pass rules
- **P10-1:** every compared number and the alarm list of all four P5-01 arms are identical to `results/replay.json`.
- **P10-2:** the A2p alarm list (test, item) equals the A2g alarm list (4 guard-risk alarms in P5-01: items 697, 1,794, 2,159, 6,647), and the profile history has one `drift_alarm` entry per alarm.
- **P10-3:** the A2d alarm list equals the A2 alarm list (no alarm in P5-01).

## Outputs
`results/replay-p5-10.json` (aggregates only); a dated note in `results.md`. Nothing is written to the P5-01 derived folder.
