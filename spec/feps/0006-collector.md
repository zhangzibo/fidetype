# FEP-0006: The Fidetype collector (receivers, processors, exporters)

| | |
|---|---|
| **FEP** | 0006 |
| **Title** | A vendor-neutral collector service for NTS: receivers → processors → exporters, pipelines, one configuration file, health and metrics, loss and privacy rules |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft |
| **Type** | Process / reference architecture (no change to the stream format) |
| **Affects** | No field of NTS changes. Uses `nts-1.0-rc2.md` sections 4.3–4.4 (segments, `end`, GEN-8), 6 (trust decisions, 6.1 `spec_version`, TD-1 … TD-11, PRV-1 … PRV-3), 8.1 (JSON Lines), 8.2.6 (LSL loss), 8.3 (WebSocket), 10 (security and privacy), 11 (VER-1) |
| **Created** | 2026-11-14 |
| **Discussion** | Roadmap phase P3 "Collector (pipeline)" (`wiki/questions/roadmap-standard.md`); reference v0.1 in `src/fidetype/collector/`; `wiki/concepts/collector.md` |
| **Updated** | 2026-11-14: v0.1 decisions (open questions 1, 3, 4, 5, 6, 7, 8 closed; see "Decisions"). Later on 2026-11-14: questions 2-4 of the second list closed (blank OFFER candidates, open `/healthz`, the automatic gate). Later on 2026-11-14: the `lsl` receiver and the `lsl` decisions exporter (section 2 rule 6, section 4 rule 5) |

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
4. When a pipeline has more than one receiver, the collector MUST make the stream ids unique, so two sources never share a trust session. The reference uses the prefix `<receiver>/<stream id>`, for example `replay/replay-0` and `live/dev-1`. The prefixed id is the `session` of the decisions and the `stream` of the status items. With one receiver, the stream id does not change.
5. The collector MUST NOT feed `trust_decision` events back into an input stream (TD-4).

### 2. Receivers
| Type | Source | Status items it emits | v0.1 |
|---|---|---|---|
| `file` | JSON Lines files (8.1.1), one stream per file, in order. Optional **tail mode** (`follow`) for a file that a decoder is still writing | `gap` (unreadable line), `lost` (tail mode: no new line for `idle_timeout_s`; `eof = "cut"`), `closed` | Yes |
| `websocket` | The `/nts` path of `nts-ws/0.1` (8.3). The binding rules (subprotocol, auth, `ws_seq`, reorder window, resume, take-over) stay in the reference server | `gap` (WS-Q3), `lost` (WS-R2), `replaced`, `closed` | Yes |
| `lsl` | LSL frames and events streams (8.2, FEP-0002), via `fidetype.adapters.lsl` (resolve, clock correction, merge, gap modes, non-blocking reconnect) | `gap` (LSL-G1, mode `abort`, inside an utterance), `lost` (LSL-G2), `closed` (after `end`) | Yes |

