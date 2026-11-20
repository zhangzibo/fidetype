---
title: P15-26 Replication of the P15-22 headline (T15 calibration draws + T12) - results
type: experiment
task: P15-26
updated: 2026-11-19
---

# P15-26: replication of LLM rescoring + learned commit confidence (results)

Pre-registration: [plan.md](plan.md), commit `39e9419` (committed and pushed before any stage ran). Code: [`run.py`](run.py), [`launch.py`](launch.py), commits `a719794` (stub smoke test on calibration subsets only; full pytest 1626 passed, 11 skipped), `4b7c07c` (launcher runs from a pinned snapshot), `83448eb` (fix in the T12 reference check, reporting only). Aggregates: [`results/results.json`](results/results.json); guard files (configuration + sheet, no text): `results/guard-p15-26-*.json`; hallucination outcome and card files (flags only): `results/halluc/`; log: [`results/run.log`](results/run.log). Per-trial decisions (with text): `C:\Users\zhang\bci-data\derived\p15-26\` (local only).

Run: 2026-11-19 14:56-18:05, detached, background class, 4 threads, **CPU only (no GPU)**, one process per stage. Peak private memory 2.78 GB (T15 draws) and 3.71 GB (T12). No stage was killed.

## Verdicts (pre-registered rules)

| part | test | verdict |
|---|---|---|
| **(a) T15, four calibration draws** | A (level: certified, safe, controls + protocol 0.2 pass, L1 > no-BCI) | **replicates** (4 of 4 draws) |
| (a) T15 | G (L1 beats the n-gram learned guard of the same draw) | **replicates** (4 of 4) |
| **(b) T12** | A (level) | **does not replicate on T12** (2.37 < 4.11) |
| (b) T12 | G (L1 beats the P5-23 learned guard) | **gain does not replicate on T12** (no clear difference) |

**Headline claim (fixed by the plan for this case):** "above gaze typing on T15 (stable over calibration draws); **not replicated on T12**".

### L1 safe WPM v0.1 per unit

| unit | calibration / evaluation | L1 safe WPM v0.1 [95 % CI] | no-BCI | commits / wrong (CP95 of the rate) | A | H1: L1 − n-gram learned, Δ [95 % CI] (hw) | G |
|---|---|---|---|---|---|---|---|
| c0 (= P15-22, code check) | `val_select` seed 0 → `val_eval` | 4.91 [4.25, 5.57] | 4.02 | 196 / 13 ([0.0099, 0.0315]) | (not a test) | +2.27 [1.76, 2.81] | - |
| **c1** | `val_select` seed 1 → `val_eval` | **5.58** [4.91, 6.28] | 4.02 | 221 / 16 ([0.0131, 0.0368]) | pass | +2.91 [2.35, 3.49] (0.57) | pass |
| **c2** | `val_select` seed 2 → `val_eval` | **6.00** [5.28, 6.72] | 4.02 | 245 / 23 ([0.0209, 0.0488]) | pass | +2.32 [1.74, 2.93] (0.59) | pass |
| **c3** | `val_select` seed 3 → `val_eval` | **5.23** [4.58, 5.92] | 4.02 | 211 / 16 ([0.0131, 0.0368]) | pass | +2.20 [1.66, 2.73] (0.54) | pass |
| **p1** | pooled re-split, seed 0 | **5.83** [5.12, 6.56] | 4.00 | 253 / 29 ([0.0279, 0.0589]) | pass | +2.38 [1.80, 2.98] (0.59) | pass |
| **T12** | 480 pool → 400 test sessions | **2.37** [1.34, 3.62] | 4.11 | 31 / 12 ([0.0156, 0.0518]) | **fail** (below 4.11) | +0.50 [0.05, 1.13] (0.54) | **fail** (no clear difference) |

- All six L1 guards are `certified`. Both null controls are 0 / 300 in every unit. The observed wrong-commit rate is at or below 0.05 everywhere.
- **The CI lower end is above the no-BCI reference in every T15 draw ("clearly above"):** c1 4.91, c2 5.28, c3 4.58, p1 5.12. The whole T12 interval is below 4.11.
- **Split dependence.** Over the five T15 values (c0-c3, p1): mean **5.51**, SD **0.44**, range 4.91-6.00. The P15-22 draw (c0) is the **lowest** of the five. So 4.91 was not a lucky draw. The between-draw SD (0.44) is about two thirds of the conditional bootstrap half-width (about 0.66), so the conditional CI does not include all of the calibration uncertainty.
- **Reporting note (no rule change):** the verdict stage reads the CI from the `safe_wpm` block, and that block has no CI. So `results.json` shows `ci_lower_above_reference: false` for every unit. The CIs above are the trial-bootstrap intervals of L1 from the paired bootstrap (`b_ci95`), as in P15-22. With them, every T15 draw is clearly above. The verdicts themselves do not use the CI.

### Secondary: H2 (L1 − L0, the learned score on top of the LLM arm)

| unit | L0 | L1 | Δ [95 % CI] | verdict |
|---|---|---|---|---|
| c0 | 4.18 | 4.91 | +0.73 [0.19, 1.27] | L1 beats |
| c1 | 3.82 | 5.58 | +1.76 [1.18, 2.33] | L1 beats |
| c2 | 3.85 | 6.00 | +2.15 [1.67, 2.66] | L1 beats |
| c3 | 4.78 | 5.23 | +0.45 [−0.07, 0.96] | no clear difference |
| p1 | 3.90 | 5.83 | +1.93 [1.38, 2.51] | L1 beats |
| T12 | 1.10 | 2.37 | +1.27 [0.33, 2.31] | L1 beats |

## Reference checks
- **c0 reproduces P15-22 exactly:** frame T 2.37015800035291, τ 0.06996627059278283, λ 1.0 and fluent threshold −7.88165954200173 were all refitted to the committed values. The decisions are the same, with the same action and text on 701 / 701 trials, for L1 (P15-22), L0 (P15-22) and R1' (P5-23 learned guard). So the draw code is the P15-22 pipeline.
- **T12 L0 reproduces the committed P15-05 T12 B1 decisions:** 400 / 400 (15 commits, 8 wrong). Row check against P5-23 / P5-24 T12: 400 / 400. Split hashes are equal to P5-23. Frame T of every T12 guard is 2.528092 (the committed value).
- Every split hash is equal to the plan. The recomputed no-BCI references are 4.0153 (`val_eval`), 4.0005 (p1) and 4.1140 (T12), equal to the plan.
- Hallucination protocol 0.2: `verify_split` passed for c0-c3 (committed T15 split) and T12 (committed T12 split). p1 used `make_controls` seed 0, as the plan says.

## Details

### Pipeline values refitted per T15 draw (P15-05 rules, calibration items only)

| draw | frame T | τ | λ | fluent threshold |
|---|---|---|---|---|
| c0 | 2.3702 | 0.0700 | 1.0 | −7.882 |
| c1 | 2.3033 | 0.0711 | 1.0 | −7.882 |
| c2 | 2.3187 | 0.0706 | 1.0 | −7.882 |
| c3 | 2.4093 | 0.0677 | 1.0 | −7.882 |
| p1 | 2.4063 | 0.0683 | 1.0 | −7.926 |

A new frame T changes every tempered input, so each new draw decoded all trials again: 4,046 new base decodes per draw and 3,861-7,269 new CPU LLM scores. That took 21-56 min per draw.

### Arms per unit (v0.1; commits / wrong; commit threshold; recall of exactly-right top-1 texts; AUROC of the commit score)

| unit | R1' or R1 (n-gram learned) | L0 (`p_top1`) | L1 (learned) |
|---|---|---|---|
| c0 | 2.64; 113 / 10; 0.87; 0.401; 0.889 | 4.18; 154 / 12; 0.77; 0.434 | 4.91; 196 / 13; 0.82; 0.560; 0.921 |
| c1 | 2.67; 112 / 9; 0.87; 0.404; 0.891 | 3.82; 136 / 10; 0.58; 0.388 | 5.58; 221 / 16; 0.73; 0.631; 0.928 |
| c2 | 3.67; 167 / 23; 0.62; 0.562; 0.888 | 3.85; 134 / 9; 0.68; 0.383 | 6.00; 245 / 23; 0.65; 0.681; 0.924 |
| c3 | 3.03; 131 / 12; 0.79; 0.465; 0.892 | 4.78; 177 / 16; 0.52; 0.491 | 5.23; 211 / 16; 0.75; 0.595; 0.924 |
| p1 | 3.46; 164 / 22; 0.64; 0.548; 0.910 | 3.90; 138 / 7; 0.65; 0.395 | 5.83; 253 / 29; 0.69; 0.675; 0.919 |
| T12 | 1.87 (P5-23, committed); 31 / 15 | 1.10; 15 / 8; 0.31; 0.200 | 2.37; 31 / 12; 0.34; 0.543; 0.914 |

- T15 top-1 exactly right: 325-332 of 701 with the LLM (WER 0.159-0.162), and 255-259 with the n-gram n-best (WER about 0.183). T12: 35 of 400 (WER 0.385).
- Fluent-wrong commits of L1: c1 6, c2 7, c3 7, p1 6, T12 3 (c0 5). The P5-23 n-gram learned guard (R1') varies more between draws (2.64-3.67) than L1 does relative to its level.
- p1: the CP95 upper end of the wrong-commit rate (0.0589) is above 0.05, but the observed rate (0.0414) is below it. So safety holds by the plan's rule, with no clear violation. The c2 upper end is 0.0488.

### Hallucination protocol 0.2

| unit | arm | real commits | swapped unsupported commits | n10 | upper bound of θ | swapped | controls |
|---|---|---|---|---|---|---|---|
| c0 | L1 | 196 | 0 / 701 | 196 | 0.015 | pass | pass |
| c1 | L1 | 221 | 0 / 701 | 221 | 0.013 | pass | pass |
| c2 | L1 | 245 | 0 / 701 | 245 | 0.012 | pass | pass |
| c3 | L1 | 211 | 0 / 701 | 211 | 0.014 | pass | pass |
| p1 | L1 | 253 | 0 / 701 | 253 | 0.012 | pass | pass |
| T12 | L0 | 15 | 0 / 400 | 15 | 0.181 | pass | pass |
| T12 | L1 | 31 | 0 / 400 | 31 | 0.092 | pass | pass |
| T12 | L2 (descriptive) | 138 | 0 / 400 | 138 | 0.021 | pass | pass |

Both fluency modes give the same verdicts. Null and scrambled pass everywhere.

### T12 secondary: prefix commits (proposed v0.2, not decided)
- L2 (LLM + learned prefix): v0.2 **5.25** [4.25, 6.31], with the reading cost 0.5 s + 0.3 s/word **4.95** [4.04, 5.92]. 138 commits, 18 wrong prefixes. v0.1 literal 0.00 (above alpha).
- L2 − R2 (P5-24 T12 prefix guard): v0.2 +0.49 [0.21, 0.81]; v0.2 + reading cost 4.51 → 4.95, +0.44 [0.19, 0.74]. L2 − L1 (v0.2 + reading cost): +2.64 [1.46, 3.81].
- This is above 4.11 only under the proposed metric v0.2, which is not adopted, so it does not count for any verdict.

## Notes and limits
- **Pinned code, now committed upstream.** The other agent later committed the grounding change as `296fb88` (P15-27). Its check reran P15-22 with the fixed code and found the same decisions and safe WPM ([P15-22 addendum](../2026-11-19-p15-22-llm-learned/results.md#addendum-2026-11-19-p15-27-check-of-the-9-trial-top-1-difference-gap-94)). So the pinned run should give the same verdicts as the current code.
- **Pinned code.** The shared working tree held another agent's uncommitted change to `src/fidetype/trust/grounding.py` (the P15-27 fix sorts the grounded n-best). That change could alter decisions. So all stages ran from a `git archive` snapshot of `4b7c07c` (+ the `83448eb` run.py). The c0 check confirms that this code reproduces P15-22.
- The first T12 run crashed after all arms had finished (KeyError in the L0 reference check: the P15-05 trials file has no truth field). `83448eb` fixed it, and the rerun reused the saved arms. No rule or decision changed.
- The draws vary the calibration (and in p1 the evaluation set) of one participant and one decoder checkpoint. p1 is slightly optimistic by design (the checkpoint was chosen on `val_select`; 354 of its 701 evaluation trials come from there). The c-draws do not have this bias and give 5.23-6.00.
- T12 has only 400 test trials and a much weaker decoder (WER 0.385 vs 0.162). The T12 gain over P5-23 (+0.50) points in the same direction as T15 but sits inside the half-width.

> **Our take:** the T15 result is robust to the calibration draw. Every one of four new draws gives a certified safe WPM clearly above gaze typing (5.23-6.00), and the original 4.91 is the lowest value we saw. The learned score + LLM gain over the n-gram learned guard (+2.2 to +2.9) also holds in every draw. The claim does not transfer to T12 at this decoder quality: 2.37 against 4.11, with only 35 of 400 top-1 texts exactly right. The limit there is the decoder, not the guard. The README and the frontier page must say "on T15", not "replicated", and must name T12 as a negative result.
