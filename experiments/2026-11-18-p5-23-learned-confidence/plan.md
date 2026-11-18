---
title: P5-23 learned commit-confidence score vs the p_top1 drop-in guard - pre-registration
type: experiment
task: P5-23
updated: 2026-11-18
---

# P5-23: learned commit-confidence score (pre-registration)

Written and committed **before** any evaluation number of this item was computed or read. Gap 67 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P5-23](../../wiki/questions/roadmap-standard.md#p5-23-learned-commit-confidence-score-for-the-drop-in-guard). Follow-up of the exploratory [P14-23 analysis](../../wiki/questions/safe-wpm-bottleneck.md) (lever C1: AUROC 0.83 → 0.87, safe WPM 3.50 [2.92, 4.04] against 2.23; that estimate had selection effects and a certificate leak, so it is not a claim). CPU only (background class, 4 threads, one process at a time, RAM target under 1 GB). No GPU. No LLM.

## Question
Does the learned commit score of `fidetype.trust.calibrate(confidence="learned")` give more safe WPM than the default `p_top1` guard, with the wrong-commit guarantee still met, when everything that is fitted uses calibration data only?

## What is compared
Two arms per set. Same decoder outputs, same word decoder, same calibration items, same seed, same `alpha` 0.05 and `delta` 0.1, same commit gate, same null controls. The only difference is the `confidence` argument.

| arm | call | commit rule |
|---|---|---|
| **current** | `calibrate(..., seed=0)` (P14-03 / P14-05 recipe, unchanged) | `p_top1 >= max(policy-grid threshold, LTT threshold)` + commit gate |
| **learned** | `calibrate(..., seed=0, confidence="learned")` (`confidence_l2` 1.0) | learned score ≥ LTT threshold + commit gate |

Library code: `src/fidetype/trust/commit_score.py` and `src/fidetype/trust/dropin.py` as committed with this plan. Script: [`run.py`](run.py) as committed with this plan (stages `t15`, `t12`, `verdict`).

### Learned score (fixed here)
- **Features (13):** `p_top1`, `logit_p_top1`, `margin`, `nbest_entropy`, `word_agreement`, `char_conf_mean`, `char_conf_min`, `guard_risk`, `log_n_words`, `acoustic_per_char`, `lm_per_word`, `acoustic_gap`, `frames_per_char` (definitions: `commit_score.FEATURES` and docs/trust-guarantee.md section 10a). No LLM feature.
- **Model:** logistic regression on standardised features, L2 1.0 (intercept free), Newton steps; features clipped to the fit range; sign constraints `commit_score.SIGNS` with backward elimination. Label: the top-1 text equals the truth after whitespace normalisation.
- **LTT:** exact binomial p-values, fixed-sequence grid 1.00 → 0.00 step 0.01, risk = wrong COMMIT / all items (an item that fails the commit gate has score −inf).

### Three-way split (fixed here)
`calibrate` permutes the calibration items with `numpy.random.default_rng(0).permutation(n)`. The first 25 % fit the temperatures and the conformal threshold, the next 37.5 % fit the policy grid; **both parts together fit the learned score**. The last 37.5 % are the **certify** part: LTT only. The evaluation set is never used for fitting or certification.

| set | calibration items | score-fit part | certify part | evaluation set | SHA-256 (first 16 hex) of the sorted score-fit / certify positions |
|---|---|---|---|---|---|
| T15 M4-13 | `val_select` 722 | 180 + 271 = 451 | 271 | `val_eval` 701 | `285b8c0d9baf5a41` / `fadfd84557fcb24b` |
| T12 v2 | trust pool of the 14 fit_a + calibration sessions, 480 | 120 + 180 = 300 | 180 | trust pool of the 10 test sessions, 400 | `630db9ca864af56f` / `3fe1b31e8e46a035` |

The script recomputes these hashes and writes them into `results/results.json`.

### Data (read only)
- **T15 (primary):** M4-13 log-probs `C:\Users\zhang\bci-data\derived\trust-reruns-m4-13\logprobs-m4-13-long0-val_select.npz` and `...\m4-13\logprobs-m4-13-long0-val_eval.npz`; texts, phoneme targets and trial durations from `derived\m4-01-02-lookahead` (P14-05 loader `t15_keys`, `t15_durations`, P14-03 `ph_symbols`). Word decoder: the B2T '25 word decoder with the `tune.json` setting (lm 1.0, edit 12, bonus 3), the same as P14-05 and the P14-23 analysis. An edit-8 version is not part of this plan (P14-24 scope).
- **T12 (replication):** the P14-03 loader `data_t12` (T12 v2 decoder log-probs, word decoder with the word LM, `experiments/2026-11-13-confirmatory-t12-v2`); durations as the P14-05 stage `t12`.
- Calibration kwargs as P14-05 / P14-03: `vocab` = 41 phoneme symbols, `blank` 0, `input_scale="log_probs"`, `frame_period` 0.08, `decode_fn` = the word decoder, `stream_texts` = phoneme targets.
- The P14-23 derived folder (`derived\p14-23-analysis\`) is **not** used by this run. Its exploratory numbers do not enter any choice here.

## Outcomes

### Primary: safe WPM (`safe-wpm/0.1`, unchanged)
`fidetype.benchmark.safe_wpm.safe_wpm` with the measured trial durations (20 ms neural bins), the default correction rule (2 s + 0.79 s per character of the truth per wrong commit), the guarantee and controls from the guard sheet. Status must be `certified`.

### Primary safety: wrong-commit rate
Wrong COMMITs / all evaluation items, with the two-sided 95 % Clopper-Pearson interval (from `safe_wpm`). **Safety holds** iff the observed rate ≤ alpha 0.05. **Clear violation** iff the CP lower bound > 0.05.

### Controls
The two null controls of `calibrate` on the final guard of each arm: **uniform** (near-uniform frames) and **shuffled** (time-shuffled calibration frames), 300 inputs each, pass iff commits ≤ floor(0.05 × 300) = 15. A failed control refuses the arm (`NullControlError`): the arm has no guard and no result.

### Decision rule (per set)
Paired percentile trial bootstrap of the safe WPM difference Δ = learned − current: 2,000 resamples of the evaluation trials (seed 0), the same resample for both arms, decisions fixed (conditional on the calibration). Half-width hw = (97.5th − 2.5th percentile) / 2.

| verdict | condition |
|---|---|
| **learned beats current** | learned controls pass **and** learned safety holds **and** Δ > hw |
| current beats learned | learned controls pass and safety holds and Δ < −hw |
| no clear difference | learned controls pass and safety holds and \|Δ\| ≤ hw |
| learned fails safety / a control | learned observed wrong-commit rate > 0.05, or a learned control fails (refused) |

**T15 is the primary set.** The P5-23 result is "learned beats current" only if T15 gives that verdict. T12 is a replication: its verdict is reported next to T15 and does not change the T15 verdict. P5-23 closes with the write-up whatever the verdict (roadmap "done when").

### Reference check (before any result is read)
The **current** arm must reproduce the committed decisions: T15 = `derived\p14-05-safe-wpm\decisions-t15-m4-13.json` (P14-05: 104 commits, 17 wrong, safe WPM 2.23), T12 = `derived\p14-03-replay-validation\decisions-t12-a0.05.json` (P14-03). The script counts trials with the same action and text. If fewer than all trials match, we report it and still apply the rule to the recomputed current arm (it is the same recipe on the same data); the mismatch is a finding. The `config_id` can differ (decoder name, P5-21 stable label); that is not a failure.

### Secondary (reported, not decided)
Per arm: commits, wrong commits, error among commits, commit threshold, in-sample LTT commits, top-1 exact rate, recall of exactly-right trials, AUROC of the commit score and of `p_top1` for "top-1 exactly right" on the evaluation set, the fitted weights and dropped features, run time and peak memory.

### P14-23 (gap 53) link
P14-23 closes only if a pre-registered result is above the no-BCI reference **4.02** on the full T15 `val_eval` set. We report whether the learned arm's T15 safe WPM is above 4.02. The P14-23 analysis estimate (3.50) suggests it will not be; this is not part of the decision rule.

## Order, limits, outputs
1. Commit this plan, the library code (full pytest first), the tests, the docs and `run.py` in one commit **before** any stage runs.
2. Run `t15`, then `t12`, then `verdict`, one process each:
   `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-18-p5-23-learned-confidence/run.py t15` (then `t12`, then `verdict`).
3. Per-trial decisions (with text) go to `C:\Users\zhang\bci-data\derived\p5-23\` only (local). The repo gets `results/results.json` (aggregates), `results/guard-*.json` (configuration and sheet, no text, no signal) and `results/run.log`.
4. A stage that is killed for low memory is not retried; it is reported as not run and a new gap registers it.
5. No change of features, model, split, grid or rule after this commit. Any later variant (other features, an LLM feature, edit 8, prefix commits) is a new item with its own plan.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including a failure.
