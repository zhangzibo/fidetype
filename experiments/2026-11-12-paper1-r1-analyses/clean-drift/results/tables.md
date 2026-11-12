# Clean drift baseline: generated tables

α = 0.05, δ = 0.1. CI: B2T day clusters (14), sEMG participant clusters (19); 95 % percentile bootstrap, B = 2000. Online methods: warm start on the clean calibration items, test items in order (B2T: file order inside each day, days ascending; sEMG: participant by participant), delay 0 and 10.

## B2T '25 order check

Pickle keys: cue_sentence, cue_sentence_phonemes, decoded_logits, decoded_phonemes_raw, decoded_sentence, decoded_sentence_phonemes, post_implant_day, speech_duration_s, vocab_size. Keys that could hold time or order: none. Days are contiguous in file order: True; ascending: True. So the only order information is the file order inside each post-implant day.

### b2t-ours/alternate

Sizes: n_fit_A 411, n_cal_B 401, n_test 816. Frame T 3.82, sentence T 4.44.

| method | λ | test wrong-commit [CI] | commit rate | error among commits | eWPM [CI] | rate on its own calibration data | shuffled order (mean of 20) |
|---|---|---|---|---|---|---|---|
| offline plug-in gate (fit-A) | 0.3000 | 0.0245 [0.0139, 0.0346] | 0.100 | 0.244 | 11.478 [10.76, 12.29] | 0.0050 | 0.0245 |
| offline CRC (clean cal) | 0.3075 | 0.0245 [0.0139, 0.0346] | 0.100 | 0.244 | 11.478 [10.76, 12.29] | 0.0050 | 0.0245 |
| offline LTT (clean cal) | 0.0000 | 0.0270 [0.0155, 0.0383] | 0.104 | 0.259 | 11.483 [10.76, 12.30] | 0.0050 | 0.0270 |
| online window@d0 | — | 0.0245 | 0.100 | — | 11.478 | — | 0.0239 |
| online decay@d0 | — | 0.0257 | 0.103 | — | 11.482 | — | 0.0247 |
| online aci@d0 (certificate 0.0428, a-priori bound 0.0682) | — | 0.0270 | 0.104 | — | 11.483 | — | 0.0265 |
| online aci_window@d0 (certificate 0.0381) | — | 0.0245 | 0.100 | — | 11.478 | — | 0.0240 |
| online window@d10 | — | 0.0233 | 0.099 | — | 11.476 | — | — |
| online decay@d10 | — | 0.0257 | 0.103 | — | 11.482 | — | — |
| online aci@d10 (certificate 0.0433, a-priori bound 0.0808) | — | 0.0270 | 0.104 | — | 11.483 | — | — |
| online aci_window@d10 (certificate 0.0385) | — | 0.0233 | 0.099 | — | 11.476 | — | — |
| online aci@d10-noticed (certificate 0.0433, a-priori bound 0.0808) | — | 0.0270 | 0.104 | — | 11.483 | — | — |
| online aci_window@d10-noticed (certificate 0.0385) | — | 0.0233 | 0.099 | — | 11.476 | — | — |

Exchangeable reference (pool calibration + test, 1000 random splits of the same sizes, CRC on one part): test rate mean 0.0182 [p05 0.0135, p95 0.0221], share > α 0.00; observed clean CRC 0.0245, one-sided p (random split >= observed) 0.012.
Random splits inside the clean test half (408 cal): CRC mean 0.0247, p95 0.0319.
Old (reused-data) baseline, M2-16: old 0.0588; crc 0.0625; ltt 0.0466.

### b2t-published/alternate

Sizes: n_fit_A 411, n_cal_B 401, n_test 816. Frame T 3.82, sentence T 1.62.

