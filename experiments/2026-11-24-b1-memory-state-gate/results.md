---
title: B1 calibrated "good encoding moment" detector on Penn RAM FR1 iEEG - results
type: experiment-results
task: P16-06 (gap 206), experiment B1
plan: plan.md (97c412b), amendment-1.md (e396554)
updated: 2026-11-25
---

# B1 results: outcome C ("not safe" by the pre-registered rules)

**Short answer.** The decoder works on new sessions: mean test AUC 0.574 over 30 subjects (p = 1.1e-5). The certified "good encoding moment" gate (G+) kept its precision bound on the next session. But two pre-registered safety rules fail. Label-permuted runs certify a threshold in 14 of 20 runs (the limit is 4), and shuffled-signal flags are too precise (0.344 against a limit of 0.285). The gate is also too rare to be useful: it flags 2.9 % of test words (the rule needs at least 5 %). So the outcome is **C** (with the qualifier "behaviour explains it": the behaviour-only gate certifies too and flags more words).

The reason for the failures is not the LTT step. It is a design gap that the plan did not see. Recall rates differ a lot **between subjects** (test sessions: 0.03 to 0.51). The per-subject Platt step learns each subject's rate, and the pooled gate then flags words of high-recall subjects. That information survives within-session label permutation, shuffled signal and noise input. See [Diagnosis](#diagnosis-exploratory-not-pre-registered).

## Run record
| item | value |
|---|---|
| data | OpenNeuro ds004789 snapshot 3.1.0 (CC0), 30 subjects, 99 sessions, bipolar EDF + text files: 792 files, 56.80 GB, all sizes and EDF header sizes checked against the OpenNeuro API |
| subjects | the plan's 30 hash-ranked subjects; no session dropped, no subject replaced |
| words | 23,616 `WORD` events; 72 dropped (`sample = -1`, amendment-1 F6); 0 dropped at the edges |
| channels per subject | 54 - 180 (median 110.5); all sessions of a subject share their channel labels |
| sampling rates | 500 / 1000 / 1600 Hz |
| cal session | 620 lists (196 order, 424 certify); 2,352 order words, 5,088 certify words; no subject needed amendment-1 F10 |
| test | 7,200 words, recall rate 0.2349 |
| compute | CPU only, 4 worker processes, below-normal priority; features 28 min, fit + test + nulls 2 min; no GPU |
| commits | plan `97c412b`; amendment `e396554`; code `2a29be8`, `6533222`; `results/gate.json` `d8dd453` (before any test word was scored); this page and `results/summary.json` |

## Pass rules (as written in the plan, with amendment-1 fill-ins)
| rule | numbers | limit | pass |
|---|---|---|---|
| **A0** event timing | one-sided Wilcoxon over 99 sessions, p = 3.4e-17; `WORD` statistic > random in 97 of 99 sessions; median ratio 1.95 | p < 0.01 | **pass** (`sample` index used) |
| **V1** decoder works | mean test AUC 0.5743 (SD 0.0767, n = 30), t = 5.30, p (two-sided) = 1.1e-5 | mean >= 0.55, p < 0.01 | **pass** |
| **(i)** no certificate without signal | N1: G+ certified in **14 of 20** permuted runs | <= 4 of 20 | **fail** |
| **(ii)** real flags keep the bound | G+ wrong-flag rate 0.6250 (130 of 208); cluster bootstrap 95 % [0.5640, 0.7075] | <= 0.6474; upper <= 0.7474 | **pass** |
| **(iii)** gate is useful | G+ flag rate 0.0289 (208 of 7,200); precision - base 0.1401, bootstrap 95 % [0.0634, 0.1964] | flag rate >= 0.05 and lower > 0 | **fail** (flag rate) |
| **(iv)** noise does not flag | N3b: flag rate 0.0422, CP 95 % upper 0.0463, bootstrap upper 0.0770 (pass); N4: precision 0.3443 vs base 0.2349 + 0.05 = 0.2849 (**fail**) | N3b <= 0.10 / 0.20 / 0.20; N4 <= base + 0.05 | **fail** (N4) |
| qualifier "behaviour explains it" | B0 G+ certifies (`lambda+` 0.30) and flags 2,391 test words (>= 208) | - | **applies** |

