# Population risk and exceedance shares: tables

α = 0.05, δ = 0.1. Share > α with exact Clopper-Pearson 95 % CI. 'with-replacement': calibration drawn i.i.d. from the pool; the pool risk of the chosen threshold is the exact population risk (theory: LTT share ≤ δ, CRC mean ≤ α). 'incl-cal' is the App. R computation (biased low). 'held-out' contains test-sampling noise.

## (a) App. R pools (full-fit pipeline, test pool)

### b2t-ours (pool 816)

| n_cal | design | rule | mean risk | share > α [CP95] | p95 |
|---|---|---|---|---|---|
| 100 | incl-cal | CRC pure | 0.0450 | 0.348 [0.327, 0.369] | 0.0834 |
| 100 | incl-cal | LTT pure | 0.0172 | 0.021 [0.015, 0.028] | 0.0429 |
| 100 | incl-cal | CRC max | 0.0419 | 0.348 [0.327, 0.369] | 0.0588 |
| 100 | incl-cal | LTT max | 0.0172 | 0.021 [0.015, 0.028] | 0.0429 |
| 100 | held-out | CRC pure | 0.0457 | 0.385 [0.363, 0.406] | 0.0895 |
| 100 | held-out | LTT pure | 0.0183 | 0.046 [0.038, 0.057] | 0.0475 |
| 100 | held-out | CRC max | 0.0425 | 0.385 [0.363, 0.406] | 0.0642 |
| 100 | held-out | LTT max | 0.0182 | 0.046 [0.038, 0.057] | 0.0475 |
| 100 | with-replacement | CRC pure | 0.0453 | 0.352 [0.331, 0.373] | 0.0833 |
| 100 | with-replacement | LTT pure | 0.0180 | 0.029 [0.022, 0.037] | 0.0453 |
| 100 | with-replacement | CRC max | 0.0418 | 0.352 [0.331, 0.373] | 0.0588 |
| 100 | with-replacement | LTT max | 0.0179 | 0.029 [0.022, 0.037] | 0.0453 |
| 408 | incl-cal | CRC pure | 0.0472 | 0.325 [0.304, 0.346] | 0.0600 |
| 408 | incl-cal | LTT pure | 0.0337 | 0.011 [0.007, 0.017] | 0.0466 |
| 408 | incl-cal | CRC max | 0.0469 | 0.325 [0.304, 0.346] | 0.0588 |
| 408 | incl-cal | LTT max | 0.0336 | 0.011 [0.007, 0.017] | 0.0466 |
| 408 | held-out | CRC pure | 0.0479 | 0.419 [0.397, 0.441] | 0.0735 |
| 408 | held-out | LTT pure | 0.0347 | 0.151 [0.136, 0.167] | 0.0588 |
| 408 | held-out | CRC max | 0.0475 | 0.419 [0.397, 0.441] | 0.0711 |
| 408 | held-out | LTT max | 0.0347 | 0.151 [0.136, 0.167] | 0.0588 |
| 408 | with-replacement | CRC pure | 0.0475 | 0.373 [0.352, 0.395] | 0.0650 |
| 408 | with-replacement | LTT pure | 0.0347 | 0.047 [0.038, 0.057] | 0.0478 |
| 408 | with-replacement | CRC max | 0.0466 | 0.373 [0.352, 0.395] | 0.0588 |
| 408 | with-replacement | LTT max | 0.0347 | 0.047 [0.038, 0.057] | 0.0478 |

### b2t-published (pool 816)

