### val (n = 437 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.579 [0.569, 0.588] | 0.727 | 0.810 | +0.148 [+0.137, +0.159] | 0.909 | 0.579 | 0.579 | 0.573 | - |
| beam, no LM | 0.575 [0.566, 0.585] | 0.717 | 0.759 | +0.142 [+0.132, +0.152] | 0.917 | 0.576 | 0.575 | 0.570 | 0.000 |
| beam + LM, RETUNED as is | 0.565 [0.555, 0.576] | 0.726 | 0.801 | +0.161 [+0.149, +0.172] | 0.857 | 0.568 | 0.567 | 0.561 | 0.000 |
| beam + LM, val-tuned | 0.561 [0.551, 0.572] | 0.717 | 0.770 | +0.156 [+0.144, +0.167] | 0.868 | 0.563 | 0.562 | 0.556 | 0.000 |

Beam minus greedy (real MEG, paired): beam, no LM -0.003 [-0.006, -0.001]; beam + LM, RETUNED as is -0.013 [-0.019, -0.007]; beam + LM, val-tuned -0.017 [-0.022, -0.013]
CPU fp32 re-run of real MEG, greedy: 0.579 [0.569, 0.588]

### test (n = 637 sentences)

| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |
|---|---|---|---|---|---|---|---|---|---|
| greedy | 0.592 [0.583, 0.601] | 0.732 | 0.819 | +0.140 [+0.131, +0.150] | 0.899 | 0.594 | 0.591 | 0.587 | - |
| beam, no LM | 0.587 [0.578, 0.596] | 0.723 | 0.773 | +0.137 [+0.127, +0.147] | 0.904 | 0.588 | 0.586 | 0.581 | 0.000 |
| beam + LM, RETUNED as is | 0.573 [0.563, 0.583] | 0.728 | 0.809 | +0.155 [+0.144, +0.166] | 0.826 | 0.575 | 0.573 | 0.569 | 0.002 |
| beam + LM, val-tuned | 0.567 [0.557, 0.577] | 0.721 | 0.782 | +0.154 [+0.144, +0.165] | 0.835 | 0.570 | 0.565 | 0.562 | 0.000 |

Beam minus greedy (real MEG, paired): beam, no LM -0.005 [-0.008, -0.003]; beam + LM, RETUNED as is -0.019 [-0.024, -0.014]; beam + LM, val-tuned -0.025 [-0.029, -0.020]
CPU fp32 re-run of real MEG, greedy: 0.591 [0.583, 0.600]

### Val grid (real MEG, CER vs target, mean over sentences)

Frame temperature fitted on real val: 2.663.

raw streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.575 | 0.591 | 0.619 | 0.660 |
| 0.05 | 0.571 | 0.582 | 0.603 | 0.636 |
| 0.1 | 0.566 | 0.573 | 0.590 | 0.621 |
| 0.15 | 0.566 | 0.570 | 0.583 | 0.606 |
| 0.25 | 0.563 | 0.563 | 0.571 | 0.590 |
| 0.5 | 0.566 | 0.561 | 0.563 | 0.571 |
| 0.75 | 0.571 | 0.563 | 0.562 | 0.567 |
| 1.0 | 0.575 | 0.568 | 0.562 | 0.563 |

calibrated streams

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| 0.0 | 0.585 | 0.654 | 0.846 | 1.273 |
| 0.05 | 0.574 | 0.618 | 0.764 | 1.128 |
| 0.1 | 0.567 | 0.602 | 0.721 | 1.023 |
| 0.15 | 0.565 | 0.591 | 0.692 | 0.953 |
| 0.25 | 0.564 | 0.581 | 0.654 | 0.853 |
| 0.5 | 0.570 | 0.571 | 0.607 | 0.711 |
| 0.75 | 0.583 | 0.571 | 0.582 | 0.642 |
| 1.0 | 0.601 | 0.580 | 0.584 | 0.614 |

