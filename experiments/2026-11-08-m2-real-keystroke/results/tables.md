# M2-10 real keystroke decoder: generated tables (run.py)

Chosen model: **lr**. Model selection (val): `{"lr": {"val_acc": 0.4191555097837281, "val_nll": 1.8960170804397798}, "mlp": {"val_acc": 0.33553038105046346, "val_nll": 2.1103896613937025}}`

## Decoder (pooled over subjects)

| input | split | trials | keys | key acc | greedy CER vs typed | greedy CER vs target | greedy WER vs target |
|---|---|---|---|---|---|---|---|
| real | val | 114 | 4855 | 0.419 | 0.563 | 0.580 | 1.063 |
| real | test | 209 | 8423 | 0.390 | 0.590 | 0.597 | 1.072 |
| shuffled_meg | val | 114 | 4855 | 0.139 | 0.747 | 0.750 | 1.142 |
| shuffled_meg | test | 209 | 8423 | 0.111 | 0.774 | 0.774 | 1.140 |
| perm_label | val | 114 | 4855 | 0.101 | 0.767 | 0.763 | 1.305 |
| perm_label | test | 209 | 8423 | 0.099 | 0.767 | 0.768 | 1.281 |
| lr | val | 114 | 4855 | 0.419 | 0.563 | 0.580 | 1.063 |
| lr | test | 209 | 8423 | 0.390 | 0.590 | 0.597 | 1.072 |
| mlp | val | 114 | 4855 | 0.336 | 0.631 | 0.641 | 1.185 |
| mlp | test | 209 | 8423 | 0.308 | 0.648 | 0.653 | 1.225 |
| lr_perm | val | 114 | 4855 | 0.101 | 0.767 | 0.763 | 1.305 |
| lr_perm | test | 209 | 8423 | 0.099 | 0.767 | 0.768 | 1.281 |
| mlp_perm | val | 114 | 4855 | 0.126 | 0.815 | 0.820 | 1.020 |
| mlp_perm | test | 209 | 8423 | 0.124 | 0.819 | 0.820 | 1.020 |

Majority-class chance: val 0.129, test 0.132.

## Decoder per subject (real input; val+test shown separately)

| subject | train keys | lam | test trials | test key acc | test greedy CER typed | val key acc | shuffled-MEG test acc | perm-label test acc |
|---|---|---|---|---|---|---|---|---|
| S1 | 5701 | 0.1 | 30 | 0.424 | 0.568 | 0.468 | 0.118 | 0.099 |
| S3 | 3660 | 0.3 | 15 | 0.359 | 0.621 | 0.352 | 0.090 | 0.104 |
| S5 | 1816 | 1.0 | 3 | 0.409 | 0.581 | 0.323 | 0.204 | 0.097 |
| S9 | 1998 | 0.3 | 13 | 0.337 | 0.637 | 0.366 | 0.089 | 0.102 |
| S11 | 3818 | 0.3 | 26 | 0.304 | 0.658 | 0.381 | 0.122 | 0.101 |
| S12 | 1839 | 1.0 | 13 | 0.281 | 0.676 | 0.263 | 0.153 | 0.110 |
| S15 | 3977 | 0.1 | 26 | 0.476 | 0.517 | 0.471 | 0.111 | 0.082 |
| S16 | 1912 | 0.3 | 13 | 0.483 | 0.511 | 0.526 | 0.090 | 0.112 |
| S18 | 1945 | 0.3 | 13 | 0.304 | 0.666 | 0.360 | 0.097 | 0.095 |
| S19 | 3889 | 0.3 | 25 | 0.367 | 0.608 | 0.369 | 0.099 | 0.108 |
| S25 | 7649 | 0.1 | 32 | 0.452 | 0.536 | 0.480 | 0.116 | 0.094 |

## Beam + Spanish 6-gram LM (CER/WER vs target)

Frame T fitted on val (for the _calT rows): 1.010.

