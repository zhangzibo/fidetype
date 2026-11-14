---
title: Lookahead vs accuracy and latency (causal decoder, M4-01 / M4-02)
type: question
tags: [decoder, causal, lookahead, latency, streaming, ctc, intracortical, neuraltextstream, trust-core]
sources: [brain-to-text-25-copytask]
updated: 2026-11-14
---

# How much accuracy does a causal decoder lose per millisecond of lookahead?

**Question:** A streaming decoder may wait L ms of future signal before it emits a frame. How do accuracy, trust outcomes and latency change with L from 0 to 500 ms? What should the NTS fields `latency` and `decoder.causal` say?

**Answer (2026-11-14, M4-01 / M4-02, one participant, an under-trained decoder):**
- Accuracy improves fast and then flattens. Shared model greedy PER: 0.6565 at L = 0, 0.4449 at 40 ms, 0.3687 at 500 ms. Most of the gain comes in the first 40 ms.
- The real delay is **not** always L. In the shared model, phonemes are ready exactly L later. But a model **trained** with L = 500 ms emits phonemes earlier. Its phonemes are ready 180 ms **before** those of the model trained with L = 0 (median).
- Compute does not depend on L: about 2 ms per 80 ms frame for the decoder, 0.4 ms for the trust layer. The final decision after the end of the utterance does not wait for L.
- **Caveat:** our decoder is far from the published T15 decoder (PER 0.0954 at latency 0). Our L = 0 models are about 7x worse. Treat the curve shape as provisional.

