---
title: P11-23 Robustness of the EMG shift margin across session steps - results
type: experiment
task: P11-23
updated: 2026-11-21
---

# P11-23: robustness of the EMG shift margin across session steps (results)

Pre-registration: [plan.md](plan.md), commit `a03b20c`, committed and pushed before any number was computed. Code and synthetic tests: `75e9689` ([run.py](run.py), [launch.py](launch.py), [test_p11_23.py](test_p11_23.py)). Aggregates, per-draw pooled counts and unlabelled spread statistics (no text): [results/results.json](results/results.json). Log: [results/run.log](results/run.log). Per-user and per-prompt files are local only, in `C:\Users\zhang\bci-data\derived\p11-23\`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page holds pooled aggregates and per-draw counts only: no per-user value, no text, no id. Per-user step sizes are given only as unlabelled spread statistics.

Run details:
- Time: 2026-11-21 12:22 to 14:58, detached, from a `git archive` snapshot of `75e9689`.
- Resources: **CPU only**, no GPU, no new inference. 2 workers x 1 thread, isolation class `background`. The session a / b log-probs and prompt rows of P11-20 were read only.
- Draws: A01-A40 (a -> b), B01-B40 (b -> a), S01-S40 (arm S2). No draw was refused. No run error.

## Sessions and how training sessions were handled
All train sessions of the 8 users (6 to 14 per user, 67 in total) were used to fine-tune the personal models. So no unused train session exists. A step that uses a train session compares an in-sample risk with a different risk, and the size of that bias is not known. So, as pre-registered, train sessions are excluded. The available steps without train and track data are a -> b and b -> a (sessions a and b selected the checkpoints, but they were never trained on).

## Check X6 (must pass)

| check | result |
|---|---|
| X6: A01-A40 reproduce P11-20 M01-M40 (status, threshold, LTT wrong, commits, wrong on b) | **passes** (40 / 40 identical) |

## Stage 1: step sizes (sessions a and b only; no track-val or track-test data)

| quantity | a -> b (A, 40 guards) | b -> a (B, 40 guards) |
|---|---|---|
| step size s_d (mean pooled gap) | **+0.0045** | **-0.0018** |
| jackknife SE_d over users | 0.0074 | 0.0066 |
| **U_d = s_d + 1.8946 x SE_d** | **0.0185** | 0.0108 |
| per-draw gap: SD; q10 / median / q90; range | 0.0085; -0.0047 / +0.0041 / +0.0150; -0.0112 to +0.0229 | 0.0072; -0.0095 / -0.0033 / +0.0069; -0.0145 to +0.0161 |
| leave-one-user-out step sizes (8): SD; range | 0.0030; -0.0019 to +0.0078 | 0.0027; -0.0045 to +0.0044 |
| per-user step sizes (8, unlabelled): SD; median; range | 0.0211; -0.0028; -0.0182 to +0.0504 | 0.0192; +0.0034; -0.0460 to +0.0176 |
| LTT in-sample rate (mean) | 0.0297 | 0.0267 |
| evaluation-session rate (mean) | 0.0342 | 0.0250 |
| evaluation commits (mean, range) | 266.8 (59-337) | 245.7 (177-294) |
| null-control commits (max) | 0 | 0 |
| LTT recount = sheet count | 40 / 40 | 40 / 40 |

- Both directions pooled (80 draws): mean gap +0.0014, SD 0.0084, q90 +0.0132.
- Max of the 18 step estimates (2 direction means + 16 leave-one-user-out means; descriptive): 0.0078.
- s(a -> b) - s(b -> a) = 0.0063.
- Descriptive only (B draws): two-step gap b -> track val -0.0080 (SD 0.0081); track-val rate 0.0188.

**Margin (pre-registered rule): m2 = max(0, max_d U_d) = 0.0185 (from direction a -> b). alpha'' = 0.0314.** P11-20 used m = 0.0045, alpha' = 0.0455.

**Spread verdict: "the one-step margin of P11-20 under-states the spread"** (alpha'' = 0.0314 < 0.0455).

## Arm S2 (primary): track val -> track test, LTT at alpha'' = 0.0314, 40 partition-only draws

| | above alpha = 0.05 on test (>= 62 of 1,221 wrong) | significant exceedances (>= 75 wrong) | test rate mean [min, max] | commits mean (range) |
|---|---|---|---|---|
| P11-18 arm P (LTT at 0.05) | 3 / 40 | 0 / 40 | 0.0342 [0.0008, 0.0508] | 249 |
| P11-20 arm S (LTT at 0.0455) | 0 / 40 | 0 / 40 | 0.0331 [0.0008, 0.0483] | 245.0 (66-310) |
| **arm S2 (LTT at 0.0314)** | **0 / 40** | 0 / 40 | **0.0238 [0.0008, 0.0434]** | **205.5 (66-293)** |

- Descriptive: 9 / 40 arm S2 draws are above alpha'' = 0.0314 on test; 0 are above the claim 0.05.
- Paired with P11-20 arm S (same partitions): the wrong count goes down in 25 draws, stays in 15, goes up in 0. McNemar on above-alpha: 0 vs 0 discordant pairs, p = 1.0. Paired with P11-18 arm P: down 25, same 15, up 0; McNemar 0 vs 3, p = 0.25.
- Optimism gap (test - LTT in-sample rate): mean +0.0087 (SD 0.0088). LTT in-sample rate mean 0.0151.
- Statuses: 40 / 40 `certified`, 0 V6 failures, all controls 0. Wrong mean 29.1 (1-53). Thresholds 0.30-0.95.

**Pre-registered conclusion: "margin removes the excess"** (f_S2 = 0 <= 1). **Assumption check: "(A2) not contradicted on test"** (mean test rate 0.0238 <= 0.05; f_S2 = 0 <= 4).

### Calibration-inclusive interval, arm S2 (P11-17 procedure unchanged)

| interval | value [95 %] | lower end > 3.09? |
|---|---|---|
| P11-18 arm P primary (LTT at 0.05) | 5.65 [0.00, 9.45] | no |
| P11-20 arm S primary (LTT at 0.0455) | 6.13 [2.62, 9.47] | no |
| **arm S2 primary** (40 draws x user-cluster bootstrap) | **5.47 [2.44, 8.77]** | **no** |
| secondary: library `calibration_draw_interval` | 5.47 [2.79, 7.31] | no |

**Verdict vs no-BCI 3.09: "above, but inside the combined interval"** (mean 5.47 > 3.09 >= lower end 2.44).
- No draw earns 0.0. Draw values: median 5.70, range 2.25-7.03; 39 / 40 above 3.09. The one low draw (S13: 66 commits, 1 wrong, 2.25) is the same as in P11-18 and P11-20.
- X1: between-draw SD 1.07, within-draw SD 1.23 (ratio 0.87); normal interval [2.27, 8.66].

## Comparison with the pre-registered rules

| rule (plan) | outcome |
|---|---|
| X6 must pass | passes (40 / 40) |
| >= 30 guards per direction, m2 < 0.05 | 40 and 40 guards; m2 = 0.0185, arm S2 run |
| spread verdict (alpha'' >= 0.0455?) | no: "under-states the spread" |
| primary table (f_S2) | 0 / 40: "margin removes the excess" |
| assumption check (A2) | "not contradicted on test" |
| interval verdict vs 3.09 | "above, but inside the combined interval" |
| expectation (not a rule): s(b -> a) < 0, m2 > 0.0045 | both true |

> **Our take:** the one-step margin of P11-20 (+0.45 points) was a point estimate. With the user-composition spread (jackknife over users) and the second direction, the upper bound of a one-session step is +1.85 points, about 4 times larger. The backward step b -> a is negative (-0.18 points): session b is harder than session a for these guards, so the shift is not a steady drift. The per-user step sizes spread widely (SD about 2 points; one user +5 points), but the pooled guard averages them. The safer margin keeps 0 / 40 draws above alpha on test, as P11-20 did. The cost: commits fall from 245 to 206 (mean), and the safe WPM mean falls from 6.13 to 5.47. The interval verdict does not change, and its lower end (2.44) stays below 3.09. So the EMG public wording does not change. The test result cannot separate the two margins: P11-20 arm S already had 0 / 40 above alpha. The value of P11-23 is that the margin now has a pre-registered upper-bound rule rather than a single mean.

## Gap rule
**Gap 170 closes.** The done-when is met under the plan (`a03b20c`, X6 passed): the step sizes of both directions and their spread (direction, leave-one-user-out, per-user, per-draw) are reported; m2 = 0.0185 and alpha'' = 0.0314 come from a rule that covers the spread (upper 95 % bound over users, worse direction); arm S2 gives 0 / 40 above alpha on test with K = 40 partition-only draws; the calibration-inclusive interval is 5.47 [2.44, 8.77] vs 3.09, "above, but inside the combined interval".

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-23-shift-margin-steps/test_p11_23.py` |
| Full run (detached; about 2.6 h CPU with 2 workers x 1 thread) | `.venv\Scripts\python.exe experiments/2026-11-21-p11-23-shift-margin-steps/launch.py 75e9689` (needs the P11-20 derived log-probs, prompt rows, memos and draws, the P11-18 draws, and the P11-09 / P11-11 / P11-14 inputs) |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-23\DONE` exists; stop the python processes whose command line has `p11-23-shift-margin-steps` |

## Limits
- (a) Only two step directions exist without train or track sessions, both between the same two sessions. The backward step is not a real time step.
- (b) Sessions a and b selected the personal and generic checkpoints, so the decoder is slightly in-sample on both.
- (c) The leave-one-user-out values keep the guard fixed (calibrated on all 8 users). They measure user-composition spread, not a held-out user.
- (d) (A2) is an assumption; one test set checks it. Track test is further from b than b is from a. The descriptive two-step gaps (a -> track val -0.0044, b -> track val -0.0080) are negative, so on these data track val is an easier session.
- (e) Pinned decoder, gate, LM, lexicon and arm choice were tuned on track-val prompts.
- (f) Arm S2 draws share the same 1,224 prompts: their spread is split variation only.
- (g) Arm S2 vs P11-20 arm S is not a test of which margin is better (0 vs 0 above alpha).
