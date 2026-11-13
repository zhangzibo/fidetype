# Tables: confirmatory T12 test (M3-27)

Pre-registration: commit `a7cf624`. Frozen trust config id `tcfg-fe35888dac333cff`. Outcome: **uninformative**.

## Data and splits

| part | sessions | trials |
|---|---|---|
| decoder train | 24 | 7900 |
| decoder validation | 24 | 880 |
| fit-A (trust pool) | 8 | 240 |
| calibration (trust pool) | 6 | 240 |
| test (trust pool) | 10 | 400 |

Speech rate (decoder-train trials): 304.0 characters/min.

## Decoder

| set | n | greedy PER | CER | WER | sentence exact | truth in n-best |
|---|---|---|---|---|---|---|
| decoder validation | 880 | 0.471 | 0.491 | 0.673 | 0.015 | 0.031 |
| test sessions | 400 | 0.542 | 0.551 | 0.751 | 0.007 | — |

## Primary and secondary rules (test sessions)

CP95: exact Clopper-Pearson; {..}: session-cluster bootstrap 95 % (B 2000, seed 20261112).

| rule | λ | wrong-commit [CP95] {boot} | commit rate {boot} | EAC (wrong/commits) | silent | eWPM {boot} |
|---|---|---|---|---|---|---|
| LTT max (primary) | 0.30 | 0.0000 [0.000, 0.009] {0.000, 0.000} | 0.000 {0.000, 0.000} | nan (0/0) | 0.0000 | 4.58 {4.27, 4.99} |
| plug-in | 0.30 | 0.0000 [0.000, 0.009] {0.000, 0.000} | 0.000 {0.000, 0.000} | nan (0/0) | 0.0000 | 4.58 {4.27, 4.99} |
| no commits | inf | 0.0000 [0.000, 0.009] {0.000, 0.000} | 0.000 {0.000, 0.000} | nan (0/0) | 0.0000 | 4.58 {4.27, 4.99} |
| always commit top-1 | — | 0.9925 [0.978, 0.998] {0.983, 1.000} | 1.000 {1.000, 1.000} | 0.993 (397/400) | 0.1700 | 3.92 {3.55, 4.36} |
| joint LTT b0.10 | inf | 0.0000 [0.000, 0.009] {0.000, 0.000} | 0.000 {0.000, 0.000} | nan (0/0) | 0.0000 | 4.58 {4.27, 4.99} |
| joint LTT b0.20 | inf | 0.0000 [0.000, 0.009] {0.000, 0.000} | 0.000 {0.000, 0.000} | nan (0/0) | 0.0000 | 4.58 {4.27, 4.99} |

Gaze typing alone: 4.11 eWPM. Gain of LTT max over the same policy without commits: +0.000 [0.000, 0.000] eWPM (sign test over sessions: 0+ / 0-, p = 1.000). Gain over gaze: +0.47 [0.13, 0.87].

## Per test session (P2, LTT max)

| session | n | wrong commits | wrong-commit [CP95] | commit rate | > α |
|---|---|---|---|---|---|
| t12.2022.07.14 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.07.21 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.07.27 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.07.29 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.08.02 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.08.11 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.08.13 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.08.18 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.08.23 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |
| t12.2022.08.25 | 40 | 0 | 0.000 [0.000, 0.088] | 0.000 | no |

Sessions above α: 0 of 10; with CP lower bound above α: 0.

## Controls (P3)

| control | rule | commits / n | one-sided CP95 upper | wrong commits |
|---|---|---|---|---|
| frame_shuffled | LTT max (primary) | 0/400 | 0.0075 | 0 |
| frame_shuffled | plug-in | 0/400 | 0.0075 | 0 |
| uniform | LTT max (primary) | 0/400 | 0.0075 | 0 |
| uniform | plug-in | 0/400 | 0.0075 | 0 |
| intent_mismatch | LTT max (primary) | 0/400 | 0.0075 | 0 |
| intent_mismatch | plug-in | 0/400 | 0.0075 | 0 |

## Criteria

| criterion | pass |
|---|---|
| C1_pooled_wrong_commit_le_alpha | True |
| C2_no_session_cp_lower_above_alpha | True |
| C3_controls_commit_le_0.01 | True |
| commits_any | False |

## Fit

LTT: λ̂ = 0.0, feasible True, n 240; final commit_p = 0.3.
Fit report: frame T 2.089, sentence T 20.000, conformal q inf, policy fit feasible True.
Trust core identical to tag `paper1-v4-frozen-config`: True.
