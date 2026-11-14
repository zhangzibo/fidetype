# FEP-0001: Streaming trust events

| | |
|---|---|
| **FEP** | 0001 |
| **Title** | Streaming trust events: segment boundary, n-best evidence fields, decode declaration, trust decisions |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft |
| **Type** | Spec change (additive, Development) |
| **Affects** | `neuraltextstream-v0.1.md` sections 3.6, 6.2 and open question 5 (section 10) |
| **Created** | 2026-11-12 |
| **Updated** | 2026-11-13 (M2-18: rule 9, empty committed text); 2026-11-12 (M4-07: decode declaration, rules made testable, conformance profile `fep-0001`) |
| **Discussion** | M4-03 (streaming trust layer), M4-06 (real-data replay), M4-07 (conformance); `src/fidetype/trust/streaming.py` |

## Summary
This FEP adds four optional parts to the JSON Lines form (6.2):

1. a `segment_end` event that closes an utterance;
2. three optional evidence fields on `hypothesis` n-best items (`char_confidences`, `logp_acoustic`, `logp_lm`);
3. a `trust_decision` output event;
4. a `decode_declaration` object (in the header or on a `hypothesis` event) that says which decoder made the hypotheses, with which parameters and frame temperature, and for which trust configuration.

All four are additive. A v0.1 consumer ignores the new event types (6.2 rule 5) and the new keys (5.1). No v0.1 stream becomes invalid. The opt-in conformance profile `fep-0001` tests every rule below (section "Conformance").

## Motivation
The streaming trust layer (`fidetype.trust.streaming.StreamingTrustLayer`) consumes events as they arrive. It found four gaps in v0.1:

