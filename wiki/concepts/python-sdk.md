---
title: Python SDK and offline demo
type: concept
tags: [sdk, api, cli, demo, neuraltextstream, trust, m7]
sources: []
updated: 2026-11-12
---

# Python SDK and offline demo

Task **M7-01**. The SDK is the small, stable surface of the `fidetype` package. A decoder author uses it to emit a [NeuralTextStream](../../spec/neuraltextstream-v0.1.md), check it, and run the [streaming trust layer](streaming-trust-layer.md). The offline demo shows the trust layer on synthetic streams. The [roadmap](../questions/roadmap-standard.md) puts "demo + benchmark" first in the adoption order.

## Public API (`import fidetype`)
All names import lazily. `import fidetype` loads no trust or conformance module and no optional dependency.

| Job | Names |
|---|---|
| Produce a stream | `make_stream(log_probs, ...)` ((T, V) matrix → `NeuralTextStream`), `write_stream(stream, path)` (`.jsonl` / `.npz`), `StreamWriter` (one event at a time, each event checked), `open_stream(path, "w", ...)`, `stream_meta(...)` (spec section 4 keys), `VOCAB`, `BLANK_ID`, `SPEC_VERSION` |
| Read and check a stream | `open_stream(path)` (iterator of events), `read_stream(path)` (reference consumer), `validate(path_or_stream, level=None)` (= `fidetype.conformance.check`), `StreamRejected` |
| Run the trust layer | `StreamingTrustLayer` (alias `TrustLayer`), `StreamingConfig`, `StreamDecision`, `Action`, `FrozenTrustConfig` (`.load`, `.save`), `replay`, `greedy_decoder()`, `calibrate(streams, texts, decode_fn)`, `NBest`, `Candidate` |

New small additions under the hood:
- `TargetReport.passes(level)` and `TargetReport.failures(level)`.
- `fidetype.trust.streaming.frame_decoder(name)`: the named decoders `none`, `greedy`, `demo` for the command lines. `--decoder demo` is now valid in `fidetype trust` and `fidetype lsl run`.
- `--max-attempts` in `fidetype trust` (1 = no ASK).

**Rule:** a `FrozenTrustConfig` is valid only with the `decode_fn` that it was fitted with. We checked this: the demo configuration with the greedy decoder (instead of the demo beam search) committed a wrong text ("ello world" for "hello world").

## Command line (`fidetype`)
One console script groups the tools. Each subcommand runs the same code as its `python -m` module, and the modules still work.

| Command | Same as |
|---|---|
| `fidetype validate FILE [--level L]` | `python -m fidetype.conformance check` |
| `fidetype trust` / `replay --config C FILE` | `python -m fidetype.trust.streaming replay` |
| `fidetype demo` | `python -m fidetype.demo` |
| `fidetype conformance`, `lsl`, `benchmark`, `ledger` | `python -m fidetype.conformance`, `.adapters.lsl`, `.benchmark`, `.trust.provenance` |
| `fidetype version` | — |

## The offline demo
`fidetype demo` needs no data, no network and no GPU. It runs in about 3 s with `--fast`.

| Part | What it is |
|---|---|
| Texts | short phrases from `fidetype.streams.corpus` (written for this project) |
| Decoder output | `NoisyDecoderSimulator` frames at greedy CER targets 0.05 / 0.17 / 0.28 / 0.41, over-confident (temperature 0.5); two null inputs: a flat stream (no signal) and a frame-shuffled stream |
| Decoder | beam search (width 8) + character 5-gram LM, fitted on other phrases |
| Configuration | `src/fidetype/demo/trust-config-demo.json`, fitted on 600 other phrases with the Paper 1 recipe (guard on, policy grid, Learn then Test, alpha 0.05). `fidetype.demo.build_config()` refits it; the result has the same `config_id` (`tcfg-a34f63a757f55371`) |
| Baseline | "always commit": type the top-1 text every time |

The session has 12 phrases in a fixed order (not selected by outcome). Then a totals table runs 40 other phrases per condition.

Totals (40 phrases per condition, `demo/decision-log.json`):

| Condition | Trust: commit rate | Trust: wrong-commit rate | Always commit: wrong-commit rate |
|---|---|---|---|
| strong signal | 0.650 | 0.050 | 0.225 |
| good signal | 0.375 | 0.025 | 0.225 |
| medium signal | 0.025 | 0.000 | 0.325 |
| weak signal | 0.000 | 0.000 | 0.300 |
| no signal (flat) | 0.000 | 0.000 | 1.000 |
| frames shuffled | 0.000 | 0.000 | 1.000 |

The key safety result: on a flat stream the LM still writes fluent text. "Always commit" types it 40/40 times. The trust layer types it 0/40 times; the guard sees no neural evidence for the characters and abstains. Paper 1 reports the same behaviour for null input on real data.

> **Our take:** the demo numbers are synthetic. They show the mechanism, not a field result. The shuffled stream is not always caught by the guard: in the session it gets an OFFER (final attempt) of garbled text, which the user rejects. It is never committed.

### Outputs
- Terminal: live previews (grey, every 1 s of signal), then the final decision and the baseline per phrase. `--speed`, `--fast`, `--no-color`.
- Static page: `fidetype demo --html demo.html`. One self-contained HTML file: no server, no network, light and dark themes. It shows all final decisions without JavaScript; "Play" replays the session on a timeline (signal evidence 1 − p(blank), previews, final decision). The repo has a prebuilt copy: [demo/index.html](../../demo/index.html) with its log `demo/decision-log.json`.
- Streams: `fidetype demo --write-streams DIR` writes the 12 session streams (`.jsonl`) and the configuration, for `fidetype trust` or LSL.

### Live mode over LSL (optional, `pip install "fidetype[lsl]"`)
```sh
fidetype demo --write-streams demo-streams
fidetype lsl replay-to-lsl demo-streams/demo-04-no-signal.jsonl --name demo     # shell 1
fidetype lsl run --config demo-streams/trust-config-demo.json --stream-name demo --decoder demo   # shell 2
```
See [LSL input](lsl-input.md).

## Examples (`examples/`)
| Script | Shows |
|---|---|
| `emit_ctc_stream.py` | CTC log-probs → `make_stream` / `StreamWriter` → `validate` (level and unmet checks) |
| `hypothesis_stream.py` | n-best text only (own beam + LM) → trust layer, hypothesis route |
| `streaming_trust.py` | `FrozenTrustConfig.load` + `StreamingTrustLayer` on stream files |
| `lsl_bridge.py` | sender thread `replay_to_lsl` → `open_source` → `LSLTrustRunner` on one machine |

## Packaging
- `uv build` gives a wheel (82 files, includes the demo configuration) and a small sdist (package, tests, examples, spec). On this Windows/OneDrive machine `uv build` needs `UV_LINK_MODE=copy` (hardlink error 396).
- A clean Python 3.12 venv with only the wheel ran `fidetype version`, `fidetype demo`, `fidetype validate` and the README quickstart (result: COMMIT of the correct text).
- Tests: `tests/test_sdk.py` (13 tests). Full suite 456 passed / 4 skipped.

## Follow-ups
TypeScript and Rust SDKs (M7-06, M7-07), a hosted demo page (M7-08, needs a user decision on GitHub Pages), PyPI release (M7-09). See [tracker](../progress/index.html).

## Related
[streaming trust layer](streaming-trust-layer.md) · [LSL input](lsl-input.md) · [open benchmark](open-benchmark.md) · [roadmap](../questions/roadmap-standard.md)
