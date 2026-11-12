---
title: Direction decision — trustworthy neural text entry
type: question
tags: [planning, decision, directions, licence, market, scope, standard, intent, benchmark]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code, case-study-opentelemetry, neural-input-landscape-2026]
updated: 2026-11-11
---

# Direction decision (2026-11-07)

**Question asked:** Which direction does the project take?

## The decision
The project direction is **trustworthy neural text entry**. We build a decoder-agnostic layer that makes text from any neural decoder (MEG, EEG, wrist EMG, implants) reliable. The layer:
- calibrates confidence,
- abstains or asks when it is not sure,
- offers n-best choices,
- guards against LLM hallucination,
- works in real time (causally).

The direction is a research program (papers on public data). It is also a possible future product or acquisition target.

The design is in [architecture.md](architecture.md). The earlier options are in [research-directions.md](research-directions.md).

## Evidence
We did three research checks on 2026-11-07.

### 1. Novelty
- A NeurIPS 2025 workshop paper (Huang, Narasimha, Patel, Mishne, Gilja, "Prototyping Co-Control BCIs Through Brain-to-Text") found that brain-to-text decoders are poorly calibrated.
- Nobody has built calibrated or abstaining sentence decoding for MEG/EEG. We found no such work.
- We found no public causal (streaming) MEG/EEG text decoder. Brain2Qwerty v2 states that it is not causal ([v2](../sources/brain2qwerty-v2.md); [sync vs async](../concepts/synchronous-vs-asynchronous-decoding.md)).
- Meta's NeuralBench (arXiv 2605.08495) already has per-keystroke typing tasks. But it measures only classification accuracy. It does not measure sentence-level CER/WER ([error metrics](../concepts/error-metrics.md)).

> **Our take:** The gap is in the layer after the decoder. Calibration, abstention and causal decoding are open for non-invasive text entry.

### 2. Commercial landscape
*Some figures in this section come from secondary sources (news and reports). We have not checked them against primary documents.*

- Decoder and foundation-model companies compete on decoding, not on this layer:
  - Sabi: $50M seed, October 2026 *(secondary source)*.
  - Hemispheric: $52M *(secondary source)*.
- Possible buyers or partners:
  - **Meta Reality Labs**: Neural Band (wrist EMG).
  - **Apple**: BCI HID protocol (May 2025); a reported Sonera acquisition in 2026 *(secondary source)*.
  - **Synchron**, **Cognixion**, **Neurable**.

> **Our take:** A layer that works with any decoder is useful to all of these companies. It does not compete with their decoders. This makes it a possible partner product or acquisition target.

### 3. The licence trap
- SpanishBCBL, emg2qwerty and LibriBrain are all **CC BY-NC** ([SpanishBCBL](../entities/spanishbcbl-dataset.md), [emg2qwerty](../entities/emg2qwerty.md)).
- Meta's Brain2Qwerty code is also CC BY-NC ([code](../sources/brain2qwerty-code.md)).
- **Rule:** use NC data only for research and benchmarks. Product model weights must come only from CC0 data (the OpenNeuro default) or our own consented data.
- **Rule:** keep a provenance ledger that records which data trained which weights.

> **Our take:** The trust layer helps here. Much of it (calibration, policy, simulator, metrics) needs little or no neural training data. So the product part depends less on NC data than a decoder would.

## Scope decision (2026-11-08): neural input, OpenTelemetry-level
**Question asked:** How big is the project?

### The decision
On 2026-11-08 the user decided that Fidetype is a big project, at the level of OpenTelemetry ([OpenTelemetry case study](../sources/case-study-opentelemetry.md)).

| | Scope |
|---|---|
| **From** | A trust layer for research brain-to-text (MEG). |
| **To** | **The vendor-neutral standard and trust layer for neural input.** |

"Neural input" means text or intent that a decoder gets from any neural or biosignal device:
- consumer wrist EMG (for example, Meta Neural Band),
- EEG headsets,
- MEG and OPM-MEG ([OPM-MEG](../concepts/opm-meg.md)),
- implants (Synchron, Neuralink and others), through interfaces such as Apple's BCI HID protocol.

Research MEG ([SpanishBCBL](../entities/spanishbcbl-dataset.md)) stays the credibility base. It is also the hardest test case for Paper 1. The ceiling of the project comes from consumer neural input.

### Reasons
1. **Market ceiling.** Consumer EMG, EEG and implant input is a much larger market than research MEG.
2. **No standard exists.** We know of no standard for decoded output with confidence.
3. **The standards gap is open.** IEEE P2731 (a BCI standard project) started in 2018. It has no published standard.

