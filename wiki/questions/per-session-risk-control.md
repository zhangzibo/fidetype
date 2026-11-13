---
title: "Per-session risk control: can the gate hold alpha on every day, not only on the mix of days?"
type: question
tags: [trust, risk-control, ltt, per-session, mondrian, e-process, monitoring, wrong-commit, b2t25, emg, paper1]
sources: [learn-then-test, conformal-risk-control, rolling-risk-control, brain-to-text-25-copytask, toronto-semg-typing]
updated: 2026-11-13
---

# Per-session risk control (Track A item 2)

**Short answer: yes, but only with at least 45 labelled sentences in the session.** The Paper 1 rule (LTT max) bounds the wrong-commit rate of the calibration mix of days. On the published gate, day 34 ran at about 2α. An offer-only warm-up of k ≥ 45 sentences, then LTT on those sentences, removed the problem with a per-session guarantee: day 34 0.103 → 0.034, 0 of 14 days above α, eWPM −2.2 %. Methods with fewer labels either never commit or do not fix day 34.

Experiment: [experiments/2026-11-13-a2-per-session-risk/results.md](../../experiments/2026-11-13-a2-per-session-risk/results.md) (tables: [tables.md](../../experiments/2026-11-13-a2-per-session-risk/results/tables.md)). Code: `src/fidetype/trust/session_risk.py`.

## The problem
- LTT gives P(R(λ) ≤ α) ≥ 1 − δ for the risk R of the calibration distribution ([LTT](../sources/learn-then-test.md)). In Paper 1, that distribution is the mix of 14 B2T '25 days ([B2T '25](../sources/brain-to-text-25-copytask.md)).
- The mix can be below α while one day is above it. Paper 1 R4: published gate, day 34, 0.098 over 200 random re-splits.
- A user meets one session at a time. So the useful target is R_session ≤ α.

## A hard floor: 45 labelled items
With 0/1 losses and an exact binomial p-value, LTT can certify R ≤ α only if (1 − α)^n ≤ δ. For α = 0.05 and δ = 0.1, **n ≥ 45** (0 errors). With 1 error, n ≥ 77; with 2 errors, n ≥ 105. No per-session finite-sample guarantee exists below this floor. So blocks of k = 10, 20 or 40 sentences can never certify a commit threshold.

## Methods tested

| method | labels per session | guarantee |
|---|---|---|
| Global LTT max (Paper 1) | 0 | mix of days only |
| Mondrian LTT (per-day calibration; fallback for n < 45) | the day's calibration items | per day only if n ≥ 45 |
| Block LTT, warm-up (W): k items offer-only, then max(global, LTT on block) | k (from the OFFER picks) | **per session**, P ≥ 1 − δ, if the session is exchangeable |
| Block LTT, feedback (F): block runs at the global threshold | k (from corrections) | per session after the block only |
| Block test: exact test of R ≤ α on the block → offer-only | k | false alarm ≤ γ only |
| Online monitor: e-process, alarm → offer-only | feedback | false alarm ≤ γ at any time; no risk bound |
| ACI ([M2-16](m2-16-online-recal-result.md)) | feedback | long-run average |
| Empirical-Bayes shrinkage † | k | **none** |

The monitor is a betting e-process: K_t = mean_j Π_i (1 + b_j (L_i − α)), with Kelly bets b_j for alternatives 0.075–0.30. Under H0 (each conditional risk ≤ α), K_t is a non-negative supermartingale. Ville's inequality gives P(sup K_t ≥ 1/γ) ≤ γ. It is our implementation of a standard construction.

## Results: day 34, published gate (random re-splits, R = 200)

| method | day 34 | days > α (of 14) | mean commit | mean eWPM |
|---|---|---|---|---|
| Global LTT max | 0.103 | 1 | 0.381 | 18.59 |
| Mondrian, fallback global | 0.098 | 1 | 0.375 | 18.58 |
| Mondrian, fallback never | 0.000 | 0 | 0.017 | 18.08 |
| **Block LTT k = 45, W** | **0.034** | **0** | 0.107 | 18.19 |
| Block LTT k = 60, W | 0.006 | 0 | 0.065 | 18.14 |
| Block LTT k = 45, F | 0.073 | 1 | 0.317 | 18.50 |
| Block test k = 20, F | 0.091 | 1 | 0.374 | 18.58 |
| Monitor | 0.097 | 1 | 0.371 | 18.57 |
| ACI | 0.077 | 1 | 0.359 | 18.56 |
| EB k = 20, κ ≤ 20 † | 0.073 | 1 | 0.326 | 18.51 |

