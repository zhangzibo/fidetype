---
title: Trust reruns on the M4-13 decoder - queue, inputs and GPU plan
type: experiment
task: P15-03, P15-05, P15-06, P5-02
updated: 2026-11-16
---

# Trust reruns on the M4-13 decoder: queue plan

Written and committed **before** the M4-13 decoder has finished. One hidden queue runs four pre-registered reruns on the stronger T15 decoder as soon as M4-13 is done. Each rerun has its own pre-registration:

| stage | rerun | pre-registration |
|---|---|---|
| `p5-02` | P5-02 precision-type guarantee | [plan](../2026-11-17-p5-02-precision-m4-13/plan.md) |
| `p15-03` | P15-03a champion / challenger replay (F1, CPU part) | [plan](../2026-11-17-p15-03-f1-m4-13/plan.md) |
| `p15-05`, `p15-06`, `p15-06-t12` | F2: P15-05, P15-06 and the variant V-single (T15 + T12) | [plan](../2026-11-17-f2-m4-13/plan.md) |

## Inputs
- M4-13 finish marker `C:\Users\zhang\bci-data\runs\m4-13-queue.DONE` (read only). The M4-13 queue writes it after training, its GPU decode of val_eval (`derived/m4-13/logprobs-m4-13-long0-val_eval.npz`) and its CPU `eval.py`.
- `runs/m4-13-long0/best.pt` (read only).
- val_select log-probs (calibration set of every rerun): **not** made by the M4-13 queue. Our queue decodes them on the CPU with [decode_cpu.py](decode_cpu.py) into `derived/trust-reruns-m4-13/`.

## GPU coordination (no GPU use at all)
- The P11-01 waiter (pid 8400; `launch_train.py --wait-for`) polls the same DONE marker every 60 s and then starts GPU training (`train.py all`: pilot, generic up to 26 h, 8 personal). The waiter is not changed, killed or paused.
- So our queue never uses the GPU. The only decoder pass (val_select, and val_eval only as a fallback if the M4-13 queue wrote none) runs on the CPU: the CPU torch venv with `HIP_VISIBLE_DEVICES=-1` / `CUDA_VISIBLE_DEVICES=-1`, and the script asserts that torch sees no GPU.
- CPU speed (measured 2026-11-16, M4-12 fixed0 checkpoint, same architecture, background class, 4 threads): about 1 s per trial, so val_select (722) takes about 12-15 min. CPU and GPU output agree: max abs difference of the log-probs 4e-5, same argmax on all frames (8 val_select trials against the M2-19 GPU decode).
- All later stages are CPU-only trust experiments (background class, 4 threads). They share the CPU with P11-01 training, at below-normal priority.

## Queue ([run_queue.py](run_queue.py), started hidden by [launch.py](launch.py))
1. Wait (poll 60 s, CPU venv, no torch) for the DONE marker. `pause` or `stop` in `derived/trust-reruns-m4-13/` ends the wait.
2. `check`: DONE says `ok=True`; best.pt exists; if the M4-13 queue's val_eval decode exists, its checkpoint SHA-256 equals best.pt. Else stop and write `queue.FAILED` (no rerun on a failed or mixed decoder).
3. `decode-eval` (fallback only, if the M4-13 queue wrote no val_eval), `decode-select` (always).
4. `p5-02` (about 10 min), `p15-03` (4 runs; estimate 3-4 h: the dry run took 20 min for one run on 160 / 360 items), `p15-05` (8 arms with the LLM; about 2.5 h), `p15-06` (18 arms from the caches; about 1 h), `p15-06-t12` (8 arms from caches; about 10 min).
- Before each stage the queue waits up to 60 min for enough free RAM (decode 2.5 GB, P5-02 2.5 GB, P15-03 3 GB, P15-05 / P15-06 4.5 GB, P15-06 T12 6 GB in case the 3.5 GB T12 decoder loads after a cache miss; dry-run peaks below plus the LLM and a margin); else it stops with "deferred". Re-running the launcher resumes: a stage is done when `stage-<name>.done` exists; each stage also resumes inside (per arm / per run).
- A failed stage is logged; stages that need it are skipped, the others run. The queue holds a keep-awake (`SetThreadExecutionState`) while stages run. End: `queue.DONE` (JSON status per stage).
- Logs: `derived/trust-reruns-m4-13/queue.log` and `logs/<stage>.log`.

