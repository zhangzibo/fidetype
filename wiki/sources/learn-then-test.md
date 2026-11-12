---
title: "Learn then Test (Angelopoulos, Bates, Candès, Jordan & Lei)"
type: source
tags: [conformal, risk-control, multiple-testing, calibration, trust, guarantee]
sources: [learn-then-test]
updated: 2026-11-11
---

# Learn then Test: Calibrating Predictive Algorithms to Achieve Risk Control

## Citation and links
- A. N. Angelopoulos, S. Bates, E. J. Candès, M. I. Jordan, L. Lei. "Learn then Test: Calibrating Predictive Algorithms to Achieve Risk Control." arXiv:2110.01052. v1 3 Oct 2021; current v5 29 Sep 2022. https://arxiv.org/abs/2110.01052. The arXiv page lists no journal-ref.
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Code:** https://github.com/aangelopoulos/ltt (listed on the arXiv page). Not read, not copied.
- **Local raw path:** none (arXiv abstract page read on 2026-11-11).

## TL;DR
LTT turns risk control into **multiple hypothesis testing**. For each λ on a grid fixed in advance, test H0: R(λ) > α with a valid p-value. Reject with a family-wise error rate (FWER) procedure at level δ. Any rejected λ has P(R(λ) ≤ α) ≥ 1 − δ. It works for any model, without refitting.

## Key facts
| Item | Value |
|---|---|
| Guarantee | P(R(λ̂) ≤ α) ≥ 1 − δ over the calibration draw (high probability, not only in expectation) |
| p-values | Hoeffding, Bentkus, and the combined Hoeffding–Bentkus (HB) p-value for losses in [0, 1]; exact binomial tails for 0/1 losses |
| FWER procedure | Bonferroni, or **fixed-sequence testing** when the risk is monotone in λ (test from the safest λ, stop at the first acceptance) |
| Not monotone? | LTT does not need a monotone loss (CRC does) |

## Limitations
- The λ grid must be fixed before the data is seen.
- More conservative than CRC for the same α: it controls a tail, not a mean.
- Needs exchangeable (i.i.d.) calibration data, as CRC does.

## Feeds
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md)
- [M2-13 conformal result](../questions/m2-13-conformal-result.md)
- [Conformal Risk Control](conformal-risk-control.md)
