---
title: "Continual Calibration: coverage can collapse before accuracy in lifelong LLM fine-tuning (Shihab et al. 2026)"
type: source
tags: [conformal, continual-learning, model-updates, coverage, guarantee, novelty-check]
sources: [continual-calibration]
updated: 2026-11-15
---

# Continual Calibration (coverage under repeated model updates)

## Citation and links
- I. F. Shihab, S. Akter, A. Sharma. "Continual Calibration: Coverage Can Collapse Before Accuracy in Lifelong LLM Fine-Tuning." arXiv:2604.23987 [cs.LG]. v1 27 Apr 2026. https://arxiv.org/abs/2604.23987
- **Licence:** arXiv non-exclusive distribution licence 1.0. We do not store the PDF.
- **Local raw path:** none. We read the arXiv abstract and the HTML full text (arxiv.org/html/2604.23987) on 2026-11-15.

## TL;DR
When a language model is fine-tuned on one task after another, conformal coverage drops faster than accuracy (about 3.4× more on average). The fix, **calibration replay**, keeps a small labelled held-out buffer per task. After each model update it refits the conformal threshold under the new model. A theorem gives exact finite-sample coverage for that step.

## Key facts
| Item | Value |
|---|---|
| Setting | sequential supervised fine-tuning of LLMs; classification and multiple-choice tasks |
| Main finding | coverage loss ≈ 3.4× ± 0.5× accuracy loss; worst case coverage 0.92 → 0.61 with accuracy within 3 points (abstract) |
| Method | after each update θ_k: recompute scores on each task buffer B_j under θ_k; set a per-task threshold (Section 6, Algorithm 1) |
| Guarantee | Section 5, Theorem 6: coverage ≥ 1 − α when the buffer is "held out from gradient updates and exchangeable with" a test point from that task, model fixed at step k |
| Buffer size | m = 200 restores coverage to within about 2 points of nominal (abstract) |
| Stated limits | needs labelled calibration data per task; classification-style tasks; open-ended generation is exploratory (Section 8) |

## Why it matters for us
It shows that "keep a stated error bound valid after each model update" already exists in general machine learning, outside BCI. So the F1 claim must be BCI-specific and must not say that the guarantee mechanism is new. It also does not use user feedback as labels: it needs a labelled held-out buffer. This matches our own note that a per-session finite-sample bound needs a fresh labelled block after each update ([north star](../questions/north-star.md#honest-risks)).

## Feeds
- [Novelty check 2026-11](../questions/novelty-check-2026-11.md#c1-f1-safe-self-improving-bci)
- [Adaptive conformal inference (source)](adaptive-conformal-inference.md): the long-run alternative that needs no buffer
