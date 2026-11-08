---
title: Beam re-tune for n-best recall
type: experiment
updated: 2026-11-08
---

# Beam re-tune: n-best recall of the CTC prefix beam

The trust layer needs the true sentence in the n-best list. With the old beam settings, the list missed the truth in 73 % of the M2 cross-check sentences. This experiment finds the cause and fixes it.

- Code: `src/fidetype/lm/beam.py` (new keyword options, `RETUNED`, `word_alternatives`). Tests: `tests/test_lm.py`.
- Script: `run.py` (`--part sweep`, `--part trust`). Raw numbers: `results/sweep.json`, `results/trust.json`, `results/dev_grid.jsonl`, logs `results/*_log.txt`. Generated tables: `results/tables.md`.

**Main finding:** The truth was lost by the search, not by the model: the per-frame top-10 cut and a 16-prefix beam removed it, and a beam of 256 without the top-k cut (fast with a new numpy search) plus a re-tuned LM weight and bonus raises recall@10 from 0.075 to 0.47 on open-domain Tatoeba text (median preset) and cuts the n-best miss rate in the M2 trust pipeline from 0.73 to 0.00 (median, T = 1), so the trust policy commits 86 % of the sentences and reaches 25.3 eWPM against 21.9 for the reference decoder.

## Set-up

| Item | Value |
|---|---|
| LM | 6-gram MKN, Tatoeba English (`eng_tatoeba_6gram_mkn.npz`), as in [lm-beam](../2026-11-08-lm-beam/results.md). |
| Test sentences | 200 held-out Tatoeba sentences (20–80 characters, mean 36.9), not in the LM training text. Same sentences and simulator seeds as the lm-beam experiment. |
| Dev sentences | 100 other held-out sentences, median preset, seed 7. Used only for the `lm_weight` × `insertion_bonus` choice. |
| Streams | `NoisyDecoderSimulator`, presets best / median / worst, `confidence_temperature = 1`. |
| Metrics | recall@k: the exact true sentence is in the top k (texts with joined spaces, k = 1, 5, 10, 20). Oracle CER@10: the best CER in the top 10. CER@1. ms: mean decode time per sentence, `align=False`, one process, laptop CPU (other jobs ran on the machine; times are approximate). |
| Search vs model error | A missed truth is a **search error** if its own score (CTC forward log-probability + w · LM + bonus · length) is higher than the score of the last hypothesis in the 20-best list (or the list is shorter than 20). Then the search lost it. Otherwise it is a **model error**: the scores rank 20 other texts above the truth. |

## Diagnosis

### 1. The top-10 cut removes a true character in most sentences

Static check: a CTC forced alignment of the true text gives the frames of each true character. The table gives the share of test sentences with at least one true character that a per-frame rule removes at all its frames.

| preset | top-10, logp ≥ −6 (old) | top-20, −6 | all 27, −6 | all 27, −9 | all 27, −12 | sentences with a deletion |
|---|---|---|---|---|---|---|
| best | 0.770 | 0.355 | 0.310 | 0.025 | 0.015 | 0.240 |
| median | **0.900** | 0.370 | 0.295 | 0.010 | 0.010 | 0.290 |
| worst | 0.960 | 0.445 | 0.310 | 0.025 | 0.010 | 0.290 |

- With the old rule, 90 % of the median sentences cannot be decoded exactly. This is the largest single cause.
- Why: the simulator puts the residual mass of a peak on the keys near the *shown* label. The true key is often not in the top 10 of that frame. Also, in blank frames all letters have the same small value, so the stable top-10 holds only the letters `a`–`i`.
- Without the top-k cut, the rest (about 0.30) is almost exactly the sentences with a deleted character (no peak). The true character then exists only in blank frames, at log p ≈ −6 to −9.

### 2. Then the beam width limits the recall

Old `lm_weight = 1.0`, `insertion_bonus = 2.0`, median test set:

| setting | r@10 | search err | model err | ms |
|---|---|---|---|---|
| old default (beam 16, top-10) | 0.075 | 0.925 | 0.000 | 37 |
| beam 16, no top-k cut | 0.135 | 0.865 | 0.000 | 28 |
| beam 64, top-10 | 0.130 | 0.780 | 0.090 | 141 |
| beam 64, no top-k cut | 0.295 | 0.520 | 0.180 | 114 |
| beam 256, no top-k cut | 0.400 | 0.280 | 0.285 | 218 |
| beam 512, no top-k cut | 0.445 | 0.195 | 0.320 | 341 |

