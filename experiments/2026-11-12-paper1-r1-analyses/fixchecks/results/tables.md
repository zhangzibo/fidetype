# Fix checks: generated tables

## B2T '25 counts

The file has 1,718 copy-task trials from 15 post-implant days. 90 trials use the 50-word vocabulary (all 50 trials of day 25 and 40 of day 27). The analysis uses the other 1,628 trials (125,000-word vocabulary), which come from 14 days (27 to 244). Each day's 125k trials are split in file order: first half -> fit (812), second half -> test (816).

| day | 50-word trials | 125k trials | fit | test |
|---|---|---|---|---|
| 25 | 50 | 0 | 0 | 0 |
| 27 | 40 | 30 | 15 | 15 |
| 34 | 0 | 100 | 50 | 50 |
| 46 | 0 | 99 | 49 | 50 |
| 48 | 0 | 115 | 57 | 58 |
| 69 | 0 | 115 | 57 | 58 |
| 74 | 0 | 74 | 37 | 37 |
| 76 | 0 | 208 | 104 | 104 |
| 81 | 0 | 138 | 69 | 69 |
| 83 | 0 | 169 | 84 | 85 |
| 88 | 0 | 90 | 45 | 45 |
| 90 | 0 | 148 | 74 | 74 |
| 95 | 0 | 50 | 25 | 25 |
| 223 | 0 | 146 | 73 | 73 |
| 244 | 0 | 146 | 73 | 73 |

## MEG: harness top-1 CER vs the M1-09 beam

Harness frame T 3.296 (fit on the first half of val); M1-09 frame T 3.285 (all val).

| setting | frame T | LM weight | insertion bonus | CER pooled | CER mean over instances | sentence acc |
|---|---|---|---|---|---|---|
| harness: T_harness, lm 0.5, bonus 1.0 (RETUNED, n_best 10) | 3.296 | 0.5 | 1.0 | 0.522 | 0.522 | 0.0031 |
| T = 1 (raw stream), lm 0.5, bonus 1.0 | 1.000 | 0.5 | 1.0 | 0.483 | 0.481 | 0.0031 |
| T_harness, lm 0.25, bonus 1.0 | 3.296 | 0.25 | 1.0 | 0.565 | 0.567 | 0.0016 |
| T_harness, lm 0.5, bonus 0.0 | 3.296 | 0.5 | 0.0 | 0.477 | 0.475 | 0.0031 |
| T_harness, lm 0.25, bonus 0.0 (= M1-09 val choice) | 3.296 | 0.25 | 0.0 | 0.477 | 0.475 | 0.0047 |
| T_M1-09, lm 0.25, bonus 0.0, n_best 10 (M1-09 val-tuned beam) | 3.285 | 0.25 | 0.0 | 0.477 | 0.475 | 0.0047 |

## sEMG key decoder (day-2 presses, 27 classes)

Chance: uniform 1/27 = 0.037; uniform over letters 1/26 = 0.038; majority class (space) 0.338.

| run | n | accuracy | balanced accuracy | letter accuracy | space accuracy | top-5 |
|---|---|---|---|---|---|---|
| xsession | 14929 | 0.168 | 0.240 | 0.249 | 0.010 | 0.571 |
| xsession_linear | 14929 | 0.162 | 0.175 | 0.177 | 0.132 | 0.525 |
| xsession_permuted | 14929 | 0.022 | 0.032 | 0.034 | 0.000 | 0.137 |
| calib | 14929 | 0.299 | 0.367 | 0.375 | 0.151 | 0.772 |
| xsubject | 14929 | 0.209 | 0.226 | 0.228 | 0.172 | 0.672 |
