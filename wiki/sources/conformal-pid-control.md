---
title: "Conformal PID Control for Time Series Prediction (Angelopoulos, Candès & Tibshirani)"
type: source
tags: [conformal, online, control-theory, time-series, guarantee, trust]
sources: [conformal-pid-control]
updated: 2026-11-11
---

# Conformal PID Control for Time Series Prediction (Angelopoulos, Candès & Tibshirani)

## Citation and links
- A. N. Angelopoulos, E. J. Candès, R. J. Tibshirani. "Conformal PID Control for Time Series Prediction." arXiv:2307.16895 (cs.LG, eess.SY, stat.ME, stat.ML). v1 31 Jul 2023. https://arxiv.org/abs/2307.16895. The arXiv page lists no journal-ref (NeurIPS 2023, from our own knowledge). Code on GitHub (listed on the arXiv page; not read, not copied).
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none (arXiv abstract page read on 2026-11-11).

## TL;DR
The paper combines conformal prediction with control theory. It updates the conformal threshold online, like a PID controller: a P term (quantile tracking: step the threshold by η(err_t − α)), an I term (integrated error) and a D term (a forecaster of the score, the "scorecaster"). The abstract says the theory simplifies and strengthens existing online conformal analyses. The methods adapt to seasonality, trends and distribution shifts (COVID-19 death forecasts, electricity demand, market returns, temperature).

## Key facts
| Item | Value |
|---|---|
| P-control (quantile tracking) | q_{t+1} = q_t + η (err_t − α): update the threshold itself, not the level |
| Guarantee of the P update | long-run coverage for any sequence if the scores are bounded; the proof is a telescoping sum of the updates |
| I and D terms | correct persistent errors and predictable trends |
| Needs | only the realised error at each step |

## Limitations
- Long-run average only. The finite-T slack depends on the score range and the step size.
- The I and D terms need tuning. We implement only the P update.

## How Fidetype uses it
In Fidetype it is the `aci` method: λ_{t+1} = max(λ_min, λ_t + η (L_t − α)) on the COMMIT threshold, with the certificate (1/T) Σ L_t ≤ α + (λ_{T+1} − λ_1) / (η T).

## Feeds
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md), section "Online re-calibration under drift"
- [M2-16 online re-calibration result](../questions/m2-16-online-recal-result.md)
- Code: `src/fidetype/trust/online_risk.py` (our own implementation; no code read or copied)
