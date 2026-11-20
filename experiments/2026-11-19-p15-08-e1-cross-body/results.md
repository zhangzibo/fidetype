---
title: P15-08 E1a cross-body pretraining -> minutes of data on Willett handwriting - results
type: experiment
task: P15-08
updated: 2026-11-19
---

# P15-08 E1a: cross-body pretraining on Willett handwriting (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (`60620ab`, before any result). Code `75c92a6`. Aggregates: [results/summary.json](results/summary.json). Weights, per-sentence outputs and the Willett cache stay local in `C:\Users\zhang\bci-data\derived\p15-08\`.

## Verdicts (pre-registered rules)
| Id | Claim | Result | Verdict |
|---|---|---|---|
| **V1** (gate) | best arm at "all" has test CER ≤ 0.50 | E at all: **0.395** | **pass** (H1-H4 count) |
| **H1 (primary, F3)** | E (EMG trunk) beats T (text-only) at ≥ 2 of {3, 10, 30} min | 0 of 3 wins. At 10 and 30 min **T is better than E** (CI95 of CER_T − CER_E entirely below 0) | **fail** |
| H2 | E beats R (random) at ≥ 2 of {3, 10, 30} | 0 of 3 wins (R is best at 3 min) | **fail** |
| H3 | T beats R at ≥ 2 of {3, 10, 30} | 0 of 3 wins | **fail** |
| H4 | E beats S (shuffled-weight control) at ≥ 2 of {3, 10, 30} | 1 of 3 (30 min) | **partial** |
| C1 | time-shuffled test CER ≥ 0.85 for runs with CER ≤ 0.70 (budgets 30, all) | 3 runs apply: R-all-s0 0.877, E-all-s0 0.892, E-all-s1 0.948 | **pass** |
| C2 | E, 30 min, labels deranged: CER ≥ max(0.75, normal + 0.10) = 0.909 | 0.836 (normal run 0.810) | **fail** |
| Roadmap rule (secondary) | E beats T by more than the seed spread (clause (i) only) at ≥ 1 of {3, 10, 30, 100} | yes at 3 min (Δ 0.003 > spread 0.0026) and 100 min (Δ 0.010 > 0.003) | **pass as written, but not meaningful**: both gaps are ≤ 1 CER point, and both bootstrap intervals include 0 (3 min [−0.003, +0.010]; 100 min [−0.001, +0.022]) |

**Summary.** E1a is a **null result for F3 at minutes scale**. With 3 to 100 labelled minutes, no arm gives a usable Willett decoder (best CER 0.767), and the EMG-pretrained trunk does not beat the text-only trunk. C2 fails: at 30 min, a decoder trained on wrong labels is only 2.6 CER points worse than the normal one. So at ≤ 30 min the decoders read almost nothing from the signal; their CER of about 0.8 comes mostly from the label prior. Only with all 506 minutes does a decoder read the signal (C1 pass), and there the EMG trunk is the best and the most stable arm (descriptive, see below).

## Test CER per arm and budget (primary readout)
Test = last block of each of the 10 sessions: 80 sentences, 3,448 characters. Greedy CTC, no LM, final step. Seed 0 / seed 1 in brackets.

| Budget (labelled minutes, seed 0 / 1) | R random | T text-only | E EMG trunk | S shuffled E |
|---|---|---|---|---|
| 3 (3.71 / 3.27) | **0.865** (0.891 / 0.839) | 0.960 (0.958 / 0.961) | 0.957 (0.956 / 0.957) | 0.919 (0.999 / 0.838) |
| 10 (10.84 / 10.38) | 1.327 (0.816 / **1.839**) | **0.863** (0.823 / 0.903) | 0.884 (0.865 / 0.903) | 0.922 (0.928 / 0.915) |
| 30 (30.55 / 30.23) | 0.851 (0.897 / 0.804) | **0.786** (0.784 / 0.788) | 0.812 (0.810 / 0.815) | 1.003 (0.923 / 1.083) |
| 100 (100.70 / 100.43) | 0.837 (0.821 / 0.854) | 0.777 (0.779 / 0.776) | **0.767** (0.768 / 0.766) | 0.919 (0.961 / 0.877) |
| all (506.0) | 0.613 (**0.305** / 0.920) | 0.805 (0.806 / 0.803) | **0.395** (0.360 / 0.431) | 0.925 (0.905 / 0.944) |

CER above 1 means many insertions (R-b10-s1 emits long wrong strings).