Receiver rules:
1. A receiver MUST NOT drop an input event silently. An event that it cannot read becomes a `gap` status at its place.
2. File: empty lines are skipped (GEN-6). Lines after `end` are ignored and counted (GEN-7).
3. File, end of file without `end`: `eof = "close"` (default) closes the stream; the trust layer then closes its last utterance, as `fidetype trust` does (GEN-8 allows a stream without `end`). The receiver MUST log one warning per such stream and count it (`closed_without_end` in the metrics), because a truncated file looks the same. `eof = "cut"` treats the end of file as a loss. In tail mode, an open stream with no new line for `idle_timeout_s` is always a loss.
4. The stream id MUST NOT come from a file name, a host name or a client address (SEC-6, LSL-C3). Reference: `stream_id` from the configuration, the WebSocket `ws.stream_id`, or `<receiver>-<index>`.
5. At shutdown, a receiver reports every open stream as `lost` (no final decision on its open utterance).
6. **LSL** (`lsl`). The receiver wraps the reference LSL source (`LSLEventSource`, `open_source`). It maps the source's control items:
   - a lost inlet → `lost` (the open utterance gets no decision, LSL-G2). The source re-resolves the stream (by `source_id` when the stream has one) on a worker thread until `reconnect_timeout_s`; after a reconnect it sends the header again (a new header resets the stream state). After `reconnect_timeout_s` the receiver is done.
   - a frame gap (LSL-G1, a step > `gap_factor` nominal periods) with `on_gap = "abort"` (**collector default**) → `gap` at its place: the open utterance and the frames up to the next boundary are dropped (section 3.2). A gap right after a boundary (`segment_end`, `end`, `header`: a producer pause between utterances) cuts no utterance; it is only counted (`gaps_between_utterances`). `on_gap = "mark"` counts the gap (`gaps_marked`) and drops the `gap` extension event (a v0.1 consumer ignores it); `"segment"` ends the utterance at the gap (a final decision on the frames before it). *Why `abort` and not the LSL-G1 reference default `mark`:* in the collector, missing frames inside an utterance are lost input (section 5 rule 2).
   - `end` → the event, then `closed`. With `stop_at_end = true` (default) the receiver is then done; else it reads on (a new header starts a new stream, LSL-E5).
   - The stream id is `stream_id` or `<receiver>-0`, never the LSL name or a host name. Metrics hold counters only.

   Settings (all optional except one of the first three):

   | Key | Default | Meaning |
   |---|---|---|
   | `stream_name`, `stream_type`, `source_id` | | The resolve query (at least one; `source_id` is stable across restarts) |
   | `events` | `"auto"` | The events stream: `"auto"` (`events_source_id` of the frames desc), `"none"`, or a stream name |
   | `stream_id` | `<receiver>-0` | The stream id (the `session` of the decisions) |
   | `on_gap`, `gap_factor` | `"abort"`, 2.5 | LSL-G1 |
   | `clock`, `out_of_order`, `merge_window_s` | `"receiver"`, `"clamp"`, 0.05 | LSL-C3, LSL-C4, LSL-C6 |
   | `values`, `vocab`, `vocab_type`, `blank` | `"auto"`, labels, `"other"`, none | A foreign stream (8.2.2, informative) |
   | `boundary_markers`, `plain_markers` | `["segment_end"]`, `"ignore"` | Plain markers (LSL-E3) |
   | `resolve_timeout_s` | 10 | Wait this long for the stream at the start (an I/O error after it, exit code 3) |
   | `open_timeout_s` | 1.0 | The inlet open after a resolve, at the start and on reconnect (M6-16; was 5 s) |
   | `reconnect_mode`, `reconnect_timeout_s` | `"thread"`, 30 | M6-14 non-blocking reconnect; give up after this many seconds |
   | `stop_at_end` | `true` | The receiver is done after `end` |

### 3. Processors
| Type | Input | Output | Purpose | v0.1 |
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
4. **Version stamp.** Every `trust_decision` that the processor emits carries `spec_version: "1.0"` (spec 6.1, VER-1, TD-F3). The key comes directly after `type`.
5. **No blank COMMIT** (TD-9, a MUST NOT for 1.x decisions). The trust configuration MUST NOT be able to COMMIT a blank text. The reference adds the commit gate `min_chars = 1` (M2-18, `FrozenTrustConfig.with_commit_gate`) when the configuration has no gate, or a gate with `min_chars = 0` and `min_words = 0`. A gated decision becomes the no-commit decision (OFFER or ABSTAIN) with a `reason` that starts with `commit gate:`; the metrics count it (`gated_commits`). The gated copy has a new `config_id`; the decisions carry it, and the log shows the old and the new id. A policy that can commit blank text and has no gate (`always_commit`) is a configuration error.
6. **No blank candidates** (TD-12, NTS 1.0 RC2). A gated blank COMMIT becomes the policy's no-commit decision. This can be an OFFER whose only candidate is the blank text. The processor MUST remove blank texts (empty or white space) from `shown` of every text OFFER, ASK and OFFER_WORDS that it emits (provisional and final). When no candidate is left:
   - an OFFER or OFFER_WORDS becomes `ABSTAIN` with `shown = []`;
   - an ASK stays an ASK with `shown = []` (it asks the user to try again; it needs no candidate).

   `reason` gets `TD-12: blank candidates dropped` (and `; no candidate left: ABSTAIN`). The metrics count the dropped texts (`blank_candidates_dropped`) and the changed decisions (`blank_offers_abstained`). *Why ABSTAIN, and not an OFFER without `shown`:* TD-9 says that a decision that shows no text is an `ABSTAIN`. An OFFER without `shown` reads as a privacy log (TD-10), where a text exists but is hidden, so a consumer would think that candidates exist. TD-8 applies to COMMIT only. The change only removes offers, so a fitted risk bound on commits still holds. The provenance ledger (option `ledger`) keeps the trust layer's own decision; the `reason` of the emitted decision names the TD-12 step, so an auditor sees why the action differs.

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
| Type | Target | v0.1 |
|---|---|---|
| `jsonl` | A JSON Lines file. Default `types = ["trust_decision"]`: a decision log (6.4) | Yes |
| `stdout` | JSON Lines on standard output (logs go to standard error) | Yes |
| `websocket` | The `/decisions` channel (8.3.6), with `ws_seq`, replay (WS-D2) and slow-subscriber close (WS-D4). With `receiver`: on that websocket receiver's server. Without `receiver`: a **standalone** server (`listen`, `token_env`, `origins`, `certfile`, `keyfile`, `linger_s`) that serves `/decisions` only | Yes |
| `lsl` | An LSL decisions outlet (LSL-X1 … LSL-X3): `stream_name` (default `fidetype.decisions`), `source_id`, `config_id`, `no_text` | Yes |
| OS input method, Apple BCI HID, AAC, Arrow / Parquet, OTLP metrics | | No (P3-03) |

