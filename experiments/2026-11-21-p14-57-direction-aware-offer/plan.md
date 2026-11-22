---
title: P14-57 / P14-58 direction-aware offer check and C5 threshold rule (willett-hw) - pre-registration
type: experiment
task: P14-57, P14-58
updated: 2026-11-21
---

# P14-57 / P14-58: a direction-aware offer check and a C5 threshold rule for `willett-hw` (pre-registration, 2026-11-21)

Roadmap: [P14-57](../../wiki/questions/roadmap-standard.md#p14-57-direction-aware-offer-check-for-willett-hw) (gap 171) and [P14-58](../../wiki/questions/roadmap-standard.md#p14-58-c5-threshold-rule-without-the-minimum-real-score) (gap 172). Both come from [P14-55](../2026-11-21-p14-55-willett-gate-robustness/results.md) (gap 151).

We commit this plan, [run.py](run.py), [launch.py](launch.py) and the library code (below) **before** any number of this work is computed on `willett-hw` data. The synthetic unit tests ran before this commit; they use no real data.

Known at this time (all earlier results, nothing new):

- P14-54: the `coherence` offer gates (built-in `>= 0.004183`, LM `>= 0.002821`), real test offers 77 / 80 for each guard.
- P14-55: all rules pass; `rev_out` (log-prob frames reversed after the decoder) gets the same `coherence` as real input and 77 / 80 (built-in) and 78 / 80 (LM) offers. C5 time-shuffled emits 26 / 800 on test draws d = 1..10 (CP95 0.0448); the 10 draw re-fits of C5 (lo -1.36 to -1.00) gave 17-30 / 800 time-shuffled passes on the same test draws with 1 / 80 real gated; the 200 half-split re-fits gave `lo` from -1.43 to 2.00. Because these test numbers are known, the P14-58 test rule uses **new** time-shuffled draws (d = 11..20).

## 1. Done-when (roadmap text) and how we read it

| Item | Roadmap text | Our measure |
|---|---|---|
| P14-57 (gap 171) | a val-only pre-registered check stops `rev_out` at <= 4 / 80 offers on test for both guards, removes <= 4 / 80 real offers, and keeps the P14-54 / P14-55 null results; or numbers say why not | rules D1-D4 (section 3) |
| P14-58 (gap 172) | a pre-registered C5 threshold rule gives time-shuffled emits with a CP95 upper bound <= 0.04 over >= 10 draws and real input gated <= 4 / 80 on test; or numbers say why not | rules E1-E2 (section 4) |

Each gap meets its done-when when its rules are reported, **pass or fail**. A failed rule gives a proposed new gap.

## 2. Objects under test (fixed)

| Object | Value |
|---|---|
| Built-in guard | `load("willett-hw").guard()`, `tcfg-39aac48688b8bd12`, offer gate `coherence >= 0.004183` |
| LM guard | `load("willett-hw").guard(readout="lm")`, `tcfg-26ae951a20a0cddd`, offer gate `coherence >= 0.002821`, decode = the C5-gated LM readout |
| Gate C5 (LM readout) | manifest `readouts.lm.gate`: `logit` score, `lo` -1.16971, `r_max` 2.83412, `k_min` 1 |

Data: Willett handwriting 2021 (T5), CC0 1.0. P14-41 log-probs and item order (`derived/p14-41/`, read only). S = the 66 non-LTT val positions (`default_rng(0).permutation(106)[:66]`). Test = the 80 last-block sentences. P14-55 per-item records (`derived/p14-55/items.jsonl`, read only).

## 3. P14-57: a direction-aware offer gate

### 3.1 Why `coherence` cannot see the direction, and the new features

`coherence` = mean `P_t . P_(t+1)` minus the all-pairs mean. Both terms stay the same when the frame order is reversed. A direction feature must change when the order is reversed. We use features that are **exactly antisymmetric**: `f(reversed frames) = -f(frames)`. Library code (`src/fidetype/trust/offer_gate.py`, new in this commit):

| Feature | Value (`D_t = P_(t+1) - P_t`, frame probabilities of the guard after its frame scaler) |
|---|---|
| `time_asym` | `sum D^3 / sum |D|^3`, all columns |
| `nb_time_asym` | the same, non-blank columns only |
| `nb_decay_asym` | `sum P_t P_(t+1) (P_t - P_(t+1)) / sum P_t P_(t+1) |P_t - P_(t+1)|`, non-blank columns (> 0: a high probability falls more slowly than it rises) |

A gate feature name with a leading `-` is the negated feature (new: `OfferGate("-nb_time_asym", 0.0)`). The sign of a decoder (for example "the character probability rises slowly and falls fast") is a property of the decoder, so it is chosen on val.

**The threshold is 0 (fixed, not fitted).** With threshold 0, an input `x` and its reversal `rev(x)` cannot both pass (`f(x) >= 0` and `-f(x) >= 0` only if `f(x) = 0`). So the `rev_out` offers are at most the real inputs with `f(x) <= 0`, and the real offers removed are the real offers with `f(x) < 0`. No threshold is fitted, so there is no threshold spread.

### 3.2 Selection (val S only, per guard)

Candidates, in this order (the order breaks ties): `nb_decay_asym`, `-nb_decay_asym`, `nb_time_asym`, `-nb_time_asym`, `time_asym`, `-time_asym`.

1. Decide the 66 S val real inputs with the packaged guard (coherence gate on, offer features on). The m real S OFFERs are the selection set.
2. For each candidate: `loss` = the number of the m real S offers with candidate value < 0.
3. Chosen = the candidate with the smallest `loss` (ties: the order above).
4. If `loss(chosen) > floor(0.05 m)`, no candidate is good enough: the direction gate is a negative result for this guard. The test stage still runs for the chosen candidate, "for information only", and D1-D4 are reported with this note.

Also reported (descriptive, val): the `rev_out` offers of the val S inputs (frames reversed) with both gates.

### 3.3 Test rules (per guard; the gate set = the shipped `coherence` gate AND the chosen direction gate at 0)

| Id | Rule (pass iff) |
|---|---|
| **D1** | `rev_out` (80 test inputs, real log-prob frames reversed): offers **<= 4 / 80** |
| **D2** | real test offers removed by the direction gate **<= 4 / 80** (reference: the real test offers with the coherence gate only) |
| **D3** | the P14-55 nulls keep their results: for each of time-shuffled d = 1..10 (800), frame-shuffled (800), near-uniform (800), `rev_in` (80), `do_nothing` (27), `lines` (80), the offers with both gates are <= the P14-55 offers, and the P14-55 rule (C1-C3: CP95 bound <= 0.05; C4, C6: <= 4 / 80; C5r: <= 1 / 27; and the P5-31 `offer_control` rule) passes against the new real test offers |
| **D4** | the P14-54 nulls keep their results: test time-shuffled (d = 0), zero, frame-shuffled, near-uniform (80 each) emit <= 4 / 80; and the P14-54 V re-check (`recheck_offer_control(gated guard, lp_val_real, null_inputs=lp_val_timeshuf)`) passes, with real LTT offers **>= 36 / 40** (P14-54 R3) and commits that match the sheet |

How D3 is computed: adding a gate can only remove offers. So only the P14-55 inputs that were offers need a new decision; every other input stays a withhold. Each such input is made again from its P14-55 recipe and seed (time-shuffled and `rev_in`: the decoder on the raw sentence; frame-shuffled and near-uniform: from the test log-probs); its P14-55 action must repeat (check), then the direction gate is applied. If a P14-55 set has offers that we cannot make again, that set is reported as "not re-checked". D4 test sets: the P14-54 stored inputs (`lp_test_timeshuf`, `lp_test_zero`) and the P14-54 recipes for frame-shuffled and near-uniform (seed `p14-41|0|test|i|kind`), decided in full with both gates.

Check (exact equivalence): for the 80 real test inputs and the 80 `rev_out` inputs, the guard with both gates gives the same actions as "coherence-gated action, then withhold if the direction value < 0".

### 3.4 Shipping

**No shipped change in this item.** The manifest loader reads one offer gate per trust block; shipping a second gate needs list support in the manifest, the model card and the P14-56 offer-control blocks re-checked. If D1-D4 pass for both guards, we propose a new gap to ship the gate. The library code (new features, `-` names) is added; it changes no default.

## 4. P14-58: a C5 threshold rule that does not use the minimum

### 4.1 The rule (library: `fidetype.pretrained.lmreadout.quantile_lo`, `hd_quantile`, `ScoreGate.with_lo`)

The coefficients, `r_max` and `k_min` of C5 stay as shipped. Only `lo` changes:

`lo_new = max( HD_0.03(real fit scores), Q_0.99(null fit scores) )`

- `HD_0.03` = the Harrell-Davis estimate of the 3 % quantile of the C5 scores of the 66 S val real inputs. It is a weighted mean of all order statistics, so one weak sentence moves it little (the shipped rule takes the smallest score).
- `Q_0.99` = the empirical 99 % quantile (`numpy.quantile`, linear) of the C5 scores of the val time-shuffled inputs at S: the P14-41 draw d = 0 and the P14-55 val draws d = 1..10 (11 x 66 = 726).
- Why these values: 3 % of real loss is about 2.4 / 80 expected on test (limit 4); the null part stops the rule from going below the null bulk.

### 4.2 Test rules

| Id | Rule (pass iff) |
|---|---|
| **E1** | gate C5 with `lo_new`, 10 **new** time-shuffled test draws d = 11..20 (800; generator `default_rng(int.from_bytes(sha256("p14-57|d|test|i|timeshuf")[:8], "little"))`, the P14-41 recipe): emits pooled, one-sided 95 % Clopper-Pearson upper bound **<= 0.04** |
| **E2** | real test inputs (80) gated by C5 with `lo_new` **<= 4 / 80** |

Emit = C5 with `lo_new` passes and the ungated LM top-1 (`lm_readout().text(lp, use_gate=False)`) is not empty.

Also reported (descriptive): the shipped C5 on the same new draws d = 11..20 (the comparison); per-draw counts and the sentence-cluster bootstrap 95 % bound (2,000 resamples, `default_rng(5757)`); `lo_new` on the known P14-55 test draws d = 1..10, d = 0, zero and near-uniform (pass counts, from the P14-55 C5 scores); `lo_new` and its two parts.

### 4.3 Stability (val only, descriptive)

The 200 P14-55 half splits of S (`default_rng(5556)`, `permutation(66)`, 33 + 33). For each split: coefficients re-fitted on half A (real A against time-shuffled d = 0 at A, the P14-49 rule), then `lo` by (a) the shipped min rule and (b) the new rule (real A scores; null = d = 0..10 at A, 363). On half B: real gated (of 33) and time-shuffled d = 0..10 passing (of 363). Reported: min / 5 % / median / 95 % / max of `lo` and of the counts, for both rules.

### 4.4 Shipping

**No shipped change in this item.** A new `lo` changes the LM readout and the LM guard's decoder (its offer gate and the P14-56 offer-control block were measured with the shipped C5). If E1 and E2 pass, we propose a new gap to ship it with those re-checks.

## 5. If a rule fails

No change to any gate, guard file or manifest. We report the numbers and propose a new gap. Gaps 171 and 172 still meet their done-when ("or numbers say why not").

## 6. Compute

CPU only (`CUDA_VISIBLE_DEVICES`, `HIP_VISIBLE_DEVICES` = -1), `python -m fidetype.utils.isolation run --class background --threads 2`, detached by `launch.py`, keep-awake; log, `DONE` / `FAILED` in `C:\Users\zhang\bci-data\derived\p14-57\`. Per-item records go to JSONL at once; a restart skips finished items.

Estimate: P14-57 about 1,100 guard decisions per guard plus about 35 decoder passes (about 15 min); P14-58 800 decoder passes (about 21 min at 1.6 s) plus the LM search on the passing inputs. About 45 min in all. **Cap: 3 h.** If the run is not done after 3 h, it is stopped and the finished parts are reported; the number of draws is not reduced after the start. Order of work: P14-57 select, P14-57 test, P14-58.

Outputs in git: `results/*.json` (counts, thresholds and summary values only) and `results/run.log`. No log-probs, text or per-item records in git.

## 7. Not in this plan

Shipping either change (sections 3.4, 4.4); new C5 coefficients; other decoders; the certification of the `willett-hw` guards (gap 138).
