# HANDOFF: where are we

This file tells a new Claude Code session where the last session stopped. The orchestrator updates it after each finished task.

Last update: 2026-11-08.

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
| SpanishBCBL MEG download | `tail C:\Users\zhang\bci-data\SpanishBCBL\_download.log`; `tasklist /FI "PID eq 37808"` | `taskkill /PID 37808 /T /F` | Rerun `C:\Users\zhang\bci-data\SpanishBCBL\_download_meg.sh` |
| Static server, http://localhost:8000 | `tasklist /FI "PID eq 50528"` or open the URL | `taskkill /PID 50528 /F` | `node tools/serve.js` (it stops at reboot) |

Note: PIDs change after a restart. Note: `tools/serve.js` is tracked in git, so a fresh clone has it.

## Current status (from tracker.json)
- **M0 Setup: in progress.** Target: 2026-11-09. M1-M7 target: 2026-11-15.
- **Done:** Python package skeleton, NeuralTextStream spec v0.1, noisy-decoder simulator (41 tests), progress tracker, session continuity (HANDOFF.md, agent-memory mirror, snapshot script), project name decided (Fidetype), package rename + README rewrite, GitHub repo renamed to `zhangzibo/fidetype`.
- **Running:** SpanishBCBL MEG download (M0-02): [107/316] files at 00:22 on 2026-11-08. GPU/PyTorch test (M0-01, an agent).
- **To do:** inspect one subject in MNE (M0-03); CI with GitHub Actions (M0-09); the M1 baseline decoder; optional local folder rename (see below).
- **Pending user decision:** enable Claude Code hooks for automatic snapshots, or not.

## Next steps
1. When the download ends, load one subject in MNE. Check for head digitisation.
2. Record the GPU/PyTorch result (ROCm, WSL2 + ROCm, DirectML or cloud).
3. Add CI: GitHub Actions runs pytest on CPU.
4. Close M0. Start M1 (baseline decoder) and M2 (trust core v0).
5. Optional: rename the local folder to `fidetype`. Do this only BETWEEN sessions (see below).

## Optional: rename the local folder to fidetype
The Claude memory folder slug (`~/.claude/projects/C--Users-zhang-OneDrive-Documents-GitHub-stealth-project/`) and `tools/session/snapshot.js` depend on the folder path. So do this only when no Claude session is open and no job writes into the repo.
1. Close all Claude Code sessions and editors that use the folder.
2. Rename `C:UserszhangOneDriveDocumentsGitHubstealth-project` to `...GitHubidetype`.
3. Rename `~/.claude/projects/C--Users-zhang-OneDrive-Documents-GitHub-stealth-project` to `~/.claude/projects/C--Users-zhang-OneDrive-Documents-GitHub-fidetype` (keeps the memory notes and the session history).
4. In `tools/session/snapshot.js`, change the `SLUG` constant to `C--Users-zhang-OneDrive-Documents-GitHub-fidetype`.
5. Start Claude Code in the new folder. Run `node tools/session/snapshot.js` and check that `agent-memory/` is unchanged. Commit the script change.

## How to resume
- In the repo folder, run `claude --continue`. Or start a new session and say "read HANDOFF.md".
- Run `node tools/session/start.js` for a short resume summary.
- Run `node tools/session/snapshot.js` to refresh `agent-memory/` from `~/.claude/...`.
- The orchestrator updates this file after each finished task.
