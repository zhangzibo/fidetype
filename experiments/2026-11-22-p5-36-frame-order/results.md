---
title: P5-36 frame-order integrity check in the trust layer - results
type: experiment
task: P5-36
updated: 2026-11-22
---

# P5-36: results (2026-11-22)

Pre-registration: [plan.md](plan.md) with [run.py](run.py), the library code and the synthetic tests, commit `a705a75` (09:41), before any real-data number. Numbers: [results/results.json](results/results.json); log: [results/run.log](results/run.log). Per-item records (actions, codes, feature values; no text) stay in `C:\Users\zhang\bci-data\derived\p5-36\` only.

## Verdict

| Route | Verdict | Key numbers (test, 80 sentences, each guard) |
|---|---|---|
| **Route 1**: stream-integrity check (`frame_times=`) | **Pass (I1, I2, I3).** It is in the trust layer, opt-in, with no `config_id` change | transport faults flagged **240 / 240** (reversed, reordered, duplicated: 80 / 80 each); real streams flagged **0 / 160** (exact and jittered times); decisions on valid times equal the decisions without times 80 / 80 |
| Route 1 on `rev_out` as P14-57 built it (R1) | **Cannot catch it, as the plan said** | flagged **0 / 80**: the rows are reversed but the times stay in order |
| **Route 2**: `lm_direction >= 0` offer gate | **Negative result (numbers say why not).** L0 fails on val (10 / 66 > 3), so L1-L3 are "for information only". L1 and L2 fail; L3 passes | `rev_out` offers 77 -> **10** (built-in) and 78 -> **10** (LM), limit 4; real offers removed **10 / 80** each, limit 4; LTT real offers 40 / 40 |

So the gap 181 done-when is met for its first two parts (the check is in the trust layer; it is tested on synthetic reversed streams). Its third part (the P14-57 `rev_out` test set at <= 4 / 80 offers with <= 4 / 80 real offers removed) is **not met**: route 1 cannot see a value fault by design, and route 2 has the same cost problem as P14-57 (10 / 80 vs 11 / 80 and 17 / 80). No packaged gate, guard file or manifest changed. `config_id` values unchanged: `tcfg-39aac48688b8bd12`, `tcfg-26ae951a20a0cddd`.

## Route 1: integrity check

| Rule | Form | Built-in | LM |
|---|---|---|---|
| **I1** pass | `rev_events` (rows and times reversed) | 80 / 80 flagged, code `frame_order_reversed` | 80 / 80, same |
| | `reordered` (2 adjacent frames swapped) | 80 / 80, `frame_order` | 80 / 80, same |
| | `duplicated` (1 frame sent twice) | 80 / 80, `frame_duplicate` | 80 / 80, same |
| **I2** pass | `real_times` (exact times) | 0 / 80 flagged | 0 / 80 |
| | `real_jitter` (+-0.4 frame period) | 0 / 80 flagged | 0 / 80 |
| **I3** pass | `real_times` vs no times: same action and reason | 80 / 80 | 80 / 80 |
| R1 (report) | `rev_out_times` (P14-57 `rev_out`, times in order) | **0 / 80 flagged**; 10 offers with both gates | 0 / 80; 10 offers |

Synthetic unit tests (`tests/test_trust_integrity.py`, 500 random streams per kind): reversed, reordered and duplicated 100 % flagged; exact and jittered times 0 % flagged. A flagged stream gives WITHHOLD for every policy action, also a COMMIT (tested on the synthetic guard).

> **Our take:**
> - Route 1 is the right fix for the fault class it covers: a fault that moves frames with their times. It costs nothing on valid streams. Before this item, the guard could not see the producer's times at all (`decide` took a matrix), and the streaming layer raised an exception instead of a recorded WITHHOLD.
> - `rev_out` as P14-57 built it is a different fault: the frame values are reversed and the times are new. No time or index check can see it. NTS has no frame index field, and an index made by the same faulty software would be in order too.

## Route 2: `lm_direction` offer gate (threshold 0, fixed)

| Rule | Built-in | LM |
|---|---|---|
| **L0** (val S) loss <= 3 / 66 | **fail**: 10 / 66 | **fail**: 10 / 66 |
| **L1** `rev_out` offers <= 4 / 80 | **fail**: 10 / 80 (coherence only: 77) | **fail**: 10 / 80 (coherence only: 78) |
| **L2** real offers removed <= 4 / 80 | **fail**: 10 / 80 (77 -> 67) | **fail**: 10 / 80 (77 -> 67) |
| **L3** LTT real offers >= 36 / 40 | pass: 40 / 40 | pass: 40 / 40 |

Checks (all hold): `lm_direction` is antisymmetric (1e-9) on 66 / 66 val and 80 / 80 test pairs; `coherence` of `rev_out` equals real on 66 / 66; both-gate actions equal "coherence action, then the direction gate" on 160 / 160 per guard. No real value was exactly 0.

Real test values of `lm_direction` on the offers (min / 5 % / median / 95 % / max, nats per character): -1.158 / -0.273 / 0.611 / 1.497 / 2.093. Val: -2.070 / -0.282 / 0.666 / 1.772 / 2.889.

> **Our take:**
> - The two guards give the same numbers because the feature reads the greedy text of the frames. The frame scaler of the LM guard does not change the argmax, so the text and the value are the same (80 / 80 equal).
> - About 1 in 7 to 1 in 8 real sentences (10 / 66 val, 10 / 80 test) has a greedy text that the LM scores higher **backward** than forward. The greedy text has a high error rate (test CER 0.305 in the manifest), so for these sentences the text is too noisy for a direction signal. It is better than the P14-57 frame statistic for the LM guard (10 vs 17 real offers removed), and close for the built-in guard (10 vs 11). It is still far from the limit of 4.
> - With a fixed threshold 0, `rev_out` offers and real offers removed are the same set of sentences (10 = 10 here). A lower threshold trades one for the other; it cannot make both <= 4 at this per-sentence power.
> - A stronger direction score would decode both directions with the LM beam (forward and reversed frames) and compare the LM-readout scores, so the LM fixes the noisy characters first. It is not antisymmetric by construction, so it needs a fitted threshold. We propose this as a new gap. A second option is to accept route 1 as the fix and record `rev_out` (a value fault after the decoder) as out of scope for the trust layer, with a software test in the producer instead.

## Deviations from the plan

None. The run used the pre-registered inputs, seeds and rules.

## Run record

CPU only, isolation class `background`, 2 threads, keep-awake. 09:41:47-09:58:02 (975 s): val 160 s, test built-in 449 s, test LM 365 s. Peak working set 438 MB. Inside the 2 h cap.

## Limits

- One participant (T5), one decoder checkpoint, 80 test sentences, one LM.
- The real streams carry the times that `from_array` makes (plus jitter in `real_jitter`). The Willett data has no per-frame producer times of a live device. So I2 shows that the check accepts regular and jittered clocks, not a real device clock.
- The transport forms are one fault each per stream (one swap, one repeat, or a full reversal). A fault that moves frames and also rewrites their times in order is a value fault for this check (as R1).
