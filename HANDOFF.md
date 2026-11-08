# HANDOFF: where are we

This file tells a new Claude Code session where the last session stopped. The orchestrator updates it after each finished task.

Last update: 2026-11-08 14:25 (scope decision, landscape research, spec v0.1 + OSS foundation files published).

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
| SpanishBCBL MEG download: [253/316] files at 14:23 on 2026-11-08 (S8 in progress). No final SUMMARY yet | `tail C:\Users\zhang\bci-data\SpanishBCBL\_download.log`; `tasklist /FI "PID eq 37808"` | `taskkill /PID 37808 /T /F` | Rerun `C:\Users\zhang\bci-data\SpanishBCBL\_download_meg.sh` |
| SpanishBCBL preprocessing cache (tSSS, 0.5–45 Hz, 100 Hz): 9 of 47 blocks ok, 0 failed, 38 queued at 14:18. Launcher PID 49364 | `Get-Content C:\Users\zhang\bci-data\cache\spanishbcbl\v1\_preprocess.log -Tail 20`; `tasklist /FI "PID eq 49364"` | `taskkill /T /F /PID 49364` | From the repo root: `C:\venvs\fidetype-rocm\Scripts\python.exe tools/data/preprocess_spanishbcbl.py --workers 2 --mem-budget-gb 14`. It skips cached blocks. Rerun it after the download ends, to add the new subjects |
| M1 decoder training (an agent is still working on it). A beam re-tune agent also runs (`experiments/2026-11-08-beam-retune/`) | Check `experiments/2026-11-08-m1b-decoder/` and `C:\Users\zhang\bci-data\runs\` | See `experiments/2026-11-08-m1b-decoder/` (launch.ps1, results.md) | See the same folder |
| Static server, http://localhost:8000 | `tasklist /FI "PID eq 50528"` or open the URL | `taskkill /PID 50528 /F` | `node tools/serve.js` (it stops at reboot) |

Note: PIDs change after a restart. Note: `tools/serve.js` is tracked in git, so a fresh clone has it.

**Memory warning.** The machine has 31 GB RAM. Several heavy jobs at the same time (preprocessing with 3 workers plus other agents) caused a 2-hour stall from paging. Run preprocessing and training with memory limits (`--mem-budget-gb`). Do not run more than one heavy job at a time. One block (S11 ses1 block2) peaked at 18.5 GB, above the 14 GB budget estimate.

## Current status (from tracker.json)
- **M0 Setup: done on 2026-11-08** (target 11-09). Only the bulk MEG download (M0-02) still runs, in the background. M1-M7 target: 2026-11-15.
- **M1 Baseline decoder: in progress.**
  - Data loader + alignment: **done** (`src/fidetype/data/`, `tools/data/preprocess_spanishbcbl.py`). 81 typing blocks; 15570/15571 keys aligned; 224 unique sentences, split by sentence hash (184/16/24). Results: `experiments/2026-11-08-m1a-data/results.md`.
  - Char n-gram LM + CTC beam: **done** (`src/fidetype/lm/`). Simulator median CER 0.281 → 0.200. LM fusion makes the confidences over-confident. Results: `experiments/2026-11-08-lm-beam/results.md`.
  - Preprocessing cache: **running** in the background (see below).
  - Conv + CTC decoder: an agent is training it now (`src/fidetype/decoders/`, `experiments/2026-11-08-m1b-decoder/`; not committed yet).
- **M2 Trust core v0: done on the simulator** (`src/fidetype/trust/`, `src/fidetype/interact/`, `src/fidetype/eval/ewpm.py`, `src/fidetype/eval/harness.py`). Still open: provenance ledger v0, and a run on real decoder outputs. Results: `experiments/2026-11-08-m2-trust-sim/results.md` and `wiki/questions/trust-core-v0-results.md`.
- **Revised Paper 1 claim:** "far fewer wrong and hallucinated commits for a small speed cost" (wrong commits 0.29–0.47 → 0.02–0.09; eWPM 7–16 % below LM top-1), not "higher eWPM".
- **Scope decision (2026-11-08):** Fidetype targets an OpenTelemetry-level, vendor-neutral standard for neural input (EMG, EEG, MEG, implants). Research MEG stays the credibility base. See [direction-decision](wiki/questions/direction-decision.md).
- **Landscape research: filed.** [wiki/sources/neural-input-landscape-2026.md](wiki/sources/neural-input-landscape-2026.md) plus entities (Apple BCI HID, W3C EMMA, Meta Neural Band, BrainFlow, Dryad). No standard for decoded neural output with confidence exists. Adapter priority: LSL/BrainFlow, Apple HID bridge, Dryad CC0 replay.
- **NeuralTextStream spec v0.1: published** at [spec/neuraltextstream-v0.1.md](spec/neuraltextstream-v0.1.md) (commit 677ba0e; 20 conformance cases; status Development).
- **OSS foundation files: done** (commit 677ba0e, CI green): CONTRIBUTING, CODE_OF_CONDUCT, GOVERNANCE, SECURITY, CITATION.cff, issue/PR templates, GitHub Discussions. Public roadmap: [issue #1](https://github.com/zhangzibo/fidetype/issues/1). Playbook: [wiki/questions/open-source-playbook.md](wiki/questions/open-source-playbook.md); only the GitHub Pages site is still open.
- **GPU env:** native Windows ROCm 7.2.1 + torch 2.9.1 at `C:\venvs\fidetype-rocm`. Use `C:\venvs\fidetype-rocm\Scripts\python.exe` for all torch work. The repo `.venv` is CPU-only: it is for tests and CI. Rebuild the GPU env with `tools/env/setup_rocm.ps1`. Details: `wiki/questions/compute-setup.md`.
- **CI:** GitHub Actions (`.github/workflows/tests.yml`) runs pytest on CPU.

## Next steps
1. **Re-tune the beam** (`prune_topk`, insertion bonus): an agent runs it now (`experiments/2026-11-08-beam-retune/`). With default settings, the n-best misses the truth in 73 % of lists.
2. **Decoder results** (M1): an agent trains the conv + CTC decoder now. Get greedy and beam CER on the fixed splits. Then make the decoder emit NeuralTextStream.
3. **Run the trust core on real decoder streams** (M2-10). This closes M2.
4. **First adapters** (M6), in priority order: LSL/BrainFlow, the Apple BCI HID bridge, Dryad CC0 replay.
5. **Conformance test suite** for the spec (M5-10). The validator exists; the suite does not.
6. **Move producers' `meta` keys** to the namespaced conventions before spec v0.2.
7. **Pending user decision:** enable Claude Code hooks for automatic snapshots, or not.
8. Optional: rename the local folder to `fidetype`. Do this only BETWEEN sessions (see below).

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