Numbers: pooled wrong-commit over the session (≈ 75 items: the day's calibration and test items). Source: [results.md](../../experiments/2026-11-13-a2-per-session-risk/results.md).

- Mondrian LTT is feasible only for day 76 (52 calibration items). The other days use the fallback.
- The monitor alarmed on day 34 in 27 % of splits, at median item 71 of 75. False alarms on the other 13 days: 3.0 % (γ = 0.1).
- Our decoder: no day above α under any method (day 34: 0.037).

## Results: forward chain (time order)
- Our decoder, V3 (model fitted on all earlier days, plug-in threshold): day 34 had **20/100 = 0.200** wrong commits (CP95 [0.127, 0.292]). The monitor alarmed at item 15 and cut it to 4/100. Block LTT k = 45 W: 3/100. Days above α: 5/13 (global) → 3/13 (monitor) → 0/13 (block LTT k = 45 W).
- Published, V3: day 34 7/100 (global), 3/100 (block LTT k = 45 W). The monitor did not alarm.
- Block LTT in mode F is not safe on a bad day, because the block runs at the bad threshold: our decoder, day 34, k = 60 F: 13/100.

## sEMG
No test participant is above α under the global rule (all three conditions). The monitor raised no alarm. A participant has only 30 test sentences, so block LTT cannot commit there.

## Cost
- Offer-only costs little eWPM in the simulated-user model: −2.9 % (published) and −1.1 % (ours) over all 14 days. Block LTT k = 45 W: −2.2 % and −0.7 %.
- User effort: 45 labelled sentences per session. As an offer-only warm-up, the labels come from normal use (the user picks or retypes the text). As a separate copy-typing block, they produce no text. In a 75-item session this lowers eWPM to 4.9 (day 34). The cost falls as the session grows.

> **Our take:** the per-session guarantee costs labels, not speed. The default fix for Paper 1 is "certify, then commit": offer-only until 45 (better 60) sentences have known truth, then commit at max(global, block LTT). Add the monitor as a drift alarm. Commits add little eWPM here, so offer-only is a safe fallback for every short or new session.

> **Our take:** block LTT assumes exchangeability inside the session. On day 34, the last 15–30 items of the session were worse than the start (post-block pooled 0.085 at k = 45, published). This agrees with the within-day drift seen in [M2-13](m2-13-conformal-result.md) and the R4 V3 forward chain. The monitor covers part of this gap. A within-session guarantee under drift remains open.

## Code
- `fidetype.trust.session_risk`: `min_ltt_items`, `mondrian_ltt`, `block_ltt`, `block_test`, `SessionRiskMonitor`, `first_alarm`, `eb_session_threshold` (†), `beta_cdf`, `fit_beta_prior`. Tests: `tests/test_trust_session_risk.py` (21, synthetic only).
- Opt-in streaming policy: `StreamingTrustLayer(..., session_risk=SessionRiskMonitor(alpha=0.05, gamma=0.1))`. Each session gets its own monitor. `feedback()` feeds it. After an alarm, the session is offer-only (commit_p = +inf) until it closes. Default off. See [streaming trust layer](../concepts/streaming-trust-layer.md).

## Limits
- One participant (B2T '25), 14 days. sEMG sessions are too short for block LTT.
- Zero feedback delay and no silent errors. Mode W assumes that every offer-only item reveals its truth.
- The random re-splits share trials. Pooled rates over splits are means, not independent samples.

## Related
- [Conformal risk control and LTT](../concepts/conformal-risk-control.md)
- [M2-13 conformal result](m2-13-conformal-result.md), [M2-16 online re-calibration](m2-16-online-recal-result.md)
- [Streaming trust layer](../concepts/streaming-trust-layer.md)
- [Paper 1 plan](paper1-plan.md)
