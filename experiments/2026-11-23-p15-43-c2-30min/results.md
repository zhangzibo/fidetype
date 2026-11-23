---
title: P15-43 C2 budget range of the F-R20 recipe - results
type: experiment
task: P15-43
updated: 2026-11-23
---

# P15-43: C2 budget range of F-R20 (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (`bd673ae`, 2026-11-22 22:11:35, before any result). Code `6235d69` (22:13:35), before the launch. Aggregates: [results/summary.json](results/summary.json). Weights, libraries, texts, per-sentence outputs and logs stay local in `C:\Users\zhang\bci-data\derived\p15-43\`.

## Summary
- **Outcome C of the plan.** C2 passes on every seed at **none** of {3, 10, 30} min.
- **30 min fails on all 3 new seeds.** Deranged test CER 0.849 / 0.889 / 0.860; needed 0.865 / 0.922 / 0.871 (seeds 2 / 3 / 4). Seeds 0 and 1 (P15-35b / P15-36) still pass.
- **3 min fails.** Seed 0 passes (0.891 ≥ 0.874, margin 0.017). Seed 1 fails (0.877 vs 0.943). The stop rule applied: seeds 2-4 were not run (not needed).
- **10 min** was already a fail (P15-41, seeds 2-4).
- **100 min was not tested** (plan: no F-R20 100-min recipe). We do not claim that 100 min fails.
- **GPU use: 2.22 h** (cap 4.5 h), in 1 launch (2026-11-22 22:13:42 to 2026-11-23 00:26:40). 5 new deranged runs, each with its own deranged aligner.

## C2 table: arm E, deranged labels (rule: deranged test CER ≥ max(0.75, normal + 0.10), final step)
Margin = deranged − needed. A positive margin is a pass. **Bold** = new in this task.

| Budget | Seed | Normal test | Deranged test | Needed | Margin | Pass | Source of the deranged run |
|---|---|---|---|---|---|---|---|
| 3 min | 0 | 0.774 | **0.891** | 0.874 | **+0.017** | **yes** | P15-43 |
| | 1 | 0.843 | **0.877** | 0.943 | **−0.066** | **no** | P15-43 |
| | 2-4 | 0.809 / 0.785 / 0.790 | not run | 0.909 / 0.885 / 0.890 | | not needed (stop rule) | |
| 10 min | 0, 1 | | not run | | | | |
| | 2 | 0.806 | 0.883 | 0.906 | −0.023 | no | P15-41 |
| | 3 | 0.771 | 0.844 | 0.871 | −0.027 | no | P15-41 |
| | 4 | 0.789 | 0.787 | 0.889 | −0.101 | no | P15-41 |
| 30 min | 0 | 0.747 | 0.877 | 0.847 | +0.030 | yes | P15-35b |
| | 1 | 0.703 | 0.870 | 0.803 | +0.067 | yes | P15-36 |
| | 2 | 0.765 | **0.849** | 0.865 | **−0.016** | **no** | P15-43 |
| | 3 | 0.822 | **0.889** | 0.922 | **−0.033** | **no** | P15-43 |
| | 4 | 0.771 | **0.860** | 0.871 | **−0.011** | **no** | P15-43 |

| Budget | Status (all 5 seeds) |
|---|---|
| 3 min | **fail** (seed 1) |
| 10 min | **fail** (seeds 2, 3, 4) |
| 30 min | **fail** (seeds 2, 3, 4) |
| **Smallest passing budget** | **none of {3, 10, 30}** |
| 100 min | not tested |

## Descriptive (no decision)
| Run | Aligner val CER | F-R20 val CER (final) | Best val (step) | Test CER | Library median snippet (deranged / normal) | Usable texts |
|---|---|---|---|---|---|---|
| E-b30-s2-labelshuf | 0.851 | 0.831 | 0.828 (2,800) | 0.849 | 66 / 91 | 88,188 |
| E-b30-s3-labelshuf | 0.863 | 0.888 | 0.878 (2,100) | 0.889 | 68 / 89 | 100,000 |
| E-b30-s4-labelshuf | 0.866 | 0.886 | 0.873 (2,900) | 0.860 | 53 / 90 | 100,000 |
| E-b3-s0-labelshuf | 0.865 | 0.785 | 0.785 (1,200) | 0.891 | 78 / 88.5 | 35,968 |
| E-b3-s1-labelshuf | 0.935 | 0.802 | 0.791 (800) | 0.877 | 69 / 89 | 39,026 |

- The margins at 30 min on the new seeds are small (−0.011 to −0.033). The pass margins on seeds 0 and 1 are also small (+0.030, +0.067). So the 30-min result is near the threshold on every seed. One deranged run per seed (no repeat) cannot separate a true gap of about 0.08-0.10 from a gap of 0.10 or more.
- At 3 min, seed 0 passes on test, but its deranged val CER (0.785) is lower than the normal val CER of the same seed (0.810, P15-36). So the seed-0 pass is fragile.
- The deranged libraries have shorter median snippets than the normal ones (ratio 0.59-0.88). On seed 4 at 30 min the ratio (0.59) is outside the P15-36 length guard (±0.30). The plan used the test rule only, so this does not change the result. It shows that a deranged aligner cuts the signal differently.

