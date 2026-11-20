---
title: "Frontier write-up E3 (F2): LLM decoding with a grounding check, a hallucination bound and a benchmark"
type: question
tags: [frontier, f2, e3, llm, hallucination, grounding, ltt, benchmark, write-up, negative-result, pre-registration]
sources: []
updated: 2026-11-20
---

# E3 (F2): can an LLM improve decoded text without putting words in the user's mouth?

Write-up for roadmap item [P15-12](roadmap-standard.md#p15-12-frontier-result-write-ups). It joins P15-05 (grounding), P15-06 (bound), P15-14 (T12 bound), P15-07 (benchmark), P15-15 (protocol 0.2) and the M4-13 reruns. Pillar F2 of the [north star](north-star.md#f2-faithful-language-model-decoding-e3).

## Question
An LLM rescores or rewrites the decoder n-best. A run-time check compares the text with the neural evidence (CTC forced alignment). Does the LLM lower WER? Does the check stop text that the signal does not support? Can we state a bound on fluent-wrong commits? Does a benchmark catch systems that follow the language side and ignore the signal?

## Short answer
- **E3 does not pass its pre-registered rule.** S4 (fluent-wrong commits not above the n-gram arm) **fails on both decoders**: M4-12 (2 vs 0) and M4-13 (6 vs 2). On T12 the WER gain does not replicate (S1 fail).
- **LLM rescoring lowers WER on T15** on both decoders: M4-12 0.3985 → 0.3831; M4-13 0.1827 → 0.1617.
- **The grounding check stops every swapped-signal commit** (wrong neural data for the sentence) in every grounded arm, on T15 and T12. It does **not** stop fluent text on the true signal.
- **A certified fluent-wrong bound exists** on T15 (P15-06) and on T12 (P15-14, V-single). On M4-12 it was vacuous (0 commits). On M4-13 it commits 36 sentences, 34 right.
- **First system that passes all tracks** of the hallucination benchmark under protocol 0.2: the M4-13 P15-06 guard (36 real commits, 0 swapped).
- **P15-22 (2026-11-19): the grounded LLM arm is also useful.** B1 + the learned commit score commits 196 of 701 (13 wrong) and gives 4.91 [4.25, 5.57] safe WPM v0.1 for one calibration draw, above gaze typing (4.02). With calibration variation (P15-29, [results](../../experiments/2026-11-20-p15-29-calibration-ci/results.md)) it is 5.18 [0.00, 6.99]: above 4.02 on average, but not reliably. It passes all protocol 0.2 tracks (0 swapped commits, null 0 / 300, scrambled 0 / 300), with 5 fluent-wrong commits (not certified).

## Steps at a glance

| step | pre-registration | design | verdict | result page |
|---|---|---|---|---|
| P15-05 (M4-12, T15 + T12) | [plan](../../experiments/2026-11-16-f2-e3-llm-grounding/plan.md), `2b4fdb8`; T12 addendum before the T12 run | Qwen2.5-1.5B (CPU), 8 arms: n-gram, rescore, lattice rewrite, free rewrite, each with / without grounding; null, shuffled, swapped controls | T15: S1-S3 pass, **S4 fail**; T12: **S1 fail**, S2-S4 pass | [results](../../experiments/2026-11-16-f2-e3-llm-grounding/results.md) |
| P15-06 (M4-12, T15 + T12) | [plan](../../experiments/2026-11-16-p15-06-halluc-bound/plan.md), `7abbff1` (before the held-out runs) | joint LTT of (commit_p, tau_commit, tau_word) on a fluent-wrong loss, alpha_h 0.01, delta_h 0.1 | T15: H1-H4 pass, utility **fail** (0 of 8 right commits kept); T12: **H1 fail** (not certifiable) | [results](../../experiments/2026-11-16-p15-06-halluc-bound/results.md) |
| F2 reruns on M4-13 + V-single (P15-14) | [plan](../../experiments/2026-11-17-f2-m4-13/plan.md), `97a2fc4` (before any M4-13 output) | P15-05 and P15-06 methods unchanged on M4-13; V-single variant on T12 | A: S1-S3 pass, **S4 fail**; B: H1-H4 pass; C: V1-V3 pass, V4 T12 **fail as written** | [results](../../experiments/2026-11-17-f2-m4-13/results.md) |
| P15-07 benchmark 0.1 | (benchmark build; baselines from the saved guards) | null / scrambled / swapped tracks, fluent-wrong metric, scorer, CI re-score of 12 outcome files | done; P14-03 guard fails swapped on T12 | [results](../../experiments/2026-11-16-p15-07-halluc-bench/results.md) |
| P15-15 protocol 0.2 | [plan](../../experiments/2026-11-17-p15-15-halluc-0.2/plan.md), `4e44c23` | paired swapped / real commit-ratio rule (r 0.5, α 0.05, m_min 25) | 10 of 12 entries change verdict; none passes on M4-12; M4-13 B1 passes | [results](../../experiments/2026-11-17-p15-15-halluc-0.2/results.md) |
| P15-22 (M4-13, T15) | [plan](../../experiments/2026-11-19-p15-22-llm-learned/plan.md), `7557b54` | P15-05 B1 + learned commit score (and prefix score); safe WPM primary; protocol 0.2 check secondary | H1 and H2 pass; 4.91 v0.1; protocol 0.2 pass | [results](../../experiments/2026-11-19-p15-22-llm-learned/results.md) |

## P15-05: LLM rescoring with a grounding check

**Pre-registered checks (primary arm B1 = rescore + grounding):**

| check | T15 M4-12 (701) | T12 (400) | T15 M4-13 (701) |
|---|---|---|---|
| S1 WER(B1) < WER(A0), CI below 0 | **pass**: 0.3831 vs 0.3985, [-0.0209, -0.0096] | **fail**: 0.3851 vs 0.3885, [-0.0086, +0.0021] | **pass**: 0.1617 vs 0.1827, [-0.0265, -0.0154] |
| S2 held-out wrong-commit <= 0.05 | **pass**: 0.0029 | **pass**: 0.0200 (15 commits, 8 wrong) | **pass**: 0.0171 [0.0089, 0.0297] |
| S3 controls (uniform, shuffled, swapped) | **pass** (0, 0, 0) | **pass** | **pass** (0, 0, 0) |
| S4 hallucination rate and fluent-wrong <= A0 | **FAIL** (fluent-wrong 2 > 0) | **pass** (4 vs 4) | **FAIL** (fluent-wrong 6 > 2) |
| E3 pass (S1-S4) | **no** | **no** ("safe but no gain") | **no** |

**What the grounding check does and does not do.**
- Swapped signal: without grounding, systems commit the other trial's sentence (M4-12 T15: up to 28 / 701; T12: up to 25 / 400; M4-13 T15: 104-180 / 701). With grounding: **0** in every arm.
- True signal: the 95 % coverage `tau` (0.0806 nats per frame) never changed the top-1 on M4-12 T15. The free rewrite kept unsupported words (56 → 37 of about 4,650).

**Negative results, stated plainly.**
- S4 fails on both T15 decoders. The LLM makes the decoder more confident, so it commits more, and its wrong commits read well. This is the exact F2 risk. On M4-13 rescoring commits 154 with 12 wrong (A0: 104 with 17 wrong), but 6 wrong commits are fluent (A0: 2). S4 compares counts, so an arm that commits more is penalised. We keep the rule as written.
- The T12 WER gain is not significant.

## P15-06 and P15-14: a certified fluent-wrong bound

**Guarantee:** P(fluent-wrong commit rate <= 0.01 and wrong-commit rate <= 0.05) >= 0.9, with exchangeable data and the decoder, LLM and fluent threshold fixed. Method: Learn then Test over 4,284 grid points, fixed-sequence test.

| set / decoder | rule | held-out commits / wrong / fluent-wrong | fluent-wrong rate | verdict |
|---|---|---|---|---|
| T15 M4-12 | primary | 0 / 0 / 0 | 0 [0, 0.0052] | H1-H4 pass; **utility fail** (0 of 8 right commits kept) |
| T15 M4-12 | most_right (secondary) | 8 / 1 / 1 | 0.0014 | bound holds |
| T12 v2 | primary | 0 (commit_p = inf) | 0 | **H1 fail**: 180 test items < 230 needed (0.99^180 = 0.164 > 0.1) |
| T15 M4-13 | primary | **36 / 2 / 1** | 0.0014 [0.0000, 0.0079] | H1-H4 pass; safe but costly (34 of 142 right commits kept, 24 %) |
| T12 v2 | V-single (P15-14) | 3 / 2 / 1 | 0.0025 [0.0001, 0.0138] | V1-V3 pass: certified (0.99^360 = 0.027 <= 0.1); not useful (1 right commit) |

- **New finding (P15-06):** the commit-text gate `tau_commit = 0` ("commit only text that the signal supports at least as well as the acoustic top-1") alone stops all swapped-signal commits, also in arms without the P15-05 grounding.
- **V4 fails as written on T12.** The selections match in 8 / 8 arms, but the `config_id` does not. Cause: only the decoder label in the recipe differs (`__main__` vs the module name). Fixed by P5-21 (`e788029`).

## P15-07 and P15-15: the hallucination benchmark

- **Protocol 0.1 (P15-07, `bdefe45`):** tracks null, scrambled, swapped; pass if commit rate <= 0.05. Null and scrambled: 0 / 300 in all 6 baselines. Swapped: systems without grounding commit as often on swapped as on real input (ratio 1.0). The P14-03 guard fails on T12 (25 / 400, 10 leaks).
- **Defect of 0.1:** a system that rarely commits passes by silence.
- **Protocol 0.2 (P15-15, plan `4e44c23`, code `40922c5`):** a paired swapped / real test (r 0.5, α 0.05, m_min 25) with verdicts pass / fail / insufficient evidence. 10 of 12 committed files change verdict. On M4-12 no baseline passes: the guards that commit rarely now get "insufficient evidence"; T12 P15-05 B0 moves from pass to **fail**.

**M4-13 entries under 0.2 (T15, 701):**

| system | real commits / wrong | swapped commits | n10 / n01 / n11 | swapped verdict | controls |
|---|---|---|---|---|---|
| P15-05 A0 n-gram | 104 / 17 | 104 | 89 / 89 / 15 | fail | **fail** |
| P15-05 B0 rescore | 141 / 10 | 141 | 115 / 115 / 26 | fail | **fail** |
| **P15-06 B1 rescore + G** | **36 / 2** | **0** | 36 / 0 / 0 | **pass** (upper bound 0.080 < 1/3) | **pass** |
| P15-22 L0: B1 + `p_top1` (= P15-05 B1) | 154 / 12 | 0 | 154 / 0 / 0 | **pass** (0.019) | **pass** |
| **P15-22 L1: B1 + learned score** | **196 / 13** | **0** | 196 / 0 / 0 | **pass** (0.015) | **pass** |

P15-22 entries ([results](../../experiments/2026-11-19-p15-22-llm-learned/results.md)): files in `experiments/2026-11-19-p15-22-llm-learned/results/halluc/` (not yet in `benchmark/results/halluc-v0.2/`). Both fluency modes give the same verdicts. The absolute unsupported swapped-commit rate is 0 / 701 (CP95 upper 0.0052).

> **Our take:** the M4-13 B1 guard is the first entry that passes every track. It commits on 5.1 % of real items. The P15-22 L1 guard passes every track too and commits on 28.0 %, but that rate was also not fixed in a P15-16 plan. P15-16 asks for a baseline that commits on "a useful part" of the items, with that rate fixed in a plan first. 5.1 % was never fixed in a plan, so this is evidence for P15-16, not its closure.

## What changed in the library
| change | commit |
|---|---|
| `fidetype.trust.grounding` (CTC forced-alignment check), LLM rescorer interface, `[llm]` extra | `2b4fdb8` |
| `fidetype.trust.halluc_bound` + `calibrate(grounding=, llm=)`: joint LTT, word-level check, guarantee-sheet entry | `7abbff1` |
| `fidetype.benchmark.hallucination` (protocol 0.1), CLI `controls / score / rescore`, CI re-score | `bdefe45` |
| protocol 0.2 default (`paired_swap_test`, `cp_lower`); 0.1 kept and marked old | `40922c5` |
| `halluc_bound.joint_ltt(target_precision=)` (precision as a third risk) | P5-02 (`3dc84bf`) |
| stable trust `config_id` (from the V4 T12 failure) | `e788029` |

## Limits
- One participant per set, one split, one LLM (1.5B, CPU). "Fluent" is judged by the same LLM that rescored.
- Commit counts are small on M4-12 (0-29 of 701); the rates are coarse.
- The fluent threshold and frame temperature were fitted on all of `val_select`, which includes the LTT items (stated in the plan).
- T12 has a weak decoder; its certificate is real but gives 3 commits.

> **Our take:** F2 now has its two main pieces: a run-time check that reliably blocks text from the wrong signal, and a distribution-free bound on fluent-wrong commits. What it does not yet have is the full "never puts words in the user's mouth" property on the true signal at a useful commit rate. The bound buys safety with most of the right commits.

## Still open
| gap | item | what |
|---|---|---|
| 4 | [P15-16](roadmap-standard.md#p15-16-hallucination-benchmark-baseline-that-commits-often-and-checks-the-signal) | a baseline that commits often and passes all tracks |
| 52 | [P15-21](roadmap-standard.md#p15-21-hallucination-benchmark-absolute-bound-on-unsupported-swapped-commits-next-to-the-ratio-rule) | absolute bound on swapped commits next to the ratio rule |
| 93 | [P15-26](roadmap-standard.md#p15-26-t12-replication-of-llm-rescoring--learned-commit-confidence) | T12 replication of P15-22 (LLM + learned score) |
| 62 | [P14-24](roadmap-standard.md#p14-24-f2-and-m4-13-trust-rerun-rows-with-word-decoder-edit-penalty-8) | F2 rows with word-decoder edit penalty 8 |
| 74 | [P5-26](roadmap-standard.md#p5-26-learned-commit-score-with-the-precision-and-hallucination-bounds) | learned commit score with the hallucination bound |

## Rerun
Scripts: `experiments/2026-11-16-f2-e3-llm-grounding/run.py`, `experiments/2026-11-16-p15-06-halluc-bound/` (see its plan), `experiments/2026-11-17-f2-m4-13/run.py`, `experiments/2026-11-16-p15-07-halluc-bench/run.py`, `experiments/2026-11-17-p15-15-halluc-0.2/rescore.py` and `add_m4_13.py`. The benchmark re-score runs in CI: `python -m fidetype.benchmark.hallucination rescore`. The LLM runs need the Qwen2.5-1.5B GGUF file and about 3 GB RAM.

## Related pages
[North star](north-star.md), [M4-13 trust reruns](m4-13-trust-reruns.md), [conformal risk control](../concepts/conformal-risk-control.md), [hallucination benchmark docs](../../docs/hallucination-benchmark.md), [decoder quality write-up](frontier-decoder-quality.md), [safe-WPM write-up](frontier-safe-wpm.md).
