# R4 item 9: sentence ECE and AUROC with bootstrap CIs; reliability data

Review: stats m10. Tables: [results/tables.md](results/tables.md). Data: [results/ece_auroc.json](results/ece_auroc.json), reliability bins [results/reliability.json](results/reliability.json), plot [results/reliability.png](results/reliability.png).

Full-fit trust pipelines (the paper's Tab. 1 trust rows), fixed test sets. 95 % percentile bootstrap at the condition's unit (B2T 14 days, sEMG 19 participants, MEG sentences x participants), seed 20261112, B 2000. ECE: 15 equal-width bins. AUROC: positive class = wrong top-1 sentence.

| condition | n | top-1 acc | ECE raw [CI] | ECE calibrated [CI] | AUROC 1 − p̂ (calibrated) [CI] | AUROC guard risk [CI] |
|---|---|---|---|---|---|---|
| B2T ours | 816 | 0.390 | 0.448 [0.419, 0.475] | 0.067 [0.065, 0.104] | 0.797 [0.773, 0.819] | 0.702 [0.677, 0.733] |
| B2T published | 816 | 0.806 | 0.102 [0.058, 0.161] | 0.058 [0.044, 0.090] | 0.710 [0.678, 0.744] | 0.667 [0.620, 0.713] |
| sEMG session-cal. | 551 | 0.459 | 0.154 [0.113, 0.199] | 0.148 [0.117, 0.187] | 0.828 [0.793, 0.860] | 0.647 [0.559, 0.719] |
| sEMG cross-session | 551 | 0.118 | 0.328 [0.293, 0.365] | 0.072 [0.044, 0.102] | 0.755 [0.686, 0.824] | 0.555 [0.500, 0.616] |
| sEMG cross-subject | 551 | 0.038 | 0.500 [0.481, 0.519] | 0.083 [0.069, 0.099] | 0.674 [0.506, 0.812] | 0.497 [0.388, 0.639] |
| MEG | 637 | 0.003 | 0.205 [0.192, 0.220] | 0.101 [0.091, 0.104] | 0.952 [0.883, 0.998] | 0.958 [0.917, 0.989] |

- Point values reproduce the paper (0.448 → 0.067; 0.102 → 0.058; 0.154 / 0.328 / 0.500 → 0.148 / 0.072 / 0.083; AUROC 0.797, 0.83, 0.76, 0.67; guard 0.702).
- The percentile CI of an ECE can sit beside the point value (B2T ours [0.065, 0.104]), because bootstrap resampling adds noise and the binned ECE is biased upwards. Report these CIs as "percentile, biased upwards".
- MEG: only 2 of 637 top-1 sentences are right, so the MEG AUROC compares 635 wrong items with 2 right items and is not informative. The paper's published-gate AUROC (0.710) was not printed in v3; add it if wanted.
- Reliability (10 bins): B2T ours lies near the diagonal; sEMG session-calibrated is under-confident in the 0.5-0.7 bins; cross-subject and MEG put almost all items in the lowest bin.
