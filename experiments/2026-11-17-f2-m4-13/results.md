---
title: F2 reruns on the M4-13 decoder (P15-05, P15-06) and the variant V-single (T15 + T12) - results
type: experiment
task: P15-05, P15-06, P15-14
updated: 2026-11-18
---

# F2 reruns on M4-13: LLM rescoring with grounding, the fluent-wrong bound, and V-single (results)

Pre-registration: [plan.md](plan.md) (commit `97a2fc4`, before any M4-13 output). Method code: the [P15-05](../2026-11-16-f2-e3-llm-grounding/results.md) and [P15-06](../2026-11-16-p15-06-halluc-bound/results.md) scripts, imported unchanged; the variant is `variant_guard` in [run.py](run.py). Aggregates: [results/results-t15.json](results/results-t15.json) (Part A), [results/results-p15-06.json](results/results-p15-06.json) (Parts B + C T15), [results/results-p15-06-t12.json](results/results-p15-06-t12.json) (Part C T12); logs `results/run.log`, `run-p15-05.log`, `run-p15-06.log`, `run-p15-06-t12.log`. Per-trial files and caches: `C:/Users/zhang/bci-data/derived/f2-reruns-m4-13/` only.

Runs (queue stages, CPU, background class, 4 threads): `p15-05` 2026-11-17 21:43-23:28 (6,333 s, peak 2.96 GB); `p15-06` 23:28-23:45 (975 s); `p15-06-t12` 23:45-23:47 (141 s). Decoder (Parts A, B, C T15): M4-13 long0 `best.pt` (step 115,000, SHA-256 `8fafe916...`); calibration val_select (722), held out val_eval (701). Part C T12: the T12 v2 decoder caches of P15-05 / P15-06 (480 calibration, 400 held out); no decoder or LLM load (0 cache misses).

## Verdict

| part | rule (pre-registered) | result |
|---|---|---|
| A (P15-05 on M4-13) | **S1** WER(B1) < WER(A0), bootstrap CI below 0 | **pass** (0.1617 vs 0.1827; diff -0.0210 [-0.0265, -0.0154]) |
| | **S2** guard returned, held-out wrong-commit rate <= 0.05 | **pass** (12 / 701 = 0.0171, CP95 [0.0089, 0.0297]) |
| | **S3** uniform, shuffled <= 1 / 300; swapped unsupported <= 2 / 701 | **pass** (0, 0, 0) |
| | **S4** hallucination rate(B1) <= A0 and fluent-wrong(B1) <= A0 | **fail** (rate 0 = 0; fluent-wrong 6 > 2) |
| | F2/E3 pass (S1-S4) | **no** (as on M4-12: S4) |
| B (P15-06 on M4-13) | **H1** feasible bound; held-out fluent-wrong <= 0.01, wrong-commit <= 0.05 | **pass** (feasible; 1 / 701 = 0.0014 and 2 / 701 = 0.0029) |
| | **H2** fluent-wrong(B1) <= A0 of Part A (2) | **pass** (1) |
| | **H3** controls (uniform, shuffled <= 1 / 300; swapped unsupported <= 2 / 701; built-in controls) | **pass** (0, 0, 0; built-in 0 / 300, 0 / 300) |
| | **H4** top-1 = Part A B1 on all 701 (WER gain kept) | **pass** (701 / 701; WER 0.1617, S1 interval above) |
| | P15-06 pass (H1-H4) | **yes** |
| | Utility: right commits of B1 vs Part A B1 | **safe but costly**: 34 of 142 kept (24 %, < half) |
| C (V-single) | **V1** B1@single certified on T12 | **pass** (commit_p 0.40, tau_commit 0, tau_word 0.5; 2,607 of 4,284 points certified) |
| | **V2** B1@single held out: fluent-wrong <= 0.01, wrong-commit <= 0.05 (T12 and T15) | **pass** (T12: 1 / 400 = 0.0025 and 2 / 400 = 0.0050; T15: 0.0014 and 0.0029) |
| | **V3** controls (T12 swapped limit 2 / 400) | **pass** (both sets: 0, 0, 0; built-in controls pass) |
| | **V4** primary guard inside each @single arm: same `config_id` and selection as the committed P15-06 T12 run (T12) / Part B (T15) | **T15 pass** (8 / 8 ids and selections). **T12 fail as written**: selection 8 / 8 equal, `config_id` 0 / 8 equal. Cause (exploratory check below): only the decoder label in the recipe differs |
| | V5 (descriptive) | T15: @single = primary in every arm. T12: primary 0 commits in every arm; @single 1-10 commits, mostly wrong |

