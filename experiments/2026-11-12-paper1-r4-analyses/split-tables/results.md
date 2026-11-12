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
