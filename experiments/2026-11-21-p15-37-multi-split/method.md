---
title: P15-37 Lower-variance calibration that keeps the LTT guarantee - method note
type: experiment
task: P15-37
updated: 2026-11-21
---

# P15-37 method note: which lower-variance calibration keeps the LTT guarantee?

Written before any number of P15-37 was computed. It is the theory step of [plan.md](plan.md). Gap 141 of the [open-gap list](../../wiki/questions/open-gaps.md).

## 1. The guarantee we must keep
`fidetype.trust.calibrate` with `confidence="learned"` does this (one split, `_split(n)`):

1. Fit the pipeline parts and the learned commit score `s` on the fit + policy-grid items (F, 451 of 722 on T15).
2. On the LTT items (L, 271), run Learn then Test (LTT): fixed-sequence test over the grid 1.00 → 0.00, exact binomial p-values. The result is the threshold `λ`.
3. The guard `g = (s, λ)` commits the top-1 text if `s(x) ≥ λ` and the commit gate passes.

Let `R(g)` = P(g commits a wrong text on a new utterance). Because `s` depends only on F, and the L items are i.i.d. and independent of F, LTT gives:

**(G)** P(R(g) > α) ≤ δ, over the calibration draw. (Angelopoulos, Bates, Candès, Jordan, Lei, "Learn then Test", arXiv 2110.01052.)

`safe-wpm/0.1` credits only this type of guarantee (`method: ltt`, alpha, delta; a high-probability, "training-conditional" statement). So a new method must give (G) with the same α = 0.05 and δ = 0.1, or a stronger statement. A guarantee "in expectation over the calibration draw" is weaker and does not count.

## 2. Candidate methods and their guarantees

| method | what it does | known guarantee | gives (G) at (0.05, 0.1)? |
|---|---|---|---|
| jackknife+ / full conformal | leave-one-out fits, aggregate | marginal coverage ≥ 1 − 2α (Barber et al. 2021, Ann. Stat.); **no** training-conditional guarantee without stability assumptions (Bian & Barber 2023, EJS) | no |
| cross-conformal / K-fold CV+ | K fold fits, aggregate | marginal ≥ 1 − 2α − small term; training-conditional: miscoverage ≤ 2α + √(2 log(K/δ)/m) with probability ≥ 1 − δ, m = fold size (Bian & Barber 2023) | no: with m ≈ 240, the extra term is about 0.17, more than α itself |
| conformal risk control (CRC), CV-CRC | threshold so that the expected loss ≤ α | E[R] ≤ α (marginal over the calibration draw) | no: expectation only, not (G) |
| multi-split conformal (Solari & Djordjilović 2022) | keep a point if it is in at least a fraction τ of B split sets | marginal coverage via Markov's inequality, with an inflated per-split level | no: marginal; and the inflation costs about as much as Bonferroni |
| majority vote of sets (Gasparin & Ramdas 2024) | merge K sets by vote | ≥ 1 − 2α (marginal) | no |
| p-value merging over splits (Vovk & Wang 2020: 2 × mean, 2 × median) | merge the LTT p-values of K splits | valid for **one** null hypothesis | no: each split tests a **different** hypothesis (its own score `s_j`), so the p-values have no common null |
| pooled cross-fit LTT (each fold scored by a model fitted on the other folds, one LTT on all 722) | more LTT items | none known: the pooled scores come from K different functions, and each deployed function has seen the other folds | no (we must not ship it) |
| **multi-split, Bonferroni, any selection** | J splits, LTT at δ/J each, deploy one guard chosen by any rule | union bound (below) | **yes** |
| **multi-split unanimity (AND)** | J splits, LTT at δ each, commit only if all J guards commit the same text | pointwise domination (below) | **yes** |

So the known lower-variance methods (cross-fitting, jackknife+, CV+, CRC) do not give (G) at our α. Their training-conditional bounds have a factor 2 on α, or a √(log/m) term that is larger than α at our sample size. Only two multi-split constructions keep (G) exactly. Both are elementary.

## 3. The two valid constructions

