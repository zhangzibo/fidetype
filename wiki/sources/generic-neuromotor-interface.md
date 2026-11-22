---
title: "A generic non-invasive neuromotor interface for human-computer interaction (CTRL-labs at Reality Labs, Kaifosh & Reardon, Nature 2025)"
type: source
tags: [emg, semg, wrist, handwriting, gestures, conformer, causal, streaming, ctc, scaling, personalisation, nc-licence, research-only]
sources: [generic-neuromotor-interface, emg2qwerty, brain2qwerty-v2]
updated: 2026-11-22
---

# Generic neuromotor interface (CTRL-labs, Nature 2025)

## Citation and links
- **Paper:** P. Kaifosh, T. R. Reardon & CTRL-labs at Reality Labs. "A generic non-invasive neuromotor interface for human-computer interaction." *Nature* 645, 702–711 (18 September 2025). https://doi.org/10.1038/s41586-025-09255-w. Received 23 February 2024, accepted 6 June 2025, published online 23 July 2025 (PDF p. 1).
- **Preprint:** bioRxiv 10.1101/2024.02.23.581779 (2024). [emg2qwerty](emg2qwerty.md) cites this preprint as "CTRL-labs at Reality Labs, D. Sussillo, P. Kaifosh, and T. Reardon" (emg2qwerty ref. list, p. 10). We did **not** read the preprint: bioRxiv refused the automated request (HTTP 429, 2026-11-22). This page uses the Nature version only.
- **Licence of the paper:** CC BY-NC-ND 4.0 (Nature article page and PDF p. 10, checked 2026-11-22). Non-commercial, no derivatives. We store the PDF locally only and quote short passages.
- **Data and code:** data at `https://fb-ctrl-oss.s3.amazonaws.com/generic-neuromotor-interface-data`. The paper names the repo `https://github.com/facebookresearch/generic-neuromotor-interface-data`. That name now redirects to `facebookresearch/generic-neuromotor-interface` (GitHub API, 2026-11-22). Released: 1,060 recordings from 300 participants, 100 per task: wrist 74 h, discrete gestures 63 h, handwriting 126 h (Data availability, PDF p. 20).
- **Local raw path (git-ignored, never committed):** `references/papers/generic_neuromotor_interface_kaifosh_2025_nature_s41586-025-09255-w.pdf` (36 pages incl. Extended Data and reporting summary) + `.txt` (pdftotext -enc UTF-8). SHA-256 in [`references/README.md`](../../references/README.md).

> **Contradiction (licence):** the paper says "Data and code are available under a Attribution-NonCommercial-ShareAlike 4.0 license" (Code availability, PDF p. 20). The repo README and `LICENSE` file say CC BY-NC 4.0 (GitHub, checked 2026-11-22). Both are non-commercial. This is the reverse of [emg2qwerty](emg2qwerty.md), where the README says BY-NC and the paper says BY-NC-SA. We follow the stricter reading (BY-NC-SA) until Meta clarifies.

## TL;DR
CTRL-labs (Meta Reality Labs) built a dry 16-channel wrist sEMG band (sEMG-RD) and collected data from thousands of people. They trained **generic** decoders that work on new people without calibration, for three tasks: wrist-angle cursor control, nine discrete gestures, and **handwriting** of characters. The handwriting decoder is a **causal, streaming Conformer** trained with CTC. Closed-loop results: 0.66 target acquisitions per second, 0.88 gesture detections per second, and handwriting at 20.9 WPM. Personalising the handwriting model with 20 min of data improves it by 16 % (Abstract, PDF p. 1; Fig. 5c, PDF p. 6).

## Decoder architectures (Methods, PDF pp. 14–16)
| Task | Input | Model | Causal? |
|---|---|---|---|
| Wrist (1D velocity) | MPF features | rotation-invariance MLP, 2 LSTM layers of 512 | yes (LSTM) |
| Discrete gestures (9) | raw sEMG, rescaled, 40 Hz high-pass | Conv1D (stride 10, 2 kHz to 200 Hz), 3 LSTM layers | yes; labels shifted 100 ms later, so the model sees 100 ms more signal before it must fire (PDF p. 15) |
| **Handwriting** (characters + 4 control gestures) | MPF features | rotation-invariance module, **15-layer Conformer**, 4 heads, conv kernel 8, stride 2 at layers 5 and 10; CTC loss; FastEmit; greedy decoding | **yes**: "self-attention is solely applied to a fixed local window situated directly before the current time step"; window 16 for layers 1–10, 8 for layers 11–15 (PDF p. 16) |

