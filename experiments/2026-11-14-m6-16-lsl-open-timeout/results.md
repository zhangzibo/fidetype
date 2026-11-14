---
title: "M6-16: LSL open_timeout and the fast reconnect: results"
type: experiment
task: M6-16
updated: 2026-11-14
---

# M6-16: LSL `open_timeout` and the fast reconnect (results)

M6-14 made the LSL reconnect non-blocking, but a reconnect after a producer restart still took about 6.3 s. M6-14 blamed the 5 s `open_timeout` of the inlet open (stale stream info). The follow-up was: a shorter `open_timeout`.

## Where the time limits are
| Setting | Where | Before | After |
|---|---|---|---|
| Inlet open (`info()` + `open_stream()`) | `PylslInlet(open_timeout=...)` | 5.0 s, not configurable | `LSLMapping.open_timeout_s`, default **1.0 s**; `fidetype lsl run --open-timeout`; collector `open_timeout_s` |
| Resolve per reconnect try | `reopen` in `open_source` | `resolve(timeout = reconnect_interval_s = 0.5 s)` | `LSLMapping.reconnect_resolver`: `continuous` (default, new) or `oneshot` (old) |
| Start | `open_source` | resolve + open (5 s) once | resolve + open (1 s); a timed-out open is retried until `timeout` |

## Measurement
Script: [measure.py](measure.py). Numbers: `results/open_timeout-run1.json` (run 1), `results/open_timeout.json` (run 2), stdout in `results/run*-stdout.txt`. One Windows PC, pylsl 1.18.6, localhost, CPU class **background** (4 threads; a 7 h soak test and a GPU training run were active). Stream names `test-collector-m616-*`.

A. Healthy open of a live outlet (30 trials): resolve p50 1.2 ms (max 4.2 ms); **inlet open p50 11.5 ms, max 11.9 ms**; first `time_correction()` p50 641 ms (liblsl's first estimate; the reconnect worker pre-warms it, M6-14).

B. Stale info (the outlet is gone after the resolve): the open waits for the full limit, then fails: 0.50 s (limit 0.5), 1.00 s (1.0), 2.00 s (2.0); with 5.0 liblsl reports the loss after 2.04-2.06 s (connection refused).

C. Producer restart (25 Hz NTS outlet, gone for 1.5 s, back with the same `source_id`), thread mode, time from the stop to the reconnect, 3 repeats per cell:

| run | resolver | `open_timeout_s` | reconnect after stop (s) | max loop step (ms) |
|---|---|---|---|---|
| 1 | oneshot (M6-14 path) | 5.0 | 6.21, 6.21, 2.26 | 21.2-21.5 |
| 1 | oneshot | 2.0 | 6.76, 6.21, 6.76 | 21.5 |
| 1 | oneshot | 1.0 | 2.26, 6.21, 6.21 | 21.1-21.5 |
| 1 | oneshot | 0.5 | 6.21, 6.21, 2.26 | 21.3-21.4 |
| 2 | oneshot | 5.0 | 2.31, 6.21, 6.21 | 21.0-21.2 |
| 2 | oneshot | 1.0 | 6.76, 6.21, 6.21 | 21.1 |
| 2 | **continuous** (M6-16) | 5.0 | **2.42, 2.42, 2.42** | 21.0 |
| 2 | **continuous** | 1.0 | **2.42, 2.42, 2.42** | 21.0-21.3 |

A trace of each `reopen` step (oneshot, `open_timeout_s` 1.0) shows where the time goes: `resolve(timeout = 0.5)`, started about 0.1 s after the loss, **returned after 5.50 s with nothing found**, although the new outlet was up 1.5 s after the stop. The next resolve found it in 1-2 ms; the open took 12 ms; the pre-warm `time_correction()` 641 ms. In about 1 of 3 restarts the first resolve returns in time (2.26-2.31 s). A probe of `resolve_bypred` alone gave the same pattern (5.5 s blocks; once the stale uid of the old outlet). A `pylsl.ContinuousResolver` created at the loss saw the new uid 0.27 s after the restart, every time, and never blocked.

## Findings
- **The `open_timeout` is not the cause** of the 6.2 s reconnect (contradicts the M6-14 note). The cause is the one-shot resolve on this Windows PC: a resolve that starts just after a loss can block about 5.5 s beyond its 0.5 s limit. A shorter `open_timeout` alone changes nothing in C.
- **Fix:** `reopen` asks a `ContinuousResolver` every 20 ms and prefers a stream with a new uid (a restarted producer) over the stale info of the lost one; the old uid is accepted after 2 s (the same outlet is still there, for example after a network break). Reconnect: **2.42 s for a 1.5 s outage** (1.5 s outage + about 0.27 s discovery + 0.64 s first clock estimate), in 6 of 6 runs; before 6.2-6.8 s in 10 of 12 runs.
- **`open_timeout_s` default 1.0 s** (was 5.0). Reasons: a healthy open takes about 12 ms on localhost, so 1 s is about 85 times that and leaves room for a LAN or Wi-Fi round trip (M6-10 will measure it); a stale or hung outlet (B) now costs 1 s per try instead of up to 5 s; the start retries a timed-out open until the resolve `timeout`, so a short limit cannot fail a slow but live start. It stays configurable.
- **No M6-14 regression:** max loop step 21.0-21.5 ms in every run (poll 20 ms); the loss still aborts the utterance (1 per run); the reconnected status and the new header come in the same order. `tests/test_lsl_reconnect.py` passes unchanged.

## Tests
`tests/test_lsl_open_timeout.py`: default and validation; `_open_first` retries a timed-out open and gives up with a clear error; the reopener prefers a new uid over stale info, takes the old uid only after `SAME_UID_AFTER_S`, bounds each try by `reconnect_interval_s`, refuses two new matches; `oneshot` still uses `resolve()`; real LSL (skips without pylsl): a 1.5 s outage reconnects in < 4.5 s with max loop step < 250 ms.

## Reproduce
```
.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe experiments\2026-11-14-m6-16-lsl-open-timeout\measure.py
```
