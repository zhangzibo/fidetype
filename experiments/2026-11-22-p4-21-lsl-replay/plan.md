# P4-21: real B2T '25 NTS streams over LSL (plan, 2026-11-22)

Roadmap: [P4-21](../../wiki/questions/roadmap-standard.md#p4-21-nts-over-lsl-transport-on-real-decoder-output) (gap 176). CPU only. No training. This plan is written before any run. Model: M6-11 did the same for WebSocket ([b2t_replay_ws.py](../2026-11-13-m6-11-ws/b2t_replay_ws.py)).

## Problem

P4-15 (commit `ffc74f4`) found: the `lsl` transport (FEP-0002 binding, `NTSOutlet` -> `LSLEventSource` -> `LSLTrustRunner`) ran only on synthetic streams in a real pylsl loopback. Support level `synthetic-only`.

## Inputs (all local, outside the repository)

- The 816 hypothesis-route NTS files of M4-06: `bci-data/derived/m4-06-real-replay/streams/hyp-ours/trial-*.jsonl` (header, `hypothesis` with 10-best and FEP-0001 evidence, `end`).
- The 816 frames-route NTS files of M4-06: `.../streams/frames/trial-*.jsonl` (41 log-prob channels, 80 ms frames).
- The frozen config `experiments/2026-11-13-m4-06-real-replay/configs/trust-config-b2t25-ours-splitA.json` and `bci-data/derived/m4-06-real-replay/batch-ours.json`.
- pylsl 1.18.6 (liblsl 1.18 in the wheel), localhost only.

## Method

**Part A: hypothesis route through the trust layer.** One LSL stream per session day (stream id = `session.id`, as M6-11). Per day: an `NTSOutlet` (events stream only; the first trial header goes in the desc), the trial events in M4-06 order, no pacing. The receiver is `open_source(source_id=...)` and an `LSLTrustRunner` with `session_id` = the day, on one `StreamingTrustLayer` (route `hypothesis`, `max_attempts = 1`). Days go one after another. A tap records every event that the source releases.

**Part B: frames over LSL (transport only).** One LSL stream pair per session day: `NTSOutlet` with frames and events, `channel_format = "double64"`. Frame timestamps go on one continuous axis per day (one frame period between frames, also across trials), so the inlet sees no gap. The headers of the later trials and the `end` events go on the events stream. The producer waits when it is more than 1,000 frames ahead of the receiver (no buffer overflow). Part B does not run the trust layer: the frames route needs the M4-06 decode function (fresh decodes); that is out of scope.

## Pass criteria (all must pass)

| # | Check | Pass |
|---|---|---|
| A1 | Final decisions | Exactly one final decision per trial: 816 / 816 |
| A2 | Equal to in-process | LSL decision `==` in-process streaming replay (as M4-06 / M6-11): `Decision` and `PolicyInputs` equal, 816 / 816 |
| A3 | Equal to batch | LSL decision equals `batch-ours.json` (action, shown, p_top1, guard risk, prediction set), 816 / 816 |
| A4 | No faults | rejected events 0, aborted utterances 0, stream losses 0, bad markers 0 |
| A5 | Payload exact | received `hypothesis` `nbest` `==` file `nbest`, 816 / 816 |
| B1 | Frame count | received frames = sent frames, per trial and in total |
| B2 | Bit-equal rows | every received `log_probs` row `==` the file row as float64: 100 % |
| B3 | Event order | the non-frame events arrive in file order; the received `header` and `end` count equals the file count; each received header equals the file header except the receiver keys (`lsl_t`, `clock_domain`, `spec_version` default) |
| B4 | No faults | gaps 0, clamped 0, dropped 0, losses 0 |

Descriptive (no pass rule): wall time, events per second, the action counts.

## Privacy

The repository gets counts and check results only. No text, no per-trial values.
