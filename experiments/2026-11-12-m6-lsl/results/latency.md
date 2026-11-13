# M6-01 LSL loopback: latency and equality

Synthetic simulator streams, 12 utterances, 4378 frames (40 ms), one file with `segment_end` between utterances. Frozen config `tcfg-d3a8a4b94122b35e` (M4-03 synthetic). CTC greedy decoder. Localhost. Windows, Python 3.12.16, pylsl 1.18.6, liblsl 118, CPU only.

| run | frames | speed | merge window | equal to file replay (exact / action+shown) | transport p50 / p95 / max ms | e2e final p50 / p95 / max ms |
|---|---|---|---|---|---|---|
| A_float32_rt_merge50 | float32 | 1.0 | 50 ms | 12/12 / 12/12 | 3.49 / 6.60 / 496.98 | 60.6 / 61.6 / 61.6 |
| B_double64_x4_merge50 | double64 | 4.0 | 50 ms | 12/12 / 12/12 | 3.59 / 6.71 / 496.32 | 56.3 / 60.4 / 60.6 |
| C_float32_x4_merge10 | float32 | 4.0 | 10 ms | 12/12 / 12/12 | 3.59 / 7.05 / 496.38 | 17.2 / 19.1 / 19.3 |

Hypothesis route (D): 213 marker events, one every 50 ms; equal 30/30; e2e final p50 3.04 ms, p95 7.22 ms, max 45.73 ms; provisional p50 3.47 ms (182 provisional).

Two processes, the CLIs (E): {"exit_codes": {"replay-to-lsl": 0, "run": 0, "streaming replay": 0}, "decisions": 12, "reference_decisions": 12, "equal_fields": ["action", "shown", "p_top1", "set_size", "guard_risk", "is_final", "utterance"], "equal": "12/12", "stop": "end", "e2e_latency_ms": {"n": 12, "p50": 91.94775000287336, "p95": 99.06628249700589, "max": 101.26840000157245}, "note": "max_attempts 1 in run; the streaming replay CLI uses the default (2), so the attempt fields are not compared"}

Max |p_top1 difference| with float32 frames (A): 0.0.
