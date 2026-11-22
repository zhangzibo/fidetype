---
title: P15-41 More seeds of the F-R20 recipe at minutes scale - pre-registered plan
type: experiment-plan
task: P15-41
updated: 2026-11-22
---

# P15-41: more seeds of F-R20 at 3 / 10 / 30 min (plan, written before any result of this task)

## Why
- Gap 184 ([P15-41](../../wiki/questions/roadmap-standard.md#p15-41-more-seeds-of-the-f-r20-recipe-at-minutes-scale)). Done when: a pre-registered run with 3-5 seeds of F-R20 at 3 / 10 / 30 min re-evaluates H1 with the E1a rule.
- P15-36 ([results](../2026-11-22-p15-36-budget-matched/results.md), `01ee3b9`): arm E (EMG-pretrained) has the lowest mean test CER at every budget. But E beats T (text-only pretrained) by more than the seed spread only at 3 min. At 10 and 30 min the difference (0.007, 0.018) is smaller than the 2-seed spread (0.042, 0.044).
- Two seeds give a weak spread estimate. This task adds 3 seeds (2, 3, 4) of arms E and T, so H1 is tested on 5 seeds with a paired test across seeds.

## Design in one table
| Item | Value |
|---|---|
| Data, splits | P15-08 E1a exactly: Willett cache (CC0), salt `fidetype-p15-08-2026-11-19`, test = last block per session (80 sentences), val = 106 sentences |
| Budgets | 3, 10, 30 min (nested budget subsets per seed, `e1.budget_subset`) |
| New seeds | **2, 3, 4** (the old seeds 0, 1 come from P15-36, read-only) |
| Arms | **T** (text-only trunk) and **E** (EMG trunk, P11-01). R and S are **not** run (see "Arms R and S") |
| Recipe | **F-R20, unchanged** (P15-36 `config.json`): recipe A + "replace" batch rule, p = 0.2, forced cut with duration prior, steps 1,200 / 2,000 / 4,000, warmup 100, cosine to 1e-6, batch RNG code 3524 |
| Aligner | P15-36 rule, unchanged: the recipe-A run of the **same arm, budget, seed**. For seeds 2-4 these runs do not exist, so this task trains them with the P15-33 code (recipe A, 600 / 1,000 / 2,000 steps, val only) |
| Recipe choice | fixed: F-R20 at ≤ 30 min (P15-36 `selection.json`, val only). **No new selection.** No choice in this task reads a test number |
| Readout | greedy CTC, no LM, final step; pooled test CER (total edits / total reference characters); test readout right after each run |
| Code | `p41.py` imports P15-36 `p36.py` (and through it the P15-35b / P15-33 / P15-08 code) read-only. The P15-36 folder is not edited |

## Hypotheses and decision rules
For each budget b and seed s: d(b, s) = CER_T(b, s) − CER_E(b, s) (test CER, final step). A positive d means E is better.

**Paired test (pre-stated).** Over the n complete seeds at budget b (target n = 5: seeds 0-4): mean d̄, sample SD, and the two-sided 95 % paired t interval d̄ ± t(0.975, n − 1) · SD / √n.
**"E wins over T at b"** = d̄ > 0 **and** the lower end of the paired 95 % interval > 0.

| Id | Claim | Pass if |
|---|---|---|
| **H1** (primary, F3) | EMG pretraining helps beyond text pretraining at 10-30 min | E wins over T at **both** 10 and 30 min. `partial` = at exactly one; `fail` = at none |
| H1-3 (secondary) | the 3-min win of P15-36 holds on more seeds | E wins over T at 3 min |
| **C2** (validity, each new seed) | adaptation learns the signal-to-text map | arm E, **10 min**, seed s ∈ {2, 3, 4}, deranged labels (F-R20 with its own deranged recipe-A aligner): test CER ≥ max(0.75, normal + 0.10) |
| C1 (validity) | the decoders read the signal | every new run at 30 min with test CER ≤ 0.70: frame-shuffled test CER ≥ 0.85 |

- **Validity reading.** H1 is reported as it comes out. If C2 fails on any new seed, or C1 fails on any applicable run, H1 is flagged "control fails on seed k" and the gap stays open. A null result (`fail`) is a valid outcome.
- **Why C2 at 10 min.** The E1a C2 is at 30 min. A 30-min deranged run costs about 0.6 GPU h per seed (aligner 2,000 + F-R20 4,000 steps), so 3 of them do not fit the cap together with the normal runs. 10 min is a primary budget and costs about 0.3 h per seed. The pass threshold is the E1a formula, unchanged. P15-36 already has C2 at 30 min on seeds 0 and 1 (pass).

**Descriptive (no decision):**
- per seed and budget: test CER of E and T; the sign count (seeds with d > 0) and the exact one-sided sign-test p;
- the E1a "beats" rule on all complete seeds (Δ of the means > seed spread = max range over seeds of E and of T, and the 10,000-resample paired sentence bootstrap of Δ with per-sentence edits averaged over seeds has its lower end > 0), for comparison with P15-36;
- the same paired test on seeds 2-4 only (new data only);
- val CER of every new run, the recipe-A aligner runs, library statistics (aligner lag, usable texts), the val and test CER of each C2 run.

## What is known before this plan (disclosure)
- The test CER of E and T at 3 / 10 / 30 min on seeds 0 and 1 are published (P15-36 results). d (T − E) per seed: 3 min 0.081 / 0.077; 10 min 0.026 / −0.013; 30 min −0.008 / 0.044. These 6 values enter the primary test unchanged.
- What is **new**: 18 normal runs (E, T x 3 budgets x seeds 2-4) with their 18 aligners, 3 deranged C2 runs at 10 min with their 3 deranged aligners, and H1 on 5 seeds.
- No smoke run of this task's code was made before this plan. The code is unit-tested on CPU (synthetic data only) after the plan commit.

## Arms R and S
R and S are not run. Each arm costs about 1.1 GPU h per seed (aligner + F-R20 at 3 budgets), so 3 seeds of R and S add about 6.5 h. That does not fit the cap. H2-H4 are therefore **not** re-evaluated here; they stay at the P15-36 result (`partial`). The R / S aligners are also weak (P15-36: lag clipped at 99 frames in 6 of 12 libraries), which is gap 185 (P15-42). R and S belong with that fix.

## 100 min
F-R20 is **not** run at 100 min. One seed pair (E, T) would cost about 0.8 h (F-R20 4,000 steps per arm; the 100-min aligners exist only for seeds 0, 1), and the estimate below leaves no room for it under the cap.

## Protocol and order
One seed block per new seed, in the order seed 2, seed 3, seed 4. Inside a block:

| # | Run | Steps |
|---|---|---|
| 1-6 | for budget 3, 10, 30: for arm T, E: recipe-A aligner (val only) -> forced-cut library -> F-R20 run (val) -> test readout | aligner 600 / 1,000 / 2,000; F-R20 1,200 / 2,000 / 4,000 |
| 7 | C2: arm E, 10 min, deranged labels: deranged recipe-A aligner -> deranged library -> F-R20 deranged run -> test readout of the deranged run | 1,000 + 2,000 |

After the last block (or at the stop rule): `summary.json` with the verdict, then `DONE`.

**Seed count rule (fixed in advance).** A seed block starts only if the GPU clock is ≤ **5.4 h** at that point (cap 8.0 h minus the block estimate 2.6 h). If a block does not start, the job goes to the summary. A seed enters the paired test only if all 6 normal runs of that seed (E and T at 3, 10, 30 min) have a test readout. A seed whose C2 run is not finished still enters H1, and C2 for it is reported as "missing" (this counts as a control flag, as a fail does).

## Compute budget and GPU cap
Measured in P15-36 (RX 7800 XT, ROCm 7.2.1 torch, venv `C:\venvs\fidetype-rocm`): F-R20 about 6.3 / 12 / 23.5 min per run at 3 / 10 / 30 min (including val every 100 steps); recipe-A aligner about 0.37 s/step.

| Part | Steps | Estimate |
|---|---|---|
| Per seed: 6 aligners | 2 x 3,600 = 7,200 | about 0.75 h |
| Per seed: 6 F-R20 runs + test readouts | 2 x 7,200 = 14,400 | about 1.45 h |
| Per seed: C2 (aligner + run + readout) | 3,000 | about 0.32 h |
| **Per seed block** | 24,600 | **about 2.5 h** |
| **3 blocks** | 73,800 | **about 7.5 h** |

- **GPU cap 8.0 h** of job wall time (sum over launches, `gpu_clock.json`; pauses not counted). At the cap the job saves `latest.pt`, writes the summary of what exists and writes `DONE` with the note `cap`.
- One GPU job (no other GPU job runs at launch). 2 CPU threads; no data-loader processes.
- `latest.pt` at every val (every 100 steps) and every 4 min; exact resume after a stop. A `pause` or `stop` file: save and exit. The process keeps the machine awake while it runs.

## Limits and confounds stated in advance
- All seeds share one text trunk (T) and one EMG trunk (E). A seed changes the stem init, the budget subset (which sentences) and the batch order. So the seed spread does not include pretraining-run variance.
- 5 seeds give a t interval with 4 degrees of freedom (t = 2.776). A small true difference can stay inside the interval.
- The budget subsets of different seeds overlap (they come from one pool); seeds are not fully independent samples of data.
- C2 is at 10 min for the new seeds, not at 30 min (cost; see above).
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM.

## Licence and rules
- Willett data: CC0. E and T weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only; every run folder has `licence.json`.
- Tatoeba text (CC BY 2.0 FR, Tatoeba contributors): training only, read in place from `derived/p15-35/text_pool.txt` (SHA-256 checked); never committed.
- Code: our own (Apache-2.0). All outputs go to `C:\Users\zhang\bci-data\derived\p15-41\`; the code refuses to write into the P15-08, P15-33, P15-35, P15-35b or P15-36 folders. It reads the P15-36 and P15-35b test results of seeds 0 and 1 read-only.
- The repo gets this plan, `config.json`, the code, the tests, `results/summary.json` (aggregates only) and `results.md`. No weights, signals, texts or per-sentence outputs.

## Rerun
| Step | Command (repo root) |
|---|---|
| Unit tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-22-p15-41-more-seeds/test_p41.py` |
| Full run (detached, resumes) | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-22-p15-41-more-seeds\launch.py` |
| Check | `Get-Content C:\Users\zhang\bci-data\derived\p15-41\run.log -Tail 5`; `Test-Path C:\Users\zhang\bci-data\derived\p15-41\DONE` |
| Stop (saves latest.pt) | `New-Item C:\Users\zhang\bci-data\derived\p15-41\stop` |
| Resume | delete the `stop` file, then run the launcher again |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-22-p15-41-more-seeds\p41.py summary` |
