---
title: P5-11 replay the online guards on T12 / T15 through the drop-in API - plan
type: experiment
task: P5-11
updated: 2026-11-16
---

# P5-11: online guards through `guard.online(...)` on T12 / T15 (plan)

Written and committed **before** the replay runs. Roadmap item: [P5-11](../../wiki/questions/roadmap-standard.md#p5-11-replay-the-online-guards-on-t12--t15-through-the-drop-in-api). Gap 15 of the [open-gap list](../../wiki/questions/open-gaps.md). Reference numbers: [P15-04 results](../2026-11-16-p15-04-bandit/results.md) (controllers driven directly on the P5-02 per-item scores).

## Question
Does the drop-in surface (`TrustGuard.online(method, ...)`, `src/fidetype/trust/online_guard.py`, after the 98daec3 fixes) give the same long-run wrong-commit numbers as the P15-04 replay, which drove the controllers directly? If not, why?

## Inputs (read only, CPU, no GPU)
- Held-out items and calibration items: the P14-03 loaders and `decode_fn`, exactly as P5-02 `run.py` uses them (T12: 480 calibration, 400 held out; T15: 722 / 701).
- The base guard: `ft.calibrate(...)` with the P5-02 arguments (seed 0). Check: its `config_id` equals the P5-02 base (`tcfg-bd955c64a9cd7966` T12, `tcfg-7ecd016879246eb6` T15).
- Item-level check: the P5-02 per-item files `C:/Users/zhang/bci-data/derived/p5-02-precision/items-*.json` (commit score and "wrong" per item; the P15-04 input).
- Outputs: `C:/Users/zhang/bci-data/derived/p5-11-online-replay/` (per-item commit / wrong / threshold, no text) and `results/summary.json` (aggregates).

## Arms (time order, alpha 0.05, eta 0.05)
| Arm | Call | P15-04 counterpart |
|---|---|---|
| A q1.0 | `guard.online("aci", floor=False, lam_init=0.3)` | A `aci`, q 1.0 |
| A q0.9 | same; a wrong commit is noticed with probability 0.9 (P15-04 notice coins, seed 0); an unnoticed one is fed back as the committed text | A `aci`, q 0.9 |
| A floor | `guard.online("aci")` (drop-in default: floor = offline `commit_p` 0.3, start 0.3) | none (shows the floor) |
| B05 | `guard.online("bandit", explore=0.05, floor=False, lam_init=0.3, seed=s)`, 20 seeds | B05, q 1.0 (200 seeds) |
| B05 floor | `guard.online("bandit", explore=0.05, seed=0)` | none |
| report only | precision bandit (target 0.5), `"window"` with full feedback | P_bandit, C `window-full` |

## Pass rules
- **O1 (base):** the rebuilt base guard has the P5-02 `config_id` on both sets.
- **O2 (items):** the commit score (`p_top1` if the guard may commit, else -inf) and the "wrong" flag of every held-out item equal the P5-02 per-item file.
- **O3 (numbers):** A q1.0, A q0.9 and B05 (every seed) give the P15-04 commits and wrong commits on both sets (T12: 35 / 20, 37 / 22, 35 / 20; T15: 48 / 33, 55 / 39, 48 / 33). B05 has the same commits as A in every seed.
- Any difference is explained item by item (for example the offline floor, the `offered` flag of the bandit, the OFFER_WORDS fallback loss, or the window warm start). The item closes if O1 to O3 pass, or if each difference has an explanation that the per-item outputs confirm.

## Expected differences (written down now)
- **Floor:** with the default `floor=True`, ACI cannot go below 0.3. P15-04 had no floor. The floor arms can only commit a subset.
- **Exploration count:** `OnlineGuard` passes `offered=True` when the policy OFFERs the item anyway (propensity 1, no coin). P15-04 called the controller with `offered=False`. So `explored` can differ; commits should not.
- **Window:** P15-04 gave the window controller a tiny warm start (`fit`); the drop-in call has none. Report only.
