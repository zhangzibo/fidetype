# P15-07 results: hallucination benchmark baselines (T15, T12)

Date: 2026-11-16. Code: `fidetype.benchmark.hallucination` (protocol `fidetype.halluc/0.1`). Docs: [docs/hallucination-benchmark.md](../../docs/hallucination-benchmark.md). Runner: [run.py](run.py). CPU only. RAM stayed well under 2 GB: the decoders and the LLM run from the P15-05 / P15-06 caches (read only), and no cache miss occurred.

## Setup

- Held-out sets: T15 `val_eval` (701 trials, Brain-to-Text '25, CC0 1.0) and the T12 test sessions (400 trials, Brain-to-Text '24, CC0 1.0). Split files: [`src/fidetype/benchmark/splits/halluc-v0.1/`](../../src/fidetype/benchmark/splits/halluc-v0.1/) (hashes and indices only).
- Controls: seed 0, `n_null` = 300, the P15-05 / P15-06 recipe. The benchmark rebuilds the same control inputs: every control input hit the P15-05 base n-best cache.
- Systems (saved guards; nothing is re-calibrated):
  - `p14-03-guard`: the P14-03 drop-in guard (α = 0.05, δ = 0.1), n-gram word decoder, no LLM.
  - `p15-05-B0_rescore`: P15-05 LLM rescoring (Qwen2.5-1.5B-Instruct Q4_K_M), no grounding.
  - `p15-06-B1_rescore_G`: the P15-06 guard: LLM rescoring + CTC grounding + fluent-wrong bound (joint LTT).
- Fluency: `llm-table` = the LLM scores in the P15-06 cache with the P15-05 threshold of each set (T15 −7.8817, T12 −8.9165 nats per word; 0 missing scores). `conservative` = every wrong commit counts as fluent.
- Per-trial records (with texts) stay in `C:/Users/zhang/bci-data/derived/p15-07-halluc-bench/`. The repo has the outcomes (flags) and the score cards in [`benchmark/results/halluc-v0.1/`](../../benchmark/results/halluc-v0.1/) and the summary in [results/results.json](results/results.json).

## Score cards

| Set | System | Real commits | Wrong commits (CP95) | Fluent-wrong, LLM (CP95) | Fluent-wrong, conservative | Null | Scrambled | Swapped commits (CP95) | Swapped leaks | Controls |
|---|---|---|---|---|---|---|---|---|---|---|
| T15 (701) | `p14-03-guard` | 2 | 2/701 [0.0003, 0.0103] | 0/701 [0.0000, 0.0052] | 2 | 0/300 | 0/300 | 2/701 [0.0003, 0.0103] | 0 | pass |
| T15 (701) | `p15-05-B0_rescore` | 9 | 2/701 [0.0003, 0.0103] | 2/701 [0.0003, 0.0103] | 2 | 0/300 | 0/300 | 9/701 [0.0059, 0.0242] | 7 | pass |
| T15 (701) | `p15-06-B1_rescore_G` | 0 | 0/701 [0.0000, 0.0052] | 0/701 [0.0000, 0.0052] | 0 | 0/300 | 0/300 | 0/701 [0.0000, 0.0052] | 0 | pass |
| T12 (400) | `p14-03-guard` | 25 | 15/400 [0.0211, 0.0611] | 4/400 [0.0027, 0.0254] | 15 | 0/300 | 0/300 | 25/400 [0.0409, 0.0909] | 10 | **fail** (swapped) |
| T12 (400) | `p15-05-B0_rescore` | 15 | 8/400 [0.0087, 0.0390] | 4/400 [0.0027, 0.0254] | 8 | 0/300 | 0/300 | 15/400 [0.0211, 0.0611] | 7 | pass |
| T12 (400) | `p15-06-B1_rescore_G` | 0 | 0/400 [0.0000, 0.0092] | 0/400 [0.0000, 0.0092] | 0 | 0/300 | 0/300 | 0/400 [0.0000, 0.0092] | 0 | pass |

Rates are over all items of a track. Intervals are Clopper-Pearson 95 %. Pass rule of a control track: commit rate ≤ 0.05.

## Checks

- Every number equals the P15-05 / P15-06 result of the same guard (real commits, wrong commits, fluent-wrong commits, null / shuffled / swapped commits, leaks). So the package reproduces the experiment code.
- `LLMFluency.from_gguf` (llama-cpp-python 0.3.36, CPU) gives the same log-prob as the cache for a test text (−92.0609).
- CI: `tests/test_halluc_bench.py` re-scores the 12 committed outcomes files (2 sets × 3 systems × 2 fluency modes) and compares each result with its committed score card.

## Findings

1. Null and scrambled inputs: 0 commits in all 6 baselines (CP95 upper 0.0122). These two tracks do not separate the systems on these sets.
2. Swapped signal: for both systems without grounding, swapped commits equal real commits (`swapped_to_real_commit_ratio` = 1.0). The guard follows the language side and ignores the signal. On T12 the P14-03 guard fails the track (25/400 = 0.0625 > 0.05). It has 10 leaks: it commits the text of the other trial.
3. The P15-06 guard passes every track on both sets, but it never commits (0/701, 0/400). This is "safe but no utility", as P15-06 reported.
4. LLM rescoring makes wrong commits more fluent: on T15, fluent-wrong goes from 0 (P14-03 guard) to 2 (B0); on T12, from 4 of 15 to 4 of 8 wrong commits.

> **Our take:** a fixed 0.05 rule on the swapped track is weak for a system that rarely commits: a system without a signal check can pass it. The ratio `swapped_to_real_commit_ratio` shows the problem directly (1.0 = no signal check). A later protocol version could make the ratio, or a paired test of it, a pass rule. The null and scrambled tracks are necessary sanity checks, but they were never the failure mode here.

## Open issues

- The tracks are not yet on the P6 leaderboard page or the P13 hub. The leaderboard code is in use by P14-05.
- No baseline commits often **and** checks the signal (P15-06 commits nothing). The benchmark needs such a system to show its range.
