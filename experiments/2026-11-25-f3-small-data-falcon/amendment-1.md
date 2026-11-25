---
title: F3 at small data (FALCON H2) - pre-run plan amendment 1
type: experiment-plan-amendment
task: P15-54 (gap 219)
amends: plan.md (pre-registration 19ec6c5; plan.md itself is not changed)
updated: 2026-11-25
---

# Amendment 1 to the F3 small-data pre-registration (before any GPU run)

**Date:** 2026-11-25. **Status:** written and committed **before the run wrapper, before any training, before any neural-signal analysis and before any test sentence was decoded.** Data read so far: the DANDI metadata (licences, sizes, SHA-256 digests), the HDF5 structure of one file per dataset, and the **trial counts and trial durations** of the 21 H2 held-in calibration files (the same information that stage 0 reads). No neural value, no sentence text and no behaviour value was looked at.

**Scope.** plan.md stays frozen. This amendment records (a) one consequence of the pre-registered session-role rule, (b) one path change, and (c) the points where plan.md leaves a detail open, with the exact choice of the wrapper (`f3s.py`, `config.json`). No arm, seed, grid, budget rule, pass rule, threshold or stop rule changes. Where this amendment and plan.md disagree, the run follows this amendment.

## 1. The session-role fallback applies (plan 4.2)
- **Data (trial counts only):** the 21 held-in calibration files have 12 to 48 trials. **No session has 50 or more trials.** Eight sessions have 34 or more: 2022-05-23 (48), 05-25 (36), 06-01 (48), 06-03 (48), 06-06 (47), 06-13 (48), 06-15 (36), 06-22 (48).
- **Plan rule:** "If fewer than 8 sessions are eligible: lower the threshold to ≥ 34 trials and drop the 40-sentence budget (core budgets become {3, 12, 24})." With the lower threshold, exactly 8 sessions are eligible, so the 5 + 3 split stays.
- **Result of the rule (stage 0 writes and commits it):** test sessions = 2022-06-03, 06-06, 06-13, 06-15, 06-22; val sessions = 2022-05-23, 05-25, 06-01; source sessions (arm P) = the other 13 held-in sessions.
- **Consequences that plan.md does not spell out (choice):**
  - Core budgets **{3, 12, 24}**; extended budgets **{6}** (24 moved to the core; 40 is dropped).
  - Every "40" that names a single budget means **24**: the core C2 runs of R are at 24; the design check is **reads(R, 24)**. Steps at 24 stay 1,100 (plan 7.1).
  - The extended "R, E, E0, I at {6, 24}" becomes "at {6}" (12 runs, not 24).
- **Expected effect:** a smaller top budget (120 instead of 200 train sentences in total). This makes C2 harder to pass at the top budget and gives fewer chances for H1-H4. The sweep still covers the FALCON few-shot point and the < 200-sentence regime.

