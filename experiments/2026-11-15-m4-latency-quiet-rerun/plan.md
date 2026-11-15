---
title: M4-01/02 latency rerun on a quiet machine - plan addendum
type: experiment-plan
task: M4-02R
updated: 2026-11-15
---

# Addendum to the M4-01/02 plan: latency rerun on a quiet machine (written before the run)

Dated: 2026-11-14 (written at about 23:55, before the run). Original experiment: [M4-01/02 results](../2026-11-13-m4-01-02-lookahead/results.md), [config.json](../2026-11-13-m4-01-02-lookahead/config.json).

## Why
The M4-01/02 latency stage ran while other agents ran tests. The foreign load on the timing cores was 5.77 %. The isolation rule limit is 5 %. So that result is not a clean benchmark. This rerun measures again when the machine is quiet.

## Start condition
- The run starts only when both markers exist: `C:\Users\zhang\bci-data\soak\m6-15\DONE` (M6-15 soak, at least 10 min old, so that the soak analysis is past its first minutes) and `C:\Users\zhang\bci-data\runs\m4-12-queue.PHASE1` (the M4-12 queue holds all GPU and CPU work after PHASE1 until this run writes `C:\Users\zhang\bci-data\runs\latency-rerun.DONE`, or until 08:30).
- If both markers do not exist by 07:40, nothing runs. The run must end by 08:30. A step that cannot end before 08:30 is skipped, and a hard stop at 08:30 ends the process. The result is then marked incomplete. `latency-rerun.DONE` is always written.

## Protocol and criteria: the same as M4-01/02
| item | value |
|---|---|
| code | `experiments/2026-11-13-m4-01-02-lookahead/run.py`, unchanged. Stage `stage_latency(force=True)` (the M6-13 DONE file is still missing, as before). Then `stage_emission()`. Output goes to `results/` of this folder (`M4_OUT`). |
| trials | the same 200 random `val_eval` trials (seed 20261113) |
| L grid | 0, 2, 5, 10, 15, 25 bins = 0, 40, 100, 200, 300, 500 ms |
| pipeline | raw 20 ms bins → NumPy `StreamingLookaheadGRU` → NTS frames → `StreamingTrustLayer` (frozen config `tcfg-f5ca0020b3b8fce2`, frames route, incremental CTC beam + word decoder) |
| measures | decoder push per bin, trust push per frame, end of utterance (flush + final decision) p50 / p95 / max; NumPy vs torch log-prob difference; same action as the accuracy stage |
| CPU class | **timing**: `isolated("timing")`, cores 8, 10, 12, 14 (one logical CPU per physical core, SMT siblings 9, 11, 13, 15 idle), timing lock held, above-normal priority. Same as M4-01/02. |
| clean criterion | foreign load on the timing cores **below 5 %** (`fidetype.utils.isolation`). If it is 5 % or more, the result is reported as not clean. |
| trust criterion | the decisions must equal the accuracy-stage decisions (200/200), and the number of commits is counted (M4-01/02: 0). |
| emission | `stage_emission()` again on the stored logits. This is not a timing measurement (it uses frame stamps, not wall time), so it must give the same numbers as before. It checks that the inputs did not change. |

## Checkpoints
- **Primary (like-for-like):** the original M4-01/02 checkpoints, as NumPy exports in `C:\Users\zhang\bci-data\derived\m4-01-02-lookahead\`: `params-m4-01-la-shared.npz` (timed at every L), and the logits of `m4-01-la-shared`, `m4-01-la-fixed0`, `m4-01-la-fixed25` (emission). The SHA-256 of each file is recorded in `results/inputs.json`.
- **Secondary (separate condition, if they exist):** the M4-12 retrained checkpoints `params-m4-12-fixed0.npz` (dedicated L = 0), `params-m4-12-fixed25.npz` (dedicated L = 500 ms), and `params-m4-12-shared.npz` (shared, timed at every L). Same timing loop and class (one isolated block per model and L). The dedicated models run at their own L only. Commits are counted from the streaming decisions directly. Emission: ready time of dedicated L 500 ms vs dedicated L 0 with the same matching rule. These numbers are reported in a separate table and are not mixed with the primary comparison.

## Known input risk
The M4-12 accuracy stage writes `trust-<which>-L<bins>.json` with the same names as M4-01/02 in the shared derived folder. `trust-dedicated_0-L0.json` was already overwritten by M4-12 (2026-11-14 16:15). The primary latency check reads only `trust-shared-L*.json` (M4-01/02 files, 2026-11-14 10:51-11:04). Their modification times are checked before the run and recorded.
