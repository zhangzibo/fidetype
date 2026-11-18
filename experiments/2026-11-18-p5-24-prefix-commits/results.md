---
title: P5-24 certified word-prefix commits vs the sentence-level learned guard - results
type: experiment
task: P5-24
updated: 2026-11-18
---

# P5-24: certified word-prefix commits (results)

Pre-registration: [plan.md](plan.md), commit `00a64ba` (library code, tests, the [safe-wpm v0.2 proposal](../../docs/safe-wpm-v0.2-proposal.md) and `run.py` in the same commit; committed and pushed before any stage ran). Code: `calibrate(confidence="learned", commit_unit="prefix")` in [`dropin.py`](../../src/fidetype/trust/dropin.py), prefix score in [`commit_score.py`](../../src/fidetype/trust/commit_score.py), `safe_wpm(metric_version="0.2")` in [`safe_wpm.py`](../../src/fidetype/benchmark/safe_wpm.py). Aggregates: [`results/results.json`](results/results.json); guard files (configuration + sheet, no text): `results/guard-*.json`; log: [`results/run.log`](results/run.log). Per-trial decisions (with text): `C:\Users\zhang\bci-data\derived\p5-24\` (local only).

> **Metric status.** The primary metric is **safe-wpm/0.2, PROPOSED, NOT ADOPTED**. The user decides adoption. Every v0.2 number below has its v0.1 number next to it. v0.1 stays the headline.

## Verdicts (pre-registered rule, safe-wpm/0.2 proposed)

| set | role | sentence (learned, P5-23) | **prefix** | Δ (prefix − sentence) | paired 95 % CI of Δ | half-width | prefix wrong commits (CP95) | controls (uniform, shuffled) | **verdict** |
|---|---|---|---|---|---|---|---|---|---|
| T15 M4-13, `val_eval` 701 | **primary** | 2.64 | **4.87** [4.43, 5.30] | +2.22 | [1.84, 2.59] | 0.38 | 13/701 = 0.0185 [0.0099, 0.0315] | 0/300, 1/300 (allowed 15) | **prefix beats sentence** |
| T12 v2, test 400 | replication | 1.87 | **4.76** [3.84, 5.78] | +2.89 | [1.89, 3.99] | 1.05 | 19/400 = 0.0475 [0.0288, 0.0732] | 0/300, 0/300 | prefix beats sentence |

- **P5-24 result (T15 decides): prefix beats sentence**, under the proposed v0.2. Safety holds on both sets (observed rate ≤ 0.05, no clear violation). All null controls pass. All prefix v0.2 entries have status `certified` (bound on `wrong-prefix-commit`).
- **T12** replicates the direction. Its observed wrong-commit rate (0.0475) is close to alpha; the CP interval includes 0.05.
- **No-BCI reference:** the T15 prefix value 4.87 and its interval [4.43, 5.30] are above 4.02. The T12 value 4.76 is above 4.11, but its interval includes 4.11.
- **Reference checks:** current arm = P14-05 / P14-03 decisions (T15 701/701, T12 400/400); sentence arm = P5-23 learned decisions (701/701, 400/400). Split hashes equal the plan (T15 `285b8c0d9baf5a41` / `fadfd84557fcb24b`; T12 `630db9ca864af56f` / `3fe1b31e8e46a035`).

## v0.1 next to v0.2

| set | arm | safe WPM v0.1 (headline) | status v0.1 | safe WPM v0.2 (proposed) | v0.2 with CTC speech span (secondary) |
|---|---|---|---|---|---|
| T15 | current (p_top1) | 2.23 | certified | 2.23 | 3.37 |
| T15 | sentence (learned) | 2.64 | certified | 2.64 | 4.04 |
| T15 | prefix, v0.1 literal (a right prefix = wrong commit) | 0.53 | **above-alpha** (421/701) | 4.87 | 7.47 |
| T15 | prefix, v0.1 complete-only (prefix commits not counted) | 1.03 | certified (44 commits, 0 wrong) | - | - |
| T12 | current | 1.27 | certified | 1.27 | 1.50 |
| T12 | sentence | 1.87 | certified | 1.87 | 2.22 |
| T12 | prefix, v0.1 literal | 0.00 | above-alpha (133/400) | 4.76 | 5.75 |
| T12 | prefix, v0.1 complete-only | 0.00 | certified (1 commit, 1 wrong) | - | - |

- v0.2 = v0.1 for the two sentence-level arms, as the proposal says (rule 6).
- **Under v0.1 the prefix guard is worse than the sentence guard.** v0.1 gives a right prefix 0 words; read literally, every partial commit is a wrong commit. In complete-only mode the prefix guard commits few whole sentences (44 on T15), because its threshold (0.94) is set for the prefix loss: paired v0.1 Δ (complete-only − sentence) = −1.62 [−2.07, −1.19] on T15.
- **No pre-registered v0.1 value is above 4.02.** P14-23 stays open (see below).

## Details per arm (T15)

| | current | sentence | prefix |
|---|---|---|---|
| commit threshold | p_top1 ≥ 0.73 | score ≥ 0.87 | prefix score ≥ 0.94 |
| commits / wrong | 104 / 17 | 113 / 10 | 465 / 13 (421 prefix + 44 complete) |
| error among commits | 0.163 | 0.088 | 0.028 |
| committed right words | 504 | 588 | **1,073** |
| words per prefix commit (all commits) | - | - | mean 2.38; 1: 181, 2: 121, 3: 67, 4: 42, 5: 27, 6: 15, 7: 8, 8: 4 |
| correction time (min) | 8.20 | 4.07 | 2.22 |
| LTT part, in-sample commits / wrong | 54 / 8 | 61 / 8 | 189 / 5 |
| paired Δ vs current (v0.2) | - | - | +2.64 [2.23, 3.05] |

- **Ceiling.** The right word prefixes of all T15 top-1 texts hold 2,688 words. The prefix guard commits 1,073 of them (40 %).
- **Fitted prefix score (T15;** 451 items, 2,957 prefix rows, 1,716 right): 14 of 16 features used. Largest standardised weights: `prefix_log_words` −0.93, `acoustic_per_char` +0.81, `prefix_agree_mean` +0.53, `lm_per_word` +0.45, `prefix_char_conf_min` +0.43, `prefix_mass` +0.43, `p_top1` +0.41. Dropped by the sign rule: `nbest_entropy`, `guard_risk`.
- **T12:** threshold 0.87; 133 commits (132 prefix, 1 complete), 19 wrong (error among commits 0.143); 185 right words; words per commit 1: 80, 2: 31, 3: 15, 4: 6, 6: 1; right-prefix ceiling 654 words. Dropped features: `p_top1`, `guard_risk`, `acoustic_gap`.

## Notes and limits
- **v0.2 is a proposal.** The verdict holds under the proposed metric only. Whether a right prefix should earn its words is the user's decision (P14-26).
- **Prefix commits are short.** On T15, 39 % of the commits are one word. A one-word commit saves the user little typing in practice; v0.2 credits it fully and gives no reading time.
- One participant per set, one split, one seed. The intervals are conditional on the calibration (decisions fixed); they do not include the calibration draw.
- The prefix feature set was designed after the exploratory P14-23 analysis, which looked at `val_eval`. The score was fitted and certified on `val_select` only. The result (4.87) is below the exploratory 5.43, as for P5-23.
- The speech span comes from our own CTC output (T15 mean 12.11 s vs 18.68 s window; T12 4.48 s vs 5.48 s). It is secondary.
- **Memory:** T15 stage peak working set 784 MB (504 s). T12 stage peak **2,340 MB** (260 s): the shared P14-03 T12 loader holds the T12 data. This is above the 1 GB target of the brief; P5-23 used the same loader but could not measure its peak. Not killed; no retry was needed.
- Not tested: LLM features or LLM-rescored n-best (P15-22), word-by-word streaming commits (one commit per trial here), online re-calibration and precision bounds for a prefix guard.

> **Our take:** prefix commits are the largest pre-registered safe-WPM gain so far, but only if right prefixes count. Under v0.2 the T15 value (4.87) and its interval are above the no-BCI reference (4.02), with fewer wrong commits than the sentence guards. Under v0.1 the same guard is worse than the sentence guard. So the metric decision (P14-26) now decides which guard is better for a user. The case for v0.2: a right prefix is real text that the user does not type. The case against: many commits are one word, and v0.2 has no reading or checking cost per commit.
