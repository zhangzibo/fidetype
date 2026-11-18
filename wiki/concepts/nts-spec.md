---
title: NeuralTextStream specification (versions, 1.0 RC4)
type: concept
tags: [spec, neuraltextstream, standard, versioning, conformance, protobuf, p1]
sources: []
updated: 2026-11-18
---

# NeuralTextStream specification

The written contract of Fidetype. A decoder writes a NeuralTextStream (NTS); a trust layer reads it and writes [`trust_decision`](trust-decision.md) events; a bridge acts only on final decisions.

| Version | File | Status |
|---|---|---|
| 0.1 | [`spec/neuraltextstream-v0.1.md`](../../spec/neuraltextstream-v0.1.md) | Current release (Development) |
| FEP-0001 … FEP-0005, FEP-0007, FEP-0008 | [`spec/feps/`](../../spec/feps/) | Draft proposals (how FEPs work: [FEP process](fep-process.md)). FEP-0007 (unknown enumeration values) is new in RC3; FEP-0008 (optional field types, semantic-convention registry) is new in RC4 |
| **1.0 RC4** | [`spec/nts-1.0-rc4.md`](../../spec/nts-1.0-rc4.md) | **DRAFT for public comment** (2026-11-15). Not final. Current RC. Changes: section 1.6 |
| 1.0 RC3 | [`spec/nts-1.0-rc3.md`](../../spec/nts-1.0-rc3.md) | Superseded by RC4; kept as the record |
| 1.0 RC2 | [`spec/nts-1.0-rc2.md`](../../spec/nts-1.0-rc2.md) | Superseded by RC3; kept as the record |
| 1.0 RC1 | [`spec/nts-1.0-rc1.md`](../../spec/nts-1.0-rc1.md) | Superseded by RC2 (same rule text); kept as the record |

Changelog: [`spec/CHANGELOG.md`](../../spec/CHANGELOG.md). Index of specs and FEPs: [`spec/README.md`](../../spec/README.md).

Tools around the spec: the [collector](collector.md) (draft FEP-0006, P3) receives NTS from files and WebSocket, runs the trust layer and the privacy filter, and exports decision logs. It changes no field of NTS.

