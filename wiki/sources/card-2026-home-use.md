---
title: "Long-term independent home use of an intracortical speech and cursor BCI (Card et al. 2026, T15)"
type: source
tags: [implant, intracortical, speech, t15, home-use, continuous-fine-tuning, update-gate, user-ratings, language-model, cursor, f1, novelty-check]
sources: [card-2026-home-use]
updated: 2026-11-24
---

# Card et al. 2026: independent home use by T15

## Citation and links
- N. S. Card, T. Singer-Clark, H. Peracha, C. Iacobacci, X. Hou, M. Wairagkar, Z. Fogg, E. C. Offenberg, L. R. Hochberg, S. D. Stavisky, D. M. Brandman. "Long-term independent use of an intracortical brain–computer interface for speech and cursor control." *Nature Medicine* 32(7):2504–2510 (2026), published online 2026-06-15. https://doi.org/10.1038/s41591-026-04414-6 (PMC13375540). Preprint: bioRxiv 2025.06.26.661591.
- **Licence:** CC BY 4.0 ("Open Access This article is licensed under a Creative Commons Attribution 4.0 International License", article text).
- **Local raw path:** `references/papers/card_2026_natmed_s41591-026-04414-6.pdf` (22 pages, SHA-256 `44813362ad6530b82f6eceb3a9f6ea9506bbfcf02549261a00f842493f0b5abc`) + `.txt` (pdftotext -enc UTF-8). Downloaded 2026-11-24 from nature.com. Git-ignored.
- Data: "Neural data and speech decoding transcripts ... cannot be shared". Figure data and code: github.com/Neuroprosthetics-Lab/NatMed_independent_personal_use (licence not checked).

## TL;DR
T15 (a man with ALS, BrainGate2) used a speech BCI at home, without researchers, for nearly two years. The decoder **fine-tunes itself continuously** during use and keeps a new checkpoint **only if validation performance improves**. T15 **rates every decoded sentence** on a 4-level scale. This is the real self-teaching loop closest to our F1. It has an update gate, but no statistical test, no stated error bound and no null controls.

## Key facts
| Item | Value | Where |
|---|---|---|
| Use | "more than 3,800 h at home with no researchers present"; 444 / 653 days; independent use from post-implant day 281 | Abstract; Results |
| Volume | "183,060 sentences—totaling 1,960,163 words—at an average rate of 56 words per minute" | Abstract |
| Self-rated quality | "He labeled 92% of sentences as being decoded at least mostly correctly" (53.3 % fully correct, 12.9 % corrected by him, 26.1 % mostly correct) | Abstract; Results, Fig. 2b |
| Copy task | 99.2 % word accuracy (transformer, 125,000-word vocabulary); vocalised speech >99 % at 30.6 WPM; silent speech 96.5 % at 49.7 WPM | Main; Results; Fig. 2e |
| Ratings | "label each decoded utterance as '100% correct', 'one word wrong', 'mostly correct' or 'incorrect', with the option to make corrections before rating"; wrong button "on less than 1% of sentences" (self-report, not checked) | Methods, Decoder evaluations |
| Continuous fine-tuning | "both RNN and transformer models underwent continuous fine-tuning"; "Each new sentence had a 67% chance of entering the training buffer and 33% chance of being held out for validation"; "Checkpoints were updated only if validation performance improved"; up to 500 batches per session; batches from the current and three random prior days | Methods, Continuous fine-tuning |
| Labels for training | offline pretraining used copy-task trials and "personal use trials that were confirmed by the participant to be decoded correctly". The fine-tuning paragraph states no rating filter ("Each new sentence") | Methods |
| Decoders | RNN (5 GRU layers × 768) until day 600, then a 12-block causal transformer with a day-specific offset vector | Methods |
| Language model | "beam search decoding with an unpruned n-gram model and large language model rescoring of candidate word sequences" | Methods, latency |
| Cursor | 2.90 ± 0.16 bits per second; RNN cursor decoder cut calibration to 0.8 ± 0.6 min | Results |

## Limitations (stated)
- "It involved a single participant". Wired percutaneous connection; daily setup by care partners.
- "we did not have a way to independently check the ground truth of independent use sentences".
- Accuracy in free conversation "was not consistently as high as it was during structured research sessions".

## Why it matters for us
- **F1 baseline.** The real T15 system already has a validation-improves update gate in daily use. So we must **never claim "first gated decoder update"**. Our F1 novelty is "a statistically tested update gate plus a stated long-run wrong-commit bound with null controls" ([novelty check update](../questions/novelty-check-2026-11.md#update-2026-11-24-literature-check)).
- **A baseline arm for E2.** A "Card rule" arm (random 1/3 hold-out of labelled items, accept if hold-out WER improves) shows what our statistical gate adds.
- **The silent-error gap.** An explicit per-sentence rating makes the noticing rate close to 1. It is a design answer to the gap in [OCP with corrupted feedback](ocp-corrupted-feedback.md).
- Same participant (T15) as our [Brain-to-Text '25](../entities/brain-to-text-25.md) data, but the home-use data is not public.

> **Our take:** Card 2026 proves that "learn from daily use" works in a real home. What it does not show is a guarantee. Its gate compares point estimates on a small random hold-out; a noisy improvement can pass. Our claim must be the guarantee and the tests, never the loop itself.

## Feeds
- [North star F1](../questions/north-star.md#f1-safe-self-improving-bci-e2)
- [Novelty check, C1](../questions/novelty-check-2026-11.md#c1-f1-safe-self-improving-bci)
- [E2 self-teaching write-up](../questions/frontier-e2-self-teaching.md)
- [CORP](corp.md), [Hou et al. 2025 (error signals)](hou-error-encoding.md), [Roy et al. 2026](roy-input-affine-recalibration.md)
