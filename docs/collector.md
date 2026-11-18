# Collector

The Collector is one service. It reads NeuralTextStream (NTS) input from several sources, runs processors on it, and writes the results to several targets. One TOML or JSON file wires it. The design copies the structure of the OpenTelemetry Collector (receivers → processors → exporters). The text and the code are our own.

Status: reference v0 in the Python package. The design is the draft [FEP-0006](../spec/feps/0006-collector.md). It is not part of NTS 1.0, because it does not change the format.

```
 file  ----> receiver --\                                                   /--> jsonl (NTS stream, decision log)
 ws /nts --> receiver ---+--> validate --> segment --> trust | guard --> thin --> redact --+--> stdout
 LSL -----> receiver --/                                                     +--> ws /decisions
                                                                             +--> LSL decisions outlet
                                                                             \--> os_text (stub)
```

## Run it

```sh
fidetype collector --config examples/collector/collector.toml --check   # check the file, print the pipelines
fidetype collector --config examples/collector/collector.toml           # run it
```

`fidetype-collector` is the same command. Run the example from the repository root. Relative paths in a configuration resolve against the folder of the configuration file. The example reads a synthetic conformance vector and uses a toy trust configuration. Fit a real one with `fidetype.calibrate(...)`.

## Components

| Kind | Types | Job |
|---|---|---|
| Receiver | `file` (JSON Lines, also tail mode; NPZ), `websocket` (FEP-0004 `/nts`), `lsl` (FEP-0002) | Read a source. Turn every loss into a `gap` or `lost` status |
| Processor | `validate`, `segment`, `trust`, `guard`, `thin`, `redact`, `privacy` | Check events, add segment ends, make trust decisions, drop previews, remove or hash decoded text, filter `meta` keys per a privacy policy |
| Exporter | `jsonl`, `stdout`, `websocket` (`/decisions`), `lsl`, `os_text` (`stub` backend only) | Write items out. Never change them |
| Pipeline | any number | Connect named receivers, processors and exporters |
| Service | `[service]` | Log level, metrics file, health endpoint (`/healthz`, `/metrics`, localhost by default), `latency = true` (per-stage latency) |

Examples: [`collector.toml`](../examples/collector/collector.toml) (file input) and [`collector-lsl.toml`](../examples/collector/collector-lsl.toml) (LSL input; needs the `lsl` extra). Each key is explained in comments in the files.

### The new parts of P3-02 to P3-04

| Component | Keys | What it does |
|---|---|---|
| `segment` processor | `pause_s`, `blank_frames`, `max_frames`, `unit` | Adds a `segment_end` when the time between two frames is more than `pause_s`, after `blank_frames` blank frames in a row (after a non-blank frame), or after `max_frames` frames. Causal. A `segment_end` from the source passes through. |
| `guard` processor | `guard` or `profile`, `online`, `online_options`, `passthrough`, `save_profile`, `audit_keep` | The drop-in trust guard ([trust quickstart](trust-quickstart.md)). `profile` loads a per-user profile ([personalisation](trust-personalisation.md)) with its drift tests. `online = "aci"` (or `aci_window`, `window`, `bandit`) adds the online controller. One decision per segment. `passthrough = true` also passes the input events on (without the `ws_*` binding keys), so a `jsonl` exporter can write the NTS stream next to the decision log. |
| `os_text` exporter | `backend = "stub"`, `path`, `separator` | Types **only** final text COMMITs (never OFFER, ASK, ABSTAIN or a provisional decision). The stub types into memory and writes one line per typed text with the full decision next to it. Real backends (Windows TSF, Android IME, macOS, IBus) are not written yet (P3-03). |
| `privacy` processor (P5-04) | `policy`, `key_env`, `key_id`, `subject_index` | P5-15: `subject_index` writes one line per stream (session + HMAC code of `subject.id`; needs `key_env`) so that an erasure request finds the subject's outputs. Filters header `meta` keys per a policy file (keep / drop / hash per key or `namespace.*`; default for other keys; PII scan) and, with `text = "drop"` or `"hash"`, the decoded text (then it must come after the trust step). Without `policy` the built-in default keeps the provenance keys and drops `subject.*`, `session.*`, `user.*` and unknown keys. See [provenance and privacy](provenance-and-privacy.md) |
| `jsonl` exporter path `{session}` (P5-15) | `path = "out/streams/{session}.nts.jsonl"` | One file per stream / decision session, so an erasure can delete a whole session file. See [provenance and privacy](provenance-and-privacy.md) section 8 |
| Input-event `jsonl` file without `{session}` (P5-17) | refused | When the pipelines of the exporter can carry more than one stream (several receivers, several file paths, a websocket or LSL receiver), `--check` refuses the file. Reason: the streams would follow one another in one file (several headers, no stream id). That file is not one NTS stream, `nts-conform` cannot check it, and an erasure can only delete it whole. Use `path = "out/streams/{session}.nts.jsonl"`. A decision log is not affected (each line names its session) |
| `trust` processor, `ledger.anchor` (P5-16) | `{ dir = "out/anchors", key_env = "...", every_n = 100, every_s = 60 }` | Signed anchors (Ed25519, extra `[sign]`) on stop and every N entries / T seconds; key from an environment variable or a key file only. See [provenance and privacy](provenance-and-privacy.md) section 4.1a |
| `trust` processor, `ledger.lineage` (P5-03) | a lineage spec file | Writes sources and artifacts (with licences) into the ledger at start; each decision then carries licence flags |
| `[service] latency` | `latency = true`, `latency_budget_ms` | Records the time of each stage (section "Latency budget"). The numbers are in `/metrics` and in `metrics_file` (`latency_ms`). |

