# Leakage (G9): generated tables

## LM rebuild

Rule: edit distance <= 0.25 x target length (normalize_text form). Original training slice 600000 sentences (matches the original build: True).

- B2T: 1717 unique cue sentences; 22 have an exact copy and 310 an exact or near variant in the char-LM training slice; removed 849 training sentences; word unigram rebuilt without 910 sentences.
- sEMG: 551 test sentences; 0 exact, 295 with a near variant in the training slice (296 of 570 fit sentences); removed 2895 training sentences.

## b2t-ours

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 11.45 [10.70, 12.31] | 0.6103 [0.5680, 0.6471] | 1.000 | 0.610 [0.568, 0.647] | 0.0441 |
| original:trust | 11.55 [10.83, 12.34] | 0.0588 [0.0449, 0.0704] | 0.232 | 0.254 [0.192, 0.321] | 0.0025 |
| clean_lm:always_commit | 11.45 [10.70, 12.31] | 0.6103 [0.5680, 0.6471] | 1.000 | 0.610 [0.568, 0.647] | 0.0441 |
| clean_lm:trust | 11.55 [10.83, 12.34] | 0.0588 [0.0449, 0.0704] | 0.232 | 0.254 [0.192, 0.321] | 0.0025 |
| gaze_only | 4.08 [4.05, 4.12] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [0.00, 0.00], wrong-commit [0.0000, 0.0000]; clean_lm:always_commit-original:always_commit: eWPM [0.00, 0.00], wrong-commit [0.0000, 0.0000]; clean_lm:trust-gaze_only: eWPM [6.75, 8.28], wrong-commit [0.0449, 0.0704]; clean_lm:trust-clean_lm:always_commit: eWPM [-0.14, 0.33], wrong-commit [-0.5857, -0.5130]

Top-1 decoder (clean LM): always_commit: CER 0.095, WER 0.149, sentence acc 0.390, truth in n-best 0.623; trust: CER 0.095, WER 0.149, sentence acc 0.390, truth in n-best 0.623
Exclusion (original LM, 669 kept / 147 removed test items): original:always_commit eWPM 11.00, wc 0.6517; original:trust eWPM 11.10, wc 0.0553; gaze_only eWPM 4.04, wc 0.0000; trust − gaze [6.33, 7.89]

## b2t-published

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 19.61 [17.81, 21.32] | 0.1936 [0.1459, 0.2533] | 1.000 | 0.194 [0.146, 0.253] | 0.0245 |
| original:trust | 18.77 [17.13, 20.35] | 0.0441 [0.0272, 0.0678] | 0.473 | 0.093 [0.057, 0.146] | 0.0037 |
| clean_lm:always_commit | 19.61 [17.81, 21.32] | 0.1936 [0.1459, 0.2533] | 1.000 | 0.194 [0.146, 0.253] | 0.0245 |
| clean_lm:trust | 18.77 [17.13, 20.35] | 0.0441 [0.0272, 0.0678] | 0.473 | 0.093 [0.057, 0.146] | 0.0037 |
| gaze_only | 4.08 [4.05, 4.12] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [0.00, 0.00], wrong-commit [0.0000, 0.0000]; clean_lm:always_commit-original:always_commit: eWPM [0.00, 0.00], wrong-commit [0.0000, 0.0000]; clean_lm:trust-gaze_only: eWPM [13.03, 16.27], wrong-commit [0.0272, 0.0678]; clean_lm:trust-clean_lm:always_commit: eWPM [-1.01, -0.66], wrong-commit [-0.1870, -0.1141]

Top-1 decoder (clean LM): always_commit: CER 0.031, WER 0.043, sentence acc 0.806, truth in n-best 0.843; trust: CER 0.031, WER 0.043, sentence acc 0.806, truth in n-best 0.843
Exclusion (original LM, 669 kept / 147 removed test items): original:always_commit eWPM 19.18, wc 0.2108; original:trust eWPM 18.34, wc 0.0419; gaze_only eWPM 4.04, wc 0.0000; trust − gaze [12.55, 15.99]

## emg-calib

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 7.81 [6.66, 9.04] | 0.5408 [0.4628, 0.6211] | 1.000 | 0.541 [0.463, 0.621] | 0.0599 |
| original:trust | 8.02 [6.93, 9.19] | 0.0036 [0.0000, 0.0091] | 0.038 | 0.095 [0.000, 0.218] | 0.0000 |
| clean_lm:always_commit | 7.81 [6.66, 9.03] | 0.5445 [0.4664, 0.6246] | 1.000 | 0.544 [0.466, 0.625] | 0.0599 |
| clean_lm:trust | 7.98 [6.92, 9.15] | 0.0054 [0.0000, 0.0117] | 0.040 | 0.136 [0.000, 0.294] | 0.0000 |
| gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [-0.08, -0.00], wrong-commit [0.0000, 0.0056]; clean_lm:always_commit-original:always_commit: eWPM [-0.03, 0.01], wrong-commit [0.0000, 0.0091]; clean_lm:trust-gaze_only: eWPM [2.68, 4.85], wrong-commit [0.0000, 0.0117]; clean_lm:trust-clean_lm:always_commit: eWPM [-0.01, 0.36], wrong-commit [-0.6189, -0.4610]

