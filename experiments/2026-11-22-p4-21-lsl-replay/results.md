---
title: P4-21 real B2T '25 NTS streams over LSL
type: experiment
updated: 2026-11-22
---

# P4-21: real B2T '25 NTS streams over LSL (gap 176)

Plan (committed before the run, `6039ad0`): [plan.md](plan.md). Code: [run.py](run.py). Numbers: [results/results.json](results/results.json). Log: `C:\Users\zhang\bci-data\derived\p4-21\run.log` (not in the repo). CPU only, about 30 s. No training.

Run (repo root): `.venv\Scripts\python.exe -I experiments/2026-11-22-p4-21-lsl-replay/run.py AB`

Set-up: pylsl 1.18.6, liblsl 1.18 (from the wheel), one Windows machine, localhost. Inputs: the 816 M4-06 test trials of B2T '25 (T15, CC0), 14 session days, frozen config `tcfg-f5ca0020b3b8fce2`. The model for the method is M6-11 (the same trials over WebSocket).

## Result: PASS (all checks of the plan)

### Part A: hypothesis route, `NTSOutlet` -> `open_source` -> `LSLTrustRunner` (FEP-0002 events stream)

| # | Check | Result |
|---|---|---|
| A1 | One final decision per trial | 816 / 816 (14 / 14 days, 0 extra) |
| A2 | LSL decision `==` in-process streaming replay (`Decision`, `PolicyInputs`) | 816 / 816 |
| A3 | LSL decision equals the batch harness (action, shown, p_top1, guard risk, set) | 816 / 816 (in-process vs batch: 816 / 816) |
| A4 | Faults | rejected 0, aborted 0, lost 0, bad markers 0 (late releases 0) |
| A5 | Received `nbest` `==` file `nbest` | 816 / 816 |

Descriptive: 2,434 events sent, wall 10.98 s (with the stream set-up of 14 days). Actions: COMMIT 82, OFFER 734.

### Part B: frames as `double64` (transport only, no trust layer)

| # | Check | Result |
|---|---|---|
| B1 | Frames received = sent | 161,503 / 161,503; per trial 816 / 816 |
| B2 | Rows bit-equal to the file (float64) | 161,503 / 161,503; 816 / 816 trials |
| B3 | Non-frame events in file order | 1,618 / 1,618 events, 14 / 14 days; 802 / 802 later headers equal (except `lsl_t`, `clock_domain`); 816 `end` events |
| B4 | Faults | gaps 0, clamped 0, dropped 0, lost 0 (late releases 0, bad markers 0) |

Descriptive: wall 18.09 s, about 8,926 frames/s (producer held at most 1,000 frames ahead of the receiver).

## Limits

- One machine, localhost. No second host, so the clock correction between hosts is not tested here.
- Part A sends the hypothesis route only (as M6-11). Part B checks the frames transport, not the frames-route trust decisions: those need the M4-06 decode function (fresh decodes), out of scope.
- Unpaced replay (no real-time pacing). The real-time latency is not measured here.
- The streams are a replay of recorded decoder output. No live device.
