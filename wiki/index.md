# Wiki index

Claude maintains this wiki. The conventions are in [`../CLAUDE.md`](../CLAUDE.md), the history is in [log.md](log.md), and the big picture is in [overview.md](overview.md).

**Progress:** open [progress/index.html](progress/index.html) for actual effort and dates against the targets (source: `progress/tracker.json`).

## Diagrams
To see all diagrams, open [diagrams/index.html](diagrams/index.html) in a browser.

| Diagram | Shows |
|---|---|
| `01-what-brain2qwerty-does` | Typing → MEG → AI → text. The signal is motor, not thought |
| `02-v1-vs-v2-pipeline` | v1 and v2 pipelines side by side, with results |
| `03-bci-stack` | The five BCI layers. Where to start |
| `04-project-options` | Long-term options A–D |
| `05-roadmap` | Phases 0 to later |
| `06-architecture-layers` | The six layers of the trust layer. Open vs later-private parts |
| `07-data-flow` | Source → decoder → NeuralTextStream → trust core → action → evaluation |
| `08-roadmap-v2` | Phase 0 → Paper 1 → Paper 2 → benchmark → devices → pilots. Deferred side tracks |
| `09-milestones` | Day-scale timeline of M0–M7 against the 1-week target (11-08 → 11-15). Externally blocked lane |

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
| [SpanishBCBL dataset](entities/spanishbcbl-dataset.md) | v1 data. Public (HF, not gated), CC BY-NC 4.0, ~268 GB MEG. The only public typing-MEG set we know of. Inspection findings for M1 |
| [EnglishBCBL dataset](entities/englishbcbl-dataset.md) | v2 data. 90 h MEG. Embargoed |
| [emg2qwerty](entities/emg2qwerty.md) | *Stub.* Meta's public wrist-EMG typing dataset. Template for causal decoding |

## Questions
| Page | Summary |
|---|---|
| [Research directions](questions/research-directions.md) | What this project could do without hardware. Candidate directions and the reading queue |
| [Direction decision](questions/direction-decision.md) | 2026-11-07: we chose trustworthy neural text entry. Evidence, licence trap, rejected options |
| [Architecture](questions/architecture.md) | Six-layer design, NeuralTextStream, open-core split, code layout, roadmap |
| [Reading list](questions/reading-list.md) | Verified papers to read for the trust-layer direction |
| [Project plan](questions/project-plan.md) | Milestones M0–M7 with targets (M0 by 11-09, M1–M7 by 11-15), tasks, "done when" criteria, timeline policy, risks, working process |
| [Compute setup](questions/compute-setup.md) | GPU path: native Windows ROCm 7.2.1 + torch 2.9.1 on the RX 7800 XT. Short venv path (MAX_PATH). Benchmarks, caveats, usage |

## Experiments
| Page | Summary | Date |
|---|---|---|
| [SpanishBCBL inspection, S25](../experiments/2026-11-08-inspect-spanishbcbl/results.md) | S25 loads in MNE. Head digitisation present. Key triggers aligned to the log (<1 ms) with a per-block drift fit | 2026-11-08 |