Exporter rules:
1. An exporter MUST NOT change an item. Status items are never exported. One exception: `no_text = true` of the `lsl` exporter removes `shown` (rule 5).
2. A JSON Lines file holds decisions **or** input events, never both (TD-11). The loader refuses a mixed `types` list.
3. An exporter that acts (an OS input method, a HID bridge) MUST forward only final `COMMIT` decisions, or a user selection after `OFFER` (TD-1, TD-3), and MUST NOT forward a blank committed text (TD-9). No v0.1 exporter acts.
4. A standalone `/decisions` server (a `websocket` exporter without `receiver`) refuses `/nts` and `/events` (HTTP 404): it accepts no input. It uses the same subscriber rules as the receiver's server (subprotocol, token, origins, `from_seq` replay from a ring of 4096 decisions, slow-subscriber close). `linger_s` (default 0) keeps it open for that many seconds after every receiver is done, so a demo subscriber can connect late and read from `from_seq = 1`. Beyond `localhost` the reference logs a warning without TLS and without a token.
5. **LSL decisions outlet** (`lsl`). Type `Markers`, 1 string channel, irregular rate, desc keys `role = trust_decisions`, `event_type = trust_decision`, `spec = FEP-0001`, `binding = nts-lsl/0.1` and `config_id` (the option, else the `config_id` of the pipeline's trust processor) (LSL-X1). One sample is one `trust_decision` as JSON; its timestamp is the emission time (LSL-X2). Only `trust_decision` events go out. LSL has no access control: every host on the network can read the outlet. `no_text = true` removes `shown` and adds `redaction = {"mode": "drop"}` (SEC-7; the same as `redact` with `mode = "drop"`); without it the reference logs a warning at start. The exporter writes no host name (LSL-C3; liblsl itself announces the outlet's host in its stream info). At stop, it waits 0.5 s while a subscriber is connected, so the last decisions reach it.

### 5. Back-pressure and loss
1. **No silent drop of input.** The collector MUST NOT drop an input event to keep up (WS-A3). The only input that is lost is input that the transport lost; it becomes a `gap` or `lost` status.
2. **Never a final decision on a cut segment** (GEN-8, LSL-G2, WS-Q5). Every path that loses input (transport gap, resume time-out, unreadable line, invalid event, tail-mode idle time-out, shutdown inside an utterance) ends in a `gap` or `lost` status, and the trust processor drops the open utterance without a decision.
3. **Reading follows processing.** The reference loop reads the next input only after the last items reached the exporters. A file receiver reads at most `batch` lines per step. The WebSocket server stops reading a producer when its queue is full (`queue_max`), so TCP flow control pushes back on the producer (WS-A2, WS-A3).
4. **Slow outputs do not block.** A WebSocket subscriber has a bounded queue; when it is full, the subscriber is closed with 1013 and resubscribes with `from_seq` (WS-D4). File and standard output exporters write synchronously; a slow disk slows the reading (rule 3), it does not drop.
5. **Bounded state.** The trust layer bounds frames per utterance and sessions (`max_frames`, `max_sessions`). `validate` and `thin` bound their per-session memory.

