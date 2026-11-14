# FEP-0006: The Fidetype collector (receivers, processors, exporters)

| | |
|---|---|
| **FEP** | 0006 |
| **Title** | A vendor-neutral collector service for NTS: receivers → processors → exporters, pipelines, one configuration file, health and metrics, loss and privacy rules |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft |
| **Type** | Process / reference architecture (no change to the stream format) |
| **Affects** | No field of NTS changes. Uses `nts-1.0-rc1.md` sections 4.3–4.4 (segments, `end`, GEN-8), 6 (trust decisions, TD-1 … TD-11, PRV-1 … PRV-3), 8.1 (JSON Lines), 8.2.6 (LSL loss), 8.3 (WebSocket), 10 (security and privacy) |
| **Created** | 2026-11-14 |
| **Discussion** | Roadmap phase P3 "Collector (pipeline)" (`wiki/questions/roadmap-standard.md`); reference v0 in `src/fidetype/collector/`; `wiki/concepts/collector.md` |

## Summary
Today each Fidetype tool is its own program: `fidetype trust` reads files, `fidetype ws run` serves WebSocket, `fidetype lsl run` reads LSL. Each one wires one input to the trust layer and one output. This FEP defines **one service, the collector**, that does this wiring from a configuration file:

1. **Receivers** take NTS from a source (files, WebSocket, LSL) and give events in order, one stream at a time.
2. **Processors** change or replace the events: validate, trust layer, redact text, thin provisional decisions, provenance.
3. **Exporters** send the result to a target (decision log file, standard output, WebSocket `/decisions`, LSL decisions outlet).
4. **Pipelines** connect named receivers, processors and exporters.
5. A **health and metrics** endpoint shows the state of each component.

The model follows the idea of the OpenTelemetry Collector (receivers, processors, exporters, pipelines, one configuration). The text and the design here are our own. The collector is a **reference architecture**, not a new wire format: a conforming producer or consumer does not need it.

## Motivation
- The roadmap goal is "OpenTelemetry for neural input". In OpenTelemetry, the collector is the part that lets operators combine sources and targets without code. NTS needs the same part.
- The P3 exit criterion is one configuration that runs "replay → trust processor → file exporter and WebSocket exporter". Today this needs code.
- The loss rules (no final decision on a cut segment, GEN-8, LSL-G2, WS-Q5) and the privacy rules (SEC-7, no host names, no tokens) are implemented per tool. One service applies them once, for every source.
- A deployment needs to change the target (a file today, an AAC app tomorrow, an OS input method later) without changing the decoder or the trust layer.

## Terms
- **Item**: one unit that moves through a pipeline: a pair (stream id, event). The event is an NTS event, a `trust_decision`, or an internal **status item**.
- **Status item**: an internal item of type `ws_status` with a `status`: `gap` (events are missing inside the stream), `lost` (the stream stopped inside an utterance), `replaced`, `closed` (the stream is complete). Status items never leave the collector.
- **Cut utterance**: an utterance whose input is incomplete because of a gap, a loss, an unreadable line or an invalid event.
- **Stream id**: the id of one input stream inside the collector. It is the `session` of the decisions of that stream.

## Proposal

### 1. Architecture
```
            +-------------------------- pipeline "main" ---------------------------+
 file  ---> | receiver  -->  validate --> trust --> thin --> redact  --> exporter  | --> decisions.jsonl
 ws /nts -> | receiver  -/                                              \ exporter | --> ws /decisions
            +----------------------------------------------------------------------+
                          health and metrics: GET /healthz, GET /metrics
```
Rules:
1. A pipeline has at least one receiver and one exporter, and zero or more processors in a fixed order.
2. A receiver and a processor keep state. Each belongs to **one** pipeline. An exporter MAY serve several pipelines.
3. Items move in order. Within one stream, a processor MUST NOT reorder items.
4. When a pipeline has more than one receiver, the collector MUST make the stream ids unique (reference: `<receiver>/<stream id>`), so two sources never share a trust session.
5. The collector MUST NOT feed `trust_decision` events back into an input stream (TD-4).

