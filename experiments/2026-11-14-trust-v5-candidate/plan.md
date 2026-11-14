---
title: P5-07 trust v5 candidate recipe - evaluation plan (pre-declared before any run)
type: experiment-plan
task: P5-07
updated: 2026-11-13
---

# P5-07: trust v5 candidate recipe (plan)

This file fixes the candidate, the arms, the data, the metrics and the success criteria **before the first evaluation run**. It is committed before any result file exists. Later changes go into a "Deviations" section of `results.md`, with the reason. CPU only, no retraining, cached decoder outputs where they exist.

## 1. Why: the known weak points of v4

| # | weak point | evidence |
|---|---|---|
| W1 | The grid value `commit_max_risk` 1.0 turns the guard limit off. A fit that picks it can COMMIT empty texts on no-signal input. | M2-18: T12 dry run 335/400 uniform commits (320 empty); 1.0 chosen in 53/200 and 65/200 T15 re-splits |
| W2 | The grid fit sees only labelled real streams, so it cannot see what a grid point does without signal. One discrete grid value decides the no-signal behaviour (T12: 1.0 on the validation blocks, 0.1 on the trust pool). | M2-18 section 5 |
| W3 | Frame-shuffled simulator streams pass the guard (1-16 of 100 commits per condition). | M3-01 |
| W4 | A decoder's confident output on zero input is not in the calibration data, so risk control cannot see it. | P12: 37 % of zero-input sEMG presses acted on; 0 with a no-signal reference |
| W5 | Declaration check "abstain" also removes every OFFER (B2T eWPM 3.55, below gaze typing 4.08). | M3-02 |

## 2. The v5 candidate (code: `fidetype.trust.recipe_v5`)

`PAPER1_V4_RECIPE`, the tag `paper1-v4-frozen-config` and every existing config id stay unchanged. v5 is a new recipe record `TRUST_V5_CANDIDATE`; a frozen v5 configuration has its own `config_id` (the recipe is part of the file). Every change is a switch of `V5Options`.

| switch | change | v5 candidate | targets |
|---|---|---|---|
| (a) `commit_gate` | commit gate B: no empty COMMIT, no COMMIT at guard risk 1.0 (`CommitGate(1, 0, 1.0)`) | on | W1 |
| (b) `control_aware_fit` | a grid point is feasible only if it also commits <= 1 % of **each** control kind made from the grid-fit streams: uniform (jitter 0.05), frame-shuffled, zero-input stand-in (every frame = the first frame). At most 200 copies per kind (seeded random subset). No labels. Same selection rule as v4 otherwise (max eWPM s.t. plug-in wrong-commit <= 0.05; first point wins a tie). | on | W1-W3 |
| (c) `max_risk_grid` | `"no-1.0"`: replace 1.0 in the `commit_max_risk` grid by 0.8 | **off** (`"keep"`) | W1 (alternative to the guard part of (a)) |
| (d) `no_signal_reference` | after LTT: `commit_p = max(commit_p, floor)`, floor = smallest value on the 0.00-1.00 step-0.01 grid at which each no-signal reference kind (uniform and zero stand-in copies of the grid-fit streams) is committed <= 1 % | on | W4 |
| (e) `declaration_check` | new streaming mode `"offer-only"`: a declaration mismatch blocks COMMIT; the policy runs with `commit_p = +inf` (OFFER / ASK / ABSTAIN by its normal rules) | `"offer-only"` | W5 |
| (f) guard feature for confident-but-shuffled input | **not added.** Reason: a per-stream temporal-structure feature (for example lag-1 frame similarity) cannot separate real from shuffled simulator streams, because the simulator has no temporal structure inside a key (M3-01); real B2T, sEMG and MEG streams already give 0 frame-shuffled commits with v4. An LM-surprise feature points the wrong way (the shuffled stream decodes to a fluent in-domain sentence, so its LM surprise is low). (b) handles W3 at the policy level. Listed as future work. | — | W3 |

Final threshold: `commit_p = max(grid commit_p, LTT lambda-hat, floor)`; LTT as v4 (alpha 0.05, delta 0.1, binomial p-values, grid 1.00 to 0.00 step 0.01, clean calibration half). The gate is applied last. **The v4 guarantee holds for v5**: (b), (c) change only the fit-A grid fit; (d) only raises `commit_p` above the LTT value (LTT certifies every grid value above lambda-hat); (a) only removes commits (M2-18). The calibration half is not used by (b) or (d).

## 3. Arms

