---
title: "CORTEG: cross-modality transfer from scalp EEG to intracranial recordings (Yang et al. 2026)"
type: source
tags: [foundation-model, cross-modality, eeg, ecog, seeg, transfer, novelty-check]
sources: [corteg-eeg-to-ecog]
updated: 2026-11-15
---

# CORTEG: scalp-EEG foundation models transferred to ECoG

## Citation and links
- L. Yang, Q. Sun, B. Van Dyck, E. Calvo Merino, M. M. Van Hulle. "CORTEG: Foundation Models Enable Cross-Modality Representation Transfer from Scalp to Intracranial Brain Recordings." arXiv:2605.10337 [cs.AI]. v1 11 May 2026; v2 14 Oct 2026. https://arxiv.org/abs/2605.10337
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none. We read the arXiv abstract and the HTML full text (arxiv.org/html/2605.10337) on 2026-11-15.

## TL;DR
CORTEG takes an EEG foundation model that was pretrained on scalp EEG and adapts it to intracranial ECoG. It adds an electrode-aware spatial adapter and a tokenizer for low-frequency and high-gamma activity. It calibrates to a held-out patient in 10–30 minutes on one GPU. It reports the best mean results on finger-trajectory regression and audio-envelope regression, and strong results on stereo-EEG classification.

## Key facts
| Item | Value |
|---|---|
| Source modality | scalp EEG (pretrained EEG foundation model, 128 Hz) |
| Target modalities | ECoG (main); stereo-EEG (BrainTreebank, secondary) |
| Tasks | finger-trajectory regression (public, n = 9); audio-envelope regression (private, n = 16); sEEG word-vs-non-word and sentence-position classification |
| Text decoding | **none**: no phoneme, word-sequence or open-vocabulary text task |
| Calibration | held-out patient in 10–30 min on one GPU (abstract) |
| Novelty wording | Discussion: "one of the first systematic studies" of this transfer; Related Work: "Cross-modal transfer from scalp EEG to intracranial ECoG remains largely unexplored" |
| Implant spikes, EMG, MEG | not used |

## Limitations
- The transfer is EEG → ECoG / sEEG. It is not a transfer to a new modality for **text** output.
- The audio task uses private data. The sEEG tasks are binary classification.
- The source modality is pretrained alone. It is not a joint model across implant, EMG and MEG/EEG.

## Why it matters for us
It is the closest published "transfer to a new recording modality" result that we found. It makes our F3 claim "no published model reports transfer to a new modality" **false as written**. The claim must say "for text decoding". See [novelty check 2026-11](../questions/novelty-check-2026-11.md#c3-f3-cross-body-model).

## Feeds
- [Novelty check 2026-11](../questions/novelty-check-2026-11.md)
- [North star](../questions/north-star.md#why-this-is-new), pillar F3