## Part A: P15-05 on M4-13 (held-out val_eval, 701)

| arm | WER | sent. acc | dWER vs A0 [95 %] | commits | wrong | wrong-commit rate [CP95] | halluc. rate | fluent-wrong | uniform | shuffled | swapped commits (unsupported) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 n-gram | 0.1827 | 0.367 | - | 104 | 17 | 0.0243 [0.0142, 0.0385] | 0 | 2 | 0 | 1 | 104 (104) |
| A1 n-gram + G | 0.1827 | 0.367 | +0.0000 | 104 | 17 | 0.0243 | 0 | 2 | 0 | 1 | **0 (0)** |
| B0 rescore | 0.1617 | 0.462 | -0.0210 [-0.0265, -0.0154] | 141 | 10 | 0.0143 [0.0069, 0.0261] | 0 | 6 | 0 | 0 | 141 (141) |
| **B1 rescore + G** | **0.1617** | **0.462** | **-0.0210 [-0.0265, -0.0154]** | **154** | **12** | **0.0171 [0.0089, 0.0297]** | **0** | **6** | 0 | 0 | **0 (0)** |
| C0 lattice rewrite | 0.1675 | 0.422 | -0.0152 [-0.0217, -0.0084] | 175 | 18 | 0.0257 [0.0153, 0.0403] | 0 | 11 | 0 | 0 | 175 (175) |
| C1 lattice rewrite + G | 0.1675 | 0.422 | -0.0152 [-0.0217, -0.0084] | 176 | 18 | 0.0257 | 0 | 11 | 0 | 0 | **0 (0)** |
| D0 free rewrite | 0.1692 | 0.428 | -0.0135 [-0.0207, -0.0064] | 180 | 18 | 0.0257 | 0.0069 (32 / 4653) | 10 | 0 | 0 | 180 (180) |
| D1 free rewrite + G | 0.1692 | 0.428 | -0.0135 [-0.0207, -0.0064] | 179 | 18 | 0.0257 | 0.0039 (18 / 4672) | 10 | 0 | 0 | **0 (0)** |

The bootstrap intervals were computed after the run with the P15-05 `paired_bootstrap` (B 2,000, seed 0) on the saved top-1 texts (the queue writes no summary file); the recomputed A0 WER equals the stored value. Secondary C1 vs A0: S1 pass, S2 pass (0.0257), S3 pass, S4 fail (fluent-wrong 11 > 2). Grounding (X1 vs X0): same WER in every pair (diff 0); swapped-signal commits 104 / 141 / 175 / 180 -> 0.

Next to M4-12 (P15-05, 2026-11-16): A0 WER 0.3985 -> 0.1827, sentence accuracy 0.084 -> 0.367; B1 commits 10 (2 wrong) -> 154 (12 wrong); B1 fluent-wrong 2 -> 6, A0 fluent-wrong 0 -> 2.

## Part B: P15-06 on M4-13 (held-out val_eval, 701)

Counts are commits / wrong / fluent-wrong. Base commit_p (P14-03 value inside P15-06) 0.77 for B1.

