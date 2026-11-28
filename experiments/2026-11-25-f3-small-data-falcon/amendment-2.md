---
title: F3 at small data (FALCON H2) - pre-run plan amendment 2 (training stability of new output layers)
type: experiment-plan-amendment
task: P15-54 (gap 219)
amends: plan.md (pre-registration 19ec6c5) and amendment-1.md (4d31f8e); neither file is changed
updated: 2026-11-27
---

# Amendment 2 to the F3 small-data pre-registration (before any GPU run)

**Date:** 2026-11-27. **Status:** written and committed **before any GPU run of P15-54, before any training, and before any test sentence was decoded.** Stage 0 ran on 2026-11-25 (caches and `results/session_roles.json`, `83da5d1`). No pretraining, stage-1 or stage-2 run exists. This commit contains this file only; the code follows in a separate commit.

**Data read for this amendment:** (a) the P15-50 results and training logs (another experiment, already published in [its results.md](../2026-11-23-f3-full-data-controls/results.md)); (b) a CPU check of the CTC loss **at step 0, with no training**, on 3 trials of the stage-1 train pool (the first 12 trials of each **val** session); (c) the frame counts and character counts of that pool, and the CTC loss of a constant label-prior output on it (with the true and with deranged labels); (d) the frame and phoneme-token counts of the T15 train trials of arm I. No test session, no test sentence and no val CER was read. No neural value was looked at other than through the step-0 loss.

**Scope.** This amendment adds one stability measure to every arm (S1), a pre-registered "did it train" rule (S2), a re-seed policy (S3), the effect of S2 on the pass rules (S4) and an opt-in val-only pilot. No arm, budget, seed of the plan, LR grid, step count, warmup, augmentation, test split, pass threshold or stop rule changes. Where this amendment and the earlier files disagree, the run follows this amendment.

## 1. Why: the P15-50 evidence
P15-50 ([results.md](../2026-11-23-f3-full-data-controls/results.md), post-hoc note 1) found that every run that did not train had a **new, randomly initialised output layer**:

| arm in P15-50 | head at start | loss at step 100 | runs that trained |
|---|---|---|---|
| E+, T (pretrained head) | pretrained | 3.6-3.8 | 5 of 5 (E+); T trained to its usual level |
| R+ (all new) | new | 44-99 | 2 of 5 |
| I (T15 trunk, new head) | new | 99-140 | 1 of 5 |

The training logs (`derived\p15-50\run.log`) show one pattern. A run that trained first fell to the **label-prior plateau** (loss about 3.0: the model emits blank on almost every frame and the characters at their unigram rate). It reached that plateau by step 200-300 and then left it. The stuck runs never reached the plateau: their loss stayed at 10-49 for 6,000 steps (R+ seeds 1 and 4, I seeds 0, 1, 2 and 4). R+ seed 2 needed 700 steps to reach the plateau and then stayed there.

Two facts make the risk **larger** in P15-54:

1. **Shorter schedules.** P15-54 runs have 500-1,100 steps (plan 7.1). P15-50 runs had 6,000. A run that needs 200-700 steps only to reach the plateau loses most of a 500-step run.
2. **Longer trials per character.** On the stage-1 train pool, H2 has **159.2 frames per character** (162,260 frames, 1,019 characters, 10 ms frames). The step-0 CTC loss of a new head (arm R, standard PyTorch init) is **904-923 per character** (seeds 0 and 10; arm E0 with its re-initialised head: 959). The mean blank probability at step 0 is about 0.01. The CTC loss grows with the frames per character, so the start is much further from the plateau than in P15-50.

The arms of P15-54 with a new CTC head are **R, E0, I, M, X-R** (and the I and P pretraining heads). The arms with a copied head are **E, T, X-E** and the P target run. If a new head gets stuck, a "win" of E over R can mean only "R did not train". This amendment removes that confound as far as possible before the run.

