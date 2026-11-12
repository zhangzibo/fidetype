# MEG: CRC with calibration and test split by sentence / participant

G1 item table (trust gate fitted on val; 637 test instances, 17 sentences x 19 participants); eligible 0.024; top-1 right 0.0031. R = 1000 splits per row. alpha = 0.05.

## Guarantee status

- clean calibration (5 val sentences): sentence-level CRC infeasible (5 < 19): never commits; instance-level CRC has no guarantee for new sentences
- val (11 sentences): sentence-level CRC infeasible (11 < 19)
- whole test pool (17 sentences): sentence-level CRC infeasible (17 < 19)
- participants (19): participant-level CRC needs all 19 for calibration: no test participants left
- Minimum calibration groups: CRC 19, LTT (zero loss, delta 0.1) 45.

## Splits

| split | rule | wrong-commit mean [p05, p95] | share > α | commit rate mean | no-commit share | error among commits (pooled) | eWPM mean |
|---|---|---|---|---|---|---|---|
| sentence-grouped 5 of 17 | CRC instance | 0.0159 [0.0046, 0.0251] | 0.000 | 0.0174 | 0.018 | 0.913 | 3.202 |
| sentence-grouped 5 of 17 | CRC instance max-rule | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.206 |
| sentence-grouped 5 of 17 | LTT instance | 0.0172 [0.0000, 0.0294] | 0.000 | 0.0188 | 0.114 | 0.917 | 3.202 |
| sentence-grouped 5 of 17 | CRC group-level | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.206 |
| sentence-grouped 5 of 17 | group-level CRC feasible share | 0.00 | | | | | |
| random instances, n_cal 188 (same size as 5 sentences) | CRC instance | 0.0167 [0.0067, 0.0245] | 0.000 | 0.0183 | 0.009 | 0.915 | 3.198 |
| random instances, n_cal 188 (same size as 5 sentences) | CRC instance max-rule | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.203 |
| random instances, n_cal 188 (same size as 5 sentences) | LTT instance | 0.0189 [0.0000, 0.0267] | 0.000 | 0.0204 | 0.054 | 0.924 | 3.199 |
| sentence-grouped 8 of 17 | CRC instance | 0.0180 [0.0063, 0.0307] | 0.000 | 0.0197 | 0.001 | 0.916 | 3.200 |
| sentence-grouped 8 of 17 | CRC instance max-rule | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.205 |
| sentence-grouped 8 of 17 | LTT instance | 0.0208 [0.0000, 0.0336] | 0.000 | 0.0225 | 0.067 | 0.926 | 3.201 |
| sentence-grouped 8 of 17 | CRC group-level | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.205 |
| sentence-grouped 8 of 17 | group-level CRC feasible share | 0.00 | | | | | |
| random instances, n_cal 300 (same size as 8 sentences) | CRC instance | 0.0186 [0.0089, 0.0267] | 0.000 | 0.0202 | 0.000 | 0.921 | 3.198 |
| random instances, n_cal 300 (same size as 8 sentences) | CRC instance max-rule | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.203 |
| random instances, n_cal 300 (same size as 8 sentences) | LTT instance | 0.0217 [0.0148, 0.0297] | 0.000 | 0.0233 | 0.027 | 0.931 | 3.198 |
| sentence-grouped 11 of 17 | CRC instance | 0.0193 [0.0042, 0.0377] | 0.000 | 0.0208 | 0.015 | 0.924 | 3.198 |
| sentence-grouped 11 of 17 | CRC instance max-rule | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.204 |
| sentence-grouped 11 of 17 | LTT instance | 0.0222 [0.0083, 0.0400] | 0.001 | 0.0238 | 0.003 | 0.933 | 3.198 |
| sentence-grouped 11 of 17 | CRC group-level | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.204 |
| sentence-grouped 11 of 17 | group-level CRC feasible share | 0.00 | | | | | |
| random instances, n_cal 413 (same size as 11 sentences) | CRC instance | 0.0192 [0.0089, 0.0312] | 0.000 | 0.0207 | 0.005 | 0.930 | 3.198 |
| random instances, n_cal 413 (same size as 11 sentences) | CRC instance max-rule | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.203 |
| random instances, n_cal 413 (same size as 11 sentences) | LTT instance | 0.0218 [0.0089, 0.0357] | 0.000 | 0.0232 | 0.003 | 0.937 | 3.198 |
| participant-grouped 6 of 19 | CRC instance | 0.0153 [0.0000, 0.0261] | 0.000 | 0.0167 | 0.073 | 0.917 | 3.202 |
| participant-grouped 6 of 19 | CRC instance max-rule | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.206 |
| participant-grouped 6 of 19 | LTT instance | 0.0173 [0.0000, 0.0325] | 0.000 | 0.0189 | 0.252 | 0.916 | 3.202 |
| participant-grouped 6 of 19 | CRC group-level | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.206 |
| participant-grouped 6 of 19 | group-level CRC feasible share | 0.00 | | | | | |
| participant-grouped 12 of 19 | CRC instance | 0.0193 [0.0038, 0.0390] | 0.003 | 0.0209 | 0.031 | 0.926 | 3.208 |
| participant-grouped 12 of 19 | CRC instance max-rule | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.213 |
| participant-grouped 12 of 19 | LTT instance | 0.0224 [0.0000, 0.0471] | 0.030 | 0.0240 | 0.057 | 0.935 | 3.208 |
| participant-grouped 12 of 19 | CRC group-level | 0.0000 [0.0000, 0.0000] | 0.000 | 0.0000 | 1.000 | — | 3.213 |
| participant-grouped 12 of 19 | group-level CRC feasible share | 0.00 | | | | | |