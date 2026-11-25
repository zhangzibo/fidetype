# Safe WPM v0.2: proposal (prefix credit and speech time)

> **Design record.** This page records a design and its decisions. It is not a user guide. For the user guide, see [Safe WPM](safe-wpm.md).

> **Status: Adopted (2026-11-22).** The project maintainer adopted it after review. `safe-wpm/0.2` is adopted with three conditions: (1) the reading cost of section 6 is part of the definition (`aac-gaze-v1`: 0.5 s + 0.3 s per word per commit, minimum prefix 1 word); (2) a headline interval includes the calibration draw (docs/safe-wpm.md section 6b) with K >= 80 calibration draws; (3) the draws are partition-only (a new split of the calibration set, no resample with replacement inside a part). Numbers computed before this date keep their labels: a v0.1 number stays a v0.1 number, and a number labelled "proposed v0.2" is not re-labelled. A v0.2 value without the reading cost, or with fewer than 80 draws, is not an adopted-v0.2 headline. The scorer default (then `metric_version="0.1"`), the leaderboard column and the status strings in the code changed in a separate step on 2026-11-23: the default is now `metric_version="0.2"` with this reading cost, and the leaderboard shows v0.2 as the headline column and v0.1 as a second column ([safe-wpm.md](safe-wpm.md) section 6a).
>
> History (status before 2026-11-22): **PROPOSED, NOT ADOPTED.** The maintainer decides adoption (planned for the week of 2026-11-18). Until then, `safe-wpm/0.1` ([docs/safe-wpm.md](safe-wpm.md)) stays the headline metric. No published v0.1 number changes. The scorer computes v0.2 only when the caller asks for it (`metric_version="0.2"`). Adoption needs one switch: the default of `metric_version` and the leaderboard column. **A review of 2026-11-18 recommended adopting v0.2 only together with a reading cost per commit (section 6).**

Source: the [safe WPM bottleneck analysis](../wiki/questions/safe-wpm-bottleneck.md). Code: [`src/fidetype/benchmark/safe_wpm.py`](../src/fidetype/benchmark/safe_wpm.py) (`safe_wpm(..., metric_version="0.2")`, `prefix_outcome`). Tests: `tests/test_safe_wpm.py` (the `v02` tests). First user: the [prefix-commit experiment plan](../experiments/2026-11-18-p5-24-prefix-commits/plan.md).

## 1. Why a v0.2

On T15 (`val_eval`, 701 trials, M4-13 decoder) v0.1 is strict in two ways that are not about safety (P14-23):

| v0.1 rule | Effect on T15 |
|---|---|
| Only a whole, exactly right sentence earns words | The right word prefixes of the top-1 sentences hold 57.5 % of all words. Exactly right sentences hold 33.8 %. |
| Time is the whole neural trial window | The window is 18.7 s per trial. Active speech (our CTC output) is 12.1 s. |

A system that types the first words of a sentence right and then stops gives the user real value. v0.1 gives it 0 words.

## 2. Definition (`safe-wpm/0.2`)

A session has N trials. Each trial has one intended sentence y_i. Words are separated by spaces, after the text normalisation of the track.

| Symbol | Meaning |
|---|---|
| `neural_s_i` | As in v0.1 (measured trial duration, or the track rate model). |
| `committed_i` | The policy COMMITs a text c_i (no user action). |
| `k_i` | The number of words of c_i. |
| `complete_i` | The commit claims the whole sentence. Every sentence-level commit is complete. A prefix guard sets it when it commits all words of its top-1 text. |
| `right_i` | See (1). |

```
(1) right_i   = (c_i == y_i)                                        if complete_i
              = (k_i >= 1 and c_i == the first k_i words of y_i)    otherwise
(2) credit_i  = words(y_i)   if committed_i and right_i and complete_i
              = k_i          if committed_i and right_i and not complete_i
              = 0            otherwise
(3) time_i    = neural_s_i + [committed_i and not right_i] * penalty_i
(4) penalty_i = 2.0 s + (2 * 60 / 152) s/char * len(y_i)                          if complete_i
              = 2.0 s + (2 * 60 / 152) s/char * len(the first k_i words of y_i)   otherwise

safe WPM v0.2 = 60 * sum_i credit_i / sum_i time_i
```