Key quotes:
- "MPF features and a conformer for the handwriting task, which we anticipated would require an architecture with richer context information" (Offline evaluation, PDF p. 4).
- "A popular model architecture for ASR is the Conformer, which provides the advantages of attention-based processing in a form that is compatible with causal time-series modelling" (Methods, PDF p. 14).
- "To ensure that the model functioned in a streaming manner, a modified conformer architecture was used ... with adjustments to ensure causality" (Methods, PDF p. 16).
- FastEmit "effectively reduced the streaming latency of our models by penalizing sequences of 'blank' outputs" (Methods, PDF p. 15).
- The largest handwriting model needs 801.7 million FLOPs per output sample. Learning rates are given for a 1 million and a 60 million parameter model (PDF p. 16). The personalisation baseline is the "60.2-million-parameter 6,527-participant pretrained generic model" (Fig. 5e caption, PDF p. 6).

## Key facts and numbers
| Item | Value | Where |
|---|---|---|
| Participants per task (training data) | 162–6,627, by task | PDF p. 2 |
| Handwriting training corpora | 25 to 6,527 participants, geometric steps | PDF p. 15 |
| Handwriting held-out sets | 50 validation + 50 test participants | PDF p. 15 |
| Offline accuracy, held-out people | "greater than 90% classification accuracy" for handwriting and gestures; wrist error "less than 13° s−1" | PDF p. 2 |
| Closed-loop handwriting | 20.9 WPM; online CER in Fig. 3i; n = 20 naive test participants | Abstract; Fig. 3i,j |
| Personalisation | 20 min of data gives a 16 % improvement in median performance, even for a 6,400-participant generic model | PDF p. 6, Fig. 5c |
| Personalisation vs more data | for a 25-participant model, 20 min of personal data equals 14,000 min of extra generic data (7×) | PDF p. 6 |
| Scaling | error follows a power law in participants and parameters | Fig. 2e–g; Methods |
| Decoding | greedy CTC; "beam decoding with language modelling ... would have been possible" | PDF p. 14 |

Online CER (median per trial) is "not directly comparable with the offline CER metric reported in Fig. 2g" (PDF p. 18).

## Relation to emg2qwerty
- Same group, same device. emg2qwerty records with "the sEMG research device (sEMG-RD) described in CTRL-labs at Reality Labs et al. (2024)" ([emg2qwerty](emg2qwerty.md), p. 5). All eight emg2qwerty authors (Sivakumar, Seely, Du, Bittner, Berenzweig, Bolarinwa, Gramfort, Mandel) are in the CTRL-labs author list of this paper (PDF p. 10).
- Different task and model. emg2qwerty is **typing** on a keyboard, with a **TDS ConvNet** baseline and 100 ms future context in training ([emg2qwerty](emg2qwerty.md), Sec. 5.1–5.2, pp. 7–8). This paper does **handwriting** (no keyboard) with a **causal Conformer**.
- This paper does not cite emg2qwerty (no match for "emg2qwerty" or "Sivakumar" in the reference list).

## Verdict on the Brain2Qwerty v2 citation (gap 179 / P11-26)
[Brain2Qwerty v2](brain2qwerty-v2.md) writes: "results in EMG have shown promising results in using a causal Conformer with low-latency to decode handwriting (Sivakumar et al., 2024)" (Discussion, p. 10). Its reference list resolves "Sivakumar et al., 2024" to the emg2qwerty NeurIPS paper (v2 p. 19). v2 does not cite the CTRL-labs paper anywhere.

| Part of the v2 claim | emg2qwerty | This paper |
|---|---|---|
| "Conformer" | no (TDS ConvNet) | yes (15 layers) |
| "causal" | near-causal (100 ms lookahead in training) | yes (attention only on a past window) |
| "low-latency" | not a stated aim | yes (streaming, FastEmit) |
| "handwriting" | no (typing) | yes |

**Verdict: confusion confirmed.** Each part of the v2 description matches this paper and not emg2qwerty. The citation points to the wrong paper of the same group.

> **Our take:** the likely cause is that the two papers share authors, the device and the "CTRL-labs 2024" timeframe. We cannot know the v2 authors' intent. For our work the point is practical: the causal Conformer template for streaming decoding is in this paper (Methods, PDF p. 16), not in emg2qwerty. A streaming MEG decoder ([synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md)) can copy the idea (local past-only attention, FastEmit), but must use our own code because the released code is NC.

## Limitations
- The sEMG-RD is a research device. It is not for sale.
- All released data and code are non-commercial (see the licence contradiction above). The paper itself is CC BY-NC-ND 4.0.
- Released data is a subset: 100 participants per task, not the thousands used for training.
- Handwriting results use greedy decoding with no language model.
- The online and offline CER metrics differ (median per trial vs aggregate), so do not compare them directly.
- We read the Nature version only, not the 2024 bioRxiv preprint. The preprint text may differ.

## Feeds
- Entities: [Meta Neural Band](../entities/meta-neural-band.md), [emg2qwerty](../entities/emg2qwerty.md).
- Concepts: [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md), [CTC](../concepts/ctc.md), [Data scaling](../concepts/data-scaling.md).
- Questions: [Public datasets](../questions/public-datasets.md).
- Other sources: [emg2qwerty (paper)](emg2qwerty.md), [Brain2Qwerty v2](brain2qwerty-v2.md).
