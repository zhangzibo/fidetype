# Brain-to-Text '25 trust run: generated tables (run.py)

Trials: 1718 (125k-vocab: fit 812, test 816; 816 test sentences, fit/test sentence overlap 1). Greedy path == stored raw phonemes: 1709 / 1718.

## Published online decoder (Card et al.; from the pickle)

| group | n | WER | sentence exact | PER raw greedy | PER of published sentence |
|---|---|---|---|---|---|
| all_1718 | 1718 | 0.0434 | 0.810 | 0.0954 | 0.0266 |
| vocab_50 | 90 | 0.0025 | 0.989 | 0.0186 | 0.0012 |
| vocab_125k | 1628 | 0.0450 | 0.800 | 0.0982 | 0.0275 |
| fit | 812 | 0.0468 | 0.793 | 0.1030 | 0.0280 |
| test | 816 | 0.0431 | 0.806 | 0.0933 | 0.0269 |

| day | n | vocab | WER published | PER raw |
|---|---|---|---|---|
| 25 | 50 | [50] | 0.0044 | 0.0167 |
| 27 | 70 | [50, 125000] | 0.0508 | 0.0917 |
| 34 | 100 | [125000] | 0.1361 | 0.1289 |
| 46 | 99 | [125000] | 0.0461 | 0.0950 |
| 48 | 115 | [125000] | 0.0540 | 0.1170 |
| 69 | 115 | [125000] | 0.0615 | 0.1245 |
| 74 | 74 | [125000] | 0.0389 | 0.1017 |
| 76 | 208 | [125000] | 0.0460 | 0.1036 |
| 81 | 138 | [125000] | 0.0406 | 0.1058 |
| 83 | 169 | [125000] | 0.0437 | 0.1013 |
| 88 | 90 | [125000] | 0.0254 | 0.0693 |
| 90 | 148 | [125000] | 0.0325 | 0.0727 |
| 95 | 50 | [125000] | 0.0099 | 0.0776 |
| 223 | 146 | [125000] | 0.0310 | 0.0933 |
| 244 | 146 | [125000] | 0.0182 | 0.0733 |

## Word decoder tuning (400 fit trials; phoneme beam PER 0.1112, greedy PER 0.1122)

| lm_weight | edit_penalty | word_bonus | WER | sentence exact | truth in n-best |
|---|---|---|---|---|---|
| 0.5 | 4.0 | 3.0 | 0.1911 | 0.282 | 0.482 |
| 0.5 | 4.0 | 6.0 | 0.1911 | 0.282 | 0.482 |
| 0.5 | 8.0 | 3.0 | 0.1676 | 0.352 | 0.540 |
| 0.5 | 8.0 | 6.0 | 0.1676 | 0.352 | 0.540 |
| 0.5 | 12.0 | 3.0 | 0.1687 | 0.350 | 0.527 |
| 0.5 | 12.0 | 6.0 | 0.1687 | 0.350 | 0.527 |
| 1.0 | 4.0 | 3.0 | 0.2024 | 0.250 | 0.472 |
| 1.0 | 4.0 | 6.0 | 0.2028 | 0.247 | 0.472 |
| 1.0 | 8.0 | 3.0 | 0.1680 | 0.347 | 0.545 |
| 1.0 | 8.0 | 6.0 | 0.1684 | 0.345 | 0.545 |
| 1.0 | 12.0 | 3.0 **(best)** | 0.1665 | 0.362 | 0.542 |
| 1.0 | 12.0 | 6.0 | 0.1669 | 0.360 | 0.542 |

## word-level trust harness (test 816 trials; fit on 812)

Values: point [trial bootstrap 95% CI] {day-cluster bootstrap 95% CI}.