All arms share one fitted pipeline per split (frame / sentence temperature, conformal set, guard). They differ only in the policy selection, the floor and the gate. The grid is swept once on the grid-fit set with `commit_max_risk` in (0.1, 0.2, 0.3, 0.5, 0.8, 1.0); each arm selects from that table. With the v4 values only, the selection equals the v4 grid fit exactly (checked against the M3-02 v4 rows).

| # | arm | grid selection | gate (a) | floor (d) |
|---|---|---|---|---|
| 0 | **v4** (baseline) | v4 rule, v4 grid | off | off |
| 1 | **v5** (a+b+d) | control-aware, v4 grid | on | on |
| 2 | v5 − a | control-aware (controls counted without gate) | off | on |
| 3 | v5 − b | v4 rule | on | on |
| 4 | v5 − d | control-aware | on | off |
| 5 | v5 + c | control-aware, grid with 0.8 instead of 1.0 | on | on |
| 6 | v4 + a | v4 rule | on | off |
| 7 | v4 + b | control-aware (without gate) | off | off |
| 8 | v4 + c | v4 rule, grid with 0.8 instead of 1.0 | off | off |
| 9 | v4 + d | v4 rule | off | on |
| ref | never commit | v4 | — | lambda = +inf (offer only) |

(e) is a streaming option. It is tested separately (section 6). In each arm the LTT lambda-hat comes from the clean calibration item table of that arm's grid selection.

**End-to-end check.** On B2T split A (both decoders) and on every simulator condition, `fit_trust_v5` (the library function) must give the same final `commit_p` and the same test commits as arm 1. The frozen v5 configuration (`freeze_v5`) is replayed through `StreamingTrustLayer` (frames route on the simulator, hypothesis route on B2T): streaming commits = batch commits on every item. Its `config_id` differs from the v4 one.

## 4. Data and splits

