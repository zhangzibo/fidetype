---
title: "emg2qwerty: A Large Dataset with Baselines for Touch Typing using Surface Electromyography (Sivakumar et al. 2024)"
type: source
tags: [dataset, emg, semg, typing, wrist, ctc, benchmark, personalisation, nc-licence, research-only]
sources: [emg2qwerty]
updated: 2026-11-21
---

# emg2qwerty (paper)

## Citation and links
- **Paper:** V. Sivakumar, J. Seely, A. Du, S. R. Bittner, A. Berenzweig, A. Bolarinwa, A. Gramfort, M. I. Mandel. "emg2qwerty: A Large Dataset with Baselines for Touch Typing using Surface Electromyography." NeurIPS 2024, Track on Datasets and Benchmarks. arXiv:2410.20081, https://arxiv.org/abs/2410.20081. We read v3 (2025-03-20; v1 2024-10-26). Authors: Reality Labs, Meta (CTRL-labs group).
- **Code and data:** https://github.com/facebookresearch/emg2qwerty. Data: `https://fb-ctrl-oss.s3.amazonaws.com/emg2qwerty/emg2qwerty-data-2021-08.tar.gz` (App. C, p. 17).
- **Licence of the paper:** CC BY-NC-SA 4.0 (arXiv abs page, checked 2026-11-21).
- **Licence of the data and code:** the paper says "CC-BY-NC-SA 4.0 licensed, as found in the emg2qwerty/LICENSE file" (App. C, p. 17; also checklist 4b, p. 15, and App. A, p. 16). Use is "only ... for purely non-commercial purposes", and the data "are not intended to be used in conjunction with any other data types" (App. A, p. 16).
- **Local raw path (git-ignored, never committed):** `references/papers/emg2qwerty_sivakumar_2024_arxiv_2410.20081.pdf` (17 pages) + `.txt` (pdftotext). SHA-256 in [`references/README.md`](../../references/README.md).
- **Data on disk:** see the [entity page](../entities/emg2qwerty.md#download-status-p4-01-2026-11-15).

> **Contradiction:** the repo README says "CC-BY-NC-4.0". The paper, the repo `LICENSE` file and the arXiv page say CC BY-NC-SA 4.0. Both are non-commercial. We follow CC BY-NC-SA 4.0. The README is the outlier.

## TL;DR
Meta recorded wrist surface EMG (two 16-channel bands, 2 kHz) from 108 people who touch-typed prompted English text on a real keyboard. A keylogger gives the labels. The set has 1,135 sessions and 346 hours. The authors define two benchmarks: a generic model for unseen users, and a personalised model for each of 8 held-out users. An ASR-style baseline (spectral features, TDS ConvNet, CTC, character 6-gram LM) gets a test CER of 55.38 % on unseen users and 11.28 % after fine-tuning (no LM). With the LM, the fine-tuned CER is 6.95 % (Table 3, p. 9).

## Dataset facts (Table 2, p. 5; Sec. 4, pp. 5–6)
| Item | Value |
|---|---|
| Users / sessions | 108 / 1,135 |
| Sessions per user (avg / max / min) | 10 / 18 / 1 |
| Total duration | 346.4 h |
| Duration per user (avg / max / min) | 3.2 h / 6.5 h / 15.3 min |
| Duration per session (avg / max / min) | 18.0 / 47.5 / 9.5 min |
| Typing rate per user (avg / max / min) | 265 / 439 / 130 keys/min |
| Mean keystroke rate | 4.4 characters per second (p. 5) |
| Total keystrokes | 5,262,671 |
| Users with ≥ 2 h | 94 of 108 (App. B, p. 17) |
| Files | 1,136: 1,135 HDF5 session files + `metadata.csv` (App. C, p. 17) |

> **Contradiction:** App. A (p. 16) says a session spans "10 to 45 minutes". Table 2 (p. 5) gives 9.5 to 47.5 minutes. We quote Table 2 for numbers.

**Hardware (p. 5).** sEMG research device (sEMG-RD): 16 differential electrode pairs per band, dry gold-plated electrodes, 2 kHz, 12 bits, maximum amplitude 6.6 mV, analogue band-pass 20–850 Hz (−3 dB), Bluetooth to the laptop. One band on each wrist (32 channels). The left band is a mirror of the right band, so the polarity is reversed.

**Post-processing (p. 6).** Signal quality checks, a 40 Hz high-pass filter, a clock-drift correction, and alignment of the two bands to the nearest sample (0.5 ms). Sessions with Bluetooth failures or no keylogger data were discarded. The output of the artefact checks is in `metadata.csv` (App. A, p. 16).

**Labels: keylogger only (p. 6; App. A, p. 16).**
- A keylogger records the typed characters with key-down and key-up times. This is the ground truth.
- "No additional labeling was performed beyond the ground-truth provided by the keylogger" (App. A, p. 16).
- Backspace use was free. The labels are the keys that were pressed, not the prompt text.
- Keyboard: Apple Magic Keyboard (US English). Prompts: random dictionary words and English Wikipedia sentences, filtered for offensive terms, lower case and basic punctuation only.
- The bands were taken off and put on again between sessions, so the electrode placement varies.
- Participants were screened for touch typing (correct finger-to-key mapping about 90 % of the time, then a typing test). An IRB approved the study.

## Benchmark (Sec. 4, p. 6; Fig. 2, p. 6; Sec. 5.2, p. 8)
| Part | Rule |
|---|---|
| Test users | 8 of 108, held out for personalisation |
| Per test user | 2 sessions validation, 2 sessions test, the rest trains the personal model |
| Generic model | sessions of the other 100 users; 2 sessions of each of these users for validation |
| Personal models | one per test user, initialised at random or from the generic model |
| Metric | CER = Levenshtein distance between predicted and true keystroke sequences, divided by the true length (p. 7) |
| Split files | Hydra configs under `emg2qwerty/config/user` in the repo (App. C, p. 17) |

## Baseline model (Sec. 5.1–5.2, pp. 7–8)
- **Features:** 33 log-scaled spectral bins per channel, every 8 ms (125 Hz), 32 ms window. 2D batch normalisation first. Spectral features beat rectified time-domain signal.
- **Augmentation:** SpecAugment (at most 3 time masks up to 200 ms, 2 frequency masks up to 4 bins), band rotation by −1 / 0 / +1 electrodes, left–right jitter of 0–120 samples (0–60 ms).
- **Architecture:** a "Rotation-Invariance" module per band (linear + ReLU over shifts −1, 0, +1, averaged; 384 outputs each), then 4 **TDS** (time-depth separable) convolution blocks, kernel 32. Receptive field 1 s (125 samples). The authors did not test Conformers, RNNs or transformers.
- **Context:** training windows of 4 s, padded with **900 ms past and 100 ms future** context. At test time, whole sessions go in without batching.
- **Loss:** [CTC](../concepts/ctc.md). A frame-level cross-entropy on the key times was possible, but CTC gave the best result.
- **LM and decoder:** lexicon-free character 6-gram (modified Kneser-Ney, KenLM, WikiText-103 raw). First-pass beam search with a backspace-aware LM state update.
- **Training:** Adam, 150 epochs, batch 32 per GPU, learning rate ramp to 1e-3 over 10 epochs then cosine to 1e-6. Generic model on 8 A10 GPUs, each personal model on 1 A10. No thorough hyperparameter sweep.

## Results (Table 3, p. 9)
CER in %, mean ± SD over the 8 test users. Every gain from personalisation and from the LM has p < .005.

| Model | No LM, val | No LM, test | 6-gram LM, val | 6-gram LM, test |
|---|---|---|---|---|
| Generic (no personalisation) | 55.57 ± 4.40 | 55.38 ± 4.10 | 52.10 ± 5.54 | 51.78 ± 4.61 |
| Personalised (random init) | 15.65 ± 5.95 | 15.38 ± 5.88 | 11.03 ± 4.45 | 9.55 ± 5.16 |
| Personalised (fine-tuned) | 11.39 ± 4.28 | **11.28 ± 4.45** | 8.31 ± 3.19 | **6.95 ± 3.61** |

- The best single user reaches a test CER of 3.16 % (fine-tuned, with LM; p. 8).
- **Usability line:** "models tend to become usable at a CER of approximately 10% or less" (p. 9). For reference, Palin et al. (2019) report a 2.3 % uncorrected error rate for mobile typing (p. 9).
- The generic model is "simply unusable" on new users (CER over 50 %). The authors link this to the 100 training users. A larger CTRL-labs study shows cross-user generalisation with an order of magnitude more users, on other tasks (p. 9).
- Fine-tuned beats random init on every metric. So representations learned across users carry over (p. 9).

> **Our take:** the number our project uses as its target, **11.28 %**, is the fine-tuned model with **no LM** on test. It is a fair target only for a decoder without an LM. A decoder with a character LM must be compared with **6.95 %**. The paper's model also uses 100 ms of future context, so a decoder with no lookahead has a harder task.

## Limitations (Sec. 6, p. 9; App. A–B, pp. 16–17)
- Users must touch type on QWERTY. English only.
- Recorded on a physical keyboard on a desk. Typing without a keyboard (on the lap, while moving) may need less force, so the EMG amplitude can differ (domain shift).
- A product would run the model on the band itself (latency, privacy, Bluetooth).
- **The sEMG-RD hardware is proprietary.** It is not widely available, so outside groups cannot test models with a human in the loop.
- Data per user varies (15.3 min to 6.5 h), so a generic model can favour some users (App. B, p. 17).
- Research and non-commercial use only. Not to be combined with other data types (App. A, p. 16).

> **Our take:** the dataset is the best public benchmark for wrist-EMG typing. But the device is not for sale, so "affordable hardware" is true for EMG in general (for example the [Meta Neural Band](../entities/meta-neural-band.md), which gives no raw EMG), not for the device that recorded this data.

## How the wiki uses it
- Our P11-01 causal decoder: personalised 15.09 % vs 11.28 % (no LM), generic 53.52 % vs 55.38 % ([P11-01 results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md), [frontier decoder quality](../questions/frontier-decoder-quality.md#second-modality-the-emg-decoder-p11-01-2026-11-19)).
- Brain2Qwerty v2 cites this paper for a "causal Conformer". The paper does not describe one. See the contradiction note on [Brain2Qwerty v2](brain2qwerty-v2.md#limitations--future-work-authors).

## Feeds
- Entities: [emg2qwerty](../entities/emg2qwerty.md), [Meta Neural Band](../entities/meta-neural-band.md), [Meta FAIR Brain & AI](../entities/meta-fair-brain-ai.md).
- Concepts: [CTC](../concepts/ctc.md), [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md), [EEG](../concepts/eeg.md).
- Questions: [Public datasets](../questions/public-datasets.md), [Frontier decoder quality](../questions/frontier-decoder-quality.md), [Research directions](../questions/research-directions.md).
- Other sources: [Brain2Qwerty v2](brain2qwerty-v2.md), [Neural input landscape 2026](neural-input-landscape-2026.md).
