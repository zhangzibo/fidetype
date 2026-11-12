# Baselines and selective risk: generated tables

CI: 95 % percentile bootstrap, B = 2000, at the condition's unit (B2T: day clusters; sEMG: participant clusters; MEG: two-way sentences x participants). Wrong-commit = P(commit and wrong) over all items; error among commits = P(wrong | commit).

## b2t-ours (n test 816; CI unit cluster (day))

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits [CI] | silent error |
|---|---|---|---|---|---|
| always commit | 11.45 [10.69, 12.32] | 0.6103 [0.5692, 0.6484] | 1.000 | 0.610 [0.569, 0.648] | 0.0441 |
| never commit / always offer (refit) | 11.37 [10.66, 12.20] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| plain threshold, raw p_top1, no guard | 11.39 [10.61, 12.26] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| plain threshold, calibrated p_top1, no guard | 11.51 [10.77, 12.38] | 0.0355 [0.0250, 0.0469] | 0.165 | 0.215 [0.141, 0.309] | 0.0000 |
| trust (plug-in) | 11.55 [10.82, 12.38] | 0.0588 [0.0451, 0.0711] | 0.232 | 0.254 [0.194, 0.320] | 0.0025 |
| trust, fit-A pipeline (plug-in) | 11.48 [10.78, 12.28] | 0.0245 [0.0145, 0.0352] | 0.100 | 0.244 [0.160, 0.324] | 0.0012 |
| trust, fit-A + CRC (clean cal) | 11.48 [10.78, 12.28] | 0.0245 [0.0145, 0.0352] | 0.100 | 0.244 [0.160, 0.324] | 0.0012 |
| trust, fit-A + LTT (clean cal) | 11.48 [10.78, 12.30] | 0.0270 [0.0163, 0.0388] | 0.104 | 0.259 [0.176, 0.340] | 0.0012 |
| gaze typing only | 4.08 [4.05, 4.12] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Clean thresholds: CRC λ 0.3075, LTT λ 0.0000, fit-A plug-in λ 0.3000 (calibration n 401).

Paired differences (eWPM; wrong-commit):

- trust-always_commit: [-0.16, 0.33]; [-0.5843, -0.5148]
- trust-never_commit: [0.12, 0.24]; [0.0451, 0.0711]
- trust-gaze_only: [6.74, 8.30]; [0.0451, 0.0711]
- never_commit-gaze_only: [6.58, 8.12]; [0.0000, 0.0000]
- no_guard-trust: [-0.10, 0.04]; [-0.0356, -0.0109]
- crc-never_commit: [0.07, 0.16]; [0.0145, 0.0352]
- crc-trust: [-0.15, 0.02]; [-0.0480, -0.0199]
- always_commit-gaze_only: [6.61, 8.24]; [0.5692, 0.6484]

## b2t-published (n test 816; CI unit cluster (day))

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits [CI] | silent error |
|---|---|---|---|---|---|
| always commit | 19.61 [17.82, 21.35] | 0.1936 [0.1452, 0.2534] | 1.000 | 0.194 [0.145, 0.253] | 0.0245 |
| never commit / always offer (refit) | 18.11 [16.61, 19.61] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| plain threshold, raw p_top1, no guard | 18.68 [17.07, 20.28] | 0.0331 [0.0215, 0.0456] | 0.423 | 0.078 [0.049, 0.114] | 0.0012 |
| plain threshold, calibrated p_top1, no guard | 18.62 [17.03, 20.22] | 0.0245 [0.0137, 0.0387] | 0.381 | 0.064 [0.035, 0.104] | 0.0012 |
| trust (plug-in) | 18.77 [17.15, 20.40] | 0.0441 [0.0266, 0.0671] | 0.473 | 0.093 [0.055, 0.142] | 0.0037 |
| trust, fit-A pipeline (plug-in) | 18.79 [17.16, 20.44] | 0.0478 [0.0288, 0.0703] | 0.491 | 0.097 [0.058, 0.146] | 0.0049 |
| trust, fit-A + CRC (clean cal) | 18.79 [17.16, 20.44] | 0.0478 [0.0288, 0.0703] | 0.491 | 0.097 [0.058, 0.146] | 0.0049 |
| trust, fit-A + LTT (clean cal) | 18.65 [17.06, 20.26] | 0.0294 [0.0136, 0.0519] | 0.403 | 0.073 [0.034, 0.128] | 0.0012 |
| gaze typing only | 4.08 [4.05, 4.12] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Clean thresholds: CRC λ 0.6983, LTT λ 0.7600, fit-A plug-in λ 0.7000 (calibration n 401).