| policy | eWPM | wrong-commit | silent error | WER | CER | sentence exact | truth in n-best | COMMIT / OFFER / ASK / ABSTAIN |
|---|---|---|---|---|---|---|---|---|
| w_a_greedy_commit | 10.49 [10.01, 10.98] {9.84, 11.23} | 0.665 [0.634, 0.697] {0.622, 0.709} | 0.051 [0.038, 0.067] {0.036, 0.066} | 0.1715 | 0.1098 | 0.335 | 0.335 | 1.00 / 0.00 / 0.00 / 0.00 |
| w_p_published_commit | 19.61 [18.68, 20.51] {17.76, 21.45} | 0.194 [0.167, 0.222] {0.144, 0.259} | 0.025 [0.015, 0.036] {0.015, 0.034} | 0.0431 | 0.0309 | 0.806 | 0.806 | 1.00 / 0.00 / 0.00 / 0.00 |
| w_b_top1_commit | 11.45 [10.95, 12.04] {10.72, 12.32} | 0.610 [0.574, 0.645] {0.570, 0.646} | 0.044 [0.031, 0.059] {0.031, 0.057} | 0.1491 | 0.0953 | 0.390 | 0.623 | 1.00 / 0.00 / 0.00 / 0.00 |
| w_c_trust | 11.55 [11.03, 12.06] {10.85, 12.38} | 0.059 [0.043, 0.075] {0.045, 0.070} | 0.002 [0.000, 0.006] {0.000, 0.006} | 0.1491 | 0.0953 | 0.390 | 0.623 | 0.23 / 0.77 / 0.00 / 0.00 |
| w_d_trust_no_calib | 11.57 [11.04, 12.12] {10.79, 12.53} | 0.071 [0.054, 0.088] {0.058, 0.087} | 0.006 [0.001, 0.011] {0.002, 0.011} | 0.1454 | 0.0964 | 0.403 | 0.610 | 0.26 / 0.74 / 0.00 / 0.00 |
| w_e_trust_no_guard | 11.51 [11.00, 12.02] {10.81, 12.36} | 0.036 [0.023, 0.048] {0.025, 0.046} | 0.000 [0.000, 0.000] {0.000, 0.000} | 0.1491 | 0.0953 | 0.390 | 0.623 | 0.17 / 0.83 / 0.00 / 0.00 |
| w_q_published_trust | 18.77 [17.88, 19.62] {17.05, 20.46} | 0.044 [0.031, 0.059] {0.026, 0.069} | 0.004 [0.000, 0.009] {0.000, 0.008} | 0.0431 | 0.0309 | 0.806 | 0.843 | 0.47 / 0.53 / 0.00 / 0.00 |
| gaze_only | 4.08 [4.04, 4.12] {4.04, 4.12} | 0 | 0 | - | - | - | - | - |

| policy | T frame | T sentence | ECE token before | after | ECE sentence before | after | coverage | set size | guard AUROC | low-evidence AUROC | inconsistency AUROC | p_top1 AUROC | word-conf AUROC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| w_a_greedy_commit | 1.000 | 1.000 | 0.090 | 0.090 | 0.665 | 0.665 | 0.335 | 1.000 | 0.621 | 0.621 | 0.500 | 0.500 | - |
| w_p_published_commit | 1.000 | 1.000 | 0.090 | 0.090 | 0.194 | 0.194 | 0.806 | 1.000 | 0.500 | 0.366 | 0.500 | 0.500 | - |
| w_b_top1_commit | 3.781 | 4.555 | 0.090 | 0.130 | 0.448 | 0.067 | 0.559 | 3.403 | 0.702 | 0.701 | 0.715 | 0.797 | - |
| w_c_trust | 3.781 | 4.555 | 0.090 | 0.130 | 0.448 | 0.067 | 0.559 | 3.403 | 0.702 | 0.701 | 0.715 | 0.797 | 0.844 |
| w_d_trust_no_calib | 1.000 | 1.000 | 0.090 | 0.090 | 0.446 | 0.446 | 0.553 | 3.819 | 0.737 | 0.707 | 0.788 | 0.789 | - |
| w_e_trust_no_guard | 3.781 | 4.555 | 0.090 | 0.130 | 0.448 | 0.067 | 0.559 | 3.403 | 0.702 | 0.701 | 0.715 | 0.797 | - |
| w_q_published_trust | 3.781 | 1.717 | 0.090 | 0.130 | 0.102 | 0.058 | 0.766 | 0.935 | 0.667 | 0.667 | 0.737 | 0.710 | - |

