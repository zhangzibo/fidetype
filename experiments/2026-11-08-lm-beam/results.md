---
title: CTC beam search + 6-gram char LM on simulator streams
type: experiment
updated: 2026-11-08
---

# CTC beam search + 6-gram character LM (simulator benchmark)

This experiment serves milestone M1 (the n-gram beam baseline) and M2 (trust core: "LM fusion → n-best").
It measures greedy CTC, beam search without an LM, and beam search with a 6-gram character LM on [simulator](../../src/fidetype/streams/simulator.py) streams.

- Code: `src/fidetype/lm/ngram.py` (`CharNgramLM`), `src/fidetype/lm/beam.py` (`ctc_prefix_beam_search`).
- Scripts: `build_lms.py` (corpora → LMs), `run_sim_benchmark.py` (this page). Raw numbers: `results/benchmark.json`, `results/benchmark_log.txt`.
- LM provenance: [`src/fidetype/lm/corpora.md`](../../src/fidetype/lm/corpora.md).

## Summary

- The LM reduces the CER by 0.07–0.08 absolute at all three presets. Best: 0.171 → 0.094. Median: 0.281 → 0.200. Worst: 0.417 → 0.343.
- The WER falls more: median 0.729 → 0.386.
- A beam without an LM gives no gain over greedy (the simulator peaks are clear).
- The best LM weight is 1.0 at all three presets. A larger weight hurts. The simulator gives calibrated acoustic probabilities, so this result is expected. A real, over-confident decoder will need a larger weight.
- The n-best list gives some headroom: the top-10 oracle CER is 0.03 below the 1-best CER (median 0.200 → 0.167).
- No 1-best character confidence is calibrated after LM fusion. The fused confidence is the best one (median ECE 0.099), but it is over-confident. The trust layer must recalibrate it.
- Decode speed: a 40-character sentence (about 400 frames) with beam 16 takes 91 ms (mean) in pure Python.

## Set-up

| Item | Value |
|---|---|
| LM (English) | 6-gram, interpolated modified Kneser–Ney, Tatoeba English, 600 000 sentences (23.4 M characters). Held-out perplexity 3.16 per symbol. |
| LM (Spanish) | 6-gram, same smoothing, Tatoeba Spanish, 434 443 sentences (17.0 M characters). Held-out perplexity 3.45; on the SpanishBCBL targets 3.78. |
| Test sentences | 200 held-out Tatoeba English sentences (20–80 characters, mean 36.9). They are not in the LM training text. |
| Dev sentences | 100 other held-out Tatoeba sentences, median preset. Used only for tuning. |
| Streams | `NoisyDecoderSimulator`, presets `best`, `median`, `worst` (greedy CER 0.17 / 0.28 / 0.41), `confidence_temperature = 1` (calibrated). |
| Chosen setting | `lm_weight = 1.0`, `insertion_bonus = 2.0`, `beam = 32` (dev tuning, below), `n_best = 10`, `prune_logp = -6`, `prune_topk = 10`. |
| Machine | Windows 11 laptop, Python 3.12, numpy, one process. |

## Results: CER and WER (test, 200 sentences per set)

| Set | Greedy CER | Greedy WER | Beam (no LM) CER | Beam (no LM) WER | Beam + LM CER | Beam + LM WER |
|---|---|---|---|---|---|---|
| English, best | 0.171 | 0.567 | 0.171 | 0.567 | **0.094** | **0.239** |
| English, median | 0.281 | 0.729 | 0.282 | 0.730 | **0.200** | **0.386** |
| English, worst | 0.417 | 0.879 | 0.423 | 0.879 | **0.343** | **0.566** |
| English corpus.py, median (out of domain) | 0.290 | 0.790 | 0.292 | 0.790 | 0.220 | 0.438 |
| Spanish Tatoeba, median (Spanish LM) | 0.292 | 0.797 | 0.295 | 0.798 | 0.203 | 0.443 |
| SpanishBCBL targets (226), median (Spanish LM) | 0.283 | 0.770 | 0.285 | 0.771 | 0.210 | 0.497 |

- The simulator uses English letter error rates for the Spanish text too. The Spanish rows check the Spanish LM only. They are not a model of SpanishBCBL decoding.
- The SpanishBCBL target sentences were removed from the Spanish LM training text (2 matches).

### CER against LM weight (test, beam 32, bonus 2.0)

| Preset | w = 0.5 | w = 1.0 | w = 2.0 | w = 3.0 |
|---|---|---|---|---|
| best | 0.132 | **0.094** | 0.123 | 0.180 |
| median | 0.260 | **0.200** | 0.233 | 0.326 |
| worst | 0.437 | **0.343** | 0.384 | 0.477 |

### Dev tuning (median preset, 100 sentences)

CER for `lm_weight` (rows) × `insertion_bonus` (columns), beam 16:

| w \ bonus | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| 0.5 | 0.222 | 0.230 | 0.270 | 0.425 |
| 1.0 | 0.256 | 0.220 | **0.219** | 0.273 |
| 1.5 | 0.320 | 0.256 | 0.247 | 0.263 |
| 2.0 | 0.396 | 0.329 | 0.278 | 0.275 |
| 3.0 | 0.543 | 0.481 | 0.399 | 0.354 |

Beam width (w = 1.0, bonus 2.0):

| Beam | 4 | 8 | 16 | 32 | 64 |
|---|---|---|---|---|---|
| CER | 0.278 | 0.238 | 0.219 | 0.208 | 0.206 |
| ms / sentence (no alignment) | 5 | 8 | 21 | 41 | 103 |