| method | λ | test wrong-commit [CI] | commit rate | error among commits | eWPM [CI] | rate on its own calibration data | shuffled order (mean of 20) |
|---|---|---|---|---|---|---|---|
| offline plug-in gate (fit-A) | 0.7000 | 0.0478 [0.0292, 0.0713] | 0.491 | 0.097 | 18.792 [17.18, 20.47] | 0.0474 | 0.0478 |
| offline CRC (clean cal) | 0.6983 | 0.0478 [0.0292, 0.0713] | 0.491 | 0.097 | 18.792 [17.18, 20.47] | 0.0474 | 0.0478 |
| offline LTT (clean cal) | 0.7600 | 0.0294 [0.0140, 0.0514] | 0.403 | 0.073 | 18.651 [17.08, 20.26] | 0.0324 | 0.0294 |
| online window@d0 | — | 0.0429 | 0.469 | — | 18.762 | — | 0.0492 |
| online decay@d0 | — | 0.0392 | 0.452 | — | 18.738 | — | 0.0423 |
| online aci@d0 (certificate 0.0478, a-priori bound 0.0586) | — | 0.0478 | 0.488 | — | 18.788 | — | 0.0498 |
| online aci_window@d0 (certificate 0.0453) | — | 0.0453 | 0.474 | — | 18.769 | — | 0.0485 |
| online window@d10 | — | 0.0453 | 0.467 | — | 18.758 | — | — |
| online decay@d10 | — | 0.0429 | 0.452 | — | 18.738 | — | — |
| online aci@d10 (certificate 0.0471, a-priori bound 0.0711) | — | 0.0466 | 0.474 | — | 18.769 | — | — |
| online aci_window@d10 (certificate 0.0459) | — | 0.0453 | 0.466 | — | 18.757 | — | — |
| online aci@d10-noticed (certificate 0.0459, a-priori bound 0.0711) | — | 0.0502 | 0.483 | — | 18.790 | — | — |
| online aci_window@d10-noticed (certificate 0.0459) | — | 0.0502 | 0.478 | — | 18.783 | — | — |

Exchangeable reference (pool calibration + test, 1000 random splits of the same sizes, CRC on one part): test rate mean 0.0493 [p05 0.0294, p95 0.0735], share > α 0.47; observed clean CRC 0.0478, one-sided p (random split >= observed) 0.539.
Random splits inside the clean test half (408 cal): CRC mean 0.0486, p95 0.0784.
Old (reused-data) baseline, M2-16: old 0.0441; crc 0.0490; ltt 0.0404.

### b2t-ours/chrono

Sizes: n_fit_A 411, n_cal_B 401, n_test 816. Frame T 3.80, sentence T 4.54.

| method | λ | test wrong-commit [CI] | commit rate | error among commits | eWPM [CI] | rate on its own calibration data | shuffled order (mean of 20) |
|---|---|---|---|---|---|---|---|
| offline plug-in gate (fit-A) | 0.4000 | 0.0600 [0.0491, 0.0712] | 0.217 | 0.277 | 11.549 [10.82, 12.37] | 0.0549 | 0.0600 |
| offline CRC (clean cal) | 0.4083 | 0.0600 [0.0491, 0.0712] | 0.212 | 0.283 | 11.540 [10.81, 12.36] | 0.0474 | 0.0600 |
| offline LTT (clean cal) | 0.4300 | 0.0515 [0.0430, 0.0591] | 0.192 | 0.268 | 11.536 [10.81, 12.36] | 0.0349 | 0.0515 |
| online window@d0 | — | 0.0478 | 0.185 | — | 11.538 | — | 0.0494 |
| online decay@d0 | — | 0.0453 | 0.170 | — | 11.514 | — | 0.0444 |
| online aci@d0 (certificate 0.0527, a-priori bound 0.0657) | — | 0.0527 | 0.185 | — | 11.510 | — | 0.0509 |
| online aci_window@d0 (certificate 0.0490) | — | 0.0490 | 0.188 | — | 11.536 | — | 0.0496 |
| online window@d10 | — | 0.0490 | 0.186 | — | 11.542 | — | — |
| online decay@d10 | — | 0.0441 | 0.170 | — | 11.521 | — | — |
| online aci@d10 (certificate 0.0521, a-priori bound 0.0783) | — | 0.0515 | 0.186 | — | 11.526 | — | — |
| online aci_window@d10 (certificate 0.0496) | — | 0.0490 | 0.184 | — | 11.538 | — | — |
| online aci@d10-noticed (certificate 0.0509, a-priori bound 0.0783) | — | 0.0527 | 0.195 | — | 11.539 | — | — |
| online aci_window@d10-noticed (certificate 0.0484) | — | 0.0502 | 0.186 | — | 11.532 | — | — |

