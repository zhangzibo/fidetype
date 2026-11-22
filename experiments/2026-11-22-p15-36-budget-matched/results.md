---
title: P15-36 E1 budget-matched recipe - results
type: experiment
task: P15-36
updated: 2026-11-22
---

# P15-36: budget-matched recipe for E1 (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (`8790238`, before any result). Code and plan addendum 1 (file names only) `81ba625`, before the launch. Aggregates: [results/selection.json](results/selection.json) (val only), [results/summary.json](results/summary.json), [results/text_pool_report.json](results/text_pool_report.json) (counts only). Weights, libraries, texts and logs stay local in `C:\Users\zhang\bci-data\derived\p15-36\`.

## Summary
- **The val-only rule chose F-R20 at 3, 10 and 30 min and E1a at 100 min and "all".** This is the same as the roadmap example, so the fixed-rule check (descriptive) gives the same result.
- **V1 passes:** the best arm at "all" is E, with 0.395 (E1a runs, known before the plan).
- **Test C2 passes:** the deranged E 30-min seed-0 run has 0.877, and the needed value is 0.847 (normal 0.747; P15-35b run, known before the plan).
- **Gap 140 closes** by the done-when: a pre-registered rule, fixed before any test number, gives V1 pass and test C2 pass.
- **H1-H4 are now valid, and each one is `partial` (1 win of 3 budgets):**
  - H1: E beats T at 3 min only.
  - H2: E beats R at 30 min only.
  - H3: T beats R at 30 min only.
  - H4: E beats S at 30 min only.
- **C1 passes** (3 applicable runs). The roadmap rule passes: E beats T by more than the seed spread at 3 and 100 min.
- **Seed-1 C2 (descriptive) passes:** the deranged E 30-min seed-1 run has 0.870, and the needed value is 0.803 (normal 0.703). This is the second seed that P15-35b did not have.
- **GPU use: 6.00 h** (cap 8.0 h), in 2 launches.

## Step 2: val-only choice per budget
Mean final val CER over the 8 normal runs (4 arms x 2 seeds). The lowest admissible value is chosen (**bold**).

| Budget | F-R20 | A | E1a | Chosen |
|---|---|---|---|---|
| 3 min | **0.851** | 0.863 | 0.921 | F-R20 |
| 10 min | **0.825** | 0.862 | 0.907 | F-R20 |
| 30 min | **0.802** | 0.833 (not admissible) | 0.834 (not admissible) | F-R20 |
| 100 min | - | 0.862 | **0.811** | E1a |
| all | - | 0.875 | **0.666** | E1a |

30-min admissibility (val-C2 with margin, arm E, seed 0):

| Recipe | Normal val | Deranged val | Needed with margin | Pass |
|---|---|---|---|---|
| F-R20 | 0.745 | 0.897 | 0.875 | yes (length ratio 0.736, guard pass) |
| A | 0.769 | 0.871 | 0.899 | no |
| E1a | 0.821 | 0.844 | 0.951 | no |

`selection.json` was written at 2026-11-22 04:30:59. The first new test readout came after it (04:31:13).

## Step 4: test CER under the chosen recipes (means over seeds 0 / 1)
| Arm | 3 min (F-R20) | 10 min (F-R20) | 30 min (F-R20) | 100 min (E1a) | all (E1a) |
|---|---|---|---|---|---|
| R | 0.819 (0.840 / 0.799) | 0.802 (0.823 / 0.781) | 0.873 (0.925 / 0.822) | 0.837 | 0.613 (0.305 / 0.920) |
| T | 0.888 (0.855 / 0.920) | 0.783 (0.804 / 0.762) | 0.743 (0.739 / 0.747) | 0.777 | 0.805 |
| E | **0.808** (0.774 / 0.843) | **0.777** (0.778 / 0.775) | **0.725** (0.747 / 0.703) | **0.767** | **0.395** (0.360 / 0.431) |
| S | 0.867 (0.947 / 0.788) | 0.899 (0.970 / 0.827) | 0.889 (0.948 / 0.831) | 0.919 | 0.925 |

