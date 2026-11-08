---
title: Project plan — trustworthy neural text entry
type: question
tags: [planning, roadmap, milestones, risks, process, scope]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code, neural-input-landscape-2026]
updated: 2026-11-08
---

# Project plan: trustworthy neural text entry

**Question asked:** What is the concrete plan, with milestones, tasks, risks and a working process?

## Summary
We build a decoder-agnostic trust layer for neural text decoders. One developer leads the work, and AI agents do most of the coding under the developer's review. The plan goes from setup (M0) to a first paper (M3), a streaming decoder (M4), an open benchmark (M5), device adapters (M6) and product pilots (M7).

- The design: [architecture](architecture.md).
- The reasons for this direction: [direction decision](direction-decision.md).
- The papers to read first: [reading list, "Start here"](reading-list.md#start-here-reading-order).
- The timeline diagram: `09-milestones` on [the diagram page](../diagrams/index.html#s9).
- The actual progress: [progress dashboard](../progress/index.html).

**Scope (2026-11-08).** The user widened the scope. Fidetype is now the vendor-neutral standard and trust layer for **neural input** from any device: wrist EMG, EEG, MEG/OPM-MEG and implants. It is an OpenTelemetry-level project. Research MEG stays the credibility base and the test case for Paper 1. The user accepts a multi-year horizon and the need for outside partners, people and funding. The targets below apply to building the code, not to adoption. Details: [scope decision](direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level).

**Targets (set by the user on 2026-11-08):** M0 is done by 2026-11-09. M1–M7 are done by 2026-11-15. Items that depend on outside people are not in these targets. See [Timeline policy](#timeline-policy-2026-11-08).

## Timeline policy (2026-11-08)
- The user sets the targets. The earlier week and month estimates are replaced.
- We track the actual effort and dates in the [progress dashboard](../progress/index.html). The source of truth is `wiki/progress/tracker.json`. Rebuild the page with `node tools/progress/build.js`.
- Some items depend on outside people: ethics approval and volunteers (M6), partner agreements (M7), arXiv endorsement (M3) and peer review. We mark them `externally_blocked`. We track them, but they do not count as late.
- We review the plan against the actuals, not against guesses.

## Fixed facts
| Item | Value |
|---|---|
| Project / package name | **Fidetype** / `fidetype` (named by the user on 2026-11-08) |
| Team | 1 developer. AI agents write most code. The developer reviews it. |
| GPU | AMD RX 7800 XT, 16 GB. Native Windows ROCm 7.2.1 + torch 2.9.1 works ([compute setup](compute-setup.md)). |
| RAM | 31 GB |
| Data root | `C:\Users\zhang\bci-data\`. It is outside OneDrive, so large data does not sync to the cloud. |
| Code licence | Apache-2.0 for all code in the public repo. |

### Licence rule
- NC-licensed data (SpanishBCBL, emg2qwerty, LibriBrain) is for **research only** ([direction decision](direction-decision.md#3-the-licence-trap)).
- Product weights come **only** from CC0 data or our own consented data.
- A **provenance ledger** is required. It records which data trained which weights.
- Our decoder is our own code. We copy no Meta code, because the Brain2Qwerty code is CC BY-NC ([code](../sources/brain2qwerty-code.md)).

## Milestones
| ID | Name | Target window | Key deliverables | Done when |
|---|---|---|---|---|
| **M0** | Setup | 2026-11-08 → 11-09 | GPU path decided. SpanishBCBL MEG downloaded. Package skeleton, NeuralTextStream spec v0.1, noisy-decoder simulator with tests. Project name. README, CI. | Simulator tests pass in CI. One subject loads in MNE. The GPU path is chosen. |
| **M1** | Baseline decoder | 11-09 → 11-11. Parallel with M2. | Our own conv + CTC decoder on SpanishBCBL MEG (offline mode). It emits NeuralTextStream. Character n-gram LM beam search. | Greedy CER approaches v2's async SpanishBCBL CER (≈0.59) or is better. |
| **M2** | Trust core v0 | 11-09 → 11-11. Parallel with M1. | Calibration, n-best + LM fusion, conformal sets, hallucination guard, decision policy, simulated user, effective WPM, evaluation harness, provenance ledger v0. | The full pipeline runs end to end on the simulator AND on real decoder outputs. All metrics are reported. |
| **M3** | Paper 1: "Calibrated, abstaining brain-to-text" | 11-11 → 11-13. Peer review and arXiv endorsement are externally blocked. | Experiments and ablations. arXiv preprint. Code release. | Preprint on arXiv. Code public. |
| **M4** | Paper 2: causal / streaming decoder | 11-11 → 11-13. Parallel with M3. | Latency vs accuracy curve (lookahead 0–500 ms). Streaming trust core. | Curve and streaming trust core in a preprint. |
| **M5** | Open benchmark v0.1 | 11-13 → 11-14 | Public harness, metrics, leaderboard. | v0.1 tagged and public. NC loaders only download. |
| **M6** | Device adapters | 11-14 → 11-15 (code parts). Own data collection is externally blocked. | LSL input. EMG/EEG consumer devices. Our own consented data collection. | A live device stream goes through the trust core. |
| **M7** | Product pilots | 11-14 → 11-15 (code parts). Pilot agreements are externally blocked. | SDK. Partner talks. Private repo for closed parts. | At least one pilot agreement. |
| — | Deferred side tracks | Not scheduled | EMG → brain transfer. Virtual OPM-MEG simulation. | — |

> **Our take:** M2 can start before M1 ends. The simulator emits NeuralTextStream, so the trust core does not wait for a real decoder.

## M0: Setup (target 11-08 → 11-09)
- [x] Test PyTorch on the GPU. Choose one path: ROCm native, WSL2 + ROCm, DirectML, or cloud. Record the result in the wiki. *(done 2026-11-08: native Windows ROCm, see [compute setup](compute-setup.md))*
- [ ] Download SpanishBCBL MEG to `C:\Users\zhang\bci-data\` ([dataset](../entities/spanishbcbl-dataset.md)). *(started 2026-11-08; 239/316 files at 14:02 on 2026-11-08; continues in the background)*
- [x] Inspect one subject in MNE. Check whether the files carry head digitisation. *(done 2026-11-08: S25, digitisation present, see [inspection results](../../experiments/2026-11-08-inspect-spanishbcbl/results.md))*
- [x] Create the Python package skeleton. *(done 2026-11-08)*
- [x] Write the NeuralTextStream spec v0.1 ([architecture](architecture.md#neuraltextstream-explained-simply)). *(done 2026-11-08)*
- [x] Build the noisy-decoder simulator with tests. *(done 2026-11-08: 41 tests)*
- [x] Decide the project name. *(done 2026-11-08: Fidetype)*
- [x] Rewrite the README. *(done 2026-11-08)*
- [x] Add CI: GitHub Actions runs pytest on CPU. *(done 2026-11-08: commit c95a3c7, first run green)*

**Done when:** the simulator tests pass in CI, one subject loads in MNE, and the GPU path is chosen.

**M0 done 2026-11-08 (target 11-09).** All three criteria are met. The bulk MEG download continues in the background.

## M1: Baseline decoder (target 11-09 → 11-11)
- [x] SpanishBCBL data loader and alignment. *(done 2026-11-08: 81 typing blocks, 15570/15571 keys aligned, see [M1-A results](../../experiments/2026-11-08-m1a-data/results.md))*
- [ ] Preprocess the SpanishBCBL cache (tSSS, 0.5–45 Hz, 100 Hz). *(running in the background: 10 of 47 blocks at 14:24 on 2026-11-08)*
- [x] Write our own conv + [CTC](../concepts/ctc.md) decoder. Copy no Meta code. *(done 2026-11-08: `src/fidetype/decoders/`, 10.06 M params, causal mode via `lookahead_frames`)*
- [x] Train it on SpanishBCBL MEG in offline (non-causal) mode first. *(done 2026-11-08: S25 only, and 5 subjects / about 2.5 h)*
- [x] Make it emit NeuralTextStream. *(done 2026-11-08: `fidetype.decoders.infer`)*
- [x] Add a character n-gram LM with beam search as a baseline. *(done 2026-11-08: 6-gram MKN + CTC prefix beam; simulator median CER 0.281 → 0.200, see [LM beam results](../../experiments/2026-11-08-lm-beam/results.md))*
- [x] Report greedy CER and beam CER on fixed splits. *(done 2026-11-08: greedy test CER 0.670; shuffled-MEG control 0.669. See [decoder M1 results](decoder-m1-results.md). Beam CER follows the beam re-tune.)*
- [ ] Sanity check: keystroke-locked hand/char decoding (v1-style). Does the cache hold keystroke signal? *(running)*
- [ ] Retrain the decoder on the full cache (all subjects).
- [ ] Low-data tuning: a smaller model, more dropout and masking.
- [ ] Cross-subject pretraining, then a per-subject fine-tune.

**Done when:** greedy CER approaches v2's async SpanishBCBL CER (≈0.59) or is better.

**Status (2026-11-08):** the decoder code is done and emits NeuralTextStream. Best test greedy CER is 0.670 (5 subjects, about 2.5 h of about 20 h). The shuffled-MEG control gives 0.669, so the model does not use the MEG yet. The "done when" criterion is **not met**. See [decoder M1 results](decoder-m1-results.md).

**Reference numbers.**
- Brain2Qwerty v1 is keystroke-locked. Its MEG CER is 0.36 for Conv+Trans and 0.29 for the full model with LM ([v1](../sources/brain2qwerty-v1.md), Fig. 2).
- Brain2Qwerty v2 reports an async CER of 0.59 on SpanishBCBL ([v2](../sources/brain2qwerty-v2.md), Fig. 1D–E).

> **Our take:** Our setup is continuous CTC, like v2's async encoder, and the dataset is small. So we expect a CER worse than v1's 0.29. The honest target is v2's async number, not v1's number.

## M2: Trust core v0 (target 11-09 → 11-11)
- [x] **Calibration:** temperature scaling, per session.
- [x] **n-best beam with LM fusion.**
- [x] **Conformal prediction sets:** split conformal first. Then adaptive conformal, to handle autocorrelation.
- [x] **Hallucination guard:** null-input and shuffled-input audit. LM-prior vs evidence score.
- [x] **Decision policy:** COMMIT / OFFER / ASK / ABSTAIN.
- [x] **Simulated user:** selection time and correction cost.
- [x] **Effective WPM** metric ([architecture](architecture.md#effective-words-per-minute)).
- [x] **Evaluation harness** with fixed splits. Metrics: CER, WER, ECE, coverage, hallucination rate, effective WPM ([error metrics](../concepts/error-metrics.md)).
- [ ] **Provenance ledger v0.**
- [ ] **Run the trust core on real decoder outputs.** It needs the M1 decoder streams.

*Status 2026-11-08:* trust core v0 runs end to end on the simulator. See [M2 simulator results](../../experiments/2026-11-08-m2-trust-sim/results.md) and [trust core v0 results](trust-core-v0-results.md).

**Known gaps (from the simulator run, 2026-11-08):**
- [ ] n-best recall is low. The truth is missing in 28–37 % of n-best lists with the reference decoder, and in 73 % with the LM beam at default settings ([M2 results](../../experiments/2026-11-08-m2-trust-sim/results.md)). Re-tune the beam (`prune_topk`, insertion bonus).
- [ ] The guard AUROC is weak (0.57–0.71). The n-best-inconsistency signal alone is better (0.65–0.88). Re-design the guard score.
- [ ] The user time costs are assumptions. Get them from the literature or from real data (Cai et al. 2024).

**Done when:** the full pipeline runs end to end on the simulator AND on real decoder outputs, with all metrics reported.

## M3: Paper 1, "Calibrated, abstaining brain-to-text" (target 11-11 → 11-13)

**Revised claim (2026-11-08).** Source: [M2 simulator results](../../experiments/2026-11-08-m2-trust-sim/results.md).
- The simulator shows that the trust policy cuts wrong commits from 0.29–0.47 to 0.02–0.09.
- It commits 0 % fluent text on shuffled or flat input. Always-commit commits 98–100 %.
- But its effective WPM is 7–16 % lower than always committing the LM top-1.
- So Paper 1 claims "far fewer wrong and hallucinated commits for a small speed cost", not "higher eWPM".
- Details: [trust core v0 results](trust-core-v0-results.md).

- [ ] Run experiments on SpanishBCBL and on the simulator.
- [ ] Run ablations: each trust-core module on and off.
- [ ] The test set is small (24 test sentences in SpanishBCBL). Use cross-validation or multiple seeds for Paper 1.
- [ ] Check the RAS formula (arXiv 2604.24278) before we cite the comparison.
- [ ] Position the paper against the closest work ([reading list](reading-list.md)):
  - Huang et al. 2025, co-control BCIs.
  - Conformal ASR: Ernez et al. 2023; Damri & Laufer-Goldshtein 2026.
  - The RAS metric (arXiv 2604.24278).
- [ ] Write the paper.
- [ ] Release the arXiv preprint and the code.
- [ ] Get arXiv endorsement, if arXiv requires it. *(externally blocked)*
- [ ] Peer review at the chosen venue. *(externally blocked)*
- [ ] Choose a venue. Candidates: NeurIPS / ICLR workshops, *Journal of Neural Engineering*, *IEEE TNSRE*.

## M4: Paper 2, causal / streaming decoder (target 11-11 → 11-13)
- [ ] Add a causal mode to the decoder with a configurable lookahead.
- [ ] Measure the latency vs accuracy curve for lookahead 0 to 500 ms.
- [ ] Make the trust core work in streaming mode.
- [ ] Write and release the preprint.
- [ ] Peer review. *(externally blocked)*

> **Our take:** We know of no public causal MEG/EEG text decoder ([sync vs async](../concepts/synchronous-vs-asynchronous-decoding.md)). This curve fills that gap.

## M5: Open benchmark v0.1 (target 11-13 → 11-14)
- [ ] Publish the harness, the metrics and fixed splits.
- [ ] Publish a leaderboard.
- [ ] Make NC dataset loaders download-only. Ship no data and no weights.
- [ ] Publish NeuralTextStream spec v0.1 ([spec](../../spec/neuraltextstream-v0.1.md)).
- [ ] Publish a conformance test suite: a decoder or device passes it when its output is valid NeuralTextStream.

**Open-source growth.** The benchmark release is the launch moment (Stage 1) of the [open-source playbook](open-source-playbook.md). That page lists the launch steps, the cheap repo actions (CONTRIBUTING, CoC, GOVERNANCE, CITATION.cff) and the path to a standard.

## M6: Device adapters (target 11-14 → 11-15)
- [ ] Add adapters in priority order ([adapter priority](architecture.md#adapter-priority-2026-11-08), set on 2026-11-08 from the [neural input landscape report](../sources/neural-input-landscape-2026.md#top-adapters)). Each adapter emits NeuralTextStream.
  1. [ ] **LSL ⇄ NTS bridge plus a [BrainFlow](../entities/brainflow.md) source** (EEG and other boards). Both are MIT.
  2. [ ] **NTS → [Apple BCI HID](../entities/apple-bci-hid.md) bridge, and an HID-report → NTS logger** (implants; Synchron first).
  3. [ ] **Offline replay of the [Dryad intracortical datasets](../entities/dryad-intracortical-datasets.md)** (CC0). This data enables commercially clean evaluation of the trust layer on real decoded text.
  4. [ ] Follow-ups: Neurosity and Emotiv adapters (probability-like scores); a Meta Web Apps shim with `score_semantics=none` ([Meta Neural Band](../entities/meta-neural-band.md)).
  5. [ ] Research only: replay [emg2qwerty](../entities/emg2qwerty.md) (CC BY-NC: no product weights).
- [ ] Collect our own consented data. Product weights need it. *(externally blocked: ethics approval and volunteers)*
- [ ] Test effective WPM with real users. *(externally blocked: volunteers)*

## M7: Product pilots (target 11-14 → 11-15)
- [ ] Build the SDK.
- [ ] Contact partners: EMG band makers, the Apple BCI HID path, EEG makers.
- [ ] Create a private repo for the closed parts ([architecture](architecture.md#open-core-split)).
- [ ] Sign at least one pilot agreement. *(externally blocked: partners)*

## Deferred side tracks
- EMG → brain transfer.
- Virtual OPM-MEG simulation ([OPM-MEG](../concepts/opm-meg.md)).

We do not schedule these. We review them when M3 is done.

## Risks and fallbacks
| Risk | Fallback |
|---|---|
| ROCm fails | CPU for small models, plus rented cloud GPU hours. |
| Dataset problems (size, gating, missing head digitisation) | Use OpenNeuro CC0 sets. |
| Meta FAIR moves into the same space (NeuralBench, v2 follow-ups) | Position our work as complementary. Build on NeuralBench. |
| NC licence contaminates product weights | Provenance ledger. Separate repos. |
| Solo bandwidth | Agent-driven development with a strict evaluation harness. Agents do well in constrained settings and fail at open-ended ones ([Auto Research](../concepts/auto-research.md)). |
| Effective WPM is only simulated | Test it with real users in M6. |

## Working process
- **Orchestrator and subagents.** The main chat is the orchestrator. It plans and reviews. Subagents do the work.
- **Wiki.** We file every result in the wiki. Every session appends an entry to [log.md](../log.md).
- **GitHub Issues (recommended).** One issue per task. One label per milestone (`M0` … `M7`). Nobody has created these issues yet.
- **Progress tracking.** The orchestrator records every task, with start and finish times and subagent effort, in [the progress dashboard](../progress/index.html).
- **Review.** We check this plan against the actuals in the tracker, not against guesses.
- **Commits.** The orchestrator decides what to commit and pushes to `main`.
- **Experiments.** Each experiment goes in `experiments/<date>-<name>/`. Each folder has a config file and a `results.md`.

## Year-1 success metrics
| Metric | Target |
|---|---|
| Paper 1 | On arXiv |
| Open benchmark | v0.1 released |
| External use | At least 1 external user or citation |
| Demo | Works on at least one real-device stream |
| Spec adoption | ≥1 decoder outside the project emits NeuralTextStream |

## M0 status (target 2026-11-09)
The live status is in the [progress dashboard](../progress/index.html).

| Task | Status on 2026-11-08 |
|---|---|
| GPU / PyTorch test (ROCm, WSL2, DirectML or cloud) | Done: native Windows ROCm ([compute setup](compute-setup.md)) |
| SpanishBCBL MEG download | Running in the background (239/316 files at 14:02 on 2026-11-08) |
| Package skeleton + NeuralTextStream spec v0.1 + simulator with tests | Done (41 tests) |
| Inspect one subject in MNE; check head digitisation | Done: S25, digitisation present |
| Decide the project name | Done (Fidetype) |
| README rewrite | Done |
| CI (GitHub Actions, pytest on CPU) | Done (green) |

## Related pages
- [Architecture](architecture.md)
- [Compute setup](compute-setup.md)
- [Trust core v0 results](trust-core-v0-results.md)
- [Decoder M1 results](decoder-m1-results.md)
- [Direction decision](direction-decision.md)
- [Reading list](reading-list.md)
- [Research directions](research-directions.md)
- [Progress dashboard](../progress/index.html)
- [Diagrams](../diagrams/index.html) (diagram 9: milestones; diagram 8: roadmap)