| arm | rule | selected (commit_p, tau_commit, tau_word) | Part A | P15-06 | blocked by gate | fluent-wrong rate [CP95] | wrong-commit rate [CP95] |
|---|---|---|---|---|---|---|---|
| A0 n-gram | fewest_halluc | 0.94, 0, 0.25 | 104 / 17 / 2 | 7 / 0 / 0 | 0 | 0 [0, 0.0052] | 0 [0, 0.0052] |
| A1 n-gram + G | fewest_halluc | 0.94, 0, 0.25 | 104 / 17 / 2 | 7 / 0 / 0 | 0 | 0 | 0 |
| B0 rescore | fewest_halluc | 0.91, 0, 0.5 | 141 / 10 / 6 | 39 / 2 / 1 | 2 | 0.0014 [0.0000, 0.0079] | 0.0029 [0.0003, 0.0103] |
| **B1 rescore + G** | fewest_halluc | **0.92, 0.05, 0.5** | 154 / 12 / 6 | **36 / 2 / 1** | 1 | 0.0014 [0.0000, 0.0079] | 0.0029 [0.0003, 0.0103] |
| C0 lattice rewrite | fewest_halluc | 0.91, 0, 1.0 | 175 / 18 / 11 | 22 / 0 / 0 | 0 | 0 | 0 |
| C1 lattice rewrite + G | fewest_halluc | 0.91, 0, 1.0 | 176 / 18 / 11 | 25 / 0 / 0 | 0 | 0 | 0 |
| D0 free rewrite | fewest_halluc | 0.92, 0, 1.0 | 180 / 18 / 10 | 27 / 0 / 0 | 0 | 0 | 0 |
| D1 free rewrite + G | fewest_halluc | 0.93, 0, 0.25 | 179 / 18 / 10 | 26 / 0 / 0 | 4 | 0 | 0 |
| B1 + G | most_right | 0.89, 0, 0.5 | 154 / 12 / 6 | 54 / 2 / 1 | 3 | 0.0014 | 0.0029 |
| C1 + G | most_right | 0.87, 0, 1.0 | 176 / 18 / 11 | 46 / 1 / 1 | 1 | 0.0014 | 0.0014 |

All arms: uniform 0 / 300, shuffled 0 / 300, swapped 0 / 701, built-in controls pass, bound holds. In-sample LTT test of B1 (271 items): 17 commits, 17 right, p-values 9.2e-7 (wrong-commit) and 0.066 (fluent-wrong). Next to M4-12: the B1 guard went from 0 commits (vacuous) to 36 commits, 34 right.

## Part C: variant V-single

### T15 (M4-13; 542 non-fit items in one test set)
In every arm, @single selects the same configuration as the primary rule, so the held-out decisions are equal (B1: 36 / 2 / 1). The in-sample test is stronger: B1 28 commits, 28 right on 542 items, p-values 8.4e-13 and 0.0043 (primary: 0.066). Primary `config_id` inside each @single arm = Part B `config_id` in 8 / 8 arms (V4 T15 pass).

### T12 v2 (360 non-fit items in one test set; primary: 180 + 180)

| arm | primary (committed P15-06 T12) | @single selected (commit_p, tau_commit, tau_word) | certified points | LTT test commits / right (n 360) | held-out commits / wrong / fluent-wrong (n 400) | fluent-wrong rate [CP95] | wrong-commit rate [CP95] |
|---|---|---|---|---|---|---|---|
| A0 n-gram | inf (0 commits) | 0.37, 0, 1.0 | 2,859 | 3 / 3 | 10 / 7 / 2 | 0.0050 [0.0006, 0.0179] | 0.0175 [0.0071, 0.0357] |
| A1 n-gram + G | inf | 0.37, 0, 1.0 | 2,859 | 3 / 3 | 10 / 7 / 2 | 0.0050 | 0.0175 |
| B0 rescore | inf | 0.40, 0, 0.5 | 2,607 | 3 / 3 | 3 / 2 / 1 | 0.0025 [0.0001, 0.0138] | 0.0050 [0.0006, 0.0179] |
| **B1 rescore + G** | **inf** | **0.40, 0, 0.5** | 2,607 | 3 / 3 | **3 / 2 / 1** | **0.0025 [0.0001, 0.0138]** | **0.0050 [0.0006, 0.0179]** |
| C0 lattice rewrite | inf | 0.43, 0, 0.25 | 2,520 | 1 / 1 | 7 / 4 / 2 | 0.0050 | 0.0100 [0.0027, 0.0254] |
| C1 lattice rewrite + G | inf | 0.43, 0, 0.25 | 2,520 | 1 / 1 | 7 / 4 / 2 | 0.0050 | 0.0100 |
| D0 free rewrite | inf | 0.43, 0, 0.25 | 2,563 | 1 / 1 | 7 / 4 / 2 | 0.0050 | 0.0100 |
| D1 free rewrite + G | inf | 0.43, 0, 0.25 | 2,563 | 1 / 1 | 7 / 4 / 2 | 0.0050 | 0.0100 |

