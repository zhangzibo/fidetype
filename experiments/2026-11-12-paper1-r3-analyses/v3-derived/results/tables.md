# Draft v3 derived numbers (from repeated-splits/per_split.json)

Paired eWPM per split (R = 50). 'no commit' = the same fit-A policy with lambda = +inf (the eWPM of the beta = 0.05 selective controllers, which never commit).

| condition | difference | mean [p05, p95] | share of splits > 0 |
|---|---|---|---|
| b2t-ours | plug-in (fit-A) - no commit | +0.132 [+0.075, +0.184] | 1.00 |
| b2t-ours | CRC pure (clean) - no commit | +0.136 [+0.077, +0.197] | 1.00 |
| b2t-ours | CRC max-rule (clean) - no commit | +0.125 [+0.077, +0.182] | 1.00 |
| b2t-ours | LTT pure (clean) - no commit | +0.119 [+0.066, +0.170] | 1.00 |
| b2t-ours | LTT max-rule (clean) - no commit | +0.114 [+0.063, +0.164] | 1.00 |
| b2t-ours | LTT max-rule (clean) - CRC max-rule (clean) | -0.010 [-0.038, +0.000] | 0.08 |
| b2t-ours | LTT max-rule (clean) - plug-in (fit-A) | -0.018 [-0.059, +0.000] | 0.06 |
| b2t-published | plug-in (fit-A) - no commit | +0.564 [+0.462, +0.674] | 1.00 |
| b2t-published | CRC pure (clean) - no commit | +0.627 [+0.527, +0.726] | 1.00 |
| b2t-published | CRC max-rule (clean) - no commit | +0.546 [+0.462, +0.648] | 1.00 |
| b2t-published | LTT pure (clean) - no commit | +0.534 [+0.439, +0.636] | 1.00 |
| b2t-published | LTT max-rule (clean) - no commit | +0.510 [+0.439, +0.599] | 1.00 |
| b2t-published | LTT max-rule (clean) - CRC max-rule (clean) | -0.036 [-0.116, +0.000] | 0.00 |
| b2t-published | LTT max-rule (clean) - plug-in (fit-A) | -0.055 [-0.171, +0.000] | 0.00 |
| emg-calib | plug-in (fit-A) - no commit | +0.040 [+0.011, +0.084] | 0.96 |
| emg-calib | CRC pure (clean) - no commit | +0.065 [+0.031, +0.101] | 0.98 |
| emg-calib | CRC max-rule (clean) - no commit | +0.037 [+0.011, +0.062] | 0.96 |
| emg-calib | LTT pure (clean) - no commit | +0.048 [+0.021, +0.086] | 0.98 |
| emg-calib | LTT max-rule (clean) - no commit | +0.033 [+0.011, +0.056] | 0.96 |
| emg-calib | LTT max-rule (clean) - CRC max-rule (clean) | -0.003 [-0.016, +0.000] | 0.04 |
| emg-calib | LTT max-rule (clean) - plug-in (fit-A) | -0.007 [-0.037, +0.000] | 0.00 |
| emg-xsession | plug-in (fit-A) - no commit | -0.001 [-0.011, +0.004] | 0.40 |
| emg-xsession | CRC pure (clean) - no commit | -0.006 [-0.018, +0.003] | 0.12 |
| emg-xsession | CRC max-rule (clean) - no commit | -0.001 [-0.008, +0.004] | 0.42 |
| emg-xsession | LTT pure (clean) - no commit | -0.004 [-0.014, +0.002] | 0.16 |
| emg-xsession | LTT max-rule (clean) - no commit | -0.001 [-0.007, +0.004] | 0.42 |
| emg-xsession | LTT max-rule (clean) - CRC max-rule (clean) | +0.000 [+0.000, +0.001] | 0.06 |
| emg-xsession | LTT max-rule (clean) - plug-in (fit-A) | +0.000 [+0.000, +0.000] | 0.06 |
