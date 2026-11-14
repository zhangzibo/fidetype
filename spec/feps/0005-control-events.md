# FEP-0005: Continuous-control events (the control profile)

| | |
|---|---|
| **FEP** | 0005 |
| **Title** | The control output profile: continuous 2D/3D velocity or position with uncertainty, units and frames, engage / stop, and the control trust decision (gain, hold, stop) with safety rules |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft |
| **Type** | Spec change (additive, Development) |
| **Affects** | `neuraltextstream-v0.1.md` sections 3.7 (`pointer`), 3.8 (timing), 3.9 (signal quality), 6.5; the control profile named in FEP-0003 section 1; uses FEP-0001 (`trust_decision`), FEP-0003 (click as an intent), FEP-0002 / FEP-0004 (transport) |
| **Created** | 2026-11-14 |
| **Discussion** | P12-03 (roadmap phase P12 "Beyond text: intent and control"); `src/fidetype/trust/control.py`, `wiki/concepts/control-events.md` |

## Summary
FEP-0003 split NTS into a core and output profiles and left the *control* profile for later. This FEP defines it:

1. A header key `control_declaration`: axes, quantity (velocity or position), **units**, **coordinate frame**, update rate, uncertainty form, decoder latency, and the FEP-0003 intent used as **click**.
2. A `control` input event per decoder tick: values, an optional per-axis `std`, a strictly increasing `tick`, and the v0.1 timing fields for latency.
3. A `control_enable` event: engage and safe-stop through a channel other than the decoder.
4. The control form of `trust_decision`: one actuation command per tick, with `state` (`act`, `attenuate`, `hold`, `stop`), the output `velocity`, the `gain`, the conformal `radius`, `v_max`, a time-to-live `ttl_s`, and audit fields.
5. Safety rules: no motion on no-signal input, a bounded velocity, a dead-man stop, a smooth hand-off from human to decoder, no discrete action while stopped, an audit trail.

All parts are additive. No field of the text or intent profile changes. A v0.1 consumer ignores the new event types and the header key. The opt-in conformance profile `fep-0005` tests the rules.

## Motivation
- Cursor control is the main use of implanted BCIs today (BrainGate, Neuralink, Synchron, Apple BCI HID pointer). v0.1 has only a `pointer` event: no units, no frame, no uncertainty, no rate, no engage, no stop.
- A wrong *continuous* output is a motion. It cannot be "not committed" later as a text can. The trust layer must decide **how much** to move on each tick, and it must stop at once when the signal goes away.
- M2-18 and FEP-0003 showed that trust layers act on no-signal input. The control form of this failure is **drift**: our linear decoder outputs 13.3 mm/s on all-zero input (section "Evaluation"). A cursor that drifts while the amplifier is off is a safety problem.
- Apple BCI HID and OS pointer APIs take one velocity or position per report. A bridge needs one clear command per tick, with a time-to-live, so a lost connection cannot leave the cursor moving.

## Terms
- **Tick**: one decoder update (one `control` event). Ticks are numbered per stream (`tick`, strictly increasing).
- **Engage / stop**: `control_enable` with `enabled = true` / `false`. A stop is *latched*: no motion until the next engage.
- **Authority**: the share of the decoder in the commanded velocity, 0 to 1. It ramps up after an engage (hand-off).
- **No-signal reference**: the decoder output on all-zero input (no labels needed).
- **Bridge**: a program that moves something (an OS cursor, an HID exporter, a wheelchair driver).

## Proposal

### 1. Place in the profile model
| Profile | Input events | Decision |
|---|---|---|
| Control (this FEP) | header `control_declaration`; `control`; `control_enable`; v0.1 `pointer` (3.7); `signal_quality` (3.9, core) | `trust_decision` with `profile = "control"` |

