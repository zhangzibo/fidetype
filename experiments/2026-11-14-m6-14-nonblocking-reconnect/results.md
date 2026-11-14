---
title: "M6-14: non-blocking LSL reconnect: results"
type: experiment
task: M6-14
updated: 2026-11-14
---

# M6-14: non-blocking LSL reconnect (results)

The M6-13 soak test found that an LSL reconnect blocked the trust loop for up to 6.1 s: `LSLEventSource.poll()` resolved and opened the new stream itself. No data was lost (LSL buffers it), but the loop could not serve other inlets, timers or a stop signal during that time.

## Change
- `fidetype.adapters.lsl`: new `LSLMapping.reconnect_mode` = `"thread"` (default) or `"inline"` (the old path).
- In thread mode, a loss starts a worker thread (`_Reconnector`). It calls `reopen()` (resolve + inlet open) until it gets an inlet, then asks the new inlet for one `time_correction()` (liblsl's first estimate takes about 0.65 s on this PC). It hands the ready inlet to the loop.
- `poll()` never waits for the worker longer than its own `timeout` (at least `reconnect_handoff_s` = 5 ms). The wait goes to the first live inlet; only if no inlet is live does the reconnect wait for the hand-off.
- The rules do not change. The loss still aborts the open utterance (no decision on a cut utterance). The `reconnected` status and the new header come in the same order. `reconnect_timeout_s` still raises `LSLStreamLost` (and cancels the worker). `close()` cancels the worker; an inlet that comes after the cancel is closed.
- The FEP-0002 conformance profile uses `reconnect_mode="inline"`: its reference consumer must be deterministic.
- Demo decoder: `RefCharLM` memo is now an `LRUCache` (M4-10), default bound 32,768 entries (the soak saw about 20,000 after 6.5 h). A memo bound changes the cost, never a value.

## Measurement
Script: [measure.py](measure.py); numbers: `results/stall.json`. One Windows PC, pylsl 1.18.6, poll timeout 20 ms. **CPU class: background** (cores 0-7, shared with a GPU training job and other agents). The timing lock was free, but the causal-decoder agent was about to take it for its latency tests; the effect here is 100x, so background was enough.

"Stall" = the duration of one `runner.step()` call, from the producer stop (B) or the loss (A) until the reconnect, both steps included. A step with no data waits for the poll timeout: 20 ms becomes about 32 ms on Windows (15.6 ms timer). So about 32 ms is the floor, not a stall.

A. Fake inlets, a fake resolver that sleeps D seconds:

| resolve D | inline: steps / max | thread: steps / p50 / p99 / max |
|---|---|---|
| 0.5 s | 1 / 504 ms | 16 / 32.3 / 33.5 / 33.5 ms |
| 2.0 s | 1 / 2,005 ms | 62 / 32.7 / 44.4 / 46.1 ms |
| 6.0 s | 1 / 6,003 ms | 183 / 32.5 / 42.3 / 66.4 ms |

B. Real LSL on localhost: a 25 Hz NTS outlet goes away and comes back with the same `source_id` after 1.5 s or 4 s. Three repeats per cell.

| | inline (before) | thread (after) |
|---|---|---|
| steps from stop to reconnect | 3-4 | 201-234 |
| max step | **5,556-5,607 ms** | **41.7-47.9 ms** in 5 of 6 runs; 141.8 ms in 1 |
| p99 step | 5,451-5,509 ms | 35.9-40.5 ms |
| reconnect step (attach + new header) | 707-753 ms (first `time_correction()`) | 12.9-47.9 ms (pre-warmed in the worker) |
| loss seen after producer stop | 0.00-0.02 s | 0.00-0.14 s |
| reconnect after producer stop | 6.29-6.92 s | 6.35-7.46 s |

Findings:
- **Before:** the loop is blind for about 5.6 s in one step, then about 0.7 s more for the new header. This matches the 6.1 s of the soak test.
- **After:** the max step is below 50 ms in 5 of 6 real runs and in 2 of 3 fake runs; the outliers (66 ms, 142 ms) are single steps in the shared background class. p99 is at most 44 ms everywhere.
- The total time to reconnect does not change (about 6.3 s, for a 1.5 s and a 4 s outage alike). Cause: the first resolve finds the stale info of the old outlet, and the inlet open then waits for its 5 s `open_timeout`. Follow-up: a shorter `open_timeout` in `reopen` would make reconnects faster. This task changes only who waits.

## Tests
- `tests/test_lsl_reconnect.py` (11): slow fake resolve (1 s): max step < 50 ms over 20+ steps while reconnecting; inline mode still blocks (control); producer restart mid-utterance gives the same decisions as inline (seq, final flag, action, shown text, frame range; 1 aborted utterance; resolve delay 0 and 0.2 s); the events inlet is served while the primary is away; a stop signal ends `run()` in < 0.5 s during a reconnect; `reconnect_timeout_s` still raises and cancels the worker; a late inlet after `close()` is closed; mapping validation; `RefCharLM` bound (values equal to the unbounded memo, size <= bound); real-LSL loopback restart (skips without pylsl; max step < 250 ms).
- Existing `tests/test_adapter_lsl.py`, `tests/test_brainflow_bridge.py`, `tests/test_fep_profiles.py`: pass unchanged.

## Reproduce
```
python -m fidetype.utils.isolation run --class background -- .venv\Scripts\python.exe experiments\2026-11-14-m6-14-nonblocking-reconnect\measure.py background
```
