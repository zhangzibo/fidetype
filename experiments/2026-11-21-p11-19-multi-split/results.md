---
title: P11-19 Multi-split EMG L-FL guard with a calibration-inclusive lower end above no-BCI - results
type: experiment
task: P11-19
updated: 2026-11-22
---

# P11-19: multi-split EMG L-FL sentence guard, calibration-inclusive lower end vs no-BCI 3.09 (results)

Pre-registration: [plan.md](plan.md), commit `c71c9bc`, committed and pushed before any number was computed. Amendment 1 (fresh decodes; X2'' -> X2f; new X1'): `445c714`, code `fca492e`. Amendment 2 (X2f descriptive; must-pass reproduction = X1 + X1'): `c3df8ad`. Both amendments were written before any phase-2 split guard, in-sample value or arm number existed. Code and synthetic tests: `1a281e6`, `fca492e`, `c3df8ad` ([run.py](run.py), [launch.py](launch.py), [test_p11_19.py](test_p11_19.py)). Aggregates and per-draw pooled counts: [results/results.json](results/results.json). Log: [results/run.log](results/run.log). Per-prompt files are local only, in `C:\Users\zhang\bci-data\derived\p11-19\`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page holds pooled aggregates and per-draw counts only: no per-user value, no text, no id.

**Metric version: `safe-wpm/0.1` (adopted).** The L-FL guard commits whole sentences. For sentence commits, v0.1 and the proposed v0.2 give the same value. So this result does **not** depend on the v0.2 proposal (P11-21 does). The calibration-inclusive interval is the method of `docs/safe-wpm.md` section 6b. That section is a **proposed** reporting addition and is not adopted.

Run details:
- Time: 2026-11-21 21:16 to 2026-11-22 01:07, detached, from `git archive` snapshots. The 21:16 chain (`1a281e6`) stopped at X2''. The 21:23 chain (`fca492e`) stopped at X2f. The 21:35 chain (`c3df8ad`) ran phase 2 from 21:36 to 01:07 and then the analysis.
- Resources: **CPU only**, no GPU, no new inference. 2 workers x 1 thread, isolation class `background`. 120 split guards, 176-268 s each (mean 211 s), plus 2 X1 and 2 X1' draws. Wall time of the final chain: 3.5 h, under the 5 h cap.

## Outcome
**The target is met. Arm BX3 (primary) gives a calibration-inclusive safe WPM (v0.1) of 5.90 [3.45, 8.89] against the no-BCI reference 3.09.** The lower end is above 3.09, so the verdict is "clearly above after calibration uncertainty". 0 / 40 draws are above alpha on test, every draw is certified, and every null control gets 0 commits.

The pass is **narrow**: the lower end clears 3.09 by 0.36. The normal-approximation interval [3.10, 8.70] clears it by only 0.01. The secondary arm BD3 (median guard) does **not** clear 3.09: 5.19 [2.90, 8.19].

## Checks
| Id | Check | Result |
|---|---|---|
| X1 (must pass) | this code, with the P11-23 memo copy, reruns P11-23 S01 and S13 | **pass**: model digest, threshold, commits, wrong commits, value and all 3 x 1,221 actions and texts are equal |
| X1' (must pass after amendment 2) | the same two draws with fresh decodes (empty memo) | **pass**: all fields equal, the same model digests, 0 differing actions |
| X2'' (original; now descriptive) | fresh decodes = P11-23 memo, 250 sample windows | failed in the first run: 14 / 250 windows differ (signals up to about 3e-8, native scores up to about 3e-5; status, top-1 and texts equal). This stopped the first chain, as the plan requires |
| X2f (amendment 1; descriptive after amendment 2) | a second empty-memo analyser = this item's fresh run memo | 159 / 250 sample windows are not in the run memo under their raw-window key (the guard path stores other keys). 17 of the 85 present windows differ, with signals up to 2.97e-8 and native scores up to 3.82e-5. In the final run memo, 3 / 250 differ from the P11-23 memo |
| X3 (must pass) | split-1 partitions = the P11-23 S2 partitions | **pass**: 40 / 40 |
| X4 (must pass) | LTT wrong-commit recount = sheet count | **pass**: 120 / 120 split guards |
| C-null | every BX3 draw: test time-shuffled and zero-EMG commits = 0 / 1,221 | **pass**: 40 / 40. The count is also 0 in every BD3, AN3 and J1 draw |
| C-cal | calibrate controls <= 15 / 300 | pass: 0 refused split guards; the maximum calibrate control count is 0 |

Split guards: 120 / 120 have a guard. 0 are refused and 0 are infeasible. 30 / 120 thresholds are at the grid floor of 0.30. In-sample values on the 1,224 calibration prompts: mean 5.38, SD 0.79, range 2.46-7.04.

## Arms: track val -> track test, 40 draws, each split guard at (alpha'' 0.0314, delta / 3)

| Arm | above alpha (>= 62 wrong) | above 0.0314 (descriptive) | test rate mean [min, max] | LTT in-sample rate | optimism gap | commits mean (range) | wrong mean (range) | thresholds at 0.30 |
|---|---|---|---|---|---|---|---|---|
| **BX3 (primary, max in-sample value)** | **0 / 40** | 13 / 40 | 0.0281 [0.0123, 0.0434] | 0.0143 | +0.0138 | 226.7 (155-288) | 34.3 (15-53) | 7 |
| BD3 (median) | 0 / 40 | 2 / 40 | 0.0190 [0.0057, 0.0377] | 0.0133 | +0.0057 | 187.4 (115-270) | 23.3 (7-46) | 12 |
| AN3 (AND of the 3) | 0 / 40 | 1 / 40 | 0.0116 [0.0008, 0.0369] | (<= 0.0150) | -0.0034 | 148.3 (66-261) | 14.2 (1-45) | - |
| J1 (split 1 alone at delta / 3) | 0 / 40 | 4 / 40 | 0.0188 [0.0008, 0.0434] | 0.0127 | +0.0061 | 184.2 (66-288) | 23.0 (1-53) | 12 |
| S2 (P11-23, split 1 at delta, reference) | 0 / 40 | 9 / 40 | 0.0238 [0.0008, 0.0434] | 0.0151 | +0.0087 | 205.5 (66-293) | 29.1 (1-53) | 16 |

- Significant exceedances (>= 75 wrong): 0 in every arm.
- BX3 picked split 1 in 13 draws, split 2 in 10 and split 3 in 17.
- Paired with S2 (exact pairing: X1' shows that the fresh and memo worlds give equal actions on S01 / S13):

| Arm vs S2 | value up / same / down | mean paired difference | McNemar on above-alpha |
|---|---|---|---|
| BX3 | 19 / 4 / 17 | +0.43 | 0 vs 0, p = 1.0 |
| BD3 | 8 / 6 / 26 | -0.27 | p = 1.0 |
| AN3 | 1 / 3 / 36 | -1.10 | p = 1.0 |
| J1 | 0 / 17 / 23 | -0.37 | p = 1.0 |

### Calibration-inclusive intervals (P11-17 procedure: 40 draw values x the same 2,000 user-cluster weight vectors; non-credited draws earn 0.0)

| Arm | value [95 %] | lower end > 3.09? | credited | draw values: median, range | SD between / within | normal interval | secondary: library (prompt-level) | verdict |
|---|---|---|---|---|---|---|---|---|
| **BX3** | **5.90 [3.45, 8.89]** | **yes** | 40 / 40 | 6.01, 4.55-6.84 | 0.59 / 1.30 | [3.10, 8.70] | 5.90 [4.41, 7.27] | **clearly above after calibration uncertainty** |
| BD3 | 5.19 [2.90, 8.19] | no | 40 / 40 | 5.20, 3.65-6.65 | 0.68 / 1.20 | [2.49, 7.90] | 5.19 [3.70, 6.76] | above, but inside |
| AN3 | 4.37 [2.17, 7.28] | no | 40 / 40 | 4.41, 2.25-6.43 | 0.79 / 1.05 | [1.78, 6.95] | 4.37 [2.66, 6.30] | above, but inside |
| J1 | 5.09 [2.42, 8.32] | no | 40 / 40 | 5.07, 2.25-6.84 | 0.95 / 1.18 | [2.12, 8.06] | 5.09 [2.79, 7.00] | above, but inside |
| S2 (P11-23) | 5.47 [2.44, 8.77] | no | 40 / 40 | 5.70, 2.25-7.03 | 1.07 / 1.23 | [2.27, 8.66] | 5.47 [2.79, 7.31] | above, but inside |

All 40 BX3 draw values are above 3.09. The lowest are 4.55 (155 commits, threshold 0.92), 4.75 and 4.87. The S2 low draw (S13: 2.25, 66 commits) does not occur: in that draw, BX3 selects another split guard.

### Why-not analysis (pre-registered; reported for every arm)
F_w = mean - 1.96 x within-draw SD, the lower end with zero between-draw spread. n_u* = the number of users, and n_cal* = the number of calibration prompts, that would put the normal lower end at 3.09 (rough, normal approximation).

| Arm | F_w | F_w > 3.09? | n_u* (users) | n_cal* (calibration prompts) |
|---|---|---|---|---|
| **BX3** | **3.35** | yes | **7.9** (8 exist) | **1,182** (1,224 exist) |
| BD3 | 2.84 | no | 16.7 | not reachable by more calibration data alone |
| AN3 | 2.30 | no | not reachable by more users alone | not reachable by more calibration data alone |
| J1 | 2.78 | no | 78.3 | not reachable by more calibration data alone |
| S2 | 3.05 | no | 36.4 | not reachable by more calibration data alone |

So the plan's statement holds: at the S2 mean, the within-draw user spread alone kept the lower end below 3.09 (F_w 3.05). BX3 passes because it does two things at once. It raises the mean (+0.43 vs S2), and it halves the between-draw SD (0.59 vs 1.07). The within-draw SD (1.30) stays about the same. The data needed by BX3 (7.9 users, 1,182 calibration prompts) is just under what exists. This confirms that the pass is narrow.

## Comparison with the pre-registered rules

| Rule (plan) | Outcome |
|---|---|
| X1, X3, X4 must pass; after amendment 2, X1' must pass | pass |
| **H1 (primary)**: BX3 lower end > 3.09 and C-null | **met: "clearly above after calibration uncertainty"** (5.90 [3.45, 8.89]) |
| H2: f(BX3) | 0 / 40: **"multi-split keeps the excess removed"**; (A2) **"not contradicted on test"** (mean test rate 0.0281) |
| H3: BD3 verdict | "above, but inside the combined interval" (5.19 [2.90, 8.19]). By the plan, this does not change H1 (one primary) |
| Expectation (not a rule): BX3 mean about +0.5 vs S2, smaller sigma_b, sigma_w about 1.2, lower end near 3.09 | about right: +0.43, sigma_b 0.59, sigma_w 1.30, lower end 3.45 |

> **Our take:** selection over three Bonferroni split guards works for EMG L-FL. It did not work for T15 (P15-37). EMG gains because many single-split L-FL guards are limited by the grid floor and by an unlucky L-model fit, not by LTT. Then a stricter delta / 3 costs little: J1 loses 0.37 against S2. Picking the best of three on calibration data recovers more than that loss: BX3 gains 0.43 against S2. The price is safety headroom. BX3 has the highest test rate of the arms (0.028), and 13 / 40 BX3 draws are above the margin level 0.0314 on test. None is above the claim 0.05, so the margin m2 = 0.0185 absorbs the selection optimism, but only just (the maximum test rate is 0.0434). The median rule (the rule the done-when names) is safer but loses value, and it does not pass. This is the first EMG **v0.1** (adopted metric) result whose calibration-inclusive lower end is above no-BCI. It holds only under assumption (A2), on these 8 users and this test set. The margin of 0.36 is about the same as that of P11-21 (0.34).

## Deviations
1. **Amendment 1 (fresh decodes; X2'' -> X2f; new X1').** The first chain (`1a281e6`) stopped at X2''. 14 / 250 windows of the P11-23 memo copy differ from fresh decodes, by small amounts (gap 180). The amendment started the memo empty, so the run uses fresh decodes only. The first memo files and X1 records were moved to `derived\p11-19\memo-p1123-copy\`. **Time-stamp error:** the amendment header says "about 21:35"; it was written at about 21:21 (the relaunch log shows 21:23).
2. **Amendment 2 (X2f descriptive).** The second chain (`fca492e`) stopped at X2f. Many sample windows are not stored under their raw key, and 17 / 85 present windows differ between processes by up to 3e-8 in the signals. In one process, fresh decodes are deterministic and do not depend on order (read-only scratch diagnosis: 0 differences in 200 windows, in forward and reverse order). The cause of the difference between processes was not found. The must-pass reproduction check became X1 + X1'; both are exact. The descriptive X2'' count also had a crash, which was fixed. **Time-stamp error:** the amendment header says "21:45"; it was written at about 21:35 (the launch log shows 21:35:44).
3. **Smoke run.** Before the code commit, a scratch run computed X01 only (with the working-tree `src/`). It matched P11-23 S01. Its files stay in the agent scratch folder.
4. No phase-2 split guard, in-sample value or arm number existed before either amendment.

## Gap rule
**Gap 159 closes on its target branch.** Under the plan (`c71c9bc`, amendments `445c714` and `c3df8ad`, with X1, X1', X3 and X4 passed), results.md reports the arm BX3 calibration-inclusive interval vs 3.09, 5.90 [3.45, 8.89], "clearly above after calibration uncertainty", together with the why-not analysis.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-19-multi-split/test_p11_19.py` |
| Full run (detached; about 3.5 h CPU with 2 workers x 1 thread) | `.venv\Scripts\python.exe experiments/2026-11-21-p11-19-multi-split/launch.py c3df8ad` (needs the P11-23 margin, draws and memos, and the P11-09 / P11-11 / P11-14 inputs; the X1 check reads `derived\p11-19\memo-p1123-copy\`) |
| Check / stop | tail `results/run.log`. Done when `C:\Users\zhang\bci-data\derived\p11-19\DONE` exists. To stop, create `derived\p11-19\STOP` |

## Limits
- (a) The margin m2 comes from two directions between the same two sessions (P11-23). (A2) is an assumption, and one test set checks it. With BX3 the headroom is small: the maximum test rate is 0.0434, and 13 / 40 draws are above 0.0314.
- (b) Sessions a and b selected the decoder checkpoints, so the decoder is slightly in-sample on them.
- (c) The pinned decoder, gate, LM, lexicon and arm choice were tuned on track-val prompts.
- (d) All draws share the same 1,224 calibration and 1,221 test prompts, so the spread is split variation only.
- (e) 8 users: the within-draw spread is fixed by the data. The pass is narrow (+0.36; normal interval +0.01).
- (f) The interval method (section 6b) is a proposed reporting addition. It is not adopted.
- (g) Window analyses can differ between processes by up to about 3e-8 in the signals (gap 180). X1' shows no action change in 2 x 3 x 1,221 actions, but a flip near a threshold in other draws cannot be excluded.
- (h) Only BX3 passes; the median rule BD3 does not. A deployment must use the max rule with its higher test rate.
