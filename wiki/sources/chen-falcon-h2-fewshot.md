---
title: "Few-shot cross-day decoding of attempted handwriting on FALCON H2 (Chen, Li & Okubo, NeurIPS 2026)"
type: source
tags: [implant, intracortical, handwriting, t5, few-shot, meta-learning, input-aligner, falcon, f3, abstract-level]
sources: [chen-falcon-h2-fewshot]
updated: 2026-11-24
---

# Chen, Li & Okubo 2026: few-shot FALCON H2

## Citation and links
- Y. Chen, M. Li, T. S. Okubo. "Few-Shot Cross-Day Neural Decoding of Attempted Handwriting." NeurIPS 2026 poster. https://neurips.cc/virtual/2026/poster/149445 . Code: https://github.com/CIBR-Okubo-Lab/FALCON_H2 .
- **Licence:** paper: not found (no PDF found). Code repo: **no licence** (GitHub API `license: null`; all rights reserved; do not copy). The README's "License: CC BY 4.0" refers to the H2 dataset.
- **Local raw path:** none. We read the poster abstract and the repo README on 2026-11-24. Numbers outside the abstract come from the README.

## TL;DR
Two stages on [FALCON H2](falcon-benchmark.md). (1) Train a GRU on pooled sessions **without** session-specific layers: it generalises better to new days with no labels. (2) Freeze this backbone and meta-learn (a MAML variant) the initialisation of a small **input aligner**; then adapt it with 3 calibration sentences.

## Key facts
| Item | Value | Where |
|---|---|---|
| Stage 1 | WER "after language-model decoding from 26.99% to 12.10% without using calibration labels" (26.99 = session-specific-layer model, zero-shot; 12.10 = pooled backbone, zero-shot) | Abstract; README Table 1 |
| Same without LM | 63.35 ± 12.77 % → 50.14 ± 21.58 % | README Table 1 |
| Stage 2 | "With three calibration sentences, this approach achieves 7.41% WER" | Abstract |
| Is 7.41 with LM? | the abstract does not say; README Table 1 lists 7.41 ± 5.44 % in the "WER w/ LM" column; without LM 47.38 ± 18.44 % | README |
| Comparators (README, with LM) | session layer + fine-tuning 17.54 %; benchmark zero-shot baseline 39 %; CORP 9 %; oracle 3 % (uses unreleased data) | README Table 1 |
| Model | bidirectional GRU, 5 layers, hidden 512; 3-gram LM + GPT-2 XL rescoring; adaptation 25 gradient steps on about 0.15 % of parameters | README |
| Stated limit | "generalization to other participants and tasks remains to be evaluated in future work" | Abstract |

> **Contradiction:** [Levin et al. 2026](levin-cross-brain-transfer.md) found that transfer **across people** fails without trainable session-specific input layers. Chen et al. found that, **within one person**, a pooled model without session layers generalises better zero-shot. Both then add a small trainable input map for the new session. We keep both results; they differ in setting (cross-person vs cross-day).

## Limitations
- One participant (T5). Bidirectional GRU, so not causal (our observation). Abstract and README only.
- With-LM WER at the 3-sentence point hides a large no-LM error (47 %); much of the gain comes from the LM.

## Why it matters for us
It is the reference number for "a new day with minutes of data" on our exact target modality. The recipe, a frozen trunk plus a small per-session aligner, is the piece our E1 model lacks. See the F3 small-data [plan](../../experiments/2026-11-25-f3-small-data-falcon/plan.md).

## Feeds
- [FALCON benchmark](falcon-benchmark.md), [Levin et al. 2026](levin-cross-brain-transfer.md), [Roy et al. 2026](roy-input-affine-recalibration.md)
- [North star F3](../questions/north-star.md#f3-cross-body-language-model-e1)
