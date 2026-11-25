---
title: F3 at small data - does a pretrained trunk from another body signal or another implant beat from-scratch training, with per-session input layers, in a FALCON H2-style few-shot protocol - pre-registration
type: experiment-plan
task: proposed (new roadmap item, frontier direction 3 "any body signal", small-data regime)
updated: 2026-11-24
---

# F3 at small data, FALCON H2-style protocol, per-session input layers (pre-registration)

Written and committed **before** any download of the data below, any training and any test-data analysis. This commit contains this file only. Nothing is launched by it. The GPU job queue at the time of writing: the full-data F3 control run, then the other queued jobs, then E2. This job starts **after E2** (see "Order").

## 1. Question
When the target has **little labelled data** (3 to 40 sentences per session), does a decoder trunk pretrained on

- another body signal: forearm surface EMG (arm **E**), or
- another implant and another task: intracortical speech of another person (arm **I**), or
- the same signal type in another species: monkey motor cortex (arm **M**),

give a lower character error rate (CER) on a new intracortical handwriting session than the same model trained from scratch (arm **R**)?

### Why this regime, and why now
| Evidence | What it says | Tag |
|---|---|---|
| Levin et al. 2026 (bioRxiv 10.64898/2026.01.12.699110, "All rights reserved", not stored in the repo) | Cross-brain transfer "improved decoding performance when training data from the target user was limited (< 200 sentences)". "Without trainable input layers, transfer failed and performed worse than training from scratch on target user data only." Electrode-permuted same-user data was as good as or better than other users' data | verified on the full text |
| FALCON benchmark (Karpowicz et al., NeurIPS 2024 D&B) | H2 = participant T5, attempted handwriting, 21 held-in sessions (7-45 min of calibration data each), 5 held-out sessions with 1-2 min (3 sentences) of calibration data; the baseline RNN has session-specific affine input layers | verified on the paper text and the challenge code |
| Chen, Li, Okubo 2026 (NeurIPS 2026 poster) | On FALCON H2, a frozen pooled GRU plus a meta-learned input aligner reaches 7.41 % WER with 3 calibration sentences per held-out session. A pooled GRU **without** session layers lowers zero-shot WER after LM decoding from 26.99 % to 12.10 % | abstract only |
| POSSM (Ryoo et al., NeurIPS 2025), Table 2 | On Willett T5 single-character classification, NHP-pretrained models beat from-scratch models: o-POSSM-GRU 97.37 ± 2.32 % vs POSSM-GRU 95.82 ± 3.41 %; o-POSSM-S4D 97.25 ± 2.88 % vs POSSM-S4D 92.11 ± 6.66 %. Pretraining used four NHP reaching datasets | verified on the full text |
| Our own minutes-scale results ([E1a](../2026-11-19-p15-08-e1-cross-body/results.md), [low-data recipe](../2026-11-20-p15-33-low-data-recipe/results.md), [synthetic sentences](../2026-11-21-p15-35-synthetic-augmentation/results.md), [budget-matched](../2026-11-22-p15-36-budget-matched/results.md), [more seeds](../2026-11-22-p15-41-more-seeds/results.md), [C2 range](../2026-11-23-p15-43-c2-30min/results.md)) | At 3-100 labelled minutes no recipe gave a valid test: the label-deranged control (C2) failed on some seed at every budget. The decoders learned mostly the label prior | our data |
| Our model code ([`e1.py`](../2026-11-19-p15-08-e1-cross-body/e1.py), class `XBody`) | **One shared stem** `Linear(192 -> 512)` for all sessions, after a per-session z-score. There is no trainable per-session layer | our code |

> **Our take:** the shared stem is the most likely design flaw behind the minutes-scale failures. Levin 2026 shows that this design makes transfer worse than training from scratch. This plan fixes the design first and then asks the F3 question in the regime where the literature predicts a gain.

## 2. Hypotheses
- **H1 (primary).** E beats R at ≥ 2 of the 3 core budgets {3, 12, 40} sentences per session.
- **H2.** I beats R at ≥ 2 of the 3 core budgets.
- **H3 (trunk vs output prior).** E0 (E trunk, **re-initialised** character head) beats R at the budgets where E beats R.
- **H4 (extended).** M beats R at ≥ 2 of the 3 core budgets.
- **H5 (extended, text prior).** E beats T (text-only pretrained trunk) at the budgets where E beats R.
- **U (extended, upper bound, descriptive).** P (pretrained on more sessions of the same user with permuted electrodes) beats R. Used only to scale the other gains.

