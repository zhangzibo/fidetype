---
title: P5-27 streaming word-by-word prefix commits within one trial - pre-registration
type: experiment
task: P5-27
updated: 2026-11-18
---

# P5-27: streaming word-by-word prefix commits (pre-registration)

Written and committed **before** any evaluation number of this item was computed or read. Gap 76 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P5-27](../../wiki/questions/roadmap-standard.md#p5-27-word-by-word-streaming-prefix-commits-within-a-trial). Follow-up of [P5-24](../2026-11-18-p5-24-prefix-commits/results.md) (one prefix commit per trial, at the end: 4.87 under the proposed v0.2) and [P14-28](../2026-11-18-p14-28-reading-cost/results.md) (reading cost per commit; the P5-24 guard keeps 4.67 [4.26, 5.07] at 0.5 s + 0.3 s/word). Metric: the **proposed** [safe-wpm/0.2](../../docs/safe-wpm-v0.2-proposal.md) with the P14-28 reading cost and the **proposed** "several commits per trial" extension (section 7 of the proposal, committed with this plan). **Neither is adopted.** The user decides. CPU only (background class, 4 threads, one process at a time, RAM cap 1.5 GB). No GPU. No LLM.

**Disclosure.** Before this plan, the only runs were (1) unit tests on synthetic data and (2) a dry run on 12 `val_select` items (pipeline and decode time; no `val_eval` data decoded or scored; numbers in "Order, limits, outputs"). No evaluation number exists.

## Question
Does a guard that may commit more words of the same sentence while the trial goes on (append-only, certified on one loss for all commits of a trial) give more safe WPM than the one-commit P5-24 prefix guard, under v0.2 with reading cost, with the wrong-trial guarantee still met? And how much earlier are words committed (commit latency)?

## Streaming input (defined here)
- **Decoder:** M4-13 (`fidetype.decoders.lookahead_gru`, dedicated L 0): causal smoothing, unidirectional GRU, patch 14, stride 4, 20 ms bins, no lookahead (causality proved by `tests/test_causal_lookahead.py`). Output frame j reads bins `[4j, 4j + 14)`. So the first n frames of the stored full-trial log-probs are exactly what the streaming decoder has emitted when bin `4(n-1) + 13` ends: **no re-decoding is needed**; a checkpoint is a prefix truncation of the stored log-probs.
- **Checkpoints:** after every **6 frames (0.48 s)** and at the end of the trial (`fidetype.trust.stream_commit.checkpoint_frames(n, 6)`). The last checkpoint is the end of the utterance.
- **Checkpoint time:** n frames exist at `(4(n-1) + 14) * 0.02 s` after trial start (`checkpoint_time_s`). The end checkpoint is at the measured trial end (bins × 0.02 s). Decoder compute time is measured and reported, not added.
- **Decode at a checkpoint:** the base guard's pipeline on the truncated log-probs: the B2T '25 word decoder (lm 1.0, edit 12, bonus 3), the frame temperature, n-best calibration, hallucination guard and commit gate of the base guard (below).

## Arms

| arm | what | role |
|---|---|---|
| **single** | the P5-24 prefix guard: `calibrate(..., seed=0, confidence="learned", commit_unit="prefix")` on `val_select`, one decision at the end of each trial | **comparator** (re-calibrated here; reference check against the P5-24 decisions) |
| **stream** | `fidetype.trust.stream_commit.calibrate_streaming(base, ...)` with `base` = the single-arm guard, step 6 frames | **treatment** |
| stream-p524-score | the P5-24 prefix score (16 features, no refit) streamed with the same rule; its threshold re-certified by LTT on the stream loss on the same certify items; streaming null controls | secondary (does the refit matter?) |

Library code: `src/fidetype/trust/stream_commit.py` (new), `src/fidetype/trust/commit_score.py` (`unit="stream-prefix"`, `STREAM_FEATURES`), `src/fidetype/benchmark/safe_wpm.py` (`n_commits`, `RISK_STREAM`), as committed with this plan. Script: [`run.py`](run.py) as committed with this plan.

### Streaming rule (fixed here)
- At each checkpoint c the base pipeline gives the top-1 words w(c) and the P5-24 prefix features of each prefix k.
- **Score:** 19 features (`STREAM_FEATURES`) = the 16 P5-24 prefix features of the decode so far + `stable_log` (log(1 + earlier checkpoints in a row whose top-1 had the same first k words), sign +), `at_end` (1 at the end, free sign), `open_last_word` (k = all top-1 words and not the end, sign −). Model: the P5-23/P5-24 type (L2 1.0 logistic regression, standardised, fit-range clipping, sign constraints with backward elimination). Monotone in k (running minimum).
- **Append-only commit:** with K words already committed: if w(c) does not start with them, no commit at c (a *conflict*, counted). Else, if the commit gate passes, commit up to the longest prefix k with score ≥ threshold, if k > K. Committed words are never retracted.
- **Complete commit:** only at the end checkpoint, when k = all top-1 words. Every earlier commit is a prefix commit. After a complete commit the trial has no more commits.
- **Decision events:** one event per commit (`fidetype.stream-commit-event/0.1`): utterance id, seq, checkpoint, frames, time, words added, words committed so far, complete, score, threshold, config id, and a hash chain (`prev_id` → `id`). `run.py` checks every chain.

### Risk (fixed here): wrong trial
A trial is **wrong** if **any** of its commits is wrong (prefix commit: its words are not the first words of the truth, or the truth is shorter; complete commit: the words are not exactly the truth). Because commits are append-only, this equals "the final committed text is wrong" under rule (1) of v0.2. **Risk** = wrong trials / all trials (marginal; offers and withholds have loss 0).

**LTT:** exact binomial p-values, fixed-sequence grid 1.00 → 0.00 step 0.01 (stop at the first p-value > delta), on the certify part only (`ltt_stream_threshold`). The loss need not be monotone in the threshold (an early commit can block a later one through a conflict); fixed-sequence LTT does not need monotonicity. Guarantee: P(risk ≤ 0.05) ≥ 0.9 over the calibration draw, for exchangeable trials.

### Split (fixed here; the P5-23 / P5-24 split)
`numpy.random.default_rng(0).permutation(722)` of `val_select`: first 25 % temperatures and conformal (base guard), next 37.5 % policy grid; **both parts (451 items) fit the streaming score** (one row per word prefix and checkpoint, unweighted; label: a commit of that prefix at that checkpoint would be right, with the complete rule only at the end); the last 37.5 % (**271 items**) **certify** the threshold. Hashes of the sorted positions: score-fit `285b8c0d9baf5a41`, certify `fadfd84557fcb24b` (= P5-24). `val_eval` (701) is never used for fitting or certification.

### Data (read only)
`derived\trust-reruns-m4-13\logprobs-m4-13-long0-val_select.npz`, `derived\m4-13\logprobs-m4-13-long0-val_eval.npz`; texts, phoneme targets and trial durations from `derived\m4-01-02-lookahead`; the P5-24 prefix decisions `derived\p5-24\decisions-p5-24-t15-m4-13-prefix.json` (reference check only). `derived\p14-23-analysis\` is **not** read. Outputs: `C:\Users\zhang\bci-data\derived\p5-27\` (checkpoint decodes, per-trial decisions; local) and `results/` here (aggregates, guard files without text, log).

## Outcomes

### Primary: safe WPM v0.2 with reading cost and the several-commits rule (proposed)
`safe_wpm(..., metric_version="0.2", n_commits=..., read_s_per_commit=0.5, read_s_per_word=0.3)` with the measured trial durations: per trial the union of its commits (final committed text) gets the v0.2 credit and penalty; every commit pays 0.5 s; every committed word pays 0.3 s once. Stream guarantee: `risk = "wrong-stream-commit"`. Status must be `certified`. The single arm is scored by the same call (one commit per trial; = the P14-28 value, 4.67, if the reference check passes).

### Primary safety
Wrong trials / all 701 trials with the two-sided 95 % Clopper-Pearson interval. **Safety holds** iff the observed rate ≤ 0.05. **Clear violation** iff the CP lower bound > 0.05.

### Controls
Streaming null controls on the final stream guard: **uniform** (near-uniform logits, lengths of random calibration items) and **shuffled** (time-shuffled calibration log-probs), 300 each, generator `default_rng((0, 527))`; every checkpoint decided; an input with ≥ 1 commit counts; pass iff count ≤ floor(0.05 × 300) = 15. A failed control refuses the arm (`NullControlError`): no guard, no result.

### Decision rule (T15)
Paired percentile trial bootstrap of Δ = stream − single, both under the primary metric: 2,000 resamples of the 701 trials (seed 0), the same resample for both arms, decisions fixed. hw = (97.5th − 2.5th percentile) / 2.

| verdict | condition |
|---|---|
| **stream beats single** | stream controls pass **and** safety holds **and** status `certified` **and** Δ > hw |
| single beats stream | controls pass, safety holds, certified, and Δ < −hw |
| no clear difference | controls pass, safety holds, certified, and \|Δ\| ≤ hw |
| stream fails safety / a control / not certified | observed rate > 0.05, or a control fails, or status not `certified` |

### Secondary (reported, not decided)
- **Commit latency:** for each committed word at position j that exists in the truth: commit time − end time of true word j. Word end = the last aligned frame of the word's last phoneme in a CTC forced alignment (Viterbi) of the true phoneme sequence on the full-trial log-probs, time `(4f + 14) × 0.02 s`; trials whose alignment fails or whose phoneme word count differs from the text are left out (count reported). Median, mean, 10th / 90th percentile for right committed words and all committed words, both arms; share of committed words committed before the trial end.
- **Compute:** wall-clock decode + feature time per checkpoint on `val_eval` (median, 95th percentile, max) vs the 0.48 s step.
- v0.2 without reading cost (with the several-commits rule); paired Δ without reading cost; v0.1 complete-only view (a trial counts only if its final commit is complete).
- Commits per trial, conflicts, words committed, final complete commits, fitted weights and dropped features, threshold, in-sample LTT risk, the stream-p524-score arm (threshold, controls, value, paired Δ vs single).
- Whether the stream value and its interval are above the no-BCI reference 4.02.

### Reference checks (before any result is read)
- The re-calibrated single-arm guard has the P5-24 config id `tcfg-e9758d5133d07fa6`, and its `val_eval` decisions equal the P5-24 prefix decisions (same action and text, 701/701). A mismatch is reported as a finding; the rule is then applied to the recomputed single arm.
- Split hashes equal those above.

### T12
**Not run.** The T12 v2 decoder is also causal (causal half-Gaussian smoothing, unidirectional GRU, causal rolling normalisation), so prefix truncations of its log-probs are a valid streaming input. But the shared T12 loader peaked at **2,340 MB** in P5-24, above the 1.5 GB cap of this task. A new gap registers the T12 replication (with a lighter loader).

### Links
- **P5-27 (gap 76)** closes when this replay is reported (roadmap "done when": a streaming guard that commits further words of the same utterance under one loss for all commits of a trial, chained decision events, a pre-registered T15 replay with safe WPM next to the one-commit prefix guard), whatever the verdict.
- **P14-23 (gap 53)** stays open: it needs a pre-registered **v0.1** value above 4.02 (or the user adopts v0.2). We report the stream v0.2 value against 4.02; this is not part of the rule.

## Order, limits, outputs
1. Commit this plan, the library code (full pytest first), the tests, the proposal section 7 and `run.py` in one commit **before** any stage runs.
2. Run `views` (long; detached; resumable chunk files), then `evaluate`, then `verdict`, one process each:
   `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-18-p5-27-streaming-prefix/run.py views` (then `evaluate`, then `verdict`).
3. A stage killed for low memory is not retried; it is reported as not run and a new gap registers it.
4. No change of features, model, step, split, grid, loss, metric, reading cost or rule after this commit.

**Run-time estimate (from the dry run).** Two dry runs on 12 `val_select` items (2026-11-18 13:57 and 2026-11-19 09:50, `results/run.log`): base calibration 264-323 s; 386 checkpoints (about 32 per item) at 0.045-0.059 s each; null inputs about 52 checkpoints each at 0.16-0.22 s; peak 785 MB; base config id `tcfg-e9758d5133d07fa6` (= P5-24). Estimate for `views`: calibration 0.1 h + 722 + 701 items × 32 × 0.05 s ≈ 0.6-0.7 h + 600 null inputs × 52 × 0.16-0.22 s ≈ 1.4-1.9 h, so **about 2-3 h**; `evaluate` about 0.3 h (no decoding); `verdict` seconds. The stages run one after the other in one detached runner with a keep-awake (`SetThreadExecutionState`); `views` writes one chunk file per 50 items and skips finished chunks on a restart.

**Known limits (stated before the run):** one participant, one split, one seed; conditional intervals only. The streaming features were designed by us without looking at `val_eval`. The word decoder sees each truncation as a full sentence (its language model has no "unfinished sentence" state); the score has to learn that the last word can be open. Word end times come from our own decoder's forced alignment, not from audio or a speech clock. Decode time is CPU time on this machine (no GPU), with other jobs running.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including a failure.
