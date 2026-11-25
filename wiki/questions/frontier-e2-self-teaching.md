---
title: "Frontier write-up E2 (F1): a decoder that learns from feedback behind an update gate"
type: question
tags: [frontier, f1, e2, self-improving, update-gate, champion-challenger, online-risk, write-up, negative-result, pre-registration]
sources: [card-2026-home-use, corp, wilson-hmm-recalibration, roy-input-affine-recalibration, ocp-corrupted-feedback, hou-error-encoding]
updated: 2026-11-24
---

# E2 (F1): can a decoder learn from user feedback while the commit bound stays valid?

Write-up for roadmap item [P15-12](roadmap-standard.md#p15-12-frontier-result-write-ups). It joins six pre-registered steps into one story: P15-01, P15-02, P15-03a, P15-13, P15-23 and P15-24. Pillar F1 of the [north star](north-star.md#f1-safe-self-improving-bci-e2). Negative results are kept.

## Question
A simulated user accepts, rejects or retypes the decoder output. The decoder learns from this feedback between sessions. Does the decoder get better? Does the long-run wrong-commit bound stay valid through every update? Does the update gate keep a better decoder and refuse a worse or broken one?

## Short answer
- **Learning from feedback works in a replay.** On 16 T12 days, feedback-only adaptation lowers PER from 0.686 (frozen) to 0.470 (P15-01, S4 pass).
- **The bound stays valid through every update.** This is true in every guarded run of P15-01, P15-02, P15-03a and P15-13, also under bad updates.
- **Three defects were found and fixed, one at a time.** (1) Null input committed (P15-01 S5 fail; fixed by P15-02). (2) The gate accepted a worse and a broken decoder under partial feedback (P15-03a H2, H3 fail; fixed by P15-13, G1-G6 pass). (3) A challenger without champion outputs skipped the test (fixed by P15-23).
- **The cost of the fix is removed (P15-24).** The default-deny gate refused 1 of 8 same-decoder re-calibrations (P15-13). A separate rule for re-calibrations of the same decoder fixed this in a pre-registered replay: R1-R7 pass, 0 of 8 refused, and every broken or worse decoder is still refused ([results](../../experiments/2026-11-18-p15-24-recal-rule/results.md)).
- **The full GPU runs of E2 (P15-03 on T12 and T15 with day-layer adaptation) have not run.**

## The steps at a glance

| step | question | pre-registration | design | verdict | result page |
|---|---|---|---|---|---|
| P15-01 pilot | does the loop work end to end? | [plan](../../experiments/2026-11-16-f1-e2-selfimprove-pilot/plan.md), `b0090d3` | T12, 16 replay days (S8-S23, 6,720 items), own small CPU decoder, 8 arms | S1-S4, S6 pass; **S5 fail** (null input commits in all 8 arms) | [results](../../experiments/2026-11-16-f1-e2-selfimprove-pilot/results.md) |
| P15-02 gated re-run | do an evidence gate and per-update null refusal fix S5? | same plan (second run, changed loop, reported next to the first) | 2 arms of P15-01 with the new loop | S1-S5 pass; sign test has no power | [results-gated](../../experiments/2026-11-16-f1-e2-selfimprove-pilot/results-gated.md), [hooks](../../experiments/2026-11-16-p15-02-hooks/results.md) |
| P15-03a | does the gate refuse worse decoders on real data? | [plan](../../experiments/2026-11-17-p15-03-f1-m4-13/plan.md), `97a2fc4` (before any M4-13 output) | T15, M4-12 / M4-13 / time-reversed M4-13, 2 seeds x 2 users (oracle, feedback-r0.3), 7 blocks | H1, H4, H5, H6 pass; **H2, H3 fail** | [results](../../experiments/2026-11-17-p15-03-f1-m4-13/results.md) |
| P15-13 | does a default-deny non-inferiority gate fix H2 / H3? | [plan](../../experiments/2026-11-18-p15-13-gate-fix/plan.md), `e788029` (with the code) | P15-03a design + probe W (broken vs the weak champion) | **G1-G6 all pass** | [results](../../experiments/2026-11-18-p15-13-gate-fix/results.md) |
| P15-23 | refuse a challenger without champion outputs | code only, `0254ebc` | unit tests | done (no replay needed) | [roadmap](roadmap-standard.md#p15-23-update-gate-refuses-a-challenger-without-champion-outputs) |
| P15-24 | can the same decoder re-tune under default deny? | [plan](../../experiments/2026-11-18-p15-24-recal-rule/plan.md), `0254ebc` (with the code) | P15-13 design, new re-calibration rule | **R1-R7 pass**: re-calibrations refused 0 / 8 (P15-13: 1 / 8); broken refused 4 / 4 (+ 4 / 4 vs weak champion), worse refused 12 / 12; wrong-commit 0.0082 | [results](../../experiments/2026-11-18-p15-24-recal-rule/results.md) |

## P15-01: CPU pilot on T12

**Design.** Replay in time order. A frozen trunk with a linear day-input layer, trained on S0-S6 (val PER 0.445; the T12 v2 decoder gives 0.269). Thresholds tuned on S7 before the replay (commit `43c9c93`). Arms: frozen, feedback with `p_notice` 0.5 / 0.9 / 1.0, oracle, self-training, shuffled labels, naive fixed threshold. Simulated user: accept if the truth is in the top-5 offer, retype with `p_retype` 0.8.

| id | criterion | result |
|---|---|---|
| S1 | true wrong-commit rate <= 0.05, every guarded arm | **pass** (7 / 7; 0.0048-0.0115) |
| S2 | share of days with phase-C risk > 0.05 <= 0.10 | **pass** (worst 1 / 16 days) |
| S3 | observed phase-C mean loss <= ACI certificate | **pass** (7 / 7) |
| S4 | feedback-p0.9 minus frozen PER <= -0.03, CI95 below 0 | **pass**: -0.2153 [-0.2492, -0.1767] |
| S5 | null-input commits <= 5 % in every arm | **FAIL** in all 8 arms (281-325 of 640) |
| S6 | shuffled labels minus frozen PER > -0.01 and S1 holds | **pass**: +0.1870; S1 0.0048 |

**Negative results, stated plainly.**
- **S5 fails.** Uniform null streams commit on almost every day (276-317 of 320 per arm). The loop used only a non-empty-text gate.
- **Self-training collapses.** PER rises from 0.485 (day 1) to about 0.97 from day 6. All 5,902 self-labels are wrong.
- **The bound is close to vacuous.** 88-100 % of commits are wrong. The frozen arm made 65 commits; all 65 were wrong. S1 passes only because commits are rare.
- **"Feedback" was mostly retyping.** About 5,390 labels per arm came from retypes at `p_retype` 0.8, because the truth was in the top-5 offer on only about 1.1 % of items.

## P15-02: evidence gate, null refusal, champion / challenger

**Library change (commit `8f2d2c7`, hooks `4355946`).** `GuardedUpdateLoop` became safe by construction:
- the M2-18 evidence gate is the default (`DEFAULT_EVIDENCE_GATE`); the loop refuses to start without one unless `unsafe=True`;
- uniform and frame-shuffled null controls run on every update; a failed control rejects the update;
- a champion / challenger sign test on a check block; each accepted update gets a new `config_id`, chained to its parent;
- `TrustGuardUpdater`, `OnlinePolicyUpdater` and ledger entries of kind `update` (proposed / accepted / rejected, hash-linked).

| id | frozen, original | frozen, gated | feedback-p0.9, original | feedback-p0.9, gated |
|---|---|---|---|---|
| S1 | pass, 0.0097 | pass, 0.0071 | pass, 0.0104 | pass, 0.0074 |
| S4 | - | - | pass, -0.2153 | pass, -0.2158 [-0.2502, -0.1767] |
| S5 | **FAIL**, 281 / 640 | **pass**, 2 / 640 | **FAIL**, 319 / 640 | **pass**, 0 / 640 |

**Still negative.** The frozen gated arm made 48 commits, all wrong. The sign test on top-1 exact loss saw 0-1 discordant pairs per day, so it could never refuse. All 16 + 16 updates were accepted. "Accepted" meant only "not shown to be worse".

## P15-03a: the gate on real decoders of different quality (T15)

**Design.** Start champion M4-12 (greedy PER 0.2574). Proposals: M4-13 (PER 0.1210), M4-12 again, and a broken decoder (M4-13 with frames in reverse time order). Users: oracle (all truth known) and feedback-r0.3 (truth known only if in the top-5 offer or retyped with p 0.3). Unknown truth counted as wrong for both sides.

| rule | pass if | result |
|---|---|---|
| H1 better M4-13 accepted | >= 3 / 4 runs | **pass** (4 / 4) |
| H2 worse M4-12 refused while M4-13 is live | every run with B1 accepted | **FAIL** (2 / 4: fails with feedback-r0.3) |
| H3 broken decoder refused | 4 / 4 runs | **FAIL** (2 / 4: accepted with feedback-r0.3, 2 worse vs 0 better, p 0.25) |
| H4 phase-C wrong-commit <= 0.05 | 4 / 4 | **pass** (0.0082, 0.0082, 0.0082, 0.0055; 78 commits) |
| H5 null controls of every accepted update | all | **pass** (20 / 20) |
| H6 audit (ledger, decisions, config change on accept only) | 4 / 4 | **pass** |

**Negative result.** With partial feedback the broken decoder became live for two blocks in both seeds. The guard then committed nothing, so the bound held, but the user got no help. A stronger champion did not fix the defect. The cause: with most truth unknown, both sides are "wrong" on most items, and the sign test sees only 1-6 discordant pairs.

## P15-13: the default-deny non-inferiority gate

**Library change (commit `e788029`).** `GuardedUpdateLoop(challenger_test="noninferiority")` is the new default. Unknown truth counts **against the challenger**. Top-1 comparison with a CER tie-break. Margins 0.1 / 0.1, level 0.05. The P15-02 sign test stays as an option (`challenger_test="sign"`). The same commit made the trust `config_id` independent of the decode-function label (P5-21).

| rule | pass if | result |
|---|---|---|
| G1 broken refused (B3) | 4 / 4 | **pass** (48 worse vs 0 better in every run) |
| G1w broken refused against the weak champion M4-12 (probe W) | 4 / 4 | **pass** (old sign test on the same items: accepted 2 / 2 with feedback-r0.3) |
| G2 worse M4-12 refused | every run with B1 accepted | **pass** (12 / 12 proposals) |
| G3 better M4-13 accepted | >= 3 / 4 | **pass** (4 / 4; feedback-r0.3 p 0.038 and 0.026) |
| G4 phase-C wrong-commit <= 0.05 | 4 / 4 | **pass** (0.0082, 0.0082, 0.0110, 0.0082; 118 commits) |
| G5 null controls | all accepted updates | **pass** (11 / 11) |
| G6 audit | all runs | **pass** |

With partial feedback the user now gets 28-29 phase-C commits per run (P15-03a: 10-11), with precision 0.893-0.897.

**Cost, stated plainly.** 1 of 8 same-decoder re-calibrations was refused (s1 oracle B6: top-1 changed on 3 of 48 items, 1 worse, 2 better). With `N = 48` the absolute branch allows no worse item. This is gap 72 (P15-24).

> **Our take:** counting "no evidence" against the challenger fixes the defect. But the margin for the better decoder is small under partial feedback (p 0.038 and 0.026 against level 0.05). A smaller improvement, or a user who retypes less than 30 % of the time, can be refused. This error direction is the one we want, but it slows learning.

## P15-23 and P15-24 (2026-11-18)
- **P15-23 (done, code `0254ebc`).** Under the default non-inferiority test, `GuardedUpdateLoop.finish_update` refuses a challenger whose champion outputs are missing. The opt-out `allow_missing_champion=True` is recorded in the update record and the config id. Closes gap 71.
- **P15-24 (done).** New rule in the same commit: `new_version(kind="recalibration")` with `recalibration_rule="absolute"` (default). A re-calibration passes if its top-1 texts are identical to the champion's, or if `P(Bin(N, 0.1) <= w) <= 0.05` (with `N = 48`: at most 1 worse item). The plan states why the gate guarantee still holds for every proposal. Pass rules R1-R7 are fixed in the [plan](../../experiments/2026-11-18-p15-24-recal-rule/plan.md). **Verdict ([results](../../experiments/2026-11-18-p15-24-recal-rule/results.md)): R1-R7 pass.** Re-calibrations refused 0 of 8 (P15-13: 1 of 8; the refused case, s1 oracle B6 with 1 worse vs 2 better, now passes at p_abs 0.040). Broken decoder refused 4 / 4 and 4 / 4 against the weak champion; worse M4-12 refused 12 / 12, all by the challenger test. Judged by the re-calibration rule, all 20 refused decoder and broken proposals are still refused (at least 34 worse of 48). Phase-C wrong-commit 0.0082 in every run (CP95 upper 0.0238); ledgers verify. W and B1-B5 repeat P15-13 exactly. Closes gap 72.

> **Our take:** the re-calibration rule removes the only cost of default deny that we measured, without a safety cost. It still allows only 1 worse item in 48 check items; a user whose drift changes the top-1 on more items needs a larger check block.

## What changed in the library because of E2

| finding | change | commit |
|---|---|---|
| null input commits (P15-01 S5) | evidence gate default; per-update null refusal | `8f2d2c7` |
| no audit of updates | update hooks, ledger kind `update`, chained `config_id` | `4355946` |
| gate accepts worse / broken decoders with partial feedback (P15-03a H2, H3) | default-deny non-inferiority test | `e788029` |
| `config_id` depends on the script label (V4 T12) | `decoder_id` / `custom:<qualname>` label | `e788029` |
| challenger without champion outputs skips the test | refuse by default; recorded opt-out | `0254ebc` |
| same decoder cannot re-tune (P15-13 D2) | re-calibration rule (R1-R7 pass, [results](../../experiments/2026-11-18-p15-24-recal-rule/results.md)) | `0254ebc` |

## Limits
- P15-01 / P15-02 used a weak CPU decoder (almost every commit wrong). Their positive results are a working harness, not F1 evidence.
- P15-03a and P15-13 swap whole decoders. They do not adapt a decoder from feedback. The learning part on a strong decoder waits for the GPU runs of P15-03.
- Simulated users only. One participant per dataset. Two seeds.
- Silent errors (wrong commits that the user does not correct) are outside every bound. They are reported separately.
- The bound is long-run over all items, not per session ([F1 guarantee scope](f1-guarantee-scope.md)).

## Still open
| gap | item | what |
|---|---|---|
| - | [P15-03](roadmap-standard.md#p15-03-e2-full-runs-on-t12-and-t15) | full GPU runs on T12 and T15 (day-layer adaptation, all arms, realistic retype rate) |
| 13 | [P15-18](roadmap-standard.md#p15-18-pilots-store-per-item-null-control-outputs) | pilots store per-item null-control outputs |
| 14 | [P15-19](roadmap-standard.md#p15-19-show-usefulness-on-stronger-decoders-p5-01-p15-02-p5-02-p15-06) | usefulness on stronger decoders |

## Closest prior work (literature check 2026-11-24)
| work | what it does | difference to E2 |
|---|---|---|
| [Card et al. 2026](../sources/card-2026-home-use.md) | real T15 home use: continuous fine-tuning, random 1/3 hold-out, checkpoint kept "only if validation performance improved", per-sentence 4-level ratings | point-estimate gate; no test, no stated bound, no null controls. A **Card-rule arm** is the baseline that shows what our statistical gate adds |
| [CORP](../sources/corp.md) | LM-corrected pseudo-labels, update after every sentence, 403 days (T5) | our ST arm (own top-1, no LM correction) is weaker: call it "naive self-training", not CORP |
| [Wilson et al. 2025](../sources/wilson-hmm-recalibration.md) | HMM-inferred cursor targets as labels; distribution matching drifts | supports FB / OR labels over ST |
| [Roy et al. 2026](../sources/roy-input-affine-recalibration.md) | input affine only (65,792 parameters) from 40 / 80 labelled trials, T12 and T15 | same family as our update 1 (day layer) |
| [OCP with corrupted feedback](../sources/ocp-corrupted-feedback.md) | theory: flipped feedback adds a term linear in the flip rate | our silent errors are one-sided flips: when ACI binds, the true rate tends to α / p_notice |
| [Hou et al. 2025](../sources/hou-error-encoding.md) | neural error signals detect BCI errors (up to 86 %) | a later, implicit feedback source |

Novelty wording: never "first gated decoder update" or "first BCI that learns from use". Use "a statistically tested update gate plus a stated long-run wrong-commit bound with null controls" ([novelty check](novelty-check-2026-11.md#update-2026-11-24-literature-check)). The T15 run records its pre-run response to this check in [amendment 2](../../experiments/2026-11-23-e2-self-teaching-t15/amendment-2.md).

## Rerun
Each experiment folder has its script (`replay.py`, `replay_gated.py`, `run.py`) and its plan lists the inputs. Run them through the isolation wrapper, for example `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-18-p15-13-gate-fix/run.py`. They need the T12 / T15 data (CC0) and the decoder outputs on the local disk. Per-trial outputs stay outside the repo.

## Related pages
[North star](north-star.md), [M4-13 trust reruns](m4-13-trust-reruns.md), [F1 online guarantees write-up](frontier-f1-online-guarantees.md), [F1 guarantee scope](f1-guarantee-scope.md), [open gaps](open-gaps.md), [roadmap P15](roadmap-standard.md#p15-frontier-added-2026-11-15-leads).
