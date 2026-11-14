---
title: WebSocket input and output (FEP-0004 adapter)
type: concept
tags: [websocket, streaming, real-time, adapter, trust, neuraltextstream, browser, m6]
sources: [neural-input-landscape-2026]
updated: 2026-11-13
---

# WebSocket input and output (FEP-0004 adapter)

Diagram: [16-websocket-input.drawio](../diagrams/16-websocket-input.drawio) (rendered in [diagrams/index.html](../diagrams/index.html#s16)).

## What it is
The **WebSocket adapter** (`fidetype.adapters.ws`, task **M6-11**) carries NeuralTextStream (NTS) over WebSocket in both directions. It follows the pattern of the [LSL adapter](lsl-input.md): a source, a runner that feeds the [streaming trust layer](streaming-trust-layer.md), a replay tool and a command line.

| Path | Direction | Content |
|---|---|---|
| `/nts` | decoder → server | NTS events of one stream per connection; the server feeds the trust layer |
| `/decisions` | server → browser | `trust_decision` events (FEP-0001) with `ws_seq`; resumable |
| `/events` | server → monitor | the NTS events after sequencing (a tap; not resumable) |

Why: a browser cannot open an LSL stream. WebSocket is the bidirectional transport that every browser has. A web keyboard, a caregiver display or a remote demo needs it.

The normative rules are the draft [FEP-0004](../../spec/feps/0004-nts-over-websocket.md) (binding `nts-ws/0.1`, subprotocol `nts-ws.0.1`). The spec had only a one-line sketch (v0.1 section 6.3).

## Command line
```
pip install "fidetype[ws]"                       # websockets 17.4 (BSD-3-Clause), pinned
fidetype ws run --config trust.json --decoder greedy [--serve-example] [--token-env VAR]
fidetype ws replay-to-ws stream.jsonl --url ws://127.0.0.1:8765/nts --speed 1 [--batch 8]
fidetype ws subscribe --url ws://127.0.0.1:8765/decisions [--from-seq 1]
```
`run` binds `127.0.0.1:8765` by default. It writes each decision as one JSON line on stdout and publishes it on `/decisions`. `--serve-example` also serves the browser page (`examples/ws-browser/`) and the built TypeScript SDK over plain HTTP. Off localhost, use `--certfile`/`--keyfile` (wss://) or a TLS proxy; `run` warns otherwise.

## The binding in short
| Topic | Rule (FEP-0004 section) |
|---|---|
| Framing | Text messages only; one JSON object each; no NaN / Infinity tokens (3). `ws_batch` carries 1-1024 events with consecutive `ws_seq` (6.4) |
| Handshake | Subprotocol `nts-ws.0.1` (else HTTP 400). First message = NTS header with an optional `ws` record: `binding`, `stream_id`, `resume` (5) |
| Order | `ws_seq` 1, 2, 3 ... on every event. Duplicates dropped. Reorder window 16 events / 0.25 s. A missing number is a **gap** (6) |
| Cut utterance | At a gap or a lost stream: abort the open utterance; also drop the frames up to the next `segment_end` (6.5) |
| Acks, back-pressure | `ws_ack` every 64 events, at `end` and after 0.1 s. Producer window 4096 unacked events. A busy server stops reading (TCP slows the producer); it never drops events (7) |
| Resume | A broken stream waits 10 s. The producer reconnects with `resume: true`; `ws_welcome.seq` = last released event; it resends the rest. A lossless resume gives the same decisions. A newer connection takes over a half-open one (close 4001) (8) |
| Decisions channel | `ws_seq` over the whole channel, no gaps. Ring of 4096 for `from_seq` resume (`missed` if older). Slow subscriber: close 1013, resubscribe. Subscribers check the order and resubscribe on a gap (7) |
| Auth hook | `Authorization: Bearer` or, for browsers, a first `ws_auth` message. Wrong token: close 1008. Tokens never logged or forwarded (9) |
| Clock | Time fields unchanged, producer clock (like FEP-0002 `event_clock = source`). Optional transport stamps `ws_t_sent` / `ws_t_recv`, valid on one host only (11) |

## Parts
| Part | Role |
|---|---|
| `IngestCore` | The input side without I/O: handshake, header, order, gaps, batches, resume, take-over, acks, refusals. Used by the live server and by the conformance profile |
| `WSServer` | `websockets` sync API, one thread per connection; one lock around the core; one ordered item queue; static HTTP routes for the example |
| `WSTrustRunner` | One trust session per stream id; the loss rules; the `ws` provenance record (`server_latency_s`, `e2e_latency_s`) |
| `OutputHub` | Ring buffer + one bounded queue per subscriber |
| `WSProducer`, `replay_to_ws` | Producer with resend-on-resume and the window; test hooks `drop` and `lose` |
| `SubscriberCore`, `subscribe` | Subscriber checks and a reconnecting client |
| TypeScript (`sdk/typescript/src/ws.ts`) | `IngestCore`, `SubscriberCore` and `DecisionSubscriber` (browser client: resubscribe on gaps, `DecisionTracker` decides what to act on) |

## Results
**Equality with the batch path** (tests and experiments; synthetic unless marked):
| Case | Result |
|---|---|
| Simulator streams over WS, single events and batches of 8 | Decision and PolicyInputs equal to the file replay (tests) |
| The connection broken twice inside utterances, then resumed | Equal to the file replay; 2 resumes, 0 aborted (test) |
| Two events never sent | 1 gap; the cut utterance has no decision; the other decisions equal the file replay (test) |
| **B2T '25 test trials (real data):** 816 trials, hypothesis route, frozen config `tcfg-f5ca0020b3b8fce2` (M4-06, our decoder), 14 session days = 14 streams, 4 producers at the same time | 816/816 equal to the in-process streaming replay (exact) and 816/816 equal to the batch harness (action, shown, p_top1, guard risk, set); 82 COMMIT, 734 OFFER; 0 rejected, 0 aborted ([counts](../../experiments/2026-11-13-m6-11-ws/results/b2t-replay.json); the trial files stay outside the repo) |
| Several NTS streams (header ... end, header ... end) in one WebSocket stream | Equal to the file replay (test; found by the B2T run: the producer first refused a later header) |

**Latency** on localhost (`experiments/2026-11-13-m6-11-ws/`, [results](../../experiments/2026-11-13-m6-11-ws/results/latency.md); timing CPU class; the M6-01 streams, config and decoder):
| Run | Equal | Transport p50 / p95 | e2e final p50 / p95 / max | LSL M6-01 e2e final p50 |
|---|---|---|---|---|
| A: frames, real time | 4/4 | 0.25 / 0.38 ms | 1.85 / 4.66 / 5.09 ms | 60.6 ms (merge 50 ms) |
| B: frames, 4× | 12/12 | 0.24 / 0.34 ms | 1.30 / 1.61 / 1.69 ms | 56.3 ms (merge 50 ms); 17.2 ms (merge 10 ms) |
| C: frames, 4×, `ws_batch` of 8 | 12/12 | 0.22 / 0.32 ms | 1.48 / 1.65 / 1.67 ms | — |
| D: hypothesis route, 50 ms pacing | 30/30 | 0.30 / 0.39 ms | 0.75 / 0.97 / 5.50 ms | 3.04 ms |

The /decisions subscriber got every decision in `ws_seq` order; delivery after emission p50 0.24-0.29 ms.

> **Our take:** on one machine, WebSocket is about 10× faster per event than LSL (transport 0.25 vs 3.5 ms). The main gain is the e2e of the final decision: 1.3-1.9 ms against 57-61 ms (LSL, 50 ms merge) or 17 ms (10 ms merge). The reason is structural: one ordered channel needs no merge window, while LSL merges two inlets by time. After the M6-08 fix, LSL e2e is 33-38 ms on a 250 Hz raw stream (not the same run). Batching does not change the e2e of the final decision, because the closing event flushes the batch; but frames inside a batch wait up to 7 frame periods, which matters for incremental decoding. These are loopback numbers in one process; LAN and Wi-Fi (M6-10) are not measured, and `ws_t_sent` is only valid on one host.

## Conformance
Profile `fep-0004`: 37 scenario vectors (20 accept, 17 reject) in `spec/conformance/fep-0004/`. The Python reference and the TypeScript SDK pass all 37 with the same verdict, and agree on 5,550 fuzz mutants (seeds 1-5, `--n 30`). The Rust SDK has no `fep-0004` profile yet; the parity scripts skip it there and say so. See the [conformance suite](conformance-suite.md).

Found while writing the vectors: without the "drop the tail" rule, the frames after a gap formed a new, partial utterance, and the trust layer decided on it. A cut text could then be committed. FEP-0004 section 6 rule 5 and the runner now drop those frames.

## CI
The `dev` extra includes `[ws]`, so CI installs `websockets` and runs the integration tests (real server and client on localhost, OS-chosen ports). Without `websockets` they skip; the sans-IO tests and the vectors need no library.

## Limits and open items
- Localhost only. LAN / Wi-Fi resume and latency: M6-10.
- No clock sync across hosts (FEP-0004 open question 2).
- No back channel for a user selection after OFFER (open question 1).
- The token check is a shared secret only; real deployments need their own auth.
- The browser example needs `npm run build` in `sdk/typescript` first (the SDK `dist/` is not committed).

## Related
[LSL input](lsl-input.md) · [streaming trust layer](streaming-trust-layer.md) · [TypeScript SDK](typescript-sdk.md) · [conformance suite](conformance-suite.md) · [streaming trust events (FEP-0001)](streaming-trust-events.md)
