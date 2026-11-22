---
title: P14-57 / P14-58 direction-aware offer check and C5 threshold rule (willett-hw) - results
type: experiment
task: P14-57, P14-58
updated: 2026-11-21
---

# P14-57 / P14-58: results (2026-11-21)

Pre-registration: [plan.md](plan.md) with [run.py](run.py), [launch.py](launch.py) and the library code, commit `e1f8573` (21:14), before any number of this work was computed. Numbers: [results/results.json](results/results.json), [results/p57-selection.json](results/p57-selection.json), [results/p58-rule.json](results/p58-rule.json), the two V re-checks `results/p57-recheck-*.json`; log: [results/run.log](results/run.log). Per-item records (features, actions; no text) stay in `C:\Users\zhang\bci-data\derived\p14-57\` only.

## Verdict

| Item | Verdict | Key numbers (test, 80 sentences) |
|---|---|---|
| **P14-57** (gap 171) direction-aware offer gate | **Negative result (numbers say why not).** The val selection already fails its own limit (section 3.2 step 4), so the chosen gate is "information only". On test, D1, D2 and D4 fail; D3 passes. | `rev_out` offers 77 -> **11** (built-in), 78 -> **18** (LM), limit 4; real offers removed **11** and **17** (limit 4) |
| **P14-58** (gap 172) C5 threshold rule | **Pass (E1, E2).** | new time-shuffled draws d = 11..20: emits **0 / 800**, CP95 **0.0037** (limit 0.04; shipped `lo` on the same draws: 18 / 800, CP95 0.0332); real gated **3 / 80** (limit 4; shipped 1 / 80) |

No shipped gate, guard file or manifest changed (plan sections 3.4, 4.4). `config_id` values unchanged: `tcfg-39aac48688b8bd12`, `tcfg-26ae951a20a0cddd`.

## P14-57: direction-aware offer gate

### Selection (val S, 66 real inputs, all 66 are offers for each guard)

`loss` = real S offers with candidate value < 0 (threshold 0 is fixed; limit `floor(0.05 x 66)` = 3).

| Candidate | Built-in | LM |
|---|---|---|
| `nb_decay_asym` | 52 | 47 |
| **`-nb_decay_asym`** (chosen, both guards) | **14** | **19** |
| `nb_time_asym` | 52 | 47 |
| `-nb_time_asym` | 14 | 19 |
| `time_asym` | 17 | 28 |
| `-time_asym` | 49 | 38 |

Chosen loss 14 / 66 and 19 / 66 > 3: **no candidate is good enough** (plan step 4). The test stage ran "for information only".

Checks on val: `coherence` of the reversed S inputs equals real on 66 / 66; the direction values are exactly antisymmetric (1e-9) on 66 / 66 (both guards). Val `rev_out` offers: 66 -> 14 (built-in) and 66 -> 19 (LM), as the threshold-0 rule predicts (= the val loss).

### Test rules (gates: shipped `coherence` AND `-nb_decay_asym >= 0`)

| Rule | Built-in | LM |
|---|---|---|
| **D1** `rev_out` offers <= 4 / 80 | **fail**: 11 / 80 (coherence only: 77) | **fail**: 18 / 80 (coherence only: 78) |
| **D2** real offers removed <= 4 / 80 | **fail**: 11 / 80 (77 -> 66) | **fail**: 17 / 80 (77 -> 60) |
| **D3** P14-55 nulls keep their results | **pass** (table below) | **pass** |
| **D4** P14-54 nulls and V re-check | **fail**: test nulls pass (time-shuffled 1, zero 0, frame-shuffled 0, near-uniform 0 of 80); V re-check controls 0 / 300, 0 / 300, 0 / 106, commits match the sheet; but real LTT offers **33 / 40** (limit >= 36) | **fail**: test nulls 0, 0, 0, 0 of 80; V controls 0 / 300, 0 / 300, 0 / 106, commits match; real LTT offers **32 / 40** |

Real test values of `-nb_decay_asym` (min / 5 % / median / 95 % / max): built-in -0.520 / -0.098 / 0.080 / 0.222 / 0.329; LM -0.611 / -0.185 / 0.075 / 0.277 / 0.371.

D3, offers with both gates (P14-55 offers -> now):

| P14-55 null | n | Built-in | LM |
|---|---|---|---|
| time-shuffled d = 1..10 | 800 | 14 -> 8 (CP95 0.018) | 13 -> 7 (CP95 0.016) |
| frame-shuffled | 800 | 0 -> 0 | 0 -> 0 |
| near-uniform | 800 | 0 -> 0 | 0 -> 0 |
| `rev_in` | 80 | 2 -> 1 | 1 -> 0 |
| `do_nothing` | 27 | 0 -> 0 | 0 -> 0 |
| `lines` | 80 | 0 -> 0 | 0 -> 0 |

All P14-55 limits and the P5-31 rule pass against the new real offers. The 22 P14-55 offered null inputs (20 time-shuffled, 2 `rev_in`) were made again from their seeds: 22 / 22 repeat their P14-55 action and `coherence` for both guards. Equivalence check (guard with both gates vs "coherence action, then the direction gate"): 160 / 160 per guard.

> **Our take:**
> - The decoder output has a time direction, but it is weak per sentence. The median sign is the same for most sentences: about 79 % (built-in) and 71 % (LM) of the val sentences have `-nb_decay_asym > 0`. That is a high-probability character column rises faster than it falls; the LM guard frame scaler makes it weaker. A 0-threshold gate then removes 1 in 5 real offers. This cost is too high for a check against a software fault.
> - `nb_time_asym` and `nb_decay_asym` have the same sign on every val sentence, so they are one signal. The all-column `time_asym` is weaker: the blank and the character columns trade mass, so their cubes partly cancel.
> - `rev_out` is not a device signal. A frame stream that is reversed after the decoder can only come from a software fault. The direct fix is a stream integrity check: frame indices or timestamps must increase. A per-sentence statistic is the wrong tool for it. We propose this as a new gap. A second option is a direction score with more power (for example a forward-vs-reverse character LM score of the decoded text). We do not test it here.

## P14-58: C5 threshold rule

### The rule on val

`lo_new = max(HD_0.03(real S scores), Q_0.99(val time-shuffled scores, d = 0..10, 726))` = max(**0.5659**, -1.1690) = **0.5659** (shipped `lo` -1.1697). The real part sets the value. On val: 1 / 66 real gated; 0 / 726 null scores at or above `lo_new`. Our score copy equals the shipped gate's score on the P14-55 records (max abs difference 0.0).

### Test rules

| Rule | Result |
|---|---|
| **E1** emits on 10 new time-shuffled draws d = 11..20 (800): CP95 <= 0.04 | **pass**: 0 / 800 (per draw all 0; cluster bootstrap bound 0), CP95 **0.0037** |
| **E2** real test gated <= 4 / 80 | **pass**: **3 / 80** (real emits 77 / 80) |

Comparison and descriptive counts (test):

| Input | Shipped `lo` -1.170 | `lo_new` 0.566 |
|---|---|---|
| time-shuffled d = 11..20 (new), emits | 18 / 800 (per draw 1, 3, 1, 3, 2, 1, 3, 2, 1, 1; CP95 0.0332) | **0 / 800** |
| time-shuffled d = 1..10 (P14-55, known), C5 passes | 26 / 800 | 1 / 800 |
| time-shuffled d = 0 (P14-41), passes | (P14-49: 2 / 80) | 0 / 80 |
| zero, near-uniform d = 1..10, `lines` | 0 | 0 |
| `rev_in`, passes | 3 / 80 | 0 / 80 |
| real gated | 1 / 80 | 3 / 80 |

### Stability (200 P14-55 half splits; coefficients re-fitted on half A; counts on half B)

| Value | Min rule (shipped rule) | New rule |
|---|---|---|
| `lo` (min / 5 % / median / 95 % / max) | -1.429 / -1.146 / 0.274 / 1.473 / 2.002 | -0.428 / -0.275 / 0.676 / 1.563 / 2.141 |
| real gated of 33 (min / 5 % / median / 95 % / max) | 0 / 0 / 1 / 4 / 9 | 0 / 0 / 1 / 4 / 10 |
| real gated, sum over 200 splits | 235 / 6,600 (3.6 %) | 281 / 6,600 (4.3 %) |
| time-shuffled d = 0..10 passing of 363 (min / 5 % / median / 95 % / max) | 0 / 0 / 0 / 9 / 12 | 0 / 0 / 0 / 2 / 3 |
| time-shuffled passing, sum | 494 / 72,600 (0.68 %) | 71 / 72,600 (0.10 %) |

> **Our take:**
> - The new rule meets the done-when with a large margin on the null side (0 / 800 vs a limit of about 22 / 800). It costs 2 more real sentences on test (3 / 80 vs 1 / 80).
> - The new rule is not much more stable at the top: with only 33 fit inputs, `lo` still reaches 2.14, and the worst held-out real loss is 10 / 33. Its gain is the low end. The 5 % split value goes from -1.15 to -0.27, so a fit with one weak real sentence no longer gives a low `lo` that lets null input through. The null pass rate falls by a factor of about 7.
> - Shipping `lo_new` changes the LM readout. It also changes the decoder of the LM guard, its `coherence` offer gate (fitted with the shipped C5) and the P14-56 offer-control block. We propose a new gap for this. It is a user decision because the real cost goes up.

## Deviations from the plan

1. **Order of work.** The V re-check of the built-in guard took 93 min (the 300 near-uniform controls are each decided in full, about 8 s each). The plan estimate was about 45 min for all stages. To keep P14-58 inside the 3 h cap, we stopped the run (STOP file) at 22:49, after the built-in re-check was saved. We relaunched it with the stages `p58 p57 score`, and finished items were skipped. No rule, input or draw changed. The LM re-check took 154 s (its 300 controls did not reach the slow path). End 23:11, inside the cap.
2. **Score-stage bug in the D3 repeat check, fixed after the first score run.** The check compared the number of made-again records of a guard (inputs that were offers for *either* guard: 20 time-shuffled) with that guard's P14-55 offers (14 and 13). So it reported "repeat failed" while 22 / 22 records repeated. We changed the check to "every record repeats, and this guard's repeated offers equal its P14-55 offers", then ran the score stage again. No count changed; D3 went from fail to pass.

## Run record

CPU only, isolation class `background`, 2 threads, detached with keep-awake. Part 1: 21:14:17-22:49:07 (select 91 s; P14-57 test, P14-54 nulls, P14-55 remakes and the built-in V re-check). Part 2: 22:49:14-23:11:06 (P14-58 1,158 s: rule and splits 9 s, 800 decoder passes over 10 sessions; LM V re-check 154 s; score). Score re-run 23:11. Peak working set 1.2 GB.

## Limits

- One participant (T5), one decoder checkpoint, 80 test sentences. The 10 new draws reuse the same 80 sentences. The cluster bootstrap bound counts this; it is 0 here because no input emitted.
- `rev_out` is a software-fault input; the D rules measure one statistic for it, not a stream check.
- The P14-58 rule keeps the shipped coefficients. The split check re-fits them, so it measures the rule and the fit together.

## Rerun

| Step | Command (repo root) |
|---|---|
| All stages, detached (about 2 h CPU, 2 threads) | `.venv\Scripts\python.exe experiments/2026-11-21-p14-57-direction-aware-offer/launch.py` |
| Check / done | tail `C:\Users\zhang\bci-data\derived\p14-57\run.log`; done when `derived\p14-57\DONE` exists (`FAILED` on an error) |
| Stop / resume | create `derived\p14-57\STOP`; resume: delete it and launch again (finished items are skipped) |
| Scores only | `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 2 -- .venv\Scripts\python.exe -I experiments/2026-11-21-p14-57-direction-aware-offer/run.py score` |

## Licence

Willett data CC0 1.0. LM text CC BY 2.0 FR (Tatoeba contributors); the LM file stays local. Our code Apache-2.0. This commit holds aggregates only: no weights, LM file, log-probs or text.
