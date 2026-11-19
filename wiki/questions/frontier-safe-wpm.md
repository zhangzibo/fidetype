---
title: "Frontier write-up: the path to safe WPM above gaze typing (P14-05 to P15-22)"
type: question
tags: [frontier, safe-wpm, trust, t15, t12, learned-confidence, prefix-commit, streaming, llm, metric, write-up, negative-result, pre-registration]
sources: []
updated: 2026-11-19
---

# Safe WPM: can a certified guard beat gaze typing (4.02 WPM) on T15?

Write-up for roadmap item [P15-12](roadmap-standard.md#p15-12-frontier-result-write-ups). It joins P14-05 (metric and baselines), the P14-23 analysis, P5-23 (learned confidence), P14-26 + P5-24 (prefix commits, metric v0.2 proposal), P14-28 (reading cost), P5-27 (streaming word-by-word commits) and P15-22 (LLM rescoring + learned confidence). Safe WPM is the user-value test of F1 / F2: words per minute that the guard commits right, with a certified wrong-commit rate and a time penalty for wrong commits ([docs/safe-wpm.md](../../docs/safe-wpm.md)).

## Question
With our causal M4-13 decoder and a certified guard, can safe WPM on T15 `val_eval` (701 trials) go above the no-BCI reference of gaze typing (4.02)?

## Short answer
- **Under the adopted metric `safe-wpm/0.1`: yes, since P15-22 (2026-11-19).** LLM rescoring with grounding (P15-05 B1) plus the learned commit score (P5-23) gives **4.91 [4.25, 5.57]**, certified, 13 / 701 wrong commits, both controls pass. The lower end of the interval is above 4.02. **Gap 53 (P14-23) is closed.**
- Before P15-22 the best pre-registered v0.1 value was 2.64 (learned confidence on the n-gram n-best, P5-23).
- **Under the proposed `safe-wpm/0.2`:** prefix commits on the same LLM pipeline give 7.14 [6.54, 7.70], and 6.75 [6.21, 7.26] with a reading cost of 0.5 s + 0.3 s per word per commit (P15-22 secondary). On the n-gram n-best: 4.87 (P5-24) and 4.67 (P14-28). **v0.2 is PROPOSED, NOT ADOPTED.** The user decides.
- Every pre-registered gain before P15-22 was smaller than its exploratory estimate. P15-22 (4.91) was larger than its estimate (about 4.50).
- **Streaming word-by-word commits (P5-27) do not help safe WPM:** 2.34 [2.11, 2.57] against 4.67 for the one-commit prefix guard (both v0.2 + reading cost). They commit right words about 10 s earlier.
- Limit: one participant (T15), one split, one seed. A T12 replication and a second calibration draw are open (gap 93).

## Steps at a glance

| step | pre-registration | question | T15 result | verdict | page |
|---|---|---|---|---|---|
| P14-05 | (metric definition + baselines) | metric and baselines on >= 3 tracks | M4-12: 0.00; M4-13 drop-in guard: **2.23**, certified (104 commits, 17 wrong) | done-when met; 2.23 < 4.02 | [results](../../experiments/2026-11-16-p14-05-safe-wpm/results.md) |
| P14-23 | exploratory analysis (`585f099`) | why 2.23, and which levers? | guard factor x 0.319 as large as decoder factor x 0.338 | exploratory only | [bottleneck page](safe-wpm-bottleneck.md) |
| P5-23 | [plan](../../experiments/2026-11-18-p5-23-learned-confidence/plan.md), `52ef14c` | learned commit score vs `p_top1` | **2.64** vs 2.23, +0.42 [0.07, 0.78] | **learned beats current**; still < 4.02 | [results](../../experiments/2026-11-18-p5-23-learned-confidence/results.md) |
| P14-26 + P5-24 | [plan](../../experiments/2026-11-18-p5-24-prefix-commits/plan.md), `00a64ba` | certified word-prefix commits vs the sentence guard (v0.2 proposed) | **4.87** [4.43, 5.30] vs 2.64, +2.22 [1.84, 2.59] | **prefix beats sentence** (under v0.2 only) | [results](../../experiments/2026-11-18-p5-24-prefix-commits/results.md) |
| P14-28 | [plan](../../experiments/2026-11-18-p14-28-reading-cost/plan.md), `691d743` | sensitivity: reading cost per commit, minimum prefix length | 4.67 [4.26, 5.07] at `aac-gaze-v1`; break-even 5.99 s per commit | statement 1 **robust**; 2 **not fragile**; 3 **yes** | [results](../../experiments/2026-11-18-p14-28-reading-cost/results.md) |
| P5-27 | [plan](../../experiments/2026-11-18-p5-27-streaming-prefix/plan.md), `5f74c2f` | streaming append-only prefix commits vs the one-commit prefix guard (v0.2 + reading cost + several-commits rule, all proposed) | **2.34** [2.11, 2.57] vs 4.67, −2.32 [−2.63, −2.02] | **single beats stream** (safe, certified) | [results](../../experiments/2026-11-18-p5-27-streaming-prefix/results.md) |
| **P15-22** | [plan](../../experiments/2026-11-19-p15-22-llm-learned/plan.md), `7557b54` | LLM rescoring (P15-05 B1) + learned commit score vs P5-23 learned (H1) and vs the LLM arm alone (H2), v0.1 | **4.91** [4.25, 5.57] vs 2.64 (+2.27 [1.76, 2.81]) and vs 4.18 (+0.73 [0.19, 1.27]) | **both pass; first v0.1 value > 4.02**; closes P14-23 | [results](../../experiments/2026-11-19-p15-22-llm-learned/results.md) |

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

## P5-27: streaming word-by-word prefix commits
- The guard decodes the causal M4-13 output every 6 frames (0.48 s) and may add words to its commit (append-only). One LTT threshold is certified on the trial loss "any commit of the trial is wrong" (calibration as P5-24).
- Result (T15 `val_eval` 701, PROPOSED v0.2 + reading cost + the proposed several-commits rule, section 7 of the proposal):

| | stream | one-commit prefix guard |
|---|---|---|
| safe WPM [95 % CI] | 2.34 [2.11, 2.57] | **4.67** [4.26, 5.07] |
| committing trials / commit events | 310 / 446 | 465 / 465 |
| wrong trials | 5 / 701 (0.0071) | 13 / 701 (0.0185) |
| right words | 528 | 1,073 |
| complete commits | 0 | 44 |
| median latency of right words after the true word ends | **1.44 s** | 11.20 s |

- **Negative:** the threshold is strict (0.99 against 0.94), the guard commits about 1.7 words early in a trial (median 31 % of the trial) and never extends the commit at the end. The P5-24 score streamed without refit passes LTT only at 1.00 (no commits).
- Follow-up: a hybrid guard (stream mid-trial + the P5-24 decision at the end, certified jointly): gap 92 = [P5-28](roadmap-standard.md#p5-28-hybrid-streaming-and-end-of-trial-prefix-guard).

## P15-22: LLM rescoring + the learned commit score
- Pipeline: the P15-05 arm B1 (n-gram n-best, then Qwen2.5-1.5B rescoring with weight 1.0, then the CTC grounding check), with all values fixed from the committed P15-05 M4-13 rerun. All decisions came from the committed caches (0 new decodes, 0 live LLM scores). CPU only, 5 min.
- Arms: L0 = B1 + `p_top1` (reproduces the committed P15-05 B1 guard, 701 / 701), **L1 = B1 + `confidence="learned"`** (primary), L2 = B1 + learned prefix score (secondary, v0.2).

| arm | commits / wrong | error among commits | recall of exactly-right top-1 | v0.1 | v0.2 + reading cost |
|---|---|---|---|---|---|
| P5-23 learned (n-gram) | 113 / 10 | 0.088 | 103 / 257 | 2.64 [2.14, 3.17] | - |
| L0 LLM, `p_top1` | 154 / 12 | 0.078 | 142 / 327 | 4.18 [3.54, 4.83] | 4.06 |
| **L1 LLM + learned** | **196 / 13** | **0.066** | **183 / 327** | **4.91 [4.25, 5.57]** | 4.75 [4.12, 5.37] |
| L2 LLM + learned prefix | 530 / 22 (wrong prefix) | 0.042 | 298 / 327 (any prefix) | 1.46 literal (above α) | **6.75** [6.21, 7.26] |

- Two levers multiply: the LLM makes more top-1 texts exactly right (327 against 257 of 701), and the learned score commits a larger share of them with a lower error among commits. The P14-23 analysis said a sentence guard needs about 159 right commits for 4.02; L1 has 183.
- Hallucination protocol 0.2: L0 and L1 pass all tracks (0 swapped commits, null 0 / 300, scrambled 0 / 300). Fluent-wrong commits: L1 5, L0 6 (not certified; gap 74).
- The edit-8 word decoder (gap 62) and T12 (gap 93) were not part of the plan.

## What changed in the library
| change | commit |
|---|---|
| `fidetype.benchmark.safe_wpm` (`safe-wpm/0.1`), benchmark column | `7d74c0f` |
| `fidetype.trust.commit_score`, `calibrate(confidence="learned")` | `52ef14c` |
| `commit_unit="prefix"`, `safe_wpm(metric_version="0.2")`, v0.2 proposal (not adopted) | `00a64ba` |
| `read_s_per_commit`, `read_s_per_word`, `min_prefix_words` (defaults change nothing; refused with v0.1) | `691d743` |
| `fidetype.trust.stream_commit`, `unit="stream-prefix"`, `safe_wpm(..., n_commits=)` (proposed extension, not adopted) | `5f74c2f` |
| no library change in P15-22 (experiment script only: P15-05 pipeline + `calibrate(confidence="learned")`) | `9643804` |

## Limits
- One participant per set, one split, one seed. The intervals are conditional on the calibration (decisions fixed).
- The prefix feature set was designed after the exploratory analysis, which looked at `val_eval`. The score was fitted and certified on `val_select` only.
- The reading costs come from literature values, not from measured BCI users (gap 77).
- Word-by-word streaming commits (P5-27) were tested on T15 only; T12 was not run (loader memory; gap 92).

> **Our take:** the guard, not only the decoder, decides user value. With the LLM pipeline and the learned score, a sentence guard beats gaze typing under the adopted v0.1 metric (4.91). Prefix commits on the same pipeline give more (6.75 with reading cost), but only if a right prefix counts as typed text; the metric decision (P14-26) decides that. We keep v0.1 as the headline until the user adopts v0.2. The claim rests on one participant; the T12 replication (gap 93) is the next check.

## Still open
| gap | item | what |
|---|---|---|
| 93, 94 | [P15-26](roadmap-standard.md#p15-26-t12-replication-of-llm-rescoring--learned-commit-confidence), [P15-27](roadmap-standard.md#p15-27-guard-n-best-top-1-differs-from-the-pipeline-top-1-on-9-of-701-trials) | T12 replication + second calibration draw of P15-22; guard vs pipeline top-1 on 9 trials |
| 62 | [P14-24](roadmap-standard.md#p14-24-f2-and-m4-13-trust-rerun-rows-with-word-decoder-edit-penalty-8) | LLM-arm rows with edit 8 |
| 92 | [P5-28](roadmap-standard.md#p5-28-hybrid-streaming-and-end-of-trial-prefix-guard) | hybrid streaming + end-of-trial prefix guard (P5-27 follow-up; gap 76 closed) |
| 77 | [P14-29](roadmap-standard.md#p14-29-measured-checking-time-per-commit-for-aac-and-bci-users) | measured checking time per commit |
| 73, 74 | [P5-25](roadmap-standard.md#p5-25-online-re-calibration-for-a-guard-with-a-learned-commit-score), [P5-26](roadmap-standard.md#p5-26-learned-commit-score-with-the-precision-and-hallucination-bounds) | learned score with online re-calibration and with the precision / hallucination bounds |
| 70 | [P14-27](roadmap-standard.md#p14-27-cost-of-causal-smoothing-on-t15-and-the-decoder-accuracy-target) | decoder accuracy target |

## Rerun
Scripts: `experiments/2026-11-16-p14-05-safe-wpm/run.py`, `experiments/2026-11-18-p5-23-learned-confidence/run.py`, `experiments/2026-11-18-p5-24-prefix-commits/run.py`, `experiments/2026-11-18-p14-28-reading-cost/run.py`, `experiments/2026-11-18-p5-27-streaming-prefix/run.py` (stages `views`, `evaluate`, `verdict`), `experiments/2026-11-19-p15-22-llm-learned/run.py all` (or `launch.py`, detached; needs the P15-05 M4-13 caches), through the isolation wrapper (`.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I <script>`). They need the local M4-13 and T12 v2 log-probs.

## Related pages
[Safe WPM bottleneck](safe-wpm-bottleneck.md), [decoder quality write-up](frontier-decoder-quality.md), [E3 write-up](frontier-e3-hallucination.md), [north star](north-star.md).
