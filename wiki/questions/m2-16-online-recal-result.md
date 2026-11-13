---
title: "M2-16 result: online re-calibration of the wrong-commit guarantee under drift"
type: question
tags: [trust, conformal, risk-control, online, drift, wrong-commit, b2t25, emg, meg]
sources: [adaptive-conformal-inference, conformal-pid-control, rolling-risk-control, conformal-beyond-exchangeability, non-exchangeable-crc, conformal-covariate-shift, conformal-risk-control, brain-to-text-25-copytask, toronto-semg-typing]
updated: 2026-11-11
---

# Can the trust gate keep wrong-commit ≤ 0.05 under drift inside a session?

**Short answer: yes, on average over the session, with online re-calibration from the user's corrections.** Offline CRC broke under within-day drift (B2T '25: 0.0625; EMG cross-session: 0.0635). Online methods bring both to 0.040–0.053 at an eWPM cost of ≤ 0.6 %. Two of them carry a long-run bound for any sequence. No method controls short windows of 50 trials. Silent errors (wrong commits the user does not notice) remain outside every guarantee.

Experiment page: [M2-16 results](../../experiments/2026-11-11-m2-16-online-recal/results.md). Code: `fidetype.trust.online_risk`.

## The problem
[M2-13](m2-13-conformal-result.md) set the COMMIT threshold with [conformal risk control](../concepts/conformal-risk-control.md). CRC needs the calibration items and the later items to be exchangeable. On [B2T '25](../sources/brain-to-text-25-copytask.md) the later trials of a day have more errors at the same confidence. CRC calibrated on the earlier halves gave 0.0625 on the later halves.

## Which feedback is available
| action | the system learns | delay |
|---|---|---|
| COMMIT, user corrects | wrong (loss 1) | until the user notices |
| COMMIT, no correction | right, *if* silence means right | a timeout |
| OFFER, user picks or retypes | the truth, so also "would the top-1 have been right?" | end of the item |
| ABSTAIN / gives up | nothing | — |

Two levels follow. **Realised loss** is always known. **Full feedback** (the counterfactual commit loss of non-committed items) needs the final text.

## Methods (all in `OnlineCommitRiskControl`)
| method | idea | guarantee | feedback | source |
|---|---|---|---|---|
| `window` | CRC on the last N items with known truth | approximate (weighted CRC bound) | full | [Barber et al.](../sources/conformal-beyond-exchangeability.md), [Farinhas et al.](../sources/non-exchangeable-crc.md) |
| `window` + `decay` | weights ρ^age | approximate | full | same |
| `aci` | λ ← max(λ_min, λ + η (L − α)) | (1/T) Σ L ≤ α + (λ_{T+1} − λ_1)/(η T), **any sequence** | realised loss only | [Gibbs & Candès](../sources/adaptive-conformal-inference.md), [conformal PID](../sources/conformal-pid-control.md), [rolling RC](../sources/rolling-risk-control.md) |
| `aci_window` | window CRC at level α_t; α_t ← α_t + γ (α − L) | (1/T) Σ L ≤ α + (α_1 − α_{T+1})/(γ T), **any sequence** | full (window) + realised | [Gibbs & Candès](../sources/adaptive-conformal-inference.md) |

API: same as `CommitRiskControl` (`fit`, `fit_policy`, `threshold`, `apply(policy, combine)`) plus `decide(score) → Ticket`, `observe(ticket, commit_loss, fallback_loss)` (any order, any delay; `None` = truth unknown), `report()` (realised rate + certificate). `OnlineTrustPolicy(policy, controller)` wraps any `DecisionPolicy`: `decide(PolicyInputs)` and `feedback(ticket, final_text)`. It reads only `PolicyInputs`, so it works for any decoder that emits a NeuralTextStream.

## Results (drift protocol: warm start on earlier data, later data in time order)
| data | offline CRC | window | decay | aci | aci_window |
|---|---|---|---|---|---|
| B2T ours: wrong-commit | **0.0625** | 0.0453 | 0.0417 | 0.0502 | 0.0478 |
| B2T ours: eWPM (old gate 11.546) | 11.553 | 11.490 | 11.500 | 11.510 | 11.489 |
| B2T published: wrong-commit / eWPM | 0.0490 / 18.80 | 0.0429 / 18.77 | 0.0392 / 18.74 | 0.0478 / 18.80 | 0.0453 / 18.77 |
| EMG cross-session: wrong-commit / eWPM | **0.0635** / 4.657 | 0.0508 / 4.669 | 0.0399 / 4.670 | 0.0526 / 4.667 | 0.0490 / 4.668 |
| MEG M1-15: wrong-commit (all commits wrong) | 0.0220 | 0.0141 | 0.0188 | 0.0173 | 0.0141 |

- Feedback 10 trials late changes little (B2T ours: 0.0404–0.0502).
- Cold start over all 1628 B2T trials (no calibration block): `aci` 0.0442, `aci_window` 0.0491; window 0.0516.
- The maximum over 50-trial windows is 0.10–0.12 for every method. An i.i.d. Bernoulli(0.05) sequence gives the same (median 0.120).
- Noticed-only feedback (silent errors look right): `aci` 0.0515 (B2T), 0.0635 (EMG cross-session).

> **Our take:** Use `aci_window` as the default in-session gate when the final text is logged (OFFER picks, retyped text): it was ≤ 0.05 in every drift case and has the any-sequence bound. Use `aci` when only corrections of commits are logged: it needs the least feedback and still has the bound, but it sits *at* α, not below. The window methods were the most conservative on B2T, but they have no bound under drift, so we would not claim a guarantee with them. Always report the guarantee as "long-run average over T items of this session", plus the silent-error rate next to it. A per-window promise ("never more than 1 wrong commit in 20") is a different, harder goal; it needs a stricter α or a different method.

> **Contradiction:** M6-07 reported CRC wrong-commit 0.004 on EMG cross-session; here offline CRC gives 0.0635. Both are right. M6-07 combined CRC with the stricter grid threshold (`combine="max"`); this page uses the pure CRC threshold. The pure threshold shows the drift that the grid threshold hid.

## Related
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md)
- [M2-13 conformal result](m2-13-conformal-result.md)
- [Per-session risk control](per-session-risk-control.md) (A2: per-day guarantee, session-start block, e-process monitor)
- [B2T '25 trust result](b2t25-trust-result.md)
- [EMG Toronto trust result](emg-toronto-trust-result.md)
- Spec section 2.3 informative note (`spec/neuraltextstream-v0.1.md`)
