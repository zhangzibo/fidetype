---
title: P5-41 bit-identical speed-up of the built-in guard direction gate - results
type: experiment
task: P5-41
updated: 2026-11-25
---

# P5-41 (gap 214): faster `lm_beam_direction` gate for the built-in `willett-hw` guard (2026-11-24)

Roadmap: [P5-41](../../wiki/questions/roadmap-standard.md#p5-41-bit-identical-speed-up-of-the-built-in-guard-direction-gate). Done when: the built-in guard's direction-gate extra time per offer drops measurably, with all decisions identical on the same identity check sets as P5-38. CPU only. Code: [run.py](run.py), [launch.py](launch.py). Harness: the P5-38 one ([P5-38 results](../2026-11-23-p5-38-fast-direction-gate/results.md)), with the mode switch changed from the readout cache to the search loop.

## Profile (before the change)

cProfile of `lm_beam_direction` alone on the gate inputs of the 20 bench sentences (built-in guard, 40 searches, one pinned core):

| Item | Value |
|---|---|
| Time in `LMBeam.push` | 6.70 of 6.72 s (99.6 %) |
| Self time of `push` (numpy ufunc calls on 8-beam arrays, inline) | 4.95 s (74 %) |
| numpy Python wrappers (`nonzero`, `argsort`, `searchsorted`, `argpartition`, ...) | about 0.7 s |
| LM lookups (`_row`, `_push_intended`) | 0.13 s |
| Frames | 103,037; 48,893 active (at least one key above the prune), mean 4.5 keys per active frame |

So the cost is numpy call overhead per frame, not arithmetic. The forward search cannot be reused (the built-in decode is not an LM beam), and both searches are needed for the value. So the only exact way is a faster loop.

## What changed

| Item | Value |
|---|---|
| Library | `fidetype.pretrained.lmreadout.LMBeam.push`: a new per-frame loop. The old loop stays as `LMBeam._push_reference` (reference for the tests; not used) |
| Same arithmetic | Every float value comes from the same operation on the same operands in the same order: the same `np.logaddexp` calls on the same arrays, the same adds and multiplies (`stay`, `flat`, `ext` expressions unchanged), the same `np.argpartition` call on the same values when more than `beam` extensions are finite (so ties at the cut keep the same extensions) |
| Changed bookkeeping | Allowed keys of all frames in one `np.nonzero`; merge of an extension into an existing prefix by a Python dict lookup (same rule as the `argsort` + `searchsorted` form: the first beam with that node); rank by a Python sort on `(-score, kind, index)` (the `lexsort` keys; scores are all > -inf, so no NaN); node, parent and last-key ids kept as Python lists; new beam values copied from lists (the length term adds 1.0 or 0.0, as the bool add did) |
| Tried, not kept | A block form for runs of frames with no allowed key (`np.add.accumulate` of the non-blank path): bit-equal but no faster (0.1048 vs 0.1016 s per search), so removed |
| Not changed | Decision logic, gates, thresholds, manifests, guard files, `config_id` (`tcfg-39aac48688b8bd12`, `tcfg-f498c0637536daec`), `offer_gate_id` (`ogate-3f39cc94f648400e`, `ogate-40628e48ebb65425`), the readout search cache |

## Speed (fixed sample, CPU pinned)

P5-38 sample: the first 20 of the 80 test sentences (real input; all 20 are coherence-gate offers for both guards). `--class timing`: cores 8, 10, 12, 14, one thread, above-normal priority. The P15-50 GPU training job of another agent ran at the same time, and other agents used the other cores; so all times are higher than in P5-38 (built-in "before" 0.337 s here, 0.243 s in P5-38). Before and after ran in the same process, interleaved (3 repetitions, rotated order, readout cache cleared before each timed decision), so the ratio is the fair measure. Per-sentence median, then median over sentences. [results/bench.json](results/bench.json).

| Guard | coherence-only decision | extra per offer, before | extra per offer, after | ratio | gate alone, before -> after | searches per offer decision |
|---|---|---|---|---|---|---|
| built-in `tcfg-39aac48688b8bd12` | 0.382 s | **0.337 s** (CPU 0.328 s) | **0.219 s** (CPU 0.219 s) | **0.65** | 0.354 -> 0.227 s (0.64) | 2 (no change) |
| LM `tcfg-f498c0637536daec` | 0.308 s | 0.090 s (CPU 0.078 s) | 0.045 s (CPU 0.047 s) | 0.49 | 0.068 -> 0.045 s (0.66) | 2, 1 from the cache (no change) |

"Extra per offer" = (decision with the shipped gate list) - (coherence-only decision). "Gate alone" = `lm_beam_direction(guard._last_lp, readout)` after a coherence-only decision, with the same cache state in both modes. CPU = `thread_time` (Windows resolution 15.6 ms). A first bench run, with three identity runs on the other cores, gave the same picture (built-in 0.354 -> 0.216 s, ratio 0.61; [results/bench-first-run.json](results/bench-first-run.json); its LM "gate alone" pair is not like-for-like, because only "before" had the cache cleared, so it is not used).

## Decision identity (before vs after)

Compared per decision: action, raw action, text and shown choices (digest), `p_top1` and `guard_risk` (bit patterns), reason (digest), offer-gate reason (digest), and every offer-gate feature, `lm_beam_direction` included (float bit patterns; features collected on every decision). No text is stored. Per-item records: `C:\Users\zhang\bci-data\derived\p5-41\` only.

| Set | built-in: equal / n (offers before = after) | LM: equal / n (offers before = after) |
|---|---|---|
| P5-36b val S, real | 66 / 66 (65 = 65) | 66 / 66 (64 = 64) |
| P5-36b val S, `rev_out` | 66 / 66 (1 = 1) | 66 / 66 (1 = 1) |
| val LTT, real | 40 / 40 (40 = 40) | 40 / 40 (40 = 40) |
| P5-36b test, real | 80 / 80 (76 = 76) | 80 / 80 (75 = 75) |
| P5-36b test, `rev_out` | 80 / 80 (1 = 1) | 80 / 80 (2 = 2) |
| **All sets** | **332 / 332** | **332 / 332** |

[results/identity-sets-builtin.json](results/identity-sets-builtin.json), [results/identity-sets-lm.json](results/identity-sets-lm.json). The offer counts equal P5-38 and P14-60.

P14-56 offer-control re-check inputs (`recheck_offer_control`, P5-31 rule, shipped gate list; real LTT 40, uniform 300, frame-shuffled 300, time-shuffled 106), every `_decide_quiet` call in order. [results/identity-recheck.json](results/identity-recheck.json).

| Guard | decisions equal in order | result dict equal | real | uniform | frame-shuffled | time-shuffled | verdict | time before / after |
|---|---|---|---|---|---|---|---|---|
| built-in | 746 / 746 | yes | 40 / 40 | 0 / 300 | 0 / 300 | 0 / 106 | PASS | 7,317 / 7,355 s |
| LM | 746 / 746 | yes | 40 / 40 | 0 / 300 | 0 / 300 | 0 / 106 | PASS | 201 / 157 s |

The re-check times are not a speed measure: the runs were in parallel under `--class background` on a loaded machine, and most built-in re-check time is the null inputs, which the coherence gate withholds before the direction gate runs.

Tests: `tests/test_lmbeam_fast_push.py` (7 test cases, synthetic): the full search state (beam arrays as bit patterns, node and intended-text tables, n-best with float bits) is equal to the reference loop after each chunk, on peaky input for 3 settings and 2 vocabularies (98 tokens, and a small one with every token kind), chunked and whole, with and without the LM; on input with many tied scores, with near-flat frames (the numpy candidate path, more than 64 candidates), with -inf values and all -inf frames, with an empty chunk, and with the lexicon term; the readout n-best and the `lm_beam_direction` value (with details) are bit-equal. A scratch check on the 20 real gate inputs, forward and reversed, whole and in 777-frame chunks: 40 / 40 states equal. Full suite: 1946 passed, 46 skipped.

## Done-when check

| Part | Result |
|---|---|
| Built-in guard direction-gate extra time per offer drops measurably | **Met:** 0.337 -> 0.219 s per offer (ratio 0.65; same run, same conditions); gate alone 0.354 -> 0.227 s |
| All decisions identical on the same identity check sets | **Met:** 332 / 332 and 746 / 746 per guard (built-in and LM) |
| No change to decision logic, thresholds, `config_id`, `offer_gate_id` | Met (values above; asserted by the harness) |

> **Our take:** the LM guard gets the same loop, so its gate and its decode are also faster (extra per offer 0.090 -> 0.045 s here). A further large step would need a compiled loop (for example numba or C), which adds a dependency; the per-frame numpy calls on 8-beam arrays are now the main cost.
