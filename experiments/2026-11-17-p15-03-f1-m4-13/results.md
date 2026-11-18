---
title: P15-03a (F1) champion / challenger replay on T15 with the M4-13 decoder - results
type: experiment
task: P15-03, P15-13
updated: 2026-11-18
---

# P15-03a: does the update gate refuse a worse decoder on real data? (results)

Pre-registration: [plan.md](plan.md) (commit `97a2fc4`, before any M4-13 output). This is the CPU part of [P15-03](../../wiki/questions/roadmap-standard.md#p15-03-e2-full-runs-on-t12-and-t15); the full GPU P15-03 stays open. Aggregates: [results/results.json](results/results.json), log [results/run.log](results/run.log). Per-trial records and ledgers: `C:/Users/zhang/bci-data/derived/p15-03-f1-m4-13/` only.

Run: queue stage `p15-03`, 2026-11-17 20:29-21:43 (4,436 s, CPU, background class, 4 threads, peak 1.3 GB). Decoders: M4-12 fixed0 (start champion) and M4-13 long0 `best.pt` (step 115,000, SHA-256 `8fafe916...`, same hash for val_select and val_eval); broken = M4-13 with the frames in reverse time order. 4 runs = seeds {0, 1} x users {oracle, feedback-r0.3}; 7 blocks each.

## Verdict

| rule (pre-registered) | pass if | result |
|---|---|---|
| **H1** better accepted (B1) | >= 3 of 4 runs | **pass** (4 / 4) |
| **H2** worse refused (every M4-12 proposal while M4-13 is live; >= 1 by the sign test with >= 10 discordant pairs) | every run where B1 was accepted (4) | **fail** (2 / 4: pass with the oracle user, fail with feedback-r0.3) |
| **H3** broken refused (B3), guard config unchanged | all 4 runs | **fail** (2 / 4: refused with the oracle user, accepted with feedback-r0.3) |
| **H4** phase-C wrong-commit rate <= 0.05 | all 4 runs | **pass** (0.0082, 0.0082, 0.0082, 0.0055; 78 commits in total, so not vacuous) |
| **H5** null controls of every accepted update | all accepted updates | **pass** (20 / 20 accepted updates; max 2 / 100 commits, allowed 5) |
| **H6** audit: ledger verifies, every proposal decided, config changes on accept only | all runs | **pass** (4 / 4) |
| H7 (secondary) PER test agrees with the gate | descriptive | agrees on 12 of 16 decoder proposals; the 4 disagreements are the worse M4-12 accepted with feedback-r0.3 |
| D1 phase-C use | descriptive | oracle: 28 and 29 commits (precision 0.89, 0.90); feedback-r0.3: 11 and 10 (0.73, 0.80) |

**H3 answer (for gap P15-13):** the stronger champion fixes the broken-decoder case **only when the truth of every check item is known**. With the oracle user the sign test refuses the reversed decoder (15 worse vs 0 better, p 3.1e-5; 16 vs 0, p 1.5e-5). With the feedback-r0.3 user, the gate accepts it in both seeds (2 worse vs 0 better, p 0.25) and the reversed decoder becomes live for two blocks. The dry-run finding is confirmed on real data.

## Per-block decisions

Oracle user (both seeds have the same decisions; seed 0 numbers, seed 1 in brackets where they differ):

| block | proposal | decision | sign test: challenger worse / better (p) | per-item PER challenger vs champion (p_worse) | live after |
|---|---|---|---|---|---|
| B1 | M4-13 vs live M4-12 | accept | 1 / 18 [0 / 18] | 0.080 vs 0.204 (1.0) | M4-13 |
| B2 | M4-12 | reject: worse | 16 / 1, p 1.4e-4 [16 / 2, p 6.6e-4] | 0.232 vs 0.105 (5.7e-9) | M4-13 |
| B3 | broken (reversed M4-13) | reject: worse | 15 / 0, p 3.1e-5 [16 / 0, p 1.5e-5] | not computed | M4-13 |
| B4 | re-calibration of M4-13 | accept | 0 / 0 | - | M4-13 |
| B5 | M4-12 | reject: worse | 18 / 0, p 3.8e-6 | 0.237 vs 0.089 (3.2e-9) | M4-13 |
| B6 | re-calibration of M4-13 | accept | 0 / 1 | - | M4-13 |
| B7 | M4-12 | reject: worse | 6 / 0, p 0.016 | 0.316 vs 0.162 (3.0e-9) | M4-13 |

Feedback-r0.3 user (seeds 0 and 1 have the same decisions):

| block | proposal | decision | sign test worse / better (p), seed 0; seed 1 | truth known on check items (of 48), s0; s1 | PER challenger vs champion (p_worse) | live after |
|---|---|---|---|---|---|---|
| B1 | M4-13 vs live M4-12 | accept | 1 / 18; 0 / 18 | 34; 31 | 0.080 vs 0.204 (1.0) | M4-13 |
| B2 | M4-12 vs live M4-13 | **accept** | 3 / 1 (p 0.31); 5 / 1 (p 0.11) | 10; 18 | 0.232 vs 0.105 (5.7e-9) | M4-12 |
| B3 | broken vs live M4-12 | **accept** | 2 / 0 (p 0.25); 2 / 0 (p 0.25) | 18; 14 | not computed | broken |
| B4 | re-calibration of broken | accept | 0 / 0 | 14; 16 | - | broken |
| B5 | M4-13 vs live broken | accept | 0 / 3; 0 / 6 | 10; 16 | 0.089 vs 0.841 (1.0; p_better 8e-10) | M4-13 |
| B6 | re-calibration of M4-13 | accept | 0 / 0 | 21; 23 | - | M4-13 |
| B7 | M4-12 vs live M4-13 | **accept** | 1 / 0 (p 0.5); 1 / 0 (p 0.5) | 19; 16 | 0.316 vs 0.162 (3.0e-9) | M4-12 |

Phase-C totals (365 items per run):

| run | commits | wrong | wrong-commit rate [CP95] | precision | blocks with commits | final live |
|---|---|---|---|---|---|---|
| s0 oracle | 28 | 3 | 0.0082 [0.0017, 0.0238] | 0.893 | 7 / 7 | M4-13 |
| s0 feedback-r0.3 | 11 | 3 | 0.0082 [0.0017, 0.0238] | 0.727 | 5 / 7 | M4-12 |
| s1 oracle | 29 | 3 | 0.0082 [0.0017, 0.0238] | 0.897 | 7 / 7 | M4-13 |
| s1 feedback-r0.3 | 10 | 2 | 0.0055 [0.0007, 0.0197] | 0.800 | 5 / 7 | M4-12 |

The blocks without commits are B3 and B4 of the feedback runs, where the broken decoder was live. The guard there commits nothing, so the guarantee holds, but the user gets no help.

## Why the gate fails with partial feedback (exploratory analysis)
- The `feedback-r0.3` user knows the truth of a check item only if the truth is in the candidate's top-5 list (accept) or the user retypes it (p 0.3). Unknown truth counts as a wrong top-1 for **both** sides (the pessimistic P15-02 rule).
- A bad candidate rarely lists the truth, so the truth is known on only 10-19 of 48 items. Then both sides are "wrong" on most items: the champion is wrong on 40-46 of 48. Few pairs are discordant (1-6), and the sign test has no power at level 0.05.
- The per-item PER test (H7) separates the decoders well (p_worse 3e-9 to 6e-9 for every M4-12 proposal). But it used the true phonemes of all 48 items. A real user gives the truth only on the known items, so a deployable PER test must use those items only, or count an unknown item against the challenger.
- No PER value was computed for B3 (broken) by design of run.py (PER only for `decoder` proposals). The B5 rows of the feedback runs show the broken decoder's PER as champion: 0.841 vs 0.089 for M4-13.

> **Our take:** the guarantee (H4) holds in every run; the gate's job of keeping the better decoder does not hold under realistic feedback. The fix belongs in the gate, not in the decoder: a stronger champion did not help when the truth is mostly unknown. P15-13 must test its PER / non-inferiority rule with the feedback-r0.3 user, not only with an oracle.

## Gap decisions
- **P15-13** (update gate: PER-based non-inferiority test): the pre-registered H3 result is now read: **H3 fails** (broken decoder accepted in 2 of 4 runs, both with feedback-r0.3). The item stays open (code change, unit test and replay not yet done) and is now unblocked. Its replay should include the feedback-r0.3 user.
- **P15-03**: CPU part P15-03a done (this page). The full P15-03 (GPU day-layer adaptation on T12 and T15) stays open.

## Deviations
- None in the method. `results.json` field `provenance.source` is `m4-12`: it names the start champion; the M4-13 provenance is under `provenance.m4-13`.
