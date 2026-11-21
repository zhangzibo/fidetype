---
title: P15-33 E1 low-data recipe that reads the target signal - results
type: experiment
task: P15-33
updated: 2026-11-20
---

# P15-33: a low-data recipe for Willett handwriting (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (`a2906d8`, before any result). Amendment 1 (performance only, `415b481`, before any result was read). Aggregates: [results/selection.json](results/selection.json) (val only) and [results/summary.json](results/summary.json). Weights, per-sentence outputs and logs stay local in `C:\Users\zhang\bci-data\derived\p15-33\`.

## Summary
- **The search selected recipe A** (full fine-tune with strong regularisation and augmentation). It was the only recipe with an arm that passed val-C2: arm E, deranged val CER 0.871 against a threshold of 0.869, so it passed by 0.002.
- **Test C2 fails.** Arm E at 30 min with deranged labels gets 0.847. The threshold is max(0.75, 0.773 + 0.10) = 0.873. The narrow val pass did not hold on the test block.
- **V1 fails.** Under recipe A the best arm at "all" has test CER 0.713, and the gate is ≤ 0.50. Recipe A over-regularises at full data. Random init (R) does not learn at any budget (0.98 at all), and E reaches only 0.713 (P15-08 recipe: 0.395).
- **So H1-H4 are inconclusive by the pre-registered rule** (V1 is the validity gate). The raw win counts are reported below as descriptive numbers only.
- **Gap 120 stays open (partial).** The done-when needs at least one arm to pass C2 at 30 min and then a valid H1-H4 rerun. Neither condition holds on test.
- Descriptive progress: under recipe A, arm E at 30 min reads more of the signal than with the E1a recipe. Its time-shuffled test CER is 0.921 / 0.928 against a normal 0.773 / 0.760 (E1a: 0.852 / 0.858 against 0.810 / 0.815). The deranged-label gap grew from 0.026 to 0.074, which is still short of the 0.10 that C2 needs.

## Step 1-2: val-only search (30 min, seed 0)
Final-step val CER (106 val sentences). Eligible = normal val CER < 0.80. Val-C2 = deranged val CER ≥ max(0.75, normal + 0.10).

| Recipe | Arm | Val CER | Time-shuffled val CER | Eligible | Deranged val CER (needed) | Val-C2 |
|---|---|---|---|---|---|---|
| A strong reg + aug | R | 0.882 | 0.890 | no | - | no |
| A | **E** | **0.769** | 0.914 | yes | **0.871 (0.869)** | **pass** |
| B frozen trunk | R | 0.854 | 0.851 | no | - | no |
| B | E | 0.909 | 0.947 | no | - | no |
| C frozen + strong aug | R | 0.949 | 0.952 | no | - | no |
| C | E | 0.988 | 0.999 | no | - | no |
| D low LR, longer | R | 0.809 | 0.808 | no | - | no |
| D | E | 0.806 | 0.858 | no | - | no |

Reference (P15-08 E1a recipe, same subset, val, final step): E 0.821, deranged E 0.844.

- The selection rule picked **A** (the only passing recipe) at 2026-11-20 00:26:34. It was written to `selection.json` before the grid started.
- Freezing the trunk (B, C) is worse than full fine-tuning for both arms. With a frozen trunk, only 150,114 parameters train (the stem, out_norm and head), against 8,583,778 for a full fine-tune.
- Arm R reads nothing at 30 min under any recipe: its time-shuffled val CER is about equal to its normal val CER.

## Step 3: test CER per arm and budget (recipe A, final step)
Test = last block of each of the 10 sessions: 80 sentences, 3,448 characters. Greedy CTC, no LM. Mean of seeds (seed 0 / seed 1). In brackets: the P15-08 E1a mean with its own recipe.

| Budget | R random | T text-only | E EMG trunk | S shuffled E |
|---|---|---|---|---|
| 3 min | **0.826** (0.850 / 0.801) [0.865] | 0.886 (0.860 / 0.912) [0.960] | 0.858 (0.845 / 0.872) [0.957] | 0.887 (0.952 / 0.821) [0.919] |
| 10 min | 0.845 (0.871 / 0.818) [1.327] | 0.871 (0.800 / 0.941) [0.863] | **0.780** (0.763 / 0.796) [0.884] | 1.039 (0.947 / 1.131) [0.922] |
| 30 min | 0.873 (0.900 / 0.845) [0.851] | 0.803 (0.821 / 0.785) [0.786] | **0.766** (0.773 / 0.760) [0.812] | 0.953 (0.956 / 0.950) [1.003] |
| 100 min | 0.939 (0.924 / 0.954) [0.837] | **0.749** (0.742 / 0.756) [0.777] | 0.786 (0.779 / 0.793) [0.767] | 0.974 (0.982 / 0.967) [0.919] |
| all (506 min) | 0.976 (0.979 / 0.973) [0.613] | 0.848 (0.786 / 0.910) [0.805] | **0.713** (0.689 / 0.737) [0.395] | 0.984 (1.000 / 0.968) [0.925] |

