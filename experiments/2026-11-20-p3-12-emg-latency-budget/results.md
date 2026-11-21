---
title: P3-12 in-beam LM EMG decoder plus guard inside the 50 ms CPU budget - results
type: experiment
task: P3-12
updated: 2026-11-20
---

# P3-12: guard end-of-window cost and CPU acoustic model inside the 50 ms budget (results)

Pre-registration: [plan.md](plan.md) (commit `cfbc26e`; amendment 1 `a3d9f10`, time stamp fix `b32faab`, amendment 2 `eaa8152`, amendment 3 `6d4fdbd`; all before any counted timing). Aggregates: [results/results.json](results/results.json), [results/check.json](results/check.json), [results/latency.json](results/latency.json) (the counted run), [results/latency-run1.json](results/latency-run1.json) (run 1, not clean), [results/latency4.json](results/latency4.json), isolation records `results/iso-*.json`, log [results/run.log](results/run.log).

**RESEARCH ONLY** (emg2qwerty data, CC BY-NC-SA 4.0). Aggregates only: no per-user value, no text, no id. Per-window files: `C:\Users\zhang\bci-data\derived\p3-12\` only. The P11-01, P11-07, P11-09, P11-11 and P11-12 files were read only.

Runs (local clock): `check` 2026-11-20 05:20-05:28 (background class); `latency` run 1 21:19-21:45 (not clean: foreign load 5.32 % >= 5 %); **`latency2` 21:45-22:10 (clean: foreign load 3.47 %; counted)**; `latency4` 22:10-22:11 (clean); `score` 22:11. CPU only, isolation class timing (cores 8, 10, 12, 14, above-normal priority, 1 BLAS thread). The GPU was not used.

## Outcome
**The P11-07 in-beam LM decoder plus the arm S guard now decides within the 50 ms CPU budget.** On the same 1,221 evaluation windows, the decision latency (last 40 ms chunk in -> decision out, acoustic model included) is **p95 6.39 ms** (p50 4.93 ms, max 11.0 ms). The P11-07 path took 67.2 ms p95 at the window end plus 47.1 ms for the CPU model chunk. A 40 ms chunk costs p95 3.48 ms, so the stream stays real time. The decisions are the same as the offline guard on 3,663 / 3,663 windows (real, time-shuffled, zero EMG), and safe WPM v0.1 stays 3.37 [1.92, 5.18], certified. **V1 passes. Gap 122 closes.**

## Verdicts (pre-registered)
| Id | Statement | Result | Verdict |
|---|---|---|---|
| **V1 (primary, gap 122)** | FL@B8: decision p95 <= 50 ms, chunk p95 <= 40 ms, A1, A2 | **6.39 ms**, 3.48 ms, A1 3,663 / 3,663, A2 pass | **pass** |
| V2 | A profile names the end-of-window costs | table below | **pass** |
| V3 | F@B8 meets the same latency rule | 6.31 ms, 3.46 ms | **pass** |
| V4 | 4 threads faster than 1 thread for the streaming model chunk | p95 2.03 vs 2.93 ms (4-thread max 59.7 ms) | **pass** (secondary) |
| A1 | Same decisions as the offline guard (fresh decode) | 1,221 / 1,221 for each of real, shuffled, zeros; n-best identical on all | **pass** |
| A2 | No accuracy loss vs P11-07 | safe WPM 3.37 [1.92, 5.18] certified, 154 commits / 43 wrong, controls 0 / 0; window top-1 intended CER 8.99 % (P11-07 9.00 %) | **pass** |
| C1 check | Streaming CRT vs batch: prob diff <= 1e-5, argmax 1.0 | 3.08e-5, argmax 1.0 | **fail as written** (see C1) |

## Profile: end-of-window costs (V2; disclosed in the plan, before the timed run)
FL@B8, 300 evaluation windows, not pinned, 1 thread.

| Part at the window end (P11-07 path) | p50 | p95 |
|---|---|---|
| Last chunk `push` (beam) | 0.02 ms | 0.03 ms |
| n-best | 0.05 ms | 0.08 ms |
| Intended merge | 0.05 ms | 0.06 ms |
| No-signal gate | 0.03 ms | 0.04 ms |
| OOV gate | 0.01 ms | 0.01 ms |
| **`guard.decide`** | **19.7 ms** | **33.6 ms** |

Inside `guard.decide` (cProfile, 100 windows, 4.1 s): per-frame trust-layer `push` with `frame_row` (JSON list to array) 2.5 s; audit hash `_input_sha` (one `json.dumps` per frame) 1.1 s; `stream_events` (array to JSON lists) 0.4 s; the decision itself (`_decide_frames`) 0.1 s. The second cost: the P11-07 model chunk recomputes the 121-frame receptive field for 4 new frames.

## Latency (counted run `latency2`, clean)
### Decision latency, new path N (1,221 windows after 20 warm-up windows)
| Path | Decision D p50 / p95 / max | End work (after the last chunk) p95 | Last chunk p95 | Per chunk p50 / p95 / max |
|---|---|---|---|---|
| **N FL@B8 (arm S decoder)** | 4.93 / **6.39** / 11.0 ms | 3.33 ms | 3.60 ms | 3.15 / **3.48** / 5.9 ms |
| N F@B8 | 4.90 / 6.31 / 15.5 ms | 3.31 ms | 3.52 ms | 3.11 / 3.46 / 6.4 ms |

D = last chunk (features + streaming model + `session.push` + beam push) + n-best + merge + gates + `session.end()`, in one `perf_counter` span.

| Per-chunk part (N FL@B8) | p50 | p95 | max |
|---|---|---|---|
| Features (4 frames from 124 samples) | 0.08 ms | 0.10 ms | 0.57 ms |
| Streaming CRT model (C1) | 2.84 ms | 3.11 ms | 5.41 ms |
| `session.push` (C2) | 0.10 ms | 0.13 ms | 0.79 ms |
| Beam push | 0.10 ms | 0.24 ms | 0.86 ms |

### Baseline B (the P11-07 path, re-measured now under the same conditions)
| Measure | p50 | p95 | max | P11-07 (2026-11-19) |
|---|---|---|---|---|
| B FL@B8 added at the window end (`guard.decide` at the end) | 15.6 ms | **32.6 ms** | 96.8 ms | p95 67.2 ms |
| B F@B8 added at the window end | 15.4 ms | 32.8 ms | 87.7 ms | p95 67.6 ms |
| Batch model chunk with receptive field, 1 thread | 19.9 ms | 20.5 ms | 21.1 ms | - |
| Batch model chunk with receptive field, 4 threads | 18.2 ms | 20.3 ms | 143.1 ms | p95 47.1 ms |
| Streaming model chunk (C1), 1 thread / 4 threads | 2.73 / 1.77 ms | 2.93 / 2.03 ms | 3.36 / 59.7 ms | - |
| H5 form (B FL@B8): end p95 + batch model p95 (1 thread) | - | 53.1 ms | - | 114.7 ms (F@B8) |

> **Our take:** the re-measured baseline is about half the P11-07 number (32.6 vs 67.2 ms at the end; batch model 20.5 vs 47.1 ms). P11-07 ran its latency stage while other agents' CPU jobs ran (its deviation 4), and the record was empty; this run is clean. So part of the old 114.7 ms was machine load, not code. Even so, the clean baseline is 53.1 ms in the H5 form, over the budget. The two changes take it to 6.4 ms, about 8x below the budget. Most of the remaining time is the model (3.1 ms per chunk). The 4-thread model is faster at p95 but has rare long stalls (max 59.7 ms), so 1 thread is the safer default for streaming.

### Run 1 (not clean, reported, not counted)
Foreign load 5.32 % on the timing cores (limit 5 %), so the plan rule ran `latency2`. Run 1 numbers are almost the same: N FL@B8 D p95 6.44 ms, chunk p95 3.62 ms; B FL@B8 end p95 33.0 ms; batch model 20.9 ms, streaming 3.16 ms ([latency-run1.json](results/latency-run1.json)).

## Exactness and accuracy (stage `check`)
| Check | Result |
|---|---|
| A1: streaming pipeline vs offline guard (fresh, un-memoised FL decode as `decode_fn`) | real 1,221 / 1,221; time-shuffled 1,221 / 1,221; zero EMG 1,221 / 1,221 (action, text, choices, `p_top1`); n-best identical on 3,663 / 3,663 |
| Same as the stored P11-07 decisions | 3,663 / 3,663 |
| A2: safe WPM v0.1 | 3.37 [1.92, 5.18], certified; 154 commits, 43 wrong (0.035, CP95 [0.026, 0.047]); time-shuffled 0, zero EMG 0 commits |
| A2: window top-1 intended CER (FL@B8, pooled, no gate) | 8.99 % (P11-07 9.00 %) |
| Targeted tests | `tests/test_p3_12_streaming_latency.py` 13 pass; existing dropin, streaming, pretrained, TD-input test files 83 pass |

### C1, stated honestly
The pre-registered C1 tolerance fails: max probability difference 3.08e-5 > 1e-5 (49 windows; log-prob diff 5.9e-4; argmax agreement 1.0). A post-hoc check ([f64_check.py](f64_check.py), written after this failure; 12 windows of 1,000 frames, 6 sessions) also runs both forms in float64:

| Comparison (max abs probability diff) | Value |
|---|---|
| float64 streaming vs float64 batch | **3.1e-15** (the algorithm is exact) |
| float32 batch (shipped `_forward`) vs float64 | 2.35e-5 |
| float32 streaming vs float64 | 1.29e-5 |
| float32 streaming vs float32 batch | 2.31e-5 |
| argmax agreement with float64 (both float32 forms) | 1.0 |

> **Our take:** the streaming CRT has the same maths as the batch model. The difference is float32 rounding, and the batch form has more of it than the streaming form. The 1e-5 limit was below the batch model's own float32 error. The decisions here use the P11-09 log-probs, so C1 does not touch A1 or A2. A test with the streaming model's own output in the decision loop is still open (new gap 139).

## What changed in the code
| Change | Where | Exact |
|---|---|---|
| C1 streaming CRT (per-block history of `(k-1) x dilation` LayerNorm outputs) | `fidetype.pretrained._crt.CRTStream`, `TrunkStream` | same maths (float64: 3e-15); float32 rounding as above |
| C2 incremental guard decision: `guard.session()`; `push(chunk)` does the per-frame work (normalisation, frame event, audit-hash line); `end()` decides | `fidetype.trust.dropin.GuardSession`, `TrustGuard.session` | the same `TrustResult` and audit record as `decide` (only `time_utc`, `latency_s` differ); a safety net falls back to `decide` |
| Batch frame push into the trust layer (no JSON); shared per-frame body | `fidetype.trust.streaming.StreamingTrustLayer.push_frames` | same checks and state as per-event `push` (test) |
| C2b: the streaming beam reads the rows that `session.push` returns | experiment code | n-best identical on 3,663 / 3,663 |

Not used: fallback F1 (beam 4) and F2 (ONNX Runtime / numba). The core stays NumPy only. Not measured: the GPU path (P11-07: 4.2 ms p95 model chunk).

## Deviations (stated honestly)
1. **Amendment 1** (05:20): the first launch met two 4-thread P15-34 CPU jobs (load 82 %). It was stopped about 1 min into `check`; the driver now waits for a quiet machine before each timing stage.
2. **Amendment 2** (06:00): wait limit 3 h -> 8 h (P15-34 ran past 3 h).
3. **Amendment 3** (21:18, bug fix): the first timed stage started at 09:52:32 and crashed at 09:52:33, before any window was timed. `gate_pass` read `k_min = None` because only a P11-07 `GuardDecoder` constructor loads the P11-12 gate thresholds and the OOV lexicon, and the `latency` stage built none. Fixed in `run.py` (`Ctx` builds one, with asserts); a 12-window smoke run in a fresh process now runs before the timed stage. No rule changed.
4. The plan-time smoke run hid the amendment 3 bug (`check` ran first in the same process).
5. Run 1 was not clean (5.32 % foreign load); the counted run is `latency2` (plan rule). Both runs give almost the same numbers.
6. The acoustic model in the timing uses the u0 weights on every window (a cost stand-in, as in P11-07). The features are computed on a fixed seeded raw block (the cost does not depend on the values).

## Gap rule
- **Gap 122 closes** (V1 passes on the clean run under the pre-registered rule).
- Gap 37 (P3-06) is not closed by this item: it needs the collector's guard processor on the `implant-logits` bench profile and a CI gate. `GuardSession` and `push_frames` are the parts it can use (evidence line in the roadmap).
- Gap 125 (P11-15, the L-FL confidence cost) stays open; this item did not measure L-FL.

## New gaps
| Gap | Item | What |
|---|---|---|
| 139 | P3-13 | Streaming CRT model in the decision loop: same decisions as the batch log-probs. Done when the streaming model output (per-user weights) feeds the guard session and the beam on the 1,221 windows, and the decisions match those from the batch log-probs (or the differences are counted and the safe WPM stays within the P3-12 tolerance) |

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q tests/test_p3_12_streaming_latency.py` |
| Full run (detached; about 1 h with a quiet machine) | `.venv\Scripts\python.exe experiments/2026-11-20-p3-12-emg-latency-budget/launch.py`; done when `C:\Users\zhang\bci-data\derived\p3-12\DONE` exists; stop: create `...\p3-12\STOP` |
| Smoke run (12 windows, not counted) | `.venv\Scripts\python.exe -I experiments/2026-11-20-p3-12-emg-latency-budget/run.py latency --smoke 12` |
| Float64 check | `.venv\Scripts\python.exe -I experiments/2026-11-20-p3-12-emg-latency-budget/f64_check.py` |

## Limits
- One machine (AMD Ryzen 7 9800X3D), offline component replay, not a collector end-to-end stream.
- The model weights are those of one user (cost only); the decisions use the P11-09 log-probs.
- 8 users, one track-test session each (the safe-WPM CI uses the user as the cluster unit).
