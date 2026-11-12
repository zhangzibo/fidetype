# Repeated deployment splits: tables

R = 50 (B2T) / 50 (sEMG) random splits; alpha = 0.05; delta = 0.1. Mean [5th, 95th percentile] over splits of the test-set value. '>α' = share of splits with test wrong-commit > α. Splits re-use one finite data set: the spread is split-to-split variation, not a CI for new data.

## b2t-ours (R = 50; frame T used 3.512, max snap 0.0094)

| policy | wrong-commit mean [p05, p95] | >α | commit rate mean [p05, p95] | error among commits (pooled) | no-commit splits | eWPM mean [p05, p95] |
|---|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0440 [0.0213, 0.0724] | 0.34 | 0.186 [0.130, 0.259] | 0.237 | 0.00 | 11.08 [10.83, 11.37] |
| CRC pure (clean) | 0.0456 [0.0262, 0.0679] | 0.34 | 0.192 [0.128, 0.261] | 0.237 | 0.00 | 11.09 [10.81, 11.39] |
| CRC max-rule (clean) | 0.0368 [0.0208, 0.0594] | 0.14 | 0.166 [0.123, 0.227] | 0.221 | 0.00 | 11.08 [10.81, 11.37] |
| LTT pure (clean) | 0.0344 [0.0169, 0.0564] | 0.16 | 0.158 [0.107, 0.229] | 0.217 | 0.00 | 11.07 [10.81, 11.38] |
| LTT max-rule (clean) | 0.0304 [0.0163, 0.0521] | 0.08 | 0.147 [0.105, 0.198] | 0.207 | 0.00 | 11.07 [10.81, 11.37] |
| CRC pure (reused) | 0.0546 [0.0366, 0.0845] | 0.58 | 0.213 [0.177, 0.283] | 0.256 | 0.00 | 11.10 [10.84, 11.39] |
| CRC max-rule (reused) | 0.0434 [0.0213, 0.0697] | 0.32 | 0.184 [0.130, 0.259] | 0.236 | 0.00 | 11.08 [10.83, 11.37] |
| LTT pure (reused) | 0.0396 [0.0232, 0.0630] | 0.26 | 0.174 [0.130, 0.223] | 0.228 | 0.00 | 11.08 [10.83, 11.36] |

Binding: CRC constraint active (excludes an eligible calibration item) in 0.98 of splits; CRC stricter than plug-in 0.56; max-rule changes a test decision 0.54; pure CRC differs from plug-in on test 0.98; plug-in certified by the calibration bound (n R̂(λ_plug-in) + 1)/(n + 1) ≤ α in 0.50. CRC bound at λ̂: mean 0.0489; calibration bound at plug-in λ: mean 0.0490 [0.0197, 0.0777]. Plug-in λ mean 0.540 [0.40, 0.60].

Reused vs clean calibration (paired by split; reused − clean test wrong-commit):

| pair | mean diff [p05, p95] | reused higher | equal | Wilcoxon p | sign test (+/−) p | MDE80 (mean) |
|---|---|---|---|---|---|---|
| CRC pure (reused) - CRC pure (clean) | 0.0091 [-0.0202, 0.0400] | 0.70 | 0.02 | 0.00275 | 35/14 p 0.0038 | 0.0076 |
| CRC max-rule (reused) - CRC max-rule (clean) | 0.0066 [0.0000, 0.0276] | 0.52 | 0.46 | 1.08e-05 | 26/1 p 4.17e-07 | 0.0038 |
| LTT pure (reused) - LTT pure (clean) | 0.0052 [-0.0269, 0.0312] | 0.62 | 0.12 | 0.0336 | 31/13 p 0.00956 | 0.0069 |

Power: SD of the clean-CRC test rate over splits 0.0140; one deployment detects a shift of 0.0348 with 80 % power (one-sided 5 %); the mean over R splits resolves 0.0049 (Monte-Carlo).

Selective-risk controllers (target error among commits β; δ = 0.1; clean calibration):

