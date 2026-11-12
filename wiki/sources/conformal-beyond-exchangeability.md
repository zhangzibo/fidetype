---
title: "Conformal prediction beyond exchangeability (Barber, Candès, Ramdas & Tibshirani)"
type: source
tags: [conformal, weighted, distribution-drift, non-exchangeable, guarantee]
sources: [conformal-beyond-exchangeability]
updated: 2026-11-11
---

# Conformal prediction beyond exchangeability (Barber, Candès, Ramdas & Tibshirani)

## Citation and links
- R. F. Barber, E. J. Candès, A. Ramdas, R. J. Tibshirani. "Conformal prediction beyond exchangeability." arXiv:2202.13415 (stat.ME). v1 27 Feb 2022; current v5 17 Mar 2023. https://arxiv.org/abs/2202.13415. The arXiv page lists no journal-ref (Annals of Statistics 2023, from our own knowledge).
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none (arXiv abstract page read on 2026-11-11).

## TL;DR
The abstract notes that "exchangeability is often violated when predictive models are deployed in practice." The paper uses **weighted quantiles** with fixed weights (for example, more weight on recent points) to add robustness against distribution drift. The coverage gap is bounded by a weighted sum of total-variation distances between the data and the data with point i swapped with the test point. Under exchangeability the guarantee is exact.

## Key facts
| Item | Value |
|---|---|
| Weights | fixed in advance (they may depend on the order, e.g. w_i = ρ^age), not on the data values |
| Coverage | ≥ 1 − α − Σ_i w̃_i d_TV(Z, Z^i), w̃_i = w_i / (1 + Σ_j w_j) |
| Exchangeable data | exact 1 − α |
| Drift | the gap is small if the high-weight points are close in distribution to the test point |

## Limitations
- The gap term cannot be computed from data. In practice the bound is approximate.
- A small total weight makes the method conservative (few effective points).

## How Fidetype uses it
Basis of the `window` method (sliding window = weight 1 for the last N items, 0 before; `decay` = ρ^age). The risk-control form is in [Non-exchangeable CRC](non-exchangeable-crc.md).

## Feeds
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md), section "Online re-calibration under drift"
- [M2-16 online re-calibration result](../questions/m2-16-online-recal-result.md)
- Code: `src/fidetype/trust/online_risk.py` (our own implementation; no code read or copied)
