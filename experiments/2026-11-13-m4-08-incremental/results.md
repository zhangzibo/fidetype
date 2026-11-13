---
title: M4-08 incremental decoding in the streaming trust layer
type: experiment
updated: 2026-11-13
---

# M4-08: decode as the frames arrive

Task M4-08 (follow-up of M4-03 and M4-06). CPU only. Code: [run.py](run.py). Settings: [config.json](config.json). Tables: [results/tables.md](results/tables.md). Numbers: [results/b2t.json](results/b2t.json), [results/synthetic.json](results/synthetic.json). Log: `results/run.log`. Per-trial outputs: `C:\Users\zhang\bci-data\derived\m4-08-incremental` (not in the repo).

Run (repo root): `.venv\Scripts\python.exe -I experiments/2026-11-13-m4-08-incremental/run.py` (stages `synthetic b2t tables`; about 46 min, most of it the B2T conditions).

## Why
M4-06 measured the frame route on real data: a fresh decode at the end of the utterance took p50 173 ms, p95 992 ms, max 3.2 s. The layer itself adds under 1 ms. The time is the decoder, and all of it falls after the user stops.

## What we built
| Part | Where | What it does |
|---|---|---|
| `IncrementalPrefixBeam` | `fidetype.lm.beam` | The CTC prefix beam search (loop and vector search, LM fusion, all options) with its state carried across chunks: `push(chunk)`, `partial(n)`, `end_candidates()`, `prewarm(max_new)`, `finalize()`. `ctc_prefix_beam_search` is now this class with one chunk, so the batch result and the chunked result come from the same code |
| `ctc_forced_align_many` | `fidetype.lm.beam` | One Viterbi pass for all n-best texts. Each state sees the same values in the same order as `ctc_forced_align`, so the spans are the same. `finalize` uses it (the batch search too) |
| Alignment memo | `fidetype.lm.beam` | `prewarm()` aligns the texts that would be final now (n-best marginal pairs). `finalize` reads the memo. A memo never changes a value |
| `IncrementalDecoder` protocol | `fidetype.trust.incremental` | `push_frames(chunk)`, `partial() -> NBest` (provisional), `finalize(stream) -> NBest` |
| `IncrementalGreedy`, `IncrementalReferenceDecoder` | `fidetype.trust.incremental` | CTC greedy and the demo segment beam, one closed peak at a time (`SegmentTracker` = `find_segments` per chunk) |
| `CTCBeamSpec` / `IncrementalCTCBeam` | `fidetype.trust.incremental` | One beam setting gives both the batch `decode_fn` and the incremental factory. `post` makes the final n-best (for example our lexicon word decoder). `prewarm_every`, `prewarm_max_new` and `on_prewarm` run speculative end work |
| `BufferedDecoder` | `fidetype.trust.incremental` | Any batch `decode_fn` behind the interface (no time saved) |
| `StreamingTrustLayer(incremental=factory)` | `fidetype.trust.streaming` | Opt-in. One decoder per utterance. Frames go to it in chunks of `incremental_chunk_frames`, after the frozen frame temperature, row by row as the batch path applies it. Previews come from `partial()`. The final decision uses `finalize(stream)`. Default (no factory): unchanged |
| `stability_metrics` | `fidetype.trust.incremental` | Top-1 changes, rewrites, time to stable, prefix share of the previews |
| CLI | `python -m fidetype.trust.streaming replay --decoder greedy|demo --incremental` | Same output as without `--incremental` |

The B2T word decoder is experiment code (`experiments/2026-11-10-b2t25-trust`). `run.py` wraps it as `post` (phoneme beam output -> `PhonemeWordDecoder` -> `NBest`) and as `on_prewarm`:
- **light**: lexicon candidates of the complete words of the top 5 candidates (not the last segment);
- **full**: a word decode of the top 20 candidates (fills the lexicon and sentence-LM caches).

Prewarm runs every 5 frames (0.4 s) with at most 256 new alignments per call.

## Results

### 1. Equality with the batch path
Fields compared with `==`: action, shown texts, p_top1, guard risk, prediction set.

| input | condition | equal |
|---|---|---|
| B2T '25 test, 816 streams, our decoder | batch with the pre-M4-08 beam code (git `bc0dd3e`) | 816/816 vs the M4-06 batch harness |
| | batch with the new beam code | 816/816 |
| | incremental, incremental + light prewarm, incremental + full prewarm, incremental + light prewarm + previews every 5 frames | 816/816 each |
| B2T '25 test, published gate | incremental | 816/816 |
| Synthetic, 200 simulator streams (demo config, frame T 2.02) | greedy, demo segment beam, CTC beam RETUNED + 6-gram LM (with and without prewarm and previews) | 200/200 each |
| Old vs new beam code, 250 random streams × 5 search settings × LM on/off, random chunks + `partial` + `prewarm` between chunks (development check) | hypotheses, scores, spans, all confidence variants | 250/250 |

**Exact equality everywhere, also for the beam decoder.** The pruning order is the same because the batch search is the same per-frame code. No metric changed: B2T ours 82 commits / 20 wrong, published 329 / 24, as in M4-06 and Paper 1 Tab. 3.