| β | method | commit rate mean [p05, p95] | error among commits pooled | share EAC > β | no-commit splits | wrong-commit mean | eWPM mean |
|---|---|---|---|---|---|---|---|
| 0.05 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 10.95 |
| 0.05 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 10.95 |
| 0.05 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 10.95 |
| 0.10 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 10.95 |
| 0.10 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 10.95 |
| 0.10 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 10.95 |
| 0.20 | SGR | 0.003 [0.000, 0.000] | 0.208 | 0.02 | 0.96 | 0.0007 | 10.95 |
| 0.20 | LTT-sel | 0.001 [0.000, 0.000] | 0.290 | 0.02 | 0.98 | 0.0002 | 10.95 |
| 0.20 | joint (SGR + CRC max-rule) | 0.003 [0.000, 0.000] | 0.208 | 0.02 | 0.96 | 0.0007 | 10.95 |

Per-day test results over splits (mean [p05, p95]):

| day | plug-in wrong-commit | plug-in commit rate | CRC max-rule wrong-commit | CRC max-rule commit rate |
|---|---|---|---|---|
| 27 | 0.0029 [0.0000, 0.0000] | 0.006 | 0.0014 [0.0000, 0.0000] | 0.003 |
| 34 | 0.0460 [0.0090, 0.0800] | 0.130 | 0.0412 [0.0000, 0.0800] | 0.118 |
| 46 | 0.0429 [0.0092, 0.0816] | 0.191 | 0.0367 [0.0092, 0.0724] | 0.173 |
| 48 | 0.0512 [0.0175, 0.0974] | 0.173 | 0.0463 [0.0175, 0.0877] | 0.160 |
| 69 | 0.0309 [0.0000, 0.0702] | 0.200 | 0.0235 [0.0000, 0.0526] | 0.181 |
| 74 | 0.0632 [0.0000, 0.1316] | 0.205 | 0.0526 [0.0000, 0.1053] | 0.184 |
| 76 | 0.0400 [0.0139, 0.0769] | 0.170 | 0.0346 [0.0096, 0.0673] | 0.155 |
| 81 | 0.0374 [0.0064, 0.0793] | 0.187 | 0.0306 [0.0064, 0.0650] | 0.169 |
| 83 | 0.0579 [0.0118, 0.1176] | 0.218 | 0.0461 [0.0118, 0.1059] | 0.196 |
| 88 | 0.0409 [0.0098, 0.0989] | 0.198 | 0.0352 [0.0000, 0.0772] | 0.174 |
| 90 | 0.0465 [0.0135, 0.0946] | 0.208 | 0.0346 [0.0135, 0.0676] | 0.179 |
| 95 | 0.0638 [0.0000, 0.1154] | 0.225 | 0.0554 [0.0000, 0.1154] | 0.185 |
| 223 | 0.0322 [0.0000, 0.0811] | 0.184 | 0.0265 [0.0000, 0.0676] | 0.168 |
| 244 | 0.0465 [0.0135, 0.0811] | 0.182 | 0.0405 [0.0135, 0.0676] | 0.162 |

## b2t-published (R = 50; frame T used 3.512, max snap 0.0094)

| policy | wrong-commit mean [p05, p95] | >α | commit rate mean [p05, p95] | error among commits (pooled) | no-commit splits | eWPM mean [p05, p95] |
|---|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0394 [0.0208, 0.0600] | 0.22 | 0.433 [0.356, 0.506] | 0.091 | 0.00 | 18.54 [18.21, 18.92] |
| CRC pure (clean) | 0.0489 [0.0293, 0.0752] | 0.42 | 0.478 [0.405, 0.557] | 0.102 | 0.00 | 18.60 [18.21, 19.01] |
| CRC max-rule (clean) | 0.0357 [0.0208, 0.0551] | 0.14 | 0.418 [0.356, 0.494] | 0.085 | 0.00 | 18.52 [18.19, 18.92] |
| LTT pure (clean) | 0.0342 [0.0213, 0.0509] | 0.06 | 0.410 [0.340, 0.477] | 0.083 | 0.00 | 18.51 [18.16, 18.88] |
| LTT max-rule (clean) | 0.0307 [0.0201, 0.0471] | 0.02 | 0.392 [0.340, 0.455] | 0.078 | 0.00 | 18.49 [18.15, 18.88] |
| CRC pure (reused) | 0.0497 [0.0323, 0.0728] | 0.48 | 0.482 [0.434, 0.554] | 0.103 | 0.00 | 18.61 [18.23, 19.05] |
| CRC max-rule (reused) | 0.0392 [0.0208, 0.0600] | 0.22 | 0.432 [0.356, 0.506] | 0.091 | 0.00 | 18.54 [18.21, 18.92] |
| LTT pure (reused) | 0.0355 [0.0189, 0.0532] | 0.12 | 0.417 [0.363, 0.496] | 0.085 | 0.00 | 18.52 [18.17, 18.97] |

