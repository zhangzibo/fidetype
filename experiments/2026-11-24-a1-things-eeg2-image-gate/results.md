---
title: A1 trust-gated zero-shot image identification on THINGS-EEG2 - results
type: experiment-results
task: P16-07 (gap 207), experiment A1
plan: plan.md (1d8e9b9, amendment 5e2279e, implementation note 5f51e28)
updated: 2026-11-27
---

# A1 results: the gate is safe on new image concepts, but it never commits (outcome B)

Pre-registration: [plan.md](plan.md). Gates: [results/gate_sub-01.json](results/gate_sub-01.json) (commit 2a1823d) and [results/gate_sub-02.json](results/gate_sub-02.json) (commit 63b9c83). Both were committed and pushed before the test units of that subject were scored. Aggregates: [results/summary.json](results/summary.json).

## Outcome

**Pre-registered outcome: B ("safe but too conservative; the decoder is too weak for this gate")**, on both subjects.

- The decoder works (V1 passes): 80-trial-average 200-way top-1 is 17.0 % (subject 1) and 24.0 % (subject 2). Chance is 0.5 %.
- The gate certifies **no** COMMIT threshold on the calibration units. So it makes 0 commits on real EEG and 0 commits on all three nulls.
- The conformal sets hold the true image (coverage 0.846 and 0.890), but they are large (mean 45 and 49 images of 200). No set has 10 images or fewer. So the gate also makes 0 OFFERs. **Every test input gets ABSTAIN.**
- Rule (i) passes (nulls are silent). The error part of rule (ii) passes, because there is no wrong commit (amendment 5e2279e). The commit part of rule (ii) fails (0 % < 5 %). Rule (iii) passes: real sets are smaller than N1 sets.

The safety result is **vacuous**: a gate that never speaks cannot be wrong. A1 does not show that the error bound holds on new concepts. It shows that this decoder with 4-trial units is too weak for a 90 % precision gate on a 200-way task.

## Rules per subject

alpha = 0.10, delta = 0.10. Test: 200 new concepts, 20 units of 4 trials per image (4000 units). All numbers below were recomputed independently from the derived score files (`scores_cal.npz`, `scores_test.npz`) with our own NumPy / SciPy code. They agree with `summary.json` to all printed digits.

| rule | criterion | subject 1 | subject 2 |
|---|---|---|---|
| **V1** decoder works | 80-trial top-1 >= 10 % | 17.0 % (top-5 50.0 %): **pass** | 24.0 % (top-5 52.5 %): **pass** |
| **(i)** nulls silent | N1, N2, N3: commit rate <= 0.10, CP upper <= 0.20, bootstrap upper <= 0.20 | 0 / 4000 commits each; CP upper 0.00075; bootstrap upper 0: **pass** | the same: **pass** |
| **(ii)** error part | wrong-commit rate (precision form) <= 0.10, CP and bootstrap upper <= 0.20 | 0 commits, so no wrong commit: **pass** (amendment rule) | 0 commits: **pass** (amendment rule) |
| **(ii)** commit part | commit rate >= 5 % | 0 / 4000 = 0 % (CP upper 0.00075): **fail** | 0 %: **fail** |
| **(iii)** sets informative | per image mean set size, real < N1, one-sided Wilcoxon, p < 0.01 (200 pairs) | 45.12 vs 49.05; p = 9.7e-22; real < N1 on 155 / 200 images: **pass** | 48.64 vs 52.66; p = 1.2e-19; 152 / 200 images: **pass** |
| **V2** coverage | test coverage >= 0.80 | 0.846: **pass** | 0.890: **pass** |
| **R1** drift (S0 passed) | early and late halves: wrong-commit <= 0.10, CP upper <= 0.20 | early 0 / 2000, late 0 / 2000 commits: **pass (vacuous)** | 0 / 2000, 0 / 2000: **pass (vacuous)** |
| **R2** category hold-out | pooled over 8 clusters: wrong-commit <= 0.10, CP upper <= 0.20 | all 8 cluster gates certify nothing; 0 / 4000 commits: **pass (vacuous)** | the same: **pass (vacuous)** |
| per-subject outcome | outcome table | **B** | **B** |

Overall outcome (both subjects B): **B**. R1 and R2 add no qualifier. V2 passes.

## Details

### Decoder (own ATM-S re-implementation, seed 0)

