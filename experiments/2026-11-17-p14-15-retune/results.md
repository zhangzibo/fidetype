---
title: P14-15 word-decoder settings re-tuned without evaluation trials - results
type: experiment
task: P14-15
updated: 2026-11-17
---

# P14-15: results

Pre-registration: [plan.md](plan.md) (commit `fc8478c`, before any run). Script: [run.py](run.py). Numbers: [results/tune.json](results/tune.json) (step 1), [results/step2.json](results/step2.json) (step 2), [results/posthoc-forward-chain.json](results/posthoc-forward-chain.json) (post hoc). Local only: `C:\Users\zhang\bci-data\derived\p14-15-retune\` (grid decodes with top-1 texts, 35 rebuilt item tables, logs). CPU only, background class, 4 threads, one process at a time (peak about 1.1 GB).

## Decision
- **Paper 1 re-split "B2T ours" rows: no effect** (pre-registered rule). The re-tune inside fit-A changed the setting in 35 of 200 re-splits (8 of the 50 R3 splits). After we rebuilt these 35 splits, **0 of 80** primary metrics changed by their CI half-width or more. The largest change was 0.27 of the half-width.
- **M4-x word-level results: the setting changes on T2a.** Without the 16 `val_eval` trials (384 trials), the rule picks edit penalty 8 instead of 12. Both points have the **same** WER (0.16477); the tie goes to the higher truth-in-n-best (0.5469 vs 0.5443). Without `val_eval` and `val_select` (368 trials), the paper point stays first. Per the plan, the M4-x results are not rerun here: new gap 44 (P14-18).

## Sanity checks (all passed before any result was read)
| Check | Result |
|---|---|
| Grid decodes on the 400 original tune trials = `b2t25-trust/results/tune.json` (12 rows) | max deviation 0.0; choice lm 1.0, edit 12, bonus 3 |
| Fit-A of fixed splits A and B = R3 [b2t-retune](../2026-11-12-paper1-r3-analyses/b2t-retune/results.md) rows | max deviation 0.0 (411 trials each) |
| Rebuild code path, split 0 with the paper setting, first 100 test items = committed R3 table | all 11 arrays equal; same T (3.44) and plug-in λ (0.5) |
| fit-A ∩ test, fit-A ∩ clean cal per re-split | 0 in all 200 splits |
| Rebuilt splits: frame temperature | equal to the original in all 35 (it does not depend on the word decoder) |

## Step 1: chosen setting per tune set
| Tune set | n | Choice | Same as paper | Paper point rank | WER choice / paper point |
|---|---|---|---|---|---|
| T1: fit-A of the 200 re-splits | 405 each | paper point 165; lm 1.0 / edit 12 / bonus 6: 28; lm 0.5 / edit 8 / bonus 3: 3; lm 0.5 / edit 12 / bonus 3: 2; lm 1.0 / edit 8 / bonus 3: 1; lm 0.5 / edit 12 / bonus 6: 1 | 165 / 200 (R3 splits: 42 / 50) | 1: 165, 2: 28, 3: 3, 4: 3, 5: 1 | WER gap mean 0.00004, max 0.0020 |
| T2a: 400 tune minus 16 `val_eval` | 384 | lm 1.0, edit 8, bonus 3 | **no** (exact WER tie) | 2 | 0.16477 / 0.16477 |
| T2b: 400 tune minus 16 `val_eval` and 16 `val_select` | 368 | lm 1.0, edit 12, bonus 3 | yes | 1 | 0.16482 / 0.16482 |

28 of the 35 changes are exact WER ties with bonus 6. The tie goes to the higher truth-in-n-best rate.

The 400 tune trials by M4 part (audit match): train 343, val_select 16, val_eval 16, HDF5 test 2, unmatched 23.

## Step 2: re-split rows with each split's own setting
We rebuilt the "b2t-ours" guard-on tables of the 35 changed splits. The other 165 keep their committed tables. Then we reran the R3 aggregation (`split_policies`, 8 policies). CI half-width = 1.96 × SD / √R of the original per-split values (Wilson for shares and the pooled error among commits).

| R | changed splits | metrics | changes ≥ half-width | largest change / half-width |
|---|---|---|---|---|
| 50 (R3) | 8 | 40 | **0** | 0.26 (LTT max-rule commit rate 0.1468 → 0.1447, half-width 0.0078) |
| 200 (R4) | 35 | 40 | **0** | 0.27 (LTT max-rule share > α 0.075 → 0.065, half-width 0.037) |

Selected rows (original → recomputed):

| R | Policy | Mean wrong-commit | Mean commit rate | Mean eWPM | Share wrong-commit > α |
|---|---|---|---|---|---|
| 50 | plug-in (fit-A) | 0.0440 → 0.0435 | 0.1855 → 0.1829 | 11.083 → 11.077 | 0.34 → 0.32 |
| 50 | CRC pure (clean) | 0.0456 → 0.0456 | 0.1924 → 0.1916 | 11.087 → 11.082 | 0.34 → 0.34 |
| 50 | LTT max-rule (clean) | 0.0304 → 0.0299 | 0.1468 → 0.1447 | 11.065 → 11.060 | 0.08 → 0.06 |
| 200 | plug-in (fit-A) | 0.0417 → 0.0415 | 0.1785 → 0.1774 | 11.109 → 11.105 | 0.305 → 0.295 |
| 200 | CRC pure (clean) | 0.0486 → 0.0483 | 0.1985 → 0.1976 | 11.118 → 11.114 | 0.44 → 0.435 |
| 200 | LTT max-rule (clean) | 0.0321 → 0.0319 | 0.1515 → 0.1506 | 11.098 → 11.094 | 0.075 → 0.065 |

All 80 rows are in [results/step2.json](results/step2.json). The committed R3 / R4 tables stay as they are. They get a "no effect" line, not a correction.

## Post hoc (not pre-registered)
- **Forward chain (R4).** V1, V2 and V4 test on whole days, so the tune trials of a test day are in its test set. A re-tune on each fit prefix (all trials of days 1..j) keeps the paper point for j = 2..13. Only j = 1 (day 1 alone, 30 trials) picks lm 1.0, edit 8, bonus 3. This prefix is used by one test day in V1 (day 3) and one in V4. Not rerun: part of gap 45 (P14-19).
- **Published gate.** `published_plus_fn` uses our word n-best: our best score sets the gate score, and our top-1 gives the word confidences. So the "B2T published" re-split rows also depend on the word setting. The audit called them clean. We did not rebuild them (not in the plan): gap 45 (P14-19).
- **Downstream analyses.** R4 population-risk, per-day, reuse, joint-LTT, no-guard (guard-off tables), M2-18, M3-01/02, trust v5 and A2 read the same split tables. Step 2 found no effect on the source tables, so the plan does not ask for these reruns. Gap 45 covers them together with the published gate.

## Limits
- Ties decide most changes. A different tie rule (for example, keep the incumbent point on equal WER) would give 7 changed splits of 200 and no change on T2a.
- The CI half-widths are Monte-Carlo half-widths over splits of one finite data set (as in R3). They are not CIs for new data.
- Only the guard-on "ours" tables were rebuilt.

> **Our take:** the indirect overlap had no measurable effect on the re-split results. The tuning surface is flat near the paper point: most "changes" are exact WER ties. For the M4 rows the change is also a tie, and the roadmap variant (T2b) keeps the paper point. So the M4 bias is probably zero in practice. Gap 44 checks this with one decode of `val_eval`.