## 2. Output folder
- plan.md 12 says `C:\Users\zhang\bci-data\derived\f3-small\`. The task brief names `derived\p15-54`. **Choice:** `C:\Users\zhang\bci-data\derived\p15-54`. A path change only. The runner refuses any other folder under `derived`.

## 3. Open details and the wrapper's choices
| # | plan.md | open point | choice |
|---|---|---|---|
| 3.1 | 5.1 binning | H2 files hold only `binned_spikes` (threshold crossings in **20 ms** bins); FALCON M1-A, MC_Maze and MC_RTT hold spike times | H2: each 20 ms bin repeated twice (the plan's hold rule). M1-A, MC_Maze, MC_RTT: spike times counted in 10 ms bins. M1-A EMG (20 ms) is held to 10 ms like H2. A trial = the bins with `start_time <= timestamp < stop_time`. No extra tail frames |
| 3.2 | 5.1 symbols | exact map | `>` -> space, `~` -> `.`, every other symbol kept as it is. Stage 0 stops (exit code 5) if a symbol is not in the 98-token vocabulary |
| 3.3 | 5.1 z-score | SD floor; order with augmentation | SD floor 0.1 (the E1a rule). z-score -> E1a augmentation -> A_s -> P_in. Pretraining data: per session over all pretraining frames of that session. T15: per-session mean and SD over its train trials (on top of the provider's normalisation) |
| 3.4 | 4.3, 7.1 batches | how trials form a batch | whole trials of all sessions of the run pooled, random order, packed up to 24,000 frames (the E1a `pack_batch`). Batch k of a run depends on (seed, budget, deranged run index, k) only, so a resume is exact |
| 3.5 | 6 arm I | trial set; frame rate | T15 train trials with a known phonemisation (the P15-50 `T15Store`), 20 ms features held to 10 ms, one A_s (512 x 512) per T15 session, P_in 512 -> 512, 41-token CTC head (blank 0), E1a augmentation, init seed 0 |
| 3.6 | 6 arm M | windows, batches, masks | windows of 1,000 frames (10 s) at random starts in the continuous recording; 24 windows (24,000 frames) per batch, all from one dataset; dataset = step mod 3 (M1-A, MC_Maze, MC_RTT). M1-A: 4 held-in calibration sessions, 64 channels, 16 EMG targets, loss only where `eval_mask` is true. MC_Maze (182 units) `hand_vel`, MC_RTT (130 units) `finger_vel`: mean of the 1 kHz samples in each 10 ms frame, loss only where a frame has a finite value. All units of the NLB train files are used. Targets z-scored per session. One `Linear(512 -> k)` readout per dataset after the LayerNorm. Same optimiser settings as I |
| 3.7 | 6 arm P | trial set; permutation | all calibration trials of the 13 source sessions, minus each trial whose text equals the text of a val or test sentence (the last 10 trials of a val or test session); one permutation `numpy.random.default_rng(12345).permutation(192)` for all source sessions; 98-token character CTC head; E1a augmentation; init seed 0 |
| 3.8 | 6 init | "same init seed rule for all arms" | `torch.manual_seed(seed)`, then all layers are built in one fixed order (A_s, P_in, trunk, LayerNorm, head); then the pretrained parts are copied over. So the head of E0 at seed s is exactly the head of R at seed s, and P_in is the same random matrix in every arm at seed s |
| 3.9 | 6 arm T | checkpoint | `derived\p15-08\text\final.pt` (E1a text pretraining, 30,000 steps): trunk, LayerNorm and head; its 64-channel text stem is not used |
| 3.10 | 6 X arms | stem | no A_s; P_in = one `Linear(192 -> 512)` for all sessions (the E1a shared stem), after the same per-session z-score |
| 3.11 | 7.1 optimiser | weight decay of A_s | the E1a `make_optim` rule: decay 0.01 on every weight with 2 or more dimensions (so also on A_s, towards 0, not towards I); none on biases and norms |
| 3.12 | 7.2 stage 1 | where to evaluate | train on the first 12 trials of each val session (one A_s per val session, z-score from those trials), evaluate on the last 10 trials of each val session (30 sentences). No test session is read in stage 1 |
| 3.13 | 6, 7.2 arm M | M's LR is chosen in the extended part | M pretraining and the 2 M selection runs run at the start of the extended part. Their choice goes to `results/selection-ext.json`. Extended stage-2 runs start only after that file is committed and pushed (second gate, exit code 4). All other LRs come from `results/selection.json` |
| 3.14 | 7.3 order | where C2 runs go | for seed 0, 1, 2: normal R, E, E0, I at 24, 12, 3; then for seed 0, 1, 2: C2 of E and I at 24, 12, 3, then C2 of R at 24. A conditional C2 pair (RNG [seed, 78], [seed, 79]) runs directly after the C2 run that triggers it. Trigger: abs(deranged CER - needed) <= 0.03. Extended: plan 11 table order |
| 3.15 | 11 caps | what a core cap does | caps are checked before each run or pretraining (a started run finishes). Core cap 9 h: the remaining core runs are "not run (cap)" and the extended part starts. Total cap 20 h: all remaining runs are "not run (cap)" |
| 3.16 | 8 C1 | shuffle | frames of each test sentence permuted with RNG seed 12345 (the E1a rule) |
| 3.17 | 8 WER | word split | words = the decoded text split on spaces; per-session WER = word edits / reference words; FALCON-style value = mean over the 5 sessions. Descriptive only |
| 3.18 | 9 outcomes | "would-be winner", D condition | would-be winner = an arm A in {E, I, M} with win(A, R, b) at ≥ 2 core budgets; N if C2(A, b) fails at ≥ 2 core budgets for such an arm, or if no C2-tested arm passes C2 at 24. D needs C2 at 24 to pass for every C2-tested arm (E, I and M if it ran). If no label applies, the label is "none (C2 partly invalid)" |
| 3.19 | 12 integrity | Python isolation | every process that reads the downloaded NWB files runs with `python -I`. The launcher uses `-I` |

## 4. Exit codes of `f3s.py`
| code | meaning |
|---|---|
| 0 | finished (DONE), or a cap was reached (DONE with "cap"), or a part is partial (re-launch) |
| 2 | refused (bad output folder, pause or stop file present) |
| 3 | paused by a `pause` or `stop` file (latest checkpoint saved) |
| 4 | waiting for a commit: `results/session_roles.json`, `results/selection.json` or `results/selection-ext.json` must be committed and on `origin/main` |
| 5 | data stop (plan "stop and report": too few sessions, a symbol outside the vocabulary, or a licence change). Writes `STOPPED` |

## 5. New GPU estimate (0.33 s per step + 10 %, as plan 11)
| part | steps | GPU h |
|---|---|---|
| I pretraining | 10,000 | 1.0 |
| stage 1 (R, E, I x 2 LRs at 12) | 4,800 | 0.5 |
| core normal (36 runs, mean 800 steps) | 28,800 | 2.9 |
| core C2 (18 runs E, I; 3 runs R at 24) | 17,700 | 1.8 |
| **core total** | 61,300 | **about 6.2** (+ up to 2 h for conditional C2 pairs) |
| extended: M and P pretraining, 2 M selection runs | 21,600 | 2.2 |
| extended normal (12 at 6; 27 M/T/P; 18 X) | 43,800 | 4.4 |
| extended C2 (M 9; R at 12 3) | 9,600 | 1.0 |
| **total** | 136,300 | **about 14** |

The caps (9 h core, 20 h total) do not change. The step time on H2 is not measured yet (CPU smoke test only); trials are long (7-94 s), so a batch holds only 2-30 trials.
