---
title: P15-45 C2 at the full-data budget of E1 - results
type: experiment
task: P15-45
updated: 2026-11-23
---

# P15-45: C2 at the full-data budget of E1 (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (`20f9f5b`, before any result). Code `d4f5990`, before the launch. Aggregates: [results/summary.json](results/summary.json). Weights, logs and per-sentence outputs stay local in `C:\Users\zhang\bci-data\derived\p15-45\`.

## Summary
- **Outcome A: C2 passes on all 5 seeds at the full-data budget** (E1a recipe, budget "all", 3,000 steps, arm E).
- The smallest margin is +0.116 (seed 1). The deranged runs are 0.435-0.619 CER worse than the normal runs.
- So the full-data E1 result (E 0.395, V1) now has a valid label-deranged control on 5 seeds, next to C1. At "all", the decoder learns the signal-to-text map, not only the label prior.
- Three new normal seeds (2-4) give 0.329 / 0.420 / 0.366. The 5-seed mean of E at "all" is **0.381** (range 0.329-0.431). Every seed is ≤ 0.50 (descriptive; V1 is not re-decided here).
- **GPU use: 2.52 h** (cap 4.0 h), one launch, 2026-11-23 18:10:12 to 20:41:10.

## C2 per seed (rule: deranged test CER ≥ max(0.75, normal + 0.10), final step)
| Seed | Normal test CER | Normal source | Deranged test CER | Needed | Margin | Pass |
|---|---|---|---|---|---|---|
| 0 | 0.360 | P15-08 (reused) | 0.979 | 0.750 | +0.229 | **yes** |
| 1 | 0.431 | P15-08 (reused) | 0.866 | 0.750 | +0.116 | **yes** |
| 2 | 0.329 | new | 0.953 | 0.750 | +0.203 | **yes** |
| 3 | 0.420 | new | 0.896 | 0.750 | +0.146 | **yes** |
| 4 | 0.366 | new | 0.876 | 0.750 | +0.126 | **yes** |

The pass rule was computed in `p45.py` from the stored test CERs. It does not use the P15-41 `control_flags` label (gap 195).

## Descriptive (no decision)
| Run | Final val CER | Best val step | Test CER at best-val step | C1 (frame-shuffled test CER) |
|---|---|---|---|---|
| E-ball-s0-labelshuf | 0.976 | 1,900 | 0.965 | - |
| E-ball-s1-labelshuf | 0.873 | 2,300 | 0.847 | - |
| E-ball-s2 | 0.300 | 3,000 | 0.329 | 0.940 |
| E-ball-s2-labelshuf | 0.964 | 2,600 | 0.948 | - |
| E-ball-s3 | 0.362 | 2,700 | 0.417 | 0.924 |
| E-ball-s3-labelshuf | 0.915 | 2,800 | 0.892 | - |
| E-ball-s4 | 0.331 | 2,800 | 0.366 | 0.928 |
| E-ball-s4-labelshuf | 0.876 | 2,400 | 0.861 | - |

- C1 also passes on the 3 new normal runs (≥ 0.85).
- Compare the minutes-scale budgets (F-R20, P15-43): there, the deranged runs were only 0.07-0.15 CER worse than the normal runs, and C2 failed on several seeds. At "all" the gap is 0.435 or more on every seed.

## Run integrity
| Check | Evidence | OK |
|---|---|---|
| All runs finished | 8 new runs, each 3,000 steps; `run.log` ends with `ALL DONE` at 20:41:10; `DONE` file | yes |
| Skipped steps (non-finite loss) | 0 in every run | yes |
| Pauses or resumes | none (one launch) | yes |
| GPU clock | `gpu_clock.json` 9,058 s = 2.52 h (≤ 4.0 h) | yes |
| Smoke run | 20 steps into a scratch folder after the plan commit; not a result | yes |
| Deviations | none | yes |

## Limits
- One deranged run per seed. All margins are ≥ +0.116, so one run per seed is enough here (P15-46 stays useful for the minutes scale).
- At "all", every seed has the same training set. Seeds differ in init, batch order and derangement only.
- Seeds 0 / 1 normal runs are reused from P15-08 (the runs behind E 0.395).
- C2 checks that the decoder uses the signal. It does not test whether EMG pretraining helps beyond text pretraining at "all" (H1 is defined at minutes scale only).
- The result holds for the E1a full-data recipe. F-R20 at "all" was not tested.
- Same confounds as P15-08: no LM; greedy readout.

> **Our take:** the full-data E1 result is now on firm ground. E reaches 0.381 CER on average over 5 seeds, and with deranged labels it falls to 0.87-0.98. So the full-data decoder reads the Willett signal. F3 can cite the full-data result with C1 and C2 on 5 seeds. The minutes-scale question stays open: there, no budget has a valid control.

## Licence
- Willett data: CC0. E weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only.
- This commit holds aggregate numbers only.
