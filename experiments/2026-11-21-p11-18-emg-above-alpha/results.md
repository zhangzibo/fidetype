---
title: P11-18 Why 22.5 % of the EMG calibration draws are above alpha - results
type: experiment
task: P11-18
updated: 2026-11-21
---

# P11-18: why 22.5 % of the EMG calibration draws are above alpha (results)

Pre-registration: [plan.md](plan.md), commit `6ce4245`. It was committed and pushed before any number was computed. Code and synthetic tests: `7537199` ([run.py](run.py), [launch.py](launch.py), [test_p11_18.py](test_p11_18.py)); launcher newline fix `b70aac7` (no change to run.py). Aggregates and per-draw counts (no text): [results/results.json](results/results.json). Log: [results/run.log](results/run.log). Per-prompt decisions (with text) are local only, in `C:\Users\zhang\bci-data\derived\p11-18\`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page holds pooled aggregates and per-draw counts only: no per-user value, no text, no id.

Run details:
- Time: 2026-11-21 07:39 to 08:40, detached, from a `git archive` snapshot of `b70aac7`.
- Resources: 4 workers x 1 thread, isolation class `background`, **CPU only**, no GPU. Arm P draws 172-210 s, arm E draws 103-127 s.
- Draws: z0 (code check), 40 arm P draws, 40 arm E draws. No draw was refused. No run error.

## Main numbers

| | draws above alpha on test (> 61 of 1,221 wrong) | significant exceedances (>= 75 wrong) |
|---|---|---|
| B: P11-17, bootstrap (with duplicates), val -> test | 9 / 40 (22.5 %) | 1 / 40 |
| **P: partition-only (no duplicates), val -> test** | **3 / 40 (7.5 %)** | 0 / 40 |
| E: partition-only, pooled exchangeable split (no session shift) | 0 / 40 (0 %) | 0 / 40 |

LTT allows at most delta = 10 %. Without duplicates (arm P), the fraction is 7.5 %, inside delta. All 3 arm P failures have exactly 62 wrong commits (rate 0.0508, the smallest count above alpha) and 311-319 commits.

### LTT in-sample risk vs test risk (per draw; rates per prompt)

| arm | test (held-out) rate, mean [min, max] | LTT in-sample rate, mean [min, max] | optimism gap = test - LTT, mean (SD) [min, max] | corr(LTT, test) |
|---|---|---|---|---|
| P (val -> test) | 0.0342 [0.0008, 0.0508] | 0.0216 [0.0022, 0.0349] | **+0.0126** (0.0084) [-0.0030, +0.0284] | 0.81 |
| E (pooled, no shift) | 0.0268 [0.0049, 0.0467] | 0.0284 [0.0044, 0.0349] | **-0.0016** (0.0096) [-0.0177, +0.0249] | 0.57 |

The LTT recount with the test rule equals the sheet's own `ltt_wrong_commits` in 40 / 40 draws of each arm.

## Decision rule (pre-registered)

| step | test | value | conclusion |
|---|---|---|---|
| 1: duplicates | one-sided Fisher, 9 / 40 > 3 / 40 | p = 0.057 | f_P = 3 <= 4 (delta), p >= 0.05: **partly duplicates** (inconclusive at K = 40) |
| 2: shift (primary) | one-sided Welch, gap P > gap E | p = 3.6e-10 | **shift present** |
| 2: shift (secondary) | one-sided Fisher, 3 / 40 > 0 / 40 | p = 0.12 | not significant |
| 2: sub-cause | shift present, x_E = 0 <= 4 | | **mainly session shift** |
| 3: noise | significant exceedances in P | 0 of 40 (limit 2) | **consistent with test-rate noise around alpha** |

**Pre-registered sentence: "The excess over delta comes from partly duplicates."** (By the plan, the step 2 sub-cause is appended only when step 1 says "noise + shift". Step 2 is reported anyway: it finds a clear session shift.)

> **Our take:** two causes act together. (1) Bootstrap duplicates made most of the excess: without them, 6 fewer draws fail (9 -> 3), and the remaining fraction (7.5 %) is inside delta. K = 40 is too small to make this drop significant (p = 0.057). (2) The val -> test session shift is real and systematic: in arm P the test rate is above the LTT in-sample rate in 35 / 40 draws (mean +1.26 points); in the exchangeable arm E it is above in 17 / 40 draws (mean -0.16 points). The shift pushes the best-committing guards to just above alpha (all 3 arm P failures sit at 62 / 1,221). With no shift (arm E), no draw fails. Each failing draw on its own is within test-rate noise of alpha (significant exceedances: 1 of 9 bootstrap failures, 0 of 3 partition-only failures). So the failures are near-alpha guards that the duplicates and the shift move across the line, not grossly unsafe guards.

## Calibration-inclusive interval, arm P (P11-17 procedure unchanged)

| interval | value [95 %] | lower end > 3.09? |
|---|---|---|
| P11-17 primary (bootstrap draws) | 5.00 [0.00, 9.55] | no |
| **P11-18 arm P primary** (partition-only draws x user-cluster bootstrap; non-credited draws earn 0.0) | **5.65 [0.00, 9.45]** | **no** |
| secondary: library `calibration_draw_interval` (prompt-level inner level) | 5.65 [0.00, 7.76] | no |
| variant V-a: above-alpha draws keep their value (descriptive) | 6.19 [2.62, 9.61] | no |
| variant V-b: credited draws only, K = 37 (descriptive) | 6.10 [2.56, 9.51] | no |

**Verdict vs no-BCI 3.09: "above, but inside the combined interval"** (mean 5.65 > 3.09 >= lower end 0.00). 3 of 40 draws earn 0.0 (7.5 % of the pooled values > 2.5 %), so the lower end is 0.00. Even with the zeros removed (V-a, V-b) the lower end (2.56-2.62) is below 3.09.

Other facts (arm P):
- Statuses: 37 `certified`, 3 `above-alpha`, 0 refused, 0 V6 failures. All null controls 0 in every draw (calibrate uniform / frame-shuffled / input-level 0 of 300; test time-shuffled and zero EMG 0 of 1,221).
- Draw values: median 6.54, range 0.00-7.40; 36 / 40 above 3.09. Low certified draws: 2.25 (66 commits, 1 wrong), 3.65, 3.67.
- Commits mean 248.8 (range 66-319); wrong mean 41.8 (1-62). Thresholds 0.30-0.86. The L model keeps 5-7 of 10 features.
- X1: between-draw SD 1.98 (with the zeros), within-draw SD 1.26, ratio 1.57; normal interval [1.04, 10.26]. P11-17: between 2.94, ratio 2.5.

Arm E (descriptive): 40 / 40 certified; held-out raw safe WPM mean 6.22 (range 3.33-7.77; a different held-out set per draw, so no interval); 582-637 of the 1,221 held-out prompts are val prompts.

## Cross-check

| check | result |
|---|---|
| **X4 code check (must pass)** | **passes.** z0 reproduces P11-14 L-FL exactly: model digest `c71fc7ed44fa`, threshold 0.63, 1,221 / 1,221 identical real, time-shuffled and zero-EMG decisions, 285 commits, 52 wrong, 6.8031, K = 1 interval [4.49, 9.63]. z0 LTT in-sample: 16 / 459 wrong. |

## Gap rule
**Gap 158 closes.** The done-when is met: a pre-registered run with K = 40 partition-only draws (fresh permutations of the 1,224 calibration prompts, same 306 / 459 / 459 sizes, no resampling) reports the above-alpha fraction (3 / 40), the calibration-inclusive interval vs 3.09 (5.65 [0.00, 9.45], "above, but inside the combined interval"), and the cause: the excess over delta comes mostly from bootstrap duplicates (pre-registered verdict "partly duplicates"; the drop 9 -> 3 is not significant at K = 40), with a clear systematic val -> test session shift (+1.26 points test over LTT in-sample; none without the shift) and no failure beyond test-rate noise around alpha.

Consequences (for the records agent):
- The P11-17 limit (b) is confirmed: bootstrap draws over-state the failure rate. A calibration-draw interval with partition-only draws gives 5.65 [0.00, 9.45]; the EMG claim stays "above on average, not reliably above no-BCI 3.09".
- The EMG guarantee is affected by the session shift: on a new session the wrong-commit rate is about 1.3 points above what the LTT part sees.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-18-emg-above-alpha/test_p11_18.py` |
| Full run (detached; about 1 h CPU, 4 workers x 1 thread) | `.venv\Scripts\python.exe experiments/2026-11-21-p11-18-emg-above-alpha/launch.py b70aac7` (needs the P11-14 derived files, the P11-17 `feat.pkl` memo or the P11-14 one, and the P11-09 / P11-11 / P11-12 inputs) |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-18\DONE` exists; stop the python processes whose command line has `p11-18-emg-above-alpha` |

## Limits
- Pinned decoder, gate, LM, lexicon and arm choice, tuned on val prompts; in arm E about half of the held-out prompts are val prompts (plan limit (a)).
- Arm E's guards differ from arm P's (mixed-session calibration); the optimism gap is used to compare them (limit (b)).
- Arm P draws share the same 1,224 prompts: their spread is split variation only (limit (c)).
- The LTT in-sample risk of the P11-17 bootstrap draws was not recorded (limit (d)).
- K = 40 per arm: the step 1 Fisher test has low power (limit (e)).
