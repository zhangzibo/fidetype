---
title: THINGS-EEG2 dataset
type: entity
tags: [dataset, eeg, image-decoding, things, cc-by, licence-clean]
sources: []
updated: 2026-11-24
---

# THINGS-EEG2

Large EEG dataset of people looking at images of the THINGS concept set. Used by experiment [A1](../../experiments/2026-11-24-a1-things-eeg2-image-gate/plan.md). Context: [Beyond words](../questions/beyond-words.md#images).

- **Citation:** Gifford, Dwivedi, Roig, Cichy, "A large and rich EEG dataset for modeling human visual object recognition", *NeuroImage* 264:119754 (2022).
- **Link:** OSF project https://osf.io/3jk45/
- **Licence:** EEG and metadata **CC BY 4.0** (OSF licence of every component: "CC-By Attribution 4.0 International", checked 2026-11-24). The THINGS **images** (Hebart et al. 2019) are research use only, no redistribution: never commit them.
- **Content:** 10 subjects. Training set 1,654 concepts x 10 images x 4 repetitions; test set 200 new concepts x 1 image x 80 repetitions (A1 plan, from the file shapes).
- **Third-party re-preprocessing:** Hugging Face `LidongYang/EEG_Image_decode` (63 channels, 250 Hz, plus CLIP ViT-H-14 features), CC BY 4.0 on the dataset card. A1 uses it as the primary EEG input.
- **Size used by A1:** 23.6 GB (subjects 1 and 2, features, OSF reference files). All 10 subjects at 250 Hz: about 104 GB (A1 plan).
- **Published decoders:** NICE (13.8 % / 39.5 % top-1 / top-5, 200-way zero-shot) and ATM-S (28.64 % top-1, 80-trial average); both codes MIT. Numbers and links: [Beyond words](../questions/beyond-words.md#images).
- **Local copy:** see [`references/README.md`](../../references/README.md) (rows `things-eeg2`, `things-eeg2-atm-250hz`).
