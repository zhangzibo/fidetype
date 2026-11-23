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

## [2026-11-11] query | M1-09 async decoder on the full cache, async check, M1 closed
- queue-2026-11-11-m1-09 finished at 02:45 (QUEUE DONE, all exit 0, no suspend gap). Small r4b-full: trend stop epoch 90 (best 74, 35.9 active min). Medium r4b-full-medium: epoch cap 100 (best 79, 51.8 active min; LR at the cosine floor).
- Test (CER vs target, 637 instances): medium greedy 0.506 (participants 0.495 ± 0.020), beam + LM val-tuned 0.475 (0.462); shuffled 0.760 / 0.732, zeros 0.925 / 0.771. Small 0.553 / 0.524.
- Async check (code read): `ConvCTC.forward(x, lengths, subjects)` has no key input. Segment = first key − 0.4 s to last key + 0.5 s; v2 uses first key − 400 ms to last key release + 400–500 ms (Methods 4.2, p. 12). Difference: our training uses key times as aux-loss labels; test split differs from v2.
- Near variants (same rule as M1-15): far 11 sentences medium 0.519 / 0.492; close 0.477 / 0.438. Per participant: 17 of 19 ≤ 0.59 greedy.
- Like for like: medium − M1-C on the 209 M1-C instances −0.125 [−0.142, −0.109] greedy; async medium − sync full-r1 −0.002 greedy, +0.028 beam.
- Fix: `infer.py` writes `participant` into `labels.jsonl` (the beam tables' participant mean fell back to subjects). 221 + 27 tests pass.
- M1 closed in the tracker. r5 (longer medium run) launched 17:36: queue-2026-11-11-m1-09-r5.
- New: `wiki/questions/m1-09-async-full-result.md`, `experiments/2026-11-11-m1-09-async-full/results.md`, `analysis/analyse.py`, `config-r5-medium.json`, `queue-r5.ps1`. Updated: `decoder-m1-results.md`, `overview.md`, `project-plan.md`, `synchronous-vs-asynchronous-decoding.md`, `index.md`, tracker, `HANDOFF.md`.

## [2026-11-11] query | M2-13 conformal risk control for the wrong-commit limit
- New module `src/fidetype/trust/risk_control.py` (own code): `crc_threshold` (conformal risk control, finite-sample correction, never-commit when infeasible), `ltt_threshold` (Learn then Test, fixed-sequence, binomial / Hoeffding–Bentkus p-values), `commit_calibration_data`, `CommitRiskControl`. Harness: `HarnessConfig.risk_control` and `TrustPipeline.calibrate_commit`. 19 new tests incl. Monte Carlo coverage; suite 239 passed, 4 skipped.
- `experiments/2026-11-11-m2-13-conformal` (CPU, about 8 min): 200 random cal/test splits of the B2T '25 test half and the MEG M1-15 full-r1 test set. B2T ours, n_cal 408: mean wrong-commit old 0.0586, CRC 0.0483, LTT 0.0345; eWPM 11.57 / 11.53 / 11.52. Published gate: 0.0441 / 0.0478 / 0.0345; eWPM 18.77 / 18.78 / 18.70. CRC p95 0.071–0.094 (marginal only). Earlier-half → later-half calibration: CRC 0.0625 (drift). MEG: all commits wrong; no method gains eWPM.
- New: `wiki/sources/conformal-risk-control.md`, `wiki/sources/learn-then-test.md` (arXiv abstract pages read; PDFs not stored), `wiki/concepts/conformal-risk-control.md`, `wiki/questions/m2-13-conformal-result.md`. Updated: `b2t25-trust-result.md`, `trust-core-v0-results.md`, `project-plan.md`, `reading-list.md`, `index.md`, `references/README.md`, spec informative note in section 2.3, tracker M2-13.

## [2026-11-11] query | M1-26 r5 longer medium async run: no gain
- queue-2026-11-11-m1-09-r5 finished at 18:45 (QUEUE DONE, beam exit 0, AC sleep restored to 30 min). Training: cosine over 200 epochs, early_stopped at epoch 76 (trend stop), best epoch 55, best val CER typed 0.4958 (r4b-full-medium 0.4944 @ 79). LR still 2.09e-04 at epoch 75.
- Test (637 instances): greedy 0.516 [0.504, 0.527], beam + LM val-tuned 0.484; mean over participants 0.504 / 0.470; shuffled 0.759, zeros 0.922 (greedy).
- r5 − r4b-full-medium, paired per sentence: test greedy +0.009 [+0.003, +0.015], beam + LM +0.009 [+0.002, +0.016]; val greedy +0.003 [−0.004, +0.009], beam +0.004 [−0.004, +0.012]. CIs over instances of 17 sentences, so too narrow.
- Headline M1 model stays r4b-full-medium (0.506 / 0.475). More epochs of the same model do not help; next gains need more data, model changes or seed / checkpoint ensembles.
- New: `experiments/2026-11-11-m1-09-async-full/results/beam-m1-09-r5-medium/`. Updated: `experiments/2026-11-11-m1-09-async-full/results.md` (section 7), `wiki/questions/m1-09-async-full-result.md`, tracker (M1-26 done; M1-25, M2-13 agent runs), `HANDOFF.md`.

## [2026-11-11] query | Roadmap scope: intent beyond text (P12) and public benchmark hub (P13)
- User decision: the long-term roadmap explicitly includes intent beyond text and a public benchmark hub. Priorities and the order of P1–P11 do not change; text entry stays first.
- P12 "Beyond text: intent and control" (2027-07-01 → 2027-12-31): output-agnostic core + output profiles (text, discrete intent, continuous control), COMMIT/OFFER/ABSTAIN for intents, confidence-gated and rate-limited actuation (velocity scaling, dead-man hold, safe-stop), Apple BCI HID target, cursor/click datasets to survey (licences not verified). Tasks P12-01..P12-07 (P12-07 externally blocked).
- P13 "Public benchmark hub" (2027-07-01 → 2027-12-31): extends P6, adds dataset registry, CRC/LTT guarantee reporting, PR submissions scored in CI, later intent tracks. Tasks P13-01..P13-05 (P13-05 externally blocked).
- Spec: informative open question 11 "Future output profiles" (no field change).
- Updated: `roadmap-standard.md`, `direction-decision.md` (scope note 2026-11-11), `spec/neuraltextstream-v0.1.md`, diagram 11 + `slides.json`, tracker, `index.md`, `HANDOFF.md`.

## [2026-11-11] ingest | Toronto sEMG typing dataset + EMG adapter + trust run (M6-07)
- Downloaded `EMG typing dataset.zip` (Borealis doi:10.5683/SP3/KV65VI, CC BY 4.0, 2,766,730,294 bytes, MD5 equals the Borealis digest). Extracted only data files (the zip also holds `.git` and Python code). Isolated, metronome-paced key presses (5 space + 10 of one letter per file), 19 people × 2 days, 16 forearm channels at 2 kHz; no text.
- New adapter `src/fidetype/adapters/toronto_semg.py`: own Intan RHD reader, keylog alignment (keylog time − file start + Lag), canonical key-press stream (`vocab_type="key"`, `blank_id=null`) and CTC character form. 10 tests; suite 249 passed, 4 skipped. **No spec change.**
- Experiment `experiments/2026-11-11-emg-toronto/`: small CNN (GPU, 48 min for 9 runs). Day-2 key accuracy: cross-session 0.168, cross-subject 0.209, session-calibrated 0.299; label-permuted control 0.022.
- Trust on 551 composed test sentences (held-out Tatoeba, real day-2 presses): wrong-commit always-commit 0.541 / 0.882 / 0.962 → trust 0.004 / 0.004 / 0.000; eWPM 7.81 → 8.02 (calib), 4.10 → 4.68 (xsession), 3.53 → 4.08 (xsubject); gaze only 4.27. CRC/LTT feasible (n 142), equal to the plug-in policy here. Null audit: trust commits 0 % on shuffled, zeros and permuted-decoder streams.
- New: `wiki/sources/toronto-semg-typing.md`, `wiki/questions/emg-toronto-trust-result.md`. Updated: entity page, `references/README.md`, `index.md`, tracker (M6-07), `HANDOFF.md`.

## [2026-11-11] query | M2-16 online re-calibration of the commit guarantee under drift
- Problem: offline CRC (M2-13) needs exchangeable data; within-day drift on B2T '25 gave wrong-commit 0.0625 > 0.05.
- New module `src/fidetype/trust/online_risk.py` (own code): `OnlineCommitRiskControl` with methods `window` / `decay` (weighted CRC, approximate), `aci` (threshold update, long-run bound for any sequence, needs only the realised loss) and `aci_window` (ACI on the level of a window CRC, long-run bound, needs full feedback); `OnlineTrustPolicy`; `weighted_crc_threshold`. Delayed / out-of-order / missing feedback. 20 tests; suite 294 passed, 4 skipped.
- Experiment `experiments/2026-11-11-m2-16-online-recal/`: B2T ours drift case 0.0625 → window 0.0453, decay 0.0417, aci 0.0502, aci_window 0.0478 (eWPM 11.55 → 11.49–11.52). EMG cross-session: offline pure CRC 0.0635 → 0.040–0.053. Full-day cold start: aci 0.0442. 50-trial windows reach 0.10–0.12 (as i.i.d. noise). Noticed-only feedback: aci 0.0515 (B2T), 0.0635 (EMG).
- New: question page `m2-16-online-recal-result.md`; six source pages (ACI, conformal PID, rolling RC, beyond exchangeability, non-exchangeable CRC, covariate shift). Updated: concept `conformal-risk-control.md`, spec 2.3 informative note (no field change), `references/README.md`, `index.md`, tracker (M2-16), `HANDOFF.md`.

## [2026-11-11] query | M2-09 provenance ledger v0
- New module `src/fidetype/trust/provenance.py` (own code): append-only JSON Lines ledger, schema `fidetype.provenance/0.1`, SHA-256 hash chain over canonical JSON; entry kinds genesis / context / decision / correction / note; `verify` detects edit, delete, reorder and (with an external head anchor) truncation.
- Privacy by design: no raw signals (stream SHA-256 + frame range only; numeric-array guard), text `store` / `hash` (HMAC-SHA256 with a key) / `omit`, subject and session ids hashed by default.
- Hooks: `TrustPipeline.attach_ledger`, `evaluate(test, ledger=)`, `run_harness(..., ledger=)`, `LedgeredPolicy`; queries `LedgerView`, `audit_report`, CLI. 25 tests; CPU suite 294 passed, 4 skipped.
- Demo `experiments/2026-11-11-m2-09-provenance/` (B2T '25 replay, plug-in and CRC gates): 1,723 entries verified; wrong commits in the ledger equal the harness (48 / 39); all tamper cases detected; about 0.1 ms per decision.
- Spec: optional `meta` keys `decoder.weights_sha256`, `adapter.name`, `adapter.version`, `stream.id` and informative section 4.3 (non-breaking; v0.1 streams stay valid).
- New: `wiki/concepts/provenance-ledger.md`. Updated: `overview.md`, `index.md`, `project-plan.md`, `architecture.md`, `roadmap-standard.md`, `b2t25-trust-result.md`, `conformal-risk-control.md`, tracker (M2-09), `HANDOFF.md`.

## [2026-11-11] query | Paper 1 outline and results inventory (M3)
- New: `papers/paper1/outline.md` (first file in `papers/`): 4 title options, abstract draft (about 215 words), 6 contributions, section plan with tables T1–T7 and figures F1–F7 (each number copied from a named result page), related-work map (existing source pages + "to add"), 12 candid limitations, ethics and data-licence statement, results inventory R1–R27 with status, gaps G1–G15, reproducibility plan, venues.
- Main gap: all MEG trust numbers come from synchronous decoders; the trust harness must run on the async M1-09 streams (G1). Also: seeds, sentence/participant CIs, KT-sEMG natural typing, unified ablations, eWPM sensitivity.
- New: `wiki/questions/paper1-plan.md`. Updated: `index.md`, tracker (M3-03, M3-06, M3-09), `HANDOFF.md`.

## [2026-11-11] query | M5-10 NeuralTextStream conformance suite
- New package `src/fidetype/conformance/` (own code): readers for NPZ and JSON Lines without validation (dense and sparse frames, Development events), 60 checks (each cites its spec clause; keyword MUST / SHOULD / PROFILE; heuristic flag), cumulative levels core / trust-ready / provenance plus advisory warnings, reference consumer `load_stream`, CLI `python -m fidetype.conformance check|consumer|vectors|list` (JSON report, summary, badge line, shields.io badge object; external consumers via `--cmd`).
- 52 golden vectors (32 NPZ, 20 JSON Lines; all spec cases C1–C20 plus empty, single frame, NaN, unnormalised, unknown keys / events, future minor version, key / phoneme / command vocabularies, provenance keys, sparse frames, events) committed in `spec/conformance/v0.1/` with `manifest.json`. Reference consumer 52 / 52.
- Adapters on synthetic inputs: SpanishBCBL MEG ConvCTC core → **provenance** (new `adapters/spanishbcbl_meg.py`, used by `decoders/infer.py`); B2T '25 **trust-ready** (only `PV-WEIGHTS` fails: no published weights); Toronto sEMG trust-ready → **provenance**.
- Bugs fixed: MEG producer had no 4.2 keys and no `frame_period`; Toronto stream with a latency kept `decoder.causal = false`; `TemperatureScaler.transform_stream` did not set `calibration.applied`; NaN accepted in `meta_json`; adapters now write `adapter.*` (and B2T '25 a `stream.id`).
- Spec v0.1 (informative only): section 7 note on the suite; section 10 item 12 with ambiguities A1–A10; changelog row. 73 new tests; CPU suite 367 passed, 4 skipped.
- New: `wiki/concepts/conformance-suite.md`. Updated: `index.md`, `roadmap-standard.md`, `architecture.md`, `provenance-ledger.md`, B2T '25 and Toronto entity pages, `spec/README.md`, tracker (M5-10; agent runs M2-16, M2-09), `HANDOFF.md`.

## [2026-11-11] query | G1: trust evaluation on the async M1-09 MEG streams
- Experiment `experiments/2026-11-11-g1-async-meg-trust/` (CPU only): the M1-15 full-r1 eWPM harness, a null-input audit, M2-13 CRC / LTT and M2-16 online re-calibration on the async `m1-09-r4b-full-medium` streams; the same script on the sync M1-15 streams reproduces the old numbers exactly (2.714 / 3.229).
- eWPM (test): always commit 2.58, trust 3.20, gaze only 3.155; wrong-commit 0.997 → 0. Trust − gaze +0.05, CI over unique sentences [−0.04, +0.15], participants [−0.07, +0.22], two-way [−0.11, +0.26]: parity, as for sync (3.23; [−0.02, +0.18]). Trial-level CIs had made sync look like a gain ([+0.03, +0.12]).
- Null audit: trust commits 0 % on real, shuffled, zeros, other-sentence, frame-shuffled, uniform input; always commit 100 % (85–100 % fluent). Guard AUROC null vs real 0.92–1.00, but 0.49 for another sentence's real stream.
- CRC / LTT (n_cal 408, 200 splits): old gate 0, CRC 0.0193, LTT 0.0214; sentence- or participant-grouped splits give the same. Online `aci` 0.0188, `aci_window` 0.0078. All degenerate: top-1 right for 2 / 637.
- Updated: `wiki/questions/m1-09-async-full-result.md` (trust section), `m1-15-full-r1-r3-result.md`, `paper1-plan.md`, `papers/paper1/outline.md` (T3 / T5 / T6 / T7 MEG rows async + sync secondary; R6, R7, R19 final; G1 done; G3 partly), `index.md`, tracker (M3-10), `HANDOFF.md`.

## [2026-11-11] query | Paper 1 LaTeX draft v0 (M3-11)
- First full draft of Paper 1 in LaTeX: `papers/paper1/latex/` (main.tex + 12 section files + appendix, refs.bib with 50 entries), compiled with Tectonic 0.17.0 to `papers/paper1/draft-v0.pdf` (23 pages, 0 undefined references or citations, 0 overfull boxes).
- Figures: 3 TikZ diagrams (architecture, trust decision flow, online re-calibration loop) and 8 data figures from `papers/paper1/make_figures.py` (teaser wrong-commit vs eWPM, eWPM per policy, risk-coverage, CRC/LTT over splits, drift trace + bars, null-input audit, MEG CER, ECE). The script reads only committed JSON; the drift trace is recomputed with `fidetype.trust.online_risk` and asserted equal to `online.json`.
- Tables: devices (T1), online methods (T2), decoders (T4), main safety/speed (T3), CRC/LTT (T6), drift (T7), licences, user model, async check. MEG rows use the committed G1 async numbers with sentence-cluster CIs; the sync M1-15 numbers are kept in Appendix B.
- Honest MEG framing: parity with gaze typing (+0.05, CI over sentences [-0.04, +0.15]); the trust layer commits 0 % also on real MEG, so the MEG null audit shows a closed gate, not null detection.
- Missing data marked with red `\todo{}` (G2-G10, G12, G14, F5, appendix D-F) and user decisions (authors, ethics wording, AI statement, venue). 18 bib entries carry `% TODO-verify` (mostly venue names from our own knowledge). No reference was invented.
- New: `papers/paper1/README.md` (toolchain + build), `how-to-read-this-draft.md` (STE guide for the author), `style-notes.md` (lessons from 5-6 published papers), `data/markdown-only-numbers.json`. Updated: `paper1-plan.md`, `index.md`, tracker (M3-11; M5-10 agent run), `HANDOFF.md`.

## [2026-11-11] setup | M5-01..03 open benchmark v0.1
- New package `src/fidetype/benchmark/` (registry, splits, prepare, submission, scoring, harness, leaderboard) and CLI `python -m fidetype.benchmark` (tracks, info, prepare, check, score, leaderboard).
- Fixed splits committed as ids + cluster labels + text SHA-256 (no text): MEG 4026/437/637, B2T cal 812 / test 816, Toronto composed cal 570 / test 551.
- Leaderboard v0.1 in `benchmark/site/` (21 baseline entries, 3 tracks); B2T published-sentence entry scored end to end from 816 NTS files and matches M6-06 exactly (CER 0.0309, WER 0.0431, wrong-commit 0.194). Other entries scored from committed per-trial or aggregate results.
- Findings: B2T CRC on the fixed day-half split 0.062 > alpha 0.05 (drift; M2-13's 0.048 is over random splits); MEG CRC commits 2.2% with 93% of commits wrong; M1-09 MEG streams reach only conformance level core.
- M5-03 licence audit: `LICENSES/DATA.md`; SpanishBCBL loader/adapter carry licence constants and a `spanishbcbl.licence` meta key; no NC code vendored; judgement call on `experiments/2026-11-08-m2-real-keystroke/results/trials.json` (SpanishBCBL typed texts).
- Pages: [open-benchmark](concepts/open-benchmark.md), `benchmark/README.md`, README section, index.


## [2026-11-11] setup | M5-12 trials.json out of the tree; M7-02 outreach drafts
- M5-12: `experiments/2026-11-08-m2-real-keystroke/results/trials.json` (SpanishBCBL per-trial target and typed texts, key labels) removed from the tip with `git rm --cached`; local copy at `~/bci-data/derived/2026-11-08-m2-real-keystroke/trials.json`. `run.py` reads and writes it there (`FIDETYPE_DERIVED` overrides the root). New `.gitignore` rule `experiments/**/results/trials.json`. No other committed file holds per-participant typed text (others hold a few target sentences only). History not rewritten: older commits (from `074c3b0`) still contain the file; noted in `LICENSES/DATA.md`. pytest 388 passed, 4 skipped.
- M7-02: new page [partner targets](questions/partner-targets.md): 15 targets with public organisational channels only, offer, priority 1-3 and timing. No target is "now" (roadmap rule: demo + benchmark before outreach).
- New `papers/outreach/`: `outreach-one-pager.md` (B2T '25 published decoder wrong-commit 0.194 -> 0.044 at -4.3 % eWPM; always-offer caveat +1.6 % / +3.6 %; EMG composed-sentence caveat; MEG parity with gaze) and `templates.md` (4 messages, 141-163 words). The user is the sender; agents sent nothing.
- Tracker: M5-12 done; M7-02 in progress; M7-05 "User sends outreach" externally blocked; agent runs added to M5-01 and M3-13.

## [2026-11-12] setup | M4-03 streaming trust layer
- New `src/fidetype/trust/streaming.py`: `StreamingTrustLayer` consumes NeuralTextStream events per session (frames route with a pluggable `decode_fn`, or hypothesis route), emits provisional and final decisions with provenance, bounded memory, attempt counting, online re-calibration hook (frozen commit_p = floor), optional provenance ledger, `replay()` and a CLI.
- New `src/fidetype/trust/frozen.py`: `FrozenTrustConfig` (fitted trust state as canonical JSON with a content id); `paper1_v4_harness_config()` for the Paper 1 recipe (guard + LTT max).
- `tests/test_trust_streaming.py` (29 tests): final decisions equal the batch path exactly on synthetic streams and the golden vectors. pytest 417 passed / 4 skipped.
- Latency benchmark `experiments/2026-11-12-m4-streaming/` (synthetic, CPU): push(frame) p50 0.008 ms, final decision 0.72 ms (greedy) / 8.1 ms (beam), push(hypothesis) 0.19 ms; 100/100 equal to batch.
- Spec proposal `spec/feps/0001-streaming-trust-events.md` (segment_end, hypothesis evidence fields, trust_decision); no v0.1 change.
- Pages: new [streaming trust layer](concepts/streaming-trust-layer.md), diagram 12; links from provenance-ledger and conformal-risk-control; index; tracker (M4-03 done; follow-ups M4-06..M4-08).


## [2026-11-12] setup | M6-01 LSL input
- New `src/fidetype/adapters/lsl.py` (own code; optional `pylsl`, MIT, extra `[lsl]`; imports without it and raises `LSLUnavailableError` with the install command). `LSLEventSource`: LSL inlet(s) → NTS events (header from `desc/fidetype/nts_header` or channel labels + options; values log_probs / probs / logits; `SignalDecoder` hook for raw EEG/EMG; receiver clock = timestamp + `time_correction()`, one offset per sender host; clamp / drop / error for non-increasing times; gaps mark / segment / abort; watermark merge of a frames and a marker inlet; loss → abort the cut utterance, re-resolve, new header). `LSLTrustRunner`: → `StreamingTrustLayer` → `trust_decision` JSON Lines with an `lsl` provenance record, optional LSL outlet `fidetype.decisions`. `replay_to_lsl`. CLI `python -m fidetype.adapters.lsl run | replay-to-lsl | list`.
- `StreamingTrustLayer.abort_utterance()` added (drop the pending utterance without a decision).
- `tests/test_adapter_lsl.py` (26 tests: 22 with a fake inlet, 4 real localhost loopbacks skipped without pylsl). pytest 443 passed / 4 skipped.
- Loopback benchmark `experiments/2026-11-12-m6-lsl/` (localhost, synthetic): every decision equals the file replay path (frames route 12/12 with float32 and double64, hypothesis route 30/30, two-process CLIs 12/12). Transport p50 3.5 ms, p95 6.6 ms; e2e final p50 60.6 ms with a 50 ms merge window, 17.2 ms with 10 ms, 3.0 ms on the hypothesis route.
- Pages: new [LSL input](concepts/lsl-input.md) (tool connection notes from the OpenBCI, BrainFlow and LSL docs), diagram 13; updated streaming-trust-layer, lab-streaming-layer, brainflow, index. Tracker: M6-01 done; M4-03 agent run filled; follow-ups M6-08..M6-11.

## [2026-11-12] setup | M7-01 Python SDK and offline demo
- Reviewed and kept the partial work of a stopped agent: lazy public API in `src/fidetype/__init__.py`, `api.py` (`open_stream`, `read_stream`, `validate`, `calibrate`, `greedy_decoder`), `writer.py` (`make_stream`, `write_stream`, `StreamWriter`, `stream_meta`), `cli.py` (console script `fidetype`), `conformance.check` + `TargetReport.passes/failures`, `frame_decoder()` (`--decoder demo`, `--max-attempts`), demo package `src/fidetype/demo/` (terminal demo, static page renderer, frozen demo config).
- Added: `examples/` (emit_ctc_stream, hypothesis_stream, streaming_trust, lsl_bridge; all run), `tests/test_sdk.py` (13 tests; pytest 456 passed / 4 skipped), sdist limited to package/tests/examples/spec, README quickstart + CLI table, regenerated `demo/index.html` + `demo/decision-log.json`.
- Checked: `uv build` (needs `UV_LINK_MODE=copy` on OneDrive), clean venv wheel install runs `fidetype demo`, `fidetype validate` and the README quickstart; demo config refit reproduces `tcfg-a34f63a757f55371`; static page has no network references; headless Edge render OK.
- Finding: a frozen config is valid only with its own `decode_fn` (demo config + greedy decoder committed "ello world").
- Pages: new [Python SDK and offline demo](concepts/python-sdk.md); links from streaming-trust-layer and lsl-input; index. Tracker: M7-01 done; M3-26 arXiv endorsement (externally blocked); follow-ups M7-06..M7-09; agent runs of M6-01 and M3-25 filled.

## [2026-11-12] query | M4-06 real-data frozen trust config through the streaming layer
- Fitted the Paper 1 frozen recipe (guard + LTT max) on B2T '25 split A and froze it: `tcfg-f5ca0020b3b8fce2` (ours, commit_p 0.3), `tcfg-ea22af7ec91eea3f` (published gate, 0.76). Config JSON (numbers only) in `experiments/2026-11-13-m4-06-real-replay/configs/`.
- Replayed 816 full-precision NTS test streams through `StreamingTrustLayer` (frames + hypothesis routes): 816/816 decisions equal to batch; test metrics equal Paper 1 Tab. 3 split A; shuffled / uniform controls 0/300; provenance and ledgers verify. Latency: hypothesis p95 0.63 ms; frames route with a fresh decode p95 992 ms (decoder).
- Finding: 6-decimal benchmark files break exact equality (p_top1 within 3.4e-8, no action changed).
- Pages: new section in [streaming trust layer](concepts/streaming-trust-layer.md); index line updated. Tracker: M4-06 done; M7-01 second agent run filled.

## [2026-11-12] setup | M4-07 FEP-0001 conformance and M6-09 FEP-0002 NTS-over-LSL binding
- FEP-0001 (Draft) updated: new part 4 `decode_declaration` (decoder, decoder_version, frame_temperature, params, config_id; M4-06 finding), testable rules (segment_end t not before the last frame; logp_* <= 0; char_confidences in code points; trust_decision rules 5-8 on seq, one final per utterance, nothing after it, COMMIT text), conformance section.
- `StreamingTrustLayer` checks the declaration on the hypothesis route: `StreamingConfig.declaration_check` = `warn` (default; provenance + `trust_decision.declaration`, no decision change) / `abstain` / `off`; `require_declaration`; `expected_decoder`. New module `fidetype.trust.declaration`.
- New FEP-0002 `spec/feps/0002-nts-over-lsl.md` (Draft): stream types and names, desc keys, float32 vs double64, marker events, clock correction, `event_clock`, gaps and loss, decisions stream, binding version `nts-lsl/0.1`. Small adapter fixes to match it (refuse int formats / label order / srate mismatch / unknown binding or event_clock for NTS-native streams; apply `event_clock = lsl`; `replay-to-lsl` writes `binding` + `event_clock`).
- Opt-in conformance profiles `fep-0001` (10 checks, 40 vectors: 12 accept / 28 reject) and `fep-0002` (6 checks, 31 scripted LSL scenarios: 15 accept / 16 reject; no pylsl) in `src/fidetype/conformance/profiles/`, `spec/conformance/fep-000{1,2}/`; CLI `fidetype conformance --profile NAME`. v0.1 vectors unchanged (52/52).
- Tests: `tests/test_fep_profiles.py` (24); pytest 480 passed / 4 skipped.
- Pages: [streaming trust layer](concepts/streaming-trust-layer.md) (declaration check, profile), [LSL input](concepts/lsl-input.md) (FEP-0002 rules, profile), [conformance suite](concepts/conformance-suite.md) (profiles section), index; `spec/README.md` FEP table.

## [2026-11-12] setup | M6-08 BrainFlow Synthetic board -> LSL -> trust layer live test
- New optional extra `[brainflow]` (brainflow 5.24.0, MIT). New `fidetype.adapters.brainflow_bridge` and CLI `fidetype lsl brainflow-bridge --board synthetic`: an `EEG` stream (labels, unit `microvolts`, `role = signal`) and a `Markers` stream (`segment_end` trial clock, `role = signal_markers`). The bridge smooths the bursty BrainFlow stamps and keeps real gaps.
- New toy decoders `fidetype.decoders.toy_signal` (`flat`, `features`). They carry no text information. `fidetype lsl run --signal-decoder toy-flat|toy-features`.
- Live run (`experiments/2026-11-13-m6-08-brainflow-live/`): two processes, demo config + demo decoder, 3-s dropout, hard kill, reconnect, clean stop. 26/26 ABSTAIN, 0 COMMIT. Transport p50 11.5 ms; steady e2e p50 33–38 ms; CPU about 2.3 % of one core per process.
- Finding and fix: liblsl `pull_chunk(timeout > 0)` waits for a full buffer. `PylslInlet.pull_chunk` now pulls with timeout 0 (transport p50 37 → 11.5 ms).
- FEP-0002 role table: informative `signal` / `signal_markers`. Tests: `tests/test_brainflow_bridge.py` (14); pytest 494 passed / 4 skipped.
- Pages: [LSL input](concepts/lsl-input.md) (new section "BrainFlow live test"), [BrainFlow](entities/brainflow.md), index; README CLI table. Tracker: M6-08 done; follow-ups M6-12 (real board, externally blocked), M6-13 (soak test).

## [2026-11-13] query | A2 per-session (per-day) risk control
- New module `fidetype.trust.session_risk`: `min_ltt_items` (45 for α 0.05, δ 0.1), `mondrian_ltt` (fallback never / global / mixture), `block_ltt`, `block_test`, `SessionRiskMonitor` (betting e-process, Ville: false alarm ≤ γ), `first_alarm`, `eb_session_threshold` (empirical Bayes, no finite-sample guarantee). Opt-in `StreamingTrustLayer(session_risk=...)`: alarm → offer-only for the rest of the session; default off.
- Experiment `experiments/2026-11-13-a2-per-session-risk/` (cached Paper 1 item tables, no new decodes): published day 34 (re-splits R = 200) global 0.103; Mondrian feasible for day 76 only (fallback global keeps 0.098); block LTT k = 45 offer-only warm-up 0.034 (0/14 days > α, eWPM −2.2 %), k = 60 0.006; k < 45 never commits; monitor alarm 27 % at median item 71 (false alarms 3.0 %); ACI 0.077; EB † ≥ 0.073. Forward chain V3, our decoder, day 34: 0.200 → monitor alarm at item 15 (0.040); block LTT k = 45 W 0/13 days > α. sEMG: no participant > α; sessions too short for block LTT.
- Tests: `tests/test_trust_session_risk.py` (21); pytest 515 passed / 4 skipped.
- Pages: new [per-session risk control](questions/per-session-risk-control.md); [conformal risk control](concepts/conformal-risk-control.md) (new section), [streaming trust layer](concepts/streaming-trust-layer.md) (new section), [M2-16](questions/m2-16-online-recal-result.md), index.

## [2026-11-13] setup | M4-08 incremental decoding in the streaming trust layer
- Code: `fidetype.lm.IncrementalPrefixBeam` (the CTC prefix beam search with state across chunks; `ctc_prefix_beam_search` now uses it with one chunk), `ctc_forced_align_many` (one Viterbi pass for all n-best texts, same spans), alignment memo + `prewarm()`; `fidetype.trust.incremental` (`IncrementalDecoder`, `IncrementalGreedy`, `IncrementalReferenceDecoder`, `CTCBeamSpec`/`IncrementalCTCBeam`, `BufferedDecoder`, `SegmentTracker`, `stability_metrics`); opt-in `StreamingTrustLayer(incremental=...)`, `StreamingConfig.incremental_chunk_frames`; CLI `replay --incremental`.
- Experiment `experiments/2026-11-13-m4-08-incremental/`: final decisions equal the batch path exactly (B2T 816/816 for ours in 4 variants and the published gate; synthetic 200/200 for greedy, segment beam, CTC beam + LM). B2T end-of-utterance p50/p95/max 175/1010/3242 ms (batch) -> 122/1005/3099 (search only) -> 33/71/595 (full word prewarm; push max 2.2 s, about 4.5x CPU). Preview stability (B2T words): change rate 0.29, 4.4 rewrites per utterance, last preview = final 65 %.
- Tests: `tests/test_trust_incremental.py` (18).
- Pages: [streaming trust layer](concepts/streaming-trust-layer.md) (new section); diagram 14.

## [2026-11-13] query | M3-27 confirmatory test on T12
- Pre-registration `experiments/2026-11-13-confirmatory-t12/PROTOCOL.md` (commit a7cf624), pushed before any decoding.
- Data: Willett et al. 2023 / B2T '24 `competitionData` (CC0), from the Zenodo copy of the Dryad record (Dryad file downloads need a login token); MD5 checked; row in `references/README.md`.
- Own causal GRU-CTC decoder (2 runs; run 1 collapsed at lr 2e-3, run 2 lr 5e-4): validation PER 0.471; test PER 0.542, WER 0.751, right sentence first 3/400.
- Frozen configuration on 400 test trials (10 later sessions): 0 wrong commits, 0 commits; controls 0/400; guard AUROC 0.966. Outcome by the pre-registered rule: **uninformative** (safe; the LTT bound not tested).
- New page [Confirmatory test on T12](questions/confirmatory-t12.md); update note on [B2T '25 trust result](questions/b2t25-trust-result.md); index.

## [2026-11-13] query | M4-09 fast exact lexicon fallback + bounded prewarm
- `PronLexicon.nearest`: exact NumPy Levenshtein per length bucket, about 20x faster; `nearest_bruteforce` kept as the reference. Equal on 5,667/5,667 B2T-decode calls and 9,000/9,000 synthetic calls.
- `CTCBeamSpec(prewarm_budget_s=...)`, `PhonemeWordDecoder.warm`, `IncrementalPrefixBeam.prewarm(deadline=...)`: prewarm in steps under a per-push time budget.
- B2T 816 test utterances: decisions equal M4-06 in every condition (ours and published gate). Batch end p95 676 -> 172 ms (fast `nearest`); budget 1 ms: push p95 3.1 ms, max 30 ms, end p50/p95 52/118 ms, CPU 2.7x search only.
- Push spikes came from Python's gen-2 GC (80-280 ms). Rule: freeze after load, GC off while an utterance streams, collect after its final decision.
- Experiment `experiments/2026-11-13-m4-09-fast-lexicon/`; tests `tests/test_fast_lexicon.py`; page [streaming trust layer](concepts/streaming-trust-layer.md) updated.

## [2026-11-13] query | M4-10 bounded decoder caches (LRU)
- `fidetype.lm.cache.LRUCache`; `PhonemeWordDecoder(cand_cache_size=5000, lm_cache_size=50000)`; `CharNgramLM` memo is now LRU (200,000; before: cleared when full). None = unbounded.
- Decisions equal the unbounded caches: synthetic 2,000-utterance session 2000/2000 (3 bound settings); B2T 816/816 vs M4-06 (unbounded, default, 256).
- Session RSS 640 -> 1,387 MB unbounded (candidate memo about 17 KB per entry) vs 641 -> 707 MB with default bounds; idle GC p50 208 -> 43 ms; push p95 2.32 ms (B2T 3.19 ms).
- Experiment `experiments/2026-11-13-m4-10-bounded-caches/`; tests `tests/test_bounded_caches.py`; page [streaming trust layer](concepts/streaming-trust-layer.md) updated.

## [2026-11-13] query | M3-28 confirmatory test v2 on T12 (stronger decoder)
- Pre-registration `experiments/2026-11-13-confirmatory-t12-v2/preregistration.md`, commit `f9741df`, pushed before any trust-pool decoding; states the v1 exposure and an informative condition (>= 21 of 400 test commits).
- Own decoder v2 (causal rolling 20-trial normalisation, GRU 5 x 1024, patch 32; Tatoeba word-trigram term beta 2.0): validation PER 0.293, test PER 0.269, WER 0.387, right sentence first 31/400 (v1: 3/400).
- Frozen configuration: 1/400 test commits (right), 0/400 controls, guard AUROC 0.792 -> outcome **uninformative** again; C1-C3 pass.
- Validation dry run before the pre-registration: the same recipe chose `commit_max_risk` 1.0 there and committed 335/400 uniform-control streams (320 empty texts). The predicted C3 failure did not occur on the trust pool (recipe chose 0.1).
- Page [confirmatory test on T12](questions/confirmatory-t12.md) updated (v2 section); index line updated.

## [2026-11-13] query | M2-18 empty commits on no-signal input: mechanism, Paper 1 impact, commit gate
- Mechanism: the guard gives an empty top-1 risk 1.0 (not 0, as M3-28 guessed). The grid value `commit_max_risk` 1.0 makes `risk <= commit_max_risk` always true, so the guard limit is off; the T12 word decoder returns only "" on most uniform streams, p_top1 ~1. Trust pool: only the fitted limit 0.1 blocked 304 empty top-1 texts (same inputs at 1.0: 321 commits).
- Synthetic reproducer `experiments/2026-11-13-m2-18-empty-commits/repro.py`; tests `tests/test_trust_commit_gate.py` (12).
- Paper 1 (T15): 6 refits reproduce Tab. 1 exactly; 0 empty / one-word commits on test and controls; all Paper 1 fits chose `commit_max_risk` <= 0.5; repeated splits chose 1.0 in 53/200 (ours) and 65/200 (published) but 0 empty top-1 in 35,816 cached T15 n-best lists. No number changes; wording erratum candidate only.
- Opt-in fix: `fidetype.trust.content.CommitGate` / `GatedPolicy`, `FrozenTrustConfig.commit_gate` (empty = off, ids unchanged), applied by `StreamingTrustLayer`. T12 dry run uniform commits 335 -> gate A 15 -> gate B 0, frame-shuffled 6 -> 3, test unchanged. FEP-0001 rule 9 (SHOULD NOT emit an empty final COMMIT) + open question 6.
- Stability finding and v5 suggestion (gate B default, drop 1.0 from the grid or a control-aware grid fit, bootstrap selection report) noted; not applied. Pages [streaming trust layer](concepts/streaming-trust-layer.md) and [confirmatory test on T12](questions/confirmatory-t12.md) updated; index updated.

## [2026-11-13] setup | Publications decoupled from the research roadmap (PUB track, no deadline)
- User decision: paper writing and publishing are a separate track. Review and publishing run on outside timelines (the user expects 50 to 60 times longer than planned). The research and engineering roadmap never waits on a paper.
- Tracker: new milestone `PUB` "Publications (no deadline)" (`no_deadline: true`, no target dates). Moved, ids and history kept: M3-03..M3-09, M3-11..M3-13, M3-15, M3-16, M3-18, M3-19, M3-21..M3-26, M4-04, M4-05, P11-04, P11-05. M3 renamed "Trust-layer validation (research)", M4 "Causal / streaming decoder (research)". `target_note` records the decision.
- `tools/progress/build.js`: a milestone with `no_deadline` (or no `target_end`) gets a "No deadline" badge, is never late and has no target bar on the timeline.
- Policy written into [project plan](questions/project-plan.md#pub-publications-no-deadline), [long-term roadmap](questions/roadmap-standard.md#publications-no-deadline), [overview](overview.md), [Paper 1 plan](questions/paper1-plan.md) and [open-source playbook](questions/open-source-playbook.md): results go to `experiments/` and the wiki first; papers draw on them later. No paper is an exit criterion of a phase. HANDOFF has a "Publications (no deadline)" section.
- Not changed: diagrams 09-milestones and 11-roadmap-standard still show the papers inside M3/M4 and P11.

## [2026-11-13] setup | CPU isolation for latency runs + tracker fragments (M0-22)
- New `src/fidetype/utils/isolation.py`: CPU classes `timing` (4 reserved physical cores, SMT siblings idle, above normal, one job at a time by file lock under `bci-data/runs/cpu-isolation/`) and `background` (other cores, below normal). CLI `python -m fidetype.utils.isolation run|show`, context manager `isolated()` with a `measurement_env` record (affinity, priority, load, CPU model, `clean`). Tests `tests/test_isolation.py`.
- Check `experiments/2026-11-13-cpu-isolation/results.md`: p95 0.645 ms (timing alone), 0.661 ms (timing + background load), 1.126 ms (no isolation, same load).
- [Compute setup](questions/compute-setup.md): new section "CPU isolation for latency measurements" with usage and limits.
- Tracker fragments: agents write `wiki/progress/fragments/<task-id>.json`; `node tools/progress/build.js` merges them (`tools/progress/fragments.js`, self-check `tools/progress/test-fragments.js`, rules in `tools/progress/README.md`).

## [2026-11-13] setup | Paper 1 v6: pre-submission text revision (PUB-01)
- No new experiment; no number changed; abstract, title, frozen configuration and tags unchanged. No `paper1-v6` tag: earlier text versions had no tags (the `paper1-vN-frozen-config` tags mark configurations).
- Guard wording made precise (from M2-18): Sec. 4.1, Sec. 6.6 ("our guard is one such check"), Discussion ("The guard stopped this"), Limitation 3 and the Figure S1 caption now say the guard acted in the reported fits; the grid value `commit_max_risk` 1.0 switches its limit off (53/200 and 65/200 re-splits; 0 empty top-1 in 35,816 cached T15 n-best lists). Opt-in commit gate named as future work. New Supplementary Section S23.
- Limitation 1 and new Section S24 (Table S21): two pre-registered T12 tests (commits `a7cf624`, `f9741df`) uninformative, 0/400 and 1/400 commits, no wrong commits, controls passed; the bound still rests on one participant. T12 row added to the licence table.
- Builds (TinyTeX pdflatex): main 23 pages, supplement 18, arXiv document 38 (main part 23 + supplement 15); 0 undefined references, 0 overfull lines, clean rebuild from the zip. `fidetype-paper1-arxiv.pdf` was locked by a viewer, so the v6 build is `fidetype-paper1-arxiv-v6.pdf`.
- Updated: `papers/paper1/final/SUBMIT.md` (version note, comments field), `papers/paper1/how-to-read-this-draft.md` ("What changed in v6"), `papers/paper1/README.md`, [Paper 1 plan](questions/paper1-plan.md), [confirmatory test on T12](questions/confirmatory-t12.md).

## [2026-11-13] query | P12-01 / P12-02: output profiles and discrete intent events (FEP-0003)
- New [FEP-0003](../spec/feps/0003-intent-events.md): output-agnostic core + profiles (text unchanged, intent, control later); header `intent_declaration` (risk class safe / undoable / irreversible, roles null / confirm / cancel / undo); `intent` and `intent_feedback` events; intent `trust_decision` (`profile`, `unit`, `intent`, `offered`, `risk_class`, `confirm_required`, `confirmation_of`, `undo_of`; never `shown`); safety rules (no null COMMIT, no COMMIT without probabilities, per-class calibrated thresholds, irreversible = arm + explicit confirmation, undo never on irreversible, no COMMIT on no-signal input, audit fields); coexistence with text and LSL (shared `seq`, no binding change).
- Code: `fidetype.trust.intent` (config `icfg-`, per-class LTT/CRC fit through `risk_control`, data-free 0.5 floor, optional no-signal reference, `IntentTrustLayer`, CLI `fidetype intent replay`), `fidetype.trust.intent_sim` (synthetic), `StreamingTrustLayer(intent=...)`; profile `fep-0003` (44 vectors), JSON schemas `spec/schemas/fep-0003/`; tests `tests/test_intent_trust.py`.
- Evaluation [experiment](../experiments/2026-11-13-p12-intent-events/results.md): Toronto sEMG (CC BY 4.0) recast as 27-way key choice + simulator. Clean wrong rates <= alpha in every setting; zero-input output acts on 37 % of presses without a no-signal reference, 0 with it (the M2-18 failure in intent form).
- New page [intent events](concepts/intent-events.md), diagram 15, roadmap P12 progress note, index rows.

## [2026-11-13] query | P12-06: public datasets for intent and control
- New [intent and control datasets](questions/intent-datasets-survey.md): about 45 datasets (implant, ECoG, EEG, EMG) with modality, task, participants, size, exact licence (read on the host page or API, no downloads) and fit scores for the FEP-0003 intent and control profiles.
- Control (P12-03) top 3: BrainGate long-term recalibration (CC0, 1.69 GB), NLB MC_RTT (CC BY, 51 MB), BNCI 002-2025 EEG 2D trajectory (CC BY). Intent top 3: PhysioNet EEGMMIDB (ODC-By, 3.4 GB, has rest), BrainGate preparatory encoding (CC0, 1.54 GB), BNCI 001-2025 (CC BY). Both profiles, over 5 GB: BrainGate drag-and-drop (CC0, 8.2 GB).
- Licence findings: BCI Competition III/IV (bbci.de), Ninapro, Tsinghua SSVEP, OpenBMI, CSL-HDEMG have no licence; Meta wrist-EMG sets are NC; emg2qwerty README (CC BY-NC 4.0) and LICENSE file (CC BY-NC-SA 4.0) disagree (contradiction note added).
- `references/README.md`: new link-only table; [intent events](concepts/intent-events.md) links the survey.

## [2026-11-13] setup | M7-06: TypeScript SDK
- New `sdk/typescript/` (`@fidetype/sdk`, private, Apache-2.0): NTS writer and readers (text, live byte streams), reference consumer for JSON Lines and NPZ (own ZIP / DEFLATE / NPY reader), the 60 v0.1 checks, a streaming validator, `DecisionTracker` for `trust_decision` (FEP-0001 rules 1, 3, 5-8; rule 9 warning), conformance runner and CLI `fidetype-ts`. Node >= 18 and browser ESM; zero runtime dependencies; dev: typescript 5.9.3 (Apache-2.0), @types/node 18.19.130 (MIT).
- New structural schemas `spec/schemas/nts-v0.1/` (7) and `spec/schemas/fep-0001/` (4). Generated TS types + embedded schemas; `npm run check:schemas` fails on drift; a test validates every event of every accepted vector.
- Parity: same verdict as the Python reference on all vectors (v0.1 52, fep-0001 40, fep-0002 31, fep-0003 44) (`npm run cross-check`) and on ~8,000 fuzz mutants (`npm run fuzz`); the first fuzz runs found and fixed 6 differences. FEP-0002 decision counts come from a structural model of the trust layer. Headless Edge: 167/167.
- CI: jobs `typescript` (Node 18 and 24) and `typescript-parity` added to `.github/workflows/tests.yml`. New page [TypeScript SDK](concepts/typescript-sdk.md); links from [Python SDK](concepts/python-sdk.md) and [conformance suite](concepts/conformance-suite.md).

## [2026-11-13] setup | M4-11 flaky budgeted-prewarm test; diagram 14/15 screenshot check
- `tests/test_fast_lexicon.py::test_budgeted_prewarm_equals_batch[1e-05]` was flaky because of the test, not the decoder. Its `assert seen` needed an on_prewarm step to run inside a 10 us budget; `beam.push` alone usually uses that budget, so under load no step ran. Decisions do not depend on the budget: the prewarm only fills pure memos that finalize recomputes when missing.
- Fix: injectable clock (`CTCBeamSpec.clock`, `IncrementalPrefixBeam.prewarm(clock=...)`, default `time.perf_counter`). The real-clock test asserts results only. New deterministic fake-clock tests make the budget run out at adversarial points (random, bursty, always expired, frozen; a cut after 0..11 alignments) and check equality with the batch decode plus coverage. 50/50 runs under background CPU load; full suite 650 passed / 9 skipped.
- Diagrams 14 and 15 were not broken. A headless test page without `<meta charset="utf-8">` made Edge decode `viewer-static.min.js` in a legacy charset, which gives a regex SyntaxError, so nothing rendered. `--virtual-time-budget=10000` and a larger window did not change that. With the charset (as in the built `index.html`) both render. Diagram 15 got two layout fixes ("p >= thr" label, confirmed-COMMIT arrow around the undo box).

## [2026-11-13] query | M3-01 / M3-02: trust-core ablations, MEG and simulator end to end
- Plan committed before any run (`experiments/2026-11-14-m3-01-02-ablations/plan.md`). 15 arms against the frozen v4 baseline: risk rule (plug-in, CRC, LTT pure), guard, calibration, alone-arms, conformal, commit gate B, session monitor, declaration check, always / never commit.
- B2T '25 (fixed splits A/B, 200 re-splits), Toronto sEMG (3 conditions), SpanishBCBL MEG (5 provenance runs, aggregated only), simulator (median/worst × distortion 0.5/1/2). v4 reproduces Paper 1 exactly.
- Findings: no module is enough alone. LTT holds the re-split exceedance (plug-in 31 %, CRC 19 %, v4 7.5 %). The max combine matters on sEMG. The guard holds the controls (198/300 uniform commits without it). Calibration stops a weak decoder from committing (MEG without it: 20 of 21 commits wrong, yet below α). A raw-decoding producer pushes B2T wrong commits above α; declaration "abstain" costs all offers (eWPM 3.55).
- M3-01: MEG gives 0 commits in all 5 runs (top-1 correct ≤ 5/637). Simulator: streaming = batch 1,800/1,800, v4 wrong-commit ≤ 0.047; frame-shuffled simulator streams pass the guard (1-16 %, new limit).
- New page [trust-core ablations](questions/trust-core-ablations.md); links from [trust core v0 results](questions/trust-core-v0-results.md), [per-session risk control](questions/per-session-risk-control.md), [confirmatory T12](questions/confirmatory-t12.md).


## [2026-11-13] setup | M7-07: Rust SDK
- Toolchain: no Rust on the dev PC and no MSVC build tools. rustup installed for the current user only (`~/.cargo`, `~/.rustup`, PATH not changed), profile minimal, `stable-x86_64-pc-windows-gnu` (rustc 1.100.0), plus target `thumbv7em-none-eabihf` and clippy.
- New `sdk/rust/` (crate `fidetype`, `publish = false`, Apache-2.0): `no_std` + `alloc` core with feature `std` (file I/O, CLI `fidetype-rs`, example `validate_replay`). NTS writer (JSONL) and NPZ writer, readers (whole text, chunked bytes), reference consumer for JSON Lines and NPZ (own ZIP / DEFLATE / NPY), the 59 v0.1 checks, `StreamValidator`, `DecisionTracker` (FEP-0001 rules 1, 3, 5-8; rule 9 warning), FEP-0001/0002/0003 profiles, conformance runner. Own JSON parser with Python semantics (`1.0` is a float). One dependency: `libm` 0.2.15 (MIT), pinned in `Cargo.lock`.
- Parity: same verdict and "ok" as Python on all 167 vectors (52/40/31/44); Python verdict on 16,141 fuzz mutants (seeds 1-4, `--n 30`). The TS scripts `cross-check.mjs` / `fuzz-parity.mjs` got `--rust BIN` (three-way comparison). The Python suite also passes the Rust CLI as external consumer (167/167). The fuzz found 2 Python behaviours to copy (late iteration of string LSL samples; the reference greedy decoder fails when `blank_id` is null, a likely reference bug) and 3 TypeScript gaps (open items).
- Tests: 9 unit, 15 integration (incl. all vectors), 3 doc tests. CI: jobs `rust` (tests, no_std Cortex-M build, CLI conformance) and `rust-parity` added to `.github/workflows/tests.yml`.
- New page [Rust SDK](concepts/rust-sdk.md); links from [TypeScript SDK](concepts/typescript-sdk.md), [Python SDK](concepts/python-sdk.md), [conformance suite](concepts/conformance-suite.md). Check count corrected to 59 (was "60") in the TS pages: Python `REGISTRY` and the TS registry both have 59.

## [2026-11-13] setup | M7-11: SDK parity fixes (blank_id null, TS fuzz mismatches)
- `blank_id` null means "no blank class" (spec 3.1). The reference greedy decoder raised IndexError on the FEP-0002 frames route (a Python bug). Fixed in `trust/_ctc.py`: every frame is a token frame; runs of equal argmax collapse into one token.
- Spec text: v0.1 section 3.1 (`blank_id` row, changelog) and FEP-0002 section 10 (MUST NOT reject). New golden vector fep-0002 L32.
- Rust SDK: the copied rejection is gone. TypeScript SDK: 4 fuzz gaps fixed (string samples, `consumer_settings`, the no-blank case, gap length of an infinite timestamp).
- Parity: Python = TypeScript = Rust on 168/168 vectors and 24,396/24,396 mutants (seeds 1-6, `--n 30`). CI fuzz raised to `--n 30` at seeds 1-3. Pages: [rust-sdk](concepts/rust-sdk.md), [typescript-sdk](concepts/typescript-sdk.md).

## [2026-11-13] setup | M6-11: WebSocket input and output adapter (FEP-0004 draft)
- New `fidetype.adapters.ws` (LSL runner pattern): `/nts` input → streaming trust layer → `/decisions` (resumable, `ws_seq`) and `/events` tap. CLI `fidetype ws run|replay-to-ws|subscribe`; `run --serve-example` serves the browser page. Optional extra `[ws]` = `websockets==17.4` (BSD-3-Clause); the core and the sans-IO parts import without it. `dev` includes `[ws]`, so CI runs the integration tests; without the library they skip.
- Draft [FEP-0004](../spec/feps/0004-nts-over-websocket.md) (binding `nts-ws/0.1`, subprotocol `nts-ws.0.1`): framing and batches, handshake, `ws_seq` duplicates / reorder window / gaps, acks and back-pressure, resume and take-over, close codes, auth hook (Bearer or `ws_auth`), TLS, clock rules (time fields unchanged, as FEP-0002 `event_clock = source`). Spec 6.3 and `spec/README.md` point to it.
- Profile `fep-0004`: 37 scenario vectors (20 accept, 17 reject). Python and TypeScript (`sdk/typescript/src/profiles/fep0004.ts`, `src/ws.ts`) pass 37/37 with the same verdict; 5,550 fuzz mutants agree (seeds 1-5, `--n 30`). Rust has no port yet: `cross-check.mjs` / `fuzz-parity.mjs` now skip a profile the Rust CLI does not know (and print it). Fuzz found one TS gap (a boolean `frame_period` / `latency`, accepted by Python): fixed in the TS structural model.
- Safety finding while writing the vectors: after a gap, the tail frames of the cut utterance formed a new partial utterance and got a decision. FEP-0004 section 6 rule 5 + the runner now drop frames until the next boundary. The B2T run found a producer bug (a later header in one stream was refused): fixed + test.
- Equality: simulator streams over WS (single, batch 8, two broken connections resumed) = file replay, exact. B2T '25 816 test trials (hypothesis route, 14 day streams, 4 producers) = in-process replay 816/816 exact and = batch harness 816/816.
- Latency (localhost, timing class, the M6-01 streams): transport p50 0.22-0.30 ms; e2e final p50 1.30-1.85 ms (LSL M6-01: 56-61 ms with a 50 ms merge window, 17 ms with 10 ms). Results: `experiments/2026-11-13-m6-11-ws/results/`.
- Browser example `examples/ws-browser/index.html` (TS `DecisionSubscriber`), checked live in headless Edge. New page [WebSocket input and output](concepts/websocket-input.md), diagram 16; links from [LSL input](concepts/lsl-input.md), [TypeScript SDK](concepts/typescript-sdk.md), [conformance suite](concepts/conformance-suite.md), [index](index.md).

## [2026-11-13] setup | M7-12: Rust SDK fep-0004 profile (WebSocket scenarios)
- New module `sdk/rust/src/ws.rs`: `IngestCore` (handshake, header, `ws_seq` duplicates, reorder hold 16 events / 0.25 s, gaps, batches, acks, resume, take-over, close codes) and `SubscriberCore` (`/decisions` checks). Sans-IO, `no_std` + `alloc`, no new dependency. Profile `sdk/rust/src/profiles/fep0004.rs` with the runner that drops the cut utterance's frames up to the next boundary.
- Reuses the FEP-0002 structural trust model. One more Python rule copied there: a boolean `frame_period` / `latency` passes as 1 / 0.
- Parity: Python = TypeScript = Rust on 205/205 vectors (fep-0004 37/37) and 31,056/31,056 fuzz mutants (seeds 1-6, `--n 30`; fep-0004 6,660). The parity scripts keep the general skip path for unknown Rust profiles. Pages: [rust-sdk](concepts/rust-sdk.md), [websocket-input](concepts/websocket-input.md).

## [2026-11-13] query | M6-13 soak test of the live path
- Plan with 10 pass criteria committed before the run (`experiments/2026-11-13-m6-13-soak/plan.md`, commit 5b363a5). Harness: `soak.py` (supervisor, detached), `trust_proc.py`, `consumer_proc.py`, `analyze.py`, `offline_memory.py`; metrics every 2 min, fsynced.
- Main run 6.78 h (stopped from outside at 20:47, cause unknown), 6,067 decisions: 0 COMMIT on toy input, 0 invalid, 0 lost, 14/14 gaps, 26/26 reconnects, push p95 worst window 1.76 ms. FAIL: memory (+16.9 MB/h), clock (3 windows at 1,373 ms transport), C1 (outside kill).
- Bug 1 fixed: the guard used the shared 200,000-entry `cached_edit_distance`; now `guard_edit_distance` (4,096). Test `tests/test_guard_cache_bound.py` (3).
- Bug 2 fixed: Windows stepped the wall clock by -1,361 ms; the BrainFlow bridge kept one wall-to-LSL offset, so stamps stayed 1.36 s late. The offset is now measured at each read (`clock_steps`). Tests in `tests/test_brainflow_bridge.py` (+3).
- Post-fix run 2.5 h, 2,242 decisions: 10/10 criteria pass (private +0.80 MB/h, push p95 worst 0.75 ms).
- Pages: [LSL input](concepts/lsl-input.md) (new section), [BrainFlow](entities/brainflow.md), [streaming trust layer](concepts/streaming-trust-layer.md) (guard memo), index.

## [2026-11-14] setup | P12-03: control profile (FEP-0005 draft), control trust layer, MC_RTT evaluation
- Data: NLB MC_RTT (DANDI 000129, CC-BY-4.0) downloaded outside the repo; 20 ms bins by `convert_mc_rtt.py` (h5py in a throw-away uv env). BrainGate recalibration (Dryad, CC0 re-checked): download blocked by a Dryad token (HTTP 401); not bypassed. Rows in `references/README.md`; pages [NLB MC_RTT](sources/nlb-mc-rtt.md), [BrainGate recalibration](entities/braingate-recalibration-dataset.md).
- Draft [FEP-0005](../spec/feps/0005-control-events.md): `control_declaration` (units, frame, rate, uncertainty, latency, click intent), `control`, `control_enable`, control `trust_decision` (state, velocity, gain, radius, v_max, ttl_s, engagement, audit); safety rules (no motion on no-signal, bounded velocity, dead-man and latched stop, re-engage + hand-off ramp, no intent COMMIT while stopped, audit).
- Code: `fidetype.trust.control` (conformal shrinkage gain, no-signal gates, clamps, dead-man poll, click via the FEP-0003 layer), `fidetype.decoders.velocity` (causal Wiener filter + residual scale, numpy), `fidetype.trust.control_sim`; CLI `fidetype control replay`; profile `fep-0005` (42 vectors), schemas `spec/schemas/fep-0005/` (TS generated types refreshed); tests `tests/test_control_trust.py`.
- Evaluation (plan committed first): R² 0.478; coverage 0.905 at 0.90 (5/5 rotations in range); all 6 criteria pass, but the level-0.90 layer never moves (radius 88.6 > decoded speed 45.8 mm/s). Zero-input drift 13.3 mm/s; the decoder's sigma is lower on zero input; gates take it to 0. Post-hoc sweep: level 0.5 -> motion 58 %, over-speed 0.17.
- New page [control events](concepts/control-events.md), diagram 17; links from [intent events](concepts/intent-events.md), [conformance suite](concepts/conformance-suite.md), [survey](questions/intent-datasets-survey.md), [Dryad datasets](entities/dryad-intracortical-datasets.md), index.

## [2026-11-14] setup | M6-14 non-blocking LSL reconnect
- `fidetype.adapters.lsl`: a loss starts a worker thread (`_Reconnector`) that resolves and opens the new inlet and pre-warms `time_correction()`; `poll()` waits at most its timeout. New `LSLMapping.reconnect_mode` (`thread` default, `inline` = old path; the `fep-0002` profile uses `inline`) and `reconnect_handoff_s`. Rules unchanged (abort on loss, status + header order, timeout raises).
- Demo decoder: `RefCharLM` memo bounded with the M4-10 `LRUCache` (32,768 entries).
- Measurement (background CPU class): max loop step during a real LSL producer restart 5,556-5,607 ms before, 41.7-47.9 ms after (1 of 6 runs 141.8 ms); fake 6 s resolve 6,003 -> 66.4 ms. Reconnect time unchanged (about 6.3 s: stale info + 5 s open timeout; follow-up).
- Tests: `tests/test_lsl_reconnect.py` (11). Pages: [LSL input](concepts/lsl-input.md); results in `experiments/2026-11-14-m6-14-nonblocking-reconnect/results.md`.

## [2026-11-14] setup | M0-24: parallel experiment runner (pmap)
- New `fidetype.utils.parallel.pmap`: spawn process pool in the background CPU class, 1 thread per worker, per-item seeds (`SeedSequence([seed, i])`), results in input order, worker count = free background slots (job registry, new `slots` field) capped by free RAM, `--workers` and `FIDETYPE_WORKERS`; initializer for shared read-only data, `save_shared` / `load_shared` (memory-mapped `.npy`), per-chunk checkpoints with resume, serial fallback. Tests `tests/test_parallel.py` (11).
- Used in M2-18 `t15_eval.py` (6 Paper 1 fits), R4 `split-tables/run.py --stage b2t --workers N` (repeated-split tables) and M4-06 `run.py uncached --workers N` (816-trial replay, one session per task).
- Equality: T15 `t15.json` = serial = committed (wall times ignored), `t15.md` byte-equal; split tables 16/16 byte-equal to serial; full R = 200 rebuild 699/700 byte-equal to the R4 cache (1 differs only in the `new_decodes` counter); M3-02 repeated-split rows equal to the committed `splits.json`; replay 816/816 decisions equal (except `latency_s`).
- Speed-ups under load (3-5 other jobs, 4-7 GB free RAM, 2-4 workers): 2.1x (T15), 2.9x / about 3.4x (split tables), 1.9x (replay). RAM per worker (0.9-1.3 GB B2T context) is the limit. Pages: [compute-setup](questions/compute-setup.md) (new section), index. Results: `experiments/2026-11-14-m0-24-parallel/results.md`.

## [2026-11-14] query | P5-07: trust v5 candidate recipe (pre-declared evaluation)
- Plan committed before any run (`experiments/2026-11-14-trust-v5-candidate/plan.md`, `6283109`). New recipe record `TRUST_V5_CANDIDATE` in `fidetype.trust.recipe_v5` (`V5Options`, `V5Pipeline`, `fit_trust_v5`, `freeze_v5`); `PAPER1_V4_RECIPE` and all v4 config ids unchanged. New streaming mode `declaration_check="offer-only"` (FEP-0001 reference note updated).
- Switches: (a) gate B, (b) control-aware grid fit (≤ 1 % commits on uniform / frame-shuffled / zero stand-in copies of the grid-fit streams), (c) 0.8 for 1.0, (d) no-signal floor, (e) offer-only. 10 arms on B2T (4 fixed splits, 2 x 50 re-splits, 2 x 10 fit sets of 240), sEMG (3 + 3 x 50), T12 dry run + pool (exploratory), MEG (5 runs), simulator (6).
- v5 = v4 on all Paper 1 splits; never worse on 250 re-splits (52 fewer-wrong, from the gate). T12 dry run: uniform 335 → 0, empty commits 655 → 0. Simulator frame-shuffled 40 → 3 of 600. Offer-only: 0 commits on mismatched hypotheses at B2T eWPM 11.34 (abstain 3.55). (c) raises wrong commits (sEMG calib 2/21 → 13/74): dropped. (d) redundant with (a).
- Criteria: S1, S2, S4 pass; S3 fails on 1 of 65 control sets (simulator 2/100 frame-shuffled). Recommendation: v5 as opt-in recipe now; default switch after a stricter fit-time limit is re-tested.
- Pages: [streaming trust layer](concepts/streaming-trust-layer.md) (new v5 section), [trust-core ablations](questions/trust-core-ablations.md) (follow-up section), index.

## [2026-11-14] setup | P1: NTS 1.0 Release Candidate 1 (DRAFT for public comment)
- New `spec/nts-1.0-rc1.md`: v0.1 + FEP-0001 … FEP-0005 in one document, with rule ids. Sections: data model, header, events, timing and clocks, trust decisions, profiles (text; intent and control stay Development), bindings (JSON Lines, NPZ read only, LSL `nts-lsl/0.1`, WebSocket `nts-ws/0.1`), conformance classes and levels, security and privacy, versioning (semver, compatibility promise, FEP lifecycle, SDK matrix), registries. Appendices: open questions (resolved or deferred to 1.1), migration from 0.1, traceability (rule → checks / vectors, gaps G-1 … G-11). Marked DRAFT, not final.
- Stricter: TD-9 (no blank final text COMMIT) is a MUST NOT for decisions with the new field `trust_decision.spec_version` 1.x; 0.1 decisions keep SHOULD NOT. Validators in Python, TypeScript and Rust; schemas; vectors F41-F47 (`fep-0001` 47). INT-S7 (no-signal reference for irreversible configurations) is a MUST on paper (gap G-5).
- Parity fuzz (seed 5) found a WebSocket header with a non-object `meta`: Python failed in the trust layer, the SDKs accepted. All three now refuse it (close 1007); vector W38 (`fep-0004` 38).
- `spec/CHANGELOG.md` (new), `spec/README.md`, [NTS specification](concepts/nts-spec.md) (new), [conformance suite](concepts/conformance-suite.md), [roadmap P1](questions/roadmap-standard.md#p1-spec-to-10), SDK pages, index. Tracker: P1-03 done, P1-01 and P1-05 in progress; M6-14, M0-24, P5-07 agent runs filled.

## [2026-11-14] query | P8-06: documentation site plan
- New [docs site plan](questions/docs-site-plan.md): structure of the Python docs, ISO C / cppreference and the OpenTelemetry spec + docs site compared (structure only; no text, design or branding copied; Brain2Qwerty page not copied either).
- Proposal: 10 top-level sections, page tree with a source map (exists / adapt / new), per-clause spec pages with rule-id anchors (`#TD-9`), status badges, one URL per spec version, rule-level diffs; tool Sphinx + MyST-Parser + own theme, TypeDoc and rustdoc linked in.
- Phases A-E (20 tasks, S/M/L). User decisions: D1 GitHub Pages on, D2 domain, D3 design sign-off, D4 spec licence on the site, D5 public progress page. Nothing built.
- Links: [roadmap P8](questions/roadmap-standard.md#p8-docs-website-demo), index. Tracker: P8-06 done.

## [2026-11-14] setup | P3: collector v0 (FEP-0006 draft)
- New draft [FEP-0006](../spec/feps/0006-collector.md): the collector as a reference architecture (receivers → processors → exporters, pipelines, one configuration, health and metrics), modelled on the OpenTelemetry Collector idea in our own words. Loss rule: every loss path ends in a `gap` / `lost` status and never gives a final decision on a cut segment (GEN-8, LSL-G2, WS-Q5). Privacy: `redact` (SEC-7), no host names or tokens in output, secrets only from environment variables.
- New `src/fidetype/collector/` (v0): receivers `file` (JSON Lines, tail mode) and `websocket` (wraps `fidetype.adapters.ws`); processors `validate` (conformance checks), `trust` (streaming trust layer + loss rules, optional ledger), `redact`, `thin`; exporters `jsonl`, `stdout`, `websocket` `/decisions`. TOML / JSON configuration (PyYAML is not a dependency). CLI `fidetype collector --config <file> [--check]`. Example `examples/collector/collector.toml` (toy trust config, synthetic vector).
- Tests `tests/test_collector.py` (29): file → trust → jsonl equals the reference replay; redaction removes all text; five loss paths give no final decision on the cut utterance; WebSocket in / `/decisions` out; config errors.
- Not in v0: LSL, gRPC, OS input exporters, calibration / LM processors, latency budget, YAML. Pages: [collector](concepts/collector.md) (new), [roadmap P3](questions/roadmap-standard.md#p3-collector-pipeline), [NTS specification](concepts/nts-spec.md), index. Tracker: P3-01, P3-02, P3-03 in progress.

## [2026-11-14] setup | P1-08: NTS 1.0 RC2 (gaps G-2, G-3, G-4 closed)
- New `spec/nts-1.0-rc2.md` (RC2 DRAFT): a copy of RC1 with no rule text changed. Section 1.1 lists the RC2 changes; 9.3 / 9.5 vector counts; 11.7 matrix (all three SDKs read 1.0 headers); B.3 status; C.1 rows HDR-2, VER-1, VER-3, VER-5, LSL-D2, GEN-5, TD-F2; C.2 G-2 / G-3 / G-4 closed. `spec/nts-1.0-rc1.md` unchanged.
- Code (G-2): one function per SDK accepts header `spec_version` `"0.1"`, `"1.0"`, `"1.<minor>"` and refuses the rest (`"2.0"`, `"1.0.0"`, `"01.0"`, `"1.01"`, numbers): Python `fidetype.streams.spec.is_supported_spec_version`, TS `isSupportedSpecVersion`, Rust `fidetype::constants::is_supported_spec_version`. Used by `NTS-VERSION`, `NeuralTextStream`, the streaming validators, LSL `FEP2-DESC`, WebSocket `FEP4-HANDSHAKE` and TD-F3. JSON schema `nts-v0.1/header`: pattern instead of `const "0.1"`; TS types regenerated. Writers still write `"0.1"`.
- Vectors (21 new): V53-V61, F48-F54, L33-L35, W39-W43. Counts: v0.1 61, fep-0001 54, fep-0002 35, fep-0003 44, fep-0004 43. G-3 (`blank_id: 0.0`, `seq: 1.0`, `ws_seq: 2.0`) and G-4 (TD-F2 types) needed no check change: all three SDKs already refused them. JSON Schema counts `1.0` as an integer, so GEN-5 is checked only by the validators.
- Parity: Python = TS = Rust on 237/237 vectors (`cross-check.mjs --rust`); fuzz seeds 1-6 `--n 30`: 36,636 mutants, identical verdicts. pytest 757 passed; TS 31 tests; cargo test pass; no_std build pass.
- Pages: [NTS specification](concepts/nts-spec.md), [conformance suite](concepts/conformance-suite.md), [TypeScript SDK](concepts/typescript-sdk.md), [Rust SDK](concepts/rust-sdk.md), index; `spec/CHANGELOG.md`, `spec/README.md`, SDK READMEs. Open: G-1 (fep-0005 in TS / Rust; another agent).

## [2026-11-14] query | M4-01 / M4-02: causal decoder lookahead vs accuracy and latency
- Ran the remaining `run.py` stages of `experiments/2026-11-13-m4-01-02-lookahead` (accuracy, emission in the background CPU class; latency in the timing class; tables; figure). Models: `shared` (L per batch), `dedicated_0`, `dedicated_25`, 30 epochs each, T15 val_eval 701 trials.
- Accuracy: shared greedy PER 0.6565 (L 0), 0.4449 (40 ms), 0.4097, 0.3858, 0.3768, 0.3687 (500 ms); dedicated L 0 0.6954, dedicated L 500 ms 0.3487. All far from the published decoder (0.0954); best epoch = last epoch, so under-trained.
- Emission: the shared model's phonemes are ready exactly L later; the dedicated L 500 ms model's phonemes are ready 180 ms earlier (median) than the dedicated L 0 model's. `latency` is an upper bound on signal use, not the user-visible delay.
- Trust (frozen `tcfg-f5ca0020b3b8fce2`, not refitted): 0 commits everywhere; eWPM 3.38–5.15 vs gaze 4.02. Compute: decoder p95 about 2 ms per bin, trust p95 0.33–0.36 ms per frame, end of utterance p50 79.8–107.5 ms at every L; measurement environment not clean (5.77 % foreign load, SMT siblings 25.23 %).
- Deviations: `latency-force` (M6-13 soak done but no DONE file); two latency-stage bug fixes (header row, isolation record read too early); figure reference = dedicated L 0.
- Pages: new [lookahead vs accuracy and latency](questions/lookahead-latency-accuracy.md) (+ SVG figure); links from [streaming trust layer](concepts/streaming-trust-layer.md), [sync vs async](concepts/synchronous-vs-asynchronous-decoding.md), [architecture](questions/architecture.md), [B2T '25 source](sources/brain-to-text-25-copytask.md); index. `nts-spec.md` not edited (another agent's work in progress); the 1.1 idea of an informative measured-emission-delay field is on the question page.

## [2026-11-14] setup | P1-09: control profile fep-0005 in the TypeScript and Rust SDKs (gap G-1 closed)
- New `sdk/typescript/src/profiles/fep0005.ts` and `sdk/rust/src/profiles/fep0005.rs`: ports of `fidetype.conformance.profiles.fep0005` and the validators of `fidetype.trust.control` (declaration, control, control_enable, control trust_decision format, order, safety). Registered in `CONSUMERS` / `consumer_for`; the CLIs and the parity scripts pick it up. Rust stays `no_std` + `alloc` (only `libm`); TS has no runtime dependency.
- Consumer "acted" list (spec 6.4): `moving_ticks` (ticks of final control COMMITs), plus `acted_intents` and `acted_texts`, as in Python.
- Two Python behaviours copied for identical verdicts: pointer `dims` `true` equals 1; an overflowing speed square (`float(v) ** 2`, `OverflowError`) is a rejection.
- Parity: Python = TS = Rust on 279/279 vectors (`cross-check.mjs --rust`); fuzz seeds 1-6 `--n 30`: 44,196 mutants (fep-0005 7,560), identical verdicts; an extra fep-0005-only run (seeds 11-13, `--n 300`, 37,800 mutants) also identical. No Python bug found; no vector changed. The Python suite accepts both CLIs as external consumers (42/42).
- Tests: pytest 786 passed / 10 skipped; TS `npm test` 32 pass; `cargo test` pass; `thumbv7em-none-eabihf` no_std build pass.
- Docs: `spec/nts-1.0-rc2.md` 1.1, 9.3, 9.5, 11.7, C.2 (G-1 closed), `spec/CHANGELOG.md`, `spec/README.md`, FEP-0005 conformance note, SDK READMEs. Pages: [TypeScript SDK](concepts/typescript-sdk.md), [Rust SDK](concepts/rust-sdk.md), [conformance suite](concepts/conformance-suite.md), [NTS specification](concepts/nts-spec.md), [control events](concepts/control-events.md).
- Review points (not changed): CTL-S7 is checked only after a `stop` decision; the 7.4.5 notes (`p_top1` null, `score_semantics` by radius) have no check.

## [2026-11-14] setup | P3 collector v0.1: FEP-0006 design decisions applied
- Configuration: TOML and JSON only. YAML is not supported (no new dependency); the error message says why.
- File receiver: `eof = "close"` stays the default. A stream without `end` now gives one warning and the counter `closed_without_end` in `/metrics`.
- Several receivers in one pipeline: the `<receiver>/<stream id>` prefix is documented (FEP-0006 1.4) and tested; the prefix now also applies to the status items at shutdown.
- Health and metrics: `127.0.0.1:13133` by default; optional bearer token `token_env` (never in the file, a log or a metric); a bind beyond localhost without a token is a configuration error unless `allow_unauthenticated = true` (then a warning).
- Trust processor: every decision carries `spec_version: "1.0"`. A trust configuration without a blank-safe commit gate gets `min_chars = 1` (TD-9; new `config_id`, logged; counter `gated_commits`); `always_commit` is refused. Decision logs (example, and a log with a gated blank COMMIT) pass fep-0001 in the Python, TypeScript and Rust consumers.
- New standalone `websocket` exporter (no `receiver`): own `WSServer`, `/decisions` only, `token_env`, TLS, `linger_s` for file replay demos. Tested end to end: file → trust → standalone `/decisions` subscriber.
- Fan-out of one receiver to two pipelines: future work. FEP-0006 (Draft) has a "Decisions" table; open: Python vs Rust for v1 (user), blank OFFER candidates, health token scope, add vs refuse the gate.
- Tests: `tests/test_collector.py` 44 (was 29). Pages: [collector](concepts/collector.md); `examples/collector/collector.toml`.

## [2026-11-14] setup | P1-10: DecisionTracker tracks control decisions; CTL-S7 check follows the spec
- `DecisionTracker` (TypeScript `sdk/typescript/src/trust.ts`, Rust `sdk/rust/src/trust.rs`) now tracks `profile = "control"` decisions. Before, it marked them invalid. It checks CTL-T1 … T5 (`seq` over all profiles, ticks do not go back, one move per input tick, a HOLD may repeat a tick) and the log checks CTL-S1 … S7, with the same state machine as the profile (`ControlSafety`). New field `tick`; `forward` on a valid control COMMIT, so the forwarded ticks are the "acted" list (6.4). The Python package has no `DecisionTracker`.
- CTL-S7: the `fep-0005` check (Python, TypeScript, Rust) now refuses an intent COMMIT while the control is not engaged, also before the first engage (`engaged_after` / `engagedAfter`). Before, only after a `stop`. No existing vector changed. New vectors E20 (reject) and E21 (accept); `fep-0005` 44 vectors.
- 7.4.5 notes (`p_top1` null, `score_semantics` by radius): no rule id and no MUST, so no check (informative).
- Parity: Python = TS = Rust on 281/281 vectors; fuzz seeds 1-6 `--n 30` 44,556 mutants (fep-0005 7,920) identical. pytest, `npm test`, `cargo test --locked`, thumbv7em no_std build pass.
- Docs: `spec/nts-1.0-rc2.md` 1.1, 7.4.6 (informative note), 9.3, 9.5, A, C.1, C.2; `spec/CHANGELOG.md`; SDK READMEs. Pages: [TypeScript SDK](concepts/typescript-sdk.md), [Rust SDK](concepts/rust-sdk.md), [control events](concepts/control-events.md).

## [2026-11-14] setup | P2-06: the three SDKs are ready to publish (not published)
- Python `fidetype`: dynamic version from `__version__`, PyPI README with absolute links (`hatch-fancy-pypi-readme`), classifiers, project URLs, `py.typed`, script `fidetype-collector`. The wheel ships the golden vectors (`fidetype/_spec/conformance`); the two vector-dir lookups fall back to it outside a checkout. sdist include list anchored (it took 20 MB of `sdk/rust/target` executables before). `twine check --strict` PASS; clean venv: `fidetype --help`, `conformance --profile fep-0001 … fep-0005` PASS.
- TypeScript `@fidetype/sdk`: `private` removed, `publishConfig` (public, provenance), repository / homepage / bugs / keywords, `./package.json` export, `files` = `dist/**/*.{js,d.ts}` + `bin` + README + CHANGELOG + LICENSE (52 files, 118 kB), `prepack` (clean, build, `check:version`). `fidetype-ts conformance` stops with a clear error when no vectors are found.
- Rust `fidetype`: `publish = false` removed, `rust-version = "1.81"` (built with 1.81), `include` whitelist (31 files), docs.rs metadata, feature docs, `SDK_VERSION` = `CARGO_PKG_VERSION`; `fidetype-rs conformance` refuses a missing vector dir (before: a silent empty run). `cargo publish --dry-run --locked` PASS.
- Names (read-only): PyPI `fidetype`, npm `@fidetype/sdk`, crates.io `fidetype` all free (404).
- New: `docs/RELEASING.md` (semver per SDK, SDK-V1 … V6 rules against spec 11.7, checklist, trusted publishing steps), `docs/release-workflow.example.yml` (manual only, not in `.github/workflows/`), `CHANGELOG.md` (Python), `sdk/typescript/CHANGELOG.md`, `sdk/rust/CHANGELOG.md`, `LICENSE` copies in both SDK folders. CI jobs `packaging` and `rust-msrv`.
- Pages: [Python SDK](concepts/python-sdk.md), [TypeScript SDK](concepts/typescript-sdk.md), [Rust SDK](concepts/rust-sdk.md), [roadmap](questions/roadmap-standard.md) P2 status.

## [2026-11-14] setup | P1-11 + P3-05: TD-12 (no blank candidates); collector drops them; open /healthz
- New RC2 rule **TD-12** (`spec/nts-1.0-rc2.md` 6.3, Appendix B row 3a, Appendix C rows, 1.1, 9.3, 9.5; `spec/CHANGELOG.md`): a 1.x trust layer SHOULD NOT put blank text in `shown` of a text OFFER, ASK or OFFER_WORDS; a consumer MUST NOT offer a blank candidate (it drops it). Producer part version-gated like TD-9; consumer part for every version.
- Validators: advisory check `FEP1-TD-SHOWN` (a warning, never a reject) in Python, TypeScript and Rust; TS / Rust profile `failures()` skip advisory checks. Consumer summary adds `offered` and `advisories`. SDK `DecisionTracker` drops blank texts from `offered` and warns on 1.x decisions.
- Vectors `fep-0001` F55 (accept with a warning) and F56 (0.1: accept, no warning); 56 now. Python = TS = Rust on 283/283 vectors and 44,916 fuzz mutants (seeds 1-6, `--n 30`).
- Collector (FEP-0006 3.2 rule 6): the trust processor drops blank candidates; an OFFER / OFFER_WORDS with none left becomes `ABSTAIN` with `shown = []` (an OFFER without `shown` would read as a TD-10 privacy log). Counters `blank_candidates_dropped`, `blank_offers_abstained`.
- Collector health (FEP-0006 7): `/healthz` is open and shows only the status; the bearer token protects `/metrics` only. The automatic commit gate stays. FEP-0006 open questions 2-4 closed ("Decisions", second round).
- Pages: [collector](concepts/collector.md), [NTS specification](concepts/nts-spec.md), [conformance suite](concepts/conformance-suite.md), [TypeScript SDK](concepts/typescript-sdk.md), [Rust SDK](concepts/rust-sdk.md).

## [2026-11-14] setup | P3-01 + P3-03 + M6-16: collector LSL receiver and LSL decisions exporter; fast LSL reconnect, open_timeout 1 s
- M6-16 ([results](../experiments/2026-11-14-m6-16-lsl-open-timeout/results.md)): the inlet open limit is now `LSLMapping.open_timeout_s` (default 1.0 s, was a fixed 5 s; `fidetype lsl run --open-timeout`). A healthy localhost open takes about 12 ms; a stale outlet costs the full limit. The start retries a timed-out open until the resolve `timeout`.
- Finding: a shorter `open_timeout` alone did not shorten the reconnect (6.2-6.8 s in 10 of 12 restarts at 5, 2, 1 and 0.5 s). Cause: a one-shot `resolve(timeout = 0.5 s)` right after the loss blocks about 5.5 s on this Windows PC. This contradicts the M6-14 note; both are kept on the [LSL input](concepts/lsl-input.md) page.
- Fix: `reopen` asks a `ContinuousResolver` and prefers a new uid over the stale info of the lost outlet (`reconnect_resolver = "continuous"`, default; `"oneshot"` = old path). Reconnect after a 1.5 s outage: **2.42 s in 6 of 6 runs**. Max loop step 21.0-21.3 ms (M6-14 holds). CPU class background.
- Collector `lsl` receiver (FEP-0006 2 rule 6): wraps `open_source` / `LSLEventSource`. Loss → `lost` (no final decision, LSL-G2), reconnect with a new header; frame gap inside an utterance → `gap` (`on_gap = "abort"`, the collector default); a gap right after a boundary cuts nothing (`gaps_between_utterances`); `mark` only counts; `end` → `closed`; give-up → done. Settings: query, `events`, `stream_id`, gap mode, clock, foreign-stream keys, `resolve_timeout_s`, `open_timeout_s`, reconnect settings, `stop_at_end`.
- Collector `lsl` exporter (FEP-0006 4 rule 5): wraps `DecisionOutlet` (LSL-X1 … X3 desc keys; `config_id` from the pipeline's trust processor); decisions only; `no_text = true` removes `shown` (SEC-7), else a warning; no host names (LSL-C3); 0.5 s flush at stop while a subscriber is connected.
- Tests: `tests/test_collector_lsl.py` (17, incl. a real LSL loopback outlet → collector → decisions outlet → inlet, equal to the file receiver), `tests/test_lsl_open_timeout.py` (7, incl. a real-LSL restart < 4.5 s). Stream names `test-collector-*`. CI has no pylsl: the real-LSL tests skip.
- Pages: [collector](concepts/collector.md), [LSL input](concepts/lsl-input.md), index. FEP-0006 (LSL removed from "not in v0"), `examples/collector/collector-lsl.toml`.

## [2026-11-14] lint | Wiki lint pass 1: links, orphans, stale claims, diagrams 09 and 11
- Mechanical check of all 90 wiki pages (relative links, frontmatter keys and types, `sources:` slugs, index entries, inbound links). Result after the fixes: 0 broken links, 0 frontmatter errors, 0 pages missing from the index, 0 orphans (overview.md is linked from the index only, as intended).
- Broken link fixed: [WebSocket input](concepts/websocket-input.md) pointed to a missing `streaming-trust-events.md`; it now points to `spec/feps/0001-streaming-trust-events.md`.
- Orphan fixed: [Conformal prediction under covariate shift](sources/conformal-covariate-shift.md) had no inbound link except the index; [Conformal risk control](concepts/conformal-risk-control.md) now links it.
- [NTS specification](concepts/nts-spec.md): new section "Timing evidence: lookahead" (MET-4, MET-5, declared `latency` = upper bound, possible 1.1 field), with a link to [lookahead vs accuracy and latency](questions/lookahead-latency-accuracy.md). The backlink was already there.
- LSL reconnect cause: [LSL input](concepts/lsl-input.md) already had the M6-16 contradiction note. The M6-14 "Our take" now says its cause is superseded. `experiments/2026-11-14-m6-14-nonblocking-reconnect/results.md` has a correction line (blocking one-shot `resolve()`, about 5.5 s; not `open_timeout`).
- Stale claim fixed: [roadmap P1](questions/roadmap-standard.md#p1-spec-to-10) said RC1 is the current draft; an update line now names RC2.
- Diagram 09: M3 and M4 renamed to the tracker names (trust-layer validation, causal decoder); "preprint" and the Paper 1 star removed; arXiv endorsement and peer review moved to the PUB track (no deadline). Diagram 11: v0.1 box no longer says "11.5k lines" and lists the 11-14 early starts (RC2 draft, three SDKs ready to publish, collector draft); P2 lists the SDKs that exist; four arrows re-routed (v0.1 → P1, P1 → P2, P2 → P7, P8 → P10) so they no longer run along box edges. Captions in `slides.json` and the index row updated; `node tools/drawio/build.js` run; headless Edge renders checked.
- Judgement calls for the user (not changed): overview.md is dated 2026-11-13 (no RC2, lookahead, collector); roadmap "src today 11.5k lines" table (2026-11-10 count; now about 37k); no concept pages for FEP process, Learn then Test, adaptive conformal inference, or trust decision; SDK pages still say "NTS 1.0 RC1" for the TD-9 change (true when written).

## [2026-11-14] setup | P4-01 (part): generic CTC-logits and text n-best adapters
- Choice: the roadmap P4 list starts with dataset replay. B2T '25, Toronto sEMG and SpanishBCBL replay adapters exist. The remaining datasets (Willett handwriting, KT-sEMG, emg2qwerty) need downloads. We built the two **generic decoder-output** adapters first: they need no GPU and no new data, and they cover the two output shapes of public decoders (CTC frames, text only).
- `fidetype.adapters.ctc_logits` ([CTC-logits adapter](concepts/ctc-logits-adapter.md)): logits / probs / log-probs (auto-detected), `(T, V)` and padded `(B, T, V)` / `(T, B, V)` batches with lengths, torch tensors without a torch import; vocabularies from a JSON list, a Hugging Face `vocab.json` map (`<pad>` blank, `|` → space) or `tokens.txt`; frame temperature marked as calibration; MET-5 (offline = `causal = false`, no `latency`); content-hash `stream.id`; CLI for `.npy` / `.npz` (`allow_pickle=False`) with a conformance check per stream. Conformance target `adapter:ctc-logits` (5 streams, provenance).
- `fidetype.adapters.text_nbest` ([text n-best adapter](concepts/text-nbest-adapter.md)): CSV `id,text[,score]` (rows with one id = one n-best list) and JSON Lines → hypothesis-only stream (`vocab = []`, `hypothesis` + `segment_end` per utterance); EVD-1 / EVD-4 / DEC-2 / HYP-1 / MET-5 enforced; `check_stream_file` = v0.1 suite + `fep-0001` profile.
- Real outputs (local, not committed): our lookahead GRU T15 log-probs (L 0 and L 500 ms, 701 trials each) → 1,402 / 1,402 streams trust-ready; published T15 RNN logits through the generic adapter equal the `b2t25` adapter on 1,718 / 1,718 trials (max |Δ| 7.6e-6); published T15 decoder sentences (1,718) → one text stream, trust-ready + `fep-0001` pass.
- Tests: `tests/test_adapter_ctc_logits.py` (26), `tests/test_adapter_text_nbest.py` (11); `tests/test_conformance.py` target set updated. Full suite 864 passed, 10 skipped (background CPU class).
- Pages: two new concept pages, index, [roadmap P4](questions/roadmap-standard.md#p4-device-and-toolkit-adapters) status line, [CTC](concepts/ctc.md) backlink.

## [2026-11-14] lint | Lint follow-ups: overview, src line count, four concept pages, C-order note
- [Overview](overview.md) dated 2026-11-14: new bullets for the lookahead result ([lookahead vs accuracy and latency](questions/lookahead-latency-accuracy.md)) and the M4-12 interim result (in progress: dedicated L 0 model greedy PER 0.2574 on T15 val, 701 trials, vs 0.6954 before and 0.0954 for the published decoder; 0 commits, 0 wrong commits; source `experiments/2026-11-14-m4-12-decoder-retrain/results/accuracy.json`); new "State of the standard" block (NTS 1.0 RC2, three SDKs, [collector](concepts/collector.md), P4-07 [CTC-logits](concepts/ctc-logits-adapter.md) and [text n-best](concepts/text-nbest-adapter.md) adapters, trust guarantees).
- [Roadmap](questions/roadmap-standard.md): `src/` is 38,500 Python lines in 105 files at commit bcabf04, plus 12,808 lines in `tests/` (counted 2026-11-14). The 2026-11-10 count (about 11.5k) stays as a history row.
- Roadmap P2: dated note "Actual order so far: Python, TypeScript, Rust; C not started. Plan change pending user decision." The plan text and diagram 11 ("C core", gate "Spec 1.0 RC + Python/C 1.0") are not changed.
- New concept pages: [FEP process](concepts/fep-process.md), [`trust_decision` event](concepts/trust-decision.md), [Learn then Test](concepts/learn-then-test.md) (from [LTT source](sources/learn-then-test.md)), [adaptive conformal inference](concepts/adaptive-conformal-inference.md) (from [ACI source](sources/adaptive-conformal-inference.md)). Inbound links from nts-spec, conformance-suite, collector, streaming-trust-layer, conformal-risk-control and the two source pages. All four are in the index. Numbers are copied from existing wiki pages and the spec; none are new.
- Tracker: R-20 and P4-07 agent stats filled (fragments); new task R-21.

## [2026-11-14] setup | SDK order decision: Python, TypeScript, Rust for NTS 1.0; C core after 1.0
- The user let the orchestrator decide the SDK order. Decision: the NTS 1.0 SDKs are Python, TypeScript and Rust. The C core (`libnts`) moves to after 1.0. It is still planned, for embedded devices and FFI use.
- Reason: the three SDKs exist, pass the same 283 conformance vectors and are ready to publish. C is not started.
- [Roadmap P2](questions/roadmap-standard.md#p2-reference-sdks): the dated decision replaces the note "Plan change pending user decision". Priority table, exit criteria ("Python, TypeScript and Rust reach 1.0 with spec 1.0 RC"), sequencing table, scope-creep rule, P3 dependency and effort row updated.
- Diagram 11 ([diagrams](diagrams/index.html)): P2 box shows the 1.0 set and "after 1.0: C core, C#, Kotlin"; gate is now "Spec 1.0 RC + Python/TS/Rust 1.0". Caption in `slides.json` updated. Render checked with headless Edge.
- Tracker: P2 milestone note and P2-02 note updated; new task R-22; R-21 agent stats filled.

## [2026-11-14] setup | P4-01: downloads for the Willett handwriting, KT-sEMG and emg2qwerty replay adapters
- [Willett 2021 handwriting](entities/willett-handwriting-2021.md): **done**. The Dryad file API needs a login (401). The same deposit (DOI `10.5061/dryad.wh70rxwmv`, Zenodo `dryad` community, CC0) is open on Zenodo record 4695519. Size, Zenodo MD5 and Dryad SHA-256 match. Extracted to `C:\Users\zhang\bci-data\raw\willett-handwriting\extracted\` (20,203 files, 6.10 GB). No code from the archive was run.
- [KT-sEMG](entities/kt-semg-dataset.md): **done**. Harvard Dataverse v1.1, CC BY 4.0, public. 88 of 88 files match the Dataverse MD5 (20,982,743,251 bytes) in `C:\Users\zhang\bci-data\raw\kt-semg\`.
- [emg2qwerty](entities/emg2qwerty.md): **not downloaded, waiting for the user**. One archive of 308.4 GB (above the 100 GB approval limit), no published checksum. Licence contradiction recorded: README CC BY-NC 4.0, `LICENSE` file CC BY-NC-SA 4.0. Research use is fine under both.
- `references/README.md`: three new rows in "Downloaded datasets"; the emg2qwerty survey row notes the `LICENSE` file. Download, check and resume commands in `HANDOFF.md`. Scripts (outside the repo): `C:/Users/zhang/bci-data/scripts/kt-semg-download.sh`, `verify-p4-01.sh`.

## [2026-11-14] setup | P4-01: Willett handwriting and KT-sEMG replay adapters
- `fidetype.adapters.willett_handwriting` ([Willett 2021 handwriting](entities/willett-handwriting-2021.md#replay-adapter-p4-01-2026-11-14)): reads only `sentences.mat` with `scipy.io.loadmat` (no scripts run, no pickles opened). One stream per closed-loop trial: one frame per character that the real-time RNN emitted (31 characters, no blank, `latency = 0`), time from the go cue; 32-token CTC form. Checked on the data: probability-row argmax = emitted character for 100 % of characters; RNN output step 100 ms.
- `fidetype.adapters.kt_semg` ([KT-sEMG](entities/kt-semg-dataset.md#replay-adapter-p4-01-2026-11-14)): chunked CSV reader (row index / 2000, the `Time` column has 6 significant digits), key-log reader (Enter as `\r\n` joined), whole-hour UTC-offset inference for the zone-less start time, key-press streams over 32 W3C key codes, small LDA reference decoder (numpy only).
- No text, participant id, run number or date in `meta`; `fidetype.replay` holds dataset slug, DOI, licence and ordinals only.
- Real data (local, not committed): Willett 288 / 288 trial streams trust-ready, CTC form 288 / 288 (only `PV-WEIGHTS` fails: no weights file). KT-sEMG sample of 7 / 29 runs, session-calibrated LDA: 55 / 55 streams `provenance`; key accuracy 0.4975 vs majority 0.1823. Cross-run LDA 0.1325 (majority 0.1891).
- Conformance targets `adapter:willett` (trust-ready) and `adapter:kt-semg` (provenance). Tests: `tests/test_adapter_willett_handwriting.py`, `tests/test_adapter_kt_semg.py` (synthetic only); `tests/test_conformance.py` target set updated.
- Pages: two entity pages, [conformance suite](concepts/conformance-suite.md) adapter table, [roadmap P4](questions/roadmap-standard.md#p4-device-and-toolkit-adapters) status, index. Open in P4-01: emg2qwerty (waits for the user).

## [2026-11-15] query | M6-15: full-length (7 h) soak test on the fixed code
- Same harness and C1-C10 as M6-13; timing CPU class; plan `experiments/2026-11-13-m6-13-soak/plan-full-rerun.md` (before the run); results in `results.md` (section "Full-length run") and `results-full/`.
- 7.00 h active (25,202 s) in 10.98 h wall time: the PC slept 4.0 h (Sleep from the Start menu). 9 of 10 criteria pass; C8 fails (16 gaps for 14 dropouts; the 2 extra gaps come from the sleep). Without the sleep window, 10 of 10.
- No crash, 0 exceptions, 6,253 decisions, 0 COMMIT, 0 invalid or lost events, push p95 <= 1.11 ms in every window, e2e p95 46 ms, RSS slope -1.44 MB/h.
- Harness: `DONE` marker at every exit (with the reason), machine-load record per heartbeat, `launch_detached.py` (CREATE_NO_WINDOW). Earlier starts died when their visible console window was closed.
- Updated `concepts/lsl-input.md` (soak table + our take), `index.md`.

## [2026-11-15] query | M4-12: causal lookahead decoder retrained (published-like recipe)
- Diagnosis (pre-declared plan `experiments/2026-11-14-m4-12-decoder-retrain/plan.md`, before the runs): M4-01/02 had about 3 % of the published B2T '25 trial passes at a 10x lower LR; the L 0 model under-fitted (train CTC 2.43 vs 0.81 at L 500 ms).
- New recipe: 10,000 steps x batch 96, LR 5e-3 cosine, AdamW eps 0.1, Xavier / orthogonal init, input dropout 0.2, noise 1.0 + random cut. Model, splits and evaluation code unchanged.
- val_eval (701 trials): dedicated L 0 greedy PER 0.2574 (was 0.6954), WER (T = 1) 0.3998 (was 0.9307). Shared L 0 → 500 ms: 0.2634 → 0.2617 (flat; was 0.6565 → 0.3687). Dedicated L 500 ms 0.2988 (was 0.3487). Published: 0.101 (validation partition), 0.0954 (online).
- Emission: dedicated L 500 ms phonemes ready +100 ms vs dedicated L 0 (M4-02: −180 ms). The M4-02 lookahead gain and "ready earlier" result were artefacts of under-training.
- Updated `questions/lookahead-latency-accuracy.md` (new M4-12 section, old numbers kept and marked superseded, contradiction note), `index.md`. Dedicated 200 ms and 300 ms models queued after a hold for another agent's latency rerun.

## [2026-11-15] query | M4-02R: M4-01/02 latency rerun on a quiet machine
- New experiment `experiments/2026-11-15-m4-latency-quiet-rerun/` (plan addendum written before the run; results.md). Run 05:41 to 06:12, after the M6-15 soak and the M4-12 phase 1; the M4-12 queue was held during the run.
- Timing class, foreign load 1.77 % (clean; M4-02 had 5.77 %). Original checkpoints, same 200 trials: decoder p95 2.08 to 2.23 ms per bin, trust p95 0.28 to 0.29 ms per frame, end of utterance p50 86.0 to 101.6 ms; flat in L; 0 commits. Emission file identical to M4-02 (−180 ms is a property of the M4-01 models).
- Secondary: M4-12 dedicated L 0 / L 500 ms and shared at every L: same compute picture, 0 commits; L 500 ms ready +100 ms vs L 0.
- Found: the M4-12 accuracy stage writes `trust-<which>-L<bins>.json` with the same names as M4-01/02 in the shared derived folder, so the M4-01/02 trust decision files were overwritten. The rerun counted the streaming actions directly.
- Updated: [lookahead latency vs accuracy](questions/lookahead-latency-accuracy.md) (new dated section), index.

## [2026-11-15] query | M4-12: dedicated 200 ms and 300 ms models (plan addendum 1); queue done
- val_eval greedy PER: dedicated 200 ms 0.2594 (WER T = 1 0.3923), 300 ms 0.2599 (0.3998); equal to dedicated L 0 (0.2574). Only dedicated 500 ms is worse (0.2988).
- Emission vs dedicated L 0: ready +120 ms (200 ms), +220 ms (300 ms), +100 ms (500 ms).
- Incident: the copied M4-12 `run.py` had overwritten the 8 M4-01/02 per-trial trust files in the shared derived folder (aggregates survive in git); fixed with an own derived folder (`experiments/2026-11-14-m4-12-decoder-retrain/results.md`).
- Updated `questions/lookahead-latency-accuracy.md` (rows + figure), `index.md`.

## [2026-11-15] query | M2-19: trust config re-tuned for the M4-12 T15 decoder
- Plan committed before the runs (`experiments/2026-11-15-m2-19-trust-retune/plan.md`, `0415f4c`); configs frozen and committed before the test run (`0727ae1`).
- Old config `tcfg-f5ca0020b3b8fce2` came from M4-06 (online logits of the published decoder, split A, LTT α 0.05, δ 0.1). Same recipe refitted on `val_select` (fit-A 371, clean cal 351); `val_eval` (701) held out.
- Dedicated L 0: commit_p 0.4 (LTT λ̂ 0.33), 9/701 commits, 6 wrong (0.0086, CP95 [0.0031, 0.0185]): guarantee holds on this draw. eWPM 6.03 (old 5.94, always-commit 5.60, gaze 4.02). Stream = batch 701/701. Shared L 0 and CRC: same picture.
- Uniform control: 186/300 commits (162 empty), because the grid set the guard limit to 1.0. Post hoc M2-18 commit gate: 0/300, 7 commits / 4 wrong on `val_eval`.
- Updated `concepts/streaming-trust-layer.md` (new section), `concepts/learn-then-test.md`, `index.md`.

## [2026-11-15] setup | P1-02: protobuf schema (proto3) as source of truth + generated JSON Schema
- New `spec/proto/neuraltextstream/v1/*.proto` (8 files, package `neuraltextstream.v1`): header, all event types, trust decisions of three profiles, LSL `gap`; field comments cite rule ids. Mapping rules in `spec/proto/README.md` (informative).
- New generator `tools/proto/gen_jsonschema.py` (stdlib) -> `spec/schemas/nts-v1.schema.json`; `check_protoc.py` (protoc via grpcio-tools = parser); `parity.py`; CI job `proto`; `tests/test_proto_schema.py`.
- Parity: 164 compared vectors (91 accept, 73 schema rejects) match, 0 mismatches (built-in validator and `jsonschema` 4.26.0); 90 reject vectors not compared (other grounds); 33 NPZ out of scope.
- Open spec questions Q-1 … Q-8 recorded in `spec/CHANGELOG.md`; RC2 Appendix C.3 added (informative, additive). Hand-written schemas and SDK behaviour unchanged.
- New page `concepts/nts-proto-schema.md`; updated `concepts/nts-spec.md`, `questions/roadmap-standard.md` (P1-02 done), `index.md`.

## [2026-11-15] lint | R-23: repository hygiene + README and docs for outside readers
- Audit of the tracked tree (1,836 files, 45 MB): no caches, build output, data or model files, secrets, private e-mail addresses, third-party PDFs or per-trial typed text. Nothing removed. 9 judgement calls listed in new page `questions/repo-hygiene.md` (example decoded texts in 9 result files, commit e-mail, home paths, agent-memory mirror, archived fragments, paper drafts, logs, large JSON, HANDOFF size).
- New `tools/hygiene/check.js` (forbidden files, secrets, e-mails, size) and `tools/hygiene/links.js` (relative links and anchors); CI job `hygiene`. `.gitignore`: tool caches, node_modules, Rust target, model formats, job sentinels.
- README.md rewritten for newcomers (what NTS is, OpenTelemetry analogy table, status, architecture, quickstarts per SDK, docs links, related projects, layout, contributing, licence and data rules).
- New docs index `docs/README.md` + `getting-started.md`, `concepts.md`, `sdks.md`, `collector.md`, `conformance.md`. SDK READMEs: status note and current vector counts (v0.1 65, fep-0005 44). CONTRIBUTING: CI and hygiene check.

## [2026-11-15] setup | P1-01: NTS 1.0 RC3 draft resolves the protobuf open questions Q-1 … Q-8
- New `spec/nts-1.0-rc3.md` (section 1.6 "Changes from RC2"); RC2 kept as the record. New `spec/feps/0007-unknown-enum-values.md` (Draft).
- Q-7: unknown enum values are version-gated (VER-6 … VER-10): an error in `"0.1"` / `"1.0"` data, accepted with a safe fallback in newer-minor data; the fallback never acts (registry 12.3 column). Binding enums stay closed.
- Q-1 GEN-9 (null only where typed), Q-2 SEG-6 / LSL-G3 (written down), Q-3 CTL-T9 (open reason codes), Q-4 TD-F2 / TD-13 (`declaration` object, key tables), Q-5 GEN-10 (integers at most 2^53 − 1), Q-6 PRF-5 (profile fields), Q-8 INT-T7 / CTL-T8.
- SDK changes in Python, TypeScript and Rust (VER-8 leniency, VER-10 consumers, `DecisionTracker` kind `unknown`, GEN-10, `declaration` check). 17 new vectors (304 in all); no RC2 verdict changed.
- Parity: Python = TypeScript = Rust on 304 vectors and 24,347 fuzz mutants (seeds 1–3). Proto: `json_profile` option, open enums + `*.known`, integer bounds; generated schema 178/178 one-line verdicts; protoc 0 differences.
- Fixed the informative parts: 9.3 / 9.5 counts, C.1 HDR-12 row (V62 … V65), new rows and gap G-12.
- Updated `concepts/nts-spec.md`, `index.md`.

## [2026-11-15] lint | R-24: repository hygiene decisions H-1 … H-9 applied
- The orchestrator decided the nine R-23 judgement calls. `questions/repo-hygiene.md` section 3 marks each one decided or done.
- H-1: `LICENSES/DATA.md` names the 9 result files with example decoded texts. They stay. New rule (DATA.md, CONTRIBUTING.md, checklist): new experiments commit no per-trial decoded or stimulus text; aggregates only.
- H-2: commits now use the GitHub noreply address (repository-local git config). Past commits unchanged.
- H-4, H-5: `agent-memory/` and `wiki/progress/fragments/archive/` are untracked and git-ignored; local copies stay. CLAUDE.md marks the mirror "local only, not committed".
- H-6: the 8 superseded Paper 1 draft PDFs (2.5 MB) are removed from the tree; `final/` stays; git history keeps the drafts. H-7: the empty `run.err.log` is removed.
- H-3, H-8, H-9: checklist rules 9–12. HANDOFF.md entries before 2026-11-13 moved to `docs/archive/handoff-2026-11-08-to-2026-11-12.md` (HANDOFF 120 kB → 58 kB).
- SDK READMEs: "59 of the 60 checks" (`NTS-LEAK-TRUTH` is Python only).

## [2026-11-15] setup | P4-01: emg2qwerty downloaded, checked and extracted
- The user approved the 308.4 GB download. Download 14:05 to 17:07 (one resumable `curl -C -` attempt), into `C:\Users\zhang\bci-data\raw\emg2qwerty\` (outside the repo).
- Archive size 308,382,645,571 bytes = HTTP `Content-Length`. No checksum is published. Our SHA-256: `7b2d827d0068b838e0a15ffe9d5ddddbdc315f55ba1b667636c84e6b510d7581`.
- Extracted: 1,136 files (1,135 HDF5 + `metadata.csv`), 339,359,730,313 bytes. The names and sizes of all files equal the `tar -tvzf` listing. Then the archive was deleted.
- `metadata.csv` aggregates: 108 users, 1,135 sessions, 346.4 h, 5,262,671 keystrokes.
- Updated `entities/emg2qwerty.md` (download status), `references/README.md` (row), `HANDOFF.md`. Manifest with SHA-256 and listing: `C:\Users\zhang\bci-data\raw\emg2qwerty.manifest.txt`.

## [2026-11-15] setup | P4-01: emg2qwerty replay adapter (P4-01 done)
- New `src/fidetype/adapters/emg2qwerty.py` (our own code; no Meta code read or copied). Read-only h5py reader (new optional extra `[emg2qwerty]`, h5py BSD-3-Clause; also in `[dev]`), checked JSON parsing of the keylogger and prompt logs, block-wise EMG reading, one key-press stream per text prompt (KT-sEMG 32-key vocabulary), opaque `stream.id`, `fidetype.replay` with licence `CC-BY-NC-SA-4.0` and `research_only`. CLI `summary` and `baseline`.
- HDF5 layout checked on all 1,135 files: compound `timeseries` (`emg_right`, `time`, `emg_left`), keys and samples on one unix clock. 5,258,056 key presses in the files vs 5,262,671 in `metadata.csv`.
- Baseline (session-calibrated LDA, 8 users × 2 sessions, aggregate only): key accuracy 0.5353 (majority 0.0961); same user, other session 0.5108; 1,392 / 1,392 streams at level `provenance`. Outputs only in `~/bci-data/derived/p4-01-emg2qwerty/`.
- Tests `tests/test_adapter_emg2qwerty.py` (synthetic HDF5). Conformance target `adapter:emg2qwerty`.
- Updated `entities/emg2qwerty.md` (file facts, stream, baseline), `entities/kt-semg-dataset.md`, `concepts/conformance-suite.md`, `questions/roadmap-standard.md` (P4-01 done), `index.md`, `LICENSES/DATA.md`. Paper ingest stays open (separate task).

## [2026-11-15] setup | P1-04: NTS semantic-convention registry v0
- New `spec/semconv/` (YAML): `manifest.yaml` (containers, namespaces, words, open questions) + `attributes/*.yaml` (one file per `meta` namespace, one per `trust_decision` object). 43 keys: the 24 `meta` keys of RC3 3.4, 14 `input` keys (6.1.1), 5 `declaration` keys (6.1.2). Each has type, unit, requirement per conformance level or class, stability (Development, proposed Stable for 3.4), validator, rule ids, suite checks.
- No new semantics. The planned modality namespaces (`emg`, `eeg`, `meg`, `fnirs`, `implant`) have no keys: open question SC-1 (needs a FEP and real producers).
- New `tools/semconv/semconv.py`: writes the generated page `spec/semconv/registry.md`; `--check` compares the registry with the spec tables (3.4, 6.1.1, 6.1.2, 12.3, 12.5), the rule ids, the proto `Struct` containers, the generated JSON Schema, the Python / TypeScript / Rust validator key tables, the suite check ids and levels, and the `meta` values of the accept vectors (210 uses). Tests `tests/test_semconv.py` (32). CI job `semconv` (PyYAML via `uv run --with`).
- Open questions SC-1 ... SC-8 (end of `registry.md`): no modality keys; planned namespaces not reserved in the validators; spec "string" vs validators that refuse `""`; open or closed value lists; target stability of the `trust_decision` keys; unit notation for counts; spec A.1 item 9 still says "not written yet"; SDK constants not generated yet.
- Docs: `docs/semconv.md` (linked from `docs/README.md`), notes in `spec/README.md` and `spec/proto/README.md`. Roadmap row P1-04 updated.

## [2026-11-15] setup | Roadmap P14 "value first" + who-uses-Fidetype page
- User decision: adoption needs real user value and credibility, not only a format (LangChain lesson). Hard rule: no existing roadmap item moved, renumbered, removed or re-prioritised.
- `questions/roadmap-standard.md`: new phase P14 (window 2026-11-16 → 2027-03-31) with items P14-01 … P14-09. Each has goal, deliverable, dependencies, done criteria and the audiences it serves. Phase-overview row, summary bullet and update note added. Short "value-first link" lines on P3, P4, P5, P6, P8 and PUB; their scope does not change.
- P14 items: pretrained decoders with one-line load (T15 and Willett CC0, Toronto / KT-sEMG CC BY; emg2qwerty research-only opt-in), weight hosting decision (ext. blocked), drop-in trust wrapper + 10-minute quickstart, one-command live path (LSL, BrainFlow, OpenBCI), safe-WPM column in the P6 leaderboard (no second leaderboard), recorded EMG demo, live wristband demo (ext. blocked, hardware), result write-ups (no paper deadline), example AAC integration.
- New `questions/who-uses-fidetype.md`: five audiences → pain today → offer → built today (yes / partly / no, with links). Linked from `index.md`, the root README "Why NTS exists" section and roadmap P14.
- Tracker: new milestone P14; tasks P14-01 … P14-09 (P14-02, P14-07 `externally_blocked`, the rest `todo`) through fragments.

## [2026-11-15] setup | P11-01: continuous EMG-to-text decoder on emg2qwerty prepared (GPU training waits for M4-13)
- New `experiments/2026-11-16-p11-01-emg-decoder/`: pre-declared [plan](../experiments/2026-11-16-p11-01-emg-decoder/plan.md), `prep.py` (feature cache), `emgdec.py` (data, model, decoding, CER, NTS export), `train.py` (budget pilot, generic, 8 x personal, eval, NTS), `config.json`, hidden launchers `launch_prep.py` / `launch_train.py` (CREATE_NO_WINDOW + new process group + job breakaway), tests `test_p11_01.py` (14 pass on CPU, synthetic HDF5; exact resume, pause file, causality, chunked decoding, torch = shift conv implementation, budget rule, full smoke of all stages, 64/64 smoke NTS streams `trust-ready`); real-cache CPU smoke 3 steps OK (finite CTC loss). Our own code; no emg2qwerty code read.
- Published baseline to compare (paper Table 3, test CER, no LM, mean over 8 users): generic 55.38 %, personalised fine-tuned 11.28 %. Pre-registered primary criterion: personalised test CER <= 20.0 %.
- Splits: the metadata defines none, so our own rule (paper scheme): 8 test users by salted SHA-256 among users with >= 8 sessions; per test user last 2 sessions test, 2 before val, rest personal train. Generic train 1,036 sessions / 317.1 h; personal train 67 / 19.8 h; val 16 / 4.9 h; test 16 / 4.6 h.
- Cache built on the CPU (22.4 min, background class, 4 workers, 0 errors): 1,135 sessions, 124,582,078 frames (12 log bands x 32 channels at 100 frames/s, float16), 5,249,381 target keys (5,339 dropped: modifiers, arrows, non-ASCII), 95.7 GB in `C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\` (local only). C: free after: 338 GB.
- Model "CRT": per-band circular ring conv + 8 causal dilated residual blocks (d 512), 8,751,522 parameters, receptive field 1.21 s, no lookahead. No GPU used in this task.
- Updated `entities/emg2qwerty.md` (section "Continuous decoder"), `HANDOFF.md` (background job row), tracker (P11-01 in progress).

## [2026-11-15] setup | P1-13: NTS 1.0 RC4 draft (semconv questions SC-2 … SC-8, gap G-12 closed)
- New `spec/nts-1.0-rc4.md` (RC4 DRAFT; section 1.6 "Changes from RC3"; RC3 kept unchanged as the record) and FEP-0008 (`spec/feps/0008-optional-field-types-and-semconv.md`, Draft).
- SC-1 (modality keys) deferred to a FEP with real-producer evidence. SC-2: planned namespaces `emg`, `eeg`, `meg`, `fnirs`, `implant` reserved (MET-3 warning in all three SDKs). SC-3: `meta` string keys are "non-empty string" (MET-7; validators already refused `""`). SC-4: open lists (regulatory status, calibration method, `input.kind`, `declaration.mode`) vs closed (`device.modality`, `declaration.status`, `declaration.where`) (MET-8). SC-5: `input` / `declaration` keys Development in 1.0. SC-6: only physical quantities have a unit (MET-9). SC-7: the YAML registry is normative, the spec tables are informative copies kept equal by CI; A.1 item 9 resolved (MET-10). SC-8: no spec change; the semconv check now also compares the SDK planned namespaces.
- G-12 closed by GEN-11 (optional fields have their table type). Found with a mutation probe (schema refuses, every Python profile consumer accepts): 48 gap signatures before, 10 after (binding records, control-only `trust_decision.t`, new gap G-13). New checks in Python, TypeScript and Rust: `segment_end.reason`, hypothesis `t_start` / `t_end` / `revision_of` / `spans`, `signal_quality.channels`, pointer `absent` / `score` / `score_semantics`, decision `score` / `score_range` (every semantics, DEC-6), header `vocab_id` / `vocab_version` (HDR-16), `trust_decision.reason`, intent `vocab_id` / `pending_cleared` (INT-T8), control `level` (CTL-T8), latency fields on every event incl. frames (TIM-4). Proto `TrustDecision.t` is control-only (`json_profile`).
- 26 new vectors (V69-V82, F63-F66, D24-D26, I25, C25, E25-E27; 330 in all); no RC3 verdict changed; no breaking change for valid data. Python = TS = Rust on 330 vectors and 26,687 fuzz mutants (seeds 1-3, n 30); generated schema 201/201 one-line verdicts (lite + jsonschema 4.26.0).
- Registry: `spec/semconv/` points at RC4; `resolved_questions`; `registered_values` (open lists); regenerated `registry.md`. Updated `spec/README.md`, `spec/CHANGELOG.md`, `spec/proto/README.md`, root and SDK changelogs, `docs/semconv.md`, docs pointers to the current RC, `concepts/nts-spec.md`, `index.md`.

## [2026-11-15] setup | P14-06: visible replay demo (`fidetype demo live`)
- New package `src/fidetype/demo/live/` (config, tracks, server, key decoder, emg2qwerty preparation, page `web/index.html`; default config `live-demo.json`). One command: `fidetype demo live`. The server reuses the FEP-0004 `WSServer` on 127.0.0.1: page, `/state/state.json`, `/events` (demo messages, resumable) and `/decisions` (FEP-0001 events only, for app developers).
- Track kinds: `trust-log` (recorded decisions + optional CTC log-probs preview), `nts-streams` (NTS files through `StreamingTrustLayer` at real time; any decoder plugs in by config, P11-01 template track disabled), `synthetic` (M7-01 session). Missing data: a clear message; a track asked for by name stops the command (exit 2).
- Page: original design, light and dark, phone width. Committed text solid, offers as dashed suggestions, withheld as a hatched pill with p and guard risk; live preview, running counts, latency, dataset + licence chips ("Research use only" for emg2qwerty), "Replay of recorded data, not live decoding" badge, whole-set wrong-commit rate with CP95, commits wrong among commits, offer hits and the always-commit baseline.
- T15 track (CC0): the recorded M2-19 val_eval decisions of `tcfg-e7e8c472f6d9ab33`: 9 commits / 701, 6 wrong (0.86 %, CP95 0.31-1.85 %), 58 of 692 offers contain the intended text; always commit 640/701 wrong. Same numbers as M2-19.
- emg2qwerty track (research only): `--prepare emg2qwerty` matches each P4-01 stream frame to its keylogger key (attributes only, no EMG read), splits the prompts per session (first half calibration, second half replay) and fits a trust config with `api.calibrate`'s recipe and a key-stream frame temperature (`tcfg-84d258c7193af56e`). Replay 700: 3 commits, all 3 wrong (0.43 %, CP95 0.09-1.25 %), 697 offers, 0 contain the intended text; always commit 700/700 wrong. Outputs only in `C:/Users/zhang/bci-data/derived/p14-06-demo/`.
- New `docs/demo.md` with a synthetic-track screenshot (`docs/img/demo-live-synthetic.png`); README and docs index link. Tests `tests/test_demo_live.py` (21, synthetic only). P14-03 drop-in API landed (f70707e) during this task; the demo keeps StreamingTrustLayer (real-time frame pushes); TODO left in `tracks.py`.

## [2026-11-15] setup | P14-03: trust layer as a drop-in wrapper for any decoder (API + docs; validation open)
- New `src/fidetype/trust/dropin.py`, exported lazily from `fidetype.trust`: `calibrate(inputs, texts, *, alpha=0.05, delta=0.1, vocab, blank, lexicon, decode_fn, null_inputs, ...) -> TrustGuard`, `wrap(pairs)`, `load(path, decode_fn)`; `TrustGuard.decide(x) -> TrustResult` (`commit` / `offer` / `withhold`, text, choices, p_top1, guard risk, the NTS `trust_decision` event), `.sheet`, `.write_audit`, `.save`, `.nts_events`. Committed early (f70707e) so P14-06 can use it.
- Input: CTC logits through the [CTC-logits adapter](concepts/ctc-logits-adapter.md) (built-in CTC prefix beam, optional word list, or the user's `decode_fn`), or n-best lists through the [text n-best adapter](concepts/text-nbest-adapter.md) (hypothesis route). No new trust maths: Paper 1 v4 LTT recipe on a random split (25 % fit, 37.5 % policy grid, 37.5 % LTT), commit gate always on, final threshold max(grid, lambda_hat).
- The 2026-11-15 re-tune rule is enforced in code ([streaming trust layer](concepts/streaming-trust-layer.md)): uniform + shuffled null controls run on every calibration; a failing config raises `NullControlError` and no config is returned (pass: commits <= floor(alpha x n); n-best input must bring the user's own null n-best).
- Finding: an LM-free decoder (no lexicon) usually fails the frame-shuffled control, because shuffled frames keep their confidence (synthetic: 8/100 commits, allowed 5). With a word list: uniform 0/100, shuffled 1/100. Very short utterances can pass a shuffle by chance ("no" -> "on").
- Docs: `docs/trust-quickstart.md` (10-minute path), `docs/trust-guarantee.md` (what is and is not guaranteed, assumptions, sheet lines, audit-log fields); `docs/README.md` row. Example `examples/trust_dropin_quickstart.py` (synthetic only, about 1 min CPU; logits test 1/200 wrong commits, n-best 0/200). Tests `tests/test_trust_dropin.py` (15, CI). [who uses Fidetype](questions/who-uses-fidetype.md) and [roadmap P14-03](questions/roadmap-standard.md#p14-03-trust-layer-as-a-drop-in-wrapper) updated.
- Open (P14-03 stays in progress): the timed fresh-agent quickstart run (orchestrator) and held-out wrong-commit <= alpha on two public replay sets.

## [2026-11-15] setup | P14-06: live demo page redesign (plain words, no cramming)
- User feedback: the page was hard to understand, crammed and looked machine-made. New page `src/fidetype/demo/live/web/index.html`: a 3-line story header and a legend (Typed / Suggested / Held back, with commit / offer / withhold as secondary text).
- Each track has the same structure: the latest sentence large (guess, decision, intended sentence, result), "now decoding" with the raw decoder output, a running score in plain words, the guarantee (wrong-commit rate, 95 % interval, target, "type every guess" baseline) and a calm history (newest 5, "Show all"). Engineering values (p(top-1), guard risk, latency, config id, licence, dataset) are behind "Details for engineers".
- One accent colour plus the outcome colours, light and dark; max width 1120 px; spacing 4/8 px. No horizontal overflow at 390, 768, 1024, 1280 and 1440 px (checked with headless Edge through CDP).
- Server counts gain `commit_correct`. New `src/fidetype/__main__.py`: `python -m fidetype ...` now works. Plainer track subtitles in `live-demo.json`.
- [docs/demo.md](../docs/demo.md) gives commands that work without an active venv; new synthetic screenshot `docs/img/demo-live-synthetic.png`. Tests: 3 new in `tests/test_demo_live.py`.

## [2026-11-16] query | P14-03: drop-in trust API validated on two public replay sets; quickstart fixes (P14-03 done)
- Plan first ([plan](../experiments/2026-11-16-p14-03-replay-validation/plan.md), `859acb8`), then [results](../experiments/2026-11-16-p14-03-replay-validation/results.md). Public API only (`fidetype.trust.calibrate` -> `TrustGuard.decide`), recorded decoder output, our B2T '25 word route as `decode_fn`, alpha 0.05, delta 0.1.
- T15 (B2T '25, CC0; by trial, 722 calibration -> 701 held out): null controls uniform 0/300, shuffled 1/300 (pass); 2/701 commits, 2 wrong, wrong-commit 0.0029 [CP95 0.0003, 0.0103]; eWPM 6.02. M2-19 had 9 commits / 6 wrong (0.0086) without the gate.
- T12 (B2T '24, CC0; by session, 14 sessions -> 10 later sessions): controls 0/300 and 0/300 (pass); 25/400 commits, 15 wrong, 0.0375 [0.0211, 0.0611]; eWPM 7.13. Point estimate below alpha (pass by the pre-declared rule); CP95 upper above alpha (session drift, one draw). alpha 0.10 gives the same decisions (grid threshold 0.3 wins).
- API fix found by the validation: `calibrate` fitted the frame temperature on word texts when the decoder outputs phonemes (T15 check: 6.58 vs 1.24). New optional `stream_texts=`; with `decode_fn` and no `stream_texts` the frame temperature stays 1.0 and the sheet warns; `HarnessConfig.fit_frame_temperature` (default True).
- Quickstart timing (fresh agent, orchestrator): 9.0 min, target 10 met. Fixes: Windows `core.longpaths` clone note (quickstart, README, getting-started), install 3-4 min, Python 3.12 hint, sheet now counts in-sample commits blocked by the commit gate and warns when the gate blocks most commits or few LTT items commit, a 4th Step 5 check + troubleshooting row, optional `guard_settings=` (GuardConfig fields), plain-text `TrustResult.reason` ("commit blocked: low acoustic evidence (guard risk 1.00 ...)"), notes on rare offers with the logits route and on p_top1 0.00 / 1.00. [Guarantee sheet doc](../docs/trust-guarantee.md) has a "Validated on" section. 4 new tests (19 in `tests/test_trust_dropin.py`).

## [2026-11-15] setup | North star changed: frontier route; roadmap P15 Frontier leads
- User direction (2026-11-15): "OpenTelemetry" meant a big project that many people use, not the same subject; find a new frontier that does not exist in BCI yet and go that route. Do not move or remove existing roadmap items.
- New page [north star](questions/north-star.md): a BCI that reads language from any body signal, teaches itself from daily use, and provably never puts words in the user's mouth. Pillars F1 safe self-improving BCI (lead, novelty high), F2 faithful LLM decoding + hallucination benchmark (medium-high), F3 cross-body language model (high on paper, medium in practice). Prior art summarised with links (abstract level only; focused literature check P15-10 before any public claim). First experiments E2 (F1), E3 (F2), E1 (F3) with method, controls, cost, proposed success criteria and blockers. Risks and the mapping of existing work.
- [Roadmap](questions/roadmap-standard.md): note at the top; new phase [P15 Frontier](questions/roadmap-standard.md#p15-frontier-added-2026-11-15-leads) with P15-00 … P15-12 (goal, deliverable, dependencies, done criteria); a P15 row in the phase table; P1–P14 unchanged.
- Diagram 11: new purple top row "Frontier" with P15; title, legend and caption updated; render checked with headless Edge.
- [Overview](overview.md): north-star section at the top; history kept. [Direction decision](questions/direction-decision.md#north-star-decision-2026-11-15-frontier-route): dated entry appended. README: new opening line and a "Where we are going" section (no results claimed); NTS content kept.
- Tracker: milestone P15 (2026-11-16 → 2027-06-30) and tasks P15-00 (done) … P15-12 (todo) via fragments.

## [2026-11-15] query | P15-10: focused literature check of the three north-star novelty claims
- New page [novelty check 2026-11](questions/novelty-check-2026-11.md): exact claim wordings, tools (web search, arXiv API, Europe PMC, OpenAlex forward citations; Semantic Scholar refused with 429, OpenReview partial), full-text reads of the closest papers, verdict and safe public wording per claim.
- C1 (F1): holds with narrower wording. No BCI work updates the decoder from user feedback with a stated bound through updates (CORP, DietCORP, ALIGN, Card 2024 have no bound). But ACI already allows a refit model at each step, and continual calibration (2026) refits the threshold after each update, so the bound mechanism is not new.
- C2 (F2): holds with narrower wording. Faithfulness of brain-decoded text is tested offline only (BIT-LLM, SemKey, Jo et al.); Probabilistic Co-Control (2026) calibrates without a bound. Run-time conformal abstention exists for closed-set EEG commands (Xing & Nagarajan, JNE 2026), so the claim must name LLM text and the neural evidence.
- C3 (F3): part 1 holds (no implant + EMG + MEG/EEG text model); part 2 false as written: CORTEG (2026) transfers scalp EEG to ECoG / sEEG (no text). Contradiction noted: NeuGPT experiments are MEG-only.
- New source pages: [continual calibration](sources/continual-calibration.md), [conformal gating for MI-BCI](sources/conformal-gating-mi-bci.md), [CORTEG](sources/corteg-eeg-to-ecog.md); rows in `references/README.md`. [ACI source](sources/adaptive-conformal-inference.md): "Model refits" section from the full text.
- [North star](questions/north-star.md#why-this-is-new): verdict table and safe wordings; pillars and experiments unchanged. Roadmap P15-10 result line; tracker P15-10 done (fragment).

## [2026-11-15] setup | Roadmap P16 write side: emotion and memory (exploration, later)
- User idea (2026-11-15): explore whether a BCI can stimulate or replicate emotion or memory. Filed as a later phase after the P15 core work.
- [Roadmap](questions/roadmap-standard.md#p16-write-side-emotion-and-memory-exploration-added-2026-11-15-later): top-note pointer, P16 row in the phase table, new section with rules, P16-01 … P16-05 (goal, deliverable, dependencies, done criteria, audience) and exit criteria. No existing item moved, renumbered or changed.
- [North star](questions/north-star.md): one-line pointer "Later: P16 write side".
- Diagram 11: new pink row "Write side" with P16 in H2 2027; title, legend and caption updated; render checked with headless Edge.
- Tracker: milestone P16 (2027-07-01 → 2027-12-31); tasks P16-01 … P16-04 todo, P16-05 externally_blocked (fragments). Agent-run stats filled for P15-00 and P15-10.

## [2026-11-16] query | P15-01: F1/E2 CPU pilot, self-improving T12 replay with a guarded update loop (P15-01 done)
- Plan pre-registered before runs ([plan](../experiments/2026-11-16-f1-e2-selfimprove-pilot/plan.md), `b0090d3`); tuning on S7 frozen (`43c9c93`); [results](../experiments/2026-11-16-f1-e2-selfimprove-pilot/results.md). Own small CPU conv-CTC decoder on S0-S6 (val PER 0.445), per-day input layer, 16 replay days S8-S23 (6,720 items), 8 arms, alpha 0.05, delta 0.1.
- S4 pass: feedback-p0.9 phase-C PER 0.470 vs frozen 0.686 (diff -0.2153, day-bootstrap CI95 [-0.2492, -0.1767]); oracle 0.459; p_notice 0.5 / 0.9 / 1.0 nearly equal (labels come mostly from 80 % retypes).
- S1-S3 pass in all 7 guarded arms (true wrong-commit 0.0048-0.0115; at most 1/16 days over alpha; ACI certificate holds); S6 pass (shuffled labels +0.187 PER, S1 holds). D1: self-training collapses (PER about 0.97 from day 6). D2: naive fixed threshold 323 commits / 302 wrong, rate 0.0449 [CP95 upper 0.0502], 4/16 days over alpha.
- S5 FAILS in all 8 arms: uniform null streams commit (276-317/320; shuffled 0-6/320). Cause: the loop has only the non-empty-text gate, not the M2-18 evidence gate `CommitGate(max_guard_risk=...)`. Vacuity caveat: 88-100 % of commits wrong; the bound is over all items. T_s = 50 at the grid edge.
- GPU follow-up (P15-02 / P15-03): evidence gate + per-update null refusal in `GuardedUpdateLoop`, stronger base decoder, wider T_s grid, 2-3 user seeds with realistic retype rate, T15, semi-bandit risk control (P15-04), silent-error margin.

## [2026-11-16] query | P15-02: safe-by-construction GuardedUpdateLoop + gated re-run of the F1/E2 pilot (P15-02 in progress)
- `fidetype.trust.adaptive.GuardedUpdateLoop` (commit `8f2d2c7`): evidence commit gate is the default (`DEFAULT_EVIDENCE_GATE`, M2-18; the loop refuses to start without it unless `unsafe=True`); `check_null_controls()` runs uniform + frame-shuffled nulls on every update (reject if commits > floor(alpha n)); `finish_update()` gives an `UpdateRecord` with a champion / challenger paired sign test, rollback and a chained `config_id`; `audit_records()`; block precision report. 29 unit tests incl. worse challenger refused, null-failing update refused, `config_id` changes on each accepted update.
- Gated re-run ([results-gated](../experiments/2026-11-16-f1-e2-selfimprove-pilot/results-gated.md)), arms frozen and feedback-p0.9 on the same 16 T12 days: **S5 now passes** (null commits 2/640 and 0/640; original 281 and 319); S1-S3 pass; S4 -0.2158 CI95 [-0.2502, -0.1767].
- Precision still bad: frozen 48/48 commits wrong, feedback-p0.9 50/56: bound near vacuous. 32/32 updates accepted, but the sign test on top-1 exact loss has no power (0-1 discordant pairs per day). Uniform refusal rests on a guard risk saturated at the gate limit 1.0.
- Not done: hooks in `TrustGuard` / `OnlineTrustPolicy`, ledger record per update. Roadmap P15-02 result line; tracker P15-02 in_progress (fragment).

## [2026-11-16] query | P15-05: F2/E3 LLM rescoring and rewrite with a grounding check, T15 (P15-05 in progress: T12 open)
- Plan pre-registered before runs ([plan](../experiments/2026-11-16-f2-e3-llm-grounding/plan.md), `2b4fdb8`); [results](../experiments/2026-11-16-f2-e3-llm-grounding/results.md). Local LLM Qwen2.5-1.5B-Instruct Q4_K_M (Apache-2.0) via llama-cpp-python, CPU only. New code `fidetype.trust.grounding` (CTC deficit vs the base top-1, split-conformal `tau`) and `fidetype.lm.llm`. 8 arms (n-gram / rescoring / lattice rewrite / free rewrite, each with and without grounding), T15 M4-12 logits, 701 held-out trials, alpha 0.05.
- Fitted on `val_select`: frame T 1.2889, `tau` 0.0806 nats / frame (95 % of true texts pass), LLM weight 1.0.
- B1 (rescoring + grounding): WER 0.3831 vs A0 0.3985 (diff -0.0154, CI95 [-0.0209, -0.0096]); 10 commits / 2 wrong (0.0029, CP95 upper 0.0103); null 0/300 + 0/300; swapped 0/701. S1-S3 pass; **S4 fails** (fluent-wrong commits 2 vs A0 0), so F2/E3 does not pass.
- Grounding takes swapped-signal commits from 9 / 28 / 23 (B0 / C0 / D0; most are the exact text of the other trial) to 0 in every grounded arm, at no WER cost. It never changes the top-1 on true signals: free-rewrite unsupported words fall only from 0.0121 to 0.0080 of shown words (none committed). The 95 % coverage `tau` is too loose for within-signal hallucination: P15-06 must calibrate on a fluent-wrong loss and gate the committed text.
- T12 v2 not run. Roadmap P15-05 and north-star F2 result lines; tracker P15-05 in_progress (fragment).

## [2026-11-16] query | P15-06: risk-controlled fluent-wrong bound joined to the drop-in wrapper, T15 (P15-06 in progress: T12 open)
- Plan before the held-out runs ([plan](../experiments/2026-11-16-p15-06-halluc-bound/plan.md)); [results](../experiments/2026-11-16-p15-06-halluc-bound/results.md). Uses the cached P15-05 artefacts (no new base decode; 49 new LLM scores into a copy of the cache, CPU).
- New code `fidetype.trust.halluc_bound` (CommitGrounding: sentence deficit vs an anchor and per-word forced-alignment deficit; HallucGate; joint_ltt over (commit_p, tau_commit, tau_word) with p-value max(p_wc, p_h)). `fidetype.trust.calibrate` gets optional `grounding=`, `llm=`, `halluc_alpha=`, `halluc_delta=`, `fluent_threshold=`, `halluc_grid=`, `halluc_select=`; defaults unchanged. `ft.load(..., grounding=)`. Tests `tests/test_trust_halluc_bound.py` (mock LLM). Docs: `docs/trust-guarantee.md` section 9.
- Guarantee: P(fluent-wrong commit rate <= 0.01 and wrong-commit rate <= 0.05) >= 0.9 (exchangeable data). Held out (701): bound held in all 10 guards; fluent-wrong commits B 2 -> 0, C 5 -> 1, D 3 -> 1; swapped-signal commits 0 in every arm, also in the ungrounded ones (tau_commit = 0 alone).
- B1 primary: H1-H4 pass, but 0 commits (P15-05: 10, 8 right): safe but costly. Secondary rule `most_right`: B1 8 commits (7 right, 1 fluent-wrong). T12 not run: P15-06 in progress. Roadmap P15-06 result line; tracker fragment.


## [2026-11-16] query | P15-05: F2/E3 T12 replication (P15-05 done)
- T12 run under the pre-registered T12 addendum (`419fe9e`), same code, model and arms; 480 fitting / 400 held-out trials (by session). [Results, T12 section](../experiments/2026-11-16-f2-e3-llm-grounding/results.md#t12-replication-2026-11-16); aggregates `results/results-t12.json`, `results/summary-t12.json`, log `results/run-t12.log`.
- Fitted: frame T 2.5281, `tau` 0.4742 nats / frame (95 % coverage; about 6x T15), LLM weight 0.5.
- B1 (rescoring + grounding): WER 0.3851 vs A0 0.3885 (diff -0.0034, CI95 [-0.0086, +0.0021]); 15 commits / 8 wrong (0.0200, CP95 upper 0.0390); null 0/300 + 0/300; swapped 0/400; fluent-wrong 4 vs 4. S1 fails, S2-S4 pass: "safe but no gain". C1: S1 and S4 fail.
- Replicated from T15: grounding takes swapped-signal commits 25 / 15 / 23 / 25 (A0-D0) to 0 in every grounded arm; it never changes the top-1 on true signals. Not replicated: the rescoring WER gain. Rewrites add fluent-wrong commits on both sets.
- P15-05 done (both sets vs the criteria); F2/E3 does not pass (T15 S4, T12 S1). Follow-up P15-06 needs a T12 loader. Roadmap P15-05 and north-star F2 result lines; tracker P15-05 done (fragment).

## [2026-11-16] query | P15-06: fluent-wrong bound on T12 (P15-06 done; done-when not met on T12)
- T12 loader in `experiments/2026-11-16-p15-06-halluc-bound/run.py` (`run.py t12 arms`; lazy T12 word decoder, never loaded: 0 base cache misses). Same rules as plan.md. [Results, T12 section](../experiments/2026-11-16-p15-06-halluc-bound/results.md#t12-2026-11-16); aggregates `results/results-t12.json`, `results/summary-t12.json`.
- 400 held-out T12 trials: the joint LTT certifies no grid point in any arm (180 LTT test items; alpha_h 0.01 at delta_h 0.1 needs >= 230 with zero losses). All guards fall back to never commit: 0 commits, fluent-wrong 0, null 0/300 + 0/300, swapped 0/400. B1: H1 fails, H2-H4 pass; utility 0 of 7.
- Fix: an infeasible joint LTT wrote NaN p-values that the sheet JSON refused; `JointLTTResult.to_dict` now writes null (test added).
- Roadmap P15-06 result line; tracker P15-06 done (fragment).

## [2026-11-16] query | P15-02: update hooks in TrustGuard / OnlineTrustPolicy and a ledger record per update (P15-02 done)
- New `fidetype.trust.update_hooks`: `TrustGuardUpdater` runs `GuardedUpdateLoop` for a candidate `TrustGuard` (check block LTT, uniform + shuffled null controls through the commit gate, sign test vs the live guard). Accepted: config swapped into the same guard object, `commit_p` raised to the session threshold if higher, `config_update` audit record. Rejected (also a failed `calibrate`): guard unchanged. `OnlinePolicyUpdater`: swaps the `OnlineTrustPolicy` policy and `commit_floor` only on accept; ACI state kept.
- `GuardedUpdateLoop(ledger=)`, `add_listener`, `reject_proposal`; provenance ledger entry kind `update` (stage proposed / accepted / rejected, `proposal_hash`, `parent_config_id` -> `config_id` chain; `verify` checks the rules). `OnlineTrustPolicy.swap_policy` / `commit_floor` (default -inf: unchanged behaviour). `dropin.py` not changed.
- Replay smoke on the T12 pilot records ([results](../experiments/2026-11-16-p15-02-hooks/results.md)): 15 proposals, 13 accepted, 2 negative controls rejected with the guard unchanged, ledger verifies; 0 phase-C commits (weak decoder; the challenger gate is not exercised on real data). 18 new tests.
- Docs: [quickstart section](../docs/trust-quickstart.md#later-update-the-decoder-safely-p15-02); [provenance ledger](concepts/provenance-ledger.md) page. Roadmap P15-02 result line; tracker P15-02 done (fragment).

## [2026-11-16] setup | P1-04 modality keys (FEP-0009, RC4 amendment), gap G-13 part b, tracker run stats
- Semconv registry: 8 modality keys from producer evidence (`emg.placement`, `emg.derivation`, `meg.sensor_types`, `implant.array_type`, `implant.array_count`, `implant.features`, `implant.bin_s`, `implant.areas`); new rule MET-11; validator `non_empty_string_list`; 51 keys. `eeg` / `fnirs` stay planned (new open question SC-9). [FEP-0009](../spec/feps/0009-modality-semantic-conventions.md), [registry](../spec/semconv/registry.md).
- Python, TypeScript and Rust validators check the new keys; six adapters write them. Vectors V83 … V87; parity 336 / 336.
- G-13 part b closed (proto option `json_null_list`, schema accepts control `absent: null`, vector C26). Part a left open with options A1 … A3 in RC4 C.2.
- [NTS spec](concepts/nts-spec.md) page, roadmap P1-04 row; tracker P1-04 done; null run stats filled for P15-02, P15-05, P15-06 (fragments).

## [2026-11-16] query | P15-07: public hallucination benchmark (null / scrambled / swapped tracks, fluent-wrong metric; P15-07 done)
- New `fidetype.benchmark.hallucination` (protocol `fidetype.halluc/0.1`): deterministic control inputs (P15-05 / P15-06 recipe, seed 0), `run_tracks` for any decoder + trust policy, fluency modes `llm` (llama-cpp, optional), `llm-table`, `conservative` (deterministic fallback), outcomes with flags only, score card with Clopper-Pearson 95 % intervals, CLI `controls | score | rescore`. Split files (salted hashes) in `src/fidetype/benchmark/splits/halluc-v0.1/`.
- Baselines on T15 (701) and T12 (400) for the P14-03 guard, P15-05 B0 (LLM rescoring) and the P15-06 guard, from the cached decoders (read only): [results](../experiments/2026-11-16-p15-07-halluc-bench/results.md). They reproduce the P15-05 / P15-06 numbers exactly. Null and scrambled: 0 commits everywhere. Swapped: ungrounded systems commit as often as on real input (ratio 1.0); P14-03 guard fails on T12 (25/400). P15-06 guard passes all tracks, never commits.
- CI: `tests/test_halluc_bench.py` re-scores the 12 committed outcomes files. Docs [hallucination-benchmark.md](../docs/hallucination-benchmark.md); [open benchmark](concepts/open-benchmark.md) section; roadmap P15-07 result line; tracker P15-07 done (fragment).

## [2026-11-16] query | P14-05: safe WPM at a certified wrong-commit rate (headline metric; leaderboard column)
- Definition `safe-wpm/0.1` ([docs/safe-wpm.md](../docs/safe-wpm.md)): words per minute of committed, exactly right text; offers and withheld trials give 0 words and cost their neural time; a wrong commit gives 0 words and costs 2.0 s + 0.79 s per character; reported only under a certified CRC / LTT bound (else `not-certified`); `above-alpha` and `vacuous` statuses. Measured trial times where the data have them (B2T '25 speech duration; T15 / T12 trial windows), else the track rate model.
- Code: `fidetype.benchmark.safe_wpm`; scorer adds a `safe_wpm` block to every result (optional truth `neural_s`); CLI `fidetype benchmark safe-wpm`; leaderboard column "Safe WPM @ alpha" with `! ABOVE alpha`; 11 tests.
- Baselines (alpha 0.05, [results](../experiments/2026-11-16-p14-05-safe-wpm/results.md)): B2T published + CRC 13.42, + LTT 12.24; B2T ours + LTT 4.05, + CRC 4.90 marked above alpha (0.062); MEG 0.03; Toronto sEMG 0.58 / 0.27 / 0 (aggregate approximation); T15 M4-12 drop-in 0.00 (2 of 2 commits wrong); T12 drop-in 1.27. No-BCI about 4.1. M4-13: `run.py t15-m4-13` after the decoder finishes.
- Pages: [error metrics](concepts/error-metrics.md), [open benchmark](concepts/open-benchmark.md), [who uses Fidetype](questions/who-uses-fidetype.md); benchmark README metric row. Tracker P14-05 done (fragment).

## [2026-11-16] query | P15-04: online risk control with bandit (shown-only) feedback + scope of the guarantee (P15-04 done)
- New `fidetype.trust.bandit_risk`: `BanditCommitRiskControl` (targets marginal / precision; rules aci / cs / max; forced exploration shown as an OFFER, never a commit), `BanditTrustPolicy`, `NaiveShownOnlyControl` (biased baseline). Exported from `fidetype.trust`; existing functions and defaults unchanged. 13 tests (identity certificates for adversarial streams, audit coverage over 120 seeds incl. an adaptive adversary, naive bias, naive precision controller overshoots, wrapper).
- Guarantees: G1 marginal and G2 precision ACI need only commit labels (valid with shown-only feedback, any sequence); G3 IPW + Bennett / Ville anytime audit per grid threshold (design-based). No new theorem claimed.
- Pre-registered replay ([plan](../experiments/2026-11-16-p15-04-bandit/plan.md), commit d90a49b; [results](../experiments/2026-11-16-p15-04-bandit/results.md)): T12 0.0500 [CP95 0.0308, 0.0762], T15 0.0471 [0.0326, 0.0655], identical to `aci`; audit violations 0 / 200; naive shown-only estimate optimistic by up to 0.235; silent errors not covered (q_notice 0.9: 0.0550 true vs 0.0500 observed); precision target 0.5 not reachable (2-7 commits).
- New page [F1 guarantee scope](questions/f1-guarantee-scope.md); docs/trust-guarantee.md section 11; roadmap P15-04 result line; index; north star link; tracker P15-04 done (fragment).

## [2026-11-16] query | P5-02 completed: adaptive conformal on the drop-in guard, one guarantee sheet per policy, joint precision + fluent-wrong LTT (P5-02 done)
- Adaptive conformal for non-exchangeable streams: the existing ACI / ACI-window / window controllers (`online_risk`) and the P15-04 bandit controller already give the any-sequence long-run bounds. New `fidetype.trust.online_guard` wires them into the drop-in API: `guard.online("aci" | "aci_window" | "window" | "bandit")` returns an `OnlineGuard` (`decide` -> `TrustResult` + ticket, `feedback`, `report`, audit records with an `online` block). Default floor = the offline `commit_p`, so the offline sheet still holds. Synthetic drift test: offline wrong-commit rate > 2 alpha; ACI realised rate <= its certificate, near alpha.
- Guarantee sheet per policy: new `fidetype.trust.guarantee_sheet.PolicySheet`, schema `fidetype.guarantee-sheet/1.0` (types offline_crc, offline_ltt, precision_ltt, joint_fluent_wrong, online_aci, online_aci_window, online_window, bandit). Each states the statement, method, risk, levels (alpha, delta or null), validity kind, calibration size and scope, assumptions, what is NOT guaranteed, null controls and status. Printable text, strict JSON, `save_sheets` / `load_sheets` round trip, CLI `python -m fidetype.trust.guarantee_sheet guard.json`.
- `target_precision` now combines with the P15-06 bound: the precision p-value is a third risk of the same joint Learn then Test (max of three p-values, one ordering split, one fixed-sequence test at min(halluc_delta, precision_delta)). Synthetic coverage test passes.
- Defaults unchanged. 10 new tests; [docs/trust-guarantee.md](../docs/trust-guarantee.md) sections 10-12; [F1 guarantee scope](questions/f1-guarantee-scope.md) section "On the drop-in API"; roadmap P5 deliverable 2 status line; tracker P5-02 done (fragment). Open outside P5-02: a decoder good enough for a non-vacuous precision point (M4-13 rerun, P11).

## [2026-11-16] query | P5-01: per-user trust profiles, drift detection, gated re-calibration (P5-01 done)
- New `fidetype.trust.drift` (`ConformalDriftTest`: smoothed conformal p-values + Simple Jumper martingale; `RiskDriftTest`: betting e-process on the observed loss; `DriftMonitor`; anytime valid by Ville) and `fidetype.trust.personal` (`UserProfile` JSON `fidetype.user-profile/0.1`: HMAC user hash, guard, calibration stats + reference scores, `config_id` history, `consent_ref` placeholder, refuses text keys; `PersonalTrust`: risk alarm tightens to offer-only, every other change through `TrustGuardUpdater.propose_calibration`). Existing code and defaults unchanged; 17 tests.
- Pre-registered experiment ([plan](../experiments/2026-11-16-p5-01-personal/plan.md), commit bec214c; [results](../experiments/2026-11-16-p5-01-personal/results.md)): S1 and R1-R5 pass. T12 frozen decoder: `p_top1` does not drift, guard risk does; drift-triggered re-calibration on the guard risk 384 labels vs daily 768, same 15 commits. Open: scale changes not detected; guard-risk test not wired into `PersonalTrust`; weak decoder.
- Pages: [trust personalisation](concepts/trust-personalisation.md), [docs](../docs/trust-personalisation.md); roadmap P5 deliverable 1 status; index; tracker P5-01 done (fragment).

## [2026-11-16] query | P6-01: benchmark tracks v0.2 + licence-clean fixed splits (P6-01 done)
- New `fidetype.benchmark.tracks`: 7 tracks (`b2t25-t15`, `b2t24-t12`, `willett-hw`, `toronto-semg`, `kt-semg` with CC0 / CC BY data; `spanishbcbl-meg`, `emg2qwerty` research-only, NC licences flagged). Each track: task, metrics (CER / WER, eWPM, safe WPM @ 0.05, wrong-commit), required controls, licence + attribution, split rule, loader via the adapters.
- Split files `src/fidetype/benchmark/splits/tracks-v0.2/`: salted hashes only (id, split, group, fingerprint of truth / size); no text, signals or plain ids. `verify` (also `python -m fidetype.benchmark verify`) checks a local copy; `select` maps a split to local data. Verify OK on all 7 local copies; the 3 v0.1-equivalent tracks hash to the same splits (0 mismatches).
- Side jobs ([results](../experiments/2026-11-16-p6-01-tracks/results.md), CPU): Toronto safe WPM exact per trial with participant CI (calib CRC 0.55 [0.28, 0.86], xsession 0.25 [0.06, 0.46]); null-commit audits at the CRC / LTT thresholds: B2T ours and MEG entries now pass all controls (0/300 uniform, 0/637 zeros MEG); B2T published null pass (CER controls stay missing). Board rebuilt, not published.
- Docs [benchmark-tracks.md](../docs/benchmark-tracks.md), benchmark/README, docs/safe-wpm.md Toronto rows; [open benchmark](concepts/open-benchmark.md) section "Tracks v0.2"; index; tracker P6-01 done (fragment). 31 tests. Open: scorer + baselines for the 4 new tracks (P6-02).

## [2026-11-16] query | G3 audit review (bandit IPW anytime bound)
- Independent review of the (G3) audit in `fidetype.trust.bandit_risk`: proof, code, tests, scope page, docs 11.2. Verdict: sound with fixes. Bennett supermartingale, filtration, union bound over 101 x 12 and code match, in decision order with complete feedback.
- H1 (high): audit sums update at `observe`; explored offers that are fed back late or never are missing, so the anytime bound can fail (Monte Carlo: never-fed-back offers, failure rate 1.00). M1: default `seed=0` makes coins a fixed public sequence. M2: the coverage test still passes with half the slack and its adversary does not depend on coins. L1-L5: proof-sketch wording, floor rows, docs assumptions, exploring s = -inf items, optional tighter V.
- Pages: new [G3 audit review](questions/g3-audit-review.md); link from [F1 guarantee scope](questions/f1-guarantee-scope.md); index. No library code changed.

## [2026-11-16] query | Open gaps registered as roadmap items (user: "make sure we do indeed fix the gap later")
- New page [open gaps](questions/open-gaps.md): 15 open gaps, each with a new id, status, follow-up of, depends on and source commit. Linked from the index, the roadmap and HANDOFF.
- Convention: new numbered ids that continue each phase (P1-14, P1-15, P4-09, P5-08 … P5-11, P14-10, P15-13 … P15-19); "follow-up of" names the extended item. No existing item moved, renumbered or removed.
- Roadmap: an "Open-gap items (added 2026-11-16)" block at the end of P1, P4, P5, P14 and P15; rows in the P14 and P15 tables; P6 status line for P6-01 (1d4ff8c). Tracker: 15 new tasks (P1-15 externally_blocked, the rest todo).
- Closed: gap 10 (target_precision + hallucination bound) by P5-02, 3dc84bf. Partly closed: gap 8 (Toronto safe WPM, null-commit audits) by P6-01, 1d4ff8c, the rest is P14-10 with P6-02; gap 6 review done (g3-audit-review, 4cd9cb5), its fixes stay open as P15-17. Added gap 15 (online guards via the drop-in API, P5-11).
- Tracker: null run stats filled for P14-05 (1413.799 s, 249,419 tokens, 106 tools) and P5-01 (1371.878 s, 253,739 tokens, 86 tools).

## [2026-11-16] lint | G3 audit review fixes applied (P15-17)
- H1: bandit audit now counts every decided item at decide time (provisional "wrong" label until feedback); late or never-returned feedback keeps G3 valid. M1: default `seed=None`. L4: s = −inf items never explored. L2: floored audit rows marked. L1/L3: docs, scope page, sheet assumptions. Commit 98daec3.
- Tests: K = J = 1 power test (catches half slack), coin-adaptive adversary, `rule="cs"`, delayed and never-returned feedback, naive negative control. Full suite 1174 passed, 11 skipped.
- P15-04 replay rerun: only exploration counts drop (L4); all rates and bounds unchanged. Pages: [G3 audit review](questions/g3-audit-review.md) "Fixes applied", [F1 guarantee scope](questions/f1-guarantee-scope.md).

## [2026-11-16] setup | P1-14 + P4-09 done (G-13 part a, BrainFlow vendor keys); P15-17 closed
- P1-14 (commit `18713f9`): RC4 amendment 2 applies option A2 of C.2 (FRM-2). A dense frame MAY carry sparse keys; the dense form wins; each present sparse key keeps its type (GEN-11). The three SDK validators (JSONL readers and streaming validators) refuse a wrong type; the schema already typed the keys. Vectors V88 (accept), V89-V92 (reject); 341 in all. Parity 341/341 and 27,497 fuzz mutants (seeds 1-3, `--n 30`); schema 210/210. G-13 closed. Pages: [NTS spec](concepts/nts-spec.md).
- P4-09 (commit `18713f9`): the BrainFlow bridge writes `brainflow.board_id` / `brainflow.board_name` (vendor namespace, MET-3), not `device.*`. The registry evidence rule (SC-1, SC-9) does not support a registry key: the id has a meaning only inside BrainFlow. ExG maps `device.modality` to `other`. Pages: [LSL input](concepts/lsl-input.md), [BrainFlow](entities/brainflow.md); docs/semconv.md.
- P15-17 marked done (fixes `98daec3`, `2e4e38d`; L5 kept as a limit). [Open gaps](questions/open-gaps.md) closed table, roadmap status lines, tracker (fragments).

## [2026-11-16] setup | P6-02 done: submission format v0.2 + one-command scorer + baselines on 4 new tracks
- New `fidetype.benchmark.scorecard` and [docs/benchmark-submission.md](../docs/benchmark-submission.md): unit rows keyed by the salted split hashes (or NTS streams), required shuffled / zeros control runs, local truth checked against the split fingerprints; `python -m fidetype.benchmark check | truth | score <track> ...`. Exit 0 only if all three controls pass.
- Baselines ([results](../experiments/2026-11-16-p6-02-scorer/results.md), cards in `benchmark/results/v0.2/`): T12 v2 + guard safe WPM 0.48 certified; Willett (81/254), KT-sEMG, emg2qwerty (research only) vacuous. Always-commit entries fail null-commit. Board rebuilt, not published.
- [Open benchmark](concepts/open-benchmark.md) gains a P6-02 section. Open gap 8: scorer part and 4 of 5 tracks closed; P11-01 open.

## [2026-11-17] setup | P5-09, P5-10, P5-11 done (gaps 11, 12, 15 closed); new gap 19 (P5-12)
- P5-09: opt-in `ConformalDriftTest(spread=True)` (bets on `|2p - 1|`); plan `3def17e` before the run; results `9277177`: false alarms 0.007 / 0.040 (levels 0.01 / 0.05), sd 1 -> 2 and 1 -> 0.5 detected 200 / 200, T12 permutation null pass; S3 small-shift margin missed (-0.25 sd 0.445 vs 0.61) -> new gap P5-12. [Results](../experiments/2026-11-16-p5-09-drift-spread/results.md).
- P5-10: opt-in `PersonalTrust(guard_risk_test=True)`; `calibration_stats` writes `reference_guard_risk`; defaults unchanged (CHANGELOG, docs 4.1). P5-01 replay reproduced exactly; guard-risk alarms through `PersonalTrust` at items 697, 1,794, 2,159, 6,647 (= A2g). [Note](../experiments/2026-11-16-p5-01-personal/results.md#p5-10-guard-risk-test-through-personaltrust-2026-11-16).
- P5-11: `guard.online(...)` reproduces P15-04 on T12 / T15 exactly with `floor=False` (item-level scores equal); explained differences: default floor, no exploration coins (policy offers), window warm start. Dated note in the P15-04 results. [Results](../experiments/2026-11-16-p5-11-online-replay/results.md).
- Pages: roadmap (statuses, new P5-12), open-gaps (3 closed, gap 19 open), concept [trust personalisation](concepts/trust-personalisation.md), tracker.

## [2026-11-17] setup | P14-04 + P4-02 done: one-command live decode (`fidetype live`)
- New `fidetype.live` ([docs](../docs/live-decode.md), [results](../experiments/2026-11-16-p14-04-live/results.md)): sources synthetic / BrainFlow (bridge code in-process; OpenBCI via board ids, untested) / LSL (raw signal + `keypress` / `segment_end` markers); key windows -> KT-sEMG reference model with causal z-score -> key beam search -> drop-in trust guard (n-best) -> one line per decision + NTS (trust-ready, provenance PASS).
- Assets: `builtin:synthetic-keys` (own synthetic signal, JSON weights; held-out 126 commits / 6 wrong of 200 = 0.030 at alpha 0.05; null 0 commits). KT-sEMG (CC BY 4.0) model + guard made locally by `train-kt`; `replay-kt` over LSL on test run28: 22 offers, 0 commits (key acc 0.248, weak). BrainFlow Synthetic board: 0 commits.
- Latency added per window p50 0.22-0.65 ms; per decision p50 1.4-2.5 ms. Quickstart sections 2-4: 107.5 s.
- Tests `tests/test_live.py` (17); CI job `live` with [lsl,brainflow]. Full suite 1209 passed, 11 skipped.
- Pages: roadmap (P4-02, P14-04 status; new items P4-10, P4-11, P14-11), [open gaps](questions/open-gaps.md) 16-18, [who uses Fidetype](questions/who-uses-fidetype.md) row 5, [LSL input](concepts/lsl-input.md), [BrainFlow](entities/brainflow.md); docs/README; tracker (fragments).

## [2026-11-17] setup | P7-01 done: conformance kit + `nts-conform` CLI
- New kit `spec/conformance/kit/`: 31 synthetic example files over every NTS 1.0 RC4 wire form (JSON Lines streams and decision logs for text / intent / control, NPZ, LSL and WebSocket captures). Verdict, rule ids and failing / warning checks per file; `kit.json` index; one vector-format `manifest.json` per profile; `rule-map.json` (check id -> rule ids from RC4 Appendix C.1).
- New console script `nts-conform` (`check`: per-rule report with location, JSON report, exit 0/1/2, stdin; `kit`: reference run or an external validator via `--cmd` / `--impl` / `--verdicts`; `list`, `build`, `rules`). Code: `fidetype.conformance.kit`, `.rules`, `.nts_conform`.
- Parity: Python = TypeScript = Rust on 31/31 kit files; schema parity 0 mismatches (new reject class `semconv`). Kit runs in `npm run ci`, `cargo test`, CI jobs `rust`, `typescript-parity`, `rust-parity`, `packaging`.
- Pages: [docs/conformance.md](../docs/conformance.md) (kit section), [conformance suite](concepts/conformance-suite.md), [roadmap P7](questions/roadmap-standard.md#p7-conformance--certification), [open gaps](questions/open-gaps.md).
- New gap 20 = P1-16: MET-11 has no Appendix C.1 row and no modality-match check.

## [2026-11-17] setup | P4-11, P4-10, P14-11 done (gaps 16, 17, 18 closed); new gaps 21 (P4-12), 22 (P4-13)
- P4-11 (commit `c3834c2`): `fidetype live --source lsl` reconnects with the `fidetype.adapters.lsl` reconnect code (new opt-in backoff), drops the cut segment and the first segment after a gap, writes `lsl_status` `gap_abort` with the LSL-G3 fields. [docs](../docs/live-decode.md#4-lsl-streams).
- P4-10 (pre-registered in `c3834c2`, results `de7f84e`): `--timing detect` with causal onset detectors ([results](../experiments/2026-11-17-p4-10-onset/results.md)). KT-sEMG test runs ±50 ms: linear F1 0.588 (H1 >= 0.70 failed), envelope 0.461; effective key accuracy 0.84x oracle; 0 commits.
- P14-11 (`c3834c2`): CI job `live-kt` replays KT-sEMG run3 (CC BY 4.0, SHA-256 pinned, cached) over pylsl and validates the NTS. First run PASS.
- Pages: [roadmap](questions/roadmap-standard.md) (P4-10, P4-11, P14-11 status; new P4-12, P4-13), [open gaps](questions/open-gaps.md), tracker.

## [2026-11-17] setup | P7-02 + P1-16 done: conformance levels, self-certification list, MET-11 check (gap 20 closed); new gaps 23 (P7-05), 24 (P7-06)
- Commit `ce7e085`. NTS 1.0 RC4 amendment 3 ([spec](../spec/nts-1.0-rc4.md#96-implementation-levels-nts-core-nts-full-nts-trust-ready-amendment-3) 1.6, 9.2, 9.6, 9.7, C.1): implementation levels NTS Core, NTS Full, NTS Trust-ready (cumulative; producer by `nts-conform check`, consumer by `nts-conform kit`; bindings by their kit entries); rule ids CNF-2 … CNF-8; generated [`levels.json`](../spec/conformance/levels.json).
- `nts-conform`: stream level per file, producer / consumer level, `--claim`, `--binding`, `--require-level`, `{level}` in `--cmd`; sub-commands `levels`, `certified`. Finer rule mapping (`refine` in `rule-map.json`). Kit 0.2.0: 36 files (K32 MET-11 warning, K33-K36 stream levels).
- Self-certification list [`certified.json`](../spec/conformance/certified.json) with evidence: Python / TypeScript / Rust SDKs = consumers at NTS Trust-ready; text n-best adapter = producer at NTS Trust-ready; 7 frame adapters = producers at NTS Core. Pull-request process: [docs/conformance.md](../docs/conformance.md#self-certification).
- P1-16: advisory `NTS-MODALITY-MATCH` in all three SDKs; the v0.1 summaries return `warnings` and `level`, so the runners compare the warning (V93-V96, kit K32). MET-11 has its C.1 row; every RC4 rule id is traced.
- Parity: Python = TypeScript = Rust on 345 vectors, 36 kit entries, 27,767 fuzz mutants; schema 213/213 one-line verdicts.
- Pages: [conformance suite](concepts/conformance-suite.md#implementation-levels-and-self-certification-p7-02), [NTS spec](concepts/nts-spec.md), [roadmap](questions/roadmap-standard.md) (P1-16, P7 status, new P7-05, P7-06), [open gaps](questions/open-gaps.md), index, tracker.

## [2026-11-17] setup | P6-08 done: v0.2 entries for b2t25-t15, toronto-semg, spanishbcbl-meg (gap 31 closed); P6-02 follow-up gaps 25-30
- Commit `b9fa645` ([results](../experiments/2026-11-17-p6-02b-v02-entries/results.md)): the v0.1 pipelines rerun in the v0.2 format (same decoders, fits, seeds, thresholds) and scored by `python -m fidetype.benchmark score`. 21 entries; CER, WER, wrong-commit, commit rate and safe WPM equal v0.1 on all of them (commit scores equal the committed per-trial items). eWPM 0.04-1.86 lower: one decision per unit and measured B2T speech time.
- Controls now per unit: B2T ours pass / pass; B2T published fail / fail (text-only decoder: the text does not depend on the input); MEG (research only) and Toronto pass at input level.
- New partial entry b2t25-t15 M4-12 + drop-in guard: 103 of 816 units. The decoder train partition holds about 368 track test trials and val_select 106 (removed from the calibration), so only val_eval trials are scored. CER 0.204, 0 commits (vacuous). M4-13 entry: one command `run.py t15-m4-13 score-m4-13 table` when its outputs exist (not run).
- Gaps from the P6-02 report registered: 25 = P6-05 (KT-sEMG cal too small for LTT), 26 = P14-12 (Willett word LM, 81/254 coverage), 27 = P14-13 (EMG baselines without oracle timing), 28 = P6-06 (input-level T12 / Willett controls), 29 = P14-14 (T12 safe WPM 0.48 vs no-BCI 4.00), 30 = P6-07 (rule for partial entries). Gap 8 (P14-10) partly closed by `5133e04`; only P11-01 is left.
- Tracker: run stats filled for P1-14, P15-17 (G3 review + fix), P6-01, P5-02 and the gap-registration run (new task R-25).
- Pages: [roadmap](questions/roadmap-standard.md) (P6 status, P6-05 ... P6-08, P14-10, P14-12 ... P14-14), [open gaps](questions/open-gaps.md), tracker. Board rebuilt, not published.

## [2026-11-17] query | T15 split audit: decoder train / calibration / evaluation overlap; new gaps 32-35
- New page [T15 split audit](questions/t15-split-audit.md). Scripts and counts (no text): `experiments/2026-11-17-t15-split-audit/` (match.py, audit.py, results/*.json). Per-trial hashed match table local only (`derived/t15-split-audit/`).
- Matched the 1,718 `t15_copyTask.pkl` trials to the B2T '25 HDF5 trials by (date, sentence, frame count). Track test (816) vs M4 partitions: train 366 (up to 368), val_select 102 (up to 106), val_eval 98 (up to 103), HDF5 test 109, unmatched 141.
- Every M4-x result (M4-01/02, M4-12, M2-19, P14-03, P14-05, P15-05/06/07, P5-02, P15-04, P5-11, demo, M4-13 eval and reruns) scores `val_eval`: 0 of 701 log-prob keys on a train or val_select trial. P6-08 partial entry: 103 units, 0 in train or val_select. B2T ours / published cards: clean (tune and calibration inside `cal`). Pre-registered M4-13 reruns: not affected (disclosure note proposed, not applied).
- Indirect overlap: the 3 word-decoder settings were tuned on 400 `cal` trials; the Paper 1 re-splits (R3, R4, M2-18 / M3-01/02 re-split tables) put 179-224 of them in each test set of 818; 16 are `val_eval` trials.
- New gaps: 32 = P6-09 (full-coverage M4-x entry without overlap), 33 = P6-10 (overlap check in the benchmark), 34 = P15-20 (halluc-v0.1 T15 index rule), 35 = P14-15 (re-tune word-decoder settings without evaluation trials). Pages: [roadmap](questions/roadmap-standard.md), [open gaps](questions/open-gaps.md), index, tracker.

## [2026-11-17] setup | P7-06 done: binding producers in the self-certification list (gap 24 closed); new gap 36 (P14-16)
- Commit `f6a2024`. New `nts-conform capture`: `--lsl QUERY` (frames + events streams, or a decisions stream), `--ws ws://HOST:PORT/nts` (recording server), `--ws ws://HOST:PORT/decisions` (subscriber); `--received` writes the consumer's view (NTS stream or decision log). Privacy: no host name, uid, address or token in a capture.
- `fidetype.conformance.binding_producers` captures our own outlets on loopback (synthetic ctc-logits stream, two utterances, about 6 s): `replay_to_lsl` + `DecisionOutlet`; `replay_to_ws` + `WSServer` `/decisions`.
- [`certified.json`](../spec/conformance/certified.json): `binding-lsl` (NTS Trust-ready, text, nts-lsl/0.1) and `binding-ws` (NTS Trust-ready, text, nts-ws/0.1); 13 entries. CI job `live`: new step "Binding producer captures (P7-06)".
- Tracker: run stats filled for P14-04, P7-01, P5-09 (shared with P5-10, P5-11), P6-02, P6-08 (P6-02b run), P4-10 (shared with P4-11, P14-11).
- New gap 36 = P14-16: `fidetype live` has no LSL / WebSocket outlet.
- Pages: [conformance suite](concepts/conformance-suite.md#binding-producers-and-nts-conform-capture-p7-06), [roadmap](questions/roadmap-standard.md) (P7-06, P14-16), [open gaps](questions/open-gaps.md), [docs](../docs/conformance.md#record-a-capture-from-a-live-producer-lsl-websocket).

## [2026-11-17] setup | P3-04 done: collector pipeline integration test + latency budget; P7-05 done (gap 23 closed); new gaps 37-41
- Commit `2298e3e`. One TOML file runs a real collector: receiver (WebSocket `/nts`, file, LSL) → `validate` (stream level provenance) → `segment` (new segmenter) → `guard` (new: drop-in guard from a per-user profile, `guard.online("aci")`, passthrough) → `jsonl` NTS stream + decision log + `os_text` stub (new; types only final COMMITs) + WebSocket `/decisions`. `python -m fidetype.collector.bench`; test file `tests/test_collector_pipeline.py`.
- Every run reaches producer level NTS Trust-ready (`nts-conform`, claim text). Latency (new `[service] latency = true`; stages receive / processors / exporters / pipeline / added / e2e), 50 Hz synthetic frames, 12 segments, p95 added: implant-speech 1.1-1.3 ms, emg-key 1.2-2.3 ms (WebSocket, file, LSL): far below the 50 ms budget. implant-logits (the guard's built-in CTC beam search inside the collector): 104-108 ms, reported, not gated.
- CI job `collector`: pipeline tests with the `lsl` extra (gate p95 added < 50 ms x `FIDETYPE_LATENCY_TOLERANCE`, default 1.0), bench report, kit run. No copy of the live runner: the guard processor uses `TrustGuard` and `nbest_of_frames`.
- P7-05: `fidetype-collector consume` (file receiver, now with NPZ, + `validate` at a stream level) reaches consumer level NTS Trust-ready on the kit for `text` (28/36; intent, control and captures not supported); `certified.json` lists `fidetype-collector`.
- Inventory of P3-01 / P3-02 / P3-03 in the tracker notes; all three stay in progress (missing: gRPC, YAML decision, LM rescoring, rate limiter, `meta` privacy filter, real OS input backends, HID bridge, Arrow / Parquet).
- New gaps: 37 = P3-06 (logits guard inside the budget), 38 = P3-07 (LSL receive stamps), 39 = P3-08 (B2T '25 replay through the collector), 40 = P3-09 (YAML: roadmap vs FEP-0006, user decision), 41 = P7-07 (collector consumer for intent, control and captures).
- Pages: [collector](concepts/collector.md), [roadmap](questions/roadmap-standard.md) (P3 status, P3-06 ... P3-09, P7-05, P7-07), [open gaps](questions/open-gaps.md), [docs](../docs/collector.md#integration-test-and-latency-budget-p3-04), tracker.

## [2026-11-17] setup | P14-16 done: `fidetype live --publish` over LSL and WebSocket (gap 36 closed); new gap 42 (P14-17)
- Commit `2fd39fc`. New option `fidetype live --publish TARGET` (repeatable): `lsl` / `lsl:NAME` (frames stream `NAME`, events stream `NAME.events`, decisions stream `NAME.decisions`), `ws://HOST:PORT/nts` (send to a server), `ws://HOST:PORT/decisions` (serve the decisions). `--publish-wait S`, `--publish-linger S`. Code: `src/fidetype/live/publish.py`.
- No new outlet code: `replay_to_lsl` now uses a new `NTSOutlet` class (the same outlets, cut out of the function); `DecisionOutlet`, `WSProducer`, `WSServer` + `OutputHub` reused.
- `trust_decision` events go only on the decisions channel. FEP-0001 section 3 r4 forbids them in an input stream; the first capture failed on this (FEP1-TD-INPUT).
- Evidence: `python -m fidetype.conformance.binding_producers --target live-lsl --target live-ws` runs the CLI (synthetic typist, 4 utterances) in a child process on loopback, about 7 s; both reach NTS Trust-ready with nts-lsl/0.1 and nts-ws/0.1. [`certified.json`](../spec/conformance/certified.json): `fidetype-live-lsl`, `fidetype-live-ws` (16 entries). CI job `live`: new step. Tests: `tests/test_live_publish.py`.
- New gap 42 = P14-17: the `--out` file of `fidetype live` holds `trust_decision` events, so `nts-conform check` gives it no producer level.
- Tracker: run stats filled for R-26 (T15 split audit) and P7-02 (shared with P1-16).
- Pages: [roadmap](questions/roadmap-standard.md) (P14-16, P14-17), [open gaps](questions/open-gaps.md), [docs](../docs/live-decode.md#8a-publish-over-a-binding---publish-p14-16), [conformance docs](../docs/conformance.md), tracker.

## [2026-11-17] setup | P14-15 done (no effect on re-split rows) and P15-20 done; gaps 34, 35 closed; new gaps 44, 45
- P14-15 (pre-registered, `fc8478c`): word-decoder grid re-tuned inside the fit-A of all 200 Paper 1 re-splits and on the 400 tune trials without M4 `val_eval` (and `val_select`) trials. 35 / 200 splits change (28 exact WER ties); rebuilt tables move 0 / 80 primary metrics by their CI half-width -> no effect. T2a picks edit penalty 8 (WER tie); T2b unchanged. [Results](../experiments/2026-11-17-p14-15-retune/results.md).
- Notes added to R3 repeated-splits, R4 split-tables, M4-12, M4-01/02 results pages and to the [T15 split audit](questions/t15-split-audit.md) (also a correction: the published gate uses our word n-best).
- P15-20 (`645dd1b`): halluc-v0.1 T15 split states i = val_eval position (HDF5 val index 2i + 1); `ids_from_rule` + test.
- New gaps 44 = P14-18, 45 = P14-19 in [open gaps](questions/open-gaps.md) and the [roadmap](questions/roadmap-standard.md).

## [2026-11-17] setup | P14-17 done: `fidetype live --out` without trust decisions, decision log `--decisions-out` (gap 42 closed); new gap 46 (P14-20)
- Commit `9de7e61, 1145f2e`. `fidetype live --out S.jsonl` writes a pure NTS input stream. The trust decisions go to a FEP-0001 decision log: new option `--decisions-out FILE`, default `S.decisions.jsonl`, `none` = off. `nts-conform check` on both files gives NTS Trust-ready. Breaking change (0.x), noted in the CHANGELOG.
- Validator disagreement found: `fidetype validate` (the v0.1 suite) read a `trust_decision` line as an unknown event type and ignored it (spec 6.2 rule 5). Only the opt-in `fep-0001` profile tested rule TD-4 (`FEP1-TD-INPUT`); `nts-conform check` runs it, `fidetype validate` does not. The same gap was in `fidetype-ts validate` and `fidetype-rs validate`.
- Fix: new core check `NTS-TD-INPUT` in the v0.1 suite of all three SDKs (`RawStream.td_lines` / `tdLines`), vector V97 (v0.1: 97 vectors, 346 in all), NTS 1.0 RC4 amendment 4 (C.1 row TD-4 names both checks). Cross-check: Python = TypeScript = Rust on every vector.
- `fidetype.live.publish.EventTee` splits the lines (stream file / decision log / publishers); `make_writer(path, ..., decisions=PATH)` does the same for library use. CI replay P14-11 (`tools/ci/kt_lsl_replay.py`) runs `nts-conform check --require-level trust-ready` on both files. `certified.json`: new producer entry `fidetype-live-file`.
- Follow-up `1145f2e`: the first CI run of the new replay failed (live-kt). `nts-conform` runs FEP-0001, and it found a `segment_end` t a fraction before the last frame t (202.31685470750003 < 202.316854708; the writer rounds frame t to 9 decimals; SEG rule 5). `LiveDecoder` now clamps `segment_end` t to the written frame t. Regression test added.
- New gap 46 = P14-20: the streaming validators (`StreamingTrustLayer.push`, TypeScript / Rust `StreamValidator`) still ignore a `trust_decision` in a live input stream.
- Tracker: P14-16 run stats filled (1501 s, 224,996 tokens, 106 tool uses).
- Pages: [roadmap](questions/roadmap-standard.md) (P14-17, P14-20), [open gaps](questions/open-gaps.md), [live decode docs](../docs/live-decode.md#8-what-the-nts-file-holds), [conformance docs](../docs/conformance.md), tracker.

## [2026-11-17] setup | P7-07, P3-07, P3-08 done: collector consumer on the whole kit, LSL receive stamps, B2T '25 replay through the collector (gaps 41, 38, 39 closed); new gap 43 (P3-10)
- Code commit `2984990`; P3-08 results with the records commit.
- P7-07: `validate` runs the FEP-0003 / FEP-0005 rule functions of `fidetype.conformance.profiles` (bounded windows). `fidetype-collector consume` replays LSL captures into the `lsl` receiver and WebSocket captures into the `websocket` receiver's ingest core, and runs the reference binding consumer. Kit 36/36; consumer level NTS Trust-ready for text, intent, control with both bindings; `certified.json` entry and CI step updated.
- P3-07: LSL receive stamp `_fidetype_t_recv` (pull time). The merge window is most of the LSL latency: p95 61.3 ms at 0.05 s (was 1.1 ms without the wait). `LSLEventSource.poll` waits at most until the merge deadline; bench window 0.02 s: p95 26.8 / 22.9 ms. Old and new numbers in [collector docs](../docs/collector.md#lsl-receive-stamps-p3-07). New gap 43 = P3-10.
- P3-08: 120 T15 `val_eval` trials at real time over WebSocket; n-best guard calibrated on `val_select` (null controls pass); p95 added 2.43 ms (budget 50 ms), producer level NTS Trust-ready, 120 OFFER, 0 COMMIT ([results](../experiments/2026-11-17-p3-08-b2t25-collector-replay/results.md)).
- Tracker: P7-06 run stats filled (1787 s, 258,657 tokens, 96 tool uses).
- Pages: [roadmap](questions/roadmap-standard.md) (P3-07, P3-08, P7-07, P3-10), [open gaps](questions/open-gaps.md), [collector concept](concepts/collector.md).

## [2026-11-17] setup | P3-10 and P14-20 done: LSL heartbeat and equal-time order; TD-14 in the streaming validators (gaps 43, 46 closed; NTS 1.0 RC4 amendment 5)
- P3-10: new binding rules LSL-C7 (an empty events-stream sample is a heartbeat; it moves the events watermark) and LSL-C8 (at equal times the frame goes first). `NTSOutlet` sends a heartbeat after each frame and stamps markers with the previous frame's time. At the receiver default window (0.05 s) the collector's LSL p95 added latency is 1.07 ms for implant-speech (was 60.4 ms) and 2.89 ms for emg-key. Vectors L36, L37 in all three SDKs. Binding version unchanged.
- P14-20: rule TD-14: an event-by-event consumer refuses a `trust_decision` inside an input stream (ignored after `end`). Python `StreamingTrustLayer`, TypeScript / Rust `StreamValidator` and the collector `validate` processor agree on the streaming cases S01-S06.
- Code commit `c241726`. Tracker: P14-17 run stats filled (2386 s, 324,608 tokens, 61 tool uses).
- Pages: [roadmap](questions/roadmap-standard.md) (P3-10, P14-20), [open gaps](questions/open-gaps.md), [LSL input](concepts/lsl-input.md). No new gap.

## [2026-11-17] query | M4-13 done: long causal decoder run reaches PER 0.1210 (published 0.101); trust layer now useful
- Plan pre-declared (`01cea4b`): M4-12 recipe, dedicated L 0, causal smoothing, 115,000 steps x 64 (6.97 M trial passes), cosine 5e-3 -> 1e-4. 4-days-per-batch sampling smoke-tested (5.4-6.0 s per step vs 1.33-1.42): not used.
- val_eval (701): greedy PER 0.1210 (M4-12 0.2574), WER 0.1880, sentence exact 0.365. "Close" (<= 0.151): yes. val_select 0.1392 / 0.1252 / 0.1211 / 0.1204 at 25 / 50 / 75 / 100 %.
- Trust, M2-19 config with the M2-18 commit gate (not refitted): 91 commits, 11 wrong (0.0157, CP95 upper 0.0279), eWPM 9.94 (gaze 4.02, always commit 9.90 with 63 % wrong). Controls with the gate: uniform 0/300, frame-shuffled 0/300.
- 2026-11-15 decision in [streaming trust layer](concepts/streaming-trust-layer.md): every trust re-tune enables the commit gate and passes both null controls.
- Pages: [lookahead vs accuracy and latency](questions/lookahead-latency-accuracy.md) (new M4-13 section), [index](index.md). Experiment: [results](../experiments/2026-11-15-m4-13-long-train/results.md).

## [2026-11-17] query | P14-18 / P14-19: word-setting follow-ups (gaps 44, 45 closed)
- Pre-registration `3d07cb4` before any run; one hidden CPU queue 03:50-07:28 (4 threads). Reference runs reproduce every committed M4-12, M4-01/02 and P14-03 number; rebuild code-path checks pass.
- P14-18: with edit penalty 8, 14 of 166 M4 metrics move by their CI half-width, all in favour of edit 8 (M4-12 1/90; M4-01/02 11/72; P14-03 2 wrong commits -> 0). The committed M4 rows are not optimistic. New gap 50 (P14-21).
- P14-19: re-split tables (published gate, guard off; 35 rebuilt splits) no effect (0/240). Forward-chain prefix 0 with edit 8: 9 plug-in rows of "ours" change by their half-width; no day keeps a CP lower bound above alpha; LTT max V3 ours 2/13 -> 1/13, published 1/13 -> 0/13. Downstream: A2 day 34, two formal effects. New gap 51 (P14-22).
- Pages: [T15 split audit](questions/t15-split-audit.md), [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md) (P14-18, P14-19, P14-21, P14-22). Correction notes on 7 results pages and `papers/paper1/correction-2026-11-17-p14-19.md`; no-effect notes on 6. Experiment: [results](../experiments/2026-11-17-p14-18-19-followups/results.md).

## [2026-11-17] setup | P5-03 and P5-04 done: provenance lineage + licence flags; consent refs, privacy processor, deletion; neural-data law table; new gaps 47, 48, 49
- P5-03 (inventory): the M2-09 ledger had the hash chain, `update` entries, `verify`, `report` and an in-memory anchor. Missing: licence flags, lineage from data to weights to calibration to output, a lineage query, an anchor CLI. Built: `fidetype.trust.licence` (SPDX normalisation, flags, product policies `project` / `commercial`); entry kinds `source` and `artifact` (`record_track_source` takes the licence from the benchmark tracks); contexts with `lineage`; each decision carries `research_only` / `commercial_ok` / `product_ok`; a product artifact with NC inputs is refused; `verify` recomputes every flag; `LedgerView.lineage`, `lineage_report`, `record_lineage_spec`; CLI `lineage`, `anchor`, `verify --anchor`; Collector `ledger.lineage`.
- Exit criterion met: B2T '25 subset replay (203 fit / 68 replay trials, CPU, 57 s): full lineage of one committed word, 8 entries (3 sources -> 3 artifacts -> context -> decision), verify PASS; product LM from Tatoeba (CC BY 2.0 FR) refused under the project rule ([experiment](../experiments/2026-11-17-p5-03-lineage/results.md)).
- P5-04: `fidetype.trust.privacy` (`check_consent_ref`, `ConsentRecord`, `PrivacyPolicy` + `DEFAULT_POLICY`, `delete_profile`, `erase` with a receipt); Collector processor `privacy` (keep / drop / hash per `meta` key, PII scan, text drop or HMAC; order check against the trust step); ledger redaction with tombstones under the new default hash rule `salted-body` (old `v0` ledgers still verify); `UserProfile` checks `consent_ref`.
- [Neural-data law table](questions/neural-data-law.md) (not legal advice): instruments checked on the web with P / S / U marks. New finds against the roadmap list: California AB 1883 (workplace, 2026), SB 44 failed, Vermont Acts 101 and 145, Delaware HB 380 verified, UNESCO Recommendation adopted 11 Nov 2025, MIND Act still a bill. Contradiction kept: SB 1223 date (landscape "1 Jan 2026" vs statute 1 Jan 2025).
- New gaps 47 = P5-13 (licence keys in NTS and `trust_decision`, FEP), 48 = P5-14 (signed anchor), 49 = P5-15 (erasure in Collector output files).
- Full pytest: 1374 passed, 11 skipped. Tracker: P3-10 / P14-20 and P7-07 / P3-07 / P3-08 run stats filled.
- Pages: [roadmap](questions/roadmap-standard.md) (P5 deliverables 3-5, exit criterion, P5-13 … P5-15), [open gaps](questions/open-gaps.md), [provenance ledger](concepts/provenance-ledger.md), [landscape](sources/neural-input-landscape-2026.md), [index](index.md); docs [provenance and privacy](../docs/provenance-and-privacy.md), [collector](../docs/collector.md).

## [2026-11-17] setup | Collector decisions: TOML/JSON config (gap 40 = P3-09 closed); Python for collector v1
- The user delegated both decisions to the orchestrator. Record: [collector decisions 2026-11](questions/collector-decisions-2026-11.md).
- Config format: TOML/JSON, as FEP-0006 section 6 says. No YAML. Reasons: a deliberate spec decision; TOML has explicit types (no YAML "Norway problem", no octal / bool coercion); `tomllib` is in the standard library; JSON covers machine-written configs.
- Collector v1 language: Python. The collector, trust layer, adapters and tests exist in Python and meet the latency budget (p95 added about 1–3 ms vs 50 ms). A Rust core can come later for embedded / on-device use (P5-05) if a measured need appears.
- Pages: [roadmap](questions/roadmap-standard.md) (P3 goal, language line, dated decision note, exit criterion, P3 status, P3-09 `done`; edited in place, no item moved), [open gaps](questions/open-gaps.md) (gap 40 closed), [index](index.md). Tracker: P3-01 title + notes, P3-09 `done`. No code change.

## [2026-11-17] setup | P15-15 done: hallucination benchmark protocol 0.2 (paired swapped / real commit rule); gap 4 part closed; new gap 52 = P15-21
- Pre-registration `4e44c23` ([plan](../experiments/2026-11-17-p15-15-halluc-0.2/plan.md)) before any scoring; code `40922c5`.
- Rule: pairs = real item j + swapped item j (same signal). Pass iff the one-sided CP upper bound of Y / m < r / (1 + r), with Y = n01 + n11, m = pairs with any commit, r 0.5, alpha 0.05. Fail if m >= 25 or clear evidence (CP lower bound of n01 / m > 1/3). Otherwise "insufficient evidence" (not a pass). Null / scrambled unchanged.
- Re-score of the 12 committed v0.1 outcome files: 10 change verdict. T15 P14-03 guard, T15 P15-05 B0 and both P15-06 guards: pass -> insufficient evidence. T12 P15-05 B0: pass -> fail. T12 P14-03 guard stays fail. No baseline passes ([results](../experiments/2026-11-17-p15-15-halluc-0.2/results.md)).
- 0.1 scoring kept (`--protocol 0.1`; CI still reproduces the 0.1 cards). New cards in `benchmark/results/halluc-v0.2/`. Docs section 1.1.
- M4-13: no rerun outputs yet; `add_m4_13.py` adds the entries in one command (dry run matches the queue's dry aggregates).
- New gap 52 = P15-21: absolute bound on unsupported swapped commits next to the ratio rule; pair-independence check.

## [2026-11-17] query | M4-13 rows: safe WPM, benchmark v0.2 entry, collector replay, split audit; new gap 53
- Safe WPM (P14-05, `run.py t15-m4-13`, 320 s CPU): T15 val_eval 701, M4-13 + drop-in guard (P14-03 recipe, `tcfg-1016759f08a3f9a1`): 2.23, certified; 104 commits, 17 wrong (0.0243, CP95 [0.0142, 0.0385]); no-BCI 4.02. M4-12 was 0.00. Rows in [P14-05 results](../experiments/2026-11-16-p14-05-safe-wpm/results.md) and `docs/safe-wpm.md` section 5.
- Benchmark v0.2 (`run.py t15-m4-13 score-m4-13 table`, 276 s): `b2t25-t15__m4-13__guard`, partial 103/816 units (val_eval only; card `coverage.partial`, board `[partial: 103/816 units]`): CER 0.067, WER 0.113, eWPM 12.83, safe WPM 4.07 [2.51, 5.74] certified (19 commits, 3 wrong), no-BCI 4.12; controls pass. Static board rebuilt; Pages not published.
- Collector replay (P3-08, `--decoder m4-13`, 120 trials, 2,171 s real time over WebSocket 127.0.0.1): p50 / p95 / p99 added 1.25 / 1.97 / 2.65 ms (PASS vs 50 ms); 16 COMMIT, 104 OFFER, 3 wrong commits; os_text typed only the 16 commits; producer level NTS Trust-ready.
- [T15 split audit](questions/t15-split-audit.md) rerun (`audit.py` now also reads the M4-13 submission): M4-13 val_eval 701 / val_select 722 keys, 0 on train; entry 103 units clean.
- New gap 53 = P14-23: T15 safe WPM above the no-BCI reference with our causal decoder. Gap 50 (P14-21) now also lists these rows (edit-12 word decoder).

## [2026-11-17] setup | P5-14 and P5-15 done: signed ledger anchors; erasure in Collector output files; gaps 48, 49 closed; new gaps 54, 55
- Code `b268203`. P5-14: `fidetype.trust.anchor` (Ed25519, optional extra `[sign]` = `cryptography`, in `[dev]`); CLI `keygen`, `anchor --sign-key-file | --sign-key-env`, `verify --anchor --public-key [--allow-growth]`. A rewritten ledger with a recomputed chain passes the chain check but fails against the signed anchor. RFC 3161 / second host documented as options (no network call).
- P5-15: `fidetype.trust.erasure`; Collector `privacy` option `subject_index` (HMAC codes, never raw ids) and `jsonl` path `{session}`; `erase --output --output-template --subject-index`; receipt `fidetype.deletion-receipt/1.1` with `outputs` (no path, no id). Test: erase one subject from a two-pipeline run; the remaining files pass `nts-conform check` at the same verdict.
- New gaps 54 = P5-16 (Collector writes signed anchors itself), 55 = P5-17 (refuse input-event files that mix streams).
- Tracker: P15-15 agent stats filled (2045.429 s, 219256 tokens, 78 tools).
- Pages: [roadmap](questions/roadmap-standard.md), [open gaps](questions/open-gaps.md), [provenance ledger](concepts/provenance-ledger.md); docs [provenance and privacy](../docs/provenance-and-privacy.md) sections 4.1, 4.2, 8, [collector](../docs/collector.md).

## [2026-11-17] setup | P5-13, P5-16, P5-17 done: data licence keys (FEP-0010, RC4 amendment 6); automatic signed anchors; no mixed-stream input files; gaps 47, 54, 55 closed; new gaps 56, 57
- Code `29d17d0`. P5-13: [FEP-0010](../spec/feps/0010-data-licence-keys.md): `data.licence`, `data.research_only` (MET-12) and `trust_decision.input.research_only` (TD-15). Vectors V98-V100 (351 in all); Python = TypeScript = Rust 351/351, kit 36/36, 28,217 fuzz mutants. Six adapters write the keys; the ledger reads them into `source` entries; the trust layers copy the flag.
- P5-16: `AutoAnchor` and the Collector option `ledger.anchor` write signed anchors every N entries / T seconds / at stop; `verify --anchor <dir>` checks the newest. A rewrite after the last manual anchor fails against the automatic one.
- P5-17: the Collector refuses an input-event `jsonl` file without `{session}` when its pipelines can carry more than one stream.
- New gaps 56 = P5-18 (collector policy for research-only decisions), 57 = P5-19 (advisory check: `data.research_only` agrees with `data.licence`).
- Tracker: P5-14 / P5-15 agent stats filled (1469.213 s, 218411 tokens, 97 tools).
- Pages: [NTS spec](concepts/nts-spec.md), [provenance ledger](concepts/provenance-ledger.md), [roadmap](questions/roadmap-standard.md), [open gaps](questions/open-gaps.md).

## [2026-11-18] query | M4-13 trust reruns written up against the pre-registrations; gaps 2, 3 closed; new gaps 58, 59
- Results `053e329` (pre-registration `97a2fc4`). New page [M4-13 trust reruns](questions/m4-13-trust-reruns.md).
- P5-02 on M4-13: P1-P3 pass at precision target 0.5 (104 / 701 commits, precision 0.837, CP95 [0.751, 0.902]); targets 0.8 / 0.9 / 0.95 infeasible. Gap 3 (P5-08) closed; new gap 58 = P5-20 (precision >= 0.8).
- P15-03a: H1, H4, H5, H6 pass; H2 and H3 fail (worse and time-reversed decoders accepted with the feedback-r0.3 user; refused with the oracle user). H7: PER test agrees on 12 of 16. Gap 1 (P15-13) confirmed and unblocked; stays open.
- F2: Part A S1-S3 pass, S4 fail (fluent-wrong 6 > 2); Part B H1-H4 pass, safe but costly (34 of 142 right commits kept); Part C V1-V3 pass (certified T12 bound, 3 commits), V4 T15 pass, V4 T12 fails as written (`config_id` label only). Gap 2 (P15-14) closed; new gap 59 = P5-21 (stable `config_id`). Note added to the P15-06 results.
- Hallucination benchmark 0.2: M4-13 entries added (16 files); the P15-06 B1 guard is the first entry that passes all tracks (36 real commits, 0 swapped).
- Gap 14 (P15-19) in progress. P15-03: CPU part P15-03a done; GPU part open.
- Pages: [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md), [north star](questions/north-star.md) (F1, F2 result lines), [index](index.md).

## [2026-11-18] setup | P2-08 publishing prep: dry runs, name checks, site build, weekend checklist; new gap 60
- Dry runs pass: Python wheel + sdist (`twine check --strict`, clean-venv install, `fidetype conformance --profile fep-0001` 66/66), `npm pack` / `npm publish --dry-run` (`@fidetype/sdk` 0.1.0, 53 files, 129.5 kB), `cargo publish --dry-run --locked` (crate `fidetype` 0.1.0, 31 files). No e-mail (only `@example.org` fixtures), no secrets, no data files in any package.
- Names free on 2026-11-18 (read-only GETs): PyPI and TestPyPI `fidetype`, npm `@fidetype/sdk` and `fidetype`, crates.io `fidetype`.
- Fixed: author `Zibo Zhang` (pyproject, package.json, Cargo.toml, CITATION.cff); crate `homepage`; absolute links in the SDK READMEs. Release workflow moved to `.github/workflows/release.yml` (manual trigger only); new manual-only `pages.yml`; new `tools/site/build.js` (assembles `_site/`, checks local links). Tests: `tests/test_publishing_metadata.py`.
- New page [docs/publishing-checklist.md](../docs/publishing-checklist.md): accounts, trusted publishing, commands, checks, rollback, minutes per step, decisions D1-D9. New gap 60 = [P2-09](questions/roadmap-standard.md#p2-09-ci-matrix-python-313-and-windows-and-macos-for-the-three-sdks).

## [2026-11-18] setup | P5-18 + P5-19: collector refuse_research_only; advisory check NTS-LICENCE-MATCH (RC4 amendment 7); new gap 61
- P5-18 (gap 56 closed, FEP-0010 LIC-3): exporter option `refuse_research_only` (+ `unknown_licence`, default `"refuse"`) on every exporter; FEP-0006 section 4 rule 6. A CC-BY-NC stream types nothing through `os_text`; a CC0 stream types as before. Code `9bccef8`.
- P5-19 (gap 57 closed, FEP-0010 LIC-2): advisory `NTS-LICENCE-MATCH` (MET-12) in Python, TypeScript, Rust; vectors V101-V104 (355); parity 355/355, kit 36/36, 28,487 fuzz mutants, 0 differences.
- New gap 61 = [P5-22](questions/roadmap-standard.md#p5-22-licence-gate-for-input-event-exporters) (licence gate for input-event exporters).
- Pages: [nts-spec](concepts/nts-spec.md), [collector](concepts/collector.md), [conformance suite](concepts/conformance-suite.md), [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md).

## [2026-11-18] setup | P15-13 default-deny update gate (code + pre-registered replay launched); P5-21 stable trust config_id done (gap 59 closed)
- P15-13 (gap 1, now in progress): `GuardedUpdateLoop` default `challenger_test="noninferiority"`: the challenger must show it is not materially worse; a pair with unknown truth counts as worse unless the texts are equal, the challenger is right or the champion is known wrong; top-1 + CER tie-break; exact one-sided tests at 0.05 with margins 0.1 / 0.1. `challenger_test="sign"` = old behaviour (same records and loop ids). `TrustGuardUpdater` takes unknown truth (`None`) and `check_rejected`. Code `e788029`.
- P15-13 replay of P15-03a with both users, 2 seeds, plus a weak-champion probe: pre-registered in `e788029` ([plan](../experiments/2026-11-18-p15-13-gate-fix/plan.md)); plumbing dry run passed (M4-12 only, labels meaningless); real run detached since 10:02.
- P5-21 (gap 59, closed): the recipe field `decoder` drops the module path; `decoder_id = <name>@<version>` enters the hash; `decoder_label="module"` reproduces old ids (CHANGELOG notes the id bump).

## [2026-11-18] query | P14-21: downstream T15 rows with word-decoder edit penalty 8 (gap 50 closed); new gaps 62, 63
- Pre-registration `095150c` ([plan](../experiments/2026-11-17-p14-21-edit8-rows/plan.md)), [results](../experiments/2026-11-17-p14-21-edit8-rows/results.md). Rows: P14-05 safe WPM (M4-13, M4-12), M4-13 eval trust rows, M2-19, v0.2 partial entries, P5-02 T15, P3-08 replays; edit-12 references first.
- Effect on 11 of 71 decided metrics (trust commit counts): M4-13 eval with frozen M2-19 configs 91 -> 12 commits; M2-19 refit 9 -> 21-28 commits, all under alpha; P5-02 base can-commit 673 -> 0. No effect: M4-13 safe WPM 2.23 -> 2.28 (still below no-BCI 4.02), v0.2 entries.
- P3-08 reference replay cut by machine sleep: R6 not used. Comparator fix before the write-up (a 0 -> 0 change is never an effect).
- Dated notes on the P14-05, M4-13, M2-19, P6-02b, P5-02 and P3-08 results pages. New gaps 62 = [P14-24](questions/roadmap-standard.md#p14-24-f2-and-m4-13-trust-rerun-rows-with-word-decoder-edit-penalty-8), 63 = [P14-25](questions/roadmap-standard.md#p14-25-p3-08-collector-replays-with-edit-penalty-8-and-a-keep-awake). Pages: [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md).

## [2026-11-18] setup | P2-09: CI matrix on Linux, Windows and macOS; gap 60 closed; new gaps 64, 65
- `.github/workflows/tests.yml`: full pytest suite on Linux 3.12 / 3.13 / 3.14 and Windows 3.12 / 3.13; job `conformance-os` (Windows 3.12, macOS 3.13): Python wheel smoke test + conformance + kit, TypeScript `npm run ci`, Rust `cargo test` + conformance; the macOS job also runs the full suite (one macOS job per push: GitHub macOS capacity). Job `all-green`. Green run 44369685042.
- Platform bugs fixed: live model assets CRLF on Windows (pinned SHA-256; `.gitattributes`), GuardScore NaN equality on Python 3.13+ (tests), macOS timing bounds (`FIDETYPE_LATENCY_TOLERANCE`), reopener timing test.
- Classifiers 3.12, 3.13, 3.14; `requires-python` unchanged. [Publishing checklist](../docs/publishing-checklist.md) D9 updated.
- New gaps 64 = [P2-10](questions/roadmap-standard.md#p2-10-python-315-in-the-ci-matrix) (Python 3.15), 65 = [P2-11](questions/roadmap-standard.md#p2-11-required-status-check-on-main) (required check, owner). Pages: [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md).

## [2026-11-18] setup | P5-22: licence gate for input-event exporters (gap 61 closed)
- Code `a38fe87`. `refuse_research_only` on a `jsonl` / `stdout` exporter of input events judges each stream by its header (`data.licence`, `data.research_only`) and drops a refused stream whole; the P5-18 `unknown_licence` rule; four new counters; a refused stream writes no file.
- Decision with reasons: FEP-0010 decision 6; FEP-0006 section 4 rule 6 (the P5-18 config error for this case is gone). Docs: collector, provenance and privacy, example config, spec CHANGELOG, [collector](concepts/collector.md).
- Test: CC-BY-NC stream writes no file, CC0 stream writes byte-identical files, unknown both ways, three-stream pipeline. Full pytest 1519 passed, 11 skipped. No new gap.

## [2026-11-18] query | P14-23: safe WPM bottleneck on T15 (decomposition + levers, exploratory); new gaps 66-70
- New page [safe WPM bottleneck](questions/safe-wpm-bottleneck.md). Offline on existing outputs only (M4-13 log-probs, P15-05 10-best and LLM caches, P14-05 guard); replayed guard = committed P14-05 decisions 701 / 701. CPU, no GPU, no LLM run.
- Decomposition (val_eval): P(top-1 exact) 0.367, commit rate 0.148, error among commits 0.163, guard commits 87 of 257 exactly-right sentences; 21.42 -> x 0.338 (decoder) -> 7.23 -> x 0.319 (guard) -> 2.31 -> penalty -> 2.23. Trial window 18.7 s vs 12.1 s active speech (speech time: 3.37).
- Levers (LTT on 271 val_select items; same-split plain guard 2.77): learned confidence 3.50 (no LLM) / 4.54 (LLM features); committed P15-05 arms B1 / C1 / D1 4.18 / 4.69 / 4.77; learned prefix commits about 5.4 (needs metric v0.2); decoder alone needs PER about 0.072; centred smoothing at most +0.7.
- P14-23 now `in_progress`. New gaps 66 = [P14-26](questions/roadmap-standard.md#p14-26-safe-wpm-v02-proposal-prefix-credit-and-a-speech-time-field), 67 = [P5-23](questions/roadmap-standard.md#p5-23-learned-commit-confidence-score-for-the-drop-in-guard), 68 = [P5-24](questions/roadmap-standard.md#p5-24-certified-prefix-commits-in-the-trust-guard), 69 = [P15-22](questions/roadmap-standard.md#p15-22-llm-rescoring-with-learned-and-prefix-confidence-for-safe-wpm), 70 = [P14-27](questions/roadmap-standard.md#p14-27-cost-of-causal-smoothing-on-t15-and-the-decoder-accuracy-target). Pages: [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md), [index](index.md).

## [2026-11-18] query | P15-13 replay results: default-deny gate passes G1-G6; gap 1 closed; new gaps 71, 72
- Pre-registered replay of P15-03a on M4-13 (plan `e788029`, [results](../experiments/2026-11-18-p15-13-gate-fix/results.md)): broken decoder refused 4 / 4 and 4 / 4 against the weak champion (old sign test: accepted 2 / 2 with feedback-r0.3, 2 vs 0, p 0.25); worse M4-12 refused 12 / 12; better M4-13 accepted 4 / 4 (feedback-r0.3 p 0.038, 0.026); phase-C wrong-commit 0.0082-0.0110; ledgers verify. Feedback-r0.3 users now get 28-29 commits (P15-03a: 10-11).
- Gap 1 (P15-13) closed. New gaps 71 = P15-23 (challenger without champion outputs skips the test), 72 = P15-24 (1 of 8 same-decoder re-calibrations refused).

## [2026-11-18] query | P5-23: learned commit-confidence score for the drop-in guard (pre-registered); gap 67 closed; new gaps 73, 74
- Code + pre-registration `52ef14c` ([plan](../experiments/2026-11-18-p5-23-learned-confidence/plan.md)): `calibrate(confidence="learned")`, module `fidetype.trust.commit_score` (13 fixed features, L2 logistic regression, fit-range clipping, sign constraints); three-way split (score fit on fit + policy-grid items, LTT on the disjoint LTT items, evaluation set untouched); score in the config id, guard file and sheets. Full pytest 1529 passed.
- [Results](../experiments/2026-11-18-p5-23-learned-confidence/results.md): T15 val_eval 701 (primary) learned 2.64 vs p_top1 2.23, +0.42 [0.07, 0.78] = **learned beats current** (113 commits / 10 wrong vs 104 / 17). T12 400 (replication) 1.87 vs 1.27, +0.60 [-0.18, 1.40] = no clear difference. Controls 0/300 everywhere.
- P14-23 stays open (2.64 < 4.02); notes on the [bottleneck page](questions/safe-wpm-bottleneck.md), roadmap and open gaps. New gaps 73 = [P5-25](questions/roadmap-standard.md#p5-25-online-re-calibration-for-a-guard-with-a-learned-commit-score), 74 = [P5-26](questions/roadmap-standard.md#p5-26-learned-commit-score-with-the-precision-and-hallucination-bounds).

## [2026-11-18] query | P14-26 safe-wpm v0.2 proposal + P5-24 certified prefix commits (pre-registered); gaps 66, 68 closed; new gaps 75, 76
- Code + pre-registration `00a64ba`: [safe-wpm v0.2 proposal](../docs/safe-wpm-v0.2-proposal.md) (PROPOSED, NOT ADOPTED; the user decides): prefix credit, wrong-prefix penalty, risk `wrong-prefix-commit`, optional speech time; `safe_wpm(metric_version="0.2")`, CLI `--metric-version 0.2`; v0.1 default and numbers unchanged. `calibrate(confidence="learned", commit_unit="prefix")`: longest certified word prefix, monotone learned prefix score, LTT on the disjoint LTT items.
- [Results](../experiments/2026-11-18-p5-24-prefix-commits/results.md), proposed v0.2: T15 val_eval 701 prefix 4.87 [4.43, 5.30] vs sentence (learned) 2.64, +2.22 [1.84, 2.59] = **prefix beats sentence** (465 commits / 13 wrong; controls pass). T12 400: 4.76 vs 1.87, prefix beats sentence. v0.1 for the same prefix guard: 0.53 literal (above alpha), 1.03 complete-only.
- P14-23 stays open (v0.2 not adopted; no v0.1 value above 4.02). Notes on the [bottleneck page](questions/safe-wpm-bottleneck.md), docs/safe-wpm.md 6a, roadmap, open gaps. New gaps 75 = [P14-28](questions/roadmap-standard.md#p14-28-reading-cost-and-short-prefixes-in-safe-wpm-v02), 76 = [P5-27](questions/roadmap-standard.md#p5-27-word-by-word-streaming-prefix-commits-within-a-trial).

## [2026-11-18] query | P15-23 done (gap 71 closed); P15-24 re-calibration rule pre-registered, replay running
- Code `0254ebc`: the default-deny gate refuses a challenger without champion outputs (opt-out `allow_missing_champion=True`, recorded; `challenger_test="sign"` keeps P15-02). Gap 71 = [P15-23](questions/roadmap-standard.md#p15-23-update-gate-refuses-a-challenger-without-champion-outputs) closed.
- Same code: same-decoder re-calibration rule (`new_version(kind="recalibration")`, `recalibration_rule="absolute"`): identical top-1, or `P(Bin(N, 0.1) <= w) <= 0.05` (N = 48: at most 1 worse item). Its null hypothesis contains the decoder rule's, so the gate guarantee holds for every proposal. `TrustGuardUpdater` sets the kind only without champion inputs and with `same_decoder`; `PersonalTrust` keeps the live decoder identity.
- Pre-registered replay of the P15-13 design ([plan](../experiments/2026-11-18-p15-24-recal-rule/plan.md)); dry run passed (plumbing); main run detached. Gap 72 = [P15-24](questions/roadmap-standard.md#p15-24-same-decoder-re-calibrations-under-the-default-deny-gate) `in_progress`. Pages: [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md).

## [2026-11-18] query | P14-28: reading cost per commit and short prefixes in proposed safe-wpm v0.2 (pre-registered sensitivity); gap 75 closed; new gap 77
- Scorer options + pre-registration `691d743`: `safe_wpm(metric_version="0.2", read_s_per_commit=, read_s_per_word=, min_prefix_words=)`, CLI flags; defaults change no published value; refused with v0.1.
- Literature values ([proposal section 6.2](../docs/safe-wpm-v0.2-proposal.md#6-reading-cost-p14-28)): KLM mental operator 1.35 s (Card, Moran & Newell); silent reading 238 wpm = 0.252 s/word (Brysbaert 2019); `aac-gaze-v1` verify 0.5 s + 0.3 s/word; Trnka et al. 2008 prediction overhead 0.33-0.69 s per keystroke; Chitnis et al. 2024 about 21 ms per suggestion; Koester & Levine 1994 / 1996 seconds not obtained (marked uncertain).
- [Results](../experiments/2026-11-18-p14-28-reading-cost/results.md) (SENSITIVITY: fixed P5-24 decisions re-scored): T15 prefix 4.87 → 4.67 [4.26, 5.07] at `aac-gaze-v1`, 4.55 at KLM M + reading; break-even 5.99 s per commit (m = 1), 0.58 s (m = 2); m = 2 at 0 s gives 4.07. Prefix still beats sentence (+2.07 [1.70, 2.43]). T12 4.51 [3.66, 5.42], break-even 2.78 s.
- Recommendation in the proposal: adopt v0.2 together with 0.5 s + 0.3 s/word per commit; keep m = 1. P14-23 stays open. New gap 77 = [P14-29](questions/roadmap-standard.md#p14-29-measured-checking-time-per-commit-for-aac-and-bci-users). Pages: [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md), [bottleneck](questions/safe-wpm-bottleneck.md), docs/safe-wpm.md 6a.

## [2026-11-18] query | P15-12: frontier result write-ups (E2, F1 online, E3, decoder quality, safe WPM, personalisation); E1 not run
- Six new write-up pages (docs only, from committed results; no runs): [E2 self-teaching](questions/frontier-e2-self-teaching.md), [F1 online guarantees](questions/frontier-f1-online-guarantees.md), [E3 hallucination](questions/frontier-e3-hallucination.md), [decoder quality](questions/frontier-decoder-quality.md), [safe WPM](questions/frontier-safe-wpm.md), [personalisation and drift](questions/frontier-personalisation-drift.md). Each: question, pre-registration + commit, design, every pre-registered verdict with numbers, negative results, library changes, limits, open gaps, rerun pointers.
- Key verdicts: P15-01 S5 fail -> P15-02 pass; P15-03a H2, H3 fail -> P15-13 G1-G6 pass; P15-05 S4 fails on M4-12 and M4-13; M4-13 P15-06 guard first pass of all hallucination tracks (0.2); M4-12 "close" rule fail, M4-13 pass; safe WPM v0.1 best 2.64 < 4.02, v0.2 (proposed, not adopted) 4.87 / 4.67; P5-09 S3 fail.
- P15-24 replay still running (no numbers reported). E1 (P15-08) not run.
- Summary table in [north star](questions/north-star.md#frontier-result-write-ups-p15-12-2026-11-18); frontier paragraph in [overview](overview.md) (replaces the stale "no results yet" line); index rows. P15-12 `in_progress`: left E1 (P15-08), P15-03 GPU runs, P15-24 verdict.

## [2026-11-18] query | P13-01: benchmark hub design (versioned dataset registry + replay adapters)
- Design doc [docs/hub-design.md](../docs/hub-design.md); summary and open questions on [hub design](questions/hub-design.md); [diagram 18](diagrams/index.html) (`18-hub-design.drawio`, slides.json, build run).
- Registry `src/fidetype/benchmark/hub/datasets-0.1.json` (schema `fidetype.hub.dataset/0.1`): SpanishBCBL (MEG, research only), Brain-to-Text '25 (implant, CC0; pkl + HDF5 forms marked `same_units`), Toronto sEMG (EMG, CC BY 4.0). Metadata only; the checker refuses re-hosting. Checker `python -m fidetype.benchmark.hub`; `tests/test_hub_registry.py` (3 tests, pass; full suite not run: low RAM).
- Replay contract RA-1 … RA-10 (reuses the adapters and `replay-to-lsl` / `replay-to-ws`), rerun recipe + levels, versioning table (dataset / revision / split / scorer / metric), dataset governance; outlines of P13-02 and P13-03.
- Seven open questions for the user (Q1 EMG dataset, Q2 truth for CI scoring, Q3 outputs outside git, Q4-Q7). P13-01 done. New gaps 78 = [P13-06](questions/roadmap-standard.md#p13-06-hub-command-line-and-rerun-recipe), 79 = [P13-07](questions/roadmap-standard.md#p13-07-registry-entries-for-the-other-v02-datasets-and-missing-checksums). [Open benchmark](concepts/open-benchmark.md) and index updated.

## [2026-11-18] query | P15-24 results: same-decoder re-calibration rule passes R1-R7; gap 72 closed
- Pre-registered replay of the P15-13 design on M4-13 (plan `0254ebc`, [results](../experiments/2026-11-18-p15-24-recal-rule/results.md)): re-calibrations refused 0 of 8 (P15-13: 1 of 8; s1 oracle B6 now passes at p_abs 0.040); broken decoder refused 4 / 4 and 4 / 4 against the weak champion; worse M4-12 refused 12 / 12; all 20 refused proposals also refused by the re-calibration rule; phase-C wrong-commit 0.0082; ledgers verify.
- Gap 72 = [P15-24](questions/roadmap-standard.md#p15-24-same-decoder-re-calibrations-under-the-default-deny-gate) closed; no new gap. Pages: [E2 write-up](questions/frontier-e2-self-teaching.md), [personalisation write-up](questions/frontier-personalisation-drift.md), [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md).

## [2026-11-18] query | P13-08: hub questions decided; project site built locally (not published)
- The user answered the hub questions: "i would like to have a site but the rest you can decide". Q1-Q7 decided ([docs/hub-design.md, Decisions](../docs/hub-design.md#decisions-2026-11-18); [hub design](questions/hub-design.md)): Q1 Toronto sEMG; Q2 private truth store for CC0 / CC BY tracks, maintainer scores research-only tracks (P13-03); Q3 outputs outside git (pointer + SHA-256); Q4 separate research-only section; Q5 `rescore`-only entries may rank, level shown; Q6 a project site; Q7 founder now, second reviewer later.
- Site: `tools/site/build.js` rewritten + `tools/site/md.js` (no dependencies). Every page comes from a repo file: landing from `README.md`, benchmark overview from the tracks v0.2 split files and `leaderboard.json` (safe WPM v0.2 marked PROPOSED from its status line), hub page from `datasets-0.1.json`, certified list from `certified.json`, docs and spec rendered from Markdown with GitHub heading ids. Static, no external requests, dark mode, phone width; checked with headless Edge; local links all OK. Built into `_site/` only; NOT published (publishing weekend 2026-11-21/22; [checklist](../docs/publishing-checklist.md) section G).
- Fixed a table cell with an unescaped pipe in docs/trust-personalisation.md. New gap 80 = [P13-09](questions/roadmap-standard.md#p13-09-per-track-leaderboard-pages-with-stable-anchors-and-history) (per-track leaderboard pages with anchors and history).
- CI run 44437999699 (commit `747f2ea`): one macOS failure in `tests/test_live_reconnect.py` (timing; passes on Linux and Windows). New gap 81 = [P4-14](questions/roadmap-standard.md#p4-14-flaky-reconnect-test-on-the-macos-runner).

## [2026-11-18] setup | README "Where we are going" status refresh; P13-08 and P15-24 agent stats
- `README.md`: replaced the stale line "We have no results for them yet" with a status table per pillar (F1, F2, F3): first results and what is not run yet, with links to the [P15-12 write-ups](questions/north-star.md#frontier-result-write-ups-p15-12-2026-11-18) and the [P15-24 results](../experiments/2026-11-18-p15-24-recal-rule/results.md). It says that these are pre-registered replays on public offline data, not user studies, that E3 fails S4, that E1 (F3) is not run, and that safe WPM v0.2 is PROPOSED. Roadmap row: phases P1-P16 (was P1-P13).
- [North star](questions/north-star.md): the E2 status row no longer says "P15-24 replay running" (done, R1-R7 pass).
- Site rebuilt locally (`node tools/site/build.js`: local links all OK; not published); `tests/test_publishing_metadata.py` 15 passed.
- Tracker: P13-08 agent run filled (1931.95 s, 229,242 tokens, 101 tool uses); P15-24 "P15-23 + P15-24 agent" run filled with the resumed-run total (1596.46 s, 300,129 tokens, 26 tool uses; includes the resumed write-up). No new gap.

## [2026-11-18] setup | P4-14: flaky macOS reconnect test fixed at the root (gap 81 closed)
- Root cause (CI run 44437999699, `tries["n"] == 3`): a check-then-act race, not a slow runner. After a `take()` that returned None, the reconnect loops of `LSLSource` and `LSLEventSource` called `_Reconnector.done()` twice. A worker that set its inlet and ended between the two calls looked like "ended, no inlet": the loop started a second worker, called `reopen()` once more and never took the first inlet (a leak with real pylsl).
- Fix (code `efa56f5`): `_Reconnector.take_or_ended()` reads `done()` once, before the last `take()`; both loops use it. The test bound stays `== 2`. New deterministic tests replay the race with a scripted fake worker (no thread, no sleep) at 5 schedule points; the old code fails 2 of 5. `EventTee.flush()` now skips closed files (the "I/O operation on closed file" log errors of the same run).
- Local stability: 19 full runs in a row of `tests/test_live*.py` + the LSL adapter, collector and demo-live tests, 141 passed each, idle priority (30 planned; stopped at 19 because memory ran low next to GPU training).
- Records: gap 81 closed in [open gaps](questions/open-gaps.md); [P4-14](questions/roadmap-standard.md#p4-14-flaky-reconnect-test-on-the-macos-runner) `done` (the "20 macOS runs" check is replaced by the deterministic schedule test); tracker + dashboard. No new gap.

## [2026-11-18] setup | P13-06: hub command line and rerun recipes (gap 78 closed)
- Code `81df2af`: `python -m fidetype.benchmark.hub` / `fidetype hub` with `list`, `show`, `instructions` (official source only; the hub never downloads or re-hosts data), `verify` (size + SHA-256 of local files), `check` (registry or one entry), `recipe` and `rerun` (level `rescore`). Design: [docs/hub-design.md section 12](../docs/hub-design.md#12-hub-command-line-and-rerun-recipes-p13-06).
- Rerun recipe `fidetype.hub.recipe/0.1` in every score card: dataset id / version / revision, track + split digest, adapter source SHA-256 (RA-9, LF line ends), decoder, policy, scorer and metric versions, exact commands with `<placeholders>`. The scorer adds it to new cards; `tools/benchmark/add_rerun_recipes.py` backfilled the 52 committed cards (no other field changed).
- Leaderboard: `Rerun` column and a "Rerun recipes" block per track; site rebuilt locally (link check OK), not published.
- `fidetype hub rerun` gave byte-identical cards (without the `rerun` block) for `b2t25-t15__published__ltt`, `b2t24-t12__t12v2__guard`, `toronto-semg__cnn-calib__crc`. Tests: `tests/test_hub_cli.py` (11); related test files 44 passed. CI run 44477148498 for the code commit (check: gh run list --limit 3). Verdict (added 2026-11-18 by P13-09): CI run 44477148498 (`81df2af`) and CI run 44477602801 (records commit `46eaf7a`) both passed (success).
- Records: gap 78 closed in [open gaps](questions/open-gaps.md); [P13-06](questions/roadmap-standard.md#p13-06-hub-command-line-and-rerun-recipe) `done`; new gaps 82 = [P13-10](questions/roadmap-standard.md#p13-10-hub-replay-command-unit-key-transport-test-and-replay-level-rerun), 83 = [P13-11](questions/roadmap-standard.md#p13-11-complete-rerun-recipes-weights-hash-policy-config-id-hallucination-cards). Tracker: P4-14 agent stats filled.
- Records commit also fixes the 21 v0.1 recipes: split digest = SHA-256 of the v0.1 split file (`digest_kind: file-sha256`), scorer `benchmark-0.1` (they were null in `81df2af`); `code_ref` kept.

## [2026-11-18] setup | P13-09: per-track leaderboard pages with stable anchors and entry history (gap 80 closed)
- The leaderboard generator (`python -m fidetype.benchmark leaderboard`) now also writes `benchmark/site/tracks/<track>.html` (10 track pages) and `benchmark/site/history.json`. Stable anchors: `index.html#track-<track>`, `tracks/<track>.html#e-<card file name>`, `#entries`, `#history`, `#details`.
- Entry history from git (new module `src/fidetype/benchmark/entry_history.py`, schema `fidetype.benchmark.history/0.1`): for each commit that added or changed a card (`git log --no-renames`; `--follow` reported new v0.2 cards as copies of v0.1 cards), the card at that commit gives the date, commit, changed top-level fields, split version + digest, scorer and metric versions, rerun level, eWPM and safe WPM. Working-tree rows, removed cards; no history without git or in a shallow clone (the page says so).
- Main leaderboard: sections v0.2 clean / research-only (separate, marked) / v0.1; track headings are `h3` with ids and link to the track pages; each decoder cell links to its entry. Safe WPM v0.2 marked PROPOSED on every track page.
- Site (`tools/site/build.js`): track pages at `benchmark/tracks/` (back link to `leaderboard.html`, PROPOSED bar), the benchmark overview links each track row, `history.json` copied. Local link check OK. NOT published. Headless Edge screenshots at 1280 px and 390 px, light and dark.
- Tests: `tests/test_leaderboard_track_pages.py` (12; fake git and a real temporary git repository; committed pages equal a regeneration from the cards + `history.json`).
- Records: gap 80 closed in [open gaps](questions/open-gaps.md); [P13-09](questions/roadmap-standard.md#p13-09-per-track-leaderboard-pages-with-stable-anchors-and-history) `done`; new gap 84 = [P13-12](questions/roadmap-standard.md#p13-12-leaderboard-freshness-check-and-same-commit-history-rows) (CI freshness check, same-commit history rows). Tracker: P13-06 agent stats filled (2417 s, 267544 tokens, 123 tool uses); CI runs 44477148498 and 44477602801 of P13-06: success.

## [2026-11-19] setup | P13-11 + P13-12: recipe values or reasons, hallucination recipes, leaderboard freshness check (gaps 83, 84 closed)
- Code `a7f0b6b` (fix `7b6cdd7`): rerun recipes hold a value or a reason for `decoder.weights_sha256` and `policy.config_id`; `check_recipe` accepts exactly one ([design 12.6](../docs/hub-design.md#126-weights-hash-config-id-and-hallucination-recipes-p13-11)).
- 52 leaderboard cards: weights SHA-256 30 filled / 22 reasons; `config_id` 6 filled (every guard card) / 46 reasons (16 always-commit, 30 TrustPipeline fits never frozen). Weights hashed read only outside the repo; T12 v2, M4-12 and M4-13 hashes match the pre-registration and decode records.
- 32 hallucination cards: level-`rescore` recipes from the committed outcomes files; all 32 commands reproduce their card. `rescore --check` ignores the `rerun` block and compares floats with a tolerance (Linux CI gave other last bits: fix `7b6cdd7`).
- Only the `rerun` block changed: key-by-key check against `HEAD` (84 cards).
- P13-12: entry history read up to the parent of the commit that holds the pages; a card committed with its pages gets a "this commit / with this page" row. `python -m fidetype.benchmark.leaderboard --check` in the new CI job `leaderboard` (`fetch-depth: 0`, in `all-green`) ([design 12.7](../docs/hub-design.md#127-leaderboard-freshness-check-p13-12)). Site regenerated.
- Records: gaps 83 and 84 closed in [open gaps](questions/open-gaps.md); [P13-11](questions/roadmap-standard.md#p13-11-complete-rerun-recipes-weights-hash-policy-config-id-hallucination-cards) and [P13-12](questions/roadmap-standard.md#p13-12-leaderboard-freshness-check-and-same-commit-history-rows) `done`; new gap 85 = [P13-13](questions/roadmap-standard.md#p13-13-frozen-trust-configs-for-the-pre-p5-23-trust-cards). Tracker: P13-09 agent run filled (1687.99 s, 188,391 tokens, 78 tool uses).

## [2026-11-19] setup | P11-01: emg2qwerty causal CTC decoder written up (S1 pass, S1+ fail; gaps 86-90)
- Results: [results.md](../experiments/2026-11-16-p11-01-emg-decoder/results.md), aggregates [results.json](../experiments/2026-11-16-p11-01-emg-decoder/results/results.json). Training 2026-11-17 17:33 to 2026-11-19 00:22 on one GPU; pause at step 26010 and resume checked clean (same step, LR and loss continuous, 0 skipped).
- Test, greedy CTC, no LM, our 8-user split: personalised CER 15.09 % mean over users (pooled 15.15 %), generic 53.52 % (pooled 53.75 %), time-shuffled 0.986, emission delay median 70 ms / p90 110 ms, 2,445 / 2,445 NTS streams `trust-ready`.
- Pre-registered: S1, S2, S3 (8/8), C1, N1, L1 pass; S1+ (<= 11.28 %) fails. Published Table 3 (no LM / LM): generic 55.38 / 51.78, fine-tuned 11.28 / 6.95. Conditions differ (no LM, greedy, own splits, no lookahead, 12 bands).
- Generic model best at step 30,000 of 150,000, then overfits. No emg2qwerty benchmark entry: generic saw 96 of 104 track test sessions; no keycode units writer; no trust config (P14-13, P14-10 updated).
- Wiki: [emg2qwerty](entities/emg2qwerty.md) continuous-decoder section, [frontier decoder quality](questions/frontier-decoder-quality.md) EMG section, [index](index.md).
- Records: P11-01 `done`; new gaps 86-90 = [P11-06](questions/roadmap-standard.md#p11-06-licence-clean-causal-convctc-on-kt-semg-and-toronto) (licence-clean decoder, the other half of P11-01), [P11-07](questions/roadmap-standard.md#p11-07-ctc-beam-search-with-a-character-lm-for-the-emg-decoder) (LM + beam), [P11-08](questions/roadmap-standard.md#p11-08-emg-decoder-accuracy-to-the-published-fine-tuned-no-lm-cer) (accuracy), [P11-09](questions/roadmap-standard.md#p11-09-trust-config-and-streaming-replay-for-the-p11-01-emg-streams) (trust config + streaming replay), [P11-10](questions/roadmap-standard.md#p11-10-ingest-the-emg2qwerty-paper-as-a-wiki-source-page) (paper ingest). Tracker: P13-11/12 agent run filled (34420.394 s, 304,592 tokens, 135 tool uses; wall time includes a machine sleep).

## [2026-11-19] setup | P15-08 E1a: cross-body pretraining -> minutes of data on a new sensor (pre-registered, launched)
- Plan frozen before any result: [plan.md](../experiments/2026-11-19-p15-08-e1-cross-body/plan.md) (`60620ab`). Code `75c92a6` (12 CPU tests pass; GPU dry run in a scratch folder).
- Target: Willett handwriting (CC0, implant; new sensor + new user). Shared output space: the P11-01 98-token character head. Arms R random, T text-only (synthetic key renderings), E P11-01 EMG trunk, S shuffled-weight control; budgets 3, 10, 30, 100 min and all (506 min); 2 seeds; final-step test CER, greedy, no LM.
- Rules: V1 gate (best CER at all <= 0.50); H1 primary = E beats T at >= 2 of {3, 10, 30} min (delta > seed spread and paired bootstrap CI95 > 0); H2 E vs R; H3 T vs R; H4 E vs S; C1 time-shuffle; C2 label-shuffle.
- GPU run launched 2026-11-19 10:28, detached, about 10 h; check / stop / resume in [HANDOFF](../HANDOFF.md). Records: P15-08 `in_progress`; new gap 91 = [P15-25](questions/roadmap-standard.md#p15-25-e1-readout-with-the-same-character-lm) (same-LM readout).

## [2026-11-19] setup | P5-27: streaming word-by-word prefix commits (pre-registered; single beats stream; gap 76 closed, new gap 92)
- Pre-registration + code `5f74c2f` (plan, `fidetype.trust.stream_commit`, `stream-prefix` score, `safe_wpm(..., n_commits=)`, proposal section 7, trust-guarantee 10c); results `72be974`: [results](../experiments/2026-11-18-p5-27-streaming-prefix/results.md).
- T15 val_eval 701 under the PROPOSED v0.2 + reading cost + several-commits rule: stream 2.34 [2.11, 2.57] (certified, 5 / 701 wrong) vs one-commit prefix guard 4.67 [4.26, 5.07]; Δ −2.32 [−2.63, −2.02]: **single beats stream**. Right words about 10 s earlier (median 1.44 s vs 11.20 s).
- Updated [frontier safe-WPM page](questions/frontier-safe-wpm.md), [open gaps](questions/open-gaps.md) (76 closed, 92 = P5-28 added), [roadmap](questions/roadmap-standard.md), tracker, index. v0.1 stays adopted; nothing published.

## [2026-11-19] setup | P15-22: LLM rescoring + learned commit confidence (pre-registered; 4.91 safe WPM v0.1 > 4.02; gaps 69 and 53 closed, new gaps 93-94)
- Pre-registration `7557b54`, code `9643804` (run.py + launch.py; full pytest 1619 passed, 11 skipped); results: [results](../experiments/2026-11-19-p15-22-llm-learned/results.md).
- T15 val_eval 701, CPU, cache-only decisions: P15-05 B1 + learned score = **4.91 [4.25, 5.57]** safe WPM v0.1, certified (196 / 13 wrong; controls 0 / 300). H1 vs P5-23 learned +2.27 [1.76, 2.81] and H2 vs the LLM arm alone (4.18) +0.73 [0.19, 1.27]: both **L1 beats**. Closes P14-23 (gap 53). Prefix arm (v0.2, proposed): 7.14; 6.75 with reading cost. Hallucination protocol 0.2: pass, 0 swapped commits.
- Updated [frontier safe-WPM page](questions/frontier-safe-wpm.md), [frontier E3 page](questions/frontier-e3-hallucination.md), [open gaps](questions/open-gaps.md) (69, 53 closed; 93 = P15-26, 94 = P15-27 added), [roadmap](questions/roadmap-standard.md), tracker, HANDOFF. v0.1 stays adopted; nothing published.

## [2026-11-19] setup | P5-28: hybrid streaming + end-of-trial prefix guard (pre-registered; hybrid beats single; gap 92 closed, new gaps 95, 96)
- Pre-registration + code `e3cb0cb` ([plan](../experiments/2026-11-19-p5-28-hybrid-prefix/plan.md), `fidetype.trust.hybrid_commit`, tests, run.py; full pytest 1625 passed, 11 skipped); results `c359eb6`: [results](../experiments/2026-11-19-p5-28-hybrid-prefix/results.md). Reuses the P5-27 views read only; CPU, 18 s.
- T15 val_eval 701 under the PROPOSED v0.2 + reading cost + several-commits rule: hybrid 4.89 [4.49, 5.27] (certified, 18 / 701 wrong) vs one-commit prefix guard 4.67 [4.26, 5.07]; Δ +0.22 [+0.14, +0.31]: **hybrid beats single**. Median latency of right words 3.85 s vs 11.20 s.
- Caution: λ_mid 0.99 came from P5-27 on the same certify items; Bonferroni sensitivity 4.63 (no clear difference). Fix: an infeasible joint certification switches off mid-trial commits.
- Updated [frontier safe-WPM page](questions/frontier-safe-wpm.md), [proposal 7.5](../docs/safe-wpm-v0.2-proposal.md#75-result-p5-28-t15-pre-registered-hybrid-guard), [open gaps](questions/open-gaps.md) (92 closed; 95 = P5-29 T12, 96 = P5-30 scorer), [roadmap](questions/roadmap-standard.md), tracker, index. v0.1 stays adopted; nothing published.


## [2026-11-19] setup | README and wiki status refresh after P15-22, P5-28, P11-01
- README "Where we are going": status date 2026-11-19; F2 row adds the P15-22 protocol 0.2 pass and gap 74 (fluent-wrong not certified with a learned score); F3 row gives the P11-01 EMG base decoder (CER 15.09 % personalised, 53.52 % generic, no LM) and P15-08 E1 as running, no result yet.
- README safe-WPM paragraph: v0.1 4.91 [4.25, 5.57] (P15-22, certified, pre-registered) above gaze typing 4.02, lower CI end also above; earlier best 2.64; one participant, one split, one seed, offline replay, not a user study; replication gap 93 (P15-26). P5-28 hybrid: first right word 2.7 s vs 14.0 s at 4.89 (v0.2 PROPOSED), WPM gain not robust; P5-27 streaming 2.34.
- Same stale claims fixed in [overview](overview.md) and [north star](questions/north-star.md) (safe-WPM write-up row, E1 row). [frontier-safe-wpm](questions/frontier-safe-wpm.md) was already current. Historical result pages unchanged.
- Tracker: run stats for p5-28-agent and the P15-22 agent filled; dashboard rebuilt. Site build local links OK; leaderboard check fresh; publishing-metadata tests 15 passed. Nothing published.

## [2026-11-19] setup | P15-27 + P5-30: grounding top-1 order and safe_wpm infeasible status (gaps 94, 96 closed; new gap 97)
- P15-27 root cause: `GroundingCheck.apply` demoted ungrounded candidates but kept the list order, so on 9 / 701 T15 trials the pipeline's first item was ungrounded; the guard's `NBest` sorts and used the right (grounded) top-1. Fix in code `296fb88`: `apply` returns the list sorted (stable); tests.
- Impact: full P15-22 rerun with the fixed code from scratch copies of the caches: every decision, config id, safe WPM and halluc card identical. **4.91 [4.25, 5.57] does not change.** Only `top1_equals_pipeline_top1` 692 -> 701. Dated addenda in the [P15-22 results](../experiments/2026-11-19-p15-22-llm-learned/results.md) and the [F2 M4-13 results](../experiments/2026-11-17-f2-m4-13/results.md) (P15-05 B1 T15 M4-13 WER 0.1617 -> 0.1609, S1 still pass).
- P5-30: `safe_wpm` gives `not-certified` for a `feasible: false` guarantee when the policy commits (v0.1 and v0.2); rule 6 in docs/safe-wpm.md; test. 100 committed safe-WPM blocks re-checked: no card changes label (the 2 infeasible cards commit nothing); leaderboard `--check` fresh.
- New gap 97 (P15-28): recompute the M4-12 / T12 grounded WER values. Updated [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md), tracker, HANDOFF. README, overview, north star and frontier-safe-wpm unchanged (headline unchanged).

## [2026-11-19] setup | P14-01: pretrained decoders, one-line load and decode to NTS (in progress; new gaps 98-101)
- Code `2442cbd`: `fidetype.pretrained` (alias `fidetype.decoders.load`), packaged manifests (input spec, files with SHA-256 + size + empty `url` slot, `data.licence` / `data.research_only`, proposed weights licence, metrics, limits), NumPy runtimes `gru-ctc` / `crt-ctc` / `key-lda`, readers of the public files, CLI `fidetype decoders`, [docs](../docs/pretrained-decoders.md), README quickstart, `examples/pretrained_decode.py`, `tools/pretrained/export_weights.py`; tests 16 (fake weights); full pytest 1651 passed, 11 skipped.
- Models: `t15-m4-13` (CC0, packaged P14-05 guard), `t12-v2` (CC0), `kt-semg-lda` (CC BY 4.0), `emg2qwerty-p11-01` (CC BY-NC-SA 4.0, research only, opt-in gate); `willett-hw`, `toronto-semg-cnn` planned. No weights in git or the wheel; nothing hosted or published.
- Rerun ([results](../experiments/2026-11-19-p14-01-pretrained/results.md)): T15 PER 0.1210 (card 0.1210), guard decisions equal to P14-05 on 701 / 701; T12 PER 0.2695 (0.269); emg2qwerty prompt CER 0.5831 (0.5832); KT run28 0.242 (0.248, other timing path).
- Done criterion not met (no hosted weights): [roadmap](questions/roadmap-standard.md) status line, [open gaps](questions/open-gaps.md) 98 = P14-30, 99 = P14-31, 100 = P14-32, 101 = P14-33; tracker P14-01 `in_progress`; hosting step in docs/publishing-checklist.md section J (user, weekend).

## [2026-11-19] setup | P11-09: EMG trust config + real-time collector replay (gaps 89 and 8 closed; new gap 102)
- Pre-registered ([plan](../experiments/2026-11-19-p11-09-emg-trust/plan.md), `0c53d68`; amendments `f28416d`, `36a921c`). Split by session: track val -> calibrate (1,224 prompts), track test -> evaluate (1,221 prompts) of the 8 P11-01 users; salted-hash split as arm H. Code `9220525`: key-code writer `fidetype.adapters.emg2qwerty.tokens_to_codes` / `merge_to_key_ctc` (98 CTC tokens -> 32 `KeyboardEvent.code` classes, track truth rule), runner, tests.
- Result ([results](../experiments/2026-11-19-p11-09-emg-trust/results.md), `e05b509`): guard `tcfg-4af5a234c1cf7826` certified (null controls 0/300) and safe (0 wrong / 1,221, CP95 [0, 0.003]) but **vacuous**: 0 commits, safe WPM v0.1 0.00 < no-BCI 2.93. Whole-prompt key sequences are exactly right on 2 / 1,221. Key error rate 0.179 [0.145, 0.214]; eWPM 3.44 vs gaze 2.93. Arms L (learned) and H (hash split): also 0 commits.
- Real-time replay (240 prompts, 8 per-user streams, WebSocket): `added` p50 58.6 ms, p95 110 ms (median over runs) / 222 ms (max): **fails** the 50 ms budget; the built-in beam inside the collector is the cause (gap 37, P3-06). Outputs NTS Trust-ready; 240 / 240 agree with offline.
- Declared-subset research-only cards `emg2qwerty__p11-01-crt-subset8__guard` / `__always-commit`, leaderboard regenerated (`--check` fresh). Gap 8 (P14-10) closed; gap 27 (P14-13) emg2qwerty part done. New gap 102 = P11-11. Updated [open gaps](questions/open-gaps.md), [roadmap](questions/roadmap-standard.md), [emg2qwerty](entities/emg2qwerty.md), [frontier decoder quality](questions/frontier-decoder-quality.md), tracker, HANDOFF.

## [2026-11-19] setup | P15-26: replication of the P15-22 safe-WPM headline (gap 93 closed; new gap 103)
- Pre-registration `39e9419`; code `a719794`, `4b7c07c`, `83448eb`; [results](../experiments/2026-11-19-p15-26-replication/results.md). CPU only.
- T15, four new calibration draws (seeds 1-3 inside `val_select`; one pooled re-split): L1 safe WPM v0.1 5.58, 6.00, 5.23, 5.83, all certified, CI lower ends above 4.02. Level and gain replicate (4 / 4 each). P15-22 (4.91) is the lowest of five draws (mean 5.51, SD 0.44).
- T12: 2.37 [1.34, 3.62] against 4.11: does not replicate. Gain over P5-23 +0.50, no clear difference.
- Claim on the frontier page: above gaze typing on T15, not on T12. Updated: frontier-safe-wpm, open-gaps, roadmap, tracker, HANDOFF. New gap 103 = P15-29 (interval that includes the calibration draw).

## [2026-11-19] setup | README, overview and north star after P15-26; tracker agent-run stats
- README (F2 row, safe-WPM paragraph), overview and north-star now give the P15-26 check of the P15-22 headline. The pre-registered headline stays 4.91 [4.25, 5.57] (v0.1, T15).
- T15: stable over 4 new calibration draws (5.23–6.00, all above gaze 4.02). 4.91 is the lowest of 5 values. T12: not above gaze typing (2.37 [1.34, 3.62] vs 4.11). The T12 decoder is too weak (35 / 400 top-1 exact).
- The intervals do not yet include calibration-draw variation (gap 103, P15-29). Link: [P15-26 results](../experiments/2026-11-19-p15-26-replication/results.md).
- tracker.json: agent-run stats added for P15-27 (+P5-30), P14-01, P15-26 (run 1 + resume) and P11-09. Dashboard rebuilt.

## [2026-11-19] setup | P11-11: non-vacuous certified EMG safe WPM (gap 102 closed; new gap 104)
- Pre-registration `b412c76`; amendment 1 + code `5f54a45`; results `766b2b3`; [results](../experiments/2026-11-19-p11-11-emg-nonvacuous/results.md). CPU only, research only, aggregates only.
- Levers: intended text after Backspace as the target; n-best rescoring with a leak-free Tatoeba 6-gram LM and a track-train lexicon; word-prefix commits. Whole-prompt top-1 rises from 0.16 % (P11-09) to 24.5 %.
- Prefix arm: certified proposed-v0.2 safe WPM 4.23 [2.60, 6.34] > no-BCI 3.09 / 2.93 (not clearly); v0.1 0.07. Sentence arms refused by the time-shuffled null control; the prefix arm fails the eval null control (6.2 %). Raw-key arm vacuous, no card.
- Updated: open-gaps (102 closed, 104 added), roadmap (P11-11 done, P11-12 new), tracker, HANDOFF, dashboard.

## [2026-11-19] setup | P11-11 reopened (gap 102 not closed); P11-09 Clopper-Pearson level fix
- Orchestrator decision: gap 102 / P11-11 is `in_progress` (partial), not done. Reason: arm X non-vacuous under proposed v0.2 but fails null control V6 (6.2 % > 5 %); v0.1 still 0.07; closes after P11-12 (gap 104) no-signal gate passes controls. The done-when asks for the same controls as P11-09.
- Updated: open-gaps (102 back in the open table), roadmap (P11-11 status), tracker (status, finished_at cleared, P11-11 agent run 4953.9 s / 284,653 tokens / 130 tool uses), HANDOFF, and an orchestrator note in the [P11-11 results](../experiments/2026-11-19-p11-11-emg-nonvacuous/results.md). Gap 104 / P11-12 unchanged.
- Bug fix: `experiments/2026-11-19-p11-09-emg-trust/run.py` called `clopper_pearson(k, n, 0.05)`; the third argument is the confidence level, so it gave a 5 % interval. Now 0.95. No number on the [P11-09 results](../experiments/2026-11-19-p11-09-emg-trust/results.md) page changes (it quotes the scorer's interval). `results.json` fields `arms.{P,L,H}.wrong_commit_cp95` were [0.0, 0.0006]; recomputed from the stored counts to [0.0, 0.003] / [0.0, 0.003] / [0.0, 0.0031]. A search of `src/` and the other experiment runners found no other misuse.

## [2026-11-19] setup | P11-12: acoustic no-signal gate for the EMG guard (gaps 104 and 102 closed; new gap 105)
- Pre-registration `f63da8a`, code `3a0572b`, results `a93aa50`: [results](../experiments/2026-11-20-p11-12-emg-nosignal-gate/results.md). Gate from the decoder argmax path only (greedy key emissions >= 15, 1.84 <= keys/s <= 17.28; fitted on the calibration tuning part).
- All arms certified, safe, non-vacuous, all P11-09 controls pass (test time-shuffled / zero EMG 0 / 1,221): sentence S v0.1 4.10 [1.99, 6.60] > no-BCI 3.09 (not clearly above); SL 5.08; prefix X v0.2 4.25 (null 6.2 % -> 0 %). Gate drops 2.2 % of real windows.
- No score card (intended-text target; the track scorer uses raw keys): new gap 105 = P11-13.
- Updated: open-gaps (102 and 104 closed, 105 added), roadmap (P11-11 and P11-12 done, P11-13 new; P11-12 depends-on wording fixed), tracker, HANDOFF, dashboard.

## [2026-11-19] setup | New roadmap items: languages, devices, UI, SDKs, production use (gaps 106-116)
- Source: user question "is this for every language, all devices, UI, SDK, production integration?".
- New items (roadmap, open gaps, tracker): P14-34 language-agnostic pipeline audit (106), P15-30 first non-English result on SpanishBCBL (107), P15-31 non-Latin scripts scan (108), P15-32 multilingual LM grounding (109), P4-15 device support matrix (110), P14-35 end-user typing UI (111), P14-36 usability study (112, `externally_blocked`), P2-12 iOS / mobile binding (113), P3-11 collector 24 h soak (114), P14-37 end-user installer (115), P8-07 effort-weighted progress view (116).
- Already covered, cross-referenced only: P4-05 / M6-02 (consumer devices), P4-06 / M6-12 (real-device tests), P14-07, P8-05 + docs site plan T11 (SDK API docs), P2-02 / P2-05 (C core, C# / Kotlin), P3-03 (OS text input), P14-09 (AAC app), gap 37 = P3-06 (EMG latency), M6-13 / M6-15 (live-path soak), M6-04 (real-user eWPM).
- No existing item moved, changed or was removed. Dashboard rebuilt.

## [2026-11-19] setup | P11-13: intended-text scoring for the emg2qwerty track (gap 105 closed)
- Scorer: versioned manifest field `target` for emg2qwerty: `raw_keys` (default, unchanged; the committed P11-09 cards rescore equal) or `intended_text` (rule `intended-text/1`, Backspace applied, same as the P11-11 `resolve`). Truth, outputs and the no-BCI reference use the target text. Code `698bbe8`; docs: benchmark-submission, benchmark-tracks.
- Leaderboard: each target in its own table with its own no-BCI row; `[target: intended_text]` in the entry name.
- Cards (`ca73b5c`, declared subset, research only): P11-12 arm S certified safe WPM v0.1 4.10 [1.99, 6.56] vs no-BCI 3.09; SL 5.08 [2.54, 7.95]; controls pass. Same value, commits and words as P11-12; CI differs only by the bootstrap cluster label order. [results](../experiments/2026-11-20-p11-13-intended-text-cards/results.md)
- Also: the closed-gaps table in open-gaps had its `|---|` separator in the middle of the table; moved under the header (no content change). Tracker: P11-12 agent run added (2382.304 s, 182,033 tokens, 61 tool uses).

## [2026-11-19] setup | P14-34: language audit and per-language config (gap 106 closed; new gaps 117-119)
- Audit `857dcf1`: [docs/language-support.md](../docs/language-support.md) lists about 40 English assumptions (file:line, impact for es / zh / ar / hi, config key, risk, state).
- Code `2b5c80f`: `fidetype.lang` (registry by BCP 47 tag). `en` default reuses `VOCAB` / `normalize_text` / `str.split`, so English outputs are bit-identical (pinned by `tests/test_lang.py` and `tests/fixtures/lang/`). `es` provisional (ñ, accents, ¿ ¡). `zh` stub: words and WPM raise `WordsNotDefinedError`, never a silent number.
- Language tag in the model manifest and the trust guard (saved only if not `en`); `safe_wpm.load_trials_jsonl(language=)`. Spanish config runs end to end on synthetic input.
- Updated: open-gaps (106 closed; 117 P14-38, 118 P14-39, 119 P14-40 added), roadmap, tracker, HANDOFF, docs index, dashboard.

## [2026-11-19] setup | P15-08 E1a results: cross-body pretraining null at minutes scale (H1 fails, C2 fails); new gap 120
- [Results](../experiments/2026-11-19-p15-08-e1-cross-body/results.md) against the plan `60620ab`; aggregates in `results/summary.json`. Run 10:28-20:00, 41 adaptation runs + text pretraining; one machine-sleep crash (S-b30-s0), clean resume at step 1000, no lost or repeated step.
- Verdicts: V1 pass (E at all 0.395); H1 fail (0 of 3; T better than E at 10 and 30 min); H2 fail; H3 fail; H4 partial; C1 pass; C2 fail (0.836 vs 0.810). Roadmap rule passes as written only by ≤ 1 CER point (CI includes 0).
- Mean test CER R / T / E / S at 3, 10, 30, 100 min, all: R 0.865, 1.327, 0.851, 0.837, 0.613; T 0.960, 0.863, 0.786, 0.777, 0.805; E 0.957, 0.884, 0.812, 0.767, 0.395; S 0.919, 0.922, 1.003, 0.919, 0.925.
- Records: P15-08 stays `in_progress` (KT-sEMG arm); new gap 120 = [P15-33](questions/roadmap-standard.md#p15-33-e1-low-data-recipe-that-reads-the-target-signal-before-more-source-arms); P14-33 (gap 101) can start; README F3 row and north-star E1 row updated.

## [2026-11-19] setup | P14-33: Willett handwriting decoder `willett-hw` in the pretrained registry (gap 101 closed; new gap 121)
- Code `b6dd77c`, [results](../experiments/2026-11-19-p14-33-willett-hw/results.md), [docs](../docs/pretrained-decoders.md). `willett-hw` v1 `available`: P15-08 run R-all-s0 (random init, Willett CC0 data only, final step 3000); runtime `xbody-ctc` (NumPy), reader `read_willett_session`; weights local only (CC0-1.0 provisional, D11; not hosted, gap 98); language `en`.
- Card metric rerun with `load("willett-hw")` on CPU: test greedy CER 0.3051 (1,052 / 3,448), equal to the PyTorch value on 80 / 80 sentences. Card: weak, seed 1 failed (0.920), no LM, descriptive only; its split differs from the benchmark track `willett-hw` (193 of 254 track test trials in its training pool).
- Guard calibration stopped by low machine memory: new gap 121 = [P14-41](questions/roadmap-standard.md#p14-41-trust-guard-for-willett-hw). PyTorch-on-CPU comparison not run (same reason).
- P14-12 (gap 26) and P6-06 (gap 28) can now use this decoder (noted in their rows; not done). `fidetype decoders list` shows the proposed weights licence.
- Updated: open-gaps (101 closed, 121 added), roadmap, tracker, HANDOFF, publishing checklist section J, dashboard.

## [2026-11-19] setup | P11-07: character LM inside the CTC beam for the emg2qwerty EMG decoder (gap 87 closed; new gaps 122-123)
- Pre-registration `d168c51`, code `9e12a97`, amendment 1 `27f6d08` (CPU model chunk timed with the NumPy CRT; the ROCm torch CPU build is BLAS-bound), results `1bd41d9`, [results](../experiments/2026-11-20-p11-07-emg-beam-lm/results.md). Research only, aggregates only.
- Own causal CTC prefix beam with shallow fusion of the leak-free Tatoeba 6-gram on the intended text; tuned on the 765 track-val tuning prompts (w 0.5, beta 1, beam 8). Session CER (8 track-test sessions, mean over users): greedy 14.66 % -> 10.10 % (8 / 8 users); beam 64 9.13 %; Table 3 fine-tuned no LM 11.28 %, LM 6.95 %. Intended-text CER 15.16 % -> 9.75 %. Lexicon term no help. C1 0.985. Greedy reproduces P11-01 on its 16 sessions (15.0898 %).
- Latency: beam push p95 <= 0.7 ms per 40 ms chunk; end-of-window guard work p95 61-70 ms for every beam; CPU model chunk p95 47 ms (GPU 4 ms). The 50 ms CPU rule fails (evidence for gap 37; new gap 122 = [P3-12](questions/roadmap-standard.md#p3-12-guard-end-of-window-cost-and-cpu-acoustic-model-inside-the-50-ms-budget)).
- P11-12 arm S with the new decoder: certified 3.37 [1.92, 5.18] (P11-12: 4.10); SL 3.16. No new card. New gap 123 = [P11-14](questions/roadmap-standard.md#p11-14-guard-confidence-for-the-in-beam-lm-decoder).
- Updated: open-gaps (87 closed, 37 evidence, 122-123 added), roadmap (P11-07 done, P3-06 evidence, P3-12, P11-14), tracker, HANDOFF, dashboard.

## [2026-11-19] setup | Records: agent run numbers filled; new gap 124 (CI latency-budget flake)
- Tracker agent runs filled: P11-13, P14-34, P14-33, P11-07 (run 1 + finish run), P15-08 write-up run (null stats replaced). P11-11 and P11-12 checked (already filled). The three helper runs (README update after P15-26, gap-102 reopen, language/device/UI gap registration) have no record task in the tracker, so they are not recorded.
- Removed the stale phrase "agent run numbers: to be added by the orchestrator" from the P15-26 and P15-27 notes.
- New gap 124 = [P2-13](questions/roadmap-standard.md#p2-13-ci-latency-budget-tests-flake-on-shared-runners): CI run 44673291448 (commit `8180a30`) failed `tests/test_collector_pipeline.py` (emg-key WebSocket latency p95 320 ms vs the 50 ms budget, windows-latest, Python 3.12); the rerun passed.
- Updated: open-gaps (124 added), roadmap (P2-13), tracker (P2-13 `todo`), dashboard.

## [2026-11-20] setup | P11-14: guard confidence for the in-beam LM EMG decoder (gap 123 closed; new gaps 125-126)
- Pre-registration `39f6432`, code + amendment 1 `a3d50eb`, card script `659616f`, results `db96a4e`, leaderboard `ecd3773` ([results](../experiments/2026-11-20-p11-14-emg-lm-confidence/results.md)). Research only; aggregates only; CPU only.
- Primary arm L-FL (selected on calibration tuning items only): certified safe WPM v0.1 **6.80 [4.49, 9.63]**, 285 commits, 52 wrong; above P11-12 S 4.10 / SL 5.08 and P11-07 S 3.37 (reproduced exactly); first EMG CI above no-BCI 3.09; all controls pass.
- The gain comes from the fused posterior over a wider competitor set plus the LM per character; the acoustic-only posterior fails.
- New intended_text card `emg2qwerty__p11-14-intended-lfl-subset8__guard`; leaderboard regenerated, `--check` passes.
- New gaps 125 = [P11-15](questions/roadmap-standard.md#p11-15-latency-cost-of-the-p11-14-confidence) (latency cost of the confidence), 126 = [P11-16](questions/roadmap-standard.md#p11-16-p11-14-confidence-signals-for-prefix-commits) (prefix commits). P15-25 (gap 91) note: use decoder FL + confidence L-FL.
- Updated: open-gaps (123 closed, 125-126 added), roadmap (P11-14 done, P11-15, P11-16, P15-25 note), tracker, dashboard, HANDOFF.

## [2026-11-20] setup | P17-00: roadmap phases P17 (daily use) and P18 (reach) added after the roadmap
- The user approved the post-roadmap list ("P17+"). Two new phases come after P1–P16. No existing item moved, renumbered or removed.
- **P17 Daily use: product, people and privacy** (2028): P17-00 (scope, done), P17-01 daily-use AAC app on the trust guard, P17-03 own data protocol + consent, P17-06 on-device learning, P17-07 federated / self-supervised adaptation, P17-08 hosted hub build + staging, P17-10 regulatory map. Externally blocked: P17-02 home use, P17-04 ethics approval, P17-05 volunteer recordings, P17-09 hub launch (user publishes), P17-11 clinical study or filing.
- **P18 Reach: hardware, models, languages, outputs, standards** (2028 → 2029-06): P18-01 open EMG wristband design, P18-02 driver, P18-04 cross-body foundation model, P18-05 zh and other languages, P18-06 commands and cursor, P18-07 speech output (all under the no-false-words guarantee), P18-08 standards package. Externally blocked: P18-03 prototype build, P18-09 standards body work item.
- Each item has a done criterion and dependencies on existing items (P14-35, P14-37, P12, P13, P5-04, P5-05, P15 F1 / F3, P15-30 … P15-32, P14-38 … P14-40). P16 (write side) is not repeated.
- Updated: [roadmap](questions/roadmap-standard.md#p17-daily-use-product-people-and-privacy-added-2026-11-20-after-the-roadmap) (P17, P18 sections, sequencing row, intro), diagram 11 (two teal rows; caption in slides.json), tracker (milestones P17, P18; 21 tasks), dashboard.

## [2026-11-20] setup | P14-42 and P14-43: adapter catalogue + contributor template, 10-minute tutorials (gaps 127-128)
- The user approved two adoption items after a comparison with LangChain history (17,256 commits: about 38 % integrations, 31 % docs, 11 % core; 3,748 contributors). Fidetype has 395 commits and 1 author.
- **P14-42** (gap 127): adapter catalogue page + machine-readable registry (device or dataset, signal type, status, licence notes, test coverage), planned entries for common non-invasive devices and public datasets, a cookiecutter-style template and a CONTRIBUTING.md section; done when 2 new adapters from the template pass the synthetic conformance test in CI. Depends on P4-15 (gap 110), P4-01, P4-02, P4-05.
- **P14-43** (gap 128): at least 3 tutorials (pretrained decode; trust guard + safe WPM; benchmark score), CPU, public or synthetic data, each under 10 min; done when all 3 pass in CI and are timed. Depends on P14-01, P14-03, P14-05, P13, P14-30 (gap 98).
- Records only: [roadmap](questions/roadmap-standard.md#p14-42-device-and-dataset-adapter-catalogue-and-contributor-template), [open gaps](questions/open-gaps.md), tracker, dashboard. No existing item moved, renumbered or removed. Diagram 11 lists phases only, so it did not change.

## [2026-11-20] setup | P14-43: 10-minute tutorials (gap 128 closed; new gaps 129-131)
- Three tutorials in `tutorials/`: (1) decode with a pretrained decoder, (2) trust guard + safe WPM, (3) score on the benchmark. Each has a synthetic mode (no download; a toy model or a simulated decoder made at run time) and a documented real-data mode (B2T '25 T15; KT-sEMG). Pages: [docs/tutorials.md](../docs/tutorials.md) and one page per tutorial.
- Smoke test `tutorials/test_tutorials.py` + CI workflow `.github/workflows/tutorials.yml` (Linux + Windows, clean venv, numpy only). CI: green (run 44723379731: ubuntu-latest 0.4 / 62.5 / 0.2 s, windows-latest 0.9 / 94.7 / 0.4 s, all under 10 min).
- Times: local CPU (Ryzen 7 9800X3D desktop, Windows, Python 3.12): tutorial 1 0.4 s, tutorial 2 79.3 s, tutorial 3 0.4 s (pinned to 2 CPUs: 0.4 / 77.9 / 0.4 s; clean venv with numpy only: 1.6 / 77.5 / 0.4 s). real-data modes on the project machine (local weights, not in CI): T15 decode 5 trials 12.4 s; T15 guard + safe WPM 65 val_eval trials 48.3 s (10 commits, 5 wrong, safe WPM 1.49 above-alpha on this small subset; all 701 trials: 2.23 certified, P14-05); KT-sEMG run28 score 47.4 s (22 / 172 units, key error 0.748, vacuous).
- The synthetic numbers are toy numbers; the pages say so. The real T15 subset (65 trials) is `above-alpha` (5 wrong commits), shown as is; the full 701-trial result stays 2.23 certified.
- API friction registered as gaps 129 (P14-44, pretrained API ergonomics), 130 (P14-45, decisions to safe WPM in one call), 131 (P14-46, benchmark glue). Real-data modes need local weights until gap 98 (P14-30) closes.

## [2026-11-20] query | P15-29: safe-WPM interval that includes the calibration draw (gap 103 closed)
- Pre-registration `d7169cf`, code `8180a30`, results `c61d215`: [results](../experiments/2026-11-20-p15-29-calibration-ci/results.md). CPU only, two detached workers, 2026-11-19 20:16 to 2026-11-20 02:56.
- Method: a two-level bootstrap. Outer: 40 T15 / 20 T12 calibration draws (resample inside the calibrate fit / policy / LTT parts, full guard recalibration, pinned T / tau / lambda). Inner: 2,000 trial resamples of the fixed evaluation set. A draw that is not certified earns 0.
- T15 L1 safe WPM v0.1: **5.18 [0.00, 6.99]**. The lower end is not above the no-BCI 4.0153, so the verdict is "above, but inside the combined interval". 2 / 40 draws are above alpha on the test set; the certified draws range from 3.50 to 6.82. Exploratory rules give lower ends of about 3.6. The trial-bootstrap CI of one draw was [4.25, 5.57].
- T12: 1.05 [0.00, 3.18], not above 4.11 (10 certified, 6 above alpha, 4 vacuous). The X4 code check passes; pinning T / tau / lambda changes the value by at most 0.15 (X3).
- New optional `fidetype.benchmark.safe_wpm.calibration_draw_interval` + tests; docs/safe-wpm.md section 6b (PROPOSED reporting addition). Open gaps, roadmap, tracker, dashboard and HANDOFF updated. The README claim about the T15 lower end must change (not edited here).

## [2026-11-20] lint | P15-29 headline correction: T15 safe WPM above gaze typing on average, not reliably
- The old public claim "the lower end of the T15 safe WPM interval is above gaze typing (4.02)" is no longer supported. P15-29 ([results](../experiments/2026-11-20-p15-29-calibration-ci/results.md)) gives 5.18 [0.00, 6.99] with calibration variation (K = 40).
- Corrected: README.md (safe WPM paragraph, F2 limits row), [overview](overview.md), [north star](questions/north-star.md) frontier row, [index](index.md) line, [safe WPM write-up](questions/frontier-safe-wpm.md) (short answer, steps table, new P15-29 section, limits, our take, still open), [E3 write-up](questions/frontier-e3-hallucination.md), a note on roadmap item P14-23.
- The single-draw CI 4.91 [4.25, 5.57] stays, with the statement that it does not include calibration variation. The EMG P11-14 result 6.80 [4.49, 9.63] stays valid; its CI also does not include calibration variation.
- No paper draft makes the claim (papers/ checked), so no correction note. docs/safe-wpm.md section 6b already states P15-29 correctly.
- New gaps: 132 = [P15-34](questions/roadmap-standard.md#p15-34-calibration-inclusive-t15-safe-wpm-lower-end-above-gaze-typing) (calibration-inclusive T15 lower end above 4.0153), 133 = [P11-17](questions/roadmap-standard.md#p11-17-calibration-inclusive-safe-wpm-interval-for-the-emg-p11-14-l-fl-guard) (same interval for the EMG L-FL guard). Open gaps, roadmap, tracker, dashboard updated.
- The user decides at the weekend whether to adopt docs/safe-wpm.md section 6b (calibration-inclusive reporting), together with safe-wpm v0.2.

## [2026-11-20] setup | P14-42: adapter catalogue, conformance helpers, template; new EDF/BDF and OpenBCI GUI readers (gap 127 closed; new gaps 134-135)
- Registry `fidetype.adapters.registry`: built from the `ADAPTER_INFO` of each adapter module and `planned.py` (no hand-kept copy). Generated [docs/adapters.md](../docs/adapters.md) and `docs/adapters.json`; `--check` runs in pytest, so CI fails on drift. 17 adapters in the repository (14 tested, 3 experimental, none tested on a real device), 16 planned rows.
- Conformance helpers `fidetype.adapters.testing`: `assert_source_conforms` (the `fidetype live` source protocol; NTS 4.1 / 4.2 meta rules; LSL-binding channel labels and units; times; markers; end; `ValueError` on bad input) and `assert_nts_conforms` (the NTS conformance suite at a level).
- Template `templates/adapter/` + `python -m fidetype.adapters.registry new <id>`; [CONTRIBUTING.md 7.1](../CONTRIBUTING.md#71-add-a-new-adapter-in-about-50-lines).
- New adapters from the template (synthetic files only): `edf` (EDF / EDF+ / BDF; 96 lines, 70 code lines) and `openbci-gui` (67 lines, 43 code lines). EDF is above the 50-line goal.
- Code `8167853`, CI run 44722287677. Updated: roadmap (P14-42 done, P4-15 progress note, P4-16, P4-17), open gaps (127 closed, 134-135 added), tracker, HANDOFF, dashboard.

## [2026-11-20] setup | P14-41: willett-hw trust guard (offer-only; gap 121 closed; new gaps 136-137)
- Memory cause of the P14-33 stop: the CTC prefix beam search kept every prefix it ever made (T^2 growth on flat null frames; 17.9 GB in a synthetic probe) and the forced alignment held a (T, S) float64 array. Fixed exactly in `fidetype.lm.beam` (caches cut to the beam, frame-wise alignment in groups), with tests. Run peak 1,194 MB.
- Pre-registration `4565cc1`, then the run (CPU, 03:29-04:51). Guard `tcfg-39aac48688b8bd12` on the 106 val sentences: returned, LTT not feasible (40 LTT items < 45), so it never commits (pre-stated). Test (80): 0 commits, 77 offers, 3 withholds; safe WPM v0.1 0.00 (vacuous). All null controls pass.
- Packaged as a release file of `willett-hw` (local, SHA-256 in the manifest, `trust` set, `commits: never`); docs/pretrained-decoders.md updated. [Results](../experiments/2026-11-20-p14-41-willett-guard/results.md), commit `b26341c`.
- New gaps: 136 = [P5-31](questions/roadmap-standard.md#p5-31-null-control-for-offers) (offers on frame-shuffled input 77/80, as on real input), 137 = [P5-32](questions/roadmap-standard.md#p5-32-memory-bound-for-the-vector-beam-search-and-the-lm-caches) (vector beam path and LM caches).

## [2026-11-20] setup | Records: agent run numbers, open-gaps table fix, new gap 138 = P14-47, two link fixes
- tracker.json: agent runs added for P11-14 (run 1 not captured; resume run), P15-29 (run 1, resume run, headline correction), P15-33 (run so far; GPU job still running), P17-00, P14-42 (roadmap-entries run for P14-42 + P14-43, recorded once; build run), P14-43, P14-41, and the earlier records run (commit `fc842aa`) on M0-12. The notes "to be filled / added by the orchestrator" are replaced.
- [Open gaps](questions/open-gaps.md): rows 134 (P4-16) and 135 (P4-17) are open `todo` gaps; they moved from "Closed gaps" to the open table. Content unchanged.
- New gap 138 = [P14-47](questions/roadmap-standard.md#p14-47-certified-non-vacuous-trust-guard-for-willett-hw-commits--0): certified, non-vacuous trust guard for `willett-hw` (commits > 0). P14-41 closed gap 121 under its pre-registered rule, but the guard never commits (LTT infeasible with 106 val sentences, safe WPM vacuous). Depends on about 120+ calibration sentences, a stronger decoder (gap 26 = P14-12, gap 120 = P15-33) and gap 136 = P5-31. Roadmap, open gaps, tracker (`todo`); the gap 121 row and the P14-41 roadmap entry point to it.
- Broken links fixed: `{R}` placeholder in [frontier-e3-hallucination](questions/frontier-e3-hallucination.md) (now the P15-22 results page); collector anchor in the roadmap (heading now ends "(P7-05, P7-07)"). docs/safe-wpm.md has no broken link. `node tools/hygiene/links.js --ci`: OK.

## [2026-11-20] query | P15-33: E1 low-data recipe search (val-C2 pass, test C2 and V1 fail; gap 120 stays open; new gaps 139-140)
- Pre-registration `a2906d8`, amendment 1 `415b481` (performance only: pad stretched batches; first run restarted). The amendment header time is corrected from 22:50 to 22:44, with the correction disclosed in plan.md.
- GPU run 2026-11-19 22:39 - 2026-11-20 07:24 (8.75 h; plan ≤ 10 h; no crash). Val-only search of 4 recipes at 30 min picked **A** (full fine-tune + strong regularisation and augmentation): arm E val 0.769, deranged 0.871 vs needed 0.869.
- Test grid with A: **C2 fails** (deranged E 30 min 0.847 vs needed 0.873), **V1 fails** (best at all E 0.713 > 0.50; A over-regularises at full data, R 0.976), so **H1-H4 are inconclusive**. C1 pass. E at 3 / 10 / 30 min 0.858 / 0.780 / 0.766 (E1a 0.957 / 0.884 / 0.812), descriptive.
- [Results](../experiments/2026-11-20-p15-33-low-data-recipe/results.md). Gap 120 stays open (`in_progress`, partial). New gaps 139 = [P15-35](questions/roadmap-standard.md#p15-35-e1-synthetic-sentence-augmentation-for-the-minutes-scale-recipe-test-c2) (synthetic sentences, test C2) and 140 = [P15-36](questions/roadmap-standard.md#p15-36-e1-budget-matched-recipe-so-that-v1-and-h1-h4-are-valid) (budget-matched recipe, V1).

## [2026-11-20] query | P15-34: safety-margin guard for the calibration-inclusive T15 safe WPM (criterion not met; gap 132 stays open; new gap 141)
- Pre-registration `025e928`; stage S lever selection on `val_select` only `d7f224b` (bootstrap world, 28 arms; no arm predicted above 4.0153). A larger calibration set was not possible without `val_eval` trials.
- Main run 2026-11-20 05:15-09:51, CPU, 40 new calibration draws x 4 arms, peak 2.87 GB per worker. X4 passes (z0 = P15-22 701 / 701, 4.91, [4.25, 5.57]).
- Primary A1 (alpha 0.05, delta 0.025): **4.90 [3.11, 6.44]**, 40 / 40 certified; the lower end is below 4.0153, so the criterion is not met. A2 (0.04, 0.1) identical; A3 (0.05, 0.01) 4.58 [2.47, 6.17]. Reference A0 (P15-29 settings, new draws) 5.35 [4.05, 6.81], 40 / 40 certified (descriptive). The margin costs 0.45-0.77 per draw and widens the between-draw spread. [Results](../experiments/2026-11-20-p15-34-margin-guard/results.md), commit `f17647e`.
- New gap 141 = [P15-37](questions/roadmap-standard.md#p15-37-lower-variance-calibration-for-the-calibration-inclusive-safe-wpm) (lower-variance calibration or more labelled data). No public claim changes (README, overview, north-star, frontier-safe-wpm unchanged).

## [2026-11-20] query | P3-12: in-beam LM EMG decoder plus guard inside the 50 ms CPU budget (gap 122 closed; new gap 142)
- Pre-registration `cfbc26e`; amendments `a3d9f10` (wait for a quiet machine), `b32faab` (time stamp), `eaa8152` (wait up to 8 h), `6d4fdbd` (bug fix: the latency stage did not load the P11-12 gate; crash at 09:52:33 before any timing; smoke dry run added); results `3a0fd49`.
- Profile: `guard.decide` was almost all of the end-of-window cost (per-frame JSON events and audit hash); the P11-07 model chunk recomputed its 121-frame receptive field.
- New code: `fidetype.pretrained._crt.CRTStream` (streaming model); `TrustGuard.session()` -> `GuardSession` and `StreamingTrustLayer.push_frames` (incremental guard decision); 13 targeted tests.
- Clean timed run (21:45-22:10, class timing, 1 thread): decision p95 **6.39 ms** (budget 50 ms), chunk p95 3.48 ms; the clean re-measured P11-07 path is 32.6 ms at the end + 20.5 ms model. Same decisions as the offline guard 3,663 / 3,663; safe WPM v0.1 3.37 unchanged.
- The pre-registered streaming-model tolerance (1e-5) failed (3.1e-5; float32 rounding; float64 forms agree to 3e-15) -> gap 142 = [P3-13](questions/roadmap-standard.md#p3-13-streaming-crt-model-in-the-decision-loop). Gap 37 (P3-06, collector profile) stays open with an evidence line.
- [Results](../experiments/2026-11-20-p3-12-emg-latency-budget/results.md).

## [2026-11-20] query | P15-25: E1a readout with the same character LM (gap 91 closed; new gaps 143-144)
- pre-registration `885f9c5`, code `29798a7`, results `44c2d8a`. All 41 E1a `final.pt` runs re-scored with one LM and one beam setting, fixed before the re-score: decoder F (P11-07, Tatoeba 6-gram, w 0.5, beta 1, beam 8) primary; FL (research-only lexicon), B0, Fv (val-tuned) secondary.
- C0: our GPU log-probs reproduce the E1a greedy edits exactly. H1 fails again (0 / 3); H4 partial -> fail; V1 pass (0.271); C1 pass; C2 fails. The minutes-scale null is not an LM artefact.
- Full data: E 0.395 -> 0.271, R-ball-s0 0.305 -> 0.173, T 0.805 -> 0.783 (H5 E beats T at all: pass, robust). The LM helps where the decoder reads the signal.
- LM overlap: 13 of 80 test sentences are in the Tatoeba export -> gap 143 = [P15-38](questions/roadmap-standard.md#p15-38-e1-lm-readout-with-the-willett-texts-blocked-from-the-lm). `willett-hw` with the F readout + no-signal gate -> gap 144 = [P14-48](questions/roadmap-standard.md#p14-48-willett-hw-with-the-same-lm-readout-and-a-no-signal-gate).
- [Results](../experiments/2026-11-20-p15-25-e1-same-lm/results.md).

## [2026-11-20] setup | Records: P15-38 done, P14-44/45/46 done, P14-48 run (gap 144 open), new gaps 145-149
- Gap 143 = [P15-38](questions/roadmap-standard.md#p15-38-e1-lm-readout-with-the-willett-texts-blocked-from-the-lm) closed: Willett-blocked Tatoeba 6-gram, no E1 verdict changes; E full data 0.271 -> 0.273, R-ball-s0 0.1734 -> 0.1743 ([results](../experiments/2026-11-20-p15-38-e1-lm-willett-blocked/results.md)).
- Gaps 129, 130, 131 = P14-44, P14-45, P14-46 closed (commits `6f7fade`, `7c455b7`, `9ebf38a`; CI runs 44878237413, 44878237441 green).
- Gap 144 = [P14-48](questions/roadmap-standard.md#p14-48-willett-hw-with-the-same-lm-readout-and-a-no-signal-gate) stays open: LM readout packaged (opt-in, test CER 0.1760 gated); N1 fails (13 / 80 time-shuffled inputs emit text); guard `tcfg-8fa3866deec917f3` offer-only ([results](../experiments/2026-11-20-p14-48-willett-lm-readout/results.md)). Evidence added to gaps 138 (P14-47) and 136 (P5-31).
- New gaps 145 = [P14-49](questions/roadmap-standard.md#p14-49-no-signal-gate-for-willett-hw-that-stops-time-shuffled-input) (gate), 146 = [P14-50](questions/roadmap-standard.md#p14-50-willett-blocked-tatoeba-lm-as-the-willett-hw-lm-readout) (Willett-blocked LM readout), 147 = [P14-51](questions/roadmap-standard.md#p14-51-toy-models-for-the-xbody-ctc-crt-ctc-and-key-lda-runtimes), 148 = [P14-52](questions/roadmap-standard.md#p14-52-kt-semg-item-count-from-the-key-log-alone), 149 = [P14-53](questions/roadmap-standard.md#p14-53-tutorial-3-real-mode-re-run-after-the-p14-46-changes).
- Tracker: agent runs for P3-12, P15-33 write-up, P15-34, P15-25, P15-38, P14-48, P14-44/45/46 (one run), M0-12 records. README: `m.decode_file(...)` and `m.decide(stream)` (no deprecated call). HANDOFF: finished background rows removed. Written 2026-11-20 23:37.

## [2026-11-21] query | P14-49 + P14-50: no-signal gate C5 and the Willett-blocked LM for `willett-hw` (gaps 144-146 closed; new gaps 150-151)
- Pre-registration and code `76747e8`, results `dcc344b`. Val-only selection over six candidates chose C5, a logistic score of five posterior features.
- Test (80 sentences): time-shuffled 2 / 80, zero 0 / 80, uniform 0 / 80 emit; real gated 1 / 80; N2 pass (frame-shuffled CER 0.881). CER 0.1743 ungated (= P15-38), 0.1746 gated.
- Guard `tcfg-26ae951a20a0cddd`: not certified (40 < 45 LTT), offer-only, safe WPM 0.00 (vacuous). Gap 144 (P14-48) closed: D1 is now met (orchestrator decision).
- Frame-shuffled frames pass C5 (79 / 80) -> gap 150 = [P14-54](questions/roadmap-standard.md#p14-54-frame-order-aware-no-signal-gate-or-offer-check-for-willett-hw); C5 robustness -> gap 151 = [P14-55](questions/roadmap-standard.md#p14-55-robustness-check-of-the-willett-hw-gate-c5).
- [Results](../experiments/2026-11-20-p14-49-willett-gate-blocked-lm/results.md).

## [2026-11-21] query | P5-31 + P5-32: offer null control and bounded vector beam memory (gaps 136-137 closed; new gaps 152-154)
- Code `5a44e1b` (P5-32), `534feae` (P5-31), re-check `367ad72`. `calibrate(offer_control="warn" | "refuse" | "off")`, default warn; `sheet.offers`; `recheck_offer_control`.
- All four packaged guards fail the offer null control; warn mode, so no status changes; commit counts equal the sheets. `t15-m4-13` stays certified for commits.
- P5-32: vector beam prefix caches and LM row caches bounded, exact; T = 10,000, V = 98: push peak 59 -> 22 MB.
- New gaps 152 = [P5-33](questions/roadmap-standard.md#p5-33-offer-policy-that-withholds-on-no-evidence-input-and-the-offer-control-default), 153 = [P14-56](questions/roadmap-standard.md#p14-56-offer-control-result-in-the-packaged-manifests-and-model-cards), 154 = [P2-14](questions/roadmap-standard.md#p2-14-windows-pytest-ci-job-within-its-job-timeout) (CI Windows py3.12 job timeout).
- [Results](../experiments/2026-11-21-p5-31-offer-control/results.md).

## [2026-11-21] setup | Records: gaps 136, 137, 144, 145, 146 closed; new gaps 150-154
- Open-gaps list, roadmap, tracker and HANDOFF updated. Gap 138 (P14-47) has new evidence (still offer-only; P5-31 now available).
- Tracker: agent runs for P14-49/50, P5-31/32 and the earlier records run (commit `96cec56`, on M0-12).
- HANDOFF: GPU paused (the user is gaming); P15-37 CPU job running; publishing weekend has begun. Written 2026-11-21 01:11.

## [2026-11-21] query | P14-53: tutorial 3 real mode re-run after P14-46 (gap 149 closed)
- Commit `f797f0f`; [tutorial 3](../docs/tutorials-03-benchmark.md); tutorials CI run 44888427226 green.
- KT-sEMG run28: 22 / 172 units, key error 0.748, eWPM 2.40 (no-BCI 2.82), 22 offers, 0 commits, safe WPM 0.00 (vacuous), all controls pass, 48.2 s on 2 CPUs.
- Key-log-only truth = committed truth file in all 172 rows; both committed `kt-semg` cards rescore exactly. eWPM 2.55 -> 2.40 from the top-3 offers (expected). NaN in `card.json` -> strict JSON, with a test.

## [2026-11-21] query | P14-56: offer-control result in the packaged manifests and cards (gap 153 closed)
- Commit `f2eb771`, updated by `9ce8006`. `trust.offer_control` and `readouts.lm.trust.offer_control` in all four packaged manifests and in `Manifest.card()`; test against the re-check JSON; docs/pretrained-decoders.md; CHANGELOG.
- The blocks are copied by hand: gaps 150 and 155 refresh them from their new re-checks (no new gap).

## [2026-11-21] query | P5-33: offer gate that withholds on no-evidence input (gap 152 closed; new gap 155)
- Pre-registration `a7abc11`, code and results `9ce8006`. `t15-m4-13` passes with the gate `coherence >= 0.1869751254594959` (frame-order feature, default on): uniform and frame-shuffled 0 / 300 offers (were 300 / 300); 54 LTT commits unchanged; real LTT offers 212 / 271; val_eval 104 commits identical to P14-05.
- `kt-semg-lda` negative: no candidate passed the selection; info-only uniform 289 / 300, user nulls 165 / 173, real 63 / 65 (key accuracy 0.248). New gap 155 = [P5-34](questions/roadmap-standard.md#p5-34-offer-gate-for-kt-semg-lda).
- `offer_control` default: orchestrator recommendation "keep warn for now (1 of 4 guards passes); revisit after gap 150"; the decision moved to the user decision list in HANDOFF.md.
- [Results](../experiments/2026-11-21-p5-33-withhold/results.md).

## [2026-11-21] query | P2-14: sharded pytest CI jobs (gap 154 in progress; new gap 156)
- Commits `d0f0d34`, `2af928f`: file-level shards with measured weights (`--shard K/N`, `--file-durations`, `tests/shard_weights.json`); 3 shards per Windows Python, 2 per ubuntu; timeout 30 min; coverage unchanged.
- 5 consecutive green runs (44889116085, 44889286346, 44892071579, 44892213002, 44892707275); slowest job 12.3 min. 5 more needed.
- New gap 156 = [P2-15](questions/roadmap-standard.md#p2-15-faster-slow-test-fixtures-hybrid_setup-and-streaming-calibration): fixtures `hybrid_setup` (121 s) and the streaming calibration setup (91 s), low priority.

## [2026-11-21] setup | Records: gaps 149, 152, 153 closed; gap 154 in progress; new gaps 155-156
- Open-gaps list, roadmap, tracker and HANDOFF updated. Gap 150 (P14-54) has new evidence from P5-33 and a done-when addition (refresh the manifest `offer_control` blocks).
- Tracker: agent runs for P14-53, P14-56, P5-33 and P2-14. New items P5-34 and P2-15 (todo).
- HANDOFF: user decision list (`offer_control` default); P15-37 at 9 of 41 draws; shard-weights maintenance note. `uv.lock` hdf5 extra committed separately. Written 2026-11-21 02:34.

## [2026-11-21] setup | Records: gaps 148, 147, 135, 134, 150, 154 closed; new gap 157
- Closed with green CI `tests` runs: 148 = P14-52 (`05a3f08`, KT count from the key log), 147 = P14-51 (`8ab2cb2`, toy models), 135 = P4-17 (`ae50049`, `fidetype live --source file`), 134 = P4-16 (`b73d9a7`, `edf` / `openbci-gui` readers `tested` on real files).
- 150 = P14-54 closed (pre-registration `09def1e`, results `2c0692f`): `coherence` offer gates for both `willett-hw` guards; gated offer control PASS (frame-shuffled 0 / 300, were 297 / 300 and 289 / 300; real 40 / 40); test real 77 / 80 offers kept. 3 of 4 packaged guards now pass the offer null control. [Results](../experiments/2026-11-21-p14-54-willett-order-gate/results.md).
- 154 = P2-14 closed: 13 consecutive green `tests` runs; slowest pytest job per run 11.4-12.9 min.
- Gap 151 = P14-55 done-when extended (new null types for the `coherence` gate). Gap 138 = P14-47: offers pass, still 0 commits. Gap 152 note: its `willett-hw` part met by gap 150. Roadmap P4-15 progress: catalogue 16 tested, 1 experimental.
- New gap 157 = [P4-18](questions/roadmap-standard.md#p4-18-openbci-gui-reader-on-a-real-gui-v5-recording-and-packet-drops) (OpenBCI GUI v5+ real recording, packet drops; low priority).
- Tracker: agent runs for P14-52, P14-51, P4-17, P4-16, P14-54 and the records passes `abc7781` and `774cbd9` (on M0-12). HANDOFF: offer_control recommendation updated (user decides); P15-37 at 25 of 41 draws; P11-17 agent working. Written 2026-11-21 05:24.

## [2026-11-21] setup | Records: gap 133 (P11-17) closed; EMG headline correction; new gaps 158-159
- 133 = P11-17 closed (plan `7922ecf`, code `eecbac8`, results `a0993be`): EMG L-FL safe WPM v0.1 with K = 40 calibration draws is 5.00 [0.00, 9.55] vs no-BCI 3.09 (P11-14 one calibration 6.80 [4.49, 9.63]); 9 / 40 draws above alpha earn 0; verdict "above, but inside the combined interval". [Results](../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md).
- EMG headline correction (same pattern as P15-29 for T15): README, overview, north star, index, [safe WPM write-up](questions/frontier-safe-wpm.md) (new P11-17 section), docs/safe-wpm.md 6b now say "6.80 [4.49, 9.63] with one calibration; 5.00 [0.00, 9.55] once the calibration draw is counted; above 3.09 on average, not reliably". Roadmap P11-14 and open-gaps rows got the same caveat. Card unchanged.
- New gaps 158 = [P11-18](questions/roadmap-standard.md#p11-18-why-225--of-the-emg-calibration-draws-are-above-alpha) (partition-only draws: why 22.5 % above alpha) and 159 = [P11-19](questions/roadmap-standard.md#p11-19-lower-variance-emg-l-fl-guard-with-a-calibration-inclusive-lower-end-above-no-bci) (lower-variance EMG guard; depends on gap 141). Notes on gaps 132 and 141.
- Tracker: P11-17 done with its agent run; P11-18, P11-19 todo; records pass `175c55a` on M0-12; P15-37 at 28 of 41 draws; agents working on P2-15 and P3-13. HANDOFF: user weekend list item (headline numbers changed for T15 and EMG). Written 2026-11-21 05:45.

## [2026-11-21] setup | Records: gaps 141 (P15-37), 132 (P15-34), 156 (P2-15) and 142 (P3-13) closed; gap 124 in progress; new gaps 160-163
- 141 = P15-37 closed (method + plan `4e81f16`, code `6de1779`, stage S + addendum `77c3df6`, results `105c5d0`) on the "which calibration size would be needed" branch: primary BMED-3 4.73 [2.60, 6.24] (criterion not met); A0 5.26 [2.95, 6.89]; R120 5.26 [2.94, 6.91]; multi-split cuts the between-draw SD only 4-15 %; about 2,760 calibration items (3.8 x `val_select`) needed. [Results](../experiments/2026-11-21-p15-37-multi-split/results.md).
- 132 = P15-34 closed (orchestrator decision) on its "numbers say why no such guard exists with the T15 data" branch. Its criterion branch (lower end above 4.0153) was NOT met. The goal continues in new gap 160 = [P15-39](questions/roadmap-standard.md#p15-39-labelled-t15-like-calibration-data-for-the-calibration-inclusive-safe-wpm) (labelled T15-like calibration data, externally blocked).
- 156 = P2-15 closed (commits `ee590af`, `03d2308`): `hybrid_setup` 121 -> 27.53 / 27.31 s, streaming setup 91 -> 22.85 / 20.88 s on windows py3.12 CI; exact. 124 = P2-13 in progress (commit `4f74ca2`, CI latency gate mode; 4 of 20 consecutive green CI runs).
- 142 = P3-13 closed (pre-registration `f7f66b0`, results `09d9eb7`): streaming per-user CRT in the decision loop, same decisions as the batch log-probs on 3,663 / 3,663 windows; safe WPM v0.1 3.37 [1.92, 5.18] certified; decision p95 8.02 ms (about 6 x under 50 ms). No new gap. [Results](../experiments/2026-11-21-p3-13-streaming-crt-loop/results.md).
- New gaps 160 = P15-39 (externally blocked), 161 = [P15-40](questions/roadmap-standard.md#p15-40-check-the-1n-assumption-of-the-calibration-size-projection) (1/sqrt(n) check), 162 = [P2-16](questions/roadmap-standard.md#p2-16-hybrid_setup-margin-under-25-s-on-windows-ci) (`hybrid_setup` margin), 163 = [P3-14](questions/roadmap-standard.md#p3-14-re-measure-the-implant-logits-latency-after-p2-15) (stale `implant-logits` latency tables). Gap 159 = P11-19 gets P15-37 as evidence, stays open.
- [Safe WPM write-up](questions/frontier-safe-wpm.md): new P15-34 / P15-37 section and "Still open" rows. HANDOFF: section 6b evidence (K >= 80, better 120; non-credited draw count; certified-only SD) added to user decision item 2.
- Tracker: P15-37, P2-15, P3-13 done and P2-13 in progress with their agent runs; P15-39 externally_blocked; P15-40, P2-16, P3-14 todo; records pass `857c878` on M0-12. Written 2026-11-21 07:48.

## [2026-11-21] setup | Records: gaps 158 (P11-18) and 126 (P11-16) closed; new gaps 164-166
- 158 = P11-18 closed (plan `6ce4245`, code `7537199` + fix `b70aac7`, results `0a75695`): partition-only EMG L-FL draws 3 / 40 above alpha (inside delta; bootstrap 9 / 40; pooled no-shift arm 0 / 40); interval 5.65 [0.00, 9.45] vs 3.09 ("above, but inside the combined interval"); verdict "partly duplicates" (Fisher p = 0.057); clear val / test session shift (Welch p = 3.6e-10). EMG public wording unchanged. [Results](../experiments/2026-11-21-p11-18-emg-above-alpha/results.md).
- 126 = P11-16 closed (plan `ded01cf`, code `0575c8a`, results `82a96bc` + `0d0107c`): EMG LX-FL prefix guard, proposed v0.2 9.47 [6.97, 12.75] with one calibration and 7.18 [0.00, 12.13] calibration-inclusive (7 / 40 draws above alpha); adopted v0.1 2.60 [1.35, 4.27]; H1-H3 and all controls pass. v0.2 stays proposed: no headline. [Results](../experiments/2026-11-21-p11-16-emg-prefix-confidence/results.md).
- New gaps 164 = [P11-20](questions/roadmap-standard.md#p11-20-shift-robust-calibration-for-the-emg-l-fl-guard) (shift-robust calibration for the L-FL guard; secondary K >= 80 arm P draws), 165 = [P5-35](questions/roadmap-standard.md#p5-35-native-calibrate-path-for-external-per-prefix-scores) (native `calibrate` path for external per-prefix scores), 166 = [P11-21](questions/roadmap-standard.md#p11-21-calibration-inclusive-lower-end-above-309-for-the-lx-fl-prefix-guard) (LX-FL calibration-inclusive lower end above 3.09). Notes on gaps 133 and 159.
- [Safe WPM write-up](questions/frontier-safe-wpm.md): one P11-18 sentence in the P11-17 section. HANDOFF: user decision item 2 gets the v0.2 card for EMG prefix guards and the section 6b method question (partition-only outer draws; 9 / 40 -> 3 / 40).
- Tracker: P11-18 and P11-16 done with their agent runs; P11-20, P11-21, P5-35 todo; records pass `37eccfe` on M0-12; P2-13 at 13 of 20 green CI runs; agent working on P15-40. Written 2026-11-21 08:57.

## [2026-11-21] setup | Records: gaps 165 (P5-35), 162 (P2-16), 124 (P2-13) and 157 (P4-18) closed; new gaps 167-168
- 165 = P5-35 closed (commit `c1f14e0`; CI `tests` run 44930128741 green): `fidetype.trust.FrozenPrefixScore` + `calibrate(..., commit_unit="prefix", prefix_score=...)`; the score digest enters the `config_id`. EMG LX-FL reproduced exactly (threshold 0.86; LTT 459 items, risk 0.03268, p 0.04882; 671 commits, 46 wrong; same decisions 1,221 / 1,221 for real, time-shuffled and zero EMG); `config_id` `tcfg-618d4ca57bb9326b`. The offer null control fails in warn mode (60 / 300 vs 157 / 459), noted in the closing row (no fitting open offer-gate gap). [Results](../experiments/2026-11-21-p5-35-external-prefix-score/results.md).
- 162 = P2-16 closed (commits `24b7cc7`, `873f068`): exact speed-ups (prefix-reuse beam search, `_viterbi_fast`); 16,488 randomised comparisons, 0 mismatches; `hybrid_setup` 21.06 / 14.58 / 20.99 s on windows py3.12 CI (was 27.5 s).
- 124 = P2-13 closed: 20 consecutive green `tests` runs since `4f74ca2` (44915291894 to 44928984469); 24 at this pass. The only attempt-2 run (44932516115) passed in attempt 1 too, so no failure is hidden.
- 157 = P4-18 closed by orchestrator decision (commit `300d44f`; CI `tests` run 44935694762 green): Cyton Sample Index drop check (default `on_drop="gap"`), two real GUI v5 files with seconds time stamps (GPL-3.0 Nepali file, 20 drops; CC BY 4.0 Mendeley cp586sfzrt v4, Marker Channel all zero). New gaps 167 = [P4-19](questions/roadmap-standard.md#p4-19-openbci-gui-reader-on-a-real-recording-with-non-zero-marker-channel-values) (real file with non-zero Marker Channel values, externally blocked) and 168 = [P4-20](questions/roadmap-standard.md#p4-20-sample-index-check-on-ganglion) (Ganglion Sample Index rule, low priority).
- [Safe WPM write-up](questions/frontier-safe-wpm.md) "Still open" table: row for closed gap 158 removed; rows for gaps 164 and 166 added; closed gap 96 taken out of the 95 / 96 row.
- Tracker: P5-35, P2-16, P2-13, P4-18 done with their agent runs; P4-19 externally_blocked; P4-20 todo; records pass `cfcf5d4` + `9e039c7` on M0-12. HANDOFF: agents working on P15-40 and P11-20; GPU paused. Written 2026-11-21 10:41.

## [2026-11-21] setup | Records: gaps 164 (P11-20) and 151 (P14-55) closed; new gaps 169-172
- 164 = P11-20 closed (plan `20b5993` before any number, code `d3511df`, results `8cbd7b7`): margin m = 0.0045 from sessions a -> b only, LTT at alpha' 0.0455; arm S 0 / 40 above alpha on test (P11-18: 3 / 40; McNemar p = 0.25); interval 6.13 [2.62, 9.47] vs 3.09 = "above, but inside the combined interval"; K = 80 partition-only 8 / 80, Fisher p = 0.060, "partly duplicates" not firm. EMG public wording unchanged. [Results](../experiments/2026-11-21-p11-20-emg-shift-robust/results.md).
- 151 = P14-55 closed (pre-registration `34f3553`, results `0188deb`): C5 time-shuffled 26 / 800 emit (CP95 0.0448), near-uniform 0 / 800, zero 0 / 80; no coefficient sign change in re-fits, `lo` -1.43 to 2.00; `coherence` offer gate rules C1-C6 pass for both guards; limit `rev_out` (77 / 80 and 78 / 80 offers). Nothing shipped changed. [Results](../experiments/2026-11-21-p14-55-willett-gate-robustness/results.md).
- New gaps 169 = [P11-22](questions/roadmap-standard.md#p11-22-firm-duplicates-verdict-for-the-emg-l-fl-calibration-draws) (firm "duplicates" verdict, low priority), 170 = [P11-23](questions/roadmap-standard.md#p11-23-robustness-of-the-emg-shift-margin-across-session-steps) (shift margin across session steps), 171 = [P14-57](questions/roadmap-standard.md#p14-57-direction-aware-offer-check-for-willett-hw) (direction-aware offer check, low priority), 172 = [P14-58](questions/roadmap-standard.md#p14-58-c5-threshold-rule-without-the-minimum-real-score) (C5 threshold rule without the minimum real score, low priority). Notes on gaps 159 and 138.
- [Safe WPM write-up](questions/frontier-safe-wpm.md): one P11-20 sentence in the P11-17 section; "Still open" table: row 164 removed, rows 169 and 170 added. HANDOFF: user decision item 2 gets the optional shift-margin mention.
- Tracker: P11-20 and P14-55 done with their agent runs; P11-22, P11-23, P14-57, P14-58 todo; records pass `3d8d1e4` on M0-12. HANDOFF: GPU free again; agents working on P15-35 (GPU) and P15-40 (CPU); P15-36 waits on P15-35. Written 2026-11-21 12:14.

## [2026-11-21] setup | Records: gaps 161 (P15-40), 170 (P11-23) and 33 (P6-10) closed; new gaps 173-175
- 161 = P15-40 closed (plan `f83397a`, code and addendum `1d64217`, results `23ae9bd`): D2 between-draw SDs 1.234 / 1.089 / 0.884 at n = 361 / 481 / 722; b_D2 = 0.48 [0.12, 0.83], consistent with 1/sqrt(n); revised n* about 2,520 [1,080, 460,000] (P15-37: 2,764); D1 b = 0.75 gives n*_A about 1,770. The mean is not fixed below 722. The P15-37 decision stands; a tighter exponent folds into gap 160 (P15-39). [Results](../experiments/2026-11-21-p15-40-sqrt-n-check/results.md).
- 170 = P11-23 closed (plan `a03b20c` before any number, code `75e9689`, results `8c2298a`; X6 40 / 40): m2 = 0.0185, alpha'' 0.0314; "the one-step margin of P11-20 under-states the spread"; arm S2 0 / 40 above alpha; interval 5.47 [2.44, 8.77] vs 3.09 = "above, but inside the combined interval"; commits 245 -> 206, safe WPM 6.13 -> 5.47. EMG public wording unchanged. [Results](../experiments/2026-11-21-p11-23-shift-margin-steps/results.md).
- 33 = P6-10 closed (commit `ddb0be3`): `training_data` declaration, overlap check by id / hash-only HDF5 map / text hash, card key `overlap_check`, `--fail-on-overlap`, board marks, CLI `overlap-hashes` / `overlap-list`, 9 tests. Retro check on 36 cards (none changed): no id overlap; M4-12 / M4-13 overlap by text on 16 / 103 units; 8 entries not checked. Deviation: a missing declaration reads "not checked". [Results](../experiments/2026-11-21-p6-10-overlap-check/results.md).
- New gaps 173 = [P11-24](questions/roadmap-standard.md#p11-24-tell-the-two-emg-shift-margins-apart-on-held-out-users-or-new-sessions) (tell the two shift margins apart; may be externally limited by data), 174 = [P6-11](questions/roadmap-standard.md#p6-11-text-overlap-rule-for-tracks-whose-sentences-repeat-by-design) (text-overlap rule; P6-09 now depends on it), 175 = [P6-12](questions/roadmap-standard.md#p6-12-training-data-of-the-published-card-et-al-2024-decoder-for-the-overlap-check) (training data of the published Card et al. 2024 decoder; may be externally limited).
- Gap 139 = P15-35 now `in_progress` (attempt 1 results `6cf8466`: no eligible recipe; attempt 2 = P15-35b, pre-registration `3a95935`, GPU job running). Gap 160 row and P15-39 get the P15-40 evidence. [Safe WPM write-up](questions/frontier-safe-wpm.md): P11-23 and P15-40 sentences; "Still open" rows 161 and 170 removed, row 173 added.
- Tracker: P15-40, P11-23, P6-10 done with their agent runs (P11-23 run 1 usage unknown); P15-35 in_progress; P11-24, P6-11, P6-12 todo; records pass `6e7910a` on M0-12. HANDOFF: only the P15-35b GPU job runs; P15-36 next on the GPU. Written 2026-11-21 15:30.

## [2026-11-21] setup | Records: gap 85 (P13-13) closed; P15-35b GPU job paused
- 85 = P13-13 closed (commit `1168b34`): All 30 pre-P5-23 trust cards (b2t25-t15 ours / published, spanishbcbl-meg, toronto-semg; v0.1 / v0.2 pairs) were refit with the build-step settings and frozen in 15 configs. A pipeline built from the loaded file alone gives the same decisions as each card (0 differences on real input and on both controls). Thresholds and calibration scores are equal; no headline number changed. Every trust card now has `config_id` + `config_id_source`. The new `config_id_problems` check and tests (`tests/test_hub_cli.py`) flag any future trust card without a valid `config_id`. Limit: the toronto v0.1 cards hold only aggregates, so they are checked by commit count; their v0.2 twins are checked per unit. No new gaps.
- Gap 139 = P15-35 stays `in_progress`: the P15-35b GPU job is paused at the user's request (15:49:08; `latest.pt` at step 1347 of arm F-R20/E-b30-s0; arm F+100 finished all 4000 steps; 2.54 GPU h so far); exact resume from the `stop` file. P15-36 (gap 140) waits on it.
- Tracker: P13-13 done with its agent run; P15-35 notes get the pause; records pass `a530a17` on M0-12. HANDOFF: no job runs; P15-35b row PAUSED (user request). Written 2026-11-21 16:15.

## [2026-11-21] ingest | emg2qwerty paper
- P11-10 (gap 90). Raw: `references/papers/emg2qwerty_sivakumar_2024_arxiv_2410.20081.pdf` (arXiv 2410.20081 v3, 17 pages, git-ignored) + pdftotext `.txt`; catalogue row in `references/README.md`. Paper licence CC BY-NC-SA 4.0 (arXiv page).
- New [source page](sources/emg2qwerty.md): 108 users, 1,135 sessions, 346.4 h, 5,262,671 keystrokes (Table 2, p. 5); keylogger labels only; 8 held-out test users (2 val + 2 test sessions each), generic model on 100 users; TDS ConvNet + CTC, 900 ms past / 100 ms future context; Table 3 (p. 9) fine-tuned test CER 11.28 % no LM / 6.95 % with 6-gram char LM, generic 55.38 / 51.78; usable at about 10 % CER or less (p. 9); sEMG-RD is proprietary (p. 9).
- Contradictions recorded: (1) Brain2Qwerty v2 says emg2qwerty used a causal Conformer for handwriting; the paper has a TDS ConvNet for typing with 100 ms lookahead ([v2](sources/brain2qwerty-v2.md), [sync vs async](concepts/synchronous-vs-asynchronous-decoding.md), [entity](entities/emg2qwerty.md)). (2) Licence: README CC BY-NC 4.0 vs paper, `LICENSE` file and arXiv CC BY-NC-SA 4.0; README is the outlier ([public datasets](questions/public-datasets.md), [Meta Neural Band](entities/meta-neural-band.md), [landscape](sources/neural-input-landscape-2026.md)). (3) "Affordable hardware" vs proprietary sEMG-RD ([research directions](questions/research-directions.md), [EEG](concepts/eeg.md), entity).
- Updated: [entity](entities/emg2qwerty.md) (partial banner and `paper-not-ingested` tag removed; hedged facts confirmed), [CTC](concepts/ctc.md) (new emg2qwerty section), [frontier decoder quality](questions/frontier-decoder-quality.md) (10 % usability line), [Meta FAIR](entities/meta-fair-brain-ai.md), [open gaps](questions/open-gaps.md) (P11-07 note: 10.10 % is a with-LM value, fair comparison 6.95 %), index.
- [P11-01 results](../experiments/2026-11-16-p11-01-emg-decoder/results.md): appended "Correction 2026-11-21 (P11-10)": 15.09 % is above the paper's usability line, so the decoder can run live but is not usable as is; link to the source page.

## [2026-11-21] setup | Records: gaps 110 (P4-15) and 90 (P11-10) closed; P15-35b GPU job resumed
- 110 = P4-15 closed (commit `ffc74f4`; CI `tests` and `tutorials` green on `ffc74f4`): Each `ADAPTER_INFO` declares `support` (real-device / replay-only / synthetic-only; planned = untested), `real_data_evidence`, `transport`, `test_covers` and `limits`. The registry refuses unbacked claims. `python -m fidetype.adapters.registry` generates [docs/device-support.md](../docs/device-support.md) (0 real device, 14 replay only, 3 synthetic only, 16 untested), and `--check` plus `tests/test_adapter_registry.py` (21 tests) fail when it is stale. Registry schema 0.2.
- 90 = P11-10 closed (commit `70807b0`): emg2qwerty paper ingested ([source page](sources/emg2qwerty.md)). 108 users, 346.4 h, keylogger labels. Table 3 p. 9: fine-tuned 11.28 % no LM / 6.95 % with LM; the paper calls about 10 % CER or less usable. Contradictions recorded: the Brain2Qwerty v2 "causal Conformer" (the paper uses a TDS ConvNet with 100 ms future context in training), the licence (the paper says CC BY-NC-SA 4.0; the repo README says CC BY-NC 4.0), and "affordable hardware" (the sEMG-RD is proprietary). The P11-01 "usable as is" claim got a dated correction note. The P11-07 comparison in the open-gap list now uses 6.95 % for with-LM.
- New gaps 176 = [P4-21](questions/roadmap-standard.md#p4-21-nts-over-lsl-transport-on-real-decoder-output) (NTS over LSL on real decoder output), 177 = [P4-22](questions/roadmap-standard.md#p4-22-text-nbest-csv-and-json-lines-readers-on-real-decoder-output-files) (`text-nbest` file readers on real decoder output), 178 = [P11-25](questions/roadmap-standard.md#p11-25-revisit-the-p11-08-decoder-target-framing) (matched decoder target for P11-08 / gap 88: no-LM vs LM, lookahead, the about 10 % usability line), 179 = [P11-26](questions/roadmap-standard.md#p11-26-check-the-ctrl-labs-2024-generic-neuromotor-paper) (check the CTRL-labs 2024 generic neuromotor paper; low priority). P11-08 and gap 88 get a pointer to gap 178.
- Gap 139 = P15-35 stays `in_progress`: the user allowed the GPU again, and the P15-35b GPU job was resumed at 16:16 (launcher pid 26708, worker pid 19728), exactly at step 1347 of arm F-R20/E-b30-s0. At 17:30: arm F+50/E-b30-s0-labelshuf, step 2500 / 4000, 0.51 s/step, 3.78 GPU h (cap 8.0 h). P15-36 (gap 140) waits on it.
- Tracker: P4-15 and P11-10 done with their agent runs; P4-21, P4-22, P11-25, P11-26 todo; P15-35 notes get the resume; records pass `b342119` on M0-12. HANDOFF: P15-35b row RUNNING. Written 2026-11-21 17:35.

## [2026-11-21] query | EMG decoder target restated (P11-25)
- New section [matched EMG decoder target](questions/frontier-decoder-quality.md#matched-emg-decoder-target-p11-25-2026-11-21). Bar 1: compare an EMG CER only with the published number of the same condition (emg2qwerty paper Table 3, p. 9; all published numbers have 100 ms lookahead and whole-session decoding): no LM 11.28 %, 6-gram char LM 6.95 %. No published number exists for a causal decoder. Bar 2 (separate): usability, CER at or below about 10 % (p. 9).
- Our numbers: P11-01 15.09 % (no LM, causal; indicative +3.81 points vs 11.28 %); P11-07 10.10 % (LM, causal, beam 8; indicative +3.15 points vs 6.95 %; at the usability line, beam 64 9.13 % below). No matched number exists yet; a no-LM 100 ms lookahead run (P11-08) would give the first.
- Fixed comparisons: [P11-07 results](../experiments/2026-11-20-p11-07-emg-beam-lm/results.md) got "Correction 2026-11-21 (P11-25)" (H2 compared the with-LM 10.10 % with the no-LM 11.28 %); frontier decoder quality "useful range" take corrected (useful for trust tests, not usable for typing); frontier-safe-wpm EMG bullet now names the FL decoder (10.88 %) and its matched reference.
- [P11-08](questions/roadmap-standard.md#p11-08-emg-decoder-accuracy-to-the-published-fine-tuned-no-lm-cer) done-when restated (original kept, dated); gap 88 row restated in [open gaps](questions/open-gaps.md); tracker P11-08 notes updated. Links to the rule from the [emg2qwerty entity](entities/emg2qwerty.md), [source page](sources/emg2qwerty.md) and [overview](overview.md).
- Gap 178 = P11-25 done (status set in place in the open-gap table; the orchestrator may move the row to "Closed gaps").

## [2026-11-21] setup | Records: gaps 166 (P11-21) and 178 (P11-25) closed; first public release in progress
- 166 = P11-21 closed (plan `95b1a91` before any number, code `beac437`, amendment 1 + code `99b7eb6`, analysis fix `fef0abb`, results `ecbc7b1`; [results](../experiments/2026-11-21-p11-21-lx-margin/results.md)): EMG LX-FL prefix guard with partition-only draws and an LX shift margin (m_LX 0.0288, alpha_LX 0.0212). Calibration-inclusive PROPOSED v0.2 5.67 [3.43, 8.26] vs no-BCI 3.09, "clearly above after calibration uncertainty" (first EMG lower end above 3.09; narrow: +0.34, one draw 2.96). 0 / 40 above alpha. LX-T 7.21 [4.78, 10.43]; LX-P 8.80 [4.89, 12.26] (1 / 40). H3 Fisher p = 0.028. Holds only under the proposed v0.2 and assumption (A2). Disclosed deviation: X2 -> X2' (Amendment 1). [Frontier safe WPM](questions/frontier-safe-wpm.md) EMG section and "Still open" table updated; public EMG wording unchanged (user decision, HANDOFF item 3).
- 178 = P11-25 closed (commit `eb09ea7`): the row was set `done` in place by the P11-25 agent; this pass moved it to "Closed gaps" in [open gaps](questions/open-gaps.md) and added a Notes line.
- New gap 180 = [P11-27](questions/roadmap-standard.md#p11-27-native-n-best-score-differences-in-the-p11-20--p11-23-analyser-memos) (why the P11-20 / P11-23 memos hold native n-best scores up to 8e-5 off fresh decodes in 203 / 2,442 windows; low priority). Gap 159 stays open.
- First public release 0.1.0 in progress: D1-D9 "all recommended" (D6 kept as is); release commit `6579534` (CI 31 / 31 green); tags `py-v0.1.0`, `ts-v0.1.0`, `rs-v0.1.0` pushed at the user's request (about 19:12). P2-07 and M7-09 set `in_progress`; the uploads are the user's. [Roadmap P2-08](questions/roadmap-standard.md#p2-08-publishing-prep-for-the-first-release) got a release progress line.
- Gap 139 = P15-35 stays `in_progress`: P15-35b runs (19:13: arm A4K/E-b30-s0, step 1400 / 4000, 5.50 GPU h, cap 8.0 h).
- Tracker: P11-21 done (agent run + detached run), P11-25 agent run, P11-27 todo, release agent runs on M7-09, records pass `3df2512` on M0-12. HANDOFF: output style rule (HTML page with pictures first). Written 2026-11-21 19:20.

## [2026-11-21] setup | First public release 0.1.0 (PyPI, npm, crates.io, Pages, GitHub releases)
- Release 0.1.0 is complete (publishing checklist step I-4). Tags `py-v0.1.0`, `ts-v0.1.0`, `rs-v0.1.0` on release commit `6579534` (CI 31 / 31 green), pushed at about 19:12.
- PyPI: [fidetype 0.1.0](https://pypi.org/project/fidetype/) by `release.yml` with trusted publishing (OIDC) and a provenance attestation, after a TestPyPI rehearsal. Clean installs give 0.1.0 and conformance fep-0001 66 / 66.
- npm: [@fidetype/sdk 0.1.0](https://www.npmjs.com/package/@fidetype/sdk) by `release.yml` with a one-time token in environment `release-npm`, SLSA provenance. Clean install OK. The "bin ... invalid and removed" warning is misleading (path normalisation only); follow-up `npm pkg fix`, low priority.
- crates.io: [fidetype 0.1.0](https://crates.io/crates/fidetype), [docs.rs](https://docs.rs/fidetype/0.1.0) built; one-time token in environment `release-crates` (`70bdb3a`).
- Site live at https://zhangzibo.github.io/fidetype/. User decision: auto-deploy on every push to `main` (`f64b65a`); package uploads stay manual-only. D6: the progress dashboard is public. D1-D9 decided "all recommended".
- GitHub releases py-v0.1.0 (Latest), ts-v0.1.0, rs-v0.1.0, with notes from the 0.1.0 changelog entries. The changelogs have an empty `## [Unreleased]`.
- Next release: the npm and crates.io trusted publishers are not set; the one-time tokens expire on 2026-11-28 (user decision: no clean-up). See [RELEASING.md](../docs/RELEASING.md) 3.1.
- Tracker: P2-07, M7-09, M7-08 done; notes on P2-06 (vcpkg/Conan, NuGet, Maven still open), P13-08, P8-01, P8-05, M3-05; P15-35 note: P15-35b FINISHED 19:55:02 (ALL DONE, 6.197 GPU h; readout not done yet); records pass `2f4ca6d` on M0-12. Dashboard 320 / 450 done. [Roadmap P2](questions/roadmap-standard.md#p2-reference-sdks), P2-08 and P13-08 got status lines. Optional, not done: repository "About" link (user), pretrained weights (P14-02). Written 2026-11-21 21:05.

## [2026-11-22] ingest | Generic neuromotor interface (CTRL-labs, Nature 2025); "causal Conformer" verdict (gap 179 / P11-26)
- New source page [generic-neuromotor-interface](sources/generic-neuromotor-interface.md). Nature 645, 702–711 (2025), CC BY-NC-ND 4.0. We read the Nature open-access PDF; the bioRxiv preprint was not read (HTTP 429). Raw PDF + txt in `references/papers/` (git-ignored); row in `references/README.md`.
- Handwriting decoder: MPF features, 15-layer Conformer, causal by past-only local attention (window 16, then 8), CTC + FastEmit, greedy (Methods, PDF pp. 15–16). Closed loop 20.9 WPM; personalisation 16 % (Fig. 5c).
- Verdict: **confusion confirmed.** Brain2Qwerty v2 (p. 10) writes "causal Conformer with low-latency to decode handwriting (Sivakumar et al., 2024)"; its reference list resolves that to emg2qwerty (p. 19). emg2qwerty has a TDS ConvNet for typing; the CTRL-labs paper has the causal Conformer for handwriting. v2 does not cite the CTRL-labs paper. All eight emg2qwerty authors are CTRL-labs co-authors (PDF p. 10).
- Updated with the verdict: [Brain2Qwerty v2](sources/brain2qwerty-v2.md), [emg2qwerty (paper)](sources/emg2qwerty.md), [emg2qwerty (entity)](entities/emg2qwerty.md), [sync vs async decoding](concepts/synchronous-vs-asynchronous-decoding.md). Cross-links added in [Meta Neural Band](entities/meta-neural-band.md), [data scaling](concepts/data-scaling.md), [public datasets](questions/public-datasets.md), [index](index.md).
- New contradiction (licence): the paper says data and code are CC BY-NC-SA 4.0 (PDF p. 20); the repo README and `LICENSE` say CC BY-NC 4.0. Both NC. We follow BY-NC-SA.

## [2026-11-22] setup | Records: gaps 139, 140, 159, 171, 172, 176, 177, 179 closed; new gaps 181-188
- 139 = [P15-35](questions/roadmap-standard.md#p15-35-e1-synthetic-sentence-augmentation-for-the-minutes-scale-recipe-test-c2) closed (results `e9699a7`): F-R20 passes val-C2 with the margin (0.897 vs 0.875) and test C2 (0.877 vs 0.847); seed-1 C2 passes inside P15-36 (0.870 vs 0.803).
- 140 = [P15-36](questions/roadmap-standard.md#p15-36-e1-budget-matched-recipe-so-that-v1-and-h1-h4-are-valid) closed (plan `8790238`, code `81ba625`, results `01ee3b9`): val-only rule F-R20 at 3 / 10 / 30 min, E1a at 100 min / all; V1, C1, C2 (2 seeds) pass; H1-H4 each partial; 6.00 GPU h. P15-08 stays `in_progress` (KT-sEMG arm).
- 159 = [P11-19](questions/roadmap-standard.md#p11-19-lower-variance-emg-l-fl-guard-with-a-calibration-inclusive-lower-end-above-no-bci) closed (results `749f192`): BX3 5.90 [3.45, 8.89] vs 3.09 under v0.1 (narrow, +0.36); BD3 5.19 [2.90, 8.19] and AN3 4.37 [2.17, 7.28] not above; max test rate 0.0434. Gap 180 (P11-27) gets new evidence and stays open.
- 171 = P14-57 closed as a negative result; 172 = P14-58 closed as a pass (`lo_new` 0.5659: 0 / 800 new time-shuffled emits, real gated 3 / 80); nothing shipped (results `71f954e`).
- 179 = P11-26 closed (`aab52bd`; the ingest entry above has the details).
- 176 = P4-21 and 177 = P4-22 closed (plans `6039ad0`, results `bd597d7`): 816 / 816 real B2T '25 decisions over LSL equal in-process and batch; `lsl` now replay-only; `text-nbest` readers on real decoder output, exact round trip. Matrix 0 / 15 / 2 / 16.
- New gaps in [open gaps](questions/open-gaps.md): 181 = P5-36 (frame-order integrity check), 182 = P14-59 (ship `lo_new`, user decision), 183 = P11-28 (BX3 headroom), 184 = P15-41 (more F-R20 seeds), 185 = P15-42 (better R / S aligners), 186 = P4-23 (LSL across two hosts + paced latency), 187 = P4-24 (frames-route decisions over LSL), 188 = P4-25 (CSV reader on a third-party file).
- [Safe WPM write-up](questions/frontier-safe-wpm.md): P11-19 bullet; gap 159 left "Still open", gap 183 added. Tracker: agent-run rows (records pass `8b74c7e`, gap 139 write-up, P15-36 x 3 + GPU clock, P14-57/58, P11-19 x 2 + CPU run, P11-26, P4-21/22). HANDOFF: user decision list extended (EMG wording now has two results, ship `lo_new`, v0.2, P2-11, hub Q1-Q7, D10-D12). Dashboard 328 / 458 done. Written 2026-11-22 09:40.

## [2026-11-22] setup | Records: gaps 183, 184 closed; gap 181 in progress; new gaps 189-195
- 183 = [P11-28](questions/roadmap-standard.md#p11-28-safety-headroom-of-the-emg-bx3-guard) closed (plan `84d465f`, code `a8877bf`, amendment 1 `bf06ee9`, results `75ae30f`): "BX3 safety holds with headroom". 0 / 80 draws above 0.05 (CP95 0.0368); 90th-percentile bound 0.0393, headroom 0.0107; new 40 draws 5.99 [3.52, 8.96], pooled 5.95 [3.49, 8.92] vs no-BCI 3.09; 31 / 80 above 0.0314. One test set of 8 users.
- 184 = [P15-41](questions/roadmap-standard.md#p15-41-more-seeds-of-the-f-r20-recipe-at-minutes-scale) closed as a negative result (plan `043486f`, code `8f70f1e`, results `02aa679`; 7.82 GPU h): H1 fails on 5 seeds (10 min d 0.038 [−0.004, 0.081]; 30 min −0.002 [−0.034, 0.031]); the 3-min win 0.095 [0.066, 0.124] has no valid control; C2 at 10 min fails on seeds 2-4. H2-H4 go to gap 185. P15-08 stays `in_progress`.
- 181 = [P5-36](questions/roadmap-standard.md#p5-36-frame-order-integrity-check-in-the-trust-layer) now `in_progress`, still open (P5-36 `a705a75` / `6f45faf`; P5-36b `dab694f` / `a7bfbc8`): integrity check passes I1-I3 (240 / 240 faults caught, 0 / 160 false flags); `lm_direction` gate fails (10 / 80, 10 / 80); the two-direction LM-beam score passes for the LM guard (0 / 80, 4 / 80) and fails B2 for the built-in guard (1 / 80, 6 / 80; `tau` 0.326). Scope question (b) is moot (the user chose route 3).
- 180 = P11-27 gets new evidence (P11-28: L-model parameters differ by about 1e-8 between memo and fresh decode; no decision change). Stays open.
- New gaps in [open gaps](questions/open-gaps.md): 189 = P5-37 (fixed-threshold-0 `lm_beam_direction` rule on unused data), 190 = P14-60 (ship the direction gate if 189 passes), 191 = P5-38 (faster direction gate, low priority), 192 = P4-26 (optional: `frame_times=` through the device adapters), 193 = P11-29 (BX3 headroom on a new session, low priority), 194 = P15-43 (C2 at 30 min for seeds 2-4 + smallest budget where C2 passes on every seed), 195 = P15-44 (`control_flags` label, low priority).
- [Safe WPM write-up](questions/frontier-safe-wpm.md): P11-28 bullet; gap 183 row replaced by gap 193. [North star](questions/north-star.md): E1 row gets the P15-36 and P15-41 lines. Tracker: agent-run rows (records pass `1c0c691`, P11-28 x 2 + CPU run, P5-36, P5-36b, P15-41 x 2 + GPU job). Dashboard 330 / 465 done.

## [2026-11-22] setup | Decision: EMG headline wording (user, 2026-11-22)
- The user adopted the EMG headline: "EMG typing with the trust layer is above the no-BCI baseline after calibration uncertainty, narrowly, for one sentence guard (BX3, safe-WPM v0.1: 5.90 [3.45, 8.89] vs 3.09; replicated 5.99 [3.52, 8.96] with safety headroom 0.0107 in P11-28), on 8 users and one test set." Short form: "EMG: above no-BCI, narrowly, for one sentence guard (8 users, one test set)." It replaces "above on average, not reliably" for EMG. The T15 wording does not change.
- Updated: README (safe WPM paragraph), [overview](overview.md), [north star](questions/north-star.md) (safe WPM row), [index](index.md) (safe WPM row), [safe WPM write-up](questions/frontier-safe-wpm.md) (short answer, P11-21 and P11-19 bullets, limits), `docs/safe-wpm.md` 6b (new bullet). Each cites the P11-19 and P11-28 results. The prefix-guard result 5.67 [3.43, 8.26] (P11-21) is labelled proposed safe-WPM v0.2 only.
- HANDOFF: EMG headline marked DECIDED (user, 2026-11-22) with the adopted text; the npm / crates token expiry (2026-11-28) moved out of the user decision list to a plain note (the user handles renewal). Tracker: R-27. Dashboard 331 / 466 done. No roadmap item moved.
