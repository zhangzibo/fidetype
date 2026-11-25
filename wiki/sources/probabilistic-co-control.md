---
title: "Probabilistic Co-Control in BCIs: uncertainty as a control signal in brain-to-text (Huang et al. 2026)"
type: source
tags: [calibration, uncertainty, ctc, cross-entropy, brain-to-text, t12, t15, language-model, f2, novelty-check]
sources: [probabilistic-co-control]
updated: 2026-11-24
---

# Probabilistic Co-Control (Huang et al. 2026)

## Citation and links
- J. Huang, S. M. Narasimha, A. N. Patel, R. D. Sristi, G. Mishne, V. Gilja. "Probabilistic Co-Control in Brain-Computer Interfaces: Uncertainty as a Control Signal in Brain-to-Text Decoding." bioRxiv, v1 posted 2026-04-06. https://doi.org/10.64898/2026.04.02.715749 (Europe PMC PPR1216238). Preprint, not peer reviewed.
- Earlier workshop version: "Prototyping Co-Control BCIs Through Brain-to-Text", NeurIPS 2025 workshop ([reading list](../questions/reading-list.md)).
- **Licence:** "This pre-print is available under a Creative Commons License (Attribution 4.0 International), CC BY 4.0" (bioRxiv page).
- **Local raw path:** `references/papers/huang_2026_probabilistic_co_control_biorxiv.pdf` (34 pages, SHA-256 `a153212695de22bba822e8737524d7cf192bc0317b4b52fc1811e03e4bc0b1d5`) + `.txt`. Downloaded 2026-11-24. Git-ignored.

## TL;DR
CTC brain-to-text decoders are over-confident: they stay confident when they are wrong. A two-stage cross-entropy (CE) loss, with CTC-derived alignments as fixed targets, gives more informative probabilities. A product-of-experts fusion of CTC and CE gives the best calibration. Better probabilities help language-model fusion.

## Key facts
| Item | Value | Where |
|---|---|---|
| Problem | CTC decoders "produce systematically over-confident predictions, with high confidence persisting even when predictions are incorrect" | Abstract |
| Data | public T12 and T15 data | Methods |
| CTC calibration | ECE T12 0.027, T15 0.011; incorrect frames still get confidence "avg. 0.817 ± 0.188" | §3 |
| CE vs CTC | CE has **higher** ECE ("CTC 0.025 vs CE 0.051"; CE is under-confident) but better resolution ("CTC 0.017 vs CE 0.022") and AUPR (0.426 ± 0.016 vs 0.469 ± 0.006) | §3.3 |
| Fusion | the CTC ⊗ CE product of experts "reduce[s] frame- and word-level calibration error"; best at α = 0.5 | §3 |
| Accuracy | abstract: "without degrading decoding accuracy"; body: PER "CTC:0.212±0.009 vs CE:0.232±0.002" | Abstract; §3 |
| LM gain | "ΔWER: 0.222 for pCE vs 0.184 for pCTC" | §3 |
| Drift | under channel dropout and cross-day drift, "CE-trained models exhibit increased uncertainty as accuracy deteriorates"; CTC stays confident | Fig. 6B |

> **Contradiction:** the abstract says CE gives better probabilities "without degrading decoding accuracy". The body shows a small PER cost (0.212 vs 0.232). Our [novelty check of 2026-11-15](../questions/novelty-check-2026-11.md#c2-f2-faithful-llm-decoding) also wrote "a cross-entropy objective gives better calibration (ECE, resolution)" from the abstract. The full text shows that CE alone has a higher ECE; only the fusion lowers it. We keep both statements and use the full-text numbers.

## Limitations
- Calibration metrics only. No stated error bound, no commit / abstain rule with a guarantee, and no check of LLM text against the neural evidence.
- "Reliable error detection" is abstract wording; we found no separate error-detection experiment beyond AUPR.
- No code link found.

## Why it matters for us
- It is the closest BCI work to **F2** and the most likely competitor. It names the same problem: confidence after decoding is not trustworthy.
- It supports our design choice to calibrate per output and not trust raw CTC confidence ([trust decision](../concepts/trust-decision.md)).

> **Our take:** a risk-controlled commit rule on top of the CE or fusion probabilities is the natural next step for this group. Our C2 window is short. Our bound does not need calibrated probabilities (it is distribution-free), but better scores would raise our commit rate.

## Feeds
- [Novelty check, C2](../questions/novelty-check-2026-11.md#c2-f2-faithful-llm-decoding) and [2026-11-24 update](../questions/novelty-check-2026-11.md#update-2026-11-24-literature-check)
- [E3 hallucination write-up](../questions/frontier-e3-hallucination.md)
- [Confidence-ordering reversal](confidence-ordering-reversal.md)
