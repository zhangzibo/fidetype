---
title: P15-06 (F2) risk-controlled fluent-wrong bound - results
type: experiment
task: P15-06
updated: 2026-11-16
---

# P15-06: a risk-controlled bound on fluent-wrong commits (results, T15 + T12)

Plan (written before the held-out runs): [plan.md](plan.md). Pillar F2 ([north star](../../wiki/questions/north-star.md#f2-faithful-language-model-decoding-e3), [roadmap P15-06](../../wiki/questions/roadmap-standard.md#p15-06-risk-controlled-hallucination-bound)). Input: [P15-05 results](../2026-11-16-f2-e3-llm-grounding/results.md). Aggregates: [results/results-t15.json](results/results-t15.json), [results/summary-t15.json](results/summary-t15.json), log [results/run.log](results/run.log), design check `results/explore-*.json`. Report script: [report.py](report.py). Per-trial outputs: `C:\Users\zhang\bci-data\derived\p15-06-halluc-bound\` only (T12: its `t12\` subfolder). T12: [section below](#t12-2026-11-16), [results/results-t12.json](results/results-t12.json), [results/summary-t12.json](results/summary-t12.json), log [results/run-t12.log](results/run-t12.log).

## Verdict
- **P15-06 passes its pre-registered rule on T15 (H1-H4 for B1), but at a high cost.** With the primary selection rule, the B1 guard (LLM rescoring + grounding) **never commits** on the 701 held-out trials (P15-05 B1: 10 commits, 8 right). The utility check fails (0 of 8 right commits kept). This is "safe but costly", as the design check predicted.
- **The bound holds in every arm.** Held-out fluent-wrong rate: 0 to 0.0029 (alpha_h 0.01); wrong-commit rate: 0 to 0.0029 (alpha 0.05).
- **Fluent-wrong commits fall in every LLM arm:** B 2 -> 0, C 5 -> 1, D 3 -> 1 (primary rule). Only B reaches the baseline (A0: 0).
- **New finding: the commit-text gate stops swapped-signal commits without the P15-05 grounding.** Every selected configuration has `tau_commit = 0` (or 0.005): the committed text must score at least as well under CTC as the decoder top-1 without the LLM on the same signal. In the ungrounded arms this takes swapped-signal commits from 9 / 28 / 23 (B0 / C0 / D0, P15-05) to 0.
- **T12 (2026-11-16): the bound is not certifiable.** With 180 LTT test items, no point of the grid can pass the test at alpha_h = 0.01, delta_h = 0.1: zero fluent-wrong commits in 180 items gives p = 0.99^180 = 0.164 > 0.1 (the minimum is 230 items). Every T12 guard falls back to "never commit" (commit_p = inf). H1 fails on T12. The held-out fluent-wrong rate is 0 and all controls pass, but only because nothing commits. See [T12](#t12-2026-11-16).
- P15-06 is **done** as a task (both sets run against the pre-registered rule). The rule passes on T15 (at a high cost) and fails on T12 (H1: no certificate). So the roadmap "done when" (a certified bound on two public sets) is **not met**.

## Guarantee (what the guard states)
With exchangeable data, and the decoder, the LLM and the fluent threshold fixed:

> P( fluent-wrong commit rate <= 0.01 **and** wrong-commit rate <= 0.05 ) >= 0.9

Fluent-wrong commit = a COMMIT whose text is not the truth and whose LLM log-probability per word is >= -7.8817 (the P15-05 metric). Rates are over all utterances. Method: Learn then Test over the joint grid (commit_p, tau_commit, tau_word) (4,284 points); p-value max(p_wc, p_h), exact binomial; test order from the 271 policy-grid items; fixed-sequence test on the 271 LTT items. The P14-03 statement (wrong-commit rate <= 0.05 with probability >= 0.9) also holds, because the chosen `commit_p` is never below the P14-03 one and the gate only removes commits.

## Arm table (held-out `val_eval`, 701 trials)
"P15-05" = the matching P15-05 arm. Counts are commits / wrong / fluent-wrong.

| arm | rule | selected (commit_p, tau_commit, tau_word) | P15-05 | P15-06 | blocked by the word / sentence gate | fluent-wrong rate [CP95] | wrong-commit rate [CP95] | uniform | shuffled | swapped not truth (P15-05) | WER |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 n-gram | primary | (0.31, 0, 0.5) | 2 / 2 / 0 | 2 / 2 / 0 | 0 | 0 [0, 0.0052] | 0.0029 [0.0003, 0.0103] | 0/300 | 0/300 | 0 (2) | 0.3985 |
| A1 n-gram + G | primary | (0.31, 0, 0.5) | 2 / 2 / 0 | 2 / 2 / 0 | 0 | 0 [0, 0.0052] | 0.0029 [0.0003, 0.0103] | 0/300 | 0/300 | 0 (0) | 0.3985 |
| B0 rescore | primary | (0.65, 0, 0.25) | 9 / 2 / 2 | 0 / 0 / 0 | 0 | 0 [0, 0.0052] | 0 [0, 0.0052] | 0/300 | 0/300 | 0 (9) | 0.3831 |
| **B1 rescore + G** | **primary** | **(0.65, 0, 0.25)** | **10 / 2 / 2** | **0 / 0 / 0** | 0 | **0 [0, 0.0052]** | **0 [0, 0.0052]** | 0/300 | 0/300 | **0 (0)** | **0.3831** |
| C0 lattice rewrite | primary | (0.42, 0, 0.5) | 28 / 9 / 5 | 4 / 1 / 1 | 0 | 0.0014 [0, 0.0079] | 0.0014 [0, 0.0079] | 0/300 | 0/300 | 0 (28) | 0.3874 |
| C1 lattice rewrite + G | primary | (0.42, 0, 0.5) | 29 / 9 / 5 | 4 / 1 / 1 | 0 | 0.0014 [0, 0.0079] | 0.0014 [0, 0.0079] | 0/300 | 0/300 | 0 (0) | 0.3874 |
| D0 free rewrite | primary | (0.36, 0, 0.5) | 23 / 6 / 3 | 6 / 1 / 1 | 2 | 0.0014 [0, 0.0079] | 0.0014 [0, 0.0079] | 0/300 | 0/300 | 0 (23) | 0.3822 |
| D1 free rewrite + G | primary | (0.37, 0, 0.5) | 26 / 6 / 3 | 6 / 1 / 1 | 2 | 0.0014 [0, 0.0079] | 0.0014 [0, 0.0079] | 0/300 | 0/300 | 0 (0) | 0.3822 |
| B1 | most_right (secondary) | (0.40, 0, 0.5) | 10 / 2 / 2 | 8 / 1 / 1 | 2 | 0.0014 [0, 0.0079] | 0.0014 [0, 0.0079] | 0/300 | 0/300 | 0 (0) | 0.3831 |
| C1 | most_right (secondary) | (0.36, 0.005, 0.5) | 29 / 9 / 5 | 13 / 2 / 2 | 1 | 0.0029 [0.0003, 0.0103] | 0.0029 [0.0003, 0.0103] | 0/300 | 0/300 | 0 (0) | 0.3874 |

- The pipeline top-1 equals P15-05 on 701 / 701 trials in every arm, so WER and sentence accuracy are the P15-05 values (the gate changes only the commit decision).
- No committed word is outside the base 10-best in any arm (unsupported committed words: 0).
- Built-in `calibrate` controls of every final guard: uniform 0/300, shuffled 0/300 (allowed 15).
- The pre-gate guard of each arm has the same fitted values as the P15-05 guard (temperatures, conformal threshold, policy, `commit_p` 0.3 / 0.4). Its `config_id` differs only by the recorded name of the decode function in the recipe.
- "Blocked by the gate" counts commits that the P14-03 policy would make at the selected `commit_p` and that the grounding gate turned into offers. Most of the removed commits come from the higher `commit_p`, not from the gate.

## Pre-registered checks (plan.md, B1 primary)
| check | result |
|---|---|
| H1 bound: feasible bound; held-out fluent-wrong <= 0.01 and wrong-commit <= 0.05 | **pass** (feasible; 0 and 0) |
| H2 fluent-wrong <= A0 (0) | **pass** (0) |
| H3 controls: uniform, shuffled <= 1/300; swapped not truth <= 2/701; built-in controls pass | **pass** (0, 0, 0; pass) |
| H4 WER gain kept: top-1 = P15-05 B1 on all 701 | **pass** (701/701; WER 0.3831 vs A0 0.3985) |
| **P15-06 pass (H1-H4)** | **yes** |
| utility (reported, does not decide): right commits kept >= 4 of 8 | **fail** (0 of 8) |

The pass is partly trivial: a guard that never commits passes H1-H3. The utility line shows the cost.

## Key findings
1. **A stated fluent-wrong bound is reachable with the drop-in wrapper**, and it held on held-out data in all 10 guards. The guarantee sheet now carries the bound (alpha_h, delta_h, loss, method, items, selected point).
2. **On T15 with this decoder, the bound costs most commits.** The would-be commits of B1 on `val_select` were 33 right, 33 fluent-wrong and 68 non-fluent wrong; their `p_top1` ranges overlap, and the word deficit separates them only in part (median 0.15 right vs 0.50 fluent-wrong). With 271 test items, alpha_h = 0.01 is certifiable only with zero fluent-wrong commits on them, so the selection goes to strict points. The primary rule ("fewest fluent-wrong first") then keeps 0 commits in B, 4 in C and 6 in D.
3. **The `most_right` rule keeps more commits** (B1: 8 commits, 7 right; C1: 13, 11 right) with the same guarantee, but keeps some fluent-wrong commits (1 and 2). Both rules hold the bound. Which rule to use is a product choice (fewer fluent-wrong vs more commits); the guarantee does not decide it.
4. **The sentence gate at `tau_commit = 0` is a cheap, strong rule**: "commit only text that the signal supports at least as well as the acoustic top-1". It blocks LLM overrides at commit time (offers keep them), and it alone stops all swapped-signal commits, also in the arms without the P15-05 grounding.
5. **The word check is used but not decisive.** Selected `tau_word` is 0.25 or 0.5 nats per frame. It blocked 2 held-out commits in D and 1-2 in the `most_right` arms; in B and C the higher `commit_p` removed the commits first.

## What this means for F2
- F2 now has a **run-time, distribution-free bound on fluent-wrong commits** for brain-decoded text, with the LLM in the loop, the null and swapped-signal controls at 0, and the WER gain of rescoring kept (as offers and top-1, not as commits). This supports the C2 claim in its safe wording (novelty check 2026-11-15): "a stated, distribution-free bound on the rate of unsupported words that it commits".
- It does **not** yet show a useful operating point on T15: with the primary rule, the LLM arms commit rarely or never. More calibration data (a lower certifiable alpha_h per item), a stronger decoder (P15-03 / M4-13) or a per-word commit (commit the grounded words, offer the rest) are the next levers.

## Deviations from the plan
- None in the held-out run. Before the plan, the design check found a cache-key bug (the anchor function got re-normalised log-probabilities, so 134 base decodes were re-run); it was fixed before the plan and before any held-out trial. The design-check numbers in the plan are from the fixed code.
- The joint-LTT selection rule became a parameter (`halluc_select`) during the design check, before the plan; the plan fixed `fewest_halluc` as primary.

## Limits
- One participant per set, one split, one LLM, CPU only. On T12 the LTT test set is too small for alpha_h = 0.01 (see T12).
- Commit counts are tiny (0 to 13 of 701); the held-out rates are coarse (CP95 upper up to 0.0103).
- The fluent threshold and the frame temperature were fitted on all of `val_select` (P15-05), which includes the LTT items (small reuse, stated in the plan).
- "Fluent" is judged by the same LLM that rescored the list. Wrong commits that it finds non-fluent count only in the wrong-commit bound.
- New LLM calls: 49 sentence scores (C / D rewrites that P15-05 never scored), CPU, into the own cache copy. No new base decode.

## T12 (2026-11-16)
Same code, config, grid, alpha_h = 0.01, delta_h = 0.1 and arms as on T15. Input: the P15-05 T12 artefacts (T12 v2 confirmatory logits; fit_a + calibration sessions = 480 fitting trials; test sessions = 400 held-out trials). Fitted values come from P15-05 T12: fluent threshold -8.9165, tau 0.4742, LLM weight 0.5, frame T 2.5281. Loader: `run.py t12 arms` (new `data_t12` + `LazyT12Decoder`; outputs only in `p15-06-halluc-bound\t12\`). We wrote no separate T12 addendum: the plan.md rules (H1-H4, utility) apply unchanged.

| arm | rule | selected | P15-05 commits / wrong / fluent-wrong | P15-06 commits / wrong / fluent-wrong | fluent-wrong rate [CP95] | uniform | shuffled | swapped not truth (P15-05) | WER |
|---|---|---|---|---|---|---|---|---|---|
| A0 n-gram | primary | not feasible (inf) | 25 / 15 / 4 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (25) | 0.3885 |
| A1 n-gram + G | primary | not feasible (inf) | 25 / 15 / 4 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (0) | 0.3885 |
| B0 rescore | primary | not feasible (inf) | 15 / 8 / 4 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (15) | 0.3851 |
| **B1 rescore + G** | **primary** | not feasible (inf) | **15 / 8 / 4** | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (**0**) | **0.3851** |
| C0 lattice rewrite | primary | not feasible (inf) | 23 / 10 / 6 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (23) | 0.3898 |
| C1 lattice rewrite + G | primary | not feasible (inf) | 23 / 10 / 6 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (0) | 0.3898 |
| D0 free rewrite | primary | not feasible (inf) | 25 / 13 / 7 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (25) | 0.3885 |
| D1 free rewrite + G | primary | not feasible (inf) | 25 / 13 / 7 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (0) | 0.3885 |
| B1 | most_right | not feasible (inf) | 15 / 8 / 4 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (0) | 0.3851 |
| C1 | most_right | not feasible (inf) | 23 / 10 / 6 | 0 / 0 / 0 | 0 [0, 0.0092] | 0/300 | 0/300 | 0 (0) | 0.3898 |

Checks (B1, primary):

| check | result |
|---|---|
| H1 bound: feasible bound; held-out fluent-wrong <= 0.01 and wrong-commit <= 0.05 | **fail** (not feasible: 0 of 4,284 grid points certified; held-out rates 0 and 0) |
| H2 fluent-wrong <= A0 (P15-05 A0: 4) | pass (0) |
| H3 controls | pass (0/300, 0/300, swapped 0/400; built-in controls 0/300, 0/300) |
| H4 WER gain kept: top-1 = P15-05 B1 | pass (400/400; WER 0.3851) |
| **P15-06 pass (H1-H4)** | **no** (H1) |
| utility: right commits kept >= half of 7 | fail (0 of 7) |

Findings:
1. **The cause is the size of the LTT test set.** The calibration split gives 180 ordering + 180 test items (T15: 271 + 271). A binomial test of "fluent-wrong rate <= 0.01" at delta 0.1 needs at least 230 items, even with zero losses (0.99^n <= 0.1). So on T12 the joint LTT stops at the first point of the chain, and `calibrate` keeps the safe fallback (commit_p = inf). The guard sheet states this (`feasible: false`).
2. **The fallback is safe:** 0 commits on 400 held-out trials, null 0/300 + 0/300, swapped 0/400, in every arm. The P15-05 T12 arms made 15-25 commits, with 8-15 wrong (4-7 fluent-wrong).
3. The pipeline top-1 equals P15-05 on 400 / 400 trials in every arm (WER unchanged). The pre-gate guards have the same fitted values as the P15-05 T12 guards (temperatures, conformal threshold, `commit_p` 0.30-0.34). The `config_id` differs only by the recorded name of the decode function (as on T15).
4. Options that would make T12 certifiable (not run; each needs a new plan first): alpha_h >= 0.0128 (n = 180 at zero losses), more calibration items (>= 230 per LTT half), or no separate ordering half.

> **Our take:** the T12 result is a power limit of the certificate, not evidence that the gate fails. A product guard must report "not certifiable at this alpha_h with this much calibration data" before deployment. The sheet already does this (`feasible: false`). A planning helper that prints the minimum calibration size for a given (alpha_h, delta_h) would make it visible earlier.

Compute: CPU, 4 threads, background class, 3.6 min for all 10 arms. No base decode (0 cache misses; the T12 word decoder never loaded). New LLM sentence scores: 65 (C / D rewrites), into the own copy of the cache. The LLM load raised private memory to 2,371 MB (before the load: under 700 MB).

Code fix during the T12 run: the first attempt stopped in `guard.save` of arm A0, before any held-out decision. An infeasible joint LTT kept NaN test p-values, and the sheet JSON refuses NaN. `JointLTTResult.to_dict` now writes `null` for them (test added in `tests/test_trust_halluc_bound.py`). The T15 results do not change (all T15 guards were feasible).
