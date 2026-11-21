---
title: P11-16 P11-14 confidence signals for EMG prefix commits - results
type: experiment
task: P11-16
updated: 2026-11-21
---

# P11-16: P11-14 confidence signals for word-prefix commits (results)

Pre-registration: [plan.md](plan.md) (commit `ded01cf`, before any number). Code: `0575c8a` ([run.py](run.py), [launch.py](launch.py), [tests](test_p11_16.py)). Aggregates: [results/results.json](results/results.json), guard sheets `results/guard-*.json`, log `results/run.log`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page and the committed files hold pooled aggregates and per-draw counts only: no per-user value, no text, no id. Per-prompt files: `C:\Users\zhang\bci-data\derived\p11-16\` only. The P11-11, P11-12, P11-14 and P11-17 files were read only.

**`safe-wpm/0.2` is a PROPOSAL. It is not adopted.** Every v0.2 number on this page is labelled "proposed v0.2". Under the adopted v0.1, only complete commits count.

Run: 2026-11-21 08:17 to 08:51, CPU only (isolation class `background`, 2 threads, one process), detached, from a `git archive` snapshot of `0575c8a`. No GPU.

## Outcome
**The P11-14 signals make a strong prefix guard. The primary arm LX-FL gives a certified proposed-v0.2 safe WPM of 9.47 [6.97, 12.75] for one calibration (671 commits, 592 of them prefix commits; 46 wrong = 3.8 % of 1,221 test prompts). This is above arm X (4.25) and above L-FL (6.80). Every control passes. Under the adopted v0.1 the same guard gives only 2.60 [1.35, 4.27], because most of its value comes from prefix commits. With the calibration draw counted (40 draws), the proposed-v0.2 value is 7.18 [0.00, 12.13]: above the no-BCI reference 3.09 on average, but not reliably. 7 of 40 draws are above alpha on the test set.**

## Checks (must pass)
| Id | Check | Result |
|---|---|---|
| C0a | FL top-1, native n-best and the 10 P11-14 signals equal the P11-14 memo | 1,524 / 1,524 windows equal: **pass** |
| C0b | `score_arm("X")` on the P11-12 arm X decisions | proposed v0.2 4.253, 423 commits, 34 wrong: **pass** |
| z0 | draw seed 0 without resampling = the primary LX-FL run | same model digest, threshold 0.86, decisions 1,221 / 1,221 (real, time-shuffled, zero EMG); weighted formula = `safe_wpm` (9.4691): **pass** |
| Splits | calibration and evaluation digests = P11-09 | yes |

## Verdicts (pre-registered)
| Id | Statement | Result | Verdict |
|---|---|---|---|
| **H1 (primary)** | LX-FL certified, safe, non-vacuous (proposed v0.2), V6 pass, value > 4.25 | certified; 46 / 1,221 = 0.038 <= 0.05; 9.47; controls pass | **pass** |
| H2 | value > 6.80 (L-FL) | 9.47 | **pass** |
| H3 | LX-FL > BX-FL (built-in prefix score, same decoder) | 9.47 vs 6.62 | **pass** |
| H4 | vs no-BCI 3.09 (proposed v0.2) | CI [6.97, 12.75] | **clearly above** (one calibration) |
| V6 | controls | calibrate: uniform 0, frame-shuffled 5, input-level 0 of 300 (limit 15); test time-shuffled 0, zero EMG 0 of 1,221 | **pass** |
| H5 (secondary, descriptive) | calibration-inclusive, vs 3.09 | 7.18 [0.00, 12.13] | **above, but inside the combined interval** |

## Main numbers (1,221 track-test prompts of the 8 users; one calibration, seed 0)
| Arm | Threshold | Commits (prefix) | Wrong, rate, CP95 | Error among commits | Proposed v0.2 [95 % CI] | Proposed v0.2 + reading cost | Adopted v0.1 (complete only) | Calibrate controls (unif / frame-shuf / input) |
|---|---|---|---|---|---|---|---|---|
| **LX-FL (primary)** | 0.86 | 671 (592) | 46, 0.038 [0.028, 0.050] | 0.069 | **9.47 [6.97, 12.75]** | 8.65 [6.49, 11.38] | 2.60 [1.35, 4.27] | 0 / 5 / 0 |
| BX-FL (built-in prefix score) | 0.91 | 474 (427) | 25, 0.020 [0.013, 0.030] | 0.053 | 6.62 [4.58, 9.12] | 6.21 [4.37, 8.36] | 1.42 [0.73, 2.21] | 0 / 2 / 0 |
| LS-FL (frozen L-FL score, complete only; exploratory) | 0.66 | 292 (0) | 52, 0.043 [0.032, 0.056] | 0.178 | 7.00 [4.62, 9.99] | 6.61 [4.43, 9.22] | 7.00 [4.62, 9.99] | 0 / 0 / 0 |
| P11-12 arm X (reference) | | 423 (421) | 34, 0.028 | 0.080 | 4.25 [2.69, 6.30] | 4.04 | 0.07 | |
| P11-14 L-FL (reference) | | 285 (0) | 52, 0.043 | 0.182 | 6.80 [4.49, 9.63] | 6.43 | 6.80 | |

Every arm: V1 certified, V2 holds, V3 non-vacuous (proposed v0.2), V4 clearly above 3.09 (one calibration), V6 pass. Test time-shuffled and zero-EMG commits are 0 / 1,221 for every arm.

LX-FL details: 1,219 right words committed (L-FL: 951); correction time 9.0 min (L-FL 20.0). Actions: 671 commits, 414 offers, 136 withholds. Offline decision time with the decode not memoised: p50 93 ms, p95 240 ms (CPU, 2 threads; not a latency claim).

LX-FL model (11 features, none dropped). Largest weights: `lg_pm_fU` +1.24, `lm_pc_k` +1.18, `log_k` -0.83, `lg_p_fU` +0.46, `dist_g` -0.35. Test AUROC over 4,413 prefix rows of committable test windows (2,523 right): `lg_pm_fU` 0.872, `lm_pc_k` 0.792, LX score 0.907.

LS-FL is a check of the external certification. Its commits are close to the P11-14 L-FL guard (292 / 52 vs 285 / 52; value 7.00 vs 6.80). The small difference comes from the threshold grid on c instead of on the `calibrate` temperature-scaled `p_top1`.

> **Our take:** the prefix mass over the wide competitor set U and the prefix LM per character are the useful signals here too. LX-FL commits more prompts (55 % vs 23 % for L-FL) at a lower error among commits (6.9 % vs 17.8 %): it commits the sure first words and stops before the unsure tail. The same decoder with the built-in prefix score (BX-FL) reaches 6.62, so about half of the gain over arm X comes from the decoder and the rest from the signals.

## Calibration-inclusive interval (LX-FL, proposed v0.2; secondary)
Same 40 calibration draws as P11-17 (seeds, bootstrap and split order from P11-17), the LX model refitted per draw, LTT and all controls repeated per draw, user-cluster inner bootstrap (B 2,000).

| Measure | Value |
|---|---|
| Point (mean of 40 draw values) | **7.18** |
| Combined 95 % interval (pooled 40 x 2,000) | **[0.00, 12.13]** |
| Draw statuses | certified 33, above-alpha 7 (earn 0 by the credit rule); no control failure |
| Draw values: median, SD, range | 8.63, 3.47, [0.00, 10.28] |
| Draws above 3.09 | 33 / 40 (82.5 %) |
| SD between draws / within draw | 3.47 / 1.24 (ratio 2.80) |
| Analytic normal interval | [-0.04, 14.40] |
| Mean commits / wrong per draw | 639.9 / 46.0 |
| Threshold range | 0.78 to 0.98 |
| Max calibrate control commits / max test control commits (any draw) | 9 / 300 (limit 15) / 0 |
| Variant (a): above-alpha draws keep their value | 9.03 [5.82, 12.86] |
| vs P11-17 L-FL, same draw k | LX higher in 32 / 40, equal in 1; mean difference +2.18 |

The 7 above-alpha draws have 62 to 69 wrong commits (rate 0.051 to 0.057) and are the draws with the most commits (693 to 727). Their raw values (10.17 to 11.06) are the highest. As in P11-17, the guards that spend their risk budget most are the ones that cross alpha on the test set.

> **Our take:** the single-calibration value (9.47, CI fully above 3.09) is not a public claim. With the calibration draw counted, LX-FL is above no-BCI on average (7.18; P11-17 L-FL: 5.00) and higher than L-FL in 32 of the same 40 draws. But 17.5 % of the draws earn 0, so the lower end is 0. A reliable lower end needs a lower-variance guard (gap 159, P11-19) or a margin below alpha. All of this holds only under the proposed v0.2.

## Deviations
None from the plan.

## Gap rule
**Gap 126 closes.** H1 is reported under the plan, and C0a, C0b and z0 passed. H1 holds.

## Limits
- 8 users, one track-test session each; the CI unit is the user.
- Proposed v0.2 only for prefix credit; adopted v0.1 value 2.60.
- LX-FL and LS-FL are certified outside `calibrate` (the library LTT function and the library controls): no `TrustGuard` file, no frame temperature, no guard-risk gate.
- The guarantee assumes exchangeable val / test sessions of the same users. Pinned decoder, gate, LM, lexicon and feature set (as P11-17).
- Offline only; the U set needs a second (no-LM) beam and an exact CTC re-scoring per window (P11-15, gap 125).
- No score card (v0.2 is proposed).

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-16-emg-prefix-confidence/test_p11_16.py` |
| Full run (detached; about 34 min CPU) | `.venv\Scripts\python.exe experiments/2026-11-21-p11-16-emg-prefix-confidence/launch.py 0575c8a` (needs `derived\p11-09\`, `derived\p11-11\`, `derived\p11-12\`, `derived\p11-14\`) |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-16\DONE` exists; stop the python processes whose command line has `p11-16-emg-prefix-confidence` |
