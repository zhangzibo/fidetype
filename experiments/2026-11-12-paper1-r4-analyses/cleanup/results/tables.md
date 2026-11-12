# Clean-up numbers: tables

## 1. MEG Tab. 1 CIs

| source | policy | eWPM | 95 % CI |
|---|---|---|---|
| unified_two_way | trust | 3.203 | [3.015, 3.439] |
| unified_two_way | never_commit | 3.203 | [3.015, 3.439] |
| unified_two_way | gaze_only | 3.155 | [3.025, 3.305] |
| unified_two_way | always_commit | 2.580 | [2.313, 2.879] |
| printed_in_v3_tab1 | trust | — | [3.02, 3.44] |
| printed_in_v3_tab1 | gaze_only | — | [3.03, 3.31] |
| teaser_figure_source_G1_sentence_bootstrap | commit | 2.580 | [2.414, 2.763] |
| teaser_figure_source_G1_sentence_bootstrap | trust | 3.203 | [3.069, 3.359] |

## 2. Exact Clopper-Pearson bounds

| count | what | one-sided 95 % upper | two-sided 95 % | rule of three |
|---|---|---|---|---|
| 0/816 | B2T test set (fixed), zero wrong commits | 0.0037 | [0.0000, 0.0045] | 0.0037 |
| 0/551 | sEMG test set, zero wrong commits | 0.0054 | [0.0000, 0.0067] | 0.0054 |
| 0/637 | MEG test instances / MEG controls | 0.0047 | [0.0000, 0.0058] | 0.0047 |
| 0/300 | B2T controls per control stream | 0.0099 | [0.0000, 0.0122] | 0.0100 |
| 0/200 | sEMG controls per condition | 0.0149 | [0.0000, 0.0183] | 0.0150 |
| 0/256 | sEMG non-templated sentences | 0.0116 | [0.0000, 0.0143] | 0.0117 |
| 1/256 | sEMG non-templated, session-calibrated (1 wrong commit) | 0.0184 | [0.0001, 0.0216] | — |
| 2/551 | sEMG session-cal. / cross-session (2 wrong commits) | 0.0114 | [0.0004, 0.0130] | — |
| 4/50 | LTT max, B2T ours: splits above alpha | 0.1738 | [0.0222, 0.1923] | — |
| 1/50 | LTT max, B2T published: splits above alpha | 0.0914 | [0.0005, 0.1065] | — |
| 7/50 | CRC max, B2T ours/published: splits above alpha | 0.2469 | [0.0582, 0.2674] | — |

## 3. Frame-temperature snapping

| condition | R | max |ΔT| | max relative change (%) |
|---|---|---|---|
| R3 b2t-ours | 50 | 0.0094 | 0.267 |
| R3 b2t-published | 50 | 0.0094 | 0.267 |
| R3 emg-calib | 50 | 0.0049 | 0.384 |
| R3 emg-xsession | 50 | 0.0049 | 0.275 |
| R3 emg-xsubject | 50 | 0.0049 | 0.227 |
| R4 b2t-ours guard 1 | 200 | 0.0100 | 0.283 |
| R4 b2t-ours guard 0 | 200 | 0.0100 | 0.283 |
| R4 b2t-published guard 0 | 200 | 0.0100 | 0.283 |
| R4 emg-calib guard 0 | 50 | 0.0049 | 0.384 |
| R4 emg-xsession guard 0 | 50 | 0.0049 | 0.275 |
| R4 emg-xsubject guard 0 | 50 | 0.0049 | 0.227 |

## 4. Comparator: the same fitted policy without commits (λ = +∞)

Definition: the same fit-A pipeline and policy with the commit threshold set to +∞, so no trial is committed and every trial takes the policy's non-commit path (offer the n-best / alternatives, else retype). Gain = eWPM(rule) − eWPM(no commit), paired by split.

