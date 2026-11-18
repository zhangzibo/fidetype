---
title: P5-02 precision-type guarantee rerun on the M4-13 decoder - results
type: experiment
task: P5-02, P5-08
updated: 2026-11-18
---

# P5-02 rerun on M4-13: "when it types, it is right" - results

Pre-registration: [plan.md](plan.md) (commit `97a2fc4`, before any M4-13 output). Queue: [trust-reruns plan](../2026-11-17-trust-reruns-m4-13/plan.md). Method and code: the [P5-02 run](../2026-11-16-p5-02-precision/results.md), imported unchanged. Aggregates: [results/results.json](results/results.json), log [results/run.log](results/run.log). Per-trial files: `C:/Users/zhang/bci-data/derived/p5-02-precision-m4-13/` only.

Run: queue stage `p5-02`, 2026-11-17 20:21-20:29 (447 s, CPU, background class, 4 threads). Decoder: M4-13 long0 `best.pt` (step 115,000, SHA-256 `8fafe916...`); calibration = val_select (722, CPU decode), held out = val_eval (701, the M4-13 queue's GPU decode). Both log-prob files carry the same checkpoint hash.

## Verdict

| rule (pre-registered) | result |
|---|---|
| **P1** held-out error among commits <= 1 - target, per feasible guard | **pass** at 0.5 (error 17 / 104 = 0.163 <= 0.5; precision 0.837, CP95 [0.751, 0.902]). Targets 0.8, 0.9, 0.95: no guard (infeasible, vacuous) |
| **P2** resampling violation rate <= 0.1 + 3 SE, targets with >= 50 feasible draws | **pass** at 0.5 (0 / 927 feasible draws, limit 0.130). 0.8: 42 feasible draws (< 50, not testable). 0.9, 0.95: 0 feasible draws |
| **P3** null controls pass; marginal wrong-commit rate <= alpha | **pass** (every control 0 / 300 commits; marginal rate at 0.5: 0.0243, CP95 [0.0142, 0.0385] <= 0.05; other targets 0) |
| **U** useful: feasible with >= 20 held-out commits | **useful at 0.5** (104 commits). **Not useful at 0.8, 0.9, 0.95** (infeasible) |

On M4-12 (P5-02, 2026-11-16) every target was infeasible and the guard never committed. On M4-13 the guard certifies precision 0.5 and commits on 14.8 % of held-out sentences. A useful high target (0.8 or more) is still not certifiable.

## Held-out table (T15 val_eval, 701)

Base (P14-03) guard `tcfg-56224bd356d42363`: commit_p 0.73. Held out: 694 items pass every commit condition at commit_p 0; top-1 right on 257 (M4-12: 59).

| target | commit_p | feasible | certified thresholds | cal. LTT commits / wrong (n 271) | held-out commits | wrong | precision [CP95] | P1 | marginal wrong-commit [CP95] | controls |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 0.73 | yes | 51 | 54 / 8 (CP lower bound of precision 0.771) | 104 | 17 | 0.837 [0.751, 0.902] | pass | 0.0243 [0.0142, 0.0385] | pass |
| 0.8 | inf | no | 0 | - | 0 | 0 | - | vacuous | 0 [0, 0.0052] | pass |
| 0.9 | inf | no | 0 | - | 0 | 0 | - | vacuous | 0 [0, 0.0052] | pass |
| 0.95 | inf | no | 0 | - | 0 | 0 | - | vacuous | 0 [0, 0.0052] | pass |

Minimum right commits on the LTT part to certify (zero wrong): 0.5: 4; 0.8: 11; 0.9: 22; 0.95: 45.

## Resampling (pre-registered, `min_commit_p` = P14-03 threshold)

| target | feasible draws | violations | violation rate | limit | P2 | mean pop. precision | mean commit rate |
|---|---|---|---|---|---|---|---|
| 0.5 | 927 / 1000 | 0 | 0.000 | 0.130 | pass | 0.837 | 0.146 |
| 0.8 | 42 / 1000 | 0 | 0.000 | 0.239 | n/a (< 50) | 0.880 | 0.098 |
| 0.9 | 0 / 1000 | - | - | - | n/a | - | - |
| 0.95 | 0 / 1000 | - | - | - | n/a | - | - |

Without `min_commit_p` (extra diagnostic, as in P5-02; exploratory): 0.5: 993 feasible, 5 violations (0.005, limit 0.129), mean commit rate 0.460, mean precision 0.629; 0.8: 35 feasible, 2 violations; 0.9 and 0.95: 0 feasible.

## Held-out precision curve (diagnostic, no guarantee)

| commit_p | 1.0 | 0.99 | 0.95 | 0.9 | 0.8 | 0.7 | 0.6 | 0.5 | 0.4 | 0.3 | 0.2 | 0.1 | 0.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| commits | 0 | 0 | 5 | 22 | 69 | 126 | 201 | 286 | 388 | 503 | 650 | 694 | 694 |
| precision | - | - | 1.000 | 0.909 | 0.855 | 0.817 | 0.761 | 0.654 | 0.572 | 0.475 | 0.392 | 0.369 | 0.369 |

## Notes (exploratory, not pre-registered)
- The precision-0.5 guard has the same threshold as the base guard (0.73), because the selection never goes below the P14-03 `commit_p`. So its held-out decisions equal the base guard (104 commits, 17 wrong; the same numbers as the M4-13 drop-in row of P14-05). The new fact is the certificate: the guard now also states "precision >= 0.5 with probability >= 0.9".
- Precision 0.8 fails on sample size, not on the decoder alone. On held-out data, commit_p 0.8 gives 69 commits at precision 0.855. But the LTT part has only 271 items. At precision near 0.85, a CP lower bound above 0.8 needs far more commits than 271 items give at this commit rate.

> **Our take:** the stronger decoder turns the precision guarantee from vacuous to useful at a low target. "When it types, it is right" at 0.84 measured precision, with a certified floor of 0.5, is a real operating point. A product target (0.9) needs either more calibration items, a per-word commit, or a decoder with many more confident right sentences (P11).

## Gap decision
- **P5-08: done-when met.** On held-out T15 data, `calibrate(target_precision=0.5)` certifies a threshold (0.73) with 104 commits, and the error among commits (0.163, CP95 upper 0.249) is at or below 1 - 0.5. Closed 2026-11-18.
- New gap: precision at a useful target (>= 0.8) is still not certifiable. Registered as P5-20 (gap 58).

## Deviations
- None in the method. The queue deferred this stage once (2026-11-17 18:51, only 327 MB free RAM) and resumed at 20:21 from the start. The run itself started only once.
