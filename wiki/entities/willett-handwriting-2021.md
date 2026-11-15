---
title: Willett 2021 handwriting BCI dataset (T5)
type: entity
tags: [dataset, implant, intracortical, handwriting, cc0, licence-clean]
sources: [neural-input-landscape-2026]
updated: 2026-11-14
---

# Willett 2021 handwriting dataset

- **Citation**: Willett et al., *High-performance brain-to-text communication via handwriting*, Nature 2021. Data: "Data from: High-performance brain-to-text communication via handwriting".
- **Link**: https://datadryad.org/dataset/doi:10.5061/dryad.wh70rxwmv
- **Licence**: Dryad deposit, **CC0**. Commercial use: yes. The example code `fwillett/handwritingBCI` has licence `NOASSERTION` (GitHub API). Do not copy it.
- **Participant**: one person (T5). Two 96-electrode arrays in the hand area of motor cortex.
- **Size**: `handwritingBCIData.tar.gz` 1.41 GB + `readme.pdf`. 10.7 hours, 1,000 sentences, 43,501 characters (Dryad page, verified 2026-11-10).
- **Content**: all neural activity of the experiments and all real-time outputs of the handwriting BCI. The format is in `readme.pdf` (not read yet).
- **Benchmark copy**: FALCON H2 "Human Handwriting iBCI" on DANDI (000950), 1.22 GB, **CC BY 4.0** (DANDI API).

## Local copy (P4-01, 2026-11-14)
- **Source used**: Zenodo record [4695519](https://zenodo.org/records/4695519). It is the Dryad deposit itself: its DOI is `10.5061/dryad.wh70rxwmv`, it is in the Zenodo `dryad` community, licence `cc-zero`, open access. Same method as for Brain-to-Text '24 (see `references/README.md`).
- **Why not Dryad**: the Dryad file API answered 401 "must have current bearer token" on 2026-11-14. Dryad metadata (no login) still gives the reference digests.
- **Dryad version**: 5, published 2021-10-15, licence CC0 1.0 (Dryad API).
- **Files** (bytes, Dryad SHA-256):

| File | Size | SHA-256 (Dryad) | MD5 (Zenodo) |
|---|---|---|---|
| `handwritingBCIData.tar.gz` | 1,408,201,020 | `f41ff3577f8e8d0e76c24f61b46b1bc5a36ab329cd027947960c5e29ab7223ac` | `38b804d8bd271bd5981c7fda7f925eb8` |
| `readme.pdf` | 288,173 | `f5755861a6f34de0b74575535982c3e8aa285fcb9d24bb56753c877d93c00232` | `aac8b5c6114b2382d63744c52c6d0709` |

- **Local path**: `C:\Users\zhang\bci-data\raw\willett-handwriting\` (outside the repo, never committed). Extracted copy: `...\willett-handwriting\extracted\`.
- **Check**: `bash C:/Users/zhang/bci-data/scripts/verify-p4-01.sh` (size, MD5 and SHA-256).
- **Status**: **done** (2026-11-14 17:21). Size, MD5 and SHA-256 match both sources. The archive has 20,282 entries (20,203 files, 79 folders), no links, no absolute or `..` paths. Extracted: 6,098,309,610 bytes in `handwritingBCIData/` (`Datasets/` with 12 T5 sessions, `RNNTrainingSteps/`, `BigramLM/`, `readme.pdf`). The archive also holds `.sh` scripts and two `.p` pickles: data only, never run or unpickle them without a safety scan.

## Fit for Fidetype
| Use | Fit | Why |
|---|---|---|
| (a) decoder training | ✔ | Character-level labels |
| (b) trust-layer / eWPM | ✔ | Real-time BCI outputs exist (exact fields unverified) |
| (c) adapter conformance | ✔ | Character decoder from handwriting: a third output type after keystrokes and phonemes |
| (d) pretraining | ~ | Small, one person |

> **Our take:** Small (1.41 GB) and clean. A good second implant adapter after [Brain-to-Text '25](brain-to-text-25.md). It would show that NeuralTextStream covers handwriting as well as speech and typing.

Related: [Dryad intracortical datasets](dryad-intracortical-datasets.md) · [Public datasets survey](../questions/public-datasets.md)
