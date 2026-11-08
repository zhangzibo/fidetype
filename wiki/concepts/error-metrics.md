---
title: Error metrics for brain-to-text (HER, CER, WER, SemER)
type: concept
tags: [evaluation, metrics]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-07
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

> **Our take:** Any work of ours should report all three (CER, WER, SemER). It should also add a **latency or streaming metric** once decoding becomes causal.

Related: [NeuroLLM](neuro-llm.md) · [CTC](ctc.md)
