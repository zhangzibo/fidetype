---
title: KT-sEMG dataset (Nokia, keyboard typing sEMG)
type: entity
tags: [dataset, emg, typing, cc-by, licence-clean]
sources: []
updated: 2026-11-10
---

# KT-sEMG (Keyboard Typing via Surface Electromyography)

- **Citation**: Crouch, Zheng, Eggleston, *Natural Typing Recognition via Surface Electromyography*, arXiv 2109.10743 (Nokia Bell Labs).
- **Link**: https://doi.org/10.7910/DVN/AV6XIR (Harvard Dataverse)
- **Licence**: "copyright 2021 Nokia. Licensed under the Creative Commons Attribution 4.0 International license. SPDX-License-Identifier: CC-BY-4.0" (Dataverse terms, verified 2026-11-10). Commercial use: **yes, with attribution**.
- **Signal**: forearm sEMG from custom sleeves, 16 channels per arm (32 total), 2000 Hz.
- **Format**: per run, a CSV of the 32 channels at 2000 Hz (`runNN.csv`), a keystroke log with millisecond timestamps (`runNN_keys.txt`), and a start-time file (`runNN_ts.txt`).
- **Size**: 88 files, 21.0 GB (Dataverse API).
- **Participants**: one "nonprofessional typist" doing natural typing (paper).
- **Volume**: "over 148,000 labeled gestures" (keystrokes). The paper used 1,960 valid 15-second blocks. Hours: not stated (unverified).
- **Paper result**: CTC-trained conv + LSTM, "almost 91% character-level accuracy", processing time under 100 ms.

## Fit for Fidetype
| Use | Fit | Why |
|---|---|---|
| (a) decoder training | ✔ | Continuous EMG + keystrokes. CTC works (paper) |
| (b) trust-layer / eWPM | ~ | Keystroke timing yes. Free typing, so no fixed target sentences (unverified) |
| (c) adapter conformance | ✔ | Plain CSV format, distinct from HDF5 (emg2qwerty) and FIF (MEG) |
| (d) pretraining | ~ | One person |

> **Our take:** This is the only commercially clean EMG typing set with a large keystroke count. One typist limits cross-subject claims, so pair it with the [Toronto set](toronto-semg-typing-dataset.md) (19 people). Second download after [Brain-to-Text '25](brain-to-text-25.md).

Related: [emg2qwerty](emg2qwerty.md) · [Meta Neural Band](meta-neural-band.md) · [Public datasets survey](../questions/public-datasets.md)