- With the old setting, **every** miss is a search error. The truth has a higher score than the 16th hypothesis, but the search dropped it.
- A larger beam alone does not help while the top-10 cut stays (beam 64: 0.130). The cut and the beam must change together.
- The beam fills with variants of the last few characters. A true character with weak acoustic evidence is 5–10 nats behind at its own frame. The LM gives the score back only some characters later (at the end of the word). A beam of 16 cannot keep it for that long.
- `prune_logp = −9` makes every blank frame a candidate frame. It costs time and lowers the recall (0.375 against 0.400 at beam 256): more junk insertions enter the beam.

### 3. The insertion bonus and the LM weight decide the rest

With a wide beam, the model errors grow (0.285 at beam 256). The bonus 2.0 makes an extra character cheap: a second character from a 2- or 3-frame peak costs about −3 nats acoustic and gets +2 back. Thus many junk insertions outrank the truth. A larger LM weight and a smaller bonus fix this (dev grid below): beam 256 gives r@10 0.400 → 0.470 and CER@1 0.149 → 0.126.

### 4. The near-duplicate lists

The old 10-best lists change on average 1.3 words against the top-1, nearly always near the end of the sentence. This follows from cause 2: older alternatives leave the beam. The new lists keep alternatives from all positions (1.5 words changed at median, 1.8 at worst), and the oracle CER@10 falls from 0.188 to 0.078.

## Changes to `beam.py`

All changes are keyword-only arguments with defaults that keep the old search. A test compares the new code with a frozen copy of the old search (`test_old_defaults_unchanged`).

| Option | Effect | Kept in `RETUNED`? |
|---|---|---|
| `search="vector"` | The same prefix search, with numpy over all (prefix, token) pairs of a frame. Only the extensions that enter the beam become Python objects. Same n-best as the loop (test `test_vector_search_matches_loop`), 1.3–3× faster at beam 16–32, and a beam of 256 without a top-k cut takes about 0.15–0.2 s per sentence. | yes |
| `prune_topk=None` | No top-k cut per frame. | yes |
| `beam=256`, `n_best=20` | A wide beam, and a separate, shorter output list. | yes |
| `space_rules=True` | No leading or double space; a trailing space is removed and merged. No recall change on Tatoeba; it removes duplicates for the trust adapter. | yes |
| `lm_weight=1.25`, `insertion_bonus=1.0` | Dev-tuned (below). | yes |
| `lm_candidates=k` | Pruning per prefix: each prefix also tries its k most probable LM characters, down to `lm_candidate_logp=−12`. It can restore a deleted character. | no: −0.02 r@10 on test, −0.01 on dev, +70 % time |
| `beam_logp` | Also drop prefixes more than `beam_logp` below the best one. | no: 0.455 r@10 at 12 nats, 15 % faster; use it if time is short |
| `max_per_stem`, `stem_drop` | Diverse beam: at most n prefixes with the same text without the last characters. | no: it lowers the recall (0.250–0.305) |
| `word_alternatives(hyps, ...)` | Per-word alternatives from an n-best list (word-level Levenshtein alignment to the top-1; mass = sum of posteriors). Accepts `Hypothesis` or trust `Candidate` objects and optional calibrated posteriors. | new helper |

The `"nbest"` character confidence now uses the 64 best final texts only (a speed limit for a wide beam). For a beam ≤ 64 the values do not change.

## Parameter sweep (median test set, 200 sentences)

