---
title: P15-35 E1 synthetic-sentence augmentation for the minutes-scale recipe - results
type: experiment
task: P15-35
updated: 2026-11-21
---

# P15-35: Willett-style synthetic sentences at 30 min (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (`218d889`, before any result). Aggregates: [results/selection.json](results/selection.json) (val only), [results/summary.json](results/summary.json) and [results/text_pool_report.json](results/text_pool_report.json) (counts only). Weights, libraries, texts and logs stay local in `C:\Users\zhang\bci-data\derived\p15-35\`.

## Summary
- **No candidate passed. The job stopped after the search with `no_recipe`, as the plan says.** No test-block number was computed.
- **No (candidate, arm) was eligible.** Eligible = normal final val CER < 0.80. The best was U50 / E at 0.813. So no deranged run was made, and val-C2 could not be tested.
- **Synthetic sentences made val CER worse than recipe A alone.** Arm E: A 0.769 (P15-33), U50 0.813, F50 0.836, F80 0.913. A higher synthetic fraction was worse (F80 < F50).
- **Gap 139 stays open.**
- GPU use: **1.08 h** for the job (cap 9.0 h), plus about 0.03 h of smoke runs before the plan.

## Text pool (step 0)
| Item | Value |
|---|---|
| Tatoeba English lines read | 2,040,567 |
| After character set, length 10-90 and de-duplication | 1,893,103 |
| Blocked texts (Willett all 1,000 + T15 cue 1,718) | 2,624 unique |
| Rejected by the block rule while sampling | 525 |
| Pool | 100,000 sentences, mean length 36.29 characters |

## Snippet libraries (seed 0, normal labels)
| Library | Lag (frames) | Median snippet (frames) | P10 / P90 | Failed sentences |
|---|---|---|---|---|
| uniform | - | 85 | 72 / 112 | 0 of 47 |
| forced, aligner A/R-b30-s0 | 38 | 88 | 60.6 / 125 | 0 of 47 |
| forced, aligner A/E-b30-s0 | 26 | 87 | 52 / 132 | 0 of 47 |

All 31 characters had snippets (2,027 snippets, 47 tails per library). No deranged library was built, because no run was eligible.

## Step 1-2: val-only search (30 min, seed 0, 2,000 steps)
Final-step val CER on the 106 val sentences. Eligible = normal val CER < 0.80.

| Candidate | Arm | Val CER | Time-shuffled val CER | Best val CER (step) | Eligible | Val-C2 with margin |
|---|---|---|---|---|---|---|
| U50 uniform, 0.5 | R | 0.939 | 0.951 | 0.935 (1,000) | no | not tested |
| U50 | E | **0.813** | 0.904 | 0.813 (1,800) | no | not tested |
| F50 forced, 0.5 | R | 0.940 | 0.948 | 0.936 (1,300) | no | not tested |
| F50 | E | 0.836 | 0.923 | 0.836 (1,900) | no | not tested |
| F80 forced, 0.8 | R | 0.961 | 0.961 | 0.959 (1,800) | no | not tested |
| F80 | E | 0.913 | 0.951 | 0.913 (1,800) | no | not tested |

Reference (P15-33 recipe A, no synthetic sentences, same subset, val, final step): R 0.882 (shuffled 0.890); E 0.769 (shuffled 0.914), deranged E 0.871.

Val CER of arm E during training (every 500 steps):

| Step | A (P15-33) | U50 | F50 | F80 |
|---|---|---|---|---|
| 500 | 0.847 | 0.945 | 0.975 | 0.999 |
| 1,000 | 0.769 | 0.870 | 0.880 | 0.970 |
| 1,500 | 0.777 | 0.833 | 0.858 | 0.929 |
| 2,000 | 0.769 | 0.813 | 0.836 | 0.913 |

- Selection (2026-11-21 13:00:31): `selected: null`. The job wrote the summary and `DONE` (`no_recipe`) and stopped.

> **Our take:** the synthetic runs were still improving at step 2,000, while recipe A had flattened by step 1,000. Each step had about half (U50, F50) or a fifth (F80) as many real sentences as recipe A, and the number of steps was the same. So the result may show a schedule effect (too few updates on real data), not only a bad synthetic distribution. Arm R did not learn under any candidate (time-shuffled ≈ normal). The uniform cut was better than the forced cut at the same fraction (0.813 vs 0.836), so the weak aligner did not help.

## Run integrity
| Check | Evidence | OK |
|---|---|---|
| All search runs finished | 6 normal runs, 2,000 steps each, 20 val points each; `run.log` ends with `no_recipe`; `DONE` 13:00:31 | yes |
| Skipped steps (non-finite loss) | 0 in every run | yes |
| Interrupts | none: one launch at 11:55:44, no stop file, no log gap > 5 min | yes |
| Test block | not used: no test readout was run (selection `null`) | yes |
| Synthetic share | logged per 100 steps: about 47 % (U50, F50) and 79 % (F80) of batch items | yes |
| Deviations from the plan | none | yes |

**Compute.** Job wall time 11:55:44 to 13:00:31 = 1.08 h (`gpu_clock.json` 3,885 s). Smoke runs before the plan: about 2 min. Total about 1.1 GPU h, far below the 9.0 h cap.

## Limits
- 1 seed, 1 budget, 3 candidates. All candidates kept recipe A and 2,000 steps. A longer schedule, a fixed number of real sentences per step, or a lower synthetic fraction (for example 0.2) were not tested.
- The forced aligner is weak (its own val CER is about 0.77). Better character times would need a better aligner or labelled single-letter data (`singleLetters.mat`, which is outside the budget).

## What this means for other items
- **P15-35 (gap 139)** stays open. The done-when (pass val-C2 with a margin, then test C2) is not met: no candidate was even eligible.
- **P15-36 (gap 140)** is still blocked by gap 139 (it needs a 30-min recipe that passes test C2).
- Suggested next step (new gap): a pre-registered pilot that keeps the real-sentence count per step of recipe A and adds synthetic sentences on top (or uses a fraction ≤ 0.2 with a longer schedule, for example 4,000 steps), on the val block only, with the same margin and length guard.

## Licence
- Willett data: CC0. R-arm weights are clean-track. E weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only.
- Tatoeba text (CC BY 2.0 FR, Tatoeba contributors): used for training only; not committed.
- This commit holds aggregate numbers only.
