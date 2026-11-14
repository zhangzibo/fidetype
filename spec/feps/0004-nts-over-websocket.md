# FEP-0004: NeuralTextStream over WebSocket

| | |
|---|---|
| **FEP** | 0004 |
| **Title** | Normative binding of NeuralTextStream to WebSocket (RFC 6455) |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft |
| **Type** | Spec change (binding, Development) |
| **Affects** | `neuraltextstream-v0.1.md` section 6.3 (replaces the sketch); uses FEP-0001 (`segment_end`, `trust_decision`); clock rules follow FEP-0002 |
| **Created** | 2026-11-13 |
| **Discussion** | M6-11 (WebSocket adapter); `src/fidetype/adapters/ws.py`, `wiki/concepts/websocket-input.md` |

## Summary
Spec 6.3 sketches NTS over WebSocket in one sentence: "one JSON object per text message, the header first". This FEP makes it a full binding for both directions. **Input** (path `/nts`): a decoder sends NTS events to a trust service. **Output** (paths `/decisions` and `/events`): the service sends `trust_decision` events and NTS events to consumers such as browsers. The FEP defines the subprotocol and the binding version (`nts-ws/0.1`), the framing (single events and batches), the handshake, sequence numbers and gap detection, back-pressure, reconnect and resume, an auth hook, TLS, and the clock rules. The opt-in conformance profile `fep-0004` tests it with scripted connections (no network, no WebSocket library).

## Motivation
- A browser cannot open an LSL stream. WebSocket is the only bidirectional transport that every browser has. A web keyboard, a caregiver dashboard or a remote demo needs NTS and trust decisions over WebSocket.
- The 6.3 sketch has no sequence numbers. TCP does not lose or reorder data inside one connection, but connections break (Wi-Fi, laptop sleep, proxies). Without numbers, a consumer cannot tell a clean stream from a stream with lost events after a reconnect. A decision on an utterance with lost frames could commit a cut text.
- Without written rules, every vendor bridge would choose its own framing, auth and resume behaviour. Test vectors make two implementations interoperate.

## Terms
- **Producer**: the client that sends NTS events to `/nts` (a decoder, `fidetype ws replay-to-ws`).
- **Server**: the program that accepts the connections, feeds the trust layer and publishes the output (`fidetype ws run`).
- **Subscriber**: a client of `/decisions` or `/events` (a browser page, `fidetype ws subscribe`).
- **Stream**: one NTS stream (header, then events). It has a **stream id** and can span several connections (resume).
- **Control message**: a message whose `type` starts with `ws_`. It is part of the binding, not an NTS event.

## Proposal

### 1. Paths and roles
| Path | Direction | Content |
|---|---|---|
| `/nts` | producer → server | NTS events of one stream per connection (section 5) |
| `/nts` | server → producer | `ws_welcome`, `ws_ack`, `ws_error` |
| `/decisions` | server → subscriber | `trust_decision` events (FEP-0001) with `ws_seq`; resumable (section 7) |
| `/events` | server → subscriber | the NTS events after sequencing, with `stream_id`; a tap for monitoring; not resumable |

Rules:
1. A server MAY use other path names. It MUST document them. The roles stay as in the table.
2. A server MUST refuse an unknown path in the opening handshake (HTTP 404).

### 2. Handshake
1. A client MUST offer the subprotocol `nts-ws.0.1` (`Sec-WebSocket-Protocol`). A server MUST select it, and MUST refuse a client that does not offer it (HTTP 400). The token `nts-ws.0.1` stands for the binding version `nts-ws/0.1` (section 10).
2. A browser client SHOULD send an `Origin` header (browsers do this). A server that serves browsers SHOULD check `Origin` against a list (the reference: `--allow-origin`).

### 3. Framing
Rules:
1. Every message MUST be a WebSocket **text** message. A server MUST refuse a binary message (close 1003).
2. A message MUST be one UTF-8 JSON object with a string `type`, without the tokens `NaN`, `Infinity` or `-Infinity` (spec 6.2 rule 3: `null` in a log-probability is `-inf`). A receiver MUST refuse anything else (close 1007).
3. A message SHOULD be at most 1 MiB. A server MAY refuse a larger one (close 1009).
4. A message is an NTS event (spec 6.2), a `ws_batch` (section 6 rule 4) or a control message.
5. A receiver MUST ignore unknown keys (spec 6.2 rule 5). The keys `ws`, `ws_seq`, `ws_t_sent` and `ws_t_recv` are binding keys. A v0.1 consumer that gets an event from a WebSocket bridge ignores them.

