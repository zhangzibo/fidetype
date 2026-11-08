---
title: Meta Neural Band (wrist sEMG)
type: entity
tags: [device, emg, consumer, meta, wearable]
sources: [neural-input-landscape-2026]
updated: 2026-11-08
---

# Meta Neural Band

The Meta Neural Band is a consumer wrist sEMG band. It works with the Ray-Ban Display glasses ([landscape report](../sources/neural-input-landscape-2026.md#devices-and-sdks)).

## Developer access
| Path | What it gives | Scores |
|---|---|---|
| **Web Apps** (developer preview, May 2026) | Gestures as arrow-key and Enter DOM events. An opt-in pinch-and-drag. Text from the on-glasses handwriting composer | No confidence, no n-best |
| **Device Access Toolkit v1.0** (Sept 2026) | No band gestures | — |
| **"Lumen"** (Oct 2026), unofficial reverse-engineered client | **UNVERIFIED** | **UNVERIFIED** |

- There is no raw EMG. Processing happens on the band.
- Sources: https://wearables.developer.meta.com/docs/develop/webapps/build/ and https://developers.meta.com/wearables/faq/

## Related datasets
Meta's public EMG datasets are all NC: [emg2qwerty](emg2qwerty.md) and generic-neuromotor-interface (CC-BY-NC-4.0), emg2pose (CC-BY-NC-SA-4.0). All are HDF5 at 2 kHz. **None is commercially usable.**

## Market
- EssilorLuxottica sold 7M+ Meta glasses in 2025 (all models).
- Ray-Ban Display is the only model with the band. It ships in the low tens of thousands per quarter: about 15k in the launch quarter and about 21.6k in Q2 2026 (estimates, **UNVERIFIED**).

> **Our take:** The band is the largest consumer neural-input device, but it is closed. A third party gets DOM events with no score. So the first adapter is only a shim with `score_semantics=none` (a later follow-up in [adapter priority](../questions/architecture.md#adapter-priority-2026-11-08)). The trust layer can add value here only if Meta exposes scores or n-best. The installed base of the band is still small compared with all Meta glasses.

Related: [emg2qwerty](emg2qwerty.md), [Apple BCI HID](apple-bci-hid.md).
