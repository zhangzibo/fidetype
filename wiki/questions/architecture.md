---
title: Architecture of the trustworthy neural text entry layer
type: question
tags: [planning, architecture, calibration, uncertainty, streaming, open-core, adapters, standard]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code, neural-input-landscape-2026]
updated: 2026-11-08
---

# Architecture: trustworthy neural text entry

**Question asked:** How do we build the project direction chosen on 2026-11-07? See [direction-decision.md](direction-decision.md) for why we chose it.

**Diagrams:** open [the diagram page](../diagrams/index.html). Diagrams 6, 7 and 8 show this page:
- `06-architecture-layers`: the six layers.
- `07-data-flow`: the data flow from source to evaluation.
- `08-roadmap-v2`: the research roadmap.

## Goal
We build a layer that makes text from a neural decoder reliable. The layer does not depend on one decoder. It works with MEG, EEG, wrist EMG and implants. It calibrates confidence, it abstains or asks when it is not sure, it offers n-best choices, it guards against LLM hallucination, and it works in real time (causally).

## The six layers
The layers go from the bottom (data in) to the top (shared infrastructure).

| # | Layer | Purpose | Key components |
|---|---|---|---|
| 1 | **Sources / adapters** | Put neural data or decoder outputs from any modality into one standard stream format. | **Now:** offline replay of datasets ([SpanishBCBL](../entities/spanishbcbl-dataset.md) MEG/EEG; OpenNeuro CC0 sets later). A **noisy-decoder simulator**. **Per modality (first-class, see table below):** EMG wristband, EEG SDK (BrainFlow / LSL), MEG, implant / HID bridge. |
| 2 | **Decoders** | Turn neural data into character probabilities. These are research models. They are interchangeable. | Our own reimplementation of a conv + [CTC](../concepts/ctc.md) decoder, under a permissive licence. It has a causal (streaming) mode with a configurable lookahead. Baselines. Any third-party decoder can plug in if it emits the NeuralTextStream format. |
| 3 | **Trust core** | Make the text reliable. This is the heart of the project and the future product. | a. Calibration. b. Streaming LM fusion. c. Uncertainty and conformal sets. d. Hallucination guard. e. Decision policy. (See below.) |
| 4 | **Interaction** | Show the text to a person, or simulate a person. | A UI that shows text with confidence, an n-best picker and correction. A **simulated user** model for offline evaluation (selection time, error-correction cost). |
| 5 | **Evaluation harness / benchmark** | Measure every part with fixed rules. | Fixed splits. Metrics: CER, WER, SemER ([error metrics](../concepts/error-metrics.md)); calibration (ECE, reliability diagrams); conformal coverage; latency; hallucination rate; **effective words per minute**. |
| 6 | **Infrastructure** | Support all other layers. | A dataset registry with a licence tag for each dataset. A **provenance ledger** (which data trained which weights). Config, experiment tracking, ROCm/CPU support. |

### Adapters per modality
The scope decision of 2026-11-08 makes adapters for all modalities first-class ([direction decision](direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level)). Each adapter emits NeuralTextStream.

| Modality | Adapter | Data or device | Status |
|---|---|---|---|
| **EMG wristband** | Dataset replay; a consumer EMG SDK if one is available | [emg2qwerty](../entities/emg2qwerty.md) (CC BY-NC: research only); for example Meta Neural Band | Planned (M6, first) |
| **EEG** | SDK bridge through BrainFlow or Lab Streaming Layer (LSL) | EEG headsets; [SpanishBCBL](../entities/spanishbcbl-dataset.md) EEG for replay | Planned (M6) |
| **MEG / OPM-MEG** | Dataset replay; live through LSL later | [SpanishBCBL](../entities/spanishbcbl-dataset.md) MEG; [OPM-MEG](../concepts/opm-meg.md) later | Replay in progress (M1) |
| **Implant / HID bridge** | A bridge from discrete HID events to NeuralTextStream | Apple BCI HID protocol; Synchron, Neuralink and others | Planned (M6) |

The build order changed on 2026-11-08. See the next section.

