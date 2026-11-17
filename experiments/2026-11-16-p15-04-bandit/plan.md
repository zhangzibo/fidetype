---
title: P15-04 bandit-feedback online risk control - replay plan
type: experiment
task: P15-04
updated: 2026-11-16
---

# P15-04: online risk control with shown-only feedback, replay on T12 and T15 (plan)

Written and committed **before** any replay run. Code: `src/fidetype/trust/bandit_risk.py` (new), tests `tests/test_trust_bandit_risk.py`. Scope of the guarantee: [f1-guarantee-scope](../../wiki/questions/f1-guarantee-scope.md).

## Question
In real use the user labels only what the system SHOWED (a commit or an offer). Does the new controller keep its stated bound on real decoder outputs, and how large is the bias of a "naive" controller that uses the shown items as if they were a random sample?

## Data (read only, no new decoding)
- T12: `C:/Users/zhang/bci-data/derived/p5-02-precision/items-t12.json` (400 held-out trials of P14-03 / P5-02, time order: session, then trial).
- T15: `.../items-t15.json` (701 held-out trials, same order rule).
- Per item: `p_top1`, `can_commit` (all other commit rules pass at commit_p 0), `wrong` (top-1 text not exactly the truth). Score `s = p_top1` if `can_commit` else `-inf`; `c = wrong`.
- Outputs per run go only to `C:/Users/zhang/bci-data/derived/p15-04-bandit/`. The repository gets aggregates only.

## Simulated user (fixed now)
- Wrong commit: corrected with probability `q_notice` in {1.0, 0.9}. Uncorrected = **silent error**: the controller sees `c = 0`. Right commit: no correction (`c = 0`).
- Shown non-commit (exploration offer): the user picks or retypes, so the true `c` arrives (no silent errors here).
- Withheld item: no label.

## Arms (fixed now; alpha = 0.05 marginal, delta = 0.1, eta = 0.05, start threshold 0.3 = the P14-03 calibrated `commit_p` of both sets, grid 0.00..1.00 step 0.01)
| Arm | Controller | Feedback it uses |
|---|---|---|
| A `aci` | `OnlineCommitRiskControl(method="aci")` (existing) | realised loss (shown-only by nature) |
| B05 / B20 `bandit-aci` | `BanditCommitRiskControl(target="marginal", rule="aci", explore=0.05 / 0.20)` | shown only + exploration offers |
| C `window-full` | `OnlineCommitRiskControl(method="window", window=200)` with every truth | full feedback (oracle, not deployable) |
| D `window-naive` | same, but truth only for commits (`None` for withheld) | shown only, no weights |
| E `bandit-max` | `BanditCommitRiskControl(rule="max", explore=0.20)` | shown + exploration |
| P-bandit | `BanditCommitRiskControl(target="precision", alpha=0.5, rule="aci", explore=0.05)` | shown + exploration |
| P-naive | `NaiveShownOnlyControl(target="precision", alpha=0.5, lam_init=0.3)` | shown only |

## Orders and seeds
1. **Time order** (one stream per set): 200 exploration seeds (0..199) per arm with exploration; one run otherwise. `q_notice` 0.9 uses seed-matched notice coins.
2. **Random orders** (exchangeable check): 200 random permutations (seed 10000 + i), same arms, `q_notice` = 1.0, exploration seed = i.

## Measures
- Realised long-run wrong-commit rate per item: observed (what the controller sees) and true (including silent errors), with CP95 intervals (time order; for seeded arms: the median-seed run and the range over seeds).
- Commits, wrong commits, the (G1) / (G2) certificate, explored items (user cost).
- Audit (G3): fraction of seeds where the upper bound is below the true counterfactual wrong-commit count at ANY grid threshold, at the end of the stream.
- Bias at thresholds 0.15, 0.20, 0.25 (below the running threshold for most of the stream): mean over seeds of (estimate - true) of the precision error, naive complete case vs IPW.
- Precision arms: error rate among commits and its certificate.

## Checks (fixed now)
- **R1** (implementation): in every run of A, B05, B20, E, observed realised rate <= certificate. Must hold in 100 % of runs.
- **R2** (done-when): long-run true wrong-commit rate of B05 on T12 (time order, q_notice 1.0) is reported with CP95 next to A. Expected: B05 commits are the same items as A (same ACI update, exploration never commits).
- **R3** audit coverage: violation fraction <= 0.1 + 3 SE (both sets, time order, B05 and B20).
- **R4** bias: naive mean bias < 0 (optimistic) at >= 2 of the 3 thresholds on each set; |IPW bias| < |naive bias| at the same thresholds.
- **R5** silent errors: with q_notice 0.9 the true rate >= the observed rate in every run; the gap is reported. It is never counted as covered.
- **R6** (report only, no pass rule): precision arms; random-order distribution of realised rates (fraction of permutations above alpha, per arm); `bandit-max` commits.

## Expected
- These decoders are weak (top-1 right 31 / 400 on T12, 59 / 701 on T15; the error rate among items with `p_top1 >= 0.3` is 0.6 on T12). The marginal bound at alpha 0.05 is still reachable by committing few items. The ACI certificate after 400 items has slack up to (1.05 - 0.3) / (0.05 * 400) = 0.0375, so a realised rate above 0.05 is possible and not a violation of (G1).
- `bandit-max` will likely never commit (too few labels to certify any threshold at these error rates). That is an honest "safe but costly" result.
- P-bandit (target precision 0.5) may commit few items; P-naive may overshoot the 0.5 error rate.
