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
| `10-open-source-path` | Open-source stages 0–5 (credibility → launch → community → standard → foundation → company). What each borrows from SGLang, LangChain, OTel, BIDS. Exit criteria |

## Sources
| Page | Summary | Date |
|---|---|---|
| [Brain2Qwerty v1](sources/brain2qwerty-v1.md) | Nature Neuro 2026. Keystroke-locked MEG/EEG typing decoding: 29% CER (MEG), 65% (EEG) | 2026-06 |
| [Brain2Qwerty v2](sources/brain2qwerty-v2.md) | Meta preprint. Continuous MEG → CTC → NeuroLLM: 39% WER, log-linear data scaling | 2026-06 |
| [Brain2Qwerty code](sources/brain2qwerty-code.md) | facebookresearch/brain2qwerty. CC BY-NC. v1 reproducible, v2 not (embargoed data) | 2026-11 |
| [Case study: SGLang](sources/case-study-sglang.md) | Lab project (LMSYS). Paper + reproducible benchmarks + day-0 model support. 38,583 stars. Spin-out RadixArk | 2026-11 |
| [Case study: LangChain](sources/case-study-langchain.md) | Side project → open-core company. Integrations first. 149,213 stars. Criticised for abstraction and churn | 2026-11 |
| [Case study: OpenTelemetry](sources/case-study-opentelemetry.md) | Merged rival standards. Vendor-neutral spec, company-capped governance. CNCF Graduated 2026-05-21. BCI standards gap | 2026-11 |
| [Neural input landscape 2026](sources/neural-input-landscape-2026.md) | Devices, SDKs, standards, regulation. No standard for decoded neural output with confidence. Closest: Apple BCI HID, W3C EMMA. Adapter priority. Data and regulatory warnings | 2026-11 |

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
| [emg2qwerty](entities/emg2qwerty.md) | *Partial.* Meta's public wrist-EMG typing dataset. CC-BY-NC-4.0, HDF5 at 2 kHz. Sibling Meta EMG sets are also NC. Template for causal decoding |
| [BIDS](entities/bids.md) | Brain Imaging Data Structure. Community data standard. Model for NeuralTextStream governance. Bridge, not rival |
| [Lab Streaming Layer](entities/lab-streaming-layer.md) | De facto real-time lab streaming tool (SCCN/UCSD). Raw signals, not decoder output |
| [IEEE P2731](entities/ieee-p2731.md) | Draft IEEE BCI terminology standard. Authorised 2018, unpublished. No stream format. Related venues: ISO/IEC SC 43, TS 27571 |
| [Apple BCI HID](entities/apple-bci-hid.md) | Apple's BCI HID reference (Usage Page 0x60). Strength, buttons, pointer, scan context. No text, no n-best. Closest neural standard |
| [W3C EMMA](entities/w3c-emma.md) | W3C multimodal annotation (1.0 Rec 2009). Confidence, n-best, timestamps. Closest non-neural precedent |
| [Meta Neural Band](entities/meta-neural-band.md) | Consumer wrist sEMG. Web Apps get DOM events only. No raw EMG, no scores |
| [BrainFlow](entities/brainflow.md) | MIT library. Uniform raw-data API across many boards. Adapter priority 1 with LSL |
| [Dryad intracortical datasets](entities/dryad-intracortical-datasets.md) | CC0. Willett 2021 handwriting, Brain-to-Text '24/'25. The only commercially clean decoded-text data found |

## Questions
| Page | Summary |
|---|---|
| [Research directions](questions/research-directions.md) | What this project could do without hardware. Candidate directions and the reading queue |
| [Direction decision](questions/direction-decision.md) | 2026-11-07: we chose trustworthy neural text entry. Evidence, licence trap, rejected options |
| [Architecture](questions/architecture.md) | Six-layer design, NeuralTextStream, open-core split, code layout, roadmap |
| [Reading list](questions/reading-list.md) | Verified papers to read for the trust-layer direction |
| [Project plan](questions/project-plan.md) | Milestones M0–M7 with targets (M0 by 11-09, M1–M7 by 11-15), tasks, "done when" criteria, timeline policy, risks, working process |
| [Open-source playbook](questions/open-source-playbook.md) | How Fidetype grows: OTel/BIDS for the standard, SGLang for credibility, LangChain for the company. Stages 0–5, cheap actions now, risks |
| [Compute setup](questions/compute-setup.md) | GPU path: native Windows ROCm 7.2.1 + torch 2.9.1 on the RX 7800 XT. Short venv path (MAX_PATH). Benchmarks, caveats, usage |
| [Decoder M1 results](questions/decoder-m1-results.md) | 2026-11-08 decoder runs. CTC alone: test CER 0.670 equals the shuffled-MEG control 0.669 (no MEG use). With a keystroke auxiliary loss (M1-C): gap +0.116 to +0.156, greedy CER 0.619. Beam + char LM, val-tuned (M1-C2): 0.590, gap +0.132. Greedy target 0.59 not met. Report the control and means over participants |
| [SpanishBCBL repeated participants](questions/spanishbcbl-repeated-participants.md) | S1/S18, S4/S14 and S5/S10/S21 are one person each. Index correct. Sentence splits, so no leakage. Effect on M1-C ≤ 0.003 CER. Report means over participants |
| [Trust core v0 results](questions/trust-core-v0-results.md) | 2026-11-08 simulator run: trust policy cuts wrong commits 0.29–0.47 → 0.02–0.09 for a 7–16 % eWPM cost. LM fusion breaks calibration. Revised Paper 1 claim. Beam re-tune, first real MEG, per-word OFFER: no BCI policy on real MEG beats gaze typing alone |

