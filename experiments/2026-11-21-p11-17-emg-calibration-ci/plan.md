---
title: P11-17 Calibration-inclusive safe WPM interval for the EMG P11-14 L-FL guard - pre-registration
type: experiment
task: P11-17
updated: 2026-11-21
---

# P11-17: a safe-WPM interval for the EMG L-FL guard that includes the calibration draw (pre-registration)

Written and committed **before** any number of this item was computed. Gap 133 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-17](../../wiki/questions/roadmap-standard.md#p11-17-calibration-inclusive-safe-wpm-interval-for-the-emg-p11-14-l-fl-guard). Method: [P15-29](../2026-11-20-p15-29-calibration-ci/plan.md) (`fidetype.benchmark.safe_wpm.calibration_draw_interval`, [docs section 6b](../../docs/safe-wpm.md), proposed). Guard: [P11-14](../2026-11-20-p11-14-emg-lm-confidence/plan.md) primary arm L-FL ([results](../2026-11-20-p11-14-emg-lm-confidence/results.md)).

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates and per-draw counts only: no per-user value, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-17\`. The P11-07, P11-09, P11-11, P11-12 and P11-14 files are read only.

CPU only (isolation runner, class `background`, 2 threads). **No GPU.**

## Problem
P11-14 gives the L-FL guard a certified safe WPM v0.1 of **6.80 [4.49, 9.63]** on the 1,221 track-test prompts of 8 users (285 commits, 52 wrong). The CI is a user-cluster bootstrap with the decisions fixed. So it is conditional on one calibration. On T15, P15-29 showed that the calibration-draw variation can be larger than the trial variation (between / within SD ratio 4.1).

## Question
What is the 95 % interval of the L-FL safe WPM v0.1 when it includes (1) the variation of the calibration sample and split and (2) the variation of the evaluation prompts? Is its lower end above the EMG no-BCI reference **3.09**?

## What was done before this plan (disclosure)
Reading of the P11-14, P15-29, P15-34 and P15-37 plans, code and result pages, and of `calibrate`, `safe_wpm`, `calibration_draw_interval` and `bootstrap_ci`. No draw, no guard, no decision and no score of this item was computed before this commit.

## Fixed parts (as P11-14, unchanged)
- Data and splits: the 8 P11-01 test users; calibration = track-val session (1,224 prompts), evaluation = track-test session (1,221 prompts); P11-09 windows (33-class key form); target = intended text (P11-11 `resolve`).
- Decoder FL (w 0.25, beta 1, lam 8, beam 8), P11-12 no-signal gate (`derived\p11-12\gate.json`), P11-11 OOV gate, the competitor set U and the 10 signals of P11-14. Arm **L-FL** (two-item n-best, amendment 1: empty at c <= 0.5).
- `calibrate` settings: alpha 0.05, delta 0.1, LTT, `confidence="p_top1"`, `input_kind="logits"`, key-CTC vocabulary, `audit_text=False`, `null_trials` 300 (automatic uniform and frame-shuffled controls), `null_inputs` = 300 input-level time-shuffled calibration windows.
- Scoring: safe WPM v0.1 (adopted), per-prompt neural time, truth lengths, default correction rule, guarantee and controls from the guard sheet; no-BCI reference 3.09.

## Pinned values (stated limit, as the pinned pipeline values of P15-29)
The decoder weights (w, beta, lam; tuned in P11-07), the no-signal gate thresholds (P11-12), the LM, the lexicon and the arm choice (L-FL, selected in P11-14) stay fixed in every draw. They were tuned on the seed-0 tuning items. Re-tuning them per draw would need a new decoder grid search per draw. So the interval leaves out their variation.

## Method (primary): two-level bootstrap, fixed evaluation set (P15-29 procedure)

**Outer level: calibration draws.** For draw k = 1, 2, ..., K:
1. Calibrate seed s_k = the first 8 hex digits of SHA-256(`"p11-17|emg|cal|<k>"`) as an integer.
2. Split rule (as `calibrate` and P15-29 `draw_order`): o = `numpy.random.default_rng(s_k).permutation(1224)`; `_split(1224)` gives the parts fit / policy grid / LTT = 306 / 459 / 459.
3. Bootstrap of the calibration sample: inside each part separately, draw the same number of prompts **with replacement** (rng = `default_rng` of the first 8 hex digits of SHA-256(`"p11-17|emg|boot|<k>"`)). The parts stay disjoint. The input order is set so that the permutation of `calibrate` with seed s_k gives exactly these parts (P15-29 `draw_order`).
4. **Refit the L confidence model** on the draw's tuning entries = the resampled fit + policy parts (765 entries, duplicates kept, sorted by source position), committable entries only, with the P11-14 rule (`Learned.fit`: standardise, clip, L2 1.0, sign constraints with backward elimination). This is the counterpart of the learned commit score that `calibrate` refits in P15-29. The LTT part is never used to fit the model.
5. Null inputs: the time-shuffled windows of the prompts at positions `sorted(default_rng(s_k).choice(1224, 300, replace=False))` of the original calibration list (for seed 0 this is the P11-14 `null_pick`).
6. Run `calibrate` with seed s_k and the settings above. So each draw refits the temperature, the conformal and policy parts and the LTT certification, and runs the three null controls again.
7. Decide all 1,221 evaluation prompts with the new guard: real, input-level time-shuffled and zero EMG.

**Credit rule per draw (fixed here).** A draw adds its values only if all of these hold:
- `calibrate` did not refuse the guard (no null control failed);
- the `safe_wpm` v0.1 status on the real evaluation prompts is `certified` (so not `not-certified`, `vacuous` or `above-alpha` = evaluation wrong-commit rate > 0.05);
- the evaluation controls pass as V6 of P11-14: time-shuffled and zero-EMG commit rates each <= 0.05.

Any other draw adds 0.0 for all B resamples. The counts of each status are reported.

**Inner level: user-cluster bootstrap (primary).** The P11-14 CI resamples users (8 clusters), not prompts. So the primary inner level is the same: B = 2,000 weight vectors from `fidetype.benchmark.scoring.bootstrap_weights(default_rng(0), "group", clusters)` with cluster = user (exactly the weights of the P11-14 CI). The same B vectors are used in every draw. Decisions are fixed inside a draw. The value of a resample is the `safe-wpm/0.1` formula with those weights (as `_point`).

**Combined interval (primary).** Pool the K x B values. The interval is their 2.5th and 97.5th percentiles. The point value is the mean of the K draw values (each = the full-evaluation-set safe WPM of the draw, or 0.0 by the credit rule). For K = 1 this is the conditional CI of P11-14.

**Secondary interval (library, trial level).** `calibration_draw_interval` on the same K draws with its default inner level (B = 2,000 prompt resamples, seed 0) and `reference=3.09`. Draws that fail the V6 evaluation controls are passed as `{"refused": True}`. Reported; no verdict depends on it.

**Number of draws.** K = **40** (k = 1 ... 40), fixed here, as P15-29 / P15-37 on T15. No cutoff. All 40 draws are analysed. If a draw stops with an error, the run is resumed until all 40 exist. The analysis does not start before all 40 draws exist.

## Cross-checks (reported)
- **X1 analytic variance decomposition** (primary inner level): total variance = mean within-draw variance + between-draw variance of the draw values (ddof 1); normal interval mean +/- 1.96 x total SD; ratio between-draw SD / within-draw SD.
- **X4 code check (must pass).** Draw z0 = seed 0, no resampling, model refit on the seed-0 tuning items. It must reproduce P11-14 L-FL: the same model parameters as `model-L-FL.json` (digest), threshold 0.63, the same action and text on 1,221 / 1,221 real, time-shuffled and zero-EMG prompts (`derived\p11-14\decisions-L-FL.json`), 285 commits, 52 wrong, safe WPM 6.80 (6.8031), and the primary interval with K = 1 on z0 = [4.49, 9.63]. A failed check stops the run (no result from code that does not reproduce). z0 is not one of the K draws.
- **Exploratory variants (pre-named here, descriptive only):** (V-a) above-alpha draws keep their value; (V-b) credited draws only. They show whether the verdict depends on the credit rule.
- Also reported: draw values (mean, median, SD, range), the fraction of draws above 3.09, mean commits and wrong commits, commit thresholds, control counts, the number of model features kept per draw.

## Decision rule
Reference: the EMG no-BCI reference **3.09** (P11-14).

| outcome (primary interval) | verdict |
|---|---|
| combined lower end > 3.09 | **clearly above after calibration uncertainty** |
| mean > 3.09 >= lower end | **above, but inside the combined interval** |
| mean <= 3.09 | **not above** |

**Pass** (the claim "the EMG L-FL guard is clearly above the no-BCI reference" survives the calibration draw) = the first row. **Gap 133 closes** when the verdict is reported under this plan with X4 passed, whatever the verdict (the done-when asks for the report against 3.09). If the verdict is not the first row, the public EMG claim must say "above on average, not reliably above once the calibration draw is counted", and a follow-up item may apply the P15-37 multi-split method to EMG (a new item; not part of this plan).

Expectation (stated now, not a rule): the EMG LTT part has 459 items (T15: 271), so the between-draw spread may be smaller than on T15. But the P11-14 empirical wrong-commit rate (0.043) is close to alpha, so some draws may be `above-alpha` and earn 0.0. If more than 2 of 40 draws (5 %) earn 0.0, the lower end is 0.0.

## Order, limits, outputs
1. Commit this plan. Then commit `run.py` (imports the P11-14 code read only; writes only to `derived\p11-17\`), `launch.py` and a test on synthetic data.
2. Run detached from a `git archive` snapshot of the committed code (other agents may change `src/fidetype/`): one worker, `python -m fidetype.utils.isolation run --class background --threads 2 -- python -I run.py worker`, CPU only, keep-awake, log `results/run.log`, `DONE` file `C:\Users\zhang\bci-data\derived\p11-17\DONE`. Order: z0 (X4 check) first, then k = 1 ... 40, then the analysis. Resumable: each finished draw is saved as `derived\p11-17\draw-<k>.json` and skipped on a rerun. The decode memo starts from a copy of `derived\p11-14\feat.pkl` (read only) and is saved in `derived\p11-17\`.
3. The repo gets `results/results.json` (aggregates and per-draw counts, no text, no per-user value) and `results/run.log`. Per-prompt decisions stay in the derived folder.
4. No change of the method, K, the credit rule, the reference or the decision rule after this commit. Any later variant is a new item.

Known limits (stated before any result): (a) pinned decoder, gate, LM, lexicon and arm choice (see above); (b) bootstrap duplicates inside the LTT part: a single draw's certificate is not a valid certificate; the draws show the sampling variation and may over-state it a little; (c) the outer level resamples prompts, not users; prompts of one user are correlated, so the calibration-sample variation may be under-stated; (d) the evaluation set is the same in every draw, so the evaluation variation comes only from the inner bootstrap; (e) 8 users, one session each.
