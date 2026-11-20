---
title: P11-14 guard confidence for the in-beam LM EMG decoder - pre-registration
type: experiment
task: P11-14
updated: 2026-11-19
---

# P11-14: a guard confidence for the in-beam LM decoder (pre-registration)

Written and committed **before** any decision on an evaluation (track-test) prompt was computed or read with a new confidence. Gap 123 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-14](../../wiki/questions/roadmap-standard.md#p11-14-guard-confidence-for-the-in-beam-lm-decoder). Follow-up of [P11-07](../2026-11-20-p11-07-emg-beam-lm/results.md) and [P11-12](../2026-11-20-p11-12-emg-nosignal-gate/results.md).

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled and over-user aggregates only: no per-user value, no user pseudonym, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true` (FEP-0010). Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-14\`. The P11-01, P11-07, P11-09, P11-11 and P11-12 files are read only.

CPU only (isolation runner, class `background`, 2 threads). **No GPU.**

## Problem (from P11-07)
The in-beam LM decoder gets the top-1 intended text right more often (gated top-1 exact 32.4 % vs 24.0 % in P11-12). But the certified safe WPM v0.1 is lower: arm S 3.37 [1.92, 5.18] vs 4.10 (P11-12), arm SL 3.16 vs 5.08. The error among commits rose (0.279 vs 0.210). The confidence of arm S is the posterior of the top-1 text in the decoder's own n-best (fused scores, temperature fitted by `calibrate`). With beam 8 the n-best has at most 8 key sequences, and the LM term is in every score. So the posterior can be high on a wrong text when the acoustic evidence is weak.

## Question
Does a confidence that separates the acoustic evidence from the LM evidence give a certified, non-vacuous safe WPM v0.1 for the in-beam LM decoder that is at least the P11-12 value (4.10, arm S) and above the best `intended_text` entry (5.08, P11-12 arm SL), with the same split, gate, certification and controls?

## What was done before this plan (disclosure)
Reading of the P11-07, P11-09, P11-11, P11-12 and P11-13 code and results, and of `fidetype.trust.dropin` / `commit_score` / `risk_control`. No new decode, no feature, no score and no decision was computed on any real window (calibration or evaluation) before this commit. The numbers above come from the committed result pages.

## Data and splits (as P11-12 / P11-07, unchanged)
- 8 P11-01 test users. Per user: track-val session = calibration (1,224 prompts), track-test session = evaluation (1,221 prompts). `check_track_splits` checks it. Unit-list digests must equal P11-09.
- Windows: P11-09 `derived\p11-09\lp\` (33-class key form; real, input-level time-shuffled, zero EMG); window = prompt frames + 0.20 s.
- Target: the intended text (Backspace applied, the P11-11 `resolve` rule).
- **Tuning items T** = the calibration prompts at the first 765 positions of calibrate's order (`default_rng(0).permutation(1224)`; digest `96f175801d6ff225`): the fit and policy-grid parts. The 459 LTT positions, the 300 null-control windows and every evaluation window are never used to fit, select or tune.

## Decoder (unchanged from P11-07)
`decode_fn` path: P11-12 no-signal gate (`derived\p11-12\gate.json`: k_min 15, r_min 1.842, r_max 17.276) -> P11-07 in-beam LM beam ([lmbeam.py](../2026-11-20-p11-07-emg-beam-lm/lmbeam.py), prune -8, beam 8) on the 33-class window -> intended texts merged (log-sum-exp of the fused scores), top 20 -> P11-11 OOV gate (0.5) on the top-1 -> empty texts dropped. If the gate or the OOV gate fails, or the best merged text is empty, the n-best is empty and the guard withholds. **The commit text (the top-1) is the same for every arm of one decoder.** Two decoders (tuned in P11-07 on the same tuning items):

| Decoder | w | beta | lam | Note |
|---|---|---|---|---|
| **FL** | 0.25 | 1 | 8 | the P11-07 guard decoder (LM + research-only lexicon term) |
| **F** | 0.5 | 1 | 0 | the P11-07 primary decoder (licence-clean LM only); window top-1 exact 34.2 % (FL 32.7 %) |

## Confidence signals (per window, fixed here)
- **Competitor set U** = the decoder's final beam (at most 8 key sequences) together with the P11-11 no-LM key beam (beam 64, 64-best; cache `derived\p11-11\nbest.pkl`, read only; a missing window is decoded with the same P11-11 function `beam_nbest`).
- For each key sequence k in U: `ac(k)` = **exact CTC log-likelihood** of k on the window (forward algorithm, our own code; no LM); `lm(k)` = Tatoeba 6-gram `score_sentence` of its intended text, minus `lam` x (out-of-lexicon words of the intended text, words normalised as in P11-07) for FL; `fused(k) = ac(k) + w * lm(k) + beta * len(k)`. Key sequences with the same intended text are merged (log-sum-exp).
- Let t = the commit text (top-1 of the decoder path above). Signals:

| Signal | Definition |
|---|---|
| `p_nb` | posterior of t in the decoder's own merged n-best (fused scores, temperature 1): the P11-07 arm S signal |
| `p_fU` | fused posterior of t over U (softmax of the merged `fused`) |
| `p_aU` | **acoustic-only posterior** of t over U (softmax of the merged `ac`; LM weight 0) |
| `agree_b0` | 1 if t equals the intended text of the no-LM beam-64 top-1, else 0 |
| `agree_g` | 1 if t equals the intended text of the greedy CTC path, else 0 |
| `dist_g` | character Levenshtein distance between t and the greedy intended text / max(1, len(t)) |
| `ac_gap` | (largest merged `ac` in U - merged `ac` of t) / max(1, len(t)) |
| `lm_pc` | `score_sentence(t)` / (len(t) + 1) |
| `log_nw` | log(1 + words of t) |
| `kps` | greedy key emissions per second of the window (the gate statistic) |

A temperature on the fused n-best is **not** a separate arm: `calibrate` already fits a sentence temperature on the fit part for `p_top1` (arm P below is that).

## Arms (fixed here)
| Arm | Confidence c | How the guard sees it |
|---|---|---|
| **P** | `p_nb` | the native merged n-best (text, fused score): exactly the P11-07 arm S protocol |
| **A** | `p_aU` | two-item n-best `[(t, log c), ("", log(1 - c))]`, c clipped to [1e-6, 1 - 1e-6] |
| **L** | learned: logistic regression on the 10 signals (logit of `p_nb`, `p_fU`, `p_aU`, clipped to [-12, 12]; the others as defined) | two-item n-best as for A |
| BL | `calibrate(confidence="learned")` (the built-in P5-23 score) with n-best items that carry `logp_acoustic` (merged exact `ac`) and `logp_lm` | native merged n-best (dicts) |

- **Two-item n-best** (A, L): the empty item is a reject item. The M2-18 commit gate never commits an empty text, so the guard can commit t only when c > 0.5, and `calibrate` then sees `p_top1 = sigmoid(logit(c) / T)` (T fitted on the fit part), which is monotone in c. So LTT certifies a threshold on c. The commit text is t in every case.
- **L model:** features standardised on the tuning items and clipped to their range; L2 logistic regression (`fidetype.trust.commit_score.fit_logistic`, l2 1.0, intercept not penalised); sign constraints with backward elimination (one feature per step, the largest wrong-sign weight first): + for the three posteriors, `agree_b0`, `agree_g`, `lm_pc`; - for `dist_g`, `ac_gap`; free for `log_nw`, `kps`. Label = t equals the truth. Fit on all 765 tuning items for the guard. The model is frozen before `calibrate` runs; a digest of its parameters is part of `decoder_version`.
- Candidate set for the primary: {P, A, L} x {F, FL} (6 candidates). BL x {F, FL} is secondary only (its score is fitted inside `calibrate`, so the tuning criterion below cannot be computed for it the same way).

## Selection of the primary arm (tuning items only; fixed here)
For each of the 6 candidates, on the 765 tuning items:
1. `committable` = gate pass, OOV gate pass and t non-empty; `right` = t equals the truth (word split).
2. Score s: P -> `p_nb`; A -> `p_aU`; L -> **5-fold cross-validated** out-of-fold probability (folds = `default_rng(0).permutation(765)` cut into 5 contiguous parts; the same fit rule inside each fold). Items that are not committable get s = -inf.
3. Simulated certification: `fidetype.trust.risk_control.ltt_threshold(s, 1 - right, alpha 0.05, delta 0.1, DEFAULT_LTT_GRID, pvalue "binomial")` -> threshold; commits = committable and s >= threshold.
4. Criterion = `fidetype.benchmark.safe_wpm.safe_wpm(..., guarantee=None)["unguarded_wpm"]` of these commits (v0.1, per-prompt neural time, truth lengths). Highest wins. Ties: fewer wrong commits, then arm order P, A, L, then decoder F before FL.

The selected candidate is the **primary arm `*`**. The criterion values of all 6 and the tuning AUROC of every signal (right vs wrong among committable items) are reported.

## Certification and evaluation (as P11-12 / P11-07)
Per arm: `fidetype.trust.calibrate` (alpha **0.05**, delta **0.1**, LTT, seed 0, `null_trials` 300, `null_inputs` = the same 300 input-level time-shuffled calibration windows, automatic uniform and frame-shuffled controls; `input_kind="logits"`, key-CTC vocabulary, `audit_text=False`; arm P, A, L with `confidence="p_top1"`, BL with `confidence="learned"`). Decisions on the 1,221 evaluation prompts: real, time-shuffled, zero EMG. Scoring: the P11-11 functions `score_arm` and `verdicts` (safe WPM v0.1 adopted, proposed v0.2 and v0.2 + reading cost; user cluster bootstrap B 2000, seed 0; Clopper-Pearson at **level 0.95**; no-BCI reference 3.09). All 8 arms (P, A, L, BL x F, FL) are calibrated, decided and scored; the primary verdicts use `*` only.

## Hypotheses and verdicts
| Id | Statement | Pass rule |
|---|---|---|
| **H1 (primary, gap 123 done-when)** | `*` gives a certified, safe, non-vacuous value at least the P11-12 value | `*`: V1 certified, V2 holds, V3 non-vacuous (v0.1), V6 pass, and safe WPM v0.1 >= 4.10 |
| **H2** | `*` beats the best `intended_text` entry | H1 holds and safe WPM v0.1 > 5.08 (P11-12 SL) |
| H3 | the new confidence beats the P11-07 confidence on the same decoder | value of `*` > value of arm P of the same decoder |
| H4 | `*` is above no-BCI | V4 "above" 3.09 (no level predicted) |
| C0 | reproduction | arm P with decoder FL gives the P11-07 arm S result: the same LTT threshold, commits and wrong commits (154 / 43), safe WPM v0.1 3.37 |
| V6 | controls | as P11-12: the three calibrate controls <= 15 / 300, and the evaluation time-shuffled and zero-EMG commit rates <= 0.05 |

Reported for every arm: V1-V6, value with CI, commits, wrong commits with CP95, error among commits, threshold, control counts, offline decision time (decode memoised); per signal the test AUROC (right vs wrong among committable real evaluation windows; descriptive).

## Gap rule
- **Gap 123 closes** when the primary arm's verdicts are reported under this plan: with H1 if it holds, or with the numbers that say why not (the roadmap done-when allows both).
- New limits become roadmap items and open-gap rows.
- The records say whether P15-25 (gap 91) should use this decoder and confidence: yes if H1 holds; else it keeps the P11-12 decoder for certified commits and may use the P11-07 decoder for accuracy only.

## Score card
Only if `*` passes H2 (certified, safe, non-vacuous, V6 pass, value > 5.08): a declared-subset `intended_text` card by the P11-13 convention (rerun recipe with `code_ref`), leaderboard regenerated, `python -m fidetype.benchmark.leaderboard --check`. No card for a secondary arm.

## Order, limits, outputs
1. Commit this plan before any real-window feature, score or decision. Then the code (run.py, tests on synthetic data, launch.py).
2. Stages (detached, isolation class `background`, 2 threads, one process, log `results/run.log`, per-window files in `derived\p11-14\`, `DONE` at the end): `feat` (decodes and signals of the calibration windows and the null windows) -> `select` (tuning criterion, L fit) -> `guards` -> `decide` -> `score`.
3. No change of split, window, decoder, gate, signal, arm, selection rule, metric or controls after this commit. Any variant is a new item.

Write-up: `results.md` in this folder with the verdicts and numbers as computed, including failures.
