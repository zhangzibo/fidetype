---
title: "Frontier write-up F1: online risk control with shown-only (bandit) feedback"
type: question
tags: [frontier, f1, online-risk, bandit-feedback, aci, ipw, audit, review, write-up, pre-registration]
sources: [adaptive-conformal-inference, ocp-corrupted-feedback, decaying-step-ocp]
updated: 2026-11-24
---

# F1: does the wrong-commit bound hold when the user gives feedback only on what was shown?

Write-up for roadmap item [P15-12](roadmap-standard.md#p15-12-frontier-result-write-ups). It covers P15-04 (method and replay), the independent G3 proof review and its fixes (P15-17), and the drop-in replay P5-11. Pillar F1 of the [north star](north-star.md#f1-safe-self-improving-bci-e2).

## Question
A real user labels only what the system showed (a commit or an offer). The truth of a withheld item stays unknown. Which online bounds stay valid with this "bandit" feedback? Can we audit other thresholds without bias?

## Short answer
- **The existing `aci` bound is already valid with shown-only feedback** for the marginal and precision forms (G1, G2): it needs only commit labels.
- **New: an anytime-valid audit (G3)** of every grid threshold, with forced exploration shown as an OFFER (never a commit) and IPW. Audit violations: 0 / 200 seeds on T12 and T15.
- **The naive shown-only estimate is biased** (optimistic by up to 0.235 on T12). The IPW estimate is within about one standard error.
- **An independent review found one high issue** (late or lost feedback could break G3). It is fixed (`98daec3`). We claim **no new theorem**; the tools are standard and cited.
- **Negative results:** the precision target 0.5 is not reached on these weak decoders (2-7 commits); the `rule="max"` controller never helps here.

## Pre-registration and design
- [Plan](../../experiments/2026-11-16-p15-04-bandit/plan.md), commit `d90a49b`, before the run. Script `replay.py` (CPU, 27 s, no decoding). Inputs: the P5-02 per-item files of T12 (400) and T15 (701), read only.
- Arms: A `aci` (existing); B05 / B20 `bandit-aci` with exploration ε 0.05 / 0.20; C window CRC with oracle labels (not deployable); D window CRC with shown-only labels; E `bandit-max`. Alpha 0.05, start threshold 0.3, 200 seeds for the coins.
- Scope statement: [F1 guarantee scope](f1-guarantee-scope.md).

## Verdicts

| check | T12 (400) | T15 (701) | verdict |
|---|---|---|---|
| R1 realised rate <= certificate, every run | 100 % | 100 % | **pass** |
| R2 long-run true wrong-commit rate, B05 vs `aci` | 0.0500 [CP95 0.0308, 0.0762] vs 0.0500 (same 35 commits, 20 wrong) | 0.0471 [0.0326, 0.0655] vs 0.0471 (same 48 commits, 33 wrong) | **reported** (done-when) |
| R3 audit (G3) violations over 200 seeds | 0 / 200 (B05, B20) | 0 / 200 (B05, B20) | **pass** |
| R4 naive bias < 0 at >= 2 of 3 thresholds, IPW smaller | 3 of 3 | 2 of 3 | **pass** |
| R5 silent errors (q_notice 0.9): true >= observed | gap mean 0.0057 | gap mean 0.0054 | **pass** (gap reported, not covered) |

- The bound fixed in advance, `alpha + (score_max - lam_1 + eta) / (eta T)`, is 0.0875 (T12) and 0.0714 (T15). The realised rates are below both.
- With random orders (200 permutations), 17 % of T12 orders end above 0.05 (at most 0.0550), inside the bound fixed in advance. On T15: 0 %.

**Negative results.**
- D (window CRC with shown-only labels) never commits: it never gets the labels it needs to start.
- E (`rule="max"`) commits 0 times on T12 and 2 times on T15: the audit cannot certify a threshold with these decoders and this few labels.
- Precision target 0.5 (report only): P-bandit makes 7 commits (error 0.857) on T12 and 2 (error 1.000) on T15. At 2-7 commits no precision claim is possible.

## The G3 review (P15-17)
- Review by a fresh agent: [G3 audit review](g3-audit-review.md), commit `4cd9cb5`. Verdict: **sound with fixes**. The mathematics is correct if every decided item is fed back in decision order.
- **H1 (high):** the code added an item to the audit only at feedback time. With delayed or lost feedback the set in the sum depends on the coins, and the bound can fail.
- **M1:** default `seed=0` made the coins a fixed public sequence. **M2:** the tests had low power (they still passed with half the slack).
- **Fixes (commit `98daec3`, review section `2e4e38d`):** each item enters the audit at decide time (shown items count as wrong until the label arrives); default `seed=None`; stronger tests (single threshold at δ 0.5, coin-adaptive adversary, `rule="cs"`, random lag, never-returned feedback with the old accounting as a negative control: failure 1.00, new 0.00); never explore items with s = −inf.
- **Rerun after the fixes:** only the exploration count changed (lower, for example T12 B05 18 → 16). Every rate, certificate, interval and audit result is the same.

## P5-11: the same controllers through the drop-in API
- [Results](../../experiments/2026-11-16-p5-11-online-replay/results.md), plan in commit `3def17e`. O1-O3 pass: `guard.online(...)` with `floor=False` reproduces the P15-04 commits and rates exactly on T12 and T15.
- **Cost of the default floor:** with `floor=True` (default) the online threshold stays at or above the offline `commit_p`. The guard then commits 19 of 35 (T12) and 2 of 48 (T15) of the P15-04 commits. Safe, but on these decoders it removes most of the gain.
- The drop-in bandit explores 0 items on T12 / T15, because the policy offers every no-commit item anyway (propensity 1). So the P15-04 "user cost of exploration" applies only to items the policy withholds.

## What changed in the library
| change | commit |
|---|---|
| new module `fidetype.trust.bandit_risk` (`BanditCommitRiskControl`, `BanditTrustPolicy`); guarantee-sheet entries | P15-04 (`4860e51`, plan `d90a49b`) |
| decide-time audit accounting, `seed=None`, no exploration of forbidden items, floored audit rows marked, assumptions in docs and sheet | `98daec3` |
| `guard.online("aci" / "bandit" / "window", ...)` on the drop-in guard | P5-11 (`3def17e`, results `9277177`) |

## Limits
- One fixed stream per set; the seeds vary only the coins. No decoder update happens in this replay.
- Weak decoders (error among the `aci` commits: T12 20 / 35, T15 33 / 48), so the bounds are valid but not yet useful.
- The simulated user always labels an explored offer; no sloppy labels.
- Silent errors are outside every bound.

> **Our take:** on real data the bandit controller is `aci` plus an audit. The value is an honest statement of why the bound holds with shown-only feedback, and an unbiased audit for counterfactual thresholds. The audit is the right tool for a champion / challenger check under shown-only feedback, but it needs a stronger decoder and more items to have power.

## Still open
- Usefulness on stronger decoders: gap 14, [P15-19](roadmap-standard.md#p15-19-show-usefulness-on-stronger-decoders-p5-01-p15-02-p5-02-p15-06).
- Online re-calibration for a learned commit score: gap 73, [P5-25](roadmap-standard.md#p5-25-online-re-calibration-for-a-guard-with-a-learned-commit-score).
- An outside human review of G3 would be a separate, externally blocked step (open-gaps note on gap 6).

Related theory found 2026-11-24: [OCP with corrupted feedback](../sources/ocp-corrupted-feedback.md) (silent errors as flipped feedback) and [decaying step sizes](../sources/decaying-step-ocp.md) (per-time coverage on stable data; a candidate descriptive controller for a CPU replay).

## Rerun
`.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-16-p15-04-bandit/replay.py` (needs the local P5-02 per-item files). P5-11: `experiments/2026-11-16-p5-11-online-replay/replay.py`.

## Related pages
[E2 self-teaching write-up](frontier-e2-self-teaching.md), [F1 guarantee scope](f1-guarantee-scope.md), [G3 audit review](g3-audit-review.md), [adaptive conformal inference](../sources/adaptive-conformal-inference.md), [north star](north-star.md).