Exchangeable reference (pool calibration + test, 1000 random splits of the same sizes, CRC on one part): test rate mean 0.0487 [p05 0.0294, p95 0.0711], share > α 0.47; observed clean CRC 0.0600, one-sided p (random split >= observed) 0.210.
Random splits inside the clean test half (408 cal): CRC mean 0.0483, p95 0.0737.
Old (reused-data) baseline, M2-16: old 0.0588; crc 0.0625; ltt 0.0466.

### b2t-published/chrono

Sizes: n_fit_A 411, n_cal_B 401, n_test 816. Frame T 3.80, sentence T 1.65.

| method | λ | test wrong-commit [CI] | commit rate | error among commits | eWPM [CI] | rate on its own calibration data | shuffled order (mean of 20) |
|---|---|---|---|---|---|---|---|
| offline plug-in gate (fit-A) | 0.7000 | 0.0478 [0.0292, 0.0713] | 0.485 | 0.098 | 18.784 [17.18, 20.47] | 0.0449 | 0.0478 |
| offline CRC (clean cal) | 0.6841 | 0.0490 [0.0297, 0.0735] | 0.495 | 0.099 | 18.797 [17.18, 20.48] | 0.0474 | 0.0490 |
| offline LTT (clean cal) | 0.7500 | 0.0306 [0.0151, 0.0526] | 0.415 | 0.074 | 18.681 [17.10, 20.32] | 0.0324 | 0.0306 |
| online window@d0 | — | 0.0441 | 0.471 | — | 18.764 | — | 0.0485 |
| online decay@d0 | — | 0.0392 | 0.451 | — | 18.736 | — | 0.0417 |
| online aci@d0 (certificate 0.0478, a-priori bound 0.0590) | — | 0.0478 | 0.491 | — | 18.792 | — | 0.0499 |
| online aci_window@d0 (certificate 0.0453) | — | 0.0453 | 0.477 | — | 18.772 | — | 0.0484 |
| online window@d10 | — | 0.0466 | 0.467 | — | 18.758 | — | — |
| online decay@d10 | — | 0.0429 | 0.455 | — | 18.741 | — | — |
| online aci@d10 (certificate 0.0471, a-priori bound 0.0715) | — | 0.0466 | 0.464 | — | 18.755 | — | — |
| online aci_window@d10 (certificate 0.0459) | — | 0.0453 | 0.475 | — | 18.771 | — | — |
| online aci@d10-noticed (certificate 0.0459, a-priori bound 0.0715) | — | 0.0502 | 0.485 | — | 18.793 | — | — |
| online aci_window@d10-noticed (certificate 0.0459) | — | 0.0502 | 0.488 | — | 18.797 | — | — |

Exchangeable reference (pool calibration + test, 1000 random splits of the same sizes, CRC on one part): test rate mean 0.0495 [p05 0.0306, p95 0.0736], share > α 0.46; observed clean CRC 0.0490, one-sided p (random split >= observed) 0.499.
Random splits inside the clean test half (408 cal): CRC mean 0.0485, p95 0.0784.
Old (reused-data) baseline, M2-16: old 0.0441; crc 0.0490; ltt 0.0404.

### emg-xsession

Sizes: n_fit_A 285, n_grid_B1 142, n_cal_B2 143, n_test 551. Frame T 1.78, sentence T 5.42.