## What outcome C means for the E1 claim
- **No minutes-scale budget has a valid label-deranged control on every seed.** With F-R20 at ≤ 30 min, a decoder trained on wrong labels is less than 0.10 CER worse than the normal decoder on at least one seed at every budget. So the normal decoders mostly learn the label (text) prior. Only a small part of their CER comes from reading the signal.
- **All minutes-scale H1 numbers of P15-36 and P15-41 are invalid** under the gap-194 rule ("E1 arm comparisons use only budgets where C2 passes on every seed"). This includes the 30-min null (d = −0.002 [−0.034, 0.031]) and the 3-min win (0.095 [0.066, 0.124]). Neither is evidence for or against EMG pretraining.
- **E1 at minutes scale (3-30 min) is "no valid test" with the F-R20 recipe.** F3 rests on the full-data result only (E1a / P15-36 "all": E 0.395, V1). The minutes-scale question stays open, but more seeds of this recipe cannot answer it.
- **P15-36 C2 at 30 min (2 of 2 seeds) was a small-sample pass.** On 5 seeds, 3 of 5 fail by small margins.

> **Our take:** the problem is not the control. It is that at ≤ 30 min the decoders read too little of the signal (normal test CER 0.70-0.82). A 100-min C2 with F-R20 needs a new recipe choice and about 12 GPU h. It would only tell us whether the threshold is crossed at 100 min, and E1a already reported C2 failing at ≤ 100 min with its own recipe. We think a better next step is (1) a C2 at the full-data budget, where E reaches 0.395 and a gap of 0.10 should be easy to see, so that the one positive F3 result has a control on more than one seed; and (2) a fixed, cheaper control readout (for example several deranged draws per seed, or a paired sentence bootstrap of the deranged − normal gap), so that a margin near 0 is not decided by one run.

## Run integrity
| Check | Evidence | OK |
|---|---|---|
| Plan before results | plan `bd673ae` 22:11:35; code `6235d69` 22:13:35; launch 22:13:42 | yes |
| One GPU job | no python process at launch (checked twice) | yes |
| Recipe unchanged | `test_recipe_unchanged_from_p15_41` (F-R20 keys and C2 rule equal to P15-41) | yes |
| Stop rule | S3 stopped after the first fail (seed 1); seeds 2-4 `not_needed` in `stages.json` | yes |
| Reused results read-only | old normal / deranged results from P15-35b / P15-36 / P15-41 folders; output only in `derived/p15-43` (`check_out`) | yes |
| Numbers | this page matches `results/summary.json` (status `done`, outcome `C`, smallest `none`) | yes |
| GPU cap | 2.22 h of 4.5 h; no FAILED file | yes |
| Aggregates only | no per-sentence numbers, weights or texts in the repo | yes |

## Records to apply
For the orchestrator. This task did not edit any shared record file.

- **Gap 194 = P15-43: `done`, negative result.** Done-when met: C2 at 30 min reported for seeds 2-4 (all fail), and the smallest budget in {3, 10, 30} where C2 passes on all 5 seeds is **none**. 100 min was not tested (no F-R20 100-min recipe; plan). Commits: plan `bd673ae`, code `6235d69`, results (this commit). GPU 2.22 h, one launch 2026-11-22 22:13:42 to 2026-11-23 00:26:40.
- **P15-08 / E1 / north star (F3 row):** minutes-scale E1 = "no valid test" (C2 fails at 3, 10 and 30 min on at least one seed). The P15-41 30-min null and the 3-min win are both invalid. F3 rests on the full-data result only. P15-08 stays `in_progress`.
- **P15-36 note:** its C2 pass at 30 min (seeds 0, 1) does not hold on seeds 2-4.
- **Suggested new gaps:**
  1. **C2 at the full-data budget** (arm E, F-R20 or the E1a recipe, ≥ 3 seeds). This puts a control under the one positive F3 result. Medium priority; GPU, cost to estimate (a full-data run is long).
  2. **A stronger C2 readout:** several deranged draws per seed and a paired sentence bootstrap of the deranged − normal gap, with a pre-stated rule. Low cost on CPU for the bootstrap; GPU for the extra draws. Medium priority.
  3. **100-min C2 with F-R20** (needs a new recipe choice, about 12 GPU h). **Low priority:** E1a already reports C2 failing at ≤ 100 min, and gaps 1-2 are more informative per GPU hour. Keep it as an open item; do not drop it.
- **Agent-run row:** P15-43, 1 launch, 2.22 GPU h, 5 deranged runs + 5 deranged aligners.