Binding: CRC constraint active (excludes an eligible calibration item) in 1.00 of splits; CRC stricter than plug-in 0.34; max-rule changes a test decision 0.34; pure CRC differs from plug-in on test 1.00; plug-in certified by the calibration bound (n R̂(λ_plug-in) + 1)/(n + 1) ≤ α in 0.66. CRC bound at λ̂: mean 0.0493; calibration bound at plug-in λ: mean 0.0417 [0.0172, 0.0679]. Plug-in λ mean 0.724 [0.70, 0.80].

Reused vs clean calibration (paired by split; reused − clean test wrong-commit):

| pair | mean diff [p05, p95] | reused higher | equal | Wilcoxon p | sign test (+/−) p | MDE80 (mean) |
|---|---|---|---|---|---|---|
| CRC pure (reused) - CRC pure (clean) | 0.0009 [-0.0288, 0.0288] | 0.52 | 0.02 | 0.716 | 26/23 p 0.775 | 0.0069 |
| CRC max-rule (reused) - CRC max-rule (clean) | 0.0035 [-0.0007, 0.0232] | 0.30 | 0.64 | 0.00136 | 15/3 p 0.00754 | 0.0030 |
| LTT pure (reused) - LTT pure (clean) | 0.0013 [-0.0204, 0.0202] | 0.46 | 0.22 | 0.494 | 23/16 p 0.337 | 0.0054 |

Power: SD of the clean-CRC test rate over splits 0.0152; one deployment detects a shift of 0.0378 with 80 % power (one-sided 5 %); the mean over R splits resolves 0.0053 (Monte-Carlo).

Selective-risk controllers (target error among commits β; δ = 0.1; clean calibration):

| β | method | commit rate mean [p05, p95] | error among commits pooled | share EAC > β | no-commit splits | wrong-commit mean | eWPM mean |
|---|---|---|---|---|---|---|---|
| 0.05 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 17.98 |
| 0.05 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 17.98 |
| 0.05 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 17.98 |
| 0.10 | SGR | 0.112 [0.000, 0.376] | 0.069 | 0.00 | 0.64 | 0.0077 | 18.12 |
| 0.10 | LTT-sel | 0.072 [0.000, 0.335] | 0.059 | 0.00 | 0.76 | 0.0043 | 18.07 |
| 0.10 | joint (SGR + CRC max-rule) | 0.111 [0.000, 0.367] | 0.068 | 0.00 | 0.64 | 0.0075 | 18.12 |
| 0.20 | SGR | 0.617 [0.455, 0.850] | 0.142 | 0.00 | 0.00 | 0.0878 | 18.79 |
| 0.20 | LTT-sel | 0.564 [0.361, 0.730] | 0.131 | 0.00 | 0.00 | 0.0736 | 18.72 |
| 0.20 | joint (SGR + CRC max-rule) | 0.418 [0.356, 0.494] | 0.085 | 0.00 | 0.00 | 0.0357 | 18.52 |

Per-day test results over splits (mean [p05, p95]):

