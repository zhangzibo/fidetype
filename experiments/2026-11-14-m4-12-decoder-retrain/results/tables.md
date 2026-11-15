# M4-12 tables (retrained decoders): lookahead L against accuracy, trust outcomes and latency

T15 val_eval (701 trials, 41 sessions). Frozen trust config `tcfg-f5ca0020b3b8fce2` (Paper 1 v4 recipe, fitted on the published decoder in M4-06; frame T 3.815); not refitted.

## Accuracy and trust outcomes against L

| model | L (ms) | greedy PER | WER (frozen T) | sentence exact (frozen T) | WER (T=1) | exact (T=1) | truth in n-best | commit rate (n) | wrong-commit (n) [CP95] | EAC | eWPM | always-commit eWPM | gaze eWPM | stream = batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| shared | 0 | 0.2634 | 0.4195 | 0.068 (48) | 0.4049 | 0.088 | 0.124 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.88 | 5.44 | 4.02 | 701/701 |
| shared | 40 | 0.2614 | 0.4173 | 0.064 (45) | 0.4034 | 0.086 | 0.121 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.87 | 5.42 | 4.02 | 701/701 |
| shared | 100 | 0.2623 | 0.4145 | 0.068 (48) | 0.4032 | 0.084 | 0.114 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.89 | 5.44 | 4.02 | 701/701 |
| shared | 200 | 0.2612 | 0.4171 | 0.068 (48) | 0.4006 | 0.080 | 0.120 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.88 | 5.41 | 4.02 | 701/701 |
| shared | 300 | 0.2608 | 0.4154 | 0.073 (51) | 0.4030 | 0.083 | 0.127 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.90 | 5.44 | 4.02 | 701/701 |
| shared | 500 | 0.2617 | 0.4094 | 0.073 (51) | 0.4013 | 0.087 | 0.126 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.93 | 5.54 | 4.02 | 701/701 |
| dedicated_0 | 0 | 0.2574 | 0.4105 | 0.074 (52) | 0.3998 | 0.090 | 0.131 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.94 | 5.53 | 4.02 | 701/701 |
| dedicated_10 | 200 | 0.2594 | 0.4036 | 0.081 (57) | 0.3923 | 0.101 | 0.140 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 6.02 | 5.62 | 4.02 | 701/701 |
| dedicated_15 | 300 | 0.2599 | 0.4109 | 0.077 (54) | 0.3998 | 0.090 | 0.130 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.97 | 5.54 | 4.02 | 701/701 |
| dedicated_25 | 500 | 0.2988 | 0.4336 | 0.068 (48) | 0.4565 | 0.068 | 0.128 | 0.000 (0) | 0.0000 (0) [0.000, 0.005] | — | 5.77 | 5.31 | 4.02 | 701/701 |

## Emission timing (greedy CTC path)

available = stamp of the first greedy frame of the phoneme + L. Matched = the phoneme is aligned exactly (Levenshtein) to the reference in both conditions. Delta = this condition - reference (seconds), median and IQR over phonemes.

| comparison | emission stamp Δ median ms [IQR] | available Δ median ms [IQR] | last matched phoneme available Δ median ms | n phonemes |
|---|---|---|---|---|
| dedicated_0/L0 vs shared/L0 | 0 [0, 80] | 0 [0, 80] | 0 | 14415 |
| dedicated_25/L25 vs shared/L0 | -400 [-960, -240] | 100 [-460, 260] | 180 | 13151 |
| shared/L2 vs shared/L0 | 0 [0, 0] | 40 [40, 40] | 40 | 14872 |
| shared/L5 vs shared/L0 | 0 [0, 0] | 100 [100, 100] | 100 | 14789 |
| shared/L10 vs shared/L0 | 0 [0, 0] | 200 [200, 200] | 200 | 14704 |
| shared/L15 vs shared/L0 | 0 [0, 0] | 300 [300, 300] | 300 | 14684 |
| shared/L25 vs shared/L0 | 0 [0, 0] | 500 [500, 500] | 500 | 14646 |
| dedicated_10/L10 vs shared/L0 | 0 [-80, 0] | 200 [120, 200] | 200 | 14260 |
| dedicated_15/L15 vs shared/L0 | -80 [-80, 0] | 220 [220, 300] | 300 | 14175 |
| dedicated_25/L25 vs dedicated_0/L0 | -400 [-960, -320] | 100 [-460, 180] | 180 | 13190 |
| shared/L0 vs dedicated_0/L0 | 0 [-80, 0] | 0 [-80, 0] | 0 | 14415 |
| shared/L2 vs dedicated_0/L0 | 0 [-80, 0] | 40 [-40, 40] | 40 | 14446 |
| shared/L5 vs dedicated_0/L0 | 0 [-80, 0] | 100 [20, 100] | 100 | 14411 |
| shared/L10 vs dedicated_0/L0 | 0 [-80, 0] | 200 [120, 200] | 200 | 14396 |
| shared/L15 vs dedicated_0/L0 | 0 [-80, 0] | 300 [220, 300] | 300 | 14397 |
| shared/L25 vs dedicated_0/L0 | 0 [-80, 0] | 500 [420, 500] | 500 | 14379 |
| dedicated_10/L10 vs dedicated_0/L0 | -80 [-80, 0] | 120 [120, 200] | 120 | 14317 |
| dedicated_15/L15 vs dedicated_0/L0 | -80 [-80, 0] | 220 [220, 300] | 220 | 14309 |

| condition | last emission stamp -> utterance end, median s [IQR] |
|---|---|
| dedicated_0/L0 | 2.32 [1.44, 4.08] |
| dedicated_25/L25 | 2.72 [1.84, 4.56] |
| shared/L0 | 2.40 [1.44, 4.16] |
| shared/L2 | 2.40 [1.44, 4.16] |
| shared/L5 | 2.40 [1.44, 4.16] |
| shared/L10 | 2.40 [1.44, 4.16] |
| shared/L15 | 2.40 [1.44, 4.16] |
| shared/L25 | 2.40 [1.44, 4.16] |
| dedicated_10/L10 | 2.40 [1.52, 4.16] |
| dedicated_15/L15 | 2.40 [1.52, 4.16] |
