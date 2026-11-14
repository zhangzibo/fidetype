---
title: M3-01 / M3-02 plan (pre-declared before any run)
type: experiment-plan
updated: 2026-11-13
---

# M3-01 / M3-02: trust-core ablations, MEG and simulator runs (plan)

Tasks: **M3-02** (ablations: each trust-core module on and off) and **M3-01** (trust layer end to end on SpanishBCBL MEG and on the simulator). CPU only, no retraining. This file fixes the arms, metrics and comparisons **before the first run**. It is committed before any result file exists. Later changes go into a "Deviations" section of `results.md`, with the reason.

## 1. Baseline: the frozen v4 configuration
Git tag `paper1-v4-frozen-config`, `fidetype.trust.frozen.PAPER1_V4_RECIPE`, `paper1_v4_harness_config()`:

| module | v4 setting |
|---|---|
| calibration | frame temperature (before LM fusion) + sentence / char temperatures, fitted on fit-A |
| conformal set | split conformal, alpha 0.1, LAC, conditional (used by OFFER, not by COMMIT) |
| guard | on, `GuardConfig` defaults, combine = max (enters `commit_max_risk`, `abstain_risk`) |
| policy fit | grid search on fit-A: max eWPM s.t. plug-in wrong-commit <= 0.05 |
| risk control | LTT, alpha 0.05, delta 0.1, binomial p-values, grid 1.00 to 0.00 step 0.01, on the clean calibration half |
| combine | final `commit_p` = max(grid `commit_p`, LTT lambda-hat) |
| commit gate (M2-18) | off (opt-in) |
| decode declaration check (FEP-0001 s. 4) | streaming layer default `"warn"` (no decision change) |
| per-session risk monitor (M2-17) | off (opt-in) |

Fit procedure (as Paper 1 and M4-06): `pipe.fit(fitA, fitA)` with risk control none, then thresholds from the item table of the clean calibration set.

## 2. Arms (M3-02)
Each arm changes one thing against v4, or keeps one module alone. Arms 1-7 and 12-13 need only the item tables of four fitted pipelines per split: {calibration on, off} x {guard on, off}.

| # | arm | calibration | guard | risk rule | other |
|---|---|---|---|---|---|
| 0 | **v4 (baseline)** | on | on | LTT max | |
| 1 | no risk control | on | on | plug-in (grid `commit_p`) | |
| 2 | CRC instead of LTT | on | on | CRC max | |
| 3 | LTT without max combine | on | on | LTT pure | |
| 4 | guard off | on | off | LTT max | |
| 5 | calibration alone | on | off | plug-in | |
| 6 | calibration off | off | on | LTT max | |
| 7 | guard alone | off | on | plug-in | |
| 8 | LTT alone | off | off | LTT max | |
| 9 | nothing (bare grid fit) | off | off | plug-in | |
| 10 | conformal off | on | on | LTT max | conformal q = nan (every candidate in the set): affects OFFER only |
| 11 | + commit gate B | on | on | LTT max | `CommitGate(min_chars=1, max_guard_risk=1.0)` (M2-18 "gate B") |
| 12 | + per-session monitor | on | on | LTT max | `SessionRiskMonitor` alpha 0.05, gamma 0.1, alternatives (0.075, 0.1, 0.15, 0.2, 0.3), bet cap 0.5; session = one day (B2T) or one participant (sEMG, MEG) in file order; zero-delay feedback; alarm -> offer-only for the rest of the session |
| 13 | declaration check | on | on | LTT max | see section 4 |
| ref | always commit | — | — | commit every top-1 | |
| ref | never commit | on | on | lambda = +inf (offer / abstain only) | |

Arm 11 and the monitor change decisions after the threshold is set. They do not refit LTT (the gate only removes commits, so the LTT bound still holds; M2-18).

## 3. Data and splits

| data | splits | arms |
|---|---|---|
| B2T '25 T15, our decoder and the published gate | Paper 1 fixed split A (alternate trials per day: fit-A / calibration) and split B (chronological halves per day); test = the 816 test trials | all arms |
| B2T '25 T15 | Paper 1 random re-splits, R = 200 (cached R3/R4 item tables, guard on and off) | arms 0-5, 12, refs (no refit possible from the cache for 6-11) |
| Toronto sEMG (CC BY 4.0), conditions calib / xsession / xsubject | Paper 1 fixed split (fit-A, fit-B1 grid, fit-B2 calibration), test 551 composed sentences (calibration 143) | all arms except 13 (declaration arm run on B2T and the simulator only) |
| Toronto sEMG | random re-splits, R = 50 (cached tables, guard on and off) | arms 0-5, 12, refs |
| SpanishBCBL MEG (M3-01) | Paper 1 clean split: val-A (6 sentences) fit, val-B calibration, test 637 instances; provenance streams (`..._provenance`) of runs r4b-full-medium (Paper 1 run), its seeds s1 and s2, r4b-full and r5-medium | arms 0-12 + streaming replay |
| Simulator (M3-01) | `NoisyDecoderSimulator`, presets median and worst x `confidence_temperature` 0.5 / 1.0 / 2.0 (6 conditions); template sentences `sentences(3400, seed=0)`; fit-A 200, calibration 300, test 300 per condition; decoder `ctc_prefix_beam_search` RETUNED, n_best 10, 6-gram char LM on `all_s[400:]` | arms 0-12 + streaming replay |

