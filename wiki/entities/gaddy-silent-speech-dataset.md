---
title: Gaddy silent-speech facial EMG dataset (Zenodo 4064409)
type: entity
tags: [dataset, emg, facial-emg, silent-speech, open-vocabulary, cc-by, licence-clean, non-invasive, f3]
sources: [gaddy-digital-voicing]
updated: 2026-11-24
---

# Gaddy silent-speech facial EMG dataset

**What:** facial EMG during silent and vocalised speech, one speaker, open and closed vocabulary. Recorded for [Gaddy & Klein 2020](../sources/gaddy-digital-voicing.md).

| Field | Value (Zenodo API and record page, read 2026-11-24) |
|---|---|
| Title | "Silent Speech EMG" |
| DOI | 10.5281/zenodo.4064409 (concept DOI 10.5281/zenodo.4064408); version 1.0, the only version |
| Published | 2020-10-02 |
| Creator | Gaddy, David (UC Berkeley) |
| Licence | **CC BY 4.0** ("Creative Commons Attribution 4.0 International"); access "open". Attribution needed; commercial use allowed |
| Files | one file `emg_data.tar.gz`, 3,919,507,637 bytes, md5 `7f97d2182b896652999b1b2d0c69fd7b` |
| Per sample | `{i}_emg.npy` ("a saved numpy array of size (T, 8) with the raw EMG signals"), `{i}_audio.flac`, `{i}_audio_clean.flac`, `{i}_info.json`, `{i}_button.npy` |
| Signal | 8 channels, 1000 Hz (paper §2.3); audio 16 kHz |
| Amount | 18.6 h in the open-vocabulary set (paper Table 2); the 2021 paper says "19 hours" |
| Code | `dgaddy/silent_speech` (MIT) |

**Status:** not downloaded. No adapter yet.

## Fit for Fidetype
- Licence-clean non-invasive language data (CC BY 4.0). It can feed clean-track weights.
- One speaker only: good for a per-user decoder and for a self-recording demo; not for cross-person claims.
- Text labels exist (the sentence prompts), so a direct EMG → text CTC decoder is possible, as [MONA LISA](../sources/mona-lisa.md) does.

> **Our take:** this is the best candidate for a non-invasive F3 target with text output. A first ConvCTC baseline on CPU caches, then GPU, is the cheap first step.

## Related
- [Public datasets](../questions/public-datasets.md), [KT-sEMG](kt-semg-dataset.md), [emg2qwerty](emg2qwerty.md)
- [North star F3](../questions/north-star.md#f3-cross-body-language-model-e1)
