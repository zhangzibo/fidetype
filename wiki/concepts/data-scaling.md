---
title: Data scaling in non-invasive decoding
type: concept
tags: [scaling, data]
sources: [brain2qwerty-v1, brain2qwerty-v2]
updated: 2026-11-07
---

# Data scaling

**Claim:** Non-invasive decoding accuracy keeps improving with more training data. Neither study has reached a plateau.

## Evidence
- **v1**: CER falls as training hours increase, with Pearson r = −0.93 across 20 training subsets ([v1](../sources/brain2qwerty-v1.md), Fig. 5d).
- **v2**: CER is **log-linear** in recording hours. Across 5 training fractions r = −0.99 and R² = 0.98, with a slope of **−0.39 CER per decade**. There is no saturation at about 90 h pooled across subjects ([v2](../sources/brain2qwerty-v2.md), Fig. 1F).
- **Volume enables asynchronous decoding.** The async encoder's CER goes from 0.59 at about 1 h per subject to 0.25 at about 10 h per subject ([v2](../sources/brain2qwerty-v2.md), Fig. 1D–E). See [sync vs async decoding](synchronous-vs-asynchronous-decoding.md).
- **Diversity counts separately from volume.** With the total held constant, 256 unique sentences typed once each give CER 0.45. The same total made of 128 sentences typed twice gives 0.65 ([v2](../sources/brain2qwerty-v2.md), Fig. 1G).
- **Pooling subjects helps.** Joint training beats per-subject training. Pretraining on the other subjects and then fine-tuning recovers most of the benefit for a new subject ([v2](../sources/brain2qwerty-v2.md), Table 1).
- **Frequency effects** point the same way. Characters and words that appear more often in training are decoded better ([v1](../sources/brain2qwerty-v1.md), Fig. 5).

## Context
Invasive BCIs train on thousands of sentences over 10–40 h ([v2](../sources/brain2qwerty-v2.md), intro).

> **Our take:** If the scaling holds, the bottleneck is data collection, which needs a scanner, rather than modelling. Without a lab, the levers we have are (a) making better use of existing data, through cross-subject and self-supervised pretraining on *all* public MEG, including non-typing datasets such as LibriBrain, and (b) arguing for a shared open data effort. Whether pretraining on public MEG from other tasks transfers to typing is an open question.

Related: [MEG](meg.md) · [Model soup](model-soup.md)
