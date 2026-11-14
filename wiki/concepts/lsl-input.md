---
title: LSL input (Lab Streaming Layer adapter)
type: concept
tags: [lsl, streaming, real-time, adapter, trust, neuraltextstream, m6]
sources: [neural-input-landscape-2026]
updated: 2026-11-13
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
| BrainFlow board → LSL (raw signal) | `BrainFlowBridge(board, descr, board_id)` in `fidetype.adapters.brainflow_bridge` | `fidetype lsl brainflow-bridge --board synthetic [--board-id N --serial-port PORT] [--trial-s 4]` |

`run` writes one `trust_decision` event (FEP-0001) per line on stdout. Log lines go to stderr. With `--outlet` it also publishes each decision on an LSL marker stream `fidetype.decisions`, so other programs can subscribe.

## Dependency and licence
- `pylsl` is **optional**: `pip install "fidetype[lsl]"` (or `uv sync --extra lsl`). The module imports without it. A call that needs the network raises `LSLUnavailableError` with the install command. The CLI then exits with code 2.
- `pylsl` 1.18.6: licence MIT (package classifier). The Windows wheel includes liblsl (`pylsl/lib/lsl.dll`, liblsl 1.18). We checked this on Windows 11. PyPI also lists wheels for macOS (universal2) and Linux (manylinux_2_35 x86_64), and a pure-Python wheel without liblsl. We did not test those.
- We copy no LSL code. The adapter is our own code (Apache-2.0).

## NTS over LSL (FEP-0002)

[FEP-0002](../../spec/feps/0002-nts-over-lsl.md) (status Draft, M6-09) is the normative binding. The adapter is its reference implementation. Binding version: `nts-lsl/0.1`.


| NTS part | LSL stream | Details |
|---|---|---|
| Frames | type `NTS`, V numeric channels | One sample per frame. Channel labels = vocab tokens, unit `log_prob`. `nominal_srate` = 1 / `frame_period`. The desc element `fidetype` holds `nts_header` (the NTS header as JSON), `values` and `events_source_id` |
| Other events | type `Markers`, 1 string channel | One sample = one NTS event as JSON (`hypothesis`, `segment_end`, `end`, `signal_quality`, ...). Its desc holds the same `nts_header` and `frames_source_id` |
| Times | LSL timestamps | The inlet sets `clock_domain = "lsl"`. It replaces the `t` of a frame with the LSL time. It adds `lsl_t` to marker events |
| Decisions | `fidetype.decisions`, type `Markers`, 1 string channel | One sample = one `trust_decision` (FEP-0001). Desc: `role`, `event_type`, `spec`, `binding`, `config_id` |

The header is in the desc, so a program that connects late still gets it.

Spec 6.4 says "float32". `replay-to-lsl` sends float32 by default. It can also send `double64`. Then the received rows are bit-equal to the file rows.

### FEP-0002 rules in brief

| Topic | Rule |
|---|---|
| Channel format | An NTS-native frames stream is `float32` or `double64`. float32 rounds by about 6e-8 (relative); the row still meets the 1e-3 normalisation rule. Use `double64` for exact replay (audit, provenance hash) |
| Channels | `channel_count` = V. Labels, if present, are the vocab in order (trimmed; an empty label matches any token, because XML loses the space token) |
| Rate | `nominal_srate` = 1 / `frame_period` (relative tolerance 1e-6), or 0 if irregular |
| desc keys | `nts_header` (JSON object, spec_version 0.1), `values`, `binding`, `role`, `events_source_id` / `frames_source_id`, `event_clock` |
| Clock | t = LSL timestamp + `time_correction` (receiver mode), one offset per sender host. Out-of-order frames: clamp (at most 5 ms back) or drop, counted |
| Times inside marker JSON | `event_clock = lsl`: `t`, `t_start`, `t_end`, `t_signal_*`, `t_decoded`, `t_emitted` are in the sender's LSL clock; the inlet adds the same offset. `source` (or absent): left as sent. Hypothesis times and frame times are then on one axis |
| Gaps and loss | `gap` extension event, or `segment_end`, or abort. A loss never gives a decision on the cut utterance; after a reconnect the header comes again |
| Versioning | `binding` absent = `nts-lsl/0.1`. An unknown version is refused |