### 2.1 Rules

| Case | Words | Time |
|---|---|---|
| Complete commit, exactly right | `words(y_i)` | `neural_s_i` |
| Complete commit, wrong | 0 | `neural_s_i` + penalty for the whole sentence (as v0.1) |
| Prefix commit, right (its k words are the first k words of y_i) | k | `neural_s_i` |
| Prefix commit, wrong | 0 | `neural_s_i` + penalty for the first k words of y_i |
| Offer, withhold, abstain | 0 | `neural_s_i` |

1. **Prefix credit.** A right prefix earns exactly its k words. It earns no part of a word.
2. **Wrong prefix.** The user deletes the committed words and types the k true words that they replace. The penalty uses the v0.1 correction constants (`aac-gaze-v1`: 2.0 s overhead, 2 * 60 / 152 s per character). A wrong prefix earns 0 words, also if some of its words are right.
3. **Words after a prefix commit.** The words of y_i after the committed prefix earn 0 words and add no time. This is the v0.1 rule for a withheld trial: the user types them, and the BCI did not make them. A trial has at most one commit in v0.2. A second commit in the same trial (streaming, word by word) is not defined here; section 7 proposes an extension (P5-27).
4. **A prefix that is too long** (more words than y_i) is wrong.
5. **A complete commit claims the end of the sentence.** "i need" committed as complete for "i need water" is wrong (penalty for the whole sentence). The same words committed as a prefix are right (2 words).
6. **v0.2 = v0.1 for sentence-level policies.** If every commit is complete, (1)-(4) are the v0.1 formulas. A test checks this.

### 2.2 Certification and the risk unit

- **Risk unit: the trial.** A wrong commit is a commit with `right_i = 0`, prefix or complete. The rate is wrong commits / all trials (marginal, as in v0.1).
- **The bound must be on this loss.** A guarantee states its loss in `risk`: `"wrong-commit"` (the v0.1 loss; the default) or `"wrong-prefix-commit"` (the v0.2 loss). A policy that makes one or more prefix commits gets status `certified` only with `risk = "wrong-prefix-commit"` (LTT or CRC, as in v0.1). Otherwise the status is `not-certified` and the value is None.
- A sentence-level policy keeps its v0.1 certificate, because for complete commits the two losses are the same.
- The P5-24 prefix guard certifies `risk = "wrong-prefix-commit"` with LTT on a disjoint calibration part. `guarantee_from_sheet` reads it from the guard sheet.
- Status `above-alpha`, `vacuous` and the controls work as in v0.1.

### 2.3 Speech time (optional field)

- A trial can carry `speech_s`: measured speech duration, or the active-speech span (first to last non-blank CTC frame). The report then has a `speech_time` block: the same credit and penalty over `sum(speech_s) + penalties`, and the source in `speech_time.timing`.
- **The headline v0.2 value still uses `neural_s`.** Speech time is a secondary field. It is not a system gain: it changes the clock, not the output. The no-BCI reference does not change.
- A CTC speech span comes from the decoder under test. Report it as such. Measured speech times (where the dataset has them) are better.

## 3. What a v0.2 entry reports

All v0.1 fields, plus:

| Field | Content |
|---|---|
| `definition`, `definition_status` | `safe-wpm/0.2` and its status (since 2026-11-22: "adopted 2026-11-22: the headline metric ..."; before that date: "proposed, not adopted") |
| `risk` | The loss of the declared bound |
| `n_prefix_commits`, `n_complete_commits`, `n_right_complete_commits` | Commit counts by kind |
| `committed_correct_words` | Words of right prefixes and right complete commits |
| `speech_time` | Optional: value, no-penalty value, minutes, timing source |

## 4. How to compute it

