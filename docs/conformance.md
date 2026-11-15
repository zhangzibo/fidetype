# Conformance

The conformance suite tells you if a producer writes valid NeuralTextStream (NTS) and if a consumer reads it correctly. Each check cites its spec rule. The rules are in [NTS 1.0 RC2, section 9](../spec/nts-1.0-rc2.md#9-conformance) (draft).

## Check a producer (your stream files)

```sh
fidetype validate my_stream.jsonl --level trust-ready
fidetype conformance check my_stream.npz --level provenance --verbose
fidetype conformance check my_decisions.jsonl --profile fep-0001
```

| Level | Adds |
|---|---|
| `core` | Every MUST rule that a validator can check |
| `trust-ready` | The SHOULD rules that a trust layer needs (`source`, `device.modality`, `decoder.causal`, `data.derived`, `language`) |
| `provenance` | Stream id, decoder name and version, weights hash, calibration id, pseudonymous ids |

`fidetype conformance list` prints every check with its level and spec clause.

## Check a consumer (your reader)

Your reader gets each golden vector as a file. It must exit 0 to accept and non-zero to reject. The suite compares the result with the expected verdict:

```sh
fidetype conformance consumer --cmd "my-reader {path}"
fidetype conformance consumer --profile fep-0001 --cmd "my-reader {path}"
```

Run the reference consumer alone (it must always pass):

```sh
fidetype conformance consumer
fidetype conformance --profile fep-0001
```

## Profiles and golden vectors

| Profile | Covers | Vectors |
|---|---|---|
| `v0.1` | Core: header, frames, segments, files (NPZ, JSON Lines) | [`spec/conformance/v0.1/`](../spec/conformance/v0.1/) |
| `fep-0001` | Text profile: hypotheses, evidence, `trust_decision` | [`spec/conformance/fep-0001/`](../spec/conformance/fep-0001/) |
| `fep-0002` | LSL binding (scenarios) | [`spec/conformance/fep-0002/`](../spec/conformance/fep-0002/) |
| `fep-0003` | Intent profile | [`spec/conformance/fep-0003/`](../spec/conformance/fep-0003/) |
| `fep-0004` | WebSocket binding (scenarios) | [`spec/conformance/fep-0004/`](../spec/conformance/fep-0004/) |
| `fep-0005` | Control profile | [`spec/conformance/fep-0005/`](../spec/conformance/fep-0005/) |

Each folder has a `manifest.json` with the expected verdict of each vector. The vectors are small synthetic files. They hold no participant data. The Python wheel ships them, so the commands above work without a clone.

## The other SDKs

```sh
node sdk/typescript/bin/fidetype-ts.mjs conformance     # after npm ci && npm run build in sdk/typescript
cd sdk/rust && cargo run --bin fidetype-rs -- conformance
```

Both CLIs also have a `consume` command that follows the consumer contract above, so the Python suite can test them directly. CI checks that Python, TypeScript and Rust give the same verdict on every vector and on fuzzed variants.

## Make a conformance claim

A claim names the class (producer, consumer, trust layer, bridge, binding), the level, the profiles, the bindings and the spec version. While NTS 1.0 is a draft, a claim must say so, for example: "Producer, NTS 1.0 RC2 (draft), level provenance, profiles text + intent, binding nts-lsl/0.1" ([spec 9.4](../spec/nts-1.0-rc2.md#94-conformance-claims)).

More detail: [wiki/concepts/conformance-suite.md](../wiki/concepts/conformance-suite.md).
