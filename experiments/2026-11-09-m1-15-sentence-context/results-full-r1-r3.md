---
title: M1-15 full-r1 (full cache) and r3 (causal) results, with leakage checks
type: experiment
updated: 2026-11-10
---

# M1-15 full-r1 and r3: results and leakage checks

Earlier runs (r1, r2): [results.md](results.md). Wiki summary: [m1-15-full-r1-r3-result](../../wiki/questions/m1-15-full-r1-r3-result.md).

## Answer in short
- **full-r1** (r2 settings, all 80 cached blocks, 19 participants) is the best decoder of the project. Test greedy CER **0.508** (mean over sentences) / **0.498** (mean over participants). Beam + LM **0.447** / **0.436**.
- **Like for like** (the same 209 test instances as r2): full-r1 greedy **0.497** vs r2 0.577 (−0.080 [−0.093, −0.067]). Beam + LM **0.437** vs 0.488 (−0.052 [−0.071, −0.033]).
- **r3** (causal, `lookahead_keys` 0, r2 blocks) costs nothing against r2: greedy 0.574 vs 0.577 (−0.003 [−0.011, +0.005]). Beam + LM 0.472 vs 0.488 (−0.016 [−0.032, −0.001]).
- **Leakage:** no exact leakage. 0 of the 17 test and 0 of the 11 val sentences are in train. 0 test or val sentences are in the LM training text (exact match or containment).
- **Near-variant memorisation: yes, partly.** SpanishBCBL has sentence pairs such as "las agencias disponen los equipos" (train) and "las agencias disponen los equipos por la manana" (test). The split hashes the exact text, so the two forms can fall in different splits. 6 of the 17 test sentences have a train sentence within CER 0.25. On these 6, the Transformer head is much better than on the other 11. The Conv-only head is not. We estimate that this gives full-r1 about 0.013 greedy and 0.022 beam CER. On the 11 test sentences with no close train variant, full-r1 greedy CER is **0.525** and beam + LM **0.474**.
- **M1 target (greedy ≈ 0.59):** met in the synchronous setting (oracle key timing), also on the "far" sentences and with the causal model. **Not met in the async setting** of v2, which the target refers to. Every M1-15 number uses the key times from the keyboard log.
- **eWPM:** full-r1 trust **3.23** vs gaze typing only **3.15**. This is the first time trust is above gaze only, but the trust CI [3.08, 3.40] contains 3.15. r3: trust 3.09 vs 3.14.

## Set-up
| Item | full-r1 | r3 |
|---|---|---|
| Config | [config-full-r1.json](config-full-r1.json) | [config-r3.json](config-r3.json) |
| Change from r2 | `subjects` and `blocks` null: all 80 cached blocks, 23 subject IDs = 19 participants | `lookahead_keys` 0 (key i sees keys 0..i only) |
| Data (sentence instances train / val / test) | 4026 / 437 / 637 | 947 / 114 / 209 (= r2) |
| Unique sentences train / val / test | 101 / 11 / 17 | 101 / 11 / 17 |
| Stop settings | `patience_evals` 12, `max_lr_reductions` 2 (a cap), plateau schedule as r2 | same |
| Training | queue-2026-11-10b, 20:53:29–22:00:02, 66.5 active min = wall clock, no suspend gap. Early stop at epoch 79. `best.pt` = epoch 77 (val CER typed 0.4865, mean over participants) | 22:21:51–22:33:26, 11.5 active min. Early stop at epoch 37. `best.pt` = epoch 24 (0.5551) |
| Inference | `infer_sentence --control --lm spa_tatoeba_6gram_mkn.npz --lm-weights 0.25 0.5 1.0 1.25 2.0`, `--head final` and `--head conv` | same |
| LM weight (picked on val) | final 1.25, conv 1.0 | final 1.25, conv 1.0 |

The full cache adds people and repetitions, not new sentences. Each of the 17 test sentences appears about 40 times (once per participant block). Exception: "los ninos mayores acaba la escuela" appears once.

