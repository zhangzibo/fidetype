# Changelog: `@fidetype/sdk` (TypeScript SDK)

This file lists the changes of the TypeScript SDK (npm package `@fidetype/sdk`). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/) with the 0.x rules in [docs/RELEASING.md](../../docs/RELEASING.md). Spec changes are in [spec/CHANGELOG.md](../../spec/CHANGELOG.md).

## [Unreleased]

### Added
- Packaging for npm (P2): `repository`, `homepage`, `bugs`, `keywords`, `publishConfig` (public access, npm provenance), `./package.json` export, `LICENSE` in the package.
- `npm run check:version`: `package.json` version = `SDK_VERSION`; `LICENSE` = repository `LICENSE`. `prepack` cleans `dist/`, builds and runs this check.
- `fidetype-ts conformance` gives a clear error when the golden vectors are not present (the npm package does not ship them; pass `--vectors DIR`).

### Changed
- The `files` whitelist ships only `dist/**/*.js`, `dist/**/*.d.ts`, `bin/`, `README.md`, `CHANGELOG.md` and `LICENSE`.
- `private: true` is removed. Publishing is still a maintainer decision (see docs/RELEASING.md).

## [0.1.0] - not published

First development version (M7-06). It was never published to npm. It has:
- Writer, reader, reference consumer (JSON Lines and NPZ), the 59 v0.1 checks, JSON Schema validation and generated types.
- `DecisionTracker` and `trust_decision` helpers for the text, intent and control profiles; NTS 1.0 RC2 header `spec_version` support.
- Conformance runner for v0.1 and fep-0001 … fep-0005 (Node entry `@fidetype/sdk/node`); WebSocket client (FEP-0004).
- CLI `fidetype-ts` (conformance, validate, consume, decisions). ESM only; Node >= 18 and browsers.
