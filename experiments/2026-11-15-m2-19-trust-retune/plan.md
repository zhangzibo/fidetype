---
title: M2-19 trust config re-tune for the M4-12 decoder - pre-declared plan
type: experiment-plan
task: M2-19
updated: 2026-11-15
---

# M2-19: re-tune the trust configuration for the retrained T15 decoder (plan, written and committed before any run)

## Why
- M4-12 retrained our causal GRU-CTC decoder on Brain-to-Text '25, participant T15 (CC0). On `val_eval` (701 trials) the dedicated L 0 model has greedy PER 0.2574 and WER (T = 1) 0.3998 ([M4-12 results](../2026-11-14-m4-12-decoder-retrain/results.md)).
- M4-12 applied the frozen trust config `tcfg-f5ca0020b3b8fce2` unchanged. Result: 0 commits (701/701 OFFER), eWPM 5.94 (dedicated L 0) vs gaze 4.02. The trust layer adds no COMMIT value.
- That config was made for another decoder on other data. So it is not a valid config for this decoder.

## Where the old frozen config came from (facts from the repo)
| item | value |
|---|---|
| file | `experiments/2026-11-13-m4-06-real-replay/configs/trust-config-b2t25-ours-splitA.json` (M4-06) |
| decoder input | the **online** phoneme logits in `t15_copyTask.pkl` (published online RNN, 1,628 trials with the 125k vocabulary), not our GRU |
| word decoder | `experiments/2026-11-10-b2t25-trust` `Decoders.words_fn` (CMUdict + Tatoeba word unigram + char 6-gram; lm_weight 1.0, edit_penalty 12, word_bonus 3) |
| split | fixed split A: first half of each post-implant day = fit (812); fit-A = alternate fit trials per day (0::2, 411) for temperatures, conformal, guard and the policy grid; clean calibration = the other fit trials (1::2, 401) for LTT |
| recipe | `paper1_v4_harness_config` (git tag `paper1-v4-frozen-config`): guard on (combine max); policy grid = max eWPM s.t. plug-in wrong-commit <= 0.05 on fit-A; then LTT on the clean half |
| guarantee | LTT, alpha 0.05, delta 0.1, exact binomial p-value (`ltt-binomial`), fixed-sequence grid 1.00 -> 0.00 step 0.01, combine max |
| fitted values | frame T 3.8151, sentence T 4.4440, LTT lambda_hat 0.00 (n 401), final commit_p 0.3 (from the grid), commit_max_risk 0.1, offer_max_k 2 |

## Decoders (no decoder changes)
| role | run | checkpoint | L |
|---|---|---|---|
| **primary** | `m4-12-fixed0` (dedicated L 0) | `C:\Users\zhang\bci-data\runs\m4-12-fixed0\best.pt`, sha256 `2b92ab33…51fd5` | 0 |
| secondary | `m4-12-shared` | `C:\Users\zhang\bci-data\runs\m4-12-shared\best.pt`, sha256 `4627040f…5ad2` | 0 |

Word route: the same `Decoders.words_fn` with the same tuned parameters as M4-06 / M4-12 (fixed upstream; not re-tuned here).

## Splits (exact choice)
All from the T15 `t15_copyTask_neuralData` derived files of M4-01/02 (`C:\Users\zhang\bci-data\derived\m4-01-02-lookahead\<session>.npz`, read only; trials whose words are all in CMUdict, as in M4-01/02/12).

| split | definition | n | use here |
|---|---|---|---|
| train | dataset `train` trials | 8,065 | decoder training only (M4-12). **Not used.** No train hold-out exists: the decoder saw all train trials. |
| `val_select` | dataset `val` trials with an even index inside their session | 722 | **all trust fitting and calibration** |
| fit-A | `val_select` trials at positions 0::2 inside each session (session order of `sessions.json`, then index order) | 371 | `pipe.fit(fitA, fitA)`: frame T and sentence T (first half of fit-A), conformal (second half), guard, policy grid (all fit-A) |
| clean cal | `val_select` trials at positions 1::2 inside each session | 351 | LTT calibration of commit_p only |
| `val_eval` | dataset `val` trials with an odd index inside their session | 701 | **final evaluation only**. Never used for any fit or choice in M2-19. |

- `val_eval` gave the M4-12 decoder numbers. So we calibrate on `val_select`, which is disjoint from `val_eval` (no trial in both).
- Caveat (written down before the run): M4-12 used `val_select` to choose the checkpoint (lowest val_select PER). In all M4-12 runs the best step was the last step (10,000), so the selection did not change the weights we would have taken anyway. We expect no material bias. We report it as a limitation.
- `val_select` and `val_eval` interleave inside the same 41 sessions, so the exchangeability assumption of LTT is plausible for the session mix (not per session).

