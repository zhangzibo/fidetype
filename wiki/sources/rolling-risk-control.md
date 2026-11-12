---
title: "Achieving Risk Control in Online Learning Settings (Feldman, Ringel, Bates & Romano)"
type: source
tags: [conformal, risk-control, online, adversarial, guarantee]
sources: [rolling-risk-control]
updated: 2026-11-11
---

# Achieving Risk Control in Online Learning Settings (Feldman, Ringel, Bates & Romano)

## Citation and links
- S. Feldman, L. Ringel, S. Bates, Y. Romano. "Achieving Risk Control in Online Learning Settings." arXiv:2205.09095 (cs.LG, stat.ML). v1 18 May 2022; current v7 27 Jan 2023. https://arxiv.org/abs/2205.09095. The arXiv page lists no journal-ref (TMLR 2023, from our own knowledge).
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none (arXiv abstract page read on 2026-11-11).

## TL;DR
"Rolling risk control": an online update of a calibration parameter so that a general risk (coverage, false negative rate, F1) stays at a user-chosen level. The abstract says the guarantee holds even when the data distribution shifts unpredictably or adversarially. It wraps any online learner at almost no extra cost and can control several risks at once.

## Key facts
| Item | Value |
|---|---|
| Update | θ_{t+1} = θ_t + γ (L_t − α) (the same telescoping idea as ACI, for a general bounded loss) |
| Guarantee | long-run average risk ≤ α + O(1 / (γ T)), any sequence |
| Needs | the realised loss at each step |

## Limitations
- Long-run average only. No statement per window or per user.
- The update above is our restatement. Check the paper for the exact conditions.

## How Fidetype uses it
It is the direct template for the `aci` method: the loss is the wrong-commit loss, the parameter is the COMMIT threshold.

## Feeds
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md), section "Online re-calibration under drift"
- [M2-16 online re-calibration result](../questions/m2-16-online-recal-result.md)
- Code: `src/fidetype/trust/online_risk.py` (our own implementation; no code read or copied)
