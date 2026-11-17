# Changelog: `fidetype` (Python package)

This file lists the changes of the Python package `fidetype` (PyPI). Other parts of the project have their own changelogs:

| Part | Changelog |
|---|---|
| NeuralTextStream spec | [spec/CHANGELOG.md](spec/CHANGELOG.md) |
| TypeScript SDK `@fidetype/sdk` | [sdk/typescript/CHANGELOG.md](sdk/typescript/CHANGELOG.md) |
| Rust SDK `fidetype` (crate) | [sdk/rust/CHANGELOG.md](sdk/rust/CHANGELOG.md) |

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/) with the 0.x rules in [docs/RELEASING.md](docs/RELEASING.md).

## [Unreleased]

### Added
- **Drift tests (P5-09, P5-10), all opt-in; defaults unchanged.** `ConformalDriftTest(spread=True)` (also `DriftMonitor(spread=)`, `PersonalTrust(spread=)`) adds the betting functions `1 + eps * (|2p - 1| - 1/2)`, so a change of spread at the same centre raises an alarm; the anytime false-alarm bound stays the same. `PersonalTrust(guard_risk_test=True, level_guard_risk=, on_guard_risk_drift=)` runs a third conformal drift test on the guard risk (then `P(any false alarm) <= level_scores + level_risk + level_guard_risk`); `PersonalTrust.drift_summary()`. `calibration_stats` now also writes `reference_guard_risk` (the guard risk of the sampled reference items; no text), and `UserProfile.reference_guard_risk` reads it. Docs: [docs/trust-personalisation.md](docs/trust-personalisation.md) sections 4.1 and 4.2.
- **NTS 1.0 RC4, optional field types (GEN-11, gap G-12, FEP-0008).** The conformance checks refuse a wrongly typed optional field: `segment_end.reason` (FEP1-SEGMENT); `hypothesis.t_start`, `t_end`, `revision_of` and `nbest[].spans` (NTS-EVT-HYPOTHESIS); `signal_quality.channels`; `pointer.absent`, `score`, `score_semantics` (null refused); `decision.score` and `score_range` for every semantics, also an unknown one (DEC-6); header `vocab_id` and `vocab_version` (NTS-VOCAB-ID, new title); `trust_decision.reason` (all profiles); intent `vocab_id`, `pending_cleared` (INT-T8); control `level` without `radius` (CTL-T8). The latency fields (TIM-4) are checked on every event of registry 12.1, frames included (`fidetype.conformance.io.TIMING_KEYS`, `TIMED_TYPES`, `RawStream.timed`). Vectors V69-V82, F63-F66, D24-D26, I25, C25, E25-E27 (330 in all); same behaviour as the TypeScript and Rust SDKs.
- **NTS 1.0 RC4, MET-3 (SC-2):** `fidetype.conformance.checks.PLANNED_NAMESPACES` (`emg`, `eeg`, `meg`, `fnirs`, `implant`). A custom `meta` key in a planned namespace gets the NTS-NAMESPACE warning (advisory).
- `tools/semconv/semconv.py`: the spec type "non-empty string", the attribute field `registered_values` (open lists, SC-4), `resolved_questions` in the manifest, and a check that the three SDKs list the same planned namespaces as the registry.
- **NTS 1.0 RC3, unknown enumeration values (VER-6 … VER-10, FEP-0007).** New helpers `fidetype.streams.spec.is_newer_minor`, `enum_ok`, `is_unknown`. In data whose governing version is a newer minor version (`"1.1"` …), every conformance check accepts an unknown enumeration string (header, event, decision, intent and control declaration values); `"0.1"` and `"1.0"` data still refuse it. Comparison rules skip unknown values. The consumers never act on them (VER-10): no actuation of an intent COMMIT with an unknown `risk_class`, `role` or `confirmed_via`; no motion on an unknown control state; after an unknown state the control counts as not engaged (CTL-S7). Vectors V66-V68, F57-F59, I24, D22, D23, C24, E22-E24; same behaviour as the TypeScript and Rust SDKs.
- The validators of `fidetype.trust.intent` (`validate_intent_declaration`, `validate_intent_event`, `validate_feedback_event`) and `fidetype.trust.control` (`validate_control_declaration`, `validate_control_event`, `validate_enable_event`, `ControlDeclaration.from_declaration`) take an optional `lenient` argument (default `False`, the RC2 behaviour). The reference trust layers stay strict.
- `StreamWriter(vocab=[])` writes a hypothesis-only (or control-only) stream, as spec HDR-12 allows. `blank_id` must then be `None` (HDR-6). With an empty vocab the writer refuses every frame: `frame()` (all three input forms), `frames()` and `event({"type": "frame", ...})` raise `ValueError` (HDR-12).
- `StreamWriter(extra_header={...})` adds header keys (for example `clock_domain`, `decode_declaration`) before `meta`, like `extraHeader` (TypeScript) and `extra_header` (Rust). It must not hold a key that the writer sets itself.
- `StreamWriter.segment_end(t, unit=...)`: `unit` is `utterance`, `word` or `trial` (SEG-5), as in the TypeScript and Rust writers.
- Conformance vectors V62-V65 (`spec/conformance/v0.1`, 65 vectors now): empty vocab with hypotheses only (accept); empty vocab with a dense frame, with a sparse frame, or with `blank_id` 0 (reject).
- Packaging for PyPI (P2): complete metadata, `py.typed`, PyPI README with absolute links, console script `fidetype-collector`.
- The wheel ships the golden conformance vectors (`fidetype/_spec/conformance`), so `fidetype conformance --profile <name>` works without a repository checkout.

### Changed
- **GEN-10 (RC3):** a JSON integer above 2^53 - 1 in magnitude is not an integer. The conformance readers parse with the `json_int` hook (`fidetype.streams.spec.json_int`, `MAX_JSON_INT`), which turns such a literal into a float, so every integer check refuses it. Vectors F60, F61, W44.
- **TD-F2 (RC3):** a `trust_decision` whose `declaration` is not an object is refused (vector F62).
- **PRF-4 (RC3):** the text "acted" lists of the `fep-0001` and `fep-0003` consumers (and `offered`, TD-12) use only decisions with `profile` absent or `"text"` (`fep0001.is_text_decision`). A final COMMIT of an unknown profile is never acted on.
- The package version has one source: `__version__` in `src/fidetype/__init__.py`.
- `fidetype.adapters.text_nbest` writes through `StreamWriter` (`vocab = []`) instead of its own JSON Lines. The output is equivalent: the same events and values; only a `segment_end` with a time now has the key order `type`, `t`, `unit` (the writer order in all three SDKs). All checks still run before the file is written.
- `NTS-NORM` reports a frame of a stream with an empty vocab as not normalised (log-sum-exp -inf), as TypeScript and Rust do. Before, the check raised an internal error (same verdict).

## [0.0.1] - not published

First development version. It was never published to PyPI. It has:
- NeuralTextStream v0.1 reader, writer and validator; NTS 1.0 RC2 header and decision `spec_version` support.
- Trust core and streaming trust layer (calibration, conformal sets, COMMIT / OFFER / ASK / ABSTAIN), intent (FEP-0003) and control (FEP-0005) trust layers.
- Conformance suite with the v0.1 and fep-0001 … fep-0005 profiles.
- Adapters: Lab Streaming Layer (`[lsl]`), BrainFlow bridge (`[brainflow]`), WebSocket (`[ws]`).
- Open benchmark v0.1 harness, provenance ledger, collector v0 (FEP-0006), offline demo.
- Console script `fidetype`.
