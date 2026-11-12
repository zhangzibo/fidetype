# Toronto sEMG: generated tables

## Decoder (day-2 key presses, 27 classes)

Chance: majority (space) 0.338; uniform 0.037.

| run | n | acc | letters | space | balanced | top-5 | NLL | participant mean (min-max) |
|---|---|---|---|---|---|---|---|---|
| xsession | 14929 | 0.168 | 0.249 | 0.010 | 0.240 | 0.571 | 2.751 | 0.167 (0.059-0.248) |
| xsession_linear | 14929 | 0.162 | 0.177 | 0.132 | 0.175 | 0.525 | 2.944 | 0.161 (0.092-0.305) |
| xsession_permuted | 14929 | 0.022 | 0.034 | 0.000 | 0.032 | 0.137 | 3.313 | 0.022 (0.008-0.035) |
| calib | 14929 | 0.299 | 0.375 | 0.151 | 0.367 | 0.772 | 2.121 | 0.298 (0.171-0.454) |
| xsubject | 14929 | 0.209 | 0.228 | 0.172 | 0.226 | 0.672 | 2.833 | 0.208 (0.099-0.386) |

Zero input: xsession: argmax 'f' p 0.24; calib_a: argmax 'j' p 0.81; xsubject_f0: argmax 'k' p 0.55

## Trust harness (composed sentences; fit 570, test 551; user 75.8 chars/min)

### xsession: decoder trained on day 1 of all 19 participants; day-2 presses

LM weight 1.0 (fit-A CER {'0.5': 0.4989336625883938, '1.0': 0.38118756313839935, '1.5': 0.3967897631608486, '2.0': 0.4250757660792457, '3.0': 0.5211583791671344})

| policy | eWPM [sent] {participant} | wrong-commit [sent] | silent error | CER | WER | exact | truth in n-best | COMMIT / OFFER / ABSTAIN | CRC/LTT threshold (n) |
|---|---|---|---|---|---|---|---|---|---|
| a_greedy_commit | 3.28 [3.24, 3.32] {3.23, 3.32} | 1.000 [1.000, 1.000] | 0.054 | 0.801 | 1.000 | 0.000 | 0.00 | 1.00 / 0.00 / 0.00 |  |
| b_top1_commit | 4.10 [3.89, 4.34] {3.59, 4.70} | 0.882 [0.851, 0.907] | 0.149 | 0.398 | 0.579 | 0.118 | 0.21 | 1.00 / 0.00 / 0.00 |  |
| c_trust | 4.68 [4.52, 4.86] {4.21, 5.25} | 0.004 [0.000, 0.009] | 0.000 | 0.398 | 0.579 | 0.118 | 0.21 | 0.02 / 0.98 / 0.00 |  |
| c_crc | 4.68 [4.52, 4.86] {4.21, 5.25} | 0.004 [0.000, 0.009] | 0.000 | 0.398 | 0.579 | 0.118 | 0.21 | 0.02 / 0.98 / 0.00 | 0.204 (142, feasible True) |
| c_ltt | 4.68 [4.52, 4.86] {4.21, 5.25} | 0.004 [0.000, 0.009] | 0.000 | 0.398 | 0.579 | 0.118 | 0.21 | 0.02 / 0.98 / 0.00 | 0.230 (142, feasible True) |
| d_trust_no_calib | 4.75 [4.58, 4.95] {4.22, 5.48} | 0.013 [0.004, 0.022] | 0.004 | 0.387 | 0.577 | 0.156 | 0.24 | 0.04 / 0.96 / 0.00 |  |
| gaze typing only | 4.27 | 0 | 0 | | | | | | |

Paired differences (sentence CI; participant CI):