Top-1 decoder (clean LM): always_commit: CER 0.123, WER 0.214, sentence acc 0.456, truth in n-best 0.632; trust: CER 0.123, WER 0.214, sentence acc 0.456, truth in n-best 0.632
LM weight: original 1.0, re-tuned with the clean LM 1.0 (fit-A CER {'0.5': 0.27219665506790885, '1.0': 0.19396116286900886, '1.5': 0.2202267370075205, '2.0': 0.27713548097429563, '3.0': 0.4028510495005051}).
Exclusion (original LM, 256 kept / 295 removed test items): original:always_commit eWPM 6.60, wc 0.6641; original:trust eWPM 6.97, wc 0.0039; gaze_only eWPM 4.15, wc 0.0000; trust − gaze [1.82, 3.92]

## emg-xsession

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 4.10 [3.56, 4.73] | 0.8820 [0.8312, 0.9281] | 1.000 | 0.882 [0.831, 0.928] | 0.1488 |
| original:trust | 4.68 [4.19, 5.25] | 0.0036 [0.0000, 0.0091] | 0.018 | 0.200 [0.000, 0.500] | 0.0000 |
| clean_lm:always_commit | 4.09 [3.55, 4.72] | 0.8838 [0.8330, 0.9310] | 1.000 | 0.884 [0.833, 0.931] | 0.1488 |
| clean_lm:trust | 4.65 [4.17, 5.23] | 0.0018 [0.0000, 0.0056] | 0.009 | 0.200 [0.000, 0.773] | 0.0000 |
| gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [-0.05, -0.01], wrong-commit [-0.0056, 0.0000]; clean_lm:always_commit-original:always_commit: eWPM [-0.03, 0.00], wrong-commit [0.0000, 0.0056]; clean_lm:trust-gaze_only: eWPM [-0.09, 0.94], wrong-commit [0.0000, 0.0056]; clean_lm:trust-clean_lm:always_commit: eWPM [0.44, 0.68], wrong-commit [-0.9305, -0.8294]

Top-1 decoder (clean LM): always_commit: CER 0.400, WER 0.581, sentence acc 0.116, truth in n-best 0.207; trust: CER 0.400, WER 0.581, sentence acc 0.116, truth in n-best 0.207
LM weight: original 1.0, re-tuned with the clean LM 1.0 (fit-A CER {'0.5': 0.5011785834549333, '1.0': 0.3802895947917836, '1.5': 0.39611628690088674, '2.0': 0.4275451790324391, '3.0': 0.518688966213941}).
Exclusion (original LM, 256 kept / 295 removed test items): original:always_commit eWPM 3.43, wc 0.9609; original:trust eWPM 4.08, wc 0.0000; gaze_only eWPM 4.15, wc 0.0000; trust − gaze [-0.37, 0.27]

## emg-xsubject

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 3.53 [3.19, 3.90] | 0.9619 [0.9419, 0.9807] | 1.000 | 0.962 [0.942, 0.981] | 0.1670 |
| original:trust | 4.08 [3.82, 4.37] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| clean_lm:always_commit | 3.54 [3.20, 3.91] | 0.9637 [0.9439, 0.9819] | 1.000 | 0.964 [0.944, 0.982] | 0.1670 |
| clean_lm:trust | 4.09 [3.83, 4.37] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [-0.01, 0.03], wrong-commit [0.0000, 0.0000]; clean_lm:always_commit-original:always_commit: eWPM [-0.01, 0.03], wrong-commit [0.0000, 0.0056]; clean_lm:trust-gaze_only: eWPM [-0.44, 0.10], wrong-commit [0.0000, 0.0000]; clean_lm:trust-clean_lm:always_commit: eWPM [0.43, 0.66], wrong-commit [-0.9819, -0.9439]

Top-1 decoder (clean LM): always_commit: CER 0.478, WER 0.680, sentence acc 0.036, truth in n-best 0.083; trust: CER 0.478, WER 0.680, sentence acc 0.036, truth in n-best 0.083
LM weight: original 1.5, re-tuned with the clean LM 1.5 (fit-A CER {'0.5': 0.5363115950162757, '1.0': 0.38893254012796047, '1.5': 0.3839937142215737, '2.0': 0.40228981928387025, '3.0': 0.489841733078909}).
Exclusion (original LM, 256 kept / 295 removed test items): original:always_commit eWPM 3.04, wc 0.9922; original:trust eWPM 3.69, wc 0.0000; gaze_only eWPM 4.15, wc 0.0000; trust − gaze [-0.66, -0.23]