Paired differences (eWPM; wrong-commit):

- trust-always_commit: [-1.01, -0.67]; [-0.1871, -0.1137]
- trust-never_commit: [0.53, 0.80]; [0.0266, 0.0671]
- trust-gaze_only: [13.07, 16.34]; [0.0266, 0.0671]
- never_commit-gaze_only: [12.55, 15.54]; [0.0000, 0.0000]
- no_guard-trust: [-0.20, -0.10]; [-0.0336, -0.0055]
- crc-never_commit: [0.54, 0.83]; [0.0288, 0.0703]
- crc-trust: [0.01, 0.04]; [0.0000, 0.0072]
- always_commit-gaze_only: [13.76, 17.28]; [0.1452, 0.2534]

## emg-calib (n test 551; CI unit cluster (participant))

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits [CI] | silent error |
|---|---|---|---|---|---|
| always commit | 7.81 [6.68, 9.00] | 0.5408 [0.4682, 0.6225] | 1.000 | 0.541 [0.468, 0.623] | 0.0599 |
| never commit / always offer (refit) | 8.01 [6.96, 9.11] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| plain threshold, raw p_top1, no guard | 8.15 [7.05, 9.34] | 0.0454 [0.0324, 0.0565] | 0.283 | 0.160 [0.114, 0.217] | 0.0000 |
| plain threshold, calibrated p_top1, no guard | 8.02 [6.97, 9.13] | 0.0036 [0.0000, 0.0091] | 0.038 | 0.095 [0.000, 0.218] | 0.0000 |
| trust (plug-in) | 8.02 [6.97, 9.13] | 0.0036 [0.0000, 0.0091] | 0.038 | 0.095 [0.000, 0.218] | 0.0000 |
| trust, fit-A pipeline (plug-in) | 7.98 [6.96, 9.02] | 0.0036 [0.0000, 0.0091] | 0.038 | 0.095 [0.000, 0.218] | 0.0000 |
| trust, fit-A + CRC (clean cal) | 8.07 [7.03, 9.18] | 0.0399 [0.0244, 0.0545] | 0.241 | 0.165 [0.109, 0.229] | 0.0054 |
| trust, fit-A + LTT (clean cal) | 8.04 [7.01, 9.12] | 0.0218 [0.0091, 0.0363] | 0.183 | 0.119 [0.057, 0.184] | 0.0018 |
| gaze typing only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Clean thresholds: CRC λ 0.4480, LTT λ 0.4900, fit-A plug-in λ 0.7000 (calibration n 143).

Paired differences (eWPM; wrong-commit):

- trust-always_commit: [0.03, 0.41]; [-0.6199, -0.4632]
- trust-never_commit: [0.01, 0.03]; [0.0000, 0.0091]
- trust-gaze_only: [2.73, 4.84]; [0.0000, 0.0091]
- never_commit-gaze_only: [2.72, 4.82]; [0.0000, 0.0000]
- no_guard-trust: [0.00, 0.00]; [0.0000, 0.0000]
- crc-never_commit: [-0.01, 0.14]; [0.0244, 0.0545]
- crc-trust: [-0.03, 0.12]; [0.0218, 0.0508]
- always_commit-gaze_only: [2.44, 4.70]; [0.4682, 0.6225]