**Novelty check (2026-11-08).** A landscape search confirmed reason 2 ([neural input landscape report](../sources/neural-input-landscape-2026.md#novelty-verdict)). No standard for decoded neural output with confidence exists. Existing work covers raw data (BIDS, ISO/IEC TS 27571, NWB), transport (LSL/XDF), terminology (IEEE P2731, P2794) and vendor control. The closest are:
- [Apple BCI HID](../entities/apple-bci-hid.md): the closest neural standard. It has a strength byte, buttons and a pointer, but no text, no n-best and no provenance.
- [W3C EMMA 1.0](../entities/w3c-emma.md): the closest non-neural precedent. It has confidence, n-best lists and timestamps, but not for neural input.

The positioning is: **NTS = "EMMA for neural input, OpenTelemetry-style".**

### Implications
1. **NeuralTextStream becomes modality-agnostic and vocabulary-agnostic.** A stream can carry chars, keys, words, phonemes or commands. The spec gets OTel-style semantic conventions, for example `device.modality` and `decoder.causal`. Spec v0.1: [neuraltextstream-v0.1.md](../../spec/neuraltextstream-v0.1.md).
2. **Adapters for all modalities are first-class.** EMG, EEG and implants get adapters, not only MEG ([architecture](architecture.md)).
3. **Governance.** The project is founder-led now. A written path leads to neutral governance and a foundation (LF AI & Data or NumFOCUS). See GOVERNANCE.md in the repo root ([open-source playbook](open-source-playbook.md)).
4. **Success metric.** We count the decoders and devices that emit NeuralTextStream. We do not count stars.
5. **Licence-clean data is more important now.** Product weights need CC0 or CC BY data, or our own data. The EMG dataset [emg2qwerty](../entities/emg2qwerty.md) is CC BY-NC, so it is for research only ([licence trap](#3-the-licence-trap)).
6. **Time and resources.** The user accepts that this takes years. It also needs outside partners, people and funding. The 1-week targets in the [project plan](project-plan.md) apply to building the code, not to adoption.

### Risks
| Risk | Effect | Mitigation |
|---|---|---|
| **Spread too thin** | One developer cannot build adapters for every modality. | Research MEG and Paper 1 come first. Add adapters one at a time: EMG first. Ask device makers to write their own adapters against the spec. |
| **Data licences** | Most public neural typing data is NC. | Provenance ledger. CC0/CC BY data or own consented data for product weights. |
| **Big players build their own** | Meta, Apple or an implant company can define their own format. | Stay vendor-neutral. Make adoption cheap (a small spec, adapters, a conformance test suite). Offer the spec to a neutral foundation. |

> **Our take:** The wide scope changes the target, not the first steps. The code for Paper 1 (MEG, trust core, benchmark) is the same. The difference is that every interface must now work for any modality and any vocabulary. The largest risk is adoption: a spec has value only when other people emit it. So the first external decoder that emits NeuralTextStream is a more important milestone than any feature.

## Scope note (2026-11-11): intent beyond text and a benchmark hub
**Decision (user, 2026-11-11):** the long-term roadmap explicitly includes two items. Priorities do not change. Text entry stays first. The user said: "if it is part of the roadmap anyway, then let's include it, no need to change prio."

| Item | Content | Roadmap phase |
|---|---|---|
| **Intent beyond text** | Cursor movement (continuous 2D), clicks and selections, commands (wheelchair, robot arm, smart home), decoded speech. The trust layer generalises: COMMIT / OFFER / ABSTAIN for discrete intents; confidence-gated, rate-limited actuation for continuous control (velocity scaling, dead-man hold, safe-stop). A modality- and output-agnostic core with output profiles (text, discrete intent, continuous control), with no breaking change to the text profile. Target interface: [Apple BCI HID](../entities/apple-bci-hid.md). | [P12](roadmap-standard.md#p12-beyond-text-intent-and-control-added-2026-11-11), 2027-07 → 2027-12 |
| **Public benchmark hub** | A public, reproducible leaderboard ("ImageNet for BCI text entry", later all intent): replay adapters for standard datasets, CER / WER, eWPM, wrong-commit rate, CRC / LTT guarantee reports, shuffled and zeros controls, NeuralTextStream submissions, a static site. It extends the P6 leaderboard. | [P13](roadmap-standard.md#p13-public-benchmark-hub-added-2026-11-11), 2027-07 → 2027-12 |

Both phases come at the end of the order. P1–P11 keep their order and dates.

> **Our take:** This makes the 2026-11-08 definition of "neural input" ("text or intent") explicit in the plan. It changes no near-term work. Spec v0.1 already has `vocab_type = "command"` and a `pointer` event, so the later profiles can grow without a break.

## Rejected or deferred options
| Option | Status | Reason |
|---|---|---|
| Brain foundation models | Rejected | The field is crowded. Funded companies compete there. |
| EMG → brain transfer | Deferred | Novel, but risky. The data is NC. Keep it as a later experiment. |
| Virtual OPM-MEG simulation | Deferred | Novel, but the market is small. Keep it as a later open-source credibility project ([OPM-MEG](../concepts/opm-meg.md)). |

## Constraints that shaped the decision
- No MEG or EEG hardware. Work starts on public data and a simulator.
- Hardware: AMD RX 7800 XT 16 GB (ROCm, not CUDA), Ryzen 7 9800X3D, 31 GB RAM.

## Related pages
- [Architecture](architecture.md)
- [Reading list](reading-list.md)
- [Research directions](research-directions.md)
- [Diagrams](../diagrams/index.html) (diagrams 6–8)
