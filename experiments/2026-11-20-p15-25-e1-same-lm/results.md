---
title: P15-25 E1a readout with the same character LM - results
type: experiment
task: P15-25
updated: 2026-11-20
---

# P15-25: E1a readout with the same character LM (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (commit `885f9c5`, before any LM result). Code `29798a7`. Aggregates: [results/summary.json](results/summary.json), log `results/run.log`. Log-probs and per-sentence outputs stay local in `C:\Users\zhang\bci-data\derived\p15-25\`.

Run: 2026-11-20 22:11:40 - 22:28:57 (detached, isolation class `background`). It started after `derived\p3-12\DONE` existed (22:11:01, checked by hand). GPU stage `logits` 22:11-22:15 (207 s, peak 1.9 GB RAM); CPU stages 22:15-22:29 (6 single-thread workers, worker peak 210 MB, main 266 MB). No stop, no restart.

## Outcome
**The same character LM does not change the E1a answer at minutes scale.** With decoder F (licence-clean Tatoeba 6-gram, fixed in advance), H1 still fails (0 of 3 budgets): at 3 to 30 min no arm reads the signal, and the LM lowers every arm's CER by about the same small amount. **At full data the LM helps a lot, and the E-over-T gap grows**: E 0.395 -> 0.271, T 0.805 -> 0.783 (H5 pass, robust). The best single run is R-ball-s0: 0.305 -> **0.173**. One secondary verdict changes with the LM: H4 (E beats S) goes from "partial" to "fail", because its 30-min win falls just below the seed spread (Δ 0.075 vs 0.077).

## Verdicts (pre-registered; F is the primary readout)
| Id | Claim | G (greedy, = E1a) | **F (LM)** | Note on F |
|---|---|---|---|---|
| C0 | greedy on our log-probs reproduces E1a | **pass** | - | 41 / 41 runs, max difference 0.0000; per-sentence edits equal on 80 / 80 sentences of every run |
| V1 | best arm at "all" <= 0.50 | pass (0.395) | **pass (0.271)** | H1-H6 count |
| **H1 (primary)** | E beats T at >= 2 of {3, 10, 30} | fail (0) | **fail (0)** | T is better than E at all three budgets (CI95 of CER_T − CER_E below 0 at 3, 10, 30) |
| H2 | E beats R at >= 2 of {3, 10, 30} | fail (0) | **fail (0)** | R best at 3 min; at 10 and 30 min Δ < R's seed spread |
| H3 | T beats R at >= 2 of {3, 10, 30} | fail (0) | **fail (0)** | as H2 |
| H4 | E beats S at >= 2 of {3, 10, 30} | partial (1) | **fail (0)** | 30 min: Δ +0.075 < spread 0.077 (CI95 [+0.027, +0.138]) |
| H5 (new) | E beats T at "all" | pass | **pass, robust** | Δ +0.512, spread 0.072, CI95 [+0.472, +0.551], Bonferroni [+0.453, +0.569] |
| H6 (new) | E beats R at "all" | fail | **fail** | Δ +0.229 < R's seed spread 0.654 (R-ball 0.173 / 0.827) |
| L1 (new) | LM lowers CER of decoders that read the signal (both E-ball runs) | - | **pass, robust** | E-ball-s0 0.360 -> 0.235 (CI95 of the gain [+0.105, +0.145]); s1 0.431 -> 0.307 ([+0.101, +0.147]) |
| L2 (new) | no H verdict changes between G and F | - | **does not hold** | H4 partial -> fail; every other verdict is the same |
| Roadmap rule | E beats T, clause (i), at >= 1 of {3, 10, 30, 100} | pass (3, 100 min) | **pass (100 min only)** | Δ +0.025 > spread 0.017; not meaningful (2.5 CER points; T better at 3-30 min) |
| C1 | F CER on time-shuffled test >= 0.85 (runs at 30 / all with F CER <= 0.70) | pass (3 runs) | **pass (3 runs)** | E-ball-s0 0.235 -> 0.895; E-ball-s1 0.307 -> 0.897; R-ball-s0 0.173 -> 0.854 |
| C2 | E-b30-s0 labels deranged: F CER >= max(0.75, normal + 0.10) | fail | **fail** | 0.811 vs needed 0.887 (normal 0.787) |

Multiple comparisons (plan): H1 is the only confirmatory test. Of the 13 secondary comparisons on F, the wins are H5 and L1 (2 runs); all three also exclude 0 in the Bonferroni interval (1 − 0.05 / 13).