| day | plug-in wrong-commit | plug-in commit rate | CRC max-rule wrong-commit | CRC max-rule commit rate |
|---|---|---|---|---|
| 27 | 0.0471 [0.0000, 0.1429] | 0.161 | 0.0471 [0.0000, 0.1429] | 0.160 |
| 34 | 0.1104 [0.0490, 0.1710] | 0.368 | 0.1080 [0.0490, 0.1600] | 0.362 |
| 46 | 0.0473 [0.0204, 0.0816] | 0.477 | 0.0429 [0.0092, 0.0816] | 0.468 |
| 48 | 0.0204 [0.0000, 0.0447] | 0.337 | 0.0175 [0.0000, 0.0351] | 0.316 |
| 69 | 0.0340 [0.0000, 0.1053] | 0.407 | 0.0221 [0.0000, 0.0702] | 0.386 |
| 74 | 0.0263 [0.0000, 0.0526] | 0.391 | 0.0258 [0.0000, 0.0526] | 0.377 |
| 76 | 0.0419 [0.0139, 0.0769] | 0.444 | 0.0385 [0.0096, 0.0726] | 0.431 |
| 81 | 0.0440 [0.0064, 0.0857] | 0.378 | 0.0383 [0.0064, 0.0714] | 0.363 |
| 83 | 0.0588 [0.0235, 0.0888] | 0.455 | 0.0541 [0.0235, 0.0824] | 0.439 |
| 88 | 0.0291 [0.0000, 0.0652] | 0.514 | 0.0252 [0.0000, 0.0652] | 0.506 |
| 90 | 0.0235 [0.0000, 0.0541] | 0.506 | 0.0219 [0.0000, 0.0405] | 0.488 |
| 95 | 0.0146 [0.0000, 0.0385] | 0.587 | 0.0131 [0.0000, 0.0385] | 0.569 |
| 223 | 0.0232 [0.0000, 0.0480] | 0.426 | 0.0211 [0.0000, 0.0405] | 0.409 |
| 244 | 0.0273 [0.0000, 0.0615] | 0.457 | 0.0249 [0.0000, 0.0615] | 0.441 |

## emg-calib (R = 50; frame T used 1.283, max snap 0.0049)

| policy | wrong-commit mean [p05, p95] | >α | commit rate mean [p05, p95] | error among commits (pooled) | no-commit splits | eWPM mean [p05, p95] |
|---|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0146 [0.0036, 0.0328] | 0.00 | 0.116 [0.035, 0.220] | 0.126 | 0.02 | 8.01 [7.89, 8.10] |
| CRC pure (clean) | 0.0286 [0.0107, 0.0612] | 0.06 | 0.187 [0.102, 0.286] | 0.153 | 0.02 | 8.04 [7.95, 8.11] |
| CRC max-rule (clean) | 0.0125 [0.0036, 0.0236] | 0.00 | 0.105 [0.035, 0.172] | 0.119 | 0.02 | 8.01 [7.89, 8.09] |
| LTT pure (clean) | 0.0173 [0.0091, 0.0337] | 0.00 | 0.137 [0.088, 0.211] | 0.127 | 0.02 | 8.02 [7.92, 8.09] |
| LTT max-rule (clean) | 0.0106 [0.0036, 0.0191] | 0.00 | 0.093 [0.035, 0.154] | 0.115 | 0.02 | 8.00 [7.89, 8.08] |
| CRC pure (reused) | 0.0270 [0.0109, 0.0510] | 0.06 | 0.183 [0.104, 0.275] | 0.147 | 0.02 | 8.04 [7.95, 8.12] |
| CRC max-rule (reused) | 0.0144 [0.0036, 0.0328] | 0.00 | 0.114 [0.035, 0.220] | 0.126 | 0.02 | 8.01 [7.89, 8.10] |
| LTT pure (reused) | 0.0135 [0.0036, 0.0264] | 0.00 | 0.112 [0.044, 0.196] | 0.120 | 0.02 | 8.01 [7.91, 8.10] |

Binding: CRC constraint active (excludes an eligible calibration item) in 0.98 of splits; CRC stricter than plug-in 0.26; max-rule changes a test decision 0.22; pure CRC differs from plug-in on test 0.96; plug-in certified by the calibration bound (n R̂(λ_plug-in) + 1)/(n + 1) ≤ α in 0.84. CRC bound at λ̂: mean 0.0440; calibration bound at plug-in λ: mean 0.0318 [0.0075, 0.0713]. Plug-in λ mean 0.594 [0.45, 0.80].

Reused vs clean calibration (paired by split; reused − clean test wrong-commit):