### 6. Configuration
1. One file, in **TOML** (`tomllib`, standard library) or **JSON**. **YAML is not supported** (decision, v0.1): a YAML reader is a new dependency (PyYAML), and TOML and JSON hold the same structure one to one. A `.yaml` or `.yml` file gives a configuration error that says this.
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
1. Optional table `service.health`. `listen` defaults to `127.0.0.1:13133` (localhost only). `GET /healthz` gives `{"status": "ok"}` (HTTP 200) while the collector runs, else its state (HTTP 503). `GET /metrics` gives the counters of every component as JSON.
2. Optional bearer token: `token_env` names the environment variable that holds it. Then `/metrics` needs `Authorization: Bearer <token>`; else HTTP 401. `/healthz` stays open (no token), so a liveness probe without a header works. `/healthz` MUST show only the status (`{"status": ...}`): no counter, no component name, no address. The token follows the secret rules of the WebSocket receiver: never in the file, never in a log line or a metric.
3. A `listen` address beyond `localhost` without `token_env` is a configuration error, unless the file sets `allow_unauthenticated = true`. Then the collector logs a warning at start (`/metrics` is open).
4. `service.metrics_file` writes the same counters when the collector stops.
5. Counters include: items, streams, ended, cut and lost streams, streams closed without `end`, unreadable lines, invalid headers / events / decisions, decisions, final decisions, gated commits, dropped blank candidates, OFFERs changed to ABSTAIN, aborted utterances, frames skipped after a gap, redacted decisions, dropped provisional decisions, exported items, subscribers.
6. The health server MUST NOT log client addresses. Metrics MUST NOT contain a host name, a client address, a token, a key or decoded text.

### 8. Security and privacy
1. Decoded text is personal data (SEC-7). The collector offers `redact` (drop or keyed hash). A deployment on a shared network SHOULD redact before every exporter that leaves the machine.
2. No host name, client address or token in any decision, exported event, metric or log line written by the collector (LSL-C3, WS-T3, 10.5). The operator's startup log line MAY show the bind address that the operator configured.
3. Off `localhost`, the WebSocket receiver SHOULD use TLS (`certfile`, `keyfile`; WS-T4). The reference logs a warning when it listens beyond `localhost` without TLS.
4. The health endpoint listens on `localhost` by default. Off `localhost`, `/metrics` needs a bearer token (`token_env`) or an explicit `allow_unauthenticated = true` (section 7). `/healthz` is always open and shows only the status.
5. Raw neural samples never enter the collector (SEC-1): it reads NTS only.

### 9. Command line
```
fidetype collector --config collector.toml [--check] [--duration S] [--max-streams N]
python -m fidetype.collector --config collector.toml
```
Exit code 0: normal stop. 2: configuration error (the message names the bad value). 3: an I/O error (for example the port is in use).

### 10. Out of scope for v0.1 (future work)
- gRPC / OTLP receivers and exporters; Arrow / Parquet files; OTLP export of the latency metrics.
- OS input-method exporters (Windows TSF, Android IME, macOS, IBus), the Apple BCI HID bridge, the AAC API (P3-03).
- Per-user calibration, LM rescoring, a segmenter, a rate limiter as processors (P3-02, P5).
- **Fan-out of one receiver to two pipelines** (OpenTelemetry allows it). Not now (decision, v0.1): it needs a copy of each item per pipeline and a rule for back-pressure when one pipeline is slower. Today a receiver belongs to one pipeline; an exporter can serve several.
- Hot reload, several worker processes, a `contrib` folder for third-party components, a plug-in registry. (YAML: not planned, section 6.)
- The intent and control profiles in the trust processor (the layers exist: `fidetype intent`, `fidetype control`).
- The latency budget test (< 50 ms added, P3-04).

