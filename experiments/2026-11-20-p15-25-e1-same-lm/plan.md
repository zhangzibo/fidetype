---
title: P15-25 E1 readout with the same character LM - pre-registered plan
type: experiment-plan
task: P15-25
updated: 2026-11-20
---

# P15-25: E1a readout with the same character LM for every arm (plan, written before any LM result)

Gap 91 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P15-25](../../wiki/questions/roadmap-standard.md#p15-25-e1-readout-with-the-same-character-lm). Follow-up of [P15-08 E1a](../2026-11-19-p15-08-e1-cross-body/results.md). The LM and the decoder come from [P11-07](../2026-11-20-p11-07-emg-beam-lm/results.md).

## Why
- The north star (F3) asks for "greedy CER **and** CER with the same character LM" (the same-LM rule). Without it, a gain can come from English character statistics and not from the signal.
- E1a read out greedy CTC only, because no licence-clean character LM existed ([E1a deviations](../2026-11-19-p15-08-e1-cross-body/plan.md#deviations-from-the-roadmap-item)).
- P11-07 now gives a licence-clean character LM (Tatoeba English 6-gram) and an in-beam shallow-fusion decoder ([lmbeam.py](../2026-11-20-p11-07-emg-beam-lm/lmbeam.py)). The E1a models emit the same 98-token key vocabulary as P11-01, so the decoder applies without change.

## Roadmap "done when" (followed exactly)
> every E1a arm and budget is re-scored with one character LM and one beam setting (fixed before the re-score), and the H1-H4 rules of the E1a plan are evaluated again on the LM CER next to the greedy CER.

## What was done before this plan (disclosure)
- Reading of the E1a plan, code, results and per-run `result.json` files (greedy edits only), the P11-07 plan / results / code, the P11-14 results and the roadmap note.
- No E1a log-probs exist on disk (E1a kept weights and greedy edits only). No LM decode of any Willett sentence was run. No LM CER was computed.

## Design in one table
| Item | Value |
|---|---|
| Models | the 41 E1a adaptation runs (4 arms R / T / E / S x 5 budgets x 2 seeds, plus the C2 label-shuffle run E-b30-s0-labelshuf), weights `final.pt` (the E1a primary readout: final step). Local only: `C:/Users/zhang/bci-data/derived/p15-08/runs/` (read only) |
| Data and splits | exactly E1a (Willett cache `derived/p15-08/willett/`, read only): test = last block of each session (80 sentences, 3,448 characters); val = one other block per session (106 sentences) |
| Log-probs | one forward pass of each `final.pt` on the test sentences (and the val sentences for the tuning runs, see Fv), batched as E1a `eval_set`, ROCm GPU, float32. Stored in `derived/p15-25/lp/` (never committed) |
| Character LM (all arms) | P11-11 `eng_tatoeba_6gram_mkn_noE2Q.npz` (sha256 `7c4f133c...a06b8`; Tatoeba English, CC BY 2.0 FR, modified Kneser-Ney, order 6) |
| Decoder (all arms) | P11-07 `LMBeam` (imported, unchanged): causal CTC prefix beam, LM on the intended text (letters lower case; space and every non-letter key = one space), prune log p >= -8, end terms (`</s>`). Whole sentence pushed (all frames incl. the 100-frame tail), top-1 hypothesis |
| CER | as E1a: Levenshtein over 98-token sequences (raw characters, punctuation and case count) / reference length; pooled over the 80 test sentences per run; per arm and budget the mean over the 2 seeds |

## Decoders (all fixed now; no tuning on Willett for the primary readout)
| Id | Setting | Role | Licence of the readout |
|---|---|---|---|
| G | greedy CTC | C0 reproduction of E1a | as the model |
| B0 | beam 8, no LM | isolates the beam from the LM | as the model |
| **F** | **w 0.5, beta 1, lam 0, beam 8** (the P11-07 decoder F, tuned on emg2qwerty track-val, not on Willett) | **primary readout** | LM text CC BY 2.0 FR (clean). R-arm readout is fully clean-track |
| FL | w 0.25, beta 1, lam 8, beam 8, P11-11 lexicon (16,875 words typed in emg2qwerty track-train sessions) | secondary readout | lexicon is CC BY-NC-SA 4.0: **research only** |
| Fv | lam 0, beam 8, (w, beta) tuned on Willett **val** (see below) | descriptive sensitivity | clean LM; uses val labels |

**Why F is primary and not FL.** The roadmap note (P11-14) proposes FL for the LM CER. We make F primary and FL secondary for three reasons: (1) FL adds a research-only term (the emg2qwerty lexicon, CC BY-NC-SA 4.0), and F is the licence-clean decoder that a clean-track result can use; (2) on emg2qwerty, F had the lower test CER (P11-07 H3 failed: FL 10.88 % vs F 10.10 %); FL's advantage in P11-14 is a **guard confidence** advantage, and this item scores CER, not guarded commits; (3) the done-when asks for "one character LM and one beam setting", and F is the plain character LM. Both F and FL are fixed before the re-score and both are reported for every run. This is a stated deviation from the note, not from the done-when.

**Fv (descriptive only).** Grid w in {0.25, 0.5, 0.75, 1.0, 1.5} x beta in {0, 1, 2} (15 configs), beam 8, lam 0. Criterion: pooled CER over the 106 val sentences of the 16 runs at budgets 30 and all (4 arms x 2 seeds x 2 budgets). Ties: smaller w, then smaller beta. The chosen (w, beta) is applied unchanged to all 41 runs on test. Fv uses the val labels (about 71 extra labelled minutes), so it is not a "minutes of data" number and it decides no verdict.

## Rules re-evaluated (the E1a rules, frozen in `p15-08/config.json`, unchanged)
"A beats B at budget b" = both (i) Δ = CER_B − CER_A (seed means) > seed spread; (ii) the 95 % paired bootstrap interval of Δ (10,000 resamples of the 80 test sentences, per-sentence edits averaged over seeds, ratio of sums, seed 0) has its lower end above 0. Each rule is computed for **G, B0, F, FL and Fv**; the verdicts that count for P15-25 are those on **F**.

| Id | Claim | Pass if (on F) |
|---|---|---|
| V1 (gate) | the target decoder is usable | best arm at "all" has F test CER <= 0.50; else H1-H6 are inconclusive |
| **H1 (primary, confirmatory)** | body-signal pretraining helps beyond text statistics, with the same LM | E beats T at >= 2 of {3, 10, 30} min ("partial" at exactly 1) |
| H2 | E beats R at >= 2 of {3, 10, 30} | as E1a |
| H3 | T beats R at >= 2 of {3, 10, 30} | as E1a |
| H4 | E beats S at >= 2 of {3, 10, 30} | as E1a |
| Roadmap rule | E beats T, clause (i) only, at >= 1 of {3, 10, 30, 100} | as E1a |
| C1 (time-shuffle) | for every run at budgets 30 and all with **F** test CER <= 0.70: F CER on frame-shuffled test input (E1a permutation: `default_rng(12345)`, sentences in test order) >= 0.85 | the LM decoder can output text without the signal |
| C2 (label-shuffle) | E-b30-s0-labelshuf: F CER >= max(0.75, F CER of E-b30-s0 + 0.10) | as E1a |

## New pre-registered claims of P15-25 (secondary)
E1a found its only clear difference at "all" (descriptive there). We pre-register these now, before any LM result:

| Id | Claim | Pass if |
|---|---|---|
| H5 | at full data, E beats T with the same LM | E beats T at "all" on F (both clauses) |
| H6 | at full data, E beats R with the same LM | E beats R at "all" on F (both clauses) |
| L1 | the LM lowers the CER of decoders that read the signal | for both E-ball runs: F CER < G CER, and the 95 % paired bootstrap interval of CER_G − CER_F over the 80 test sentences (per run, seed 0) has its lower end above 0 |
| L2 (same-LM rule) | no greedy verdict changes only because of the LM | reported as a table: for V1, H1-H6, roadmap rule, C1, C2, the verdict on G next to the verdict on F. "Holds" if no H moves from fail to pass, or from pass to fail, between G and F. A change is reported, not hidden |

## Multiple comparisons
- **H1 on F is the only confirmatory test.** Its three budget comparisons combine by the pre-set ">= 2 of 3" rule (as E1a); no further correction.
- Secondary: H2, H3, H4 (9 budget comparisons), H5, H6 (2), L1 (2): k = 13 pairwise comparisons on F. Each is reported with its 95 % interval **and** with a Bonferroni interval at level 1 − 0.05 / 13 (percentiles 0.19 % / 99.81 % of the same bootstrap). A secondary win is "robust" only if the Bonferroni interval also excludes 0.
- G, B0, FL and Fv tables and verdicts are descriptive (no extra claims).

## Controls and checks
| Id | Check | Pass if |
|---|---|---|
| C0 (reproduction) | G on our log-probs vs E1a `test_cer_final` per run (41 runs) | abs. difference <= 0.005 for every run (GPU non-determinism allows small differences). If it fails, the run is reported and the LM numbers are still given, with the difference |
| LM overlap | share of the Willett test and val sentences (LM-normalised) that occur exactly in the Tatoeba English export (an upper bound of the LM training set; the LM blocked only emg2qwerty texts) | reported, no threshold. A high overlap makes the absolute LM CER optimistic for every arm alike; it does not bias the arm comparison |
| LM-only output | F on all-blank input (log p(blank) = 0) and on uniform log-probs, 1 sentence length | reported (shows what the LM alone emits) |

## What is out of scope (stated now)
- **Guarded safe WPM.** The done-when asks for CER only. The P11-14 confidence L-FL is fitted on emg2qwerty features, and E1a has no Willett guard calibration; the Willett guard of P14-41 never commits (gap 138). So this item computes no guarded commits and no safe WPM. If the results show a usable decoder (F CER at "all" well below 0.30), a guarded Willett readout becomes a new gap.
- Best-val checkpoints (E1a secondary readout) are not re-scored.
- No new LM, no lexicon built from Willett text, no per-arm tuning.

## Compute, outputs, rules
| Stage | Where | Estimate |
|---|---|---|
| `logits` | ROCm venv, GPU (one GPU job), 41 runs: test (80), val (16 tuning runs only), time-shuffled test (12 C1 runs) | about 5-10 min; about 9 GB on disk (float32) |
| `overlap`, `lmonly` | CPU, 1 thread | about 1 min |
| `tune` (Fv) | CPU, 6 single-thread workers | about 20-40 min |
| `test` (G, B0, F, FL, Fv on 41 runs; F on 12 shuffled) | CPU, 6 workers | about 15-30 min |
| `summary` | CPU | < 1 min |

- Heavy stages start only after `C:/Users/zhang/bci-data/derived/p3-12/DONE` exists (P3-12 needs a quiet machine).
- Detached: `launch.py` -> `python -m fidetype.utils.isolation run --class background --threads 1 -- ...` (the GPU stage in the ROCm venv; the CPU stages in the main venv). Log `results/run.log`; per-unit files in `C:/Users/zhang/bci-data/derived/p15-25/` (a stop loses minutes only; finished units are skipped on restart); `STOP` file `derived/p15-25/STOP`; `DONE` file at the end; keep-awake (`SetThreadExecutionState`). Peak memory logged; target < 8 GB (workers memory-map the log-prob files).
- **Licence.** Willett: CC0. T, E, S weights and their log-probs derive from emg2qwerty (CC BY-NC-SA 4.0): research only. FL uses the research-only lexicon. The repo gets this plan, code and aggregate CERs only: no weights, log-probs, per-sentence outputs or text.
- No change of models, splits, LM, decoders, rules or metrics after this commit. A change is an amendment with a time stamp, before the affected result.

## Gap rule
- **Gap 91 closes** when all 41 runs are re-scored with F (one LM, one beam setting, fixed here) and V1, H1-H4, the roadmap rule, C1 and C2 are evaluated on F next to G, under this plan, whatever the outcome. A null result closes the gap too.
- New limits become roadmap items and open-gap rows with the next free numbers.

Write-up: `results.md` in this folder, with every result, including failures.
