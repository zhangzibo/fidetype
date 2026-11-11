# HANDOFF: where are we

This file tells a new Claude Code session where the last session stopped. The orchestrator updates it after each finished task.

Last update: 2026-11-10 21:05 (queue-2026-11-10b RUNNING: M1-15 full-r1 on all 80 cached blocks, then r3 causal; AC sleep never until the queue ends; max_lr_reductions is now a cap, commit 4dd073b). Before: 2026-11-10 20:55 (M1-15 r2 finished and analysed: test greedy 0.577, beam + LM 0.488, below the logistic regression; queue-2026-11-10 done, AC sleep back to 30 min). Before: 2026-11-10 19:30 (M1-15 r2 launched in queue-2026-11-10 with sleep prevention and a plateau schedule; AC sleep set to never until the queue ends). Before: 2026-11-09 23:10 (overnight queue finished: preprocessing 30 ok / 1 failed, M1-15 r1 trained 9 epochs only because the PC slept, results recorded); 2026-11-09 18:40 (queue set up); 18:25 (preprocessing restarted). Earlier: 2026-11-08 18:45 (GPU stress test PASS); 17:47 (crash recovery recorded).

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

## GPU stress test: PASS (2026-11-08, 17:58–18:30)
- The test repeated the crash condition of 16:44. The iGPU was disabled in Device Manager.
- Real ConvCTC training (`config-r2-small-aux0.5.json`): 721 s, stopped at max_minutes, epoch 161, step 9675, best val CER 0.606.
- Then the GPU idled for 1200 s with the CUDA context alive. The script wrote `RESULT PASS` and exited.
- System event log since 17:55: no Kernel-Power 41, BugCheck 1001, ID 4101, WHEA or amdkmdag events. stderr has only the AOTriton attention warnings.
- Files: `C:\Users\zhang\bci-data\runs\stress-2026-11-08\` (`heartbeat.log`, `stdout.log`, `stderr.log`).
- Result: the SpanishBCBL preprocessing restarted after the test (see "Background processes"). The crash cause stays unconfirmed. If the crash occurs again, analyse the minidump and reinstall the driver.

## Crash on 2026-11-08 (read this)
- At about **16:44** on 2026-11-08 the PC blue-screened: bugcheck **0x7E** in the AMD driver `amdkmdag` (`DMM_PowerManagement::GetPowerState`).
- **Cause not confirmed** (AMD driver bug, or hardware). The two AMD driver versions (iGPU vs RX 7800 XT) are **by design**: both come from Adrenalin 26.10.1. An earlier note called them a "mismatch". That was wrong.
- **Done:** (1) iGPU disabled; (3) verified (torch check, `gpu_smoke.py`, stress test PASS). Still optional: (2) reinstall Adrenalin 26.10.2 with Factory Reset. Details and commands: [compute-setup, "Driver crash"](wiki/questions/compute-setup.md#driver-crash-2026-11-08).
- The old session transcript (19d95f58) was lost. The recovery session is e302da03.
- Only the "record and commit" step was lost. M1-C and M2-14 had finished on disk. They are now recorded and committed.

## Background processes
| Process | Check | Stop | Resume |
|---|---|---|---|
| SpanishBCBL MEG download: **done** at 14:59 on 2026-11-08 (316/316 files, 251.36 GB, `STATUS=COMPLETE`). No process runs | `tail C:\Users\zhang\bci-data\SpanishBCBL\_download.log` | — | Rerun `C:\Users\zhang\bci-data\SpanishBCBL\_download_meg.sh` only to verify (it skips finished files) |
| SpanishBCBL preprocessing cache: **done** at 20:24:09 on 2026-11-09 (`END ok=30 failed=1`). 80 of 81 typing blocks are cached. **S1/ses1_block1 fails** each time (2026-11-08 and 2026-11-09): "sidecar invalid: segment 48+: empty segment, key sample outside the segment". The raw `Block1.fif` (1.90 GB) ends before the typing log: the dataset has no `Block1-1.fif` continuation (Block3 of the same session has one). No process runs | `Get-Content C:\Users\zhang\bci-data\cache\spanishbcbl\v1\_preprocess.log -Tail 5` | — | Rerun `C:\venvs\fidetype-rocm\Scripts\python.exe tools/data/preprocess_spanishbcbl.py --workers 1 --mem-budget-gb 14` only to retry (it skips cached blocks; S1/ses1_block1 will fail again unless the script drops the segments past the end of the MEG) |
| M1 decoder training: no run active now (M1-C runs `m1c-*` all finished; queue log `C:\Users\zhang\bci-data\runs\m1c-queue.log`). Runs live in `C:\Users\zhang\bci-data\runs\<run_name>\`, streams in `C:\Users\zhang\bci-data\streams\<run_name>\` | `Get-Content C:\Users\zhang\bci-data\runs\<run_name>\status.json`; `Get-Content C:\Users\zhang\bci-data\runs\<run_name>\train.log -Tail 5`; `Get-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\<run_name>\pid.txt)` | `Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\<run_name>\pid.txt)` (last checkpoint is at most 5 min old) | `.\experiments\2026-11-08-m1b-decoder\launch.ps1 -RunName <run_name> -Resume` |
| **Queue 2026-11-10b: RUNNING** (started 20:53:29, queue PID **8692**, hard stop 2026-11-11 06:53). Steps: train M1-15 full-r1 (`config-full-r1.json`, run `m1-15-sentence-context-full-r1`, training PID 20276 = venv launcher, worker python 32464) -> inference `--head final` and `--head conv` -> train r3 (`config-r3.json`, run `m1-15-sentence-context-r3`) -> inference final + conv -> eWPM check (CPU, `results/ewpm-full-r1`, `results/ewpm-r3`) -> QUEUE DONE. AC sleep set to 0 at start (saved 1800 s in `sleep-ac-seconds.txt`), restored in `finally`. full-r1: device=cuda, 2.7 GB GPU, about 106 s/epoch (first epoch 303 s, cold cache), 252 steps/epoch. Expected end about 23:00-00:30. Script and logs: `C:\Users\zhang\bci-data\runs\queue-2026-11-10b\` | `Get-Content C:\Users\zhang\bci-data\runs\queue-2026-11-10b\queue.log -Tail 5`; `Get-Content C:\Users\zhang\bci-data\runs\<run>\train.log -Tail 3`; `Get-Content C:\Users\zhang\bci-data\runs\<run>\status.json` | `Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\queue-2026-11-10b\queue.pid)`; then `taskkill /PID (Get-Content C:\Users\zhang\bci-data\runs\<run>\pid.txt) /T /F`; then **`powercfg /change standby-timeout-ac 30`** (a hard kill skips the restore) | Training: `.\experiments\2026-11-09-m1-15-sentence-context\launch.ps1 -RunName <run> -Resume` (latest.pt every 5 min). Whole queue: remove the finished steps from `$Jobs` in queue.ps1, then start it again (the header has the command) |
| Queue 2026-11-10: **done** ("QUEUE DONE" 19:38:47; AC sleep restored to 30 min). It trained M1-15 r2 (early stop after 43 epochs, 13.0 active min, no suspend gap) and ran the inference with `--head final` and `--head conv`. No process runs. Script and logs: `C:\Users\zhang\bci-data\runs\queue-2026-11-10\` | `Get-Content C:\Users\zhang\bci-data\runs\queue-2026-11-10\queue.log -Tail 5` | — | — |
| Queue 2026-11-09: **done** ("QUEUE DONE" 22:05:05). It trained M1-15 r1 and ran the inference. No process runs. Script and logs: `C:\Users\zhang\bci-data\runs\queue-2026-11-09\` | `Get-Content C:\Users\zhang\bci-data\runs\queue-2026-11-09\queue.log -Tail 5` | — | — |
| Static server, http://localhost:8000: not running (stopped by the crash) | Open the URL | Stop its node process | `node tools/serve.js` (it stops at reboot) |

**Running now (2026-11-10 21:05): queue-2026-11-10b (see the table). Max 1 heavy job: start no other GPU job or preprocessing until "QUEUE DONE".** **Sleep warning:** the PC went into S3 sleep from 20:32:38 to 22:00:03 during M1-15 r1. `max_minutes` counts wall-clock time, so the run lost its budget. Before a long unattended run, prevent sleep (for example `powercfg /change standby-timeout-ac 0`, restore `30` after) or make the trainer call `SetThreadExecutionState`. Note: PIDs change after a restart. An auto-sleep watcher was set up on 2026-11-08 at about 23:20 and cancelled by the user (sleep settings restored to AC 30 min). The 4 hung M1-B python processes noted in the M1-C results also ended with the crash. Note: `tools/serve.js` is tracked in git, so a fresh clone has it.

**Memory warning.** The machine has 31 GB RAM. Several heavy jobs at the same time (preprocessing with 3 workers plus other agents) caused a 2-hour stall from paging. Run preprocessing and training with memory limits (`--mem-budget-gb`). Do not run more than one heavy job at a time. One block (S11 ses1 block2) peaked at 18.5 GB, above the 14 GB budget estimate. On 2026-11-08 the blocks peaked at 16.5–19.7 GB. S17/ses2_block1 took 13674 s (3.8 h) against about 6 min for the others, very probably from paging. At the 2026-11-09 restart only 15.9 GB RAM was free (other apps use about 15 GB), and the pagefile is only 6.9 GB (commit limit 37.9 GB). So a 16–19 GB block can page. To lower the risk: close large apps (browsers, Discord, Spotify, Notion) while it runs, run no other heavy job, and optionally set a larger pagefile (for example 16–32 GB, needs a reboot).

## Sleep prevention (code, 2026-11-10, commit 6132c60)
- `train.py` and `train_sentence.py` now run inside `fidetype.utils.power.keep_awake()`: `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` while training, cleared on exit (also on exceptions). No-op off Windows. `train.log` shows `keep_awake=on`.
- `max_minutes` now counts **active compute time** (`ActiveTimer`, `time.monotonic()` deltas). A gap longer than 5 min between steps is logged as "suspend gap detected" and not counted. The total (`active_s`) is in the checkpoint, so `-Resume` keeps the budget. `status.json` shows `active_min`.
- `train_sentence.py` has an opt-in `optim.schedule: "plateau"`: warm-up, then constant LR, x0.5 after `plateau_patience` (5) evals without improvement of the EMA-smoothed val CER (`smooth_alpha` 0.3, `min_delta` 0.002), floor `min_lr` 1e-5. Stop when `patience_evals` (20) evals show no improvement AND (LR at the floor OR `max_lr_reductions` (3) reached). `best.pt` = best raw val CER. Each eval line in `train.log` ends with `trend: smoothed ... lr ... evals_since_improve ... lr_reductions ...`. Default `"cosine"` keeps r1 reproducible.
- `infer_sentence.py --head {final,conv}`: `conv` = the per-key head before the Transformer (Conv-only CER); outputs go to `<streams>/<run_name>_head-conv/`.
- Belt and braces: the queue also set the AC sleep timeout to 0 and restores it at the end.

## Current status (from tracker.json)
- **M0 Setup: done on 2026-11-08** (target 11-09). The bulk MEG download (M0-02) finished at 14:59 on 2026-11-08. M1-M7 target: 2026-11-15.
- **M1 Baseline decoder: in progress.**
  - Data loader + alignment: **done** (`src/fidetype/data/`, `tools/data/preprocess_spanishbcbl.py`). 81 typing blocks; 15570/15571 keys aligned; 224 unique sentences, split by sentence hash (184/16/24). Results: `experiments/2026-11-08-m1a-data/results.md`.
  - Char n-gram LM + CTC beam: **done** (`src/fidetype/lm/`). Simulator median CER 0.281 → 0.200. LM fusion makes the confidences over-confident. Results: `experiments/2026-11-08-lm-beam/results.md`.
  - Preprocessing cache: **done** (2026-11-09 20:24). 80 of 81 blocks are cached. S1/ses1_block1 fails: its MEG file ends before the typing log (no split continuation in the dataset).
  - Conv + CTC decoder: **code done** (`src/fidetype/decoders/`; our own ConvCTC, 10 M params, custom Conformer, causal mode via `lookahead_frames`). It emits NeuralTextStream. Results: `experiments/2026-11-08-m1b-decoder/results.md` and `wiki/questions/decoder-m1-results.md`.
  - **Result:** 5 subjects (about 2.5 h of about 20 h): test greedy CER **0.670**. The shuffled-MEG control gives **0.669**, zeros 0.858. So the model uses a text prior, **not the MEG**. The M1 target (≈0.59) is **not met**. Always report the shuffled-MEG control with a CER.
  - **Sanity check: passed.** Keystroke-locked linear decoding (v1-style), 6 subjects: hand window 0.83–0.96 (chance 0.60), letter 0.31–0.49 (chance about 0.14). Both controls at chance. Peaks at −10..+60 ms. So the cache and the alignment are correct. The CTC failure comes from data volume or the model. Results: `experiments/2026-11-08-m1-sanity/results.md`.
  - **First real MEG decoding (2026-11-08):** synchronous keystroke decoder, oracle key timing (`src/fidetype/decoders/keystroke.py`; per-subject logistic regression, −0.2..+0.3 s, 10 bins × 306 channels). 20 blocks, 11 subjects. Test key accuracy **0.390** (chance 0.13; shuffled MEG 0.111, permuted labels 0.099). Greedy CER **0.59** (controls 0.77). LM beam (`RETUNED`, w 0.5) CER 0.531. This meets the M1 number only in the synchronous setting, not async. Results: `experiments/2026-11-08-m2-real-keystroke/results.md`.
  - **M1-C keystroke auxiliary loss: done (2026-11-08 16:21).** A per-keystroke CE head on the encoder frames makes the CTC decoder use the MEG. 11 subjects, 20 pinned blocks. Test shuffled-MEG gap: without the loss −0.001 / −0.002; with it +0.116 (weight 0.5 and 1.0) and **+0.156** (keystroke-pretrained r4b; CI [+0.141, +0.172]). Best test CER **0.619** (mean over subjects 0.624). The 0.59 target is **not met**. Also fixed: ROCm process-exit hang (`train.hard_exit()`). Results: `experiments/2026-11-08-m1c-decoder-aux/results.md`, section in `wiki/questions/decoder-m1-results.md`.
  - **M1-C2 beam + char LM on the r4b streams: done (2026-11-08 23:25, commit dcff1de).** Test CER: greedy 0.619 → beam without LM 0.605 → beam + Spanish char LM, val-tuned (w 0.25, bonus 1.0) **0.590** [0.576, 0.604]. Shuffled-MEG gap +0.132. The `RETUNED` settings as they are (w 1.25) make it worse: 0.633. The true sentence is in the 20-best for 0 test sentences. Greedy is still 0.619, so the M1 greedy target is **not met**. Results: `experiments/2026-11-08-m1c2-beam-lm/results.md`.
  - **M1-15 r1 sentence-context keystroke decoder: undertrained (2026-11-09).** Only 9 of 150 epochs (about 5 min of compute) because the PC slept. Test (mean over sentences, vs target): greedy **0.619**, beam + LM (w 1.0) **0.532**. M2-10 logistic regression: 0.597 / 0.531. Shuffled gap +0.172 greedy, +0.219 beam (CIs exclude 0). Conv-only vs Conv + Trans val key acc 0.387 vs 0.397. Trust harness on its streams: trust 2.98 eWPM, always commit 2.38, gaze only 3.14: still no BCI gain. Results: `experiments/2026-11-09-m1-15-sentence-context/results.md`.
  - **M1-15 r2: done (2026-11-10).** Plateau schedule, trend stop after 43 epochs (13.0 active min, sleep prevented, no suspend gap). Test (mean over sentences, vs target): greedy **0.577**, beam + LM (w 1.25) **0.488**. First decoder below the like-for-like M2-10 logistic regression (0.597 / 0.531). Shuffled gap +0.214 greedy, +0.258 beam. Conv-only head 0.602 / 0.503: sentence context adds only 0.025 / 0.015 CER (v1: 0.31). Overfits after epoch 12–19 (val CE rises, val CER flat); the stop fired correctly. Trust harness: trust 3.06 eWPM, commit 2.49, gaze only 3.14: still no BCI gain. Results: r2 section of `experiments/2026-11-09-m1-15-sentence-context/results.md`.
  - **S1/S18 check: resolved (2026-11-08, commit 9f8808e).** S1/S18 are one person (P01); so are S4/S14 and S5/S10/S21. The index is correct. Splits are by sentence, so there is no leakage. M1-C mean over people 0.6210 vs over subjects 0.6237. **Report means over participants.** The paper says 20 MEG participants; the release has usable data for 19 (S13 has no logs). Page: `wiki/questions/spanishbcbl-repeated-participants.md`.
- **M2 Trust core v0: done on the simulator** (`src/fidetype/trust/`, `src/fidetype/interact/`, `src/fidetype/eval/ewpm.py`, `src/fidetype/eval/harness.py`). Still open: provenance ledger v0. **M2-15 done** (commit 422406b): `TemperatureScaler.transform_stream` now keeps all stream metadata.
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
1. **M1-15 r3 (causal):** r2 config with `model.lookahead_keys: 0`, same 20 pinned blocks, `train.patience_evals` 12, `optim.max_lr_reductions` 2 (r2 would have stopped at about epoch 34 with the same `best.pt`). Run name `m1-15-sentence-context-r3`. Queue it like queue-2026-11-10 (sleep prevention, `--head final` and `--head conv`, then `ewpm_check.py r3 ewpm-r3`). r3 vs r2 = the cost of causality. Optional small fix: make `max_lr_reductions` a cap in `plateau_update` (r2 logged 4 cuts).
1b. Optional: make `preprocess_spanishbcbl.py` drop segments past the end of the MEG, so S1/ses1_block1 caches with its first 47 segments.
2. **Then: full-cache r4a → r4b retrain** (M1-09; now possible: 80 of 81 blocks cached). First `experiments/2026-11-08-m1c-decoder-aux/config-r4a-pretrain-keys.json`, then `config-r4b-small-aux0.5-pretrained.json`, both with `subjects: null` (all subjects). Pin the new block list. Report participant-aware means (S1/S18, S4/S14, S5/S10/S21 are one person each) and the shuffled-MEG control.
3. **Then 3 seeds** of the full-cache r4b (and r1, r2 if time allows).
4. **Re-tune the beam on val** for the new streams: `lm_weight` and `insertion_bonus`, with the grid extended below w 0.25 (for example 0, 0.05, 0.1, 0.15, 0.25). Decode test once.
5. **Sentence-context keystroke decoder** (M1-15; code + tests done in b56056e, r1 undertrained, r2 done: test 0.577 / 0.488, r3 causal is step 1; then the full cache, because r2 overfits): a Transformer over key embeddings, v1 Conv+Trans style (v1: Conv 0.67 → Conv+Trans 0.36 CER). Goal: an LM top-1 that is right for a real share of sentences, so the real-MEG trust test is no longer degenerate and can beat gaze typing. Then re-run the M2-10 / M2-14 pipeline on it.
6. **Trust core follow-ups** (M2, simulator, light work): re-tune the guard for the new beam (M2-12); conformal risk control for the wrong-commit limit (M2-13). Report every eWPM next to the no-BCI (gaze typing) baseline.
7. **First adapters** (M6), in priority order: LSL/BrainFlow, the Apple BCI HID bridge, Dryad CC0 replay.
7b. **Public datasets** (M6-05, [survey](wiki/questions/public-datasets.md)): first download Brain-to-Text '25 `t15_copyTask.pkl` (58 MB, CC0, real RNN logits) and write a `b2t25` adapter to NeuralTextStream for a licence-clean trust run; then KT-sEMG (21 GB, CC BY 4.0) for the EMG adapter.
8. **Conformance test suite** for the spec (M5-10). The validator exists; the suite does not.
9. **Move producers' `meta` keys** to the namespaced conventions before spec v0.2.
10. **Pending user decision:** enable Claude Code hooks for automatic snapshots, or not.
11. Optional: rename the local folder to `fidetype`. Do this only BETWEEN sessions (see below).
12. **After v0.1 (M0–M7):** follow the long-term roadmap [wiki/questions/roadmap-standard.md](wiki/questions/roadmap-standard.md) (phases P1–P11 in the tracker; diagram 11). First: P6 leaderboard, P1 proto schema + semconv registry, P4 replay adapters.

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
