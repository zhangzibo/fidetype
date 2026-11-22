---
title: P15-36 E1 budget-matched recipe so that V1 and H1-H4 are valid - pre-registered plan
type: experiment-plan
task: P15-36
updated: 2026-11-21
---

# P15-36: a budget-matched recipe for E1 (plan, written before any result of this task)

## Why
- Gap 140 ([P15-36](../../wiki/questions/roadmap-standard.md#p15-36-e1-budget-matched-recipe-so-that-v1-and-h1-h4-are-valid)). Done when: a pre-registered budget-matched recipe rule, fixed before any test number, gives **V1 pass** and **test C2 pass**; then H1-H4 of E1a are evaluated under it (same splits, 2 seeds).
- E1a ([P15-08 plan](../2026-11-19-p15-08-e1-cross-body/plan.md)): one recipe for all budgets. V1 passes (E at "all" 0.395), but C2 fails at 30 min. So at minutes scale the E1a decoders mostly output the label prior.
- P15-33 ([results](../2026-11-20-p15-33-low-data-recipe/results.md)): one recipe (A) for all budgets. A over-regularises at full data (E 0.713, R 0.976 at "all"). V1 fails, H1-H4 are inconclusive, test C2 fails.
- P15-35b ([results](../2026-11-21-p15-35b-synthetic-on-top/results.md), `e9699a7`): **F-R20** (recipe A, forced cut, 20 % of batch items replaced by synthetic sentences, 4,000 steps) passed val-C2 with margin (deranged 0.897 vs 0.875) and test C2 (0.877 vs 0.847; normal 0.747). Arm E, 30 min, seed 0 only.
- So no single recipe works at every budget. This task fixes **one rule that picks the recipe per budget from val numbers only**, runs the missing minutes-scale runs, and reads V1, H1-H4, C1 and C2 under that rule.

## Design in one table
| Item | Value |
|---|---|
| Data, splits, budgets, seeds | P15-08 E1a exactly: Willett cache (CC0), salt `fidetype-p15-08-2026-11-19`, test = last block per session (80 sentences), val = 106 sentences, budgets 3, 10, 30, 100 min and all, seeds 0 and 1 (nested budget subsets) |
| Arms | R (random), T (text-only), E (EMG, P11-01), S (E weights shuffled within tensors) - as E1a |
| Candidate recipes | **E1a** (P15-08 recipe; existing runs), **A** (P15-33 recipe A; existing grid runs), **F-R20** (new runs at 3, 10, 30 min) |
| Readout | greedy CTC, no LM, final step; pooled CER (total edits / total reference characters) |
| Hypotheses and controls | V1, H1-H4, C1, C2 and the "beats" rule of E1a, unchanged (P15-08 `run.py` `verdict`, P15-33 `config.json` rules) |

## Candidate recipes
| Id | Recipe | Steps 3 / 10 / 30 / 100 / all | Runs here |
|---|---|---|---|
| **E1a** | P15-08: AdamW LR 5e-4, wd 0.01, dropout 0.1, base augmentation | 500 / 800 / 1,200 / 2,000 / 3,000 | none (read-only: `derived/p15-08/runs/`) |
| **A** | P15-33 recipe A: wd 0.05, dropout 0.3, strong augmentation (incl. time stretch, channel drop) | 600 / 1,000 / 2,000 / 2,000 / 3,000 | none (read-only: `derived/p15-33/grid/`) |
| **F-R20** | recipe A + P15-35b batch rule "replace": each real batch slot becomes a synthetic sentence with p = 0.2 (forced cut with duration prior; aligner = the P15-33 recipe-A run of the **same arm, budget, seed**; attempt-1 text pool) | **1,200 / 2,000 / 4,000** / - / - | 23 new runs (4 arms x 3 budgets x 2 seeds, minus E-b30-s0, reused from P15-35b) |

**F-R20 steps rule.** P15-35b used 2 x the recipe-A steps at 30 min (4,000 vs 2,000). The same factor 2 sets the steps at 3 min (1,200) and 10 min (2,000). Warmup 100, cosine to 1e-6 over the total. F-R20 is not run at 100 min and "all" (compute; see "Limits"). The batch RNG uses the P15-35b candidate code 3524 and the budget code, so the reused E-b30-s0 run is the same run that this code would train.

F-R20 libraries: one forced-cut library per (arm, budget, seed), built from the budget subset with that run's aligner. Texts with a character that the library does not cover are not used (P15-35 rule). The number of usable texts is logged and reported.

## The budget-matched recipe rule (val only)
For each budget b in {3, 10, 30, 100, all}:
1. **Candidates at b:** E1a and A at every budget; F-R20 at 3, 10 and 30 min.
2. **Admissible at 30 min only:** the candidate's arm-E, seed-0 runs pass **val-C2 with margin** (P15-35b rule): deranged final val CER ≥ max(0.75, normal final val CER + 0.10) + 0.03. For F-R20 the length guard (median snippet ratio within ±30 %) must also hold; E1a and A have no library, so the guard does not apply. The deranged runs exist: E1a `p15-08/runs/E-b30-s0-labelshuf`, A `p15-33/grid/E-b30-s0-labelshuf`, F-R20 `p15-35b/search/F-R20/E-b30-s0-labelshuf`. At 3, 10, 100 min and all there is no admissibility condition (C2 is defined at 30 min only).
3. **Choose** the admissible candidate with the **lowest mean final val CER over the 8 normal runs** (4 arms x 2 seeds) at b. Tie: the order F-R20, A, E1a.
4. If no candidate is admissible at 30 min: no test readout, `DONE` note `no_recipe`, gap 140 stays open.

The rule uses only val numbers. E1a val numbers are the final-step lines of `metrics.jsonl` (step = total steps; checked to exist for all 41 E1a runs). The rule treats all arms the same, so it cannot favour one arm in H1-H4. The chosen recipe per budget goes into `selection.json` before any new test number is computed.

## Hypotheses and controls (E1a definitions, unchanged)
"A beats B at budget b" = both (i) Δ = CER_B − CER_A (means over the 2 seeds) > seed spread s = max(|seed0 − seed1| of A, of B); (ii) the 95 % paired bootstrap interval of Δ (10,000 resamples of the 80 test sentences, per-sentence edits averaged over seeds, seed 0) has its lower end > 0. Each budget uses its chosen recipe for all four arms.

| Id | Claim | Pass if |
|---|---|---|
| **V1** (validity gate) | the target decoder is usable | best arm at "all" has mean test CER ≤ 0.50 |
| **H1** (primary, F3) | body-signal pretraining helps beyond text statistics | E beats T at ≥ 2 of {3, 10, 30} min ("partial" at exactly 1) |
| H2 | another body + user helps a new sensor | E beats R at ≥ 2 of {3, 10, 30} |
| H3 | text-only pretraining helps | T beats R at ≥ 2 of {3, 10, 30} |
| H4 | the gain is the learned function, not the weight scale | E beats S at ≥ 2 of {3, 10, 30} |
| **C1** | the decoders read the signal | every run at 30 min and all with test CER ≤ 0.70: frame-shuffled test CER ≥ 0.85 |
| **C2** | adaptation learns the signal-to-text map | arm E, 30 min, seed 0, deranged labels, chosen recipe at 30 min: test CER ≥ max(0.75, normal + 0.10) |
| Roadmap rule (secondary) | P15-08 rule as written | E beats T (clause (i) only) at ≥ 1 of {3, 10, 30, 100} |

If V1 fails, H1-H4 are **inconclusive** (E1a rule).

**Done-when reading (gap 140):**
| V1 | C2 | Reading |
|---|---|---|
| pass | pass | gap 140 **closed**; H1-H4 are valid and reported as they come out (a null result is a valid outcome) |
| pass | fail | partial; gap stays open; H1-H4 are reported but flagged "C2 fails" |
| fail | any | gap stays open; H1-H4 inconclusive |

## What is known before this plan (disclosure)
- The test numbers of every E1a and P15-33 grid run are already published (E1a and P15-33 results). The F-R20 E-b30-s0 test numbers (normal 0.747, deranged 0.877) are published (P15-35b). If the rule picks E1a at "all", V1 is known to pass (E1a: E 0.395). If it picks F-R20 at 30 min, C2 is known to pass (P15-35b). The rule itself uses val numbers only, and I did not read the E1a val CERs or the P15-33 grid val CERs at 3, 10, 100 min and all before writing it.
- What is **new**: the 23 F-R20 runs (all arms at 3, 10, 30 min, both seeds), the val-only choice per budget, and H1-H4 / C1 under the chosen recipes.
- No smoke run of this task's code was made before this plan. The code is unit-tested on CPU (synthetic data only) after the plan commit.

## Protocol and readout order
| Step | What | Data |
|---|---|---|
| 1. Train | 23 F-R20 normal runs (order: seed 0 then seed 1; budget 3, 10, 30; arm R, T, E, S). Val only (`do_test` off). Each builds its library first | budget subsets + val block |
| 2. Select | the rule above -> `selection.json` (val numbers only; also copied to `results/`) | val numbers |
| 3. Test readout | test CER of every new F-R20 run (same weights, final step; C1 at 30 min). Runs at a budget where F-R20 is not chosen are descriptive only | test block |
| 4. Verdict | V1, H1-H4, C1, C2, roadmap rule under the chosen recipes (E1a `verdict` function) -> `summary.json` | test numbers |
| 5. Seed-1 C2 (descriptive) | F-R20, arm E, 30 min, **seed 1**: the deranged aligner (recipe A, 2,000 steps, deranged labels) and the deranged F-R20 run, test readout; C2 rule as above. Starts only if the GPU clock is ≤ 6.5 h at that point | test block |
| 6. Summary | `summary.json` again with step 5; `DONE` | - |

No test-block number of any new run is computed before `selection.json` exists. Step 2 is a fixed function of val numbers. Step 5 is after the verdict and cannot change it.

Descriptive (no decision): per budget the mean val and test CER of every candidate recipe; the verdict under the fixed roadmap example (F-R20 ≤ 30 min, E1a at 100 min and all) if it differs from the chosen rule; test CER at the best-val step; learning curves.

## Limits and confounds stated in advance
- F-R20 has 1 seed of C2 evidence (P15-35b) with small margins (val 0.022, test 0.030). Step 5 adds a descriptive second seed if the clock allows.
- The F-R20 step factor 2 was validated at 30 min only. At 3 and 10 min the val-only rule can fall back to E1a or A if F-R20 is worse there.
- F-R20 is not run at 100 min and "all" (it would add about 12 GPU h). At those budgets the choice is between E1a and A only.
- C2 is checked at 30 min only (E1a definition). At 3 and 10 min the chosen recipe has no label-shuffle control.
- At 3 min (4-5 sentences) the forced-cut library may not cover every character; fewer usable texts. Reported.
- Recipe choice per budget means a learning curve that mixes recipes. H1-H4 compare arms within a budget, so they are not affected.
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM.

## Compute budget and GPU cap
P15-35b measured about 0.36 s/step for F-R20 including val (4,000 steps in about 24 min on the RX 7800 XT, ROCm 7.2.1 torch, venv `C:\venvs\fidetype-rocm`).

| Part | Steps | Estimate |
|---|---|---|
| 23 F-R20 runs | seed 0: 4 x (1,200 + 2,000) + 3 x 4,000 = 24,800; seed 1: 4 x (1,200 + 2,000 + 4,000) = 28,800; total 53,600 | about 5.4 h |
| 23 libraries (aligner log-probs, CPU cut) | - | about 0.2 h |
| Test readouts (23) | - | about 0.1 h |
| Seed-1 C2 (descriptive) | 2,000 (aligner) + 4,000 | about 0.6 h |
| **Total** | | **about 6.3 h; hard cap 8.0 h** |

- **GPU cap 8.0 h** of job wall time (sum over launches, `gpu_clock.json`; pauses not counted). At the cap the job saves `latest.pt`, writes a summary of what exists and writes `DONE` with the note `cap`. The order puts the verdict before the descriptive step 5.
- One GPU job. 2 CPU threads; no data-loader processes; RAM target ≤ 4 GB.
- `latest.pt` at every val (every 100 steps) and every 4 min; exact resume. A `pause` or `stop` file: save and exit. The process keeps the machine awake (SetThreadExecutionState).

## Licence and rules
- Willett data: CC0. E, S and T weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only; every run folder has `licence.json`.
- Tatoeba text (CC BY 2.0 FR, Tatoeba contributors): training only, read in place from `derived/p15-35/text_pool.txt` (SHA-256 checked); never committed.
- Code: our own (Apache-2.0). It imports P15-35b `p35b.py` / `p35_lib.py`, P15-33 `p33.py` and P15-08 `e1.py` / `run.py` read-only. All outputs go to `C:\Users\zhang\bci-data\derived\p15-36\`; the code refuses to write into the P15-08, P15-33, P15-35 or P15-35b folders.
- The repo gets this plan, `config.json`, the code, the tests, `results/selection.json`, `results/summary.json`, `results/text_pool_report.json` (aggregates only) and `results.md`. No weights, signals, texts or per-sentence outputs.

## Rerun
| Step | Command (repo root) |
|---|---|
| Unit tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-22-p15-36-budget-matched/test_run.py` |
| Full run (detached, resumes) | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-22-p15-36-budget-matched\launch.py` |
| Check | `Get-Content C:\Users\zhang\bci-data\derived\p15-36\run.log -Tail 5`; `Test-Path C:\Users\zhang\bci-data\derived\p15-36\DONE` |
| Stop (saves latest.pt) | `New-Item C:\Users\zhang\bci-data\derived\p15-36\stop` |
| Resume | delete the `stop` file, then run the launcher again |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-22-p15-36-budget-matched\run.py summary` |
