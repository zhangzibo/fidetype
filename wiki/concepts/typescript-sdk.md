---
title: TypeScript SDK
type: concept
tags: [sdk, typescript, browser, neuraltextstream, conformance, trust, schemas, m7]
sources: []
updated: 2026-11-13
---

# TypeScript SDK

Task **M7-06**. The second reference SDK, after the [Python SDK](python-sdk.md). It lives in [`sdk/typescript/`](../../sdk/typescript/README.md) (package `@fidetype/sdk`, private, not on npm). It runs in Node (>= 18) and in the browser (ESM). The core has zero runtime dependencies and no Node API.

## What it gives

| Job | API |
|---|---|
| Write a stream | `NtsWriter` (one checked event per line), `toJsonl` |
| Read a stream | `parseNtsText`, `readNtsEvents` (byte or text stream, chunk borders and UTF-8 handled), `validateNtsStream` |
| Accept or reject a file | `loadStream(name, bytes)`: port of the reference consumer `load_stream` (JSON Lines **and** NPZ; own ZIP/DEFLATE/NPY reader) |
| Check a file | `checkStream`: the 60 checks of the [conformance suite](conformance-suite.md), levels core / trust-ready / provenance / advisory |
| Check a live stream | `StreamValidator`: the event checks of the [streaming trust layer](streaming-trust-layer.md) `push` (header first, increasing t, normalised rows, valid n-best) |
| Act on decisions | `DecisionTracker`: per `trust_decision` the kind (commit, offer, ask, abstain, preview), the committed text or intent, `forward`, errors (FEP-0001 rules 5-8) and warnings (rule 9: empty final COMMIT) |
| Conformance | `runVectors`: the golden vectors in `spec/conformance/` for `v0.1`, `fep-0001`, `fep-0002`, [`fep-0003`](intent-events.md) |

## Schemas are the source of truth
- New structural JSON schemas (draft 2020-12): `spec/schemas/nts-v0.1/` (7 event kinds) and `spec/schemas/fep-0001/` (segment_end, n-best item, decode_declaration, trust_decision), next to `spec/schemas/fep-0003/`.
- A generator writes the TypeScript types and an embedded copy of the schemas. `npm run check:schemas` fails on drift; the build and CI run it.
- A test validates every event of every accepted JSON Lines vector against its schema, and checks that the structural reject vectors break it.

## Parity with Python

| Profile | Vectors | TypeScript pass | Same verdict as Python |
|---|---|---|---|
| v0.1 (NPZ + JSON Lines) | 52 | 52 | 52/52 |
| fep-0001 | 40 | 40 | 40/40 |
| fep-0002 (LSL scenarios) | 31 | 31 | 31/31 |
| fep-0003 | 44 | 44 | 44/44 |

- `npm run cross-check` runs both reference consumers on every vector and compares verdict and "ok".
- `npm run fuzz` mutates the JSON vectors (fixed seed). Two runs, about 4,000 mutants each: identical verdicts. The first fuzz runs found 6 differences (Python iterates strings and dicts; NumPy converts sample strings late). All are fixed.
- The Python suite can also run the TS consumer: `python -m fidetype.conformance consumer --cmd "node sdk/typescript/bin/fidetype-ts.mjs consume {path}"` (52/52; fep-0002 31/31).
- A headless Edge run of all 167 vectors (NPZ included) passed. So the core works in a browser.

> **Our take:** Identical verdicts need the Python data model, not only the rules. Python keeps `1.0` (float) apart from `1` (int), and the profiles reject `1.0` where an integer is required. The SDK's own JSON parser records float literals for this reason. A plain `JSON.parse` port gives different verdicts on such input. A future spec version should state the rule (for example "an integer is written without a fraction or exponent"), so that every SDK can follow the text.

> **Our take:** The `fep-0002` reference consumer runs the full trust layer, so its expected values include decision counts. The SDK uses a structural model (same event checks, same counts, no decoding, no policy). This is enough to check an LSL producer. A TypeScript trust layer is a separate, larger task.

## Layout decision
`sdk/typescript/` at the top level, not under `src/`: the repo root is the Python package, and the roadmap phase P2 adds more SDKs (for example Rust, M7-07). Each SDK reads `spec/` in place.

## Open items
- npm publishing: a user decision (name, scope, versioning policy, trusted publishing; compare M7-09 for PyPI).
- The offline demo (`demo/index.html`) is not wired to the SDK. It runs from `file://`, which cannot load ES modules; it would need a bundle.
- Parity fuzz covers JSON vectors only, not NPZ.

Related: [Python SDK](python-sdk.md), [conformance suite](conformance-suite.md), [streaming trust layer](streaming-trust-layer.md), [LSL input](lsl-input.md), [intent events](intent-events.md).