| setting | val CER | val WER | test CER | test WER | test sentence acc | test target in n-best |
|---|---|---|---|---|---|---|
| default/w=0.5 | 0.533 | 1.054 | 0.552 | 1.096 | 0.000 | 0.000 |
| default/w=1.0 | 0.562 | 1.090 | 0.557 | 1.081 | 0.000 | 0.000 |
| default/w=1.25 | 0.562 | 1.084 | 0.572 | 1.093 | 0.000 | 0.000 |
| default/w=2.0 | 0.590 | 1.103 | 0.598 | 1.105 | 0.000 | 0.000 |
| default/w=3.0 | 0.626 | 1.082 | 0.635 | 1.120 | 0.000 | 0.000 |
| retuned/w=0.5 | 0.496 | 0.960 | 0.531 | 1.023 | 0.000 | 0.000 |
| retuned/w=1.0 | 0.501 | 0.937 | 0.535 | 0.958 | 0.000 | 0.000 |
| retuned/w=1.25 | 0.514 | 0.922 | 0.544 | 0.957 | 0.000 | 0.000 |
| retuned/w=2.0 | 0.568 | 0.920 | 0.575 | 0.947 | 0.000 | 0.000 |
| retuned/w=3.0 | 0.600 | 0.902 | 0.620 | 0.926 | 0.000 | 0.000 |
| retuned_calT/w=0.5 (best on val) | 0.496 | 0.960 | 0.531 | 1.023 | 0.000 | 0.000 |
| retuned_calT/w=1.0 | 0.501 | 0.924 | 0.536 | 0.958 | 0.000 | 0.000 |
| retuned_calT/w=1.25 | 0.516 | 0.922 | 0.542 | 0.956 | 0.000 | 0.000 |
| retuned_calT/w=2.0 | 0.568 | 0.921 | 0.575 | 0.944 | 0.000 | 0.000 |
| retuned_calT/w=3.0 | 0.602 | 0.905 | 0.622 | 0.925 | 0.000 | 0.000 |

## Trust pipeline on test (209 trials, 17 sentences; fit on val: 114 trials, 11 sentences)

Values: point [trial-bootstrap 95% CI] {sentence-cluster bootstrap 95% CI}.

| policy | eWPM | wrong-commit | silent error | top-1 CER | committed CER |
|---|---|---|---|---|---|
| a_greedy_commit | 9.21 [8.97, 9.42] {8.84, 9.57} | 1.000 [1.000, 1.000] {1.000, 1.000} | 0.081 [0.048, 0.120] {0.051, 0.117} | 0.597 [0.585, 0.611] | 0.597 [0.585, 0.611] {0.580, 0.614} |
| b_top1_commit | 9.61 [9.34, 9.86] {9.27, 9.97} | 1.000 [1.000, 1.000] {1.000, 1.000} | 0.081 [0.048, 0.120] {0.051, 0.117} | 0.530 [0.511, 0.547] | 0.530 [0.511, 0.547] {0.511, 0.548} |
| b0_top1_commit_uncal | 9.59 [9.33, 9.85] {9.25, 9.96} | 1.000 [1.000, 1.000] {1.000, 1.000} | 0.081 [0.048, 0.120] {0.051, 0.117} | 0.531 [0.513, 0.548] | 0.531 [0.513, 0.548] {0.511, 0.550} |
| c_trust | 9.70 [9.52, 9.89] {9.29, 10.15} | 0.000 [0.000, 0.000] {0.000, 0.000} | 0.000 [0.000, 0.000] {0.000, 0.000} | 0.530 [0.511, 0.547] | - |
| d_trust_no_calib | 9.69 [9.52, 9.88] {9.30, 10.14} | 0.010 [0.000, 0.024] {0.000, 0.026} | 0.000 [0.000, 0.000] {0.000, 0.000} | 0.531 [0.513, 0.548] | 0.406 [0.154, 0.579] {0.154, 0.579} |
| e_trust_no_guard | 9.70 [9.52, 9.89] {9.29, 10.15} | 0.000 [0.000, 0.000] {0.000, 0.000} | 0.000 [0.000, 0.000] {0.000, 0.000} | 0.530 [0.511, 0.547] | - |
| f_trust_consistency_ptop1 | 9.70 [9.52, 9.89] {9.29, 10.15} | 0.000 [0.000, 0.000] {0.000, 0.000} | 0.000 [0.000, 0.000] {0.000, 0.000} | 0.530 [0.511, 0.547] | - |

