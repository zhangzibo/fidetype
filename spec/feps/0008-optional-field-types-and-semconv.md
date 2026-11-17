# FEP-0008: Optional field types and the semantic-convention registry

| | |
|---|---|
| **FEP** | 0008 |
| **Title** | Optional fields have their table type; the YAML semantic-convention registry is normative |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft (folded into [NTS 1.0 RC4](../nts-1.0-rc4.md), sections 1.6, 3.4 and A.8; reference implementation and vectors in Python, TypeScript and Rust) |
| **Type** | Spec change |
| **Affects** | NTS 1.0 RC3 sections 3.1, 3.4, 4.1, 4.3, 4.5–4.8, 5.2, 6.2, 7.3.5, 7.4.5, 12.5 and Appendix A.1 item 9 |
| **Created** | 2026-11-15 |
| **Discussion** | Gap G-12 of RC3 Appendix C.2; open questions SC-1 … SC-8 of the [semantic-convention registry](../semconv/registry.md) (roadmap P1-04) |

## Summary
Two groups of changes. (1) **Optional field types (gap G-12).** RC3 gave a type to every field in its tables, but the three SDK validators did not check the type of some optional fields. The generated JSON Schema did. New rule GEN-11: an optional field has the type of its table when it is present, and a consumer refuses a wrong type. (2) **Semantic conventions (SC-2 … SC-8).** The YAML registry `spec/semconv/` becomes normative for key names, types, value lists and validators (MET-10). The planned modality namespaces are reserved (MET-3). String keys of 3.4 are non-empty (MET-7). Each listed value set is open or closed (MET-8). Counts and indices have no unit (MET-9). SC-1 (modality keys) stays open.

## Motivation
- A field type that no validator checks is not a rule in practice. Two producers can write `reason: 7` and `reason: "gap"`, and both pass. A consumer that reads `reason` as a string then fails at run time.
- The validators and the generated JSON Schema gave different verdicts on the same data (RC3 proto README section 9). A conformance claim must not depend on the tool.
- The registry work (P1-04) found seven places where the spec was silent or disagreed with the validators (SC-2 … SC-8). A registry that is "the machine-readable form" but not normative cannot settle a difference.

## Proposal
Normative text: RC4 sections 1.6 (summary table), 3.4 (MET-3, MET-7 … MET-10) and the rules named below.

| Rule | Change |
|---|---|
| GEN-11 (new) | An optional field of a field table MUST have the table type when present. Not for a field of another profile (PRF-5) or an unknown key (GEN-4). |
| HDR-16 (new) | Header `vocab_id`, `vocab_version`: string or null. |
| SEG-6 | `segment_end.reason` is a string (now checked). |
| SQ-1 | `signal_quality.channels` is a list of numbers (now checked). |
| DEC-6 (new) | `score` (number or null) and `score_range` (two numbers) have their types for every `score_semantics`, also an unknown one. |
| HYP-5 (new) | `hypothesis.t_start`, `t_end` numbers; `revision_of` string or null; `nbest[].spans` objects with typed keys. |
| PTR-1 | `pointer.absent` is a list of `dims` booleans; `score_semantics` (not null) and DEC-2 … DEC-6 apply. |
| TIM-4 | The latency fields are numbers on every event of registry 12.1, frames included. |
| TD-F2 | `trust_decision.reason` is a string. |
| INT-T8 (new) | Intent decision `vocab_id`, `pending_cleared`: strings. |
| CTL-T8 | `level` is a number in (0, 1) also without `radius`. 7.4.5 lists the control decision `t` (number). |
| MET-3 | The planned namespaces `emg`, `eeg`, `meg`, `fnirs`, `implant` are reserved (SC-2). |
| MET-7 (new) | A "non-empty string" key MUST NOT be `""` (SC-3). |
| MET-8 (new) | `enum` keys have closed lists; open lists name registered values and allow others (SC-4). |
| MET-9 (new) | Only physical quantities have a unit; times are seconds (SC-6). |
| MET-10 (new) | The YAML registry is normative; the spec tables are informative copies, checked equal in CI (SC-7, SC-8). |

SC-5 (target stability of the `input` and `declaration` keys) is an entry of section 2.3: Development. SC-1 (modality keys) is deferred to a FEP that has evidence from real producers (A.8).