## Metric note (read first)
- CER is vs the prompted (target) text.
- Two means exist. **Mean over sentences** (all instances weigh the same) is the r1 / r2 convention in [results.md](results.md). **Mean over participants** (each person weighs the same; S1/S18, S4/S14 and S5/S10/S21 merged) is the `infer.log` headline.
- For r2 and r3 the two means are almost equal. For full-r1 they differ by about 0.01: mean over participants is lower (0.498 vs 0.508 greedy).
- The numbers 0.498 / 0.436 (full-r1) and 0.574 / 0.480 (r3) in the queue summary are **means over participants**. r2's 0.577 / 0.488 is a **mean over sentences** (r2 over participants: 0.577 / 0.493). Compare like with like.

## Test results (CER vs target)
| run | head | decoder | real (sentences / participants) | shuffled | zeros | gap shuffled − real [95 % CI] |
|---|---|---|---|---|---|---|
| r2 | Conv + Trans | greedy | 0.577 / 0.577 | 0.791 | 0.841 | +0.214 [+0.200, +0.228] |
| r2 | Conv + Trans | beam + LM | 0.488 / 0.493 | 0.746 | 0.750 | +0.258 [+0.238, +0.278] |
| r2 | Conv only | greedy | 0.602 / 0.605 | 0.807 | 0.901 | +0.205 [+0.189, +0.221] |
| r2 | Conv only | beam + LM | 0.503 / 0.500 | 0.763 | 0.775 | +0.259 [+0.240, +0.280] |
| **full-r1** | Conv + Trans | greedy | **0.508 / 0.498** | 0.784 | 0.808 | +0.276 [+0.266, +0.286] |
| **full-r1** | Conv + Trans | beam + LM | **0.447 / 0.436** | 0.741 | 0.755 | +0.294 [+0.282, +0.307] |
| full-r1 | Conv only | greedy | 0.590 / 0.582 | 0.819 | 0.885 | +0.229 [+0.220, +0.238] |
| full-r1 | Conv only | beam + LM | 0.489 / 0.477 | 0.772 | 0.763 | +0.283 [+0.270, +0.296] |
| r3 (causal) | Conv + Trans | greedy | 0.574 / 0.574 | 0.788 | 0.845 | +0.214 [+0.198, +0.230] |
| r3 (causal) | Conv + Trans | beam + LM | 0.472 / 0.480 | 0.744 | 0.750 | +0.272 [+0.250, +0.294] |
| r3 (causal) | Conv only | greedy | 0.612 / 0.608 | 0.810 | 0.901 | +0.198 [+0.183, +0.214] |
| r3 (causal) | Conv only | beam + LM | 0.494 / 0.490 | 0.765 | 0.767 | +0.272 [+0.250, +0.294] |

Shuffled and zeros columns: mean over sentences. Gap CIs: paired bootstrap over sentences, 10,000 resamples. No resample is ≤ 0 in any row. No test sentence has CER 0, except 1 r3 beam + LM instance (0.5 %).

## Val results (CER vs target)
| run | head | decoder | real (sentences / participants) | shuffled | zeros | gap [95 % CI] |
|---|---|---|---|---|---|---|
| full-r1 | Conv + Trans | greedy | 0.514 / 0.502 | 0.764 | 0.771 | +0.250 [+0.239, +0.262] |
| full-r1 | Conv + Trans | beam + LM | 0.465 / 0.452 | 0.719 | 0.710 | +0.254 [+0.240, +0.269] |
| full-r1 | Conv only | greedy | 0.590 / 0.580 | 0.811 | 0.892 | +0.221 [+0.209, +0.233] |
| full-r1 | Conv only | beam + LM | 0.495 / 0.480 | 0.763 | 0.752 | +0.268 [+0.252, +0.284] |
| r3 | Conv + Trans | greedy | 0.558 / 0.570 | 0.775 | 0.838 | +0.217 [+0.195, +0.239] |
| r3 | Conv + Trans | beam + LM | 0.450 / 0.471 | 0.733 | 0.705 | +0.282 [+0.252, +0.312] |
| r3 | Conv only | greedy | 0.596 / 0.608 | 0.793 | 0.903 | +0.197 [+0.174, +0.219] |
| r3 | Conv only | beam + LM | 0.486 / 0.502 | 0.751 | 0.736 | +0.265 [+0.234, +0.296] |

