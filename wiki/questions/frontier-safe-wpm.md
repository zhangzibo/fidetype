---
title: "Frontier write-up: the path to safe WPM above gaze typing (P14-05 to P15-22, P5-28)"
type: question
tags: [frontier, safe-wpm, trust, t15, t12, learned-confidence, prefix-commit, streaming, llm, metric, write-up, negative-result, pre-registration]
sources: []
updated: 2026-11-23
---

# Safe WPM: can a certified guard beat gaze typing (4.02 WPM) on T15?

Write-up for roadmap item [P15-12](roadmap-standard.md#p15-12-frontier-result-write-ups). It joins P14-05 (metric and baselines), the P14-23 analysis, P5-23 (learned confidence), P14-26 + P5-24 (prefix commits, metric v0.2 proposal), P14-28 (reading cost), P5-27 (streaming word-by-word commits) and P15-22 (LLM rescoring + learned confidence). Safe WPM is the user-value test of F1 / F2: words per minute that the guard commits right, with a certified wrong-commit rate and a time penalty for wrong commits ([docs/safe-wpm.md](../../docs/safe-wpm.md)).

## Question
With our causal M4-13 decoder and a certified guard, can safe WPM on T15 `val_eval` (701 trials) go above the no-BCI reference of gaze typing (4.02)?

## Short answer

> **Decision (user, 2026-11-22): `safe-wpm/0.2` is ADOPTED** ([docs/safe-wpm.md](../../docs/safe-wpm.md) sections 6a and 6b), with the reading cost (0.5 s + 0.3 s per word per commit), calibration-inclusive intervals with K >= 80 calibration draws, and partition-only draws. The numbers below were computed before the adoption and keep their labels: "adopted v0.1" and "proposed v0.2" describe the status at the time of each result. No old number is re-labelled. The code switch (scorer default, leaderboard column) was roadmap item [P14-61](roadmap-standard.md#p14-61-switch-the-scorer-and-the-leaderboard-to-the-adopted-safe-wpm-v02) (gap 196). Done 2026-11-23: the default is `metric_version="0.2"` with the reading cost; the leaderboard shows v0.2 as the headline column and v0.1 as a second column; `calibration_draw_interval` warns when K < 80 or the draws are not stated as partition-only. For a sentence-level entry the v0.2 value is a little lower than its v0.1 value (reading time), for example the T15 M4-13 guard card 4.07 -> 3.94.

- **Under the adopted metric `safe-wpm/0.1`: on average yes, but not reliably (P15-29, 2026-11-20).** LLM rescoring with grounding (P15-05 B1) plus the learned commit score (P5-23) gives **4.91 [4.25, 5.57]** for one calibration draw (P15-22), certified, 13 / 701 wrong commits, both controls pass. This interval resamples only the test trials; it does not include the calibration-draw variation. **Gap 53 (P14-23) is closed.**
- **With the calibration variation (P15-29, pre-registered, K = 40 draws):** **5.18 [0.00, 6.99]**. The mean is above 4.02; the lower end is **not**. 2 of the 40 draws are above alpha on the test set and earn 0 by the pre-registered rule. The 38 certified draws give 3.50–6.82; 36 of 40 draws are above 4.02. Variants that were not pre-registered also have lower ends below 4.02: 5.52 [3.61, 7.11] and 5.45 [3.60, 7.01] ([P15-29 results](../../experiments/2026-11-20-p15-29-calibration-ci/results.md)). Next: gap 132 ([P15-34](roadmap-standard.md#p15-34-calibration-inclusive-t15-safe-wpm-lower-end-above-gaze-typing)).
- Before P15-22 the best pre-registered v0.1 value was 2.64 (learned confidence on the n-gram n-best, P5-23).
- **Under the proposed `safe-wpm/0.2`:** prefix commits on the same LLM pipeline give 7.14 [6.54, 7.70], and 6.75 [6.21, 7.26] with a reading cost of 0.5 s + 0.3 s per word per commit (P15-22 secondary). On the n-gram n-best: 4.87 (P5-24) and 4.67 (P14-28). **v0.2 was PROPOSED, NOT ADOPTED at the time; adopted 2026-11-22** (with the reading cost, K >= 80 draws, partition-only draws).
- Every pre-registered gain before P15-22 was smaller than its exploratory estimate. P15-22 (4.91) was larger than its estimate (about 4.50).
- **Streaming word-by-word commits (P5-27) do not help safe WPM:** 2.34 [2.11, 2.57] against 4.67 for the one-commit prefix guard (both v0.2 + reading cost). They commit right words about 10 s earlier.
- **A hybrid guard (P5-28) keeps the words and most of the latency gain:** stream commits mid-trial + the P5-24 end decision that can extend them, certified jointly, give 4.89 [4.49, 5.27] against 4.67 (v0.2 + reading cost; Δ +0.22 [+0.14, +0.31], pre-registered verdict **hybrid beats single**). The first right word appears a median 2.7 s after it ends, against 14.0 s. Caution: with δ split over three mid thresholds the WPM gain disappears (4.63).
- **Replication (P15-26, pre-registered):** on T15 the result **replicates** over four new calibration draws: 5.58, 6.00, 5.23 and 5.83 safe WPM v0.1, all certified, all with the CI lower end above the no-BCI reference. The P15-22 value (4.91) is the lowest of the five T15 draws (mean 5.51, SD 0.44). **On T12 it does not replicate:** 2.37 [1.34, 3.62] against 4.11. The T12 decoder gets only 35 of 400 top-1 texts exactly right (WER 0.385). P15-29 (40 draws) later showed a wider spread than these four draws. So the claim is now: **above gaze typing on T15 on average (about 5.2), but not reliably once calibration variation is counted (interval 0.0–7.0); not on T12.**
- **EMG headline (decided by the user, 2026-11-22):** EMG typing with the trust layer is above the no-BCI baseline after calibration uncertainty, narrowly, for one sentence guard (BX3, safe-WPM v0.1: **5.90 [3.45, 8.89]** vs 3.09; replicated **5.99 [3.52, 8.96]** with safety headroom 0.0107 in P11-28), on 8 users and one test set ([P11-19 results](../../experiments/2026-11-21-p11-19-multi-split/results.md), [P11-28 results](../../experiments/2026-11-22-p11-28-bx3-headroom/results.md)). Short form: "EMG: above no-BCI, narrowly, for one sentence guard (8 users, one test set)." The EMG prefix guard result 5.67 [3.43, 8.26] (P11-21) holds only under the proposed safe-WPM v0.2. See the P11-19 and P11-28 bullets below.
- **EMG (P11-14, P11-17), earlier guard:** the P11-14 L-FL guard gives 6.80 [4.49, 9.63] with one calibration draw. Once the calibration draw is counted (P11-17, pre-registered, K = 40) it gives **5.00 [0.00, 9.55]** against no-BCI 3.09 ([P11-17 results](../../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md)). So this guard is above no-BCI on average, but not reliably: 9 of 40 draws are above alpha on the test set and earn 0. See the P11-17 section below. The L-FL guard runs on the P11-07 FL decoder: causal, in-beam char LM plus a lexicon term, 10.88 % CER (P11-07 primary F: 10.10 %). Its matched published reference is 6.95 % (with LM), not 11.28 %, and it is above the usability line of about 10 % CER ([matched-target rule](frontier-decoder-quality.md#matched-emg-decoder-target-p11-25-2026-11-21), P11-25).

## Steps at a glance

| step | pre-registration | question | T15 result | verdict | page |
|---|---|---|---|---|---|
| P14-05 | (metric definition + baselines) | metric and baselines on >= 3 tracks | M4-12: 0.00; M4-13 drop-in guard: **2.23**, certified (104 commits, 17 wrong) | done-when met; 2.23 < 4.02 | [results](../../experiments/2026-11-16-p14-05-safe-wpm/results.md) |
| P14-23 | exploratory analysis (`585f099`) | why 2.23, and which levers? | guard factor x 0.319 as large as decoder factor x 0.338 | exploratory only | [bottleneck page](safe-wpm-bottleneck.md) |
| P5-23 | [plan](../../experiments/2026-11-18-p5-23-learned-confidence/plan.md), `52ef14c` | learned commit score vs `p_top1` | **2.64** vs 2.23, +0.42 [0.07, 0.78] | **learned beats current**; still < 4.02 | [results](../../experiments/2026-11-18-p5-23-learned-confidence/results.md) |
| P14-26 + P5-24 | [plan](../../experiments/2026-11-18-p5-24-prefix-commits/plan.md), `00a64ba` | certified word-prefix commits vs the sentence guard (v0.2 proposed) | **4.87** [4.43, 5.30] vs 2.64, +2.22 [1.84, 2.59] | **prefix beats sentence** (under v0.2 only) | [results](../../experiments/2026-11-18-p5-24-prefix-commits/results.md) |
| P14-28 | [plan](../../experiments/2026-11-18-p14-28-reading-cost/plan.md), `691d743` | sensitivity: reading cost per commit, minimum prefix length | 4.67 [4.26, 5.07] at `aac-gaze-v1`; break-even 5.99 s per commit | statement 1 **robust**; 2 **not fragile**; 3 **yes** | [results](../../experiments/2026-11-18-p14-28-reading-cost/results.md) |
| P5-27 | [plan](../../experiments/2026-11-18-p5-27-streaming-prefix/plan.md), `5f74c2f` | streaming append-only prefix commits vs the one-commit prefix guard (v0.2 + reading cost + several-commits rule, all proposed) | **2.34** [2.11, 2.57] vs 4.67, −2.32 [−2.63, −2.02] | **single beats stream** (safe, certified) | [results](../../experiments/2026-11-18-p5-27-streaming-prefix/results.md) |
| P5-28 | [plan](../../experiments/2026-11-19-p5-28-hybrid-prefix/plan.md), `e3cb0cb` | hybrid: stream commits mid-trial (λ_mid 0.99) + P5-24 end decision (λ_end 0.94, joint LTT on the trial loss) vs the one-commit prefix guard (v0.2 + reading cost + several-commits rule, all proposed) | **4.89** [4.49, 5.27] vs 4.67, +0.22 [+0.14, +0.31] | **hybrid beats single** (safe, certified); Bonferroni sensitivity: no clear difference | [results](../../experiments/2026-11-19-p5-28-hybrid-prefix/results.md) |
| **P15-22** | [plan](../../experiments/2026-11-19-p15-22-llm-learned/plan.md), `7557b54` | LLM rescoring (P15-05 B1) + learned commit score vs P5-23 learned (H1) and vs the LLM arm alone (H2), v0.1 | **4.91** [4.25, 5.57] vs 2.64 (+2.27 [1.76, 2.81]) and vs 4.18 (+0.73 [0.19, 1.27]) | **both pass; first v0.1 value > 4.02** (one calibration draw); closes P14-23 | [results](../../experiments/2026-11-19-p15-22-llm-learned/results.md) |
| **P15-26** | [plan](../../experiments/2026-11-19-p15-26-replication/plan.md), `39e9419` | replication of P15-22: four T15 calibration draws + T12 | T15: 5.58, 6.00, 5.23, 5.83 (all > 4.02, CI lower ends > 4.02); T12: 2.37 vs 4.11 | **T15 replicates (4 / 4); T12 does not replicate** | [results](../../experiments/2026-11-19-p15-26-replication/results.md) |
| **P15-29** | [plan](../../experiments/2026-11-20-p15-29-calibration-ci/plan.md), `d7169cf` | interval that includes the calibration draw (two-level bootstrap, K = 40 T15 draws, 20 T12 draws) | T15 **5.18 [0.00, 6.99]**; T12 1.05 [0.00, 3.18] | T15 **above, but inside the combined interval** (lower end not above 4.0153); T12 not above | [results](../../experiments/2026-11-20-p15-29-calibration-ci/results.md) |

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
- Follow-up: the hybrid guard of P5-28 (next section).

## P5-28: hybrid streaming + end-of-trial prefix guard
Pre-registered ([plan](../../experiments/2026-11-19-p5-28-hybrid-prefix/plan.md), `e3cb0cb`; [results](../../experiments/2026-11-19-p5-28-hybrid-prefix/results.md), `c359eb6`). The hybrid commits mid-trial with the P5-27 streaming score (λ_mid 0.99, fixed) and decides again at the trial end with the P5-24 prefix score. The end decision can extend the early commit. λ_end (0.94) is certified by LTT on the trial loss with the mid-trial commits on. T15 `val_eval` 701, PROPOSED v0.2 + reading cost + several-commits rule:

| | hybrid | one-commit prefix guard | stream (P5-27) |
|---|---|---|---|
| safe WPM [95 % CI] | **4.89** [4.49, 5.27] | 4.67 [4.26, 5.07] | 2.34 [2.11, 2.57] |
| committing trials / commit events | 500 / 803 | 465 / 465 | 310 / 446 |
| wrong trials | 18 / 701 (0.0257) | 13 / 701 (0.0185) | 5 / 701 (0.0071) |
| right words | 1,143 | 1,073 | 528 |
| median latency of right words | 3.85 s | 11.20 s | **1.44 s** |
| median latency of the first right word | 2.72 s | 14.00 s | 2.08 s |

- Verdict: **hybrid beats single** (Δ +0.22 [+0.14, +0.31], hw 0.08; controls 0 / 300 and 0 / 300; certified). Non-inferior (margin 0.25). Earlier (H3).
- The hybrid commits in every trial that the single arm commits (465 / 465) plus 35 more. The end decision extended a mid-trial commit in 167 trials.
- **Caution:** λ_mid 0.99 came from P5-27 on the same certify items. With δ split over λ_mid ∈ {0.99, 0.98, 0.97} (Bonferroni), λ_end rises to 0.95 and the value is 4.63, Δ −0.04 [−0.15, +0.08]: no clear difference. The T12 replication with λ_mid fixed in advance is gap 95 = [P5-29](roadmap-standard.md#p5-29-t12-replication-of-the-streaming-and-hybrid-prefix-guards).

> **Our take:** the hybrid gives the user text while they still speak (first right word about 11 s earlier) at no loss of safe WPM. The WPM gain itself is small and not yet robust. The same hybrid on the P15-22 LLM pipeline (prefix 6.75 with reading cost) is a natural next step.

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

## P15-26: replication over calibration draws and on T12
- Same L1 pipeline and rules as P15-22. Each T15 draw refits the frame temperature, τ and λ on its own calibration set. Draw c0 (the P15-22 split) reproduced P15-22 exactly (701 / 701 decisions).

| unit | L1 safe WPM v0.1 [95 % CI] | no-BCI | commits / wrong | L1 − n-gram learned guard | test A (level) | test G (gain) |
|---|---|---|---|---|---|---|
| c0 = P15-22 | 4.91 [4.25, 5.57] | 4.02 | 196 / 13 | +2.27 | - | - |
| c1 (seed 1) | 5.58 [4.91, 6.28] | 4.02 | 221 / 16 | +2.91 [2.35, 3.49] | pass | pass |
| c2 (seed 2) | 6.00 [5.28, 6.72] | 4.02 | 245 / 23 | +2.32 [1.74, 2.93] | pass | pass |
| c3 (seed 3) | 5.23 [4.58, 5.92] | 4.02 | 211 / 16 | +2.20 [1.66, 2.73] | pass | pass |
| p1 (pooled re-split) | 5.83 [5.12, 6.56] | 4.00 | 253 / 29 | +2.38 [1.80, 2.98] | pass | pass |
| **T12** | **2.37** [1.34, 3.62] | 4.11 | 31 / 12 | +0.50 [0.05, 1.13] | **fail** | **fail** (no clear difference) |

- **Negative result, stated plainly:** the P15-22 claim does not transfer to T12. The guard is certified and safe there (12 / 400 wrong, protocol 0.2 pass), but the T12 decoder is too weak.
- The between-draw SD on T15 (0.44) is about two thirds of the conditional CI half-width. The reported CIs do not include the calibration draw (new gap 103, P15-29). P15-29 then measured it: see the next section.
- T12 prefix guard (proposed v0.2 + reading cost): 4.95 [4.04, 5.92]; not decided.

## P15-29: interval that includes the calibration draw
- Two-level bootstrap: 40 T15 calibration draws (full guard recalibration) x 2,000 trial resamples of `val_eval` ([results](../../experiments/2026-11-20-p15-29-calibration-ci/results.md)).
- **T15: 5.18 [0.00, 6.99]**, against no-BCI 4.0153. The lower end is 0.00 because 2 of 40 draws (k30, k38) are above alpha on the test set and earn 0. The 38 certified draws: mean 5.45, SD 0.79, range 3.50–6.82. 36 of 40 draws are above 4.02.
- Variants that were not pre-registered: above-alpha draws keep their value 5.52 [3.61, 7.11]; certified draws only 5.45 [3.60, 7.01]. Both lower ends are below 4.02.
- T12: 1.05 [0.00, 3.18], not above 4.11.
- The single-draw CI 4.91 [4.25, 5.57] is still a correct number for that one guard. It does not answer "what does a new calibration give?".
- Reporting rule: [docs/safe-wpm.md](../../docs/safe-wpm.md) section 6b proposes calibration-inclusive reporting. It was **proposed, not adopted** at the time; **adopted 2026-11-22** with v0.2 (K >= 80 draws, partition-only draws).

## P11-17: the same interval for the EMG guard
- Same two-level method on the EMG P11-14 L-FL guard: K = 40 calibration draws (new splits and resamples of the 1,224 calibration prompts) x user-cluster bootstrap over the 8 test users ([results](../../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md); pre-registration `7922ecf`, code `eecbac8`, results `a0993be`).
- **EMG: 5.00 [0.00, 9.55]**, against no-BCI 3.09. Pre-registered verdict: "above, but inside the combined interval". The single-calibration P11-14 CI was 6.80 [4.49, 9.63]. The code check reproduces P11-14 exactly (285 commits, 52 wrong, 6.8031).
- 9 of 40 draws (22.5 %) are above alpha on the test set (62–76 wrong commits, rate 0.051–0.062). They are the draws that commit the most (301–339 commits). Each earns 0. LTT allows this in at most delta = 10 % of draws. The 31 certified draws: mean 6.46, range 1.14–7.27. All null controls pass in every draw.
- Between-draw SD 2.94, within-draw SD 1.19. Library `calibration_draw_interval` (prompt-level inner level): 5.00 [0.00, 7.84]. Variants that were not pre-registered: above-alpha draws keep their value 6.63 [1.87, 9.88]; certified draws only 6.46 [1.42, 9.74]. No lower end is above 3.09.
- The benchmark card `emg2qwerty__p11-14-intended-lfl-subset8__guard` is unchanged. It is a correct single-calibration value under the adopted v0.1.
- P11-18 ([results](../../experiments/2026-11-21-p11-18-emg-above-alpha/results.md)): with partition-only draws (no bootstrap duplicates) 3 of 40 draws are above alpha and the interval is 5.65 [0.00, 9.45], so the claim stays "above 3.09 on average, not reliably", and a clear val / test session shift remains (gap 164).
- P11-20 ([results](../../experiments/2026-11-21-p11-20-emg-shift-robust/results.md)): a shift margin from two earlier sessions (m = 0.0045, LTT at alpha' 0.0455) gives 0 of 40 draws above alpha on test and the interval 6.13 [2.62, 9.47], so the claim stays "above 3.09 on average, not reliably" (gaps 169, 170).
- P11-23 ([results](../../experiments/2026-11-21-p11-23-shift-margin-steps/results.md)): a margin from several session steps (m2 = 0.0185, alpha'' 0.0314) shows that the one-step margin under-states the spread; 0 of 40 draws are above alpha on test and the interval is 5.47 [2.44, 8.77], so the claim does not change (gap 173).
- P11-21 ([results](../../experiments/2026-11-21-p11-21-lx-margin/results.md); plan `95b1a91`, amendment 1 `99b7eb6`, results `ecbc7b1`): the LX-FL **prefix** guard with partition-only draws and an LX-specific shift margin (m_LX 0.0288, alpha_LX 0.0212) gives **5.67 [3.43, 8.26]** against 3.09. Pre-registered verdict: "clearly above after calibration uncertainty". This is the first EMG lower end above 3.09. 0 of 40 draws are above alpha, all are certified, and the null controls give 0. The margin is narrow: the lower end clears 3.09 by 0.34, and one draw is 2.96. LX-T (L-FL margin) 7.21 [4.78, 10.43]; LX-P (no margin) 8.80 [4.89, 12.26] with 1 / 40 above alpha (fragile); H3: LX-P 1 / 40 vs P11-16 7 / 40, Fisher p = 0.028. **It holds only under the PROPOSED `safe-wpm/0.2` (the user decides adoption) and under assumption (A2).** Disclosed deviation: check X2 failed on small memo differences (gap 180) and Amendment 1 replaced it with the fresh-decode check X2' before any margin or arm number; X2' passes. This result is not the public EMG headline: on 2026-11-22 the user adopted the BX3 sentence-guard headline under v0.1 (see the P11-19 bullet and the short answer).
- P11-19 ([results](../../experiments/2026-11-21-p11-19-multi-split/results.md); plan `c71c9bc`, amendments `445c714`, `c3df8ad`, results `749f192`): the **L-FL sentence** guard with 3 Bonferroni split guards per draw (each at delta / 3, P11-23 margin alpha'' 0.0314) and selection of the split guard with the highest in-sample value (arm BX3, primary, calibration data only) gives **5.90 [3.45, 8.89]** against 3.09 under the **adopted v0.1** (sentence commits, so v0.1 = v0.2). Pre-registered verdict: "clearly above after calibration uncertainty". 0 of 40 draws are above alpha; null controls give 0. The pass is narrow: the lower end clears 3.09 by 0.36 (normal approximation [3.10, 8.70]). The median arm BD3 5.19 [2.90, 8.19] and AND arm AN3 4.37 [2.17, 7.28] do not clear 3.09. Safety cost: BX3 test rate mean 0.028, max 0.0434; 13 / 40 draws above 0.0314, none above 0.05 (gap 183). It holds under assumption (A2), on 8 users and one test set; the interval method (6b) is still proposed. The user adopted this result as the EMG headline on 2026-11-22: "EMG typing with the trust layer is above the no-BCI baseline after calibration uncertainty, narrowly, for one sentence guard (BX3, safe-WPM v0.1: 5.90 [3.45, 8.89] vs 3.09; replicated 5.99 [3.52, 8.96] with safety headroom 0.0107 in P11-28), on 8 users and one test set."
- P11-28 ([results](../../experiments/2026-11-22-p11-28-bx3-headroom/results.md); plan `84d465f`, amendment 1 `bf06ee9`, results `75ae30f`): 40 new BX3 draws pooled with the 40 of P11-19. Verdict: "BX3 safety holds with headroom". 0 / 80 draws have a test wrong-commit rate above 0.05 (CP95 0.0368); the 90th-percentile bound is 0.0393, so the headroom is 0.0107. The value replicates: new 40 draws 5.99 [3.52, 8.96], pooled 5.95 [3.49, 8.92] vs 3.09. 31 / 80 draws are above alpha'' 0.0314. It holds on one test set of 8 users (gap 193).

> **Our take:** EMG now shows the same calibration-variance problem as T15, and more strongly (22.5 % vs 5 % of draws above alpha). Possible causes are bootstrap duplicates in the LTT part, test-rate noise and the val / test session shift. Gap 158 ([P11-18](roadmap-standard.md#p11-18-why-225--of-the-emg-calibration-draws-are-above-alpha)) separates them with partition-only draws. Gap 159 ([P11-19](roadmap-standard.md#p11-19-lower-variance-emg-l-fl-guard-with-a-calibration-inclusive-lower-end-above-no-bci)) tries a lower-variance guard.

## P15-34 and P15-37: can the guard lower the calibration variance?
- P15-37 (2026-11-21): guarantee-keeping multi-split guards (AND, Bonferroni + selection) do not lift the T15 lower end (primary BMED-3 4.73 [2.60, 6.24]); K = 120 of the P15-29 settings gives 5.26 [2.94, 6.91]; about 2,760 calibration items (3.8 x `val_select`) would be needed ([results](../../experiments/2026-11-21-p15-37-multi-split/results.md)).
- P15-40 (2026-11-21): sub-sampling `val_select` gives between-draw SDs 1.234 / 1.089 / 0.884 at n = 361 / 481 / 722 and the exponent b_D2 = 0.48 [0.12, 0.83], consistent with 1/sqrt(n); the revised projection is about 2,520 [1,080, 460,000] calibration items ([results](../../experiments/2026-11-21-p15-40-sqrt-n-check/results.md)).
- The multi-split rules cut the between-draw SD by only 4-15 %. With K = 40, the same P15-29 settings gave lower ends of 0.00 (P15-29), 4.05 (P15-34) and 2.95 (P15-37).
- Gaps 132 and 141 are closed on their "numbers say why" branches. The criterion (lower end above 4.0153) was not met. The goal continues in gap 160 ([P15-39](roadmap-standard.md#p15-39-labelled-t15-like-calibration-data-for-the-calibration-inclusive-safe-wpm), new labelled data, externally blocked).

## What changed in the library
| change | commit |
|---|---|
| `fidetype.benchmark.safe_wpm` (`safe-wpm/0.1`), benchmark column | `7d74c0f` |
| `fidetype.trust.commit_score`, `calibrate(confidence="learned")` | `52ef14c` |
| `commit_unit="prefix"`, `safe_wpm(metric_version="0.2")`, v0.2 proposal (not adopted) | `00a64ba` |
| `read_s_per_commit`, `read_s_per_word`, `min_prefix_words` (defaults change nothing; refused with v0.1) | `691d743` |
| `fidetype.trust.stream_commit`, `unit="stream-prefix"`, `safe_wpm(..., n_commits=)` (proposed extension, not adopted) | `5f74c2f` |
| `fidetype.trust.hybrid_commit` (mid-trial stream score + end prefix score, joint LTT on the trial loss); fix: an infeasible certification switches off mid-trial commits | `e3cb0cb`, `c359eb6` |
| no library change in P15-22 (experiment script only: P15-05 pipeline + `calibrate(confidence="learned")`) | `9643804` |

## Limits
- The P15-22 / P15-26 intervals are conditional on the calibration (decisions fixed). P15-29 includes the calibration draw: T15 5.18 [0.00, 6.99], so the T15 headline holds on average only, not reliably. T12 does not replicate. The same holds for the EMG P11-14 guard (P11-17): 5.00 [0.00, 9.55] against 3.09. The adopted EMG headline (BX3, P11-19 / P11-28) is narrow and rests on 8 users and one test set, under assumption (A2).
- The prefix feature set was designed after the exploratory analysis, which looked at `val_eval`. The score was fitted and certified on `val_select` only.
- The reading costs come from literature values, not from measured BCI users (gap 77).
- Word-by-word streaming commits (P5-27) and the hybrid guard (P5-28) were tested on T15 only; no T12 checkpoint views exist (gap 95). The P5-28 mid threshold came from P5-27 on the same certify items.

> **Our take:** the guard, not only the decoder, decides user value. With the LLM pipeline and the learned score, a sentence guard beats gaze typing on average under the adopted v0.1 metric (4.91 for one draw; 5.18 mean over 40 draws). It does not yet beat it reliably: with calibration variation the interval contains 4.02 (P15-29). Prefix commits on the same pipeline give more (6.75 with reading cost), but only if a right prefix counts as typed text; the metric decision (P14-26) decides that. We keep v0.1 as the headline until the user adopts v0.2. The claim rests on one participant; the T12 replication (gap 93) is the next check.

## Still open
| gap | item | what |
|---|---|---|
| 160 | [P15-39](roadmap-standard.md#p15-39-labelled-t15-like-calibration-data-for-the-calibration-inclusive-safe-wpm) | calibration-inclusive T15 lower end above 4.0153 with new labelled calibration data (externally blocked; gap 103 closed by P15-29, gaps 132 and 141 closed by P15-34 / P15-37 on their "numbers say why" branches, criterion not met) |
| 173 | [P11-24](roadmap-standard.md#p11-24-tell-the-two-emg-shift-margins-apart-on-held-out-users-or-new-sessions) | tell the two EMG shift margins apart (m = 0.0045 vs m2 = 0.0185) on held-out users or new sessions (gaps 164 and 170 closed by P11-20 / P11-23; may be externally limited by data) |
| 169 | [P11-22](roadmap-standard.md#p11-22-firm-duplicates-verdict-for-the-emg-l-fl-calibration-draws) | firm "duplicates" verdict for the EMG calibration draws (bootstrap vs partition-only; low priority) |
| 193 | [P11-29](roadmap-standard.md#p11-29-bx3-safety-headroom-on-a-new-session-or-test-set) | BX3 safety headroom on a new session or test set (gap 183 closed by P11-28: 0 / 80 above 0.05, headroom 0.0107 on one test set; low priority) |
| 180 | [P11-27](roadmap-standard.md#p11-27-native-n-best-score-differences-in-the-p11-20--p11-23-analyser-memos) | why the P11-20 / P11-23 memos hold native n-best scores up to 8e-5 off fresh decodes (203 / 2,442 windows; P11-19: also between processes, up to 3e-8 in the signals, no action changed in X1'; P11-28: L-model parameters differ by about 1e-8, no decision changed in X5; low priority) |
| 62 | [P14-24](roadmap-standard.md#p14-24-f2-and-m4-13-trust-rerun-rows-with-word-decoder-edit-penalty-8) | LLM-arm rows with edit 8 |
| 95 | [P5-29](roadmap-standard.md#p5-29-t12-replication-of-the-streaming-and-hybrid-prefix-guards) | T12 replication of the stream + hybrid guards (λ_mid fixed in advance) (gaps 76, 92 closed; gap 96 = P5-30, scorer status for an infeasible guarantee that commits, closed 2026-11-19) |
| 77 | [P14-29](roadmap-standard.md#p14-29-measured-checking-time-per-commit-for-aac-and-bci-users) | measured checking time per commit |
| 73, 74 | [P5-25](roadmap-standard.md#p5-25-online-re-calibration-for-a-guard-with-a-learned-commit-score), [P5-26](roadmap-standard.md#p5-26-learned-commit-score-with-the-precision-and-hallucination-bounds) | learned score with online re-calibration and with the precision / hallucination bounds |
| 70 | [P14-27](roadmap-standard.md#p14-27-cost-of-causal-smoothing-on-t15-and-the-decoder-accuracy-target) | decoder accuracy target |

## Rerun
Scripts: `experiments/2026-11-16-p14-05-safe-wpm/run.py`, `experiments/2026-11-18-p5-23-learned-confidence/run.py`, `experiments/2026-11-18-p5-24-prefix-commits/run.py`, `experiments/2026-11-18-p14-28-reading-cost/run.py`, `experiments/2026-11-18-p5-27-streaming-prefix/run.py` (stages `views`, `evaluate`, `verdict`), `experiments/2026-11-19-p15-22-llm-learned/run.py all` (or `launch.py`, detached; needs the P15-05 M4-13 caches), through the isolation wrapper (`.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I <script>`). They need the local M4-13 and T12 v2 log-probs.

## Related pages
[Safe WPM bottleneck](safe-wpm-bottleneck.md), [decoder quality write-up](frontier-decoder-quality.md), [E3 write-up](frontier-e3-hallucination.md), [north star](north-star.md).