```python
from fidetype.benchmark.safe_wpm import safe_wpm, prefix_outcome, guarantee_from_sheet

o = [prefix_outcome(text, truth, complete) for ...]          # per commit
r = safe_wpm(committed, [x["correct"] for x in o], n_words, n_chars, neural_s,
             guarantee=guarantee_from_sheet(guard.sheet.to_dict()),
             metric_version="0.2",
             committed_words=[x["committed_words"] for x in o], complete=[x["complete"] for x in o],
             penalty_chars=[x["penalty_chars"] for x in o],
             speech_s=speech_s, speech_timing="CTC active-speech span")      # speech_s is optional
```

Command line: `fidetype benchmark safe-wpm --trials t.jsonl --guarantee g.json --metric-version 0.2`. Per-trial JSON fields: `committed`, `truth`, `neural_s`, and for a commit `committed_text` + `complete` (or `committed_words` + `penalty_chars`); optional `speech_s`. Without `--metric-version` the CLI scores v0.2 (the default since 2026-11-23, with the section 6 reading cost). `--metric-version 0.1` scores v0.1, where only the exact sentence counts.

## 5. Adoption (the user's decision)

**Decided 2026-11-22: adopt v0.2 with the section 6 reading cost** (see the status note at the top).

| Option | Effect |
|---|---|
| Adopt v0.2 | (Recommended: with the section 6 reading cost.) Default `metric_version="0.2"`; the leaderboard column becomes v0.2 with a dated note; v0.1 stays as a second column. Every published sentence-level number stays the same (rule 6). |
| Keep v0.1 only | v0.2 stays an opt-in research field. Prefix guards are reported with v0.2 next to v0.1 and never in place of it. |
| Change v0.2 first | For example a stricter wrong-prefix penalty (the whole sentence, the "sentence" variant), or speech time as the headline. Each change is a new pre-registered text. |

Open points for the decision:
- The wrong-prefix penalty charges only the k replaced words. A stricter user model (the user re-reads and rewrites the whole sentence) gives the v0.1 penalty. P14-23 found the difference small on T15 (5.43 vs 5.55, exploratory).
- One commit per trial. A streaming guard that commits word by word needs a rule for several commits: section 7 proposes one (P5-27).
- Reading time: v0.2 as committed charges 0 s, as v0.1. P14-28 recommends 0.5 s per commit + 0.3 s per committed word (section 6).

> **Our take:** v0.2 removes a strictness of v0.1 that does not protect the user: a right prefix is real typed text. It keeps the safety part: every wrong commit, prefix or complete, counts against the same certified rate and costs correction time. Because v0.2 equals v0.1 for sentence-level policies, adoption changes no existing number.

## 6. Reading cost (P14-28)

Roadmap item P14-28 (gap 75). Pre-registration: [plan](../experiments/2026-11-18-p14-28-reading-cost/plan.md) (commit `691d743`). Results: [results](../experiments/2026-11-18-p14-28-reading-cost/results.md). **This is a sensitivity analysis:** it re-scores the fixed P5-24 decisions. It is not a new test of the guard.

**Why.** On T15, 181 of the 465 prefix commits are one word. v0.2 as committed gives the user no time to read or check a commit. Many short commits could then overstate the gain.

### 6.1 Scorer options

`safe_wpm(..., metric_version="0.2", read_s_per_commit=c, read_s_per_word=w, min_prefix_words=m)` (CLI: `--read-s-per-commit`, `--read-s-per-word`, `--min-prefix-words`):

```
(5) read_i  = [committed_i] * (c + w * k_i)       k_i = words of the committed text (right or wrong commit)
    time_i  = neural_s_i + [committed_i and not right_i] * penalty_i + read_i
(6) a prefix commit (not complete) with k_i < m counts as no commit (0 words, no time)
```

Defaults c = 0, w = 0, m = 1 give the v0.2 values above. The options are refused with v0.1. A `reading_cost` block reports them. The speech-time block pays the same reading time. With c > 0 or w > 0, rule 6 of section 2.1 (v0.2 = v0.1 for sentence policies) no longer holds: a sentence commit also pays its reading time.

### 6.2 Published estimates