| condition / guard / R | no-commit eWPM | rule | gain mean (MC SE) | p05–p95 over splits | share > 0 / < 0 |
|---|---|---|---|---|---|
| b2t-ours/guard/R200 | 10.99 | LTT max | +0.111 (0.002) | +0.061 – +0.168 | 1.00 / 0.00 |
| b2t-ours/guard/R200 | 10.99 | CRC max | +0.118 (0.002) | +0.063 – +0.172 | 1.00 / 0.00 |
| b2t-ours/guard/R200 | 10.99 | plug-in | +0.122 (0.003) | +0.062 – +0.183 | 1.00 / 0.00 |
| b2t-ours/guard/R200 | 10.99 | joint LTT b0.10 | +0.000 (0.000) | +0.000 – +0.000 | 0.00 / 0.00 |
| b2t-ours/guard/R50 | 10.95 | LTT max | +0.114 (0.005) | +0.063 – +0.164 | 1.00 / 0.00 |
| b2t-ours/guard/R50 | 10.95 | CRC max | +0.125 (0.005) | +0.077 – +0.182 | 1.00 / 0.00 |
| b2t-ours/guard/R50 | 10.95 | plug-in | +0.132 (0.005) | +0.075 – +0.184 | 1.00 / 0.00 |
| b2t-ours/guard/R50 | 10.95 | joint LTT b0.10 | +0.000 (0.000) | +0.000 – +0.000 | 0.00 / 0.00 |
| b2t-ours/no guard/R200 | 10.98 | LTT max | +0.104 (0.002) | +0.062 – +0.155 | 1.00 / 0.00 |
| b2t-ours/no guard/R200 | 10.98 | CRC max | +0.111 (0.002) | +0.065 – +0.165 | 1.00 / 0.00 |
| b2t-ours/no guard/R200 | 10.98 | plug-in | +0.112 (0.002) | +0.065 – +0.173 | 1.00 / 0.00 |
| b2t-ours/no guard/R200 | 10.98 | joint LTT b0.10 | +0.000 (0.000) | +0.000 – +0.000 | 0.00 / 0.00 |
| b2t-ours/no guard/R50 | 10.95 | LTT max | +0.106 (0.005) | +0.063 – +0.166 | 1.00 / 0.00 |
| b2t-ours/no guard/R50 | 10.95 | CRC max | +0.116 (0.005) | +0.067 – +0.174 | 1.00 / 0.00 |
| b2t-ours/no guard/R50 | 10.95 | plug-in | +0.120 (0.005) | +0.072 – +0.180 | 1.00 / 0.00 |
| b2t-ours/no guard/R50 | 10.95 | joint LTT b0.10 | +0.000 (0.000) | +0.000 – +0.000 | 0.00 / 0.00 |
| b2t-published/guard/R200 | 18.00 | LTT max | +0.514 (0.004) | +0.434 – +0.608 | 1.00 / 0.00 |
| b2t-published/guard/R200 | 18.00 | CRC max | +0.553 (0.005) | +0.452 – +0.656 | 1.00 / 0.00 |
| b2t-published/guard/R200 | 18.00 | plug-in | +0.571 (0.005) | +0.452 – +0.687 | 1.00 / 0.00 |
| b2t-published/guard/R200 | 18.00 | joint LTT b0.10 | +0.093 (0.012) | +0.000 – +0.438 | 0.24 / 0.00 |
| b2t-published/guard/R50 | 17.98 | LTT max | +0.510 (0.007) | +0.439 – +0.599 | 1.00 / 0.00 |
| b2t-published/guard/R50 | 17.98 | CRC max | +0.546 (0.009) | +0.462 – +0.648 | 1.00 / 0.00 |
| b2t-published/guard/R50 | 17.98 | plug-in | +0.564 (0.010) | +0.462 – +0.674 | 1.00 / 0.00 |
| b2t-published/guard/R50 | 17.98 | joint LTT b0.10 | +0.093 (0.024) | +0.000 – +0.432 | 0.24 / 0.00 |
| b2t-published/no guard/R200 | 18.00 | LTT max | +0.477 (0.003) | +0.428 – +0.537 | 1.00 / 0.00 |
| b2t-published/no guard/R200 | 18.00 | CRC max | +0.484 (0.003) | +0.429 – +0.615 | 1.00 / 0.00 |
| b2t-published/no guard/R200 | 18.00 | plug-in | +0.486 (0.004) | +0.429 – +0.628 | 1.00 / 0.00 |
| b2t-published/no guard/R200 | 18.00 | joint LTT b0.10 | +0.076 (0.012) | +0.000 – +0.473 | 0.19 / 0.00 |
| b2t-published/no guard/R50 | 17.98 | LTT max | +0.471 (0.003) | +0.435 – +0.500 | 1.00 / 0.00 |
| b2t-published/no guard/R50 | 17.98 | CRC max | +0.471 (0.003) | +0.435 – +0.500 | 1.00 / 0.00 |
| b2t-published/no guard/R50 | 17.98 | plug-in | +0.471 (0.003) | +0.435 – +0.500 | 1.00 / 0.00 |
| b2t-published/no guard/R50 | 17.98 | joint LTT b0.10 | +0.070 (0.023) | +0.000 – +0.475 | 0.16 / 0.00 |
| emg-calib/guard/R50 | 7.97 | LTT max | +0.033 (0.002) | +0.011 – +0.056 | 0.96 / 0.02 |
| emg-calib/guard/R50 | 7.97 | CRC max | +0.037 (0.002) | +0.011 – +0.062 | 0.96 / 0.02 |
| emg-calib/guard/R50 | 7.97 | plug-in | +0.040 (0.003) | +0.011 – +0.084 | 0.96 / 0.02 |
| emg-calib/guard/R50 | 7.97 | joint LTT b0.10 | +0.000 (0.000) | +0.000 – +0.000 | 0.00 / 0.00 |
| emg-calib/no guard/R50 | 7.97 | LTT max | +0.033 (0.002) | +0.011 – +0.056 | 0.98 / 0.02 |
| emg-calib/no guard/R50 | 7.97 | CRC max | +0.037 (0.002) | +0.011 – +0.062 | 0.98 / 0.02 |
| emg-calib/no guard/R50 | 7.97 | plug-in | +0.040 (0.003) | +0.011 – +0.084 | 0.98 / 0.02 |
| emg-calib/no guard/R50 | 7.97 | joint LTT b0.10 | +0.000 (0.000) | +0.000 – +0.000 | 0.00 / 0.00 |
| emg-xsession/guard/R50 | 4.68 | LTT max | -0.001 (0.001) | -0.007 – +0.004 | 0.42 / 0.24 |
| emg-xsession/guard/R50 | 4.68 | CRC max | -0.001 (0.001) | -0.008 – +0.004 | 0.42 / 0.24 |
| emg-xsession/guard/R50 | 4.68 | plug-in | -0.001 (0.001) | -0.011 – +0.004 | 0.40 / 0.26 |
| emg-xsession/guard/R50 | 4.68 | joint LTT b0.10 | +0.000 (0.000) | +0.000 – +0.000 | 0.00 / 0.00 |
| emg-xsession/no guard/R50 | 4.68 | LTT max | -0.001 (0.001) | -0.007 – +0.004 | 0.42 / 0.26 |
| emg-xsession/no guard/R50 | 4.68 | CRC max | -0.001 (0.001) | -0.008 – +0.004 | 0.42 / 0.26 |
| emg-xsession/no guard/R50 | 4.68 | plug-in | -0.001 (0.001) | -0.011 – +0.004 | 0.40 / 0.28 |
| emg-xsession/no guard/R50 | 4.68 | joint LTT b0.10 | +0.000 (0.000) | +0.000 – +0.000 | 0.00 / 0.00 |

