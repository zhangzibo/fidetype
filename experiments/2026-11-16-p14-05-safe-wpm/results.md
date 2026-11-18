---
title: P14-05 safe WPM baselines - results
type: experiment
task: P14-05
updated: 2026-11-17
---

# P14-05: safe WPM at a certified wrong-commit rate (baselines)

Definition: [docs/safe-wpm.md](../../docs/safe-wpm.md) (`safe-wpm/0.1`). Code: [`fidetype.benchmark.safe_wpm`](../../src/fidetype/benchmark/safe_wpm.py), runner [run.py](run.py). Numbers: `results/safe-wpm.json` (aggregates only). Leaderboard column: [benchmark/site/leaderboard.md](../../benchmark/site/leaderboard.md). Per-trial files: `C:\Users\zhang\bci-data\derived\p14-05-safe-wpm\` only. CPU only. No GPU.

## Done-when check
| Criterion (roadmap P14-05) | Status |
|---|---|
| The scorer gives safe WPM for our baselines on >= 3 tracks | **met**: B2T '25 T15 copy task, SpanishBCBL MEG, Toronto sEMG (+ 2 replay sets: T15 M4-12, T12 v2). `fidetype benchmark score` adds a `safe_wpm` block to every new result |
| Entries whose measured wrong-commit rate is above alpha are marked | **met**: `b2t25-t15-copytask/ours/crc` (0.0625 > 0.05) shows `! ABOVE alpha` |
| The required shuffled and null controls are shown next to it | **met**: the board keeps the Controls column; each `safe_wpm` block carries the control status |

## Results (alpha 0.05; LTT delta 0.1)

| Track / set | Decoder + policy | Safe WPM [95 % CI] | Status | Test wrong-commit [CP95] | Commits (wrong) | No-penalty WPM | eWPM | No-BCI |
|---|---|---|---|---|---|---|---|---|
| B2T '25 T15 copy | published sentence + CRC (n_cal 812) | 13.42 [11.72, 15.08] | certified | 0.049 [0.035, 0.066] | 405 (40) | 14.90 | 18.80 | 4.08 |
| B2T '25 T15 copy | published sentence + LTT (n_cal 812) | 12.24 [10.98, 13.45] | certified | 0.040 [0.028, 0.056] | 364 (33) | 13.34 | 18.73 | 4.08 |
| B2T '25 T15 copy | ours + CRC (n_cal 812) | 4.90 [4.10, 5.62] | **above alpha** | 0.062 [0.047, 0.081] | 199 (51) | 5.61 | 11.55 | 4.08 |
| B2T '25 T15 copy | ours + LTT (n_cal 812) | 4.05 [3.22, 4.77] | certified | 0.047 [0.033, 0.063] | 159 (38) | 4.48 | 11.51 | 4.08 |
| SpanishBCBL MEG | ConvCTC-M + CRC (n_cal 437) | 0.03 [0.00, 0.17] | certified | 0.020 [0.011, 0.035] | 14 (13) | 0.03 | 3.20 | 3.15 |
| SpanishBCBL MEG | ConvCTC-M + LTT (n_cal 437) | 0.03 [0.00, 0.17] | certified | 0.022 [0.012, 0.037] | 15 (14) | 0.03 | 3.20 | 3.15 |
| Toronto sEMG | CNN session-calibrated + CRC (n_cal 142) | 0.58 | certified | 0.004 [0.000, 0.013] | 21 (2) | 0.58 | 7.98 | 4.27 |
| Toronto sEMG | CNN cross-session + CRC | 0.27 | certified | 0.004 [0.000, 0.013] | 10 (2) | 0.27 | 4.68 | 4.27 |
| Toronto sEMG | CNN cross-subject + CRC | 0.00 | vacuous | 0.000 | 0 | 0.00 | 4.08 | 4.27 |
| T15 val_eval (701) | M4-12 + P14-03 drop-in guard (LTT, n_cal 271) | 0.00 | certified | 0.0029 [0.0003, 0.0103] | 2 (2) | 0.00 | 6.02 | 4.02 |
| T12 v2 test sessions (400) | T12 v2 + P14-03 drop-in guard (LTT, n_cal 180) | 1.27 | certified | 0.0375 [0.0211, 0.0611] | 25 (15) | 1.48 | 7.13 | 4.11 |
| T15 val_eval (701) | M4-13 + drop-in guard (same recipe, LTT, n_cal 271; added 2026-11-17) | 2.23 | certified | 0.0243 [0.0142, 0.0385] | 104 (17) | 2.31 | not computed | 4.02 |

Policies without a certified bound (always commit, plug-in trust fit) get "n/a (no certified bound)" on the board. Their `unguarded_wpm` is in the result JSON for reference (B2T published + plug-in: 12.92).

## M4-13 row (2026-11-17)
Stage `t15-m4-13` (CPU, background class, 4 threads, 320 s; guard `tcfg-1016759f08a3f9a1`, file `results/guard-t15-m4-13.json`). M4-13 = the long-trained T15 decoder ([results](../2026-11-15-m4-13-long-train/results.md); greedy PER 0.1210). The guard commits 104 of 701 trials; 17 commits are wrong (wrong-commit 0.0243, CP95 upper 0.0385 < alpha 0.05), so the value is certified. Of 4,675 words, 504 are committed and right. 218.3 min neural time + 8.2 min corrections give **2.23 safe WPM**. This is below the no-BCI reference (4.02). Controls: shuffled 0/300, uniform 0/300 commits (pass). The eWPM of this drop-in config is not computed here; the M4-13 results page gives eWPM 9.94 for a different config (M2-19 + commit gate, 91 commits).

> **Our take:** M4-13 moves the T15 drop-in row from 0.00 (M4-12, 2 of 2 commits wrong) to 2.23, with 87 of 104 commits right. It is still about half of gaze typing. The error among commits (0.163) is the limit: each wrong commit costs about 5 s of correction, and only 15 % of trials commit.

## Timing per set
| Set | Neural time | Source |
|---|---|---|
| B2T '25 T15 copy track | measured `speech_duration_s` per trial | `t15_copyTask.pkl` (CC0), read only |
| T15 val_eval, T12 test | measured trial window: 20 ms bins of each trial (T15 mean 18.7 s, T12 mean 5.5 s) | per-session npz files in `derived/m4-01-02-lookahead/` and `derived/2026-11-13-confirmatory-t12-v2/`, read only |
| SpanishBCBL MEG | rate model 152 chars/min (track user model) | no per-trial times in the committed items |
| Toronto sEMG | rate model 75.76 chars/min (one key per 0.792 s) | composed sentences; aggregate approximation (no per-trial data committed) |

## Check of the compute path
Stage `t15-m4-12-recompute` runs the M4-13 code path (calibrate on val_select, decide val_eval) on M4-12 (CPU, background class, 4 threads, 433 s). Its 701 decisions equal the P14-03 decisions: same action, same text and same p_top1 for all 701 trials, so the same safe WPM (0.00, 2 of 2 commits wrong). The config id differs (`tcfg-fcd45cf2cc381ca7` vs `tcfg-09baa8a632ade86e`) only because the guard name is part of the id. So `t15-m4-13` uses the validated P14-03 recipe.

## Rerun (repo root)
```bash
# leaderboard tracks + the two P14-03 replay sets (seconds)
.venv\Scripts\python.exe -I experiments/2026-11-16-p14-05-safe-wpm/run.py tracks t15-m4-12 t12
# M4-13, after runs\m4-13-queue.DONE and the trust-reruns CPU decode of val_select exist (about 6 min CPU)
.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-16-p14-05-safe-wpm/run.py t15-m4-13
```
`tracks` changes only the `safe_wpm` key of each `benchmark/results/v0.1/*.json` and rebuilds `benchmark/site/`. It needs the local truth files (`C:\Users\zhang\bci-data\benchmark\*-truth.jsonl`) and `t15_copyTask.pkl`.

## Our take
> **Our take:** Only the published Card et al. 2024 decoder gives a safe WPM well above gaze typing (12.2-13.4 vs 4.1). Our decoders are at or below the no-BCI level. Their eWPM gain comes from offers that the user must check.

> **Our take:** The metric does what it should. It gives 0 when a guard commits only wrong text (T15 M4-12: 2 of 2), and it marks the one entry whose test rate broke alpha (B2T ours + CRC, cal / test drift within a day).

## Limitations
- One participant per B2T set; the replay sets have no CI.
- Toronto values are an aggregate approximation (committed-right words = `share_words_system` x test words; penalty at the mean sentence length).
- The T15 / T12 trial windows include time outside speech, so those values are conservative.
- No reading time for committed text. The correction penalty uses the `aac-gaze-v1` constants; other user models give other values.
- The M4-13 row has no eWPM (the stage does not compute it).
- Not computed: emg2qwerty LDA demo (3 of 3 commits wrong, so 0; no per-trial timing export), KT-sEMG and Willett T12 handwriting (no trust-guarded decoder outputs yet), P11-01 EMG decoder (training).

## Note 2026-11-18: P14-21 rerun with word-decoder edit penalty 8

P14-21 ([results](../2026-11-17-p14-21-edit8-rows/results.md)) reran the T15 rows with the B2T '25 word decoder at lm 1.0 / edit 8 / bonus 3 (tuned without `val_eval`; P14-15, P14-18), guard recalibrated on `val_select`. The edit-12 reference reproduced both blocks exactly. **No effect.** M4-13: safe WPM 2.23 -> **2.28** certified (104 -> 99 commits, 17 -> 15 wrong; half-width 0.46), still below no-BCI 4.02 (gap 53). M4-12: 2 -> 0 commits, value 0 -> 0 (vacuous). The numbers above stay as committed.