Adapter changes for FEP-0002 (small): it refuses an NTS-native frames stream with an integer format, labels out of order or a wrong `nominal_srate`, and any stream with an unknown `binding` or `event_clock`. It applies `event_clock = lsl`. `replay-to-lsl` now writes `binding` and `event_clock = lsl` and maps the time fields of marker events to the LSL clock. The decisions outlet writes `binding`. New helpers: `info_to_xml`, `ScriptedInlet` (a scripted inlet without pylsl), `check_binding`, `check_native_frames`, `decisions_desc`, `LSLTrustRunner.flush()`. Streams from before FEP-0002 still read the same way (no `binding` = 0.1, no `event_clock` = source).

### Conformance profile `fep-0002`
31 golden vectors (15 accept, 16 reject) in `spec/conformance/fep-0002/`. Each vector is a JSON scenario: stream infos as liblsl XML, scripted chunks with LSL timestamps (or `"lost"`), the clock correction and the consumer settings. No network and no pylsl are needed. The expected values include the header, frame count and times, `-inf` cells, a SHA-256 of the double64 rows, the event types, hypothesis times, decisions, and the counts of gaps, clamps, drops, reconnects and bad markers.

```bash
fidetype conformance --profile fep-0002                         # reference consumer over the 31 scenarios
fidetype conformance check --profile fep-0002 frames-info.xml   # producer check of a stream info (pylsl: info.as_xml())
```

## Which streams work

