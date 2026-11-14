---
title: "Confirmatory test of the Paper 1 frozen configuration on a second intracortical participant (T12)"
type: question
tags: [trust-core, confirmatory, pre-registration, intracortical, t12, ltt, guard, paper1, commit-gate]
sources: [brain-to-text-25-copytask]
updated: 2026-11-13
---

# Confirmatory test on participant T12

**Question:** Does the Paper 1 frozen configuration (tag `paper1-v4-frozen-config`: guard + LTT max, α 0.05, δ 0.1) keep the wrong-commit rate at or below α on later sessions of a second participant? Does it still refuse no-signal streams?

**Answer (2026-11-13, two pre-registered runs): uninformative both times.** The configuration stayed safe, but it committed nothing (v1) or 1 of 400 trials (v2), so the LTT bound was not tested. v1 failed on a weak decoder. v2 had a much better decoder (test PER 0.27), but the word LM still gave few right sentences, and the frozen recipe chose a strict guard limit. A validation dry run before v2 showed that the same recipe **can** commit on no-signal streams (see [v2](#v2-m3-28-stronger-decoder)).

## Method
- Pre-registration: [`experiments/2026-11-13-confirmatory-t12/PROTOCOL.md`](../../experiments/2026-11-13-confirmatory-t12/PROTOCOL.md), commit `a7cf624`, pushed before any decoding.
- Data: Willett et al. 2023 (T12), Brain-to-Text '24 `competitionData`, CC0 (Zenodo copy of the Dryad record). 24 sessions.
- Decoder: our own causal GRU-CTC, trained on the earlier blocks of each session. Then the unchanged B2T '25 phoneme-to-word route (see [B2T '25 result](b2t25-trust-result.md)).
- Trust pool = the last block of each session. Fit-A = sessions 1-8 (240 trials), calibration = sessions 9-14 (240), test = sessions 15-24 (400). Fit-A < calibration < test in time.

## Results
| item | value |
|---|---|
| Decoder, test sessions | greedy PER 0.542, WER 0.751, right sentence first 3/400 |
| Wrong-commit (LTT max) | 0/400, CP95 [0.000, 0.009] |
| Commit rate | 0/400 |
| Sessions above α | 0 of 10 |
| Controls (frame-shuffled, uniform) | 0/400 commits each |
| Guard AUROC (wrong top-1) | 0.966 |
| eWPM | 4.58, against 4.11 for gaze typing alone |
| Criteria C1 / C2 / C3 | pass / pass / pass; no commits → "uninformative" |

Details and deviations: [`results.md`](../../experiments/2026-11-13-confirmatory-t12/results.md). Tables: [`results/tables.md`](../../experiments/2026-11-13-confirmatory-t12/results/tables.md).

> **Our take:** This is a decoder failure, not a trust-layer failure. The safe behaviour with almost no right sentences is to commit nothing, and the layer did that. The Paper 1 commit-rule claim still rests on one participant (T15). An informative test needs a T12 decoder that gets the right sentence first for a fair share of trials (T15: 39 %). That needs better normalisation, a larger model or a better word LM. The test sessions have now been decoded once, so a second attempt needs a new pre-registration (v2) that says so.

## Deviations (short)
1. The learning rate changed from 2e-3 to 5e-4 after a CTC collapse in run 1. The protocol allows this on validation PER only.
2. MIOpen GRU backward fails on this ROCm build, so the 5 layers are separate GRUs with dropout between them, and MIOpen is off.
3. The input smoothing is causal.
4. Small code fixes before the test run (dry-run mode only), and one print fix after it. No number changed.

## v2 (M3-28): stronger decoder
- Pre-registration: [`experiments/2026-11-13-confirmatory-t12-v2/preregistration.md`](../../experiments/2026-11-13-confirmatory-t12-v2/preregistration.md), commit `f9741df`, pushed before the v2 decoder decoded any trust-pool trial. It states that v1 had already decoded the same test sessions once (aggregate results only).
- Same data, splits, frozen configuration and criteria C1-C3. New: an informative condition (at least 21 of 400 test commits, the smallest number for which C1 can fail).
- Decoder changes (chosen on validation only): causal rolling normalisation over the 20 previous trials, GRU 5 × 1024, patch 32; a Tatoeba word-trigram term in the sentence LM (β 2.0).

