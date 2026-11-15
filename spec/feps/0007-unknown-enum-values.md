# FEP-0007: Unknown enumeration values (forward compatibility with a safe fallback)

| | |
|---|---|
| **FEP** | 0007 |
| **Title** | Unknown enumeration values: version-gated acceptance with a safe fallback per enumeration |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft (folded into [NTS 1.0 RC3](../nts-1.0-rc3.md), section 11.2.1; reference implementation and vectors in Python, TypeScript and Rust) |
| **Type** | Spec change |
| **Affects** | NTS 1.0 RC2 sections 11.1, 11.2 (VER-3), 12.2, 12.3 and every rule that lists allowed values (HDR-5, HDR-11, SEG-5, SQ-1, DEC-*, TD-F1, PRF-4, INT-*, CTL-*) |
| **Created** | 2026-11-15 |
| **Discussion** | Open question Q-7 of the P1-02 protobuf work ([CHANGELOG](../CHANGELOG.md)) |

## Summary
A minor version may add values to a registry (11.1). RC2 said two things that do not fit together: a 1.0 consumer reads a newer minor version with the 1.0 rules and ignores what it does not know (VER-3), and a 1.0 consumer MUST refuse an unknown value (HDR-5, TD-F1 and others). This FEP makes the answer depend on the **governing version** of the data. In data of a version that the consumer implements, an unknown value stays an error. In data of a newer minor version, the consumer accepts the value, keeps it as "unknown", and applies a **safe fallback** that never causes an action.

## Motivation
- Without a rule, a 1.1 producer that uses a new `action` or a new control `state` breaks every 1.0 consumer. That stops the 1.x compatibility promise (11.3).
- The opposite rule, "ignore every unknown value", is not safe. NTS decisions move cursors and actuate intents. An unknown control `state` or an unknown intent `risk_class` must never cause motion or an irreversible action.
- Proto3 enums are already open (the binary form keeps an unknown number). The JSON form needs the same behaviour, with explicit safety.

## Proposal
Normative text: RC3 section 11.2.1 (rules VER-6 … VER-10) and the "Safe fallback" column of registry 12.3. In short:

1. **VER-6, VER-7.** The governing version of a `trust_decision` is its own `spec_version` (absent = `"0.1"`); for every other event it is the header `spec_version`. If the consumer implements that version, an unknown value is an error (as in RC2).
2. **VER-8.** In data of a newer minor version, a JSON string that is not a known value is accepted. The consumer keeps it as unknown, applies the fallback, and does not apply rules that compare the unknown value with other values. A value of another JSON type is an error at every version.
3. **VER-9.** Binding enumerations stay closed: they follow the binding version.
4. **VER-10.** A fallback never adds an action. A trust layer or bridge that cannot apply a fallback stops acting on the stream.

Fallbacks (full list in 12.3):

| Value | Safe fallback |
|---|---|
| `trust_decision.action`, `profile` | Non-acting, as `ABSTAIN` |
| Intent `risk` / `risk_class`, `role`, `confirmed_via` | `irreversible` / not actuated / as `null` / not actuated |
| Control `state`; `quantity`, `frame`, `units`, `uncertainty` | Zero velocity and not engaged; no motion on the stream |
| `control_enable.source` | A stop is a stop; an engage is not an engage |
| `intent_feedback.outcome` | Never confirms; drops an armed intent |
| `score_semantics` | Not a probability (DEC-1, INT-S2) |
| `vocab_type`, `clock_domain`, `device.modality`, `signal_quality.unit` | Read as `other` (no typed text from unknown tokens; no clock comparison; never good signal) |

## Examples
A 1.0 consumer reads this 1.1 decision log (vector D22):

```json
{"type": "trust_decision", "spec_version": "1.1", "profile": "intent", "session": "u1", "seq": 0, "unit": 0, "is_final": true, "action": "COMMIT", "risk_class": "critical", "intent": "intent.menu", "p_top1": 0.97, "score_semantics": "calibrated_prob"}
{"type": "trust_decision", "spec_version": "1.1", "profile": "intent", "session": "u1", "seq": 3, "unit": 2, "is_final": true, "action": "COMMIT", "risk_class": "undoable", "intent": "intent.select", "p_top1": 0.97, "score_semantics": "calibrated_prob"}
```

It accepts both lines. It actuates only `intent.select`. The same first line with `"spec_version": "1.0"` is refused (vector D23).

## Compatibility
- Producers: no change for 0.1 and 1.0 producers.
- Consumers: every RC2 reject vector stays a reject; data of a newer minor version is now accepted where RC2 refused it.
- Stability: the rules are part of the proposed Stable versioning section (11).

## Reference implementation
- Python: `fidetype.streams.spec.is_newer_minor`, `enum_ok`; the validators of `fidetype.conformance` and `fidetype.trust.intent` / `.control` (`lenient`).
- TypeScript: `isNewerMinor`, `enumOk`, `isUnknown` (`constants.ts`); the profile validators; `DecisionTracker` kind `unknown`.
- Rust: `constants::is_newer_minor`, `json::{enum_ok, is_unknown, newer_minor}`; the profile validators; `DecisionKind::Unknown`.
- Generated JSON Schema: enumeration fields accept any string; `Header.known` and `TrustDecision.known` require known values unless `spec_version` is a newer minor version.
- Vectors: V66 … V68, F57 … F59, I24, D22, D23, C24, E22 … E24. Python = TypeScript = Rust on all 304 vectors and on the fuzz mutants.

## Alternatives
- **Refuse every unknown value (RC2 text).** Safe, but no 1.x forward compatibility. Rejected.
- **Map every unknown value to `other`.** Most enumerations have no `other`, and for actions or states a mapping to a known value would act. Rejected.
- **Ignore the whole event.** Loses data (for example a whole header), and an ignored stop could be unsafe. Rejected in favour of per-enumeration fallbacks.
- **Accept unknown values at every version.** Turns producer errors in 1.0 data into silent fallbacks. Rejected: the version gate keeps the validators strict where the producer claims a version they know.
- Other standards: proto3 open enums and OpenTelemetry's "unknown values MUST be handled" guidance follow the same idea (keep, do not act on).

## Privacy and leakage
No new field. An unknown value is a registry string, not user text.

## Open questions
- Should a validator give an advisory warning (not a failure) for each unknown value in newer-minor data?
- Should the reference trust layers apply the fallbacks instead of refusing the stream (VER-10 allows both)?
