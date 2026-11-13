# FEP-0002: NeuralTextStream over LSL

| | |
|---|---|
| **FEP** | 0002 |
| **Title** | Normative binding of NeuralTextStream to the Lab Streaming Layer (LSL) |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft |
| **Type** | Spec change (binding, Development) |
| **Affects** | `neuraltextstream-v0.1.md` section 6.4 (replaces the sketch); uses FEP-0001 (`segment_end`, `trust_decision`) |
| **Created** | 2026-11-12 |
| **Discussion** | M6-01 (LSL adapter), M6-09 (this FEP); `src/fidetype/adapters/lsl.py`, `wiki/concepts/lsl-input.md` |

## Summary
Spec 6.4 sketches NTS over LSL in two table rows. This FEP makes it a full binding: the stream types and names, the `desc` keys (with the NTS header as JSON), the channel formats and their precision, the marker events, the timestamp and clock-correction rules, the time fields inside marker events, gaps and stream loss, the decisions outlet, and versioning. The binding has a version string (`nts-lsl/0.1`). The opt-in conformance profile `fep-0002` tests it with scripted inlets (no network, no `pylsl`).

## Motivation
- The LSL adapter (M6-01) works, but parts of it were our choices, not rules: the `nts_header` desc key, `float32` vs `double64`, the extension keys `gap` and `lsl_t`, and the decisions outlet. Another implementation (C++, a vendor app, a TypeScript bridge) must give the same NTS events from the same LSL streams. It needs written rules and test vectors.
- In M6-01, `hypothesis` times (`t_start`, `t_end`) stayed in the producer's clock while frames were in the LSL clock. A consumer could not put them on one time axis. This FEP defines the clock of the time fields inside marker JSON.
- LSL is the common transport of research BCI tools (OpenBCI GUI, LabRecorder, many device apps). A clear binding lets a decoder publish NTS once and reach every LSL tool.

## Terms
- **Producer**: the program that publishes LSL outlets (a decoder, `replay-to-lsl`).
- **Consumer**: the program that reads LSL inlets and gives NTS events (`LSLEventSource`, then for example `StreamingTrustLayer`).
- **Sender clock**: `local_clock()` of the producer's host. **Receiver clock**: `local_clock()` of the consumer's host.
- **time_correction**: the offset that liblsl estimates; receiver time = sender time + time_correction.
- An **NTS-native** stream carries `desc/fidetype/nts_header`. A **foreign** stream does not.

## Proposal

### 1. Streams
An NTS stream maps to up to three LSL streams:

| NTS part | LSL stream | Type | Channels | Format | Rate |
|---|---|---|---|---|---|
| Frames (3.1) | frames stream | `NTS` | V (one per vocab token) | `float32` or `double64` | 1 / `frame_period`, or 0 |
| Other events (header copies, `hypothesis`, `segment_end`, `signal_quality`, `decision`, `pointer`, `end`, ...) | events stream | `Markers` | 1 | `string` | 0 (irregular) |
| Trust output (`trust_decision`, FEP-0001) | decisions stream | `Markers` | 1 | `string` | 0 (irregular) |

A hypothesis-only producer has no frames stream. Its events stream is then the primary stream.

### 2. Names and ids
1. The frames stream name SHOULD be `<producer>.nts`. The events stream name SHOULD be the frames stream name + `.events`. The decisions stream name SHOULD be `fidetype.decisions`.
2. A producer SHOULD set a stable `source_id`, so that a consumer can find the same stream again after a loss.
3. The frames stream desc SHOULD name the events stream in `events_source_id`; the events stream desc SHOULD name the frames stream in `frames_source_id`.

