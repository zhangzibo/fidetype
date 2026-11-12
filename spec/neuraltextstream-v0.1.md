# NeuralTextStream specification, v0.1

| | |
|---|---|
| **Version** | 0.1 |
| **Status** | **Development** |
| **Date** | 2026-11-08 |
| **Reference implementation** | [`fidetype.streams.spec`](../src/fidetype/streams/spec.py) (`NeuralTextStream`) |
| **Licence** | Apache-2.0 |
| **Change process** | [FEPs](feps/) (Fidetype Enhancement Proposals) |

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY in this document are to be read as in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when they are in capitals.

**In one line:** NeuralTextStream (NTS) is "EMMA for neural input, in the OpenTelemetry style". It is a vendor-neutral format for what a neural decoder outputs, **with honest confidence**, in a data model plus shared field names (semantic conventions).

## 1. Status and stability

### 1.1 Stability levels
Each part of this spec has one stability level. The levels are the same as in OpenTelemetry.

| Level | Meaning |
|---|---|
| **Development** | The part can change or go away in any release. Do not depend on it in production. |
| **Stable** | The part does not change in a way that breaks producers or consumers, within one major version. |
| **Deprecated** | The part still works. A replacement exists. The part will be removed after its support window. |
| **Removed** | The part is no longer in the spec. |

### 1.2 Status of this version
- All parts of v0.1 are at **Development**. No part is Stable yet. Breaking changes can occur before v1.0.
- **The frame core** (sections 3.1–3.3 and the NPZ form in 6.1) is the **Stable candidate**. It is implemented and tested in the reference implementation. We intend to make it Stable first.
- The other event kinds, the vocabulary registry, the extended timing, signal quality and the bindings (sections 3.4–3.10, 6.2–6.5) are **Development** sketches. The reference implementation does not implement them yet.
- Each breaking change gets a FEP and a changelog entry.

