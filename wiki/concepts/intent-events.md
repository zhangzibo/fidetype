---
title: Intent events (discrete intent and control)
type: concept
tags: [intent, control, standard, fep, risk-control, trust, safety, p12, neuraltextstream, emg]
sources: [toronto-semg-typing, conformal-risk-control]
updated: 2026-11-13
---

# Intent events (discrete intent and control)

Diagram: [15-intent-events.drawio](../diagrams/15-intent-events.drawio) ([rendered](../diagrams/index.html#s15)).
Spec: [FEP-0003](../../spec/feps/0003-intent-events.md). Code: `fidetype.trust.intent`. Result: [experiment](../../experiments/2026-11-13-p12-intent-events/results.md).
Roadmap: [P12 "Beyond text"](../questions/roadmap-standard.md#p12-beyond-text-intent-and-control-added-2026-11-11), tasks P12-01 and P12-02.

## What it is
An **intent** is one discrete action that a person means: select, confirm, cancel, undo, a menu choice among N options, a mode switch, or a device command such as "call caregiver". FEP-0003 extends NeuralTextStream (NTS) and the trust layer from text to intents. Text stays first and does not change.

## Core and profiles
| Part | Contents |
|---|---|
| Core | header, frames, time, `signal_quality`, `segment_end`, `end`, `meta`, provenance |
| Text profile | `hypothesis`, text `trust_decision` (FEP-0001). Unchanged |
| Intent profile | header `intent_declaration`, `intent`, `intent_feedback`, v0.1 `decision`, `trust_decision` with `profile = "intent"` |
| Control profile | v0.1 `pointer`; actuation policy in a later FEP (P12-03) |

## Risk classes
| Class | Example | Default limit per decision unit | Extra rule |
|---|---|---|---|
| `safe` | stop, next, cancel | 0.10 | |
| `undoable` | select, key, mode switch | 0.05 | `undo` reverses it |
| `irreversible` | send, call caregiver, delete | 0.01 | armed only; needs a confirmation |

The producer declares the class. A deployment can only make it stricter.

## How the trust layer decides
1. Calibrate the candidate scores with the frozen temperature.
2. Gates (each only removes COMMITs): never COMMIT a `null` (rest) intent; no COMMIT without probability scores; no COMMIT at low signal quality; COMMIT needs p >= 0.5.
3. One threshold per risk class, fitted with LTT or CRC (`fidetype.trust.risk_control`, unchanged). The loss of class r is "a wrong COMMIT of a class-r intent", which is monotone in the threshold, so the existing machinery applies as is ([conformal risk control](conformal-risk-control.md)).
4. Safe or undoable top intent above its threshold: COMMIT. Irreversible: **arm** (OFFER with `confirm_required`). It executes only after the next unit is `confirm` (irreversible threshold) or a second channel sends `intent_feedback` `confirmed`.
5. Otherwise OFFER a small top-k set (the user picks) or ABSTAIN.

Intent decisions never carry `shown`. So an older text bridge can never type an intent id as text.

## What the evaluation showed
Public sEMG data (Toronto sEMG typing, CC BY 4.0) recast as a 27-way key choice, plus a synthetic simulator ([results](../../experiments/2026-11-13-p12-intent-events/results.md)):

- On clean data every class stays at or below its alpha (three decoders, LTT and CRC).
- Uniform input never commits.
- **The decoder's zero-input output commits on 37 % of presses** when the configuration was fitted only on clean data. This is the intent form of the M2-18 empty-commit failure ([streaming trust layer](streaming-trust-layer.md)). A **no-signal reference** at fit time (decoder output on zero input; no labels) removes it (0 %), at a cost of clean act rate 0.082 -> 0.057.
- In the simulator a signal-quality gate takes commits on no-signal trials from 0.405 to 0.
- Pair-shuffled outputs break exchangeability and exceed alpha, as the theory says.

> **Our take:** risk control protects against wrong commits on data like the calibration data. It does not protect against an input type the calibration never saw. For actions, "no signal" must be a known input type: a `null` intent trained on rest data, a quality channel, or a no-signal reference. We made the controls a required report in FEP-0003 and the reference a SHOULD (open question 4: a MUST for irreversible intents?).

> **Our take:** with about 260 calibration units, LTT cannot arm an irreversible intent at alpha 0.01. Irreversible actions will mostly go through OFFER + explicit selection until decoders get better or sessions give more calibration units. That is a safe default, not a failure.

## Related
- [Apple BCI HID](../entities/apple-bci-hid.md): target interface for intents and pointer (P12-05).
- [Toronto sEMG typing](../sources/toronto-semg-typing.md): the public data of the evaluation.
- [Conformance suite](conformance-suite.md): profile `fep-0003` (44 vectors).
- [LSL input](lsl-input.md): intents travel on the events stream with no binding change.
