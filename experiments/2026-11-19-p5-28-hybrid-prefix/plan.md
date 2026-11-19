---
title: P5-28 hybrid streaming + end-of-trial prefix guard - pre-registration
type: experiment
task: P5-28
updated: 2026-11-19
---

# P5-28: hybrid streaming + end-of-trial prefix guard (pre-registration)

Written and committed **before** any evaluation number of this item was computed or read. Gap 92 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P5-28](../../wiki/questions/roadmap-standard.md#p5-28-hybrid-streaming-and-end-of-trial-prefix-guard). Follow-up of [P5-27](../2026-11-18-p5-27-streaming-prefix/results.md) (streaming guard: 2.34 [2.11, 2.57] against 4.67 [4.26, 5.07] for the one-commit P5-24 prefix guard; right words a median 1.44 s after the word ends, against 11.20 s). Metric: the **proposed** [safe-wpm/0.2](../../docs/safe-wpm-v0.2-proposal.md) with the P14-28 reading cost and the **proposed** several-commits rule (section 7 of the proposal). **Neither is adopted.** v0.1 stays the adopted metric. The user decides. CPU only (background class, 4 threads). No GPU. No LLM. No new decoding.

**Disclosure.**
- Before this plan, the only runs were (1) unit tests on synthetic data and (2) a `dry` stage that loaded the P5-27 guard files and the first `val_select` view chunk and ran the hybrid rule on 12 `val_select` items (no certification, no `val_eval` data). Dry result: base config id `tcfg-e9758d5133d07fa6` (= P5-24), views made with that base and step 6, P5-27 streaming score config id `scfg-9171461e4f8cf0c2` (= P5-27); load 5.7 s, 0.02 s for 12 items, peak 539 MB.
- **We know the P5-27 results** (aggregates and the exploratory diagnostic in its results.md: the streaming score ranks end-of-trial prefixes low, commits fall at a median 31 % of the trial). This design reacts to them. The value λ_mid = 0.99 is the threshold that P5-27 certified **on the same 271 certify items**. So λ_mid depends on the certify data; the joint LTT below then re-uses those items. This is a small breach of the "fix before you look" rule for the certification; it is stated here and in the results. The secondary Bonferroni arm does not fix λ_mid from P5-27 alone.

## Question
Does a guard that commits words mid-trial (the P5-27 streaming score) **and** decides again at the trial end with the P5-24 prefix score (which can extend the mid-trial commit), certified together on the trial loss, give more safe WPM than the one-commit P5-24 prefix guard under v0.2 with reading cost? Does it keep the P5-27 latency gain?

## Hypotheses
- **H1 (primary).** The hybrid gives safe WPM v0.2 + reading cost different from the single arm (two-sided rule below). Our prior: no clear difference or a small loss, because the end decision gives most words in both arms and each extra commit pays 0.5 s.
- **H2 (secondary).** The hybrid is non-inferior to the single arm with margin 0.25 WPM (about 5 % of 4.67).
- **H3 (secondary).** The hybrid commits right words earlier than the single arm (lower median latency of right committed words; lower median latency of the first right word).

## Design (fixed here)

### Input (reused, read only)
The P5-27 checkpoint views in `C:\Users\zhang\bci-data\derived\p5-27\views\` (decodes of the causal M4-13 log-probs at every 6 frames = 0.48 s and at the trial end, made with the P5-24 base guard `tcfg-e9758d5133d07fa6`; `base.json` records that id and step 6), `controls.json` (names of the 600 null inputs), `decisions-single.json` and `decisions-stream.json`. Guard files: `experiments/2026-11-18-p5-27-streaming-prefix/results/guard-p5-27-base.json` and `guard-p5-27-stream.json`. Texts, durations and phoneme ids through the P5-27 `load_t15`. Nothing in `derived\p5-27\` is written. Validity check before use: the base guard config id, the views' base id and step, and the stream config id must equal the values above (the `dry` stage passed them; `evaluate` checks again and records them).

### Arms

| arm | what | role |
|---|---|---|
| **single** | the P5-24 prefix guard (one decision at the trial end, threshold 0.94); the P5-27 `decisions-single.json` (= P5-24, 701/701) | **comparator** |
| **hybrid** | `fidetype.trust.hybrid_commit.HybridPrefixGuard`: mid-trial checkpoints use the P5-27 streaming score (19 features, no refit) with **λ_mid = 0.99**; the end checkpoint uses the P5-24 prefix score of the base guard (16 features, no refit) with **λ_end certified jointly** | **treatment** |
| stream | the P5-27 streaming guard (`decisions-stream.json`) | secondary comparator |
| hybrid-bonferroni | λ_mid ∈ {0.99, 0.98, 0.97}, each with its own λ_end certified at δ/3 = 0.0333 | secondary (sensitivity; reported, not decided) |

Library code: `src/fidetype/trust/hybrid_commit.py` (new). Script: [`run.py`](run.py). Both as committed with this plan.

### Hybrid rule
- **Append-only** as in P5-27. With K words committed: if the top-1 words at a checkpoint do not start with them, no commit there (conflict, counted). Else, if the commit gate passes, commit up to the longest prefix k whose monotone score ≥ the threshold of that checkpoint (λ_mid before the end, λ_end at the end), if k > K.
- Mid-trial commits are prefix commits. At the end, k = all top-1 words gives a **complete** commit. The end decision can extend a mid-trial commit; it cannot change it.
- One decision event per commit (`fidetype.hybrid-commit-event/0.1`; utterance id, seq, checkpoint, frames, time, words added, words so far, complete, score, the threshold used, config id, hash chain). `run.py` checks every chain.

### Joint certification (trial loss)
- **Loss:** a trial is wrong if **any** of its commits is wrong (`stream_wrong`, the P5-27 loss; = "the final committed text is wrong" under rule (1) of v0.2). Risk = wrong trials / all trials.
- **LTT on λ_end with λ_mid fixed and the mid-trial commits on:** exact binomial p-values, fixed sequence 1.00 → 0.00 step 0.01, stop at the first p-value > δ; α = 0.05, δ = 0.1; on the P5-23/P5-24 certify part only (the last 37.5 % = 271 items of `default_rng(0).permutation(722)`, hash `fadfd84557fcb24b`). Neither score used these items (the base guard's conformal parts use the first 25 %; the streaming score was fit on the first 62.5 %).
- Guarantee: P(rate of wrong trials ≤ 0.05) ≥ 0.9 over the calibration draw, for exchangeable trials, for the pair (0.99, λ_end) as a whole, subject to the disclosure above on λ_mid.
- If no λ_end passes, λ_end = inf: the hybrid then commits only mid-trial and its status is not `certified` (no bound) → verdict "hybrid not certified".

### Data
`val_select` (722) calibrates; `val_eval` (701) evaluates. `val_eval` is never used for fitting, certification or the choice of λ_mid. Outputs: `C:\Users\zhang\bci-data\derived\p5-28\` (per-trial decisions with text, runner log, DONE file; local) and `results/` here (aggregates, guard file without text, log).

## Outcomes

### Primary: safe WPM v0.2 with reading cost and the several-commits rule (proposed)
`safe_wpm(..., metric_version="0.2", n_commits=..., read_s_per_commit=0.5, read_s_per_word=0.3)` with the measured trial durations (the P5-27 `score`); guarantee `risk = "wrong-stream-commit"`; status must be `certified`. The single arm by the same call (4.67).

### Primary safety
Wrong trials / 701 with the two-sided 95 % Clopper-Pearson interval. **Safety holds** iff the observed rate ≤ 0.05. **Clear violation** iff the CP lower bound > 0.05.

### Controls
The 600 P5-27 streaming null inputs (300 **uniform**, 300 **shuffled**, generator `default_rng((0, 527))`), every checkpoint decided by the final hybrid guard; an input with ≥ 1 commit counts; pass iff count ≤ 15 per control. A failed control refuses the arm (`NullControlError`): no guard, no result.

### Decision rule (T15)
Paired percentile trial bootstrap of Δ = hybrid − single under the primary metric: 2,000 resamples of the 701 trials (seed 0), the same resample for both arms, decisions fixed (the P5-27 `paired`). hw = (97.5th − 2.5th percentile) / 2.

| verdict | condition |
|---|---|
| **hybrid beats single** | controls pass **and** safety holds **and** status `certified` **and** Δ > hw |
| single beats hybrid | controls pass, safety holds, certified, and Δ < −hw |
| no clear difference | controls pass, safety holds, certified, and \|Δ\| ≤ hw |
| hybrid fails safety / a control / not certified | observed rate > 0.05, or a control fails, or status not `certified` |

**H2 (secondary, pre-registered):** "non-inferior" iff controls pass, safety holds, certified, and the 2.5th percentile of Δ > −0.25.
**H3 (secondary, pre-registered):** "earlier" iff the median latency of right committed words of the hybrid < that of the single arm. We also report the first-right-word latency.

### Secondary (reported, not decided)
- Latency (P5-27 definition: commit time − end time of the same true word; word ends from the CTC forced alignment of the true phonemes; an end commit is at the trial end): right / all committed words (median, mean, p10, p90), share committed before the trial end, and the first right word per committing trial; hybrid, single and stream.
- v0.2 without reading cost; paired Δ without reading cost; v0.1 complete-only view; paired Δ hybrid − stream.
- Commits per trial, trials with mid commits, with end commits, with a mid commit extended at the end, conflicts, words, complete commits, overlap with the single arm; λ_end, in-sample LTT risk, commit rate.
- The hybrid-bonferroni arm: λ_end, controls, value, paired Δ vs single, per λ_mid.
- Whether the hybrid v0.2 value and its interval are above the no-BCI reference 4.02, and whether its v0.1 complete-only value is above 4.02.

### Reference checks (computed in `evaluate` before the hybrid; reported whatever they show)
1. The end decision alone (λ_mid = inf, λ_end = 0.94) on the `val_eval` views equals `decisions-single.json` (action and text, 701/701).
2. With λ_mid = inf, the joint LTT gives λ_end = 0.94 (the P5-24 threshold; same loss with one commit per trial).
3. The guard and view ids above; split hashes as in P5-27.
A mismatch is reported as a finding; the rule is then applied as written.

### T12
**Not run.** No T12 checkpoint views exist (P5-27 did not decode T12). A T12 hybrid needs a new streaming decode of the T12 v2 log-probs (hours of CPU), its own frame timing, a streaming score fit and the same certification. The shared T12 loader peaked at 2,340 MB in P5-24, which fits the 6 GB cap of this task, but the decode is a separate run. A new gap registers the T12 replication of P5-27 and P5-28.

### Links
- **P5-28 (gap 92)** closes when this replay is reported (a hybrid guard with mid-trial and end decisions under one trial loss, chained events, a pre-registered T15 replay next to the one-commit guard), whatever the verdict. The T12 part moves to the new gap.
- **P14-23 (gap 53)** stays open unless a pre-registered **v0.1** value > 4.02 (the v0.1 complete-only view here is that number) or the user adopts v0.2.

## Order, limits, outputs
1. Commit this plan, the library code (full pytest first), the tests and `run.py` in one commit **before** `evaluate` runs.
2. Run `evaluate`, then `verdict`, one process each, under `python -m fidetype.utils.isolation run --class background --threads 4`, in one detached runner (`CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`, keep-awake `SetThreadExecutionState`), log and DONE file in `derived\p5-28\`. Each stage writes its result atomically; a restart re-runs only the stages that have no result in `results.json` (the runner skips a stage marked done). Expected time: minutes (no decoding; P5-27 `evaluate` took 11 s plus the LTT grids); peak below 1 GB.
3. A stage killed for low memory is not retried; it is reported.
4. No change of scores, λ_mid, grid, loss, metric, reading cost, split or rule after this commit.

**Known limits:** one participant, one split, one seed; conditional intervals only. λ_mid comes from P5-27 on the same certify items (disclosure). The word decoder sees each truncation as a whole sentence. Word ends come from our own decoder's forced alignment. The metric and its several-commits rule are proposals.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including a failure.
