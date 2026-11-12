---
title: "Conformal Risk Control (Angelopoulos, Bates, Fisch, Lei & Schuster)"
type: source
tags: [conformal, risk-control, calibration, trust, statistics, guarantee]
sources: [conformal-risk-control]
updated: 2026-11-11
---

# Conformal Risk Control

## Citation and links
- A. N. Angelopoulos, S. Bates, A. Fisch, L. Lei, T. Schuster. "Conformal Risk Control." arXiv:2208.02814 [stat.ME]. v1 4 Aug 2022; current v4 13 Jun 2025. https://arxiv.org/abs/2208.02814, DOI https://doi.org/10.48550/arXiv.2208.02814. Published at ICLR 2024 (the arXiv page lists no journal-ref; the venue is from our prior knowledge, not checked on the page).
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Code:** https://github.com/aangelopoulos/conformal-risk (listed on the arXiv page). We did not read or copy it. Our code is our own: `src/fidetype/trust/risk_control.py`.
- **Local raw path:** none (we read the arXiv abstract page on 2026-11-11 and use the method from our knowledge of the paper).

## TL;DR
Split conformal prediction controls one loss: miscoverage. CRC controls the **expected value of any monotone, bounded loss**. The arXiv abstract opens: "We extend conformal prediction to control the expected value of any monotone loss function." It is tight up to an O(1/n) term.

## Key facts
| Item | Value |
|---|---|
| Setting | n calibration items. A loss L_i(λ) that is non-increasing in λ, in [0, B] |
| Rule | λ̂ = inf { λ : (n / (n + 1)) R̂_n(λ) + B / (n + 1) ≤ α } |
| Guarantee | E[L_{n+1}(λ̂)] ≤ α if the n + 1 items are exchangeable (marginal, in expectation) |
| Tightness | E[L_{n+1}(λ̂)] ≥ α − 2B / (n + 1) under extra continuity conditions |
| Extensions in the paper | distribution shift (weighted), quantile risk, multiple risks, adversarial risks, U-statistics |
| Examples in the paper | false negative rate (vision), graph distance, token-level F1 (NLP) |

## Limitations
- The guarantee is marginal: an average over calibration sets and new items. One session can be above α.
- It needs exchangeability. Drift between sessions breaks it.
- It needs a monotone loss. Our wrong-commit loss is monotone in the COMMIT threshold once the fallback loss is folded in (see [conformal risk control](../concepts/conformal-risk-control.md)).

## Feeds
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md)
- [M2-13 conformal result](../questions/m2-13-conformal-result.md)
- Companion high-probability method: [Learn then Test](learn-then-test.md)