| data | splits | role |
|---|---|---|
| B2T '25 T15 (our decoder; published gate) | Paper 1 fixed splits A and B (fit-A 411, calibration 401, test 816); the Paper 1 300-trial control draw | all arms; test-time controls; (e) on split A |
| B2T '25 T15 | repeated splits r = 0..49 (R3 generator, seed 3, day-stratified 1/4 fit-A, 1/4 calibration, 1/2 test; frame temperature snapped to 0.02 as R3/R4) | all arms, refitted |
| B2T '25 T15, small fit set | split A with fit-A = a random 240 of the 411 trials (10 draws, seed 240); calibration and test unchanged | all arms (no collapse check) |
| Toronto sEMG (CC BY 4.0), calib / xsession / xsubject | Paper 1 fixed split (fit-A temperature, fit-B1 grid, fit-B2 calibration, test 551); Paper 1 audit draw of 200 + uniform, as M3-02 | all arms; controls include the decoder's **real zero-input** output |
| Toronto sEMG | repeated splits r = 0..49 (R3 generator, seed 3 + 100) | all arms, refitted |
| T12 v2 (M3-28), aggregate only | (i) validation dry run: decoder-validation blocks, `fit_a` (240 trials) / calibration / test sessions; (ii) trust pool: `fit_a` / calibration / test. Controls as M3-28 (400 each: frame-shuffled, uniform, intent mismatch) + zero stand-in | all arms. **Exploratory**: the confirmatory M3-28 result does not change; the pool test set was already used once |
| SpanishBCBL MEG (CC BY-NC 4.0), aggregate only | 5 provenance runs (Paper 1 run, seeds s1 / s2, r4b-full, r5-medium); Paper 1 clean split (fit-A 6 val sentences, calibration the rest, test 637); controls as M3-01 (shuffled MEG and zero MEG = the decoder's real outputs; frame-shuffled; uniform; intent mismatch) | all arms |
| Simulator | 6 conditions (presets median / worst x confidence temperature 0.5 / 1.0 / 2.0); fit-A 200, calibration 300, test 300, controls 100 per kind; one attempt per item; as M3-01 | all arms; (e); streaming end to end |

Fit-time control copies are made from the **grid-fit** streams (fit-A; sEMG fit-B1) with seed 0, never from calibration or test streams. The test-time controls are the existing draws (other trials, other RNG). On B2T, T12 and the simulator the test-time zero stand-in and uniform controls are the same *kind* as the fit-time copies (not the same streams); the out-of-kind checks are the real zero-input outputs (sEMG, MEG), shuffled MEG and the intent-mismatch control.

## 5. Metrics

Per arm and split:
- wrong-commit rate k/n with exact Clopper-Pearson 95 % interval; commit rate; eWPM (same user models as Paper 1: `aac_gaze` on B2T / T12, Paper 1 sEMG and MEG users, default user on the simulator); chosen grid point (`commit_p`, `commit_max_risk`) and the lambda parts (grid, LTT, floor).
- difference to v4: exact McNemar on the per-item wrong-commit outcome, Holm over the 9 arms per split.
- empty COMMITs (count) on test and on every control set.
- control commits per kind on the test-time controls (k/n and one-sided 95 % upper bound) and the fit-time control rates at the selected grid point.
- repeated splits: mean wrong-commit, share of splits with test wrong-commit > alpha (CP95), mean commit rate, mean eWPM, sign test vs v4.
- **stability**: B = 200 bootstrap resamples of the grid-fit set (per-item outcomes of every grid point are kept from the sweep; the calibration and the control copies stay fixed). For the v4 rule and the v5 rule (arm 1 selection): the share of resamples that pick each `commit_max_risk` value, the share of the most frequent grid point, and the number of distinct winners. Datasets: B2T fixed splits (4 fits), sEMG (3), T12 (2), MEG (5), simulator (6).

## 6. Declaration check (e)

As M3-02 arm 13: a producer decodes the raw stream (frame temperature 1.0) and sends the n-best to a layer frozen at the fitted temperature (hypothesis route). The **v5 frozen configuration** is used with check `"warn"`, `"abstain"` and `"offer-only"`. Data: B2T split A (both decoders, 816 test trials) and the 6 simulator conditions. Metrics: commits, wrong commits, eWPM, number of mismatches. Matched streams (correct declaration): the check must change 0 decisions.

## 7. Success criteria (fixed now)

v5 is recommended as the **default for new configurations** if S1-S4 all hold. S5 is the reported cost.

| id | criterion |
|---|---|
| S1 | **Not less safe on real data.** On every real fixed split (B2T 4, sEMG 3, T12 2, MEG 5), v5 wrong-commit is not significantly higher than v4 (McNemar, Holm p < 0.05 with v5 worse = fail). On repeated splits (B2T 2 x 50, sEMG 3 x 50), the share of splits > alpha for v5 is at most the v4 share + 0.05. |
| S2 | **0 empty commits** with v5 on every test and control set of every dataset. |
| S3 | **Controls <= 1 %.** v5 commits at most 1 % (k/n <= 0.01) of every signal-destroying test-time control (uniform, frame-shuffled, zero input or zero stand-in, shuffled MEG) on every dataset, simulator included. Intent mismatch (a real stream of another sentence) is reported, not a criterion. |
| S4 | **No collapse on 240-trial fit sets.** T12 (both fits) and the 10 B2T 240-trial draws: v5 eWPM >= never-commit eWPM − 0.05 on every fit, and the median relative eWPM loss of v5 vs v4 over the B2T 240 draws <= 10 %. |
| S5 | Cost (reported): relative eWPM change v5 vs v4 on the real fixed splits and the mean over repeated splits. A loss > 5 % on B2T or sEMG is named as a trade-off in the recommendation. |

Per change: a change stays in the recommended recipe only if removing it (arms 2-4) breaks S2 or S3 on at least one dataset, or if it costs < 0.1 eWPM (absolute) on every real fixed split. (c) is recommended only if arm 5 is better than arm 1 on S3 at no larger eWPM cost. (e) is recommended if offer-only gives 0 commits on mismatched streams and higher eWPM than "abstain".

## 8. Runs and budget

CPU only, at most 4 single-thread processes at a time, each under `python -m fidetype.utils.isolation run --class background --threads 1 --`. Decodes come from the Paper 1 / M3-02 caches; new decodes (the fit-time control copies) go to `C:/Users/zhang/bci-data/cache/trust-v5/` (outside the repo). Output: `results/*.json` (aggregates only: no text, no signals, no participant ids, no per-trial rows), logs `results/run-*.log`, tables `results/tables.md`.

Order: B2T fixed (2 processes) + sEMG fixed + simulator; then T12, MEG, B2T 240 draws; then the repeated splits. If time runs short, the repeated splits are cut to r = 0..24 and the MEG runs to the Paper 1 run first; any cut is reported as a deviation.

## 9. Not in scope
No change to `PAPER1_V4_RECIPE`, Paper 1, `papers/`, or the conformance profiles. The FEP-0001 reference-implementation note gets the new `"offer-only"` mode (rule 5 is a SHOULD ABSTAIN; offer-only also blocks COMMIT). Whether v5 becomes the reference default (and FEP-0001 rule 9 a MUST) is a decision after this evaluation.
