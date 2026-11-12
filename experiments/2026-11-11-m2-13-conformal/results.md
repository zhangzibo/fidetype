---
title: "M2-13: conformal risk control for the COMMIT threshold"
type: experiment
updated: 2026-11-11
---

# M2-13: conformal risk control (CRC) and Learn then Test (LTT) for the trust gate

Goal: give the wrong-commit limit (α = 0.05) a finite-sample guarantee. Before, the threshold fit used the plug-in rule "empirical wrong-commit ≤ α on validation". On Brain-to-Text '25 the test rate was then 0.059 (our decoder) and 0.044 (published-sentence gate).

- Code: `src/fidetype/trust/risk_control.py` (our own implementation), harness hooks in `src/fidetype/eval/harness.py`. Tests: `tests/test_trust_risk_control.py` (16), 3 new tests in `tests/test_trust_harness.py`. Full suite: **239 passed, 4 skipped** (CPU `.venv`).
- Script: [run.py](run.py), settings: [config.json](config.json). Tables: [results/tables.md](results/tables.md). Numbers: `results/splits.json`. Per-trial scores and outcomes (no text): `results/items-*.json`. Log: `results/run.log`.
- Run: `.venv\Scripts\python.exe -I experiments/2026-11-11-m2-13-conformal/run.py` (about 8 min on CPU, 2 threads, no GPU). `--stages splits,tables` reuses the item files (10 s).
- Method: [conformal risk control](../../wiki/concepts/conformal-risk-control.md). Wiki result: [m2-13-conformal-result](../../wiki/questions/m2-13-conformal-result.md).

## Main finding
- **CRC meets the target in expectation.** Mean test wrong-commit over 200 random splits: 0.046–0.048 (our decoder) and 0.047–0.048 (published gate), all ≤ 0.05. The old fixed gate gives 0.059 on our decoder (above α in 86–100 % of splits).
- **The guarantee is marginal.** With CRC the 95th percentile of the per-split rate is 0.071–0.094. One session can be above 0.05. LTT (δ = 0.1) limits the tail: 95th percentile 0.048–0.061, mean 0.019–0.035.
- **The eWPM cost is small.** Our decoder: 11.57 (old) → 11.53 (CRC) → 11.52 (LTT) at n_cal 408 (−0.3 % to −0.4 %). Published gate: 18.77 → 18.78 (CRC) → 18.70 (LTT). With only 100 calibration trials, LTT costs more: 11.45 (−0.9 %) and 18.49 (−1.4 %). All stay far above gaze typing alone (4.08).
- **Without exchangeability the CRC guarantee fails.** Calibrated on the earlier half of each day and tested on the later half: CRC 0.0625 (ours) and 0.049 (published). LTT stayed below α (0.047, 0.040), but it has no guarantee in this setting either.
- **MEG (M1-15 full-r1) is degenerate.** No test top-1 sentence is right. Only 2.2 % of trials can commit at all (the other rules block the rest). The old gate commits nothing. CRC uses part of its budget on these wrong commits (0.013–0.019) and gives no eWPM gain (3.22–3.23). CRC bounds the risk; it does not minimise it.

## Setting
| item | value |
|---|---|
| Data | B2T '25 test half (816 trials, 14 days; M6-06 split). MEG M1-15 full-r1 test (637 trials, 17 sentences, 19 participants) |
| Upstream (fixed) | Frame / sentence temperatures, conformal sets, guard and the other policy thresholds exactly as in M6-06 (fit on the B2T fit half) and in the M1-15 eWPM check (fit on MEG val). Check: the old gate reproduces 0.0588 / 11.546 eWPM and 0.0441 / 18.767 |
| Tuned here | Only `commit_p` |
| Commit score | calibrated `p_top1` if the other rules allow COMMIT, else −inf (never commits) |
| Loss | 1 if the commit would be wrong (top-1 ≠ truth), else 0. The non-commit action has loss 0 here (no OFFER_WORDS) |
| Splits | 200 random splits of the test set: n_cal = 100 or 408 for calibration, the rest for test. Seed 0 |
| eWPM | Exact per-trial mix of the two outcomes (COMMIT or the non-commit action) from the simulated `aac_gaze` user, as in M6-06. The mix was checked against the full harness run trial by trial |

### Methods
| name | rule | guarantee |
|---|---|---|
| old gate | `commit_p` from the M6-06 / M1-15 grid fit, fixed | none |
| plug-in re-tune | max eWPM on cal, subject to empirical wrong-commit ≤ α | none |
| CRC | smallest λ with (n R̂(λ) + 1) / (n + 1) ≤ α | E[wrong-commit] ≤ α (exchangeable data) |
| CRC + eWPM tune | max eWPM on cal over λ ≥ λ_CRC | same as CRC (any λ ≥ λ_CRC is valid) |
| LTT | fixed-sequence test on the grid 1.00, 0.99, …, 0.00; exact binomial p-values; δ = 0.1 | P(R(λ̂) ≤ α) ≥ 0.9 |

