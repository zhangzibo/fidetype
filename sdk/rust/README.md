# Fidetype Rust SDK (`fidetype` crate)

Rust SDK for **NeuralTextStream (NTS) v0.1** and the draft FEP profiles. The core is **`no_std` + `alloc`**: it parses, checks, writes and decides without an operating system. So it can run in device firmware, for example on a Cortex-M microcontroller. The `std` feature (on by default) adds file helpers, the CLI `fidetype-rs` and the example program.

| Part | What it does |
|---|---|
| Writer | `NtsWriter`, `to_jsonl`: write NTS JSON Lines (header, frames, hypotheses, `segment_end`, `end`). Each event is checked before it is written. `npz::write_npz`: write an NPZ stream (stored members, as `numpy.savez`). |
| Readers | `reader::parse_nts_text`, `reader::LineSplitter`, `reader::EventReader`: read a whole text, or byte chunks from a serial port, socket or file. UTF-8 is strict across chunk borders. |
| Reference consumer | `load_stream(name, bytes)`: accept or reject a `.jsonl` or `.npz` file with the core rules of the Python reference (`fidetype.conformance.io.load_stream`). |
| Checks | `check_stream`: all v0.1 checks with levels `core`, `trust-ready`, `provenance`, `advisory` (the same 59 checks as `fidetype validate`). `StreamValidator`: event-by-event checks for live streams. |
| Decisions | `DecisionTracker`, `trust::is_final_commit`, `trust::committed_text`, `trust::empty_commit_warning`: what a consumer may do with each `trust_decision` (COMMIT / OFFER / ASK / ABSTAIN, text and intent profiles). |
| Profiles | `profiles::fep0001`, `fep0002` (LSL scenarios), `fep0003`, `fep0004` (WebSocket scenarios): the producer checks and the reference consumers of each FEP profile. |
| WebSocket core | `ws::IngestCore`, `ws::SubscriberCore`: the sans-IO logic of FEP-0004 (`nts-ws/0.1`). No networking: you give connection events and messages, and you apply the returned `Effects`. |
| Conformance | `conformance::run_vectors`: run the golden vectors in `spec/conformance/` (the same files as the Python suite) for every profile. |

## Where it lives

The SDK is in `sdk/rust/`, next to `sdk/typescript/`. It reads the spec files in place (`spec/conformance/`), so there is one copy of each vector.

## Quick start

```bash
cd sdk/rust
cargo test                                        # unit tests, integration tests, golden vectors, doc tests
cargo run --bin fidetype-rs -- conformance        # all profiles in spec/conformance/
cargo build --no-default-features --lib           # the no_std core alone
```

Not published to crates.io (see "Open items"). In another local project: `fidetype = { path = "../path/to/sdk/rust" }`, or with `default-features = false` for firmware.

## Examples

### Write a stream

```rust
use fidetype::json::{Map, Value};
use fidetype::writer::{NbestItem, NtsWriter, WriterOptions};

let mut opts = WriterOptions::new("acme-decoder");
opts.frame_period = Some(0.04);
opts.meta = Map::from_pairs([("device.modality", Value::str("emg")), ("data.derived", Value::Bool(true))]);
let mut out = String::new();
let mut w = NtsWriter::new(|line: &str| { out.push_str(line); out.push('\n'); }, opts)?;
w.frame_probs(0.0, &row_of_28_probabilities)?;     // or frame_log_probs / frame_logits
w.hypothesis(&[NbestItem::new("hi", -1.2)], true, None, "none", None)?;
w.segment_end(Some(0.5), Some("utterance"))?;
w.end()?;
```

The sink is a closure, so a firmware build can write each line to a UART or a ring buffer.

### Read and check a stream

```rust
use fidetype::{check_stream, load_stream, Level};

match load_stream("stream.jsonl", &bytes) {                 // ".npz" also works
    Ok(s) => println!("{} frames", s.summary.get("n_frames").as_f64().unwrap()),
    Err(e) => println!("rejected: {} (clause {})", e.check_id, e.clause),
}
let report = check_stream("stream.jsonl", &bytes, Level::TrustReady)?;
println!("ok = {}, level reached = {:?}", report.ok, report.level);
```