## RC4 amendment 7: advisory licence check (2026-11-18)
Roadmap P5-19 (gap 57), FEP-0010 LIC-2. No rule change; no earlier vector changed its verdict or warnings. Text: [RC4 section 1.6](../../spec/nts-1.0-rc4.md#16-changes-from-rc3), 3.4 (MET-12 note), C.1.

| Item | Detail |
|---|---|
| New advisory check | `NTS-LICENCE-MATCH`: `data.research_only = false` with a Creative Commons id with `NC` or `LicenseRef-unknown` (ASCII, without case) gives a warning, never a reject |
| Table | One fixed pattern, not the SPDX list: Python `fidetype.trust.licence.no_commercial_id`, TypeScript `noCommercialId`, Rust `checks::no_commercial_id`. Other ids give no warning (silent, not "permissive") |
| Vectors and parity | V101, V102 (NPZ), V103 (lower case, `-IGO`): accept with the warning; V104 (`CC-BY-SA-4.0`): accept, no warning. 355 in all. Python = TypeScript = Rust, warnings pinned |
| Policy half (P5-18, LIC-3) | Collector exporter option `refuse_research_only` ([collector](collector.md)); FEP-0006 section 4 rule 6 |

## RC4 amendment 6: data licence keys (2026-11-17)
Roadmap P5-13 (gap 47). Additive; no earlier vector changed its verdict. Text: [FEP-0010](../../spec/feps/0010-data-licence-keys.md), [RC4 section 1.6](../../spec/nts-1.0-rc4.md#16-changes-from-rc3), 3.4 (MET-12), 6.1.1, 6.2 (TD-15).

| Item | Detail |
|---|---|
| New `meta` keys (MET-12) | `data.licence` (SPDX id, non-empty string) and `data.research_only` (boolean; MUST be `true` for a licence without commercial use). Optional, Development |
| New `input` key (TD-15) | `trust_decision.input.research_only` (boolean, audit data, TD-13): from the stream keys and from the provenance lineage |
| Evidence | The six reference adapters (emg2qwerty, KT-sEMG, Toronto sEMG, Willett, SpanishBCBL, B2T '25) and the 7 benchmark tracks. SpanishBCBL dropped its custom key `spanishbcbl.licence` |
| Decisions in the FEP | Spelling `licence` (as the ledger and `fidetype.trust.licence`); `research_only` inside `input`, not a new top-level field (no schema change); validators check types only |
| Open (FEP-0010) | LIC-1 dataset id key. LIC-2 (advisory agreement check) answered by amendment 7 (P5-19); LIC-3 (collector policy) answered by FEP-0006 4 rule 6 (P5-18), both 2026-11-18 |
| Vectors and parity | V98 (accept), V99, V100 (reject); 351 in all. Python = TypeScript = Rust |

> **Our take:** the stream can now say "research only" without the ledger. This is the format half of the licence rule; the policy half (refuse research-only output in a product build) is gap 56.

## RC4 amendment 3: implementation levels, self-certification, MET-11 check (2026-11-17)
Roadmap P7-02 and P1-16. Additive; no earlier vector or kit entry changed its verdict. Text: [RC4 section 1.6, 9.2, 9.6, 9.7](../../spec/nts-1.0-rc4.md#96-implementation-levels-nts-core-nts-full-nts-trust-ready-amendment-3).

| Item | Detail |
|---|---|
| Implementation levels (CNF-2, CNF-5 … CNF-7) | NTS Core (frame core), NTS Full (all event kinds of the named profiles), NTS Trust-ready (Full + stream level provenance for producers; the right stream level of each kit stream for consumers). Cumulative. Bindings added by their kit entries. Details: [conformance suite](conformance-suite.md#implementation-levels-and-self-certification-p7-02) |
| Stream levels get rule ids | CNF-3 (trust-ready checks), CNF-4 (provenance checks) |
| Self-certification (CNF-8) | `spec/conformance/certified.json` + the `nts-conform` JSON report as evidence; first entries: our three SDKs (consumers, NTS Trust-ready) and our adapters (producers) |
| MET-11 check | Advisory `NTS-MODALITY-MATCH` in Python, TypeScript and Rust; MET-11 gets its C.1 row (gap 20 closed) |
| Vectors and parity | V93 … V96 (accept; three pin the warning); 345 in all; kit 36 entries (0.2.0). Python = TypeScript = Rust on all 345, on the 36 kit entries and on 27,767 fuzz mutants (seeds 1-3, `--n 30`); the summaries also agree on `warnings` and `level` where a vector pins them; schema 213 / 213 one-line verdicts |

## RC4 amendment: modality keys and G-13 part b (2026-11-16)
Additive change to the RC4 draft ([FEP-0009](../../spec/feps/0009-modality-semantic-conventions.md), [RC4 section 1.6](../../spec/nts-1.0-rc4.md#16-changes-from-rc3)). No RC4 vector changed its verdict.

| Item | Detail |
|---|---|
| New keys (SC-1, partly) | `emg.placement`, `emg.derivation`; `meg.sensor_types`; `implant.array_type`, `implant.array_count`, `implant.features`, `implant.bin_s`, `implant.areas`. All optional, Development |
| Evidence | Only facts that a reference adapter writes: emg2qwerty, KT-sEMG, Toronto sEMG, SpanishBCBL MEG, Willett handwriting, Brain-to-Text '25; checked against NLB MC_RTT |
| New rule MET-11 | A modality key goes with its `device.modality`. Not checked by the validators |
| Still open | `eeg.*`, `fnirs.*`: no reference producer yet (SC-9) |
| G-13 part b closed | New proto option `json_null_list`; the generated schema accepts control `absent: null` (GEN-9). Vector C26 |
| G-13 part a | A dense frame with wrong-typed sparse keys. Options A1 (forbid both forms), A2 (both allowed, sparse keys still typed; recommended), A3 (sparse keys ignored, schema relaxed). **Closed by amendment 2 (below): A2** |
| Vectors and parity | V83 … V87, C26 (336 in all); Python = TypeScript = Rust on all 336; schema 205 / 205 one-line verdicts |

## RC4 amendment 2: G-13 part a closed with option A2 (2026-11-16)
Roadmap P1-14. Rule FRM-2 of [RC4 section 4.2](../../spec/nts-1.0-rc4.md#42-frame); summary in RC4 section 1.6. No earlier vector changed its verdict.

| Item | Detail |
|---|---|
| Rule (FRM-2) | A dense frame MAY also carry sparse keys. The dense form wins; the consumer does not use the sparse keys. Each sparse key that is present keeps its type (GEN-11): `top_ids` unique integers >= 0, `top_log_probs` numbers or null, `rest_log_prob` a number or null |
| Why A2 | It follows GEN-11 (a field of a table has its type when present). It keeps every stream with well-typed keys valid. The schema already typed the keys, so the schema does not change |
| SDK change | Python, TypeScript, Rust: the JSONL readers and the streaming validators refuse a wrong type (check NTS-JSONL-FRAME) |
| Vectors and parity | V88 (accept), V89 … V92 (reject); 341 in all. Python = TypeScript = Rust on all 341 and on 27,497 fuzz mutants (seeds 1-3, `--n 30`); schema 210 / 210 one-line verdicts |

## RC4: semantic conventions and optional field types (2026-11-15)
RC4 answers the open questions SC-2 … SC-8 of the [semantic-convention registry](../../spec/semconv/registry.md) (roadmap P1-04) and closes gap G-12. Rule: the simplest rule that keeps valid data valid. No RC3 vector changed its verdict. Normative changes: [FEP-0008](../../spec/feps/0008-optional-field-types-and-semconv.md).

| Item | Answer | Rules |
|---|---|---|
| SC-1 modality keys | Deferred to a FEP with evidence from real producers (P4 adapters) | 12.5, A.8 |
| SC-2 planned namespaces | Reserved now; a custom key in `emg.*` … `implant.*` gets the MET-3 warning (all three SDKs) | MET-3 |
| SC-3 empty strings | `""` is not valid for the string keys of 3.4 ("non-empty string"); the validators already refused it | MET-7 |
| SC-4 value lists | Open: regulatory status, calibration method, `input.kind`, `declaration.mode`. Closed: `device.modality`, `declaration.status`, `declaration.where` | MET-8 |
| SC-5 stability of `input` / `declaration` keys | Development in 1.0 | 2.3 |
| SC-6 units | Only physical quantities have a unit (seconds); counts and indices have none | MET-9 |
| SC-7 YAML or prose | The YAML registry is normative; the spec tables are informative copies, kept equal by CI; A.1 item 9 resolved | MET-10 |
| SC-8 SDK constants | No spec change; the CI check also compares the SDK planned namespaces | MET-10 |
| G-12 optional field types | The table type applies (GEN-11). All three validators now check about 20 optional fields that only the JSON Schema checked, and the latency fields on every event | GEN-11, HDR-16, DEC-6, HYP-5, INT-T8, SEG-6, SQ-1, PTR-1, TIM-4, TD-F2, CTL-T8 |

| Item | Detail |
|---|---|
| How G-12 was found | A mutation probe: each field of each accept vector set to a wrong type; a gap = the generated schema refuses and every Python profile consumer accepts. 48 gap signatures before, 10 after (all accounted for: binding records, schema-only `trust_decision.t` now control-only, and new gap G-13) |
| New vectors | V69 … V82, F63 … F66, D24 … D26, I25, C25, E25 … E27 (26; 330 in all) |
| Parity | Python = TypeScript = Rust on 330 vectors and 26,687 fuzz mutants (seeds 1–3, `--n 30`); schema 201 / 201 one-line verdicts |
| New gap G-13 | Schema stricter than the spec in two places: sparse keys on a dense frame, control `absent: null` |

> **Our take:** making the YAML registry normative is the step that lets later keys (SC-1) and generated SDK constants live in one place, as in OpenTelemetry semantic conventions. The prose tables stay for readers; CI makes a difference impossible to merge. The G-12 fix was cheap only because the generated JSON Schema already had the types: the schema found the gaps, and the probe proved that no accept vector depended on them.

## RC3: the protobuf open questions answered (2026-11-15)
RC3 answers Q-1 … Q-8 of the [protobuf schema](nts-proto-schema.md) work. Rule: write down what the three SDKs already do, if that is safe. Else pick one rule and change all three SDKs. Before the choice, probe vectors went through all three SDKs: they agreed on every probe.

| Question | Answer | Rules | SDK change |
|---|---|---|---|
| Q-7 New enum values in a minor version | Version-gated. In `"0.1"` or `"1.0"` data an unknown value is an error, as before. In `"1.1"`+ data it is accepted, kept as "unknown", and gets a **safe fallback** that never acts (registry 12.3 column). Binding enums stay closed | VER-6 … VER-10, [FEP-0007](../../spec/feps/0007-unknown-enum-values.md) | Yes, all three |
| Q-1 JSON null | Only where the type says "or null" (four header fields and three intent fields now say so) | GEN-9 | No |
| Q-2 LSL keys outside EXT-3 | Written down: `segment_end.reason`, a `gap` field table, an EXT-3 exception | SEG-6, LSL-G3 | No |
| Q-3 Control reason codes | Open list; never read an unknown code as `ok` | CTL-T9 | No |
| Q-4 `declaration` / `input` keys | `declaration` MUST be an object; recommended key tables; audit data only | TD-F2, TD-13 | Yes (refuse a non-object `declaration`) |
| Q-5 Integer range | At most 2^53 − 1 | GEN-10 | Yes (JavaScript lost precision above it) |
| Q-6 Field of another profile | A custom key | PRF-5 | No (generated schema follows) |
| Q-8 Two SDK checks | Rule ids added | INT-T7, CTL-T8 | No |

Safe fallbacks of the action-relevant enums (VER-10):

| Unknown value | Fallback |
|---|---|
| `trust_decision.action` or `profile` | As ABSTAIN: no commit, no actuation, zero velocity, no candidate shown |
| intent `risk` / `risk_class` / `role` / `confirmed_via` | treated as `irreversible` / not actuated / as `null` / not actuated |
| control `state` | zero velocity; not engaged for CTL-S7 |
| control `quantity`, `frame`, `units`, `uncertainty` | no motion on the stream |
| `control_enable.source` | a stop is still a stop; an engage is not an engage |
| `intent_feedback.outcome` | never confirms; drops an armed intent |
| `score_semantics` | not a probability (INT-S2 as for `none`) |

| Item | Detail |
|---|---|
| New vectors | V66 … V68, F57 … F62, I24, D22, D23, W44, C24, E22 … E24 (17; 304 in all). No RC2 vector changed its verdict |
| Consumers | Text "acted" lists only from `profile` absent or `"text"`; `DecisionTracker` kind `unknown` (never forwarded) |
| Reference trust layers | Stay strict: they refuse a header with an unknown `vocab_type`, intent risk / role or control declaration value (VER-10 allows a stop) |
| Generated schema | Enum fields open; `Header.known` / `TrustDecision.known` apply unless `spec_version` is a newer minor version; profile fields typed per profile; integer bounds. 178 / 178 one-line vectors match |
| Parity | Python = TypeScript = Rust on 304 vectors and on 24,347 fuzz mutants (seeds 1–3, `--n 30`) |
| Informative fixes | 9.3 / 9.5 vector counts; C.1 row of HDR-12 (V62 … V65); new gap G-12 (optional-field types no validator checks) |

> **Our take:** the version gate is the key idea. A registry gets a new value only through a minor version, so an unknown value in `"1.0"` data is a producer bug, and in `"1.1"` data it is valid. This keeps the validators strict where they can be, and gives 1.x forward compatibility without one unsafe action. The open point: the reference trust layers refuse instead of applying the fallbacks (FEP-0007 open question).

## 1.0 RC2 in one table (RC3 has the same sections)
Roadmap phase [P1](../questions/roadmap-standard.md#p1-spec-to-10), tasks P1-01 (data model), P1-03 (versioning), P1-05 (bindings, partly), P1-08 (RC2: gaps G-2, G-3, G-4).

| Section | Content |
|---|---|
| 1-2 | Status, RFC 2119 key words, rule ids, terms; core data model and proposed stability per part |
| 3 | Header (core fields, vocabulary identity, `meta` conventions) |
| 4 | Events: JSON rules, `frame`, `segment_end`, `end`, `signal_quality`, `decision`, `hypothesis` (+ evidence, `decode_declaration`), `pointer` |
| 5 | Timing and clocks |
| 6 | Trust decisions (format, rules TD-1 … TD-12, provenance) |
| 7 | Profiles: text, [intent](intent-events.md) (Development), [control](control-events.md) (Development) |
| 8 | Bindings: JSON Lines, NPZ (read only for new data), [LSL](lsl-input.md) `nts-lsl/0.1`, [WebSocket](websocket-input.md) `nts-ws/0.1` |
| 9 | Conformance classes, levels, suite profiles, claims, SDK parity |
| 10 | Security and privacy: no raw signal in the stream, personal data, leakage, audit fields, transport auth |
| 11 | Versioning: semver, `spec_version` on headers and decisions, compatibility promise, extension rules, FEP lifecycle, SDK matrix |
| 12 | Registries (IANA style): event types, profiles, enumerations, vocabulary and intent namespaces, binding tokens, close codes |
| A | Every open question: resolved or "deferred to 1.1", with the reason |
| B | Migration from 0.1 |
| C | Traceability: rule id → [conformance](conformance-suite.md) check ids and vectors; gaps G-1 … G-11 |

## The one rule made stricter in code
**TD-9:** a 1.x trust layer MUST NOT emit a final text COMMIT whose committed text is empty or white space. Before: SHOULD NOT. The rule is gated by the new field `trust_decision.spec_version`, so 0.1 logs (for example Paper 1 v4) stay valid.

| Item | Detail |
|---|---|
| Evidence | M2-18: 320 empty COMMITs on 400 no-signal T12 streams ([streaming trust layer](streaming-trust-layer.md)); FEP-0003 forbids a null-intent COMMIT; FEP-0005 forbids motion on no-signal input. P5-07 (v5 candidate, opt-in): T12 dry run empty commits 655 → 0 |
| Validators | `FEP1-TD-FORMAT` in Python, TypeScript and Rust; JSON schemas of `fep-0001`, `fep-0003`, `fep-0005` |
| Vectors | `fep-0001` F41-F47 (accept: 1.0 log, 0.1 empty commit, future minor 1.7; reject: empty, white space, `"2.0"`, number `1.0`) |
| White space | The Python `str.isspace` set (listed in RC1 section 1.4), the same in all SDKs |

## RC2: TD-12, no blank candidates (new rule)
**TD-12:** a 1.x trust layer SHOULD NOT put blank text in `shown` of a text OFFER, ASK or OFFER_WORDS. A consumer or bridge MUST NOT offer a blank candidate: it drops it. Cause: the TD-9 commit gate turns a blank COMMIT into an OFFER whose only candidate can be the blank text (found in the [collector](collector.md)).

| Item | Detail |
|---|---|
| Version gate | Producer part: 1.x decisions only (0.1 decisions give no finding). Consumer part: every version |
| Validators | Advisory check `FEP1-TD-SHOWN` (a warning, never a reject) in Python, TypeScript and Rust. TypeScript and Rust profile `failures()` now skip advisory checks, as Python does. SDK `DecisionTracker` drops blank texts from `offered` and warns on 1.x decisions |
| Consumer summary | New keys `offered` (final text OFFER / ASK / OFFER_WORDS candidates without blanks) and `advisories` |
| Vectors | `fep-0001` F55 (accept with a warning, 1.0) and F56 (accept, 0.1: no warning). 56 vectors |
| Parity | Python = TypeScript = Rust on 283 vectors (`v0.1` … `fep-0005`; F55 and F56 also match on `offered` and `advisories`) and on 44,916 fuzz mutants (seeds 1-6, `--n 30`) |
| Producer with no candidate left | `ABSTAIN` with `shown = []`, not an OFFER without `shown` (that reads as a privacy log, TD-10) |

> **Our take:** TD-12 is a SHOULD NOT and not a MUST NOT because a blank candidate is never acted on by itself (the user must select it), so it is a usability fault, not a safety fault. The consumer MUST NOT keeps the user safe from it in every version.

## RC2: 1.x headers accepted (gap G-2 closed)
This part of RC2 changes no rule text. It makes the code follow rules HDR-2, VER-3, VER-4 and VER-5 for headers.

| Value of header `spec_version` | Result |
|---|---|
| `"0.1"` | Accepted, 0.1 rules (unchanged) |
| `"1.0"`, `"1.3"`, `"1.10"` | Accepted, 1.0 rules (VER-3) |
| `"2.0"`, `"1.0.0"`, `"01.0"`, `"1.01"`, `"0.2"`, the number `1.0` | Refused (VER-5) |

| Item | Detail |
|---|---|
| One function per SDK | Python `fidetype.streams.spec.is_supported_spec_version`, TypeScript `isSupportedSpecVersion`, Rust `fidetype::constants::is_supported_spec_version`. The decision field (TD-F3) uses the same function |
| Checks | `NTS-VERSION`, `NeuralTextStream`, the streaming validators, LSL `FEP2-DESC`, WebSocket `FEP4-HANDSHAKE`; JSON schema `nts-v0.1/header` (pattern instead of `const "0.1"`) |
| Writers | Still write `"0.1"` by default. Output does not change |
| Vectors | V53-V61, F48-F54, L33-L35, W39-W43 (21 new). Also closes G-3 (integers written as `0.0` / `1.0` / `2.0`) and G-4 (TD-F2 types) |
| Parity | Python = TypeScript = Rust on 237 vectors (`v0.1` … `fep-0004`) and on the fuzz mutants, seeds 1-6, `--n 30`. After G-1: 279 vectors (`v0.1` … `fep-0005`), 44,196 mutants |

> **Our take:** JSON Schema counts `1.0` as an integer. So GEN-5 (no `1.0` where an integer is required) is stricter than the schemas can say. Only the validators check it. A third-party tool that checks only the schemas will accept `seq: 1.0`.

A second rule, INT-S7 (no-signal reference for configurations that can arm irreversible intents), is stricter on paper only: a stream validator cannot check a configuration (gap G-5).

The parity fuzz also found one binding bug while this work ran: a WebSocket header with a non-object `meta` made the Python trust layer fail, and the SDKs accepted it. All three now refuse it at the header (close 1007); vector W38.

## Main gaps (Appendix C.2)
- G-1, G-2, G-3 and G-4 are closed in RC2. G-1 (2026-11-14): the TypeScript and Rust SDKs run the control profile `fep-0005` with the Python verdicts on all 42 vectors and on 7,560 fuzz mutants (seeds 1-6, `--n 30`).
- Many rules are behaviour that a stream validator cannot see (G-6, G-7, G-9).

> **Our take:** With RC2 a real "1.0" stream validates in all three SDKs. With G-1 closed, all six suite profiles run in all three SDKs; no implementation gap is open. Next: the protobuf schema (P1-02) and the YAML conventions (P1-04). 1.0 Stable needs outside reviewers (P1-07, externally blocked).

## Protobuf schema and generated JSON Schema (P1-02)
Since 2026-11-15 the RC2 data model also exists as proto3 files ([`spec/proto/neuraltextstream/v1/`](../../spec/proto/neuraltextstream/v1/), package `neuraltextstream.v1`). A JSON Schema of one JSON Lines event is generated from them ([`spec/schemas/nts-v1.schema.json`](../../spec/schemas/nts-v1.schema.json)). No rule text changed. RC2 Appendix C has a new informative subsection C.3.

| Item | Detail |
|---|---|
| Coverage | Header with the three declarations, all 13 event types of registry 12.1 plus the LSL `gap` event, timing fields, binding keys |
| Parity | 164 vectors depend on one line (91 accept, 73 reject): 164 match, 0 mismatches. 90 reject vectors fail on rules a one-line schema cannot see; 33 NPZ vectors are out of scope |
| CI | Job `proto`: schema up to date, protoc compiles the files, parity (two validators) |
| Open questions | Q-1 … Q-8 in [`spec/CHANGELOG.md`](../../spec/CHANGELOG.md): all resolved in RC3 (section above) |

Details: [NTS protobuf schema](nts-proto-schema.md).

## Timing evidence: lookahead
Rule MET-4 says that `decoder.lookahead_s` and `latency` MUST be equal. Rule MET-5 says that a causal decoder uses no signal after `frame_times[t] + latency` for frame t. M4-01/02 tested this with our own causal GRU-CTC decoder at lookahead L 0-500 ms ([lookahead vs accuracy and latency](../questions/lookahead-latency-accuracy.md)). The declared `latency` (= `decoder.lookahead_s`) is an upper bound on signal use. It is not the delay that the user sees. A dedicated L 500 ms model gave its phonemes 180 ms earlier than a dedicated L 0 model.

> **Our take:** an optional, informative field for the measured emission delay is a possible NTS 1.1 item (from the same page). It is not a spec change now.

Related: [NTS protobuf schema](nts-proto-schema.md), [FEP process](fep-process.md), [FEP-0007](../../spec/feps/0007-unknown-enum-values.md), [`trust_decision` event](trust-decision.md), [lookahead vs accuracy and latency](../questions/lookahead-latency-accuracy.md), [conformance suite](conformance-suite.md), [TypeScript SDK](typescript-sdk.md), [Rust SDK](rust-sdk.md), [roadmap P1](../questions/roadmap-standard.md#p1-spec-to-10).