1. **No utterance boundary.** A live stream can carry many sentences. v0.1 has only `end` (end of the whole stream) and leaves segment boundaries open (section 10, question 5). The trust layer must know when the user finished one sentence, because it decides once per sentence.
2. **Hypotheses lack evidence.** The hallucination guard compares the language model with the neural evidence per character. A `hypothesis` item has only `text`, `score` and `spans`. Span scores have no defined meaning. So a hypothesis-only producer cannot feed the guard, and the guard then sees "no evidence" for every character.
3. **No form for trust output.** A trust layer emits commit / offer / ask / abstain decisions. A downstream bridge (for example the Apple BCI HID bridge, 6.5) must send only committed text. It needs a standard event that says which decision is final and what the calibrated confidence is.
4. **The layer cannot see how a hypothesis was made.** A frozen trust configuration is valid only with the decoding it was fitted on. On the hypothesis route the producer decodes, so the producer must apply the frozen frame temperature before it decodes. In M4-06 (B2T '25 replay, `experiments/2026-11-13-m4-06-real-replay/results.md`) the layer could not check this. A wrong temperature or a different decoder changes the calibrated confidence, and the layer would commit on a confidence that its calibration does not cover.

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
5. If present, `t` MUST be a finite number. It MUST NOT be less than the `t` of the last frame of the segment.

### 2. Evidence fields on `hypothesis` n-best items (Development)
| Field | Type | Required | Description |
|---|---|---|---|
| `char_confidences` | list of numbers in [0, 1] | No | One value per character of `text`: the posterior of that character under the neural evidence only (no language model) |
| `logp_acoustic` | number | No | Log-probability of `text` under the neural evidence only |
| `logp_lm` | number | No | Log-probability of `text` under the language model only |

Rules:
1. If present, `char_confidences` MUST have exactly `len(text)` values, counted in Unicode code points (not UTF-16 code units, not bytes).
2. A producer MUST NOT put a language-model-fused value in `char_confidences`. The field exists so that a consumer can compare the two sources.
3. `score` of each item MUST be a finite number when the item is meant for a trust layer.
4. If present, `logp_acoustic` and `logp_lm` MUST be finite numbers <= 0 (they are log-probabilities).

### 3. `trust_decision` event (Development)
A trust layer MAY emit its decisions as events of the same JSON Lines form (for example, into a log or a downstream bridge).

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"trust_decision"` | Yes | |
| `is_final` | boolean | Yes | `false`: a provisional preview |
| `action` | string | Yes | `COMMIT`, `OFFER`, `ASK`, `ABSTAIN` or `OFFER_WORDS` |
| `shown` | list of strings | No | The text(s) shown to the user. For `COMMIT`, `shown[0]` is the committed text. Omit in privacy-sensitive logs |
| `p_top1` | number in [0, 1] or null | Yes | Confidence of the top candidate |
| `score_semantics` | string | Yes | As in 3.5. A calibrated trust layer uses `calibrated_prob` |
| `set_size` | integer >= 0 | No | Conformal set size |
| `guard_risk` | number in [0, 1] or null | No | Guard risk |
| `session`, `seq`, `utterance` | string, integer >= 0, integer >= 0 | No | Order within a session |
| `config_id` | string | No | Content id of the trust configuration that made the decision |
| `input` | object | No | Reference to the input: frame range and stream SHA-256, or hypothesis id and SHA-256 |
| `latency_s` | number >= 0 | No | Computation time of the decision |
| `declaration` | object | No | Result of the decode-declaration check (section 4): `status` (`match`, `mismatch`, `absent`), `mode`, `where`, `decoder`, `mismatches` |

Other keys (for example `reason`, `attempt`, `final_attempt`, the LSL record `lsl` of FEP-0002) are allowed. A consumer ignores keys it does not know.

Rules:
1. **A consumer MUST NOT act on (commit, send, actuate) a `trust_decision` with `is_final = false`.**
2. `score_semantics = "calibrated_prob"` follows rule 3 of section 3.5: a calibration step must have run.
3. A bridge to a lossy output (6.5) SHOULD forward only final `COMMIT` decisions, or a user selection after `OFFER`.
4. `trust_decision` events are output. They MUST NOT appear in a stream that is fed back as decoder input. A decision log is a JSON Lines file in which every line is a `trust_decision` (no header).
5. Within one `session`, `seq` MUST increase strictly and `utterance` MUST NOT decrease.
6. A trust layer MUST emit at most one final decision per (`session`, `utterance`).
7. A trust layer MUST NOT emit any decision for an utterance after its final decision. (After a final `ASK`, the retry is a new utterance.)
8. A `COMMIT` that carries `shown` MUST have at least one text in it.
9. A trust layer SHOULD NOT emit a final `COMMIT` whose committed text (`shown[0]`) is empty or only white space. To show no text, it uses `ABSTAIN`. If a layer emits such a `COMMIT`, its `reason` SHOULD say why. A bridge to a lossy output (6.5) SHOULD NOT forward an empty committed text. *Why (M2-18):* in a dry run on participant T12 the Paper 1 v4 configuration committed 320 empty texts on 400 no-signal (uniform) control streams (`experiments/2026-11-13-m2-18-empty-commits/results.md`). An empty COMMIT tells the user "the system understood you" when no text came from the neural evidence. The reference layer can enforce this rule with the opt-in commit gate (`FrozenTrustConfig.commit_gate`, `fidetype.trust.content`). This rule is a SHOULD, not a MUST, because frozen configurations made before M2-18 (Paper 1 v4) can still emit an empty `COMMIT`; the conformance profile does not check it yet (open question 6).

### 4. `decode_declaration` (Development)
A JSON object in the header (it applies to the whole stream) or on a `hypothesis` event (it applies to that event only).

| Field | Type | Required | Description |
|---|---|---|---|
| `decoder` | string | Yes | Id of the decoder that made the n-best list (for example `acme-beam`) |
| `decoder_version` | string | No | Version of that decoder |
| `frame_temperature` | number > 0 | No | The temperature T that the producer applied to the frame log-probabilities before it decoded: `log_softmax(log_probs / T)`. Absent means 1.0 (no scaling) |
| `params` | object | No | Other decode parameters (for example `beam`, `lm_weight`, `lm`) |
| `config_id` | string | No | Content id of the frozen trust configuration that the producer decoded for |

Example: `"decode_declaration": {"decoder": "acme-beam", "decoder_version": "2.1", "frame_temperature": 1.37, "params": {"beam": 16, "lm_weight": 0.8}, "config_id": "tcfg-f5ca0020b3b8fce2"}`.

Rules:
1. A producer that sends `hypothesis` events for a trust layer SHOULD send a `decode_declaration`.
2. A declaration on a `hypothesis` event replaces the header declaration for that event. The two objects are not merged.
3. A producer that decodes for a frozen trust configuration MUST apply the frozen frame temperature of that configuration before it decodes, and MUST declare it in `frame_temperature`.
4. A trust layer that reads declarations MUST compare the declaration of each hypothesis with its configuration:
   - `config_id`, if declared, MUST equal the layer's configuration id;
   - `frame_temperature` (default 1.0) MUST equal the configuration's frozen frame temperature (relative tolerance 1e-9);
   - `decoder`, `decoder_version` and each key of `params` MUST equal the values that the layer requires, if it requires any.
5. On a mismatch the layer MUST record it in the decision (the `declaration` field of `trust_decision`, or its provenance). It SHOULD give `ABSTAIN`. A layer MAY run in a record-only mode (for migration); it MUST then still record the mismatch.
6. A layer MAY treat a missing declaration as a mismatch.
7. On the frames route the layer decodes itself (with its own decoder and the frozen temperature). The declaration does not apply there.
8. A declaration is a claim of the producer. The layer cannot prove it. It catches configuration mistakes, not a dishonest producer.

## Examples
Input with a declaration, two utterances and a hypothesis with evidence:
```json
{"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a", "b", " "], "vocab_type": "char", "blank_id": 0, "source": "my-decoder", "decode_declaration": {"decoder": "my-beam", "frame_temperature": 1.25, "config_id": "tcfg-0123456789abcdef"}}
{"type": "hypothesis", "id": "h1", "is_final": false, "score_semantics": "none", "nbest": [{"text": "ab", "score": -1.2, "char_confidences": [0.91, 0.40]}]}
{"type": "hypothesis", "id": "h2", "revision_of": "h1", "is_final": true, "score_semantics": "none", "nbest": [{"text": "ab", "score": -1.0, "char_confidences": [0.93, 0.88], "logp_acoustic": -2.1, "logp_lm": -3.0}, {"text": "a", "score": -2.4}]}
{"type": "segment_end", "t": 1.2}
{"type": "end"}
```
Output of the trust layer (a decision log):
```json
{"type": "trust_decision", "session": "u1", "seq": 0, "utterance": 0, "is_final": false, "action": "OFFER", "reason": "conformal set of 1 <= 3", "p_top1": 0.71, "score_semantics": "calibrated_prob", "set_size": 1, "guard_risk": 0.5, "config_id": "tcfg-0123456789abcdef", "declaration": {"status": "match", "mode": "warn", "where": "header", "decoder": "my-beam"}}
{"type": "trust_decision", "session": "u1", "seq": 1, "utterance": 0, "is_final": true, "action": "COMMIT", "shown": ["ab"], "reason": "p_top1 0.93 >= 0.90", "p_top1": 0.93, "score_semantics": "calibrated_prob", "set_size": 1, "guard_risk": 0.12, "config_id": "tcfg-0123456789abcdef", "input": {"kind": "hypothesis", "hypothesis_id": "h2", "revision_of": "h1"}, "declaration": {"status": "match", "mode": "warn", "where": "header", "decoder": "my-beam"}}
```
A bridge acts on the second line only.

## Compatibility
- Producers: no change is required. All parts are optional.
- Consumers: a v0.1 consumer ignores `segment_end` and `trust_decision` (6.2 rule 5) and the new keys. The reference v0.1 consumer (`fidetype.conformance.io.load_stream`) counts the new events as ignored events. The 52 v0.1 golden vectors do not change.
- Stability: all four parts start at Development.

## Conformance
Profile `fep-0001` (opt-in, `src/fidetype/conformance/profiles/fep0001.py`). Golden vectors: [`spec/conformance/fep-0001/`](../conformance/fep-0001/) (`manifest.json`; 40 JSON Lines files: 12 accept, 28 reject).

```
fidetype conformance --profile fep-0001                          # reference consumer over the vectors
fidetype conformance consumer --profile fep-0001 --cmd "my-reader {path}"
fidetype conformance check --profile fep-0001 decisions.jsonl    # producer check (input stream or decision log)
fidetype conformance vectors --profile fep-0001 --out DIR
```

| Check | Rules | Vectors (accept / reject) |
|---|---|---|
| `FEP1-PARSE`, `FEP1-KIND` | 6.2 (v0.1); section 3 rule 4 | F39 |
| `FEP1-V01-CORE` | Compatibility: an input stream also passes the v0.1 core level | F40 |
| `FEP1-SEGMENT` | section 1 table, rule 5 | F01-F03 / F04-F06 |
| `FEP1-EVIDENCE` | section 2 table, rules 1 and 4 | F07, F08 / F09-F13 |
| `FEP1-SCORE` | section 2 rule 3 | F14 |
| `FEP1-DECL` | section 4 table | F15, F16 / F17-F20 |
| `FEP1-TD-INPUT` | section 3 rule 4 | F21 |
| `FEP1-TD-FORMAT` | section 3 table, rules 2 and 8 | F22-F26 / F27-F35 |
| `FEP1-TD-FINAL` | section 3 rules 5-7 | F25, F26 / F36-F38 |

**`is_final` semantics for consumers.** For a decision log, the reference consumer returns `acted`: the texts a bridge may act on (`shown[0]` of each final `COMMIT`). The manifest gives the expected list. F23 has a provisional `COMMIT` followed by a final `ABSTAIN`: a conforming consumer acts on nothing.

## Reference implementation
- `fidetype.trust.streaming`: reads `segment_end`, the evidence fields (`nbest_from_hypothesis`) and `decode_declaration`, and writes `trust_decision` (`StreamDecision.to_event`). Tests: `tests/test_trust_streaming.py`, `tests/test_fep_profiles.py`.
- `fidetype.trust.declaration`: `validate_declaration`, `compare_declaration`.
- `StreamingConfig.declaration_check`: `"warn"` (default: record the result in the provenance and in `trust_decision.declaration`, log a mismatch once per session, do not change the decision), `"abstain"` (a mismatch gives ABSTAIN), `"off"`. `require_declaration` (a missing declaration is a mismatch) and `expected_decoder` (`decoder`, `decoder_version`, `params` that must match). A malformed declaration is a `StreamEventError`.
- Not yet done: the change to the reference v0.1 consumer to read the new events as known types (it ignores them, which is correct for v0.1).

## Alternatives
- **A `meta` key for segment boundaries.** Rejected: `meta` is a header field and cannot mark a point in time.
- **Reuse `decision` (3.5) for trust output.** Rejected: `decision` is decoder output ("the user selected X"). A trust decision has other fields (action, provisional state, set size) and a different producer. Mixing them would let a trust layer read its own output as input.
- **Span scores in place of `char_confidences`.** Rejected for now: span score semantics are undefined, and spans need time ranges that a hypothesis-only producer may not have.
- **Reuse the `decoder.name` / `decoder.version` meta keys (4.2) for the declaration.** Rejected: `meta` describes the stream producer as a whole, cannot change per hypothesis, and has no key for the frame temperature or for the trust configuration. A producer SHOULD keep both consistent.
- **Let the layer re-apply the temperature on the hypothesis route.** Not possible: the temperature acts on the frames before the decoder; the n-best scores do not allow to undo it.

## Privacy and leakage
- `shown` holds decoded text. It is not ground truth (rule 3 of 3.6 applies), but it is personal data. Logs SHOULD omit it or use the provenance ledger's hash mode.
- `segment_end`, the evidence fields and `decode_declaration` hold no text beyond what v0.1 already carries. `params` MUST NOT carry text of the user (for example a prompt or a target sentence; see 5.3).

## Open questions
1. Should `segment_end` carry an id, so that a `trust_decision` can name the segment it closes?
2. Should a provisional `trust_decision` use a separate action name (for example `PREVIEW`) instead of `is_final = false`?
3. Should `char_confidences` move to a per-hypothesis lattice when lattices arrive (question 3)?
4. Should `decode_declaration` carry a hash of the decoder weights (as `decoder.weights_sha256`, 4.2), and should the layer require it?
5. Should `abstain` become the default `declaration_check` mode when the FEP moves to Stable?
6. Should rule 9 become a MUST (with a reject vector in the `fep-0001` profile) when the FEP moves to Stable? This needs a reference configuration that never commits an empty text (a v5 configuration with the commit gate on by default).