### Adapter priority (2026-11-08)
The [neural input landscape report](../sources/neural-input-landscape-2026.md#top-adapters) sets this order. It supersedes "EMG first" in the table above.

| Priority | Adapter | Why | Licence status |
|---|---|---|---|
| 1 | **LSL ⇄ NTS bridge plus a [BrainFlow](../entities/brainflow.md) source** | The most reach for the least effort. One source covers many EEG boards. See [NTS over LSL](../entities/lab-streaming-layer.md#nts-over-lsl-binding-idea) | liblsl MIT; BrainFlow MIT |
| 2 | **NTS → [Apple BCI HID](../entities/apple-bci-hid.md) bridge, and an HID-report → NTS logger** | Puts NTS in front of every implant vendor that targets Apple, Synchron first. The NTS → HID direction is lossy | Apple reference is vendor documentation. Our code is our own (Apache-2.0) |
| 3 | **Offline replay of the [Dryad intracortical datasets](../entities/dryad-intracortical-datasets.md)** | Willett handwriting, Brain-to-Text '24, Card / Brain-to-Text '25 (with a pretrained RNN). Real decoded text for trust-layer evaluation | **CC0.** The only commercially clean decoded-text data found |
| Follow-up | Neurosity adapter | The only consumer SDK with explicit per-label probability | SDK MIT (**UNVERIFIED**) |
| Follow-up | Emotiv Cortex adapter | `com` stream gives {act, pow 0–1}, top-1 only. Maps to `score_semantics=power` | Proprietary; raw EEG needs a paid licence |
| Follow-up | Meta Web Apps shim ([Meta Neural Band](../entities/meta-neural-band.md)) | DOM gestures and text, no scores. Maps to `score_semantics=none` | Proprietary platform |
| Research only | [emg2qwerty](../entities/emg2qwerty.md) replay | EMG typing benchmark | CC-BY-NC-4.0: no product weights |

> **Our take:** The order trades market size for reach and licence safety. The consumer EMG band is the largest market, but it exposes no scores today. LSL/BrainFlow and the HID bridge reach the most devices for the least code, and both are licence-clean. The Dryad CC0 data lets us show the trust layer on real decoded text with no NC trap.

### The trust core in detail
| Module | What it does |
|---|---|
| a. **Calibration** | Temperature scaling. Recalibration per user and per session. |
| b. **Streaming LM fusion** | A character n-gram or a small LLM inside a beam search. It produces n-best hypotheses with scores. |
| c. **Uncertainty and conformal sets** | Word-level and sentence-level confidence. Conformal prediction sets that account for autocorrelation (adaptive conformal). |
| d. **Hallucination guard** | Compares the LM prior with the neural evidence. Runs null-input and shuffled-input audits. Flags text that the language model "invented". |
| e. **Decision policy** | Selects one action: **COMMIT** the text, **OFFER** n-best choices, **ASK** the user to repeat, or **ABSTAIN**. |

**Vocabularies.** The trust core must not assume characters. A stream can carry chars, keys, words, phonemes or commands. Calibration, conformal sets, the guard and the policy must work over any declared vocabulary. A command vocabulary (for example "select", "back", "send") has no character LM, so LM fusion is optional for it.

> **Our take:** The guard targets a known risk. In Brain2Qwerty v2, the [NeuroLLM](../concepts/neuro-llm.md) improves WER and SemER but makes CER worse, and it can write fluent sentences that are wrong ([v2](../sources/brain2qwerty-v2.md)). For a patient, a fluent wrong sentence is worse than no sentence.

### Effective words per minute
**Effective WPM** is the number of correct words per minute after the simulated user makes its corrections and selections. We propose it as a new standard metric. Raw CER does not show the cost of a fix. Effective WPM includes this cost. So it rewards a system that abstains or offers good choices at the right time.

## Data flow
Source → Decoder → **NeuralTextStream** → Trust core (calibrate → fuse LM → uncertainty → guard → policy) → Interaction (UI or simulated user) → Evaluation.

Evaluation results go back to research. They guide the next change to the decoder or the trust core.

## NeuralTextStream, explained simply
A decoder looks at the signal in small time steps. At each step, it gives a score for each possible character ("a" is likely, "s" is less likely, and so on).

NeuralTextStream is the format for these scores:
- Each step has a **timestamp**.
- Each step has **log-probabilities** over the characters.
- Optionally, each step has an **embedding** (a vector that summarises the neural evidence).

This format is the contract between the decoder and the trust core. The trust core does not need to know how the decoder works. A MEG model, an EMG model, the simulator, or a third-party implant decoder can all feed the same trust core. This is why the layer is decoder-agnostic.

Since the scope decision of 2026-11-08, the format is also modality-agnostic and vocabulary-agnostic. The "characters" above can be keys, words, phonemes or commands. The spec adds OTel-style semantic conventions, for example `device.modality` and `decoder.causal`. The spec is [NeuralTextStream v0.1](../../spec/neuraltextstream-v0.1.md).

> **Our take:** The simulator is important for the start. It takes clean text and produces realistic step-by-step character probabilities with tunable error rates and confusions (for example, confusions between keyboard neighbours). So we can build and test the trust core before any real decoder works. The keyboard-neighbour confusions copy a pattern that the Brain2Qwerty errors show ([v1](../sources/brain2qwerty-v1.md)).

## Open-core split
| Part | Status |
|---|---|
| NeuralTextStream format spec | Open source (Apache-2.0) |
| Adapters | Open source (Apache-2.0) |
| Noisy-decoder simulator | Open source (Apache-2.0) |
| Reference trust-core library | Open source (Apache-2.0) |
| Evaluation harness and benchmark | Open source (Apache-2.0). Loaders for NC datasets only download the data. They ship no data and no weights. |
| Personalised adaptation models trained on our own consented data | Private, later |
| Clinical / AAC deployment | Private, later |
| Per-device calibration profiles | Private, later |
| OEM integrations | Private, later |

## Licence and provenance rule
- SpanishBCBL, emg2qwerty and LibriBrain are **CC BY-NC**. Use them only for research and benchmarks.
- Product model weights must come **only** from CC0 data (the OpenNeuro default) or from our own consented data.
- Keep a **provenance ledger**. It records which data trained which weights. v0 (M2-09, 2026-11-11) records each trust decision with its full provenance; see [provenance ledger](../concepts/provenance-ledger.md).
- Meta's Brain2Qwerty code is also CC BY-NC ([code](../sources/brain2qwerty-code.md)). So our decoder is our own reimplementation, not copied code.

## Proposed code layout
This is a proposal. The project is named **Fidetype**, and the package is `fidetype` (named by the user on 2026-11-08). Today the package has `streams/` (spec, vocabulary, simulator) and `eval/` (metrics). The other folders are planned.

```
src/fidetype/
  streams/      NeuralTextStream spec + adapters (replay, simulator, LSL later)
  decoders/     conv+CTC (causal + offline), baselines
  lm/           char n-gram, small-LLM scorer, beam search
  trust/        calibration.py, conformal.py, guard.py, policy.py
  interact/     simulated_user.py ; web demo later in apps/
  eval/         metrics.py, benchmark.py, reports
  data/         registry (licence tags), provenance ledger
apps/demo/      web UI (later)
experiments/    configs + results per experiment
```

## Roadmap
| Step | Content | Layers used |
|---|---|---|
| **Phase 0: setup** | Test PyTorch/ROCm on the GPU. Download SpanishBCBL MEG. Build the noisy-decoder simulator. | 1, 6 |
| **Paper 1: "Calibrated, abstaining brain-to-text"** | Calibration + conformal sets + hallucination audit + effective WPM on SpanishBCBL. The simulator lets this work start before a real decoder exists. | 1, 3, 4, 5 |
| **Paper 2: causal typing decoder** | The latency vs accuracy curve. | 2, 5 |
| **Then** | Open benchmark release. Real-device adapters (EMG/EEG through LSL). Product pilots. | 1, 4, 5 |
| **Deferred side tracks** | EMG → brain transfer. Virtual OPM-MEG. | — |

> **Our take:** Paper 2 fills a clear gap. v2 waits for the end of the sentence, and no public causal MEG/EEG text decoder exists that we know of ([sync vs async](../concepts/synchronous-vs-asynchronous-decoding.md)).

## Open design questions
1. **Stream format details.** What is the step rate? Which character set? Do we include blank and space tokens from CTC? Do we send embeddings by default? How do we mark the end of a word or sentence?
2. **Which small LLM fits in 16 GB?** The GPU is an AMD RX 7800 XT with 16 GB. The LLM must run in real time next to the decoder.
3. **Does ROCm work?** *Resolved 2026-11-08: yes.* Native Windows ROCm 7.2.1 + torch 2.9.1 runs on the RX 7800 XT. See [compute setup](compute-setup.md). CPU fallback must still work.
4. **Project name.** Resolved on 2026-11-08: the project is **Fidetype**, and the package is `fidetype`.
5. **Wire protocol.** How does a stream go between processes and devices? Do we define an OTLP-like protocol (for example, protobuf over gRPC or HTTP)? Or do we use LSL as the transport and define only the payload?
6. **Discrete events vs per-frame distributions.** An HID switch or an implant command sends discrete events, not a probability distribution per frame. How does the spec carry both? How does the trust core calibrate an event with no score?
7. **On-device and embedded runtimes.** A wristband or an implant has little compute. Must the trust core (or a subset) run on-device, on a phone, or on a microcontroller? Which parts need a C or Rust port?

## Related pages
- [Direction decision](direction-decision.md): why we chose this direction.
- [Reading list](reading-list.md): verified papers to read for this direction.
- [Research directions](research-directions.md): the earlier candidate directions.
- [NeuroLLM](../concepts/neuro-llm.md), [Error metrics](../concepts/error-metrics.md), [CTC](../concepts/ctc.md), [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md).
- [Brain2Qwerty v2](../sources/brain2qwerty-v2.md), [SpanishBCBL dataset](../entities/spanishbcbl-dataset.md), [emg2qwerty](../entities/emg2qwerty.md).