| policy | COMMIT | OFFER | ASK | ABSTAIN | communicated | committed WER | WER top-1 |
|---|---|---|---|---|---|---|---|
| a_greedy_commit | 1.00 | 0.00 | 0.00 | 0.00 | 0.919 | 1.072 | 1.072 |
| b_top1_commit | 1.00 | 0.00 | 0.00 | 0.00 | 0.919 | 1.018 | 1.018 |
| b0_top1_commit_uncal | 1.00 | 0.00 | 0.00 | 0.00 | 0.919 | 1.023 | 1.023 |
| c_trust | 0.00 | 1.00 | 0.00 | 0.00 | 1.000 | - | 1.018 |
| d_trust_no_calib | 0.01 | 0.99 | 0.00 | 0.00 | 1.000 | 0.636 | 1.023 |
| e_trust_no_guard | 0.00 | 1.00 | 0.00 | 0.00 | 1.000 | - | 1.018 |
| f_trust_consistency_ptop1 | 0.00 | 1.00 | 0.00 | 0.00 | 1.000 | - | 1.018 |
| pareto_trust_0.02 | 0.00 | 1.00 | 0.00 | 0.00 | 1.000 | - | 1.018 |
| pareto_trust_0.1 | 0.00 | 1.00 | 0.00 | 0.00 | 1.000 | - | 1.018 |
| pareto_trust_0.2 | 0.00 | 1.00 | 0.00 | 0.00 | 1.000 | - | 1.018 |

## Calibration, conformal and guard (test)

| policy | T frame | T sentence | ECE char before | after | ECE sentence before | after | coverage | coverage in n-best | mean set size | n-best miss | guard AUROC | inconsistency AUROC | p_top1 AUROC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| c_trust | 1.018 | 20.000 | 0.037 | 0.042 | 0.182 | 0.103 | 0.000 | - | 10.000 | 1.000 | - | - | - |
| d_trust_no_calib | 1.000 | 1.000 | 0.037 | 0.037 | 0.180 | 0.180 | 0.000 | - | 10.000 | 1.000 | - | - | - |
| e_trust_no_guard | 1.018 | 20.000 | 0.037 | 0.042 | 0.182 | 0.103 | 0.000 | - | 10.000 | 1.000 | - | - | - |
| f_trust_consistency_ptop1 | 1.018 | 20.000 | 0.037 | 0.042 | 0.182 | 0.103 | 0.000 | - | 10.000 | 1.000 | - | - | - |

## Paired bootstrap differences (test)

| difference | trial CI | P(diff <= 0) | sentence CI |
|---|---|---|---|
| c_trust-b_top1_commit:ewpm | [-0.110, 0.349] | 0.204 | [-0.073, 0.280] |
| c_trust-b_top1_commit:wrong_commit_rate | [-1.000, -1.000] | 1.000 | [-1.000, -1.000] |
| c_trust-b_top1_commit:silent_error_rate | [-0.120, -0.048] | 1.000 | [-0.117, -0.051] |
| c_trust-a_greedy_commit:ewpm | [0.285, 0.747] | 0.000 | [0.274, 0.715] |
| c_trust-a_greedy_commit:wrong_commit_rate | [-1.000, -1.000] | 1.000 | [-1.000, -1.000] |
| c_trust-a_greedy_commit:silent_error_rate | [-0.120, -0.048] | 1.000 | [-0.117, -0.051] |
| b_top1_commit-a_greedy_commit:ewpm | [0.296, 0.499] | 0.000 | [0.288, 0.500] |
| b_top1_commit-a_greedy_commit:wrong_commit_rate | [0.000, 0.000] | 1.000 | [0.000, 0.000] |
| b_top1_commit-a_greedy_commit:silent_error_rate | [0.000, 0.000] | 1.000 | [0.000, 0.000] |

