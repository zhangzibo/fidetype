---
title: P11-16 P11-14 confidence signals for EMG prefix commits - pre-registration
type: experiment
task: P11-16
updated: 2026-11-21
---

# P11-16: P11-14 confidence signals for word-prefix commits (pre-registration)

Written and committed **before** any feature, score, guard or decision of this item was computed. Gap 126 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-16](../../wiki/questions/roadmap-standard.md#p11-16-p11-14-confidence-signals-for-prefix-commits). Follow-up of [P11-14](../2026-11-20-p11-14-emg-lm-confidence/results.md) and [P11-12](../2026-11-20-p11-12-emg-nosignal-gate/results.md). Scoring of prefix commits: `safe-wpm/0.2` ([docs/safe-wpm.md](../../docs/safe-wpm.md), P14-26). **`safe-wpm/0.2` is a proposal. It is not adopted.** Every v0.2 number below is labelled "proposed v0.2".

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates and per-draw counts only: no per-user value, no user pseudonym, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-16\`. The P11-07, P11-09, P11-11, P11-12, P11-14 and P11-17 files are read only.

CPU only (isolation runner, class `background`, 2 threads). **No GPU.**

## Done-when (roadmap)
A pre-registered prefix guard on the in-beam decoder uses the P11-14 signals (per prefix: the wide-set fused mass of the prefix and the LM per character) and reports a certified proposed-v0.2 value with the P11-12 controls, compared with arm X (4.25) and with L-FL (6.80 v0.1); or the result states with numbers why not.

## Problem
- P11-14 L-FL (sentence commits, in-beam decoder FL): certified safe WPM v0.1 **6.80 [4.49, 9.63]** for one calibration. Sentence commits score the same under proposed v0.2, so its proposed-v0.2 value is also 6.80. P11-17: **5.00 [0.00, 9.55]** once the calibration draw is counted.
- P11-12 arm X (word-prefix commits, P11-11 decoder without in-beam LM, built-in learned prefix score of P5-24): proposed v0.2 **4.25 [2.69, 6.30]**.
- The P11-14 gain came from `p_fU` (fused posterior over the wide competitor set U) and `lm_pc` (LM log-prob per character). Arm X sees neither.

## Question
Does a word-prefix guard on the in-beam decoder FL, with a prefix score built from the P11-14 signals, give a certified, non-vacuous proposed-v0.2 safe WPM that passes the P11-12 controls? Is it above arm X (4.25) and above L-FL (6.80)?

## What was done before this plan (disclosure)
Reading of the P11-11, P11-12, P11-14 and P11-17 plans, code and result pages, of `fidetype.trust.commit_score` (prefix functions), `fidetype.trust.dropin` (`calibrate`, `_fit_prefix_score`, `_run_controls`), `fidetype.benchmark.safe_wpm` (v0.2, `prefix_outcome`) and `fidetype.lm.ngram.CharNgramLM.score_sentence`. No new decode, feature, score or decision was computed on any window before this commit. The numbers above come from committed result pages.

## Fixed parts (as P11-14, unchanged)
- Data and splits: the 8 P11-01 test users; calibration = track-val session (1,224 prompts), evaluation = track-test session (1,221 prompts); `check_track_splits`; unit digests equal P11-09.
- Windows: P11-09 `lp\` (33-class key form; real, input-level time-shuffled, zero EMG).
- Target: intended text (Backspace applied, P11-11 `resolve`). Words = split on spaces.
- Decoder **FL** only (w 0.25, beta 1, lam 8, beam 8): P11-12 no-signal gate -> P11-07 in-beam LM beam -> intended texts merged -> P11-11 OOV gate -> empty texts dropped. The commit text t (top-1) is the P11-14 FL top-1. **Committable** = gate pass, OOV gate pass, t non-empty.
- Competitor set U and the 10 P11-14 signals (`p_nb`, `p_fU`, `p_aU`, `agree_b0`, `agree_g`, `dist_g`, `ac_gap`, `lm_pc`, `log_nw`, `kps`): computed by the P11-14 `Analyser` code (imported, not copied). This item also keeps the merged fused score of every intended text in U (the values P11-14 computes for `p_fU`).
- Calibration split of `calibrate` with seed 0: permutation `default_rng(0).permutation(1224)`; `_split(1224)` = fit 306 / policy grid 459 / LTT 459. **Tuning items** = the first 765 positions (fit + policy grid; digest `96f175801d6ff225`). **LTT items** = the last 459 positions. The LTT items, the null windows and every evaluation window are never used to fit or tune.
- Risk: alpha **0.05**, delta **0.1**, loss = **wrong prefix commit** (`commit_score.RISK_PREFIX`: a committed prefix of k < m words is wrong if its words are not the first k words of the truth; a commit of all m top-1 words claims the whole sentence and is wrong unless it equals the truth); rate over all utterances.

## Prefix signals (per word prefix k = 1 ... m of t; fixed here)
Let w_1 ... w_m be the words of t.

| Feature | Definition | Sign |
|---|---|---|
| `lg_pm_fU` | logit (clipped to [-12, 12]) of the **wide-set fused prefix mass**: softmax over the merged fused scores of the intended texts in U; the mass of the texts whose first k words are w_1 ... w_k. For k = m: the mass of t itself (= `p_fU`, the whole-sentence claim) | + |
| `lg_pm_nb` | the same over the decoder's own merged n-best (fused scores, temperature 1); k = m: `p_nb` | + |
| `lm_pc_k` | **LM per character of the prefix**: k < m: `score_sentence(normalize_text(prefix) + " ", eos=False, normalize=False) / (len(prefix) + 1)` (the word boundary after the prefix counts, no end marker); k = m: `lm_pc` of P11-14 (`score_sentence(t) / (len(t) + 1)`) | + |
| `lg_p_fU` | sentence `p_fU` (logit, clipped) | + |
| `lm_pc` | sentence `lm_pc` | + |
| `dist_g` | sentence distance to the greedy text | - |
| `kps` | greedy key emissions per second | free |
| `log_nw` | log(1 + m) | free |
| `log_k` | log(1 + k) | free |
| `share` | k / m | free |
| `complete` | 1 if k = m, else 0 | free |

The prefix LM uses the P11-11 Tatoeba 6-gram (no lexicon term).

## Arms (fixed here)

| Arm | Role | Prefix score | How it is certified |
|---|---|---|---|
| **LX-FL** | **primary** | learned prefix score on the 11 features above | outside `calibrate`, with the library functions (see below) |
| BX-FL | secondary | the built-in learned prefix score (P5-24 `PREFIX_FEATURES`) on the FL native merged n-best with `logp_acoustic` (merged exact CTC) and `logp_lm` (the P11-14 BL items) | `fidetype.trust.calibrate(confidence="learned", commit_unit="prefix")`, native guard |
| LS-FL | exploratory check | the frozen P11-14 model `model-L-FL.json` as the score of the complete row only (sentence commits; no prefix rows) | as LX-FL |

**LX-FL model.** Rows = all prefix rows of the committable tuning items; label = `commit_score.prefix_right(words of t, words of truth)`. Model as P11-14 `Learned`: features standardised on the fit rows and clipped to their range; L2 logistic regression (`commit_score.fit_logistic`, l2 1.0, intercept not penalised); sign constraints with backward elimination (one feature per step, the largest wrong-sign weight first). The model is frozen before any LTT item is scored.

**LX-FL and LS-FL decision rule** (as the library prefix guard, P5-24): raw prefix scores -> `commit_score.monotone_prefix_scores` (running minimum) -> `longest_prefix(scores, threshold)` = k. k > 0: COMMIT the first k words (complete if k = m). k = 0 and committable: OFFER (counts as no commit). Not committable: WITHHOLD.

**LX-FL and LS-FL certification.** `commit_score.ltt_prefix_threshold(scores of the 459 LTT items, prefix_right, alpha 0.05, delta 0.1, DEFAULT_LTT_GRID)` (the function that `calibrate` uses for prefix guards; grid 1.00 -> 0.00 step 0.01; not committable items never commit).

**LX-FL and LS-FL controls** (the P11-12 controls, with the library code): `fidetype.trust.dropin._run_controls` on an adapter that applies this decision rule, with the same random state as `calibrate(seed=0)` (`default_rng(0)` after `permutation(1224)`), `null_trials` 300 (uniform and frame-shuffled calibration windows), `null_inputs` = the 300 P11-14 input-level time-shuffled calibration windows (`null_pick`); rate 0.05, so at most 15 / 300 commits each. Control windows are decoded fresh (no memo).

**Difference from a `calibrate` guard (stated limit).** The LX-FL and LS-FL guards are not `TrustGuard` files: no frame temperature, no conformal set, no trust-layer guard-risk gate. Their commit gate is the decoder gate above (no-signal gate, OOV gate, non-empty t). Their guarantee rests on the same LTT function on the same 459 LTT items. Their sheet (alpha, delta, split counts, threshold, feasible, controls, `confidence.unit = "prefix"`, an id = SHA-256 of the frozen model and threshold) is built for `safe_wpm.guarantee_from_sheet` / `controls_from_sheet`.

## Scoring (both versions, labelled)
P11-11 `score_arm` with arm type `"X"` for LX-FL, BX-FL and LS-FL (user-cluster bootstrap B 2,000, seed 0; Clopper-Pearson level 0.95; no-BCI reference 3.09; per-prompt neural time; truth lengths):
- **proposed v0.2** (primary metric of this item): prefix commits get credit for their words (`safe_wpm.prefix_outcome`); also v0.2 + reading cost (0.5 s + 0.3 s / word per commit; P14-28).
- **adopted v0.1**: only complete commits count; prefix commits count as no commit ("v0.1 complete only").
- Also reported: commits (prefix / complete), wrong commits with CP95, error among commits, actions, right words, correction time, threshold, control counts, test AUROC of `lg_pm_fU`, `lm_pc_k` and of the LX score over all prefix rows of the committable test windows (descriptive).

## Hypotheses and verdicts
| Id | Statement | Pass rule |
|---|---|---|
| **H1 (primary, done-when)** | LX-FL gives a certified, safe, non-vacuous proposed-v0.2 value with the P11-12 controls, above arm X | V1 certified (feasible threshold), V2 holds (test wrong-prefix-commit rate <= 0.05), V3 non-vacuous (proposed v0.2 status `certified`, value > 0), V6 pass, and proposed v0.2 value **> 4.25** |
| H2 | LX-FL beats the sentence guard L-FL | H1 holds and proposed v0.2 value **> 6.80** (L-FL: v0.1 = proposed v0.2 = 6.80) |
| H3 | the P11-14 signals beat the built-in prefix score on the same decoder | proposed v0.2 value of LX-FL > that of BX-FL |
| H4 | LX-FL vs no-BCI | V4 (proposed v0.2): "clearly above" (CI low end > 3.09), "above" or "below" |
| V6 | controls (P11-12) | the three calibration controls <= 15 / 300 each, and the test time-shuffled and zero-EMG commit rates <= 0.05 |
| C0a (must pass) | code reuse | for every calibration and null window, the FL top-1, native n-best and the 10 signals of this item equal the P11-14 memo (`derived\p11-14\feat.pkl`, read only; floats within 1e-9) |
| C0b (must pass) | scoring reuse | `score_arm("X")` on the P11-12 arm X decisions and sheet (`derived\p11-12\`, read only) gives proposed v0.2 4.25 (to 2 decimals), 423 commits, 34 wrong |

If C0a or C0b fails, the run stops and no result is reported from that code.

## Calibration-inclusive interval (secondary; decision stated here)
**Primary values are single-calibration values.** Reason: the done-when compares with arm X (4.25) and L-FL (6.80), and both are single-calibration values (seed 0). A comparison is fair only on the same footing.

**A calibration-inclusive interval is also reported for LX-FL.** Reason: P11-17 showed that the single-calibration EMG L-FL value (6.80 [4.49, 9.63]) becomes 5.00 [0.00, 9.55] once the calibration draw is counted, because 9 / 40 draws were above alpha on the test set. The wrong-prefix-commit rate of a prefix guard can sit close to alpha in the same way. Any public claim from this item must use the calibration-inclusive interval.

Method (P11-17 procedure, adapted to the external prefix guard; proposed reporting, docs/safe-wpm.md 6b):
- **The same K = 40 calibration draws as P11-17**: seeds s_k = first 8 hex digits of SHA-256(`"p11-17|emg|cal|<k>"`), bootstrap seeds from `"p11-17|emg|boot|<k>"`, and the P11-17 `draw_order` (imported): parts fit / policy / LTT (306 / 459 / 459), resampled with replacement inside each part. So draw k uses the same calibration sample as P11-17 draw k.
- Per draw: refit the LX model on the draw's 765 tuning entries (duplicates kept); certify with `ltt_prefix_threshold` on the draw's 459 LTT entries; controls with `_run_controls` on the draw's inputs in draw order and `default_rng(s_k)` after `permutation(1224)`, null inputs = time-shuffled windows at `sorted(default_rng(s_k).choice(1224, 300, replace=False))`; decide the 1,221 evaluation prompts (real, time-shuffled, zero EMG).
- Credit rule (as P11-17, with proposed v0.2): a draw adds its values only if no calibration control failed, the proposed-v0.2 `safe_wpm` status is `certified` (not `above-alpha`, `vacuous`, `not-certified`), and the test time-shuffled and zero-EMG commit rates are each <= 0.05. Else it adds 0.0.
- Inner level: the P11-17 user-cluster weights (`cluster_weights`, B 2,000, seed 0). Value of a resample = the proposed-v0.2 formula with those weights: 60 x sum(w x credit words) / (sum(w x neural s) + sum(w x correction penalty of `prefix_outcome` penalty chars, wrong commits)). Pooled K x B percentiles (2.5, 97.5); point = mean of the K draw values; plus the variance decomposition.
- **z0 check (must pass before the draws count):** seed 0 without resampling must give exactly the primary LX-FL model, threshold and decisions (1,221 / 1,221 for real, time-shuffled, zero EMG), and the weighted formula with unit weights must equal the `safe_wpm` proposed-v0.2 value (within 1e-9).
- Verdict H5 (descriptive; no pass rule of this item depends on it), as P11-17 against 3.09: "clearly above after calibration uncertainty" (lower end > 3.09) / "above, but inside the combined interval" (mean > 3.09 >= lower end) / "not above". Also reported: statuses of the 40 draws, draw value mean / median / range, fraction above 3.09; and, per draw, the comparison with the P11-17 L-FL draw value of the same k (from `experiments/2026-11-21-p11-17-emg-calibration-ci/results/results.json`; descriptive).
- Not done for BX-FL and LS-FL (cost; they are secondary).
- Known limits as P11-17: pinned decoder, gate, LM, lexicon and feature set; bootstrap duplicates in the LTT part (one draw's certificate is not a valid certificate); prompts, not users, are resampled at the outer level; the evaluation set is the same in every draw.

## Gap rule
- **Gap 126 closes** when the H1 verdict is reported under this plan with C0a and C0b passed, whether H1 holds or not (the done-when allows "or the result states with numbers why not").
- New limits become proposals for new roadmap items and open-gap rows (in the report to the orchestrator; this item does not edit the shared record files).
- No score card in this item (the v0.2 metric is proposed; a v0.2 card is a separate decision).

## Order, outputs
1. Commit this plan before any feature, score, guard or decision. Then commit `run.py` (imports the P11-14, P11-11 and P11-17 code read only; writes per-prompt files only to `derived\p11-16\`), `launch.py` and tests on synthetic data.
2. Run detached from a `git archive` snapshot of the committed code (other agents may change `src/fidetype/`): `python -m fidetype.utils.isolation run --class background --threads 2 -- python -I run.py <stage>`, keep-awake, log `results/run.log`, `DONE` file `C:\Users\zhang\bci-data\derived\p11-16\DONE`. Stages: `feat` (decodes, signals, prefix rows of calibration, null and evaluation windows; C0a) -> `guards` (LX-FL, LS-FL, BX-FL) -> `decide` -> `score` (C0b, verdicts) -> `draws` (z0, k = 1 ... 40) -> `analyse`. Resumable (finished stages and draws are skipped).
3. The repo gets `results/results.json` (aggregates, per-draw counts), `results/guard-*.json` (sheets) and `results/run.log`. No text, no per-user value.
4. No change of data, split, decoder, signals, features, arms, model rule, certification, metric, controls, K, credit rule or pass rules after this commit. Any variant is a new item.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including failures.