| source | value | use as a commit cost | certainty |
|---|---|---|---|
| Card, Moran & Newell, keystroke-level model (CACM 1980; *The Psychology of Human-Computer Interaction*, 1983) | mental operator M = 1.35 s; Kieras' guide: 0.6-1.35 s, "use 1.2 s" | one M per commit (decide to keep the text) | standard HCI constant; not measured on BCI users |
| Brysbaert, "How many words do we read per minute?", *J. Mem. Lang.* 109:104047 (2019), 190 studies | silent reading 238 wpm (non-fiction) = 0.252 s/word | per committed word | adults under 60; not AAC users |
| Fidetype `aac-gaze-v1` user model (`fidetype.interact.simulated_user`; checked against Cai et al., *Nat. Commun.* 2024, SpeakFaster) | verify a commit: 0.5 s + 0.3 s/word (200 wpm) | per commit + per word | **project assumption**; the eWPM simulated user already uses it |
| Trnka, McCaw, Yarrington, McCoy & Pennington, "Word prediction and communication rate in AAC", Telehealth/AT 2008 (28 participants, 1.5 s key delay) | 2.26 s per keystroke without prediction; 2.59 (basic) / 2.95 (advanced) with prediction | overhead 0.33-0.69 s per keystroke | indirect: the list is checked at many keystrokes, not once per commit |
| Chitnis, Yang & Geramifard, arXiv:2403.15502 (2024), inline autocomplete, N = 9 | about 21 ms per suggestion (9 ms right, 50 ms wrong) | lower bound | small study; fast able-bodied typists |
| Li & Feit, arXiv:2602.06489 (2026), simulation | gaze shift to the suggestion bar 200 ms (SD 100) | part of a fixed cost | simulation parameter |
| Koester & Levine, *IEEE Trans. Rehabil. Eng.* 2(3):177-187 (1994); *AAC* 12 (1996) | list search much slower for users with spinal cord injury; prediction lowered their text rate | qualitative only | **uncertain: exact seconds not obtained** (no full text here) |

No source measures the time a BCI user needs to check one committed word. The values above span about 0.01 s to 1.35 s per commit plus about 0.25-0.3 s per word.

### 6.3 Sensitivity (T15 `val_eval` 701, M4-13; no-BCI 4.02)

| reading cost | m | prefix guard (P5-24) | sentence guard (P5-23) | Δ [95 % CI] |
|---|---|---|---|---|
| 0 s (as committed) | 1 | 4.87 [4.43, 5.30] | 2.64 | +2.22 [1.84, 2.59] |
| 1 s per commit | 1 | 4.70 [4.29, 5.11] | 2.62 | +2.08 [1.70, 2.44] |
| 3 s per commit | 1 | 4.40 [4.02, 4.77] | 2.58 | +1.82 [1.47, 2.17] |
| **0.5 s + 0.3 s/word (`aac-gaze-v1`)** | 1 | **4.67 [4.26, 5.07]** | 2.60 | +2.07 [1.70, 2.43] |
| 1.35 s + 0.252 s/word (KLM M + reading) | 1 | 4.55 [4.16, 4.94] | 2.58 | +1.97 [1.61, 2.32] |
| 0 s | 2 | 4.07 [3.61, 4.51] | 2.64 | +1.43 [1.05, 1.81] |
| 0.5 s + 0.3 s/word | 2 | 3.94 [3.51, 4.36] | 2.60 | +1.35 [0.99, 1.72] |
| 0.5 s + 0.3 s/word | 3 | 2.97 [2.54, 3.41] | 2.60 | +0.38 [0.02, 0.73] |

- **Break-even (T15, m = 1):** the prefix value falls to 4.02 at **5.99 s per commit** (or 2.52 s per committed word). With m = 2: 0.58 s. With m = 3: below 4.02 at 0 s.
- **T12** (test 400, no-BCI 4.11): 4.76 → 4.51 [3.66, 5.42] at `aac-gaze-v1`; break-even 2.78 s per commit (m = 1). The T12 CI includes 4.11 at every cost, as before.
- A minimum length of 2 words removes 181 T15 commits with 177 right words and 4 wrong commits. It lowers the value more than any literature reading cost.
- Full grid (0, 0.5, 1, 2, 3 s; three user models; m = 1, 2, 3; both sets): [results](../experiments/2026-11-18-p14-28-reading-cost/results.md).

