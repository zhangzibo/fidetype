---
title: P11-18 Why 22.5 % of the EMG calibration draws are above alpha - pre-registration
type: experiment
task: P11-18
updated: 2026-11-21
---

# P11-18: why 22.5 % of the EMG calibration draws are above alpha (pre-registration)

Written and committed **before** any number of this item was computed. Gap 158 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-18](../../wiki/questions/roadmap-standard.md#p11-18-why-225--of-the-emg-calibration-draws-are-above-alpha). Source: [P11-17](../2026-11-21-p11-17-emg-calibration-ci/plan.md) ([results](../2026-11-21-p11-17-emg-calibration-ci/results.md)). Guard: [P11-14](../2026-11-20-p11-14-emg-lm-confidence/plan.md) arm L-FL.

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates and per-draw counts only: no per-user value, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-18\`. The P11-09, P11-11, P11-12, P11-14 and P11-17 files are read only.

CPU only (isolation runner, class `background`; 4 workers x 1 thread). **No GPU.**

## Problem
P11-17 ran K = 40 calibration draws of the L-FL guard. Each draw (1) made a fresh split of the 1,224 calibration (track-val) prompts into fit / policy grid / LTT = 306 / 459 / 459 and (2) resampled each part **with replacement**. 9 of 40 draws (22.5 %) had a wrong-commit rate above alpha = 0.05 on the 1,221 test (track-test) prompts (62-76 wrong commits). LTT promises P(population risk > alpha) <= delta = 10 % over the calibration draw.

Three causes can add up:
1. **Bootstrap duplicates** in the LTT part (about 290 distinct of 459): the binomial p-values treat duplicates as independent items, so they are too optimistic.
2. **Test-rate noise**: the test rate of a guard is a binomial estimate (n = 1,221, SD about 0.006 near 0.05). A guard with a true risk of 0.045 is above 0.05 on the test set with probability about 0.18 (exact binomial). So a test-set above-alpha fraction above delta does **not** by itself show that (G) fails.
3. **Session shift**: the guarantee assumes that the calibration and test prompts are exchangeable. Here they come from different sessions (val vs test).

## Question
With partition-only draws (no duplicates), what fraction of draws is above alpha on the test set, and what is the calibration-inclusive interval against no-BCI 3.09? Does the excess over delta come from (1) duplicates, or from (2) + (3)? And inside (2) + (3), is there evidence of (3)?

## What was done before this plan (disclosure)
Reading of the P11-17 plan, results, run.py, launch.py and tests, of the P15-37 method note, of the P11-14 / P11-09 / P11-11 runner functions used, and of `calibrate` / `_split` / the guard sheet fields. From the committed P11-17 `results.json` (already public) I listed the per-draw commit and wrong-commit counts (mean wrong 51.0 of 1,221; max 76). I computed, with no new data, the exact Fisher and binomial tail values used in the decision rule below. No draw, no guard, no decision and no score of this item was computed before this commit.

## Fixed parts (as P11-14 / P11-17, unchanged)
Data, windows, target, decoder FL, the no-signal gate, the OOV gate, the competitor set and the 10 signals; arm L-FL with the P11-14 model-fit rule (`Learned.fit`); `calibrate` settings (alpha 0.05, delta 0.1, LTT, `confidence="p_top1"`, `input_kind="logits"`, key-CTC vocabulary, `audit_text=False`, 300 automatic uniform and frame-shuffled null trials, 300 input-level time-shuffled null inputs); safe WPM v0.1 with the default correction rule; no-BCI reference 3.09; the P11-17 credit rule. Pinned: decoder weights, gate thresholds, LM, lexicon, arm choice (as P11-17 limit (a)).

## Arms

### Arm P (primary): partition-only draws, val -> test. K = 40.
For k = 1 ... 40:
1. seed s_k = the first 8 hex digits of SHA-256(`"p11-18|emg|cal|<k>"`) as an integer.
2. o = `numpy.random.default_rng(s_k).permutation(1224)`; `_split(1224)` = 306 / 459 / 459. **No resampling**: each part holds distinct prompts and the three parts cover all 1,224 prompts once (P11-17 `draw_order(n, s_k, None)`; the input order is the identity).
3. Refit the L model on the fit + policy parts (765 prompts, committable entries only; P11-17 `fit_model`).
4. Null inputs: the time-shuffled windows of `sorted(default_rng(s_k).choice(1224, 300, replace=False))`.
5. `calibrate` with seed s_k. Decide all 1,221 test prompts: real, input-level time-shuffled, zero EMG.
6. Per draw, record: the test commits and wrong commits; the safe WPM v0.1 status and value; the V6 controls; the credit (P11-17 rule); and the **LTT in-sample risk** = wrong commits of the deployed guard on the draw's 459 LTT prompts / 459, counted by re-deciding the LTT prompts with the same `same()` rule as the test (also recorded: the sheet's own `ltt_commits` / `ltt_wrong_commits`).

### Arm E (no session shift): partition-only draws on a pooled, exchangeable split. K = 40.
For k = 1 ... 40:
1. Pool the 1,224 val and 1,221 test prompts (2,445; val first, then test, each in the P11-11 order). q = `default_rng(seed_of("p11-18|emg|pool|<k>")).permutation(2445)`. Calibration list = pool[q[:1224]] (in that order); held-out "test" = pool[q[1224:]] (1,221 prompts, mixed sessions).
2. As arm P steps 2-5 on this calibration list, with seed s_k = seed_of(`"p11-18|emg|poolcal|<k>"`), no resampling. On the held-out set only the real windows are decided (the V6 evaluation controls are not run in arm E; the three calibrate null controls still run).
3. Record the held-out commits and wrong commits, the held-out wrong-commit rate (/ 1,221), the LTT in-sample risk (as arm P), and the safe WPM status (descriptive).

Calibration and held-out prompts in arm E are exchangeable by construction. So arm E has noise (1) + (2) only, and no session shift.

### X4 code check (must pass)
Draw z0 = seed 0, no resampling, model refit on the seed-0 tuning items. It must reproduce P11-14 L-FL exactly, as P11-17 X4 (P11-17 `x4_check`): model digest, threshold 0.63, 1,221 / 1,221 identical real, time-shuffled and zero-EMG decisions, 285 commits, 52 wrong, 6.8031, K = 1 interval [4.49, 9.63]. If it fails, no result is reported. z0 is not one of the K draws.

## Metrics
- **above-alpha fraction**: f = (number of draws with test wrong commits / 1,221 > 0.05) / 40, i.e. >= 62 wrong commits. f_B = 9 / 40 (P11-17, bootstrap, fixed); f_P (arm P); f_E (arm E, held-out rate).
- **significant exceedances**: draws whose test wrong commits w have a one-sided exact binomial p-value P(Bin(1221, 0.05) >= w) < 0.05, i.e. `binom.sf(w - 1, 1221, 0.05) < 0.05`. This is w >= 75 (w = 74: 0.054; w = 75: 0.042). Reported for B (from P11-17 counts), P and E.
- **optimism gap** per draw: g = test (or held-out) wrong-commit rate - LTT in-sample risk. Reported: mean, SD, range per arm; Pearson correlation of the two rates per arm.
- **calibration-inclusive interval (arm P)**: P11-17 primary procedure unchanged (K = 40 draw values with the P11-17 credit rule x the same B = 2,000 user-cluster weight vectors; pooled 2.5 / 97.5 percentiles; point = mean of draw values); X1 variance decomposition; library `calibration_draw_interval` (secondary); variants V-a and V-b (descriptive). Verdict vs 3.09 with the P11-17 rule (clearly above / above, but inside / not above).
- Also: statuses, mean commits and wrong commits, threshold range, control counts, model features kept. Arm E: held-out safe WPM values (descriptive only; a different test set per draw, so no interval).

## Decision rule (fixed here)

**Step 1: duplicates.** One-sided Fisher exact test of f_B = 9 / 40 > f_P. The tail values for 9 / 40 vs x / 40 are: x = 2: 0.024; x = 3: 0.057; x = 4: 0.112; x = 5: 0.189.

| f_P | conclusion |
|---|---|
| x <= 2 (Fisher p < 0.05; f_P <= delta) | **duplicates**: the excess goes away without bootstrap duplicates |
| x = 3 or 4 (f_P <= delta, p >= 0.05) | **partly duplicates** (inconclusive at K = 40): f_P is within delta, but the drop is not significant |
| x >= 5 (f_P > delta) | **noise + shift**: the excess stays without duplicates, so duplicates are not needed to explain it |

**Step 2: shift vs noise** (reported in every case; it names the sub-cause when step 1 says "noise + shift").
- Primary shift test: one-sided Welch t-test that the mean optimism gap of arm P is larger than that of arm E (p < 0.05 = **shift present**). The gap removes the in-sample optimism that both arms share.
- Secondary: one-sided Fisher exact test f_P > f_E.

| shift test (primary) | f_E | sub-cause |
|---|---|---|
| p < 0.05 | x_E <= 4 | **mainly session shift** |
| p < 0.05 | x_E >= 5 | **shift and noise** |
| p >= 0.05 | any | **mainly test-rate noise** (no evidence of a shift) |

**Step 3: noise check.** If the significant exceedances in arm P are at most 2 of 40 (5 %), the above-alpha draws are "consistent with test-rate noise around alpha" (single-draw level). More than 2 of 40 = "exceedances larger than test noise explains".

The final sentence of results.md takes the form: "The excess over delta comes from <step 1 conclusion>[; sub-cause: <step 2>]."

Expectation (stated now, not a rule): P11-17 had mean wrong 51 / 1,221 = 0.042 and only 1 of 40 draws (w = 76 >= 75) with a significant exceedance. So I expect f_P near f_B (step 1: noise + shift) and a small or no shift effect, but this is not a rule.

## Gap rule
**Gap 158 closes** when results.md reports, under this plan with X4 passed: f_P with K = 40 partition-only draws, the arm P calibration-inclusive interval vs 3.09, and the step 1 / step 2 conclusions, whatever they are.

## Order, limits, outputs
1. Commit this plan. Then commit `run.py` (imports the pure helpers of P11-17 `run.py` and the P11-14 runner read only; writes only to `derived\p11-18\`), `launch.py` and a test on synthetic data.
2. Run detached from a `git archive` snapshot of the committed code: 4 workers (`python -m fidetype.utils.isolation run --class background --threads 1 -- python -I run.py worker <w> 4`), jobs z0, P1-P40, E1-E40 round-robin; keep-awake; log `results/run.log`; `DONE` file `C:\Users\zhang\bci-data\derived\p11-18\DONE`. Each worker keeps its own window memo (`derived\p11-18\feat-w<w>.pkl`, started from a copy of `derived\p11-17\feat.pkl`, read only). Each finished draw is saved as `derived\p11-18\draw-<name>.json` and skipped on a rerun. Then `run.py analyse` (starts only when all 81 draws exist).
3. The repo gets `results/results.json` (aggregates and per-draw counts) and `results/run.log`.
4. No change of the arms, K, seeds, metrics or decision rule after this commit. Any later variant is a new item.

Known limits (stated before any result):
- (a) Pinned decoder, gate, LM, lexicon and arm choice; they were tuned on val prompts. In arm E about half of the held-out prompts are val prompts, some of them in the P11-07 / P11-14 tuning set. This can make arm E's held-out rate a little optimistic.
- (b) Arm E's calibration mixes sessions; its guard differs from arm P's. The optimism gap is used to compare the arms because it removes part of this difference.
- (c) Outer level: prompts, not users (as P11-17 limit (c)). Arm P draws share the same 1,224 prompts; their spread shows split variation only, not sample variation.
- (d) P11-17 did not record the LTT in-sample risk of the bootstrap draws, so the duplicate effect is measured only through f_B vs f_P.
- (e) K = 40 per arm: Fisher tests have low power for differences of a few draws (see the tail values above).