## Test CER per arm and budget (80 test sentences, 3,448 characters; mean of 2 seeds, seed 0 / seed 1)
### F: same character LM (primary)
| Budget | R random | T text-only | E EMG trunk | S shuffled E |
|---|---|---|---|---|
| 3 | **0.874** (0.896 / 0.852) | 0.941 (0.938 / 0.944) | 0.949 (0.949 / 0.950) | 0.911 (0.979 / 0.843) |
| 10 | 1.008 (0.785 / 1.231) | **0.836** (0.795 / 0.876) | 0.873 (0.855 / 0.891) | 0.843 (0.840 / 0.846) |
| 30 | 0.844 (0.893 / 0.796) | **0.771** (0.771 / 0.772) | 0.791 (0.787 / 0.794) | 0.866 (0.828 / 0.904) |
| 100 | 0.808 (0.798 / 0.818) | 0.776 (0.785 / 0.767) | **0.751** (0.752 / 0.751) | 0.844 (0.851 / 0.838) |
| all | 0.500 (**0.173** / 0.827) | 0.783 (0.782 / 0.784) | **0.271** (0.235 / 0.307) | 0.786 (0.747 / 0.825) |

### All readouts (seed means)
| Arm, budget | G greedy | B0 beam, no LM | **F LM** | FL LM + lexicon (research only) | Fv LM, val-tuned |
|---|---|---|---|---|---|
| R 3 / 10 / 30 / 100 / all | 0.865 / 1.327 / 0.851 / 0.837 / 0.613 | 0.867 / 1.347 / 0.849 / 0.835 / 0.573 | 0.874 / 1.008 / 0.844 / 0.808 / 0.500 | 0.863 / 1.340 / 0.847 / 0.829 / 0.504 | 0.857 / 1.342 / 0.837 / 0.829 / 0.521 |
| T | 0.960 / 0.863 / 0.786 / 0.777 / 0.805 | 0.953 / 0.851 / 0.776 / 0.767 / 0.781 | 0.941 / 0.836 / 0.771 / 0.776 / 0.783 | 0.942 / 0.830 / 0.761 / 0.765 / 0.742 | 0.929 / 0.793 / 0.803 / 0.856 / 0.796 |
| E | 0.956 / 0.884 / 0.812 / 0.767 / 0.395 | 0.954 / 0.873 / 0.795 / 0.747 / 0.369 | 0.949 / 0.873 / 0.791 / 0.751 / **0.271** | 0.946 / 0.863 / 0.784 / 0.730 / 0.278 | 0.934 / 0.833 / 0.756 / 0.740 / **0.254** |
| S | 0.919 / 0.922 / 1.003 / 0.919 / 0.925 | 0.919 / 0.904 / 0.988 / 0.903 / 0.831 | 0.911 / 0.843 / 0.866 / 0.844 / 0.786 | 0.906 / 0.886 / 0.978 / 0.867 / 0.768 | 0.901 / 0.871 / 0.987 / 0.924 / 0.776 |
| Minutes to CER 0.60 (R / T / E / S) | - / - / 208 / - | 427 / - / 189 / - | 300 / - / **167** / - | 315 / - / 160 / - | 335 / - / 160 / - |

Verdicts on the secondary readouts (descriptive): B0 and FL give the same H1-H6 verdicts as F, except FL H3 "partial" (T beats R at 30 min). Fv (tuned on val: w 0.5, beta 2; val CER 0.676) gives H1 "partial" (E beats T at 30 min: Δ +0.047 > spread 0.026, CI95 [+0.028, +0.070]) and H2 "partial". Fv uses about 71 extra labelled minutes and decides no verdict (plan).

**Insertions.** F removes most of the long wrong strings of the diverged R-b10-s1 run (greedy hyp / ref length 1.82, F 1.09; CER 1.839 -> 1.231). FL does not (1.85): its lexicon term with beta 1 does not stop the run-on output.

## Pairwise tests on F at the H budgets
Δ = CER(B) − CER(A), seed means; spread = largest seed difference of A or B; CI95 = paired bootstrap over the 80 test sentences (10,000 resamples, seed 0).

| Pair (A beats B?) | 3 min | 10 min | 30 min | Wins |
|---|---|---|---|---|
| H1 E vs T | −0.008 / 0.006 / [−0.014, −0.002] | −0.038 / 0.081 / [−0.047, −0.028] | −0.020 / 0.007 / [−0.031, −0.007] | 0 |
| H2 E vs R | −0.076 / 0.044 / [−0.084, −0.066] | +0.135 / 0.446 / [+0.023, +0.265] | +0.054 / 0.098 / [+0.035, +0.076] | 0 |
| H3 T vs R | −0.068 / 0.044 / [−0.077, −0.058] | +0.172 / 0.446 / [+0.059, +0.304] | +0.073 / 0.098 / [+0.055, +0.095] | 0 |
| H4 E vs S | −0.038 / 0.135 / [−0.044, −0.032] | −0.030 / 0.036 / [−0.048, −0.011] | +0.075 / 0.077 / [+0.027, +0.138] | 0 |