- Recipe A helps arm E at 3, 10 and 30 min (by 0.10, 0.10 and 0.05 against E1a), and it helps T at 3 min.
- Recipe A hurts badly at 100 min and at full data. With all 506 minutes, R falls from 0.613 to 0.976 and E from 0.395 to 0.713. The regularisation that limits memorisation of 47 sentences also stops the model from fitting 781 sentences in 3,000 steps.
- Minutes to reach CER 0.60: not reached by any arm (E1a: E about 208 min).

The secondary readout (test CER at the best-val step) is within 0.05 of the final-step value for every arm and budget mean except two S cells: 10 min (0.913 vs 1.039) and all (0.917 vs 0.984). See `summary.json`, `bestval_mean`.

## Step 4: verdicts (pre-registered rules, unchanged from P15-08)
| Id | Rule | Result | Verdict |
|---|---|---|---|
| **V1** (gate) | best arm at "all" has test CER ≤ 0.50 | E at all **0.713** | **fail** |
| H1 (primary, F3) | E beats T at ≥ 2 of {3, 10, 30} | 1 raw win (30 min) | **inconclusive** (V1 fail) |
| H2 | E beats R at ≥ 2 of {3, 10, 30} | 2 raw wins (10, 30 min) | **inconclusive** (V1 fail) |
| H3 | T beats R at ≥ 2 of {3, 10, 30} | 1 raw win (30 min) | **inconclusive** (V1 fail) |
| H4 | E beats S at ≥ 2 of {3, 10, 30} | 2 raw wins (10, 30 min) | **inconclusive** (V1 fail) |
| C1 | time-shuffled test CER ≥ 0.85 for runs with CER ≤ 0.70 (budgets 30, all) | 1 run applies: E-all-s0 0.689 -> 0.931 | **pass** |
| **C2** | E, 30 min, seed 0, deranged labels: CER ≥ max(0.75, normal + 0.10) = 0.873 | **0.847** (normal 0.773) | **fail** |
| Roadmap rule (secondary) | E beats T by more than the seed spread (clause (i) only) at ≥ 1 of {3, 10, 30, 100} | yes at 30 min (Δ 0.037 > spread 0.036) | pass as written; not meaningful while V1 and C2 fail |

**Why V1 fails.** V1 asks if the target decoder works at all with all the data. Recipe A was chosen for the 30-min budget only. The plan applies one recipe to every budget, and A's regularisation (dropout 0.3, weight decay 0.05, channel dropout 0.2, 5 time masks, noise 0.5, time stretch) is too strong for 506 minutes in 3,000 steps. The best full-data arm reaches 0.713.

**Why H1-H4 are inconclusive.** The plan (P15-08 rule, reused) says: if V1 fails, H1-H4 are inconclusive, not null. A comparison of trunks is not valid when no arm makes a usable decoder at full data. Also, C2 fails on test, so at ≤ 30 min the numbers still contain a large label-prior part.

Pairwise numbers (descriptive only). Δ = CER(B) − CER(A), seed means; spread = largest seed difference; CI95 = paired bootstrap over the 80 test sentences.

| Pair (A beats B?) | 3 min: Δ / spread / CI95 | 10 min | 30 min | Raw wins |
|---|---|---|---|---|
| H1 E vs T | +0.027 / 0.052 / [+0.016, +0.038] | +0.091 / 0.141 / [+0.080, +0.103] | +0.037 / 0.036 / [+0.026, +0.047] | 1 |
| H2 E vs R | −0.033 / 0.048 / [−0.054, −0.007] | +0.065 / 0.053 / [+0.052, +0.079] | +0.106 / 0.055 / [+0.076, +0.154] | 2 |
| H3 T vs R | −0.060 / 0.052 / [−0.081, −0.034] | −0.026 / 0.141 / [−0.042, −0.010] | +0.070 / 0.055 / [+0.037, +0.118] | 1 |
| H4 E vs S | +0.028 / 0.131 / [+0.018, +0.039] | +0.259 / 0.184 / [+0.194, +0.334] | +0.187 / 0.013 / [+0.170, +0.208] | 2 |

> **Our take:** these numbers lean toward "the EMG trunk helps at 10-30 min under a recipe that limits memorisation". E is the best arm at 10 and 30 min, and its bootstrap interval against T is above 0 at all three H budgets. But the rules exist to stop this reading. V1 fails, C2 fails, and the T-arm seed spread at 10 min (0.141) is large. We do not claim H1.

