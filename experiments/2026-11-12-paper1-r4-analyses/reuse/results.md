# R4 item 7: data reuse, all 12 comparisons, with a test that respects the split overlap

Reviews: stats M5, editor M5. Tables: [results/tables.md](results/tables.md). Data: [results/reuse.json](results/reuse.json). Helper: [emg_who.py](emg_who.py) (participant of each sEMG fit sentence, written to the R4 cache).

## Tests
- **Wilcoxon over splits** (R3 test). The splits are i.i.d. random partitions of one fixed pool, so the test is valid conditional on that pool. It says nothing about new data.
- **Delete-a-cluster jackknife (primary, respects the overlap).** For each day (B2T, 14) or test participant (sEMG, 19): remove its items from the reused, clean and test tables of every split, recompute both thresholds and the mean paired difference. Jackknife SE over clusters, t test with G − 1 df. All splits share the clusters, so the SE includes the between-split dependence. Limit: the fitted pipeline is not refitted without the cluster.
- Cluster sign-flip test (exact) of the per-cluster mean difference: reported, but anti-conservative (one threshold per split is shared by all days, so the day differences are correlated).
- Holm over the 12 comparisons, per test family.

## Results (R = 50, the paper's splits; reused − clean test wrong-commit)

| comparison | mean diff | Wilcoxon p (Holm) | sign test splits +/− | jackknife 95 % CI | **jackknife p (Holm)** |
|---|---|---|---|---|---|
| B2T ours, CRC pure (paper) | +0.0091 | 0.0028 (0.028) | 35/14 | [+0.0050, +0.0131] | **0.0003 (0.004)** |
| B2T ours, CRC max | +0.0066 | 1.1e-5 (1.3e-4) | 26/1 | [+0.0025, +0.0107] | **0.004 (0.046)** |
| B2T ours, LTT pure | +0.0052 | 0.034 (0.24) | 31/13 | [−0.0018, +0.0122] | 0.13 (1) |
| B2T published, CRC pure | +0.0009 | 0.72 (1) | 26/23 | [−0.0051, +0.0068] | 0.76 (1) |
| B2T published, CRC max | +0.0035 | 0.0014 (0.015) | 15/3 | [−0.0015, +0.0085] | 0.16 (1) |
| B2T published, LTT pure | +0.0013 | 0.49 (1) | 23/16 | [−0.0027, +0.0053] | 0.50 (1) |
| sEMG session-cal., CRC pure | −0.0016 | 0.71 (1) | 23/23 | [−0.0106, +0.0074] | 0.71 (1) |
| sEMG session-cal., CRC max | +0.0019 | 0.011 (0.095) | 9/1 | [−0.0004, +0.0042] | 0.10 (0.92) |
| sEMG session-cal., LTT pure | −0.0038 | 0.020 (0.16) | 15/33 | [−0.0110, +0.0034] | 0.28 (1) |
| sEMG cross-session, CRC pure | +0.0073 | 0.036 (0.24) | 18/13 | [+0.0012, +0.0134] | 0.021 (0.21) |
| sEMG cross-session, CRC max | +0.0012 | 0.11 (0.54) | 3/0 | [−0.0006, +0.0029] | 0.19 (1) |
| sEMG cross-session, LTT pure | +0.0008 | 0.81 (1) | 13/15 | [−0.0077, +0.0094] | 0.84 (1) |

R = 200 (B2T): ours CRC pure +0.0032 (Wilcoxon 0.0073, Holm 0.073; jackknife 0.016, Holm 0.17); ours CRC max +0.0036 (Wilcoxon 3e-11; jackknife 0.0048, Holm 0.058); published CRC max +0.0029 (Wilcoxon 4e-9; jackknife 0.16). The R = 50 CRC-pure effect (+0.009) shrinks to +0.003 with 200 splits.

## For the reviser
- Report all 12 comparisons with Holm. After Holm, only B2T ours shows a reuse effect: CRC pure (jackknife Holm 0.004 at R = 50) and CRC max (0.046). The stats reviewer's "max-rule p ≈ 1e-5" is the uncorrected, pool-conditional Wilcoxon; with the overlap-respecting jackknife it is 0.004 (Holm 0.046).
- The sEMG LTT-pure "lowering" (−0.0038, Wilcoxon 0.020) does not survive the jackknife (0.28) or Holm.
- With 200 splits the ours CRC-pure effect is +0.003, and it is not significant after Holm. Drop the reuse p-value from the abstract; keep the principle (calibration data must play no other role).
