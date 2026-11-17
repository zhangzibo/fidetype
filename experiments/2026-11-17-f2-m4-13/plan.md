---
title: F2 reruns on the M4-13 decoder (P15-05, P15-06) and the P15-06 variant V-single (T15 + T12) - pre-registration
type: experiment
task: P15-05, P15-06
updated: 2026-11-16
---

# F2 reruns: LLM rescoring with grounding (P15-05) and the fluent-wrong bound (P15-06) on M4-13 (pre-registration)

Written and committed **before** the M4-13 decoder has finished and before any M4-13 output exists. Code: [run.py](run.py) imports the P15-05 and P15-06 scripts unchanged and only points them at new inputs and new output folders. Queue and GPU plan: [trust-reruns plan](../2026-11-17-trust-reruns-m4-13/plan.md).

## Why
- P15-05 on T15 (M4-12 fixed0): B1 lowered WER but failed S4 ([results](../2026-11-16-f2-e3-llm-grounding/results.md)). On T12 it was "safe but no gain".
- P15-06 on T15: the bound held, but B1 never committed; on T12 it was not certifiable in any arm: 180 LTT test items, while alpha_h 0.01 at delta_h 0.1 needs >= 230 even with zero losses ([results T12](../2026-11-16-p15-06-halluc-bound/results.md#t12-2026-11-16)).
- A stronger decoder (M4-13) gives more right top-1 sentences, so more commits to bound. The variant V-single fixes the sample-size problem without new data.

## Part A: P15-05 rerun on M4-13 T15 (method unchanged)
- Calibration: M4-13 val_select (722, CPU decode with best.pt); held out: M4-13 val_eval (701). Same LLM (Qwen2.5-1.5B Q4_K_M, SHA-256 in the P15-05 config), same 8 arms, grids, seed 0, alpha 0.05, delta 0.1, 300 null trials, 2,000 bootstrap draws.
- The LLM cache of P15-05 is copied into our folder (a text -> score / rewrite memo of the same model and seed; it changes speed, not results). The P15-05 folder is not written.
- Pass rules: **S1-S4 of the [P15-05 plan](../2026-11-16-f2-e3-llm-grounding/plan.md)** for B1 against A0, unchanged: S1 WER(B1) < WER(A0) with the paired-bootstrap 95 % interval below 0; S2 a guard and held-out wrong-commit rate <= 0.05; S3 held-out uniform and shuffled commits <= 1 / 300 each, unsupported swapped commits <= 2 / 701; S4 hallucination rate(B1) <= (A0) and fluent-wrong commits(B1) <= (A0). Secondary and grounding effects: as in that plan. We also report each value next to the M4-12 run.

## Part B: P15-06 rerun on M4-13 T15 (method unchanged)
- From the Part A outputs (guards, base n-best cache, LLM cache, fluent threshold, tau). Same grid, alpha_h 0.01, delta_h 0.1, rule `fewest_halluc`; secondary arms `B1_rescore_G@most_right`, `C1_rewrite_G@most_right`.
- Pass rules: **H1-H4 of the [P15-06 plan](../2026-11-16-p15-06-halluc-bound/plan.md)** for B1, unchanged (H2 compares with A0 of the Part A run). Utility rule unchanged (right commits of B1 vs Part A B1).
- With 722 calibration items the primary rule has 271 LTT test items (25 % fit, then half / half), so the primary bound is certifiable in principle (>= 230).

## Part C: new pre-registered variant V-single (T15 M4-13 and T12 v2)
**Problem.** The primary rule splits the non-fit items into an ordering half and a test half. On T12 (480 calibration items) the test half has 180 items < 230, so no configuration can be certified.

**Variant V-single (fixed now).** Same fit part (25 %), same base guard, same grid, same alpha (0.05), alpha_h (0.01), delta_h (0.1), same item statistics. Difference: **no ordering split**. The configurations are tested in a fixed, data-independent order, the library's strictness order `halluc_bound._strictness` (higher `commit_p` first, then smaller `tau_commit`, then smaller `tau_word`), with a fixed-sequence test on **all** non-fit items (T12: 360; T15: 542). The chain stops at the first configuration whose p-value `max(p_wc, p_h)` is above delta_h. Selection among the certified ones: `fewest_halluc`, then `commit_p >=` the P14-03 value, as in the primary rule. A fixed-sequence test with an order fixed before the data keeps the family-wise error <= delta_h, so the guarantee statement of P15-06 is unchanged. Cost: the order is not tuned to the data, so the chain may stop earlier.

Implementation: experiment code only ([run.py](run.py) `variant_guard`); `dropin.py` and `halluc_bound.py` are not changed. It calls `halluc_bound.joint_ltt([], all_non_fit_items, grid, ...)`; an empty ordering set gives every configuration the same p-value, so the sort falls back to `_strictness`. The held-out decisions, null controls and swapped-signal control are those of the P15-06 `run_arm` (same seeds).

**Arms.** `<arm>@single` for the 8 primary arms, on (1) M4-13 T15 (after Part B, same caches) and (2) T12 v2 (P15-05 / P15-06 T12 caches, read only; our copies of the LLM cache and the extra n-best cache, so the 3.5 GB T12 decoder should not load).

**Pass rules (fixed now).**
| id | rule |
|---|---|
| **V1** feasible | B1@single gives a certified configuration on T12 (the primary rule could not) |
| **V2** bound | B1@single held out: fluent-wrong rate <= 0.01 and wrong-commit rate <= 0.05 (on T12 and on T15) |
| **V3** controls | as H3: uniform and shuffled <= 1 / 300 each, unsupported swapped <= 2 (out of 400 on T12, 701 on T15), built-in controls pass |
| **V4** reproducibility | the primary guard computed inside each `@single` arm has the same `config_id` and selection as the committed P15-06 T12 result (T12) / Part B (T15) |
| V5 (descriptive) | right commits and commits of `@single` vs the primary rule, per arm and set |

The original rule stays reported: on T12 from the committed P15-06 T12 result (also recomputed inside each `@single` arm, V4); on T15 from Part B. If V1 fails, the result is "not certifiable even with one test set" (report the smallest p-value and the needed losses).

## Outputs
Per-trial files and caches only in `C:/Users/zhang/bci-data/derived/f2-reruns-m4-13/{p15-05,p15-06,p15-06-t12-single}/`. Repo: `results/results-t15.json` (Part A, the P15-05 file name), `results/results-p15-06.json` (Parts B + C T15), `results/results-p15-06-t12.json` (Part C T12), logs `results/run.log` (Part A), `run-p15-06.log`, `run-p15-06-t12.log`; `results.md` after the run. CPU only (4 threads); RAM about 2-2.5 GB with the LLM loaded (P15-05 / P15-06 runs: 2.4 GB peak on T12).

## Dry run (plumbing only)
`TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12 TRUST_RERUN_STUB_LLM=1`: M4-12 subsets (160 calibration, 60 held out), a deterministic stub instead of the LLM, arms A0 and B1 only, 20 null trials; on T12 a cache miss gives an empty n-best (no decoder load). Real runs refuse the stub and the M4-12 source. Result: P15-05 (873 MB), P15-06 with `@single` (740 MB) and T12 `@single` (670 MB) run end to end. On the 160-item subset no configuration is certifiable (expected: 120 test items < 230).
