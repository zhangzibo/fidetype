---
title: "M6-13: soak test of the live path: plan and pass criteria"
type: experiment
task: M6-13
updated: 2026-11-13
---

# M6-13: soak test of the live path (plan, written before the run)

This file was written and committed **before** the long run started. The pass criteria below do not change after the run. A 7-min pilot (2 bridge cycles of 160 s) ran first, only to debug the harness. Its numbers are not results.

## Goal
Run the full live chain for hours and check that it stays correct and stable:

```
BrainFlow Synthetic board -> bridge -> LSL (EEG + Markers) -> toy signal decoder -> StreamingTrustLayer
    (incremental decoder, GC rule, bounded caches) -> trust_decision events on LSL -> consumer (validator)
```

Earlier live runs (M6-01, M6-08) lasted 70 s per mode. The M4-10 long session (2,000 utterances) ran in one process with no LSL.

## Set-up

| part | what | process |
|---|---|---|
| source | `fidetype lsl brainflow-bridge --board synthetic` (BrainFlow board -1, 16 EEG ch, 250 Hz, fake data), `segment_end` marker every 4 s | bridge (restarted, see below) |
| signal decoder | `fidetype.decoders.toy_signal`, 25 frames/s, 28-token char vocab. Mode `features` and `flat` alternate at each bridge restart. Both carry **no text information**. | trust |
| trust layer | `StreamingTrustLayer` with the frozen demo config (`src/fidetype/demo/trust-config-demo.json`), the demo decoder (segment beam 8 + char 5-gram LM) as the **incremental** decoder (M4-08, `IncrementalReferenceDecoder`), `max_attempts 1` | trust |
| GC rule (M4-09) | `gc.collect(); gc.freeze()` after setup, automatic GC off, one timed `gc.collect()` after each final decision or aborted utterance (and at most 60 s apart when idle) | trust |
| bounded caches (M4-10) | a **shadow** incremental decoder on the same frames: CTC prefix beam 16 + `CharNgramLM` 6-gram with an LRU memo bound of 20,000 entries (small on purpose, so that it fills and evicts), prewarm every 5 frames with a 1 ms budget. It makes no decision. Every 20th final utterance, its incremental result is compared with the batch decode of the same frames. | trust |
| output | `DecisionOutlet` (`soak.decisions`, FEP-0002 section 8: JSON strings on a marker stream) | trust |
| consumer | reads the outlet; validates **every** event with the conformance validator (`fep0001.td_format_errors`) and the order rules 5-7 online; counts lost, duplicate and reordered events by `seq`; measures transport latency and the clock offset | consumer |
| supervisor | starts the processes (one Windows job object each), restarts the bridge, writes `supervisor.jsonl`, keeps the PC awake | supervisor |

All on one Windows 11 PC, CPU only, localhost. A GPU training job of another task runs at the same time; it uses the GPU and some CPU. The soak uses about 10 % of one core in total.

## Timeline
- Planned active time: **7 h** (25,200 s). `--planned-s 25200`.
- Bridge cycle: 30 min. Even cycles end with a **hard kill** (TerminateJobObject). Odd cycles end with a **clean stop** (`--duration`). 5 s later a new bridge starts with the same `source_id`. About 14 cycles, 13 restarts.
- Each bridge life has one 3-s **dropout** (`--pause 600:3`) at 10 min.
- Metrics windows: 2 min. Each window writes one JSON line per process (`results/metrics-trust.jsonl`, `results/metrics-consumer.jsonl`), flushed and fsynced. A crash loses at most one window.
- Warm-up: the first 30 min. The RSS slope uses the windows after it.

## Measurements (per window)
RSS, private bytes, handle count, CPU s (each process measures itself); push latency p50/p95/max (`layer.push` of one frame, with the incremental decode); end-of-utterance latency (`layer.push` of the `segment_end` that gives the final decision); e2e latency (decision emission minus the LSL time of the `segment_end` marker); idle `gc.collect()` time; shadow push and finalize time; LSL transport latency; source counts (samples, frames, gaps, clamped, out-of-order drops, late releases, losses, reconnects); clock offset (`time_correction`) and its spread; cache sizes (`RefCharLM` memo of the demo decoder, shadow `CharNgramLM` LRU); decision counts per toy mode and action; exceptions. Consumer: received, invalid, lost, duplicate/reordered, transport latency, clock offset.

## Pass criteria (fixed before the run)

| id | criterion | threshold |
|---|---|---|
| C1 | no crash | no process died or restarted; trust and consumer exit code 0 at the end; 0 exceptions caught in the trust loop |
| C2 | memory | RSS slope after the 30-min warm-up **<= 2 MB/h** (trust and consumer; linear fit over the 2-min windows) |
| C3 | push latency | push p95 **< 5 ms in every** 2-min window |
| C4 | end of utterance | end-of-utterance p95 **< 50 ms in every** window; whole-run e2e p95 **< 100 ms** |
| C5 | event validity | **0 invalid events** (online check of every event) and the full conformance check (FEP-0001 profile) of the received decision log passes |
| C6 | no lost events | consumer received = trust emitted; **0** seq gaps; 0 duplicates or reorders |
| C7 | no wrong commits | **0 COMMIT** in both toy modes (the input has no text information, so each COMMIT is wrong) |
| C8 | LSL path | gaps found = dropouts made (no false gap, none missed); 0 out-of-order drops; reconnects = 2 x bridge restarts (signal + markers) |
| C9 | clock | `time_correction` spread < 1 ms; slope of the per-window transport p50 after warm-up < 1 ms/h |
| C10 | caches | shadow LRU entries <= bound in every window; shadow incremental = batch on 100 % of the checked utterances |

Not a criterion, reported only: the `RefCharLM` memo of the demo decoder has no bound. An offline check (300 utterances of each toy mode) showed it saturating near 20,000 entries. The soak reports its size over time. If it grows linearly, that is a finding.

## If something fails
Record the failure in `results.md`. If it is a real bug, fix it with a test, record the fix, and say which numbers came before the fix. Do not change the thresholds.

## Commands
Run directory (local, not committed): `C:\Users\zhang\bci-data\soak\m6-13\` (logs, `state.json`, `events.jsonl`). Committed: `results/*.jsonl`, `results/summary.json`, `results/tables.md`.

```
.venv\Scripts\python.exe experiments\2026-11-13-m6-13-soak\soak.py supervise --planned-s 25200   # detached, see HANDOFF.md
.venv\Scripts\python.exe experiments\2026-11-13-m6-13-soak\soak.py status
.venv\Scripts\python.exe experiments\2026-11-13-m6-13-soak\soak.py stop
.venv\Scripts\python.exe experiments\2026-11-13-m6-13-soak\soak.py supervise --resume            # after a crash or stop
.venv\Scripts\python.exe experiments\2026-11-13-m6-13-soak\soak.py analyze
```
