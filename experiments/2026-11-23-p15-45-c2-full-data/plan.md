---
title: P15-45 C2 at the full-data budget of E1 - pre-registered plan
type: experiment-plan
task: P15-45
updated: 2026-11-23
---

# P15-45: C2 at the full-data budget of E1 (plan, written before any result of this task)

## Why
- Gap 197 ([P15-45](../../wiki/questions/roadmap-standard.md#p15-45-c2-at-the-full-data-budget-of-e1)). Done when: a pre-registered run reports C2 (arm E, deranged labels; rule: deranged test CER ≥ max(0.75, normal + 0.10)) at the full-data budget on at least 3 seeds, with normal and deranged runs on the same seeds and pass or fail per seed.
- P15-43 ([results](../2026-11-23-p15-43-c2-30min/results.md), `a98964c`): C2 passes on every seed at none of 3 / 10 / 30 min. So F3 rests on the full-data result only: E at "all" = 0.395 (mean of seeds 0 / 1: 0.360 / 0.431; P15-08 E1a runs, V1 pass). That result has C1 (frame shuffle) but **no label-deranged control at "all"** on any seed.
- This task asks one question: at the full-data budget, does the decoder that gives the V1 result learn the signal-to-text map (C2 passes), or mostly the label prior?

## Which recipe (and why not F-R20)
- The full-data E1 result (E 0.395) comes from the **E1a recipe** (P15-08: AdamW LR 5e-4, wd 0.01, dropout 0.1, base augmentation, 3,000 steps at "all"). The P15-36 val-only rule chose E1a at 100 min and "all" (P15-36 `selection.json`).
- F-R20 has **no full-budget recipe**. It was defined and run at 3 / 10 / 30 min only. A C2 for F-R20 at "all" would need a new recipe choice and would not test the result that F3 rests on.
- So this task uses the **E1a recipe at "all", unchanged** (read from the P15-08 `config.json`). This is the roadmap's "the E1a full-data recipe" option. F-R20 at "all" is not run (see "Limits").
- Arm: **E** only (C2 is defined on arm E). Arm T is not run: C2 does not use it, and the full-data E vs T gap (0.395 vs 0.805) is not the open question.

## Design in one table
| Item | Value |
|---|---|
| Data, splits | P15-08 E1a exactly: Willett cache (CC0) `derived/p15-08/willett` (read-only), salt `fidetype-p15-08-2026-11-19`, test = last block per session (80 sentences), val = 106 sentences, train = the whole pool (budget "all", 506.0 min) |
| Arm | **E** (EMG trunk, P11-01 checkpoint, step 30,000) |
| Recipe | **E1a at "all", unchanged**: P15-08 `run.py` `train_run`, 3,000 steps, warmup 100, cosine to 1e-6 |
| Seeds | **0, 1, 2, 3, 4** (done-when needs ≥ 3). A seed changes the stem init, the batch order and the derangement. At "all" the training set is the same for every seed |
| Deranged labels | `e1.derangement` of the "all" set with RNG `[seed, 77]` (P15-08 code, unchanged). No sentence keeps its own text |
| Normal runs | seeds 0, 1: **reused, read-only** from `derived/p15-08/runs/E-ball-s{0,1}` (the runs behind E 0.395). Seeds 2, 3, 4: **new**, same code and recipe |
| Deranged runs | seeds 0-4: **new** |
| Readout | greedy CTC, no LM, final step (3,000); pooled test CER (total edits / total reference characters) over the 80 test sentences |
| Code | `p45.py` imports P15-08 `run.py` / `e1.py` read-only and calls `train_run` unchanged. Output only to `C:\Users\zhang\bci-data\derived\p15-45\`. It refuses to write into any other experiment's derived folder |

## New runs (in this order)
| # | Run | Steps |
|---|---|---|
| 1 | `E-ball-s0-labelshuf` | 3,000 |
| 2 | `E-ball-s1-labelshuf` | 3,000 |
| 3-4 | `E-ball-s2`, `E-ball-s2-labelshuf` | 3,000 each |
| 5-6 | `E-ball-s3`, `E-ball-s3-labelshuf` | 3,000 each |
| 7-8 | `E-ball-s4`, `E-ball-s4-labelshuf` | 3,000 each |

**Stop rule.** No early stop on a fail: every seed runs, so the result has pass or fail per seed on all 5 seeds. The only stop is the GPU cap (below), checked before the start of each run.

## Pass rule (pre-stated; the E1a formula, unchanged)
For seed s: **C2 passes on s** if deranged test CER ≥ max(0.75, normal test CER + 0.10), both at the final step (rules `c2_min_cer` 0.75, `c2_min_gap` 0.10; same as `p35_lib.c2_need`). The rule is computed in `p45.py` from the stored test CERs. It does not use the P15-41 `control_flags` label (gap 195).

**"C2 passes at full data"** = C2 is done and passes on **every** seed that ran, and at least 3 seeds ran.

## Outcomes and what each means
| Outcome | Condition | Meaning for E1 / F3 |
|---|---|---|
| **A** | all 5 seeds done, C2 passes on all 5 | The full-data E1 result has a **valid label-deranged control** on 5 seeds. The decoders at "all" learn the signal-to-text map, not only the label prior. F3 can cite E 0.395 (V1) with C1 and C2. Gap 197 closes |
| **A3** | 3 or 4 seeds done (cap), C2 passes on every done seed | As A, on the seeds that ran. Gap 197 closes (done-when ≥ 3 seeds); the missing seeds are reported as "not run (cap)" |
| **B** | C2 fails on at least 1 done seed, passes on at least 1 | **No valid control on every seed** at full data. The full-data V1 result is flagged "C2 fails on seed(s) k". F3 then has no fully valid E1 result at any budget. Gap 197 closes (the question is answered); a follow-up gap (stronger C2 readout, P15-46) gets more weight |
| **C** | C2 fails on every done seed (≥ 3 done) | The full-data decoders mostly learn the label prior. E 0.395 is not valid evidence for F3. F3 has no valid E1 result. Gap 197 closes as a negative result |
| **N** | fewer than 3 seeds done and no fail | Not determined. Gap 197 stays open |

A fail is a valid result. We report the outcome as it comes out.

## Descriptive (no decision)
- per seed: the C2 margin (deranged − needed); final and best val CER of each new run; test CER at the best-val step;
- C1 (frame-shuffled test CER) of the new normal runs (P15-08 code computes it at "all");
- mean and range of the normal test CER over the 5 seeds (seeds 2-4 are new evidence for V1; V1 itself is not re-decided here).

## What is known before this plan (disclosure)
- Published: normal E at "all", seeds 0 / 1: test 0.360 / 0.431 (P15-08). So C2 needs deranged ≥ max(0.75, 0.460) = **0.75** on seed 0 and ≥ max(0.75, 0.531) = **0.75** on seed 1. For new seeds the floor 0.75 decides unless the normal CER is above 0.65.
- Published: the E1a deranged run at 30 min seed 0 has test CER 0.836 (P15-08), and F-R20 deranged runs at 3 / 10 / 30 min have 0.787-0.889 (P15-36 / P15-41 / P15-43). No deranged run at "all" exists, and no seed 2-4 run at "all" exists.
- **New**: 5 deranged runs and 3 normal runs at "all".
- No run of this task's code was made before this plan. After the plan commit the code is unit-tested on CPU (pure rules) and checked with a short smoke run (a few steps, into a scratch folder that is not the output folder; its numbers are not results).

## Compute budget and GPU cap
Measured (RX 7800 XT, ROCm torch, venv `C:\venvs\fidetype-rocm`): P15-08 `E-ball-s0` took about 17 min for 3,000 steps plus val and test (0.31-0.36 s/step).

| Part | Runs | Estimate |
|---|---|---|
| 8 runs x 3,000 steps | 24,000 steps | about 2.3 h |
| **Total** | | **about 2.3 h** |

- **GPU cap 4.0 h** of job wall time (sum over launches, `gpu_clock.json`; pauses not counted), checked before each run starts (a started run finishes, about 17 min). At the cap the job writes the summary of what exists and `DONE` with the note `cap`.
- One GPU job (no other GPU job runs at launch). 2 CPU threads; no data-loader processes.
- `latest.pt` at every val (every 100 steps) and every 4 min (P15-08 `train_run`); exact resume after a stop. A `pause` or `stop` file: save and exit. The process keeps the machine awake while it runs.

## Limits stated in advance
- One deranged run per seed. A margin near 0 is fragile (P15-46 covers repeated deranged runs).
- At "all" every seed has the same training set; seeds differ in init, batch order and derangement only.
- The seed 0 / 1 normal runs are reused, not retrained (they are the runs behind E 0.395). ROCm is not bit-identical across runs.
- F-R20 at "all" is not tested. The result is about the E1a full-data recipe, which is the recipe behind the F3 full-data result.
- C2 at "all" says the decoder uses the signal. It does not say that EMG pretraining helps (that is H1, which is not tested at "all").
- Same confounds as P15-08: no LM; greedy readout.

## Licence and rules
- Willett data: CC0. E weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only; every run folder has `licence.json`.
- Code: our own (Apache-2.0). All outputs go to `C:\Users\zhang\bci-data\derived\p15-45\`.
- The repo gets this plan, `config.json`, the code, the tests, `results/summary.json` (aggregates only) and `results.md`. No weights, signals, texts or per-sentence outputs.

## Rerun
| Step | Command (repo root) |
|---|---|
| Unit tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-23-p15-45-c2-full-data/test_p45.py` |
| Full run (detached, resumes) | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-p15-45-c2-full-data\launch.py` |
| Check | `Get-Content C:\Users\zhang\bci-data\derived\p15-45\run.log -Tail 5`; `Test-Path C:\Users\zhang\bci-data\derived\p15-45\DONE` |
| Stop (saves latest.pt) | `New-Item C:\Users\zhang\bci-data\derived\p15-45\stop` |
| Resume | delete the `stop` file, then run the launcher again |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-p15-45-c2-full-data\p45.py summary` |