Live stream, chunk by chunk (no `std` needed):

```rust
use fidetype::reader::EventReader;

let mut r = EventReader::new();
for chunk in incoming_chunks {
    for (event, result) in r.push(chunk)? {        // an error at the first bad event
        if result.kind() == "frame" { /* use the row */ }
    }
}
r.finish()?;
```

### Act on trust decisions

```rust
use fidetype::trust::{DecisionKind, DecisionTracker};

let mut tracker = DecisionTracker::new();
for line in decision_lines {
    let d = tracker.push_text(line);
    if d.forward { output.type_text(d.committed.as_deref().unwrap()); }   // final COMMIT with a non-empty text only
    else if d.kind == DecisionKind::Offer { ui.show_choices(&d.offered); }
    for w in &d.warnings { eprintln!("{w}"); }                             // for example FEP-0001 rule 9
    for e in &d.errors { eprintln!("{e}"); }                               // rules 5-8: order, one final per utterance
}
```

Rules that the tracker applies (FEP-0001 section 3):

| Rule | Tracker behaviour |
|---|---|
| 1. Do not act on `is_final = false` | `kind = Preview`, `forward = false` |
| 3. Forward only a final COMMIT (or a user selection after OFFER) | `forward = true` only for a final COMMIT |
| 5-7. `seq` increases; one final decision per (session, utterance) or (session, unit); nothing after it | an entry in `errors` |
| 8. A COMMIT with `shown` has at least one text | an entry in `errors` |
| 9 (SHOULD). No final COMMIT with an empty or white-space text | an entry in `warnings`, `forward = false` |

### Example program: validate a replay file

```bash
cargo run --example validate_replay                         # default: spec/conformance/fep-0001/f25-log-two-sessions.jsonl
cargo run --example validate_replay -- path/to/replay.jsonl
```

A decision log: each decision with what a consumer does with it. An input stream: event-by-event validation (in 64 KiB blocks), then the whole-file reference consumer. Exit code 0 = valid, 1 = invalid.

### Command line

```bash
fidetype-rs conformance [--profile NAME|all] [--vectors DIR] [--json OUT|-]
fidetype-rs validate stream.npz --level provenance [--json]
fidetype-rs decisions decisions.jsonl
fidetype-rs consume --profile fep-0001 file.jsonl           # exit 0 = accept
```

`consume` follows the external-consumer contract of the Python suite. So the Python suite can test this SDK directly (on Windows, give the absolute path of the `.exe`):

```bash
python -m fidetype.conformance consumer --cmd "sdk/rust/target/release/fidetype-rs consume {path}"
python -m fidetype.conformance consumer --profile fep-0002 --cmd "sdk/rust/target/release/fidetype-rs consume --profile fep-0002 {path}"
```

All five profiles pass this way (205/205).

## Conformance and parity with Python

| Profile | Vectors | Rust | Same verdict and "ok" as Python | Fuzz mutants, same verdict as Python (seeds 1-6, `--n 30`, M7-12) |
|---|---|---|---|---|
| `v0.1` (NPZ + JSON Lines) | 52 | 52/52 pass | 52/52 | 3,516/3,516 |
| `fep-0001` streaming trust events | 40 | 40/40 pass | 40/40 | 7,200/7,200 |
| `fep-0002` NTS over LSL (scenarios) | 32 | 32/32 pass | 32/32 | 5,760/5,760 |
| `fep-0003` intent events | 44 | 44/44 pass | 44/44 | 7,920/7,920 |
| `fep-0004` NTS over WebSocket (scenarios, M7-12) | 37 | 37/37 pass | 37/37 | 6,660/6,660 |

The parity scripts are the TypeScript SDK scripts with the option `--rust BIN`. They compare Python, TypeScript and Rust on the same files:

```bash
cargo build --release
cd ../typescript && npm ci && npm run build
node scripts/cross-check.mjs --rust ../rust/target/release/fidetype-rs     # golden vectors: verdict + "ok"
node scripts/fuzz-parity.mjs --n 30 --seed 1 --rust ../rust/target/release/fidetype-rs
```