### 2. Receivers
| Type | Source | Status items it emits | v0 |
|---|---|---|---|
| `file` | JSON Lines files (8.1.1), one stream per file, in order. Optional **tail mode** (`follow`) for a file that a decoder is still writing | `gap` (unreadable line), `lost` (tail mode: no new line for `idle_timeout_s`; `eof = "cut"`), `closed` | Yes |
| `websocket` | The `/nts` path of `nts-ws/0.1` (8.3). The binding rules (subprotocol, auth, `ws_seq`, reorder window, resume, take-over) stay in the reference server | `gap` (WS-Q3), `lost` (WS-R2), `replaced`, `closed` | Yes |
| `lsl` | LSL frames and events streams (8.2), via `fidetype.adapters.lsl` | `gap` (LSL-G1, mode `segment` or `abort`), `lost` (LSL-G2), `closed` | No (section 10) |

Receiver rules:
1. A receiver MUST NOT drop an input event silently. An event that it cannot read becomes a `gap` status at its place.
2. File: empty lines are skipped (GEN-6). Lines after `end` are ignored and counted (GEN-7).
3. File, end of file without `end`: `eof = "close"` (default) closes the stream; the trust layer then closes its last utterance, as `fidetype trust` does (GEN-8 allows a stream without `end`). `eof = "cut"` treats the end of file as a loss. In tail mode, an open stream with no new line for `idle_timeout_s` is always a loss.
4. The stream id MUST NOT come from a file name, a host name or a client address (SEC-6, LSL-C3). Reference: `stream_id` from the configuration, the WebSocket `ws.stream_id`, or `<receiver>-<index>`.
5. At shutdown, a receiver reports every open stream as `lost` (no final decision on its open utterance).

### 3. Processors
| Type | Input | Output | Purpose | v0 |
|---|---|---|---|---|
| `validate` | any | same items, or a `gap` in place of an invalid input event | Conformance checks per event | Yes |
| `trust` | NTS events, status items | `trust_decision` events only | The streaming trust layer, one session per stream; optional provenance ledger | Yes |
| `redact` | any | same items without decoded text | Privacy (SEC-7, TD-10, PRV-2) | Yes |
| `thin` | any | same items, fewer provisional decisions | Bandwidth; never drops a final decision | Yes |
| `provenance` | decisions | decisions + ledger entries | PRV-1 record per final decision | As the `ledger` option of `trust` |
| `calibrate`, `lm_rescore`, `segment`, `rate_limit` | | | P3-02 / P5 | No |

#### 3.1 `validate`
1. Header: the core MUST checks of the conformance suite (`fidetype.conformance`), on a header-only stream.
2. Frames: FRM-1 … FRM-4 with the reference frame reader, and strictly increasing `t` (WS-K2).
3. `segment_end` (SEG-4, SEG-5), `hypothesis` (HYP-1), `signal_quality` (SQ-1).
4. `trust_decision`: the FEP-0001 profile format checks (TD-F1 … TD-F3, TD-8, TD-9 for 1.x), and per session TD-5 (`seq` increases) and TD-6 / TD-7 (one final decision per utterance, nothing after it).
5. `on_invalid = "cut"` (default): an invalid input event becomes a `gap` status; an invalid header drops the stream until the next valid header (status `lost` if a stream was open); an invalid decision is dropped. `on_invalid = "log"` passes the item on and only counts it (debugging only).

#### 3.2 `trust`
1. It wraps `StreamingTrustLayer` and the loss rules of the reference WebSocket runner. It MUST apply GEN-8, LSL-G2 and WS-Q5 to every receiver:
   - `gap`: drop the open utterance **without** a decision, then drop the `frame` events up to the next `segment_end`, `end` or `header`;
   - `lost` or `replaced`: drop the open utterance without a decision;
   - `closed`: close the stream (its last complete utterance MAY get its final decision).
2. A stream from a WebSocket receiver keeps the `ws` record of the reference server (WS-K4). A stream from another receiver gets no transport record.
3. Option `ledger`: a hash-chained provenance ledger (`fidetype.trust.provenance`, PRV-1 … PRV-3) with `text_mode` `hash` (default), `omit` or `store`.

