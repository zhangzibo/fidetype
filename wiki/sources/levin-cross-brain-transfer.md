---
title: "Cross-brain transfer of intracortical speech and handwriting BCIs (Levin et al. 2026)"
type: source
tags: [implant, intracortical, transfer-learning, cross-person, speech, handwriting, ctc, input-layers, low-data, f3, novelty-check]
sources: [levin-cross-brain-transfer]
updated: 2026-11-24
---

# Cross-brain transfer (Levin et al. 2026)

## Citation and links
- A. D. Levin, D. T. Avansino, F. B. Kamdar, N. S. Card, M. Wairagkar, ..., S. D. Stavisky, N. AuYong, C. Pandarinath, S. W. Linderman, J. M. Henderson, F. R. Willett. "Cross-brain transfer of high-performance intracortical speech and handwriting BCIs." bioRxiv, version posted 2026-01-14. https://doi.org/10.64898/2026.01.12.699110
- **Licence:** "All rights reserved. No reuse allowed without permission" (bioRxiv page header). We keep **no PDF and no text** in the repo. This page is a summary only.
- **Local raw path:** none. We read the full PDF text once in a private scratch folder on 2026-11-24 (not stored in `references/`).

## TL;DR
A decoder pre-trained on other BrainGate2 users and fine-tuned on a new user beats a decoder trained from scratch, but **only when the new user has little data (< 200 sentences)**. Transfer works only with **trainable, session-specific input layers**. With one shared input layer, transfer was often worse than training from scratch. The gains were "modest".

## Key facts
| Item | Value | Where |
|---|---|---|
| Data | 5 BrainGate2 participants (T5, T12, T15, T16, T18); "48.9 hours" of attempted speech and handwriting, open-ended English | Abstract; Introduction |
| Decoder | "5-layer, stacked gated recurrent unit RNN" (as Willett et al. 2023), CTC to phonemes (speech) or characters (handwriting) | Methods, Architecture |
| Input layer | per session: affine map (W ∈ ℝ^{d×d}, bias) then softsign x / (\|x\| + 1); d = 512 (speech), 768 (handwriting) | Methods, Eq. near line 370 |
| Fine-tuning mix | "30% of training was equally distributed across the source participants' session days, while 70% ... across all target user days" (a replay buffer) | Methods, Training data distributions |
| Main result | transfer "improved performance when training data was limited (< 200 sentences)", for all targets except T18 | Results; Fig. 2 |
| Input-layer ablation | "Without trainable input layers, transfer failed and performed worse than training from scratch" | Abstract; Fig. 3 |
| Permuted-data control | electrode-permuted data of the same user "simulates sampling from another brain with identical neural latent structure". T16 speech, T12 handwriting: transfer as good as permuted data. T12 speech, T15 speech: permuted data better | Abstract; Fig. 4 |
| T18 | "2% character error rate" from scratch with one handwriting session; saturates with "~20 sentences" | Discussion; Results |
| Split | per session 70 % train / 30 % test; sentences reused across participants removed from the target test set | Methods |
| Claim of priority | "the first successful transfer of intracortical speech and handwriting decoders between users" | Discussion |

## Limitations (stated or visible)
- The authors call the gains "modest". They give no gain above about 200 target sentences.
- Offline evaluation only (no closed-loop test of the transferred decoder).
- Five people, three clinical populations (ALS, brainstem stroke, spinal cord injury). The authors think that many more users are needed.
- Same modality only (intracortical to intracortical). No EMG, EEG or other body signal.
- Linear re-alignment may not be enough, because users seem to differ "in the underlying neural latent structure" (Discussion).

## Why it matters for us
- It is the closest prior work to **F3** ([north star](../questions/north-star.md#f3-cross-body-language-model-e1)). It shows **cross-person** transfer of open-vocabulary text decoders. So we must **never claim "first cross-person transfer"** of BCI text decoders.
- It predicts the low-data regime where a transfer gain can appear (< 200 sentences). Our P15-50 test runs at 781 sentences, where this paper finds no gain.
- It names a probable cause of our minutes-scale failure: our E1 model has one shared input stem for all sessions ([F3 check](../questions/novelty-check-2026-11.md#update-2026-11-24-literature-check)).
- The electrode-permuted control is a cheap upper bound for "more data with the same structure". We can copy the idea (not the code).

> **Our take:** the evidence now says "transfer is a low-data effect, and it needs per-session input layers on a shared trunk". This is a mechanism, not only a result. Our next F3 recipe should test exactly this before any new cross-modality arm.

## Feeds
- [North star, F3](../questions/north-star.md#f3-cross-body-language-model-e1)
- [Novelty check, 2026-11-24 update](../questions/novelty-check-2026-11.md#update-2026-11-24-literature-check)
- [FALCON benchmark](falcon-benchmark.md), [Chen et al. 2026 (FALCON H2)](chen-falcon-h2-fewshot.md), [POSSM](possm.md)
- [Willett 2021 handwriting (T5)](../entities/willett-handwriting-2021.md)
- [Data scaling](../concepts/data-scaling.md)