Val is optimistic for two reasons: `best.pt` and the LM weight were both picked on val. Val `lm_weight` scores (mean over participants), full-r1 final head: 0.25 → 0.482, 0.5 → 0.465, 1.0 → 0.453, **1.25 → 0.452**, 2.0 → 0.463.

## Like-for-like comparison with r2
All runs write per-sentence files with the block and trial in the file name (for example `S1_ses1_block2_3.npz`). All 209 r2 test instances and 114 r2 val instances are in the full-r1 sets with the same target text. So no new inference was needed. Paired bootstrap over instances, 10,000 resamples.

| split | head | decoder | r2 | full-r1, same instances | full-r1 − r2 [95 % CI] | full-r1, the other instances | r3 | r3 − r2 [95 % CI] |
|---|---|---|---|---|---|---|---|---|
| test (209) | Conv + Trans | greedy | 0.577 | **0.497** | **−0.080** [−0.093, −0.067] | 0.514 (428) | 0.574 | −0.003 [−0.011, +0.005] |
| test (209) | Conv + Trans | beam + LM | 0.488 | **0.437** | **−0.052** [−0.071, −0.033] | 0.452 | 0.472 | −0.016 [−0.032, −0.001] |
| test (209) | Conv only | greedy | 0.602 | 0.580 | −0.022 [−0.034, −0.010] | 0.595 | 0.612 | +0.010 [+0.002, +0.018] |
| test (209) | Conv only | beam + LM | 0.503 | 0.484 | −0.019 [−0.037, −0.002] | 0.491 | 0.494 | −0.009 [−0.022, +0.003] |
| val (114) | Conv + Trans | greedy | 0.560 | 0.502 | −0.057 [−0.074, −0.041] | 0.517 | 0.558 | −0.002 [−0.013, +0.010] |
| val (114) | Conv + Trans | beam + LM | 0.454 | 0.461 | +0.007 [−0.018, +0.032] | 0.467 | 0.450 | −0.004 [−0.023, +0.016] |
| val (114) | Conv only | greedy | 0.588 | 0.589 | +0.001 [−0.014, +0.016] | 0.591 | 0.596 | +0.009 [−0.002, +0.019] |
| val (114) | Conv only | beam + LM | 0.480 | 0.493 | +0.013 [−0.012, +0.038] | 0.496 | 0.486 | +0.006 [−0.014, +0.027] |

Means over sentences. On the r2 test instances, mean over participants: full-r1 0.504 greedy, 0.445 beam + LM (r2: 0.577 / 0.493).

- The full cache helps the Transformer head much more than the Conv-only head (test greedy −0.080 vs −0.022).
- On val, the beam + LM gain disappears (+0.007, CI crosses 0). Only 11 val sentences exist, so val is noisy at the sentence level.
- Causality (r3) costs nothing measurable. With oracle key timing, the right context inside a sentence does not help this model.

## Per participant (full-r1 test, CER vs target, mean over that person's instances)
| participant | subject IDs | n | n in r2 test | greedy | beam + LM | Conv-only greedy |
|---|---|---|---|---|---|---|
| P01 | S1 + S18 | 61 | 43 | 0.539 | 0.487 | 0.627 |
| P02 | S2 | 32 | 0 | 0.531 | 0.454 | 0.611 |
| P03 | S3 | 18 | 15 | 0.546 | 0.498 | 0.655 |
| P04 | S4 + S14 | 64 | 0 | 0.558 | 0.489 | 0.629 |
| P05 | S5 + S10 + S21 | 66 | 3 | 0.591 | 0.545 | 0.657 |
| P06 | S6 | 29 | 0 | 0.414 | 0.360 | 0.523 |
| P07 | S7 | 32 | 0 | 0.444 | 0.375 | 0.529 |
| P08 | S8 | 29 | 0 | 0.487 | 0.437 | 0.577 |
| P09 | S9 | 19 | 13 | 0.453 | 0.410 | 0.535 |
| P11 | S11 | 32 | 26 | 0.551 | 0.495 | 0.663 |
| P12 | S12 | 16 | 13 | 0.608 | 0.547 | 0.682 |
| P15 | S15 | 32 | 26 | **0.351** | **0.260** | 0.455 |
| P16 | S16 | 16 | 13 | 0.384 | 0.314 | 0.475 |
| P17 | S17 | 32 | 0 | 0.494 | 0.419 | 0.574 |
| P19 | S19 | 31 | 25 | 0.494 | 0.427 | 0.554 |
| P20 | S20 | 32 | 0 | **0.632** | 0.579 | 0.694 |
| P22 | S22 | 32 | 0 | 0.471 | 0.411 | 0.557 |
| P24 | S24 | 32 | 0 | 0.441 | 0.368 | 0.517 |
| P25 | S25 | 32 | 32 | 0.473 | 0.412 | 0.534 |

