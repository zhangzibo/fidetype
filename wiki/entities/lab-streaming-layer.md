---
title: Lab Streaming Layer (LSL)
type: entity
tags: [standard, streaming, real-time, tooling]
sources: [case-study-opentelemetry, neural-input-landscape-2026]
updated: 2026-11-12
---

# Lab Streaming Layer (LSL)

LSL is the de facto tool for real-time streams in neuroscience labs. It comes from SCCN at UCSD. It moves raw signals (EEG, markers, other sensors) between programs with time synchronisation. It does not define a format for decoder output ([OpenTelemetry case study](../sources/case-study-opentelemetry.md#bci-and-neuro-standards)).

- **Governance:** we found no formal governance document. **UNVERIFIED.**
- **Licence:** liblsl is MIT (https://github.com/sccn/liblsl). Recordings use the XDF file format ([landscape report](../sources/neural-input-landscape-2026.md#devices-and-sdks)).
- **Decoder output today:** probabilities appear in LSL streams only by convention. No stream type defines them.
- **Use in Fidetype:** the LSL adapter is done (M6-01, 2026-11-12): [LSL input](../concepts/lsl-input.md). It reads LSL streams into the streaming trust layer and publishes NTS files and trust decisions on LSL. The architecture lists LSL for live devices in layer 1 ([architecture](../questions/architecture.md#the-six-layers)).
- **pylsl** (the Python binding) 1.18.6 is MIT. Its Windows wheel includes liblsl (checked 2026-11-12).

> **Our take:** LSL carries the raw signal. NeuralTextStream carries the decoder output. They fit together. We bridge to LSL (an adapter, and possibly an LSL stream type for NeuralTextStream). We do not compete with it. See the [open-source playbook](../questions/open-source-playbook.md).

## NTS over LSL (binding idea)
NeuralTextStream v0.1 lists "NTS over LSL" as a binding ([spec](../../spec/neuraltextstream-v0.1.md); [landscape report](../sources/neural-input-landscape-2026.md#spec-implications)). The idea:
- An NTS stream is an LSL stream with its own declared stream type.
- LSL gives the transport and clock synchronisation. NTS gives the payload: `frame` and `decision` events, `score_semantics`, `vocab_id`, and the timing fields (`clock_domain` can name the LSL clock).
- An **LSL ⇄ NTS bridge**, together with a [BrainFlow](brainflow.md) source, is adapter priority 1 ([architecture](../questions/architecture.md#adapter-priority-2026-11-08)). Both are MIT.

Implemented in M6-01: a frames stream (type `NTS`) plus a `Markers` stream with JSON events; the NTS header sits in the desc ([LSL input](../concepts/lsl-input.md#nts-over-lsl-spec-64-as-implemented)).

> **Our take:** This binding gives us the lab ecosystem at almost no cost. Existing LSL tools (recorders, viewers, XDF files) then carry NTS without changes. The open detail is how to pack variable-length events (n-best lists) into LSL samples. A string channel with JSON is the simple first answer.

Related: [BIDS](bids.md), [IEEE P2731](ieee-p2731.md), [BrainFlow](brainflow.md), [Apple BCI HID](apple-bci-hid.md).
