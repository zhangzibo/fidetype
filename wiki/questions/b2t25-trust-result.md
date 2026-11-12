---
title: "Trust layer on a second device type: Brain-to-Text '25 (intracortical speech)"
type: question
tags: [trust-core, cross-device, intracortical, phoneme, ctc, ewpm, calibration, neuraltextstream, adapter]
sources: [brain-to-text-25-copytask]
updated: 2026-11-10
---

# Trust layer on intracortical speech (Brain-to-Text '25)

**Question:** Do the NeuralTextStream spec and the trust core work on a second device type, with real, licence-clean decoder output? Does trust help there?

**Answer in short:** Yes. A new adapter turns the T15 phoneme CTC logits into valid NTS streams (`vocab_type="phoneme"`). The trust core runs on them with no change except one optional field. Unlike real MEG, the test is not degenerate: the right sentence is often the top-1. The trust policy cuts wrong commits 4–10× at 0–4 % speed cost, and every BCI policy is far faster than gaze typing alone. Data and method: [source page](../sources/brain-to-text-25-copytask.md), [experiment](../../experiments/2026-11-10-b2t25-trust/results.md).

## Results (test, 816 trials, 14 days)
| policy | eWPM [95 % CI, trials] | wrong-commit | silent error |
|---|---|---|---|
| always commit our top-1 (WER 0.149) | 11.45 [10.95, 12.04] | 0.610 | 0.044 |
| **trust** on our n-best | 11.55 [11.03, 12.06] | **0.059** | 0.002 |
| always commit the published sentence (WER 0.043) | 19.61 [18.68, 20.51] | 0.194 | 0.025 |
| **trust gate** on the published sentence | 18.77 [17.88, 19.62] | **0.044** | 0.004 |
| gaze typing only (no BCI) | 4.08 [4.04, 4.12] | 0 | 0 |

([experiment](../../experiments/2026-11-10-b2t25-trust/results.md), "Trust harness, word level")

- Paired: trust − commit (ours) eWPM [−0.11, +0.30]; wrong-commit [−0.59, −0.52]. Published gate − published commit: eWPM [−0.98, −0.72] (−4.3 %), wrong-commit [−0.18, −0.13].
- Confidence predicts errors: AUROC "top-1 sentence wrong" for −p_top1 is 0.797 (word level) and 0.884 (phoneme level). The guard risk is lower (0.702 / 0.825). Per word, the acoustic word confidence gives AUROC 0.844 for "word wrong". Our signals predict errors of the published sentence less well (AUROC 0.66).
- Calibration: the logits are over-confident (frame T 3.78). Sentence ECE 0.448 → 0.067.
- Null input: frame-shuffled and uniform streams → trust commits 0 %, always commit 100 %. A real stream of **another** sentence → trust on our decoder commits 22 % (as for real input: the stream cannot know intent); the published gate commits 0 %.
- Published WER: the file gives 0.0434 pooled over all 1,718 trials and 0.0044 on day 25 (50 words). The paper says "99.6% accuracy with a 50-word vocabulary" and "sustained 97.5% accuracy over a period of 8.4 months" ([source](../sources/brain-to-text-25-copytask.md)).

## Comparison with real MEG
| | real MEG ([M2-10](trust-core-v0-results.md#6-real-meg-first-test-2026-11-08), [M2-14](trust-core-v0-results.md#7-per-word-offer-and-partial-correction-2026-11-08)) | intracortical speech |
|---|---|---|
| truth is top-1 | 0 % | 39 % (ours), 81 % (published) |
| trust vs gaze only | 2.96–3.06 vs 3.14 eWPM (BCI loses) | 11.55 / 18.77 vs 4.08 (BCI wins) |
| best error signal | low evidence | −p_top1 |

> **Our take:** This is the first evidence that the trust layer can **pass correct commits and stop wrong ones** on real data, not only refuse everything. The spec held up on a new token type (phonemes) and a new modality (intracortical) with no breaking change. The harness needed one optional field (`Item.stream_text`), because the truth in the stream's token space (phonemes) differs from the truth the user sees (words).

> **Our take:** The published-gate result is the most product-relevant one. A strong LM-rescored decoder (WER 4 %) still commits a wrong sentence 19 % of the time. Gating its text by agreement with the raw neural evidence keeps 96 % of the speed and cuts wrong commits to 4 %, and it rejects the text when the neural stream belongs to another sentence. This is a decoder-agnostic use of NTS: the gate needs only the stream and the text.

> **Our take:** The wrong-commit limit (0.05) was met only approximately on test (0.059). A finite-sample method (conformal risk control, M2-13) is now worth doing, because real data finally gives non-trivial commit rates.

**Update 2026-11-11 (M2-13):** with conformal risk control on per-session calibration data, the mean test wrong-commit is 0.046–0.048 (both decoders), at ≤ 0.4 % eWPM cost. See [M2-13 result](m2-13-conformal-result.md).

## Open questions
- Does the result hold for the conversation-mode data (user ratings, no text)?
- Can a real word LM (not our char 6-gram + unigram) close the gap from WER 0.149 to 0.043 with licence-clean parts?
- Next device: wrist sEMG (KT-sEMG, CC BY 4.0), see the [datasets survey](public-datasets.md).

Related: [Brain-to-Text '25](../entities/brain-to-text-25.md) · [Provenance ledger](../concepts/provenance-ledger.md) (M2-09 audit demo on this replay) · [Trust core v0 results](trust-core-v0-results.md) · [Public datasets](public-datasets.md) · [CTC](../concepts/ctc.md)

> **Update 2026-11-11:** the third device type (forearm sEMG) gave the same pattern: see [EMG Toronto trust result](emg-toronto-trust-result.md).