| method | λ | test wrong-commit [CI] | commit rate | error among commits | eWPM [CI] | rate on its own calibration data | shuffled order (mean of 20) |
|---|---|---|---|---|---|---|---|
| offline plug-in gate (fit-A) | 0.3000 | 0.0036 [0.0000, 0.0091] | 0.018 | 0.200 | 4.677 [4.20, 5.28] | 0.0070 | 0.0036 |
| offline CRC (clean cal) | 0.2036 | 0.0563 [0.0395, 0.0737] | 0.093 | 0.608 | 4.663 [4.18, 5.27] | 0.0420 | 0.0563 |
| offline LTT (clean cal) | 0.2300 | 0.0309 [0.0200, 0.0417] | 0.054 | 0.567 | 4.667 [4.19, 5.27] | 0.0210 | 0.0309 |
| online window@d0 | — | 0.0472 | 0.076 | — | 4.672 | — | 0.0481 |
| online decay@d0 | — | 0.0381 | 0.065 | — | 4.669 | — | 0.0424 |
| online aci@d0 (certificate 0.0526, a-priori bound 0.0807) | — | 0.0526 | 0.085 | — | 4.665 | — | 0.0506 |
| online aci_window@d0 (certificate 0.0490) | — | 0.0490 | 0.080 | — | 4.664 | — | 0.0486 |
| online window@d10 | — | 0.0454 | 0.078 | — | 4.672 | — | — |
| online decay@d10 | — | 0.0381 | 0.071 | — | 4.662 | — | — |
| online aci@d10 (certificate 0.0499, a-priori bound 0.0998) | — | 0.0508 | 0.078 | — | 4.673 | — | — |
| online aci_window@d10 (certificate 0.0462) | — | 0.0472 | 0.085 | — | 4.674 | — | — |
| online aci@d10-noticed (certificate 0.0499, a-priori bound 0.0998) | — | 0.0581 | 0.091 | — | 4.661 | — | — |
| online aci_window@d10-noticed (certificate 0.0462) | — | 0.0526 | 0.089 | — | 4.671 | — | — |

Exchangeable reference (pool calibration + test, 1000 random splits of the same sizes, CRC on one part): test rate mean 0.0451 [p05 0.0181, p95 0.0799], share > α 0.34; observed clean CRC 0.0563, one-sided p (random split >= observed) 0.299.
Random splits inside the clean test half (275 cal): CRC mean 0.0456, p95 0.0763.
Old (reused-data) baseline, M2-16: old 0.0036; crc 0.0635; ltt 0.0472.

### emg-calib

Sizes: n_fit_A 285, n_grid_B1 142, n_cal_B2 143, n_test 551. Frame T 1.25, sentence T 2.42.

| method | λ | test wrong-commit [CI] | commit rate | error among commits | eWPM [CI] | rate on its own calibration data | shuffled order (mean of 20) |
|---|---|---|---|---|---|---|---|
| offline plug-in gate (fit-A) | 0.7000 | 0.0036 [0.0000, 0.0091] | 0.038 | 0.095 | 7.977 [6.83, 9.09] | 0.0000 | 0.0036 |
| offline CRC (clean cal) | 0.4480 | 0.0399 [0.0244, 0.0561] | 0.241 | 0.165 | 8.072 [6.86, 9.26] | 0.0420 | 0.0399 |
| offline LTT (clean cal) | 0.4900 | 0.0218 [0.0091, 0.0357] | 0.183 | 0.119 | 8.039 [6.86, 9.20] | 0.0210 | 0.0218 |
| online window@d0 | — | 0.0490 | 0.243 | — | 8.048 | — | 0.0489 |
| online decay@d0 | — | 0.0454 | 0.230 | — | 8.039 | — | 0.0423 |
| online aci@d0 (certificate 0.0490, a-priori bound 0.0719) | — | 0.0490 | 0.243 | — | 8.049 | — | 0.0498 |
| online aci_window@d0 (certificate 0.0490) | — | 0.0490 | 0.249 | — | 8.043 | — | 0.0496 |
| online window@d10 | — | 0.0472 | 0.243 | — | 8.048 | — | — |
| online decay@d10 | — | 0.0363 | 0.225 | — | 8.045 | — | — |
| online aci@d10 (certificate 0.0518, a-priori bound 0.0907) | — | 0.0508 | 0.241 | — | 8.050 | — | — |
| online aci_window@d10 (certificate 0.0518) | — | 0.0508 | 0.252 | — | 8.047 | — | — |
| online aci@d10-noticed (certificate 0.0499, a-priori bound 0.0907) | — | 0.0563 | 0.261 | — | 8.074 | — | — |
| online aci_window@d10-noticed (certificate 0.0499) | — | 0.0563 | 0.261 | — | 8.053 | — | — |