Experiment: [results.md](../../experiments/2026-11-13-m4-01-02-lookahead/results.md), [tables](../../experiments/2026-11-13-m4-01-02-lookahead/results/tables.md). Data: [Brain-to-Text '25 copy task](../sources/brain-to-text-25-copytask.md) (T15, CC0).

![Accuracy and phoneme ready time against lookahead L](lookahead-latency-accuracy.svg)

*Left: error rates on T15 val_eval (701 trials) against L. Right: median phoneme ready time (first greedy frame + L) relative to the dedicated L = 0 model. The dotted line is the nominal delay (ready L ms later).*

## Setup
| item | value |
|---|---|
| decoder | `fidetype.decoders.lookahead_gru`: our own causal GRU-CTC (5 layers, 768 units, 14-bin patches, stride 4 = 80 ms frames) plus a masked lookahead branch over bins `t_k + 1 .. t_k + L` |
| causality | output k uses bins `<= t_k + L` only; proved by `tests/test_causal_lookahead.py` |
| models | `shared` (L drawn per batch from {0, 40, 100, 200, 300, 500} ms), `dedicated_0` (L = 0), `dedicated_25` (L = 500 ms); 30 epochs each |
| L grid | declared 0, 50, 100, 200, 300, 500 ms; rule `floor(ms / 20)` bins, so 50 ms became **40 ms** |
| evaluation | `val_eval`: 701 trials, 41 sessions (odd-index `val` trials; checkpoint choice used the even-index ones) |
| trust | frozen Paper 1 v4 config `tcfg-f5ca0020b3b8fce2` from [M4-06](../concepts/streaming-trust-layer.md), not refitted, through `StreamingTrustLayer` |
| latency | NumPy streaming decoder fed one 20 ms bin at a time → NTS frames → `StreamingTrustLayer` with the incremental CTC beam and word decoder; 200 trials; timing CPU class |

## Results

### Accuracy and trust outcomes
| model | L (ms) | greedy PER | WER (T = 1) | sentence exact | commits | eWPM (gaze 4.02) |
|---|---|---|---|---|---|---|
| shared | 0 | 0.6565 | 0.8907 | 0.000 | 0 | 3.47 |
| shared | 40 | 0.4449 | 0.6791 | 0.006 | 0 | 4.13 |
| shared | 100 | 0.4097 | 0.6310 | 0.004 | 0 | 4.27 |
| shared | 200 | 0.3858 | 0.5979 | 0.016 | 0 | 4.44 |
| shared | 300 | 0.3768 | 0.5803 | 0.017 | 0 | 4.48 |
| shared | 500 | 0.3687 | 0.5728 | 0.014 | 0 | 4.48 |
| dedicated_0 | 0 | 0.6954 | 0.9307 | 0.000 | 0 | 3.38 |
| dedicated_25 | 500 | 0.3487 | 0.5405 | 0.034 | 0 | 5.15 |

- The frozen trust config committed nothing in all 8 conditions (701/701 OFFER, wrong-commit 0, CP95 [0.000, 0.005]). It was fitted on a much better decoder. So this test checks only the OFFER side: at L = 0 the trust layer is slower than gaze typing alone (3.47 vs 4.02 eWPM). From L = 40 ms it is faster.
- Always-commit would be wrong on 96 % to 100 % of the trials (wrong-commit 0.9629 to 1.0).
- Streaming = batch harness on 701/701 trials in every condition.

### Emission timing (median over exactly matched phonemes)
| comparison | emission stamp Δ (ms) | ready time Δ (ms) |
|---|---|---|
| shared L vs shared L = 0 | 0 | +L (40, 100, 200, 300, 500) |
| dedicated_0 vs shared L = 0 | +240 | +240 |
| dedicated_25 (L 500) vs dedicated_0 | −680 | **−180** |

### Compute latency (shared model, ms)
| L (ms) | decoder per 20 ms bin p50 / p95 | trust per frame p50 / p95 | end of utterance p50 / p95 / max |
|---|---|---|---|
| 0 | 0.04 / 2.01 | 0.24 / 0.33 | 79.8 / 148.3 / 280.6 |
| 40 | 0.09 / 1.96 | 0.24 / 0.34 | 99.6 / 188.9 / 262.6 |
| 100 | 0.08 / 2.06 | 0.25 / 0.36 | 107.5 / 201.0 / 281.0 |
| 200 | 0.09 / 2.10 | 0.25 / 0.36 | 103.1 / 180.3 / 274.4 |
| 300 | 0.09 / 2.11 | 0.25 / 0.36 | 99.4 / 193.3 / 256.3 |
| 500 | 0.07 / 1.99 | 0.24 / 0.34 | 99.5 / 173.0 / 272.1 |

The p95 per bin is the bins that complete a frame (1 in 4). The end-of-utterance cost is the word decoder's final pass; the decoder flush costs 0.4 ms or less. NumPy vs torch logits differ by at most 1.62e-04; actions match the accuracy stage on 200/200 trials at every L. The measurement environment was **not clean** (foreign load on the timing cores 5.77 %, SMT siblings busy 25.23 %; other agents ran tests). A first run gave the same picture.

> **Our take:** For a live display, a small lookahead (40 to 100 ms) buys most of the accuracy here. But the gain at L = 0 → 40 ms is so large that it may be a sign of our weak training, not a property of the data. Retest with a decoder near the published PER before we use the curve in Paper 2.

> **Our take:** The dedicated-model result is the more useful finding. A CTC model with L = 0 learns to emit late. A model with lookahead moves its emissions forward. So "L = 500 ms" can feel faster than "L = 0". Compare decoders by measured ready time, not by declared lookahead.

## What this means

### For the streaming decoder
- Train one model per L, or at least fine-tune per L. The shared model is simple, but it is worse at 500 ms (PER 0.3687 vs 0.3487) and it does not move its emissions forward.
- L delays only the partial output. The final decision at the end of an utterance costs the same for every L (flush + word decoder, about 100 ms p50). A product can show partial text at a small L and still decide on the full utterance.
- Compute is not a limit: under 3 ms per 80 ms frame on one CPU core set.

### For the NTS fields
- `latency` = `decoder.lookahead_s` = L x 20 ms, and `decoder.causal = true` at every L, including 500 ms. This matches MET-4 and MET-5 of the [NTS 1.0 draft](../concepts/nts-spec.md): frame t uses no signal after `frame_times[t] + latency`.
- `latency` is an **upper bound on signal use**. It is not the delay a user sees: the dedicated L = 500 ms model makes phonemes ready earlier than the L = 0 model. A consumer must not rank decoders by `latency`.
- Possible 1.1 item (not a spec change now): an optional, informative field for the measured emission delay (for example the median ready-time offset on a stated test set), next to `latency`.

## Limitations
- One participant, one seed, 30 epochs; the best epoch was the last in all three runs, so the models are under-trained.
- Dedicated models only at L = 0 and 500 ms.
- The trust config was not fitted to this decoder: no commit-side result.
- Emission timing uses the greedy path and exact matches only; the L = 0 models match fewer phonemes. The last emitted phoneme is about 3.1 to 3.7 s (median) before the trial end; we did not check why.
- Compute numbers: one machine, environment not clean.
- Deviations from the plan are listed in [results.md](../../experiments/2026-11-13-m4-01-02-lookahead/results.md#deviations-from-the-plan) (forced latency stage after the finished soak test, two bug fixes in the latency stage, figure reference).

## Related
- [Streaming trust layer](../concepts/streaming-trust-layer.md): the consumer of these frames.
- [NTS specification](../concepts/nts-spec.md): `latency`, `decoder.causal`, `decoder.lookahead_s`.
- [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md).
- [CTC](../concepts/ctc.md).
- [B2T '25 trust result](b2t25-trust-result.md): the trust layer on the published T15 decoder.
- [Architecture](architecture.md) (Paper 2: causal typing decoder).
