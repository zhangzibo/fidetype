# Getting started

This page takes you from a clone to your first NeuralTextStream (NTS) file and your first trust decisions. It uses the Python SDK, because the trust layer and the Collector are in Python. For TypeScript and Rust, see [sdks.md](sdks.md).

## 1. Install

You need Python 3.12 or later. The package is not on PyPI yet, so install it from a clone:

```sh
git clone https://github.com/zhangzibo/fidetype.git
cd fidetype
pip install .                 # or: uv sync --extra dev   (adds pytest; then: uv run pytest -q)
fidetype version              # prints the package version and the spec version
```

Optional extras:

| Extra | Adds | Install |
|---|---|---|
| `lsl` | Lab Streaming Layer input and output (`pylsl`) | `pip install ".[lsl]"` |
| `brainflow` | BrainFlow board → LSL bridge (also needs `lsl`) | `pip install ".[lsl,brainflow]"` |
| `ws` | WebSocket input and output, FEP-0004 (`websockets`) | `pip install ".[ws]"` |
| `data` | Dataset loaders and preprocessing (`mne`, `scipy`) | `pip install ".[data]"` |
| `dev` | `pytest` and `ws` | `pip install ".[dev]"` |

## 2. Run the offline demo

```sh
fidetype demo --fast                          # no waiting between phrases
fidetype demo --fast --html demo.html         # also write a static demo page
```

The demo needs no data and no network. It runs synthetic decoder streams through the trust layer and prints COMMIT, OFFER and ABSTAIN phrase by phrase. On a flat (no-signal) stream, the decoder's language model still writes fluent text. "Always commit" types it. The trust layer abstains. A prebuilt page is in [demo/index.html](../demo/index.html).

## 3. Emit a stream from your decoder

A CTC decoder gives one row of log-probabilities per frame over `fidetype.VOCAB` (blank first). Write the rows as an NTS file and check it:

```sh
fidetype demo --fast --write-streams demo-streams   # gives demo-streams/trust-config-demo.json
```

```python
import fidetype
from fidetype.demo import build_decoder, make_stream   # stand-ins for your decoder

log_probs = make_stream("the boy found a red box", "strong", seed=0).log_probs   # (T, V) from your decoder
meta = fidetype.stream_meta(modality="eeg", decoder_name="my-ctc", decoder_version="1.0")
with fidetype.open_stream("utt.jsonl", "w", source="my-ctc", meta=meta, frame_period=0.04) as w:
    for i, row in enumerate(log_probs):
        w.frame(0.04 * i, row)                 # or w.frame(t, logits=raw_scores)
print(fidetype.validate("utt.jsonl").level)    # "trust-ready"
```

The same check from the command line:

```sh
fidetype validate utt.jsonl --level trust-ready
```

## 4. Run the trust layer

```python
config = fidetype.FrozenTrustConfig.load("demo-streams/trust-config-demo.json")
layer = fidetype.TrustLayer(config, decode_fn=build_decoder())   # the decoder the config was fitted with
for event in fidetype.open_stream("utt.jsonl"):
    for d in layer.push(event):
        print("final" if d.final else "preview", d.action.value, d.shown)
```

Or from the command line (one `trust_decision` JSON line per decision):

```sh
fidetype trust --config demo-streams/trust-config-demo.json --decoder demo utt.jsonl
```

**Important.** A frozen trust configuration is valid only with the `decode_fn` it was fitted with. With another decoder, its guarantee does not hold. For real use, fit your own configuration on labelled calibration data of the same user:

```python
fidetype.calibrate(streams, texts, decode_fn).save("trust.json")
```

## 5. Next steps

| Goal | Read |
|---|---|
| Understand the data model and the decisions | [concepts.md](concepts.md) |
| Run inputs, trust and outputs as one service | [collector.md](collector.md) |
| Prove that your producer or consumer is conformant | [conformance.md](conformance.md) |
| More examples (hypothesis-only streams, LSL bridge, streaming trust) | [examples/](../examples/) |
| The full Python API | [sdks.md](sdks.md#python-sdk-guide) and [wiki/concepts/python-sdk.md](../wiki/concepts/python-sdk.md) |

## Command line summary

| Command | What it does |
|---|---|
| `fidetype validate FILE [--level L]` | Conformance check of a stream (levels `core`, `trust-ready`, `provenance`) |
| `fidetype trust --config F FILE` | Streaming trust layer; prints `trust_decision` JSON Lines |
| `fidetype intent`, `fidetype control` | Trust layers of the intent (FEP-0003) and control (FEP-0005) profiles |
| `fidetype demo` | Offline demo |
| `fidetype conformance` | The full conformance suite (`check`, `consumer`, `vectors`, `list`) |
| `fidetype collector --config F` | The Collector (FEP-0006) |
| `fidetype lsl ...`, `fidetype ws ...` | LSL and WebSocket input and output (extras `lsl`, `ws`) |
| `fidetype benchmark ...` | Open benchmark v0.1 (`tracks`, `prepare`, `score`, `leaderboard`) |
| `fidetype ledger ...` | Provenance ledger tools |

Run `fidetype <command> --help` for the options.
