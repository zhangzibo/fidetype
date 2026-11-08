# HANDOFF: where are we

This file tells a new Claude Code session where the last session stopped. The orchestrator updates it after each finished task.

Last update: 2026-11-08 (M0 closed).

## Project in one paragraph
**Fidetype** is an open trust layer for neural text entry. It was first called "neurotext" (a placeholder name). It lives in the GitHub repo https://github.com/zhangzibo/fidetype (renamed from `stealth-project` on 2026-11-08). The local folder is still named `stealth-project`. The project started on 2026-11-07 from Meta FAIR's Brain2Qwerty (MEG typing decoding). Fidetype adds calibration, abstention and provenance on top of brain-to-text decoders. It works with public datasets, because the user has no MEG or EEG hardware.

## Read first
1. `CLAUDE.md`: the schema, the working mode and the rules.
2. `wiki/index.md`: the catalogue of all wiki pages.
3. `wiki/questions/project-plan.md`: milestones M0-M7.
4. `wiki/progress/index.html`: the progress dashboard. Its source is `wiki/progress/tracker.json`.
5. `agent-memory/MEMORY.md`: a mirror of Claude's memory notes.

## Working rules in brief
- The main chat is the **orchestrator**. Subagents do all actual work.
- Write in **"80% ASD-STE100"** style: short sentences, active voice, simple words.
- Diagrams go in `wiki/diagrams/` (draw.io + `slides.json`, then `node tools/drawio/build.js`).
- The **orchestrator decides commits** and pushes. Never commit third-party code, PDFs, data or secrets.
- Record **every task** in `wiki/progress/tracker.json`. Then run `node tools/progress/build.js`.
- Run **long jobs detached**, with checkpoints and a log file.

## Background processes
| Process | Check | Stop | Resume |
|---|---|---|---|
| SpanishBCBL MEG download: [130/316] files at 00:43 on 2026-11-08 (S5 done, S10 started) | `tail C:\Users\zhang\bci-data\SpanishBCBL\_download.log`; `tasklist /FI "PID eq 37808"` | `taskkill /PID 37808 /T /F` | Rerun `C:\Users\zhang\bci-data\SpanishBCBL\_download_meg.sh` |
| Static server, http://localhost:8000 | `tasklist /FI "PID eq 50528"` or open the URL | `taskkill /PID 50528 /F` | `node tools/serve.js` (it stops at reboot) |

Note: PIDs change after a restart. Note: `tools/serve.js` is tracked in git, so a fresh clone has it.

## Current status (from tracker.json)
- **M0 Setup: done on 2026-11-08** (target 11-09). Only the bulk MEG download (M0-02) still runs, in the background. M1-M7 target: 2026-11-15.
- **GPU env:** native Windows ROCm 7.2.1 + torch 2.9.1 at `C:\venvs\fidetype-rocm`. Use `C:\venvs\fidetype-rocm\Scripts\python.exe` for all torch work. The repo `.venv` is CPU-only: it is for tests and CI. Rebuild the GPU env with `tools/env/setup_rocm.ps1`. Details: `wiki/questions/compute-setup.md`.
- **CI:** GitHub Actions (`.github/workflows/tests.yml`) runs pytest on CPU. Green.
- **S25 inspection: done.** S25 loads in MNE. Head digitisation is present. The key triggers align with the log to < 1 ms after a per-block drift fit. Results: `experiments/2026-11-08-inspect-spanishbcbl/results.md`. Summary: `wiki/entities/spanishbcbl-dataset.md` ("Inspection findings").
- **Also done:** package skeleton, NeuralTextStream spec v0.1, noisy-decoder simulator (41 tests), progress tracker, session continuity, project name (Fidetype), README, GitHub repo renamed to `zhangzibo/fidetype`.
- **Pending user decision:** enable Claude Code hooks for automatic snapshots, or not.

## Next steps: M1, the baseline decoder (target 11-09 → 11-11)
1. **Data loader** in `src/fidetype/data/`. Our own code: copy no Meta code (CC BY-NC). It implements the alignment method from the S25 inspection (drop the test ramp, match code sequences, fit offset + drift per block, check by time), the keystroke labels, and the typed-vs-target alignment. It must handle the messy file names and duplicate folders.
2. **Preprocessing pipeline:** bad channels (`find_bad_channels_maxwell`) → tSSS → notch 50/100 Hz → band-pass 0.5–45 Hz → resample to 100 Hz.
3. **Conv + CTC decoder** in `src/fidetype/decoders/`. Train it in the GPU env, with checkpoints every few minutes, as a detached process with a log file. Add it to "Background processes".
4. Make the decoder **emit NeuralTextStream**.
5. Add a **character n-gram LM with beam search**. Report greedy CER and beam CER on fixed splits.
6. M2 (trust core v0) can start in parallel on the simulator.
7. Optional: rename the local folder to `fidetype`. Do this only BETWEEN sessions (see below).

## Optional: rename the local folder to fidetype
The Claude memory folder slug (`~/.claude/projects/C--Users-zhang-OneDrive-Documents-GitHub-stealth-project/`) and `tools/session/snapshot.js` depend on the folder path. So do this only when no Claude session is open and no job writes into the repo.
1. Close all Claude Code sessions and editors that use the folder.
2. Rename `C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project` to `...\GitHub\fidetype`.
3. Rename `~/.claude/projects/C--Users-zhang-OneDrive-Documents-GitHub-stealth-project` to `~/.claude/projects/C--Users-zhang-OneDrive-Documents-GitHub-fidetype` (keeps the memory notes and the session history).
4. In `tools/session/snapshot.js`, change the `SLUG` constant to `C--Users-zhang-OneDrive-Documents-GitHub-fidetype`.
5. Start Claude Code in the new folder. Run `node tools/session/snapshot.js` and check that `agent-memory/` is unchanged. Commit the script change.

## How to resume
- In the repo folder, run `claude --continue`. Or start a new session and say "read HANDOFF.md".
- Run `node tools/session/start.js` for a short resume summary.
- Run `node tools/session/snapshot.js` to refresh `agent-memory/` from `~/.claude/...`.
- The orchestrator updates this file after each finished task.