| setting | r@1 | r@5 | r@10 | r@20 | oracle CER@10 | CER@1 | search err | model err | ms mean | ms p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| old default (loop) | 0.055 | 0.075 | 0.075 | 0.075 | 0.188 | 0.210 | 0.925 | 0.000 | 37 | 60 |
| old default (vector) | 0.055 | 0.075 | 0.075 | 0.075 | 0.188 | 0.210 | 0.925 | 0.000 | 26 | 43 |
| prune_topk 20 | 0.125 | 0.135 | 0.135 | 0.135 | 0.166 | 0.187 | 0.865 | 0.000 | 28 | 47 |
| prune_topk None | 0.125 | 0.135 | 0.135 | 0.135 | 0.170 | 0.190 | 0.865 | 0.000 | 28 | 51 |
| prune_topk None, prune_logp −9 | 0.110 | 0.130 | 0.130 | 0.130 | 0.183 | 0.204 | 0.870 | 0.000 | 44 | 72 |
| beam 64, topk 10 | 0.095 | 0.120 | 0.130 | 0.130 | 0.154 | 0.187 | 0.780 | 0.090 | 141 | 282 |
| beam 32, topk None | 0.155 | 0.195 | 0.205 | 0.205 | 0.144 | 0.175 | 0.700 | 0.095 | 53 | 99 |
| beam 64, topk None | 0.200 | 0.280 | 0.295 | 0.300 | 0.121 | 0.159 | 0.520 | 0.180 | 114 | 225 |
| beam 128, topk None | 0.235 | 0.335 | 0.360 | 0.380 | 0.106 | 0.150 | 0.380 | 0.240 | 150 | 371 |
| beam 256, topk None | 0.225 | 0.365 | 0.400 | 0.435 | 0.096 | 0.149 | 0.280 | 0.285 | 218 | 483 |
| beam 512, topk None | 0.245 | 0.395 | 0.445 | 0.485 | 0.087 | 0.144 | 0.195 | 0.320 | 341 | 648 |
| beam 256, topk None, logp −9 | 0.205 | 0.345 | 0.375 | 0.405 | 0.112 | 0.168 | 0.225 | 0.370 | 269 | 600 |
| beam 256 + space_rules | 0.225 | 0.365 | 0.400 | 0.435 | 0.096 | 0.149 | 0.280 | 0.285 | 206 | 465 |
| beam 256 + space + lm_cand 3 | 0.205 | 0.355 | 0.380 | 0.405 | 0.109 | 0.165 | 0.245 | 0.350 | 228 | 457 |
| **RETUNED** (beam 256, space, w 1.25, bonus 1.0) | **0.275** | **0.420** | **0.470** | **0.495** | **0.078** | **0.126** | 0.260 | 0.245 | 148 | 340 |
| RETUNED, beam 64 | 0.240 | 0.325 | 0.335 | 0.340 | 0.110 | 0.144 | 0.545 | 0.115 | 93 | 208 |
| RETUNED, beam 128 | 0.265 | 0.375 | 0.395 | 0.405 | 0.096 | 0.133 | 0.405 | 0.190 | 129 | 309 |
| RETUNED, beam 512 | 0.280 | 0.450 | 0.520 | 0.540 | 0.072 | 0.123 | 0.180 | 0.280 | 238 | 499 |
| RETUNED + lm_cand 3 | 0.265 | 0.405 | 0.450 | 0.475 | 0.089 | 0.136 | 0.250 | 0.275 | 253 | 504 |
| RETUNED + lm_cand 5 | 0.265 | 0.405 | 0.445 | 0.470 | 0.089 | 0.136 | 0.255 | 0.275 | 237 | 477 |
| RETUNED + stem cap 4 | 0.165 | 0.220 | 0.250 | 0.250 | 0.122 | 0.165 | 0.570 | 0.180 | 207 | 429 |
| RETUNED + stem cap 8 (drop 2) | 0.200 | 0.285 | 0.305 | 0.310 | 0.108 | 0.145 | 0.495 | 0.195 | 188 | 388 |
| RETUNED + beam_logp 12 | 0.270 | 0.410 | 0.455 | 0.485 | 0.080 | 0.128 | 0.270 | 0.245 | 127 | 323 |
| RETUNED, no space_rules | 0.280 | 0.420 | 0.470 | 0.495 | 0.078 | 0.126 | 0.260 | 0.245 | 159 | 356 |
| RETUNED, topk 10 (old cut) | 0.115 | 0.155 | 0.170 | 0.170 | 0.137 | 0.183 | 0.690 | 0.140 | 172 | 332 |

Trade-off curve (RETUNED weights, median): beam 64 → 128 → 256 → 512 gives r@10 0.335 → 0.395 → 0.470 → 0.520 for 93 → 129 → 148 → 238 ms (no alignment). The time grows less than linearly with the beam. The ms values are noisy (±30 %): other jobs used the CPU.

### Dev tuning (median dev set, 100 sentences, beam 128, no top-k cut, space rules)

