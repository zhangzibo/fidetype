---
title: P5-37 fixed threshold 0 for lm_beam_direction on the willett-hw pool - results
type: experiment
task: P5-37
updated: 2026-11-23
---

# P5-37: fixed threshold 0 for `lm_beam_direction` on the 781 pool sentences (results, 2026-11-23)

Roadmap: [P5-37](../../wiki/questions/roadmap-standard.md#p5-37-fixed-threshold-0-rule-for-the-lm_beam_direction-offer-gate) (gap 189). Earlier work: [P5-36b](../2026-11-22-p5-36b-two-direction-lm/results.md) (`dab694f`, `a7bfbc8`).

History: the data audit (`5d74a8e`, 2026-11-22 22:12) found no clean unused `willett-hw` data (section "Data audit" below). The user chose **option A** (the decoder's training pool, bias stated in advance). Pre-registration: [plan.md](plan.md) with [run.py](run.py) and [launch.py](launch.py), commit `d8231f8` (2026-11-22 23:30:42), before any gate number on the pool. Numbers: [results/results.json](results/results.json); log: [results/run.log](results/run.log); audit counts: [results/data-audit.json](results/data-audit.json). Per-item records (actions, coherence, feature values, times; no text) stay in `C:\Users\zhang\bci-data\derived\p5-37\` only.

## Verdict

| Guard | P1 `rev_out` offers (<= 39 / 781) | P2 real offers removed (<= 39 / 781) | Checks C0-C2 | Secondary S0, S1 |
|---|---|---|---|---|
| Built-in (`tcfg-39aac48688b8bd12`) | **pass: 1 / 781** (coherence only: 767) | **pass: 1 / 781** (767 -> 766) | hold | all pass |
| LM (`tcfg-f498c0637536daec`) | **pass: 0 / 781** (coherence only: 764) | **pass: 0 / 781** (767 -> 767) | hold | all pass |

**Pass for both guards, as pre-registered weak evidence.** The fixed-threshold-0 rule meets the gap 189 done-when (as amended by option A) on the pool. The plan stated in advance that this data is decoder-seen: a pass is **weak** evidence, it does not show that the rule holds on new data, gap 181 stays open, and gap 190 does not start on this pass alone. A fail would have been final; there is no fail.

No library code, packaged gate, guard file or manifest changed. `config_id` values unchanged.

## Primary rules and checks (781 pool sentences per guard)

| | Built-in | LM |
|---|---|---|
| Real offers, coherence only -> both gates | 767 -> 766 | 767 -> 767 |
| **P2** real offers removed | **1** (`D` = -0.025) | **0** |
| `rev_out` offers, coherence only -> both gates | 767 -> **1** | 764 -> **0** |
| S0 `rev_out` emits (offer or commit) with both gates | 1 | 0 |
| Commits (real, `rev_out`) | 0, 0 | 0, 0 |
| Real offers with `D < 0` / `D = 0` | 1 / 0 | 0 / 0 |
| C0 decoder path = stored P14-41 val log-probs (5 sentences) | max abs difference 0.0 | (same check) |
| C1 antisymmetry (1e-9); `coherence` equal (1e-9) | 781 / 781; 781 / 781 | 781 / 781; 781 / 781 |
| C2 equivalence (both gates vs "coherence, then `D < 0`") | 1,562 / 1,562 | 1,562 / 1,562 |

For the LM guard, `rev_out` has 3 fewer coherence-only offers than real input (764 vs 767), with equal `coherence`. The difference comes from other steps of the LM-guard decision (for example the readout's no-signal gate), not from an offer gate.

## Secondary S1: null inputs (781 each; emits with coherence only -> both gates)

| Null | Built-in | LM | Rule (<= 39, not more than before, `offer_control`) |
|---|---|---|---|
| time-shuffled raw input (d = 0) | 1 -> **0** (CP95 0.0038) | 1 -> **1** (CP95 0.0061) | pass, pass |
| zero raw input | 0 -> 0 | 0 -> 0 | pass, pass |
| `rev_in` (raw input reversed before the decoder) | 6 -> **4** (CP95 0.0117) | 0 -> 0 | pass, pass |
| frame-shuffled log-probs | 0 -> 0 | 0 -> 0 | pass, pass |
| near-uniform log-probs | 0 -> 0 | 0 -> 0 | pass, pass |

No null input was committed.

## Descriptive (no rule)

| | Built-in | LM |
|---|---|---|
| `D` of the real offers (min / 5 % / median / 95 % / max) | -0.025 / 0.510 / 0.969 / 1.400 / 2.545 | 0.208 / 0.540 / 0.989 / 1.479 / 2.172 |
| **P5-36b fitted `tau`** (val S) | 0.3259 | 0.1344 (fitted with the earlier LM guard `tcfg-26ae951a20a0cddd`) |
| at that `tau`: real offers removed / `rev_out` offers | **8 / 781** / 0 | 0 / 781 / 0 |
| two beam searches, median (5 % / 95 %) | 0.193 s (0.040 / 0.444) | 0.080 s (0.017 / 0.177) |
| median ratio extra / coherence-only decision | 0.70 | 0.44 |

Bias check: the greedy CER of the pool is **0.2177** (7,401 / 33,993 characters). The P14-33 references are val 0.2603 and test 0.3051. So the pool frames are cleaner than the held-out frames, as expected, but the decoder does not fit its training text exactly.

> **Our take:**
> - On 781 sentences the threshold-0 rule loses almost nothing: 1 real offer (built-in) and 0 (LM), and it stops all but 1 `rev_out` offer. On the P14-57 test set the post-hoc look gave 1-2 of 80. The two sets agree in direction, but the pool is decoder-seen, so the pool rate (about 0.1 %) is probably lower than the rate on new data.
> - The `D` distribution on the pool is shifted up against the test set (median 0.97-0.99 against 0.82-0.88 in P5-36b). This matches the cleaner frames (CER 0.218 against 0.305). We cannot separate "the rule works" from "the decoder knows these sentences" with this data. That is why the pass is weak.
> - On the same pool records the P5-36b fitted `tau` of the built-in guard removes 8 real offers against 1 at threshold 0, with the same `rev_out` result (0 against 1). This repeats the P5-36b finding that its fitted `tau` was too high, now on 781 sentences. It is descriptive only.
> - The `rev_in` null (reversal before the decoder) gives 4 / 781 offers for the built-in guard with both gates. That is in the limit, and it is a different fault from `rev_out`.

## Deviations from the plan

None. The run used the pre-registered objects, inputs, seeds and rules. Run time 16,945 s (4.7 h; plan estimate 4.5-5.5 h, cap 8 h).

## Run record

CPU only (`HIP_VISIBLE_DEVICES`, `CUDA_VISIBLE_DEVICES` = -1), isolation class `background`, 1 thread, keep-awake; the GPU job P15-43 ran at the same time. 2026-11-22 23:30:50 to 2026-11-23 04:13:15: C0 7 s; pass 1 (real, `rev_out`) 3,297 s; pass 2 (nulls) 13,624 s; score 10 s. Peak working set 818 MB (limit 2,500 MB). `DONE` written.

## Limits

- **Decoder-seen data** (section "Data audit"): the main limit. It was stated in advance.
- One participant (T5), one decoder checkpoint, one LM, one beam setting.
- `rev_out` is one synthetic fault form (rows reversed after the decoder). A partial reversal or a reorder of chunks is not tested.
- Times come from a shared machine with a GPU job running; they are indicative only.

## Records to apply

- **Gap 189 (P5-37): `done`**, as weak evidence. Evidence line: "2026-11-23 (P5-37 option A, data audit `5d74a8e`, pre-registration `d8231f8`, results `2451892`, [results](../../experiments/2026-11-22-p5-37-fixed-threshold/results.md)): fixed `tau` 0 for `lm_beam_direction` on the 781 decoder-seen pool sentences passes for both guards: built-in `tcfg-39aac48688b8bd12` `rev_out` offers 1 / 781, real offers removed 1 / 781; LM `tcfg-f498c0637536daec` 0 / 781 and 0 / 781 (limits 39). C0-C2 hold; nulls S0/S1 pass. Pre-stated: a pass is weak evidence (decoder trained on the pool; pool greedy CER 0.218 vs test 0.305). Descriptive: the P5-36b fitted `tau` (0.326) removes 8 / 781 on the same records."
- **Gap 181 (P5-36): stays `in_progress`.** Per the pre-registration, this pass alone does not close it. It now has: LM guard pass on the P14-57 test set with a val-only fit (P5-36b), and both guards pass with the fixed threshold 0 on decoder-seen data (P5-37). The open part: a built-in-guard result on clean new data. Closing it still needs a user decision (P5-37 audit options C or D) or new data (option B or E).
- **Gap 190 (P14-60): does not start** on this pass alone (pre-stated). If the user later closes gap 181 by decision, gap 190 can start with the fixed threshold 0 as the rule.
- No change to the library, packaged gates, guard files, manifests or `config_id` values.

## Options from the data audit (for reference)

| Option | Status |
|---|---|
| A. Pool with a stated bias | **done here** (weak pass) |
| B. Held-out retrain (new decoder, new `config_id`) | open; GPU, days |
| C. Accept the LM-guard evidence only for gap 181 | open; user decision |
| D. Close the `rev_out` route by design (P5-36 route 1 + gap 192 = P4-26) | open; user decision |
| E. Wait for new public T5 data | external |

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

