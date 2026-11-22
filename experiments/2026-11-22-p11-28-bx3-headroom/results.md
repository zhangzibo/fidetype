---
title: P11-28 Safety headroom of the EMG BX3 guard - results
type: experiment
task: P11-28
updated: 2026-11-22
---

# P11-28: safety headroom of the EMG BX3 guard (results)

Pre-registration: [plan.md](plan.md), commit `84d465f`. It was committed and pushed before any number was computed. Code and synthetic tests: `a8877bf` ([run.py](run.py), [launch.py](launch.py), [test_p11_28.py](test_p11_28.py)). Amendment 1 (X5 model digest descriptive): `bf06ee9`, written before any phase-2 split guard or arm number existed. Aggregates and per-draw pooled counts: [results/results.json](results/results.json). Log: [results/run.log](results/run.log). Per-prompt files are local only, in `C:\Users\zhang\bci-data\derived\p11-28\`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page holds pooled aggregates and per-draw counts only: no per-user value, no text, no id. **Metric version: `safe-wpm/0.1` (adopted).** For sentence commits it equals the proposed v0.2. The calibration-inclusive interval (`docs/safe-wpm.md` section 6b) is a proposed reporting addition. It is not adopted.

Run details:
- First chain: code `a8877bf`, 10:07 to 10:19:59. It stopped at X5, as the plan requires.
- Second chain: code `bf06ee9`, 10:21:24 to 12:53:28. Phase 2 ran from 10:21:26 to 12:53:19. Then came the analysis.
- **CPU only**, no GPU, no new inference. 2 workers x 1 thread, isolation class `background`.
- 124 split guards were computed: 4 in phase 1 (about 245-519 s each) and 120 in phase 2 (147-171 s each, mean 152 s).
- Wall time from the first launch to DONE was 4.8 h, under the 5 h cap. The compute time of the second chain was 2.5 h.
- Fresh decodes only: the window memo started empty.

## Outcome
**BX3 keeps the claim with headroom ("BX3 safety holds with headroom").**
- **Exceedances:** 0 / 80 draws have a test wrong-commit rate above 0.05 (40 P11-19 draws + 40 new draws). The one-sided 95 % CP bound on P(rate > 0.05) is **0.037**. It was 0.072 with 40 draws, and the claim is delta = 0.1.
- **Headroom:** the 95 % upper bound on the 90th percentile of the test rate is **0.0393**, so the headroom against 0.05 is **0.0107**.
- **Replication:** the new draws alone confirm both results. They have 0 / 40 exceedances, a maximum rate of 0.0410 and a headroom of 0.0090.
- **Value:** the P11-19 value pass also replicates. On the new 40 draws, BX3 gives 5.99 [3.52, 8.96] vs no-BCI 3.09.
- **Secondary rules:** none of them gives more margin and also keeps the value pass.

## Checks
| Id | Check | Result |
|---|---|---|
| X1' (must pass) | an empty-memo rerun of P11-23 S01 / S13 at (0.0314, 0.1) | **pass**: all fields are equal to P11-23 S01 / S13 and to the P11-19 XF01 / XF13 files. This includes the model digest. 0 differing actions in 4 x 3 x 1,221 |
| X5 (must pass, amendment 1) | reruns of the P11-19 split guards k01-j2 and k13-j3 at (0.0314, delta / 3) | **pass**: the threshold, commits, wrong commits, value, statuses, `v_in`, model structure and all actions are equal (0 differing actions). The model parameters differ by at most 9.7e-9 (k01-j2) and 8.4e-10 (k13-j3), so the **model digests differ** (descriptive; gap 180). In the first chain this failed X5 as originally written (see Deviations) |
| X4 (must pass) | LTT wrong-commit recount = sheet count | **pass**: 120 / 120 new split guards |
| X6 (must pass) | the 40 old BX3 draws rebuild P11-19 BX3 | **pass**: test-rate mean 0.028112203112203117 and point value 5.898744142080952, both exact |
| C-null | every new BX3 draw: test time-shuffled and zero-EMG commits = 0 / 1,221 | **pass**: 40 / 40. The count is 0 in every arm |

New split guards: 120 / 120 produced a guard. 0 were refused and 0 were infeasible. 26 / 120 thresholds are at the grid floor of 0.30. The maximum calibrate control count is 0. The in-sample value is mean 5.50, SD 0.81, range 2.98-6.83 (P11-19: 5.38, 0.79, 2.46-7.04).

## Primary: BX3 test-rate tail and headroom
| Set | N | f (> 0.05) | CP95 upper | Q (rank) | headroom h | label | mean (SD) | 90 % quantile | max | top rates | > 0.0314 | normal-fit P(> 0.05) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **pooled (H1, H2)** | 80 | **0** | **0.0368** | **0.0393** (77) | **0.0107** | **clear headroom** | 0.0286 (0.0079) | 0.0385 | 0.0434 | 0.0434, 0.0410, 0.0401, 0.0393, 0.0393 | 31 | 0.0033 |
| new (H2-rep) | 40 | 0 | 0.0722 | 0.0410 (40 = max) | 0.0090 | clear headroom | 0.0290 (0.0080) | 0.0378 | 0.0410 | 0.0410, 0.0385, 0.0385, 0.0385, 0.0377 | 18 | 0.0042 |
| old (P11-19) | 40 | 0 | 0.0722 | 0.0434 (max) | 0.0066 | clear headroom | 0.0281 (0.0079) | 0.0386 | 0.0434 | 0.0434, 0.0401, 0.0393, 0.0393, 0.0385 | 13 | |

- **H1 (claim): pass.** U(0, 80) = 0.0368 <= 0.10.
- **H2 (headroom): "clear headroom".** h = 0.0107 >= 0.005.
- **H2-rep: replicated.** f40 = 0 <= 1. The new-draw maximum (0.0410) is below the P11-19 maximum (0.0434).
- The LTT in-sample rate is mean 0.0142 (pooled), so the optimism gap (test - LTT) is +0.0143. The test-rate mean 0.0286 is between alpha'' 0.0314 and the LTT rate. Selection plus the shift between sessions uses most of the m2 margin (0.0185), but none of the claim. 31 / 80 draws are above alpha'' (39 %).

### Test-set uncertainty (descriptive; 2,000 user-cluster weight vectors on the one test set)
| Set | fraction of draws > 0.05: median / 95th pct | P(fraction > delta) | max rate over draws: median / 95th pct |
|---|---|---|---|
| BX3 pooled | 0.000 / 0.013 | 0.007 | 0.0434 / 0.0508 |
| BX3 new | 0.000 / 0.000 | 0.007 | 0.0410 / 0.0484 |

All draws share one test set (8 users), so U and Q are conditional on it. When the users are reweighted, the fraction of draws above 0.05 stays below delta in 99.3 % of the weight vectors. The largest draw rate is above 0.05 in about 5 % of them. So the headroom is clear for the δ-quantile, but it is not large against the test-set noise for the single worst draw.

## H3: value replication (BX3, P11-17 interval procedure)
| Set | value [95 %] | lower end > 3.09? | SD between / within | draw values range | credited | verdict |
|---|---|---|---|---|---|---|
| **new 40** | **5.99 [3.52, 8.96]** | **yes** | 0.58 / 1.30 | 4.51-6.76 | 40 / 40 | **clearly above after calibration uncertainty** |
| pooled 80 | 5.95 [3.49, 8.92] | yes | 0.59 / 1.30 | 4.51-6.84 | 80 / 80 | clearly above after calibration uncertainty |
| P11-19 (old 40) | 5.90 [3.45, 8.89] | yes | 0.59 / 1.30 | 4.55-6.84 | 40 / 40 | clearly above after calibration uncertainty |

**The P11-19 value pass replicates on new draws.** The margin is still narrow (+0.43 on the new draws). BX3 j-hat (pooled): split 1: 26, split 2: 20, split 3: 34.

## Secondary rules (same split guards; pooled 80, with the new 40 in brackets)
| Rule | f | Q | headroom | mean rate | max rate | > 0.0314 | value [95 %] | verdict vs 3.09 | more margin (Q lower than BX3 **and** lower end > 3.09)? |
|---|---|---|---|---|---|---|---|---|---|
| **BX3** (primary) | 0 (0) | 0.0393 (0.0410) | 0.0107 (0.0090) | 0.0286 | 0.0434 | 31 | 5.95 [3.49, 8.92] | clearly above | - |
| BXS (safety tie-break) | 0 (0) | 0.0393 (0.0410) | 0.0107 (0.0090) | 0.0265 | 0.0434 | 26 | 5.75 [3.15, 8.80]; new 5.84 [3.15, 8.89] | clearly above | **no** (same Q) |
| BX2 (max of splits 1, 2) | 0 (0) | 0.0393 (0.0410) | 0.0107 (0.0090) | 0.0247 | 0.0434 | 23 | 5.63 [3.04, 8.74]; new 5.75 [3.02, 8.83] | above, but inside | no |
| BD3 (median) | 0 (0) | 0.0352 (0.0369) | 0.0148 (0.0131) | 0.0204 | 0.0377 | 9 | 5.29 [2.90, 8.30]; new 5.38 [2.90, 8.39] | above, but inside | no (lower end below 3.09) |
| J1 (split 1 at delta / 3) | 0 (0) | 0.0369 (0.0385) | 0.0131 (0.0115) | 0.0208 | 0.0434 | 17 | 5.27 [2.53, 8.51] | above, but inside | no |
| AN3 (AND of 3) | 0 (0) | 0.0278 (0.0287) | 0.0222 (0.0213) | 0.0122 | 0.0369 | 1 | 4.45 [2.17, 7.37] | above, but inside | no |

- BXS lowers the mean rate (0.0265 vs 0.0286) and the count above alpha'' (26 vs 31). It does not lower the tail: the worst draws are the same guards. It costs 0.20 WPM and has a wider spread (between-draw SD 0.76 vs 0.59), and its lower end (3.15) is closer to 3.09.
- BX2 and BD3 have a lower mean rate. BD3 and AN3 also have a lower tail. But each of them loses the value pass.
- So on these data, safety margin and value trade off. **No secondary rule meets the plan's "keeps the pass with more margin" test.** BX3 stays the rule to report.

## Comparison with the pre-registered rules
| Rule (plan) | Outcome |
|---|---|
| X1', X5 (amended), X4 and X6 must pass | pass |
| **H1**: U(f80, 80) <= 0.10 | **pass** (0 / 80, U = 0.0368) |
| **H2**: headroom h = 0.05 - Q(80) | **0.0107, "clear headroom"** |
| H2-rep: new 40 | f40 = 0; Q = max = 0.0410; h = 0.0090; replicated |
| H3: value on the new 40 | 5.99 [3.52, 8.96], "clearly above after calibration uncertainty"; replicated |
| Overall verdict | **"BX3 safety holds with headroom"** |
| Secondary "more margin" | none (BXS, BX2, BD3, J1, AN3: all no) |

> **Our take:** the BX3 selection costs safety margin, but it does not cost the claim. Over 80 calibration draws, no deployed guard exceeds 0.05 on test. The 90th-percentile rate is at most about 0.039. The P11-19 maximum of 0.0434 was the tail of a stable distribution (mean 0.029, SD 0.008). It was not a sign of drift toward 0.05. The cost is visible elsewhere: 39 % of the draws are above alpha'' 0.0314. So the selection optimism uses most of the shift margin m2. That margin is the safety buffer if (A2) fails on another session. The headroom result is conditional on one test set of 8 users. When the users are reweighted, the single worst draw goes above 0.05 in about 5 % of the cases. A new session (the other done-when option) would be the stronger test. The value pass also replicates on new draws (lower end 3.52 vs 3.09).

## Deviations
1. **Amendment 1 (X5 model digest descriptive).** The first chain (`a8877bf`) stopped after the checks. X1' passed. X5 failed on the model digest only: all decisions and values were equal, and the L-model parameters differed by up to 9.7e-9 (gap 180, between processes). The amendment (`bf06ee9`) keeps X5 must-pass on the decisions, the model structure and the parameters within 1e-6. No phase-2 split guard or arm number existed before it. The first checks file is kept as `derived\p11-28\checks-first-run.json`.
2. **Time-stamp error:** the amendment header says "10:25". It was written at about 10:20 (the relaunch log shows 10:21:24).
3. **Cap timing:** the 4.6 h worker cap restarted with the second chain (the plan amendment says so). The wall time from the first launch was 4.8 h, under 5 h.
4. No smoke run on real data before the code commit. Only the 8 synthetic tests ran.

## Gap rule
**Gap 183 closes** on its headroom branch. Under the plan (`84d465f`, amendment `bf06ee9`, with X1', X5, X4 and X6 passed), this page reports the BX3 test-rate headroom against 0.05 on 80 draws: 0 / 80 above, CP95 0.037, headroom 0.0107. It also reports the replication on 40 new draws, the test-set uncertainty, the H3 value replication and the comparison of BXS / BX2 / BD3 / J1 / AN3. J = 4 and a lower `commit_p` floor were not run (reasons in the plan).

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-22-p11-28-bx3-headroom/test_p11_28.py` |
| Full run (detached; about 2.7 h CPU with 2 workers x 1 thread) | `.venv\Scripts\python.exe experiments/2026-11-22-p11-28-bx3-headroom/launch.py bf06ee9` (needs the P11-19 and P11-23 derived files and the P11-09 / P11-11 / P11-14 inputs) |
| Check / stop | tail `results/run.log`. Done when `C:\Users\zhang\bci-data\derived\p11-28\DONE` exists. To stop, create `derived\p11-28\STOP` |

## Limits
- (a) One test set (1,221 prompts, 8 users). U and Q are conditional on it. The cluster bootstrap shows the worst draw above 0.05 in about 5 % of the weight vectors.
- (b) (A2) and m2 come from two sessions (P11-23). Selection uses most of m2 (mean test rate 0.0286 vs alpha'' 0.0314).
- (c) All draws share the 1,224 calibration prompts, so the spread is split variation only.
- (d) The old 40 draws were known as aggregates before the plan. The new 40 replicate the result on their own.
- (e) Cross-process decode differences (gap 180) change the L-model parameters by about 1e-8. X5 shows no decision change in 2 guards.
- (f) The interval method (section 6b) is proposed and not adopted.
