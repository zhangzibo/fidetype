---
title: Direction decision — trustworthy neural text entry
type: question
tags: [planning, decision, directions, licence, market]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-07
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