### 4. Control messages
| Type | From | Fields | Meaning |
|---|---|---|---|
| `ws_welcome` | server | `binding`, `role` (`ingest`, `decisions`, `events`), `seq`, and per role: `stream_id`, `resumed`, `ack_every`, `window` (ingest); `spec`, `config_id`, `first_available`, `replayed`, `missed` (decisions) | The answer to the header or to `ws_subscribe` |
| `ws_ack` | server | `stream_id`, `seq` | All events up to `ws_seq = seq` are released to the trust layer (or dropped as gaps) |
| `ws_error` | server | `code`, `detail` | Sent before a refusal close; codes in section 9 |
| `ws_batch` | producer | `events` | Several events in one message (section 6 rule 4) |
| `ws_auth` | client | `token` | A token, for clients that cannot set HTTP headers (section 9) |
| `ws_subscribe` | subscriber | `binding`, `from_seq`, `types`, `stream_id` (all optional) | The first message on `/decisions` or `/events` |

Rules:
1. NTS event types never start with `ws_`. A producer MUST NOT send a `ws_` type that this table does not list, except new types of a later binding version.
2. A server MUST NOT forward a `ws_auth` message or a token.
3. A receiver MUST ignore an unknown `ws_` message (and count it).

### 5. Input: the stream
Rules:
1. The first message on `/nts` (after an optional `ws_auth`) MUST be the NTS **header** (spec 6.2 line 1). A server MUST refuse any other first message (close 1007).
2. The header follows the v0.1 header rules. A server MUST refuse an unknown `spec_version` (close 1007).
3. The header MAY carry the binding record `ws`: `binding` (default `nts-ws/0.1`), `stream_id` (a string of 1-128 characters), `resume` (boolean, default false). A producer SHOULD set a stable `stream_id`; without one, the server gives one (`anon-N`) and the stream cannot be resumed. The `ws` record is not part of the NTS header: the server removes it before the trust layer gets the header.
4. One connection carries one stream. Several producers MAY send at the same time; each stream id is one trust session. The `session` of each `trust_decision` is the stream id.
5. The server answers the header with `ws_welcome` (`seq` = the last `ws_seq` it has, 0 for a new stream).
6. A later `header` event inside the stream (spec 6.2) is an ordinary event with a `ws_seq`.

### 6. Sequence numbers, order and gaps
Rules:
1. Every NTS event after the header MUST have `ws_seq`: an integer ≥ 1, 1 for the first event of a stream, +1 for each next event. The header has no `ws_seq`. A server MUST refuse an event with a missing or non-integer `ws_seq` (close 1007).
2. **Duplicates.** An event with a `ws_seq` that the server already has (released or held) is a duplicate. The server MUST drop it and count it. So a producer may resend safely.
3. **Reorder and gaps.** The server releases events to the trust layer in `ws_seq` order. An event with a `ws_seq` above the next expected one is held. The reference holds at most `reorder_window` events (16) for at most `reorder_timeout_s` (0.25 s). When the window is full or the oldest held event is older than the time-out, the missing numbers are a **gap**: the server releases the held events from the lowest one on, and counts the gap and the missing events. With `reorder_window = 0` a missing number is a gap at once. Inside one TCP connection a conforming producer does not reorder; the window covers resend after resume and multi-path bridges.
4. **Batches.** `{"type": "ws_batch", "events": [...]}` carries 1 to `max_batch` (reference: 1024; larger: close 1009) events. The events MUST have consecutive `ws_seq` values, and MUST NOT be control messages (else close 1007). A batch is the same as its events sent one by one.
5. **No decision on a cut utterance.** At a gap the consumer MUST drop the open utterance without a decision (`abort_utterance`). It MUST also drop the `frame` events after the gap up to the next `segment_end`, `end` or `header`: they are the tail of the cut utterance. A `hypothesis` event is complete in itself and is not dropped.

