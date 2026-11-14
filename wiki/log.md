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
