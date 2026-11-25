---
title: E2 self-teaching on T15 - pre-run plan amendment 2 (literature check 2026-11-24)
type: experiment-plan-amendment
task: P15-49 (gap 209)
amends: plan.md (pre-registration 29c1dc9) and amendment-1.md (44e64da); neither file is changed
updated: 2026-11-24
---

# Amendment 2 to the E2 T15 pre-registration (before any GPU run)

**Date:** 2026-11-24. **Status:** written and committed **before any GPU run of P15-49** and before any data of the replay sessions S9-S44 was read. This file is committed before the code that implements it. The only runs so far are CPU tests and CPU dry runs on S0-S7 (3 training steps) and S8 items, in scratch folders that were deleted. No result exists.

**Why.** A literature check on 2026-11-24 (F1 / F2) found two predictable problems in the plan (the P2b rule and the gate's bias) and one missing baseline (Card et al. 2026). The user approved five changes on 2026-11-24. We checked the reasoning of the check ourselves; where our reading differs, this file says so.

**Scope.** The 20 plan runs keep every arm, user, seed, window, threshold, rule and stop rule of plan.md and amendment 1. Every live decision of the plan runs (commit / offer, accept / refuse, labels, fits) stays the same. This amendment adds (a) a secondary controller that runs as a shadow, (b) reports, (c) two secondary arms with 2 runs each, (d) a second reading of P2b and of the outcome table. Where this file and plan.md disagree, the run follows this file, and the results page reports both readings.

## 1. P2b: the silent-error gap is predicted to make the plan reading fail

### 1a. The prediction (stated now)
- The live ACI controller gets the **observed** loss: a wrong commit counts only if the simulated user notices it (probability `p_notice`; `FeedbackUser.respond_commit`). So E[observed loss] = `p_notice` x E[true loss] for every commit.
- When ACI binds (`lambda_aci > lambda_session`), ACI holds the long-run observed rate near alpha (bound G1). The true rate then tends to **alpha / p_notice**: 0.05 / 0.9 = **0.0556** for U1 and 0.05 / 0.5 = **0.10** for U2. Both are above the P2b limit 0.05.
- P2b divides by all phase-C items, also the items of offer-only sessions. ACI divides only by the commit-mode items. So the plan reading of P2b fails in a U1 run if ACI binds on most commit-mode items and the commit-mode share of phase C is above 0.9. It passes if `lambda_session` (the block LTT) binds on most items.
- **Evidence.**
  - Our P15-04 replay (T15, 701 items, ACI with exploration 0.05, q_notice 0.9): true rate **0.0556**, observed **0.0456** ([P15-04 results](../2026-11-16-p15-04-bandit/results.md), table row "A `aci`, q 0.9"; also in [guarantee scope](../../wiki/questions/f1-guarantee-scope.md), replay table). We checked both numbers in the repo.
  - Synthetic CPU check (test `test_aci_on_observed_loss_overshoots_by_one_over_p_notice_and_the_secondary_target_holds`, 30,000 items where ACI binds): observed 0.050, true **0.0548** (U1); true **0.0957** (U2).
  - Theory: Wang, Zecchin and Simeone 2026, "Online Conformal Prediction with Corrupted Feedback" (arXiv 2605.20515), Theorem 1: with label flips the miscoverage bound has an extra term that does not vanish as T grows. Their flip model is symmetric. Ours is one-sided (a missed wrong commit looks right), which gives the simple form above. We take the theorem statement from the literature check; we did not re-read the paper.

### 1b. New per-run report: which threshold binds
Per phase-C item in commit mode, the runner records `lambda_session`, `lambda_aci` (at decision time) and whether ACI binds (`lambda_aci > lambda_session`). Per session and per run: commit-mode items, items where ACI binds, the share, and the commits where ACI binds. Also the **noticing-adjusted bound** G1 certificate / `p_notice` (descriptive; `p_notice` is known only to the simulator).

### 1c. New secondary controller (shadow)
- A second ACI controller (`OnlineCommitRiskControl`, method "aci", the same eta 0.05 and lambda_1) with target **alpha_obs = alpha x q_lower**.
- **q_lower** is a pre-stated lower bound on the noticing rate. In the simulated-user model each wrong commit is noticed by an independent coin with probability `p_notice`, so the realised noticing share among N wrong commits is Bin(N, p_notice) / N. Near the bound a run has about alpha x 4,495 phase-C items = 225 wrong commits; we use **N = 100** as a safe floor. q_lower = the 1st percentile of Bin(100, p_notice) / 100 (`scipy.stats.binom.ppf(0.01, 100, p)`): **U1 0.82** (alpha_obs 0.041), **U2 0.38** (alpha_obs 0.019). P(realised share < q_lower) is at most 1 % at N = 100 and smaller at N = 225.
- Then the true rate is about observed / realised share <= alpha x q_lower / realised share <= alpha, except with probability about 1 %, plus the G1 slack (lambda_{T+1} − lambda_1) / (eta T), which is at most 0.0045 for T = 4,495 and |delta lambda| <= 1. Synthetic check (same test): true **0.045** (U1) and **0.036** (U2), both <= 0.05.
- **How it runs.** It sees the same phase-C items, the same `lambda_session`, the same evidence gate and the same alarm state as the live loop (the same effective score that the loop gives its own ACI; the runner checks this on every item). A commit of the shadow gets the same notice coin that the live user would draw on a commit of that item. **It never changes a live decision, a label or a fit.** So the plan runs stay as pre-registered.
- **Limits.** (1) It is a shadow on the decoder versions of the live run. A system that used it live would commit less, offer more and so collect other labels. (2) A real system does not know `p_notice`. It would estimate a lower bound from random confirmation prompts (the compensation route of Wang et al. 2026), or ask for a rating of every sentence as Card et al. 2026 do. Here the simulator fixes `p_notice`, so q_lower is known in advance. This is an idealisation and the results page says so.

### 1d. How P2b is evaluated after this amendment
| reading | rule | status |
|---|---|---|
| **P2b (plan reading)** | true phase-C wrong-commit rate of the **live** controller over the whole replay <= 0.05 in every U1 run (CP95 reported); U2 descriptive | computed and reported unchanged. Predicted to fail where ACI binds (1a) |
| **P2b_q (amendment-2 reading)** | true phase-C wrong-commit rate of the **secondary** controller's commits over the whole replay (same denominator: all phase-C items) <= 0.05 in every U1 plan run (CP95 reported); U2 descriptive | new |

The outcome table of plan.md is computed **twice**: the plan reading (P2b) and the amendment-2 reading (P2b_q in the place of P2b, also inside P4's "P2b holds for SH and ST"). `summary.json` has `outcome` (plan reading) and `amendment_2.outcome_amendment_2`. The results page prints both, side by side. A safety claim from the amendment-2 reading must say: "with the noticing-adjusted secondary controller, run as a shadow on the same decoder versions, with the noticing rate known to the simulator". No rule is changed silently.

## 2. The gate's bias: report it, and add a randomised-exposure option

### 2a. Our check of the literature-check reasoning
The check says that unknown-truth check items are "mostly items where the champion was wrong" and that the plan "counts them against the challenger". The first part is right; the second part is not what the code does:
- In phase B the user sees the champion's offer. With `p_sloppy` 0 a right champion top-1 is always in the offer, so the user accepts it. So **every** item with unknown truth has a wrong champion.
- The champion's top-1 is then in the rejected list, so `_pair_outcome` scores the pair as a **tie**, not as "worse" (library rule: "a champion known to be wrong ... makes the pair a tie when the challenger's result is unknown").
- Effect: the challenger can never win such an item ("better" is lost); it never loses it either. The worse count w is exact. So the absolute branch of the test (N fixed) is unbiased, and the non-inferiority branch (n = w + b) loses power. The test stays valid and errs toward refusal, as the check says.
- Tests: `test_unknown_truth_items_have_a_wrong_champion_without_exposure`, `test_plan_test_shadow_scores_unknown_with_wrong_champion_as_tie`.

### 2b. New report (all runs, report only)
Per session (`check_unknown`) and per run: check items with unknown truth, split by the true status of the champion (right / wrong) and of the challenger: `lost_better` = champion wrong, challenger right, truth unknown (the pairs the plan test cannot credit); `hidden_worse` = champion right, challenger wrong, truth unknown (possible only when the challenger's offer was shown). **Prediction:** `champion_right` = 0 in every plan run.

### 2c. Randomised-exposure option (secondary arm FBX)
- Arm **FBX** = arm FB (same labels, fits, schedule) plus: in phase B, for each check item, a coin with fixed **P = 0.5** (seeded by run seed, user, session, item, drawn before the feedback) shows the **challenger's** offer (its top 5, from the candidate guard) instead of the champion's. Phase B is offer-only, so this has no commit risk.
- **Test:** the champion / challenger decision uses inverse-propensity weighting. W (challenger wrong, champion right) is observed on every champion-shown item and B (challenger right, champion wrong) on every challenger-shown item. Horvitz-Thompson sums W_hat and B_hat, with the **G3 audit bound** reused unchanged (`fidetype.trust.bandit_risk.ipw_slack`: Bennett + Ville, one test each). Two branches at level 0.05 / 2 each (Bonferroni, as the plan test): absolute (upper bound of W < 0.1 N) and non-inferiority (lower bound of 0.6 B − 0.4 W > 0). All top-1 texts identical: pass. Code: `ipw_challenger_test` in `e2.py`.
- If the IPW test passes, the version goes through the loop as a decoder proposal whose paired test compares the version with itself; the block LTT, the null controls and the ledger still apply. If it fails, the proposal is refused (recorded) and the champion's re-calibration follows, as in the plan. The plan test on the same check block is computed and reported (`plan_test_shadow`).
- **Effect on P1 power.** The plan runs have no exposure, so **P1 power does not change**. If the IPW gate replaced the plan gate, almost no decoder update would pass with 45 check items. Synthetic CPU simulation (45 items, champion top-1 error 0.3, user U1, the truth in the top 5 of a wrong top-1 with probability 0.3; 1,000 blocks per case; script in the scratch folder, not committed; "shared" = 70 % of both-wrong pairs have the same text):

| challenger (a = P(worse given champion right), b = P(better given champion wrong)) | plan gate, champion shown | plan gate, coin 0.5 | IPW gate, coin 0.5 | lost-better items per block |
|---|---|---|---|---|
| equal (a 0.05, b 0.05), shared | 0.191 | 0.076 | 0.001 | 0.32 |
| slightly better (a 0.03, b 0.15), shared | 0.378 | 0.157 | 0.001 | 0.92 |
| better (a 0.02, b 0.3), shared | 0.543 | 0.301 | 0.000 | 1.92 |
| much better (a 0, b 0.6), shared | 1.000 | 0.830 | 0.033 | 4.04 |
| much better (a 0, b 0.6), no shared texts | 1.000 | 0.562 | 0.018 | 3.92 |
| worse (a 0.3, b 0.02), shared | 0.000 | 0.000 | 0.000 | 0.11 |

- Reading: the bias is real (about 0.3 to 4 lost "better" items per block), but at 45 items the plan gate still accepts a much better challenger. The design-based IPW gate with the anytime G3 bound has almost no power: its absolute branch can never pass at N = 45 (log(12 / 0.025) = 6.17 > 0.1 x 45), and the non-inferiority branch needs a very large gain. The coin also makes the plan gate weaker, because a shown wrong challenger can hide a right champion.
- **Decision.** The plan gate stays primary. FBX runs as the **last** 2 runs (U1, seeds 0 and 1), if the GPU cap allows. **Prediction:** at most 5 % of FBX decoder proposals pass the IPW test, and FBX − F WER is close to 0. A larger check block (or a sequential test over sessions) is the way to get power; that needs its own plan.

## 3. Card-rule baseline arm (secondary arm CR) and the ST name

- **Source:** Card et al. 2026, *Nature Medicine* (T15 home use, CC BY 4.0, PMC13375540), as quoted by the literature check: continuous fine-tuning; "Each new sentence had a 67% chance of entering the training buffer and 33% chance of being held out for validation"; "Checkpoints were updated only if validation performance improved"; training on trials "confirmed by the participant to be decoded correctly".
- **Arm CR** (U1, seeds 0 and 1 = **2 runs**, run after the plan's U1 runs and before the U2 runs):
  - Labels: confirmed labels only = accepted offers, retypes and corrections. Kept commits are not used: in our simulation the user does not confirm a kept commit, and a kept commit can be a silent error. (In Card et al. the user rates every sentence.)
  - Each labelled item goes to the held-out validation buffer with probability 0.33 (coin seeded by run seed, session, item); held-out items never train. Phase-A held-out items join the buffer before the session's gate, so the buffer includes the current day.
  - Fits, schedule, steps, LR and the challenger choice are the same as FB (amendment 1).
  - **Update rule:** a decoder challenger goes live iff its greedy phoneme error rate on the whole buffer is **strictly lower** than the champion's (no statistical test; an empty buffer refuses). We use PER, not WER, because it needs no word decoding of the growing buffer; Card et al. do not say which validation metric (we read the check's quote only).
  - The block LTT, the null controls, the evidence gate, ACI, the e-process monitor and the ledger still apply to the version that goes live (the same trust guard). The plan test on the same check block is reported (`plan_test_shadow`), so we can count where the two rules disagree.
  - Reported: CR − F and CR − FB phase-C WER (last third, per seed), accepted decoder updates, P2a, P2b, P2b_q, P3, P5. CR is not part of P1-P5.
- **ST** is renamed **"naive self-training"** in the config and in the results (its own top-1 on every item, no filter). It is weaker than CORP (Fan et al. 2023: LM-corrected pseudo-labels, replay, a loss threshold); the results never call it CORP. The arm code stays "ST".

## 4. Claim wording (narrowed)
- Card et al. 2026 already use an update gate ("validation improves") on the same participant at home. So "an update gate" is **not** new.
- Our claim, if outcome A holds: **"a statistically tested update gate (a non-inferiority test at a stated level, with null controls) plus a stated long-run wrong-commit bound"**, on one participant with simulated feedback. Cite Card et al. 2026 as the closest real system. The CR arm shows what the statistical gate adds or costs against Card's rule.
- Do not write "first ACI / conformal in speech BCI" (an EEG speech-decoding preprint uses ACI, chen 2026).

## 5. GPU-hour estimate (local RX 7800 XT)
| part | plan + amendment 1 | added by amendment 2 |
|---|---|---|
| base | 10.6 h | 0 |
| 20 plan runs (fits, forward passes, word decoding) | about 34 h | challenger guard on the check block (45 decodes per session, 0.06 s each): about 0.03 h per run, 0.6 h in all; the shadow controller: negligible (CPU, no decode) |
| CR, 2 runs | - | about 2.4 h per run (fits 1.25 h, forward 0.3 h, decoding 0.4 h, validation buffer about 0.3 h, more labels refused) = **about 4.8 h** |
| FBX, 2 runs | - | about 2 h per run (as FB) = **about 4 h** |
| **total wall time** | about 45 h (plan range 45-60 h) | **about 54 h (range 54-70 h)** |

The cap stays **90 h** (wall time, checked before each part). The estimate stays under the cap, so all 24 runs are expected to finish. Order: the plan's U1 runs, then CR (it compares with them), then the plan's U2 runs, then FBX. CR runs before the U2 runs; only if the job came within about 5 h of the cap could CR cost a U2 run. At about 54 h of 90 h this does not happen.

## Code and checks (same task, after this file is committed)
- `e2.py`: `make_shadow`, `ipw_challenger_test`, `card_rule`, `unknown_split`, `plan_test_shadow`; per-arm options from `config.json` (`gate`, `exposure_p`, `holdout_share`); per-run `binding`, `p2b_q`, `noticing_adjusted_bound`, `check_unknown`, `external_rule`; `verdict` keeps the plan rules on the 20 plan runs and adds `amendment_2` (P2b_q, the amended outcome, the secondary runs).
- `config.json`: arms CR and FBX, `secondary_runs`, `execution_order` (24 runs), `amendment_2` (q_lower and the rules above).
- CPU tests in `test_e2.py`; a CPU dry run (scratch folder, deleted; `HIP_VISIBLE_DEVICES=-1`) runs all 7 arms on two S8 pseudo-sessions and the stop / resume check.