Rules:
1. FEP-0003 section 1 rules 1-2 apply. A stream MAY carry control, intent and text events.
2. **Click and other discrete events are intents.** A click, a drag start or a mode switch is a FEP-0003 `intent` with its risk class. The control declaration names the click intent (`click_intent`). The FEP-0003 rules (thresholds per risk class, confirmation of irreversible intents, no null COMMIT) apply unchanged.
3. A v0.1 `pointer` on a stream with a `control_declaration` is an **unscored** control input: `relative` values are a displacement per event in the position unit of the declared velocity unit (velocity = values x `rate_hz`); `absolute` values are a normalised screen position. The pointer event does not change.

### 2. Control declaration (header key `control_declaration`, Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `dims` | integer 1-3 | Yes | Number of axes |
| `quantity` | `velocity` or `position` | Yes | What `values` mean |
| `units` | string | Yes | Velocity: `norm/s`, `px/s`, `mm/s`, `m/s`, `deg/s`. Position: `norm`, `px`, `mm`, `m`, `deg`. `norm` = fraction of the screen width (x) and height (y) |
| `frame` | `screen` or `workspace` | Yes | `screen`: x right, y down, origin top-left (OS and HID convention). `workspace`: x right, y up, z towards the user (right-handed); the producer documents the origin |
| `rate_hz` | number > 0 | Yes | Nominal update rate |
| `axes` | list of `dims` strings | No | Axis names (default `x`, `y`, `z`) |
| `uncertainty` | `none` or `std` | No | `std`: every decoder `control` event carries a per-axis standard deviation (default `none`) |
| `max_speed` | number > 0 | No | The producer's hint of the largest plausible speed (declared units). The consumer sets its own bound (section 6 rule 3) |
| `latency_s` | number >= 0 | No | Nominal decoder latency (end of the signal window to output) |
| `window_s` | number >= 0 | No | Length of the signal history that the decoder uses |
| `click_intent` | string | No | The FEP-0003 intent id that means "click" |

Rules:
1. `units` MUST fit `quantity` (table). `norm` position is defined only in the `screen` frame.
2. `axes`, if present, MUST have `dims` unique names.
3. Unknown keys are allowed and ignored (spec 5.1).
4. `click_intent` MUST be declared in the `intent_declaration` (FEP-0003) of the same header, and its role MUST NOT be `null`.
5. A control-only stream has no frames. Its `vocab` is a placeholder (reference: `["control"]`, `vocab_type = "command"`, `blank_id = null`). With an `intent_declaration`, FEP-0003 section 2 rule 5 applies.

### 3. `control` event (decoder or human channel, Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"control"` | Yes | |
| `t` | float | Yes | Signal time of the output (end of the signal window), seconds |
| `tick` | integer >= 0 | Yes | Tick number, strictly increasing per stream (decoder events) |
| `values` | list of `dims` numbers | Yes | One value per axis, declared units and frame. An absent axis MAY be `null` |
| `absent` | list of `dims` booleans | No | As in 3.7: `true` = no value for that axis |
| `std` | list of `dims` numbers > 0 | If declared | Per-axis standard deviation of the output, declared units (section 2 `uncertainty`) |
| `source` | `decoder` (default) or `human` | No | `human`: an assistive or manual channel (joystick, eye tracker, caregiver) used for the hand-off |
| `id` | string | No | |
| `t_signal_start`, `t_signal_end`, `t_decoded`, `t_emitted` | float | No | v0.1 3.8 timing; end-to-end latency = `t_emitted - t_signal_end` |

Rules:
1. A `control` event MUST come after a header with a `control_declaration`.
2. For decoder events, `tick` and `t` MUST increase strictly.
3. With `uncertainty = std`, every decoder event MUST carry `std`. With `uncertainty = none`, no event carries `std`. *Why:* a consumer must know before the first tick if it can calibrate.
4. A v0.1 `pointer` on such a stream MUST have `dims` equal to the declared `dims`.
5. `std` is decoder output, not truth. A trust layer calibrates it (section 6 rule 6). Signal quality stays a separate input (3.9).