For comparison, the means of the same arms in E1a (E1a recipe at every budget) for E at 3 / 10 / 30 min are 0.957 / 0.884 / 0.812. P15-33 (recipe A at every budget) gives 0.858 / 0.780 / 0.766.

## Hypotheses (rule: Δ > seed spread and the lower end of the bootstrap CI95 > 0)
| Id | Budget | CER a / b | Δ | Spread | CI95 of Δ | Win |
|---|---|---|---|---|---|---|
| H1 E vs T | 3 | 0.808 / 0.888 | 0.079 | 0.069 | [0.066, 0.091] | **yes** |
| | 10 | 0.777 / 0.783 | 0.007 | 0.042 | [-0.007, 0.020] | no |
| | 30 | 0.725 / 0.743 | 0.018 | 0.044 | [0.006, 0.031] | no (Δ < spread) |
| H2 E vs R | 3 | 0.808 / 0.819 | 0.011 | 0.069 | [-0.002, 0.024] | no |
| | 10 | 0.777 / 0.802 | 0.025 | 0.041 | [0.009, 0.043] | no (Δ < spread) |
| | 30 | 0.725 / 0.873 | 0.149 | 0.102 | [0.123, 0.180] | **yes** |
| H3 T vs R | 3 | 0.888 / 0.819 | -0.068 | 0.065 | [-0.080, -0.056] | no (R is better) |
| | 10 | 0.783 / 0.802 | 0.019 | 0.042 | [0.002, 0.036] | no (Δ < spread) |
| | 30 | 0.743 / 0.873 | 0.131 | 0.102 | [0.102, 0.164] | **yes** |
| H4 E vs S | 3 | 0.808 / 0.867 | 0.059 | 0.159 | [0.048, 0.069] | no (Δ < spread) |
| | 10 | 0.777 / 0.899 | 0.122 | 0.144 | [0.108, 0.136] | no (Δ < spread) |
| | 30 | 0.725 / 0.889 | 0.165 | 0.117 | [0.149, 0.181] | **yes** |

| Id | Result | Status |
|---|---|---|
| **V1** | best at "all" = E 0.395 ≤ 0.50 | **pass** |
| **H1** (primary, F3) | 1 win (3 min) | **partial** |
| H2 | 1 win (30 min) | partial |
| H3 | 1 win (30 min) | partial |
| H4 | 1 win (30 min) | partial |
| **C1** | R-ball-s0 0.305 -> shuffled 0.877; E-ball-s0 0.360 -> 0.892; E-ball-s1 0.431 -> 0.948 (all ≥ 0.85). No run at 30 min is ≤ 0.70 (E-b30-s1 0.703) | **pass** (3 applicable) |
| **C2** | E-b30-s0 deranged 0.877 ≥ max(0.75, 0.747 + 0.10) = 0.847 | **pass** (by 0.030) |
| Roadmap rule | E beats T (clause (i)) at 3 min (0.079 > 0.069) and 100 min (0.010 > 0.003) | pass |

Learning curve (descriptive): only E reaches CER 0.60, at about 208 min (log interpolation between 100 min and all).

## Step 5: seed-1 C2 (descriptive)
F-R20, arm E, 30 min, seed 1. The deranged aligner was trained here (recipe A, 2,000 steps, deranged labels; lag 0, median snippet 64 vs 86 in the normal library).

| | Normal | Deranged | Needed | Pass |
|---|---|---|---|---|
| Val | 0.698 | 0.894 | 0.828 (with margin) | yes |
| Test | 0.703 | 0.870 | 0.803 | **yes** (by 0.067) |

