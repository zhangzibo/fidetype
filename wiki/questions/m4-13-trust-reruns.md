---
title: M4-13 trust reruns - do the guarantees become useful with a stronger decoder?
type: question
tags: [trust, guarantees, m4-13, precision, update-gate, hallucination, f1, f2, pre-registration]
sources: []
updated: 2026-11-18
---

# M4-13 trust reruns: do the guarantees become useful with a stronger decoder?

**Question:** our trust results were safe but useless on the M4-12 decoder: top-1 was right on only 59 of 701 T15 sentences, so the guards almost never committed. M4-13 halves the phoneme error rate (val_eval greedy PER 0.121, see [lookahead vs accuracy](lookahead-latency-accuracy.md)). Do the same pre-registered trust methods now give useful operating points?

**Short answer:** mostly yes on T15, not yet on T12, and one real defect appeared. Precision and hallucination guarantees now commit many mostly-right sentences on T15. The update gate keeps the guarantee but does not keep the better decoder when the user gives only partial feedback.

All four reruns were pre-registered in commit `97a2fc4` before any M4-13 output existed. They ran in one hidden CPU queue on 2026-11-17 (no GPU). Verdicts follow the pre-registered rules; other analyses are marked exploratory on the result pages.

## Results at a glance (T15 val_eval, 701 held-out sentences)

| question | M4-12 (before) | M4-13 (now) | pre-registered verdict | result page |
|---|---|---|---|---|
| Precision guarantee ("when it types, it is right"), target 0.5 | no threshold certified, 0 commits | certified; 104 commits, 17 wrong, precision 0.837 [0.751, 0.902] | P1-P3 pass; useful at 0.5 | [P5-02 rerun](../../experiments/2026-11-17-p5-02-precision-m4-13/results.md) |
| Precision target 0.8 / 0.9 / 0.95 | infeasible | still infeasible | vacuous (valid) | same |
| Update gate: better decoder accepted | (not testable: no discordant pairs) | 4 / 4 runs | H1 pass | [P15-03a](../../experiments/2026-11-17-p15-03-f1-m4-13/results.md) |
| Update gate: worse and broken decoders refused | broken accepted (dry run) | refused with an oracle user; **accepted** with the feedback-r0.3 user (2 / 2 seeds) | H2, H3 **fail** | same |
| Wrong-commit bound through updates | held | 0.0055-0.0082 per run (alpha 0.05) | H4 pass | same |
| LLM rescoring + grounding (P15-05) | WER 0.3985 -> 0.3831; 10 commits | WER 0.1827 -> 0.1617; 154 commits, 12 wrong | S1-S3 pass, S4 fail (fluent-wrong 6 > 2) | [F2 reruns](../../experiments/2026-11-17-f2-m4-13/results.md) |
| Fluent-wrong bound (P15-06) | 0 commits (vacuous) | 36 commits, 34 right; fluent-wrong 1 / 701 | H1-H4 pass; safe but costly (34 of 142 right commits kept) | same |
| Hallucination benchmark 0.2 (swapped-signal track) | "insufficient evidence" (no commits) | P15-06 guard passes all tracks: 36 real commits, 0 swapped | first pass under 0.2 | [P15-15](../../experiments/2026-11-17-p15-15-halluc-0.2/results.md#m4-13-t15) |

## T12 (V-single variant of P15-06)
- The primary P15-06 rule cannot certify on T12: 180 test items, and alpha_h 0.01 at delta_h 0.1 needs at least 230 (0.99^180 = 0.164 > 0.1).
- The pre-registered variant V-single tests one fixed order on all 360 non-fit items (0.99^360 = 0.027). It certifies a configuration in all 8 arms (V1 pass). Held out (400): B1 fluent-wrong 0.0025, wrong-commit 0.0050, all controls 0 (V2, V3 pass).
- The certificate is real but not useful: B1 commits 3 sentences, 1 right. T12 needs a stronger decoder.
- V4 (reproduce the committed primary T12 guard) fails as written: the selections match in 8 / 8 arms, but the `config_id` does not. An exploratory check shows that the only difference is the decoder label in the recipe (`__main__` vs the imported module name).

## What we learned
1. **Decoder strength was the main limit for precision and hallucination guarantees.** The methods did not change; only the decoder log-probs did. On T15 the guards now commit 5-22 % of sentences at 84-94 % precision ([P5-02 rerun](../../experiments/2026-11-17-p5-02-precision-m4-13/results.md), [F2 reruns](../../experiments/2026-11-17-f2-m4-13/results.md)).
2. **The update gate has a defect that a stronger decoder does not fix.** With partial feedback, unknown truth counts as wrong for both decoders. Most check pairs are then "both wrong", the sign test sees 1-6 discordant pairs, and it accepts the worse M4-12 and the time-reversed decoder. A per-item PER test separates them clearly (p about 3e-9), but only with the truth of all items ([P15-03a](../../experiments/2026-11-17-p15-03-f1-m4-13/results.md)).
3. **Safety holds everywhere.** Every held-out wrong-commit and fluent-wrong rate stays under its alpha, every null / shuffled / swapped control passes, and every ledger verifies.
4. **Certificates can cost much utility.** The fluent-wrong bound keeps only 24 % of the right commits (most_right rule: 37 %). Precision targets of 0.8 or more are not yet certifiable with 271 LTT items.

> **Our take:** this is the first evidence that the trust stack is useful, not only safe, on a public intracortical set (T15). The next levers differ by result: more calibration items or per-word commits for high precision targets; a feedback-aware non-inferiority test for the update gate; a stronger T12 decoder for T12 usefulness.

## Gap decisions (see [open gaps](open-gaps.md))

| gap | item | decision | reason |
|---|---|---|---|
| 3 | P5-08 non-vacuous precision bound | **closed** | target 0.5 certified on held-out T15 with 104 commits; error 0.163 <= 0.5 (CP95 upper 0.249) |
| 1 | P15-13 update gate: PER / non-inferiority test | open, unblocked | H3 read: fails with the feedback-r0.3 user; the code change is still to do, and its replay must use partial feedback |
| 2 | P15-14 certified T12 hallucination bound | **closed** | V-single certifies on T12 (alpha_h 0.01, delta_h 0.1); held-out fluent-wrong 0.0025; not useful (3 commits) |
| 14 | P15-19 usefulness on stronger decoders | open, in progress | M4-13 evidence for P5-02, P15-02 (via P15-03a) and P15-06; still needed: P5-01 on M4-13 and all four on the P11 decoders |
| 58 (new) | P5-20 certified precision >= 0.8 | new | 0.8 / 0.9 / 0.95 infeasible on M4-13 |
| 59 (new) | P5-21 trust `config_id` independent of the decode-function label | new | same configuration, different id when a script is imported instead of run (V4 T12) |

## Related pages
- [Open gaps](open-gaps.md), [roadmap](roadmap-standard.md), [north star](north-star.md) (pillars F1, F2)
- [Lookahead vs accuracy and latency](lookahead-latency-accuracy.md) (the M4-13 decoder)
- [F1 guarantee scope](f1-guarantee-scope.md)
- Queue plan: [trust reruns on M4-13](../../experiments/2026-11-17-trust-reruns-m4-13/plan.md)
