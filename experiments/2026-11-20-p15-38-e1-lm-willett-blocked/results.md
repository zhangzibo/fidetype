---
title: P15-38 E1 LM readout with the Willett texts blocked from the LM - results
type: experiment
task: P15-38
updated: 2026-11-20
---

# P15-38: E1a LM readout with every Willett text blocked from the LM (results)

Pre-registration: [plan.md](plan.md) and [config.json](config.json) (commit `1dd2a1a`, before any re-score result). Aggregates: [results/summary.json](results/summary.json), log `results/run.log`. The new LM, the per-sentence decodes and the blocked texts stay local in `C:\Users\zhang\bci-data\derived\p15-38\`. The P15-25 log-probs and decodes (`derived\p15-25\`) were read only.

Run: 2026-11-20 22:47:11 - 22:56:04 (detached, isolation class `background`, CPU only, 3 steps). No stop, no restart, no failure. Peak memory: LM build 1.21 GB, decode workers 217 MB, main 333 MB (target < 6 GB met).

## Outcome
**No P15-25 verdict changes when the LM holds no Willett text (M1 holds).** The CER moves by at most 0.0015 in any run. 17 of 41 runs change at all. The full-data E arm goes from 0.271 to 0.273 (seed 0: 0.2352 -> 0.2367; seed 1: 0.3074 -> 0.3089). R-ball-s0 goes from 0.1734 to 0.1743. The Tatoeba overlap made the P15-25 LM CER optimistic by about 0.1-0.2 CER points, not more.

## The new LM
| Item | Value |
|---|---|
| Recipe | P11-11 `stage_lm` (unchanged code path) + the Willett block |
| Blocked texts | 2,399 emg2qwerty intended texts (P11-11, kept) + **907 unique Willett texts** (all 1,000 trials of the 10 `sentences.mat` files; the E1a `meta.json` adds none). 3,306 texts, 3,086 of >= 15 characters |
| Sentences removed beyond the toy blocklist | 3,387 (P11-11: 1,445; so the Willett block removes 1,942 more) |
| Train / held-out | 600,000 / 5,000 sentences (as P11-11) |
| Held-out perplexity (first 2,000) | 3.1582 (P11-11: 3.1578; the held-out set shifts a little) |
| File | `derived\p15-38\eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz`, sha256 `d7f6e829b827d1f7d09f5927eb51ec33fd79df29201d7e722a0878a503059261`. Local only |
| LMa (exact Willett text in train or held-out) | **0** (pass) |
| LMb (containment, >= 15 characters) | **0** (pass) |
| For comparison: the P11-11 LM text | train held 30 Willett texts exactly (held-out 1), and 609 train sentences hit a Willett text by the containment rule |

## Controls
| Id | Check | Result |
|---|---|---|
| LM0 | P11-11 recipe, Willett block empty, vs `p11-11\eng_tatoeba_6gram_mkn_noE2Q.npz` | **pass**: all 30 arrays equal, header (order, smoothing, discounts) equal; same counts (1,445 removed, ppl 3.1578). The P11-11 file sha256 is the P15-25 value |
| C0' | greedy on the P15-25 log-probs = P15-25 G | **pass**: per-sentence edits equal on 41 / 41 runs |
| R0 | F with the old LM on E-ball-s0 and R-ball-s0 = P15-25 F | **pass**: edits equal (0.2352, 0.1734) |
| Old verdicts | our re-run of the P15-25 verdict code on the P15-25 F decodes = P15-25 `summary.json` | equal for all 10 rules |
| LM-only (new F, 4,100 frames) | all-blank / uniform input | 0 tokens / 4,100 tokens (as P15-25: a no-signal gate is still needed) |

So the comparison is clean: the only change between P15-25 F and the new F is the LM.

## M1 (primary): verdicts, P15-25 LM vs new LM
| Id | G (greedy) | **F, P15-25 LM** | **F, new LM** | FL old / new | Fv old / new |
|---|---|---|---|---|---|
| V1 | pass | pass (0.271) | **pass (0.273)** | pass / pass | pass / pass |
| **H1 (primary)** | fail | fail (0) | **fail (0)** | fail / fail | partial / partial |
| H2 | fail | fail | **fail** | fail / fail | partial / partial |
| H3 | fail | fail | **fail** | partial / partial | fail / fail |
| H4 | partial | fail | **fail** | fail / fail | fail / fail |
| H5 | pass | pass, robust | **pass, robust** | pass / pass | pass / pass |
| H6 | fail | fail | **fail** | fail / fail | fail / fail |
| Roadmap rule | pass | pass (100 min) | **pass (100 min)** | pass / pass | pass / pass |
| C1 | pass | pass (3 runs) | **pass (3 runs)** | - | - |
| C2 | fail | fail (0.811) | **fail (0.811)** | fail / fail | fail / fail |
| L1 | - | pass, robust | **pass, robust** | - | - |

**M1 holds: no verdict changes**, on F, FL or Fv. L2 on the new F gives the P15-25 answer: it does not hold, because H4 is "partial" on G and "fail" on F.

Key numbers on the new F (P15-25 F in brackets):
- H1: Δ (CER_T − CER_E) −0.008 / −0.037 / −0.020 at 3 / 10 / 30 min (−0.008 / −0.038 / −0.020); T is still better than E at all three budgets.
- H4 at 30 min: Δ +0.0748 vs spread 0.0757 (+0.0753 vs 0.0766); CI95 [+0.027, +0.138]. Still just below the spread.
- H5: Δ +0.510, spread 0.072, CI95 [+0.470, +0.549] (+0.512, [+0.472, +0.551]).
- H6: Δ +0.228 < R's seed spread 0.653.
- L1: E-ball-s0 0.360 -> 0.237 (gain CI95 [+0.103, +0.143]); E-ball-s1 0.431 -> 0.309 ([+0.099, +0.146]).
- C1: E-ball-s0 0.237 -> 0.895, E-ball-s1 0.309 -> 0.897, R-ball-s0 0.174 -> 0.854 (all >= 0.85).
- Minutes to CER 0.60: E 168 (167), R 300 (300), T and S never.

## M2: CER change per arm and budget (F, seed means; new − P15-25)
| Budget | R | T | E | S |
|---|---|---|---|---|
| 3 | 0.874 -> 0.874 (+0.000) | 0.941 -> 0.941 (+0.000) | 0.949 -> 0.949 (+0.000) | 0.911 -> 0.911 (+0.000) |
| 10 | 1.008 -> 1.008 (−0.000) | 0.836 -> 0.836 (+0.000) | 0.873 -> 0.873 (−0.000) | 0.843 -> 0.843 (+0.000) |
| 30 | 0.844 -> 0.845 (+0.000) | 0.771 -> 0.771 (−0.000) | 0.791 -> 0.791 (+0.000) | 0.866 -> 0.866 (−0.000) |
| 100 | 0.808 -> 0.808 (+0.000) | 0.776 -> 0.776 (+0.000) | 0.751 -> 0.752 (+0.000) | 0.844 -> 0.844 (+0.000) |
| all | 0.500 -> 0.501 (+0.000) | 0.783 -> 0.783 (−0.000) | **0.271 -> 0.273 (+0.001)** | 0.786 -> 0.786 (+0.000) |

Largest change in any single run: 0.0015. Label-shuffle run: 0.811 -> 0.811. FL: largest cell change +0.001. Fv: largest cell change +0.003 (R at 10 min, the diverged R-b10-s1 run) and −0.002 (S at 30 min).

## M3: where the change comes from (F, 13 test sentences in the Tatoeba export vs the other 67)
| Run | G in / out | F old LM in / out | F new LM in / out |
|---|---|---|---|
| E-ball-s0 | 0.334 / 0.364 | 0.196 / 0.242 | 0.202 / 0.243 |
| E-ball-s1 | 0.373 / 0.441 | 0.257 / 0.316 | 0.257 / 0.318 |
| R-ball-s0 | 0.306 / 0.305 | 0.157 / 0.176 | 0.163 / 0.176 |
| T-ball-s0 | 0.804 / 0.806 | 0.778 / 0.783 | 0.778 / 0.783 |

(13 sentences, 509 characters "in"; 67 sentences, 2,939 characters "out".) The overlap sentences are easier already for greedy decoding (E-ball-s0: 0.334 vs 0.364). The new LM raises their F CER by at most 0.006. The LM gain on the other 67 sentences is almost the same with both LMs.

## M4: full-data change per run (paired bootstrap of CER_new − CER_old, 80 sentences, 10,000, seed 0)
| Run | P15-25 F | New F | Δ | CI95 | Sentences changed |
|---|---|---|---|---|---|
| E-ball-s0 | 0.2352 | 0.2367 | +0.0015 | [0.0000, +0.0039] | 2 |
| E-ball-s1 | 0.3074 | 0.3089 | +0.0015 | [0.0000, +0.0033] | 3 |
| R-ball-s0 | 0.1734 | 0.1743 | +0.0009 | [0.0000, +0.0024] | 2 |

## Overlap (descriptive; nothing else was blocked)
| Set | Sentences | In Tatoeba (exact) | Exact or containment | Unique texts | Unique in Tatoeba (exact) | Unique, exact or containment |
|---|---|---|---|---|---|---|
| Willett test | 80 | 13 | 29 | 47 | 5 | 11 |
| Willett val | 106 | 9 | 20 | 106 | 9 | 20 |
| Willett pool | 781 | 97 | 157 | 734 | 83 | 130 |
| All Willett texts | - | - | - | 907 | 100 | 164 |

- Tatoeba export: 2,032,357 unique normalised sentences; 1,873 of them hit a Willett text by the containment rule.
- **emg2qwerty**: 2,399 unique intended texts (the 16 P11-09 sessions). 3 occur exactly in the Tatoeba export; the containment rule removed 1,445 Tatoeba sentences for them in P11-11. **No Willett text is an emg2qwerty text** (0 exact).

## EMG (P11-07 / P11-14): not re-measured
P11-07 and P11-14 use the P11-11 LM. That LM already blocks every intended text of the 16 emg2qwerty sessions they score (exact and containment), and LM0 shows that our recipe gives the same file. The new LM is used only in this item, and no Willett text is an emg2qwerty text. So the overlap does not touch any EMG number. We skipped the EMG re-measure, as the plan says.

> **Our take:** the overlap was real but small in effect. The LM is a character 6-gram trained on 600,000 sentences, and 30 exact Willett texts in its train set give it almost no sentence memory. The E1a and P15-25 answers stand without change: at <= 30 min no arm reads the signal with or without the LM, and at full data the EMG-pretrained trunk is at 0.273 with a clean LM (R-ball-s0 0.174). For later Willett readouts (P14-48, the `willett-hw` package) we suggest the new LM, because it has no test overlap and costs nothing in CER. But it adds a research-only build input (see Licence), so the choice is a licence question too.

## Deviations
- None from the plan. Note: the plan estimated the `test` stage at 15-25 min with 4 workers; it took 7 min.

## Gap rule
**Gap 143 closes:** the new LM is built by the P11-11 rule with every Willett sentence blocked (LMa 0, LMb 0), all 41 E1a runs are re-scored with F on it, and M1 (each verdict, P15-25 F vs new F: no change) and M2 (full-data E 0.271 -> 0.273, R-ball-s0 0.1734 -> 0.1743) are reported.

## Rerun
| Step | Command (repo root) |
|---|---|
| Tests (CPU, seconds) | `.venv\Scripts\python.exe -m pytest -q experiments/2026-11-20-p15-38-e1-lm-willett-blocked/test_p15_38.py` |
| Full run (detached, about 9 min) | `.venv\Scripts\python.exe experiments/2026-11-20-p15-38-e1-lm-willett-blocked/launch.py` (needs the P15-25 log-probs in `derived\p15-25\lp\`; finished stages and units are skipped) |
| Check / stop / resume | tail `results/run.log`; done when `C:\Users\zhang\bci-data\derived\p15-38\DONE` exists; stop: create `derived\p15-38\STOP`; resume: delete STOP and launch again |

## Licence
- LM text: Tatoeba, CC BY 2.0 FR (attribution: Tatoeba contributors). The new LM is built with a blocklist that holds research-only emg2qwerty texts (CC BY-NC-SA 4.0) and CC0 Willett texts. As P11-07 / P11-11, the LM file stays local; the repo has the recipe, the sha256 and the counts only.
- Willett data: CC0. T, E, S weights and their log-probs derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only. FL uses the research-only lexicon.
- This commit holds aggregate CERs and counts only: no LM file, no log-probs, no per-sentence outputs, no text.