## Risk and guarantee
- **Risk** = wrong-commit rate: the fraction of **all** trials on which the final action is COMMIT and the committed text is not the truth (normalised words, as in the harness). `max_attempts` = 1.
- **Method**: as our existing code does it, unchanged: `paper1_v4_harness_config(seed=0, user_config=UserConfig.aac_gaze(159.3 cpm))`; `pipe.fit(fitA, fitA)` with `risk_control="none"` (grid step), then `pipe.config = v4`; `pipe.calibrate_commit(clean_cal)` = `CommitRiskControl(method="ltt")`.
- **Target**: alpha = **0.05**, delta = **0.1** (same as the old frozen config; no reason to change). Exact binomial p-value, fixed-sequence testing over the grid 1.00 -> 0.00 step 0.01, combine `max` (final commit_p = max(grid commit_p, LTT lambda_hat)).
- **Guarantee claimed**: P( R(lambda_hat) <= 0.05 ) >= 0.9 over the draw of the calibration trials, if the calibration and test trials are exchangeable. If no lambda passes, LTT gives +inf (never commit); we report that as the result.
- Freeze with `FrozenTrustConfig.from_pipeline` (recipe record = `PAPER1_V4_RECIPE` + this split). Commit the config file (numbers and settings only, no per-trial data). Only then evaluate on `val_eval`.

## Search grid (fixed, the code defaults)
- Policy grid `fidetype.trust.policy.DEFAULT_GRID`: commit_p {0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 1.01} x commit_max_risk {0.1, 0.2, 0.3, 0.5, 1.0} x offer_max_k {0, 1, 2, 3, 5, 8} x abstain_risk {0.6, 0.8, 1.01} x final_fallback {offer, abstain}; objective max eWPM s.t. plug-in wrong-commit <= 0.05 on fit-A. No OFFER_WORDS (as the old config).
- LTT grid: lambda = 1.00, 0.99, …, 0.00.

## Evaluation on `val_eval` (701 trials), each decoder
Frames route through `StreamingTrustLayer` (one session per T15 session, a header per trial, `max_attempts` = 1), as in M4-12. eWPM from the harness user simulation fed the streaming decisions (`ReplayPolicy`), user `UserConfig.aac_gaze(159.3 cpm)`, fallback typing 20 chars/min.

### Primary metrics (dedicated L 0)
1. Commit rate (n commits / 701).
2. Wrong-commit rate (n / 701) with a two-sided Clopper-Pearson 95 % CI. Also the error rate among commits.
3. **Guarantee check**: "holds on the held-out trials" = observed `val_eval` wrong-commit rate <= 0.05. We also report whether the CP95 upper bound is <= 0.05 (a stronger statement). One test draw cannot prove or disprove a 1 − delta probability statement; we say so.
4. eWPM of the re-tuned config vs (a) gaze typing alone, (b) always-commit with the new frame T, (c) the old frozen config (M4-12: 5.94 for dedicated L 0).
5. Action mix (COMMIT / OFFER / ASK / ABSTAIN / OFFER_WORDS counts).
6. Stream == batch: streaming decisions vs the batch harness with the same frozen parts (action and committed text, `==`), n / 701.

### Secondary (reported, no decision depends on them)
- Same recipe, same splits, on the `shared` model at L 0.
- CRC sensitivity on dedicated L 0: same fit-A grid step, then `calibrate_commit(clean_cal, method="crc")` at alpha 0.05 (marginal guarantee E[R] <= 0.05). Reported next to LTT; LTT stays primary.
- Controls on a 300-trial draw of `val_eval` (rng seed 0), dedicated L 0, re-tuned config: frame-shuffled log-probs and uniform log-probs. Report commits (expect 0).
- Fitted values: frame T, sentence T, conformal q, grid commit_p, LTT lambda_hat and bound, final commit_p, the grid winner.
- Calibration-side numbers on clean cal (commit rate, wrong-commit) for context.

## Decision rules (pre-declared)
- **Success** (the trust layer now adds COMMIT value safely) if all hold for dedicated L 0: commit rate > 0; `val_eval` wrong-commit <= 0.05; eWPM > the old frozen config (5.94); stream == batch 701/701.
- If LTT is infeasible or commit_p ends > 1 (no commits): report "no safe COMMIT is possible at alpha 0.05, delta 0.1 with this decoder and n = 351", with the clean-cal numbers that show why. We do not change alpha, delta or the split after seeing results. Any extra analysis then is labelled post hoc.
- If `val_eval` wrong-commit > 0.05: we report the guarantee as **not met on this draw** and keep the config (no re-fit on `val_eval`).

## Outputs and safety rules
- New decodes (`val_select` and a `val_eval` re-decode for an equality check against the M4-12 log-probs) go to `C:\Users\zhang\bci-data\derived\m2-19-trust-retune\` only. File names carry `m2-19`. Nothing is written to `derived\m4-01-02-lookahead` or `derived\m4-12-decoder-retrain` (read only).
- GPU decode with the ROCm venv (`C:\venvs\fidetype-rocm`, one GPU job). CPU stages through `fidetype.utils.isolation run --class background --threads 4`.
- The repo gets aggregate numbers and the frozen config JSON only. No per-trial text, no log-probs, no checkpoints.
- No `src/` change is planned.
