---
title: P14-55 robustness of the willett-hw no-signal gates - pre-registration
type: experiment
task: P14-55
updated: 2026-11-21
---

# P14-55: robustness of the `willett-hw` no-signal gates (pre-registration, 2026-11-21)

Roadmap: [P14-55](../../wiki/questions/roadmap-standard.md#p14-55-robustness-check-of-the-willett-hw-gate-c5) (gap 151). Follow-up of [P14-49](../2026-11-20-p14-49-willett-gate-blocked-lm/results.md) (gate C5 of the LM readout) and [P14-54](../2026-11-21-p14-54-willett-order-gate/results.md) (`coherence` offer gate of both guards).

We commit this plan and [run.py](run.py) **before** any number of this work is computed. Known at this time: the P14-49, P14-54 and P5-31 results (one draw of each null input), and a timing probe (one forward pass of the decoder on random counts: 1.6 s; one guard decision on a real test input: 0.45 s built-in, 0.28 s LM).

## 1. Done-when (roadmap text) and how we read it

| Part | Roadmap text | Our measure |
|---|---|---|
| A | C5 emit counts over at least 10 new draws of each null input, with a 95 % upper bound on the emit rate | section 4 |
| B | C5 re-fitted on other inner splits of the 66 val positions, spread of its coefficients and threshold | section 5 |
| C | the `coherence` offer gate of both guards re-checked on new null types (time-reversed streams, real data of another task or session) with a pre-registered rule | section 6 |

Gap 151 meets its done-when when A, B and C are reported with the rules below, **pass or fail** ("or numbers say why not"). A failed rule gives a new gap; it does not keep gap 151 open.

## 2. Objects under test (fixed, not changed by this work)

| Object | Where | Value |
|---|---|---|
| Gate C5 of the LM readout | manifest `willett-hw.json`, `readouts.lm.gate` | `kind: score`, `feature: logit`, `lo` -1.16971, `r_max` 2.83412, `k_min` 1 |
| LM readout | `load("willett-hw").lm_readout()` (default gate = C5) | LM `eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz` (local, read only) |
| Built-in guard + offer gate | `load("willett-hw").guard()` | `tcfg-39aac48688b8bd12`, `coherence >= 0.004183` |
| LM guard + offer gate | `load("willett-hw").guard(readout="lm")` | `tcfg-26ae951a20a0cddd`, `coherence >= 0.002821`; its `decode_fn` is the C5-gated LM readout |

All inputs go through the packaged API (`m.log_probs(x, session)`, `m.lm_readout()`, `m.guard(...)`). The script checks both `config_id` values.

**Emit** (C5, as P14-49 N1'): the gated LM readout gives non-empty text. **Guard emit**: the gated guard returns COMMIT or OFFER. Both guards are offer-only (no certified commit threshold), so a guard emit is an OFFER.

## 3. Inputs

Data: Willett handwriting 2021 (T5), CC0 1.0. Split and item order: the P14-41 order (`derived/p14-41/items.json`, read only; the script matches each sentence by its key). The 80 test sentences = the last block of each of the 10 sessions. S = the 66 non-LTT val positions (calibrate order, `default_rng(0).permutation(106)[:66]`).

### 3.1 New draws of the P14-49 null inputs (draws d = 1..10; the P14-41 draw is d = 0 and is not counted)

Generator per input: `default_rng(int.from_bytes(sha256("p14-55|d|split|i|kind")[:8], "little"))`.

| Kind | Recipe | Sets |
|---|---|---|
| time-shuffled input | a random permutation of the 10 ms bins of the neural input, then the decoder (P14-41 recipe) | test (80 x 10 = 800); val S (66 x 10 = 660, for part B) |
| near-uniform frames | `log(1/V) + 0.05 N(0,1)` logits of the real length, log-softmax (P14-41 recipe) | test (800) |
| frame-shuffled frames | a random permutation of the real test log-prob frames | test (800); not a C5 null (C5 does not read order, P14-49), but a P14-54 null of the offer gate |
| zero input | all-zero neural input | **no new draw exists**: the input has no randomness. We recompute it once (80) and report it |

### 3.2 New null types (part C; also run through C5, descriptive)

| Id | Null type | Recipe | n |
|---|---|---|---|
| `rev_in` | time-reversed stream (device side) | the neural bins of each test sentence in reverse order, then the decoder with the right day layer | 80 |
| `rev_out` | time-reversed stream (decoder side) | the real test log-prob frames in reverse order | 80 |
| `do_nothing` | real neural data of another task, same sessions | the `neuralActivityCube_doNothing` trials of `singleLetters.mat` (T5 was cued to do nothing; 201 bins = 2.01 s each), 27 per session x 10 sessions, each with its own day layer | 270 |
| `lines` | real neural data of another task **and** another session | `t5.2019.06.03/straightLines.mat` (straight-line drawing; this session is not in the model). 80 segments of the continuous `neuralActivityTimeSeries`, lengths = the 80 test sentence lengths; for each segment a block with enough bins is drawn uniformly, then a start uniformly inside it (`default_rng(5555)`). Day layer: index 0 (`t5.2019.05.08`, the nearest earlier session, 26 days before) | 80 |

`rev_out` is a mechanism check, not a null with a rule: `coherence` is the mean of `P_t . P_(t+1)` minus the all-pairs mean, and both terms do not change when the frame order is reversed. **Prediction:** `coherence(rev_out) = coherence(real)` for every input (to 1e-9), so the offer gate cannot stop it. Whether the guard offers on it depends on the decoder and LM.

### 3.3 Not used, with the reason

| Data | Why not |
|---|---|
| T15 (brain-to-text '25), T12 (brain-to-text '24) local data | Other participants and other arrays: 256 electrodes (T15: 512 features), 20 ms bins, other feature pipelines. The `willett-hw` input is 192 T5 threshold-crossing channels in 10 ms bins with a T5 day layer per session. Any channel map would be arbitrary, so the result would not describe a realistic input |
| `singleLetters.mat` letter trials | T5 writes one character per trial, so text output is expected: not a null |
| sentences of session A with the day layer of session B | real intended text (a shift, not a null); out of scope |

## 4. Part A: C5 emit counts over new draws

Measure: for each kind and draw d, the emits of the packaged gated LM readout on the 80 test inputs. The LM search runs only when C5 passes (an input that C5 stops cannot emit).

| Id | Null | Rule (pass iff) |
|---|---|---|
| **A1** | time-shuffled input, d = 1..10 pooled (800) | the one-sided 95 % Clopper-Pearson upper bound of the pooled emit rate is **<= 0.05** (= 4 / 80) |
| **A2** | near-uniform frames, pooled (800) | same |
| A3 | zero input (one deterministic input per sentence) | reported; P14-49 value 0 / 80 must repeat (a check, not a new draw) |

Also reported (descriptive): per-draw counts (min / median / max, and the number of draws above 4 / 80); a sentence-cluster bootstrap 95 % upper bound (2,000 resamples of the 80 sentences with their 10 draws, `default_rng(5557)`), because the 10 draws reuse the same 80 sentences, so the Clopper-Pearson bound treats correlated draws as independent; C5 pass counts (C5 passes, LM text may be empty); frame-shuffled emits (no rule, C5 does not read order).

## 5. Part B: re-fit of C5 (val only)

1. **Other inner splits.** 200 random half splits of S into 33 + 33 (`default_rng(5556)`, `permutation(66)`). For each split: fit C5 on half A with the P14-49 rule (`ScoreGate.fit("logit", real_A, 0.01, null=timeshuf_A(d=0))`), then count on half B: real gated, and time-shuffled passes on the d = 0 draw and on the 10 new val draws (pooled 330).
2. **Other time-shuffled draws.** 10 re-fits on all 66 S positions, each with the time-shuffled val draw d = 1..10 instead of d = 0. Count each on the test inputs: real test gated, time-shuffled test passes (d = 0 and d = 1..10 pooled). The test counts are descriptive: they do not change the shipped gate.

Reported: min / 5 % / median / 95 % / max of the 5 standardised coefficients, the intercept, `lo` and `r_max` over the 200 splits and over the 10 draws, the shipped values next to them, and the number of splits where a coefficient has the other sign than the shipped one. No pass rule (the done-when asks for the spread). The shipped gate does not change.

## 6. Part C: the `coherence` offer gate on new null types (both guards)

Each input is decided by each packaged guard with its offer gate on (`TrustGuard._decide_quiet`, offer features on), as in P14-54. We record the action, whether the offer gate removed an offer, and `coherence`. Near-uniform inputs use the P14-54 exact fast path: decide in full only if `coherence` reaches the gate threshold; the first 5 are always decided in full and their fast-path features must equal the guard's (relative tolerance 1e-6), else every input is decided in full.

Reference: the real test offers of each gated guard, recomputed in this run (P14-54: 77 / 80 for each guard).

| Id | Null | Rule (pass iff; for each guard) |
|---|---|---|
| **C1** | time-shuffled input, d = 1..10 pooled (800) | guard emits: one-sided 95 % Clopper-Pearson upper bound **<= 0.05**, and the P5-31 rule (`offer_control`: rate 0.05, ratio 0.5, p 0.05) passes against the real test offers |
| **C2** | frame-shuffled frames, pooled (800) | same |
| **C3** | near-uniform frames, pooled (800) | same |
| **C4** | `rev_in` (80) | guard emits **<= 4 / 80**, and the P5-31 rule passes |
| **C5r** | `do_nothing` (270) | guard emits **<= floor(0.05 x 270) = 13**, and the P5-31 rule passes |
| **C6** | `lines` (80) | guard emits **<= 4 / 80**, and the P5-31 rule passes |
| C7 | `rev_out` (80) | no rule: the prediction of section 3.2, and the guard emits, reported |

These limits are the gap 150 limits (each null at most 4 / 80 emitting; offer control pass).

## 7. If a rule fails

- **No change** to gate C5, the offer gates, the guard files or the manifest in this item. We report the failing rule with its numbers and propose a new gap with a done-when (for example: an order-direction feature for `rev_in` / `rev_out`, or a task check for `do_nothing` / `lines`, chosen on val only and tested on test).
- Gap 151 still meets its done-when (section 1).

## 8. Compute

CPU only (`CUDA_VISIBLE_DEVICES` and `HIP_VISIBLE_DEVICES` = -1), `python -m fidetype.utils.isolation run --class background --threads 2`, detached, keep-awake, log and `DONE` / `FAILED` files in `C:\Users\zhang\bci-data\derived\p14-55\`. Per-item records are written to JSONL as they are made; a restart skips finished items (sessions are re-read).

Estimate: about 1,600 decoder passes (about 45 min at 1.6 s), about 2,100 decisions per guard (about 30 min), plus the LM search on the inputs that pass C5: about 1.5-2 h in all. Budget limit 6 h: if the run is not done after 6 h, it is stopped and the parts that are done are reported (the order of work is: per session the test time-shuffled draws, zero, `rev_in`, the val time-shuffled draws and `do_nothing`; then `lines`; then the real test inputs, `rev_out`, frame-shuffled and uniform; then the scores of parts A, B and C). The number of draws is not reduced after the start.

Outputs in git: `results/*.json` (counts, thresholds, coefficients only). No log-probs, text or per-item records in git.

## 9. Not in this plan

Any new gate or feature; the default `offer_control` mode; `kt-semg-lda`; the certification of the `willett-hw` guards (gap 138).
