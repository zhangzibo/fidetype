---
title: P5-02 precision-type guarantee rerun on the M4-13 decoder - pre-registration
type: experiment
task: P5-02
updated: 2026-11-16
---

# P5-02 rerun: "when it types, it is right" with the M4-13 decoder (pre-registration)

Written and committed **before** the M4-13 decoder has finished and before any M4-13 output exists. Method, measures and code: the [P5-02 plan](../2026-11-16-p5-02-precision/plan.md) and its run.py (imported unchanged by [run.py](run.py)). Queue: [trust-reruns plan](../2026-11-17-trust-reruns-m4-13/plan.md).

## Why
On M4-12 fixed0 (T15) and T12 v2 the precision guarantee was vacuous: no threshold certified at any target, 0 commits; top-1 right only 59/701 (T15) and 31/400 (T12) ([results](../2026-11-16-p5-02-precision/results.md)). Certifying precision 0.9 needs >= 22 right commits on the LTT part (0.95: 45). M4-13 has about half the phoneme error rate of M4-12, so more right top-1 sentences.

## What changes
Only the decoder log-probs: calibration = M4-13 val_select (722, CPU decode of best.pt), held out = M4-13 val_eval (701, the M4-13 queue's decode). T15 only (M4-13 is a T15 decoder; the T12 values stay those of the committed P5-02 run). Everything else is the P5-02 T15 setting: P14-03 `decode_fn` and loaders' item order and texts, seed 0, alpha 0.05, delta 0.1, `precision_delta` 0.1, targets {0.5, 0.8, 0.9, 0.95}, grid 1.00 -> 0.00 step 0.01, selection rule, null controls.

## Measures (as P5-02)
1. Held out per target: commits, wrong commits, precision with CP95, commit rate, marginal wrong-commit rate with CP95.
2. Null controls of each final guard.
3. Resampling coverage check: per-item `(can_commit, p_top1, wrong)` of the held-out set with the base guard at commit_p 0; 1000 draws of 175 ordering + 175 test items without replacement (seed `[0, 502, 3]`), `precision_ltt` per target with `min_commit_p` = the P14-03 threshold; and the same without `min_commit_p`.
4. Diagnostic precision curve on the held-out items.

## Pass rules (fixed now; the P5-02 rules on T15)
- **P1:** for each feasible guard, held-out error among commits <= `1 - target_precision` (point estimate; CP95 reported).
- **P2:** resampling violation rate <= 0.1 + 3 SE at each target with >= 50 feasible draws.
- **P3:** null controls pass; held-out marginal wrong-commit rate <= alpha.
- **U (utility, reported):** a target is "useful" if its guard is feasible with >= 20 held-out commits. An infeasible guard is a valid, vacuous result.

## Outputs
Per-trial files: `C:/Users/zhang/bci-data/derived/p5-02-precision-m4-13/` only. Repo: `results/results.json`, `results/run.log`, `results.md` after the run. CPU, about 10 min (P5-02 T15: 568 s), RAM about 1 GB.

## Dry run (plumbing only)
`TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12`, 160 calibration + 60 held-out M4-12 items, 40 draws of 12 + 12: all targets infeasible (expected on 160 items), controls pass, code path complete (`results/dryrun-m4-12/`).