All T12 arms: uniform 0 / 300, shuffled 0 / 300, swapped 0 / 400, built-in controls pass. B1 in-sample p-values: 9.6e-9 (wrong-commit) and 0.027 (fluent-wrong). The arithmetic: zero fluent-wrong commits in n test items gives p = 0.99^n; 0.99^360 = 0.027 <= 0.1, while 0.99^180 = 0.164 > 0.1 (the primary split). Any n >= 230 can pass.

### V4 on T12: why the ids differ (exploratory check, not pre-registered)
The committed P15-06 T12 guards store the recipe field `decoder = custom:__main__.calibrate_arm.<locals>.fn` (the script ran as `__main__`). Our run imports the same script as module `p1506_run`, so the label is `custom:p1506_run.calibrate_arm.<locals>.fn`. The label is part of the hashed config, so `config_id` changes. Check: we loaded each committed T12 guard config, replaced only `__main__.` by `p1506_run.` in that label, and recomputed `FrozenTrustConfig.config_id`. It equals the @single arm's primary `config_id` in 8 / 8 arms. All other config fields, the selection and the decisions are equal. So the primary T12 rule is reproduced; the id is not stable under a code label. New gap P5-21 (gap 59).

## What this means
- **P15-14 (certified T12 bound): done-when met.** A certified fluent-wrong bound (alpha_h 0.01, delta_h 0.1, with wrong-commit alpha 0.05) exists on held-out T12 data: B1@single, held-out fluent-wrong 0.0025, wrong-commit 0.0050, all controls pass. The guarantee statement is that of P15-06 (fixed-sequence test in a data-independent order keeps the family-wise error <= delta_h).
- But the T12 bound is **not useful**: 3 held-out commits, 1 right. It is a certificate, not an operating point. T12 usefulness waits for a stronger T12 decoder (P14-14, P11).
- On T15 the bound is now **non-vacuous**: 36 commits, 34 right (M4-12: 0 commits). The cost is large: 24 % of the right commits of the unbounded B1 stay (most_right rule: 52 of 142, 37 %).
- F2/E3 still fails S4 on M4-13. Rescoring makes more commits (154 vs 104) with fewer wrong ones (12 vs 17), but more of the wrong ones are fluent (6 vs 2). S4 compares counts, so an arm that commits more is penalised. We report the rule as written.

> **Our take:** with M4-13 the trust stack is safe and starts to be useful on T15: the drop-in guard commits 104 sentences at 84 % precision, LLM rescoring raises this to 154 at 92 %, and the fluent-wrong bound keeps 36 at 94 %. On T12 the safety certificates now exist, but the decoder is too weak to give a useful commit rate.

## Hallucination benchmark 0.2 add-on (run after the queue, 2026-11-18)
[add_m4_13.py](../2026-11-17-p15-15-halluc-0.2/add_m4_13.py) scored the M4-13 guards under protocol `fidetype.halluc/0.2` (cache-only, 667 MB peak). The P15-06 B1 guard (and B1@single, the same decisions) **passes all tracks**: real 36 commits (2 wrong), null 0 / 300, scrambled 0 / 300, swapped 0 / 701 (pairs with a commit: n10 36, n01 0). It is the first benchmark entry that passes the swapped track under 0.2. P15-05 A0 and B0 fail the swapped track (A0: n10 89, n01 89; B0: n10 115, n01 115). Details: [P15-15 results](../2026-11-17-p15-15-halluc-0.2/results.md#m4-13-t15).

## Deviations
- None in the method. The config `description` string in `results-t15.json` still says "T15 M4-12 fixed0 logits": it is copied from the P15-05 config file. The provenance block (`source m4-13`, checkpoint hash) and the run log show the real inputs.
- The S1 / dWER intervals were computed after the queue (the queue has no report step), with the unchanged P15-05 function on the saved per-trial outputs.
