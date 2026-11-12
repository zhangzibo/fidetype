# R4 item 8: clean-up numbers

Reviews: stats m1, m2, m6; editor M4. Tables: [results/tables.md](results/tables.md). Data: [results/cleanup.json](results/cleanup.json). Inputs: R3 `unified-ci/results/ci.json`, R3 user-model rerun, R3 `per_split.json`, R4 split tables, committed clean-drift items.

## 1. MEG Tab. 1 CIs (verified)
| policy | unified two-way bootstrap (seed 20261112, B 2000) | printed in v3 Tab. 1 |
|---|---|---|
| trust (= always offer) | 3.20 **[3.01, 3.44]** (3.0148, 3.4389) | [3.02, 3.44] (round-1 value) |
| gaze typing | 3.15 **[3.02, 3.31]** (3.0245, 3.3052) | [3.03, 3.31] (round-1 value) |
| always commit | 2.58 [2.31, 2.88] | same |

The stats reviewer is right. The teaser figure (`papers/paper1/make_figures.py`, `meg_rows`) takes MEG CIs from the G1 harness file with a **sentence** bootstrap: trust 3.20 [3.07, 3.36], commit 2.58 [2.41, 2.76]. This is a third interval; switch the figure to the unified two-way values.

## 2. Exact Clopper-Pearson bounds
| count | one-sided 95 % upper | two-sided 95 % | rule of three |
|---|---|---|---|
| 0/816 (B2T fixed test) | **0.0037** | [0, 0.0045] | 0.0037 |
| 0/551 (sEMG test) | 0.0054 | [0, 0.0067] | 0.0054 |
| 0/637 (MEG) | 0.0047 | [0, 0.0058] | 0.0047 |
| 0/300 (B2T controls) | 0.0099 | [0, 0.0122] | 0.0100 |
| 0/200 (sEMG controls) | 0.0149 | [0, 0.0183] | 0.0150 |
| 0/256 (sEMG non-templated) | 0.0116 | [0, 0.0143] | 0.0117 |
| 1/256 | 0.0184 | [0.0001, 0.0216] | |
| 2/551 | 0.0114 | [0.0004, 0.0130] | |
| 4/50 (LTT max > α, ours) | 0.174 | [0.022, 0.192] | |
| 1/50 (LTT max > α, published) | 0.091 | [0.0005, 0.107] | |
| 7/50 (CRC max > α) | 0.247 | [0.058, 0.267] | |

Verified: "0.0045 (816 items)" in the Tab. 1 caption is the two-sided upper limit; the one-sided 95 % bound is 0.0037.

## 3. Frame-temperature snapping (largest relative change)
B2T 0.267 % (R3, 50 splits; 0.283 % over 200 splits); sEMG session-calibrated **0.384 %**, cross-session 0.275 %, cross-subject 0.227 %. Verified: write "0.27 % (B2T), 0.38 % (sEMG)".

## 4. Comparator "the same fitted policy without commits"
Definition: the same fit-A pipeline and fitted policy with the commit threshold λ = +∞. No trial is committed; every trial takes the policy's non-commit path (offer the n-best / word alternatives, else retype). It is "always offer" with the same fitted pipeline. Gain = eWPM(rule) − eWPM(no commit), paired by split.

| condition | rule | R | gain mean (MC SE) | 5th-95th pct over splits | share > 0 |
|---|---|---|---|---|---|
| B2T ours | LTT max | 50 | **+0.114** (0.005) | +0.063 to +0.164 | 1.00 |
| B2T ours | LTT max | 200 | +0.111 (0.002) | +0.061 to +0.168 | 1.00 |
| B2T published | LTT max | 50 | **+0.510** (0.007) | +0.439 to +0.599 | 1.00 |
| B2T published | LTT max | 200 | +0.514 (0.004) | +0.434 to +0.608 | 1.00 |
| B2T ours / published | plain + LTT max | 200 | +0.104 / +0.477 | | 1.00 |
| sEMG session-cal. / cross-session | LTT max | 50 | +0.033 / −0.001 | | 0.96 / 0.42 |

Fixed splits (paired day-cluster bootstrap CI): ours split A +0.058 [0.034, 0.090], split B +0.125 [0.077, 0.188]; published split A +0.537 [0.439, 0.636] (split B in tables.md).
The v3 numbers 0.11 / 0.51 are reproduced (λ = +∞ gives the same values as the v3 proxy). In v3 the brackets (0.06-0.16) are percentiles over splits, not CIs; the MC standard error of the mean is 0.005 / 0.007, and the CIs over test days are the fixed-split values above.

## 5. Always commit vs trust in the 9 user-model variants
Variants where always commit is faster than trust (point values) / CI of (trust − always commit) entirely below 0 / entirely above 0:

| condition | always commit faster | CI < 0 | CI > 0 |
|---|---|---|---|
| B2T ours | 5 of 9 | 1 (fallback 40 cpm) | 3 |
| **B2T published** | **9 of 9** | **9** | 0 |
| sEMG session-cal. | 1 of 9 | 0 | 5 |
| sEMG cross-session | 2 of 9 | 0 | 7 |
| sEMG cross-subject | 2 of 9 | 2 | 7 |
| MEG | 1 of 9 | 1 | 7 |

Full table with every variant: tables.md section 5. The editor's "always commit was the fastest policy in all 9 user-model variants" holds for the published gate only (−0.46 to −1.47 eWPM). On our decoder the sign depends on the user model.
