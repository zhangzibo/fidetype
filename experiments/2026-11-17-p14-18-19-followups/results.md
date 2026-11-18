---
title: P14-18 and P14-19 word-setting follow-ups - results
type: experiment
task: P14-18, P14-19
updated: 2026-11-17
---

# P14-18 / P14-19: results

Pre-registration: [plan.md](plan.md) (commit `3d07cb4`, before any run). Script: [run.py](run.py) (stages `m4`, `p1403`, `rebuild`, `analyze`, `downstream`, `recompare`), launcher [launch.py](launch.py). Numbers: [results/p14-18.json](results/p14-18.json), [results/p14-19-step2.json](results/p14-19-step2.json), [results/p14-19-step3.json](results/p14-19-step3.json). Local only: `C:\Users\zhang\bci-data\derived\p14-18-19\` (rebuilt tables, decode cache, per-trial values, downstream reruns, logs). CPU only: one hidden queue, background class, 4 threads, 2026-11-17 03:50-07:28 (M4-12 37 min, P14-03 14 min, rebuild 1.85 h, M4-01/02 52 min, analyses 4 min).

## Decisions (pre-registered rule: effect = a primary metric moves by its 95 % CI half-width or more)
- **P14-18 (gap 44): effect.** With edit penalty 8, **14 of 166** primary metrics move by their half-width or more. 1 is in M4-12 (of 90), 11 are in the superseded M4-01/02 rows (of 72), and 2 are in the P14-03 rows. **All of them move in favour of edit 8:** lower WER, more truth in n-best, higher eWPM, and fewer commits. So the 16 `val_eval` tune trials did not make the committed M4 rows look better. The committed rows are equal to or slightly worse than the rows with the setting tuned without `val_eval`.
- **P14-19 (gap 45): effect, but only in the forward chain.** The rebuilt re-split tables (published gate guard on, ours and published guard off) show **0 of 240** effects (largest change 0.47 of the half-width). The effects come from the forward-chain fit prefix "day 1 only" (30 trials), which picks edit 8. They are 9 of 320 forward-chain metrics, all of them plug-in-rule rows of "ours". The same prefix gives 16 day-level effects in A2 (all on day 34). Downstream there are also 2 small-denominator effects in joint LTT and 1 Monte-Carlo-only effect in population risk (see step 3).

Committed numbers stay as they are. The affected pages get dated correction notes. The paper track gets a correction note ([papers/paper1/correction-2026-11-17-p14-19.md](../../papers/paper1/correction-2026-11-17-p14-19.md)).

## Checks (all passed before any result was read)
| Check | Result |
|---|---|
| M4-12 reference runs (edit 12, committed cache read-only), 10 conditions | all committed numbers reproduced (WER, exact, truth in n-best, commits, wrong commits, eWPM); 0 cache misses |
| M4-01/02 reference runs, 8 conditions | all reproduced. The committed cache had no entry for these log-probs (1,402 misses per condition, decoded fresh with edit 12), so this is also an independent decode check |
| P14-03 T15 reference (alpha 0.05 / 0.10) | commits 2 / 2 wrong and eWPM 6.016 reproduced (the `config_id` hash differs from the committed one; the decisions do not) |
| Rebuild code path, paper setting: `published-g1` split 0 (first 100 test items) | all 11 arrays, T and plug-in lambda equal |
| Rebuild code path, paper setting: forward prefix 0 "ours" guard on (all 13 later days) | all arrays and T equal |

## P14-18: M4 rows with edit penalty 8 (lm 1.0, bonus 3)
M4-12 (`val_eval`, 701 trials). Committed (edit 12) → edit 8 (CI half-width):

| condition | WER T = 1 | WER frozen T | truth in n-best (frozen T) | commits | trust eWPM |
|---|---|---|---|---|---|
| dedicated_0 L 0 | 0.3998 → 0.3976 (0.0173) | 0.4105 → 0.4041 (0.0172) | 0.131 → 0.143 | 0 → 0 | 5.94 → 6.03 (0.19) |
| dedicated_10 L 200 ms | 0.3923 → 0.3923 | 0.4036 → 0.3994 | 0.140 → 0.155 | 0 → 0 | 6.02 → 6.05 |
| dedicated_15 L 300 ms | 0.3998 → 0.3987 | 0.4109 → 0.4053 | 0.130 → 0.143 | 0 → 0 | 5.97 → 6.03 |
| dedicated_25 L 500 ms | 0.4565 → 0.4558 | 0.4336 → 0.4272 | 0.128 → 0.147 | 0 → 0 | 5.77 → 5.88 |
| shared L 0 | 0.4049 → 0.4032 | 0.4195 → 0.4111 | 0.124 → 0.144 | 0 → 0 | 5.88 → 5.96 |
| shared L 40 ms | 0.4034 → 0.4028 | 0.4173 → 0.4094 | **0.121 → 0.148** (half-width 0.024) | 0 → 0 | 5.87 → 5.97 |
| shared L 100-500 ms | 0.4006-0.4032 → 0.4006-0.4015 | 0.4094-0.4171 → 0.4047-0.4101 | 0.114-0.127 → 0.134-0.144 | 0 → 0 | 5.88-5.93 → 5.95-5.99 |

- The only M4-12 effect is the truth-in-n-best rate of shared L 40 ms (ratio 1.12). No WER, commit or eWPM change reaches its half-width. The M4-12 conclusions (flat lookahead curve, 2.5x the published PER, 0 commits) do not change.
- **M4-01/02** (superseded by M4-12): WER at the frozen T is 0.019-0.023 lower with edit 8 for shared L 40-500 ms. This is 1.2-1.4x the half-width (6 effects). The other effects: eWPM +0.10 (shared L 100 and 500 ms), sentence exact 0.006 → 0.013, truth in n-best +0.010-0.011, and always-commit wrong-commit 0.994 → 0.987 (shared L 200 ms). WER at T = 1 does not move by its half-width in any condition.
- **P14-03 T15 guard** (calibrate on `val_select`, decide on `val_eval`): commits 2 (both wrong) → 0 at alpha 0.05 and 0.10. Wrong-commit rate 0.0029 → 0 (half-width 0.0048), commit rate the same, eWPM 6.016 → 6.013 (half-width 0.19). The sentence temperature is 11.96 → 12.61. The error among commits (2 of 2) has no value with 0 commits. The script counts this change as an effect, which is conservative; the plan did not name this case. The held-out wrong-commit result ("pass") stays.

> **Our take:** the M4 effect is real but small, and its sign is the reassuring one. Edit 8 decodes `val_eval` slightly better than the paper point, so the committed M4 word rows are not optimistic. P14-03 loses its 2 (wrong) commits; its pass verdict gets stronger, not weaker. New gap 50 (P14-21) reruns the M4-x / M2-19 / P15-05..07 / P5-02 rows that use these decodes.

## P14-19 step 1: rebuilt tables
For the 35 changed re-splits (8 with r < 50): 105 tables (published-g1, ours-g0, published-g0) + 32 published-margin tables + 16 trust v5 split rows, each with the split's own fit-A setting. Forward-chain prefix 0: 4 tables with edit 8. For prefix 0, T stays 2.78, and the fit-A commit threshold changes only for published guard off (0.95 → 0.80).

## P14-19 step 2: primary analysis
R3 `split_policies`, 8 policies x 5 metrics, MC / Wilson half-widths of the original values:

| table | R | changed splits | effects | largest change / half-width |
|---|---|---|---|---|
| published, guard on | 50 / 200 | 8 / 35 | 0 / 0 | 0.28 / 0.16 |
| ours, guard off | 50 / 200 | 8 / 35 | 0 / 0 | 0.22 / 0.25 |
| published, guard off | 50 / 200 | 8 / 35 | 0 / 0 | 0.47 / 0.13 |

**Forward chain** (R4 `forward-chain`, prefix 0 replaced; it feeds V1 test day 3, V4 test day 4, V3 test day 2 and the staleness view): 120 of 320 metrics change. **9 are effects, all on the plug-in rule of "ours":** pooled commit rate in V1 / V3 / V4 (guard on and off), and pooled wrong-commit in V4 guard on and V1 / V4 guard off (largest ratio 1.53). Summary rows, committed → recomputed:

| condition | variant | plug-in days > α, pooled | CRC max days > α | LTT max days > α, pooled |
|---|---|---|---|---|
| ours, guard | V1 | 5/12, 0.052 → 4/12, 0.041 | 4/12 → 4/12 | 2/12, 0.022 → 2/12, 0.022 |
| ours, guard | V4 | 5/11, 0.060 → 4/11, 0.046 | 4/11 → 3/11 | 0/11, 0.027 → 0/11, 0.025 |
| ours, guard | V3 | 5/13, 0.058 → 4/13, 0.044 | 3/13 → 2/13 | 2/13, 0.015 → **1/13, 0.011** |
| ours, no guard | V1 | 1/12, 0.038 → 0/12, 0.027 | 0/12 → 0/12 | 0/12, 0.018 → 0/12, 0.019 |
| published, guard | V3 | 1/13, 0.028 → 1/13, 0.025 | 1/13 → 0/13 | 1/13, 0.010 → **0/13, 0.006** |
| published, no guard | V3 | 1/13, 0.021 → 1/13, 0.020 | 1/13 → 0/13 | 1/13, 0.014 → 0/13, 0.010 |

- The days with a plug-in CP lower bound above α (ours: day 46 in V1, day 48 in V4, day 34 in V3) were all tested with the prefix-0 fit. **With the edit-8 prefix, no day in any design has a CP lower bound above α.**
- LTT max: 0-2 of 10-13 days above α (unchanged range). The pooled range becomes 0.006-0.027 (was 0.010-0.027). V2 does not use prefix 0 and does not change.

## P14-19 step 3: downstream analyses (rerun with redirected tables)
| analysis | changed values | values with a committed CI | effects | note |
|---|---|---|---|---|
| R4 population risk | 108 | 24 | 1 | "ours" R = 50 CRC max population share > α 0.1685 → 0.1604; the CI (half-width 0.0074) is the CP interval over 10,000 resampling draws, so it covers only resampling noise (ratio 1.10). Test-exceedance shares: no effect |
| R4 per-day | 1,857 | 0 | 0 | no CI in the file; same tables as step 2 |
| R4 joint LTT | 484 | 24 (+ 36 MC) | 2 | share of committing splits with EAC > β = 0.20, "ours" guard on R = 50, SGR rules: 0.5 → 0.0. Only 2 splits commit, so 1 split decides (CP half-width 0.49, ratio 1.03). MC half-widths of the means: 0 of 36 (largest 0.24) |
| R4 no-guard Tab. 2 | 269 | 18 | 0 | largest 0.43 |
| R4 bonus sensitivity (repeated) | 103 | 3 | 0 | largest 0.19 |
| R4 reuse, cleanup | 297, 91 | 0 | 0 | no CI in the files (p-values not decided on) |
| M3-01/02 repeated-split arms | 106 | 9 | 0 | largest 0.26 |
| trust v5 split summary (8 rows rebuilt) | 86 | 10 | 0 | largest 0.24 |
| A2 per-session risk | 8,541 | 144 | 16 | all on test day 34, V3 "ours" (prefix 0): the day rate drops to 0 for every method (global 0.20 → 0.00, half-width 0.083). Re-split parts: no CI in the files |

M2-18, all fixed-split rows (splits A and B) and all full-fit rows were not rerun (plan: their fit sets keep the paper point).

> **Our take:** the re-split rows of Paper 1 do not depend on the word setting, for either decoder or guard setting. Only the 30-trial day-1 fit is sensitive, and there the paper point was worse: it added wrong plug-in commits on days 2-4. This makes the forward-chain result for LTT max slightly better (published V3 0/13 days above α). The joint-LTT and population-risk "effects" are formal: one split out of two, or a resampling-only CI.

## Deviation from the plan
- **Comparator fix before the write-up.** In its first pass, the step-3 comparator paired CIs too loosely. It paired every `share*` key with `share_gt_alpha_cp95` (for example, the share of the 2-3 committing splits with the share over 200 splits). It also compared A2's count `wrong` with its rate CI `wrong_cp95`. That pass gave 10 joint-LTT and 73 A2 "effects" (ratios up to 242). We fixed the pairing to exact siblings (stage `recompare`, same saved outputs, no rerun) before we wrote any decision. The table above uses the fixed pass. Both passes report "effect".
- No other deviation.

## New gaps
- **50 = P14-21:** rerun the M4-x / M2-19 / P15-05..07 / P5-02 rows that use the B2T word decodes of `val_eval` with lm 1.0 / edit 8 / bonus 3 (P14-18 found an effect, favourable to edit 8).
- **51 = P14-22:** R3-level analyses that read the re-split tables but were not covered here: R3 `repeated-splits` analyze (full output), `selective-risk`, `deployable-rule`, `v3-derived`, R4 `v4-derived` guard controls; also the forward-chain-based figures of Paper 1 (Fig. deploy a).

## Limits
- Most setting changes are exact WER ties (P14-15). With another tie rule, edit 12 would stay on T2a, and P14-18 would have nothing to rerun.
- CI half-widths are conditional on one participant's data (trial bootstrap / Wilson / MC over splits), as in P14-15.
