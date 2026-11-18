---
title: P15-13 default-deny update gate - replay of P15-03a on M4-13 with partial feedback - pre-registration
type: experiment
task: P15-13
updated: 2026-11-18
---

# P15-13: does the default-deny gate refuse worse and broken decoders under partial feedback? (pre-registration)

Written and committed **before** any run of the new gate on M4-13 data. Roadmap item [P15-13](../../wiki/questions/roadmap-standard.md#p15-13-update-gate-per-based-non-inferiority-challenger-test) (open gap 1).

## Why
The pre-registered P15-03a replay ([results](../2026-11-17-p15-03-f1-m4-13/results.md)) read **H3 = fail**: with the feedback-r0.3 user, the gate accepted the time-reversed (broken) M4-13 decoder in both seeds (2 worse vs 0 better, p 0.25), and the worse M4-12 (H2 fail). Cause: unknown truth counted as wrong for **both** sides, so most pairs were "both wrong" and the sign test had no power. With the oracle user the same gate refused both. The fix must work with partial feedback.

## The change (code, before this plan)
`GuardedUpdateLoop(challenger_test="noninferiority")` is the new default ([adaptive.py](../../src/fidetype/trust/adaptive.py), module docstring "Champion / challenger test"). The P15-02 sign test stays available as `challenger_test="sign"`.

- **Default deny.** The challenger must show that it is not materially worse. Absence of evidence counts against it.
- Per check item, a pair (challenger, champion). Primary loss: top-1 right or wrong. Tie-break: CER of the two top-1 texts when the truth is known (a continuous loss that a user can give: the text, not the phonemes).
- Unknown truth: identical top-1 texts are a tie; a right challenger is never worse; a champion known to be wrong (its top-1 is in the list that the user rejected) gives a tie; every other pair with an unknown side counts as **worse**.
- With `w` worse (unknown included), `b` better, `n = w + b`, `N` items: pass if `p = min(1, 2 min(p_ni, p_abs)) <= 0.05`, with `p_ni = P(Bin(n, 0.6) <= w)` and `p_abs = P(Bin(N, 0.1) <= w)`. All `N` top-1 texts identical: pass.
- **Margins fixed now:** level 0.05, `challenger_margin` 0.1 (worse share among differing pairs < 0.6), `challenger_margin_abs` 0.1 (worse share of all items < 0.1).
- Guarantee: if the true worse share among differing pairs is >= 0.6 and the true worse share of all items is >= 0.1, the gate accepts with probability <= 0.05 (exact binomial, Bonferroni). Unknown items only add to `w`.
- `TrustGuardUpdater.propose(..., check_texts)` accepts `None` (truth unknown) and `check_rejected` (the offered list that the user rejected).

## Data (read only)
As P15-03a: M4-12 fixed0 and M4-13 long0 `best.pt` log-probs (`C:/Users/zhang/bci-data/derived/{m2-19-trust-retune, m4-01-02-lookahead, trust-reruns-m4-13, m4-13}`), texts and phonemes from `m4-01-02-lookahead`. Broken = M4-13 frames in reverse time order. Word route: the P14-03 `decode_fn`. Outputs (ledgers): `C:/Users/zhang/bci-data/derived/p15-13-gate-fix/` only. Repo: `results/results.json`, `results/run.log`, then `results.md`.

## Design (fixed now)
- Same as P15-03a ([plan](../2026-11-17-p15-03-f1-m4-13/plan.md)): live guard `calibrate` on M4-12 val_select (alpha 0.05, delta 0.1, 300 null trials, seed s); `GuardedUpdateLoop(alpha 0.05, delta 0.1, n_check 48)` with a ledger; `TrustGuardUpdater(null_trials 100)`; val_eval in order, 7 blocks; first 48 items of a block = offer-only check block, the rest = phase C; same proposal schedule B1-B7 (B1 M4-13; B2, B5, B7 the decoder that is not live; B3 broken; B4, B6 re-calibration of the live decoder); same seeds of calibration and user (`[s, 1503]`).
- Users: `oracle` (`p_retype` 1.0) and `feedback-r0.3` (`p_retype` 0.3). The user sees the candidate's top-5. Truth known if accepted or retyped; else unknown, and the offered list is passed as rejected.
- **New gate** (defaults above) in every run.
- **Weak-champion probe W** (per run, before B1; it does not change the main run): the broken decoder (calibrated on reversed M4-13 val_select, seed s + 1000, 100 null trials) proposed against a copy of the start guard (M4-12 live) on the B3 check items, user seed `[s, 1513]`. Run twice on separate loops: new gate and sign test.
- Runs: seeds {0, 1} x users {oracle, feedback-r0.3} = 4 runs. [run.py](run.py), detached by [launch.py](launch.py); CPU, background class, 4 threads.

## Pass rules (fixed now)
| id | rule | pass if |
|---|---|---|
| **G1** broken refused | B3 rejected (any reason) and the guard config does not change | 4 / 4 runs |
| **G1w** broken refused, weak champion | probe W with the new gate rejected, guard copy unchanged | 4 / 4 runs |
| **G2** worse refused | every M4-12 proposal while M4-13 is live (B2, B5, B7) is rejected, and at least one of them by the challenger test | every run where B1 was accepted |
| **G3** better accepted | B1 accepted | >= 3 / 4 runs; if not, we report the cost (runs, counts, p) and do not change the gate |
| **G4** guarantee | phase-C wrong-commit rate over all blocks <= 0.05 (point estimate; CP95 reported) | 4 / 4 runs (vacuous if < 10 commits in total) |
| **G5** null controls | every accepted update passed its uniform and shuffled controls (<= floor(0.05 n)) | all accepted updates |
| **G6** audit | every ledger (main and W) verifies; every proposal has a decision; the config changes on accept only | all runs |
| D1 | phase-C commits, precision, blocks with commits; compared with P15-03a | descriptive |
| D2 | B4 / B6 (re-calibration of the same decoder): accepted or not, and why (cost of default deny) | descriptive |
| D3 | the P15-02 sign test on the same blocks (`legacy_*` fields; W sign loop): what the old gate would decide | descriptive |
| D4 | per-item greedy PER test (one-sided Wilcoxon), on all 48 items and on known-truth items only, for every decoder and broken proposal | descriptive |

If B1 is rejected in a run, G2 is "not testable" in that run (M4-13 never live); we report it. The P15-03a H3 result (fail with feedback-r0.3; refused with the oracle) is quoted in the results.

**P15-13 decision rule:** close gap 1 if G1, G1w, G2, G4, G5 and G6 pass, and G3 passes or its cost is reported and accepted as the price of default deny. Else gap 1 stays open with the reason.

## Dry run (plumbing only, after this commit)
`TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12` with 160 calibration and 360 held-out items, one seed, the feedback-r0.3 user, blocks B1-B3 only. Both "decoders" are M4-12, so the labels mean nothing; outputs in `derived/p15-13-gate-fix/dryrun/` and `results/dryrun-m4-12/`. It checks only that the code runs end to end; a fix found there changes no rule above and is listed as a deviation.
