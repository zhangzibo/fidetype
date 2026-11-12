### val (n = 437 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.515 [0.501, 0.528] | 0.749 | 0.924 | +0.234 [+0.220, +0.248] | 0.841 | 0.518 | 0.515 | 0.504 | - |
| beam, no LM | 0.510 [0.496, 0.524] | 0.730 | 0.824 | +0.219 [+0.205, +0.234] | 0.845 | 0.513 | 0.511 | 0.500 | 0.000 |
| beam + LM, RETUNED as is | 0.506 [0.491, 0.521] | 0.747 | 0.858 | +0.240 [+0.224, +0.257] | 0.770 | 0.510 | 0.508 | 0.494 | 0.007 |
| beam + LM, val-tuned | 0.488 [0.472, 0.504] | 0.716 | 0.744 | +0.228 [+0.212, +0.245] | 0.830 | 0.490 | 0.490 | 0.475 | 0.011 |

Beam minus greedy (real MEG, paired): beam, no LM -0.004 [-0.007, -0.002]; beam + LM, RETUNED as is -0.009 [-0.015, -0.003]; beam + LM, val-tuned -0.026 [-0.033, -0.020]
CPU fp32 re-run of real MEG, greedy: 0.515 [0.501, 0.528]

### test (n = 637 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.516 [0.504, 0.527] | 0.759 | 0.922 | +0.244 [+0.232, +0.256] | 0.837 | 0.516 | 0.514 | 0.504 | - |
| beam, no LM | 0.509 [0.498, 0.520] | 0.747 | 0.810 | +0.238 [+0.226, +0.250] | 0.838 | 0.509 | 0.508 | 0.498 | 0.000 |
| beam + LM, RETUNED as is | 0.501 [0.489, 0.514] | 0.759 | 0.849 | +0.258 [+0.245, +0.271] | 0.757 | 0.503 | 0.500 | 0.489 | 0.016 |
| beam + LM, val-tuned | 0.484 [0.471, 0.498] | 0.731 | 0.743 | +0.247 [+0.234, +0.261] | 0.807 | 0.485 | 0.483 | 0.470 | 0.016 |

Beam minus greedy (real MEG, paired): beam, no LM -0.007 [-0.009, -0.004]; beam + LM, RETUNED as is -0.014 [-0.020, -0.009]; beam + LM, val-tuned -0.031 [-0.037, -0.026]
CPU fp32 re-run of real MEG, greedy: 0.516 [0.504, 0.527]

### Val grid (real MEG, CER vs target, mean over sentences)

Frame temperature fitted on real val: 2.959.

raw streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.510 | 0.523 | 0.544 | 0.579 |
| 0.05 | 0.506 | 0.514 | 0.528 | 0.559 |
| 0.1 | 0.504 | 0.508 | 0.519 | 0.540 |
| 0.15 | 0.501 | 0.504 | 0.512 | 0.529 |
| 0.25 | 0.499 | 0.498 | 0.503 | 0.514 |
| 0.5 | 0.505 | 0.496 | 0.494 | 0.498 |
| 0.75 | 0.513 | 0.499 | 0.494 | 0.493 |
| 1.0 | 0.525 | 0.509 | 0.499 | 0.494 |

calibrated streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.555 | 0.654 | 0.835 | 1.104 |
| 0.05 | 0.526 | 0.598 | 0.737 | 0.961 |
| 0.1 | 0.509 | 0.567 | 0.675 | 0.856 |
| 0.15 | 0.500 | 0.545 | 0.636 | 0.787 |
| 0.25 | 0.488 | 0.523 | 0.598 | 0.714 |
| 0.5 | 0.490 | 0.501 | 0.548 | 0.643 |
| 0.75 | 0.504 | 0.498 | 0.528 | 0.595 |
| 1.0 | 0.531 | 0.503 | 0.519 | 0.564 |