Outcome rule: (i) or (iv) fails, so the outcome is **C**, with the qualifier "behaviour explains it". The behaviour-only gate (serial position + list number) flags 11 times more words at a similar precision. The real flag rate (0.0289) is below alpha, so the plan asks for the N3b / real flag-rate ratio: **1.46**. Noise input flags more often than real input.

## Gate (fitted on cal only; `results/gate.json`)
| input | `b_order` | `tau+` | `lambda+` | cert commits / wrong | `tau-` | `lambda-` |
|---|---|---|---|---|---|---|
| neural | 0.2526 | 0.3526 | 0.54 | 126 / 74 | 0.7974 | 0.70 |
| B0 (behaviour) | 0.2526 | 0.3526 | 0.30 | 1,580 / 994 | 0.7974 | 0.63 |
| B0+N | 0.2526 | 0.3526 | 0.54 | 145 / 81 | 0.7974 | 0.69 |
| P0 (pre-stimulus) | 0.2526 | 0.3526 | 0.40 | 507 / 310 | 0.7974 | 0.73 |

## Test results (pooled over 30 subjects; bootstrap = subject-cluster, 10,000 resamples, 95 % percentile interval)
| input | AUC mean (SD) | G+ flag rate [95 %] | G+ wrong-flag rate [95 %] | G+ precision - base [95 %] | G- flag rate | G- wrong-flag rate [95 %] |
|---|---|---|---|---|---|---|
| **neural** | 0.574 (0.077) | 0.029 [0.011, 0.054] | 0.625 [0.564, 0.708] | 0.140 [0.063, 0.196] | 0.651 | 0.183 [0.149, 0.219] |
| B0 behaviour only | 0.576 (0.109) | 0.332 [0.203, 0.472] | 0.650 [0.578, 0.718] | 0.115 [0.063, 0.183] | 0.782 | 0.188 [0.157, 0.220] |
| B0+N | 0.583 (0.078) | 0.034 [0.014, 0.060] | 0.595 [0.458, 0.719] | 0.170 [0.055, 0.300] | 0.684 | 0.193 [0.157, 0.233] |
| P0 pre-stimulus | 0.520 (0.070) | 0.112 [0.052, 0.185] | 0.613 [0.551, 0.688] | 0.152 [0.087, 0.215] | 0.611 | 0.190 [0.153, 0.229] |
| N2 time-reversed | 0.574 (0.077) | 0.029 | 0.625 | 0.140 | 0.651 | 0.183 |
| N3a phase-randomised | 0.556 (0.070) | 0.023 [0.007, 0.045] | 0.648 [0.584, 0.787] | 0.117 [-0.009, 0.175] | 0.659 | 0.191 |
| **N3b** session-mean noise | 0.513 (0.051) | 0.042 [0.016, 0.077] | 0.671 [0.604, 0.748] | 0.094 [0.027, 0.165] | 0.654 | 0.196 |
| **N4** shuffled signal | - | 0.029 [0.011, 0.055] | 0.656 [0.527, 0.746] | 0.110 [0.027, 0.239] | 0.650 | 0.193 |
| N5 uniform score | - | 0 | - | - | 1.000 | 0.235 |

