---
title: "Online conformal prediction with decaying step sizes (Angelopoulos, Barber & Bates 2024)"
type: source
tags: [conformal, online, aci, step-size, guarantee, f1]
sources: [decaying-step-ocp]
updated: 2026-11-24
---

# Online conformal prediction with decaying step sizes (2024)

## Citation and links
- A. N. Angelopoulos, R. F. Barber, S. Bates. "Online conformal prediction with decaying step sizes." ICML 2024, PMLR 235. arXiv:2402.01139 (v2, 2024-05-28). https://arxiv.org/abs/2402.01139 . Code: github.com/aangelopoulos/online-conformal-decaying.
- **Licence:** arXiv non-exclusive distribution 1.0. We do not store the PDF.
- **Local raw path:** none. Abstract and HTML full text read on 2026-11-24.

## TL;DR
ACI with a fixed step size gives only a long-run average coverage. Its coverage at one time point can swing a lot. With a **decaying step size** η_t ∝ t^(−1/2−ε), the method keeps the guarantee for any sequence, and on stable data the coverage is near the target at **every** time point.

## Key facts
| Item | Value | Where |
|---|---|---|
| Any sequence | "ours possesses a retrospective guarantee of coverage for arbitrary sequences" | Abstract |
| Stable data | "the coverage is close to the desired level for every time point, not just on average over the observed sequence" | Abstract |
| Schedule | η_t ∝ t^(−1/2−ε), small ε ∈ (0, 1/2); adversarial long-run error O(1/T^(1/2−ε)); i.i.d. convergence | §1.1, §3 |
| Theorem 1 | nonincreasing η_t, scores in [0, B]: \|(1/T)Σ 1{Y_t ∈ C_t} − (1−α)\| ≤ (B + η_1)/(η_T T) | §3 |
| Theorem 2 | arbitrary step sequence (for example, raise η after a detected shift): bound (B + max η_t)/T · ‖Δ_{1:T}‖₁ | §3 |
| Fixed step | with online-trained scores, liminf coverage 0 and limsup 1 almost surely (Proposition 3) | §4 |
| Experiments | Elec2 (shift), ImageNet (exchangeable); fixed η 0.05 vs decaying η_t = t^(−0.6), α = 0.1 | §5 |

## Limitations
- The per-time result needs a stable distribution. Under drift, the decaying step reacts slowly unless η is reset (Theorem 2).
- Coverage, not risk control; the authors name online risk control as future work.

## Why it matters for us
Our `aci` controller uses a fixed step. Its long-run bound says little about one session ([F1 guarantee scope](../questions/f1-guarantee-scope.md#what-is-not-guaranteed)). A decaying step (with a reset at a detected drift or a decoder update) is a cheap descriptive arm for a CPU replay of recorded scores.

## Feeds
- [ACI (concept)](../concepts/adaptive-conformal-inference.md)
- [F1 online guarantees](../questions/frontier-f1-online-guarantees.md)