Exchangeable reference (pool calibration + test, 1000 random splits of the same sizes, CRC on one part): test rate mean 0.0468 [p05 0.0181, p95 0.0818], share > α 0.37; observed clean CRC 0.0399, one-sided p (random split >= observed) 0.596.
Random splits inside the clean test half (275 cal): CRC mean 0.0456, p95 0.0763.
Old (reused-data) baseline, M2-16: old 0.0036; crc 0.0417; ltt 0.0254.

### emg-xsubject

Sizes: n_fit_A 285, n_grid_B1 142, n_cal_B2 143, n_test 551. Frame T 2.17, sentence T 20.00.

| method | λ | test wrong-commit [CI] | commit rate | error among commits | eWPM [CI] | rate on its own calibration data | shuffled order (mean of 20) |
|---|---|---|---|---|---|---|---|
| offline plug-in gate (fit-A) | 0.3000 | 0.0000 [0.0000, 0.0000] | 0.000 | — | 4.080 [3.81, 4.35] | 0.0000 | 0.0000 |
| offline CRC (clean cal) | — | 0.0000 [0.0000, 0.0000] | 0.000 | — | 4.080 [3.81, 4.35] | 0.0000 | 0.0000 |
| offline LTT (clean cal) | 0.0000 | 0.0000 [0.0000, 0.0000] | 0.000 | — | 4.080 [3.81, 4.35] | 0.0000 | 0.0000 |
| online window@d0 | — | 0.0000 | 0.000 | — | 4.080 | — | 0.0000 |
| online decay@d0 | — | 0.0000 | 0.000 | — | 4.080 | — | 0.0000 |
| online aci@d0 (certificate 0.0137, a-priori bound 0.0518) | — | 0.0000 | 0.000 | — | 4.080 | — | 0.0000 |
| online aci_window@d0 (certificate 0.0319) | — | 0.0000 | 0.000 | — | 4.080 | — | 0.0000 |
| online window@d10 | — | 0.0000 | 0.000 | — | 4.080 | — | — |
| online decay@d10 | — | 0.0000 | 0.000 | — | 4.080 | — | — |
| online aci@d10 (certificate 0.0130, a-priori bound 0.0703) | — | 0.0000 | 0.000 | — | 4.080 | — | — |
| online aci_window@d10 (certificate 0.0315) | — | 0.0000 | 0.000 | — | 4.080 | — | — |
| online aci@d10-noticed (certificate 0.0130, a-priori bound 0.0703) | — | 0.0000 | 0.000 | — | 4.080 | — | — |
| online aci_window@d10-noticed (certificate 0.0315) | — | 0.0000 | 0.000 | — | 4.080 | — | — |

Exchangeable reference (pool calibration + test, 1000 random splits of the same sizes, CRC on one part): test rate mean 0.0000 [p05 0.0000, p95 0.0000], share > α 0.00; observed clean CRC 0.0000, one-sided p (random split >= observed) 1.000.
Random splits inside the clean test half (275 cal): CRC mean 0.0000, p95 0.0000.
Old (reused-data) baseline, M2-16: old 0.0000; crc 0.0000; ltt 0.0000.

