# FEP-0010: Data licence keys in the stream and in trust decisions

| | |
|---|---|
| **FEP** | 0010 |
| **Title** | `data.licence` and `data.research_only` in `meta`; `research_only` in `trust_decision.input` |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft (folded into [NTS 1.0 RC4](../nts-1.0-rc4.md) as amendment 6 of 2026-11-17: sections 1.6, 3.4 (MET-12), 6.1.1, 6.2 (TD-15), 9.3, 9.5, C.1; reference implementation and vectors in Python, TypeScript and Rust). 2026-11-18: LIC-2 answered by RC4 amendment 7 (advisory check `NTS-LICENCE-MATCH`, roadmap P5-19); LIC-3 answered by FEP-0006 section 4 rule 6 (exporter option `refuse_research_only`, roadmap P5-18) |
| **Type** | Spec change (additive) |
| **Affects** | NTS 1.0 RC4 sections 3.4, 6.1.1, 6.2; the registry [`spec/semconv/`](../semconv/registry.md) |
| **Created** | 2026-11-17 |
| **Discussion** | Gap 47 (roadmap P5-13), found by P5-03: licence flags lived in the provenance ledger only |

## Summary
Three optional keys. Two are stream `meta` keys in the reserved namespace `data`. One is a recommended audit key of `trust_decision.input`.

