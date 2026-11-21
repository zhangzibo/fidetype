---
title: P14-55 robustness of the willett-hw no-signal gates - results
type: experiment
task: P14-55
updated: 2026-11-21
---

# P14-55: robustness of the `willett-hw` no-signal gates (results, 2026-11-21)

Pre-registration: [plan.md](plan.md) with [run.py](run.py) and [launch.py](launch.py), commit `34f3553`, before any number of this work was computed. Numbers: [results/results.json](results/results.json); log: [results/run.log](results/run.log). Per-item records (features and actions, no text) stay in `C:\Users\zhang\bci-data\derived\p14-55\` only.

## Verdict

**Every pre-registered rule passes. Gap 151 meets its done-when.** No gate, guard file or manifest changed.

| Part | Rule | Result |
|---|---|---|
| A1 | C5, time-shuffled input, 10 new draws (800): CP95 upper bound of the emit rate <= 0.05 | **pass**: 26 / 800 emit (0.0325), bound **0.0448** |
| A2 | C5, near-uniform frames, 10 new draws (800): same | **pass**: 0 / 800, bound 0.0037 |
| A3 | C5, zero input (no new draw exists): 0 / 80 repeats | **pass**: 0 / 80 |
| B | C5 re-fit spread (200 inner splits; 10 other time-shuffled draws) | reported (no rule); no coefficient changes sign |
| C1-C3 | offer gate, both guards: time-shuffled / frame-shuffled / near-uniform, 800 each: CP95 bound <= 0.05 and P5-31 rule | **pass** for both guards |
| C4 | `rev_in` (input reversed in time), 80: emits <= 4 and P5-31 rule | **pass**: built-in 2, LM 1 |
| C5r | `do_nothing` (real T5 data, no task), 27: emits <= 1 and P5-31 rule | **pass**: 0 and 0 |
| C6 | `lines` (real T5 data, straight-line task, unseen session), 80: emits <= 4 and P5-31 rule | **pass**: 0 and 0 |
| C7 | `rev_out` (log-prob frames reversed), 80: mechanism check, no rule | prediction holds: `coherence` equal to real on 80 / 80; the guards offer on **77 / 80** (built-in) and **78 / 80** (LM) |

## Checks

| Check | Result |
|---|---|
| The decoder on the raw sentences gives the P14-41 log-probs (first test and val sentence of each of the 10 sessions) | max abs difference 0.0 on all 20 |
| `config_id` of the packaged guards | `tcfg-39aac48688b8bd12`, `tcfg-26ae951a20a0cddd` (unchanged) |
| Re-fit of C5 on all 66 S positions with the d = 0 draw, from our feature copy of the fit rule | equal to the shipped gate (coefficients, `lo`, `r_max`: difference 0.0) |
| Near-uniform fast path (first 5 per guard decided in full) | 5 / 5 equal, both guards; no uniform input reached a threshold |
| Real test inputs (reference, recomputed) | C5 emits 79 / 80; offers 77 / 80 for each guard, 0 removed by the offer gate (= P14-49 / P14-54) |

## Part A: gate C5 over new draws (80 test sentences, LM readout)

| Input | Emit (pooled) | Rate | CP95 upper | Cluster bootstrap 95 % upper | Per draw (d = 1..10) | Draws above 4 / 80 | Sentences that emit in any draw |
|---|---|---|---|---|---|---|---|
| time-shuffled input | **26 / 800** | 0.0325 | **0.0448** | 0.0475 | 3, 1, 3, 2, 5, 1, 2, 1, 4, 4 | 1 | 15 / 80 |
| near-uniform frames | 0 / 800 | 0 | 0.0037 | 0 | all 0 | 0 | 0 |
| zero input (deterministic) | 0 / 80 | 0 | - | - | - | - | - |
| frame-shuffled frames (no rule; C5 does not read order) | 790 / 800 | 0.988 | - | - | 79 each | 10 | 79 |

Every time-shuffled input that passed C5 also gave non-empty text (26 passes, 26 emits). The P14-49 draw (d = 0) had 2 / 80.

C5 on the new null types (descriptive): `rev_in` 3 / 80 emit, `lines` 0 / 80, `do_nothing` 0 / 27, `rev_out` 79 / 80 (same as real: the posterior features of C5 do not depend on the frame order).

> **Our take:** A1 passes, but the margin is small. The pooled rate (3.25 %) is near the limit (5 %), one of ten draws has 5 / 80, and the cluster bootstrap bound (0.0475), which counts the reuse of the same 80 sentences, is also close to 0.05. The P14-49 test count (2 / 80) was a little lucky. The time-shuffled emits come from 15 sentences: for these sentences the shuffled bins still give a posterior that looks real to C5.

## Part B: re-fit spread of C5 (fits on val only)

Standardised coefficients, intercept, threshold `lo` and `r_max` (min / 5 % / median / 95 % / max):

| Value | Shipped (66, d = 0) | 200 half splits (fit on 33) | 10 re-fits on 66 with draw d = 1..10 |
|---|---|---|---|
| coef peak | 1.773 | 0.947 / 1.071 / 1.332 / 1.633 / 1.782 | 1.551 / 1.561 / 1.770 / 2.044 / 2.102 |
| coef neg_entropy | 1.045 | 0.686 / 0.762 / 0.917 / 1.151 / 1.252 | 1.021 / 1.036 / 1.182 / 1.397 / 1.455 |
| coef nb_share | 1.252 | 0.767 / 0.860 / 1.083 / 1.306 / 1.374 | 1.066 / 1.097 / 1.233 / 1.357 / 1.359 |
| coef kps | 1.145 | 0.707 / 0.824 / 0.986 / 1.145 / 1.241 | 0.816 / 0.896 / 1.112 / 1.148 / 1.158 |
| coef log(1 + n_keys) | 0.920 | 0.416 / 0.578 / 0.788 / 0.954 / 1.084 | 0.574 / 0.584 / 0.703 / 0.870 / 0.881 |
| intercept | 0.544 | -0.059 / 0.095 / 0.306 / 0.566 / 0.630 | 0.211 / 0.223 / 0.432 / 0.629 / 0.658 |
| `lo` | -1.170 | **-1.429 / -1.146 / 0.274 / 1.473 / 2.002** | -1.363 / -1.326 / -1.213 / -1.016 / -1.001 |
| `r_max` | 2.834 | 2.412 / 2.618 / 2.834 / 2.834 / 2.834 | 2.834 (all) |

Sign changes against the shipped coefficients: 0 in all 200 splits and all 10 draws.

Held-out counts of the 200 split gates (each evaluated on the other 33 positions):

| Count | Per split (min / 5 % / median / 95 % / max) | Sum over 200 splits |
|---|---|---|
| real inputs gated (of 33) | 0 / 0 / 1 / 4 / 9 | 235 / 6,600 (3.6 %) |
| time-shuffled d = 0 passing (of 33) | 0 / 0 / 0 / 1 / 2 | 47 / 6,600 (0.7 %) |
| time-shuffled d = 1..10 passing (of 330) | 0 / 0 / 0 / 9 / 12 | 447 / 66,000 (0.7 %) |

The 10 draw re-fits on test (C5 pass counts, an upper count of emits): real gated 1 / 80 for every re-fit; time-shuffled d = 0: 0-2 / 80; d = 1..10 pooled: 17-30 / 800 (shipped gate: 26 / 800).

> **Our take:** the direction of C5 is stable: all five features keep a positive weight in every re-fit, and a new time-shuffled draw moves the weights by about 15 %. The threshold is not stable. `lo` = the smallest real fit score (with fewer than 100 fit inputs the rule takes the minimum), so it depends on the one or two weakest real val sentences. With 33 fit inputs, `lo` ranges from -1.43 to 2.00, and the held-out real loss goes up to 9 / 33. The shipped `lo` (-1.17) is near the low end of the split range: it is low because S holds one weak real sentence, and this keeps the real cost at 1 / 80 on test. A new session or participant needs a re-fit with more than 66 real inputs, or a rule that does not use the minimum.

## Part C: the `coherence` offer gate on new null types (packaged guards, gate on)

Guard emits (COMMIT + OFFER; both guards never commit), the offers that the offer gate removed, and `coherence` (min / 5 % / median / 95 % / max). Real test reference: 77 / 80 offers for each guard.

**Built-in guard** (`tcfg-39aac48688b8bd12`, threshold 0.004183):

| Null | n | Emits | Removed by the offer gate | CP95 upper | P5-31 rule (p) | `coherence` | At or above threshold | Rule |
|---|---|---|---|---|---|---|---|---|
| time-shuffled (d = 1..10) | 800 | 14 (per draw 0-3) | 32 | 0.0272 | pass (7.0e-92) | 0.00018 / 0.00077 / 0.00237 / 0.00466 / 0.00644 | 82 | C1 pass |
| frame-shuffled (d = 1..10) | 800 | 0 | 770 | 0.0037 | pass | -0.00057 / -0.00034 / -0.00003 / 0.00043 / 0.00090 | 0 | C2 pass |
| near-uniform (d = 1..10) | 800 | 0 | 0 | 0.0037 | pass | about 0 | 0 | C3 pass |
| `rev_in` | 80 | 2 | 3 | - | pass (2.9e-39) | 0.00089 / 0.00161 / 0.00279 / 0.00454 / 0.00509 | 7 | C4 pass |
| `do_nothing` | 27 | 0 | 0 | - | pass (2.6e-22) | 0.00036 / 0.00038 / 0.00088 / 0.00208 / 0.00300 | 0 | C5r pass |
| `lines` | 80 | 0 | 6 | - | pass (1.0e-42) | 0.00141 / 0.00176 / 0.00239 / 0.00306 / 0.00356 | 0 | C6 pass |
| `rev_out` (no rule) | 80 | **77** | 0 | - | fail (0.66) | equal to real (80 / 80) | 77 | C7: as predicted |

**LM guard** (`tcfg-26ae951a20a0cddd`, threshold 0.002821; its decoder is the C5-gated LM readout):

| Null | n | Emits | Removed by the offer gate | CP95 upper | P5-31 rule (p) | `coherence` | At or above threshold | Rule |
|---|---|---|---|---|---|---|---|---|
| time-shuffled (d = 1..10) | 800 | 13 (per draw 0-3) | 11 | 0.0257 | pass (1.1e-92) | 0.00001 / 0.00015 / 0.00095 / 0.00273 / 0.00456 | 31 | C1 pass |
| frame-shuffled (d = 1..10) | 800 | 0 | 769 | 0.0037 | pass | -0.00057 / -0.00033 / -0.00004 / 0.00043 / 0.00095 | 0 | C2 pass |
| near-uniform (d = 1..10) | 800 | 0 | 0 | 0.0037 | pass | about 0 | 0 | C3 pass |
| `rev_in` | 80 | 1 | 1 | - | pass (7.5e-41) | 0.00014 / 0.00059 / 0.00118 / 0.00268 / 0.00395 | 2 | C4 pass |
| `do_nothing` | 27 | 0 | 0 | - | pass (2.6e-22) | 0.00004 / 0.00004 / 0.00016 / 0.00059 / 0.00074 | 0 | C5r pass |
| `lines` | 80 | 0 | 0 | - | pass (1.0e-42) | 0.00031 / 0.00062 / 0.00112 / 0.00184 / 0.00214 | 0 | C6 pass |
| `rev_out` (no rule) | 80 | **78** | 0 | - | fail (0.82) | equal to real (80 / 80) | 79 | C7: as predicted |

> **Our take:**
> - Real neural data without handwriting intent (`do_nothing`, `lines`) gives no offers. Its `coherence` stays below both thresholds: the decoder output keeps some frame order, but much less than on real handwriting. For the built-in guard, the guard itself withholds most of these inputs; the offer gate removed the other 6 `lines` offers.
> - The device stream reversed in time (`rev_in`) is mostly stopped: the decoder does not read reversed handwriting as letters. Some `rev_in` inputs reach the threshold (7 built-in, 2 LM), but only 2 and 1 get an offer.
> - The time-shuffled offer rate over 10 draws (1.75 % and 1.6 %) is the same as the P14-54 single draw (1 / 80 each).
> - **Limit found:** `coherence` is symmetric in time, so the gate cannot see a frame stream that is reversed after the decoder (`rev_out`). The guards then offer on 77-78 / 80 inputs, as often as on real input. This input is not a device signal: it can only come from a software fault that reverses the frame order. It is outside the gap 150 null set, so no rule failed. A direction-aware check would close it (new gap proposed below).

## Deviations from the plan

1. **`do_nothing` has 27 inputs, not 270.** Only `t5.2019.05.08/singleLetters.mat` holds `neuralActivityCube_doNothing`; the other nine files have the 31 character cubes only. We found this when the run stopped at session 2 (`KeyError`). We changed the script to read the doNothing trials only where they exist, and the rule limit became `floor(0.05 x 27) = 1` (the plan rule `floor(0.05 n)`). At that time an interim count of the 27 session-1 trials had been seen (0 offers). No rule or threshold changed. With n = 27 this null has less power than planned.
2. The score stage first failed on a JSON type error (`int64`); fixed in `save_json`, then the score stage was run again. No number changed.

## Run record

CPU only, isolation class `background`, 2 threads, detached with keep-awake. First start 11:02 (stopped at 11:17 by deviation 1; its 421 finished items were kept), restart 11:18: neural stage 2,146 s, `lines` 148 s, frames stage 701 s, score 2 s (end 12:08). 3,487 per-item records. Peak working set 783 MB.

## Limits

- One participant (T5), one decoder checkpoint, the 80 test sentences. The 10 draws reuse the same sentences, so the Clopper-Pearson bound treats correlated draws as independent; the cluster bootstrap bound (0.0475 for A1) is the more careful number.
- `do_nothing` has only 27 trials of one session. `lines` uses the day layer of another session (no layer exists for `t5.2019.06.03`).
- T15 / T12 data were not used: other participants, arrays (256 electrodes) and bin widths (20 ms) than the 192-channel, 10 ms T5 input; any channel map would be arbitrary.
- The guards stay offer-only (gap 138). The gates make the offer list depend on the signal; they do not make the offers correct.

## Rerun

| Step | Command (repo root) |
|---|---|
| All stages, detached (about 1 h CPU with 2 threads) | `.venv\Scripts\python.exe experiments/2026-11-21-p14-55-willett-gate-robustness/launch.py` |
| Check / done | tail `C:\Users\zhang\bci-data\derived\p14-55\run.log`; done when `derived\p14-55\DONE` exists (`FAILED` on an error) |
| Stop / resume | create `derived\p14-55\STOP`; resume: delete it and launch again (finished items are skipped) |
| Scores only | the same `run.py score` under `python -m fidetype.utils.isolation run --class background --threads 2 --` |

## Licence

Willett data CC0 1.0. LM text CC BY 2.0 FR (Tatoeba contributors); the LM file stays local. Our code Apache-2.0. This commit holds aggregates only: no weights, LM file, log-probs or text.
