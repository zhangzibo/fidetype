---
title: emg2qwerty (wrist-EMG typing dataset)
type: entity
tags: [dataset, emg, typing, public, nc-licence, not-yet-ingested]
sources: [brain2qwerty-v1, brain2qwerty-v2, neural-input-landscape-2026]
updated: 2026-11-10
---

# emg2qwerty

> **Partial page.** Facts below were checked on the repo page and the download server on 2026-11-10 ([public datasets survey](../questions/public-datasets.md)). The paper itself is not ingested yet.

- **Citation**: Sivakumar et al., *emg2qwerty: A large dataset with baselines for touch typing using surface electromyography*, NeurIPS 2024 (arXiv 2410.20081).
- **Code and data**: https://github.com/facebookresearch/emg2qwerty (archived, read-only). Data: `https://fb-ctrl-oss.s3.amazonaws.com/emg2qwerty/emg2qwerty-data-2021-08.tar.gz`.
- **Licence**: **CC-BY-NC-4.0** (repo README: "emg2qwerty is CC-BY-NC-4.0 licensed"). It is not commercially usable. Use it only for research and benchmarks ([landscape report](../sources/neural-input-landscape-2026.md#data-warning)).
- **Size**: 108 users, 1,135 session files, 346 hours (repo). The archive is **308.4 GB** (HTTP `Content-Length` 308,382,645,571 bytes). A BIDS copy on NEMAR (NM000104) is said to be about 239 GB (unverified).
- **Format**: one HDF5 file per session. Each has left and right sEMG, the prompted text, keylogger ground truth and their timestamps (repo).
- **Signal**: 2 kHz. Two wristbands with 16 differential channels each, 32 in total (secondary sources). About 5.26 million keystrokes (secondary, unverified).
- **What it measures**: surface EMG from the **wrist** while people type. This is muscle activity, not brain activity, so it is not a BCI in the strict sense.
- **Relevance**:
  - Both Brain2Qwerty papers cite it as the model for **continuous, causal decoding**. v2 points to its low-latency causal Conformer as a template for real-time decoding ([v1](../sources/brain2qwerty-v1.md), [v2](../sources/brain2qwerty-v2.md)).
  - It is the *largest public* typing dataset of any modality. It can be decoded with the same CTC machinery, and the hardware (EMG wristbands) is affordable.

## Sibling Meta datasets
All Meta EMG datasets are NC. All are HDF5 at 2 kHz.

| Dataset | Content | Size | Licence |
|---|---|---|---|
| emg2qwerty | typing, 108 users, 346 h | 308.4 GB | CC-BY-NC-4.0 |
| generic-neuromotor-interface | discrete gestures, handwriting (98.8 / 31.5 / 10.4 h train/val/test), wrist; 100 users per task | not checked | CC-BY-NC-4.0 |
| emg2pose | hand pose, 193 users, 370 h | 462.8 GB (431 GiB) | CC-BY-NC-SA-4.0 |

## Commercially clean alternatives
- [KT-sEMG (Nokia)](kt-semg-dataset.md): CC BY 4.0, 32 ch at 2000 Hz, ms keystroke timestamps, one typist, 21.0 GB.
- [Toronto sEMG typing](toronto-semg-typing-dataset.md): CC BY 4.0, 16 ch at 2 kHz, 19 people, 2.77 GB.

> **Our take:** emg2qwerty stays the research benchmark for the EMG adapter. It cannot train product weights. For licence-clean EMG work use KT-sEMG and the Toronto set. For licence-clean trust-layer evaluation on real decoded text, use [Brain-to-Text '25](brain-to-text-25.md).

**Next step:** ingest the paper and repo. Check whether a per-user download exists before fetching 308 GB.

Related: [Meta Neural Band](meta-neural-band.md) · [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md) · [CTC](../concepts/ctc.md) · [Public datasets survey](../questions/public-datasets.md)
