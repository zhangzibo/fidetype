# Unified CIs and inference checks

One bootstrap: seed 20261112, B = 2000, percentile 95 %, conditional on the fitted pipeline and the threshold. Full data: `ci.json`.

## Tab. 2 (baselines): eWPM and wrong-commit with unified CIs

| condition | policy | eWPM [CI] | wrong-commit [CI] | wrong / n (CP95 two-sided) | commit rate | error among commits (counts if < 30 commits) |
|---|---|---|---|---|---|---|
| b2t-ours | always_commit | 11.45 [10.70, 12.31] | 0.6103 [0.568, 0.647] | 498/816 [0.5759, 0.6439] | 1.000 | 0.610 |
| b2t-ours | never_commit | 11.37 [10.67, 12.17] | 0.0000 [0.000, 0.000] | 0/816 [0.0000, 0.0045] | 0.000 | 0/0 |
| b2t-ours | raw_no_guard | 11.39 [10.61, 12.27] | 0.0000 [0.000, 0.000] | 0/816 [0.0000, 0.0045] | 0.000 | 0/0 |
| b2t-ours | no_guard | 11.51 [10.79, 12.35] | 0.0355 [0.025, 0.046] | 29/816 [0.0239, 0.0506] | 0.165 | 0.215 |
| b2t-ours | trust | 11.55 [10.83, 12.34] | 0.0588 [0.045, 0.070] | 48/816 [0.0437, 0.0772] | 0.232 | 0.254 |
| b2t-ours | gaze_only | 4.08 [4.05, 4.12] | 0.0000 [0.000, 0.000] | 0/816 [0.0000, 0.0045] | 0.000 | 0/0 |
| b2t-ours | crc | 11.48 [10.79, 12.29] | 0.0245 [0.015, 0.035] | 20/816 [0.0150, 0.0376] | 0.100 | 0.244 |
| b2t-ours | ltt | 11.48 [10.79, 12.29] | 0.0270 [0.016, 0.038] | 22/816 [0.0170, 0.0405] | 0.104 | 0.259 |
| b2t-ours | clean_plugin | 11.48 [10.79, 12.29] | 0.0245 [0.015, 0.035] | 20/816 [0.0150, 0.0376] | 0.100 | 0.244 |
| b2t-published | always_commit | 19.61 [17.81, 21.32] | 0.1936 [0.146, 0.253] | 158/816 [0.1670, 0.2224] | 1.000 | 0.194 |
| b2t-published | never_commit | 18.11 [16.59, 19.57] | 0.0000 [0.000, 0.000] | 0/816 [0.0000, 0.0045] | 0.000 | 0/0 |
| b2t-published | raw_no_guard | 18.68 [17.05, 20.24] | 0.0331 [0.021, 0.045] | 27/816 [0.0219, 0.0478] | 0.423 | 0.078 |
| b2t-published | no_guard | 18.62 [17.01, 20.17] | 0.0245 [0.014, 0.038] | 20/816 [0.0150, 0.0376] | 0.381 | 0.064 |
| b2t-published | trust | 18.77 [17.13, 20.35] | 0.0441 [0.027, 0.068] | 36/816 [0.0311, 0.0606] | 0.473 | 0.093 |
| b2t-published | gaze_only | 4.08 [4.05, 4.12] | 0.0000 [0.000, 0.000] | 0/816 [0.0000, 0.0045] | 0.000 | 0/0 |
| b2t-published | crc | 18.79 [17.13, 20.37] | 0.0478 [0.029, 0.071] | 39/816 [0.0342, 0.0648] | 0.491 | 0.097 |
| b2t-published | ltt | 18.65 [17.04, 20.20] | 0.0294 [0.013, 0.050] | 24/816 [0.0189, 0.0434] | 0.403 | 0.073 |
| b2t-published | clean_plugin | 18.79 [17.13, 20.37] | 0.0478 [0.029, 0.071] | 39/816 [0.0342, 0.0648] | 0.491 | 0.097 |
| emg-calib | always_commit | 7.81 [6.66, 9.04] | 0.5408 [0.463, 0.621] | 298/551 [0.4982, 0.5830] | 1.000 | 0.541 |
| emg-calib | never_commit | 8.01 [6.92, 9.17] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-calib | raw_no_guard | 8.15 [7.05, 9.38] | 0.0454 [0.033, 0.058] | 25/551 [0.0296, 0.0663] | 0.283 | 0.160 |
| emg-calib | no_guard | 8.02 [6.93, 9.19] | 0.0036 [0.000, 0.009] | 2/551 [0.0004, 0.0130] | 0.038 | 2/21 |
| emg-calib | trust | 8.02 [6.93, 9.19] | 0.0036 [0.000, 0.009] | 2/551 [0.0004, 0.0130] | 0.038 | 2/21 |
| emg-calib | gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-calib | crc | 8.07 [6.98, 9.26] | 0.0399 [0.025, 0.056] | 22/551 [0.0252, 0.0598] | 0.241 | 0.165 |
| emg-calib | ltt | 8.04 [6.97, 9.21] | 0.0218 [0.009, 0.036] | 12/551 [0.0113, 0.0377] | 0.183 | 0.119 |
| emg-calib | clean_plugin | 7.98 [6.95, 9.11] | 0.0036 [0.000, 0.009] | 2/551 [0.0004, 0.0130] | 0.038 | 2/21 |
| emg-xsession | always_commit | 4.10 [3.56, 4.73] | 0.8820 [0.831, 0.928] | 486/551 [0.8521, 0.9078] | 1.000 | 0.882 |
| emg-xsession | never_commit | 4.67 [4.19, 5.25] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsession | raw_no_guard | 4.75 [4.18, 5.52] | 0.0127 [0.002, 0.026] | 7/551 [0.0051, 0.0260] | 0.042 | 7/23 |
| emg-xsession | no_guard | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 2/551 [0.0004, 0.0130] | 0.018 | 2/10 |
| emg-xsession | trust | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 2/551 [0.0004, 0.0130] | 0.018 | 2/10 |
| emg-xsession | gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsession | crc | 4.66 [4.18, 5.24] | 0.0563 [0.039, 0.074] | 31/551 [0.0385, 0.0789] | 0.093 | 0.608 |
| emg-xsession | ltt | 4.67 [4.18, 5.25] | 0.0309 [0.021, 0.042] | 17/551 [0.0181, 0.0489] | 0.054 | 0.567 |
| emg-xsession | clean_plugin | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 2/551 [0.0004, 0.0130] | 0.018 | 2/10 |
| emg-xsubject | always_commit | 3.53 [3.19, 3.90] | 0.9619 [0.942, 0.981] | 530/551 [0.9423, 0.9763] | 1.000 | 0.962 |
| emg-xsubject | never_commit | 4.08 [3.82, 4.37] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsubject | raw_no_guard | 4.76 [4.23, 5.40] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsubject | no_guard | 4.08 [3.82, 4.37] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsubject | trust | 4.08 [3.82, 4.37] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsubject | gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsubject | crc | 4.08 [3.82, 4.37] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsubject | ltt | 4.08 [3.82, 4.37] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| emg-xsubject | clean_plugin | 4.08 [3.82, 4.37] | 0.0000 [0.000, 0.000] | 0/551 [0.0000, 0.0067] | 0.000 | 0/0 |
| meg-async | always_commit | 2.58 [2.31, 2.88] | 0.9969 [0.987, 1.000] | 635/637 [0.9887, 0.9996] | 1.000 | 0.997 |
| meg-async | never_commit | 3.20 [3.01, 3.44] | 0.0000 [0.000, 0.000] | 0/637 [0.0000, 0.0058] | 0.000 | 0/0 |
| meg-async | raw_no_guard | 3.04 [2.88, 3.24] | 0.0047 [0.000, 0.016] | 3/637 [0.0010, 0.0137] | 0.006 | 3/4 |
| meg-async | no_guard | 3.20 [3.01, 3.44] | 0.0000 [0.000, 0.000] | 0/637 [0.0000, 0.0058] | 0.000 | 0/0 |
| meg-async | trust | 3.20 [3.01, 3.44] | 0.0000 [0.000, 0.000] | 0/637 [0.0000, 0.0058] | 0.000 | 0/0 |
| meg-async | gaze_only | 3.15 [3.02, 3.31] | 0.0000 [0.000, 0.000] | 0/637 [0.0000, 0.0058] | 0.000 | 0/0 |
| meg-async | crc | 3.20 [3.01, 3.43] | 0.0283 [0.006, 0.061] | 18/637 [0.0168, 0.0443] | 0.030 | 18/19 |
| meg-async | ltt | 3.20 [3.01, 3.44] | 0.0000 [0.000, 0.000] | 0/637 [0.0000, 0.0058] | 0.002 | 0/1 |
| meg-async | clean_plugin | 3.20 [3.01, 3.44] | 0.0000 [0.000, 0.000] | 0/637 [0.0000, 0.0058] | 0.000 | 0/0 |

