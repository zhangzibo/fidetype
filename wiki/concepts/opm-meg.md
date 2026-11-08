---
title: Optically pumped magnetometer MEG (OPM-MEG)
type: concept
tags: [modality, hardware, wearable, meg]
sources: [brain2qwerty-v1, brain2qwerty-v2]
updated: 2026-11-07
---

# OPM-MEG (wearable MEG)

OPM-MEG builds MEG from **optically pumped magnetometers**, quantum sensors that work **at room temperature**. Because they need no cryogenics, they can be mounted in a flexible helmet worn on the head (Boto et al. 2018, *Nature*; Schofield et al. 2022). Typical arrays have **50–150 sensors** ([v2](../sources/brain2qwerty-v2.md), §A.4).

## Why it matters here
Both Brain2Qwerty papers name OPM-MEG as the route to a practical device ([v1](../sources/brain2qwerty-v1.md), Discussion; [v2](../sources/brain2qwerty-v2.md), Discussion). v2's sensor ablation gives the first estimate of how much headroom there is:

| Sensors (out of 306) | WER |
|---|---|
| 306 (full) | 0.433 |
| 230 | 0.467 |
| 153 | 0.490 |
| 76 | 0.547 |

These numbers come from a single LoRA with r = 2 ([v2](../sources/brain2qwerty-v2.md), Table 2).

The authors also suggest that an *optimised* sensor selection, rather than the random subset they tested, could do better.

> **Caveat:** These are *subsets of cryogenic SQUID sensors*. Real OPMs differ in noise, bandwidth, placement, and in motion and field artefacts. Nobody has yet shown typing decoding on actual OPM hardware.

> **Our take:** We can do sensor-selection and simulated-OPM research entirely in software on the public data. To be checked: OPM vendors such as Cerca/QuSpin, and whether any public OPM datasets exist.

Related: [MEG](meg.md) · [EEG](eeg.md)
