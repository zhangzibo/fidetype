# Fidetype specifications

This folder holds the written specifications of Fidetype. A spec is the normative contract. The Python code in `src/fidetype/` is the reference implementation.

| Spec | Version | Status | What it defines |
|---|---|---|---|
| [NeuralTextStream](neuraltextstream-v0.1.md) | 0.1 | Development (current release) | The output of any neural input decoder: a probability distribution over a declared vocabulary at each time frame (the core), plus Development event kinds for decisions, text hypotheses, pointer movement and signal quality |
| [NeuralTextStream 1.0 RC4](nts-1.0-rc4.md) | 1.0 RC4 | **DRAFT for public comment** (not final; current RC) | The same document as RC3, plus: optional fields have their table type and all three validators check it (GEN-11, gap G-12 closed); the YAML semantic-convention registry is normative (MET-10); planned modality namespaces reserved; non-empty string keys; open and closed value lists; units (SC-2 … SC-8, FEP-0008). Amendment of 2026-11-16: modality keys for `emg`, `meg`, `implant` (MET-11, FEP-0009) and gap G-13 part b (schema accepts control `absent: null`). Changes: section 1.6 |
| [NeuralTextStream 1.0 RC3](nts-1.0-rc3.md) | 1.0 RC3 | Superseded by RC4 (kept unchanged as the record) | The same document as RC2, plus the answers to the protobuf open questions Q-1 … Q-8: unknown enumeration values with a safe fallback (FEP-0007), the JSON null and integer-range rules, profile-scoped fields, open reason codes, gap fields, rule ids for two SDK checks. Changes: section 1.6 |
| [NeuralTextStream 1.0 RC2](nts-1.0-rc2.md) | 1.0 RC2 | Superseded by RC3 (kept unchanged as the record) | One document: v0.1 + FEP-0001 … FEP-0005 (core data model, header, events, timing, trust decisions, text / intent / control profiles, JSON Lines / NPZ / LSL / WebSocket bindings, conformance levels, security and privacy, versioning, registries). Appendices: open-question resolutions, migration from 0.1, conformance traceability with gaps |
| [NeuralTextStream 1.0 RC1](nts-1.0-rc1.md) | 1.0 RC1 | Superseded by RC2 (kept unchanged as the record) | The first release candidate. RC2 changes no rule text; it closes gaps G-2, G-3 and G-4 |

**NTS 1.0 RC4 (2026-11-15) is a draft.** Comment on it with an issue or a Discussion (label `spec-1.0-rc`; name the rule id, for example `TD-9`). 1.0 Stable needs outside review by at least two decoder groups. Until then, claim "NTS 1.0 RC4 (draft)" only. Changes: [CHANGELOG.md](CHANGELOG.md).

## Why a written spec
- Any decoder, from any lab or company, can emit the same format.
- Any consumer (the Fidetype trust layer, a UI, a benchmark) can read it without knowing the decoder.
- The spec does not depend on one modality (EMG, EEG, MEG, implants) or one vocabulary (characters, keys, words, phonemes, commands).

The model is OpenTelemetry (a data model plus semantic conventions) and BIDS (80/20, adoption first).

## Conformance
Check a producer or a consumer with the conformance suite (levels core, trust-ready, provenance; each check cites its spec clause):

```bash
python -m fidetype.conformance check my_stream.npz --level trust-ready
python -m fidetype.conformance consumer --cmd "my-reader {path}"   # exit 0 = accept
```

The golden vectors are in [`conformance/v0.1/`](conformance/v0.1/). Details: [wiki/concepts/conformance-suite.md](../wiki/concepts/conformance-suite.md).

The TypeScript SDK ([`sdk/typescript/`](../sdk/typescript/README.md)) runs the same vectors for every profile and gives the same verdict as the Python reference (`npm run cross-check`). The JSON schemas in [`schemas/`](schemas/) are structural; its TypeScript types are generated from them.

**Protobuf source of truth (P1-02, draft):** [`proto/neuraltextstream/v1/*.proto`](proto/) describe the full 1.0 RC2 data model (proto3, package `neuraltextstream.v1`). [`schemas/nts-v1.schema.json`](schemas/nts-v1.schema.json) is generated from them (`python tools/proto/gen_jsonschema.py`) and gives the SDK verdict on every vector that fails or passes on one line (178 of 178). Mapping rules, the rules a schema cannot express and the open questions: [proto/README.md](proto/README.md).