Paired differences (eWPM CI; wrong-commit CI):

- b2t-ours: trust-always_commit [-0.14, 0.33] / [-0.586, -0.513]; trust-never_commit [0.12, 0.24] / [0.045, 0.070]; trust-gaze_only [6.75, 8.28] / [0.045, 0.070]; never_commit-gaze_only [6.60, 8.10] / [0.000, 0.000]; no_guard-trust [-0.10, 0.04] / [-0.035, -0.011]; crc-never_commit [0.06, 0.16] / [0.015, 0.035]; crc-trust [-0.15, 0.02] / [-0.048, -0.020]; always_commit-gaze_only [6.62, 8.23] / [0.568, 0.647]
- b2t-published: trust-always_commit [-1.01, -0.66] / [-0.187, -0.114]; trust-never_commit [0.53, 0.80] / [0.027, 0.068]; trust-gaze_only [13.03, 16.27] / [0.027, 0.068]; never_commit-gaze_only [12.51, 15.49] / [0.000, 0.000]; no_guard-trust [-0.20, -0.10] / [-0.034, -0.007]; crc-never_commit [0.54, 0.83] / [0.029, 0.071]; crc-trust [0.01, 0.04] / [0.000, 0.007]; always_commit-gaze_only [13.73, 17.25] / [0.146, 0.253]
- emg-calib: trust-always_commit [0.02, 0.39] / [-0.618, -0.458]; trust-never_commit [0.01, 0.03] / [0.000, 0.009]; trust-gaze_only [2.71, 4.91] / [0.000, 0.009]; never_commit-gaze_only [2.70, 4.89] / [0.000, 0.000]; no_guard-trust [0.00, 0.00] / [0.000, 0.000]; crc-never_commit [-0.01, 0.15] / [0.025, 0.056]; crc-trust [-0.03, 0.13] / [0.023, 0.051]; always_commit-gaze_only [2.41, 4.73] / [0.463, 0.621]
- emg-xsession: trust-always_commit [0.46, 0.69] / [-0.926, -0.825]; trust-never_commit [-0.00, 0.01] / [0.000, 0.009]; trust-gaze_only [-0.07, 0.97] / [0.000, 0.009]; never_commit-gaze_only [-0.07, 0.97] / [0.000, 0.000]; no_guard-trust [0.00, 0.00] / [0.000, 0.000]; crc-never_commit [-0.04, 0.01] / [0.039, 0.074]; crc-trust [-0.04, 0.01] / [0.038, 0.068]; always_commit-gaze_only [-0.70, 0.45] / [0.831, 0.928]
- emg-xsubject: trust-always_commit [0.43, 0.66] / [-0.981, -0.942]; trust-never_commit [0.00, 0.00] / [0.000, 0.000]; trust-gaze_only [-0.44, 0.09] / [0.000, 0.000]; never_commit-gaze_only [-0.44, 0.09] / [0.000, 0.000]; no_guard-trust [0.00, 0.00] / [0.000, 0.000]; crc-never_commit [0.00, 0.00] / [0.000, 0.000]; crc-trust [0.00, 0.00] / [0.000, 0.000]; always_commit-gaze_only [-1.08, -0.37] / [0.942, 0.981]
- meg-async: trust-always_commit [0.45, 0.83] / [-1.000, -0.987]; trust-never_commit [0.00, 0.00] / [0.000, 0.000]; trust-gaze_only [-0.10, 0.25] / [0.000, 0.000]; never_commit-gaze_only [-0.10, 0.25] / [0.000, 0.000]; no_guard-trust [0.00, 0.00] / [0.000, 0.000]; crc-never_commit [-0.04, 0.01] / [0.006, 0.061]; crc-trust [-0.04, 0.01] / [0.006, 0.061]; always_commit-gaze_only [-0.86, -0.27] / [0.987, 1.000]
  - sentences only: trust-always_commit [0.51, 0.75]; trust-never_commit [0.00, 0.00]; trust-gaze_only [-0.04, 0.15]; never_commit-gaze_only [-0.04, 0.15]; no_guard-trust [0.00, 0.00]; crc-never_commit [-0.03, 0.01]; crc-trust [-0.03, 0.01]; always_commit-gaze_only [-0.78, -0.39]
  - participants only: trust-always_commit [0.51, 0.74]; trust-never_commit [0.00, 0.00]; trust-gaze_only [-0.08, 0.22]; never_commit-gaze_only [-0.08, 0.22]; no_guard-trust [0.00, 0.00]; crc-never_commit [-0.02, 0.00]; crc-trust [-0.02, 0.00]; always_commit-gaze_only [-0.75, -0.35]

