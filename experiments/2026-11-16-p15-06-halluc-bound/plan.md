---
title: P15-06 (F2) risk-controlled fluent-wrong bound - plan
type: experiment
task: P15-06
updated: 2026-11-16
---

# P15-06: a risk-controlled bound on fluent-wrong commits (plan)

Written before any held-out run. Pillar F2 ([north star](../../wiki/questions/north-star.md#f2-faithful-language-model-decoding-e3), [roadmap P15-06](../../wiki/questions/roadmap-standard.md#p15-06-risk-controlled-hallucination-bound)). Input: the P15-05 result ([results](../2026-11-16-f2-e3-llm-grounding/results.md)). Before this plan, the code ran only on `val_select` (the calibration trials): unit tests with a mock LLM, and one design check per arm for A0, B1, C1 and D1 (numbers below). No `val_eval` trial was used.

## Question
P15-05: LLM rescoring lowers WER under the P14-03 trust bound, but the LLM arms commit fluent-but-wrong sentences (B1 2, C1 5, A0 0), and the 95 %-coverage grounding check never stopped one. Can we **bound** the rate of fluent-wrong commits with a stated guarantee, keep the wrong-commit bound and the null controls, and keep the WER gain?

## Loss (what is bounded)
For one utterance and one configuration `lambda`:

- **fluent-wrong loss** `L_h = 1` if the guard COMMITs a text that is **not the truth** (exact word string, after the trust-core normalisation) **and** is **fluent**: LLM log-probability per word `>=` -7.8817. That threshold is the P15-05 fluent threshold (median of the true `val_select` texts, Qwen2.5-1.5B-Instruct Q4_K_M, same prompt), so the loss is the same metric that failed S4. A text whose LLM score is unknown counts as fluent (upper bound of the loss).
- **wrong-commit loss** `L_wc`: the P14-03 loss (wrong COMMIT, monotonised with the wrong-OFFER_WORDS fallback loss, as in `fidetype.trust.risk_control`).

Rates are over **all** utterances (not over commits).

## Guarantee
With exchangeable data (calibration and live utterances from the same distribution, the decoder, the LLM and the fluent threshold fixed):

> `P( R_h(lambda_hat) <= alpha_h  and  R_wc(lambda_hat) <= alpha ) >= 1 - delta_h`, with `alpha_h = 0.01`, `alpha = 0.05`, `delta_h = 0.1`.

In addition, the P14-03 statement `P(R_wc <= alpha) >= 1 - delta` (delta 0.1) still holds, because the chosen `commit_p` is never below the P14-03 `commit_p` and the gate only removes commits; for the same reason the null controls cannot get worse.

What it does **not** say: a bound on wrong commits that the LLM finds non-fluent (they stay under the wrong-commit bound only); any single utterance; another user, day or LLM; that each committed word was said.

## Method
1. **Grounding statistics of the text to commit** (new `fidetype.trust.halluc_bound.CommitGrounding`), on the frame-calibrated log-probabilities that the decoder sees:
   - **sentence deficit** `(log p_ctc(anchor) - log p_ctc(text)) / T` (nats per frame); anchor = base top-1 without the LLM (the P15-05 anchor). `log p_ctc` = CTC forward score of the CMUdict phoneme sequence (best of up to 16 variants, words joined by the SIL label).
   - **word deficit** (the per-word check): Viterbi forced alignment of the text's best variant; for each word, the mean over the frames that the alignment gives to the word's phoneme labels of `max_v log p(v | t) - log p(label | t)`. The statistic is the largest word deficit. A text with an out-of-lexicon word gets `inf` for both.
2. **Commit grounding gate** `HallucGate(tau_commit, tau_word)`: a COMMIT passes only if sentence deficit `<= tau_commit` and max word deficit `<= tau_word`; otherwise it becomes the no-commit decision of the same policy (offer or withhold; as the M2-18 commit gate). It acts on the **committed text only**; offers are unchanged.
3. **Joint Learn then Test** over `lambda = (commit_p, tau_commit, tau_word)`:
   - grid: `commit_p` in {inf, 1.00, 0.99, ..., 0.00} (102), `tau_commit` in {0, 0.002, 0.005, 0.01, 0.02, 0.05, inf} (7), `tau_word` in {0.25, 0.5, 1, 2, 4, inf} (6): 4,284 points (the module defaults).
   - per point, `H_lambda: R_wc > alpha or R_h > alpha_h`; p-value `max(p_wc, p_h)`, exact binomial.
   - the order of the tests comes from the 271 policy-grid items of the P14-03 split (smallest p-value first; ties: fewer commits, then stricter); fixed-sequence testing on the 271 LTT items certifies the chain prefix with all p-values `<= delta_h`. With 271 test items, `alpha_h = 0.01` is certifiable only with 0 fluent-wrong commits on them (`0.99^271 = 0.066 <= 0.1`).
   - **selection (primary)**: among certified points with `commit_p >=` the P14-03 `commit_p`: fewest fluent-wrong commits on the 542 ordering + test items, then most right commits, then fewest commits, then strictest. **Secondary (descriptive)**: rule `most_right` (most right commits first), for B1 and C1 only.
   - no certified point: the guard never commits.
4. Public API: `fidetype.trust.calibrate(..., grounding=CommitGrounding(...), llm=scorer, halluc_alpha=0.01, fluent_threshold=-7.8817)`. Defaults unchanged (no `grounding`, no `llm`: the P14-03 guard, same `config_id`). The guarantee sheet gets a hallucination-bound block.

## Setup
| item | value |
|---|---|
| data | T15, the P15-05 sets: fit `val_select` (722), held out `val_eval` (701) |
| arms | the 8 P15-05 arms (A0 ... D1), same pipelines, same LLM weight 1.0, same P15-05 grounding (`tau` 0.0806) in the X1 arms; P15-06 adds the joint LTT and the commit gate to each |
| caches | P15-05 base n-best and LLM scores / rewrites (`derived/f2-e3-llm-grounding/`, read only; the LLM sqlite is copied to `derived/p15-06-halluc-bound/`). Expected: no new base decode, few new LLM scores (rewrites in C / D that P15-05 never scored), CPU only, 4 threads |
| controls | built-in `calibrate` controls of the final guard (same inputs as the P14-03 step); held-out uniform 300 + shuffled 300 (the same seeded draws as P15-05); swapped signal on all 701 (the same derangement as P15-05) |

## Design check (val_select only, before this plan)
In-sample counts on the 542 ordering + test items (not a test; they set the expectation):

| arm | P14-03 `commit_p` | P14-03 guard: commits / right / fluent-wrong | P15-06 primary: selected `(commit_p, tau_commit, tau_word)` | commits / right / fluent-wrong |
|---|---|---|---|---|
| A0 | 0.30 | 5 / 3 / 0 | (0.31, 0, 0.5) | 4 / 3 / 0 |
| B1 | 0.40 | 9 / 6 / 3 | (0.65, 0, 0.25) | 1 / 1 / 0 |
| C1 | 0.30 | 22 / 14 / 6 | (0.42, 0, 0.5) | 5 / 5 / 0 |
| D1 | 0.30 | 29 / 22 / 2 | (0.37, 0, 0.5) | 9 / 7 / 0 |

- The would-be commits (at `commit_p = 0`) of B1: 33 right, 33 fluent-wrong, 68 non-fluent wrong. Their `p_top1` ranges overlap; word deficits separate them only in part (median 0.15 right vs 0.50 fluent-wrong). Sentence deficits are 0 for most texts (the top-1 is the base top-1).
- **Expectation:** the bound will hold and fluent-wrong commits will fall, but the guard will commit much less (B1 about 1 in 542 in-sample). The "most_right" rule keeps more commits but allows fluent-wrong commits on the ordering items.

## Pre-registered success criteria (held-out `val_eval`, 701 trials)
Primary arm: **B1** with the primary rule. Comparisons: P15-05 A0 (baseline) and P15-05 B1.

1. **H1 bound:** `calibrate` returns a guard with a feasible hallucination bound (a certified point), and on held-out data the fluent-wrong commit rate `<= 0.01` and the wrong-commit rate `<= 0.05`.
2. **H2 fluent-wrong vs baseline:** fluent-wrong commits(B1, P15-06) `<=` fluent-wrong commits(A0, P15-05) = 0.
3. **H3 controls:** held-out uniform and shuffled commits `<= 1 / 300` each; swapped-signal commits that are not the truth of the signal `<= 2 / 701`; the built-in controls of the final guard pass.
4. **H4 WER gain kept:** the pipeline top-1 (so WER) equals P15-05 B1 on all 701 trials (the gate changes only the commit decision), so WER(B1) < WER(A0) with the P15-05 bootstrap interval below 0.

**P15-06 pass** = H1-H4 for B1. **Utility (reported, does not decide the pass):** right commits of B1, P15-06 vs P15-05 (8); a guard that keeps fewer than half (< 4) is "safe but costly", and we say so. Secondary (descriptive): the same checks for all arms and for the `most_right` rule (B1, C1); the per-arm effect against the matching P15-05 arm.

## Honest limits (known before the run)
- One participant, one split, one LLM; commit counts are small (P15-05: 2 to 29 of 701), so held-out rates are coarse (CP95 intervals reported).
- With 271 LTT items, `alpha_h = 0.01` needs zero fluent-wrong commits on them. A tighter `alpha_h` needs more calibration data.
- The fluent threshold and the P14-03 frame temperature were fitted on all of `val_select` (P15-05), which includes the LTT items. They define the loss and the input; this is a small reuse, stated here.
- "Fluent" is the judgement of the same LLM that rescored the list.
- T12 v2 is not run here (P15-05 T12 is still open, run by another agent).

## Outputs
- Repo: `run.py`, `config.json`, `launch_detached.py`, `report.py`, `results/results-t15.json` (aggregates), `results/explore-*.json` (design check), `results/run.log`, `results.md`.
- Per-trial outputs, guard files, calibration item statistics, the LLM cache copy: `C:\Users\zhang\bci-data\derived\p15-06-halluc-bound\` only.
