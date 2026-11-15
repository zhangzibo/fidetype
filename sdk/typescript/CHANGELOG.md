# Changelog: `@fidetype/sdk` (TypeScript SDK)

This file lists the changes of the TypeScript SDK (npm package `@fidetype/sdk`). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/) with the 0.x rules in [docs/RELEASING.md](../../docs/RELEASING.md). Spec changes are in [spec/CHANGELOG.md](../../spec/CHANGELOG.md).

## [Unreleased]

### Added
- `NtsWriter` accepts `vocab: []` (a hypothesis-only or control-only stream, spec HDR-12). `blank_id` must then be `null` (HDR-6). With an empty vocab the writer refuses every frame: `frame()` and `event({ type: "frame" })` throw `RangeError` (HDR-12). Same behaviour and messages as the Python and Rust writers.
- Tests: the empty-vocab writer stream (same events and key order as Python and Rust) and its refusals. Vectors V62-V65 run in the v0.1 suite (65 vectors).
- Packaging for npm (P2): `repository`, `homepage`, `bugs`, `keywords`, `publishConfig` (public access, npm provenance), `./package.json` export, `LICENSE` in the package.
- `npm run check:version`: `package.json` version = `SDK_VERSION`; `LICENSE` = repository `LICENSE`. `prepack` cleans `dist/`, builds and runs this check.
- `fidetype-ts conformance` gives a clear error when the golden vectors are not present (the npm package does not ship them; pass `--vectors DIR`).

### Changed
- `extraHeader` must not hold a key that the writer sets itself (`type`, `spec_version`, `vocab`, `vocab_type`, `blank_id`, `source`, `frame_period`, `latency`, `meta`; exported as `HEADER_KEYS`). Before, it could overwrite them and so skip the checks.
- `segmentEnd(t, unit)` checks `unit` at run time (`utterance`, `word`, `trial`; SEG-5).
- The `files` whitelist ships only `dist/**/*.js`, `dist/**/*.d.ts`, `bin/`, `README.md`, `CHANGELOG.md` and `LICENSE`.
- `private: true` is removed. Publishing is still a maintainer decision (see docs/RELEASING.md).

## [0.1.0] - not published

First development version (M7-06). It was never published to npm. It has:
- Writer, reader, reference consumer (JSON Lines and NPZ), the 59 v0.1 checks, JSON Schema validation and generated types.
- `DecisionTracker` and `trust_decision` helpers for the text, intent and control profiles; NTS 1.0 RC2 header `spec_version` support.
- Conformance runner for v0.1 and fep-0001 … fep-0005 (Node entry `@fidetype/sdk/node`); WebSocket client (FEP-0004).
- CLI `fidetype-ts` (conformance, validate, consume, decisions). ESM only; Node >= 18 and browsers.
