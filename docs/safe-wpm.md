# Safe WPM: words per minute at a guaranteed wrong-commit rate

The definition of safe WPM, the headline metric of the Fidetype benchmark, and how to compute it.

**Status:** Alpha ([status levels](glossary.md#status-levels)). `safe-wpm/0.1` is the metric in use. `safe-wpm/0.2` is adopted; the scorer switches to it in a later release (section 6a).

Code: [`src/fidetype/benchmark/safe_wpm.py`](../src/fidetype/benchmark/safe_wpm.py). Baselines: [results](../experiments/2026-11-16-p14-05-safe-wpm/results.md). Leaderboard column: "Safe WPM @ alpha" in [`benchmark/site/leaderboard.md`](../benchmark/site/leaderboard.md).

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
   - `ltt` ([Learn then Test](glossary.md#ltt-learn-then-test)): P(wrong-commit rate <= alpha) >= 1 - delta, over calibration draws ([alpha, delta](glossary.md#alpha-delta)).
   - `crc` (conformal risk control): expected wrong-commit rate <= alpha. CRC has no delta.
   - Any other policy (always commit, a plug-in threshold) gets status `not-certified` and no value. `unguarded_wpm` gives the same formula for reference only.
4. **Measured rate above alpha.** If the wrong-commit rate on the scored trials is above the stated alpha, the status is `above-alpha`. The leaderboard shows `! ABOVE alpha`.
5. **No commits.** If the policy commits nothing, the status is `vacuous` and the value is 0.0. The policy is safe, but it gives no value.
6. **Infeasible calibration.** If the guarantee has `feasible: false` (the calibration found no certified threshold), the bound covers only a policy that never commits. If the policy commits on one trial or more, the status is `not-certified` and the value is None. If it commits nothing, rule 5 applies (`vacuous`). Before 2026-11-19 the scorer gave `certified` in this case. No committed score card changed: the two infeasible cards commit nothing.

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

From the decisions of a drop-in `TrustGuard`, one call builds the five lists, the guarantee and the controls:

```python
from fidetype.benchmark.safe_wpm import from_decisions

results = [guard.decide(x) for x in outputs]              # TrustResult per utterance
r = from_decisions(results, truths, neural_s, guard,      # guard, guard.sheet or the sheet dict
                   normalizer="words",                    # None (whitespace only), a track normaliser, or a callable
                   timing="measured trial durations")
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
| Toronto sEMG (composed) | CNN session-calibrated + CRC | 0.55 [0.28, 0.86] | certified | 0.004 [0.000, 0.013] | 21 (2) | 7.98 | 4.27 | rate model 75.76 chars/min; exact per-trial decisions (the earlier aggregate approximation gave 0.58) |
| Toronto sEMG (composed) | CNN cross-session + CRC | 0.25 [0.06, 0.46] | certified | 0.004 [0.000, 0.013] | 10 (2) | 4.68 | 4.27 | as above (approximation gave 0.27) |
| Toronto sEMG (composed) | CNN cross-subject + CRC | 0.00 | vacuous | 0.000 | 0 | 4.08 | 4.27 | as above |
| Replay: T15 val_eval (701) | our earlier T15 phoneme decoder + drop-in guard (LTT) | 0.00 | certified | 0.0029 [0.0003, 0.0103] | 2 (2) | 6.02 | 4.02 | measured trial window (20 ms bins) |
| Replay: T12 v2, 10 later sessions (400) | T12 v2 decoder + drop-in guard (LTT) | 1.27 (no CI) | certified | 0.0375 [0.0211, 0.0611] | 25 (15) | 7.13 | 4.11 | measured trial window |
| Replay: T15 val_eval (701) | `t15-m4-13` + drop-in guard (same recipe, LTT; added 2026-11-17) | 2.23 (no CI) | certified | 0.0243 [0.0142, 0.0385] | 104 (17) | not computed | 4.02 | measured trial window |

> **Our take:** The headline result is plain. Only the published Card et al. decoder gives a safe WPM clearly above the no-BCI reference (12-13 vs 4.1). Our own T15 word decoder is at the no-BCI level (LTT 4.05; the CRC entry, 4.90, is above alpha). Our other decoders give under 1.3 safe WPM. Their eWPM gain comes almost fully from offers, not from commits. A stronger decoder is the main lever, not the trust layer. The `t15-m4-13` row (2026-11-17) confirms the direction but not the level: the drop-in row goes from 0.00 (earlier decoder) to 2.23, still below the no-BCI 4.02.

> **Our take:** Safe WPM punishes wrong commits much more than eWPM does. On T12, 15 of 25 commits are wrong. The corrections take 6.1 of 42.6 minutes, and the value drops from 1.48 to 1.27.

## 6. Assumptions and limits

- **Timing.** B2T '25 copy task: `speech_duration_s` of `t15_copyTask.pkl` (measured). T15 / T12 replay sets: the length of the neural trial (20 ms bins). This window also holds time before and after speech, so it is longer than the speech: T15 trials average 18.7 s. This makes those numbers conservative. MEG and Toronto sEMG: the track rate model, because the committed per-trial data hold no times. Toronto sentences are composed from single key presses, so their time is not natural typing time.
- **Toronto timing is a rate model.** The Toronto values use exact per-trial CRC decisions with a participant-cluster CI ([results](../experiments/2026-11-16-p6-01-tracks/results.md)). The neural time is still the rate model (composed sentences, 0.792 s per character).
- **No reading time.** The user reads committed text, but we add no time for it. The penalty adds time only for wrong commits.
- **The bound is marginal.** It covers wrong commits / all trials, not precision. A certified policy can still be wrong on most of its few commits (T15, earlier decoder: 2 of 2).
- **Exchangeability.** On the B2T copy track, `cal` is the first half of each day and `test` the second half. Drift can break the bound, as the `ours + CRC` entry shows.
- **One participant per set.** The replay sets have no CI. A trial bootstrap would be too narrow.
- **Controls.** The leaderboard shows the required controls next to the value. Many baseline entries lack a null-commit audit at their threshold ("controls: no").

## 6a. v0.2 (ADOPTED 2026-11-22; proposed 2026-11-18)

> **Adopted on 2026-11-22, with three conditions.** (1) The reading cost of the proposal (section 6 there) is part of the definition (`aac-gaze-v1`: 0.5 s + 0.3 s per word per commit, minimum prefix 1 word). (2) A headline interval includes the calibration draw (section 6b below) with K >= 80 calibration draws. (3) The draws are partition-only (a new split of the calibration set, no resample with replacement inside a part). Numbers computed before this date keep their labels: a v0.1 number stays a v0.1 number, and a number labelled "proposed v0.2" is not re-labelled. A v0.2 value without the reading cost, or with fewer than 80 draws, is not an adopted-v0.2 headline. The scorer default (`metric_version="0.1"`), the leaderboard column and the status strings in the code change in a later release. Until then, v0.1 stays the headline metric. Full text and history: [safe-wpm-v0.2-proposal.md](safe-wpm-v0.2-proposal.md).

- **Prefix credit.** A commit can claim only its first k words (a prefix commit). If these are the first k words of the truth, the trial earns k words. A complete commit (every sentence-level commit) earns words(y) only if it is exactly right, as in v0.1.
- **Wrong prefix.** It earns 0 words and costs 2.0 s + 0.79 s per character of the k true words that it replaces. A wrong complete commit costs the v0.1 penalty.
- **Words after a prefix commit** earn 0 words and add no time (as a withheld trial). One commit per trial.
- **Risk unit: the trial.** A wrong commit is a wrong prefix or a wrong complete commit; the rate is over all trials. A policy with prefix commits is certified only by a bound on this loss (`risk = "wrong-prefix-commit"`).
- **Speech time.** An optional per-trial `speech_s` adds a secondary `speech_time` value. The headline v0.2 value still uses `neural_s`.
- **Same as v0.1 for sentence-level policies.** Every number in section 5 is also its v0.2 value.
- **Code:** `safe_wpm(..., metric_version="0.2")`; CLI `--metric-version 0.2`. Default: `"0.1"`.
- **First use (pre-registered, [results](../experiments/2026-11-18-p5-24-prefix-commits/results.md)):** T15 `t15-m4-13` `val_eval` 701 with certified prefix commits: v0.2 4.87 [4.43, 5.30] (465 commits, 13 wrong); the same decisions under v0.1: 0.53 (literal, above alpha) or 1.03 (complete commits only). T12: v0.2 4.76, v0.1 0.00.
- **Reading cost (sensitivity, [proposal section 6](safe-wpm-v0.2-proposal.md#6-reading-cost-p14-28)):** optional `read_s_per_commit`, `read_s_per_word`, `min_prefix_words` (v0.2 only; defaults change nothing). With 0.5 s + 0.3 s/word per commit (`aac-gaze-v1`) the T15 prefix value is 4.67 [4.26, 5.07]; it falls to 4.02 at 5.99 s per commit. The adopted v0.2 includes this reading cost.

## 6b. Reporting addition: an interval over calibration draws (ADOPTED 2026-11-22 with v0.2; proposed 2026-11-19)

> **Adopted on 2026-11-22, with two rules:** use K >= 80 calibration draws (better 120), and partition-only draws (a new split per draw, no resample with replacement inside a part). Report the count of non-credited (above-alpha or not-certified) draws and the certified-only between-draw SD next to the interval. Intervals computed before this date (for example K = 40, or draws with resampling) keep their numbers and labels. It changes no `safe-wpm/0.1` rule, value or status. Until the scorer switches, a leaderboard entry reports the trial-bootstrap `ci` of section 3, and that CI is conditional on one calibration. Pre-registration and first use: [plan](../experiments/2026-11-20-p15-29-calibration-ci/plan.md), [results](../experiments/2026-11-20-p15-29-calibration-ci/results.md).

**Problem.** The `ci` of section 3 resamples the evaluation trials with the decisions fixed. A new calibration set gives a new guard and new decisions. On T15 the spread between calibration draws was about 2/3 of the trial-bootstrap half-width. So the usual CI is too narrow for the question "what does this system give a new user?".

**Method (two-level bootstrap).**

| Level | What changes | How |
|---|---|---|
| Outer: K calibration draws | the calibration sample and split | per draw: new calibrate seed, the `calibrate` split into fit / policy / LTT parts, a resample with replacement inside each part, then the full calibration again (learned score, LTT, null controls) |
| Inner: B trial resamples | the evaluation trials | the same B multinomial resamples for every draw (decisions of that draw fixed) |

- **Credit rule.** A draw adds its values only if its status is `certified`. A refused, `not-certified`, `above-alpha` or `vacuous` draw adds 0.0.
- **Interval.** The 2.5th and 97.5th percentiles of the pooled K × B values. **Point value:** the mean of the K draw values. With K = 1 the interval is the usual trial-bootstrap CI.
- **Cross-check.** The law of total variance: total SD² = mean within-draw SD² + between-draw SD². The function also returns the normal interval mean ± 1.96 × total SD.
- **First use (T15 guard, K = 40, pinned pipeline values).** The result is 5.18 [0.00, 6.99]. The trial-bootstrap CI of one draw was 4.91 [4.25, 5.57]. 2 of the 40 draws are above alpha on the test set and earn 0.0. The certified draws range from 3.50 to 6.82. The lower end is not above the no-BCI reference 4.02. T12: 1.05 [0.00, 3.18].
- **Second use (an EMG sentence guard, K = 40, user-cluster inner level).** The result is 5.00 [0.00, 9.55] against the EMG no-BCI reference 3.09. The trial-bootstrap CI of one draw was 6.80 [4.49, 9.63]. 9 of the 40 draws are above alpha on the test set and earn 0.0. The library `calibration_draw_interval` (prompt-level inner level) gives 5.00 [0.00, 7.84]. The lower end is not above 3.09 ([results](../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md)).
- **Current EMG headline (one EMG sentence guard, partition-only draws; a v0.1 number, label kept).** EMG typing with the trust layer is above the no-BCI baseline after calibration uncertainty, narrowly, for one sentence guard (safe-WPM v0.1: 5.90 [3.45, 8.89] vs 3.09; replicated 5.99 [3.52, 8.96] with safety headroom 0.0107), on 8 users and one test set ([results](../experiments/2026-11-21-p11-19-multi-split/results.md), [replication](../experiments/2026-11-22-p11-28-bx3-headroom/results.md)). The EMG prefix guard result 5.67 [3.43, 8.26] holds only under safe-WPM v0.2 with its prefix credit.
- **Limits.** The evaluation set is the same in every draw. Duplicates in a resampled LTT part make one draw's certificate invalid as a certificate; the draws only show the sampling variation. Pipeline values fitted before the guard (for example a frame temperature) can be refitted per draw or pinned; the report must say which.

**Code.**

```python
from fidetype.benchmark.safe_wpm import calibration_draw_interval

r = calibration_draw_interval(
    [{"committed": c_k, "correct": ok_k, "guarantee": guarantee_from_sheet(sheet_k)} for ...]  # one per draw
    + [{"refused": True}],                                  # a draw whose calibration was refused
    n_words, n_chars, neural_s, B=2000, seed=0, level=0.95, reference=no_bci_wpm)
print(r["value"], r["interval"], r["sd_between_draws"], r["lower_above_reference"])
```

## 7. Relation to other metrics

| Metric | Counts | Needs a bound |
|---|---|---|
| eWPM | All text that ends right after the simulated user acts (commits, offers, corrections) | no |
| Safe WPM | Only text that the system commits and gets exactly right; wrong commits cost time | yes (CRC / LTT) |
| Wrong-commit rate | Wrong commits / all trials | the bound is on this |
| Error among commits | Wrong commits / commits (precision) | separate bound (`calibrate(target_precision=)`) |

See also [error metrics](../wiki/concepts/error-metrics.md), [trust guarantee](trust-guarantee.md) and the [open benchmark](../benchmark/README.md).