### 6.4 Recommendation (rule fixed before the numbers)

| decision | recommendation | reason |
|---|---|---|
| Reading cost in v0.2 | **Adopt c = 0.5 s per commit + w = 0.3 s per committed word** as the v0.2 default, on every commit of every entry | It is the project's existing user model. It lies inside the published range. It stops a guard from gaining by many tiny commits. |
| Minimum prefix length | **Keep m = 1** in the metric; m is a guard design option only | m = 2 removes right text and costs more than the reading time it saves. |
| Claim "above the no-BCI reference" (T15) | Holds under the recommended cost (4.67 [4.26, 5.07]) and up to about 6 s per commit | Pre-registered statements 1 and 2: robust, not fragile. |
| Rule 6 | Restate it: with a reading cost, a sentence policy's v0.2 value is a little below its v0.1 value (T15 sentence guard 2.64 → 2.60) | The reading time is a real user cost for every commit. |

Until the user decides, the scorer default stays c = 0, w = 0, m = 1. Adoption of the recommendation is one more default change in `safe_wpm` and the CLI. (Done: adopted 2026-11-22; since 2026-11-23 the default is c = 0.5, w = 0.3, m = 1. c = 0, w = 0 is now a sensitivity variant.)

> **Our take:** the T15 gain of prefix commits under v0.2 is not an artefact of free reading time. The weak points of the v0.2 result are T12 (break-even 2.8 s, CI includes the reference) and the single participant per set, not the one-word commits.

## 7. Several commits per trial (P5-27; PROPOSED EXTENSION, NOT ADOPTED)

