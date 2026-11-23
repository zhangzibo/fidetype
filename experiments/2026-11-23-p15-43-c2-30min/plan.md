---
title: P15-43 C2 budget range of the F-R20 recipe - pre-registered plan
type: experiment-plan
task: P15-43
updated: 2026-11-22
---

# P15-43: C2 budget range of F-R20 (plan, written before any result of this task)

## Why
- Gap 194 ([P15-43](../../wiki/questions/roadmap-standard.md#p15-43-c2-budget-range-of-the-f-r20-recipe)). Done when: a pre-registered run reports C2 at 30 min for seeds 2-4 and the smallest budget in {3, 10, 30, 100} min where C2 passes on all 5 seeds (or that none does).
- C2 is the label-deranged control. Arm E is retrained with deranged labels. The deranged run must be at least 0.10 CER worse on test than the normal run. If it is not, the decoder learns the label prior, not the signal-to-text map.
- P15-41 ([results](../2026-11-22-p15-41-more-seeds/results.md), `02aa679`): C2 at 10 min fails on seeds 2, 3, 4. P15-36 ([results](../2026-11-22-p15-36-budget-matched/results.md), `01ee3b9`): C2 at 30 min passes on seeds 0, 1. No seed has a 3-min C2. Seeds 2-4 have no 30-min C2.

## Design in one table
| Item | Value |
|---|---|
| Data, splits | P15-08 E1a exactly (through the P15-41 / P15-36 code): Willett cache (CC0), salt `fidetype-p15-08-2026-11-19`, test = last block per session (80 sentences), val = 106 sentences |
| Arm | **E** only (EMG trunk, P11-01) |
| Recipe | **F-R20, unchanged** (P15-36 / P15-41 `config.json`): recipe A + "replace" batch rule, p = 0.2, forced cut with duration prior, steps 1,200 (3 min) / 4,000 (30 min), batch RNG code 3524 |
| Deranged labels | `e1.derangement` of the budget subset with RNG `[seed, 77]` (same code as P15-36 / P15-41) |
| Aligner of a deranged run | its own deranged recipe-A run of the same arm, budget, seed (P15-41 rule), trained here: 600 steps (3 min), 2,000 steps (30 min), val only |
| Normal runs | **reused, not retrained**: the normal E runs of P15-41 (seeds 2-4), P15-36 (seed 1 at 30 min; seeds 0, 1 at 3 min) and P15-35b (seed 0 at 30 min). Their test results are read read-only. They come from the same code and recipe |
| Old deranged runs | 30 min seeds 0, 1: P15-35b `E-b30-s0-labelshuf` and P15-36 `E-b30-s1-labelshuf` (read-only). 10 min seeds 2-4: P15-41 (read-only) |
| Readout | greedy CTC, no LM, final step; pooled test CER (total edits / total reference characters); test readout right after each run |
| Code | `p43.py` imports P15-41 `p41.py` (and through it the P15-36 / P15-35b / P15-33 / P15-08 code) read-only. No other experiment folder is edited. Output only to `C:\Users\zhang\bci-data\derived\p15-43\` |

## New runs (in this order)
| # | Stage | Run | Steps (aligner + F-R20) |
|---|---|---|---|
| 1-3 | S30 (primary) | `E-b30-s2-labelshuf`, `E-b30-s3-labelshuf`, `E-b30-s4-labelshuf` | 2,000 + 4,000 each |
| 4-8 | S3 (secondary, sequential) | `E-b3-s0-labelshuf`, then s1, s2, s3, s4 | 600 + 1,200 each |

- **S30 always runs on all 3 seeds** (the done-when needs C2 at 30 min for seeds 2-4).
- **S3 stops at the first seed that fails C2** (fixed in advance). One failing seed already means that 3 min does not pass on every seed, so the remaining 3-min runs cannot change the answer. Seeds after the first fail are reported as "not run (not needed)".
- S3 runs even if S30 fails. C2 is not assumed to be monotone in the budget.

## Pass rule (pre-stated; the E1a formula, unchanged)
For budget b and seed s: C2 passes if deranged test CER ≥ max(0.75, normal test CER + 0.10), with both runs at the final step (`p35_lib.c2_need`, rules `c2_min_cer` 0.75, `c2_min_gap` 0.10).

**"C2 passes at budget b"** = C2 passes on **every** seed 0-4 at b. A seed with a missing run (cap, failure) counts as "not passed", and the budget is then "not determined" if no seed fails.

| Budget | Seeds 0, 1 | Seeds 2, 3, 4 | Budget status before this task |
|---|---|---|---|
| 3 min | new (S3) | new (S3) | unknown |
| 10 min | not run | **fail** (P15-41) | **fails** (known) |
| 30 min | pass (P15-35b / P15-36) | new (S30) | open |
| 100 min | not run here | not run here | see "100 min" |

**Smallest passing budget** = the smallest b in {3, 10, 30} where "C2 passes at b". 10 min is already a fail.

## What each outcome means for the E1 claim
Rule of gap 194: E1 arm comparisons (E vs T) use only budgets where C2 passes on every seed.

| Outcome | Smallest passing budget | Meaning for E1 (P15-41 H1 numbers, 5 seeds) |
|---|---|---|
| A: S30 passes on seeds 2-4; S3 fails | **30 min** | The 30-min E vs T comparison becomes a **valid null**: d = −0.002 [−0.034, 0.031]. So at the one budget where the decoders read the signal, EMG pretraining does not help beyond text pretraining. The 3- and 10-min differences stay invalid (prior effects). |
| B: S30 passes on seeds 2-4; S3 passes on all 5 | **3 min** | The 3-min E vs T win (0.095 [0.066, 0.124], 5 / 5) becomes a valid comparison, and 30 min stays a valid null. 10 min stays invalid. A pass at 3 min and a fail at 10 min is not monotone. We report it as found, flag it as a surprise and do not claim an E1 win before a replication (new gap). |
| C: S30 fails on any of seeds 2-4; S3 fails | **none of {3, 10, 30}** | No minutes-scale budget has a valid control on every seed. All minutes-scale H1 numbers of P15-36 / P15-41 are invalid. E1 at minutes scale is "no valid test", and F3 rests on the full-data result only (E1a / P15-36 "all"). 100 min stays open (new gap). |
| D: S30 fails on any seed; S3 passes on all 5 | **3 min** (not monotone) | As B for 3 min, and 30 min is invalid. Report as a surprise; no E1 claim before a replication. |
| Cap or failure before all needed runs exist | not determined | Report what exists; the gap stays open. |

We report the outcome as it comes out. A fail is a valid result.

## 100 min
F-R20 has **no 100-min recipe** (P15-36 fixed steps for 3 / 10 / 30 min only), and no seed has a normal 100-min F-R20 run. A 100-min C2 on 5 seeds needs a new recipe choice plus 10 runs and 10 aligners (estimate about 12 GPU h). That is outside this task and the cap. So:
- in outcome A or B, 100 min is not needed (a smaller budget passes);
- in outcome C, the answer is "none of {3, 10, 30} passes; 100 min not tested". We propose a follow-up gap in the results. We do not claim that 100 min fails.

## Descriptive (no decision)
- val CER (final) of every new deranged run and of its deranged aligner; library statistics (median snippet length, usable texts) of the deranged and normal libraries;
- the C2 margin (deranged − needed) per seed and budget;
- the full 5-seed C2 table at 3, 10 and 30 min (10 min seeds 0, 1 "not run").

## What is known before this plan (disclosure)
- Published and reused: normal E test CER at 30 min, seeds 0-4: 0.747 / 0.703 / 0.765 / 0.822 / 0.771; at 3 min, seeds 0-4: 0.774 / 0.843 / 0.809 / 0.785 / 0.790. So C2 needs deranged ≥ 0.865 / 0.922 / 0.871 at 30 min (seeds 2-4) and ≥ 0.874 / 0.943 / 0.909 / 0.885 / 0.890 at 3 min (seeds 0-4).
- Published: deranged at 30 min seeds 0, 1: 0.877 / 0.870 (pass). Deranged at 10 min seeds 2-4: 0.883 / 0.844 / 0.787 (fail).
- **New**: 3 deranged 30-min runs and up to 5 deranged 3-min runs, each with its own deranged aligner.
- No run of this task's code was made before this plan. The code is unit-tested on CPU (synthetic data only) after the plan commit.

## Compute budget and GPU cap
Measured (RX 7800 XT, ROCm torch, venv `C:\venvs\fidetype-rocm`): P15-36 `E-b30-s1-labelshuf` aligner + run + test took 39 min; P15-41 `E-b3-s2` aligner + run + test took 13 min.

| Stage | Runs | Estimate |
|---|---|---|
| S30 | 3 x (2,000 + 4,000 steps) | about 2.0 h |
| S3 | up to 5 x (600 + 1,200 steps) | up to about 1.1 h |
| **Total** | up to 8 runs | **about 3.1 h** |

- **GPU cap 4.5 h** of job wall time (sum over launches, `gpu_clock.json`; pauses not counted). At the cap the job saves `latest.pt`, writes the summary of what exists and writes `DONE` with the note `cap`.
- One GPU job (no other GPU job runs at launch). 2 CPU threads; no data-loader processes.
- `latest.pt` at every val (every 100 steps) and every 4 min; exact resume after a stop. A `pause` or `stop` file: save and exit. The process keeps the machine awake while it runs.

## Limits stated in advance
- One deranged run per seed and budget. The C2 result of a seed has no repeat; a margin near 0 is fragile.
- Seeds share one EMG trunk. A seed changes the stem init, the budget subset, the derangement and the batch order.
- The normal runs are reused, not retrained. A retrain on the same code gives near-identical numbers, but not bit-identical ones on ROCm.
- The 30-min seed-0 pair comes from P15-35b (same F-R20 recipe; P15-36 reused it).
- Same confounds as P15-08: no LM; greedy readout.

## Licence and rules
- Willett data: CC0. E weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only; every run folder has `licence.json`.
- Tatoeba text (CC BY 2.0 FR, Tatoeba contributors): training only, read in place (SHA-256 checked); never committed.
- Code: our own (Apache-2.0). All outputs go to `C:\Users\zhang\bci-data\derived\p15-43\`. The code refuses to write into the P15-08, P15-33, P15-35, P15-35b, P15-36 or P15-41 folders.
- The repo gets this plan, `config.json`, the code, the tests, `results/summary.json` (aggregates only) and `results.md`. No weights, signals, texts or per-sentence outputs.

## Rerun
| Step | Command (repo root) |
|---|---|
| Unit tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-23-p15-43-c2-30min/test_p43.py` |
| Full run (detached, resumes) | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-p15-43-c2-30min\launch.py` |
| Check | `Get-Content C:\Users\zhang\bci-data\derived\p15-43\run.log -Tail 5`; `Test-Path C:\Users\zhang\bci-data\derived\p15-43\DONE` |
| Stop (saves latest.pt) | `New-Item C:\Users\zhang\bci-data\derived\p15-43\stop` |
| Resume | delete the `stop` file, then run the launcher again |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-p15-43-c2-30min\p43.py summary` |