## Examples
Input: `spec/conformance/fep-0001/f01-segments.jsonl` (two utterances, `segment_end` between them, `end`). Pipeline: `file` → `validate` → `trust` (`decoder = "greedy"`) → `redact` (`mode = "drop"`) → `jsonl`. Output decision log (two lines, abbreviated):
```json
{"type": "trust_decision", "spec_version": "1.0", "session": "replay-0", "seq": 0, "utterance": 0, "is_final": true, "action": "COMMIT", "p_top1": 1.0, "score_semantics": "calibrated_prob", "config_id": "tcfg-09fdaf9f0f9dd28c", "input": {"kind": "frames", "frame_range": [0, 2], "t_range": [0.0, 0.04], "stream_sha256": "604e…"}, "redaction": {"mode": "drop"}}
{"type": "trust_decision", "spec_version": "1.0", "session": "replay-0", "seq": 1, "utterance": 1, "is_final": true, "action": "COMMIT", "p_top1": 1.0, "score_semantics": "calibrated_prob", "config_id": "tcfg-09fdaf9f0f9dd28c", "input": {"kind": "frames", "frame_range": [0, 2], "t_range": [1.0, 1.04], "stream_sha256": "0ed9…"}, "redaction": {"mode": "drop"}}
```
(The example trust configuration is a toy, not calibrated; it only shows the wiring. It has no commit gate, so the collector adds `min_chars = 1`: the `config_id` is that of the gated copy.) If a line inside utterance 1 is unreadable, the receiver emits a `gap`, and the log has only the decision of utterance 0.

## Compatibility
- No change to NTS, to the bindings or to the conformance profiles. Existing tools (`fidetype trust`, `fidetype ws run`, `fidetype lsl run`) do not change.
- A decision from the collector equals the decision of `fidetype trust` on the same file and the same (blank-safe) trust configuration (the reference tests check this), except for `spec_version`, `redaction` / `shown_hmac` when `redact` runs, and the TD-12 step (section 3.2 rule 6) when `shown` has a blank candidate. With a configuration that has no commit gate, the collector adds the gate (section 3.2), so a blank COMMIT of `fidetype trust` becomes an OFFER or ABSTAIN, and the `config_id` differs.
- The collector's decisions carry `spec_version: "1.0"`. They pass the FEP-0001 profile in the Python, TypeScript and Rust reference consumers (checked 2026-11-14 on the example log and on a log with a gated blank COMMIT).

