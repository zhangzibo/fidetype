---
title: P15-38 E1 LM readout with the Willett texts blocked from the LM - pre-registered plan
type: experiment-plan
task: P15-38
updated: 2026-11-20
---

# P15-38: E1a LM readout with every Willett text blocked from the LM (plan, written before any re-score result)

Gap 143 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P15-38](../../wiki/questions/roadmap-standard.md#p15-38-e1-lm-readout-with-the-willett-texts-blocked-from-the-lm). Follow-up of [P15-25](../2026-11-20-p15-25-e1-same-lm/results.md). The LM build rule comes from [P11-11](../2026-11-19-p11-11-emg-nonvacuous/run.py) (`stage_lm`), the decoder from [P11-07](../2026-11-20-p11-07-emg-beam-lm/lmbeam.py).

## Why
- P15-25 used the P11-11 LM (`eng_tatoeba_6gram_mkn_noE2Q.npz`). That LM blocked the emg2qwerty texts only. 13 of the 80 Willett test sentences (5 of 47 unique texts), 9 of 106 val and 97 of 781 pool sentences occur in the Tatoeba English export.
- So the LM can know some test sentences. The arm comparison is fair (one LM for all arms), but the absolute LM CER can be optimistic, and a verdict can depend on it.

## Roadmap "done when" (followed exactly)
> the Tatoeba 6-gram is rebuilt with every Willett sentence blocked (exact and containment, the P11-11 rule), the 41 E1a runs are re-scored with decoder F, and the change of each H verdict and of the full-data E / R CER is reported.

## Primary question
**Do any P15-25 verdicts change when the LM has no Willett text?** We report, for every rule, the P15-25 F verdict next to the new F verdict, and the CER change (new F − P15-25 F) per arm and budget.

## What was done before this plan (disclosure)
- Reading of the P15-25 plan, code, results and `summary.json`; the P11-07, P11-11, P11-14 code and notes; the roadmap and gap rows.
- A count of the Willett texts (scratch script, no LM, no decode): 10 session files `Datasets/*/sentences.mat`, 1,000 sentence trials (all of them are in the E1a cache `meta.json`), 907 unique texts after `normalize_text` (169 shorter than 15 characters). Lengths 3-116 characters, mean 42.6.
- No new LM was built. No decode with a new LM was run. No CER was computed.

## The new LM (one change from P11-11: the Willett block)
| Item | Value |
|---|---|
| Recipe | P11-11 `stage_lm`, unchanged: `build_lms.read_tatoeba("eng")` (normalised, de-duplicated) -> permutation `default_rng(20261108)` -> drop the `corpus.sentences(2000)` texts -> drop the blocked texts -> held-out = first 5,000, train = next 600,000 -> `CharNgramLM(order=6, smoothing="mkn")`, `train(normalize=False)` |
| Blocked texts, P11-11 part (kept) | the intended texts of the 16 emg2qwerty sessions (P11-09 `prompts.json`, P11-11 `intended_truth`), 2,399 texts. Kept so that the new LM differs from the P15-25 LM in **one** thing only |
| Blocked texts, new part | **every Willett sentence**: `intendedText` of all 1,000 trials of the 10 `sentences.mat` files (train, val, test and pool; excluded trials too), plus every `text` of the E1a `meta.json`; all through `normalize_text` (lower case, accents removed, non-letters -> space, spaces joined) |
| Block rule (P11-11, unchanged) | exact match after normalisation; and containment both ways (a Tatoeba sentence contains a blocked text, or a blocked text contains the Tatoeba sentence) for blocked texts of >= 15 characters and Tatoeba sentences of >= 15 characters. We import P11-11 `contains_block` (unchanged) |
| File | `C:/Users/zhang/bci-data/derived/p15-38/eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz` (local; see Licence) |

**LM0 (recipe check, before the new LM).** We rebuild the P11-11 LM with the same code path and the Willett block empty. Pass if every array and the discounts are equal to `derived/p11-11/eng_tatoeba_6gram_mkn_noE2Q.npz` (a byte hash cannot match: the zip holds time stamps). If LM0 fails, the new LM is still built and used, and the difference is reported.

**LM checks (new LM).** (a) No blocked Willett text is in the train or held-out list (exact); count must be 0. (b) No train or held-out sentence of >= 15 characters contains, or is contained in, a Willett text of >= 15 characters; count must be 0. (c) Reported: sentences removed in addition to P11-11, train size, held-out perplexity (first 2,000 held-out sentences; the held-out set shifts a little, so this number is descriptive).

## Decoders (all fixed now; no retuning)
| Id | Setting | LM | Role |
|---|---|---|---|
| G | greedy CTC | - | reference; recomputed on the P15-25 log-probs (check C0') |
| **F** | **w 0.5, beta 1, lam 0, beam 8, prune -8** (P15-25 F, unchanged) | **new LM** | **primary readout** |
| FL | w 0.25, beta 1, lam 8, beam 8, P11-11 lexicon (research only) | new LM | secondary (descriptive) |
| Fv | w 0.5, beta 2, lam 0, beam 8: the P15-25 Fv setting, **not retuned** | new LM | descriptive |
| B0 | beam 8, no LM | - | not re-run: no LM, so the P15-25 numbers hold (read from `derived/p15-25/dec/B0`) |

Decoder code: P11-07 `lmbeam.LMBeam` (imported, unchanged), same call as P15-25 `run.py` `decode` (whole sentence pushed, top-1). CER: P15-25 / E1a (Levenshtein over 98-token sequences / reference length, pooled over the 80 test sentences per run; per arm and budget the mean over 2 seeds).

## Inputs (read only)
- Log-probs: P15-25 `C:/Users/zhang/bci-data/derived/p15-25/lp/<run>/{test,shuf}.{npy,json}` (41 runs; 12 time-shuffled C1 sets). Never written.
- P15-25 per-unit decodes `derived/p15-25/dec/{G,B0,F,FL,Fv}/test/*.json` and `dec/F/shuf/*.json` (the comparison baseline).
- E1a: `derived/p15-08/willett/{meta,splits}.json`, `derived/p15-08/runs/<run>/result.json`, `experiments/2026-11-19-p15-08-e1-cross-body/config.json` (rules).

## Rules (the P15-25 rules, the same verdict code)
Verdict code: P15-25 `common.py` (`verdict`, `beats`, `bootstrap`), **imported unchanged** from the P15-25 folder (never edited). The rules, as in the [P15-25 plan](../2026-11-20-p15-25-e1-same-lm/plan.md): V1 (best arm at "all" <= 0.50), H1 (primary: E beats T at >= 2 of {3, 10, 30}), H2, H3, H4, H5, H6, roadmap rule, C1 (time-shuffled, F), C2 (label-shuffle), L1 (F lowers the CER of both E-ball runs vs G), L2 (G verdict vs F verdict). Bootstrap 10,000, seed 0, k = 13 for the Bonferroni interval. "Verdict" below means the status string (pass / partial / fail / inconclusive; pass or fail for V1, C1, C2, L1, roadmap rule).

| Id | Claim | Pass if |
|---|---|---|
| **M1 (primary)** | the P15-25 F verdicts do not depend on the Willett overlap | for each of V1, H1-H6, roadmap rule, C1, C2, L1: the status on new F equals the status on P15-25 F. "Holds" if no H1-H6 status changes. Any change is reported, not hidden |
| M2 | CER change per arm and budget | reported: new F − P15-25 F, seed means and per seed, for all 20 cells; plus the change of the full-data E (2 seeds) and R-ball-s0 |
| M3 | where the change comes from | reported: for E-ball-s0, E-ball-s1, R-ball-s0, T-ball-s0, the F CER on the 13 test sentences whose text is in the Tatoeba export vs the other 67, P15-25 LM vs new LM |
| M4 | full-data E / R change is real | reported: per run (E-ball-s0, E-ball-s1, R-ball-s0) paired bootstrap of CER_new − CER_old over the 80 test sentences (10,000, seed 0); descriptive, no threshold |
| L1, L2 | as P15-25 | on new F |

H1 on new F is the only confirmatory test (as P15-25). The other comparisons are secondary or descriptive, with the same Bonferroni rule (k = 13).

## Controls
| Id | Check | Pass if |
|---|---|---|
| LM0 | the recipe reproduces the P11-11 LM | all arrays equal (see above) |
| LMa, LMb | no Willett text in the new LM text | counts 0 |
| C0' | G on the P15-25 log-probs reproduces the P15-25 G edits | equal per-sentence edits on all 41 runs |
| R0 | the decode path reproduces P15-25 F with the old LM | F with the P11-11 LM on E-ball-s0 and R-ball-s0 test: per-sentence edits equal to P15-25 `dec/F/test` |
| LM-only | F (new LM) on all-blank and uniform log-probs, 4,100 frames | reported (as P15-25) |

If C0' or R0 fails, the new numbers are still reported, with the difference, and M1 is marked "not comparable".

## Overlap (descriptive; nothing else is blocked)
- Willett texts (test / val / pool / all, sentences and unique) in the Tatoeba export: exact, and by the containment rule.
- Willett texts in the 2,399 emg2qwerty intended texts (exact, unique): reported only.
- emg2qwerty intended texts in the Tatoeba export (exact, unique): reported only. The P11-11 LM already blocks them (P11-11 removed 1,445 extra Tatoeba sentences for them).

## EMG (P11-07 / P11-14): decided now
P11-07 and P11-14 use the P11-11 LM, which already blocks every intended text of the 16 emg2qwerty sessions they score. The new LM is used only here. So the Willett block cannot change any EMG number, and the emg2qwerty overlap is already handled. **No EMG re-measure.** The overlap stage still reports the emg2qwerty-Tatoeba and Willett-emg2qwerty counts. If the overlap stage finds an emg2qwerty test text that the P11-11 LM did **not** block (it should be 0), that becomes a new gap; it does not start an EMG re-run in this item.

## Compute, outputs, rules
| Stage | Where | Estimate |
|---|---|---|
| `blocks` | CPU, 1 process | < 1 min |
| `lm0`, `lm` | CPU, one process each | about 1-2 min each |
| `overlap`, `check`, `lmonly` | CPU | a few min |
| `test` (F, FL, Fv on 41 runs; F on 12 shuffled) | CPU, 4 single-thread workers | about 15-25 min |
| `summary` | CPU | < 1 min |

- Detached: `launch.py` -> `python -m fidetype.utils.isolation run --class background --threads 1 -- python -I run.py <stages>` (CPU only: `HIP_VISIBLE_DEVICES` and `CUDA_VISIBLE_DEVICES` empty). Log `results/run.log`; per-unit files in `C:/Users/zhang/bci-data/derived/p15-38/` only (finished units are skipped on restart); stop file `derived/p15-38/STOP`; `DONE` file at the end; keep-awake. Peak memory logged per process; target < 6 GB.
- No GPU stage: the P15-25 log-probs are reused.

## Licence
- Tatoeba text: CC BY 2.0 FR (attribution: Tatoeba contributors). The new LM is a derived work of it, and it is built with a blocklist that holds research-only emg2qwerty texts. As P11-07 / P11-11, **the LM file stays local** (`derived/p15-38/`); the repo gets its build recipe, sha256 and counts only.
- Willett data: CC0. T, E, S weights and log-probs derive from emg2qwerty (CC BY-NC-SA 4.0): research only, local only. FL uses the research-only lexicon.
- The repo gets this plan, the code and aggregate CERs only: no LM file, no log-probs, no per-sentence outputs, no text.
- No change of models, splits, LM recipe, decoders, rules or metrics after this commit. A change is an amendment with a time stamp, before the affected result.

## Gap rule
- **Gap 143 closes** when the new LM is built by the rule above (LMa and LMb at 0), all 41 runs are re-scored with F on it, and M1 (each verdict, P15-25 F vs new F) and M2 (the E / R full-data CER change) are reported under this plan, whatever the outcome.
- New limits become proposed gaps for the records agent (unnumbered).

Write-up: `results.md` in this folder, with every result, including failures.
