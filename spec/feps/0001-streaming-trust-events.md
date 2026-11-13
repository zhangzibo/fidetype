# FEP-0001: Streaming trust events

| | |
|---|---|
| **FEP** | 0001 |
| **Title** | Streaming trust events: segment boundary, n-best evidence fields, trust decisions |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft |
| **Type** | Spec change (additive, Development) |
| **Affects** | `neuraltextstream-v0.1.md` sections 3.6, 6.2 and open question 5 (section 10) |
| **Created** | 2026-11-12 |
| **Discussion** | M4-03 (streaming trust layer), `src/fidetype/trust/streaming.py` |

## Summary
This FEP adds three optional parts to the JSON Lines form (6.2): a `segment_end` event that closes an utterance, three optional fields on `hypothesis` n-best items (`char_confidences`, `logp_acoustic`, `logp_lm`), and a `trust_decision` output event. All three are additive. A v0.1 consumer ignores the new event types (6.2 rule 5) and the new keys (5.1). No v0.1 stream becomes invalid.

## Motivation
The streaming trust layer (`fidetype.trust.streaming.StreamingTrustLayer`) consumes events as they arrive. It found three gaps in v0.1:

1. **No utterance boundary.** A live stream can carry many sentences. v0.1 has only `end` (end of the whole stream) and leaves segment boundaries open (section 10, question 5). The trust layer must know when the user finished one sentence, because it decides once per sentence.
2. **Hypotheses lack evidence.** The hallucination guard compares the language model with the neural evidence per character. A `hypothesis` item has only `text`, `score` and `spans`. Span scores have no defined meaning. So a hypothesis-only producer cannot feed the guard, and the guard then sees "no evidence" for every character.
3. **No form for trust output.** A trust layer emits commit / offer / ask / abstain decisions. A downstream bridge (for example the Apple BCI HID bridge, 6.5) must send only committed text. It needs a standard event that says which decision is final and what the calibrated confidence is.

## Proposal

### 1. `segment_end` event (Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"segment_end"` | Yes | |
| `t` | float | No | Signal time of the boundary, in seconds |
| `unit` | string | No | `utterance` (default), `word` or `trial` |

Rules:
1. A producer MAY send `segment_end` after the last event of a segment.
2. A consumer that decides per segment MUST treat all events between two boundaries (or between the header and the first boundary) as one segment.
3. `end` also closes the open segment.
4. A segment with no frame and no hypothesis carries no input. A consumer SHOULD NOT emit a decision for it.

### 2. Evidence fields on `hypothesis` n-best items (Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `char_confidences` | list of numbers in [0, 1] | No | One value per character of `text`: the posterior of that character under the neural evidence only (no language model) |
| `logp_acoustic` | number | No | Log-probability of `text` under the neural evidence only |
| `logp_lm` | number | No | Log-probability of `text` under the language model only |

Rules:
1. If present, `char_confidences` MUST have exactly `len(text)` values (Unicode code points).
2. A producer MUST NOT put a language-model-fused value in `char_confidences`. The field exists so that a consumer can compare the two sources.
3. `score` of each item MUST be a finite number when the item is meant for a trust layer.