**Semantic-convention registry (P1-04; normative since RC4, MET-10):** [`semconv/`](semconv/) holds the key conventions of RC4 as YAML: the 24 `meta` keys of section 3.4 and the recommended `trust_decision` `input` (6.1.1) and `declaration` (6.1.2) keys, each with type, unit, requirement level per conformance level, stability and rule ids. The reference page [semconv/registry.md](semconv/registry.md) is generated (`python tools/semconv/semconv.py`). CI job `semconv` checks that the YAML agrees with the spec tables, the proto files, the generated JSON Schema, the three SDK validators and the conformance vectors. The modality namespaces (`emg.*`, `eeg.*`, ...) are reserved but have no keys yet (SC-1: deferred to a FEP with real-producer evidence). How to use it: [docs/semconv.md](../docs/semconv.md).

Opt-in profiles test draft FEPs on top of v0.1. They do not change the v0.1 levels or vectors:

```bash
fidetype conformance --profile fep-0001     # streaming trust events: vectors in conformance/fep-0001/
fidetype conformance --profile fep-0002     # NTS over LSL: scenario vectors in conformance/fep-0002/
fidetype conformance --profile fep-0003     # output profiles + discrete intent events: vectors in conformance/fep-0003/
fidetype conformance --profile fep-0004     # NTS over WebSocket: scenario vectors in conformance/fep-0004/
fidetype conformance --profile fep-0005     # control profile: vectors in conformance/fep-0005/ (Python, TypeScript, Rust)
```

