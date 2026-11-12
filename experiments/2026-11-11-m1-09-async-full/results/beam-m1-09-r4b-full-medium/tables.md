### val (n = 437 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.512 [0.498, 0.526] | 0.755 | 0.924 | +0.243 [+0.229, +0.258] | 0.838 | 0.515 | 0.514 | 0.514 | - |
| beam, no LM | 0.508 [0.494, 0.522] | 0.737 | 0.853 | +0.229 [+0.215, +0.244] | 0.842 | 0.510 | 0.510 | 0.510 | 0.000 |
| beam + LM, RETUNED as is | 0.505 [0.489, 0.520] | 0.750 | 0.854 | +0.245 [+0.229, +0.262] | 0.776 | 0.509 | 0.508 | 0.508 | 0.007 |
| beam + LM, val-tuned | 0.485 [0.469, 0.500] | 0.717 | 0.781 | +0.232 [+0.216, +0.249] | 0.834 | 0.488 | 0.487 | 0.487 | 0.009 |

Beam minus greedy (real MEG, paired): beam, no LM -0.004 [-0.006, -0.002]; beam + LM, RETUNED as is -0.007 [-0.013, -0.001]; beam + LM, val-tuned -0.027 [-0.034, -0.021]
CPU fp32 re-run of real MEG, greedy: 0.512 [0.498, 0.526]

### test (n = 637 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.506 [0.495, 0.518] | 0.760 | 0.925 | +0.254 [+0.241, +0.265] | 0.842 | 0.508 | 0.505 | 0.505 | - |
| beam, no LM | 0.500 [0.489, 0.511] | 0.745 | 0.845 | +0.245 [+0.233, +0.257] | 0.845 | 0.501 | 0.499 | 0.499 | 0.000 |
| beam + LM, RETUNED as is | 0.493 [0.480, 0.505] | 0.759 | 0.853 | +0.266 [+0.253, +0.279] | 0.755 | 0.496 | 0.489 | 0.489 | 0.011 |
| beam + LM, val-tuned | 0.475 [0.461, 0.489] | 0.732 | 0.771 | +0.257 [+0.243, +0.271] | 0.809 | 0.477 | 0.473 | 0.473 | 0.009 |

Beam minus greedy (real MEG, paired): beam, no LM -0.006 [-0.008, -0.005]; beam + LM, RETUNED as is -0.014 [-0.019, -0.009]; beam + LM, val-tuned -0.031 [-0.037, -0.025]
CPU fp32 re-run of real MEG, greedy: 0.506 [0.495, 0.518]

### Val grid (real MEG, CER vs target, mean over sentences)

Frame temperature fitted on real val: 3.285.

raw streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.508 | 0.514 | 0.527 | 0.554 |
| 0.05 | 0.505 | 0.508 | 0.517 | 0.538 |
| 0.1 | 0.501 | 0.503 | 0.511 | 0.527 |
| 0.15 | 0.500 | 0.500 | 0.505 | 0.517 |
| 0.25 | 0.499 | 0.497 | 0.500 | 0.504 |
| 0.5 | 0.505 | 0.496 | 0.492 | 0.493 |
| 0.75 | 0.509 | 0.501 | 0.494 | 0.492 |
| 1.0 | 0.521 | 0.507 | 0.499 | 0.492 |

calibrated streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.545 | 0.641 | 0.811 | 1.073 |
| 0.05 | 0.519 | 0.588 | 0.719 | 0.935 |
| 0.1 | 0.504 | 0.558 | 0.660 | 0.829 |
| 0.15 | 0.496 | 0.539 | 0.625 | 0.763 |
| 0.25 | 0.485 | 0.518 | 0.580 | 0.694 |
| 0.5 | 0.488 | 0.494 | 0.534 | 0.622 |
| 0.75 | 0.500 | 0.489 | 0.515 | 0.578 |
| 1.0 | 0.524 | 0.500 | 0.505 | 0.553 |

