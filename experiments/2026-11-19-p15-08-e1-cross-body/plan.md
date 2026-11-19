---
title: P15-08 E1a cross-body pretraining -> minutes of data on a new sensor (Willett handwriting) - pre-registered plan
type: experiment-plan
task: P15-08
updated: 2026-11-19
---

# P15-08 E1a: does an EMG-pretrained shared character space let a new sensor start with minutes of data? (plan, written before any result)

## Why
- Pillar F3 of the [north star](../../wiki/questions/north-star.md#f3-cross-body-language-model-e1) asks: can one shared output space let a **new sensor or a new user** start with **minutes of data**? F3 is the only pillar with no result yet ([P15-08](../../wiki/questions/roadmap-standard.md#p15-08-e1-cross-body-pretraining-on-willett-handwriting)).
- We now have a trained causal EMG decoder with a character (key) head: [P11-01](../2026-11-16-p11-01-emg-decoder/results.md) (emg2qwerty, 100 users, best generic step 30,000). We have a CC0 implant dataset with a native character target: Willett handwriting (T5, 192 electrodes, 10 sessions).
- This is the **smallest honest first E1** that fits one GPU in about 10 h. It is part 1 (E1a) of P15-08. The other P15-08 arms come later (see [Deviations](#deviations-from-the-roadmap-item)).

## Question and design in one table
| Item | Value |
|---|---|
| Target (new sensor + new user) | Willett handwriting, intracortical, 192 channels, threshold crossings in 10 ms bins (100 frames/s). CC0 |
| Shared output space | The P11-01 98-token character head (emg2qwerty key vocabulary, CTC blank 0). Every Willett character (a-z, space, `,` `.` `'` `?`) is a token of this head |
| Model (all arms) | new stem Linear(192 -> 512) -> the P11-01 causal trunk (8 residual blocks, d 512, dilations 1,2,4,8 x2, receptive field 121 frames) -> LayerNorm -> 98-token head. Fully causal, no lookahead |
| Learning curve | labelled target minutes **3, 10, 30, 100, all (506 min)** |
| Seeds | 0 and 1. The seed sets the init of the stem (and of the trunk for arm R), the batch order **and the budget subset** |
| Readout | greedy CTC, **no language model** |

## Arms
| Arm | Trunk + head init | Body signal in pretraining | Licence of the checkpoint |
|---|---|---|---|
| **R** random | random | none | CC0 (Willett only) |
| **T** text-only | pretrained 30,000 steps on **synthetic** renderings of the emg2qwerty key sequences (no signal; see below) | none | research only (emg2qwerty text, CC BY-NC-SA 4.0) |
| **E** EMG | P11-01 generic `best.pt` (step 30,000, emg2qwerty, 100 users) | forearm sEMG (16+16 electrodes) | research only (CC BY-NC-SA 4.0) |
| **S** EMG shuffled weights (control) | E's weights, entries permuted at random **within each tensor** (seed 1000 + run seed) | none (function destroyed, scale kept) | research only |

The stem is always new (random, same seed for all arms of one seed). All weights train during adaptation (no freezing). All arms use the same fine-tune recipe, the same steps and the same augmentation.

**Text-only pretraining (arm T).** Input: 64-d synthetic frames at 100 frames/s, windows of 400 frames, batch 64. For each key press of a P11-01 generic-train session (same sessions, same key timings as E saw), we add a Hann bump (8-20 frames, delay 0-10 frames) of a fixed random unit embedding of the key, amplitude 3. Each key is dropped with p 0.25 or replaced by a random key with p 0.15; white noise SD 1.0 everywhere. CTC target = the true key sequence of the window. So T learns CTC alignment and English key statistics (it must use context to recover dropped keys), but no body signal. Same trunk, head, optimiser and step count (30,000) as E's selected checkpoint; LR 1e-3, warmup 2,000, cosine to 1e-6 over 30,000 steps. T uses its final step (no selection).

## Data and splits (Willett)
- Source: `Datasets/<session>/sentences.mat` of the Dryad / Zenodo deposit (local `C:\Users\zhang\bci-data\raw\willett-handwriting\extracted\`). 10 sessions with sentences (2019.06.03 has none). Read with `scipy.io.loadmat` (plain arrays), named variables only.
- One item = one sentence: frames from the go cue for `numTimeBinsPerSentence` bins, plus up to 100 frames after the end in the same block (no labels there; a causal model needs them because T5's characters come late).
- Target: `intendedText` with `>` -> space, `~` -> period, `#` (pause cue) removed. All characters are in the vocabulary.
- Dropped: the 33 sentences with `excludedSentences = 1` (dataset rule).
- **Test = the last block of each session** (north-star rule; a forward-in-time hold-out). **Val = one other block per session**, the block with the smallest SHA-256(salt | "val" | session | block); val is for diagnostics and the secondary readout only. **Train pool = all other blocks.** Salt `fidetype-p15-08-2026-11-19`.
- Budget subset of seed s: pool sentences sorted by SHA-256(salt | "budget" | s | session | trial); take the shortest prefix with at least B minutes of writing time (go cue to end). Budgets of one seed are nested; arms of one seed use the same subset (paired).
- Input normalisation: per session, mean and SD per channel over the frames of that session's **non-test** sentences (pool + val; no labels used; SD floor 0.1). The test block is never used for any statistic.

| Split | Sentences | Writing minutes | Characters |
|---|---|---|---|
| Test (last block x 10 sessions) | 80 | 54.6 | 3,448 |
| Val (1 block x 10 sessions) | 106 | 71.0 | 4,826 |
| Train pool | 781 | 506.0 | 33,993 |

| Budget | Seed 0: sentences / minutes | Seed 1: sentences / minutes |
|---|---|---|
| 3 min | 4 / 3.71 | 5 / 3.27 |
| 10 min | 14 / 10.84 | 16 / 10.38 |
| 30 min | 47 / 30.55 | 47 / 30.23 |
| 100 min | 147 / 100.70 | 160 / 100.43 |
| all | 781 / 506.0 | 781 / 506.0 |

(Counts from the split rule on the metadata only, before any model ran.)

## Fine-tune recipe (all arms, all budgets)
AdamW, LR 5e-4, warmup 100, cosine to 1e-6, weight decay 0.01, clip 1.0, dropout 0.1. Batches: random sentences of the budget subset until (n x longest) would pass 24,000 frames. Augmentation on normalised input: per-channel offset SD 0.2, white noise SD 0.3, 2 time masks of up to 20 frames. **Fixed steps per budget: 3 min 500, 10 min 800, 30 min 1,200, 100 min 2,000, all 3,000.** Val CER every 100 steps (best-val weights kept for the secondary readout).

## Metrics
- **Primary:** test CER = total edit distance / total reference characters over the 80 test sentences, greedy CTC, no LM, at the **final step** (no selection on target labels outside the budget). Per arm and budget: the mean of the two seeds.
- Secondary: (a) test CER at the best-val step (this uses the val block labels: about 71 extra labelled minutes, so it is not a "minutes of data" number); (b) the learning curve (CER vs minutes, log scale) per arm; (c) minutes to reach CER 0.60 (linear interpolation in log minutes; "not reached" if none); (d) the roadmap rule (below).

## Pass / fail rules (frozen)
"A beats B at budget b" means **both**: (i) Δ = CER_B − CER_A (means over seeds) is larger than the seed spread s = max(|seed0 − seed1| of A, |seed0 − seed1| of B); (ii) the 95 % paired bootstrap interval of Δ (10,000 resamples of the 80 test sentences, per-sentence edits averaged over seeds, ratio of sums, seed 0) has its lower end above 0.

| Id | Claim | Pass if | If it fails |
|---|---|---|---|
| **V1** (validity gate) | The target decoder is usable at all | the best arm at "all" has test CER ≤ 0.50 | H1-H4 are **inconclusive**, not null |
| **H1 (primary, F3)** | Body-signal pretraining helps beyond text statistics | E beats T at ≥ 2 of the budgets {3, 10, 30} min ("partial" at exactly 1) | F3 transfer is not shown at minutes scale |
| H2 | Pretraining on another body + user helps a new sensor at minutes scale | E beats R at ≥ 2 of {3, 10, 30} | - |
| H3 | Text-only pretraining helps | T beats R at ≥ 2 of {3, 10, 30} | - |
| H4 | The gain comes from the learned function, not the weight scale | E beats S at ≥ 2 of {3, 10, 30} | a gain of E over R is an init-scale effect |
| C1 (time-shuffle control) | The decoders read the signal | for every run at budgets 30 and all with test CER ≤ 0.70: CER on frame-shuffled test input (frames permuted within each sentence, seed 12345) ≥ 0.85 | the decoder can output text without the signal |
| C2 (label-shuffle control) | Adaptation learns the signal-to-text map | arm E, 30 min, seed 0, trained with the labels deranged among the subset sentences: test CER ≥ max(0.75, CER of the normal run + 0.10) | gains could come from the label prior alone |
| Roadmap rule (secondary) | P15-08 rule as written: "an EMG-pretrained arm beats text-only by more than the seed spread at ≤ 25 % data" | E beats T (clause (i) only) at ≥ 1 of {3, 10, 30, 100} min (all ≤ 20 % of the pool) | - |

**Reading of the outcomes:**
| H1 | H2 | H4 | Reading |
|---|---|---|---|
| pass | pass | pass | first evidence that a body-signal-pretrained shared character space transfers to a new sensor + new user at minutes scale (F3 part 2 "for text", narrowed to this pair) |
| fail | pass | - | the gain over random init comes from text / CTC pretraining, not from the body signal |
| fail | fail | - | no benefit of pretraining at minutes scale with this recipe (a valid null result) |
| pass | pass | fail | E helps, but a weight-scale effect explains it; no transfer claim |

A null result is a valid outcome. It is written up (P15-12).

## Confounds stated in advance
- **Cross-person and cross-modality are not separable here:** the target differs from the source in body site, sensor, task (handwriting vs typing) **and** person. A positive H1 shows transfer for this pair only; it does not say which factor matters (P15-09 must state it next to each result).
- Arm T is a model of "English key statistics + CTC alignment". It is one text-only control, not every possible one.
- One recipe for every arm (no per-arm tuning). A different LR could favour another arm. We report this as a limit, not as a fix after the results.
- No language model. The roadmap's same-LM rule needs a character LM (P11-07); it is a follow-up (new gap at the records commit).

## Compute budget
| Part | Steps | Estimate (0.31-0.34 s/step measured on random tensors, RX 7800 XT) |
|---|---|---|
| Willett cache (CPU) | - | about 5 min, about 1 GB on disk |
| T pretraining | 30,000 | about 2.6-3 h |
| 40 adaptation runs (4 arms x 5 budgets x 2 seeds) | 60,000 | about 6 h incl. val |
| C2 | 1,200 | about 7 min |
| Test eval + C1 + summary | - | about 15 min |
| **Total** | | **about 9-10 h GPU** (one stage; under the 12 h split limit) |

RAM target ≤ 14 GB (Willett cache about 1 GB in RAM; key sequences about 0.1 GB; no data-loader processes, 2 threads). One GPU job only. Checkpoint every 4 min and at each val; exact resume (batch k of a run depends only on (seed, budget, k)); `pause` / `stop` file. Logs and weights in `C:\Users\zhang\bci-data\derived\p15-08\` (never committed); `DONE` file at the end.

## Deviations from the roadmap item
| Roadmap P15-08 | E1a (this plan) | Why |
|---|---|---|
| 10 / 25 / 50 / 100 % data | 3, 10, 30, 100 min and all (0.6, 2, 6, 20, 100 %) | the F3 question is "minutes of data"; "all" anchors 100 % |
| arms random / text-only / emg2qwerty / KT-sEMG / optional T15 | R, T, E + control S | no KT-sEMG trunk exists yet (needs P11-06, gap 86); the T15 decoder has a phoneme head. P15-08 stays `in_progress` until the clean-track KT-sEMG arm runs |
| same character LM | no LM | no licence-clean character LM yet (P11-07, gap 87) |
| 20-45 GPU-h | about 10 GPU-h | smallest honest first step; E's pretraining is reused from P11-01 |

## Licence and rules
- Willett data: CC0. The Willett cache and the R-arm weights are clean-track.
- E, S and T checkpoints derive from emg2qwerty (CC BY-NC-SA 4.0): **research only**. Every checkpoint folder has a `licence.json`. No weights, signals or per-sentence outputs are committed. The commit holds code, this plan and aggregate numbers only.
- Code: our own (Apache-2.0); shared parts come from our P11-01 module.
- One GPU job at a time. Another agent's CPU job may run in parallel.

## Rerun
| Step | Command (repo root) |
|---|---|
| Unit tests (CPU) | `C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q experiments/2026-11-19-p15-08-e1-cross-body/test_e1.py` |
| Full run (detached) | `.venv\Scripts\python.exe experiments\2026-11-19-p15-08-e1-cross-body\launch.py` (resumes; finished runs are skipped) |
| Summary only | `C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-19-p15-08-e1-cross-body\run.py summary` |
