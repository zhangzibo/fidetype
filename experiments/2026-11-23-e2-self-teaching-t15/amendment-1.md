---
title: E2 self-teaching on T15 - pre-run plan amendment 1
type: experiment-plan-amendment
task: P15-49 (wrapper P15-52, gap 212, E2 part)
amends: plan.md (pre-registration 29c1dc9; plan.md itself is not changed)
updated: 2026-11-24
---

# Amendment 1 to the E2 T15 pre-registration (before any GPU run)

**Date:** 2026-11-24. **Status:** written and committed **before any GPU run of P15-49 and before any data of the replay sessions S9-S44 was read**. The only runs so far are CPU tests and a CPU dry run on S0-S7 (3 training steps) and S8 items, in a scratch folder that was deleted after the run. No result exists.

**Scope.** plan.md stays frozen. This amendment records where plan.md is ambiguous or defective, and the exact choice that the run wrapper (`e2.py`, `config.json`, commit `83053f3`) makes. No arm, user, rule, window, seed, threshold or stop rule changes. If this amendment and plan.md disagree, the run follows this amendment for the six points below, and the results page reports each point.

## The six points

### 1. The S8 grid cannot choose the nightly step count
- **Plan says:** "Update-1 LR {1e-4, 3e-4} x nightly steps {150, 300}. Rule: ... choose the setting with the lowest phase-C WER of S8; ties to the smaller LR and fewer steps." The default in "Replay loop" is 300 nightly steps.
- **Defect:** the nightly fit runs after phase C (plan step 7). On a one-day grid, it cannot change the S8 phase-C WER. The two step values always tie exactly, so the tie rule always picks 150. The grid really chooses only the LR.
- **Choice:** the grid runs each LR once on S8 (FB, U1, seed 0) without the nightly fit, and both step cells get that LR's result. `select_grid` applies the plan rule unchanged. So **the nightly step count is 150 in every replay run, never 300.** The grid file (`results/grid.json`) states this.
- **Expected effect:** each nightly fit takes half the steps of the plan's default. That can make the nightly learning smaller, which weakens P1 (FB − F ≤ −0.02) and narrows the OR − F gap. The safety rules (P2a, P2b, P3, P5) do not depend on it, because every version must pass the gate. GPU time also drops: the fits take about 20 h instead of about 30 h. A null P1 result (outcome B) must be read with this point in mind.

### 2. The nightly LR is not given
- **Plan says:** the grid varies the "Update-1 LR". For the nightly fit it gives a step count, but no LR.
- **Defect:** the nightly fit needs an LR, and plan.md does not name one.
- **Choice:** the nightly fit uses the chosen update-1 LR (1e-4 or 3e-4).
- **Expected effect:** small. Both values are standard fine-tuning LRs. Because the nightly fit also trains the last GRU layer and the output layer, a too-small LR mainly reduces learning (a risk to P1, not to safety).

### 3. Which model the update-1 challenger starts from
- **Plan says:** step 3: "Update 1: fit the day layer of d only, **from the champion**, on the phase-A labels ... This is the challenger." Step 7: the nightly version "**becomes the challenger of session d + 1** at its phase B".
- **Ambiguity:** read literally, session d + 1 has two challengers (the nightly version and the update-1 fit). There is only one check block and one gate per session. Testing two challengers on the same block would raise the error level of the test.
- **Choice:** one challenger per session. If a nightly version of d − 1 exists, update 1 starts from it: its day layer of d − 1 is copied to day d, then the day layer of d is fit on the phase-A labels. Otherwise update 1 starts from the champion. The challenger is tested against the live champion. Phases A and B still show the champion's offers. If the challenger is refused, it is discarded. The live champion then gets the same-decoder re-calibration proposal (kind "recalibration"). The next nightly fit starts from the live version and uses all labels collected so far, so no label is lost.
- **Expected effect:** the nightly learning reaches users only through the gate, as the plan intends. A refused challenger throws away both that night's fit and that day's update-1 fit. If the gate refuses often (the plan expects this risk with 45 check items), learning reaches the live decoder slowly. That can push P1 toward outcome B, which is the safe direction.