r@10 for `lm_weight` (rows) × `insertion_bonus` (columns), `lm_candidates = 0`. CER@1 in brackets.

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 | 2.0 | 2.5 |
|---|---|---|---|---|---|---|
| 0.8 | – | – | 0.24 (0.144) | 0.22 (0.155) | 0.19 (0.175) | 0.16 (0.225) |
| 1.0 | – | – | 0.28 (0.144) | 0.27 (0.146) | 0.25 (0.165) | 0.21 (0.191) |
| 1.25 | 0.23 (0.187) | 0.29 (0.156) | **0.29 (0.145)** | 0.28 (0.149) | 0.27 (0.151) | 0.25 (0.173) |
| 1.5 | 0.22 (0.212) | 0.28 (0.175) | 0.30 (0.152) | – | – | – |
| 2.0 | 0.12 (0.287) | 0.17 (0.230) | 0.26 (0.213) | – | – | – |

With `lm_candidates = 3` every cell is 0.00–0.02 lower (full grid in `results/tables.md`).

## Chosen defaults and why

`RETUNED = {search: "vector", beam: 256, n_best: 20, prune_topk: None, prune_logp: −6, space_rules: True, lm_weight: 1.25, insertion_bonus: 1.0}`.

- **No top-k cut.** It is the main cause of the misses (diagnosis 1).
- **Beam 256.** It is the largest beam that stays well under 0.5 s with alignment: 40-character sentences take 179 ms without and 261 ms with the forced alignment and all confidences (mean of 50); test sets 251–299 ms with alignment. Beam 512 gives +0.05 r@10 at about 1.6× the time. Use it offline.
- **w = 1.25, bonus = 1.0.** The dev surface is flat near the top (0.28–0.30 for w 1.0–1.5, bonus 0.5–1.5; 0.01 is one sentence). The best dev cell is w 1.5 / bonus 1.0 (0.30, CER 0.152). We took w 1.25 / bonus 1.0 (0.29, CER 0.145): it has the lowest CER@1 of the top cells and is the smallest change from the old weight. The lm-beam experiment chose bonus 2.0 for CER@1 at beam 16; with a wide beam, bonus 1.0 is also better for CER@1.
- **`prune_logp = −6`, no `lm_candidates`.** A lower floor or LM-guided candidates can restore deleted characters, but they bring more junk insertions than restored characters on this data.
- The old defaults of `ctc_prefix_beam_search` do not change (backward compatible). Callers opt in with `**RETUNED`.

### Old default vs RETUNED, all presets (test, 200 sentences each)

| preset | setting | r@1 | r@5 | r@10 | r@20 | oracle CER@10 | CER@1 | search err | model err | ms |
|---|---|---|---|---|---|---|---|---|---|---|
| best | old | 0.165 | 0.180 | 0.180 | 0.180 | 0.085 | 0.102 | 0.820 | 0.000 | 27 |
| best | RETUNED | 0.455 | 0.680 | **0.715** | 0.735 | 0.022 | 0.050 | 0.170 | 0.095 | 193 |
| median | old | 0.055 | 0.075 | 0.075 | 0.075 | 0.188 | 0.210 | 0.925 | 0.000 | 27 |
| median | RETUNED | 0.275 | 0.420 | **0.470** | 0.495 | 0.078 | 0.126 | 0.260 | 0.245 | 162 |
| worst | old | 0.020 | 0.025 | 0.025 | 0.025 | 0.322 | 0.356 | 0.975 | 0.000 | 26 |
| worst | RETUNED | 0.105 | 0.175 | **0.195** | 0.220 | 0.200 | 0.265 | 0.260 | 0.520 | 166 |

- The recall@10 target of 0.7 is met at the best preset only. At the median preset on open-domain Tatoeba text it is 0.47. Half of the remaining misses are model errors: the LM plus the acoustic scores rank 20 texts above the truth. A wider beam cannot fix those.
- CER@1 also improves a lot: median 0.210 → 0.126 (the lm-beam result at beam 32 was 0.200).

## Trust pipeline with the new beam

Set-up: the M2 harness and config, unchanged ([m2-trust-sim](../2026-11-08-m2-trust-sim/results.md)). Template sentences, 120 calibration / 120 validation / 120 test per condition, the M2 seeds. The LM for the beam is `CharNgramLM(order=6)` trained on the other template sentences (as in the M2 cross-check); the reference decoder uses its own 5-gram Witten-Bell LM. The beam output goes through `from_lm_hypotheses` (frame confidences). The new beam uses `RETUNED` with `n_best=10`, so all decoders give 10 candidates. Policy (b) = always COMMIT the top-1, no calibration. Policy (c) = the full trust policy, fitted on validation for max eWPM with wrong-commit ≤ 0.05. No change to `src/fidetype/trust/` was necessary.