| pair | mean diff [p05, p95] | reused higher | equal | Wilcoxon p | sign test (+/−) p | MDE80 (mean) |
|---|---|---|---|---|---|---|
| CRC pure (reused) - CRC pure (clean) | -0.0016 [-0.0320, 0.0256] | 0.46 | 0.08 | 0.714 | 23/23 p 1 | 0.0084 |
| CRC max-rule (reused) - CRC max-rule (clean) | 0.0019 [0.0000, 0.0157] | 0.18 | 0.80 | 0.0106 | 9/1 p 0.0215 | 0.0022 |
| LTT pure (reused) - LTT pure (clean) | -0.0038 [-0.0218, 0.0137] | 0.30 | 0.04 | 0.0198 | 15/33 p 0.0133 | 0.0045 |

Power: SD of the clean-CRC test rate over splits 0.0159; one deployment detects a shift of 0.0396 with 80 % power (one-sided 5 %); the mean over R splits resolves 0.0056 (Monte-Carlo).

Selective-risk controllers (target error among commits β; δ = 0.1; clean calibration):

| β | method | commit rate mean [p05, p95] | error among commits pooled | share EAC > β | no-commit splits | wrong-commit mean | eWPM mean |
|---|---|---|---|---|---|---|---|
| 0.05 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |
| 0.05 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |
| 0.05 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |
| 0.10 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |
| 0.10 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |
| 0.10 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |
| 0.20 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |
| 0.20 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |
| 0.20 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 7.97 |

## emg-xsession (R = 50; frame T used 1.759, max snap 0.0049)

| policy | wrong-commit mean [p05, p95] | >α | commit rate mean [p05, p95] | error among commits (pooled) | no-commit splits | eWPM mean [p05, p95] |
|---|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0082 [0.0000, 0.0330] | 0.04 | 0.019 [0.000, 0.060] | 0.440 | 0.34 | 4.68 [4.63, 4.72] |
| CRC pure (clean) | 0.0248 [0.0000, 0.0627] | 0.14 | 0.043 [0.000, 0.102] | 0.575 | 0.34 | 4.67 [4.63, 4.72] |
| CRC max-rule (clean) | 0.0068 [0.0000, 0.0272] | 0.00 | 0.016 [0.000, 0.051] | 0.414 | 0.34 | 4.68 [4.63, 4.72] |
| LTT pure (clean) | 0.0169 [0.0000, 0.0436] | 0.02 | 0.032 [0.000, 0.071] | 0.532 | 0.34 | 4.68 [4.63, 4.72] |
| LTT max-rule (clean) | 0.0057 [0.0000, 0.0228] | 0.00 | 0.015 [0.000, 0.046] | 0.382 | 0.34 | 4.68 [4.63, 4.72] |
| CRC pure (reused) | 0.0321 [0.0000, 0.0708] | 0.24 | 0.055 [0.000, 0.116] | 0.587 | 0.34 | 4.67 [4.63, 4.71] |
| CRC max-rule (reused) | 0.0079 [0.0000, 0.0330] | 0.02 | 0.018 [0.000, 0.060] | 0.436 | 0.34 | 4.68 [4.63, 4.72] |
| LTT pure (reused) | 0.0177 [0.0000, 0.0464] | 0.04 | 0.033 [0.000, 0.081] | 0.532 | 0.34 | 4.68 [4.63, 4.72] |

Binding: CRC constraint active (excludes an eligible calibration item) in 0.66 of splits; CRC stricter than plug-in 0.40; max-rule changes a test decision 0.06; pure CRC differs from plug-in on test 0.64; plug-in certified by the calibration bound (n R̂(λ_plug-in) + 1)/(n + 1) ≤ α in 0.94. CRC bound at λ̂: mean 0.0321; calibration bound at plug-in λ: mean 0.0169 [0.0075, 0.0489]. Plug-in λ mean 0.314 [0.30, 0.40].

Reused vs clean calibration (paired by split; reused − clean test wrong-commit):

| pair | mean diff [p05, p95] | reused higher | equal | Wilcoxon p | sign test (+/−) p | MDE80 (mean) |
|---|---|---|---|---|---|---|
| CRC pure (reused) - CRC pure (clean) | 0.0073 [-0.0181, 0.0427] | 0.36 | 0.38 | 0.036 | 18/13 p 0.473 | 0.0081 |
| CRC max-rule (reused) - CRC max-rule (clean) | 0.0012 [0.0000, 0.0010] | 0.06 | 0.94 | 0.109 | 3/0 p 0.25 | 0.0025 |
| LTT pure (reused) - LTT pure (clean) | 0.0008 [-0.0312, 0.0347] | 0.26 | 0.44 | 0.811 | 13/15 p 0.851 | 0.0079 |