Let `g_1, ..., g_J` be the guards of J splits of the same calibration sample. The splits are random partitions that do not depend on the labels or the scores (they may depend on the multiplicity of an item in a resampled set, see plan.md). Each `g_j` is a full `calibrate` run, so each satisfies (G) at its own (α, δ_j). The splits share data, so the `g_j` are dependent. Neither argument below needs independence.

**(A) Unanimity (AND), each split at (α, δ).** `g_∧` commits text t on x only if every `g_j` commits t on x. Otherwise it does not commit.
- Pointwise: if `g_∧` commits a wrong text on x, then `g_1` commits the same wrong text on x. So `1{g_∧ wrong commit on x} ≤ 1{g_1 wrong commit on x}` for every x, and `R(g_∧) ≤ R(g_1)`. (The same holds for every j, so `R(g_∧) ≤ min_j R(g_j)`.)
- So P(R(g_∧) > α) ≤ P(R(g_1) > α) ≤ δ. **(G) holds at (α, δ), with no correction.**
- Cost: `g_∧` commits less than any `g_j`. Expected gain: `g_∧` is unsafe only if all J guards are unsafe together, so the rare unsafe draws (the zeros of P15-29) should become rarer, and the split noise is cut from the top.

**(B) Bonferroni and selection, each split at (α, δ/J).** Deploy `g_ĵ`, where ĵ is any function of the calibration data (for example the guard with the highest in-sample safe WPM on its own LTT items, or the median one).
- Event E = {R(g_j) ≤ α for all j}. Union bound: P(not E) ≤ Σ_j δ/J = δ.
- On E, every `g_j` is safe, so `g_ĵ` is safe whatever ĵ is. So P(R(g_ĵ) > α) ≤ δ. **(G) holds at (α, δ).**
- Cost: each guard is certified at δ/J (a stricter test). Expected gain: choosing among J guards removes part of the split noise.

**Null controls.** They are an extra rule, not part of (G). The deployed guard (`g_∧` or `g_ĵ`) must pass the uniform and shuffled controls (at most 15 of 300 commits), counted on the deployed guard's own decisions.

**Not claimed.** Neither construction reduces the part of the between-draw spread that comes from the calibration sample itself (all J splits see the same 722 items). They can only remove the part that comes from the split and from rare unsafe draws. P15-29 / P15-26 suggest that the split part is about a third of the between-draw variance (split-only SD 0.44 against 0.79 with resampling). So a large gain is not expected.

## 4. Choice
- We use only (A) and (B). Both keep (G) exactly at (0.05, 0.1), so a draw of either method is scored by the unchanged `safe-wpm/0.1` rules and the P15-29 credit rule.
- The plan picks one primary arm from {AND-2, AND-3, AND-4, BMAX-2, BMAX-3, BMED-3} by a stage S on `val_select` only. The others are computed on the same draws as descriptive arms (they share the guards, so they cost little).
- We do **not** ship cross-fitting, jackknife+, CV+, CRC or pooled cross-fit LTT: we cannot argue (G) for them at α = 0.05 with 722 items.

## References
- A. N. Angelopoulos, S. Bates, E. J. Candès, M. I. Jordan, L. Lei. Learn then Test: calibrating predictive algorithms to achieve risk control. arXiv:2110.01052.
- R. F. Barber, E. J. Candès, A. Ramdas, R. J. Tibshirani. Predictive inference with the jackknife+. Ann. Statist. 49(1), 2021. https://arxiv.org/abs/1905.02928
- M. Bian, R. F. Barber. Training-conditional coverage for distribution-free predictive inference. Electron. J. Statist. 17(2), 2023. https://arxiv.org/abs/2205.03647
- A. Solari, V. Djordjilović. Multi split conformal prediction. Stat. Probab. Lett., 2022. https://arxiv.org/abs/2103.00627
- M. Gasparin, A. Ramdas. Merging uncertainty sets via majority vote. arXiv:2401.09379.
- V. Vovk, R. Wang. Combining p-values via averaging. Biometrika 107(4), 2020.
- A. N. Angelopoulos, S. Bates, A. Fisch, L. Lei, T. Schuster. Conformal risk control. ICLR 2024.
