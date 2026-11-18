# Safe WPM: words per minute at a guaranteed wrong-commit rate

Roadmap item: P14-05. Code: [`src/fidetype/benchmark/safe_wpm.py`](../src/fidetype/benchmark/safe_wpm.py). Baselines: [experiments/2026-11-16-p14-05-safe-wpm](../experiments/2026-11-16-p14-05-safe-wpm/results.md). Leaderboard column: "Safe WPM @ alpha" in [`benchmark/site/leaderboard.md`](../benchmark/site/leaderboard.md).

Safe WPM is one number that tells a user what the system gives them. It counts the words that the system types by itself and gets exactly right. It counts these words only when the trust layer has a certified limit on the wrong-commit rate.

## 1. Definition (`safe-wpm/0.1`)

A session has N trials. Each trial has one intended sentence y_i. For each trial:

| Symbol | Meaning |
|---|---|
| `neural_s_i` | Time of the neural input, in seconds. Use the measured trial duration if the dataset has it. Otherwise use the track rate model `len(y_i) * 60 / chars_per_min`. The report states which one (`timing`). |
| `committed_i` | The trust policy COMMITs a text. The user does nothing. |
| `correct_i` | The committed text equals y_i exactly, after the text normalisation of the track. |

```
credit_i  = words(y_i)   if committed_i and correct_i
          = 0            otherwise
time_i    = neural_s_i + [committed_i and not correct_i] * penalty_i
penalty_i = 2.0 s + (2 * 60 / 152) s/char * len(y_i)

safe WPM  = 60 * sum_i credit_i / sum_i time_i
```

`words(y)` is the number of words separated by spaces.

## 2. Rules

| Case | Words | Time |
|---|---|---|
| Commit, exactly right | `words(y_i)` | `neural_s_i` |
| Commit, wrong | 0 | `neural_s_i` + correction penalty |
| Offer (the user must choose) | 0, also if the right text is in the list | `neural_s_i` |
| Withhold or abstain | 0 | `neural_s_i` |

1. **Only committed text counts.** Offered text needs a user action, so it is not "typed by the system". The eWPM column already credits offers through the simulated user.
2. **A wrong commit costs a correction.** The user deletes the text and writes the sentence again. The time uses the correction constants of the `aac-gaze-v1` user model (`UserConfig.correction_overhead_s` = 2.0 s, `correction_s_per_char` = 2 * 60 / 152 s). The rewritten words do not count, because the BCI did not make them. `CorrectionRule(name="none")` turns the penalty off. That variant is optimistic and is not the headline number (`wpm_no_penalty` reports it).
3. **The value needs a certified bound.**
   - `ltt` (Learn then Test): P(wrong-commit rate <= alpha) >= 1 - delta, over calibration draws.
   - `crc` (conformal risk control): expected wrong-commit rate <= alpha. CRC has no delta.
   - Any other policy (always commit, a plug-in threshold) gets status `not-certified` and no value. `unguarded_wpm` gives the same formula for reference only.
4. **Measured rate above alpha.** If the wrong-commit rate on the scored trials is above the stated alpha, the status is `above-alpha`. The leaderboard shows `! ABOVE alpha`.
5. **No commits.** If the policy commits nothing, the status is `vacuous` and the value is 0.0. The policy is safe, but it gives no value.

## 3. What each entry reports

| Field | Content |
|---|---|
| `value`, `ci` | Safe WPM and its 95 % percentile cluster bootstrap CI (track unit; none for one-participant replay sets) |
| `status` | `certified`, `above-alpha`, `vacuous`, `not-certified` |
| `method`, `alpha`, `delta`, `n_cal`, `calibration` | The declared bound and the calibration size |
| `measured_wrong_commit`, `measured_wrong_commit_cp95` | Wrong commits / all scored trials, with the Clopper-Pearson 95 % interval |
| `n_commits`, `n_wrong_commits`, `error_among_commits` | Commit counts |
| `committed_correct_words`, `total_words`, `minutes_neural`, `minutes_correction` | The parts of the ratio |
| `unguarded_wpm`, `wpm_no_penalty` | Reference variants (no bound needed; no penalty) |
| `no_bci_wpm` | Gaze typing of every sentence at 20 chars/min (the eWPM no-BCI reference) |
| `controls` | Status of the required shuffled, zeros and null-commit controls |
| `timing`, `correction_rule` | How the time was measured and the penalty formula |