Power: SD of the clean-CRC test rate over splits 0.0229; one deployment detects a shift of 0.0569 with 80 % power (one-sided 5 %); the mean over R splits resolves 0.0080 (Monte-Carlo).

Selective-risk controllers (target error among commits β; δ = 0.1; clean calibration):

| β | method | commit rate mean [p05, p95] | error among commits pooled | share EAC > β | no-commit splits | wrong-commit mean | eWPM mean |
|---|---|---|---|---|---|---|---|
| 0.05 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |
| 0.05 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |
| 0.05 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |
| 0.10 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |
| 0.10 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |
| 0.10 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |
| 0.20 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |
| 0.20 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |
| 0.20 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.68 |

## emg-xsubject (R = 50; frame T used 2.175, max snap 0.0049)

| policy | wrong-commit mean [p05, p95] | >α | commit rate mean [p05, p95] | error among commits (pooled) | no-commit splits | eWPM mean [p05, p95] |
|---|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0000 [0.0000, 0.0000] | 0.00 | 0.000 [0.000, 0.000] | 0.000 | 1.00 | 4.07 [4.02, 4.12] |
| CRC pure (clean) | 0.0000 [0.0000, 0.0000] | 0.00 | 0.000 [0.000, 0.000] | 0.000 | 1.00 | 4.07 [4.02, 4.12] |
| CRC max-rule (clean) | 0.0000 [0.0000, 0.0000] | 0.00 | 0.000 [0.000, 0.000] | 0.000 | 1.00 | 4.07 [4.02, 4.12] |
| LTT pure (clean) | 0.0000 [0.0000, 0.0000] | 0.00 | 0.000 [0.000, 0.000] | 0.000 | 1.00 | 4.07 [4.02, 4.12] |
| LTT max-rule (clean) | 0.0000 [0.0000, 0.0000] | 0.00 | 0.000 [0.000, 0.000] | 0.000 | 1.00 | 4.07 [4.02, 4.12] |
| CRC pure (reused) | 0.0000 [0.0000, 0.0000] | 0.00 | 0.000 [0.000, 0.000] | 0.000 | 1.00 | 4.07 [4.02, 4.12] |
| CRC max-rule (reused) | 0.0000 [0.0000, 0.0000] | 0.00 | 0.000 [0.000, 0.000] | 0.000 | 1.00 | 4.07 [4.02, 4.12] |
| LTT pure (reused) | 0.0000 [0.0000, 0.0000] | 0.00 | 0.000 [0.000, 0.000] | 0.000 | 1.00 | 4.07 [4.02, 4.12] |

Binding: CRC constraint active (excludes an eligible calibration item) in 0.00 of splits; CRC stricter than plug-in 1.00; max-rule changes a test decision 0.00; pure CRC differs from plug-in on test 0.00; plug-in certified by the calibration bound (n R̂(λ_plug-in) + 1)/(n + 1) ≤ α in 1.00. CRC bound at λ̂: mean 0.0075; calibration bound at plug-in λ: mean 0.0075 [0.0075, 0.0075]. Plug-in λ mean 0.300 [0.30, 0.30].

Reused vs clean calibration (paired by split; reused − clean test wrong-commit):

| pair | mean diff [p05, p95] | reused higher | equal | Wilcoxon p | sign test (+/−) p | MDE80 (mean) |
|---|---|---|---|---|---|---|
| CRC pure (reused) - CRC pure (clean) | 0.0000 [0.0000, 0.0000] | 0.00 | 1.00 | 1 | 0/0 p 1 | 0.0000 |
| CRC max-rule (reused) - CRC max-rule (clean) | 0.0000 [0.0000, 0.0000] | 0.00 | 1.00 | 1 | 0/0 p 1 | 0.0000 |
| LTT pure (reused) - LTT pure (clean) | 0.0000 [0.0000, 0.0000] | 0.00 | 1.00 | 1 | 0/0 p 1 | 0.0000 |