The `guard` processor uses the same parts as `fidetype live` ([live decode](live-decode.md)): `TrustGuard.decide`, and the key beam search `nbest_of_frames` for key frames. For an n-best guard the segment input is the last final `hypothesis`; for a logits guard it is the frames of the segment.

## Safety and privacy rules

| Rule | What the Collector does |
|---|---|
| No final decision on a cut segment | A gap or a lost input drops the open utterance without a decision |
| No silent drop | An unreadable line or an invalid event becomes a `gap` status |
| Decoded text is personal data | The `redact` processor removes `shown` or replaces it with an HMAC (key from an environment variable) |
| `meta` holds only what the policy allows (SEC-3, SEC-4) | The `privacy` processor drops or hashes `meta` keys per a policy file and drops a value that looks like an e-mail address, a phone number or an IP address |
| No secrets in files | Tokens and keys come only from environment variables. A key in the file is a configuration error |
| No blank final COMMIT | The `trust` processor adds a commit gate if the configuration has none (rule TD-9). The `guard` processor always has the gate |
| Only committed text reaches the OS | The `os_text` exporter types final COMMITs only and logs the full decision next to each typed text |

## Integration test and latency budget (P3-04)

`python -m fidetype.collector.bench` runs the full pipeline from one TOML file on synthetic input at a realistic rate. The test file [`tests/test_collector_pipeline.py`](../tests/test_collector_pipeline.py) runs the same code in CI.

```
receiver (websocket /nts | file | lsl)
  -> validate (stream level provenance) -> segment -> guard (per-user profile, online ACI, passthrough)
  -> jsonl NTS stream + jsonl decision log + os_text stub (+ websocket /decisions)
```

```sh
python -m fidetype.collector.bench --out bench-out                                  # all profiles, WebSocket + file
python -m fidetype.collector.bench --profile emg-key --receiver lsl --json r.json   # needs the lsl extra
```

Each run checks:

- `nts-conform` gives the outputs (NTS stream file + decision log) the producer level **NTS Trust-ready** (claim `text`).
- The `os_text` stub typed exactly the final COMMITs.
- One decision per segment; the `/metrics` file holds the latency numbers.

### Profiles

| Profile | Input | Guard | Gated |
|---|---|---|---|
| `implant-speech` | CTC character frames at 50 Hz (20 ms) and the decoder's final n-best `hypothesis` after each utterance (the decoder and its language model run before the collector, as in a B2T '25 replay). No source boundaries: the segmenter cuts after 6 blank frames | n-best guard, calibrated on synthetic n-best lists | yes |
| `emg-key` | One key-posterior frame per key over the 32-key KT-sEMG vocabulary, sent at 50 Hz (faster than any typist), and a `segment_end` per phrase | `builtin:synthetic-keys` (the guard of `fidetype live`) on the key beam search | yes |
| `implant-logits` | The implant frames without the hypothesis | logits guard: its built-in CTC prefix beam search (beam 64, lexicon, n-best confidences) runs **inside** the collector | no (reported) |

All input is synthetic and our own. It contains no participant data.

### Stages

