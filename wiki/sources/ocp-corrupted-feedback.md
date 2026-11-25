---
title: "Online conformal prediction with corrupted feedback (Wang, Zecchin & Simeone 2026)"
type: source
tags: [conformal, online, aci, feedback, label-noise, silent-errors, guarantee, f1]
sources: [ocp-corrupted-feedback]
updated: 2026-11-24
---

# Online conformal prediction with corrupted feedback (2026)

## Citation and links
- B. Wang, M. Zecchin, O. Simeone. "Online Conformal Prediction with Corrupted Feedback." arXiv:2605.20515 (v1, 2026-05-19; cs.LG, eess.SP). https://arxiv.org/abs/2605.20515
- **Licence:** arXiv non-exclusive distribution 1.0. We do not store the PDF.
- **Local raw path:** none. Abstract page and HTML full text read on 2026-11-24.

## TL;DR
Online conformal prediction (OCP, the ACI family) updates its threshold from a "miscovered or not" signal. If that signal is sometimes flipped, the long-run miscoverage error gets an extra term that grows with the flip rate and does not shrink with time. Two fixes: **F-ROCP** filters feedback on rounds where the true gradient is known, and **AC-ROCP** adds a compensation term with an estimated flip rate.

## Key facts
| Item | Value | Where |
|---|---|---|
| General bound | MisCov(T) ≤ (B+η)/(ηT) + \|G^T_{0→1} − G^T_{1→0}\|/T + max{α G^T_{1→0}, (1−α) G^T_{0→1}}/T; G counts flips of the update gradient in each direction; B = score bound; η = fixed step | Theorem 1, eq. (13) |
| i.i.d. flips at rate p | MisCov(T) ≤ (B+η)/(ηT) + 2(p + √(log(1/δ)/(2T))) with probability ≥ 1−δ; "the miscoverage error of OCP scales linearly with the feedback corruption probability p" | Corollary 1, eq. (29) |
| Flip model | general: no assumption on the error sequence; i.i.d. model: the same p for both directions; Markov model in experiments | §IV, §VII |
| F-ROCP | needs no side information; "replaces the term O(2p) by O(p\|I\|/T)" | Corollary 2 |
| AC-ROCP | known p, or p estimated in "active training rounds" (first \|P\| = 50 rounds) that play a full or an empty set, so the flip can be read without true labels; error terms vanish as T → ∞ if the training phase grows | §V-A2, §VI-B2, Corollary 3 |
| Adversarial memory model | "since the corruption-dependent term does not vanish as T→∞, the miscoverage error may persist indefinitely under adversarial corruption" | Corollary 4, §VII-C |
| Experiments | CIFAR-100 (T = 10,000, α = 0.1) and AVA regression (T = 15,557); figures only | §VIII |

## Limitations
- Not BCI. Symmetric or Markov flip models. Results are in figures, with no tables.
- The AC-ROCP trick (play a full or empty set) has no clear BCI equivalent: an "empty set" is a withheld item; a "full set" is not possible for free text.

## Why it matters for us
This is the theory for our **silent-error gap** in F1. In E2, ACI sees the *observed* loss. A wrong commit is seen only with probability q (`p_notice`). Our flips are **one-sided** (a miss is read as "right", never the reverse). So, when ACI is the binding threshold, it drives the observed rate to α, and the true rate tends to α / q (0.05 / 0.9 ≈ 0.0556 for U1). This is our arithmetic, not the paper's. Our P15-04 replay shows the same pattern (true 0.0556, observed 0.0456; [F1 guarantee scope](../questions/f1-guarantee-scope.md#what-is-not-guaranteed)).

> **Our take:** a one-sided flip model is simpler than theirs: E[observed] = q · E[true]. A target α_obs = α · q̂, with q̂ a lower confidence bound on the noticing rate, is the direct fix. In a live system, q̂ can come from random confirmation prompts. The related query model of [Skalse et al. 2026](https://arxiv.org/abs/2608.07139) (OCPQ: coverage ≥ β − O(T^-1/3) "while querying only an expected T^{-1/3} fraction of rounds"; CC BY 4.0, abstract checked 2026-11-24) gives a theory for such prompts.

## Feeds
- [F1 guarantee scope](../questions/f1-guarantee-scope.md), [F1 online guarantees](../questions/frontier-f1-online-guarantees.md)
- [ACI (concept)](../concepts/adaptive-conformal-inference.md), [ACI (source)](adaptive-conformal-inference.md)
- [Card et al. 2026](card-2026-home-use.md): explicit per-sentence ratings make q close to 1
