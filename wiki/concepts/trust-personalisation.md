---
title: Trust personalisation (per-user profiles, drift detection, gated re-calibration)
type: concept
tags: [trust, personalisation, drift, conformal, e-process, online-learning, privacy]
sources: [conformal-risk-control]
updated: 2026-11-16
---

# Trust personalisation (P5-01)

**What it is:** one trust profile per user, plus two anytime-valid drift tests that decide when the user's guard must change. Every change that can add commits goes through the existing gated update path. Code: `fidetype.trust.personal`, `fidetype.trust.drift`. User guide: [docs/trust-personalisation.md](../../docs/trust-personalisation.md). Experiment: [P5-01 results](../../experiments/2026-11-16-p5-01-personal/results.md).

## Parts
| Part | Role | Reuses |
|---|---|---|
| `UserProfile` | Versioned JSON per user: hashed id (HMAC-SHA256), guard, calibration statistics + reference scores, `config_id` history, drift summary, `consent_ref` placeholder (P5-04). No text, no signal | `TrustGuard.to_dict` / `load` |
| `ConformalDriftTest` | Drift of the score distribution (`p_top1`, or the guard risk) | conformal p-values; Simple Jumper martingale |
| `RiskDriftTest` | Observed wrong-commit loss above α | betting e-process |
| `PersonalTrust` | Live controller: decide → feedback → alarm → tighten or propose → gated re-calibration | `TrustGuardUpdater.propose_calibration`, `GuardedUpdateLoop`, `swap_guard` |

## The rule
- **Tighten at once, loosen only through the gate.** A risk alarm sets the commit threshold to infinity (offer only). A higher threshold only removes commits, so it needs no evidence.
- A re-calibration uses only labels collected after the trigger. It passes `calibrate()` (with its null controls), then the loop checks: block LTT, evidence gate, uniform and shuffled null controls, champion / challenger test ([P15-02](../questions/roadmap-standard.md#p15-02-decoder-update-loop-and-re-calibration-hooks)).

## Guarantee of the drift tests
Anytime valid: under the null hypothesis, `P(any alarm over the whole stream) <= level` (Ville's inequality). Methods from the literature, our own code:
- Vovk, Nouretdinov, Gammerman (2003), *Testing exchangeability on-line*, ICML: smoothed conformal p-values are independent and uniform under exchangeability.
- Vovk (2021), *Testing randomness online*, Statistical Science 36(4): the Simple Jumper betting martingale.
- Vovk et al. (2021), *Retrain or not retrain: conformal test martingales for change-point detection*, COPA (PMLR 152).
- Waudby-Smith and Ramdas (2024), *Estimating means of bounded random variables by betting*, JRSSB 86(1).

> **Our take:** the drift tests watch the assumption behind the guard's bound (live data exchangeable with the check block). They do not prove it. Silent errors stay outside the risk test, as in [F1 guarantee scope](../questions/f1-guarantee-scope.md).

## Related
[Adaptive conformal inference](adaptive-conformal-inference.md) · [Conformal risk control](conformal-risk-control.md) · [Learn then Test](learn-then-test.md) · [Provenance ledger](provenance-ledger.md) · [M2-16 online re-calibration](../questions/m2-16-online-recal-result.md)