### 3. Frames stream
Rules:
1. An NTS-native frames stream MUST use channel format `float32` or `double64`. A consumer MUST refuse other formats for an NTS-native stream.
2. `channel_count` MUST equal V, the length of `vocab`. A consumer MUST refuse a mismatch.
3. If the desc has channel labels, label i MUST be vocab token i (`desc/channels/channel/label`; unit `log_prob`; type `nts.log_prob`). A consumer MUST refuse labels in another order. XML can lose white space, so a consumer compares trimmed labels, and an empty label matches any token (the space token `" "` often reads as `""`).
4. **Precision.** A `float32` stream rounds each log-probability to float32 (relative error about 6e-8). The rounded row still meets 5.2.1 (tolerance 1e-3), and a consumer MUST accept it. A `double64` stream carries the values bit-exact. A producer SHOULD use `double64` when the receiver must reproduce a file replay exactly (for example a provenance hash or an audit), and MAY use `float32` to halve the bandwidth.
5. One LSL sample is one frame. The values are natural-log probabilities (unless `values` says otherwise, section 4). `-inf` is allowed. NaN and `+inf` are not: a consumer MUST refuse a frame that holds them (5.2.2).
6. `nominal_srate` MUST be 1 / `frame_period` (relative tolerance 1e-6) when the header has `frame_period`. It MUST be 0 when the frame rate is irregular. A consumer MUST refuse an NTS-native stream whose `nominal_srate` (> 0) differs from 1 / `frame_period`.
7. *(Informative.)* A consumer MAY read a foreign numeric stream of class scores: the vocab comes from the channel labels or from the consumer's settings, `values` from the settings (`log_probs`, `probs` or `logits`), and the consumer writes `adapter.name`, `adapter.version` and `data.derived` into `meta`. A raw-signal stream (EEG, EMG) needs a decoder that makes frames; that decoder is outside this binding.

### 4. `desc/fidetype` keys
All keys are child elements of `<desc><fidetype>`; each value is text.

| Key | Streams | Required | Value |
|---|---|---|---|
| `nts_header` | frames, events | Yes (NTS-native) | The NTS header (6.2 line 1) as one JSON object; `type` MAY be absent |
| `values` | frames | No | `log_probs` (default), `probs` or `logits` |
| `binding` | all | SHOULD | Binding version, `nts-lsl/0.1` (section 9) |
| `role` | all | SHOULD | `nts_frames`, `nts_events` or `trust_decisions`. *(Informative)* a raw-signal producer MAY use `signal` (a raw EEG/EMG stream, section 3 rule 7) and `signal_markers` (its plain task markers) |
| `events_source_id` / `frames_source_id` | frames / events | SHOULD | `source_id` of the partner stream |
| `event_clock` | events | SHOULD | `lsl` or `source` (section 6, rule 5). Absent means `source` |
| `event_type`, `spec`, `config_id` | decisions | see section 8 | |

Rules:
1. `nts_header` MUST be a JSON object. A consumer MUST refuse a stream whose `nts_header` is not JSON or not an object.
2. The header in `nts_header` follows the v0.1 header rules (6.2 rule 1). A consumer MUST refuse an unknown `spec_version` (5.1.4). It carries the header in the desc, so that a consumer that connects late still gets it.
3. A consumer MUST refuse a `values` kind it does not know. An NTS-native producer SHOULD use `log_probs`.
4. A consumer MUST ignore desc keys it does not know.

### 5. Events stream
Rules:
1. The events stream MUST have type `Markers`, 1 channel, channel format `string` and an irregular rate. A consumer MUST refuse an events stream with a numeric format.
2. One sample is one NTS event: the UTF-8 JSON object of 6.2, with no NaN or infinity tokens.
3. A consumer MAY map plain (non-JSON) strings: a configured boundary string (for example `trial_end`) becomes `segment_end`; with an explicit setting, other plain strings become final 1-best `hypothesis` events (`score_semantics` `none`). Otherwise it MUST ignore plain strings and count them.
4. A sample that starts with `{` but is not a JSON object with a string `type` is malformed. A consumer MUST ignore it, count it, and go on.
5. A `header` event on the events stream starts a new NTS stream (as in 6.2). The consumer sets its `clock_domain` to `lsl`.
6. `frame` events MAY also come as JSON on the events stream (for a producer with no frames stream). Their `t` follows section 6, rule 2.

