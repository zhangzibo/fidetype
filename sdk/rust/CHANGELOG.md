# Changelog: `fidetype` (Rust crate)

This file lists the changes of the Rust SDK (crate `fidetype`). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/) with the 0.x rules in [docs/RELEASING.md](../../docs/RELEASING.md). Spec changes are in [spec/CHANGELOG.md](../../spec/CHANGELOG.md).

## [Unreleased]

### Added
- `NtsWriter` accepts `vocab: Some(vec![])` (a hypothesis-only or control-only stream, spec HDR-12). `blank_id` must then be `None` (HDR-6). With an empty vocab the writer refuses every frame: `frame_log_probs`, `frame_probs`, `frame_logits` and `event` with `type = "frame"` return a `Usage` error (HDR-12). Same behaviour and messages as the Python and TypeScript writers.
- Tests: the empty-vocab writer stream (same events and key order as Python and TypeScript) and its refusals. Vectors V62-V65 run in the v0.1 suite (65 vectors).
- Packaging for crates.io (P2): `homepage`, `documentation`, `rust-version`, `include` whitelist, docs.rs settings (all features, `docsrs` cfg), `LICENSE` in the crate.

### Changed
- `extra_header` must not hold a key that the writer sets itself (`writer::HEADER_KEYS`). Before, it could overwrite them and so skip the checks.
- `SDK_VERSION` comes from `CARGO_PKG_VERSION`, so `Cargo.toml` is the one source of the version.
- `publish = false` is removed. Publishing is still a maintainer decision (see docs/RELEASING.md).

## [0.1.0] - not published

First development version (M7-07). It was never published to crates.io. It has:
- `no_std` + `alloc` core: parse, check, write, decide. Feature `std` (default): file and stream I/O, the CLI `fidetype-rs` and the example.
- Readers for JSON Lines and NPZ, the v0.1 checks, `trust_decision` rules of FEP-0001 / 0003 / 0005, `DecisionTracker`, NTS 1.0 RC2 header `spec_version` support.
- Conformance runner for v0.1 and fep-0001 … fep-0005.
