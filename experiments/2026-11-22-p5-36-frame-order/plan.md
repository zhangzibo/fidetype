---
title: P5-36 frame-order integrity check in the trust layer - pre-registration
type: experiment
task: P5-36
updated: 2026-11-22
---

# P5-36: frame-order integrity check in the trust layer (pre-registration, 2026-11-22)

Roadmap: [P5-36](../../wiki/questions/roadmap-standard.md#p5-36-frame-order-integrity-check-in-the-trust-layer) (gap 181). Source: [P14-57](../2026-11-21-p14-57-direction-aware-offer/results.md) (negative result: a per-sentence time-direction statistic of the frames removes 11 / 80 and 17 / 80 real offers).

We commit this plan, [run.py](run.py), the library code and the synthetic tests **before** any number of this work is computed on real data. The synthetic tests ran before this commit; they use no real data.

## 1. What `rev_out` is, and what a time check can see

We read the P14-57 code ([run.py](../2026-11-21-p14-57-direction-aware-offer/run.py), `stage_p57`). `rev_out` is `guard.decide(lp[::-1])`: a `(T, V)` NumPy matrix with its rows reversed. The matrix has **no times**. The guard makes the times itself (`_Codec.stream` -> `from_array`: `t = frame_period * (1 + arange(T))`). So the guard sees **strictly increasing** times for `rev_out`, as for real input.

Consequence (stated before the run): **a check of frame times or frame indices cannot catch `rev_out` as P14-57 built it.** It is a fault in the frame **values**, with the times in order. We expect 0 / 80 of these inputs to be flagged by the time check (rule R1, section 4).

What the NTS stream carries today (spec RC4, section 5.1; `src/fidetype/streams/spec.py`; `src/fidetype/trust/streaming.py`):

| Item | Content | Check today |
|---|---|---|
| Frame time `t` (event) / `frame_times` (array form) | seconds, TIM-1 finite, **TIM-2 strictly increasing** | the streaming layer **raises** `StreamEventError` on a non-increasing `t` (`push`, `push_frames`); `NeuralTextStream.validate` **raises** `ValueError` |
| Frame index | none (NTS has no frame index field) | - |
| `seq` | on `trust_decision` events only (TD-5), not on frames | - |
| `ws_seq` | WebSocket binding only (WS-Q1..Q3: reorder window, gaps) | the binding |
| `TrustGuard.decide(x)` | a matrix; **times of the producer are dropped** | none |

So the gap in the trust layer is narrow: a caller with a `(T, V)` matrix and the producer's times had no way to give the times to the guard, and a bad stream on the event path gives an exception, not a recorded non-acting decision.

## 2. What we build (two routes)

### Route 1: stream-integrity check (library, opt-in)

- New module `fidetype.trust.integrity`: `check_frame_times(times, n_frames, min_step=0.0, max_step=None)` -> `IntegrityReport` (no exception). Codes, first match wins: `frame_times_shape`, `frame_times_not_finite`, `frame_order_reversed` (every step < 0), `frame_order` (a step < `-min_step`), `frame_duplicate` (a step in `[-min_step, min_step]`), `frame_gap` (opt-in, `max_step` set). Default tolerance `min_step = 0`: TIM-2 exactly ("strictly increasing"). `check_events(events)` does the same on NTS frame events.
- `TrustGuard.decide(x, frame_times=...)` and `GuardSession.push(chunk, times=...)`: if the producer's times are given, the check runs. **Action on a failed check: ABSTAIN** (user action `withhold`, nothing shown), for any action of the policy (also a COMMIT). The reason starts with `withhold: stream integrity check failed (<code>: ...)`. The audit record gets the key `integrity` (the report). Settings: `guard.frame_check`.
- **`config_id`:** the check is a **separate, documented integrity layer**, not part of the frozen configuration. It does not change `config_id`. Why this is honest: on a stream that meets TIM-2 the decision is computed exactly as before (the times are not used for it); the check only turns a decision on a stream that breaks the spec rule TIM-2 into a WITHHOLD. Rule I3 tests "no change on valid streams". No shipped manifest or guard file changes.
- What route 1 catches: a fault that moves frames **together with their times** (reversed, reordered or repeated frames at the transport or adapter level). What it does not catch: a value fault with times in order (`rev_out`), and input without times.

### Route 2: forward-vs-reverse character-LM direction score (the second route the gap names)

- New offer-gate feature `lm_direction` (logits input; needs a character LM): `s` = `normalize_text` of the greedy CTC text of the frames; value = `(log p(s) - log p(reverse(s))) / (len(s) + 1)`, end marker included, 0 for an empty text. The greedy text of reversed frames is the reversed text, and `normalize_text` keeps that, so the value changes sign **exactly** when the frame order is reversed (checked: 1e-9).
- LM: the packaged LM of the `willett-hw` LM readout, `eng_tatoeba_6gram_mkn_noE2Q_noWillett` (Tatoeba, every Willett text blocked; P15-38). It is the same LM object (`m.lm_readout().lm`) for both guards.
- **The threshold is 0 (fixed, not fitted; no sign choice).** A forward English LM gives English text a higher forward score; this is known before the data. With threshold 0, `x` and `rev(x)` cannot both pass unless the value is exactly 0 (an empty or palindrome text). The gate is an `OfferGate`: it changes OFFER to WITHHOLD only and does not change `config_id` (P5-33 design). For both `willett-hw` guards the policy never commits (offer-only), so the commit path does not matter here.
- Gate set in route 2: the shipped `coherence` gate AND `lm_direction >= 0`.

## 3. Objects (fixed)

| Object | Value |
|---|---|
| Built-in guard | `load("willett-hw").guard()`, `tcfg-39aac48688b8bd12`, offer gate `coherence >= 0.004183` |
| LM guard | `load("willett-hw").guard(readout="lm")`, `tcfg-26ae951a20a0cddd`, offer gate `coherence >= 0.002821` |
| Data | Willett handwriting 2021 (T5), CC0 1.0. P14-41 log-probs (`derived/p14-41/lp_{val,test}_real.npz`, read only). S = the 66 non-LTT val positions (`default_rng(0).permutation(106)[:66]`); LTT = the other 40; test = the 80 last-block sentences (the P14-57 test set) |
| Frame times | `p * (1 + arange(T))`, `p` = the guard's `frame_period` (0.01 s): the times `from_array` gives |

Test forms of each test input (rows and times; seeds `default_rng(int.from_bytes(sha256("p5-36|test|i|<kind>")[:8], "little"))`):

| Form | Rows | Times | Fault kind |
|---|---|---|---|
| `real_times` | real | exact | none |
| `real_jitter` | real | exact + uniform(-0.4, 0.4) x `p` per frame (order kept) | none (clock jitter) |
| `rev_out_times` | reversed (P14-57 `rev_out`) | exact, increasing | value fault |
| `rev_events` | reversed | reversed with the rows | transport: whole stream reversed |
| `reordered` | two adjacent frames swapped at seeded `k` | swapped with the rows | transport: one reorder |
| `duplicated` | frame `j` (seeded) sent twice | its time repeated | transport: one repeated frame |

## 4. Rules (per guard; pass iff)

Route 1 (integrity):

| Id | Rule |
|---|---|
| **I1** | `rev_events`, `reordered`, `duplicated`: **80 / 80 each flagged** (withhold with the integrity reason). Also: the synthetic unit tests (`tests/test_trust_integrity.py`, 500 random streams per kind) flag 100 % |
| **I2** | `real_times` and `real_jitter`: **0 / 80 each flagged** |
| **I3** | `real_times` decisions equal the decisions without times (action and reason) **80 / 80**; `config_id` unchanged |
| R1 (report) | `rev_out_times`: flagged count. Expected **0 / 80** (section 1). This is not a pass or a fail; it shows the limit of route 1 |

Route 2 (`lm_direction` offer gate):

| Id | Rule |
|---|---|
| **L0** (val) | loss = real S offers (coherence gate) with `lm_direction < 0`; pass iff loss <= `floor(0.05 m)` (m = real S offers; 3 if m = 66). If L0 fails, L1-L3 still run "for information only" |
| **L1** | `rev_out` (80 test inputs, P14-57 form): offers with both gates **<= 4 / 80** |
| **L2** | real test offers removed by `lm_direction` **<= 4 / 80** (reference: coherence gate only) |
| **L3** | real LTT offers with both gates **>= 36 / 40** (the P14-54 R3 limit) |

Checks (must hold, else the result is not valid): `lm_direction` antisymmetric (1e-9) on S and test, real vs `rev_out`; equivalence: both-gate actions = "coherence action, then withhold if `lm_direction < 0`" on 160 / 160 test inputs.

Nulls: an added offer gate can only remove offers, so the P14-54 / P14-55 null results cannot get worse. We do not re-run them.

**Done-when (gap 181)** reads: the check is in the trust layer (route 1), tested on synthetic reversed streams (I1, unit tests), and the P14-57 `rev_out` test set gives <= 4 / 80 offers with <= 4 / 80 real offers removed. Route 1 cannot meet the last part by design (R1). So the last part is met **only** if route 2 passes L1 and L2 (with L0 for a valid pre-registered claim). If it fails, the gap closes with "numbers say why not" and a new gap.

## 5. Shipping

- Route 1: library code, opt-in (`frame_times=`). No default, manifest or `config_id` change. Documented in the CHANGELOG and the module text.
- Route 2: library feature only. **No packaged gate changes.** The manifest loader reads one offer gate per trust block (P14-57 section 3.4); shipping a second gate needs list support, the model card and the P14-56 offer-control blocks re-checked. If L0-L3 pass for both guards, we propose a new gap to ship it.

## 6. Compute

CPU only (`CUDA_VISIBLE_DEVICES`, `HIP_VISIBLE_DEVICES` = -1), `python -m fidetype.utils.isolation run --class background --threads 2`, keep-awake; log, `DONE` / `FAILED` and per-item JSONL (restart skips finished items) in `C:\Users\zhang\bci-data\derived\p5-36\`. About 1,000 guard decisions per guard; estimate 15-25 min. **Cap: 2 h.** Outputs in git: `results/results.json` (counts and summary values) and `results/run.log`. No log-probs, text or per-item records in git.

## 7. Not in this plan

Shipping either route; other decoders; a frame index field in NTS (a spec change); the WebSocket binding (it has its own `ws_seq` rules).