#### 3.3 `redact`
1. It removes `shown` from each `trust_decision`. `mode = "hmac"` writes `shown_hmac` (HMAC-SHA256 hex of each text) instead, with a key from an environment variable; an auditor with the key can check a text, the log does not hold it.
2. Each changed decision gets `redaction` (`mode`, optional `key_id`). The key itself MUST NOT appear in any output.
3. With `hypothesis_text = true` (default), the `text` of each n-best item of a `hypothesis` event is treated the same way (for pipelines that export input events).
4. `redact` MUST come after `trust` in a pipeline (the trust layer needs the text). The configuration loader refuses the other order.

#### 3.4 `thin` (sampling that keeps state changes)
1. It MUST NOT drop a final decision, an input event or a status item.
2. `keep_provisional = "changes"` (default): keep a provisional decision only when its `action` or its shown texts differ from the last kept provisional decision of the same utterance. `"none"`: drop all provisional decisions (consumers MUST NOT act on them anyway, TD-1). `"all"`: keep all.
3. Dropped provisional decisions leave holes in `seq`. `seq` still increases strictly (TD-5).

### 4. Exporters
| Type | Target | v0 |
|---|---|---|
| `jsonl` | A JSON Lines file. Default `types = ["trust_decision"]`: a decision log (6.4) | Yes |
| `stdout` | JSON Lines on standard output (logs go to standard error) | Yes |
| `websocket` | The `/decisions` channel (8.3.6) of a websocket receiver's server, with `ws_seq`, replay (WS-D2) and slow-subscriber close (WS-D4) | Yes (shares the receiver's server) |
| `lsl` | An LSL decisions outlet (LSL-X1 … LSL-X3) | No |
| OS input method, Apple BCI HID, AAC, Arrow / Parquet, OTLP metrics | | No (P3-03) |

Exporter rules:
1. An exporter MUST NOT change an item. Status items are never exported.
2. A JSON Lines file holds decisions **or** input events, never both (TD-11). The loader refuses a mixed `types` list.
3. An exporter that acts (an OS input method, a HID bridge) MUST forward only final `COMMIT` decisions, or a user selection after `OFFER` (TD-1, TD-3), and MUST NOT forward a blank committed text (TD-9). No v0 exporter acts.

### 5. Back-pressure and loss
1. **No silent drop of input.** The collector MUST NOT drop an input event to keep up (WS-A3). The only input that is lost is input that the transport lost; it becomes a `gap` or `lost` status.
2. **Never a final decision on a cut segment** (GEN-8, LSL-G2, WS-Q5). Every path that loses input (transport gap, resume time-out, unreadable line, invalid event, tail-mode idle time-out, shutdown inside an utterance) ends in a `gap` or `lost` status, and the trust processor drops the open utterance without a decision.
3. **Reading follows processing.** The reference loop reads the next input only after the last items reached the exporters. A file receiver reads at most `batch` lines per step. The WebSocket server stops reading a producer when its queue is full (`queue_max`), so TCP flow control pushes back on the producer (WS-A2, WS-A3).
4. **Slow outputs do not block.** A WebSocket subscriber has a bounded queue; when it is full, the subscriber is closed with 1013 and resubscribes with `from_seq` (WS-D4). File and standard output exporters write synchronously; a slow disk slows the reading (rule 3), it does not drop.
5. **Bounded state.** The trust layer bounds frames per utterance and sessions (`max_frames`, `max_sessions`). `validate` and `thin` bound their per-session memory.

### 6. Configuration
1. One file. The reference v0 reads **TOML** (`tomllib`, standard library) or **JSON**. YAML (the OpenTelemetry habit) is the same structure; v0 does not read it because PyYAML is not a dependency (open question 1).
2. Top-level tables: `service`, `receivers`, `processors`, `exporters`, `pipelines`. Each component has a name (the table key) and a `type`.
3. Relative paths resolve against the folder of the configuration file.
4. **Secrets are never in the file.** A key named `token`, `key`, `password` or `secret` is an error. A component names an environment variable (`token_env`, `key_env`).
5. The loader MUST refuse, with a message that names the bad value: unknown keys, unknown types, unknown component names in a pipeline, a receiver or processor in two pipelines, an unused receiver or processor, `redact` before `trust`, `validate` after `trust`, two `trust` processors in one pipeline, a mixed `jsonl` `types` list, a `websocket` exporter whose receiver is not in the pipeline.
6. `fidetype collector --config <file> --check` checks the file and prints the pipelines.

