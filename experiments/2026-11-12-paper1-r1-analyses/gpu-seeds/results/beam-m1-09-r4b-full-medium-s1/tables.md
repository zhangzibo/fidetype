### val (n = 437 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.508 [0.494, 0.521] | 0.742 | 0.943 | +0.234 [+0.220, +0.249] | 0.834 | 0.510 | 0.510 | 0.496 | - |
| beam, no LM | 0.499 [0.485, 0.512] | 0.723 | 0.793 | +0.224 [+0.210, +0.238] | 0.836 | 0.501 | 0.502 | 0.488 | 0.000 |
| beam + LM, RETUNED as is | 0.502 [0.487, 0.515] | 0.739 | 0.827 | +0.237 [+0.222, +0.253] | 0.775 | 0.504 | 0.503 | 0.490 | 0.002 |
| beam + LM, val-tuned | 0.478 [0.463, 0.494] | 0.715 | 0.758 | +0.237 [+0.221, +0.253] | 0.847 | 0.481 | 0.481 | 0.466 | 0.011 |

Beam minus greedy (real MEG, paired): beam, no LM -0.008 [-0.011, -0.006]; beam + LM, RETUNED as is -0.006 [-0.012, -0.000]; beam + LM, val-tuned -0.029 [-0.036, -0.022]
CPU fp32 re-run of real MEG, greedy: 0.507 [0.493, 0.520]

### test (n = 637 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.502 [0.490, 0.513] | 0.745 | 0.948 | +0.243 [+0.231, +0.255] | 0.828 | 0.505 | 0.501 | 0.492 | - |
| beam, no LM | 0.494 [0.483, 0.506] | 0.730 | 0.799 | +0.236 [+0.224, +0.248] | 0.835 | 0.497 | 0.493 | 0.484 | 0.003 |
| beam + LM, RETUNED as is | 0.490 [0.477, 0.502] | 0.743 | 0.831 | +0.253 [+0.240, +0.267] | 0.753 | 0.493 | 0.489 | 0.480 | 0.019 |
| beam + LM, val-tuned | 0.467 [0.453, 0.480] | 0.725 | 0.776 | +0.258 [+0.244, +0.272] | 0.799 | 0.470 | 0.466 | 0.455 | 0.019 |

Beam minus greedy (real MEG, paired): beam, no LM -0.008 [-0.010, -0.006]; beam + LM, RETUNED as is -0.012 [-0.017, -0.007]; beam + LM, val-tuned -0.035 [-0.040, -0.030]
CPU fp32 re-run of real MEG, greedy: 0.501 [0.490, 0.513]

### Val grid (real MEG, CER vs target, mean over sentences)

Frame temperature fitted on real val: 3.217.

raw streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.499 | 0.506 | 0.522 | 0.548 |
| 0.05 | 0.496 | 0.500 | 0.510 | 0.532 |
| 0.1 | 0.496 | 0.495 | 0.501 | 0.519 |
| 0.15 | 0.495 | 0.493 | 0.496 | 0.510 |
| 0.25 | 0.496 | 0.489 | 0.491 | 0.496 |
| 0.5 | 0.501 | 0.491 | 0.487 | 0.487 |
| 0.75 | 0.506 | 0.497 | 0.489 | 0.484 |
| 1.0 | 0.516 | 0.504 | 0.496 | 0.489 |

calibrated streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.543 | 0.637 | 0.818 | 1.102 |
| 0.05 | 0.512 | 0.586 | 0.719 | 0.946 |
| 0.1 | 0.495 | 0.552 | 0.653 | 0.838 |
| 0.15 | 0.489 | 0.533 | 0.616 | 0.764 |
| 0.25 | 0.478 | 0.512 | 0.577 | 0.689 |
| 0.5 | 0.482 | 0.486 | 0.531 | 0.618 |
| 0.75 | 0.497 | 0.491 | 0.515 | 0.574 |
| 1.0 | 0.523 | 0.496 | 0.504 | 0.546 |

