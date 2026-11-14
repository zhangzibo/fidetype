---
title: BrainFlow
type: entity
tags: [sdk, eeg, biosignals, open-source, tooling]
sources: [neural-input-landscape-2026]
updated: 2026-11-13
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

The BrainFlow board docs (checked 2026-11-12) show a Synthetic board and a Streaming board, and do not mention LSL.

## Fidetype bridge (M6-08)
`fidetype.adapters.brainflow_bridge` is our own BrainFlow → LSL bridge (Apache-2.0; no BrainFlow code copied). `brainflow` is an optional extra.

| Item | Value |
|---|---|
| Install | `pip install "fidetype[lsl,brainflow]"` |
| Tested version | brainflow 5.24.0 (PyPI wheel, Windows 11). Licence MIT (`LICENSE.txt` in the wheel) |
| Synthetic board | board id -1, name `Synthetic`: 16 EEG channels (Fz, C3, Cz, C4, Pz, PO7, Oz, PO8, F5, F7, F3, F1, F2, F4, F6, F8), 250 Hz, a timestamp channel and a marker channel |
| Stamps | Unix time per sample, in packets about 16 ms apart (measured). The bridge smooths them before LSL. Since M6-13 it measures the wall-to-LSL offset at each read, so a wall-clock step (Windows time sync: -1,361 ms seen in the soak test) does not shift the stamps (`clock_steps` in the stats) |

Commands:
```
fidetype lsl brainflow-bridge --board synthetic                       # fake EEG, no hardware
fidetype lsl brainflow-bridge --board cyton --serial-port COM3        # a BoardIds name (not tested: no hardware)
fidetype lsl brainflow-bridge --board-id 0 --serial-port /dev/ttyUSB0 # or the numeric board id
fidetype lsl brainflow-bridge --board synthetic --trial-s 4 --pause 20:3 --duration 60 --stats bridge.json
fidetype lsl run --config trust.json --stream-name fidetype.brainflow --signal-decoder toy-flat --decoder demo
```

The bridge sends an `EEG` stream (`desc/fidetype/role = signal`, unit `microvolts`) and a `Markers` stream (`segment_end` every `--trial-s` seconds). Details and the live results: [LSL input, BrainFlow live test](../concepts/lsl-input.md#brainflow-live-test-m6-08) and [results.md](../../experiments/2026-11-13-m6-08-brainflow-live/results.md).

> **Our take:** the M6-08 run showed the full path BrainFlow → LSL → trust layer, with 26 of 26 ABSTAIN on toy input that carries no text information. Fidetype has no EEG text decoder. A real-board test needs hardware (externally blocked).

The M6-13 soak test ran the bridge for 6.78 h + 2.5 h with restarts every 30 min: [LSL input, soak test](../concepts/lsl-input.md#soak-test-m6-13).

Related: [Lab Streaming Layer](lab-streaming-layer.md), [LSL input](../concepts/lsl-input.md).
