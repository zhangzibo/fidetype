---
title: P11-20 Shift-robust calibration for the EMG L-FL guard - results
type: experiment
task: P11-20
updated: 2026-11-21
---

# P11-20: shift-robust calibration for the EMG L-FL guard (results)

Pre-registration: [plan.md](plan.md), commit `20b5993`. It was committed and pushed before any number was computed. Code and synthetic tests: `d3511df` ([run.py](run.py), [launch.py](launch.py), [test_p11_20.py](test_p11_20.py)). Aggregates and per-draw counts (no text): [results/results.json](results/results.json). Log: [results/run.log](results/run.log). Log-probs and per-prompt decisions are local only, in `C:\Users\zhang\bci-data\derived\p11-20\`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page holds pooled aggregates and per-draw counts only: no per-user value, no text, no id.

Run details:
- Time: 2026-11-21 09:14 to 11:42, detached, from a `git archive` snapshot of `d3511df`.
- Resources: **CPU only**, no GPU. Inference: 1 process x 4 threads (2,506 s for 16 sessions). Draws: 4 workers x 1 thread, isolation class `background`.
- Draws: R01 (code check), M01-M40, P41-P80, S01-S40. No draw was refused. No run error.

## Checks (all must pass)

| check | result |
|---|---|
| C1: prompt builder reproduces the P11-09 rows of the 16 track sessions | **passes** (2,445 / 2,445 rows identical) |
| C2: inference reproduces the P11-09 track-val log-probs of u0 | **passes** (81,202 frames; max probability difference 0.0; argmax agreement 1.0) |
| X5: R01 reproduces P11-18 draw P01 | **passes** (threshold 0.60, 310 commits, 56 wrong, 1,221 / 1,221 identical real, time-shuffled and zero-EMG decisions) |

Sessions a and b (the two P11-01 personal-val sessions, before track val): 1,221 prompts each.

## Stage 1: the margin (sessions a -> b only; no track-val or track-test data)

| quantity (40 draws, 40 guards) | mean | SD | range |
|---|---|---|---|
| LTT in-sample rate on session a (458 LTT prompts) | 0.0297 | 0.0081 | 0.0044-0.0349 |
| rate on session b (1,221 prompts) | 0.0342 | 0.0121 | 0.0016-0.0549 |
| **one-step gap g = b rate - LTT rate** | **+0.0045** | 0.0085 | -0.0112 to +0.0229 |
| descriptive: rate on track val | 0.0253 | 0.0084 | 0.0033-0.0433 |
| descriptive: two-step gap (track val - LTT rate) | -0.0044 | 0.0066 | -0.0145 to +0.0130 |

**m = 0.0045, alpha' = 0.0455** (margin rule: m = max(0, mean g); alpha' = floor((0.05 - m) x 10^4) / 10^4). All null controls 0 commits. The LTT recount equals the sheet count in 40 / 40 draws.

## Arm S (primary): track val -> track test, LTT at alpha' = 0.0455, 40 partition-only draws

| | above alpha = 0.05 on test (>= 62 of 1,221 wrong) | significant exceedances (>= 75 wrong) | test rate mean [min, max] |
|---|---|---|---|
| P11-18 arm P (LTT at 0.05; same 40 partitions) | 3 / 40 (7.5 %) | 0 / 40 | 0.0342 [0.0008, 0.0508] |
| **arm S (LTT at 0.0455)** | **0 / 40 (0 %)** | 0 / 40 | 0.0331 [0.0008, 0.0483] |

- Descriptive: 3 / 40 arm S draws are above alpha' = 0.0455 on test, and 0 are above the claim 0.05.
- Paired with P11-18 P01-P40 (same partition, same L model): the wrong count goes down in 9 draws, stays the same in 31 draws (the threshold does not change), and goes up in 0 draws. Exact McNemar on above-alpha: 0 vs 3 discordant pairs, p = 0.25.
- Optimism gap (test - LTT in-sample rate): mean +0.0126 (SD 0.0085), as in P11-18. The margin does not remove the shift. It only moves the guard far enough below alpha.
- Statuses: 40 / 40 `certified` (against the claim alpha 0.05), 0 V6 failures, all controls 0. Commits mean 245.0 (66-310); wrong mean 40.5 (1-59). Thresholds 0.30-0.89.

**Pre-registered conclusion: "margin removes the excess"** (f_S = 0 <= 1). **Assumption check: "(A) not contradicted on test"** (mean test rate 0.0331 <= 0.05; f_S = 0 <= 4).

### Calibration-inclusive interval, arm S (P11-17 procedure unchanged)

| interval | value [95 %] | lower end > 3.09? |
|---|---|---|
| P11-18 arm P primary (LTT at 0.05) | 5.65 [0.00, 9.45] | no |
| **arm S primary** (40 draws x user-cluster bootstrap; non-credited draws earn 0.0) | **6.13 [2.62, 9.47]** | **no** |
| secondary: library `calibration_draw_interval` | 6.13 [2.85, 7.76] | no |
| variants V-a, V-b (no draw is non-credited, so both equal the primary) | 6.13 [2.62, 9.47] | no |

**Verdict vs no-BCI 3.09: "above, but inside the combined interval"** (mean 6.13 > 3.09 >= lower end 2.62).
- No draw earns 0.0 now (zero fraction 0.0; P11-18: 7.5 %). The lower end rises from 0.00 to 2.62.
- Draw values: median 6.56, range 2.25-7.25; 39 / 40 above 3.09. The one low draw (S13: 66 commits, 1 wrong, 2.25) is the same low draw as in P11-18.
- X1: between-draw SD 1.14, within-draw SD 1.31 (ratio 0.87); normal interval [2.73, 9.54]. The within-draw (user-cluster) spread now limits the lower end more than the calibration draw does.

## Secondary: K = 80 partition-only draws at alpha = 0.05 (P11-18 P01-P40 + new P41-P80)

| | above alpha | wrong counts of the above-alpha draws |
|---|---|---|
| P01-P40 (P11-18) | 3 / 40 | 62, 62, 62 |
| P41-P80 (new) | 5 / 40 | 62, 62, 65, 67, 62 |
| **K = 80** | **8 / 80 (10.0 %)** | 0 significant exceedances |

- One-sided Fisher, 9 / 40 (P11-17 bootstrap) > 8 / 80: **p = 0.060**. **Conclusion: "partly duplicates", still inconclusive at K = 80** (pre-registered rule: x_80 = 8 = delta x 80).
- Why not firm: the partition-only fraction sits exactly at delta (10 %), and the bootstrap side stays at 40 draws. At the same 10 % rate, the Fisher p falls only slowly with more partition-only draws: K = 120: 0.044; K = 160: 0.036; K = 400: 0.023 (bootstrap fixed at 9 / 40). With 80 bootstrap draws at the P11-17 rate (18 / 80) against 8 / 80, p would be 0.026. So the fixed 40-draw bootstrap side limits the power more than the partition-only side.
- K = 80 interval (descriptive): 5.66 [0.00, 9.58] ("above, but inside"); optimism gap mean +0.0131 (SD 0.0077); between-draw SD 2.18, within 1.27.

> **Our take:** a margin estimated on two earlier sessions (a -> b, +0.45 points) is enough to remove the above-alpha draws on track test (3 / 40 -> 0 / 40), at a small cost (mean commits 249 -> 245; mean draw value 5.65 -> 6.13 because no draw earns 0 now). The margin is smaller than the val -> test optimism gap (+1.26 points). It works because most draws were already well below alpha: only the near-alpha draws needed to move. So the claim "P(test risk > 0.05) <= 0.1 under assumption (A)" holds on this test set, but this is one check of (A), not a proof. The descriptive two-step gap a -> track val is negative (-0.44 points): track val is an easier session than b for these guards. So the session shift is not a steady drift in one direction; it changes from session to session. A margin from one session step is therefore a rough estimate. The calibration-inclusive lower end (2.62) is still below 3.09: the remaining limit is the user-cluster spread and one low-commit draw, not above-alpha draws.

## Gap rule
**Gap 164 closes.** The done-when is met: a pre-registered run (plan `20b5993`, checks C1, C2 and X5 passed) tests a shift-robust calibration (LTT at alpha' = 0.05 - m, m = 0.0045 from sessions a -> b, which the track does not use) and reports the above-alpha fraction on test with 40 partition-only draws (0 / 40) and the calibration-inclusive interval vs 3.09 (6.13 [2.62, 9.47], "above, but inside the combined interval"). Secondary: K = 80 partition-only draws give 8 / 80; the "partly duplicates" verdict is **not** firm (Fisher p = 0.060); the numbers above say why (fraction exactly at delta; the 40-draw bootstrap side limits the power).

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-20-emg-shift-robust/test_p11_20.py` |
| Full run (detached; about 2.5 h CPU: inference 42 min at 4 threads, draws 4 workers x 1 thread) | `.venv\Scripts\python.exe experiments/2026-11-21-p11-20-emg-shift-robust/launch.py d3511df` (needs the torch venv `C:\venvs\fidetype-rocm`, the P11-01 feature cache, labels and personal weights, the raw emg2qwerty HDF5 files, the P11-09 / P11-11 / P11-14 inputs and the P11-18 derived draws and memos) |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-20\DONE` exists; stop the python processes whose command line has `p11-20-emg-shift-robust` |

## Limits
- (a) Assumption (A) is not testable on calibration data alone. Sessions a and b were the checkpoint-selection sessions of the personal models. The two-step gap a -> track val was negative, so the step size changes between sessions.
- (b) One shift instance per user; m averages split variation only.
- (c) Pinned decoder, gate, LM, lexicon and arm choice were tuned on track-val prompts.
- (d) Arm S draws share the same 1,224 prompts: their spread is split variation only.
- (e) The K = 80 Fisher test keeps the P11-17 bootstrap count at 9 / 40.
- (f) One test set. f_S = 0 / 40 vs 3 / 40 is not a significant paired difference (McNemar p = 0.25).