The reference rows reproduce the M2 table exactly (for example median/T=1.0: b 23.89, c 21.88). The old-beam row at median/T=1.0 reproduces the M2 cross-check (b 20.42, c 16.27, miss rate 0.733).

### Trust policy (c), test set

| condition | decoder | eWPM | wrong-commit | guard AUROC | n-best inconsistency AUROC | coverage | coverage in n-best | set size | miss rate | word coverage | COMMIT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| median/T=0.5 | reference | 19.69 | 0.025 | 0.656 | 0.742 | 0.567 | 0.829 | 0.83 | 0.317 | 0.907 | 0.12 |
| median/T=0.5 | old beam | 13.69 | 0.050 | 0.561 | 0.863 | 0.167 | 0.667 | 0.30 | 0.750 | 0.826 | 0.04 |
| median/T=0.5 | **new beam** | **25.34** | 0.067 | 0.681 | 0.853 | **0.933** | 0.957 | 1.09 | **0.025** | 0.884 | 0.90 |
| median/T=1.0 | reference | 21.88 | 0.033 | 0.649 | 0.771 | 0.700 | 0.966 | 1.29 | 0.275 | 0.891 | 0.23 |
| median/T=1.0 | old beam | 16.27 | 0.000 | 0.431 | 0.846 | 0.283 | 0.971 | 0.93 | 0.708 | 0.851 | 0.00 |
| median/T=1.0 | **new beam** | **25.33** | 0.033 | 0.486 | 0.900 | **0.908** | 0.908 | 0.99 | **0.000** | 0.912 | 0.86 |
| worst/T=0.5 | reference | 19.74 | 0.017 | 0.622 | 0.727 | 0.608 | 0.924 | 1.09 | 0.342 | 0.901 | 0.17 |
| worst/T=0.5 | old beam | 11.04 | 0.000 | 0.486 | 0.759 | 0.083 | 1.000 | 9.90 | 0.917 | 0.717 | 0.00 |
| worst/T=0.5 | **new beam** | **20.84** | 0.058 | 0.569 | 0.778 | **0.942** | 0.958 | 2.67 | **0.017** | 0.904 | 0.53 |
| worst/T=1.0 | reference | 20.14 | 0.033 | 0.642 | 0.739 | 0.625 | 0.915 | 1.25 | 0.317 | 0.895 | 0.18 |
| worst/T=1.0 | old beam | 11.28 | 0.000 | 0.485 | 0.827 | 0.092 | 1.000 | 9.94 | 0.908 | 0.692 | 0.00 |
| worst/T=1.0 | **new beam** | 20.44 | 0.075 | 0.562 | 0.818 | **0.933** | 0.957 | 2.52 | **0.025** | 0.889 | 0.51 |

Conformal target: coverage 0.9 (alpha 0.1). "coverage" counts a missed truth as a miss (strict). Set size is the mean conformal set size.

### Always-commit top-1 (b), test set

| condition | reference eWPM / wrong-commit | old beam | new beam |
|---|---|---|---|
| median/T=0.5 | 23.42 / 0.425 | 16.87 / 1.000 | 17.17 / 1.000 |
| median/T=1.0 | 23.89 / 0.317 | 20.42 / 0.758 | **25.78 / 0.108** |
| worst/T=0.5 | 22.59 / 0.442 | 14.89 / 1.000 | 15.90 / 0.992 |
| worst/T=1.0 | 22.16 / 0.408 | 17.63 / 0.908 | **23.35 / 0.342** |

### Findings

