---
title: F3 cross-body transfer at full data with a tuned random-init arm, clean and implant arms, and repeated deranged-label controls - pre-registration
type: experiment-plan
task: proposed P15-50 (frontier direction 3, HORIZONTAL; continues P15-08, P15-45, P15-46)
updated: 2026-11-23
---

# F3 at full data: does a wrist-EMG trunk help an implant handwriting decoder more than a tuned random init? (pre-registration)

Written and committed **before** any run of this task. Nothing is launched by this commit (the local GPU runs P15-45). The P15-45 result is not known to this plan; this plan runs whatever it shows (see "Relation to P15-45").

## The confound this plan addresses
At full data (506 min of Willett T5 handwriting), the E1a arms gave test CER: E (EMG trunk) **0.395** (seeds 0 / 1: 0.360 / 0.431), T (text-only) 0.805, R (random init) 0.613 (**0.305** / 0.920). Our packaged `willett-hw` decoder **is** R seed 0 (P14-33), CER 0.305, better than both E seeds. R seed 1 diverged. So "E beats R" at full data may only mean "the E1a recipe is unstable from a random init". A fair test needs a random-init arm whose recipe is tuned as well as the pretrained arms' recipe.

## Hypotheses
- **H1 (primary).** With recipes tuned by the same val-only rule, the EMG-pretrained arm **E+** has a lower test CER than the tuned random-init arm **R+** at full data.
- **H2.** E+ has a lower test CER than the text-only arm T (same tuned recipe as E+).
- **H3 (clean track).** A trunk pretrained on KT-sEMG (CC BY 4.0) beats R+.
- **H4 (implant reference).** A trunk pretrained on T15 intracortical speech (CC0) beats R+; and how it compares with E+ (cross-person + same modality vs cross-person + cross-modality).

