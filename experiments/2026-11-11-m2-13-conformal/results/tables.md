# M2-13 tables (alpha 0.05, delta 0.1, 200 random splits)

## b2t-ours

Test trials 816; old commit_p 0.5; eligible (other rules allow COMMIT) 0.664; top-1 right 0.390.

Whole test set: old: wrong-commit 0.0588, commit 0.232, eWPM 11.55; always_commit_eligible: wrong-commit 0.3456, commit 1.000, eWPM 11.54; never_commit: wrong-commit 0.0000, commit 0.000, eWPM 11.37

### Random splits, n_cal = 100, n_test = 716

| method | wrong-commit mean ± se | p95 | P(> alpha) | commit rate | eWPM mean [p05, p95] | silent error | median commit_p | never-commit share |
|---|---|---|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.0586 ± 0.0002 | 0.0642 | 1.00 | 0.231 | 11.55 [11.39, 11.70] | 0.0025 | 0.5 | 0.00 |
| plug-in re-tune on cal (empirical <= alpha) | 0.0492 ± 0.0019 | 0.0978 | 0.46 | 0.196 | 11.52 [11.37, 11.68] | 0.0016 | 0.541721109603658 | 0.00 |
| CRC | 0.0464 ± 0.0017 | 0.0936 | 0.38 | 0.189 | 11.52 [11.37, 11.68] | 0.0014 | 0.5507067538089664 | 0.00 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.0412 ± 0.0016 | 0.0828 | 0.30 | 0.174 | 11.51 [11.37, 11.66] | 0.0011 | 0.5794792848373547 | 0.00 |
| LTT (delta 0.1, binomial) | 0.0189 ± 0.0010 | 0.0475 | 0.04 | 0.097 | 11.45 [11.31, 11.63] | 0.0002 | 0.65 | 0.00 |

### Random splits, n_cal = 408, n_test = 408

| method | wrong-commit mean ± se | p95 | P(> alpha) | commit rate | eWPM mean [p05, p95] | silent error | median commit_p | never-commit share |
|---|---|---|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.0586 ± 0.0006 | 0.0711 | 0.86 | 0.233 | 11.57 [11.17, 11.98] | 0.0025 | 0.5 | 0.00 |
| plug-in re-tune on cal (empirical <= alpha) | 0.0435 ± 0.0013 | 0.0760 | 0.35 | 0.181 | 11.52 [11.13, 11.91] | 0.0010 | 0.5502887086768475 | 0.00 |
| CRC | 0.0483 ± 0.0010 | 0.0712 | 0.45 | 0.194 | 11.53 [11.13, 11.92] | 0.0016 | 0.538762825664628 | 0.00 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.0403 ± 0.0012 | 0.0712 | 0.32 | 0.172 | 11.52 [11.11, 11.91] | 0.0008 | 0.5721010792529743 | 0.00 |
| LTT (delta 0.1, binomial) | 0.0345 ± 0.0009 | 0.0564 | 0.14 | 0.156 | 11.52 [11.12, 11.91] | 0.0005 | 0.58 | 0.00 |

### Earlier data: calibrate on the fit half, test on the whole test half (one shot, not exchangeable)

| method | commit_p | wrong-commit | commit rate | eWPM | silent error |
|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.5 | 0.0588 | 0.232 | 11.55 | 0.0025 |
| plug-in re-tune on cal (empirical <= alpha) | 0.4852 | 0.0637 | 0.248 | 11.55 | 0.0025 |
| CRC | 0.4893 | 0.0625 | 0.244 | 11.55 | 0.0025 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.4893 | 0.0625 | 0.244 | 11.55 | 0.0025 |
| LTT (delta 0.1, binomial) | 0.54 | 0.0466 | 0.195 | 11.51 | 0.0012 |

## b2t-published

Test trials 816; old commit_p 0.7; eligible (other rules allow COMMIT) 0.603; top-1 right 0.806.

Whole test set: old: wrong-commit 0.0441, commit 0.473, eWPM 18.77; always_commit_eligible: wrong-commit 0.0833, commit 1.000, eWPM 18.95; never_commit: wrong-commit 0.0000, commit 0.000, eWPM 18.11

### Random splits, n_cal = 100, n_test = 716

| method | wrong-commit mean ± se | p95 | P(> alpha) | commit rate | eWPM mean [p05, p95] | silent error | median commit_p | never-commit share |
|---|---|---|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.0442 ± 0.0002 | 0.0489 | 0.01 | 0.473 | 18.75 [18.51, 19.04] | 0.0037 | 0.7 | 0.00 |
| plug-in re-tune on cal (empirical <= alpha) | 0.0549 ± 0.0015 | 0.0880 | 0.56 | 0.502 | 18.79 [18.56, 19.07] | 0.0050 | 0.658516252201221 | 0.00 |
| CRC | 0.0468 ± 0.0015 | 0.0839 | 0.42 | 0.469 | 18.74 [18.50, 19.02] | 0.0041 | 0.7020711315494845 | 0.00 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.0468 ± 0.0015 | 0.0839 | 0.42 | 0.469 | 18.74 [18.50, 19.02] | 0.0041 | 0.7020711315494845 | 0.00 |
| LTT (delta 0.1, binomial) | 0.0195 ± 0.0011 | 0.0489 | 0.04 | 0.292 | 18.49 [18.14, 18.81] | 0.0016 | 0.89 | 0.00 |

### Random splits, n_cal = 408, n_test = 408