| | subject 1 | subject 2 |
|---|---|---|
| best val epoch (200-way top-1 on 2000 val units) | 40 (17.55 %) | 34 (15.00 %) |
| test top-1 / top-5, 4-trial units (4000) | 12.25 % / 34.98 % | 14.00 % / 37.53 % |
| test top-1 / top-5, 80-trial average (200) | 17.0 % / 50.0 % | 24.0 % / 52.5 % |
| mean top-1 minus top-2 cosine (test units) | 0.0193 | 0.0168 |

The ATM paper reports 28.64 % (80-trial average, mean over subjects, best test epoch). Our epoch choice uses val only, and we hold out 500 training concepts for val and cal. So a lower number is expected (plan, "Where it may honestly fail"). We do not claim a comparison with the published number.

### Gate (fitted on calibration units only)

| | subject 1 | subject 2 |
|---|---|---|
| temperature T (val NLL) | 0.0500 | 0.0500 |
| COMMIT threshold (precision LTT, order 1000 / certify 2000 units) | none certified | none certified |
| first tested threshold: order wrong / commits; certify wrong / commits; certify p-value | 0.38: 0 / 3; 6 / 9; 1.0 | 0.43: 0 / 5; 0 / 5; 0.59 |
| largest certify p_top1 | 0.597 | 0.601 |
| conformal LAC threshold (3000 cal units, level 0.90) | 0.99394 | 0.99423 |

Fixed-sequence LTT stops at the first threshold that fails on the certify units. Both subjects fail at the first step. A 90 % precision target at delta 0.10 needs at least 22 error-free commits. The calibration units do not have enough high-confidence units for this.

### Controls on the test

| input (4000 units each) | subject 1 commits / mean set | subject 2 commits / mean set |
|---|---|---|
| real EEG | 0 / 45.12 (coverage 0.846) | 0 / 48.64 (coverage 0.890) |
| N1 trial-shuffled | 0 / 49.05 | 0 / 52.66 |
| N2 time-reversed | 0 / 46.99 | 0 / 47.09 |
| N3 spectrum-matched noise | 0 / 48.59 | 0 / 47.88 |
| R1 early (sessions 1-2, 2000) | 0 / 45.36 (coverage 0.832) | 0 / 48.54 (coverage 0.868) |
| R1 late (sessions 3-4, 2000) | 0 / 45.04 (coverage 0.856) | 0 / 48.86 (coverage 0.892) |

S0 (session reconstruction check, data only): subject 1 mean difference 0.0074, p = 1.2e-34; subject 2 0.0125, p = 7.2e-35. Both pass, so R1 ran.

### alpha = 0.05 (descriptive row, plan)

| | subject 1 | subject 2 |
|---|---|---|
| COMMIT threshold | none certified | none certified |
| commits | 0 / 4000 | 0 / 4000 |
| coverage / mean set | 0.915 / 68.17 | 0.954 / 75.95 |

## Deviations from the plan

1. **MIOpen off (implementation only, commit 5f51e28, recorded in the plan before any epoch).** The first launch (2026-11-27 17:04) stopped in the first forward pass. The MIOpen BatchNorm kernel does not compile on this ROCm build (`miopenStatusUnknownError`). The run sets `torch.backends.cudnn.enabled = False`, so PyTorch uses its native kernels. The model, loss, recipe, splits and rules did not change. No epoch had been trained and no data had been scored.
2. No other deviation. The runner stopped with exit code 4 after each gate fit, as designed. It scored the test units of a subject only after its gate file was committed and on `origin/main` (subject 1: gate commit 18:03, test scored 21:10; subject 2: gate commit 21:54:21, test scored 21:54:36).

## Compute

Measured from `a1.log` and `launcher.log` (wall clock of the GPU process, local RX 7800 XT):

| part | time |
|---|---|
| failed first launch (MIOpen) | 17:04:42 to before 17:10:20, at most 6 min |
| subject 1: train 40 epochs + score cal + gate | 17:10:20 to 17:54:09, 44 min |
| subject 1 test scoring, subject 2: train + score cal + gate | 21:10:40 to 21:53:43, 43 min |
| subject 2 test scoring, evaluation, summary | 21:54:23 to 21:54:37, 0.2 min |
| **total** | **about 1.56 GPU-h** (cap 6 h; estimate was 1-3 h) |

The pickle conversion and S0 ran on the CPU on 2026-11-24 (about 1 min in total).

## Post-hoc notes (not pre-registered; they do not change the outcome)

