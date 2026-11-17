# NeuralTextStream 1.0, Release Candidate 4 (DRAFT)

| | |
|---|---|
| **Version** | 1.0 Release Candidate 4 (`spec_version` `"1.0"`) |
| **Status** | **RC4 DRAFT for public comment. This is not the final 1.0 specification.** Any part can change before 1.0 Stable. |
| **Date** | 2026-11-15 |
| **Previous RC** | [NTS 1.0 RC3](nts-1.0-rc3.md) (kept unchanged as the record; RC2: [nts-1.0-rc2.md](nts-1.0-rc2.md), RC1: [nts-1.0-rc1.md](nts-1.0-rc1.md)). Changes: section 1.6 and the [CHANGELOG](CHANGELOG.md). |
| **Replaces** | [NeuralTextStream v0.1](neuraltextstream-v0.1.md) (it stays valid; see section 11 and Appendix B) |
| **Folds in** | [FEP-0001](feps/0001-streaming-trust-events.md) (streaming trust events), [FEP-0002](feps/0002-nts-over-lsl.md) (LSL binding), [FEP-0003](feps/0003-intent-events.md) (output profiles: core, text, intent), [FEP-0004](feps/0004-nts-over-websocket.md) (WebSocket binding), [FEP-0005](feps/0005-control-events.md) (control profile), [FEP-0007](feps/0007-unknown-enum-values.md) (unknown enumeration values, RC3), [FEP-0008](feps/0008-optional-field-types-and-semconv.md) (optional field types and the semantic-convention registry, new in RC4) |
| **Reference implementation** | Python package `fidetype` ([`src/fidetype/`](../src/fidetype/)); SDKs in TypeScript ([`sdk/typescript/`](../sdk/typescript/)) and Rust ([`sdk/rust/`](../sdk/rust/)) |
| **Conformance** | [`conformance/`](conformance/) (profiles `v0.1`, `fep-0001` … `fep-0005`); the kit [`conformance/kit/`](conformance/kit/) and `nts-conform`; implementation levels NTS Core, NTS Full, NTS Trust-ready (9.6) and the self-certification list [`conformance/certified.json`](conformance/certified.json) (9.7); traceability in Appendix C. Semantic conventions: [`semconv/`](semconv/registry.md) (normative registry, MET-10) |
| **Licence** | Apache-2.0 |
| **Comments** | Open an issue or a Discussion with the label `spec-1.0-rc`. Name the section and the rule id (for example `TD-9`). |

> **DRAFT.** This document is a release candidate for public comment. It is not final. 1.0 Stable needs outside review by at least two decoder groups (roadmap task P1-07, externally blocked). Until then, do not claim "NTS 1.0 conformant". Claim "conformant to NTS 1.0 RC4 (draft)".

---