| Stream | What to pass | Notes |
|---|---|---|
| NTS stream from a Fidetype producer | the stream name | Header, vocab and events stream come from the desc (`--events auto`) |
| Class probabilities from another decoder | `--vocab` (default: the channel labels), `--vocab-type`, `--blank`, `--values log_probs\|probs\|logits` | The adapter adds `adapter.name`, `adapter.version` and `data.derived` to `meta` |
| Raw EEG / EMG samples | a `SignalDecoder` object (Python API; `open_source` also takes a factory `info -> decoder`), or `--signal-decoder toy-flat\|toy-features` | It turns sample chunks into frames. Fidetype has no EEG text decoder. The `toy-*` decoders carry **no text information** (pipeline tests only; see [BrainFlow live test](#brainflow-live-test-m6-08)) |
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

`tests/test_brainflow_bridge.py` (M6-08), 14 tests: the bridge with a fake board and recording outlets (stream desc, stamp smoothing, dropout jump, trial markers, board markers), the toy decoders, the scripted raw-signal path into the trust layer (no COMMIT, one gap), the decoder factory and the CLI. One live test (Synthetic board → pylsl → trust layer) skips without brainflow and pylsl.

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

## BrainFlow live test (M6-08)
Task M6-08 (the P4 exit check) ran the full live path with the [BrainFlow](../entities/brainflow.md) Synthetic board (board id -1: 16 EEG channels, 250 Hz, fake data, no hardware). Script, numbers and logs: [results.md](../../experiments/2026-11-13-m6-08-brainflow-live/results.md).

```
pip install "fidetype[lsl,brainflow]"
fidetype lsl brainflow-bridge --board synthetic --trial-s 4                         # shell 1
fidetype lsl run --config src/fidetype/demo/trust-config-demo.json \
  --stream-name fidetype.brainflow --signal-decoder toy-flat --decoder demo --max-attempts 1   # shell 2
```

The bridge (`fidetype.adapters.brainflow_bridge`, our own code) sends two LSL streams:

| Stream | Type | Content | `desc/fidetype/role` |
|---|---|---|---|
| `fidetype.brainflow` | `EEG` (or `EMG`, `ExG` with `--kind`) | the board channels of that kind, float32, `nominal_srate` = board rate; channel `label` = electrode name, `unit` = `microvolts` | `signal` |
| `fidetype.brainflow.markers` | `Markers` | plain `segment_end` every `--trial-s` seconds (a fixed trial clock); `brainflow_marker:<v>` for the BrainFlow marker channel | `signal_markers` |

- **Stamps.** The Synthetic board sends samples in packets (about 16 ms apart). Raw stamps would look like gaps. The bridge maps the board time to the LSL clock and smooths it (1 / srate per sample, 1 % pull to the board time). If the board time jumps more than 0.25 s ahead (lost data), the stamp jumps too, so the consumer sees a real gap.
- **Dropout test.** `--pause AT:FOR` discards the board data for FOR seconds (repeatable).
- **Toy decoders** (`fidetype.decoders.toy_signal`): `flat` gives near-uniform frames that ignore the signal. `features` maps per-channel log variance through a fixed random matrix: the frames change with the signal but carry no text information. 25 frames/s over the 28-token character vocab. The header says `decoder.toy = true` and `decoder.text_information = none`.

Results (two processes on one PC, 70 s per mode, dropout + hard kill + reconnect + clean stop):

| | `toy-flat` | `toy-features` |
|---|---|---|
| Final decisions: COMMIT / OFFER / ABSTAIN | 0 / 0 / 13 | 0 / 0 / 13 |
| Gaps found / losses / reconnects / aborted utterances | 1 / 4 / 2 / 2 | 1 / 4 / 2 / 2 |
| Transport p50 / p95 | 11.5 / 21.1 ms | 11.5 / 21.2 ms |
| e2e steady p50 / p95 (10 decisions) | 32.8 / 45.7 ms | 38.1 / 45.1 ms |
| CPU of one core: consumer / bridge | 2.4 % / 2.3 % | 2.2 % / 2.4 % |

- Every decision was ABSTAIN with `guard risk 1.00 >= 0.80`. The demo beam + LM still writes fluent text from such frames, so "always commit" would have typed 26 wrong texts.
- A kill or a clean stop aborted the open utterance (no decision). The consumer reconnected by `source_id` and sent a new header.
- The trial boundary inside the dropout came 0.25 s late (`trial_hold_s`). That decision had e2e ≈ 370 ms.
- **Fix found by this test.** liblsl's `pull_chunk(timeout > 0)` waits until `max_samples` samples are there or the timeout ends. At a 50 ms poll on a 250 Hz stream this added about 25–30 ms. `PylslInlet.pull_chunk` now pulls with timeout 0 and sleeps 2 ms between empty pulls (transport p50 37 → 11.5 ms; steady e2e p50 57–61 → 33–38 ms). The [latency](#latency-loopback-localhost-synthetic) table above was measured before this change.

> **Our take:** the P4 exit check passes. A real device SDK feeds the live path, and the guard stops an LM that hallucinates on a signal with no text in it. This does not show EEG text decoding. A real board (OpenBCI) needs hardware and is a follow-up.

## Soak test (M6-13)
Task M6-13 ran the same live chain for hours, with the M4-08 to M4-10 settings: the incremental demo decoder, the M4-09 GC rule, and a shadow CTC beam + bounded `CharNgramLM` on the same frames. The bridge restarted every 30 min (hard kill and clean stop in turn), with one 3-s dropout per bridge life. A consumer read the `trust_decision` events from the LSL outlet and checked every event with the conformance validator. Plan (criteria fixed before the run): [plan.md](../../experiments/2026-11-13-m6-13-soak/plan.md). Results: [results.md](../../experiments/2026-11-13-m6-13-soak/results.md).

| | main run | post-fix run |
|---|---|---|
| active time / final decisions | 6.78 h / 6,067 | 2.5 h / 2,242 |
| COMMIT on toy input (no text information) | 0 | 0 |
| invalid / lost events (consumer side) | 0 / 0 | 0 / 0 |
| gaps = dropouts; reconnects = 2 x restarts | 14 = 14; 26 = 26 | 5 = 5; 8 = 8 |
| push p95, worst 2-min window | 1.76 ms | 0.75 ms |
| end-of-utterance p95, worst window; e2e p95 | 9.97 ms; 55 ms | 3.96 ms; 56 ms |
| trust private bytes after warm-up | **+16.9 MB/h** (bug 1) | +0.80 MB/h |
| transport p50 | 11 ms, but **1,373 ms** in 3 windows (bug 2) | 11.2-11.3 ms |
| pass criteria | 7 of 10 (C1: outside kill at 6.78 h; C2; C9) | 10 of 10 |

Two bugs found and fixed (with tests):
1. **Guard memo.** The guard used the shared 200,000-entry `cached_edit_distance` memo. Live, it grew by about 30 entries (about 22 KB) per decision for about 7.5 h, and the idle GC grew from 0.8 to 8 ms. The guard now has its own 4,096-entry memo (`guard_edit_distance`). See [streaming trust layer](streaming-trust-layer.md) (guard memo, M6-13).
2. **Wall-clock step in the bridge.** Windows set the clock back by 1,361 ms. The bridge used one wall-to-LSL offset taken at start, so all later stamps were 1.36 s late until the bridge restarted. A forward step would have made a false gap. The bridge now measures the offset at each read and handles a step (`clock_steps`). See [BrainFlow](../entities/brainflow.md#fidetype-bridge-m6-08).

> **Our take:** the live path is stable for hours when both fixes are in: no memory growth, no lost or invalid events, no wrong commits, and push p95 under 1 ms. Two limits stay. The post-fix run lasted 2.5 h, not 6-8 h. No wall-clock step happened during it, so only unit tests check the bridge fix. A reconnect also blocks the consumer loop for up to 6 s while it resolves the new stream; LSL buffers the data, so nothing is lost.

## How to connect common tools
We state only what their documentation says (checked 2026-11-12).

| Tool | What its docs say | How to use it with Fidetype |
|---|---|---|
| **OpenBCI GUI** | The Networking widget can send data over LSL. The GUI docs name FFT data over LSL (from v4.1.5-beta.3); the networking section lists Time Series, FFT, EMG, Band Power, Accel/Aux and Pulse data ([docs](https://docs.openbci.com/Software/OpenBCISoftware/GUIWidgets/)). The LSL docs list OpenBCI as "supported via vendor-provided software" ([LSL devices](https://labstreaminglayer.readthedocs.io/info/supported_devices.html)) | These are raw or spectral signals, not decoder output. Use a `SignalDecoder` (Python API), or a decoder program that publishes an NTS stream |
| **BrainFlow** | The board docs show a Synthetic board (no hardware needed) and a Streaming board fed by `add_streamer`. They do not mention LSL ([boards](https://brainflow.readthedocs.io/en/stable/SupportedBoards.html)) | Use `fidetype lsl brainflow-bridge` (M6-08). It streams a BrainFlow board to LSL as a raw-signal stream. A `SignalDecoder` then makes frames. Tested with the Synthetic board only |
| **LabRecorder** | "LabRecorder saves data to Extensible Data Format (xdf)" ([LSL getting started](https://labstreaminglayer.readthedocs.io/info/getting_started.html)) | It can record the NTS streams and `fidetype.decisions` next to the raw signal. Not tested by us |
| **Muse, Emotiv, g.tec** | Listed in the LSL device list (third-party or vendor software) ([LSL devices](https://labstreaminglayer.readthedocs.io/info/supported_devices.html)) | Raw signals: same path as OpenBCI. Not tested (no hardware) |

## Limits and follow-ups
- Tested on one machine (localhost) only. LAN and Wi-Fi latency are not measured.
- No real device was tested (the user has no hardware). The BrainFlow Synthetic board test is done (M6-08), and so is a 6.78 h + 2.5 h soak test (M6-13). A real board (OpenBCI) needs hardware.
- A reconnect resolves the new stream inside `poll()` and blocks the loop for up to 6 s (M6-13). Moving the resolve to a thread is a possible follow-up.
- FEP-0002 defines the binding (M6-09). It stays Draft until an outside LSL implementation runs the `fep-0002` vectors.
- The frames route decodes at the end of the utterance (M4-08 incremental decoding).

## Related
[Streaming trust layer](streaming-trust-layer.md) · [Lab Streaming Layer](../entities/lab-streaming-layer.md) · [BrainFlow](../entities/brainflow.md) · [Conformance suite](conformance-suite.md) · [Standard roadmap](../questions/roadmap-standard.md)

Live demo over LSL: see [Python SDK and offline demo](python-sdk.md) and `examples/lsl_bridge.py`.

For browsers and remote clients, see [WebSocket input and output](websocket-input.md) (M6-11, FEP-0004): the same runner pattern over WebSocket; no merge window, so the final decision follows the closing event after about 1-2 ms on localhost (LSL: 17-61 ms, set by the merge window).
