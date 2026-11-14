# Spec changelog

All notable changes to the specifications in `spec/`. Newest first. Earlier v0.1 entries are also in [section 11 of the v0.1 spec](neuraltextstream-v0.1.md#11-changelog).

## [1.0 RC2, DRAFT] 2026-11-14
**Status: draft for public comment. Not final.** Document: [nts-1.0-rc2.md](nts-1.0-rc2.md). RC1 stays unchanged as the record.

### Changed (implementation; no rule text changed)
- **Gap G-2 closed (HDR-2, VER-1, VER-3, VER-5, LSL-D2):** a header `spec_version` of `"0.1"`, `"1.0"` or `"1.<minor>"` (minor: `0` or digits without a leading zero) is accepted. Every other value is refused, for example `"2.0"`, `"1.0.0"`, `"01.0"`, `"1.01"` or the number `1.0`. This applies to:
  - Python: `NTS-VERSION`, `NeuralTextStream`, the streaming trust layer header check, the LSL `nts_header` check (`FEP2-DESC`) and the WebSocket header check (`FEP4-HANDSHAKE`). One shared function: `fidetype.streams.spec.is_supported_spec_version`.
  - TypeScript: the same checks, through `isSupportedSpecVersion` (exported).
  - Rust: the same checks, through `fidetype::constants::is_supported_spec_version`.
  - JSON schema `nts-v0.1/header`: `spec_version` is a string with the pattern `^(0\.1|1\.(0|[1-9][0-9]*))$` (was `const "0.1"`). The TypeScript generated types follow.
- 0.1 behaviour is unchanged: `"0.1"` streams give the same verdicts, and `"0.2"` is still refused (V17). The writers still write `"0.1"` by default.

### Added (vectors)
- `v0.1` V53-V61 (61 vectors now, from 52): accept `"1.0"`, `"1.3"` and an NPZ `version` `"1.0"`; reject `"2.0"`, `"1.0.0"`, `"1.01"`, `"01.0"`, the number `1.0`; reject `blank_id: 0.0` (G-3).
- `fep-0001` F48-F54 (54 now, from 47): accept an input stream with a `"1.0"` header; reject a `"2.0"` header; reject `seq: 1.0` (G-3); reject the wrong types of `session`, `config_id`, `input`, `latency_s` (G-4).
- `fep-0002` L33-L35 (35 now, from 32): `nts_header` `"1.0"` accepted, `"2.0"` and `"1.01"` refused.
- `fep-0004` W39-W43 (43 now, from 38): header `"1.0"` and `"1.3"` accepted, `"2.0"` and `"1.0.0"` refused; `ws_seq: 2.0` refused (G-3).
- **Gaps G-3 and G-4 closed.** The three SDKs already refused these inputs (no check changed). JSON Schema counts `1.0` as an integer, so only the validators check GEN-5.

### Parity
- Python = TypeScript = Rust on all 237 vectors of `v0.1` … `fep-0004` (`cross-check.mjs --rust`), and on the fuzz mutants (`fuzz-parity.mjs`, seeds 1-6, `--n 30`). `fep-0005` is still Python only (gap G-1).

## [1.0 RC1, DRAFT] 2026-11-14
**Status: draft for public comment. Not final.** Document: [nts-1.0-rc1.md](nts-1.0-rc1.md).

### Added
- One document for NTS 1.0: v0.1 plus FEP-0001 (streaming trust events), FEP-0002 (LSL binding `nts-lsl/0.1`), FEP-0003 (output profiles: core, text, intent), FEP-0004 (WebSocket binding `nts-ws/0.1`) and FEP-0005 (control profile).
- Rule ids for every normative statement (for example `TD-9`), and a traceability table from each id to the conformance checks and vectors (Appendix C), with 11 gap groups (G-1 … G-11).
- `trust_decision.spec_version` (section 11.2): `"0.1"` or `"1.<minor>"`; absent = `"0.1"`. Required for 1.0 trust layers. In all three SDK validators (`FEP1-TD-FORMAT`) and in the trust-decision JSON schemas of `fep-0001`, `fep-0003` and `fep-0005`.
- Conformance levels and classes (producer, consumer, trust layer, bridge, binding), conformance claims (section 9).
- Security and privacy section (10): neural-data sensitivity, no raw signal in the stream, personal data, leakage, provenance and audit fields, transport security.
- Versioning and extension rules (11): semver, compatibility promise, extension rules, binding versions, FEP lifecycle, SDK and spec compatibility matrix.
- Registries (12): event types, profile names, enumerations, vocabulary and intent namespaces, convention namespaces, binding versions, WebSocket close and error codes, configuration id prefixes.
- Appendix A: resolution or deferral (to 1.1) of every open question of v0.1 section 10 (items 1-11, A1-A10) and of FEP-0001 … FEP-0005.
- Appendix B: migration from 0.1.
- Vectors `fep-0001` F41-F47 (47 vectors now, from 40).

### Changed (stricter)
- **TD-9 (FEP-0001 section 3 rule 9):** a final text COMMIT with a blank committed text is a **MUST NOT** for decisions with `spec_version` 1.x. Decisions without `spec_version`, or with `"0.1"`, keep the 0.1 SHOULD NOT. Evidence: M2-18 (320 empty COMMITs on 400 no-signal T12 streams), FEP-0003 (no null-intent COMMIT), FEP-0005 (no motion on no-signal input).
- **INT-S7 (FEP-0003 question 4):** a configuration that can arm irreversible intents MUST be fitted with a no-signal reference. Evidence: P12 (0.371 of zero-input presses acted without it, 0 with it). A configuration rule; no stream check (gap G-5).
- **WebSocket header:** a header whose `meta` is present and not a JSON object is refused (close 1007, `bad_header`), in Python, TypeScript and Rust. This applies v0.1 rule 5.1.7 at the binding. Before, the Python reference failed later in the trust layer and the SDKs accepted the stream (found by the parity fuzz, seed 5). New vector `fep-0004` W38 (38 vectors now, from 37).

### Changed (looser or clarified)
- A 1.x consumer accepts every `"1.<minor>"` (resolution A6). Implemented for decisions; headers: gap G-2.
- Written down from SDK behaviour: integers have no fraction or exponent (GEN-5); empty JSON Lines lines are ignored (GEN-6); lines after `end` are ignored (GEN-7).
- No frame revisions (FRM-6); V = 0 only without frames (HDR-12); `vocab_type` describes meaning (HDR-14); reserved convention namespaces (MET-3); `decoder.causal` with absent `latency` = lookahead 0 (MET-5); any numeric NPZ dtype is read (FIL-5); NPZ holds the frame core only and is read only for new data (FIL-6); leakage pointers are allowed (SEC-8).

### Not changed
- Binding versions stay `nts-lsl/0.1` and `nts-ws/0.1` (no mapping change).
- No existing vector changed (v0.1 52, `fep-0002` 32, `fep-0003` 44, `fep-0005` 42; new: F41-F47, W38).
- The reference validators still accept only `"0.1"` in a header (gap G-2, planned for RC2).

## [0.1] 2026-11-08 … 2026-11-13
See [v0.1 section 11](neuraltextstream-v0.1.md#11-changelog).
