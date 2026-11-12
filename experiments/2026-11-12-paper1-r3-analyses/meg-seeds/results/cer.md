# MEG decoder seeds: test CER (637 instances, mean over sentences)

Seeds: [0, 1].

| condition / decoder | seed 0 | seed 1 | mean ± SD |
|---|---|---|---|
| real/greedy | 0.506 | 0.502 | 0.504 ± 0.003 |
| real/beam_nolm | 0.500 | 0.494 | 0.497 ± 0.004 |
| real/beam_lm_retuned | 0.493 | 0.490 | 0.491 ± 0.002 |
| real/beam_lm_valtuned | 0.475 | 0.467 | 0.471 ± 0.006 |
| shuffled/greedy | 0.760 | 0.745 | 0.752 ± 0.011 |
| shuffled/beam_nolm | 0.745 | 0.730 | 0.738 ± 0.010 |
| shuffled/beam_lm_retuned | 0.759 | 0.743 | 0.751 ± 0.011 |
| shuffled/beam_lm_valtuned | 0.732 | 0.725 | 0.728 ± 0.005 |
| zeros/greedy | 0.925 | 0.948 | 0.936 ± 0.017 |
| zeros/beam_nolm | 0.845 | 0.799 | 0.822 ± 0.033 |
| zeros/beam_lm_retuned | 0.853 | 0.831 | 0.842 ± 0.016 |
| zeros/beam_lm_valtuned | 0.771 | 0.776 | 0.774 ± 0.003 |