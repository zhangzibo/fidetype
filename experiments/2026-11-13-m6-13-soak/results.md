---
title: "M6-13: soak test of the live path: results"
type: experiment
task: M6-13
updated: 2026-11-13
---

# M6-13: soak test of the live path (results)

Plan and pass criteria: [plan.md](plan.md) (commit 5b363a5, before the run). Numbers: `results/` (main run) and `results-postfix/` (run after the fixes): `metrics-*.jsonl` (one line per 2-min window), `supervisor.jsonl`, `summary.json`, `tables.md`. Offline memory check: [results/offline-memory.md](results/offline-memory.md). Logs and the received decision logs stay local (`C:\Users\zhang\bci-data\soak\m6-13*\`).

Chain: BrainFlow Synthetic board → bridge → LSL → toy signal decoder (`features` / `flat`, no text information) → `StreamingTrustLayer` (incremental demo decoder, M4-09 GC rule, shadow CTC beam + bounded `CharNgramLM`) → `trust_decision` events on LSL → consumer (validates each event). One PC, CPU only. A GPU training job of another task ran at the same time.

## Summary

| run | code | active time | final decisions | result |
|---|---|---|---|---|
| main | plan commit 5b363a5 | **6.78 h** of 7 h planned (stopped from outside at 20:47) | 6,067 | 7 of 10 criteria pass. **C2 memory FAIL** (bug 1), **C9 clock FAIL** (bug 2), **C1 FAIL**: an outside kill, no crash |
| post-fix | bug 1 fixed in the trust process; bug 2 fixed in the bridges from cycle 1 on | 2.50 h (9,000 s, as planned) | 2,242 | **10 of 10 criteria pass** |

The post-fix run is shorter than the plan asked for (2.5 h, not 6-8 h). It checks the fixes. It does not replace a full-length run.

## Criteria

| id | criterion | main run (6.78 h) | post-fix run (2.5 h) |
|---|---|---|---|
| C1 | no crash, exit 0, 0 exceptions | **FAIL**: all four soak processes stopped at 20:47:38 from outside (no traceback, no final window, bridge exit code 143). 0 exceptions and 0 restarts before that. | PASS (exit 0 / 0, 0 exceptions) |
| C2 | RSS slope after warm-up <= 2 MB/h | **FAIL**: trust private bytes +16.9 MB/h (RSS +7.9 MB/h); consumer -4.3 MB/h | PASS: trust private +0.80 MB/h (RSS -6.7 MB/h); consumer -3.4 MB/h |
| C3 | push p95 < 5 ms in every window | PASS: worst window p95 1.76 ms (203 windows); max 39.5 ms | PASS: worst 0.75 ms (75 windows); whole run p50/p95/max 0.48/0.68/9.1 ms |
| C4 | EOU p95 < 50 ms per window; e2e p95 < 100 ms | PASS: worst EOU p95 9.97 ms; e2e p50/p95/p99 31/55/337 ms | PASS: worst EOU p95 3.96 ms; e2e p50/p95/p99/max 34/56/78/384 ms |
| C5 | 0 invalid events | PASS: 0 online; FEP-0001 profile check of 6,080 received events: PARSE, KIND, TD-FORMAT, TD-FINAL pass | PASS: 0; 2,242 events, all checks pass |
| C6 | 0 lost events | PASS: 0 seq holes in 6,080 received events (6,067 emitted at the last trust window); 0 duplicates | PASS: emitted 2,242 = received 2,242 |
| C7 | 0 COMMIT on toy input | PASS: 0 / 6,067 (features 3,150 ABSTAIN, flat 2,917 ABSTAIN) | PASS: 0 / 2,242 (1,344 + 898 ABSTAIN) |
| C8 | gaps = dropouts; 0 out-of-order drops; reconnects = 2 x restarts | PASS: 14 gaps / 14 dropouts; 0 drops; 26 reconnects / 13 restarts | PASS: 5 / 5; 0; 8 / 4 |
| C9 | offset spread < 1 ms; transport p50 slope < 1 ms/h | **FAIL**: spread 0.073 ms, but slope -11.6 ms/h (3 windows with transport p50 1,373 ms, bug 2). Without those 3 windows: +0.02 ms/h | PASS: spread 0.056 ms; slope +0.0002 ms/h |
| C10 | LRU <= bound; shadow incremental = batch | PASS: 20,000 / 20,000 entries from 0.4 h on; 303/303 equal | PASS: 112/112 equal |

## Over time (main run, one window every 30 min)

| t (h) | trust RSS MB | private MB | handles | push p95 ms | EOU p95 ms | idle GC p50 ms | transport p50 ms | RefCharLM entries |
|---|---|---|---|---|---|---|---|---|
| 0.03 | 65.4 | 527.0 | 359 | 0.56 | 2.23 | 0.55 | 11.2 | 14,660 |
| 1.00 | 95.5 | 557.6 | 347 | 0.61 | 2.95 | 1.54 | **1,373** | 17,597 |
| 2.00 | 114.0 | 576.3 | 355 | 0.57 | 3.02 | 2.26 | 11.1 | 18,079 |
| 3.00 | 121.2 | 592.7 | 355 | 0.58 | 3.00 | 3.05 | 11.2 | 18,686 |
| 4.00 | 121.6 | 609.7 | 355 | 0.57 | 2.07 | 2.79 | 11.2 | 19,153 |
| 5.00 | 138.0 | 625.6 | 355 | 0.56 | 2.08 | 3.34 | 11.2 | 19,695 |
| 6.50 | 125.6 | 649.7 | 355 | 0.67 | 3.60 | 7.92 | 11.3 | 20,050 |

Post-fix run: private bytes 527.8 → 540.9 (0.5 h) → 543.7 MB (2.5 h); idle GC p50 0.6-0.9 ms the whole run; handles 347-359; transport p50 11.2-11.3 ms. Full tables: `results*/tables.md`.

## Bug 1: the guard filled a 200,000-entry edit-distance memo (fixed)

- **Symptom.** Trust private bytes grew about 17 MB/h with no end in sight. The idle `gc.collect()` grew from 0.8 to 8 ms (p50), because the memo objects are not frozen.
- **Cause** (found with `tracemalloc` in [offline_memory.py](offline_memory.py), no LSL). `guard.nbest_consistency` and `guard.semantic_entropy` call `fidetype.trust._align.cached_edit_distance`, an `lru_cache(maxsize=200_000)` shared with the offline evaluation code (eWPM, simulated user). Live, each final decision adds about 30 new word-tuple pairs (hit rate about 8 %), about 0.75 KB each. The bound holds only after about 6,700 utterances (about 7.5 h at 15 decisions/min) and about 150 MB. M4-10 bounded the decoder memos; this memo was not on its list.
- **Fix.** `_align.edit_distance` (no cache); `cached_edit_distance` keeps 200,000 entries for offline evaluation; the guard uses its own `guard_edit_distance` with `GUARD_EDIT_CACHE_SIZE = 4096` (about 3 MB). The distance values do not change, so no guard score changes.
- **Check.** Offline, 4,000 utterances: private bytes +85.8 MB before, +6.4 MB after (flat from about 1,200 utterances on). Live post-fix run: +0.80 MB/h. Test: `tests/test_guard_cache_bound.py` (3).

## Bug 2: a wall-clock step moved all later bridge stamps (fixed)

- **Symptom.** In bridge cycle 1 of the main run, from 0.92 h until that bridge stopped at 1.0 h, the LSL transport latency was 1,373 ms (normal: 11 ms), e2e was about 350 ms, and the merge counted 1,875 late releases. The bridge stats show push lag p95 1,364 ms. All other bridges had p95 3.3-3.4 ms.
- **Cause.** Windows set the system clock back by 1,361 ms at 14:55:52 (System log, Kernel-General event 1, "Time Delta: -1361 ms"; the same happened at 05:49 with -1,402 ms). The bridge maps the BrainFlow Unix stamps to the LSL clock with **one offset taken at start**. After the step, every stamp was 1.36 s late until the bridge restarted. A forward step larger than `jump_s` (0.25 s) would have made a false gap and stamps in the future (shown with the old code in the new test: a 1.40 s stamp step, push lag -1,400 ms).
- **Fix** (`brainflow_bridge.py`). The offset LSL clock − wall clock is measured at each read. A change > `clock_step_s` (0.05 s) counts as a step (`stats.clock_steps`); the bridge takes the new offset and stamps that one read from the model (previous stamp + 1/srate), because the read can hold samples from both sides of the step. Smaller changes (slewing) are followed at each read.
- **Check.** Tests in `tests/test_brainflow_bridge.py` (3 new): steps of -1.361 s and +1.4 s keep the push lag < 50 ms and every stamp step < 2.5 periods, with `clock_steps == 1` and `jumps == 0`; a 500 ppm slew is followed with no step. The post-fix bridges (cycles 1-4) ran the new code: `clock_steps` 0, push lag p95 3.4 ms. No wall-clock step happened during the post-fix run, so the fix is tested by unit tests only, not live.

## Outside stop of the main run (not a crash, cause unknown)
At 20:47:38 the supervisor, the trust process, the consumer and the bridge all ended within one second, with no traceback and no final metrics window. The bridge exit code was 143. The run had reached 24,420 s of active time (97 % of 7 h). Other agents were active on the PC at that time (a GPU training queue restarted at 20:43, a pytest run started at 20:46:52). We found no code in the repo that kills such processes. We did not resume the run: it would have added only 13 min on the old code. Because the main run ended this way, C1 fails for it. The windows up to 20:46:46 are complete and fsynced (the checkpoint design worked).

## Other observations
- **RefCharLM memo** (demo decoder, no bound): 14,660 → 20,050 entries in 6.5 h. The growth slows down (+540 in the last 1.5 h); it adds about 1 MB. No action now. A bound would be a small safety rail.
- **Push max** 39.5 ms (main run, one window); post-fix max 9.1 ms. Push p95 never went over 1.8 ms.
- **Reconnect blocks the loop** for up to 6.1 s (step max): the reader resolves the new stream inside `poll()`. No data is lost (LSL buffers it), but the loop is blind while it waits. Not a criterion; a follow-up could move the resolve to a thread.
- **Shadow decoder** (prewarm budget 1 ms): push p95 1.17 ms, finalize p95 up to 43.7 ms; the 20,000-entry LRU filled in 0.4 h and stayed at the bound.
- **CPU**: trust process 1,359 s in 6.77 h = 5.6 % of one core (with the shadow decoder); consumer 0.2 %; bridge about 2 %.
- Private bytes start at about 527 MB because liblsl reserves buffers; RSS (working set) starts at 65 MB.

## Reproduce
```
.venv\Scripts\python.exe experiments\2026-11-13-m6-13-soak\soak.py supervise --planned-s 25200
.venv\Scripts\python.exe experiments\2026-11-13-m6-13-soak\soak.py analyze
.venv\Scripts\python.exe experiments\2026-11-13-m6-13-soak\offline_memory.py 4400
```
Post-fix run: the same, with `SOAK_RUN_DIR` and `SOAK_RESULTS_DIR` set to other folders and `--planned-s 9000`.