### 7. Acks, back-pressure and the decisions channel
Rules:
1. **Acks.** The server sends `ws_ack` (`seq` = the last released `ws_seq`) after every `ack_every` released events (reference: 64), after `end`, and when released events have waited `ack_interval_s` (reference: 0.1 s) for an ack.
2. **Producer window.** The welcome gives `window` (reference: 4096). A producer MUST NOT have more than `window` unacknowledged events. It keeps them for resend (section 8).
3. **Server back-pressure.** When the trust layer is behind, the server SHOULD stop reading from the producer connections (the reference: more than `queue_max` = 8192 queued items). TCP flow control then slows the producer. The server MUST NOT drop events to keep up.
4. **Decisions channel.** A subscriber sends `ws_subscribe` first (after an optional `ws_auth`). The server answers with `ws_welcome` (`seq` = the last decision number, `first_available`). Each `trust_decision` then has `ws_seq`: 1, 2, 3, ... over the whole channel (all streams), with no gap. The FEP-0001 `seq` field (the per-session decision index) is a different field and stays unchanged.
5. **Resume of a subscriber.** With `from_seq`, the server first replays the decisions with `ws_seq ≥ from_seq` that it still holds (reference: the last 4096), then sends new ones. If `from_seq < first_available`, the welcome has `missed` = the number of lost decisions. Without `from_seq`, the subscriber gets new decisions only.
6. **Subscriber gaps.** A subscriber MUST check that `ws_seq` increases by 1. On a gap it MUST NOT skip silently: it closes, connects again and subscribes with `from_seq` = the next expected number. It drops duplicates. It MUST follow FEP-0001 (act only on final COMMIT, one final decision per utterance).
7. **Slow subscribers.** A slow subscriber MUST NOT slow the trust layer. The server gives each subscriber a bounded queue (reference: 1024 messages). When it is full, the server sends `ws_error` `slow_consumer` and closes with 1013; the subscriber resumes with `from_seq`.
8. `/events` uses the same `ws_subscribe` (with an optional `types` filter; the reference default is all types). Its messages are the released NTS events with `stream_id` and their producer `ws_seq`. It has no replay and no channel-wide sequence.

### 8. Reconnect and resume (input)
Rules:
1. A connection can end without a close handshake. The server detects it by the TCP state and by WebSocket ping/pong (reference: ping every 5 s, time-out 10 s).
2. When the connection of an unfinished stream ends, the server keeps the stream state (header, expected `ws_seq`, held events, the open utterance) for `resume_timeout_s` (reference: 10 s). The open utterance waits; it is not decided.
3. To resume, the producer connects again and sends the same header with `ws.resume = true` and the same `stream_id`. The header MUST be equal to the first one (except `ws`); else the server refuses it (close 1007).
4. The server answers `ws_welcome` with `resumed = true` and `seq` = the last released `ws_seq`. The producer resends every event after `seq`. Events it resends twice are duplicates (section 6 rule 2). A lossless resume gives the same decisions as an unbroken connection.
5. If no resume comes within `resume_timeout_s`, the stream is **lost**: the server drops the open utterance without a decision (as FEP-0002 section 7 rule 3) and forgets the stream.
6. A resume header for a stream that the server does not know (never seen, or lost) starts a new stream: `resumed = false`, `seq = 0`. The producer MUST then treat the old stream as ended. It SHOULD NOT resend events of utterances that the server may already have decided.
7. **Take-over.** If a resume arrives while the old connection still looks open (a half-open TCP connection), the new connection wins: the server sends `ws_error` `taken_over` on the old one and closes it with 4001.
8. A new header (not a resume) with the stream id of an unfinished stream replaces it: the open utterance of the old stream is dropped without a decision.
9. After `end`, a clean close forgets the stream.