## emg-xsession (n test 551; CI unit cluster (participant))

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits [CI] | silent error |
|---|---|---|---|---|---|
| always commit | 4.10 [3.59, 4.73] | 0.8820 [0.8330, 0.9274] | 1.000 | 0.882 [0.833, 0.927] | 0.1488 |
| never commit / always offer (refit) | 4.67 [4.22, 5.25] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| plain threshold, raw p_top1, no guard | 4.75 [4.20, 5.51] | 0.0127 [0.0018, 0.0254] | 0.042 | 0.304 [0.050, 0.583] | 0.0036 |
| plain threshold, calibrated p_top1, no guard | 4.68 [4.22, 5.25] | 0.0036 [0.0000, 0.0091] | 0.018 | 0.200 [0.000, 0.500] | 0.0000 |
| trust (plug-in) | 4.68 [4.22, 5.25] | 0.0036 [0.0000, 0.0091] | 0.018 | 0.200 [0.000, 0.500] | 0.0000 |
| trust, fit-A pipeline (plug-in) | 4.68 [4.22, 5.25] | 0.0036 [0.0000, 0.0091] | 0.018 | 0.200 [0.000, 0.500] | 0.0000 |
| trust, fit-A + CRC (clean cal) | 4.66 [4.20, 5.25] | 0.0563 [0.0395, 0.0726] | 0.093 | 0.608 [0.500, 0.727] | 0.0073 |
| trust, fit-A + LTT (clean cal) | 4.67 [4.21, 5.24] | 0.0309 [0.0207, 0.0409] | 0.054 | 0.567 [0.454, 0.708] | 0.0054 |
| gaze typing only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Clean thresholds: CRC λ 0.2036, LTT λ 0.2300, fit-A plug-in λ 0.3000 (calibration n 143).

Paired differences (eWPM; wrong-commit):

- trust-always_commit: [0.46, 0.69]; [-0.9246, -0.8263]
- trust-never_commit: [-0.00, 0.01]; [0.0000, 0.0091]
- trust-gaze_only: [-0.05, 0.98]; [0.0000, 0.0091]
- never_commit-gaze_only: [-0.05, 0.98]; [0.0000, 0.0000]
- no_guard-trust: [0.00, 0.00]; [0.0000, 0.0000]
- crc-never_commit: [-0.04, 0.01]; [0.0395, 0.0726]
- crc-trust: [-0.04, 0.01]; [0.0376, 0.0682]
- always_commit-gaze_only: [-0.69, 0.45]; [0.8330, 0.9274]

## emg-xsubject (n test 551; CI unit cluster (participant))

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits [CI] | silent error |
|---|---|---|---|---|---|
| always commit | 3.53 [3.19, 3.92] | 0.9619 [0.9398, 0.9800] | 1.000 | 0.962 [0.940, 0.980] | 0.1670 |
| never commit / always offer (refit) | 4.08 [3.82, 4.38] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| plain threshold, raw p_top1, no guard | 4.76 [4.25, 5.44] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| plain threshold, calibrated p_top1, no guard | 4.08 [3.82, 4.38] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| trust (plug-in) | 4.08 [3.82, 4.38] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| trust, fit-A pipeline (plug-in) | 4.08 [3.82, 4.38] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| trust, fit-A + CRC (clean cal) | 4.08 [3.82, 4.38] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| trust, fit-A + LTT (clean cal) | 4.08 [3.82, 4.38] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| gaze typing only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Clean thresholds: CRC λ —, LTT λ 0.0000, fit-A plug-in λ 0.3000 (calibration n 143).

Paired differences (eWPM; wrong-commit):

- trust-always_commit: [0.44, 0.67]; [-0.9800, -0.9398]
- trust-never_commit: [0.00, 0.00]; [0.0000, 0.0000]
- trust-gaze_only: [-0.45, 0.10]; [0.0000, 0.0000]
- never_commit-gaze_only: [-0.45, 0.10]; [0.0000, 0.0000]
- no_guard-trust: [0.00, 0.00]; [0.0000, 0.0000]
- crc-never_commit: [0.00, 0.00]; [0.0000, 0.0000]
- crc-trust: [0.00, 0.00]; [0.0000, 0.0000]
- always_commit-gaze_only: [-1.08, -0.36]; [0.9398, 0.9800]