## Experiments
| Page | Summary | Date |
|---|---|---|
| [SpanishBCBL inspection, S25](../experiments/2026-11-08-inspect-spanishbcbl/results.md) | S25 loads in MNE. Head digitisation present. Key triggers aligned to the log (<1 ms) with a per-block drift fit | 2026-11-08 |
| [M1-A data layer, SpanishBCBL cache](../experiments/2026-11-08-m1a-data/results.md) | Loader + preprocessing cache. 81 typing blocks. 15570/15571 keys aligned. tSSS removes the 23.3 Hz peak. 224 sentences, hash split | 2026-11-08 |
| [CTC beam + 6-gram char LM](../experiments/2026-11-08-lm-beam/results.md) | Simulator: median CER 0.281 → 0.200 with the LM. 91 ms/sentence. Fused confidences over-confident | 2026-11-08 |
| [M1-B conv + CTC decoder](../experiments/2026-11-08-m1b-decoder/results.md) | Own ConvCTC (10 M params, custom Conformer, causal-capable). 5 subjects, 2.5 h: test CER 0.670 vs shuffled-MEG 0.669, zeros 0.858. ROCm fixes | 2026-11-08 |
| [Trust core on the simulator (M2)](../experiments/2026-11-08-m2-trust-sim/results.md) | eWPM, wrong-commit, calibration, conformal, guard, null-input audit, ablations over 9 simulator conditions | 2026-11-08 |
| [Beam re-tune for n-best recall](../experiments/2026-11-08-beam-retune/results.md) | Old misses were search errors (top-10 cut, beam 16). `RETUNED` beam: recall@10 0.075 → 0.47 (median Tatoeba); trust pipeline n-best miss 0.73 → 0.00; trust policy 25.3 eWPM vs always-commit 25.8 with 0.033 vs 0.108 wrong commits | 2026-11-08 |
| [M1 sanity check: keystroke-locked linear decoding](../experiments/2026-11-08-m1-sanity/results.md) | Signal present in the cache: hand window 0.83–0.96, letter 0.31–0.49 (chance about 0.14), controls at chance, peaks −10..+60 ms | 2026-11-08 |
| [M2-10 trust core on real MEG (keystroke decoder)](../experiments/2026-11-08-m2-real-keystroke/results.md) | First real MEG decoding: synchronous keystroke decoder (oracle timing), test key acc 0.390 (controls 0.10–0.11), greedy CER 0.59 (control 0.77), LM beam CER 0.53. Trust: wrong-commit 100 % → 0 %, fluent null-input commits 83–100 % → 0 %; truth never in the n-best (degenerate test) | 2026-11-08 |
| [M1-C keystroke auxiliary loss for ConvCTC](../experiments/2026-11-08-m1c-decoder-aux/results.md) | Per-keystroke CE head on the encoder frames. 11 subjects, 20 blocks. Shuffled-MEG gap 0 without it, +0.116 to +0.156 with it. Best test CER 0.619 (keystroke-pretrained). ROCm process-exit hang fixed | 2026-11-08 |
| [OFFER_WORDS: per-word choices + partial correction](../experiments/2026-11-08-m2-offer-words/results.md) | New trust action + word-level gaze user model. Simulator worst preset +0.4 to +1.7 eWPM; median no change. Real MEG: never selected; trust 2.96 vs gaze typing alone 3.14 eWPM | 2026-11-08 |
| [M1-C2 beam + char LM on the r4b CTC streams](../experiments/2026-11-08-m1c2-beam-lm/results.md) | Test CER greedy 0.619 → beam no LM 0.605 → beam + LM val-tuned (w 0.25, bonus 1.0) 0.590 [0.576, 0.604]. Shuffled-MEG gap +0.132. `RETUNED` as is: 0.633 (worse). Truth in the 20-best for 0 sentences | 2026-11-08 |
