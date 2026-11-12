---
title: "Non-Exchangeable Conformal Risk Control (Farinhas, Zerva, Ulmer & Martins)"
type: source
tags: [conformal, risk-control, weighted, non-exchangeable, drift]
sources: [non-exchangeable-crc]
updated: 2026-11-11
---

# Non-Exchangeable Conformal Risk Control (Farinhas, Zerva, Ulmer & Martins)

## Citation and links
- A. Farinhas, C. Zerva, D. Ulmer, A. F. T. Martins. "Non-Exchangeable Conformal Risk Control." arXiv:2310.01262. v1 2 Oct 2023; v2 26 Jan 2024. ICLR 2024 (Comments field of the arXiv page). https://arxiv.org/abs/2310.01262.
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none (arXiv abstract page read on 2026-11-11).

## TL;DR
The paper joins [CRC](conformal-risk-control.md) and the weighted method of [Barber et al.](conformal-beyond-exchangeability.md). It controls the expected value of any monotone loss on non-exchangeable data. Data points get weights by their relevance to the test point. The abstract says this can give tighter bounds under change points, time series and distribution drift.

## Key facts
| Item | Value |
|---|---|
| Rule | λ̂ = inf { λ : (Σ_i w_i L_i(λ) + w_{n+1} B) / (Σ_i w_i + w_{n+1}) ≤ α } |
| Guarantee | E[L_{n+1}(λ̂)] ≤ α + B Σ_i w̃_i d_TV(Z, Z^i) (approximate under drift; exact under exchangeability) |
| Loss | bounded by B, non-increasing in λ (as in CRC) |

## Limitations
- The d_TV term is unknown. Under real drift the bound is not a computable guarantee.
- The rule and bound above are our restatement. Check the paper for the exact conditions.

## How Fidetype uses it
Fidetype `weighted_crc_threshold` (this rule, with w_{n+1} = 1) and the `window` / `decay` methods of `OnlineCommitRiskControl`.

## Feeds
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md), section "Online re-calibration under drift"
- [M2-16 online re-calibration result](../questions/m2-16-online-recal-result.md)
- Code: `src/fidetype/trust/online_risk.py` (our own implementation; no code read or copied)