| Stage | From | To |
|---|---|---|
| `receive` | the receive stamp of the trigger event: `ws_t_recv` (WebSocket server) or `_fidetype_t_recv` (LSL receiver: the time the sample was pulled from the inlet, P3-07) | the receiver's poll returns |
| `processor.<name>`, `exporter.<name>` | start of the call | end of the call |
| `pipeline` | poll returns | the last exporter returns |
| **`added`** (the budget number) | the trigger event is available (its receive stamp; for file input: the poll return) | the last exporter returns |
| `e2e` | `ws_t_sent` of the trigger event (producer on the same host) | the last exporter returns |

The trigger event of a step is the last boundary (`segment_end`, `end`) of the batch. A boundary that the segmenter adds carries the stamps of the frame that caused it. One sample per step that wrote a decision. The clock is `time.perf_counter`.

### Results (2026-11-17, Windows 11 laptop, CPU, 12 segments per run)

First run (P3-04). For LSL input these numbers start at the poll return, so they do not include the inlet merge-window wait (see "LSL receive stamps (P3-07)" below).

`added` latency in milliseconds. Budget: **p95 < 50 ms**.

| Profile | Receiver | p50 | p95 | p99 | Budget |
|---|---|---|---|---|---|
| implant-speech | websocket | 1.05 | 1.27 | 1.27 | PASS |
| implant-speech | file | 0.69 | 1.12 | 1.32 | PASS |
| implant-speech | lsl | 0.81 | 1.11 | 1.19 | PASS |
| emg-key | websocket | 1.85 | 2.34 | 2.37 | PASS |
| emg-key | file | 1.01 | 1.16 | 1.21 | PASS |
| emg-key | lsl | 1.59 | 2.23 | 2.55 | PASS |
| implant-logits | websocket | 64.2 | 104.1 | 107.4 | over (not gated) |
| implant-logits | file | 62.5 | 108.0 | 109.6 | over (not gated) |
| implant-logits | lsl | 66.8 | 107.3 | 117.4 | over (not gated) |

- Almost all of the added time is the `guard` stage (the trust decision; for `emg-key` also the key beam search). `validate`, `segment` and the exporters take less than 0.3 ms per step at p95. The WebSocket `e2e` time (with the loopback transport) is 0.2 to 0.3 ms above `added`.
- `implant-logits` does not meet the budget: the guard's built-in CTC beam search (n-best confidences over 64 texts) takes 60 to 110 ms per segment. This is decoding work, not collector overhead. It is an open gap (P3-06): decode during the frames, not at the boundary.
- For LSL input `added` started at the poll return in this first run. P3-07 (next section) fixed this.

### LSL receive stamps (P3-07)

The LSL receiver now stamps each event with the time when the LSL source pulled its sample from the inlet (`_fidetype_t_recv`, `time.perf_counter` clock, never written out). `receive` and `added` count from this stamp. So the time that the inlet merge window (`merge_window_s`) holds an event is now part of the budget number.

A frames stream and an events stream go through one merge. The merge holds an event until the other stream has passed its time, or until `merge_window_s` ends. Between markers the events stream is idle, so in practice every frame and every boundary waits for the merge window. Two changes:

- `LSLEventSource.poll` now waits at most until the merge window of the oldest held event ends. Before, it waited for the next sample (one frame period, 20 ms at 50 Hz), so a held event left up to one frame late.
- The bench sets `merge_window_s = 0.02` for LSL input (`--lsl-merge-window`, `LSL_MERGE_WINDOW_S`). The receiver default stays 0.05 s.

