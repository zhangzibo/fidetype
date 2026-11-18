---
title: "Frontier write-up: the path to safe WPM above gaze typing (P14-05 to P14-28)"
type: question
tags: [frontier, safe-wpm, trust, t15, t12, learned-confidence, prefix-commit, metric, write-up, negative-result, pre-registration]
sources: []
updated: 2026-11-18
---

# Safe WPM: can a certified guard beat gaze typing (4.02 WPM) on T15?

Write-up for roadmap item [P15-12](roadmap-standard.md#p15-12-frontier-result-write-ups). It joins P14-05 (metric and baselines), the P14-23 analysis, P5-23 (learned confidence), P14-26 + P5-24 (prefix commits, metric v0.2 proposal) and P14-28 (reading cost). Safe WPM is the user-value test of F1 / F2: words per minute that the guard commits right, with a certified wrong-commit rate and a time penalty for wrong commits ([docs/safe-wpm.md](../../docs/safe-wpm.md)).

## Question
With our causal M4-13 decoder and a certified guard, can safe WPM on T15 `val_eval` (701 trials) go above the no-BCI reference of gaze typing (4.02)?

## Short answer
- **Under the adopted metric `safe-wpm/0.1`: no.** The best pre-registered v0.1 value is 2.64 (learned confidence, P5-23). **v0.1 is still below 4.02.**
- **Under the proposed `safe-wpm/0.2`: yes**, with certified prefix commits: 4.87 [4.43, 5.30] (P5-24), and 4.67 [4.26, 5.07] with a reading cost of 0.5 s + 0.3 s per word per commit (P14-28).
- **v0.2 is PROPOSED, NOT ADOPTED.** The user decides. So gap 53 (P14-23) stays open.
- Every pre-registered gain was smaller than its exploratory estimate.

## Steps at a glance

| step | pre-registration | question | T15 result | verdict | page |
|---|---|---|---|---|---|
| P14-05 | (metric definition + baselines) | metric and baselines on >= 3 tracks | M4-12: 0.00; M4-13 drop-in guard: **2.23**, certified (104 commits, 17 wrong) | done-when met; 2.23 < 4.02 | [results](../../experiments/2026-11-16-p14-05-safe-wpm/results.md) |
| P14-23 | exploratory analysis (`585f099`) | why 2.23, and which levers? | guard factor x 0.319 as large as decoder factor x 0.338 | exploratory only | [bottleneck page](safe-wpm-bottleneck.md) |
| P5-23 | [plan](../../experiments/2026-11-18-p5-23-learned-confidence/plan.md), `52ef14c` | learned commit score vs `p_top1` | **2.64** vs 2.23, +0.42 [0.07, 0.78] | **learned beats current**; still < 4.02 | [results](../../experiments/2026-11-18-p5-23-learned-confidence/results.md) |
| P14-26 + P5-24 | [plan](../../experiments/2026-11-18-p5-24-prefix-commits/plan.md), `00a64ba` | certified word-prefix commits vs the sentence guard (v0.2 proposed) | **4.87** [4.43, 5.30] vs 2.64, +2.22 [1.84, 2.59] | **prefix beats sentence** (under v0.2 only) | [results](../../experiments/2026-11-18-p5-24-prefix-commits/results.md) |
| P14-28 | [plan](../../experiments/2026-11-18-p14-28-reading-cost/plan.md), `691d743` | sensitivity: reading cost per commit, minimum prefix length | 4.67 [4.26, 5.07] at `aac-gaze-v1`; break-even 5.99 s per commit | statement 1 **robust**; 2 **not fragile**; 3 **yes** | [results](../../experiments/2026-11-18-p14-28-reading-cost/results.md) |

## P14-05: the metric and the first numbers
- `safe-wpm/0.1`: only whole right sentences earn words; an entry whose measured wrong-commit rate is above alpha is marked.
- Baselines (alpha 0.05): B2T '25 published decoder + CRC 13.42; our decoder + LTT 4.05 (copy-task track); SpanishBCBL MEG 0.03; Toronto sEMG 0.58 / 0.27 / 0.00; T15 M4-12 + drop-in guard 0.00; T12 v2 1.27; **T15 M4-13 + drop-in guard 2.23** (added 2026-11-17).
- **Negative:** `b2t25-t15-copytask/ours/crc` measured 0.062 > 0.05 and is marked "above alpha".

## P14-23: where the words go (exploratory)
- Decoder: the top-1 is exactly right on 257 of 701 trials (36.7 %). A perfect guard at this decoder gives 7.23.
- Guard: the certified guard commits 87 of the 257. Guard factor 0.319, decoder factor 0.338.
- Correction penalty: small (0.08 WPM).
- Exploratory lever estimates: learned confidence 3.50; LLM features 4.54; prefix commits about 5.4; decoder alone would need PER about 0.072.

## P5-23: a learned commit score
- **Library change:** `calibrate(confidence="learned")`, module `fidetype.trust.commit_score` (13 fixed features, sign-constrained L2 logistic regression, three-way split so the certificate does not leak).

| | T15 current | T15 learned | T12 current | T12 learned |
|---|---|---|---|---|
| safe WPM | 2.23 | **2.64** | 1.27 | 1.87 |
| paired Δ [95 %] | - | +0.42 [0.07, 0.78] | - | +0.60 [−0.18, 1.40] |
| commits / wrong | 104 / 17 | 113 / 10 | 25 / 15 | 31 / 15 |
| AUROC for "top-1 exactly right" | 0.834 | 0.889 | 0.844 | 0.920 |
| controls (uniform, shuffled) | 0 / 300, 0 / 300 | 0 / 300, 0 / 300 | 0 / 300, 0 / 300 | 0 / 300, 0 / 300 |

- Verdict (T15 decides): **learned beats current.** T12: **no clear difference** (interval includes 0).
- **Negative:** 2.64 is far below the exploratory 3.50 and below 4.02.

## P14-26 + P5-24: certified prefix commits and the v0.2 proposal
- **Library change:** `calibrate(confidence="learned", commit_unit="prefix")` commits the longest certified word prefix; `safe_wpm(metric_version="0.2")`. The [v0.2 proposal](../../docs/safe-wpm-v0.2-proposal.md) credits a right prefix with its k words and penalises a wrong prefix.

| set | arm | v0.1 (adopted) | v0.2 (proposed) |
|---|---|---|---|
| T15 | current (`p_top1`) | 2.23 | 2.23 |
| T15 | sentence (learned) | 2.64 | 2.64 |
| T15 | prefix, v0.1 literal | 0.53 (**above alpha**, 421 / 701) | **4.87** [4.43, 5.30] |
| T15 | prefix, v0.1 complete only | 1.03 | - |
| T12 | prefix | 0.00 | 4.76 [3.84, 5.78] |

- T15 prefix guard: 465 commits (421 prefix + 44 complete), 13 wrong (0.0185 [0.0099, 0.0315]), 1,073 right words; controls 0 / 300 and 1 / 300 (allowed 15).
- **Negative results, stated plainly.** Under v0.1 the prefix guard is **worse** than the sentence guard (paired Δ complete-only − sentence = −1.62 [−2.07, −1.19]). 39 % of the T15 prefix commits are one word. T12 wrong-commit 0.0475 is close to alpha (CP interval includes 0.05).

## P14-28: reading cost and minimum prefix length (sensitivity)
- Re-scores the fixed P5-24 decisions. No new fitting or decisions. The P5-24 verdict does not change.

| T15 cell | prefix safe WPM v0.2 | commits |
|---|---|---|
| 0 s, m = 1 | 4.87 [4.43, 5.30] | 465 |
| `aac-gaze-v1` (0.5 s + 0.3 s/word), m = 1 | **4.67 [4.26, 5.07]** | 465 |
| KLM M + reading 238 wpm, m = 1 | 4.55 [4.16, 4.94] | 465 |
| `aac-gaze-v1`, m = 2 | 3.94 [3.51, 4.36] | 284 |
| `aac-gaze-v1`, m = 3 | 2.97 [2.54, 3.41] | 164 |

- Break-even to 4.02 (m = 1): 5.99 s per commit, or 2.52 s per word.
- **Negative:** a minimum prefix of 2 words drops below 4.02 at `aac-gaze-v1` (3.94). On T12 the break-even is lower (2.78 s per commit).
- Recommendation in the proposal (for the user's weekend decision): adopt v0.2 **with** the 0.5 s + 0.3 s/word reading cost; keep m = 1.

## What changed in the library
| change | commit |
|---|---|
| `fidetype.benchmark.safe_wpm` (`safe-wpm/0.1`), benchmark column | `7d74c0f` |
| `fidetype.trust.commit_score`, `calibrate(confidence="learned")` | `52ef14c` |
| `commit_unit="prefix"`, `safe_wpm(metric_version="0.2")`, v0.2 proposal (not adopted) | `00a64ba` |
| `read_s_per_commit`, `read_s_per_word`, `min_prefix_words` (defaults change nothing; refused with v0.1) | `691d743` |

## Limits
- One participant per set, one split, one seed. The intervals are conditional on the calibration (decisions fixed).
- The prefix feature set was designed after the exploratory analysis, which looked at `val_eval`. The score was fitted and certified on `val_select` only.
- The reading costs come from literature values, not from measured BCI users (gap 77).
- One commit per trial. Word-by-word streaming commits were not tested (gap 76).

> **Our take:** the guard, not only the decoder, decides user value. Prefix commits are the largest pre-registered gain so far, but only if a right prefix counts as typed text. The metric decision (P14-26) now decides which guard is better for a user. We keep v0.1 as the headline until the user adopts v0.2.

## Still open
| gap | item | what |
|---|---|---|
| 53 | [P14-23](roadmap-standard.md#p14-23-t15-safe-wpm-above-the-no-bci-reference-with-our-causal-decoder) | T15 safe WPM above 4.02 (open: v0.1 below; v0.2 not adopted) |
| 76 | [P5-27](roadmap-standard.md#p5-27-word-by-word-streaming-prefix-commits-within-a-trial) | word-by-word streaming prefix commits |
| 77 | [P14-29](roadmap-standard.md#p14-29-measured-checking-time-per-commit-for-aac-and-bci-users) | measured checking time per commit |
| 69 | [P15-22](roadmap-standard.md#p15-22-llm-rescoring-with-learned-and-prefix-confidence-for-safe-wpm) | LLM rescoring with learned and prefix confidence |
| 73, 74 | [P5-25](roadmap-standard.md#p5-25-online-re-calibration-for-a-guard-with-a-learned-commit-score), [P5-26](roadmap-standard.md#p5-26-learned-commit-score-with-the-precision-and-hallucination-bounds) | learned score with online re-calibration and with the precision / hallucination bounds |
| 70 | [P14-27](roadmap-standard.md#p14-27-cost-of-causal-smoothing-on-t15-and-the-decoder-accuracy-target) | decoder accuracy target |

## Rerun
Scripts: `experiments/2026-11-16-p14-05-safe-wpm/run.py`, `experiments/2026-11-18-p5-23-learned-confidence/run.py`, `experiments/2026-11-18-p5-24-prefix-commits/run.py`, `experiments/2026-11-18-p14-28-reading-cost/run.py`, through the isolation wrapper (`.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I <script>`). They need the local M4-13 and T12 v2 log-probs.

## Related pages
[Safe WPM bottleneck](safe-wpm-bottleneck.md), [decoder quality write-up](frontier-decoder-quality.md), [E3 write-up](frontier-e3-hallucination.md), [north star](north-star.md).
