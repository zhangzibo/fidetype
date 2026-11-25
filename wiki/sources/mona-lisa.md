---
title: "MONA LISA: cross-modal silent speech with LLM-enhanced recognition (Benster et al. 2024)"
type: source
tags: [emg, silent-speech, cross-modal, contrastive, shared-latent, llm, rescoring, brain-to-text-24, f2, f3]
sources: [mona-lisa]
updated: 2026-11-24
---

# MONA LISA (Benster et al. 2024)

## Citation and links
- T. Benster, G. Wilson, R. Elisha, F. R. Willett, S. Druckmann. "A Cross-Modal Approach to Silent Speech with LLM-Enhanced Recognition." arXiv:2403.05583 (v1, 2024-03-02, cs.HC). https://arxiv.org/abs/2403.05583
- **Licence:** CC BY 4.0 (arXiv licence link). Code `tbenst/silent_speech`: MIT.
- **Local raw path:** `references/papers/benster_2024_mona_lisa_arxiv_2403.05583.pdf` (15 pages, SHA-256 `964b2fa6493f739d6193672088705270361e1bc3a34652f447f176d192146947`) + `.txt` (pdftotext -enc UTF-8). Downloaded 2026-11-24. Git-ignored.

## TL;DR
MONA ("Multimodal Orofacial Neural Audio") trains EMG and audio encoders into **one shared latent space** with two contrastive losses (crossCon, supTcon). Audio-only data (LibriSpeech) then helps the EMG decoder. LISA ("Large Language Model (LLM) Integrated Scoring Adjustment") lets an LLM rescore or rewrite the top beams of an ensemble.

## Key facts
| Item | Value | Where |
|---|---|---|
| Silent EMG, open vocabulary | "reduces the state-of-the-art word error rate (WER) from 28.8% to 12.2% in the Gaddy (2020) benchmark dataset" | Abstract |
| Baseline 28.8 % | the EMG-to-text model of Gaddy (2022, PhD thesis, UC Berkeley EECS-2022-68), not the 2020 voicing WER | §5 |
| Vocal EMG | "from 23.3% to 3.7%" | Abstract |
| Without LISA | silent EMG 22.2 %, vocal EMG 8.9 % | Table 3 |
| Priority claim | "the first instance where noninvasive silent speech recognition on an open vocabulary has cleared the threshold of 15% WER" | Abstract |
| Brain-to-Text '24 | "LISA performs best, improving the top WER from 9.8% to 8.9%" (intracortical speech; the paper does not name the participant) | Abstract |
| LISA | GPT-3.5 or GPT-4 rescoring of a 10-model ensemble ("Ensemble 10 x top 1"); 4-gram LM in the beam search | §4 |

## Limitations (stated)
- "the benefit from fine-tuning on GPT3.5-turbo generalized poorly on silent EMG data".
- Fine-tuning does "not generalize well from ensemble-to-ensemble" (15.0 % and 21.1 %).
- The ensemble needs a "10x increase in compute".
- "CTC loss is only loosely predictive of WER".
- One EMG speaker (Gaddy data). With chain-of-reasoning prompts the LLM did not follow the task 3 % of the time.

## Why it matters for us
- **F3:** the strongest cross-modal language result we know is alignment to a **shared output space**, not a shared input trunk. It supports "modality-specific encoders + one shared output space" ([north star F3](../questions/north-star.md#f3-cross-body-language-model-e1)).
- **F2:** LISA lets an LLM rewrite the decoded text, with no check against the EMG evidence. This is exactly the case that our grounding check and hallucination bound address ([E3 write-up](../questions/frontier-e3-hallucination.md)).

> **Our take:** an LLM rewrite that lowers WER can still add words that the signal does not support. MONA LISA reports WER only. A fluent-wrong count on its outputs would be a good public test of our F2 tracks.

## Feeds
- [Gaddy & Klein 2020](gaddy-digital-voicing.md), [Gaddy dataset](../entities/gaddy-silent-speech-dataset.md)
- [NeuroLLM](../concepts/neuro-llm.md)
- [Novelty check, 2026-11-24 update](../questions/novelty-check-2026-11.md#update-2026-11-24-literature-check)
