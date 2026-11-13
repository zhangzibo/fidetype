# Track A item 2: per-session (per-day) risk control

Tables: [results/tables.md](results/tables.md) (generated). Data: `results/rs-b2t-published.json`, `results/rs-b2t-ours.json`, `results/forward_chain.json`, `results/emg.json`, `results/power.json`. Code: [`src/fidetype/trust/session_risk.py`](../../src/fidetype/trust/session_risk.py) (tests: `tests/test_trust_session_risk.py`, 21, synthetic only). Input: the cached Paper 1 item tables (R3/R4 split tables, forward-chain tables); no new decodes. Run time 75 s on CPU.

Run (repo root): `.venv\Scripts\python.exe -I experiments/2026-11-13-a2-per-session-risk/run.py`

## Problem
Paper 1 (R4 per-day analysis): LTT max bounds the wrong-commit rate of the calibration **mixture** of 14 days. It does not bound each day. On the published gate, day 34 ran at 0.098 (R = 200). A user meets one session at a time.

## Methods and guarantees

| method | what it does | guarantee |
|---|---|---|
| `global` | Paper 1 LTT max (here: leave-day-out calibration) | mixture of days only |
| `mondrian-never/global/mixture` | LTT on the day's own calibration items; fallback when n < 45 | per day if n ≥ 45 (never: always safe; global, mixture: none per day) |
| `block-ltt k W` | first k items offer-only (labels from OFFER picks or copy typing); then max(global, LTT on the block) | **per session**: P(R_session ≤ α) ≥ 1 − δ, if the rest of the session is exchangeable with the block |
| `block-ltt k F` | as above, but the block runs at the global threshold (labels from feedback) | per session after the block; none during the block |
| `block-test k` | exact binomial test of H0: R ≤ α on the block; reject → offer-only | false alarm ≤ γ only |
| `monitor` | e-process K_t = mean_j Π(1 + b_j(L_i − α)); K_t ≥ 1/γ → offer-only for the rest of the session | false alarm ≤ γ per session at any time (Ville); no risk bound before the alarm |
| `aci` | `OnlineCommitRiskControl(method="aci")`, floor = global threshold | long-run average for any sequence (M2-16) |
| `eb k` † | empirical-Bayes beta prior from other days, updated by the block | **none** (heuristic) |

Settings: α = 0.05, δ = 0.1, γ = 0.1, LTT grid 1.00 → 0.00 (step 0.01), seed 20261112. Feedback without delay; silent errors are not modelled. Session definitions are in `config.json`. Random re-splits (RS): session = the day's calibration + test items of the split in file order (≈ 75 items for day 34); the global threshold is LTT max on the other days' calibration items. The splits share trials, so pooled rates over splits are means, not independent samples.

## Sample-size facts (exact, no data)
- Per-session LTT needs **k ≥ 45** labelled items to commit at all (0 errors); 77 with 1 error, 105 with 2. So k = 10, 20, 40 blocks can never certify a threshold: block LTT with k < 45 means "never commit in this session".
- Exact block test at γ = 0.1: power against a 2α session (ρ = 0.10) is 0.26 (k = 10), 0.32 (k = 20), 0.37 (k = 40).
- Monitor on Bernoulli(ρ) losses (5000 runs): false alarm within 400 items 0.060 at ρ = α; at ρ = 0.10 alarm within 100 items 0.49 (median delay 93); at ρ = 0.20 0.99 (median 17).

## Headline: day 34, published gate, random re-splits (R = 200)

| method | day-34 wrong-commit (pooled) | share of splits > α | commit | eWPM (copy-typing view) | days > α (of 14) | mean eWPM all days |
|---|---|---|---|---|---|---|
| Paper 1 LTT max (test items) | 0.098 | 0.89 | 0.347 | 12.42 | 1 | 18.60 |
| global (leave-day-out, session) | **0.103** | 0.96 | 0.359 | 12.40 | 1 | 18.59 |
| mondrian-never | 0.000 | 0.00 | 0.000 | 12.22 | 0 | 18.08 |
| mondrian-global | 0.098 | 0.89 | 0.347 | 12.42 | 1 | 18.58 |
| block-ltt k=20 W | 0.000 | 0.00 | 0.000 | 12.20 (8.74) | 0 | 18.05 |
| **block-ltt k=45 W** | **0.034** | 0.23 | 0.108 | 12.26 (4.91) | **0** | 18.19 |
| block-ltt k=45 W + monitor | 0.033 | 0.23 | 0.106 | 12.26 | 0 | 18.19 |
| block-ltt k=60 W | 0.006 | 0.00 | 0.029 | 12.22 (2.45) | 0 | 18.14 |
| block-ltt k=45 F | 0.073 | 0.89 | 0.275 | 12.36 | 1 | 18.50 |
| block-test k=20 F | 0.091 | 0.82 | 0.311 | 12.37 | 1 | 18.58 |
| monitor | 0.097 | 0.96 | 0.343 | 12.39 | 1 | 18.57 |
| aci | 0.077 | 0.95 | 0.300 | 12.37 | 1 | 18.56 |
| eb k=0 † | 0.096 | 0.96 | 0.340 | 12.39 | 1 | 18.54 |
| eb k=20 F, κ ≤ 20 † | 0.073 | 0.92 | 0.250 | 12.34 | 1 | 18.51 |

