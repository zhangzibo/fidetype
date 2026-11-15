---
title: NeuralTextStream specification (versions, 1.0 RC2)
type: concept
tags: [spec, neuraltextstream, standard, versioning, conformance, p1]
sources: []
updated: 2026-11-14
---

# NeuralTextStream specification

The written contract of Fidetype. A decoder writes a NeuralTextStream (NTS); a trust layer reads it and writes `trust_decision` events; a bridge acts only on final decisions.

| Version | File | Status |
|---|---|---|
| 0.1 | [`spec/neuraltextstream-v0.1.md`](../../spec/neuraltextstream-v0.1.md) | Current release (Development) |
| FEP-0001 … FEP-0005 | [`spec/feps/`](../../spec/feps/) | Draft proposals on top of 0.1 |
| **1.0 RC2** | [`spec/nts-1.0-rc2.md`](../../spec/nts-1.0-rc2.md) | **DRAFT for public comment** (2026-11-14). Not final. Current RC |
| 1.0 RC1 | [`spec/nts-1.0-rc1.md`](../../spec/nts-1.0-rc1.md) | Superseded by RC2 (same rule text); kept as the record |

Changelog: [`spec/CHANGELOG.md`](../../spec/CHANGELOG.md). Index of specs and FEPs: [`spec/README.md`](../../spec/README.md).

Tools around the spec: the [collector](collector.md) (draft FEP-0006, P3) receives NTS from files and WebSocket, runs the trust layer and the privacy filter, and exports decision logs. It changes no field of NTS.

## 1.0 RC2 in one table
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

## Timing evidence: lookahead
Rule MET-4 says that `decoder.lookahead_s` and `latency` MUST be equal. Rule MET-5 says that a causal decoder uses no signal after `frame_times[t] + latency` for frame t. M4-01/02 tested this with our own causal GRU-CTC decoder at lookahead L 0-500 ms ([lookahead vs accuracy and latency](../questions/lookahead-latency-accuracy.md)). The declared `latency` (= `decoder.lookahead_s`) is an upper bound on signal use. It is not the delay that the user sees. A dedicated L 500 ms model gave its phonemes 180 ms earlier than a dedicated L 0 model.

> **Our take:** an optional, informative field for the measured emission delay is a possible NTS 1.1 item (from the same page). It is not a spec change now.

Related: [lookahead vs accuracy and latency](../questions/lookahead-latency-accuracy.md), [conformance suite](conformance-suite.md), [TypeScript SDK](typescript-sdk.md), [Rust SDK](rust-sdk.md), [roadmap P1](../questions/roadmap-standard.md#p1-spec-to-10).
