---
title: P15-13 default-deny update gate - replay of P15-03a on M4-13 with partial feedback - results
type: experiment
task: P15-13
updated: 2026-11-18
---

# P15-13: does the default-deny gate refuse worse and broken decoders under partial feedback? (results)

Pre-registration: [plan.md](plan.md) (commit `e788029`, with the code, before any run). Aggregates: [results/results.json](results/results.json), log [results/run.log](results/run.log). Ledgers: `C:/Users/zhang/bci-data/derived/p15-13-gate-fix/` only.

Run: 2026-11-18 10:02-11:29 (5,271 s, CPU, background class, 4 threads, peak 1.35 GB), detached. Decoders as P15-03a: M4-12 fixed0 (start champion), M4-13 long0 `best.pt`, broken = M4-13 frames in reverse time order. 4 runs = seeds {0, 1} x users {oracle, feedback-r0.3}; 7 blocks each, plus the weak-champion probe W. The two feedback runs took 167 s and 195 s: the word decoder's in-process cache already held the outputs of the same inputs from the oracle run. The cache does not change any output.

## Contrast: the P15-03a result that this item fixes
P15-03a ([results](../2026-11-17-p15-03-f1-m4-13/results.md)), pre-registered **H3 = fail**. The P15-02 sign test refused the reversed decoder with the oracle user (15-16 worse vs 0 better, p <= 3.1e-5). With the feedback-r0.3 user it **accepted** the reversed decoder in both seeds (2 worse vs 0 better, p 0.25), and also the worse M4-12 (H2 fail). The broken decoder was live for two blocks.

## Verdict (pre-registered rules)

| rule | pass if | result |
|---|---|---|
| **G1** broken refused (B3), guard config unchanged | 4 / 4 runs | **pass** (4 / 4; 48 worse vs 0 better in every run; feedback runs: 30 and 34 of them unknown) |
| **G1w** broken refused against the weak champion M4-12 (probe W, new gate) | 4 / 4 runs | **pass** (4 / 4; 48 worse vs 0 better; guard copy unchanged) |
| **G2** worse M4-12 refused (B2, B5, B7 while M4-13 is live), at least one by the challenger test | every run where B1 was accepted (4) | **pass** (4 / 4; all 12 proposals refused by the challenger test, p 1.0) |
| **G3** better M4-13 accepted (B1) | >= 3 / 4 runs | **pass** (4 / 4; oracle p 2.9e-9 and 1.1e-10; feedback-r0.3 p 0.038 and 0.026) |
| **G4** phase-C wrong-commit rate <= 0.05 | 4 / 4 runs | **pass** (0.0082, 0.0082, 0.0110, 0.0082; 118 commits in total, not vacuous) |
| **G5** null controls of every accepted update | all accepted updates | **pass** (11 / 11; max 2 / 100 commits, allowed 5) |
| **G6** audit: every ledger verifies (main + W), every proposal decided, config changes on accept only | all runs | **pass** (4 / 4 main, 8 / 8 W) |

**Decision rule of the plan:** G1, G1w, G2, G4, G5 and G6 pass, and G3 passes. **Gap 1 (P15-13) closes.**

## Probe W: broken decoder against the weak champion (the dry-run case of P15-03a)

| run | truth known (of 48) | new gate: worse / better (unknown), p | new gate | sign test: worse / better, p | sign test |
|---|---|---|---|---|---|
| s0 oracle | 48 | 48 / 0 (0), 1.0 | refused | 7 / 0, 0.0078 | refused |
| s0 feedback-r0.3 | 14 | 48 / 0 (34), 1.0 | refused | 2 / 0, 0.25 | **accepted** |
| s1 oracle | 48 | 48 / 0 (0), 1.0 | refused | 7 / 0, 0.0078 | refused |
| s1 feedback-r0.3 | 15 | 48 / 0 (33), 1.0 | refused | 2 / 0, 0.25 | **accepted** |