| Key | Container | Type | Meaning |
|---|---|---|---|
| `data.licence` | `header.meta` | non-empty string | The licence of the recorded data: an SPDX licence id (`CC0-1.0`, `CC-BY-4.0`, `CC-BY-NC-4.0`, ...) or a `LicenseRef-` id |
| `data.research_only` | `header.meta` | boolean | `true`: the stream may be used for research only (its data licence, or the licence of another input that made it, does not allow commercial use or is unknown) |
| `research_only` | `trust_decision.input` | boolean | `true`: the decision depends on research-only data (from the input stream or from the layer's provenance lineage) |

New rule **MET-12**: a producer that knows the data licence SHOULD write both meta keys; `data.research_only` MUST be `true` for a licence without commercial use. New rule **TD-15**: a trust layer that knows the licence of its input SHOULD write `input.research_only`. All three keys are Development.

## Motivation
- The project licence rule says: non-commercial (NC) data is for research only, and product weights come only from CC0 or own consented data ([licence rule](../../wiki/questions/project-plan.md#licence-rule)). P5-03 put licence flags into the provenance ledger (`source`, `artifact`, `context` and `decision` entries).
- A consumer that reads only the stream or only the decision log could not see the flags. The SpanishBCBL adapter wrote the custom key `spanishbcbl.licence`, which no tool can read in general. An emitted `trust_decision` had no `research_only`.
- With the keys, a product pipeline can refuse research-only streams and decisions without access to the ledger.

## Evidence (what each producer can fill)

| Producer | Dataset licence (source) | `data.licence` | `data.research_only` |
|---|---|---|---|
| `fidetype.adapters.emg2qwerty` (Meta emg2qwerty) | CC BY-NC-SA 4.0 (repository `LICENSE`) | `CC-BY-NC-SA-4.0` | `true` |
| `fidetype.adapters.kt_semg` (KT forearm sleeves, Harvard Dataverse) | CC BY 4.0 | `CC-BY-4.0` | `false` |
| `fidetype.adapters.toronto_semg` (Toronto sEMG, Borealis) | CC BY 4.0 | `CC-BY-4.0` | `false` |
| `fidetype.adapters.willett_handwriting` (Willett 2021, Dryad) | CC0 1.0 | `CC0-1.0` | `false` |
| `fidetype.adapters.spanishbcbl_meg` (SpanishBCBL MEG, Hugging Face) | CC BY-NC 4.0 | `CC-BY-NC-4.0` | `true` |
| `fidetype.adapters.b2t25` (Brain-to-Text '25, Dryad) | CC0 1.0 | `CC0-1.0` | `false` |
| Benchmark tracks (`fidetype.benchmark.tracks`, 7 tracks) | per track (`licence`, `research_only`) | `fidetype.trust.licence.track_meta(track)` | from the track; checked against the licence by `track_licence` |

The adapters take the keys from `fidetype.trust.licence.licence_meta(LICENCE)`, so the SPDX form and the research-only rule come from one place. A test (`tests/test_licence_keys.py`) checks that each adapter's keys equal the keys of its benchmark track.

Rejected candidates:
- `data.attribution` (the text a CC BY licence asks for). The track definitions hold it, but no adapter needs it in each stream, and it is free text (a privacy and size risk in every header). The ledger `source` entry keeps it.
- `data.commercial_ok` and `data.product_ok`. They follow from `data.licence` and `data.research_only` and from a product policy that is not part of the stream (the `project` and `commercial` policies of `fidetype.trust.licence`). Two keys that can disagree are worse than one.
- A licence key per input (decoder weights, LM corpus). The ledger holds the full lineage; the stream carries the combined flag only.

## Proposal
Normative text: RC4 sections 3.4 (MET-12, two table rows), 6.1.1 (one row), 6.2 (TD-15), and the registry files `spec/semconv/attributes/data.yaml` and `trust-decision-input.yaml`.

- **Types.** `data.licence` uses the validator `non_empty_string` (MET-7), `data.research_only` the validator `boolean`. No new validator.
- **Value of `data.licence`.** An SPDX licence id (the short id, not a full expression) or a `LicenseRef-` id. The examples in the registry are not a closed list: a consumer MUST NOT read an unknown id as permissive. The validators do not check the SPDX list (it changes; the check would need a copy of it in three SDKs).
- **MET-12 (content).** `data.research_only` MUST be `true` when the licence does not allow commercial use. It MAY be `true` for other reasons (an NC decoder on CC BY data). A consumer that finds only `data.licence` reads its flags; with only `data.research_only = false` and no licence it reads "unknown licence, research only" (the claim cannot be checked).
- **TD-15.** `input.research_only` is `true` if the stream says research only or the layer's lineage (decoder, LM, calibration data in the provenance ledger) is research only. Without either it is absent. It is audit data (TD-13): it never changes a decision.
- **Ledger.** A stream that declares one of the meta keys becomes a `source` entry of the provenance ledger (`details.from = "stream meta"`; `research_only: true` in the source when the stream says so). Its context lists it in `stream_sources`, and the context and decision flags combine it with the artifact lineage. `verify` recomputes the combined flags.

### Decisions taken in this FEP (with the options)
1. **Spelling `licence`, not `license`.** Options: (a) `data.licence` (the roadmap text, the project's British spelling in `fidetype.trust.licence`, the ledger key `licence`); (b) `data.license` (SPDX and OpenTelemetry use US spelling). Taken: (a), so that the stream, the ledger and the code use one word. A later version can add an alias only through a FEP; no producer writes (b).
2. **Where `research_only` goes in a decision.** Options: (a) a key of `input` (6.1.1), audit data under TD-13; (b) a new top-level field of `trust_decision` (a schema, proto and three-SDK type change); (c) a new container `licence`. Taken: (a). The flag describes the input of the decision, TD-13 already says how a consumer treats audit keys, and the roadmap asks for "an audit key, TD-13". No schema or proto change.
3. **Validators check types only.** Options: (a) types only; (b) also an advisory check that `data.research_only` agrees with `data.licence` (needs an SPDX NC rule in three SDKs). Taken: (a) in amendment 6; (b) added by amendment 7 (LIC-2 below).
4. **The table of the advisory check (LIC-2, 2026-11-18).** Options: (a) a copy of the SPDX licence list in three SDKs; (b) a fixed rule: a Creative Commons id with the element `NC`, plus `LicenseRef-unknown`; (c) the full normalisation of `fidetype.trust.licence.normalise` (free forms like `"CC BY-NC 4.0"`) in three SDKs. Taken: (b), ASCII only and without case (SPDX ids match without case). It needs no list that changes, it is one pattern that three SDKs can match alike (`fidetype.trust.licence.no_commercial_id`, TypeScript `noCommercialId`, Rust `checks::no_commercial_id`), and it catches the cases that P5-03 found in real data (the CC BY-NC datasets). Any other id gives no warning; the check never reads an unknown id as permissive. A warning, never a reject: MET-12 is content, and a wrong warning must not block a stream.
5. **Collector policy (LIC-3, 2026-11-18).** Options: (a) an exporter option that drops research-only decisions; (b) the same, but a COMMIT becomes an OFFER (the user still sees the text); (c) a processor before the exporters; (d) refuse at configuration time to connect a research-only source to a product exporter. Taken: (a), `refuse_research_only = true` on any exporter (FEP-0006 section 4 rule 6). Reason: (b) changes an item (FEP-0006 rule 1) and still shows research-only text in a product; (c) would also remove the decisions from the audit log of the same pipeline; (d) cannot know the licence before the header arrives. A decision without `input.research_only` has an **unknown** licence and is dropped by default (`unknown_licence = "refuse"`; `"pass"` exports it), because the project licence rule reads an unknown licence as research only. Default without the option: unchanged.
6. **Input-event exporters (P5-22, 2026-11-18).** Question: can an exporter of input events (a `jsonl` or `stdout` copy of the stream, for example into a product data store) refuse a research-only stream? Options: (a) no, input events always pass (P5-18); (b) yes, per stream by its header keys, the whole stream (header and all its events); (c) per event, by a key on each event; (d) refuse at configuration time. Taken: (b), the same option `refuse_research_only` and the same `unknown_licence` rule (FEP-0006 section 4 rule 6). Reason: the header is the one place where a stream declares `data.licence` and `data.research_only` (MET-12), and NTS sends it first, so the exporter knows the verdict before the first frame. The stream flags are read as for TD-15 (`stream_licence`), so a stream and the decisions made from it get the same verdict. (a) leaves a research-only copy in a product store; (c) needs a new key on every frame; (d) cannot know the licence before the header (decision 5). A partial stream (a header without its frames, or frames without a header) is never written: the whole stream goes or none of it. An event without a header before it has an unknown licence.

## Compatibility
- Additive. Every earlier vector keeps its verdict.
- A stream that wrote a custom key `data.licence` or `data.research_only` with a wrong type is now refused (NTS-META-TYPES). MET-3 already said SHOULD NOT for a reserved namespace, and no reference producer wrote one.
- The SpanishBCBL adapter no longer writes the custom key `spanishbcbl.licence`. A reader of old streams can still read it as a custom key.
- Ledgers: a context that comes from a stream with the keys now has `stream_sources` and licence flags; its content id changes. Old ledgers verify as before (no `stream_sources`).

## Reference implementation
- Python `fidetype.conformance.checks.DEFINED_KEYS`, TypeScript `DEFINED_KEYS` (`sdk/typescript/src/checks.ts`), Rust `DEFINED_KEYS` (`sdk/rust/src/checks.rs`): 2 new keys.
- `fidetype.trust.licence`: `licence_meta`, `track_meta`, `stream_licence`, `restrict`.
- Producers: the six adapters above; `track_meta` for the benchmark tracks.
- Ledger: `ProvenanceLedger.record_context` reads the stream keys into a `source` entry; `record_source(research_only=)`; `verify` and `LedgerView.lineage` know `stream_sources`.
- Trust layers: `StreamingTrustLayer` (stream keys and ledger lineage), `IntentTrustLayer`, `ControlTrustLayer` and the collector `guard` processor (stream keys) write `input.research_only`.
- Vectors (`v0.1`): V98 (accept: both keys), V99 (reject: `data.licence` is `""`), V100 (reject, NPZ: `data.research_only` is `"yes"`). Python = TypeScript = Rust.
- `tools/semconv/semconv.py --check` compares the new keys with the spec tables, the three SDK tables and the accept vectors.
- Amendment 7 (P5-19): the advisory check `NTS-LICENCE-MATCH` in the three validators; vectors V101, V102, V103 (accept with the warning), V104 (accept, no warning); `tests/test_licence_match.py`.
- P5-18: `fidetype.collector.exporters.LicenceGate` and the exporter options `refuse_research_only`, `unknown_licence`; `tests/test_research_only_policy.py`.
- P5-22: the same gate per stream on input-event exporters (`LicenceGate.input_events`, counters `*_streams_refused`, `*_events_refused`); `tests/test_input_event_licence_gate.py`.

## Privacy and leakage
No personal data. A licence id is public information about a dataset. `data.licence` MUST NOT hold a consent text or a person's name; own consented data uses `LicenseRef-fidetype-consented` and the separate key `consent.ref` (an opaque reference).

## Open questions
- **LIC-1.** Should a stream also name its dataset (`data.source` with a DOI or URL)? The adapters know it (`fidetype.replay`), but a URL in every header can point to a person-level record in some datasets.
- ~~**LIC-2.**~~ **Answered 2026-11-18 (roadmap P5-19, RC4 amendment 7):** yes. The advisory check `NTS-LICENCE-MATCH` warns when `data.research_only = false` and `data.licence` is a Creative Commons id with `NC` or `LicenseRef-unknown`, the same in Python, TypeScript and Rust (vectors V101 … V104). Decision 4 above.
- ~~**LIC-3.**~~ **Answered 2026-11-18 (roadmap P5-18, FEP-0006 section 4 rule 6):** yes, by option. `refuse_research_only = true` on an exporter drops decisions with `input.research_only = true` and, by default, decisions without the key (unknown licence), with counters and a log line. Test: a CC-BY-NC stream types nothing through an `os_text` exporter; a CC0 stream types as before (`tests/test_research_only_policy.py`). Decision 5 above. P5-22 (2026-11-18) extends it to input-event exporters, per stream by the header keys (decision 6).