### 9. Close codes, auth and TLS
| Close code | `ws_error` code | When |
|---|---|---|
| (HTTP 400) | — | No subprotocol `nts-ws.0.1` (section 2) |
| (HTTP 404) | — | Unknown path |
| 1003 | `binary` | A binary message |
| 1007 | `bad_message`, `bad_header`, `bad_seq`, `bad_batch`, `bad_subscribe` | Not JSON, not an object, a bad header, a bad or missing `ws_seq`, a bad batch, a bad `ws_subscribe` |
| 1008 | `auth` | Missing or wrong token |
| 1009 | `too_big` | A message or a batch above the limit |
| 1013 | `slow_consumer` | A subscriber queue is full (not a refusal: resubscribe) |
| 4000 | `binding` | An unknown binding version |
| 4001 | `taken_over` | A newer connection resumed the stream (not a refusal) |

Rules:
1. **Auth hook.** A server MAY require a token. A client SHOULD send it as `Authorization: Bearer <token>` in the opening handshake.
2. A browser cannot set this header. A browser client sends `{"type": "ws_auth", "token": "..."}` as its first message instead. The server MUST accept a token from either place.
3. A missing or wrong token MUST close the connection with 1008 before the server accepts any event. This FEP defines the hook, not the token format or its issuance (a shared secret, a signed token, OAuth: outside this binding). The reference has a shared-token check only.
4. A token MUST NOT appear in a log line, a header, an event, a decision or a `ws_error` detail. A token SHOULD NOT go in the URL query (proxies log URLs).
5. **TLS.** Off `localhost`, a client and a server MUST use `wss://` (TLS 1.2 or later). NTS events and `shown` texts are personal data. The reference server binds `127.0.0.1` by default and warns when it listens elsewhere without TLS; it can load a certificate (`--certfile`, `--keyfile`) or run behind a TLS reverse proxy.

### 10. Versioning
Rules:
1. The binding version is `nts-ws/0.1`; its subprotocol token is `nts-ws.0.1`.
2. A missing `ws.binding` (header), `binding` (`ws_subscribe`, `ws_welcome`) means `nts-ws/0.1`.
3. A receiver MUST refuse a binding version it does not know (server: close 4000; subscriber: treat the channel as invalid). While the major version is 0, every minor change can break readers (spec 5.1.4).
4. The binding version is separate from the NTS `spec_version`.

### 11. Clock and timestamps
Rules (consistent with FEP-0002 section 6):
1. WebSocket does not change any NTS time field. `t`, `t_start`, `t_end` and the other time fields stay in the producer's clock, and the header's `clock_domain` stays as the producer wrote it. Unlike LSL, WebSocket has no clock synchronisation, so the binding has no `event_clock` key: the event clock is always the source clock (FEP-0002 `event_clock = source`).
2. NTS frame times MUST increase strictly (spec 6.2 rule 4). The binding does not clamp or reorder times; `ws_seq` gives the order.
3. A producer MAY add `ws_t_sent` (the send time, seconds) to each event. A server MAY add `ws_t_recv` (the receive time). These are transport stamps, not event times. A consumer MAY compute a transport latency (`ws_t_recv − ws_t_sent`) only when both stamps come from the same clock (the reference: `perf_counter` of one host, which is valid on localhost only). Across hosts, a consumer needs its own clock sync (for example NTP) and SHOULD NOT use the difference.
4. A server MAY add to each `trust_decision` a `ws` record: `stream_id`, `binding`, `trigger_seq`, `server_latency_s` (emission − `ws_t_recv` of the closing event; always valid) and `e2e_latency_s` (emission − `ws_t_sent`; valid on one host only).

### Extension keys (summary)
| Key | Where | Meaning |
|---|---|---|
| `ws` | header (object) | `binding`, `stream_id`, `resume` (section 5) |
| `ws_seq` | NTS events (input); `trust_decision` (output) | Sections 6 and 7 |
| `ws_t_sent`, `ws_t_recv` | NTS events | Transport stamps (section 11) |
| `stream_id` | `/events` messages | The source stream |
| `ws` | `trust_decision` (object) | Provenance record of section 11 rule 4 |

A v0.1 consumer ignores all of them (5.1, 6.2 rule 5).