`added` latency, LSL input, milliseconds (12 segments per run, same laptop; the B2T '25 replay of P3-08 ran at the same time):

| Profile | Run | `merge_window_s` | p50 | p95 | p99 | Budget |
|---|---|---|---|---|---|---|
| implant-speech | P3-04 (poll return, no merge wait) | 0.05 | 0.81 | 1.11 | 1.19 | PASS |
| implant-speech | stamps only | 0.05 | 61.1 | 61.3 | 61.3 | over |
| implant-speech | stamps only | 0.02 | 40.4 | 41.1 | 41.2 | PASS |
| implant-speech | stamps + poll wait bound | 0.05 | 58.0 | 60.4 | 60.6 | over |
| implant-speech | **stamps + poll wait bound (bench default)** | **0.02** | **21.2** | **26.8** | **30.2** | **PASS** |
| emg-key | P3-04 (poll return, no merge wait) | 0.05 | 1.59 | 2.23 | 2.55 | PASS |
| emg-key | stamps only | 0.05 | 21.6 | 63.6 | 103.7 | over |
| emg-key | stamps only | 0.02 | 21.6 | 36.3 | 50.3 | PASS |
| emg-key | stamps + poll wait bound | 0.05 | 21.3 | 35.8 | 49.1 | PASS |
| emg-key | **stamps + poll wait bound (bench default)** | **0.02** | **21.6** | **22.9** | **23.3** | **PASS** |
| implant-logits | P3-04 | 0.05 | 66.8 | 107.3 | 117.4 | over (not gated) |
| implant-logits | stamps + poll wait bound | 0.02 | 74.5 | 114.8 | 119.3 | over (not gated) |

The same run for the other receivers (no change expected): implant-speech websocket 1.07 / 1.27 / 1.32, file 0.55 / 0.71 / 0.72; emg-key websocket 1.84 / 2.33 / 2.46, file 1.40 / 2.05 / 2.17; implant-logits websocket 59.0 / 97.3 / 100.4, file 64.2 / 96.2 / 100.1 (p50 / p95 / p99 ms).

- B2T '25 replay (P3-08): real T15 data at real time over WebSocket, 120 trials: p95 `added` 2.43 ms, producer level NTS Trust-ready ([results](../experiments/2026-11-17-p3-08-b2t25-collector-replay/results.md)).
- With LSL input, the merge window is now most of the added latency: about `merge_window_s` plus 1 to 2 ms. The guard itself still takes about 1 to 2 ms.
- With the receiver default (0.05 s) the implant-speech p95 is over the budget. Choose `merge_window_s` below the budget. A window shorter than the time skew between the two LSL streams can release events out of order (counted as `late_releases`). An idle events stream with a heartbeat would remove most of the wait: open gap P3-10 (fixed, next section).

### LSL heartbeat and equal times (P3-10)

The merge waited for the window because the events stream is idle between markers. NTS 1.0 RC4 amendment 5 adds two binding rules ([FEP-0002](../spec/feps/0002-nts-over-lsl.md) section 6 rules 7 and 8):

- **LSL-C7 heartbeat.** An empty events-stream sample is a heartbeat. It is not an NTS event, but it tells the consumer that the events stream has passed its timestamp. `NTSOutlet` (used by `replay-to-lsl`, the bench and `fidetype live --publish lsl`) sends one after each frame, with the frame's timestamp. The merge then releases the frame at once.
- **LSL-C8 equal times.** At equal times the merge gives the frame first. `NTSOutlet` now stamps a marker with the timestamp of the frame before it (before: that time plus a small step). So a `segment_end` leaves the merge as soon as its last frame has arrived, not at the next frame.
- `LSLEventSource.poll` waits on the inlet that holds the oldest item back (for a held frame: the events inlet), so the heartbeat ends the wait.

Why the order stays right: a frame at time t is released only when the events inlet has a sample at t or later. Events-stream timestamps do not decrease (LSL-C7, MUST), so no later marker has a time before t; a later marker at exactly t goes after the frame anyway (LSL-C8). A marker at time t is released only when the frames inlet has a frame at t or later. Frame times increase strictly (LSL-C4), so every later frame comes after t. The merge window is not needed for the order; it only limits the wait for a producer that sends no heartbeat.

The bench now runs LSL input at the **receiver default** window (0.05 s; `LSL_MERGE_WINDOW_S = None`). `--no-lsl-heartbeat` gives a producer without heartbeats, for comparison.

`added` latency, LSL input, milliseconds (12 segments per run, same laptop, 2026-11-17; the earlier rows are the P3-07 table above):

| Profile | Run | `merge_window_s` | p50 | p95 | p99 | Budget |
|---|---|---|---|---|---|---|
| implant-speech | P3-07: stamps + poll wait bound | 0.05 | 58.0 | 60.4 | 60.6 | over |
| implant-speech | P3-07: stamps + poll wait bound (old bench default) | 0.02 | 21.2 | 26.8 | 30.2 | PASS |
| implant-speech | P3-10: no heartbeat, marker at frame time | 0.05 | 63.5 | 63.7 | 63.9 | over |
| implant-speech | **P3-10: heartbeat + equal times (receiver and bench default)** | **0.05** | **0.96** | **1.07** | **1.10** | **PASS** |
| emg-key | P3-07: stamps + poll wait bound | 0.05 | 21.3 | 35.8 | 49.1 | PASS |
| emg-key | P3-07: stamps + poll wait bound (old bench default) | 0.02 | 21.6 | 22.9 | 23.3 | PASS |
| emg-key | P3-10: no heartbeat, marker at frame time | 0.05 | 2.34 | 2.77 | 2.96 | PASS |
| emg-key | **P3-10: heartbeat + equal times (receiver and bench default)** | **0.05** | **1.74** | **2.89** | **3.36** | **PASS** |
| implant-logits | P3-07: stamps + poll wait bound | 0.02 | 74.5 | 114.8 | 119.3 | over (not gated) |
| implant-logits | P3-10: heartbeat + equal times | 0.05 | 61.3 | 123.7 | 147.3 | over (not gated) |

- With heartbeats the LSL `added` latency is the same as for WebSocket and file input (the guard, 1 to 2 ms). The merge window no longer counts.
- Without heartbeats implant-speech still waits for the full window (each frame is held). emg-key passes without heartbeats too: a marker stamped with the frame time also moves the events watermark to that frame, so the frames before it leave the merge with it (LSL-C8), and the closing marker does not wait for the next frame.
- implant-logits stays over the budget because of its CTC beam search (P3-06); it gives 13 decisions for 12 segments with and without this change (the same at commit `4350b2d`).
- A producer of another vendor that sends no heartbeat still gets the 0.05 s wait. For it, choose a smaller `merge_window_s` (P3-07 table).

### The CI gate and its tolerance

- The test `test_pipeline_websocket_at_50_hz_within_budget` (both gated profiles, WebSocket input, 8 segments) and the file and LSL tests fail when the p95 `added` latency is not below **50 ms x `FIDETYPE_LATENCY_TOLERANCE`**.
- The default tolerance is **1.0** (the budget itself). CI does not set it. Our local p95 is 1 to 3 ms for WebSocket and file input, so a CI runner that is 10 times slower still passes. For LSL input the p95 is about 1 to 3 ms at the receiver default window (0.05 s), because the producer sends heartbeats (P3-10). The LSL test runs both gated profiles. Set `FIDETYPE_LATENCY_TOLERANCE=2` only on a machine that is known to be slow, and say so in the report.
- The guard imports its parts when it starts, so the first decision has no import cost.
- The CI job `collector` runs the pipeline tests with the `lsl` extra (so the LSL test runs), prints the bench report, and runs the kit against the collector consumer (next section).

## The collector as a consumer: the conformance kit (P7-05, P7-07)

`fidetype-collector consume [--profile P] [--level L] FILE` reads one file or capture through the collector's own input path and checks it with the `validate` processor at stream level `L`. Exit 0 = accept, 1 = reject, 2 = usage error. This is the kit contract of [`nts-conform kit`](conformance.md):

```sh
nts-conform kit --require-level trust-ready --binding nts-lsl/0.1 --binding nts-ws/0.1 \
  --cmd "fidetype-collector consume --profile {profile} --level {level} {path}"
```

| Kit file | Receiver | Checks |
|---|---|---|
| JSON Lines stream or decision log, NPZ (`v0.1`, `fep-0001`, `fep-0003`, `fep-0005`) | `file` | `validate`: header, frames, events, decisions; FEP-0003 and FEP-0005 rules (P7-07) |
| LSL capture, kind `inlet` (`fep-0002`) | `lsl`, on an LSL source that plays the recorded inlets (no network) | the reference LSL consumer (binding rules), then `validate` |
| WebSocket capture, kind `ingest` (`fep-0004`) | `websocket`; the server is not started, the recorded steps go into its ingest core | the reference WebSocket consumer (binding rules, refusals), then `validate` |
| LSL `decisions` and WebSocket `subscribe` captures | the decisions that the reference subscriber reads | the reference consumer, then `validate` (decision rules) |

- The intent (FEP-0003) and control (FEP-0005) rules in `validate` are the rule functions of `fidetype.conformance.profiles` (not a copy). They see the newest 512 profile events of a stream and the newest 512 decisions of a session (bounded memory).
- Loss inside a capture (`gap`, `lost`) does not reject it: the binding defines it, and the collector handles it (no decision on a cut utterance). A file receiver loss (an unreadable line) still rejects a file.

Result (P7-07, 2026-11-17): **36 / 36** kit entries give the expected verdict. Consumer level **NTS Trust-ready** for `text`, `intent` and `control`, with the bindings `nts-lsl/0.1` and `nts-ws/0.1`. `certified.json` lists `fidetype-collector` with these profiles and bindings. Before P7-07 (P7-05): 28 / 36, `text` only, no bindings (the 8 intent, control and capture entries said "not supported").

Full rule list and design notes: [wiki/concepts/collector.md](../wiki/concepts/collector.md).
