# M4-01 / M4-02 tables: lookahead L against accuracy, trust outcomes and latency

T15 val_eval (701 trials, 41 sessions). Frozen trust config `tcfg-f5ca0020b3b8fce2` (Paper 1 v4 recipe, fitted on the published decoder in M4-06; frame T 3.815); not refitted.

## Accuracy and trust outcomes against L

| model | L (ms) | greedy PER | WER (frozen T) | sentence exact (frozen T) | WER (T=1) | exact (T=1) | truth in n-best | commit rate (n) | wrong-commit (n) [CP95] | EAC | eWPM | always-commit eWPM | gaze eWPM | stream = batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| shared | 0 | 0.6565 | 0.9307 | 0.000 (0) | 0.8907 | 0.000 | 0.000 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 3.47 | 2.65 | 4.02 | 701/701 |
| shared | 40 | 0.4449 | 0.7189 | 0.001 (1) | 0.6791 | 0.006 | 0.006 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 4.13 | 3.46 | 4.02 | 701/701 |
| shared | 100 | 0.4097 | 0.6824 | 0.006 (4) | 0.6310 | 0.004 | 0.013 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 4.27 | 3.62 | 4.02 | 701/701 |
| shared | 200 | 0.3858 | 0.6477 | 0.006 (4) | 0.5979 | 0.016 | 0.017 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 4.44 | 3.83 | 4.02 | 701/701 |
| shared | 300 | 0.3768 | 0.6376 | 0.009 (6) | 0.5803 | 0.017 | 0.016 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 4.48 | 3.87 | 4.02 | 701/701 |
| shared | 500 | 0.3687 | 0.6383 | 0.006 (4) | 0.5728 | 0.014 | 0.024 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 4.48 | 3.86 | 4.02 | 701/701 |
| dedicated_0 | 0 | 0.6954 | 0.9996 | 0.000 (0) | 0.9307 | 0.000 | 0.000 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 3.38 | 2.57 | 4.02 | 701/701 |
| dedicated_25 | 500 | 0.3487 | 0.5345 | 0.037 (26) | 0.5405 | 0.034 | 0.070 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.15 | 4.56 | 4.02 | 701/701 |

## Emission timing (greedy CTC path)

available = stamp of the first greedy frame of the phoneme + L. Matched = the phoneme is aligned exactly (Levenshtein) to the reference in both conditions. Delta = this condition - reference (seconds), median and IQR over phonemes.

| comparison | emission stamp Δ median ms [IQR] | available Δ median ms [IQR] | last matched phoneme available Δ median ms | n phonemes |
|---|---|---|---|---|
| shared/L2 vs shared/L0 | 0 [0, 0] | 40 [40, 40] | 40 | 5944 |
| shared/L5 vs shared/L0 | 0 [0, 0] | 100 [100, 100] | 100 | 5982 |
| shared/L10 vs shared/L0 | 0 [0, 0] | 200 [200, 200] | 200 | 6030 |
| shared/L15 vs shared/L0 | 0 [0, 0] | 300 [300, 300] | 300 | 6078 |
| shared/L25 vs shared/L0 | 0 [0, 0] | 500 [500, 500] | 500 | 6094 |
| dedicated_0/L0 vs shared/L0 | 240 [-160, 480] | 240 [-160, 480] | 160 | 4732 |
| dedicated_25/L25 vs shared/L0 | -480 [-720, -240] | 20 [-220, 260] | 100 | 5802 |
| shared/L0 vs dedicated_0/L0 | -240 [-480, 160] | -240 [-480, 160] | -160 | 4732 |
| shared/L2 vs dedicated_0/L0 | -240 [-400, 240] | -200 [-360, 280] | -120 | 5107 |
| shared/L5 vs dedicated_0/L0 | -240 [-400, 240] | -140 [-300, 340] | -60 | 5176 |
| shared/L10 vs dedicated_0/L0 | -240 [-400, 240] | -40 [-200, 440] | 40 | 5219 |
| shared/L15 vs dedicated_0/L0 | -240 [-400, 240] | 60 [-100, 540] | 140 | 5249 |
| shared/L25 vs dedicated_0/L0 | -240 [-400, 240] | 260 [100, 740] | 340 | 5274 |
| dedicated_25/L25 vs dedicated_0/L0 | -680 [-1040, -240] | -180 [-540, 260] | -140 | 5120 |

| condition | last emission stamp -> utterance end, median s [IQR] |
|---|---|
| shared/L0 | 3.60 [2.56, 5.36] |
| shared/L2 | 3.20 [2.08, 4.88] |
| shared/L5 | 3.20 [2.08, 4.88] |
| shared/L10 | 3.20 [2.08, 4.88] |
| shared/L15 | 3.20 [2.08, 4.88] |
| shared/L25 | 3.12 [2.08, 4.88] |
| dedicated_0/L0 | 3.68 [2.48, 5.44] |
| dedicated_25/L25 | 3.44 [2.32, 5.12] |

## Latency against L (shared model, 200 trials, NumPy streaming decoder + StreamingTrustLayer incremental)

Measurement environment clean: False (other load on the class CPUs 5.77% >= 5.0%, SMT siblings of timing cores busy 25.23%).

| L (ms) | algorithmic lookahead ms | + stride wait ms (max) | decoder push per 20 ms bin p50 / p95 ms | trust push per frame p50 / p95 ms | end of utterance: decoder flush p50 ms | trust end p50 / p95 / max ms | total end p50 / p95 / max ms | same action as accuracy stage |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 60 | 0.04 / 2.01 | 0.24 / 0.33 | 0.0 | 79.8 / 148.3 / 280.6 | 79.8 / 148.3 / 280.6 | 200/200 |
| 40 | 40 | 60 | 0.09 / 1.96 | 0.24 / 0.34 | 0.0 | 99.5 / 188.8 / 262.6 | 99.6 / 188.9 / 262.6 | 200/200 |
| 100 | 100 | 60 | 0.08 / 2.06 | 0.25 / 0.36 | 0.1 | 107.4 / 201.0 / 281.0 | 107.5 / 201.0 / 281.0 | 200/200 |
| 200 | 200 | 60 | 0.09 / 2.10 | 0.25 / 0.36 | 0.2 | 102.8 / 180.2 / 274.2 | 103.1 / 180.3 / 274.4 | 200/200 |
| 300 | 300 | 60 | 0.09 / 2.11 | 0.25 / 0.36 | 0.3 | 99.2 / 193.1 / 256.0 | 99.4 / 193.3 / 256.3 | 200/200 |
| 500 | 500 | 60 | 0.07 / 1.99 | 0.24 / 0.34 | 0.4 | 99.1 / 172.7 / 271.7 | 99.5 / 173.0 / 272.1 | 200/200 |
