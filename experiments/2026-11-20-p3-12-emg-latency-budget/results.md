---
title: P3-12 in-beam LM EMG decoder plus guard inside the 50 ms CPU budget - results (INTERIM)
type: experiment
task: P3-12
updated: 2026-11-20
---

# P3-12: guard end-of-window cost and CPU acoustic model inside the 50 ms budget (results, INTERIM)

**Status: INTERIM.** The exactness and accuracy stage (`check`) is done. The timed stages (`latency`, `latency4`) have not run yet. The driver waits for a quiet machine (amendments 1 and 2; up to 8 h): the P15-34 agent runs two 4-thread CPU jobs (machine load 46-82 %). No latency verdict exists yet. Gap 122 stays open.

Pre-registration: [plan.md](plan.md) (commit `cfbc26e`, amendment 1 `a3d9f10`, time stamp fix `b32faab`, amendment 2 with this interim commit). Aggregates: [results/check.json](results/check.json), log [results/run.log](results/run.log).

**RESEARCH ONLY** (emg2qwerty data, CC BY-NC-SA 4.0). Aggregates only. Per-window files: `C:\Users\zhang\bci-data\derived\p3-12\` only.

## Profile: end-of-window costs (V2; disclosed in the plan, before the timed run)
FL@B8, 300 evaluation windows, not pinned, 1 thread.

| Part at the window end | p50 | p95 |
|---|---|---|
| Last chunk `push` (beam) | 0.02 ms | 0.03 ms |
| n-best | 0.05 ms | 0.08 ms |
| Intended merge | 0.05 ms | 0.06 ms |
| No-signal gate | 0.03 ms | 0.04 ms |
| OOV gate | 0.01 ms | 0.01 ms |
| **`guard.decide`** | **19.7 ms** | **33.6 ms** |

Inside `guard.decide` (cProfile, 100 windows, 4.1 s in total): per-frame trust-layer `push` with `frame_row` (JSON list to array) 2.5 s; audit hash `_input_sha` (one `json.dumps` per frame) 1.1 s; `stream_events` (array to JSON lists) 0.4 s; the decision itself (`_decide_frames`) 0.1 s. So nearly all of the end cost is per-frame JSON work, not the guard maths. The second cost is the acoustic model: the P11-07 chunk form recomputes the 121-frame receptive field for 4 new frames.

## Exactness and accuracy (stage `check`, 2026-11-20 05:20-05:28)
| Check | Result | Rule | Verdict |
|---|---|---|---|
| **A1**: streaming pipeline (guard session + beam on the session rows) vs offline guard (fresh, un-memoised FL decode) | real 1,221 / 1,221; time-shuffled 1,221 / 1,221; zero EMG 1,221 / 1,221 (action, text, choices, `p_top1`); n-best identical on 3,663 / 3,663 | 3,663 / 3,663 | **pass** |
| Same as the stored P11-07 decisions | 3,663 / 3,663 | (reported) | - |
| **A2**: safe WPM v0.1 (streaming decisions) | **3.37 [1.92, 5.18]**, certified; 154 commits, 43 wrong; time-shuffled and zero-EMG commits 0 / 0 | >= 3.32, certified, wrong <= 44, controls 0 | **pass** |
| A2: window top-1 intended CER (FL@B8, pooled, no gate) | 8.99 % (P11-07: 9.00 %) | <= 9.10 % | **pass** |
| C1 check (streaming CRT vs batch `_forward`, every 25th window, 49 windows) | max abs probability diff **3.08e-5**; max abs log-prob diff 5.9e-4; argmax agreement 1.0 | prob diff <= 1e-5 and argmax 1.0 | **fail as written** |

**C1, stated honestly.** The pre-registered C1 tolerance (1e-5) fails. A post-hoc check ([f64_check.py](f64_check.py), written after this failure; 12 windows of 1,000 frames, 6 sessions) runs both forms in float64 too:

| Comparison (max abs probability diff) | Value |
|---|---|
| float64 streaming vs float64 batch | **3.1e-15** (the algorithm is exact) |
| float32 batch (shipped `_forward`) vs float64 | 2.35e-5 |
| float32 streaming vs float64 | 1.29e-5 |
| float32 streaming vs float32 batch | 2.31e-5 |
| argmax agreement with float64 (both float32 forms) | 1.0 |

> **Our take:** the streaming CRT has the same maths as the batch model. The difference is float32 rounding, and the batch form has more of it than the streaming form. The 1e-5 tolerance in the plan was below the batch model's own float32 error. The decisions in this experiment use the P11-09 log-probs, so C1 does not change A1 or A2. A decision-level check with the streaming model in the loop is still open (see the gaps).

## Latency (PENDING)
Not measured yet. The `latency` stage (class timing, 1 thread) starts when the machine is quiet. The verdicts V1, V3 and V4 wait for it.

## How to continue
| Step | Command or file |
|---|---|
| Check | `C:\Users\zhang\bci-data\derived\p3-12\launcher.log` (lines "waiting before latency"), [results/run.log](results/run.log) |
| Done when | `C:\Users\zhang\bci-data\derived\p3-12\DONE` exists (or `WAITING-NOT-QUIET`: the 8 h wait ran out, then resume) |
| Stop | create `C:\Users\zhang\bci-data\derived\p3-12\STOP` |
| Resume | delete `STOP` / `WAITING-NOT-QUIET`, then `.venv\Scripts\python.exe experiments/2026-11-20-p3-12-emg-latency-budget/launch.py` (finished stages are skipped) |
| Then | write the latency part of this page from `results/results.json` against plan.md; records (gap 122, roadmap, tracker, log, HANDOFF) |
| Tests | `.venv\Scripts\python.exe -m pytest -q tests/test_p3_12_streaming_latency.py` (13 pass) |
