# HANDOFF: where are we

This file tells a new Claude Code session where the last session stopped. The orchestrator updates it after each finished task.

Last update: 2026-11-08 15:45 (beam re-tuned; keystroke sanity check passed; download complete).

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
| SpanishBCBL MEG download: **done** at 14:59 on 2026-11-08 (316/316 files, 251.36 GB, `STATUS=COMPLETE`). No process runs | `tail C:\Users\zhang\bci-data\SpanishBCBL\_download.log` | — | Rerun `C:\Users\zhang\bci-data\SpanishBCBL\_download_meg.sh` only to verify (it skips finished files) |
| SpanishBCBL preprocessing cache (tSSS, 0.5–45 Hz, 100 Hz): 23 of 47 blocks ok, 0 failed, 24 queued at 15:38 (S18 ses1 block1 running). Launcher PID 49364 | `Get-Content C:\Users\zhang\bci-data\cache\spanishbcbl\v1\_preprocess.log -Tail 20`; `tasklist /FI "PID eq 49364"` | `taskkill /T /F /PID 49364` | From the repo root: `C:\venvs\fidetype-rocm\Scripts\python.exe tools/data/preprocess_spanishbcbl.py --workers 2 --mem-budget-gb 14`. It skips cached blocks. The download is complete: rerun it after this pass ends, to add any subjects that are not queued |
| M1 decoder training: no run active now. Runs live in `C:\Users\zhang\bci-data\runs\<run_name>\`, streams in `C:\Users\zhang\bci-data\streams\<run_name>\` | `Get-Content C:\Users\zhang\bci-data\runs\<run_name>\status.json`; `Get-Content C:\Users\zhang\bci-data\runs\<run_name>\train.log -Tail 5`; `Get-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\<run_name>\pid.txt)` | `Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\<run_name>\pid.txt)` (last checkpoint is at most 5 min old) | `.\experiments\2026-11-08-m1b-decoder\launch.ps1 -RunName <run_name> -Resume` |
| Agents still working (not committed): (1) keystroke-synchronous decoder + trust core on real MEG (`experiments/2026-11-08-m2-real-keystroke/`, edits `src/fidetype/decoders/keystroke.py`); (2) CTC decoder + keystroke auxiliary loss (`experiments/2026-11-08-m1c-decoder-aux/`, edits `src/fidetype/decoders/`). Their files are left unstaged | Check their folders | — | — |
| Static server, http://localhost:8000 | `tasklist /FI "PID eq 50528"` or open the URL | `taskkill /PID 50528 /F` | `node tools/serve.js` (it stops at reboot) |

Note: PIDs change after a restart. Note: `tools/serve.js` is tracked in git, so a fresh clone has it.

**Memory warning.** The machine has 31 GB RAM. Several heavy jobs at the same time (preprocessing with 3 workers plus other agents) caused a 2-hour stall from paging. Run preprocessing and training with memory limits (`--mem-budget-gb`). Do not run more than one heavy job at a time. One block (S11 ses1 block2) peaked at 18.5 GB, above the 14 GB budget estimate.

## Current status (from tracker.json)
- **M0 Setup: done on 2026-11-08** (target 11-09). The bulk MEG download (M0-02) finished at 14:59 on 2026-11-08. M1-M7 target: 2026-11-15.
- **M1 Baseline decoder: in progress.**
  - Data loader + alignment: **done** (`src/fidetype/data/`, `tools/data/preprocess_spanishbcbl.py`). 81 typing blocks; 15570/15571 keys aligned; 224 unique sentences, split by sentence hash (184/16/24). Results: `experiments/2026-11-08-m1a-data/results.md`.
  - Char n-gram LM + CTC beam: **done** (`src/fidetype/lm/`). Simulator median CER 0.281 → 0.200. LM fusion makes the confidences over-confident. Results: `experiments/2026-11-08-lm-beam/results.md`.
  - Preprocessing cache: **running** in the background: 23 of 47 blocks at 15:38 (see above).
  - Conv + CTC decoder: **code done** (`src/fidetype/decoders/`; our own ConvCTC, 10 M params, custom Conformer, causal mode via `lookahead_frames`). It emits NeuralTextStream. Results: `experiments/2026-11-08-m1b-decoder/results.md` and `wiki/questions/decoder-m1-results.md`.
  - **Result:** 5 subjects (about 2.5 h of about 20 h): test greedy CER **0.670**. The shuffled-MEG control gives **0.669**, zeros 0.858. So the model uses a text prior, **not the MEG**. The M1 target (≈0.59) is **not met**. Always report the shuffled-MEG control with a CER.
  - **Sanity check: passed.** Keystroke-locked linear decoding (v1-style), 6 subjects: hand window 0.83–0.96 (chance 0.60), letter 0.31–0.49 (chance about 0.14). Both controls at chance. Peaks at −10..+60 ms. So the cache and the alignment are correct. The CTC failure comes from data volume or the model. Results: `experiments/2026-11-08-m1-sanity/results.md`.
  - **Running now:** CTC decoder + keystroke auxiliary loss (`experiments/2026-11-08-m1c-decoder-aux/`).
- **M2 Trust core v0: done on the simulator** (`src/fidetype/trust/`, `src/fidetype/interact/`, `src/fidetype/eval/ewpm.py`, `src/fidetype/eval/harness.py`). Still open: provenance ledger v0, and a run on real decoder outputs (**running now**: keystroke-synchronous decoder + trust core on real MEG, `experiments/2026-11-08-m2-real-keystroke/`). Results: `experiments/2026-11-08-m2-trust-sim/results.md` and `wiki/questions/trust-core-v0-results.md`.
- **Beam re-tuned (2026-11-08).** The old n-best misses were search errors (`prune_topk = 10` plus beam 16). Use the `RETUNED` preset: `ctc_prefix_beam_search(stream, lm, **RETUNED)` (`from fidetype.lm import RETUNED`) (beam 256, no top-k cut, w 1.25, bonus 1.0, numpy vector search). The old defaults are unchanged. recall@10 0.075 → 0.47 (median Tatoeba). In the trust pipeline (simulator), the n-best miss rate falls 0.73 → 0.00. Results: `experiments/2026-11-08-beam-retune/results.md`, section 5 of `wiki/questions/trust-core-v0-results.md`.
- **Revised Paper 1 claim (after the beam re-tune, simulator only; real data pending):** "the trust policy now matches always-commit speed (25.3 vs 25.8 eWPM) with about 3× fewer wrong commits (0.033 vs 0.108)". The earlier claim was "far fewer wrong commits for a small speed cost" (eWPM 7–16 % below LM top-1).
- **Scope decision (2026-11-08):** Fidetype targets an OpenTelemetry-level, vendor-neutral standard for neural input (EMG, EEG, MEG, implants). Research MEG stays the credibility base. See [direction-decision](wiki/questions/direction-decision.md).
- **Landscape research: filed.** [wiki/sources/neural-input-landscape-2026.md](wiki/sources/neural-input-landscape-2026.md) plus entities (Apple BCI HID, W3C EMMA, Meta Neural Band, BrainFlow, Dryad). No standard for decoded neural output with confidence exists. Adapter priority: LSL/BrainFlow, Apple HID bridge, Dryad CC0 replay.
- **NeuralTextStream spec v0.1: published** at [spec/neuraltextstream-v0.1.md](spec/neuraltextstream-v0.1.md) (commit 677ba0e; 20 conformance cases; status Development).
- **OSS foundation files: done** (commit 677ba0e, CI green): CONTRIBUTING, CODE_OF_CONDUCT, GOVERNANCE, SECURITY, CITATION.cff, issue/PR templates, GitHub Discussions. Public roadmap: [issue #1](https://github.com/zhangzibo/fidetype/issues/1). Playbook: [wiki/questions/open-source-playbook.md](wiki/questions/open-source-playbook.md); only the GitHub Pages site is still open.
- **GPU env:** native Windows ROCm 7.2.1 + torch 2.9.1 at `C:\venvs\fidetype-rocm`. Use `C:\venvs\fidetype-rocm\Scripts\python.exe` for all torch work. The repo `.venv` is CPU-only: it is for tests and CI. Rebuild the GPU env with `tools/env/setup_rocm.ps1`. Details: `wiki/questions/compute-setup.md`.
- **CI:** GitHub Actions (`.github/workflows/tests.yml`) runs pytest on CPU.

## Next steps
1. **Wait for the two running agents:** the keystroke-synchronous decoder + trust core on real MEG (M2-10), and CTC + keystroke auxiliary loss (M1-12). Review and commit their results.
2. **Decoder** (M1): the sanity check passed. Wait for the full cache (preprocessing; the download is done) and **retrain on all subjects** (`config-real.json`, subjects `null`). In parallel: **low-data tuning** (smaller model, more dropout and masking), then cross-subject pretraining + per-subject fine-tune. Report beam CER with the `RETUNED` beam. Report the shuffled-MEG control every time.
3. **Trust core follow-ups** (M2, simulator): re-tune the guard for the new beam (n-best inconsistency + `p_top1`; M2-12); a finite-sample wrong-commit guarantee with conformal risk control (test wrong-commit 0.058–0.075 against the 0.05 target; M2-13); a per-word OFFER action in the simulated user (M2-14). Always calibrate the frames before the beam.
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

## Decoder commands (from experiments/2026-11-08-m1b-decoder/results.md)
Launch (detached, hidden window; it outlives the session):

```powershell
.\experiments\2026-11-08-m1b-decoder\launch.ps1 -Config experiments\2026-11-08-m1b-decoder\config-real.json -RunName <run_name>
```

Check: `Get-Content C:\Users\zhang\bci-data\runs\<run_name>\status.json` and `Get-Content C:\Users\zhang\bci-data\runs\<run_name>\train.log -Tail 5`.

Resume: `.\experiments\2026-11-08-m1b-decoder\launch.ps1 -RunName <run_name> -Resume`

Inference, metrics and the MEG control (GPU env):

```bash
C:/venvs/fidetype-rocm/Scripts/python.exe -m fidetype.decoders.infer --run-dir C:/Users/zhang/bci-data/runs/<run_name>          # add --control for real/shuffled/zeros
```

ROCm notes: `MIOPEN_FIND_MODE=FAST` (set by train/infer), lengths padded to a multiple of 100 samples, `train.torch_threads = 4`. CPU contention with preprocessing slows training 10x or more. Details: `wiki/questions/compute-setup.md`.

## How to resume
- In the repo folder, run `claude --continue`. Or start a new session and say "read HANDOFF.md".
- Run `node tools/session/start.js` for a short resume summary.
- Run `node tools/session/snapshot.js` to refresh `agent-memory/` from `~/.claude/...`.
- The orchestrator updates this file after each finished task.
