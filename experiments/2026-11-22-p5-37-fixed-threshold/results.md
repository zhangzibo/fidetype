---
title: P5-37 fixed-threshold-0 rule for lm_beam_direction - stopped at the data audit
type: experiment
task: P5-37
updated: 2026-11-22
---

# P5-37: fixed threshold 0 for `lm_beam_direction` - stopped before any number (2026-11-22)

Roadmap: [P5-37](../../wiki/questions/roadmap-standard.md#p5-37-fixed-threshold-0-rule-for-the-lm_beam_direction-offer-gate) (gap 189). Earlier work: [P5-36b](../2026-11-22-p5-36b-two-direction-lm/results.md) (pre-registration `dab694f`, results `a7bfbc8`).

Audit code: [data_audit.py](data_audit.py). Counts: [results/data-audit.json](results/data-audit.json). The audit reads only sentence metadata (block number, excluded flag, intended-text length check). It computes no log-prob, no guard decision and no gate value.

## Outcome

**Stopped at step 1. No clean unused `willett-hw` data exists.** There is no pre-registration commit and no run. No number of the gate was computed on any new data. The gap 189 done-when is **not met**, and it is not tested.

## Data audit: where every Willett sentence goes

The public Willett handwriting 2021 data (T5, CC0 1.0) has 1,000 sentences in 10 sessions (`sentences.mat`). The session `t5.2019.06.03` has no sentences (only straight-line trials). The `willett-hw` decoder uses the P15-08 split (P14-33: equal to P15-08): test = the last block of each session, val = one salted-hash block of each session, pool = all other blocks.

| Group | Sentences | Who used them | Clean and unused? |
|---|---|---|---|
| Test blocks, usable | 80 | P14-41, P14-54, P14-55, P14-57 (the `rev_out` test set), P5-36, P5-36b (B1, B2, B4, B5); the post-hoc threshold-0 look of P5-36b | no |
| Val blocks, usable | 106 | P14-41 guard calibration (all 106); P5-36b fit (S, 66) and B3 (LTT, 40); P14-57, P5-36 | no |
| Pool blocks, usable | 781 | P15-08 trained the `willett-hw` decoder (`R-all-s0`, budget "all") on every pool sentence, with its text labels, and fit the per-session z-score on them | no (see below) |
| Excluded by the dataset authors | 33 (test blocks 2, val blocks 1, pool blocks 30) | nobody: the reader skips them, and P15-08 training skips them | unused, but not clean (see below) |
| Empty text or out-of-vocabulary text, not excluded | 0 | - | - |

Sum: 80 + 106 + 781 + 33 = 1,000.

Other files in the same data:

- `singleLetters.mat` (10 sessions): isolated characters in an instructed-delay task, with no real-time decoder. One character per trial is not a sentence. A direction score that compares a forward and a backward LM decode has almost no signal on one character. These trials are not valid real inputs for this test.
- `rev_out` is `lp[::-1]` of a real input. It is deterministic, so new `rev_out` draws need new real inputs. There are no `rev_out` draws without them.

### Why the pool is not clean

The decoder saw every pool sentence in training. On its own training data a decoder gives cleaner frames than on held-out data (P14-33: val greedy CER 0.260, test 0.305; we expect a lower training CER, but we did not measure it). With threshold 0 the two rules count almost the same sentences: because `D(rev x) = -D(x)` exactly and `coherence` is equal for `x` and `rev x`, a real offer is removed iff `D(x) < 0`, and its `rev_out` is offered iff `D(x) <= 0`. So the whole test measures one thing: the fraction of real offers with `D <= 0`. Cleaner frames give a larger `D`. So the pool would give an **optimistic** estimate for both rules. A pass on the pool would not show that the rule holds on new data. A fail on the pool would be informative.

### Why the 33 excluded sentences are not clean

The dataset readme says why they are excluded. In most of them a false head-turn detection started the next trial before T5 finished, so the sentence is incomplete. Other causes: T5 skipped a free-write question; the intended spelling was unknown; a decoder software bug at the start of 4 blocks (2020.01.06); T5 forgot the phrase in copy-from-memory trials. These are not normal use. The set is also small: 5 % of 33 gives an integer limit of 1, so the test has almost no power.

## Options (for the orchestrator and the user)

| Option | What it needs | What a pass would show | Cost |
|---|---|---|---|
| **A. Pool with a stated bias** | Pre-register fixed `tau` 0 on the 781 pool sentences (all 781, no sampling), both guards, limits 39 / 781 (5 %). State in advance that a pass is optimistic and a fail is final. Add a descriptive bias check: greedy CER of the pool against the val CER | a weak pass only (decoder-seen data); a fail would close gap 189 as negative | CPU, about 1-2 h (decoder on 781 sentences plus 4 beam searches per sentence) |
| **B. Held-out retrain** | Retrain the decoder with one more held-out block per session (about 80-100 new held-out sentences), then build both guards again on it | the rule on truly new data, but for a **new** decoder and new `config_id` values, not the shipped `willett-hw` guards | GPU training (P15-08 recipe; seed 1 failed there), plus guard calibration; days |
| **C. Accept the LM-guard evidence only** | Change the gap 181 done-when to need one guard (the LM guard passed with a val-only fit in P5-36b) and record the built-in guard as a limit | nothing new; a scope decision | none |
| **D. Close the `rev_out` route by design** | `rev_out` comes only from a software fault after the decoder. Record the residual risk, and rely on P5-36 route 1 plus gap 192 (P4-26, producer frame times through the adapters) | nothing new on `rev_out` values; it moves the fix to the producer side | P4-26 work (CPU) |
| **E. Wait for new T5 data** | A new public release of T5 handwriting sentences | the clean test as planned | external; not known if it will happen |

A second dataset does not help this gap directly: both guards belong to the `willett-hw` decoder, which reads only T5 Utah-array data from these 10 sessions.

> **Our take:** option A is the cheapest useful step, if it is pre-registered as "fail is final, pass is weak". Its pass alone should not close gap 181. Option C or D is the honest way to close gap 181 without new data. Option B tests a different object and is expensive.

## Records to apply

- **Gap 189 (P5-37):** stays `todo` (or `blocked` on a data decision). Evidence line: "2026-11-22 (P5-37 data audit, [results](../../experiments/2026-11-22-p5-37-fixed-threshold/results.md)): no clean unused `willett-hw` data. The 1,000 Willett sentences are test 80 and val 106 (both used by P14-57 / P5-36 / P5-36b), pool 781 (decoder training, P15-08) and 33 excluded by the authors (incomplete trials). No pre-registration and no number. Options A-E in the results. A decision is needed."
- **Gap 181 (P5-36):** cannot close. It stays `in_progress`. The built-in guard has no valid pass. Closing it needs a decision (option C or D) or new evidence (option A as weak evidence, B or E).
- **Gap 190 (P14-60):** must **not** start. It needs gap 189 to pass first.
- No change to the library, packaged gates, guard files, manifests or `config_id` values.

## Run record

Data audit only: 2026-11-22 22:11, CPU, a few seconds, metadata reads only. No detached job. Nothing written to `C:\Users\zhang\bci-data\derived\`.
