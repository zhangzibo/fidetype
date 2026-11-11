---
title: Willett 2021 handwriting BCI dataset (T5)
type: entity
tags: [dataset, implant, intracortical, handwriting, cc0, licence-clean]
sources: [neural-input-landscape-2026]
updated: 2026-11-10
---

# Willett 2021 handwriting dataset

- **Citation**: Willett et al., *High-performance brain-to-text communication via handwriting*, Nature 2021. Data: "Data from: High-performance brain-to-text communication via handwriting".
- **Link**: https://datadryad.org/dataset/doi:10.5061/dryad.wh70rxwmv
- **Licence**: Dryad deposit, **CC0**. Commercial use: yes. The example code `fwillett/handwritingBCI` has licence `NOASSERTION` (GitHub API). Do not copy it.
- **Participant**: one person (T5). Two 96-electrode arrays in the hand area of motor cortex.
- **Size**: `handwritingBCIData.tar.gz` 1.41 GB + `readme.pdf`. 10.7 hours, 1,000 sentences, 43,501 characters (Dryad page, verified 2026-11-10).
- **Content**: all neural activity of the experiments and all real-time outputs of the handwriting BCI. The format is in `readme.pdf` (not read yet).
- **Benchmark copy**: FALCON H2 "Human Handwriting iBCI" on DANDI (000950), 1.22 GB, **CC BY 4.0** (DANDI API).

## Fit for Fidetype
| Use | Fit | Why |
|---|---|---|
| (a) decoder training | ✔ | Character-level labels |
| (b) trust-layer / eWPM | ✔ | Real-time BCI outputs exist (exact fields unverified) |
| (c) adapter conformance | ✔ | Character decoder from handwriting: a third output type after keystrokes and phonemes |
| (d) pretraining | ~ | Small, one person |

> **Our take:** Small (1.41 GB) and clean. A good second implant adapter after [Brain-to-Text '25](brain-to-text-25.md). It would show that NeuralTextStream covers handwriting as well as speech and typing.

Related: [Dryad intracortical datasets](dryad-intracortical-datasets.md) · [Public datasets survey](../questions/public-datasets.md)
