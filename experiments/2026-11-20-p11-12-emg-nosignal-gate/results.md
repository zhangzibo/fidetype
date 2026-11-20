---
title: P11-12 no-signal gate for the EMG intended-text guard - results
type: experiment
task: P11-12
updated: 2026-11-19
---

# P11-12: a no-signal gate for the EMG intended-text guard (results)

Pre-registration: [plan.md](plan.md) (commit `f63da8a`, before any evaluation decision). Code: `3a0572b` ([run.py](run.py), [launch.py](launch.py), [tests](test_p11_12.py)). Aggregates: [results/results.json](results/results.json), guard sheets `results/guard-{S,SL,X}.json`, log `results/run.log`.

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page and the committed files hold pooled aggregates only: no per-user value, no text, no id. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-prompt files: `C:\Users\zhang\bci-data\derived\p11-12\` only. The P11-09 and P11-11 files were read only.

Run: 2026-11-19 19:33-19:39, CPU only (isolation runner, class `background`, 4 threads), detached. No GPU.

## Outcome
**The acoustic no-signal gate fixes the null-control failure. All three arms are certified, safe, non-vacuous and pass every control. The primary sentence arm S gives the first certified, non-vacuous EMG safe WPM under the ADOPTED v0.1: 4.10 [1.99, 6.60] (167 commits, 35 wrong = 2.9 % of 1,221 test prompts), above the no-BCI reference 3.09 (not clearly above). The prefix arm X now commits on 0 / 1,221 time-shuffled test inputs (P11-11: 76 = 6.2 %), with the same value as before: proposed v0.2 4.25 [2.69, 6.30]. The gate removes 2.2 % of the real test windows.**

## The gate (fitted on the calibration tuning part only)
Pass iff greedy CTC key emissions `n_keys >= 15` and key rate `1.84 <= kps <= 17.28` per second (plan rule: `K_MIN`, `R_MIN` from the 1 % tail of the 765 real tuning-part windows, `R_MAX` = 2 x their fastest rate). It reads only the decoder's argmax path: no LM, no lexicon. Tuning digest `96f175801d6ff225` (= P11-11).

| Check | Value |
|---|---|
| Real tuning-part windows gated (fit) | 1.7 % (13 / 765) |
| Time-shuffled tuning-part windows that pass (572, outside the 300 null-control prompts) | 0 % |
| Real **test** windows gated | 2.2 % (27 / 1,221) |
| Time-shuffled / zero-EMG **test** windows gated | 100 % / 100 % |
| Top-1 intended text exactly right on test, without / with the gate | 24.5 % / 24.0 % |

## Verdicts (pre-registered)
| Id | Arm S (primary) | Arm SL | Arm X (prefix, v0.2) |
|---|---|---|---|
| **V1 guard** | **certified** (`tcfg-3875f995e4c256fb`, p_top1 >= 0.55; controls uniform 0, frame-shuffled 1, input-level time-shuffled 0 of 300) | certified (`tcfg-0cd6e9578e965f42`; 0 / 1 / 0) | certified (`tcfg-bea10a2046878c8d`; 0 / 7 / 0) |
| **V2 safety** | **holds**: 35 / 1,221 = 0.029, CP95 [0.020, 0.040] | holds: 31 / 1,221 = 0.025, CP95 [0.017, 0.036] | holds: 34 / 1,221 = 0.028, CP95 [0.019, 0.039] |
| **V3 value** | **non-vacuous**: v0.1 4.10 [1.99, 6.60], `certified` | non-vacuous: v0.1 5.08 [2.67, 7.96] | non-vacuous: v0.2 4.25 [2.69, 6.30] |
| **V4 vs no-BCI** | **above** 3.09 (intended text) and 2.93 (P11-09); not clearly above | above; not clearly above | above; not clearly above |
| **V6 controls** | **pass**: test time-shuffled 0 / 1,221, zero EMG 0 / 1,221 | pass (0 / 0) | **pass** (0 / 0; P11-11: 76 / 0) |
| V7 gate cost | 2.2 % of real test windows gated | same | same |

Hypotheses: **H1** (S certified, safe, non-vacuous v0.1, V6 pass) **supported**. **H2** (X: V6 pass, certified, safe, non-vacuous, value inside [2.60, 6.34]) **supported**: 4.25. **H3** (gate removes <= 2 % of real test windows) **not supported, narrowly**: 2.2 %. **H4** (S above no-BCI) **supported**, not clearly above.

## Main numbers (1,221 track-test prompts of the 8 users; 4,985 intended words; 119.8 min neural time)
| Measure | Arm S | Arm SL | Arm X |
|---|---|---|---|
| Safe WPM, adopted v0.1 | **4.10 [1.99, 6.60]** | **5.08 [2.67, 7.96]** | 0.07 [0.00, 0.17] (complete commits only) |
| Proposed v0.2 (plain) | 4.10 [1.99, 6.60] | 5.08 [2.67, 7.96] | **4.25 [2.69, 6.30]** |
| Proposed v0.2 + reading cost (0.5 s + 0.3 s / word per commit) | 3.95 [1.95, 6.25] | 4.88 [2.61, 7.46] | 4.04 [2.60, 5.88] |
| No-BCI reference (gaze, 20 chars/min, intended text) | 3.09 | 3.09 | 3.09 |
| Commits / offers / withholds | 167 / 822 / 232 | 194 / 795 / 232 | 423 / 566 / 232 (421 prefix, 2 complete) |
| Right words committed | 548 | 670 | 528 |
| Wrong commits, rate | 35, 0.029 | 31, 0.025 | 34, 0.028 |
| Error among commits | 0.210 | 0.160 | 0.080 |
| Correction time | 14.1 min | 12.0 min | 4.4 min |
| LTT threshold; LTT-part commits (in-sample) | p_top1 0.55; 71 (16 wrong) | learned 0.61; 80 (16 wrong) | learned prefix 0.89; 170 (16 wrong) |
| Offline decision time per prompt (cached beam) | p50 20 ms, p95 40 ms | p50 18 ms, p95 38 ms | p50 18 ms, p95 39 ms |

Always-commit reference (gated top-1, no bound): 293 right of 1,221, unguarded WPM 2.49 (below no-BCI). The guard is what makes the value.

Post-hoc check (not pre-registered; mirrors the P11-09 scorer controls; scratch script on the arm S decisions): pooled CER of the top-1 intended text vs the truth: real 0.277 (0.263 without the gate), time-shuffled 1.000, zero EMG 1.000.

> **Our take:** the failure in P11-11 was a language-side illusion: time-shuffled EMG makes the decoder emit almost no keys (median 0 greedy emissions vs 29 on real prompts), and the LM / lexicon then build one confident word from the weak n-best tail. A two-number acoustic check removes that path completely at a cost of about 2 % of real prompts. The adopted-v0.1 sentence arm is now useful and certified; the learned score (SL) gives the highest value. All CIs are wide (8 users), so none is clearly above gaze typing.

> **Our take:** the error among commits is high for arm S (21 %). The guarantee bounds wrong commits over all prompts (2.9 % <= 5 %), not precision. A user would see about one wrong sentence per five commits; the correction time (14.1 min) is in the value.

## Checks
| Check | Result |
|---|---|
| Track splits (our first / second test session = track val / test) | 8 / 8 users (`check_track_splits`) |
| Calibration and evaluation unit digests = P11-09 | yes |
| Gate fitted on the non-certify part only | yes: the first 765 positions of calibrate's order; no LTT item, no null-control window |
| Decoder | the P11-11 decoder unchanged (w 0.5, c 4, LM, lexicon, OOV gate) after the gate |
| Clopper-Pearson | level 0.95 (P11-11 fixed runner); intervals equal the safe-WPM blocks |

## Deviations
None from the plan. The post-hoc CER check above is extra and marked.

## Gap rule
- **Gap 104 closes:** H1 holds and arm X's test time-shuffled commit rate is 0 % (<= 5 %), with v0.1 and v0.2 values on the same split.
- **Gap 102 closes:** arm S (v0.1) is certified, safe, non-vacuous and passes V6 (the primary path; arm X also qualifies under v0.2).

## Benchmark entry
None (plan rule). The track target is the raw key sequence, and the track scorer compares commits to it. The arms commit intended text, so the track scorer cannot score them. The P11-09 declared-subset cards keep the track-conformant (vacuous) result. A track variant that scores intended text is a new item (gap 105, P11-13). **Later (P11-13):** the track scorer got the target `intended_text`; arms S and SL now have declared-subset cards ([P11-13 results](../2026-11-20-p11-13-intended-text-cards/results.md)).

## New gaps
| Gap | Item | What |
|---|---|---|
| 105 | P11-13 | Intended-text scoring for the emg2qwerty track (submission target `intended`, Backspace applied), so that the certified intended-text guards can get a score card and a leaderboard row |

Open as before: latency (gap 37, P3-06: the LM rescoring is offline only here), the emg2qwerty in-beam LM (gap 87, P11-07).

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-20-p11-12-emg-nosignal-gate/test_p11_12.py` |
| Full run (detached; about 6 min CPU after P11-11) | `.venv\Scripts\python.exe experiments/2026-11-20-p11-12-emg-nosignal-gate/launch.py` (needs `derived\p11-09\prompts.json` and `lp\`, and `derived\p11-11\` tune, LM, lexicon, beam cache) |
| Check / stop | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p11-12\DONE` exists; stop the python processes whose command line has `p11-12-emg-nosignal-gate` |

## Limits
- 8 users, one track-test session each; the CI unit is the user (8 clusters), so the CIs are wide.
- The target is the intended text after Backspace, not the track's raw keys; no track card.
- The guarantee assumes exchangeable val / test sessions of the same users. The gate was fitted on the same calibration sessions (tuning part only).
- The null inputs are time-shuffled and zero EMG. Other no-signal cases (rest EMG, a band off the wrist, typing on another device) were not tested.
- Offline only; no collector replay.