| action | command (repo root) |
|---|---|
| start (now or later; it waits for the marker) | `.venv\Scripts\python.exe experiments\2026-11-17-trust-reruns-m4-13\launch.py` |
| check | `Get-Content C:\Users\zhang\bci-data\derived\trust-reruns-m4-13\queue.log -Tail 5` |
| pause (after the current stage) | `New-Item C:\Users\zhang\bci-data\derived\trust-reruns-m4-13\pause` |
| hard stop | `taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\derived\trust-reruns-m4-13\queue.pid)` (loses at most the current arm / run) |
| resume | remove `pause`, then the start command |

## Rules
- Outputs only in new folders: `derived/trust-reruns-m4-13/`, `derived/p5-02-precision-m4-13/`, `derived/p15-03-f1-m4-13/`, `derived/f2-reruns-m4-13/`. Foreign derived folders are read only (`common.FOREIGN` assert). Per-trial data stay local; the repo gets aggregates only.
- Real runs refuse the dry-run settings (M4-12 source, stub LLM).
- Plans are committed before any M4-13 output exists. Any change after the first real run goes under "Deviations" in the results page.

## Dry runs (plumbing only, 2026-11-16, M4-12 subsets, no M4-13 data)
All dry runs use `TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12` (160 calibration items; 60 held out, P15-03 360), write to `dryrun/` subfolders and `results/dryrun-m4-12/`, and say nothing about the real results.

| part | result | peak RAM |
|---|---|---|
| CPU decode (`decode_cpu.py`, M4-12 fixed0 best.pt, 4 + 67 val_select items) | same keys as the M2-19 GPU decode; max abs difference 4e-5, same argmax on all frames; about 1 s per item | < 1 GB |
| P5-02 | runs end to end; all targets infeasible (expected on 160 items); controls pass | not measured (ran before the peak report was added) |
| P15-03a (1 seed, user feedback-r0.3) | 7 proposals, 7 decisions, ledger verifies; 0 phase-C commits; 1,232 s | 975 MB |
| P15-05 (stub LLM, arms A0 + B1) | prep, ground prep, 2 arms, held-out and swapped controls | 873 MB |
| P15-06 (stub LLM, A0, B1, B1@most_right, A0@single, B1@single) | runs; V-single tests all 120 non-fit items with an empty ordering set (primary: 60 + 60) | 740 MB |
| P15-06 T12 V-single (stub LLM, empty n-best on a cache miss) | runs; decoder and LLM not loaded | 670 MB |
| queue (`run_queue.py --dry` via `launch.py`, hidden) | waits, skips decode in dry mode, runs the stages with the env, resumes (stages skip done work), writes `queue.DONE`; `check()` tested on a fake ok / failed marker against the real best.pt (read only) | small |

Finding from the P15-03a dry run (both "decoders" are M4-12 there): the gate **accepted** the broken reversed decoder (B3). Both sides were wrong on 46-48 of 48 check items, so the top-1 sign test had 2 discordant pairs (p 0.25); the candidate never commits, so the null controls and the block LTT pass. Later, the per-item PER test found the real decoder much better than the broken one (PER 0.25 vs 0.82, Wilcoxon p 8e-10) where the sign test had 1 discordant pair. So with a weak champion the gate does not refuse a useless (non-committing) decoder. H3 tests whether the stronger M4-13 champion fixes this on real data; H7 reports the PER test. A PER-based (or non-inferiority) challenger test in `GuardedUpdateLoop` is an open item for P15-02 follow-up, not changed here.
