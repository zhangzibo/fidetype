---
title: The trust_decision event
type: concept
tags: [spec, nts, trust-layer, event, decision, safety, td-9]
sources: []
updated: 2026-11-14
---

# The `trust_decision` event

A `trust_decision` is the **output event of a trust layer**. A decoder writes a NeuralTextStream (NTS). A trust layer reads it and writes one `trust_decision` per decision: what to do with the decoded text, intent or control. A consumer (an app, a bridge to a keyboard) acts only on these events. The event came from [FEP-0001](../../spec/feps/0001-streaming-trust-events.md) and is section 6 of [NTS 1.0 RC2](../../spec/nts-1.0-rc2.md#6-trust-decisions).

```
decoder --NTS frames / hypotheses--> trust layer --trust_decision--> consumer (app, bridge)
                                          |
                                          +--> decision log (JSON Lines), LSL fidetype.decisions, WebSocket /decisions
```

## Fields (RC2 section 6.1)
| Field | Required | Meaning |
|---|---|---|
| `type` | yes | `"trust_decision"` |
| `spec_version` | yes for 1.0 producers | Rule version. Absent means `"0.1"` |
| `profile` | no | `text` (default), `intent`, `control` |
| `is_final` | yes | `false` = provisional preview |
| `action` | yes | `COMMIT`, `OFFER`, `ASK`, `ABSTAIN`, `OFFER_WORDS` (intent and control use a subset) |
| `shown` | no | Texts shown to the user. For `COMMIT`, `shown[0]` is the committed text |
| `p_top1` | yes | Confidence of the top candidate, in [0, 1] or null |
| `score_semantics` | yes | For example `calibrated_prob` |
| `set_size`, `guard_risk` | no | Conformal set size; guard risk |
| `session`, `seq`, `utterance` | no | Order within a session |
| `config_id`, `input`, `latency_s`, `declaration`, `reason` | no | Trust configuration id, input reference (frame range + stream SHA-256), compute time, declaration check result, short reason |

## Main rules (RC2 sections 6.2–6.4)
| Rule | Content |
|---|---|
| TD-1 | A consumer MUST NOT act on a decision with `is_final = false` |
| TD-4 | Decisions are output. They MUST NOT be fed back as decoder input |
| TD-5, TD-6, TD-7 | `seq` increases strictly per session; at most one final decision per (`session`, `utterance`); nothing after the final decision |
| TD-9 | (stricter in 1.0) A 1.x trust layer MUST NOT emit a final text `COMMIT` with blank committed text. It uses `ABSTAIN`. For `spec_version` `"0.1"` the old SHOULD NOT stays |
| TD-10 | A log or channel MAY omit `shown` for privacy |
| TD-11 | A decision log holds only `trust_decision` lines |
| TD-12 | (new in RC2) A 1.x layer SHOULD NOT offer blank candidates; a consumer MUST drop them |

The reason for TD-9, as the spec gives it: in M2-18 the frozen Paper 1 v4 configuration committed 320 empty texts on 400 no-signal T12 control streams ([RC2 section 6.3](../../spec/nts-1.0-rc2.md#63-semantic-rules-all-profiles-unless-a-profile-says-otherwise)). The fix is the opt-in commit gate of the [streaming trust layer](streaming-trust-layer.md). The gate only removes commits, so a fitted risk bound ([CRC](conformal-risk-control.md), [LTT](learn-then-test.md)) still holds.

## Who writes and reads it
| Component | Role | Page |
|---|---|---|
| `StreamingTrustLayer` | Writes final and provisional decisions | [streaming trust layer](streaming-trust-layer.md) |
| Collector `trust` processor | Writes decisions stamped `spec_version` 1.0 with the commit gate | [collector](collector.md) |
| LSL and WebSocket bindings | Carry decisions (`fidetype.decisions` outlet, `/decisions` channel) | [LSL input](lsl-input.md), [WebSocket](websocket-input.md) |
| Python, TypeScript, Rust SDKs | Validate decisions; `DecisionTracker` applies the rules | [Python SDK](python-sdk.md), [TypeScript SDK](typescript-sdk.md), [Rust SDK](rust-sdk.md) |
| Provenance ledger | One record per final decision (PRV-1 … PRV-3) | [provenance ledger](provenance-ledger.md) |
| Conformance profile `fep-0001` | Golden vectors for the rules | [conformance suite](conformance-suite.md) |

Intent and control profiles reuse the event with their own fields ([intent events](intent-events.md), [control events](control-events.md)).

> **Our take:** `trust_decision` is the part of NTS that makes Fidetype more than a file format. It is the one place where "the system understood you" becomes a contract. TD-1 (no action on a preview) and TD-9 (no blank commit) are the two rules a bridge author must not get wrong.

## Related
- [NTS specification](nts-spec.md)
- [FEP process](fep-process.md)
