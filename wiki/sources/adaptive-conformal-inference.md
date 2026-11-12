---
title: "Adaptive Conformal Inference Under Distribution Shift (Gibbs & Candès)"
type: source
tags: [conformal, online, distribution-shift, drift, guarantee, trust]
sources: [adaptive-conformal-inference]
updated: 2026-11-11
---

# Adaptive Conformal Inference Under Distribution Shift (Gibbs & Candès)

## Citation and links
- I. Gibbs, E. Candès. "Adaptive Conformal Inference Under Distribution Shift." arXiv:2106.00170 (stat.ME). v1 1 Jun 2021; current v3 28 Oct 2021. https://arxiv.org/abs/2106.00170. The arXiv page lists no journal-ref (published at NeurIPS 2021, from our own knowledge).
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none (arXiv abstract page read on 2026-11-11).

## TL;DR
ACI keeps a conformal method valid when the data distribution changes over time in an unknown way. It treats the miscoverage level as one parameter α_t and updates it online after each observed error: α_{t+1} = α_t + γ(α − err_t). The abstract says the method provably achieves the target coverage frequency over long time intervals, for any data-generating process. It wraps any black-box predictor.

## Key facts
| Item | Value |
|---|---|
| Update | α_{t+1} = α_t + γ (α − err_t); err_t = 1 if the set missed the truth |
| Guarantee | long-run: \|(1/T) Σ err_t − α\| ≤ (max(α_1, 1 − α_1) + γ) / (γ T), for any sequence (deterministic, no exchangeability) |
| Needs | only the error of the action taken at step t (the realised loss) |
| Trade-off | large γ: fast tracking, more jitter; small γ: smooth, slow, larger slack for a given T |

## Limitations
- The bound is a long-run average. It says nothing about one short window.
- The slack is O(1 / (γ T)): it is small only for long streams.
- The form of the bound above is our restatement of the standard result. Check the paper for the exact statement.

## How Fidetype uses it
In Fidetype it is the `aci_window` method: the window CRC runs at level α_t, and α_t follows the ACI update with the realised wrong-commit loss. The older `AdaptiveConformal` class (M2-03) uses ACI for conformal sets.

## Feeds
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md), section "Online re-calibration under drift"
- [M2-16 online re-calibration result](../questions/m2-16-online-recal-result.md)
- Code: `src/fidetype/trust/online_risk.py` (our own implementation; no code read or copied)
