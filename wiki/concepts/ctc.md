---
title: Connectionist Temporal Classification (CTC)
type: concept
tags: [loss, sequence, asynchronous]
sources: [brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-07
---

# CTC (Connectionist Temporal Classification)

CTC (Graves et al. 2006) is a loss function for learning to map a long input sequence onto a shorter label sequence **without frame-level alignment**. Speech recognition uses it widely. The model emits one distribution per frame over the labels plus a special *blank* symbol. Training then sums over every alignment that collapses to the target string. Decoding can be greedy (take the argmax, merge repeats, drop blanks) or a beam search, optionally combined with a language model.

## In Brain2Qwerty v2 ([paper](../sources/brain2qwerty-v2.md), [code](../sources/brain2qwerty-code.md))
- **Vocabulary**: 28 classes, made up of blank (0), a–z (1–26) and space (27). In the code, space is written `&`.
- **Frame rate**: about 1 frame per 40 ms, after a stride-4 convolution on 100 Hz data.
- **Loss**: `L = 0.3·CTC(final) + 0.7·CTC(aux)`. The auxiliary head sits after the conv encoder and is fed back as intermediate conditioning, following Nozaki & Komatsu 2021.
- **Downstream use**: the greedy CTC *space* predictions also segment the frames into words. This is the "CTC tokenizer" behind the [NeuroLLM](neuro-llm.md). Spaces make up about 19% of characters and are predicted reliably, so 86% of sentences get a word count within ±1 of the truth.
- **With a language model**: CTC plus a 6-gram character KenLM (beam 50, LM weight 2.0) is still the best decoder on **CER**, at 0.26.

Related: [Synchronous vs asynchronous decoding](synchronous-vs-asynchronous-decoding.md) · [NeuroLLM](neuro-llm.md)
