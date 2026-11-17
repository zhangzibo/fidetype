---
title: P5-02 precision-type guarantee on two replay sets - plan
type: experiment
task: P5-02
updated: 2026-11-16
---

# P5-02: "when it types, it is right" on the P14-03 replay sets (plan)

Written before any validation run. Task: roadmap P5-02 (safety guarantees), the precision part: a calibrated bound on P(commit is wrong | the guard commits) at a level that the user chooses. The P14-03 guard bounds only the marginal rate (wrong commits / all utterances). On P14-03 most commits were wrong (T15 2 of 2, T12 15 of 25); in the F1 pilot 88-100 %.

## Method (code: `src/fidetype/trust/precision_bound.py`, `calibrate(target_precision=)`)
- Loss: a commit whose text is not exactly the true text (the P14-03 text normalisation).
- Per threshold `commit_p`: exact binomial p-value `P(Bin(commits, beta) <= wrong)` on the commits of the test items, `beta = 1 - target_precision`. It is valid given the number of commits (exchangeable items).
- Learn then Test: test order from the policy-grid items (37.5 %), fixed-sequence test on the LTT items (37.5 %), level `delta_p`. Grid 1.00 -> 0.00 step 0.01.
- Selection: most commits among certified thresholds with `commit_p >=` the P14-03 threshold. So the P14-03 marginal bound and the null controls still hold.
- No certified threshold: the guard never commits.

## Sets and splits (the P14-03 ones, unchanged)
Same data, decoders, `decode_fn`, `stream_texts`, seed 0 and splits as [P14-03](../2026-11-16-p14-03-replay-validation/plan.md): T15 by trial (722 calibration, 701 held out), T12 by session (480 calibration, 400 held out). Inputs are read only from `C:/Users/zhang/bci-data/derived/` (the P14-03 loaders, imported, not changed). Per-trial outputs go only to `C:/Users/zhang/bci-data/derived/p5-02-precision/`. The repository gets aggregates only.

## Arms (fixed now)
alpha 0.05, delta 0.1 (P14-03 values). `target_precision` in {0.5, 0.8, 0.9, 0.95}, `precision_delta` 0.1. One guard per set and target.

## Measures
1. Held out: commits, wrong commits, precision = right / commits with a two-sided CP95 interval, commit rate = commits / utterances, marginal wrong-commit rate with CP95.
2. Null controls of each final guard (uniform, shuffled), as in P14-03.
3. Resampling check of the bound (T15 and T12, separately): the held-out items of each set act as a population. With the base guard of the set (commit_p 0), compute per-item `(can_commit, p_top1, wrong)` once. Then 1000 random draws: 175 ordering + 175 test items (T12: 133 + 133) without replacement, `precision_ltt` at each target, with `min_commit_p` = the P14-03 threshold. A violation = the population precision at the selected threshold is below the target. Report the violation rate among feasible draws and the mean commit rate.
4. Diagnostic: precision against `commit_p` on the held-out items (no guarantee).

## Pass rules (fixed now)
- P1 (held out): for each feasible guard, held-out error among commits <= `1 - target_precision` (point estimate). Report the CP95 interval; one draw cannot prove a 1 - delta statement.
- P2 (resampling): on T15 (exchangeable by trial), violation rate <= 0.1 + 3 SE at each target with >= 50 feasible draws. T12 (later sessions) is reported, not judged: the held-out sessions are a different distribution than the calibration sessions, but inside the resampling they are exchangeable, so it checks the method, not drift.
- P3: null controls pass; held-out marginal wrong-commit rate stays <= alpha.
- An infeasible guard (never commits) is a valid, honest result, not a failure. It is reported as "vacuous".

## Expected
Few base commits on both sets (T15 about 2 per 701). Certifying precision 0.9 needs >= 22 right commits on the LTT part (0.95: 45). High targets will likely be infeasible with these decoders. Low targets (0.5) may be feasible on T12.