### 1.3 Promise after Stable
When a part becomes Stable:
- The spec version follows [semantic versioning](https://semver.org/). A breaking change to a Stable part needs a new major version.
- A Deprecated Stable part stays supported for **at least 12 months** after the release that deprecates it.
- The reference validator accepts all Stable versions in their support window.

## 2. Scope

### 2.1 In scope
NeuralTextStream is the output of any neural input decoder.
- The core is the **frame**: at each time frame, a probability distribution over a declared vocabulary.
- The vocabulary can contain characters, keys, words, phonemes, or commands and intents.
- The decoder can be a CTC decoder (with a blank token) or not.
- The device can be of any modality: wrist EMG, EEG, MEG, OPM-MEG, ECoG, intracortical arrays, fNIRS, or a simulator.
- Development extensions add discrete **decisions**, **text hypotheses** (n-best), **pointer** movement and **signal quality** (section 3.4 onward).

The stream is the contract between a decoder and the consumers of its output. A consumer does not need to know how the decoder works.

### 2.2 Why a new format
We know of no standard for decoded neural output with confidence (2026-11-08):
- **Apple BCI HID** (HID Usage Page 0x60) sends discrete button events and a 0–255 "neural activity strength". The strength is not a probability.
- **W3C EMMA 1.0** (2009) has `emma:confidence` and `emma:one-of` for n-best results. It is not specific to neural input. It has no per-frame distributions.
- Vendor SDKs differ: some give a 0–1 "power", some a "probability", some nothing.

NTS fills this gap. It bridges to these formats and does not replace them (section 9).

### 2.3 Out of scope
| Topic | Where it belongs |
|---|---|
| Raw neural signals and their real-time transport | [Lab Streaming Layer (LSL)](https://labstreaminglayer.org/) |
| Raw neural data at rest (files, datasets) | [BIDS](https://bids.neuroimaging.io/); ISO/IEC TS 27571 (section 9) |
| Trust decisions: calibration, abstention, the choice to commit, hallucination flags | The Fidetype trust layer. It *consumes* NeuralTextStreams. Its outputs are not part of this spec. |
| Final input events to an operating system | HID-level protocols (section 9) |

*Informative note (2026-11-11).* The reference trust layer can set its COMMIT threshold with conformal risk control (`fidetype.trust.risk_control`). It then bounds the expected wrong-commit rate by a target α (default 0.05), or bounds it with probability 1 − δ (Learn then Test). The bound holds only if the calibration items and the later items are exchangeable. In practice: calibrate per user and per session, on items with known truth, and re-calibrate after drift. A consumer that reports such a bound SHOULD state α (and δ), the method, the number of calibration items and their scope (user, session). This note adds no field to the stream.

*Informative note (2026-11-11, M2-16).* Under drift inside a session the offline bound can fail. The reference trust layer can then re-calibrate the threshold online from the user's feedback (`fidetype.trust.online_risk`). Two of its methods bound the **long-run average** wrong-commit rate over the T items of a session by α plus a term of order 1/T, for any sequence of items. The bound does not cover short windows, and it covers only the errors that the system observes (a wrong commit that the user does not notice is outside it). A consumer that reports such a bound SHOULD state the method, α, T, the feedback it used (corrections only, or the final text) and the measured silent-error rate. This note adds no field to the stream.

### 2.4 Design principles
1. **80/20.** Define the small set of fields that most decoders need. Put the rest in `meta`.
2. **Adoption first.** A decoder that emits log-softmax output already has most of the data. Emitting a stream must be cheap.
3. **Do not reinvent.** Bridge to LSL, BIDS, EMMA and HID. Do not replace them.
4. **Honest probabilities.** The stream carries the decoder's own output. A producer MUST NOT sharpen or smooth the probabilities for display. Consumers calibrate them.
5. **Say what a score means.** A number is a probability only if the stream says so (section 3.5).

## 3. Data model

### 3.0 Overview
A stream has one **header** and a sequence of **events**. The header holds the fields that do not change: the vocabulary, the source and `meta`.

| Event kind | Content | Stability | In reference implementation |
|---|---|---|---|
| `frame` | A distribution over the vocabulary at one time | Development (**Stable candidate**) | Yes |
| `decision` | One discrete label with a score and its semantics | Development | No |
| `hypothesis` | Text n-best list, with spans and streaming revisions | Development | No |
| `pointer` | Continuous 1-D to 3-D movement | Development | No |
| `signal_quality` | Quality of the input signal, separate from confidence | Development | No |

In the array form (NPZ, and the `NeuralTextStream` class), all frames of a stream are stored together as arrays. A stream of T frames and a vocabulary of V tokens has the fields below. T can be 0.

### 3.1 Required fields (frame core)
| Field | Type | Description | Stability |
|---|---|---|---|
| `spec_version` | string | The version of this spec. For this document: `"0.1"`. | Development |
| `log_probs` | float array, shape [T, V] | Row t holds the **natural-log** probabilities of the V tokens at frame t. `-inf` is allowed. | Development |
| `frame_times` | float array, shape [T] | The time of each frame, in **seconds**. The zero point is the producer's choice (for example, the start of a trial). | Development |
| `vocab` | list of V strings | `vocab[i]` is the token of column i. The order is significant. | Development |
| `vocab_type` | string (enum) | The kind of token: `char`, `key`, `word`, `phoneme`, `command` or `other`. | Development |
| `blank_id` | integer or null | The index of the CTC blank token in `vocab`. `null` if the decoder is not a CTC decoder. | Development |

**`vocab_type` values.**

| Value | Tokens are | Example |
|---|---|---|
| `char` | Characters of a written language | `"a"`, `" "` |
| `key` | Keys of a physical or virtual keyboard | `"KeyA"`, `"Backspace"` |
| `word` | Whole words from a closed word list | `"water"`, `"help"` |
| `phoneme` | Phonemes (for example, ARPABET or IPA symbols) | `"AH"`, `"ʃ"` |
| `command` | Commands or intents | `"select"`, `"undo"`, `"rest"` |
| `other` | Anything else. Describe it in `meta`. | — |

The blank token and any "no event" or "rest" token are normal entries in `vocab`. The spec does not reserve token strings.

### 3.2 Optional fields (frame core)
| Field | Type | Description | Stability |
|---|---|---|---|
| `frame_period` | float > 0, or absent | The nominal time between frames, in seconds. A consumer MUST use `frame_times` as the true times. | Development |
| `latency` | float ≥ 0, or absent | The **algorithmic lookahead** of the decoder, in seconds: how much signal after `frame_times[t]` the decoder used to compute frame t. `0` means a causal decoder. A full-sequence (offline) decoder SHOULD omit it and set `meta["decoder.causal"] = false`. | Development |
| `source` | non-empty string | A short name of the producer, for example `"simulator"`. Default: `"unknown"`. | Development |
| `meta` | JSON object | Extra data. Keys SHOULD follow the semantic conventions in section 4. | Development |

### 3.3 Sparse (top-k) frames (Development)
A large vocabulary (for example, words) makes dense frames large. In the streaming forms, a frame MAY be sparse:
- `top_ids`: a list of k token indices, and `top_log_probs`: their k log-probabilities.
- `rest_log_prob`: the log of the total probability of all other tokens. It MAY be `null` (`-inf`).
- The normalisation rule applies to the k values plus `rest_log_prob`.
- A consumer that needs a dense row MUST spread the rest mass uniformly over the other V − k tokens, unless it has a better model.

The NPZ form (6.1) stores only dense frames in v0.1.

### 3.4 Vocabulary identity (Development)
Two decoders with the same token strings can still mean different things. Optional header fields name the vocabulary:

| Field | Type | Description |
|---|---|---|
| `vocab_id` | string | A namespaced name of a registered vocabulary, for example `char.b2q-28` |
| `vocab_version` | string | The version of that vocabulary, for example `"1"` |

Registry namespaces (the entries are Development and will be listed in `spec/vocab/` later):

| Namespace | For | Example ids |
|---|---|---|
| `char.*` | Character sets | `char.b2q-28` (CTC blank, `a`–`z`, space; the Brain2Qwerty set) |
| `phoneme.*` | Phoneme sets | `phoneme.arpabet-39` |
| `hid.bci.switch.*` | Switch actions that mirror the actions of the Apple BCI HID usage page | `hid.bci.switch.primary` |
| `gesture.*` | Hand or wrist gestures (for example, EMG) | `gesture.pinch` |
| `mi.*` | Motor-imagery classes | `mi.left-hand`, `mi.right-hand`, `mi.rest` |

If `vocab_id` is present, `vocab` MUST still be present and MUST match the registered list.

### 3.5 Decision event (Development)
A **decision** is one discrete output: "the user selected X". Many devices give only decisions, not distributions.

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | string | Yes | The selected token. It SHOULD be a token in `vocab`. |
| `t` | float | Yes | The time of the decision, in seconds |
| `score` | number or null | No | The vendor's score for the decision |
| `score_semantics` | string (enum) | Yes | What `score` means (table below) |
| `score_range` | [min, max] | If `power` or `strength` | The range of `score`, for example `[0, 255]` |

| `score_semantics` | Meaning | Example source |
|---|---|---|
| `calibrated_prob` | A probability in [0, 1] that was calibrated on held-out data | A trust layer output |
| `uncalibrated_prob` | A probability in [0, 1], not calibrated | Softmax output of a classifier; a vendor "probability" field |
| `power` | A non-negative magnitude, not a probability | A vendor 0–1 "power" value |
| `strength` | An ordinal strength on a fixed scale | Apple BCI HID "neural activity strength", 0–255 |
| `none` | No score. `score` MUST be null or absent | A device that exposes only the event |

Rules:
1. A consumer MUST NOT treat `score` as a probability unless `score_semantics` is `calibrated_prob` or `uncalibrated_prob`.
2. If `score_semantics` is a probability, `score` MUST be in [0, 1].
3. A producer MUST NOT label a score `calibrated_prob` unless a calibration step was applied. It SHOULD then set `decoder.calibration_id` and `decoder.calibration_method` (section 4).

### 3.6 Text hypotheses (Development)
A decoder with a language model can emit text directly. A **hypothesis** event carries an n-best list.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique within the stream |
| `nbest` | list | Yes | Ranked best first. Each item: `text` (string), `score` (number), and optional `spans` |
| `score_semantics` | string (enum) | Yes | As in 3.5. Use `none` for raw log-scores and add `meta` to explain them. |
| `is_final` | boolean | Yes | `false` while the decoder can still change the text |
| `revision_of` | string or null | No | The `id` of an earlier hypothesis that this one replaces |
| `t_start`, `t_end` | float | No | The signal time that the hypothesis covers, in seconds |

Each item of `spans` maps a part of `text` to the signal: `{"char_start": int, "char_end": int, "t_start": float, "t_end": float, "score": number}`. `char_end` is exclusive.

Rules:
1. A consumer MUST treat a hypothesis with `is_final = false` as provisional.
2. A hypothesis with `revision_of` replaces the earlier one completely.
3. Hypothesis text is decoder output. It is not ground truth. The leakage rule (5.3) still applies.
4. A lattice form is a future extension (section 10).

### 3.7 Pointer event (Development)
A **pointer** event carries continuous movement, for example cursor control from an implant.

| Field | Type | Required | Description |
|---|---|---|---|
| `t` | float | Yes | Time, in seconds |
| `dims` | integer, 1–3 | Yes | The number of axes |
| `mode` | `relative` or `absolute` | Yes | `relative`: a change since the last event. `absolute`: a position |
| `values` | list of `dims` numbers | Yes | One value per axis. Absolute values are normalised to [0, 1] |
| `absent` | list of `dims` booleans | No | `true` if the decoder gives no value for that axis in this event. The value MUST then be ignored |
| `score`, `score_semantics` | as in 3.5 | No | Confidence of the movement |

This event maps to the pointer report (Report 3) of the Apple BCI HID protocol.

### 3.8 Timing (Development)
`frame_times` and `t` are the signal time of an event. For latency analysis, an event MAY carry more times:

| Field | Meaning |
|---|---|
| `t_signal_start` | The start of the signal window that the decoder used |
| `t_signal_end` | The end of that window |
| `t_decoded` | When the decoder finished the computation |
| `t_emitted` | When the producer sent the event |

The header field `clock_domain` names the clock of all times in the stream: `lsl` (the LSL clock), `unix` (seconds since 1970-01-01 UTC), `monotonic` (a local monotonic clock), `trial` (relative to the trial start; the default) or `other`.

Then the end-to-end latency of an event is `t_emitted − t_signal_end`. Times MUST be in seconds. For each event, `t_signal_start ≤ t_signal_end ≤ t_decoded ≤ t_emitted` MUST hold when they are present.

### 3.9 Signal quality (Development)
Signal quality is **not** decoder confidence. A clean signal can still give a wrong decode. A noisy signal can give a correct one by chance. So NTS keeps them apart.

A `signal_quality` event has `t`, `value`, `unit` and optional `channels`:
- `value`: a number. For `unit = "index"`, a value in [0, 1], where 1 is best.
- `unit`: `index`, `snr_db`, `impedance_ohm` or `other`.
- `channels`: an optional list of per-channel values in the same unit.

A consumer MUST NOT fold signal quality into `log_probs` or `score`. It MAY use it as a separate input, for example to abstain.

### 3.10 Header fields of the extensions (summary)
`vocab_id`, `vocab_version` and `clock_domain` are optional header fields. They are Development and not in the reference implementation yet.

## 4. Semantic conventions for `meta`
Semantic conventions are shared key names. They let different producers describe the same thing in the same way, as in OpenTelemetry.

### 4.1 Rules
- Keys are namespaced with dots: `<namespace>.<name>`. Names use `snake_case`.
- A key in this table MUST have the type and meaning given here.
- Producers MAY add their own keys. Custom keys SHOULD use a namespace that is not in this table (for example, `acme.gain`), so they do not collide with future conventions.
- Values MUST be JSON values.

### 4.2 Defined keys
| Key | Type | Values / meaning | Stability |
|---|---|---|---|
| `device.modality` | string (enum) | `emg`, `eeg`, `meg`, `opm-meg`, `ecog`, `intracortical`, `fnirs`, `other` | Development |
| `device.vendor` | string | The maker of the recording device | Development |
| `device.model` | string | The device model | Development |
| `device.channel_count` | integer ≥ 1 | The number of input channels that the decoder used | Development |
| `device.invasive` | boolean | `true` for implanted electrodes (ECoG, intracortical) | Development |
| `device.regulatory_status` | string | For example `research`, `investigational`, `cleared`, `consumer`, `unknown`. This is information only. It is not a claim of approval. | Development |
| `decoder.name` | string | The name of the decoder or model | Development |
| `decoder.version` | string | The version of the decoder or of its weights | Development |
| `decoder.causal` | boolean | `true` if frame t uses no signal after `frame_times[t]` plus `latency` | Development |
| `decoder.lookahead_s` | float ≥ 0 | The lookahead in seconds. If both are present, it MUST be equal to `latency` | Development |
| `decoder.calibration_id` | string | An identifier of the calibration that was applied (for example, a hash of its parameters) | Development |
| `decoder.calibration_method` | string | For example `temperature`, `platt`, `isotonic`, `none` | Development |
| `decoder.weights_sha256` | string | The SHA-256 (64 lowercase hex characters) of the weights file that produced the stream. Optional. For provenance (section 4.3) | Development |
| `adapter.name` | string | The name of the adapter that converted a device or dataset output into NTS, if there is one | Development |
| `adapter.version` | string | The version of that adapter (for example, a release or a commit id) | Development |
| `stream.id` | string | An **opaque**, unique identifier of this stream (for example, a UUID). It MUST NOT contain personal data. Optional. For provenance (section 4.3) | Development |
| `lm.name` | string | The language model inside the decoder, if any. `"none"` if there is no LM | Development |
| `user.personalized` | boolean | `true` if the decoder was adapted to this user | Development |
| `session.id` | string | A **pseudonymous** session identifier | Development |
| `subject.id` | string | A **pseudonymous** subject identifier (for example, `"sub-01"`) | Development |
| `language` | string | The language of the decoded text, as a [BCP 47](https://www.rfc-editor.org/info/bcp47) tag (for example, `"es"`, `"en-US"`) | Development |
| `calibration.applied` | boolean | `true` if a calibration step changed the probabilities after the decoder. Default when absent: `false` | Development |
| `data.derived` | boolean | `true` if the stream holds only data derived from neural signals and no raw samples. An NTS stream SHOULD set `true` | Development |
| `consent.ref` | string | An **opaque** reference to a consent record that is kept elsewhere. It MUST NOT contain the consent text or personal data | Development |

> **Note.** Today, some reference producers in this repository still use older, flat meta keys (for example, `subject`, `session`). They will move to these conventions before v0.2.

### 4.3 Provenance (informative)
*Added 2026-11-11 (M2-09). This section is informative. It adds four optional `meta` keys (4.2) and no required field. Every valid v0.1 stream stays valid.*

A consumer that acts on decoded text (for example, a trust layer that commits text for the user) SHOULD keep a provenance record for each decision. The record links the text to the stream, the models and the settings that produced it. Then a wrong output can be traced and audited later. The Fidetype reference is `fidetype.trust.provenance` (an append-only JSON Lines ledger with a SHA-256 hash chain).

Recommendations:
1. Refer to a stream by `stream.id` if present. Otherwise use a content hash of the stream (the reference uses SHA-256 over the canonical JSON header plus the `log_probs` and `frame_times` bytes). Record the frame range `[start, end)` that the decision used.
2. Copy the provenance keys of `meta` (`device.*`, `adapter.*`, `decoder.*` with `decoder.weights_sha256`, `decoder.calibration_id`, `lm.*`) into the record. Add the consumer's own calibration, policy version and decision scores.
3. Do not copy raw signals or frame arrays into the record. Store hashes and identifiers. Store text only if the deployment allows it; otherwise store a keyed hash (HMAC) or nothing.
4. Treat `subject.id` and `session.id` as in 5.4. A record SHOULD store them pseudonymised again (for example, hashed) or not at all.
5. A later user correction SHOULD be a new record that refers to the decision it corrects. Do not change the old record.

## 5. Normative rules

### 5.1 Structure
1. `log_probs` MUST have exactly 2 dimensions, [T, V].
2. V MUST be equal to the length of `vocab`.
3. `frame_times` MUST have shape [T].
4. `spec_version` MUST be a version that the consumer supports. For this spec: `"0.1"`.
5. `vocab_type` MUST be one of the values in section 3.1.
6. If `blank_id` is not null, it MUST be in the range 0 to V−1.
7. If `source` is present, it MUST be a non-empty string. If `meta` is present, it MUST be a JSON object.

### 5.2 Values
1. **Normalisation.** Each row of `log_probs` MUST log-sum-exp to 0, with a tolerance of **1e-3**: |log Σᵢ exp(log_probs[t, i])| ≤ 1e-3. A producer whose model gives logits MUST apply `log_softmax` first.
2. `log_probs` MUST NOT contain NaN or `+inf`. It MAY contain `-inf` (probability 0).
3. **Time.** `frame_times` MUST be finite. They MUST increase strictly (monotonic): `frame_times[t+1] > frame_times[t]`.
4. **Vocabulary.** The tokens in `vocab` MUST be unique strings.
5. `frame_period`, if present, MUST be finite and > 0. `latency`, if present, MUST be finite and ≥ 0.

### 5.3 Leakage rule
1. A stream MUST NOT contain the ground-truth text, the target labels, or any value derived from them. This applies to all fields and all event kinds, including `meta`.
2. Ground truth for evaluation MUST travel separately from the stream (for example, in a separate file or in a BIDS `events.tsv`).

This rule keeps evaluations honest. A consumer that sees the answer in the stream can give false results.

### 5.4 Privacy rules
1. `meta` MUST NOT contain personal identifiers: names, e-mail addresses, dates of birth, medical record numbers, addresses, or face or voice data.
2. `subject.id` and `session.id` MUST be pseudonymous. The mapping to real people MUST NOT be in the stream.
3. A producer SHOULD NOT put free-text notes in `meta`. Free text can contain personal data by accident.
4. A stream SHOULD state `data.derived`. If consent applies, it SHOULD carry only an opaque `consent.ref`.

**Neural-data laws.** Some jurisdictions now regulate neural data. Examples: Colorado HB24-1058, California SB 1223 and Montana SB 163. Decoded output can be neural data under such laws. The fields `data.derived` and `consent.ref` help a producer document what a stream holds and under which consent. They do not make a stream compliant. This spec is not legal advice. Check the current text of each law.

> The reference validator checks the rules in 5.1 and 5.2. The rules in 5.3 and 5.4 are the producer's responsibility. A validator cannot check them fully.

## 6. Serialisations and bindings

### 6.1 NPZ file (Development, Stable candidate)
A NumPy `.npz` archive, written with `numpy.savez_compressed`. It MUST load with `allow_pickle=False`. This is the layout of `NeuralTextStream.to_npz` in the reference implementation. It holds the frame core only.

| NPZ key | dtype / shape | Holds | Required |
|---|---|---|---|
| `version` | unicode string, shape () | `spec_version` | Yes |
| `log_probs` | `float32`, shape (T, V) | `log_probs` | Yes |
| `frame_times` | `float64`, shape (T,) | `frame_times` | Yes |
| `vocab` | unicode string, shape (V,) | `vocab` | Yes |
| `vocab_type` | unicode string, shape () | `vocab_type` | No. A reader MUST use `"char"` if it is absent (files written before this key existed). |
| `blank_id` | `int64`, shape () | `blank_id`. The value **−1 means null** (no blank). | Yes |
| `source` | unicode string, shape () | `source` | Yes |
| `meta_json` | unicode string, shape () | `meta`, as a JSON text | Yes |
| `frame_period` | `float64`, shape () | `frame_period` | No. Written only if set. |
| `latency` | `float64`, shape () | `latency` | No. Written only if set. |

Notes:
- The NPZ key for `spec_version` is `version`. This keeps files from before this document readable.
- A reader MUST ignore unknown keys. This lets later minor versions add keys.

### 6.2 JSON Lines streaming form (Development)
For live use, a stream MAY be sent as [JSON Lines](https://jsonlines.org/): UTF-8, one JSON object per line.
- **Line 1 is the header.** It holds all header fields (everything except the events).
- **Each next line is one event.** The `type` key gives the event kind.
- **An optional last line marks the end.**

```json
{"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a", "b", " "], "vocab_type": "char", "blank_id": 0, "source": "my-decoder", "frame_period": 0.04, "latency": 0.2, "clock_domain": "trial", "meta": {"device.modality": "emg", "decoder.causal": true, "data.derived": true}}
{"type": "frame", "t": 0.00, "log_probs": [-0.0834, -2.9957, -3.9120, -4.6052]}
{"type": "frame", "t": 0.04, "log_probs": [-0.2231, -1.8971, -2.9957, null]}
{"type": "signal_quality", "t": 0.04, "value": 0.92, "unit": "index"}
{"type": "decision", "t": 0.08, "label": "a", "score": 0.71, "score_semantics": "uncalibrated_prob"}
{"type": "hypothesis", "id": "h1", "is_final": false, "score_semantics": "none", "nbest": [{"text": "ab", "score": -1.2}, {"text": "a", "score": -1.9}]}
{"type": "end"}
```

Rules:
1. The header MUST come first. It MUST contain `"type": "header"`, `spec_version`, `vocab`, `vocab_type` and `blank_id`.
2. A dense frame MUST contain `"type": "frame"`, `t` (seconds) and `log_probs` (a list of V numbers). A sparse frame uses the keys of section 3.3 instead of `log_probs`.
3. JSON has no infinity. `null` in a log-probability MUST mean `-inf`.
4. The rules of section 5 apply to the frames in order. `t` MUST increase strictly from frame to frame.
5. A consumer MUST ignore unknown keys and unknown `type` values.
6. The stream MAY end without an `end` line (for example, if the connection drops).

### 6.3 WebSocket JSON (Development, sketch)
Send the JSON Lines objects of 6.2 as WebSocket text messages, one object per message. The first message MUST be the header.

### 6.4 NTS over LSL (Development, sketch)
[LSL](https://labstreaminglayer.org/) can carry an NTS stream as two LSL streams:

| NTS part | LSL stream | Details |
|---|---|---|
| Frames | A `float32` stream with V channels | One LSL sample per frame. `nominal_srate` = 1 / `frame_period` (0 if irregular). The channel labels in the XML `desc` follow the `vocab` order. The other header fields go in the `desc` as well. LSL timestamps give `clock_domain = "lsl"`. |
| Decisions, hypotheses, pointer, signal quality | A string marker stream (irregular rate) | One LSL sample per event. The sample is the JSON object of 6.2. |

### 6.5 NTS → Apple BCI HID bridge (Development, sketch)
A bridge can turn NTS decisions into Apple BCI HID reports:
- a `decision` with a label in `hid.bci.switch.*` → a button event;
- a `pointer` event → the pointer report (Report 3);
- `score` → the 0–255 strength, only by an explicit, documented mapping.

**This bridge is lossy.** HID carries no distributions, no n-best lists, no score semantics and no calibration. A bridge SHOULD send only decisions that a trust layer committed. It SHOULD log the full NTS events next to the HID output, so that each HID event stays inspectable.

### 6.6 Binary wire protocol (open question)
A compact binary protocol (for example, Protocol Buffers, like OTLP in OpenTelemetry) may come later. See section 10.

## 7. Conformance
- The reference validator is `NeuralTextStream.validate()` in [`fidetype.streams.spec`](../src/fidetype/streams/spec.py). The constructor and `from_npz` call it. It raises `ValueError` with a message at the first error. It covers the frame core.
- A separate **conformance test suite** will ship. It will contain valid and invalid example files in each serialisation, so that implementations in other languages can test themselves.

### 7.1 Conformance cases
| # | Case | Expected result |
|---|---|---|
| C1 | Valid char stream (28 tokens, CTC blank at 0) | Accept |
| C2 | Valid command stream, `blank_id = null`, `vocab_type = "command"` | Accept |
| C3 | Empty stream (T = 0) | Accept |
| C4 | A row of `-inf` except one `0` | Accept |
| C5 | A row that sums to 2 in probability space | Reject (normalisation) |
| C6 | NaN or `+inf` in `log_probs` | Reject |
| C7 | Two equal `frame_times` | Reject (monotonic) |
| C8 | Duplicate token in `vocab` | Reject (unique) |
| C9 | V ≠ length of `vocab` | Reject |
| C10 | `blank_id` = V | Reject |
| C11 | Unknown `vocab_type` | Reject |
| C12 | Unknown `spec_version` | Reject |
| C13 | Negative `latency`, or `frame_period` = 0 | Reject |
| C14 | NPZ file without `vocab_type` | Accept, `vocab_type = "char"` |
| C15 | NPZ file with an unknown extra key | Accept |
| C16 | JSON Lines with `null` in `log_probs` | Accept, read as `-inf` |
| C17 | `decision` with `score_semantics = "uncalibrated_prob"` and `score = 1.5` | Reject (Development) |
| C18 | `decision` with `score_semantics = "strength"` and no `score_range` | Reject (Development) |
| C19 | JSON Lines with an unknown event `type` | Accept, ignore the event |
| C20 | Event with `t_decoded` < `t_signal_end` | Reject (Development) |

## 8. Examples

### 8.1 Python (reference implementation)
```python
import numpy as np
from fidetype.streams.spec import NeuralTextStream

logits = np.random.default_rng(0).standard_normal((50, 4))
log_probs = logits - np.log(np.exp(logits).sum(axis=1, keepdims=True))  # log_softmax

stream = NeuralTextStream(
    log_probs=log_probs,
    frame_times=np.arange(50) * 0.02,
    vocab=["rest", "select", "next", "back"],
    vocab_type="command",
    blank_id=None,
    source="my-emg-decoder",
    frame_period=0.02,
    latency=0.0,
    meta={"device.modality": "emg", "decoder.causal": True, "subject.id": "sub-07"},
)
stream.to_npz("stream.npz")
```

### 8.2 Typical producers
| Producer | Main event kind | `vocab_type` | `blank_id` | Notes |
|---|---|---|---|---|
| MEG typing decoder with CTC (Brain2Qwerty-style) | `frame` | `char` | 0 | 28 tokens: blank, a–z, space (`char.b2q-28`) |
| Wrist-EMG keyboard decoder | `frame` | `key` | null or an index | Key codes as tokens |
| Speech BCI with phoneme CTC and an LM | `frame` + `hypothesis` | `phoneme` | an index | Phoneme set in `vocab_id` |
| Consumer EEG headset with a "mental command" API | `decision` | `command` | null | `score_semantics = "power"` |
| Implant cursor | `pointer` + `decision` | `command` | null | Maps to Apple BCI HID |

## 9. Relation to other standards
| Standard | What it covers | Relation to NeuralTextStream |
|---|---|---|
| [Lab Streaming Layer (LSL)](https://labstreaminglayer.org/) | Real-time transport of raw signals and markers in the lab | Different layer. LSL carries the signal *into* a decoder. NTS *can be carried over LSL* (section 6.4). |
| [BIDS](https://bids.neuroimaging.io/) | Offline storage of raw neuroimaging data (MEG, EEG, iEEG and more) | Different layer. BIDS stores the raw data. An NTS file could become a **BIDS derivative** of a recording. A BIDS extension proposal is a possible later step. |
| ISO/IEC TS 27571:2026 (ISO/IEC JTC 1/SC 43) | A raw-data format for non-invasive BCI. **Status UNVERIFIED** | Different layer (raw data). NTS starts after the decoder. We will align terms when we can check the document. |
| [W3C EMMA 1.0](https://www.w3.org/TR/emma/) (2009) | Annotation of multimodal input results: `emma:confidence`, `emma:one-of` for n-best | The closest model for confidence and n-best. Not neural-specific. No per-frame distributions. NTS `hypothesis` events can be converted to EMMA `one-of` results. |
| [IEEE P2731](https://standards.ieee.org/ieee/2731/) | Unified terminology for BCI | We use its terms where they exist. We will align our terms when it is published. |
| [Apple BCI HID](https://developer.apple.com/documentation/accessibility/brain-computer-interface-hid-reference-for-connecting-to-apple-platforms) (HID Usage Page 0x60) | Input events from a BCI to Apple platforms: button events, a 0–255 neural activity strength, a pointer report | Downstream. HID events are final decisions. Their strength is not a probability. NTS sits **upstream**: it keeps the full distribution and the score semantics, and a trust layer adds calibrated confidence before an event is committed. A lossy bridge is sketched in 6.5. |

Rule: Fidetype does not create a rival format where one exists. It bridges.

## 10. Open questions
1. **Binary wire protocol.** Do we need a Protocol Buffers (or similar) form for low-latency transport, like OTLP? Which transport is the default: LSL, WebSocket or gRPC?
2. **Embeddings.** Should a frame optionally carry an embedding vector (a summary of the neural evidence)? Which shape and dtype?
3. **Lattices.** Should `hypothesis` events support a word lattice, not only an n-best list?
4. **Frame revisions.** A causal decoder with lookahead can revise earlier frames. Do frames also need `revision_of`, or only hypotheses?
5. **Segment boundaries.** How do we mark the end of a word, sentence or trial? A reserved event, or a `meta` key?
6. **Multi-head output.** Some decoders emit two distributions at once (for example, characters and commands). One stream per head, or one stream with several heads?
7. **Vocabulary registry.** Who maintains `spec/vocab/`? How do we version an entry? How exactly do we mirror the Apple switch actions and W3C key codes?
8. **Clock domains.** How do we relate two clock domains (for example, `lsl` and `unix`) across devices?
9. **Semantic convention schema.** Should the conventions live in a machine-readable schema, as in OpenTelemetry's semantic-conventions repository?
10. **Extensions in NPZ.** Do decisions, hypotheses and signal quality need an NPZ form, or only the streaming forms?
11. **Future output profiles** *(informative note, 2026-11-11; it adds or changes no field)*. The project roadmap (phase P12) plans to cover neural input beyond text: discrete intents (clicks, selections, commands) and continuous control (2D cursor). The preferred design is a modality- and output-agnostic core (header, frames, timing, provenance, `meta`) plus output profiles: *text* (this spec), *discrete intent* and *continuous control*. The text profile stays as it is; a profile adds event kinds or conventions only, through FEPs. The present `vocab_type = "command"`, `decision` (3.5) and `pointer` (3.7) parts are the starting point. Open: one stream type with profiles, or a sibling stream type; and how a consumer gates actuation (for example velocity scaling by confidence, a dead-man hold, a safe-stop).

## 11. Changelog
| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-11-08 | First written spec (Development). Frame core: fields `spec_version`, `vocab_type` and the optional `frame_period` and `latency` added to the reference implementation in a backward-compatible way; `blank_id` can be null. Semantic conventions for `meta`. NPZ and JSON Lines serialisations. From landscape research (same day): event kinds `decision`, `hypothesis`, `pointer`, `signal_quality`; `score_semantics`; sparse frames; vocabulary identity and registries; extended timing and `clock_domain`; conventions `device.invasive`, `device.regulatory_status`, `decoder.calibration_id`, `decoder.calibration_method`, `lm.name`, `user.personalized`, `data.derived`, `consent.ref`; neural-data-law note; LSL, WebSocket and Apple BCI HID binding sketches; EMMA and ISO/IEC TS 27571 in the related standards. The extensions are not in the reference implementation yet. |
| 0.1 (non-breaking addition) | 2026-11-11 | M2-09: optional `meta` keys `decoder.weights_sha256`, `adapter.name`, `adapter.version`, `stream.id`; informative section 4.3 (provenance records). No required field changes; all v0.1 streams stay valid. |