The sign test repeats the P15-03a failure on the same items (2 vs 0, p 0.25). The new gate counts the 33-34 unknown items against the challenger. On the 14-15 known items the broken decoder is worse by CER on every item.

## Per-block decisions (new gate)

Oracle user. Seed 0 numbers; seed 1 in brackets where it differs. "w / b" = worse (unknown included) / better pairs of 48.

| block | proposal | decision | w / b, identical texts | p (passed by) | sign test on the same block (D3) | PER challenger vs champion, p_worse (D4) |
|---|---|---|---|---|---|---|
| B1 | M4-13 vs live M4-12 | accept | 5 / 34 [3 / 34], 7 [8] | 2.9e-9 [1.1e-10] (non-inferior) | 1 / 18 [0 / 18], would accept | 0.080 vs 0.204 (1.0) |
| B2 | M4-12 | reject | 37 / 3, 5 | 1.0 | 16 / 1 [16 / 2], would reject | 0.232 vs 0.105 (5.7e-9) |
| B3 | broken | reject | 48 / 0, 0 | 1.0 | 15 / 0 [16 / 0], would reject | 0.854 vs 0.117 (8.1e-10) |
| B4 | re-calibration of M4-13 | accept | 0 / 1 [0 / 0], 47 [48] | 0.013 (few worse items) [identical top-1] | 0 / 0 | - |
| B5 | M4-12 | reject | 42 / 1, 4 | 1.0 | 18 / 0, would reject | 0.237 vs 0.089 (3.2e-9) |
| B6 | re-calibration of M4-13 | accept [**reject**] | 0 / 2 [1 / 2], 46 [45] | 0.013 (few worse items) [0.081] | 0 / 1 | - |
| B7 | M4-12 | reject | 35 / 2 [34 / 2], 8 | 1.0 | 6 / 0, would reject | 0.316 vs 0.162 (3.0e-9) |

Feedback-r0.3 user (seed 0; seed 1 in brackets):

| block | proposal | decision | truth known | w / b (unknown) | p | sign test on the same block (D3) | PER on known items only, p_worse (D4) |
|---|---|---|---|---|---|---|---|
| B1 | M4-13 vs live M4-12 | accept | 34 [31] | 17 / 23 (13) [16 / 23 (15)] | 0.038 [0.026] | 1 / 18 [0 / 18], would accept | n.s. (challenger better) |
| B2 | M4-12 | reject | 10 [18] | 42 / 1 (36) [41 / 1 (29)] | 1.0 | 3 / 1, p 0.31 [5 / 1, p 0.11]: **would accept** | too few nonzero [2.1e-4] |
| B3 | broken | reject | 18 [14] | 48 / 0 (30) [48 / 0 (34)] | 1.0 | 8 / 0, p 0.0039 [6 / 0, p 0.016]: would reject | 3.8e-6 [4.9e-4] |
| B4 | re-calibration of M4-13 | accept | 37 [36] | 0 / 0 (0) | 0.013 [identical top-1] | 0 / 0 | - |
| B5 | M4-12 | reject | 10 [16] | 44 / 0 (36) [43 / 0 (29)] | 1.0 | 6 / 0, p 0.016 [4 / 0, p 0.063: **would accept**] | too few nonzero [1.5e-4] |
| B6 | re-calibration of M4-13 | accept | 20 [23] | 0 / 0 (0) [0 / 2 (0)] | 0.013 | 0 / 0 [0 / 1] | - |
| B7 | M4-12 | reject | 20 [20] | 38 / 1 (25) [39 / 0 (26)] | 1.0 | 3 / 0, p 0.125 [2 / 0, p 0.25]: **would accept** | 6.6e-5 [6.6e-5] |

In the feedback runs, M4-13 stays live from B1 to the end. In P15-03a, M4-12 and the broken decoder took over at B2 and B3.

Why B3 differs from P15-03a in the feedback runs: in P15-03a the live decoder at B3 was the (wrongly accepted) M4-12. Here it is M4-13, so the sign test on this block would also refuse (8 / 0, 6 / 0). Probe W gives the like-for-like comparison with a weak champion.

