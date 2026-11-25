---
title: "Conformal Alignment: knowing when to trust foundation models with guarantees (Gui, Jin & Ren 2024)"
type: source
tags: [conformal, selection, fdr, precision, llm, guarantee, f2, baseline]
sources: [conformal-alignment]
updated: 2026-11-24
---

# Conformal Alignment (Gui, Jin & Ren 2024)

## Citation and links
- Y. Gui, Y. Jin, Z. Ren. "Conformal Alignment: Knowing When to Trust Foundation Models with Guarantees." NeurIPS 2024 (Advances in Neural Information Processing Systems 37). arXiv:2405.10301 (v3, 2024-11-05). https://arxiv.org/abs/2405.10301
- **Licence:** CC BY 4.0 (arXiv licence link).
- **Local raw path:** `references/papers/gui_jin_ren_2024_conformal_alignment_arxiv_2405.10301v3.pdf` (28 pages, SHA-256 `76773bcfd9138b1ad092ef694c2ba7eb677cc4c140bb2f890439ce6e27be42b2`) + `.txt` (pdftotext -enc UTF-8). Downloaded 2026-11-24. Git-ignored.

## TL;DR
Train a predictor of "this output is acceptable" on a small labelled reference set. Compute conformal p-values for new outputs and select with Benjamini-Hochberg. Then the **false discovery rate** among the selected outputs is at most α, in finite samples, for any model and any data distribution (under exchangeability).

## Key facts
| Item | Value | Where |
|---|---|---|
| Guarantee | "It is guaranteed that on average, a prescribed fraction of selected units indeed meet the alignment criterion, regardless of the foundation model or the data distribution" | Abstract |
| Form | FDR = E[#(selected and not aligned) / #selected] ≤ α; "holds in finite-sample as long as the holdout data are exchangeable with the new units" | §1, eq. (1.1); Theorem 3.1 |
| Basis | Conformalized Selection (Jin & Candès, JMLR 2023); BH threshold on conformal p-values | §3 |
| Applications | question answering (TriviaQA, CoQA; OPT-13B, LLaMA-2-13B-chat); radiology reports (MIMIC-CXR) | §4–5 |
| Data need | "a few hundred high-quality samples suffice to achieve relatively high power"; for CXR "\|D\|=500 already suffices" | §5 |
| Model strength | OPT-13B: almost no selections at α = 0.05; LLaMA-2-13B-chat: power up to 0.50 at α = 0.05 | §4 |

## Limitations (stated)
- "The choice of alignment score in different applications remains an open problem".
- An expectation (FDR) guarantee, not a high-probability one. Exchangeability needed (no drift).

## Why it matters for us
It is a stronger baseline for our **precision bound** ("error rate among commits"). Our `precision_bound` and `joint_ltt(target_precision=)` give a high-probability bound with LTT. Conformal selection gives an in-expectation bound, often less conservative at small n. We should compare both on the cached T15 decodes (CPU).

## Feeds
- [Learn then Test](learn-then-test.md), [conformal risk control](../concepts/conformal-risk-control.md)
- [E3 hallucination write-up](../questions/frontier-e3-hallucination.md)
- [Trust decision](../concepts/trust-decision.md)