## Controls and checks
| Check | Result |
|---|---|
| C0 reproduction | exact: our GPU log-probs give the E1a greedy edits on every sentence of all 41 runs |
| C1 time-shuffled (F) | all 16 shuffled sets 0.767-0.897; the 3 applicable runs pass (>= 0.854) |
| C2 label-shuffle (F) | fail, as greedy: 0.811 vs 0.787 normal (2.4 points). The LM does not make the 30-min decoders read the signal |
| LM overlap (Tatoeba English export, 2,032,357 sentences, an upper bound of the LM training set) | test 13 of 80 sentences (5 of 47 unique texts); val 9 of 106; pool 97 of 781 (83 of 734 unique). The absolute LM CER can be a little optimistic; the effect is the same for every arm |
| LM-only output (F, 4,100 frames) | all-blank input: 0 tokens; uniform log-probs: 4,100 tokens (one per frame: the length bonus beta 1 and the LM decide everything when the acoustic scores are flat) |
| Memory | peak 1.9 GB (GPU stage process), CPU workers 210 MB, main 266 MB; target < 8 GB met |

> **Our take:** the same-LM rule does its job here. It confirms the E1a reading and does not rescue the minutes-scale question: at <= 30 min every arm stays at CER 0.77-0.95 with the LM, the label-shuffle control still fails, and the text-only arm is still a little better than the EMG arm. So a "gain from English statistics" cannot explain any F3 transfer, because there is no transfer to explain at minutes scale. The full-data picture is stronger with the LM: the EMG-pretrained trunk reaches 0.271 on both seeds (0.235 / 0.307), and the LM gain is largest where the decoder reads the signal (about 12 points for E-ball, 13 for R-ball-s0, 2 for T-ball). This matches P11-07: the LM multiplies a usable acoustic signal; it does not create one. The uniform-input check is a warning for any guard on this decoder: with flat log-probs, F emits a token on every frame, so a no-signal gate (as P11-12 for EMG) is needed before F is used for commits.

## Deviations (stated honestly)
1. **F primary, FL secondary**, against the roadmap note (P11-14) that proposes FL. Reasons in the plan (licence-clean, lower CER in P11-07, CER not guarded commits). Both are fixed in advance and reported for every run; the FL verdicts are the same as F except H3 partial.
2. No guarded safe WPM (plan: out of scope; the done-when asks for CER only).
3. `results/run.log` starts with two smoke runs from 21:24 (2 test sentences, 1 val sentence of E-ball-s0, written to `smoke-*` folders that were deleted before the real run). They gave no counted number.

## Gap rule
**Gap 91 closes:** all 41 E1a runs are re-scored with one character LM and one beam setting (F, fixed before the re-score), and V1, H1-H4, the roadmap rule, C1 and C2 are evaluated on F next to G under the plan.

## New gaps
| Gap | Item | What |
|---|---|---|
| 143 | P15-38 | E1 LM readout with the Willett texts blocked from the LM: 13 of 80 test sentences occur in the Tatoeba export. Done when the Tatoeba 6-gram is rebuilt with every Willett sentence blocked (the P11-11 exclusion rule), the 41 runs are re-scored with F, and the change of each H verdict and of the E / R full-data CER is reported |
| 144 | P14-48 | `willett-hw` with the same-LM readout: the packaged decoder (R-ball-s0, P14-33) falls from 0.305 (greedy) to 0.173 with F. Done when the package offers the F readout with a no-signal gate (uniform input emits 4,100 tokens), the card states the LM licence and the overlap, and the P14-41 guard is re-calibrated on it (feeds gap 138) |

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests (CPU, seconds) | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-20-p15-25-e1-same-lm/test_p15_25.py` |
| Full run (detached, about 18 min: GPU 4 min + CPU 14 min) | `.venv\Scripts\python.exe experiments/2026-11-20-p15-25-e1-same-lm/launch.py` (refuses while `derived\p3-12\DONE` is missing; finished runs and units are skipped) |
| Check / stop / resume | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p15-25\DONE` exists; stop: create `derived\p15-25\STOP`; resume: delete STOP and launch again |

## Licence
- Willett data: CC0. R-arm log-probs and the F readout of R are clean-track (Tatoeba text CC BY 2.0 FR, attribution: Tatoeba contributors).
- T, E and S weights and their log-probs derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only. FL uses the research-only emg2qwerty lexicon.
- This commit holds aggregate CERs only: no weights, log-probs, per-sentence outputs or text.
