# HANDOFF: where are we

This file tells a new Claude Code session where the last session stopped. The orchestrator updates it after each finished task.

Last update: 2026-11-08 17:58 (GPU stress test started; see "Stress test in progress"). Earlier: 2026-11-08 18:35 (crash recovery: M1-C keystroke loss and M2-14 OFFER_WORDS recorded and committed; preprocessing paused until the GPU check passes). 18:35: corrected the crash note (driver versions are by design; cause open).

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
- **Load limits (new, 2026-11-08, after the crash):** at most **2 subagents** at the same time. At most **1 heavy job**: GPU training OR preprocessing, never both. **Record and commit right after each result** (tracker, HANDOFF, wiki, commit, push), so a crash loses nothing.

## Stress test in progress (started 2026-11-08 about 17:58)
- **What it does:** repeats the crash condition of 16:44. Real ConvCTC training (config `experiments/2026-11-08-m1c-decoder-aux/config-r2-small-aux0.5.json`, no early stop) for about 12 min. Then the GPU idles for 20 min. The process keeps its torch CUDA context during the idle phase. Then it writes `RESULT PASS` and exits. Total: about 35 min.
- **Before it:** the user disabled the iGPU in Device Manager. After the reboot at 17:52, `tools/env/gpu_smoke.py` passed and the event log was clean.
- **Folder:** `C:\Users\zhang\bci-data\runs\stress-2026-11-08\` (outside the repo). Script `stress.py`, launcher `launch.ps1`, heartbeat `heartbeat.log`, training run `train\`, output `stdout.log` / `stderr.log`, PID `pid.txt`.
- **Check:** `Get-Content C:\Users\zhang\bci-data\runs\stress-2026-11-08\heartbeat.log -Tail 5`. The script writes one line every 20 s (flush + fsync): time, phase (`train`, `idle`, `end`), step, loss, GPU memory.
- **After a reboot, PASS or crash?**
  1. Read the last line of `heartbeat.log`. `RESULT PASS` = the test finished. Another last line = the process died at that time, in that phase.
  2. Compare with the System event log: `Get-WinEvent -FilterHashtable @{LogName='System'; StartTime='2026-11-08 17:55'} | Where-Object { $_.Id -in 41,1001,4101 -or $_.ProviderName -match 'WHEA|amdkmdag' } | Format-List TimeCreated,Id,ProviderName,Message`. Kernel-Power 41 or BugCheck 1001 a short time after the last heartbeat line = a crash.
- **Stop:** `taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\runs\stress-2026-11-08\pid.txt)`.
- **Rule:** no other GPU job or preprocessing during the test. Resume the SpanishBCBL preprocessing only on PASS.

## Crash on 2026-11-08 (read this)
- At about **16:44** on 2026-11-08 the PC blue-screened: bugcheck **0x7E** in the AMD driver `amdkmdag` (`DMM_PowerManagement::GetPowerState`).
- **Cause not confirmed** (AMD driver bug, or hardware). The two AMD driver versions (iGPU vs RX 7800 XT) are **by design**: both come from Adrenalin 26.10.1. An earlier note called them a "mismatch". That was wrong.
- **To do (user), before the next GPU or preprocessing job:** (1) disable the iGPU; (2) optional: reinstall Adrenalin 26.10.2 with Factory Reset; (3) verify (torch check, `gpu_smoke.py`, short training + 10–20 min idle). Details and commands: [compute-setup, "Driver crash"](wiki/questions/compute-setup.md#driver-crash-2026-11-08).
- The old session transcript (19d95f58) was lost. The recovery session is e302da03.
- Only the "record and commit" step was lost. M1-C and M2-14 had finished on disk. They are now recorded and committed.

## Background processes
| Process | Check | Stop | Resume |
|---|---|---|---|
| SpanishBCBL MEG download: **done** at 14:59 on 2026-11-08 (316/316 files, 251.36 GB, `STATUS=COMPLETE`). No process runs | `tail C:\Users\zhang\bci-data\SpanishBCBL\_download.log` | — | Rerun `C:\Users\zhang\bci-data\SpanishBCBL\_download_meg.sh` only to verify (it skips finished files) |
| SpanishBCBL preprocessing cache (tSSS, 0.5–45 Hz, 100 Hz): **paused – resume after the GPU check passes.** The PC crash stopped it. `_preprocess.log` stopped at 16:41:49 with 40 ok, 1 failed, 1 running, 5 queued. S24/ses1_block1 and S11/ses1_block1 have no output. No process runs | `Get-Content C:\Users\zhang\bci-data\cache\spanishbcbl\v1\_preprocess.log -Tail 20` | Find the python PID in Task Manager, then `taskkill /T /F /PID <pid>` | From the repo root, run detached: `C:\venvs\fidetype-rocm\Scripts\python.exe tools/data/preprocess_spanishbcbl.py --workers 1 --mem-budget-gb 14`. It skips cached blocks. Do not run it at the same time as GPU training |
| M1 decoder training: no run active now (M1-C runs `m1c-*` all finished; queue log `C:\Users\zhang\bci-data\runs\m1c-queue.log`). Runs live in `C:\Users\zhang\bci-data\runs\<run_name>\`, streams in `C:\Users\zhang\bci-data\streams\<run_name>\` | `Get-Content C:\Users\zhang\bci-data\runs\<run_name>\status.json`; `Get-Content C:\Users\zhang\bci-data\runs\<run_name>\train.log -Tail 5`; `Get-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\<run_name>\pid.txt)` | `Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\<run_name>\pid.txt)` (last checkpoint is at most 5 min old) | `.\experiments\2026-11-08-m1b-decoder\launch.ps1 -RunName <run_name> -Resume` |
| Static server, http://localhost:8000: not running (stopped by the crash) | Open the URL | Stop its node process | `node tools/serve.js` (it stops at reboot) |

Note: no PIDs are listed, because the crash ended all processes. PIDs change after a restart. The 4 hung M1-B python processes noted in the M1-C results also ended with the crash. Note: `tools/serve.js` is tracked in git, so a fresh clone has it.

**Memory warning.** The machine has 31 GB RAM. Several heavy jobs at the same time (preprocessing with 3 workers plus other agents) caused a 2-hour stall from paging. Run preprocessing and training with memory limits (`--mem-budget-gb`). Do not run more than one heavy job at a time. One block (S11 ses1 block2) peaked at 18.5 GB, above the 14 GB budget estimate.

## Current status (from tracker.json)
- **M0 Setup: done on 2026-11-08** (target 11-09). The bulk MEG download (M0-02) finished at 14:59 on 2026-11-08. M1-M7 target: 2026-11-15.
- **M1 Baseline decoder: in progress.**
  - Data loader + alignment: **done** (`src/fidetype/data/`, `tools/data/preprocess_spanishbcbl.py`). 81 typing blocks; 15570/15571 keys aligned; 224 unique sentences, split by sentence hash (184/16/24). Results: `experiments/2026-11-08-m1a-data/results.md`.
  - Char n-gram LM + CTC beam: **done** (`src/fidetype/lm/`). Simulator median CER 0.281 → 0.200. LM fusion makes the confidences over-confident. Results: `experiments/2026-11-08-lm-beam/results.md`.
  - Preprocessing cache: **paused** (40 blocks ok at the crash, 16:41:49). Resume after the GPU check passes (see above).
  - Conv + CTC decoder: **code done** (`src/fidetype/decoders/`; our own ConvCTC, 10 M params, custom Conformer, causal mode via `lookahead_frames`). It emits NeuralTextStream. Results: `experiments/2026-11-08-m1b-decoder/results.md` and `wiki/questions/decoder-m1-results.md`.
  - **Result:** 5 subjects (about 2.5 h of about 20 h): test greedy CER **0.670**. The shuffled-MEG control gives **0.669**, zeros 0.858. So the model uses a text prior, **not the MEG**. The M1 target (≈0.59) is **not met**. Always report the shuffled-MEG control with a CER.
  - **Sanity check: passed.** Keystroke-locked linear decoding (v1-style), 6 subjects: hand window 0.83–0.96 (chance 0.60), letter 0.31–0.49 (chance about 0.14). Both controls at chance. Peaks at −10..+60 ms. So the cache and the alignment are correct. The CTC failure comes from data volume or the model. Results: `experiments/2026-11-08-m1-sanity/results.md`.
  - **First real MEG decoding (2026-11-08):** synchronous keystroke decoder, oracle key timing (`src/fidetype/decoders/keystroke.py`; per-subject logistic regression, −0.2..+0.3 s, 10 bins × 306 channels). 20 blocks, 11 subjects. Test key accuracy **0.390** (chance 0.13; shuffled MEG 0.111, permuted labels 0.099). Greedy CER **0.59** (controls 0.77). LM beam (`RETUNED`, w 0.5) CER 0.531. This meets the M1 number only in the synchronous setting, not async. Results: `experiments/2026-11-08-m2-real-keystroke/results.md`.
  - **M1-C keystroke auxiliary loss: done (2026-11-08 16:21).** A per-keystroke CE head on the encoder frames makes the CTC decoder use the MEG. 11 subjects, 20 pinned blocks. Test shuffled-MEG gap: without the loss −0.001 / −0.002; with it +0.116 (weight 0.5 and 1.0) and **+0.156** (keystroke-pretrained r4b; CI [+0.141, +0.172]). Best test CER **0.619** (mean over subjects 0.624). The 0.59 target is **not met**. Also fixed: ROCm process-exit hang (`train.hard_exit()`). Results: `experiments/2026-11-08-m1c-decoder-aux/results.md`, section in `wiki/questions/decoder-m1-results.md`.
- **M2 Trust core v0: done on the simulator** (`src/fidetype/trust/`, `src/fidetype/interact/`, `src/fidetype/eval/ewpm.py`, `src/fidetype/eval/harness.py`). Still open: provenance ledger v0; bug: `TemperatureScaler.transform_stream` drops `vocab_type`, `frame_period` and `latency` (M2-15).
- **Per-word OFFER (OFFER_WORDS) + partial correction: done (M2-14, 2026-11-08 16:42).** New action and word-level gaze user (`UserConfig.aac_gaze()`); defaults unchanged. Simulator worst preset: +0.4 to +1.7 eWPM over trust (paired CIs [0.36, 1.57], [0.40, 1.74]); median preset no change. Real MEG: the fit never selects it (system word accuracy 0.10). Trust 2.96, always commit 2.31, **gaze typing alone 3.14 eWPM: no BCI policy beats the no-BCI baseline.** Paper 1 must report eWPM against a no-BCI baseline. Results: `experiments/2026-11-08-m2-offer-words/results.md`, section 7 of `wiki/questions/trust-core-v0-results.md`.
- **Trust core on real MEG: done (M2-10, 2026-11-08).** Always-commit LM top-1: wrong-commit 100 % (83 % fluent Spanish). Trust policy: 0 % (always OFFER). eWPM 9.61 vs 9.70 (CI crosses 0). Null input: LM top-1 commits fluent text on 83–100 %, trust 0 %. Guard AUROC 0.85 (top-1 CER above median), 0.98 (uniform vs real), about 0.5 (shuffled vs real). **Degenerate test:** the true sentence is never in the n-best, so conformal coverage is 0 and usefulness is untested. See section 6 of `wiki/questions/trust-core-v0-results.md`. Results: `experiments/2026-11-08-m2-trust-sim/results.md` and `wiki/questions/trust-core-v0-results.md`.
- **Beam re-tuned (2026-11-08).** The old n-best misses were search errors (`prune_topk = 10` plus beam 16). Use the `RETUNED` preset: `ctc_prefix_beam_search(stream, lm, **RETUNED)` (`from fidetype.lm import RETUNED`) (beam 256, no top-k cut, w 1.25, bonus 1.0, numpy vector search). The old defaults are unchanged. recall@10 0.075 → 0.47 (median Tatoeba). In the trust pipeline (simulator), the n-best miss rate falls 0.73 → 0.00. Results: `experiments/2026-11-08-beam-retune/results.md`, section 5 of `wiki/questions/trust-core-v0-results.md`.
- **Revised Paper 1 claim (after the beam re-tune, simulator only; real data pending):** "the trust policy now matches always-commit speed (25.3 vs 25.8 eWPM) with about 3× fewer wrong commits (0.033 vs 0.108)". Real MEG so far: wrong-commit 100 % → 0 %, but with no correct candidates. The earlier claim was "far fewer wrong commits for a small speed cost" (eWPM 7–16 % below LM top-1).
- **Scope decision (2026-11-08):** Fidetype targets an OpenTelemetry-level, vendor-neutral standard for neural input (EMG, EEG, MEG, implants). Research MEG stays the credibility base. See [direction-decision](wiki/questions/direction-decision.md).
- **Landscape research: filed.** [wiki/sources/neural-input-landscape-2026.md](wiki/sources/neural-input-landscape-2026.md) plus entities (Apple BCI HID, W3C EMMA, Meta Neural Band, BrainFlow, Dryad). No standard for decoded neural output with confidence exists. Adapter priority: LSL/BrainFlow, Apple HID bridge, Dryad CC0 replay.
- **NeuralTextStream spec v0.1: published** at [spec/neuraltextstream-v0.1.md](spec/neuraltextstream-v0.1.md) (commit 677ba0e; 20 conformance cases; status Development).
- **OSS foundation files: done** (commit 677ba0e, CI green): CONTRIBUTING, CODE_OF_CONDUCT, GOVERNANCE, SECURITY, CITATION.cff, issue/PR templates, GitHub Discussions. Public roadmap: [issue #1](https://github.com/zhangzibo/fidetype/issues/1). Playbook: [wiki/questions/open-source-playbook.md](wiki/questions/open-source-playbook.md); only the GitHub Pages site is still open.
- **GPU env:** native Windows ROCm 7.2.1 + torch 2.9.1 at `C:\venvs\fidetype-rocm`. Use `C:\venvs\fidetype-rocm\Scripts\python.exe` for all torch work. The repo `.venv` is CPU-only: it is for tests and CI. Rebuild the GPU env with `tools/env/setup_rocm.ps1`. Details: `wiki/questions/compute-setup.md`.
- **CI:** GitHub Actions (`.github/workflows/tests.yml`) runs pytest on CPU.

## Next steps
1. **User: disable the iGPU and verify the GPU** (plan in [compute-setup](wiki/questions/compute-setup.md#driver-crash-2026-11-08)). When the check passes, resume the preprocessing (command above), as the only heavy job.
2. **Sentence-context keystroke decoder** (M1-15): a Transformer over key embeddings, v1 Conv+Trans style (v1: Conv 0.67 → Conv+Trans 0.36 CER). Goal: an LM top-1 that is right for a real share of sentences, so the real-MEG trust test is no longer degenerate and can beat gaze typing. Then re-run the M2-10 / M2-14 pipeline on it.
3. **M1-C follow-ups:** 3 seeds for r1, r2, r4b; the `RETUNED` beam + char LM on the r4b streams; check S1/S18 = P01.
4. **Full-cache retrain** when the preprocessing finishes (M1-14): the keystroke decoder and the CTC decoder (r4a/r4b) on all subjects. Pin the new block list.
5. **Trust core follow-ups** (M2, simulator): re-tune the guard for the new beam (M2-12); conformal risk control for the wrong-commit limit (M2-13); fix `TemperatureScaler.transform_stream` (M2-15). Report every eWPM next to the no-BCI (gaze typing) baseline.
6. **First adapters** (M6), in priority order: LSL/BrainFlow, the Apple BCI HID bridge, Dryad CC0 replay.
7. **Conformance test suite** for the spec (M5-10). The validator exists; the suite does not.
8. **Move producers' `meta` keys** to the namespaced conventions before spec v0.2.
9. **Pending user decision:** enable Claude Code hooks for automatic snapshots, or not.
10. Optional: rename the local folder to `fidetype`. Do this only BETWEEN sessions (see below).

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
