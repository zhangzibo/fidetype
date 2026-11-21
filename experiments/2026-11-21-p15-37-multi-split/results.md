---
title: P15-37 Multi-split guards for a lower-variance calibration-inclusive safe WPM - results
type: experiment
task: P15-37
updated: 2026-11-21
---

# P15-37: multi-split guards that keep the LTT guarantee, interval over calibration draws (results)

Pre-registration: [plan.md](plan.md) and the theory note [method.md](method.md), commit `4e81f16`. Both were committed and pushed before any number was computed. Code: [`run.py`](run.py), [`launch.py`](launch.py), commit `6de1779` (smoke run on calibration subsets only). Stage S result and the plan addendum that names the primary arm: commit `77c3df6`, before the main run started. Aggregates (no text): [`results/selection.json`](results/selection.json), [`results/results.json`](results/results.json). Log: [`results/run.log`](results/run.log). Per-trial decisions (with text) are local only, in `C:\Users\zhang\bci-data\derived\p15-37\`.

Run details:
- Smoke (calibration subsets only): 2026-11-20 23:57 to 2026-11-21 00:21. Checks C1 and C2 passed on the smoke draws.
- Stage S (`val_select` only): 2026-11-21 00:21-01:03 (2,517 s, peak 2.65 GB). One process, 4 threads.
- Main run: 2026-11-21 01:03-07:29, detached. Two workers, background class, **2 threads each (4 in total)**, **CPU only, no GPU**. Peak private memory 2.83 GB per worker (total under 6 GB). About 17-19 min per draw per worker.
- Code: a `git archive` snapshot of `6de1779` in `derived/p15-37/snapshot/`, because other agents work in `src/`.
- All 41 draws (z0 + k01-k40) finished. No split guard was refused. No arm failed a null control (maximum 1 of 300 commits, allowed 15).

## Theory (method.md, short)
- Cross-fitting, jackknife+, CV+, cross-conformal and conformal risk control do **not** give the LTT guarantee P(R > 0.05) ≤ 0.1 at our size. Their known guarantees are marginal (in expectation), or have a factor 2 on alpha, or an extra term √(2 log(K/δ)/m) of about 0.17 (Bian & Barber 2023). We did not use them.
- Two multi-split rules keep the guarantee exactly: **AND** (commit only if all J split guards commit the same text; R(AND) ≤ R(g_1) pointwise, no correction) and **Bonferroni + any selection** (each split at δ/J; union bound). We tested only these.

## Stage S (selection on `val_select` only)
12 pseudo-calibration / pseudo-evaluation pairs (481 / 241 items). The rule chose **M = BMED-3** (3 splits at δ = 0.1/3, deploy the median guard by in-sample value), with a predicted 4.82 [2.84, 6.55]. No arm had a predicted lower end above 4.0153. Full table: [plan.md addendum](plan.md#addendum-2026-11-21-0105-stage-s-result-and-the-primary-arm-before-the-main-run).

## Verdict (pre-registered rule)

| arm | safe WPM v0.1 [95 %], calibration + trials, K = 40 | statuses | SD between / within | draws ≤ 4.0153 | mean commits / wrong | paired diff to A0 | verdict |
|---|---|---|---|---|---|---|---|
| **BMED-3 (primary M)** | **4.73 [2.60, 6.24]** | 40 certified | 0.88 / 0.34 | 9 / 40 | 187.5 / 12.7 | −0.53 | above, but inside the combined interval |
| A0 = S1 (P15-29 settings, new draws) | 5.26 [2.95, 6.89] | 40 certified | 0.92 / 0.35 | 4 / 40 | 211.2 / 16.6 | 0 | above, but inside |
| AND-2 | 4.82 [2.83, 6.29] | 40 certified | 0.83 / 0.34 | 6 / 40 | 189.6 / 12.5 | −0.44 | above, but inside |
| AND-3 | 4.55 [2.75, 5.89] | 40 certified | 0.78 / 0.33 | 9 / 40 | 177.5 / 10.5 | −0.71 | above, but inside |
| AND-4 | 4.37 [2.45, 5.78] | 40 certified | 0.81 / 0.33 | 11 / 40 | 169.9 / 9.5 | −0.89 | above, but inside |
| BMAX-2 | 5.39 [3.20, 6.83] | 40 certified | 0.82 / 0.36 | 2 / 40 | 215.5 / 17.1 | +0.12 | above, but inside |
| BMAX-3 | 5.29 [2.10, 6.77] | 39 certified, 1 above-alpha | 1.14 / 0.35 (0.76 certified only) | 3 / 40 | 219.3 / 17.8 | +0.03 | above, but inside |
| **R120** (P15-29 + P15-34 A0 + this A0; not blind) | 5.26 [2.94, 6.91] | 118 certified, 2 above-alpha | 1.04 / 0.35 (0.79 certified only) | 8 / 120 | - | - | above, but inside |

**The pre-registered criterion is not met.** The primary arm BMED-3 has a lower end of 2.60, below the no-BCI 4.0153. No arm and not R120 reaches it. The best lower end of any arm is BMAX-2 (3.20, descriptive only; it was not the stage-S choice).

## Variance comparison (required by the plan)

| set | between-draw SD (all draws) | certified only | within-draw SD |
|---|---|---|---|
| P15-29 (K = 40) | 1.43 | 0.79 | 0.35 |
| P15-34 A0 (K = 40) | 0.63 | 0.63 | 0.35 |
| **this run, A0 (K = 40, new draws)** | **0.92** | 0.92 | 0.35 |
| this run, BMED-3 (primary) | 0.88 | 0.88 | 0.34 |
| this run, AND-3 (lowest SD) | 0.78 | 0.78 | 0.33 |
| R120 (K = 120) | 1.04 | 0.79 | 0.35 |

- The multi-split rules reduce the between-draw SD only a little: by 4 % (BMED-3) to 15 % (AND-3) against the paired A0 on the same draws.
- They pay with the mean: −0.44 to −0.89 WPM for AND and BMED. BMAX-2 gains +0.12 in the mean, but its SD falls only to 0.82.
- The spread between draws stays 2.3-3.2 times the within-draw spread in every arm. The calibration sample, not the split, sets the lower end. This is the limit that method.md section 3 stated before the run.
- The certified-only SD of the P15-29 settings is 0.79 over 120 draws. P15-34 A0 (0.63) was a low-spread draw set: the new A0 set has SD 0.92 and a minimum of 2.82, so its lower end is 2.95, not 4.05.

## Rare unsafe draws
- AND and BMED remove unsafe draws in theory and in stage S (zero fraction 0 against 1 / 12 for S1).
- But in the main run the A0 draws had no above-alpha draw (0 / 40), so there was nothing to remove. Over R120, 2 / 120 draws are above alpha (both from P15-29). The LTT allows up to δ = 10 %.
- BMAX-3 produced 1 above-alpha draw that A0 did not have. This is allowed by the guarantee (≤ δ), but it shows that selecting the most aggressive of 3 guards raises the risk of a test-set failure.

## R120 (option 3, separate, not blind)
- Compatibility checks passed: X4 of P15-29 and P15-34 true; all 120 sheets have alpha 0.05, delta 0.1, n_ltt 271 and the pinned T; the 701 truths are equal; no seed overlap.
- 5.26 [2.94, 6.91], 2 above-alpha draws (1.7 % of the pooled mass). 8 / 120 draws are at or below 4.0153. This was the expectation stated in the plan. As pre-registered, R120 cannot close a gap.
- With K = 120 the lower end no longer jumps to 0 for one or two rare draws (P15-29 0.00). But it is still about 2.9, because the certified draws themselves spread widely (SD 0.79, range 2.82-6.82 over the three sets).

## Calibration size projection (pre-registered; a rough estimate, not a test)
- Basis R120: mean 5.264, between-draw SD 1.039 (all draws, with the two zeros), within-draw SD 0.352.
- Needed between-draw SD for mean − 1.96 √(σ_b² + σ_w²) = 4.0153: **0.531**.
- With σ_b ∝ 1/√n: **n* ≈ 2,760 calibration items**, about 3.8 times the 722 of `val_select` (the evaluation set stays 701).
- Exploratory, not pre-registered: with the certified-only SD (0.785) the same formula gives n* ≈ 1,580 (2.2 times). The zero draws do not shrink with n: LTT bounds them by δ at every n, so the pre-registered figure (with zeros) is the honest one.
- Assumptions: the mean and the within-draw SD stay fixed; the spread falls as 1/√n. Both are unverified.

## Code checks

| check | result |
|---|---|
| **X4** | **passes.** z0 split 1 = the P15-22 decisions on 701 / 701 trials; safe WPM 4.91; K = 1 interval [4.25, 5.57]; threshold 0.82, 196 commits, 13 wrong (= P15-29 z0). |
| C1 offline decisions = `guard.decide` (split 1, every draw) | passes (701 / 701 in all 41 draws) |
| C2 offline control counts = sheet counts (split 1, every draw) | passes |
| C3 recomputed LTT threshold = guard threshold (every split guard) | passes (164 guards) |
| C4 split parts disjoint by source trial, sizes 180 / 271 / 271 | passes |
| Stage S threshold check | passes (48 guards) |

## Hypotheses and expectations, answered honestly
- **Primary question: does a guarantee-keeping lower-variance calibration give a T15 lower end above 4.0153? No.** BMED-3 gives 2.60; the best arm (BMAX-2, descriptive) 3.20.
- **Expectation (plan): M has fewer zero draws, similar or smaller SD, a lower mean, lower end below 4.0153.** Lower mean and lower end: confirmed. Smaller SD: only slightly (0.88 vs 0.92). Fewer zero draws: not testable here, because the paired A0 had none.
- **Stage S ranking did not transfer.** Stage S put BMED-3 first and BMAX-2 low (it had one zero pair of 12). In the main run BMAX-2 was the best arm and BMED-3 lost 0.53 WPM against A0. With 12 small pairs, one zero pair dominated the predicted 2.5th percentile. This is a limit of the stage-S design (stated in the plan as "ranks arms; does not predict").
- **P15-34 A0 lower end 4.05:** not replicated. The same settings on 40 more draws give 2.95. The 4.05 came from a favourable draw set.

## Notes and limits
- The P15-29 limits apply: (a) pinned pipeline values; (b) duplicates in resampled parts (one draw's certificate is not a valid certificate; the draws show the sampling variation and may over-state it a little); (c) one participant, one decoder checkpoint; (d) the same evaluation set in every draw.
- (e) The group rule of splits 2-4 puts trials with many bootstrap copies a little more often into later parts; it uses no label. (f) Splits 2-4 ran their own controls with 20 trials; the arm controls used the 600 control inputs of split 1. No control failed.
- `docs/safe-wpm.md` is unchanged.

## Proposals (for the user to decide; no rule is changed)
1. **docs/safe-wpm.md section 6b (proposed reporting addition):** when the lower end of a calibration-draw interval is compared with a reference, report K, the number of non-credited draws and the certified-only SD next to the interval, and use K ≥ 80 (better 120). Reason: with K = 40 the same settings gave lower ends of 0.00 (P15-29), 4.05 (P15-34) and 2.95 (P15-37).
2. **Library (not done, would be a new item):** an optional `calibrate_multi(..., rule="and" | "bonferroni-select", J=...)` in `fidetype.trust` is safe by method.md, but this run shows no user value on T15 (AND costs 0.4-0.9 WPM; Bonferroni-select changes little). We do **not** propose to ship it now.

> **Our take:** the T15 lower end is limited by the size of the calibration set, not by how the set is split or how many draws are used. Every guarantee-keeping lever we tried (a margin in P15-34; six multi-split rules and K = 120 here) leaves the calibration-inclusive lower end between about 2.1 and 3.2. The pre-registered projection says that about 2,760 labelled calibration trials (3.8 times `val_select`) would be needed for a lower end above 4.02 at this mean. T15 has no such data outside `val_eval`. The honest T15 headline stays "about 5.2 safe WPM on average, interval about 2.9-6.9 including the calibration draw; above gaze typing on average, not reliably above".
