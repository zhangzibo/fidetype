---
title: P15-37 Multi-split guards for a lower-variance calibration-inclusive safe WPM - pre-registration
type: experiment
task: P15-37
updated: 2026-11-21
---

# P15-37: multi-split guards that keep the LTT guarantee, interval over calibration draws (pre-registration)

Written and committed **before** any number of this item was computed. Gap 141 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P15-37](../../wiki/questions/roadmap-standard.md#p15-37-lower-variance-calibration-for-the-calibration-inclusive-safe-wpm). Also gap 132 ([P15-34](../2026-11-20-p15-34-margin-guard/plan.md)). Follow-up of [P15-29](../2026-11-20-p15-29-calibration-ci/plan.md) and [P15-34](../2026-11-20-p15-34-margin-guard/results.md). Theory: [method.md](method.md).

## Problem
- P15-29 (K = 40): the T15 L1 safe WPM v0.1 with calibration draws is 5.18 [0.00, 6.99]. 2 / 40 draws are `above-alpha` and earn 0.0.
- P15-34 A0 (same settings, 40 new draws): 5.35 [4.05, 6.81]. A safety margin (A1) gives 4.90 [3.11, 6.44].
- The between-draw SD (0.63-0.91) is 2-3 times the within-draw SD (0.34). It sets the lower end.
- No extra labelled T15 data exists outside `val_eval`. So option (1) of gap 141 is not possible.

## Methods (from method.md)
Two multi-split constructions keep the guarantee (G) P(R > 0.05) ≤ 0.1 exactly. Cross-fitting, jackknife+, CV+ and conformal risk control do not (method.md, section 2), so they are not used.

| arm | rule | guarantee argument |
|---|---|---|
| AND-J (J = 2, 3, 4) | J split guards, each `calibrate` at (0.05, 0.1); commit the text t only if all J guards commit t | R(AND) ≤ R(g_1) pointwise; no correction |
| BMAX-J (J = 2, 3) | J split guards, each at (0.05, 0.1/J); deploy the one with the highest in-sample safe WPM on its own LTT items (tie: lowest j) | union bound over J |
| BMED-3 | 3 split guards at (0.05, 0.1/3); deploy the one with the median in-sample value (tie: lowest j) | union bound over 3 |
| S1 | split 1 alone at (0.05, 0.1) = the P15-29 settings | LTT |

**In-sample value** of a guard (BMAX, BMED only): the `safe-wpm/0.1` formula on that guard's own LTT items (words of the right commits × 60 / (measured durations + correction penalty of the wrong commits)), at its δ/J threshold. It uses calibration data only.

**Implementation.** Each split guard is one `fidetype.trust.calibrate` call at (0.05, 0.1) (pinned pipeline values, `confidence="learned"`, commit gate, `stream_texts`, `null_max_commit_rate` 0.05, as P15-29 / P15-34). The learned score of a split does not depend on δ. So the δ/J threshold is computed from the same LTT items with `ltt_threshold(s, loss, 0.05, δ/J, DEFAULT_LTT_GRID, "binomial")`. For every item the code computes (score, gate pass, top-1 text) exactly as `_fit_commit_score` / `_learned_commit` do; a guard commits at threshold λ iff gate pass, a text exists and score ≥ λ. Code checks (must pass, see below) compare this path with `guard.decide` and with the sheet.

## Stage S: arm selection on `val_select` only
Stage S never loads, decodes or scores a `val_eval` trial (the evaluation split is deleted at load, as P15-34).

1. Pairs: 4 repeats q = 0..3 of a 3-fold split of the 722 `val_select` trials (permutation `default_rng` of the first 8 hex digits of SHA-256(`"p15-37|sel|perm|<q>"`), `numpy.array_split` into 3 folds). Pair (q, f): pseudo-evaluation set E = fold f (240 or 241), pseudo-calibration set C = the other two folds (481 or 482), in permutation order. 12 pairs.
2. For each pair and j = 1..4: `calibrate` on C with seed SHA-256(`"p15-37|sel|<q>|<f>|<j>"`), (0.05, 0.1), `null_trials` 20 (the controls do not enter stage S). Check: the recomputed LTT threshold at (0.05, 0.1) equals the guard threshold; if not, stage S stops. A refused split guard makes every arm that uses it earn 0 for that pair.
3. Per pair and arm: decisions on E. Value by the P15-29 credit rule: the E wrong-commit rate must be ≤ 0.05 and there must be ≥ 1 commit, else 0.0. Inner level: B = 200 multinomial resamples of E (rng `default_rng(1)`, size |E|).
4. Predicted lower end of an arm = the 2.5th percentile of its pooled 12 × 200 values. Also the mean, the between-pair SD and the zero fraction.

**Arm rule (fixed now).** Primary arm **M** = the arm other than S1 with the highest predicted lower end. Ties (difference < 0.01): the higher predicted mean, then the order AND-2, AND-3, AND-4, BMAX-2, BMED-3, BMAX-3. Stage S writes `results/selection.json`. A short addendum to this plan names M. Both are committed **before** the main run starts. M is used in the main run even if S1 has a higher predicted lower end (that fact is reported).

Known limit of stage S: C has about 481 items (LTT 180) and E has about 240 items, so the values are lower and noisier than with 722 / 701. Stage S ranks arms; it does not predict the main result.

## Main run: two-level bootstrap (P15-29 procedure)
- Evaluation set fixed: T15 `val_eval` (701). Calibration set: `val_select` (722). Pinned pipeline values as P15-29 (T 2.37015800035291, τ 0.06996627059278283, λ 1.0, fluent −7.88165954200173).
- Draws k = 1..40, new seeds: calibrate seed s_k = first 8 hex digits of SHA-256(`"p15-37|t15|cal|<k>"`), bootstrap seed b_k = SHA-256(`"p15-37|t15|boot|<k>"`).
- **Split 1 = the P15-29 draw.** The P15-29 `draw_order(722, s_k, b_k)`: split by `_split`, resample with replacement inside each part. This gives the draw's calibration sample S_k (722 entries; the three parts have disjoint source trials). `calibrate` with seed s_k, (0.05, 0.1), `null_trials` 300. This guard is arm **A0** (the P15-29 settings on new draws).
- **Splits j = 2, 3, 4: new partitions of the same sample S_k.** The entries of one source trial (its bootstrap copies) form a group and stay in one part, so no trial is in two parts. Groups are taken in a random order (rng from SHA-256(`"p15-37|t15|split|<k>|<j>|<attempt>"`)) and put into the first part (fit, policy, LTT order) that still has room for the whole group, with the part sizes of `_split(722)` = 180 / 271 / 271. If the parts cannot be filled exactly, the next attempt is used (up to 100). This rule uses only the group sizes, never a label or a score. The input order is set so that `calibrate` with seed SHA-256(`"p15-37|t15|cal|<k>|<j>"`) sees exactly these parts. (0.05, 0.1), `null_trials` 20 (own controls, reported).
- Draw z0 (code check): seed 0, no resampling, split 1 only (and splits 2-4 as above with the no-resampling sample, reported).
- **Null controls of a multi-split arm.** The 600 control inputs of split 1 (the uniform and shuffled inputs that `calibrate` drew with seed s_k) are rebuilt with the same random generator. Every split guard decides them. The arm's control count is the number of control inputs on which the arm commits (AND: all J commit the same text; BMAX / BMED: the deployed guard). Allowed: 15 of 300 per control. An arm draw is `refused` (earns 0.0) if a control fails or a split guard it uses was refused.
- **Credit rule and interval:** as P15-29. Only `certified` draws add their values; refused, `not-certified`, `above-alpha`, `vacuous` add 0.0. `calibration_draw_interval` with the same B = 2,000 trial resamples (`default_rng(0)`). The guarantee of every arm is (0.05, 0.1), n_cal 271 (method.md).
- K = 40 for every arm. No cutoff. If a job is killed for low memory, it is not restarted; then no arm with fewer than 40 draws is analysed.

## Option 3 arm R120 (separate, pre-registered)
- **R120** = the P15-29 settings with K = 120: P15-29 draws k01-k40 + P15-34 A0 draws k01-k40 + the 40 new A0 draws of this run. The first two sets are read only from `C:\Users\zhang\bci-data\derived\p15-29\t15\` and `...\p15-34\t15\a0.050-d0.100\`.
- **Compatibility checks (must pass, else R120 is not decided):** every draw has status `ok` or `refused`; sheet alpha 0.05, delta 0.1, n_ltt 271; frame temperature = the pinned T; the truths of the 701 rows equal those of this run's z0; the X4 check of P15-29 and P15-34 passed (their `results/results.json`); the three seed sets do not overlap.
- **Not blind:** 80 of the 120 draws have known test outcomes (2 `above-alpha` in P15-29, 0 in P15-34). Expectation stated now: 2 / 120 = 1.7 % of the pooled mass is 0.0, and the known low draws (P15-29 k14 3.50, k35 3.87) add more mass below 4.0153, so we expect the R120 lower end to stay below 4.0153. Because it is not blind, **R120 cannot close a gap**. Its three-way verdict is reported.

## Code checks (must pass)
- **X4 (as P15-29 / P15-34).** z0 split 1 reproduces the P15-22 L1 decisions on T15 (701 / 701 same action and text; safe WPM 4.91); the library with K = 1 gives [4.25, 5.57]; threshold 0.82, 196 commits, 13 wrong (= P15-29 z0).
- **C1.** In every draw, the offline decision path of split 1 equals `guard.decide` on all 701 trials (action and text).
- **C2.** In every draw, the offline control counts of split 1 equal the `uniform` and `shuffled` counts of its sheet.
- **C3.** For every split guard, the recomputed LTT threshold at (0.05, 0.1) equals the guard threshold.
- **C4.** Every multi-split partition has disjoint source trials across parts and the sizes 180 / 271 / 271.
A failed check stops the analysis (no result).

## Decision rule
Reference: the no-BCI WPM of `val_eval`, **4.0153**.

| outcome for **M** (primary) | verdict | gaps |
|---|---|---|
| pooled 2.5th percentile > 4.0153 | **clearly above after calibration uncertainty** | 132 and 141 closed |
| mean > 4.0153 ≥ 2.5th percentile | above, but inside the combined interval | 132 open; 141 see below |
| mean ≤ 4.0153 | not above | 132 open; 141 see below |

- Only M can close a gap. A0, R120 and the other multi-split arms are descriptive (their verdicts are reported).
- Also reported per arm: statuses, draw values (mean, median, SD, range), the fraction of draws above 4.0153, mean commits and wrong commits, the X1 decomposition (between-draw SD, within-draw SD), and the paired difference to A0 on the same draws.
- **Variance comparison (required):** the between-draw SD of M against the paired A0 (same draws), P15-29 (1.43 all draws; 0.79 certified only) and P15-34 A0 (0.63).
- **Calibration size projection (pre-registered, for the "or shows with numbers" branch of gap 141).** From R120 (if decided, else this run's A0): mean μ, between-draw SD σ_b, within-draw SD σ_w. Assume that σ_b scales as 1/√n (n = calibration items) and μ, σ_w stay the same. The SD needed for μ − 1.96 √(σ_b*² + σ_w²) = 4.0153 is σ_b*; the needed size is n* = 722 × (σ_b / σ_b*)². If no σ_b* > 0 exists, the report says so. Also reported: the fraction of non-credited draws, which LTT bounds by δ at every n (so a larger n alone does not remove the zero draws). This projection is a rough estimate with a stated assumption; it is not a test. If M fails, gap 141 is closed only if this projection is reported with numbers (done-when of P15-37).

## Expectation (stated before any result; not a rule)
The multi-split arms can remove only the split part of the spread and the rare unsafe draws (method.md, section 3). The sample part stays. AND lowers the commits, BMAX / BMED pay a Bonferroni cost. We expect M to have fewer zero draws than A0 and a similar or smaller SD, but a lower mean, and we expect its lower end to stay below 4.0153.

## Order, limits, outputs
1. Commit method.md, this plan, `run.py`, `launch.py`. Smoke run on calibration subsets only (`P1537_SMOKE=1`; it never reads `val_eval`).
2. Stage S (calibration data only, about 1 h), then commit `results/selection.json` and the plan addendum.
3. Main run detached from a `git archive` snapshot of the committed code (other agents may change `src/fidetype/trust/`): two workers, each `python -m fidetype.utils.isolation run --class background --threads 2 -- python -I run.py worker <w>` (4 threads in total; the user uses the PC), CPU only, **no GPU**, keep-awake, log, `DONE` file `C:\Users\zhang\bci-data\derived\p15-37\DONE`, stop file `C:\Users\zhang\bci-data\derived\p15-37\STOP` (a worker stops after its current draw). Worker 0: z0 and odd k; worker 1: even k. Resumable: each finished draw is saved and skipped on a rerun. **Expected duration: about 10-14 hours** (split 1 of a draw needs about 13 min of new null-control decodes as in P15-34, with fewer threads; splits 2-4 add about 4 min).
4. Derived data only in `C:\Users\zhang\bci-data\derived\p15-37\`. Read only: `derived/p15-22/`, `derived/p15-26/` (caches, P15-22 decisions), `derived/p15-29/t15/`, `derived/p15-34/t15/a0.050-d0.100/` (R120). Peak memory under 8 GB in total (P15-34: 2.9 GB per worker); peak RSS is logged.
5. The repo gets `results/selection.json`, `results/results.json` (aggregates, no text) and `results/run.log`.
6. No change of the methods, the arm rule, K, the reference or the decision rule after this commit. Any later variant is a new item.

Known limits (stated before any result): the P15-29 limits (a) pinned pipeline values, (b) duplicates inside a resampled part (a single draw's certificate is not a valid certificate; the draws show the sampling variation), (c) one participant and one decoder checkpoint, (d) the same evaluation set in every draw; (e) the group rule of splits 2-4 puts large groups (trials with many bootstrap copies) a little more often into later parts; it uses no label, so the parts stay independent of the outcomes; (f) splits 2-4 run their own controls with 20 trials only; the arm controls use the 300 + 300 inputs of split 1.

## Addendum (2026-11-21 01:05): stage S result and the primary arm (before the main run)
Stage S ran on `val_select` only (12 pairs, B = 200; 00:21-01:03, peak 2.65 GB; [results/selection.json](results/selection.json)). The check (recomputed LTT threshold = guard threshold) passed for all 48 split guards. No split guard was refused.

| arm | predicted mean [2.5 %, 97.5 %] | SD between pairs | zero fraction |
|---|---|---|---|
| S1 (P15-29 settings) | 4.89 [0.00, 7.37] | 1.79 | 1 / 12 |
| AND-2 | 4.67 [2.66, 6.97] | 0.99 | 0 |
| AND-3 | 4.55 [2.66, 6.42] | 0.83 | 0 |
| AND-4 | 4.49 [2.66, 6.33] | 0.80 | 0 |
| BMAX-2 | 4.55 [0.00, 7.11] | 1.66 | 1 / 12 |
| BMAX-3 | 4.74 [0.00, 7.35] | 1.72 | 1 / 12 |
| **BMED-3** | **4.82 [2.84, 6.55]** | 0.81 | 0 |

By the arm rule, the primary arm is **M = BMED-3** (3 splits, each LTT at (0.05, 0.1/3); deploy the guard with the median in-sample value). S1 does not have a higher predicted lower end. **No arm has a predicted lower end above 4.0153** (best 2.84, at the smaller stage-S sizes). The main run goes on as pre-registered. Nothing else changes.