## Reference implementation
`src/fidetype/collector/` (Apache-2.0, our own code, standard library + numpy; `websockets` only for the WebSocket components, as in `fidetype[ws]`):
- `config.py`: loader and checks (`ConfigError` names the bad value).
- `receivers.py`: `FileReceiver`, `WebSocketReceiver` (wraps `fidetype.adapters.ws.WSServer`), `LSLReceiver` (wraps `fidetype.adapters.lsl.LSLEventSource`).
- `processors.py`: `ValidateProcessor` (wraps `fidetype.conformance` checks and the reference frame reader), `TrustProcessor` (wraps `StreamingTrustLayer` and the loss rules of `WSTrustRunner`), `RedactProcessor`, `ThinProcessor`.
- `exporters.py`: `JsonlExporter`, `StdoutExporter`, `WebSocketExporter` (the receiver's `OutputHub`), `StandaloneWebSocketExporter` (its own `WSServer`, `/decisions` only), `LSLExporter` (wraps `fidetype.adapters.lsl.DecisionOutlet`).
- `service.py`: `Collector` (build, run loop, stop, metrics, health endpoint).
- Tests: `tests/test_collector.py` (file → trust → jsonl equals the reference replay; redaction removes all text; an unreadable line, an invalid frame, a WebSocket gap, `eof = "cut"` and a stop in tail mode give no final decision on the cut utterance; configuration errors; command line; WebSocket in and `/decisions` out; v0.1: the `eof = "close"` warning and counter, the `<receiver>/<id>` prefix, health defaults and bearer token (open `/healthz`, protected `/metrics`), `spec_version` and the FEP-0001 profile, the gated blank COMMIT and the TD-12 step (`drop_blank_candidates`), file → trust → standalone `/decisions`). `tests/test_collector_lsl.py`: scripted LSL inlets (a loss mid-utterance gives no final decision, the reconnect goes on; `abort` and `mark` gaps; a gap between utterances cuts nothing; shutdown and give-up; `stop_at_end = false`), the exporter (decisions only, `no_text`), configuration errors, `config_id` from the trust processor, and a real LSL loopback (outlet → collector → decisions outlet → inlet; same decisions as the file receiver; desc keys; no host name; skips without pylsl).

## Alternatives
- **Use the OpenTelemetry Collector itself** (Go) with an NTS receiver. Rejected for v0: the trust layer is Python; OTel pipelines carry traces, metrics and logs, not ordered per-utterance state with loss rules. An OTLP exporter for collector metrics stays possible (section 10).
- **One program per pair** (today's state). Rejected: every new source or target multiplies the tools, and the loss and privacy rules repeat.
- **Rust for v1** (the roadmap leaves Rust or Python open). v0 is Python to reuse the trust layer and the adapters; the configuration and the item model are language-neutral, so a Rust collector can read the same files (open question 1).
- **YAML configuration** (the OpenTelemetry habit). Rejected for v0.1: it needs a new dependency, and TOML / JSON hold the same structure.
- **A configuration map for stream ids** across receivers. Rejected for v0.1: the fixed prefix `<receiver>/<id>` is simple, unique and needs no configuration.

## Privacy and leakage
The collector carries decoded text and behavioural data (10.1). The rules in sections 3.3 and 8 apply. It never reads ground truth (SEC-8). The provenance ledger stores hashes by default (PRV-2).

## Decisions (v0.1, 2026-11-14)
The maintainers closed these open questions of the first draft:

| # | Question | Decision |
|---|---|---|
| 1 | YAML? | No. TOML and JSON only (no new dependency). Section 6 |
| 3 | Stream ids across receivers | Keep the prefix `<receiver>/<stream id>`. Section 1 rule 4 |
| 4 | Health endpoint security | `localhost` by default; optional bearer token (`token_env`); a bind beyond `localhost` needs a token or `allow_unauthenticated = true` (warning). Section 7 |
| 5 | `spec_version` on decisions | Yes: `"1.0"` on every decision; the commit gate makes TD-9 hold. Section 3.2 |
| 6 | Fan-out of one receiver to two pipelines | Not now; future work. Section 10 |
| 7 | Default for a file without `end` | Keep `close`; one warning per stream and the counter `closed_without_end`. Section 2 rule 3 |
| 8 | Standalone `/decisions` server | Yes: a `websocket` exporter without `receiver`. Section 4 rule 4 |

Second round (2026-11-14). The maintainers closed questions 2-4 of the list below:

| # | Question | Decision |
|---|---|---|
| 2 | Blank OFFER candidates | New spec rule TD-12 (NTS 1.0 RC2, 6.3): a 1.x trust layer SHOULD NOT list a blank candidate; a consumer MUST NOT offer one. The collector removes blank candidates and turns an OFFER with none left into `ABSTAIN` with `shown = []`. Section 3.2 rule 6 |
| 3 | Health token scope | `/healthz` stays open (liveness probes) and shows only the status. The token protects `/metrics` only. A bind beyond `localhost` without a token is still a configuration error, unless `allow_unauthenticated = true`. Section 7 |
| 4 | Stamped version and the commit gate | No change: the collector keeps adding the gate (`min_chars = 1`) to a configuration without one, with a log line that shows the old and the new `config_id`. A refusal would break every existing ungated configuration and add no safety. The log line and the new `config_id` in each decision make the change visible. Section 3.2 rule 5 |

## Open questions
1. **Language of v1.** Stay in Python, or write v1 in Rust as a long-running local service (roadmap P3)? This decides where the OS input-method exporters live. (The user decides.)
2. ~~**Blank OFFER.**~~ Closed (2026-11-14): TD-12; see "Decisions", second round.
3. ~~**Health token scope.**~~ Closed (2026-11-14): open `/healthz`, protected `/metrics`; see "Decisions", second round.
4. ~~**Stamped version and the commit gate.**~~ Closed (2026-11-14): keep the automatic gate; see "Decisions", second round.
