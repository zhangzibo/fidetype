---
title: "F1 guarantee scope: what the online wrong-commit bound covers with shown-only feedback, and what it does not"
type: question
tags: [trust, risk-control, online, bandit-feedback, aci, guarantee, silent-errors, f1, p15]
sources: [adaptive-conformal-inference, rolling-risk-control, conformal-risk-control, conformal-beyond-exchangeability, ocp-corrupted-feedback, decaying-step-ocp, card-2026-home-use, hou-error-encoding]
updated: 2026-11-24
---

# F1 guarantee scope (P15-04)

**Short answer.** With shown-only feedback, Fidetype gives two kinds of statement. (1) A **long-run bound on the realised wrong-commit rate** of the running system. It holds for any sequence of inputs, also under drift and decoder updates, and it needs no exploration. (2) An **audit bound** on the wrong commits that *another* threshold would have made on the same items. It holds with probability ≥ 1 − δ over a random exploration that Fidetype draws itself. Neither statement covers **silent errors** (wrong text that the user never corrects), and neither is a statement about one short session.

Code: `fidetype.trust.bandit_risk` (`BanditCommitRiskControl`, `BanditTrustPolicy`). Replay: [P15-04 results](../../experiments/2026-11-16-p15-04-bandit/results.md). North star: [F1](north-star.md#f1-safe-self-improving-bci-e2).

## The feedback problem

| Action | Shown to the user? | What the system learns |
|---|---|---|
| COMMIT | yes (inserted) | wrong: the user corrects it (if the user notices); right: no correction |
| OFFER (policy) | yes (list) | the pick or the retyped text = the truth |
| OFFER (exploration, rate ε) | yes (list) | the truth; nothing is inserted without the user's confirmation |
| ASK / ABSTAIN | no | nothing |

The truth arrives only for shown items. This is *semi-bandit* feedback: the label is seen only if it is inside what the system showed (Ge, Bastani & Bastani 2024, arXiv:2405.13268; Yang, Kim & Park 2026, arXiv:2604.17984, "OCP-Unlock+"-type setting cited in the [north star](north-star.md#what-the-sources-say-abstract-level)).

The shown items are not a random sample: they are the high-score ones. A "naive" estimator that uses them as if they were random is **optimistic** for any threshold below the current one. On the T12 / T15 replays and on synthetic streams it under-estimates the error rate among commits at lower thresholds ([results](../../experiments/2026-11-16-p15-04-bandit/results.md)). A naive controller that acts on it overshoots its precision target (synthetic: mean error 0.11 for a target of 0.10).

## Replay evidence (P15-04, pre-registered)

| Set (held out, time order) | `aci` = bandit (ε 0.05) long-run wrong-commit [CP95] | bound fixed in advance | audit violations | naive bias at λ 0.15 (IPW) | true rate with q_notice 0.9 |
|---|---|---|---|---|---|
| T12 (400) | 0.0500 [0.0308, 0.0762], 35 commits | 0.0875 | 0 / 200 | −0.235 (−0.022) | 0.0550 (observed 0.0500) |
| T15 (701) | 0.0471 [0.0326, 0.0655], 48 commits | 0.0714 | 0 / 200 | −0.109 (−0.013) | 0.0556 (observed 0.0456) |

Source: [P15-04 results](../../experiments/2026-11-16-p15-04-bandit/results.md).

## What is guaranteed

Notation: score `s_t`, top-1 error `c_t` ∈ {0, 1}, threshold `λ_t`, commit iff `s_t ≥ λ_t`, wrong-commit loss `L_t = c_t · 1[commit]`. Step size η. Start threshold λ₁.

| ID | Statement | Assumptions | Type |
|---|---|---|---|
| **G1** marginal | `(1/T) Σ L_t ≤ α + (λ_{T+1} − λ₁)/(η T)`; λ stays ≤ `score_max + η(1 + d)` (d = feedback delay), so the slack is O(1/(ηT)) | none on the data (any sequence, adversarial, drift, decoder updates); each commit gets its observed label; a commit with no label counts as wrong | deterministic, long-run |
| **G2** precision | `(wrong commits)/N_c ≤ α_p + (λ_{T+1} − λ₁)/(η N_c)`, λ updated only at commits | same as G1 | deterministic, long-run, per commit |
| **G3** audit | for all thresholds λ_k of a fixed grid (K points) and all times t at once, with probability ≥ 1 − δ: `Σ_{i≤t} c_i 1[s_i ≥ λ_k] ≤ Σ X_i(λ_k) + min_b [ψ(b) V_t(λ_k) + log(KJ/δ)]/b` | exploration rate ε > 0 is known and drawn by Fidetype after `s_t`, `c_t` are fixed; the sequence may be adaptive but does not see the coin; the coins are unpredictable to whatever produces the data (default `seed=None`, OS entropy; fixed seeds only for replays and tests); every decided item is in the sum, in decision order (the code adds it at decide time and counts a shown item as wrong until its label arrives); a shown item with no label counts as wrong | probabilistic over the exploration coins only (design-based) |

- G1 is the existing `aci` controller ([ACI](../concepts/adaptive-conformal-inference.md); [rolling risk control](../sources/rolling-risk-control.md)). Its proof sums the updates. It needs only the realised loss, and shown-only feedback gives the realised loss exactly: a commit is shown, and a non-commit has wrong-commit loss 0. So **ACI is already valid under bandit feedback**. The new code adds G2, G3 and the exploration.
- In G3, `X_i(λ) = O_i ĉ_i 1[s_i ≥ λ] / π_i` is the inverse-propensity term (π_i = 1 for a commit or a policy OFFER, else ε), `V_t(λ) = Σ_{π_i<1} 1[s_i ≥ λ]/π_i`, `ψ(b) = e^b − 1 − b`, and b runs over J = 12 fixed bets. The proof: Bennett's lemma for increments ≤ 1, Ville's inequality, a union bound over (λ_k, b). The tools are standard (Freedman 1975; the off-policy confidence sequences of Karampatziakis, Mineiro & Ramdas 2021, arXiv:2102.09540, and Waudby-Smith et al. 2022, arXiv:2210.10768). **We do not claim a new theorem.**
- G3 divided by the known count `N_t(λ_k) = Σ 1[s_i ≥ λ_k]` bounds the counterfactual error rate among commits at λ_k.
- `rule="max"` uses `max(λ_ACI, λ_audit)`. It keeps G1 / G2: the ACI identity holds for any decisions, and above `score_max` nothing commits.

## What is NOT guaranteed

| Not covered | Why | What we do instead |
|---|---|---|
| **Silent errors** (a wrong commit that the user does not correct) | It looks like a right commit. Every statement above is about **observed** labels | Report silent errors separately; simulate `q_notice` < 1 ([north star risks](north-star.md#honest-risks)). Replay: with `q_notice` 0.9 the true rate is above the observed rate |
| **One session or one short window** | G1 / G2 are long-run averages; the slack term is large for small T (T = 400, η = 0.05: up to 0.0375) | [Per-session risk control](per-session-risk-control.md) (LTT on a warm-up), the session e-process monitor |
| **Future items** (G3) | G3 is about the items already seen. It predicts the future only if the future is like the past (exchangeable / stationary) | Use G3 to audit and to gate a change; use G1 for the forward guarantee |
| **A rate at a fixed time with a fixed probability** (offline LTT type) | G1 is deterministic for the realised sequence, not a (1 − δ) statement about a population | Offline LTT / CRC at calibration ([drop-in wrapper](roadmap-standard.md#p14-03-trust-layer-as-a-drop-in-wrapper)) |
| **Labels from withheld items without exploration** | With ε = 0 there is no unbiased information below the threshold; G3 is infinite there | Exploration offers at rate ε; the user cost is ε × (withheld items) extra offers |
| **A user whose intended text changes because of what was shown** | G3 assumes `c_t` is fixed before the coin | Not testable in replay; note for live studies |
| **Wrong labels** (the user accepts a wrong offer: `p_sloppy`) | The label itself is wrong | Measured in the P15-01 simulator, not bounded |
| **Fluent-wrong LLM text** | A different loss | [P15-06](roadmap-standard.md#p15-06-risk-controlled-hallucination-bound) |

> **Theory for the silent-error row (2026-11-24):** [Wang, Zecchin & Simeone 2026](../sources/ocp-corrupted-feedback.md) show that flipped feedback adds a miscoverage term linear in the flip rate (2p for i.i.d. flips), which does not shrink with T. Our flips are one-sided (a missed wrong commit reads as right), so E[observed] = q · E[true] with q = `q_notice`; when ACI binds, the true rate tends to α / q (our arithmetic). Fixes: a target α · q̂ with a lower bound q̂ on the noticing rate, or explicit per-sentence ratings as in [Card et al. 2026](../sources/card-2026-home-use.md) (q close to 1), or later neural error signals ([Hou et al. 2025](../sources/hou-error-encoding.md)). For the "one session" row, a decaying step size gives near-target coverage at each time on stable data ([Angelopoulos, Barber & Bates 2024](../sources/decaying-step-ocp.md)).

## Exchangeable vs adversarial data

| Data | G1 / G2 | G3 | `rule="cs"` threshold |
|---|---|---|---|
| Adversarial, adaptive, drift, decoder updates | holds | holds (randomness = exploration only) | the threshold was certified on the past; no forward guarantee |
| Exchangeable / stationary | holds | holds | the past bound also predicts the future (approximately) |

> **Our take:** the claim that F1 can make is narrow and honest: "for the text that the user saw and checked, the long-run rate of wrong inserted text stays at or under α plus a stated slack, for any sequence, through every decoder update". The public wording must add "silent errors are measured, not bounded". The audit bound G3 is the tool for a fair champion / challenger comparison under shown-only feedback, but at ε = 0.05 it is wide: each withheld item adds 1/ε to the variance term. On the weak T12 / T15 decoders `rule="max"` never commits.

## On the drop-in API (P5-02)
Since P5-02, the same controllers run behind the drop-in guard: `guard.online("aci" | "aci_window" | "window" | "bandit")` ([docs section 11](../../docs/trust-guarantee.md)). Each online policy also has a uniform guarantee sheet (`policy_type` `online_*` or `bandit`, [docs section 12](../../docs/trust-guarantee.md)) that states the statement, the feedback it needs and what is NOT guaranteed (silent errors, one short session). Code: `src/fidetype/trust/online_guard.py`, `src/fidetype/trust/guarantee_sheet.py`.

## Independent review of G3 (2026-11-16)
An independent review checked the G3 proof, code, tests and wording: [G3 audit review](g3-audit-review.md). Verdict: sound with fixes. The bound needs every decided item in the sum in decision order (in the old code, delayed or lost feedback for explored offers broke it) and unpredictable exploration coins (the old default `seed=0` was fixed). Both are now fixed in the code (2026-11-16): the audit adds each item at decide time with a provisional "wrong" label, and the default seed is None. Items with score −inf are no longer explored. See the "Fixes applied" section of the review.

## Related pages
- [North star](north-star.md) · [roadmap P15-04](roadmap-standard.md#p15-04-bandit-feedback-online-risk-control-and-guarantee-statement)
- [M2-16 online re-calibration](m2-16-online-recal-result.md) · [per-session risk control](per-session-risk-control.md)
- [ACI](../concepts/adaptive-conformal-inference.md) · [conformal risk control](../concepts/conformal-risk-control.md)
