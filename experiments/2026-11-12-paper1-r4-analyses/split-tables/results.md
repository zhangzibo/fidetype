# R4 shared input: item tables of the extended repeated splits

Builder for items 2-7. Manifest: [results/manifest.json](results/manifest.json). Split summary: [results/splits-b2t-200-summary.json](results/splits-b2t-200-summary.json). Logs: `results/run-*.log`. The item tables (derived numbers, no signals or texts) are in the cache outside the repo: `C:/Users/zhang/bci-data/cache/paper1-r4/splits/` (1,050 files) and `splits-b2t-200.json`.

| set | splits | files |
|---|---|---|
| B2T ours / published, guard on | r 50-199 (r 0-49 = R3 cache) | 150 + 150 |
| B2T ours / published, guard off (plain threshold) | r 0-199 | 200 + 200 |
| B2T published, bonus 0 / 0.5 / 1 / 4 (guard on) | r 0-49 | 4 x 50 |
| sEMG calib / xsession / xsubject, guard off | r 0-49 | 3 x 50 |

Checks:
- The R3 generator (seed 3) with R = 200 gives the R3 splits as its first 50 (asserted for every split). The sEMG generator (seed 3 + 100) gives the R3 assignments (asserted).
- A rebuild of R3 split 0 (published) gives the same scores and outcomes as the R3 table (scratch check).
- Frame temperature snapped to 0.02 (B2T; largest relative change 0.283 %) / 0.01 (sEMG; 0.384 %). One new temperature (3.42) was decoded; its cache is in the R4 cache folder.
- Wall time about 37 min on 8 + 3 CPU processes.

## Check 2026-11-17 (P14-15): word-decoder tune overlap, no effect
179-224 of the 400 word-decoder tune trials are in each test set of the 200 splits ([T15 split audit](../../../wiki/questions/t15-split-audit.md), issue D). P14-15 re-tuned the settings inside each split's fit-A (pre-registered). 35 of 200 splits change their setting (28 are exact WER ties). With the 35 guard-on "ours" tables rebuilt, no metric of the R = 200 aggregation moved by its CI half-width (largest: 0.27 of it). The tables stand. Details: [P14-15 results](../../2026-11-17-p14-15-retune/results.md). Guard-off and published-gate tables and the downstream analyses: gap 45 (P14-19).

## Note 2026-11-17 (P14-19): tables with the per-split word setting
For the 35 re-splits whose fit-A tune changes the word setting (P14-15), the published-g1, ours-g0, published-g0 and published-margin tables were rebuilt outside this cache (`derived/p14-18-19/tables`; [results](../../2026-11-17-p14-18-19-followups/results.md)). R3 policies: 0 of 240 metrics move by their CI half-width. The cache tables here are not changed.
