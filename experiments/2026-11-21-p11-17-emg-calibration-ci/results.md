---
title: P11-17 Calibration-inclusive safe WPM interval for the EMG P11-14 L-FL guard - results
type: experiment
task: P11-17
updated: 2026-11-21
---

# P11-17: a safe-WPM interval for the EMG L-FL guard that includes the calibration draw (results)

Pre-registration: [plan.md](plan.md), commit `7922ecf`. It was committed and pushed before any number was computed. Code and synthetic tests: `eecbac8` ([run.py](run.py), [launch.py](launch.py), [test_p11_17.py](test_p11_17.py)). Aggregates and per-draw counts (no text): [results/results.json](results/results.json). Log: [results/run.log](results/run.log). Per-prompt decisions (with text) are local only, in `C:\Users\zhang\bci-data\derived\p11-17\`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page holds pooled aggregates and per-draw counts only: no per-user value, no text, no id.

Run details:
- Time: 2026-11-21 03:07 to 05:36, detached, from a `git archive` snapshot of `eecbac8`.
- Resources: one worker, isolation class `background`, 2 threads, **CPU only**, no GPU. Each draw took 190-247 s.
- Draws: z0 (code check) and all K = 40 pre-registered draws. No draw was refused. No run error.

## Verdict (pre-registered rule)

| | safe WPM v0.1 [95 % interval] | no-BCI | verdict |
|---|---|---|---|
| P11-14 (one calibration, user-cluster CI) | 6.80 [4.49, 9.63] | 3.09 | clearly above |
| **P11-17 primary (K = 40 calibration draws x user-cluster bootstrap)** | **5.00 [0.00, 9.55]** | 3.09 | **above, but inside the combined interval** |

**The EMG claim does not survive the calibration draw.** The mean (5.00) is above 3.09. The lower end (0.00) is not. So the public EMG wording must change from "clearly above the no-BCI reference" to "above on average, not reliably above once the calibration draw is counted" (plan, decision rule).

## Why the lower end is 0.00: 9 of 40 draws are unsafe on the test session
- **9 of 40 draws (22.5 %) are `above-alpha`**: their wrong-commit rate on the 1,221 test prompts is above alpha 0.05 (62-76 wrong commits, rate 0.051-0.062). By the credit rule each earns 0.0. So 22.5 % of the pooled values are 0.0.
- These are the draws that commit the most (301-339 commits) and have the highest raw values (6.78-7.51).
- The other 31 draws are `certified` and safe. Their values: mean 6.46, median 6.85, range 1.14-7.27.
- Two certified draws are low: k35 3.38 (104 commits, 5 wrong) and k40 1.14 (33 commits, 0 wrong; threshold 0.95). Both are conservative guards.
- Every null control passed in every draw: calibrate uniform / frame-shuffled / input-level 0 of 300; test time-shuffled and zero EMG 0 of 1,221. So no draw failed V6.

LTT allows the population wrong-commit rate to exceed alpha in at most delta = 10 % of calibration draws. We observed 22.5 % above alpha on the test session. This is more than twice delta.

> **Our take:** three causes can add up here. They are not separated by this run. (1) **Sampling noise of the test rate:** with 1,221 prompts the rate has an SD of about 0.006 near 0.05, and most failing draws are just above the limit (0.051-0.055). A guard whose true rate is 0.048 fails on the test set fairly often. (2) **Bootstrap duplicates** in the resampled LTT part (plan limit (b)): the LTT test sees 459 entries with only about 290 distinct prompts, so its p-values are too optimistic, and the resampled draws can commit too much. (3) **Session shift:** the guarantee assumes exchangeable val and test sessions; P11-14 already showed an empirical rate (0.043) close to alpha. On T15 (P15-29) only 2 / 40 draws failed; there the LTT part also had duplicates, so (2) alone does not explain the larger EMG rate. A partition-only rerun (no resampling) would separate (2) from (1) + (3).

## Secondary and exploratory intervals

| interval | value [95 %] | lower end > 3.09? |
|---|---|---|
| **primary** (user-cluster inner level; non-credited draws earn 0.0) | 5.00 [0.00, 9.55] | no |
| secondary: library `calibration_draw_interval` (prompt-level inner level) | 5.00 [0.00, 7.84] | no |
| variant V-a: above-alpha draws keep their value (descriptive) | 6.63 [1.87, 9.88] | no |
| variant V-b: credited draws only, K = 31 (descriptive) | 6.46 [1.42, 9.74] | no |

The verdict does not depend on the credit rule. In every variant the lower end is at most 1.87. The low certified draws (k35, k40) and the user-cluster spread pull it down even without the zero draws.

## Cross-checks

| check | result |
|---|---|
| **X4 code check (must pass)** | **passes.** z0 reproduces P11-14 L-FL exactly: the same L model (digest `c71fc7ed44fa`), threshold 0.63, the same action and text on 1,221 / 1,221 real, time-shuffled and zero-EMG prompts, 285 commits, 52 wrong, 6.8031; the primary interval with K = 1 is [4.49, 9.63]. |
| **X1 variance decomposition** (primary) | between-draw SD 2.94 (with the 9 zeros), within-draw SD 1.19, ratio 2.5; normal interval [-1.22, 11.22]. Without the zeros (V-b): between 1.25, within 1.35, ratio 0.93. So the calibration draw adds a spread as large as the 8-user spread, and the unsafe draws add much more. |
| fraction of draws above 3.09 | 30 / 40 (75 %); among credited draws 30 / 31 |

## Draw summary
- Statuses: 31 `certified`, 9 `above-alpha`, 0 refused, 0 vacuous, 0 V6 failures.
- Mean commits 278.1, mean wrong commits 51.0 (all 40 draws). Commit thresholds 0.30-0.95 (`p_top1`; the two-item n-best commits only at c > 0.5 in all cases).
- The refitted L model keeps 5-8 of the 10 features (P11-14: 6).
- Distinct prompts per resampled part: 179-203 of 306 (fit), 277-301 of 459 (policy), 275-301 of 459 (LTT).
- Per-draw values, commits, wrong commits, thresholds and control counts: `results/results.json`, key `draws`.

## Gap rule
**Gap 133 closes.** The done-when is met: a pre-registered run applies `calibration_draw_interval` (P15-29 procedure) to the P11-14 L-FL guard with the same split, gate, LTT and controls, K = 40 stated in advance, and reports the calibration-inclusive interval against 3.09. X4 passed. The verdict is "above, but inside the combined interval" (not a pass of the "clearly above" claim).

Consequences:
- Public EMG pages that call the P11-14 result "clearly above" no-BCI must add the calibration-inclusive interval 5.00 [0.00, 9.55] (as was done for T15 after P15-29).
- The declared-subset card `benchmark/results/v0.2/emg2qwerty__p11-14-intended-lfl-subset8__guard.json` stays valid under the adopted `safe-wpm/0.1` (one calibration, conditional CI). The interval of this page is the proposed reporting addition of docs/safe-wpm.md section 6b; this item changes no card.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-17-emg-calibration-ci/test_p11_17.py` |
| Full run (detached; about 2.5 h CPU) | `.venv\Scripts\python.exe experiments/2026-11-21-p11-17-emg-calibration-ci/launch.py eecbac8` (needs the P11-14 derived files `feat.pkl`, `model-L-FL.json`, `decisions-L-FL.json`, and the P11-09 / P11-11 / P11-12 inputs) |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-17\DONE` exists; stop the python processes whose command line has `p11-17-emg-calibration-ci` |

## Limits
- Pinned decoder weights, gate, LM, lexicon and arm choice (plan limit (a)).
- Bootstrap duplicates in each resampled part (limit (b)): a single draw's certificate is not valid; the draws show the sampling variation and may over-state the failure rate.
- The outer level resamples prompts, not users (limit (c)).
- The same evaluation set in every draw (limit (d)); 8 users, one session each (limit (e)).