Example (TOML; the full example is `examples/collector/collector.toml`):
```toml
[receivers.replay]
type = "file"
paths = ["streams/session-01.jsonl"]

[receivers.live]
type = "websocket"
listen = "127.0.0.1:8765"
token_env = "FIDETYPE_WS_TOKEN"

[processors.check]
type = "validate"

[processors.trust]
type = "trust"
config = "trust.json"
decoder = "greedy"

[processors.privacy]
type = "redact"
mode = "hmac"
key_env = "FIDETYPE_REDACT_KEY"

[exporters.log]
type = "jsonl"
path = "out/decisions.jsonl"

[exporters.live_decisions]
type = "websocket"
receiver = "live"

[pipelines.main]
receivers = ["replay", "live"]
processors = ["check", "trust", "privacy"]
exporters = ["log", "live_decisions"]
```

### 7. Health and metrics
1. Optional `service.health.listen` (reference: `127.0.0.1:13133`). `GET /healthz` gives `{"status": "ok"}` (HTTP 200) while the collector runs, else its state (HTTP 503). `GET /metrics` gives the counters of every component as JSON.
2. `service.metrics_file` writes the same counters when the collector stops.
3. Counters include: items, streams, ended, cut and lost streams, unreadable lines, invalid headers / events / decisions, decisions, final decisions, aborted utterances, frames skipped after a gap, redacted decisions, dropped provisional decisions, exported items, subscribers.
4. The health server MUST NOT log client addresses. Metrics MUST NOT contain a host name, a client address, a token, a key or decoded text.

### 8. Security and privacy
1. Decoded text is personal data (SEC-7). The collector offers `redact` (drop or keyed hash). A deployment on a shared network SHOULD redact before every exporter that leaves the machine.
2. No host name, client address or token in any decision, exported event, metric or log line written by the collector (LSL-C3, WS-T3, 10.5). The operator's startup log line MAY show the bind address that the operator configured.
3. Off `localhost`, the WebSocket receiver SHOULD use TLS (`certfile`, `keyfile`; WS-T4). The reference logs a warning when it listens beyond `localhost` without TLS.
4. The health endpoint has no authentication in v0. It SHOULD listen on `localhost` only.
5. Raw neural samples never enter the collector (SEC-1): it reads NTS only.

### 9. Command line
```
fidetype collector --config collector.toml [--check] [--duration S] [--max-streams N]
python -m fidetype.collector --config collector.toml
```
Exit code 0: normal stop. 2: configuration error (the message names the bad value). 3: an I/O error (for example the port is in use).

### 10. Out of scope for v0
- LSL receiver and LSL decisions exporter (the adapter exists; the wrapper is the next step).
- gRPC / OTLP receivers and exporters; Arrow / Parquet files; OTLP export of the latency metrics.
- OS input-method exporters (Windows TSF, Android IME, macOS, IBus), the Apple BCI HID bridge, the AAC API (P3-03).
- Per-user calibration, LM rescoring, a segmenter, a rate limiter as processors (P3-02, P5).
- YAML configuration, hot reload, several worker processes, a `contrib` folder for third-party components, a plug-in registry.
- The intent and control profiles in the trust processor (the layers exist: `fidetype intent`, `fidetype control`).
- The latency budget test (< 50 ms added, P3-04).
- A standalone `/decisions` server without a websocket receiver.

## Examples
Input: `spec/conformance/fep-0001/f01-segments.jsonl` (two utterances, `segment_end` between them, `end`). Pipeline: `file` → `validate` → `trust` (`decoder = "greedy"`) → `redact` (`mode = "drop"`) → `jsonl`. Output decision log (two lines, abbreviated):
```json
{"type": "trust_decision", "session": "replay-0", "seq": 0, "utterance": 0, "is_final": true, "action": "COMMIT", "p_top1": 1.0, "score_semantics": "calibrated_prob", "config_id": "tcfg-d598b2747d186085", "input": {"kind": "frames", "frame_range": [0, 2], "t_range": [0.0, 0.04], "stream_sha256": "604e…"}, "redaction": {"mode": "drop"}}
{"type": "trust_decision", "session": "replay-0", "seq": 1, "utterance": 1, "is_final": true, "action": "COMMIT", "p_top1": 1.0, "score_semantics": "calibrated_prob", "config_id": "tcfg-d598b2747d186085", "input": {"kind": "frames", "frame_range": [0, 2], "t_range": [1.0, 1.04], "stream_sha256": "0ed9…"}, "redaction": {"mode": "drop"}}
```
(The example trust configuration is a toy, not calibrated; it only shows the wiring.) If a line inside utterance 1 is unreadable, the receiver emits a `gap`, and the log has only the decision of utterance 0.