## Null-input audit (test streams)

| policy | input | fluent top-1 | COMMIT rate | fluent and committed | mean chars |
|---|---|---|---|---|---|
| a_greedy_commit | real | 0.005 | 1.000 | 0.005 | 38.5 |
| a_greedy_commit | shuffled_meg | 0.000 | 1.000 | 0.000 | 38.4 |
| a_greedy_commit | frame_shuffled | 0.010 | 1.000 | 0.010 | 37.2 |
| a_greedy_commit | uniform | 0.000 | 1.000 | 0.000 | 74.0 |
| b_top1_commit | real | 0.828 | 1.000 | 0.828 | 40.1 |
| b_top1_commit | shuffled_meg | 0.837 | 1.000 | 0.837 | 40.1 |
| b_top1_commit | frame_shuffled | 0.856 | 1.000 | 0.856 | 36.0 |
| b_top1_commit | uniform | 1.000 | 1.000 | 1.000 | 45.2 |
| b0_top1_commit_uncal | real | 0.823 | 1.000 | 0.823 | 40.1 |
| b0_top1_commit_uncal | shuffled_meg | 0.828 | 1.000 | 0.828 | 40.1 |
| b0_top1_commit_uncal | frame_shuffled | 0.847 | 1.000 | 0.847 | 36.0 |
| b0_top1_commit_uncal | uniform | 1.000 | 1.000 | 1.000 | 45.2 |
| c_trust | real | 0.828 | 0.000 | 0.000 | 40.1 |
| c_trust | shuffled_meg | 0.837 | 0.000 | 0.000 | 40.1 |
| c_trust | frame_shuffled | 0.856 | 0.000 | 0.000 | 36.0 |
| c_trust | uniform | 1.000 | 0.000 | 0.000 | 45.2 |
| d_trust_no_calib | real | 0.823 | 0.010 | 0.010 | 40.1 |
| d_trust_no_calib | shuffled_meg | 0.828 | 0.014 | 0.014 | 40.1 |
| d_trust_no_calib | frame_shuffled | 0.847 | 0.010 | 0.010 | 36.0 |
| d_trust_no_calib | uniform | 1.000 | 0.019 | 0.019 | 45.2 |
| e_trust_no_guard | real | 0.828 | 0.000 | 0.000 | 40.1 |
| e_trust_no_guard | shuffled_meg | 0.837 | 0.000 | 0.000 | 40.1 |
| e_trust_no_guard | frame_shuffled | 0.856 | 0.000 | 0.000 | 36.0 |
| e_trust_no_guard | uniform | 1.000 | 0.000 | 0.000 | 45.2 |
| f_trust_consistency_ptop1 | real | 0.828 | 0.000 | 0.000 | 40.1 |
| f_trust_consistency_ptop1 | shuffled_meg | 0.837 | 0.000 | 0.000 | 40.1 |
| f_trust_consistency_ptop1 | frame_shuffled | 0.856 | 0.000 | 0.000 | 36.0 |
| f_trust_consistency_ptop1 | uniform | 1.000 | 0.000 | 0.000 | 45.2 |

## Guard signals (test): AUROC for top-1 CER above the median, Spearman with top-1 CER

| policy | risk | inconsistency | -p_top1 | low evidence | rho risk | rho inconsistency | rho -p_top1 |
|---|---|---|---|---|---|---|---|
| b_top1_commit | 0.848 | 0.516 | 0.552 | 0.848 | 0.658 | 0.074 | 0.103 |
| b0_top1_commit_uncal | 0.860 | 0.541 | 0.559 | 0.860 | 0.660 | 0.124 | 0.110 |
| c_trust | 0.848 | 0.516 | 0.552 | 0.848 | 0.658 | 0.074 | 0.103 |
| d_trust_no_calib | 0.860 | 0.541 | 0.559 | 0.860 | 0.660 | 0.124 | 0.110 |
| e_trust_no_guard | 0.848 | 0.516 | 0.552 | 0.848 | 0.658 | 0.074 | 0.103 |
| f_trust_consistency_ptop1 | 0.516 | 0.516 | 0.552 | 0.848 | 0.074 | 0.074 | 0.103 |

