# R1 item 1: clean drift baseline

Review items: methods review Major 3 (and Major 4, W13); domain review M9, minor 9. CPU only. Date: 2026-11-11.

**Question.** In M2-13 / M2-16, offline CRC calibrated on the earlier half of each B2T day gave 0.0625 on the later half (target 0.05), and on sEMG cross-session 0.0635. But the CRC calibration data were the same data that fit the temperatures, the conformal sets and the policy grid. Does the "drift" failure survive when the calibration data are disjoint from all fitted parts?

## Answer
1. **The offline-CRC failure does not survive as a robust result.** With clean calibration data, offline CRC gave on the test half:
   - B2T our decoder: **0.0245** [0.014, 0.035] (split `alternate`) and **0.0600** [0.049, 0.071] (split `chrono`).
   - B2T published gate: **0.0478** and **0.0490** (both splits).
   - sEMG cross-session **0.0563** [0.040, 0.074]; session-calibrated **0.0399**; cross-subject 0 (never commits).
   So 1 B2T row of 4 and 1 sEMG row of 3 are above 0.05, and none is significantly above what exchangeable data give (exchangeable-reference p = 0.21 for B2T ours `chrono`, 0.30 for sEMG cross-session).
2. **There is a small shift between calibration and test data on B2T ours**, but it is not consistent. In split `alternate`, the test rate (0.0245) is higher than random splits of the pooled items give (mean 0.0182; p = 0.012), but still below α. In split `chrono` the difference is not significant (p = 0.21). The old 0.0625 therefore mixes data reuse (in-sample temperatures and grid) and split-to-split variation.
3. **Online methods stay at or below α on the clean protocol** (delay 0): B2T ours `chrono` aci 0.0527 / aci_window 0.0490 / window 0.0478 / decay 0.0453; `alternate` 0.0270 / 0.0245 / 0.0245 / 0.0257; published 0.0392–0.0478; sEMG cross-session 0.0526 / 0.0490 / 0.0472 / 0.0381; calib 0.0490 / 0.0490 / 0.0490 / 0.0454. The `aci` a-priori bound at these T is 0.059–0.081 (cross-subject 0.052); the `aci` and `aci_window` certificates are 0.038–0.053 (cross-subject 0.014–0.032).
4. **Shuffled-order control:** random test order gives the same offline rates (offline thresholds do not depend on order) and online rates within ±0.007 of the in-order rates (tables). Order inside the test half does not matter.
5. **Time order is file order.** The B2T pickle has no time, block or trial-number field (keys checked; see tables). Days are contiguous and ascending in the file. sEMG "order" is participant by participant: a between-participant sequence, not a session.

> **Our take:** the paper should drop "within-session drift" as a demonstrated phenomenon. Recommended wording: "With calibration data disjoint from all fitted parts, offline CRC gave 0.025–0.060 (B2T, two splits) and 0.040–0.056 (sEMG); no value was significantly above the rate expected for exchangeable data. The earlier 0.0625 used the fit data for calibration." The online methods remain useful as a guarantee that does not need exchangeability, not as a fix for an observed failure.

## Protocol
| item | B2T '25 (ours, published gate) | sEMG (xsession, calib, xsubject) |
|---|---|---|
| fit-A: temperatures, conformal, guard, policy grid | half of each day's fit trials (`alternate`: odd/even positions; `chrono`: first half of the day's fit trials); `pipe.fit(A, A)` (M6-06 recipe) | fit-A as M6-07 (temperatures, conformal) + fit-B1 (first half of fit-B: policy grid) |
| clean calibration (CRC / LTT only) | the other half of each day's fit trials (401 trials; fit-A 411) | fit-B2 (143 sentences; the M6-07 `c_crc` split) |
| test | test half (816 trials, 14 days) | 551 sentences (19 participants) |
| online | warm start on the clean calibration items, test in order (delay 0 and 10), M2-16 methods and settings | same |
| references | exchangeable reference: pool calibration + test, 1000 random splits of the same sizes; random splits inside the clean test half (n_cal 408); old M2-16 numbers | same (n_cal 275) |
| CI | day cluster (14), B = 2000 | participant cluster (19), B = 2000 |

## Files
- `run.py`, `config.json`, `tables.py`; `results/tables.md` (all rows, certificates, a-priori bounds, shuffled control, references).
- `results/clean_drift_b2t.json`, `results/clean_drift_emg.json`: all numbers.
- `results/items-*.json`: per-item commit scores and both outcomes (no text, no signals), used by `baselines`, `ablation` and `smallcal`.
- Reproduce: `.venv\Scripts\python.exe -I experiments/2026-11-12-paper1-r1-analyses/clean-drift/run.py` (about 15 min), then `... -X utf8 clean-drift/tables.py`.