- 16 of 19 participants are below greedy 0.59. P05 (0.591), P12 (0.608) and P20 (0.632) are above it.
- The merged people (P01, P04, P05) have 2–3× the data of the others but are not better. P05 (3 subject IDs) is second worst.
- P15 and P16 are best, as in r1 and r2.

## Leakage and memorisation checks
Scripts: [analysis/leak.py](analysis/leak.py), [analysis/analyse.py](analysis/analyse.py), [analysis/extra.py](analysis/extra.py) (CPU, about 3 min). Output: [results/leakage-analysis-full-r1-r3.json](results/leakage-analysis-full-r1-r3.json).

### a. Do test or val sentences appear in train?
- **No.** `assign_split` (`src/fidetype/data/preprocess.py`) hashes the normalised target text (SHA-1, 80/10/10). Every repetition of a sentence, in any subject, gets the same split.
- Check on all 80 cache sidecars: the stored split equals the hash rule for every segment (0 mismatches). Exact overlap test ∩ train = 0, val ∩ train = 0, test ∩ val = 0.
- The cache holds 24 test / 16 val / 183 train unique sentences. The decoder drops the practice trials (`is_training` = true), so the runs use 17 / 11 / 101.
- The S1/S18, S4/S14 and S5/S10/S21 merges do not matter here: the split is by sentence, so no person sees a test sentence in training.

### b. Does the beam LM's training text contain test sentences?
- The beam uses `spa_tatoeba_6gram_mkn.npz`: a character 6-gram (modified Kneser-Ney) trained on the Spanish Tatoeba export (434,443 sentences). It is not trained on SpanishBCBL text. Build script: `experiments/2026-11-08-lm-beam/build_lms.py`.
- The build removes all 226 SpanishBCBL targets (exact match), and every Tatoeba sentence that contains a target of 15+ characters or is contained in one. It removed 2 sentences.
- Our re-check (normalised text): the 24 test, 16 val and 183 train sentences are all in the blocklist. Raw Tatoeba has 0 exact matches for test and val (1 for train: "las calles de esta ciudad son estrechas"). 0 Tatoeba sentences contain a test or val sentence. After the exclusion: 0 exact matches, 0 containments.
- Word 4-gram overlap with the LM text: 0 of the 54 word 4-grams of the 17 test sentences. Over all 24 cache test sentences, 1 word 4-gram is shared ("los accesos a la estacion son numerosos", a sentence that occurs only as a practice trial).
- **Verdict: no LM leakage.** A re-score with another LM is not necessary.

### c. Near-variant sentences (a partial memorisation path)
SpanishBCBL builds sentences in pairs: a short form and a long form, or a singular and a plural form. The hash split treats each form as a different sentence. So a test sentence can have a close variant in train.

| test sentence | closest train sentence | CER between them |
|---|---|---|
| los ninos mayores acaba la escuela (n = 1) | los ninos mayores acaban la escuela | 0.029 |
| el cliente establece la conexion creada | el cliente establece las conexiones | 0.179 |
| la revolucion nueva abarca las esferas | las revoluciones abarcan las esferas | 0.184 |
| la diversidad dificulta la relacion | la diversidad previa dificulta la relacion | 0.200 |
| los productos cumplen la propiedad asociada | los productos cumplen la propiedad | 0.209 |
| el centro describe las parabolas asociadas | el centro describe las parabolas | 0.238 |
| 11 other test sentences | — | 0.28–0.48 |