### 4. `control_enable` event (other channel, Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"control_enable"` | Yes | |
| `enabled` | boolean | Yes | `true`: engage; `false`: safe-stop (latched) |
| `t` | float | No | Time, stream clock |
| `source` | `switch`, `caregiver`, `ui`, `voice`, `eye-tracker`, `watchdog`, `other` | No | The channel. Never a person's name |
| `reason` | string | No | A short code or text, no personal content |

The decoder MUST NOT send `control_enable`. It is input from a channel the user or a caregiver controls (a switch, a button, a voice command decided by another system) or from a watchdog.

### 5. Control `trust_decision` (trust layer output, Development)
A control decision is a FEP-0001 `trust_decision` with these fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `profile` | `"control"` | Yes | |
| `tick` | integer >= 0 | Yes | The input tick (in place of `utterance` / `unit`) |
| `is_final` | `true` | Yes | Every control decision is final |
| `action` | `COMMIT` or `ABSTAIN` | Yes | `COMMIT` = move (`state` `act` or `attenuate`); `ABSTAIN` = no motion (`hold` or `stop`) |
| `state` | `act`, `attenuate`, `hold`, `stop` | Yes | `act`: full decoder output; `attenuate`: 0 < gain < 1; `hold`: zero velocity, resumes by itself; `stop`: zero velocity, latched until an engage |
| `velocity` | list of numbers | Yes | The commanded velocity, declared units and frame |
| `gain` | number in [0, 1] | Yes | `||velocity|| / ||raw||` (0 on hold / stop) |
| `units` | string | Yes | Units of `velocity` |
| `v_max` | number > 0 | Yes | The speed bound in force |
| `ttl_s` | number > 0 | Yes | Time-to-live: the command is void after `t + ttl_s` (bridge time: after receipt + `ttl_s`) |
| `engagement` | integer >= 0 | Yes | Engage counter; it increases at each engage |
| `raw` | list of numbers | No | The decoder output of this tick |
| `radius`, `level` | number >= 0, number in (0, 1) | No | Conformal radius of the velocity interval at `level` |
| `authority` | number in [0, 1] | No | Decoder authority (hand-off) |
| `reasons` | list of codes | No | `ok`, `shrunk`, `uncertain`, `no_signal`, `no_signal_reference`, `unscored`, `disengaged`, `not_engaged`, `stale_input`, `absent`, `handoff`, `clamp_speed`, `clamp_accel` |
| `t`, `p_top1` (null), `score_semantics`, `session`, `seq`, `reason`, `config_id`, `input`, `latency_s` | as FEP-0001 | | `score_semantics = "calibrated_prob"` when a calibrated radius was used, else `none` |

Rules:
1. A control decision MUST carry `profile = "control"` and `tick`. It MUST NOT carry `shown`, `utterance` or `unit`. (A FEP-0001 text bridge then never types it.)
2. `is_final` MUST be `true`. There is no provisional motion.
3. `state` MUST fit `action` (table).
4. `v_max` and `ttl_s` MUST be present.
5. Within one session, `seq` increases strictly over all profiles (FEP-0003 section 7 rule 2). Ticks do not go back. **One input tick moves at most once**: a second COMMIT for the same tick is not allowed. A HOLD MAY repeat the last tick (dead-man, section 6 rule 4).
6. A bridge acts on every control decision: it applies `velocity` until the next decision or until `ttl_s` runs out, whichever comes first. After that it MUST command zero velocity.

