---
title: P15-03a (F1) champion / challenger replay on T15 with the M4-13 decoder - pre-registration
type: experiment
task: P15-03
updated: 2026-11-16
---

# P15-03a: does the update gate refuse a worse decoder on real data? (pre-registration)

Written and committed **before** the M4-13 decoder has finished and before any M4-13 output exists. Roadmap item [P15-03](../../wiki/questions/roadmap-standard.md#p15-03-e2-full-runs-on-t12-and-t15). This is the **CPU part** of P15-03 ("a"). The full P15-03 (decoder adaptation from user feedback on T12 and T15) needs GPU training of a GRU day layer and waits for the GPU after P11-01. Queue and GPU plan: [trust-reruns plan](../2026-11-17-trust-reruns-m4-13/plan.md).

## Why this run
- The P15-02 smoke test ([results](../2026-11-16-p15-02-hooks/results.md)) and the gated pilot re-run ([results](../2026-11-16-f1-e2-selfimprove-pilot/results-gated.md)) used a weak decoder. Both decoders were wrong on every check item, so the champion / challenger sign test never saw a discordant pair. The "worse challenger" path was tested only by unit tests.
- M4-13 (val_select PER 0.124 at step 69,000 on 2026-11-16, still training) is much stronger than M4-12 fixed0 (val_select PER 0.256). Two real decoders with different quality on the same trials give the gate a real test.

## Data (read only)
| decoder | calibration (val_select, 722) | held out (val_eval, 701) |
|---|---|---|
| M4-12 fixed0 (weaker) | `derived/m2-19-trust-retune/logprobs-m2-19-m4-12-fixed0.npz` | `derived/m4-01-02-lookahead/logprobs-m4-12-fixed0.npz` |
| M4-13 long0 best.pt (stronger) | CPU decode by the queue (`derived/trust-reruns-m4-13/`) | the M4-13 queue's GPU decode (`derived/m4-13/`); CPU fallback if missing |
| broken: M4-13 with the frames in reverse time order | same, reversed | same, reversed |

Texts, phonemes and item order: as P14-03 (session order, then index). Word route: the P14-03 `decode_fn` (B2T '25 phoneme beam + lexicon + n-gram LM, tuned). Note: best.pt is selected on val_select PER, so val_select is not fully independent of M4-13. It is used only for calibration (as in M2-19 and P14-03); all claims use val_eval.

## Design (fixed now)
- Live guard at start: `fidetype.trust.calibrate` on M4-12 val_select (alpha 0.05, delta 0.1, 300 null trials, seed s). Champion version `m4-12`.
- `GuardedUpdateLoop(alpha 0.05, delta 0.1, n_check 48, evidence gate default CommitGate(max_guard_risk 1.0), challenger_level 0.05)` with a `ProvenanceLedger`; `TrustGuardUpdater(null_trials 100)`.
- val_eval in order, cut into 7 contiguous blocks (`linspace(0, 701, 8)`). Block b: items 1-48 = check block of proposal b (offer-only); the rest = phase C (the live guard decides on the live decoder's log-probs).
- Every proposal: `TrustGuardUpdater.propose_calibration` (candidate calibrated on its decoder's val_select, 100 null trials, seed `s + 100 b`), checked on the 48 check items with the live decoder's outputs as champion.

| block | proposal | expected |
|---|---|---|
| B1 | M4-13 vs live M4-12 (better challenger) | accept |
| B2 | the decoder that is not live (M4-12 if M4-13 is live) | reject (worse) |
| B3 | broken: reversed M4-13 | reject |
| B4 | re-calibration of the live decoder (no champion inputs) | descriptive |
| B5 | the decoder that is not live (replication of B2) | reject (worse) |
| B6 | re-calibration of the live decoder | descriptive |
| B7 | the decoder that is not live (second replication) | reject (worse) |

- Simulated user on the check block ([`FeedbackUser`](../../src/fidetype/trust/adaptive.py)): the candidate's top-5 list is offered. `oracle`: truth always known (`p_retype` 1.0). `feedback-r0.3`: truth known if it is in the list (accept) or retyped (`p_retype` 0.3); unknown truth counts as a wrong top-1 (pessimistic, as P15-02). User seed `[s, 1503]`.
- Runs: seeds s in {0, 1} x users {oracle, feedback-r0.3} = 4 runs.

## Pass rules (fixed now)
| id | rule | pass if |
|---|---|---|
| **H1** better accepted | B1 accepted | in >= 3 of 4 runs |
| **H2** worse refused, real test | every proposal of M4-12 while M4-13 is live (B2, B5, B7) is rejected, and at least one of them is rejected by the sign test (reason "worse than champion") with >= 10 discordant pairs | in every run where B1 was accepted |
| **H3** broken refused | B3 rejected (any reason: calibration refused, null controls, sign test, infeasible block) and the guard config does not change | in all 4 runs |
| **H4** guarantee | phase-C wrong-commit rate over all blocks <= 0.05 (point estimate; CP95 reported) | in all 4 runs |
| **H5** null controls | every accepted update passed its uniform and shuffled controls (<= floor(0.05 n) commits) | all accepted updates |
| **H6** audit | ledger `verify` passes; every proposal has a decision; config changes on accept only | all runs |
| H7 (secondary) | per-item greedy phoneme error rate, challenger minus champion, on the check block of every decoder proposal (one-sided Wilcoxon, level 0.05): does the PER test agree with the gate decision? | descriptive (the plan of P15-01 asked for a loss with more signal than top-1 exact) |
| D1 | phase-C commits, precision (right / commits), share of blocks with commits; M4-13 live vs the start | descriptive |

If B1 is rejected in a run, H2 is "not testable" for that run (no worse challenger exists); we report it. A vacuous result (fewer than 10 phase-C commits over the 4 runs) is reported as vacuous for H4.

## Outputs
Per-trial records and ledgers: `C:/Users/zhang/bci-data/derived/p15-03-f1-m4-13/` only. Repo: `results/results.json` (aggregates), `results.md` after the run. Run: [run.py](run.py) (stage `p15-03` of the queue). CPU, background class, 4 threads; RAM peak in the dry run below.

## Dry run (plumbing only, before any M4-13 output)
`TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12` with 160 calibration and 360 held-out items; both "decoders" are M4-12, so accept / reject labels mean nothing. Outputs in `derived/.../dryrun/` and `results/dryrun-m4-12/`. Result: the code path works end to end (7 proposals, ledger verifies, 975 MB peak, 20 min). It also showed a gap: with a weak champion the broken decoder was accepted (2 discordant pairs, p 0.25) and the PER test saw a difference that the sign test missed. Details in the [trust-reruns plan](../2026-11-17-trust-reruns-m4-13/plan.md#dry-runs-plumbing-only-2026-11-16-m4-12-subsets-no-m4-13-data). The pass rules above are not changed by this.
