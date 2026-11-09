---
title: Error metrics for brain-to-text (HER, CER, WER, SemER)
type: concept
tags: [evaluation, metrics]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-08
---

# Error metrics

| Metric | Definition | Used in |
|---|---|---|
| **HER**: hand error rate | How often the predicted key is on the wrong half of the keyboard. Left-hand keys are those left of Y/H/B. Space, digits and special characters are excluded. | [v1](../sources/brain2qwerty-v1.md) |
| **CER**: character error rate | Levenshtein distance (substitutions + deletions + insertions) divided by the number of target characters. Computed per sentence, averaged within each subject, then averaged across subjects. | v1 (headline metric), [v2](../sources/brain2qwerty-v2.md) |
| **WER**: word error rate | The same edit distance at word level, after splitting on whitespace. | v2 (headline metric) |
| **SemER**: semantic error rate | L2 distance between the L2-normalised, mean-pooled RoBERTa-large embeddings of the prediction and the target. | v2 |

## Notes
- **Metric choice changes the ranking.** In v2, CTC + n-gram has the best CER (0.26), while the NeuroLLM has the best WER (0.39) and SemER (0.059). An LLM can produce a fluent sentence with a different meaning, which costs a lot of CER without improving WER or SemER. Which metric matters depends on the use: exact characters for a password, meaning for a conversation ([v2](../sources/brain2qwerty-v2.md), Discussion).
- **Chance level** for CER in v1 is a model that always predicts the most frequent character.
- **Implementation quirk**: v1's *training-time* CER is computed per batch, not per sentence. The offline scripts compute it per sentence ([code](../sources/brain2qwerty-code.md)).
- **Missing from both papers**: neither reports information transfer rate or characters/words per minute in a closed-loop setting. Both evaluate offline only.

## Control conditions

A CER alone does not show that a model decodes the brain signal. A strong text prior can give a CER well below 1.0 with no neural input. So we report every CER next to two controls. The same trained model decodes each input.

| Input | What it is | What it measures |
|---|---|---|
| **Real** | The MEG of the trial | Decoder performance |
| **Shuffled** | The MEG of another trial in the same split | The text prior plus generic signal statistics (for example, segment length) |
| **Zeros** | A flat (all-zero) input of the same length | The text prior alone, with no signal |

- A model decodes the signal only if the real-input CER is clearly **below** the shuffled-input CER.
- If real equals shuffled, the CER comes from the text prior. Example: our first M1 decoder got test CER 0.671 (real), 0.669 (shuffled) and 0.858 (zeros) ([decoder M1 results](../questions/decoder-m1-results.md)).
- Our M1-C decoder with a keystroke auxiliary loss passes this test: test CER 0.619 (real), 0.776 (shuffled), 1.000 (zeros) ([decoder M1 results](../questions/decoder-m1-results.md#ctc-decoder--keystroke-auxiliary-loss-m1-c-2026-11-08)).
- This is the same test as the null-input audit of the trust layer ([trust core v0 results](../questions/trust-core-v0-results.md#null-input-audit-median-t--10)). There, the trust policy must not commit text for shuffled or flat input.

## Usefulness metrics: a no-BCI baseline
Error rates do not show if a BCI saves the user time. We report effective WPM (eWPM) and the keystroke saving rate (KSR = 1 − fallback keystrokes / target characters, as in Cai et al. 2024). We compare them with a **no-BCI baseline**: the same user types with the fallback method alone (for example, a gaze keyboard). On real MEG (2026-11-08), every BCI policy was below gaze typing alone (trust 2.96 vs gaze 3.14 eWPM) ([trust core v0 results](../questions/trust-core-v0-results.md#7-per-word-offer-and-partial-correction-2026-11-08)).

> **Our take:** Any work of ours should report all three (CER, WER, SemER). It should also add a **latency or streaming metric** once decoding becomes causal. It should always report the shuffled-input control next to CER.

Related: [NeuroLLM](neuro-llm.md) · [CTC](ctc.md)