### 6. Safety rules
1. **No motion on hold or stop.** A decision with `action = ABSTAIN` MUST have zero `velocity` and `gain = 0`. A COMMIT MUST have a non-zero velocity.
2. **No motion on no-signal input.** A trust layer MUST NOT move when it knows the input carries no signal: (a) the latest `signal_quality` index is below the configured minimum; (b) the input is stale (no decoder tick for `stale` periods); (c) an axis is absent; (d) the output cannot be told apart from the **no-signal reference**: `||raw - v_ns|| <= radius`. The decision then is a HOLD with the reason code. A COMMIT MUST NOT carry `no_signal`, `no_signal_reference`, `stale_input`, `disengaged`, `not_engaged` or `absent`. A producer SHOULD send `signal_quality`. An evaluation MUST report motion on zero-input and shuffled controls next to the clean numbers.
3. **Bounded velocity.** `||velocity|| <= v_max` on every decision. The change per tick SHOULD be bounded (`a_max * dt`). A bound MUST NOT delay a stop: a zero target gives zero velocity at once, and the bounded output is never faster than the gated target.
4. **Dead-man.** Motion needs an engage (`control_enable`, `enabled = true`) unless the deployment documents another enable channel. `enabled = false` is a latched stop. Each decision has a `ttl_s` of a few update periods (reference: 3). A layer SHOULD emit a HOLD (`stale_input`) when the decoder stops; a bridge MUST stop by itself when decisions stop (rule 5.6).
5. **Re-engage and hand-off.** After a `stop`, a COMMIT needs a new engagement (a higher `engagement`). After an engage, the decoder authority SHOULD ramp continuously from 0 to 1 (reference: linear over 1 s). During the ramp the rest of the command MAY come from a human channel (`source = "human"`); without one, the ramp starts from rest.
6. **Calibrated gain (reference policy).** With `uncertainty = std`, a layer SHOULD calibrate the radius by split conformal prediction on labelled ticks of the same user and session: score `||v - v_hat|| / max(std)`, radius `r = q * max(std)` at `level`. The reference gain is **conformal shrinkage**: `velocity = raw * max(0, 1 - r / ||raw||)`, the point of the interval ball closest to zero. If the ball covers the true velocity, the output is never faster than the true velocity and its direction error is at most `asin(r / ||raw||)`. All later gates only reduce the speed (at full authority, `||velocity|| <= ||raw||`). Without `std`, a layer MUST NOT move faster than a configured `unscored_gain x raw` (reference default 0: no motion without uncertainty). *Caveat (Evaluation):* at `level = 0.9` this policy gave no motion on public monkey data. The level is a deployment choice, not a fixed number of this FEP.
7. **No discrete action while stopped.** A trust layer MUST NOT COMMIT an intent (FEP-0003) while the control is not engaged. (A click must not happen while the user has stopped the cursor.)
8. **Gates keep the bound.** Rules 2-5 and 7 only remove motion or actions. A coverage-based speed bound (rule 6) still holds with them.
9. **Audit trail.** Every control decision SHOULD carry `config_id` (content id of the frozen configuration, `ccfg-...`), `input` (`kind`, `tick`, SHA-256 of the input event), `raw`, `reasons` and `latency_s`. A layer MAY write decisions to the provenance ledger (4.3). A log MAY be thinned for storage only if it keeps every state change and every decision with a non-`ok` reason.

### 7. Transport, rates and HID
1. **LSL (FEP-0002).** `control` and `control_enable` are marker JSON on the events stream; control decisions go to a decisions stream. At 50 Hz and more, a producer MAY instead send `values` (and `std`) as a float channel stream; that binding is an open question (question 3).
2. **WebSocket (FEP-0004).** No change: control events are NTS events with `ws_seq`. A gap (FEP-0004 section 6 rule 3) is a no-signal condition: the layer SHOULD HOLD until the next tick after the gap.
3. **Separate decision stream.** Control decisions (one per tick) SHOULD go to their own decisions stream or log. A `fep-0003`-only consumer rejects the unknown profile value `control`.
4. **Apple BCI HID (6.5).** A bridge maps a final control COMMIT to the pointer report (Report 3) and a HOLD / STOP to a zero report. It MUST apply `ttl_s`. A click intent COMMIT maps to a button event (FEP-0003 section 7 rule 4).