- **N1** (labels permuted within each session, whole pipeline, 20 seeds): G+ certified in 14 of 20 runs (`lambda+` 0.31 - 0.47), G- in 19 of 20. In the 14 certified runs, the test precision minus the pooled base rate is +0.07 to +0.15, and the test wrong-flag rate is 0.61 - 0.69.
- **Invariance checks, as predicted in the plan:** N2 gives the same flags as real input (agreement 1.000, score correlation 1.000). N3a keeps most of it (agreement 0.966, AUC 0.556). The information is in time-averaged power.
- **OFFER** (binary conformal, alpha = 0.10): neural coverage 0.897, singleton share 0.587 (B0 0.909 / 0.557).
- **G-** ("poor encoding moment", reported only): wrong-flag rate 0.183, below its target `1 - tau-` = 0.203; bootstrap upper 0.219.
- **Published numbers:** Ezzyat et al. 2018 mean AUC 0.61; Li, Pazdera & Kahana 2024 (scalp EEG) 0.59 / 0.60. Our 0.574 is lower. Most of our subjects train on one or two sessions (the plan predicted this).

## Diagnosis (exploratory, not pre-registered)
The plan's nulls assume that "no word-level signal" means "no certificate". That is false for a gate pooled over subjects with per-subject calibration:
1. Subject recall rates differ: test-session rate 0.03 - 0.51 (median 0.22, SD 0.116). A subject's cal rate predicts its test rate (correlation 0.81 over 30 subjects).
2. Per-subject Platt has an intercept. So `p_recall` carries the subject's own base rate, also when the score carries no word information (permuted labels, noise, shuffled words).
3. The pooled target is `b_order + 0.10` with the **pooled** base rate. Words of a high-recall subject pass it with no word-level information.

A check against the **own-subject** base rate (each flag weighted by its subject's test recall rate) separates the two parts:

| input | G+ flags | precision | flag-weighted own-subject base rate | difference |
|---|---|---|---|---|
| neural | 208 | 0.375 | 0.285 | **+0.090** |
| N3b noise | 304 | 0.329 | 0.319 | +0.010 |

> **Our take:** the real neural flags carry within-subject information (about +0.09 above the subject's own rate). The noise flags carry almost none: they only pick out subjects. So the certificate is "valid" for the claim it makes (pooled precision >= 0.35 held on test). But that claim does not mean "this moment is good for memory", and the pre-registered nulls correctly caught it. This is a general lesson for the trust layer: a pooled precision gate over heterogeneous users needs a per-user base rate in the target (or a null that permutes across users). The gate in its B1 form is **not safe** as a "good encoding moment" detector.

## Caveats
- The outcome follows the pre-registered rules exactly. The diagnosis above is post hoc and is not a test.
- The first rule evaluation applied the B0 qualifier to outcomes A and B only. The plan has no such limit, so we removed it and evaluated the rules again on the same numbers (no new scoring). The outcome stays C.
- (ii) passed, but on 208 flags in 12 of 30 subjects; the cluster bootstrap interval is wide.
- (iii) would fail even without the safety problem: 2.9 % of words flagged.
- One decoder family (Ezzyat features, L2 logistic regression), 30 epilepsy patients with clinical electrodes, one memory label (recall in this list's free recall). No claim for healthy people or scalp EEG. B1 reads a memory state, never memory content.
- The intercept of our logistic regression is not penalised (LIBLINEAR penalises it). This is the only known deviation from Ezzyat et al.
- The download ran while the code was written (amendment-1, "Step order"). No iEEG sample was analysed before the code and the amendment were committed.

## Possible next step (not planned yet)
A new pre-registration ("B1b") could change only the target: `tau+` per subject from its own order-word rate, or a gate on the within-subject excess. It would keep the same nulls and add one: labels permuted **across** subjects of the same base-rate stratum. The B1 numbers above must not be used to tune it.

## Files
- `results/gate.json`: the gate, fitted on cal only, committed before the test step (`d8dd453`).
- `results/summary.json`: all test aggregates, N1 runs and rule results. No subject code, no per-word or per-channel value.
- Local only (not committed): per-subject values, features and decoder weights in `C:/Users/zhang/bci-data/derived/b1-penn-ram-fr1/`.