## Contents
1. [Status, conventions and terms](#1-status-conventions-and-terms) (changes from RC3: [1.6](#16-changes-from-rc3))
2. [Scope and core data model](#2-scope-and-core-data-model)
3. [Header](#3-header)
4. [Events](#4-events)
5. [Timing and clocks](#5-timing-and-clocks)
6. [Trust decisions](#6-trust-decisions)
7. [Output profiles](#7-output-profiles)
8. [Transport bindings](#8-transport-bindings)
9. [Conformance](#9-conformance)
10. [Security and privacy](#10-security-and-privacy)
11. [Versioning and extension rules](#11-versioning-and-extension-rules)
12. [Registries](#12-registries)
- [Appendix A. Open questions: resolutions and deferrals](#appendix-a-open-questions-resolutions-and-deferrals)
- [Appendix B. Migration from 0.1 to 1.0](#appendix-b-migration-from-01-to-10)
- [Appendix C. Conformance traceability](#appendix-c-conformance-traceability)
- [Appendix D. Relation to other standards](#appendix-d-relation-to-other-standards)

---

## 1. Status, conventions and terms

### 1.1 Status of this document
- This is **Release Candidate 4** of NTS 1.0. It is a **DRAFT for public comment**.
- It folds v0.1, the draft FEPs 0001–0005, FEP-0007 (unknown enumeration values) and FEP-0008 (optional field types and the semantic-convention registry) into one document. Where this document and a FEP differ, this document is the proposal for 1.0. The FEPs stay as the record of the design and its evaluation.
- New in this RC (not in v0.1 or a FEP): the rule ids, the decision field `spec_version` (11.2), rule TD-9 as a MUST NOT for 1.x decisions (6.3), the WebSocket header check of HDR-8 (WS-S1), the JSON number rules (4.1), the resolutions of Appendix A, and the registries (12). Appendix B lists every change.
- **Changes in RC4 (from RC3):** section 1.6. RC4 answers the semantic-convention questions SC-2 … SC-8 of the registry work (roadmap P1-04) and closes gap G-12 (optional fields whose type no validator checked).
- **Changes in RC3 (from RC2)** (kept as the record; full table: [RC3 section 1.6](nts-1.0-rc3.md#16-changes-from-rc2)). RC3 answered the open questions Q-1 … Q-8 of the protobuf schema work (roadmap P1-02): unknown enumeration values are version-gated with a safe fallback (VER-6 … VER-10, FEP-0007); GEN-9 (null only where typed); GEN-10 (integers ≤ 2^53 − 1); `declaration` is an object (TD-F2, TD-13); SEG-6, LSL-G3, CTL-T9, PRF-5, INT-T7, CTL-T8 written down. 17 new vectors (304).
- **Changes in RC2 (from RC1)** (kept as the record). One new rule (TD-12, below); no other rule text changed. RC2 closes four implementation gaps of Appendix C.2:
  - **G-2:** the Python, TypeScript and Rust validators, the LSL `nts_header` check, the WebSocket header check and the JSON schema `nts-v0.1/header` now accept a header `spec_version` `"0.1"`, `"1.0"` or `"1.<minor>"` (HDR-2, VER-3, VER-4) and refuse every other value (VER-5). New vectors V53–V60, F48–F49, L33–L35, W39–W42.
  - **G-3:** golden vectors with an integer written as `0.0`, `1.0` or `2.0` (GEN-5): V61, F50, W43.
  - **G-4:** reject vectors for the types of `session`, `config_id`, `input` and `latency_s` (TD-F2): F51–F54.
  - The writers still write `"0.1"` headers by default. A producer that writes `"1.0"` is now accepted by all three SDKs.
  - **G-1:** the TypeScript and Rust SDKs run the control profile `fep-0005` (all CTL rules that the suite checks). Python = TypeScript = Rust on all 281 vectors of `v0.1` … `fep-0005`.
  - **TD-12 (new rule text, SHOULD NOT and MUST NOT):** no blank candidate in `shown` of a 1.x text `OFFER`, `ASK` or `OFFER_WORDS`; a consumer drops a blank candidate (6.3). The validators report the producer part as an advisory warning (`FEP1-TD-SHOWN`). New vectors F55 and F56 (accept).
  - **CTL-S7 check:** the `fep-0005` log check now follows the rule text. An intent COMMIT is refused while the control is not engaged: before the first engage, and after a stop until a higher `engagement` (7.4.6). Before, the check refused it only after a stop. New vectors E20 (reject) and E21 (accept). The SDK `DecisionTracker` (TypeScript, Rust) now tracks control decisions.

### 1.2 Key words
The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY and OPTIONAL are to be read as in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when they are in capitals.

### 1.3 Rule ids
Each normative statement has an id in square brackets, for example **[FRM-4]**. Appendix C maps each id to the conformance checks and vectors that test it. Ids are stable within 1.x: a later version can add ids and deprecate ids, but it does not reuse an id for another rule.

### 1.4 Terms
| Term | Meaning |
|---|---|
| **Stream** | One header plus a sequence of events (section 2). |
| **Producer** | A program that writes a stream (a decoder, an adapter, a replay tool). |
| **Consumer** | A program that reads a stream (a trust layer, a UI, a benchmark, a validator). |
| **Trust layer** | A consumer that turns input events into `trust_decision` events (section 6). |
| **Decision log** | A JSON Lines file in which every line is a `trust_decision` (no header). |
| **Bridge** | A program that acts on decisions: it types text, actuates an intent, or moves something. |
| **Profile** | A named group of event kinds and rules on top of the core: `text`, `intent`, `control` (section 7). |
| **Binding** | A mapping of NTS to a transport: files, LSL, WebSocket (section 8). |
| **Segment** | The events between two boundaries (`segment_end`, `end` or `header`). One utterance in the text profile. |
| **Decision unit** | One intent decision (7.3). |
| **Tick** | One control update (7.4). |
| **White space** | The code points U+0009–U+000D, U+001C–U+001F, U+0020, U+0085, U+00A0, U+1680, U+2000–U+200A, U+2028, U+2029, U+202F, U+205F and U+3000. (This is the set of Python `str.isspace`; the three reference SDKs use it.) |
| **Blank text** | A string that is empty or has only white space. |

### 1.5 Stability levels
Each part has one stability level, as in OpenTelemetry.

| Level | Meaning |
|---|---|
| **Development** | Can change or go away in any release. |
| **Stable** | No breaking change within one major version. |
| **Deprecated** | Still works. A replacement exists. A Deprecated Stable part stays at least **12 months** after the release that deprecates it. |
| **Removed** | No longer in the spec. |

In this RC, a part is either **proposed Stable** (it becomes Stable when 1.0 is final) or **Development** (it stays Development in 1.0). Section 2.3 lists them.

### 1.6 Changes from RC3
RC4 answers the open questions SC-2 … SC-8 of the semantic-convention registry (roadmap P1-04, [registry](semconv/registry.md)) and closes gap G-12 of Appendix C.2. The rule for each answer is the RC3 rule: write down what the three SDKs already do, if that is safe; else pick the simplest rule that keeps valid data valid and change all three SDKs. Every behaviour change has accept and reject vectors, and Python = TypeScript = Rust on all of them (9.5). Normative changes: [FEP-0008](feps/0008-optional-field-types-and-semconv.md).

| Item | Answer | Rules | Vectors | SDK change |
|---|---|---|---|---|
| **SC-1** Modality keys | **Deferred** to a FEP that has evidence from real producers (the P4 adapters). The namespaces stay planned, with no keys. | 12.5, A.8 | — | No |
| **SC-2** Planned namespaces | **Reserved now.** `emg`, `eeg`, `meg`, `fnirs`, `implant` are reserved like the namespaces with keys. A custom key in them gets the MET-3 warning (advisory, never a reject). | MET-3, 12.5 | V69 (accept, with a warning) | Yes: the namespace warning of all three validators includes the planned namespaces |
| **SC-3** Empty strings | **"" is not valid** for the string keys of 3.4: they are "non-empty string". This writes down the validators (all three already refused ""). The keys of 6.1.1 and 6.1.2 stay "string" (audit data, TD-13). | MET-7, table 3.4 | (existing behaviour) | No |
| **SC-4** Open or closed value lists | **Per key.** Open lists (registered values; other values are valid): `device.regulatory_status`, `decoder.calibration_method`, `input.kind`, `declaration.mode`. Closed lists: `device.modality`, `declaration.status`, `declaration.where`. | MET-8, tables 3.4, 6.1.1, 6.1.2 | (existing behaviour) | No |
| **SC-5** Target stability of `input` and `declaration` keys | **Development** in 1.0. | 2.3 | — | No |
| **SC-6** Units | A key has a unit only if it is a physical quantity. Times are seconds (`s`, TIM-1). A count, an index, a flag, an identifier or a text has no unit. | MET-9 | — | No |
| **SC-7** Which form is normative | **The YAML registry** ([`semconv/`](semconv/registry.md)) is normative for key names, types, value lists and validators. The key tables of 3.4, 6.1.1 and 6.1.2 are informative copies; a CI check keeps them equal. The rules about the keys stay in this text. | MET-10; A.1 item 9 | (CI job `semconv`) | No (tooling) |
| **SC-8** Generated SDK constants | **No spec change.** An SDK may hand-write or generate its key table; the CI check compares all three with the registry (keys, validators, modality list, planned namespaces). | MET-10 | — | Tooling: the check now also compares the planned namespaces |
| **G-12** Optional fields that no validator checked | **The type of the field table applies** (GEN-11). The three validators now check: `segment_end.reason`; `hypothesis.t_start`, `t_end`, `revision_of`; `nbest[].spans`; `signal_quality.channels`; `pointer.absent`, `score`, `score_semantics`; `decision.score` and `score_range` for every semantics; header `vocab_id`, `vocab_version`; `trust_decision.reason`; intent `vocab_id`, `pending_cleared`; control `level` without `radius`; the latency fields of 5.2 on every event (frames included). | GEN-11, HDR-16, SEG-6, SQ-1, DEC-6, HYP-5, PTR-1, TIM-4, TD-F2, INT-T8, CTL-T8 | V69 … V82, F63 … F66, D24 … D26, I25, C25, E25 … E27 | Yes: all three validators |

Also in RC4:
- **No valid data changes.** Every RC3 vector keeps its verdict. Each new check refuses only a value that the generated JSON Schema already refused (C.3), so no accept vector and no reference producer output changes. A stream that RC3 validators accepted can now be refused only if one of these optional fields had a wrong type.
- **Control decision `t`** is listed in 7.4.5 (a number; the SDKs already checked it). On another profile it is a custom key (PRF-5); the proto field now has `json_profile = "control"`.
- **Not changed:** binding versions (`nts-lsl/0.1`, `nts-ws/0.1`), the enumeration registries and their fallbacks, and every rule of RC3 not named above.
- **Informative parts brought up to date:** the vector counts of 2.3, 9.3 and 9.5 (330 vectors), C.1, C.2 (G-12 closed; new G-13), C.3 (201 of 201 one-line verdicts) and Appendix A (A.1 item 9; new A.8).

**Amendment 1 of 2026-11-16 (still RC4 DRAFT; [FEP-0009](feps/0009-modality-semantic-conventions.md)).** Additive only; no RC4 vector changed its verdict.

| Item | Answer | Rules | Vectors | SDK change |
|---|---|---|---|---|
| **SC-1** Modality keys (partly) | 8 optional Development keys from producer evidence: `emg.placement`, `emg.derivation`, `meg.sensor_types`, `implant.array_type`, `implant.array_count`, `implant.features`, `implant.bin_s`, `implant.areas`. `emg`, `meg` and `implant` are now namespaces with keys; `eeg` and `fnirs` stay planned (SC-9). | MET-11, table 3.4, 12.5 | V83, V84, V85 (accept), V86, V87 (reject) | Yes: the three validators check the types (new type "list of non-empty strings") |
| **G-13** (b) control `absent: null` | The generated JSON Schema accepts `absent: null` (GEN-9 already allowed it; the SDKs read it as absent). Part (a) stays open (C.2). | GEN-9, CTL-4 | C26 (accept) | No (schema only) |

- A stream that wrote a wrong-typed custom key with one of these 8 names (MET-3 said SHOULD NOT) is now refused. No reference producer wrote one.
- Vector counts: 336 (v0.1 87, fep-0005 53). Python = TypeScript = Rust on all 336 and on 27,047 fuzz mutants (seeds 1–3, `--n 30`, 0 differences). Schema parity (C.3): 205 of 205 one-line verdicts. Informative parts updated: 2.3, 9.5, C.2 (G-13), C.3, A.8 (SC-1, SC-9).

**Amendment 2 of 2026-11-16 (still RC4 DRAFT; gap G-13 part a, roadmap P1-14).** Option A2 of C.2 applies. No earlier vector changed its verdict.

| Item | Answer | Rules | Vectors | SDK change |
|---|---|---|---|---|
| **G-13** (a) dense frame with sparse keys | **Option A2.** A dense frame MAY also carry sparse keys. The dense form wins: a consumer uses `log_probs` and does not use the sparse keys. Each sparse key that is present MUST still have its type (GEN-11): `top_ids` a list of unique integers ≥ 0, `top_log_probs` a list of numbers or null, `rest_log_prob` a number or null. The generated JSON Schema already checked these types, so it does not change. G-13 is closed. | FRM-2, GEN-11 | V88 (accept), V89 … V92 (reject) | Yes: the three validators (file readers and streaming validators) check the types |

- A stream with a dense frame and a wrong-typed sparse key is now refused (NTS-JSONL-FRAME). The schema refused it already (C.3). No reference producer writes sparse keys on a dense frame.
- Vector counts: 341 (v0.1 92). Python = TypeScript = Rust on all 341 and on 27,497 fuzz mutants (seeds 1–3, `--n 30`, 0 differences). Schema parity (C.3): 210 of 210 one-line verdicts. Informative parts updated: 2.3, 9.5, C.1 (FRM-2), C.2 (G-13), C.3.

**Amendment 3 of 2026-11-17 (still RC4 DRAFT; roadmap P7-02 and P1-16).** Additive only. No earlier vector and no earlier kit entry changed its verdict.

| Item | Answer | Rules | Vectors / kit | SDK change |
|---|---|---|---|---|
| **Implementation levels** (P7-02) | Three cumulative levels for a program: **NTS Core** (the frame core), **NTS Full** (all event kinds of the named output profiles), **NTS Trust-ready** (Full + score semantics, provenance and timing: the stream levels trust-ready and provenance, and the safety rules). Producer and consumer qualify by the kit and `nts-conform` (9.6). The stream levels of 9.2 get rule ids. | CNF-2 … CNF-7, 9.2, 9.6 | Kit 0.2.0: K33 … K36 (accept; stream levels core and trust-ready), `stream_level` on every input-stream entry | Yes: the v0.1 consumers of the three SDKs return `warnings` and `level` in their summary; `consume --level` in the TypeScript and Rust CLIs |
| **Self-certification** (P7-02) | A public, machine-readable list of implementations with a claimed level and the evidence (the `nts-conform` JSON report). A pull request adds an entry. | CNF-8, 9.7 | `conformance/certified.json` | No |
| **MET-11 check** (P1-16, gap 20) | An **advisory** check `NTS-MODALITY-MATCH`: a key of `emg`, `meg` or `implant` on a stream whose `device.modality` is not a modality of that namespace gives a warning, never a reject. MET-11 gets its C.1 row. | MET-11 | V93, V94, V96 (accept with the warning), V95 (accept, no warning); kit K32 | Yes: all three validators, same warning |

- The golden vectors of v0.1 can now pin the advisory warnings: `expected.warnings` (V93 … V96, and the v0.1 kit entries) is compared by the runners of all three SDKs, so the warning itself has three-way parity, not only the verdict.
- Vector counts: 345 (v0.1 96). Kit: 36 entries. Python = TypeScript = Rust on all 345, on the 36 kit entries and on 27,767 fuzz mutants (seeds 1–3, `--n 30`, 0 differences). Schema parity (C.3): 213 of 213 one-line verdicts. Informative parts updated: 2.3, 9.3, 9.5, C.1 (MET-11, CNF-2 … CNF-8), C.2, C.3.

**Amendment 4 of 2026-11-17 (still RC4 DRAFT; roadmap P14-17, gap 42).** A check that was missing. No rule changes. No earlier vector changed its verdict.

| Item | Answer | Rules | Vectors | SDK change |
|---|---|---|---|---|
| **TD-4 in the v0.1 suite** | The v0.1 suite read a `trust_decision` line in an input stream as an unknown event type and ignored it (6.2 rule 5). Only the `fep-0001` profile (`FEP1-TD-INPUT`) tested TD-4, so `fidetype validate`, `fidetype-ts validate` and `fidetype-rs validate` passed a file that `nts-conform check` failed. A new core check `NTS-TD-INPUT` tests TD-4 in the v0.1 suite. | TD-4 | V97 (reject) | Yes: the three v0.1 file validators and consumers reject the file |

- A stream with a `trust_decision` line next to its input events is now refused by the v0.1 consumers. `fidetype live --out` wrote such files before P14-17; it now writes the decisions to a separate decision log (`--decisions-out`).

**Amendment 5 of 2026-11-17 (still RC4 DRAFT; roadmap P3-10, gap 43, and P14-20, gap 46).** Two additions. No earlier vector changed its verdict. The binding version stays `nts-lsl/0.1`: a consumer of the earlier text already ignores an empty plain string (LSL-E3) and already moves its watermark with every sample.

| Item | Answer | Rules | Vectors | SDK change |
|---|---|---|---|---|
| **LSL merge wait** (P3-10) | The events stream is idle between markers, so the merge (LSL-C6) held every frame for the whole merge window: at the reference window (50 ms) the merge wait alone took the collector's added latency over its 50 ms budget. Now: an empty events-stream sample is a **heartbeat**. It is not an NTS event; it tells the consumer that the events stream has passed its timestamp. A producer with both streams SHOULD send one after each frame, with the frame's timestamp, and its events-stream timestamps MUST NOT decrease. **At equal times a frame goes before a marker**, so a producer can stamp a marker with the time of the frame before it and the merge releases the marker at once. | LSL-C7, LSL-C8 (new), LSL-C6 (note) | L36 (heartbeats), L37 (equal times) | Yes: the three LSL consumers (Python reference, TypeScript and Rust `fep-0002` runners) count heartbeats (`heartbeats`) and order equal times frame first. The Python producer (`NTSOutlet`, `replay-to-lsl`, `fidetype live --publish lsl`) sends heartbeats |
| **TD-4 in a live input stream** (P14-20) | A consumer that reads an input stream event by event (a streaming validator, a trust layer, a collector) **refuses** a `trust_decision` event between the header and `end`: it reports a TD-4 error for that event, does not use it as input and does not pass it on as input. After `end` the event is ignored like every other event (A5). Refuse, not ignore + warn: the file validators refuse the same stream (`NTS-TD-INPUT`), and a live consumer gives the same verdict as a file consumer. | TD-14 (new) | Streaming cases S01 … S06 (`conformance/streaming/td-input.json`); V97 event by event | Yes: Python `StreamingTrustLayer.push`, TypeScript and Rust `StreamValidator`, the collector's `validate` processor |

- Collector (FEP-0006): a refused `trust_decision` is an invalid input event: the `validate` processor cuts the open utterance (`gap`), and `fidetype-collector consume` rejects the file. Decisions of a stream that has no header are a decision log; TD-14 does not apply to them.
- Vector counts: 348 (fep-0002 37). Streaming cases: 6 (Python = TypeScript = Rust on all 6, and on V97). Informative parts updated: 8.2.5, 9.3, 9.5, C.1.

---

## 2. Scope and core data model

### 2.1 Scope
NTS is the output of any neural input decoder, with honest confidence, in a vendor-neutral data model plus shared field names (semantic conventions).
- The core is the **frame**: at each time frame, a probability distribution over a declared vocabulary.
- A vocabulary can hold characters, keys, words, phonemes, or commands and intents.
- A decoder can be a CTC decoder (with a blank token) or not.
- The device can have any modality: wrist EMG, EEG, MEG, OPM-MEG, ECoG, intracortical arrays, fNIRS, or a simulator.
- NTS also defines the output of a **trust layer** (`trust_decision`), so that bridges act only on decisions that a trust layer made final.

Out of scope:

| Topic | Where it belongs |
|---|---|
| Raw neural signals and their real-time transport | [LSL](https://labstreaminglayer.org/) |
| Raw neural data at rest | [BIDS](https://bids.neuroimaging.io/); ISO/IEC TS 27571 (Appendix D) |
| How a trust layer calibrates or decides (methods) | The trust layer. NTS defines only the decision format and the safety rules a decision must meet. |
| Final input events to an operating system | HID-level protocols (Appendix D) |

Design principles:
1. **80/20.** Define the small set of fields that most decoders need. Put the rest in `meta`.
2. **Adoption first.** A decoder that has log-softmax output already has most of the data.
3. **Do not reinvent.** Bridge to LSL, BIDS, EMMA and HID.
4. **Honest probabilities.** **[GEN-1]** A producer MUST NOT sharpen or smooth the probabilities for display. Consumers calibrate them.
5. **Say what a score means.** A number is a probability only if the stream says so (`score_semantics`, 4.6).
6. **No raw signal in the stream.** NTS carries decoder output, not samples of the neural signal (10.2).

### 2.2 Stream model
A stream has one **header** and a sequence of **events**. The header holds the fields that do not change. The events are typed by `type`.

| Part | Content | Section | Profile |
|---|---|---|---|
| `header` | spec version, vocabulary, source, `meta`, clock, declarations | 3 | core |
| `frame` | a distribution over the vocabulary at one time (dense or sparse) | 4.2 | core |
| `segment_end` | the end of a segment (utterance, word, trial) | 4.3 | core |
| `end` | the end of the stream | 4.4 | core |
| `signal_quality` | the quality of the input signal, separate from confidence | 4.5 | core |
| `decision` | one discrete label with a score and its semantics | 4.6 | core (mapped by the intent profile) |
| `hypothesis` | text n-best list, revisions, evidence fields | 4.7 | text |
| `pointer` | continuous 1-D to 3-D movement (v0.1 form) | 4.8 | control |
| `intent`, `intent_feedback` | discrete intents with risk classes | 7.3 | intent |
| `control`, `control_enable` | continuous control with units, frame, uncertainty | 7.4 | control |
| `trust_decision` | trust layer output | 6 | text, intent, control |

### 2.3 Proposed stability in 1.0
| Part | 1.0 level | Why |
|---|---|---|
| Header core fields, `frame` (dense and sparse), `segment_end`, `end`, `signal_quality`, timing fields, `meta` conventions of 3.4 | proposed Stable | In all three SDKs; 96 v0.1 + 66 fep-0001 vectors; real-data replays (M4-06, M6-01, M6-11, M6-13) |
| `decision`, `hypothesis` with evidence fields and `decode_declaration` | proposed Stable | Same; streaming trust layer and replays |
| `trust_decision` (text profile), decision logs | proposed Stable | Same; LSL and WebSocket decisions channels |
| JSON Lines form (8.1) | proposed Stable | All SDKs, all vectors |
| NPZ form (8.1) | proposed Stable, **read only for new data** | Legacy frame-core files (roadmap decision: NPZ read only) |
| LSL binding `nts-lsl/0.1` (8.2) | proposed Stable | 35 vectors, three-way parity, 6.78 h soak (M6-13) |
| WebSocket binding `nts-ws/0.1` (8.3) | proposed Stable | 44 vectors, three-way parity; localhost only (LAN tests open) |
| Intent profile (7.3) | Development | One public data set (recast sEMG) plus a simulator |
| Control profile (7.4), `pointer` | Development | One public data set (MC_RTT); the declared level gave no motion; position control untested |
| `vocab_id` registry entries (12.4) | Development | No entries are published yet |
| Recommended `input` and `declaration` keys of `trust_decision` (6.1.1, 6.1.2) | Development | Audit data, not checked (TD-13); the reference layers write different shapes per route *(RC4, SC-5)* |

---

## 3. Header

### 3.1 Header fields
| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"header"` | Yes (JSON forms) | |
| `spec_version` | string | Yes | `"1.0"` for this version. `"0.1"` for v0.1 streams (Appendix B). |
| `vocab` | list of V strings | Yes | `vocab[i]` is the token of column i. The order is significant. |
| `vocab_type` | `char`, `key`, `word`, `phoneme`, `command`, `other` | Yes | The kind of token (table 3.2). Unknown values: VER-8. |
| `blank_id` | integer or null | Yes | The index of the CTC blank in `vocab`. `null`: no blank class; every column is a token. |
| `frame_period` | number > 0, or null | No | Nominal time between frames, seconds. `null` = absent (GEN-9). |
| `latency` | number ≥ 0, or null | No | Algorithmic lookahead of the decoder, seconds (5.2). `null` = absent (GEN-9). |
| `source` | non-empty string | No | Short producer name. Default `"unknown"`. |
| `meta` | JSON object | No | Semantic conventions (3.4) and custom keys. |
| `clock_domain` | `lsl`, `unix`, `monotonic`, `trial`, `other` | No | The clock of all times (5.3). Default `trial`. |
| `vocab_id`, `vocab_version` | string, or null | No | Registered vocabulary (3.3, 12.4). `null` = absent (GEN-9). |
| `decode_declaration` | object | No | Text profile (4.7.3). |
| `intent_declaration` | object | No | Intent profile (7.3.2). |
| `control_declaration` | object | No | Control profile (7.4.2). |
| `ws` | object | No | WebSocket binding record (8.3). Not part of the NTS header; the server removes it. |

Rules:
- **[HDR-1]** In the JSON forms, the header MUST be the first line or message. It MUST contain `"type": "header"`, `spec_version`, `vocab`, `vocab_type` and `blank_id`.
- **[HDR-2]** `spec_version` MUST be a version that the consumer supports (11.2).
- **[HDR-3]** `vocab` MUST be a list of strings. **[HDR-4]** The tokens MUST be unique.
- **[HDR-5]** `vocab_type` MUST be one of the values of table 3.2. (In a stream of a newer minor version, another string is allowed: VER-8.)
- **[HDR-6]** If `blank_id` is not null, it MUST be an integer in 0 … V−1.
- **[HDR-7]** If `source` is present, it MUST be a non-empty string. **[HDR-8]** If `meta` is present, it MUST be a JSON object.
- **[HDR-9]** `frame_period`, if present, MUST be finite and > 0. **[HDR-10]** `latency`, if present, MUST be finite and ≥ 0.
- **[HDR-11]** `clock_domain`, if present, MUST be one of the values of 5.3 (unknown values of a newer minor version: VER-8).
- **[HDR-12]** V MAY be 0 only if the stream has no frames (for example a hypothesis-only or control-only producer). *(Resolution A10.)*
- **[HDR-13]** A consumer that decodes frames MUST NOT fail on `blank_id = null`. A greedy (best-path) decoder then takes the argmax of each frame and collapses each run of equal argmax frames into one token. It removes nothing.

### 3.2 `vocab_type` values
| Value | Tokens are | Example |
|---|---|---|
| `char` | Characters of a written language | `"a"`, `" "` |
| `key` | Keys of a physical or virtual keyboard | `"KeyA"`, `"Backspace"` |
| `word` | Whole words from a closed list | `"water"` |
| `phoneme` | Phonemes (ARPABET, IPA) | `"AH"` |
| `command` | Commands or intents | `"intent.select"` |
| `other` | Anything else; describe it in `meta` | — |

- **[HDR-14]** `vocab_type` describes the **meaning** of the tokens, not their spelling. A producer that encodes phonemes as one letter each still uses `phoneme`. *(Resolution A3.)*
- The blank token and any "rest" token are normal entries of `vocab`. The spec reserves no token string.

### 3.3 Vocabulary identity
- `vocab_id` names a registered vocabulary (namespaces in 12.4), for example `char.b2q-28`. `vocab_version` is its version.
- **[HDR-15]** If `vocab_id` is present, `vocab` MUST still be present. If the id names a registered entry, `vocab` MUST match it.
- **[HDR-16]** **(New in RC4.)** `vocab_id` and `vocab_version`, if present, MUST be strings or null (GEN-9, GEN-11). *(Gap G-12: the validators did not check the type.)*

### 3.4 Semantic conventions for `meta`
Rules:
- **[MET-1]** Keys are namespaced with dots (`<namespace>.<name>`, `snake_case`). A key of the table below MUST have the type and meaning given here.
- **[MET-2]** Values MUST be JSON values (no NaN, no infinity).
- **[MET-3]** Producers MAY add their own keys. A custom key SHOULD use a namespace that is not in the table (for example `acme.gain`). The namespaces of the table and the planned modality namespaces of 12.5 (`emg`, `eeg`, `meg`, `fnirs`, `implant`) are **reserved** for keys that this spec or a later version defines. A producer SHOULD NOT add new keys in a reserved namespace; a consumer accepts them and MAY warn. *(Resolution A2. RC4, SC-2: the planned namespaces are reserved too; the validators warn.)*
- **[MET-4]** `decoder.lookahead_s` and `latency`: if both are present, they MUST be equal.
- **[MET-5]** `decoder.causal = true` means: frame t uses no signal after `frame_times[t] + latency`, with an absent `latency` read as 0. A decoder with a bounded window after the frame time is causal with `latency` = the window. A full-sequence (offline) decoder SHOULD set `decoder.causal = false` and SHOULD omit `latency`. *(Resolution A1.)*
- **[MET-6]** If `calibration.applied` is true, `decoder.calibration_method` SHOULD be present and not `none`; a producer MUST NOT set `calibration.applied = true` unless a calibration step ran.
- **[MET-7]** **(New in RC4.)** A key of type "non-empty string" MUST NOT be `""`. *(SC-3. It writes down the three validators, which already refused `""`. An empty name, version or id carries no information, and an empty `stream.id` is not unique.)*
- **[MET-8]** **(New in RC4.)** A key of type `enum` has a **closed** list: in 1.0 data another value is an error (VER-7); in newer-minor data it gets the fallback of 12.3 (VER-8). A key of type string with an **open list** names registered values; another value is valid, and a consumer MUST NOT read it as one of the registered values. Open lists: `device.regulatory_status`, `decoder.calibration_method` (3.4), `input.kind` (6.1.1), `declaration.mode` (6.1.2). *(SC-4.)*
- **[MET-9]** **(New in RC4.)** A key has a unit only if it is a physical quantity. Times and durations are in seconds (TIM-1); the key name then ends in `_s` or the table says so. A count (`device.channel_count`), an index (`input.frame_range`), a flag, an identifier or a text has no unit. *(SC-6.)*
- **[MET-10]** **(New in RC4.)** The semantic-convention registry [`spec/semconv/`](semconv/registry.md) (YAML: `manifest.yaml`, `attributes/*.yaml`) is **normative** for the key names, types, value lists and validator rules of 3.4, 6.1.1 and 6.1.2. The key tables of this document are informative copies. The check `tools/semconv/semconv.py --check` (CI) keeps them equal, and also compares the key tables of the three reference SDKs. If a table and the registry differ, the registry applies and the table has an erratum. The rules MET-1 … MET-9, MET-11 and TD-13 stay normative in this text. *(SC-7, SC-8. Why the registry: tools and the SDKs read it, it holds the validator of each key, and it is the form that later keys (SC-1) go into; the tables stay here for readers.)*

| Key | Type | Values / meaning |
|---|---|---|
| `device.modality` | enum | Closed list: `emg`, `eeg`, `meg`, `opm-meg`, `ecog`, `intracortical`, `fnirs`, `other` |
| `device.vendor`, `device.model` | non-empty string | Maker and model of the recording device |
| `device.channel_count` | integer ≥ 1 | Input channels that the decoder used |
| `device.invasive` | boolean | `true` for implanted electrodes |
| `device.regulatory_status` | non-empty string | Open list (MET-8). Registered: `research`, `investigational`, `cleared`, `consumer`, `unknown`. Information only, not a claim of approval |
| `decoder.name`, `decoder.version` | non-empty string | Decoder or model, and its version |
| `decoder.causal` | boolean | See MET-5 |
| `decoder.lookahead_s` | number ≥ 0 | See MET-4 |
| `decoder.calibration_id` | non-empty string | Identifier of the calibration that was applied |
| `decoder.calibration_method` | non-empty string | Open list (MET-8). Registered: `temperature`, `platt`, `isotonic`, `none` |
| `decoder.weights_sha256` | string | SHA-256 of the weights file, 64 lowercase hex characters |
| `adapter.name`, `adapter.version` | non-empty string | The adapter that converted device or dataset output into NTS. SHOULD be both present or both absent |
| `stream.id` | non-empty string | Opaque unique id of the stream. MUST NOT contain personal data |
| `lm.name` | non-empty string | The language model inside the decoder; `"none"` if there is none |
| `user.personalized` | boolean | `true` if the decoder was adapted to this user |
| `session.id`, `subject.id` | non-empty string | Pseudonymous ids (10.3) |
| `language` | string | BCP 47 tag of the decoded text |
| `calibration.applied` | boolean | A calibration step changed the probabilities after the decoder. Default `false` |
| `data.derived` | boolean | The stream holds only data derived from neural signals, no raw samples. SHOULD be `true` |
| `consent.ref` | non-empty string | Opaque reference to a consent record kept elsewhere |
| `emg.placement` | non-empty string | Open list (MET-8). Registered: `wrist`, `forearm`, `face`, `neck`. Where the surface EMG electrodes are on the body |
| `emg.derivation` | non-empty string | Open list (MET-8). Registered: `bipolar` (also called differential), `monopolar` |
| `meg.sensor_types` | list of non-empty strings | Open list (MET-8). Registered: `magnetometer`, `planar_gradiometer`, `axial_gradiometer`. The sensor kinds that the decoder used; an OPM sensor is a magnetometer |
| `implant.array_type` | non-empty string | Open list (MET-8). Registered: `utah` (Utah microelectrode array) |
| `implant.array_count` | integer ≥ 1 | Implanted arrays that the decoder used |
| `implant.features` | list of non-empty strings | Open list (MET-8). Registered: `threshold_crossings`, `spike_band_power`, `sorted_units`. The neural features that the decoder used |
| `implant.bin_s` | number ≥ 0 | Width of one feature bin, seconds |
| `implant.areas` | list of non-empty strings | Brain areas of the arrays, free text (for example `precentral gyrus`, `6v`, `M1`) |

- **[MET-11]** **(Added to RC4 on 2026-11-16, [FEP-0009](feps/0009-modality-semantic-conventions.md).)** **Modality keys.** A key of the namespaces `emg`, `meg` and `implant` describes the recording of `device.modality`: `emg.*` goes with `emg`; `meg.*` with `meg` or `opm-meg`; `implant.*` with `intracortical` or `ecog`. A producer SHOULD NOT write the keys of another modality. All modality keys are optional and Development. A list key (`meg.sensor_types`, `implant.features`, `implant.areas`) is a JSON array of non-empty strings (MET-7 for each item). *(SC-1. The keys come from the reference adapters, the producer evidence that RC4 asked for: emg2qwerty, KT-sEMG and Toronto sEMG (`emg`); SpanishBCBL MEG (`meg`); Willett handwriting and Brain-to-Text '25 (`implant`), checked against NLB MC_RTT. The validators check the types (NTS-META-TYPES). Amendment 3 (2026-11-17): the modality match is the advisory check NTS-MODALITY-MATCH of all three validators; `meg.*` goes with `meg` and `opm-meg`, and every modality key gets the warning on `device.modality = other`. Without `device.modality` (or with a value of a newer minor version) the check does not apply.)*

*Informative.* The table is a copy of the registry (MET-10); [registry.md](semconv/registry.md) adds the validator, the requirement level per conformance level and the stability of each key. Older reference producers used flat keys (`subject`, `session`). These are not conventions. A 1.0 producer uses `subject.id` and `session.id`.

---

## 4. Events

### 4.1 JSON encoding (all JSON forms)
- **[GEN-2]** A line or message MUST be one UTF-8 JSON object with a string `type`. The tokens `NaN`, `Infinity` and `-Infinity` are not JSON and MUST NOT appear.
- **[GEN-3]** In a log-probability field, `null` MUST mean `-inf`.
- **[GEN-4]** A consumer MUST ignore unknown keys and unknown event `type` values.
- **[GEN-5]** **Integers.** A field of type integer MUST be written as a JSON number with no fraction part and no exponent (`3`, not `3.0` or `3e0`). A boolean is not a number. *(New text in 1.0. It writes down the behaviour of the three reference SDKs; see the SDK parity notes.)*
- **[GEN-6]** **Empty lines.** A consumer MUST ignore an empty (or white-space) line in JSON Lines. A producer SHOULD NOT write one. *(Resolution A4.)*
- **[GEN-7]** **After `end`.** A consumer MUST ignore lines after an `end` event, and MAY warn. A `header` event after the first header (and before `end`) starts a new stream (4.4). *(Resolution A5.)*
- **[GEN-9]** **(New in RC3.) JSON `null`.** A field MAY be `null` only if its type in the field table says "or null". `null` then means `-inf` in a log-probability field (GEN-3), and "no value" in every other field (the same as an absent key; for a required field such as `p_top1` or `blank_id`, the key stays present). Elsewhere `null` is a wrong type. *(Resolution of Q-1. It writes down the SDK behaviour: `frame_period`, `latency`, `vocab_id`, `vocab_version`, intent `threshold` and `role`, feedback `intent` and control `absent` were read as "no value" when `null`; their types now say so.)*
- **[GEN-10]** **(New in RC3.) Integer range.** A field of type integer MUST have a value in −(2^53 − 1) … 2^53 − 1 (−9007199254740991 … 9007199254740991). A consumer MUST treat a larger value as "not an integer" and refuse it where an integer is required. *Why:* JavaScript reads JSON numbers as IEEE 754 doubles, so 2^53 and 2^53 + 1 read as the same value; a `seq` check (TD-5) would then differ between SDKs. The binary form keeps `uint64` (proto README section 4). *(Resolution of Q-5.)*
- **[GEN-11]** **(New in RC4.)** **Optional fields.** An optional field that a field table of this document defines MUST have the type of that table when it is present, as a required field does. A consumer MUST refuse a wrong type. Exceptions: a field of another profile (PRF-5) and an unknown key (GEN-4) have no type. *(Gap G-12: the validators did not check some optional fields. The generated JSON Schema already checked them, so no valid stream changes.)*

### 4.2 `frame`
| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"frame"` | Yes | |
| `t` | number | Yes | Frame time, seconds (5.1) |
| `log_probs` | list of V numbers or null | Dense form | Natural-log probabilities; `null` = `-inf` |
| `top_ids`, `top_log_probs`, `rest_log_prob` | list of k integers, list of k numbers, number or null | Sparse form | k token indices, their log-probabilities, log of the rest mass (`null` = `-inf`) |

Rules:
- **[FRM-1]** A dense frame MUST have exactly V values. **[FRM-2]** A sparse frame uses the sparse keys instead of `log_probs`. **(Amended in RC4, gap G-13 a.)** A dense frame (with `log_probs`) MAY also carry sparse keys. Then the dense form wins: a consumer MUST use `log_probs` and MUST NOT use the sparse keys, and FRM-3, FRM-5 and the rule `top_ids` < V do not apply to them. Each sparse key that is present MUST still have the type of the table above (GEN-11): `top_ids` a list of unique integers ≥ 0, `top_log_probs` a list of numbers or null, `rest_log_prob` a number or null. A consumer MUST refuse a wrong type.
- **[FRM-3]** **Normalisation.** Each frame MUST log-sum-exp to 0 with a tolerance of **1e-3**: |log Σᵢ exp(log_probs[i])| ≤ 1e-3. For a sparse frame, the sum is over the k values plus `rest_log_prob`. A producer whose model gives logits MUST apply `log_softmax` first.
- **[FRM-4]** Log-probabilities MUST NOT be NaN or `+inf`. They MAY be `-inf`.
- **[FRM-5]** A consumer that needs a dense row from a sparse frame MUST spread the rest mass uniformly over the other V − k tokens, unless it has a better model. With k = V, the rest mass counts for FRM-3, and the dense row ignores it.
- **[FRM-6]** A frame is final when it is sent. NTS has no frame revision. A decoder with lookahead sends frame t after its lookahead and declares the lookahead in `latency`. *(Resolution of v0.1 question 4; FRM-6 follows from TIM-2.)*

Array form (NPZ, and the `NeuralTextStream` class): T frames are stored together as `log_probs` [T, V] and `frame_times` [T].
- **[FRM-7]** `log_probs` MUST have 2 dimensions [T, V]. **[FRM-8]** V MUST equal the length of `vocab`. **[FRM-9]** `frame_times` MUST have shape [T]. T MAY be 0.

### 4.3 `segment_end`
| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"segment_end"` | Yes | |
| `t` | number | No | Signal time of the boundary |
| `unit` | `utterance` (default), `word`, `trial` | No | Unknown values: VER-8 |
| `reason` | string | No | Why the segment ended: a short code, no personal content. Open list; registered code: `gap` (LSL-G1) |

- **[SEG-1]** A producer MAY send `segment_end` after the last event of a segment.
- **[SEG-2]** A consumer that decides per segment MUST treat all events between two boundaries (or between the header and the first boundary) as one segment. `end` and a new `header` also close the open segment.
- **[SEG-3]** A segment with no frame and no hypothesis carries no input. A consumer SHOULD NOT emit a decision for it.
- **[SEG-4]** If present, `t` MUST be a finite number and MUST NOT be less than the `t` of the last frame of the segment. **[SEG-5]** `unit` MUST be one of the three values (unknown values of a newer minor version: VER-8; such a boundary still closes the segment, SEG-2).
- **[SEG-6]** **(New in RC3.)** `reason`, if present, MUST be a string. It MUST NOT carry personal text (SEC-5). A consumer MUST NOT change its segment rules because of `reason`: every `segment_end` is a boundary (SEG-2). *(Resolution of Q-2: the LSL binding already writes `reason = "gap"`, LSL-G1. RC4: the validators check the type, GEN-11.)*

### 4.4 `end` and stream boundaries
- `{"type": "end"}` marks the end of the stream. **[GEN-8]** A stream MAY end without an `end` event (for example when a connection drops). A consumer MUST NOT emit a final decision on a segment that a transport loss cut (8.2, 8.3).
- A `header` event after the first header starts a new stream with its own clock and vocabulary.

### 4.5 `signal_quality`
| Field | Type | Required | Description |
|---|---|---|---|
| `t` | number | Yes | |
| `value` | number | Yes | For `unit = "index"`: in [0, 1], 1 is best |
| `unit` | `index`, `snr_db`, `impedance_ohm`, `other` | Yes | |
| `channels` | list of numbers | No | Per-channel values in the same unit |

- **[SQ-1]** The fields MUST have these types; an `index` value MUST be in [0, 1]. `channels`, if present, MUST be a list of numbers. *(RC4: the validators check `channels`, GEN-11.)*
- **[SQ-2]** A consumer MUST NOT fold signal quality into log-probabilities or scores. It MAY use it as a separate input, for example to abstain or hold.

### 4.6 `decision` and `score_semantics`
A decision is one discrete decoder output ("the user selected X").

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | string | Yes | The selected token. SHOULD be in `vocab` |
| `t` | number | Yes | |
| `score` | number or null | No | The vendor's score |
| `score_semantics` | enum | Yes | Table below |
| `score_range` | [min, max] | If `power` or `strength` | |

| `score_semantics` | Meaning |
|---|---|
| `calibrated_prob` | Probability in [0, 1], calibrated on held-out data |
| `uncalibrated_prob` | Probability in [0, 1], not calibrated |
| `power` | Non-negative magnitude, not a probability |
| `strength` | Ordinal strength on a fixed scale (for example Apple BCI HID 0–255) |
| `none` | No score; `score` is null or absent |

- **[DEC-1]** A consumer MUST NOT treat `score` as a probability unless `score_semantics` is `calibrated_prob` or `uncalibrated_prob`.
- **[DEC-2]** With a probability semantics, `score` MUST be in [0, 1]. **[DEC-3]** With `power` or `strength`, `score_range` MUST be present. **[DEC-4]** With `none`, `score` MUST be null or absent.
- **[DEC-5]** A producer MUST NOT label a score `calibrated_prob` unless a calibration step ran. It SHOULD then set `decoder.calibration_id` and `decoder.calibration_method`.
- **[DEC-6]** **(New in RC4.)** For every `score_semantics`, also an unknown one of a newer minor version (VER-8): `score`, if present, MUST be a number or null, and `score_range`, if present, MUST be a list of two numbers [min, max]. *(Gap G-12: the validators checked `score_range` only for `power` and `strength`, and the type of `score` only for a probability.)*

### 4.7 `hypothesis` (text profile)
| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique in the stream |
| `nbest` | list | Yes | Best first. Item: `text`, `score`, optional `spans` and evidence fields (4.7.2) |
| `score_semantics` | enum | Yes | As in 4.6; `none` for raw log-scores |
| `is_final` | boolean | Yes | `false` while the decoder can still change the text |
| `revision_of` | string or null | No | Id of the hypothesis that this one replaces |
| `t_start`, `t_end` | number | No | Signal time covered |
| `decode_declaration` | object | No | Replaces the header declaration for this event (4.7.3) |

`spans` items: `{"char_start", "char_end" (exclusive), "t_start", "t_end", "score"}`: integers ≥ 0 (code points), numbers (seconds), number. Each key is optional.

#### 4.7.1 Rules
- **[HYP-1]** The required fields MUST be present with these types.
- **[HYP-2]** A consumer MUST treat a hypothesis with `is_final = false` as provisional. **[HYP-3]** A hypothesis with `revision_of` replaces the earlier one completely.
- **[HYP-4]** Hypothesis text is decoder output, not ground truth. The leakage rule (10.4) applies.
- **[HYP-5]** **(New in RC4.)** The optional fields MUST have their types when present: `t_start` and `t_end` numbers; `revision_of` a string or null; `spans` a list of objects whose keys have the types above. *(Gap G-12.)*

#### 4.7.2 Evidence fields on n-best items
| Field | Type | Description |
|---|---|---|
| `char_confidences` | list of numbers in [0, 1] | Per character of `text`: the posterior under the neural evidence only (no LM) |
| `logp_acoustic` | number ≤ 0 | Log-probability of `text` under the neural evidence only |
| `logp_lm` | number ≤ 0 | Log-probability of `text` under the LM only |

- **[EVD-1]** `char_confidences` MUST have exactly `len(text)` values, counted in Unicode code points. Each value MUST be a number in [0, 1].
- **[EVD-2]** A producer MUST NOT put an LM-fused value in `char_confidences`.
- **[EVD-3]** The `score` of each item MUST be a finite number when the item is meant for a trust layer.
- **[EVD-4]** `logp_acoustic` and `logp_lm`, if present, MUST be finite numbers ≤ 0.

#### 4.7.3 `decode_declaration`
| Field | Type | Required | Description |
|---|---|---|---|
| `decoder` | string | Yes | Id of the decoder that made the n-best list |
| `decoder_version` | string | No | |
| `frame_temperature` | number > 0 | No | Temperature T applied before decoding: `log_softmax(log_probs / T)`. Absent = 1.0 |
| `params` | object | No | Other decode parameters (beam, LM weight) |
| `config_id` | string | No | Id of the frozen trust configuration the producer decoded for |

- **[DCL-1]** The declaration MUST have this form.
- **[DCL-2]** A producer that sends hypotheses for a trust layer SHOULD send a declaration. **[DCL-3]** A hypothesis declaration replaces the header declaration for that event (no merge).
- **[DCL-4]** A producer that decodes for a frozen trust configuration MUST apply its frozen frame temperature before it decodes and MUST declare it.
- **[DCL-5]** A trust layer that reads declarations MUST compare them with its configuration: `config_id` (if declared) equal; `frame_temperature` (default 1.0) equal within relative tolerance 1e-9; `decoder`, `decoder_version` and each required `params` key equal if the layer requires them.
- **[DCL-6]** On a mismatch the layer MUST record it (the `declaration` field of the decision or its provenance) and SHOULD give ABSTAIN. A record-only mode MAY exist; it MUST still record the mismatch. A layer MAY treat a missing declaration as a mismatch.
- **[DCL-7]** `params` MUST NOT carry text of the user (a prompt, a target sentence).
- *Informative.* A declaration is a claim of the producer. It catches configuration mistakes, not a dishonest producer. On the frames route the layer decodes itself, and the declaration does not apply.

### 4.8 `pointer` (control profile, v0.1 form)
| Field | Type | Required | Description |
|---|---|---|---|
| `t` | number | Yes | |
| `dims` | integer 1–3 | Yes | |
| `mode` | `relative` or `absolute` | Yes | `relative`: change since the last event; `absolute`: position normalised to [0, 1] |
| `values` | list of `dims` numbers | Yes | |
| `absent` | list of `dims` booleans | No | `true`: no value for that axis; the value MUST be ignored |
| `score`, `score_semantics` | as 4.6 | No | |

- **[PTR-1]** The fields MUST have these types and lengths. On a stream with a `control_declaration`, see CTL-12. *(RC4: the validators check the optional fields too: `absent` is a list of `dims` booleans; `score_semantics`, if present, is a value of 4.6 (not null), and DEC-2 … DEC-4 and DEC-6 apply.)*

---

## 5. Timing and clocks

### 5.1 Frame and event times
- **[TIM-1]** All times are in **seconds**. Frame times MUST be finite.
- **[TIM-2]** Frame times MUST increase strictly from frame to frame (in the array form: `frame_times[t+1] > frame_times[t]`).
- **[TIM-3]** A consumer MUST use the frame times as the true times; `frame_period` is nominal.

### 5.2 Latency fields
`latency` (header) is the algorithmic lookahead: how much signal after `frame_times[t]` the decoder used for frame t. `0` is a causal decoder (MET-5). An event MAY carry the fields below.

| Field | Meaning |
|---|---|
| `t_signal_start` | Start of the signal window that the decoder used |
| `t_signal_end` | End of that window |
| `t_decoded` | When the decoder finished |
| `t_emitted` | When the producer sent the event |

- **[TIM-4]** When present, each of these fields MUST be a number, and `t_signal_start ≤ t_signal_end ≤ t_decoded ≤ t_emitted` MUST hold. End-to-end latency = `t_emitted − t_signal_end`. *(RC4: the validators check this on every event of 12.1 that a stream carries, frames included; before, only on `decision`, `hypothesis`, `pointer`, `signal_quality` and the control events.)*

### 5.3 Clock domains
`clock_domain` names the clock of all times in the stream: `lsl` (LSL clock), `unix` (seconds since 1970-01-01 UTC), `monotonic` (a local monotonic clock), `trial` (relative to the trial start; default), `other`.

### 5.4 Clocks in the bindings
| Binding | Event clock | Rule |
|---|---|---|
| Files | the header's `clock_domain` | — |
| LSL | `clock_domain = lsl` after the consumer | LSL-C1 … LSL-C6 (8.2.5) |
| WebSocket | the producer's clock, unchanged | WS-K1 … WS-K4 (8.3.8) |

- **[TIM-5]** Transport stamps (`ws_t_sent`, `ws_t_recv`, `lsl_t`) are not event times. A consumer MAY subtract two stamps only when both come from the same clock.
- *Informative.* NTS 1.0 does not define a mapping between two clock domains across devices (Appendix A, v0.1 question 8: deferred).

---

## 6. Trust decisions

### 6.1 The `trust_decision` event
A trust layer emits its decisions as `trust_decision` events: into a decision log, an LSL decisions stream (8.2.6) or a WebSocket decisions channel (8.3.6).

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `"trust_decision"` | Yes | |
| `spec_version` | string | **Yes for 1.0 producers** | The version of the rules this decision follows (11.2). Absent means `"0.1"`. |
| `profile` | `text` (default), `intent`, `control` | No | Section 7 |
| `is_final` | boolean | Yes | `false`: a provisional preview |
| `action` | `COMMIT`, `OFFER`, `ASK`, `ABSTAIN`, `OFFER_WORDS` | Yes | Intent and control profiles use a subset (7.3, 7.4) |
| `shown` | list of strings | No | Text profile: texts shown to the user; for `COMMIT`, `shown[0]` is the committed text |
| `p_top1` | number in [0, 1] or null | Yes | Confidence of the top candidate |
| `score_semantics` | enum (4.6) | Yes | A calibrated layer uses `calibrated_prob` |
| `set_size` | integer ≥ 0 | No | Conformal set size |
| `guard_risk` | number in [0, 1] or null | No | |
| `session`, `seq`, `utterance` | string, integer ≥ 0, integer ≥ 0 | No | Order within a session |
| `config_id` | string or null | No | Content id of the trust configuration |
| `input` | object | No | Reference to the input: recommended keys in 6.1.1 |
| `latency_s` | number ≥ 0 | No | Computation time of the decision |
| `declaration` | object | No | Result of the declaration check (DCL-5): recommended keys in 6.1.2 |
| `reason` | string | No | Short reason code or text, no personal content |

Other keys are allowed (for example `attempt`, the LSL record `lsl`, the WebSocket record `ws`).

#### 6.1.1 `input` keys (recommended)
| Key | Type | When | Meaning |
|---|---|---|---|
| `kind` | string | always | The input route. Open list (MET-8); registered: `frames`, `hypothesis`, `intent`, `decision`, `feedback`, `control`, `control_enable`, `timer` |
| `frame_range` | [integer, integer] | `frames` | Frame indices `[start, end)` of the segment |
| `t_range` | [number, number] | `frames` | Signal times of the first and the last frame |
| `hypothesis_id`, `revision_of` | string | `hypothesis` | The hypothesis that the decision used |
| `intent_id` | string | `intent` | The `intent` event id |
| `label` | string | `decision` | The label of the `decision` event |
| `tick` | integer | `control` | The input tick |
| `ref_unit`, `outcome`, `source` | integer, string, string | `feedback` | The `intent_feedback` that caused the decision |
| `score_semantics` | string | intent routes | The semantics of the input scores (INT-S2) |
| `sha256`, `hypothesis_sha256` | string (64 lowercase hex) | event routes | SHA-256 of the input event (canonical JSON) |

#### 6.1.2 `declaration` keys (recommended)
| Key | Type | Meaning |
|---|---|---|
| `status` | `match`, `mismatch`, `absent` | Result of the check (DCL-5). A consumer reads an unknown value as `mismatch` |
| `mode` | string | The layer's check mode. Open list (MET-8); registered (the reference layer): `off`, `warn`, `abstain`, `offer-only` |
| `where` | `header` or `hypothesis` | Where the checked declaration was (DCL-3). Closed list |
| `decoder` | string | The declared decoder id |
| `mismatches` | list of strings | One short text per mismatch (no user text, DCL-7) |

### 6.2 Format rules
- **[TD-F1]** `is_final` MUST be a boolean; `action` MUST be in the enum; `p_top1` MUST be present (number in [0, 1] or null); `score_semantics` MUST be present and in the enum. (A decision of a newer minor version MAY use other strings: VER-8.)
- **[TD-F2]** `shown`, if present, MUST be a list of strings. `set_size`, `seq` and `utterance` MUST be integers ≥ 0 (GEN-5, GEN-10). `guard_risk` MUST be in [0, 1] or null. `session` MUST be a string. `config_id` MUST be a string or null. `input` MUST be an object. `declaration` MUST be an object *(new in RC3, Q-4)*. `latency_s` MUST be a number ≥ 0. `reason` MUST be a string *(RC4, G-12)*.
- **[TD-F3]** `spec_version`, if present, MUST be `"0.1"` or `"1.<minor>"` (11.2).
- **[TD-13]** **(New in RC3.)** A trust layer SHOULD write the keys of 6.1.1 and 6.1.2 with the types given there. They are audit data. A consumer MUST NOT base an action on them, and MUST ignore keys that it does not know. *(Resolution of Q-4. The validators check only that both are objects, TD-F2.)*

### 6.3 Semantic rules (all profiles unless a profile says otherwise)
- **[TD-1]** **A consumer MUST NOT act on (commit, send, actuate) a `trust_decision` with `is_final = false`.**
- **[TD-2]** `score_semantics = "calibrated_prob"` follows DEC-5: a calibration step must have run.
- **[TD-3]** A bridge to a lossy output (Appendix D, HID) SHOULD forward only final `COMMIT` decisions, or a user selection after `OFFER`.
- **[TD-4]** `trust_decision` events are output. They MUST NOT appear in a stream that is fed back as decoder input. A decision log has no header.
- **[TD-5]** Within one `session`, `seq` MUST increase strictly, over all profiles. `utterance` MUST NOT decrease.
- **[TD-6]** A trust layer MUST emit at most one final decision per (`session`, `utterance`) (intent: per `unit`; control: 7.4).
- **[TD-7]** A trust layer MUST NOT emit a decision for an utterance after its final decision. After a final `ASK`, the retry is a new utterance.
- **[TD-8]** A `COMMIT` that carries `shown` MUST have at least one text.
- **[TD-9]** **(Stricter in 1.0.)** A 1.x trust layer **MUST NOT** emit a final text `COMMIT` whose committed text (`shown[0]`) is blank text (1.4). To show no text, it uses `ABSTAIN`. A bridge MUST NOT forward a blank committed text. For decisions that declare `spec_version` `"0.1"` or omit it, the 0.1 rule stays: SHOULD NOT, with a `reason` that says why (Appendix B). *Why:* in M2-18 the frozen Paper 1 v4 configuration committed 320 empty texts on 400 no-signal (uniform) T12 control streams. An empty COMMIT tells the user "the system understood you" when no text came from the neural evidence. The intent profile already forbids a null-intent COMMIT (INT-S1) and the control profile forbids motion on no-signal input (CTL-S2); TD-9 gives the text profile the same rule. A layer can meet it with a commit gate that turns such a COMMIT into the policy's non-commit decision; the gate only removes commits, so a fitted risk bound still holds (M2-18). *(Resolution of FEP-0001 question 6.)*
- **[TD-10]** A decision log or decisions channel MAY omit `shown` (privacy). A bridge then acts on no text.
- **[TD-14]** **(Amendment 5.)** A consumer that reads an input stream event by event (a streaming validator, a trust layer, a collector) MUST refuse a `trust_decision` event that comes after the header and before `end` (TD-4). It reports the refusal, does not use the event as input and does not pass it on as input; its state for the stream does not change because of the event. What it does with the rest of the stream is its rule for any refused event (for example the collector cuts the open utterance, FEP-0006). After `end` the event is ignored (A5). A decision log or a decisions channel (no header) is not an input stream. *Why:* the file validators refuse the same stream (`NTS-TD-INPUT`, amendment 4); a live consumer and a file consumer give the same verdict.
- **[TD-12]** **(New in RC2.)** A 1.x trust layer SHOULD NOT put blank text (1.4) in `shown` of a text `OFFER`, `ASK` or `OFFER_WORDS` decision. A consumer or a bridge MUST NOT offer a blank candidate to the user: it drops it. If no candidate is left, the user sees no text, as for `ABSTAIN`. For decisions that declare `spec_version` `"0.1"` or omit it, the producer part does not apply; the consumer part applies to decisions of every version (a dropped blank candidate removes no text that the user can read). *Why:* the commit gate of TD-9 turns a blank final COMMIT into the policy's non-commit decision. That decision can be an `OFFER` whose only candidate is the blank text (FEP-0006 question 2). A blank button tells the user that the system has a candidate when it has none. A validator reports a 1.x violation as a warning (advisory check `FEP1-TD-SHOWN`), not as a reject. *Note:* a producer that removes the blank candidates and has no candidate left emits `ABSTAIN` with `shown = []`. It does not omit `shown`, because a decision without `shown` reads as a privacy log (TD-10).

### 6.4 Decision logs and the reference consumer
- A decision log is a JSON Lines file of `trust_decision` lines only. **[TD-11]** A file that mixes `trust_decision` lines with input events and has no header is invalid.
- For a log, a consumer's "acted" list holds `shown[0]` of each final text COMMIT (null when `shown` is absent), each final intent COMMIT (`intent`), and each control COMMIT (moving tick). The vectors give the expected lists.

### 6.5 Provenance and audit (informative, with SHOULD rules)
- **[PRV-1]** A consumer that acts on decoded output SHOULD keep a provenance record for each final decision. The record links the decision to the stream (`stream.id`, or a content hash: SHA-256 over the canonical JSON header plus the `log_probs` and `frame_times` bytes), the frame range `[start, end)` or the input event hash, the provenance keys of `meta` (`device.*`, `adapter.*`, `decoder.*`, `lm.*`), the trust configuration id and the decision scores.
- **[PRV-2]** A record MUST NOT copy raw signals or frame arrays. It stores hashes and ids. It stores text only if the deployment allows it; otherwise a keyed hash (HMAC) or nothing.
- **[PRV-3]** A later user correction SHOULD be a new record that refers to the decision it corrects. An old record MUST NOT be changed.
- The reference is `fidetype.trust.provenance` (append-only JSON Lines with a SHA-256 hash chain).

---

## 7. Output profiles

### 7.1 Profile model
| Part | Events and fields |
|---|---|
| **Core** | `header` core fields, `frame`, `signal_quality`, `segment_end`, `end`, timing fields, `meta`, provenance |
| **Text profile** | `hypothesis` + evidence + `decode_declaration`; `trust_decision` without `profile` or with `profile = "text"` |
| **Intent profile** | `intent_declaration`; `intent`; `intent_feedback`; `decision` mapped to one-candidate intents; `trust_decision` with `profile = "intent"` |
| **Control profile** | `control_declaration`; `control`; `control_enable`; `pointer`; `trust_decision` with `profile = "control"` |

- **[PRF-1]** A stream MAY carry events of more than one profile. Each event belongs to exactly one profile, by its `type` and, for `trust_decision`, by `profile`.
- **[PRF-2]** A profile adds event kinds and conventions only. It MUST NOT change a core field or a field of another profile.
- **[PRF-3]** A `decision` with a label in the declared intents is an intent decision unit with one candidate. A `pointer` belongs to the control profile.
- **[PRF-4]** `profile`, if present, MUST be `text`, `intent` or `control`. A consumer that does not implement a profile MUST NOT act on its decisions (this includes an unknown profile, VER-8; a text consumer acts only on decisions without `profile` or with `profile = "text"`). *(The fep-0003 profile, which knows only `text` and `intent`, rejects `control`; so control decisions SHOULD go to their own decision stream or log, CTL-T3.)*
- **[PRF-5]** **(New in RC3.)** A field that a profile defines (the intent fields of 7.3.5, the control fields of 7.4.5) has its type and meaning only on decisions of that profile. On a decision of another profile it is a custom key (GEN-4): a consumer ignores it, unless a rule of the decision's profile forbids it (INT-T1, INT-T2, CTL-T1). A producer SHOULD NOT write it. *(Resolution of Q-6. It writes down the SDK behaviour: each profile checks its fields only on its own decisions.)*
- The format keeps the name **NeuralTextStream (NTS)** for all profiles. *(Resolution of FEP-0003 question 1.)*

### 7.2 Text profile
The text profile is sections 4.7 and 6 with no `profile` key (or `profile = "text"`). No extra rules.

### 7.3 Intent profile (Development)

#### 7.3.1 Terms
- **Decision unit**: one `intent` event, one `decision`, one segment of command frames, or one explicit feedback that executes an intent. Units are numbered 0, 1, 2, … per session (`unit`).
- **Arm**: a final OFFER with `confirm_required = true`. It waits for a confirmation. Arming does not act.

#### 7.3.2 `intent_declaration` (header)
| Field | Type | Required | Description |
|---|---|---|---|
| `vocab_id`, `vocab_version` | string | No | `intent.*` namespace (12.4) |
| `intents` | list | Yes | At least one |
| `intents[].id` | string | Yes | Unique. Convention `intent.<verb>[.<object>]` |
| `intents[].risk` | `safe`, `undoable`, `irreversible` | Yes | Producer's risk class |
| `intents[].role` | `action` (default), `null`, `confirm`, `cancel`, `undo` | No | |
| `intents[].label` | string | No | |

| Risk class | Meaning | Reference default limit |
|---|---|---|
| `safe` | A wrong action costs little | α 0.10 |
| `undoable` | A wrong action can be reversed by `undo` | α 0.05 |
| `irreversible` | A wrong action cannot be reversed | α 0.01 and confirmation (INT-S4) |

- **[INT-D1]** Intent ids MUST be unique. At least one intent MUST have a role other than `null`.
- **[INT-D2]** `risk` MUST be one of the three classes. **[INT-D3]** At most one intent each MAY have the roles `confirm`, `cancel` and `undo`.
- **[INT-D4]** If any intent is `irreversible`, the `confirm` intent (if present) MUST be `irreversible`.
- **[INT-D5]** On a `vocab_type = "command"` stream with a declaration, the tokens of `vocab` (without `blank_id`) MUST equal the declared ids (as sets).
- **[INT-D6]** A vocabulary SHOULD have a `null` intent if the decoder can see rest input. The decoder SHOULD be trained to output it on rest and no-signal input.

#### 7.3.3 `intent` event
| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique in the stream |
| `t` | number | Yes | |
| `t_start`, `t_end` | number | No | |
| `is_final` | boolean | Yes | |
| `revision_of` | string or null | No | |
| `score_semantics` | enum (4.6) | Yes | |
| `candidates` | list, at least one | Yes | `intent` (a declared id), `score` (number, or null/absent with `none`) |

- **[INT-E1]** An `intent` event MUST come after a header with an `intent_declaration`.
- **[INT-E2]** Every candidate intent MUST be declared. An intent MUST NOT appear twice.
- **[INT-E3]** With a probability semantics, every score MUST be in [0, 1] and the scores MUST sum to at most 1 (tolerance 1e-6); a consumer spreads the missing mass uniformly over the unlisted intents. With `none`, no candidate has a score. With `power` or `strength`, scores are finite numbers.
- **[INT-E4]** Scored candidates MUST be ranked best first. **[INT-E5]** `id` MUST be unique in the stream.
- **[INT-E6]** On a command stream, the frames of one segment form one decision unit.
- **[INT-E7]** The required fields MUST be present with these types.

#### 7.3.4 `intent_feedback` event
Fields: `ref_unit` (integer ≥ 0, required), `outcome` (`confirmed`, `cancelled`, `selected`, `undone`, `correct`, `wrong`; required; unknown values: VER-8), `intent` (string, or null; a string is required for `selected`), `t`, `source` (a channel such as `switch`, `touch`, `caregiver`, `eye-tracker`).
- **[INT-F1]** The fields MUST have this form. **[INT-F2]** Feedback MUST NOT carry free text of the user. `source` names a channel, never a person.

#### 7.3.5 Intent `trust_decision`
Fields of 6.1, plus: `profile = "intent"` (required), `unit` (required), `action` in `COMMIT`, `OFFER`, `ABSTAIN`; `intent` (string; for COMMIT), `offered` (list of strings; for OFFER), `risk_class` (risk class, or null; required for COMMIT), `threshold` (number in [0, 1], or null), `role` (intent role, or null), `confirm_required` (boolean), `confirmation_of` (integer ≥ 0; for an irreversible COMMIT), `confirmed_via` (`intent` or `feedback`), `undo_of` (integer ≥ 0), `pending_cleared` (string), `vocab_id` (string). `p_top1` is null for a COMMIT that an explicit feedback caused.

- **[INT-T1]** An intent decision MUST carry `profile = "intent"` and `unit`, and MUST NOT carry `utterance`.
- **[INT-T2]** It MUST NOT carry `shown` (so a text bridge can never type an intent id).
- **[INT-T3]** A COMMIT MUST carry `intent` and `risk_class`. An OFFER MUST carry a non-empty `offered`. `action` MUST be COMMIT, OFFER or ABSTAIN.
- **[INT-T4]** TD-1 and TD-5 … TD-7 apply with `unit` in place of `utterance`.
- **[INT-T5]** A bridge MUST actuate only final COMMITs. It MUST NOT actuate an OFFER.
- **[INT-T6]** Text and intent decisions of one session MAY share one log; they then share the `seq` counter.
- **[INT-T7]** **(New in RC3.)** `confirm_required`, if present, MUST be a boolean. It MAY be `true` only on an `OFFER` (an arm, 7.3.1). *(Resolution of Q-8: the three SDKs already refuse it on another action.)*
- **[INT-T8]** **(New in RC4.)** `vocab_id` and `pending_cleared`, if present, MUST be strings. *(Gap G-12.)*

#### 7.3.6 Intent safety rules
- **[INT-S1]** A trust layer MUST NOT COMMIT an intent whose role is `null`. It SHOULD NOT OFFER it.
- **[INT-S2]** A trust layer MUST NOT COMMIT on input whose `score_semantics` is `none`, `power` or `strength`, unless an explicit feedback confirms the intent. It MAY OFFER.
- **[INT-S3]** A COMMIT (and an arm) of class r needs `p_top1 ≥ threshold_r`. The thresholds SHOULD come from a finite-sample risk-control method on labelled units of the same user and session (reference: LTT or CRC). A class whose bound is infeasible MUST NOT commit (threshold = infinity).
- **[INT-S4]** A trust layer MUST NOT COMMIT an `irreversible` intent directly. It arms it. A later final COMMIT with `confirmation_of` = that unit executes it, when (a) the next unit is the `confirm` intent and passes the `irreversible` threshold, or (b) an `intent_feedback` `confirmed` (or `selected`) arrives through another channel. Any other unit, a failed confirmation or `cancelled` drops the armed intent. An armed intent waits for the next unit only. One OFFER MUST NOT be confirmed twice. *(FEP-0003 questions 2, 3, 5: no change; Appendix A.)*
- **[INT-S5]** An undo COMMIT carries `undo_of` = the unit of an earlier final COMMIT of the session. It MUST NOT target an `irreversible` COMMIT.
- **[INT-S6]** A trust layer MUST NOT COMMIT when it knows the input carries no signal: (a) the top-1 intent is `null`; (b) the latest `signal_quality` index is below the configured minimum; (c) the distribution is uniform. A producer SHOULD send `signal_quality`. **[INT-S7]** **(Stricter in 1.0.)** A configuration that can arm `irreversible` intents MUST be fitted with a no-signal reference (decoder outputs on all-zero or rest input); other configurations SHOULD be. *Why:* in P12 a configuration fitted on clean sEMG data acted on 0.371 of zero-input presses (97 % wrong); with the reference, 0. *(Resolution of FEP-0003 question 4.)*
- **[INT-S8]** An evaluation MUST report commits on no-signal controls (uniform, zero input) next to the clean numbers.
- **[INT-S9]** A consumer MAY raise the risk class of an intent. It MUST NOT lower the declared class.
- **[INT-S10]** Every final intent decision SHOULD carry `config_id`, `input` (kind, input id, `score_semantics`, SHA-256 of the input event) and `vocab_id`.
- *Informative.* INT-S1, S2, S4 and S6 only remove COMMITs. A fitted risk bound still holds with them.

### 7.4 Control profile (Development)

#### 7.4.1 Terms
- **Tick**: one `control` event; `tick` increases strictly per stream.
- **Engage / stop**: `control_enable` with `enabled = true` / `false`. A stop is latched until the next engage.
- **Authority**: the decoder share of the commanded velocity, 0 to 1. It ramps up after an engage.
- **No-signal reference**: the decoder output on all-zero input.

#### 7.4.2 `control_declaration` (header)
| Field | Type | Required | Description |
|---|---|---|---|
| `dims` | integer 1–3 | Yes | |
| `quantity` | `velocity` or `position` | Yes | |
| `units` | string | Yes | Velocity: `norm/s`, `px/s`, `mm/s`, `m/s`, `deg/s`. Position: `norm`, `px`, `mm`, `m`, `deg` |
| `frame` | `screen` or `workspace` | Yes | `screen`: x right, y down, origin top-left. `workspace`: x right, y up, z towards the user; the producer documents the origin |
| `rate_hz` | number > 0 | Yes | |
| `axes` | list of `dims` strings | No | Default `x`, `y`, `z` |
| `uncertainty` | `none` or `std` | No | Default `none` |
| `max_speed` | number > 0 | No | Producer hint |
| `latency_s`, `window_s` | number ≥ 0 | No | |
| `click_intent` | string | No | The intent id that means "click" |

- **[CTL-D1]** The fields MUST have these types and values. `units` MUST fit `quantity`. `norm` position is defined only in the `screen` frame.
- **[CTL-D2]** `axes`, if present, MUST have `dims` unique names.
- **[CTL-D3]** `click_intent` MUST be declared in the `intent_declaration` of the same header, and its role MUST NOT be `null`.
- **[CTL-D4]** A control-only stream has no frames; its `vocab` is a placeholder (reference: `["control"]`, `command`, `blank_id = null`).

#### 7.4.3 `control` event
Fields: `t` (required), `tick` (integer ≥ 0, required), `values` (list of `dims` numbers; an absent axis MAY be null), `absent` (list of `dims` booleans, or null = absent, GEN-9), `std` (list of `dims` numbers > 0), `source` (`decoder` default, or `human`), `id`, timing fields of 5.2.

- **[CTL-1]** A `control` event MUST come after a header with a `control_declaration`.
- **[CTL-2]** For decoder events, `tick` and `t` MUST increase strictly.
- **[CTL-3]** With `uncertainty = std`, every decoder event MUST carry `std`. With `none`, no event carries `std`.
- **[CTL-4]** The fields MUST have the types and lengths of the table; a null value MUST have `absent = true` on its axis.
- **[CTL-12]** A `pointer` on a stream with a `control_declaration` MUST have `dims` equal to the declared `dims`. It is an unscored control input.
- *Informative.* `std` is decoder output, not truth. A trust layer calibrates it.

#### 7.4.4 `control_enable` event
Fields: `enabled` (boolean, required), `t`, `source` (`switch`, `caregiver`, `ui`, `voice`, `eye-tracker`, `watchdog`, `other`), `reason`.
- **[CTL-E1]** The fields MUST have this form. **[CTL-E2]** The decoder MUST NOT send `control_enable`. **[CTL-E3]** It MUST NOT carry personal text; `source` names a channel, never a person.

#### 7.4.5 Control `trust_decision`
Required: `profile = "control"`, `tick`, `is_final = true`, `action` (`COMMIT` = move, `ABSTAIN` = no motion), `state` (`act`, `attenuate`, `hold`, `stop`), `velocity`, `gain` (in [0, 1]), `units`, `v_max` (> 0), `ttl_s` (> 0), `engagement` (integer ≥ 0). Optional: `raw`, `radius`, `level`, `authority`, `t` (number: the time of the decision, seconds; listed in RC4, the SDKs already checked it), `reasons` (an open list of codes, CTL-T9; registered: `ok`, `shrunk`, `uncertain`, `no_signal`, `no_signal_reference`, `unscored`, `disengaged`, `not_engaged`, `stale_input`, `absent`, `handoff`, `clamp_speed`, `clamp_accel`), and the fields of 6.1. `p_top1` is null. `score_semantics` is `calibrated_prob` when a calibrated radius was used, else `none`.

- **[CTL-T1]** A control decision MUST carry `profile = "control"` and `tick`. It MUST NOT carry `shown`, `utterance` or `unit`.
- **[CTL-T2]** `is_final` MUST be `true`. **[CTL-T3]** `state` MUST fit `action` (`act`/`attenuate` ↔ COMMIT; `hold`/`stop` ↔ ABSTAIN). **[CTL-T4]** `v_max` and `ttl_s` MUST be present; the required fields MUST have these types.
- **[CTL-T5]** Within a session, `seq` increases strictly over all profiles. Ticks do not go back. One input tick moves at most once. A HOLD MAY repeat the last tick.
- **[CTL-T6]** A bridge applies `velocity` until the next decision or until `ttl_s` runs out. After that it MUST command zero velocity.
- **[CTL-T7]** Control decisions SHOULD go to their own decision stream or log.
- **[CTL-T8]** **(New in RC3.)** `radius`, if present, MUST be a number ≥ 0, and the decision MUST then carry `level`, a number in (0, 1). `level` without `radius` is allowed; it MUST then also be a number in (0, 1) *(RC4, G-12)*. *(Resolution of Q-8: the three SDKs already refuse `radius` without `level`.)*
- **[CTL-T9]** **(New in RC3.)** `reasons` is an open list: each item MUST be a string. A trust layer SHOULD use the registered codes (registry 12.3) and SHOULD give a custom code a namespace (`acme.too_close`). A consumer MUST accept any string. It MUST NOT read an unknown code as `ok`. A bridge acts on `action` and `velocity` only, never on a reason code. *(Resolution of Q-3. It writes down the SDK behaviour: the validators accept any string.)*

#### 7.4.6 Control safety rules
- **[CTL-S1]** An ABSTAIN MUST have zero `velocity` and `gain = 0`. A COMMIT MUST have a non-zero velocity.
- **[CTL-S2]** A trust layer MUST NOT move when it knows the input carries no signal: low `signal_quality`; stale input; an absent axis; output inside the no-signal reference ball (`‖raw − v_ns‖ ≤ radius`). The decision is then a HOLD with the reason code. A COMMIT MUST NOT carry `no_signal`, `no_signal_reference`, `stale_input`, `disengaged`, `not_engaged` or `absent`. An evaluation MUST report motion on zero-input and shuffled controls.
- **[CTL-S3]** `‖velocity‖ ≤ v_max` on every decision. The change per tick SHOULD be bounded. A bound MUST NOT delay a stop.
- **[CTL-S4]** Motion needs an engage, unless the deployment documents another enable channel. `enabled = false` is a latched stop. `ttl_s` is a few update periods (reference: 3). A layer SHOULD emit a HOLD (`stale_input`) when the decoder stops.
- **[CTL-S5]** After a `stop`, a COMMIT needs a higher `engagement`. After an engage, the authority SHOULD ramp from 0 to 1 (reference: linear over 1 s).
- **[CTL-S6]** With `uncertainty = std`, a layer SHOULD calibrate the radius by split conformal prediction on labelled ticks of the same user and session (reference gain: conformal shrinkage). At full authority, `‖velocity‖ ≤ ‖raw‖`. Without `std`, a layer MUST NOT move faster than a configured `unscored_gain × raw` (reference default 0). The `level` is a deployment choice.
- **[CTL-S7]** A trust layer MUST NOT COMMIT an intent while the control is not engaged.
- *Informative (how a log check sees CTL-S7).* A decision log has no `control_enable` events. The `fep-0005` check takes the state from the last control decision of the session before the intent COMMIT. The control is not engaged after a `stop` (latched until a decision with a higher `engagement`), after a decision with `engagement` 0, and after a decision with the reason `not_engaged` or `disengaged`. Before the first control decision of a session, the check has no state and does not check CTL-S7. Vectors: E17, E20 (reject), E02, E21 (accept).
- **[CTL-S8]** Every control decision SHOULD carry `config_id`, `input` (`kind`, `tick`, SHA-256), `raw`, `reasons` and `latency_s`. A log MAY be thinned for storage only if it keeps every state change and every decision with a non-`ok` reason.
- *Informative.* CTL-S2 … S5 and S7 only remove motion or actions. A coverage-based speed bound still holds with them. On MC_RTT (P12-03) the declared level 0.9 gave no motion (radius 88.6 mm/s > mean decoded speed 45.8 mm/s). This is why the control profile stays Development.

---

## 8. Transport bindings

### 8.1 Files
#### 8.1.1 JSON Lines (proposed Stable)
UTF-8, one JSON object per line ([JSON Lines](https://jsonlines.org/)). Line 1 is the header (HDR-1). Each next line is one event. An optional last line is `end`. Rules GEN-2 … GEN-8 apply.

```json
{"type": "header", "spec_version": "1.0", "vocab": ["<blank>", "a", "b", " "], "vocab_type": "char", "blank_id": 0, "source": "my-decoder", "frame_period": 0.04, "latency": 0.2, "clock_domain": "trial", "meta": {"device.modality": "emg", "decoder.causal": true, "data.derived": true}}
{"type": "frame", "t": 0.00, "log_probs": [-0.0834, -2.9957, -3.9120, -4.6052]}
{"type": "frame", "t": 0.04, "log_probs": [-0.2231, -1.8971, -2.9957, null]}
{"type": "signal_quality", "t": 0.04, "value": 0.92, "unit": "index"}
{"type": "hypothesis", "id": "h1", "is_final": true, "score_semantics": "none", "nbest": [{"text": "ab", "score": -1.2, "char_confidences": [0.91, 0.40]}]}
{"type": "segment_end", "t": 0.08}
{"type": "end"}
```

A decision log (no header):
```json
{"type": "trust_decision", "spec_version": "1.0", "session": "u1", "seq": 0, "utterance": 0, "is_final": false, "action": "OFFER", "p_top1": 0.71, "score_semantics": "calibrated_prob", "shown": ["ab"]}
{"type": "trust_decision", "spec_version": "1.0", "session": "u1", "seq": 1, "utterance": 0, "is_final": true, "action": "COMMIT", "p_top1": 0.93, "score_semantics": "calibrated_prob", "shown": ["ab"], "config_id": "tcfg-0123456789abcdef"}
```

#### 8.1.2 NPZ (proposed Stable, read only for new data)
A NumPy `.npz` archive of the frame core only. **[FIL-1]** It MUST load with `allow_pickle=False`.

| NPZ key | dtype / shape | Holds | Required |
|---|---|---|---|
| `version` | unicode, () | `spec_version` | Yes |
| `log_probs` | `float32`, (T, V) | `log_probs` | Yes |
| `frame_times` | `float64`, (T,) | `frame_times` | Yes |
| `vocab` | unicode, (V,) | `vocab` | Yes |
| `vocab_type` | unicode, () | `vocab_type` | No; absent = `"char"` |
| `blank_id` | `int64`, () | `blank_id`; **−1 = null** | Yes |
| `source` | unicode, () | `source` | Yes |
| `meta_json` | unicode, () | `meta` as JSON text | Yes |
| `frame_period`, `latency` | `float64`, () | | No |

- **[FIL-2]** The required keys MUST be present. **[FIL-3]** A reader MUST read an absent `vocab_type` as `"char"`. **[FIL-4]** A reader MUST ignore unknown keys.
- **[FIL-5]** A writer SHOULD use the dtypes of the table. A reader MUST accept any real numeric dtype for the numeric keys. *(Resolution A7.)*
- **[FIL-6]** NPZ holds the frame core only. Events other than frames have no NPZ form in 1.0. New tools SHOULD write JSON Lines; NPZ stays for existing files. *(Resolution of v0.1 question 10; roadmap decision "NPZ read only".)*

### 8.2 LSL binding `nts-lsl/0.1` (proposed Stable)
From FEP-0002. An NTS stream maps to up to three LSL streams.

| NTS part | LSL stream | Type | Channels | Format | Rate |
|---|---|---|---|---|---|
| Frames | frames | `NTS` | V | `float32` or `double64` | 1 / `frame_period`, or 0 |
| Other events | events | `Markers` | 1 | `string` | 0 |
| `trust_decision` | decisions | `Markers` | 1 | `string` | 0 |

A hypothesis-only producer has no frames stream; its events stream is primary. An **NTS-native** stream has `desc/fidetype/nts_header`; a **foreign** stream has not.

#### 8.2.1 Names and ids
- **[LSL-N1]** The frames stream name SHOULD be `<producer>.nts`; the events stream name SHOULD be that name + `.events`; the decisions stream SHOULD be `fidetype.decisions`. A producer SHOULD set a stable `source_id`. The frames desc SHOULD name `events_source_id` and the events desc `frames_source_id`.

#### 8.2.2 Frames stream
- **[LSL-F1]** An NTS-native frames stream MUST use `float32` or `double64`. A consumer MUST refuse other formats.
- **[LSL-F2]** `channel_count` MUST equal V. A consumer MUST refuse a mismatch.
- **[LSL-F3]** If the desc has channel labels, label i MUST be vocab token i (unit `log_prob`, type `nts.log_prob`). A consumer MUST refuse another order. It compares trimmed labels; an empty label matches any token.
- **[LSL-F4]** A consumer MUST accept a `float32` stream (rounding keeps FRM-3). A producer SHOULD use `double64` when the receiver must reproduce a file replay exactly; it MAY use `float32`.
- **[LSL-F5]** One sample is one frame. A consumer MUST refuse a frame with NaN or `+inf`.
- **[LSL-F6]** `nominal_srate` MUST be 1 / `frame_period` (relative tolerance 1e-6) when the header has `frame_period`, and 0 when the rate is irregular. A consumer MUST refuse an NTS-native stream whose rate (> 0) differs.
- *Informative.* A consumer MAY read a foreign stream of class scores (vocab from labels or settings; `values` from settings) and then writes `adapter.name`, `adapter.version` and `data.derived` into `meta`.
- **[LSL-F7]** On the frames route with `blank_id = null`, the consumer MUST NOT reject the stream for this reason (HDR-13).

#### 8.2.3 `desc/fidetype` keys
| Key | Streams | Required | Value |
|---|---|---|---|
| `nts_header` | frames, events | Yes (NTS-native) | The header as one JSON object; `type` MAY be absent |
| `values` | frames | No | `log_probs` (default), `probs`, `logits` |
| `binding` | all | SHOULD | `nts-lsl/0.1` |
| `role` | all | SHOULD | `nts_frames`, `nts_events`, `trust_decisions` (informative: `signal`, `signal_markers`) |
| `events_source_id` / `frames_source_id` | frames / events | SHOULD | partner `source_id` |
| `event_clock` | events | SHOULD | `lsl` or `source`; absent = `source` |
| `event_type`, `spec`, `config_id`, `profiles` | decisions | 8.2.6 | |

- **[LSL-D1]** `nts_header` MUST be a JSON object; a consumer MUST refuse a stream whose `nts_header` is not.
- **[LSL-D2]** The header follows HDR-1 … HDR-13. A consumer MUST refuse an unsupported `spec_version` (HDR-2).
- **[LSL-D3]** A consumer MUST refuse an unknown `values` kind. An NTS-native producer SHOULD use `log_probs`.
- **[LSL-D4]** A consumer MUST ignore desc keys it does not know.

#### 8.2.4 Events stream
- **[LSL-E1]** The events stream MUST have type `Markers`, 1 channel, format `string`, irregular rate. A consumer MUST refuse a numeric format.
- **[LSL-E2]** One sample is one NTS event as UTF-8 JSON (GEN-2).
- **[LSL-E3]** A consumer MAY map plain strings by explicit settings (a boundary string → `segment_end`; others → final 1-best hypotheses). Otherwise it MUST ignore plain strings and count them.
- **[LSL-E4]** A sample that starts with `{` but is not a JSON object with a string `type` is malformed. A consumer MUST ignore it, count it and go on.
- **[LSL-E5]** A `header` on the events stream starts a new NTS stream; the consumer sets `clock_domain = lsl`. JSON `frame` events MAY come on the events stream.
- *Intent and control events* are marker JSON on the events stream. `intent_declaration` and `control_declaration` travel inside `nts_header`. No binding change.

#### 8.2.5 Timestamps and clock
- **[LSL-C1]** The LSL timestamp of a sample is the time of its event in the sender clock. A producer MUST stamp each sample when the event time is known.
- **[LSL-C2]** The consumer gives NTS events with `clock_domain = "lsl"`. The `t` of a frame is the corrected timestamp. For a JSON frame on the events stream it keeps the producer's value in `t_source`.
- **[LSL-C3]** Receiver mode (default): t = timestamp + time_correction, one offset for all streams of one sender host, refreshed (reference 5 s). Sender mode: raw timestamps. The mode and offset go into the provenance. **A consumer MUST NOT write the host name into any output.**
- **[LSL-C4]** A frame timestamp at or before the previous one is moved to just after it (1 µs) if it is at most a tolerance behind (reference 5 ms), else dropped; both are counted. A consumer MAY instead refuse the stream.
- **[LSL-C5]** `event_clock = lsl`: in receiver mode the consumer MUST add the same `time_correction` to the time fields inside marker JSON. `source` (or absent): the consumer MUST leave them unchanged. A consumer MUST refuse another value. A producer SHOULD use `lsl`. The consumer adds `lsl_t` to every marker event.
- **[LSL-C6]** Two inlets are merged by time with a merge window (reference 50 ms); a late marker is released out of order and counted. *(Amendment 5: with LSL-C7 heartbeats and LSL-C8 the merge releases items at once; the window then only limits the wait for a producer that sends no heartbeat.)*
- **[LSL-C7]** **(Amendment 5.)** **Heartbeat.** An events-stream sample whose string is empty after white space is removed is a heartbeat. A consumer MUST NOT give it as an NTS event and MUST NOT count it as an ignored plain string (LSL-E3); it MAY count it (reference: `heartbeats`). Its timestamp moves the inlet's merge position like any other sample. A producer MUST push the samples of its events stream with timestamps that do not decrease. A producer with a frames stream and an events stream SHOULD push a heartbeat after each frame, with the timestamp of that frame. *Why:* without it the idle events stream holds every frame for the merge window (P3-10: 60.4 ms p95 added latency at 50 ms; with heartbeats 1.07 ms).
- **[LSL-C8]** **(Amendment 5.)** **Equal times.** When a frames-stream item and an events-stream item have the same (corrected) time, the merge MUST give the frames-stream item first. Items of one stream keep their order. A producer MAY stamp a marker (for example `segment_end`) with the timestamp of the frame before it (SEG-4 allows `t` equal to the last frame time); the merge then releases the marker as soon as that frame has arrived. The rule needs the one clock offset per sender host of LSL-C3: two separate offset estimates differ by microseconds and can turn equal times into a wrong order. A capture that removes the host name stores the same offset on both inlets.

#### 8.2.6 Gaps, loss and the decisions stream
- **[LSL-G1]** A frame step larger than 2.5 (reference) nominal periods is a gap. Modes: `mark` (default: extension event `gap`), `segment` (`segment_end` with `reason = "gap"`), `abort` (drop the open utterance; the reference consumer emits the extension event `lsl_status` with `status = "gap_abort"`).
- **[LSL-G3]** **(New in RC3.)** A gap record carries these fields: on the `gap` event, on a `segment_end` with `reason = "gap"`, and on an `lsl_status` event with `status = "gap_abort"`. They are an exception to EXT-3 (written down from the 1.0 reference; a later binding version MAY prefix them). A consumer that does not know them ignores them (GEN-4). *(Resolution of Q-2.)*

| Field | Type | Meaning |
|---|---|---|
| `t_start` | number | Time of the last frame before the gap, seconds |
| `t_end` | number | Time of the first frame after the gap, seconds |
| `missing_frames` | integer ≥ 0, or null | Missing frames; null if the stream has no nominal rate |
| `stream` | string | Name of the LSL stream (never a host name, LSL-C3) |
- **[LSL-G2]** When a stream is lost inside an utterance, the consumer MUST NOT emit a final decision on that utterance. It MAY re-resolve the stream by `source_id` (reference 30 s). After a reconnect it MUST emit the header again.
- **[LSL-X1]** The decisions stream MUST have type `Markers`, 1 channel, `string`, irregular rate, and desc keys `role = trust_decisions` and `event_type = trust_decision`. It SHOULD have `spec = FEP-0001`, `binding`, `config_id` and (with several profiles) `profiles`.
- **[LSL-X2]** One sample is one `trust_decision` as JSON. It MUST meet section 6. The sample timestamp is the emission time.
- **[LSL-X3]** A subscriber MUST NOT act on `is_final = false` (TD-1).

#### 8.2.7 Binding version
- **[LSL-V1]** A producer SHOULD write `binding = nts-lsl/0.1`. A consumer MUST read a missing `binding` as `nts-lsl/0.1`. A consumer MUST refuse an unknown binding version. The binding version is separate from `spec_version`.

Extension keys: `lsl` (header and decision records; never the host name), `lsl_t`, `t_source`, `lsl_clamped`, `lsl_dropped_before`, the gap fields of LSL-G3, event types `gap` and `lsl_status`. A consumer that does not know them ignores them (GEN-4).

### 8.3 WebSocket binding `nts-ws/0.1` (proposed Stable)
From FEP-0004, [RFC 6455](https://www.rfc-editor.org/rfc/rfc6455).

| Path | Direction | Content |
|---|---|---|
| `/nts` | producer → server | NTS events of one stream per connection |
| `/nts` | server → producer | `ws_welcome`, `ws_ack`, `ws_error` |
| `/decisions` | server → subscriber | `trust_decision` with `ws_seq`; resumable |
| `/events` | server → subscriber | released NTS events with `stream_id`; not resumable |

#### 8.3.1 Paths and handshake
- **[WS-H1]** A server MAY use other path names and MUST document them. It MUST refuse an unknown path (HTTP 404).
- **[WS-H2]** A client MUST offer the subprotocol `nts-ws.0.1`. A server MUST select it and MUST refuse a client that does not offer it (HTTP 400).
- **[WS-H3]** A server that serves browsers SHOULD check `Origin` against a list.

#### 8.3.2 Framing
- **[WS-F1]** Every message MUST be a text message. A server MUST refuse a binary message (close 1003).
- **[WS-F2]** A message MUST be one JSON object with a string `type` (GEN-2). A receiver MUST refuse anything else (close 1007).
- **[WS-F3]** A message SHOULD be at most 1 MiB. A server MAY refuse a larger one (close 1009).
- **[WS-F4]** A receiver MUST ignore unknown keys. `ws`, `ws_seq`, `ws_t_sent`, `ws_t_recv` are binding keys.

#### 8.3.3 Control messages
| Type | From | Fields |
|---|---|---|
| `ws_welcome` | server | `binding`, `role`, `seq`; ingest: `stream_id`, `resumed`, `ack_every`, `window`; decisions: `spec`, `config_id`, `first_available`, `replayed`, `missed` |
| `ws_ack` | server | `stream_id`, `seq` |
| `ws_error` | server | `code`, `detail` |
| `ws_batch` | producer | `events` |
| `ws_auth` | client | `token` |
| `ws_subscribe` | subscriber | `binding`, `from_seq`, `types`, `stream_id` (optional) |

- **[WS-M1]** NTS event types never start with `ws_`. A producer MUST NOT send an unlisted `ws_` type. **[WS-M2]** A server MUST NOT forward `ws_auth` or a token. **[WS-M3]** A receiver MUST ignore (and count) an unknown `ws_` message.

#### 8.3.4 Input stream, sequence numbers and gaps
- **[WS-S1]** The first message on `/nts` (after an optional `ws_auth`) MUST be the header. A server MUST refuse another first message, an unsupported `spec_version`, and a header that breaks HDR-8 (`meta` not a JSON object) (close 1007).
- **[WS-S2]** The header MAY carry `ws`: `binding`, `stream_id` (1–128 characters), `resume`. A producer SHOULD set a stable `stream_id`. One connection carries one stream; the `session` of each decision is the stream id. The server answers with `ws_welcome`.
- **[WS-Q1]** Every event after the header MUST have `ws_seq`: integer ≥ 1, 1 first, +1 each. A server MUST refuse a missing or non-integer `ws_seq` (close 1007).
- **[WS-Q2]** A duplicate `ws_seq` MUST be dropped and counted.
- **[WS-Q3]** Events are released in `ws_seq` order. A held event waits up to `reorder_window` (16) events or `reorder_timeout_s` (0.25 s); then the missing numbers are a gap.
- **[WS-Q4]** A `ws_batch` carries 1 to `max_batch` (1024) events with consecutive `ws_seq` and no control messages (else close 1007 / 1009).
- **[WS-Q5]** At a gap the consumer MUST drop the open utterance without a decision, and MUST drop the `frame` events after the gap up to the next `segment_end`, `end` or `header`.

#### 8.3.5 Acks and back-pressure
- **[WS-A1]** The server sends `ws_ack` after every `ack_every` (64) released events, after `end`, and after `ack_interval_s` (0.1 s).
- **[WS-A2]** A producer MUST NOT have more than `window` (4096) unacknowledged events.
- **[WS-A3]** When the trust layer is behind, the server SHOULD stop reading. It MUST NOT drop events to keep up.

#### 8.3.6 Decisions channel
- **[WS-D1]** A subscriber sends `ws_subscribe` first; the server answers `ws_welcome`. Each decision then has `ws_seq` 1, 2, 3, … over the channel, with no gap. The FEP-0001 `seq` field is a different field.
- **[WS-D2]** With `from_seq`, the server replays the decisions it still holds (reference: last 4096); `missed` counts the lost ones.
- **[WS-D3]** A subscriber MUST check that `ws_seq` increases by 1. On a gap it MUST NOT skip silently: it resubscribes with `from_seq`. It drops duplicates. It MUST follow section 6.
- **[WS-D4]** A slow subscriber MUST NOT slow the trust layer: bounded queue (1024), then `ws_error` `slow_consumer` and close 1013.
- `/events` uses `ws_subscribe` (optional `types`), with no replay.

#### 8.3.7 Resume, close codes, auth and TLS
- **[WS-R1]** When the connection of an unfinished stream ends, the server keeps the stream state for `resume_timeout_s` (10 s); the open utterance waits. A resume header (`ws.resume = true`, same `stream_id`) MUST equal the first header except `ws`; else close 1007. The server answers `resumed = true` with the last released `ws_seq`.
- **[WS-R2]** Without a resume in time, the stream is lost: the server drops the open utterance without a decision. An unknown stream id starts a new stream; the producer MUST then treat the old stream as ended. A new resume while the old connection looks open takes over (old: `ws_error` `taken_over`, close 4001). A new non-resume header for an unfinished stream id replaces it and drops its open utterance.

| Close | `ws_error` | When |
|---|---|---|
| HTTP 400 | — | No subprotocol |
| HTTP 404 | — | Unknown path |
| 1003 | `binary` | Binary message |
| 1007 | `bad_message`, `bad_header`, `bad_seq`, `bad_batch`, `bad_subscribe` | Bad message |
| 1008 | `auth` | Missing or wrong token |
| 1009 | `too_big` | Message or batch above the limit |
| 1013 | `slow_consumer` | Subscriber queue full (resubscribe) |
| 4000 | `binding` | Unknown binding version |
| 4001 | `taken_over` | A newer connection resumed the stream |

- **[WS-T1]** A server MAY require a token. A client SHOULD send it as `Authorization: Bearer <token>`; a browser sends `ws_auth` as its first message. A server MUST accept a token from either place.
- **[WS-T2]** A missing or wrong token MUST close the connection with 1008 before the server accepts any event.
- **[WS-T3]** A token MUST NOT appear in a log line, a header, an event, a decision or a `ws_error` detail. It SHOULD NOT go in the URL query.
- **[WS-T4]** Off `localhost`, a client and a server MUST use `wss://` (TLS 1.2 or later).

#### 8.3.8 Clock and binding version
- **[WS-K1]** WebSocket does not change any NTS time field or `clock_domain`. The event clock is always the source clock.
- **[WS-K2]** Frame times MUST increase strictly; the binding does not clamp or reorder times.
- **[WS-K3]** `ws_t_sent` / `ws_t_recv` are transport stamps (TIM-5). Across hosts, a consumer SHOULD NOT use their difference.
- **[WS-K4]** A server MAY add a `ws` record to each decision (`stream_id`, `binding`, `trigger_seq`, `server_latency_s`, `e2e_latency_s`).
- **[WS-V1]** The binding version is `nts-ws/0.1` (token `nts-ws.0.1`). A missing binding means `nts-ws/0.1`. A receiver MUST refuse an unknown binding version (server: close 4000). Control events over WebSocket: a gap is a no-signal condition; the control layer SHOULD HOLD until the next tick after the gap.

### 8.4 Bindings not in 1.0
In-process API, gRPC, Arrow/Parquet, shared memory and BLE are not defined in this RC. See Appendix A (v0.1 question 1) and section 11.6.

---

## 9. Conformance

### 9.1 Conformance classes
| Class | Must meet |
|---|---|
| **Producer** | HDR, MET, FRM, SEG, SQ, DEC, HYP, EVD, DCL (producer parts), TIM, GEN, FIL (for files), the profile rules for the events it writes, and section 10 |
| **Consumer** | Accept exactly the streams that the producer rules allow; GEN-3, GEN-4, GEN-6, GEN-7; HDR-13; HYP-2; DEC-1; SQ-2; TD-1 |
| **Trust layer** | Consumer rules plus section 6 and the safety rules of each profile it implements |
| **Bridge** | TD-1, TD-3, TD-9 (bridge part), INT-T5, CTL-T6 |
| **Binding implementation** | The rules of 8.2 or 8.3 for its role |

### 9.2 Levels (producer streams)
The levels are cumulative and come from the conformance suite. They are **stream levels**: they judge one stream. The implementation levels of 9.6 (NTS Core, NTS Full, NTS Trust-ready) judge a program and use these stream levels.

| Level | Content |
|---|---|
| **core** | Every MUST rule that a validator can check on the stream |
| **trust-ready** | core + the SHOULD rules that a trust layer needs: `source`, `device.modality`, `decoder.causal`, `data.derived`, calibration consistency, `language` for text vocabularies |
| **provenance** | trust-ready + `stream.id`, `decoder.name`/`version`, `decoder.weights_sha256`, adapter pair, `decoder.calibration_id`, pseudonymous ids |

- **[CNF-3]** **(Amendment 3.)** A stream reaches level **trust-ready** when it reaches core and every trust-ready check passes: `TR-SOURCE`, `TR-MODALITY`, `TR-CAUSAL`, `TR-OFFLINE-LATENCY`, `TR-DERIVED`, `TR-CALIB`, `TR-LANGUAGE`, `NTS-VT-CHAR`.
- **[CNF-4]** **(Amendment 3.)** A stream reaches level **provenance** when it reaches trust-ready and every provenance check passes: `PV-STREAM-ID`, `PV-DECODER`, `PV-WEIGHTS`, `PV-ADAPTER`, `PV-CALIB-ID`, `PV-PSEUDONYM`.
- An advisory check (for example `NTS-NAMESPACE`, `NTS-MODALITY-MATCH`) never blocks a level. `nts-conform check` prints the stream level of each file.

### 9.3 Profiles of the suite
| Suite profile | Covers | Vectors | Python | TypeScript | Rust |
|---|---|---|---|---|---|
| `v0.1` | Sections 3, 4.1–4.6, 4.8, 5, 8.1 (incl. 1.x header versions V53–V61, HDR-12 V62–V65, unknown enumeration values V66–V68; RC4: optional field types V69–V82; amendments: modality keys V83–V87, dense and sparse keys V88–V92, MET-11 warning V93–V96; amendment 4: TD-4 V97) | 97 | yes | yes | yes |
| `fep-0001` | 4.3, 4.7, 6 (incl. TD-9 for 1.x, TD-F2 types, TD-F3, TD-12 advisory; RC3: VER-8 F57–F59, GEN-10 F60–F61, `declaration` F62; RC4: F63–F66) | 66 | yes | yes | yes |
| `fep-0002` | 8.2 (amendment 5: LSL-C7 L36, LSL-C8 L37) | 37 | yes | yes (structural) | yes (structural) |
| streaming cases (`conformance/streaming/`) | TD-14 (amendment 5): outcome per event of an event-by-event validator | 6 | yes | yes | yes |
| `fep-0003` | 7.1, 7.3 (RC3: VER-8 I24, D22, D23; RC4: I25, D24–D26) | 51 | yes | yes | yes |
| `fep-0004` | 8.3 (incl. W38: header `meta` must be an object; RC3: GEN-10 W44) | 44 | yes | yes | yes |
| `fep-0005` | 7.4 (RC3: VER-8 C24, E22–E24; RC4: C25, E25–E27; amendment 1: C26) | 53 | yes | yes | yes |
| kit (`conformance/kit/`) | Every wire form (8.1–8.3), one or more realistic files each; verdict, rule ids and `stream_level` per file (P7-01; kit 0.2.0 by amendment 3) | 36 | yes | yes | yes |

```
fidetype conformance --profile fep-0001                    # reference consumer over the vectors
fidetype conformance check --level provenance my.jsonl     # producer check
fidetype conformance consumer --cmd "my-reader {path}"     # your consumer over the vectors
node sdk/typescript/bin/fidetype-ts.mjs conformance        # TypeScript SDK
fidetype-rs conformance                                    # Rust SDK
```

### 9.4 Conformance claims
A claim names the class, the level, the profiles and the bindings, and the RC: for example "Producer, NTS 1.0 RC4 (draft), level provenance, profiles text + intent, binding nts-lsl/0.1". **[CNF-1]** A claim MUST NOT omit "RC4 (draft)" (or the RC that it names) while this document is a draft.

*Amendment 3.* A claim of an implementation level (9.6) names that level and the kit version, for example "Consumer, NTS 1.0 RC4 (draft), NTS Trust-ready, profiles text + intent + control, bindings nts-lsl/0.1 + nts-ws/0.1, kit 0.2.0". The stream level of 9.2 ("level provenance") stays the claim about one stream.

### 9.5 Parity of the reference SDKs
The three SDKs give the same verdict as the Python reference on every vector of `v0.1` … `fep-0005` (97 + 66 + 37 + 51 + 44 + 53 = 348 since amendment 5 of 2026-11-17; amendment 4: 346; amendment 3: 345; amendment 2: 341; amendment 1: 336; RC4: 330), the same advisory warnings and stream level where a vector or kit entry pins them (`expected.warnings`, `expected.level`; amendment 3), and the same verdict on the 36 kit entries (`sdk/typescript/scripts/cross-check.mjs --rust`) and on the fuzz mutants of those vectors (`fuzz-parity.mjs`; amendment 3 run: seeds 1–3, `--n 30`, 27,767 mutants, 0 differences; amendment 2 run: 27,497 mutants; RC4 run: 26,687 mutants; RC3 run: 24,347 mutants). Gap G-1 (control profile in Python only) is closed.

### 9.6 Implementation levels: NTS Core, NTS Full, NTS Trust-ready (amendment 3)
The stream levels of 9.2 judge one stream. The implementation levels judge a program: a producer (it writes streams or decision logs) or a consumer (a reader, a validator or a trust layer). The test material is the conformance kit ([`conformance/kit/`](conformance/kit/)) and the tool `nts-conform`. A generated, informative copy of this section is [`conformance/levels.json`](conformance/levels.json) (`nts-conform levels`).

- **[CNF-2]** The implementation levels are **cumulative**: NTS Trust-ready includes NTS Full, and NTS Full includes NTS Core. A claim names the highest level that the implementation meets, the output profiles and bindings that it covers, and the kit version. An advisory check never blocks a level.
- **[CNF-5]** **Producer.** A producer meets a level when its evidence (files that it wrote, checked with `nts-conform check`) gives the result of the table below. The evidence MUST be the producer's real output (or output of the same code on synthetic input), not files written by hand.
- **[CNF-6]** **Consumer.** A consumer meets a level when it gives the expected verdict on every kit entry of the level (`nts-conform kit`). At NTS Trust-ready it also reports the `stream_level` of every input-stream entry in scope: it accepts the file at each stream level up to that one and refuses it at the next one.
- **[CNF-7]** **Bindings.** A claim adds a binding only when the implementation also gives the expected verdict on the kit entries of that binding: `nts-lsl/0.1` = suite profile `fep-0002` (K26–K28), `nts-ws/0.1` = `fep-0004` (K29–K31). The rules LSL-* or WS-* then apply.

| Level | Rule ids (Appendix C.1) | Kit entries | Producer evidence | Consumer |
|---|---|---|---|---|
| **NTS Core** | GEN, HDR, MET, FRM, SEG, SQ, DEC, PTR, TIM, VER, FIL, EXT, SEC, CNF (except CNF-3, CNF-4) | `v0.1`: K01–K14, K32–K36 | Every file passes `nts-conform check --level core`. At least one input stream (JSON Lines or NPZ). | The expected verdict on every Core entry. |
| **NTS Full** | Core + for each named output profile: text HYP, EVD, DCL, TD, TD-F; intent PRF, INT-D, INT-E, INT-F, INT-T; control CTL, CTL-D, CTL-E, CTL-T. No profile named = all three. | Core + text `fep-0001` K15–K18, intent `fep-0003` K19–K22, control `fep-0005` K23–K25, for each named profile | Core, and for each named profile at least one file that uses its events: text = a stream with `hypothesis` or `segment_end`, or a text decision log; intent = a stream with `intent_declaration` (or `intent` events), or an intent decision log; control = a stream with `control_declaration` (or `control` events), or a control decision log. | Core + the expected verdict on every entry of each named profile. |
| **NTS Trust-ready** | Full + INT-S, CTL-S, PRV, CNF-3, CNF-4. The SHOULD rules behind them (MET-5, MET-6, DEC-5, SEC-2, SEC-4) are required. | The Full entries and their `stream_level` | Full, and every input stream reaches stream level **provenance** (`nts-conform check --level provenance`); every decision log passes, safety rules included. | Full + the expected `stream_level` (core, trust-ready, provenance) of every input-stream entry in scope (`{level}` in `nts-conform kit --cmd`). |

*Informative.* NTS Trust-ready is what a trust layer needs from its input: score semantics (calibration consistency, MET-6, DEC-5), provenance (stream id, decoder, weights hash, adapter, pseudonymous ids) and timing (`decoder.causal`, no `latency` on an offline decoder, MET-5). A producer that writes only frames meets NTS Core; the stream level of its files (9.2) then tells a trust layer what it gets. NPZ is read only for new data (2.3), so an NPZ-only producer stops at NTS Core. `nts-conform check` prints the producer level of all its files together, `nts-conform kit` the consumer level; `--claim text|intent|control` names the profiles, `--binding` a binding, `--require-level` sets the exit code.

### 9.7 Self-certification (amendment 3)
- **[CNF-8]** A **self-certification** claim of a level is a pull request that adds one entry to [`conformance/certified.json`](conformance/certified.json) (schema `fidetype.conformance.certified/1`) and its evidence: the JSON report of `nts-conform kit` (consumer, schema `fidetype.nts-conform.kit-report/1`) or `nts-conform check` (producer, `fidetype.nts-conform.report/1`) over the full kit of the version that the entry names. The report MUST reach the claimed level. `nts-conform certified --check` (CI) compares every entry with its evidence.

*Informative.* The list holds the name, language, class, level, profiles, bindings, spec RC, kit version, implementation version, evidence path, the command that made the evidence, maintainer, repository, licence and date. It is self-certification: the project checks the evidence file, not the implementation. The first entries are the reference implementations of this repository (the Python, TypeScript and Rust SDKs and the producer adapters). A listing is not a licence to use a trademark (roadmap P7-03). The process: `docs/conformance.md`, section "Self-certification".

---

## 10. Security and privacy

### 10.1 Neural data is sensitive
Decoded output can reveal what a person wanted to write or do, when they asked for help, and how they move. Some jurisdictions regulate neural data (for example Colorado HB24-1058, California SB 1223, Montana SB 163). Decoded output can be neural data under such laws. This spec is not legal advice; check the current text of each law. The fields `data.derived` and `consent.ref` help a producer document a stream. They do not make it compliant.

### 10.2 No raw signal in the stream
- **[SEC-1]** An NTS stream carries decoder output (distributions, labels, hypotheses, control values, quality indices). It MUST NOT carry raw neural samples. A raw signal travels on its own transport (for example an LSL signal stream, role `signal`) or in its own file (BIDS).
- **[SEC-2]** A stream SHOULD set `meta["data.derived"] = true`.
- No part of NTS requires the raw signal. A consumer, a trust layer and a bridge work on the stream alone.

### 10.3 Personal data
- **[SEC-3]** `meta` MUST NOT contain personal identifiers: names, e-mail addresses, dates of birth, medical record numbers, addresses, face or voice data.
- **[SEC-4]** `subject.id` and `session.id` MUST be pseudonymous. The mapping to real people MUST NOT be in the stream. A provenance record SHOULD pseudonymise them again (for example hash them) or omit them.
- **[SEC-5]** A producer SHOULD NOT put free text in `meta`. `intent_feedback`, `control_enable` and `reason` fields MUST NOT carry personal text.
- **[SEC-6]** `consent.ref` MUST be an opaque reference. It MUST NOT contain the consent text or personal data. `stream.id` MUST NOT contain personal data.
- **[SEC-7]** `shown` holds decoded text, which is personal data. Logs SHOULD omit it or store a keyed hash. A decisions outlet on a shared network SHOULD offer a mode without text (reference: `--no-text`). Intent and control logs are behavioural data; keep them under the same rules.

### 10.4 Leakage (evaluation honesty)
- **[SEC-8]** A stream MUST NOT contain the ground-truth text, the target labels, or any value derived from them, in any field or event, including `meta`. Ground truth MUST travel separately (for example a BIDS `events.tsv`). An index that lets an evaluator find the truth (for example a trial index) is allowed. *(Resolution A8.)*

### 10.5 Provenance and audit fields
| Purpose | Fields |
|---|---|
| Which stream | `meta["stream.id"]`, or a content hash (PRV-1) |
| Which device and adapter | `device.*`, `adapter.name`, `adapter.version` |
| Which model | `decoder.name`, `decoder.version`, `decoder.weights_sha256`, `lm.name` |
| Which calibration | `calibration.applied`, `decoder.calibration_id`, `decoder.calibration_method` |
| Which trust configuration | `trust_decision.config_id`; `decode_declaration.config_id` |
| Which input | `trust_decision.input` (frame range or input id, SHA-256) |
| Which rules | `trust_decision.spec_version` (11.2) |
| Transport | `lsl` and `ws` records (never a host name, a client address or a token) |

PRV-1 … PRV-3 (6.5), INT-S10 and CTL-S8 give the audit rules.

### 10.6 Transport security
- **[SEC-9]** WebSocket: WS-T1 … WS-T4 (auth hook, no token in output, `wss://` off localhost). `/events` exposes the full input stream; a server SHOULD require auth for it on any shared network.
- **[SEC-10]** LSL has no authentication or encryption. LSL-C3 forbids host names in output. A deployment SHOULD run LSL only on a trusted network segment and SHOULD omit `shown` on shared networks.
- *Informative.* A `decode_declaration` is a claim, not a proof (4.7.3). NTS 1.0 has no signature scheme for streams or decisions (deferred; Appendix A).

---

## 11. Versioning and extension rules

### 11.1 Semantic versioning
- The spec version follows [semver](https://semver.org/) with two parts in the stream: `MAJOR.MINOR`.
- A **minor** version adds optional fields, event kinds, profiles, registry entries or Development parts. It does not break a Stable part.
- A **major** version may break Stable parts. A Deprecated Stable part stays at least 12 months.
- The patch level (errata, clarifications) does not appear in streams.

### 11.2 `spec_version` in streams and decisions
- **[VER-1]** A 1.0 producer MUST write `spec_version` `"1.0"` in the header, and in every `trust_decision`.
- **[VER-2]** A `trust_decision` without `spec_version` follows the 0.1 rules. *Why:* decision logs have no header, and every log written before 1.0 lacks the field.
- **[VER-3]** A 1.x consumer MUST accept `"1.0"` and every `"1.<minor>"` (minor: `0` or digits without a leading zero). It reads a newer minor version with the 1.0 rules and ignores what it does not know (GEN-4). An unknown enumeration value of a newer minor version follows 11.2.1. *(Resolution A6.)*
- **[VER-4]** A 1.x consumer MUST accept `"0.1"` streams and decisions by the mapping of Appendix B, and apply the 0.1 rules to them (for example TD-9 as SHOULD NOT).
- **[VER-5]** A consumer MUST refuse another major version (for example `"2.0"`) and any other string (for example `"1.0.0"`, `"01.0"`).

#### 11.2.1 Unknown enumeration values (new in RC3; [FEP-0007](feps/0007-unknown-enum-values.md))
A minor version may add values to a registry of 12.2 or 12.3 (11.1). A 1.0 consumer does not know them. These rules say what it does with them.

- **[VER-6]** **Known values.** A value of an enumeration is *known* to a consumer if the registry of the version that the consumer implements lists it. A 1.0 consumer knows the values of 12.2 and 12.3.
- **[VER-7]** **Governing version.** The governing version of a `trust_decision` is its own `spec_version` (absent = `"0.1"`, VER-2). The governing version of the header and of every other event of a stream is the `spec_version` of the header. If the governing version is one that the consumer implements (`"0.1"`, or a 1.x minor version not above its own), an unknown value is an error. The rules that list values (HDR-5, HDR-11, SEG-5, SQ-1, DEC-1 … DEC-4, HYP-1, MET-1 `device.modality`, PTR-1, TD-F1, PRF-4, INT-D2, INT-E7, INT-F1, INT-T3, 7.3.5, CTL-D1, CTL-4, CTL-E1, CTL-T3) apply as before. A validator refuses the stream or log.
- **[VER-8]** **Newer minor version.** If the governing version is a newer minor version of the same major (VER-3), an unknown value is not an error. A consumer MUST accept it if it is a JSON string (another type is an error at every version). It MUST keep it as "unknown": it does not change it into a known value in its output or in forwarded data. It MUST apply the safe fallback of registry 12.3 to its own behaviour. A rule that compares the value with another value (for example "`state` fits `action`" in CTL-T3, "units fit quantity" in CTL-D1, "the confirm intent is irreversible" in INT-D4, the score rules of DEC-2 … DEC-4 and INT-E3, INT-E4) does not apply to an unknown value.
- **[VER-9]** **Bindings stay closed.** The enumerations of a binding (LSL `values`, `event_clock`, `role`; WebSocket subprotocol, close and error codes; binding version strings) follow the binding version, not `spec_version`. A consumer MUST refuse an unknown binding value (LSL-D3, LSL-C5, LSL-V1, WS-V1). A new binding value needs a new binding version (11.5).
- **[VER-10]** **Safety.** A safe fallback never adds an action. Because of an unknown value, a consumer MUST NOT commit, actuate an intent, move, confirm or select, and a consumer or bridge MUST NOT show a candidate. In particular:
  - a `trust_decision` with an unknown `action` or `profile` is a non-acting decision, as `ABSTAIN`: no commit, no actuation, zero velocity, no candidate shown. It still counts for `seq` (TD-5);
  - an intent COMMIT with an unknown `risk_class`, `role` or `confirmed_via` is not actuated; an intent declared with an unknown `risk` is treated as `irreversible`; an intent with an unknown `role` is never committed and never used as `confirm`, `cancel` or `undo` (as `null`);
  - a control COMMIT with an unknown `state` gives zero velocity, and the control counts as not engaged for CTL-S7 until a decision with a known state; a stream with an unknown `quantity`, `frame`, `units` or `uncertainty` gives no motion; a `control` event with an unknown `source` moves nothing; an engage (`enabled = true`) from an unknown `control_enable.source` is not an engage, but a stop (`enabled = false`) from it is a stop;
  - an `intent_feedback` with an unknown `outcome` never confirms, selects, undoes or labels; it drops an armed intent, as `cancelled` does;
  - a score with an unknown `score_semantics` is not a probability (DEC-1); INT-S2 then applies as for `none`;
  - a `signal_quality` value with an unknown `unit` is never evidence of good signal (a quality gate ignores it).

  A trust layer or a bridge that cannot apply a fallback MUST stop acting on the stream (it MAY close it). It MUST NOT guess a known value. *(Resolution of Q-7.)*
- *Informative (why version-gated).* A registry with policy Spec gets a new value only through a minor version. So a `"1.0"` stream with an unknown value has a producer error, and a `"1.1"` stream with one is valid data. The version gate keeps every RC2 reject vector a reject, and lets a 1.0 consumer read 1.1 data safely. Proto3 enums are open too: the binary form keeps an unknown number (proto README section 5). *Reference behaviour:* the conformance consumers and the SDK `DecisionTracker` (kind `unknown`, `forward = false`) implement VER-8 and VER-10. The reference trust layers refuse a header with an unknown `vocab_type` (`fidetype.trust.streaming`; the SDK stream readers `StreamValidator` share this header check), an unknown intent `risk` or `role` (`fidetype.trust.intent`) or an unknown control declaration value (`fidetype.trust.control`). VER-10 allows this: they stop instead of acting.

### 11.3 Compatibility promise
| Writer | Reader | Promise |
|---|---|---|
| 1.0 | 1.x (x ≥ 0) | Accepted. Stable parts keep their meaning. |
| 1.x (x > 0) | 1.0 | Accepted (VER-3). New optional parts are ignored. New enumeration values get the safe fallback (VER-8, VER-10). |
| 0.1 | 1.x | Accepted with the mapping of Appendix B. Rules that 1.0 made stricter apply only to 1.x data. |
| 1.x | 0.1 | Not promised. A 0.1 reader refuses `"1.0"` (v0.1 rule 5.1.4). |

### 11.4 Extension rules
- **[EXT-1]** New fields are optional. A field never changes its type or meaning within a major version. (A profile field has its type on decisions of its profile only: PRF-5.)
- **[EXT-2]** Custom `meta` keys use a namespace outside the registry (MET-3). Custom event types SHOULD use a namespaced type (for example `acme.calibration_event`). Custom `trust_decision` keys are allowed.
- **[EXT-3]** A binding adds keys only with a binding prefix (`lsl`, `lsl_*`, `ws`, `ws_*`), and event types only with that prefix or through registry 12.1. Exception in 1.0: the gap fields of LSL-G3.
- **[EXT-4]** A profile adds event kinds and conventions only (PRF-2).
- **[EXT-5]** A consumer MUST ignore unknown keys and unknown event types (GEN-4). It MUST NOT act on a `trust_decision` with an unknown `profile` value (PRF-4, VER-10).

### 11.5 Binding versions
- Binding versions are separate from `spec_version`: `nts-lsl/0.1`, `nts-ws/0.1`. This RC does not change either mapping, so their versions stay.
- Rules LSL-V1 and WS-V1 apply. While a binding major version is 0, every minor change can break readers. A binding goes to `/1.0` when 1.0 is final and its mapping is Stable.

### 11.6 Change process and FEP lifecycle
| State | Meaning |
|---|---|
| Draft | Proposed. Anything can change. |
| Under review | Open for comment, with a reference implementation and conformance vectors. |
| Accepted | The maintainers agreed; the change is planned for a release. |
| Implemented | In the reference implementation and the vectors (in all SDKs that claim the profile). |
| Final | Part of a released spec version. |
| Rejected / Withdrawn | Not adopted. The FEP stays as the record. |

- **[FEP-1]** Each FEP needs a reference implementation and conformance vectors before it is Implemented.
- A change to a Stable part needs an explicit vote (GOVERNANCE.md section 4).
- FEPs 0001–0005 are **Draft**. This RC proposes them for **Under review**. FEP-0007 (unknown enumeration values, RC3) and FEP-0008 (optional field types and the semantic-convention registry, RC4) are **Draft**, folded into this RC with a reference implementation and vectors in all three SDKs. The FEP index is [spec/README.md](README.md#proposals-feps).

### 11.7 SDK and spec compatibility matrix
SDK versions are separate from spec versions.

| SDK | Version | v0.1 streams | 1.x decision `spec_version` + TD-9 | 1.0 header `spec_version` | RC3 (VER-8, GEN-10, TD-F2 `declaration`) | RC4 (GEN-11 optional field types, MET-3 planned namespaces) | Profiles |
|---|---|---|---|---|---|---|---|
| Python `fidetype` | 0.0.1 | yes | yes (RC1) | yes (RC2; reads `"1.<minor>"`, writes `"0.1"` by default) | yes | yes | v0.1, fep-0001 … fep-0005 |
| TypeScript `@fidetype/sdk` | 0.1.0 | yes | yes (RC1) | yes (RC2; reads `"1.<minor>"`, writes `"0.1"` by default) | yes | yes | v0.1, fep-0001 … fep-0005 |
| Rust `fidetype` | 0.1.0 | yes | yes (RC1) | yes (RC2; reads `"1.<minor>"`, writes `"0.1"` by default) | yes | yes | v0.1, fep-0001 … fep-0005 |

---

## 12. Registries
NTS keeps IANA-style registries in this repository. Each registry has a name, a policy, and its entries. Until 1.0 is final, entries are Development.

| Policy | Meaning |
|---|---|
| **Spec** | Only a spec version (through a FEP) adds or changes an entry. |
| **FEP** | A FEP adds an entry; no spec version is needed. |
| **Expert review** | A maintainer reviews a pull request against the registry's rules. |
| **First come** | Any namespaced value; no review. |

### 12.1 Event types (policy: Spec)
| Value | Section | Profile |
|---|---|---|
| `header`, `frame`, `segment_end`, `end`, `signal_quality`, `decision` | 3, 4 | core |
| `hypothesis` | 4.7 | text |
| `pointer`, `control`, `control_enable` | 4.8, 7.4 | control |
| `intent`, `intent_feedback` | 7.3 | intent |
| `trust_decision` | 6 | all |
| `gap`, `lsl_status` | 8.2.6 (LSL-G1, LSL-G3) | LSL extension |
| `ws_welcome`, `ws_ack`, `ws_error`, `ws_batch`, `ws_auth`, `ws_subscribe` | 8.3.3 | WebSocket control messages (not NTS events) |
| Namespaced (`<org>.<name>`) | EXT-2 | First come |

### 12.2 Profile names (policy: FEP)
A new profile name is valid in a decision only from the minor version that registers it (VER-7). Safe fallback of an unknown name: the decision is never acted on (PRF-4, VER-10).

| Value | Section |
|---|---|
| `text` | 7.2 (default when `profile` is absent) |
| `intent` | 7.3 |
| `control` | 7.4 |

### 12.3 Enumerations (policy: Spec)
The last column is the **safe fallback** of an unknown value in data of a newer minor version (VER-8, VER-10). In data of a version that the consumer implements, an unknown value is an error (VER-7).

| Registry | Values | Safe fallback of an unknown value |
|---|---|---|
| `vocab_type` | `char`, `key`, `word`, `phoneme`, `command`, `other` | Read as `other`. A consumer MUST NOT turn the tokens into typed text unless it knows the vocabulary (for example by `vocab_id`). INT-D5 does not apply |
| `score_semantics` | `calibrated_prob`, `uncalibrated_prob`, `power`, `strength`, `none` | The score is not a probability (DEC-1); INT-S2 applies as for `none` |
| `clock_domain` | `lsl`, `unix`, `monotonic`, `trial`, `other` | Read as `other`: do not compare the times with times of another clock |
| `segment_end.unit` | `utterance`, `word`, `trial` | A boundary as any other (SEG-2) |
| `signal_quality.unit` | `index`, `snr_db`, `impedance_ohm`, `other` | Read as `other`: never evidence of good signal |
| `trust_decision.action` | `COMMIT`, `OFFER`, `ASK`, `ABSTAIN`, `OFFER_WORDS` | Non-acting, as `ABSTAIN` (no commit, no actuation, zero velocity, no candidate shown); counts for `seq` |
| `trust_decision.profile` (12.2) | `text`, `intent`, `control` | Never acted on (PRF-4) |
| Intent risk classes (`risk`, `risk_class`) | `safe`, `undoable`, `irreversible` | Declared `risk`: treated as `irreversible`. Decision `risk_class`: the COMMIT is not actuated |
| Intent roles (`role`) | `action`, `null`, `confirm`, `cancel`, `undo` | As `null` for acting: never committed, never a confirm, cancel or undo. A COMMIT that carries it is not actuated |
| Intent `confirmed_via` | `intent`, `feedback` | The COMMIT is not actuated |
| Intent feedback outcomes | `confirmed`, `cancelled`, `selected`, `undone`, `correct`, `wrong` | Never confirms, selects, undoes or labels; drops an armed intent as `cancelled` |
| Control `quantity` / `frame` / `uncertainty` | `velocity`, `position` / `screen`, `workspace` / `none`, `std` | No motion on the stream |
| Control units | `norm/s`, `px/s`, `mm/s`, `m/s`, `deg/s`; `norm`, `px`, `mm`, `m`, `deg` | No motion on the stream |
| Control `state` | `act`, `attenuate`, `hold`, `stop` | Zero velocity; not engaged for CTL-S7 until a known state |
| `control.source` | `decoder`, `human` | The event moves nothing |
| `control_enable.source` | `switch`, `caregiver`, `ui`, `voice`, `eye-tracker`, `watchdog`, `other` | `enabled = false` is a stop; `enabled = true` is not an engage |
| `pointer.mode` | `relative`, `absolute` | The event moves nothing |
| `device.modality` | `emg`, `eeg`, `meg`, `opm-meg`, `ecog`, `intracortical`, `fnirs`, `other` | Read as `other` |
| `declaration.status` (6.1.2) | `match`, `mismatch`, `absent` | Read as `mismatch` |
| Control reason codes (**open list**, CTL-T9) | `ok`, `shrunk`, `uncertain`, `no_signal`, `no_signal_reference`, `unscored`, `disengaged`, `not_engaged`, `stale_input`, `absent`, `handoff`, `clamp_speed`, `clamp_accel` | Any string is valid at every version; never read as `ok` |
| `segment_end.reason` (**open list**, SEG-6) | `gap` | Any string is valid; no effect on segments |
| LSL `values` / `role` / `event_clock` (binding) | `log_probs`, `probs`, `logits` / `nts_frames`, `nts_events`, `trust_decisions` (`signal`, `signal_markers` informative) / `lsl`, `source` | Closed (VER-9): refuse |

### 12.4 Vocabulary and intent ids (policy: Expert review; entries Development)
| Namespace | For | Example ids |
|---|---|---|
| `char.*` | Character sets | `char.b2q-28` (CTC blank, `a`–`z`, space) |
| `phoneme.*` | Phoneme sets | `phoneme.arpabet-39` |
| `hid.bci.switch.*` | Switch actions that mirror the Apple BCI HID usage page | `hid.bci.switch.primary` |
| `gesture.*` | Hand or wrist gestures | `gesture.pinch` |
| `mi.*` | Motor-imagery classes | `mi.left-hand`, `mi.rest` |
| `intent.*` | Intent ids and intent vocabularies | `intent.select`, `intent.call-caregiver`, `intent.home-v1` |

Rules: an entry has an id, a version, the token list in order, the blank (if any), and for intent vocabularies the risk class and role of each intent. A new version of an entry gets a new `vocab_version`; an old version is never changed. Entries will live in `spec/vocab/` (not published yet).

### 12.5 Semantic-convention namespaces (policy: Spec for the listed keys; First come outside)
Reserved namespaces: `device.*`, `decoder.*`, `adapter.*`, `stream.*`, `lm.*`, `user.*`, `session.*`, `subject.*`, `calibration.*`, `data.*`, `consent.*`, `emg.*`, `meg.*`, `implant.*`, `language`. Planned modality namespaces (roadmap P1-04, not defined yet): `eeg.*`, `fnirs.*`. Since RC4 the planned namespaces are reserved too (MET-3, SC-2). Their keys need a FEP with evidence from real producers (SC-9, A.8). The modality namespaces `emg`, `meg` and `implant` have keys since the RC4 amendment of 2026-11-16 ([FEP-0009](feps/0009-modality-semantic-conventions.md), MET-11). The normative list of keys, types and value lists is the registry [`semconv/`](semconv/registry.md) (MET-10).

### 12.6 Binding versions and subprotocol tokens (policy: Spec)
| Binding | Version string | Token |
|---|---|---|
| LSL | `nts-lsl/0.1` | — |
| WebSocket | `nts-ws/0.1` | `nts-ws.0.1` (`Sec-WebSocket-Protocol`) |

### 12.7 WebSocket close codes and error codes (policy: Spec)
The table of 8.3.7. Close codes 4000–4099 are reserved for this binding; 4000 `binding` and 4001 `taken_over` are assigned. `ws_error` codes: `binary`, `bad_message`, `bad_header`, `bad_seq`, `bad_batch`, `bad_subscribe`, `auth`, `too_big`, `slow_consumer`, `binding`, `taken_over`.

### 12.8 Configuration id prefixes (policy: First come, informative)
`tcfg-` (text trust configuration), `icfg-` (intent), `ccfg-` (control). A content id is the prefix plus a hash of the frozen configuration.

---

## Appendix A. Open questions: resolutions and deferrals
"Resolved" means this RC answers the question, with the evidence named. "Deferred to 1.1" means 1.0 does not answer it; the reason is given. No new feature comes from a resolution.

### A.1 Spec v0.1, section 10
| # | Question | Outcome | Rationale |
|---|---|---|---|
| 1 | Binary wire protocol; default transport | **Deferred to 1.1** (task P1-02 may bring it to a later RC) | The roadmap chose protobuf as the future source of truth, but no `.proto` exists yet. JSON Lines, LSL and WebSocket JSON are the 1.0 forms (8). No transport is "the default"; each binding is for its use (labs: LSL; browsers: WebSocket; files: JSON Lines). |
| 2 | Embeddings in frames | **Deferred to 1.1** | No producer or consumer in the repo needs them. |
| 3 | Lattices | **Deferred to 1.1** | No lattice producer exists; n-best covers all current decoders. |
| 4 | Frame revisions | **Resolved: no frame revisions** (FRM-6) | TIM-2 already forbids a frame at an earlier time. Causal decoders with lookahead (M4-01/02) emit frame t after the lookahead and declare it in `latency`; the streaming trust layer works on final frames (M4-08). Hypotheses keep `revision_of`. |
| 5 | Segment boundaries | **Resolved** by `segment_end` (4.3) | FEP-0001; vectors F01–F06; used by every streaming replay. |
| 6 | Multi-head output | **Partly resolved.** One frame vocabulary per stream; profiles let one stream carry text, intent and control events (PRF-1). Several frame heads in one stream: **deferred to 1.1** | Vectors I02 (char frames + intent events) and C02 (control + click intent). No decoder in the repo emits two frame heads. |
| 7 | Vocabulary registry | **Partly resolved:** registry, namespaces and policy (12.4). Entries and the mapping to Apple switch actions and W3C key codes: **deferred to 1.1** | The process can be fixed now; entries need outside producers. |
| 8 | Clock domains across devices | **Partly resolved:** LSL clock correction (8.2.5) and the WebSocket source-clock rule (8.3.8). Mapping between two domains across hosts: **deferred to 1.1** | LAN and Wi-Fi tests (M6-10) are not done. M6-13 measured a Windows clock step of −1,361 ms, so a mapping rule needs field data. |
| 9 | Machine-readable conventions | **Resolved in RC4** (MET-10; task P1-04, SC-7) | The YAML registry [`spec/semconv/`](semconv/registry.md) holds every key of 3.4, 6.1.1 and 6.1.2 with its type, value list, validator, requirement level and stability. It is normative; the tables of this document are informative copies, and a CI check keeps them, the proto, the JSON Schema and the three SDK key tables equal. Modality keys stay open (SC-1, A.8). |
| 10 | Extensions in NPZ | **Resolved: no** (FIL-6) | Roadmap decision "NPZ read only"; JSON Lines carries all events. |
| 11 | Future output profiles | **Resolved:** one stream type with profiles (7) | FEP-0003 and FEP-0005; vectors I01–I23, D01–D21, C01–C23, E01–E21. |
| 12-A1 | `decoder.causal` and `latency` | **Resolved** (MET-5) | Adopts the suite's choice. |
| 12-A2 | Custom keys in a defined namespace | **Resolved** (MET-3): reserved; accepted with a warning | Adopts the suite's choice. |
| 12-A3 | Encoded vocabularies | **Resolved** (HDR-14): meaning wins; use `vocab_id` | Adopts the suite's choice. |
| 12-A4 | Blank lines | **Resolved** (GEN-6): ignored | All SDKs ignore them. |
| 12-A5 | Lines after `end`, second header | **Resolved** (GEN-7, 4.4) | LSL (LSL-E5) and WebSocket already treat a later header as a new stream. |
| 12-A6 | Future minor versions | **Resolved** (VER-3): accept same major | Needed for the 1.x compatibility promise. Tested for decisions (F45) and headers (V54, W40; RC2). |
| 12-A7 | NPZ dtypes | **Resolved** (FIL-5) | Vector V27. |
| 12-A8 | Leakage pointers | **Resolved** (SEC-8): allowed | Adopts the suite's choice. |
| 12-A9 | Validator scope | **Resolved:** the conformance suite, level core, is the normative validator (9) | Three SDKs agree on it. |
| 12-A10 | V = 0; sparse k = V | **Resolved** (HDR-12, FRM-5) | Vector W03 (hypothesis-only producer, empty vocab) and the control placeholder vocab. |

### A.2 FEP-0001 (streaming trust events)
| # | Question | Outcome | Rationale |
|---|---|---|---|
| 1 | `segment_end` id | **Deferred to 1.1** | `trust_decision.input` already names the input; no consumer needs a segment id. |
| 2 | `PREVIEW` action | **Resolved: no.** Keep `is_final = false` | Every profile and SDK uses it (F22, F23, D06; the SDK `DecisionTracker` reports kind "preview"). A new action would break FEP-0001 consumers. |
| 3 | `char_confidences` in lattices | **Deferred to 1.1** | Depends on lattices (A.1 #3). |
| 4 | Weights hash in `decode_declaration` | **Deferred to 1.1** | `meta["decoder.weights_sha256"]` covers stream provenance; no evidence yet that the layer must check it. |
| 5 | `abstain` as the default declaration mode | **Deferred to 1.1** | DCL-6 already says SHOULD ABSTAIN. The reference default (`warn`) is an implementation choice; there is no field data on mismatch rates. |
| 6 | Rule 9 as a MUST | **Resolved: MUST NOT for 1.x decisions** (TD-9); 0.1 decisions keep SHOULD NOT | M2-18: 320 empty COMMITs on 400 no-signal T12 streams with the frozen Paper 1 v4 configuration. P12 (FEP-0003): no null-intent COMMIT is already a MUST. P12-03 (FEP-0005): no motion on no-signal input is already a MUST. The M2-18 commit gate shows that a layer can comply without losing its risk bound, and the P5-07 v5 candidate recipe (opt-in, commit gate on) took the T12 dry-run empty commits from 655 to 0. The version gate keeps Paper 1 v4 logs valid. New vectors F41–F47. |

### A.3 FEP-0002 (LSL)
| # | Question | Outcome | Rationale |
|---|---|---|---|
| 1 | Chunk size or maximum latency | **Deferred to 1.1** | Needs LAN tests (M6-10). |
| 2 | Back channel for OFFER selections | **Deferred to 1.1** | No UI uses it yet; `intent_feedback` covers intents. |
| 3 | `time_correction` statistics as required provenance | **Deferred to 1.1** | No evidence on which statistics matter. |
| 4 | LAN and Wi-Fi defaults | **Deferred to 1.1** | M6-10 not done. |

### A.4 FEP-0003 (output profiles, intent)
| # | Question | Outcome | Rationale |
|---|---|---|---|
| 1 | Name of the core | **Resolved: keep "NeuralTextStream" (NTS)** for all profiles | The name is in the binding tokens (`nts-lsl`, `nts-ws`), SDK APIs and vectors. A rename is a breaking change with no technical gain. |
| 2 | Direct COMMIT of irreversible intents | **Resolved: no** (INT-S4 unchanged) | P12: LTT never armed the irreversible keys with about 260 calibration units (α 0.01 infeasible). There is no evidence that a stricter α makes a direct commit safe. |
| 3 | `CONFIRM` action | **Resolved: no.** Keep OFFER + `confirm_required` | Keeps the FEP-0001 action set; D02, D03 pass in all SDKs. |
| 4 | No-signal reference as a MUST for irreversible configurations | **Resolved: MUST** (INT-S7) | P12: without the reference, 0.371 of zero-input presses acted (97 % wrong); with it, 0. Not testable on a stream (gap G-5). |
| 5 | How long an armed intent waits | **Resolved: the next decision unit only** (INT-S4) | The reference and vectors D02, D03, D18, D19 use it. A time-based wait: deferred to 1.1. |
| 6 | `intent.*` registry | **Resolved** (12.4) | Entries deferred with A.1 #7. |

### A.5 FEP-0004 (WebSocket)
| # | Question | Outcome | Rationale |
|---|---|---|---|
| 1 | Back channel on `/decisions` | **Deferred to 1.1** | As A.3 #2. |
| 2 | Clock-sync exchange | **Deferred to 1.1** | As A.1 #8. |
| 3 | `/events` resume | **Deferred to 1.1** | `/events` is a monitoring tap; no consumer needs resume. |
| 4 | `max_batch` default for small devices | **Deferred to 1.1** | No microcontroller producer tested yet. |
| 5 | LAN defaults (`reorder_timeout_s`, `resume_timeout_s`) | **Deferred to 1.1** | M6-10 not done. |

### A.6 FEP-0005 (control)
| # | Question | Outcome | Rationale |
|---|---|---|---|
| 1 | Gain level; horizon bound | **Deferred to 1.1** | P12-03: level 0.9 gave no motion; the horizon bound is not built or tested. |
| 2 | Full covariance | **Deferred to 1.1** | No decoder in the repo gives it. |
| 3 | Float-channel LSL binding for control | **Deferred to 1.1** | Not implemented. |
| 4 | Position control rules | **Deferred to 1.1** | The reference actuates velocity only; position is untested. |
| 5 | No-signal reference gate as a MUST | **Deferred to 1.1** | Mixed evidence: on MC_RTT it blocked almost every tick at level 0.9. |
| 6 | Click dwell rule | **Deferred to 1.1** | No evidence. |

### A.7 RC2 open questions (protobuf work, P1-02; answered in RC3)
| # | Question | Outcome | Rationale |
|---|---|---|---|
| Q-1 | JSON null in optional fields | **Resolved** (GEN-9): null only where the type says "or null" | Probes of the three SDKs (they agreed on all): null was refused in every checked field, except the fields already typed "or null" and `frame_period`, `latency`, `vocab_id`, `vocab_version` (header), `threshold`, `role` (intent decision), `intent` (feedback) and `absent` (control). Those types now say "or null". No SDK change. |
| Q-2 | LSL keys outside EXT-3 | **Resolved** (SEG-6, LSL-G3): written down | The three LSL consumers write the same keys; a rename gives no safety gain and breaks the reference adapters. |
| Q-3 | Control reason codes | **Resolved** (CTL-T9): open list | The three SDKs accept any string. A bridge acts on `action` and `velocity`, so an unknown code cannot cause motion. |
| Q-4 | Keys of `declaration` and `input` | **Resolved** (TD-F2, TD-13): `declaration` is an object; key tables are recommended | The reference layers write different `input` shapes per route (6.1.1). A strict table would refuse valid reference output. A list `declaration` was accepted by all three SDKs: now refused (F62). |
| Q-5 | Integer range | **Resolved** (GEN-10): at most 2^53 − 1 | All three SDKs accepted `seq` 2^60, but TypeScript reads 2^53 and 2^53 + 1 as one value, so TD-5 could differ. Now refused in all three (F60, W44). |
| Q-6 | A field of another profile | **Resolved** (PRF-5): a custom key | Written down from the SDKs; the generated JSON Schema now types profile fields per profile. |
| Q-7 | New enumeration values in a minor version | **Resolved** (VER-6 … VER-10, FEP-0007): version-gated, with a safe fallback per enumeration | Keeps every RC2 reject vector; makes 1.1 data readable by a 1.0 consumer with no unsafe action (D22, E22, E24). |
| Q-8 | Two SDK format checks | **Resolved** (INT-T7, CTL-T8): rule ids added | The checks are safe and in all three SDKs. |

### A.8 Semantic-convention registry questions (P1-04; answered in RC4) and gap G-12
| # | Question | Outcome | Rationale |
|---|---|---|---|
| SC-1 | Modality keys (`emg.*`, `eeg.*`, `meg.*`, `fnirs.*`, `implant.*`) | **Deferred** in RC4; **partly resolved** by the amendment of 2026-11-16 (MET-11, [FEP-0009](feps/0009-modality-semantic-conventions.md)): 8 keys for `emg`, `meg` and `implant` | A key needs a type, a unit and a meaning. The P4 adapters (emg2qwerty, KT-sEMG, Toronto sEMG, SpanishBCBL MEG, Willett, B2T '25) and NLB MC_RTT showed which facts a consumer needs and the producer knows. Only facts that every adapter of the modality can fill became keys. |
| SC-9 | `eeg.*` and `fnirs.*` keys | **Open** | No reference producer writes EEG or fNIRS streams yet. The namespaces stay planned and reserved (SC-2). |
| SC-2 | Planned namespaces reserved? | **Resolved** (MET-3, 12.5): yes | A warning only, so no stream changes; it keeps the names free for the FEP of SC-1. No producer in the repository writes such a key. |
| SC-3 | Is `""` a valid string value? | **Resolved** (MET-7): no, for the string keys of 3.4 | All three validators already refused `""`. The keys of 6.1.1 and 6.1.2 are audit data and not checked (TD-13). |
| SC-4 | Open or closed value lists | **Resolved** (MET-8): per key | Open where producers have their own values (regulatory status, calibration method, input route, check mode); closed where a consumer acts on the value or reads a fallback (`device.modality`, `declaration.status`), and for `declaration.where` (two places only, DCL-3). |
| SC-5 | Target stability of the `input` and `declaration` keys | **Resolved** (2.3): Development | Recommended audit data; shapes differ per route. |
| SC-6 | Units of counts and indices | **Resolved** (MET-9): no unit | A unit notation for counts adds nothing a consumer can check. |
| SC-7 | YAML or prose: which is normative | **Resolved** (MET-10): the YAML registry | It is the form that tools and SDKs read and that holds the validators. The tables stay as informative copies for readers; the CI check keeps them equal, so a difference is an erratum. |
| SC-8 | Generated SDK constants | **Resolved**: no spec change | The CI check gives the same guarantee for hand-written tables. Generation stays a tooling task. |
| G-12 | Optional fields whose type no validator checked | **Resolved** (GEN-11 and the rules of 1.6): the three validators check the types | The simplest rule that keeps valid data valid: the type of the field table, which the generated JSON Schema already checked. No accept vector changed. |

---

## Appendix B. Migration from 0.1 to 1.0

### B.1 What changes
| # | Change | Kind | Effect on 0.1 data |
|---|---|---|---|
| 1 | Header `spec_version` `"1.0"` | New version | 0.1 streams stay valid (VER-4) |
| 2 | `trust_decision.spec_version` (VER-1, TD-F3) | New field (required for 1.0 producers) | Absent = 0.1 (VER-2) |
| 3 | TD-9: blank final COMMIT text is a MUST NOT | Stricter, version-gated | 0.1 decisions keep SHOULD NOT |
| 3a | TD-12 (RC2): no blank candidate in `shown` of an OFFER, ASK or OFFER_WORDS (SHOULD NOT); consumers drop blank candidates (MUST NOT offer) | New, version-gated for producers (warning only) | 0.1 decisions: no finding; consumers still drop the blank candidate |
| 4 | INT-S7: no-signal reference MUST for irreversible configurations | Stricter (configuration rule) | None on streams |
| 5 | Same-major minor versions accepted (VER-3) | Looser | A 0.1 reader still rejects `"0.2"` |
| 6 | GEN-5 integers; GEN-6 empty lines; GEN-7 after `end` | Written down (SDK behaviour) | None |
| 7 | FRM-6 no frame revision; HDR-12 V = 0; HDR-14; MET-3; MET-5; FIL-5; FIL-6; SEC-8 pointers | Clarifications (resolutions of A1–A10) | None |
| 8 | FEP-0001 … FEP-0005 folded in | Additive | None |
| 9 | LSL and WebSocket bindings replace the v0.1 sketches 6.3 and 6.4 | Normative binding | A 6.3-sketch WebSocket producer needs `ws_seq` (one-line change) |
| 10 | NPZ is read only for new data (FIL-6) | Recommendation | NPZ files stay valid |
| 11 | Flat `meta` keys (`subject`, `session`) | Not conventions | Use `subject.id`, `session.id` |
| 12 | Registries (12) | New | None |
| 13 | RC3: GEN-9 (null only where typed "or null") | Written down (SDK behaviour) | None |
| 14 | RC3: GEN-10 (integers at most 2^53 − 1) | Stricter (all versions) | A value above 2^53 − 1 is refused (no known producer writes one) |
| 15 | RC3: VER-6 … VER-10 (unknown enumeration values) | Looser for newer-minor data; safe fallbacks | 0.1 and 1.0 data: unchanged (unknown values stay errors) |
| 16 | RC3: TD-F2 `declaration` is an object; TD-13 key tables | Stricter (all versions) | A non-object `declaration` is refused (the reference layer writes objects) |
| 17 | RC3: SEG-6, LSL-G3, CTL-T9, PRF-5, INT-T7, CTL-T8 | Written down | None |
| 18 | RC4: GEN-11 (optional fields have their table type; HDR-16, DEC-6, HYP-5, INT-T8, SQ-1, PTR-1, TIM-4, TD-F2 `reason`, CTL-T8 `level`) | Stricter (all versions) | A wrongly typed optional field is refused (the JSON Schema already refused it; no reference producer writes one) |
| 19 | RC4: MET-3 planned namespaces reserved; MET-7 … MET-10 | Written down / clarification | None (a warning for a custom key in `emg.*` etc.) |

### B.2 Reading 0.1 data in a 1.x consumer
1. A header with `spec_version` `"0.1"`: read it as 1.0, with these mappings: no field is renamed; NPZ key `version` = `spec_version`; NPZ `blank_id` −1 = null; NPZ without `vocab_type` = `"char"`.
2. A `trust_decision` without `spec_version`, or with `"0.1"`: apply the 0.1 rules. TD-9 is a SHOULD NOT: accept the decision, warn, and do not forward a blank text (a bridge rule that did not change in effect: v0.1 rule 9 already said a bridge SHOULD NOT forward it).
3. LSL streams without `binding` read as `nts-lsl/0.1` with `event_clock = source` (LSL-V1).

### B.3 Upgrading a producer
1. Write `"spec_version": "1.0"` in the header.
2. Trust layers: write `"spec_version": "1.0"` in every `trust_decision`. Never emit a final text COMMIT with a blank `shown[0]`: turn it into the non-commit decision (the M2-18 commit gate does this: `FrozenTrustConfig.with_commit_gate(min_chars=1)`). Then remove blank candidates from `shown` of OFFER, ASK and OFFER_WORDS (TD-12); an OFFER with no candidate left becomes `ABSTAIN` with `shown = []` (the collector does this, FEP-0006 3.2).
3. Intent configurations that can arm irreversible intents: fit them with a no-signal reference.
4. WebSocket producers: send `ws_seq` (8.3.4).
5. Check with `fidetype conformance check --level provenance` and the profiles you claim.

*Implementation status (2026-11-15, RC3; the RC2 note stays valid):* steps 1 and 2 are in all three SDKs. The Python, TypeScript and Rust validators (`NTS-VERSION`, the streaming validators, the LSL `nts_header` check and the WebSocket header check) and the JSON schema accept a header with `"0.1"`, `"1.0"` or `"1.<minor>"` (gap G-2 closed). The writers still write `"0.1"` by default, so existing output does not change. A producer that writes `"1.0"` headers is accepted by every reference consumer. A 0.1-only consumer outside this repository still refuses `"1.0"` (11.3).

---

## Appendix C. Conformance traceability
Each normative rule id, its keyword, and the check ids and vectors that test it. Vector ids: `V` = v0.1, `F` = fep-0001, `L` = fep-0002, `I`/`D` = fep-0003, `W` = fep-0004, `C`/`E` = fep-0005. **Status:** `T` tested (accept and reject vectors), `P` partly tested (one side, or a heuristic), `G` gap (no check). A gap is listed in C.2.

### C.1 Table
| Rule | Key | Check | Vectors | Status |
|---|---|---|---|---|
| GEN-1 | MUST NOT | — | — | G-6 |
| GEN-2 | MUST | NTS-PARSE, FEP1-PARSE, FEP3-PARSE, FEP5-PARSE, FEP4-FRAMING | V41, W23 | T |
| GEN-3 | MUST | NTS-JSONL-FRAME | V35, L04 | T (accept) |
| GEN-4 | MUST | (consumer) | V38, V40, W04, F25 | T |
| GEN-5 | MUST | type checks of every profile | F34, W25 (`1.5`); V61, F50, W43 (`0.0`, `1.0`, `2.0`) | T (reject vectors; JSON Schema `integer` counts `1.0` as an integer, so only the validators check it) |
| GEN-6 | MUST | (consumer) | — | G-7 |
| GEN-7 | MUST | (consumer) | V48 | P (second header: no vector) |
| GEN-8 | MAY / MUST NOT | FEP2-CONSUME, FEP4-RESUME | V05, L10, W11 | T |
| GEN-9 | MAY / MUST | type checks of every profile | (null where typed: V03 `blank_id`, F22 `config_id`; refused: F27 …) | P (no vector per field; SDK probes in the RC3 work) |
| GEN-10 | MUST | integer checks of every profile (`is_int`, `isInt`, `json_int`) | F61 / F60, W44 | T |
| GEN-11 | MUST | type checks of every profile (RC4) | V69, F63, D24, E25 / V70 … V82, F64 … F66, D25, D26, I25, C25, E26, E27 | T |
| HDR-1 | MUST | NTS-JSONL-HEADER | V45, V50, W18 | T |
| HDR-2 | MUST | NTS-VERSION, FEP2-DESC, FEP4-HANDSHAKE | V16, V17, V53–V60, F48, F49, L23, L33–L35, W21, W39–W42 | T |
| HDR-3 | MUST | NTS-VOCAB-STR | — | P |
| HDR-4 | MUST | NTS-VOCAB-UNIQUE | V12 | T |
| HDR-5 | MUST | NTS-VOCAB-TYPE | V15, V68 | T |
| HDR-6 | MUST | NTS-BLANK | V14, V47 | T |
| HDR-7 | MUST | NTS-SOURCE | — | P |
| HDR-8 | MUST | NTS-META-OBJECT, FEP4-HANDSHAKE | W38 | T (WebSocket); P (files) |
| HDR-9 | MUST | NTS-FRAME-PERIOD | V19 | T |
| HDR-10 | MUST | NTS-LATENCY | V18 | T |
| HDR-11 | MUST | NTS-CLOCK | V52, V67 | T |
| HDR-12 | MAY | (consumer), NTS-NORM | V62, W03 / V63, V64, V65 | T |
| HDR-13 | MUST NOT | FEP2-CONSUME | V03, L32 | T (accept) |
| HDR-14 | — | advisory | — | P (advisory warning) |
| HDR-15 | MUST | NTS-VOCAB-ID | — | P |
| HDR-16 | MUST | NTS-VOCAB-ID | V69 / V78 | T |
| MET-1 | MUST | NTS-META-TYPES | V30, V32, V34 | T |
| MET-2 | MUST | NTS-META-JSON | V25 | T |
| MET-3 | SHOULD | advisory (NTS-NAMESPACE; RC4: planned namespaces too) | V34, V69 | P (advisory warning) |
| MET-4 | MUST | NTS-META-LOOKAHEAD | V31 | T |
| MET-5 | SHOULD | TR-CAUSAL, TR-OFFLINE-LATENCY | — | P (level trust-ready) |
| MET-6 | SHOULD / MUST NOT | TR-CALIB | — | P |
| MET-7 | MUST NOT | NTS-META-TYPES (`non_empty_string`) | (string keys of every accept vector) | P (no reject vector for `""`; all three validators refuse it) |
| MET-8, MET-9 | MUST NOT / — | registry (`semconv.py --check`) | — | P (definitions; open lists are not checked) |
| MET-10 | — | CI job `semconv` (`tools/semconv/semconv.py --check`) | (all accept vectors: meta values pass the registry validators) | T (tooling) |
| MET-11 | SHOULD NOT | NTS-META-TYPES (types of the modality keys), advisory (NTS-MODALITY-MATCH; amendment 3) | V83, V84, V85, V95 / V86, V87 (types); V93, V94, V96, K32 (warning) | T (types); P (advisory warning) |
| FRM-1 | MUST | NTS-V-MATCH | V46 | T |
| FRM-2 | — | NTS-JSONL-FRAME | V42, V88 (accept); V89 … V92 (reject: sparse keys of a wrong type on a dense frame, amendment 2) | T |
| FRM-3 | MUST | NTS-NORM, NTS-SPARSE | V08, V23, V24, V43, F40 | T |
| FRM-4 | MUST NOT | NTS-LP-FINITE | V09, V10, L22 | T |
| FRM-5 | MUST | NTS-SPARSE (normalisation only) | V42 | P (dense spreading is consumer behaviour) |
| FRM-6 | — | NTS-FT-MONO | V11, V44 | T (via TIM-2) |
| FRM-7 | MUST | NTS-LP-2D | — | P |
| FRM-8 | MUST | NTS-V-MATCH | V13 | T |
| FRM-9 | MUST | NTS-FT-SHAPE | V04 | P |
| SEG-1, SEG-2 | MAY / MUST | FEP1 summary (`segments`) | F01, F02, F03 | T (accept) |
| SEG-3 | SHOULD NOT | (trust layer) | F03 | P |
| SEG-4, SEG-5 | MUST | FEP1-SEGMENT | F04, F05, F06 | T |
| SEG-6 | MUST / MUST NOT | FEP1-SEGMENT | L07, F63 / F64 | T (type; the content part is G-6) |
| SQ-1 | MUST | NTS-EVT-SIGNAL-QUALITY | V51, V69 / V73 | T |
| SQ-2 | MUST NOT | — | — | G-6 |
| DEC-1 | MUST NOT | — | — | G-6 |
| DEC-2, DEC-3, DEC-4 | MUST | NTS-EVT-DECISION | V36, V37, V51 | T |
| DEC-5 | MUST NOT / SHOULD | TR-CALIB, PV-CALIB-ID | — | P |
| DEC-6 | MUST | NTS-EVT-DECISION, NTS-EVT-POINTER | V69 / V76, V77, V81 | T |
| HYP-1 | MUST | NTS-EVT-HYPOTHESIS | V51, F07 | P (accept only) |
| HYP-2, HYP-3 | MUST | (consumer) | F07 | P |
| HYP-4 | — | see SEC-8 | | |
| HYP-5 | MUST | NTS-EVT-HYPOTHESIS | V69 / V70, V71, V72 | T |
| EVD-1 | MUST | FEP1-EVIDENCE | F07, F08, F09, F10, F11 | T |
| EVD-2 | MUST NOT | — | — | G-6 |
| EVD-3 | MUST | FEP1-SCORE | F14 | T |
| EVD-4 | MUST | FEP1-EVIDENCE | F12, F13 | T |
| DCL-1 | MUST | FEP1-DECL | F15, F16, F17–F20 | T |
| DCL-2 | SHOULD | — | — | G-8 |
| DCL-3 | MUST | (trust layer) | F16 | P |
| DCL-4 | MUST | — | — | G-6 |
| DCL-5, DCL-6 | MUST / SHOULD | (reference layer tests) | — | G-9 |
| DCL-7 | MUST NOT | — | — | G-6 |
| PTR-1 | MUST | NTS-EVT-POINTER | V51, V69 / V74, V75, V82 | T |
| TIM-1 | MUST | NTS-FT-FINITE | — | P |
| TIM-2 | MUST | NTS-FT-MONO | V11, V44 | T |
| TIM-3 | MUST | — | — | G-7 |
| TIM-4 | MUST | NTS-EVT-TIMING, FEP5-CONTROL | V39, C19, C03; RC4: V69, F63 / V79, V80, F65, I25, C25 | T |
| TIM-5 | MAY | — | — | G-7 |
| TD-F1 | MUST | FEP1-TD-FORMAT | F27–F33, F59 | T |
| TD-F2 | MUST | FEP1-TD-FORMAT | F24, F34, F50, F51–F54, F62, F66, E27 | T |
| TD-F3 | MUST | FEP1-TD-FORMAT | F41, F42, F45 / F46, F47 | T |
| TD-1 | MUST NOT | consumer `acted` lists | F22, F23, D06, L26, W31 | T |
| TD-2 | — | see DEC-5 | | |
| TD-3 | SHOULD | — | — | G-7 |
| TD-4 | MUST NOT | FEP1-TD-INPUT, NTS-TD-INPUT (amendment 4) | F21, V97 | T |
| TD-14 | MUST | streaming validators (`StreamingTrustLayer`, `StreamValidator`), collector `validate` (amendment 5) | S01 … S06, V97 (event by event) | T |
| TD-5 | MUST | FEP1-TD-FINAL, FEP3-TD-FINAL, FEP5-TD-ORDER | F25, F38, D14, E16 | T |
| TD-6 | MUST | FEP1-TD-FINAL, FEP2-DECISIONS, FEP4-DECISIONS | F26, F36, L31, W37, D13 | T |
| TD-7 | MUST NOT | FEP1-TD-FINAL | F37 | T |
| TD-8 | MUST | FEP1-TD-FORMAT | F35 | T |
| TD-9 (1.x) | MUST NOT | FEP1-TD-FORMAT | F41 / F43, F44 | T |
| TD-9 (0.1) | SHOULD NOT | SDK `DecisionTracker` warning | F42 | T (accept) |
| TD-10 | MAY | — | F24, F41 | T (accept) |
| TD-11 | MUST | FEP1-KIND | F39 | T |
| TD-12 (1.x producer) | SHOULD NOT | FEP1-TD-SHOWN (advisory), SDK `DecisionTracker` warning | F55 (warns), F56 (0.1: no warning) | T (accept with warning) |
| TD-12 (consumer) | MUST NOT | consumer `offered` lists, SDK `DecisionTracker.offered` | F55, F56 | T (accept) |
| TD-13 | SHOULD / MUST NOT | — | — | G-10 (audit data; only the object type is checked, TD-F2) |
| PRV-1 … PRV-3 | SHOULD / MUST | — | — | G-10 |
| PRF-1 | MAY | — | I02, D04, C02, E02 | T (accept) |
| PRF-2 | MUST NOT | — | — | G-6 |
| PRF-3 | — | FEP3-INTENT | I06 | P |
| PRF-4 | MUST | FEP3-TD-FORMAT, consumer `acted` lists | D12; F58, D22 (unknown profile not acted) | T |
| PRF-5 | — / SHOULD NOT | (profile checks) | — | P (SDK behaviour; no vector) |
| INT-D1 … INT-D4 | MUST | FEP3-DECL | I01 / I07–I11 | T |
| INT-D5 | MUST | FEP3-VOCAB | I05 / I12 | T |
| INT-D6 | SHOULD | — | — | G-8 |
| INT-E1 … INT-E5, INT-E7 | MUST | FEP3-INTENT | I01, I02, I04 / I13–I21 | T |
| INT-E6 | — | (trust layer) | I05 | P |
| INT-F1 | MUST | FEP3-FEEDBACK | I03 / I22 | T |
| INT-F2 | MUST NOT | — | — | G-6 |
| INT-T1 … INT-T3 | MUST | FEP3-TD-FORMAT | D01–D06 / D07–D12 | T |
| INT-T4 | MUST | FEP3-TD-FINAL | D04, D06 / D13, D14 | T |
| INT-T5 | MUST | consumer `acted_intents` | D06 | P |
| INT-T6 | MAY / MUST | FEP3-TD-FINAL | D04 / D14 | T |
| INT-T7 | MUST | FEP3-TD-FORMAT | D02 / — | P (no reject vector) |
| INT-T8 | MUST | FEP3-TD-FORMAT | D01, D24 / D25, D26 | T |
| INT-S1 | MUST NOT | FEP3-SAFETY | D15 | T |
| INT-S2 | MUST NOT | FEP3-SAFETY | D03 / D21 | T |
| INT-S3 | MUST | FEP3-SAFETY (threshold) | D16 | P (the fit method is not testable on a log) |
| INT-S4 | MUST NOT | FEP3-SAFETY | D02, D03 / D17, D18, D19 | T |
| INT-S5 | MUST NOT | FEP3-SAFETY | D05 / D20 | T |
| INT-S6 | MUST NOT | — | — | G-5 (needs the input stream next to the log) |
| INT-S7 | MUST | — | — | G-5 |
| INT-S8 | MUST | — | — | G-11 |
| INT-S9 | MUST NOT | — | — | G-9 |
| INT-S10 | SHOULD | — | — | G-10 |
| CTL-D1 … CTL-D3 | MUST | FEP5-DECL | C01, C02, C05 / C06–C11 | T |
| CTL-D4 | — | FEP5-V01-CORE | C01 | P |
| CTL-1 … CTL-4 | MUST | FEP5-CONTROL | C01, C03 / C12–C18 | T |
| CTL-12 | MUST | FEP5-CONTROL | C04 / C21 | T |
| CTL-E1 | MUST | FEP5-ENABLE | C01 / C20 | T |
| CTL-E2, CTL-E3 | MUST NOT | — | — | G-6 |
| CTL-T1 … CTL-T4 | MUST | FEP5-TD-FORMAT | E01–E04 / E09–E14 | T |
| CTL-T5 | MUST | FEP5-TD-ORDER | E02, E04 / E15, E16 | T |
| CTL-T6 | MUST | — | — | G-7 |
| CTL-T7 | SHOULD | — | — | G-8 |
| CTL-T8 | MUST | FEP5-TD-FORMAT | E01, E25 / E26 | T |
| CTL-T9 | MUST / SHOULD / MUST NOT | FEP5-TD-FORMAT (list of strings) | E01 | P |
| CTL-S1 | MUST | FEP5-SAFETY | E01 / E05, E19 | T |
| CTL-S2 | MUST NOT | FEP5-SAFETY (reason codes) | E01 / E08 | P (the gates need the input stream) |
| CTL-S3 | MUST | FEP5-SAFETY | E06 | P (accel bound and "no delay of a stop" untested) |
| CTL-S4 | MUST / SHOULD | FEP5-SAFETY | E04 | P |
| CTL-S5 | MUST | FEP5-SAFETY | E03 / E07 | T |
| CTL-S6 | SHOULD / MUST NOT | FEP5-SAFETY | E18 | P |
| CTL-S7 | MUST NOT | FEP5-SAFETY | E02, E21 / E17, E20 | T |
| CTL-S8 | SHOULD | — | — | G-10 |
| FIL-1 | MUST | NTS-PARSE | V26 | T |
| FIL-2 | MUST | NTS-NPZ-KEYS | V28 | T |
| FIL-3 | MUST | (reader) | V20 | T |
| FIL-4 | MUST | (reader) | V21 | T |
| FIL-5 | SHOULD / MUST | advisory | V27 | T |
| FIL-6 | SHOULD | — | — | G-8 |
| LSL-N1 | SHOULD | — | — | G-8 |
| LSL-F1 | MUST | FEP2-FRAMES | L01, L02 / L17 | T |
| LSL-F2 | MUST | FEP2-FRAMES | L16 | T |
| LSL-F3 | MUST | FEP2-FRAMES | L18 | T |
| LSL-F4 | MUST / SHOULD | FEP2-CONSUME | L01, L02 | T (accept) |
| LSL-F5 | MUST | FEP2-CONSUME | L04 / L22 | T |
| LSL-F6 | MUST | FEP2-FRAMES | L20 | T |
| LSL-F7 | MUST NOT | FEP2-CONSUME | L32 | T (accept) |
| LSL-D1 | MUST | FEP2-DESC | L15 | T |
| LSL-D2 | MUST | FEP2-DESC | L23, L33 / L34, L35 | T |
| LSL-D3 | MUST | FEP2-DESC | L24 | T |
| LSL-D4 | MUST | (consumer) | L01 | P |
| LSL-E1 | MUST | FEP2-MARKERS | L21 | T |
| LSL-E2, LSL-E4 | MUST | FEP2-CONSUME | L13 | T (accept) |
| LSL-E3 | MAY / MUST | FEP2-CONSUME | L13 | T (accept) |
| LSL-E5 | — | FEP2-CONSUME | L11 | P |
| LSL-C1 | MUST | — | — | G-7 (producer behaviour) |
| LSL-C2, LSL-C3 | MUST | FEP2-CONSUME | L01, L05 | T (accept); host-name rule G-6 |
| LSL-C4 | MAY | FEP2-CONSUME | L09 | T (accept) |
| LSL-C5 | MUST | FEP2-CONSUME, FEP2-BINDING | L11, L12 / L25 | T |
| LSL-C6 | — | FEP2-CONSUME | L01 | P |
| LSL-C7 | MUST NOT / SHOULD | FEP2-CONSUME | L36 | P (consumer side; the producer SHOULD is not checked) |
| LSL-C8 | MUST | FEP2-CONSUME | L37 | T (accept; without the rule L37 gives 2 final decisions) |
| LSL-G1 | — | FEP2-CONSUME | L06, L07, L08 | T (accept) |
| LSL-G2 | MUST NOT / MUST | FEP2-CONSUME | L10 | T (accept) |
| LSL-G3 | — | FEP2-CONSUME | L06, L07, L08 | T (accept) |
| LSL-X1 | MUST | FEP2-DECISIONS | L26 / L29, L30 | T |
| LSL-X2 | MUST | FEP2-DECISIONS | L26 / L27, L28, L31 | T |
| LSL-X3 | MUST NOT | consumer `acted` | L26 | T |
| LSL-V1 | MUST | FEP2-BINDING | L03 / L19 | T |
| WS-H1 | MUST | — | — | G-7 (HTTP layer; vectors are sans-IO) |
| WS-H2 | MUST | FEP4-HANDSHAKE | W01 / W19 | T |
| WS-H3 | SHOULD | — | — | G-8 |
| WS-F1 | MUST | FEP4-FRAMING | W22 | T |
| WS-F2 | MUST | FEP4-FRAMING | W23 | T |
| WS-F3 | SHOULD / MAY | FEP4-FRAMING | W27 (batch size) | P (message size untested) |
| WS-F4 | MUST | FEP4-CONSUME | W04, W05 | T (accept) |
| WS-M1 … WS-M3 | MUST | FEP4-CONSUME | W04, W15 | P (WS-M2 no-forward untested) |
| WS-S1 | MUST | FEP4-HANDSHAKE | W18, W21, W38 | T |
| WS-S2 | MAY / SHOULD | FEP4-CONSUME | W05, W14 | T (accept) |
| WS-Q1 | MUST | FEP4-FRAMING | W01 / W24, W25 | T |
| WS-Q2 | MUST | FEP4-ORDER | W06 | T (accept) |
| WS-Q3 | — | FEP4-ORDER | W07, W08, W09 | T (accept) |
| WS-Q4 | MUST | FEP4-FRAMING | W02 / W26, W27 | T |
| WS-Q5 | MUST | FEP4-ORDER | W08 | T (accept) |
| WS-A1 | — | FEP4-CONSUME | W17 | T (accept) |
| WS-A2 | MUST NOT | — | — | G-7 (producer) |
| WS-A3 | SHOULD / MUST NOT | — | — | G-7 |
| WS-D1 | MUST | FEP4-DECISIONS | W31 / W34, W36 | T |
| WS-D2 | — | FEP4-DECISIONS | W33 | T (accept) |
| WS-D3 | MUST | FEP4-DECISIONS | W32 / W37 | T |
| WS-D4 | MUST NOT | — | — | G-7 |
| WS-R1 | MUST | FEP4-RESUME | W10 / W28 | T |
| WS-R2 | MUST | FEP4-RESUME | W11, W12, W13 | T (accept) |
| WS-T1 | MAY / SHOULD / MUST | FEP4-AUTH | W15, W16 | T (accept) |
| WS-T2 | MUST | FEP4-AUTH | W29 | T |
| WS-T3 | MUST NOT | — | — | G-6 |
| WS-T4 | MUST | — | — | G-7 |
| WS-K1, WS-K2 | MUST | FEP4-CONSUME | W01, W30 | P |
| WS-K3, WS-K4 | SHOULD NOT / MAY | — | — | G-7 |
| WS-V1 | MUST | FEP4-HANDSHAKE, FEP4-DECISIONS | W05 / W20, W35 | T |
| SEC-1 | MUST NOT | — | — | G-6 |
| SEC-2 | SHOULD | TR-DERIVED | — | P |
| SEC-3 | MUST NOT | NTS-PRIVACY (heuristic) | — | P |
| SEC-4 | MUST | PV-PSEUDONYM (heuristic) | — | P |
| SEC-5, SEC-6 | MUST NOT / SHOULD NOT | NTS-PRIVACY (heuristic, `meta` only) | — | P |
| SEC-7 | SHOULD | — | F24 | P |
| SEC-8 | MUST NOT | NTS-LEAK-KEYS (heuristic) | V33 | P |
| SEC-9, SEC-10 | MUST / SHOULD | see WS-T*, LSL-C3 | | |
| VER-1 | MUST | NTS-VERSION, FEP1-TD-FORMAT | V53, F48, L33, W39 (header); F41 (decision) | P (accept side: a validator cannot require `"1.0"` from a producer that claims 0.1) |
| VER-2 | — | FEP1-TD-FORMAT | F42 | T |
| VER-3 | MUST | NTS-VERSION, FEP1-TD-FORMAT, FEP2-DESC, FEP4-HANDSHAKE | V53, V54, V60, F45, F48, L33, W39, W40 / V57, L35 | T |
| VER-4 | MUST | all v0.1 vectors | V01–V52 | T |
| VER-5 | MUST | NTS-VERSION, FEP1-TD-FORMAT, FEP2-DESC, FEP4-HANDSHAKE | V16, V55–V59, F46, F47, F49, L34, L35, W41, W42 | T |
| VER-6, VER-7 | — / MUST | enum checks of every profile | V67, F59, D23, E23 (and every RC2 enum reject vector) | T |
| VER-8 | MUST | enum checks of every profile | V66, F57, F58, I24, D22, C24, E22 / V68 | T |
| VER-9 | MUST | FEP2-DESC, FEP2-BINDING, FEP4-HANDSHAKE | L19, L24, L25, W20 | T (RC2 vectors) |
| VER-10 | MUST NOT / MUST | consumer `acted`, `acted_intents`, `moving_ticks`; FEP5-SAFETY; SDK `DecisionTracker` | F58, D22, E22 / E24 | T |
| EXT-1 … EXT-4 | — | process rules | — | — |
| EXT-5 | MUST | see GEN-4, PRF-4 | | |
| FEP-1 | MUST | process rule | — | — |
| CNF-1 | MUST NOT | process rule | — | — |
| CNF-2 | — | `nts-conform` levels (definition) | kit (all entries) | — |
| CNF-3 | — | TR-SOURCE, TR-MODALITY, TR-CAUSAL, TR-OFFLINE-LATENCY, TR-DERIVED, TR-CALIB, TR-LANGUAGE, NTS-VT-CHAR | K01 / K33, K35, K36 | T (stream level) |
| CNF-4 | — | PV-STREAM-ID, PV-DECODER, PV-WEIGHTS, PV-ADAPTER, PV-CALIB-ID, PV-PSEUDONYM | K01 / K34 | T (stream level) |
| CNF-5 | MUST | `nts-conform check` (producer level) | — | P (the tool cannot see if the evidence is real output) |
| CNF-6, CNF-7 | — | `nts-conform kit` (consumer level, bindings) | kit (all entries) | T |
| CNF-8 | MUST | `nts-conform certified --check` | `conformance/certified.json` | T (tooling) |

### C.2 Gaps
| Gap | Rules | What is missing | Proposed fix |
|---|---|---|---|
| ~~**G-1**~~ (closed) | 7.4 (all CTL rules) | Closed in this draft: the TypeScript and Rust SDKs run the control profile `fep-0005` (44 vectors) with the Python verdicts, and the parity scripts include it. | Done (TS `profiles/fep0005.ts`, Rust `profiles/fep0005.rs`). |
| ~~G-2~~ | HDR-2, VER-1, VER-3, LSL-D2 | **Closed in RC2.** All three SDKs, the LSL and WebSocket header checks and the JSON schema accept `"0.1"` and `"1.<minor>"` and refuse other values. | Vectors V53–V60, F48, F49, L33–L35, W39–W42. |
| ~~G-3~~ | GEN-5 | **Closed in RC2.** Golden vectors with an integer written with a fraction part. | V61 (`blank_id: 0.0`), F50 (`seq: 1.0`), W43 (`ws_seq: 2.0`). |
| ~~G-4~~ | TD-F2 | **Closed in RC2.** Reject vectors for the types of `session`, `config_id`, `input`, `latency_s`. | F51–F54. All three SDKs already refused them. |
| **G-5** | INT-S6, INT-S7, CTL-S2 (gates) | No-signal gates need the input stream next to the decision log; INT-S7 is a configuration property. A log-only validator cannot check them. | A paired-file check (input stream + decision log), and a configuration check in `fit_intent_config`. |
| **G-6** | GEN-1, SQ-2, DEC-1, EVD-2, DCL-4, DCL-7, PRF-2, INT-F2, CTL-E2, CTL-E3, WS-T3, SEC-1, LSL-C3 (host name) | Behaviour or content rules that a stream validator cannot see. | Producer self-declaration in a conformance report; heuristics where possible (for example a free-text detector for `reason`). |
| **G-7** | GEN-6, TIM-3, TIM-5, TD-3, CTL-T6, LSL-C1, WS-H1, WS-A2, WS-A3, WS-D4, WS-T4, WS-K3, WS-K4 | Consumer, bridge, producer-runtime or network behaviour. No vector. | Scenario vectors for consumers (empty lines, a second header); bridge test harness (TTL expiry); network tests (M6-10). |
| **G-8** | DCL-2, INT-D6, CTL-T7, FIL-6, LSL-N1, WS-H3 | SHOULD rules with no check. | Advisory checks in the suite. |
| **G-9** | DCL-5, DCL-6, INT-S9 | Trust-layer behaviour; tested by unit tests of the reference layer only (`tests/test_trust_streaming.py`, `tests/test_intent_trust.py`), not by vectors. | Trust-layer scenario vectors (input + configuration → expected decisions). |
| **G-10** | PRV-1 … PRV-3, INT-S10, CTL-S8 | Audit SHOULD rules; no check. | A `provenance` level for decision logs. |
| **G-11** | INT-S8, CTL-S2 (evaluation part) | Evaluation reporting rules. | A benchmark submission check (roadmap P6 / P13). |
| ~~G-12~~ | GEN-9, SEG-6 (types of fields that no validator checks) | **Closed in RC4** (GEN-11). The three validators check the types of every optional field that the generated JSON Schema types and the spec tables list (1.6). | V69 … V82, F63 … F66, D24 … D26, I25, C25, E25 … E27. |
| **G-13** (new in RC4; **closed**: part b by amendment 1, part a by amendment 2 of 2026-11-16) | FRM-2, GEN-9 | Two places where the generated JSON Schema is stricter than the validators, and the spec allows the validator verdict: (a) a dense frame (with `log_probs`) that also carries sparse keys of a wrong type; the consumer uses the dense form and ignores the sparse keys; (b) control `absent: null` (GEN-9 allows it; a repeated proto field had no null). **(b) closed:** new proto option `json_null_list` (a repeated field whose whole value MAY be null); the schema accepts `absent: null`; vector C26 (accept). **(a) closed by amendment 2: option A2 applies** (FRM-2; vectors V88 accept, V89 … V92 reject; the three validators check the types; the schema did not change). The options were: **A1** a frame MUST NOT carry both forms (simple and unambiguous; the validators then refuse data that they accept now, so a version gate or a 2.0 change); **A2** both forms MAY be present, the dense form wins, and the sparse keys MUST still have their types (the validators add type checks; the schema stays as it is; no valid stream with well-typed keys changes); **A3** both forms MAY be present and the sparse keys are ignored without a type check (the schema relaxes them on a dense frame with an `if`/`then` rule; nothing else changes). A2 was the recommendation: the GEN-11 rule (a field of a table has its type when present). | None (closed). |

Summary: of the rule groups in C.1, the frame core, segments, evidence, decision format, intent and control formats, and both bindings have accept and reject vectors. The gaps are mostly behaviour that a stream validator cannot see. RC2 closed G-2 (1.0 headers), G-3 and G-4, and then G-1 (control profile parity in TypeScript and Rust). RC3 added G-12 (field types that no validator checks), and RC4 closed it (GEN-11); RC4 added G-13 (two places where the schema is stricter than the spec), and the two amendments of 2026-11-16 closed it (A2 for part a). The RC3 and RC4 behaviour changes have vectors in all three SDKs. Amendment 3 (2026-11-17) adds rows for MET-11 (the last rule id without a row) and CNF-2 … CNF-8; no new gap.

### C.3 Generated JSON Schema (informative; added by roadmap task P1-02, 2026-11-15; updated in RC3 and RC4)
This subsection adds no rule and changes no row of C.1. The proto3 files [`proto/neuraltextstream/v1/`](proto/neuraltextstream/v1/) describe the data model of this document; the JSON Schema [`schemas/nts-v1.schema.json`](schemas/nts-v1.schema.json) is generated from them and checks one JSON object (one line) at a time. On the 345 vectors it gives the SDK verdict on all 213 vectors whose verdict depends on one line (111 accept, 102 reject): 0 mismatches (amendment 2: 210 of 341; amendment 1 of 2026-11-16: 205 of 336; RC4 before the amendments: 201 of 330; RC3: 178 of 304). RC3: an enumeration field accepts any string; the known values are required by `Header.known` and `TrustDecision.known` unless `spec_version` is a newer minor version (VER-7, VER-8). So an unknown value on another event (for example F04, I22) depends on the header line: these vectors moved to the class cross-line. Integers have the bounds of GEN-10. Profile fields are typed per profile (PRF-5); RC4: the control decision `t` too (7.4.5). Rules that it checks: HDR-1 (required keys), HDR-2 … HDR-11, GEN-2, GEN-3, FRM-1/FRM-2 (form), FRM-4, SEG-4 (type), SEG-5, SQ-1, DEC-2 … DEC-4, HYP-1, EVD-1 (values), EVD-3, EVD-4, DCL-1, PTR-1, TD-F1 … TD-F3, TD-8, PRF-4, INT-D1 … INT-D4 (except unique ids), INT-E3 (per score), INT-E7, INT-F1, INT-T1 … INT-T3, CTL-D1, CTL-D2, CTL-D3 (presence of the intent declaration), CTL-4 (types), CTL-E1, CTL-T1 … CTL-T4, CTL-T8, INT-T7, GEN-10, VER-3, VER-5, VER-7 (header and decisions), PRF-5, TD-F2 `declaration`; RC4: GEN-11 (HDR-16, DEC-6, HYP-5, SQ-1 `channels`, TIM-4 types, TD-F2 `reason`, INT-T8, CTL-T8 `level`). All other rules stay with the checks of C.1 (they need other lines, the header, arithmetic, the trust rules, the spelling of a number (GEN-5) or the transport). Mapping rules, the list by class and the vectors: [`proto/README.md`](proto/README.md).

---

## Appendix D. Relation to other standards
| Standard | Relation to NTS |
|---|---|
| [LSL](https://labstreaminglayer.org/) | Different layer (raw signals into a decoder). NTS is carried over LSL (8.2). |
| [BIDS](https://bids.neuroimaging.io/) | Raw data at rest. An NTS file could be a BIDS derivative of a recording. |
| ISO/IEC TS 27571:2026 | A raw-data format for non-invasive BCI. **Status UNVERIFIED.** Different layer. |
| [W3C EMMA 1.0](https://www.w3.org/TR/emma/) | `emma:confidence`, `emma:one-of` for n-best. NTS `hypothesis` can convert to EMMA. Not neural-specific; no per-frame distributions. |
| [IEEE P2731](https://standards.ieee.org/ieee/2731/) | BCI terminology. We align terms when it is published. |
| [Apple BCI HID](https://developer.apple.com/documentation/accessibility/brain-computer-interface-hid-reference-for-connecting-to-apple-platforms) (Usage Page 0x60) | Downstream. A bridge maps final text or intent COMMITs to button events and final control COMMITs to the pointer report (Report 3), with `ttl_s`. The bridge is lossy (no distributions, no score semantics); it SHOULD log the NTS events next to the HID output. HID has no risk classes or confirmation, so the bridge applies INT-S4 and INT-T5 before it sends a report. |
| ROS `geometry_msgs/TwistStamped` | Velocity with a frame id, no uncertainty policy. Comparable to `control`. |
| IEC 62304, ISO 14971, IEC 60601-1 | Risk-management and safety processes, not data formats. |

Rule: NTS does not create a rival format where one exists. It bridges.