"A beats B" is defined in section 8.

## 3. Data and licences (verified 2026-11-24 from the DANDI API, the Zenodo API and the sources)
| data | licence (verified) | size (verified) | use | stored where |
|---|---|---|---|---|
| FALCON H2, DANDI 000950, version 0.241029.1403 (T5 attempted handwriting, sessions 2022-05-18 to 2023-10-09) | **CC BY 4.0** (`spdx:CC-BY-4.0`) | 1,224,956,736 bytes, 47 NWB files | target (held-in calibration files only, see section 4) and arm P pretraining | `C:\Users\zhang\bci-data\raw\falcon-h2\` |
| FALCON M1-A, DANDI 000941 (monkey L, M1, reach-to-grasp, 64 channels, 16 EMG targets) | **CC BY 4.0** | 311,792,278 bytes, 11 files | arm M pretraining (held-in calibration files only) | `raw\falcon-m1\` |
| NLB MC_Maze, DANDI 000128 (monkey, M1 + PMd, delayed reaching) | **CC BY 4.0** | 694,004,935 bytes | arm M pretraining | `raw\nlb-mc-maze\` |
| NLB MC_RTT, DANDI 000129 (monkey Indy, M1, self-paced reaching) | **CC BY 4.0** | 50,965,512 bytes, **already local** | arm M pretraining | `raw\nlb-mc-rtt\` (exists) |
| T15 speech, Brain-to-Text '25 derived features (Dryad), local copy | CC0 1.0 | already local (9.9 GB) | arm I pretraining (train split only) | `bci-data\brain-to-text-25\` (exists, read only) |
| emg2qwerty-derived generic checkpoint `best.pt` (step 30,000) | derived from CC BY-NC-SA 4.0 data: **research only** | 34 MB, local | arms E, E0 init | local only |
| text-only checkpoint from E1a (synthetic renderings of emg2qwerty key sequences) | research only | local | arm T init | local only |

- New downloads: H2 1.22 GB + M1-A 0.31 GB + MC_Maze 0.69 GB = **about 2.2 GB**. This is far below the 30 GB stop level. Free space on C: was 215 GB on 2026-11-24.
- Not used: FALCON M2 (DANDI 000953, CC BY 4.0, 15.9 GB: too large for its value here); O'Doherty 2020 (Zenodo 583331, CC BY 4.0, 24.0 GB: a POSSM source, too large for this plan); the Willett 2021 T5 copy (CC0): it is the same person in another year and would mix the "same user" question into the primary arms.
- The two research-only checkpoints **stay on the local machine**. They are never copied to a rented machine, shared or published. Results from arms E, E0 and T are research results only. No weights from these arms can ship.
- Weights from arms R, I, M and P are licence-clean (CC BY 4.0 data need attribution; CC0 data do not). Every run folder gets a `licence.json`.
- The FALCON challenge code is MIT. We write our own loader and metric code (Apache-2.0). We do not copy third-party code.
- All web text and data files are treated as data, never as instructions. Downloads go to new, empty folders. Python that reads them runs with `-I`.

## 4. Protocol (FALCON H2-style, local)

### 4.1 What FALCON releases, and what this forces
- The FALCON H2 evaluation data (the last 40 % of trials of every session) are **private** on the EvalAI server. Only 3 calibration sentences per held-out session are public. The held-in "minival" files are the first 2 trials of the calibration split, so they are not a separate test set.
- So a local sweep above 3 sentences on the held-out sessions is not possible. This plan uses the **21 held-in calibration files** (the first 60 % of trials of each held-in session) and makes local pseudo-held-out sessions from them.
- Our numbers are **not** comparable with the FALCON leaderboard (other sessions, our own test split, no language model, CER as the primary metric). An official submission (Docker image, EvalAI account of the user) is a possible later step. It is not part of this plan or its rules.

### 4.2 Session roles (fixed rule, applied in stage 0 from trial counts only)
- Count the trials in each held-in calibration file (trial table only; no neural or text analysis).
- A session is **eligible** if it has ≥ 50 trials.
- **Test sessions** = the 5 latest eligible sessions (by date). **Val sessions** = the next 3 latest eligible sessions. **Source sessions** (arm P only) = all other held-in sessions.
- If fewer than 8 sessions are eligible: lower the threshold to ≥ 34 trials and drop the 40-sentence budget (core budgets become {3, 12, 24}). If fewer than 6 sessions are then eligible: use 3 test and 3 val sessions. If fewer than 6: stop and report (outcome "not run (data)").
- The 5 held-out sessions (2023) are not used.

### 4.3 Splits inside a test or val session
- Trials are in time order. **Train pool** = the first n trials (n = budget), as in FALCON, where the calibration sentences are the first 3 trials of a session. Budgets are nested.
- **Test** = the last 10 trials of the calibration file. These trials are never used for any choice, any training or any pretraining.
- Test set: 5 sessions x 10 = **50 sentences**. Val set: 3 sessions x 10 = 30 sentences.
- Budgets n (sentences per session): **core {3, 12, 40}**, extended {6, 24}. Totals over the 5 test sessions: 15 / 30 / 60 / 120 / 200 sentences. So the sweep covers the FALCON few-shot point (3 per session) and the < 200-sentence regime of Levin 2026.
- One run trains on all test sessions at once (n trials from each), with one input layer per session, as the FALCON baseline does.
- Stage 0 reports (counts only): how many test sentences have a text that also occurs in a train pool of the same run. These are not removed (FALCON protocol). Any pretraining trial (arm P) whose text equals a val or test sentence is removed.

## 5. Model (the same for every arm)

### 5.1 Input
- Neural features: threshold-crossing counts, binned at **10 ms** from the NWB spike times (100 frames/s, the E1a frame rate). If a file holds only 20 ms binned counts, each bin is repeated twice (hold). The same rule applies to every dataset and every arm. T15 features (20 ms) are held to 10 ms.
- Per-session z-score per channel, with mean and SD from the train-pool frames of that session only.
- Characters: the 31 H2 symbols map into the 98-token character vocabulary of the trunk (`>` -> space, `~` -> `.`). Stage 0 checks that every symbol maps; if one does not, stop and report.

### 5.2 Architecture
| Part | Exact form | Shared? | Init on the target |
|---|---|---|---|
| Per-session input layer A_s | dropout(0.1) -> `y = softsign(W_s x + b_s)`, W_s ∈ R^{C x C}, b_s ∈ R^C, C = channels (192 for H2) -> dropout(0.1); softsign(z) = z / (1 + abs(z)) (Levin 2026, eq. 1) | **one per session** | W_s = I, b_s = 0 |
| Input projection P_in | `Linear(C -> 512)` | one per dataset (channel space) | **new (random) for every arm** |
| Trunk | the causal trunk of E1a: 8 residual causal blocks, d 512, kernel 5, dilations 1, 2, 4, 8, 1, 2, 4, 8, ff_mult 2, dropout 0.1, receptive field 121 frames; then LayerNorm | shared | per arm (section 6) |
| Head | `Linear(512 -> 98)`, log-softmax, CTC (blank = the trunk's blank index) | shared | per arm (section 6) |

- Fully causal. No lookahead. No language model. Greedy CTC decoding.
- Parameters added per H2 session: 192 x 192 + 192 = 37,056.
- The same structure is used for every pretraining run in this plan (arms I, M, P): one A_s per source session, one P_in per source dataset, the shared trunk, and a task head. Arms E and T use fixed existing checkpoints, which were pretrained with a shared stem. This asymmetry is stated, not fixed.

## 6. Arms
| arm | trunk + head init | pretraining | track | core / extended |
|---|---|---|---|---|
| **R** | random (same init seed rule for all arms) | none | clean | core |
| **E** | emg2qwerty generic checkpoint, step 30,000: trunk, LayerNorm **and** 98-token head | forearm sEMG, 100 users (existing) | research only | core |
| **E0** | as E, but the head is **re-initialised** (same init as R) | as E | research only | core |
| **I** | T15 trunk + LayerNorm; head new | new: T15 phoneme CTC (41 tokens), per-session A_s (512 x 512) for each T15 train session, P_in 512 -> 512; 10,000 steps | clean (CC0) | core |
| **M** | NHP trunk + LayerNorm; head new | new: causal regression of behaviour (M1-A: 16 EMG channels; MC_Maze and MC_RTT: 2-D hand velocity; z-scored targets, MSE, one linear readout per dataset), per-session A_s, per-dataset P_in; 10,000 steps | clean (CC BY 4.0) | extended |
| **T** | text-only checkpoint (trunk + head) | synthetic key renderings (existing) | research only | extended |
| **P** | trunk + LayerNorm + head from P pretraining | new: character CTC on the H2 source sessions, channels permuted by one fixed random permutation (RNG seed 12345) for all source sessions (Levin 2026), per-session A_s; 10,000 steps | clean (CC BY 4.0) | extended |
| **X-R, X-E** | as R, E, but with the E1a shared stem (no A_s; one `Linear(192 -> 512)` for all sessions) | as R, E | as R, E | extended (design check) |

- Pretraining settings (I, M, P): AdamW, LR 1e-3, warmup 1,000, cosine to 1e-6, weight decay 0.01, clip 1.0, max 24,000 frames per batch, last step kept. One pretraining run per arm (seed 0).
- During target training **all weights train** (no freezing). No replay of source data (Levin 2026 used a 30 % source replay buffer; we do not, to keep the arms equal).
- With a full C x C input layer per session, a fixed channel permutation can be absorbed by A_s. So P measures "more data from the same user and the same latent structure". This is its purpose.

## 7. Recipe, selection and seeds

### 7.1 Target training recipe (all arms)
AdamW, weight decay 0.01, warmup 100, cosine to 1e-6, clip 1.0, max 24,000 frames per batch, E1a augmentation (noise SD 0.3, offset SD 0.2, 2 time masks of ≤ 20 frames). Steps by budget: **3: 500, 6: 650, 12: 800, 24: 1,100, 40: 1,500.** Final step is the reported model.

### 7.2 Stage 1: selection on val sessions only
- Grid: LR ∈ {3e-4, 1e-3}. Budget 12 per val session. Tuning seed **10** (not used again). Arms R, E, I (core) and M (extended) each get their own LR.
- Rule: per arm, choose the LR with the lower final-step val CER (30 val sentences). A run with val CER > 0.95 is excluded (diverged). Tie (difference < 0.005): the smaller LR. If both are excluded: LR 3e-4.
- E0 and T use the LR of E. P, X-R and X-E use the LR of R and E respectively.
- `selection.json` is committed **before** stage 2 reads any test number. No test sentence is decoded in stage 1.

### 7.3 Stage 2: main runs
- Seeds **0, 1, 2**. A seed changes the init of all new layers (A_s, P_in, new heads, R trunk), the batch order and the augmentation. The train pool of a budget is the same for every seed (the first n trials, as in FALCON).
- Normal runs (core): R, E, E0, I x budgets {3, 12, 40} x 3 seeds = **36 runs**.
- C2 label-deranged runs (core): E and I at {3, 12, 40} x 3 seeds = 18 runs; R at 40 x 3 seeds = 3 runs (tests whether the design fix alone reads the signal). **21 runs.**
- Derangement: over all train trials of the run (all sessions pooled), a derangement with RNG `[seed, 77]` (the E1a `derangement` function): no trial keeps its own text. If a C2 margin (section 8) is within ±0.03 on a seed, 2 more deranged runs are made for that seed (RNG `[seed, 78]`, `[seed, 79]`) and the 3-run rule applies.
- Extended normal runs: R, E, E0, I at {6, 24} (24 runs); M, T, P at {3, 12, 40} (27 runs); X-R, X-E at {3, 12, 40} (18 runs). Extended C2: M at {3, 12, 40} (9 runs); R at 12 (3 runs).
- C1 (time-shuffled test input) for every normal run: evaluation only.

## 8. Metric and pass rules (fixed now)
- **Primary metric:** pooled test CER over the 50 test sentences (total edit distance / total reference characters), greedy CTC, no LM, final step.
- Descriptive: FALCON-style per-session CER and WER (mean over sessions), the CER-vs-budget curve per arm, and the transfer ratio (CER_R − CER_X) / (CER_R − CER_P) where P beats R.

| id | rule | pass if |
|---|---|---|
| **win(A, B, b)** "A beats B at budget b" | per seed s, d_s = CER_B − CER_A with a paired sentence bootstrap CI95 (10,000 resamples, RNG seed 0). (a) d_s > 0 on **all 3** seeds, **and** (b) the CI95 of d_s is entirely above 0 on **≥ 2 of 3** seeds | (a) and (b) |
| **C2(A, b)** validity | per seed: deranged test CER ≥ max(0.75, normal + 0.10) (the rule of the full-data C2 run); with 3 deranged runs on a seed: the mean meets it **and** ≥ 2 of 3 runs meet it | on **every** seed |
| **C1(A, b)** validity | time-shuffled test CER ≥ 0.85 for each normal run with CER ≤ 0.70 | every such run |
| **valid win** | win(A, R, b) and C2(A, b) and C1(A, b) | all three |
| **H1** | valid win(E, R, b) at ≥ 2 of {3, 12, 40} | yes |
| **H2** | valid win(I, R, b) at ≥ 2 of {3, 12, 40} | yes |
| **H3** | at every budget b where H1 has a valid win: win(E0, R, b) | yes |
| **H4** | valid win(M, R, b) at ≥ 2 of {3, 12, 40} | yes |
| **H5** | at every budget b where H1 has a valid win: win(E, T, b) | yes |
| **neg(A)** negative transfer | win(R, A, b) at ≥ 2 of {3, 12, 40} | yes |
| **reads(R, 40)** design check (descriptive gate) | C2(R, 40) passes | yes |

If the budget rule of section 4.2 changes the core budgets, "{3, 12, 40}" means the new core set.

## 9. Outcomes and what each means
| outcome | condition | meaning |
|---|---|---|
| **A-trunk** | H1 and H3 pass (and H5, if T ran) | A wrist-EMG trunk transfers to implant handwriting at small data, beyond its character head and beyond the text prior. A narrow F3 result: one target person, a research-only trunk. Next step: a licence-clean EMG trunk |
| **A-head** | H1 passes, H3 fails | The gain comes from the pretrained output layer (character prior), not from the trunk. F3 trunk transfer is **not** shown |
| **A-text** | H1 passes, H5 fails | The gain is the text prior of the source, not the body signal |
| **I-only** | H2 passes, H1 fails | Same signal type, other person, other task (speech -> handwriting) transfers; the cross-modality part of F3 does not. Supports the "shared output space, signal-specific encoders" form of F3 |
| **M-only / M-also** | H4 passes | Same signal type, other species transfers (POSSM direction, now for sentence CTC) |
| **C** | neg(E) or neg(I) | Pretraining on that source costs accuracy at small data |
| **D** | no H rule passes, no neg rule passes, and C2 is valid for the arms tested | No transfer gain beyond seed and sentence noise at small data with per-session input layers. F3 "trunk transfer" is not supported in its own regime; the mechanism moves to a shared output space |
| **N** | C2 fails for the would-be winner at ≥ 2 core budgets, or no arm passes C2 at 40 | No valid test. The decoders still learn mostly the label prior at ≤ 200 sentences |

- reads(R, 40) is reported with every outcome. If it passes, the per-session input layer is enough for a from-scratch decoder to read the signal at 40 sentences per session (200 in total). This is the done-when of the open low-data-recipe gap (C2 passes at ≤ 100 labelled sentences on 3+ seeds) only if it also passes at 12 sentences per session (60 in total); that extra check uses the extended R deranged runs at 12; if they did not run, it is "not tested".
- X-R and X-E (extended) are descriptive: they show whether the per-session layer, and not the source, explains a change from the old minutes-scale results. Chen et al. 2026 found that a pooled model without session layers generalises better **zero-shot**; this plan tests the few-shot case only.
- **Cross-person vs cross-modality.** Every pretrained arm except P differs from the target in person: E in person and signal type, I in person and task, M in species and task. P differs in nothing but electrode order. Every number in the write-up carries this note.

## 10. Relation to the full-data F3 control run (open-gap row 210)
- That run tests F3 at 781 sentences (506 min, 8.4 h) on the Willett 2021 copy. Levin 2026 (< 200 sentences) and NDT3 (gains below about 1.5 h of target data, parity above; secondary source, not verified on the primary text) predict **no transfer gain** there. A full-data null is the expected result and **does not decide F3**. F3 is a small-data claim.
- This plan does not read, use or wait for any number of that run, and does not touch its derived folder `C:\Users\zhang\bci-data\derived\p15-50`. Its rules do not change with that result.
- The two runs use different data (Willett 2021 sessions vs FALCON H2 sessions, the same person T5) and different designs (shared stem vs per-session input layers). They are reported side by side, not pooled.

## 11. Compute and disk (local RX 7800 XT)
Measured base: a 3,000-step E1a run (10 ms bins, 24,000 frames per batch, same trunk) takes about 17 min, 0.31-0.36 s per step. This plan uses the same frame rate and batch size, so we use 0.33 s per step plus 10 % for evaluation.

| part | runs | steps | local GPU |
|---|---|---|---|
| stage 0: download, binning, session roles, smoke test | - | - | CPU, about 1 h; GPU smoke < 0.1 h |
| I pretraining (core) | 1 | 10,000 | about 1.0 h |
| stage 1 selection, R / E / I | 6 | 800 each | about 0.5 h |
| stage 2 normal, core | 36 | mean 933 | about 3.4 h |
| stage 2 C2, core | 21 (+ up to 6 conditional) | mean 933 | about 2.0 h (2.6 h max) |
| **core total** | | | **about 7 h** (max about 7.5 h) |
| extended: M pretraining + selection, P pretraining | 1 + 2 + 1 | | about 2.2 h |
| extended normal (R/E/E0/I at 6, 24; M, T, P; X-R, X-E) | 69 | | about 6.1 h |
| extended C2 (M; R at 12) | 12 | | about 1.1 h |
| **total** | | | **about 16-17 h** |

- The core is **larger than the 2-6 GPU h target** (about 7 h). The reason is the new I pretraining (about 1 h) and the C2 runs, which are needed for a valid test. Without I the core is about 5 h; we keep I in the core because H2 is part of the question.
- **GPU caps:** core 9 h; total 20 h. At a cap the remaining runs are "not run (cap)". Run order: stage 0; I pretraining; stage 1; then by seed (0, 1, 2): R, E, E0, I normal at 40, 12, 3; then C2 of E, I, R; then the extended part in the order of the table above.
- **Disk:** downloads about 2.2 GB; binned caches about 3 GB; final weights only (34 MB per run, about 160 runs) about 5.5 GB; resume checkpoints are overwritten. **Total below 12 GB.** No download exceeds 30 GB.
- Long-running job rules: one detached process, checkpoint every 4 min, resume from the latest checkpoint, log to a file, one GPU job at a time.

## 12. Stop rules and integrity
- Stage 0 must write `session_roles.json` (dates, trial counts, roles; no neural or text values) and commit it before stage 1.
- Stage 1 must commit `selection.json` before stage 2.
- No early stop on a value. No change of grid, budgets, arms, rules or test split after this commit. A needed fix is an amendment, committed before the affected stage and before any test number of that stage.
- If a licence on DANDI differs from section 3 at download time: stop that arm and report.
- Outputs only to `C:\Users\zhang\bci-data\derived\f3-small\`. The repo gets code, CPU tests, `session_roles.json`, `selection.json`, `results/summary.json` (aggregates only) and `results.md`. No weights, signals or sentence texts in the repo.

## 13. Where it may honestly fail
- 50 test sentences and 3 seeds give wide intervals. A real gain of 1-2 CER points may not pass.
- At 3 sentences per session the C2 control may fail for every arm, as at minutes scale before (outcome N).
- E and T come from checkpoints pretrained with a shared stem; I, M and P are pretrained with per-session layers. This favours I, M and P a little.
- One target person (T5), one task. The local protocol is not the FALCON leaderboard protocol.
- 10 ms binning from spike times may differ from the 20 ms features of FALCON; the hold rule makes the frame rate equal for all arms, but not the information.

## 14. Order
1. Commit this plan (this commit, alone). 2. Commit the runner and CPU tests (selection rule, pass rules, derangement, session-role rule, symbol map). 3. Stage 0 (downloads, `session_roles.json`). 4. I pretraining. 5. Stage 1, `selection.json`. 6. Stage 2 core. 7. Extended part. 8. `results/summary.json`, `results.md`.