| paired difference | trial CI | P(diff <= 0) | day CI |
|---|---|---|---|
| w_c_trust-w_b_top1_commit:ewpm | [-0.105, 0.303] | 0.180 | [-0.169, 0.334] |
| w_c_trust-w_b_top1_commit:wrong_commit_rate | [-0.587, -0.516] | 1.000 | [-0.585, -0.515] |
| w_c_trust-w_b_top1_commit:silent_error_rate | [-0.055, -0.029] | 1.000 | [-0.054, -0.029] |
| w_c_trust-w_p_published_commit:ewpm | [-8.912, -7.346] | 1.000 | [-9.287, -6.583] |
| w_c_trust-w_p_published_commit:wrong_commit_rate | [-0.169, -0.105] | 1.000 | [-0.196, -0.086] |
| w_c_trust-w_p_published_commit:silent_error_rate | [-0.033, -0.012] | 1.000 | [-0.031, -0.013] |
| w_c_trust-gaze_only:ewpm | [6.959, 7.974] | 0.000 | [6.784, 8.309] |
| w_c_trust-gaze_only:wrong_commit_rate | [0.043, 0.075] | 0.000 | [0.045, 0.070] |
| w_c_trust-gaze_only:silent_error_rate | [0.000, 0.006] | 0.121 | [0.000, 0.006] |
| w_q_published_trust-w_p_published_commit:ewpm | [-0.981, -0.720] | 1.000 | [-1.007, -0.677] |
| w_q_published_trust-w_p_published_commit:wrong_commit_rate | [-0.175, -0.126] | 1.000 | [-0.191, -0.114] |
| w_q_published_trust-w_p_published_commit:silent_error_rate | [-0.032, -0.011] | 1.000 | [-0.029, -0.012] |
| w_q_published_trust-gaze_only:ewpm | [13.809, 15.532] | 0.000 | [12.958, 16.400] |
| w_q_published_trust-gaze_only:wrong_commit_rate | [0.031, 0.059] | 0.000 | [0.026, 0.069] |
| w_q_published_trust-gaze_only:silent_error_rate | [0.000, 0.009] | 0.048 | [0.000, 0.008] |
| w_p_published_commit-gaze_only:ewpm | [14.611, 16.425] | 0.000 | [13.685, 17.383] |
| w_p_published_commit-gaze_only:wrong_commit_rate | [0.167, 0.222] | 0.000 | [0.144, 0.259] |
| w_p_published_commit-gaze_only:silent_error_rate | [0.015, 0.036] | 0.000 | [0.015, 0.034] |
| w_b_top1_commit-gaze_only:ewpm | [6.887, 7.949] | 0.000 | [6.640, 8.234] |
| w_b_top1_commit-gaze_only:wrong_commit_rate | [0.574, 0.645] | 0.000 | [0.570, 0.646] |
| w_b_top1_commit-gaze_only:silent_error_rate | [0.031, 0.059] | 0.000 | [0.031, 0.057] |

Our risk vs 'published sentence wrong' (test): AUROC risk 0.661, -p_top1 0.662.

| coverage (highest our p_top1 first) | published WER | published sentence error |
|---|---|---|
| 0.5 | 0.0261 | 0.130 |
| 0.7 | 0.0285 | 0.137 |
| 0.8 | 0.0326 | 0.155 |
| 0.9 | 0.0391 | 0.176 |
| 1.0 | 0.0431 | 0.194 |

| day | WER our top-1 (test) |
|---|---|
| 27 | 0.2500 |
| 34 | 0.1719 |
| 46 | 0.1678 |
| 48 | 0.1592 |
| 69 | 0.1571 |
| 74 | 0.1282 |
| 76 | 0.1904 |
| 81 | 0.1620 |
| 83 | 0.1797 |
| 88 | 0.1116 |
| 90 | 0.1224 |
| 95 | 0.1032 |
| 223 | 0.1135 |
| 244 | 0.1072 |

## Null-input audit (word level, test streams)

