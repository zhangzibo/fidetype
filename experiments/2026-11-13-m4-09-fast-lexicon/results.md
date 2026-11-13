---
title: "M4-09: exact fast lexicon fallback and bounded prewarm: results"
type: experiment
task: M4-09
updated: 2026-11-13
---

# M4-09: exact fast lexicon fallback and bounded prewarm

Follow-up of [M4-08](../2026-11-13-m4-08-incremental/results.md). M4-08 left two problems on the B2T '25 word route: a slow end-of-utterance tail (the brute-force `PronLexicon.nearest` fallback) and push spikes up to 2.2 s with full prewarm. All numbers: [results/tables.md](results/tables.md), `results/b2t.json` (main run), `results/b2t-gc-freeze-once.json`, `results/b2t-gc-default.json`, `results/nearest.json`. Log: `results/run.log`. CPU only, one process.

## What changed (code)

| change | where | effect on results |
|---|---|---|
| `PronLexicon.nearest`: exact Levenshtein of the query to **all** fallback pronunciations of one length at once (NumPy; one DP row per query symbol; the insertion chain of a row is a running minimum `minimum.accumulate(tmp - j) + j`). Length buckets that cannot reach the best distance are skipped (length difference is a lower bound). | `src/fidetype/lm/phoneme_words.py` | none: same words, distance and order as `nearest_bruteforce` (kept as the reference) |
| `PhonemeWordDecoder.warm(texts)`: a generator; each `next()` fills one cache entry that `decode` would compute (candidates of one segment, its `nearest` fallback, or one sentence-LM score) | same | none: the caches hold values that `decode` computes anyway |
| `CTCBeamSpec(prewarm_budget_s=...)`: the prewarm runs in steps, at most about the budget per `push_frames` call (measured from the start of the call), and continues in the next pushes. A new prewarm replaces an unfinished one; `finalize` drops an unfinished one. `IncrementalPrefixBeam.prewarm(deadline=...)` | `src/fidetype/trust/incremental.py`, `src/fidetype/lm/beam.py` | none: prewarm only fills memos |
| Harness: `gc.collect()` + `gc.freeze()` after setup; automatic GC off while an utterance streams; `gc.collect()` between utterances | `run.py` (`gc_freeze`, `gc_idle` in `config.json`) | none on decisions; removes GC pauses from pushes |

## 1. `nearest()`: fast = brute force

Every distinct `nearest` query of the B2T test decode (1,889, recorded in the main B2T run, including the speculative prewarm queries; list outside the repo) and 3,000 synthetic queries (1,500 random strings over the 39 symbols, length 1-16; 1,500 lexicon pronunciations with 0-4 random edits), each with `max_len_diff` 2 (default), 0 and 4. Equal = the returned lists are `==` (word, distance, order).

| query set | calls | equal | brute p50 / p95 / max (ms) | fast p50 / p95 / max (ms) | total speed-up |
|---|---|---|---|---|---|
| B2T test queries | 5,667 | **5,667/5,667** | 108.9 / 188.6 / 253.6 | 5.16 / 9.27 / 25.16 | 20.9x |
| synthetic | 9,000 | **9,000/9,000** | 31.9 / 170.0 / 252.8 | 1.70 / 7.99 / 14.24 | 20.1x |

The query set of the first B2T run (1,888 queries) also gave 5,664/5,664 equal (first `nearest` stage, `run.log`).

Tests (`tests/test_fast_lexicon.py`, synthetic lexicons): `_levenshtein_many` equals the scalar edit distance; `nearest` equals `nearest_bruteforce` for 3 seeds x 331 queries (empty, random, other alphabet, edited pronunciations) x 5 `max_len_diff` values (-1 to 3); the index follows `set_fallback_words`.

## 2. B2T '25: 816 test utterances through the streaming layer

Data: the 816 split-A test streams of [M4-06](../2026-11-13-m4-06-real-replay/results.md) (Card et al. 2024, T15, CC0), full-precision NTS JSON Lines, 80 ms frames, one frame per push. Decoder as M4-08: phoneme CTC prefix beam (vector, beam 64, n_best 20) -> `PhonemeWordDecoder`. Prewarm every 5 frames, top 20 texts, at most 256 new alignments. Word-decoder caches are cleared at the start of each condition and kept across its trials (as in a live session). Main run: `gc.freeze()` after setup, automatic GC off inside a condition, one `gc.collect()` before each utterance (untimed; see section 3).

**Equality: 816/816 in every condition**, for our decoder and for the published gate (action, shown texts, p_top1, guard risk and prediction set `==` the M4-06 batch harness). Commits / wrong commits are unchanged: ours 82 / 20, published 329 / 24.