## Tab. 3 (clean calibration): test wrong-commit [CI]

| condition | plug-in (fit-A) | CRC pure | LTT pure | CRC max-rule | LTT max-rule |
|---|---|---|---|---|---|
| ours-alternate | 0.0245 [0.015, 0.035] | 0.0245 [0.015, 0.035] | 0.0270 [0.016, 0.038] | 0.0245 [0.015, 0.035] | 0.0245 [0.015, 0.035] |
| ours-chrono | 0.0600 [0.049, 0.071] | 0.0600 [0.049, 0.071] | 0.0515 [0.043, 0.059] | 0.0600 [0.049, 0.071] | 0.0515 [0.043, 0.059] |
| published-alternate | 0.0478 [0.029, 0.071] | 0.0478 [0.029, 0.071] | 0.0294 [0.013, 0.050] | 0.0478 [0.029, 0.071] | 0.0294 [0.013, 0.050] |
| published-chrono | 0.0478 [0.029, 0.071] | 0.0490 [0.030, 0.073] | 0.0306 [0.014, 0.052] | 0.0478 [0.029, 0.071] | 0.0306 [0.014, 0.052] |
| emg-xsession | 0.0036 [0.000, 0.009] | 0.0563 [0.039, 0.074] | 0.0309 [0.021, 0.042] | 0.0036 [0.000, 0.009] | 0.0036 [0.000, 0.009] |
| emg-calib | 0.0036 [0.000, 0.009] | 0.0399 [0.025, 0.056] | 0.0218 [0.009, 0.036] | 0.0036 [0.000, 0.009] | 0.0036 [0.000, 0.009] |
| emg-xsubject | 0.0000 [0.000, 0.000] | 0.0000 [0.000, 0.000] | 0.0000 [0.000, 0.000] | 0.0000 [0.000, 0.000] | 0.0000 [0.000, 0.000] |

