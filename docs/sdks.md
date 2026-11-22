# SDKs

Fidetype has three reference SDKs. All three read, write and check NeuralTextStream (NTS) and give the same conformance verdict on every golden vector. All three are at version 0.1.0, the first registry release. A C SDK is planned after NTS 1.0.

| | Python | TypeScript | Rust |
|---|---|---|---|
| Package (from 0.1.0) | `pip install fidetype` (PyPI) | `npm install @fidetype/sdk` (npm) | `cargo add fidetype` (crates.io) |
| Folder | [`src/fidetype/`](../src/fidetype/) | [`sdk/typescript/`](../sdk/typescript/README.md) | [`sdk/rust/`](../sdk/rust/README.md) |
| Runtime | Python 3.12+ | Node 18+ and browsers (ESM) | Rust 1.81+; `no_std` + `alloc` core for firmware |
| Runtime dependencies | `numpy` (extras optional) | none | `libm` |
| Writer, reader, checks | yes | yes | yes |
| `DecisionTracker` (consumer rules for `trust_decision`) | yes | yes | yes |
| Conformance profiles `v0.1`, `fep-0001` … `fep-0005` | yes (reference) | yes (`fep-0002` structural) | yes (`fep-0002`, `fep-0004` structural / sans-IO) |
| Trust layer (calibration, decisions) | yes | no | no |
| Collector, adapters (LSL, WebSocket, datasets) | yes | WebSocket client only | WebSocket sans-IO core only |
| CLI | `fidetype` | `fidetype-ts` | `fidetype-rs` |
| Changelog | [CHANGELOG.md](../CHANGELOG.md) | [CHANGELOG.md](../sdk/typescript/CHANGELOG.md) | [CHANGELOG.md](../sdk/rust/CHANGELOG.md) |

Which one to use:

- You write a decoder in Python, or you need the trust layer or the Collector: **Python**.
- You build a web app or a Node service that shows or checks decisions: **TypeScript**.
- You write device firmware or a native service: **Rust**.

Versions and releases: [RELEASING.md](RELEASING.md). Parity tests (Python = TypeScript = Rust on the golden vectors and on fuzzed variants) run in CI.

## Python SDK guide

The Python package is the reference implementation. Install it from a clone ([getting-started.md](getting-started.md#1-install)).

### Public API

`import fidetype` loads nothing heavy. All names import lazily.

| Job | Names |
|---|---|
| Produce a stream | `open_stream(path, "w", ...)`, `StreamWriter`, `stream_meta(...)`, `make_stream(log_probs, ...)`, `write_stream(stream, path)` |
| Read and check a stream | `open_stream(path)` (iterator of events), `read_stream(path)`, `validate(path_or_stream, level=None)`, `StreamRejected` |
| Run the trust layer | `TrustLayer` (= `StreamingTrustLayer`), `FrozenTrustConfig`, `calibrate(streams, texts, decode_fn)`, `replay`, `greedy_decoder()`, `Action` |

A worked example is in [getting-started.md](getting-started.md#3-emit-a-stream-from-your-decoder). More detail, with the design notes: [wiki/concepts/python-sdk.md](../wiki/concepts/python-sdk.md).

### Modules

| Module | Content |
|---|---|
| `fidetype.streams` | NTS data classes, vocabulary, noisy-decoder simulator, test corpus |
| `fidetype.trust` | Trust core, frozen configuration, streaming trust layer, intent and control trust layers, provenance ledger |
| `fidetype.conformance` | Producer checks, reference consumer, golden vectors |
| `fidetype.collector` | The Collector (FEP-0006) |
| `fidetype.adapters` | LSL, BrainFlow bridge, WebSocket, dataset replay, text n-best |
| `fidetype.benchmark` | Open benchmark v0.1 |
| `fidetype.demo` | Offline demo |
| `fidetype.eval` | Metrics: CER, WER, ECE, CTC greedy decode |

### Examples

| Script | Shows |
|---|---|
| [`examples/emit_ctc_stream.py`](../examples/emit_ctc_stream.py) | Write CTC log-probabilities as NTS |
| [`examples/hypothesis_stream.py`](../examples/hypothesis_stream.py) | A hypothesis-only stream (a decoder with text output only) |
| [`examples/streaming_trust.py`](../examples/streaming_trust.py) | The streaming trust layer, event by event |
| [`examples/lsl_bridge.py`](../examples/lsl_bridge.py) | An LSL bridge (needs the `lsl` extra) |
| [`examples/simulate_demo.py`](../examples/simulate_demo.py) | The noisy-decoder simulator |
| [`examples/ws-browser/index.html`](../examples/ws-browser/index.html) | A browser page on the WebSocket decisions channel |

## TypeScript and Rust

The full guides are the SDK READMEs: [TypeScript](../sdk/typescript/README.md) and [Rust](../sdk/rust/README.md). Quick start from a clone:

```sh
cd sdk/typescript && npm ci && npm run build && npm test && npm run conformance
cd sdk/rust && cargo test && cargo run --bin fidetype-rs -- conformance
```