| n_cal | design | rule | mean risk | share > α [CP95] | p95 |
|---|---|---|---|---|---|
| 100 | incl-cal | CRC pure | 0.0454 | 0.350 [0.330, 0.372] | 0.0772 |
| 100 | incl-cal | LTT pure | 0.0174 | 0.025 [0.018, 0.032] | 0.0417 |
| 100 | incl-cal | CRC max | 0.0376 | 0.000 [0.000, 0.002] | 0.0441 |
| 100 | incl-cal | LTT max | 0.0170 | 0.000 [0.000, 0.002] | 0.0417 |
| 100 | held-out | CRC pure | 0.0462 | 0.386 [0.365, 0.408] | 0.0824 |
| 100 | held-out | LTT pure | 0.0186 | 0.038 [0.031, 0.048] | 0.0461 |
| 100 | held-out | CRC max | 0.0380 | 0.008 [0.005, 0.013] | 0.0475 |
| 100 | held-out | LTT max | 0.0181 | 0.008 [0.005, 0.013] | 0.0461 |
| 100 | with-replacement | CRC pure | 0.0454 | 0.341 [0.320, 0.362] | 0.0821 |
| 100 | with-replacement | LTT pure | 0.0179 | 0.025 [0.019, 0.033] | 0.0441 |
| 100 | with-replacement | CRC max | 0.0372 | 0.000 [0.000, 0.002] | 0.0441 |
| 100 | with-replacement | LTT max | 0.0173 | 0.000 [0.000, 0.002] | 0.0441 |
| 408 | incl-cal | CRC pure | 0.0474 | 0.328 [0.307, 0.349] | 0.0600 |
| 408 | incl-cal | LTT pure | 0.0329 | 0.009 [0.006, 0.015] | 0.0441 |
| 408 | incl-cal | CRC max | 0.0426 | 0.000 [0.000, 0.002] | 0.0441 |
| 408 | incl-cal | LTT max | 0.0326 | 0.000 [0.000, 0.002] | 0.0441 |
| 408 | held-out | CRC pure | 0.0483 | 0.422 [0.401, 0.444] | 0.0735 |
| 408 | held-out | LTT pure | 0.0340 | 0.120 [0.107, 0.136] | 0.0565 |
| 408 | held-out | CRC max | 0.0428 | 0.196 [0.178, 0.214] | 0.0564 |
| 408 | held-out | LTT max | 0.0336 | 0.120 [0.107, 0.136] | 0.0564 |
| 408 | with-replacement | CRC pure | 0.0479 | 0.384 [0.362, 0.405] | 0.0650 |
| 408 | with-replacement | LTT pure | 0.0339 | 0.041 [0.033, 0.051] | 0.0490 |
| 408 | with-replacement | CRC max | 0.0417 | 0.000 [0.000, 0.002] | 0.0441 |
| 408 | with-replacement | LTT max | 0.0331 | 0.000 [0.000, 0.002] | 0.0441 |

### emg-calib (pool 551)

| n_cal | design | rule | mean risk | share > α [CP95] | p95 |
|---|---|---|---|---|---|
| 100 | incl-cal | CRC pure | 0.0443 | 0.308 [0.288, 0.329] | 0.0780 |
| 100 | incl-cal | LTT pure | 0.0167 | 0.017 [0.012, 0.024] | 0.0381 |
| 100 | incl-cal | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 100 | incl-cal | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 100 | held-out | CRC pure | 0.0453 | 0.379 [0.358, 0.401] | 0.0865 |
| 100 | held-out | LTT pure | 0.0182 | 0.030 [0.023, 0.038] | 0.0443 |
| 100 | held-out | CRC max | 0.0037 | 0.000 [0.000, 0.002] | 0.0044 |
| 100 | held-out | LTT max | 0.0037 | 0.000 [0.000, 0.002] | 0.0044 |
| 100 | with-replacement | CRC pure | 0.0448 | 0.334 [0.313, 0.355] | 0.0799 |
| 100 | with-replacement | LTT pure | 0.0179 | 0.030 [0.023, 0.039] | 0.0381 |
| 100 | with-replacement | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 100 | with-replacement | LTT max | 0.0035 | 0.000 [0.000, 0.002] | 0.0036 |
| 275 | incl-cal | CRC pure | 0.0453 | 0.272 [0.252, 0.292] | 0.0618 |
| 275 | incl-cal | LTT pure | 0.0299 | 0.021 [0.015, 0.028] | 0.0454 |
| 275 | incl-cal | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 275 | incl-cal | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 275 | held-out | CRC pure | 0.0470 | 0.452 [0.430, 0.474] | 0.0799 |
| 275 | held-out | LTT pure | 0.0319 | 0.099 [0.086, 0.113] | 0.0616 |
| 275 | held-out | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0072 |
| 275 | held-out | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0072 |
| 275 | with-replacement | CRC pure | 0.0447 | 0.300 [0.280, 0.321] | 0.0672 |
| 275 | with-replacement | LTT pure | 0.0300 | 0.051 [0.042, 0.062] | 0.0508 |
| 275 | with-replacement | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 275 | with-replacement | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |

### emg-xsession (pool 551)

