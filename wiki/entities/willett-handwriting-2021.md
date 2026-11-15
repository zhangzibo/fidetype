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

## Replay adapter (P4-01, 2026-11-14)
Module: `fidetype.adapters.willett_handwriting` (our own code, Apache-2.0). Tests: `tests/test_adapter_willett_handwriting.py` (synthetic data only). Conformance target: `adapter:willett`.

**What it reads.** Only `Datasets/<session>/sentences.mat`, with `scipy.io.loadmat` (MATLAB 5 format, plain arrays). It reads the decoder variables and the trial table, not the neural cube. It never runs the `.sh` scripts and never opens the `.p` pickles. All the data that the adapter needs is in `.mat` files.

**What the stream holds.** The output of the real-time RNN decoder in the closed-loop trials (conditions `CL Corpus`, `CL Pandarinath`, `CL Free Write`). The open-loop trials have no decoder output, so they have no stream.

| Item | Value |
|---|---|
| Unit | One stream per closed-loop sentence trial |
| Frames | One frame per character that the system put on the screen (`rnn_decodedCharTimes`) |
| Probabilities | The `rnn_charProbTimeSeries` row that carries the character (31 characters, softmax) |
| Vocabulary | 31 tokens: `a`–`z`, space, `,`, `'`, `.`, `?` (`>` → space, `~` → period). `vocab_type = char`, no blank |
| CTC form | `to_ctc_stream`: blank + 31 tokens, one blank frame between two characters. CTC greedy = the emitted text |
| Time | Seconds from the go cue. 10 ms bins; the RNN output changes every 100 ms |
| Causality | `decoder.causal = true`, `latency = 0`. The RNN ran in real time on past data only |
| Provenance | `adapter.name` / `adapter.version`, opaque `stream.id`, `fidetype.replay` = dataset slug, DOI, licence, session ordinal, trial index, condition, excluded flag |
| Not in the stream | Text, prompts, participant or session names, dates |

**Checks on the data** (readme.pdf and our own checks):
- The argmax of the probability row equals the emitted character for 100 % of the emitted characters (9 sessions).
- The RNN output row changes every 10 bins (100 ms).
- Every emitted character is inside its trial (go cue to sentence end).

**Real-data validation** (local, nothing committed; conformance suite v0.1 checks):

| Count | Value |
|---|---|
| Sessions with real-time output | 9 of 10 (the pilot day has none) |
| Closed-loop trial streams (excluded trials included) | 288 |
| Frames | 13,104 |
| `char` streams trust-ready | 288 / 288 |
| CTC-form streams trust-ready | 288 / 288 |
| Failed check | only `PV-WEIGHTS` (no weights file to hash) |
| Greedy text = stored online text | 281 / 288 |
| CTC round trip exact (to 1e-4) | 288 / 288 |

> **Our take:** The 7 trials where the greedy text differs from `rnn_decodedText` are a data question, not a stream error. The stored text may include characters outside the go-to-end window. We did not check this further.

Open: (1) The offline RNN outputs in `RNNTrainingSteps/Step5_RNNInference/*_inferenceOutputs.mat` (all sentences, 32 columns) could give a second stream type. Their timing and column meaning are not in the readme, so we left them out. (2) A dense 100 ms stream (all RNN outputs, with the new-character signal) needs a spec rule for a "new token" signal; today the stream holds only emitted characters.

## Fit for Fidetype
| Use | Fit | Why |
|---|---|---|
| (a) decoder training | ✔ | Character-level labels |
| (b) trust-layer / eWPM | ✔ | Real-time BCI outputs exist (exact fields unverified) |
| (c) adapter conformance | ✔ | Character decoder from handwriting: a third output type after keystrokes and phonemes |
| (d) pretraining | ~ | Small, one person |

> **Our take:** Small (1.41 GB) and clean. A good second implant adapter after [Brain-to-Text '25](brain-to-text-25.md). It would show that NeuralTextStream covers handwriting as well as speech and typing.

Related: [Dryad intracortical datasets](dryad-intracortical-datasets.md) · [Public datasets survey](../questions/public-datasets.md)
