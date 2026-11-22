---
title: P11-21 Calibration-inclusive lower end above 3.09 for the EMG LX-FL prefix guard - results
type: experiment
task: P11-21
updated: 2026-11-21
---

# P11-21: calibration-inclusive lower end above 3.09 for the EMG LX-FL prefix guard (results)

Pre-registration: [plan.md](plan.md), commit `95b1a91`, committed and pushed before any number was computed. Amendment 1 (check X2 -> X2'): commit `99b7eb6`, before any margin, alpha_LX or arm number existed. Code and synthetic tests: `beac437`, `99b7eb6`, `fef0abb` ([run.py](run.py), [launch.py](launch.py), [x2_fresh.py](x2_fresh.py), [test_p11_21.py](test_p11_21.py)). Aggregates, per-draw pooled counts and unlabelled spread statistics: [results/results.json](results/results.json). Log: [results/run.log](results/run.log). Per-prompt and per-user files are local only, in `C:\Users\zhang\bci-data\derived\p11-21\`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page holds pooled aggregates and per-draw counts only: no per-user value, no text, no id.

**`safe-wpm/0.2` is a PROPOSAL. It is not adopted.** Every value on this page is a proposed-v0.2 value. No headline may use it before the user adopts v0.2.

Run details:
- Time: 2026-11-21 17:46 to 18:33, detached, from `git archive` snapshots (`beac437` for stage 1; `99b7eb6` and `fef0abb` for the margin, the arms and the analysis; finished draws were reused).
- Resources: **CPU only**, no GPU, no new inference. 2 workers x 1 thread, isolation class `background`. 202 draws (2 X1 + 80 stage 1 + 120 arms), about 21 to 25 s each after the first session a / b window analyses.

## Outcome
**The target is met. Arm LX-M (primary) gives a calibration-inclusive proposed-v0.2 safe WPM of 5.67 [3.43, 8.26] against the no-BCI reference 3.09. The lower end is above 3.09. 0 / 40 draws are above alpha on the test set, every draw is certified, and every null control gets 0 commits.** The two levers together do it: partition-only outer draws and a shift margin that is estimated for the LX-FL guard itself. The secondary arms are also above: LX-T (L-FL margin) 7.21 [4.78, 10.43], and LX-P (no margin) 8.80 [4.89, 12.26].

## Checks
| Id | Check | Result |
|---|---|---|
| X1 (must pass) | this code reruns P11-16 draws k01 and k07 | **pass**: model digest, threshold, commits, prefix commits, wrong commits, raw value and all 3 x 1,221 actions are equal (k01: 0.95, 505, 21, 6.730; k07: 0.83, 693, 62, 10.166) |
| X2 (original; now descriptive) | session a / b analyses equal the P11-23 memo | 203 / 2,442 windows differ, in the native n-best **scores** only (maximum 8.0e-5); status, top-1, n-best texts and the 10 signals are equal. The first run stopped here, as the plan requires (see Deviations) |
| X2' (must pass; amendment 1) | fresh analyses with an empty memo equal this item's memo, under the run code and under the P11-20 code snapshot `d3511df` | **pass**: 203 / 203 differing windows and 100 / 100 other windows are equal, under both codes |
| X3 (must pass) | session a / b prompt counts = P11-20 file | **pass**: 1,221 + 1,221, 8 users |
| X4 (must pass) | LTT wrong-commit recount (prefix rule) = `ltt_prefix_threshold` risk x n | **pass**: 80 / 80 stage-1 draws, 120 / 120 arm draws |
| C-null | primary draws: test time-shuffled and zero-EMG commits = 0 / 1,221 | **pass** (40 / 40; also 0 in every LX-P and LX-T draw) |
| C-cal | calibrate controls <= 15 / 300 | pass in all 200 draws (maximum 10) |

## Stage 1: LX-FL shift steps (sessions a and b only; no track-val or track-test data)

| quantity | a -> b (A, 40 draws) | b -> a (B, 40 draws) |
|---|---|---|
| guards (finite threshold, controls pass) | 40 | 40 |
| step size s_d (mean pooled gap) | **+0.0079** | **-0.0063** |
| jackknife SE_d over users | 0.0110 | 0.0090 |
| **U_d = s_d + 1.8946 x SE_d** | **0.0288** | 0.0108 |
| per-draw gap: SD; q10 / median / q90; range | 0.0060; -0.0000 / +0.0077 / +0.0159; -0.0024 to +0.0210 | 0.0062; -0.0137 / -0.0065 / +0.0028; -0.0161 to +0.0082 |
| leave-one-user-out step sizes (8): SD; range | 0.0045; -0.0009 to +0.0118 | 0.0036; -0.0091 to +0.0014 |
| per-user step sizes (8, unlabelled): SD; median; range | 0.0313; -0.0025; -0.0184 to +0.0706 | 0.0258; +0.0049; -0.0610 to +0.0138 |
| LTT in-sample rate (mean) | 0.0328 | 0.0329 |
| evaluation-session rate (mean, range) | 0.0407 (0.0303-0.0557) | 0.0266 (0.0172-0.0426) |
| evaluation commits (mean, range) | 679.7 (647-755) | 652.0 (570-741) |
| thresholds | 0.81-0.94 | 0.84-0.94 |

**Margin (pre-registered P11-23 rule): m_LX = 0.0288 (from a -> b), alpha_LX = 0.0212.** For comparison, the L-FL margin of P11-23 is m2 = 0.0185 (alpha'' 0.0314). The LX-FL step is larger (s +0.0079 vs +0.0045) and spreads more over users (SE 0.0110 vs 0.0074).

## Arms: track val -> track test, 40 partition-only draws each

| Arm | LTT level | above alpha (>= 62 wrong) | test rate mean [min, max] | LTT in-sample rate | commits mean (range) | prefix commits | wrong mean (range) | thresholds |
|---|---|---|---|---|---|---|---|---|
| **LX-M (primary)** | **0.0212** | **0 / 40** | 0.0113 [0.0025, 0.0238] | 0.0086 | 462.7 (297-572) | 446.4 | 13.8 (3-29) | 0.92-0.99 |
| LX-T | 0.0314 | 0 / 40 | 0.0203 [0.0106, 0.0385] | 0.0182 | 544.9 (457-671) | 509.8 | 24.8 (13-47) | 0.84-0.97 |
| LX-P | 0.05 | 1 / 40 (63 wrong) | 0.0357 [0.0254, 0.0516] | 0.0332 | 640.9 (582-703) | 571.3 | 43.6 (31-63) | 0.80-0.92 |
| P11-16 (bootstrap draws, reference) | 0.05 | 7 / 40 | | | 639.9 | | 46.0 | 0.78-0.98 |

- Significant exceedances (>= 75 wrong): 0 in every arm.
- Above the arm's own LTT level (descriptive): LX-M 1 / 40 above 0.0212; LX-T 1 / 40 above 0.0314.
- Optimism gap (test minus LTT in-sample rate): LX-M +0.0028 (SD 0.0030), LX-T +0.0021, LX-P +0.0025. On these partition-only draws the val / test shift of LX-FL is small.
- Paired by k: LX-M has fewer wrong commits than LX-P in 40 / 40 draws and fewer than LX-T in 39 / 40 (1 equal). McNemar on above-alpha, LX-M vs P11-16: 0 vs 7, p = 0.016.

### Calibration-inclusive intervals (P11-17 procedure: 40 draw values x the same 2,000 user-cluster weight vectors; non-credited draws earn 0.0)

| Arm | value [95 %] | lower end > 3.09? | credited | draw values: median, range | SD between / within draws | normal interval | secondary: prompt-level inner level |
|---|---|---|---|---|---|---|---|
| **LX-M (primary)** | **5.67 [3.43, 8.26]** | **yes** | 40 / 40 | 5.73, 2.96-7.94 | 0.78 / 0.92 | [3.31, 8.03] | 5.67 [3.85, 7.46] |
| LX-T | 7.21 [4.78, 10.43] | yes | 40 / 40 | 7.38, 5.21-9.48 | 0.91 / 1.15 | [4.33, 10.09] | 7.21 [5.42, 9.11] |
| LX-P | 8.80 [4.89, 12.26] | yes (fragile, see below) | 39 / 40 | 9.13, 0.00-10.02 | 1.54 / 1.38 | [4.75, 12.85] | 8.80 [6.66, 10.38] |
| P11-16 (bootstrap draws, reference) | 7.18 [0.00, 12.13] | no | 33 / 40 | 8.63, 0.00-10.28 | 3.47 / 1.24 | [-0.04, 14.40] | |

- LX-M: 39 / 40 draw values are above 3.09. The lowest draw is 2.96 (297 commits), the next ones are 4.57 and 4.63.
- LX-P: its 1 zero draw is exactly 2.5 % of the pooled values, so the 2.5th percentile sits on the edge of the zero block. One more zero draw would put the lower end at 0. So the LX-P lower end is not a reliable result. With the zero draw counted at its raw value, LX-P gives 9.06 [6.50, 12.33].

## Comparison with the pre-registered rules

| rule (plan) | outcome |
|---|---|
| X1, X2' (amendment 1), X3, X4 must pass | pass |
| >= 30 guards per direction, m_LX < 0.05 | 40 and 40; m_LX = 0.0288; arm LX-M run |
| **H1 (primary)**: LX-M lower end > 3.09 and C-null | **met: "clearly above after calibration uncertainty"** (5.67 [3.43, 8.26]) |
| H2: f_LXM | 0 / 40: **"margin removes the excess"**; (A2) **"not contradicted on test"** (mean test rate 0.0113) |
| H3: f_LXP < 7 | yes: 1 / 40 (one-sided Fisher vs 7 / 40, p = 0.028) |
| robustness: LX-T verdict | "clearly above after calibration uncertainty" (7.21 [4.78, 10.43]); the robustness note is not needed |
| expectation (not a rule): m_LX <= 0.0185 | **wrong**: m_LX = 0.0288 is larger than the L-FL margin |

> **Our take:** two fixes that worked for L-FL also work for the LX-FL prefix guard. Partition-only draws alone cut the zero draws from 7 / 40 to 1 / 40. The LX-specific shift margin removes the last one. It also lowers the error rate a lot: the mean test rate falls from 0.036 to 0.011, so the guard is far from alpha on every draw. The cost is value: commits fall from 641 to 463 per draw, and the mean falls from 8.80 to 5.67. But the interval gets much narrower (between-draw SD 0.78 vs 3.47 in P11-16), so the lower end rises from 0.00 to 3.43. The margin rule is conservative here. The LX step a -> b is larger than the L-FL step, but the track-val -> track-test step on these draws is small (+0.0028), so LX-T with the smaller L-FL margin also stays safe (0 / 40) and gives a higher lower end (4.78). We keep LX-M as the result because it was pre-registered and its margin comes from the guard that is deployed. The lower end clears 3.09 by only 0.34, so this is a narrow pass. One low draw (2.96, 297 commits) shows that a single calibration can still give a value below no-BCI. This is the first EMG result whose calibration-inclusive lower end is above no-BCI. It holds only under the proposed v0.2 and assumption (A2), and only on these 8 users.

## Deviations
1. **Amendment 1 (check X2 -> X2').** The first chain run (code `beac437`) stopped at the margin stage because X2 failed (see Checks). Read-only diagnosis showed that fresh analyses give this item's values exactly, under both the current and the P11-20 code. The stored P11-20 / P11-23 memo entries carry a small, state-dependent difference in the native scores (cause not found). The amendment replaced X2 with a fresh-decode reproduction check X2'. It changed no lever, arm, seed, margin rule, metric or decision rule. It was written before any m_LX, alpha_LX or arm number existed. Its header says "18:20"; it was actually written at about 18:08 (the run log shows the relaunch at 18:09). Some stage-1 per-draw lines (gaps) had been seen in the log before the amendment.
2. **Smoke test before launch.** Before the code commit, a scratch run computed X01 (= P11-16 k01; it matched) and A01 (gap -0.0005, the same as in the real run). These files stayed in the scratch folder.
3. **Analysis bug fix** (`fef0abb`): the P11-16 draw files have no `above_alpha` field, so the paired McNemar test now computes it from the wrong counts (n_wrong / 1,221 > 0.05). No draw was rerun.
4. **Secondary interval.** The library `calibration_draw_interval` scores v0.1 sentence commits only. So the secondary interval uses the same prompt-level multinomial resampling scheme (`default_rng(0)`, B 2,000) with the v0.2 formula of P11-16 `v02_values`.

## Gap rule
**Gap 166 closes.** Under the plan (`95b1a91`, amendment 1 `99b7eb6`, with X1, X2', X3 and X4 passed), results.md reports the arm LX-M calibration-inclusive interval vs 3.09: 5.67 [3.43, 8.26], "clearly above after calibration uncertainty".

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-21-lx-margin/test_p11_21.py` |
| X2' | `.venv\Scripts\python.exe -I experiments/2026-11-21-p11-21-lx-margin/x2_fresh.py <code root> <run or p1120>` (needs feat-w0.pkl from stage 1) |
| Full run (detached; about 45 min CPU with 2 workers x 1 thread) | `.venv\Scripts\python.exe experiments/2026-11-21-p11-21-lx-margin/launch.py fef0abb` (needs the P11-16 memo and draws, the P11-20 session a / b log-probs and prompt rows, the P11-23 memos, and the P11-09 / P11-11 / P11-14 inputs). Run the X2' script after stage 1 and before the margin stage. |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-21\DONE` exists; to stop, create `derived\p11-21\STOP` |

## Limits
- (a) The margin comes from two directions between the same two sessions (a, b). The backward step is not a real time step.
- (b) Sessions a and b selected the decoder checkpoints (slightly in-sample).
- (c) (A2) is an assumption; one test set checks it. The test result does not show which margin is right: LX-T (smaller margin) also had 0 / 40 above alpha.
- (d) The pinned decoder, gate, LM, lexicon and the LX feature set were chosen on track-val prompts.
- (e) All draws share the same 1,224 calibration and 1,221 test prompts; the spread is split variation only.
- (f) 8 users: the within-draw user-cluster spread is fixed by the data. The lower end clears 3.09 by 0.34 only.
- (g) Proposed v0.2 only. The adopted v0.1 value of LX-FL is much lower (P11-16: 2.60 with one calibration).
- (h) LX-FL is certified outside `calibrate` (no `TrustGuard` file; gap 165, P5-35).