- c_trust-b_top1_commit:ewpm: [0.438, 0.715]; [0.464, 0.690]
- c_trust-b_top1_commit:wrong_commit_rate: [-0.906, -0.848]; [-0.925, -0.828]
- c_trust-b_top1_commit:silent_error_rate: [-0.180, -0.122]; [-0.189, -0.111]
- c_crc-b_top1_commit:ewpm: [0.438, 0.715]; [0.464, 0.690]
- c_crc-b_top1_commit:wrong_commit_rate: [-0.906, -0.848]; [-0.925, -0.828]
- c_crc-b_top1_commit:silent_error_rate: [-0.180, -0.122]; [-0.189, -0.111]
- c_ltt-b_top1_commit:ewpm: [0.438, 0.715]; [0.464, 0.690]
- c_ltt-b_top1_commit:wrong_commit_rate: [-0.906, -0.848]; [-0.925, -0.828]
- c_ltt-b_top1_commit:silent_error_rate: [-0.180, -0.122]; [-0.189, -0.111]
- c_trust-gaze_only:ewpm: [0.263, 0.564]; [-0.044, 0.964]
- c_trust-gaze_only:wrong_commit_rate: [0.000, 0.009]; [0.000, 0.009]
- c_trust-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_crc-gaze_only:ewpm: [0.263, 0.564]; [-0.044, 0.964]
- c_crc-gaze_only:wrong_commit_rate: [0.000, 0.009]; [0.000, 0.009]
- c_crc-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-gaze_only:ewpm: [0.263, 0.564]; [-0.044, 0.964]
- c_ltt-gaze_only:wrong_commit_rate: [0.000, 0.009]; [0.000, 0.009]
- c_ltt-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- b_top1_commit-gaze_only:ewpm: [-0.381, 0.050]; [-0.682, 0.420]
- b_top1_commit-gaze_only:wrong_commit_rate: [0.851, 0.907]; [0.835, 0.927]
- b_top1_commit-gaze_only:silent_error_rate: [0.122, 0.180]; [0.111, 0.189]
- c_crc-c_trust:ewpm: [0.000, 0.000]; [0.000, 0.000]
- c_crc-c_trust:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_crc-c_trust:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-c_trust:ewpm: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-c_trust:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-c_trust:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]

Calibration (trust policy c_trust): fit_temperature_frame 1.778, fit_temperature_sentence 5.421, ece_sentence_before 0.328, ece_sentence_after 0.072, ece_char_before 0.140, ece_char_after 0.021, p_top1_auroc 0.755, guard_auroc 0.555

Null audit (commit rate / wrong-commit rate):

| policy | real | other_sentence | frame_shuffled | zeros_input | permuted_label_decoder |
|---|---|---|---|---|---|
| b_top1_commit | 1.00 / 0.88 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| c_trust | 0.03 / 0.01 | 0.03 / 0.03 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| c_crc | 0.03 / 0.01 | 0.03 / 0.03 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| c_ltt | 0.03 / 0.01 | 0.03 / 0.03 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |

Examples (truth -> always-commit top-1):

- `it kept raining for a week` -> `it is the phone for a week`
- `is there anything to eat for sale here` -> `is there anything to be able to there`
- `yanni is young` -> `yanni is young`
- `i can do anything` -> `i can do anything`
- `i know tom is charming` -> `i know why is charming`
- `what have you been doing for the last three hours` -> `what have you get around for the last three hours`

### calib: day 1 + half of day 2 (cross-fitted: the other half is predicted)

LM weight 1.0 (fit-A CER {'0.5': 0.27208440902458186, '1.0': 0.19452239308564373, '1.5': 0.2205634751375014, '2.0': 0.27578852845437196, '3.0': 0.40262655741385117})

| policy | eWPM [sent] {participant} | wrong-commit [sent] | silent error | CER | WER | exact | truth in n-best | COMMIT / OFFER / ABSTAIN | CRC/LTT threshold (n) |
|---|---|---|---|---|---|---|---|---|---|
| a_greedy_commit | 3.09 [3.01, 3.16] {2.99, 3.17} | 1.000 [1.000, 1.000] | 0.094 | 0.619 | 0.989 | 0.000 | 0.00 | 1.00 / 0.00 / 0.00 |  |
| b_top1_commit | 7.81 [7.36, 8.30] {6.60, 9.01} | 0.541 [0.495, 0.583] | 0.060 | 0.123 | 0.214 | 0.459 | 0.64 | 1.00 / 0.00 / 0.00 |  |
| c_trust | 8.02 [7.63, 8.45] {6.90, 9.15} | 0.004 [0.000, 0.009] | 0.000 | 0.123 | 0.214 | 0.459 | 0.64 | 0.04 / 0.96 / 0.00 |  |
| c_crc | 7.98 [7.62, 8.38] {6.91, 9.03} | 0.004 [0.000, 0.009] | 0.000 | 0.123 | 0.214 | 0.459 | 0.64 | 0.04 / 0.96 / 0.00 | 0.448 (142, feasible True) |
| c_ltt | 7.98 [7.62, 8.38] {6.91, 9.03} | 0.004 [0.000, 0.009] | 0.000 | 0.123 | 0.214 | 0.459 | 0.64 | 0.04 / 0.96 / 0.00 | 0.490 (142, feasible True) |
| d_trust_no_calib | 8.15 [7.77, 8.59] {6.99, 9.32} | 0.045 [0.029, 0.064] | 0.000 | 0.116 | 0.212 | 0.461 | 0.63 | 0.28 / 0.72 / 0.00 |  |
| gaze typing only | 4.27 | 0 | 0 | | | | | | |

