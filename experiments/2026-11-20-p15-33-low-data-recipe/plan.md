---
title: P15-33 E1 low-data recipe that reads the target signal - pre-registered plan
type: experiment-plan
task: P15-33
updated: 2026-11-19
---

# P15-33: find a low-data recipe that reads the Willett signal at minutes scale (plan, written before any result)

## Why
- [P15-08 E1a](../2026-11-19-p15-08-e1-cross-body/results.md) is null at minutes scale. With 3 to 100 labelled minutes, every arm stays at test CER ≥ 0.77.
- C2 fails: at 30 min, arm E trained on deranged labels gets 0.836, the normal run 0.810. The time-shuffled CER is about equal to the normal CER at 30 min. So the decoders output the label prior. They do not read the signal.
- The 30-min train loss falls to about 1.1 (the same as at full data), but the val CER stays at about 0.81. So the model memorises the 47 training sentences.
- A new source arm (KT-sEMG) with the same recipe would hit the same floor. This task ([gap 120](../../wiki/questions/open-gaps.md)) fixes the recipe first.

## Design in one table
| Step | What | Data used |
|---|---|---|
| 1. Search | 4 candidate recipes x arms R and E, 30-min budget, seed 0; a label-deranged run where eligible | train subset + **val block only** |
| 2. Select | fixed rule (below): pass val-C2, then lowest val CER | val numbers only |
| 3. Grid | the selected recipe, frozen, on all arms R, T, E, S x budgets 3, 10, 30, 100, all x seeds 0, 1 + C2 | P15-08 test protocol |
| 4. Verdict | P15-08 rules V1, H1-H4, C1, C2, roadmap rule, unchanged | test block |

One detached job runs all 4 steps. No test-block number is computed before step 3. Step 2 is a fixed function of the val numbers, so no human choice happens between the search and the test.

