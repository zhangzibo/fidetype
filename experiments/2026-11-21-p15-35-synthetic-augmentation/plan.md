---
title: P15-35 E1 synthetic-sentence augmentation for the minutes-scale recipe - pre-registered plan
type: experiment-plan
task: P15-35
updated: 2026-11-21
---

# P15-35: Willett-style synthetic sentences for the 30-min recipe (plan, written before any result)

## Why
- [P15-33](../2026-11-20-p15-33-low-data-recipe/results.md) selected recipe A (full fine-tune, strong regularisation and augmentation). Arm E passed val-C2 by 0.002 only (deranged 0.871, needed 0.869).
- On test, C2 fails: deranged E at 30 min 0.847, needed max(0.75, 0.773 + 0.10) = 0.873.
- So at 30 min the decoder still holds a large label-prior part. With 47 training sentences, the model memorises the sentences.
- Willett et al. (2021) trained the handwriting decoder with synthetic sentences. They cut labelled character snippets out of the real data and spliced them into new sentences. This gives many new character orders from the same neural data. This task ([gap 139](../../wiki/questions/open-gaps.md)) tests that idea at the 30-min budget.
- Gap 140 (P15-36, budget-matched recipe for V1 and H1-H4) is **not** part of this task.

## Design in one table
| Step | What | Data used |
|---|---|---|
| 0. Text pool | Tatoeba English sentences, filtered and blocked (below) | public text only |
| 1. Search | 3 synthetic candidates x arms R and E, 30-min budget, seed 0; a label-deranged run where eligible | the 30-min train subset + **val block only** |
| 2. Select | fixed rule (below): pass val-C2 **with a margin of 0.03** and a length guard, then lowest val CER | val numbers only |
| 3. Test C2 | the selected candidate: test readout of the seed-0 normal and deranged runs of each passing arm | test block |
| 4. Seed 1 (descriptive) | the same arms at seed 1, normal + deranged, only if the GPU clock allows | test block |

One detached job runs all steps. No test-block number is computed before step 3. Step 2 is a fixed function of the val numbers.

## What stays the same as P15-33 (reused read-only)
| Item | Value |
|---|---|
| Code | P15-33 `p33.py` (recipe, model init, augmentation, readout `finish_run`) and P15-08 `e1.py` / `run.py` (store, eval, CER), imported read-only |
| Data | the P15-08 Willett cache `C:\Users\zhang\bci-data\derived\p15-08\willett\` (CC0): same sentences, splits, salt and per-session normalisation |
| Budget | 30 min, the same salted subset (seed 0: 47 sentences, 30.55 min; seed 1: its own P15-08 subset) |
| Arms | R (random init, clean track) and E (P11-01 EMG trunk). T and S are not run |
| Recipe | P15-33 recipe **A** unchanged: AdamW, LR 5e-4, warmup 100, cosine to 1e-6, weight decay 0.05, dropout 0.3, strong augmentation (offset 0.3, noise 0.5, 5 time masks ≤ 40 frames, channel dropout 0.2, time stretch U(0.8, 1.25)), clip 1.0, max 24,000 frames per batch, **2,000 steps**, val every 100 steps, readout at the final step |
| Label derangement (C2) | the P15-08 derangement (rng [seed, 77]) among the subset sentences |
| Readout | greedy CTC, no LM; pooled CER; time-shuffled CER (frames permuted in each sentence, seed 12345) |

All outputs go to `C:\Users\zhang\bci-data\derived\p15-35\`. The code refuses to write into the P15-08 or P15-33 folders.

## Synthetic sentences
### Source text
| Item | Value |
|---|---|
| Corpus | Tatoeba English export (`eng_sentences.tsv.bz2`, downloaded 2026-11-08, already used for the LM; see `src/fidetype/lm/corpora.md`) |
| Licence | CC BY 2.0 FR (Tatoeba default; some sentences CC0). Attribution: "Sentences from Tatoeba (https://tatoeba.org), by the Tatoeba contributors, CC BY 2.0 FR." |
| Normalisation | lower case; typographic apostrophes become `'`; runs of spaces become one space |
| Keep | only sentences that use the 31 Willett characters (a-z, space, `,` `.` `'` `?`), 10 to 90 characters long (Willett pool: median 44, 95th percentile 84), no duplicates |
| Blocklist | every Willett handwriting sentence (all 1,000 trials: train, val, test and excluded) and every T15 copy-task cue sentence (`t15_copyTask.pkl`, 1,718 trials) |
| Block rule | reject a sentence if it equals a blocked text, shares any word 5-gram with one, contains a blocked text of fewer than 5 words (≥ 15 characters), or (≥ 15 characters) is contained in a blocked text |
| Pool | shuffle (seed 20261121), keep the first 100,000 sentences that pass the block rule |
| Storage | `text_pool.txt` stays local in the derived folder. The repo gets only `results/text_pool_report.json` (counts and a SHA-256, no text) |

