---
title: "facebookresearch/brain2qwerty (code repo)"
type: source
tags: [code, meg, reproduction, licence]
sources: [brain2qwerty-code]
updated: 2026-11-07
---

# Brain2Qwerty code repo

- **Link**: https://github.com/facebookresearch/brain2qwerty
- **Licence**: **CC BY-NC 4.0**, which means **no commercial use**. We can study it and reimplement the ideas, but we must not copy files into anything we might sell.
- **Raw**: `references/repos/brain2qwerty/`. Shallow clone taken 2026-11-07 with `.git` removed. The folder is git-ignored. Its `AGENT_README.md` is inaccurate in several places (see the gotchas below).
- **Read by**: a subagent code review, spot-checked by hand. Nothing has been run yet.

## TL;DR
The repo is small: about 3.5k lines of Python in two packages, `brain2qwerty_v1/` and `brain2qwerty_v2/`. Most of the model building blocks live in Meta's PyPI libraries `neuraltrain==0.2.2` and `neuralset==0.2.2`. **v1 can be reproduced** from the public [SpanishBCBL](../entities/spanishbcbl-dataset.md) data. **v2 cannot run end-to-end**: its data is embargoed and its loader class `PinetAudio2025` is missing from the repo.

## Stack
- Python ≥3.12. The v2 README says 3.10+, which contradicts `pyproject.toml`.
- torch 2.6, torchaudio 2.6, lightning 2.5, mne 1.11, transformers 4.52, peft 0.18, x-transformers. `kenlm` is optional.
- `requirements.lock` pins dependencies for **Linux x86-64 + CUDA 12.4**. On Windows we would use WSL2.
- Paths are set with the env vars `BRAIN2QWERTY_STUDIES`, `_CACHE` and `_RESULTS`.
- CLI: `python -m brain2qwerty_v{1,2}.main {cache,debug,train,eval}`.

## v1 as implemented vs the paper
- Same preprocessing as [the paper](brain2qwerty-v1.md): 50 Hz, 0.1–20 Hz, a −0.2…+0.3 s window, 29 classes. The splitter uses TF-IDF clustering.
- `SimpleConvTimeAgg` has 8 dilated blocks with hidden size 2048, followed by a 4-layer transformer with ALiBi and a cross-entropy loss.
- The repo defaults **differ from the paper**: lr 5e-5 ("more stable than the one reported in paper"), 300 epochs, early stopping with patience 30.
- **No KenLM ARPA file ships.** You have to build one with `lmplz`.
- AGENT_README reports MEG CER ≈ 0.36 without the LM. This matches the Conv+Trans bar in the paper.

## v2 as implemented vs the paper
- The encoder, CTC loss, `CTCSpaceSegmenter` and SigLIP + hard-DTW `WordContrastiveLoss` all match [the paper](brain2qwerty-v2.md).
- The released LLM config differs from the one used for the reported results:
  | | Released config | Paper |
  |---|---|---|
  | LLM | TinyLlama-1.1B | Qwen3-4B |
  | LoRA rank | 2 | 128 |
  | Adapters | One for all subjects | Per-subject model soup |
- The defaults assume 8 GPUs with DDP and fall back to however many are available.

## Gotchas (noted from reading, not yet confirmed by running)
- `v2/transforms.py:170` caches typed-label sequences by sentence *text*. Two subjects who made different typos in the same sentence may get the same cached label.
- `v2/augmentations.py` applies torchaudio Time/FrequencyMasking to a `(B,T,C)` tensor, so the two masks may be swapped: "frequency" masking would hit time and "time" masking would hit channels.
- Hard-DTW and the segmenter are pure-Python loops that run on every training step, so they are slow.
- v1 computes its training-time CER per batch, not per sentence. The offline scripts compute it per sentence.

## Reproducing v1 on one machine
1. Request access to the gated HuggingFace dataset and download the MEG subtree (the full dataset is ~262 GB).
2. Set up WSL2 with Python 3.12 and run `pip install -r requirements.lock`.
3. Run `cache`, then `train`, then `eval`, then `scripts.extract_predictions`.
4. Optionally, train a 9-gram on Spanish Wikipedia and run `ngram_decoding`.

The paper reports ~18 h on a 32 GB GPU. A 12–24 GB consumer card should fit batch 64. The code uses BF16, which needs an Ampere or newer GPU.

## Feeds
[Brain2Qwerty v1](brain2qwerty-v1.md) · [Brain2Qwerty v2](brain2qwerty-v2.md) · [BrainModule](../concepts/brainmodule.md) · [CTC](../concepts/ctc.md) · [NeuroLLM](../concepts/neuro-llm.md) · [Meta FAIR Brain & AI](../entities/meta-fair-brain-ai.md)
