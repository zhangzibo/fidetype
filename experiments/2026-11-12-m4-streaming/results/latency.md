# M4-03 streaming trust layer: latency and equivalence

Synthetic simulator streams (median preset), 100 utterances, mean 453 frames (max 555), V = 28. Config `tcfg-d3a8a4b94122b35e`. Machine: Windows, Python 3.12.16, CPU only.

| path | measure | p50 ms | p95 ms | p99 ms | max ms | equal to batch |
|---|---|---|---|---|---|---|
| frames, beam decoder | push(frame) | 0.008 | 0.014 | 0.016 | 0.174 |  |
| frames, beam decoder | end -> final decision | 8.052 | 11.099 | 13.953 | 14.327 | 100/100 |
| frames, greedy decoder | push(frame) | 0.008 | 0.013 | 0.014 | 0.199 |  |
| frames, greedy decoder | end -> final decision | 0.719 | 1.084 | 1.385 | 2.157 | 100/100 |
| hypothesis | push(hypothesis) | 0.190 | 0.315 | 0.458 | 0.522 | 100/100 |

Actions (beam): {'OFFER': 100}.

Peak buffered frame bytes per session: 124320 (float64 rows of the current utterance only; freed at the end of the utterance).

64 interleaved sessions (greedy): 28879 events in 1.02 s (28221 events/s); tracemalloc peak 8.7 MB.
