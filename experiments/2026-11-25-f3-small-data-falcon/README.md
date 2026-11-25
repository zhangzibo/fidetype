# P15-54 F3 at small data (FALCON H2): how to run it

The pre-registration is [plan.md](plan.md) (commit `19ec6c5`, frozen). [amendment-1.md](amendment-1.md) (commit `4d31f8e`, before the wrapper and before any training) records the session-role fallback (no H2 session has 50 trials, so the core budgets are {3, 12, 24}), the output folder and the open details. No result exists yet.

| file | what it does |
|---|---|
| `f3s.py` | the runner: stage 0 (NWB -> caches, session roles), arm I / M / P pretraining, stage 1 selection, stage 2 core and extended runs, rules, hypotheses, outcome |
| `config.json` | the plan and amendment values in one place |
| `launch.py` | starts `f3s.py all` detached, with no visible window, with `python -I` |
| `test_f3s.py` | CPU tests (no data, no GPU) |

## Data (stage 0 input, all CC BY 4.0, downloaded 2026-11-25, SHA-256 checked against DANDI)
| folder under `C:\Users\zhang\bci-data\raw` | DANDI | files | bytes |
|---|---|---|---|
| `falcon-h2` | 000950 v0.241029.1403 | 47 | 1,224,956,736 |
| `falcon-m1` | 000941 v0.241029.1405 | 11 | 311,792,278 |
| `nlb-mc-maze` | 000128 v0.220113.0400 | 2 | 694,004,935 |
| `nlb-mc-rtt` (already local; train file only) | 000129 v0.241017.1444 | 1 | 49,764,168 |

Manifest with hashes: `C:\Users\zhang\bci-data\raw\p15-54.manifest.json`.

## Stages
```
prep (CPU) -> gate 0: results/session_roles.json committed and pushed
  -> pretrain-I (10,000 steps) -> stage 1 (R, E, I x 2 LRs) -> selection.json
  -> gate 1: results/selection.json committed and pushed (exit code 4 until then)
  -> core: 36 normal runs + 21 C2 runs (+ conditional C2 pairs)      [core cap 9 h]
  -> pretrain-M -> stage 1 M -> selection-ext.json -> pretrain-P
  -> gate 2: results/selection-ext.json committed and pushed (exit code 4 until then)
  -> extended: 57 normal runs + 12 C2 runs                            [total cap 20 h]
  -> summary.json + results/summary.json (aggregates only)
```
All outputs go to `C:\Users\zhang\bci-data\derived\p15-54`. The runner refuses any other folder under `derived`. Caches, `result.json` files and weights stay there. The caches hold sentence texts, so never commit them.

## Commands (PowerShell, from the repo root)
Start only when no other GPU job runs (queue order: P15-50 -> A1 -> E2 -> this run).

Launch (hidden window, detached; it resumes if a checkpoint exists):
```powershell
C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-25-f3-small-data-falcon\launch.py
```
Check:
```powershell
Get-Content C:\Users\zhang\bci-data\derived\p15-54\run.log -Tail 20
Get-Process -Id (Get-Content C:\Users\zhang\bci-data\derived\p15-54\run.pid) -ErrorAction SilentlyContinue
Get-Content C:\Users\zhang\bci-data\derived\p15-54\gpu_clock.json
```
Stop (clean: the job saves `latest.pt` after the current step and exits with code 3):
```powershell
New-Item -ItemType File C:\Users\zhang\bci-data\derived\p15-54\stop
```
Resume:
```powershell
Remove-Item C:\Users\zhang\bci-data\derived\p15-54\stop
C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-25-f3-small-data-falcon\launch.py
```
After exit code 4 (`run.log`: "[gate] ... waits"): commit and push the named file under `results/`, then launch again.

Status files: `DONE` (finished or cap), `FAILED` (error; the launcher renames it to `FAILED.prev`), `STOPPED` (data stop, exit code 5), `run.pid`, `run.out`.

## Checkpoints
Every training part writes `latest.pt` every 4 min and at a pause; a re-launch resumes at that step (batches depend on the step index only, so a resume is exact). A finished run (`DONE.json`) is skipped. A hard stop loses at most 4 min.

## Smoke test (CPU, never the result folder)
```powershell
$env:HIP_VISIBLE_DEVICES="-1"; C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments\2026-11-25-f3-small-data-falcon\f3s.py smoke --out <scratch folder> --device cpu
```
It runs stage 0 on the real data, then every stage with 3 steps, cropped trials, seed 0 and no gates. Smoke numbers are not results.
