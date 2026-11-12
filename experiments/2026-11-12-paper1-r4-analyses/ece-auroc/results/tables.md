# Sentence ECE and AUROC with bootstrap CIs

Full-fit trust pipelines on the fixed test sets. 95 % percentile bootstrap at the condition's unit (seed 20261112, B 2000). AUROC: positive class = wrong top-1 sentence.

| condition | n | top-1 acc | ECE raw [CI] | ECE calibrated [CI] | AUROC 1 − p̂ calibrated [CI] | AUROC 1 − p̂ raw [CI] | AUROC guard risk [CI] |
|---|---|---|---|---|---|---|---|
| b2t-ours | 816 | 0.390 | 0.448 [0.419, 0.475] | 0.067 [0.065, 0.104] | 0.797 [0.773, 0.819] | 0.765 [0.728, 0.800] | 0.702 [0.677, 0.733] |
| b2t-published | 816 | 0.806 | 0.102 [0.058, 0.161] | 0.058 [0.044, 0.090] | 0.710 [0.678, 0.744] | 0.707 [0.672, 0.748] | 0.667 [0.620, 0.713] |
| emg-calib | 551 | 0.459 | 0.154 [0.113, 0.199] | 0.148 [0.117, 0.187] | 0.828 [0.793, 0.860] | 0.837 [0.804, 0.869] | 0.647 [0.559, 0.719] |
| emg-xsession | 551 | 0.118 | 0.328 [0.293, 0.365] | 0.072 [0.044, 0.102] | 0.755 [0.686, 0.824] | 0.751 [0.674, 0.827] | 0.555 [0.500, 0.616] |
| emg-xsubject | 551 | 0.038 | 0.500 [0.481, 0.519] | 0.083 [0.069, 0.099] | 0.674 [0.506, 0.812] | 0.681 [0.546, 0.797] | 0.497 [0.388, 0.639] |
| meg-async | 637 | 0.003 | 0.205 [0.192, 0.220] | 0.101 [0.091, 0.104] | 0.952 [0.883, 0.998] | 0.961 [0.898, 1.000] | 0.958 [0.917, 0.989] |

Reliability data: `reliability.json` (10 bins of calibrated p_top1; count, mean confidence, accuracy, CP 95 %). Plot: `reliability.png`.
