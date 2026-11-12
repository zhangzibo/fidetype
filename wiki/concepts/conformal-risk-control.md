---
title: Conformal risk control (CRC) and Learn then Test (LTT)
type: concept
tags: [conformal, risk-control, trust, calibration, wrong-commit, guarantee]
sources: [conformal-risk-control, learn-then-test, brain-to-text-25-copytask]
updated: 2026-11-11
---

# Conformal risk control and Learn then Test

## What it is
A method to set a threshold λ so that a chosen **risk** stays below a target α, with a **finite-sample guarantee**. Split conformal prediction controls one risk (miscoverage). CRC controls the expected value of any bounded loss that is non-increasing in λ ([CRC](../sources/conformal-risk-control.md)). LTT gives a high-probability version through multiple testing ([LTT](../sources/learn-then-test.md)).

## How Fidetype uses it
The trust gate commits the top-1 text if its calibrated `p_top1` ≥ `commit_p`. The risk is the **wrong-commit rate**.

| step | detail |
|---|---|
| Score s_i | `p_top1` if the other policy rules allow COMMIT, else −inf |
| Loss L_i(λ) | if s_i ≥ λ: the commit loss (1 if top-1 ≠ truth); else the loss of the non-commit action (0, or an upper bound for OFFER_WORDS). Made monotone with max(c_i, f_i) |
| CRC | λ̂ = smallest λ with (n R̂(λ) + 1) / (n + 1) ≤ α. Guarantee: E[wrong-commit] ≤ α |
| LTT | grid 1.00 → 0.00; H0: R(λ) > α; exact binomial (0/1 losses) or Hoeffding–Bentkus p-values; fixed-sequence testing at δ. Guarantee: P(R ≤ α) ≥ 1 − δ |
| No feasible λ | λ̂ = +inf: never commit. For CRC this happens if n < 1/α − 1 (19 for α = 0.05) |
| Stricter is still valid | Any λ ≥ λ̂ keeps the guarantee. So an eWPM-tuned threshold can be combined as `max(tuned, λ̂)` |

API (all in `fidetype.trust`):
- `crc_threshold(scores, commit_losses, alpha, fallback_losses=None)` and `ltt_threshold(..., delta, grid, pvalue)` return a `RiskControlResult` (threshold, feasible, n, bound, commit rate).
- `commit_calibration_data(policy, inputs, truths)` builds the scores and losses from any `DecisionPolicy` and its `PolicyInputs`. So it works for any decoder that emits a NeuralTextStream and goes through the trust core.
- `CommitRiskControl(alpha, method, delta).fit_policy(policy, inputs, truths).apply(policy, combine)`.
- Harness: `HarnessConfig(risk_control="crc" | "ltt", risk_control_fraction, risk_control_delta, risk_control_combine)`, or `TrustPipeline.calibrate_commit(items, ...)`.

## Assumptions
- **Exchangeability.** Calibration items and later items must be exchangeable. In practice: calibrate **per user and per session**, on items with known truth (for example a short copy block at the start of the session). Drift breaks the guarantee: on B2T '25 the later half of each day gave 0.0625 after CRC on the earlier half ([M2-13 result](../questions/m2-13-conformal-result.md)).
- **Fixed upstream.** Temperatures, conformal sets, guard and the other policy thresholds must come from other data.
- **Marginal.** CRC bounds a mean. A single session can be above α (B2T: 95th percentile 0.071–0.094). Use LTT when the tail matters.

## Evidence
- B2T '25: CRC mean wrong-commit 0.046–0.048 vs old gate 0.059; LTT 0.019–0.035; eWPM cost ≤ 0.4 % at 408 calibration trials ([M2-13 result](../questions/m2-13-conformal-result.md)).

> **Our take:** CRC is the right default for the 0.05 promise, but the promise must carry its scope: "expected wrong-commit ≤ 0.05 for this user in this session, given n calibration sentences". For a claim about single sessions, LTT is the safer wording. For live drift, pair it with adaptive conformal inference (`AdaptiveConformal`, Gibbs & Candès 2021).

## Related
- [B2T '25 trust result](../questions/b2t25-trust-result.md) (the 0.059 that motivated M2-13)
- [Trust core v0 results](../questions/trust-core-v0-results.md)
- [Error metrics](error-metrics.md)