CI runs both in the job `rust-parity` (cross-check + fuzz `--n 30` at seeds 1-3).

Rules that matter for identical verdicts (in addition to those of the TypeScript SDK):

| Python behaviour | How the SDK copies it |
|---|---|
| `1.0` is a float, so it is not an integer (`seq`, `unit`, `set_size`, `blank_id`, ...) | `Value::Num(f64, float_literal)` keeps the literal form; `Value::is_int` reads it. |
| Objects keep key order; a later duplicate key replaces the value in place | `json::Map` is an ordered list. |
| `True == 1` in `==`, `in` and dict keys | `json::py_eq`, `profiles::common::tuple_key`. |
| String-format LSL samples are iterated only when a chunk with timestamps is pulled | `Samples::Raw(Value)`, iterated in `Reader::pull`. |
| `str(x)` of a non-string marker sample is Python `repr` (`{'a': 1}` is not JSON) | `json::py_str`. |
| ElementTree (expat) refuses a bare `&` in stream-info XML | the XML reader refuses it. |
| `int(round(x))` for the gap length: half to even; an error for inf / NaN | `libm::rint` and an error. |
| `blank_id` null = no blank class (spec 3.1, FEP-0002 section 10, vector L32): the greedy decoder decodes it | The structural trust model accepts it. (M7-11 fixed the reference, which raised IndexError before.) |
| A boolean `frame_period` or `latency` passes as 1 or 0 (bool is an int in Python) | The structural trust model reads it as a number (M7-12; the TypeScript SDK got the same fix in M6-11). |

### FEP-0002 note

FEP-0002 vectors are LSL scenarios. The Python reference plays them through its LSL adapter and its trust layer. The SDK ports the LSL binding logic (stream infos, clock correction, order, gaps, reconnect, markers) and uses a **structural model** of the trust layer: the same event checks and the same decision counts (`decisions`, `final_decisions`, `aborted_utterances`). It does not decode and it does not apply a trust policy. So the SDK can check an FEP-0002 producer, but it is not a Rust trust layer.

### FEP-0004 note

FEP-0004 vectors are WebSocket scenarios (`ingest` and `subscribe`). `ws::IngestCore` is a port of the sans-IO server logic of `fidetype.adapters.ws`: handshake, header, `ws_seq` duplicates, the reorder hold (16 events or 0.25 s by default), gaps, batches, acks, resume and take-over, and the close codes. After a gap, the frames of the cut utterance are dropped up to the next `segment_end`, `end` or header. The decision counts use the same structural trust model as FEP-0002. There is no networking code: a caller connects the core to its own WebSocket library.

## Embedded use

- `default-features = false` gives the `no_std` + `alloc` core. CI and a local build check it on `thumbv7em-none-eabihf` (Cortex-M4F/M7, no OS). The firmware gives the global allocator.
- No `unsafe` code (`#![forbid(unsafe_code)]`).
- Math (`exp`, `log`) comes from `libm`, so the results are the same on every platform.
- Objects are small ordered lists (linear key search). That is fast for NTS events, which have few keys.

## Dependencies and licences

| Crate | Kind | Version (pinned in `Cargo.lock`) | Licence |
|---|---|---|---|
| `libm` | runtime (no_std math) | 0.2.15 | MIT |

That is the only dependency. The SDK has its own JSON parser (with Python semantics), DEFLATE decoder, ZIP and NPY reader and writer, SHA-256 and CRC-32, so it does not need `serde`/`serde_json`. Python semantics (float literals, key order, lone surrogates) are easier to keep in an own parser. The SDK is Apache-2.0, as the repository.

## Open items

- **crates.io publishing is a user decision.** The crate has `publish = false`. Before a release: choose the crate name (`fidetype` may be taken), the versioning policy and trusted publishing (as M7-09 for PyPI).
- No JSON Schema validator in Rust (the TypeScript SDK has one). The checks give the same verdicts without it.
- The minimum supported Rust version is not tested (CI uses stable).
- The parity fuzz mutates JSON vectors only, not NPZ files.
