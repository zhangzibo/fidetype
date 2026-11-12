---
title: "Conformal Prediction Under Covariate Shift (Tibshirani, Barber, Candès & Ramdas)"
type: source
tags: [conformal, weighted, covariate-shift, likelihood-ratio]
sources: [conformal-covariate-shift]
updated: 2026-11-11
---

# Conformal Prediction Under Covariate Shift (Tibshirani, Barber, Candès & Ramdas)

## Citation and links
- R. J. Tibshirani, R. F. Barber, E. J. Candès, A. Ramdas. "Conformal Prediction Under Covariate Shift." arXiv:1904.06019 (stat.ME). v1 12 Apr 2019; current v3 6 Jul 2020. https://arxiv.org/abs/1904.06019. The arXiv page lists no journal-ref (NeurIPS 2019, from our own knowledge).
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none (arXiv abstract page read on 2026-11-11).

## TL;DR
Weighted conformal prediction stays distribution-free when the covariate distribution differs between calibration and test, if the likelihood ratio between the two is known or can be estimated from unlabelled test covariates. The weights are the likelihood ratios. The paper also introduces "weighted exchangeability".

## Key facts
| Item | Value |
|---|---|
| Shift type | covariate shift only: P(X) changes, P(Y \| X) stays fixed |
| Weights | w(x) = dP_test(x) / dP_cal(x), known or estimated |
| Guarantee | exact coverage under weighted exchangeability |

## Limitations
- The B2T '25 drift is not pure covariate shift: at the same confidence the later trials have more errors, so P(wrong | score) changes. Likelihood-ratio weights do not apply directly. We use order-based weights ([Barber et al.](conformal-beyond-exchangeability.md)).

## How Fidetype uses it
Background only. Not implemented.

## Feeds
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md), section "Online re-calibration under drift"
- [M2-16 online re-calibration result](../questions/m2-16-online-recal-result.md)
- Code: `src/fidetype/trust/online_risk.py` (our own implementation; no code read or copied)