## Examples
Input (a 2D velocity stream with a click intent):
```json
{"type": "header", "spec_version": "0.1", "vocab": ["intent.rest", "intent.click"], "vocab_type": "command", "blank_id": null, "source": "acme-utah", "intent_declaration": {"intents": [{"id": "intent.rest", "risk": "safe", "role": "null"}, {"id": "intent.click", "risk": "undoable"}]}, "control_declaration": {"dims": 2, "quantity": "velocity", "units": "mm/s", "frame": "workspace", "rate_hz": 50, "uncertainty": "std", "window_s": 0.2, "click_intent": "intent.click"}}
{"type": "control_enable", "t": 0.0, "enabled": true, "source": "switch"}
{"type": "signal_quality", "t": 1.98, "value": 0.94, "unit": "index"}
{"type": "control", "t": 2.0, "tick": 99, "values": [180.0, -42.0], "std": [21.0, 21.0], "t_signal_end": 2.0, "t_emitted": 2.004}
```
Output:
```json
{"type": "trust_decision", "profile": "control", "session": "s1", "seq": 99, "tick": 99, "t": 2.0, "is_final": true, "action": "COMMIT", "state": "attenuate", "velocity": [87.6, -20.4], "raw": [180.0, -42.0], "gain": 0.4865, "units": "mm/s", "radius": 94.9, "level": 0.8, "authority": 1.0, "engagement": 1, "v_max": 352.0, "ttl_s": 0.06, "reasons": ["shrunk"], "reason": "shrunk", "p_top1": null, "score_semantics": "calibrated_prob", "config_id": "ccfg-0123456789abcdef", "input": {"kind": "control", "tick": 99, "sha256": "..."}}
```

## Compatibility
- Producers: nothing changes for text or intent producers. All parts are optional.
- Consumers: a v0.1 consumer ignores the new event types and the header key. A FEP-0001 consumer of a decision log sees control decisions with `COMMIT` / `ABSTAIN` and no `shown`: it types nothing. A `fep-0003` consumer rejects `profile = "control"` (it knows only `text` and `intent`); section 7 rule 3 keeps control decisions in their own stream. The v0.1, `fep-0001` to `fep-0004` vectors do not change.
- Stability: all parts start at Development.

## Conformance
Profile `fep-0005` (opt-in, `src/fidetype/conformance/profiles/fep0005.py`). Golden vectors: [`spec/conformance/fep-0005/`](../conformance/fep-0005/) (`manifest.json`; 42 JSON Lines files: 9 accept, 33 reject). JSON schemas (structural): [`spec/schemas/fep-0005/`](../schemas/fep-0005/). The TypeScript and Rust SDKs do not have this profile yet (follow-up); their parity scripts skip it.

```
fidetype conformance --profile fep-0005                        # reference consumer over the vectors
fidetype validate --profile fep-0005 stream_or_log.jsonl       # producer check
fidetype control replay --config ccfg.json stream.jsonl        # reference control trust layer
```

| Check | Rules | Vectors (accept / reject) |
|---|---|---|
| `FEP5-V01-CORE` | Compatibility | C01-C05 / C23 |
| `FEP5-DECL` | 2 table, r1-r4 | C01, C02, C05 / C06-C11 |
| `FEP5-CONTROL` | 3 table, r1-r4 | C01, C03, C04 / C12-C19, C21 |
| `FEP5-ENABLE` | 4 table | C01 / C20 |
| `FEP5-INTENT` | 1 r2 (FEP-0003) | C02 / C22 |
| `FEP5-TD-FORMAT` | 5 table, r1-r4 | E01-E04 / E09-E14 |
| `FEP5-TD-ORDER` | 5 r5 | E02 / E15, E16 |
| `FEP5-SAFETY` | 6 r1-r7 | E01, E03, E04 / E05-E08, E17-E19 |

For a decision log the reference consumer returns `moving_ticks` (control COMMITs), `acted_intents` and `acted_texts`.

## Reference implementation
- `fidetype.trust.control`: validators, `ControlDeclaration`, `ControlTrustConfig` (frozen, `ccfg-` content id), `conformal_quantile`, `fit_control_config`, `gate` / `gate_batch` (shrinkage + no-signal gates), `clamp`, `ControlTrustLayer` (engage / stop, hand-off with a human channel, dead-man `poll`, optional FEP-0003 intent layer for the click with shared `seq`). CLI: `fidetype control replay`.
- `fidetype.decoders.velocity`: our own causal Wiener filter (ridge on sqrt counts, 200 ms history), `ResidualScale` (the `std` model), `StreamingVelocityDecoder` (one bin at a time). numpy only.
- `fidetype.trust.control_sim`: a clearly synthetic tuning-curve simulator for tests.
- Tests: `tests/test_control_trust.py`; profile tests in `tests/test_fep_profiles.py`.

