# Leakage (G9): generated tables

## LM rebuild

Rule: edit distance <= 0.25 x target length (normalize_text form). Original training slice 600000 sentences (matches the original build: True).

- B2T: 1717 unique cue sentences; 22 have an exact copy and 310 an exact or near variant in the char-LM training slice; removed 849 training sentences; word unigram rebuilt without 910 sentences.
- sEMG: 551 test sentences; 0 exact, 295 with a near variant in the training slice (296 of 570 fit sentences); removed 2895 training sentences.

## b2t-ours

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 11.45 [10.74, 12.34] | 0.6103 [0.5681, 0.6468] | 1.000 | 0.610 [0.568, 0.647] | 0.0441 |
| original:trust | 11.55 [10.85, 12.40] | 0.0588 [0.0445, 0.0701] | 0.232 | 0.254 [0.190, 0.318] | 0.0025 |
| clean_lm:always_commit | 11.45 [10.74, 12.34] | 0.6103 [0.5681, 0.6468] | 1.000 | 0.610 [0.568, 0.647] | 0.0441 |
| clean_lm:trust | 11.55 [10.85, 12.40] | 0.0588 [0.0445, 0.0701] | 0.232 | 0.254 [0.190, 0.318] | 0.0025 |
| gaze_only | 4.08 [4.05, 4.12] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [0.00, 0.00], wrong-commit [0.0000, 0.0000]; clean_lm:always_commit-original:always_commit: eWPM [0.00, 0.00], wrong-commit [0.0000, 0.0000]; clean_lm:trust-gaze_only: eWPM [6.78, 8.33], wrong-commit [0.0445, 0.0701]; clean_lm:trust-clean_lm:always_commit: eWPM [-0.15, 0.33], wrong-commit [-0.5848, -0.5137]

Top-1 decoder (clean LM): always_commit: CER 0.095, WER 0.149, sentence acc 0.390, truth in n-best 0.623; trust: CER 0.095, WER 0.149, sentence acc 0.390, truth in n-best 0.623
Exclusion (original LM, 669 kept / 147 removed test items): original:always_commit eWPM 11.00, wc 0.6517; original:trust eWPM 11.10, wc 0.0553; gaze_only eWPM 4.04, wc 0.0000; trust − gaze [6.30, 7.90]

## b2t-published

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 19.61 [17.82, 21.42] | 0.1936 [0.1433, 0.2522] | 1.000 | 0.194 [0.143, 0.252] | 0.0245 |
| original:trust | 18.77 [17.13, 20.46] | 0.0441 [0.0270, 0.0671] | 0.473 | 0.093 [0.056, 0.143] | 0.0037 |
| clean_lm:always_commit | 19.61 [17.82, 21.42] | 0.1936 [0.1433, 0.2522] | 1.000 | 0.194 [0.143, 0.252] | 0.0245 |
| clean_lm:trust | 18.77 [17.13, 20.46] | 0.0441 [0.0270, 0.0671] | 0.473 | 0.093 [0.056, 0.143] | 0.0037 |
| gaze_only | 4.08 [4.05, 4.12] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [0.00, 0.00], wrong-commit [0.0000, 0.0000]; clean_lm:always_commit-original:always_commit: eWPM [0.00, 0.00], wrong-commit [0.0000, 0.0000]; clean_lm:trust-gaze_only: eWPM [13.05, 16.38], wrong-commit [0.0270, 0.0671]; clean_lm:trust-clean_lm:always_commit: eWPM [-1.00, -0.66], wrong-commit [-0.1876, -0.1124]

Top-1 decoder (clean LM): always_commit: CER 0.031, WER 0.043, sentence acc 0.806, truth in n-best 0.843; trust: CER 0.031, WER 0.043, sentence acc 0.806, truth in n-best 0.843
Exclusion (original LM, 669 kept / 147 removed test items): original:always_commit eWPM 19.18, wc 0.2108; original:trust eWPM 18.34, wc 0.0419; gaze_only eWPM 4.04, wc 0.0000; trust − gaze [12.57, 16.07]

## emg-calib

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 7.81 [6.68, 9.04] | 0.5408 [0.4631, 0.6222] | 1.000 | 0.541 [0.463, 0.622] | 0.0599 |
| original:trust | 8.02 [6.96, 9.21] | 0.0036 [0.0000, 0.0091] | 0.038 | 0.095 [0.000, 0.214] | 0.0000 |
| clean_lm:always_commit | 7.81 [6.69, 9.04] | 0.5445 [0.4664, 0.6261] | 1.000 | 0.544 [0.466, 0.626] | 0.0599 |
| clean_lm:trust | 7.98 [6.95, 9.14] | 0.0054 [0.0000, 0.0113] | 0.040 | 0.136 [0.000, 0.286] | 0.0000 |
| gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [-0.08, -0.01], wrong-commit [0.0000, 0.0056]; clean_lm:always_commit-original:always_commit: eWPM [-0.02, 0.01], wrong-commit [0.0000, 0.0091]; clean_lm:trust-gaze_only: eWPM [2.72, 4.85], wrong-commit [0.0000, 0.0113]; clean_lm:trust-clean_lm:always_commit: eWPM [-0.02, 0.36], wrong-commit [-0.6203, -0.4614]

