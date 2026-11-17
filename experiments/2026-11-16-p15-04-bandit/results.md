---
title: P15-04 bandit-feedback online risk control - replay results
type: experiment
task: P15-04
updated: 2026-11-16
---

# P15-04: online risk control with shown-only feedback - results

[Plan](plan.md) (committed in `d90a49b` before the run). Code: `src/fidetype/trust/bandit_risk.py`; tests `tests/test_trust_bandit_risk.py` (13). Scope of the guarantee: [f1-guarantee-scope](../../wiki/questions/f1-guarantee-scope.md). Run: `replay.py` (CPU, background class, 27 s, no decoding; inputs = P5-02 per-item files, read only). Aggregates: [results/summary.json](results/summary.json). Per-run files only in `C:/Users/zhang/bci-data/derived/p15-04-bandit/`.

## Summary

| Check | T12 (400) | T15 (701) | Verdict |
|---|---|---|---|
| R1 realised (observed) rate <= certificate, every run of A, B05, B20, E | 100 % | 100 % | **pass** |
| R2 long-run true wrong-commit rate, B05 vs `aci` (time order, q_notice 1.0) | 0.0500 [CP95 0.0308, 0.0762] vs 0.0500 (same 35 commits, 20 wrong) | 0.0471 [0.0326, 0.0655] vs 0.0471 (same 48 commits, 33 wrong) | **reported** (done-when) |
| R3 audit (G3) violations over 200 seeds (B05, B20) | 0 / 200, 0 / 200 | 0 / 200, 0 / 200 | **pass** (limit 0.1 + 3 SE) |
| R4 naive bias < 0 at >= 2 of 3 thresholds, and abs IPW bias < abs naive bias there | 3 of 3 (B05, B20) | 2 of 3 (B05, B20) | **pass** |
| R5 silent errors (q_notice 0.9): true >= observed in every run | gap mean 0.0057, min 0 | gap mean 0.0054, min 0 | **pass** (gap reported, not covered) |

B05 makes the same commits as `aci` in 200 / 200 seeds: exploration never commits, and the ACI update is the same. The new part is the audit and the exploration labels. User cost of exploration: median 18 extra offers (T12, ε 0.05) and 73 (ε 0.20); T15 32 and 129.

## Long-run wrong-commit rate (time order, alpha 0.05, start threshold 0.3)

| Arm | T12 commits / wrong | T12 rate [CP95] | T15 commits / wrong | T15 rate [CP95] |
|---|---|---|---|---|
| A `aci` (existing), q 1.0 | 35 / 20 | 0.0500 [0.0308, 0.0762] | 48 / 33 | 0.0471 [0.0326, 0.0655] |
| B05 `bandit-aci` ε 0.05, q 1.0 | 35 / 20 | 0.0500 [0.0308, 0.0762] | 48 / 33 | 0.0471 [0.0326, 0.0655] |
| B20 ε 0.20, q 1.0 | 35 / 20 | 0.0500 | 48 / 33 | 0.0471 |
| A `aci`, q 0.9 (true; observed) | 37 / 22 | 0.0550 (observed 0.0500) | 55 / 39 | 0.0556 (observed 0.0456) |
| B05, q 0.9, median of 200 seeds (range) | 37 | 0.0550 (0.050-0.070) | 52 | 0.0528 (0.047-0.061) |
| C `window-full` (oracle labels, not deployable) | 28 / 18 | 0.0450 [0.0269, 0.0702] | 42 / 27 | 0.0385 [0.0255, 0.0555] |
| D `window-naive` (shown only) | 0 / 0 | 0 | 0 / 0 | 0 |
| E `bandit-max` ε 0.20 | 0 | 0 | 2 / 1 | 0.0014 |

- The (G1) certificate equals the realised observed rate in each run. This is expected: it is an identity. The useful number is the bound fixed in advance, `alpha + (score_max - lam_1 + eta) / (eta T)`: 0.0875 for T12 (T = 400) and 0.0714 for T15 (T = 701). The realised rates are under both.
- Random orders (200 permutations, q 1.0): `aci` and B05 median 0.0500 (T12) and 0.0485 (T15); 17 % of T12 permutations end above 0.05 (at most 0.0550, inside the bound fixed in advance, 0.0875); 0 % on T15.
- D never commits: without exploration, a window CRC that sees only commit labels never gets the labels it needs to start. C needs labels that the user does not give.
- E (`rule="max"`) is "safe but costly", as expected: the audit cannot certify a threshold with these decoders and this few labels.

## Bias of the naive estimate (precision error at thresholds below the running threshold, mean over 200 seeds of estimate - true)