## Data and licence
| data | licence | use | **copy to a rented cloud machine?** |
|---|---|---|---|
| Willett 2021 handwriting, T5 (Dryad doi:10.5061/dryad.wh70rxwmv; local from Zenodo 4695519), cache `derived/p15-08/willett` (729 MB, read only) | CC0 1.0 | target | yes |
| emg2qwerty-derived P11-01 generic checkpoint `best.pt` (34 MB) | derived from CC BY-NC-SA 4.0 data: **research only** | E+ init | **allowed for non-commercial research as a private copy** (a rented machine is our own tool, not a distribution). Do not share it, do not publish it, delete it after the run. We prefer the local GPU for any run that needs this file |
| P15-08 T text-only checkpoint (synthetic renderings of emg2qwerty key sequences) | research only (emg2qwerty text) | T init | same as the row above |
| KT-sEMG (Nokia, Harvard Dataverse doi:10.7910/DVN/AV6XIR), raw 20 GB local | CC BY 4.0 | K trunk pretraining | yes (attribution) |
| T15 (B2T '25) derived features (9.9 GB) | CC0 1.0 | I trunk pretraining | yes |

## Splits (P15-08 E1a, unchanged)
Salt `fidetype-p15-08-2026-11-19`; test = the last block per session (**80 sentences**, never used for any choice); val = **106 sentences** (salted-hash blocks; used for recipe selection only); train = the whole pool ("all", 781 sentences, 506.0 min).

## Arms (same model for all: new stem Linear(192 -> 512) -> the P11-01 causal trunk (8 residual blocks, d 512) -> LayerNorm -> 98-token head; same parameter count)
| arm | init of trunk + head | pretraining signal | recipe | track |
|---|---|---|---|---|
| **R+** | random | none | tuned for R (grid below) | clean (CC0) |
| **E+** | P11-01 generic `best.pt`, step 30,000 | forearm sEMG (emg2qwerty, 100 users) | tuned for E (grid below) | research only |
| **T** | P15-08 T checkpoint | none (synthetic key renderings) | E+ recipe | research only |
| **K** | trunk pretrained on KT-sEMG with the P11-01 objective (needs P11-06, gap 86) | sEMG (Nokia keyboard) | E+ recipe | clean (CC BY 4.0) |
| **I** | trunk pretrained on T15 phoneme CTC (new 512-ch stem, 41-token head; the trunk is kept, the head is new for Willett) | intracortical speech, other person | E+ recipe | clean (CC0) |

The stem is always new. All weights train during adaptation (no freezing), as E1a. K and I pretraining: 30,000 steps each, P15-08 T-pretraining optimiser settings (LR 1e-3, warmup 2,000, cosine to 1e-6), last step. **K runs only if P11-06 has delivered a KT-sEMG trunk recipe before stage 2 starts; else K is reported "not run (dependency)".**

## Recipe tuning (stage 1; val only; test never read)
Grid (same for R and E): LR {2.5e-4, 5e-4, 1e-3} x steps {3,000, 6,000}; warmup 100, cosine to 1e-6, weight decay 0.01, dropout 0.1, E1a augmentation. Tuning seeds **10 and 11** (not used again). Rule: per arm, choose the cell with the lowest **mean val CER at the final step over the two tuning seeds**; a cell where any tuning seed has val CER > 0.90 is excluded (a diverged run). Ties: the smaller LR, then fewer steps. `selection.json` is committed before stage 2 reads any test number. 24 runs.

## Main runs (stage 2; seeds 0-4)
- Normal runs: R+, E+, T, I (and K) x seeds 0-4 = 20 (25).
- **Deranged-label runs (C2):** E+: **3 per seed** (derangement RNG `[seed, 77 + j]`, j = 0, 1, 2) = 15; R+, I (and K): 1 per seed = 15 (20).
- C1 (time-shuffled test input) for every normal run (P15-08 code).
- Code: P15-08 `run.py` `train_run` and `e1.py`, imported unchanged; the tuned LR / steps come from `selection.json`. Outputs only to `C:/Users/zhang/bci-data/derived/f3-full/`.

## Primary metric
Pooled test CER (total edits / reference characters over the 80 test sentences), greedy CTC, no LM, final step.

## Pass / fail rules (fixed now)
For a pair (A beats B): per seed s, d_s = CER_B − CER_A with a paired sentence bootstrap CI95 (10,000 resamples, seed 0).

| id | rule | pass if |
|---|---|---|
| **H1** (primary) E+ beats R+ | (a) CI95 of d_s entirely above 0 on **>= 4 of 5** seeds, **and** (b) the 5-seed mean of d_s > 0 with a one-sample t CI95 (4 df) above 0 | both |
| H2 E+ beats T | same rule | both |
| H3 K beats R+ | same rule | both |
| H4 I beats R+ | same rule; I vs E+ reported with the same statistics (descriptive) | both |
| **C2 (validity)** per arm that "wins" | E+: per seed, the mean of the 3 deranged CERs >= max(0.75, normal + 0.10) **and** at least 2 of the 3 runs individually meet it; R+, K, I: the single deranged run meets it | on **every** seed |
| C1 | time-shuffled test CER >= 0.85 for each normal run with CER <= 0.70 | every such run |
| V1 | the best arm has mean test CER <= 0.50 | gate for H1-H4 |

A win counts only if C1 and C2 pass for the winning arm on every seed.

## Outcomes and what each means
| outcome | condition | meaning |
|---|---|---|
| **A** | H1, H2 pass, C1 / C2 pass | A cross-body gain at full data: the EMG trunk helps an implant handwriting decoder more than a tuned random init and more than text-only pretraining. Narrow: one target person, research-only trunk |
| **A-clean** | H3 passes with valid controls | The same with a licence-clean trunk (KT-sEMG); a shippable result |
| **B** | H2 passes, H1 fails | "A better initialisation than text-only, **not** a cross-body gain over a tuned random init." F3 is recorded this way |
| **C** | R+ beats E+ (the H1 rule with A and B swapped passes) | Once R is tuned, EMG pretraining costs accuracy at full data |
| **D** | no rule passes either way | No difference beyond seed and sentence noise |
| **I-notes** | H4 result | If I beats E+, a same-modality (implant) trunk is the better source; the cross-modality part of F3 is weak. If E+ beats I, the body signal type matters less than the trunk training |
| **N** | V1 fails, or C2 fails for the arm that would win | No valid test (as minutes-scale F3) |

**Cross-person vs cross-modality.** Every pretrained arm comes from other people (emg2qwerty: 100 users; KT-sEMG: Nokia participants; T15: another implant user). E+ and K differ from the target in person **and** modality; I differs in person only. Every number in the write-up is reported with this note.

## Relation to P15-45
P15-45 (E1a recipe, C2 at "all", one deranged run per seed) runs now. Its outcome is cited next to this result. This plan does not reuse P15-45 runs (other recipe after tuning) and does not change if P15-45 fails or passes.

## Stop rules
- Stage 1 must finish and `selection.json` must be committed before stage 2.
- **GPU cap:** 45 h local or 15 h rented. Order of stage 2: E+ and R+ normal (seeds 0-4), E+ deranged, R+ deranged, T, I (+ deranged), K (+ deranged). At the cap the remaining runs are "not run (cap)". H1 needs the first four groups.
- No early stop on a value. No change of the grid, rules or arms after this commit.

## Compute estimate
Measured: a 3,000-step E1a run takes about 17 min on the local GPU (P15-08, 0.31-0.36 s / step); a 6,000-step run about 34 min.

| part | runs | local RX 7800 XT | rented A100 class |
|---|---|---|---|
| stage 1 grid | 24 (half at 6,000 steps) | about 10 h | about 3-4 h, **our estimate** |
| I trunk pretraining (30,000 steps on T15) | 1 | about 3 h | about 1 h |
| K trunk pretraining | 1 (after P11-06) | about 3 h | about 1 h |
| stage 2 normal | 25 | about 7-14 h (depends on the chosen steps) | about 2-4 h |
| stage 2 deranged | 35 | about 10-20 h | about 3-6 h |
| **total** | about 86 runs | **about 33-50 h** | **about 10-16 h** |

Recommended: run on the **local GPU** (the job is set up there, and two inputs are research-only files that we prefer not to copy). Rented cost if needed: about 10-16 GPU-h.

## Where it may honestly fail
- The most likely result (our estimate) is B or D: E only fixed an unstable random-init recipe.
- Val has 106 sentences; the grid choice can overfit val a little. The test set (80 sentences) is small; seed and sentence noise are large.
- C2 margins were near the threshold at minutes scale (P15-43); at full data they may also be near it.
- The I arm needs a stem for 512 channels at 20 ms bins and its head is new, while E+ keeps a pretrained character head: I starts with a handicap. Stated, not fixed.
- One target person (T5). The research-only weights (E+, T) cannot ship.

## Order and outputs
1. Commit this plan (this commit). 2. Commit the stage scripts (they import P15-08 `run.py` / `e1.py` unchanged) and CPU tests of the selection and pass rules. 3. Stage 1, commit `selection.json`. 4. Pretrain I (and K). 5. Stage 2. 6. `results/summary.json` (aggregates only), `results.md`. No weights, signals or texts in the repo; each run folder has `licence.json`.