## 2. S1: blank-bias initialisation of every new CTC head (all arms)
- **Rule.** Every CTC head that is **built new** starts with `bias[blank] = b`, with **b = 9.6** for the H2 character heads and **b = 7.9** for the T15 phoneme head of the I pretraining. All other weights and biases keep the PyTorch default init. The bias is set after all layers are built and uses no random number, so every other tensor of a seed is the same as before (amendment 1, 3.8 still holds: the head of E0 at seed s equals the head of R at seed s, now with the same blank bias).
- **Where it applies.** The new 98-token head of every target run (R, E0, I, M, X-R, in stage 1, stage 2 and the pilot) and the new heads of the I pretraining (41 phoneme tokens, blank 0) and the P pretraining (98 tokens). A head copied from a checkpoint (E, T, X-E, P target runs) is not changed: copy_parts replaces it. M pretraining has regression readouts, not a CTC head: no change.
- **Value.** b = ln((V − 1)(F − 1)) with V = 98 tokens and F = 159.2 frames per character of the stage-1 train pool, rounded to one decimal: b = ln(97 × 158.2) = **9.6**. With a zero input to the head, this gives p(blank) = (F − 1) / F at every frame: the blank rate of an ideal alignment. It uses train-pool label lengths and trial lengths only. The same formula for the I pretraining head: V = 41 phoneme tokens, F = **68.52** frames (10 ms, after the hold) per phoneme token over the 8,065 T15 train trials (14,110,528 frames, 205,923 tokens): b = ln(40 × 67.52) = **7.9**. The P pretraining uses H2 characters, so b = 9.6.
- **Step-0 check (CPU, no training, 3 stage-1 train trials, arm R seed 10):**

| blank bias | 0 (plan init) | 4 | 6 | 8 | 9.6 (S1) | 11 | pretrained head (E) | label-prior model |
|---|---|---|---|---|---|---|---|---|
| step-0 loss per character | 923.0 | 265.6 | 63.9 | 11.7 | 5.23 | 5.10 | 4.38 | 3.08 |
| mean p(blank) | 0.010 | 0.343 | 0.776 | 0.960 | 0.992 | 0.998 | 0.993 | 0.994 |

  The "label-prior model" is a constant output with p(blank) = 1 − 1/F and each character at its train-pool unigram rate divided by F (no input; 36 stage-1 train trials). It is the plateau that every trained P15-50 run passed through.
- **Why this measure and not another.**
  - It acts on the cause seen in P15-50: a new head starts far above the label-prior plateau, and some seeds never reach it. A blank-dominated start is the state that a pretrained head already has (E+ in P15-50: loss 3.6-3.8 at step 100). With S1 a new head starts in that state.
  - It is standard CTC practice to start a new output layer with a high blank probability, because a CTC model first learns to emit blank on almost every frame and only then learns where the characters are.
  - It carries **no character prior**: all non-blank biases stay equal (default init). So H3 (E0 vs R: trunk vs output prior) keeps its meaning. E's copied head still has the character prior; E0 and R have only "blank is likely", which is true for every CTC task and every label set (also for the deranged C2 runs).
  - It changes no recipe value. A longer warmup (the other common measure) would take 20-40 % of a 500-step run and would change the recipe of the E arm too, which trained on every seed in P15-50. Gradient clipping (1.0) is already present in every run (plan 7.1). A smaller output init scale alone does not move p(blank) away from 1/98.
- **Fairness.** S1 applies the same rule to every arm. An arm with a copied head is not changed, because it already starts blank-dominated (step-0 loss 4.38). So S1 makes the start state of new-head arms close to that of copied-head arms. It does not favour one arm.

## 3. S2: "did it train" rule (pre-registered)
- **Rule.** A target run **trained** if the mean training CTC loss over its **last 100 optimiser steps** (finite losses only) is **≤ its own label-prior loss + 1.0** (nat per character). Otherwise (higher, or no finite loss) it **did not train**.
- **Label-prior loss of a run.** The CTC loss (per target character, mean over trials, the same reduction as the training loss) of a constant output on the run's own train pool: p(blank) = 1 − L/T and p(c) = u(c) · L/T, where T = total frames, L = total characters and u = the character unigram of the pool, **with the labels the run trains on** (deranged labels for a C2 run). It needs no neural value. The runner computes it for every run and writes `prior_loss` and `trained_max_loss` to `result.json`.
- **Why this signal.** A stage-2 run has no val split: its per-session input layers are for the 5 test sessions, and at budget 3 the train pool has only 3 trials per session. The training loss reads only the run's own train pool. It never reads a val or test sentence. The flag is computed and written **before** the run's evaluation (`result.json` field `trained`). The same rule applies in stage 1, the pilot and stage 2, to normal and deranged runs and to every arm.
- **Why this threshold.**
  - A run at or below its label prior has at least learned the output prior. That needs no signal. So a run at the prior that does not go lower is a **valid** "did not read the signal" result, and it counts as "trained". S2 flags only runs that did not even reach the prior: an optimisation failure.
  - The stage-1 train pool has a label-prior loss of **3.08** (2.85-3.63 per trial). With the deranged labels of seeds 10, 0, 1 and 2 it is **3.56-3.78** (a deranged text can fall on a short trial). A fixed threshold near 4 would flag deranged runs that sit at their own prior, which are valid C2 evidence. So the threshold is per run.
  - With S1, a new head starts at about 5.2 (table above), above prior + 1 = 4.08. So a run that does not move from its start is flagged too.
  - The stuck runs of P15-50 stayed at 10-49, far above every threshold here.
  - Training loss includes augmentation and dropout. The label prior does not depend on the input, so augmentation does not move it.