Split of the test results at nearest-train CER 0.25 ("close": 6 sentences, 199 instances; "far": 11 sentences, 438 instances). Mean over sentences:

| run / head | greedy close | greedy far | gap far − close | beam + LM close | beam + LM far | gap |
|---|---|---|---|---|---|---|
| full-r1 Conv + Trans | 0.471 | **0.525** | **0.054** | 0.388 | **0.474** | **0.086** |
| full-r1 Conv only | 0.581 | 0.594 | 0.012 | 0.478 | 0.494 | 0.016 |
| r2 Conv + Trans | 0.562 | 0.584 | 0.022 | 0.461 | 0.501 | 0.040 |
| r2 Conv only | 0.594 | 0.605 | 0.011 | 0.493 | 0.508 | 0.015 |
| r3 Conv + Trans | 0.561 | 0.580 | 0.019 | 0.443 | 0.485 | 0.042 |
| r3 Conv only | 0.603 | 0.616 | 0.013 | 0.483 | 0.499 | 0.016 |

- The Conv-only head sees one key at a time. Its close − far gap (0.011–0.016) measures how much easier the "close" sentences are by themselves.
- The Transformer head has a larger gap, and the gap grows with more repetitions of the same 101 train sentences: 0.022 (r2) → 0.054 (full-r1) greedy.
- The extra gap (difference in differences, full-r1) is about 0.042 greedy and 0.070 beam + LM on the 199 close instances. Spread over all 637 test instances, this is about **0.013 greedy and 0.022 beam + LM CER**.
- The model does not copy train sentences: 0 of 637 greedy outputs and 1 of 637 beam outputs equal a train sentence.
- The "far" numbers (greedy 0.525, beam + LM 0.474) are the cleaner estimate for new sentences. They are still well below r2 (far: 0.584 / 0.501).

> **Our take:** This is not leakage of test sentences. It is a property of the corpus: the sentences share templates, and the Transformer learns them. A real user's sentences would not have a close variant in our train set. So report the "far" numbers next to the headline. A cleaner fix is a split by sentence family (group the variant pairs before the hash). We did not do this here, because it changes the split of all past results.

### d. Why the zeros control gives CER about 0.8, not 1.0
The decoder gets the key times, so it outputs exactly one character per key. The output length is right, and the CER counts only substitutions plus a few alignment shifts. Any character that lands on the right position by chance lowers the CER. Text-only baselines on the 637 full-r1 test instances (output length = target length):

| text-only output (no MEG) | test CER |
|---|---|
| empty string | 1.000 |
| "eeee…" | 0.888 |
| spaces only | 0.867 |
| most frequent train character at each position | 0.750 |
| one fixed train sentence, picked on train ("las calles marcan las lineas") | **0.688** |
| zeros input, full-r1 Conv + Trans, greedy | 0.808 |
| zeros input, full-r1 Conv only, greedy | 0.885 |
| zeros input, full-r1, beam + LM | 0.755 |
| shuffled MEG, full-r1, greedy | 0.784 |

- So a CER of about 0.7–0.8 needs no brain signal at all. The text-only floor is about 0.69, not 1.0.
- With zeros, the Transformer head (0.808) beats the Conv-only head (0.885). The difference (0.08) is a learned position and language prior.
- **Meaning for 0.498 / 0.508:** the real-MEG greedy CER is about 0.18–0.19 below the best text-only baseline, and 0.28 below the shuffled control. That part comes from the MEG. The step from 1.0 to about 0.7 does not.
- Small caveat on the shuffled control: it takes the windows of another instance of the same split. In the full-r1 test set, 32 of 637 partners (5 %) are another person typing the same sentence. This makes the shuffled CER a little too low, so the gap is a little conservative.

## Trust-layer check (eWPM)
Same harness as r1 / r2 (`ewpm_check.py <run> <out>`: M2-14 real-MEG harness, `RETUNED` beam, `lm_weight` 0.5, `n_best` 10, frame calibration, fit on val, user `aac_gaze()`). CPU only. full-r1: 967 s (637 test trials); r3: 258 s. Files: `results/ewpm-full-r1/real.json`, `results/ewpm-r3/real.json` (+ `ewpm_log.txt`).

