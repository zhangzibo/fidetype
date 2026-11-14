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
- Packaging for PyPI (P2): complete metadata, `py.typed`, PyPI README with absolute links, console script `fidetype-collector`.
- The wheel ships the golden conformance vectors (`fidetype/_spec/conformance`), so `fidetype conformance --profile <name>` works without a repository checkout.

### Changed
- The package version has one source: `__version__` in `src/fidetype/__init__.py`.

## [0.0.1] - not published

First development version. It was never published to PyPI. It has:
- NeuralTextStream v0.1 reader, writer and validator; NTS 1.0 RC2 header and decision `spec_version` support.
- Trust core and streaming trust layer (calibration, conformal sets, COMMIT / OFFER / ASK / ABSTAIN), intent (FEP-0003) and control (FEP-0005) trust layers.
- Conformance suite with the v0.1 and fep-0001 … fep-0005 profiles.
- Adapters: Lab Streaming Layer (`[lsl]`), BrainFlow bridge (`[brainflow]`), WebSocket (`[ws]`).
- Open benchmark v0.1 harness, provenance ledger, collector v0 (FEP-0006), offline demo.
- Console script `fidetype`.
