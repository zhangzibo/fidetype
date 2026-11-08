---
title: SpanishBCBL dataset (Brain2Qwerty v1)
type: entity
tags: [dataset, meg, eeg, public]
sources: [brain2qwerty-v1, brain2qwerty-code]
updated: 2026-11-07
---

# SpanishBCBL

- **Access**: https://huggingface.co/datasets/bcbl190626/SpanishBCBL. The dataset is **gated**: request access, then `hf auth login`. The paper itself says data is available "upon request" to academics.
- **Size**: about **262 GB** in total (MEG `.fif`, EEG BrainVision, behavioural `.mat`). The loader can download the MEG subtree on its own.
- **Contents**:
  - MEG: 20 participants (19 usable), 21.5 h, 5,100 sentences, 193k characters.
  - EEG: 20 participants, 17.7 h, 4,000 sentences, 146k characters.
  - Each session covers 128 unique Spanish sentences, each typed about twice. Sentence diversity is low.
- **Loader**: `studies/spanishbcbl.py` in the [code repo](../sources/brain2qwerty-code.md) (study class `Pinet2024Meg`). It hard-codes some bad-file lists and naming quirks.
- **Licence / terms**: *to check* on the HuggingFace card before downloading.

> **Our take:** This is the **only public typing-MEG dataset we know of**. Any reproduction or new method has to start here.

Related: [EnglishBCBL](englishbcbl-dataset.md) · [BCBL](bcbl.md) · [Brain2Qwerty v1](../sources/brain2qwerty-v1.md)
