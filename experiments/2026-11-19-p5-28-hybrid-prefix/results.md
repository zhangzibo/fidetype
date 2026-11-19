---
title: P5-28 hybrid streaming + end-of-trial prefix guard - results
type: experiment
task: P5-28
updated: 2026-11-19
---

# P5-28: hybrid streaming + end-of-trial prefix guard (results)

Pre-registration: [plan.md](plan.md), commit `e3cb0cb` (plan, `fidetype.trust.hybrid_commit`, tests and [`run.py`](run.py) in one commit, pushed before `evaluate` ran). Aggregates: [`results/results.json`](results/results.json); log: [`results/run.log`](results/run.log); guard file without text: [`results/guard-p5-28-hybrid.json`](results/guard-p5-28-hybrid.json). Per-trial decisions (with text): `C:\Users\zhang\bci-data\derived\p5-28\` (local only). Input: the P5-27 checkpoint views, read only (no new decoding).

> **Metric status.** All values use the **PROPOSED** safe-wpm/0.2 with the P14-28 reading cost (0.5 s per commit + 0.3 s per committed word) and the **PROPOSED** several-commits rule ([proposal section 7](../../docs/safe-wpm-v0.2-proposal.md#7-several-commits-per-trial-p5-27-proposed-extension-not-adopted)). None of them is adopted. v0.1 stays the adopted metric. The user decides.

## Verdict (T15, pre-registered rule)

**hybrid beats single.** The hybrid passes its controls and its safety rule, and it is certified. It gives more safe WPM than the one-commit P5-24 prefix guard, and it commits right words much earlier.

| arm | safe WPM v0.2 + reading cost [95 % CI] | trials with a commit | commit events | wrong trials / 701 [CP95] | right words |
|---|---|---|---|---|---|
| single (P5-24 prefix guard, one commit at the trial end) | 4.67 [4.26, 5.07] | 465 | 465 | 13 (0.0185) [0.0099, 0.0315] | 1,073 |
| **hybrid** (stream commits mid-trial at λ_mid 0.99 + P5-24 end decision at λ_end 0.94) | **4.89** [4.49, 5.27] | 500 | 803 | 18 (0.0257) [0.0153, 0.0403] | 1,143 |
| stream (P5-27) | 2.34 [2.11, 2.57] | 310 | 446 | 5 (0.0071) [0.0023, 0.0166] | 528 |
| Δ hybrid − single (paired trial bootstrap, B = 2,000) | **+0.22** [+0.14, +0.31], hw 0.08 | | | | |

Rule check: controls pass (uniform 0 / 300, shuffled 0 / 300; allowed 15) · safety holds (0.0257 ≤ 0.05; CP lower bound 0.0153, no clear violation) · status `certified` · Δ = +0.22 > hw = 0.08 → **hybrid beats single**.

- **H2 (non-inferiority, margin 0.25): pass** (2.5th percentile of Δ = +0.14 > −0.25).
- **H3 (earlier): pass.** Median latency of right committed words 3.85 s (hybrid) vs 11.20 s (single). First right word: median 2.72 s vs 14.00 s.
- **No-BCI reference 4.02:** the hybrid value (4.89) and its whole interval [4.49, 5.27] are above it, under the PROPOSED v0.2. Its v0.1 complete-only value is 1.03 (the same 44 complete commits as the single arm), below 4.02. Gap 53 (P14-23) was already closed by P15-22 (v0.1 4.91, commit `ab92a8e`); this result does not change that.

> **Caution (pre-registered disclosure; read with the verdict).** λ_mid = 0.99 is the threshold that P5-27 certified on the **same** 271 certify items. The joint LTT then re-used those items at δ = 0.1. The secondary Bonferroni arm, which splits δ over three λ_mid values, certifies λ_end 0.95 for λ_mid 0.99 and gives **4.63, Δ −0.04 [−0.15, +0.08]: no clear difference**. So the WPM gain is small and depends on the full δ. The latency gain does not depend on it.

## Reference checks

| check | result |
|---|---|
| guard and view ids (base `tcfg-e9758d5133d07fa6` = P5-24; views made with it, step 6; stream score `scfg-9171461e4f8cf0c2` = P5-27) | pass |
| split hashes (score-fit `285b8c0d9baf5a41`, certify `fadfd84557fcb24b`) | pass |
| 2. joint LTT with λ_mid = inf gives λ_end 0.94 (= P5-24) | pass |
| 1. end-only decisions (λ_mid = inf, λ_end 0.94) = single arm | **`run.py` reported 465 / 701.** Cause: a comparator flaw in `run.py`. It compared the action labels, and the single arm labels a non-commit `offer` (236 trials) while the hybrid labels it `no-commit`. A post-hoc check ([`refcheck.py`](refcheck.py), read only) compares commit / text / complete: **701 / 701**. The decisions agree; only the labels differ. |

Every hybrid decision event chain passed `check_chain` (`run.py` asserts it per trial).

## Secondary outcomes (reported, not decided)

| outcome | hybrid | single |
|---|---|---|
| v0.2 without reading cost | 5.17 [4.73, 5.60] | 4.87 [4.43, 5.30] |
| Δ without reading cost | +0.30 [+0.22, +0.39] | |
| v0.1 complete-only view | 1.03 (44 complete commits) | 1.03 (44) |
| prefix / complete commits (final text) | 456 / 44 | 421 / 44 |
| reading time (min, on 218.3 neural min) | 12.6 | 9.4 |
| Δ hybrid − stream (v0.2 + reading cost) | +2.55 [+2.27, +2.82] | |

**Hybrid guard.** λ_mid 0.99 (fixed), λ_end **0.94** certified on the joint trial loss (in-sample risk 0.0258, p = 0.037, LTT commit rate 0.723). Config id `hcfg-88aa7d41de821e9b`.

**Commits per trial:** 0: 201 · 1: 276 · 2: 160 · 3: 51 · 4: 11 · 5: 2 (224 trials with two or more). Trials with a mid-trial commit: 310. Trials with an end commit: 357. Trials whose mid-trial commit the end decision extended: 167. Conflicts: 0. Overlap with single: both commit 465; hybrid only 35; single only 0. Words committed: 1,181 (1,143 right in right trials).

**Commit latency** (P5-27 definition; 701 / 701 trials aligned):

| | hybrid | single | stream |
|---|---|---|---|
| right committed words: median (mean) [p10, p90] | **3.85 s** (6.41) [0.16, 16.01] | 11.20 s (11.67) [4.44, 19.13] | 1.44 s (1.47) [0.00, 2.88] |
| first right word per committing trial: median [p10, p90] | **2.72 s** [0.64, 18.12] (n 491) | 14.00 s [7.82, 21.74] (n 460) | 2.08 s [0.16, 3.40] (n 306) |
| committed words committed before the trial end | 45 % | 0 % | 100 % |

**Bonferroni sensitivity** (λ_mid ∈ {0.99, 0.98, 0.97}, δ/3 each):

| λ_mid | λ_end | safe WPM v0.2 + reading | Δ vs single | note |
|---|---|---|---|---|
| 0.99 | 0.95 | 4.63 (14 / 701 wrong) | −0.04 [−0.15, +0.08] | certified; controls 0 / 300, 0 / 300 |
| 0.98 | none passes | (3.72 scored) | | **not certified** (see below) |
| 0.97 | none passes | (4.16 scored, 41 / 701 wrong, above α) | | **not certified** (see below) |

For λ_mid 0.98 and 0.97 no λ_end passed. The first version of `calibrate_hybrid` then kept λ_mid, so the guard still made mid-trial commits without any bound, and the scorer labelled the 0.98 arm `certified` (it reads "no threshold found" as "the policy never commits"). Both values above therefore belong to an uncertified policy and are not results. Fix (in the results commit): if no λ_end passes, `calibrate_hybrid` sets λ_mid to inf too, so the guard never commits (new test `test_infeasible_certification_switches_off_mid_commits`). The primary arm was feasible, so the fix does not change it. The scorer behaviour is registered as gap 96 (P5-30).

> **Our take:** the hybrid does what P5-27 could not. The end decision extends the early commits (167 trials), so the hybrid keeps every trial that the single arm commits (465 / 465, same end score) and adds 35 trials that only the stream commits. It pays for this with 338 extra commit events (3.2 more reading minutes) and 5 more wrong trials. The net WPM gain is small (+0.22) and does not survive a δ split (−0.04 with λ_end 0.95). The latency gain is large and robust: the first right word appears a median 2.7 s after it ends, against 14.0 s. For a user, that is the main benefit: text appears while they are still speaking, at no WPM cost. A clean test of the WPM gain needs λ_mid fixed before any certify data is seen: T12 (fresh data, λ_mid 0.99 fixed now) is that test (gap 95 = P5-29).

## Limits

One participant, one split, one seed; conditional intervals only (decisions fixed). λ_mid came from P5-27 on the same certify items (disclosed in the plan). The word decoder sees each truncation as a whole sentence. Word ends come from our own decoder's forced alignment. The metric and its several-commits rule are proposals. T12 not run: no T12 checkpoint views exist (plan section T12).

## Gap status

- **Gap 92 (P5-28): closed.** A hybrid guard with mid-trial and end decisions under one trial loss, chained events, and a pre-registered T15 replay next to the one-commit guard exist. Verdict: hybrid beats single (with the caution above). The T12 part moves to gap 95.
- **Gap 53 (P14-23):** already closed by P15-22 (pre-registered v0.1 4.91 > 4.02). Not affected.
- **New gap 95 = P5-29:** T12 replication of the streaming and hybrid guards (new T12 streaming decode, λ_mid 0.99 fixed before any T12 data; loader under the memory cap).
- **New gap 96 = P5-30:** `safe_wpm` labels an infeasible guarantee `certified` even when the policy commits; it should refuse that combination.

## Run record

`evaluate` 18 s (peak 618 MB), `verdict` 0 s. One detached runner (`CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`) ran both stages under `python -m fidetype.utils.isolation run --class background --threads 4` with a keep-awake (`SetThreadExecutionState`); log `main.out` and DONE file in `C:\Users\zhang\bci-data\derived\p5-28\`; the runner skips a stage that already has a result. No stage was killed or restarted. Full pytest before the pre-registration commit: 1625 passed, 11 skipped.
