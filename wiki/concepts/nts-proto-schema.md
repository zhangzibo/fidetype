---
title: NTS protobuf schema and generated JSON Schema (P1-02)
type: concept
tags: [spec, neuraltextstream, protobuf, json-schema, wire-format, conformance, p1]
sources: []
updated: 2026-11-15
---

# NTS protobuf schema and generated JSON Schema

Roadmap task P1-02 (done 2026-11-15). The [roadmap decision "wire formats"](../questions/roadmap-standard.md#decision-wire-formats) makes protobuf (proto3) the source of truth of the NTS data model. JSON Lines stays, defined by a JSON mapping plus a JSON Schema. Now both exist. The normative text is still [NTS 1.0 RC2](../../spec/nts-1.0-rc2.md) ([NTS specification](nts-spec.md)). The proto work changes no rule.

| Part | Where |
|---|---|
| Proto3 files (source of truth) | [`spec/proto/neuraltextstream/v1/`](../../spec/proto/neuraltextstream/v1/), package `neuraltextstream.v1`, 8 files, 25 messages, 19 enums |
| Mapping rules (informative) | [`spec/proto/README.md`](../../spec/proto/README.md) |
| Generated JSON Schema | [`spec/schemas/nts-v1.schema.json`](../../spec/schemas/nts-v1.schema.json) (draft 2020-12, one line = one event) |
| Generator, parser, validator, parity | [`tools/proto/`](../../tools/proto/) (Python standard library only) |
| Test and CI | `tests/test_proto_schema.py`; CI job `proto` in `.github/workflows/tests.yml` |

## How it fits together

| Step | What happens | Check |
|---|---|---|
| 1. Write `.proto` | Fields, rule ids in comments, JSON options (required, nullable, ranges, enum strings, one-line rules) | protoc must accept the files (`check_protoc.py`, grpcio-tools; protoc is not committed) |
| 2. Generate | `gen_jsonschema.py` reads the files with a small parser and writes the schema | The parser must equal protoc on every message, field, enum value and option |
| 3. Commit | The schema file is committed | `--check`: CI fails if the file is stale |
| 4. Compare | `parity.py` validates every JSON object of the 287 vectors | 0 mismatches with the SDK verdicts; same result with the `jsonschema` library |

The structure follows OpenTelemetry's `opentelemetry-proto` ([OTel case study](../sources/case-study-opentelemetry.md)): one package per major version, one envelope message, a JSON mapping next to the binary form. No text is copied.

## Design decisions

| Topic | Decision |
|---|---|
| Package | `neuraltextstream.v1` = NTS major 1, every 1.x minor. 2.0 gets `v2`. The runtime version stays `spec_version` |
| Envelope | `Event { oneof body { Header header = 1; Frame frame = 2; ... } }`. The oneof case name is the JSON `type` |
| Field numbers | 1-15 frequent fields; 16-899 spec fields; 900 `Timing`, 1000 `Binding`, 2047 `ext` (inline groups); never reused |
| JSON keys | The proto field names (snake_case), not lowerCamelCase |
| Enums | JSON strings from the option `json_value` (`"norm/s"`, `"COMMIT"`); value 0 `*_UNSPECIFIED` is never valid |
| Integers | JSON numbers (not strings, as proto3 JSON would write 64-bit values) |
| null | Only where a field allows it. Binary form: no value, or `-inf` for log-probabilities (GEN-3), or NaN for an absent control axis |
| Unknown keys | Allowed by the schema; kept in `ext` (field 2047) in the binary form (GEN-4) |
| Unknown types | Allowed by the schema; `UnknownEvent` in the binary form |
| Custom data | Never a new field number in a `v1` message. Namespaced keys only (EXT-2), like OTel attributes |
| One-line rules | Rules that link fields of one object (for example DEC-4, INT-D3, CTL-T3) are JSON Schema fragments in the message option `json_rule`, each with its rule id |

## Parity with the SDKs

| Vectors | Count | Schema result |
|---|---|---|
| Accept | 91 | 91 accepted |
| Reject on a one-line rule (class `schema`) | 73 | 73 rejected, each for the intended rule |
| Reject on another ground (not compared) | 90 | all accepted: cross-line 28, binding 21, trust 17, cross-field 10, arithmetic 7, parse 4, lexical 3 |
| NPZ (not a JSON form) | 33 | out of scope |

Result: **164 compared, 164 match, 0 mismatches.** The built-in validator and `jsonschema` 4.26.0 agree on all 287 vectors.

## What a schema cannot express
- **Other lines:** header first (HDR-1), V from the header (FRM-1), time order (TIM-2, SEG-4), unique ids, decision order (TD-5 … TD-7).
- **Two fields in a way JSON Schema has no keyword for:** `blank_id < len(vocab)` (HDR-6), `char_confidences` count (EVD-1), ranking (INT-E4), timing order (TIM-4).
- **Arithmetic:** log-sum-exp (FRM-3), score sums (INT-E3).
- **Trust rules (by design):** TD-9, TD-12, INT-S*, CTL-S*.
- **Spelling of a number:** GEN-5. JSON Schema counts `1.0` as an integer (V61, F50, W43).
- **Transport:** LSL stream info, WebSocket framing, sequence numbers, auth.

> **Our take:** the schema is a good first gate for third-party tools: it catches every type, enum, range and required-key error that the vectors test. It is not a validator. A tool that checks only the schema accepts streams that do not normalise or that break the trust rules. The conformance suite stays the normative validator (resolution 12-A9).

## Open spec questions found (Q-1 … Q-8)
Recorded in [`spec/CHANGELOG.md`](../../spec/CHANGELOG.md) (RC2, "Open questions (P1-02)"). No rule text changed.

| Id | Question |
|---|---|
| Q-1 | JSON null in optional fields such as `frame_period`: the SDKs read it as absent; the spec does not say so |
| Q-2 | LSL adds `reason` to `segment_end` without a binding prefix (EXT-3); the `gap` event has no field table |
| Q-3 | Control `reasons`: closed list (registry) or any string (SDKs)? |
| Q-4 | `trust_decision.declaration` and `input` have no field tables |
| Q-5 | Integer range: no upper bound; JSON numbers above 2^53 − 1 are not portable |
| Q-6 | A field of another profile on a decision: custom key or typed field? |
| Q-7 | New enum values in a minor version vs consumers that refuse unknown values |
| Q-8 | Two SDK format checks without rule text (`radius` needs `level`; `confirm_required` only on OFFER) |

> **Our take:** Q-7 is the most important one for 1.0 Stable. The compatibility promise (11.3) says a 1.0 reader accepts 1.x data, but a new `vocab_type` or `action` value would make it refuse the stream. proto3 enums are open (the binary form keeps an unknown number), so the proto does not decide it. NTS needs one rule per enum: refuse, ignore the event, or read the value as `other`.

## Not in P1-02
- Binary framing (length-delimited files), gRPC, protobuf over WebSocket: bindings, P1-05.
- `meta` conventions as machine-readable rules: P1-04 (semconv YAML).
- Whether the generated schema replaces the hand-written `spec/schemas/nts-v0.1/` and `fep-000N/` files (the TypeScript SDK embeds those): P1-06.

Related: [NTS specification](nts-spec.md), [conformance suite](conformance-suite.md), [TypeScript SDK](typescript-sdk.md), [Rust SDK](rust-sdk.md), [`trust_decision` event](trust-decision.md), [roadmap P1](../questions/roadmap-standard.md#p1-spec-to-10).
