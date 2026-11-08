---
title: "Neural input landscape 2026 (devices, SDKs, standards, regulation)"
type: source
tags: [landscape, standards, devices, sdk, emg, eeg, implant, hid, licence, regulation, market]
sources: [neural-input-landscape-2026]
updated: 2026-11-08
---

# Neural input landscape 2026

## Citation and links
- **Source:** a research report (agent web research), verified by a research agent on 2026-11-08.
- **Raw source:** research report (agent web research), no raw file saved.
- **Licence:** not applicable (our own report). Each linked page has its own licence.
- **Key links:**
  - Apple BCI HID: https://developer.apple.com/documentation/accessibility/brain-computer-interface-hid-reference-for-connecting-to-apple-platforms
  - Meta Web Apps: https://wearables.developer.meta.com/docs/develop/webapps/build/ ; FAQ: https://developers.meta.com/wearables/faq/
  - Synchron demo: https://www.businesswire.com/news/home/20250804537175/en
  - BrainFlow: https://github.com/brainflow-dev/brainflow
  - Emotiv Cortex: https://emotiv.gitbook.io/cortex-api/data-subscription/data-sample-object
  - Neurosity predictions: https://docs.neurosity.co/docs/api/predictions
  - liblsl: https://github.com/sccn/liblsl
  - Dryad datasets: doi:10.5061/dryad.wh70rxwmv (Willett handwriting), doi:10.5061/dryad.dncjsxm85 (Card / Brain-to-Text '25)

## TL;DR
**No standard for decoded neural output that carries confidence exists.** Current standards cover raw data, transport, terminology and vendor-specific control. The closest neural standard is [Apple BCI HID](../entities/apple-bci-hid.md). It has no text, no n-best and no provenance. The closest non-neural precedent is [W3C EMMA 1.0](../entities/w3c-emma.md). It has confidence, n-best lists and timestamps for speech and multimodal input. Of the consumer SDKs, only Neurosity gives an explicit per-label probability. The only commercially clean decoded-text data we found is the CC0 [Dryad intracortical datasets](../entities/dryad-intracortical-datasets.md).

## Novelty verdict
Existing work covers only these layers:

| Layer | Existing work | Covers decoded output with confidence? |
|---|---|---|
| Raw data at rest | [BIDS](../entities/bids.md); ISO/IEC TS 27571:2026 (non-invasive BCI raw data, JTC 1/SC 43; status **UNVERIFIED**, iso.org returned 403); NWB | No |
| Transport | [LSL / XDF](../entities/lab-streaming-layer.md) | No. Probabilities appear only by convention |
| Terminology and reporting | [IEEE P2731](../entities/ieee-p2731.md), IEEE P2794 | No |
| Vendor-specific control | [Apple BCI HID](../entities/apple-bci-hid.md) | No. Signal strength only, no probability |
| Non-neural precedent | [W3C EMMA 1.0](../entities/w3c-emma.md) (Recommendation, 2009) | Yes, for speech and multimodal input. Not for neural input |

The positioning is: **NTS = "EMMA for neural input, OpenTelemetry-style"** ([OpenTelemetry case study](case-study-opentelemetry.md)).

## Devices and SDKs
| Device / SDK | Modality | What it exposes | Probabilities? | Transport / format | Third-party decoder? | Licence | Source |
|---|---|---|---|---|---|---|---|
| [Meta Neural Band](../entities/meta-neural-band.md), Web Apps (developer preview, May 2026) | sEMG (wrist) | Gestures as arrow-key and Enter DOM events. Opt-in pinch-and-drag. Text from the on-glasses handwriting composer | No. No confidence, no n-best | DOM events in a web app | No. Processing is on the band. No raw EMG | Proprietary | wearables.developer.meta.com/docs/develop/webapps/build/ |
| Meta Device Access Toolkit v1.0 (Sept 2026) | — | No band gestures | No | — | No | Proprietary | developers.meta.com/wearables/faq/ |
| "Lumen" (Oct 2026), unofficial reverse-engineered client | sEMG | **UNVERIFIED** | **UNVERIFIED** | **UNVERIFIED** | **UNVERIFIED** | **UNVERIFIED** | — |
| Meta datasets: [emg2qwerty](../entities/emg2qwerty.md), generic-neuromotor-interface, emg2pose | sEMG | Raw EMG, HDF5 at 2 kHz | Not applicable (data) | HDF5 | Yes (research) | CC-BY-NC-4.0; emg2pose CC-BY-NC-SA-4.0. **Not commercially usable** | — |
| Synchron | Implant (endovascular) | Switch Control through [Apple BCI HID](../entities/apple-bci-hid.md) (Aug 2025 demo) | No | Apple BCI HID | No SDK | Proprietary | businesswire.com/news/home/20250804537175/en |
| Neuralink, Precision, Paradromics | Implant | No public SDK found | — | — | No | Proprietary | — |
| [BrainFlow](../entities/brainflow.md) | EEG and other biosignals | Uniform API for raw data across many boards (OpenBCI, Muse, Unicorn; Neurosity per the board list, **UNVERIFIED**) | ML module gives scalar scores only | Library API | Yes | MIT | github.com/brainflow-dev/brainflow |
| Emotiv Cortex | EEG | `com` stream: {act, pow 0–1}, top-1 only. Raw EEG needs a paid licence | Power score, top-1 only | JSON-RPC over WebSocket | Limited | Proprietary | emotiv.gitbook.io/cortex-api/data-subscription/data-sample-object |
| Neurosity Crown | EEG | `predictions`: {probability, label, timestamp, metric} | **Yes. The only consumer SDK with explicit per-label probability** | SDK | Yes | MIT (believed; **UNVERIFIED**) | docs.neurosity.co/docs/api/predictions |
| Neurable | EEG | No public API (OEM model) | — | — | No | Proprietary | — |
| Muse | EEG | SDK discontinued for new users. Raw data through Mind Monitor (OSC), BrainFlow or muse-lsl | No | OSC, LSL | Yes (raw) | Varies | — |
| g.tec Unicorn | EEG | Raw EEG and a P300 speller (details **UNVERIFIED**) | **UNVERIFIED** | **UNVERIFIED** | Yes (raw) | Proprietary | — |
| Cognixion Axon-R | EEG (research headset) | LSL output. Not FDA cleared | — | LSL | Yes | Proprietary | — |
| [LSL / XDF](../entities/lab-streaming-layer.md) | Any | Real-time streams and recordings | Only by convention | LSL, XDF | Yes | MIT (liblsl) | github.com/sccn/liblsl |
| Timeflux, BCI2000, OpenViBE, MNE-LSL | Middleware | Classifier outputs stay internal | Internal only | Various | Yes | **UNVERIFIED** | — |
| [BIDS](../entities/bids.md) | Data at rest | No schema for decoded output. EMG (BEP042) finished review in Oct 2025; merge unconfirmed | No | Files | — | — | — |

## Spec implications
These are being folded into [NeuralTextStream v0.1](../../spec/neuraltextstream-v0.1.md) as Development features.

| Area | Implication |
|---|---|
| Event kinds | Two kinds: `frame` (a distribution per frame) and `decision` (label, score, `score_semantics` ∈ `calibrated_prob` \| `uncalibrated_prob` \| `power` \| `strength` \| `none`) |
| N-best | Optional `nbest[]` with `is_final` and `revision_of` (as in EMMA `one-of`) |
| Vocabularies | `vocab_id` and `vocab_version` with namespaced registries: `char`, `phoneme`, `hid.bci.switch`, `gesture`, `mi` |
| Pointer | A `pointer` event that maps to Apple BCI HID Report 3 |
| Timing | `t_signal_start`, `t_signal_end`, `t_decoded`, `t_emitted`, `clock_domain` |
| Signal quality | `signal_quality` is separate from confidence (Apple Report 1 is strength, not probability) |
| Conventions | `device.invasive`, `device.regulatory_status`, `decoder.calibration_id`, `decoder.calibration_method`, `lm.name`, `user.personalized` |
| Privacy | `data.derived`, `consent.ref` |
| Bindings | NTS over LSL; an NTS → HID bridge (lossy); WebSocket JSON |

## Top adapters
| Priority | Adapter | Why | Licence status |
|---|---|---|---|
| 1 | **LSL ⇄ NTS bridge plus a BrainFlow source** | Most reach for the least effort | Both MIT |
| 2 | **NTS → Apple BCI HID bridge, and an HID-report → NTS logger** | Puts NTS in front of every implant vendor that targets Apple, Synchron first | Apple docs are vendor documentation. Our code is our own |
| 3 | **Offline replay of the Dryad intracortical datasets** | Willett handwriting, Brain-to-Text '24, Card / Brain-to-Text '25 (with a pretrained RNN) | **CC0. The only commercially clean decoded-text data found** |
| Later | Neurosity and Emotiv adapters | The only consumer SDKs with probability-like scores | Neurosity MIT (**UNVERIFIED**); Emotiv proprietary |
| Later | Meta Web Apps shim with `score_semantics=none` | Gestures and text from the band, with no score | Proprietary platform |

## Data warning
- All Meta EMG data is NC: [emg2qwerty](../entities/emg2qwerty.md) and generic-neuromotor-interface are CC-BY-NC-4.0; emg2pose is CC-BY-NC-SA-4.0.
- LibriBrain is CC-BY-NC-4.0.
- The BNCI P300 and ErrP sets that were checked are CC-BY-NC-ND-4.0.
- The OpenBMI licence listings conflict.
- OpenNeuro is assumed CC0 by policy. **UNVERIFIED.**
- The Dryad intracortical deposits are CC0 ([Dryad datasets](../entities/dryad-intracortical-datasets.md)).

## Regulatory angle
| Area | Fact |
|---|---|
| FDA | The 2021 implanted-BCI guidance treats implanted BCIs as significant-risk devices. The 2023 device-software guidance applies, at "Enhanced" documentation |
| US state neural-data laws | Colorado HB24-1058 (Aug 2024); California SB 1223 (CCPA regulations from 1 Jan 2026); Montana SB 163 (Oct 2025); Connecticut SB 1295 (Jul 2026); Delaware HB 380 (Jan 2027, **UNVERIFIED**) |
| US federal | The MIND Act (S.2925) is pending |
| EU AI Act | Emotion recognition is banned in workplaces and education. Attention measurement may count as emotion recognition |
| EU other | Medical BCIs also fall under the MDR and GDPR |
| Standards venues for NTS | ISO/IEC JTC 1/SC 43 work items; the joint CEN-CLC BCI committee proposed in late 2025 |

## Market signals
- EssilorLuxottica sold 7M+ Meta glasses in 2025 (all models).
- Ray-Ban Display is the only model with the band. It ships in the low tens of thousands per quarter. Estimates: about 15k in the launch quarter and about 21.6k in Q2 2026 (**UNVERIFIED**).

## Limitations
- This is a web-research report, not a primary document. Several claims are marked **UNVERIFIED**.
- iso.org returned 403, so the ISO/IEC TS 27571 status is not confirmed.
- Proprietary SDK details can change without notice.

> **Our take:** The gap is real and specific. Every device gives either raw data or a top-1 decision with a score of unknown meaning. Nobody declares what the score means. So `score_semantics` is the single most important field in the spec: a trust core cannot calibrate a score until it knows whether the score is a probability, a power or a strength. The Apple HID bridge is the strategic adapter, because implant vendors already target it. The LSL/BrainFlow bridge is the cheap adapter, because it reaches many EEG devices at once. The Dryad CC0 data is the key data asset, because it lets us evaluate the trust layer on real decoded text with no licence trap. The consumer EMG band is the largest market, but today it exposes no scores, so a trust layer can do little with it until Meta opens more.

## Feeds these pages
- Entities: [Apple BCI HID](../entities/apple-bci-hid.md), [W3C EMMA](../entities/w3c-emma.md), [Meta Neural Band](../entities/meta-neural-band.md), [BrainFlow](../entities/brainflow.md), [Dryad intracortical datasets](../entities/dryad-intracortical-datasets.md), [emg2qwerty](../entities/emg2qwerty.md), [Lab Streaming Layer](../entities/lab-streaming-layer.md), [IEEE P2731](../entities/ieee-p2731.md), [BIDS](../entities/bids.md).
- Questions: [Architecture](../questions/architecture.md#adapter-priority-2026-11-08), [Project plan](../questions/project-plan.md#m6-device-adapters-target-11-14--11-15), [Direction decision](../questions/direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level).
