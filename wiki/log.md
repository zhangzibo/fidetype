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
