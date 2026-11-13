---
title: Streaming trust layer
type: concept
tags: [trust, streaming, real-time, provenance, risk-control, neuraltextstream, m4]
sources: []
updated: 2026-11-12
---

# Streaming trust layer

Diagram: [12-streaming-trust-layer.drawio](../diagrams/12-streaming-trust-layer.drawio) (rendered in [diagrams/index.html](../diagrams/index.html#s12)).

## What it is
The batch trust core reads a complete stream and selects one action. A live system gets the stream one event at a time. The **streaming trust layer** (`fidetype.trust.streaming.StreamingTrustLayer`, task **M4-03**) reads NeuralTextStream events as they arrive. It keeps a state per session. It emits commit / offer / ask / abstain decisions with provenance.

It runs a **frozen configuration**: the fitted state of the trust core, loaded from one JSON file (`fidetype.trust.frozen.FrozenTrustConfig`). So the live system uses exactly the thresholds that were calibrated, without the calibration data.

## API

| Call | What it does |
|---|---|
| `FrozenTrustConfig.from_pipeline(pipe, name, recipe)` | Freeze a fitted `TrustPipeline`: frame, sentence and character temperatures, conformal q, guard settings, policy thresholds, risk-control record |
| `cfg.save(path)` / `FrozenTrustConfig.load(path)` | Canonical JSON. `inf` and `nan` are written as strings. `cfg.config_id` = SHA-256 content id |
| `paper1_v4_harness_config()` | Harness settings of the Paper 1 frozen recipe (guard on, LTT α 0.05, δ 0.1, combine max). Fit on the user's calibration data, then freeze |
| `StreamingTrustLayer(cfg, decode_fn=None, streaming=StreamingConfig(), online=None, ledger=None)` | The layer. `decode_fn(stream) -> NBest` selects the frames route; without it the layer uses the hypothesis route |
| `layer.push(event, session_id)` | Consume one event (dict or JSON string). Returns the decisions it causes, often none |
| `layer.end_of_utterance(session_id, final_attempt=None)` | Close the utterance when the producer sends no boundary |
| `layer.flush()`, `layer.close(sid)`, `layer.new_item(sid)` | End all pending utterances; drop a session; reset the attempt count |
| `layer.feedback(decision, truth)` | The user's final text (or None). Feeds the online controller and writes a ledger correction |
| `replay(path, layer)`, `iter_events(path)` | File (JSON Lines or NPZ) → events → layer |
| `python -m fidetype.trust.streaming replay --config trust.json [--decoder greedy] files...` | Print `trust_decision` events as JSON Lines |

Each `StreamDecision` has `final`, `action`, `shown`, `inputs` (p_top1, conformal set, guard risk), `attempt`, `final_attempt`, `ticket` (online only) and `provenance`.

## Two input routes

| Route | Input | When does the layer decide? | Cost of the final decision |
|---|---|---|---|
| `frames` | `frame` events (dense or sparse) | At the end of the utterance: it builds the stream, applies the frozen frame temperature, calls `decode_fn`, runs the trust core | One decode of the utterance |
| `hypothesis` | `hypothesis` events (n-best lists) | Partial hypothesis → provisional decision. Final hypothesis → final decision at once | Trust core only |

An utterance ends at a final hypothesis, a `segment_end` event, an `end` event, a new header, or `end_of_utterance()`. An utterance with no input gives no decision.

**Rule: a consumer must not act on a provisional decision.** It can show it as a preview. Only a final decision is an action.

## State and bounds

| Item | Bound |
|---|---|
| Frame rows | Current utterance only, at most `max_frames` (default 15 000 = 10 min at 40 ms). A longer utterance gives a final ABSTAIN ("input too long") |
| Hypotheses | The latest one only (`revision_of` replaces) |
| Sessions | At most `max_sessions` (default 256) |
| Feedback tickets | At most `max_pending_feedback` per session; the oldest is closed as "feedback missing" |
| Work per frame | O(V): checks and one append |
| Provisional decodes (frames route) | Every `partial_every_frames` frames, off by default |
| Latency budget | `latency_budget_s` flags a slow decision in its provenance. It does not change the decision, so replay stays deterministic |

Bad events (frame before header, time that does not increase, a row that does not sum to 1, NaN, unknown vocab type, bad `blank_id`) raise `StreamEventError`. The session state does not change. Lines after `end` are ignored (spec ambiguity A5).

## Attempts
The policy needs `final_attempt`, because ASK is not possible on the last attempt. The session counts attempts. After a final ASK, the next utterance is the next attempt of the same item. After any other final action, the count goes back to 0. `max_attempts` defaults to 2, as in the harness.

## Online re-calibration
Pass an `OnlineCommitRiskControl` ([conformal risk control](conformal-risk-control.md), M2-16) as `online`. Each session gets its own copy. Final decisions then carry a ticket. `feedback()` closes it. With `online_floor=True` (default), the frozen `commit_p` is the floor (`lam_min`) of the online threshold. So the online loop can make the gate stricter than the frozen configuration, never looser.

> **Our take:** the floor keeps the Paper 1 guarantee (LTT on the calibration half) as the minimum. The online loop adds protection against drift inside the session. It cannot remove the offline protection.

## Provenance
Each decision carries: `config_id`, session, utterance, route, the input reference (frame range, time range and the SHA-256 of the raw stream; or the hypothesis id, `revision_of` and its SHA-256), the event range, the commit threshold in effect and the computation time. With a [provenance ledger](provenance-ledger.md), each final decision is also a hash-chained ledger entry. One context entry per session holds the full frozen configuration. `feedback()` writes the linked correction.

## Equivalence with the batch path
On the same input, the final decision equals the batch decision (`TrustPipeline.analyze` + `policy.decide`) exactly: the same action, shown texts, reason, p_top1, conformal set and guard score. `tests/test_trust_streaming.py` checks this:

| Input | Result |
|---|---|
| 20 synthetic streams × 3 configurations (plain fit, Paper 1 recipe, Paper 1 recipe with a looser gate) × 2 file forms (JSON Lines, NPZ) | All equal |
| Two utterances in one stream (`segment_end`), 3 interleaved sessions, provisional decodes every 10 frames | Final decisions equal |
| Hypothesis route, 8 streams (partial then final hypothesis) | All equal |
| Conformance golden vectors, every `accept` vector | Equal (empty streams give no decision); frame-core `reject` vectors raise |

## Latency (synthetic, CPU)
`experiments/2026-11-12-m4-streaming/bench_latency.py`; numbers in [results/latency.md](../../experiments/2026-11-12-m4-streaming/results/latency.md). 100 simulator utterances, mean 453 frames, V = 28.

| Path | p50 | p95 | p99 | Equal to batch |
|---|---|---|---|---|
| `push(frame)` | 0.008 ms | 0.014 ms | 0.016 ms | |
| End → final decision, reference beam decoder | 8.1 ms | 11.1 ms | 14.0 ms | 100/100 |
| End → final decision, greedy decoder | 0.72 ms | 1.08 ms | 1.39 ms | 100/100 |
| `push(hypothesis)` (trust core only) | 0.19 ms | 0.32 ms | 0.46 ms | 100/100 |

64 interleaved sessions: about 28 000 events/s on one core; tracemalloc peak 8.7 MB. Peak frame buffer per session: 124 kB.

> **Our take:** the trust layer adds well under 1 ms on the hypothesis route. On the frames route the decoder dominates the latency. The trust layer is not the bottleneck for real-time text entry. All synthetic decisions were OFFER (the synthetic gate is strict); the tests cover the other actions.

## Spec additions (proposal, not breaking v0.1)
[FEP-0001](../../spec/feps/0001-streaming-trust-events.md) proposes three Development parts: a `segment_end` event (open question 5 of the spec), optional evidence fields on hypothesis items (`char_confidences`, `logp_acoustic`, `logp_lm`) so that the guard works on the hypothesis route, and a `trust_decision` output event with the rule "do not act on `is_final = false`". A v0.1 consumer ignores all three.

## Limits and follow-ups
- The frames route decodes the whole utterance at its end. A truly incremental decoder (prefix beam state carried across frames) is M4-01 (causal mode).
- No frozen configuration fitted on real data is committed yet. Fit the Paper 1 recipe per user and session, then freeze it (follow-up M4-06).
- FEP-0001 needs conformance checks and golden vectors (follow-up M4-07).
- An LSL / WebSocket input adapter for live use is M6-01.

## Related
[Provenance ledger](provenance-ledger.md) · [Conformal risk control](conformal-risk-control.md) · [Conformance suite](conformance-suite.md) · [Synchronous vs asynchronous decoding](synchronous-vs-asynchronous-decoding.md) · [Architecture](../questions/architecture.md) · [Standard roadmap](../questions/roadmap-standard.md) · [Lab Streaming Layer](../entities/lab-streaming-layer.md)
