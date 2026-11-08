---
title: "Brain2Qwerty v1: Noninvasive decoding of typed sentences from human brain activity"
type: source
tags: [meg, eeg, typing, decoding, synchronous]
sources: [brain2qwerty-v1]
updated: 2026-11-07
---

# Brain2Qwerty v1 (Nature Neuroscience, 2026)

- **Citation**: Lévy J., Zhang M., Pinet S., Rapin J., Banville H., d'Ascoli S.\*, King J.-R.\* *Noninvasive decoding of typed sentences from human brain activity.* Nature Neuroscience 29, 2438–2444 (Oct 2026). Received 21 Mar 2025, published online 29 Jun 2026.
- **Link**: https://doi.org/10.1038/s41593-026-02303-2. Licence: CC BY-NC-ND 4.0.
- **Raw**: `references/papers/brain2qwerty_v1_nature_neuroscience_s41593-026-02303-2.pdf` (+ `.txt`)
- **Affiliations**: [Meta FAIR Brain & AI](../entities/meta-fair-brain-ai.md), ENS/PSL, Rothschild Foundation hospital, Univ. Lille, [BCBL](../entities/bcbl.md)

## TL;DR
Healthy volunteers typed memorised Spanish sentences while recorded with [MEG](../concepts/meg.md) or [EEG](../concepts/eeg.md). A deep model classifies each keystroke from a 500 ms window locked to that keystroke ([synchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md)). It reaches **29% CER with MEG** versus **65% with EEG**, and 18% CER for the best MEG participants.

## Protocol
- **Participants**: 35 healthy, right-handed, skilled typists (typing accuracy ≥80%). 20 recorded with EEG and 20 with MEG, 5 of them in both. One MEG participant was excluded for metal. Mean age 31.6, 77% women. Participants were paid €12/h.
- **Recording time**: 0.88 h per participant for EEG and 0.93 h for MEG, giving **17.7 h of EEG and 21.5 h of MEG** in total.
- **Trial**: read → wait → type. The sentence is shown word by word (RSVP, 465–665 ms per word), followed by a 1.5 s fixation cross. The participant then types it from memory without seeing the text. A small square rotates 10° per keystroke so that eye movements don't follow the text. Backspace is not allowed.
- **Stimuli**: each session has 128 unique Spanish declarative sentences of 5–8 words, typed in uppercase without accents.
- **Totals**:
  - MEG: 5,100 sentences, 193k characters
  - EEG: 4,000 sentences, 146k characters
- **Hardware**:
  - MEGIN 306-channel MEG (102 magnetometers + 204 gradiometers) at 1 kHz.
  - BrainVision actiCAP slim, 64 channels (61 EEG).
  - A custom MR-compatible HybridMojo keyboard, with non-ferromagnetic silver springs in place of the steel ones.
- **Data**: [SpanishBCBL](../entities/spanishbcbl-dataset.md). The paper says data is shared "upon request" with academics, but it is also on HuggingFace (gated).

## Pipeline
- **Preprocessing**: 0.1–20 Hz bandpass, resample to 50 Hz, a −0.2…+0.3 s window around each keystroke, baseline correction, RobustScaler, clamping.
- **Text**: typed and target sentences are aligned with `difflib`. Sentences with more than 10 typos are dropped. Analyses use the *target* key. 3.6% of keystrokes are typos, and typing speed is 152 characters/min.
- **Splits**: 80/10/10 over *unique sentences*. TF-IDF agglomerative clustering (threshold 0.5) keeps near-duplicate sentences in the same split.
- **Model** (~400M params). There are 29 output classes: 26 letters, space, a number class and an "other" class.
  1. **Conv** (258M). The [BrainModule](../concepts/brainmodule.md) has spatial attention over sensors, a subject layer and 8 dilated conv blocks (kernel 3). Attention pooling over time produces a 2048-d vector per keystroke.
  2. **Trans** (138M). A 4-layer, 2-head transformer over the keystrokes of one sentence, followed by a linear layer to the 29 classes.
  3. **LM**. A 9-gram character KenLM trained on Spanish Wikipedia, using beam search (beam 30, LM weight 5).
- **Training**: cross-entropy, AdamW, OneCycleLR (warm-up to 1e-4), 100 epochs, batch 128. Training takes **~18 h on one 32 GB Quadro GV100**.

## Key results
| Metric | MEG | EEG |
|---|---|---|
| CER, mean (± SEM) | **29 ± 1.7%** | 65 ± 0.7% |
| CER, best participant | 18 ± 2.3% | 61 ± 1.9% |
| CER, worst participant | 47 ± 3.2% | 69 ± 1.8% |
| Linear left/right hand accuracy (peak at +40 ms) | 74% | 64% |

- **Baselines**: Brain2Qwerty is 2.5× better than EEGNet on MEG CER and 1.2× better on EEG.
- **Ablations**: going from Conv to Conv+Trans to Conv+Trans+LM improves CER significantly at each step (Fig. 2). For example, MEG CER goes 0.67 → 0.36 → 0.29.
- **Frequency effects**: frequent words and characters are decoded better (character-frequency r = −0.87). Rare letters (z, k, w) are at chance. Out-of-vocabulary words reach 70% CER.
- **[Data scaling](../concepts/data-scaling.md)**: CER falls with training hours (r = −0.93). There is no plateau.
- **Motor origin**: confusions grow with keyboard distance (r = 0.73). k-means on the Conv embeddings separates left from right hand and recovers the keyboard layout.
- **Typos**: mistyped characters are decoded worse (Conv+Trans CER 69% vs 36%). The language model sometimes *corrects* the user's typos ("EK BENEFUCUI…" is decoded as "EL BENEFICIO SUPERA LOS RIESGOS").

## Limitations (authors)
1. It is not real-time. It needs the keystroke onsets, and the transformer and LM wait for the end of the sentence.
2. Participants are healthy and typing overtly. Paralysed users would need attempted or imagined movement, which has not been validated non-invasively.
3. It relies on cryogenic MEG. The authors hope [OPM-MEG](../concepts/opm-meg.md) will eventually provide this in wearable form.
4. It is still well behind invasive BCIs: Willett 2021 handwriting reaches <6% CER, and Metzger 2023 speech reaches 15.2% CER.

## Feeds
[MEG](../concepts/meg.md) · [EEG](../concepts/eeg.md) · [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md) · [BrainModule](../concepts/brainmodule.md) · [Data scaling](../concepts/data-scaling.md) · [Error metrics](../concepts/error-metrics.md) · [SpanishBCBL](../entities/spanishbcbl-dataset.md) · [Brain2Qwerty v2](brain2qwerty-v2.md) · [Code](brain2qwerty-code.md)
