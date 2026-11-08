---
title: Architecture of the trustworthy neural text entry layer
type: question
tags: [planning, architecture, calibration, uncertainty, streaming, open-core]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code]
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
| 1 | **Sources / adapters** | Put neural data or decoder outputs into one standard stream format. | **Now:** offline replay of datasets ([SpanishBCBL](../entities/spanishbcbl-dataset.md) MEG/EEG; later [emg2qwerty](../entities/emg2qwerty.md) and OpenNeuro CC0 sets). A **noisy-decoder simulator**. **Later:** live devices through Lab Streaming Layer (LSL), and an Apple BCI HID bridge. |
| 2 | **Decoders** | Turn neural data into character probabilities. These are research models. They are interchangeable. | Our own reimplementation of a conv + [CTC](../concepts/ctc.md) decoder, under a permissive licence. It has a causal (streaming) mode with a configurable lookahead. Baselines. Any third-party decoder can plug in if it emits the NeuralTextStream format. |
| 3 | **Trust core** | Make the text reliable. This is the heart of the project and the future product. | a. Calibration. b. Streaming LM fusion. c. Uncertainty and conformal sets. d. Hallucination guard. e. Decision policy. (See below.) |
| 4 | **Interaction** | Show the text to a person, or simulate a person. | A UI that shows text with confidence, an n-best picker and correction. A **simulated user** model for offline evaluation (selection time, error-correction cost). |
| 5 | **Evaluation harness / benchmark** | Measure every part with fixed rules. | Fixed splits. Metrics: CER, WER, SemER ([error metrics](../concepts/error-metrics.md)); calibration (ECE, reliability diagrams); conformal coverage; latency; hallucination rate; **effective words per minute**. |
| 6 | **Infrastructure** | Support all other layers. | A dataset registry with a licence tag for each dataset. A **provenance ledger** (which data trained which weights). Config, experiment tracking, ROCm/CPU support. |

### The trust core in detail
| Module | What it does |
|---|---|
| a. **Calibration** | Temperature scaling. Recalibration per user and per session. |
| b. **Streaming LM fusion** | A character n-gram or a small LLM inside a beam search. It produces n-best hypotheses with scores. |
| c. **Uncertainty and conformal sets** | Word-level and sentence-level confidence. Conformal prediction sets that account for autocorrelation (adaptive conformal). |
| d. **Hallucination guard** | Compares the LM prior with the neural evidence. Runs null-input and shuffled-input audits. Flags text that the language model "invented". |
| e. **Decision policy** | Selects one action: **COMMIT** the text, **OFFER** n-best choices, **ASK** the user to repeat, or **ABSTAIN**. |

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
- Keep a **provenance ledger**. It records which data trained which weights.
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
3. **Does ROCm work?** The GPU uses ROCm, not CUDA. Phase 0 must test PyTorch on it. CPU fallback must work.
4. **Project name.** Resolved on 2026-11-08: the project is **Fidetype**, and the package is `fidetype`.

## Related pages
- [Direction decision](direction-decision.md): why we chose this direction.
- [Reading list](reading-list.md): verified papers to read for this direction.
- [Research directions](research-directions.md): the earlier candidate directions.
- [NeuroLLM](../concepts/neuro-llm.md), [Error metrics](../concepts/error-metrics.md), [CTC](../concepts/ctc.md), [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md).
- [Brain2Qwerty v2](../sources/brain2qwerty-v2.md), [SpanishBCBL dataset](../entities/spanishbcbl-dataset.md), [emg2qwerty](../entities/emg2qwerty.md).