T15 test-split labels are hidden by the data owners, so the T15 block uses the copy-task cue sentences. No val or test sentence of Willett is ever a synthetic sentence.

### Character snippets (budget data only)
Each budget sentence is cut into one snippet per character of its **training** target. For a deranged run, the training target is the deranged text, so the snippets carry the deranged labels.

| Alignment | Rule |
|---|---|
| **uniform** | the writing frames [0, n_write) are cut into L equal parts (L = number of characters). No model |
| **forced** | forced alignment with a duration prior (segmental dynamic programming). Aligner = the P15-33 recipe-A model of the same arm, seed and labels at 30 min (trained on the 30-min subset only). Segment k of the writing frames gets the score: aligner non-blank log-posterior of character k at frame (segment end − 1 + lag) + log N(length; μ, (0.4 μ)²), μ = n_write / L, length in [0.25 μ, 3 μ]. The best total score wins. Lag = median over the budget sentences of (frame of the last character on the plain CTC Viterbi path − n_write), clipped to [0, 100]. A causal model emits a character after its end; the lag corrects this |

- Aligner weights: `p15-33/search/A/{R-b30-s0, E-b30-s0, E-b30-s0-labelshuf}/final.pt` and `p15-33/grid/{R,E}-b30-s1/final.pt` (read-only). A missing aligner (R deranged, seed-1 deranged) is trained here with the P15-33 code and recipe A on the same subset and labels.
- The aligner sees only the budget sentences (its own training data). It never sees val or test labels.
- The library is built once per (alignment, arm, seed, labels) and saved, so a resumed run uses the same snippets.
- Snippets are z-scored with their own session's statistics. The post-writing frames (the TAIL, up to 100 frames) of each budget sentence form a separate "tail" list.

### Rendering a synthetic sentence
1. Draw a text from the pool (only texts whose characters all have snippets).
2. For each character, draw one snippet of that character at random (any budget sentence, any session).
3. Append one random tail, cut to 100 frames.
4. Pick a random budget session s0. Map the z-scored frames into the raw space of s0 (z · std[s0] + mean[s0]). The model's own normalisation with s0 then gives back the z values.
5. The item then goes through the normal recipe-A path (time stretch, offset, noise, time masks, channel dropout).

### Mixing into batches
Each batch is first packed from the real budget sentences, as in P15-33. Then each slot becomes a synthetic sentence with probability `synth_frac`. If the padded batch passes 24,000 frames, synthetic items are dropped (longest first; at least 1 item stays). Batch k depends only on (seed, budget, label shuffle, k, candidate) and the saved library, so resume is exact.

## Candidates (step 1)
| Id | Alignment | synth_frac |
|---|---|---|
| **U50** | uniform | 0.5 |
| **F50** | forced (duration prior) | 0.5 |
| **F80** | forced (duration prior) | 0.8 |

Everything else is recipe A. Reference (P15-33, recipe A without synthetic sentences, same subset): E val 0.769, deranged 0.871; R val 0.882.

## Search protocol (step 1)
- Budget 30 min, seed 0. Arms R and E. One normal run per (candidate, arm).
- Readout at the final step on the val block: val CER and time-shuffled val CER.
- **Eligible** = normal final val CER < 0.80 (as P15-33). Only an eligible (candidate, arm) gets a deranged run with the same candidate. The deranged run uses deranged labels for the real sentences **and** a library built from the deranged labels (with its own deranged aligner for "forced").

## Selection rule (step 2, fixed)
1. A (candidate, arm) **passes val-C2 with margin** if all hold:
   - it is eligible;
   - deranged final val CER ≥ max(0.75, normal final val CER + 0.10) **+ 0.03** (the margin);
   - **length guard:** the median snippet length of the deranged library is within ±30 % of the normal library. This stops a pass that comes only from broken (very short or very long) deranged snippets.
2. A candidate passes if at least one arm passes.
3. Select the passing candidate with the lowest normal final val CER over its passing arms. Tie: the order U50, F50, F80.
4. If no candidate passes: **stop**. No test readout. `DONE` gets the note `no_recipe`. The gap stays open.

`selection.json` (val numbers only) is written before any test number and is copied to `results/selection.json`.

