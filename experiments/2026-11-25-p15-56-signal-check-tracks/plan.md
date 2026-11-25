---
title: P15-56 signal-check tracks for the hallucination benchmark - truncated signal, graded noise mix, near-miss sentence swap (pre-registration)
type: experiment
task: P15-56
gap: 232
updated: 2026-11-25
---

# P15-56: three signal-check tracks (pre-registration)

Written and committed **before** any code of the tracks and before any run. No decision of any system on these tracks exists at this commit. CPU only. No GPU. No shipped guard, score card or published number changes because of this work.

## Why
The hallucination benchmark has three control tracks: `null`, `scrambled` and `swapped`. Null and scrambled inputs carry no information, and the swapped language side belongs to a sentence with a different text. These controls are coarse. The 2026-11-24 literature check ([confidence-ordering reversal](../../wiki/sources/confidence-ordering-reversal.md), Zhang & Liu 2026) found that after language-model fusion, the remaining errors can look more confident than the real repairs. A signal check must therefore also catch **small** and **partial** mismatches. The [E3 page](../../wiki/questions/frontier-e3-hallucination.md) lists the missing tracks. This plan adds three of them:

1. `truncated`: the decoder sees only the first part of the signal.
2. `noise_mix`: the signal is mixed with noise at three levels.
3. `near_miss`: the language side proposes a sentence that differs from the true sentence by one or two words.

## What does not change
- The tracks `real`, `null`, `scrambled`, `swapped`, protocol `fidetype.halluc/0.2`, its pass rules, the outcomes schema `fidetype.halluc.outcomes/0.1` and the score-card schemas. `to_outcomes` and `score_outcomes` ignore the new tracks. A test pins this: outcomes and cards with and without new-track records are equal, and every committed card still re-scores to the same file (the existing CI tests).
- The new tracks are **opt-in**. They have their own outcomes schema (`fidetype.halluc.signal-outcomes/0.1`) and their own card (`fidetype.halluc.signal-card/0.1`). They are not part of `controls_verdict`.
- The guards are read only. Nothing is re-calibrated. The decoders, the frame temperatures, the language models and the grounding settings are the saved ones.

## Common definitions
- Held-out set: the `n` held-out trials of the split file (T15: 701, T12: 400), in held-out order. Every new track has one item per held-out trial: item `j` uses the signal of trial `j`.
- Seed: `seed` = 0 (the benchmark default and the seed of all baselines). Generators: numpy `PCG64` (`default_rng`).
- Text comparison: as the benchmark (runs of spaces joined, ends stripped).
- Pairs: real item `j` and new-track item `j` use the same signal trial. `R_j` = 1 if the real item commits (any text). `S_j` = 1 if the new-track item makes an **unsupported** commit (definition per track below).
- Paired test: the protocol 0.2 swapped test, unchanged (`paired_swap_test`): `m = n10 + n01 + n11`, `Y = n01 + n11`, `θ_r = r / (1 + r)`.
  - `pass`: one-sided Clopper-Pearson upper bound (1 − α) of `Y / m` < `θ_r`.
  - `fail`: not pass, and (`m ≥ m_min`, or the lower bound of `n01 / m` > `θ_r`).
  - `insufficient evidence`: all other cases. It is never a pass.
  - Constants: `r` = 0.5, α = 0.05, `m_min` = 25 (the protocol 0.2 values). In words: the system passes a level if, with 95 % confidence, unsupported commits on the level are fewer than half of its real commits.
- Combination of levels into a track verdict: `fail` if any scored level fails; `pass` if all scored levels pass; else `insufficient evidence`.
- Card verdict `signal_checks_verdict`: `fail` if any of the three tracks fails; `pass` if all three pass; else `insufficient evidence`.

## Track 1: `truncated` (only the first part of the signal)
- Levels `f` ∈ {0.25, 0.50, 0.75}. Track keys `truncated_25`, `truncated_50`, `truncated_75`.
- Input of item `j`: the first `max(1, ceil(f · T_j))` frames of the held-out input `x_j` (`T_j` frames). No random draw.
- Language side: the system's own (as for `real`).
- **Supported** commit: the committed text is a **proper word prefix** of the truth of trial `j` (1 to `w_j − 1` words, each equal to the truth word at the same position). **Unsupported** commit: every other commit, including the full true sentence. Reason: the frames after the cut carry the rest of the sentence. A commit of the full sentence comes from the language side, not from the signal.
- Scored levels: `truncated_25` and `truncated_50`. `truncated_75` is reported but has **no pass rule**: in some trials the speech ends before 75 % of the frames, so the full sentence can be supported there.
- Reported per level: commit rate, unsupported commits, supported prefix commits, full-truth commits, paired cells, verdict.

## Track 2: `noise_mix` (graded noise)
- Levels `λ` ∈ {0.25, 0.50, 0.75}. Track keys `noise_mix_25`, `noise_mix_50`, `noise_mix_75`.
- Noise: `rng = default_rng([seed, 13])`. For each item `j` in held-out order, one matrix `q_j = −log V + σ · rng.standard_normal((T_j, V))` with σ = 0.05 (the null-track noise), renormalised per frame (log-softmax). The three levels use the **same** `q_j`, so the levels are nested.
- Input of item `j` at level `λ`: per frame, `log((1 − λ) · softmax(x_j) + λ · exp(q_j))`, float32. At `λ` = 1 this is the null input. At `λ` = 0 it is the real input.
- Language side: the system's own.
- **Unsupported** commit: a commit whose text is not the truth of trial `j` (the `wrong` flag of the real track).
- Scored levels: all three.
- Reported per level: commit rate, wrong commits, error among commits, paired cells, verdict. Diagnostic (no rule): the commit rate should not rise with `λ`.