## Holm correction over the six Tab. 3 tests

| test | p (plain reference) | Holm | p (day-stratified reference for B2T) | Holm |
|---|---|---|---|---|
| b2t-ours/split A | 0.0120 | 0.0719 | 0.0140 | 0.0840 |
| b2t-ours/split B | 0.2098 | 1.0000 | 0.2104 | 1.0000 |
| b2t-published/split A | 0.5395 | 1.0000 | 0.5407 | 1.0000 |
| b2t-published/split B | 0.4985 | 1.0000 | 0.4918 | 1.0000 |
| emg-xsession | 0.2987 | 1.0000 | 0.2987 | 1.0000 |
| emg-calib | 0.5964 | 1.0000 | 0.5964 | 1.0000 |

Day-stratified reference (B2T): b2t-ours/split A: observed 0.0245, mean 0.0181 (0.0135–0.0221); b2t-ours/split B: observed 0.0600, mean 0.0486 (0.0294–0.0711); b2t-published/split A: observed 0.0478, mean 0.0491 (0.0294–0.0735); b2t-published/split B: observed 0.0490, mean 0.0490 (0.0294–0.0711)

## Cluster-level tests (B2T: 14 days; sEMG: 19 participants)

| condition | difference | eWPM: positive / negative clusters | sign p | sign-flip p | wrong-commit: + / − | sign p | sign-flip p |
|---|---|---|---|---|---|---|---|
| b2t-ours | trust - never_commit | 12/1 | 0.0034 | 0.0044 | 12/0 | 0.0005 | 0.0005 |
| b2t-ours | trust - always_commit | 7/7 | 1.0000 | 0.5981 | 0/14 | 0.0001 | 0.0001 |
| b2t-ours | crc - never_commit | 13/1 | 0.0018 | 0.0005 | 9/0 | 0.0039 | 0.0039 |
| b2t-ours | no_guard - trust | 6/7 | 1.0000 | 0.7173 | 1/9 | 0.0215 | 0.0059 |
| b2t-ours | trust - gaze_only | 14/0 | 0.0001 | 0.0001 | 12/0 | 0.0005 | 0.0005 |
| b2t-ours | never_commit - gaze_only | 14/0 | 0.0001 | 0.0001 | 0/0 | 1.0000 | 1.0000 |
| b2t-published | trust - never_commit | 14/0 | 0.0001 | 0.0001 | 11/0 | 0.0010 | 0.0010 |
| b2t-published | trust - always_commit | 1/13 | 0.0018 | 0.0004 | 0/14 | 0.0001 | 0.0001 |
| b2t-published | crc - never_commit | 14/0 | 0.0001 | 0.0001 | 11/0 | 0.0010 | 0.0010 |
| b2t-published | no_guard - trust | 1/13 | 0.0018 | 0.0004 | 3/8 | 0.2266 | 0.1748 |
| b2t-published | trust - gaze_only | 14/0 | 0.0001 | 0.0001 | 11/0 | 0.0010 | 0.0010 |
| b2t-published | never_commit - gaze_only | 14/0 | 0.0001 | 0.0001 | 0/0 | 1.0000 | 1.0000 |
| emg-calib | trust - never_commit | 13/0 | 0.0002 | 0.0001 | 2/0 | 0.5000 | 0.4942 |
| emg-calib | trust - always_commit | 13/6 | 0.1671 | 0.0737 | 0/19 | 0.0000 | 0.0000 |
| emg-calib | crc - never_commit | 12/7 | 0.3593 | 0.2064 | 12/0 | 0.0005 | 0.0004 |
| emg-calib | no_guard - trust | 0/0 | 1.0000 | 1.0000 | 0/0 | 1.0000 | 1.0000 |
| emg-calib | trust - gaze_only | 18/1 | 0.0001 | 0.0000 | 2/0 | 0.5000 | 0.4942 |
| emg-calib | never_commit - gaze_only | 18/1 | 0.0001 | 0.0000 | 0/0 | 1.0000 | 1.0000 |
| emg-xsession | trust - never_commit | 5/1 | 0.2188 | 0.5609 | 2/0 | 0.5000 | 0.5010 |
| emg-xsession | trust - always_commit | 18/1 | 0.0001 | 0.0000 | 0/19 | 0.0000 | 0.0000 |
| emg-xsession | crc - never_commit | 10/5 | 0.3018 | 0.6635 | 15/0 | 0.0001 | 0.0000 |
| emg-xsession | no_guard - trust | 0/0 | 1.0000 | 1.0000 | 0/0 | 1.0000 | 1.0000 |
| emg-xsession | trust - gaze_only | 11/8 | 0.6476 | 0.0379 | 2/0 | 0.5000 | 0.5010 |
| emg-xsession | never_commit - gaze_only | 11/8 | 0.6476 | 0.0383 | 0/0 | 1.0000 | 1.0000 |
| emg-xsubject | trust - never_commit | 0/0 | 1.0000 | 1.0000 | 0/0 | 1.0000 | 1.0000 |
| emg-xsubject | trust - always_commit | 18/1 | 0.0001 | 0.0000 | 0/19 | 0.0000 | 0.0000 |
| emg-xsubject | crc - never_commit | 0/0 | 1.0000 | 1.0000 | 0/0 | 1.0000 | 1.0000 |
| emg-xsubject | no_guard - trust | 0/0 | 1.0000 | 1.0000 | 0/0 | 1.0000 | 1.0000 |
| emg-xsubject | trust - gaze_only | 8/11 | 0.6476 | 0.3499 | 0/0 | 1.0000 | 1.0000 |
| emg-xsubject | never_commit - gaze_only | 8/11 | 0.6476 | 0.3499 | 0/0 | 1.0000 | 1.0000 |

## Exact bounds for zero-event rates (items treated as independent: optimistic under clustering)

| rate | k / n | CP95 two-sided | one-sided 95 % upper | rule of three |
|---|---|---|---|---|
| B2T null-audit controls (trust, 0 of 300 per control) | 0/300 | [0.0000, 0.0122] | 0.0099 | 0.0100 |
| sEMG null-audit controls (trust, 0 of 200 per condition) | 0/200 | [0.0000, 0.0183] | 0.0149 | 0.0150 |
| MEG controls (trust, 0 of 637) | 0/637 | [0.0000, 0.0058] | 0.0047 | 0.0047 |
| sEMG test (0 of 551) | 0/551 | [0.0000, 0.0067] | 0.0054 | 0.0054 |

## Re-runs with the unified bootstrap

- ablation: results/rerun/ablation/results/ (ablation-emg-calib+emg-xsession+emg-xsubject+meg-async+b2t-ours+b2t-published.json)
- user-model: results/rerun/user-model/results/ (user-model-emg-calib+emg-xsession+emg-xsubject+b2t-ours+b2t-published+meg-async.json)
- leakage: results/rerun/leakage/results/ (leakage.json)