Secondary readout: test CER at the best-val step (uses the val block labels, about 71 extra minutes):

| Budget | R | T | E | S |
|---|---|---|---|---|
| 3 | 0.959 | 0.947 | 0.911 | 0.916 |
| 10 | 1.319 | 0.854 | 0.858 | 0.912 |
| 30 | 0.806 | 0.783 | 0.809 | 0.873 |
| 100 | 0.815 | 0.775 | 0.756 | 0.874 |
| all | 0.608 | 0.779 | 0.394 | 0.860 |

Minutes to reach CER 0.60 (linear in log minutes): E about **208 min**; R, T and S never reach it on the mean curve.

## Pairwise tests at the H budgets
Δ = CER(B) − CER(A), means over the 2 seeds; spread = largest seed difference of A or B; CI95 = paired bootstrap over the 80 test sentences.

| Pair (A beats B?) | 3 min: Δ / spread / CI95 | 10 min | 30 min | Wins |
|---|---|---|---|---|
| H1 E vs T | +0.003 / 0.003 / [−0.003, +0.010] | −0.021 / 0.080 / [−0.031, −0.011] | −0.026 / 0.005 / [−0.039, −0.013] | 0 |
| H2 E vs R | −0.092 / 0.053 / [−0.102, −0.081] | +0.443 / 1.024 / [+0.200, +0.721] | +0.039 / 0.093 / [+0.016, +0.069] | 0 |
| H3 T vs R | −0.095 / 0.053 / [−0.104, −0.085] | +0.464 / 1.024 / [+0.218, +0.747] | +0.065 / 0.093 / [+0.044, +0.094] | 0 |
| H4 E vs S | −0.038 / 0.161 / [−0.045, −0.031] | +0.037 / 0.037 / [+0.005, +0.077] | +0.191 / 0.160 / [+0.093, +0.324] | 1 |

At 10 and 30 min the bootstrap often favours E and T over R, but the seed spread of R (one diverged seed) is larger than the gap, so the rule does not count a win.

## Controls
| Run | Test CER | Time-shuffled CER |
|---|---|---|
| R 30 min s0 / s1 | 0.897 / 0.804 | 0.899 / 0.788 |
| T 30 min s0 / s1 | 0.784 / 0.788 | 0.775 / 0.815 |
| E 30 min s0 / s1 | 0.810 / 0.815 | 0.852 / 0.858 |
| R all s0 / s1 | 0.305 / 0.920 | 0.877 / 0.942 |
| T all s0 / s1 | 0.806 / 0.803 | 0.869 / 0.867 |
| E all s0 / s1 | 0.360 / 0.431 | 0.892 / 0.948 |
| E 30 min s0, labels deranged (C2) | 0.836 | - |

At 30 min the shuffled CER is about equal to the normal CER for every arm (T is even lower on seed 0). This agrees with C2: at this budget the decoders output mostly prior text, not text from the signal. C1 applies only to the three runs with CER ≤ 0.70, and all three pass.

## Descriptive results at 100 min and all (not pre-registered)
| Pair | 100 min: Δ / spread / CI95 | all: Δ / spread / CI95 |
|---|---|---|
| E vs T | +0.010 / 0.003 / [−0.001, +0.022] | **+0.409** / 0.071 / [+0.388, +0.432] |
| E vs R | +0.070 / 0.033 / [+0.034, +0.114] | +0.217 / **0.615** / [+0.198, +0.236] |
| T vs R | +0.060 / 0.033 / [+0.026, +0.102] | −0.192 / 0.615 / [−0.204, −0.180] |
| E vs S | +0.152 / 0.084 / [+0.139, +0.165] | +0.529 / 0.071 / [+0.504, +0.554] |

- With all 506 min, the EMG trunk trains well on both seeds (0.360, 0.431). Random init works on seed 0 (0.305, the best single run) but fails on seed 1 (0.920). The text-only trunk does not learn the signal at all (0.80 on both seeds, about its 30-min value). The shuffled-weight trunk fails too.
- So the EMG pretraining gives a **better and more stable start for full-data training**, and the text-only pretraining **hurts** at full data. This is a descriptive finding on 2 seeds. It is not the pre-registered question.

