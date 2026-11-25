---
title: "CORP: plug-and-play stability for intracortical BCIs, one year of self-recalibration (Fan et al. 2023)"
type: source
tags: [implant, intracortical, handwriting, t5, self-training, pseudo-labels, recalibration, language-model, f1, novelty-check]
sources: [corp]
updated: 2026-11-24
---

# CORP (Fan et al. 2023)

## Citation and links
- C. Fan, N. Hahn, F. Kamdar, D. Avansino, G. H. Wilson, L. Hochberg, K. V. Shenoy, J. M. Henderson, F. R. Willett. "Plug-and-Play Stability for Intracortical Brain-Computer Interfaces: A One-Year Demonstration of Seamless Brain-to-Text Communication." NeurIPS 2023 (Advances in Neural Information Processing Systems 36, doi 10.52202/075280-1831). arXiv:2311.03611 (v1, 2023-11-06). https://arxiv.org/abs/2311.03611
- **Licence:** arXiv non-exclusive distribution 1.0. We do not store the PDF. Code `cffan/CORP`: no licence found (do not copy).
- **Local raw path:** none. Full text read as arXiv HTML on 2026-11-15 ([novelty check](../questions/novelty-check-2026-11.md)) and again on 2026-11-24.

## TL;DR
CORP ("Continual Online Recalibration with Pseudo-labels") lets a language model correct the decoded text. It then retrains the decoder on these corrected outputs after every sentence. It kept a handwriting decoder stable for more than a year with one participant (T5). It states no error bound and has no update gate.

## Key facts
| Item | Value | Where |
|---|---|---|
| Method | "uses language models (LMs) to automatically correct communication iBCI text outputs, and continually retrains the decoder using these corrected outputs ("pseudo-labels")"; online SGD with CTC loss | Abstract; §3 |
| Duration | "more than one year (403 days)"; 15 monthly evaluation sessions; "6.18% CER" after 405 days | Abstract; Results |
| Participant | T5 (BrainGate2), handwriting, "73.2±11.0 characters per minute" | §4 |
| Accuracy | "stable decoding accuracy of 93.84%±2.28"; CORP blocks average CER "6.35%±1.75"; day-0 seed CER 3.22 % | Results |
| WER (Table 1) | no recalibration 23.15 offline / 26.51 online; CORP 3.68 [3.21, 4.76] / 6.16; CORP with ground truth 2.05 offline | Table 1 |
| Ablations (CER %, Table 2) | CORP 4.80; no data augmentation 5.87; no replay buffer 6.42; no GRU backbone training 7.00; **no language model 19.22** | Table 2 |
| Guards | replay buffer, noise augmentation, "we stop the recalibration once the loss falls below a certain threshold" (a training-loss stop, not a confidence filter) | §3 |

## Limitations (stated)
- "dependence on the accuracy of the pseudo-labels"; recalibration CER grows sub-linearly with pseudo-label CER (Fig. 5).
- "may pose challenges in cases where the iBCI system exhibits substantial nonstationarity or low decoding accuracy".
- One participant, handwriting only. The authors name speech as future work.
- "we lack a validation set" (no held-out check of each update).

## Why it matters for us
- It is the reference self-recalibration method for **F1**. Our E2 "ST" arm (own top-1, no filter, no LM correction) is weaker than CORP. Call it "naive self-training", not CORP.
- The ablation shows that the LM correction does most of the work (19.22 % CER without it).

> **Our take:** CORP and [Card et al. 2026](card-2026-home-use.md) together show that "learn from use" works in real implant users. Our F1 novelty is not "learning from use". It is a statistically tested update gate plus a stated long-run wrong-commit bound with null controls.

## Feeds
- [North star F1](../questions/north-star.md#f1-safe-self-improving-bci-e2)
- [Novelty check, C1](../questions/novelty-check-2026-11.md#c1-f1-safe-self-improving-bci)
- [E2 self-teaching write-up](../questions/frontier-e2-self-teaching.md)
- [Wilson et al. 2025 (HMM recalibration)](wilson-hmm-recalibration.md)