> **Status: ADOPTED 2026-11-24 as part of v0.2 (option A of the decision record).** The maintainer delegated the decision; it adopts rule (7) below without change: every commit event pays the fixed reading cost c = 0.5 s, every committed word pays w = 0.3 s once. The heading of this section keeps its old text so that existing links still work. The decision changed no published number: no score card has a trial with several commits (the submission format holds one action per unit). Values labelled "proposed" before this date (sections 7.4 and 7.5) keep their labels and values. With the adoption, the scorer also closes a hole: a `wrong-stream-commit` guarantee scored without `n_commits` is not an adopted headline (`not_headline_because`), because the scorer cannot see the commit events and would charge one reading fee per trial. Decision record: [recommendation](../experiments/2026-11-24-p14-63-multi-commit-decision/recommendation.md) (P14-63, gap 203). User guide: [safe-wpm.md section 6c](safe-wpm.md#6c-several-commits-per-trial-adopted-2026-11-24-part-of-v02).
>
> History (status 2026-11-19 to 2026-11-23): proposed extension of v0.2 (v0.2 adopted 2026-11-22; this extension not adopted). It was not part of v0.2 as committed (rule 3 of section 2.1 allows one commit per trial). v0.1 does not change. The scorer applies it only when the caller passes `n_commits`. Roadmap item: P5-27 (gap 76). Pre-registration: [plan](../experiments/2026-11-18-p5-27-streaming-prefix/plan.md). Code: `safe_wpm(..., metric_version="0.2", n_commits=...)`, `fidetype.trust.stream_commit`.

**Why.** A streaming guard decides while the trial goes on. It can commit "i need" after 2 s and "some water" after 4 s. v0.2 as committed has no rule for the second commit.

### 7.1 Rule

The commits of a trial are **append-only**: each commit adds words after the words already committed; no commit removes or changes a committed word. Let J_i be the number of commits of trial i and C_i the union of its commits (the final committed text, K_i words; `complete_i` = the last commit claims the whole sentence).

```
(7) right_i   = every commit of trial i is right by (1)   ( = C_i is right by (1), because the commits are nested )
    credit_i  = (2) applied to C_i
    penalty_i = (4) applied to C_i                        (the user deletes all committed words and types the true ones)
    read_i    = c * J_i + w * K_i                         (every commit pays c; every committed word is read once)
    time_i    = neural_s_i + [committed_i and not right_i] * penalty_i + read_i
```

| Case | Words | Time |
|---|---|---|
| "i need" (prefix) then "some water" (complete), truth "i need some water" | 4 | `neural_s` + 2 c + 4 w |
| "i need" then "some" (both prefix), truth "i need some water" | 3 | `neural_s` + 2 c + 3 w |
| "i need" then "sun", truth "i need some water" | 0 | `neural_s` + penalty("i need some") + 2 c + 3 w |
| one commit only | as v0.2 | as v0.2 (J_i = 1) |

### 7.2 Certification

- **Risk unit: the trial.** A trial is wrong if **any** of its commits is wrong. The rate is wrong trials / all trials.
- A policy with a trial of two or more commits gets status `certified` only with a bound on this loss: `risk = "wrong-stream-commit"`. A `wrong-stream-commit` bound also certifies a policy with one commit per trial (the two losses are then the same).
- `min_prefix_words` (section 6) is not defined for trials with several commits; the scorer refuses the combination.
- With one commit per trial, (7) gives exactly the v0.2 value (with or without reading cost). A test checks this.

### 7.3 What an entry reports

All v0.2 fields, plus a `multi_commit` block: `n_commit_events`, `n_trials_with_several_commits`, `max_commits_per_trial`, the rule text and its status. The per-trial JSON Lines file of the CLI takes `n_commits` (default 1 for a committed trial).

### 7.4 Result (P5-27, T15, pre-registered)

[Results](../experiments/2026-11-18-p5-27-streaming-prefix/results.md): under v0.2 + reading cost (0.5 s + 0.3 s/word) + rule (7), the streaming guard gives **2.34 [2.11, 2.57]** (certified; 310 committing trials, 446 commit events, 5 / 701 wrong trials, CP95 [0.0023, 0.0166]) against **4.67 [4.26, 5.07]** for the one-commit prefix guard: Δ −2.32 [−2.63, −2.02], **single beats stream**. The stream commits right words much earlier (median 1.44 s after the true word ends, against 11.20 s), but it never extends a commit at the trial end and makes no complete commit. Rule (7) itself worked as designed: it reproduced the v0.2 value for the one-commit arm (4.67) and charged every commit event its reading cost. A hybrid guard is roadmap item P5-28 (gap 92).

> **Our take:** charging the fixed reading cost per commit, not per trial, is the important part. Without it, a guard could split a sentence into many one-word commits at no cost. With it, each extra commit must earn its 0.5 s.

### 7.5 Result (P5-28, T15, pre-registered): hybrid guard

[Results](../experiments/2026-11-19-p5-28-hybrid-prefix/results.md): a **hybrid** guard commits mid-trial with the P5-27 streaming score (λ_mid 0.99, fixed) and decides again at the trial end with the P5-24 prefix score (λ_end 0.94, certified jointly on the trial loss), so the end decision can extend the early commit. Under v0.2 + reading cost + rule (7) it gives **4.89 [4.49, 5.27]** (certified; 500 committing trials, 803 commit events, 18 / 701 wrong trials, CP95 [0.0153, 0.0403]; controls 0 / 300 and 0 / 300) against **4.67 [4.26, 5.07]** for the one-commit guard: Δ **+0.22 [+0.14, +0.31]**, **hybrid beats single**. Median latency of right words 3.85 s vs 11.20 s (first right word 2.72 s vs 14.00 s). Caution: λ_mid came from P5-27 on the same certify items; with δ split over three λ_mid values the gain disappears (4.63, Δ −0.04 [−0.15, +0.08]). The T12 replication with λ_mid fixed in advance is P5-29 (gap 95).

> **Our take:** rule (7) charged the hybrid for its 338 extra commit events (3.2 more reading minutes on 218 neural minutes) and it still came out level or ahead. So the several-commits rule does not punish a guard that shows text early, as long as the early commits are right. This supports adopting rule (7) together with v0.2 if the user adopts v0.2. (Rule (7) was adopted on 2026-11-24.)
