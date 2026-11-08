---
title: Apple BCI HID (Brain Control Interface HID reference)
type: entity
tags: [standard, hid, implant, apple, accessibility, switch-control]
sources: [neural-input-landscape-2026]
updated: 2026-11-08
---

# Apple BCI HID

https://developer.apple.com/documentation/accessibility/brain-computer-interface-hid-reference-for-connecting-to-apple-platforms

Apple BCI HID is Apple's reference for how a brain-computer interface connects to Apple platforms as a HID device. It is the closest existing neural standard to NeuralTextStream ([landscape report](../sources/neural-input-landscape-2026.md#novelty-verdict)).

| Item | Value |
|---|---|
| Platforms | iOS, iPadOS and visionOS 26 |
| Usage Page | 0x60, "Brain Control Interface" |
| Status | Vendor-documented. We found no USB-IF HUT entry |
| Known user | Synchron: Switch Control through BCI HID (Aug 2025 demo) |
| Text | None |
| N-best | None |
| Provenance | None |

## Report breakdown
| Report | Content | Fields | Notes |
|---|---|---|---|
| **1. Signal quality** | Neural activity strength per button | [button id, neural activity strength 0–255] | This is **strength, not probability** |
| **2. Buttons** | Discrete switch presses | 32 button bits | Mapped to Switch Control actions |
| **3. Pointer** | Cursor movement | 1D, 2D or 3D; relative or absolute | −128 means the axis is absent |
| **4. Scan context** | State of the Switch Control scan | selected item, item count, seed, control type, uiScanningLatency | Gives the device context for its decoder |

## Mapping to NeuralTextStream
| BCI HID | NeuralTextStream (spec v0.1, Development features) |
|---|---|
| Report 1 strength | `signal_quality`, or a `decision` score with `score_semantics=strength`. Not a confidence |
| Report 2 buttons | `decision` events over the vocabulary `hid.bci.switch` |
| Report 3 pointer | `pointer` event |
| Report 4 scan context | Context fields for the trust core |
| — | NTS → HID bridge is lossy: HID has no field for n-best, probability or provenance |

See [NeuralTextStream v0.1](../../spec/neuraltextstream-v0.1.md).

> **Our take:** BCI HID is a control protocol, not a text or confidence format. Its strength byte has no declared meaning as a probability. So a trust layer cannot calibrate it directly. But every implant vendor that targets Apple must speak it. An NTS → HID bridge and an HID → NTS logger put NeuralTextStream next to these vendors at low cost. This is adapter priority 2 ([architecture](../questions/architecture.md#adapter-priority-2026-11-08)).

Related: [W3C EMMA](w3c-emma.md), [IEEE P2731](ieee-p2731.md), [Lab Streaming Layer](lab-streaming-layer.md).
