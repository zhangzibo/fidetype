---
title: P15-50 F3 at full data with tuned arms and repeated deranged controls - results
type: experiment
task: P15-50 (gap 210)
updated: 2026-11-27
---

# P15-50: F3 at full data, tuned R+ / E+ arms (results)

Pre-registration: [plan.md](plan.md) (`29c1dc9`, before any run). Run wrapper: [f3.py](f3.py) and [config.json](config.json) (`88a3ab8`, before the launch). Stage-1 selection: [results/selection.json](results/selection.json) (`3bb55f0`, before stage 2 read any test number). Aggregates: [results/summary.json](results/summary.json). Weights, logs and per-sentence outputs stay local in `C:\Users\zhang\bci-data\derived\p15-50\`. The folder has no amendment. `config.json` records two details that the plan did not fix (the output folder name and the I-pretraining batch packing); both were set before any run.

## Summary
- **Outcome B** (pre-registered): "A better initialisation than text-only, **not** a cross-body gain over a tuned random init."
- H2 (E+ beats T) **passes**. H1 (E+ beats R+) **fails**: part (a) passes (4 of 5 seeds), part (b) fails (the t CI95 of the 5-seed mean is [-0.039, +0.957]).
- V1, C1 and C2 pass for the winning arm E+ on every seed.
- **3 of 5 R+ seeds and 4 of 5 I seeds did not train.** They did not diverge (no non-finite loss, no rise after learning). Their training loss stayed on a plateau from about step 200 to step 6,000. The plan has no rule that excludes such a seed in stage 2, so they count as they are. This R+ instability is the main reason why H1 fails (post-hoc, see below).
- Where R+ trained (seeds 0 and 3), R+ and E+ are close: d = -0.004 (CI95 includes 0) and +0.044 (CI95 above 0). This is descriptive only.
- **GPU use: 41.49 h** (cap 45 h). No run was cut by the cap. Every planned run finished. K is "not run (dependency)", as the plan says.

## Verdicts (pre-registered rules, recomputed independently)
All rule values below were recomputed from the per-run `result.json` files with separate code (own bootstrap and t interval). Every value matches `summary.json` exactly.

| Id | Claim | Result | Verdict |
|---|---|---|---|
| **V1** (gate) | best arm has mean test CER ≤ 0.50 | E+ mean **0.164** | **pass** |
| **H1** (primary) | E+ beats R+ | (a) CI95 above 0 on **4 of 5** seeds: pass. (b) mean d **+0.459**, t CI95 **[-0.039, +0.957]**: fail | **fail** |
| **H2** | E+ beats T | (a) 5 of 5. (b) mean d **+0.599**, t CI95 [+0.558, +0.640] | **pass** |
| H3 | K beats R+ | K not run (dependency: P11-06, gap 86) | not run |
| **H4** | I beats R+ | (a) 3 of 5. (b) mean d -0.116, t CI95 [-0.506, +0.273] | **fail** |
| H4 (descriptive) | E+ vs I | E+ better: 4 of 5 seeds CI above 0, mean d +0.575, t CI95 [+0.166, +0.985] | - |
| H1 swapped | R+ beats E+ (outcome C) | 0 of 5, mean d -0.459 | **fail** |
| H2 swapped | T beats E+ | 0 of 5 | **fail** |
| **C1** | time-shuffled test CER ≥ 0.85 for each normal run with CER ≤ 0.70 | 8 runs apply (E+ 5, R+ 2, I 1): all 0.899-0.927 | **pass** (T: no run applies) |
| **C2** E+ | per seed: mean of 3 deranged ≥ max(0.75, normal + 0.10), and ≥ 2 of 3 individually | 5 of 5 seeds, 15 of 15 runs individually | **pass** |
| C2 R+ | the single deranged run meets the need | seeds 0, 3 pass; 1, 2, 4 fail | fail (not the winner) |
| C2 I | same | seed 3 passes; 0, 1, 2, 4 fail | fail (not the winner) |

**Outcome logic** (plan table): H2 passes, H1 fails, E+ is valid (C1 and C2 on every seed) → **B**. No other label applies (A needs H1; C needs H1 swapped; D needs no pass). Confirmed.

## Stage 1 (recipe selection, val only)
Rule: per arm, lowest mean val CER at the final step over tuning seeds 10 and 11; a cell with any seed > 0.90 is excluded.

| Arm | Chosen cell | Mean val CER | Excluded cells |
|---|---|---|---|
| R+ | LR 5e-4, 6,000 steps | 0.171 | 4 of 6 (seed 10 > 0.90 in each) |
| E+ | LR 1e-3, 6,000 steps | 0.120 | 0 of 6 |

T and I use the E+ recipe (plan).

## Test CER per arm and seed (primary readout)
Test = last block of each Willett session: 80 sentences. Pooled CER, greedy CTC, no LM, final step. Train = "all" (781 sentences, 506.0 min).

| Arm | Seed 0 | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Mean | Seeds that trained (post-hoc) |
|---|---|---|---|---|---|---|---|
| **E+** (EMG trunk) | 0.184 | 0.162 | 0.165 | 0.157 | 0.151 | **0.164** | 5 of 5 |
| **R+** (random init) | 0.180 | *0.902* | *0.942* | 0.201 | *0.887* | 0.622 | 2 of 5 |
| **T** (text-only) | 0.744 | 0.738 | 0.764 | 0.772 | 0.796 | 0.763 | - (see post-hoc note 4) |
| **I** (T15 implant trunk) | *0.852* | *0.945* | *0.928* | 0.150 | *0.818* | 0.739 | 1 of 5 |
| K (KT-sEMG trunk) | - | - | - | - | - | not run (dependency) | - |

*Italic* = the run did not train (post-hoc label: training loss stayed on a plateau, final val CER ≥ 0.83).

### Per-seed differences for H1 (d = CER of R+ − CER of E+; bootstrap CI95 over sentences, 10,000 resamples)
| Seed | d | CI95 | CI above 0 |
|---|---|---|---|
| 0 | -0.004 | [-0.022, +0.013] | no |
| 1 | +0.740 | [+0.717, +0.762] | yes |
| 2 | +0.777 | [+0.757, +0.798] | yes |
| 3 | +0.044 | [+0.030, +0.059] | yes |
| 4 | +0.736 | [+0.715, +0.758] | yes |

## Controls
### C2 (label-deranged runs, final test CER)
| Arm, seed | Normal | Deranged runs | Need | Margin (mean − need) | Pass |
|---|---|---|---|---|---|
| E+ 0 | 0.184 | 0.765 / 0.778 / 0.770 | 0.750 | +0.021 | yes |
| E+ 1 | 0.162 | 0.766 / 0.764 / 0.771 | 0.750 | +0.017 | yes |
| E+ 2 | 0.165 | 0.769 / 0.784 / 0.794 | 0.750 | +0.032 | yes |
| E+ 3 | 0.157 | 0.767 / 0.752 / 0.822 | 0.750 | +0.030 | yes |
| E+ 4 | 0.151 | 0.776 / 0.784 / 0.792 | 0.750 | +0.034 | yes |
| R+ 0 / 1 / 2 / 3 / 4 | see table above | 0.915 / 0.927 / 0.863 / 0.950 / 0.945 | 0.750 / 1.002 / 1.042 / 0.750 / 0.987 | +0.165 / -0.075 / -0.179 / +0.200 / -0.041 | yes / no / no / yes / no |
| I 0 / 1 / 2 / 3 / 4 | see table above | 0.739 / 0.934 / 0.781 / 0.760 / 0.762 | 0.952 / 1.045 / 1.028 / 0.750 / 0.918 | -0.213 / -0.111 / -0.247 / +0.010 / -0.157 | no / no / no / yes / no |

A normal run that did not train cannot pass C2: its need is above 0.98. This is the rule working as written.

### C1 (time-shuffled test input)
E+ 0.910 / 0.903 / 0.927 / 0.927 / 0.899; R+ seed 0 0.904, seed 3 0.906; I seed 3 0.927. All ≥ 0.85.

## Run integrity
- 24 stage-1 runs, the I trunk pretraining (30,000 steps, 8,065 T15 train trials, 0 skipped steps) and all 45 stage-2 runs finished. Every stage-2 run has 6,000 steps and 0 skipped (non-finite) steps.
- The GPU clock was 40.92 h at the start of the last run and 41.49 h at the end. No run was cut by the 45 h cap.
- One planned pause: run E+ seed 2, deranged j = 1, stopped by the stop file at step 1,300 (2026-11-24 21:05) and resumed from its checkpoint at step 1,300 (22:20). Its result is in the normal range of the other deranged E+ runs.
- The pooled test CER recomputed from the per-sentence edit counts equals the stored value in every run.

## Post-hoc notes (NOT pre-registered; descriptive only, no decision)
These notes use the training logs and val curves. They do not change the outcome.

**1. The failed R+ and I runs did not train; they did not diverge.** Training loss (from `run.log`, mean over steps 4,000-6,000) and val CER:

| Run | Loss at step 100 | Loss, steps 4k-6k | Val CER at 1k / 3k / 6k | Mode |
|---|---|---|---|---|
| E+ seeds 0-4 | 3.6-3.8 | 0.3-0.4 | 0.36-0.92 / 0.17-0.20 / 0.12-0.14 | trained |
| R+ seed 0 | 44 | 0.3 | 1.00 / 0.20 / 0.14 | trained (late start) |
| R+ seed 3 | 88 | 0.5 | 1.00 / 0.29 / 0.18 | trained (late start) |
| R+ seeds 1, 4 | 77, 64 | 19.1, 19.6 | 0.94-0.97 / 0.93 / 0.90-0.91 | stuck at a high-loss plateau |
| R+ seed 2 | 99 | 2.7 | 0.99 / 0.95 / 0.94 | stuck at the label-prior level (loss like T) |
| I seed 3 | 107 | 0.3 | 0.96 / 0.18 / 0.12 | trained |
| I seeds 0, 4 | 115, 99 | 17.6, 18.8 | 0.94-0.97 / 0.88-0.93 / 0.83-0.86 | stuck at a high-loss plateau |
| I seeds 1, 2 | 111, 140 | 49.0, 44.7 | 0.96-0.98 / 0.95-0.96 / 0.94-0.96 | stuck at a higher plateau |

- No run has a non-finite loss (skipped = 0). No run learned and then got worse. So "diverged" is the wrong word. These runs **failed to start learning**.
- The arms with a pretrained head (E+, T) start at a loss of about 3.6. The arms with a new head (R+: all new; I: new head on a T15 trunk) start at a loss of 44-140. Every stuck run is in this second group. Our interpretation (not tested): the new, randomly initialised output layer plus the short warmup (100 steps) puts some seeds into a state they do not leave. A pretrained head avoids it.
- Stage 1 showed the same risk: tuning seed 10 of R ended with val CER > 0.90 in 4 of 6 cells (3 of them with a loss plateau of about 19-65). The chosen R+ cell trained on both tuning seeds (2 of 2), then on only 2 of 5 main seeds. Over the 7 runs of the chosen R+ recipe, 4 trained.

**2. R+ instability drives the E+ vs R+ result.** On the 3 stuck R+ seeds, d is about +0.74 to +0.78. On the 2 seeds where R+ trained, d is -0.004 (no difference) and +0.044. So:
- part (a) of H1 passes mainly because R+ failed to train on 3 seeds;
- part (b) fails because the 5 differences are bimodal (large spread);
- the data do not show that the EMG trunk gives a better final decoder than a random init **when the random init trains**. With 2 such seeds, they also do not show that it does not.
- What E+ shows reliably is **training stability**: 5 of 5 main seeds trained, and all 12 stage-1 E runs ended with val CER ≤ 0.90 (none stayed on a high-loss plateau). Stability is a real practical value, but it is not the pre-registered H1 claim.

**3. I trains to the E+ level when it trains.** I seed 3 (0.150) vs E+ seed 3 (0.157): d = +0.007 for I, CI95 includes 0. With 1 of 5 seeds this is an anecdote. The H4 seeds where "I beats R+" with a CI above 0 (seeds 2 and 4) compare two runs that both did not train. They carry no information about transfer.

**4. T is a weak comparison arm at full data.** T test CER is 0.74-0.80 and its val CER never goes below 0.72. Its time-shuffled CER (0.79-0.83) is only 0.03-0.07 above its normal CER, so T uses the input signal very little. Its training loss stays near 2.8, the same level as the stuck R+ seed 2. So the large H2 margin (+0.60) means "E+ trains on this data and T does not" more than "EMG pretraining beats text pretraining". In P15-08 (E1a recipe) T at full data was 0.805, so this is not new.

**5. The tuned recipe narrows the C2 margins.** The deranged E+ runs reach 0.752-0.822, with margins +0.017 to +0.034 over the need of 0.75. In P15-45 (E1a recipe, LR and steps not tuned) the deranged E runs were 0.866-0.979 (margins +0.116 to +0.229). The deranged runs here end with a training loss of about 2.1-2.4, below the T level (about 2.8). Our interpretation: the longer, faster recipe lets a deranged run fit more of the label prior. C2 still passes as written on all 15 runs. Future plans that use this recipe should keep repeated deranged runs.

**6. Three of the five R+ deranged runs (seeds 0, 3 and 4) also stayed on a high-loss plateau** (loss 133-147 at steps 4k-6k). A C2 pass on R+ seeds 0 and 3 is partly because the deranged run did not train, not only because labels were wrong. This has no effect on the outcome (R+ is not the winner).

**7. Full-data accuracy moved a lot with tuning.** E at "all": 0.381 (E1a recipe, 5 seeds, P15-08 + P15-45) → 0.164 (tuned, 5 seeds). R seed 0: 0.305 (E1a recipe; this is the packaged `willett-hw` decoder) → 0.180 (tuned). Different recipes, so this is a recipe effect, not a transfer effect.

## What this means for F3 ("any body signal")
- **Pre-registered reading (outcome B):** at full data (506 min of one implant user's handwriting), the EMG-pretrained trunk is a better initialisation than the text-only trunk. It is **not** shown to be a cross-body gain over a tuned random init.
- **This agrees with the literature check of 2026-11-24** ([novelty check](../../wiki/questions/novelty-check-2026-11.md)): cross-person transfer of intracortical decoders helps mainly when the target has little data ([Levin et al. 2026](../../wiki/sources/levin-cross-brain-transfer.md): gains below 200 target sentences; [NDT3](../../wiki/sources/ndt3.md): gains below about 1.5 h). Here the target has 781 sentences. A full-data accuracy gain was not expected, and we did not find one where R+ trained.
- **Cross-person vs cross-modality.** Every pretrained arm comes from other people. E+ and T differ from the target (Willett T5) in person **and** modality; I differs in person only. So no result here separates a cross-modality effect from a cross-person effect.
- **No novelty claim.** This result is not a "first cross-person transfer" or a "first cross-modality transfer". Cross-person transfer of intracortical text decoders is published (Levin et al. 2026).
- **Licence.** E+ and T use research-only weights (derived from emg2qwerty, CC BY-NC-SA 4.0). They cannot ship. R+ and I are on the clean track (CC0 data).
- **Next:** the small-data test [P15-54](../2026-11-25-f3-small-data-falcon/README.md) (FALCON H2 few-shot, per-session input layers, arms E, I, M vs R from scratch). That is the regime where transfer is expected to help. The new-head instability in note 1 is relevant to its R and I arms.

## Where this can mislead
- One target person (T5), one test split of 80 sentences. Seed noise is larger than sentence noise here.
- Only 2 trained R+ seeds and 1 trained I seed. Any statement about "R+ when it trains" or "I when it trains" is anecdotal.
- The "trained / stuck" labels in the post-hoc notes were made after the results were known. They are not a rule.
