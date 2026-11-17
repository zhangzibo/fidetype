---
title: P5-11 replay the online guards on T12 / T15 through the drop-in API - results
type: experiment
task: P5-11
updated: 2026-11-17
---

# P5-11: online guards through `guard.online(...)` on T12 / T15 (results)

[Plan](plan.md) (committed in `3def17e` before the run). Script: [replay.py](replay.py) (CPU, background class; T12 5.5 min, T15 13.5 min, most of it the rebuild of the base guard and the first decode). Aggregates: [results/summary.json](results/summary.json). Per-item outputs (commit, wrong, threshold; no text): `C:/Users/zhang/bci-data/derived/p5-11-online-replay/`. Reference: [P15-04 results](../2026-11-16-p15-04-bandit/results.md) (controllers driven directly).

## Outcome

| id | criterion | T12 (400) | T15 (701) |
|---|---|---|---|
| **O1** | rebuilt base guard has the P5-02 `config_id` | **pass** `tcfg-bd955c64a9cd7966` | **pass** `tcfg-7ecd016879246eb6` |
| **O2** | commit score and "wrong" of each item equal the P5-02 per-item file | **pass** 400 / 400 and 400 / 400 (max score difference 0.0) | **pass** 701 / 701 and 701 / 701 |
| **O3** | A q1.0, A q0.9, B05 (every seed) give the P15-04 commits / wrong | **pass** | **pass** |

The drop-in surface reproduces the P15-04 long-run wrong-commit numbers exactly. The differences below are all explained, and the per-item outputs confirm them.

## Long-run wrong-commit numbers (time order, alpha 0.05, eta 0.05)

| Arm (drop-in call) | T12 drop-in | T12 P15-04 | T15 drop-in | T15 P15-04 |
|---|---|---|---|---|
| A `online("aci", floor=False, lam_init=0.3)`, q 1.0 | 35 / 20, 0.0500 [0.0308, 0.0762] | 35 / 20, 0.0500 | 48 / 33, 0.0471 [0.0326, 0.0655] | 48 / 33, 0.0471 |
| A, q 0.9 (true; observed) | 37 / 22, 0.0550 (0.0500) | 37 / 22, 0.0550 (0.0500) | 55 / 39, 0.0556 (0.0456) | 55 / 39, 0.0556 (0.0456) |
| B05 `online("bandit", explore=0.05, floor=False, lam_init=0.3, seed=s)`, 20 seeds | 35 / 20 in 20 / 20 seeds; same commits as A in 20 / 20 | 35 / 20 (200 seeds) | 48 / 33 in 20 / 20; same as A in 20 / 20 | 48 / 33 |
| Precision bandit, target 0.5 (report only), median of 20 seeds | 7 commits, error 0.857 | 7, 0.857 | 2, 1.000 | 2, 1.000 |
| `online("window", floor=False, lam_init=0.3)`, full feedback (report only) | 27 / 17, 0.0425 | 28 / 18, 0.0450 | 42 / 27, 0.0385 | 42 / 27, 0.0385 |
| **A floor** `online("aci")` (drop-in default) | 19 / 11, 0.0275 [0.0138, 0.0487] | - | 2 / 2, 0.0029 [0.0003, 0.0103] | - |
| **B05 floor** `online("bandit", explore=0.05, seed=0)` | 19 / 11 | - | 2 / 2 | - |

The (G1) certificate equals the observed rate in every A / B05 run (an identity, as in P15-04). Floor arms: certificate 0.0521 (T12) and 0.0500 (T15).

## Differences and their causes

1. **The offline floor (default `floor=True`).** The drop-in default keeps the online threshold at or above the offline `commit_p` (0.3 on both sets). P15-04 had no floor, and ACI lowered the threshold below 0.3. With the floor the online guard commits a subset of the offline commits: 19 of 35 on T12 and 2 of 48 on T15. This is the intended trade (the offline sheet still holds), and on these weak decoders it costs most commits. With `floor=False` the numbers are those of P15-04.
2. **Exploration count (bandit).** The drop-in guard explored 0 items in every run; P15-04 explored a median of 16 (T12) and 31 (T15). `OnlineGuard` passes `offered=True` when the policy shows the item as an OFFER anyway (propensity 1, no coin). On T12 and T15 every item that is not committed is either offered by the policy or has no commit score (s = -inf; never explored since the L4 fix), so no coin is used. Offered items are labelled with propensity 1. P15-04 drove the controller with `offered=False`, so it treated these items as withheld and spent coins on them. Commits do not change (exploration never commits). So the "user cost of exploration" in the P15-04 results (16 / 31 extra offers at ε 0.05) does not exist through the drop-in API on these sets: those items are offers anyway.
3. **Window warm start (T12 only).** P15-04 gave the window controller a one-item warm start (`fit([0.3 + 1e-9], [0.0])`); the drop-in call has none. Driving the controller directly on the P5-02 items without the warm start gives 27 / 17 on T12, the drop-in number; with it, 28 / 18. On T15 both give 42 / 27.

No other difference: scores, "wrong" flags, ACI thresholds and commits are the same item for item.

> **Our take:** P5-11 closes: the drop-in API is a faithful wrapper of the controllers. Two points matter for users. (a) The default floor is safe but, with a weak decoder, takes away most of the gain of the online threshold; `floor=False` gives the any-sequence ACI bound only (the offline sheet no longer applies). (b) With the drop-in guard, the bandit audit costs nothing extra when the policy offers the no-commit items; the coins matter only for items the policy withholds (ABSTAIN / ASK) that still have a commit score.

## Limits
- One fixed stream per set (time order). 20 seeds here, not 200 (the commits were identical in all 20, as in P15-04's 200).
- Held-out trials of a frozen decoder; no decoder update.
- The simulated user always gives the final text (q 1.0), or misses a wrong commit with probability 0.1 (q 0.9).
