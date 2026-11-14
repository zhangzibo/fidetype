---
title: Rust SDK
type: concept
tags: [sdk, rust, embedded, no-std, neuraltextstream, conformance, trust, m7]
sources: []
updated: 2026-11-13
---

# Rust SDK

Task **M7-07**. The third reference SDK, after the [Python SDK](python-sdk.md) and the [TypeScript SDK](typescript-sdk.md). It lives in [`sdk/rust/`](../../sdk/rust/README.md) (crate `fidetype`, `publish = false`, not on crates.io). Its target is device firmware and embedded paths: the core is `no_std` + `alloc`, and a feature `std` (on by default) adds file I/O, the CLI `fidetype-rs` and an example program.

## What it gives

| Job | API |
|---|---|
| Write a stream | `NtsWriter` (one checked event per line; the sink is a closure, for example a UART), `to_jsonl`; `npz::write_npz` (stored NPZ, as `numpy.savez`) |
| Read a stream | `parse_nts_text`, `LineSplitter` and `EventReader` (byte chunks, strict UTF-8 across chunk borders) |
| Accept or reject a file | `load_stream(name, bytes)`: port of the reference consumer (JSON Lines **and** NPZ; own ZIP / DEFLATE / NPY code) |
| Check a file | `check_stream`: the 59 checks of the [conformance suite](conformance-suite.md), levels core / trust-ready / provenance / advisory |
| Check a live stream | `StreamValidator`: the event checks of the [streaming trust layer](streaming-trust-layer.md) `push` |
| Act on decisions | `DecisionTracker`: kind, committed text or intent, `forward`, errors (FEP-0001 rules 5-8), warnings (rule 9: empty final COMMIT) |
| Conformance | `conformance::run_vectors` over `spec/conformance/` for `v0.1`, `fep-0001`, `fep-0002` ([LSL](lsl-input.md) scenarios), `fep-0003` ([intent events](intent-events.md)) |

## Parity with Python

| Profile | Vectors | Rust pass | Same verdict and "ok" as Python | Fuzz mutants, same verdict (seeds 1-4, `--n 30`) |
|---|---|---|---|---|
| v0.1 (NPZ + JSON Lines) | 52 | 52 | 52/52 | 2,341/2,341 |
| fep-0001 | 40 | 40 | 40/40 | 4,800/4,800 |
| fep-0002 (LSL scenarios) | 31 | 31 | 31/31 | 3,720/3,720 |
| fep-0003 | 44 | 44 | 44/44 | 5,280/5,280 |

- The TypeScript parity scripts got an option `--rust BIN`: `cross-check.mjs` and `fuzz-parity.mjs` now compare Python, TypeScript and Rust on the same files. CI job `rust-parity` runs both (cross-check + `--n 10`).
- The Python suite also accepts the Rust CLI as an external consumer: `python -m fidetype.conformance consumer --cmd "fidetype-rs consume {path}"` gives 167/167 over the four profiles.
- The golden vectors passed on the first run. The fuzz found 2 more Python behaviours to copy (string-format LSL samples are iterated only when a chunk with timestamps is pulled; the reference greedy decoder fails when `blank_id` is null). After the fix: 16,141 of 16,141 mutants give the Python verdict.

## Design

| Choice | Why |
|---|---|
| Own JSON parser, not `serde_json` | It must keep the Python data model: `1.0` is a float, not an int; key order; a later duplicate key replaces the value in place; lone surrogate escapes. |
| One dependency: `libm` 0.2.15 (MIT) | `exp` / `log` without `std`, with the same results on every platform. Pinned in `Cargo.lock`. |
| `#![forbid(unsafe_code)]` | Firmware code that parses untrusted input. |
| Checked on `thumbv7em-none-eabihf` | CI builds the core for a Cortex-M4F/M7 target with no OS. |
| GNU host toolchain on the dev PC | The machine has no MSVC build tools; `stable-x86_64-pc-windows-gnu` brings its own linker. rustup was installed for the current user only. |

> **Our take:** Three independent ports now give the same verdicts. That makes the conformance vectors a real cross-language contract, but it also shows where the contract lives in Python code and not in the spec text. Two examples from this port: the reference refuses a non-CTC stream (`blank_id` null) on the frames route only because its greedy decoder calls `np.delete(lp, None, axis=1)`; and FEP-0002 string samples are iterated late. A future spec revision should either state such rules or the reference should drop them. The first one looks like a reference bug.

> **Our take:** The fuzz also found 3 mutants where the TypeScript SDK differs from Python (the two cases above, and a truthy non-object `consumer_settings`). They are open items for the TS SDK; the Rust SDK has the Python verdict on all three.

## Open items
- crates.io publishing: a user decision (crate name, versioning policy, trusted publishing; compare M7-09).
- The reference no-blank decode failure: fix in Python, or keep and document. The Rust copy is one check in `StructuralLayer::end`.
- No JSON Schema validator in Rust (verdicts do not need it). Minimum Rust version not tested. Fuzz covers JSON vectors only, not NPZ.

Related: [TypeScript SDK](typescript-sdk.md), [Python SDK](python-sdk.md), [conformance suite](conformance-suite.md), [streaming trust layer](streaming-trust-layer.md), [LSL input](lsl-input.md), [intent events](intent-events.md).
