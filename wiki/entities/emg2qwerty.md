---
title: emg2qwerty (wrist-EMG typing dataset)
type: entity
tags: [dataset, emg, typing, public, not-yet-ingested]
sources: [brain2qwerty-v1, brain2qwerty-v2]
updated: 2026-11-07
---

# emg2qwerty

> **Stub.** This page is built only from mentions in the Brain2Qwerty papers. The source itself has not been ingested yet.

- **Citation**: Sivakumar et al., *emg2qwerty: A large dataset with baselines for touch typing using surface electromyography*, NeurIPS 2024.
- **Code and data**: https://github.com/facebookresearch/emg2qwerty
- **Signal**: surface EMG recorded from the **wrist** while people type. This measures muscle activity, not brain activity, so it is not a BCI in the strict sense.
- **Relevance**:
  - Both Brain2Qwerty papers cite it as the model for **continuous, causal decoding**. v2 points to its low-latency causal Conformer as a template for real-time decoding ([v1](../sources/brain2qwerty-v1.md), [v2](../sources/brain2qwerty-v2.md)).
  - It is a *large public* typing dataset that can be decoded with the same CTC machinery, and the hardware (EMG wristbands) is affordable.

**Next step:** ingest the paper and repo.

Related: [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md) · [CTC](../concepts/ctc.md)
