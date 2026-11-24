---
title: Collector (receivers, processors, exporters)
type: concept
tags: [collector, pipeline, standard, p3, privacy, websocket, lsl, trust-layer]
sources: []
updated: 2026-11-18
---

# Collector

The collector is one service that takes NeuralTextStream (NTS) input from several sources, runs processors on it, and sends the results to several targets. One configuration file wires it. It is the P3 part of the "OpenTelemetry for neural input" plan ([roadmap P3](../questions/roadmap-standard.md#p3-collector-pipeline)). The design is in the draft [FEP-0006](../../spec/feps/0006-collector.md). The code is `src/fidetype/collector/` (v0 and v0.1, 2026-11-14; LSL receiver and exporter later the same day).

```
 file  ----> receiver --\                                         /--> jsonl (decision log)
 ws /nts --> receiver ---+--> validate --> trust --> thin --> redact --+--> stdout
 LSL -----> receiver --/                                           +--> ws /decisions
                                                                   \--> LSL fidetype.decisions
             GET /healthz (open, status only), GET /metrics (JSON; 127.0.0.1 by default, optional bearer token)
```

## Model
| Part | Job | v0 components |
|---|---|---|
| Receiver | Read a source. Give `(stream id, event)` items in order. Turn a loss into a status item (`gap`, `lost`) | `file` (JSON Lines, tail mode), `websocket` (FEP-0004 `/nts`), `lsl` (FEP-0002 frames + events streams) |
| Processor | Change or replace items. Keep state per stream | `validate`, `trust`, `redact`, `thin` |
| Exporter | Write items out. Never change them | `jsonl`, `stdout`, `websocket` (FEP-0004 `/decisions`, on the receiver's server or standalone), `lsl` (decisions outlet, LSL-X1 … LSL-X3) |
| Pipeline | Connect named receivers, processors, exporters | any number |
| Service | Run loop, stop, metrics file, health endpoint | `fidetype collector --config <file>` |

The idea comes from the OpenTelemetry Collector (receivers → processors → exporters, pipelines, one configuration). The text and the code are our own.

## What v0 reuses (no copies)
| Collector part | Wraps |
|---|---|
| `websocket` receiver and exporter (shared or standalone server) | `fidetype.adapters.ws.WSServer`, `OutputHub` ([WebSocket input](websocket-input.md)) |
| `lsl` receiver | `fidetype.adapters.lsl.open_source` / `LSLEventSource` ([LSL input](lsl-input.md)): resolve, clock correction, merge, gap modes, non-blocking reconnect (M6-14), fast reconnect and `open_timeout_s` (M6-16) |
| `lsl` exporter | `fidetype.adapters.lsl.DecisionOutlet` (FEP-0002 section 8 desc keys) |
| `trust` blank-COMMIT guard | `FrozenTrustConfig.with_commit_gate` / `CommitGate` (M2-18) |
| `trust` processor | `StreamingTrustLayer` ([streaming trust layer](streaming-trust-layer.md)) and the loss rules of `WSTrustRunner` |
| `trust` option `ledger` | `fidetype.trust.provenance.ProvenanceLedger` ([provenance ledger](provenance-ledger.md)) |
| `validate` processor | `fidetype.conformance` header checks, the FEP-0001 decision checks ([conformance suite](conformance-suite.md)), the reference frame reader |

## Rules it applies
| Rule | Spec | How |
|---|---|---|
| Never a final decision on a cut segment | GEN-8, LSL-G2, WS-Q5 | Every loss path ends in a `gap` or `lost` status. The trust processor drops the open utterance without a decision, and after a gap drops frames up to the next boundary |
| No silent drop of input | WS-A3 | An unreadable line or an invalid event becomes a `gap`. Reading waits for processing (back-pressure) |
| Decoded text is personal data | SEC-7, TD-10, PRV-2 | `redact`: remove `shown`, or replace it with an HMAC (key from an environment variable) |
| No host name, address or token in output | LSL-C3, WS-T3 | Stream ids never come from file names or addresses. Tokens and keys only from environment variables; a secret key in the file is a configuration error. The health server logs no addresses |
| Decision log holds decisions only | TD-11 | A `jsonl` exporter refuses a mixed `types` list |
| Decisions name their rules version | 6.1, VER-1, TD-F3 | Every decision carries `spec_version: "1.0"` (directly after `type`) |
| No blank final COMMIT for 1.x decisions | TD-9 | The trust processor adds the commit gate `min_chars = 1` if the configuration has none (new `config_id`, logged). A gated decision is OFFER or ABSTAIN with reason `commit gate: ...`, counted as `gated_commits`. `always_commit` is refused |
| No blank candidate in an OFFER, ASK or OFFER_WORDS | TD-12 (RC2) | The trust processor removes blank texts from `shown` (`drop_blank_candidates`). An OFFER or OFFER_WORDS with no candidate left becomes `ABSTAIN` with `shown = []` (not an OFFER without `shown`, which reads as a privacy log, TD-10). An ASK stays an ASK. `reason` gets `TD-12: blank candidates dropped`. Counters `blank_candidates_dropped`, `blank_offers_abstained`. The provenance ledger keeps the trust layer's own decision |
| Unique sessions across receivers | FEP-0006 1.4 | With two or more receivers in one pipeline, the stream id is `<receiver>/<stream id>` (for example `replay/replay-0`). It is the decision `session`. With one receiver the id does not change |

Loss paths that give no final decision on the open utterance (all tested): an unreadable line, an invalid frame, a WebSocket `ws_seq` gap, `eof = "cut"`, a tail-mode idle time-out, a stop while an utterance is open, a lost LSL inlet (also when it is not reconnected), an LSL frame gap inside an utterance (`on_gap = "abort"`).

## Configuration
TOML or JSON only. YAML is not supported: it would need a new dependency (PyYAML), and TOML and JSON hold the same structure. Example: [`examples/collector/collector.toml`](../../examples/collector/collector.toml). `fidetype collector --config <file> --check` checks a file and prints the pipelines. Errors name the bad value, for example `pipelines.main.processors[1]: unknown processor 'trsut' (known: check, trust)`.

## LSL receiver and exporter (2026-11-14)
| LSL event | Collector item | Effect |
|---|---|---|
| Inlet lost | `lost` | No final decision on the open utterance (LSL-G2). Reconnect on a worker thread; the new header resets the stream |
| `reconnected` | none (counted) | The header that follows starts the stream again |
| Frame gap inside an utterance, `on_gap = "abort"` (collector default) | `gap` | The utterance and its frames up to the next boundary are dropped |
| Frame gap right after `segment_end` / `end` / header | none (`gaps_between_utterances`) | A pause between utterances cuts nothing |
| Frame gap, `on_gap = "mark"` | none (`gaps_marked`) | The utterance goes on (the LSL-G1 reference default) |
| `end` | `end`, then `closed` | With `stop_at_end = true` (default) the receiver is done |
| Not reconnected within `reconnect_timeout_s` | none | The receiver is done (the loss already sent `lost`) |

> **Our take:** the collector uses `on_gap = "abort"`, not the LSL-G1 reference default `mark`. In the collector a hole inside an utterance is lost input, and FEP-0006 5.2 says lost input never gets a final decision. The check "a gap right after a boundary cuts nothing" keeps file replays usable: their utterances are often 1 s apart.

The `lsl` exporter publishes `trust_decision` events only, one JSON per sample, with the desc keys `role`, `event_type`, `spec`, `binding` and `config_id` (taken from the pipeline's trust processor). LSL has no access control, so `no_text = true` removes `shown` (SEC-7); without it the collector logs a warning. Example: [`examples/collector/collector-lsl.toml`](../../examples/collector/collector-lsl.toml).

## v0.1 decisions (2026-11-14)
| Topic | Decision |
|---|---|
| Configuration format | TOML and JSON only; a `.yaml` file gives a clear error |
| File without `end` | Default stays `eof = "close"`. One warning per stream; counter `closed_without_end` in `/metrics` |
| Several receivers in one pipeline | Prefix `<receiver>/<stream id>` (documented in FEP-0006 1.4) |
| Health and metrics | `127.0.0.1:13133` by default. `/healthz` is always open and shows only `{"status": ...}` (liveness probes need no header). Optional bearer token (`token_env`; never in the file or a log) protects `/metrics` only. A bind beyond localhost needs a token or `allow_unauthenticated = true` (then a warning) |
| `spec_version` | `"1.0"` on every decision; the commit gate makes TD-9 hold |
| Fan-out of one receiver to two pipelines | Not now (future work) |
| Standalone `/decisions` | A `websocket` exporter without `receiver` starts its own server: `/decisions` only (`/nts`, `/events` give 404), optional `token_env`, TLS, `linger_s` to stay open after a file replay |

Decision logs of the collector pass the FEP-0001 profile in the Python, TypeScript (`fidetype-ts consume`) and Rust (`fidetype-rs consume`) consumers, also a log with a gated blank COMMIT (checked 2026-11-14).

## Tests (2026-11-14; P3-04 additions 2026-11-17)
`tests/test_collector_pipeline.py` (P3-04, P7-05): segmenter rules, guard processor (profile, online ACI, gap loss rule, valid decisions, feedback), `os_text` commit filter, latency helpers, NPZ input, the kit against the consumer entry point, and the integration runs (WebSocket at 50 Hz for both gated profiles, file, LSL if pylsl is installed, the logits guard reported). CI job `collector`.


`tests/test_collector.py`, 44 tests (29 in v0, 15 in v0.1):
- File → validate → trust → jsonl gives the same decisions as `fidetype trust` (the reference replay) on a synthetic 4-utterance stream.
- `redact` drop: no committed text appears in the log file. `redact` hmac: `shown_hmac` equals the HMAC of the reference text; the key is not in the file.
- Cut segments: the five loss paths above give no final decision on the cut utterance; the other utterances keep theirs.
- WebSocket in and `/decisions` out: the same decisions as the reference, with `ws_seq` 1, 2, 3 on the channel.
- 16 configuration errors give messages that name the value. Command line exit codes (0, 2).
- `tests/test_collector_lsl.py` (17): scripted LSL inlets (loss mid-utterance + reconnect, `abort` / `mark` gaps, gap between utterances, shutdown, give-up, `stop_at_end = false`), the exporter (`no_text`), configuration errors, `config_id` from the trust processor, and a real LSL loopback: outlet → collector → decisions outlet → inlet gives the same decisions as the file receiver, the desc keys of LSL-X1, and no host name (skips without pylsl).
- v0.1: the `eof = "close"` warning (once per stream) and its counter; the `<receiver>/<id>` prefix with two receivers (a cut stream still reaches its own session); health default listen, refused open bind, warning with `allow_unauthenticated`, bearer token (`/metrics` 401 without it, `/healthz` open; token never in metrics or logs); `spec_version` on every decision and the FEP-0001 profile check; a blank final COMMIT is gated, and its blank-only OFFER becomes `ABSTAIN` with `shown = []` (TD-12; the log passes the FEP-0001 profile with no warning); `drop_blank_candidates` cases; gate rules and the `always_commit` refusal; file → trust → standalone `/decisions` with token, `from_seq = 1` replay after the input is done, and `/nts` refused.

## P3-04 integration test, latency budget, consumer entry point (2026-11-17)
New parts ([docs](../../docs/collector.md#integration-test-and-latency-budget)):

| Part | Kind | What it does |
|---|---|---|
| `segment` | processor (P3-02) | Adds `segment_end` on a pause, a blank run or a length limit; causal; copies the receive stamps of the frame that caused the cut |
| `guard` | processor (P3-02) | The drop-in guard ([trust quickstart](../../docs/trust-quickstart.md)), optional per-user profile ([personalisation](trust-personalisation.md)) (`PersonalTrust` drift tests) and online control (`guard.online`); key frames use the `fidetype live` key beam search (no copy of the live runner); `passthrough` writes the NTS input next to the decision log |
| `os_text` | exporter (P3-03) | `stub` backend: types only final text COMMITs, logs the full decision next to each typed text |
| `refuse_research_only` | option of every exporter (P5-18) | Drops decisions with `input.research_only = true` (FEP-0010 TD-15) and, with `unknown_licence = "refuse"` (default), decisions without the key; counters and one log line. Default off. Test: a CC-BY-NC stream types nothing through `os_text`, a CC0 stream types as before. P5-22: on a `jsonl` or `stdout` exporter of input events it drops a research-only (or, by default, unknown-licence) stream whole, by its header keys; a refused stream writes no file, a CC0 stream writes the same file as before ([provenance and privacy](../../docs/provenance-and-privacy.md)) |
| `file` receiver | receiver (P3-01) | Now also reads NPZ streams (reference reader, no pickle) |
| `[service] latency` | service | Per-stage latency (`receive`, each processor and exporter, `pipeline`, `added`, `e2e`) in `/metrics` |
| `fidetype-collector consume` | entry point (P7-05, P7-07) | The kit contract: file, LSL or WebSocket receiver (captures replayed without network) + `validate` (with the FEP-0003 / FEP-0005 rules) at a stream level; exit 0 = accept |

Results ([docs](../../docs/collector.md#results)): with 50 Hz synthetic frames the p95 **added** latency is 1.1 to 1.3 ms (implant-speech, decoder n-best before the collector) and 1.2 to 2.3 ms (emg-key, key beam search in the collector), over WebSocket, file and LSL input: far below the 50 ms budget. Every run reaches producer level NTS Trust-ready with `nts-conform`. The logits guard with its built-in CTC beam search inside the collector needs 104 to 108 ms at p95 (gap P3-06). The collector consumer reaches consumer level NTS Trust-ready on the kit for `text`, `intent` and `control` with both bindings (36 / 36, P7-07; before: `text` only, 28 / 36).

> **Our take:** the collector itself costs well under 1 ms per decision. The budget question is where the decoder runs. A decoder that searches only at the segment end (the built-in CTC beam of the drop-in guard) does not fit 50 ms; an incremental decoder, or a decoder before the collector, does.

## What v0 does not do
- No gRPC, OTLP, Arrow or Parquet. No real OS input-method backend (only the `os_text` stub), no Apple BCI HID bridge (P3-03).
- No LM rescoring processor, no rate limiter, no `meta`-key privacy filter (P3-02). The `redact` processor covers decoded text only.
- Text profile only in the trust and guard processors (intent and control layers are separate tools).
- YAML configuration: FEP-0006 says no (no new dependency); the roadmap exit criterion says YAML (gap P3-09).
- The integration run uses synthetic input; a B2T '25 replay through the collector is gap P3-08.
- One process, one loop thread. No hot reload, no fan-out of one receiver to two pipelines (future work), no plug-in registry.
- The example trust configuration is a toy (not calibrated). It shows the wiring only.

> **Our take:** v0.1 meets the first half of the P3 exit criterion ("one configuration: replay → trust → file and WebSocket exporters") on synthetic data. It does not yet meet the other half (an OS input exporter that types on Windows, a measured latency budget). The item model `(stream id, event)` plus status items is small and language-neutral, so a later Rust collector can keep the same configuration and the same tests.

## Open questions (FEP-0006)
Python or Rust for v1 (the user decides).

Closed on 2026-11-14 (FEP-0006 "Decisions", second round): blank OFFER candidates → spec rule TD-12 and the collector step above; health token scope → open `/healthz`, protected `/metrics`; ungated configurations → the collector keeps adding the gate with a log line.

> **Our take:** adding the gate inside the collector keeps old trust configurations usable, but the `config_id` in the decisions then differs from the file on disk. The log line shows both ids. Freezing the gated configuration (`with_commit_gate(min_chars=1)`) avoids the surprise.

## Related
[NTS specification](nts-spec.md) · [`trust_decision` event](trust-decision.md) · [FEP process](fep-process.md) · [WebSocket input](websocket-input.md) · [LSL input](lsl-input.md) · [streaming trust layer](streaming-trust-layer.md) · [provenance ledger](provenance-ledger.md) · [conformance suite](conformance-suite.md) · [roadmap P3](../questions/roadmap-standard.md#p3-collector-pipeline)