## Descriptive results

**D1 phase C** (365 items per run):

| run | commits | wrong | wrong-commit rate [CP95] | precision | blocks with commits | P15-03a (same run): commits, precision |
|---|---|---|---|---|---|---|
| s0 oracle | 28 | 3 | 0.0082 [0.0017, 0.0238] | 0.893 | 7 / 7 | 28, 0.893 |
| s0 feedback-r0.3 | 28 | 3 | 0.0082 [0.0017, 0.0238] | 0.893 | 7 / 7 | 11, 0.727 |
| s1 oracle | 33 | 4 | 0.0110 [0.0030, 0.0278] | 0.879 | 7 / 7 | 29, 0.897 |
| s1 feedback-r0.3 | 29 | 3 | 0.0082 [0.0017, 0.0238] | 0.897 | 7 / 7 | 10, 0.800 |

With partial feedback, the user now gets the same help as with full feedback: 28-29 commits instead of 10-11, and no block without commits.

**D2 cost of default deny (re-calibration of the same decoder):** 7 of 8 re-calibrations were accepted: 3 by "identical top-1", 4 by "few worse items". One was refused: s1 oracle B6. The top-1 changed on 3 of 48 items (1 worse, 2 better), and with `N = 48` and margin_abs 0.1 the gate needs `w = 0` (p_abs 0.040 > 0.025). The refusal changes nothing that the user sees: the guard keeps the B4 configuration (7 phase-C commits, 0 wrong). A refused re-calibration can still matter for a user whose decoder drifts; see gap 72 below.

**D3 old gate on the same blocks:** with the feedback-r0.3 user, the sign test would accept the worse M4-12 in 5 of 6 blocks (B2 x2, B5 seed 1, B7 x2) and the broken decoder against the weak champion in 2 of 2 (probe W). With the oracle user it refuses all of them.

**D4 per-item PER test:** on all 48 items it separates every decoder proposal (p_worse 3e-9 to 6e-9 for M4-12, 8e-10 for the broken decoder). A deployable PER needs the phoneme truth. On known items only it separates where at least 10 differences exist (p_worse 6.6e-5 to 4.9e-4), but it gives no result on the 10-item blocks. The gate uses the text (top-1 + CER), which a user can give.

> **Our take:** counting "no evidence" against the challenger fixes the defect without losing the better decoder. Under partial feedback the margin for the better decoder is real but small: B1 passed at p 0.038 and 0.026 against level 0.05, with 13-15 unknown items counted as worse. A weaker improvement, or a user who retypes less often than 30 %, can be refused. That is the intended direction of error ("never puts words in the user's mouth"), but it slows learning. More check items per block, or offering both decoders' top-1, would give the gate more evidence.

## Gap decisions
- **P15-13 (gap 1): closed.** Decision rule of the plan holds. Done-when: a continuous-loss (CER) non-inferiority test next to the sign test, with margins fixed in the plan; unit tests and this replay refuse the reversed decoder, also against the weak champion with few discordant pairs (probe W: 2 discordant pairs, refused). The H3 outcome of P15-03a is quoted above.
- **New gap 71 (P15-23):** a challenger proposed **without champion outputs** skips the champion / challenger test (`_challenger_test` returns None) and can be accepted on the null controls and block LTT alone. Under default deny this should refuse, or need an explicit opt-out.
- **New gap 72 (P15-24):** same-decoder re-calibrations are refused when the top-1 changes on a few items (D2: 1 of 8, s1 oracle B6, 1 worse vs 2 better). With `N = 48` the absolute branch allows no worse item. A drifting user could then not re-tune. Options: a larger check block, a re-calibration path that keeps the top-1 fixed, or a pre-registered margin for re-calibrations.

## Deviations
- None in the method. The plumbing dry run (plan section "Dry run") passed without a code change ([results/dryrun-m4-12](results/dryrun-m4-12/)).