## meg-async (n test 637; CI unit two_way)

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits [CI] | silent error |
|---|---|---|---|---|---|
| always commit | 2.58 [2.31, 2.88] | 0.9969 [0.9857, 1.0000] | 1.000 | 0.997 [0.986, 1.000] | 0.2355 |
| never commit / always offer (refit) | 3.20 [3.02, 3.43] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| plain threshold, raw p_top1, no guard | 3.04 [2.88, 3.23] | 0.0047 [0.0000, 0.0166] | 0.006 | 0.750 [0.000, 1.000] | 0.0000 |
| plain threshold, calibrated p_top1, no guard | 3.20 [3.02, 3.43] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| trust (plug-in) | 3.20 [3.02, 3.43] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| trust, fit-A pipeline (plug-in) | 3.20 [3.02, 3.44] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| trust, fit-A + CRC (clean cal) | 3.20 [3.01, 3.42] | 0.0283 [0.0076, 0.0606] | 0.030 | 0.947 [0.750, 1.000] | 0.0047 |
| trust, fit-A + LTT (clean cal) | 3.20 [3.02, 3.44] | 0.0000 [0.0000, 0.0000] | 0.002 | 0.000 [0.000, 0.000] | 0.0000 |
| gaze typing only | 3.15 [3.02, 3.30] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Clean thresholds: CRC λ 0.1030, LTT λ 0.1100, fit-A plug-in λ 0.5000 (calibration n 199).

Paired differences (eWPM; wrong-commit):

- trust-always_commit: [0.45, 0.82]; [-1.0000, -0.9857]
- trust-never_commit: [0.00, 0.00]; [0.0000, 0.0000]
- trust-gaze_only: [-0.11, 0.26]; [0.0000, 0.0000]
- never_commit-gaze_only: [-0.11, 0.26]; [0.0000, 0.0000]
- no_guard-trust: [0.00, 0.00]; [0.0000, 0.0000]
- crc-never_commit: [-0.03, 0.01]; [0.0076, 0.0606]
- crc-trust: [-0.03, 0.01]; [0.0076, 0.0606]
- always_commit-gaze_only: [-0.86, -0.25]; [0.9857, 1.0000]
- (sentences) trust - gaze_only eWPM [-0.05, 0.15]; trust - never_commit [0.000, 0.000]
- (participants) trust - gaze_only eWPM [-0.08, 0.22]; trust - never_commit [0.000, 0.000]

## CRC / LTT selective risk in random calibration / test splits (committed item files, 200 splits)

| pool | n_cal | method | wrong-commit mean | commit rate mean | error among commits (pooled) | share of splits with no commit |
|---|---|---|---|---|---|---|
| b2t-ours (M2-13) | 100 | CRC | 0.0464 | 0.189 | 0.246 | 0.00 |
| b2t-ours (M2-13) | 100 | LTT | 0.0189 | 0.097 | 0.195 | 0.00 |
| b2t-ours (M2-13) | 408 | CRC | 0.0483 | 0.194 | 0.248 | 0.00 |
| b2t-ours (M2-13) | 408 | LTT | 0.0345 | 0.156 | 0.221 | 0.00 |
| b2t-published (M2-13) | 100 | CRC | 0.0461 | 0.464 | 0.099 | 0.00 |
| b2t-published (M2-13) | 100 | LTT | 0.0184 | 0.279 | 0.066 | 0.09 |
| b2t-published (M2-13) | 408 | CRC | 0.0485 | 0.483 | 0.100 | 0.00 |
| b2t-published (M2-13) | 408 | LTT | 0.0348 | 0.428 | 0.081 | 0.00 |
| meg-async (G1) | 100 | CRC | 0.0129 | 0.014 | 0.899 | 0.07 |
| meg-async (G1) | 100 | LTT | 0.0085 | 0.010 | 0.848 | 0.10 |
| meg-async (G1) | 408 | CRC | 0.0193 | 0.021 | 0.919 | 0.00 |
| meg-async (G1) | 408 | LTT | 0.0214 | 0.023 | 0.926 | 0.00 |