| item | v1 (M3-27) | v2 (M3-28) |
|---|---|---|
| validation greedy PER | 0.470 | 0.293 |
| test greedy PER / WER | 0.542 / 0.751 | 0.269 / 0.387 |
| right sentence first (test) | 3/400 | 31/400 |
| fitted `commit_max_risk` / LTT λ̂ | — / 0.00 | 0.1 / 0.00 |
| test commits (wrong) | 0 (0) | 1 (0) |
| controls frame-shuffled / uniform | 0/400 / 0/400 | 0/400 / 0/400 |
| guard AUROC (test) | 0.966 | 0.792 |
| eWPM vs gaze typing alone | 4.58 vs 4.11 | 7.14 vs 4.11 |
| outcome | uninformative | uninformative |

**Validation dry run (before the v2 pre-registration).** On decoder-validation blocks the same recipe chose `commit_max_risk` 1.0, committed 22 of 400 "test" trials (11 wrong, wrong-commit 0.0275) and committed **335 of 400 uniform-control streams** (320 of them with an empty text). The pre-registration predicted a C3 failure from this. On the trust pool the recipe chose 0.1 instead, and nothing was committed. Details: [`results.md`](../../experiments/2026-11-13-confirmatory-t12-v2/results.md).

> **Our take:** Two findings matter for Paper 1. (1) The frozen recipe is not stable on 240-trial fit sets: one grid value decides between "commits nothing" and "fails the no-signal control". (2) The frozen configuration can commit an empty or very short text on no-signal input; a later configuration needs an explicit rule against this. The commit-rule claim still rests on T15 only. The next informative T12 test needs a much stronger licence-clean word LM, or more calibration and test trials.

## Why the empty commits happened (M2-18)
Experiment: [2026-11-13-m2-18-empty-commits](../../experiments/2026-11-13-m2-18-empty-commits/results.md).

- **The pre-registration guess ("an empty candidate gets guard risk 0") was wrong.** The guard gives an empty top-1 risk **1.0**. All 320 empty uniform top-1 texts had risk 1.0, and so did the 15 non-empty uniform commits.
- The cause is the grid value `commit_max_risk = 1.0`. COMMIT needs `guard_risk <= commit_max_risk`; at 1.0 this is always true, so the guard limit is off. The word decoder returns only the empty text for most uniform streams (242 of 320 with a one-candidate list), so `p_top1` is 1.0 (median) and passes the commit threshold 0.3.
- **Trust pool:** the decoder also returned 304 empty top-1 texts (risk 1.0) on the uniform controls. Only the fitted limit 0.1 blocked them (risk 1.0 > 0.1); no other rule did. With 1.0 the same inputs give 321 commits (304 empty).
- **Fix (opt-in):** the commit gate ([streaming trust layer](../concepts/streaming-trust-layer.md#commit-gate-m2-18-opt-in)). Dry-run uniform commits: v4 335 -> gate A (no empty text) 15 -> gate B (also guard risk < 1) **0**; frame-shuffled 6 -> 3 (0.75 %, below the 1 % C3 limit); test rows unchanged (22 commits, 11 wrong).
- **Paper 1 (T15): no number changes.** All Paper 1 fits chose `commit_max_risk` <= 0.5, the refits reproduce Tab. 1 exactly, and no T15 trial has an empty top-1 in 35,816 cached n-best lists. Erratum candidate (wording only): "the guard stopped this" holds for the reported fits, not for every fit of the frozen recipe. **Applied in Paper 1 v6 (2026-11-13):** the wording is fixed, and Limitation 1 plus Supplementary Section S24 report both T12 tests as uninformative ([Paper 1 plan](paper1-plan.md)).

### Stability finding
One discrete grid value switches the frozen recipe between "commits nothing" and "commits on no-signal input". On 240-trial T12 fit sets it chose 1.0 (validation blocks) and 0.1 (trust pool). On T15 random re-splits it chose 1.0 in 53 of 200 splits (our decoder) and 65 of 200 (published gate). The grid fit sees only real trials, so it cannot detect the no-signal case.

> **Our take (v5 suggestion, not applied):** (1) commit gate B on by default; or drop 1.0 from the `commit_max_risk` grid; (2) a control-aware grid fit: a grid point is feasible only if it commits at most 1 % of uniform and frame-shuffled versions of the fit-A streams (no labels needed); (3) report how often each grid value wins on bootstrap resamples of fit-A, and prefer the more conservative value on near-ties. Keep `PAPER1_V4_RECIPE` and its tag unchanged.

Related: [B2T '25 trust result](b2t25-trust-result.md) · [Public datasets](public-datasets.md)

## Related pages
- [Trust-core ablations](trust-core-ablations.md): the monitor and commit gate B as ablation arms on Paper 1 data (M3-02).
