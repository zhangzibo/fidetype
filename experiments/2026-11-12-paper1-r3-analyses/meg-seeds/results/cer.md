# MEG decoder seeds: test CER (637 instances, mean over sentences)

Seeds: [0, 1, 2].

| condition / decoder | seed 0 | seed 1 | seed 2 | mean ± SD |
|---|---|---|---|---|
| real/greedy | 0.506 | 0.502 | 0.592 | 0.533 ± 0.051 |
| real/beam_nolm | 0.500 | 0.494 | 0.587 | 0.527 ± 0.052 |
| real/beam_lm_retuned | 0.493 | 0.490 | 0.573 | 0.518 ± 0.047 |
| real/beam_lm_valtuned | 0.475 | 0.467 | 0.567 | 0.503 ± 0.056 |
| shuffled/greedy | 0.760 | 0.745 | 0.732 | 0.746 ± 0.014 |
| shuffled/beam_nolm | 0.745 | 0.730 | 0.723 | 0.733 ± 0.011 |
| shuffled/beam_lm_retuned | 0.759 | 0.743 | 0.728 | 0.743 ± 0.015 |
| shuffled/beam_lm_valtuned | 0.732 | 0.725 | 0.721 | 0.726 ± 0.006 |
| zeros/greedy | 0.925 | 0.948 | 0.819 | 0.897 ± 0.069 |
| zeros/beam_nolm | 0.845 | 0.799 | 0.773 | 0.806 ± 0.037 |
| zeros/beam_lm_retuned | 0.853 | 0.831 | 0.809 | 0.831 ± 0.022 |
| zeros/beam_lm_valtuned | 0.771 | 0.776 | 0.782 | 0.776 ± 0.005 |