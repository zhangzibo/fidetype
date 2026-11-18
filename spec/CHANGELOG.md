# Spec changelog

All notable changes to the specifications in `spec/`. Newest first. Earlier v0.1 entries are also in [section 11 of the v0.1 spec](neuraltextstream-v0.1.md#11-changelog).

## [1.0 RC4, DRAFT] amendment 7 of 2026-11-18 (advisory licence check)
**Still RC4 DRAFT.** Changes in [nts-1.0-rc4.md](nts-1.0-rc4.md) (section 1.6, "Amendment 7 of 2026-11-18"; 3.4 MET-12 note; 9.2; 9.3; 9.5; Appendix C.1). [FEP-0010](feps/0010-data-licence-keys.md) open questions LIC-2 and LIC-3 answered; [FEP-0006](feps/0006-collector.md) section 4 rule 6.

### Added
- **NTS-LICENCE-MATCH (MET-12).** An advisory check in the three validators: `data.research_only = false` with a Creative Commons id with `NC` or `LicenseRef-unknown` (ASCII, without case) gives a warning, never a reject. Other ids give no warning. Vectors V101, V102, V103 (accept with the warning), V104 (accept, no warning).
- **Collector exporter option `refuse_research_only`** (FEP-0006 section 4 rule 6; an operator policy, not a format rule): drop decisions with `input.research_only = true`; `unknown_licence = "refuse"` (default) or `"pass"` for decisions without the key.
- **`refuse_research_only` on input-event exporters** (P5-22, FEP-0006 section 4 rule 6, FEP-0010 decision 6; operator policy): a `jsonl` or `stdout` exporter of input events drops a research-only stream whole, by its header keys; the same `unknown_licence` rule. The P5-18 configuration error for this case is gone. No format change.

### Counts
- Vectors 355 (v0.1 104). Streaming cases 6, kit 36 (unchanged). Python = TypeScript = Rust on all 355 (warnings pinned by `expected.warnings`), the 36 kit entries and 28,487 fuzz mutants (seeds 1-3, `--n 30`, 0 differences).

## [1.0 RC4, DRAFT] amendment 6 of 2026-11-17 (data licence keys)
**Still RC4 DRAFT.** Additive changes in [nts-1.0-rc4.md](nts-1.0-rc4.md) (section 1.6, "Amendment 6 of 2026-11-17"; 3.4 MET-12 and two rows; 6.1.1 one row; 6.2 TD-15; 9.3; 9.5; Appendix C.1). New FEP: [FEP-0010](feps/0010-data-licence-keys.md) (Draft). Roadmap P5-13 (gap 47). No earlier vector changed its verdict.

### Added
- **MET-12 data licence keys.** `data.licence` (non-empty string, an SPDX id) and `data.research_only` (boolean; MUST be `true` for a licence without commercial use) in the reserved namespace `data`. Registry: `spec/semconv/attributes/data.yaml` (54 keys in all). The Python, TypeScript and Rust validators check the types. Vectors V98 (accept), V99, V100 (reject).
- **TD-15.** A recommended audit key `input.research_only` (boolean) on `trust_decision`: the trust layer copies the research-only flag of its input stream and of its provenance lineage. Audit data (TD-13); no validator change.

### Changed (reference implementations)
- Adapters emg2qwerty, kt_semg, toronto_semg, willett_handwriting, spanishbcbl_meg (was the custom key `spanishbcbl.licence`) and b2t25 write the two keys.
- Provenance ledger: a stream with the keys becomes a `source` entry; contexts list it in `stream_sources`; `verify` recomputes the flags.
- `StreamingTrustLayer`, `IntentTrustLayer`, `ControlTrustLayer` and the collector `guard` processor write `input.research_only`.

### Counts
- Vectors 351 (v0.1 100). Streaming cases 6, kit 36 (unchanged). Python = TypeScript = Rust on all 351, the 36 kit entries and 28,217 fuzz mutants (seeds 1-3, `--n 30`).

## [1.0 RC4, DRAFT] amendment 5 of 2026-11-17 (LSL heartbeat and equal times; TD-4 in live input)
**Still RC4 DRAFT.** Changes in [nts-1.0-rc4.md](nts-1.0-rc4.md) (section 1.6, "Amendment 5 of 2026-11-17"; 6.3 TD-14; 8.2.5 LSL-C6 … LSL-C8; 9.3; 9.5; Appendix C.1) and [FEP-0002](feps/0002-nts-over-lsl.md) section 6 rules 6-8. Roadmap P3-10 (gap 43) and P14-20 (gap 46). No earlier vector changed its verdict. Binding version unchanged (`nts-lsl/0.1`).

### Added
- **LSL-C7 heartbeat.** An empty events-stream sample is a heartbeat: not an NTS event, not an ignored plain string, but it moves the inlet's merge position. Events-stream timestamps MUST NOT decrease. A two-stream producer SHOULD send one after each frame with the frame's timestamp. Vector L36.
- **LSL-C8 equal times.** At equal times the merge gives the frames-stream item first. A producer MAY stamp a marker with the time of the frame before it. Vector L37 (without the rule: 2 final decisions instead of 1).
- **TD-14.** An event-by-event consumer MUST refuse a `trust_decision` between the header and `end` of an input stream (TD-4), and ignore it after `end`. Streaming cases S01 … S06 (`conformance/streaming/td-input.json`), run by the Python, TypeScript and Rust tests.

### Changed (reference implementations)
- Python `NTSOutlet` / `replay-to-lsl` / `fidetype live --publish lsl`: a heartbeat after each frame; markers take the timestamp of the frame before them. Collector bench: LSL input at the receiver default window (0.05 s): implant-speech p95 added 1.07 ms (was 60.4 ms).
- `StreamingTrustLayer.push`, TypeScript / Rust `StreamValidator`, collector `validate`: refuse a `trust_decision` in an input stream.

### Counts
- Vectors 348 (fep-0002 37). Streaming cases 6. Kit 36 (unchanged).

## [1.0 RC4, DRAFT] amendment 4 of 2026-11-17 (TD-4 check in the v0.1 suite)
**Still RC4 DRAFT.** Changes in [nts-1.0-rc4.md](nts-1.0-rc4.md) (section 1.6, "Amendment 4 of 2026-11-17"; 9.3; Appendix C.1 row TD-4). Roadmap P14-17 (gap 42). No rule changed. No earlier vector changed its verdict.

### Added
- **Core check `NTS-TD-INPUT` in the v0.1 suite (TD-4).** The v0.1 suite read a `trust_decision` line in an input stream as an unknown event type and ignored it (6.2 rule 5). Only the `fep-0001` profile (`FEP1-TD-INPUT`) tested TD-4. So `fidetype validate`, `fidetype-ts validate` and `fidetype-rs validate` passed a file that `nts-conform check` failed. The three v0.1 validators now refuse it. Vector V97 (reject).

### Counts
- Vectors 346 (v0.1 97). Kit 36 (unchanged).

## [1.0 RC4, DRAFT] amendment 3 of 2026-11-17 (levels, self-certification, MET-11 check) and conformance kit 0.2.0
**Still RC4 DRAFT.** Changes in [nts-1.0-rc4.md](nts-1.0-rc4.md) (section 1.6, "Amendment 3 of 2026-11-17"; sections 9.2, 9.6, 9.7; Appendix C.1). Roadmap P7-02 and P1-16 (gap 20). Additive: no earlier vector and no earlier kit entry changed its verdict.

### Added
- **Implementation levels (9.6; CNF-2, CNF-5, CNF-6, CNF-7):** NTS Core (the frame core), NTS Full (all event kinds of the named output profiles), NTS Trust-ready (Full + score semantics, provenance and timing). Cumulative. Producers qualify with `nts-conform check` on their files, consumers with `nts-conform kit`. Bindings `nts-lsl/0.1` and `nts-ws/0.1` are added to a claim by their kit entries. Generated copy: [`conformance/levels.json`](conformance/levels.json).
- **Rule ids for the stream levels (9.2):** CNF-3 (trust-ready checks), CNF-4 (provenance checks).
- **Self-certification (9.7, CNF-8):** [`conformance/certified.json`](conformance/certified.json) with evidence reports in `conformance/certified/`. First entries: the Python, TypeScript and Rust SDKs (consumers, NTS Trust-ready) and the producer adapters of this repository. No outside entry.
- **MET-11 check:** advisory `NTS-MODALITY-MATCH` in the three validators (a modality key that does not fit `device.modality` is a warning, never a reject). Vectors V93, V94, V96 (accept with the warning), V95 (accept, no warning). C.1 row for MET-11 (the last rule id without a row) and rows for CNF-2 … CNF-8.
- **Conformance kit 0.2.0:** K32 (MET-11 warning), K33 … K36 (valid streams at stream level core or trust-ready); `stream_level` on every input-stream entry; the v0.1 kit manifest and V93 … V96 pin `expected.warnings` and `expected.level`, which the three SDK runners compare.
- **`rule-map.json`:** a `refine` table maps the messages of broad checks to the rule of the finding (for example `FEP2-CONSUME` -> `LSL-F2` for a wrong channel count).

### Counts
- Vectors 345 (v0.1 96). Kit 36. Python = TypeScript = Rust on all of them and on 27,767 fuzz mutants (seeds 1–3, `--n 30`). Schema parity (C.3): 213 of 213 one-line verdicts.

## Conformance kit 0.1.0 (2026-11-17, roadmap P7-01)
No change to the spec text or to any vector verdict.

### Added
- **[`conformance/kit/`](conformance/kit/kit.json):** 31 small example files, one or more per wire form of NTS 1.0 RC4: JSON Lines input streams (dense and sparse frames, `meta` conventions, v0.1 events, text, intent and control profiles), NPZ, decision logs (text, intent, control), LSL captures (frames + events, decisions) and WebSocket captures (`/nts`, `/decisions`). 14 accept, 1 accept-with-warnings, 16 reject. Each entry names its verdict, the rule ids that it exercises and the checks that must fail or warn. One `manifest.json` per suite profile in the golden-vector format. Python = TypeScript = Rust on all 31; the generated JSON Schema agrees on every entry that it can judge.
- **[`conformance/kit/rule-map.json`](conformance/kit/rule-map.json):** check id -> rule ids, generated from Appendix C.1 of RC4.
- Binary protobuf has no kit file: it is not a wire form in RC4 (binary framing: roadmap P1-05).

## [1.0 RC4, DRAFT] amendment 2 of 2026-11-16 (gap G-13 part a)
**Still RC4 DRAFT.** Changes in [nts-1.0-rc4.md](nts-1.0-rc4.md) (section 1.6, "Amendment 2 of 2026-11-16"; rule FRM-2). Roadmap P1-14. No earlier vector changed its verdict.

### Changed
- **FRM-2 (option A2 of C.2).** A dense frame MAY also carry sparse keys. The dense form wins: a consumer uses `log_probs` and does not use the sparse keys (FRM-3, FRM-5 and `top_ids` < V do not apply to them). Each sparse key that is present MUST still have its type (GEN-11): `top_ids` a list of unique integers >= 0, `top_log_probs` a list of numbers or null, `rest_log_prob` a number or null.
- **Validators (Python, TypeScript, Rust):** the JSONL readers and the streaming validators (`frame_row` / `frameRow`) refuse a wrong-typed sparse key on a dense frame (check NTS-JSONL-FRAME). Before, they ignored the keys.
- **Proto / schema:** comment on `Frame` only. The generated JSON Schema already typed the sparse keys, so it does not change.

### Added
- **Vectors:** `v0.1` V88 (accept), V89, V90, V91, V92 (reject): 92 now. 341 in all. Python = TypeScript = Rust on all 341 and on 27,497 fuzz mutants (seeds 1-3, `--n 30`). Schema parity: 210 of 210 one-line verdicts.

### Closed
- Gap G-13 (both parts). Nothing of it stays open.

## [1.0 RC4, DRAFT] amendment 2026-11-16
**Still RC4 DRAFT.** Additive changes in [nts-1.0-rc4.md](nts-1.0-rc4.md) (section 1.6, "Amendment 1 of 2026-11-16"). New FEP: [FEP-0009](feps/0009-modality-semantic-conventions.md) (Draft). No RC4 vector changed its verdict.

### Added
- **Modality keys (SC-1, partly; MET-11).** `emg.placement`, `emg.derivation`, `meg.sensor_types`, `implant.array_type`, `implant.array_count`, `implant.features`, `implant.bin_s`, `implant.areas`: optional, Development. From the reference adapters (emg2qwerty, KT-sEMG, Toronto sEMG, SpanishBCBL MEG, Willett handwriting, Brain-to-Text '25), checked against NLB MC_RTT. `emg`, `meg`, `implant` are now namespaces with keys; `eeg`, `fnirs` stay planned (new open question SC-9).
- **Registry:** files `attributes/emg.yaml`, `meg.yaml`, `implant.yaml`; validator `non_empty_string_list`; `registered_values` allowed on `string[]` keys. 51 keys (32 `meta`).
- **Validators (Python, TypeScript, Rust):** the 8 keys in `DEFINED_KEYS` (type check NTS-META-TYPES); `PLANNED_NAMESPACES` = `eeg`, `fnirs`.
- **Adapters:** the six adapters above write the keys that they know.
- **Proto / schema (gap G-13 part b closed):** field option `json_null_list`; `Control.absent` uses it, so the generated schema accepts `absent: null` (GEN-9). The hand-written `schemas/fep-0005/control-event.schema.json` agrees.
- **Vectors:** `v0.1` V83, V84, V85 (accept), V86, V87 (reject): 87 now. `fep-0005` C26 (accept): 53 now. 336 in all. Python = TypeScript = Rust on all 336 and on 27,047 fuzz mutants (seeds 1-3, `--n 30`). Schema parity: 205 of 205 one-line verdicts.

### Open
- G-13 part (a) (a dense frame with sparse keys of a wrong type): options A1 … A3 in C.2; needs a decision for 1.0 Stable. *Closed by amendment 2 (option A2), above.*

## [1.0 RC4, DRAFT] 2026-11-15
**Status: draft for public comment. Not final.** Document: [nts-1.0-rc4.md](nts-1.0-rc4.md) (section 1.6 "Changes from RC3"). RC3, RC2 and RC1 stay unchanged as the record. New FEP: [FEP-0008](feps/0008-optional-field-types-and-semconv.md) (Draft).

RC4 answers the semantic-convention questions SC-2 … SC-8 of the P1-04 registry and closes gap G-12. Rule used: the simplest rule that keeps valid data valid. No RC3 vector changed its verdict.

### Resolved questions
| # | Resolution | Rules | SDK change | Vectors |
|---|---|---|---|---|
| SC-1 | Modality keys: **deferred** to a FEP with evidence from real producers | 12.5, A.8 | none | none |
| SC-2 | Planned namespaces `emg`, `eeg`, `meg`, `fnirs`, `implant` are reserved; a custom key in them gets the MET-3 warning | MET-3, 12.5 | Python, TypeScript, Rust: `PLANNED_NAMESPACES` in the namespace warning | V69 (accept, warning) |
| SC-3 | String keys of 3.4 are "non-empty string" (the validators already refused `""`) | MET-7 | none | none |
| SC-4 | Open lists: `device.regulatory_status`, `decoder.calibration_method`, `input.kind`, `declaration.mode`; closed: `device.modality`, `declaration.status`, `declaration.where` | MET-8 | none | none |
| SC-5 | `input` and `declaration` keys: Development in 1.0 | 2.3 | none | none |
| SC-6 | Only physical quantities have a unit (seconds); counts, indices, flags, ids and texts have none | MET-9 | none | none |
| SC-7 | The YAML registry is normative; spec tables are informative copies checked in CI; A.1 item 9 resolved | MET-10 | none (tooling) | CI `semconv` |
| SC-8 | No spec change; the CI check compares the SDK key tables, modality lists and planned namespaces with the registry | MET-10 | `semconv.py` checks `PLANNED_NAMESPACES` | — |
| G-12 | Optional fields have their table type (GEN-11): `segment_end.reason`; `hypothesis.t_start`, `t_end`, `revision_of`, `nbest[].spans`; `signal_quality.channels`; `pointer.absent`, `score`, `score_semantics`; `decision.score`, `score_range` (every semantics); header `vocab_id`, `vocab_version`; `trust_decision.reason`; intent `vocab_id`, `pending_cleared`; control `level`; latency fields on every event | GEN-11, HDR-16, SEG-6, SQ-1, DEC-6, HYP-5, PTR-1, TIM-4, TD-F2, INT-T8, CTL-T8 | Python, TypeScript, Rust (same checks) | V69 (accept), V70-V82 (reject), F63 (accept), F64-F66, D24 (accept), D25, D26, I25, C25, E25 (accept), E26, E27 |

### Changed
- **Validators (Python, TypeScript, Rust, same behaviour).** New type checks of G-12. The latency-field check (TIM-4) now covers every event of registry 12.1 in a JSON Lines stream, frames included (new `RawStream.timed` / `timed`). `NTS-VOCAB-ID` checks the type of `vocab_id` and `vocab_version` (title changed). A known `score_semantics` is not needed for the type rules of DEC-6 (an unknown semantics of a newer minor version keeps them). A `null` pointer `score_semantics` is refused (GEN-9).
- **Proto:** `TrustDecision.t` has `json_profile = "control"` (PRF-5; 7.4.5 now lists `t`). Generated JSON Schema regenerated.
- **Semantic-convention registry:** spec document `nts-1.0-rc4.md`; `resolved_questions` (SC-2 … SC-8); attribute field `registered_values` (open lists) instead of `examples`; `target_stability: development` for the `input` and `declaration` keys; the check reads the spec type "non-empty string" and compares `PLANNED_NAMESPACES` of the SDKs.

### Added (vectors)
- `v0.1` V69 (accept), V70-V82 (reject): 82 vectors now, from 68.
- `fep-0001` F63 (accept), F64-F66 (reject): 66 now, from 62.
- `fep-0003` D24 (accept), D25, D26, I25 (reject): 51 now, from 47.
- `fep-0005` E25 (accept), E26, E27, C25 (reject): 52 now, from 48.
- 330 vectors in all. Python = TypeScript = Rust on all 330 and on 26,687 fuzz mutants (seeds 1-3, `--n 30`). Generated JSON Schema: 201 of 201 one-line verdicts (built-in validator and `jsonschema` 4.26.0).

### Not changed
- Every RC3 vector verdict; binding versions; the enumeration registries and fallbacks.

## [1.0 RC3, DRAFT] 2026-11-15
**Status: draft for public comment. Not final.** Document: [nts-1.0-rc3.md](nts-1.0-rc3.md) (section 1.6 "Changes from RC2"). RC2 and RC1 stay unchanged as the record. New FEP: [FEP-0007](feps/0007-unknown-enum-values.md) (Draft).

RC3 answers the open questions Q-1 … Q-8 of the P1-02 protobuf work (listed under RC2 below). Rule used: write down what the three SDKs already do if that is safe; else choose one rule and change all three SDKs.

### Resolved questions
| # | Resolution | Rules | SDK change | Vectors |
|---|---|---|---|---|
| Q-1 | `null` only where the type says "or null"; `frame_period`, `latency`, `vocab_id`, `vocab_version`, intent `threshold`, `role`, feedback `intent`, control `absent` now say "or null" (the SDKs already read null as "no value" there) | GEN-9 | none | none (SDK probes, no change) |
| Q-2 | Written down: `segment_end.reason` (core, open list, `gap` registered); `gap` field table; gap keys as an EXT-3 exception; event type `lsl_status` registered | SEG-6, LSL-G3, EXT-3 | none | L06 … L08 (existing) |
| Q-3 | Control `reasons` is an open list; never read an unknown code as `ok` | CTL-T9 | none | none (existing) |
| Q-4 | `declaration` MUST be an object; recommended key tables for `input` (6.1.1) and `declaration` (6.1.2); audit data, never a basis for an action | TD-F2, TD-13 | Python, TypeScript, Rust refuse a non-object `declaration` | F62 (reject) |
| Q-5 | Integers in −(2^53 − 1) … 2^53 − 1 | GEN-10 | Python (`json_int` parse hook), TypeScript (`Number.isSafeInteger`), Rust (`Value::is_int` bound) | F60 (reject), F61 (accept), W44 (reject) |
| Q-6 | Profile fields have their type only on decisions of their profile; elsewhere custom keys | PRF-5, EXT-1 | none (generated schema follows) | none (existing) |
| Q-7 | Version-gated unknown enumeration values with a safe fallback per enumeration (registry 12.3 column); binding enumerations stay closed | VER-6 … VER-10 (11.2.1), FEP-0007 | all three SDKs (below) | V66, F57, F58, I24, D22, C24, E22 (accept); V67, V68, F59, D23, E23, E24 (reject) |
| Q-8 | Rule ids for the two SDK checks | INT-T7, CTL-T8 | none | none (existing) |

### Changed (implementation)
- **VER-8 in the validators (Python, TypeScript, Rust, same behaviour).** When the governing version (decision `spec_version`, else the header `spec_version`) is a newer minor version (`"1.1"` …), these checks accept any string: `vocab_type`, `clock_domain`, `device.modality`, `signal_quality.unit`, `decision`/`hypothesis`/`intent` `score_semantics`, `pointer.mode`, `segment_end.unit`, decision `action`, `score_semantics`, `profile`, intent `risk`, `role` (declaration), `risk_class`, `role`, `confirmed_via` (decision), `intent_feedback.outcome`, control `quantity`, `units`, `frame`, `uncertainty`, `control.source`, `control_enable.source`, control decision `action`, `state`. Comparison rules skip unknown values (CTL-T3, CTL-D1, INT-D4, the score rules, the ranking rule, the `std` rule of CTL-3). Helpers: Python `fidetype.streams.spec.is_newer_minor`, `enum_ok`, `is_unknown`; TypeScript `isNewerMinor`, `enumOk`, `isUnknown`; Rust `constants::is_newer_minor`, `json::{enum_ok, is_unknown, newer_minor}`.
- **VER-10 in the consumers.** `acted` / `acted_texts`: only text-profile decisions (`profile` absent or `"text"`; PRF-4). `acted_intents`: no intent COMMIT with an unknown `risk_class`, `role` or `confirmed_via`. `moving_ticks`: only COMMITs with a known moving state. CTL-S7 log check: after a control decision with an unknown state or action, the control is not engaged (vector E24). SDK `DecisionTracker` (TypeScript, Rust): new kind `unknown` (an unknown action or profile; never forwarded); `forward = false` for an intent COMMIT with an unknown value and for a control COMMIT with an unknown state.
- **The reference trust layers stay strict** (they refuse a header with an unknown `vocab_type`, intent risk/role or control declaration value; VER-10 allows it). The SDK stream readers share the text layer's header check.
- **API (Python, TypeScript):** the validators of `fidetype.trust.intent` / `.control` and their TypeScript ports take an optional `lenient` argument. **Rust (breaking, crate 0.x):** `validate_intent_declaration`, `validate_intent_event`, `validate_feedback_event`, `validate_control_declaration`, `validate_control_event` and `validate_enable_event` take a `lenient: bool` argument.

### Added (vectors)
- `v0.1` V66 (accept), V67, V68 (reject): 68 vectors now, from 65.
- `fep-0001` F57, F58, F61 (accept), F59, F60, F62 (reject): 62 now, from 56.
- `fep-0003` I24, D22 (accept), D23 (reject): 47 now, from 44.
- `fep-0004` W44 (reject): 44 now, from 43.
- `fep-0005` C24, E22 (accept), E23, E24 (reject): 48 now, from 44.
- No RC2 vector changed its verdict.

### Changed (proto and generated JSON Schema)
- New field option `json_profile` (50105) on the intent fields (40–51) and control fields (60–72) of `TrustDecision`: the generated schema types them only on decisions of that profile (PRF-5).
- Enumeration fields accept any string in the base schema; new definitions `Header.known`, `TrustDecision.known` (and the nested `*.known`) require the known values unless `spec_version` is a newer minor version. The action and state rules (INT-T1, CTL-T1, CTL-T3), CTL-D1 units and INT-D4 now name the known values that they forbid, so a newer minor version can add values.
- Integers carry `maximum` 2^53 − 1 (GEN-10). `Header.vocab_id` and `vocab_version` are nullable (GEN-9). `SegmentEnd.reason` (field 3, SEG-6). Rule ids INT-T7, CTL-T8, CTL-T9 in the comments.
- Parity (`tools/proto/parity.py`): of 304 vectors, 178 are compared (99 accept, 79 reject): **178 match, 0 mismatches**, with the built-in validator and with `jsonschema` 4.26.0. F04 and I22 moved to class cross-line (an unknown event value is an error only under a 1.0 header). `check_protoc.py`: 0 differences.

### Fixed (informative parts)
- The vector counts of 2.3, 9.3 and 9.5, and the C.1 row of HDR-12 (now V62 … V65, W03; status T). C.1 rows for every new rule; new gap G-12 (optional-field types that no validator checks); C.3 counts.

### Parity
- Python = TypeScript = Rust on all 304 vectors of `v0.1` … `fep-0005` (`cross-check.mjs --rust`), and on 24,347 fuzz mutants (seeds 1–3, `--n 30`; 0 differences).

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
- **Not changed (open point):** the vector-count table (9.3, `v0.1` = 61) and the traceability row of HDR-12 (C.1, vector W03 only) in `nts-1.0-rc2.md` are not updated; they can list V62-V65 in the next draft. *(Fixed in RC3.)*

### Added (P1-02, 2026-11-15; no rule text changed): protobuf schema and generated JSON Schema
- **Proto3 source of truth:** [`proto/neuraltextstream/v1/*.proto`](proto/neuraltextstream/v1/) (package `neuraltextstream.v1`) covers the full RC2 data model: the header with the three declarations, `frame` (dense and sparse), `segment_end`, `end`, `signal_quality`, `decision`, `hypothesis` (n-best, evidence fields, spans, `decode_declaration`), `pointer`, `intent`, `intent_feedback`, `control`, `control_enable`, `trust_decision` (text, intent and control profiles), the LSL `gap` extension event, the timing fields and the binding keys. Field comments cite the rule ids. Rules for the package and versioning, field numbers, the NTS JSON mapping and unknown or extension data: [`proto/README.md`](proto/README.md) (informative).
- **Generated JSON Schema:** [`schemas/nts-v1.schema.json`](schemas/nts-v1.schema.json) (draft 2020-12, one line = one event) by `tools/proto/gen_jsonschema.py` (standard library only). CI job `proto`: the file is up to date; protoc (grpcio-tools, not committed) compiles the proto files and agrees with the generator's parser; parity with the SDK verdicts.
- **Parity:** of the 287 vectors, 164 are compared (91 accept, 73 reject on a rule that the schema expresses): **164 match, 0 mismatches**, with the built-in validator and with `jsonschema` 4.26.0. 90 reject vectors fail on a rule that a one-line schema cannot see (cross-line 28, trust 17, cross-field 10, arithmetic 7, binding 21, lexical GEN-5 3, parse 4); the schema accepts all 90. 33 NPZ vectors are out of scope. List and classes: `tools/proto/parity.py`, [`proto/README.md`](proto/README.md) section 8.
- **Not changed:** the hand-written schemas (`schemas/nts-v0.1/`, `schemas/fep-000N/`), the TypeScript generated types, the SDK validators and every vector.

### Open questions (P1-02, found while writing the proto; the normative text is not changed) — **all resolved in RC3** (see above)
- **Q-1.** *(Resolved in RC3: GEN-9.)* **JSON null in optional fields.** GEN-3 defines `null` only for log-probabilities. The field tables give `frame_period` and `latency` the type "number", but the three SDKs (and `schemas/nts-v0.1/header`) read `null` as "absent". The binary form has no null. The proto marks these two fields nullable (null = no value). Should 1.0 say "null = absent" for every optional field, or forbid null outside GEN-3 and the fields typed "or null"?
- **Q-2.** *(Resolved in RC3: SEG-6, LSL-G3.)* **LSL keys outside EXT-3.** LSL-G1 (mode `segment`) adds `reason = "gap"` to `segment_end`, a key without the `lsl` prefix (EXT-3). The `gap` event (12.1) has no field table; the proto takes its fields from the reference adapter (`t_start`, `t_end`, `missing_frames`, `stream`). Should 1.0 rename the key (for example `lsl_reason`) and give `gap` a field table?
- **Q-3.** *(Resolved in RC3: CTL-T9.)* **Control `reasons`: closed list or open?** 7.4.5 and registry 12.3 (policy Spec) list 13 reason codes. The SDK validators accept any string. The proto keeps `repeated string`. Is an unknown code an error, a warning or allowed?
- **Q-4.** *(Resolved in RC3: TD-F2, TD-13.)* **Keys of `declaration` and `input`.** 6.1 names the keys of `trust_decision.declaration` (`status`, `mode`, `where`, `decoder`, `mismatches`) and the content of `input` (frame range + SHA-256, or hypothesis id + SHA-256), but gives no key names or types for `input` and no types for `declaration`. The proto keeps both as free JSON objects. Should 1.0 give them field tables?
- **Q-5.** *(Resolved in RC3: GEN-10.)* **Integer range.** RC2 says "integer" with no upper bound. The proto must choose a width (uint64 for `seq`, `utterance`, `unit`, `tick`, `engagement`, `ws_seq`, `ref_unit`; uint32 for `blank_id`, `set_size`, `dims`). JSON numbers above 2^53 − 1 lose precision in JavaScript. Should 1.0 cap integers at 2^53 − 1?
- **Q-6.** *(Resolved in RC3: PRF-5.)* **A field of another profile on a decision.** A text decision with `"tick": "x"`: is `tick` a custom key (any type, GEN-4) or the control field with a wrong type (EXT-1: one type per field)? The SDKs check profile fields only inside their profile; the generated schema types them on every decision.
- **Q-7.** *(Resolved in RC3: VER-6 … VER-10, FEP-0007.)* **New enum values in a minor version.** 11.1 lets a minor version add registry entries (for example a `vocab_type` or an `action` value). VER-3 says a 1.0 consumer reads a newer minor version with the 1.0 rules and ignores what it does not know, but HDR-5, TD-F1, SEG-5 and others make a 1.0 consumer refuse an unknown value. Should a 1.0 consumer refuse, ignore the event, or map the value to "other"? (proto3 enums are open: the binary form keeps an unknown number.)
- **Q-8.** *(Resolved in RC3: INT-T7, CTL-T8.)* **Two SDK format checks without rule text.** The validators refuse a control decision with `radius` but without `level` (7.4.5 lists both as optional) and an intent decision with `confirm_required = true` on an action other than OFFER (7.3.1 defines an arm, but no rule id forbids the other case). The generated schema follows the SDKs. Should 1.0 add rule ids, or should the SDKs drop the checks?

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