### 3. `trust_decision` event (Development)
A trust layer MAY emit its decisions as events of the same JSON Lines form (for example, into a log or a downstream bridge).

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"trust_decision"` | Yes | |
| `is_final` | boolean | Yes | `false`: a provisional preview |
| `action` | string | Yes | `COMMIT`, `OFFER`, `ASK`, `ABSTAIN` or `OFFER_WORDS` |
| `shown` | list of strings | No | The text(s) shown to the user. Omit in privacy-sensitive logs |
| `p_top1` | number or null | Yes | Confidence of the top candidate |
| `score_semantics` | string | Yes | As in 3.5. A calibrated trust layer uses `calibrated_prob` |
| `set_size`, `guard_risk` | number | No | Conformal set size and guard risk in [0, 1] |
| `session`, `seq`, `utterance` | string, int, int | No | Order within a session |
| `config_id` | string | No | Content id of the trust configuration that made the decision |
| `input` | object | No | Reference to the input: frame range and stream SHA-256, or hypothesis id and SHA-256 |
| `latency_s` | number | No | Computation time of the decision |

Rules:
1. **A consumer MUST NOT act on (commit, send, actuate) a `trust_decision` with `is_final = false`.**
2. `score_semantics = "calibrated_prob"` follows rule 3 of section 3.5: a calibration step must have run.
3. A bridge to a lossy output (6.5) SHOULD forward only final `COMMIT` decisions, or a user selection after `OFFER`.
4. `trust_decision` events are output. They MUST NOT appear in a stream that is fed back as decoder input.

## Examples
Input with two utterances and a hypothesis with evidence:
```json
{"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a", "b", " "], "vocab_type": "char", "blank_id": 0, "source": "my-decoder"}
{"type": "hypothesis", "id": "h1", "is_final": false, "score_semantics": "none", "nbest": [{"text": "ab", "score": -1.2, "char_confidences": [0.91, 0.40]}]}
{"type": "hypothesis", "id": "h2", "revision_of": "h1", "is_final": true, "score_semantics": "none", "nbest": [{"text": "ab", "score": -1.0, "char_confidences": [0.93, 0.88], "logp_acoustic": -2.1, "logp_lm": -3.0}, {"text": "a", "score": -2.4}]}
{"type": "segment_end", "t": 1.2}
{"type": "end"}
```
Output of the trust layer:
```json
{"type": "trust_decision", "session": "u1", "seq": 0, "utterance": 0, "is_final": false, "action": "OFFER", "reason": "conformal set of 1 <= 3", "p_top1": 0.71, "score_semantics": "calibrated_prob", "set_size": 1, "guard_risk": 0.5, "config_id": "tcfg-0123456789abcdef"}
{"type": "trust_decision", "session": "u1", "seq": 1, "utterance": 0, "is_final": true, "action": "COMMIT", "reason": "p_top1 0.93 >= 0.90", "p_top1": 0.93, "score_semantics": "calibrated_prob", "set_size": 1, "guard_risk": 0.12, "config_id": "tcfg-0123456789abcdef", "input": {"kind": "hypothesis", "hypothesis_id": "h2", "revision_of": "h1"}}
```

## Compatibility
- Producers: no change is required. All parts are optional.
- Consumers: a v0.1 consumer ignores `segment_end` and `trust_decision` (6.2 rule 5) and the new item keys. The reference consumer (`fidetype.conformance.io.load_stream`) counts them as ignored events. No golden vector changes.
- Stability: all three parts start at Development.

## Reference implementation
- `fidetype.trust.streaming`: reads `segment_end`, the evidence fields (`nbest_from_hypothesis`) and writes `trust_decision` (`StreamDecision.to_event`). Tests: `tests/test_trust_streaming.py`.
- Not yet done: conformance checks and golden vectors for the three parts (follow-up task), and the change to the reference consumer to read them as known types.

## Alternatives
- **A `meta` key for segment boundaries.** Rejected: `meta` is a header field and cannot mark a point in time.
- **Reuse `decision` (3.5) for trust output.** Rejected: `decision` is decoder output ("the user selected X"). A trust decision has other fields (action, provisional state, set size) and a different producer. Mixing them would let a trust layer read its own output as input.
- **Span scores in place of `char_confidences`.** Rejected for now: span score semantics are undefined, and spans need time ranges that a hypothesis-only producer may not have.

## Privacy and leakage
- `shown` holds decoded text. It is not ground truth (rule 3 of 3.6 applies), but it is personal data. Logs SHOULD omit it or use the provenance ledger's hash mode.
- `segment_end` and the evidence fields hold no text beyond what v0.1 already carries.

## Open questions
1. Should `segment_end` carry an id, so that a `trust_decision` can name the segment it closes?
2. Should a provisional `trust_decision` use a separate action name (for example `PREVIEW`) instead of `is_final = false`?
3. Should `char_confidences` move to a per-hypothesis lattice when lattices arrive (question 3)?
