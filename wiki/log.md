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