## Test C2 (step 3) and done-when
- For each arm that passed in step 2 under the selected candidate: test readout of its seed-0 normal run and its seed-0 deranged run (the search weights, final step; no new training).
- **C2 rule, exactly as P15-33 / P15-08:** the deranged test CER ≥ max(0.75, normal test CER + 0.10). No margin on test.
- **Gap 139 closes** if test C2 passes for at least one tested arm (the gap's done-when). With 2 arms, up to 2 tests are made; both are reported.
- Also reported (descriptive): time-shuffled test CER of the normal runs, test CER at the best-val step.

| Outcome | Reading |
|---|---|
| val pass with margin, test C2 pass | gap 139 closed: a 30-min recipe that passes C2 on test exists; P15-36 can build on it |
| val pass with margin, test C2 fail | partial: the val pass did not hold on the forward-in-time test block; gap stays open |
| no val pass | gap stays open; no test numbers; the next idea is named |

## Seed 1 (step 4, descriptive only)
- Only if the GPU clock is ≤ 7.0 h when step 4 starts: the selected candidate, the passing arms, seed 1, normal + deranged runs, trained here, test readout.
- Seed-1 numbers do not change the verdict. They show if a pass holds on a second seed and subset.

## Confounds and limits stated in advance
- 1 seed, 1 budget and 2 arms in the search; 3 candidates on 1 val block. The margin of 0.03 lowers the risk of a selection effect like P15-33 (pass by 0.002, test fail).
- The synthetic sentences change two things at once: more character orders (the intended effect) and a different item distribution (spliced snippets with boundary jumps). The search does not split these effects.
- The forced aligner is a weak model (val CER about 0.77). Its boundaries are noisy; the duration prior pulls them toward uniform.
- A deranged library is built with the deranged labels and (for "forced") the deranged aligner. This is the fair control: the whole pipeline sees wrong labels. The length guard catches the one failure mode where this control is unfair (broken snippet lengths).
- Disclosure: a GPU smoke run (30 steps per candidate, no val or test readout) was made before this plan to check code and speed. It printed the library statistics of the E seed-0 libraries (forced normal: lag 26, median snippet 87 frames; forced deranged: lag 0, median 64; uniform: median 85). No CER was computed. The first forced rule (cut at the CTC Viterbi emission frames) gave deranged snippets with a median of 1 frame; the duration prior and the length guard were added for this reason, before any CER.
- Same confounds as P15-08: cross-person and cross-modality cannot be separated; no LM.

## Compute budget and GPU cap
Measured in the smoke run (RX 7800 XT, ROCm 7.2.1 torch venv `C:\venvs\fidetype-rocm`): 0.31-0.40 s/step on the 30-min subset with synthetic items. Val eval adds about 1 min per 2,000-step run.

| Part | Runs | Estimate |
|---|---|---|
| Search (worst case: all 6 eligible -> 12 runs of 2,000 steps) | 6-12 | 1.4-2.8 h |
| R deranged aligner (only if R is eligible under F50 or F80) | 0-1 | ≤ 0.25 h |
| Test readout | 2-4 readouts | ≤ 0.1 h |
| Seed 1 (descriptive): 2-4 runs + 1-2 deranged aligners | 3-6 | 0.7-1.4 h |
| **Total** | | **about 2-4.5 h; hard cap 9.0 h** |

- **GPU cap: 9.0 h** of job wall time (sum over launches; `gpu_clock.json`). At the cap, the job saves `latest.pt`, writes the summary of what exists, and writes `DONE` with the note `cap`. The target stays ≤ 10 h total for the task.
- One GPU job. No data-loader processes; 2 CPU threads; RAM target ≤ 4 GB.
- Checkpoint `latest.pt` at every val (every 100 steps, about 40 s) and every 4 min; exact resume from the latest checkpoint. `pause` / `stop` file: save and exit. `DONE` file at the end. The process keeps the machine awake (SetThreadExecutionState).

## Licence and rules
- Willett data: CC0. R-arm weights are clean-track. E weights derive from emg2qwerty (CC BY-NC-SA 4.0): research only; every run folder has `licence.json`.
- Tatoeba text: CC BY 2.0 FR; used for training only; never committed.
- No weights, signals, texts or per-sentence outputs are committed. The repo gets this plan, `config.json`, the code, the tests, `results/text_pool_report.json`, `results/selection.json`, `results/summary.json` (aggregates only) and `results.md`.
- Code: our own (Apache-2.0).

## Rerun
| Step | Command (repo root) |
|---|---|
| Unit tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-21-p15-35-synthetic-augmentation/test_p35.py` |
| Full run (detached, resumes) | `.venv\Scripts\python.exe experiments\2026-11-21-p15-35-synthetic-augmentation\launch.py` |
| Check | `Get-Content C:\Users\zhang\bci-data\derived\p15-35\run.log -Tail 5`; `Test-Path C:\Users\zhang\bci-data\derived\p15-35\DONE` |
| Stop (saves latest.pt) | `New-Item C:\Users\zhang\bci-data\derived\p15-35\stop` |
| Resume | delete the `stop` file, then run the launcher again |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-21-p15-35-synthetic-augmentation\p35.py summary` |