### Main run (test)
| policy | r2 | **full-r1** | r3 |
|---|---|---|---|
| always commit LM top-1 | 2.49 | 2.71 | 2.57 |
| trust, no OFFER_WORDS | 3.06 | **3.23** | 3.09 |
| trust + OFFER_WORDS (`trust_ow`) | 3.06 | 3.23 | 3.09 |
| trust, silent variant | 3.06 | 3.23 | 3.09 |
| trust + OFFER_WORDS, silent | 3.06 | 3.23 | 3.09 |
| diag: OFFER_WORDS always | 2.95 | 3.11 | 2.97 |
| gaze typing only (no BCI) | 3.14 | **3.15** | 3.14 |
| trust eWPM 95 % CI (sentence bootstrap) | [2.93, 3.19] | [3.08, 3.40] | [2.97, 3.23] |
| trust − commit [95 % CI] | [+0.35, +0.83] | [+0.40, +0.63] | [+0.29, +0.83] |
| wrong-commit: commit / trust / trust_ow | 1.000 / 0 / 0 | 1.000 / 0 / 0.002 | 0.995 / 0 / 0 |
| silent error rate, commit | 0.215 | 0.199 | 0.196 |
| harness CER / system word accuracy | 0.491 / 0.178 | 0.451 / 0.232 | 0.479 / 0.193 |
| top-1 sentence accuracy | 0.000 | 0.000 | 0.005 |
| n-best miss rate (truth not in the 10-best) | 0.995 | 0.994 | 0.995 |
| trust: words selected from offers / typed | 0.26 / 0.74 | 0.31 / 0.69 | 0.27 / 0.74 |
| trust: keystrokes saved | −0.00 | 0.06 | 0.01 |

The trust policy OFFERs on every trial (rate_offer 1.0; trust_ow 0.998). full-r1 uses its own 637 test trials (19 participants), so its eWPM column is not like for like with r2 and r3 (209 trials).

### Sensitivity runs (test eWPM: commit / trust / trust_ow; gaze only)
| user variant | r2 | full-r1 | r3 |
|---|---|---|---|
| fallback 40 cpm | 4.18 / 4.95 / 4.95; gaze 6.29 | 4.45 / 5.15 / 5.15; gaze 6.31 | 4.32 / 4.98 / 4.98; gaze 6.29 |
| `p_miss_unflagged` 0 | 3.09 / 3.06 / 3.06; gaze 3.14 | **3.27** / 3.23 / 3.23; gaze 3.15 | 3.13 / 3.09 / 3.09; gaze 3.14 |
| `p_miss_unflagged` 0.2 | 1.11 / 3.06 / 3.06; gaze 3.14 | 1.45 / 3.23 / 3.23; gaze 3.15 | 1.14 / 3.09 / 3.09; gaze 3.14 |
| slow selection (scan, select, nav ×2) | 2.43 / 2.85 / 2.85; gaze 3.14 | 2.60 / 2.99 / 2.99; gaze 3.15 | 2.52 / 2.89 / 2.89; gaze 3.14 |
| no full retype | 2.49 / 3.05 / 3.05; gaze 3.14 | 2.70 / 3.22 / 3.22; gaze 3.15 | 2.57 / 3.08 / 3.08; gaze 3.14 |
| no typing after ABSTAIN | 2.49 / 3.06 / 3.06; gaze 3.14 | 2.71 / 3.23 / 3.23; gaze 3.15 | 2.57 / 3.09 / 3.09; gaze 3.14 |

- full-r1 is the first decoder where trust (3.23) is above gaze only (3.15) in the main run. The trust CI [3.08, 3.40] contains 3.15, so this is not a clear win. No paired trust − gaze test exists in the harness.
- In the `p_miss_unflagged` 0 variant (the user catches every error), always commit (3.27) is also above gaze only.
- With a 40 cpm fallback or slow selection, gaze only stays faster.
- The true sentence is still in the 10-best for fewer than 1 % of trials. The gain comes from word offers (31 % of the words), not from whole-sentence hits.

> **Our take:** The BCI now reaches parity with gaze typing, not a clear gain. The trust layer still adds safety (wrong-commit 1.0 → 0) at no speed cost against always commit (+0.40 to +0.63 eWPM). A clear gain needs the true sentence in the n-best for a real share of trials.