Check against v3 (β = 0.05 selective controllers as the no-commit row): {"b2t-ours": {"v3 LTT max - no commit": 0.1143912106951538, "r4 LTT max - no commit": 0.1143912106951538}, "b2t-published": {"v3 LTT max - no commit": 0.5096723064459421, "r4 LTT max - no commit": 0.5096723064459421}}

Fixed splits (paired day-cluster bootstrap, unified seed):

| split | rule | eWPM | no commit | gain [95 % CI] |
|---|---|---|---|---|
| b2t-ours/split A | LTT max | 11.48 | 11.42 | +0.058 [0.034, 0.090] |
| b2t-ours/split A | CRC max | 11.48 | 11.42 | +0.058 [0.034, 0.090] |
| b2t-ours/split A | plug-in | 11.48 | 11.42 | +0.058 [0.034, 0.090] |
| b2t-ours/split A | joint LTT b0.10 | 11.42 | 11.42 | +0.000 [0.000, 0.000] |
| b2t-ours/split B | LTT max | 11.54 | 11.41 | +0.125 [0.077, 0.188] |
| b2t-ours/split B | CRC max | 11.54 | 11.41 | +0.129 [0.082, 0.197] |
| b2t-ours/split B | plug-in | 11.55 | 11.41 | +0.138 [0.089, 0.208] |
| b2t-ours/split B | joint LTT b0.10 | 11.41 | 11.41 | +0.000 [0.000, 0.000] |
| b2t-published/split A | LTT max | 18.65 | 18.11 | +0.537 [0.439, 0.636] |
| b2t-published/split A | CRC max | 18.79 | 18.11 | +0.678 [0.538, 0.831] |
| b2t-published/split A | plug-in | 18.79 | 18.11 | +0.678 [0.538, 0.831] |
| b2t-published/split A | joint LTT b0.10 | 18.11 | 18.11 | +0.000 [0.000, 0.000] |
| b2t-published/split B | LTT max | 18.68 | 18.11 | +0.567 [0.456, 0.694] |
| b2t-published/split B | CRC max | 18.78 | 18.11 | +0.670 [0.536, 0.826] |
| b2t-published/split B | plug-in | 18.78 | 18.11 | +0.670 [0.536, 0.826] |
| b2t-published/split B | joint LTT b0.10 | 18.11 | 18.11 | +0.000 [0.000, 0.000] |