Paired differences (sentence CI; participant CI):

- c_trust-b_top1_commit:ewpm: [0.045, 0.379]; [0.013, 0.405]
- c_trust-b_top1_commit:wrong_commit_rate: [-0.579, -0.492]; [-0.625, -0.464]
- c_trust-b_top1_commit:silent_error_rate: [-0.080, -0.042]; [-0.090, -0.035]
- c_crc-b_top1_commit:ewpm: [-0.023, 0.363]; [-0.061, 0.390]
- c_crc-b_top1_commit:wrong_commit_rate: [-0.579, -0.492]; [-0.625, -0.464]
- c_crc-b_top1_commit:silent_error_rate: [-0.080, -0.042]; [-0.090, -0.035]
- c_ltt-b_top1_commit:ewpm: [-0.023, 0.363]; [-0.061, 0.390]
- c_ltt-b_top1_commit:wrong_commit_rate: [-0.579, -0.492]; [-0.625, -0.464]
- c_ltt-b_top1_commit:silent_error_rate: [-0.080, -0.042]; [-0.090, -0.035]
- c_trust-gaze_only:ewpm: [3.380, 4.157]; [2.660, 4.852]
- c_trust-gaze_only:wrong_commit_rate: [0.000, 0.009]; [0.000, 0.009]
- c_trust-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_crc-gaze_only:ewpm: [3.357, 4.099]; [2.657, 4.733]
- c_crc-gaze_only:wrong_commit_rate: [0.000, 0.009]; [0.000, 0.009]
- c_crc-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-gaze_only:ewpm: [3.357, 4.099]; [2.657, 4.733]
- c_ltt-gaze_only:wrong_commit_rate: [0.000, 0.009]; [0.000, 0.009]
- c_ltt-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- b_top1_commit-gaze_only:ewpm: [3.088, 4.020]; [2.376, 4.715]
- b_top1_commit-gaze_only:wrong_commit_rate: [0.495, 0.583]; [0.467, 0.628]
- b_top1_commit-gaze_only:silent_error_rate: [0.042, 0.080]; [0.035, 0.090]
- c_crc-c_trust:ewpm: [-0.128, 0.052]; [-0.136, 0.029]
- c_crc-c_trust:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_crc-c_trust:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-c_trust:ewpm: [-0.128, 0.052]; [-0.136, 0.029]
- c_ltt-c_trust:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-c_trust:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]

Calibration (trust policy c_trust): fit_temperature_frame 1.254, fit_temperature_sentence 2.424, ece_sentence_before 0.154, ece_sentence_after 0.148, ece_char_before 0.074, ece_char_after 0.021, p_top1_auroc 0.828, guard_auroc 0.647

Null audit (commit rate / wrong-commit rate):

| policy | real | other_sentence | frame_shuffled | zeros_input | permuted_label_decoder |
|---|---|---|---|---|---|
| b_top1_commit | 1.00 / 0.57 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| c_trust | 0.04 / 0.01 | 0.04 / 0.04 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| c_crc | 0.04 / 0.01 | 0.04 / 0.04 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| c_ltt | 0.04 / 0.01 | 0.04 / 0.04 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |

Examples (truth -> always-commit top-1):

- `it kept raining for a week` -> `i might raining for a week`
- `is there anything to eat for sale here` -> `is there anything to get forms of here`
- `yanni is young` -> `yanni is young`
- `i can do anything` -> `i can do anything`
- `i know tom is charming` -> `i know tom is charming`
- `what have you been doing for the last three hours` -> `what have you been doing for the last three hours`

### xsubject: 4-fold leave-participants-out; no data of the user

LM weight 1.5 (fit-A CER {'0.5': 0.5359748568862948, '1.0': 0.3883713099113256, '1.5': 0.38343248400493884, '2.0': 0.403187787630486, '3.0': 0.48871927264563925})