### 6. Timestamps and clock
Rules:
1. The LSL timestamp of a sample is the time of its event, in the sender clock. A producer MUST stamp each sample (it MUST NOT rely on the liblsl default of "now" when the event time is known).
2. The consumer gives NTS events with `clock_domain = "lsl"` in the header. The `t` of a frame is the (corrected) LSL timestamp. For a JSON frame on the events stream, the consumer keeps the producer's value in `t_source`.
3. **Clock correction.** In receiver mode (default) the consumer adds `time_correction` to each timestamp: t = timestamp + time_correction. It refreshes the offset (the reference uses 5 s) and uses one offset for all streams from the same sender host, so that offset noise cannot change the order of a frame and a marker. In sender mode it uses raw timestamps. The mode and the current offset go into the provenance (`lsl` record). A consumer MUST NOT write the host name into any output.
4. **Order.** NTS frame times increase strictly (6.2 rule 4). A frame timestamp at or before the previous one is moved to just after it (1 µs) if it is at most a tolerance behind (reference: 5 ms), else dropped. Both are counted and reported (`lsl_clamped`, `lsl_dropped_before` on the next frame). A consumer MAY instead refuse the stream.
5. **Time fields inside marker JSON.** `desc/fidetype/event_clock` of the events stream says which clock the time fields of its JSON events use (`t`, `t_start`, `t_end`, `t_signal_start`, `t_signal_end`, `t_decoded`, `t_emitted`):
   - `lsl`: the sender clock. In receiver mode the consumer MUST add the same `time_correction` as for the sample timestamps. Then `hypothesis` `t_start` / `t_end` and the frame times are on one axis.
   - `source` (or absent): the producer's own clock. The consumer MUST leave the fields unchanged.
   - A consumer MUST refuse another value.
   A producer SHOULD use `lsl`. The consumer adds `lsl_t` (the corrected timestamp of the sample) to every marker event.
6. Two inlets are merged by time. An item waits until every other inlet has passed its time, or for a merge window (reference: 50 ms). A smaller window lowers latency; a late marker is then released out of order and counted.

### 7. Gaps and stream loss
Rules:
1. A frame step larger than a factor (reference: 2.5) times the nominal period is a gap.
2. The consumer handles a gap in one of three modes: `mark` (default) emits an extension event `{"type": "gap", "t_start", "t_end", "missing_frames", "stream"}` (a v0.1 consumer ignores it); `segment` emits `segment_end` (with `"reason": "gap"`) at the gap; `abort` drops the open utterance without a decision.
3. **Loss.** When a stream is lost inside an utterance, the consumer MUST NOT emit a final decision on that cut utterance. It drops the utterance (the reference calls `StreamingTrustLayer.abort_utterance`). It MAY re-resolve the stream (by `source_id`) for a time-out (reference: 30 s). After a reconnect it MUST emit the header again.

### 8. Decisions stream
Rules:
1. The decisions stream MUST have type `Markers`, 1 channel, format `string`, irregular rate, and desc keys `role = trust_decisions` and `event_type = trust_decision`. It SHOULD have `spec = FEP-0001`, `binding`, and `config_id` (the trust configuration id). Its `source_id` SHOULD be `fidetype.decisions.<config_id>`.
2. One sample is one `trust_decision` event (FEP-0001 section 3) as JSON. It MUST meet the FEP-0001 rules (format, `is_final` semantics). It MAY carry the extension record `lsl` (stream ids, clock mode, offset, utterance counts, `e2e_latency_s`).
3. The sample timestamp is the emission time in the publisher's LSL clock.
4. A subscriber MUST NOT act on a decision with `is_final = false` (FEP-0001 section 3 rule 1).