Top-1 decoder (clean LM): always_commit: CER 0.123, WER 0.214, sentence acc 0.456, truth in n-best 0.632; trust: CER 0.123, WER 0.214, sentence acc 0.456, truth in n-best 0.632
LM weight: original 1.0, re-tuned with the clean LM 1.0 (fit-A CER {'0.5': 0.27219665506790885, '1.0': 0.19396116286900886, '1.5': 0.2202267370075205, '2.0': 0.27713548097429563, '3.0': 0.4028510495005051}).
Exclusion (original LM, 256 kept / 295 removed test items): original:always_commit eWPM 6.60, wc 0.6641; original:trust eWPM 6.97, wc 0.0039; gaze_only eWPM 4.15, wc 0.0000; trust − gaze [1.79, 4.00]

## emg-xsession

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 4.10 [3.58, 4.72] | 0.8820 [0.8351, 0.9292] | 1.000 | 0.882 [0.835, 0.929] | 0.1488 |
| original:trust | 4.68 [4.22, 5.23] | 0.0036 [0.0000, 0.0091] | 0.018 | 0.200 [0.000, 0.500] | 0.0000 |
| clean_lm:always_commit | 4.09 [3.57, 4.69] | 0.8838 [0.8368, 0.9310] | 1.000 | 0.884 [0.837, 0.931] | 0.1488 |
| clean_lm:trust | 4.65 [4.19, 5.19] | 0.0018 [0.0000, 0.0056] | 0.009 | 0.200 [0.000, 1.000] | 0.0000 |
| gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [-0.05, -0.01], wrong-commit [-0.0056, 0.0000]; clean_lm:always_commit-original:always_commit: eWPM [-0.03, 0.00], wrong-commit [0.0000, 0.0054]; clean_lm:trust-gaze_only: eWPM [-0.08, 0.92], wrong-commit [0.0000, 0.0056]; clean_lm:trust-clean_lm:always_commit: eWPM [0.44, 0.68], wrong-commit [-0.9305, -0.8316]

Top-1 decoder (clean LM): always_commit: CER 0.400, WER 0.581, sentence acc 0.116, truth in n-best 0.207; trust: CER 0.400, WER 0.581, sentence acc 0.116, truth in n-best 0.207
LM weight: original 1.0, re-tuned with the clean LM 1.0 (fit-A CER {'0.5': 0.5011785834549333, '1.0': 0.3802895947917836, '1.5': 0.39611628690088674, '2.0': 0.4275451790324391, '3.0': 0.518688966213941}).
Exclusion (original LM, 256 kept / 295 removed test items): original:always_commit eWPM 3.43, wc 0.9609; original:trust eWPM 4.08, wc 0.0000; gaze_only eWPM 4.15, wc 0.0000; trust − gaze [-0.37, 0.27]

## emg-xsubject

| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |
|---|---|---|---|---|---|
| original:always_commit | 3.53 [3.20, 3.90] | 0.9619 [0.9404, 0.9805] | 1.000 | 0.962 [0.940, 0.981] | 0.1670 |
| original:trust | 4.08 [3.83, 4.36] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| clean_lm:always_commit | 3.54 [3.21, 3.91] | 0.9637 [0.9421, 0.9819] | 1.000 | 0.964 [0.942, 0.982] | 0.1670 |
| clean_lm:trust | 4.09 [3.84, 4.36] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |
| gaze_only | 4.27 [4.22, 4.32] | 0.0000 [0.0000, 0.0000] | 0.000 | —  | 0.0000 |

Paired: clean_lm:trust-original:trust: eWPM [-0.01, 0.03], wrong-commit [0.0000, 0.0000]; clean_lm:always_commit-original:always_commit: eWPM [-0.01, 0.03], wrong-commit [0.0000, 0.0054]; clean_lm:trust-gaze_only: eWPM [-0.44, 0.09], wrong-commit [0.0000, 0.0000]; clean_lm:trust-clean_lm:always_commit: eWPM [0.44, 0.66], wrong-commit [-0.9819, -0.9421]

Top-1 decoder (clean LM): always_commit: CER 0.478, WER 0.680, sentence acc 0.036, truth in n-best 0.083; trust: CER 0.478, WER 0.680, sentence acc 0.036, truth in n-best 0.083
LM weight: original 1.5, re-tuned with the clean LM 1.5 (fit-A CER {'0.5': 0.5363115950162757, '1.0': 0.38893254012796047, '1.5': 0.3839937142215737, '2.0': 0.40228981928387025, '3.0': 0.489841733078909}).
Exclusion (original LM, 256 kept / 295 removed test items): original:always_commit eWPM 3.04, wc 0.9922; original:trust eWPM 3.69, wc 0.0000; gaze_only eWPM 4.15, wc 0.0000; trust − gaze [-0.65, -0.24]

