---
title: "Confidence-ordering reversal under contextual priors in neural decoding (Zhang & Liu 2026)"
type: source
tags: [meg, speech, retrieval, language-model, fusion, confidence, selective-prediction, f2, novelty-check]
sources: [confidence-ordering-reversal]
updated: 2026-11-24
---

# Confidence-ordering reversal (Zhang & Liu 2026)

## Citation and links
- X. Zhang, S. Liu. "Confidence-Ordering Reversal under Contextual Priors in Neural Decoding." arXiv:2610.08229 (v1, 2026-10-06, cs.AI), preprint. https://arxiv.org/abs/2610.08229 . Code: github.com/AmadeusFake/NeuDecodingConfReversal.
- **Licence:** CC BY 4.0 (arXiv licence link).
- **Local raw path:** `references/papers/zhang_liu_2026_confidence_ordering_reversal_arxiv_2610.08229v1.pdf` (28 pages, SHA-256 `434cac2b58145b6af7e0f428731d4460e05d21e01eb25ab0de63d6ce137f1490`) + `.txt`. Downloaded 2026-11-24. Git-ignored.

## TL;DR
When a contextual prior (a language model or a history prior) is fused with a neural decoder, the fused confidence can rank **residual errors above real repairs**. The reversal is strongest when the true candidate started deep in the decoder's ranking. Reading the local (neural) score and the prior score separately gives a better selective decoder.

## Key facts
| Item | Value | Where |
|---|---|---|
| Task | offline MEG speech retrieval, MEG-MASC (27 people) and MOUS (96 people); 3-s word windows; wav2vec2 audio targets | Abstract; §3 |
| Candidate pool | MEG-MASC: 71,736 test windows, 1,464 audio candidates; MOUS: 825 candidates | §3 |
| Reversal | pooled AUROC 0.87, but AUROC repairs vs residual errors "falls from 0.70 at initial ranks 2-3 to 0.39 at ranks 21-50" (MEG-MASC; MOUS 0.62 → 0.41) | Abstract; §4.1 |
| Size of the problem | errors starting beyond rank 20 "make up 46.6% of all post-fusion errors" | Abstract; appendix |
| Fix | separate local and prior scores: the decoder "answers on 74.5% of windows instead of 56.7%" while "92% of output sets still contain the correct candidate" (coverage matched on the test curve, 92.24 %) | Abstract; §4.3; Table 2(b) |
| Guarantee | none. "validation constraints are not guaranteed on test" | Appendix I |

## Limitations (stated)
- Offline retrieval over a fixed candidate pool. No generated text. Thresholds picked on validation, no finite-sample guarantee.
- The authors name BCI spellers as a future test.

## Why it matters for us
- Direct evidence for **F2**: LM fusion makes residual errors look confident. A commit rule that uses only the fused score can be fooled.
- It supports a choice that `commit_score.py` already makes: it keeps acoustic and LM features apart (`acoustic_per_char`, `acoustic_gap`, `lm_per_word`).

> **Our take:** we have not tested our learned commit score for this reversal. A cheap CPU diagnostic: AUROC of the commit score for "the LM changed top-1 and was right" vs "residual error", split by the acoustic rank of the true text.

## Feeds
- [E3 hallucination write-up](../questions/frontier-e3-hallucination.md)
- [Probabilistic Co-Control](probabilistic-co-control.md)
- [NeuroLLM](../concepts/neuro-llm.md), [MEG](../concepts/meg.md)
