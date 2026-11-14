---
title: Collector (receivers, processors, exporters)
type: concept
tags: [collector, pipeline, standard, p3, privacy, websocket, trust-layer]
sources: []
updated: 2026-11-14
---

# Collector

The collector is one service that takes NeuralTextStream (NTS) input from several sources, runs processors on it, and sends the results to several targets. One configuration file wires it. It is the P3 part of the "OpenTelemetry for neural input" plan ([roadmap P3](../questions/roadmap-standard.md#p3-collector-pipeline)). The design is in the draft [FEP-0006](../../spec/feps/0006-collector.md). The code is `src/fidetype/collector/` (v0 and v0.1, 2026-11-14).

```
 file  ----> receiver --\                                         /--> jsonl (decision log)
 ws /nts --> receiver ---+--> validate --> trust --> thin --> redact --+--> stdout
                                                                  \--> ws /decisions
             GET /healthz (open, status only), GET /metrics (JSON; 127.0.0.1 by default, optional bearer token)
```

## Model
| Part | Job | v0 components |
|---|---|---|
| Receiver | Read a source. Give `(stream id, event)` items in order. Turn a loss into a status item (`gap`, `lost`) | `file` (JSON Lines, tail mode), `websocket` (FEP-0004 `/nts`) |
| Processor | Change or replace items. Keep state per stream | `validate`, `trust`, `redact`, `thin` |
| Exporter | Write items out. Never change them | `jsonl`, `stdout`, `websocket` (FEP-0004 `/decisions`, on the receiver's server or standalone) |
| Pipeline | Connect named receivers, processors, exporters | any number |
| Service | Run loop, stop, metrics file, health endpoint | `fidetype collector --config <file>` |

The idea comes from the OpenTelemetry Collector (receivers → processors → exporters, pipelines, one configuration). The text and the code are our own.

## What v0 reuses (no copies)
| Collector part | Wraps |
|---|---|
| `websocket` receiver and exporter (shared or standalone server) | `fidetype.adapters.ws.WSServer`, `OutputHub` ([WebSocket input](websocket-input.md)) |
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

Loss paths that give no final decision on the open utterance (all tested): an unreadable line, an invalid frame, a WebSocket `ws_seq` gap, `eof = "cut"`, a tail-mode idle time-out, a stop while an utterance is open.

## Configuration
TOML or JSON only. YAML is not supported: it would need a new dependency (PyYAML), and TOML and JSON hold the same structure. Example: [`examples/collector/collector.toml`](../../examples/collector/collector.toml). `fidetype collector --config <file> --check` checks a file and prints the pipelines. Errors name the bad value, for example `pipelines.main.processors[1]: unknown processor 'trsut' (known: check, trust)`.

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

## Tests (2026-11-14)
`tests/test_collector.py`, 44 tests (29 in v0, 15 in v0.1):
- File → validate → trust → jsonl gives the same decisions as `fidetype trust` (the reference replay) on a synthetic 4-utterance stream.
- `redact` drop: no committed text appears in the log file. `redact` hmac: `shown_hmac` equals the HMAC of the reference text; the key is not in the file.
- Cut segments: the five loss paths above give no final decision on the cut utterance; the other utterances keep theirs.
- WebSocket in and `/decisions` out: the same decisions as the reference, with `ws_seq` 1, 2, 3 on the channel.
- 16 configuration errors give messages that name the value. Command line exit codes (0, 2).
- v0.1: the `eof = "close"` warning (once per stream) and its counter; the `<receiver>/<id>` prefix with two receivers (a cut stream still reaches its own session); health default listen, refused open bind, warning with `allow_unauthenticated`, bearer token (`/metrics` 401 without it, `/healthz` open; token never in metrics or logs); `spec_version` on every decision and the FEP-0001 profile check; a blank final COMMIT is gated, and its blank-only OFFER becomes `ABSTAIN` with `shown = []` (TD-12; the log passes the FEP-0001 profile with no warning); `drop_blank_candidates` cases; gate rules and the `always_commit` refusal; file → trust → standalone `/decisions` with token, `from_seq = 1` replay after the input is done, and `/nts` refused.

## What v0 does not do
- No LSL receiver or LSL decisions exporter yet (the [LSL adapter](lsl-input.md) exists; the wrapper is next).
- No gRPC, OTLP, Arrow or Parquet. No OS input-method exporter, no Apple BCI HID bridge, no AAC API (P3-03).
- No per-user calibration, LM rescoring, segmenter or rate limiter (P3-02, P5).
- Text profile only in the trust processor (intent and control layers are separate tools).
- No latency budget measurement yet (P3-04, target < 50 ms added).
- One process, one loop thread. No hot reload, no fan-out of one receiver to two pipelines (future work), no plug-in registry.
- The example trust configuration is a toy (not calibrated). It shows the wiring only.

> **Our take:** v0.1 meets the first half of the P3 exit criterion ("one configuration: replay → trust → file and WebSocket exporters") on synthetic data. It does not yet meet the other half (an OS input exporter that types on Windows, a measured latency budget). The item model `(stream id, event)` plus status items is small and language-neutral, so a later Rust collector can keep the same configuration and the same tests.

## Open questions (FEP-0006)
Python or Rust for v1 (the user decides).

Closed on 2026-11-14 (FEP-0006 "Decisions", second round): blank OFFER candidates → spec rule TD-12 and the collector step above; health token scope → open `/healthz`, protected `/metrics`; ungated configurations → the collector keeps adding the gate with a log line.

> **Our take:** adding the gate inside the collector keeps old trust configurations usable, but the `config_id` in the decisions then differs from the file on disk. The log line shows both ids. Freezing the gated configuration (`with_commit_gate(min_chars=1)`) avoids the surprise.

## Related
[NTS specification](nts-spec.md) · [WebSocket input](websocket-input.md) · [LSL input](lsl-input.md) · [streaming trust layer](streaming-trust-layer.md) · [provenance ledger](provenance-ledger.md) · [conformance suite](conformance-suite.md) · [roadmap P3](../questions/roadmap-standard.md#p3-collector-pipeline)
