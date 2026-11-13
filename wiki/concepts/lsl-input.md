---
title: LSL input (Lab Streaming Layer adapter)
type: concept
tags: [lsl, streaming, real-time, adapter, trust, neuraltextstream, m6]
sources: [neural-input-landscape-2026]
updated: 2026-11-12
---

# LSL input (Lab Streaming Layer adapter)

Diagram: [13-lsl-input.drawio](../diagrams/13-lsl-input.drawio) (rendered in [diagrams/index.html](../diagrams/index.html#s13)).

## What it is
[LSL](../entities/lab-streaming-layer.md) moves time series between programs on one machine or a LAN, with clock synchronisation. The **LSL adapter** (`fidetype.adapters.lsl`, task **M6-01**) connects LSL to Fidetype in both directions:

| Direction | API | CLI |
|---|---|---|
| LSL → NTS events | `LSLEventSource` (`open_source(...)` resolves the streams) | — |
| LSL → trust decisions | `LSLTrustRunner(layer, source)` feeds the [streaming trust layer](streaming-trust-layer.md) | `python -m fidetype.adapters.lsl run --config trust.json --stream-name NAME [--decoder greedy] [--outlet]` |
| NTS file → LSL | `replay_to_lsl(path, name)` (demos, tests) | `python -m fidetype.adapters.lsl replay-to-lsl FILE --name NAME [--speed 1] [--channel-format float32\|double64]` |
| List streams | `list_streams()` | `python -m fidetype.adapters.lsl list` |

`run` writes one `trust_decision` event (FEP-0001) per line on stdout. Log lines go to stderr. With `--outlet` it also publishes each decision on an LSL marker stream `fidetype.decisions`, so other programs can subscribe.

## Dependency and licence
- `pylsl` is **optional**: `pip install "fidetype[lsl]"` (or `uv sync --extra lsl`). The module imports without it. A call that needs the network raises `LSLUnavailableError` with the install command. The CLI then exits with code 2.
- `pylsl` 1.18.6: licence MIT (package classifier). The Windows wheel includes liblsl (`pylsl/lib/lsl.dll`, liblsl 1.18). We checked this on Windows 11. PyPI also lists wheels for macOS (universal2) and Linux (manylinux_2_35 x86_64), and a pure-Python wheel without liblsl. We did not test those.
- We copy no LSL code. The adapter is our own code (Apache-2.0).

## NTS over LSL (spec 6.4, as implemented)

| NTS part | LSL stream | Details |
|---|---|---|
| Frames | type `NTS`, V numeric channels | One sample per frame. Channel labels = vocab tokens, unit `log_prob`. `nominal_srate` = 1 / `frame_period`. The desc element `fidetype` holds `nts_header` (the NTS header as JSON), `values` and `events_source_id` |
| Other events | type `Markers`, 1 string channel | One sample = one NTS event as JSON (`hypothesis`, `segment_end`, `end`, `signal_quality`, ...). Its desc holds the same `nts_header` and `frames_source_id` |
| Times | LSL timestamps | The inlet sets `clock_domain = "lsl"`. It replaces the `t` of a frame with the LSL time. It adds `lsl_t` to marker events |

The header is in the desc, so a program that connects late still gets it.

Spec 6.4 says "float32". `replay-to-lsl` sends float32 by default. It can also send `double64`. Then the received rows are bit-equal to the file rows.

## Which streams work

| Stream | What to pass | Notes |
|---|---|---|
| NTS stream from a Fidetype producer | the stream name | Header, vocab and events stream come from the desc (`--events auto`) |
| Class probabilities from another decoder | `--vocab` (default: the channel labels), `--vocab-type`, `--blank`, `--values log_probs\|probs\|logits` | The adapter adds `adapter.name`, `adapter.version` and `data.derived` to `meta` |
| Raw EEG / EMG samples | a `SignalDecoder` object (Python API) | It turns sample chunks into frames. Fidetype has no EEG decoder |
| Text decoder output on a marker stream | the stream name; no `--decoder` | JSON `hypothesis` events, or plain strings with `--plain-markers hypothesis` |
| Task markers from another program (for example "trial_end") | `--events NAME --boundary-marker trial_end` | A matching string ends the utterance (`segment_end`) |

## Clock, order, gaps and loss

| Problem | What the adapter does | Setting |
|---|---|---|
| Different clocks on sender and receiver | t = LSL timestamp + `time_correction()`, refreshed every 5 s. Inlets from the same sender host share one offset, so offset noise cannot change the order of a frame and a marker | `--clock receiver` (default) or `sender` (raw timestamps) |
| Timestamp ≤ the last one (NTS needs strictly increasing times) | At most 5 ms back: move it 1 µs after the last one (clamp). More: drop it. Both are counted | `--out-of-order clamp\|drop\|error` |
| Gap (step > 2.5 nominal periods) | `mark` (default): an extension `gap` event; the layer ignores it; the count goes into provenance. `segment`: end the utterance at the gap. `abort`: drop the utterance without a decision | `--on-gap` |
| Two inlets (frames + events) | Merge by time. An item waits until the other inlet has passed its time, or for the merge window | `--merge-window 0.05` |
| Stream lost (sender stopped, network) | The runner **drops the cut utterance without a decision** (`StreamingTrustLayer.abort_utterance`). The source re-resolves the stream (by `source_id`) for up to 30 s. After a reconnect it sends the header again | — |
| Producer sends no boundary | `--idle-flush S` ends the utterance after S idle seconds | off by default |

Each decision carries an `lsl` record in its provenance and in the output event: the stream ids (name, type, source_id, uid; never the host name), the clock mode, the current offset, the number of offset updates, the reconnect count, the per-utterance counts (frames, gaps, clamped, dropped) and `e2e_latency_s`.

> **Our take:** a decision on a cut input could commit a cut sentence. So a loss or an `abort` gap drops the utterance. The user then repeats it. This costs time, but it never commits text that the user did not finish.

## Tests
`tests/test_adapter_lsl.py`, 26 tests.

| Kind | What it checks |
|---|---|
| Fake inlet (no pylsl), 22 tests | Import without pylsl; header from desc XML and from labels (host name never written); value kinds; clock correction (receiver, sender, refresh, shared host offset); clamp / drop / error; gaps (mark, segment, abort); loss → abort → reconnect → header; loss without reconnect raises; merge watermark; bad events skipped; idle flush; raw-signal decoder; `abort_utterance` |
| Fake loopback | 5 utterances (frames + markers inlets): decisions equal the file replay path exactly |
| Real LSL loopback on localhost (skipped without pylsl / liblsl), 4 tests | Outlet → inlet → trust layer: double64 frames give exactly the file replay decisions; float32 frames give the same actions and texts (p_top1 within 1e-4); hypothesis-only marker stream equal; `fidetype.decisions` outlet round trip |

CI installs only the `dev` extra, so CI skips the 4 real-LSL tests. The local `.venv` has pylsl and runs them.

## Latency (loopback, localhost, synthetic)
`experiments/2026-11-12-m6-lsl/bench_lsl_latency.py`; numbers in [results/latency.md](../../experiments/2026-11-12-m6-lsl/results/latency.md). 12 simulator utterances (4 378 frames of 40 ms) in one file, `segment_end` between utterances, 0.5 s pause between them. Frozen synthetic config of M4-03, CTC greedy decoder. Outlet and inlet on one Windows PC (localhost), pylsl 1.18.6, CPU only.

- **transport** = receive time − (LSL timestamp + time correction), per sample.
- **e2e** = emission of the final decision − LSL time of the event that closed the utterance. It includes the merge wait, the decode and the trust core.

| Run | Frames | Speed | Merge window | Equal to file replay | Transport p50 / p95 | e2e final p50 / p95 / max |
|---|---|---|---|---|---|---|
| A | float32 | real time | 50 ms | 12/12 exact | 3.5 / 6.6 ms | 60.6 / 61.6 / 61.6 ms |
| B | double64 | 4× | 50 ms | 12/12 exact | 3.6 / 6.7 ms | 56.3 / 60.4 / 60.6 ms |
| C | float32 | 4× | 10 ms | 12/12 exact | 3.6 / 7.1 ms | 17.2 / 19.1 / 19.3 ms |
| D: hypothesis route, 213 marker events every 50 ms | — | real time | — | 30/30 exact | 3.2 / 7.0 ms | 3.0 / 7.2 / 45.7 ms |
| E: the two CLIs in two processes (`replay-to-lsl` → `run --outlet`) vs `python -m fidetype.trust.streaming replay` | float32 | 4× | 50 ms | 12/12 (action, shown, p_top1, set size, guard risk) | — | 91.9 / 99.1 / 101.3 ms |

Notes:
- In A–C the frames stop during the pause after each utterance. So the closing `segment_end` waits for the full merge window. The merge window is the largest part of e2e: 50 ms → about 57–61 ms, 10 ms → about 17 ms.
- The transport maximum is about 0.5 s in each run, once. We think it is the start-up (the first `time_correction()` call blocks while samples queue). We did not check this.
- No sample was clamped, dropped or released late. The time correction on localhost was below 15 µs.
- All 12 frame-route decisions were COMMIT. The greedy decoder gives a 1-best list, so p_top1 is the same with float32 and double64 frames. The unit tests cover the other actions.

> **Our take:** on one machine, LSL adds about 3–7 ms per sample. The trust decision follows the closing event after the merge window plus about 7 ms. With one inlet (a marker stream only) there is no merge wait (run D). With two inlets, a smaller merge window lowers the wait but makes a late marker more likely. LAN and Wi-Fi need their own test (M6-10).

## How to connect common tools
We state only what their documentation says (checked 2026-11-12).

| Tool | What its docs say | How to use it with Fidetype |
|---|---|---|
| **OpenBCI GUI** | The Networking widget can send data over LSL. The GUI docs name FFT data over LSL (from v4.1.5-beta.3); the networking section lists Time Series, FFT, EMG, Band Power, Accel/Aux and Pulse data ([docs](https://docs.openbci.com/Software/OpenBCISoftware/GUIWidgets/)). The LSL docs list OpenBCI as "supported via vendor-provided software" ([LSL devices](https://labstreaminglayer.readthedocs.io/info/supported_devices.html)) | These are raw or spectral signals, not decoder output. Use a `SignalDecoder` (Python API), or a decoder program that publishes an NTS stream |
| **BrainFlow** | The board docs show a Synthetic board (no hardware needed) and a Streaming board fed by `add_streamer`. They do not mention LSL ([boards](https://brainflow.readthedocs.io/en/stable/SupportedBoards.html)) | Write a small script: read BrainFlow data, run a decoder, publish NTS frames with pylsl (or call `LSLEventSource` with a `SignalDecoder`). The P4 exit test with the Synthetic board is a follow-up |
| **LabRecorder** | "LabRecorder saves data to Extensible Data Format (xdf)" ([LSL getting started](https://labstreaminglayer.readthedocs.io/info/getting_started.html)) | It can record the NTS streams and `fidetype.decisions` next to the raw signal. Not tested by us |
| **Muse, Emotiv, g.tec** | Listed in the LSL device list (third-party or vendor software) ([LSL devices](https://labstreaminglayer.readthedocs.io/info/supported_devices.html)) | Raw signals: same path as OpenBCI. Not tested (no hardware) |

## Limits and follow-ups
- Tested on one machine (localhost) only. LAN and Wi-Fi latency are not measured.
- No real device was tested (the user has no hardware). The BrainFlow Synthetic board test is a follow-up.
- `gap` and `lsl_t` are extension keys; `hypothesis` `t_start` / `t_end` stay in the producer's clock. A FEP should define the LSL binding fully (stream types, desc keys, float32 vs double64, gap event).
- The frames route decodes at the end of the utterance (M4-08 incremental decoding).

## Related
[Streaming trust layer](streaming-trust-layer.md) · [Lab Streaming Layer](../entities/lab-streaming-layer.md) · [BrainFlow](../entities/brainflow.md) · [Conformance suite](conformance-suite.md) · [Standard roadmap](../questions/roadmap-standard.md)

Live demo over LSL: see [Python SDK and offline demo](python-sdk.md) and `examples/lsl_bridge.py`.
