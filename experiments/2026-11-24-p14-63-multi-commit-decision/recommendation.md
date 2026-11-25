---
title: P14-63 several commits per trial in safe-WPM v0.2 - recommendation for the user decision
type: experiment
task: P14-63
updated: 2026-11-24
---

# P14-63: adopt the "several commits per trial" rule of safe-WPM v0.2? (recommendation)

Gap 203. **This page prepares a user decision. It does not make it.** No scorer default, card or published number changes here. CPU only; the analysis reads local per-trial decision logs (read only) and writes only [`results.json`](results.json) (aggregates, no text).

Rule under decision: [proposal section 7](../../docs/safe-wpm-v0.2-proposal.md#7-several-commits-per-trial-p5-27-proposed-extension-not-adopted), "rule (7)". In short: the commits of a trial are append-only. The trial is right only if every commit is right (for append-only commits this is the same as "the final committed text is right"). Credit and penalty use the final committed text. **Every commit event pays the fixed reading cost 0.5 s; every committed word pays 0.3 s once.** A policy with several commits in a trial is certified only by a bound on the trial loss "any commit is wrong" (`risk = "wrong-stream-commit"`).

## 1. Recommendation in five lines

1. **Adopt rule (7) as part of safe-WPM v0.2 (option A).** It changes no published number: no leaderboard card has a trial with several commits.
2. It matters today only for two T15 experiment arms (stream, hybrid). For the hybrid it moves the value by at most ±0.05 against the two plausible reading rules, and the result "hybrid beats single" holds under each of them.
3. Its main protection is the per-event reading fee: without it a guard can split one commit into many at no cost. The adopted scorer has this gap today when a caller leaves out `n_commits`: fix it under every option.
4. Rule (7) counts each committed word once. Nothing is counted twice. A stricter rule ("re-read all committed words at each event") costs the hybrid only 0.05 more.
5. Options: **A** adopt rule (7) (recommended), **B** do not adopt yet (status quo: several-commit numbers stay "not an adopted headline"), **C** adopt with the stricter re-read reading rule.

## 2. Where the rule matters

| Set | Entries | Trials with several commits | Effect of the decision |
|---|---|---|---|
| Leaderboard cards, tracks v0.2 | 36 | **0** | none |
| Leaderboard cards, tracks v0.1 | 21 | **0** | none |
| Hallucination cards (v0.1, v0.2) | 52 | 0 | none |
| T15 `val_eval` (701 trials), one-commit prefix guard (P5-24, "single") | 1 | 0 | none (rule (7) = v0.2) |
| T15, streaming guard (P5-27, "stream") | 1 | 115 of 310 committing trials; 446 commit events; max 4 | labelled "proposed" today |
| T15, hybrid guard (P5-28, "hybrid") | 1 | **224** of 500 committing trials; 803 commit events; max 5 | labelled "proposed" today |
| T12 replication of stream + hybrid (P5-29) | not run | (expected: yes) | its headline needs this rule |

Why the cards have none: the benchmark submission format holds **one action per unit** (`commit`, `offer` or `abstain`, with one text; [`scorecard.py`](../../src/fidetype/benchmark/scorecard.py), unit rows). It cannot express a second commit. No committed card has a prefix commit either (`n_prefix_commits` is 0 or absent on all 109 cards; scan in `results.json` → `cards`).

## 3. Measured effect (T15, the only data with several commits)

Five scoring rules for the same fixed decisions (adopted aac-gaze-v1 constants: penalty 2 s + 0.79 s/char, reading 0.5 s per commit + 0.3 s per word; 218.3 neural minutes):

| Rule | What it charges | single | stream | hybrid |
|---|---|---|---|---|
| **R7** (proposal rule (7)) | 0.5 s per commit event + 0.3 s per committed word once | 4.67 | 2.34 | **4.89** |
| ONE | the final text as one commit: 0.5 s per trial (what the adopted scorer gives today if the caller leaves out `n_commits`) | 4.67 | 2.36 | 4.94 |
| REREAD | per event: 0.5 s + 0.3 s per word committed so far (the user reads the whole text again) | 4.67 | 2.33 | 4.84 |
| FIRST | only the first commit event counts; later commits are ignored | 4.67 | 1.75 | 2.91 |
| REFUSE | the adopted rule 3 (one commit per trial) | 4.67 | no value | no value |

R7 reproduces the recorded values exactly (4.667, 2.344, 4.890; also through the library scorer with `n_commits`).

Differences against R7 (paired trial bootstrap, B = 2,000, seed 0; decisions fixed):

| Arm | ONE − R7 | REREAD − R7 | FIRST − R7 |
|---|---|---|---|
| stream | +0.012 [+0.009, +0.015] | −0.010 [−0.013, −0.007] | −0.59 [−0.69, −0.49] |
| hybrid | +0.053 [+0.043, +0.064] | −0.048 [−0.059, −0.038] | −1.98 [−2.28, −1.68] |

The comparison that the experiments report (hybrid − single) under each rule:

| Rule | hybrid − single [95 % CI] | Verdict |
|---|---|---|
| R7 | **+0.22 [+0.14, +0.31]** | hybrid beats single (as recorded) |
| ONE | +0.28 [+0.20, +0.36] | hybrid beats single |
| REREAD | +0.17 [+0.10, +0.26] | hybrid beats single |
| FIRST | −1.76 [−2.08, −1.42] | single beats hybrid |

Reading time of the hybrid: R7 12.6 min, ONE 10.1 min, REREAD 14.9 min (single: 9.4 min).

**Break-even fee.** With the fee per commit event raised for both arms, the hybrid falls to the single value at **2.68 s per event** (5.4 times the adopted 0.5 s). With the fee raised for the hybrid only: 1.33 s. The hybrid falls to the no-BCI reference 4.02 at 4.28 s per event. The stream arm is below 4.02 at any fee.

> **Our take:** the choice between R7, ONE and REREAD is a second-order matter (±0.05 on the hybrid). The choice that matters is between a rule that counts the later commits (R7, ONE, REREAD) and a rule that does not (FIRST, REFUSE). FIRST is not a safe alternative: it ignores 5 of the hybrid's 18 wrong trials (13 counted) and the words the user saw committed later. REFUSE gives no value at all, so streaming guards cannot have an adopted headline.

## 4. Risks

| Risk | Under R7 | Evidence |
|---|---|---|
| **Gaming by splitting** one commit into many small commits | Each extra event costs 0.5 s. Splitting a k-word commit into k one-word commits costs (k − 1) × 0.5 s and earns no word more. | Without the fee (ONE) splitting is free; the hybrid gains +0.05 only from the 303 extra events. Break-even fees above. |
| **Gaming through the API today** | The adopted scorer, called without `n_commits`, scores a several-commit trial as one commit and labels it an adopted headline (hybrid: 4.94, `adopted_headline: true`, guarantee risk `wrong-stream-commit`). | `results.json` → `t15.hybrid.library_without_n_commits`. Fix under every option: refuse, or mark as not a headline, a `wrong-stream-commit` guarantee without `n_commits`. |
| **Double counting the reading cost** | No double counting: each committed word pays 0.3 s once; the 0.5 s is per event (a gaze shift and a decision), not per word. | REREAD (every event re-reads all earlier words) is the upper bound: −0.05 on the hybrid. |
| **Penalty after a wrong later commit** | The user deletes all committed words, also the right earlier ones, and types them again: penalty on the final text. This is the conservative choice. | Proposal section 7.1, third example row. |
| **Certification** | A trial is wrong if any commit is wrong; the rate is wrong trials / all trials, as in v0.1 and v0.2. No new statistics. Needs `risk = "wrong-stream-commit"`. | P5-27 and P5-28 certify this loss with LTT. |
| **What it does not cover** | Retractions (a commit that removes words) and a credit for earlier text (latency). A guard that retracts is out of scope; latency is reported next to safe WPM, not inside it. | P5-28: right words median 3.85 s vs 11.20 s after the word ends; not part of the value. |
| **Calibration-draw interval** | Unchanged rule: an adopted headline interval still needs K >= 80 partition-only calibration draws. P5-27 / P5-28 have only trial-bootstrap CIs, so they stay "not a headline" even under option A. | docs/safe-wpm.md section 6b. |

## 5. Options

| Option | What changes | Effect on numbers | What it unlocks |
|---|---|---|---|
| **A. Adopt rule (7)** (recommended) | docs/safe-wpm.md: the decision and its reason; the proposal section 7 status "adopted"; scorer: a trial with several commits no longer marks the report as a variant; tests; the `n_commits` gap fix. | None published. P5-27 / P5-28 values keep their "proposed" label (no re-labelling). | Streaming and hybrid guards can get an adopted v0.2 headline (with a K >= 80 interval). The T12 replication (P5-29) can report one. A later item can add commit events to the submission format, so such guards can enter the leaderboard. |
| **B. Do not adopt yet** | docs/safe-wpm.md: the decision "not adopted" and its reason; the `n_commits` gap fix. | None. | Nothing new. Several-commit values stay "not an adopted headline". The question comes back when a streaming guard wants a leaderboard entry. |
| **C. Adopt with the REREAD reading rule** | As A, with `read_i = sum over events of (0.5 s + 0.3 s × words committed so far)`. | None published. The T15 hybrid would read 4.84 instead of 4.89 (a "proposed" number keeps its value; a new run would use C). | As A. Stricter for long streams, so a guard that commits early and often pays more. |

Reason for A over C: R7 matches the reading model that v0.2 already adopted for one commit (read each committed word once, plus one fixed cost per look). There is no measurement of BCI users re-reading streamed text (proposal section 6.2: no source measures the check time of one committed word). C adds a new assumption that changes the hybrid result by only 0.05.

Reason for A over B: B leaves the scorer gap of section 4 as the easier path (a caller who leaves out `n_commits` pays less and gets a headline label), and it blocks the planned T12 replication from an adopted headline.

## 6. What the user decision unlocks

- The done-when of gap 203: the decision and its reason go into docs/safe-wpm.md. With A or C: the scorer and the tests implement it, and no earlier number is re-labelled.
- With A or C: a follow-up for the submission format (commit events per unit) so that streaming guards can be scored on the leaderboard; until then the rule applies to the library and the CLI only (the per-trial JSON Lines of the CLI already take `n_commits`).
- With every option: the scorer fix for a `wrong-stream-commit` guarantee without `n_commits` (section 4), as a small separate item.

## 7. Reproduce

`C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-24-p14-63-multi-commit-decision/analyse.py` (about 3 s). Inputs (local, read only): `derived/p5-27/decisions-single.json`, `derived/p5-27/decisions-stream.json`, `derived/p5-28/decisions-hybrid.json`, and the T15 trial durations (`derived/m4-01-02-lookahead`, `derived/m4-13`). Output: [`results.json`](results.json).

## Limits

One participant (T15), one split, decisions fixed (no new calibration per rule), conditional intervals only. The FIRST rule keeps the guard's certificate, which was made for the trial loss of all commits; it is shown only to size the effect. The P5-28 λ_mid caveat (chosen on the same certify items) applies to every hybrid number here.
