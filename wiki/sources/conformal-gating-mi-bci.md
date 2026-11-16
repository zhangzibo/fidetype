---
title: "From confidence to caution: conformal gating for cross-session motor imagery BCIs (Xing & Nagarajan 2026)"
type: source
tags: [conformal, bci, eeg, motor-imagery, abstention, gating, cross-session, novelty-check]
sources: [conformal-gating-mi-bci]
updated: 2026-11-15
---

# Conformal gating for cross-session motor imagery BCIs

## Citation and links
- S. Xing, A. Nagarajan. "From confidence to caution: conformal gating for cross-session motor imagery brain-computer interfaces." *Journal of Neural Engineering*, 2026. DOI https://doi.org/10.1088/1741-2552/aead26 (PubMed 42805221).
- **Licence:** journal copyright; not open access (Europe PMC flag). We do not store the article.
- **Local raw path:** none. We read the PubMed / Europe PMC abstract on 2026-11-15. **Full text not read.**

## TL;DR
The paper uses conformal prediction as a **command gate** for an EEG motor imagery BCI: the system withholds uncertain commands. It tests the gate across sessions, where exchangeability does not hold. Ungated, about 36–38 % of commands were wrong. With the conformal gates, wrong-decisive rates fell to 9–16 % (OpenBMI) and 6–8 % (BCIC IV-2a).

## Key facts
| Item | Value (abstract) |
|---|---|
| Data | OpenBMI (54 subjects, 2 classes); BCI Competition IV-2a (9 subjects, 4 classes) |
| Base classifier | DeepConvNet, **fixed** (no decoder updates reported) |
| Gates compared | threshold CP (THR), RAPS / RAPS-Opt, Chow's selective prediction |
| Calibration sources | five chronological splits with increasing match to the target session |
| Ungated wrong-decisive rate | 37.5 % (OpenBMI), 35.5 % (BCIC IV-2a) |
| Gated wrong-decisive rate | 9–16 % (OpenBMI), 6–8 % (BCIC IV-2a) |
| Output | discrete commands (2 or 4 classes); no text, no language model |

## Limitations
- The decoder does not learn from feedback. The gate is calibrated offline per split.
- The abstract says exchangeability "cannot be assumed" across sessions. So the conformal coverage statement does not hold formally there. The paper reports empirical rates.
- Closed-set commands, not text.

## Why it matters for us
It is published run-time conformal abstention in a BCI. So neither "first conformal BCI" nor "first risk-controlled abstention in a BCI" is a safe claim. It does **not** meet F1 (no decoder updates) or F2 (no language model, no text). See [novelty check 2026-11](../questions/novelty-check-2026-11.md).

## Feeds
- [Novelty check 2026-11](../questions/novelty-check-2026-11.md)
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md)
