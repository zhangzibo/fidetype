# Changelog: `fidetype` (Rust crate)

This file lists the changes of the Rust SDK (crate `fidetype`). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/) with the 0.x rules in [docs/RELEASING.md](../../docs/RELEASING.md). Spec changes are in [spec/CHANGELOG.md](../../spec/CHANGELOG.md).

## [Unreleased]

### Added
- Packaging for crates.io (P2): `homepage`, `documentation`, `rust-version`, `include` whitelist, docs.rs settings (all features, `docsrs` cfg), `LICENSE` in the crate.

### Changed
- `SDK_VERSION` comes from `CARGO_PKG_VERSION`, so `Cargo.toml` is the one source of the version.
- `publish = false` is removed. Publishing is still a maintainer decision (see docs/RELEASING.md).

## [0.1.0] - not published

First development version (M7-07). It was never published to crates.io. It has:
- `no_std` + `alloc` core: parse, check, write, decide. Feature `std` (default): file and stream I/O, the CLI `fidetype-rs` and the example.
- Readers for JSON Lines and NPZ, the v0.1 checks, `trust_decision` rules of FEP-0001 / 0003 / 0005, `DecisionTracker`, NTS 1.0 RC2 header `spec_version` support.
- Conformance runner for v0.1 and fep-0001 … fep-0005.