### 2. End-of-utterance latency (B2T '25, 816 utterances, 80 ms frames)
End = `push(end event)` -> final decision. Push = one `push(frame)`. Times in ms.

| condition | end p50 | end p95 | end max | push p95 | push max | CPU per utterance p50 |
|---|---|---|---|---|---|---|
| batch, pre-M4-08 code (M4-06 path) | 174.7 | 1010.1 | 3241.8 | 0.017 | 0.2 | 178 |
| batch, new code (batched alignment) | 136.3 | 967.9 | 3124.2 | 0.017 | 0.4 | 139 |
| incremental, no prewarm | 122.2 | 1004.9 | 3099.4 | 0.25 | 0.9 | 154 |
| incremental + light prewarm | 80.3 | 843.3 | 3514.9 | 6.0 | 1042.8 | 278 |
| **incremental + full prewarm** | **33.2** | **70.9** | **594.8** | 20.8 | 2153.2 | 622 |
| incremental + light prewarm + previews | 49.8 | 469.5 | 1804.1 | 7.1 | 437.0 | 265 |

- The phoneme search moves out of the end path (about 50 ms of the p50). The tail stays: it is the word decoder. A few utterances have a word segment with no close lexicon entry, and the brute-force `nearest()` search then takes 0.5-3 s.
- Full prewarm runs that word work while the frames arrive. End p95 falls from 968-1010 ms to 71 ms (14×), the max from 3.2 s to 0.6 s.
- The cost moves into the pushes: push p95 21 ms (frame period 80 ms), but single pushes up to 2.2 s, and about 4.5× more CPU per utterance (speculative work on candidates that later change). A live consumer then lags for a moment and catches up; no frame is lost (the layer buffers).
- Timing noise: another agent ran a GPU job on the same PC. Compare rows inside one run, not across runs.

### 3. Synthetic streams (200 utterances, median 440 frames, 40 ms frames)

| decoder | batch end p50 / p95 | incremental end p50 / p95 | push p95 (incremental) |
|---|---|---|---|
| CTC greedy | 0.71 / 0.95 | 0.59 / 0.96 | 0.04 |
| demo segment beam | 10.9 / 14.1 | **0.86 / 1.09** | 0.26 |
| CTC beam RETUNED (beam 256) + 6-gram LM | 225.6 / 352.3 | 153.2 / 284.0; with prewarm **87.1 / 175.8** | 0.48; with prewarm 13.9 (max 97) |

For the LM beam, the rest of the end work is the end-of-sentence LM terms, the batched alignment and the "fused" confidences of 20 texts.

### 4. Stability of the provisional top-1 (previews every 5 frames)

| stream / decoder | previews per utterance | top-1 change rate | rewrites per utterance (mean) | last preview = final | stable before the end | median time stable before the end | previews that are a prefix of the final |
|---|---|---|---|---|---|---|---|
| B2T, word previews (top 3 phoneme partials -> words) | 36 | 0.29 | 4.4 | 65 % | 65 % | 1.28 s | 72 % |
| synthetic, greedy | 88 | 0.42 | 0.0 | 100 % | 100 % | 0.28 s | 100 % |
| synthetic, demo segment beam | 88 | 0.38 | 14.9 | 99.5 % | 99.5 % | 0.28 s | 58 % |
| synthetic, CTC beam + LM | 88 | 0.38 | 9.3 | 71.5 % | 71.5 % | 0.28 s | 70 % |

"Rewrite" = the new preview does not start with the old one: shown text changes, not only grows. "Stable before the end" = from some preview on, every preview equals the final top-1.

- On B2T the word preview changes in 29 % of the steps and rewrites shown text 4.4 times per utterance. In 35 % of the utterances the final top-1 differs from the last preview (the end-of-sentence terms and the last word change it).
- Greedy previews only grow (no rewrite), but greedy is the weakest decoder.
- The synthetic streams have no trailing silence, so they become stable only at the last preview.

## Conclusions
1. Incremental decoding in the layer is exact: 816/816 real B2T trials and 200/200 synthetic streams, for greedy, segment beam and CTC prefix beam with LM. No documented difference is needed.
2. Only the search moves for free. The B2T tail is the lexicon word decoder. Speculative prewarm cuts end p95 from about 1 s to 71 ms, at the cost of push spikes up to 2.2 s and about 4.5× CPU. Which one to use is a deployment choice (`prewarm_every`, `on_prewarm`).
3. Previews are unstable (B2T: 4.4 rewrites per utterance; the last preview differs from the final in 35 % of utterances). This supports the FEP-0001 rule: never act on `is_final = false`. A UI should show previews as grey, changeable text.

## Limits
- One participant (T15) and one split. CPU timings on a shared PC.
- The word decoder's `nearest()` fallback is the real tail. A faster exact lexicon search (for example a BK-tree or a bounded edit-distance automaton) would help both paths.
- Prewarm runs in the push thread. A worker thread or a time budget per push would cap the push spikes.
- M4-01 (lookahead of the neural decoder) and M4-02 (lookahead sweep) are not part of this task.
