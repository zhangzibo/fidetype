---
title: Trust core on Brain-to-Text '25 copy-task logits (intracortical, T15)
type: experiment
updated: 2026-11-10
---

# Trust core on a second device type: intracortical speech (Brain-to-Text '25)

First test of the NeuralTextStream (NTS) spec and the trust layer on a device that is not MEG. Data: `t15_copyTask.pkl` (Card et al. 2024, Dryad, CC0), the online phoneme CTC logits of a 256-electrode speech BCI. CPU only, 2 threads.

- Code: adapter `src/fidetype/adapters/b2t25.py`, phoneme → words `src/fidetype/lm/phoneme_words.py`, harness change `Item(stream_text=...)` in `src/fidetype/eval/harness.py`. Tests: `tests/test_adapter_b2t25.py` (17).
- Script: [run.py](run.py) (stages `prep`, `tune`, `trust`, `extra`, `tables`). Settings: [config.json](config.json). All tables: [results/tables.md](results/tables.md). Numbers: `results/prep.json`, `results/tune.json`, `results/trust.json`. Log: `results/run.log`.
- Run: `.venv\Scripts\python.exe -I experiments/2026-11-10-b2t25-trust/run.py` (about 45 min on CPU; the `extra` stage was added after the first run, see "Fixes").
- Source page: [wiki/sources/brain-to-text-25-copytask.md](../../wiki/sources/brain-to-text-25-copytask.md). Wiki result: [b2t25-trust-result](../../wiki/questions/b2t25-trust-result.md).

## Main finding
The trust core works unchanged on intracortical phoneme logits, and this time the test is **not degenerate**: the right sentence is the top-1 for 39 % (our decoder) and 81 % (published decoder) of test trials. On both decoders, the trust policy cuts wrong commits by 4–10× for a speed cost of 0 to 4 %:

| decoder | always commit: eWPM / wrong-commit / silent error | trust: eWPM / wrong-commit / silent error |
|---|---|---|
| ours (CMUdict + word unigram + char 6-gram) | 11.45 / 0.610 / 0.044 | 11.55 / **0.059** / 0.002 |
| published online decoder (5-gram + OPT), gated by our neural evidence | 19.61 / 0.194 / 0.025 | 18.77 / **0.044** / 0.004 |
| gaze typing only (no BCI) | 4.08 | — |

All BCI policies here are **far above** gaze typing alone (4.08 eWPM). On real MEG, no policy was (trust 2.96–3.06 vs gaze 3.14).

## Setting
| item | value |
|---|---|
| Trials | 1,718 in the file. Main analysis: the 1,628 trials with the 125,000-word vocabulary (the 90 50-word trials are reported for the published decoder only) |
| Split | Per post-implant day, in file order: first half → fit (812 trials), second half → test (816). One sentence occurs in both |
| Truth | Words: the cue sentence, lower case, `a`–`z`, `'` and spaces (`normalize_words`). Phonemes: `cue_sentence_phonemes` |
| Stream | `vocab_type="phoneme"`, 41 tokens (blank, `SIL`, 39 ARPAbet), `frame_period` 0.08 s, `latency` 0, frame time = end of a 14 × 20 ms patch (inferred). `log_softmax` of the logits. No text in `meta`. For the trust core: one-character-per-token form (`to_symbol_stream`, `SIL` → space) |
| User model | `UserConfig.aac_gaze()` with `chars_per_min` = 159.3, the measured T15 copy-task speech rate (32.4 words/min). Fallback typing 20 chars/min (gaze keyboard, as for MEG) |
| Fit | `TrustPipeline.fit(fit, fit)` as in M2-10: frame T and sentence T on the first half of `fit`, conformal on the second half, policy on all of `fit`; limit wrong-commit ≤ 0.05 |
| CIs | 95 %, 1000 resamples: trials `[...]` and day clusters `{...}` (14 test days) |

## Decoding route (why this one)
- Phoneme CTC → words needs a lexicon and an LM. The challenge LMs (3-gram 60 GB RAM, 5-gram 300 GB RAM, OPT 6.7B) do not fit our limits and their code has no licence.
- Our route, all licence-clean: (1) CTC prefix beam over phonemes, no LM (beam 64, 20-best); (2) split at `SIL`; (3) look up each segment in **CMUdict** (BSD-2-Clause style; 124,926 words) with 1–2 phoneme edits (SymSpell-style deletion index; nearest-word fallback over words seen ≥ 5 times); (4) beam over the segments with an edit penalty and a **Tatoeba English word unigram** (CC BY 2.0 FR; 82,442 word types); (5) rescore with our existing **Tatoeba English char 6-gram LM**. Per-character confidence = the lowest frame posterior of the word's phonemes × 0.5^edits.
- Tuned on 400 fit trials (grid of 12; [tables](results/tables.md)): `lm_weight` 1.0, `edit_penalty` 12, `word_bonus` 3. The best value of `edit_penalty` is at the grid edge.
- We also ran the trust core at **phoneme level** (truth = phoneme string; no lexicon, no LM).

