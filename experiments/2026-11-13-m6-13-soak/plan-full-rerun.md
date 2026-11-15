---
title: "M6-15: full-length soak rerun on the fixed code: plan"
type: experiment
task: M6-15
updated: 2026-11-14
---

# M6-15: full-length soak rerun (plan, written before the run)

This file was committed **before** the run started. It does not change after the run.

## Why
The M6-13 main run (6.78 h) failed C2 (memory) and C9 (clock), and C1 because of an outside stop. The fixes (guard edit-distance cache, bridge clock-step recheck, M6-14 non-blocking reconnect, bounded `RefCharLM` memo) passed a 2.5 h check. The plan asked for 6-8 h. This run is the full-length check.

## What stays the same
- The harness (`soak.py`, `trust_proc.py`, `consumer_proc.py`, `analyze.py`), the set-up and the timeline of [plan.md](plan.md): 7 h planned (`--planned-s 25200`), 30-min bridge cycles (kill / clean in turn), one 3-s dropout per bridge life, 2-min windows, 30-min warm-up.
- The 10 pass criteria C1-C10 of [plan.md](plan.md), with the same thresholds. `analyze.py` computes them with the same code (checked: the post-fix `summary.json` is the same before and after the change below, except for the new `machine_load` block).

## What is new (no effect on the criteria)
| change | why |
|---|---|
| The whole process tree runs in the **timing** CPU class (`python -m fidetype.utils.isolation run --class timing --threads 1`): CPUs 8, 10, 12, 14, above-normal priority, timing lock held for the run | other agents run tests and a GPU training job at the same time (M0-22 rule for latency measurements) |
| Each supervisor heartbeat (1 per min) records the CPU load of the timing, background and idle-sibling CPUs, and the soak's own CPU share (`load` in `supervisor.jsonl`). `analyze.py` reports it as `machine_load` (with the launcher record `measurement_env.json`). | an honest record of the machine noise |
| `supervise` always writes `DONE` in the run folder at exit, with the reason (`finished`, `error: ...`) | later jobs wait on it (M4-02 waited on a missing `DONE`) |

The M6-13 run used no CPU pinning and default thread counts. So latency numbers of the two runs are not fully comparable. The thresholds are wide (push p95 < 5 ms; the M6-13 worst window was 1.76 ms).

## Where
Run folder (local): `C:\Users\zhang\bci-data\soak\m6-15\`. Results (committed): `results-full/`. Started detached by `C:\Users\zhang\bci-data\soak\m6-15\launch.ps1`. Edit at 12:10, before any result (launch method only): the first two starts (Win32_Process.Create; then a scheduled task that was disabled after its start) died within seconds. A third start (12:09, scheduled task) died after 3 min (all processes and the separate keep-awake ended with 0xC000013A, console close / Ctrl-C), after one 2-min window. Nobody looked at its numbers. Edit at 16:35, before any result: the run that counts was started at 16:34 on HEAD 7c6a577 (adds the M6-16 fast LSL reconnect) by [launch_detached.py](launch_detached.py): no console, new process group, out of the caller's job object. Criteria unchanged.