## Is the M1 target met?
| criterion | value | met? |
|---|---|---|
| "Greedy CER approaches v2's async SpanishBCBL CER (≈ 0.59) or is better" ([project plan](../../wiki/questions/project-plan.md)) | async CTC decoder (M1-C r4b): 0.619 greedy, 0.590 beam + LM | **no** (async) |
| same number, synchronous setting (oracle key timing) | full-r1 0.508 (sentences) / 0.498 (participants); far sentences 0.525; r3 causal 0.574 | yes (sync only) |

> **Our take:** All M1-15 runs use oracle key times from the keyboard log. v2's 0.59 needs no key times. So the M1 criterion is met only in the easier, synchronous setting. The async decoder (M1-C r4b, 0.619) has not been retrained on the full cache yet (M1-09). Closing M1 needs either a decision to accept the synchronous setting, or an async decoder at or below 0.59.

## Limits
- One seed per run. Differences of about 0.01 are within seed noise (not measured).
- Oracle key timing in all M1-15 runs (also r3: causal over keys, but the key times are known).
- Only 17 test and 11 val sentences. Instance-level CIs understate the sentence-level uncertainty. The val beam + LM result (no gain over r2) shows this.
- `best.pt` (epoch 77) was the second-last eval of full-r1. The val CER was still falling slowly. A longer run might help a little.
- The near-variant effect is an estimate from 6 vs 11 sentences. It assumes that the Conv-only head measures the "easiness" of the close sentences.
- The shuffled-control partner index assumes that the dataset order equals the `labels.jsonl` order.

## Files
- Metrics: `results/metrics-full-r1.json`, `results/metrics-full-r1-head-conv.json`, `results/metrics-r3.json`, `results/metrics-r3-head-conv.json`.
- Logs: `results/train_log-full-r1.txt`, `results/train_log-r3.txt`, `results/infer_log-full-r1*.txt`, `results/infer_log-r3*.txt`.
- eWPM: `results/ewpm-full-r1/`, `results/ewpm-r3/` (`real.json` + `ewpm_log.txt`).
- Leakage and like-for-like analysis: `analysis/*.py`, `results/leakage-analysis-full-r1-r3.json`.
- Outside the repo: checkpoints `C:\Users\zhang\bci-data\runs\m1-15-sentence-context-{full-r1,r3}\`, streams and per-sentence files `C:\Users\zhang\bci-data\streams\m1-15-sentence-context-{full-r1,r3}[_head-conv]\`.

## Reproduce
```powershell
.\experiments\2026-11-09-m1-15-sentence-context\launch.ps1 -Config experiments\2026-11-09-m1-15-sentence-context\config-full-r1.json -RunName m1-15-sentence-context-full-r1
C:\venvs\fidetype-rocm\Scripts\python.exe -m fidetype.decoders.infer_sentence --run-dir C:/Users/zhang/bci-data/runs/m1-15-sentence-context-full-r1 --control --lm C:/Users/zhang/bci-data/lm/spa_tatoeba_6gram_mkn.npz --lm-weights 0.25 0.5 1.0 1.25 2.0 --head final
C:\venvs\fidetype-rocm\Scripts\python.exe -m fidetype.decoders.infer_sentence --run-dir C:/Users/zhang/bci-data/runs/m1-15-sentence-context-full-r1 --control --lm C:/Users/zhang/bci-data/lm/spa_tatoeba_6gram_mkn.npz --lm-weights 0.25 0.5 1.0 1.25 2.0 --head conv
.venv\Scripts\python.exe experiments\2026-11-09-m1-15-sentence-context\ewpm_check.py full-r1 ewpm-full-r1
# r3: the same with config-r3.json / m1-15-sentence-context-r3 / ewpm_check.py r3 ewpm-r3
.venv\Scripts\python.exe experiments\2026-11-09-m1-15-sentence-context\analysis\leak.py
.venv\Scripts\python.exe experiments\2026-11-09-m1-15-sentence-context\analysis\analyse.py
.venv\Scripts\python.exe experiments\2026-11-09-m1-15-sentence-context\analysis\extra.py
```
