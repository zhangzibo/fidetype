---
title: "Adaptive Conformal Inference Under Distribution Shift (Gibbs & Candès)"
type: source
tags: [conformal, online, distribution-shift, drift, guarantee, trust]
sources: [adaptive-conformal-inference]
updated: 2026-11-15
---

# Adaptive Conformal Inference Under Distribution Shift (Gibbs & Candès)

## Citation and links
- I. Gibbs, E. Candès. "Adaptive Conformal Inference Under Distribution Shift." arXiv:2106.00170 (stat.ME). v1 1 Jun 2021; current v3 28 Oct 2021. https://arxiv.org/abs/2106.00170. The arXiv page lists no journal-ref (published at NeurIPS 2021, from our own knowledge).
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none (arXiv abstract page read on 2026-11-11; full text read via ar5iv on 2026-11-15 for P15-10).

## TL;DR
ACI keeps a conformal method valid when the data distribution changes over time in an unknown way. It treats the miscoverage level as one parameter α_t and updates it online after each observed error: α_{t+1} = α_t + γ(α − err_t). The abstract says the method provably achieves the target coverage frequency over long time intervals, for any data-generating process. It wraps any black-box predictor.

## Key facts
| Item | Value |
|---|---|
| Update | α_{t+1} = α_t + γ (α − err_t); err_t = 1 if the set missed the truth |
| Guarantee | long-run: \|(1/T) Σ err_t − α\| ≤ (max(α_1, 1 − α_1) + γ) / (γ T), for any sequence (deterministic, no exchangeability) |
| Needs | only the error of the action taken at step t (the realised loss) |
| Trade-off | large γ: fast tracking, more jitter; small γ: smooth, slow, larger slack for a given T |

## Model refits (full text, checked 2026-11-15)
- Section 2: "we assume that at each time t we are given a fitted score function" S_t(·); both functions "should be regularly re-estimated to align with the most recent observations".
- Proposition 4.1 needs only α_1 ∈ [0, 1] and non-decreasing quantile functions with the stated boundary values. The proof does not use stationarity, so the long-run bound holds for **any sequence of refit models**.
- The experiments refit the model over time (GARCH on the most recent 1250 days, Section 2.2). Section 5: "one should re-fit the model at each time step".
- Effect on us: "an error bound that stays valid while the decoder learns" is not a new statistical result. See [novelty check 2026-11](../questions/novelty-check-2026-11.md#c1-f1-safe-self-improving-bci).

## Limitations
- The bound is a long-run average. It says nothing about one short window.
- The slack is O(1 / (γ T)): it is small only for long streams.
- The form of the bound above is our restatement of the standard result. Check the paper for the exact statement.

## How Fidetype uses it
In Fidetype it is the `aci_window` method: the window CRC runs at level α_t, and α_t follows the ACI update with the realised wrong-commit loss. The older `AdaptiveConformal` class (M2-03) uses ACI for conformal sets.

## Feeds
- [Adaptive conformal inference (concept)](../concepts/adaptive-conformal-inference.md)
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md), section "Online re-calibration under drift"
- [M2-16 online re-calibration result](../questions/m2-16-online-recal-result.md)
- [Novelty check 2026-11](../questions/novelty-check-2026-11.md); related: [continual calibration](continual-calibration.md) (finite-sample refit after each update)
- Code: `src/fidetype/trust/online_risk.py` (our own implementation; no code read or copied)
