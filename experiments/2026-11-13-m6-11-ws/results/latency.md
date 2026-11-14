# M6-11 WebSocket loopback: latency and equality

Synthetic simulator streams (the M6-01 LSL streams). Frozen config `tcfg-d3a8a4b94122b35e` (M4-03 synthetic). CTC greedy decoder. Localhost, one process. Windows-11-10.0.26200-SP0, Python 3.12.16, websockets 17.4, CPU only, isolation class `timing`.

| run | frames | speed | batch | equal to file replay (exact) | transport p50 / p95 / max ms | e2e final p50 / p95 / max ms | server final p50 ms | delivery to subscriber p50 / p95 ms |
|---|---|---|---|---|---|---|---|---|
| A_frames_rt_single | 1583 | 1.0 | 1 | 4/4 | 0.25 / 0.38 / 0.80 | 1.85 / 4.66 / 5.09 | 1.57 | 0.29 / 0.40 |
| B_frames_x4_single | 4378 | 4.0 | 1 | 12/12 | 0.24 / 0.34 / 0.55 | 1.30 / 1.61 / 1.69 | 0.97 | 0.24 / 0.47 |
| C_frames_x4_batch8 | 4378 | 4.0 | 8 | 12/12 | 0.22 / 0.32 / 0.59 | 1.48 / 1.65 / 1.67 | 1.18 | 0.25 / 0.60 |
| D_hypothesis_50ms | 0 | 50 ms pacing | 1 | 30/30 | 0.30 / 0.39 / 5.28 | 0.75 / 0.97 / 5.50 | 0.43 | 0.27 / 0.39 |

Hypothesis route (D): provisional e2e p50 0.68 ms (182 provisional decisions).

Every run: the /decisions subscriber got every decision in ws_seq order: A_frames_rt_single 4 (in order), B_frames_x4_single 12 (in order), C_frames_x4_batch8 12 (in order), D_hypothesis_50ms 212 (in order).
