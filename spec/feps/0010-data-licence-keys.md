# FEP-0010: Data licence keys in the stream and in trust decisions

| | |
|---|---|
| **FEP** | 0010 |
| **Title** | `data.licence` and `data.research_only` in `meta`; `research_only` in `trust_decision.input` |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft (folded into [NTS 1.0 RC4](../nts-1.0-rc4.md) as amendment 6 of 2026-11-17: sections 1.6, 3.4 (MET-12), 6.1.1, 6.2 (TD-15), 9.3, 9.5, C.1; reference implementation and vectors in Python, TypeScript and Rust) |
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
3. **Validators check types only.** Options: (a) types only; (b) also an advisory check that `data.research_only` agrees with `data.licence` (needs an SPDX NC rule in three SDKs). Taken: (a) now; (b) is open question LIC-2.

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

## Privacy and leakage
No personal data. A licence id is public information about a dataset. `data.licence` MUST NOT hold a consent text or a person's name; own consented data uses `LicenseRef-fidetype-consented` and the separate key `consent.ref` (an opaque reference).

## Open questions
- **LIC-1.** Should a stream also name its dataset (`data.source` with a DOI or URL)? The adapters know it (`fidetype.replay`), but a URL in every header can point to a person-level record in some datasets.
- **LIC-2.** Should the validators warn when `data.research_only = false` but `data.licence` is a `CC-BY-NC-*` id (an advisory check like NTS-MODALITY-MATCH)? Cheap, but it puts an SPDX rule into three SDKs.
- **LIC-3.** Should the collector refuse (by option) to pass research-only decisions to a product exporter (for example the `os_text` backend in a product build)? This is a policy, not a format rule; it belongs in FEP-0006.
