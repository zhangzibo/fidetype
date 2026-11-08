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