Decoder outputs: the cached decodes of Paper 1 (`C:/Users/zhang/bci-data/cache/paper1-r1|r3|r4`) are reused. New decodes (calibration off = frame temperature 1.0) go to a new cache folder outside the repo. No training.

## 4. Declaration check arm (13)
The check matters only on the hypothesis route, when a producer decodes at a frame temperature other than the frozen one (M4-06 finding). Test: the producer decodes the **raw** stream (temperature 1.0, no declared temperature) and sends the n-best to a layer frozen at the fitted temperature.
- check `"abstain"`: every such hypothesis is a mismatch, so 0 commits (by construction; we verify it).
- check `"off"` / `"warn"`: the layer scores the mismatched n-best. We report its wrong-commit rate, commit rate and control commits.
- Data: B2T split A (both decoders), the 816 test trials, and the 300-trial control draw; simulator (one condition per preset at T = 1.0).
- Clean, matched streams: the check changes nothing (0 decisions changed); verified on the same data with a matching declaration.

## 5. Controls
Same draws as Paper 1 where they exist.

| control | B2T | sEMG | MEG | simulator |
|---|---|---|---|---|
| frame-shuffled | yes (300 trials) | yes (200) | yes (637) | yes (100) |
| uniform (flat log-probs) | yes | yes (new) | yes | yes |
| intent mismatch (another trial's stream, scored against this trial's sentence) | yes ("other trial") | yes ("other sentence") | yes | yes |
| zero input | stand-in: every frame = the stream's first frame (pre-speech silence); the T15 RNN is not available, so the true zero-input output cannot be made | the decoder's real zero-input output (`zeros_input`) | the decoder's real zero-input output (`zeros_meg`) | stand-in: every frame = the first (lead-in silence) frame |

Signal-destroying controls = frame-shuffled, uniform, zero input. For these, every commit is a failure. Intent mismatch: a correct decode of the wrong intent; the layer cannot see intent, so commits are expected at about the real commit rate (we report them, not judge them).

## 6. Metrics (pre-declared)
Per arm, condition and fixed split, on the test set:
1. **Wrong-commit rate** = wrong commits / all test items, with the exact two-sided Clopper-Pearson 95 % interval (CP95). Zero counts: also the one-sided 95 % upper bound.
2. **Commit rate** = commits / items.
3. **eWPM** from the harness simulated user (`UserConfig.aac_gaze`, Paper 1 settings per dataset).
4. **Control commit rates**: commits / n per control, with the one-sided 95 % CP upper bound; wrong commits on intent mismatch.
5. Repeated splits: mean wrong-commit rate, 5th-95th percentile, share of splits with wrong-commit > alpha, mean commit rate, mean eWPM.
6. Monitor arm: also the number of sessions with an alarm (and false alarms on sessions whose realised rate is <= alpha).

## 7. Comparisons (pre-declared)
- **Primary:** each arm vs arm 0 on the fixed splits: difference in wrong-commit rate, commit rate and eWPM. Paired exact McNemar test on the per-item wrong-commit indicator; Holm correction over the arms within one condition x split. Two-sided, level 0.05.
- **Primary (safety):** an arm "fails the controls" if it commits on any signal-destroying control stream. Reported as counts; no test.
- **Secondary:** repeated splits: share of splits > alpha per arm (with CP95 of the share); paired difference of the mean wrong-commit rate vs arm 0 (sign test over splits). Splits share trials, so these are descriptive.
- **MEG (M3-01):** if v4 makes 0 commits on the real test streams, the result is reported as "no commits": the one-sided bound on the wrong-commit rate, the gaze-typing comparison of eWPM, and what the arms without risk control do. We do not lower any threshold to force commits.
- **Simulator (M3-01):** the same table as B2T; plus the effect of calibration per `confidence_temperature` (the simulator's distortion is known).
- No other comparison is a confirmatory claim. Anything added later is labelled exploratory.

## 8. Outputs
`run_b2t.py`, `run_emg.py`, `run_meg.py`, `run_sim.py`, `tables.py`, `results/*.json` (aggregated numbers only), `results/tables.md`, `results.md`. No per-trial text, no signals, no participant data in the repo. SpanishBCBL (CC BY-NC 4.0): aggregated results only.