Power: SD of the clean-CRC test rate over splits 0.0000; one deployment detects a shift of 0.0000 with 80 % power (one-sided 5 %); the mean over R splits resolves 0.0000 (Monte-Carlo).

Selective-risk controllers (target error among commits β; δ = 0.1; clean calibration):

| β | method | commit rate mean [p05, p95] | error among commits pooled | share EAC > β | no-commit splits | wrong-commit mean | eWPM mean |
|---|---|---|---|---|---|---|---|
| 0.05 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |
| 0.05 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |
| 0.05 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |
| 0.10 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |
| 0.10 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |
| 0.10 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |
| 0.20 | SGR | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |
| 0.20 | LTT-sel | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |
| 0.20 | joint (SGR + CRC max-rule) | 0.000 [0.000, 0.000] | — | 0.00 | 1.00 | 0.0000 | 4.07 |

## Main (full-fit) pipeline per day (committed arrays; the paper's trust row)

### b2t-ours

| day | n | trust wrong-commit | trust commit rate | trust eWPM | always offer eWPM | trust − always offer eWPM |
|---|---|---|---|---|---|---|
| 27 | 15 | 0.0000 | 0.000 | 10.21 | 10.21 | +0.00 |
| 34 | 50 | 0.0800 | 0.220 | 10.78 | 10.54 | +0.23 |
| 46 | 50 | 0.0400 | 0.180 | 10.64 | 10.45 | +0.20 |
| 48 | 58 | 0.0862 | 0.259 | 11.66 | 11.47 | +0.19 |
| 69 | 58 | 0.0000 | 0.207 | 11.33 | 11.04 | +0.29 |
| 74 | 37 | 0.0811 | 0.189 | 13.09 | 13.37 | -0.28 |
| 76 | 104 | 0.0769 | 0.163 | 10.00 | 9.87 | +0.14 |
| 81 | 69 | 0.0580 | 0.275 | 11.25 | 11.00 | +0.25 |
| 83 | 85 | 0.0824 | 0.282 | 9.91 | 9.78 | +0.12 |
| 88 | 45 | 0.0444 | 0.200 | 13.00 | 12.82 | +0.19 |
| 90 | 74 | 0.0405 | 0.284 | 13.67 | 13.30 | +0.37 |
| 95 | 25 | 0.0800 | 0.280 | 13.22 | 12.69 | +0.53 |
| 223 | 73 | 0.0548 | 0.288 | 12.21 | 12.14 | +0.07 |
| 244 | 73 | 0.0548 | 0.233 | 13.42 | 13.22 | +0.19 |

### b2t-published

| day | n | trust wrong-commit | trust commit rate | trust eWPM | always offer eWPM | trust − always offer eWPM |
|---|---|---|---|---|---|---|
| 27 | 15 | 0.0667 | 0.200 | 14.33 | 14.17 | +0.16 |
| 34 | 50 | 0.1800 | 0.480 | 12.37 | 12.18 | +0.19 |
| 46 | 50 | 0.0000 | 0.400 | 19.51 | 18.91 | +0.61 |
| 48 | 58 | 0.0517 | 0.448 | 18.71 | 18.12 | +0.58 |
| 69 | 58 | 0.0690 | 0.466 | 16.21 | 15.70 | +0.52 |
| 74 | 37 | 0.0000 | 0.378 | 23.41 | 22.61 | +0.79 |
| 76 | 104 | 0.0481 | 0.452 | 17.11 | 16.56 | +0.55 |
| 81 | 69 | 0.0435 | 0.449 | 19.33 | 18.68 | +0.65 |
| 83 | 85 | 0.0471 | 0.459 | 17.43 | 16.88 | +0.55 |
| 88 | 45 | 0.0444 | 0.489 | 20.30 | 19.05 | +1.25 |
| 90 | 74 | 0.0135 | 0.554 | 21.30 | 20.39 | +0.91 |
| 95 | 25 | 0.0000 | 0.680 | 24.58 | 23.03 | +1.55 |
| 223 | 73 | 0.0137 | 0.493 | 20.31 | 19.62 | +0.69 |
| 244 | 73 | 0.0411 | 0.534 | 23.28 | 22.21 | +1.07 |
