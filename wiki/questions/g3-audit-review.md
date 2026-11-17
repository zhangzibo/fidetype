---
title: "G3 audit review: is the bandit IPW anytime bound valid as proved, coded, tested and stated?"
type: question
tags: [trust, risk-control, online, bandit-feedback, ipw, supermartingale, ville, review, f1, p15]
sources: []
updated: 2026-11-16
---

# G3 audit review (independent check, 2026-11-16)

**Review target.** The (G3) audit in `src/fidetype/trust/bandit_risk.py` (module docstring lines 38–96, `decide` lines 281–298, `observe` lines 304–344, `audit_upper` / `ipw_slack`), its tests in `tests/test_trust_bandit_risk.py`, the wrapper in `src/fidetype/trust/online_guard.py`, the scope page [F1 guarantee scope](f1-guarantee-scope.md) and [docs/trust-guarantee.md](../../docs/trust-guarantee.md) section 11.2. The reviewer did not change library code.

## Verdict: sound with fixes

The mathematics is correct **if every decided item is fed to `observe` in decision order before the next decision** (the way the tests and the replay use it). The supermartingale, the filtration, the δ split and the bet grid are all right. The code implements the formula exactly.

Two things are not right:

1. The API allows delayed and out-of-order feedback, and the statement "the items seen so far" then means "the items observed so far". That set depends on the coins. The bound can then fail with probability 1 (Monte Carlo below). This is the one **high** issue.
2. The default `seed=0` makes the "random" coins a fixed, public sequence. The probability statement then needs an extra assumption that the docs do not state.

The tests pass, but they have low power: they still pass when the slack is cut in half.

## What was checked and holds

| Step | Check | Result |
|---|---|---|
| Unbiasedness | π_t = 1 (commit or policy OFFER): the item is shown, ĉ ≥ c, so D_t = Y_t − X_t ≤ 0. π_t = ε: E[O_t]/ε = 1, ĉ ∈ {c, 1} ≥ c, so E[D_t \| past, s_t, c_t] ≤ 0 | holds |
| Increment bound | D_t ≤ Y_t ≤ 1 for c ∈ [0, 1]. Bets b ∈ (0, 1]. For x ≤ 1, e^{bx} ≤ 1 + bx + ψ(b)x² (the function (e^{bx} − 1 − bx)/x² increases in x). So E e^{bD} ≤ 1 + ψ(b) E D² ≤ exp(ψ(b) E D²) | holds |
| Variance proxy | E[D² \| ·] = c²(1/ε − 1) with a label; ≤ c² − 2c² + 1/ε with a missing label (ĉ = 1). Both ≤ 1[s ≥ λ]/π. The proxy uses only π_t and s_t, so it is predictable | holds (conservative) |
| Large lower jumps | D can be as low as 1 − 1/ε. This does not matter: the Bennett step needs only the upper bound D ≤ 1 | holds |
| Filtration | π_t depends on λ_t, which depends on past coins through the audit (`rule="cs"`/`"max"`) and on `offered`. Both are fixed before coin t. Data s_t, c_t may depend on past coins. Coin t is a fresh `rng.random() < π_t` | holds, in decision order |
| Union bound | One Ville event per (λ_k, b) at level δ/(K J); K = `grid` size, J = `bets` size (`ipw_slack` line 145). Taking min over b after the fact is valid because all K·J events hold at once | holds |
| Algebra | exp(bS − ψ(b)V) < KJ/δ ⇔ S < [ψ(b)V + log(KJ/δ)]/b | holds |
| Code ↔ formula | `_SX += above * c_hat / propensity` only for shown items; `_V += above / propensity` only for π < 1; withheld labels are ignored (line 316); missing label on a shown item → ĉ = 1 (line 319); `rng.random() < pi` gives probability π exactly; `explore = 0` gives inf where V > 0 | matches, no off-by-one |

## Issues

