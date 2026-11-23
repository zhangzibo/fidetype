---
title: P14-59 ship the P14-58 C5 threshold lo_new in the willett-hw manifest - results
type: experiment
task: P14-59
updated: 2026-11-22
---

# P14-59: results (2026-11-22)

Pre-registration: [plan.md](plan.md) and [run.py](run.py), commit `dedf60c`, before any number of this work. Numbers: [results/results.json](results/results.json), [results/recheck-lm-gated.json](results/recheck-lm-gated.json), [results/calibration.json](results/calibration.json); log: [results/run.log](results/run.log). Per-item records (actions, features; no text) stay in `C:\Users\zhang\bci-data\derived\p14-59\` only.

## Verdict

**All three re-checks pass. `lo_new` ships** (plan section 6). Gap 182 closed.

| Re-check | Rules | Result |
|---|---|---|
| **RC1** LM guard calibrated again with `lo_new` (decoder_version 3) | G1 not refused, commit controls pass, 0 LTT commits; G2 0 test commits; G3 readout: real gated <= 4 / 80, null emits <= 4 / 80 | **pass**: controls uniform 0 / 300, frame-shuffled 0 / 300, user 0 / 106 commits; 0 LTT commits (feasible: false, as before); 0 commits on all 5 test inputs; real gated **3 / 80**; time-shuffled, zero, uniform emit **0 / 80** each |
| **RC2** `coherence` offer gate (P14-54 tier-1 rule on S) | S rule; R3 LTT offers >= 36 / 40; R4 null emits <= 4 / 80; R5 real offers removed <= 4 / 80; R6 frame-shuffled control | **pass**: threshold **0.003486** (P14-54: 0.002821); S: uniform 0 / 300, frame-shuffled 0 / 300, user 0 / 66 offers; LTT offers 40 / 40; time-shuffled, zero, uniform 0 / 80; real removed 0 / 80; frame-shuffled 0 / 80 vs real 77 / 80 (p 1.0e-42) |
| **RC3** P5-31 offer-control block (`recheck_offer_control`) | V1 all controls pass; V2 commits match the sheet, 0 LTT commits | **pass**: uniform 0 / 300, frame-shuffled 0 / 300, time-shuffled 0 / 106 offers vs real 40 / 40; commits match the sheet |

New LM guard: `tcfg-f498c0637536daec` (was `tcfg-26ae951a20a0cddd`), release file `willett-hw.lm3.guard.json` (SHA-256 `9d87fc60...`, 8,613 bytes; local only, not in git).

## Test counts (80 sentences per input, new guard with the new offer gate)

| Input | Offers | Commits | Removed by the offer gate | Readout gated by C5 | Readout emits text |
|---|---|---|---|---|---|
| real | 77 | 0 | 0 | 3 | 77 |
| time-shuffled | 0 | 0 | 0 | 80 | 0 |
| zero | 0 | 0 | 0 | 80 | 0 |
| frame-shuffled | 0 | 0 | 77 | 2 | 78 |
| uniform | 0 | 0 | 0 | 80 | 0 |

Descriptive: gated readout test CER 0.1769 (empty text when gated; P14-49 with the old `lo`: 0.1746); 9 / 80 exact. On val S, 65 / 66 real inputs pass C5 (P14-58: 1 / 66 gated). Ungated S selection nulls: frame-shuffled 291 / 300 offers, uniform 0 / 300, time-shuffled 0 / 66.

> **Our take:**
> - The cost of `lo_new` is as P14-58 said: 2 more real test sentences get no text (3 / 80 vs 1 / 80). The gain is on time-shuffled input: 0 / 80 emits here and 0 / 800 in P14-58.
> - The offer-gate threshold went up (0.002821 -> 0.003486) because one real S sentence is now gated by C5, so it is no longer an offer, and the smallest offer value moved. No real test offer is lost to the offer gate.
> - The guard stays offer-only (40 LTT items < 45). The change does not create commits.

## What shipped

`src/fidetype/pretrained/manifests/willett-hw.json`: `readouts.lm.gate.lo` 0.5659314232741417; the guard file entry `willett-hw.lm3.guard.json`; `readouts.lm.trust` (`config_id`, offer gate 0.003486, offer-control block from RC3; the before-gate counts of the previous guard are kept with a note); metrics and texts. Tests: `tests/test_pretrained_offer_control.py`, `tests/test_pretrained_lmreadout.py`. Docs: [pretrained-decoders.md](../../docs/pretrained-decoders.md). CHANGELOG entry. The default (greedy) readout and its guard `tcfg-39aac48688b8bd12` do not change.

## Run record

CPU only (the GPU ran another job), isolation class `background`, 2 threads. 22:16:28-22:25:00 (cal 145 s, select 122 s, recheck 153 s, test 91 s). Peak working set 717 MB. No deviation from the plan.

## Limits

- One participant (T5), one decoder checkpoint, 80 test sentences; the test inputs were already seen by P14-49, P14-54, P14-57 and P14-58.
- The offer-gate threshold is the smallest real S offer value (66 inputs), as in P14-54.
- The new guard was not re-checked without the offer gate.

## Licence

Willett data CC0 1.0. LM text CC BY 2.0 FR (Tatoeba contributors); the LM file stays local. Our code Apache-2.0. This commit holds aggregates only: no weights, LM file, log-probs or text.
