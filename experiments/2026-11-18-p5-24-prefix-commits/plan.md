---
title: P5-24 certified word-prefix commits vs the sentence-level learned guard - pre-registration
type: experiment
task: P5-24
updated: 2026-11-18
---

# P5-24: certified word-prefix commits (pre-registration)

Written and committed **before** any evaluation number of this item was computed or read. Gap 68 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P5-24](../../wiki/questions/roadmap-standard.md#p5-24-certified-prefix-commits-in-the-trust-guard). Follow-up of the exploratory [P14-23 analysis](../../wiki/questions/safe-wpm-bottleneck.md) (lever A1: about 5.4 safe WPM with prefix credit, 505 prefix commits, 23 wrong; that estimate had selection effects and a certificate leak, so it is not a claim) and of [P5-23](../2026-11-18-p5-23-learned-confidence/results.md) (sentence-level learned score: 2.64 on T15). The metric is the **proposed** [safe-wpm/0.2](../../docs/safe-wpm-v0.2-proposal.md) (P14-26, committed with this plan). **v0.2 is not adopted.** The user decides adoption; v0.1 numbers are reported next to every v0.2 number. CPU only (background class, 4 threads, one process at a time, RAM target under 1 GB). No GPU. No LLM.

## Question
Does a guard that commits the longest certified word prefix of the top-1 sentence give more safe WPM (v0.2, proposed) than the sentence-level learned guard of P5-23, with the wrong-commit guarantee still met, when everything that is fitted uses calibration data only?

## What is compared
Three arms per set. Same decoder outputs, word decoder, calibration items, seed 0, `alpha` 0.05, `delta` 0.1, commit gate and null controls.

| arm | call | commit rule | role |
|---|---|---|---|
| current | `calibrate(..., seed=0)` (P14-03 recipe) | `p_top1 >= threshold` + commit gate | reference (P14-05) |
| **sentence** | `calibrate(..., seed=0, confidence="learned")` (P5-23) | learned sentence score >= LTT threshold + commit gate | **comparator** |
| **prefix** | `calibrate(..., seed=0, confidence="learned", commit_unit="prefix")` (new) | longest prefix with monotone prefix score >= LTT threshold + commit gate | **treatment** |

Library code: `src/fidetype/trust/commit_score.py` (prefix features, `prefix_right`, `monotone_prefix_scores`, `ltt_prefix_threshold`), `src/fidetype/trust/dropin.py` (`commit_unit="prefix"`), `src/fidetype/benchmark/safe_wpm.py` (`metric_version="0.2"`), as committed with this plan. Script: [`run.py`](run.py) as committed with this plan (stages `t15`, `t12`, `verdict`).

### Prefix score (fixed here)
- **Features (16, `commit_score.PREFIX_FEATURES`):** `prefix_mass`, `prefix_agree_min`, `prefix_agree_mean`, `prefix_char_conf_mean`, `prefix_char_conf_min`, `prefix_log_words`, `prefix_share`, `complete`, and the sentence features `p_top1`, `nbest_entropy`, `guard_risk`, `acoustic_per_char`, `lm_per_word`, `acoustic_gap`, `frames_per_char`, `log_n_words`. Signs: `commit_score.PREFIX_SIGNS`. No LLM feature.
- **Model:** the P5-23 model type (L2 1.0 logistic regression on standardised features, Newton steps, fit-range clipping, sign constraints with backward elimination). One row per word prefix of the top-1 text of each fit item. Label: `prefix_right` (below).
- **Monotone score:** the score of prefix k = min of the raw scores of prefixes 1..k.
- **Decision:** commit the longest prefix k with score >= threshold (k = 0: no commit; the trust layer's offer / withhold stays). The commit gate is applied to the top-1 text (non-empty, guard risk < 1.0), as for the sentence arms.

### Risk (fixed here): wrong prefix commit
For one trial with top-1 words w_1..w_m, truth words y_1..y_n and committed prefix k >= 1:
- k < m (**prefix commit**, `complete = False`): **wrong** iff (w_1..w_k) != (y_1..y_k) or n < k.
- k = m (**complete commit**, `complete = True`): **wrong** iff (w_1..w_m) != (y_1..y_n), i.e. the text is not exactly the truth.
- **Risk** = wrong commits / all trials (marginal; one trial = one unit; offers and withholds have loss 0).

The loss is monotone in the threshold (a lower threshold gives a longer or equal prefix; a wrong prefix stays wrong when it grows; a right prefix can become wrong). **LTT:** exact binomial p-values, fixed-sequence grid 1.00 → 0.00 step 0.01 (stop at the first p-value > delta), on the certify part only (`commit_score.ltt_prefix_threshold`). Guarantee: P(risk ≤ 0.05) ≥ 0.9 over the calibration draw.

### Three-way split (fixed here; the P5-23 split)
`calibrate` permutes the calibration items with `numpy.random.default_rng(0).permutation(n)`. First 25 %: temperatures and conformal threshold; next 37.5 %: policy grid; **both parts together fit the score** (sentence and prefix); last 37.5 %: **certify** part (LTT only). The evaluation set is never used for fitting or certification.

| set | calibration items | score-fit part | certify part | evaluation set | SHA-256 (first 16 hex) of the sorted score-fit / certify positions |
|---|---|---|---|---|---|
| T15 M4-13 | `val_select` 722 | 451 | 271 | `val_eval` 701 | `285b8c0d9baf5a41` / `fadfd84557fcb24b` |
| T12 v2 | trust pool of the 14 fit_a + calibration sessions, 480 | 300 | 180 | trust pool of the 10 test sessions, 400 | `630db9ca864af56f` / `3fe1b31e8e46a035` |

### Data (read only)
The P5-23 loaders (`run.py` imports `experiments/2026-11-18-p5-23-learned-confidence/run.py`: `data_t15`, `data_t12`): M4-13 log-probs `derived\trust-reruns-m4-13\logprobs-m4-13-long0-val_select.npz`, `derived\m4-13\logprobs-m4-13-long0-val_eval.npz`; texts, phoneme targets and trial durations from `derived\m4-01-02-lookahead`; the B2T '25 word decoder (lm 1.0, edit 12, bonus 3); T12 v2 as P14-03. Reference decisions: `derived\p14-05-safe-wpm\decisions-t15-m4-13.json`, `derived\p14-03-replay-validation\decisions-t12-a0.05.json`, `derived\p5-23\decisions-p5-23-*-learned.json`. The P14-23 folder (`derived\p14-23-analysis\`) is **not** read. Outputs: `C:\Users\zhang\bci-data\derived\p5-24\` (per-trial, local) and `results/` here (aggregates, guard files without text, log).

## Outcomes

### Primary: safe WPM v0.2 (proposed)
`safe_wpm(..., metric_version="0.2")` with the measured trial durations (20 ms neural bins), the default correction constants, the guarantee and controls from the guard sheet (the prefix guard's sheet gives `risk = "wrong-prefix-commit"`). Status must be `certified`. For the sentence and current arms v0.2 = v0.1 (all commits complete).

### Also reported: safe WPM v0.1 (the headline metric)
- **sentence, current:** v0.1 as P5-23 / P14-05.
- **prefix, v0.1 literal:** the v0.1 rule applied to the prefix guard's decisions: a commit earns words only if its text is exactly the truth; every other commit (also a right prefix) is a wrong commit with the v0.1 penalty. The status follows v0.1 (it can be `above-alpha`).
- **prefix, v0.1 complete-only:** the prefix guard deployed in a v0.1-compatible mode: only its complete commits are commits; its prefix commits become no commit (0 words, no penalty). Its complete commits are a subset of the certified commits, so its wrong-commit rate is at most the certified one.

### Secondary (reported, not decided)
- v0.2 with the active-speech span of our CTC output (first to last non-blank argmax frame, 0.08 s frames) as `speech_s`.
- Paired difference prefix (v0.2) − current (v0.2); prefix v0.1 complete-only − sentence v0.1.
- Per arm: commits, wrong commits, prefix vs complete commits, words per commit histogram, error among commits, threshold, in-sample LTT commits, P(top-1 exact), recall of exact top-1 trials, AUROC of `p_top1` and of the sentence score, the fitted weights and dropped features, the words in the right prefixes of all top-1 texts (perfect-prefix-guard ceiling), run time, peak memory.

### Primary safety
Wrong prefix commits / all evaluation items with the two-sided 95 % Clopper-Pearson interval. **Safety holds** iff the observed rate ≤ alpha 0.05. **Clear violation** iff the CP lower bound > 0.05.

### Controls
The two null controls of `calibrate` on the final guard of each arm: **uniform** (near-uniform frames) and **shuffled** (time-shuffled calibration frames), 300 inputs each; pass iff commits (prefix or complete) ≤ floor(0.05 × 300) = 15. A failed control refuses the arm (`NullControlError`): no guard, no result.

### Decision rule (per set)
Paired percentile trial bootstrap of Δ = prefix − sentence, both under safe-wpm v0.2: 2,000 resamples of the evaluation trials (seed 0), the same resample for both arms, decisions fixed. Half-width hw = (97.5th − 2.5th percentile) / 2.

| verdict | condition |
|---|---|
| **prefix beats sentence** | prefix controls pass **and** prefix safety holds **and** prefix v0.2 status `certified` **and** Δ > hw |
| sentence beats prefix | prefix controls pass, safety holds, certified, and Δ < −hw |
| no clear difference | prefix controls pass, safety holds, certified, and \|Δ\| ≤ hw |
| prefix fails safety / a control | prefix observed rate > 0.05, or a prefix control fails |

**T15 is the primary set.** The P5-24 verdict is the T15 verdict. T12 is a replication, reported next to it. The verdict is under the **proposed** v0.2; we state it as such.

### Reference checks (before any result is read)
- current arm = the P14-05 T15 decisions (104 commits, 17 wrong, 2.23) and the P14-03 T12 decisions;
- sentence arm = the P5-23 learned decisions (T15: 113 commits, 10 wrong, 2.64; T12: 31 commits, 15 wrong, 1.87).
The script counts trials with the same action and text. A mismatch is reported as a finding; the rule is then applied to the recomputed arms.

### P5-24 and P14-23 links
- **P5-24 (gap 68)** closes when this replay is reported (roadmap "done when": prefix commits in the guard, decision event with the word count, null controls on prefixes, a pre-registered T15 replay with v0.2 next to v0.1), whatever the verdict.
- **P14-23 (gap 53)** closes only with a pre-registered **v0.1** value above **4.02** on all 701 T15 `val_eval` trials with both controls passing (the sentence arm or the prefix v0.1 complete-only view), or if the user adopts v0.2 and the v0.2 value is above 4.02. We report whether the prefix v0.2 value and its 95 % interval are above 4.02; this is not part of the decision rule. Because v0.2 is not adopted, a v0.2 value above 4.02 does not close P14-23.

## Order, limits, outputs
1. Commit this plan, the library code (full pytest first), the tests, the v0.2 proposal, the docs and `run.py` in one commit **before** any stage runs.
2. Run `t15`, then `t12`, then `verdict`, one process each:
   `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-18-p5-24-prefix-commits/run.py t15` (then `t12`, then `verdict`).
3. A stage killed for low memory is not retried; it is reported as not run and a new gap registers it.
4. No change of features, model, split, grid, loss, metric or rule after this commit. A later variant (LLM features, edit 8, word-by-word streaming commits, another penalty) is a new item.

**Known limits (stated before the run):** the prefix feature set was designed after the exploratory P14-23 analysis, which looked at `val_eval`; the score itself is fitted on `val_select` only. One participant per set, one split, one seed; conditional intervals only. The speech span comes from our own CTC output.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including a failure.