## 4. How to compute it

Library:

```python
from fidetype.benchmark.safe_wpm import safe_wpm, guarantee_from_sheet, controls_from_sheet

r = safe_wpm(committed, correct, n_words, n_chars, neural_s,
             guarantee=guarantee_from_sheet(guard.sheet.to_dict()),   # drop-in TrustGuard
             controls=controls_from_sheet(guard.sheet.to_dict()),
             timing="measured trial durations")
print(r["value"], r["status"])
```

Command line (one JSON object per trial: `committed`, `correct`, `truth` or `n_words` + `n_chars`, `neural_s`, optional `cluster`):

```bash
fidetype benchmark safe-wpm --trials trials.jsonl --guard guard.json --out safe.json
fidetype benchmark safe-wpm --trials trials.jsonl --method ltt --alpha 0.05 --delta 0.1 --n-cal 271 --chars-per-min 159.27
```

The benchmark scorer (`fidetype benchmark score`) adds a `safe_wpm` block to every result. It uses the submission's `guarantee`. It uses measured times if every scored trial in the truth file has a `neural_s` field; otherwise it uses the track rate model.

## 5. Baselines (2026-11-16)

All numbers use alpha 0.05. LTT entries use delta 0.1. Details and the rerun command: [results](../experiments/2026-11-16-p14-05-safe-wpm/results.md).

| Track / set | Decoder + policy | Safe WPM [95 % CI] | Status | Test wrong-commit [CP95] | Commits (wrong) | eWPM | No-BCI | Timing |
|---|---|---|---|---|---|---|---|---|
| B2T '25 T15 copy task | Card et al. 2024 published sentence + CRC | 13.42 [11.72, 15.08] | certified | 0.049 [0.035, 0.066] | 405 (40) | 18.80 | 4.08 | measured speech duration |
| B2T '25 T15 copy task | published sentence + LTT | 12.24 [10.98, 13.45] | certified | 0.040 [0.028, 0.056] | 364 (33) | 18.73 | 4.08 | measured |
| B2T '25 T15 copy task | ours (phoneme beam -> word) + CRC | 4.90 [4.10, 5.62] | **above alpha** | 0.062 [0.047, 0.081] | 199 (51) | 11.55 | 4.08 | measured |
| B2T '25 T15 copy task | ours + LTT | 4.05 [3.22, 4.77] | certified | 0.047 [0.033, 0.063] | 159 (38) | 11.51 | 4.08 | measured |
| SpanishBCBL MEG (async) | ConvCTC-M + CRC | 0.03 [0.00, 0.17] | certified | 0.020 [0.011, 0.035] | 14 (13) | 3.20 | 3.15 | rate model 152 chars/min |
| SpanishBCBL MEG (async) | ConvCTC-M + LTT | 0.03 [0.00, 0.17] | certified | 0.022 [0.012, 0.037] | 15 (14) | 3.20 | 3.15 | rate model |
| Toronto sEMG (composed) | CNN session-calibrated + CRC | 0.55 [0.28, 0.86] | certified | 0.004 [0.000, 0.013] | 21 (2) | 7.98 | 4.27 | rate model 75.76 chars/min; exact per-trial decisions (P6-01; the aggregate approximation gave 0.58) |
| Toronto sEMG (composed) | CNN cross-session + CRC | 0.25 [0.06, 0.46] | certified | 0.004 [0.000, 0.013] | 10 (2) | 4.68 | 4.27 | as above (approximation gave 0.27) |
| Toronto sEMG (composed) | CNN cross-subject + CRC | 0.00 | vacuous | 0.000 | 0 | 4.08 | 4.27 | as above |
| Replay: T15 val_eval (701) | M4-12 + P14-03 drop-in guard (LTT) | 0.00 | certified | 0.0029 [0.0003, 0.0103] | 2 (2) | 6.02 | 4.02 | measured trial window (20 ms bins) |
| Replay: T12 v2, 10 later sessions (400) | T12 v2 decoder + P14-03 drop-in guard (LTT) | 1.27 (no CI) | certified | 0.0375 [0.0211, 0.0611] | 25 (15) | 7.13 | 4.11 | measured trial window |
| Replay: T15 val_eval (701) | M4-13 + drop-in guard (same recipe, LTT; added 2026-11-17) | 2.23 (no CI) | certified | 0.0243 [0.0142, 0.0385] | 104 (17) | not computed | 4.02 | measured trial window |

