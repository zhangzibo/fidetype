---
title: Safe WPM bottleneck on T15 (P14-23) - decomposition and levers
type: question
tags: [safe-wpm, trust, t15, m4-13, confidence, prefix-commit, llm, metric, exploratory]
sources: []
updated: 2026-11-18
---

# Why is T15 safe WPM 2.23, and what would bring it above 4.02?

**Question (gap 53 = [P14-23](roadmap-standard.md#p14-23-t15-safe-wpm-above-the-no-bci-reference-with-our-causal-decoder)):** our causal M4-13 decoder + the drop-in guard gives a certified [safe WPM](../../docs/safe-wpm.md) of 2.23 on T15 `val_eval` (701 trials). Gaze typing gives 4.02. Which factors cause the gap, and which levers close it?

**Short answer (exploratory):** the guard, not the decoder, is the main limit. The decoder gets the whole sentence exactly right on 257 of 701 trials (36.7 %), but the certified guard commits only 87 of them. A perfect guard at this decoder would give 7.23. Three levers each reach about 3.5 to 5.5 in offline estimates: a learned confidence score, LLM rescoring, and word-prefix commits. The prefix lever needs a new metric version. Decoder accuracy alone would need PER about 0.07 (now 0.121). All gains below are exploratory. Each one must pass a pre-registered test before we claim it.

## Method
- **Data (read only, existing outputs):** M4-13 log-probs of `val_select` (722) and `val_eval` (701); the 10-best lists of the B2T '25 word decoder (lm 1.0, edit 12, bonus 3) from the P15-05 cache; the cached LLM sentence scores of P15-05; the P14-05 guard `tcfg-1016759f08a3f9a1`. No decoding, no LLM run and no GPU were needed.
- **Check:** the replayed guard gives the committed P14-05 decisions on all 701 / 701 `val_eval` trials (same action, text and `p_top1`). The P15-05 trial order matches (701 / 701).
- **Rule:** every fitted choice uses `val_select` only. For a new score we fit on 451 `val_select` items and run LTT (alpha 0.05, delta 0.1, exact binomial, fixed sequence) on the other 271. `val_eval` is for reporting only.
- **Code and outputs:** local scratch scripts; aggregates and per-trial tables in `C:\Users\zhang\bci-data\derived\p14-23-analysis\` (local only, they hold text). CPU only, background class, 4 threads; the runs took about 1 minute each.

> **Update 2026-11-18 (P5-23, pre-registered):** lever C1 as a library option (`calibrate(confidence="learned")`, three-way split, no certificate leak) gives **2.64** on T15 `val_eval` (p_top1 guard 2.23; paired difference +0.42 [0.07, 0.78]; 113 commits, 10 wrong; AUROC 0.889), not the exploratory 3.50. T12 replication: 1.87 vs 1.27, interval includes 0. [Results](../../experiments/2026-11-18-p5-23-learned-confidence/results.md).

> **Update 2026-11-18 (P5-24, pre-registered):** lever A1 as a library option (`calibrate(confidence="learned", commit_unit="prefix")`) gives **4.87** [4.43, 5.30] on T15 `val_eval` under the **proposed** [safe-wpm v0.2](../../docs/safe-wpm-v0.2-proposal.md) (465 commits, 13 wrong; sentence-level learned guard 2.64; prefix beats sentence), not the exploratory 5.43. Under v0.1 the same guard gives 0.53 (literal, above alpha) or 1.03 (complete commits only). v0.2 is not adopted, so P14-23 stays open. [Results](../../experiments/2026-11-18-p5-24-prefix-commits/results.md).

## 1. Decomposition at the certified guard

| factor | `val_select` (calibration) | `val_eval` (report) |
|---|---|---|
| trials / words (mean per trial) | 722 / 4,751 (6.58) | 701 / 4,675 (6.67) |
| P(top-1 sentence exactly right) | 0.380 | **0.367** (257 trials) |
| truth anywhere in the 10-best | 0.566 | 0.535 |
| commit rate at the certified threshold (0.73) | 0.173 (125) | **0.148** (104) |
| error among commits | 0.136 (17) | **0.163** (17) |
| share of exactly-right trials that commit (recall) | 0.394 | **0.339** (87 of 257) |
| words per right commit | 5.69 | 5.79 |
| mean trial window (`neural_s`) | 18.19 s | **18.68 s** |
| mean active-speech span (first to last non-blank CTC frame) | 11.90 s | **12.11 s** |
| mean time to the first non-blank frame | 3.56 s | 3.61 s |
| mean rate-model time (159.65 chars/min, T15 copy task) | 12.37 s | 12.48 s |
| neural time / correction time | 218.9 / 7.6 min | 218.3 / 8.2 min |
| **safe WPM (`safe-wpm/0.1`)** | 2.71 (in-sample) | **2.23** (trial bootstrap 1.78-2.74, conditional) |
| no correction penalty | 2.80 | 2.31 |
| speech-span time instead of the trial window | 4.07 | 3.37 (2.69-4.14) |
| rate-model time | 3.92 | 3.27 |
| no-BCI reference | 4.00 | 4.02 |

### Where the words go (`val_eval`, trial-window time)

| step | safe WPM | factor |
|---|---|---|
| every word typed, perfect decoder and guard | 21.42 | - |
| x share of words in exactly-right top-1 sentences | 7.23 | x 0.338 (decoder) |
| x share of those words that the certified guard commits | 2.31 | x 0.319 (guard) |
| - correction penalty (17 wrong commits, 8.2 min) | **2.23** | - 0.08 |

- **The guard factor (0.32) is as large as the decoder factor (0.34).** The guard throws away about two thirds of the exactly-right sentences, because its score cannot separate them from the wrong ones at alpha 0.05.
- **The correction penalty is small** (0.08 WPM). Wrong commits matter mostly because they force a strict threshold, not because of their time.
- **Timing costs a factor of 1.51.** The trial window holds about 3.6 s before speech starts and some time after it. Speech-span time gives 3.37, rate-model time 3.27. This is a measurement choice, not a system gain. The no-BCI reference (4.02) does not change.
- **Sentence-level credit hides most right words.** The right prefixes of the top-1 sentences hold 2,688 words (57.5 % of all words). The exactly-right sentences hold 1,579 (33.8 %). `safe-wpm/0.1` credits only whole sentences.

### What a sentence-level guard needs (v0.1, trial-window time)
To reach 4.02 at today's decoder, the guard must commit about 918 right words: about 159 right sentences, which is 62 % of the 257 exactly-right trials (today 34 %). With about 21 wrong commits (3 % of trials, inside alpha 0.05) that is a commit rate of about 0.26 and an error among commits of about 0.12 (today 0.148 and 0.163).

## 2. Levers (offline estimates on existing outputs)

All values are `val_eval` safe WPM, certified by LTT on 271 `val_select` items, trial-window time, unless the row says otherwise. The intervals are conditional trial-bootstrap 95 % intervals with the decisions fixed. **Split noise:** the plain guard score on our 271-item LTT split gives 2.77 (139 commits, 27 wrong), not 2.23. So compare the learned scores with 2.77 as well.

| id | lever | safe WPM `val_eval` | gain vs 2.23 | commits (wrong) | effort | GPU | metric change |
|---|---|---|---|---|---|---|---|
| C1 | learned confidence score, no LLM (logistic regression on `p_top1`, n-best softmax, margin, word agreement, char confidence, acoustic log-prob per frame, LM per word, length, guard risk) | **3.50** [2.92, 4.04] | +1.27 | 168 (30) | S (CPU, days) | no | no |
| C2 | learned confidence score with 2 LLM features | **4.54** [3.92, 5.12] | +2.31 | 194 (23) | M (LLM at run time, about 3 GB RAM) | no | no |
| B1 | committed P15-05 arms, scored with v0.1 (own certified guards): B1 rescore + G / C1 lattice rewrite + G / D1 free rewrite + G | **4.18 / 4.69 / 4.77** | +1.95 to +2.55 | 154 (12) / 176 (18) / 179 (18) | none (already run) | no | no |
| B2 | LLM-rescored top-1 + learned non-LLM confidence | 4.50 [3.89, 5.08] | +2.27 | 175 (14) | M | no | no |
| A1 | word-prefix commits with a learned prefix confidence, no LLM | **5.43** (sentence penalty) / 5.55 (prefix penalty) | +3.2 | 505 prefixes (23 wrong); 1,242 right words | M (CPU) | no | **yes (v0.2)** |
| A2 | prefix commits on the LLM-rescored n-best | 4.76 / 4.81 | +2.5 | 318 (8) | M | no | yes |
| T | speech-span time instead of the trial window | 3.37 | x 1.51 | 104 (17) | S | no | yes (timing field) |
| K | LTT on all 722 `val_select` items instead of 271 (same score) | 2.82 | +0.05 vs 2.77 | 141 (27) | S | no | no |
| D | decoder accuracy only (guard as today) | 4.02 needs P(exact) 0.66, WER about 0.105, PER about 0.072 | - | - | L | **yes** | no |
| E | centred instead of causal smoothing (upper bound: all of the PER gap 0.121 to 0.101) | about 2.9 (speech time 4.4) | at most +0.7 | - | M (retrain) | **yes** | no; breaks the real-time rule |

**Ceilings at today's decoder:** perfect sentence guard 7.23 (speech time 11.16); perfect guard on the LLM-rescored top-1 9.29; perfect prefix guard 12.31 (speech time 19.00).

### Notes per lever
- **(c) Confidence.** The guard's `p_top1` has AUROC 0.83 for "top-1 exactly right" on `val_eval`. The learned score without LLM features has 0.87; with LLM features 0.94. A softmax over the 10-best alone (3.13 with LLM rescoring, 2.55 without) and the n-best word agreement alone (2.71) do not help. The guard risk is informative (AUROC 0.78 when reversed, on the 451-item fit part), but the commit gate does not use it (`max_guard_risk` 1.0). Added to `p_top1` alone it gives 2.90.
- **(b) LLM rescoring.** It raises P(exact) from 0.367 to 0.462 (WER 0.183 to 0.162, P15-05). With the committed P15-05 guards, three arms are already above 4.02 under v0.1. This was not pre-registered for safe WPM, and the margin over 4.02 is inside the usual half-width (about 0.5). The LLM run needs about 3 GB RAM (P15-05 peak 2.96 GB).
- **(a) Prefix commits.** A posterior from the 10-best alone cannot certify prefixes: when all 10 candidates share a prefix, its mass is 1.0 even if the truth is not in the list, and LTT finds no feasible threshold. A learned prefix confidence (prefix mass, position, char confidence, word agreement, sentence score) is feasible and gives the largest gain. It needs a metric version that credits right prefixes and defines the cost of a wrong prefix.
- **(d) Accuracy needed.** Model: at a fixed guard recall and error mix, safe WPM scales with P(exact). We map P(exact) to WER with a log-linear fit on 5 T15 points (M4-12, and the A0, B0, C, D arms on M4-13) and WER to PER with a line through M4-12 and M4-13. With a perfect guard, today's decoder is already enough (P(exact) 0.20 would do). With speech-span time, the fixed-recall target is P(exact) 0.44 (WER about 0.164, PER about 0.109).
- **(e) Causal vs centred.** M4-13 is 0.020 PER behind the published decoder. Even if centred smoothing explains all of it, the estimate is about +0.7. This is a measurement of the real-time rule's cost, not a lever we can ship.

> **Our take:** the path above 4.02 does not need the GPU. The cheapest real gain is a better guard score (C1), and the largest is prefix commits (A1). Both are CPU work on the trust layer. LLM rescoring stacks with both, but it costs RAM and run time. Decoder work (D, E) waits for the GPU (P11-01) and gives less per hour.

> **Our take:** safe WPM v0.1 is strict in two ways that are not about safety: it times the whole trial window, and it gives no credit for a right prefix. A v0.2 that fixes both must be pre-registered and reported next to v0.1, never in its place without notice.

## Limits
- **Exploratory.** We compared more than 12 variants and looked at `val_eval` for each. The ranking can contain selection effects. No number here is a claim.
- **Certificate leakage.** The guard's `p_top1` (a feature) was fitted on `val_select` items that overlap our 271-item LTT split. A clean test needs a three-way split fixed in a pre-registration.
- One participant, one split; conditional intervals only. Speech span comes from our own CTC output, not from measured speech times.
- The penalty for a wrong prefix is our proposal (2 s + 0.79 s per committed char), next to the v0.1 rule (whole sentence).

## Recommended order (registered as new gaps)

| order | gap | item | expected (exploratory) | cost |
|---|---|---|---|---|
| 1 | 66 | [P14-26](roadmap-standard.md#p14-26-safe-wpm-v02-proposal-prefix-credit-and-a-speech-time-field) safe-wpm v0.2 proposal: prefix credit, wrong-prefix cost, speech-time field (pre-registered; v0.1 stays the headline) | enables A1 and T | S, CPU, docs + scorer |
| 2 | 67 | [P5-23](roadmap-standard.md#p5-23-learned-commit-confidence-score-for-the-drop-in-guard) learned commit-confidence score for the drop-in guard | 2.2 to about 3.5 (v0.1) | S-M, CPU |
| 3 | 68 | [P5-24](roadmap-standard.md#p5-24-certified-prefix-commits-in-the-trust-guard) certified prefix commits in the trust guard | about 5.4 (v0.2) | M, CPU |
| 4 | 69 | [P15-22](roadmap-standard.md#p15-22-llm-rescoring-with-learned-and-prefix-confidence-for-safe-wpm) LLM rescoring with learned and prefix confidence for safe WPM | 4.2-4.8 (v0.1); more with prefixes | M, CPU, about 3 GB RAM |
| 5 | 70 | [P14-27](roadmap-standard.md#p14-27-cost-of-causal-smoothing-on-t15-and-the-decoder-accuracy-target) cost of causal smoothing on T15 and the decoder accuracy target | at most +0.7 | M, **GPU** (after P11-01) |

## Related pages
- [Safe WPM definition](../../docs/safe-wpm.md), [P14-05 results](../../experiments/2026-11-16-p14-05-safe-wpm/results.md), [P14-21 results](../../experiments/2026-11-17-p14-21-edit8-rows/results.md)
- [M4-13 trust reruns](m4-13-trust-reruns.md), [F2 reruns on M4-13](../../experiments/2026-11-17-f2-m4-13/results.md)
- [Lookahead vs accuracy](lookahead-latency-accuracy.md), [open gaps](open-gaps.md), [roadmap](roadmap-standard.md)