## What stays the same as P15-08 (reused read-only)
| Item | Value |
|---|---|
| Code | `e1.py` (model, splits, budgets, augmentation, metrics) and `run.py` (Willett store, eval, verdict) of P15-08, imported read-only |
| Data | the P15-08 Willett cache `C:\Users\zhang\bci-data\derived\p15-08\willett\` (same sentences, splits, salt, per-session normalisation) |
| Splits | test = last block of each session (80 sentences, 3,448 characters); val = one other block per session (106 sentences); train pool = the rest (781 sentences, 506 min) |
| Budget subsets | the same salted nested subsets per seed (for example 30 min: 47 sentences on seed 0) |
| Trunks | T = P15-08 text-only trunk (`text/final.pt`); E = P11-01 `best.pt` step 30,000; S = E shuffled within tensors (seed 1000 + run seed); R = random |
| Model | new stem Linear(192 -> 512) -> 8 causal blocks (d 512) -> LayerNorm -> 98-token head; greedy CTC; no LM |
| Batches | random sentences up to 24,000 frames; batch k depends only on (seed, budget, label shuffle, k) |
| Label derangement (C2) | the P15-08 derangement (rng [seed, 77]) among the subset sentences |
| Rules | V1, H1-H4, C1, C2, roadmap rule exactly as in the P15-08 plan; same bootstrap (10,000, seed 0) |

All outputs go to `C:\Users\zhang\bci-data\derived\p15-33\`. The code refuses to write into the P15-08 folder.

## Candidate recipes (step 1)
All candidates use AdamW, cosine LR to 1e-6, clip 1.0, val CER every 100 steps, and the same steps per budget: **3 min 600, 10 min 1,000, 30 min 2,000, 100 min 2,000, all 3,000** (P15-08: 500 / 800 / 1,200 / 2,000 / 3,000).

| Id | Idea | Trainable | LR / warmup | Weight decay | Dropout | Augmentation |
|---|---|---|---|---|---|---|
| **A** | stronger regularisation + augmentation | all | 5e-4 / 100 | 0.05 | 0.3 | strong |
| **B** | frozen trunk: train input and output layers only | stem + out_norm + head | 1e-3 / 100 | 0.01 | (trunk in eval mode) | base |
| **C** | frozen trunk + strong augmentation | stem + out_norm + head | 1e-3 / 100 | 0.01 | (trunk in eval mode) | strong |
| **D** | lower LR + longer schedule + more dropout | all | 1.5e-4 / 200 | 0.05 | 0.3 | base |

| Augmentation | Offset SD | Noise SD | Time masks | Channel dropout | Time stretch |
|---|---|---|---|---|---|
| base (= P15-08) | 0.2 | 0.3 | 2 x ≤ 20 frames | none | none |
| strong | 0.3 | 0.5 | 5 x ≤ 40 frames | each electrode zeroed with p 0.2 per sentence | speed factor U(0.8, 1.25) per sentence, linear resampling, label unchanged |

With a frozen trunk, the trunk weights do not change and its dropout is off (fixed feature map). Gradients still pass through the trunk to the stem. For arm R the frozen trunk is a fixed random feature map; for arm S a fixed shuffled one.

**Not chosen, and why:**
| Idea from the gap | Why not in this search |
|---|---|
| smaller model | H1-H4 compare trunks of one fixed shape; a smaller model cannot load the T / E / S trunks |
| Willett-style synthetic sentences from labelled character snippets | needs character time labels. The budget sentences have none; `singleLetters.mat` would add labelled data outside the budget; forced alignment from a weak model is circular. Kept for a follow-up if this search fails |
| CTC blank bias | a small change to the start of training; it does not address memorisation |

## Search protocol (step 1)
- Budget 30 min, seed 0 (47 sentences, 30.55 min). Arms **R** (clean track) and **E** (the H1 arm).
- For each candidate and arm: one normal run. Readout at the **final step** on the val block: val CER and time-shuffled val CER (frames permuted within each sentence, seed 12345; descriptive).
- **Eligible** = normal final val CER < 0.80. (P15-08 baseline on val at 30 min, final step: E 0.821, label-deranged E 0.844.) Only an eligible (candidate, arm) gets a label-deranged run with the same recipe. This saves compute; a non-eligible run is not better than the baseline.
- No test-block number is computed in the search.

## Selection rule (step 2, fixed)
1. A (candidate, arm) **passes val-C2** if it is eligible and its deranged final val CER ≥ max(0.75, normal final val CER + 0.10). (Same thresholds as the P15-08 C2 rule, on val.)
2. A candidate **passes** if at least one of its arms passes val-C2.
3. Among passing candidates, select the one with the **lowest normal final val CER over its passing arms**. Tie: fewer trainable parameters.
4. If no candidate passes: **stop**. No test grid runs. The gap stays open; the write-up reports the val numbers and proposes the next recipe (for example Willett-style synthetic sentences). The job writes `DONE` with the note `no_recipe`.

`selection.json` (val numbers only) is written before the grid starts and is copied to `results/selection.json`.

## Grid and verdict (steps 3-4)
- The selected recipe is applied unchanged to all 4 arms x 5 budgets x 2 seeds (40 runs), primary readout = test CER at the final step, as in P15-08.
- The search runs of the selected candidate at 30 min seed 0 (arms R, E, normal and deranged) used the same recipe, data and batches as the grid runs. Their weights are reused; only the test readout is added.
- **C2 (test):** arm E, 30 min, seed 0, deranged labels (as in P15-08). If the arm that passed selection is R, the R deranged run is evaluated on test too. The P15-08 C2 rule applies to each run.
- **C1:** as in P15-08 (budgets 30 and all; runs with test CER ≤ 0.70 must have time-shuffled test CER ≥ 0.85).
- V1, H1-H4, roadmap rule: unchanged code and thresholds.

## Done-when (from gap 120) and reading
| Outcome | Reading |
|---|---|
| a candidate passes val-C2, and test C2 passes | the gap is closed: a low-data recipe that reads the target at 30 min exists; H1-H4 under it are the new E1 answer at minutes scale |
| a candidate passes val-C2, test C2 fails | the val pass did not hold on the forward-in-time test block; the gap stays open (partial); H1-H4 are reported but marked "recipe does not read the signal on test" |
| no candidate passes | gap stays open; no test numbers; the next recipe is named |

H1-H4 outcomes are read with the P15-08 table. A null H1 under a recipe that passes C2 is a stronger null than E1a's (the decoders then read the signal, and the EMG trunk still does not help).

## Confounds and limits stated in advance
- The search uses 2 arms, 1 seed and 1 budget. The selected recipe can favour R or E. The grid applies it to all arms; this is a limit, not tuned per arm.
- The candidates change several factors at once. The search finds a recipe; it does not say which factor matters.
- 4 candidates on 1 val block: a mild selection effect on val. The test block stays clean.
- With a frozen trunk, the arm comparison changes meaning: H1 then asks whether the EMG trunk is a better **fixed feature map** than the text-only trunk, not a better **initialisation**.
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM.

## Compute budget
Measured on the 30-min subset (RX 7800 XT, training steps only, no eval): full fine-tune 0.32-0.39 s/step; frozen trunk 0.25 s/step. Val eval adds about 1 min per 2,000-step run.

| Part | Runs | Estimate |
|---|---|---|
| Search (worst case: all 8 eligible -> 16 runs of 2,000 steps) | 8-16 | about 1.5-3.1 h |
| Grid, full fine-tune recipe (A or D): 8 x 8,600 steps, minus 2-3 reused runs, plus 1-2 C2 runs | 39-40 trained | about 7.3 h |
| Grid, frozen recipe (B or C) | 39-40 trained | about 4.9 h |
| **Total** | | **about 6.5-10.4 h GPU; expected about 9 h** |

RAM target ≤ 5 GB (Willett cache about 0.75 GB; no data-loader processes; 2 CPU threads). One GPU job. Checkpoint at each val (every 100 steps, about 40 s) and every 4 min; exact resume (tested on CPU: straight run == paused + resumed run, weights and val log). `pause` / `stop` file. `DONE` file at the end.

## Licence and rules
- Willett data: CC0. R-arm weights are clean-track. T, E and S weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only; every run folder has `licence.json`.
- No weights, signals or per-sentence outputs are committed. The repo gets this plan, the code, `results/selection.json` and `results/summary.json` (aggregates only), and `results.md`.
- Code: our own (Apache-2.0).

## Rerun
| Step | Command (repo root) |
|---|---|
| Unit tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q experiments/2026-11-20-p15-33-low-data-recipe/test_p33.py` |
| Full run (detached, resumes) | `.venv\Scripts\python.exe experiments\2026-11-20-p15-33-low-data-recipe\launch.py` |
| Check | `Get-Content C:\Users\zhang\bci-data\derived\p15-33\run.log -Tail 5`; `Test-Path C:\Users\zhang\bci-data\derived\p15-33\DONE` |
| Stop (saves latest.pt) | `New-Item C:\Users\zhang\bci-data\derived\p15-33\stop` |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-20-p15-33-low-data-recipe\p33.py summary` |

## Amendment 1 (2026-11-19 22:50, before any search result was read)
- **What:** stretched training batches (strong augmentation, candidates A and C) are post-padded to a multiple of 128 frames (`pad_time` in `p33.py`).
- **Why:** performance only. The first launch ran at about 1.26 s/step on candidate A (probe: 0.39 s/step). Time stretch gives a new tensor length almost every step, and MIOpen tunes a new kernel for each new shape. The probe did not show this because its second pass reused the shapes of the first pass.
- **Effect on results:** none by design. The model is causal and CTC uses the true lengths, so padding after the last frame does not change any valid output (unit test `test_pad_time_keeps_valid_outputs`). The noise tensor has a different shape, so the random draws differ; the augmentation distribution is the same.
- **Handling:** the job was stopped with the `stop` file at step 238 of the first run (A / R-b30-s0). That run folder was deleted and the run restarts from step 0 with the fix. No val or test number was read before this amendment.