| ID | Severity | Location | Issue | Suggested fix |
|---|---|---|---|---|
| H1 | **High** | `bandit_risk.py` `observe` lines 324–336 (audit sums updated at feedback time); class docstring lines 171–179 ("later, maybe out of order"); module docstring line 82 ("for every time t") | The proof indexes items by **decision** order and needs every decided item in the sum. The code adds an item only when `observe` is called. In normal use a withheld item is observed at once (no label to wait for), but an explored OFFER waits for the user. So at time t the set in the sum is selected **by the coin**: shown items (negative D) are missing, unshown items (positive D) are in. An item that is never observed (session ends, integration drops the ticket) is missing for ever. `rule="cs"` acts on this mid-run bound | Add each item to the audit at `decide` time: N, V and, for a shown item, X with provisional ĉ = 1. When the label arrives, lower X to the true ĉ. Because ĉ_provisional = 1 ≥ c, the sum always dominates the proved one (use D'_t with the true c_t, which is measurable at decision time). Alternatively: refuse `audit_upper` / `rule="cs"` while shown tickets are pending, and state "every decided item must be fed back" as an assumption in the docs and the sheet |
| M1 | Medium | `BanditCommitRiskControl.seed = 0` (line 196); `online(..., seed=0)` (`online_guard.py` line 197) | The guarantee is "probability ≥ 1 − δ over the exploration coins". With a fixed default seed every session draws the **same** coin sequence, and the repo is public. The statement then holds only if the data stream is independent of that fixed PRNG stream. Sessions that are pooled are not independent draws. An adversary who reads the code can predict every coin | Default `seed=None` (OS entropy) for live use; keep fixed seeds only in tests and replays. Add to the scope page and sheet: "coins must be unpredictable to whatever produces the data" |
| M2 | Medium | `tests/test_trust_bandit_risk.py` lines 105–131 | (a) Low power: with the same adversary, 120 runs and the same pass rule, a slack cut to 0.5× still passes (observed failure rate 0.008); the test fails only at about 0.3× (0.22). The test cannot see a factor-2 error. (b) The "adaptive adversary" uses `rc.threshold`. With `rule="aci"`, `target="marginal"`, λ_t moves only on commit losses, and commits do not depend on coins. So the adversary is **not** adaptive to the coins. (c) No test feeds back late or out of order (H1). (d) No test uses `rule="cs"`, where π_t really depends on past coins | Add: (1) a single-threshold, single-bet test (K = J = 1, δ about 0.3–0.5) where the true failure rate is not near 0, with enough runs to detect 2×; (2) a coin-adaptive adversary (c_t depends on whether the last withheld item was explored); (3) a `rule="cs"` run; (4) a delayed-feedback test that must fail before the H1 fix and pass after it; (5) a negative control: the naive estimator (no 1/π) must fail the same coverage check |
| L1 | Low | Module docstring lines 52–54, 86–91 | The proof sketch conditions on (past, s_t, c_t) but ĉ_t depends on label arrival, which happens **after** the coin and may depend on it. D_t is then not measurable at step t. The result is still true (use D'_t = c_t(1 − O_t/π_t) 1[s_t ≥ λ], which is measurable, and note X_t ≥ X'_t pointwise), but the sketch does not say so | Add one sentence: the supermartingale is built on the true c_t; the pessimistic ĉ only makes X larger |
| L2 | Low | `online_guard.py` lines 110–111 (`score < floor → -inf`) | With the default floor, the audit row for a grid λ below the offline `commit_p` is the bound for "commit iff p ≥ max(λ, floor)", not for threshold λ on the raw score. The rows below the floor are copies of the floor row. A reader of `report()["audit"]` can misread them | Mark grid points below the floor as `null` in the report and the sheet, or document the meaning |
| L3 | Low | `docs/trust-guarantee.md` line 234 (table row "Audit"); sheet assumptions in `guarantee_sheet.py` `sheet_from_bandit` | The docs row says "probability ≥ 1 − δ over the exploration coins" but lists only "`explore` > 0" as the need. It omits: coins unseen by the data source (M1), every decided item fed back (H1), labels not silent. The scope page row G3 states the first one; neither states the second | Add both conditions to the docs row, the scope page G3 row and the sheet `assumptions` |
| L4 | Low (efficiency) | `decide` lines 288–292 | Items with s = −inf (policy rules forbid COMMIT) are still explored at rate ε. They add 0 to every Y, X and V, so the offer costs user effort and gives the audit no information | Do not explore items with s = −inf (π = 0 is fine there: 1[s ≥ λ] = 0 for every grid λ) |
| L5 | Low (optional tightening) | `observe` line 332 | V uses 1/π. With a label the exact second moment is c²(1 − π)/π, so the bound is a little loose. With missing labels the 1/π form is the safe one | Optional. Keep 1/π unless a proof for (1 − π)/π with missing labels is written down |

**Claims in the scope page and docs.** "Any threshold" is always qualified as "any grid threshold" or "λ_k of a fixed grid": correct. "Anytime": correct in decision order with complete feedback (H1). "Adversarial, adaptive" (scope page, data table line 69): correct for data that cannot see coin t, but needs M1. "Future items not covered" and "silent errors not covered" are stated: correct. "We do not claim a new theorem": correct; the construction is the standard IPW + Bennett + Ville one.

## Monte Carlo probes

Scratch scripts outside the repo (not committed). Run with the repo `.venv`, CPU only.

| Probe | Setup | Result |
|---|---|---|
| A: coin-adaptive adversary, in order | K = J = 1, b = 0.25, δ = 0.2, ε = 0.1, 400 items all withheld; c_t = 1 unless the previous item was explored; 2,000 runs | failure rate 0.000 ≤ 0.2 (valid; the bound is conservative) |
| B1: shown items fed back with lag 50 | `BanditCommitRiskControl`, ε 0.05, λ fixed 0.6, every item below λ is wrong, 2,000 items, check every 100, 40 runs | failure rate 0.00 |
| B2: lag 500 | same | failure rate 0.00 |
| B3: shown items never fed back during the run (withheld fed at once) | same | **failure rate 1.00**; median worst excess of the true count over the bound: 482 wrong commits |
| C: power of the repo test | adversary and pass rule of `test_audit_upper_bound_holds_uniformly_in_time`, slack multiplied by f | f = 1.0: 0.000; f = 0.5: 0.008 (test passes); f = 0.3: 0.217; f = 0.2: 0.558 |

> **Our take:** moderate, coin-independent delays do not break the bound in practice, because the slack is wide. The failure in B3 is the realistic end-of-session case: offers that were explored and never confirmed. The H1 fix (account at decision time, pessimistic until the label arrives) is small and removes the issue fully. After H1 and M1, G3 is a correct, standard, design-based statement.

## Fixes applied (2026-11-16, commit 98daec3)

| ID | Fix | Where |
|---|---|---|
| H1 | The audit adds each item at `decide` time: N, V and, for a shown item, X with a provisional ĉ = 1. `observe` only lowers X to the label. The sum always contains every decided item in decision order, and each term is ≥ the proof term. `rule="cs"` uses this sum. New report field `n_decided` | `bandit_risk.py` `decide` / `observe` |
| M1 | Default `seed=None` (OS entropy) in `BanditCommitRiskControl` and `online(...)`. Fixed seeds stay for replays and tests. Docstrings: "coins must be unpredictable to the data source". The P15-04 replay already passes `seed=seed` per run, so it reproduces | `bandit_risk.py`, `online_guard.py` |
| M2 | New tests: K = J = 1, δ 0.5 (failure rate about 0.33; fails if the slack is halved, checked by mutation); coin-adaptive adversary; `rule="cs"` uniform-in-time run (60 runs); random lag up to 300, out of order; never-returned feedback (old accounting as negative control: failure 1.00, new: 0.00); naive count without 1/π as negative control (fails > 95 %) | `tests/test_trust_bandit_risk.py` |
| L1 | Module docstring: "Why late labels are safe" (supermartingale on D′ with the true c; X ≥ X′ pointwise) | `bandit_risk.py` |
| L2 | `OnlineGuard.report()["audit"]` marks rows with grid λ < floor in `floored` and sets their numbers to None; the sheet says so | `online_guard.py`, `guarantee_sheet.py` |
| L3 | Both conditions (unpredictable coins; every decided item in the audit) in the docs row, the scope page G3 row and the bandit sheet `assumptions` | `docs/trust-guarantee.md`, [F1 guarantee scope](f1-guarantee-scope.md), `guarantee_sheet.py` |
| L4 | Items with s = −inf get π = 0 and are never explored. One coin is still drawn per withheld item, so the coin stream does not depend on the scores | `bandit_risk.py` `decide` |
| L5 | Not done (optional). V keeps 1/π | — |

**P15-04 replay rerun.** Only `explored_median` changed (lower, because of L4; for example T12 B05 18 → 16, T15 B20 129 → 124). Every rate, certificate, interval, audit violation fraction and bias is the same. Dated note in [P15-04 results](../../experiments/2026-11-16-p15-04-bandit/results.md).

## Related pages
- [F1 guarantee scope](f1-guarantee-scope.md) (the statement under review)
- [docs/trust-guarantee.md section 11.2](../../docs/trust-guarantee.md)
- [P15-04 results](../../experiments/2026-11-16-p15-04-bandit/results.md)
- [ACI](../concepts/adaptive-conformal-inference.md)