## Decoders (test, 816 trials)
| decoder | WER | CER | sentence exact | truth in n-best |
|---|---|---|---|---|
| published online decoder (from the file) | **0.0431** | 0.031 | 0.806 | — |
| ours: greedy phonemes → lexicon top-1 | 0.1715 | 0.110 | 0.335 | — |
| ours: beam 20-best → words, 10-best | **0.1491** | 0.095 | 0.390 | 0.623 |
| phoneme level: greedy / beam (PER, `SIL` counted) | — | 0.097 / 0.094 | 0.244 / 0.246 | 0.429 |

**Published WER (quoted exactly).** The paper abstract says "99.6% accuracy with a 50-word vocabulary" on the first day, "90.2% accuracy using a 125,000-word vocabulary" on the second day, and "sustained 97.5% accuracy over a period of 8.4 months". From the file we compute: day 25 (50-word) WER **0.0044** (= 99.56 % accuracy, matches 99.6 %); all 1,718 trials pooled **0.0434**; 125k trials pooled 0.0450; per day 0.0099 to 0.1361 (day 34). The "97.5 %" figure is an aggregate that we did not reproduce from the pooled data (possibly a mean over sessions or another subset). Day 27 mixes both vocabularies here (WER 0.0508).

## Trust harness, word level (test 816 trials)
| policy | eWPM [trial] {day} | wrong-commit | silent error | COMMIT / OFFER |
|---|---|---|---|---|
| (a) always commit, greedy → words | 10.49 [10.01, 10.98] {9.84, 11.23} | 0.665 | 0.051 | 1.00 / 0 |
| (p) always commit the published sentence | **19.61** [18.68, 20.51] {17.76, 21.45} | 0.194 [0.167, 0.222] | 0.025 | 1.00 / 0 |
| (b) always commit our top-1 | 11.45 [10.95, 12.04] {10.72, 12.32} | 0.610 [0.574, 0.645] | 0.044 | 1.00 / 0 |
| (c) **trust** on our n-best | 11.55 [11.03, 12.06] {10.85, 12.38} | **0.059** [0.043, 0.075] | 0.002 | 0.23 / 0.77 |
| (d) (c) without calibration | 11.57 [11.04, 12.12] {10.79, 12.53} | 0.071 [0.054, 0.088] | 0.006 | 0.26 / 0.74 |
| (e) (c) without guard | 11.51 [11.00, 12.02] {10.81, 12.36} | 0.036 [0.023, 0.048] | 0.000 | 0.17 / 0.83 |
| (q) **trust gate on the published sentence** | **18.77** [17.88, 19.62] {17.05, 20.46} | **0.044** [0.031, 0.059] | 0.004 | 0.47 / 0.53 |
| gaze typing only | 4.08 [4.04, 4.12] | 0 | 0 | — |

Paired differences (trial CI; day CI in [tables](results/tables.md)):
- (c) − (b): eWPM [−0.11, +0.30]; wrong-commit [−0.587, −0.516]; silent error [−0.055, −0.029].
- (q) − (p): eWPM [−0.98, −0.72] (−4.3 %); wrong-commit [−0.175, −0.126]; silent error [−0.032, −0.011].
- (c) − gaze: eWPM [+6.96, +7.97]. (q) − gaze: [+13.81, +15.53].

**Policy (q).** The candidate list is the published sentence on top of our 10-best (score = our best + 2.0). A published word gets the acoustic confidence of the same word in our top-1 (word alignment), else 0. So the guard asks: "how much of the LM-rescored text does the neural evidence confirm?" The decoder is a black box; the trust core sees only the NTS stream and the text.

## Calibration and error prediction (word level, test)
| item | ours (c) | published gate (q) |
|---|---|---|
| frame T / sentence T | 3.78 / 4.56 | 3.78 / 1.72 |
| sentence ECE before → after | 0.448 → **0.067** | 0.102 → 0.058 |
| token (phoneme peak) ECE before → after | 0.090 → 0.130 (worse) | same |
| conformal coverage (target 0.9) / mean set size | 0.559 / 3.40 (n-best miss 0.38) | 0.766 / 0.94 |
| AUROC "top-1 wrong": −p_top1 / guard risk / inconsistency / low evidence | **0.797** / 0.702 / 0.715 / 0.701 | 0.710 / 0.667 / 0.737 / 0.667 |
| AUROC "word wrong": word confidence (min over its characters) | **0.844** (5,118 top-1 words, 14.7 % wrong) | — |
| AUROC "published sentence wrong": our risk / our −p_top1 | 0.661 / 0.662 | — |

Phoneme level: AUROC −p_top1 **0.884**, guard risk 0.825, low evidence 0.842.

Selective use of the published sentence, ranked by our p_top1 (no published confidence needed):

