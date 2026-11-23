---
title: P14-59 ship the P14-58 C5 threshold lo_new in the willett-hw manifest - pre-registration
type: experiment
task: P14-59
updated: 2026-11-22
---

# P14-59: ship `lo_new` in the `willett-hw` LM readout (pre-registration, 2026-11-22)

Roadmap: [P14-59](../../wiki/questions/roadmap-standard.md#p14-59-ship-the-p14-58-c5-threshold-in-the-willett-hw-manifest) (gap 182). User decision 2026-11-22 ("all recommended"): ship `lo_new`, but only after the three re-checks of the done-when, and only if all three pass.

This plan, [run.py](run.py) and the rules below are committed **before** any number of this work is computed. Known at this time: the P14-58 result (`lo_new` = 0.5659314232741417; test time-shuffled emits 0 / 800; real test gated 3 / 80; real val S gated 1 / 66; [results](../2026-11-21-p14-57-direction-aware-offer/results.md)), the P14-49, P14-54 and P14-55 results.

## 1. What changes

Only the lower bound `lo` of the LM readout gate C5 (`readouts.lm.gate`): shipped -1.1697116125105564 -> `lo_new` 0.5659314232741417 (`ScoreGate.with_lo`, coefficients, `k_min`, `r_max` unchanged). The default (greedy) readout and its guard `tcfg-39aac48688b8bd12` do not use C5 and do not change.

The LM guard calls the gated readout as its decoder. A different gate is a different decoder, so the LM guard is calibrated again (re-check 1), its `coherence` offer gate is fitted again by the P14-54 rule (re-check 2), and its P5-31 offer-control block is computed again (re-check 3).

## 2. Data (as P14-49 / P14-54; read only)

- Log-probs: `derived/p14-41/lp_{val,test}_{real,timeshuf,zero}.npz`; truths: `derived/p14-41/items.json`.
- Frame-shuffled and uniform test inputs: the P14-41 generators `item_rng("test", i, kind)` (seed 0), as P14-54.
- Selection set S and selection nulls (seed 5454): as P14-54 section 4.
- Model: packaged `willett-hw` (weights and LM file of the manifest, SHA-256 checked by the loader).

## 3. Re-check 1: the LM guard with `lo_new`

`fidetype.trust.calibrate` with the P14-49 settings: the 106 val sentences, the 106 time-shuffled val inputs as `null_inputs`, alpha 0.05, delta 0.1, seed 0, `input_scale="log_probs"`, `decode_fn` = `lm_readout(gate=C5.with_lo(lo_new)).decode_fn()`, `decoder_name="fidetype-willett-hw-lm-f"`, `decoder_version="3"` (P14-49: "2"), `name="p14-59-willett-hw-lm"`.

| Rule | Pass if |
|---|---|
| G1 | calibrate does not refuse; the three commit controls (uniform, frame-shuffled, user) pass; 0 LTT commits (the guard stays offer-only, as shipped) |
| G2 | 0 commits on every test input (real, time-shuffled, zero, frame-shuffled, uniform; 80 each) |
| G3 | readout level (gate only): real test gated <= 4 / 80; readout emits text on time-shuffled, zero and uniform test input <= 4 / 80 each |

## 4. Re-check 2: the `coherence` offer gate

Threshold `tau` = the P14-54 tier-1 rule on the new guard: the smallest `coherence` over the real S offers. Only the feature `coherence` is allowed (the shipped feature); no fallback to other features or tiers.

| Rule | Pass if |
|---|---|
| S | the P5-31 rule on S passes with `coherence >= tau` (selection nulls: 300 uniform, 300 frame-shuffled, 66 user) |
| R3 | real LTT offers with the gate >= 36 / 40 (from re-check 3) |
| R4 | gated guard emits on time-shuffled, zero and uniform test input <= 4 / 80 each |
| R5 | real test offers removed by the offer gate <= 4 / 80 |
| R6 | test frame-shuffled control passes the P5-31 rule against the real test offers |

## 5. Re-check 3: the P14-56 offer-control block

`recheck_offer_control(new guard + coherence gate, lp_val_real, null_inputs=lp_val_timeshuf)`.

| Rule | Pass if |
|---|---|
| V1 | the P5-31 rule passes for all three controls |
| V2 | `commits_match_sheet` is true and the LTT commits are 0 |

## 6. Decision rule (fixed now)

Ship only if re-checks 1, 2 and 3 all pass. Then: copy the new guard file into the local model folder as `willett-hw.lm3.guard.json`; in the manifest set `readouts.lm.gate.lo` = `lo_new`, the new guard file (name, SHA-256, size), the new `config_id`, the new offer-gate threshold, the offer-control block from re-check 3 and the new test counts; update the model card text, the tests and docs/pretrained-decoders.md. If any re-check fails: ship nothing, keep every manifest value, and record which rule failed and why.

Descriptive only (no rule): the gated readout test CER (empty text when gated), real test offers, top-1 exact of the offers, time per stage.

## 7. Run

CPU only (the GPU is in use by another job), isolation class `background`, 2 threads. Stages `cal`, `select`, `eval`, `score`; each writes a checkpoint in `C:\Users\zhang\bci-data\derived\p14-59\` and skips finished work. Per-item records (actions, features; no text) stay in that folder. `results/` holds counts only.

## Licence

Willett data CC0 1.0. LM text CC BY 2.0 FR (Tatoeba contributors); the LM file stays local. Our code Apache-2.0. Aggregates only: no weights, LM file, log-probs or text in git.