### 9. Versioning
Rules:
1. A producer SHOULD write `desc/fidetype/binding` = `nts-lsl/0.1` on every stream.
2. A consumer MUST read a missing `binding` as `nts-lsl/0.1`.
3. A consumer MUST refuse a binding version it does not know. (While the major version is 0, every minor change can break readers, as in spec 5.1.4.)
4. The binding version is separate from the NTS `spec_version` inside `nts_header`. A new NTS version does not change the binding version unless the mapping changes.

### Extension keys (summary)
| Key | Where | Meaning |
|---|---|---|
| `lsl` | header (object) | Stream ids (name, type, source_id, uid, channel count, rate, format; never the host name), clock mode, `values`, `binding`, `event_clock`, adapter name and version |
| `lsl` | `trust_decision` (object) | Provenance record of section 8 rule 2 |
| `lsl_t` | marker events | Corrected LSL time of the sample |
| `t_source` | JSON frame from the events stream | The producer's `t` |
| `lsl_clamped`, `lsl_dropped_before` | frame | Counts of section 6 rule 4 since the previous frame |
| `gap` | event type | Section 7 rule 2 |

A v0.1 consumer ignores all of them (5.1, 6.2 rule 5).

## Examples
Frames stream info (abridged XML):
```xml
<info><name>acme.nts</name><type>NTS</type><channel_count>28</channel_count><channel_format>double64</channel_format>
<source_id>acme-1</source_id><nominal_srate>25.0</nominal_srate>
<desc><channels><channel><label>&lt;blank&gt;</label><unit>log_prob</unit><type>nts.log_prob</type></channel>...</channels>
<fidetype><nts_header>{"spec_version": "0.1", "vocab": ["&lt;blank&gt;", "a", ...], "vocab_type": "char", "blank_id": 0, "frame_period": 0.04, ...}</nts_header>
<values>log_probs</values><role>nts_frames</role><binding>nts-lsl/0.1</binding><events_source_id>acme-1.events</events_source_id></fidetype></desc></info>
```
Events stream samples (`event_clock = lsl`, sender clock):
```json
{"type": "hypothesis", "id": "h2", "is_final": true, "score_semantics": "none", "nbest": [{"text": "ab", "score": -1.0}], "t_start": 5021.30, "t_end": 5022.10}
{"type": "segment_end", "t": 5022.11}
```
With time_correction = 0.25 s the consumer gives `t_start` 5021.55, `t_end` 5022.35, and `lsl_t` = sample timestamp + 0.25.

## Compatibility
- v0.1 streams and files do not change. The binding replaces the sketch of 6.4.
- Streams from the M6-01 adapter (before this FEP) have no `binding` and no `event_clock`: they read as `nts-lsl/0.1` with `event_clock = source`, which is what M6-01 did.
- Reference-adapter changes in this FEP (small): it now refuses an NTS-native frames stream with an integer format, labels out of vocab order, a `nominal_srate` that differs from 1 / `frame_period`, an unknown `binding` or an unknown `event_clock`; it applies `event_clock = lsl`; `replay-to-lsl` writes `binding` and `event_clock = lsl` and maps the event time fields to the LSL clock; the decisions outlet writes `binding`.

## Conformance
Profile `fep-0002` (opt-in, `src/fidetype/conformance/profiles/fep0002.py`). Golden vectors: [`spec/conformance/fep-0002/`](../conformance/fep-0002/) (`manifest.json`; 31 JSON scenarios: 15 accept, 16 reject).

```
fidetype conformance --profile fep-0002                               # reference consumer over the vectors
fidetype conformance consumer --profile fep-0002 --impl my_mod:consume
fidetype conformance check --profile fep-0002 frames-info.xml         # producer check of a stream info (pylsl: info.as_xml())
```