> **Our take:** The headline result is plain. Only the published Card et al. decoder gives a safe WPM clearly above the no-BCI reference (12-13 vs 4.1). Our own T15 word decoder is at the no-BCI level (LTT 4.05; the CRC entry, 4.90, is above alpha). Our other decoders give under 1.3 safe WPM. Their eWPM gain comes almost fully from offers, not from commits. A stronger decoder (M4-13, P11-01) is the main lever, not the trust layer. The M4-13 row (2026-11-17) confirms the direction but not the level: the drop-in row goes from 0.00 (M4-12) to 2.23, still below the no-BCI 4.02.

> **Our take:** Safe WPM punishes wrong commits much more than eWPM does. On T12, 15 of 25 commits are wrong. The corrections take 6.1 of 42.6 minutes, and the value drops from 1.48 to 1.27.

## 6. Assumptions and limits

- **Timing.** B2T '25 copy task: `speech_duration_s` of `t15_copyTask.pkl` (measured). T15 / T12 replay sets: the length of the neural trial (20 ms bins). This window also holds time before and after speech, so it is longer than the speech: T15 trials average 18.7 s. This makes those numbers conservative. MEG and Toronto sEMG: the track rate model, because the committed per-trial data hold no times. Toronto sentences are composed from single key presses, so their time is not natural typing time.
- **Toronto timing is a rate model.** Since P6-01 the Toronto values use exact per-trial CRC decisions with a participant-cluster CI ([results](../experiments/2026-11-16-p6-01-tracks/results.md)). The neural time is still the rate model (composed sentences, 0.792 s per character).
- **No reading time.** The user reads committed text, but we add no time for it. The penalty adds time only for wrong commits.
- **The bound is marginal.** It covers wrong commits / all trials, not precision. A certified policy can still be wrong on most of its few commits (T15 M4-12: 2 of 2).
- **Exchangeability.** On the B2T copy track, `cal` is the first half of each day and `test` the second half. Drift can break the bound, as the `ours + CRC` entry shows.
- **One participant per set.** The replay sets have no CI. A trial bootstrap would be too narrow.
- **Controls.** The leaderboard shows the required controls next to the value. Many baseline entries lack a null-commit audit at their threshold ("controls: no").

## 6a. Proposed v0.2 (PROPOSED, NOT ADOPTED)

> **Proposed, not adopted (2026-11-18, P14-26).** The user decides adoption. v0.1 above stays the headline metric and no v0.1 number changes. Full text: [safe-wpm-v0.2-proposal.md](safe-wpm-v0.2-proposal.md).

- **Prefix credit.** A commit can claim only its first k words (a prefix commit). If these are the first k words of the truth, the trial earns k words. A complete commit (every sentence-level commit) earns words(y) only if it is exactly right, as in v0.1.
- **Wrong prefix.** It earns 0 words and costs 2.0 s + 0.79 s per character of the k true words that it replaces. A wrong complete commit costs the v0.1 penalty.
- **Words after a prefix commit** earn 0 words and add no time (as a withheld trial). One commit per trial.
- **Risk unit: the trial.** A wrong commit is a wrong prefix or a wrong complete commit; the rate is over all trials. A policy with prefix commits is certified only by a bound on this loss (`risk = "wrong-prefix-commit"`).
- **Speech time.** An optional per-trial `speech_s` adds a secondary `speech_time` value. The headline v0.2 value still uses `neural_s`.
- **Same as v0.1 for sentence-level policies.** Every number in section 5 is also its v0.2 value.
- **Code:** `safe_wpm(..., metric_version="0.2")`; CLI `--metric-version 0.2`. Default: `"0.1"`.

## 7. Relation to other metrics

| Metric | Counts | Needs a bound |
|---|---|---|
| eWPM | All text that ends right after the simulated user acts (commits, offers, corrections) | no |
| Safe WPM | Only text that the system commits and gets exactly right; wrong commits cost time | yes (CRC / LTT) |
| Wrong-commit rate | Wrong commits / all trials | the bound is on this |
| Error among commits | Wrong commits / commits (precision; P5-02) | separate bound (`calibrate(target_precision=)`) |

See also [error metrics](../wiki/concepts/error-metrics.md), [trust guarantee](trust-guarantee.md) and the [open benchmark](../benchmark/README.md).