## Examples
Refused by RC4 validators (accepted by RC3 validators, refused by the RC3 JSON Schema):

```json
{"type": "segment_end", "t": 0.1, "unit": "utterance", "reason": 7}
{"type": "trust_decision", "spec_version": "1.0", "session": "s1", "seq": 0, "utterance": 0, "is_final": true, "action": "COMMIT", "shown": ["ab"], "p_top1": 0.9, "score_semantics": "calibrated_prob", "reason": 0}
```

Accepted, with a warning (MET-3, vector V69): a header `meta` with the custom key `"emg.gain_db": 20.0`.

## Compatibility
- **No valid data changes.** Every RC3 vector keeps its verdict. Each new check refuses only a value that the generated JSON Schema already refused, so the 103 accept vectors and the reference producers are not affected.
- **Validators are stricter** for wrongly typed optional fields (in all spec versions, as for GEN-10 in RC3). A producer outside this repository that wrote such a field gets a reject. We prefer this to leniency because the field table already gave the type, and because the schema already refused the data.
- **SC-2** adds a warning, never a reject. **SC-3** writes down what the validators already did. **SC-4 … SC-8** change no verdict.
- Stability: GEN-11 is part of the proposed Stable core (4.1). MET-7 … MET-10 are part of the proposed Stable `meta` conventions (2.3).

## Reference implementation
- Python: `fidetype.conformance.checks` (`_score_errors`, `_span_errors`, NTS-VOCAB-ID, NTS-EVT-*, `PLANNED_NAMESPACES`), `fidetype.conformance.io` (`TIMING_KEYS`, `TIMED_TYPES`, `RawStream.timed`), the profile checks in `profiles/fep0001.py`, `fep0003.py`, `fep0005.py`.
- TypeScript: `checks.ts`, `raw.ts`, `constants.ts` (`PLANNED_NAMESPACES`, `TIMING_KEYS`, `TIMED_TYPES`), `profiles/fep0001.ts`, `fep0003.ts`, `fep0005.ts`.
- Rust: `checks.rs`, `raw.rs`, `constants.rs`, `profiles/fep0001.rs`, `fep0003.rs`, `fep0005.rs`.
- Registry: `spec/semconv/manifest.yaml` (resolved questions, RC4 document), attribute field `registered_values` (open lists), `tools/semconv/semconv.py` (spec type "non-empty string", planned-namespace check of the SDKs).
- Proto: `TrustDecision.t` has `json_profile = "control"`.
- Vectors: V69 … V82, F63 … F66, D24 … D26, I25, C25, E25 … E27 (330 in all). Python = TypeScript = Rust on all 330 vectors and on 26,687 fuzz mutants (seeds 1–3, `--n 30`). JSON Schema: 201 of 201 one-line verdicts.

## Alternatives
- **Leave the optional types unchecked** and say so in the spec. Rejected: the tables would then not be rules, and the schema and the validators would keep giving different verdicts.
- **Accept `""` for string keys (SC-3)** and relax the validators. Rejected: an empty name or id carries no information, and the change would turn existing reject verdicts into accepts for no user.
- **Make the prose tables normative (SC-7).** Possible, because the CI check keeps the two forms equal. Rejected because the registry holds more (validator, requirement level, stability), tools and SDKs read it, and later keys (SC-1) need one place to go.
- **Close every value list (SC-4).** Rejected for regulatory status, calibration method, input route and check mode: producers have values that we cannot list now, and no consumer acts on them.

## Privacy and leakage
No new field. `reason` codes and `pending_cleared` stay short codes or ids, not user text (SEC-5).

## Open questions
- SC-1: which modality keys, with which types and units (needs the P4 adapters). *Partly answered by [FEP-0009](0009-modality-semantic-conventions.md) (2026-11-16): keys for `emg`, `meg`, `implant`; `eeg` and `fnirs` open as SC-9.*
- G-13: may a frame carry both the dense and the sparse form (FRM-2)? Should the JSON Schema allow `absent: null` on control events (GEN-9)? *2026-11-16: the second part is closed (proto option `json_null_list`, vector C26). The first part needs a design decision; the options A1 … A3 are in [RC4 C.2](../nts-1.0-rc4.md#c2-gaps).*
