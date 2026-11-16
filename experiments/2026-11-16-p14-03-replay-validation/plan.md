---
title: P14-03 replay validation of the drop-in trust API - plan
type: experiment
task: P14-03
updated: 2026-11-15
---

# P14-03: held-out wrong-commit of the drop-in API on two public replay sets (plan)

Written before any validation run. Task: close the P14-03 done check "held-out wrong-commit <= alpha on two public replay sets" ([roadmap](../../wiki/questions/roadmap-standard.md)).

## Rule: use the API as an outside user
- Only the public API: `fidetype.trust.calibrate(...)` -> `TrustGuard.decide(x)`. No `_private` call, no harness call, no hand-set threshold.
- Input: the recorded decoder output (CTC log-probabilities per trial, `(T, 41)`), the true sentence, our own text decoder as `decode_fn` (an outside user brings their own beam search with an LM).
- The eWPM replay uses the public `SimulatedUser.respond` and `fidetype.eval.ewpm.summarize` on the guard decisions (same user models as the earlier experiments, one attempt per trial). It is a secondary number.

## API issue found while reading the code (before the run)
`calibrate` fits the frame temperature on the true **texts**. With `decode_fn`, the texts can be in another space than the decoder tokens (here: words vs phonemes). Then the frame temperature is fitted against wrong targets. Check on 180 T15 `val_select` trials: frame T 6.58 with word texts, 1.24 with phoneme texts (M2-19: 1.2385). The guarantee (LTT on the final decisions) stays valid, but the guard loses most of its evidence.

Fix (in `src/fidetype/trust/dropin.py`, with a test; public signatures kept, one new optional keyword):
- New keyword `stream_texts=`: the truth in the token space of the decoder (here the phoneme symbol string). It is used only for the frame temperature.
- With `decode_fn` and no `stream_texts`: the frame temperature stays 1.0 (not fitted), and the guarantee sheet gives a warning.
- Without `decode_fn` (built-in decoder): unchanged (the texts are in the token space).
- `HarnessConfig` gets `fit_frame_temperature: bool = True` (default keeps every old result).

## Sets and splits (fixed now)
| | Set 1: T15 (Brain-to-Text '25, CC0) | Set 2: T12 (Brain-to-Text '24, CC0) |
|---|---|---|
| decoder output | M4-12 `m4-12-fixed0` (dedicated L 0), recorded log-probs | M3-28 v2 GRU-CTC (`5317b060...`), recorded log-probs |
| calibration | `val_select`: the 722 even-index `val` trials (file `derived/m2-19-trust-retune/logprobs-m2-19-m4-12-fixed0.npz`, read only) | trust pool of the 14 `fit_a` + `calibration` sessions (480 trials) |
| held out | `val_eval`: the 701 odd-index `val` trials (file `derived/m4-01-02-lookahead/logprobs-m4-12-fixed0.npz`, read only) | trust pool of the 10 `test` sessions (400 trials) |
| split kind | by trial (index parity inside each session; the M4-12 / M2-19 rule) | by session (time order; the M3-28 pre-registration rule) |
| `decode_fn` | B2T '25 word route (`experiments/2026-11-10-b2t25-trust` `Decoders.words_fn`, tuned `lm_weight`, `edit_penalty`, `word_bonus`) | same word route + Tatoeba word trigram beta 2.0 (M3-28 v2 config) |
| `stream_texts` | CMUdict phoneme symbol string of each trial | same |
| simulated user (eWPM) | `UserConfig.aac_gaze(chars_per_min = B2T '25 speech rate)` | `UserConfig.aac_gaze(chars_per_min = 304.0)` |
| earlier result | M2-19 `tcfg-e7e8c472f6d9ab33`: 9/701 commits, 6 wrong, 0.0086 [0.0031, 0.0185] (harness, no gate) | M3-28: 1/400 commits, 0 wrong (frozen recipe, not the drop-in) |

`calibrate` makes its own seeded split of the calibration set (seed 0): 25 % fit, 37.5 % policy grid, 37.5 % LTT. Calibration and held-out sets share no trial. The held-out set is used for nothing else.

Why T12 for set 2: it is the cheapest honest choice. The log-probs of all trials are on disk, the route is the same (logits + `decode_fn`), the licence is CC0, it is a second participant and a second dataset, and a by-session split is already defined. Not chosen: emg2qwerty LDA (CC BY-NC; the n-best route needs the user's own null n-best inputs, which we do not have on disk; the decoder is almost always wrong), Willett handwriting (no decoder output on disk), KT-sEMG (no n-best on disk). Honest limits of T12: the test sessions were decoded once before (M3-28, aggregates only), and the decoder family is the same as for T15.

## Runs
- alpha 0.05 (primary) and alpha 0.10 (secondary), delta 0.1, all other `calibrate` arguments at their defaults (`null_trials` 300, `null_max_commit_rate` = alpha).
- Per set and alpha: `calibrate` on the calibration set, then `guard.decide` on every held-out trial, once, in file order.
- CPU only, `fidetype.utils.isolation run --class background --threads 4`.
- Per-trial outputs (decisions, audit logs) only in `C:\Users\zhang\bci-data\derived\p14-03-replay-validation\`. The repo gets aggregates and the guard files (no signal, no text).

## Reported per set and alpha
Null-control results (from the guarantee sheet), held-out commits, wrong commits, wrong-commit rate (wrong COMMITs / all held-out trials) with a Clopper-Pearson 95 % interval, error among commits, COMMIT / OFFER / WITHHOLD counts, eWPM (secondary), frame T, commit threshold, config id.

## Pass rule (fixed now)
Per set, at alpha 0.05:
- **Pass:** `calibrate` returns a guard (both null controls pass) **and** the held-out wrong-commit rate <= 0.05.
- **Fail:** the held-out wrong-commit rate > 0.05.
- **Refused:** `calibrate` raises `NullControlError`. This is reported as a finding. It is not a pass. The controls are not weakened.
- A pass with 0 held-out commits counts as a pass of the literal check, but it is reported as "vacuous" (the guard never commits).
- We also report whether the CP95 upper bound is <= alpha (a stronger statement; not part of the pass rule).

The P14-03 check passes if both sets pass at alpha 0.05. alpha 0.10 results are descriptive only.

One draw per set cannot prove a `1 - delta` statement. The check tests that the API, used as documented, does not break the bound on real held-out data.