## Compatibility
- No change to NTS, to the bindings or to the conformance profiles. Existing tools (`fidetype trust`, `fidetype ws run`, `fidetype lsl run`) do not change.
- A decision from the collector equals the decision of `fidetype trust` on the same file and the same trust configuration (the reference tests check this), except for `redaction` / `shown_hmac` when `redact` runs.
- The collector's decisions carry no `spec_version` yet: they follow the 0.1 rules, as the trust layer does today (open question 5).

## Reference implementation
`src/fidetype/collector/` (Apache-2.0, our own code, standard library + numpy; `websockets` only for the WebSocket components, as in `fidetype[ws]`):
- `config.py`: loader and checks (`ConfigError` names the bad value).
- `receivers.py`: `FileReceiver`, `WebSocketReceiver` (wraps `fidetype.adapters.ws.WSServer`).
- `processors.py`: `ValidateProcessor` (wraps `fidetype.conformance` checks and the reference frame reader), `TrustProcessor` (wraps `StreamingTrustLayer` and the loss rules of `WSTrustRunner`), `RedactProcessor`, `ThinProcessor`.
- `exporters.py`: `JsonlExporter`, `StdoutExporter`, `WebSocketExporter` (the receiver's `OutputHub`).
- `service.py`: `Collector` (build, run loop, stop, metrics, health endpoint).
- Tests: `tests/test_collector.py` (file → trust → jsonl equals the reference replay; redaction removes all text; an unreadable line, an invalid frame, a WebSocket gap, `eof = "cut"` and a stop in tail mode give no final decision on the cut utterance; configuration errors; command line; WebSocket in and `/decisions` out).

## Alternatives
- **Use the OpenTelemetry Collector itself** (Go) with an NTS receiver. Rejected for v0: the trust layer is Python; OTel pipelines carry traces, metrics and logs, not ordered per-utterance state with loss rules. An OTLP exporter for collector metrics stays possible (section 10).
- **One program per pair** (today's state). Rejected: every new source or target multiplies the tools, and the loss and privacy rules repeat.
- **Rust for v1** (the roadmap leaves Rust or Python open). v0 is Python to reuse the trust layer and the adapters; the configuration and the item model are language-neutral, so a Rust collector can read the same files (open question 2).
- **YAML configuration.** Kept as the long-term form; v0 uses TOML to avoid a new dependency.

## Privacy and leakage
The collector carries decoded text and behavioural data (10.1). The rules in sections 3.3 and 8 apply. It never reads ground truth (SEC-8). The provenance ledger stores hashes by default (PRV-2).

## Open questions
1. **YAML.** Add PyYAML as an optional extra (`fidetype[collector]`), or keep TOML / JSON only?
2. **Language of v1.** Stay in Python, or write v1 in Rust as a long-running local service (roadmap P3)? This decides where the OS input-method exporters live.
3. **Stream ids across receivers.** Is the prefix `<receiver>/<id>` right, or should the configuration map ids?
4. **Health endpoint security.** Add a token, or keep it on `localhost` only?
5. **`spec_version` on decisions.** Should the collector stamp `spec_version: "1.0"` once the trust layer meets the 1.x rules (TD-9 MUST NOT is already met by the commit gate)?
6. **Fan-out of one receiver to two pipelines** (OpenTelemetry allows it). Needed? It needs a copy of each item per pipeline.
7. **Default for a file without `end`.** `close` (today, as `fidetype trust`) or `cut` (stricter)?
8. **Standalone `/decisions` server** without a WebSocket receiver, for file replay demos.