## Results: B2T '25, our decoder (n_cal 408, n_test 408)
| method | wrong-commit mean ± se | p95 | share of splits > α | commit rate | eWPM mean [p05, p95] | silent error |
|---|---|---|---|---|---|---|
| old gate | 0.0586 ± 0.0006 | 0.0711 | 0.86 | 0.233 | 11.57 [11.17, 11.98] | 0.0025 |
| plug-in re-tune | 0.0435 ± 0.0013 | 0.0760 | 0.35 | 0.181 | 11.52 [11.13, 11.91] | 0.0010 |
| **CRC** | **0.0483 ± 0.0010** | 0.0712 | 0.45 | 0.194 | 11.53 [11.13, 11.92] | 0.0016 |
| CRC + eWPM tune | 0.0403 ± 0.0012 | 0.0712 | 0.32 | 0.172 | 11.52 [11.11, 11.91] | 0.0008 |
| **LTT** | **0.0345 ± 0.0009** | 0.0564 | 0.14 | 0.156 | 11.52 [11.12, 11.91] | 0.0005 |

n_cal 100 (n_test 716): old 0.0586 (p95 0.064, eWPM 11.55); plug-in 0.0492 (p95 0.098, 11.52); CRC **0.0464** (p95 0.094, 11.52); CRC + tune 0.0412 (p95 0.083, 11.51); LTT **0.0189** (p95 0.048, share > α 0.04, 11.45).

## Results: B2T '25, published-sentence gate (n_cal 408, n_test 408)
| method | wrong-commit mean ± se | p95 | share of splits > α | commit rate | eWPM mean [p05, p95] | silent error |
|---|---|---|---|---|---|---|
| old gate | 0.0441 ± 0.0005 | 0.0588 | 0.20 | 0.471 | 18.77 [18.14, 19.43] | 0.0035 |
| plug-in re-tune | 0.0503 ± 0.0011 | 0.0786 | 0.45 | 0.488 | 18.79 [18.16, 19.45] | 0.0044 |
| **CRC** | **0.0478 ± 0.0010** | 0.0761 | 0.41 | 0.479 | 18.78 [18.16, 19.42] | 0.0041 |
| CRC + eWPM tune | 0.0478 ± 0.0010 | 0.0761 | 0.41 | 0.479 | 18.78 [18.16, 19.42] | 0.0041 |
| **LTT** | **0.0345 ± 0.0010** | 0.0614 | 0.14 | 0.427 | 18.70 [18.08, 19.36] | 0.0023 |

n_cal 100 (n_test 716): old 0.0442 (18.75); plug-in 0.0549 (p95 0.088, 18.79); CRC **0.0468** (p95 0.084, 18.74); LTT **0.0195** (p95 0.049, 18.49).

The old gate was below α on this decoder by chance of the fit: the same plug-in rule, re-tuned on this data, gives 0.050–0.055.

## Results: MEG M1-15 full-r1 (n_cal 408, n_test 229)
| method | wrong-commit | commit rate | eWPM |
|---|---|---|---|
| old gate | 0.0000 | 0.000 | 3.23 |
| plug-in re-tune | 0.0108 | 0.011 | 3.22 |
| CRC | 0.0186 | 0.019 | 3.22 |
| CRC + eWPM tune | 0.0108 | 0.011 | 3.22 |
| LTT | 0.0207 | 0.021 | 3.22 |

All commits on MEG are wrong. All methods stay below α. Gaze typing alone: 3.15 (M1-15). No method changes the MEG conclusion (parity with gaze typing).

## Earlier data: calibrate on the fit half, test on the test half (one shot)
This is a deployment-like check: calibrate on the first half of each day, use the threshold on the second half. It is **not** exchangeable.

| data | old | plug-in | CRC | LTT |
|---|---|---|---|---|
| B2T ours: wrong-commit / eWPM | 0.0588 / 11.55 | 0.0637 / 11.55 | **0.0625** / 11.55 | 0.0466 / 11.51 |
| B2T published: wrong-commit / eWPM | 0.0441 / 18.77 | 0.0490 / 18.80 | 0.0490 / 18.80 | 0.0404 / 18.73 |
| MEG: wrong-commit / eWPM | 0.0000 / 3.23 | 0.0063 / 3.23 | 0.0220 / 3.23 | 0.0000 / 3.23 |

The later trials of each day have more errors at the same confidence. CRC cannot see this drift. So: calibrate inside the session that the gate serves, and re-calibrate often. For a drifting stream, combine it with adaptive conformal inference (`AdaptiveConformal`).

## Synthetic check (unit tests)
- CRC, 2000 random calibration / test draws, n_cal 50 and 200: mean test risk ≤ α + 3 se, and ≥ α − 0.02 (not trivially conservative).
- Plug-in rule with n_cal 40: mean test risk above α. CRC on the same draws: ≤ α.
- LTT, 400 draws, n_cal 300, true risk from 200,000 items: share of draws with true risk > α ≤ δ + 3 se.

## Notes and limits
- "Share of splits > α" counts the empirical rate on a finite test part. It includes test-sampling noise (n_test 408: se about 0.011). So it is not P(R > α), and it can be above δ for LTT (0.14 at n_cal 408). With n_test 716 it is 0.04.
- The trials of one test half are treated as exchangeable, but they come from 14 days. A per-day split would be closer to real use. Each day has only 22–37 test trials: too few for α = 0.05 (CRC needs n ≥ 19 to commit at all).
- One participant (B2T), one decoder seed. On MEG all commits are wrong, so MEG tests only the "no harm" side.
- The non-commit losses are 0 here. With OFFER_WORDS enabled, the code uses an upper bound (top-1 wrong) for that loss.
- The tie-break of the eWPM tune (prefer the larger threshold) was added after the first run; the numbers did not change.
