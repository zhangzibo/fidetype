---
title: Collector (receivers, processors, exporters)
type: concept
tags: [collector, pipeline, standard, p3, privacy, websocket, trust-layer]
sources: []
updated: 2026-11-14
---

# Collector

The collector is one service that takes NeuralTextStream (NTS) input from several sources, runs processors on it, and sends the results to several targets. One configuration file wires it. It is the P3 part of the "OpenTelemetry for neural input" plan ([roadmap P3](../questions/roadmap-standard.md#p3-collector-pipeline)). The design is in the draft [FEP-0006](../../spec/feps/0006-collector.md). The code is `src/fidetype/collector/` (v0, 2026-11-14).

```
 file  ----> receiver --\                                         /--> jsonl (decision log)
 ws /nts --> receiver ---+--> validate --> trust --> thin --> redact --+--> stdout
                                                                  \--> ws /decisions
             GET /healthz, GET /metrics (JSON)
```

## Model
| Part | Job | v0 components |
|---|---|---|
| Receiver | Read a source. Give `(stream id, event)` items in order. Turn a loss into a status item (`gap`, `lost`) | `file` (JSON Lines, tail mode), `websocket` (FEP-0004 `/nts`) |
| Processor | Change or replace items. Keep state per stream | `validate`, `trust`, `redact`, `thin` |
| Exporter | Write items out. Never change them | `jsonl`, `stdout`, `websocket` (FEP-0004 `/decisions`) |
| Pipeline | Connect named receivers, processors, exporters | any number |
| Service | Run loop, stop, metrics file, health endpoint | `fidetype collector --config <file>` |

The idea comes from the OpenTelemetry Collector (receivers → processors → exporters, pipelines, one configuration). The text and the code are our own.

## What v0 reuses (no copies)
| Collector part | Wraps |
|---|---|
| `websocket` receiver and exporter | `fidetype.adapters.ws.WSServer`, `OutputHub` ([WebSocket input](websocket-input.md)) |
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

Loss paths that give no final decision on the open utterance (all tested): an unreadable line, an invalid frame, a WebSocket `ws_seq` gap, `eof = "cut"`, a tail-mode idle time-out, a stop while an utterance is open.

## Configuration
TOML or JSON (PyYAML is not a dependency). Example: [`examples/collector/collector.toml`](../../examples/collector/collector.toml). `fidetype collector --config <file> --check` checks a file and prints the pipelines. Errors name the bad value, for example `pipelines.main.processors[1]: unknown processor 'trsut' (known: check, trust)`.

## Tests (2026-11-14)
`tests/test_collector.py`, 29 tests:
- File → validate → trust → jsonl gives the same decisions as `fidetype trust` (the reference replay) on a synthetic 4-utterance stream.
- `redact` drop: no committed text appears in the log file. `redact` hmac: `shown_hmac` equals the HMAC of the reference text; the key is not in the file.
- Cut segments: the five loss paths above give no final decision on the cut utterance; the other utterances keep theirs.
- WebSocket in and `/decisions` out: the same decisions as the reference, with `ws_seq` 1, 2, 3 on the channel.
- 11 configuration errors give messages that name the value. Command line exit codes (0, 2).

## What v0 does not do
- No LSL receiver or LSL decisions exporter yet (the [LSL adapter](lsl-input.md) exists; the wrapper is next).
- No gRPC, OTLP, Arrow or Parquet. No OS input-method exporter, no Apple BCI HID bridge, no AAC API (P3-03).
- No per-user calibration, LM rescoring, segmenter or rate limiter (P3-02, P5).
- Text profile only in the trust processor (intent and control layers are separate tools).
- No latency budget measurement yet (P3-04, target < 50 ms added).
- One process, one loop thread. No hot reload, no fan-out of one receiver to two pipelines, no plug-in registry.
- The health endpoint has no authentication; keep it on `localhost`.
- Decisions carry no `spec_version` (they follow the 0.1 rules, as the trust layer does).
- The example trust configuration is a toy (not calibrated). It shows the wiring only.

> **Our take:** v0 meets the first half of the P3 exit criterion ("one configuration: replay → trust → file and WebSocket exporters") on synthetic data. It does not yet meet the other half (an OS input exporter that types on Windows, a measured latency budget). The item model `(stream id, event)` plus status items is small and language-neutral, so a later Rust collector can keep the same configuration and the same tests.

## Open questions (FEP-0006)
YAML as an optional extra; Python or Rust for v1; the stream-id prefix with several receivers; auth for the health endpoint; `spec_version` on decisions; fan-out; `close` or `cut` as the default for a file without `end`; a standalone `/decisions` server.

## Related
[NTS specification](nts-spec.md) · [WebSocket input](websocket-input.md) · [LSL input](lsl-input.md) · [streaming trust layer](streaming-trust-layer.md) · [provenance ledger](provenance-ledger.md) · [conformance suite](conformance-suite.md) · [roadmap P3](../questions/roadmap-standard.md#p3-collector-pipeline)
