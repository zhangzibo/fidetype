---
title: "Confident and adaptive generative speech recognition via risk control (Damri & Laufer-Goldshtein, ICLR 2026)"
type: source
tags: [asr, llm, error-correction, learn-then-test, risk-control, f2, abstract-only]
sources: [damri-risk-controlled-asr]
updated: 2026-11-24
---

# Risk-controlled generative ASR (Damri & Laufer-Goldshtein 2026)

## Citation and links
- A. Damri, B. Laufer-Goldshtein. "Confident and Adaptive Generative Speech Recognition via Risk Control." ICLR 2026. OpenReview https://openreview.net/forum?id=ck5T7QeiDh ; ICLR poster page https://iclr.cc/virtual/2026/poster/10008472 . Code: github.com/amitdamritau/adaptive-ger.
- **Licence:** **not verified** (OpenReview refused automated access on 2026-11-24). We store nothing.
- **Local raw path:** none. **Abstract level only:** title, authors and abstract from the ICLR poster page and the ML Anthology record. A search-engine snippet gave the title as "...via Conformal Risk Control"; the fetched poster page says "...via Risk Control". Check by hand.

## TL;DR
An LLM corrects ASR output from the n-best hypotheses. The method chooses, per input, how many hypotheses the LLM sees, from the ASR confidence, with Learn then Test. It bounds the expected relative WER degradation against the best size.

## Key facts (abstract)
- "We propose an adaptive framework that dynamically determines the optimal number of hypotheses for each input using risk control. This mechanism leverages ASR confidence scores and applies Learn then test (LTT)".
- The risk: "the expected relative word error rate degradation compared to the best achievable performance for a given model and hypothesis set".
- "our approach provides theoretical guarantees with high-probability bounds while matching or exceeding fixed-size correction baselines and requiring fewer hypotheses on average".
- The README names Whisper top-5 hypotheses, LoRA fine-tuning and "Learn Then Test (LTT) and Pareto testing". Per-dataset numbers were seen only on a third-party summary site; we do not quote them.

## Limitations
- Not neural data. The risk is WER degradation; there is no commit / abstain decision and no check against an evidence signal.
- Not read in full.

## Why it matters for us
It is the closest non-neural method to F2: LTT around an LLM that rewrites recogniser output. Paper 1 must cite it ([paper 1 plan](../questions/paper1-plan.md)).

## Feeds
- [Learn then Test](learn-then-test.md)
- [Reading list](../questions/reading-list.md)
- [E3 hallucination write-up](../questions/frontier-e3-hallucination.md)