## Evaluation
`experiments/2026-11-14-p12-03-control/` (plan committed before the runs). Public data: NLB MC_RTT (DANDI 000129, CC-BY-4.0; one monkey, 649 s, 130 units, 20 ms bins). The BrainGate CC0 set is planned (the Dryad download needs a token). Main split, test block 195 s:

| Measure | Result |
|---|---|
| Raw decoder R² / Pearson r | 0.478 / 0.707 (rotations 0.441-0.500) |
| Coverage at 0.80 / 0.90 / 0.95 (normalised) | 0.810 / 0.905 / 0.962 (0.90 in 5 / 5 rotations within [0.87, 0.93]: 0.877-0.923) |
| Mean 0.90 radius vs mean decoded speed | 88.6 mm/s vs 45.8 mm/s |
| Gated output at the declared level 0.90 | **no motion** (hold on 100 % of ticks); over-speed 0 |
| Zero input | raw drift 13.3 mm/s; gated 0 |
| Shuffled / time-reversed spikes | raw R² -0.133 / -0.317; gated motion 0 |
| Latency (decoder + layer, per tick) | median 0.09-0.10 ms, p99 0.20-1.66 ms (shared CPU) |

All six pre-declared criteria pass, but the declared configuration is useless for control: the 90 % velocity interval is wider than most decoded speeds, so the shrinkage gain is zero. A post-hoc level sweep (not pre-declared) shows the trade-off: at level 0.5 the cursor moves on 58 % of ticks with over-speed 0.17; at level 0.1 it moves on 96 % with over-speed 0.49 and R² 0.33. A per-tick speed bound at a high level does not fit a decoder with R² near 0.5. See the results for the full table and the open questions below.

## Alternatives
- **Extend v0.1 `pointer` with units and std.** Rejected: `pointer` has normalised absolute values and "change since the last event" semantics; a new event keeps it unchanged and adds `tick`, `std` and a declaration.
- **Per-tick COMMIT / OFFER as for intents.** Rejected: continuous output needs "how much", not "whether". `state` + `gain` keep FEP-0001 `COMMIT` / `ABSTAIN` for old consumers.
- **Gain from the decoder's own confidence only (no calibration).** Rejected as the reference: a decoder's `std` is not calibrated; split conformal gives a finite-sample coverage statement.
- **Other standards.** Apple BCI HID Report 3 carries pointer deltas, no uncertainty and no engage. ROS `geometry_msgs/TwistStamped` carries velocity with a frame id, no uncertainty policy. IEC 60601-1 / ISO 14971 give processes for risk, not a data format.

## Privacy and leakage
- Control logs are behavioural data (where and when a person moved). Keep them under the rules of text logs (5.4).
- `control_enable` MUST NOT carry personal text. `source` names a channel, never a person.
- Raw neural data never appears in control events; `std` and `values` are decoder outputs.

## Open questions
1. **The gain level.** At level 0.9, conformal shrinkage gave no motion with a linear decoder (R² 0.48). Should the reference move to a calibrated bound on displacement over a horizon (for example 0.5 s), where errors average out, instead of a per-tick speed bound?
2. Should `uncertainty` allow a full covariance (ellipse) and a conformal radius sent by the producer?
3. A float-channel LSL binding for control at high rates (section 7 rule 1).
4. Position control: the reference layer actuates velocity only. Rules for absolute position (bounded jump per tick, hold = keep the last position) are not tested.
5. Should the no-signal reference gate (section 6 rule 2d) be a MUST? On MC_RTT it blocked almost every tick at level 0.9 (decoded speeds are close to the 13 mm/s drift).
6. Should the click intent be blocked while the cursor moves fast (a dwell rule)?
