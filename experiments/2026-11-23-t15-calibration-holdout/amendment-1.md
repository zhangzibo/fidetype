---
title: T15 calibration hold-out - pre-run plan amendment 1 (sentence-group-aware calibration parts)
type: experiment-plan-amendment
task: P15-48 (gap 208)
amends: plan.md (pre-registration 29c1dc9; plan.md itself is not changed)
updated: 2026-11-24
---

# Amendment 1 to the T15 calibration hold-out pre-registration (before any run)

**Date:** 2026-11-24. **Status:** written **before any decoder of this task is trained, before any decode and before any calibration draw**. The only new numbers are counts from the labels and texts (no decoder output): the crossing audit below (`holdout.py crossing`, CPU, a few seconds).

**Scope.** No change of the decoder, the arms, K, the metric, the reference, the rules P1 / P2 / P3 / S, the outcomes or the stop rules. Two split rules change, both toward cleaner calibration data. If this file and plan.md disagree, the run follows this file.

## The problem
- Copy-task sentences repeat by design (plan.md: 1,418 train trials in 653 repeated sentences).
- The hold-out rule keeps each sentence group on one side of the **decoder** split. That part is correct.
- But inside a calibration draw, `fidetype.trust.calibrate` makes a **plain random split** of the pool (a seeded permutation, then `_split`: fit 25 %, then policy grid and LTT half each of the rest). Repeats of one sentence can land in the fit, policy-grid and LTT parts at the same time.
- The LTT step treats its items as fresh, independent draws. An LTT item whose sentence was also a fit or policy item is not fresh: the fitted temperatures, scores and policy have seen that sentence. So the certificate is a little optimistic.
- The same holds for the pipeline-tune set of rule 4: it takes **items** by a key hash, so a tune sentence can also be in the pool.
- Source of the point: the literature check of 2026-11-24 (finding F-4). We checked it on the data (below).

## Crossing audit on the existing data (CPU, labels and texts only)
File: [`results/crossing-audit.json`](results/crossing-audit.json) (counts only, no text). Draw seeds as in plan.md (first 8 hex digits of SHA-256(`t15-calho|<arm>|cal|<k>`), k = 1 .. 120). Pool order: hold-out calibration keys, then `val_select`; `calibrate` permutes it with the draw seed.

**Old rules (plan.md as written):**
| part | count |
|---|---|
| pipeline-tune set (250 items, 244 groups): tune sentence groups also in pool A | **41** groups (52 pool items) |
| arm A (pool 2,688 items, 2,504 groups, 159 repeated): groups in two or more of fit / policy / LTT, per draw | **mean 109.6** (min 96, max 123), holding 242.5 items |
| arm A: groups in all three parts, per draw | mean 5.1 (max 12) |
| arm A: LTT items (of 1,008) that share a sentence with a fit or policy item, per draw | **mean 87.5** (min 67, max 105) |
| arms B and R (`val_select`, 722 items, 710 groups, 6 repeated): crossing groups per draw | mean 5.4 (B) and 5.3 (R), max 6; about 6 LTT items per draw |

Also reported (not a calibration part): 24 pool-A groups also occur in `val_eval` (28 `val_eval` items). This is the normal repeat structure of the task and is not changed.

## The change
1. **Rule 5 (replaces rule 4): the pipeline-tune set takes whole sentence groups.** Groups of the hold-out in the order of SHA-256(`SALT|tune-group|<text>`), skipping any group that also has a `val_select` trial, are added until the set has at least 250 items. The rest of the hold-out joins the pool. Result: **250 items (220 groups)**, pool A **2,688 items (2,487 groups)**, **0** tune groups in the pool.
2. **Rule 6: every calibration draw is group-aware.** Each `calibrate` call of this experiment (arms A, B and R, all 120 draws) passes `groups=` = the normalised sentence text of each pool item. All repeats of a sentence then fall in one part. The group order comes from the draw seed; the part sizes are the group boundaries closest to the plain sizes (draw 1 of arm A: 672 / 1,008 / 1,008, as before). Audit with the new rules: **0** crossing groups in every draw of every arm.
3. **Library.** `fidetype.trust.calibrate` gets an **opt-in** argument `groups=` (default `None`). The default path is unchanged: a test pins the configuration id of a reference calibration to the value of the parent commit, and the guard file is the same with and without `groups=None` (we also compared it with the parent-commit code: identical except the creation time). No library default changes, so **no published number changes**.

## What stays open (reported, not fixed)
- Repeats **inside** the LTT part stay correlated, and the binomial p-value of LTT still treats them as independent. With rule 6, arm A has about 932 distinct sentences among its 1,008 LTT items per draw (B / R: about 267 of 271). We report the LTT group count of every draw.
- Sensitivity (descriptive, computed by this experiment's analysis script, no library change): the safe-WPM interval with a sentence-group cluster bootstrap of `val_eval` next to the trial bootstrap of plan.md. The plan's interval stays the primary metric.

## Expected effect
- Each draw's guard is calibrated on parts that share no sentence, so its LTT certificate is no longer optimistic in this way. The guard can become slightly more conservative (fewer commits), which can lower the safe WPM a little. This is the safe direction.
- Arm R (M4-13 reference) also uses rule 6, so the three arms stay comparable. Earlier published reference numbers came from other protocols and are not changed.

## Code and tests
- `holdout.py`: `split_tune_groups` (rule 5), `pool_groups` (rule 6), `draw_seed`, `part_crossing`, `crossing_audit`, `load_parts`, and the command `crossing`.
- `src/fidetype/trust/dropin.py`: `calibrate(..., groups=None)` and `_group_split`; tests in `tests/test_trust_dropin_groups.py`.
- `test_holdout.py`: CPU tests of rules 5 and 6 and of the audit (no data needed).
