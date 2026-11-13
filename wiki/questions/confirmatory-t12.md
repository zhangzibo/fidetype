---
title: "Confirmatory test of the Paper 1 frozen configuration on a second intracortical participant (T12)"
type: question
tags: [trust-core, confirmatory, pre-registration, intracortical, t12, ltt, guard, paper1]
sources: [brain-to-text-25-copytask]
updated: 2026-11-13
---

# Confirmatory test on participant T12

**Question:** Does the Paper 1 frozen configuration (tag `paper1-v4-frozen-config`: guard + LTT max, α 0.05, δ 0.1) keep the wrong-commit rate at or below α on later sessions of a second participant? Does it still refuse no-signal streams?

**Answer (2026-11-13): uninformative.** The configuration is safe, but it committed nothing, so the LTT bound was not tested. The cause is our weak T12 decoder.

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

Related: [B2T '25 trust result](b2t25-trust-result.md) · [Public datasets](public-datasets.md)