The 1.0 rule ids map to these checks and vectors in [Appendix C](nts-1.0-rc4.md#appendix-c-conformance-traceability). RC4: all three SDKs check the type of every optional field of the spec tables (GEN-11; vectors V69-V82, F63-F66, D24-D26, I25, C25, E25-E27) and warn about a custom key in a planned modality namespace (MET-3). RC3: in data of a newer minor version (`"1.1"` …) all three SDKs accept unknown enumeration values and never act on them (VER-8, VER-10; vectors V66-V68, F57-F59, I24, D22, D23, C24, E22-E24); integers above 2^53 - 1 are refused (GEN-10; F60, F61, W44). All three SDKs accept a header `spec_version` of `"0.1"`, `"1.0"` or `"1.<minor>"` and refuse other values (RC2, gap G-2; vectors V53-V60, F48-F49, L33-L35, W39-W42). One stricter rule is also in the validators of all three SDKs: a `trust_decision` with `"spec_version": "1.x"` MUST NOT be a final COMMIT with an empty committed text (rule TD-9; vectors F41-F47). Decisions without `spec_version`, or with `"0.1"`, keep the 0.1 rule (a SHOULD NOT).

## Proposals (FEPs)
FEPs 0001-0005 and 0007-0009 are folded into [NTS 1.0 RC4](nts-1.0-rc4.md). Their open questions are answered or deferred in [Appendix A](nts-1.0-rc4.md#appendix-a-open-questions-resolutions-and-deferrals). The FEP lifecycle (Draft, Under review, Accepted, Implemented, Final, Rejected / Withdrawn) is in [section 11.6](nts-1.0-rc4.md#116-change-process-and-fep-lifecycle).

| FEP | Title | Status | Conformance profile |
|---|---|---|---|
| [0001](feps/0001-streaming-trust-events.md) | Streaming trust events (`segment_end`, evidence fields, decode declaration, `trust_decision`) | Draft (in 1.0 RC4) | `fep-0001` (66 vectors; F41-F47 test rule TD-9 and `trust_decision.spec_version`; F48-F54 test 1.x input headers, GEN-5 and TD-F2 types; F55-F56 test TD-12, blank candidates; F57-F62 test RC3: VER-8, GEN-10, `declaration`; F63-F66 test RC4: GEN-11) |
| [0002](feps/0002-nts-over-lsl.md) | NeuralTextStream over LSL (binding `nts-lsl/0.1`) | Draft (in 1.0 RC4) | `fep-0002` (35 vectors; L33-L35 test 1.x `nts_header` versions) |
| [0003](feps/0003-intent-events.md) | Output profiles (core, text, intent, control) and discrete intent events (risk classes, confirmation, undo, `intent_feedback`, intent `trust_decision`) | Draft (in 1.0 RC4) | `fep-0003` (51 vectors; I24, D22, D23 test VER-8; I25, D24-D26 test GEN-11); JSON schemas in `schemas/fep-0003/` |
| [0004](feps/0004-nts-over-websocket.md) | NeuralTextStream over WebSocket (binding `nts-ws/0.1`: framing, `ws_seq` order and gaps, resume, back-pressure, auth hook, decisions channel) | Draft (in 1.0 RC4) | `fep-0004` (44 vectors; W38 tests the RC1 header check; W39-W43 test 1.x header versions and GEN-5; W44 tests GEN-10) |
| [0005](feps/0005-control-events.md) | Continuous-control events (control profile: `control_declaration` units / frame / rate / uncertainty, `control`, `control_enable`, control `trust_decision` with gain / hold / stop, safety rules) | Draft (in 1.0 RC4) | `fep-0005` (52 vectors; C24, E22-E24 test VER-8 and VER-10; C25, E25-E27 test GEN-11; Python, TypeScript, Rust) |
| [0007](feps/0007-unknown-enum-values.md) | Unknown enumeration values: version-gated acceptance with a safe fallback per enumeration (forward compatibility of registries) | Draft (in 1.0 RC3, section 11.2.1) | vectors in `v0.1`, `fep-0001`, `fep-0003`, `fep-0005` |
| [0008](feps/0008-optional-field-types-and-semconv.md) | Optional field types (GEN-11, gap G-12) and the semantic-convention registry (normative YAML, planned namespaces reserved, non-empty strings, open and closed lists, units; SC-2 … SC-8) | Draft (in 1.0 RC4, sections 1.6, 3.4, A.8) | vectors in `v0.1`, `fep-0001`, `fep-0003`, `fep-0005` |
| [0009](feps/0009-modality-semantic-conventions.md) | Modality keys for `emg`, `meg`, `implant` from producer evidence (MET-11; SC-1 partly; SC-9 open for `eeg`, `fnirs`) | Draft (in the 1.0 RC4 amendment of 2026-11-16, sections 1.6, 3.4, 12.5, A.8) | V83 … V87 in `v0.1` |
| [0006](feps/0006-collector.md) | The collector (reference architecture, not a format change): receivers → processors → exporters, pipelines, TOML / JSON configuration, loss and privacy rules, health and metrics | Draft (not in 1.0; reference v0 `fidetype collector`) | - |

## Stability levels
| Level | Meaning |
|---|---|
| Development | Can change in any release |
| Stable | No breaking change within a major version |
| Deprecated | Still works. Removed after its support window |
| Removed | No longer in the spec |

## How to change a spec
1. Open an issue or a Discussion to test the idea.
2. Copy [`feps/0000-template.md`](feps/0000-template.md) to `feps/NNNN-short-title.md`. Use the next free number.
3. Open a pull request with the FEP. The process is in [GOVERNANCE.md](../GOVERNANCE.md#4-spec-changes-feps).
4. When the FEP is accepted, update the spec, the reference implementation and the changelog in the same release.

## Layout
```
spec/
  README.md                   this file
  neuraltextstream-v0.1.md    the NeuralTextStream spec, v0.1 (current release)
  nts-1.0-rc4.md              NTS 1.0 Release Candidate 4 (DRAFT for public comment; current RC)
  nts-1.0-rc3.md              NTS 1.0 Release Candidate 3 (superseded by RC4; kept as the record)
  nts-1.0-rc2.md              NTS 1.0 Release Candidate 2 (superseded by RC3; kept as the record)
  nts-1.0-rc1.md              NTS 1.0 Release Candidate 1 (superseded by RC2; kept as the record)
  CHANGELOG.md                spec changelog
  conformance/v0.1/           golden test vectors (manifest.json + small synthetic .npz / .jsonl files)
  conformance/fep-0001/       golden vectors of the opt-in FEP-0001 profile (.jsonl)
  conformance/fep-0002/       golden vectors of the opt-in FEP-0002 profile (LSL scenarios, .json)
  conformance/fep-0003/       golden vectors of the opt-in FEP-0003 profile (.jsonl)
  conformance/fep-0004/       golden vectors of the opt-in FEP-0004 profile (WebSocket scenarios, .json)
  conformance/fep-0005/       golden vectors of the opt-in FEP-0005 profile (.jsonl)
  proto/neuraltextstream/v1/  proto3 files of the 1.0 data model (source of truth, P1-02); proto/README.md = mapping rules
  schemas/nts-v1.schema.json  JSON Schema of one 1.0 JSON Lines event, GENERATED from proto/ (do not edit)
  schemas/nts-v0.1/           JSON schemas (draft 2020-12, structural) of the v0.1 JSON Lines events
  schemas/fep-0001/           JSON schemas of the FEP-0001 objects (segment_end, n-best item, decode_declaration, trust_decision)
  schemas/fep-0003/           JSON schemas (draft 2020-12) of the FEP-0003 objects
  schemas/fep-0005/           JSON schemas (draft 2020-12) of the FEP-0005 objects
  feps/                       Fidetype Enhancement Proposals
    0000-template.md          the template for a new FEP
    0001-streaming-trust-events.md
    0002-nts-over-lsl.md
    0003-intent-events.md
    0004-nts-over-websocket.md
    0005-control-events.md
    0006-collector.md
    0007-unknown-enum-values.md
    0008-optional-field-types-and-semconv.md
    0009-modality-semantic-conventions.md
```
