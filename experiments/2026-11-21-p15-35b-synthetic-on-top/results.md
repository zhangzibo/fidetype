---
title: P15-35b E1 synthetic sentences on top of recipe A, longer schedule - results
type: experiment
task: P15-35
updated: 2026-11-21
---

# P15-35b: synthetic sentences at 30 min, attempt 2 (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (`3a95935`, before any result of this attempt). Aggregates: [results/selection.json](results/selection.json) (val only), [results/summary.json](results/summary.json) and [results/text_pool_report.json](results/text_pool_report.json) (counts only). Weights, libraries, texts and logs stay local in `C:\Users\zhang\bci-data\derived\p15-35b\`.

## Summary
- **The selection rule picked F-R20** (forced cut, 20 % of batch items replaced by synthetic sentences, 4,000 steps, arm E). F-R20 was the only candidate that passed val-C2 with the margin of 0.03.
- **Test C2 passes for F-R20 / E:** deranged test CER **0.877** ≥ needed max(0.75, 0.747 + 0.10) = **0.847**. Normal test CER 0.747.
- **Gap 139 closes** by the done-when of the plan. The selected candidate uses the forced cut, so the done-when is met as written (no uniform-cut note is necessary).
- **The control A4K** (recipe A at 4,000 steps, no synthetic items) had a slightly lower normal val CER (0.738 vs 0.745). But A4K does **not** pass val-C2 with the margin (deranged 0.859 < 0.868). So the synthetic items did not improve the normal CER. They raised the deranged CER (0.897 vs 0.859): the model learned less of the label prior.
- Seed 1 (descriptive) was skipped by the pre-registered GPU-clock rule (6.20 h > 6.0 h).
- GPU use: **6.20 h** for the job (cap 8.0 h), plus about 0.15 h of smoke runs before the plan.

## Text pool and snippet libraries (seed 0)
The attempt-1 text pool was reused read-only (100,000 Tatoeba sentences; SHA-256 checked at start, OK).

| Library | Lag (frames) | Median snippet (frames) | P10 / P90 | Failed sentences |
|---|---|---|---|---|
| uniform, normal labels | - | 85 | 72 / 112 | 0 of 47 |
| uniform, deranged labels | - | 69 | 11 / 197 | 0 of 47 |
| forced, aligner A/E-b30-s0 | 26 | 87 | 52 / 132 | 0 of 47 |
| forced, aligner A/E-b30-s0-labelshuf (deranged) | 0 | 64 | 11 / 205.4 | 0 of 47 |

The normal libraries are the same as in attempt 1. Length guard (median ratio deranged / normal within ±30 %): uniform 0.812, forced 0.736. Both pass.

## Step 1-2: val-only search (arm E, 30 min, seed 0, 4,000 steps)
Final-step CER on the 106 val sentences. Eligible = normal val CER < 0.80. Needed (with margin) = max(0.75, normal + 0.10) + 0.03.

| Candidate | Val CER | Time-shuffled val CER | Best val CER (step) | Eligible | Deranged val CER | Needed with margin | Val-C2 with margin |
|---|---|---|---|---|---|---|---|
| U+50 (uniform, +50 % on top) | 0.780 | 0.883 | 0.769 (3,100) | yes | 0.904 | 0.910 | **fail** (by 0.006) |
| F+50 (forced, +50 % on top) | 0.788 | 0.842 | 0.784 (3,100) | yes | 0.916 | 0.918 | **fail** (by 0.002) |
| F+100 (forced, +100 % on top) | 0.791 | 0.853 | 0.787 (3,100) | yes | 0.858 | 0.921 | **fail** |
| **F-R20** (forced, 20 % replaced) | **0.745** | 0.900 | 0.744 (3,800) | yes | **0.897** | **0.875** | **pass** (by 0.022) |

Control (descriptive, not selectable; same rules applied for comparison):

| Control | Val CER | Time-shuffled val CER | Best val CER (step) | Deranged val CER | Needed with margin | Needed without margin |
|---|---|---|---|---|---|---|
| A4K (recipe A, 4,000 steps, no synthetic) | 0.738 | 0.908 | 0.737 (3,400) | 0.859 | 0.868 (fail) | 0.838 (pass) |

References: P15-33 recipe A at 2,000 steps (same subset): E val 0.769, deranged 0.871 (val-C2 pass by 0.002, test C2 fail 0.847 vs 0.873). Attempt 1 best: U50 / E val 0.813.

- Selection (2026-11-21 19:04:30): `selected: F-R20`, passing arms `[E]`. `selection.json` was written before any test number.

### Val CER during training (normal runs, every 500 steps)

| Step | A (P15-33, 2,000 steps) | U+50 | F+50 | F+100 | F-R20 | A4K |
|---|---|---|---|---|---|---|
| 500 | 0.847 | 0.872 | 0.902 | 0.880 | 0.853 | 0.860 |
| 1,000 | 0.769 | 0.793 | 0.821 | 0.827 | 0.777 | 0.764 |
| 1,500 | 0.777 | 0.801 | 0.814 | 0.817 | 0.774 | 0.760 |
| 2,000 | 0.769 | 0.785 | 0.797 | 0.809 | 0.760 | 0.762 |
| 2,500 | - | 0.801 | 0.795 | 0.803 | 0.772 | 0.746 |
| 3,000 | - | 0.776 | 0.794 | 0.795 | 0.747 | 0.739 |
| 3,500 | - | 0.776 | 0.788 | 0.794 | 0.747 | 0.738 |
| 4,000 | - | 0.780 | 0.788 | 0.791 | 0.745 | 0.738 |

