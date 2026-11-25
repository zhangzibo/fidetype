---
title: "Digital Voicing of Silent Speech (Gaddy & Klein 2020) and the follow-up model (2021)"
type: source
tags: [emg, facial-emg, silent-speech, open-vocabulary, dataset, cc-by, non-invasive, f3, licence-clean]
sources: [gaddy-digital-voicing]
updated: 2026-11-24
---

# Digital Voicing of Silent Speech (Gaddy & Klein 2020)

## Citation and links
- D. Gaddy, D. Klein. "Digital Voicing of Silent Speech." Proc. EMNLP 2020, pages 5521–5530. https://aclanthology.org/2020.emnlp-main.445 (doi 10.18653/v1/2020.emnlp-main.445; arXiv 2010.02960). The Anthology lists "Award: Best Paper".
- Follow-up: D. Gaddy, D. Klein. "An Improved Model for Voicing Silent Speech." Proc. ACL-IJCNLP 2021 (Volume 2: Short Papers), pages 175–181. doi 10.18653/v1/2021.acl-short.23.
- Dataset: "Silent Speech EMG", Zenodo record 4064409, version 1.0, 2020-10-02, creator D. Gaddy (UC Berkeley). See [the entity page](../entities/gaddy-silent-speech-dataset.md).
- **Licence:** both papers: "Materials published in or after 2016 are licensed on a Creative Commons Attribution 4.0 International License" (ACL Anthology footer). Code `dgaddy/silent_speech`: MIT. Dataset: CC BY 4.0 (Zenodo API).
- **Local raw path:** `references/papers/gaddy_klein_2020_emnlp_digital_voicing.pdf` (10 pages, SHA-256 `840620fb9e10f9c3a40e24a264a1f8f1a00d757b1b36b57119c955107d897a28`) and `references/papers/gaddy_klein_2021_acl_improved_voicing.pdf` (7 pages, SHA-256 `32fde42fe36e5b625bf458aefa4c001ce25ee45b8a886a1df11ac04ffe17d2c0`), each with a `pdftotext -enc UTF-8` .txt. Downloaded 2026-11-24. Git-ignored.

## TL;DR
One speaker wears 8 facial EMG electrodes and speaks silently (mouths words) or aloud. The model turns silent EMG into audio ("digital voicing"). The audio targets come from the vocalised recordings, aligned to the silent ones. It is the main open-vocabulary, non-invasive EMG speech dataset, and it is **CC BY 4.0**.

## Key facts
| Item | Value | Where |
|---|---|---|
| Sensor | "Eight channels are collected at a sample rate of 1000 Hz"; OpenBCI Cyton board; audio 16 kHz | 2020, §2.3 |
| Data | "nearly 20 hours of facial EMG signals from a single speaker" | 2020, §1 |
| Open vocabulary | parallel 3.6 h silent / 3.9 h vocalised (1,588 utterances) + 11.2 h vocalised only (5,477 utterances); total 18.6 h; 9,828 words in vocabulary | 2020, Table 2 |
| Closed vocabulary (dates and times) | 26 min silent / 30 min vocalised, 500 utterances, 67 words | 2020, Table 1 |
| Main result | transcription WER "from 64% to 4% in one data condition and 88% to 68% in another" | 2020, abstract |
| Open vocabulary detail | automatic (DeepSpeech) WER: baseline 91.2, without throat electrode 88.0, model 68.0 (Table 5); human transcription 95.1 → 74.8 | 2020, §5 |
| ASR floor | DeepSpeech on real vocalised audio: "a WER of 9.5%" | 2020 |
| Method | DTW alignment of vocalised audio targets to silent EMG, refined with CCA; BiLSTM then WaveNet vocoder; session embeddings for electrode shifts | 2020, §3 |
| Data scaling | "there does not seem to be a plateau in performance" beyond 15 h | 2020 |
| 2021 model | convolution + Transformer on raw EMG, auxiliary phoneme loss, about 40 M parameters: "from 68.0% to 42.2%" automatic WER; human evaluators 32.3 % average | 2021, abstract, §4 |

## Limitations
- One speaker. No cross-person test.
- The output is audio. WER is measured by an ASR system (or human listeners) on that audio, not by a text decoder.
- Silent speech here is mouthing by an able speaker, not attempted speech by a person with paralysis.

## Why it matters for us
- It is a **licence-clean, non-invasive, open-vocabulary EMG-to-language** source. Our current EMG text sources are either NC ([emg2qwerty](../entities/emg2qwerty.md)) or typing ([KT-sEMG](../entities/kt-semg-dataset.md)).
- It gives F3 a second target and a clean EMG source for a trunk ([north star F3](../questions/north-star.md#f3-cross-body-language-model-e1)).
- The project owner could record the same kind of data with an open board (no implant, no lab). Ethics rules for publication still apply.
- [MONA LISA](mona-lisa.md) uses this data as its silent-speech benchmark (28.8 % → 12.2 % WER).

## Feeds
- [Gaddy silent-speech dataset](../entities/gaddy-silent-speech-dataset.md)
- [MONA LISA](mona-lisa.md)
- [Public datasets](../questions/public-datasets.md)
- [Novelty check, 2026-11-24 update](../questions/novelty-check-2026-11.md#update-2026-11-24-literature-check)