- S2 does not change the plan's stage-1 exclusion (val CER > 0.95) or any other rule. It is a separate flag.

## 4. S3: re-seed policy (primary) and the as-is analysis (secondary)
- **Slot.** A slot is one planned run: (stage, arm, budget, seed, deranged index j). Attempt 0 is the plan's run, exactly as before (same init seed, same batches, same augmentation).
- **Re-seed.** If attempt a did not train (S2), the runner starts attempt a + 1, up to **2 re-seeds** (3 attempts in total). Attempt a uses init seed **s + 1000 a** and its own batch and augmentation stream (RNG key `[s, budget, j code, stage code, a]`). The **labels do not change**: the train pool is fixed by the budget, and the derangement uses the slot seed `[s, 77 + j]` as before.
- **Accepted run.** The first attempt that trained is the slot's result. If no attempt trained, attempt 0 is the slot's result, flagged `trained: false`. If a cap stops the re-seeds of a slot, the slot counts as "no attempt trained".
- **Stage 1.** Each (arm, LR) cell is a slot with tuning seed 10 (re-seeds 1010, 2010). An LR whose accepted run did not train is excluded, like a run with val CER > 0.95 (the plan's fallback then applies).
- **Conditional C2 pairs** (plan 7.3) are triggered from the accepted normal and accepted deranged results of the slot.
- **Cap.** The cap is checked before every attempt (amendment 1, 3.15). The caps (9 h core, 20 h total) do not change.
- **Why re-seed and not "count as-is" for the primary.**
  - Counting a stuck baseline as-is gives E or I a "win" that measures R's optimisation failure, not transfer. That is the confound this amendment exists to remove.
  - Re-seeding is decided from the training loss only, by a rule fixed here, for every arm the same way. It cannot read a test number.
  - S2 removes only runs that did not even reach the label prior, which needs no signal. A run that reaches the prior but does not read the signal stays in the analysis. So re-seeding cannot turn a real "R does not learn from 3 sentences" result into an R win by picking lucky seeds; it can only replace optimisation failures.
  - The cost of a re-seed falls on the arm that fails, so an unstable arm costs more GPU time, not more accuracy.
- **Secondary (reported, marked as secondary).** `summary.json` field `secondary_as_is`: the plan rules **exactly as written** on attempt 0 of every slot (plan seeds, no re-seed, no trained requirement), with its own outcome label and a flag `agrees_with_primary`. If the two outcomes differ, the write-up must say so in its summary.
- **Stability readout (descriptive, reported).** `summary.json` field `stability`: per arm, normal and deranged, the number of slots, attempt-0 runs that did not train, re-seeds used, and slots where no attempt trained. In P15-50 the main practical value of E+ was stability (post-hoc note 2). Here it is measured by a rule that was fixed before the run.

## 5. S4: what "trained" does to the pass rules (primary)
- **Wins.** win(A, B, b) is computed as in plan 8. In the primary analysis it counts for H1-H5, neg(A) and the "would-be winner" test (amendment 1, 3.18) **only if every paired run (both arms, all 3 seeds) trained**. A win that passes the plan rule with an untrained run in it is listed in `untrained_confounded_wins` and does not count.
- **C2.** A C2 seed whose deciding deranged run(s) did not train after all re-seeds gives no valid C2 evidence: that seed **fails** C2 (status `untrained`). A deranged run that does not train has a high CER for a reason that is not the wrong labels (P15-50 note 6), so it must not make C2 pass. A normal run that did not train fails C2 already through its own high need.
- **C1** is unchanged.
- **Effect.** S4 can only remove passes (of a win or of a C2 seed). It cannot create one. So it can move the outcome toward "none" or N, never toward an A label.

## 6. Opt-in stability pilot (val only, before the main run)
- **Purpose.** To check, before the 6-8 GPU h main run, that S1 removes the stuck mode at H2 scale, and that S2 does not misfire.
- **Design.** Arm R. Budget 12 on the 3 **val** sessions (the stage-1 setting: train = first 12 trials of each val session, eval = last 10). LR {3e-4, 1e-3} (the stage-1 grid). Seeds **20, 21, 22, 23, 24** (used nowhere else). Blank bias **on** (S1) and **off** (plan init). Each run uses the full 800-step LR schedule of budget 12 and stops at **step 400**. No re-seed. 2 x 2 x 5 = **20 runs**. Each run writes the S2 flag (loss of steps 301-400), the loss curve (mean per 100 steps) and the val CER at step 400. No test session is read; the runner refuses a test session in the pilot.
- **Pre-registered reading.** If **3 or more of the 10 blank-bias runs** did not train (S2 at step 400), the decision is **stop**: the main run does not start (`f3s.py all` refuses with exit code 2) and a new amendment is needed. Otherwise **go**. The 10 runs without the bias are descriptive: they show whether the stuck mode exists at H2 scale without S1.
- **The pilot never changes S1, S2, S3 or any value of this amendment.** It only decides go or stop. Pilot val CERs are not used for any selection.
- **How to run.** `launch.py pilot` (or `f3s.py pilot`), after the A1 GPU job. Output: `derived\p15-54\pilot\` and `pilot\pilot.json`. The pilot has its own GPU clock (`pilot\gpu_clock.json`) and its own cap of 1.5 h. It does not count toward the plan caps. The main run is allowed without the pilot, but the orchestrator's plan is to run the pilot first.
- **GPU estimate.** 20 runs x 400 steps = 8,000 steps; 0.33 s per step + 10 % (plan 11) = **about 0.8 h** (48 min). The H2 step time is not measured yet.

## 7. New GPU estimate
| part | GPU h |
|---|---|
| pilot (opt-in, own clock) | about 0.8 |
| core, as amendment 1 | about 6.2 (+ up to 2 for conditional C2 pairs) |
| re-seeds in the core (allowance: 10 % of the 57 core slots re-seeded once, mean 900 steps) | about 0.6 |
| extended, as amendment 1 | about 7.6 |
| re-seeds in the extended part (same allowance) | about 0.7 |
| **total with the pilot** | **about 16** (worst case with all conditional pairs: about 18) |

The caps do not change: core 9 h, total 20 h (main run only). If many runs need re-seeds, the core cap ends the core earlier ("not run (cap)"), as amendment 1, 3.15 says.

## 8. Records in the run folder and in `summary.json`
- Each target run's `result.json`: `attempt`, `init_seed`, `blank_bias`, `final_train_loss`, `loss_curve`, `prior_loss`, `trained_max_loss`, `trained`. Re-seed attempts are in `<run>-a1`, `<run>-a2`.
- Pretraining `DONE.json` / `config.json` of I and P: `blank_bias`.
- `selection.json` (stage 1): per cell the accepted attempt and its train loss.
- `summary.json`: the primary (accepted runs, S4), `untrained_confounded_wins`, `secondary_as_is`, `stability`.

## 9. Where this can still fail
- S1 may not remove every stuck run: the trunk and the per-session layers are new too in arm R. The re-seed policy and the pilot are there for this case.
- A real transfer gain that comes only through faster or more stable training (the E+ stability of P15-50) is reported in `stability`, not as an H1 pass.
- The value of b is set from the val sessions. The test sessions are the same person and task, so F should be similar; it is not checked on test data.
- S2 uses the same margin (1 nat) at every budget. A run that learns slowly might still be above its threshold at the end; it would then be re-seeded. This is a cost, not a bias: the same rule applies to every arm. The pilot shows how often this happens at budget 12 without and with S1.
