# User-model sensitivity: generated tables

eWPM point values; refit = policy refitted under the variant; misspecified = fitted under the main user, scored under the variant. gaze+LM = gaze typing with k = 3 word completion (no glance cost); glance = 1 s per look. CIs of differences at the condition's unit (B = 1000).

## b2t-ours

| variant | always commit | trust | never commit | trust (misspec.) | gaze | gaze+LM | gaze+LM glance | ranking | trust − gaze [CI] | trust − gaze+LM [CI] | trust − never commit [CI] | trust − always commit [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main | 11.45 | 11.55 | 11.37 | — | 4.08 | 5.84 | 4.55 | trust > always_commit > never_commit > gaze_lm > gaze_only | [6.75, 8.27] | [5.01, 6.51] | [0.118, 0.235] | [-0.16, 0.35] |
| fallback 10 cpm | 7.79 | 8.28 | 8.22 | 8.24 | 2.04 | 3.59 | 3.06 | trust > never_commit > always_commit > gaze_lm > gaze_only | [5.58, 7.04] | [4.03, 5.46] | [0.010, 0.108] | [0.35, 0.64] |
| fallback 40 cpm | 14.97 | 14.65 | 14.46 | 14.45 | 8.16 | 9.06 | 6.08 | always_commit > trust > never_commit > gaze_lm > gaze_only | [5.74, 7.31] | [4.84, 6.40] | [0.153, 0.224] | [-0.43, -0.18] |
| selection x0.5 | 11.96 | 12.24 | 12.11 | 12.24 | 4.08 | 7.19 | 5.33 | trust > never_commit > always_commit > gaze_lm > gaze_only | [7.43, 8.99] | [4.35, 5.89] | [0.071, 0.187] | [0.02, 0.54] |
| selection x2 | 10.55 | 10.37 | 10.13 | 10.37 | 4.08 | 4.53 | 3.64 | always_commit > trust > never_commit > gaze_lm > gaze_only | [5.62, 7.05] | [5.18, 6.59] | [0.183, 0.303] | [-0.41, 0.05] |
| p_miss 0 | 11.65 | 11.54 | 11.37 | 11.54 | 4.08 | 5.84 | 4.55 | always_commit > trust > never_commit > gaze_lm > gaze_only | [6.74, 8.27] | [5.00, 6.51] | [0.118, 0.233] | [-0.31, 0.07] |
| p_miss 0.2 | 10.77 | 11.52 | 11.37 | 11.52 | 4.08 | 5.84 | 4.55 | trust > never_commit > always_commit > gaze_lm > gaze_only | [6.71, 8.25] | [4.97, 6.49] | [0.089, 0.215] | [0.47, 1.05] |
| symmetric offer (p_miss 0.05, no oracle retype) | 11.45 | 11.36 | 11.18 | 11.36 | 4.08 | 5.84 | 4.55 | always_commit > trust > never_commit > gaze_lm > gaze_only | [6.58, 8.06] | [4.84, 6.27] | [0.119, 0.236] | [-0.30, 0.10] |
| symmetric offer, p_miss 0.2 | 10.77 | 10.77 | 10.60 | 10.77 | 4.08 | 5.84 | 4.55 | always_commit > trust > never_commit > gaze_lm > gaze_only | [5.95, 7.57] | [4.21, 5.81] | [0.107, 0.237] | [-0.26, 0.27] |

Trust silent-error rate per variant: main 0.0025; fallback 10 cpm 0.0025; fallback 40 cpm 0.0025; selection x0.5 0.0025; selection x2 0.0025; p_miss 0 0.0000; p_miss 0.2 0.0098; symmetric offer (p_miss 0.05, no oracle retype) 0.0380; symmetric offer, p_miss 0.2 0.1495

## b2t-published

| variant | always commit | trust | never commit | trust (misspec.) | gaze | gaze+LM | gaze+LM glance | ranking | trust − gaze [CI] | trust − gaze+LM [CI] | trust − never commit [CI] | trust − always commit [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main | 19.61 | 18.77 | 18.11 | — | 4.08 | 5.84 | 4.55 | always_commit > trust > never_commit > gaze_lm > gaze_only | [13.08, 16.32] | [11.32, 14.53] | [0.530, 0.800] | [-1.01, -0.68] |
| fallback 10 cpm | 16.12 | 15.36 | 14.89 | 15.36 | 2.04 | 3.59 | 3.06 | always_commit > trust > never_commit > gaze_lm > gaze_only | [11.46, 15.36] | [9.92, 13.78] | [0.348, 0.647] | [-1.03, -0.53] |
| fallback 40 cpm | 21.99 | 21.12 | 20.32 | 21.12 | 8.16 | 9.06 | 6.08 | always_commit > trust > never_commit > gaze_lm > gaze_only | [11.69, 14.16] | [10.79, 13.23] | [0.687, 0.912] | [-1.00, -0.74] |
| selection x0.5 | 20.00 | 19.54 | 19.18 | 19.54 | 4.08 | 7.19 | 5.33 | always_commit > trust > never_commit > gaze_lm > gaze_only | [13.88, 17.06] | [10.76, 13.93] | [0.286, 0.457] | [-0.59, -0.33] |
| selection x2 | 18.87 | 17.40 | 16.32 | 17.40 | 4.08 | 4.53 | 3.64 | always_commit > trust > never_commit > gaze_lm > gaze_only | [11.70, 14.97] | [11.25, 14.52] | [0.877, 1.320] | [-1.74, -1.22] |
| p_miss 0 | 19.52 | 18.75 | 18.11 | 18.75 | 4.08 | 5.84 | 4.55 | always_commit > trust > never_commit > gaze_lm > gaze_only | [13.09, 16.29] | [11.33, 14.50] | [0.537, 0.750] | [-0.87, -0.66] |
| p_miss 0.2 | 19.69 | 18.72 | 18.11 | 18.72 | 4.08 | 5.84 | 4.55 | always_commit > trust > never_commit > gaze_lm > gaze_only | [13.04, 16.30] | [11.28, 14.52] | [0.459, 0.770] | [-1.21, -0.66] |
| symmetric offer (p_miss 0.05, no oracle retype) | 19.61 | 18.82 | 18.16 | 18.82 | 4.08 | 5.84 | 4.55 | always_commit > trust > never_commit > gaze_lm > gaze_only | [13.11, 16.41] | [11.33, 14.65] | [0.550, 0.780] | [-0.90, -0.68] |
| symmetric offer, p_miss 0.2 | 19.69 | 18.86 | 18.17 | 18.86 | 4.08 | 5.84 | 4.55 | always_commit > trust > never_commit > gaze_lm > gaze_only | [13.00, 16.44] | [11.24, 14.69] | [0.583, 0.810] | [-0.95, -0.72] |

Trust silent-error rate per variant: main 0.0037; fallback 10 cpm 0.0037; fallback 40 cpm 0.0037; selection x0.5 0.0037; selection x2 0.0037; p_miss 0 0.0000; p_miss 0.2 0.0098; symmetric offer (p_miss 0.05, no oracle retype) 0.0245; symmetric offer, p_miss 0.2 0.0674

## emg-calib

| variant | always commit | trust | never commit | trust (misspec.) | gaze | gaze+LM | gaze+LM glance | ranking | trust − gaze [CI] | trust − gaze+LM [CI] | trust − never commit [CI] | trust − always commit [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main | 7.81 | 8.02 | 8.01 | — | 4.27 | 6.19 | 4.84 | trust > never_commit > always_commit > gaze_lm > gaze_only | [2.65, 4.88] | [0.74, 2.99] | [0.006, 0.026] | [0.01, 0.41] |
| fallback 10 cpm | 5.76 | 6.24 | 6.23 | 6.15 | 2.14 | 3.89 | 3.31 | trust > never_commit > always_commit > gaze_lm > gaze_only | [2.98, 5.35] | [1.25, 3.63] | [0.004, 0.017] | [0.31, 0.68] |
| fallback 40 cpm | 9.57 | 9.63 | 9.62 | 9.51 | 8.55 | 9.43 | 6.35 | trust > never_commit > always_commit > gaze_lm > gaze_only | [0.20, 1.97] | [-0.68, 1.08] | [0.007, 0.022] | [-0.15, 0.31] |
| selection x0.5 | 8.13 | 8.45 | 8.44 | 8.45 | 4.27 | 7.77 | 5.75 | trust > never_commit > always_commit > gaze_lm > gaze_only | [3.06, 5.32] | [-0.40, 1.83] | [0.004, 0.020] | [0.12, 0.52] |
| selection x2 | 7.32 | 7.38 | 7.29 | 7.34 | 4.27 | 4.71 | 3.79 | trust > always_commit > never_commit > gaze_lm > gaze_only | [2.06, 4.20] | [1.62, 3.76] | [0.033, 0.175] | [-0.15, 0.26] |
| p_miss 0 | 8.11 | 8.09 | 8.01 | 8.02 | 4.27 | 6.19 | 4.84 | always_commit > trust > never_commit > gaze_lm > gaze_only | [2.68, 4.98] | [0.77, 3.06] | [0.041, 0.129] | [-0.14, 0.13] |
| p_miss 0.2 | 6.90 | 8.02 | 8.01 | 8.02 | 4.27 | 6.19 | 4.84 | trust > never_commit > always_commit > gaze_lm > gaze_only | [2.65, 4.88] | [0.74, 2.99] | [0.006, 0.026] | [0.83, 1.46] |
| symmetric offer (p_miss 0.05, no oracle retype) | 7.80 | 7.82 | 7.75 | 7.76 | 4.27 | 6.19 | 4.84 | trust > always_commit > never_commit > gaze_lm > gaze_only | [2.36, 4.73] | [0.46, 2.82] | [0.010, 0.136] | [-0.14, 0.20] |
| symmetric offer, p_miss 0.2 | 6.90 | 7.16 | 7.09 | 7.09 | 4.27 | 6.19 | 4.84 | trust > never_commit > always_commit > gaze_lm > gaze_only | [1.50, 4.23] | [-0.42, 2.32] | [0.014, 0.133] | [0.10, 0.45] |

Trust silent-error rate per variant: main 0.0000; fallback 10 cpm 0.0000; fallback 40 cpm 0.0000; selection x0.5 0.0000; selection x2 0.0018; p_miss 0 0.0000; p_miss 0.2 0.0000; symmetric offer (p_miss 0.05, no oracle retype) 0.0417; symmetric offer, p_miss 0.2 0.1688

## emg-xsession

| variant | always commit | trust | never commit | trust (misspec.) | gaze | gaze+LM | gaze+LM glance | ranking | trust − gaze [CI] | trust − gaze+LM [CI] | trust − never commit [CI] | trust − always commit [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main | 4.10 | 4.68 | 4.67 | — | 4.27 | 6.19 | 4.84 | gaze_lm > trust > never_commit > gaze_only > always_commit | [-0.09, 0.96] | [-1.99, -0.95] | [-0.002, 0.007] | [0.47, 0.69] |
| fallback 10 cpm | 2.63 | 3.09 | 3.08 | 3.07 | 2.14 | 3.89 | 3.31 | gaze_lm > trust > never_commit > always_commit > gaze_only | [0.56, 1.41] | [-1.17, -0.34] | [-0.003, 0.004] | [0.39, 0.54] |
| fallback 40 cpm | 6.02 | 6.58 | 6.58 | 6.48 | 8.55 | 9.43 | 6.35 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-2.43, -1.46] | [-3.32, -2.35] | [0.001, 0.005] | [0.40, 0.73] |
| selection x0.5 | 4.34 | 5.00 | 5.00 | 5.00 | 4.27 | 7.77 | 5.75 | gaze_lm > trust > never_commit > always_commit > gaze_only | [0.20, 1.32] | [-3.27, -2.19] | [-0.003, 0.007] | [0.55, 0.78] |
| selection x2 | 3.99 | 4.29 | 4.28 | 4.29 | 4.27 | 4.71 | 3.79 | gaze_lm > trust > never_commit > gaze_only > always_commit | [-0.41, 0.49] | [-0.85, 0.05] | [-0.002, 0.009] | [0.20, 0.42] |
| p_miss 0 | 4.72 | 4.68 | 4.67 | 4.68 | 4.27 | 6.19 | 4.84 | gaze_lm > always_commit > trust > never_commit > gaze_only | [-0.09, 0.96] | [-1.99, -0.95] | [-0.002, 0.007] | [-0.09, 0.02] |
| p_miss 0.2 | 2.69 | 4.67 | 4.67 | 4.68 | 4.27 | 6.19 | 4.84 | gaze_lm > trust > never_commit > gaze_only > always_commit | [-0.09, 0.96] | [-1.99, -0.96] | [0.000, 0.000] | [1.78, 2.15] |
| symmetric offer (p_miss 0.05, no oracle retype) | 4.06 | 4.05 | 4.04 | 4.05 | 4.27 | 6.19 | 4.84 | gaze_lm > gaze_only > always_commit > trust > never_commit | [-0.79, 0.44] | [-2.70, -1.48] | [-0.002, 0.006] | [-0.06, 0.06] |
| symmetric offer, p_miss 0.2 | 2.67 | 3.39 | 3.38 | 2.75 | 4.27 | 6.19 | 4.84 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-0.93, -0.84] | [-2.85, -2.75] | [-0.001, 0.013] | [0.01, 1.28] |

Trust silent-error rate per variant: main 0.0000; fallback 10 cpm 0.0000; fallback 40 cpm 0.0000; selection x0.5 0.0000; selection x2 0.0000; p_miss 0 0.0000; p_miss 0.2 0.0000; symmetric offer (p_miss 0.05, no oracle retype) 0.1525; symmetric offer, p_miss 0.2 0.0145

## emg-xsubject

| variant | always commit | trust | never commit | trust (misspec.) | gaze | gaze+LM | gaze+LM glance | ranking | trust − gaze [CI] | trust − gaze+LM [CI] | trust − never commit [CI] | trust − always commit [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main | 3.53 | 4.08 | 4.08 | — | 4.27 | 6.19 | 4.84 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-0.44, 0.09] | [-2.35, -1.84] | [0.000, 0.000] | [0.44, 0.67] |
| fallback 10 cpm | 2.21 | 2.60 | 2.60 | 2.56 | 2.14 | 3.89 | 3.31 | gaze_lm > trust > never_commit > always_commit > gaze_only | [0.27, 0.70] | [-1.47, -1.06] | [0.000, 0.000] | [0.34, 0.46] |
| fallback 40 cpm | 5.45 | 6.01 | 6.01 | 6.01 | 8.55 | 9.43 | 6.35 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-2.79, -2.24] | [-3.68, -3.13] | [0.000, 0.000] | [0.45, 0.68] |
| selection x0.5 | 3.74 | 4.36 | 4.36 | 4.36 | 4.27 | 7.77 | 5.75 | gaze_lm > trust > never_commit > gaze_only > always_commit | [-0.17, 0.39] | [-3.66, -3.11] | [0.000, 0.000] | [0.51, 0.74] |
| selection x2 | 3.52 | 3.80 | 3.80 | 3.80 | 4.27 | 4.71 | 3.79 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-0.67, -0.25] | [-1.11, -0.69] | [0.000, 0.000] | [0.21, 0.34] |
| p_miss 0 | 4.14 | 4.08 | 4.08 | 4.08 | 4.27 | 6.19 | 4.84 | gaze_lm > gaze_only > always_commit > trust > never_commit | [-0.44, 0.09] | [-2.35, -1.84] | [0.000, 0.000] | [-0.07, -0.06] |
| p_miss 0.2 | 1.98 | 4.08 | 4.08 | 4.08 | 4.27 | 6.19 | 4.84 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-0.44, 0.09] | [-2.35, -1.84] | [0.000, 0.000] | [1.93, 2.26] |
| symmetric offer (p_miss 0.05, no oracle retype) | 3.50 | 3.45 | 3.45 | 3.44 | 4.27 | 6.19 | 4.84 | gaze_lm > gaze_only > always_commit > trust > never_commit | [-1.16, -0.45] | [-3.07, -2.37] | [0.000, 0.000] | [-0.07, -0.01] |
| symmetric offer, p_miss 0.2 | 1.96 | 3.33 | 3.33 | 1.92 | 4.27 | 6.19 | 4.84 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-0.97, -0.92] | [-2.91, -2.81] | [0.000, 0.000] | [0.96, 1.70] |

