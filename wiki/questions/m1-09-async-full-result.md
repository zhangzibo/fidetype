---
title: M1-09 async decoder on the full cache, result and async check
type: question
tags: [decoder, meg, spanishbcbl, asynchronous, ctc, evaluation, leakage, controls]
sources: [brain2qwerty-v2, brain2qwerty-v1]
updated: 2026-11-11
---

# M1-09 async decoder on the full cache

**Questions:** (1) Does the async ConvCTC decoder (M1-C recipe) reach the M1 target (≈ 0.59 greedy CER, v2's async SpanishBCBL number) on all 80 cached blocks? (2) Is the setting really async, and is it the same as v2's? (3) How much of the result comes from near-variant sentences?

Full tables and the scripts: [experiment results](../../experiments/2026-11-11-m1-09-async-full/results.md). Earlier runs: [decoder M1 results](decoder-m1-results.md), [M1-15 full-r1 and r3](m1-15-full-r1-r3-result.md).

## Answer
1. **Yes.** Medium model (conv 320, model 256, 4 Conformer layers), test CER vs target: greedy **0.506** over sentences, **0.495** over the 19 participants. Beam + char LM (val-tuned): **0.475** / **0.462**. Shuffled MEG 0.760, zeros 0.925 (greedy). The small model gives 0.553 / 0.524.
2. **Yes at inference, with one training difference.** The model gets the MEG segment, its length and the participant index. It gets no key times. The segment runs from the first key press − 0.4 s to the last key press + 0.5 s. v2 uses the same bounds: "400 ms before sentence onset (first key pressed) through sentence offset (last key released)" plus 400–500 ms ([v2](../sources/brain2qwerty-v2.md), Methods 4.2, p. 12). The difference: our keystroke aux loss uses the key times as **training labels**. v2 trains with CTC only.
3. **A little.** On the 11 test sentences with no close train variant: greedy 0.519 (participants 0.508), beam + LM 0.492 (0.479). The effect on the headline is about 0.013 greedy and 0.017 beam CER.

4. **A longer run does not help (r5, M1-26).** Cosine over 200 epochs, trend stop at epoch 76 (best 55). Test greedy 0.516, beam + LM 0.484. r5 − r4b-full-medium, paired per sentence: greedy +0.009 [+0.003, +0.015], beam + LM +0.009 [+0.002, +0.016] on test; +0.003 [−0.004, +0.009] greedy on val. The headline model stays r4b-full-medium.

**M1 status:** the criterion "greedy CER approaches v2's async SpanishBCBL CER (≈ 0.59) or is better" is met in the v2 async input setting. M1 is closed in the tracker on 2026-11-11.

## Main numbers (test, CER vs target)
| decoder | setting | greedy | beam + LM | shuffled gap (greedy) |
|---|---|---|---|---|
| v2 Encoder Async ([v2](../sources/brain2qwerty-v2.md), Fig. 1E) | async, 19 participants, own split | 0.59 ± 0.02 | — | — |
| M1-C r4b (+ M1-C2 beam) | async, 20 blocks, 209 instances | 0.619 | 0.590 | +0.156 |
| M1-09 small (r4b-full) | async, 80 blocks, 637 instances | 0.553 | 0.524 | +0.208 |
| **M1-09 medium (r4b-full-medium)** | async, 80 blocks, 637 instances | **0.506** | **0.475** | +0.254 [+0.241, +0.265] |
| M1-09 medium r5 (longer schedule, M1-26) | async, 80 blocks, 637 instances | 0.516 | 0.484 | +0.244 [+0.232, +0.256] |
| M1-09 medium, mean over participants | | 0.495 ± 0.020 (SEM) | 0.462 ± 0.022 | |
| M1-09 medium, far sentences only | async, 438 instances | 0.519 | 0.492 | +0.240 |
| M1-09 medium on the 209 M1-C instances | async | 0.494 | 0.461 | |
| M1-15 full-r1 (sync, oracle key times) | sync, 637 instances | 0.508 | 0.447 | +0.276 |

Means over sentences unless noted. Paired differences: medium − M1-C (same 209 instances) −0.125 [−0.142, −0.109] greedy, −0.130 beam. Medium async − full-r1 sync (same 637 instances): greedy −0.002 [−0.011, +0.007], beam + LM +0.028 [+0.016, +0.041].

Per participant (medium greedy): median 0.501, range 0.312–0.621. 17 of 19 participants are at or below 0.59.

## Async check
| input at inference | M1-09 | v2 async |
|---|---|---|
| MEG of the sentence segment | yes | yes |
| segment start | first key − 0.4 s | first key − 400 ms |
| segment end | last key press + 0.5 s | last key release + 400–500 ms |
| per-key times or key count | **no** | no |
| participant index (per-subject layer) | yes | yes |
| key times as training labels | **yes** (aux loss, r4a pretraining) | no |

The code path: `ConvCTC.forward(x, lengths, subjects)` has no key input. The key times reach only the training loss and a diagnostic (head accuracy at the true keys) that reads the output after the forward pass.

> **Our take:** both decoders take the sentence bounds from the keyboard log. So neither is a free-running, real-time decoder: that needs sentence onset detection as well. The inputs match. The training supervision does not. We count the M1 criterion as met, and we name the training difference with every v2 comparison.

## Caveats
- **17 unique test sentences only.** The CIs are over instances and do not include the variance across sentences.
- **Different test split from v2.** So "0.495 vs 0.59" is not a head-to-head result. We do not claim to beat v2.
- **Near variants:** the medium model gains more on the 6 "close" sentences (close 0.477, far 0.519) than the small model (0.549 vs 0.555). A larger model learns the templates more.
- **One seed.** The medium run stopped at its 100-epoch cap (best epoch 79). A longer run (r5: cosine over 200 epochs, same init) trend-stopped at epoch 76 with best val 0.4958 (r4b: 0.4944). It is not better: same on val, about 0.009 worse on test. The test CI ([+0.003, +0.015] greedy) excludes 0, but it is over instances of 17 sentences, so it is too narrow.
- WER is still high (0.84 greedy). The true sentence is almost never in the n-best (0.9 %).

> **Our take:** the jump from 0.619 (20 blocks) to 0.494 on the same instances comes from 4x data and a larger model, as v2's scaling result predicts ([v2](../sources/brain2qwerty-v2.md), Fig. 1F). Async now matches our synchronous decoder at greedy. The next gains for the trust layer need a better LM step (sentence n-best recall), not only a lower CER.

> **Our take (r5):** more epochs of the same model do not help. Both medium runs plateau at val CER about 0.495. The long cosine span kept the LR high (2.09e-04 at epoch 75), and the trend stop fired first. Next CER gains need more data, a model change, or ensembling over seeds and checkpoints.

## Related pages
- [Decoder M1 results](decoder-m1-results.md)
- [M1-15 full-r1 and r3 result](m1-15-full-r1-r3-result.md)
- [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md)
- [Brain2Qwerty v2](../sources/brain2qwerty-v2.md)
- [Project plan](project-plan.md)