- Mondrian LTT is feasible only for day 76 (52 calibration items ≥ 45, in 100 % of splits). The other 13 days use the fallback. With fallback "global", day 34 stays at 0.098. With "never" or "mixture" (α·π_d ≈ 0.004 is never feasible), the 13 days commit nothing.
- **Only block LTT with k ≥ 45 (warm-up, W) removed the day-34 problem with a per-session guarantee**: 0.103 → 0.034 (k = 45) or 0.006 (k = 60); 0 of 14 days above α.
- The monitor raised an alarm on day 34 in 27 % of splits, median at item 71 of 75 (too late). False alarms on the other 13 days: 3.0 % of sessions (≤ γ).
- ACI and EB lower day 34 but keep it above α. Block tests with k ≤ 40 have too little power.
- Our decoder: day 34 is at 0.037 under the global rule; no day is above α under any method.

## Forward chain (time order; one realisation per day, exact CP 95 %)

| condition | method | days > α | pooled [CP95] | commit | Δ eWPM vs global [day bootstrap 95 %] | day 34 |
|---|---|---|---|---|---|---|
| ours, V3 (fit days 1..k-1, plug-in threshold) | global | 5/13 (34, 48, 74, 83, 88) | 0.054 [0.043, 0.066] | 0.213 | 0 | **20/100 = 0.200 [0.127, 0.292]** |
| | monitor | 3/13 | 0.041 [0.032, 0.052] | 0.180 | −0.01 [−0.04, 0.02] | alarm at item 15: 4/100 = 0.040 |
| | aci | 3/13 | 0.040 [0.031, 0.051] | 0.170 | −0.03 [−0.05, −0.02] | 8/100 = 0.080 |
| | block-ltt k=45 W | **0/13** | 0.014 [0.009, 0.021] | 0.066 | −0.14 [−0.19, −0.08] | 3/100 = 0.030 |
| | block-ltt k=60 F | 2/13 | 0.035 [0.027, 0.045] | 0.147 | −0.07 [−0.10, −0.04] | 13/100 = 0.130 [0.071, 0.212] |
| published, V3 | global | 2/13 (34, 83) | 0.031 [0.023, 0.040] | 0.378 | 0 | 7/100 = 0.070 [0.029, 0.139] |
| | monitor | 2/13 | 0.031 | 0.364 | −0.04 | no alarm |
| | block-ltt k=45 W | **0/13** | 0.009 [0.005, 0.015] | 0.150 | −0.36 [−0.54, −0.22] | 3/100 = 0.030 |
| ours, V1 (cal = previous day) | global | 2/12 (74, 95) | 0.022 [0.015, 0.031] | 0.109 | 0 | — (not testable) |
| | monitor | 1/12 (95) | 0.021 | 0.101 | 0.00 | — |
| | block-ltt k=45 W | 0/12 | 0.007 [0.004, 0.013] | 0.049 | −0.07 [−0.13, −0.03] | — |
| published, V1 | global | 0/12 | 0.016 [0.010, 0.024] | 0.316 | 0 | — |

- In time order, day 34 exists only in V3 (the model is fitted on day 27, 30 trials). For our decoder this is the worst case: 0.200 with a CP lower bound above α. The monitor caught it after 15 items.
- Block LTT in mode F is unsafe on a bad day: the block itself runs at the bad global threshold (ours, day 34: 13/100 at k = 60).

## sEMG (per test participant, R = 50)
Global LTT max: 0 of 19 participants above α in all three conditions (max 0.038 / 0.023 / 0.000). The monitor raised no alarm. A test participant has 30 sentences, so block LTT (k ≥ 45) cannot commit; the remedy is not testable here.

## Cost
- In the simulated-user eWPM model, OFFER costs little time: offer-only on all 14 days gives 18.05 vs 18.59 eWPM (published, −2.9 %) and 10.95 vs 11.07 (ours, −1.1 %). Block LTT k = 45 W: −2.2 % and −0.7 %.
- Labels: 45 labelled sentences per session. As an offer-only warm-up, the labels come from the user's OFFER picks at no extra effort (normal use at offer-only speed). As a separate copy-typing block, the 45 sentences produce no user text: in a 75-item session, eWPM falls to 4.9 (published day 34). The block cost falls as the session grows.

## Limits
- The block-LTT guarantee needs exchangeability **inside** the session. On day 34 the post-block items (the last 15–30 of the session) had a pooled rate of 0.085 (published, k = 45) and 0.094 (ours, k = 60). These items are almost the same trials in every split, so the number rests on few trials. It agrees with the R4 V3 finding: the later part of a day can be worse than the start.
- One participant (B2T '25), 14 days; sEMG sessions are too short for block LTT.
- Zero feedback delay, no silent errors; W mode assumes that every offer-only item gives its truth.
- EB (†) has no finite-sample guarantee. The κ ≤ 20 rows were added after a 3-split smoke run (config `eb_sens_note`).

## Recommendation
- Library default stays **off** (existing behaviour unchanged).
- For a deployment that must hold α **per session**: "certify, then commit": an offer-only warm-up of k ≥ 45 sentences (60 is better), then COMMIT at max(global, block LTT), with the monitor (γ = 0.1) on top as a drift alarm. This is the remedy Paper 1 should name. Cost here: −2.2 % eWPM, 45 labelled sentences per session.
- The monitor alone (`StreamingTrustLayer(session_risk=SessionRiskMonitor())`) is a cheap safety net: valid false-alarm control (3 % observed) and fast on gross failures (0.200 day: alarm at item 15). It is too slow for a 2α day within one session (median 93 items at ρ = 0.10).
