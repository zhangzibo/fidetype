---
title: BrainFlow
type: entity
tags: [sdk, eeg, biosignals, open-source, tooling]
sources: [neural-input-landscape-2026]
updated: 2026-11-08
---

# BrainFlow

https://github.com/brainflow-dev/brainflow

BrainFlow is an open-source library with one uniform API for raw data from many biosignal boards ([landscape report](../sources/neural-input-landscape-2026.md#devices-and-sdks)).

| Item | Value |
|---|---|
| Licence | MIT |
| Boards | Many, for example OpenBCI, Muse and Unicorn. Neurosity is in the board list (**UNVERIFIED**) |
| Output | Raw data |
| ML module | Scalar scores only. No distributions, no n-best |

> **Our take:** BrainFlow plus an LSL ⇄ NTS bridge is adapter priority 1 ([architecture](../questions/architecture.md#adapter-priority-2026-11-08)). Both are MIT, so the licence is clean. One BrainFlow source reaches many EEG boards at once. BrainFlow gives raw data, so our own decoder or a third-party decoder must produce the NTS events.

Related: [Lab Streaming Layer](lab-streaming-layer.md).
