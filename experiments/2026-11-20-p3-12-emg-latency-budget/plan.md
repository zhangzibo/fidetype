---
title: P3-12 in-beam LM EMG decoder plus guard inside the 50 ms CPU budget - pre-registration
type: experiment
task: P3-12
updated: 2026-11-20
---

# P3-12: guard end-of-window cost and CPU acoustic model inside the 50 ms budget (pre-registration)

Written and committed **before** the timed measurement of any candidate. Gap 122 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P3-12](../../wiki/questions/roadmap-standard.md#p3-12-guard-end-of-window-cost-and-cpu-acoustic-model-inside-the-50-ms-budget). Follow-up of [P11-07](../2026-11-20-p11-07-emg-beam-lm/results.md) (H5 fail) and [P3-06](../../wiki/questions/roadmap-standard.md#p3-06-logits-guard-inside-the-latency-budget-incremental-decoding) (gap 37).

**RESEARCH ONLY** (emg2qwerty data, CC BY-NC-SA 4.0). The repo gets aggregates only: no per-user value, no text, no id. Per-window files stay in `C:\Users\zhang\bci-data\derived\p3-12\`. The P11-01, P11-07, P11-09, P11-11 and P11-12 files are read only.

## Roadmap text (done when)
"a profile names the end-of-window costs; an incremental guard decision (features kept up to date while frames arrive) plus a faster CPU acoustic model (or the GPU path, stated as such) gives p95 <= 50 ms on the same 1,221 windows, with the same decisions as the offline guard (test)."

## Baseline (P11-07, committed)
- Decoder of the arm S guard: FL (w 0.25, beta 1, lam 8, beam 8, prune -8; `lmbeam.py`) -> intended merge (20-best) -> P11-11 OOV gate; P11-12 no-signal gate; guard `tcfg-60a1ffc45809f11f` (arm S, threshold 0.70).
- Added at the window end (last chunk push + n-best + merge + gates + `guard.decide`), 1 thread: FL@B8 p95 67.2 ms, F@B8 p95 67.6 ms.
- CPU acoustic model, one 4-frame chunk with its 121-frame receptive field (NumPy CRT, 4 threads, class timing): p95 47.1 ms.
- H5 rule: 67.6 + 47.1 = 114.7 ms > 50 ms (F@B8). Accuracy of arm S: certified safe WPM v0.1 3.37 [1.92, 5.18], 154 commits, 43 wrong; window top-1 intended CER (FL, pooled) 9.00 %.

## What was done before this plan (disclosure)
1. **Profile** (`cProfile`, 300 + 100 evaluation windows, not pinned, not timed for any verdict). End-of-window parts, p50 / p95: last push 0.02 / 0.03 ms, n-best 0.05 / 0.08 ms, intended merge 0.05 / 0.06 ms, no-signal gate 0.03 / 0.04 ms, OOV gate 0.01 / 0.01 ms, **`guard.decide` 19.7 / 33.6 ms**. Inside `guard.decide` (100 windows, 4.1 s): per-frame event work is almost all of it: `StreamingTrustLayer.push` per frame with `frame_row` (JSON list -> array) 2.5 s, the audit hash `_input_sha` (one `json.dumps` per frame) 1.1 s, `stream_events` (array -> JSON lists) 0.4 s. The decision itself (`_decide_frames`) is 0.1 s (1 ms per window). The acoustic model chunk recomputes the whole 121-frame receptive field for 4 new frames.
2. **Code written** (candidates C1 and C2 below) and checked for exactness, not for speed verdicts: streaming CRT vs batch on 800 frames of one session (u0 weights): max |log-prob diff| 1.5e-5, argmax agreement 1.0; one unpinned speed smoke: chunk p50 2.9 ms, p95 4.2 ms. Guard session vs `guard.decide` on 150 evaluation windows: identical result and audit record (except the clock fields `time_utc`, `latency_s`) on 150 / 150; unpinned smoke: `end()` p50 2.3 ms, p95 3.8 ms. These smoke numbers do not count; the verdict uses only the timed run below.
3. **Smoke run** of `run.py` on the first 12 evaluation windows into the scratch folder (not pinned; no verdict): the stages run; A1 12 / 12 per input kind; the streaming CRT log-prob diff reached 1.24e-4 on a long window (very small probabilities), so the CRT check uses the probability difference (below) instead of the log-prob difference; smoke times (12 windows): baseline end p95 about 31 ms, batch model chunk p95 about 39 ms, streaming chunk p95 about 4.5 ms, new decision p95 about 9 ms.
4. Targeted tests `tests/test_p3_12_streaming_latency.py` (13 pass) and the existing dropin, streaming, pretrained test files (83 pass).

## Candidates (fixed here, in this order)
| Id | Change | Where | Exact? |
|---|---|---|---|
| **C1** | Streaming CRT: each residual block keeps its last `(k-1) x dilation` LayerNorm outputs; a 4-frame chunk costs 4 frames of work (not 125) | `fidetype.pretrained._crt.CRTStream`, `TrunkStream` | same maths; float32 sums may differ in the last bits (check on every 25th evaluation window: max abs probability diff <= 1e-5 and argmax agreement 1.0 vs `_forward` on the same frames; the log-prob diff is reported) |
| **C2** | Incremental guard decision: `guard.session()`; `push(chunk)` does the per-frame work while frames arrive (row normalisation, frame event, its audit-hash line); `end()` sends the frames to the trust layer in one batch (`StreamingTrustLayer.push_frames`, no JSON) and decides | `fidetype.trust.dropin.GuardSession`, `fidetype.trust.streaming.StreamingTrustLayer.push_frames` | yes: the same `TrustResult` and audit record as `guard.decide` (test); a safety net falls back to `decide` if the rows or times differ |
| C2b | The streaming beam reads the rows that `session.push` returns (the guard's float32 rows), so its n-best equals the offline decoder's n-best on the guard stream | experiment code | yes (checked on all windows) |
| C3 | Threads: model at 1 thread (primary) and 4 threads (secondary, separate process) | runner | - |
| F1 (fallback, only if C1 + C2 miss the rule) | beam 4 instead of 8 | experiment | no: must pass the accuracy rule |
| F2 (fallback) | ONNX Runtime (MIT) or numba (BSD-2-Clause) as an optional extra for the model | not planned | not used if C1 + C2 pass (core stays NumPy only; extras policy in `pyproject.toml`) |

Not in scope: the GPU path (P15-33 holds the GPU; P11-07 GPU chunk p95 4.2 ms stays as reported). The P11-14 L-FL confidence (second beam, CTC re-scoring) is gap 125 (P11-15), not this item.

## Latency metric (primary, fixed here)
- Machine: the reference CPU (AMD Ryzen 7 9800X3D). Isolation runner, timing class: `python -m fidetype.utils.isolation run --class timing --threads 1 --env-json ... -- python -I run.py latency` (4 pinned physical cores, above-normal priority; BLAS threads 1). The measurement record (`clean`, foreign load) is saved and reported.
- Windows: the same 1,221 evaluation windows (P11-09 prompts, track-test sessions; key-CTC 33-class log-probs of P11-09), chunk 4 frames = 40 ms, the last chunk 1-4 frames (as P11-07). 20 warm-up windows first, not counted.
- Per chunk: `feat` (features of 4 new frames: `frames_from_block` on a 124-sample, 32-channel block; a fixed seeded block, the cost does not depend on the values) + `model` (C1 streaming CRT, u0 weights, on the session's own feature frames of the window: a cost stand-in, as in P11-07; the decisions use the P11-09 log-probs) + `session.push` + beam `push`.
- **Decision latency D (per window)** = one `perf_counter` span over: the last chunk's feat + model + `session.push` + beam push, then n-best + intended merge + no-signal gate + OOV gate + `session.end()`. This is the time from "the last 40 ms of signal is in" to "the decision is out".
- **Primary rule (gap 122):** p95 over the 1,221 windows of D <= **50 ms**, for FL@B8 (the arm S decoder).
- Real-time rule (needed too): p95 of the per-chunk time (feat + model + session.push + beam push) <= 40 ms (one chunk of signal).
- Also reported: F@B8; p50 / p95 / max of each part; the H5 form (end-of-window p95 + standalone model chunk p95); the re-measured P11-07 path (baseline B: raw rows into the beam, `guard.decide` at the end; batch model chunk with the receptive field at 1 and 4 threads) under the same conditions.

## Accuracy rule (fixed here)
- **A1 (same decisions, roadmap test):** for each of the 1,221 evaluation windows and each input kind (real, time-shuffled, zero EMG), the streaming pipeline (C2 + C2b) gives the same action, text, choices and `p_top1` as the offline guard (`guard.decide(x)` with a fresh, un-memoised FL `GuardDecoder` as `decode_fn`). Required: 3,663 / 3,663.
- **A2 (no loss vs P11-07):** on the stored P11-07 evaluation, with the streaming decisions: safe WPM v0.1 >= 3.37 - 0.05 and certified, wrong commits <= 43 + 1, time-shuffled and zero-EMG commits 0; window top-1 intended CER (FL@B8, pooled, no gate) <= 9.00 % + 0.10 points. If the streaming decisions equal the stored P11-07 decisions, A2 holds by construction (it is still computed). Differences against the stored file (P11-07 used a memo keyed on the window rounded to 3 decimals) are counted and reported.

## Verdicts
| Id | Statement |
|---|---|
| **V1 (primary, gap 122)** | FL@B8: p95 D <= 50 ms, per-chunk p95 <= 40 ms, A1 holds, A2 holds |
| V2 | The profile names the end-of-window costs (table in results) |
| V3 | F@B8 also meets the same latency rule |
| V4 | 4-thread model is faster than 1-thread (secondary) |

- If the isolation record is not clean (foreign load on the timing cores >= 5 %), the latency stage runs once more; the verdict uses the clean run, or the second run with a note.
- If V1 fails with C1 + C2, fallback F1 (beam 4) is measured the same way and must pass A2 to count. F2 is not run in this task (new gap).
- **Gap 122 closes only if V1 passes.** Otherwise it stays open with the measured floor (the smallest p95 D reached and its parts).

## Outputs
- `results/results.json` (aggregates), `results/run.log`, `results/latency.json` and `results/check.json` (aggregates only). Per-window decisions and times: `derived\p3-12\` only.
- results.md: every result, failures too.

## Rerun
- Tests: `.venv\Scripts\python.exe -m pytest -q tests/test_p3_12_streaming_latency.py`
- Full run (detached): `.venv\Scripts\python.exe experiments/2026-11-20-p3-12-emg-latency-budget/launch.py`; done when `C:\Users\zhang\bci-data\derived\p3-12\DONE` exists; stop: create `C:\Users\zhang\bci-data\derived\p3-12\STOP` (the stages stop between windows).

## Amendment 1 (2026-11-20 05:20, before any timed measurement)
At the first launch (05:19) the P15-34 agent ran two 4-thread background CPU jobs (machine load 82 %). The run was stopped after about one minute of the `check` stage (no timing had started). The driver now waits before each timing stage until no other registered CPU job (registered in the last 6 h) runs and the machine load over 20 s is below 25 %. It waits up to 3 h; then it writes `WAITING-NOT-QUIET` and stops before the timing stage. No metric, rule or candidate changes.

## Amendment 2 (2026-11-20 06:00, before any timed measurement)
The P15-34 CPU run is expected to end about 11:00 (HANDOFF). That is after the 3 h wait limit of amendment 1, so the wait limit is now 8 h. The `check` stage had finished (05:28); it is not run again. No metric, rule or candidate changes.
