---
title: P5-23 learned commit-confidence score vs the p_top1 drop-in guard - results
type: experiment
task: P5-23
updated: 2026-11-18
---

# P5-23: learned commit-confidence score (results)

Pre-registration: [plan.md](plan.md), commit `52ef14c` (library code, tests, docs and `run.py` in the same commit; committed and pushed before any stage ran). Code: [`src/fidetype/trust/commit_score.py`](../../src/fidetype/trust/commit_score.py), `calibrate(confidence="learned")` in [`dropin.py`](../../src/fidetype/trust/dropin.py). Aggregates: [`results/results.json`](results/results.json); guard files (configuration + sheet, no text): `results/guard-*.json`; log: [`results/run.log`](results/run.log). Per-trial decisions (with text): `C:\Users\zhang\bci-data\derived\p5-23\` (local only).

## Verdicts (pre-registered rule)

| set | role | current (p_top1) safe WPM | learned safe WPM | Δ (learned − current) | paired 95 % CI of Δ | half-width | learned wrong-commit (CP95) | controls | **verdict** |
|---|---|---|---|---|---|---|---|---|---|
| T15 M4-13, `val_eval` 701 | **primary** | 2.23 | **2.64** | +0.42 | [0.07, 0.78] | 0.35 | 10/701 = 0.0143 [0.0069, 0.0261] | uniform 0/300, shuffled 0/300 | **learned beats current** |
| T12 v2, test 400 | replication | 1.27 | 1.87 | +0.60 | [−0.18, 1.40] | 0.79 | 15/400 = 0.0375 [0.0211, 0.0611] | uniform 0/300, shuffled 0/300 | no clear difference |

- **P5-23 result (T15 decides): learned beats current.** Safety holds on both sets (observed wrong-commit rate ≤ 0.05; no clear violation). Both null controls pass with 0 commits in both arms on both sets.
- **T12** points the same way (+0.60), but its interval includes 0: 400 trials and few right sentences (31 exactly-right top-1 texts) give a wide interval.
- **P14-23 (gap 53):** the learned T15 safe WPM 2.64 is **below** the no-BCI reference 4.02. P14-23 stays open. The exploratory P14-23 estimate (3.50) was too high: it had a different split, the certificate leak and selection effects.
- **Reference check:** the current arm reproduces the committed decisions exactly: T15 701/701 (P14-05: 104 commits, 17 wrong, 2.23), T12 400/400 (P14-03: 25 commits, 15 wrong). The `config_id`s differ (decoder name); the plan allows this.
- **Split check:** the recomputed split hashes equal the plan (T15 `285b8c0d9baf5a41` / `fadfd84557fcb24b`; T12 `630db9ca864af56f` / `3fe1b31e8e46a035`).

## Details per arm

| | T15 current | T15 learned | T12 current | T12 learned |
|---|---|---|---|---|
| commit threshold | p_top1 ≥ 0.73 | score ≥ 0.87 | p_top1 ≥ 0.30 | score ≥ 0.28 |
| commits / wrong | 104 / 17 | 113 / 10 | 25 / 15 | 31 / 15 |
| error among commits | 0.163 | **0.088** | 0.600 | 0.484 |
| committed right words | 504 | 588 | 54 | 79 |
| recall of exactly-right top-1 trials | 87 / 257 = 0.339 | 103 / 257 = 0.401 | 10 / 31 = 0.323 | 16 / 31 = 0.516 |
| correction time (min) | 8.20 | 4.07 | - | - |
| AUROC of the commit score for "top-1 exactly right" | 0.834 | **0.889** | 0.844 | **0.920** |
| LTT part, in-sample commits / wrong | 54 / 8 | 61 / 8 | 10 / 4 | 14 / 4 |
| safe WPM, trial bootstrap 95 % (conditional) | [1.77, 2.70] | [2.14, 3.17] | [0.50, 2.19] | [0.99, 2.94] |
| no-BCI reference | 4.02 | 4.02 | 4.11 | 4.11 |

The top-1 text is the same in both arms (same decoder, same n-best): P(top-1 exact) is 0.367 on T15 and 0.078 on T12. Only the commit choice differs.

### The fitted scores (fit + policy-grid items only)
- **T15** (451 fit items, 169 right top-1): 9 of 13 features used. Largest standardised weights: acoustic log-probability per character +1.64, number of words −0.87, `p_top1` +0.73, word agreement +0.53, acoustic gap −0.50, n-best entropy −0.35, LM per word +0.28. Dropped by the sign rule: `logit_p_top1`, `margin`, both character-confidence features.
- **T12** (300 fit items, 16 right top-1): 9 of 13 used. Largest: acoustic per character +1.04, LM per word +0.77, margin +0.68, number of words −0.56. Dropped: `p_top1`, `nbest_entropy`, `guard_risk`, `acoustic_gap`.
- On both sets the strongest new signal is the **acoustic score per character** of the top-1 text, which `p_top1` (a softmax over total scores) does not separate from the LM score. Longer sentences get a lower score.

## Notes and limits
- One participant per set, one split, one seed. The intervals are conditional on the calibration (decisions fixed); they do not include the calibration draw.
- The learned guard on T15 commits more (113 vs 104) **and** with fewer wrong commits (10 vs 17). The gain in safe WPM comes from both more right words (+84) and less correction time (−4.1 min).
- The learned score uses the same LTT part (271 / 180 items) as the current guard. It does not use more data; it uses the fit and policy-grid items a second time, which is allowed because LTT uses only the disjoint LTT part.
- Memory: the run's own peak-memory field reads 0 (the `ctypes` call failed silently); an outside check during the T15 stage showed about 0.65-0.76 GB working set. Run times: T15 469 s, T12 247 s (the learned arm reuses the cached decodes: 23 s / 12 s to calibrate).
- Not tested here: LLM features (P15-22), prefix commits (P5-24), the edit-8 word decoder (P14-24), the online methods and the precision / hallucination bounds with a learned score (not available in this version; new gaps 71, 72).

> **Our take:** the learned score is a real, pre-registered gain on T15 (+0.42 safe WPM, about +19 %), with a lower wrong-commit rate. It is far smaller than the exploratory +1.27, so the exploratory P14-23 lever ranking was optimistic. The guard is still the bottleneck: 103 of 257 exactly-right T15 sentences commit. Closing the gap to 4.02 needs the other levers (LLM rescoring, prefix commits) on top of this one.