## Examples
Producer → server (`/nts`, subprotocol `nts-ws.0.1`):
```json
{"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a", "b"], "vocab_type": "char", "blank_id": 0, "source": "acme", "frame_period": 0.04, "ws": {"binding": "nts-ws/0.1", "stream_id": "acme-1"}}
{"type": "frame", "t": 0.00, "log_probs": [-0.105, -2.659, -3.507], "ws_seq": 1}
{"type": "ws_batch", "events": [{"type": "frame", "t": 0.04, "log_probs": [-0.105, -2.659, -3.507], "ws_seq": 2}, {"type": "segment_end", "ws_seq": 3}]}
```
Server → producer:
```json
{"type": "ws_welcome", "binding": "nts-ws/0.1", "role": "ingest", "stream_id": "acme-1", "seq": 0, "resumed": false, "ack_every": 64, "window": 4096}
{"type": "ws_ack", "stream_id": "acme-1", "seq": 3}
```
Resume after a broken connection (the server had released up to 2):
```json
{"type": "header", "spec_version": "0.1", "...": "...", "ws": {"binding": "nts-ws/0.1", "stream_id": "acme-1", "resume": true}}
{"type": "ws_welcome", "binding": "nts-ws/0.1", "role": "ingest", "stream_id": "acme-1", "seq": 2, "resumed": true, "ack_every": 64, "window": 4096}
```
Subscriber (`/decisions`):
```json
{"type": "ws_subscribe", "binding": "nts-ws/0.1", "from_seq": 41}
{"type": "ws_welcome", "binding": "nts-ws/0.1", "role": "decisions", "spec": "FEP-0001", "config_id": "tcfg-0123456789abcdef", "seq": 42, "first_available": 1, "replayed": 2}
{"type": "trust_decision", "session": "acme-1", "seq": 7, "utterance": 3, "is_final": true, "action": "COMMIT", "shown": ["ab"], "p_top1": 0.93, "score_semantics": "calibrated_prob", "ws_seq": 41, "ws": {"stream_id": "acme-1", "binding": "nts-ws/0.1", "trigger_seq": 118, "server_latency_s": 0.0019}}
```

## Compatibility
- v0.1 streams and files do not change. The binding replaces the sketch of 6.3.
- A 6.3-sketch producer (header, then events, no `ws_seq`) does not conform: rule 6.1 requires `ws_seq`. Adding `ws_seq` is a one-line change. A header without the `ws` record is accepted (binding `nts-ws/0.1`, a server stream id).
- The output is ordinary FEP-0001 `trust_decision` events. A FEP-0001 consumer reads them unchanged.

## Conformance
Profile `fep-0004` (opt-in, `src/fidetype/conformance/profiles/fep0004.py`; TypeScript port `sdk/typescript/src/profiles/fep0004.ts`). Golden vectors: [`spec/conformance/fep-0004/`](../conformance/fep-0004/) (`manifest.json`; 37 JSON scenarios: 20 accept, 17 reject).

```
fidetype conformance --profile fep-0004                               # Python reference consumer over the vectors
fidetype conformance consumer --profile fep-0004 --impl my_mod:consume
node sdk/typescript/bin/fidetype-ts.mjs conformance                   # TypeScript SDK (all profiles)
```

A vector is a JSON scenario (schema `fidetype.conformance.ws-scenario/1`).
- `kind: "ingest"`: `steps` script connections to `/nts`. A step has a time `at` (seconds, not decreasing; the time-outs run before each step), a connection number `conn`, and exactly one of: `open` (`subprotocols`, optional `authorization`), `msg` (a message as a JSON value), `raw` (a text message as a string), `binary`, `drop` (the connection ends without a close handshake), `close`, `tick`. Optional `settings` (the reference values of sections 6-8 and a required `token`) and `route` (`frames`: CTC greedy decoder; `hypothesis`). At the end, the reference drops the open utterance of every stream that waits for a resume and closes the open utterance of every connected stream. A refusal (close 1002, 1003, 1007, 1008, 1009 or 4000) rejects the vector.
- `kind: "subscribe"`: `messages` that a `/decisions` subscriber receives, after a `ws_subscribe` with `from_seq` (scenario key; default 1, `null` = new decisions only).

