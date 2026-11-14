---
title: Control events (continuous control profile)
type: concept
tags: [control, cursor, standard, fep, conformal, trust, safety, p12, neuraltextstream, implant]
sources: [nlb-mc-rtt]
updated: 2026-11-14
---

# Control events (continuous control profile)

Diagram: [17-control-events.drawio](../diagrams/17-control-events.drawio) ([rendered](../diagrams/index.html#s17)).
Spec: [FEP-0005](../../spec/feps/0005-control-events.md). Code: `fidetype.trust.control`, `fidetype.decoders.velocity`. Result: [experiment](../../experiments/2026-11-14-p12-03-control/results.md).
Roadmap: [P12 "Beyond text"](../questions/roadmap-standard.md#p12-beyond-text-intent-and-control-added-2026-11-11), task P12-03. Sibling profile: [intent events](intent-events.md) (FEP-0003).

## What it is
The **control profile** carries continuous decoder output: 1-3 axes of velocity or position, for example a 2D cursor. A **click** is not continuous: it is a FEP-0003 intent with a risk class. The trust layer turns each decoder tick into one actuation command. It decides **how much** to move, not **whether** to commit.

## Events
| Event | From | Contents |
|---|---|---|
| header `control_declaration` | producer | `dims`, `quantity` (velocity / position), `units` (`mm/s`, `px/s`, `norm/s`, ...), `frame` (`screen`: y down; `workspace`: y up), `rate_hz`, `uncertainty` (`none` / `std`), `latency_s`, `click_intent` |
| `control` | decoder (or a human channel) | `tick`, `t`, `values`, `std` per axis, v0.1 timing fields |
| `control_enable` | switch, caregiver, UI, watchdog | `enabled`: engage or a latched stop. Never the decoder |
| `trust_decision` (`profile = "control"`) | trust layer | `state` (act / attenuate / hold / stop), `velocity`, `gain`, `radius`, `v_max`, `ttl_s`, `engagement`, audit fields |

## How the reference layer decides
Each step can only slow the cursor down ([diagram](../diagrams/index.html#s17)):

1. **No-signal gates (HOLD):** low signal quality, stale input, an absent axis, or an output that cannot be told apart from the decoder's output on zero input (the *no-signal reference*).
2. **Conformal shrinkage:** split conformal prediction gives a radius r around the decoded velocity ([conformal risk control](conformal-risk-control.md) covers the related risk-control methods). The output is the point of that ball closest to zero: `v = raw * max(0, 1 - r / |raw|)`. If the ball covers the true velocity, the output is never faster than the true velocity.
3. **Hand-off:** after an engage, decoder authority ramps from 0 to 1 over 1 s. A human channel fills the rest.
4. **Clamps:** speed <= `v_max`; bounded change per tick; never faster than the gated target; a stop is never delayed.
5. **Dead-man:** no motion before an engage; a stop is latched; each command expires after `ttl_s` (3 ticks), so a bridge stops by itself.
6. **Click:** the FEP-0003 intent layer decides it. No click while the control is stopped.

## What the evaluation showed
NLB MC_RTT, one monkey, causal Wiener filter on 130 units ([source](../sources/nlb-mc-rtt.md), [results](../../experiments/2026-11-14-p12-03-control/results.md)):

| Measure | Value |
|---|---|
| Raw decoder R² / Pearson r | 0.478 / 0.707 |
| Conformal coverage at 0.80 / 0.90 / 0.95 | 0.810 / 0.905 / 0.962 (0.90: 5 of 5 rotations in [0.877, 0.923]) |
| Gated motion at level 0.90 | **0 %** of ticks (radius 88.6 mm/s > mean decoded speed 45.8 mm/s) |
| Zero-input drift: raw / gated | 13.3 mm/s / 0 |
| Shuffled, time-reversed spikes: raw R² | -0.133 / -0.317; gated motion 0 |
| Post-hoc: level 0.5 / 0.1 | motion 58 % / 96 %; over-speed 0.17 / 0.49; gated R² 0.04 / 0.33 |

All six pre-declared criteria passed, but the declared configuration never moved.

> **Our take:** a per-tick conformal speed bound is honest and calibrated, but with a decoder near R² 0.5 it leaves almost no motion at useful levels. The next step is a bound on displacement over a short horizon (0.25-0.5 s), a better decoder, and closed-loop data (BrainGate). Until then the level is a deployment dial; the sweep table is the evidence a deployer needs.

> **Our take:** the no-signal failure appears in all three profiles: empty text commits (M2-18), confident zero-input intents (FEP-0003), and now cursor drift (13.3 mm/s on zero input). The decoder's uncertainty model was *more* confident on zero input (sigma 9.5 mm/s on zero input vs a median of 31.4 mm/s on real test input), so it cannot catch it. Explicit no-signal inputs must be part of the standard.

## Related
- [Intent events](intent-events.md): FEP-0003, the click and other discrete actions.
- [Apple BCI HID](../entities/apple-bci-hid.md): Report 3 (pointer) is the main target; P12-05 maps control decisions to it.
- [BrainGate recalibration dataset](../entities/braingate-recalibration-dataset.md): human closed-loop cursor data, the planned second evaluation.
- [Intent and control datasets](../questions/intent-datasets-survey.md): the P12-06 survey that picked MC_RTT and BrainGate.
- [Conformance suite](conformance-suite.md): profile `fep-0005` (42 vectors).
- [WebSocket input](websocket-input.md) and [LSL input](lsl-input.md): transports; a WebSocket gap is a no-signal condition.
