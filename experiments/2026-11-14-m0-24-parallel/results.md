---
title: "M0-24: parallel experiment runner (pmap): speed-ups and equality checks"
type: experiment
task: M0-24
updated: 2026-11-14
---

# M0-24: parallel experiment runner

New helper `fidetype.utils.parallel.pmap` (process pool, spawn, background CPU class, 1 thread per worker, per-item seeds, input order, checkpoints, serial fallback). How to use it: [compute-setup, "Parallel CPU experiments with pmap"](../../wiki/questions/compute-setup.md#parallel-cpu-experiments-with-pmap-2026-11-14-m0-24). Tests: `tests/test_parallel.py` (11, synthetic).

All check outputs are outside the repo: `C:\Users\zhang\bci-data\runs\m0-24-parallel\`. Check scripts: [check_equal.py](check_equal.py), [m302_rows.py](m302_rows.py), [queue_splits.sh](queue_splits.sh).

## 1. The slow serial loops (before)

| Loop | Where | Unit | Serial wall time (recorded) |
|---|---|---|---|
| B2T 816-trial replays, uncached decode | M4-06 `run.py uncached`, M4-09 (11 conditions), M4-10, M6-11 | trial / session | M4-06 232 s per condition; M4-09 about 1 h 15 min |
| Repeated-split item tables (Paper 1 Tab. 2, R = 200) | R4 `split-tables/run.py --stage b2t` | one split x job | 24 s per guard-on table, 3-4 s per guard-off table; 1,050 tables took 37 min on 11 hand-sharded processes |
| Paper 1 T15 refits (6 fits) | M2-18 `t15_eval.py` | one fit | 255 s (warm cache) |
| M3-02 ablations | `run_b2t.py`, `run_meg.py`, `run_sim.py`, `run_emg.py` | split / run / condition | B2T 5 min per decoder; MEG 11-25 min per run; simulator 9-15 min per condition (6 conditions); sEMG 3 min |
| M3-02 repeated-split rows | `run_b2t.py --stage splits` | split | 7 s per decoder (cached tables): too short to gain |

We converted the first three (the heaviest with independent units) and left the others as candidates (the simulator and MEG runs have one condition / run per unit; the same pattern applies).

## 2. Machine state during the checks

The background class (CPUs 0-7, 4 physical cores) was shared with 4-5 other registered jobs (trust-v5 runs, the GPU trainer's CPU process) at about 80 % load, and free RAM was 4-7 GB. Each B2T worker holds its own decoder context (about 0.9-1.3 GB). The automatic sizing (free background slots, then free RAM / 1.6 GB) therefore gave **2-4 workers**, not 8. The speed-ups below are for these worker counts.

## 3. Speed-ups (same machine, same load class, serial = `--workers 1`)

| Experiment | Serial | Parallel | Workers | Speed-up |
|---|---|---|---|---|
| M2-18 T15: all 6 Paper 1 fits + controls (warm decode cache) | 255.4 s | 120.0 s | 2 (RAM limit) | **2.1x** |
| R4 split tables, subset r 50-53 x 4 jobs (16 tables) | 207.8 s | 70.8 s | 4 | **2.9x** |
| R4 split tables, full rebuild: guard on r 50-199, ours + published (300 tables) | about 6,600 s (estimate: 22 s per table, the serial subset rate) | 1,958 s | 4 | **about 3.4x** |
| R4 split tables, full rebuild: guard off r 0-199, ours + published (400 tables) | about 1,300 s (estimate: 3.3 s per table) | 465 s | 3 | **about 2.8x** |
| M4-06 B2T replay, 816 trials, uncached decode (replay part) | 158 s | 85 s | 2 (RAM limit) | **1.9x** |

- The gain per worker is below 1 because the background CPUs were busy with other jobs and SMT siblings share a core. The table CPU sum rose from 201 s (serial) to 240 s (4 workers) on the subset.
- First T15 attempt (cold cache): 386 s serial vs 256 s with 3 workers (1.5x). The serial run reused decodes of one fit in a later fit; the workers could not. `t15_eval.py` now loads its own saved decodes in setup. The output is unchanged (checked below).

## 4. Equality checks (parallel vs serial)

| Check | Result |
|---|---|
| T15, 6 fits (Paper 1 v4 refits: ours / published x split A, split B, full fit; test, controls, gates A-C) | `t15.json` **equal** parallel = serial = committed M2-18 file (only the wall-time `seconds` keys ignored); `t15.md` **byte-equal** to the committed file. Paper 1 Tab. 1 reproduced in all four split fits |
| R4 split tables, subset (16 tables) | **16/16 byte-equal** parallel vs serial, and 16/16 byte-equal to the R4 cache |
| R4 split tables, full R = 200 rebuild (700 tables) | **699/700 byte-equal** to the R4 cache (built in 2026-11-12 by the serial loop on 8 hand-sharded processes). The other file (`b2t-ours-g1-123.json`) differs only in `new_decodes` (0 now, 28 then: the R4 run decoded the new frame temperature 3.42 for the first time). All scores, outcomes and fitted settings are equal |
| M3-02 repeated-split rows (B2T ours / published, R 200; v4 baseline row and all arms) from the rebuilt tables | **equal** to the committed M3-02 `results/splits.json` (both decoders, all arms). v4 baseline: ours mean wrong-commit 0.0321, > α in 0.075 of splits; published 0.0303, 0.055 (as M3-02 and Paper 1 R4). r < 50 guard-on tables still come from the R3 cache |
| M4-06 B2T replay, 816 decisions | **816/816** equal parallel vs serial (every field of the decision event except `latency_s`); 816/816 equal to the committed M4-06 derived file; 816/816 equal to the batch harness; metrics (wrong-commit 0.0245, 20 / 82 commits, eWPM 11.48) equal |

Ignored keys are wall times only (`seconds`, `wall_s`) and, for the replay, the latency fields. Under parallel load the replay latency is not a latency result; the M4-06 latency numbers stay the serial timing-class ones.

## 5. Code changes in the experiment scripts (no change to configs or logic)

- `t15_eval.py`: the body of the fit loop is now `run_fit(fit)`; setup moved into `setup()` (pmap initializer). Thread variables use `setdefault` (as `common.py`), so workers keep 1 thread. Setup also reads the task's own decode cache. Flags `--workers`, `--exact-workers`, `--out`, `--checkpoint`.
- `split-tables/run.py`: `--stage b2t --workers N` runs one table per task (`b2t_task`, the same loop body as `stage_b2t`). Tasks are sorted by frame temperature, so a worker keeps one decode cache. Existing tables are skipped (resume). `--out`, `--jobs`, `--r-from`, `--r-to` select the output folder and the tables. The old `--worker / --nworkers` sharding still works.
- M4-06 `run.py uncached --workers N`: one task per session (post-implant day), longest first, with a fresh `StreamingTrustLayer` per session; decisions and timings are put back in trial order. Only for the uncached frames replay without a ledger. `--out` redirects results and per-trial outputs.
- `fidetype.utils.isolation.register_job` has a new optional `slots` field (CPUs a job keeps busy); pmap registers its worker count there.

## 6. Limits

- RAM, not CPUs, limits the worker count for B2T work on this PC while other agents run. Shared decoder memory (memory-mapped LM tables) would need changes inside the decoders; not done.
- Workers do not share memo caches; persist new decodes to disk so that every worker starts warm.
- Latency must still be measured serially in the timing class.
