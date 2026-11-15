---
title: Learn then Test (LTT)
type: concept
tags: [conformal, risk-control, multiple-testing, calibration, trust, guarantee]
sources: [learn-then-test, conformal-risk-control]
updated: 2026-11-15
---

# Learn then Test (LTT)

**Learn then Test** (Angelopoulos, Bates, Candès, Jordan & Lei, arXiv:2110.01052) chooses a threshold λ so that a risk stays below α **with high probability**: P(R(λ̂) ≤ α) ≥ 1 − δ over the calibration draw ([LTT](../sources/learn-then-test.md)). [Conformal risk control](conformal-risk-control.md) (CRC) bounds only the mean, E[R] ≤ α ([CRC](../sources/conformal-risk-control.md)).

## How it works
LTT turns risk control into **multiple hypothesis testing** ([LTT](../sources/learn-then-test.md)).

| Step | Detail |
|---|---|
| 1. Grid | Fix a grid of λ values **before** you see the data |
| 2. Hypotheses | For each λ: H0: R(λ) > α ("this λ is unsafe") |
| 3. p-values | From the calibration losses: Hoeffding, Bentkus, or combined Hoeffding–Bentkus for losses in [0, 1]; exact binomial tails for 0/1 losses |
| 4. FWER control | Reject at level δ with Bonferroni, or with **fixed-sequence testing** when the risk is monotone in λ (start at the safest λ, stop at the first acceptance) |
| 5. Pick | Any rejected λ is safe with probability ≥ 1 − δ |

It works for any model, without refitting. Unlike CRC, it does not need a monotone loss.

## LTT vs CRC
| | CRC | LTT |
|---|---|---|
| Guarantee | E[risk] ≤ α | P(risk ≤ α) ≥ 1 − δ |
| Loss | bounded, non-increasing in λ | bounded; monotone not needed |
| Conservatism | less | more (controls a tail, not a mean) |
| Data | exchangeable calibration | exchangeable calibration |

## How Fidetype uses it
- `fidetype.trust.ltt_threshold(..., delta, grid, pvalue)`: grid 1.00 → 0.00, H0: R(λ) > α, exact binomial or Hoeffding–Bentkus p-values, fixed-sequence testing at δ. The risk is the wrong-commit rate of the COMMIT threshold ([CRC concept](conformal-risk-control.md)).
- Any λ ≥ λ̂ keeps the guarantee, so a threshold tuned for eWPM can be combined as max(tuned, λ̂) ([CRC concept](conformal-risk-control.md)). The frozen Paper 1 configuration of the [streaming trust layer](streaming-trust-layer.md) uses this "LTT max" form.
- B2T '25 (M2-13): with LTT the mean wrong-commit is 0.035 and the 95th percentile 0.056–0.061. With CRC the 95th percentile is 0.071–0.076. The eWPM cost of LTT is −0.4 % at 408 calibration trials ([M2-13 result](../questions/m2-13-conformal-result.md)).
- Per session: LTT needs n ≥ 45 labelled items of that session (α = 0.05, δ = 0.1, 0 errors) ([per-session risk control](../questions/per-session-risk-control.md)).
- The [open benchmark](open-benchmark.md) has a CRC / LTT guarantee column.
- Our T15 GRU decoder (M2-19, 2026-11-15): LTT on 351 calibration trials gave λ̂ 0.33; the grid commit_p 0.4 was stricter. Held-out wrong-commit 0.0086 (CP95 upper 0.0185) at a commit rate of only 0.013, with 6 of 9 commits wrong ([streaming trust layer](streaming-trust-layer.md#re-tuned-config-for-our-retrained-t15-decoder-m2-19-2026-11-15)).

## Limits
- The grid must be fixed before the data ([LTT](../sources/learn-then-test.md)).
- It needs exchangeable (i.i.d.) calibration data ([LTT](../sources/learn-then-test.md)). Drift breaks it: use [adaptive conformal inference](adaptive-conformal-inference.md) for online re-calibration.
- The guarantee is for the calibration distribution. Items from many days give a guarantee for the mix of days, not for each day ([CRC concept](conformal-risk-control.md#per-session-guarantee-track-a-item-2)).

> **Our take:** For a claim about one session ("this user will rarely see more than α wrong commits"), LTT is the safer wording than CRC. On B2T '25 it costs little eWPM. Its real price is the minimum calibration size per session.

## Related
- [Conformal risk control](conformal-risk-control.md)
- [Adaptive conformal inference](adaptive-conformal-inference.md)
- [`trust_decision` event](trust-decision.md)
