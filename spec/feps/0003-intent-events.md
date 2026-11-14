# FEP-0003: Output profiles and discrete intent events

| | |
|---|---|
| **FEP** | 0003 |
| **Title** | Output-agnostic core + output profiles; the discrete-intent profile (intent vocabulary, intent events, risk classes, COMMIT / OFFER / ABSTAIN for intents, confirmation, undo, feedback) |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft |
| **Type** | Spec change (additive, Development) |
| **Affects** | `neuraltextstream-v0.1.md` sections 3.0, 3.1 (`vocab_type = "command"`), 3.5 (`decision`), 3.7 (`pointer`), 6.5 and section 10; uses FEP-0001 (`segment_end`, `trust_decision`) and FEP-0002 (LSL) |
| **Created** | 2026-11-13 |
| **Discussion** | P12-01, P12-02 (roadmap phase P12 "Beyond text: intent and control"); `src/fidetype/trust/intent.py`, `wiki/concepts/intent-events.md` |

## Summary
Today NTS carries text: frames over characters or phonemes, n-best text hypotheses, and text trust decisions. This FEP does two things.

1. **Core and profiles (P12-01).** It names the parts of NTS that do not depend on the output (the *core*) and groups the rest into *output profiles*: `text` (today's NTS, unchanged), `intent` (this FEP) and `control` (continuous pointer control, a later FEP). It maps the v0.1 `decision` and `pointer` events into the profiles.
2. **The discrete-intent profile (P12-02).** It adds an intent vocabulary declaration with a **risk class** per intent, an `intent` input event (a candidate set with scores), an `intent_feedback` event, and the intent form of `trust_decision` (COMMIT / OFFER / ABSTAIN). It adds safety rules: an irreversible intent needs stricter risk control and an explicit confirmation; a null intent is never committed; there is no COMMIT on no-signal input; every final decision carries audit fields.

All parts are additive. No field of the text profile changes. A v0.1 consumer ignores the new event types (6.2 rule 5) and the new header key. The opt-in conformance profile `fep-0003` tests the rules.

## Motivation
- People who cannot speak or type also need to *act*: select a menu item, confirm, cancel, undo, stop a wheelchair, switch a mode, call a caregiver. Many BCIs give such discrete outputs (P300 spellers, SSVEP menus, motor-imagery switches, EMG gestures, Apple BCI HID buttons).
- v0.1 has `vocab_type = "command"` and a `decision` event, but no risk information and no trust output for actions. The text trust layer cannot be reused as is: a wrong text can be corrected later; a wrong "call caregiver" or "send" cannot.
- A "stop" is safer than a "go". One wrong-commit limit for all intents is too strict for safe intents and too lax for irreversible ones. The trust layer needs one limit **per risk class**.
- M2-18 showed that a trust layer can commit on no-signal input (empty texts on uniform streams). The same failure happens with intents: in our sEMG recast, the decoder's output on an all-zero window is one confident key, and a configuration fitted on clean data acts on 37 % of zero-input presses (section "Evaluation"). The standard must make this failure visible and give a defence.

## Terms
- **Decision unit**: one intent decision of a session (one `intent` event, one v0.1 `decision`, one segment of command frames, or one explicit feedback that executes an intent). Units are numbered 0, 1, 2, ... per session (`unit`).
- **Arm**: a final OFFER with `confirm_required = true`. It shows an irreversible intent and waits for a confirmation. Arming does not act.
- **Bridge**: a program that actuates decisions (a device driver, an HID exporter, a smart-home gateway).

## Proposal

### 1. Core and output profiles (P12-01)
| Part | What | Events and fields |
|---|---|---|
| **Core** | Output-agnostic: stream identity, vocabulary, frames, time, signal quality, provenance | `header` (`spec_version`, `vocab`, `vocab_type`, `blank_id`, `source`, `meta`, `clock_domain`), `frame`, `signal_quality`, `segment_end` (FEP-0001), `end`, timing fields (3.8), `meta` conventions (4), provenance (4.3) |
| **Text profile** | Text entry (today's NTS) | `hypothesis` (3.6) with evidence fields and `decode_declaration` (FEP-0001); `trust_decision` without `profile` (or `profile = "text"`) |
| **Intent profile** | Discrete intents (this FEP) | header `intent_declaration`; `intent`; `intent_feedback`; v0.1 `decision` (3.5) as a one-candidate intent; `trust_decision` with `profile = "intent"` |
| **Control profile** | Continuous control (later FEP, P12-03) | v0.1 `pointer` (3.7); confidence-gated actuation (velocity scaling, dead-man hold, safe-stop, rate limits) |

Rules:
1. A stream MAY carry events of more than one profile. Each event belongs to exactly one profile by its `type` (and, for `trust_decision`, by `profile`).
2. A profile adds event kinds and conventions only. It MUST NOT change a core field or a field of another profile.
3. **Mapping of v0.1 events.** A v0.1 `decision` with a label in the declared intents is an intent decision unit with one candidate (`score` and `score_semantics` as given). A v0.1 `pointer` belongs to the control profile. Neither event changes.
4. The name of the core is open (question 1). "NeuralTextStream" stays the name of the text profile and of the whole format for now.

### 2. Intent vocabulary declaration (header key `intent_declaration`, Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `vocab_id` | string | No | Namespaced id, `intent.*` (for example `intent.home-v1`) |
| `vocab_version` | string | No | Version of that vocabulary |
| `intents` | list of objects | Yes | One entry per intent, at least one |
| `intents[].id` | string | Yes | The intent id, unique. Convention: `intent.<verb>[.<object>]`, for example `intent.select`, `intent.call-caregiver`, `intent.menu.3`, `intent.mode.switch` |
| `intents[].risk` | `safe`, `undoable` or `irreversible` | Yes | The producer's risk class (section 6 rule 7: a consumer may make it stricter) |
| `intents[].role` | `action` (default), `null`, `confirm`, `cancel`, `undo` | No | `null`: "no intent" (rest, idle); `confirm` / `cancel` / `undo`: control intents with the meaning of section 6 |
| `intents[].label` | string | No | A human-readable label |

Risk classes (from the least to the most strict):

| Class | Meaning | Examples | Default wrong-commit limit (reference) |
|---|---|---|---|
| `safe` | A wrong action costs little and needs no repair | stop, next, previous, scroll, cancel | alpha 0.10 |
| `undoable` | A wrong action can be reversed by `undo` | select, type a key, mode switch, menu choice | alpha 0.05 |
| `irreversible` | A wrong action cannot be reversed | send message, call caregiver, pay, delete, unlock door | alpha 0.01 **and** confirmation (section 6 rule 4) |

Rules:
1. Intent ids MUST be unique. `intents` MUST have at least one intent whose role is not `null`.
2. `risk` MUST be one of the three classes.
3. At most one intent each MAY have the role `confirm`, `cancel` and `undo`.
4. If any intent is `irreversible`, the `confirm` intent (if present) MUST be `irreversible`: it executes irreversible intents.
5. On a stream with `vocab_type = "command"` and an `intent_declaration`, the tokens of `vocab` (without `blank_id`) MUST equal the declared intent ids (as sets). On other streams (for example a character stream that also carries intent events) `vocab` stays the text vocabulary.
6. A vocabulary SHOULD have a `null` intent if the decoder can see "no intent" (rest) input. The decoder SHOULD be trained to output it on rest and no-signal input.

### 3. `intent` event (decoder output, Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"intent"` | Yes | |
| `id` | string | Yes | Unique in the stream |
| `t` | float | Yes | Signal time of the decision, seconds |
| `t_start`, `t_end` | float | No | Signal window that the decision covers |
| `is_final` | boolean | Yes | `false`: a provisional preview (the decoder can still change it) |
| `revision_of` | string or null | No | Id of an earlier intent event that this one replaces |
| `score_semantics` | string | Yes | As in 3.5 |
| `candidates` | list of objects | Yes | Ranked best first, at least one: `intent` (a declared id) and `score` (number, or null / absent with `none`) |

Rules:
1. An `intent` event MUST come after a header with an `intent_declaration`.
2. Every `candidates[].intent` MUST be declared. An intent MUST NOT appear twice.
3. With `calibrated_prob` or `uncalibrated_prob`, every score MUST be in [0, 1] and the scores MUST sum to at most 1 (tolerance 1e-6). The list MAY be a top-k subset; a consumer spreads the missing mass uniformly over the intents that are not listed (as for sparse frames, 3.3). With `none`, no candidate has a score. With `power` or `strength`, scores are finite numbers.
4. Candidates with scores MUST be ranked best first (non-increasing scores).
5. `id` MUST be unique in the stream.
6. Command-vocabulary frames are an alternative form: on a `vocab_type = "command"` stream, the frames of a segment (closed by `segment_end` or `end`) form one decision unit; the reference layer averages their probabilities.

### 4. `intent_feedback` event (user interface or other channel, Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"intent_feedback"` | Yes | |
| `ref_unit` | integer >= 0 | Yes | The decision unit it answers |
| `outcome` | string | Yes | `confirmed`, `cancelled`, `selected`, `undone`, `correct`, `wrong` |
| `intent` | string | If `selected` | The intent the user selected (from an OFFER) |
| `t` | float | No | Time of the feedback |
| `source` | string | No | The channel, for example `switch`, `touch`, `caregiver`, `eye-tracker` |

`confirmed` / `selected` are explicit choices through a channel other than the decoder. `cancelled` drops an armed intent. `undone`, `correct` and `wrong` are labels for monitoring (an undo is a noisy label: the user may undo a correct action). Feedback is input to the trust layer, not decoder output.

### 5. Intent `trust_decision` (trust layer output, Development)
An intent decision is a FEP-0001 `trust_decision` with these changes:

| Field | Type | Required | Description |
|---|---|---|---|
| `profile` | `"intent"` | Yes | Marks the intent profile. Absent means `text` |
| `unit` | integer >= 0 | Yes | Decision unit (in place of `utterance`) |
| `action` | `COMMIT`, `OFFER`, `ABSTAIN` | Yes | No ASK and no OFFER_WORDS for intents |
| `intent` | string | For COMMIT | The intent to actuate (for an armed OFFER: the armed intent) |
| `offered` | list of strings | For OFFER | Intents shown to the user, best first |
| `risk_class` | class or null | For COMMIT | Effective risk class of `intent` (or of the top-1 intent) |
| `threshold` | number in [0, 1] or null | No | The COMMIT threshold of that class |
| `role` | role or null | No | Role of `intent` (or of the top-1 intent) |
| `confirm_required` | boolean | No | `true` on an armed OFFER |
| `confirmation_of` | integer | For an irreversible COMMIT | Unit of the OFFER that this COMMIT confirms |
| `confirmed_via` | `intent` or `feedback` | No | How the confirmation came |
| `undo_of` | integer | For an undo COMMIT | Unit of the COMMIT it reverses |
| `pending_cleared` | string | No | Why an armed intent was dropped |
| `p_top1`, `score_semantics`, `session`, `seq`, `reason`, `config_id`, `input`, `latency_s` | as FEP-0001 | | `p_top1` is null for a COMMIT that an explicit feedback caused |
| `vocab_id` | string | No | `vocab_id` of the declaration |

Rules:
1. An intent decision MUST carry `profile = "intent"` and `unit`, and MUST NOT carry `utterance`.
2. An intent decision MUST NOT carry `shown`. *Why:* a FEP-0001 text bridge acts on `shown[0]` of a final COMMIT. Without `shown` it can never type an intent id as text. (Such a bridge sees a COMMIT with no text, as in a privacy log.)
3. A COMMIT MUST carry `intent` and `risk_class`. An OFFER MUST carry a non-empty `offered`.
4. FEP-0001 section 3 rules 1 and 5-7 apply, with `unit` in place of `utterance`: **a bridge MUST NOT actuate a decision with `is_final = false`**; at most one final decision per (`session`, `unit`); none after it.
5. A bridge MUST actuate only final COMMITs (`intent`). It MUST NOT actuate an OFFER. An OFFER becomes an action only through a later COMMIT (a confirmation or an explicit selection).

### 6. Safety rules
1. **No null COMMIT.** A trust layer MUST NOT COMMIT an intent whose role is `null`. It SHOULD NOT OFFER it either. (The M2-18 content-gate idea: "nothing" must not look like an action.)
2. **No COMMIT without probabilities.** A trust layer MUST NOT COMMIT on input whose `score_semantics` is `none`, `power` or `strength` (it cannot calibrate them), unless an explicit feedback confirms the intent. It MAY OFFER.
3. **Calibrated per-class threshold.** A COMMIT (and an arm) of class r needs the calibrated top-1 probability `p_top1 >= threshold_r`. The thresholds SHOULD come from a finite-sample risk-control method on labelled calibration units of the same user and session (reference: LTT with delta split over the classes, or CRC). The controlled quantity is, per class r, the rate of **wrong COMMITs of class r per decision unit** (for `irreversible`: wrong arms). The reference default limits are 0.10 / 0.05 / 0.01. A class whose bound is infeasible on the calibration data MUST NOT commit (threshold = infinity).
4. **Irreversible intents need an explicit confirmation.** A trust layer MUST NOT COMMIT an `irreversible` intent directly. It arms it (final OFFER, `confirm_required = true`). A later final COMMIT with `confirmation_of` = that unit executes it, when either (a) the next decision unit is the `confirm` intent and passes the `irreversible` threshold, or (b) an `intent_feedback` with `confirmed` (or `selected` for an OFFER list) arrives through another channel. An armed intent is dropped by any other decision unit, a failed confirmation, or `cancelled`. One OFFER MUST NOT be confirmed twice. Confirmation can only remove executions, so the wrong-execution rate is at most the wrong-arm rate.
5. **Undo.** An undo COMMIT carries `undo_of` = the unit of an earlier final COMMIT of the same session. It MUST NOT target an `irreversible` COMMIT. The reference layer undoes the latest undoable or safe action within a window (3 units; optional seconds).
6. **No COMMIT on no-signal input.** A trust layer MUST NOT COMMIT when it knows the input carries no signal: (a) the top-1 intent is `null`; (b) the latest `signal_quality` index is below the configured minimum; (c) the distribution is uniform. The reference also applies a data-free floor (COMMIT needs p >= 0.5, "more likely than all other intents together"). A producer SHOULD send `signal_quality` (3.9). A configuration SHOULD be fitted with a **no-signal reference** (decoder outputs on all-zero or rest input; no labels needed): each class threshold is raised above the reference's top-1 probability of that class. An evaluation MUST report commits on no-signal controls (uniform, zero input) next to the clean numbers. *Why:* risk control bounds the wrong-commit rate on data like the calibration data. It does not see a no-signal input that the calibration data did not contain (section "Evaluation").
7. **Risk classes only get stricter.** A consumer MAY raise the risk class of an intent (deployment `risk_override`, or a stricter class in the stream's declaration). It MUST NOT lower the declared class.
8. **Gates keep the bound.** Rules 1, 2, 4 and 6 only remove COMMITs. For one unit the loss can only go down, so a fitted risk bound still holds with them.
9. **Audit and provenance.** Every final intent decision SHOULD carry `config_id` (content id of the frozen configuration), `input` (kind, input id, `score_semantics`, SHA-256 of the input event) and `vocab_id`. A layer MAY write the decisions to the provenance ledger (4.3).

### 7. Coexistence with text, LSL and HID
1. Text and intent events MAY share one NTS stream (and one LSL events stream, FEP-0002 section 5). An intent event does not end the current text utterance; `segment_end` closes text utterances (and command-frame segments).
2. Text and intent decisions of one session MAY share one decision log (and one FEP-0002 decisions stream). Then they MUST share the `seq` counter: `seq` increases strictly over both profiles. `utterance` counts text units and `unit` counts intent units, each on its own.
3. **LSL (FEP-0002).** No binding change: `intent` and `intent_feedback` are marker JSON on the events stream; intent `trust_decision` events go to the decisions stream. `intent_declaration` travels inside `desc/fidetype/nts_header`. A decisions outlet SHOULD add the desc key `profiles` (for example `text,intent`). The binding version stays `nts-lsl/0.1`.
4. **Apple BCI HID (6.5).** A bridge MAY map final intent COMMITs to button events by an explicit table (P12-05). HID has no risk classes and no confirmation: the bridge MUST apply rules 4 and 5 of section 5 before it sends a report.

## Examples
Input (a home-control vocabulary on a command stream):
```json
{"type": "header", "spec_version": "0.1", "vocab": ["intent.rest", "intent.select", "intent.stop", "intent.undo", "intent.confirm", "intent.call-caregiver"], "vocab_type": "command", "blank_id": null, "source": "acme-ssvep", "intent_declaration": {"vocab_id": "intent.home-v1", "intents": [{"id": "intent.rest", "risk": "safe", "role": "null"}, {"id": "intent.select", "risk": "undoable"}, {"id": "intent.stop", "risk": "safe"}, {"id": "intent.undo", "risk": "undoable", "role": "undo"}, {"id": "intent.confirm", "risk": "irreversible", "role": "confirm"}, {"id": "intent.call-caregiver", "risk": "irreversible"}]}}
{"type": "signal_quality", "t": 4.9, "value": 0.93, "unit": "index"}
{"type": "intent", "id": "u7", "t": 5.0, "is_final": true, "score_semantics": "uncalibrated_prob", "candidates": [{"intent": "intent.call-caregiver", "score": 0.97}, {"intent": "intent.select", "score": 0.02}]}
{"type": "intent", "id": "u8", "t": 6.5, "is_final": true, "score_semantics": "uncalibrated_prob", "candidates": [{"intent": "intent.confirm", "score": 0.98}]}
```
Output (decision log):
```json
{"type": "trust_decision", "profile": "intent", "session": "s1", "seq": 12, "unit": 7, "is_final": true, "action": "OFFER", "reason": "armed: p 0.996 >= 0.990 (irreversible); needs confirmation", "p_top1": 0.996, "score_semantics": "calibrated_prob", "risk_class": "irreversible", "threshold": 0.99, "intent": "intent.call-caregiver", "role": "action", "offered": ["intent.call-caregiver"], "confirm_required": true, "config_id": "icfg-0123456789abcdef", "input": {"kind": "intent", "intent_id": "u7", "score_semantics": "uncalibrated_prob", "sha256": "..."}}
{"type": "trust_decision", "profile": "intent", "session": "s1", "seq": 13, "unit": 8, "is_final": true, "action": "COMMIT", "reason": "confirmed: p 0.997 >= 0.990", "p_top1": 0.997, "score_semantics": "calibrated_prob", "risk_class": "irreversible", "threshold": 0.99, "intent": "intent.call-caregiver", "role": "action", "confirmation_of": 7, "confirmed_via": "intent", "config_id": "icfg-0123456789abcdef"}
```
A bridge acts on the second line only.

## Compatibility
- Producers: nothing changes for text producers. All parts are optional.
- Consumers: a v0.1 consumer ignores `intent`, `intent_feedback` and the header key. A FEP-0001 consumer of a decision log accepts intent decisions (they meet the FEP-0001 table) and acts on no text, because they carry no `shown` (tested: the reference layer's intent log passes the `fep-0001` profile). The 52 v0.1 vectors and the `fep-0001` / `fep-0002` vectors do not change.
- Stability: all parts start at Development.

## Conformance
Profile `fep-0003` (opt-in, `src/fidetype/conformance/profiles/fep0003.py`). Golden vectors: [`spec/conformance/fep-0003/`](../conformance/fep-0003/) (`manifest.json`; 44 JSON Lines files: 12 accept, 32 reject). JSON schemas (structural): [`spec/schemas/fep-0003/`](../schemas/fep-0003/).

```
fidetype conformance --profile fep-0003                          # reference consumer over the vectors
fidetype validate --profile fep-0003 stream_or_log.jsonl         # producer check
fidetype conformance consumer --profile fep-0003 --cmd "my-reader {path}"
fidetype intent replay --config icfg.json stream.jsonl           # reference intent trust layer
```

| Check | Rules | Vectors (accept / reject) |
|---|---|---|
| `FEP3-V01-CORE` | Compatibility | I01-I06 / I23 |
| `FEP3-DECL` | 2 table, r1-r4 | I01 / I07-I11 |
| `FEP3-VOCAB` | 2 r5 | I05 / I12 |
| `FEP3-INTENT` | 3 table, r1-r5 | I01, I02, I04 / I13-I21 |
| `FEP3-FEEDBACK` | 4 table | I03 / I22 |
| `FEP3-TD-FORMAT` | 5 table, r1-r3 | D01-D06 / D07-D12 |
| `FEP3-TD-FINAL` | 5 r4, 7 r2 | D04, D06 / D13, D14 |
| `FEP3-SAFETY` | 6 r1-r5 | D02, D03, D05 / D15-D21 |

For a decision log the reference consumer returns `acted_intents` (final intent COMMITs) and `acted_texts` (FEP-0001). D06 has a provisional COMMIT and a final ABSTAIN: a conforming consumer acts on nothing.

## Reference implementation
- `fidetype.trust.intent`: `IntentVocabulary`, `IntentTrustConfig` (frozen, `icfg-` content id), `fit_intent_config` (temperature + per-class LTT/CRC through `fidetype.trust.risk_control`, optional no-signal reference), `IntentPolicy`, `evaluate_policy`, `IntentTrustLayer` (intent events, v0.1 decisions, command frames, confirmation, undo, feedback). CLI: `fidetype intent replay`.
- `fidetype.trust.streaming.StreamingTrustLayer(intent=IntentTrustLayer(...))`: one stream, both profiles, shared `seq`.
- `fidetype.trust.intent_sim`: a clearly synthetic simulator (null intent, no-signal trials, quality channel).
- Tests: `tests/test_intent_trust.py`; profile tests in `tests/test_fep_profiles.py`.

## Evaluation
`experiments/2026-11-13-p12-intent-events/results.md`. Public data only: the Toronto sEMG typing set (CC BY 4.0) recast as a 27-way key-choice intent, plus the simulator. Summary (session-calibrated sEMG decoder, top-1 accuracy 0.299; 19 participants x 100 splits; LTT + no-signal reference):

| input | act rate | wrong safe / undoable / irreversible (per unit) |
|---|---|---|
| clean | 0.057 (commit precision 0.796; OFFER 0.12, truth in offer 0.905) | 0.0002 / 0.0115 / 0 |
| uniform | 0 | 0 / 0 / 0 |
| zero input | 0 (without the reference: 0.371, 97 % wrong) | 0 / 0 / 0 |
| time-shuffled EMG | 0.006 | 0 / 0.0044 / 0 |
| pair-shuffled outputs (exchangeability broken) | 0.057 | 0.0080 / 0.0432 (above alpha in 34 % of test sets) / 0 |

On clean data every class stays at or below its alpha in every setting (sEMG three decoders, simulator; LTT and CRC). LTT never arms the irreversible keys with about 260 calibration units (infeasible at alpha 0.01); CRC arms 1 % with 0.0029 wrong arms. In the simulator a signal-quality gate takes commits on no-signal trials from 0.405 to 0.

## Alternatives
- **Reuse `hypothesis` for intents (text = intent id).** Rejected: a text bridge would type intent ids, and n-best text has no risk class.
- **One wrong-commit limit for all intents.** Rejected: it forces the strictest limit on safe intents (few commits) or the laxest on irreversible ones (unsafe).
- **Put risk classes only in the trust configuration.** Rejected: the producer knows the device semantics. The declaration carries them; the consumer can only make them stricter.
- **A separate action name `CONFIRM`.** Rejected for now: OFFER + `confirm_required` keeps the FEP-0001 action set and its consumers (open question 3).
- **Other standards.** Apple BCI HID carries buttons and pointer, but no scores, risk or confirmation. IEC 62304 / ISO 14971 give risk-management processes, not a data format. LSL carries the events (section 7 rule 3).

## Privacy and leakage
- Intent ids and labels are device semantics, not personal text. A decision log of intents is still behavioural data (when a person called for help). Logs SHOULD be kept under the same rules as text logs (5.4).
- `intent_feedback` MUST NOT carry free text of the user. `source` names a channel, never a person.

## Open questions
1. Name of the core: keep "NeuralTextStream" for everything, or an umbrella name (for example "NeuralStream") with "NTS text profile"?
2. Should `irreversible` intents be allowed a direct COMMIT under a stricter limit (for example alpha 0.001) when a second channel is not available?
3. Should an armed intent use its own action name (`CONFIRM`) instead of OFFER + `confirm_required`?
4. Should the no-signal reference (section 6 rule 6) become a MUST for configurations of irreversible intents?
5. How long may an armed intent wait (units vs seconds)? The reference allows only the next unit.
6. Should the `intent.*` id conventions become a registry (`spec/vocab/`), aligned with `hid.bci.switch.*`?