## Descriptive: every candidate recipe per budget (mean test CER over 2 seeds; R / T / E / S)
| Budget | F-R20 | A | E1a |
|---|---|---|---|
| 3 | 0.819 / 0.888 / 0.808 / 0.867 | 0.826 / 0.886 / 0.858 / 0.887 | 0.865 / 0.960 / 0.956 / 0.919 |
| 10 | 0.802 / 0.783 / 0.777 / 0.899 | 0.845 / 0.871 / 0.780 / 1.039 | 1.327 / 0.863 / 0.884 / 0.922 |
| 30 | 0.873 / 0.743 / 0.725 / 0.889 | 0.873 / 0.803 / 0.766 / 0.953 | 0.851 / 0.786 / 0.812 / 1.003 |
| 100 | - | 0.939 / 0.749 / 0.786 / 0.974 | 0.837 / 0.777 / 0.767 / 0.919 |
| all | - | 0.976 / 0.848 / 0.713 / 0.984 | 0.613 / 0.805 / 0.395 / 0.925 |

At each of 3, 10 and 30 min, F-R20 has the lowest test CER for arm E of the three recipes. The val choice and the test numbers agree.

## Run integrity
| Check | Evidence | OK |
|---|---|---|
| All runs finished | 23 new F-R20 runs plus the seed-1 deranged aligner and run; `run.log` ends with `ALL DONE` at 05:13:44; `DONE` file | yes |
| Skipped steps (non-finite loss) | 0 in every run | yes |
| Pause | user GPU pause: `stop` file at 21:17, `latest.pt` at step 311 of R-b3-s0; second launch 23:15:44, `resume at step 311 (best val 0.8164 @ 200)`. No other log gap > 5 min | yes |
| GPU clock | `gpu_clock.json` 21,584 s = **6.00 h**: launch 1 (21:15:16-21:17:05) 0.03 h, launch 2 (23:15:44-05:13:44) 5.97 h | yes (≤ 8.0 h) |
| Test block | read only after `selection.json` (04:30:59) | yes |
| Synthetic texts | usable texts per library: 3 min 35,968 (seed 0) / 39,026 (seed 1); 10 min 88,188 / 59,726; 30 min 96,229-100,000 | yes |
| Deviations | plan addendum 1 (file names only, before the launch). No rule change | yes |

## Limits
- The two numbers that decide the done-when (V1 and C2 seed 0) were known before the plan, as the plan disclosed. The new evidence is the val-only choice per budget, H1-H4, C1 and the seed-1 C2.
- Every H is `partial`. The wins are not consistent across budgets. H1 (E vs T) wins only at 3 min. At 10 and 30 min E is better than T on average, but by less than the seed spread.
- H2-H4 win only at 30 min. Under F-R20 at 30 min, R and S are poor and unstable (R 0.925 / 0.822, S 0.948 / 0.831), so these wins partly measure the weakness of R and S under this recipe.
- Seed spreads are large at 3 min (S 0.159). Two seeds give a weak spread estimate.
- The forced aligners of R and S are weak: the lag is clipped at 99 frames in 6 of 12 R / S libraries. So for R and S the synthetic sentences may be close to noise.
- F-R20 was not run at 100 min or "all". The step factor 2 was checked only through the val choice.
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM.

> **Our take:** with a budget-matched recipe, E1 is valid at last (V1 and C2 pass, C2 also on seed 1). The answer to F3 at minutes scale is "partly". EMG pretraining is the best arm at every budget on average (0.808 / 0.777 / 0.725). But it beats text-only pretraining by more than the seed noise only at 3 min. At 30 min, both pretrained arms (E and T) clearly beat random and shuffled init. So most of the minutes-scale gain is "a pretrained trunk" more than "body signal". Firmer H1 numbers need more seeds (3-5) and the KT-sEMG arm.

## Licence
- Willett data: CC0. E, S and T weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only.
- Tatoeba text (CC BY 2.0 FR, Tatoeba contributors): training only; not committed.
- This commit holds aggregate numbers only.