### Val CER of the deranged runs (every 500 steps)

| Step | U+50 | F+50 | F+100 | F-R20 | A4K |
|---|---|---|---|---|---|
| 1,000 | 0.926 | 0.936 | 0.924 | 0.965 | 0.908 |
| 2,000 | 0.898 | 0.914 | 0.877 | 0.905 | 0.861 |
| 3,000 | 0.895 | 0.906 | 0.861 | 0.904 | 0.859 |
| 4,000 | 0.904 | 0.916 | 0.858 | 0.897 | 0.859 |

## Step 3: test C2 (selected candidate F-R20, arm E, seed 0)
Same weights as the search (final step); 80 test sentences.

| Run | Test CER (final) | Test CER (best-val step) | Time-shuffled test CER |
|---|---|---|---|
| normal | **0.747** | 0.746 | 0.887 |
| deranged | **0.877** | - | - |

- **C2 rule:** deranged ≥ max(0.75, 0.747 + 0.10) = 0.847. 0.877 ≥ 0.847: **pass** (by 0.030).
- For comparison, P15-33 recipe A on the same test block: normal 0.773, deranged 0.847, needed 0.873 (fail).

## Step 4-5: control and seed 1
- Control A4K: done (val only, numbers above). No test readout, as the plan says.
- **Seed 1: skipped.** Plan rule: seed 1 runs only if the GPU clock is ≤ 6.0 h when step 5 starts. The clock was 6.20 h at 19:55:02. The skip agrees with the pre-registration (`3a95935`: plan "Protocol" step 5 and `config.json` `seed1_start_max_hours: 6.0`).

## Run integrity
| Check | Evidence | OK |
|---|---|---|
| All runs finished | 4 normal + 4 deranged search runs and 2 control runs, 4,000 steps each, 40 val points each; `run.log` ends with `ALL DONE`; `DONE` 19:55:02 | yes |
| Skipped steps (non-finite loss) | 0 in every run | yes |
| Pause | the user put a `stop` file at 15:49:08 during F-R20 normal (saved `latest.pt` at step 1,347). Second launch 16:16:04; exact resume at step 1,347 (best val 0.7640 @ 1,300). This is a planned pause, not a fault. No other log gap > 5 min | yes |
| GPU clock | `gpu_clock.json` 22,309 s = 6.20 h (sum of the two launches; the 27-min pause is not counted) | yes |
| Test block | used only after `selection.json` (19:04:30); only for the selected candidate | yes |
| Synthetic share (per 100 steps) | U+50, F+50 about 30 % of items (about 1.4-1.5 synthetic per 3.4 real); F+100 about 48 %; F-R20 about 17-21 % | yes |
| Deviations from the plan | none | yes |

**Compute.** Launch 1: 13:16:13 to 15:49:08. Launch 2: 16:16:04 to 19:55:02. Job clock 6.20 h (cap 8.0 h). Smoke runs before the plan: about 0.15 h. Total about 6.35 GPU h.

## Limits
- 1 seed, 1 budget, 1 arm (E). Seed 1 was not run, so the pass is not checked on a second subset.
- The test margin is 0.030 and the val margin over the needed line is 0.022. Both are small. P15-33 showed that a small val pass can fail on test; here the test held.
- 4 candidates on one val block. Only one passed. The on-top candidates F+50 and U+50 failed by 0.002 and 0.006.
- The control A4K has the best normal val CER (0.738). The synthetic items did not lower the normal CER. Their effect is on the deranged run (higher CER), which is the C2 quantity.
- The deranged libraries have many very short and very long snippets (P10 11 frames, P90 about 200 frames). The median-based length guard passes, but the deranged snippet distribution differs from the normal one. This is part of the "whole pipeline sees wrong labels" control, but it is a possible confound for the C2 gap.
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM.

> **Our take:** a small synthetic share (0.2) with a longer schedule is enough to pass C2 at 30 min on this split. More synthetic items (on top) made the normal CER worse than the control and did not help C2 more. The main gain over P15-33 comes from the longer schedule (A4K normal 0.738 vs A 0.769) plus the synthetic items (which keep the deranged CER high). A second seed would make the result firmer.

## What this means for other items
- **P15-35 (gap 139):** closed by its done-when (pre-registered val pass with margin, then test C2 pass at 30 min for arm E, with the forced cut).
- **P15-36 (gap 140):** can start. It can use F-R20 at 4,000 steps as the minutes-scale recipe.
- Suggested new gap: seed-1 replication of F-R20 (normal + deranged, test C2), which the GPU-clock rule skipped here.

## Licence
- Willett data: CC0. E weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only.
- Tatoeba text (CC BY 2.0 FR, Tatoeba contributors): used for training only; not committed.
- This commit holds aggregate numbers only.
