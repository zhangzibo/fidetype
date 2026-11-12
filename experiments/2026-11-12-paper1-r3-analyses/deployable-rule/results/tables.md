# Deployable rule rows (fit-A plug-in + clean CRC / LTT, max rule)

95 % percentile CIs: bootstrap at the condition's unit (B2T day, sEMG participant, MEG two-way), seed 20261112, B = 2000, conditional on the fitted pipeline and the threshold. CP95 = exact one-sided 95 % upper bound (Clopper-Pearson, items treated as independent: optimistic under clustering).

## b2t-ours/split A

n_cal 401, n_test 816; λ plug-in 0.300, λ CRC 0.3075, λ LTT 0.000; CRC bound at λ̂ 0.0075; calibration bound at plug-in λ 0.0075 (plug-in certified: True); CRC constraint active: False; max rule changes a test decision: False (LTT: False).

| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |
|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0245 [0.015, 0.035] | 20/816 (0.0354) | 0.100 | 0.244 | 11.48 [10.79, 12.29] |
| CRC max-rule (clean) [deployable] | 0.0245 [0.015, 0.035] | 20/816 (0.0354) | 0.100 | 0.244 | 11.48 [10.79, 12.29] |
| LTT max-rule (clean) | 0.0245 [0.015, 0.035] | 20/816 (0.0354) | 0.100 | 0.244 | 11.48 [10.79, 12.29] |
| CRC pure (clean) | 0.0245 [0.015, 0.035] | 20/816 (0.0354) | 0.100 | 0.244 | 11.48 [10.79, 12.29] |
| LTT pure (clean) | 0.0270 [0.016, 0.038] | 22/816 (0.0383) | 0.104 | 0.259 | 11.48 [10.79, 12.29] |

## b2t-ours/split B

n_cal 401, n_test 816; λ plug-in 0.400, λ CRC 0.4083, λ LTT 0.430; CRC bound at λ̂ 0.0498; calibration bound at plug-in λ 0.0572 (plug-in certified: False); CRC constraint active: True; max rule changes a test decision: True (LTT: True).

| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |
|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0600 [0.049, 0.071] | 49/816 (0.0756) | 0.217 | 0.277 | 11.55 [10.85, 12.36] |
| CRC max-rule (clean) [deployable] | 0.0600 [0.049, 0.071] | 49/816 (0.0756) | 0.212 | 0.283 | 11.54 [10.84, 12.35] |
| LTT max-rule (clean) | 0.0515 [0.043, 0.059] | 42/816 (0.0661) | 0.192 | 0.268 | 11.54 [10.83, 12.34] |
| CRC pure (clean) | 0.0600 [0.049, 0.071] | 49/816 (0.0756) | 0.212 | 0.283 | 11.54 [10.84, 12.35] |
| LTT pure (clean) | 0.0515 [0.043, 0.059] | 42/816 (0.0661) | 0.192 | 0.268 | 11.54 [10.83, 12.34] |

## b2t-published/split A

n_cal 401, n_test 816; λ plug-in 0.700, λ CRC 0.6983, λ LTT 0.760; CRC bound at λ̂ 0.0498; calibration bound at plug-in λ 0.0498 (plug-in certified: True); CRC constraint active: True; max rule changes a test decision: False (LTT: True).

| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |
|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0478 [0.029, 0.071] | 39/816 (0.0620) | 0.491 | 0.097 | 18.79 [17.13, 20.37] |
| CRC max-rule (clean) [deployable] | 0.0478 [0.029, 0.071] | 39/816 (0.0620) | 0.491 | 0.097 | 18.79 [17.13, 20.37] |
| LTT max-rule (clean) | 0.0294 [0.013, 0.050] | 24/816 (0.0411) | 0.403 | 0.073 | 18.65 [17.04, 20.20] |
| CRC pure (clean) | 0.0478 [0.029, 0.071] | 39/816 (0.0620) | 0.491 | 0.097 | 18.79 [17.13, 20.37] |
| LTT pure (clean) | 0.0294 [0.013, 0.050] | 24/816 (0.0411) | 0.403 | 0.073 | 18.65 [17.04, 20.20] |

## b2t-published/split B

n_cal 401, n_test 816; λ plug-in 0.700, λ CRC 0.6841, λ LTT 0.750; CRC bound at λ̂ 0.0498; calibration bound at plug-in λ 0.0473 (plug-in certified: True); CRC constraint active: True; max rule changes a test decision: False (LTT: True).

| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |
|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0478 [0.029, 0.071] | 39/816 (0.0620) | 0.485 | 0.098 | 18.78 [17.13, 20.36] |
| CRC max-rule (clean) [deployable] | 0.0478 [0.029, 0.071] | 39/816 (0.0620) | 0.485 | 0.098 | 18.78 [17.13, 20.36] |
| LTT max-rule (clean) | 0.0306 [0.014, 0.052] | 25/816 (0.0425) | 0.415 | 0.074 | 18.68 [17.06, 20.23] |
| CRC pure (clean) | 0.0490 [0.030, 0.073] | 40/816 (0.0633) | 0.495 | 0.099 | 18.80 [17.14, 20.38] |
| LTT pure (clean) | 0.0306 [0.014, 0.052] | 25/816 (0.0425) | 0.415 | 0.074 | 18.68 [17.06, 20.23] |

## emg-calib

n_cal 143, n_test 551; λ plug-in 0.700, λ CRC 0.4480, λ LTT 0.490; CRC bound at λ̂ 0.0486; calibration bound at plug-in λ 0.0069 (plug-in certified: True); CRC constraint active: True; max rule changes a test decision: False (LTT: False).

| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |
|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0036 [0.000, 0.009] | 2/551 (0.0114) | 0.038 | 2/21 | 7.98 [6.95, 9.11] |
| CRC max-rule (clean) [deployable] | 0.0036 [0.000, 0.009] | 2/551 (0.0114) | 0.038 | 2/21 | 7.98 [6.95, 9.11] |
| LTT max-rule (clean) | 0.0036 [0.000, 0.009] | 2/551 (0.0114) | 0.038 | 2/21 | 7.98 [6.95, 9.11] |
| CRC pure (clean) | 0.0399 [0.025, 0.056] | 22/551 (0.0565) | 0.241 | 0.165 | 8.07 [6.98, 9.26] |
| LTT pure (clean) | 0.0218 [0.009, 0.036] | 12/551 (0.0350) | 0.183 | 0.119 | 8.04 [6.97, 9.21] |

## emg-xsession

n_cal 143, n_test 551; λ plug-in 0.300, λ CRC 0.2036, λ LTT 0.230; CRC bound at λ̂ 0.0486; calibration bound at plug-in λ 0.0139 (plug-in certified: True); CRC constraint active: True; max rule changes a test decision: False (LTT: False).

| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |
|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0036 [0.000, 0.009] | 2/551 (0.0114) | 0.018 | 2/10 | 4.68 [4.19, 5.25] |
| CRC max-rule (clean) [deployable] | 0.0036 [0.000, 0.009] | 2/551 (0.0114) | 0.018 | 2/10 | 4.68 [4.19, 5.25] |
| LTT max-rule (clean) | 0.0036 [0.000, 0.009] | 2/551 (0.0114) | 0.018 | 2/10 | 4.68 [4.19, 5.25] |
| CRC pure (clean) | 0.0563 [0.039, 0.074] | 31/551 (0.0752) | 0.093 | 0.608 | 4.66 [4.18, 5.24] |
| LTT pure (clean) | 0.0309 [0.021, 0.042] | 17/551 (0.0459) | 0.054 | 0.567 | 4.67 [4.18, 5.25] |

## emg-xsubject

n_cal 143, n_test 551; λ plug-in 0.300, λ CRC —, λ LTT 0.000; CRC bound at λ̂ 0.0069; calibration bound at plug-in λ 0.0069 (plug-in certified: True); CRC constraint active: False; max rule changes a test decision: False (LTT: False).

| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |
|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0000 [0.000, 0.000] | 0/551 (0.0054) | 0.000 | 0/0 | 4.08 [3.82, 4.37] |
| CRC max-rule (clean) [deployable] | 0.0000 [0.000, 0.000] | 0/551 (0.0054) | 0.000 | 0/0 | 4.08 [3.82, 4.37] |
| LTT max-rule (clean) | 0.0000 [0.000, 0.000] | 0/551 (0.0054) | 0.000 | 0/0 | 4.08 [3.82, 4.37] |
| CRC pure (clean) | 0.0000 [0.000, 0.000] | 0/551 (0.0054) | 0.000 | 0/0 | 4.08 [3.82, 4.37] |
| LTT pure (clean) | 0.0000 [0.000, 0.000] | 0/551 (0.0054) | 0.000 | 0/0 | 4.08 [3.82, 4.37] |

## meg-async

n_cal 199, n_test 637; λ plug-in 0.500, λ CRC 0.1030, λ LTT 0.110; CRC bound at λ̂ 0.0400; calibration bound at plug-in λ 0.0050 (plug-in certified: True); CRC constraint active: False; max rule changes a test decision: False (LTT: False).

| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |
|---|---|---|---|---|---|
| plug-in (fit-A) | 0.0000 [0.000, 0.000] | 0/637 (0.0047) | 0.000 | 0/0 | 3.20 [3.01, 3.44] |
| CRC max-rule (clean) [deployable] | 0.0000 [0.000, 0.000] | 0/637 (0.0047) | 0.000 | 0/0 | 3.20 [3.01, 3.44] |
| LTT max-rule (clean) | 0.0000 [0.000, 0.000] | 0/637 (0.0047) | 0.000 | 0/0 | 3.20 [3.01, 3.44] |
| CRC pure (clean) | 0.0283 [0.006, 0.061] | 18/637 (0.0416) | 0.030 | 18/19 | 3.20 [3.01, 3.43] |
| LTT pure (clean) | 0.0000 [0.000, 0.000] | 0/637 (0.0047) | 0.002 | 0/1 | 3.20 [3.01, 3.44] |

Instance-level CRC on 5 calibration sentences (199 instances). Instances of one sentence are dependent; the exchangeable unit is the sentence, so this row carries no guarantee for new sentences.

## Attribution of the B2T-ours change (test wrong-commit / commit rate)

| step | split A | split B |
|---|---|---|
| full-fit plug-in (paper trust row, 812 fit trials) | 0.0588 / 0.232 | 0.0588 / 0.232 |
| full_calibration + fitA_policy | 0.0245 / 0.099 | 0.0600 / 0.221 |
| fitA_calibration + full_policy | 0.0625 / 0.245 | 0.0588 / 0.233 |
| fitA_plugin | 0.0245 / 0.100 | 0.0600 / 0.217 |
| fitA + CRC max-rule | 0.0245 / 0.100 | 0.0600 / 0.212 |
| fitA + CRC pure | 0.0245 / 0.100 | 0.0600 / 0.212 |

Full-fit policy: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2; frame T 3.781. Fit-A policy split A: commit_p 0.3, commit_max_risk 0.1; split B: commit_p 0.4, commit_max_risk 0.3.