## Controls
| Run | Test CER | Time-shuffled test CER |
|---|---|---|
| R 30 min s0 / s1 | 0.900 / 0.845 | 0.896 / 0.820 |
| T 30 min s0 / s1 | 0.821 / 0.785 | 0.829 / 0.904 |
| E 30 min s0 / s1 | 0.773 / 0.760 | **0.921 / 0.928** |
| S 30 min s0 / s1 | 0.956 / 0.950 | 0.955 / 0.999 |
| E all s0 / s1 | 0.689 / 0.737 | 0.931 / 0.901 |
| E 30 min s0, labels deranged (C2) | 0.847 | - |

- At 30 min, only arm E shows a clear drop from time-shuffled to normal input (about 0.16). R and S show none. T shows a drop on seed 1 only.
- The deranged-label run is 0.074 worse than the normal run (E1a: 0.026). That is progress, but the plan needs 0.10.

## Run integrity
| Check | Evidence | OK |
|---|---|---|
| All parts finished | 8 search runs + 1 deranged search run; selection 00:26:34; 41 grid runs (40 + the E C2 run; 3 reused from the search with an added test readout); summary; `DONE` 2026-11-20 07:24:34; `run.log` ends `ALL DONE` | yes |
| Interrupts | One planned stop only (amendment 1): first launch 22:39:36, stopped with the `stop` file at step 238 of A/R-b30-s0 (22:43:43). That run folder was deleted, and the run restarted from step 0 at 22:44:32. No crash and no machine sleep afterwards (no log gap > 5 min) | yes |
| Skipped steps (non-finite loss) | 0 in every run | yes |
| Steps | every run has its planned step count (600 / 1,000 / 2,000 / 2,000 / 3,000) | yes |
| Test block | not used in the search or the selection (`selection.json` has val numbers only; the search code computes no test number); not used for normalisation | yes |
| Reuse | A/R-b30-s0, A/E-b30-s0 and A/E-b30-s0-labelshuf reuse their search weights (same recipe, data and batches, as the plan says) | yes |

**Compute.** The plan allowed about 6.5-10.4 GPU hours (≤ 10 h target). Real use: 22:39:36 to 07:24:34 = **8.75 h** wall time, of which 4 min were discarded work from the first launch. Search 22:44-00:26 (1.70 h), grid and summary 00:26-07:24 (6.97 h). **There was no overrun:** the run used 8.75 h of the ≤ 10 h budget. An interim estimate during the run (11-12 h if A were selected) was too pessimistic. The full fine-tune ran at about 0.39-0.47 s/step against 0.32-0.39 s/step in the probe; the 3, 10 and 30-min runs are short, so the total stayed below the limit.

## Deviations
| Item | What | Effect |
|---|---|---|
| Amendment 1 | stretched batches post-padded to a multiple of 128 frames (performance only; first run restarted from step 0) | none on valid outputs (unit test) |
| Plan correction | the amendment header said 22:50; the true time is 22:44 (disclosed in plan.md) | none |

## Limits
- The search used 1 seed, 1 budget and 2 arms. Its pass was within 0.002 of the threshold, so a selection effect on val is likely. This is the reason the test C2 did not hold.
- One recipe for all budgets (pre-registered). A recipe tuned for 30 min cannot be expected to work at 506 min. A budget-dependent recipe (strong regularisation only at small budgets) would need a new pre-registration.
- The candidates change several factors at once. We do not know which part of A helps E at small budgets.
- No character time labels, so no Willett-style synthetic sentences in this search (stated in the plan).
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM; 2 seeds.

## What this means for other items
- **P15-33 (gap 120)** stays open, status `in_progress` (partial): val-C2 passed but test C2 fails, and V1 fails, so H1-H4 have no valid rerun.
- **New gap 139 = [P15-35](../../wiki/questions/roadmap-standard.md#p15-35-e1-synthetic-sentence-augmentation-for-the-minutes-scale-recipe-test-c2):** a minutes-scale recipe that passes C2 on **test**. The next step is Willett-style synthetic sentences built from character snippets of the budget sentences (character times from a forced alignment), with a larger margin on val.
- **New gap 140 = [P15-36](../../wiki/questions/roadmap-standard.md#p15-36-e1-budget-matched-recipe-so-that-v1-and-h1-h4-are-valid):** a budget-matched recipe rule (for example recipe A up to 30 min, the E1a recipe at 100 min and all), pre-registered, so that V1 holds and H1-H4 are valid.
- **P15-08** stays `in_progress`. The KT-sEMG arm should wait for P15-35 / P15-36, because it would hit the same floor.

## Licence
- Willett data: CC0. R-arm weights are clean-track. T, E and S weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only; each run folder has `licence.json`.
- This commit holds aggregate CERs only: no weights, signals, per-sentence outputs or text.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q experiments/2026-11-20-p15-33-low-data-recipe/test_p33.py` |
| Full run (detached, about 9 h GPU) | `.venv\Scripts\python.exe experiments\2026-11-20-p15-33-low-data-recipe\launch.py` |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-20-p15-33-low-data-recipe\p33.py summary` |