## Track 3: `near_miss` (near-miss sentence swap)
- Near-miss text `v_j` of trial `j`, from `rng = default_rng([seed, 17])`, items in held-out order. Let `w_j` = number of words of the truth.
  1. `e_j` = 1 if `w_j` = 1, else `e_j = 1 + rng.integers(0, 2)` (1 or 2 word edits).
  2. Positions: `sorted(rng.choice(w_j, e_j, replace=False))`.
  3. For each position in order: draw `rng.integers(0, len(pool))` until the pool word differs from the truth word at that position; replace it. `pool` = the sorted set of all words in the held-out truths of the set (so the words are real words of the task vocabulary).
  4. So `v_j` has the same number of words as the truth and differs from it in exactly `e_j` positions.
- Input: the signal `x_j` (unchanged). Language side: the near-miss text `v_j`.
- **Unsupported** commit: a commit whose text is not the truth of trial `j`. The card also counts `near_miss_commits` (commits equal to `v_j`).
- Benchmark interface: `decide_near_miss(x_signal, near_miss_text, item)`. How a system takes `v_j` as its language side is system-specific and the card names it (as for `swapped`).
- **Our baselines** (n-best decoders): the language-side n-best list is the system's own base n-best list of trial `j`, with the **text of the top candidate replaced by `v_j`**. All score fields of the top candidate stay (`score`, `logp_acoustic`, `logp_lm`). Its `char_confidences` are mapped to the new length by relative position (character `c` of `v_j` takes the value of character `round(c · (L_0 − 1) / (L_v − 1))` of the old top text; one character: the first value). Any other candidate whose text equals `v_j` is removed. Then rescoring (if the arm has it), grounding (if the arm has it) and the guard run as on the real track, with the signal `x_j`. This simulates the failure of the source: language fusion puts a near-miss on top, with the confidence features of the top candidate.
- Scored: one test.

## Systems (the shipped baselines; guards read only)
The 10 systems that have committed protocol 0.2 score cards (`benchmark/results/halluc-v0.2/`):

| Set | Systems | Decoder input | Caches (read only) |
|---|---|---|---|
| T15 `b2t25-t15-val-eval` (701) | `p14-03-guard`, `p15-05-B0_rescore`, `p15-06-B1_rescore_G` | M4-12 fixed0 log-probs | P15-05 / P15-06 base n-best and LLM caches |
| T15 `b2t25-t15-val-eval` (701) | `m4-13-p15-05-A0_ngram`, `m4-13-p15-05-B0_rescore`, `m4-13-p15-06-B1_rescore_G`, `m4-13-p15-06-B1_rescore_G@single` | M4-13 long0 log-probs | M4-13 rerun caches |
| T12 `b2t24-t12-test` (400) | `p14-03-guard`, `p15-05-B0_rescore`, `p15-06-B1_rescore_G` | T12 v2 log-probs | P15-05 / P15-06 T12 caches |

New inputs miss the caches. The runner then decodes on the CPU with the same word decoder (phoneme beam + lexicon + n-gram LM; T12 with its word trigram) and scores new texts with the same LLM (Qwen2.5-1.5B-Instruct Q4_K_M, llama-cpp-python, CPU). It writes its new cache entries only to `C:/Users/zhang/bci-data/derived/p15-56/`.

## Checks before results count
1. **Real-track replay:** the runner re-runs the real track of each system and compares the `committed` and `wrong` flags with the committed outcomes file. Any difference stops that system (reported, no card).
2. The near-miss texts differ from the truth in exactly `e_j` words (assert per item).
3. Fluency: `llm-table` (the caches plus the new LLM scores; threshold of each set as in the committed cards) and `conservative`. The verdicts use commit flags only, so both modes give the same verdicts.

## Expectations (stated before the run; not pass rules)
- Systems without grounding (`p14-03-guard`, `B0`, `A0`): on `near_miss`, unsupported commits about equal to real commits (they follow the language side), so `fail` where `m ≥ 25`.
- Systems that never or rarely commit on the real track: `insufficient evidence` on most tracks (`m` < 8 gives no pass).
- No prediction for the grounded systems on `truncated` and `noise_mix`.

## Outputs
- Code: `fidetype.benchmark.hallucination` (new functions, opt-in), tests in `tests/`. Docs: a new section in `docs/hallucination-benchmark.md`.
- Repo (flags only, no text): `results/` of this folder: signal outcomes and signal cards per system and fluency mode, `results.json`, `run.log`. Per-trial records (texts) and caches: `C:/Users/zhang/bci-data/derived/p15-56/` only.
- The existing cards in `benchmark/results/` are not edited.

## Cost estimate
Base decode about 0.1 s per input; LLM about 0.12 s per text with 3 threads, about 10 texts per input. New inputs: 6 truncated / noise levels × (701 + 701 + 400) = 10 812, plus near-miss texts. About 2 to 3 CPU hours for the LLM scores (shared between `B0` and `B1`), less than 1 hour of decoding. No GPU-hours. RAM: below 5 GB (T12 word trigram + LLM).

## Done when (gap 232)
The three tracks exist with fixed seeds and docs, and the 10 shipped systems are scored on them (or a system is reported as stopped by check 1).
