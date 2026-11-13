---
title: "M4-10: bounded decoder caches (LRU): results"
type: experiment
task: M4-10
updated: 2026-11-13
---

# M4-10: bounded decoder caches (LRU)

Follow-up of [M4-09](../2026-11-13-m4-09-fast-lexicon/results.md). The word decoder kept its memos for the whole session. They grew without limit. This task bounds them with an LRU rule and checks that no decision changes. All numbers: [results/tables.md](results/tables.md), `results/session-*.json`, `results/session-compare.json`, `results/b2t.json`. Log: `results/run.log`. CPU only, one process per run.

## What changed (code)

| change | where |
|---|---|
| `LRUCache`: a dict with an entry bound. When it is full, it removes the least recently used entry. `maxsize=None`: no bound. | `src/fidetype/lm/cache.py` (new) |
| `PhonemeWordDecoder(cand_cache_size=5000, lm_cache_size=50000)`: bounds on the two memos (segment -> lexicon candidates, word sentence -> sentence-LM score). None = unbounded. `set_cache_sizes`, `clear_caches`, `cache_info`. | `src/fidetype/lm/phoneme_words.py` |
| `CharNgramLM(cache_size=200000)`: the next-symbol memo is now LRU. Before, it was cleared completely when full. None = unbounded. | `src/fidetype/lm/ngram.py` |
| The beam memos (LM rows, alignments) stay as they are. They live in one `IncrementalPrefixBeam` per utterance and go with it. | docstring in `src/fidetype/trust/incremental.py` |

A memo stores only values of pure functions. So a bound can change the cost of a call, but not its result.

## 1. Long synthetic session: 2,000 utterances

Data: 2,000 synthetic phoneme streams (117,709 frames, 80 ms each). Each one is a Tatoeba sentence (3-12 words, all words in CMUdict) turned into CMUdict pronunciations. Random phoneme edits are added (10 % substitution, 4 % deletion, 4 % insertion), then the frames are built with Gaussian logits. Decoder and trust config are as M4-09: phoneme beam 64 -> `PhonemeWordDecoder` with CMUdict, the word unigram and the char 6-gram LM, plus the frozen M4-06 config (ours). The streaming layer runs with prewarm budget 1 ms. GC rule of M4-09: `gc.freeze()` after setup, automatic GC off during the session, and one timed `gc.collect()` after each final decision. One process per run.

**Equality: 2,000/2,000 decisions equal the unbounded run in every setting** (action, shown texts, p_top1, guard risk and prediction set `==`).

| run | bounds (cand / sentence-LM / char-LM) | entries at end | memo MB at end (cand / lm / char) | RSS after setup -> end (MB) | push p95 / max | end p50 / p95 | idle GC p50, first -> last 10 % |
|---|---|---|---|---|---|---|---|
| unbounded | None / None / None | 39,977 / 138,799 / 98,847 | 692 / 22 / 45 | 640 -> **1,387** (+747) | 2.47 / 11.9 | 80 / 153 | 14 -> **208** |
| **default** | 5,000 / 50,000 / 200,000 | 5,000 / 50,000 / 96,228 | 89 / 12 / 44 | 641 -> **707** (+66) | **2.32** / 16.4 | 85 / 158 | 13 -> **43** |
| small | 2,000 / 2,000 / 2,000 | 2,000 / 2,000 / 2,000 | 28 / 0.4 / 1 | 640 -> 661 (+21) | 1.36 / 16.4 | 115 / 232 | 9 -> 32 |
| 50,000 (first default, later dropped) | 50,000 / 50,000 / 50,000 | 39,302 / 50,000 / 50,000 | 668 / 12 / 25 | 641 -> 1,331 | 2.29 / 17.4 | 81 / 154 | 14 -> 199 |

Memo MB is a `sys.getsizeof` estimate of the container, keys and values. It leaves out the word strings, which the lexicon shares. Times are in ms.

| utterances | unbounded RSS / cand entries | default RSS / cand entries |
|---|---|---|
| 0 | 640 / 0 | 641 / 0 |
| 500 | 754 / 10,830 | 675 / 5,000 |
| 1,000 | 982 / 20,805 | 688 / 5,000 |
| 1,500 | 1,199 / 30,691 | 697 / 5,000 |
| 2,000 | 1,387 / 39,977 | 707 / 5,000 |

