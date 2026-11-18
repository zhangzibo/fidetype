---
title: P15-24 same-decoder re-calibration rule - replay of P15-13 on M4-13 - pre-registration
type: experiment
task: P15-24
updated: 2026-11-18
---

# P15-24: does the re-calibration rule let the same decoder re-tune, and does the gate still refuse worse and broken decoders? (pre-registration)

Written and committed **before** any run of the new rule on M4-13 data. Roadmap item [P15-24](../../wiki/questions/roadmap-standard.md#p15-24-same-decoder-re-calibrations-under-the-default-deny-gate) (open gap 72). The code change is in the same commit as this plan.

## Why
In the pre-registered P15-13 replay ([results](../2026-11-18-p15-13-gate-fix/results.md), D2), the default-deny gate refused 1 of 8 re-calibrations of the same M4-13 decoder (s1 oracle B6). A re-calibration fits a new guard (frame temperature, thresholds) on new items. The new temperature changed the top-1 word text on 3 of 48 check items: 1 worse, 2 better (p 0.081). The first branch of the test (worse share among differing items) has only 3 items. The Bonferroni split leaves the absolute branch at level / 2 = 0.025, and with `N = 48`, `P(Bin(48, 0.1) <= 1) = 0.040`. So no worse item is allowed. A user whose data drift may then not be able to re-tune.

## The change (code, before this plan)
`src/fidetype/trust/adaptive.py`, `update_hooks.py`, `personal.py` (module docstrings "Same-decoder re-calibration rule").

- `GuardedUpdateLoop.new_version(..., kind="decoder" | "recalibration")`. The kind goes into the ledger proposal (`details.kind`).
- **Re-calibration rule** (`recalibration_rule="absolute"`, default): a `kind="recalibration"` proposal passes if its top-1 texts are identical to the champion's on all items, or if `p_abs = P(Bin(N, margin_abs) <= w) <= level` (the absolute branch alone, at the full level; `w` counts unknown pairs as worse, as before). With `N = 48`, margin_abs 0.1, level 0.05: `w <= 1`.
- **Guarantee:** if the true worse share of all items is >= margin_abs, the rule accepts with probability <= level. This null hypothesis contains the null hypothesis of the decoder rule (worse share among differing items >= 0.6 **and** worse share >= 0.1). So the documented gate guarantee holds for every proposal, also for a decoder change that is wrongly declared a re-calibration. Such a proposal only loses power.
- **Decoder rule unchanged** (P15-13: two branches, Bonferroni) for `kind="decoder"`. `recalibration_rule="decoder"` gives the P15-13 behaviour for re-calibrations.
- `TrustGuardUpdater.propose` sets `kind="recalibration"` only if `champion_inputs` is None (both guards read the same decoder outputs) **and** `same_decoder(candidate, live)` holds (same `decode_fn` object, same codec: input kind, vocabulary, decoder name / version / modality). Else `kind="decoder"`. In this replay B4 and B6 meet both conditions; B1, B2, B3, B5, B7 and probe W give `champion_inputs` and are decoder changes.
- The block LTT checks the new thresholds on the check block, as for every version (unchanged).
- Also in this commit (P15-23, gap 71): a challenger without champion outputs is refused by default. It does not apply in this replay: every proposal gives the champion outputs.

## Data (read only)
As P15-13 ([plan](../2026-11-18-p15-13-gate-fix/plan.md)): M4-12 fixed0 and M4-13 long0 `best.pt` log-probs (`C:/Users/zhang/bci-data/derived/{m2-19-trust-retune, m4-01-02-lookahead, trust-reruns-m4-13, m4-13}`), texts and phonemes from `m4-01-02-lookahead`. The P15-13 outputs (`derived/p15-13-gate-fix/`) are read only and not used by the run. Outputs (ledgers): `C:/Users/zhang/bci-data/derived/p15-24/` only. Repo: `results/results.json`, `results/run.log`, then `results.md`.

## Design (fixed now)
**The P15-13 design without change** ([run.py](run.py) is a copy of the P15-13 run.py; the only code changes are the output folders, `recalibration_rule="absolute"` on the loop and two report fields per row: `kind` and `recal_rule_on_counts`). Same seeds {0, 1}, users {oracle, feedback-r0.3}, 7 blocks of T15 val_eval in order, 48 offer-only check items per block, schedule B1-B7 (B1 M4-13; B2, B5, B7 the decoder that is not live; B3 broken = time-reversed M4-13; B4, B6 re-calibration of the live decoder), probe W (broken vs the weak champion M4-12, new gate and sign test), `GuardedUpdateLoop(alpha 0.05, delta 0.1, n_check 48)`, level 0.05, margins 0.1 / 0.1, `TrustGuardUpdater(null_trials 100)`. Guard names and ledger chain names keep their P15-13 strings, so that the decoder-change decisions can be compared item for item. CPU, background class, 4 threads, detached ([launch.py](launch.py)).

Expected (not a rule): with the same seeds, W and B1-B5 repeat P15-13 exactly, because the decoder rule and the inputs do not change. B6 of s1 oracle is the case that the new rule changes; if it is accepted, B7 and phase C of that run use another live guard and can differ from P15-13.

## Pass rules (fixed now)
| id | rule | pass if |
|---|---|---|
| **R1** broken refused (= P15-13 G1) | B3 rejected and the guard config does not change | 4 / 4 runs |
| **R2** broken refused, weak champion (= G1w) | probe W with the new gate rejected, guard copy unchanged | 4 / 4 runs |
| **R3** worse refused (= G2) | every M4-12 proposal while M4-13 is live (B2, B5, B7) rejected, at least one by the challenger test | every run where B1 was accepted (12 / 12 proposals if B1 is accepted in all 4) |
| **R4** re-calibrations | refused same-decoder re-calibrations (B4, B6; 8 in total) <= 1 (the P15-13 count); and all 8 registered as `kind="recalibration"` (the rule under test was used) | both parts |
| **R5** guarantee (= G4) | phase-C wrong-commit rate over all blocks <= 0.05 (point estimate; CP95 reported) | 4 / 4 runs (vacuous if < 10 commits) |
| **R6** audit (= G6, with G5) | every ledger (main + W) verifies; every proposal has a decision; the config changes on accept only; every accepted update passed its uniform and shuffled null controls | all runs |
| **R7** mislabel check | the re-calibration rule applied to the counts of every decoder and broken proposal that the gate refused (B2, B3, B5, B7, W; `recal_rule_on_counts`) also refuses it | all such proposals |
| D1 | B1 accepted (runs, p); phase-C commits and precision; compared with P15-13 | descriptive |
| D2 | per re-calibration: worse / better / unknown, p_abs, the P15-13 decoder-rule p on the same block, decision | descriptive |
| D3 | decisions that differ from P15-13 (block, run, why) | descriptive |

**P15-24 decision rule:** close gap 72 if R1-R7 pass. If R4 fails (more than 1 refusal), gap 72 stays open with the counts; the rule is still kept if R1-R3 and R5-R7 pass, because it is never less safe than the decoder rule (guarantee above). If R1, R2, R3, R5, R6 or R7 fails, the rule is withdrawn (default back to `"decoder"`) and gap 72 stays open.

## Dry run (plumbing only, after this commit)
`TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12 TRUST_RERUN_NCAL=160 TRUST_RERUN_NHELD=360 run.py --seeds 0 --users feedback-r0.3 --max-blocks 4` (both "decoders" are M4-12, labels mean nothing; B4 is a re-calibration, so the new path runs). Outputs in `derived/p15-24/dryrun/` and `results/dryrun-m4-12/`. It checks only that the code runs end to end; a fix found there changes no rule above and is listed as a deviation.