| policy | eWPM [sent] {participant} | wrong-commit [sent] | silent error | CER | WER | exact | truth in n-best | COMMIT / OFFER / ABSTAIN | CRC/LTT threshold (n) |
|---|---|---|---|---|---|---|---|---|---|
| a_greedy_commit | 3.02 [2.93, 3.10] {2.92, 3.13} | 1.000 [1.000, 1.000] | 0.118 | 0.761 | 0.999 | 0.000 | 0.00 | 1.00 / 0.00 / 0.00 |  |
| b_top1_commit | 3.53 [3.37, 3.72] {3.19, 3.88} | 0.962 [0.944, 0.976] | 0.167 | 0.479 | 0.681 | 0.038 | 0.08 | 1.00 / 0.00 / 0.00 |  |
| c_trust | 4.08 [3.98, 4.20] {3.83, 4.36} | 0.000 [0.000, 0.000] | 0.000 | 0.479 | 0.681 | 0.038 | 0.08 | 0.00 / 1.00 / 0.00 |  |
| c_crc | 4.08 [3.98, 4.20] {3.83, 4.36} | 0.000 [0.000, 0.000] | 0.000 | 0.479 | 0.681 | 0.038 | 0.08 | 0.00 / 1.00 / 0.00 | - (142, feasible True) |
| c_ltt | 4.08 [3.98, 4.20] {3.83, 4.36} | 0.000 [0.000, 0.000] | 0.000 | 0.479 | 0.681 | 0.038 | 0.08 | 0.00 / 1.00 / 0.00 | 0.000 (142, feasible True) |
| d_trust_no_calib | 4.76 [4.60, 4.94] {4.25, 5.35} | 0.005 [0.000, 0.013] | 0.000 | 0.369 | 0.562 | 0.116 | 0.20 | 0.01 / 0.99 / 0.00 |  |
| gaze typing only | 4.27 | 0 | 0 | | | | | | |

Paired differences (sentence CI; participant CI):

- c_trust-b_top1_commit:ewpm: [0.433, 0.671]; [0.441, 0.665]
- c_trust-b_top1_commit:wrong_commit_rate: [-0.976, -0.944]; [-0.979, -0.942]
- c_trust-b_top1_commit:silent_error_rate: [-0.198, -0.136]; [-0.203, -0.134]
- c_crc-b_top1_commit:ewpm: [0.433, 0.671]; [0.441, 0.665]
- c_crc-b_top1_commit:wrong_commit_rate: [-0.976, -0.944]; [-0.979, -0.942]
- c_crc-b_top1_commit:silent_error_rate: [-0.198, -0.136]; [-0.203, -0.134]
- c_ltt-b_top1_commit:ewpm: [0.433, 0.671]; [0.441, 0.665]
- c_ltt-b_top1_commit:wrong_commit_rate: [-0.976, -0.944]; [-0.979, -0.942]
- c_ltt-b_top1_commit:silent_error_rate: [-0.198, -0.136]; [-0.203, -0.134]
- c_trust-gaze_only:ewpm: [-0.281, -0.090]; [-0.427, 0.081]
- c_trust-gaze_only:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_trust-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_crc-gaze_only:ewpm: [-0.281, -0.090]; [-0.427, 0.081]
- c_crc-gaze_only:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_crc-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-gaze_only:ewpm: [-0.281, -0.090]; [-0.427, 0.081]
- c_ltt-gaze_only:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-gaze_only:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- b_top1_commit-gaze_only:ewpm: [-0.910, -0.571]; [-1.072, -0.397]
- b_top1_commit-gaze_only:wrong_commit_rate: [0.944, 0.976]; [0.942, 0.979]
- b_top1_commit-gaze_only:silent_error_rate: [0.136, 0.198]; [0.134, 0.203]
- c_crc-c_trust:ewpm: [0.000, 0.000]; [0.000, 0.000]
- c_crc-c_trust:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_crc-c_trust:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-c_trust:ewpm: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-c_trust:wrong_commit_rate: [0.000, 0.000]; [0.000, 0.000]
- c_ltt-c_trust:silent_error_rate: [0.000, 0.000]; [0.000, 0.000]

Calibration (trust policy c_trust): fit_temperature_frame 2.165, fit_temperature_sentence 20.000, ece_sentence_before 0.500, ece_sentence_after 0.083, ece_char_before 0.213, ece_char_after 0.022, p_top1_auroc 0.674, guard_auroc 0.497

Null audit (commit rate / wrong-commit rate):

| policy | real | other_sentence | frame_shuffled | zeros_input | permuted_label_decoder |
|---|---|---|---|---|---|
| b_top1_commit | 1.00 / 0.95 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| c_trust | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| c_crc | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| c_ltt | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |

Examples (truth -> always-commit top-1):

- `it kept raining for a week` -> `it is the united to be`
- `is there anything to eat for sale here` -> `we have anything to get to do that`
- `yanni is young` -> `do you thing`
- `i can do anything` -> `i can do anything`
- `i know tom is charming` -> `i know why isn t he`
- `what have you been doing for the last three hours` -> `what he think that he didn t have been life`

