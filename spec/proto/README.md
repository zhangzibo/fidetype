# NTS protobuf schema (proto3) and the generated JSON Schema

| | |
|---|---|
| **Status** | Informative DRAFT (roadmap task P1-02; updated for RC3). It does not change any rule of [NTS 1.0 RC3](../nts-1.0-rc3.md). If this file and the RC3 text differ, the RC3 text wins. |
| **Source of truth** | [`neuraltextstream/v1/*.proto`](neuraltextstream/v1/) (proto3, package `neuraltextstream.v1`) |
| **Generated** | [`../schemas/nts-v1.schema.json`](../schemas/nts-v1.schema.json) (JSON Schema draft 2020-12) by [`tools/proto/gen_jsonschema.py`](../../tools/proto/gen_jsonschema.py). Do not edit it. |
| **Checks (CI job `proto`)** | schema up to date; protoc accepts the files and agrees with the generator; parity with the SDK verdicts on the 304 conformance vectors |
| **Licence** | Apache-2.0 |
| **Model** | The structure of OpenTelemetry's `opentelemetry-proto` (one package per signal and major version, an envelope message, a JSON mapping next to the binary form). No text is copied. |

The roadmap decision "wire formats" ([roadmap P1](../../wiki/questions/roadmap-standard.md#decision-wire-formats)) makes protobuf the canonical schema and keeps JSON Lines, defined by the proto JSON mapping plus a JSON Schema. This folder does that for the full RC3 data model.

## 1. Files

| File | Holds | RC2 sections |
|---|---|---|
| `options.proto` | Custom options that carry the JSON rules (required, nullable, ranges, enum strings, one-line rules, profile of a field) | 4.1, 7.1 |
| `common.proto` | `ScoreSemantics`; the inline groups `Timing` (5.2) and `Binding` (LSL / WebSocket keys) | 4.6, 5.2, 8.2, 8.3 |
| `core.proto` | `Header`, `Frame`, `SegmentEnd`, `End`, `SignalQuality`, `Decision`, `Gap` (LSL extension event) | 3, 4.2–4.6, 8.2.6 |
| `text.proto` | `Hypothesis`, `NBestItem`, `Span`, `DecodeDeclaration` | 4.7 |
| `intent.proto` | `IntentDeclaration`, `IntentSpec`, `Intent`, `IntentCandidate`, `IntentFeedback` | 7.3 |
| `control.proto` | `ControlDeclaration`, `Control`, `ControlEnable`, `Pointer` | 4.8, 7.4 |
| `trust.proto` | `TrustDecision` (text, intent and control profiles) | 6, 7.3.5, 7.4.5 |
| `event.proto` | `Event` (the envelope: one line = one `Event`), `UnknownEvent` | 2.2, 4.1, 12.1 |

Field comments name the rule ids that apply (for example `HDR-6`). Each message comment lists the rules of that object that the schema does **not** express.

## 2. Package and versioning
- **Package `neuraltextstream.v1`, directory `neuraltextstream/v1/`.** `v1` is the NTS major version. It covers every 1.x minor version. The package name uses the format name (NeuralTextStream), not the project name, so a rename of the project does not change it.
- A 1.x minor version adds fields, messages, enum values and `oneof` cases to `v1`. It never removes or renumbers a field (EXT-1). A future 2.0 gets a new package `neuraltextstream.v2` next to `v1`.
- The proto package version is not the runtime version. A stream says its version in `spec_version` (11.2), as before. Binding versions (`nts-lsl/0.1`, `nts-ws/0.1`) stay separate (11.5).

## 3. Field numbers
| Range | Use |
|---|---|
| 1–15 | The most frequent spec fields (one-byte tag on the wire: `t`, `log_probs`, the header core) |
| 16–899 | Other spec fields. Only a spec version (through a FEP) assigns them. In `TrustDecision`: 1–39 all profiles, 40–59 intent, 60–79 control. |
| 900 | `Timing timing` (inline): `t_signal_start`, `t_signal_end`, `t_decoded`, `t_emitted` |
| 1000 | `Binding binding` (inline): `lsl`, `ws`, `ws_seq`, `ws_t_sent`, `ws_t_recv`, `lsl_t`, `t_source`, `lsl_clamped`, `lsl_dropped_before` |
| 2047 | `google.protobuf.Struct ext` (inline): every JSON key that has no field (custom keys, keys of a later minor version) |
| 19000–19999 | Not used (protobuf keeps them) |

`Event` oneof numbers: 1–99 core and profile events (registry 12.1, policy Spec), 1000–1099 binding extension events (`gap` = 1000), 2047 `UnknownEvent`.

Rules: a number is never used again. A removed field goes into `reserved` with its number and name. Every enum has value 0 `<ENUM>_UNSPECIFIED`, which has no JSON form and is never valid. The generator refuses files that break these rules (`lint` in `gen_jsonschema.py`).

## 4. JSON mapping (the "NTS JSON mapping")
The JSON Lines form of RC2 (8.1.1) is older than the proto. It is not the proto3 canonical JSON mapping. The NTS JSON mapping is the canonical mapping with these differences. A writer that converts a proto `Event` to JSON, or JSON to a proto `Event`, follows them.

| Topic | Proto3 canonical JSON | NTS JSON mapping |
|---|---|---|
| Event kind | `{"frame": {...}}` (oneof as a nested object) | **Flat object with a discriminator:** `"type"` = the name of the `Event` oneof case (= the message option `json_type`); the fields of that message are keys of the same object. |
| Key names | lowerCamelCase (`logProbs`) | **The proto field names** (`log_probs`): snake_case, as in RC2. Same as "preserve proto field names". |
| Enums | Enum value names (`VOCAB_TYPE_CHAR`) | **The `json_value` string** of the value (`"char"`, `"norm/s"`, `"COMMIT"`). |
| 64-bit integers | JSON strings | **JSON numbers** without a fraction part or exponent (GEN-5), in −(2^53 − 1) … 2^53 − 1 (GEN-10). The binary form keeps `uint64`; a converter refuses a binary value above 2^53 − 1 when it writes JSON. |
| Inline groups | Nested objects | `Timing`, `Binding` and `ext` (the fields with `json_inline`) are keys of the parent object. |
| JSON null | Default value | Allowed only for fields with `json_nullable` (GEN-9: the field table says "or null"). Binary form (`null_binary`): `unset` (no value; the default), `neg_inf` (log-probabilities: GEN-3) or `nan` (an absent control axis in `control.values`). |
| Presence | — | A field that a table marks "Required" has `json_required` and no `optional` label; every other scalar field is `optional` (it has presence). A JSON writer writes a required nullable field with no value as `null` (for example `p_top1`, `blank_id`). |
| Free objects | `Struct` | `meta`, `params`, `input`, `declaration`, `ws`, `lsl` are `google.protobuf.Struct` (any JSON object). |
| Numbers | NaN and Infinity as strings | **Never** NaN or Infinity in JSON (GEN-2). In the binary form a double MUST be finite, except a log-probability (−inf) and an absent control axis (NaN). |

## 5. Unknown and extension data (forward compatibility)
The proto keeps the forward-compatibility rules of RC2 (GEN-4, VER-3, EXT-1 … EXT-5):

| Case | JSON Lines | Binary proto |
|---|---|---|
| Unknown key (custom key, key of a later 1.x) | The schema allows it (no `additionalProperties: false`). A converter puts it into `ext` and writes it back as a top-level key. | Kept in `ext` (field 2047); or, from a newer `.proto`, kept as an unknown field by the protobuf runtime (proto3 keeps unknown fields). A consumer ignores it. |
| Unknown event type (`acme.calibration_event`, a 1.x type) | The schema allows any object with a string `type`. | `UnknownEvent` (oneof 2047) keeps `type` and the other keys; a newer oneof case arrives as an unknown field. A consumer ignores it. |
| Binding keys | Prefixed `lsl` / `ws` keys (EXT-3) in `Binding` (field 1000). | Same. |
| Unknown enum value | The base schema accepts any string. `Header.known` and `TrustDecision.known` require the known values unless `spec_version` is a newer minor version (VER-7, VER-8). On other events the verdict depends on the header line (a cross-line rule). | proto3 enums are open: the runtime keeps the number. The consumer treats it as the JSON validators treat the string: an error in data of a known version, else unknown with the safe fallback of registry 12.3 (VER-8, VER-10). |
| Profile field on another profile | Typed only on decisions of its profile (option `json_profile`, PRF-5); elsewhere a custom key. | Kept in its field (the number is the same); the consumer ignores it (PRF-5). |

Custom data never gets a field number in a `neuraltextstream.v1` message. It travels as a namespaced key (EXT-2, MET-3), which lands in `ext` or `meta`. This is the role that attributes play in OpenTelemetry.

## 6. Generate and check

```bash
python tools/proto/gen_jsonschema.py            # write spec/schemas/nts-v1.schema.json
python tools/proto/gen_jsonschema.py --check    # exit 1 if it is stale (CI)
python tools/proto/parity.py -v                 # parity with the SDK verdicts on the vectors (CI)
uv run --no-project --with jsonschema==4.26.0 python tools/proto/parity.py --engine jsonschema
uvx --from grpcio-tools==1.85.1 python tools/proto/check_protoc.py   # protoc compiles; parser = protoc
```

- The generator and the parity runner use the Python standard library only. The generator has its own small proto3 parser (`tools/proto/protoparse.py`); `check_protoc.py` compiles the same files with protoc and fails if protoc and the parser disagree on any message, field, enum value or option.
- **protoc is not committed and not required for the generator.** To get it: `pip install grpcio-tools` (contains protoc; `python -m grpc_tools.protoc ...`), or `uvx --from grpcio-tools ...` (no install), or a release binary of protoc or buf from their GitHub releases. Include path: `-Ispec/proto` plus the well-known types (`google/protobuf/*.proto`, shipped with protoc).
- The parity test also runs in pytest (`tests/test_proto_schema.py`).

## 7. Parity with the SDK verdicts
The three SDKs agree on all 304 vectors. `tools/proto/parity.py` takes every JSON object that a vector holds in a JSON form (JSON Lines lines up to `end`, LSL `nts_header` and marker samples, WebSocket NTS messages and `ws_batch` items) and validates it. A vector is "reject" under the schema if one object fails.

| Class of vector | Vectors | Rule |
|---|---|---|
| accept | 99 | The schema MUST accept them: **99 of 99 accepted** |
| reject, class `schema` | 79 | The schema MUST reject them: **79 of 79 rejected**, each for the intended rule |
| reject, other class | 93 | Not compared (the reason is not on one line); the schema accepts all 93 |
| NPZ (not a JSON form) | 33 | Out of scope |

**Result: 178 compared, 178 match, 0 mismatches** (built-in validator and `jsonschema` 4.26.0 give the same verdicts on all 304 vectors). RC3 moved F04 (SEG-5) and I22 (INT-F1) to class cross-line: an unknown value on an event that is not the header is an error only under a header of a known version (VER-7). The class of every reject vector is in `REJECT_CLASS` in `parity.py`.

## 8. What the schema cannot express
These rules stay in the SDK validators. "Vectors" are the reject vectors of that class.

| Class | Why a one-line schema cannot see it | Rules | Vectors |
|---|---|---|---|
| cross-line | Needs other lines: the header (V, declarations, the governing version of VER-7), the order or the uniqueness in a stream or session | VER-7 for events that are not the header (F04, I22), HDR-1 (first line), FRM-1 (V values), TIM-2, SEG-2, SEG-4 (order), HYP-1 id unique, TD-4 … TD-7, TD-11, INT-D5, INT-E1, INT-E2 (declared), INT-E5, INT-T4, INT-T6, CTL-1 … CTL-4 (dims, uncertainty), CTL-12, CTL-T5, WS-S1 (header first), WS-R1 | 30 |
| cross-field | Links two fields of one object in a way JSON Schema has no keyword for (equal lengths, index < length, order of values, unique values of one key, membership in another field) | HDR-6 (blank_id < V), EVD-1 count, FRM-5 / sparse lengths and `top_ids < V`, TIM-4, INT-D1 unique ids, INT-E2 twice, INT-E4 ranking, CTL-D3 (declared, role not null), CTL-4 (null only with `absent`), PTR-1 absolute range, `raw` length = `velocity` length, MET-4 | 10 |
| arithmetic | A computed value | FRM-3 (log-sum-exp, also the empty rows of HDR-12), INT-E3 (sum ≤ 1) | 7 |
| trust | Semantic rules of a trust layer (they stay in the SDKs by design); some also compare fields (INT-S3 p ≥ threshold, CTL-S3 ‖v‖ ≤ v_max) | TD-9, TD-12, INT-S1 … INT-S10, CTL-S1 … CTL-S8, VER-10 (E24) | 18 |
| lexical | JSON Schema compares JSON numbers, so `1.0` is an integer | GEN-5 | 3 (V61, F50, W43) |
| parse | No JSON object to validate | GEN-2 (NaN token, not JSON), LSL-D1, LSL-X2, WS-F2 | 4 |
| binding | Transport rules: stream info, framing, sequence numbers, auth | LSL-F*, LSL-E1, LSL-D3, LSL-C5, LSL-V1, LSL-X1, WS-H2, WS-F1, WS-Q1 (required `ws_seq`), WS-Q4, WS-D1, WS-T2, WS-V1 | 21 |
| content | Behaviour or content, not form (no vector: gaps G-6, G-7 of Appendix C) | GEN-1, SQ-2, DEC-1, DEC-5, EVD-2, DCL-2 … DCL-7, MET-1 … MET-6 (the `meta` conventions: planned as semconv YAML, roadmap P1-04), SEC-1 … SEC-8 | — |

The schema **does** express (with the vectors that test it): HDR-1 required keys, HDR-2/VER-3/VER-5 (`spec_version` pattern), HDR-3, HDR-4, HDR-5, HDR-6 (type), HDR-7 … HDR-11, FRM-1/FRM-2 (dense or sparse form), FRM-4 (JSON has no NaN or +inf), GEN-2 (an object with a string `type`), GEN-3, SEG-4 (type), SEG-5, SQ-1, DEC-2 … DEC-4, HYP-1, EVD-1 (values), EVD-3, EVD-4, DCL-1, PTR-1 (types, `values` length = `dims`), TD-F1 … TD-F3, TD-8, PRF-4, INT-D1 (non-null role), INT-D2 … INT-D4, INT-E3 (per-score rules), INT-E7, INT-F1, INT-T1 … INT-T3, CTL-D1, CTL-D2, CTL-D3 (an `intent_declaration` is present), CTL-4 (types, `std` > 0), CTL-E1, CTL-T1 … CTL-T4, CTL-T8, INT-T7, WS-Q1 (`ws_seq` is an integer ≥ 1 when present), GEN-10 (F60, W44), TD-F2 `declaration` (F62), VER-7 for the header and decisions (V67, F59, D23, E23), PRF-5.

## 9. Where the schema is stricter than the SDK validators
No vector is affected. Each item is a place where the RC3 text gives a type that the SDK validators do not check yet (gap G-12 of Appendix C).
- (Fixed in RC3: profile fields are now typed per profile, PRF-5. `"tick": "x"` on a text decision is a custom key in the schema too.)
- `segment_end.reason` (SEG-6), `trust_decision.reason`, intent `vocab_id`: typed by the schema only.
- `control.absent: null` is valid (GEN-9; the SDKs read it as absent), but a repeated proto field has no null form, so the schema refuses it. No vector has it.
- `hypothesis.t_start` / `t_end`, `nbest[].spans`, `signal_quality.channels`, `pointer.score_semantics`, `decision.score_range` for every semantics: typed by the schema only.
- `logp_acoustic` / `logp_lm`: the schema uses `maximum 0` (EVD-4 text); the validators allow 1e-9 of tolerance.

## 10. Relation to the hand-written schemas
The hand-written schemas in [`../schemas/nts-v0.1/`](../schemas/nts-v0.1/) and `../schemas/fep-000N/` are **not changed**. The TypeScript SDK still embeds them (`npm run gen:schemas`). The generated `nts-v1.schema.json` is one file for all event types; the generator writes it at the top of `schemas/`, outside the folders that the TypeScript generator reads. (The roadmap named `spec/schema/nts-v1.schema.json`; the existing `schemas/` folder is used instead.) Known differences from the hand-written files: the control decision `p_top1` is "number in [0, 1] or null" here (the SDKs check that; the hand-written file says `null` only), and the generated schema adds the one-line rules INT-D1, INT-D3, INT-D4, CTL-D1 (units fit quantity), CTL-D2, CTL-D3 (presence), CTL-T3 and PTR-1. Whether the generated file replaces the hand-written ones is task P1-06.

## 11. Not in this task
- The binary framing of a file or a socket (length-delimited `Event` messages), a gRPC service and protobuf frames over WebSocket: bindings, roadmap P1-05.
- The WebSocket control messages (`ws_welcome`, `ws_ack`, `ws_batch`, …) and LSL stream infos: binding records, not NTS events (WS-M1). The parity runner skips them, except the events inside a `ws_batch`.
- The NPZ form (8.1.2): read only, frame core only (FIL-6).
- The `meta` conventions of 3.4 as machine-readable rules: roadmap P1-04, now in [`../semconv/`](../semconv/registry.md) (the check compares the registry containers with the proto `Struct` fields `Header.meta`, `TrustDecision.input` and `TrustDecision.declaration`).

## 12. Open spec questions found by the proto
They are recorded in [CHANGELOG.md](../CHANGELOG.md) (RC2 section, "Open questions (P1-02)"). **All eight are resolved in RC3** (section 1.6 of [nts-1.0-rc3.md](../nts-1.0-rc3.md)): Q-1 GEN-9, Q-2 SEG-6 / LSL-G3, Q-3 CTL-T9, Q-4 TD-F2 / TD-13, Q-5 GEN-10, Q-6 PRF-5, Q-7 VER-6 … VER-10, Q-8 INT-T7 / CTL-T8.
