# Wiki log

An append-only history. Each entry is formatted `## [YYYY-MM-DD] <ingest|query|lint|setup> | <title>`. To see the latest entries, run `grep "^## \[" wiki/log.md | tail -5`.

## [2026-11-07] setup | Wiki created
- Adopted the LLM-wiki pattern (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
- Schema written in `CLAUDE.md`.
- Raw layer: `references/`. Wiki layer: `wiki/`, with sources/, concepts/, entities/ and questions/.

## [2026-11-07] ingest | Brain2Qwerty v1 (Nature Neuroscience)
- Created [sources/brain2qwerty-v1](sources/brain2qwerty-v1.md).
- Created concepts: meg, eeg, synchronous-vs-asynchronous-decoding, brainmodule, data-scaling, error-metrics.
- Created entities: meta-fair-brain-ai, bcbl, spanishbcbl-dataset.

## [2026-11-07] ingest | Brain2Qwerty v2 (Meta preprint)
- Created [sources/brain2qwerty-v2](sources/brain2qwerty-v2.md).
- Created concepts: ctc, neuro-llm, model-soup, opm-meg, auto-research.
- Created entities: englishbcbl-dataset, emg2qwerty (stub).
- Updated: data-scaling, synchronous-vs-asynchronous-decoding, brainmodule, error-metrics.

## [2026-11-07] ingest | facebookresearch/brain2qwerty code
- Created [sources/brain2qwerty-code](sources/brain2qwerty-code.md). Licence: CC BY-NC.
- v2 is not runnable (missing study class, embargoed data). Two suspected bugs noted.

## [2026-11-07] query | What could this project do?
- Filed [questions/research-directions](questions/research-directions.md).
- Wrote [overview](overview.md).

## [2026-11-07] setup | Diagram system (draw.io)
- Added the local draw.io viewer (`tools/drawio/`, Apache-2.0) and `build.js`, which generates `wiki/diagrams/index.html` from `slides.json`.
- Created 5 diagrams: what Brain2Qwerty does, v1 vs v2 pipeline, BCI stack, project options, roadmap.
- Installed the VS Code extension `hediet.vscode-drawio` for editing.

## [2026-11-07] query | Direction decision + architecture
- Filed [questions/direction-decision](questions/direction-decision.md): the chosen direction (trustworthy neural text entry), the novelty, commercial and licence evidence, and the rejected or deferred options. Secondary-source figures are marked.
- Filed [questions/architecture](questions/architecture.md): six layers, trust-core modules, data flow, NeuralTextStream, open-core split, provenance rule, proposed code layout (`neurotext` is a placeholder), roadmap, open design questions.
- Added a "Decision (2026-11-07)" section to [questions/research-directions](questions/research-directions.md) and a "Project direction" section to [overview](overview.md).
- Created diagrams `06-architecture-layers`, `07-data-flow` and `08-roadmap-v2`. Added them to `slides.json` and rebuilt `diagrams/index.html`.
- Updated [index](index.md): 3 diagrams and 3 question pages (including [reading-list](questions/reading-list.md)).

## [2026-11-08] query | Project plan
- Filed [questions/project-plan](questions/project-plan.md): milestones M0–M7 with estimated windows, task checklists and "done when" criteria; licence rule; risks and fallbacks; working process; year-1 success metrics; the M0 checklist for the next 2 weeks.
- Created diagram `09-milestones` (Gantt-like timeline, dates marked as estimates). Added it to `slides.json` as slide 9 and rebuilt `diagrams/index.html`.
- Updated [overview](overview.md) ("Project direction") and [index](index.md) (diagram row and Questions row).

## [2026-11-08] setup | Progress tracker (effort + timeline)
- The user replaced the estimated windows with targets: M0 by 2026-11-09, M1–M7 by 2026-11-15.
- Created `progress/tracker.json` (source of truth). Seeded milestones R and M0–M7 with 66 tasks. R holds the 19 done tasks of 2026-11-07 with their agent effort (approximate times). 6 tasks are `externally_blocked`.
- Created `tools/progress/build.js`. It generates the offline dashboard [progress/index.html](progress/index.html): summary cards, milestone rows, SVG timeline, task table.
- Updated [questions/project-plan](questions/project-plan.md): target windows and a "Timeline policy (2026-11-08)" section.
- Redrew diagram `09-milestones` on a day scale (11-07 → 11-16) with an externally blocked lane. Updated its caption and rebuilt `diagrams/index.html`.
- Added a "Progress tracking" section to `CLAUDE.md`. Added a Progress line to [index](index.md).

## [2026-11-08] setup | Session continuity (memory mirror, HANDOFF.md, snapshot script)
- Created `HANDOFF.md`: project summary, read-first list, working rules, background processes, status, next steps, how to resume.
- Created `tools/session/snapshot.js`: mirrors Claude's memory notes into `agent-memory/` and rebuilds the progress dashboard.
- Created `tools/session/start.js`: prints a resume context block.
- Added a "Session continuity" section and layout rows to `CLAUDE.md`.
- Claude Code hooks for automatic snapshots: not set up. This waits for a user decision.

## [2026-11-08] setup | Project named Fidetype
- The user named the project **Fidetype** (*fides*, Latin: trust, + type). The package is `fidetype`. The placeholder `neurotext` is retired. "Veritype" was rejected: it has a pending US software trademark.
- Renamed `src/neurotext/` to `src/fidetype/`. Updated all imports, `pyproject.toml` (name, description, keywords, classifiers, repository URL) and `uv.lock`. 41 tests pass.
- Rewrote `README.md`: what it does, why, architecture, status, quick start, layout, data and licences.
- Replaced the placeholder name in [questions/architecture](questions/architecture.md), [questions/project-plan](questions/project-plan.md), [overview](overview.md), `diagrams/slides.json`, `CLAUDE.md` and `HANDOFF.md`. Marked tracker task M0-07 done.
- The GitHub repo and the local folder keep the name `stealth-project` until the rename.

## [2026-11-08] query | GPU path: native Windows ROCm
- Tested PyTorch on the AMD RX 7800 XT (gfx1101). Native Windows ROCm 7.2.1 + torch 2.9.1 works. bf16 matmul 51.7 TFLOPS. A training step is about 10–15× faster than on the CPU.
- Found the MAX_PATH catch: rocBLAS crashes if the venv path is long. The fix is a short venv path, `C:\venvs\fidetype-rocm`.
- Added `tools/env/setup_rocm.ps1` (builds the venv from zero) and `tools/env/gpu_smoke.py` (smoke test). The smoke test and the 41 repo tests pass in the venv.
- Filed [questions/compute-setup](questions/compute-setup.md). Linked it from [index](index.md), [project-plan](questions/project-plan.md) and [architecture](questions/architecture.md) (open question 3 resolved).

## [2026-11-08] ingest | SpanishBCBL inspection (S25)
- Loaded subject S25 (2 sessions × 2 blocks) in MNE. 322 channels. Head digitisation is present (3 fiducials, 5 HPI, 315 head-shape points).
- The key triggers carry the Windows VK code of each key. The log and MEG clocks drift by about 0.5 ms/s. A per-block offset + slope fit matches 9366/9367 key presses (median residual 0.33 ms).
- Filed the results in [experiments/2026-11-08-inspect-spanishbcbl/results.md](../experiments/2026-11-08-inspect-spanishbcbl/results.md) (indexed under a new "Experiments" section).
- Added "Inspection findings (2026-11-08)" and an M1 "Our take" to [entities/spanishbcbl-dataset](entities/spanishbcbl-dataset.md). Corrected the access line: the dataset is not gated. Licence CC BY-NC 4.0. ~268 GB MEG.
- Added the optional `data` extra (mne, scipy) to `pyproject.toml`.

## [2026-11-08] setup | CI (GitHub Actions)
- Added `.github/workflows/tests.yml`: pytest on CPU via uv. Commit c95a3c7.
- The first run is green (41 tests, 10 s).
- With CI, the GPU path and the S25 inspection, M0 is done (2026-11-08, target 11-09). Ticked the M0 checklist in [project-plan](questions/project-plan.md). The MEG download continues in the background.

## [2026-11-08] ingest | Open-source case studies (SGLang, LangChain, OpenTelemetry)
- Ingested three verified web-research reports (numbers as of 2026-11-08). No raw files saved in `references/`.
- Created [sources/case-study-sglang](sources/case-study-sglang.md), [sources/case-study-langchain](sources/case-study-langchain.md) and [sources/case-study-opentelemetry](sources/case-study-opentelemetry.md): numbers, origin, growth, adoption drivers, governance, money, criticisms, lessons for Fidetype. UNVERIFIED items are marked.
- Created entity pages [BIDS](entities/bids.md), [Lab Streaming Layer](entities/lab-streaming-layer.md) and [IEEE P2731](entities/ieee-p2731.md).
- Updated [index](index.md) (Sources, Entities).

## [2026-11-08] query | Open-source growth playbook
- Filed [questions/open-source-playbook](questions/open-source-playbook.md): thesis (OTel/BIDS for the standard, SGLang for credibility, LangChain for the company), comparison table, stages 0–5 with checklists and exit criteria, success metrics, cheap actions now (none done yet), BCI standards landscape, risks.
- Created diagram `10-open-source-path`. Added it to `slides.json` as slide 10 and rebuilt `diagrams/index.html`. Checked the rendering with headless Edge.
- Added an "Open-source path" line to [overview](overview.md) and an "Open-source growth" note under M5 in [project-plan](questions/project-plan.md).
- Updated [index](index.md) (Questions, Diagrams).

## [2026-11-08] query | M1-A data layer + preprocessing
- Added `fidetype.data`: SpanishBCBL file discovery, log parsing, per-block drift-fit alignment, text alignment, `assign_split` (sentence hash), preprocessing (tSSS, notch, 0.5–45 Hz, 100 Hz) and a block cache. CLI: `tools/data/preprocess_spanishbcbl.py`.
- Discovery finds 81 typing blocks. 15570/15571 key presses align (median residual 0.18–0.33 ms). tSSS removes the 23.3 Hz peak in all cached blocks.
- 224 unique sentences: 184 train / 16 val / 24 test. Typed text equals target text in 41 % of trials.
- The first detached run stalled for about 2 h on RAM contention. The CLI now has a memory budget (`--mem-budget-gb`).
- Filed [experiments/2026-11-08-m1a-data/results.md](../experiments/2026-11-08-m1a-data/results.md). Ticked the loader item in [project-plan](questions/project-plan.md). The cache job still runs in the background.

## [2026-11-08] query | Char LM + CTC beam
- Added `fidetype.lm`: 6-gram modified Kneser–Ney char LM (Tatoeba EN/ES, CC BY 2.0 FR; SpanishBCBL sentences removed) and CTC prefix beam search with LM fusion and n-best output.
- Simulator: median CER 0.281 → 0.200, WER 0.729 → 0.386. 91 ms per 40-character sentence.
- The top-10 oracle gain is small (0.200 → 0.167). LM fusion makes the character confidences over-confident.
- Filed [experiments/2026-11-08-lm-beam/results.md](../experiments/2026-11-08-lm-beam/results.md). Ticked the LM item in [project-plan](questions/project-plan.md).

## [2026-11-08] query | Trust core v0 on simulator
- Added `fidetype.trust` (calibration, conformal sets, guard, policy), `fidetype.interact` (simulated user) and `fidetype.eval.ewpm` / `fidetype.eval.harness`.
- The trust policy cuts wrong commits 0.29–0.47 → 0.02–0.09. It costs 7–16 % eWPM against LM top-1. It commits 0 % fluent text on shuffled or flat input (always-commit: 98–100 %).
- Filed [questions/trust-core-v0-results](questions/trust-core-v0-results.md) and [experiments/2026-11-08-m2-trust-sim/results.md](../experiments/2026-11-08-m2-trust-sim/results.md).
- Updated [project-plan](questions/project-plan.md): ticked the M2 items, added the M2 known gaps, and added the M3 "Revised claim (2026-11-08)". Updated [index](index.md) (Questions, Experiments).

## [2026-11-08] query | Scope: OpenTelemetry-level neural input standard
- The user widened the scope. Fidetype is now the vendor-neutral standard and trust layer for neural input: wrist EMG, EEG, MEG/OPM-MEG and implants (through interfaces such as Apple BCI HID). Research MEG stays the credibility base and the Paper 1 test case.
- Reasons: the consumer market ceiling, no standard for decoded output with confidence, and IEEE P2731 unpublished since 2018. Risks: spread too thin, data licences, big players build their own.
- Added "Scope decision (2026-11-08)" with an "Our take" block to [direction-decision](questions/direction-decision.md).
- [architecture](questions/architecture.md): multi-modality adapters table, non-character vocabularies in the trust core, link to the [spec v0.1](../spec/neuraltextstream-v0.1.md), and three open questions (wire protocol, discrete events vs per-frame distributions, on-device runtimes).
- [project-plan](questions/project-plan.md): scope note, explicit M6 adapter list (EMG first, EEG via BrainFlow/LSL, implant/HID bridge), M5 items for the spec and a conformance test suite, and the Year-1 metric "≥1 decoder outside the project emits NeuralTextStream". Milestone targets are unchanged.
- Added a status note to [open-source playbook](questions/open-source-playbook.md) and a scope paragraph to [overview](overview.md).
- Success metric: decoders and devices that emit NeuralTextStream, not stars. The user accepts a multi-year horizon and the need for outside partners, people and funding.

## [2026-11-08] ingest | Neural input landscape (devices, SDKs, standards, regulation)
- Filed [sources/neural-input-landscape-2026](sources/neural-input-landscape-2026.md) from a verified agent web-research report. No raw file saved. UNVERIFIED claims stay marked.
- Novelty verdict: no standard for decoded neural output with confidence exists. The closest are Apple BCI HID (neural) and W3C EMMA 1.0 (non-neural). Positioning: NTS = "EMMA for neural input, OpenTelemetry-style".
- New entities: [Apple BCI HID](entities/apple-bci-hid.md), [W3C EMMA](entities/w3c-emma.md), [Meta Neural Band](entities/meta-neural-band.md), [BrainFlow](entities/brainflow.md), [Dryad intracortical datasets](entities/dryad-intracortical-datasets.md) (CC0).
- Updated [emg2qwerty](entities/emg2qwerty.md) (CC-BY-NC-4.0, sibling Meta sets, no longer a licence stub), [Lab Streaming Layer](entities/lab-streaming-layer.md) (NTS-over-LSL binding), [IEEE P2731](entities/ieee-p2731.md) (ISO/IEC SC 43, TS 27571, CEN-CLC).
- [architecture](questions/architecture.md): new "Adapter priority (2026-11-08)" section: LSL/BrainFlow, then the Apple HID bridge, then Dryad replay; follow-ups Neurosity, Emotiv, Meta Web Apps shim.
- [project-plan](questions/project-plan.md): M6 adapter list reordered to that priority. Dryad CC0 enables commercially clean trust-layer evaluation. Milestone dates unchanged.
- [direction-decision](questions/direction-decision.md): novelty check note under the scope decision. Updated [index](index.md) (Sources, Entities).

## [2026-11-08] setup | OSS foundation files + spec v0.1 published
- Commit 677ba0e added the open-source foundation files: [CONTRIBUTING](../CONTRIBUTING.md), [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md) (Contributor Covenant), [GOVERNANCE](../GOVERNANCE.md) (founder-led, with a written path to neutral governance), [SECURITY](../SECURITY.md) and [CITATION.cff](../CITATION.cff).
- Published [spec/neuraltextstream-v0.1.md](../spec/neuraltextstream-v0.1.md) with 20 conformance cases. Status: Development. `spec/feps/` holds the FEP process.
- Added issue templates (bug, feature, adapter request) and a PR template under `.github/`.
- On GitHub: enabled Discussions and opened the public roadmap issue [#1](https://github.com/zhangzibo/fidetype/issues/1). CI is green on 677ba0e.
- Ticked the cheap actions and the Stage 0 spec item in [open-source playbook](questions/open-source-playbook.md). Only the GitHub Pages site is still open.
- Still open: a conformance test suite (the validator exists), and moving producers' `meta` keys to the namespaced conventions before spec v0.2.

## [2026-11-08] query | M1-B decoder: first real results (no MEG use yet)
- Filed [questions/decoder-m1-results](questions/decoder-m1-results.md) from the [M1-B experiment](../experiments/2026-11-08-m1b-decoder/results.md). Own ConvCTC, 10 M params. 5 subjects (about 2.5 h): test greedy CER 0.670, shuffled-MEG 0.669, zeros 0.858. The model uses a text prior, not the MEG. M1 target (≈0.59) not met.
- Key lesson: always report the shuffled-MEG control. Added a "Control conditions" section to [error metrics](concepts/error-metrics.md). Linked to the null-input audit in [trust core v0 results](questions/trust-core-v0-results.md) and to [data scaling](concepts/data-scaling.md).
- [project-plan](questions/project-plan.md) M1: ticked the decoder items; added sanity check, full-cache retrain, low-data tuning and cross-subject items; added a status line.
- [compute-setup](questions/compute-setup.md): MIOpen notes (`MIOPEN_FIND_MODE=FAST`, length padding, CPU contention, `torch_threads`, gemm fallback).
- Updated [index](index.md) (Questions, Experiments).

## [2026-11-08] query | Sanity check: keystroke signal present
- Wrote [experiments/2026-11-08-m1-sanity/results.md](../experiments/2026-11-08-m1-sanity/results.md) from `results/decoding.json`. Linear ridge classifier, keystroke-locked epochs (−0.5..+0.5 s, 306 channels), 5-fold CV grouped by trial, 6 subjects.
- Hand window 0.83–0.96 (chance 0.60), letter window 0.31–0.49 (chance about 0.14). Both controls (shuffled labels, random times) at chance. Peaks at −10..+60 ms. GFP 2–4.5× above baseline.
- Verdict A: the cache and the alignment are correct. The M1-B CTC failure comes from data volume or the model.
- Added a "Sanity check" section to [decoder M1 results](questions/decoder-m1-results.md). Ticked the item in [project plan](questions/project-plan.md) M1; added the keystroke auxiliary-loss item.

## [2026-11-08] query | Beam re-tune: search errors fixed
- Source: [experiments/2026-11-08-beam-retune/results.md](../experiments/2026-11-08-beam-retune/results.md). The old n-best misses were search errors: `prune_topk = 10` cut a true character in 90 % of median sentences, and beam 16 was too narrow.
- New `RETUNED` preset in `fidetype.lm` (beam 256, no top-k cut, w 1.25, bonus 1.0, numpy vector search). Old defaults unchanged. recall@10 0.075 → 0.47 (median Tatoeba).
- Trust pipeline (simulator): n-best miss 0.73 → 0.00. Trust policy 25.3 eWPM vs always-commit 25.8, with 0.033 vs 0.108 wrong commits.
- Added section 5 "Beam re-tune" to [trust core v0 results](questions/trust-core-v0-results.md). Updated the M3 revised claim in [project plan](questions/project-plan.md) (simulator only; real-data confirmation pending) and added M2 items: guard re-tune, conformal risk control, per-word OFFER.
- Updated [index](index.md) (Experiments).

## [2026-11-08] query | Trust core on real MEG (first test)
- Source: [experiments/2026-11-08-m2-real-keystroke/results.md](../experiments/2026-11-08-m2-real-keystroke/results.md). New code: `src/fidetype/decoders/keystroke.py` (synchronous keystroke decoder, oracle timing, per-subject logistic regression → NeuralTextStream).
- Decoder (test, 11 subjects, 17 sentences): key acc 0.390 (chance 0.13; shuffled MEG 0.111, permuted labels 0.099). Greedy CER 0.590 (controls 0.77). LM beam (`RETUNED`, w 0.5) CER 0.531. The true sentence is never in the n-best.
- Trust: always-commit LM top-1 wrong-commit 100 % (83 % fluent Spanish); trust policy 0 % (always OFFER); eWPM 9.61 vs 9.70, CI crosses 0. Null input: LM top-1 commits fluent text on 83–100 %, trust 0 %. Guard AUROC 0.85 (top-1 CER above median), 0.98 (uniform vs real), about 0.5 (shuffled vs real). Conformal coverage 0.
- Degenerate test: the trust layer is safe, but usefulness is untested (no correct candidates).
- Added section 6 to [trust core v0 results](questions/trust-core-v0-results.md) and a section to [decoder M1 results](questions/decoder-m1-results.md). Updated M1, M2 and M3 in [project plan](questions/project-plan.md). Updated [index](index.md) (Experiments).

## [2026-11-08] query | M1-C: keystroke auxiliary loss makes the CTC decoder use the MEG
- Source: [experiments/2026-11-08-m1c-decoder-aux/results.md](../experiments/2026-11-08-m1c-decoder-aux/results.md). Recorded after the PC crash at 16:44 (the runs finished at 16:21).
- Code: `src/fidetype/decoders/` (keystroke heads, `key_pos`/`key_label` in the dataset, `data.blocks`, `train.init_from`, `hard_exit()`, paired-bootstrap control gap). 8 new decoder tests.
- 11 subjects, 20 pinned blocks. Test shuffled-MEG gap: r0 −0.001, r1 small −0.002, r2 (weight 0.5) +0.116, r3 (weight 1.0) +0.116, r4b (keystroke-pretrained) +0.156. Best test CER 0.619 (mean over subjects 0.624). The M1 target 0.59 is not met.
- Added an M1-C section to [decoder M1 results](questions/decoder-m1-results.md). Added "In Fidetype" to [CTC](concepts/ctc.md). Added the M1-C control example to [error metrics](concepts/error-metrics.md). Ticked the items in [project plan](questions/project-plan.md) M1. Updated [index](index.md).

## [2026-11-08] query | OFFER_WORDS: per-word choices and partial correction
- Source: [experiments/2026-11-08-m2-offer-words/results.md](../experiments/2026-11-08-m2-offer-words/results.md). Recorded after the PC crash at 16:44 (the work finished at 16:42).
- Code: action `OFFER_WORDS` in `src/fidetype/trust/policy.py`; word-level user `UserConfig.aac_gaze()` in `src/fidetype/interact/`; word slots and new metrics (KSR, system word accuracy) in `src/fidetype/eval/`. 24 new tests. Defaults unchanged.
- Simulator worst preset: trust + OFFER_WORDS 20.45 / 20.46 vs trust 19.49 / 19.40 eWPM (paired CIs [0.36, 1.57], [0.40, 1.74]). Median preset: no change.
- Real MEG: the fit never selects OFFER_WORDS (system word accuracy 0.10). Trust 2.96, always commit 2.31, gaze typing alone 3.14 eWPM. No BCI policy beats the no-BCI baseline.
- Added section 7 to [trust core v0 results](questions/trust-core-v0-results.md). Added "Usefulness metrics: a no-BCI baseline" to [error metrics](concepts/error-metrics.md). Ticked the item and added the no-BCI baseline to the M3 claim in [project plan](questions/project-plan.md). Added a note to [overview](overview.md). Updated [index](index.md).

## [2026-11-08] query | AMD driver check: versions are by design, crash cause open
- Correction: the two AMD driver versions (iGPU 32.0.21045.16010, RX 7800 XT 32.0.32015.7029) both come from Adrenalin 26.10.1. Since Adrenalin 25.10.2, RDNA1/RDNA2 GPUs (incl. Ryzen iGPUs) use a separate maintenance branch. The earlier "mismatch" note was wrong.
- The cause of the 16:44 blue screen (0x7E in `amdkmdag`) is not confirmed: a driver bug in either branch, or hardware. The minidump is not analysed yet.
- ROCm 7.2.1 PyTorch needs driver 26.2.2 or newer; 26.10.1 works; 26.10.2 is very likely safe. Do not install the "ROCm 10.1" driver (26.10.41.05).
- Plan: disable the iGPU, optional Adrenalin 26.10.2 with Factory Reset, then verify (torch check, `gpu_smoke.py`, short training + 10–20 min idle). Preprocessing stays paused until this passes.
- Updated the "Driver crash" section of [compute setup](questions/compute-setup.md), `HANDOFF.md` and tracker task M0-15.

## [2026-11-08] query | GPU stress test after iGPU disable
- Repeated the crash condition of 16:44 (bugcheck 0x7E in `amdkmdag`) with the iGPU disabled in Device Manager.
- Real ConvCTC training (`config-r2-small-aux0.5.json`): 721 s, epoch 161, best val CER 0.606. Then 1200 s GPU idle with the CUDA context alive. Result: `RESULT PASS`, no crash.
- System event log since 17:55: no ID 41/1001/4101, WHEA or amdkmdag events.
- The SpanishBCBL preprocessing resumed at 18:38 (`--workers 1 --mem-budget-gb 14`). The crash cause stays unconfirmed.
- Updated the "Driver crash" section of [compute setup](questions/compute-setup.md), `HANDOFF.md` and tracker tasks M0-15 (real finish time), M0-16 and M1-07.

## [2026-11-08] query | M1-C2: beam + char LM on the r4b CTC streams
- Source: [experiments/2026-11-08-m1c2-beam-lm/results.md](../experiments/2026-11-08-m1c2-beam-lm/results.md) (commit dcff1de). CPU only, about 14 min.
- Test CER (209 sentences): greedy 0.619 → beam no LM 0.605 → beam + Spanish 6-gram char LM, val-tuned (w 0.25, bonus 1.0) 0.590 [0.576, 0.604]. Shuffled-MEG gap +0.132 [+0.117, +0.147].
- The `RETUNED` settings as they are (w 1.25, bonus 1.0) make it worse: 0.633. The true sentence is in the 20-best for 0 test sentences.
- Greedy is still 0.619, so the M1 greedy target (0.59) is not met.
- Added an M1-C2 section to [decoder M1 results](questions/decoder-m1-results.md). Updated [index](index.md) and [overview](overview.md) (one line, on 2026-11-09).

## [2026-11-08] query | S1/S18 check (repeated participants) + M2-15
- S1/S18 are one person (P01); so are S4/S14 and S5/S10/S21. The data index is correct. Splits are by sentence hash, so there is no train/test leakage (commit 9f8808e).
- M1-C mean CER over people 0.6210 vs over subjects 0.6237 (effect ≤ 0.003). From now on, report means over participants.
- The paper says 20 MEG participants. The release has usable data for 19 (S13 has no logs).
- New page [SpanishBCBL repeated participants](questions/spanishbcbl-repeated-participants.md). Updated [SpanishBCBL dataset](entities/spanishbcbl-dataset.md), [decoder M1 results](questions/decoder-m1-results.md) and [index](index.md).
- M2-15 done (commit 422406b): `TemperatureScaler.transform_stream` keeps all stream metadata.

## [2026-11-09] setup | Resume preprocessing
- The user stopped the SpanishBCBL preprocessing at about 23:35 on 2026-11-08 for a shutdown (9 ok in that run, 31 queued; S2/ses1_block2 discarded). An auto-sleep watcher set up at about 23:20 was cancelled; sleep settings were restored.
- Restarted at 18:13:44 on 2026-11-09 (`--workers 1 --mem-budget-gb 14`): launcher PID 1584, script PID 16724. 50 blocks cached, 31 queued. First block S2/ses1_block2 (est 16.1 GB).
- RAM: 31.2 GB total, 15.9 GB free at the start, pagefile 6.9 GB. Blocks of 16–19 GB can page. See the memory warning in `HANDOFF.md`.
- Updated `HANDOFF.md` and tracker tasks M0-17, M0-18, M0-19, M1-07, M1-14, M1-16, M1-17, M2-15.

## [2026-11-09] setup | Queue M1-15 training after preprocessing
- New detached queue (PID 1128): `C:\Users\zhang\bci-data\runs\queue-2026-11-09\queue.ps1`, log `queue.log` in the same folder. It runs outside the repo.
- It waits until the SpanishBCBL preprocessing ends (2 checks in a row), waits 2 min, then trains M1-15 r1 (`m1-15-sentence-context-r1`, one `-Resume` on failure), then runs `infer_sentence` with controls and the LM weight grid. Max 1 heavy job at a time.
- Hard stop: if it still waits at 2026-11-10 08:00, it exits without training. It changes no power settings.
- Dry run of the stage-1 check: "not finished" (preprocessing 2 ok, 0 failed, 0 running, 29 queued).
- Updated `HANDOFF.md` (background processes, next steps) and tracker tasks M0-19 (done), M0-20 (new, done), M1-15 (in progress).

## [2026-11-09] query | M1-15 r1 sentence-context decoder results
- The overnight queue finished ("QUEUE DONE" 22:05:05). Preprocessing ended at 20:24:09: ok=30, failed=1. 80 of 81 typing blocks are now cached.
- The failed block is S1/ses1_block1 (it also failed on 2026-11-08): "sidecar invalid: segment 48+ empty, key sample outside the segment". `Block1.fif` (1.90 GB) ends before the typing log, and the dataset has no `Block1-1.fif` split part.
- M1-15 r1 is undertrained: the PC was in S3 sleep from 20:32:38 to 22:00:03, and `max_minutes` counts wall-clock time. Only 9 of 150 epochs ran (about 5 min of compute). Best val CER typed 0.6003 at epoch 8, at peak lr.
- Test (mean over sentences, vs target): greedy 0.619, beam + LM (w 1.0) 0.532. M2-10 logistic regression: 0.597 / 0.531. Shuffled-MEG gap +0.172 [+0.158, +0.186] greedy, +0.219 [+0.200, +0.238] beam + LM. Conv-only vs Conv + Trans val key accuracy 0.387 vs 0.397. WER above 1 comes from insertions (not a bug).
- Trust harness (M2-14 set-up, CPU, 250 s) on the r1 streams: trust 2.98 eWPM, always commit 2.38, gaze typing only 3.14. No change to the trust picture.
- New: `experiments/2026-11-09-m1-15-sentence-context/results.md`, `results/` (metrics copy, training curve, logs, eWPM json), `ewpm_check.py`. Updated `wiki/questions/decoder-m1-results.md`, `wiki/index.md`, the experiment README, `HANDOFF.md`, tracker (M0-20, M1-14 done, M1-15, new M1-18).
- Next: M1-15 r2 (full schedule, sleep prevented, same 20 blocks), then the full-cache r4a → r4b retrain.

## [2026-11-10] setup | M1-15 r2 launch with sleep prevention
- Code (commit 6132c60): `src/fidetype/utils/power.py` keeps Windows awake during training (`SetThreadExecutionState`, cleared on exit). `max_minutes` now counts active compute time: a gap over 5 min ("suspend gap detected") is not counted, and the total is in the checkpoint, so a resume keeps the budget. Applies to `train.py` and `train_sentence.py`.
- `train_sentence.py`: opt-in `optim.schedule: "plateau"`. Constant LR after warm-up, halved after 5 evals without improvement of the smoothed val CER. Training stops on the val trend, not at a fixed epoch count. The trend is logged per eval in `train.log` and `status.json`.
- `infer_sentence.py --head conv` gives the Conv-only (pre-Transformer) head its own CER, in a separate output folder.
- New config `experiments/2026-11-09-m1-15-sentence-context/config-r2.json`: r1 config (same 20 blocks, same subjects), plateau schedule, `epochs` 2000, `max_minutes` 300 (active-time cap). README run plan: r2 = this rerun; the causal run is r3.
- Queue `C:\Users\zhang\bci-data\runs\queue-2026-11-10\queue.ps1` (PID 31416) started 19:16: r2 training on the GPU (cuda, bf16, about 37 s per epoch at the start), then inference with the final head and the conv head. AC sleep set from 1800 s to never; the queue restores it at the end. Hard stop 8 h after start.
- 13 new tests (`tests/test_power_budget.py`); 72 decoder tests pass on CPU.

## [2026-11-10] query | Public datasets survey
- Web survey of about 30 public datasets for Fidetype: wrist sEMG, EEG, MEG, intracortical, sEEG/ECoG, classic P300/SSVEP spellers, pretraining corpora. Metadata only (repository APIs, dataset cards, papers). No data downloaded.
- New: `wiki/questions/public-datasets.md` (comparison table, top 5, licence warnings, next actions, lab leads, open questions); entity pages `brain-to-text-25.md`, `willett-handwriting-2021.md`, `kt-semg-dataset.md`, `toronto-semg-typing-dataset.md`.
- Updated: `emg2qwerty.md` (108 users, 346 h, 308.4 GB archive, CC BY alternatives), `dryad-intracortical-datasets.md` (sizes, B2T '24, inner speech, unlicensed code repos), `overview.md` (data problem, sEMG as second testbed), `index.md`, `references/README.md` (links + licences), `HANDOFF.md` (one next-step line).
- Top 5: Brain-to-Text '25 (CC0), KT-sEMG (CC BY 4.0), emg2qwerty (NC), Willett 2021 handwriting (CC0), Toronto sEMG typing (CC BY 4.0).
- Licence flags: all Meta EMG sets and LibriBrain NC (emg2pose NC-SA); BNCI P300 CC BY-NC-ND; Dryad code repos have no licence; Toronto code CC BY-SA; TUEG, Armeni, MOUS, Cam-CAN under DUAs; Tsinghua SSVEP terms not stated. Contradiction noted: Du-IN listed as OpenNeuro ds005170, which is Chisco.
- Recommended first download: Brain-to-Text '25 `t15_copyTask.pkl` (57.79 MB, real RNN logits), then the 11.05 GB neural data; then KT-sEMG (21.0 GB).
- Tracker: M1-19 real agent numbers; new task M6-05.

## [2026-11-10] query | M1-15 r2 results
- r2 (plateau schedule, trend stop, sleep prevented) stopped after the epoch-42 eval: 13.0 active min, no suspend gap, `best.pt` epoch 19. Queue `queue-2026-11-10` done 19:38:47; AC sleep back to 30 min.
- Test (mean over sentences, CER vs target): greedy 0.577, beam + LM (w 1.25) 0.488. M2-10 logistic regression 0.597 / 0.531; r1 0.619 / 0.532 (r1 − r2 paired +0.042 greedy). Shuffled gap +0.214 [+0.200, +0.228] greedy, +0.258 beam.
- Conv-only head (`--head conv`): 0.602 / 0.503. Sentence context adds −0.025 [−0.031, −0.018] greedy, −0.015 beam. v1 had 0.31.
- Training curve: val CE minimum 1.991 at epoch 12, 2.498 at the end; val CER flat 0.557–0.573 from epoch 16. Overfitting; the stop fired correctly. LR cut every 5 evals after the last gain (4 cuts; `max_lr_reductions` is only a stop condition). r3 (causal): `patience_evals` 12, `max_lr_reductions` 2.
- eWPM check on the r2 streams (`ewpm_check.py r2 ewpm-r2`, CPU 284 s): trust 3.06, always commit 2.49, gaze only 3.14. True sentence in the 10-best for 1 of 209 test trials.
- Updated: `experiments/2026-11-09-m1-15-sentence-context/results.md` (r2 section, results files, `train_curve-r2.png`), `ewpm_check.py` (run suffix + output args), `wiki/questions/decoder-m1-results.md`, `wiki/overview.md`, tracker (M1-15 note, new M1-20), `HANDOFF.md`.

## [2026-11-10] setup | M1-15 full-cache + r3 queue
- Code (commit 4dd073b): `plateau_update` now caps the LR reductions at `optim.max_lr_reductions` (before, it was only a stop condition, so r2 logged 4 cuts with a limit of 3). New unit test `test_plateau_max_lr_reductions_is_a_cap`. 285 tests pass on CPU.
- `config-full-r1.json`: r2 settings on all 80 cached blocks (`subjects` and `blocks` null; 23 subject IDs = 19 participants). `config-r3.json`: r2 config (20 pinned blocks) with `lookahead_keys` 0 (causal). Both: `patience_evals` 12, `max_lr_reductions` 2.
- Data, full vs r2 (sentence instances train/val/test): 4026/437/637 vs 947/114/209. Keys: 149910/17354/24828 vs 38204/4855/8423. Unique sentences are the same (101/11/17): the full cache adds people and repetitions, not new sentences. The full test set is larger, so compare with r2 on the r2 blocks only.
- Memory: the cache is 4.4 GB (80 uncompressed `.npz`). The loader memory-maps each block and reads only the windows of one sentence. No loader change.
- Queue `C:\Users\zhang\bci-data\runs\queue-2026-11-10b\` (PID 8692): train full-r1, inference (final + conv head), train r3, inference, eWPM check for both. AC sleep set to never at the start, restored in `finally`. Hard stop 2026-11-11 06:53.

## [2026-11-10] query | Long-term standard roadmap
- User decision: Fidetype aims for full standardisation at OpenTelemetry scale; we build all of it (agents write code and docs, the user does outward-facing actions). M0–M7 are v0.1.
- New page `wiki/questions/roadmap-standard.md`: phases P1–P11 (spec 1.0, SDKs, collector, adapters, product-grade trust layer, benchmark + leaderboard, conformance + certification, docs + three-device demo, governance, adoption, research), each with goals, deliverables, exit criteria, effort and dependencies. Decisions: proto3 as source of truth and primary wire form, JSON Lines kept, Arrow for bulk, NPZ read-only, FlatBuffers not chosen; transports in-process, files, LSL, WebSocket, gRPC.
- Scale reference: `src/` 11,532 Python lines on disk (10,795 committed) vs Brain2Qwerty 5,555; LangChain and OpenTelemetry sizes marked rough. The gap is SDKs, adapters and integrations.
- Neural-data laws: Colorado, California, Montana, Connecticut cited from the landscape source; Chile, EU and US federal marked "to check".
- New diagram `11-roadmap-standard` (slides.json slide 11; rendering checked with headless Edge).
- Tracker: milestones P1–P11 (dates chosen because the schema needs them), 55 tasks (15 `externally_blocked`), and this run as M5-11.
- Linked from overview, project-plan, open-source-playbook, index; HANDOFF next steps.

## [2026-11-10] ingest | Brain-to-Text '25 copy-task logits
- Downloaded `t15_copyTask.pkl` (57,786,348 bytes; SHA-256 `7313b9a1…5e165e3`, equal to the Dryad API digest) and the dataset card to `C:\Users\zhang\bci-data\brain-to-text-25\` (outside the repo). Dryad file downloads need a login, so we used the HF mirror `Paulownia/Brain-to-text_25_data` and checked the digest.
- Pickle safety: opcode scan (no load) found only 4 numpy globals and no risky opcodes. Loaded only with a whitelist Unpickler (`fidetype.adapters.b2t25.safe_load`).
- Contents: 1,718 trials (1,628 with the 125k vocabulary), 15 days, logits (T, 41): blank, `SIL`, 39 ARPAbet (order checked: greedy path = stored raw phonemes in 1,709 trials). Published WER 0.0434 pooled, day 25 0.0044.
- Also downloaded CMUdict (BSD-2-Clause style, pinned commit) to `bci-data\lexicon\cmudict\`.
- New: `wiki/sources/brain-to-text-25-copytask.md`. Updated: `wiki/entities/brain-to-text-25.md`, `references/README.md` (downloaded-files table with SHA-256; SpanishBCBL row now "not gated, 280.4 GB"), `wiki/questions/public-datasets.md` (contradiction resolved), `index.md`.

## [2026-11-10] query | B2T '25 cross-device trust result
- Own adapter `src/fidetype/adapters/b2t25.py` (NTS, `vocab_type="phoneme"`, 80 ms frames, latency 0) and licence-clean phoneme → word route `src/fidetype/lm/phoneme_words.py` (CMUdict fuzzy lookup + Tatoeba unigram + char 6-gram; test WER 0.149). Harness: optional `Item.stream_text`. 17 new tests; 221 pass on CPU.
- `experiments/2026-11-10-b2t25-trust` (fit 812 / test 816 trials, `aac_gaze` user at the measured 159.3 chars/min): trust 11.55 eWPM, wrong-commit 0.059 vs always commit 11.45 / 0.610. Published-sentence gate 18.77 / 0.044 vs 19.61 / 0.194. Gaze only 4.08. AUROC −p_top1 0.797 (word), 0.884 (phoneme); word confidence 0.844. Null audit: shuffled/uniform 0 % commits; another trial's stream 22 % (ours), 0 % (gate).
- New: `wiki/questions/b2t25-trust-result.md`. Updated: `wiki/questions/trust-core-v0-results.md` (section 8), `index.md`, tracker (M6-05 real numbers, M6-06), `HANDOFF.md`.

## [2026-11-10] query | M1-15 full-r1 + r3 results, leakage checks
- queue-2026-11-10b finished at 23:04 (QUEUE DONE; AC sleep restored to 30 min). full-r1: 66.5 active min, early stop epoch 79, `best.pt` epoch 77. r3: 11.5 active min, early stop epoch 37, `best.pt` epoch 24. No suspend gap.
- Test (mean over sentences, CER vs target): full-r1 greedy 0.508, beam + LM 0.447 (mean over participants 0.498 / 0.436); Conv-only head 0.590 / 0.489. r3 (causal) 0.574 / 0.472; Conv-only 0.612 / 0.494. Shuffled gaps all exclude 0 (full-r1 +0.276 greedy).
- Like for like on the 209 r2 test instances (from the per-sentence files, no new inference): full-r1 0.497 / 0.437 vs r2 0.577 / 0.488 (−0.080 [−0.093, −0.067] greedy). r3 − r2: −0.003 greedy, −0.016 beam.
- Leakage: 0 test / val sentences in train (hash split re-checked on 80 sidecars). 0 in the Tatoeba LM text (exact, containment; 0 of 54 test word 4-grams). Near variants: 6 of 17 test sentences have a train sentence within CER 0.25. Difference-in-differences against the Conv-only head: about 0.013 greedy / 0.022 beam CER. Far sentences: 0.525 / 0.474.
- Zeros ≈ 0.8: the output length is known from the key times. Text-only baselines: fixed train sentence 0.688, positional prior 0.750, "eee" 0.888.
- eWPM: full-r1 trust 3.23 [3.08, 3.40] vs gaze only 3.15 (parity, first time above); commit 2.71. r3 trust 3.09 vs 3.14.
- M1 async target not met (sync only). M1 stays in progress.
- New: `wiki/questions/m1-15-full-r1-r3-result.md`, `experiments/2026-11-09-m1-15-sentence-context/results-full-r1-r3.md`, `analysis/*.py`, result files. Updated: `decoder-m1-results.md`, `overview.md`, `project-plan.md`, `spanishbcbl-repeated-participants.md`, `index.md`, tracker, `HANDOFF.md`.