- **The candidate memo was the leak.** One entry holds about 17 KB, because a short phoneme segment often matches hundreds of lexicon words. Unbounded, it grew by about 0.35 MB per utterance (692 MB after 2,000). The sentence-LM and char-LM memos are much smaller.
- The first default (50,000 entries for both word memos) did not bound the candidate memo in 2,000 utterances: 39,302 entries, RSS +690 MB. That is why the defaults are now split: 5,000 candidates (about 85 MB at most) and 50,000 sentence-LM scores (about 10 MB).
- **Default bounds: RSS +66 MB over 2,000 utterances, and flat after about 1,000 utterances** (688 -> 707 MB over the last 1,000).
- **The idle GC also stays bounded.** Unbounded, the `gc.collect()` after each decision grew from 14 to 208 ms (p50), because the memo objects are not frozen. With the default bounds it reaches 43 ms.
- **Latency does not regress.** Push p95 is 2.32 ms with the default bounds and 2.47 ms unbounded (target < 5 ms). End p50/p95 is 85/158 ms against 80/153 ms. A very small bound (2,000) costs end latency (p95 232 ms), because more work is repeated at the end of the utterance.

## 2. B2T '25: 816 test utterances

Data and decoder as M4-09: the 816 split-A test streams of M4-06 (Card et al. 2024, T15, CC0), incremental route, prewarm budget 1 ms. The memos are new at the start of each condition and are kept across its trials.

**Equality: 816/816 in all three conditions** (`==` the M4-06 batch harness decisions).

| word / char-LM bounds | equal | entries at end (cand / lm) | evictions (cand / lm) | end p50 / p95 / max | push p95 / max | CPU/utt p50 | idle GC p50 / max |
|---|---|---|---|---|---|---|---|
| unbounded | 816/816 | 18,056 / 171,364 | 0 / 0 | 68.6 / 165.7 / 285.8 | 2.91 / 30.3 | 291 | 82.8 / 146.5 |
| **default** (5,000 / 50,000; char-LM 200,000) | 816/816 | 5,000 / 50,000 | 17,026 / 152,075 | 55.7 / 124.0 / 219.4 | **3.19** / 31.0 | 278 | 47.2 / 75.2 |
| 256 (all three memos) | 816/816 | 256 / 256 | 31,777 / 252,125 | 64.5 / 139.2 / 242.6 | 3.37 / 31.1 | 304 | 4.5 / 11.9 |

- Even 256-entry memos with about 250,000 evictions give the same 816 decisions.
- Push p95 stays under the 5 ms target (3.19 ms at the default; M4-09: 3.10 ms). Push max is 31 ms (M4-09: 30.3 ms).
- The end-latency differences between the rows are within run-to-run noise. The unbounded condition ran first in the process, and M4-09 measured 52/118/220 ms for the same setting. Hit and miss counters count `get` calls only. Prewarm (`warm`) fills the memos without `get`, so the eviction counts are larger than the misses.

> **Our take:** the bound is a free safety rail. Decisions never change, the push target holds, and memory stops growing. Without it, a full day of use (thousands of utterances) would add gigabytes and make each idle GC pass take hundreds of ms. The candidate memo is the one that matters. A later step could store only the `per_slot` best candidates per segment and make each entry about 50x smaller. That needs care, because experiments share one memo between word decoders with different weights.

## Measurement notes

- One CPU process per run (`time.perf_counter`; Windows working set = RSS through `K32GetProcessMemoryInfo`). The session streams are built one by one and are not kept in memory. The harness keeps only small per-utterance records, so RSS growth comes from the decoder state.
- The "50,000" run overlapped with a short pytest run (about 10 s). Its latency numbers are a little noisy.
- Speculative prewarm depends on time, so the set of memo entries differs a little between runs (for example 39,977 vs 39,302 candidates). The decisions do not differ.

## Tests

`tests/test_bounded_caches.py` (8, synthetic only): LRU order, refresh and eviction; unbounded mode, `resize` and validation; equality, pickle and copy; default bounds; word-decoder output identical for bounds 1, 2, 7, 40 and None over 120 utterances with warm steps mixed in; char-LM rows and sentence scores identical with bound 7; streaming with 3-entry memos and a 0.2 ms prewarm budget equals the unbounded batch decode. Full suite: 557 passed, 4 skipped.

## Reproduce

Repo root, one command per process:

```
.venv\Scripts\python.exe -I experiments/2026-11-13-m4-10-bounded-caches/run.py session none
.venv\Scripts\python.exe -I experiments/2026-11-13-m4-10-bounded-caches/run.py session default
.venv\Scripts\python.exe -I experiments/2026-11-13-m4-10-bounded-caches/run.py session 2000
.venv\Scripts\python.exe -I experiments/2026-11-13-m4-10-bounded-caches/run.py compare
.venv\Scripts\python.exe -I experiments/2026-11-13-m4-10-bounded-caches/run.py b2t
.venv\Scripts\python.exe -I experiments/2026-11-13-m4-10-bounded-caches/run.py tables
```

About 7-10 min per session run and 15 min for `b2t`. The B2T stage needs the M4-06 derived streams. Per-utterance decisions go to `C:\Users\zhang\bci-data\derived\m4-10-bounded-caches\` (not in the repo).
