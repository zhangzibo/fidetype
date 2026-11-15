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
- Python = TypeScript = Rust on all 237 vectors of `v0.1` … `fep-0004` (`cross-check.mjs --rust`), and on the fuzz mutants (`fuzz-parity.mjs`, seeds 1-6, `--n 30`).

### Changed (implementation, later on 2026-11-14; no rule text changed)
- **Gap G-1 closed (section 7.4, all CTL rules that the suite checks):** the TypeScript SDK (`sdk/typescript/src/profiles/fep0005.ts`) and the Rust SDK (`sdk/rust/src/profiles/fep0005.rs`) run the control profile `fep-0005`. They port `fidetype.conformance.profiles.fep0005` and the validators of `fidetype.trust.control`. For a decision log, the reference consumers return `moving_ticks` (the "acted" list of control COMMITs, 6.4), `acted_intents` and `acted_texts`. Rust stays `no_std` + `alloc`; TypeScript has no runtime dependency.
- The parity scripts (`cross-check.mjs`, `fuzz-parity.mjs`) and the CI parity jobs now include `fep-0005` (they take the profile list from the SDK consumers).
- Python = TypeScript = Rust on all 279 vectors of `v0.1` … `fep-0005`, and on 44,196 fuzz mutants (seeds 1-6, `--n 30`; `fep-0005`: 7,560). The fuzz found no Python bug. No vector changed. Open review points (not changed): the profile checks CTL-S7 only after a `stop` decision (a log has no other engagement signal), and it does not check the 7.4.5 notes `p_top1` is null and `score_semantics` follows the radius.

### Changed (check follows the rule text, P1-10, 2026-11-14; no rule text changed)
- **CTL-S7 (7.4.6):** the `fep-0005` decision-log check now follows the rule "a trust layer MUST NOT COMMIT an intent while the control is not engaged". Before, it refused an intent COMMIT only after a `stop`. Now it also refuses one before the first engage. A log has no `control_enable` events, so the check takes the state from the last control decision of the same session: not engaged after a `stop` (latched until a decision with a higher `engagement`), after `engagement` 0, and after the reason `not_engaged` or `disengaged`. Before the first control decision of a session there is no state and no check. The reference trust layer (`fidetype.trust.control`) already blocked such clicks. Python (`fep0005.engaged_after`), TypeScript (`fep0005.engagedAfter`, `ControlSafety`) and Rust (`profiles::fep0005::engaged_after`, `ControlSafety`) have the same rule. An informative note in 7.4.6 tells how a log check sees CTL-S7.
- No existing vector changed its verdict.
- **Added vectors:** `fep-0005` E20 (reject, `FEP5-SAFETY`: an intent COMMIT after a `not_engaged` HOLD with `engagement` 0) and E21 (accept: stop with `engagement` 1, an uncertain HOLD with `engagement` 2, then a click COMMIT). `fep-0005` has 44 vectors now, from 42.
- **SDK `DecisionTracker` (TypeScript, Rust):** it now tracks control decisions (before, it marked them invalid). It checks CTL-T1 … T5 (`seq` over all profiles, ticks do not go back, one move per input tick, a HOLD may repeat a tick) and the log checks CTL-S1 … S7 with the same code as the profile. `forward` is true on a valid control COMMIT, so the forwarded `tick` values are the "acted" list of 6.4. New field `tick`. The Python package has no `DecisionTracker`.
- **7.4.5 notes not checked (by design):** "`p_top1` is null" and "`score_semantics` is `calibrated_prob` when a calibrated radius was used, else `none`" have no rule id and no RFC 2119 key word. They describe the reference output. The checks stay as they are.
- **Parity:** Python = TypeScript = Rust on all 281 vectors of `v0.1` … `fep-0005` (`cross-check.mjs --rust`) and on 44,556 fuzz mutants (seeds 1-6, `--n 30`; `fep-0005`: 7,920).

