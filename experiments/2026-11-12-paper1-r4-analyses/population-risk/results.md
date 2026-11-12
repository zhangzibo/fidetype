# R4 item 3: population risk without the low bias; exceedance shares with exact CIs

Review: stats M4(b, c). Tables: [results/tables.md](results/tables.md). Data: [results/population_risk.json](results/population_risk.json). Seeds: 20261112 (App. R pools), 20261113 (split pools).

## (a) App. R pools (full-fit pipeline, test pool of 816 B2T trials / 551 sEMG sentences), 2,000 draws

Share of draws whose risk exceeds α = 0.05 (exact CP95), n_cal = 408 (B2T) / 275 (sEMG):

| pool | rule | incl-cal (App. R, biased low) | held-out (test noise) | **with replacement (exact population risk)** |
|---|---|---|---|---|
| B2T ours | LTT pure | 0.011 [0.007, 0.017] | 0.151 [0.136, 0.167] | **0.047 [0.038, 0.057]** |
| B2T ours | CRC pure | 0.325 | 0.419 | 0.373 [0.352, 0.395] |
| B2T published | LTT pure | 0.009 [0.006, 0.015] | 0.120 [0.107, 0.136] | **0.041 [0.033, 0.051]** |
| B2T published | CRC pure | 0.328 | 0.422 | 0.384 [0.362, 0.405] |

- n_cal = 100 and sEMG: tables.md. Mean population risk of CRC pure stays ≤ α in every design (B2T 0.047-0.048), as CRC promises.
- The App. R value (0.5 % / 1.5 % over 200 splits) is the biased "incl-cal" design. The exact population exceedance of LTT is 4.7 % / 4.1 %: still within δ = 0.1, but 4-9 times higher than printed.

## (b) Repeated splits: exact population risk (pool = clean calibration + test of each split; 200 with-replacement draws per split)

| condition | R | rule | test-set: splits > α [CP95] | population: share > α [CP95] | population mean |
|---|---|---|---|---|---|
| B2T ours | 50 | LTT max | 4/50 = 0.080 [0.022, 0.192] | 0.026 [0.023, 0.029] | 0.032 |
| B2T ours | 50 | CRC max | 7/50 = 0.140 [0.058, 0.267] | 0.169 | 0.039 |
| B2T ours | 50 | LTT pure | 8/50 = 0.160 [0.072, 0.291] | 0.060 | 0.035 |
| B2T ours | 50 | CRC pure | 17/50 = 0.340 [0.212, 0.488] | 0.392 | 0.048 |
| B2T ours | 200 | LTT max | 15/200 = 0.075 [0.043, 0.121] | 0.020 [0.018, 0.021] | 0.031 |
| B2T ours | 200 | CRC max | 37/200 = 0.185 [0.134, 0.246] | 0.123 | 0.037 |
| B2T published | 50 | LTT max | 1/50 = 0.020 [0.001, 0.106] | 0.014 [0.012, 0.016] | 0.030 |
| B2T published | 50 | CRC max | 7/50 = 0.140 [0.058, 0.267] | 0.074 | 0.036 |
| B2T published | 200 | LTT max | 11/200 = 0.055 [0.028, 0.096] | 0.016 [0.015, 0.017] | 0.030 |
| B2T published | 200 | CRC max | 35/200 = 0.175 [0.125, 0.235] | 0.091 | 0.036 |
| sEMG session-cal. | 50 | LTT max | 0/50 [0, 0.071] | 0.000 | |
| sEMG cross-session | 50 | LTT max | 0/50 [0, 0.071] | 0.002 | |

Population shares are over R x 200 draws; draws inside one split share the pool, so their CP interval is conditional on the R pools.

## (c) LTT max vs CRC max (exact McNemar on test-set exceedance, paired by split)

| condition | R = 50 | R = 200 |
|---|---|---|
| B2T ours | 0 vs 3 discordant, p = 0.25 | 0 vs 22, p = 4.8e-7 |
| B2T published | 0 vs 6, p = 0.031 | 0 vs 24, p = 1.2e-7 |

LTT max is never above α in a split where CRC max is not (it is always at least as strict). With 50 splits the difference is not significant on our decoder; with 200 splits it is clear on both decoders.

## For the reviser
- Replace "(allowed: 10 %)" with the shares and their CIs: LTT max 4/50 = 0.08 [0.02, 0.19] and 1/50 = 0.02 [0.001, 0.11]; with 200 splits 0.075 [0.043, 0.121] and 0.055 [0.028, 0.096].
- App. R: replace 0.5 % / 1.5 % (biased low) with the with-replacement values 4.7 % [3.8, 5.7] / 4.1 % [3.3, 5.1] (LTT pure, n_cal 408).
- The population view gives a cleaner statement: over the repeated splits, the exact population risk of LTT max exceeded α in 2.0 % / 1.6 % of draws (R = 200), LTT pure in 6.0 % / 5.9 %, both ≤ δ; CRC pure in 39 % / 41 % (not promised).
