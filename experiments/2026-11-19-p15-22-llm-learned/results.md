---
title: P15-22 LLM rescoring with the learned commit confidence (and prefix commits) for safe WPM - results
type: experiment
task: P15-22
updated: 2026-11-19
---

# P15-22: LLM rescoring + learned commit confidence (results)

Pre-registration: [plan.md](plan.md), commit `7557b54` (committed and pushed before any stage ran). Code: [`run.py`](run.py) and [`launch.py`](launch.py), commit `9643804` (smoke test on `val_select` subsets only; full pytest 1619 passed, 11 skipped). Aggregates: [`results/results.json`](results/results.json); guard files (configuration + sheet, no text): `results/guard-p15-22-t15-*.json`; hallucination outcome and score-card files (flags only): `results/halluc/`; log: [`results/run.log`](results/run.log). Per-trial decisions and records (with text): `C:\Users\zhang\bci-data\derived\p15-22\` (local only).

Run: 2026-11-19 12:42-12:47 (detached, background class, 4 threads, CPU only, no GPU), 5 min in total; peak private memory 2.53 GB (the LLM loaded on the CPU for the fluency check of prefix texts only, see "Cache misses").

## Verdicts (pre-registered rule)

| id | comparison (v0.1, T15 `val_eval` 701) | A | B (L1) | Δ = B − A | paired 95 % CI | half-width | **verdict** |
|---|---|---|---|---|---|---|---|
| **H1** | L1 (LLM + learned) − R1 (P5-23 learned, n-gram) | 2.64 | **4.91** | +2.27 | [1.76, 2.81] | 0.53 | **L1 beats the other** |
| **H2** | L1 (LLM + learned) − L0 (LLM arm alone, `p_top1`) | 4.18 | **4.91** | +0.73 | [0.19, 1.27] | 0.54 | **L1 beats the other** |

- **L1 safe WPM v0.1 = 4.91, trial-bootstrap 95 % CI [4.25, 5.57]**, status `certified` (LTT α 0.05, δ 0.1, 271 certify items). Held-out wrong-commit rate 13 / 701 = 0.0185, CP95 [0.0099, 0.0315] (safety holds; no clear violation). Both null controls pass (uniform 0 / 300, shuffled 0 / 300).
- **P14-23 (gap 53): closed.** L1 is a certified v0.1 safe WPM above the no-BCI reference 4.02 on all 701 `val_eval` trials, with both controls passing. The lower end of its interval (4.25) is also above 4.02, so it is **clearly above**. This is the first pre-registered `safe-wpm/0.1` value above 4.02 with our causal decoder.
- L0 (the LLM arm alone) gives 4.18 [3.54, 4.83]. It is above 4.02, but its interval includes 4.02, and the plan says that L0 alone never closes P14-23 (its value was known from the exploratory analysis).
- Both learned levers add: the LLM adds +2.27 to the learned guard (H1), and the learned score adds +0.73 to the LLM arm (H2).

## Reference checks
- **L0 reproduces the committed P15-05 M4-13 B1 guard exactly:** 701 / 701 trials with the same action and text (154 commits, 12 wrong).
- Split hashes equal the P5-23 plan: score-fit `285b8c0d9baf5a41`, certify `fadfd84557fcb24b`.
- Row check: the 701 truths equal R1 and R2 row by row (701 / 701 each).
- The frame temperature of all three guards is 2.370158, equal to the committed `ground_prep` value. So all decisions used the committed decodes.
- The bootstrap point values equal the `safe_wpm` values for all 6 paired comparisons.

## Details per arm (T15 `val_eval` 701)

| | R1 P5-23 learned | L0 `llm` | **L1 `llm_learned`** | L2 `llm_prefix` |
|---|---|---|---|---|
| n-best | n-gram | LLM-rescored + grounded | LLM-rescored + grounded | LLM-rescored + grounded |
| commit rule | learned ≥ 0.87 | `p_top1` ≥ 0.77 | learned ≥ 0.82 | learned prefix ≥ 0.90 |
| commits / wrong | 113 / 10 | 154 / 12 | **196 / 13** | 530 / 22 (wrong prefix) |
| error among commits | 0.088 | 0.078 | **0.066** | 0.042 |
| exactly-right top-1 texts | 257 | 327 | 327 | 327 |
| recall of exactly-right top-1 | 0.401 | 0.434 | **0.560** | 0.911 (any prefix) |
| AUROC of the commit score for "top-1 exactly right" | 0.889 | 0.856 | **0.921** | - |
| in-sample LTT commits / wrong | 61 / 8 | 72 / 8 | 86 / 8 | 206 / 8 |
| controls (uniform, shuffled) | 0, 0 | 0, 0 | 0, 0 | 0, 2 (of 300; allowed 15) |
| **safe WPM v0.1** (adopted) | 2.64 [2.14, 3.17] | 4.18 [3.54, 4.83] | **4.91 [4.25, 5.57]** | 1.46 (literal, above α); 2.82 complete commits only |
| safe WPM v0.2 (proposed) | - | 4.18 | 4.91 | **7.14 [6.54, 7.70]** |
| v0.2 + reading cost 0.5 s + 0.3 s/word | - | 4.06 | 4.75 [4.12, 5.37] | **6.75 [6.21, 7.26]** |
| fluent-wrong commits (CP95 of the rate) | - | 6 [0.0031, 0.0185] | 5 [0.0023, 0.0166] | 2 |
| hallucination rate (unsupported shown words) | - | 0 | 0 | 0 |

L2 commits a prefix of 3.14 words on average; 108 of its 530 commits are complete. The top-1 text WER (guard view) is 0.1609 in every LLM arm.

### Secondary paired comparisons (reported, not decided)

| comparison | metric | A | B | Δ | paired 95 % CI |
|---|---|---|---|---|---|
| L0 − R1 | v0.1 | 2.64 | 4.18 | +1.54 | [0.91, 2.17] |
| L2 − R2 (P5-24 prefix) | v0.2 | 4.87 | 7.14 | +2.27 | [1.95, 2.59] |
| L2 − R2 | v0.2 + reading cost | 4.67 | 6.75 | +2.09 | [1.79, 2.38] |
| L2 − L1 | v0.2 + reading cost | 4.75 | 6.75 | +2.00 | [1.60, 2.40] |

### The fitted learned scores (fit + policy-grid items only, 451 items)
- **L1** (216 right top-1 texts among the 451): 7 of 13 features used. Standardised weights: acoustic log-prob per character +1.38, number of words −1.28, word agreement +1.22, n-best entropy −0.72, smallest character confidence +0.46, n-gram LM per word +0.22, frames per character −0.21. Dropped by the sign rule: `p_top1`, `logit_p_top1`, `margin`, `char_conf_mean`, `guard_risk`, `acoustic_gap`.
- **L2** (1,888 prefix rows): 15 of 16 features used; largest: prefix length −1.14, acoustic per character +0.78, n-best entropy −0.55, LM per word +0.53. Dropped: `p_top1`.
- As in P5-23, the acoustic score per character is the strongest signal. After LLM rescoring, `p_top1` adds nothing on top of the other features.

## Hallucination protocol 0.2 check (secondary)
Tracks of P15-07 on the 701 `val_eval` trials. `verify_split`: same trials, null indices and swap permutation as the committed v0.1 T15 split.

| arm | real commits | null | scrambled | swapped unsupported commits (rate, CP95) | n10 / n01 / n11 | upper bound of θ | swapped 0.2 | controls 0.2 |
|---|---|---|---|---|---|---|---|---|
| L0 `llm` | 154 | pass | pass | 0 / 701 (0, [0, 0.0052]) | 154 / 0 / 0 | 0.019 | **pass** | **pass** |
| L1 `llm_learned` | 196 | pass | pass | 0 / 701 (0, [0, 0.0052]) | 196 / 0 / 0 | 0.015 | **pass** | **pass** |
| L2 `llm_prefix` (descriptive) | 530 | pass | pass (1 / 300) | 0 / 701 | 530 / 0 / 0 | 0.006 | pass | pass |

Both fluency modes give the same verdicts. L1 passes every track under protocol 0.2 and commits on 196 of 701 real items (28.0 %). The absolute unsupported swapped-commit rate is 0 with CP95 upper 0.0052 for all three arms, so the "ratio rule only" hole (gap 52, P15-21; the plan wrote "gap 72" by mistake) does not apply to these entries. For L2 the protocol counts a right prefix as a wrong commit (425 of 530), so its fluent-wrong and wrong counts on the card mean nothing; the card is descriptive only, as planned.

## Cache misses
- **Decisions:** 0 new base decodes and 0 live LLM scores in all three arms. Every decision used the committed P15-05 / P15-06 M4-13 caches.
- **Fluency only:** the prefix texts of L2 are not whole n-best texts, so the fluency check scored them live: 14 texts in stage `t15` (wrong prefix commits) and 254 in stage `halluc` (all committed prefixes). The LLM (Qwen2.5-1.5B, CPU) loaded for this; it raised the peak memory to 2.53 GB. These scores do not change any decision.

## Notes and limits
- One participant (T15), one split, one seed. The intervals are conditional on the calibration (decisions fixed); they do not include the calibration draw. T12 was not part of the plan (new gap 93).
- The word decoder used edit 12 (as P15-05, P5-23 and P5-24). The edit-8 rows stay in P14-24 (gap 62).
- The fluent-wrong rate of L1 (5 / 701) is not certified: the joint fluent-wrong bound of P15-06 cannot run with a learned score (gap 74). L1 has fewer fluent-wrong commits than L0 (5 vs 6) with 42 more commits.
- The top-1 text of the guard's n-best and of the pipeline output differ on 9 of 701 trials (692 equal) in every LLM arm. The decisions use the guard's view; the effect on WPM is small but not explained here (new gap 94).
- `safe-wpm/0.2` is still a proposal (P14-26). The L2 numbers (7.14, 6.75 with reading cost) do not count for P14-23.

> **Our take:** this is the first pre-registered result above the gaze-typing reference under the adopted metric: 4.91 [4.25, 5.57] safe WPM against 4.02, with a certified wrong-commit rate and all hallucination controls passing. Two levers that each looked modest add up: the LLM makes more top-1 texts exactly right (327 vs 257), and the learned score commits more of them (56 % vs 43 %) with a lower error among commits. The proposed prefix guard on the same pipeline reaches 6.75 even with a reading cost. The next risk is generalisation: one participant and one split. A T12 replication and a fresh-calibration-draw check would make the claim stronger.
