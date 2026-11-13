# M4-06 tables: real-data frozen config through the streaming trust layer

B2T '25 T15, fixed split A, Paper 1 frozen recipe (guard + LTT max, alpha 0.05, delta 0.1). Test = 816 trials.

## Frozen configurations

| decoder | config_id | frame T | sentence T | conformal q | grid commit_p | LTT threshold (n, feasible) | final commit_p | commit_max_risk | paper λ (LTT max) |
|---|---|---|---|---|---|---|---|---|---|
| ours | `tcfg-f5ca0020b3b8fce2` | 3.8151 | 4.4440 | 0.9108 | 0.3 | 0.0 (401, True) | 0.3 | 0.1 | 0.3 |
| published | `tcfg-ea22af7ec91eea3f` | 3.8151 | 1.6171 | 0.4303 | 0.7 | 0.76 (401, True) | 0.76 | 0.5 | 0.76 |

## Equivalence: streaming final decision vs batch harness (per test trial)

Fields compared exactly (==): action, shown texts, p_top1, guard risk, prediction set.

| decoder / route | input | equal / n | mismatches |
|---|---|---|---|
| ours/frames | full-precision NTS | 816 / 816 | 0 |
| ours/hypothesis | full-precision NTS | 816 / 816 | 0 |
| published/frames | full-precision NTS | 816 / 816 | 0 |
| published/hypothesis | full-precision NTS | 816 / 816 | 0 |
| ours/frames (fresh decode) | full-precision NTS | 816 / 816 | 0 |
| ours/frames | benchmark v0.1 NTS (6 decimals) | 1 / 816 | 815 (action differs in 0; max abs Δp_top1 2.03e-08); other top text in 0 |
| published/frames | benchmark v0.1 NTS (6 decimals) | 5 / 816 | 811 (action differs in 0; max abs Δp_top1 3.38e-08); other top text in 0 |

## Test metrics from the streaming decisions vs Paper 1 (Tab. 3, guaranteed rule, split A)

| decoder / route | wrong-commit (n) | commit rate (n) | eWPM | silent error | paper wrong-commit (n) | paper commit (n) | paper eWPM |
|---|---|---|---|---|---|---|---|
| ours/frames | 0.0245 (20) | 0.100 (82) | 11.48 | 0.0012 | 0.0245 (20) | 0.100 (82) | 11.48 |
| ours/hypothesis | 0.0245 (20) | 0.100 (82) | 11.48 | 0.0012 | 0.0245 (20) | 0.100 (82) | 11.48 |
| published/frames | 0.0294 (24) | 0.403 (329) | 18.65 | 0.0012 | 0.0294 (24) | 0.403 (329) | 18.65 |
| published/hypothesis | 0.0294 (24) | 0.403 (329) | 18.65 | 0.0012 | 0.0294 (24) | 0.403 (329) | 18.65 |
| ours/frames, 6-decimal files | 0.0245 (20) | 0.100 (82) | 11.48 | 0.0012 | | | |
| published/frames, 6-decimal files | 0.0294 (24) | 0.403 (329) | 18.65 | 0.0012 | | | |

## Latency per decision (one CPU process, perf_counter)

Decision = push of the event that closes the utterance -> final decision (frames route: includes building the stream, frame temperature, decode, trust core; hypothesis route: trust core only).

| decoder / route | decode | decision p50 ms | p95 ms | max ms | push(frame) p50 / p95 ms | push(hypothesis, final) p50 ms |
|---|---|---|---|---|---|---|
| ours/frames | disk cache (paper decodes) | 0.973 | 1.643 | 3.016 | 0.0140 / 0.0166 | — |
| ours/hypothesis | disk cache (paper decodes) | 0.437 | 0.628 | 1.001 | — | 0.437 |
| published/frames | disk cache (paper decodes) | 0.702 | 1.068 | 2.295 | 0.0140 / 0.0164 | — |
| published/hypothesis | disk cache (paper decodes) | 0.441 | 0.611 | 0.963 | — | 0.441 |
| ours/frames | fresh decode | 173.091 | 992.402 | 3229.184 | 0.0142 / 0.0160 | — |
| ours/frames, 6-decimal files | fresh decode (cache miss) | 133.093 | 734.155 | 2325.964 | 0.0092 / 0.0181 | — |
| published/frames, 6-decimal files | fresh decode of ours + lookup | 0.626 | 1.025 | 1.847 | 0.0092 / 0.0157 | — |

## Memory

| decoder / route | max buffer per session | max frames buffered | traced peak (100 trials, cached decode) | retained after 100 trials |
|---|---|---|---|---|
| ours/frames | 180.0 KiB | 562 | 1064.2 KiB | 14.1 KiB |
| ours/hypothesis | 0.0 KiB | 0 | 66.1 KiB | 42.1 KiB |
| published/frames | 180.0 KiB | 562 | 1058.2 KiB | 5.5 KiB |
| published/hypothesis | 0.0 KiB | 0 | 37.2 KiB | 11.4 KiB |

## Provenance

| decoder / route | decisions | config_id ok | input hash ok | ledger id ok | ledger verifies | ledger entries |
|---|---|---|---|---|---|---|
| ours/frames | 816 | 816 | 816 | 816 | True | genesis 1, context 1, decision 816 |
| ours/hypothesis | 816 | 816 | 816 | 816 | True | genesis 1, context 1, decision 816 |
| published/frames | 816 | 816 | 816 | 816 | True | genesis 1, context 1, decision 816 |
| published/hypothesis | 816 | 816 | 816 | 816 | True | genesis 1, context 1, decision 816 |

## Controls (300 streams each; commits, one-sided 95 % CP upper bound)

| decoder | control | paper (split A, guard, LTT max) | batch (this run) | streaming frames (equal to batch) | streaming hypothesis (equal to batch) |
|---|---|---|---|---|---|
| ours | real | 29/300 | 29/300 | 29/300 (<= 0.1295; 300) | 29/300 (300) |
| ours | other_trial | 29/300 | 29/300 | 29/300 (<= 0.1295; 300) | 29/300 (300) |
| ours | frame_shuffled | 0/300 | 0/300 | 0/300 (<= 0.0099; 300) | 0/300 (300) |
| ours | uniform | 0/300 | 0/300 | 0/300 (<= 0.0099; 300) | 0/300 (300) |
| published | real | 115/300 | 115/300 | 115/300 (<= 0.4319; 300) | 115/300 (300) |
| published | other_trial | 0/300 | 0/300 | 0/300 (<= 0.0099; 300) | 0/300 (300) |
| published | frame_shuffled | 0/300 | 0/300 | 0/300 (<= 0.0099; 300) | 0/300 (300) |
| published | uniform | 0/300 | 0/300 | 0/300 (<= 0.0099; 300) | 0/300 (300) |

Streams: 816 frame files; hypothesis n-best JSON round trip equal: ours 816/816, published 816/816.
