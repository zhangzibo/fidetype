---
title: NeuroLLM (LLM conditioned on brain tokens)
type: concept
tags: [llm, architecture, alignment, contrastive]
sources: [brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-07
---

# NeuroLLM

A NeuroLLM is a pretrained LLM, fine-tuned with LoRA, that generates the target sentence while conditioned on **text decoded from the brain** together with **brain-derived embeddings placed directly in the LLM's token space**. Brain2Qwerty v2 is the example ([paper](../sources/brain2qwerty-v2.md)).

## How v2 builds the tokens (the "CTC tokenizer")
1. The [CTC](ctc.md) encoder frames are split wherever greedy CTC emits a *space*. Each chunk becomes one "MEG word".
2. Each chunk passes through a 2-layer MLP and is mean-pooled, then a linear projection maps it to the LLM's hidden size.
3. These MEG words are aligned to the LLM's (non-contextual) **input embeddings** of the true words. Training uses a **SigLIP** loss, and **hard DTW** pairs predicted words with true ones when their counts differ. Repeated words are labelled as duplicate positives.
4. The prompt has the form `CTC: <decoded text> \nMEG: <MEG word embeddings> \nOutput:`.
5. The LLM is trained with cross-entropy and label smoothing 0.02. **Modality dropout** (rate 0.1 on both streams) forces it to use each input stream.

## Does the LLM actually read the brain tokens?
Yes. With the MEG tokens removed, every metric gets worse: WER goes from 0.43 to 0.49 and CER from 0.34 to 0.38, using Qwen3-0.6B ([v2](../sources/brain2qwerty-v2.md), Fig. S4). The authors summarise it this way: "the CTC text anchors the LLM to a plausible linguistic prior, while the MEG tokens carry the residual neural information".

## Tokenization comparison (Fig. 4A)
| Tokenization | WER |
|---|---|
| CTC tokenizer | 0.39 |
| One embedding per sentence | 0.46 |
| Fixed patches | 0.49 |

## Trade-off and failure mode
The NeuroLLM has the best WER and SemER but a *worse CER* (0.31) than CTC + n-gram (0.26). When the signal is weak it **hallucinates fluent but wrong sentences**. See [error metrics](error-metrics.md).

> **Our take:** Possible directions include confidence or abstention ("I'm not sure, here are 3 candidates"), constrained decoding that stays close to the CTC lattice, or letting the user pick from an n-best list. All of these are cheap to try and matter a lot for a real user.

Related: [Model soup](model-soup.md) · [CTC](ctc.md) · [Auto Research](auto-research.md)
