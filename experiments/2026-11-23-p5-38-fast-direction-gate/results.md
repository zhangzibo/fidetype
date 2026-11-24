---
title: P5-38 faster lm_beam_direction offer gate (reuse the forward decode) - results
type: experiment
task: P5-38
updated: 2026-11-23
---

# P5-38 (gap 191): faster `lm_beam_direction` gate, reuse of the forward decode (2026-11-23)

Roadmap: [P5-38](../../wiki/questions/roadmap-standard.md#p5-38-faster-direction-gate-reuse-the-forward-decode). Done when: the gate reuses the forward beam of the guard decode, so only the reverse beam is new; decisions are equal on the P5-36b val and test sets; the new median extra time per sentence is measured and reported. CPU only. Code: [run.py](run.py), [launch.py](launch.py).

## What changed

| Item | Value |
|---|---|
| Library | `fidetype.pretrained.lmreadout.LmReadout` keeps the full sorted result of its last 2 searches (`search_cache = 2`; `0` = off). A search on log-probs that are bit-equal to a kept input (float64 bit patterns), with the same LM object and the same settings (`lm_weight`, `bonus`, `beam`, `prune_logp`), returns the kept result. The input is copied, and the result is copied out. `search_stats` counts searches run and searches served from the cache |
| Why it is exact | The search is deterministic and does not depend on `n`: `nbest(n)` sorts all final beams, then keeps the first `n`. So the kept list, cut to `n`, equals a new search |
| Effect, LM guard (`guard(readout="lm")`) | The guard decodes with the same readout object as the direction gate (P14-60 wiring), and on the same frames. So `S(x)` comes from the cache, and only the search on `rev x` is new: 2 searches per offer decision instead of 3 (decode + 2) |
| Effect, built-in guard (`guard()`) | None. Its decode is the built-in CTC beam without the LM, so no forward LM beam exists to reuse. The gate still runs 2 new searches |
| Not changed | Gates, thresholds, manifests, guard files, `config_id` values. The order "coherence first, the direction gate only if coherence passes" was already in place (P5-36b lazy gates) |

## Speed (fixed sample, CPU pinned)

The first 20 of the 80 test sentences (real input; all 20 are coherence-gate offers for both guards). `--class timing`: cores 8, 10, 12, 14, one thread, above-normal priority (the GPU job of another agent was not pinned to these cores). 3 repetitions per sentence, modes in rotated order, readout cache cleared before each timed decision; per-sentence median, then median over sentences. [results/bench.json](results/bench.json).

| Guard | coherence-only decision | extra per offer, cache off (P14-60) | extra per offer, cache on | gate alone, off -> on | searches per offer decision, off -> on |
|---|---|---|---|---|---|
| LM `tcfg-f498c0637536daec` | 0.324 s | **0.128 s** (CPU 0.133 s) | **0.063 s** (CPU 0.063 s) | 0.125 -> 0.066 s (ratio 0.53) | 3 -> 2 (+1 from the cache) |
| built-in `tcfg-39aac48688b8bd12` | 0.320 s | 0.243 s (CPU 0.250 s) | 0.249 s (CPU 0.258 s) | 0.271 -> 0.274 s (ratio 1.01) | 2 -> 2 |

"Extra per offer" = (decision with the shipped gate list) - (coherence-only decision). "Gate alone" = `lm_beam_direction(guard._last_lp, readout)` after a coherence-only decision (the P5-36b `t_beam2` measure). CPU time is `thread_time` (Windows resolution 15.6 ms, so the CPU medians are coarse). For the built-in guard the cache adds about 1 % (the input copy and the bit compare), which is in the noise of this sample.

## Decision identity (cache off vs on)

Compared per decision: action, raw action, text and shown choices (digest), `p_top1` and `guard_risk` (bit patterns), reason (digest), offer-gate reason (digest), and every offer-gate feature, `lm_beam_direction` included (float bit patterns; features collected on every decision). No text is stored. Per-item records: `C:\Users\zhang\bci-data\derived\p5-38\` only.

| Set | built-in: equal / n (offers off = on) | LM: equal / n (offers off = on) |
|---|---|---|
| P5-36b val S, real | 66 / 66 (65 = 65) | 66 / 66 (64 = 64) |
| P5-36b val S, `rev_out` | 66 / 66 (1 = 1) | 66 / 66 (1 = 1) |
| val LTT, real | 40 / 40 (40 = 40) | 40 / 40 (40 = 40) |
| P5-36b test, real (the 80 test sentences) | 80 / 80 (76 = 76) | 80 / 80 (75 = 75) |
| P5-36b test, `rev_out` | 80 / 80 (1 = 1) | 80 / 80 (2 = 2) |
| **All sets** | **332 / 332** | **332 / 332** |

[results/identity-sets-builtin.json](results/identity-sets-builtin.json), [results/identity-sets-lm.json](results/identity-sets-lm.json). The test counts equal the P14-60 wiring check (built-in 76 real, 1 `rev_out`; LM 75 and 2).

P14-56 offer-control re-check inputs (`recheck_offer_control`, P5-31 rule, shipped gate list; real LTT 40, uniform 300, frame-shuffled 300, time-shuffled 106): every `_decide_quiet` call recorded in order (digests of action, choices, reason, offer-gate reason), plus the re-check result dict. [results/identity-recheck.json](results/identity-recheck.json).

| Guard | decisions equal | result dict equal | real | uniform | frame-shuffled | time-shuffled | verdict | time off / on |
|---|---|---|---|---|---|---|---|---|
| built-in | 746 / 746 in order | yes | 40 / 40 | 0 / 300 | 0 / 300 | 0 / 106 | PASS | 3,697 / 3,693 s |
| LM | 746 / 746 in order | yes | 40 / 40 | 0 / 300 | 0 / 300 | 0 / 106 | PASS | 253 / 258 s |

These equal the shipped P14-60 re-checks. The re-check time does not drop: most of it is the null inputs, which the coherence gate withholds before the direction gate runs (the four re-checks ran in parallel, under `--class background`, so these times are not a speed measure).

Tests: `tests/test_lmreadout_search_cache.py` (5 tests, synthetic): equal hypotheses with the cache on and off; hits only on bit-equal input (a one-ulp change is a new search); input and output copies; settings and LM changes are new searches; a guard that decodes with the readout and has the direction gate runs 2 searches per decision (1 from the cache) and gives the same decisions, reasons and features as without the cache.

## Done-when check

| Part | Result |
|---|---|
| The gate reuses the forward beam of the guard decode; only the reverse beam is new | **Met for the LM guard** (searches per offer decision 3 -> 2). **Not possible for the built-in guard as written:** its guard decode is not an LM beam, so there is no forward LM beam to reuse |
| Decisions equal on the P5-36b val and test sets | Met for both guards (332 / 332 each), and on the P14-56 re-check inputs (746 / 746 each) |
| New median extra time per sentence | LM guard 0.128 -> 0.063 s per offer; built-in guard unchanged at 0.25 s |

> **Our take:** a built-in-guard speed-up needs a different change: a faster `LMBeam.push` (a bit-identical rewrite of the per-frame loop; a cProfile run puts 74 % of the gate time in the body of that loop, mostly numpy call overhead on 8-beam arrays), or a direction statistic that does not need the LM beam on the built-in guard's frames. The second changes the decisions, so it needs a new pre-registered check. Neither is done here.