| n_cal | design | rule | mean risk | share > α [CP95] | p95 |
|---|---|---|---|---|---|
| 100 | incl-cal | CRC pure | 0.0426 | 0.324 [0.303, 0.344] | 0.0744 |
| 100 | incl-cal | LTT pure | 0.0153 | 0.009 [0.006, 0.015] | 0.0381 |
| 100 | incl-cal | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 100 | incl-cal | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 100 | held-out | CRC pure | 0.0432 | 0.343 [0.322, 0.364] | 0.0820 |
| 100 | held-out | LTT pure | 0.0168 | 0.033 [0.025, 0.041] | 0.0443 |
| 100 | held-out | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0044 |
| 100 | held-out | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0044 |
| 100 | with-replacement | CRC pure | 0.0423 | 0.309 [0.289, 0.330] | 0.0780 |
| 100 | with-replacement | LTT pure | 0.0163 | 0.013 [0.009, 0.020] | 0.0381 |
| 100 | with-replacement | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 100 | with-replacement | LTT max | 0.0035 | 0.000 [0.000, 0.002] | 0.0036 |
| 275 | incl-cal | CRC pure | 0.0445 | 0.247 [0.229, 0.267] | 0.0599 |
| 275 | incl-cal | LTT pure | 0.0282 | 0.000 [0.000, 0.002] | 0.0381 |
| 275 | incl-cal | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 275 | incl-cal | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 275 | held-out | CRC pure | 0.0453 | 0.354 [0.333, 0.375] | 0.0761 |
| 275 | held-out | LTT pure | 0.0300 | 0.100 [0.087, 0.113] | 0.0507 |
| 275 | held-out | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0072 |
| 275 | held-out | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0072 |
| 275 | with-replacement | CRC pure | 0.0441 | 0.302 [0.282, 0.323] | 0.0653 |
| 275 | with-replacement | LTT pure | 0.0284 | 0.008 [0.005, 0.013] | 0.0472 |
| 275 | with-replacement | CRC max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |
| 275 | with-replacement | LTT max | 0.0036 | 0.000 [0.000, 0.002] | 0.0036 |

### emg-xsubject (pool 551)

| n_cal | design | rule | mean risk | share > α [CP95] | p95 |
|---|---|---|---|---|---|
| 100 | incl-cal | CRC pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | incl-cal | LTT pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | incl-cal | CRC max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | incl-cal | LTT max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | held-out | CRC pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | held-out | LTT pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | held-out | CRC max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | held-out | LTT max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | with-replacement | CRC pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | with-replacement | LTT pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | with-replacement | CRC max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 100 | with-replacement | LTT max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | incl-cal | CRC pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | incl-cal | LTT pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | incl-cal | CRC max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | incl-cal | LTT max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | held-out | CRC pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | held-out | LTT pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | held-out | CRC max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | held-out | LTT max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | with-replacement | CRC pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | with-replacement | LTT pure | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | with-replacement | CRC max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |
| 275 | with-replacement | LTT max | 0.0000 | 0.000 [0.000, 0.002] | 0.0000 |

## (b, c) Repeated splits: test-set exceedance and exact population risk (with replacement)

### b2t-ours/R200

| rule | test: splits > α | share [CP95] | population (w.r.): mean | share > α [CP95] | max per-split share |
|---|---|---|---|---|---|
| CRC pure | 88/200 | 0.440 [0.370, 0.512] | 0.0476 | 0.3874 [0.3826, 0.3921] | 0.495 |
| LTT pure | 29/200 | 0.145 [0.099, 0.202] | 0.0348 | 0.0605 [0.0582, 0.0629] | 0.120 |
| CRC max | 37/200 | 0.185 [0.134, 0.246] | 0.0371 | 0.1231 [0.1199, 0.1264] | 0.490 |
| LTT max | 15/200 | 0.075 [0.043, 0.121] | 0.0310 | 0.0197 [0.0183, 0.0211] | 0.120 |

Exact McNemar (test exceedance, paired by split): LTT max vs CRC max: 0 vs 22 discordant, p = 4.77e-07; LTT pure vs CRC pure: 0 vs 59, p = 3.47e-18.

### b2t-ours/R50

| rule | test: splits > α | share [CP95] | population (w.r.): mean | share > α [CP95] | max per-split share |
|---|---|---|---|---|---|
| CRC pure | 17/50 | 0.340 [0.212, 0.488] | 0.0476 | 0.3915 [0.3819, 0.4011] | 0.490 |
| LTT pure | 8/50 | 0.160 [0.072, 0.291] | 0.0347 | 0.0597 [0.0551, 0.0645] | 0.105 |
| CRC max | 7/50 | 0.140 [0.058, 0.267] | 0.0386 | 0.1685 [0.1612, 0.1760] | 0.490 |
| LTT max | 4/50 | 0.080 [0.022, 0.192] | 0.0316 | 0.0257 [0.0227, 0.0290] | 0.100 |

Exact McNemar (test exceedance, paired by split): LTT max vs CRC max: 0 vs 3 discordant, p = 0.25; LTT pure vs CRC pure: 0 vs 9, p = 0.00391.

### b2t-published/R200

