---
title: P15-41 More seeds of the F-R20 recipe at minutes scale - results
type: experiment
task: P15-41
updated: 2026-11-22
---

# P15-41: more seeds of F-R20 at 3 / 10 / 30 min (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (`043486f`, 09:31:48, before any result). Code `8f70f1e` (09:34:55), before the launch. Aggregates: [results/summary.json](results/summary.json). Weights, libraries, texts, per-sentence outputs and logs stay local in `C:\Users\zhang\bci-data\derived\p15-41\`.

## Summary
- **H1 (primary) fails.** E does not win over T at 10 min or at 30 min on 5 seeds (paired 95 % t interval).
  - 10 min: mean d (T − E) = 0.038, CI95 [−0.004, 0.081]. E is better on 4 of 5 seeds, but the interval includes 0.
  - 30 min: mean d = −0.002, CI95 [−0.034, 0.031]. E and T are the same. E is better on 1 of 5 seeds.
- **The 3-min secondary wins:** mean d = 0.095, CI95 [0.066, 0.124]. E is better on 5 of 5 seeds.
- **C2 fails on all 3 new seeds** (arm E, 10 min, deranged labels): deranged test CER 0.883 / 0.844 / 0.787, needed 0.906 / 0.871 / 0.889. On seed 4 the deranged run (0.787) is as good as the normal run (0.789).
- So **H1 is flagged "control fails on seeds 2, 3, 4"** (`H1_valid` = false). At 10 min the F-R20 decoders mostly learn the label (text) prior, not the signal-to-text map.
- C1 has no applicable run: no new 30-min run has test CER ≤ 0.70.
- **GPU use: 7.82 h** (cap 8.0 h), in 1 launch. All 3 seed blocks ran.

## H1: E vs T on 5 seeds (test CER, final step)
d = CER_T − CER_E. A positive d means that E is better. Seeds 0 and 1 are from P15-36 (known before the plan). Seeds 2-4 are new.

| Budget | Arm | s0 | s1 | s2 | s3 | s4 | Mean |
|---|---|---|---|---|---|---|---|
| 3 min | T | 0.855 | 0.920 | 0.942 | 0.867 | 0.892 | 0.895 |
| | E | 0.774 | 0.843 | 0.809 | 0.785 | 0.790 | 0.800 |
| | d | 0.081 | 0.077 | 0.132 | 0.082 | 0.102 | 0.095 |
| 10 min | T | 0.804 | 0.762 | 0.846 | 0.838 | 0.859 | 0.822 |
| | E | 0.778 | 0.775 | 0.806 | 0.771 | 0.789 | 0.784 |
| | d | 0.026 | −0.013 | 0.039 | 0.068 | 0.071 | 0.038 |
| 30 min | T | 0.739 | 0.747 | 0.744 | 0.807 | 0.762 | 0.760 |
| | E | 0.747 | 0.703 | 0.765 | 0.822 | 0.771 | 0.762 |
| | d | −0.008 | 0.044 | −0.021 | −0.015 | −0.010 | −0.002 |

### Decision rule (pre-registered): mean d > 0 and lower end of the paired 95 % t interval > 0 (n = 5, t = 2.776)
| Budget | Mean d | SD | CI95 | E wins | Role |
|---|---|---|---|---|---|
| 3 min | 0.095 | 0.023 | [0.066, 0.124] | **yes** | secondary |
| 10 min | 0.038 | 0.034 | [−0.004, 0.081] | no | primary |
| 30 min | −0.002 | 0.026 | [−0.034, 0.031] | no | primary |

| Id | Result | Status |
|---|---|---|
| **H1** (primary) | 0 wins of {10, 30} min | **fail**, flagged: C2 fails on seeds 2, 3, 4 |
| H1-3 (secondary) | win at 3 min | win, but no control at 3 min (see "What this means") |
| **C2** (each new seed) | 0 of 3 pass | **fail** |
| C1 | 0 applicable runs | pass (vacuous) |

### Descriptive (no decision)
| Budget | Sign test (d > 0) | Paired t, seeds 2-4 only | E1a "beats" rule, 5 seeds (Δ / spread / bootstrap CI95) |
|---|---|---|---|
| 3 min | 5 of 5, p = 0.031 | 0.106 [0.042, 0.169] | 0.095 / 0.087 / [0.085, 0.104]: win |
| 10 min | 4 of 5, p = 0.188 | 0.059 [0.017, 0.102] | 0.038 / 0.097 / [0.029, 0.048]: no (Δ < spread) |
| 30 min | 1 of 5, p = 0.969 | −0.015 [−0.029, −0.002] | −0.002 / 0.120 / [−0.010, 0.007]: no |

On the new seeds alone, E is better at 10 min (interval above 0) and T is slightly better at 30 min (interval below 0). On all 5 seeds neither difference holds. The two old seeds and the three new seeds do not agree, so the difference is small compared with the seed-to-seed variation.

## C2: arm E, 10 min, deranged labels (rule: deranged test CER ≥ max(0.75, normal + 0.10))
| Seed | Normal test | Deranged test | Needed | Pass | Normal val | Deranged val |
|---|---|---|---|---|---|---|
| 2 | 0.806 | 0.883 | 0.906 | **no** (short by 0.023) | 0.762 | 0.854 |
| 3 | 0.771 | 0.844 | 0.871 | **no** (short by 0.027) | 0.786 | 0.796 |
| 4 | 0.789 | 0.787 | 0.889 | **no** (deranged = normal) | 0.749 | 0.842 |

Each deranged run used its own deranged recipe-A aligner (val CER 0.926 / 0.866 / 0.825). The median snippet lengths of the deranged libraries were 69 / 76 / 69 frames. The normal libraries had 96 / 86 / 90.

