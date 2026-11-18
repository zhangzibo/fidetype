---
title: P14-03 replay validation of the drop-in trust API - results
type: experiment
task: P14-03
updated: 2026-11-15
---

# P14-03: held-out wrong-commit of the drop-in API on two public replay sets (results)

Plan (committed before the runs): [plan.md](plan.md), commit `859acb8`. Code: [run.py](run.py). Numbers: `results/results.json`; guard files (no signal, no text): `results/guard-*.json`; log: `results/run.log`. Per-trial decisions and audit logs: `C:\Users\zhang\bci-data\derived\p14-03-replay-validation\` only.

## Outcome: **pass on both sets** (pre-declared rule)

| set | split | calibrate | held-out commits | wrong commits | wrong-commit rate [CP95] | pass (rate <= 0.05) | CP95 upper <= 0.05 |
|---|---|---|---|---|---|---|---|
| T15 (B2T '25, CC0) | by trial: 722 `val_select` -> 701 `val_eval` | guard returned; uniform 0/300, shuffled 1/300 (allowed 15) | 2 / 701 | 2 | **0.0029** [0.0003, 0.0103] | **yes** | yes |
| T12 (B2T '24, CC0) | by session: 14 sessions (480) -> 10 later sessions (400) | guard returned; uniform 0/300, shuffled 0/300 (allowed 15) | 25 / 400 | 15 | **0.0375** [0.0211, 0.0611] | **yes** | **no** |

alpha 0.05, delta 0.1, seed 0, all other `calibrate` arguments at their defaults. Both null controls passed on both sets, so no config was refused.

### Details
| | T15 alpha 0.05 | T12 alpha 0.05 |
|---|---|---|
| config_id | `tcfg-09baa8a632ade86e` | `tcfg-ca5af419ca3738f1` |
| calibration split (`calibrate`, seed 0) | 180 fit + 271 grid + 271 LTT | 120 fit + 180 grid + 180 LTT |
| frame T (fitted on `stream_texts`) / sentence T | 1.2889 / 11.957 | 2.5281 / 20.0 (upper limit) |
| lambda_hat (feasible) / final commit threshold | 0.22 (yes) / 0.3 (grid) | 0.29 (yes) / 0.3 (grid) |
| LTT in-sample commits / wrong | 2 / 1 | 10 / 4 |
| held-out commit / offer / withhold | 2 / 699 / 0 | 25 / 375 / 0 |
| error among commits [CP95] | 1.00 [0.158, 1.000] (2 of 2) | 0.60 [0.387, 0.789] |
| empty commits | 0 | 0 |
| eWPM (secondary; public simulated user, 1 attempt) | 6.02 | 7.13 |
| calibrate + 701 / 400 decisions | 326 s | 177 s |

alpha 0.10 (descriptive): the same decisions on both sets (T15 `tcfg-6626f8bf11e7ad19`, lambda_hat 0.21; T12 `tcfg-059087ff4c4c633a`, lambda_hat 0.25). The policy-grid threshold 0.3 is stricter than lambda_hat at both alphas, so the final threshold does not change. Null controls: T15 0/300 and 1/300, T12 0/300 and 0/300 (allowed 30).

### Comparison with the earlier runs (same decoder output)
| | earlier | drop-in (this run) |
|---|---|---|
| T15 | M2-19 `tcfg-e7e8c472f6d9ab33` (harness, no commit gate): 9/701 commits, 6 wrong, 0.0086 [0.0031, 0.0185], eWPM 6.03; with the post hoc gate: 7 commits, 4 wrong | 2/701 commits, 2 wrong, 0.0029 [0.0003, 0.0103], eWPM 6.02 |
| T12 | M3-28 frozen recipe (fit-A / calibration by session, guard limit 0.1 from the grid): 1/400 commits, 0 wrong, eWPM 7.14 | 25/400 commits, 15 wrong, 0.0375 [0.0211, 0.0611], eWPM 7.13 |

The drop-in uses its own random split of the calibration set (not the earlier fit-A / calibration halves), and its commit gate is always on. So the configs differ. On T15 its sentence temperature is higher (11.96 vs 7.80), so fewer trials reach p_top1 0.3.

## API fix found by this validation
`calibrate` fitted the frame temperature on the word texts, also when the decoder outputs phonemes and the user brings a `decode_fn`. Check on 180 T15 trials: frame T 6.58 with word texts, 1.24 with phoneme texts (M2-19: 1.2385). Fixed before the runs (plan.md):
- new optional keyword `calibrate(..., stream_texts=...)`: the truth in the decoder's token space (a string of one-character tokens or a list of tokens); used only for the frame temperature;
- with `decode_fn` and no `stream_texts`, the frame temperature stays 1.0 and the sheet warns;
- `HarnessConfig.fit_frame_temperature` (default True, old results unchanged);
- test `test_stream_texts_fit_the_frame_temperature_in_the_token_space`.

## Our take
> **Our take:** The P14-03 check passes: on two public sets, used as an outside user would use it, the API kept the held-out wrong-commit rate under alpha 0.05, and both null controls passed without any change. One draw per set cannot prove a `1 - delta` statement.

> **Our take:** T12 is the more useful test. It is a by-session split (later sessions held out), so it includes day-to-day drift, which the exchangeability assumption does not cover. The held-out rate (0.0375) is higher than the in-sample LTT rate (4/180 = 0.022), and the CP95 upper bound (0.061) is above alpha. So the point estimate passes, but the data do not show the bound with 95 % confidence. A user with drift should recalibrate per session or use a smaller alpha.

> **Our take:** As in M2-19, the commits are of low quality: 2 of 2 wrong on T15 and 15 of 25 wrong on T12. The guarantee is on wrong commits over all utterances, not on precision. The eWPM gain from commits is near zero (the gain over gaze typing comes from offers). This is the open precision question (P5-02), not an API bug.

## Limitations
- One participant per set, one split, one test draw per set; the T12 test sessions were decoded once before (M3-28, aggregate numbers only).
- Both sets use our GRU-CTC decoders and the same B2T '25 word route as `decode_fn`. A second modality (EMG, n-best route) is not tested here.
- eWPM uses the public simulated user with one attempt; it follows the harness method but is a secondary number.
- The run used `dropin.py` with the `stream_texts` fix. The sheet improvements made after the run (gate-block count, plain-text reasons) change no decision.

## Deviations from the plan
None.

## Correction note 2026-11-17 (P14-18): T15 rows with edit penalty 8
Pre-registered rerun ([P14-18/19 results](../2026-11-17-p14-18-19-followups/results.md)) of the T15 rows with the word decoder tuned without the M4 `val_eval` trials (lm 1.0, **edit penalty 8**, bonus 3). The reference run (edit 12) reproduced 2 / 701 commits, 2 wrong, eWPM 6.016. With edit 8: **0 / 701 commits** at alpha 0.05 and 0.10 (wrong-commit 0.0029 → 0, half-width 0.0048), eWPM 6.016 → 6.013, sentence temperature 11.96 → 12.61. The error among commits (2 of 2) has no value with 0 commits; the script counts this as an effect. The pass verdict stays. The numbers above are not changed.
