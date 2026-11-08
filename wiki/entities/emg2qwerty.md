---
title: emg2qwerty (wrist-EMG typing dataset)
type: entity
tags: [dataset, emg, typing, public, nc-licence, not-yet-ingested]
sources: [brain2qwerty-v1, brain2qwerty-v2, neural-input-landscape-2026]
updated: 2026-11-08
---

# emg2qwerty

> **Partial page.** The licence and format facts come from the [neural input landscape report](../sources/neural-input-landscape-2026.md#data-warning). The rest comes from mentions in the Brain2Qwerty papers. The paper and repo themselves are not ingested yet.

- **Citation**: Sivakumar et al., *emg2qwerty: A large dataset with baselines for touch typing using surface electromyography*, NeurIPS 2024.
- **Code and data**: https://github.com/facebookresearch/emg2qwerty
- **Licence**: **CC-BY-NC-4.0.** It is not commercially usable. Use it only for research and benchmarks ([landscape report](../sources/neural-input-landscape-2026.md#data-warning)).
- **Format**: HDF5 at 2 kHz.
- **Signal**: surface EMG recorded from the **wrist** while people type. This measures muscle activity, not brain activity, so it is not a BCI in the strict sense.
- **Relevance**:
  - Both Brain2Qwerty papers cite it as the model for **continuous, causal decoding**. v2 points to its low-latency causal Conformer as a template for real-time decoding ([v1](../sources/brain2qwerty-v1.md), [v2](../sources/brain2qwerty-v2.md)).
  - It is a *large public* typing dataset that can be decoded with the same CTC machinery, and the hardware (EMG wristbands) is affordable.

## Sibling Meta datasets
All Meta EMG datasets are NC. All are HDF5 at 2 kHz.

| Dataset | Licence |
|---|---|
| emg2qwerty | CC-BY-NC-4.0 |
| generic-neuromotor-interface | CC-BY-NC-4.0 |
| emg2pose | CC-BY-NC-SA-4.0 |

> **Our take:** emg2qwerty stays useful for research replay of the EMG adapter. It cannot train product weights. For licence-clean evaluation of the trust layer on real decoded text, the CC0 [Dryad intracortical datasets](dryad-intracortical-datasets.md) are the better choice.

**Next step:** ingest the paper and repo.

Related: [Meta Neural Band](meta-neural-band.md) · [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md) · [CTC](../concepts/ctc.md)