### Added (rule text, P1-11, 2026-11-14): TD-12, no blank candidates
- **TD-12 (6.3, new):** a 1.x trust layer SHOULD NOT put blank text (1.4) in `shown` of a text `OFFER`, `ASK` or `OFFER_WORDS`. A consumer or bridge MUST NOT offer a blank candidate to the user: it drops it. The producer part is version-gated like TD-9: decisions with `spec_version` `"0.1"` or without it give no finding. The consumer part applies to every version. Why: the TD-9 commit gate turns a blank final COMMIT into an OFFER whose only candidate can be the blank text (FEP-0006 question 2, found in the collector).
- **Validators (Python, TypeScript, Rust, same behaviour):** new advisory check `FEP1-TD-SHOWN` in the `fep-0001` profile. A failure is a warning (`warn`); it never rejects a file. TypeScript and Rust profile `failures()` now skip advisory checks, as Python `failures("core")` does. The reference consumers add two keys to a decision-log summary: `offered` (for each final text OFFER, ASK, OFFER_WORDS: `shown` without blank texts, null if `shown` is absent) and `advisories` (the number of decisions with a TD-12 warning).
- **SDK `DecisionTracker` (TypeScript, Rust):** `offered` drops blank texts (text profile, every version); a 1.x decision with blank candidates gets a TD-12 warning. New helpers `blankCandidateWarning` (TypeScript) and `blank_candidate_warning` (Rust).
- **Vectors:** `fep-0001` F55 (accept with a warning: blank candidates in a provisional OFFER, a final OFFER, an ASK and an OFFER_WORDS of spec_version 1.0; `offered` `[["ab"], [], ["cd"]]`, `advisories` 4) and F56 (accept: the same in 0.1 decisions, `advisories` 0, the consumer still drops the blank texts). `fep-0001` has 56 vectors now, from 54. No existing vector changed its verdict.
- **Collector (FEP-0006 3.2):** the trust processor removes blank candidates; an OFFER or OFFER_WORDS with no candidate left becomes `ABSTAIN` with `shown = []`. Metrics `blank_candidates_dropped` and `blank_offers_abstained`.
- **Parity:** Python = TypeScript = Rust on all 283 vectors of `v0.1` … `fep-0005` (`cross-check.mjs --rust`; the expected `offered` and `advisories` values of F55 and F56 match in all three), and on 44,916 fuzz mutants (seeds 1-6, `--n 30`).

### Added (vectors, P4-08, 2026-11-14; no rule text changed): HDR-12, empty vocabulary
- **Vectors:** `v0.1` V62 (accept: `vocab = []`, `blank_id` null, two hypotheses and two `segment_end`, no frames), V63 (reject, `NTS-NORM`: `vocab = []` with a dense frame `log_probs = []`), V64 (reject, `NTS-NORM`: `vocab = []` with a sparse frame, k = 0 and `rest_log_prob` 0), V65 (reject, `NTS-BLANK`: `vocab = []` with `blank_id` 0, HDR-6). `v0.1` has 65 vectors now, from 61. No existing vector changed its verdict. No validator gives a separate HDR-12 finding: an empty-vocab frame fails FRM-3 (`NTS-NORM`; a row with no values has log-sum-exp -inf).
- **Writers (Python `StreamWriter`, TypeScript and Rust `NtsWriter`, same behaviour):** they accept `vocab = []` with `blank_id` null and refuse every frame of such a stream (HDR-12). The text n-best adapter now writes through `StreamWriter`.
- **Parity:** Python = TypeScript = Rust on all 287 vectors of `v0.1` … `fep-0005` (`cross-check.mjs --rust`), and on the fuzz mutants (seeds 1-3, `--n 30`).
- **Not changed (open point):** the vector-count table (9.3, `v0.1` = 61) and the traceability row of HDR-12 (C.1, vector W03 only) in `nts-1.0-rc2.md` are not updated; they can list V62-V65 in the next draft.