| Set, arm | lam 0.15 naive / IPW | lam 0.20 naive / IPW | lam 0.25 naive / IPW |
|---|---|---|---|
| T12, B05 | -0.235 / -0.022 | -0.171 / -0.026 | -0.067 / -0.026 |
| T12, B20 | -0.112 / -0.009 | -0.110 / -0.003 | -0.052 / -0.007 |
| T15, B05 | -0.109 / -0.013 | +0.031 / -0.018 | -0.035 / +0.006 |
| T15, B20 | -0.055 / -0.009 | +0.024 / +0.003 | -0.031 / -0.009 |

The naive estimate is optimistic where the shown items are a biased sample (T12: by up to 0.235 on an error rate near 0.86). The IPW estimate is within about one standard error of zero (the bias column is the mean of a noisy estimator over 200 coin draws on one fixed stream).

## Precision target (R6, report only): target precision 0.5

| Set | P-bandit commits / error among commits / certificate | P-naive commits / error |
|---|---|---|
| T12 | 7 / 0.857 / 0.857 | 10 / 0.600 [CP95 0.262, 0.878] |
| T15 | 2 / 1.000 / 1.000 | 2 / 1.000 |

Both overshoot 0.5 on these streams. The (G2) bound is long-run per commit: with 7 commits its slack `(lam_end - lam_1)/(eta N_c)` is 0.357. After a few wrong commits the precision ACI raised the threshold above every later score and stopped committing. That is the controller doing what (G2) says, but at 2-7 commits no precision claim is possible. On the synthetic stream of the test suite (3000 items) the precision ACI holds the target (error <= 0.10 + 0.01 with > 1000 commits) where the naive controller overshoots (mean 0.11).

## Interpretation

> **Our take:** the done-when holds: the method runs on the T12 replay and its long-run wrong-commit rate is reported with intervals next to `aci`. On real data the bandit controller is `aci` plus an audit: the commits are identical, so the rate bound is the same and it holds with shown-only feedback. The real gains are (1) an honest statement of why this is valid (only commit labels are needed), (2) an unbiased, anytime-valid audit of other thresholds, which the naive shown-only estimate is not (bias up to -0.235), and (3) a written scope. The audit is wide at ε 0.05: each withheld item adds 1/ε to its variance term. So `rule="max"` never helps on these weak decoders. For P15-03 champion / challenger under shown-only feedback, the audit (IPW) is the right tool for the counterfactual risk of a challenger; it needs a stronger decoder and more items to have power.

## Limits
- One fixed stream per set (time order); the 200 seeds vary only the exploration and the notice coins.
- Items are held-out trials of a frozen decoder: no decoder update happens in this replay (the update loop is P15-02 / P15-03).
- The simulated user always gives the label of an explored offer, and no `p_sloppy` noise.
- Start threshold 0.3 (the P14-03 value). The certificate slack depends on it.

## Rerun after the G3 review fixes (2026-11-16)

The [G3 audit review](../../wiki/questions/g3-audit-review.md) found issues H1, M1 and L4. The fixes changed `bandit_risk.py`: the audit now adds each item at decide time (H1), the default seed is None (M1), and items with s = −inf (the policy forbids COMMIT) are never explored (L4). The replay passes an explicit seed per run, so M1 does not change it. We ran the replay again with the same command (CPU, 26.5 s). The original numbers above stay as they were.

- **Changed:** only `explored_median` (the user cost of exploration). It is lower because forbidden items are no longer offered. T12: B05 18 → 16 (q 1.0 and 0.9); B20 73 → 68 and 72.5 → 67; E_max 80 → 75; P_bandit 19 → 17.5. T15: B05 32 → 31 and 32 → 30.5; B20 129 → 124 and 128.5 → 123; E_max 139 → 133; P_bandit 35 → 33.
- **Not changed:** every rate, commit count, certificate, CP95 interval, audit violation fraction (still 0.0) and bias value. The coin stream is the same (one coin per withheld item, also for forbidden items), and in this replay each item is fed back before the next decision, so the H1 accounting gives the same sums.

## Note: replay through the drop-in API (P5-11, 2026-11-17)

[P5-11](../2026-11-16-p5-11-online-replay/results.md) replayed the same items through `guard.online(...)`. Commits, wrong commits and rates are identical (`floor=False`). One number above does not carry over: the drop-in guard passes `offered=True` for items that the policy offers anyway, and on T12 / T15 every no-commit item is offered or has no commit score. So the drop-in bandit explores 0 items; the "user cost of exploration" above (median 16 on T12, 31 on T15 at ε 0.05) comes from driving the controller with `offered=False`. The numbers above stay as they were.
