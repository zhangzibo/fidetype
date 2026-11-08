# Wiki index

Claude maintains this wiki. The conventions are in [`../CLAUDE.md`](../CLAUDE.md), the history is in [log.md](log.md), and the big picture is in [overview.md](overview.md).

## Sources
| Page | Summary | Date |
|---|---|---|
| [Brain2Qwerty v1](sources/brain2qwerty-v1.md) | Nature Neuro 2026. Keystroke-locked MEG/EEG typing decoding: 29% CER (MEG), 65% (EEG) | 2026-06 |
| [Brain2Qwerty v2](sources/brain2qwerty-v2.md) | Meta preprint. Continuous MEG → CTC → NeuroLLM: 39% WER, log-linear data scaling | 2026-06 |
| [Brain2Qwerty code](sources/brain2qwerty-code.md) | facebookresearch/brain2qwerty. CC BY-NC. v1 reproducible, v2 not (embargoed data) | 2026-11 |

## Concepts
| Page | Summary |
|---|---|
| [MEG](concepts/meg.md) | Magnetic brain recording. 306-channel cryogenic scanner. Higher SNR than EEG |
| [EEG](concepts/eeg.md) | Scalp electrodes. Cheap, but low SNR: 65% CER on typing |
| [OPM-MEG](concepts/opm-meg.md) | Wearable room-temperature MEG. A sensor ablation suggests about 150 sensors are enough |
| [Synchronous vs asynchronous decoding](concepts/synchronous-vs-asynchronous-decoding.md) | Event-locked vs continuous. The gap closes with data. Neither is causal yet |
| [CTC](concepts/ctc.md) | Alignment-free sequence loss behind v2's encoder and word segmentation |
| [BrainModule](concepts/brainmodule.md) | Meta's subject-aware conv front end (270 virtual channels) |
| [NeuroLLM](concepts/neuro-llm.md) | LLM conditioned on CTC text plus MEG word tokens. Better meaning, but hallucinates |
| [Model soup](concepts/model-soup.md) | Per-subject LoRA adapters averaged into one model. Scales with LLM size |
| [Data scaling](concepts/data-scaling.md) | Log-linear gains with hours. Diversity matters. No plateau yet |
| [Auto Research](concepts/auto-research.md) | AI agents tuning the pipeline. Works when constrained, fails when open-ended |
| [Error metrics](concepts/error-metrics.md) | HER, CER, WER, SemER, and why they disagree |

## Entities
| Page | Summary |
|---|---|
| [Meta FAIR Brain & AI](entities/meta-fair-brain-ai.md) | J.-R. King's Paris team. Authors of Brain2Qwerty |
| [BCBL](entities/bcbl.md) | Basque lab that recorded and owns the data |
| [SpanishBCBL dataset](entities/spanishbcbl-dataset.md) | v1 data. Public (gated HF), ~262 GB. The only public typing-MEG set we know of |
| [EnglishBCBL dataset](entities/englishbcbl-dataset.md) | v2 data. 90 h MEG. Embargoed |
| [emg2qwerty](entities/emg2qwerty.md) | *Stub.* Meta's public wrist-EMG typing dataset. Template for causal decoding |

## Questions
| Page | Summary |
|---|---|
| [Research directions](questions/research-directions.md) | What this project could do without hardware. Candidate directions and the reading queue |