- Without a bonus, a high LM weight makes the search drop characters. Each character costs about 1.15 nats of LM log-probability (perplexity 3.16). The bonus balances this cost.
- The v2 setting (6-gram, beam 50, LM weight 2.0) used KenLM log10 scores and a real decoder. Do not copy its weight to this code.

## Results: decode speed

| Case | Mean | Max |
|---|---|---|
| 40-character sentences (50, mean 403 frames), beam 16, n_best 10, no alignment | 91 ms | 260 ms |
| same, with forced alignment and all confidences | 173 ms | 247 ms |
| Test set (36.9 characters), beam 32, no alignment (median preset) | 41 ms | – |
| Test set, beam 32, with alignment (median preset) | 111 ms | – |

- The forced alignment runs once per returned hypothesis. Use `align=False` if you need only the texts and the scores.
- A unit test checks the 1 s limit (`tests/test_lm.py::test_speed_40_chars`).

## Results: n-best oracle (beam + LM, n_best = 10)

Oracle CER = the CER of the best hypothesis in the top k.

| Set | k = 1 | k = 3 | k = 5 | k = 10 | Exact sentence in top 1 / 3 / 10 |
|---|---|---|---|---|---|
| English, best | 0.094 | 0.080 | 0.076 | 0.073 | 18 % / 22 % / 22 % |
| English, median | 0.200 | 0.180 | 0.173 | 0.167 | 7 % / 9 % / 10 % |
| English, worst | 0.343 | 0.317 | 0.312 | 0.304 | 4 % / 4 % / 4 % |
| Spanish Tatoeba, median | 0.203 | 0.180 | 0.171 | 0.166 | 6 % / 9 % / 10 % |
| SpanishBCBL targets, median | 0.210 | 0.190 | 0.184 | 0.178 | 2 % / 4 % / 4 % |

- The top-3 list removes 10–14 % of the remaining character errors at the median preset (0.200 → 0.180).
- The 10 hypotheses are often near copies of each other (they differ in one or two characters near the end). Thus the oracle gain from k = 3 to k = 10 is small.
- For "OFFER n-best" in the trust layer, a list of whole-sentence alternatives is not enough. The trust layer should offer alternatives per word or per region, where the hypotheses differ.

## Results: calibration of the 1-best character confidences

ECE = expected calibration error, 15 bins (`metrics.expected_calibration_error`). A 1-best character is "correct" if a Levenshtein alignment to the reference matches it to the same character. The values in brackets are the mean confidence. "Acc." is the share of correct 1-best characters.

| Set | Decoder | Acc. | ECE fused | ECE frame | ECE n-best (T=1) | ECE n-best (T=8) |
|---|---|---|---|---|---|---|
| English, best | beam, no LM | 0.835 | 0.020 (0.855) | **0.010** (0.844) | 0.162 | 0.162 |
| English, best | beam + LM | 0.922 | **0.053** (0.893) | 0.166 (0.757) | 0.064 | 0.049 |
| English, median | beam, no LM | 0.728 | 0.021 (0.748) | **0.014** (0.732) | 0.268 | 0.267 |
| English, median | beam + LM | 0.832 | **0.099** (0.843) | 0.226 (0.606) | 0.143 | 0.120 |
| English, worst | beam, no LM | 0.588 | 0.028 (0.614) | **0.015** (0.595) | 0.401 | 0.401 |
| English, worst | beam + LM | 0.701 | **0.177** (0.792) | 0.247 (0.458) | 0.265 | 0.237 |

Reference: the simulator peak confidence of the greedy output has ECE 0.010–0.017 (it is calibrated by design).

Sentence level (beam + LM, median): the n-best posterior of the 1-best text, against "exact match", has ECE 0.488 at T = 1 and 0.175 at T = 4. It is strongly over-confident.

Findings:

- Without an LM, the frame posterior stays calibrated (ECE ≤ 0.015). It is the simulator's own calibrated value.
- With the LM, the frame posterior is under-confident. The LM changes characters to ones with a low frame posterior, and these changes are often right.
- The fused confidence (frame posterior × LM, renormalised) is the best variant with the LM. It is still over-confident, and more so for worse presets (ECE 0.053 / 0.099 / 0.177). The beam chooses characters where the fused value is high, so a selection effect is likely. The Tatoeba LM is also sharp on in-domain text.
- The n-best marginal is over-confident (mean 0.99 without the LM). The beam keeps few alternatives for early characters, so most positions get a value near 1. A higher temperature helps only a little.
- Decision: `char_confidences` uses the fused variant by default (`confidence="fused"`). All three variants are in `Hypothesis.confidence_variants`. The trust layer must recalibrate them (for example, temperature or isotonic scaling on held-out data).

## Problems and limits

- The simulator acoustic model is calibrated and independent across characters. Real decoders are over-confident and have correlated errors. The best LM weight and the calibration results will change on real data.
- The test sentences are held-out Tatoeba sentences. Tatoeba has many near-duplicates ("tom is ..."), so the in-domain LM gain is optimistic. The out-of-domain corpus.py row (0.290 → 0.220) is a more careful estimate.
- Deletions (a character with no peak) cannot be repaired. The beam can only choose among characters with `log p >= prune_logp` at some frame.
- The search is pure Python. Beam 64 takes about 0.1 s per sentence; this is acceptable offline but not for very long streams.
- The SpanishBCBL sidecar JSONs (`C:\Users\zhang\bci-data\cache\spanishbcbl\v1\`) did not exist yet. The blocklist came directly from the 84 experiment logs. Re-run `build_lms.py` when the sidecars exist.

## Reproduce

```bash
export PATH="$HOME/.local/bin:$PATH"
uv run python experiments/2026-11-08-lm-beam/build_lms.py        # about 2 min
uv run python experiments/2026-11-08-lm-beam/run_sim_benchmark.py  # about 15 min
```