A vector is a JSON scenario (schema `fidetype.conformance.lsl-scenario/1`): stream infos as liblsl XML (`info_xml`), scripted chunks (`samples` + `timestamps`, or `"lost"`), the `time_correction`, the consumer settings, and the route. In numeric samples JSON `null` is `-inf` and `"NaN"` is NaN. The scripts need no network: the reference consumer plays them through `fidetype.adapters.lsl.ScriptedInlet`. At the end of the scripts it closes the open utterance. Its trust layer uses a fixed loose synthetic configuration and the CTC greedy decoder on the frames route. Expected values:

| Key | Meaning |
|---|---|
| `clock_domain`, `binding`, `event_clock`, `vocab_size` | From the header that the consumer gives |
| `frames`, `first_frame_t`, `neg_inf_cells`, `rows_sha256` | Frame events given; t of the first; `-inf` cells; SHA-256 of the rows as float64 little-endian |
| `event_types` | Count per type of the NTS events given (header, frame, gap, segment_end, hypothesis, end) |
| `hypothesis_times`, `marker_lsl_t` | `[t_start, t_end]` of each hypothesis; `lsl_t` of each marker event |
| `decisions`, `final_decisions`, `aborted_utterances` | Trust layer output (section 7 rule 3) |
| `gaps`, `clamped`, `dropped_out_of_order`, `reconnects`, `bad_markers`, `ignored_markers` | Counts of sections 5-7 |
| `acted` (decisions scenarios) | Texts a subscriber may act on (final COMMIT only) |

| Section | Accept | Reject |
|---|---|---|
| 3 frames stream | L01, L02 (double64 bit-exact), L04 (-inf), L14 (foreign) | L16 (channels), L17 (int16), L18 (labels), L20 (rate), L22 (NaN) |
| 4 desc keys | L01 | L15 (not JSON), L23 (spec_version), L24 (values) |
| 5 events stream | L13 (plain markers, bad JSON) | L21 (numeric format) |
| 6 clock | L01 (receiver), L05 (sender), L09 (order), L11 / L12 (event_clock lsl / source) | L25 (event_clock) |
| 7 gaps and loss | L06-L08 (mark / segment / abort), L10 (loss, reconnect) | |
| 8 decisions stream | L26 | L27-L31 |
| 9 versioning | L03 (no binding key) | L19 (unknown binding) |

## Reference implementation
`fidetype.adapters.lsl` (`LSLEventSource`, `LSLTrustRunner`, `DecisionOutlet`, `replay_to_lsl`, `check_binding`, `check_native_frames`, `info_to_xml`, `ScriptedInlet`, `decisions_desc`). Tests: `tests/test_adapter_lsl.py`, `tests/test_fep_profiles.py`.

## Alternatives
- **One LSL stream for everything (string samples, frames as JSON).** Rejected as the main form: JSON frames cost about 10× the bandwidth and lose the numeric tools (LabRecorder plots, XDF readers). Section 5 rule 6 still allows it.
- **Frame header in channel metadata only (no `nts_header`).** Rejected: LSL channel metadata cannot carry `blank_id`, `vocab_type`, `meta` or `latency` without a custom schema; one JSON copy of the header is simpler and lossless.
- **Always `float32` (as the 6.4 sketch).** Kept as allowed, not required: `double64` gives exact replays, which audit and provenance need.
- **Convert all marker times to the receiver clock without a desc key.** Rejected: an M6-01 producer sends times in its own clock; a silent conversion would shift them wrongly. The explicit `event_clock` keeps old streams correct.

## Privacy and leakage
- The binding carries the same data as v0.1 JSON Lines. The host name of a stream is used only to group clock offsets. It MUST NOT appear in a header, a decision or a log line.
- The decisions stream carries `shown` texts (personal data). A publisher SHOULD omit them on a shared network (`--no-text`, `include_text=False`).

## Open questions
1. Should the binding define a chunk size or a maximum latency for the frames stream?
2. Should the decisions stream carry a back channel (user selection after `OFFER`) as a second marker stream?
3. Should `time_correction` statistics (spread, failures) become required provenance fields?
4. LAN and Wi-Fi tests (M6-10) may change the reference merge window and clamp tolerance.
