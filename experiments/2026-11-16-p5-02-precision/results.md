---
title: P5-02 precision-type guarantee on two replay sets - results
type: experiment
task: P5-02
updated: 2026-11-16
---

# P5-02: "when it types, it is right" - results

[Plan](plan.md) (written before the runs). Code: `src/fidetype/trust/precision_bound.py`, `fidetype.trust.calibrate(target_precision=)`, tests `tests/test_trust_precision_bound.py`. Run: `run.py t15 t12` (CPU, background class, about 15 min, peak about 0.8 GB). Tables: `report.py`. Per-trial files only in `C:/Users/zhang/bci-data/derived/p5-02-precision/`.

## Summary

| Check | Result |
|---|---|
| P1 held-out precision >= target | **Vacuous** on both sets at all four targets (0.5, 0.8, 0.9, 0.95): no threshold was certified, so every guard never commits (0 / 701, 0 / 400). No wrong commit on held-out data, so the bound holds trivially |
| P2 resampling coverage (T15) | **Not testable**: 0 of 1000 draws feasible at every target (with the P14-03 `min_commit_p`, as planned) |
| P3 null controls, marginal wrong-commit <= alpha | Pass (all controls 0 commits; marginal rate 0) |
| Method validity | Shown on synthetic exchangeable data only (`test_bound_holds_on_exchangeable_data`: 200 draws, violation rate <= delta + 3 SE, mean commit rate > 10 %) |

**Why vacuous.** These decoders are rarely right. The top-1 sentence is right on 59 / 701 (T15) and 31 / 400 (T12) held-out trials. No `p_top1` threshold gives a precision near 0.5 with enough commits (curves below): T15 best 0.367 (90 commits at `commit_p` 0.2); T12 0.5 at 4 commits, 0.40 at 25 commits. Certifying precision 0.5 at delta 0.1 needs at least 4 right commits with no wrong one, or more commits at a precision clearly above 0.5. Precision 0.9 needs at least 22 right commits. So the new guard does the right thing: it refuses to commit, where the P14-03 guard committed 2 (T15, both wrong) and 25 (T12, 15 wrong).

> **Our take:** the precision guarantee works as a safety switch, but on today's replay decoders it buys safety only by removing all commits. A useful operating point needs a decoder with much higher top-1 accuracy at high `p_top1` (P11 / M4-13), or a looser commit unit (word-level commit, P15-06 open item). The guarantee itself does not need changes for that.

## Tables (aggregates only)

### T15 (722 calibration, 701 held out)

Base (P14-03) guard `tcfg-7ecd016879246eb6`: commit_p 0.3. Held out: 673 items pass every commit condition at commit_p 0; top-1 right on 59.

| target precision | commit_p | feasible | cal. test commits / wrong | held-out commits / n | commit rate | wrong | precision [CP95] | P1 | marginal wrong-commit [CP95] | controls |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | inf | False | 0 / 0 | 0 / 701 | 0.0000 | 0 | - - | vacuous | 0.0000 [0.0000, 0.0052] | PASS |
| 0.8 | inf | False | 0 / 0 | 0 / 701 | 0.0000 | 0 | - - | vacuous | 0.0000 [0.0000, 0.0052] | PASS |
| 0.9 | inf | False | 0 / 0 | 0 / 701 | 0.0000 | 0 | - - | vacuous | 0.0000 [0.0000, 0.0052] | PASS |
| 0.95 | inf | False | 0 / 0 | 0 / 701 | 0.0000 | 0 | - - | vacuous | 0.0000 [0.0000, 0.0052] | PASS |

Resampling, with min_commit_p = P14-03 threshold (plan):

| target | feasible draws | violations | violation rate | limit (0.1 + 3 SE) | pass | mean pop. precision | mean commit rate |
|---|---|---|---|---|---|---|---|
| 0.5 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.8 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.9 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.95 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |

Resampling, no min_commit_p (extra diagnostic, not in the plan):

| target | feasible draws | violations | violation rate | limit (0.1 + 3 SE) | pass | mean pop. precision | mean commit rate |
|---|---|---|---|---|---|---|---|
| 0.5 | 11 / 1000 | 3 | 0.2727 | 0.3714 | n/a (< 50 feasible) | 0.5436 | 0.0335 |
| 0.8 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.9 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.95 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |

Held-out precision curve (diagnostic, no guarantee):

| commit_p | 1.0 | 0.99 | 0.95 | 0.9 | 0.8 | 0.7 | 0.6 | 0.5 | 0.4 | 0.3 | 0.2 | 0.1 | 0.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| commits | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 90 | 673 | 673 |
| precision | - | - | - | - | - | - | - | - | - | 0.000 | 0.367 | 0.088 | 0.088 |

### T12 (480 calibration, 400 held out)

Base (P14-03) guard `tcfg-bd955c64a9cd7966`: commit_p 0.3. Held out: 376 items pass every commit condition at commit_p 0; top-1 right on 31.

| target precision | commit_p | feasible | cal. test commits / wrong | held-out commits / n | commit rate | wrong | precision [CP95] | P1 | marginal wrong-commit [CP95] | controls |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | inf | False | 0 / 0 | 0 / 400 | 0.0000 | 0 | - - | vacuous | 0.0000 [0.0000, 0.0092] | PASS |
| 0.8 | inf | False | 0 / 0 | 0 / 400 | 0.0000 | 0 | - - | vacuous | 0.0000 [0.0000, 0.0092] | PASS |
| 0.9 | inf | False | 0 / 0 | 0 / 400 | 0.0000 | 0 | - - | vacuous | 0.0000 [0.0000, 0.0092] | PASS |
| 0.95 | inf | False | 0 / 0 | 0 / 400 | 0.0000 | 0 | - - | vacuous | 0.0000 [0.0000, 0.0092] | PASS |

Resampling, with min_commit_p = P14-03 threshold (plan):

| target | feasible draws | violations | violation rate | limit (0.1 + 3 SE) | pass | mean pop. precision | mean commit rate |
|---|---|---|---|---|---|---|---|
| 0.5 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.8 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.9 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.95 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |

Resampling, no min_commit_p (extra diagnostic, not in the plan):

| target | feasible draws | violations | violation rate | limit (0.1 + 3 SE) | pass | mean pop. precision | mean commit rate |
|---|---|---|---|---|---|---|---|
| 0.5 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.8 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.9 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |
| 0.95 | 0 / 1000 | 0 | - | - | n/a (< 50 feasible) | - | - |

Held-out precision curve (diagnostic, no guarantee):

| commit_p | 1.0 | 0.99 | 0.95 | 0.9 | 0.8 | 0.7 | 0.6 | 0.5 | 0.4 | 0.3 | 0.2 | 0.1 | 0.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| commits | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 4 | 25 | 108 | 376 | 376 |
| precision | - | - | - | - | - | - | - | 0.000 | 0.500 | 0.400 | 0.231 | 0.080 | 0.080 |

## Notes
- The P14-03 base guard is reproduced exactly (`commit_p` 0.3 on both sets).
- "cal. test commits" = commits of the selected threshold on the LTT part of the calibration set (empty: nothing certified).
- The unconstrained resampling (no `min_commit_p`) is an extra diagnostic, not in the plan. On T15 at target 0.5 it was feasible in 11 / 1000 draws, with 3 violations (too few draws to judge; the bound is a 1 - delta statement over draws, and 11 draws give no power).
- Held-out sets are used as a finite population in the resampling. For T12 (later sessions) this checks the method, not drift.
