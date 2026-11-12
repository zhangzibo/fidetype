---
title: M1-09 async decoder on the full cache, result and async check
type: question
tags: [decoder, meg, spanishbcbl, asynchronous, ctc, evaluation, leakage, controls, trust, ewpm, conformal]
sources: [brain2qwerty-v2, brain2qwerty-v1]
updated: 2026-11-11
---

# M1-09 async decoder on the full cache

**Questions:** (1) Does the async ConvCTC decoder (M1-C recipe) reach the M1 target (≈ 0.59 greedy CER, v2's async SpanishBCBL number) on all 80 cached blocks? (2) Is the setting really async, and is it the same as v2's? (3) How much of the result comes from near-variant sentences? (4) Does a longer run help? (5) Does the trust layer give the same result on these async streams as on the sync M1-15 streams (Paper 1 gap G1)?

Full tables and the scripts: [experiment results](../../experiments/2026-11-11-m1-09-async-full/results.md). Earlier runs: [decoder M1 results](decoder-m1-results.md), [M1-15 full-r1 and r3](m1-15-full-r1-r3-result.md).

## Answer
1. **Yes.** Medium model (conv 320, model 256, 4 Conformer layers), test CER vs target: greedy **0.506** over sentences, **0.495** over the 19 participants. Beam + char LM (val-tuned): **0.475** / **0.462**. Shuffled MEG 0.760, zeros 0.925 (greedy). The small model gives 0.553 / 0.524.
2. **Yes at inference, with one training difference.** The model gets the MEG segment, its length and the participant index. It gets no key times. The segment runs from the first key press − 0.4 s to the last key press + 0.5 s. v2 uses the same bounds: "400 ms before sentence onset (first key pressed) through sentence offset (last key released)" plus 400–500 ms ([v2](../sources/brain2qwerty-v2.md), Methods 4.2, p. 12). The difference: our keystroke aux loss uses the key times as **training labels**. v2 trains with CTC only.
3. **A little.** On the 11 test sentences with no close train variant: greedy 0.519 (participants 0.508), beam + LM 0.492 (0.479). The effect on the headline is about 0.013 greedy and 0.017 beam CER.

4. **A longer run does not help (r5, M1-26).** Cosine over 200 epochs, trend stop at epoch 76 (best 55). Test greedy 0.516, beam + LM 0.484. r5 − r4b-full-medium, paired per sentence: greedy +0.009 [+0.003, +0.015], beam + LM +0.009 [+0.002, +0.016] on test; +0.003 [−0.004, +0.009] greedy on val. The headline model stays r4b-full-medium.

5. **Trust layer (G1): the same as sync.** Wrong-commit 0.997 → 0; trust 3.20 eWPM vs gaze only 3.155: parity (trust − gaze CI over sentences [−0.04, +0.15]). Trust commits nothing on any null input. CRC / LTT 0.0193 / 0.0214. See [Trust layer on the async streams](#trust-layer-on-the-async-streams-g1-2026-11-11).

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

## Trust layer on the async streams (G1, 2026-11-11)
Full tables: [G1 experiment](../../experiments/2026-11-11-g1-async-meg-trust/results.md). Same harness and settings as the sync M1-15 full-r1 run ([M1-15 full-r1](m1-15-full-r1-r3-result.md#trust-layer-ewpm-test)). CPU only.

eWPM on test [95 % CI: unique sentences (17) / participants (19) / two-way]:

| decoder | always commit | trust | gaze only | trust − gaze | wrong-commit commit → trust |
|---|---|---|---|---|---|
| **async M1-09** | 2.58 [2.41, 2.76] / [2.41, 2.79] | **3.20** [3.07, 3.36] / [3.08, 3.37] / [3.02, 3.43] | 3.155 [3.02, 3.29] | +0.05 [−0.04, +0.15] / [−0.07, +0.22] / [−0.11, +0.26] | 0.997 → 0 |
| sync M1-15 full-r1 | 2.71 [2.54, 2.90] / [2.54, 2.90] | 3.23 [3.08, 3.40] / [3.12, 3.37] / [3.04, 3.46] | 3.155 | +0.07 [−0.02, +0.18] / [−0.04, +0.22] / [−0.07, +0.26] | 1.000 → 0 |

- Trust − always commit (async): +0.62 [+0.49, +0.75] (sentences).
- Null audit (637 trials per input): always commit commits 100 % on real, shuffled-MEG, zeros-MEG, other-sentence, frame-shuffled and uniform input (85–100 % fluent). Trust commits 0 % on all. Guard-risk AUROC null vs real: shuffled 0.92, zeros and uniform 1.00, other sentence 0.49, frame-shuffled 0.47.
- CRC / LTT (n_cal 408, 200 splits): old gate 0, CRC 0.0193, LTT 0.0214, eWPM 3.199–3.204. Splits grouped by sentence or participant give the same means. Online `aci` 0.0188, `aci_window` 0.0078.
- True sentence in the 10-best: 1.6 % (sync 0.6 %). Trust is above gaze only for 10 of 19 participants (P15 4.32, P16 4.13).
- With a 40 cpm fallback or slow selection, gaze only is faster (6.31 vs 5.15; 3.15 vs 3.00).

> **Our take:** the async decoder keeps the safety result and the parity with gaze typing. On MEG the trust layer adds safety, not speed. Trial-level CIs made the sync result look like a small gain ([+0.03, +0.12]); the sentence-level CIs do not support it. Report sentence or two-way CIs for MEG.

## Caveats
- **17 unique test sentences only.** The CER CIs are over instances and do not include the variance across sentences. The trust section gives sentence, participant and two-way CIs.
- **Different test split from v2.** So "0.495 vs 0.59" is not a head-to-head result. We do not claim to beat v2.
- **Near variants:** the medium model gains more on the 6 "close" sentences (close 0.477, far 0.519) than the small model (0.549 vs 0.555). A larger model learns the templates more.
- **One seed.** The medium run stopped at its 100-epoch cap (best epoch 79). A longer run (r5: cosine over 200 epochs, same init) trend-stopped at epoch 76 with best val 0.4958 (r4b: 0.4944). It is not better: same on val, about 0.009 worse on test. The test CI ([+0.003, +0.015] greedy) excludes 0, but it is over instances of 17 sentences, so it is too narrow.
- WER is still high (0.84 greedy). The true sentence is almost never in the n-best (0.9 %).

> **Our take:** the jump from 0.619 (20 blocks) to 0.494 on the same instances comes from 4x data and a larger model, as v2's scaling result predicts ([v2](../sources/brain2qwerty-v2.md), Fig. 1F). Async now matches our synchronous decoder at greedy. The next gains for the trust layer need a better LM step (sentence n-best recall), not only a lower CER.

> **Our take (r5):** more epochs of the same model do not help. Both medium runs plateau at val CER about 0.495. The long cosine span kept the LR high (2.09e-04 at epoch 75), and the trend stop fired first. Next CER gains need more data, a model change, or ensembling over seeds and checkpoints.

## Related pages
- [Decoder M1 results](decoder-m1-results.md)
- [M2-13 conformal result](m2-13-conformal-result.md)
- [M2-16 online re-calibration result](m2-16-online-recal-result.md)
- [Paper 1 plan](paper1-plan.md)
- [M1-15 full-r1 and r3 result](m1-15-full-r1-r3-result.md)
- [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md)
- [Brain2Qwerty v2](../sources/brain2qwerty-v2.md)
- [Project plan](project-plan.md)
