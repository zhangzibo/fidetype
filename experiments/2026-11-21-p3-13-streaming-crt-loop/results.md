---
title: P3-13 streaming CRT model in the decision loop - results
type: experiment
task: P3-13
updated: 2026-11-21
---

# P3-13: streaming CRT model in the decision loop (results)

Pre-registration: [plan.md](plan.md) (commit `f7f66b0`, before the counted run). Aggregates: [results/results.json](results/results.json), [results/check.json](results/check.json), [results/latency.json](results/latency.json), isolation record [results/iso-latency.json](results/iso-latency.json), log [results/run.log](results/run.log).

**RESEARCH ONLY** (emg2qwerty data, CC BY-NC-SA 4.0). Aggregates only: no per-user value, no text, no id. Per-window decisions and the exported weights: `C:\Users\zhang\bci-data\derived\p3-13\` only. The P11-01, P11-07, P11-09, P11-11, P11-12 and P3-12 files were read only.

Runs (local clock, 2026-11-21): weights export 05:27 (torch venv, CPU); `check` 05:32-06:32 (background class, 2 threads); `latency` 07:29-07:45 (timing class, 1 thread, **clean**: foreign load 4.0 %); `score` 07:45. The driver waited 06:32-07:29 for a quiet machine. CPU only. The GPU was not used.

## Outcome
**The streaming CRT model with the per-user weights now feeds the guard session and the beam, and it gives the same decisions as the batch log-probs on 3,663 / 3,663 windows** (1,221 evaluation windows x real, time-shuffled, zero EMG). Safe WPM v0.1 stays **3.37 [1.92, 5.18], certified** (154 commits, 43 wrong, controls 0 / 0), the same as P3-12. With the real model in the loop, the decision latency is **p95 8.02 ms** (budget 50 ms) and a 40 ms chunk costs p95 4.94 ms. **V1 passes (by M1). Gap 142 closes.**

## Verdicts (pre-registered)
| Id | Statement | Result | Verdict |
|---|---|---|---|
| **M1** | Same `action`, `text`, `choices`; abs `p_top1` diff <= 1e-3 | **3,663 / 3,663**; max abs `p_top1` diff 2.1e-5 | **pass** |
| M2 (fallback) | Safe WPM v0.1 >= 3.32, certified, controls 0 | 3.37 [1.92, 5.18] certified, shuffled 0, zeros 0 | pass (not needed) |
| **V1 (primary, gap 142)** | M1 or M2 | M1 | **pass** |
| C2 (secondary) | Max abs probability diff of the 33-column guard rows <= 1e-3 per kind | real 2.2e-4, shuffled 1.2e-5, zeros 9.7e-4 | pass |
| L1 (secondary) | Decision p95 <= 50 ms, chunk p95 <= 40 ms | 8.02 ms, 4.94 ms | pass |

## Decisions: streaming model (S) vs batch log-probs (B)
| Measure | real | shuffled | zeros |
|---|---|---|---|
| Same action, text, choices | 1,221 / 1,221 | 1,221 / 1,221 | 1,221 / 1,221 |
| Exact `p_top1` equality | 148 | 1,221 | 1,221 |
| Max abs `p_top1` diff | 2.1e-5 | 0 | 0 |
| Same n-best texts (after the gates) | 1,221 | 1,221 | 1,221 |
| Same n-best with exact scores | 136 | 1,221 | 1,221 |
| Same no-signal gate result | 1,221 | 1,221 | 1,221 |
| Commits S / B | 154 / 154 | 0 / 0 | 0 / 0 |
| Path B same as the stored P3-12 decisions | 1,221 | 1,221 | 1,221 |
| Max abs probability diff (33 columns) | 2.2e-4 | 1.2e-5 | 9.7e-4 |
| Max abs log-prob diff | 9.9e-4 | 4.0e-4 | 2.23 |
| Frame argmax agreement (min) | 1.0 | 1.0 | 1.0 |

> **Our take:** the two paths differ only in float32 rounding (NumPy streaming vs torch batch). The rounding moves the n-best scores and `p_top1` in the low digits. It never changes a key, an n-best text, a gate result or an action. Shuffled and zero-EMG windows never pass the no-signal gate, so their outputs are empty in both paths (exact equality). The zero-EMG input has the largest differences (probability 9.7e-4, close to the C2 limit; log-prob 2.23 on very small probabilities). This input is far outside the training data, so the activations are large and float32 rounding grows. It does not change any decision, because the gate stops these windows.

## Accuracy (P11-11 scorer, arm S sheet)
| Path | Safe WPM v0.1 | Commits | Wrong | Wrong CP95 | Shuffled commits | Zero commits |
|---|---|---|---|---|---|---|
| S streaming model | **3.37 [1.92, 5.18]** certified | 154 | 43 | [0.026, 0.047] | 0 | 0 |
| B batch log-probs | 3.37 [1.92, 5.18] certified | 154 | 43 | [0.026, 0.047] | 0 | 0 |

## Latency (counted run, clean; real windows, FL@B8)
D = the last chunk (features + streaming model + merge to 33 columns + `session.push` + beam push), then n-best + intended merge + gates + `session.end()`, in one `perf_counter` span. 1,221 windows after 20 warm-up windows.

| Measure | p50 | p95 | max |
|---|---|---|---|
| **Decision D** | 5.41 ms | **8.02 ms** | 13.7 ms |
| Work after the last chunk | 2.14 ms | 4.15 ms | 10.3 ms |
| Last chunk | 3.34 ms | 4.75 ms | 5.7 ms |
| **Per chunk (212,805 chunks)** | 3.55 ms | **4.94 ms** | 12.8 ms |
| - features | 0.09 ms | 0.14 ms | 0.77 ms |
| - streaming model (per-user weights) | 3.08 ms | 4.27 ms | 11.9 ms |
| - merge to 33 columns | 0.13 ms | 0.21 ms | 0.78 ms |
| - `session.push` | 0.11 ms | 0.17 ms | 0.52 ms |
| - beam push | 0.11 ms | 0.35 ms | 5.8 ms |

> **Our take:** P3-12 measured p95 6.39 ms with a cost stand-in (u0 weights, no merge). The real loop adds the merge (0.2 ms p95) and the model is a little slower (p95 4.27 vs 3.11 ms per chunk). The cause is not clear: the 8 user weights have the same shapes, but the machine load during the run was higher (background class load 41.5 %, foreign load on the timing cores 4.0 %). The decision is still about 6x below the 50 ms budget.

## Code
No code bug was found. No library code changed (`src/` untouched). New experiment code only: [export_params.py](export_params.py) (per-user `best.pt` -> NumPy arrays, CPU), [run.py](run.py), [launch.py](launch.py). No regression test was added (the rule was "if a code bug is found").

## Deviations (stated honestly)
1. **CER metric.** The plan listed the window top-1 intended CER "(FL@B8, pooled, no gate)". The code computed it from the `top1` field of the decision record, which is the top-1 **after** the no-signal and OOV gates (empty when a gate withholds; 136 of 1,221 real windows). That value is 18.3 % and is not comparable with the P3-12 / P11-07 9.0 % (no gate). The gated top-1 text is the same in both paths on 1,221 / 1,221 windows, so the gated CER is equal for S and B. The no-gate CER of path S was not computed. No verdict uses it.
2. The C2 bound held on the zero-EMG input with a small margin (9.7e-4 vs 1e-3).

## Gap rule
- **Gap 142 closes** (V1 passes by M1; the safe WPM rule also holds).

## Rerun
| Step | Command (repo root) |
|---|---|
| Weights export (torch venv, CPU only) | `C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-21-p3-13-streaming-crt-loop/export_params.py` |
| Full run (detached; about 1 h 20 min plus the wait for a quiet machine) | `.venv\Scripts\python.exe experiments/2026-11-21-p3-13-streaming-crt-loop/launch.py`; done when `C:\Users\zhang\bci-data\derived\p3-13\DONE` exists; stop: create `...\p3-13\STOP` |
| Smoke (8 windows, not counted) | `.venv\Scripts\python.exe -I experiments/2026-11-21-p3-13-streaming-crt-loop/run.py check --smoke 8` |

## Limits
- One machine (AMD Ryzen 7 9800X3D); offline component replay, not a collector end-to-end stream.
- 8 users, one track-test session each.
- Each window starts its model stream 120 frames before the window (the receptive field). A live stream runs from the session start; the maths is the same, the rounding can differ in the last bits.
