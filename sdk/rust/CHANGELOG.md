# Changelog: `fidetype` (Rust crate)

This file lists the changes of the Rust SDK (crate `fidetype`). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/) with the 0.x rules in [docs/RELEASING.md](../../docs/RELEASING.md). Spec changes are in [spec/CHANGELOG.md](../../spec/CHANGELOG.md).

## [Unreleased]

### Added
- **NTS 1.0 RC3, unknown enumeration values (VER-6 … VER-10, FEP-0007).** New helpers `constants::is_newer_minor`, `json::enum_ok`, `json::is_unknown`, `json::newer_minor`. In data whose governing version is a newer minor version (`"1.1"` …), every validator accepts an unknown enumeration string; 0.1 and 1.0 data still refuse it. Comparison rules skip unknown values. Same behaviour as Python and TypeScript (vectors V66-V68, F57-F59, I24, D22, D23, C24, E22-E24).
- `DecisionKind::Unknown` (name `"unknown"`): a valid decision with an unknown `action` or `profile`; never forwarded. `forward` is false for an intent COMMIT with an unknown `risk_class`, `role` or `confirmed_via`, and for a control COMMIT with an unknown `state` (VER-10).
- `profiles::fep0001::is_text_decision`, `profiles::fep0003::unknown_intent_values`.
- `NtsWriter` accepts `vocab: Some(vec![])` (a hypothesis-only or control-only stream, spec HDR-12). `blank_id` must then be `None` (HDR-6). With an empty vocab the writer refuses every frame: `frame_log_probs`, `frame_probs`, `frame_logits` and `event` with `type = "frame"` return a `Usage` error (HDR-12). Same behaviour and messages as the Python and TypeScript writers.
- Tests: the empty-vocab writer stream (same events and key order as Python and TypeScript) and its refusals. Vectors V62-V65 run in the v0.1 suite (65 vectors).
- Packaging for crates.io (P2): `homepage`, `documentation`, `rust-version`, `include` whitelist, docs.rs settings (all features, `docsrs` cfg), `LICENSE` in the crate.

### Changed
- **Breaking (0.x):** `validate_intent_declaration`, `validate_intent_event`, `validate_feedback_event`, `validate_control_declaration`, `validate_control_event` and `validate_enable_event` take a `lenient: bool` argument (VER-8). Pass `false` for the RC2 behaviour.
- **GEN-10 (RC3):** `Value::is_int` is false for a value above 2^53 - 1 in magnitude (`constants::MAX_JSON_INT`). Before, such values were accepted. Vectors F60, F61, W44.
- **TD-F2 (RC3):** a `trust_decision` whose `declaration` is not an object is refused (vector F62).
- **PRF-4 (RC3):** the text "acted" lists and `committed_text` use only decisions with `profile` absent or `"text"`. `moving_ticks` lists only COMMITs with a known moving state; after a control decision with an unknown state the control counts as not engaged (CTL-S7, vector E24).
- Tests: vector counts 68 / 62 / 35 / 47 / 44 / 48 (304). V66 (1.1, unknown `vocab_type`) is refused by the streaming header check, which is the trust-layer check (VER-10 allows a stop).
- `extra_header` must not hold a key that the writer sets itself (`writer::HEADER_KEYS`). Before, it could overwrite them and so skip the checks.
- `SDK_VERSION` comes from `CARGO_PKG_VERSION`, so `Cargo.toml` is the one source of the version.
- `publish = false` is removed. Publishing is still a maintainer decision (see docs/RELEASING.md).

## [0.1.0] - not published

First development version (M7-07). It was never published to crates.io. It has:
- `no_std` + `alloc` core: parse, check, write, decide. Feature `std` (default): file and stream I/O, the CLI `fidetype-rs` and the example.
- Readers for JSON Lines and NPZ, the v0.1 checks, `trust_decision` rules of FEP-0001 / 0003 / 0005, `DecisionTracker`, NTS 1.0 RC2 header `spec_version` support.
- Conformance runner for v0.1 and fep-0001 … fep-0005.
