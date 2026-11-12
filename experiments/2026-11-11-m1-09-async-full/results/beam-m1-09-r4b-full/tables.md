### val (n = 437 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.550 [0.539, 0.561] | 0.768 | 0.923 | +0.218 [+0.205, +0.231] | 0.860 | 0.552 | 0.551 | 0.551 | - |
| beam, no LM | 0.541 [0.530, 0.553] | 0.746 | 0.835 | +0.205 [+0.192, +0.217] | 0.867 | 0.543 | 0.542 | 0.542 | 0.000 |
| beam + LM, RETUNED as is | 0.548 [0.536, 0.560] | 0.778 | 0.831 | +0.229 [+0.215, +0.243] | 0.803 | 0.551 | 0.551 | 0.551 | 0.000 |
| beam + LM, val-tuned | 0.517 [0.505, 0.530] | 0.714 | 0.716 | +0.197 [+0.184, +0.210] | 0.882 | 0.519 | 0.519 | 0.519 | 0.000 |

Beam minus greedy (real MEG, paired): beam, no LM -0.009 [-0.011, -0.006]; beam + LM, RETUNED as is -0.002 [-0.008, +0.005]; beam + LM, val-tuned -0.033 [-0.039, -0.026]
CPU fp32 re-run of real MEG, greedy: 0.549 [0.538, 0.560]

### test (n = 637 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.553 [0.544, 0.562] | 0.761 | 0.922 | +0.208 [+0.197, +0.218] | 0.858 | 0.554 | 0.553 | 0.553 | - |
| beam, no LM | 0.546 [0.537, 0.555] | 0.742 | 0.835 | +0.196 [+0.186, +0.206] | 0.864 | 0.547 | 0.547 | 0.547 | 0.000 |
| beam + LM, RETUNED as is | 0.554 [0.544, 0.565] | 0.774 | 0.834 | +0.219 [+0.208, +0.231] | 0.816 | 0.556 | 0.554 | 0.554 | 0.002 |
| beam + LM, val-tuned | 0.524 [0.513, 0.535] | 0.716 | 0.731 | +0.192 [+0.180, +0.203] | 0.868 | 0.524 | 0.524 | 0.524 | 0.000 |

Beam minus greedy (real MEG, paired): beam, no LM -0.007 [-0.009, -0.004]; beam + LM, RETUNED as is +0.001 [-0.004, +0.007]; beam + LM, val-tuned -0.029 [-0.035, -0.023]
CPU fp32 re-run of real MEG, greedy: 0.553 [0.544, 0.562]

### Val grid (real MEG, CER vs target, mean over sentences)

Frame temperature fitted on real val: 2.781.

raw streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.541 | 0.550 | 0.570 | 0.611 |
| 0.05 | 0.538 | 0.542 | 0.558 | 0.590 |
| 0.1 | 0.538 | 0.536 | 0.547 | 0.572 |
| 0.15 | 0.535 | 0.533 | 0.538 | 0.559 |
| 0.25 | 0.535 | 0.530 | 0.532 | 0.543 |
| 0.5 | 0.543 | 0.529 | 0.524 | 0.525 |
| 0.75 | 0.556 | 0.539 | 0.526 | 0.520 |
| 1.0 | 0.577 | 0.555 | 0.537 | 0.526 |

calibrated streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.582 | 0.695 | 0.895 | 1.191 |
| 0.05 | 0.550 | 0.641 | 0.796 | 1.048 |
| 0.1 | 0.535 | 0.604 | 0.726 | 0.935 |
| 0.15 | 0.526 | 0.582 | 0.687 | 0.859 |
| 0.25 | 0.517 | 0.555 | 0.643 | 0.784 |
| 0.5 | 0.526 | 0.530 | 0.593 | 0.698 |
| 0.75 | 0.550 | 0.529 | 0.559 | 0.643 |
| 1.0 | 0.580 | 0.544 | 0.543 | 0.609 |

