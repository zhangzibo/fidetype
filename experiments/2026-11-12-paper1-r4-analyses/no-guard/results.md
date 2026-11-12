# R4 item 5: the no-guard configuration (plain threshold) in Tables 1-2 and on the control streams

Reviews: editor M6, stats. Tables: [results/tables.md](results/tables.md). Data: [results/no_guard.json](results/no_guard.json) (assembled from `no_guard_b2t.json`, `no_guard_emg.json`, `no_guard_meg.json`). New decodes went to the R4 cache.

Checks: the full-fit plain threshold reproduces the paper's appendix rows (B2T ours 11.51 eWPM / 0.036; published 18.62 / 0.025) and the R3 unified `no_guard` rows. The guard-on rows recomputed from the committed items reproduce Tab. 1 (e.g. ours split A LTT max 0.0245).

## Table 1 rows (fixed test sets; 95 % unified bootstrap CIs)

| condition | row | guard off: wrong-commit [CI], commit, eWPM | guard on (paper) |
|---|---|---|---|
| B2T ours | full fit, plug-in | 0.0355 [0.025, 0.046], 0.165, 11.51 | 0.059, 0.23, 11.55 |
| B2T ours | split A, LTT max | 0.0404 [0.030, 0.051], 0.183, 11.55 (= plug-in = CRC max) | 0.0245, 0.100, 11.48 |
| B2T ours | split B, LTT max | 0.0294 [0.021, 0.038], 0.147, 11.53 (CRC max 0.0343) | 0.0515, 0.192, 11.54 |
| B2T published | full fit, plug-in | 0.0245 [0.014, 0.038], 0.381, 18.62 | 0.044, 0.47, 18.77 |
| B2T published | split A, LTT max | 0.0270 [0.016, 0.040], 0.391, 18.63 | 0.0294, 0.403, 18.65 |
| B2T published | split B, LTT max | 0.0245 [0.014, 0.038], 0.387, 18.63 | 0.0306, 0.415, 18.68 |
| sEMG session-cal. | full fit / LTT max | 0.0036 [0, 0.009], 0.038, 8.02 / 7.98 | identical |
| sEMG cross-session | full fit / LTT max | 0.0036 [0, 0.009], 0.018, 4.68 | identical |
| sEMG cross-subject | full fit / LTT max | 0 (≤ 0.0054), 0 commits | identical |
| MEG | full fit / clean split LTT max | 0 (≤ 0.0047), 0 commits, 3.20 [3.01, 3.44] / 3.21 | identical |

Joint LTT β = 0.10 with the guard off commits nothing in every fixed row (tables.md).

## Table 2 rows (repeated splits; mean wrong-commit, splits > α [CP95], commit)

| condition | R | plain + LTT max | plain + CRC max | plain plug-in | guard + LTT max (paper) |
|---|---|---|---|---|---|
| B2T ours | 50 | 0.0305, 0/50 [0, 0.07], 0.143 | 0.0341, 2/50 | 0.0376, 5/50 | 0.0304, 4/50, 0.147 |
| B2T ours | 200 | 0.0296, 0/200 [0, 0.02], 0.141 | 0.0329, 0.05 | 0.0350, 0.10 | 0.0321, 0.07, 0.152 |
| B2T published | 50 | 0.0244, 0/50, 0.363 | 0.0244, 0/50 | 0.0244, 0/50 | 0.0307, 1/50, 0.392 |
| B2T published | 200 | 0.0239, 0.01 [0, 0.03], 0.367 | 0.0248, 0.03 | 0.0251, 0.03 | 0.0303, 0.06, 0.394 |
| sEMG session-cal. | 50 | 0.0106, 0/50, 0.093 | 0.0125 | 0.0146 | 0.0106, 0/50 |
| sEMG cross-session | 50 | 0.0058, 0/50, 0.015 (no commit 32 %) | 0.0068 | 0.0082 | 0.0057 (no commit 34 %) |
| sEMG cross-subject | 50 | 0, never commits | | | 0 |

eWPM: plain threshold rows are within 0.03 eWPM of the guard rows (tables.md).

## Control streams (commits / n)

| condition | policy | real | other trial / sentence | frame shuffled | uniform | zeros / shuffled MEG / permuted decoder |
|---|---|---|---|---|---|---|
| B2T ours | plain threshold, full fit | 38/300 | 38/300 | **2/300** | **203/300** (wrong 0.68) | — |
| B2T ours | plain + LTT max (split A) | 43/300 | 43/300 | **3/300** | **198/300** (wrong 0.66) | — |
| B2T ours | plain + joint LTT β=0.10 | 0 | 0 | 0 | 0 | — |
| B2T published | plain threshold / + LTT max | 106 / 110 | 0 | 0 | 0 | — |
| sEMG session-cal. | plain / + LTT max | 8/200 | 8/200 | 0 | — | 0, 0 |
| sEMG cross-session | plain / + LTT max | 5/200 | 5/200 | 0 | — | 0, 0 |
| sEMG cross-subject | all | 0 | 0 | 0 | — | 0, 0 |
| MEG | all | 0/637 | 0 | 0 | 0 | 0, 0 |

With the guard (paper, Sec. 7.6) the layer committed none of the B2T or sEMG signal-destroying controls (0/300, bound 0.0099; 0/200, bound 0.015).

## For the reviser
- **The plain threshold fails the signal-destroying control on our intracortical decoder.** It committed 203 of 300 uniform (no-information) streams, 68 % of them wrong, and 2-3 of 300 frame-shuffled streams. Uniform streams give flat phoneme posteriors; the word decoder then returns a fluent LM-driven sentence with a high calibrated p_top1. The guard (low evidence share, consistency) is what rejects these streams. The published gate and sEMG did not commit any control without the guard.
- So the frozen configuration "plain threshold + LTT max" cannot be carried forward as is. Either keep the guard (or at least its low-evidence term) as a pre-filter, or add an input-validity check, or freeze joint LTT (which commits nothing on controls here because it commits almost nothing).
- On real data the guard does not help the wrong-commit rate: plain + LTT max had 0/200 splits above α on our decoder (guard: 7 %) and the lower mean on the published gate (0.024 vs 0.030).