### 4. The fit optimiser
- **Plan says:** "Fits use the M4-13 CTC step (collate, micro_chunks, augmentation) with AdamW". The grid LRs are 1e-4 and 3e-4.
- **Ambiguity:** the M4-13 base training used AdamW with **eps 0.1**, LR up to 5e-3. With eps 0.1 and LR 1e-4, each Adam step is roughly lr · g / 0.1. For typical gradients (about 1e-3) that is about 1e-6 per step, so a 100-step fit hardly changes the weights.
- **Choice:**
  - AdamW with the **torch default eps 1e-8**, betas 0.9 / 0.999, constant LR, and a new optimiser for each fit.
  - Weight decay follows the M4-13 parameter groups (weights 0.001, biases 0, day layers 0), with gradient clip 10.
  - Batch 32: phase A has 24 items, so update 1 uses all labelled phase-A items in every step.
  - The M4-13 step is otherwise used unchanged: `collate` with noise 1.0 / offset 0.2 / random cut 3, `micro_chunks`, `patch_model` input dropout 0.2, model dropout 0.4, and the train.py length filter.
  - Day layers other than d are restored exactly after each fit.
- **Expected effect:** the fits can change the model at the grid LRs. With eps 0.1, an F-like "no learning" result would follow almost by construction, so P1 would be uninformative. A larger effective step also raises the risk that a fit makes the decoder worse. The gate (non-inferiority test, null controls) catches that, and refused updates are reported. A fit with a non-finite loss is refused, counted and not retried (the plan's broken-fit rule).

### 5. The offer list
- **Plan says:** "simulated users (`FeedbackUser`; offer = top 5)".
- **Ambiguity:** the calibrated drop-in guard shows only 1 choice (`offer_max_k` 1 in the start-guard config). The earlier P15-13 / P15-24 code passed the guard's choices, which would give a 1-item offer.
- **Choice:** the offer is the guard's top-1 text, then the texts of the word n-best list that the guard decoded for that item, in order, without duplicates, 5 at most. The commit decision, the score and the guard risk come from the guard unchanged.
- **Expected effect:** the user accepts more offers than with a 1-item list. That gives more correct labels in phase A / B / C and fewer "unknown truth" check items. Fewer unknown items make the gate less likely to refuse a challenger. This matches the plan's design; a 1-item offer would starve FB and SH of labels.

### 6. The output folder
- **Plan says:** own outputs go to `C:/Users/zhang/bci-data/derived/e2-t15/` (and `derived/e2-t12/`).
- **Change:** the task brief for the wrapper names `C:/Users/zhang/bci-data/derived/p15-49`. The wrapper writes only there and refuses any other folder under `derived`.
- **Expected effect:** none on any number. Only the path changes.

## Other wrapper choices (not fixed by the plan)
- **ACI start value λ_1:** the `commit_p` of the start guard (calibrated on S8). This is part of "choose ... the start guard" on S8. P2a uses this λ_1 in the bound alpha + (λ_{T+1} − λ_1)/(ηT).
- **Candidate guards:** every proposal, whether a decoder challenger or a re-calibration, uses a **copy of the start guard** as the candidate. On accept, `TrustGuardUpdater` raises `commit_p` to the session threshold (its unchanged behaviour). A copy of the live guard would only ever raise `commit_p`, and the threshold could never come down again.
- **Start guard:** `fidetype.trust.calibrate` on all 279 labelled S8 items with the base decoder (S8 day layer = copy of the S7 day layer), 300 null trials, seed 0. If calibration refuses (`NullControlError`), the job stops with `FAILED`. The plan has no fallback, so this would be reported as outcome N.
- **Nightly labels:** the arm's labels from the replay sessions S9 .. d, all phases. No base-session labels are used ("all labels of sessions <= d that the arm may use").
- **SH permutation:** update 1 permutes inside the phase-A label set. Each nightly fit draws a new permutation of the whole label pool.
- **Simulated-user randomness:** one generator per item, seeded by (run seed, user, session, item index), and the same for every arm. Paired arms therefore get the same coin flips.
- **GPU clock for the 90 h cap:** wall time of the job, because the job holds the GPU while it runs, also while the CPU decodes.
- **T12 stage 2:** not wired yet. It needs its own wrapper for the T12 v2 recipe. The plan starts it only after the T15 U1 runs and only if the cap leaves ≥ 8 h. A second amendment comes before any T12 run.
- **eWPM and safe WPM v0.2 (descriptive):** not computed by the runner. The analysis step computes them from the per-item records (action, right / wrong, texts, bins), which stay in the derived folder.