Expected values (ingest): `streams`, `event_types` and `frames` (events released to the trust layer), `decisions`, `final_decisions`, `sessions`, `aborted_utterances`, `skipped_after_gap`, `duplicates`, `reordered`, `gaps`, `missing_events`, `resumes`, `takeovers`, `lost_streams`, `ignored_controls`, `welcomes` (`[stream_id, seq, resumed]`), `acks` (`seq` of each `ws_ack`), `closes` (`[conn, code]`). Expected values (subscribe): `decisions`, `final`, `acted` (texts a client may act on), `gaps` (the `from_seq` of each resubscribe), `duplicates`, `missed`.

| Section | Accept | Reject |
|---|---|---|
| 2, 5 handshake and header | W01, W05 (no `ws` record), W14 (two producers) | W18 (first not header), W19 (no subprotocol), W20 (binding), W21 (spec_version) |
| 3, 6 framing | W01, W02 (batches), W03 (hypothesis route), W04 (unknown types) | W22 (binary), W23 (not JSON), W24 (no `ws_seq`), W25 (float `ws_seq`), W26 (batch order), W27 (batch size), W30 (bad frame) |
| 6 order and gaps | W06 (duplicates), W07 (reorder), W08 (gap after time-out), W09 (window 0) | |
| 7 acks | W17 | |
| 8 resume | W10 (lossless), W11 (time-out), W12 (unknown stream), W13 (take-over) | W28 (resume header differs) |
| 9 auth | W15 (`ws_auth`), W16 (Bearer header) | W29 (wrong token) |
| 7 decisions channel | W31, W32 (gap, resubscribe), W33 (missed history) | W34 (no welcome), W35 (binding), W36 (no `ws_seq`), W37 (two finals) |

## Reference implementation
`fidetype.adapters.ws` (`IngestCore`, `SubscriberCore`, `OutputHub`, `WSServer`, `WSTrustRunner`, `WSProducer`, `replay_to_ws`, `subscribe`; CLI `fidetype ws run|replay-to-ws|subscribe`). The optional dependency is `websockets` (BSD-3-Clause, `pip install "fidetype[ws]"`, pinned 17.4); the sans-IO cores need no library. TypeScript: `IngestCore`, `SubscriberCore`, `DecisionSubscriber` (browser client) in `sdk/typescript/src/ws.ts`. Tests: `tests/test_adapter_ws.py`, `tests/test_fep_profiles.py`, `sdk/typescript/test/ws.test.mjs`. Browser example: `examples/ws-browser/`.

## Alternatives
- **Sequence numbers per message, not per event.** Rejected: a batch would hide which events are lost, and resend would need the old batch borders.
- **Reuse the FEP-0001 `seq` name.** Rejected: `trust_decision` already has `seq` (the per-session decision index). A separate `ws_seq` keeps both.
- **Binary frames (CBOR, Protocol Buffers).** Not in 0.1: JSON text keeps the 6.2 objects unchanged and is easy in a browser. A dense frame of 40 tokens is about 0.5 kB of JSON; at 25 frames/s this is about 13 kB/s per stream, which is small. A binary form can be a later binding version (spec open question 1).
- **Server-Sent Events for the output.** Rejected as the only form: SSE is one-way, so the input direction would need a second transport. `/decisions` over WebSocket also carries `ws_subscribe` and resume.
- **Token in the URL query.** Rejected as a recommendation (proxy logs); `ws_auth` covers browsers.

## Privacy and leakage
- The binding carries the same data as v0.1 JSON Lines and FEP-0001 decisions: neural-derived data and `shown` texts (personal data). Use `wss://` off localhost (section 9 rule 5). A server SHOULD offer a mode without texts (the reference: `--no-text`).
- The reference server never writes the client address or a token into a header, a decision or a log line.
- `/events` exposes the full input stream; a server SHOULD require auth for it on any shared network.

## Open questions
1. Should the decisions channel carry a back channel (a user selection after `OFFER`) as a client → server message?
2. Should the binding define an optional clock-sync exchange (NTP-like `ws_time` messages), so that `ws_t_sent` is valid across hosts?
3. Should `/events` get a channel-wide sequence and resume like `/decisions`?
4. Is 1024 a good default `max_batch` for constrained producers (microcontrollers with a small TCP buffer)?
5. LAN and Wi-Fi tests (M6-10) may change the reference `reorder_timeout_s` and `resume_timeout_s`.
