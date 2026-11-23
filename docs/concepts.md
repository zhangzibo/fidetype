# Concepts

The main ideas of Fidetype and its data format NTS: streams and events, profiles, bindings, the trust layer, conformance and the Collector.

**Status:** the NTS format is a Release Candidate: [NTS 1.0 RC4](../spec/nts-1.0-rc4.md) is a draft for public comment. The trust layer is Alpha ([status levels](glossary.md#status-levels)).

This page explains the main ideas of NeuralTextStream (NTS) and Fidetype. It is informative. Short meanings of all terms are in the [glossary](glossary.md). The rules are in the spec, [NTS 1.0 RC4](../spec/nts-1.0-rc4.md) (draft). Each section below links to the spec section that defines it.

## The problem NTS solves

A neural input decoder turns brain or muscle signals into text, intents or control signals. Each decoder has its own output. So each consumer (an app, a UI, a benchmark, a safety check) must be written again for each decoder. NTS is one output contract for all of them. A decoder writes NTS once. Any consumer reads it.

NTS borrows its structure from [OpenTelemetry](https://opentelemetry.io/): a data model with semantic conventions, several transport bindings, SDKs, a Collector, a conformance suite and an enhancement-proposal process. It does not use OpenTelemetry code or text.

## Data model

A stream has one **header** and a sequence of typed **events** ([spec section 2.2](../spec/nts-1.0-rc4.md#22-stream-model)).

| Event | Content | Profile |
|---|---|---|
| `header` | Spec version, vocabulary, source, `meta`, clock, declarations | core |
| `frame` | A probability distribution over the vocabulary at one time (dense or sparse) | core |
| `segment_end` | The end of a segment: utterance, word or trial | core |
| `end` | The end of the stream | core |
| `signal_quality` | The quality of the input signal (separate from confidence) | core |
| `decision` | One discrete label with a score and its semantics | core |
| `hypothesis` | A text n-best list, with revisions and evidence | text |
| `intent`, `intent_feedback` | Discrete intents with risk classes | intent |
| `control`, `control_enable`, `pointer` | Continuous control with units, frame and uncertainty | control |
| `trust_decision` | The output of a trust layer | text, intent, control |

**Vocabulary.** The header declares the vocabulary and its type: characters, keys, words, phonemes or commands. A frame gives one probability per vocabulary entry. NTS does not depend on one modality or one vocabulary.

**Semantic conventions.** `meta` keys such as `device.modality`, `decoder.name`, `decoder.causal` and `data.derived` describe the source in a standard way ([spec 3.4](../spec/nts-1.0-rc4.md#34-semantic-conventions-for-meta)).

**No raw signal.** A stream carries decoder output only, never the raw recording ([spec 10.2](../spec/nts-1.0-rc4.md#102-no-raw-signal-in-the-stream)). Decoded text is personal data ([spec 10.3](../spec/nts-1.0-rc4.md#103-personal-data)).

## Output profiles

A profile adds event kinds to the core. It never changes a core field ([spec 7](../spec/nts-1.0-rc4.md#7-output-profiles)).

| Profile | Use | Proposal |
|---|---|---|
| Core | Frames, segments, signal quality: every stream | v0.1 |
| Text | Typed or spoken text: hypotheses and text decisions | FEP-0001 ([FEP](glossary.md#fep) = enhancement proposal) |
| Intent | Discrete commands with risk classes, confirmation and undo | FEP-0003 |
| Control | Continuous control (cursor, gain), with safety rules: hold and stop | FEP-0005 |

## Bindings

| Binding | Form | Defined in |
|---|---|---|
| JSON Lines (`.jsonl`) | One JSON event per line; the default file form | [spec 8.1](../spec/nts-1.0-rc4.md#81-files) |
| NPZ (`.npz`) | NumPy archive of a whole stream; compact for dense frames | [spec 8.1](../spec/nts-1.0-rc4.md#81-files) |
| LSL `nts-lsl/0.1` | Lab Streaming Layer streams, with clock correction and gap rules | [FEP-0002](../spec/feps/0002-nts-over-lsl.md) |
| WebSocket `nts-ws/0.1` | Framing, order, resume, back-pressure and a decisions channel | [FEP-0004](../spec/feps/0004-nts-over-websocket.md) |

The proto3 files in [`spec/proto/`](../spec/proto/README.md) describe the full 1.0 data model. The JSON Schema in `spec/schemas/nts-v1.schema.json` is generated from them.

## Trust layer

Decoders make errors. Their language models can also write fluent text that the person did not intend. The trust layer sits between the decoder and the user. For each utterance, it emits one final `trust_decision` ([spec 6](../spec/nts-1.0-rc4.md#6-trust-decisions)):

| Action | Meaning |
|---|---|
| `COMMIT` | Use the text. `shown[0]` is the committed text |
| `OFFER` | Show the user a short list of candidates |
| `ASK` | Ask the user to try again |
| `ABSTAIN` | Use nothing |

How it decides:

| Part | Job |
|---|---|
| Calibration | Make the decoder's confidence match its real accuracy |
| Conformal sets | Give a candidate set with a coverage guarantee on held-out data |
| Hallucination guard | Detect text that the language model wrote without support from the signal |
| Decision policy | Map the scores to an action, with a commit gate (no blank COMMIT, rule TD-9) |
| Frozen configuration | All thresholds in one file with a content id (`config_id`). Each decision names it, so an auditor can reproduce it |

Rules that every consumer must follow: act only on a final decision (`is_final = true`); forward only a final COMMIT with a non-empty text, or a user choice after an OFFER. The SDKs give a `DecisionTracker` that applies these rules.

**Limit.** A trust configuration holds its guarantee only for the decoder and the user it was calibrated with.

## Conformance

The conformance suite checks producers and consumers against golden vectors ([spec 9](../spec/nts-1.0-rc4.md#9-conformance)).

| Level (producer) | Adds |
|---|---|
| `core` | Every MUST rule that a validator can check |
| `trust-ready` | The SHOULD rules that a trust layer needs: `source`, `device.modality`, `decoder.causal`, `data.derived`, `language` |
| `provenance` | Stream id, decoder name and version, weights hash, calibration id, pseudonymous ids |

The suite has one profile per area (`v0.1`, `fep-0001` … `fep-0005`). The Python, TypeScript and Rust SDKs must give the same verdict on every vector and on fuzzed variants of them. How to run it: [conformance.md](conformance.md).

## Collector

The Collector is one service that reads NTS from several sources, runs processors on it and writes the results to several targets. It copies the structure of the OpenTelemetry Collector: receivers → processors → exporters, wired in pipelines by one configuration file. Guide: [collector.md](collector.md). Design: [FEP-0006](../spec/feps/0006-collector.md).

## How the spec changes

A change to the spec needs a FEP (Fidetype Enhancement Proposal). FEPs have a lifecycle: Draft, Under review, Accepted, Implemented, Final (or Rejected / Withdrawn) ([spec 11.6](../spec/nts-1.0-rc4.md#116-change-process-and-fep-lifecycle)). The process is in [GOVERNANCE.md](../GOVERNANCE.md#4-spec-changes-feps).

## Related projects

| Project | What it is | Relation to NTS |
|---|---|---|
| OpenTelemetry | Vendor-neutral telemetry for software | The structural model for NTS |
| Lab Streaming Layer (LSL) | Transport for time series and markers, with clock sync | A transport; NTS defines the content (FEP-0002) |
| BCI2000 | A general BCI research platform | A full system; it could emit NTS as its decoder output |
| BIDS | A storage standard for neuroimaging datasets | Covers recorded data at rest; NTS covers decoder output |

## Terms

| Term | Meaning |
|---|---|
| Producer | Software that writes NTS (a decoder, an adapter, a bridge) |
| Consumer | Software that reads NTS (an app, a trust layer, a benchmark) |
| Golden vector | A small synthetic test file with an expected verdict (accept or reject) |
| Decision log | A file of `trust_decision` events only |
| eWPM | Effective words per minute: the rate of correct text, with the time for corrections included. The benchmark compares it with a no-BCI baseline |
| FEP | Fidetype Enhancement Proposal |

The full term list is in [spec 1.4](../spec/nts-1.0-rc4.md#14-terms). Plain-language meanings of more terms are in the [glossary](glossary.md).