Trust silent-error rate per variant: main 0.0000; fallback 10 cpm 0.0000; fallback 40 cpm 0.0000; selection x0.5 0.0000; selection x2 0.0000; p_miss 0 0.0000; p_miss 0.2 0.0000; symmetric offer (p_miss 0.05, no oracle retype) 0.1670; symmetric offer, p_miss 0.2 0.0054

## meg-async

| variant | always commit | trust | never commit | trust (misspec.) | gaze | gaze+LM | gaze+LM glance | ranking | trust − gaze [CI] | trust − gaze+LM [CI] | trust − never commit [CI] | trust − always commit [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main | 2.58 | 3.20 | 3.20 | — | 3.15 | 4.10 | 3.16 | gaze_lm > trust > never_commit > gaze_only > always_commit | [-0.11, 0.27] | [-1.14, -0.64] | [0.000, 0.000] | [0.44, 0.81] |
| fallback 10 cpm | 1.51 | 1.89 | 1.89 | 1.89 | 1.58 | 2.37 | 2.02 | gaze_lm > trust > never_commit > gaze_only > always_commit | [0.21, 0.45] | [-0.66, -0.30] | [0.000, 0.000] | [0.27, 0.49] |
| fallback 40 cpm | 4.31 | 5.15 | 5.15 | 5.13 | 6.31 | 6.83 | 4.46 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-1.36, -0.89] | [-1.91, -1.41] | [0.000, 0.000] | [0.59, 1.11] |
| selection x0.5 | 2.74 | 3.45 | 3.45 | 3.45 | 3.15 | 4.75 | 3.53 | gaze_lm > trust > never_commit > gaze_only > always_commit | [0.13, 0.53] | [-1.61, -0.96] | [0.000, 0.000] | [0.51, 0.91] |
| selection x2 | 2.54 | 2.96 | 2.96 | 2.95 | 3.15 | 3.42 | 2.70 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-0.31, -0.02] | [-0.58, -0.29] | [0.000, 0.000] | [0.28, 0.58] |
| p_miss 0 | 3.24 | 3.20 | 3.20 | 3.20 | 3.15 | 4.10 | 3.16 | gaze_lm > always_commit > trust > never_commit > gaze_only | [-0.11, 0.27] | [-1.14, -0.64] | [0.000, 0.000] | [-0.05, -0.04] |
| p_miss 0.2 | 1.24 | 3.20 | 3.20 | 3.20 | 3.15 | 4.10 | 3.16 | gaze_lm > trust > never_commit > gaze_only > always_commit | [-0.11, 0.27] | [-1.14, -0.64] | [0.000, 0.000] | [1.77, 2.18] |
| symmetric offer (p_miss 0.05, no oracle retype) | 2.54 | 2.75 | 2.75 | 2.51 | 3.15 | 4.10 | 3.16 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-0.43, -0.39] | [-1.52, -1.21] | [0.000, 0.000] | [-0.10, 0.47] |
| symmetric offer, p_miss 0.2 | 1.20 | 2.75 | 2.75 | 1.18 | 3.15 | 4.10 | 3.16 | gaze_lm > gaze_only > trust > never_commit > always_commit | [-0.43, -0.39] | [-1.52, -1.21] | [0.000, 0.000] | [1.25, 1.83] |

Trust silent-error rate per variant: main 0.0000; fallback 10 cpm 0.0000; fallback 40 cpm 0.0000; selection x0.5 0.0000; selection x2 0.0000; p_miss 0 0.0000; p_miss 0.2 0.0000; symmetric offer (p_miss 0.05, no oracle retype) 0.0000; symmetric offer, p_miss 0.2 0.0000