| coverage | published WER | published sentence error |
|---|---|---|
| 0.5 | 0.0261 | 0.130 |
| 0.7 | 0.0285 | 0.137 |
| 0.9 | 0.0391 | 0.176 |
| 1.0 | 0.0431 | 0.194 |

- The logits are strongly over-confident: the frame temperature is 3.78. Frame T fixes the sentence posteriors (ECE 0.448 → 0.067) but makes the phoneme peak ECE worse (0.090 → 0.130). The NLL-optimal T is not the ECE-optimal T for the peaks.
- Calibration does not change the policy result much: (d) without calibration has 0.071 wrong commits vs 0.059.
- The guard does not help on this decoder: (e) without it has fewer wrong commits (0.036) at the same eWPM. −p_top1 is the best single signal (as on the simulator, unlike real MEG).
- The fitted limit was 0.05; the test wrong-commit rate of (c) is 0.059 [0.043, 0.075]. The limit holds only approximately: the policy fit has no finite-sample guarantee (task M2-13).

## Null-input audit (word level, 300 random test trials)
| policy | real: commit / wrong commit | other trial's stream | frame-shuffled | uniform |
|---|---|---|---|---|
| (b) always commit | 1.00 / 0.64 | commit 1.00, fluent 1.00 | commit 1.00, fluent 1.00 | commit 1.00, fluent 0.09 |
| (c) trust | 0.22 / 0.07 | **commit 0.22** | 0.00 | 0.00 |
| (d) no calibration | 0.25 / 0.08 | 0.25 | 0.00 | 0.00 |
| (q) published gate | 0.48 / 0.05 | **0.00** | 0.00 | 0.00 |

- "Fluent" = ≥ 2 words and ≥ 80 % in CMUdict. Our decoder outputs only lexicon words, so its text is always "fluent" on any input: real output and hallucination look the same, as with the MEG LM.
- Frame-shuffled and uniform streams: the trust policy commits nothing (risk AUROC null vs real 0.98–1.00).
- **Other-trial stream** (real speech of another sentence): (c) commits it as often as real input (AUROC 0.500). The stream alone cannot know what the user intended. (q) commits 0 %, because the published sentence of trial *i* disagrees with the stream of trial *j* (AUROC 0.994). This is the "neural evidence vs LM text" check working as designed.

## Phoneme level (test)
| policy | eWPM | wrong-commit | silent error | PER | COMMIT / OFFER |
|---|---|---|---|---|---|
| greedy commit | 10.16 [9.67, 10.62] | 0.756 | 0.064 | 0.097 | 1.00 / 0 |
| beam top-1 commit | 10.21 [9.75, 10.68] | 0.754 | 0.062 | 0.094 | 1.00 / 0 |
| trust | 10.20 [9.80, 10.61] | **0.054** | 0.002 | 0.094 | 0.19 / 0.81 |

The phoneme-level eWPM is only indicative: the simulated user's typing time counts symbol-string characters (one per phoneme), not letters. Gaze-only on these strings: 4.82.

## Comparison with real MEG (M2-10 / M2-14 / M1-15)
| claim | real MEG (keystroke decoder) | intracortical speech (this run) |
|---|---|---|
| truth is top-1 | 0 % | 39 % (ours), 81 % (published) |
| wrong-commit, always commit → trust | 1.00 → 0.00 | 0.61 → 0.06 (ours); 0.19 → 0.04 (published) |
| eWPM, trust vs always commit | 2.96 vs 2.31 (`aac_gaze`) | 11.55 vs 11.45 (ours); 18.77 vs 19.61 (published) |
| BCI vs gaze typing alone | trust 2.96–3.06 < gaze 3.14 | trust 11.55 / 18.77 ≫ gaze 4.08 |
| best error signal | low evidence only (0.85 for high CER) | −p_top1 (0.80 word level, 0.88 phoneme level) |
| null input committed by trust | 0 % | 0 % (shuffled, uniform); 22 % for another real trial (ours), 0 % (published gate) |

## Fixes during the run
- The first full run skipped the extra word metrics (word-confidence AUROC, published-error AUROC) because a bound method was tested with `is`. The `extra` stage refits (c) and adds them to `trust.json`; it also recomputes (c)'s eWPM as a check (11.546, the same as the main run).

## Limits
- One participant, copy task, online logits (we cannot rerun the decoder). Frame timing is inferred.
- Our word decoder is simple (WER 0.149 vs 0.043 published). Tuning stopped at a grid edge.
- 64 of the 1,628 cue sentences occur in Tatoeba English, which trains our char LM and the word unigram (possible small leak; not removed).
- The user-model costs are literature-based assumptions (see [OFFER_WORDS](../2026-11-08-m2-offer-words/results.md)); the neural input speed is the measured speech rate.
- The policy fit and the frame/sentence temperatures use the same 812 fit trials (two halves inside the harness). One seed.
