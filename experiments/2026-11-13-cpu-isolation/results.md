# M0-22 CPU isolation micro-benchmark (2026-11-13 19:55)

Script: `bench.py` (this folder). Raw numbers and the full `measurement_env` record of each condition: `results.json`.

## Set-up
- CPU: AMD Ryzen 7 9800X3D (8 cores, 16 logical CPUs, one CCD, shared 96 MB L3).
- Split from `fidetype.utils.isolation`: timing = logical CPUs 8, 10, 12, 14 (one per physical core 4-7). Their SMT siblings 9, 11, 13, 15 stay idle. Background = 0-7 (physical cores 0-3).
- Workload: one thread, 3 numpy 96x96 matmuls + a 15,000-step Python loop per iteration (about 0.33 ms). 20 s per condition. The first 50 iterations are dropped.
- Synthetic load: 8 processes. Each does a 16 MB numpy array pass plus a Python loop, in a loop.
- The M6-13 soak ran during the test. Its processes are not pinned (affinity 0xFFFF, normal priority). We did not change them. Desktop apps (OneDrive, browser, Spotify, IDE) also ran; machine load was about 37 % before the synthetic load.

## Results

| Condition | n | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|
| A: timing class, no synthetic load | 46,707 | 0.335 | 0.645 | 0.669 | 1.36 |
| B: timing class, load in background class | 40,992 | 0.501 | 0.661 | 0.765 | 1.27 |
| C: no isolation, same load unpinned at normal priority | 26,552 | 0.659 | 1.126 | 1.349 | 16.15 |

- B vs A: p50 +0.166 ms (+50 %), p95 +0.016 ms (+2.5 %), max unchanged.
- C vs A: p50 +0.324 ms (+97 %), p95 +0.481 ms (+75 %), max 16 ms (12x).
- B vs C: isolation cuts p95 by 41 % and removes the multi-millisecond stalls.

## Records (from `measurement_env`)
| Condition | load on timing CPUs | other (foreign) load on timing CPUs | load on idle siblings | clean |
|---|---:|---:|---:|---|
| A | 40.9 % | 15.9 % | 26.7 % | no |
| B | 63.0 % | 38.1 % | 55.8 % | no |

Both timing runs are flagged "not clean". Unpinned processes (the soak, desktop apps, other agents) still ran on the timing CPUs and on their SMT siblings. In B, the background CPUs were full (100 %), so the scheduler moved unpinned work onto the timing cores.

## What this means
- The timing class removes the long tail (p95, max) that the background load causes. This is the part that matters for latency claims.
- It does not remove all interference. The p50 still rises in B. Causes: the shared L3 cache and memory bandwidth (one CCD), and unpinned processes on the timing cores and their siblings.
- A measurement is only clean when the other heavy jobs also run in the background class. The record shows when this was not the case (`clean: false`, `foreign_load_pct`).
- This run is short (3 x 20 s) and on a busy desktop. Treat the numbers as a check that the tool works, not as a machine characterisation.