## 5. Trust vs always commit in the 9 user-model variants

| condition | variant | always commit | trust | trust − always commit [CI] | fastest | always commit faster than trust |
|---|---|---|---|---|---|---|
| emg-calib | main | 7.81 | 8.02 | +0.22 [0.02, 0.39] | trust | no |
| emg-calib | fallback 10 cpm | 5.76 | 6.24 | +0.49 [0.32, 0.68] | trust | no |
| emg-calib | fallback 40 cpm | 9.57 | 9.63 | +0.06 [-0.16, 0.29] | trust | no |
| emg-calib | selection x0.5 | 8.13 | 8.45 | +0.32 [0.13, 0.50] | trust | no |
| emg-calib | selection x2 | 7.32 | 7.38 | +0.06 [-0.14, 0.25] | trust | no |
| emg-calib | p_miss 0 | 8.11 | 8.09 | -0.02 [-0.14, 0.12] | always_commit | yes |
| emg-calib | p_miss 0.2 | 6.90 | 8.02 | +1.13 [0.83, 1.42] | trust | no |
| emg-calib | symmetric offer (p_miss 0.05, no oracle retype) | 7.80 | 7.82 | +0.02 [-0.14, 0.19] | trust | no |
| emg-calib | symmetric offer, p_miss 0.2 | 6.90 | 7.16 | +0.26 [0.08, 0.45] | trust | no |
| emg-xsession | main | 4.10 | 4.68 | +0.57 [0.46, 0.69] | gaze_lm | no |
| emg-xsession | fallback 10 cpm | 2.63 | 3.09 | +0.46 [0.38, 0.54] | gaze_lm | no |
| emg-xsession | fallback 40 cpm | 6.02 | 6.58 | +0.56 [0.38, 0.72] | gaze_lm | no |
| emg-xsession | selection x0.5 | 4.34 | 5.00 | +0.66 [0.54, 0.78] | gaze_lm | no |
| emg-xsession | selection x2 | 3.99 | 4.29 | +0.30 [0.18, 0.42] | gaze_lm | no |
| emg-xsession | p_miss 0 | 4.72 | 4.68 | -0.05 [-0.10, 0.02] | gaze_lm | yes |
| emg-xsession | p_miss 0.2 | 2.69 | 4.67 | +1.98 [1.78, 2.17] | gaze_lm | no |
| emg-xsession | symmetric offer (p_miss 0.05, no oracle retype) | 4.06 | 4.05 | -0.01 [-0.06, 0.05] | gaze_lm | yes |
| emg-xsession | symmetric offer, p_miss 0.2 | 2.67 | 3.39 | +0.72 [0.04, 1.27] | gaze_lm | no |
| emg-xsubject | main | 3.53 | 4.08 | +0.55 [0.43, 0.66] | gaze_lm | no |
| emg-xsubject | fallback 10 cpm | 2.21 | 2.60 | +0.39 [0.33, 0.46] | gaze_lm | no |
| emg-xsubject | fallback 40 cpm | 5.45 | 6.01 | +0.57 [0.45, 0.68] | gaze_lm | no |
| emg-xsubject | selection x0.5 | 3.74 | 4.36 | +0.62 [0.50, 0.74] | gaze_lm | no |
| emg-xsubject | selection x2 | 3.52 | 3.80 | +0.28 [0.21, 0.34] | gaze_lm | no |
| emg-xsubject | p_miss 0 | 4.14 | 4.08 | -0.06 [-0.07, -0.06] | gaze_lm | yes |
| emg-xsubject | p_miss 0.2 | 1.98 | 4.08 | +2.10 [1.95, 2.26] | gaze_lm | no |
| emg-xsubject | symmetric offer (p_miss 0.05, no oracle retype) | 3.50 | 3.45 | -0.04 [-0.07, -0.01] | gaze_lm | yes |
| emg-xsubject | symmetric offer, p_miss 0.2 | 1.96 | 3.33 | +1.37 [0.98, 1.73] | gaze_lm | no |
| b2t-ours | main | 11.45 | 11.55 | +0.10 [-0.14, 0.33] | trust | no |
| b2t-ours | fallback 10 cpm | 7.79 | 8.28 | +0.50 [0.35, 0.64] | trust | no |
| b2t-ours | fallback 40 cpm | 14.97 | 14.65 | -0.32 [-0.43, -0.18] | always_commit | yes |
| b2t-ours | selection x0.5 | 11.96 | 12.24 | +0.28 [0.03, 0.53] | trust | no |
| b2t-ours | selection x2 | 10.55 | 10.37 | -0.18 [-0.40, 0.04] | always_commit | yes |
| b2t-ours | p_miss 0 | 11.65 | 11.54 | -0.11 [-0.30, 0.06] | always_commit | yes |
| b2t-ours | p_miss 0.2 | 10.77 | 11.52 | +0.74 [0.47, 1.05] | trust | no |
| b2t-ours | symmetric offer (p_miss 0.05, no oracle retype) | 11.45 | 11.36 | -0.09 [-0.29, 0.09] | always_commit | yes |
| b2t-ours | symmetric offer, p_miss 0.2 | 10.77 | 10.77 | -0.00 [-0.24, 0.25] | always_commit | yes |
| b2t-published | main | 19.61 | 18.77 | -0.85 [-1.01, -0.66] | always_commit | yes |
| b2t-published | fallback 10 cpm | 16.12 | 15.36 | -0.76 [-1.02, -0.52] | always_commit | yes |
| b2t-published | fallback 40 cpm | 21.99 | 21.12 | -0.88 [-1.00, -0.74] | always_commit | yes |
| b2t-published | selection x0.5 | 20.00 | 19.54 | -0.46 [-0.59, -0.32] | always_commit | yes |
| b2t-published | selection x2 | 18.87 | 17.40 | -1.47 [-1.72, -1.20] | always_commit | yes |
| b2t-published | p_miss 0 | 19.52 | 18.75 | -0.77 [-0.87, -0.67] | always_commit | yes |
| b2t-published | p_miss 0.2 | 19.69 | 18.72 | -0.96 [-1.21, -0.63] | always_commit | yes |
| b2t-published | symmetric offer (p_miss 0.05, no oracle retype) | 19.61 | 18.82 | -0.79 [-0.90, -0.68] | always_commit | yes |
| b2t-published | symmetric offer, p_miss 0.2 | 19.69 | 18.86 | -0.83 [-0.94, -0.72] | always_commit | yes |
| meg-async | main | 2.58 | 3.20 | +0.62 [0.45, 0.83] | gaze_lm | no |
| meg-async | fallback 10 cpm | 1.51 | 1.89 | +0.38 [0.28, 0.50] | gaze_lm | no |
| meg-async | fallback 40 cpm | 4.31 | 5.15 | +0.84 [0.59, 1.12] | gaze_lm | no |
| meg-async | selection x0.5 | 2.74 | 3.45 | +0.71 [0.52, 0.93] | gaze_lm | no |
| meg-async | selection x2 | 2.54 | 2.96 | +0.42 [0.28, 0.58] | gaze_lm | no |
| meg-async | p_miss 0 | 3.24 | 3.20 | -0.04 [-0.05, -0.04] | gaze_lm | yes |
| meg-async | p_miss 0.2 | 1.24 | 3.20 | +1.97 [1.75, 2.20] | gaze_lm | no |
| meg-async | symmetric offer (p_miss 0.05, no oracle retype) | 2.54 | 2.75 | +0.21 [-0.09, 0.49] | gaze_lm | no |
| meg-async | symmetric offer, p_miss 0.2 | 1.20 | 2.75 | +1.55 [1.25, 1.82] | gaze_lm | no |
