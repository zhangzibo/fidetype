---
title: P15-35b E1 synthetic sentences added on top of the real batch, longer schedule - pre-registered plan
type: experiment-plan
task: P15-35
updated: 2026-11-21
---

# P15-35b: synthetic sentences on top of recipe A, 4,000 steps (plan, written before any result of this attempt)

## Why
- Gap 139 ([P15-35](../../wiki/questions/roadmap-standard.md#p15-35-e1-synthetic-sentence-augmentation-for-the-minutes-scale-recipe-test-c2)) asks for a 30-min recipe with Willett-style synthetic sentences that passes val-C2 with a margin and then test C2.
- Attempt 1 ([plan](../2026-11-21-p15-35-synthetic-augmentation/plan.md), [results](../2026-11-21-p15-35-synthetic-augmentation/results.md), `218d889`, `6cf8466`) was a null result. Synthetic sentences **replaced** 50 % or 80 % of the batch items. No candidate was eligible (normal val CER < 0.80). Best: U50 / E 0.813; recipe A alone 0.769.
- In attempt 1 the synthetic runs still improved at step 2,000. Recipe A flattened by step 1,000. Each step had only about half (or a fifth) of the real sentences of recipe A. So the null result can be a schedule effect.
- This attempt keeps **all real sentences of each recipe-A batch** and **adds** synthetic sentences on top (one candidate uses a small replacement fraction, 0.2). The schedule is **4,000 steps**. The data budget is the same 30-min subset (47 sentences, 30.55 min).
- Gap 140 (P15-36) is **not** part of this task.

## What stays the same as attempt 1 (reused read-only)
| Item | Value |
|---|---|
| Code | `p35_lib.py` = verbatim copy of attempt-1 `p35.py` (`218d889`): text blocker, uniform cut, forced cut with duration prior, snippet library, rendering, aligner choice, **selection function** `select`. It imports P15-33 `p33.py` and P15-08 `e1.py` / `run.py` read-only. `p35b.py` adds only the batch rule, the step count, the stage order and the control |
| Data | P15-08 Willett cache (CC0); same splits, salt, per-session normalisation |
| Budget | 30 min, seed 0: the same 47 salted sentences (30.55 min) |
| Text pool | attempt-1 `text_pool.txt` (100,000 Tatoeba sentences, CC BY 2.0 FR, blocked against all Willett and T15 cue sentences), read in place, SHA-256 `2360dc05...63c9` checked at start. No new text is made |
| Snippet libraries | same rules (uniform cut; forced cut with duration prior and lag; aligners = P15-33 recipe-A weights of the same arm, seed and labels). Rebuilt in our folder with the same code and inputs (deterministic) |
| Rendering | attempt-1 rule: random text, one random snippet per character, one random tail (≤ 100 frames), random budget session s0 |
| Label derangement (C2) | P15-08 derangement (rng [seed, 77]); deranged runs use deranged labels for the real items **and** a library built from the deranged labels (with the deranged aligner for "forced") |
| Recipe | P15-33 recipe **A**: AdamW, LR 5e-4, warmup 100, cosine to 1e-6, weight decay 0.05, dropout 0.3, strong augmentation, clip 1.0, real part packed to max 24,000 frames, val every 100 steps, readout at the final step |
| Readout | greedy CTC, no LM; pooled CER; time-shuffled CER (seed 12345) |

## What changes
| Item | Attempt 1 | This attempt |
|---|---|---|
| Steps | 2,000 | **4,000** (warmup 100, cosine over 4,000) |
| Batch rule | each real slot becomes synthetic with p = 0.5 / 0.8 | **on top:** all real items of the P15-33 packing stay; add n = floor(x · n_real) + Bernoulli(frac. part) synthetic items (x = 0.5 or 1.0). One candidate: **replacement p = 0.2** |
| Frame cap per batch | 24,000 | on top: 24,000 · (1 + x); above the cap, synthetic items are dropped (longest first). Real items are never dropped. Replacement: 24,000 (attempt-1 rule) |
| Arms | R, E | **E only** (see "Limits") |
| Control | none | **A4K**: recipe A at 4,000 steps, no synthetic items (descriptive, never selectable) |
| GPU cap | 9.0 h | **8.0 h** |

## Candidates (arm E, 30 min, seed 0, 4,000 steps)
| Id | Cut | Batch rule | Real items per step | Synthetic items per step (expected) |
|---|---|---|---|---|
| **U+50** | uniform | on top, x = 0.5 | as recipe A (about 3.3) | about 1.6 |
| **F+50** | forced (duration prior) | on top, x = 0.5 | as recipe A | about 1.6 |
| **F+100** | forced | on top, x = 1.0 | as recipe A | about 3.3 |
| **F-R20** | forced | replacement, p = 0.2 | about 80 % of recipe A | about 0.7 |

Control (descriptive): **A4K** = recipe A, 4,000 steps, no synthetic items. It shows how much of any change comes from the longer schedule alone.

Three of four candidates use the forced cut, because the gap's done-when names "character times from a forced alignment". U+50 is the comparator (in attempt 1 uniform was better than forced). If only U+50 passes, the report says so and the orchestrator decides if the done-when is met.

## Protocol
| Step | What | Data |
|---|---|---|
| 1. Search | normal run of every candidate (4 runs); then a deranged run of every **eligible** candidate (0-4 runs) | 30-min subset + **val block only** |
| 2. Select | attempt-1 rule, unchanged (below) -> `selection.json` | val numbers only |
| 3. Test C2 | selected candidate: test readout of its seed-0 normal and deranged runs (same weights, final step) | test block |
| 4. Control | A4K normal run; its deranged run if A4K is eligible. Val only, no test readout | val block |
| 5. Seed 1 (descriptive) | selected candidate at seed 1, normal + deranged, test readout; only if the GPU clock is ≤ 6.0 h when step 5 starts | test block |

No test-block number is computed before step 3. Step 2 is a fixed function of the val numbers. The control runs after the selection, so it cannot change it.

## Selection rule (same as attempt 1 and P15-33 plus margin)
1. **Eligible** = normal final val CER < 0.80.
2. A candidate **passes val-C2 with margin** if: it is eligible; its deranged final val CER ≥ max(0.75, normal final val CER + 0.10) **+ 0.03**; and the **length guard** holds (median snippet length of the deranged library within ±30 % of the normal library).
3. Select the passing candidate with the lowest normal final val CER. Tie: the order U+50, F+50, F+100, F-R20.
4. No passing candidate: no test readout; the control still runs; `DONE` gets the note `no_recipe`; gap 139 stays open.

## Test C2 and done-when
- **C2 rule, as P15-33 / P15-08:** deranged test CER ≥ max(0.75, normal test CER + 0.10). No margin on test.
- **Gap 139 closes** if test C2 passes for the selected candidate (arm E).
- Descriptive: time-shuffled test CER of the normal run; test CER at the best-val step; control val numbers; seed-1 numbers.

| Outcome | Reading |
|---|---|
| val pass with margin, test C2 pass | gap 139 closed (if the selected candidate is U+50: closed with a note on the uniform cut) |
| val pass with margin, test C2 fail | partial; gap stays open |
| no val pass | gap stays open; no test numbers |

## Confounds and limits stated in advance
- Arm E only. Arm R was never near the eligibility line (P15-33 recipe A 0.882; attempt 1 0.939-0.961). Running R would double the GPU time for a near-certain "not eligible". The done-when needs one arm.
- 1 seed, 1 budget, 4 candidates on one val block. The margin 0.03 lowers the selection risk.
- On-top candidates see more items per step than recipe A (more gradient signal per step, larger batches). The control A4K separates the longer schedule from the synthetic items, but not the batch-size change.
- 4,000 steps on 47 sentences is about twice as many passes over the real data as recipe A. Recipe A itself may overfit more at 4,000 steps; A4K shows this.
- The forced aligner is weak (val CER about 0.77); the duration prior pulls it toward uniform.
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM.
- **Disclosure (smoke run before this plan):** a GPU code and speed check ran every candidate and the control for 30 and then 120 training steps (arm E, seed 0) in a separate folder, then deleted the run folders. No val or test readout and no CER were computed. It printed the library statistics (uniform: median snippet 85 frames; forced E-b30-s0: lag 26, median 87 — the same as attempt 1), the training loss, the speed and the peak GPU memory (U+50 5.4 GiB, F+100 7.1 GiB, F-R20 and A4K 4.4 GiB).

## Compute budget and GPU cap
Measured in the smoke run (RX 7800 XT, ROCm 7.2.1 torch venv `C:\venvs\fidetype-rocm`); steps 100-120 of the 120-step smoke run: U+50 0.70-0.77 s/step, F+50 0.63-0.82, F+100 1.14-1.58, F-R20 0.35-0.51, A4K 0.36-0.51 (attempt 1: 0.30-0.40). Val eval adds about 2 min per 4,000-step run.

| Part | Runs | Estimate |
|---|---|---|
| Search normal | 4 x 4,000 steps | U+50 ≈ 0.8 h, F+50 ≈ 0.8 h, F+100 ≈ 1.3-1.8 h, F-R20 ≈ 0.45 h: **3.4-3.9 h** |
| Search deranged (only eligible) | 0-4 | the same per candidate: 0-3.9 h (worst case: all 4 eligible) |
| Test readout | 0-2 readouts | ≤ 0.05 h |
| Control A4K (+ deranged if eligible) | 1-2 | 0.45-0.9 h |
| Seed 1 (descriptive; + 1 deranged aligner of 2,000 steps for a forced candidate) | 0-3 | ≤ 1.5 h |
| **Total** | | **expected about 4-5 h (few eligible); worst case about 8 h; hard cap 8.0 h** |

- **GPU cap: 8.0 h** of job wall time (sum over launches; `gpu_clock.json`). At the cap, the job saves `latest.pt`, writes the summary of what exists, and writes `DONE` with the note `cap`. The order (candidates, deranged, select, test, then control, then seed 1) makes sure the verdict comes first.
- One GPU job. No data-loader processes; 2 CPU threads; RAM target ≤ 3 GB.
- `latest.pt` at every val (every 100 steps) and every 4 min; exact resume. `pause` / `stop` file: save and exit. `DONE` file at the end. The process keeps the machine awake (SetThreadExecutionState).

## Licence and rules
- Willett data: CC0. E weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only; every run folder has `licence.json`.
- Tatoeba text: CC BY 2.0 FR ("Sentences from Tatoeba (https://tatoeba.org), by the Tatoeba contributors"); training only; never committed.
- No weights, signals, texts or per-sentence outputs are committed. The repo gets this plan, `config.json`, the code, the tests, `results/text_pool_report.json`, `results/selection.json`, `results/summary.json` (aggregates only) and `results.md`.
- Code: our own (Apache-2.0). All outputs go to `C:\Users\zhang\bci-data\derived\p15-35b\`; the code refuses to write into the P15-08, P15-33 or P15-35 folders.

## Rerun
| Step | Command (repo root) |
|---|---|
| Unit tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-21-p15-35b-synthetic-on-top/test_p35b.py` |
| Full run (detached, resumes) | `.venv\Scripts\python.exe experiments\2026-11-21-p15-35b-synthetic-on-top\launch.py` |
| Check | `Get-Content C:\Users\zhang\bci-data\derived\p15-35b\run.log -Tail 5`; `Test-Path C:\Users\zhang\bci-data\derived\p15-35b\DONE` |
| Stop (saves latest.pt) | `New-Item C:\Users\zhang\bci-data\derived\p15-35b\stop` |
| Resume | delete the `stop` file, then run the launcher again |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-21-p15-35b-synthetic-on-top\p35b.py summary` |