## What this means for the E1 claim
- **At 10 min, the F-R20 decoders do not show that they read the signal.** A decoder trained on wrong labels reaches nearly the same test CER (and the same on seed 4). So a CER near 0.78-0.85 at 10 min is mostly what a label prior gives. A difference between E and T at this level is a difference in prior or regularisation, not in decoding.
- **This is a stronger statement than P15-36 made.** P15-36 checked C2 only at 30 min (seeds 0, 1: pass, by 0.030 and 0.067). This task checked C2 at 10 min for the first time, and it fails there. The plan chose 10 min for cost reasons. That choice put the control on a budget where it was never validated.
- **The 3-min "win" cannot be read as an E1 result.** 3 min has less data than 10 min, and there is no 3-min control. If the 10-min decoders mostly output the prior, the 3-min ones almost surely do too. E is better at 3 min on every seed (0.800 vs 0.895). The most likely cause is that the EMG trunk gives a better prior or a more stable start than the text trunk, not that it reads more of the signal.
- **At 30 min, where C2 passed on seeds 0 and 1, E and T are equal** (0.762 vs 0.760 on 5 seeds). No new seed has a 30-min C2.
- **Combined reading:** at minutes scale (3-30 min) there is no valid evidence that EMG pretraining helps beyond text pretraining. The one budget with a passing control (30 min) shows no difference. The budgets with a difference (3 min, and 10 min on new seeds) have a failing or missing control. H1 at minutes scale is **not supported**. Only the full-data result of P15-36 / E1a stays (E 0.395 at "all", V1).

> **Our take:** the honest F3 answer at minutes scale is now "no evidence". The P15-36 3-min win looked like the one positive H1 sign. With a control at 10 min failing, that win is most likely a prior effect. The next useful step is not more seeds. It is a recipe or a budget where C2 passes on every seed, so that a difference between arms can mean decoding. For example, check C2 at 30 min for seeds 2-4, or find the smallest budget where C2 passes.

## Run integrity
| Check | Evidence | OK |
|---|---|---|
| All runs finished | 18 normal runs + 3 deranged runs, each with its own recipe-A aligner (21 aligners); `run.log` ends `ALL DONE` at 17:24:15; `DONE` file; no `FAILED` | yes |
| Seed count rule | block s2 started at 0.00 h, s3 at 2.56 h, s4 at 5.24 h (all ≤ 5.4 h); blocks done at 2.56 / 5.24 / 7.82 h | yes |
| Skipped steps (non-finite loss) | 0 in every run | yes |
| GPU clock | 7.817 h ≤ 8.0 h; one launch, 09:35:12-17:24:15, no pause | yes |
| Recipe | F-R20 keys equal to P15-36 `config.json` (unit test); steps 1,200 / 2,000 / 4,000; aligners 600 / 1,000 / 2,000 | yes |
| No re-selection on test | the recipe was fixed by P15-36 `selection.json`; no choice in this task read a test number | yes |
| Synthetic texts | usable texts per library: 3 min 45,806-57,533; 10 min 68,494-95,316; 30 min 88,188-100,000 | yes |
| Aligner lags | 19-88 frames; none at the 99-frame clip | yes |
| Deviations | none from the plan. Cosmetic: the `control_flags` strings in `summary.json` read "C2 done on seed k". The code prints the run status ("done"), not "fail". `C2.<k>.pass` = false is the correct value | - |

## Limits
- All seeds share one T trunk and one E trunk. A seed changes only the stem init, the budget subset and the batch order.
- n = 5 gives wide t intervals (t = 2.776). A true 10-min difference of about 0.04 can stay inside the interval.
- C2 for the new seeds is at 10 min only. There is no 30-min C2 for seeds 2-4 and no C2 at 3 min.
- R and S were not run, so H2-H4 are not re-evaluated (they stay at the P15-36 `partial`; see gap 185 / P15-42).
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM.

## Licence
- Willett data: CC0. E and T weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only.
- Tatoeba text (CC BY 2.0 FR, Tatoeba contributors): training only; not committed.
- This commit holds aggregate numbers only.

## Records to apply
- **Gap 184 / P15-41:** `done` (negative). Plan `043486f` (09:31:48), code `8f70f1e` (09:34:55), results (this commit). The done-when ("3-5 seeds of F-R20 at 3 / 10 / 30 min re-evaluate H1-H4 with the E1a rule") is met for H1 on 5 seeds. H2-H4 were left out by the plan (R / S cost) and move to gap 185 (P15-42).
- **GPU:** 7.82 h of the 8.0 h cap, one launch 09:35:12-17:24:15.
- **Summary:** H1 fails at 10 and 30 min (5 seeds, paired t). The 3-min secondary wins 5 of 5. C2 at 10 min fails on all 3 new seeds, so H1 is flagged invalid and minutes-scale H1 is "not supported". P15-08 stays `in_progress`.
- **New gaps (suggested):**
  1. C2 at 30 min for seeds 2-4, plus a "smallest budget where C2 passes on every seed" check. This would establish the budget range where E1 arm comparisons mean decoding.
  2. Fix the cosmetic `control_flags` label in `p41.py` (prints the run status, not "fail"). Low priority.
- **Results-page lines:** "P15-41 (5 seeds of F-R20, arms E and T): H1 fails. E vs T at 10 min d = 0.038 [−0.004, 0.081], at 30 min −0.002 [−0.034, 0.031]. The 3-min win (0.095 [0.066, 0.124]) has no valid control. The label-deranged control at 10 min fails on all 3 new seeds (seed 4: deranged = normal). So at minutes scale there is no valid evidence that EMG pretraining beats text pretraining."