| condition | nearest | end p50 | end p95 | end max | push p95 | push max | CPU/utt p50 |
|---|---|---|---|---|---|---|---|
| batch (M4-06 path) | brute | 105.5 | 675.6 | 2361.3 | 0.02 | 0.2 | 108 |
| batch | **fast** | 94.9 | **172.2** | **265.0** | 0.02 | 0.2 | 97 |
| incremental, search only | brute | 87.9 | 679.4 | 2253.8 | 0.18 | 0.7 | 112 |
| incremental, search only | **fast** | 80.7 | **147.8** | **248.8** | 0.18 | 8.2 | 102 |
| incremental + full prewarm (M4-08) | brute | 32.9 | 70.8 | 602.3 | 20.43 | 2239.6 | 611 |
| incremental + full prewarm | fast | 32.6 | 73.7 | 130.7 | 20.39 | 118.7 | 519 |
| incremental + prewarm, budget 0.5 ms | fast | 69.8 | 137.6 | 236.4 | **0.84** | **12.7** | 192 |
| incremental + prewarm, budget 1 ms | fast | 52.3 | 117.9 | 219.7 | **3.10** | **30.3** | 271 |
| incremental + prewarm, budget 2 ms | fast | 34.9 | 95.1 | 212.7 | 5.46 | 36.7 | 377 |
| published gate, batch | fast | 97.6 | 170.6 | 286.6 | 0.02 | 0.2 | 99 |
| published gate, incremental | fast | 82.1 | 150.4 | 235.1 | 0.19 | 0.8 | 103 |

Times in ms. End = `push(end event)` until the final decision. CPU/utt = the sum of all push times of one utterance.

- **The fast `nearest` removes the end tail.** Batch end p95 676 -> 172 ms, max 2.4 s -> 0.27 s. Incremental search only: p95 679 -> 148 ms.
- **Full prewarm no longer has 2-s pushes** (max 2240 -> 119 ms), but its push p95 stays about 20 ms: each prewarm runs to its end inside one push.
- **Budgeted prewarm meets the push target** (p95 < 5 ms, max < 50 ms) at 0.5 ms and 1 ms. Budget 1 ms: push p95 3.10 ms, max 30.3 ms; end p50/p95 52/118 ms (search only: 81/148); CPU 2.7x the search-only route (full prewarm: 5.1x). Budget 2 ms misses p95 (5.46 ms). A push overshoots the budget by at most one step (largest steps: one `nearest` call, up to about 25 ms).
- Budget trade-off: a larger budget finishes more prewarm before the end (lower end latency) and costs more CPU.

## 3. Push spikes came from Python's cyclic GC

The first run (default GC; `results/b2t-gc-default.json`) gave push maxima of 303 ms and 402 ms with budgets of 1 and 2 ms. A GC callback showed the cause: gen-2 collections of 80-280 ms inside a push (the heap holds about 2.5 M objects: lexicon, LMs, cached streams).

| GC setting | budget 1 ms push p95 / max | automatic GC pauses > 5 ms (max) in that condition |
|---|---|---|
| default (first run) | 3.11 / 302.6 | not recorded |
| `gc.freeze()` once after setup (second run, `results/b2t-gc-freeze-once.json`) | 3.10 / 147.5 | 51 (149 ms) |
| freeze + automatic GC off in the utterance + `gc.collect()` between utterances (main run) | 3.10 / **30.3** | **0** |

- With freeze only, pauses came back, because objects from the earlier conditions and the growing caches are not frozen. A partial third run (freeze before each condition, automatic GC on) still had 60-70 ms push maxima without prewarm; we stopped it.
- The collection between utterances costs p50 40 ms (search only) to 89 ms (budget 1 ms) and up to 270 ms (full prewarm). It must run at an idle point, after the final decision is delivered.

> **Our take:** for a Python live decoder with a large lexicon, the GC is a bigger source of push spikes than the decoder. Deployment rule: `gc.collect(); gc.freeze()` after the models load; `gc.disable()` while an utterance streams; `gc.collect()` after its final decision. With that and a 1 ms prewarm budget, the B2T word route meets push p95 < 5 ms and max < 50 ms on this PC, with no change to any decision.

## Measurement notes

- One CPU process on the desktop PC (`time.perf_counter`), no other heavy job. The M4-08 numbers (batch end p50/p95/max 175/1010/3242 ms) were measured while the T12 GPU job and its CPU work ran in parallel. The brute-force rows here (105/676/2361) are the like-for-like baseline.
- Single push maxima are noisy (one OS scheduling delay can add tens of ms); for example, search only had 8.2 ms here and 0.7-0.8 ms in the other runs.
- Speculative prewarm is time-dependent, so the set of `nearest` queries differs a little between runs (1,884-1,889 distinct). Decisions do not: 816/816 in all three runs.

## Tests

`tests/test_fast_lexicon.py` (synthetic only): Levenshtein kernel = scalar; `nearest` = `nearest_bruteforce`; index follows `set_fallback_words`; `warm` fills the caches and changes no decode; `warm` is lazy; budgeted prewarm = batch for 3 budgets; a budget bounds the work per push to one step; `finalize` drops unfinished prewarm; `IncrementalPrefixBeam.prewarm(deadline=...)`; budget validation.

## Reproduce

Repo root: `.venv\Scripts\python.exe -I experiments/2026-11-13-m4-09-fast-lexicon/run.py b2t nearest tables` (CPU, about 1 h 15 min). Needs the M4-06 derived streams (`C:\Users\zhang\bci-data\derived\m4-06-real-replay\`). Per-trial outputs and the query list go to `C:\Users\zhang\bci-data\derived\m4-09-fast-lexicon\` (not in the repo).

## Next

- A worker thread is not needed for the B2T route with the budget. The idle `gc.collect()` grows with the cache size; bound the word-decoder caches (LRU) for long sessions.
- M4-01 / M4-02 (neural decoder lookahead) stay open.