These checks used the calibration and test score files after the outcome was known. They are descriptive only.

1. **The temperature is at the search bound.** `TemperatureScaler` searches T in [0.05, 20]. The fitted T is 0.0500 on both subjects. An unconstrained search on the val units gives T = 0.031 (subject 1) and 0.033 (subject 2), with a lower val NLL (3.56 vs 3.76; 3.69 vs 3.85). So the posteriors are too flat at the bound.
2. **The bound did not cause outcome B.** With the unconstrained T, the certify units still have low precision at high confidence: subject 1 at p_top1 >= 0.7 has 20 commits with 11 wrong; subject 2 has 17 commits with 5 wrong. No threshold reaches 90 % precision with 22 or more commits. (Calibration units only; we did not score the test with this T.)
3. **OFFER could not happen.** The smallest test set has 14 images (subject 1) and 21 images (subject 2). The pre-registered OFFER limit is 10. At 4 trials per unit, a 90 % conformal set over 200 images is about 45-49 images.
4. **Coverage drops from cal to test on subject 1.** The nominal level is 0.90. Test coverage is 0.846 (subject 1) and 0.890 (subject 2). V2 (>= 0.80) passes, but subject 1 is 5 points below the nominal level. This agrees with the exchangeability caveat in the plan: cal concepts come from the training partition, test concepts from the test partition.
5. **Rule (iii) uses N1 only. Against N2 and N3, subject 2 fails.** One-sided Wilcoxon, real < null: subject 1 p = 7.2e-4 (N2) and 8.7e-16 (N3); subject 2 p = 1.0 (N2) and 1.0 (N3). For subject 2, the time-reversed and noise nulls give **smaller** mean sets (47.09, 47.88) than real EEG (48.64). So the "sets are informative" result is not robust on subject 2. A null with the same spectrum can give sets as tight as real EEG.
6. **R1 and R2 are vacuous.** They pass because there are no commits. They give no evidence about drift or category transfer.

> **Our take:** A1 is an honest "too weak to test" result, not a safety result. The gate behaved correctly: it refused to commit when calibration did not support 90 % precision, and it stayed silent on all nulls. But it never spoke, so we learn nothing about whether the bound transfers from training-partition concepts to new concepts. The main limit is the decoder signal per input (4 trials, 12-14 % top-1 over 200 images). A 200-way identity decision with a 90 % precision bound is far beyond that signal.

## What this means for the "beyond words" direction

- For **image identity** from EEG, a per-decision COMMIT is not reachable with this decoder at 4-trial units. This agrees with B1 (memory state, outcome C) in one way: weak non-invasive signals give the gate almost nothing to certify.
- The useful output at this signal level is a **set**, not a single image. Sets of about 45 of 200 images hold the true image about 85-89 % of the time. A useful product needs smaller sets (fewer candidates, more trials per unit, or a stronger decoder).
- The informativeness claim needs all three nulls. The subject 2 result shows that a spectrum-matched null can match real EEG on set size.

## Follow-up candidates (not part of A1; each needs its own plan)

1. **A1b: an easier decision.** Options to pre-register: more trials per unit (for example 20 or 80), a smaller gallery (for example 2-way or 10-way), or a coarser label (super-category). Each one makes commits possible and tests the transfer question that A1 could not test.
2. **Temperature search bound.** `T_MIN = 0.05` in `fidetype.trust.calibration` is too high for cosine-similarity logits. A later change should allow a lower bound (or fit a scale on the logits) and add a test. This is a library issue, not an A1 rule change.
3. **Rule (iii) with all nulls.** Future plans should require real < null for every null type, not only N1.
4. **Cal-to-test shift.** Measure coverage on test-partition-like calibration data (for example, hold out some test images for calibration) to separate concept shift from repetition-count effects.
5. Leave-one-subject-out and the NICE decoder stay out of scope (plan); they need all 10 subjects.

## Data and licence

THINGS-EEG2 (Gifford et al. 2022), CC BY 4.0. 63-channel 250 Hz re-preprocessing and CLIP ViT-H-14 features from Hugging Face `LidongYang/EEG_Image_decode` (CC BY 4.0). THINGS images were not used and are not in the repo. The model re-implements ATM-S (MIT, (c) 2023 DongyangLi). Only aggregates are committed: `summary.json` holds rates, counts, means and p-values per subject, with no per-trial, per-unit, per-image or per-cluster values.
