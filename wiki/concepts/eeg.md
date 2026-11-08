---
title: Electroencephalography (EEG)
type: concept
tags: [modality, hardware, eeg]
sources: [brain2qwerty-v1]
updated: 2026-11-07
---

# Electroencephalography (EEG)

EEG uses scalp electrodes to measure the brain's electric fields. It is cheap, portable and widely available, from consumer headsets up to research caps. Its drawback is a **limited signal-to-noise ratio**. Because of that, classic EEG BCIs rely on demanding paradigms such as flickering stimuli (SSVEP), P300 spellers or long periods of motor imagery. Even then, accuracy is moderate. For example, the MOABB benchmark reports 43.3% accuracy on a 4-class motor-imagery task ([v1](../sources/brain2qwerty-v1.md), intro).

## In Brain2Qwerty v1
- **Device**: BrainVision actiCAP slim, 64 channels (61 EEG + 3 ocular), BrainAmp DC amplifier, 1 kHz.
- **Data**: 20 participants, 17.7 h, 4,000 sentences.
- **Results**: mean **CER 65%**, 61% for the best participant. For comparison, [MEG](meg.md) reaches 29%. On EEG, Brain2Qwerty is only 1.2× better than EEGNet.
- The decoded EEG text was "rarely comprehensible".
- v2 dropped EEG and used MEG only.

> **Our take:** If you want something that works now with affordable hardware, EEG typing decoding is weak. Wrist EMG ([emg2qwerty](../entities/emg2qwerty.md)) or MEG-class signals look like better bets. Where EEG still makes sense is for cheap experiments and for pretraining.

Related: [MEG](meg.md) · [OPM-MEG](opm-meg.md)
