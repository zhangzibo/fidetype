# Safe WPM v0.2: proposal (prefix credit and speech time)

> **Status: PROPOSED, NOT ADOPTED.** The user decides adoption at the weekend (week of 2026-11-18). Until then, `safe-wpm/0.1` ([docs/safe-wpm.md](safe-wpm.md)) stays the headline metric. No published v0.1 number changes. The scorer computes v0.2 only when the caller asks for it (`metric_version="0.2"`). Adoption needs one switch: the default of `metric_version` and the leaderboard column.

Roadmap item: P14-26 (gap 66). Source: the [P14-23 bottleneck analysis](../wiki/questions/safe-wpm-bottleneck.md). Code: [`src/fidetype/benchmark/safe_wpm.py`](../src/fidetype/benchmark/safe_wpm.py) (`safe_wpm(..., metric_version="0.2")`, `prefix_outcome`). Tests: `tests/test_safe_wpm.py` (the `v02` tests). First user: P5-24 ([plan](../experiments/2026-11-18-p5-24-prefix-commits/plan.md)).

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
3. **Words after a prefix commit.** The words of y_i after the committed prefix earn 0 words and add no time. This is the v0.1 rule for a withheld trial: the user types them, and the BCI did not make them. A trial has at most one commit in v0.2. A second commit in the same trial (streaming, word by word) is not defined here.
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
| `definition`, `definition_status` | `safe-wpm/0.2` and "proposed, not adopted" (until the user adopts it) |
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

Command line: `fidetype benchmark safe-wpm --trials t.jsonl --guarantee g.json --metric-version 0.2`. Per-trial JSON fields: `committed`, `truth`, `neural_s`, and for a commit `committed_text` + `complete` (or `committed_words` + `penalty_chars`); optional `speech_s`. Without `--metric-version` the CLI scores v0.1, where only the exact sentence counts.

## 5. Adoption (the user's decision)

| Option | Effect |
|---|---|
| Adopt v0.2 | Default `metric_version="0.2"`; the leaderboard column becomes v0.2 with a dated note; v0.1 stays as a second column. Every published sentence-level number stays the same (rule 6). |
| Keep v0.1 only | v0.2 stays an opt-in research field. Prefix guards are reported with v0.2 next to v0.1 and never in place of it. |
| Change v0.2 first | For example a stricter wrong-prefix penalty (the whole sentence, the "sentence" variant), or speech time as the headline. Each change is a new pre-registered text. |

Open points for the decision:
- The wrong-prefix penalty charges only the k replaced words. A stricter user model (the user re-reads and rewrites the whole sentence) gives the v0.1 penalty. P14-23 found the difference small on T15 (5.43 vs 5.55, exploratory).
- One commit per trial. A streaming guard that commits word by word needs a v0.3.
- Reading time is still 0, as in v0.1.

> **Our take:** v0.2 removes a strictness of v0.1 that does not protect the user: a right prefix is real typed text. It keeps the safety part: every wrong commit, prefix or complete, counts against the same certified rate and costs correction time. Because v0.2 equals v0.1 for sentence-level policies, adoption changes no existing number.
