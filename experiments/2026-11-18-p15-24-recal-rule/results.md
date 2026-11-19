---
title: P15-24 same-decoder re-calibration rule - replay of P15-13 on M4-13 - results
type: experiment
task: P15-24
updated: 2026-11-18
---

# P15-24: does the re-calibration rule let the same decoder re-tune, and does the gate still refuse worse and broken decoders? (results)

Pre-registration: [plan.md](plan.md) (commit `0254ebc`, with the code, before any run on M4-13 data). Aggregates: [results/results.json](results/results.json), log [results/run.log](results/run.log). Ledgers: `C:/Users/zhang/bci-data/derived/p15-24/` only. Analysis: rule checks computed from `results.json` and compared with the P15-13 [results.json](../2026-11-18-p15-13-gate-fix/results/results.json).

Run: 2026-11-18 12:54-14:19 (5,114 s, CPU, background class, 4 threads, peak 1.35 GB), detached. The design is the P15-13 design without change ([P15-13 results](../2026-11-18-p15-13-gate-fix/results.md)): 4 runs = seeds {0, 1} x users {oracle, feedback-r0.3}, 7 blocks of 48 check items + phase C, probe W. The only change in the gate: B4 and B6 (re-calibrations of the live M4-13) are `kind="recalibration"` and use the re-calibration rule (pass on identical top-1, or `P(Bin(48, 0.1) <= w) <= 0.05`, that is `w <= 1`). Plumbing dry run: passed without a code change ([results/dryrun-m4-12](results/dryrun-m4-12/)).

## Verdict (pre-registered rules)

| rule | pass if | result |
|---|---|---|
| **R1** broken refused (B3), guard config unchanged | 4 / 4 runs | **pass** (4 / 4) |
| **R2** broken refused against the weak champion (probe W, new gate) | 4 / 4 runs | **pass** (4 / 4; 48 worse vs 0 better, the same counts as P15-13) |
| **R3** worse M4-12 refused (B2, B5, B7 while M4-13 is live), at least one by the challenger test | every run where B1 was accepted (4) | **pass** (12 / 12 refused, all 12 by the challenger test) |
| **R4** re-calibrations: refused <= 1 of 8, and all 8 registered as `kind="recalibration"` | both parts | **pass** (0 of 8 refused; 8 / 8 `recalibration`) |
| **R5** phase-C wrong-commit rate <= 0.05 | 4 / 4 runs | **pass** (0.0082 in every run, CP95 [0.0017, 0.0238]; 114 commits in total, not vacuous) |
| **R6** audit + null controls | all runs | **pass** (ledgers verify: 4 / 4 main, 8 / 8 W; every proposal decided; the config changes on accept only; 24 / 24 controls of accepted updates pass, max 2 / 100 commits, allowed 5) |
| **R7** the re-calibration rule on the counts of every refused decoder / broken proposal also refuses it | all such proposals | **pass** (20 / 20 refused; fewest worse items 34 of 48, p_abs 1.0) |

**Decision rule of the plan:** R1-R7 pass. **Gap 72 (P15-24) closes.** The rule stays the default (`recalibration_rule="absolute"`).

## D2: the 8 re-calibrations

"w / b / unk" = worse (unknown included) / better / unknown pairs of 48; "ident" = identical top-1 texts. P15-13 p = the decoder rule on the same block (`2 min(p_ni, p_abs)`).

| run | block | w / b / unk | ident | p (new rule) | passed by | P15-13 decision (p) |
|---|---|---|---|---|---|---|
| s0 oracle | B4 | 0 / 1 / 0 | 47 | 0.0064 | few worse items | accept (0.013) |
| s0 oracle | B6 | 0 / 2 / 0 | 46 | 0.0064 | few worse items | accept (0.013) |
| s0 feedback-r0.3 | B4 | 0 / 0 / 0 | 47 | 0.0064 | few worse items | accept (0.013) |
| s0 feedback-r0.3 | B6 | 0 / 0 / 0 | 46 | 0.0064 | few worse items | accept (0.013) |
| s1 oracle | B4 | 0 / 0 / 0 | 48 | - | identical top-1 | accept (identical) |
| s1 oracle | **B6** | **1 / 2 / 0** | 45 | **0.040** | **few worse items** | **reject (0.081)** |
| s1 feedback-r0.3 | B4 | 0 / 0 / 0 | 48 | - | identical top-1 | accept (identical) |
| s1 feedback-r0.3 | B6 | 0 / 2 / 0 | 45 | 0.0064 | few worse items | accept (0.013) |

The only case that changes is the P15-13 refusal (s1 oracle B6): the same 1 worse vs 2 better pairs now pass at p_abs 0.040 <= 0.05.

## D1 and D3: what else changed against P15-13

- W and B1-B5 repeat P15-13 exactly in all 4 runs (same decisions, same counts). B1 accepted 4 / 4 (oracle p 2.9e-9 and 1.1e-10; feedback-r0.3 p 0.038 and 0.026), as in P15-13.
- s1 oracle only: B6 is accepted (P15-13: refused), so the guard of the B6 re-calibration is live from B6 on. Phase-C commits in B6: 5 (P15-13: 7, with the B4 guard). B7: M4-12 still refused (34 worse, the same count); phase-C commits 3 -> 1.
- Phase C over all blocks:

| run | commits | wrong | wrong-commit rate [CP95] | precision | P15-13 commits / wrong |
|---|---|---|---|---|---|
| s0 oracle | 28 | 3 | 0.0082 [0.0017, 0.0238] | 0.893 | 28 / 3 |
| s0 feedback-r0.3 | 28 | 3 | 0.0082 [0.0017, 0.0238] | 0.893 | 28 / 3 |
| s1 oracle | 29 | 3 | 0.0082 [0.0017, 0.0238] | 0.897 | 33 / 4 |
| s1 feedback-r0.3 | 29 | 3 | 0.0082 [0.0017, 0.0238] | 0.897 | 29 / 3 |

> **Our take:** the rule removes the one cost of default deny that P15-13 found, and it changes nothing else: every worse or broken decoder is still refused, also when its counts are judged by the more lenient re-calibration rule (R7: at least 34 worse items of 48, where the rule allows 1). A re-calibration that is accepted can commit less (s1 oracle: 29 vs 33 phase-C commits), because its own block LTT sets the threshold. That is the intended direction. The rule still allows only 1 worse item in 48. A user whose drift changes the top-1 on more items needs a larger check block. This replay had no such case, so we do not register a new gap for it.

## Gap decisions
- **P15-24 (gap 72): closed.** Done-when: a pre-registered check (this replay) measures how often re-calibrations of the same decoder are refused (0 of 8; P15-13: 1 of 8). The chosen remedy (the re-calibration rule, `0254ebc`) keeps that rate low. It accepts none of the P15-13 broken or worse decoders (R1-R3, R7).
- No new gap.

## Deviations
- None. The dry run passed without a code change.