1. **The miss rate falls from 0.71–0.92 (old beam) and 0.28–0.34 (reference) to 0.00–0.03.** Strict conformal coverage rises to 0.91–0.94, above the 0.9 target, with a mean set size of 1.0–2.7.
2. **The trust policy can now commit.** At the median preset it commits 86–90 % of the sentences, and eWPM is 25.3 against 19.7–21.9 for the reference decoder and 13.7–16.3 for the old beam. At the worst preset the new beam is level with the reference (20.4–20.8 against 19.7–20.1) and commits about half of the sentences.
3. **The wrong-commit limit holds less well.** On test it is 0.033–0.075 against the 0.05 validation target (reference: 0.017–0.033). As in M2, the grid fit on 120 validation sentences has no finite-sample guarantee. The new beam commits more often, so this matters more now.
4. **The guard is still weak.** Its combined risk has AUROC 0.49–0.68 for a wrong top-1 (reference 0.62–0.66). The n-best inconsistency signal alone does much better (0.78–0.90), and so does `p_top1` (0.75–0.91). The guard needs re-tuning for this decoder's frame confidences; this was out of scope (no change to `trust/`).
5. **The raw n-best scores are now close to calibrated.** The fitted sentence temperature is 1.0–1.8 (old beam 5–20, reference 7–9).
6. **The CTC beam needs the frame calibration.** Without it (policy b at T = 0.5, an over-confident stream), both LM beams commit a wrong text in almost every sentence. The CTC prefix probability sums the evidence of all frames of a peak, so a doubled log-probability is very hard for the LM to overrule. The reference decoder uses the centre frame only and suffers less. With the frame temperature fitted (policy c), the new beam is the best decoder at T = 0.5 too.

### Per-word alternatives

The simulated user cannot choose words, so the harness cannot measure a per-word OFFER. We measured whether a per-word OFFER could reach the truth, on the sentences with a wrong top-1 (fitted pipeline c, calibrated posteriors, `word_alternatives`).

| condition | decoder | wrong top-1 | truth in top-3 sentences | built from top-2 per word | built from top-3 per word |
|---|---|---|---|---|---|
| median/T=0.5 | new beam | 12 | 0.750 | 0.750 | 0.833 |
| median/T=1.0 | new beam | 12 | 0.917 | 0.917 | 1.000 |
| worst/T=0.5 | new beam | 30 | 0.533 | 0.667 | 0.700 |
| worst/T=1.0 | new beam | 40 | 0.700 | 0.625 | 0.850 |
| worst/T=1.0 | reference | 48 | 0.208 | 0.188 | 0.208 |
| worst/T=1.0 | old beam | 109 | 0.000 | 0.000 | 0.000 |

Tatoeba median test set (RETUNED, all 200 sentences): truth in the top-3 sentences 0.38, top-5 0.42; built from the top-2 alternatives per word 0.415, top-3 per word 0.465. A sentence has on average 1.9 uncertain word slots (more than one alternative, top mass < 0.9).

- With the new beam, three choices per word reach the truth in 8–17 % more of the wrong-top-1 sentences than three whole sentences. On Tatoeba, three per word (0.465) beat five sentences (0.42).
- The time is about the same. With the default time model (read: 0.5 s per candidate + 0.3 s per word; select: 1.0 + 0.5 · log2(k + 1) s), two 3-way word choices cost about 4.8 s read + 4.0 s select = 8.8 s. Three 7-word sentences cost about 7.8 s read + 2.0 s select = 9.8 s. This is an estimate, not a harness result.
- Thus per-word alternatives would likely help the simulated user, mainly because they reach the truth more often, not because they are faster. To measure it, the user model needs a per-word OFFER action (a change in `interact/` and `trust/policy.py`, not done here).
- With the reference decoder and the old beam, per-word alternatives do not help: the truth is not in the list at all.

## Problems and limits

- Simulator data only. The simulator spreads the residual mass of a wrong peak around the shown label. This made the top-k cut very harmful. A real decoder can differ; check the cut again on real streams.
- The 0.7 recall target at the median preset is met on in-domain template text, not on open-domain Tatoeba text (0.47). For open text, the remaining misses are half model errors.
- Deletions (about 29 % of the sentences have one) are not restored by the chosen setting. `lm_candidates` can restore them, but it did not raise the recall here. A better approach may need a duration model or a deletion penalty that the LM cannot exploit.
- The decode time is about 6× the old default (still under 0.3 s with alignment for 40 characters). The search is single-threaded numpy plus Python.
- Times were measured while other jobs ran on the machine.
- One simulator seed per preset. 200 test sentences: a recall difference below about 0.04 is noise.

## Reproduce

```bash
export PATH="$HOME/.local/bin:$PATH"
uv run python experiments/2026-11-08-beam-retune/run.py --part sweep   # about 35 min (dev grid cached in results/dev_grid.jsonl)
uv run python experiments/2026-11-08-beam-retune/run.py --part trust   # about 20 min
```

Delete `results/dev_grid.jsonl` to run the dev grid again (about 35 min more).