| policy | input | fluent top-1 | COMMIT | fluent and committed | wrong commit |
|---|---|---|---|---|---|
| w_b_top1_commit | real | 1.000 | 1.000 | 1.000 | 0.637 |
| w_b_top1_commit | other_trial | 1.000 | 1.000 | 1.000 | 1.000 |
| w_b_top1_commit | frame_shuffled | 1.000 | 1.000 | 1.000 | 1.000 |
| w_b_top1_commit | uniform | 0.093 | 1.000 | 0.093 | 1.000 |
| w_b_top1_commit | risk AUROC null vs real | other_trial 0.500, frame_shuffled 0.981, uniform 0.998 | | | |
| w_c_trust | real | 1.000 | 0.217 | 0.217 | 0.073 |
| w_c_trust | other_trial | 1.000 | 0.217 | 0.217 | 0.217 |
| w_c_trust | frame_shuffled | 1.000 | 0.000 | 0.000 | 0.000 |
| w_c_trust | uniform | 0.093 | 0.000 | 0.000 | 0.000 |
| w_c_trust | risk AUROC null vs real | other_trial 0.500, frame_shuffled 0.981, uniform 0.998 | | | |
| w_d_trust_no_calib | real | 1.000 | 0.247 | 0.247 | 0.083 |
| w_d_trust_no_calib | other_trial | 1.000 | 0.247 | 0.247 | 0.247 |
| w_d_trust_no_calib | frame_shuffled | 1.000 | 0.000 | 0.000 | 0.000 |
| w_d_trust_no_calib | uniform | 0.110 | 0.000 | 0.000 | 0.000 |
| w_d_trust_no_calib | risk AUROC null vs real | other_trial 0.500, frame_shuffled 0.987, uniform 0.998 | | | |
| w_q_published_trust | real | 1.000 | 0.483 | 0.483 | 0.053 |
| w_q_published_trust | other_trial | 1.000 | 0.000 | 0.000 | 0.000 |
| w_q_published_trust | frame_shuffled | 1.000 | 0.000 | 0.000 | 0.000 |
| w_q_published_trust | uniform | 1.000 | 0.000 | 0.000 | 0.000 |
| w_q_published_trust | risk AUROC null vs real | other_trial 0.994, frame_shuffled 0.996, uniform 0.997 | | | |

## phoneme-level trust harness (test 816 trials; fit on 812)

Values: point [trial bootstrap 95% CI] {day-cluster bootstrap 95% CI}.

| policy | eWPM | wrong-commit | silent error | WER | CER | sentence exact | truth in n-best | COMMIT / OFFER / ASK / ABSTAIN |
|---|---|---|---|---|---|---|---|---|
| p_a_greedy_commit | 10.16 [9.67, 10.62] {9.59, 10.79} | 0.756 [0.725, 0.787] {0.721, 0.797} | 0.064 [0.048, 0.082] {0.054, 0.076} | 0.2128 | 0.0968 | 0.244 | 0.244 | 1.00 / 0.00 / 0.00 / 0.00 |
| p_b_top1_commit | 10.21 [9.75, 10.68] {9.66, 10.86} | 0.754 [0.722, 0.784] {0.716, 0.792} | 0.062 [0.047, 0.081] {0.052, 0.075} | 0.2109 | 0.0943 | 0.246 | 0.429 | 1.00 / 0.00 / 0.00 / 0.00 |
| p_c_trust | 10.20 [9.80, 10.61] {9.60, 10.85} | 0.054 [0.039, 0.069] {0.038, 0.070} | 0.002 [0.000, 0.006] {0.000, 0.006} | 0.2109 | 0.0943 | 0.246 | 0.429 | 0.19 / 0.81 / 0.00 / 0.00 |
| gaze_only | 4.82 [4.77, 4.87] {4.77, 4.88} | 0 | 0 | - | - | - | - | - |

| policy | T frame | T sentence | ECE token before | after | ECE sentence before | after | coverage | set size | guard AUROC | low-evidence AUROC | inconsistency AUROC | p_top1 AUROC | word-conf AUROC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p_a_greedy_commit | 1.000 | 1.000 | 0.090 | 0.090 | 0.756 | 0.756 | 0.244 | 1.000 | 0.602 | 0.602 | 0.500 | 0.500 | - |
| p_b_top1_commit | 3.781 | 0.948 | 0.090 | 0.130 | 0.129 | 0.124 | 0.374 | 5.515 | 0.825 | 0.842 | 0.752 | 0.884 | - |
| p_c_trust | 3.781 | 0.948 | 0.090 | 0.130 | 0.129 | 0.124 | 0.374 | 5.515 | 0.825 | 0.842 | 0.752 | 0.884 | - |

| paired difference | trial CI | P(diff <= 0) | day CI |
|---|---|---|---|
