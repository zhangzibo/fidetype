# R4 item 2: per-day (per-session) risk under the primary rule (LTT max)

Reviews: stats M2, editor M5(c). Tables: [results/tables.md](results/tables.md). Data: [results/per_day.json](results/per_day.json). Input: R3 split tables (r 0-49) and R4 split tables (r 50-199), guard on.

## Results: LTT max, pooled test wrong-commit per day (Σ wrong / Σ n over splits)

| day | n test / split | B2T ours R50 | ours R200 | published R50 | published R200 | published: share of splits > α (R50) |
|---|---|---|---|---|---|---|
| 27 | 14 | 0.000 | 0.001 | 0.047 | 0.048 | 0.58 |
| **34** | 50 | 0.036 | 0.038 | **0.102** | **0.098** | **0.94** |
| 46 | 49 | 0.032 | 0.035 | 0.039 | 0.040 | |
| 48 | 57 | 0.039 | 0.042 | 0.016 | 0.016 | |
| 69 | 57 | 0.020 | 0.021 | 0.012 | 0.015 | |
| 74 | 38 | 0.042 | 0.044 | 0.025 | 0.027 | |
| 76 | 104 | 0.030 | 0.031 | 0.033 | 0.031 | |
| 81 | 70 | 0.022 | 0.023 | 0.030 | 0.030 | |
| 83 | 85 | 0.034 | 0.039 | 0.048 | 0.047 | |
| 88 | 46 | 0.030 | 0.032 | 0.021 | 0.020 | |
| 90 | 74 | 0.026 | 0.029 | 0.018 | 0.019 | |
| 95 | 26 | 0.049 | 0.046 | 0.007 | 0.006 | |
| 223 | 74 | 0.021 | 0.023 | 0.020 | 0.020 | |
| 244 | 74 | 0.038 | 0.036 | 0.018 | 0.017 | |

- The stats reviewer's number is reproduced: published gate, day 34, LTT max = **0.102** (R50; 0.098 with R = 200). In 94 % of the 50 splits the day-34 test rate was above α. CRC max gave 0.108, plug-in 0.110.
- Our decoder: all 14 days ≤ 0.049 (R50) and ≤ 0.046 (R200).
- Fixed splits (one realisation, exact CP): published day 34 had 8 wrong commits in 50 trials under LTT max (0.160, CP95 [0.072, 0.291]) in split A and in split B. This single day is significantly above α.
- Joint LTT β = 0.10 on day 34 (published): 0.016 pooled at commit rate 0.060.
- sEMG per test participant (LTT max, R50): session-calibrated ≤ 0.038, cross-session ≤ 0.023, cross-subject 0.
- Group-conditional (Mondrian) LTT per day: with 1/4 of a day as calibration (8-52 items), LTT is feasible only for day 76 (52 items ≥ 45) and commits nothing on the other 13 days. Per-day LTT needs ≥ 45 calibration items per day; this design cannot supply that.

## Scope of the guarantee (for the reviser)
- LTT bounds the risk of the calibration distribution. In these splits that distribution is the mixture of the 14 days (B2T) or 19 participants (sEMG). It does not bound the risk of each day.
- On the published gate, one day in 14 (day 34) ran at about 2α under the primary rule over random splits, and at 3α in the fixed split. "The per-deployment guarantee is the one a user experiences" must be withdrawn or qualified: a user meets one session at a time.
- Remedy to name: per-session (Mondrian / group-conditional) calibration with ≥ 45 calibration items per session for LTT (≥ 19 for CRC), or a session-start calibration block (forward-chain V3).