| method | wrong-commit mean ± se | p95 | P(> alpha) | commit rate | eWPM mean [p05, p95] | silent error | median commit_p | never-commit share |
|---|---|---|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.0441 ± 0.0005 | 0.0588 | 0.20 | 0.471 | 18.77 [18.14, 19.43] | 0.0035 | 0.7 | 0.00 |
| plug-in re-tune on cal (empirical <= alpha) | 0.0503 ± 0.0011 | 0.0786 | 0.45 | 0.488 | 18.79 [18.16, 19.45] | 0.0044 | 0.6709362532210374 | 0.00 |
| CRC | 0.0478 ± 0.0010 | 0.0761 | 0.41 | 0.479 | 18.78 [18.16, 19.42] | 0.0041 | 0.6929597645502854 | 0.00 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.0478 ± 0.0010 | 0.0761 | 0.41 | 0.479 | 18.78 [18.16, 19.42] | 0.0041 | 0.6929597645502854 | 0.00 |
| LTT (delta 0.1, binomial) | 0.0345 ± 0.0010 | 0.0614 | 0.14 | 0.427 | 18.70 [18.08, 19.36] | 0.0023 | 0.74 | 0.00 |

### Earlier data: calibrate on the fit half, test on the whole test half (one shot, not exchangeable)

| method | commit_p | wrong-commit | commit rate | eWPM | silent error |
|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.7 | 0.0441 | 0.473 | 18.77 | 0.0037 |
| plug-in re-tune on cal (empirical <= alpha) | 0.6696 | 0.0490 | 0.498 | 18.80 | 0.0049 |
| CRC | 0.6717 | 0.0490 | 0.496 | 18.80 | 0.0049 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.6717 | 0.0490 | 0.496 | 18.80 | 0.0049 |
| LTT (delta 0.1, binomial) | 0.72 | 0.0404 | 0.446 | 18.73 | 0.0037 |

## meg-full-r1

Test trials 637; old commit_p 0.5; eligible (other rules allow COMMIT) 0.022; top-1 right 0.000.

Whole test set: old: wrong-commit 0.0000, commit 0.000, eWPM 3.23; always_commit_eligible: wrong-commit 0.0220, commit 1.000, eWPM 3.23; never_commit: wrong-commit 0.0000, commit 0.000, eWPM 3.23

### Random splits, n_cal = 100, n_test = 537

| method | wrong-commit mean ± se | p95 | P(> alpha) | commit rate | eWPM mean [p05, p95] | silent error | median commit_p | never-commit share |
|---|---|---|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.0000 ± 0.0000 | 0.0000 | 0.00 | 0.000 | 3.23 [3.21, 3.25] | 0.0000 | 0.5 | 0.00 |
| plug-in re-tune on cal (empirical <= alpha) | 0.0107 ± 0.0005 | 0.0223 | 0.00 | 0.011 | 3.23 [3.21, 3.24] | 0.0011 | 0.1026978800168738 | 0.14 |
| CRC | 0.0126 ± 0.0005 | 0.0223 | 0.00 | 0.013 | 3.23 [3.21, 3.24] | 0.0011 | 0.10267465802030526 | 0.07 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.0107 ± 0.0005 | 0.0223 | 0.00 | 0.011 | 3.23 [3.21, 3.24] | 0.0011 | 0.10287822012510009 | 0.14 |
| LTT (delta 0.1, binomial) | 0.0058 ± 0.0007 | 0.0261 | 0.00 | 0.006 | 3.23 [3.21, 3.25] | 0.0004 | 0.11 | 0.00 |

### Random splits, n_cal = 408, n_test = 229

| method | wrong-commit mean ± se | p95 | P(> alpha) | commit rate | eWPM mean [p05, p95] | silent error | median commit_p | never-commit share |
|---|---|---|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.0000 ± 0.0000 | 0.0000 | 0.00 | 0.000 | 3.23 [3.17, 3.29] | 0.0000 | 0.5 | 0.00 |
| plug-in re-tune on cal (empirical <= alpha) | 0.0108 ± 0.0007 | 0.0306 | 0.00 | 0.011 | 3.22 [3.17, 3.29] | 0.0014 | 0.10439518637658932 | 0.00 |
| CRC | 0.0186 ± 0.0005 | 0.0306 | 0.00 | 0.019 | 3.22 [3.17, 3.29] | 0.0014 | 0.10175013953615732 | 0.00 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.0108 ± 0.0007 | 0.0306 | 0.00 | 0.011 | 3.22 [3.17, 3.29] | 0.0014 | 0.10439518637658932 | 0.00 |
| LTT (delta 0.1, binomial) | 0.0207 ± 0.0006 | 0.0349 | 0.00 | 0.021 | 3.22 [3.17, 3.29] | 0.0014 | 0.0 | 0.00 |

### Earlier data: calibrate on the fit half, test on the whole test half (one shot, not exchangeable)

| method | commit_p | wrong-commit | commit rate | eWPM | silent error |
|---|---|---|---|---|---|
| old gate (fixed, M6-06 / M1-15 fit) | 0.5 | 0.0000 | 0.000 | 3.23 | 0.0000 |
| plug-in re-tune on cal (empirical <= alpha) | 0.1046 | 0.0063 | 0.006 | 3.23 | 0.0000 |
| CRC | 0.1006 | 0.0220 | 0.022 | 3.23 | 0.0016 |
| CRC + eWPM tune (lambda >= lambda_CRC) | 0.1046 | 0.0063 | 0.006 | 3.23 | 0.0000 |
| LTT (delta 0.1, binomial) | 0.11 | 0.0000 | 0.000 | 3.23 | 0.0000 |
