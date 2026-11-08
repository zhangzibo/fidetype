---
title: Magnetoencephalography (MEG)
type: concept
tags: [modality, hardware, meg]
sources: [brain2qwerty-v1, brain2qwerty-v2]
updated: 2026-11-07
---

# Magnetoencephalography (MEG)

MEG measures the tiny magnetic fields produced by cortical neurons. It samples at the millisecond scale (Brain2Qwerty records at 1 kHz) and has a **higher signal-to-noise ratio than [EEG](eeg.md)** ([v1](../sources/brain2qwerty-v1.md), intro).

## In Brain2Qwerty
- **Device**: MEGIN (Elekta) TRIUX, **306 channels** (102 magnetometers + 204 planar gradiometers). It has an online 0.1 Hz high-pass and a 330 Hz low-pass filter. The sensors are **cryogenically cooled (SQUIDs)** inside a magnetically shielded room.
- **MEG vs EEG**: MEG gave more than a 2× improvement over EEG on the same task, with CER 29% vs 65% ([v1](../sources/brain2qwerty-v1.md)).
- **Where the signal comes from**: source reconstruction at keystroke time shows bilateral **primary motor cortex (M1) and SMA**, stronger in the right hemisphere. There is weaker residual activity in left frontal and temporo-parietal language areas ([v2](../sources/brain2qwerty-v2.md), Fig. 1A, S1).
- **Practical constraints**: everything near the scanner has to be non-magnetic. That is why both studies used a custom HybridMojo keyboard with silver springs. The scanner is large and costs millions, which the authors acknowledge makes it "inaccessible to most patients".
- **Sensor count**: decoding degrades gracefully as sensors are removed. With 153 of 306 sensors, WER rises by only about 6 points ([v2](../sources/brain2qwerty-v2.md), Table 2). See [OPM-MEG](opm-meg.md).

> **Our take:** The obstacle to taking MEG out of the lab is cost and form factor, not signal quality. So the hardware question reduces to whether [OPM-MEG](opm-meg.md) can match it. That makes "how few sensors do you really need?" a research question we can work on from software.

Related: [EEG](eeg.md) · [OPM-MEG](opm-meg.md) · [BrainModule](brainmodule.md)
