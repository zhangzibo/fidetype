---
title: M1-15 full-cache (full-r1) and causal (r3) result, with leakage checks
type: question
tags: [decoder, meg, spanishbcbl, sentence-context, evaluation, leakage, controls, trust, ewpm]
sources: [brain2qwerty-v1, brain2qwerty-v2]
updated: 2026-11-10
---

# M1-15 full-r1 and r3 result

**Questions:** (1) Does the sentence-context keystroke decoder improve with the full SpanishBCBL cache (full-r1)? (2) What does causality cost (r3)? (3) Are the numbers inflated by leakage or memorisation? (4) Is the M1 target met?

Full details, all tables and the scripts: [experiment results](../../experiments/2026-11-09-m1-15-sentence-context/results-full-r1-r3.md). Earlier runs: [decoder M1 results](decoder-m1-results.md#m1-15-r2-sentence-context-decoder-trained-to-the-val-plateau-2026-11-10).

## Answer
1. **Yes.** On the same 209 test instances as r2, full-r1 lowers greedy CER from 0.577 to **0.497** and beam + LM CER from 0.488 to **0.437**. On its full test set (637 instances, 19 participants): greedy **0.508**, beam + LM **0.447** (mean over sentences).
2. **Nothing measurable.** r3 (causal over keys) vs r2: greedy 0.574 vs 0.577, beam + LM 0.472 vs 0.488.
3. **No exact leakage, but some template memorisation.** 0 test or val sentences are in train. 0 are in the LM text. But 6 of the 17 test sentences have a close variant in train. That gives full-r1 about 0.013 greedy and 0.022 beam CER. On the 11 "far" test sentences: greedy **0.525**, beam + LM **0.474**.
4. **Only in the synchronous setting.** All M1-15 runs use oracle key times. The M1 target (≈ 0.59) refers to v2's asynchronous decoder. Our async decoder is still at 0.619 greedy. So **M1 is not closed** on the strict reading.

## Main numbers (test, CER vs target)
| decoder | setting | greedy | beam + LM | shuffled-MEG gap (greedy) |
|---|---|---|---|---|
| M2-10 logistic regression | sync, oracle timing, 20 blocks | 0.597 | 0.531 | ≈ +0.18 |
| M1-C r4b CTC (+ M1-C2 beam) | **async**, 20 blocks | 0.619 | 0.590 | +0.156 |
| M1-15 r2, Conv + Trans | sync, 20 blocks | 0.577 | 0.488 | +0.214 |
| M1-15 r3, Conv + Trans, causal | sync, 20 blocks | 0.574 | 0.472 | +0.214 |
| **M1-15 full-r1, Conv + Trans** | sync, 80 blocks, 637 instances | **0.508** | **0.447** | +0.276 |
| full-r1 on the r2 test instances | sync, 209 instances | 0.497 | 0.437 | — |
| full-r1, "far" test sentences only | sync, 438 instances | 0.525 | 0.474 | — |
| full-r1, Conv-only head | sync, 637 instances | 0.590 | 0.489 | +0.229 |
| v1 paper, Conv + Trans + LM ([v1](../sources/brain2qwerty-v1.md), Fig. 2) | sync | 0.36 (no LM) | 0.29 | — |

Means over sentences. The means over participants are 0.498 / 0.436 for full-r1 and 0.574 / 0.480 for r3. Do not compare a mean over participants with r2's 0.577 / 0.488 (a mean over sentences).

Controls (full-r1 test, greedy / beam + LM): shuffled MEG 0.784 / 0.741, zeros 0.808 / 0.755. All shuffled − real CIs exclude 0.

## Leakage checks
| check | result |
|---|---|
| Test or val sentence in train? | **No.** Split = SHA-1 hash of the normalised text; 0 split mismatches in the 80 sidecars; test ∩ train = val ∩ train = test ∩ val = 0 |
| Test sentence in the beam LM's text? | **No.** Tatoeba 6-gram char LM; all 226 SpanishBCBL targets removed by exact match and containment. Our re-check: 0 exact, 0 containment, 0 of 54 test word 4-grams |
| Same person in train and test? | Yes, by design (within-subject, as v1). Not leakage: sentences differ. See [repeated participants](spanishbcbl-repeated-participants.md) |
| Close variant of a test sentence in train? | **Yes, 6 of 17** (for example "las agencias disponen los equipos" in train, "... por la manana" in test). Effect about 0.013 greedy / 0.022 beam CER |
| Model copies train sentences? | No: 0 / 637 greedy and 1 / 637 beam outputs equal a train sentence |

How we measured the variant effect: the Conv-only head decodes each key alone, so it cannot use sentence templates. Its CER is only 0.012 lower on the 6 "close" sentences than on the 11 others. The Transformer head is 0.054 lower (r2: 0.022). The extra 0.042 on 199 of 637 instances is about 0.013 on the whole test set.

> **Our take:** The variant pairs are a property of the SpanishBCBL corpus, not a split bug. A split by sentence family would remove them, but it would change all past splits. Until then, report the "far" numbers next to the headline.

## Why zeros input gives CER about 0.8
The decoder knows the key times, so it outputs one character per key. The length is right, and chance matches on frequent characters (space, e, a, l, s) lower the CER. Text-only baselines on the same test instances:

| output (no MEG) | CER |
|---|---|
| "eeee…" | 0.888 |
| most frequent train character per position | 0.750 |
| one fixed train sentence, picked on train | **0.688** |
| zeros input, Transformer head | 0.808 |

So the no-signal floor is about 0.69, not 1.0. The MEG explains the step from about 0.69–0.78 down to 0.50, not the step from 1.0. See [error metrics](../concepts/error-metrics.md).

## Trust layer (eWPM, test)
| policy | r2 | full-r1 | r3 |
|---|---|---|---|
| always commit LM top-1 | 2.49 | 2.71 | 2.57 |
| trust (all four trust variants are equal) | 3.06 | **3.23** [3.08, 3.40] | 3.09 |
| OFFER_WORDS always | 2.95 | 3.11 | 2.97 |
| gaze typing only (no BCI) | 3.14 | **3.15** | 3.14 |

- full-r1 is the first decoder where trust is above gaze only. The CI contains 3.15, so it is parity, not a clear gain.
- Trust still removes all wrong commits (1.0 → 0) and is faster than always commit (+0.40 to +0.63).
- The true sentence is in the 10-best for fewer than 1 % of trials. The gain comes from word offers (31 % of the words).
- In the sensitivity runs, gaze only stays faster with a 40 cpm fallback (6.31 vs 5.15) and with slow selection (3.15 vs 2.99).

> **Our take:** With the full cache, the BCI reaches parity with gaze typing. A real gain needs the true sentence in the n-best for a real share of trials. More unique training sentences (not more repetitions of the same 101) is the most likely lever. The other is an async decoder on the full cache (M1-09), which M1 still needs.

## Per participant (full-r1 test, greedy)
P15 0.351 and P16 0.384 are best. P20 0.632, P12 0.608 and P05 0.591 are worst. 16 of 19 participants are below 0.59. The merged people (P01, P04, P05) have 2–3× the data but are not better. Full table: [experiment results](../../experiments/2026-11-09-m1-15-sentence-context/results-full-r1-r3.md#per-participant-full-r1-test-cer-vs-target-mean-over-that-persons-instances).

## Limits
- One seed per run.
- Oracle key timing in all M1-15 runs.
- 17 test and 11 val sentences. Instance-level CIs understate the sentence-level uncertainty. On the r2 val instances, the full-r1 beam + LM gain is +0.007 (CI crosses 0).

## Related pages
- [Decoder M1 results](decoder-m1-results.md)
- [SpanishBCBL repeated participants](spanishbcbl-repeated-participants.md)
- [SpanishBCBL dataset](../entities/spanishbcbl-dataset.md)
- [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md)
- [Error metrics](../concepts/error-metrics.md)
- [Trust core v0 results](trust-core-v0-results.md)
- [Project plan](project-plan.md)