### Added (P1-02, 2026-11-15; no rule text changed): protobuf schema and generated JSON Schema
- **Proto3 source of truth:** [`proto/neuraltextstream/v1/*.proto`](proto/neuraltextstream/v1/) (package `neuraltextstream.v1`) covers the full RC2 data model: the header with the three declarations, `frame` (dense and sparse), `segment_end`, `end`, `signal_quality`, `decision`, `hypothesis` (n-best, evidence fields, spans, `decode_declaration`), `pointer`, `intent`, `intent_feedback`, `control`, `control_enable`, `trust_decision` (text, intent and control profiles), the LSL `gap` extension event, the timing fields and the binding keys. Field comments cite the rule ids. Rules for the package and versioning, field numbers, the NTS JSON mapping and unknown or extension data: [`proto/README.md`](proto/README.md) (informative).
- **Generated JSON Schema:** [`schemas/nts-v1.schema.json`](schemas/nts-v1.schema.json) (draft 2020-12, one line = one event) by `tools/proto/gen_jsonschema.py` (standard library only). CI job `proto`: the file is up to date; protoc (grpcio-tools, not committed) compiles the proto files and agrees with the generator's parser; parity with the SDK verdicts.
- **Parity:** of the 287 vectors, 164 are compared (91 accept, 73 reject on a rule that the schema expresses): **164 match, 0 mismatches**, with the built-in validator and with `jsonschema` 4.26.0. 90 reject vectors fail on a rule that a one-line schema cannot see (cross-line 28, trust 17, cross-field 10, arithmetic 7, binding 21, lexical GEN-5 3, parse 4); the schema accepts all 90. 33 NPZ vectors are out of scope. List and classes: `tools/proto/parity.py`, [`proto/README.md`](proto/README.md) section 8.
- **Not changed:** the hand-written schemas (`schemas/nts-v0.1/`, `schemas/fep-000N/`), the TypeScript generated types, the SDK validators and every vector.

### Open questions (P1-02, found while writing the proto; the normative text is not changed)
- **Q-1. JSON null in optional fields.** GEN-3 defines `null` only for log-probabilities. The field tables give `frame_period` and `latency` the type "number", but the three SDKs (and `schemas/nts-v0.1/header`) read `null` as "absent". The binary form has no null. The proto marks these two fields nullable (null = no value). Should 1.0 say "null = absent" for every optional field, or forbid null outside GEN-3 and the fields typed "or null"?
- **Q-2. LSL keys outside EXT-3.** LSL-G1 (mode `segment`) adds `reason = "gap"` to `segment_end`, a key without the `lsl` prefix (EXT-3). The `gap` event (12.1) has no field table; the proto takes its fields from the reference adapter (`t_start`, `t_end`, `missing_frames`, `stream`). Should 1.0 rename the key (for example `lsl_reason`) and give `gap` a field table?
- **Q-3. Control `reasons`: closed list or open?** 7.4.5 and registry 12.3 (policy Spec) list 13 reason codes. The SDK validators accept any string. The proto keeps `repeated string`. Is an unknown code an error, a warning or allowed?
- **Q-4. Keys of `declaration` and `input`.** 6.1 names the keys of `trust_decision.declaration` (`status`, `mode`, `where`, `decoder`, `mismatches`) and the content of `input` (frame range + SHA-256, or hypothesis id + SHA-256), but gives no key names or types for `input` and no types for `declaration`. The proto keeps both as free JSON objects. Should 1.0 give them field tables?
- **Q-5. Integer range.** RC2 says "integer" with no upper bound. The proto must choose a width (uint64 for `seq`, `utterance`, `unit`, `tick`, `engagement`, `ws_seq`, `ref_unit`; uint32 for `blank_id`, `set_size`, `dims`). JSON numbers above 2^53 − 1 lose precision in JavaScript. Should 1.0 cap integers at 2^53 − 1?
- **Q-6. A field of another profile on a decision.** A text decision with `"tick": "x"`: is `tick` a custom key (any type, GEN-4) or the control field with a wrong type (EXT-1: one type per field)? The SDKs check profile fields only inside their profile; the generated schema types them on every decision.
- **Q-7. New enum values in a minor version.** 11.1 lets a minor version add registry entries (for example a `vocab_type` or an `action` value). VER-3 says a 1.0 consumer reads a newer minor version with the 1.0 rules and ignores what it does not know, but HDR-5, TD-F1, SEG-5 and others make a 1.0 consumer refuse an unknown value. Should a 1.0 consumer refuse, ignore the event, or map the value to "other"? (proto3 enums are open: the binary form keeps an unknown number.)
- **Q-8. Two SDK format checks without rule text.** The validators refuse a control decision with `radius` but without `level` (7.4.5 lists both as optional) and an intent decision with `confirm_required = true` on an action other than OFFER (7.3.1 defines an arm, but no rule id forbids the other case). The generated schema follows the SDKs. Should 1.0 add rule ids, or should the SDKs drop the checks?

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
