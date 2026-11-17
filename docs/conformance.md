# Conformance

The conformance suite tells you if a producer writes valid NeuralTextStream (NTS) and if a consumer reads it correctly. Each check cites its spec rule. The rules are in [NTS 1.0 RC4, section 9](../spec/nts-1.0-rc4.md#9-conformance) (draft).

Start with the **conformance kit** and `nts-conform` (below). Use the golden vectors (further down) when you want every edge case.

## The conformance kit and `nts-conform`

The kit is a short list of realistic example files: 31 files, one or more for each wire form of the spec. Each file has an expected verdict and the rule ids that it exercises. The files live in [`spec/conformance/kit/`](../spec/conformance/kit/). The index is [`kit.json`](../spec/conformance/kit/kit.json).

| Wire form | Spec | Kit entries |
|---|---|---|
| `jsonl-stream`: JSON Lines input stream (header, dense or sparse frames, events, `meta` keys; text, intent and control profiles) | 8.1.1, 3, 4, 7 | K01, K02, K06-K15, K19, K20, K23, K24 |
| `npz`: NPZ frame core | 8.1.2 | K03, K04, K05 |
| `jsonl-decision-log`: `trust_decision` lines (text, intent, control) | 6, 7.3.5, 7.4.5 | K16-K18, K21, K22, K25 |
| `lsl-capture`, `lsl-decisions-capture`: LSL binding `nts-lsl/0.1` | 8.2 | K26-K28 |
| `ws-capture`, `ws-decisions-capture`: WebSocket binding `nts-ws/0.1` | 8.3 | K29-K31 |

Binary protobuf is not a wire form in RC4. The proto files define the data model and the JSON mapping; the binary framing is roadmap P1-05. The JSON Lines files of the kit are the JSON mapping.

Verdicts: `accept` (no failed check, no warning), `accept-with-warnings` (only the listed advisory checks warn), `reject` (at least the listed checks fail). `nts-conform list` prints the full table.

### Check your producer's files

`nts-conform` is installed with the Python package (`pip install -e .` in a clone). It finds the wire form and runs every profile that applies.

```sh
nts-conform check my_stream.jsonl                  # input stream, decision log, .npz, LSL / WebSocket capture
nts-conform check out/ --level trust-ready --json report.json
my-decoder --emit-nts | nts-conform check -        # a live capture on stdin (JSON Lines or NPZ)
```

Output: one line per finding, with the outcome, the rule ids, the check id, the location and the message. Example (kit file K20):

```text
spec/conformance/kit/fep-0003/k20-intent-undeclared.jsonl  [jsonl-stream; profiles v0.1, fep-0001, fep-0003; level core]
  FAIL  PRF-3,INT-E1,INT-E2,INT-E3,+3 FEP3-INTENT          line 2         candidates[0] intent 'intent.open-door' is not in the declaration
  => FAIL: 1 failed and 0 warning checks of 51 run (25 not applicable); ...
```

- **FAIL** is a failed check at or below `--level` (default `core`). **WARN** is an advisory check, or a failed check of a higher level than `--level`.
- The rule ids come from the traceability table of the spec ([Appendix C.1](../spec/nts-1.0-rc4.md#c1-table)). A check that tests several rules lists them all. If the message names one rule, only that rule is listed. The map is [`rule-map.json`](../spec/conformance/kit/rule-map.json).
- An LSL capture or a WebSocket capture is a scenario JSON file (schemas `fidetype.conformance.lsl-scenario/1`, `fidetype.conformance.ws-scenario/1`): the stream infos and the recorded chunks or messages. See the kit files K26-K31.
- `--json OUT` writes the report (schema `fidetype.nts-conform.report/1`): per target the form, the profiles, the verdict, the outcome per rule id, and every result with rule ids, check, level, location and message.

Exit codes: 0 = every target passes, 1 = a target fails, 2 = an input error (no such file, unknown form).

### Run the kit against your implementation

Your validator or reader gets each kit file. The kit mode compares its verdicts with the expected verdicts.

```sh
nts-conform kit                                                  # the reference (must always pass)
nts-conform kit --cmd "my-validator {path}"                      # exit 0 = accept, other = reject
nts-conform kit --cmd "my-validator --profile {profile} {path}"  # {profile}: v0.1, fep-0001 ... fep-0005
nts-conform kit --impl my_pkg.reader:load                        # Python: returns = accept, raises = reject
nts-conform kit --verdicts my-verdicts.json                      # verdicts you made offline: {"K01": "accept", ...}
nts-conform kit --profile fep-0004 --json kit-report.json
```

The reference run checks two things for each file: the consumer verdict, and the producer check (`nts-conform check`). Both must give the expected verdict. With `--cmd`, `--impl` or `--verdicts`, only your verdicts are compared. The JSON report has the schema `fidetype.nts-conform.kit-report/1`.

The TypeScript and Rust SDKs run the kit with their own consumers. Each kit profile folder has a `manifest.json` in the golden-vector format, so the SDK runners read it as it is:

```sh
node sdk/typescript/bin/fidetype-ts.mjs conformance --vectors spec/conformance/kit   # or: npm run conformance:kit
fidetype-rs conformance --vectors spec/conformance/kit
nts-conform kit --cmd "fidetype-rs consume --profile {profile} {path}"
```

CI checks that Python, TypeScript and Rust give the same verdict on every kit file (`sdk/typescript/scripts/cross-check.mjs --vectors spec/conformance/kit --rust BIN`), and that the generated JSON Schema agrees with them (`tools/proto/parity.py`).

Maintainers: `nts-conform build --out spec/conformance/kit` writes the kit. `nts-conform rules --write` rebuilds `rule-map.json` after a change of Appendix C. Tests fail if either copy is stale.

## Check a producer (your stream files)

The older `fidetype conformance` commands stay. They run one profile at a time.

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

A claim names the class (producer, consumer, trust layer, bridge, binding), the level, the profiles, the bindings and the spec version. While NTS 1.0 is a draft, a claim must say so, for example: "Producer, NTS 1.0 RC4 (draft), level provenance, profiles text + intent, binding nts-lsl/0.1" ([spec 9.4](../spec/nts-1.0-rc4.md#94-conformance-claims)).

More detail: [wiki/concepts/conformance-suite.md](../wiki/concepts/conformance-suite.md).