## Guard signals: AUROC null input vs real input (test streams)

| policy | null input | risk | inconsistency | -p_top1 | low evidence |
|---|---|---|---|---|---|
| b_top1_commit | shuffled_meg | 0.488 | 0.510 | 0.517 | 0.488 |
| b_top1_commit | frame_shuffled | 0.491 | 0.595 | 0.516 | 0.491 |
| b_top1_commit | uniform | 0.978 | 0.635 | 0.263 | 0.978 |
| b0_top1_commit_uncal | shuffled_meg | 0.486 | 0.501 | 0.518 | 0.486 |
| b0_top1_commit_uncal | frame_shuffled | 0.491 | 0.591 | 0.517 | 0.491 |
| b0_top1_commit_uncal | uniform | 0.981 | 0.595 | 0.268 | 0.981 |
| c_trust | shuffled_meg | 0.488 | 0.510 | 0.517 | 0.488 |
| c_trust | frame_shuffled | 0.491 | 0.595 | 0.516 | 0.491 |
| c_trust | uniform | 0.978 | 0.635 | 0.263 | 0.978 |
| d_trust_no_calib | shuffled_meg | 0.486 | 0.501 | 0.518 | 0.486 |
| d_trust_no_calib | frame_shuffled | 0.491 | 0.591 | 0.517 | 0.491 |
| d_trust_no_calib | uniform | 0.981 | 0.595 | 0.268 | 0.981 |
| e_trust_no_guard | shuffled_meg | 0.488 | 0.510 | 0.517 | 0.488 |
| e_trust_no_guard | frame_shuffled | 0.491 | 0.595 | 0.516 | 0.491 |
| e_trust_no_guard | uniform | 0.978 | 0.635 | 0.263 | 0.978 |
| f_trust_consistency_ptop1 | shuffled_meg | 0.510 | 0.510 | 0.517 | 0.488 |
| f_trust_consistency_ptop1 | frame_shuffled | 0.595 | 0.595 | 0.516 | 0.491 |
| f_trust_consistency_ptop1 | uniform | 0.635 | 0.635 | 0.263 | 0.978 |

## Word-level alternatives (test): share of true words found

| policy | top-1 sentence word | top-3 per-word slot | best of top-3 sentences |
|---|---|---|---|
| b_top1_commit | 0.264 | 0.291 | 0.289 |
| c_trust | 0.264 | 0.291 | 0.289 |

## Per subject (test)

| subject | n | eWPM b | wrong-commit b | eWPM c | wrong-commit c | COMMIT c |
|---|---|---|---|---|---|---|
| S1 | 30 | 9.86 | 1.000 | 10.13 | 0.000 | 0.00 |
| S3 | 15 | 9.44 | 1.000 | 9.47 | 0.000 | 0.00 |
| S5 | 3 | 8.46 | 1.000 | 9.91 | 0.000 | 0.00 |
| S9 | 13 | 8.71 | 1.000 | 9.15 | 0.000 | 0.00 |
| S11 | 26 | 8.88 | 1.000 | 8.90 | 0.000 | 0.00 |
| S12 | 13 | 8.15 | 1.000 | 8.64 | 0.000 | 0.00 |
| S15 | 26 | 10.83 | 1.000 | 11.06 | 0.000 | 0.00 |
| S16 | 13 | 10.43 | 1.000 | 10.42 | 0.000 | 0.00 |
| S18 | 13 | 9.36 | 1.000 | 9.04 | 0.000 | 0.00 |
| S19 | 25 | 9.44 | 1.000 | 9.27 | 0.000 | 0.00 |
| S25 | 32 | 10.32 | 1.000 | 10.31 | 0.000 | 0.00 |

Fitted policy (c): `{"commit_p": 0.3, "commit_max_risk": 0.1, "commit_max_set": null, "offer_max_k": 1, "abstain_risk": 1.01, "final_fallback": "offer"}` feasible on val: True
