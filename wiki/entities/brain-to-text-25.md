---
title: Brain-to-Text '25 dataset (Card et al., T15)
type: entity
tags: [dataset, implant, intracortical, speech, cc0, licence-clean, trust-eval]
sources: [neural-input-landscape-2026, brain-to-text-25-copytask]
updated: 2026-11-10
---

# Brain-to-Text '25 (Card et al.)

- **Citation**: Card et al., *An accurate and rapidly calibrating speech neuroprosthesis* (NEJM 2024). Data: "Data for: An accurate and rapidly calibrating speech neuroprosthesis".
- **Link**: https://datadryad.org/dataset/doi:10.5061/dryad.dncjsxm85
- **Licence**: Dryad deposits are **CC0**. Commercial use: yes. The code repo `Neuroprosthetics-Lab/nejm-brain-to-text` has **no licence** (GitHub API: `null`). Write our own loader.
- **Participant**: one person (T15) with ALS and severe dysarthria. Arrays in the left precentral gyrus (secondary source).
- **Signal**: 256 channels → 512 features (threshold crossings + spike band power), 20 ms bins, z-scored over the preceding 20 trials.
- **Size**: 11.59 GB (version of 2025-07-03), verified on the Dryad page 2026-11-10.

| File | Size | Content |
|---|---|---|
| `t15_copyTask.pkl` | 57.79 MB | Per trial: cue sentence, decoded phonemes and words, duration, RNN logits. 1,718 evaluation trials |
| `t15_personalUse.pkl` | 1.13 MB | Conversation mode: 22,126 sentences. Word count, duration, user correctness rating. Text withheld |
| `t15_copyTask_neuralData.zip` | 11.05 GB | Neural data + sentence labels, train/val/test. 11,000+ trials, 45 sessions over 20 months. Test labels withheld (challenge) |
| `t15_pretrained_rnn_baseline.zip` | 484.94 MB | Pretrained RNN weights |

## Downloaded (2026-11-10)
- `t15_copyTask.pkl` is local at `C:\Users\zhang\bci-data\brain-to-text-25\` (outside the repo). Size 57,786,348 bytes. SHA-256 equals the Dryad digest. Details: [source page](../sources/brain-to-text-25-copytask.md).
- Dryad file downloads need a login token. We used the HF mirror `Paulownia/Brain-to-text_25_data` and checked the digest.
- Pickle safety: only 4 numpy globals; loaded with a whitelist Unpickler.
- Contents: 1,718 trials (1,628 with the 125,000-word vocabulary), 15 days. Logits (T, 41): blank, `SIL`, 39 ARPAbet phonemes. Frames 80 ms (inferred).
- Published online decoder (from the file): WER 0.0434 pooled over all trials; PER of the raw greedy phonemes 0.0954.
- Adapter: `src/fidetype/adapters/b2t25.py` (our code). Result: [B2T '25 trust result](../questions/b2t25-trust-result.md).

## Fit for Fidetype
| Use | Fit | Why |
|---|---|---|
| (a) decoder training | ✔ | 11,000+ labelled trials, a baseline RNN |
| (b) trust-layer / eWPM evaluation | ✔ | Real decoder logits and cue sentences. User ratings in conversation mode |
| (c) adapter conformance | ✔ | Phoneme-logit decoder output: a different shape from our MEG char CTC |
| (d) pretraining | ~ | One person, implant only |

> **Our take (2026-11-10, before the download):** This is the **first dataset to download**. Start with `t15_copyTask.pkl` (58 MB): it already holds real logits, so the trust harness can run on licence-clean decoder output without a GPU. The conversation-mode correctness ratings are a rare real-world ground truth for "did the user accept this sentence". See the [survey](../questions/public-datasets.md#recommended-next-actions).

Related: [Conformance suite](../concepts/conformance-suite.md) (adapter level: trust-ready) · [Source page (copy-task file)](../sources/brain-to-text-25-copytask.md) · [B2T '25 trust result](../questions/b2t25-trust-result.md) · [Dryad intracortical datasets](dryad-intracortical-datasets.md) · [Willett 2021 handwriting](willett-handwriting-2021.md) · [Public datasets survey](../questions/public-datasets.md) · [Trust core v0 results](../questions/trust-core-v0-results.md)
