---
title: Adaptive conformal inference (ACI)
type: concept
tags: [conformal, online, distribution-shift, drift, guarantee, trust]
sources: [adaptive-conformal-inference, rolling-risk-control, conformal-pid-control, ocp-corrupted-feedback, decaying-step-ocp]
updated: 2026-11-24
---

# Adaptive conformal inference (ACI)

**Adaptive conformal inference** (Gibbs & Candès, arXiv:2106.00170) keeps a conformal method valid when the data distribution changes over time in an unknown way ([ACI](../sources/adaptive-conformal-inference.md)). It needs no exchangeability. It wraps any black-box predictor.

## How it works
ACI treats the miscoverage level as one parameter α_t. It updates α_t online after each step ([ACI](../sources/adaptive-conformal-inference.md)):

α_{t+1} = α_t + γ (α − err_t),  where err_t = 1 if the step missed (for example, the set missed the truth).

| Item | Value |
|---|---|
| Guarantee | Long-run: the average error over T steps is near α, for **any** sequence. The slack is O(1 / (γ T)) |
| Feedback | Only the realised error of the action taken at step t |
| Large γ | Fast tracking, more jitter |
| Small γ | Smooth, slow, larger slack for a given T |

The bound form on the source page is our restatement of the standard result. Check the paper for the exact statement ([ACI](../sources/adaptive-conformal-inference.md), Limitations).

## How Fidetype uses it
Fidetype uses ACI for **online re-calibration** of the COMMIT threshold in `fidetype.trust.online_risk` (M2-16, our own code) ([CRC concept](conformal-risk-control.md#online-re-calibration-under-drift), [M2-16 result](../questions/m2-16-online-recal-result.md)).

| Method | Rule | Bound (any sequence) |
|---|---|---|
| `aci` | λ ← max(λ_min, λ + η (L − α)), on the threshold itself ([rolling RC](../sources/rolling-risk-control.md), [conformal PID](../sources/conformal-pid-control.md)) | (1/T) Σ L ≤ α + (λ_{T+1} − λ_1)/(η T) |
| `aci_window` | window CRC at level α_t; α_t ← α_t + γ (α − L) ([ACI](../sources/adaptive-conformal-inference.md)) | (1/T) Σ L ≤ α + (α_1 − α_{T+1})/(γ T) |

The older `AdaptiveConformal` class (M2-03) uses ACI for conformal sets. In the [streaming trust layer](streaming-trust-layer.md), the online controller gets one copy per session, and the frozen `commit_p` is its floor: the online loop can make the gate stricter, never looser.

## Evidence (M2-16)
| Case (wrong-commit rate) | Offline CRC | `aci` | `aci_window` |
|---|---|---|---|
| B2T '25 drift case | 0.0625 | 0.0502 | 0.0478 |
| B2T '25 cold start, all 1628 trials, no calibration block | — | 0.0442 | 0.0491 |

The eWPM cost is −0.3 % to −0.6 % ([CRC concept](conformal-risk-control.md#online-re-calibration-under-drift), [M2-16 result](../questions/m2-16-online-recal-result.md)).

## Limits
- The bound is a long-run average. It says nothing about one short window. Windows of 50 trials still reach 0.10–0.12 ([CRC concept](conformal-risk-control.md#online-re-calibration-under-drift)).
- The slack is small only for long streams ([ACI](../sources/adaptive-conformal-inference.md)).
- Silent errors (wrong commits that the user does not notice) are invisible to the update. With noticed-only feedback the true rate can exceed α (EMG 0.058–0.064) ([CRC concept](conformal-risk-control.md#online-re-calibration-under-drift)). Theory: flipped feedback adds a miscoverage term linear in the flip rate that does not shrink with T ([OCP with corrupted feedback](../sources/ocp-corrupted-feedback.md)).
- A fixed step gives only a long-run average. A decaying step η_t ∝ t^(−1/2−ε) keeps the any-sequence guarantee and gives near-target coverage at each time on stable data ([decaying step sizes](../sources/decaying-step-ocp.md)).

> **Our take:** ACI is the complement of [LTT](learn-then-test.md) and CRC. LTT and CRC give a guarantee at the start of a session from a calibration block. ACI keeps the error rate near α when the session drifts. A live trust layer needs both: an offline start, then an online update. Always report ACI results as "long-run average over T items of this session", with the silent-error rate next to them.

## Related
- [Conformal risk control](conformal-risk-control.md)
- [Learn then Test](learn-then-test.md)
- [Streaming trust layer](streaming-trust-layer.md)
- [F1 guarantee scope](../questions/f1-guarantee-scope.md) (P15-04: ACI needs only the realised loss, so it stays valid when the user labels only shown text; IPW audit with forced exploration)