| rule | test: splits > α | share [CP95] | population (w.r.): mean | share > α [CP95] | max per-split share |
|---|---|---|---|---|---|
| CRC pure | 85/200 | 0.425 [0.356, 0.497] | 0.0484 | 0.4083 [0.4035, 0.4132] | 0.515 |
| LTT pure | 23/200 | 0.115 [0.074, 0.168] | 0.0331 | 0.0585 [0.0563, 0.0609] | 0.125 |
| CRC max | 35/200 | 0.175 [0.125, 0.235] | 0.0359 | 0.0914 [0.0886, 0.0943] | 0.490 |
| LTT max | 11/200 | 0.055 [0.028, 0.096] | 0.0295 | 0.0157 [0.0145, 0.0169] | 0.110 |

Exact McNemar (test exceedance, paired by split): LTT max vs CRC max: 0 vs 24 discordant, p = 1.19e-07; LTT pure vs CRC pure: 0 vs 62, p = 4.34e-19.

### b2t-published/R50

| rule | test: splits > α | share [CP95] | population (w.r.): mean | share > α [CP95] | max per-split share |
|---|---|---|---|---|---|
| CRC pure | 21/50 | 0.420 [0.282, 0.568] | 0.0483 | 0.4037 [0.3941, 0.4134] | 0.515 |
| LTT pure | 3/50 | 0.060 [0.013, 0.165] | 0.0333 | 0.0579 [0.0534, 0.0627] | 0.120 |
| CRC max | 7/50 | 0.140 [0.058, 0.267] | 0.0361 | 0.0740 [0.0689, 0.0793] | 0.455 |
| LTT max | 1/50 | 0.020 [0.001, 0.106] | 0.0298 | 0.0137 [0.0115, 0.0162] | 0.110 |

Exact McNemar (test exceedance, paired by split): LTT max vs CRC max: 0 vs 6 discordant, p = 0.0312; LTT pure vs CRC pure: 0 vs 18, p = 7.63e-06.

### emg-calib/R50

| rule | test: splits > α | share [CP95] | population (w.r.): mean | share > α [CP95] | max per-split share |
|---|---|---|---|---|---|
| CRC pure | 3/50 | 0.060 [0.013, 0.165] | 0.0412 | 0.2830 [0.2742, 0.2919] | 0.380 |
| LTT pure | 0/50 | 0.000 [0.000, 0.071] | 0.0274 | 0.0730 [0.0680, 0.0783] | 0.135 |
| CRC max | 0/50 | 0.000 [0.000, 0.071] | 0.0157 | 0.0000 [0.0000, 0.0004] | 0.000 |
| LTT max | 0/50 | 0.000 [0.000, 0.071] | 0.0139 | 0.0000 [0.0000, 0.0004] | 0.000 |

Exact McNemar (test exceedance, paired by split): LTT max vs CRC max: 0 vs 0 discordant, p = 1; LTT pure vs CRC pure: 0 vs 3, p = 0.25.

### emg-xsession/R50

| rule | test: splits > α | share [CP95] | population (w.r.): mean | share > α [CP95] | max per-split share |
|---|---|---|---|---|---|
| CRC pure | 7/50 | 0.140 [0.058, 0.267] | 0.0261 | 0.1582 [0.1511, 0.1655] | 0.320 |
| LTT pure | 1/50 | 0.020 [0.001, 0.106] | 0.0175 | 0.0404 [0.0366, 0.0444] | 0.120 |
| CRC max | 0/50 | 0.000 [0.000, 0.071] | 0.0074 | 0.0085 [0.0068, 0.0105] | 0.215 |
| LTT max | 0/50 | 0.000 [0.000, 0.071] | 0.0065 | 0.0023 [0.0015, 0.0034] | 0.060 |

Exact McNemar (test exceedance, paired by split): LTT max vs CRC max: 0 vs 0 discordant, p = 1; LTT pure vs CRC pure: 0 vs 6, p = 0.0312.

### emg-xsubject/R50

| rule | test: splits > α | share [CP95] | population (w.r.): mean | share > α [CP95] | max per-split share |
|---|---|---|---|---|---|
| CRC pure | 0/50 | 0.000 [0.000, 0.071] | 0.0000 | 0.0000 [0.0000, 0.0004] | 0.000 |
| LTT pure | 0/50 | 0.000 [0.000, 0.071] | 0.0000 | 0.0000 [0.0000, 0.0004] | 0.000 |
| CRC max | 0/50 | 0.000 [0.000, 0.071] | 0.0000 | 0.0000 [0.0000, 0.0004] | 0.000 |
| LTT max | 0/50 | 0.000 [0.000, 0.071] | 0.0000 | 0.0000 [0.0000, 0.0004] | 0.000 |

Exact McNemar (test exceedance, paired by split): LTT max vs CRC max: 0 vs 0 discordant, p = 1; LTT pure vs CRC pure: 0 vs 0, p = 1.