## Run integrity
| Check | Evidence | OK |
|---|---|---|
| All parts finished | 41 adaptation runs + text pretraining (30,000 steps) + summary; `DONE` 2026-11-19 20:00:01; `run.log` ends `ALL DONE` | yes |
| Interrupt | The machine slept; MIOpen raised "Invalid elapsed time" (about 14:06) and the process ended during run S-b30-s0 after the step-1000 log line. Relaunch 14:41:03 (`launcher.log`) | - |
| Resume point | `14:41:07 [S-b30-s0] resume at step 1000 (best val 0.9360 @ 1000)`: `latest.pt` was saved at the step-1000 val check, so the optimiser state matches step 1000 | yes |
| Lost or duplicated steps | none: steps 1,001-1,200 ran once after the resume (log lines 1100, 1200); `metrics.jsonl` of S-b30-s0 has 12 val entries (100 ... 1,200), one per step; every other run has exactly its expected entry count (5, 8, 12, 20, 30). Updates done after step 1000 before the crash (at most a few) were discarded with the process and redone from the same batches (batch k depends only on seed, budget and k) | yes |
| Finished runs before the crash | skipped on relaunch (their `DONE.json`); no run trained twice | yes |
| Skipped steps (non-finite loss) | 0 in all 41 runs and in text pretraining; total 61,200 adaptation steps = plan | yes |
| Data leakage | test block never used for training, normalisation or selection; val used only for the secondary readout | yes |

GPU non-determinism means a resumed run is not bit-identical to an uninterrupted one; the CPU test `test_cpu_smoke_full_pipeline_and_exact_resume` shows the logic is exact. The affected run is a control (S) at 30 min.

Wall time 10:28 to 20:00 (9.5 h) including the 35-min sleep gap; plan estimate 9-10 h.

## Limits
- One fine-tune recipe for all arms (LR 5e-4, fixed steps, no freezing). Random init is unstable with it (R-b10-s1 1.839, R-all-s1 0.920). A recipe tuned for low data (frozen trunk, smaller LR, longer schedule, Willett-style synthetic sentences) could change the low-budget picture. This was stated in advance as a limit and is not fixed after the results.
- The target decoder is weak even with all data: best 0.305 greedy CER. The published real-time RNN of Willett et al. 2021 is much better (single-digit raw error; the wiki has no source page with the exact number yet). Its recipe differs: non-CTC time-warped labels and augmentation with synthetic sentences. With a weak target, small transfer effects are hard to see.
- Cross-person and cross-modality cannot be separated (stated in the plan).
- No language model (P15-25, gap 91). The KT-sEMG clean-track arm and the T15 arm are not run.
- 2 seeds. The seed spread rule is strict when one seed diverges.

> **Our take:** F3's "new sensor with minutes of data" is not supported by this first test. With this recipe, the trunk init is not what limits the minutes-scale result: no arm learns to read the implant signal from ≤ 100 labelled minutes with this recipe (C2). The useful sign is at full data: the EMG-pretrained trunk trains reliably where random init fails on one seed and the text-only trunk fails on both. That points to "body-signal pretraining as a stable initialiser" rather than "minutes of data". The next step should first make the low-data recipe work on the target (with a frozen trunk or a smaller LR, and a stronger target decoder) before the KT-sEMG arm runs; otherwise the KT-sEMG arm will hit the same floor.

## What this means for other items
- **P15-08** stays `in_progress`: the roadmap done-when needs the clean-track KT-sEMG arm (P11-06, gap 86). E1a is part 1.
- **P14-33** (gap 101, Willett decoder in the pretrained registry) **can start**: R-all-s0 is the best run on val (0.258) and on test (0.305), and its weights are clean-track (Willett CC0 only). The caveats: greedy CER 0.305 is weak, and the same recipe fails on seed 1, so the card must say so.
- **P14-12** (gap 26) and **P6-06** (gap 28) depended on "a Willett decoder of our own": one now exists (local weights), with the same caveats.
- **P15-25** (gap 91, same-LM readout) stays open; an LM cannot rescue decoders that do not read the signal at ≤ 100 min, but it can change the full-data comparison.

## Licence
- Willett data: CC0. R-arm weights are clean-track.
- T, E and S weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only, each run folder has `licence.json`.
- This commit holds aggregate CERs only: no weights, signals, per-sentence outputs or text.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q experiments/2026-11-19-p15-08-e1-cross-body/test_e1.py` |
| Full run (detached, about 10 h GPU) | `.venv\Scripts\python.exe experiments\2026-11-19-p15-08-e1-cross-body\launch.py` |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-19-p15-08-e1-cross-body\run.py summary` |
