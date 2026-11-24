---
title: Long-term roadmap — Fidetype as a full neural input standard
type: question
tags: [planning, roadmap, north-star, frontier, write-side, affect, memory, standard, spec, sdk, collector, adapters, benchmark, conformance, governance, adoption, intent, cursor, benchmark-hub, value-first, toolkit, daily-use, aac-app, privacy, federated-learning, emg-hardware, foundation-model, multilingual, regulatory]
sources: [case-study-opentelemetry, case-study-langchain, case-study-sglang, neural-input-landscape-2026, brain2qwerty-code]
updated: 2026-11-24
---

# Long-term roadmap: Fidetype as a full neural input standard

> **North star changed (2026-11-15).** The project now aims at a new frontier: a BCI that reads language from any body signal, teaches itself from daily use, and provably never puts words in the user's mouth ([north star](north-star.md)). **[P15 Frontier](#p15-frontier-added-2026-11-15-leads) leads.** P1–P14 below stay as they are: no item moved, renumbered or removed. The standard work (spec, SDKs, collector) is now internal plumbing with a lower priority. **After the roadmap (added 2026-11-20):** [P17 daily use](#p17-daily-use-product-people-and-privacy-added-2026-11-20-after-the-roadmap) and [P18 reach](#p18-reach-hardware-models-languages-outputs-standards-added-2026-11-20-after-the-roadmap) start in 2028.
>
> **Later: [P16 write side](#p16-write-side-emotion-and-memory-exploration-added-2026-11-15-later)** (user idea, 2026-11-15): explore emotion and memory stimulation. It starts after the P15 core work. Real stimulation is externally blocked.

**Question asked (2026-11-10):** The user decided that Fidetype aims for **full standardisation at OpenTelemetry scale**, and that we build all of it ourselves. Claude subagents write the code and the docs. The user does the outward-facing actions. The current milestones M1–M7 (due 2026-11-15) are only **v0.1**. What comes after v0.1?

**Diagram:** `11-roadmap-standard` on [the diagram page](../diagrams/index.html#s11).

**Update (2026-11-11):** the user added two scope items at the end: [P12](#p12-beyond-text-intent-and-control-added-2026-11-11) (intent beyond text) and [P13](#p13-public-benchmark-hub-added-2026-11-11) (public benchmark hub). Priorities and the order of P1–P11 do not change.

**Update (2026-11-15):** the user added [P14](#p14-value-first-a-useful-toolkit-added-2026-11-15) (value first: pretrained decoders, a drop-in trust wrapper, live lab inputs, a safe-WPM metric, a visible demo, result write-ups, an example AAC integration). No existing item moves, changes its ID or changes its priority.

**Update (2026-11-16):** the user asked that known gaps are fixed later, not forgotten. 15 new items register the open gaps of 2026-11-16 at the end of their phases (P1-14, P1-15, P4-09, P5-08 … P5-11, P14-10, P15-13 … P15-19). Convention: new numbered ids that continue each phase; "follow-up of" names the item they extend. No existing item moved. List: [open gaps](open-gaps.md).

**Context:** [project plan](project-plan.md) (M0–M7 = v0.1), [open-source playbook](open-source-playbook.md) (stages 0–5), [architecture](architecture.md), [direction decision](direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level), [spec v0.1](../../spec/neuraltextstream-v0.1.md), [public datasets](public-datasets.md), [progress dashboard](../progress/index.html) (milestones P1–P11).

## Summary
- v0.1 (M0–M7) gives one spec draft, one Python package, one trust core, a first benchmark and first adapters.
- After v0.1, the roadmap has **13 phases (P1–P13)**. Most of them run in parallel.
- **P12 (beyond text: intent and control)** and **P13 (public benchmark hub)** were added on 2026-11-11 at the end of the order. They do not change priorities. Text entry stays first ([decision](direction-decision.md#scope-note-2026-11-11-intent-beyond-text-and-a-benchmark-hub)).
- **P14 (value first)** was added on 2026-11-15. It makes `fidetype` useful on its own (pretrained decoders, a trust wrapper, a demo), so that people have a reason to install it. It references existing items and changes none of them.
- **P15 (frontier)** was added on 2026-11-15 and **leads**: safe self-improving decoding (F1), faithful LLM decoding (F2) and a cross-body language model (F3) ([north star](north-star.md)). It changes no existing item.
- The critical path is: **benchmark (P6) + spec 1.0 RC (P1) → Python + C SDKs (P2) → replay adapters (P4) → collector (P3) → "three devices, one stream" demo (P8) → launch (P10)**. Papers are not on the critical path (see [publications](#publications-no-deadline)).
- The gap to an OpenTelemetry-scale project is **not the core**. It is the **SDKs, adapters and integrations** (see [scale reference](#scale-reference)).
- **Dataset replay** lets us test devices we do not own. Real hardware, outreach, partners, ethics, user studies, peer review and arXiv endorsement depend on outside people. They are **`externally_blocked`** or user-owned.

> **Our take:** We can build a complete, tested standard stack without outside help. We cannot make it *a standard* without outside adopters. So the order is: make it real and testable first (P1–P8), then ask people to use it (P10).

## Where v0.1 ends
| v0.1 item (M0–M7) | State on 2026-11-10 | Carried into |
|---|---|---|
| NeuralTextStream spec v0.1 (Development) | Published. Frame core implemented; other event kinds are sketches | P1 |
| `fidetype` Python package (about 11.5k lines on 2026-11-10; 38,500 lines on 2026-11-14) | Decoders, LM, trust core, eval harness, first adapter (B2T '25) | P2, P3, P5 |
| Trust core v0 | Runs on the simulator, real MEG and B2T '25 | P5 |
| Benchmark v0.1 (M5) | Harness exists; leaderboard not yet | P6 |
| Validator; conformance cases C1–C20 | Validator exists. 2026-11-11 (M5-10): [conformance suite](../concepts/conformance-suite.md) v0 (`fidetype.conformance`, 60 checks, levels core / trust-ready / provenance, 52 golden vectors in `spec/conformance/v0.1/`) | P7 |
| Adapters (M6) | B2T '25 replay in progress; LSL/BrainFlow not yet | P4 |
| OSS files, FEP template, GOVERNANCE.md | Done (commit 677ba0e) | P9 |
| Paper 1, Paper 2 | Paper 1 draft v5 + arXiv package done (2026-11-12); Paper 2 not written | PUB (no deadline) |

## Scale reference
| Project | Size | How we know |
|---|---|---|
| **Fidetype `src/` today** | **38,500** Python lines in 105 files (committed at bcabf04) + 12,808 lines in `tests/` | Counted 2026-11-14 |
| Fidetype `src/` (history) | about **11.5k** Python lines (11,532 on disk; 10,795 committed) + 3.4k test lines | Counted 2026-11-10 |
| Brain2Qwerty (Meta, `references/repos/brain2qwerty`) | about **5.6k** Python lines (5,555) | Counted 2026-11-10 |
| LangChain | **hundreds of thousands** of lines (rough, not measured) | Rough figure |
| OpenTelemetry (spec + collector + SDKs) | **millions** of lines across **about 10 or more** languages (rough, not measured) | Rough figure |

- Our core is already twice the size of Brain2Qwerty (2026-11-10; about 7 times on 2026-11-14). The core is not the gap.
- OpenTelemetry is large because of **one SDK per language**, a **collector with hundreds of components**, and **instrumentation for many libraries** ([OTel case study](../sources/case-study-opentelemetry.md)).
- Fidetype at spec 1.0 needs the same kind of breadth, but in a field of thousands of researchers, not millions of developers ([playbook, realistic expectations](open-source-playbook.md#realistic-expectations)).

**Our rough size target at spec 1.0** (our estimate, not a commitment):

| Part | Rough lines |
|---|---|
| Spec, schemas, semantic-convention registry, generated docs | 10–20k (mostly generated) |
| SDKs: Python, TypeScript, Rust, then C core, C#/Kotlin bindings | 30–60k |
| Collector (receivers, processors, exporters) | 15–30k |
| Adapters (devices, toolkits, dataset replay) | 15–30k |
| Trust layer (product grade) | 10–20k |
| Conformance kit, benchmark, website, examples | 10–20k |
| **Total** | **about 90–180k** |

> **Our take:** 90–180k lines is about 10× the current core. With agents writing the code, the limit is **review, testing and access to real devices**, not typing speed. Each phase below therefore has machine-checkable exit criteria.

## Phase overview
Effort is rough. **1 agent-day** = about 8 h of subagent work. "User" = hours of the user's own time. The calendar windows are our choice: the tracker schema needs `target_start` and `target_end` for each milestone. They assume the current pace (one developer, agents write the code). Items that depend on outside people have no date and never count as late.

| ID | Phase | Goal | Effort (agent-days / user) | Depends on | Window |
|---|---|---|---|---|---|
| **P1** | Spec to 1.0 | A complete, versioned, machine-readable spec | 25–40 / 15 h | v0.1 spec | 2026-11-16 → 2027-02-28 (RC); 1.0 Stable is ext. blocked |
| **P2** | Reference SDKs | Emit and read NTS from 6 languages | 40–70 / 10 h | P1 schema | 2026-12-01 → 2027-05-31 |
| **P3** | Collector | A vendor-neutral pipeline: receivers → processors → exporters | 30–50 / 8 h | P2 (Python, C) | 2027-01-04 → 2027-06-30 |
| **P4** | Adapters | Devices, toolkits and dataset replay → NTS | 30–60 / 10 h (+ hardware) | P1, P2 | 2026-11-16 → 2027-06-30 |
| **P5** | Trust layer, product grade | Personalised, guaranteed, private, on-device | 30–50 / 10 h | v0.1 trust core, P3 | 2026-12-01 → 2027-09-30 |
| **P6** | Benchmark + leaderboard | Public eWPM and error metrics across modalities | 15–25 / 8 h | M5, P4 replay | 2026-11-16 → 2027-01-31 |
| **P7** | Conformance + certification | Test kit and the "Fidetype-compatible" mark | 15–25 / 10 h | P1, P2 | 2027-02-01 → 2027-07-31 |
| **P8** | Docs, website, demo | Quickstarts and a three-device demo | 15–25 / 10 h | P2, P3, P4 | 2026-12-15 → 2027-04-30 |
| **P9** | Governance + community | Licences, process, a later neutral home | 5–10 / 20 h | — | 2026-11-16 → 2027-03-31 (code parts) |
| **P10** | Adoption | Users outside the project | 5–10 / 60+ h | P6, P8 (Paper 1 helps; not a gate) | 2027-01-15 → 2027-12-31 (mostly ext. blocked) |
| **P11** | Research track | Better decoders (papers: PUB) | ongoing | GPU, datasets | 2026-11-16 → 2027-12-31 |
| **P12** | Beyond text: intent and control | Output profiles for discrete intent, continuous control and speech; trust policies for actuation | 20–35 / 8 h | P1 1.0 RC, P2, P3, P5 | 2027-07-01 → 2027-12-31 |
| **P13** | Public benchmark hub | Extend the P6 leaderboard into a reproducible hub; later all intent | 10–20 / 6 h | P6, P4 replay, P12 (intent tracks) | 2027-07-01 → 2027-12-31 |
| **P14** | Value first: useful toolkit (added 2026-11-15) | Pretrained decoders, drop-in trust wrapper, live lab inputs, safe-WPM metric, demo, write-ups, AAC example | 25–40 / 6 h | M4-12, P4, P5, P6, P11-01 | 2026-11-16 → 2027-03-31 (user and hardware items ext. blocked) |
| **P15** | **Frontier (added 2026-11-15, leads)** | F1 safe self-improving BCI, F2 faithful LLM decoding + hallucination benchmark, F3 cross-body language model; first experiments E2, E3, E1 | 30–60 / 8 h | Trust layer (P5, P14-03), M4-12 / M4-13, T12 v2, P11-01, GPU queue | 2026-11-16 → 2027-06-30 (first round) |
| **P16** | Write side: emotion and memory (exploration; added 2026-11-15, later) | Literature, read-side affect decoding on public data, ethics, offline closed-loop design; real stimulation only with partners | 10–20 / 6 h | P15 core work, trust layer (P5, P14-03) | 2027-07-01 → 2027-12-31 (P16-05 ext. blocked) |

## P1. Spec to 1.0
**Goal:** NeuralTextStream 1.0. Every part has a stability level. A machine-readable schema is the source of truth. The prose spec and the docs are generated from it or checked against it.

**Status (2026-11-14): 1.0 RC1 DRAFT for public comment** ([`spec/nts-1.0-rc1.md`](../../spec/nts-1.0-rc1.md); summary: [NTS specification](../concepts/nts-spec.md)). It folds v0.1 and FEP-0001 … FEP-0005 into one document, with rule ids, a traceability table (Appendix C, gaps G-1 … G-11), the open-question resolutions (Appendix A), migration (Appendix B), security and privacy, versioning and registries. One rule is stricter in the validators of all three SDKs: TD-9, no blank final text COMMIT for `spec_version` 1.x decisions (vectors F41-F47).

**Update (2026-11-14): 1.0 RC2** ([`spec/nts-1.0-rc2.md`](../../spec/nts-1.0-rc2.md)) supersedes RC1 as the current draft. It adds TD-12 (no blank candidates) and closes gaps G-1 … G-4. Details: [NTS specification](../concepts/nts-spec.md).

| Task | State after RC1 | What is left |
|---|---|---|
| P1-01 data model | in progress | Provenance block, frame-level multi-head, lattices, embeddings: deferred to 1.1 (Appendix A); 1.0 headers not accepted by the validators yet (gap G-2) |
| P1-02 protobuf + generated JSON Schema | done (2026-11-15) | [`spec/proto/`](../../spec/proto/README.md) + generated `spec/schemas/nts-v1.schema.json`, CI drift and parity checks ([NTS protobuf schema](../concepts/nts-proto-schema.md)); open spec questions Q-1 … Q-8 for the next RC |
| P1-03 versioning, SDK matrix, FEP lifecycle and index | done (RC1 section 11, spec/README) | Outside review |
| P1-04 semconv YAML | done (registry v0 2026-11-15; modality keys 2026-11-16) | [`spec/semconv/`](../../spec/semconv/registry.md): 32 `meta` keys (24 of RC4 3.4 + 8 modality keys of [FEP-0009](../../spec/feps/0009-modality-semantic-conventions.md): `emg.*`, `meg.*`, `implant.*`, rule MET-11) + 19 recommended `trust_decision` keys, generated page, CI check `semconv` (spec tables, proto, schema, 3 SDK validators, vectors). Open: `eeg.*` and `fnirs.*` keys wait for a real producer (SC-9) |
| P1-05 bindings | in progress | Files, LSL, WebSocket in RC1; in-process API and gRPC not written |
| P1-06 generated docs + CI agreement check + tag RC | todo | RC1 is not tagged (draft) |
| P1-07 1.0 Stable | externally blocked | Two outside decoder groups |

### Deliverables
1. **Data model 1.0.** Streams (header + events), all event kinds (`frame`, `decision`, `hypothesis`, `pointer`, `signal_quality`), plus the open questions of [spec section 10](../../spec/neuraltextstream-v0.1.md#10-open-questions):
   - **Confidence:** `score_semantics` for every score; calibration metadata.
   - **Provenance:** a `provenance` block: decoder id and version, weights hash, training-data ids and licences, calibration id. It links to the ledger of P5.
   - **Timing:** `clock_domain`, the four timestamps of spec 3.8, and clock-domain mapping between devices.
   - **Segments:** word, sentence and trial boundaries (open question 5).
   - **Revisions:** frame and hypothesis revisions for causal decoders (open question 4).
   - **Multi-head output:** several vocabularies in one stream (open question 6).
2. **Versioning and compatibility rules.**
   - The spec follows semver. Stable parts do not break within a major version. Deprecated Stable parts stay at least 12 months (already in [spec 1.3](../../spec/neuraltextstream-v0.1.md#13-promise-after-stable)).
   - Protobuf rules: never reuse a field number; new fields are optional; unknown fields are kept and ignored.
   - The header carries `spec_version`. A consumer accepts all minor versions of its major version.
   - SDK versions are separate from the spec version. A published **compatibility matrix** maps SDK versions to spec versions.
3. **Change process.** FEPs already exist ([`spec/feps/`](../../spec/feps/), [GOVERNANCE.md](../../GOVERNANCE.md)). Add: FEP states (draft → accepted → implemented → final), a rule that each FEP needs a reference implementation and conformance cases, and a public FEP index.
4. **Semantic conventions per modality**, in a YAML registry (`spec/semconv/*.yaml`):

   | Modality | Example keys (to define) |
   |---|---|
   | All | `device.*`, `decoder.*`, `lm.*`, `session.*`, `subject.*`, `consent.ref`, `data.derived` (exist in v0.1) |
   | sEMG | `emg.placement` (wrist, forearm), `emg.band_count`, `emg.electrode_layout`, `emg.sample_rate_hz`, `gesture.*` vocabularies |
   | EEG | `eeg.montage` (10-20, 10-10), `eeg.reference`, `eeg.dry_electrodes`, `eeg.paradigm` (P300, SSVEP, MI, typing) |
   | MEG | `meg.system` (SQUID, OPM), `meg.sensor_type`, `meg.preprocessing` (tSSS, filters) |
   | fNIRS | `fnirs.wavelengths_nm`, `fnirs.channel_pairs`, `fnirs.hemodynamic_delay_s` (a lower bound on latency) |
   | ECoG / intracortical | `implant.array_type`, `implant.site`, `implant.feature` (threshold crossings, spike-band power), `implant.bin_s` |

5. **Wire formats** (decision below).
6. **Transports** (decision below).
7. **Source of truth:** `spec/proto/neuraltextstream/v1/*.proto` for the data model, `spec/semconv/*.yaml` for the conventions. A generated JSON Schema (`spec/schema/nts-v1.schema.json`) validates the JSON Lines form.
8. **Generated docs:** field tables, convention tables and language constants are generated from the proto and YAML files. CI fails if the prose spec and the schema disagree.

### Decision: wire formats
| Form | Use | Choice |
|---|---|---|
| **Protocol Buffers (proto3)** | Canonical schema and binary wire form; gRPC; embedded devices | **Primary.** |
| JSON Lines (proto3 JSON mapping) | Debugging, browsers, logs; the v0.1 form | **Kept**, defined by the proto JSON mapping + JSON Schema |
| Apache Arrow IPC / Parquet | Offline files and benchmark submissions with large [T, V] arrays | **Secondary**, for bulk and analytics |
| NPZ | v0.1 files | **Kept read-only** as a legacy form |
| FlatBuffers | Zero-copy binary | **Not chosen** |

Reasons:
- **Protobuf:** OpenTelemetry uses it for OTLP ([OTel case study](../sources/case-study-opentelemetry.md#design)), so the pattern is proven for a vendor-neutral standard. It has code generators for all our SDK languages (C via nanopb for microcontrollers, C++, Rust, TypeScript, C#, Kotlin). It has clear schema-evolution rules. gRPC uses it natively.
- **Arrow:** dense `log_probs` [T, V] are columnar data. Arrow maps them to NumPy and pandas without a copy, and Parquet compresses them for the leaderboard.
- **Not FlatBuffers:** zero-copy reads matter less than ecosystem support at our frame rates (tens of frames per second). Its gRPC and JSON support is weaker. We can add it later through a FEP if a device needs it.

### Decision: transports
| Transport | For | Status target |
|---|---|---|
| In-process API | A decoder and a trust layer in one process (SDK call) | Stable in 1.0 |
| Files (Arrow/Parquet, JSON Lines, NPZ read) | Datasets, benchmarks, replay | Stable in 1.0 |
| **LSL** | Labs; real-time alongside raw signals (spec 6.4) | Stable in 1.0 |
| **WebSocket** (JSON or protobuf frames) | Browsers, web AAC apps | Stable in 1.0 |
| **gRPC** (protobuf streaming) | Services, the collector (P3), OTLP-style export | Stable in 1.0 |
| Shared memory / BLE GATT profile | Low-latency local use; wearables | Development (FEP later) |

### Exit criteria
- `.proto`, JSON Schema and semconv YAML are in `spec/`. Docs are generated. CI checks that they agree.
- All event kinds are implemented in the Python SDK and pass the conformance kit (P7).
- A **1.0 release candidate** is tagged.
- **1.0 Stable** needs outside review by at least 2 decoder groups ([playbook stage 3](open-source-playbook.md#stage-3-standard)): **externally blocked**.

**Effort:** 25–40 agent-days; about 15 h of user review. **Depends on:** v0.1 spec; lessons from P4 adapters and P6 benchmark (real producers find spec gaps).

### Open-gap items (added 2026-11-16)
The user asked that known gaps are fixed later, not forgotten. These items come from agent reports of 2026-11-16. Full list: [open gaps](open-gaps.md). No existing item moved.

#### P1-14 Gap G-13 part (a): apply option A2 (dense + sparse in one frame, sparse keys type-checked)
- **Gap:** 5 of the [open-gap list](open-gaps.md). Follow-up of P1-13, P1-04.
- **Status:** `done`. Commit `18713f9` (2026-11-16): RC4 amendment 2 applies A2 (FRM-2); three validators type-check the sparse keys; vectors V88 … V92; parity 341/341; G-13 closed.
- **Depends on:** P1-13 (RC4), GEN-11.
- **Source:** Commit `de2f242` (P1-04 done: G-13 part b closed, part a open with options A1-A3, A2 recommended).
- **Done when:** The next spec draft applies option A2 of RC4 Appendix C.2: a frame may carry dense and sparse values together, and the sparse keys are type-checked (in line with GEN-11). The Python, TypeScript and Rust validators, the proto / JSON Schema and new conformance vectors agree (parity check passes), and G-13 is marked closed in the traceability table.

#### P1-15 SC-9: `eeg.*` and `fnirs.*` semconv keys from a real producer
- **Gap:** 7 of the [open-gap list](open-gaps.md). Follow-up of P1-04.
- **Status:** `externally_blocked`.
- **Depends on:** An EEG or fNIRS adapter (P4) or dataset that emits the keys.
- **Source:** Commit `de2f242` (FEP-0009: `eeg` and `fnirs` stay planned, SC-9).
- **Done when:** A FEP defines `eeg.*` and / or `fnirs.*` keys from the evidence of a real producer (a public dataset adapter or a device adapter that fills them). The registry, the three SDK validators, the vectors and the `semconv` CI check include them. Externally blocked until such a dataset or adapter exists.

#### P1-16 MET-11: traceability row in Appendix C.1 and an advisory modality-match check
- **Gap:** 20 of the [open-gap list](open-gaps.md) (closed 2026-11-17). Follow-up of P1-04, P7-01.
- **Status:** `done` (2026-11-17, with P7-02, commit `ce7e085`). RC4 amendment 3: C.1 row for MET-11; advisory check `NTS-MODALITY-MATCH` in Python, TypeScript and Rust (same warning); vectors V93, V94, V96 (accept with the warning), V95 (accept, no warning), kit K32; the v0.1 summaries return `warnings`, so the three runners compare the warning itself; `KNOWN_UNTRACED` is empty; `rule-map.json` rebuilt.
- **Depends on:** P1-04 (FEP-0009, RC4 amendment 1), P7-01 (`rule-map.json`, test `test_every_defined_rule_has_a_traceability_row`).
- **Source:** P7-01 (2026-11-17): `nts-conform` maps checks to rule ids from RC4 Appendix C.1. Of the 267 rule ids that the RC4 text defines, only MET-11 (amendment 1) has no C.1 row. The spec text says that the validators check the types of the modality keys but not the modality match ("a producer SHOULD NOT write the keys of another modality").
- **Done when:** The next spec draft (or an editorial amendment of RC4) adds a C.1 row for MET-11 (checks, vectors, status). The Python, TypeScript and Rust validators have an advisory check (a warning, never a level block) for a modality key that does not match `device.modality`, with accept-with-warning vectors in all three SDKs (parity passes). `KNOWN_UNTRACED` in `tests/test_nts_conform.py` is empty and `spec/conformance/kit/rule-map.json` is rebuilt (`nts-conform rules --write`).

## P2. Reference SDKs
**Goal:** any decoder or app can emit and read NTS in its own language, with the same behaviour everywhere.

**Status (2026-11-21):** all three SDKs are **published as 0.1.0**: PyPI `fidetype`, npm `@fidetype/sdk`, crates.io `fidetype` (first public release; [P2-08](#p2-08-publishing-prep-for-the-first-release) has the details). The exit criterion "published to its registry with a 0.x version" is met for these three SDKs.

**Status (2026-11-14):** three SDKs exist and give the same verdicts: Python `fidetype` ([Python SDK](../concepts/python-sdk.md)), TypeScript `@fidetype/sdk` ([TypeScript SDK](../concepts/typescript-sdk.md)) and Rust `fidetype` ([Rust SDK](../concepts/rust-sdk.md)). All three are **ready to publish, not published** (P2-06 code part): complete registry metadata, one version source each, changelogs, `twine check` / `npm pack` / `cargo publish --dry-run` clean, CI job `packaging` (and `rust-msrv`) on every push. All three names were free on 2026-11-14. The release process, semver policy and SDK-to-spec version rules are in [docs/RELEASING.md](../../docs/RELEASING.md); the manual-only release workflow (trusted publishing) is `.github/workflows/release.yml` (moved from `docs/` on 2026-11-18); the step-by-step guide for the first release is [docs/publishing-checklist.md](../../docs/publishing-checklist.md) (P2-08). Publishing waits for the user (P2-07: accounts, trusted publishers). Not started: C core, C#, Kotlin, WASM. The package names differ from the table below (`@fidetype/sdk`, crate `fidetype`).

> **Decision (2026-11-14):** The NTS 1.0 SDKs are **Python, TypeScript and Rust**. The C core (`libnts`) moves to after 1.0. It is still planned, for embedded devices and FFI use. Reason: the three SDKs exist, pass the same 283 conformance vectors and are ready to publish. C is not started. Earlier plan (replaced): C core at priority 2 and the gate "Spec 1.0 RC + Python/C 1.0". Diagram `11-roadmap-standard` ([diagrams](../diagrams/index.html)) now shows the gate "Spec 1.0 RC + Python/TS/Rust 1.0".

### Deliverables
| SDK | Role | Package | Priority |
|---|---|---|---|
| **Python** (`fidetype`) | First-class. Research, decoders, trust layer, benchmark | PyPI | 1 |
| **TypeScript/JS** (`@fidetype/nts`) | Web apps, AAC web apps, WebSocket client, browser demo | npm | 1 |
| **Rust** (`nts`) | Safe native core; collector components; WASM for the browser | crates.io | 1 |
| **C core** (`libnts`, C11) + C++ header wrapper | Devices, firmware, toolkit plugins (BCI2000, OpenViBE), FFI core for other bindings. After 1.0 (decision 2026-11-14) | vcpkg, Conan; nanopb for MCUs | 2 |
| **C#** | Windows input (Text Services Framework), Unity | NuGet | 4 |
| **Kotlin** | Android input (IME), BLE devices | Maven Central | 4 |

- One **shared conformance suite** (P7) runs in the CI of every SDK.
- Same API shape in each language: `StreamWriter`, `StreamReader`, `validate()`, event types, semconv constants (generated).
- C# and Kotlin may wrap the C core or Rust (choose by a small FEP).

### Exit criteria
- Each SDK passes 100 % of the conformance kit in CI on Linux, Windows and macOS.
- Each SDK is published to its registry with a 0.x version and a compatibility-matrix entry.
- Python, TypeScript and Rust reach **1.0** with spec 1.0 RC (decision 2026-11-14; before: Python and C). The C core follows after 1.0.

**Effort:** 40–70 agent-days (about 6–12 per language). User: registry accounts and publish tokens (**user-owned**). **Depends on:** P1 schema (generated code).

#### P2-08 Publishing prep for the first release
- **Status:** `done` (2026-11-18). Publishing itself waits for the user (P2-07, M7-09).
- **Release done (2026-11-21, about 21:00):** first public release 0.1.0 is complete (checklist step I-4). P2-07, M7-09 and M7-08 are `done`. PyPI [fidetype](https://pypi.org/project/fidetype/) (trusted publishing, provenance), npm [@fidetype/sdk](https://www.npmjs.com/package/@fidetype/sdk) (provenance), crates.io [fidetype](https://crates.io/crates/fidetype) ([docs.rs](https://docs.rs/fidetype/0.1.0)). Site [zhangzibo.github.io/fidetype](https://zhangzibo.github.io/fidetype/) deploys on every push to `main` (user decision, commit `f64b65a`). GitHub releases py-v0.1.0 (Latest), ts-v0.1.0, rs-v0.1.0. Next release: the npm and crates.io trusted publishers are not set, and the one-time tokens expire on 2026-11-28 ([RELEASING.md](../../docs/RELEASING.md) section 3.1).
- **Release progress (2026-11-21):** the user chose "all recommended" for decisions D1-D9 (D6 had no recommendation, so it stays as is: the dashboard is included). Release commit `6579534` (0.1.0 for Python, TypeScript and Rust; CI 31 / 31 green). Tags `py-v0.1.0`, `ts-v0.1.0` and `rs-v0.1.0` on `6579534` were pushed at the user's request. P2-07 and M7-09 are in progress: the uploads (accounts, PyPI, npm, crates.io, Pages, GitHub releases) are the user's steps.
- **Result:** dry runs of the three packages pass (`twine check --strict`, `npm publish --dry-run`, `cargo publish --dry-run --locked`); a clean install of the wheel runs `fidetype conformance --profile fep-0001` (66/66). The names `fidetype` (PyPI, crates.io) and `@fidetype/sdk` (npm) were free on 2026-11-18. Author `Zibo Zhang` in all manifests and `CITATION.cff`; crate `homepage`; SDK READMEs with absolute links (npm and crates.io pages). The release workflow is now `.github/workflows/release.yml` (manual trigger only). New manual-only `.github/workflows/pages.yml` and `tools/site/build.js` (assembles `_site/` from the existing pages and checks local links). Step-by-step guide with time per step and the user decisions: [docs/publishing-checklist.md](../../docs/publishing-checklist.md).

#### P2-09 CI matrix: Python 3.13+ and Windows and macOS for the three SDKs
- **Gap:** 60 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P2-08, closed 2026-11-18). Follow-up of P2-08.
- **Status:** `done` (2026-11-18, green run 44369685042).
- **Result:** `.github/workflows/tests.yml`: full pytest suite on Linux 3.12 / 3.13 / 3.14, Windows 3.12 / 3.13, macOS 3.13 (inside `conformance-os`); job `conformance-os` (Windows, macOS): Python wheel smoke test + `fidetype conformance` + `nts-conform kit --require-level trust-ready`, TypeScript `npm run ci`, Rust `cargo test` + `fidetype-rs conformance` (vectors and kit). Job `all-green` fails when any job fails. Classifiers 3.12-3.14. Platform fixes: `.gitattributes` keeps the live model assets LF (pinned SHA-256); NaN-aware GuardScore comparison in tests (Python 3.13 dataclass `==`); `FIDETYPE_LATENCY_TOLERANCE` 4 on macOS for wall-clock test bounds. Release and pages workflows stay manual (`workflow_dispatch` only). Open: the branch rule that requires `all-green` (P2-11, owner) and Python 3.15 (P2-10).
- **Depends on:** P2-08 (done).
- **Source:** P2-08: CI runs the Python tests on Python 3.12 and Linux only. `requires-python = ">=3.12"` lets pip install the package on 3.13 and 3.14 without a test. The P2 exit criteria ask for the conformance kit on Linux, Windows and macOS.
- **Done when:** CI runs the Python tests on 3.12, 3.13 and 3.14 (Linux) and the conformance suites of the three SDKs on Windows and macOS; the classifiers list each tested Python version; a red platform blocks the merge.

#### P2-10 Python 3.15 in the CI matrix
- **Gap:** 64 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P2-09). Follow-up of P2-09.
- **Status:** `todo`.
- **Depends on:** h5py wheels for CPython 3.15 (outside the project).
- **Source:** P2-09: Python 3.15.2 is out. h5py 3.16.0 (dev extra `[emg2qwerty]`) has no cp315 wheel in `uv.lock`; the other locked packages have one or are pure Python.
- **Done when:** the `pytest` job runs on Linux with Python 3.15 (green), and the classifiers list 3.15; or a note says which package still blocks it.

#### P2-11 Required status check on main
- **Gap:** 65 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P2-09). Follow-up of P2-09.
- **Status:** `done` (2026-11-22, user decision "all recommended"; set with `gh api` by an agent): ruleset id 27878244 "main: require CI (P2-11)" (enforcement `active`, target the default branch `main`), rule `required_status_checks` with the contexts `all-green`, `tutorials (ubuntu-latest, py3.12)` and `tutorials (windows-latest, py3.12)` (integration GitHub Actions, id 15368), strict policy off; bypass actor = repository role Admin (id 5), mode `always`, so the owner's (and the agents') direct pushes to `main` still work (git reports "Bypassed rule violations"); no review rule; no classic branch protection; no other setting changed. Decision for direct pushes: they stay allowed for the owner through the admin bypass; pull requests need the three checks green before merge. Gap 65 closed.
- **Depends on:** the repository owner (GitHub settings).
- **Source:** P2-09: the `all-green` job of `tests.yml` fails when any job fails, but `main` has no branch rule (`gh api .../branches/main/protection`: 404), so a red platform does not block a merge.
- **Done when:** a ruleset on `main` requires the `all-green` check for pull requests, and the decision for direct pushes (agents push to `main`) is written down.

#### P2-12 iOS (Swift) binding and a mobile build check
- **Gap:** 113 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P2-05.
- **Status:** `todo`.
- **Depends on:** P2-02 (C core) or a C ABI on the Rust SDK (choose by a small FEP, as P2 says for C# and Kotlin); P2-05 (Kotlin, Android).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" The Python, TypeScript and Rust SDKs exist and give the same verdicts (not published). P2-05 plans Kotlin (Android IME) and C# (Windows TSF). No item plans iOS. Per-language API reference docs are already planned (P8-05, [docs site plan](docs-site-plan.md) task T11: autodoc, TypeDoc, rustdoc); this item does not repeat them.
- **Done when:** A Swift package reads and validates NTS on iOS through the chosen core and passes the conformance vectors in CI (macOS runner, iOS simulator). An Android build of the same core runs the vectors in CI (with P2-05). The compatibility matrix lists both.

#### P2-13 CI latency-budget tests flake on shared runners
- **Gap:** 124 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a CI failure). Follow-up of P2-09.
- **Status:** `done` (2026-11-21). Gap 124 closed: 20 consecutive green `tests` runs since the change (44915291894 to 44928984469, `d3511df`); no run in the streak had a failed attempt 1 and no collector gate failed. Progress before (commit `4f74ca2`): CI gate mode in `src/fidetype/collector/latency.py`: strict locally; on CI (`GITHUB_ACTIONS` / `CI`) the median is strict in every run and the p95 is the best of up to 3 fresh runs, only after a tail-only failure (`FIDETYPE_LATENCY_GATE` overrides). The gate report names the tail stage (receive or pipeline). Docs: docs/collector.md "Gate modes (P2-13)". Cause evidence: run 44913077810 attempt 1, receive p95 52.8 ms (max 117.2 ms) vs pipeline p95 1.27 ms, so a runner stall, not our code. Green `tests` runs since the change: 4 of 20 needed (44915291894, 44915895663, 44915904168, 44919622175).
- **Depends on:** P2-09 (done: CI matrix; `FIDETYPE_LATENCY_TOLERANCE` is 4 on macOS only).
- **Source:** CI run 44673291448 (2026-11-20 UTC, commit `8180a30`) failed. The test `tests/test_collector_pipeline.py` measured the emg-key WebSocket latency at p95 320 ms. The budget is 50 ms. The runner was windows-latest with Python 3.12. The rerun passed. Wall-clock budget checks on shared CI runners depend on the runner load, not only on our code.
- **Done when:** The wall-clock budget assertions in CI are either marked as performance tests that run only under the isolation runner or locally, or use a CI-specific tolerance with the strict budget checked in a dedicated performance job. The flake does not recur in 20 consecutive CI runs.

#### P2-14 Windows pytest CI job within its job timeout
- **Gap:** 154 of the [open-gap list](open-gaps.md) (added 2026-11-21 from CI runs). Follow-up of P2-09.
- **Status:** `done` (2026-11-21; commits `d0f0d34`, `2af928f`). The pytest jobs are sharded by whole test files with measured weights (`tests/conftest.py` `--shard K/N` and `--file-durations`; `tests/shard_weights.json`; `tests/test_shard_split.py`): 3 shards per Windows Python, 2 per ubuntu Python. `timeout-minutes` stays 30; coverage unchanged. 13 consecutive green `tests` runs (need: 10): 44889116085, 44889286346, 44892071579, 44892213002, 44892707275, 44894980699, 44895398281, 44895851514, 44896306731, 44896959230, 44897313435, 44897568907, 44906980131. Slowest pytest job per run in the last 8 runs: 12.5, 12.9, 12.4, 11.7, 12.5, 11.8, 12.3, 11.4 min (first 5 runs: slowest 12.3 min).
- **Maintenance:** refresh `tests/shard_weights.json` from the `json:` line of `--file-durations` when a shard goes above about 20 min.
- **Follow-up:** gap 156 = [P2-15](#p2-15-faster-slow-test-fixtures-hybrid_setup-and-streaming-calibration) (faster slow fixtures, low priority).
- **Depends on:** P2-09 (done: CI matrix). Not the same issue as gap 124 = [P2-13](#p2-13-ci-latency-budget-tests-flake-on-shared-runners): P2-13 is a latency-assertion flake; this item is the total job time.
- **Source:** CI runs 44881145511 (`96cec56`), 44882224116 (`76747e8`), 44882979465 (`dcc344b`) and 44883759336 (`534feae`), 2026-11-21 UTC. The job `pytest (windows-latest, py3.12)` stopped at the 30-min `timeout-minutes` of `.github/workflows/tests.yml` (status cancelled). The tests passed until the stop. The `all-green` check failed. Run 44884477288 (`6de1779`) passed in about 22 min; in that run `pytest (windows-latest, py3.13)` took about 25 min.
- **Done when:** the Windows pytest jobs finish within their timeout (a raised timeout with a stated reason, or a sharded suite) in 10 consecutive CI runs, and the job times are reported.

#### P2-15 Faster slow test fixtures (hybrid_setup and streaming calibration)
- **Gap:** 156 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P2-14). Follow-up of P2-14.
- **Status:** `done` (2026-11-21; commits `ee590af`, `03d2308`). Exact CTC beam finalize speed-up: batched numpy n-best marginals (same floats as before) and `frame_only=True` in the trust drop-in decoders. Config ids, sheets, views and events are identical to HEAD; assertions unchanged. CI windows py3.12: `hybrid_setup` 27.53 s (run 44912022087) and 27.31 s (run 44913077810), was 121 s; streaming setup 22.85 s and 20.88 s, was 91 s. `tests/shard_weights.json` refreshed from run 44912022087.
- **Follow-ups:** gap 162 = [P2-16](#p2-16-hybrid_setup-margin-under-25-s-on-windows-ci) (`hybrid_setup` margin); gap 163 = [P3-14](#p3-14-re-measure-the-implant-logits-latency-after-p2-15) (`implant-logits` latency tables).
- **Depends on:** P2-14 (done). CPU.
- **Source:** P2-14 (2026-11-21, `--file-durations` on CI, windows py3.12): the module fixture `hybrid_setup` in `tests/test_trust_hybrid_commit.py` takes 121 s; the setup of `test_calibrate_streaming_end_to_end` in `tests/test_trust_stream_commit.py` takes 91 s.
- **Ideas:** a cached or precomputed calibration.
- **Done when:** both take less than 30 s on windows py3.12 CI, with all assertions unchanged, and `tests/shard_weights.json` is refreshed.

#### P2-16 hybrid_setup margin under 25 s on windows CI
- **Gap:** 162 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P2-15). Follow-up of P2-15.
- **Status:** `done` (2026-11-21; commits `24b7cc7`, `873f068`). Gap 162 closed. Exact speed-ups: `PrefixReuseSearch` + `IncrementalPrefixBeam.fork()` in the trust drop-in decoders (about 35 % of the frames pushed); faster `_align_group` Viterbi (`_viterbi_fast`, same tie choice, NaN / +inf fallback). Same config ids, sheets, views and events as HEAD; 16,488 randomised comparisons, 0 mismatches; assertions unchanged. CI windows py3.12 `hybrid_setup`: 21.06 s (run 44931534102), 14.58 s (run 44932516115), 20.99 s (run 44932516115 attempt 2); was 27.5 s. `tests/shard_weights.json` refreshed from run 44931534102.
- **Depends on:** P2-15 (done). CPU.
- **Source:** P2-15 (2026-11-21, commits `ee590af`, `03d2308`): `hybrid_setup` takes 27.53 s (run 44912022087) and 27.31 s (run 44913077810) on windows py3.12. This is under the 30 s target, but the margin is small.
- **Ideas:** the beam push, `_align_group`.
- **Done when:** `hybrid_setup` stays under 25 s on windows py3.12 CI in 3 runs, with all assertions unchanged.

#### P2-17 LF line endings for shell scripts
- **Gap:** 213 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the rental kit). Follow-up of P2-09.
- **Status:** `in_progress` (2026-11-24; one code-fix agent runs gaps 200, 202, 205, 195 and 213; nothing committed yet). Low priority.
- **Serves:** research labs, small teams.
- **Depends on:** rental kit `aa91210` (done); `.gitattributes` is a shared file; CPU. Low priority.
- **Source:** plan agent report (2026-11-23, commit `aa91210`): `tools/rental/setup_cuda.sh` runs with bash on a Linux machine. A Windows checkout with `core.autocrlf=true` can write CRLF line ends, and bash then fails. `.gitattributes` has no rule for `*.sh`.
- **Done when:** `.gitattributes` has `*.sh text eol=lf`, the script is renormalised, and a check shows LF bytes in a fresh checkout.

## P3. Collector (pipeline)
**Goal:** a vendor-neutral process, like the OpenTelemetry Collector, that takes NTS from any source, applies processors, and sends results to any target. Configuration is a TOML/JSON file (FEP-0006; [decision 2026-11-17](collector-decisions-2026-11.md)).

**Status (2026-11-14):** v0 started early. Draft [FEP-0006](../../spec/feps/0006-collector.md) and `src/fidetype/collector/` ([collector](../concepts/collector.md)): receivers `file` + `websocket`, processors `validate` + `trust` + `redact` + `thin`, exporters `jsonl` + `stdout` + `websocket`, TOML / JSON configuration (no YAML yet), health and metrics. Not yet: LSL, gRPC, OS input exporters, latency budget.

### Deliverables
| Stage | Components |
|---|---|
| **Receivers** | NTS gRPC, WebSocket, LSL, files; device adapters from P4 |
| **Processors** | Trust layer (calibration, conformal sets, decision policy), per-user calibration, LM rescoring, segmenter, **privacy filter** (drop or hash `meta` keys, enforce spec 5.4), rate limiter, provenance stamper |
| **Exporters** | **OS text input**: Windows TSF / IME, Android IME, macOS input method, Linux IBus; Apple BCI HID bridge (spec 6.5); **AAC apps** (WebSocket API for web AAC tools); files (Arrow, JSON Lines); analytics (Parquet, an optional OTLP export of latency metrics) |

- Language: Python for v1 ([decision 2026-11-17](collector-decisions-2026-11.md)). A Rust core can follow later for embedded or on-device use, if a measured need appears (P5-05 already plans a C or Rust on-device trust core).
- A `contrib` folder for third-party components, as in OTel.
- Hard rule: an exporter to an OS input method sends **only committed** decisions. It logs the full NTS next to each output.
- **Value-first link (2026-11-15):** [P14-09](#p14-09-example-aac-integration) uses the WebSocket exporter for an example AAC app integration. P3 scope does not change.

> **Decision (2026-11-17, orchestrator; the user delegated it):** (1) The collector config format is **TOML/JSON (FEP-0006)**, not YAML. FEP-0006 section 6 made this choice on purpose. TOML has explicit types (no YAML "Norway problem", no octal or bool coercion) and is in the Python standard library (`tomllib`). JSON covers configs that programs write. This closes gap 40 = P3-09. (2) Collector v1 is **Python**. The collector, the trust layer, the adapters and the tests exist in Python and meet the latency budget (p95 added about 1–3 ms vs 50 ms). A Rust core can come later if a measured need appears. Record: [collector decisions 2026-11](collector-decisions-2026-11.md).

### Exit criteria
- One TOML/JSON config (FEP-0006) runs: B2T '25 replay → trust processor → file exporter and WebSocket exporter. End-to-end latency is measured and below 50 ms added (our target).
- At least one OS input exporter types committed text into a text field on Windows.
- Components have unit tests and a pipeline integration test in CI.

**Effort:** 30–50 agent-days; about 8 h user testing on the PC. **Depends on:** P2 (Python and Rust), P5 trust API.

**Status (2026-11-17):** P3-04 `done` (commit `2298e3e`): a pipeline integration test and the latency budget. One TOML file runs receiver (WebSocket, file, LSL) → `validate` → `segment` (new) → `guard` (new: drop-in guard, per-user profile, online ACI) → `jsonl` NTS stream + decision log + `os_text` stub (new) + WebSocket `/decisions`. Outputs reach producer level NTS Trust-ready; p95 added latency 1.1–2.3 ms at 50 Hz for the gated profiles (budget 50 ms); CI job `collector` fails above the budget. The logits guard with its built-in CTC beam search in the collector takes 104–108 ms at p95 (gap 37 = P3-06). [Docs](../../docs/collector.md#integration-test-and-latency-budget-p3-04). P3-01, P3-02, P3-03 stay `in_progress` (inventory in the tracker notes). P3 exit criteria still open: an OS input exporter that types on Windows (P3-03). Config format: TOML/JSON (FEP-0006), decided 2026-11-17 (gap 40 = P3-09 closed). The B2T '25 replay through the collector is done (P3-08, 2026-11-17: p95 added 2.43 ms). P3-07 (LSL receive stamps) and P7-07 (collector consumer, all kit profiles) are done; new gap 43 = P3-10.

#### P3-06 Logits guard inside the latency budget (incremental decoding)
- **Gap:** 37 of the [open-gap list](open-gaps.md). Follow-up of P3-04, P14-03.
- **Status:** `todo`.
- **Depends on:** P3-04 (done); the incremental CTC beam of `fidetype.lm.beam` (precomputes the n-best pairs during frames).
- **Source:** P3-04 (2026-11-17): profile `implant-logits` (the drop-in guard with input kind `logits` decodes with its built-in CTC prefix beam search, beam 64, lexicon, n-best marginal confidences, at each segment end): p95 added latency 104.1 ms (WebSocket), 108.0 ms (file), 107.3 ms (LSL); the search is about 95 % of it (`_nbest_marginal` / `align_pairs`).
- **Done when:** a logits guard in the collector decides within the 50 ms budget at p95 on the `implant-logits` bench profile (for example: decode incrementally while frames arrive, with the same decisions as the offline search on the same input, checked by a test), and the profile joins the CI gate.
- **Evidence (2026-11-19, P11-09):** real EMG replay (emg2qwerty, P11-01 decoder, beam 16, no lexicon, about 500 frames x 33 keys per prompt): `added` p50 58.6 ms, p95 110 ms (median over 8 runs), 222 ms (max); `processor.guard` is almost all of it ([results](../../experiments/2026-11-19-p11-09-emg-trust/results.md)).
- **Evidence (2026-11-19, P11-07):** in-beam character LM, streaming in 40 ms chunks (emg2qwerty, 1,221 windows, 1 thread): beam `push` p95 0.3-0.7 ms per chunk for beams 4-64; added time at the window end (last chunk, n-best, intended merge, gates, `guard.decide`) p95 61-70 ms, almost the same for every beam; CPU acoustic model chunk (NumPy CRT, 4 threads) p95 47 ms, GPU 4 ms. So the 50 ms CPU rule fails at every beam (108-117 ms); the beam is not the bottleneck ([results](../../experiments/2026-11-20-p11-07-emg-beam-lm/results.md#latency-1221-evaluation-windows-1-thread-chunk-4-frames--40-ms)). Follow-up: P3-12 (gap 122).
- **Evidence (2026-11-20, P3-12):** with the streaming CRT model and the incremental guard decision (`TrustGuard.session()`, `StreamingTrustLayer.push_frames`), the same EMG decoder + guard decides in p95 6.39 ms on CPU with the same decisions as the offline guard ([results](../../experiments/2026-11-20-p3-12-emg-latency-budget/results.md)). The collector guard processor and the `implant-logits` bench profile do not use them yet, so this item stays open.

#### P3-07 Receive stamps for LSL input (merge-window wait in the latency)
- **Gap:** 38 of the [open-gap list](open-gaps.md). Follow-up of P3-04, P3-01.
- **Status:** `done` (2026-11-17, commit `2984990`). The LSL source marks each released event with its pull time (`LSLEventSource.arrival_key`); the collector's LSL receiver sets it to `_fidetype_t_recv` (`time.perf_counter` clock, never exported), and the latency recorder counts `receive` and `added` from it. Result: the merge-window wait was the largest part of the LSL latency (implant-speech p95 61.3 ms at the default `merge_window_s` 0.05, not 1.1 ms). Two fixes: `LSLEventSource.poll` waits at most until the oldest held event's merge window ends; the bench uses `merge_window_s = 0.02`. New LSL p95 added: implant-speech 26.8 ms, emg-key 22.9 ms (PASS). [Docs](../../docs/collector.md#lsl-receive-stamps-p3-07). New gap 43 = P3-10.
- **Depends on:** P3-04 (done); `fidetype.adapters.lsl` (LSLEventSource).
- **Source:** P3-04 (2026-11-17): for LSL input the `added` latency starts at the receiver's poll return. The inlet merge window (`merge_window_s`, default 50 ms) can hold an event before that; this wait is not measured. WebSocket input has `ws_t_recv`, LSL input has no equal stamp.
- **Done when:** the LSL receiver stamps each event at pull time (local clock, not sent on), the latency recorder uses it for `receive` and `added`, and the LSL bench numbers include the merge wait.

#### P3-08 B2T '25 replay through the collector with the latency budget
- **Gap:** 39 of the [open-gap list](open-gaps.md). Follow-up of P3-04.
- **Status:** `done` (2026-11-17, commit `2984990` (code; results committed with this record)). 120 T15 `val_eval` trials (M4-12 fixed0 log-probs + the P14-03 word LM n-best) at real time over WebSocket into one collector: `validate` -> `segment` -> `guard` (n-best guard calibrated on `val_select`, null controls passed, per-user profile, online ACI) -> NTS file + decision log + `os_text` stub + WebSocket `/decisions`. p95 added **2.43 ms** (budget 50 ms); producer level NTS Trust-ready; 120 decisions, all OFFER (the weak M4-12 decoder: no commit, see P15-19). Re-runnable with `--decoder m4-13`. [Results](../../experiments/2026-11-17-p3-08-b2t25-collector-replay/results.md).
- **Depends on:** P3-04 (done); B2T '25 data on the local machine (not in CI); a B2T guard or trust configuration (P6-02 entries).
- **Source:** P3-04 (2026-11-17): the P3 exit criterion names a B2T '25 replay; P3-04 uses synthetic input only (CI has no data).
- **Done when:** a local run replays B2T '25 at real time into the collector (WebSocket or LSL), with a trust step and the file and WebSocket exporters; the outputs pass `nts-conform` (producer level reported) and the p95 added latency is reported against the 50 ms budget in an experiment page.

#### P3-09 YAML configuration: roadmap or FEP-0006 (user decision)
- **Gap:** 40 of the [open-gap list](open-gaps.md). Follow-up of P3-01.
- **Status:** `done` (2026-11-17). Decided: TOML/JSON (FEP-0006), option (a). The P3 goal and exit criterion now say "TOML/JSON (FEP-0006)". FEP-0006 does not change. The user delegated the decision to the orchestrator. Record: [collector decisions 2026-11](collector-decisions-2026-11.md).
- **Depends on:** a user decision (made 2026-11-17).
- **Source:** P3-04 (2026-11-17): the P3 exit criterion says "one YAML config"; FEP-0006 section 6 decided "TOML and JSON only, YAML not planned" (no new dependency, PyYAML). The integration test uses TOML.
- **Done when:** the user chooses: (a) change the exit criterion to "one TOML or JSON config", or (b) add YAML as an optional extra (`fidetype[yaml]`, PyYAML) and amend FEP-0006; then the roadmap and FEP-0006 say the same.

#### P3-10 LSL merge window inside the latency budget (idle events stream)
- **Gap:** 43 of the [open-gap list](open-gaps.md). Follow-up of P3-07.
- **Status:** `done` (2026-11-17). NTS 1.0 RC4 amendment 5: LSL-C7 heartbeat (an empty events-stream sample moves the events watermark; a two-stream producer SHOULD send one after each frame) and LSL-C8 (at equal times the frame goes first; markers carry the time of the frame before them). FEP-0002 section 6 rules 7-8, vectors L36, L37 (three SDKs). At the receiver default (0.05 s): implant-speech p95 added 1.07 ms (was 60.4 ms), emg-key 2.89 ms; the bench and the CI LSL tests (both gated profiles) now use the default ([collector doc](../../docs/collector.md#lsl-heartbeat-and-equal-times-p3-10)).
- **Depends on:** P3-07 (done); FEP-0002 (LSL binding, LSL-C6 merge).
- **Source:** P3-07 (2026-11-17): with receive stamps, the inlet merge window is most of the LSL added latency. A frames stream and an idle events stream go through one merge, so each frame and each boundary waits about `merge_window_s`. At the receiver default (0.05 s) implant-speech has p95 added 60.4 ms (over the 50 ms budget); the bench uses 0.02 s (p95 26.8 ms).
- **Done when:** the LSL receiver meets the 50 ms budget at its default settings with a two-stream producer (for example: an events-stream heartbeat in the binding that lets the merge release frames at once, or a default `merge_window_s` below the budget with a measured `late_releases` rate), and FEP-0002 and the docs say the same.

#### P3-11 Collector soak test: 24 h run, reconnects, memory
- **Gap:** 114 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P3-04, M6-13, M6-15.
- **Status:** `todo`.
- **Depends on:** P3-04 (done); the M6-15 soak harness (done).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" M6-13 (1 h+) and M6-15 (7 h) soak-tested the live path (BrainFlow -> LSL -> trust). No soak test covers the collector (receivers, guard processor, exporters, WebSocket clients that connect and drop).
- **Done when:** A pre-registered 24 h collector run (replay input over WebSocket and LSL, guard on, file and WebSocket exporters, forced client and source reconnects) meets written criteria: no crash, bounded memory growth, no lost or duplicate decisions, p95 added latency inside the 50 ms budget. A results page gives the check, stop and resume commands.

#### P3-12 Guard end-of-window cost and CPU acoustic model inside the 50 ms budget
- **Gap:** 122 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-07). Follow-up of P3-06, P11-07.
- **Status:** `done` (2026-11-20; pre-registration `cfbc26e`, amendments `a3d9f10`, `b32faab`, `eaa8152`, `6d4fdbd`, results `3a0fd49`). Gap 122 closed. On the same 1,221 evaluation windows (CPU, isolation class timing, 1 thread, clean record) the in-beam LM decoder FL@B8 + arm S guard decides in **p95 6.39 ms** (last 40 ms chunk in -> decision out, model included; p50 4.93 ms); a 40 ms chunk costs p95 3.48 ms. Changes: streaming CRT model (`fidetype.pretrained._crt.CRTStream`, 2.9 ms vs 20.5 ms per chunk), incremental guard decision (`TrustGuard.session()` -> `GuardSession`; `StreamingTrustLayer.push_frames`). Same decisions as the offline guard on 3,663 / 3,663 windows (real, shuffled, zeros); safe WPM v0.1 3.37 unchanged. The pre-registered streaming-model tolerance (1e-5) failed (3.1e-5; float32 rounding; float64 forms agree to 3e-15) -> new gap 142 = [P3-13](#p3-13-streaming-crt-model-in-the-decision-loop). [Results](../../experiments/2026-11-20-p3-12-emg-latency-budget/results.md).
- **Depends on:** P11-07 (done); P3-06 (gap 37); `fidetype.pretrained._crt` (NumPy CRT); CPU.
- **Source:** P11-07 ([results](../../experiments/2026-11-20-p11-07-emg-beam-lm/results.md)): the in-beam LM beam costs at most 0.7 ms p95 per 40 ms chunk, but the end-of-window work (n-best to intended texts, OOV and no-signal gates, `guard.decide`) is 61-70 ms p95 for every beam 4-64, and the CPU model chunk (NumPy, 4 threads) is 47 ms p95 (GPU 4 ms). Beam 8: 67.6 + 47.1 = 114.7 ms > 50 ms.
- **Done when:** a profile names the end-of-window costs; an incremental guard decision (features kept up to date while frames arrive) plus a faster CPU acoustic model (or the GPU path, stated as such) gives p95 <= 50 ms on the same 1,221 windows, with the same decisions as the offline guard (test).

#### P3-13 Streaming CRT model in the decision loop
- **Gap:** 142 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P3-12). Follow-up of P3-12.
- **Status:** `done` (2026-11-21; pre-registration `f7f66b0`, results `09d9eb7`, [results](../../experiments/2026-11-21-p3-13-streaming-crt-loop/results.md)). Gap 142 closed: the streaming per-user CRT (P11-01 weights, CPU) in the decision loop gives the same decisions as the P11-09 batch log-probs on 3,663 / 3,663 windows (1,221 evaluation windows x real / time-shuffled / zero); max p_top1 difference 2.1e-5 (tolerance 1e-3); n-best texts and gates identical; commits 154 / 154; controls 0 / 0; safe WPM v0.1 3.37 [1.92, 5.18] certified, 43 wrong (same as P3-12). Decision p95 8.02 ms (p50 5.41, max 13.7), chunk p95 4.94 ms (model 4.27), clean timing run, 1 thread: about 6 x under the 50 ms budget. C2 log-prob check passes (max probability difference 9.7e-4 on zero EMG; small margin). Stated deviation: gated CER computed instead of no-gate CER. No new gap.
- **Depends on:** P3-12 (done); the P11-01 per-user weights (research only); CPU.
- **Source:** P3-12 ([results](../../experiments/2026-11-20-p3-12-emg-latency-budget/results.md)): the decisions used the P11-09 log-probs; the streaming CRT ran as a cost stand-in (u0 weights). Its float32 output differs from the batch model by up to 3.1e-5 in probability (the pre-registered 1e-5 failed; the float64 forms agree to 3e-15).
- **Done when:** the streaming model output with the per-user weights feeds the guard session and the beam on the 1,221 evaluation windows, and the decisions match those from the batch log-probs, or the differences are counted and the safe WPM v0.1 stays within the P3-12 tolerance (>= 3.32, certified, controls 0).

#### P3-14 Re-measure the implant-logits latency after P2-15
- **Gap:** 163 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P2-15). Follow-up of P3-04, P2-15.
- **Status:** `todo`. Low priority.
- **Depends on:** P2-15 (done; faster CTC beam finalize); CPU.
- **Source:** P2-15 (2026-11-21, commit `ee590af`): after the faster finalize, `implant-logits` takes about 13.3-17.6 ms. The latency tables in docs/collector.md still show about 104-124 ms p95 and "over (not gated)".
- **Done when:** `implant-logits` is re-measured locally, the tables in docs/collector.md are updated, and `implant-logits` is gated if it meets the 50 ms budget.

## P4. Device and toolkit adapters
**Goal:** NTS comes out of the tools that people already use. Dataset replay stands in for devices we do not own.

### Deliverables (in order)
| # | Adapter | Kind | Licence / terms | Notes |
|---|---|---|---|---|
| 1 | **Dataset replay**: Brain-to-Text '25, Willett handwriting, KT-sEMG, Toronto sEMG (commercially clean); SpanishBCBL, emg2qwerty (research only) | replay | CC0 / CC BY 4.0 / CC BY-NC 4.0 ([public datasets](public-datasets.md)) | Replay at real time from files. Tests devices we do not own. Own loader code only |
| 2 | **LSL** in/out | toolkit | MIT ([LSL](../entities/lab-streaming-layer.md)) | Already priority 1 in M6 |
| 3 | **BrainFlow / OpenBCI** | toolkit + boards | MIT ([BrainFlow](../entities/brainflow.md)) | Covers many boards through one API |
| 4 | **MNE-Python** | toolkit | BSD-3-Clause (to check) | Raw → decoder → NTS examples; MNE `Raw` replay |
| 5 | **BCI2000** | toolkit | to check (copyleft suspected) | Separate process over LSL or network; no linking until checked |
| 6 | **OpenViBE** | toolkit | to check (copyleft suspected) | Same rule as BCI2000 |
| 7 | **Emotiv** (Cortex API) | consumer EEG | vendor terms, to check | Probably needs an app licence and a device (**user-owned**) |
| 8 | **Muse** (Interaxon) | consumer EEG | vendor terms, to check | Community LSL bridges exist (to check) |
| 9 | **Neurosity** | consumer EEG | SDK licence, to check | `score_semantics = power` style scores ([spec 3.5](../../spec/neuraltextstream-v0.1.md#35-decision-event-development)) |
| 10 | **EMG bands**: [Meta Neural Band](../entities/meta-neural-band.md) (Web Apps shim, `score_semantics = none`), other sEMG bands | consumer EMG | vendor terms, to check | DOM events only for Meta's band today |
| 11 | **[Apple BCI HID](../entities/apple-bci-hid.md)** bridge + logger | OS input | Apple developer terms, to check | Lossy downstream bridge (spec 6.5) |

- **Status (2026-11-15):** two generic decoder-output adapters exist: [CTC-logits adapter](../concepts/ctc-logits-adapter.md) (frames from any CTC decoder) and [text n-best adapter](../concepts/text-nbest-adapter.md) (text-only decoders → hypothesis stream). Dataset replay adapters so far: B2T '25, Toronto sEMG, SpanishBCBL, [Willett handwriting](../entities/willett-handwriting-2021.md#replay-adapter-p4-01-2026-11-14) and [KT-sEMG](../entities/kt-semg-dataset.md#replay-adapter-p4-01-2026-11-14) (both 2026-11-14). [emg2qwerty](../entities/emg2qwerty.md#replay-adapter-p4-01-2026-11-15) followed on 2026-11-15 (research only). All six replay adapters of deliverable 1 exist; P4-01 is done.
- Each adapter has a replay test that runs in CI with no hardware.
- **Value-first link (2026-11-15):** [P14-04](#p14-04-live-decode-from-lab-tools) builds a one-command live path on the LSL and BrainFlow / OpenBCI adapters of deliverables 2–3 (task P4-02). P4 scope does not change.
- **P4-02 done (2026-11-16):** LSL in/out (M6-01, `fidetype lsl`), BrainFlow → LSL bridge (M6-08) and an in-process BrainFlow source in `fidetype live` (OpenBCI Cyton / Ganglion through their BrainFlow board ids; untested on a real board: P4-06). Synthetic-board test: CI job `live` runs `fidetype live --source brainflow --board-id -1` and a real pylsl loopback end to end ([docs](../../docs/live-decode.md), `tests/test_live.py`). New gaps: P4-10 (live key-onset detector), P4-11 (reconnect in `fidetype live --source lsl`).
- Licence rule: before any code, an agent records the licence or terms in the adapter README. Copyleft toolkits get **process-separated** adapters only. We copy no third-party code.

### Exit criteria
- Four replay adapters (two modalities with commercially clean data) emit valid NTS in CI.
- LSL and BrainFlow adapters pass a live test with the BrainFlow synthetic board.
- Each real-device adapter is tested on the device: **externally blocked** (needs hardware; the user has none today).

**Effort:** 30–60 agent-days; user: hardware purchase or loans (**user-owned**). **Depends on:** P1, P2; dataset downloads.

### Open-gap items (added 2026-11-16)
The user asked that known gaps are fixed later, not forgotten. These items come from agent reports of 2026-11-16. Full list: [open gaps](open-gaps.md). No existing item moved.

#### P4-09 BrainFlow bridge: move `device.board_id` / `device.board_name` out of the reserved namespace
- **Gap:** 9 of the [open-gap list](open-gaps.md). Follow-up of P4-02.
- **Status:** `done`. Commit `18713f9` (2026-11-16): vendor keys `brainflow.board_id`, `brainflow.board_name`; test with no MET-3 warning.
- **Depends on:** P1-04 (semconv registry).
- **Source:** MET-3 warning on BrainFlow bridge streams ([docs/semconv.md](../../docs/semconv.md) rule 3); open-gap list 2026-11-16.
- **Done when:** `src/fidetype/adapters/brainflow_bridge.py` no longer writes custom keys in the reserved `device` namespace: the keys move to a vendor namespace (for example `brainflow.*`) or a FEP registers them in `spec/semconv/`. A bridge stream validates with no MET-3 warning, and a test checks this.

#### P4-10 Live key-onset detector for EMG (no oracle key markers)
- **Gap:** 16 of the [open-gap list](open-gaps.md) (added 2026-11-16 by P14-04). Follow-up of P4-02 / P14-04.
- **Status:** `done`. Commits `c3834c2` (code + pre-registered plan, before any test run) and `de7f84e` (results), 2026-11-17: `fidetype live --timing detect` with `--onset envelope` or a trained linear `*.onset.json` (`fidetype.live.onset`, causal, numpy only). KT-sEMG test runs, ±50 ms: linear detector recall 0.829, precision 0.456, F1 0.588 (H1 >= 0.70 failed; 0.73 on the two dense-typing runs), 238 false alarms / min, matched error median about 20 ms; envelope F1 0.461. End to end: effective key accuracy 0.229 vs 0.274 oracle (0.84x), 172 decisions, 0 commits in every arm (vacuous). New gaps P4-12, P4-13. [Results](../../experiments/2026-11-17-p4-10-onset/results.md).
- **Depends on:** P14-04 (done); KT-sEMG or emg2qwerty data; P11-01 (a stronger EMG decoder can share the detector).
- **Source:** P14-04: `fidetype live` with `markers` timing needs `keypress` onset markers. In the KT-sEMG replay they come from the key log (oracle timing, as in P4-01). A real board gives no markers, so boards use `fixed` timing.
- **Done when:** a causal onset detector (for example an EMG envelope with an adaptive threshold, or a small classifier) runs inside `fidetype live` as `--timing detect`. On the KT-sEMG test runs it finds key onsets with a stated recall and false-alarm rate at a stated tolerance (for example ±50 ms), and the end-to-end replay with detected onsets reports decisions and the wrong-commit rate next to the oracle-timing run.

#### P4-11 Reconnect in `fidetype live --source lsl`
- **Gap:** 17 of the [open-gap list](open-gaps.md) (added 2026-11-16 by P14-04). Follow-up of P4-02 / P14-04.
- **Status:** `done`. Commit `c3834c2` (2026-11-17): `LSLSource` re-resolves a lost signal / marker stream with `fidetype.adapters.lsl._Reopener` / `_Reconnector` (new opt-in backoff), drops the cut segment and the first segment after the gap, and writes `lsl_status` `gap_abort` with the LSL-G3 fields (plus `lsl_cause`); `--max-reconnects`, `--reconnect-timeout`, `--reconnect-backoff`. Tests: scripted-inlet loss (always runs) and a real pylsl outlet closed and opened again (reconnect in 1.9 s; no decision spans the gap; ran in CI, not skipped). [Docs](../../docs/live-decode.md#4-lsl-streams).
- **Depends on:** P14-04 (done); M6-14 / M6-16 (the reconnect code of `fidetype lsl run`).
- **Source:** P14-04: `LSLSource` ends the run when the stream is lost. `fidetype lsl run` has non-blocking reconnect, but its event source makes NTS frames inside the inlet and cannot pass key markers to a raw-signal model.
- **Done when:** `fidetype live --source lsl` survives a stream loss: it drops the open segment (no decision on a cut input), re-resolves the stream (reusing the `fidetype.adapters.lsl` reconnect code, not a copy) and goes on. A test kills and restarts a loopback outlet and checks that no decision spans the gap.

#### P4-12 Onset detector: false alarms on forearm activity without typing
- **Gap:** 21 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P4-10). Follow-up of P4-10.
- **Status:** `todo`.
- **Depends on:** P4-10 (done); KT-sEMG or emg2qwerty data; P11-01 (a stronger EMG decoder can share features).
- **Source:** P4-10 ([results](../../experiments/2026-11-17-p4-10-onset/results.md)): on the KT-sEMG test runs with little typing (run26: 107 keys, run27: 230 keys) the linear detector keeps recall 0.90-0.94 but has precision 0.02-0.04; pooled F1 0.588 < 0.70 (H1).
- **Done when:** a pre-registered rerun on the same test runs reaches pooled F1 >= 0.70 at ±50 ms with no run below precision 0.3 (for example with a typing-activity gate, or idle-period negatives in training), and the end-to-end CER with detected onsets is reported next to the oracle CER.

#### P4-13 Segment ends from the signal (no `segment_end` markers)
- **Gap:** 22 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P4-10). Follow-up of P4-10.
- **Status:** `todo`.
- **Depends on:** P4-10 (done), P4-12.
- **Source:** P4-10: with `--timing detect` the segment ends still come from markers (oracle bursts in the evaluation) or a fixed `--segment-s`.
- **Done when:** `fidetype live` can end a segment after a pause in the detected onsets (for example `--segment-pause S`), and a KT-sEMG replay with no markers at all reports decisions, wrong commits and segment boundary error against the benchmark bursts.

#### P4-14 Flaky reconnect test on the macOS runner
- **Gap:** 81 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P13-08). Follow-up of P4-11.
- **Status:** `done` (2026-11-18, code `efa56f5`). Done 2026-11-18 (code `efa56f5`). Root cause: a check-then-act race in the reconnect loop, not a slow runner. After a `take()` that returned None, `LSLSource._try_reconnect` (and `LSLEventSource`) called `_Reconnector.done()` twice. If the worker set its inlet and ended between the two calls, the loop saw "ended, no inlet", started a second worker and called `reopen()` a third time (the first inlet was never taken: a leak with real pylsl). Fix: `_Reconnector.take_or_ended()` reads `done()` once, before the last `take()`; both loops use it. The bound stays `== 2`. New deterministic tests replay the race with a scripted fake worker (no thread, no sleep) at 5 schedule points; the old code fails 2 of 5. Also `EventTee.flush()` skips closed files (the "I/O operation on closed file" log errors). Local stability: 19 full runs in a row, 141 passed each (about 95 s per run; the planned 30 runs stopped at 19 because the machine ran low on memory next to GPU training) of `tests/test_live*.py` + LSL adapter tests at idle priority, 0 failures. Done-when note: the "20 times in a row on the macOS runner" check is replaced by the deterministic schedule test, which runs the race window on every OS in every CI run; the macOS job of the push run is green (see the log entry).
- **Depends on:** P4-11 (done).
- **Source:** CI run 44437999699 (commit `747f2ea`, 2026-11-18), job `conformance (macos-latest)`, full pytest suite: `tests/test_live_reconnect.py::test_loss_drops_cut_segment_and_reconnects` failed with `tries["n"] == 3` (expected 2; `losses == 1`, `reconnects == 1` held), plus "I/O operation on closed file" log errors. 1544 other tests passed. The same commit passed on Linux and Windows, and the previous commit passed on macOS, so the test depends on runner timing.
- **Done when:** the cause of the extra `reopen()` call is found and fixed in the code or the test (no retry loop, no wider bound); the test passes 20 times in a row on the macOS runner.

#### P4-15 Device support matrix generated from adapter metadata
- **Gap:** 110 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P4-01, P4-02, P4-06.
- **Status:** `done` (2026-11-21; commit `ffc74f4`; CI `tests` and `tutorials` green on `ffc74f4`). Gap 110 closed. Each `ADAPTER_INFO` declares `support` (real-device / replay-only / synthetic-only; planned = untested), `real_data_evidence`, `transport`, `test_covers` and `limits`. The registry refuses unbacked claims. `python -m fidetype.adapters.registry` generates [docs/device-support.md](../../docs/device-support.md) (0 real device, 14 replay only, 3 synthetic only, 16 untested), and `--check` plus `tests/test_adapter_registry.py` (21 tests) fail when it is stale. Registry schema 0.2.
- **Follow-ups:** gap 176 = [P4-21](#p4-21-nts-over-lsl-transport-on-real-decoder-output) (NTS over LSL on real decoder output); gap 177 = [P4-22](#p4-22-text-nbest-csv-and-json-lines-readers-on-real-decoder-output-files) (`text-nbest` file readers on real decoder output).
- **Depends on:** P4-01, P4-02 (done).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" Adapters exist for six dataset replays, LSL, BrainFlow (OpenBCI and other boards) and WebSocket. No adapter is tested on a real device (the user has no EEG or MEG hardware). No page tells a user which devices work. Real-device tests stay P4-06 and M6-12 (`externally_blocked`, hardware); consumer-device adapters stay P4-05 and M6-02 (wristband demo: P14-07). This item adds no new device item.
- **Done when:** Each adapter declares in metadata its support level (tested on a real device / replay only / synthetic only / untested) and the devices it was tested on. A script generates `docs/device-support.md` from the metadata. CI fails when the page and the metadata differ. The README links the page.
- **Progress (2026-11-20, P14-42):** the P14-42 registry gives each adapter `status` (tested / experimental / planned) and `hardware_tested` (empty for all) in its `ADAPTER_INFO`; [docs/adapters.md](../../docs/adapters.md) is generated with a CI check. Left for P4-15: the four-level support field (real device / replay only / synthetic only / untested) or a decision that `status` + `hardware_tested` replace it, `docs/device-support.md` (or accept `docs/adapters.md`), and the README link.
- **Progress (2026-11-21, P4-16, commit `b73d9a7`):** the `edf` and `openbci-gui` readers are now `tested` on real public files. The catalogue now has 16 `tested` adapters and 1 `experimental` (`brainflow`).

#### P4-16 Real-file check of the EDF and OpenBCI GUI readers
- **Gap:** 134 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P14-42). Follow-up of P14-42.
- **Status:** `done` (2026-11-21; commit `b73d9a7`; CI `tests` run 44896959230 green). `edf` read PhysioNet EEGMMIDB S001R01.edf and S001R04.edf (ODC-By 1.0) and MNE test.edf / test.bdf (BSD-3); `openbci-gui` read OpenBCI_GUI-v6-blinks-jawClench-alpha.txt (MIT). EDF equals MNE exactly; BDF within 0.17 digital step; OpenBCI against a csv parse within 0.005 uV. Conformance and `fidetype live --source file --speed 0` pass; NTS trust-ready. Both readers are now `tested`. Licences in references/README.md. Local test `tests/test_adapter_files_real.py` (skipped without the data); no real file committed. Bugs fixed: OpenBCI millisecond time stamps; the CLI gave 0 windows with non-keypress markers; a clearer error for GUI v4 files.
- **Follow-up:** gap 157 = [P4-18](#p4-18-openbci-gui-reader-on-a-real-gui-v5-recording-and-packet-drops).
- **Depends on:** P14-42 (done); public files with a licence that allows the test.
- **Source:** P14-42: the `edf` and `openbci-gui` readers pass the conformance helper on synthetic files only. The synthetic files follow the format descriptions as we know them. No real EDF / BDF file and no real OpenBCI GUI recording has been read, so both are `experimental`.
- **Done when:** each reader reads at least one real public file (for example a PhysioNet EDF+ recording and an OpenBCI GUI sample file; licences checked and recorded) outside the repository, the values match a second reader (for example MNE) within the format resolution, and the registry status becomes `tested`. No real file is committed.

#### P4-17 File-reader sources in the `fidetype live` command
- **Gap:** 135 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P14-42). Follow-up of P14-42, P14-04.
- **Status:** `done` (2026-11-21; commit `ae50049`; CI `tests` run 44896306731 green). `fidetype live --source file --path FILE [--reader ID]` picks the reader from the adapter registry by `file_patterns`; errors exit 2 / 3; `--speed` applies; the NTS header gets `fidetype.live.source="file"` and `fidetype.file_reader`. The template and CONTRIBUTING 7.1 say how a new reader joins. Test `tests/test_live_file_source.py`; registry `--check` passes.
- **Depends on:** P14-42 (done), P14-04 (done).
- **Source:** P14-42: `edf.open_source()` and `openbci_gui.open_source()` return `fidetype live` signal sources, but `fidetype live --source` accepts only `synthetic`, `brainflow` and `lsl`. A user cannot replay a recording file from the command line.
- **Done when:** `fidetype live --source file --path <file>` (or one option per reader) picks the reader from the registry, with a test on a synthetic file; the template and CONTRIBUTING 7.1 say how a new reader joins.

#### P4-18 OpenBCI GUI reader on a real GUI v5+ recording and packet drops
- **Gap:** 157 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P4-16). Follow-up of P4-16.
- **Status:** `done` (2026-11-21; commit `300d44f`; CI `tests` run 44935694762 green). Gap 157 closed by orchestrator decision: the met parts close, the rest is split. Packet drops: the reader checks the Cyton Sample Index (wrap 0-255 is not a drop; step 1 Cyton, 2 Daisy). Default `on_drop="gap"`: rows are kept, later times are corrected, `Chunk.gap` with cause `sample_index`, and the live runner writes `gap_abort`. `on_drop="error"` is available. Reason for the gap default: real files often have drops (Nepali file: 20 drops). Real GUI v5 files with time stamps in seconds (not committed; licences in references/README.md): Bot-Ro-Bot/Silent-Speech-Recognition-in-Nepali `OpenBCI-RAW-2021-05-13_15-21-21.txt` (GPL-3.0; Cyton 8 ch 250 Hz, GUI v5.0, Unix seconds; 20 drops / 30 samples lost, same as a plain-loop check) and Mendeley Data cp586sfzrt v4 `OpenBCI-RAW-2026-05-07_14-48-12.txt` (CC BY 4.0; Cyton + Daisy 16 ch 125 Hz, seconds; Marker Channel present but all zero). Tests: 9 synthetic in `tests/test_adapter_openbci_gui.py`; local `tests/test_adapter_openbci_gui_real.py` (env `FIDETYPE_P4_18_DATA`). Not met: non-zero markers on a real file.
- **Follow-ups:** gap 167 = [P4-19](#p4-19-openbci-gui-reader-on-a-real-recording-with-non-zero-marker-channel-values) (non-zero markers, externally blocked); gap 168 = [P4-20](#p4-20-sample-index-check-on-ganglion) (Ganglion index rule, low priority).
- **Depends on:** P4-16 (done); an openly licensed real OpenBCI GUI v5+ recording.
- **Source:** P4-16 (2026-11-21, commit `b73d9a7`): the only real OpenBCI GUI file read (OpenBCI_GUI-v6-blinks-jawClench-alpha.txt, MIT) has millisecond time stamps and no non-zero markers. The reader does not check the Sample Index for jumps (packet drops).
- **Done when:** the `openbci-gui` reader is checked on an openly licensed real OpenBCI GUI v5+ recording with time stamps in seconds and non-zero markers (licence recorded, file not committed), and a Sample Index jump (packet drop) raises an error or is recorded as a gap, with a test.

#### P4-19 OpenBCI GUI reader on a real recording with non-zero Marker Channel values
- **Gap:** 167 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P4-18). Follow-up of P4-18.
- **Status:** `externally_blocked` (needs an openly licensed file from outside people).
- **Depends on:** P4-18 (done); an openly licensed real OpenBCI GUI v5.1+ recording with non-zero Marker Channel values.
- **Source:** P4-18 (2026-11-21, commit `300d44f`): both real GUI v5 files read have time stamps in seconds, but no non-zero marker (Nepali file GUI v5.0, no Marker Channel; Mendeley cp586sfzrt v4 file: Marker Channel present but all zero). Search done: GitHub code search 85 repos (54 without a licence); Zenodo API 403; Mendeley 3 datasets; OSF and Figshare not searched directly.
- **Done when:** an openly licensed real OpenBCI GUI v5.1+ file with non-zero Marker Channel values is read, its marker times match a csv parse, the licence is recorded, and the file is not committed.

#### P4-20 Sample Index check on Ganglion
- **Gap:** 168 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P4-18). Follow-up of P4-18.
- **Status:** `todo`. Low priority.
- **Depends on:** P4-18 (done); a real or documented Ganglion GUI file. CPU.
- **Source:** P4-18 (2026-11-21, commit `300d44f`): the packet-drop check knows the Sample Index rule for Cyton (step 1, wrap 0-255) and Cyton + Daisy (step 2) only. No Ganglion file was read.
- **Done when:** a real or documented Ganglion GUI file gives the index rule, and drops are detected with a test.

#### P4-21 NTS-over-LSL transport on real decoder output
- **Gap:** 176 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P4-15). Follow-up of P4-15.
- **Status:** `done` (2026-11-22). Gap 176 closed. (plan `6039ad0`, results `bd597d7`, [results](../../experiments/2026-11-22-p4-21-lsl-replay/results.md)): 816 real B2T '25 trials over a real pylsl loopback (pylsl 1.18.6, one machine). Decisions over LSL = in-process = batch on 816 / 816; 161,503 `double64` frames bit-equal; 0 faults. The `lsl` matrix row is now `replay-only`. Matrix: 0 real device / 15 replay-only / 2 synthetic-only / 16 untested. Limits: one host, unpaced, hypothesis route only for trust decisions.
- **Follow-ups:** gap 186 = [P4-23](#p4-23-nts-over-lsl-across-two-hosts-with-a-paced-latency-run); gap 187 = [P4-24](#p4-24-frames-route-trust-decisions-over-lsl-on-real-streams).
- **Depends on:** P4-15 (done); the local B2T '25 NTS streams; CPU.
- **Source:** P4-15 (2026-11-21, commit `ffc74f4`, [docs/device-support.md](../../docs/device-support.md)): the `lsl` transport is `tested` only through a synthetic loopback (support level `synthetic-only`). The NTS-over-LSL path has not carried real decoder output yet (the raw-signal LSL path has: `lsl-signal-source`).
- **Done when:** real B2T '25 NTS streams are replayed over LSL (as M6-11 did for WebSocket), the evidence is recorded, and the matrix row cites it.

#### P4-22 `text-nbest` CSV and JSON Lines readers on real decoder output files
- **Gap:** 177 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P4-15). Follow-up of P4-15.
- **Status:** `done` (2026-11-22). Gap 177 closed. (plan `6039ad0`, results `bd597d7`, [results](../../experiments/2026-11-22-p4-22-nbest-readers/results.md)): `read_csv` / `read_jsonl` on real decoder output (1,718 online 1-best texts of the Card et al. 2024 decoder; 816 M4-06 10-best lists with 8,158 items). Exact round trip, 0 conformance failures. Honest scope: no local tool writes these forms, so a converter made the files (the decoders are real, the layout is ours); the real texts have 0 CSV quoting cases.
- **Follow-ups:** gap 188 = [P4-25](#p4-25-text-nbest-csv-reader-on-a-third-party-file-and-real-quoting-cases).
- **Depends on:** P4-15 (done); output files of a real decoder; CPU.
- **Source:** P4-15 (2026-11-21, commit `ffc74f4`, [docs/device-support.md](../../docs/device-support.md)): only `normalise_item` has seen real n-best lists (the KT-sEMG LDA lists of P5-33). The CSV and JSON Lines file readers ran on synthetic files only.
- **Done when:** both readers parse real decoder output files in a test or experiment, and the matrix row cites it.

#### P4-23 NTS over LSL across two hosts with a paced latency run
- **Gap:** 186 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P4-21). Follow-up of P4-21.
- **Status:** `todo`. Low priority.
- **Depends on:** P4-21 (done); a second machine on the same network; CPU. Low priority.
- **Source:** P4-21 (2026-11-22, results `bd597d7`, [results](../../experiments/2026-11-22-p4-21-lsl-replay/results.md)): one machine, localhost, unpaced replay. The clock correction between hosts and the real-time latency are not tested.
- **Done when:** the P4-21 hypothesis route runs between two hosts with the same pass checks (decisions = in-process on every trial, 0 faults), and a paced (real-time) replay of real streams reports the end-to-end latency (median, p95) against the collector latency budget.

#### P4-24 Frames-route trust decisions over LSL on real streams
- **Gap:** 187 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P4-21). Follow-up of P4-21.
- **Status:** `todo`. Low priority.
- **Depends on:** P4-21 (done); the M4-06 decode function (fresh decodes); CPU. Low priority.
- **Source:** P4-21 (2026-11-22, results `bd597d7`, [results](../../experiments/2026-11-22-p4-21-lsl-replay/results.md)): part B checks the `double64` frames transport only (bit-equal); the trust decisions over LSL used the hypothesis route only.
- **Done when:** real B2T '25 frame streams sent over LSL give trust decisions equal to the in-process frames route (and the batch harness) on every trial, with 0 faults.

#### P4-25 `text-nbest` CSV reader on a third-party file and real quoting cases
- **Gap:** 188 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P4-22). Follow-up of P4-22.
- **Status:** `todo`. Low priority.
- **Depends on:** P4-22 (done); a third-party decoder output file (for example a Kaggle submission writer); CPU. Low priority.
- **Source:** P4-22 (2026-11-22, results `bd597d7`, [results](../../experiments/2026-11-22-p4-22-nbest-readers/results.md)): our converter made the CSV and JSON Lines files, and the real texts have 0 commas, 0 double quotes and 0 edge spaces, so the real files do not exercise CSV quoting.
- **Done when:** `read_csv` parses a file that a third-party tool writes (its own column names through `id_col`, `text_col`, `score_col`) and real texts with commas, quotes and edge spaces, with an exact round trip and 0 conformance failures.

#### P4-26 Producer frame times from the device adapters to the trust layer
- **Gap:** 192 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P5-36). Follow-up of P5-36.
- **Status:** `todo`. Optional.
- **Serves:** research labs, small teams.
- **Depends on:** P5-36 (the integrity check, opt-in `frame_times=`); adapters with per-frame producer times; CPU. Optional.
- **Source:** P5-36 (2026-11-22, results `6f45faf`, [results](../../experiments/2026-11-22-p5-36-frame-order/results.md)): the stream-integrity check flags 240 / 240 transport faults and 0 / 160 real streams, but it is opt-in, and no device adapter passes `frame_times=` yet. The Willett data has no producer times of a live device, so I2 tested regular and jittered clocks only.
- **Done when:** each adapter that has per-frame producer times passes them as `frame_times=` to the trust layer; a replay test and a synthetic transport fault (reversed, reordered, duplicated frames) show flagged faults and unchanged decisions on valid streams; the device-support matrix notes which adapters pass times.

## P5. Trust layer to product grade
**Goal:** the trust layer works for one person, gives stated guarantees, records where each output came from, respects consent, and runs on the device.

### Deliverables
1. **Personalisation:** per-user calibration profiles; online recalibration from user corrections; drift detection. **Done (P5-01, 2026-11-16):** `fidetype.trust.personal` (`UserProfile`: hashed id, guard, calibration stats, `config_id` history, `consent_ref` placeholder, no text; `PersonalTrust`: tighten at once, re-calibrate only through `TrustGuardUpdater` / `GuardedUpdateLoop`) and `fidetype.trust.drift` (anytime-valid conformal and betting tests). T12 16-day replay: drift-triggered re-calibration on the guard risk needs 384 check labels vs 768 daily, same 15 commits and wrong-commit rate 0.0022 ([results](../../experiments/2026-11-16-p5-01-personal/results.md), [concept](../concepts/trust-personalisation.md)).
2. **Safety guarantees:** conformal risk control for a wrong-commit limit (finite-sample, as in M2-13); adaptive conformal for non-exchangeable streams; a written guarantee sheet per policy (what holds, under which assumptions). **Done 2026-11-16 (P5-02):** CRC / LTT drop-in (P14-03), precision LTT, joint fluent-wrong + precision LTT (one test), adaptive conformal on the drop-in guard (`guard.online`: ACI, ACI-window, window, bandit), and one uniform sheet per policy (`fidetype.guarantee-sheet/1.0`; [docs](../../docs/trust-guarantee.md) sections 10-12). Useful operating points still need a stronger decoder (M4-13, P11).
3. **Provenance ledger:** an append-only, hash-chained ledger: data → weights → calibration → each committed output. Licence flags (NC data cannot reach product weights; [licence rule](project-plan.md#licence-rule)). v0 done (M2-09, 2026-11-11): decision-level ledger, [provenance ledger](../concepts/provenance-ledger.md). **Done 2026-11-17 (P5-03):** `source` / `artifact` entries with SPDX licences and checked flags (`fidetype.trust.licence`); each decision carries `research_only` / `commercial_ok` / `product_ok`; a product artifact with NC inputs is refused; `LedgerView.lineage`, CLI `lineage`, `anchor`, `verify --anchor`; lineage spec files and the Collector option `ledger.lineage`. B2T '25 demo: full lineage of one committed word, 8 entries, verify PASS ([experiment](../../experiments/2026-11-17-p5-03-lineage/results.md); [docs](../../docs/provenance-and-privacy.md)). Open: gaps 47 (licence keys in NTS), 48 (signed anchor).
4. **Privacy and consent:** consent records referenced by `consent.ref`; the privacy processor (P3); data minimisation defaults (`data.derived = true`, no raw samples); deletion on request. **Done 2026-11-17 (P5-04):** `fidetype.trust.privacy` (`check_consent_ref`, `ConsentRecord` with purposes / expiry / withdrawal, `PrivacyPolicy`, `delete_profile`, `erase` with a deletion receipt); Collector processor `privacy` (keep / drop / hash per `meta` key, PII scan, text drop or HMAC; built-in minimal default); ledger redaction with tombstones under the new hash rule `salted-body` (the chain still verifies). Open: gap 49 (erasure in Collector output files).
5. **Neural-data law review** (information for design, not legal advice):

   | Jurisdiction | Instrument | Status in this wiki (checked 2026-11-17, P5-04) |
   |---|---|---|
   | Colorado | HB24-1058 (effective 7 Aug 2024) | Verified (primary) |
   | California | SB 1223 (effective 1 Jan 2025); AB 1883 workplace (chaptered 30 Sep 2026); SB 44 failed | Verified (secondary) |
   | Montana | SB 163 (effective 1 Oct 2025; genetic-data businesses only) | Verified (secondary) |
   | Connecticut | SB 1295 = PA 25-113 (effective 1 Jul 2026; CNS only) | Verified (secondary) |
   | Vermont | Act 101 (neurological rights, 18 May 2026); Act 145 (privacy act, effective 1 Jan 2028) | Verified (primary) |
   | Delaware | HB 380 (effective 1 Jan 2027) | Verified (secondary) |
   | Minnesota | SF 1240 | Pending, no action (primary) |
   | Chile | Ley 21.383, Art. 19 No. 1 (Oct 2021); Girardi v. Emotiv (Aug 2023) | Verified (primary / secondary) |
   | EU | GDPR Art. 9 (neural data not named); AI Act Art. 5 (from 2 Feb 2025); EDPS TechDispatch 2024 | Verified (primary / secondary) |
   | US federal | MIND Act S. 2925 (introduced 29 Sep 2025; study bill; no progress) | Verified (primary) |
   | UNESCO | Recommendation on the Ethics of Neurotechnology (adopted 11 Nov 2025) | Verified (primary) |

   Full table with dates, scopes, duties and confidence marks: [neural-data law table](neural-data-law.md) (**not legal advice**). The legal review stays P5-06 (externally blocked).

6. **On-device operation:** a quantised trust core in the C/Rust SDK; runs on a phone or a Raspberry-Pi-class board; no network needed.

### Exit criteria
- On B2T '25 and two other replay sets, the wrong-commit rate stays below the set limit at the stated confidence level.
- The ledger reproduces the full lineage of one committed word. **Met 2026-11-17 (P5-03)** on a B2T '25 subset replay ([report](../../experiments/2026-11-17-p5-03-lineage/results/lineage-report.md)).
- The trust core runs on-device with less than 20 ms per decision (our target).
- A legal review of the law table: **externally blocked** (needs a lawyer; user-owned).

**Effort:** 30–50 agent-days. **Depends on:** v0.1 trust core, P3 processors, P11 (better decoders make usefulness testable).

**Value-first link (2026-11-15):** [P14-03](#p14-03-trust-layer-as-a-drop-in-wrapper) packages the deliverable-2 guarantees as a drop-in wrapper for any decoder. P5 scope does not change.

### Open-gap items (added 2026-11-16)
The user asked that known gaps are fixed later, not forgotten. These items come from agent reports of 2026-11-16. Full list: [open gaps](open-gaps.md). No existing item moved.

#### P5-08 Non-vacuous precision bound ("when it types, it is right")
- **Gap:** 3 of the [open-gap list](open-gaps.md). Follow-up of P5-02.
- **Status:** `done`. Done 2026-11-18 (pre-registration `97a2fc4`, results `053e329`, [P5-02 rerun](../../experiments/2026-11-17-p5-02-precision-m4-13/results.md), [summary](m4-13-trust-reruns.md)): on held-out T15 val_eval with the M4-13 decoder, `calibrate(target_precision=0.5)` certifies commit_p 0.73; 104 commits, 17 wrong, precision 0.837 CP95 [0.751, 0.902]; P1-P3 pass. Targets 0.8, 0.9, 0.95 stay infeasible: follow-up P5-20 (gap 58).
- **Depends on:** M4-13 rerun ([plan](../../experiments/2026-11-17-p5-02-precision-m4-13/plan.md)) or a per-word commit; P11-01.
- **Source:** Commits `13f1853` (precision replay vacuous on T15 + T12) and `3dc84bf` (P5-02 done, open point).
- **Done when:** On held-out data of at least one public set, `calibrate(target_precision=)` certifies a commit threshold with at least one commit, and the measured error among commits is at or below the target at the stated confidence. Either the stronger M4-13 decoder (pre-registered rerun) or a per-word commit gives this. If neither does, the result says so with numbers, and the item stays open for P11 decoders.

#### P5-09 Drift test that detects a spread change at the same centre
- **Gap:** 11 of the [open-gap list](open-gaps.md). Follow-up of P5-01.
- **Status:** `done`. Commits `3def17e` (code + plan, before the run) and `9277177` (results), 2026-11-16: opt-in `ConformalDriftTest(spread=True)` adds bets `1 + eps (|2p - 1| - 1/2)`; false alarms 0.007 / 0.040 at 0.01 / 0.05; sd 1 -> 2 and sd 1 -> 0.5 detected in 200 / 200 (median 75 and 66 items); T12 permutation null pass. The small-mean-shift margin (S3, -0.25 sd) was missed: new gap P5-12. [Results](../../experiments/2026-11-16-p5-09-drift-spread/results.md).
- **Depends on:** P5-01.
- **Source:** Commit `9cb7a81` (P5-01 done; scale changes not detected).
- **Done when:** `ConformalDriftTest` (`src/fidetype/trust/drift.py`) can also bet on |p − 1/2| (or an equal spread statistic), so a change of spread at the same centre raises an alarm. A plan with the alarm criteria and the false-alarm check is committed before any test run. Synthetic results show the false-alarm rate at or below the level and detection of a pure spread change.

#### P5-10 PersonalTrust watches the guard risk
- **Gap:** 12 of the [open-gap list](open-gaps.md). Follow-up of P5-01.
- **Status:** `done`. Commits `3def17e` (code + plan) and `9277177` (results), 2026-11-16: opt-in `PersonalTrust(guard_risk_test=True)` (conformal test on the guard risk; default unchanged, documented in CHANGELOG and docs); P5-01 replay reproduced exactly; guard-risk alarms through `PersonalTrust` at the A2g items 697, 1,794, 2,159, 6,647. [Note](../../experiments/2026-11-16-p5-01-personal/results.md#p5-10-guard-risk-test-through-personaltrust-2026-11-16).
- **Depends on:** P5-01.
- **Source:** Commit `9cb7a81` (P5-01: on T12 the guard risk drifts, `p_top1` does not; test not wired into `PersonalTrust`).
- **Done when:** `PersonalTrust` can run the guard-risk drift test (`RiskDriftTest` on the guard risk), not only the `p_top1` test. The default behaviour stays the same and the guard-risk test is opt-in, or the change of default is documented in the changelog and the docs. A test and the T12 replay show the alarm path through `PersonalTrust`.

#### P5-11 Replay the online guards on T12 / T15 through the drop-in API
- **Gap:** 15 of the [open-gap list](open-gaps.md). Follow-up of P5-02.
- **Status:** `done`. Commits `3def17e` (plan) and `9277177` (results), 2026-11-16: `guard.online("aci" | "bandit", floor=False, lam_init=0.3)` gives the P15-04 numbers exactly (T12 35 / 20, q 0.9 37 / 22; T15 48 / 33, 55 / 39; bandit = aci in 20 / 20 seeds); item-level scores equal. Explained differences: the default offline floor (T12 19 / 11, T15 2 / 2), no exploration coins (the policy offers every no-commit item), window warm start (T12 27 / 17 vs 28 / 18). [Results](../../experiments/2026-11-16-p5-11-online-replay/results.md).
- **Depends on:** P5-02, P15-04.
- **Source:** Commit `3dc84bf` (P5-02 done; online guards not yet replayed via the drop-in API).
- **Done when:** A replay on T12 and T15 through the drop-in surface (`guard.online(...)`, `src/fidetype/trust/online_guard.py`) reproduces the P15-04 long-run wrong-commit numbers (which used the controllers directly), or the result explains each difference.

#### P5-12 Spread-aware drift test without the small-shift cost
- **Gap:** 19 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P5-09). Follow-up of P5-09.
- **Status:** `todo`.
- **Depends on:** P5-09 (done).
- **Source:** Commit `9277177` (P5-09 S3: with `spread=True` a -0.25 sd mean shift is detected in 0.445 of runs vs 0.61 without; margin 0.10 missed). On T12 the spread bets also lose 2 of 4 guard-risk alarms.
- **Done when:** a spread-aware variant (for example prior weights that favour the mean bets, or a separate spread test with its own level) keeps the false-alarm level, detects sd 1 -> 2 in at least 95 % of runs, and loses at most 0.10 of detected share at -0.25 sd and at most 25 % median delay at -0.5 / -1.0 sd against the P5-01 test, in a plan committed before the run. Only then may the default of `spread` change (documented in the changelog).

#### P5-13 Licence flags in the stream and in trust decisions (FEP)
- **Gap:** 47 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P5-03). Follow-up of P5-03.
- **Status:** `done`. Done 2026-11-17 (code `29d17d0`): [FEP-0010](../../spec/feps/0010-data-licence-keys.md), NTS 1.0 RC4 amendment 6. `meta` keys `data.licence` (SPDX id, non-empty string) and `data.research_only` (boolean; MUST be true for a licence without commercial use, MET-12); `trust_decision.input.research_only` (audit key, TD-15). Registry 54 keys (`spec/semconv/attributes/data.yaml`, `trust-decision-input.yaml`). Python, TypeScript, Rust validators check the types; vectors V98 (accept), V99, V100 (reject); 351 vectors. Parity Python = TypeScript = Rust 351/351, kit 36/36, 28,217 fuzz mutants (seeds 1-3, `--n 30`), 0 differences. Producers: the six adapters (emg2qwerty, kt_semg, toronto_semg, willett_handwriting, spanishbcbl_meg (custom `spanishbcbl.licence` dropped), b2t25) via `fidetype.trust.licence.licence_meta`; `track_meta` for the benchmark tracks (test: adapter keys = track keys). Ledger: a stream with the keys becomes a `source` entry; context `stream_sources`; `verify` recomputes the flags. Trust layers: `StreamingTrustLayer` (stream keys + ledger lineage), `IntentTrustLayer`, `ControlTrustLayer`, collector `guard` copy `research_only`. Decisions in the FEP: spelling `licence`; key inside `input` (no schema change); validators check types only. New gaps 56 = P5-18 (LIC-3), 57 = P5-19 (LIC-2).
- **Depends on:** P5-03 (done); a FEP (semantic conventions, MET-10).
- **Source:** P5-03: licence flags live in the provenance ledger only. A producer has no registered `meta` key to declare the data licence (the SpanishBCBL adapter writes the custom key `spanishbcbl.licence`), and an emitted `trust_decision` does not carry `research_only`, so a consumer that reads only the stream or the decision log cannot see that an output depends on NC data.
- **Done when:** a FEP adds optional keys (for example `data.licence` (SPDX id) and `data.research_only`) to the registry with accept / reject vectors in the three SDKs, the reference adapters write them, the ledger reads them into `source` entries, and the trust layers copy `research_only` into `trust_decision` (an audit key, TD-13), with Python = TypeScript = Rust on the vectors.

#### P5-14 Signed or external anchor of the ledger head
- **Gap:** 48 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P5-03). Follow-up of P5-03, M2-09.
- **Status:** `done`. Done 2026-11-17 (code `b268203`): module `fidetype.trust.anchor` (Ed25519 through the optional extra `[sign]` = `cryptography`, Apache-2.0 OR BSD-3-Clause; in `[dev]`): `generate_key`, `sign_anchor`, `check_signature`, `verify_anchored` (signature + key id, ledger id, anchored entry seq + hash, head = anchor unless `allow_growth`, whole chain). Anchor schema `fidetype.ledger-anchor/1.0`. CLI `keygen` (never overwrites; private key owner-only), `anchor --sign-key-file | --sign-key-env`, `verify --anchor --public-key [--allow-growth]`; a signed anchor without a public key fails. Test: a rewritten ledger with a recomputed chain passes `verify` alone but fails against the signed anchor; a re-signed anchor with another key fails. Redaction keeps anchors valid. External option documented (RFC 3161 via `openssl ts`, second host); no network call. Keys: throwaway keys in tests only. Docs section 4.1 / 4.2. New gap 54 = P5-16.
- **Depends on:** P5-03 (done).
- **Source:** P5-03 added `anchor` / `verify --anchor`, but the anchor is a plain JSON file. A person who can rewrite the whole ledger and the anchor file can recompute the chain (tamper-evident, not tamper-proof).
- **Done when:** the anchor can be signed (for example Ed25519 with a key outside the ledger) or sent to an external store (an RFC 3161 timestamp or a second host), `verify` checks the signature, and a test shows that a rewritten ledger with a recomputed chain fails against a signed anchor.

#### P5-15 Erasure in Collector output files
- **Gap:** 49 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P5-04). Follow-up of P5-04.
- **Status:** `done`. Done 2026-11-17 (code `b268203`): module `fidetype.trust.erasure`. Collector: `privacy` option `subject_index` (one line per stream: session + `h:` HMAC code of `subject.id`, never the raw id; needs `key_env`) and `jsonl` path placeholder `{session}` (one file per stream / decision session). `erase(outputs=, output_templates=, subject_indexes=, index_key=, sessions=)` and CLI `erase --output --output-template --subject-index --index-key-env --sessions-env`: per-session files deleted, decision-log and `os_text` lines of the subject's sessions removed (other lines byte for byte), NTS stream files deleted when the header subject matches, index lines removed; atomic rewrite. Receipt `fidetype.deletion-receipt/1.1` `outputs`: per file position, form, action, counts, SHA-256 before / after, `nts-conform` before / after; no path, no session id, no subject id; exit 1 if a rewritten file lost conformance. Test: a two-pipeline run (3 streams, 2 subjects) -> erase one subject -> remaining decision log, per-session files and stream file pass `nts-conform check` at the same verdict. Docs section 8. New gap 55 = P5-17.
- **Depends on:** P5-04 (done).
- **Source:** P5-04: `erase` deletes the profile and redacts the ledgers, but the Collector's other outputs (JSON Lines decision logs, passthrough NTS streams, the `os_text` stub log, metrics files) are plain files without a hash chain or a subject index; they are not reached.
- **Done when:** an erasure request can also remove a subject's items from the Collector output files (by `session` / pseudonymous subject, with a receipt entry per file), or the Collector can write those outputs in a redactable form; a test erases one subject from a pipeline run's outputs and the remaining files still pass `nts-conform check`.

#### P5-16 Signed anchors written by the Collector and the trust layers
- **Gap:** 54 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P5-14). Follow-up of P5-14.
- **Status:** `done`. Done 2026-11-17 (code `29d17d0`): `fidetype.trust.anchor.AutoAnchor(ledger, key, dir, every_n=, every_s=, on_stop=, keep=)` (hooks `ProvenanceLedger.on_append`; timer checked at each entry and each collector loop step) writes Ed25519-signed `anchor-<seq>.json` files into a separate directory (atomic; older anchors unchanged); `load_private_key(key_env= | key_file=)`. Collector `trust` option `ledger.anchor` (`dir`, `key_env` or `key_file`, `every_n`, `every_s`, `on_stop`, `keep`); the key never goes into the config, a log or the metrics (metrics `anchors`: count, newest seq, key id). `verify --anchor <dir> --allow-growth --public-key` checks the newest anchor. Test: a rewrite after the last manual anchor passes the manual anchor but fails against the automatic one (API and CLI); a collector run writes anchors and the key is in no output. Tests skip without `cryptography`. Docs section 4.1a, FEP-0006 section 4.
- **Depends on:** P5-14 (done).
- **Source:** P5-14: an anchor is signed only when the operator runs `anchor --sign-key-file` (or calls `sign_anchor`). The Collector `trust` processor ledger, `StreamingTrustLayer(ledger=)` and live loops never write a signed anchor, so between two manual runs a rewrite of the newest entries is not covered.
- **Done when:** the Collector `trust` ledger option (and the Python API) can write a signed anchor on stop and every N entries or T seconds (key from an environment variable, never in the config file), the anchors go to a separate file or directory, `verify --anchor` can check the newest one with `--allow-growth`, and a test shows that a rewrite of entries written after the last manual anchor fails against the automatic one.

#### P5-17 Collector refuses an input-event file that would mix streams
- **Gap:** 55 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P5-15). Follow-up of P5-15, P3-04.
- **Status:** `done`. Done 2026-11-17 (code `29d17d0`): the config check refuses (ConfigError naming the reasons) a `jsonl` exporter of input events without `{session}` when its pipelines can carry more than one stream (several receivers, several file paths, a websocket or LSL receiver, or one exporter shared by two pipelines); a decision log is not affected. Reason in docs/collector.md and FEP-0006 section 6 rule 5. Example configs show `{session}`; the P3-04 bench writes `out/streams/{session}.nts.jsonl`. Tests: refused for each case, accepted with `{session}` and for one stream.
- **Depends on:** P5-15 (done).
- **Source:** P5-15: a `jsonl` exporter of input event types without `{session}` writes all streams of a pipeline into one file, one header after the other, with no stream id. Such a file is not one NTS stream, and an erasure can only delete it whole (it reads the first header only).
- **Done when:** the config check refuses (or warns, with a reason in the docs) an input-event `jsonl` exporter without `{session}` when its pipeline can carry more than one stream (several receivers, several file paths, a websocket or LSL receiver), the example configs use `{session}`, and a test covers both cases.

#### P5-18 Collector policy for research-only decisions
- **Gap:** 56 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P5-13). Follow-up of P5-13.
- **Status:** `done`. Done 2026-11-18 (code `9bccef8`): every collector exporter takes `refuse_research_only = true` (FEP-0006 section 4 rule 6; FEP-0010 LIC-3 answered). It drops decisions (trust, intent, control) with `input.research_only = true` (counter `research_only_refused`); a decision without the key has an unknown licence: `unknown_licence = "refuse"` (default) drops it (counter `licence_unknown_refused`), `"pass"` exports it. One log line at the first drop of each kind (no text, no session id). Input events pass; the option on a `jsonl`/`stdout` exporter without a decision type is a config error. Default (option absent) unchanged. `fidetype.collector.exporters.LicenceGate`, `Exporter.deliver`. Test (`tests/test_research_only_policy.py`): a CC-BY-NC stream types nothing through `os_text` (the decision log keeps all); a CC0 stream types the same text as without the option; unknown rule both ways. Docs: docs/collector.md, docs/provenance-and-privacy.md section 2, examples/collector/collector.toml. New gap 61 = P5-22 (input events).
- **Depends on:** P5-13 (done).
- **Source:** FEP-0010 open question LIC-3: every reference trust layer writes `trust_decision.input.research_only`, but no collector exporter can refuse such decisions. A product build (for example the `os_text` exporter) could type output that depends on non-commercial data.
- **Done when:** an exporter option (for example `refuse_research_only = true`, FEP-0006) drops or blocks research-only decisions with a counter and a log line, a decision without the key is treated by a documented rule (unknown), and a test shows that a CC-BY-NC stream types nothing through a product exporter while a CC0 stream types as before.

#### P5-19 Advisory check: data.research_only agrees with data.licence
- **Gap:** 57 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P5-13). Follow-up of P5-13.
- **Status:** `done`. Done 2026-11-18 (code `9bccef8`): NTS 1.0 RC4 amendment 7. Advisory check `NTS-LICENCE-MATCH` (MET-12) in Python, TypeScript and Rust: `data.research_only = false` with a Creative Commons id with `NC` or `LicenseRef-unknown` (ASCII, without case) is a warning, never a reject; other ids are silent. One table: `fidetype.trust.licence.no_commercial_id` (pattern of `terms`), mirrored by TS `noCommercialId` and Rust `checks::no_commercial_id`; the same test lists in the three SDKs. Vectors V101, V102 (NPZ), V103 (lower case, -IGO): accept with the warning; V104 (CC-BY-SA-4.0): accept, no warning; 355 vectors (v0.1 104). C.1 MET-12 row; rule-map.json regenerated (levels.json unchanged); semconv registry. Parity: Python = TypeScript = Rust 355/355, kit 36/36, 28,487 fuzz mutants (seeds 1-3, `--n 30`), 0 differences. FEP-0010 LIC-2 answered (decision 4).
- **Depends on:** P5-13 (done).
- **Source:** FEP-0010 open question LIC-2: the validators check only the types of `data.licence` and `data.research_only`. A stream with `data.research_only = false` and `data.licence = "CC-BY-NC-4.0"` breaks MET-12 but passes.
- **Done when:** an advisory check (a warning, never a reject; like NTS-MODALITY-MATCH) flags `data.research_only = false` with a licence id that has `NC` (and `LicenseRef-unknown`) in Python, TypeScript and Rust with the same warning, with accept vectors that pin the warning, and three-SDK parity.

#### P5-20 Certified precision at a useful target (0.8 or more)
- **Gap:** 58 of the [open-gap list](open-gaps.md) (added 2026-11-18 by the M4-13 reruns). Follow-up of P5-08.
- **Status:** `todo`.
- **Depends on:** P11-01 decoders, or a per-word commit, or more calibration items.
- **Source:** [P5-02 rerun on M4-13](../../experiments/2026-11-17-p5-02-precision-m4-13/results.md): target 0.5 is certified (104 commits), but 0.8, 0.9 and 0.95 are infeasible. The LTT part has 271 items; 0.8 is feasible in 42 of 1000 resampling draws. Held-out precision at commit_p 0.8 is 0.855 on 69 commits, so the limit is the sample size as much as the decoder.
- **Done when:** on held-out data of at least one public set, `calibrate(target_precision=0.8)` (or higher) certifies a threshold with at least 20 held-out commits, the held-out error among commits is at or below 1 - target, and the null controls pass. The plan is written before the run. If no decoder or commit unit gives this, the result says so with numbers.

#### P5-21 Trust config_id independent of the decode-function label
- **Gap:** 59 of the [open-gap list](open-gaps.md) (added 2026-11-18 by the M4-13 reruns). Follow-up of P15-06.
- **Status:** `done`. Done 2026-11-18 (code `e788029`): `calibrate()` writes the recipe field `decoder` of a custom `decode_fn` as `custom:<qualname>` (no module path) and adds `decoder_id = <decoder_name>@<decoder_version>`. Decision: the module path depends on how the script is loaded, so it stays out of the content hash; the user-given name and version are the stable identity. New ids for guards with a custom `decode_fn` (id version bump, CHANGELOG); saved guard files keep their bytes and ids; `calibrate(decoder_label="module")` reproduces an old id. Test: the same script run as `__main__` and imported as `p1506_run` gives one id (and two ids with the old label).
- **Depends on:** none (CPU, code).
- **Source:** [F2 rerun V4](../../experiments/2026-11-17-f2-m4-13/results.md#v4-on-t12-why-the-ids-differ-exploratory-check-not-pre-registered): the recipe field `decoder` stores the Python module path of a custom decode function (`custom:__main__.calibrate_arm.<locals>.fn` vs `custom:p1506_run.calibrate_arm.<locals>.fn`). The same T12 configuration gets a different `config_id` when the script is imported instead of run (8 of 8 arms; equal after relabelling).
- **Done when:** a decision is written down (with a reason) on which recipe fields enter the content hash, the `config_id` of one configuration no longer depends on how the defining script is loaded (or a stable user-given decoder name is required), old ids still verify (or a migration note says why not), and a test loads the same decoder as `__main__` and as a module and gets one id.

#### P5-22 Licence gate for input-event exporters
- **Gap:** 61 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P5-18). Follow-up of P5-18.
- **Status:** `done` (2026-11-18, code `a38fe87`): yes, per stream by the header keys (FEP-0010 decision 6, FEP-0006 section 4 rule 6); a refused stream writes no file; test `tests/test_input_event_licence_gate.py`.
- **Depends on:** P5-18 (done).
- **Source:** P5-18: `refuse_research_only` acts on decisions only. A `jsonl` or `stdout` exporter of input events (header, frames) copies a research-only stream (`data.research_only = true` in its header) unchanged, for example into a product data store.
- **Done when:** a decision is written down (with a reason) whether an input-event exporter can refuse a research-only stream (by its header keys, per stream, with the unknown rule of P5-18), and, if yes, the option works per stream (header and all its events), with counters and a test (a CC-BY-NC stream writes no file, a CC0 stream writes the same file as before).

#### P5-23 Learned commit-confidence score for the drop-in guard
- **Gap:** 67 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P14-23). Follow-up of P14-23, P14-03.
- **Status:** `done` (2026-11-18, code + pre-registration `52ef14c`, [results](../../experiments/2026-11-18-p5-23-learned-confidence/results.md)): pre-registered T15 `val_eval` 701: learned 2.64 vs p_top1 2.23, paired diff +0.42 [0.07, 0.78] > half-width 0.35, "learned beats current"; 113 commits / 10 wrong (0.0143, CP95 [0.0069, 0.0261]) vs 104 / 17; AUROC 0.889 vs 0.834; T12 replication 1.87 vs 1.27, +0.60 [-0.18, 1.40], no clear difference; controls 0/300 on both sets. Below the no-BCI 4.02 (P14-23 stays open). New gaps 73 = P5-25, 74 = P5-26.
- **Depends on:** none (CPU, code + one pre-registered T15 replay).
- **Source:** P14-23 [analysis](safe-wpm-bottleneck.md) (exploratory): the guard's `p_top1` has AUROC 0.83 for "top-1 exactly right" on T15 `val_eval`; it commits only 87 of 257 exactly-right sentences. A logistic score on n-best and decoder features (no LLM) has AUROC 0.87 and gives safe WPM 3.50 (168 commits, 30 wrong) against 2.23; with 2 LLM features 4.54. The guard risk is informative but unused by the commit gate (`max_guard_risk` 1.0).
- **Done when:** `calibrate()` can fit an optional commit score on a fit part that is disjoint from the LTT part (three-way split in the sheet), the config hash covers the score, and a pre-registered T15 replay (calibrate on `val_select`, decide `val_eval`) compares it with the current `p_top1` guard on safe WPM v0.1, wrong-commit rate and controls, with the result written up either way.

#### P5-24 Certified prefix commits in the trust guard
- **Gap:** 68 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P14-23). Follow-up of P14-23, P5-08.
- **Status:** `done` (2026-11-18; code + pre-registration `00a64ba`, [results](../../experiments/2026-11-18-p5-24-prefix-commits/results.md)). `calibrate(confidence="learned", commit_unit="prefix")`; T15 under the PROPOSED safe-wpm v0.2: 4.87 [4.43, 5.30] vs 2.64 (sentence), prefix beats sentence; v0.1 0.53 literal / 1.03 complete-only; T12 4.76 vs 1.87. Follow-ups: P14-28, P5-27.
- **Depends on:** P14-26 (metric v0.2), P5-23 (score fitting). CPU.
- **Source:** P14-23 [analysis](safe-wpm-bottleneck.md) (exploratory): right prefixes of the T15 top-1 sentences hold 57.5 % of all words, exactly-right sentences 33.8 %. A learned, monotone prefix confidence with LTT on the wrong-prefix loss gives about 5.4 safe WPM (505 prefix commits, 23 wrong). A posterior from the 10-best alone is not feasible (shared prefixes get mass 1.0).
- **Done when:** the guard can commit the longest prefix whose confidence passes a certified threshold (loss: the committed prefix is not a prefix of the truth; bound on the rate over all trials), the decision event says how many words are committed, the null controls cover prefixes, and a pre-registered T15 replay reports safe WPM v0.2 next to v0.1.

#### P5-25 Online re-calibration for a guard with a learned commit score
- **Gap:** 73 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P5-23). Follow-up of P5-23, P5-02.
- **Status:** `todo`.
- **Depends on:** P5-23 (done). CPU.
- **Source:** P5-23 ([results](../../experiments/2026-11-18-p5-23-learned-confidence/results.md)): `TrustGuard.online(...)` (ACI, window, bandit) moves a threshold on `p_top1`; for a guard with `confidence="learned"` it raises a ValueError.
- **Done when:** the online methods move the threshold of the learned score (the score itself stays frozen), their policy sheets state it, and a replay on T15 / T12 with the learned guard reports the online guarantee and safe WPM next to the offline learned guard.

#### P5-26 Learned commit score with the precision and hallucination bounds
- **Gap:** 74 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P5-23). Follow-up of P5-23, P5-02, P15-06.
- **Status:** `todo`.
- **Depends on:** P5-23 (done). CPU (LLM arm about 3 GB RAM).
- **Source:** P5-23: `calibrate(confidence="learned")` refuses `target_precision=`, `grounding=` and `llm=` (ValueError). The precision bound and the joint fluent-wrong test choose `commit_p` on `p_top1`.
- **Done when:** the precision LTT and the joint test can run on the learned score (same three-way split: score fit on the fit + policy-grid items, ordering and test on the LTT part as now), with unit tests of the bounds and one T15 replay that states the bounds with the learned score.

#### P5-27 Word-by-word streaming prefix commits within a trial
- **Gap:** 76 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P5-24). Follow-up of P5-24, P3-06.
- **Status:** `done` (2026-11-19; code + pre-registration `5f74c2f`, results `72be974`, [results](../../experiments/2026-11-18-p5-27-streaming-prefix/results.md)). `fidetype.trust.stream_commit`; metric: the PROPOSED several-commits extension of the PROPOSED v0.2 (proposal section 7). T15: stream 2.34 [2.11, 2.57] vs one-commit prefix guard 4.67 [4.26, 5.07], Δ −2.32 [−2.63, −2.02]: single beats stream (safe: 5 / 701 wrong; certified; controls pass). Right words about 10 s earlier. Follow-up: P5-28.
- **Depends on:** P5-24 (done); a metric rule for several commits per trial (v0.3, after the P14-26 decision). CPU.
- **Source:** P5-24 ([results](../../experiments/2026-11-18-p5-24-prefix-commits/results.md)): the prefix guard decides once per trial at the end. On T15 it commits 1,073 of the 2,688 words in the right prefixes of the top-1 texts.
- **Done when:** a streaming guard can commit further words of the same utterance as evidence arrives (each commit certified under one loss that covers all commits of a trial), the decision events chain the commits, and a pre-registered T15 replay reports safe WPM next to the one-commit prefix guard.

#### P5-28 Hybrid streaming and end-of-trial prefix guard
- **Gap:** 92 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P5-27). Follow-up of P5-27.
- **Status:** `done` (2026-11-19; pre-registration + code `e3cb0cb`, results `c359eb6`, [results](../../experiments/2026-11-19-p5-28-hybrid-prefix/results.md)). `fidetype.trust.hybrid_commit`: mid-trial commits with the P5-27 streaming score (λ_mid 0.99, fixed) + the P5-24 end decision (λ_end 0.94, certified jointly on the trial loss). T15 (PROPOSED v0.2 + reading cost + several-commits rule): hybrid 4.89 [4.49, 5.27] vs one-commit guard 4.67 [4.26, 5.07], Δ +0.22 [+0.14, +0.31]: hybrid beats single (18 / 701 wrong; certified; controls pass). Median latency of right words 3.85 s vs 11.20 s. Caution: λ_mid came from P5-27 on the same certify items; the Bonferroni sensitivity gives no clear difference (4.63). T12 moved to P5-29; scorer issue P5-30.
- **Depends on:** P5-27 (done); local M4-13 log-probs and P5-27 checkpoint decodes; for T12 a loader that stays under 1.5 GB. CPU.
- **Source:** P5-27 ([results](../../experiments/2026-11-18-p5-27-streaming-prefix/results.md)): one LTT threshold over about 39 checkpoints per trial is strict (0.99 vs 0.94); the streaming guard commits about 1.7 words at a median 31 % of the trial and never extends a commit at the end (0 complete commits). It gets 2.34 against 4.67 for the one-commit guard, but right words appear about 10 s earlier. T12 was not run (shared loader peak 2,340 MB).
- **Done when:** a guard that combines mid-trial streaming commits with an end-of-trial prefix decision (for example the P5-24 decision at the end, or separate mid / end thresholds on a 2-D LTT grid), certified jointly on the trial loss, is compared in a pre-registered T15 replay with the one-commit prefix guard on safe WPM (proposed v0.2 + reading cost) and on commit latency; plus the T12 replication on a lighter loader, or a recorded reason why it cannot run.

#### P5-29 T12 replication of the streaming and hybrid prefix guards
- **Gap:** 95 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P5-28). Follow-up of P5-27, P5-28.
- **Status:** `todo`.
- **Depends on:** P5-27, P5-28 (done); T12 v2 log-probs (causal decoder); a T12 loader under the memory cap (the shared loader peaked at 2,340 MB in P5-24); CPU, a few hours for the streaming decode.
- **Source:** P5-28 ([results](../../experiments/2026-11-19-p5-28-hybrid-prefix/results.md)): on T15 the hybrid beats the one-commit guard by +0.22 safe WPM, but λ_mid 0.99 came from P5-27 on the same certify items, and with δ split over three λ_mid values the gain disappears. No T12 checkpoint views exist.
- **Done when:** a pre-registered T12 replay (new streaming decode of the T12 v2 log-probs with its own frame timing; streaming score fit; **λ_mid = 0.99 fixed before any T12 number**; λ_end certified jointly) reports stream, hybrid and one-commit safe WPM (proposed v0.2 + reading cost) and commit latency, or a recorded reason why it cannot run.

#### P5-30 safe_wpm: refuse "certified" for an infeasible guarantee when the policy commits
- **Gap:** 96 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P5-28).
- **Status:** `done` (2026-11-19, code `296fb88`; `not-certified` for `feasible: false` with commits, v0.1 and v0.2; rule 6 in docs/safe-wpm.md; test; 100 committed safe-WPM blocks re-checked: no label changes, leaderboard fresh).
- **Depends on:** nothing. CPU.
- **Source:** P5-28 ([results](../../experiments/2026-11-19-p5-28-hybrid-prefix/results.md), Bonferroni sensitivity): `fidetype.benchmark.safe_wpm.certification` reads `feasible: false` as "the policy never commits" and still sets `certified`. The first `calibrate_hybrid` kept mid-trial commits when no λ_end passed, and the scorer labelled that uncertified policy `certified`. `calibrate_hybrid` is fixed (`c359eb6`); the scorer still trusts the flag.
- **Done when:** `safe_wpm` gives a non-certified status (or refuses) when the guarantee is infeasible and at least one trial is committed, with a test; existing entries re-checked.

#### P5-31 Null control for offers
- **Gap:** 136 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P14-41). Follow-up of P14-41, P14-03.
- **Status:** `done` (2026-11-21; code `534feae`, re-check `367ad72`, [results](../../experiments/2026-11-21-p5-31-offer-control/results.md), [docs](../../docs/trust-guarantee.md) section 5a). The sheet reports the offer rate next to the commit rate on each null control. Rule `offer_control`: null offer rate <= 0.5 x real offer rate, and (null offers <= floor(0.05 n) or one-sided Fisher exact p <= 0.05). `calibrate(offer_control="warn" | "refuse" | "off")`, default `"warn"`; `recheck_offer_control` for a saved guard. All four packaged guards fail (warn mode, no status changes, commit counts equal the sheets): `willett-hw` frame-shuffled 297 / 300, `willett-hw` LM 289 / 300, `t15-m4-13` uniform and frame-shuffled 300 / 300 (still certified for commits), `kt-semg-lda` uniform 300 / 300 and user nulls 173 / 173. Evidence 2026-11-21 (P14-49, `dcc344b`): gate C5 lowers the time-shuffled offers from 13 / 80 to 2 / 80; frame-shuffled stays 77 / 80.
- **Follow-up:** gap 152 = [P5-33](#p5-33-offer-policy-that-withholds-on-no-evidence-input-and-the-offer-control-default) (policy that withholds on no-evidence input, then the default), gap 153 = [P14-56](#p14-56-offer-control-result-in-the-packaged-manifests-and-model-cards) (cards), gap 150 = [P14-54](#p14-54-frame-order-aware-no-signal-gate-or-offer-check-for-willett-hw) (`willett-hw` frame order).
- **Evidence:** 2026-11-20 (P14-48, results `28870eb`): LM-readout guard offer rates on null inputs: frame-shuffled 77 / 80 (equal to real input), time-shuffled 13 / 80, zero 0 / 80, uniform 0 / 80.
- **Depends on:** P14-41 (done). CPU.
- **Source:** P14-41 ([results](../../experiments/2026-11-20-p14-41-willett-guard/results.md)): the offer-only `willett-hw` guard offers on 77 / 80 frame-shuffled test inputs, as often as on real input (77 / 80), and the offered top-1 is never exact. The drop-in null controls of `fidetype.trust.calibrate` count only commits.
- **Done when:** the guarantee sheet reports the offer rate on the null controls next to the commit rate, with a stated rule (for example: the offer rate on frame-shuffled input clearly below the real offer rate, or a warning on the sheet), a test, and a rerun on `willett-hw` and one other packaged guard.

#### P5-32 Memory bound for the vector beam search and the LM caches
- **Gap:** 137 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P14-41). Follow-up of P14-41.
- **Status:** `done` (2026-11-21; commit `5a44e1b`). The `search="vector"` prefix caches and the LM row caches are bounded, with exact results (test). Memory test on a long near-uniform input (T = 10,000, V = 98): push peak 59 MB -> 22 MB, linear in T.
- **Depends on:** P14-41 (done). CPU.
- **Source:** P14-41 ([results](../../experiments/2026-11-20-p14-41-willett-guard/results.md)): the loop prefix search (`PREFIX_CACHE_MAX`) and `ctc_forced_align_many` (groups, frame-wise scores) are now bounded and exact. The `search="vector"` path keeps `lm_score` / `lm_arr` for every prefix that entered the beam, and the LM row caches also grow with T.
- **Done when:** both paths have bounded per-utterance memory with exact results (test), and a CI test decides a long near-uniform input (for example T = 10,000, V = 98) under a stated memory limit.

#### P5-33 Offer policy that withholds on no-evidence input, and the offer-control default
- **Gap:** 152 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P5-31). Follow-up of P5-31.
- **Status:** `done` (2026-11-21; pre-registration `a7abc11`, code and results `9ce8006`, [results](../../experiments/2026-11-21-p5-33-withhold/results.md)). `t15-m4-13` passes the offer null control with the offer gate `coherence >= 0.1869751254594959` (a frame-order feature), on by default: E1 uniform 0 / 300 and frame-shuffled 0 / 300 offers (were 300 / 300); E2 54 LTT commits, unchanged; E3 real LTT offers 212 / 271 (limit >= 185; 217 before); E4 val_eval 104 commits (identical to P14-05), offers 568 / 597 (limit >= 508), nulls 0 / 300 and 0 / 300. `kt-semg-lda`: negative. No candidate passed the selection (`char_lm_best` 100 / 108 user nulls against 103 / 108 real; `char_lm_best` AND margin 0 / 300 uniform but 100 / 108 user nulls); info-only evaluation FAIL (uniform 289 / 300, user nulls 165 / 173, real 63 / 65). Reason: the user nulls are real key windows at random times; key accuracy 0.248.
- **Default decision:** the orchestrator recommends to keep `offer_control="warn"` for now (1 of 4 packaged guards passes) and to revisit after gap 150. The decision itself moved to the user's decision list in HANDOFF.md and is tracked there.
- **Follow-up:** gap 155 = [P5-34](#p5-34-offer-gate-for-kt-semg-lda) (`kt-semg-lda` part, split from this gap); gap 150 = [P14-54](#p14-54-frame-order-aware-no-signal-gate-or-offer-check-for-willett-hw) (`willett-hw`, still open).
- **Depends on:** P5-31 (done); gap 150 = [P14-54](#p14-54-frame-order-aware-no-signal-gate-or-offer-check-for-willett-hw) for `willett-hw`; local calibration inputs of `t15-m4-13` and `kt-semg-lda`. CPU.
- **Source:** P5-31 re-check (2026-11-21, `367ad72`, [results](../../experiments/2026-11-21-p5-31-offer-control/results.md)): every packaged guard fails the offer null control. `t15-m4-13` offers on 300 / 300 uniform and 300 / 300 frame-shuffled inputs (real 217 / 271). `kt-semg-lda` offers on 300 / 300 uniform inputs and 173 / 173 user nulls (real 65 / 65). `willett-hw` offers on 297 / 300 and 289 / 300 frame-shuffled inputs (real 40 / 40). The mode is `warn`, so no status changed.
- **Note (2026-11-21):** the `willett-hw` part is now met by gap 150 (P14-54, `2c0692f`): 3 of 4 packaged guards pass the offer null control (only `kt-semg-lda` fails, gap 155).
- **Overlap:** the `willett-hw` part has the same done-when as gap 150 (P14-54) and closes there. This item keeps `t15-m4-13` and `kt-semg-lda` (they fail on uniform input too, so they need a gate before the offer list) and the default decision.
- **Done when:** each packaged guard has a policy (for example a no-signal gate before the offer list) under which `recheck_offer_control` passes, or numbers say why not; then a recorded decision whether `offer_control="refuse"` becomes the default, with a test.

#### P5-34 Offer gate for kt-semg-lda
- **Gap:** 155 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P5-33; split from gap 152). Follow-up of P5-33.
- **Status:** `todo`.
- **Depends on:** P5-33 (done); a stronger key decoder (key accuracy 0.248) or a feature that reads the key order across keys; local KT-sEMG calibration inputs. CPU.
- **Source:** P5-33 (2026-11-21, pre-registration `a7abc11`, code and results `9ce8006`, [results](../../experiments/2026-11-21-p5-33-withhold/results.md)): no candidate gate passed the calibration-only selection for `kt-semg-lda` (`char_lm_best`: 100 / 108 user nulls against 103 / 108 real; `char_lm_best` AND margin: 0 / 300 uniform but 100 / 108 user nulls). Info-only evaluation FAIL: uniform 289 / 300, user nulls 165 / 173, real 63 / 65. The user nulls are real key windows at random times, and the key accuracy is 0.248.
- **Done when:** a pre-registered gate, chosen on calibration data only, passes the P5-31 offer null control against both the uniform and the user-null controls, keeps at least 0.85 x the real LTT offers, and leaves the commits unchanged. Then refresh the manifest `offer_control` block from the new re-check.

#### P5-35 Native calibrate path for external per-prefix scores
- **Gap:** 165 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-16). Follow-up of P11-16, P5-24.
- **Status:** `done` (2026-11-21; commit `c1f14e0`, [results](../../experiments/2026-11-21-p5-35-external-prefix-score/results.md); CI `tests` run 44930128741 green). Gap 165 closed. `fidetype.trust.FrozenPrefixScore` + `calibrate(..., commit_unit="prefix", prefix_score=...)`; the score digest enters the `config_id`; `ft.load(path, prefix_score=...)` refuses a missing or other score. LX-FL reproduced exactly: threshold 0.86; LTT record equal (459 items, risk 0.03268, p 0.04882); controls 0 / 5 / 0 of 300; 671 commits (592 prefix), 46 wrong; same decisions 1,221 / 1,221 for real, time-shuffled and zero EMG; `config_id` `tcfg-618d4ca57bb9326b`. The 4 old guard types keep their `config_id` and dicts (vs `9e039c7`). The P5-31 offer null control fails in warn mode (shuffled 60 / 300 offers vs real 157 / 459), as for the other EMG guards. Tests: `tests/test_trust_external_prefix_score.py` (8 fast + 1 local). Docs: docs/trust-guarantee.md 10b.1; CHANGELOG.
- **Depends on:** P11-16 (done); `calibrate(commit_unit="prefix")` (P5-24); CPU.
- **Source:** P11-16 ([results](../../experiments/2026-11-21-p11-16-emg-prefix-confidence/results.md)): LX-FL and LS-FL are certified outside `calibrate` (library function `ltt_prefix_threshold` and the library controls). So they have no `TrustGuard` file, no frame temperature, no guard-risk gate and no `config_id`.
- **Done when:** `calibrate` accepts a frozen external per-prefix score, and LX-FL is reproduced through it (same threshold and decisions) with tests, giving a `TrustGuard` with a `config_id`.

#### P5-36 Frame-order integrity check in the trust layer
- **Gap:** 181 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P14-57). Follow-up of P14-57, P5-31.
- **Status:** `done` (2026-11-23, closed by user decision, option C). Gap 181 closed. The LM guard passes on clean data (P5-36b: `rev_out` 0 / 80, real removed 4 / 80). The built-in guard passed only on the 781 decoder-seen pool sentences (P5-37: `rev_out` 1 / 781, real removed 1 / 781). The built-in guard on clean new data is accepted as weakly tested; the model card says "tested on training data only". Follow-ups: gap 190 = [P14-60](#p14-60-ship-the-lm_beam_direction-offer-gate-in-the-willett-hw-manifests) (done), gap 201 = [P5-40](#p5-40-built-in-direction-gate-on-clean-held-out-data). Earlier: `in_progress` (2026-11-22). Gap 181 stayed open: the done-when was not met for the built-in guard. Evidence 2026-11-22 (P5-36, pre-registration `a705a75`, results `6f45faf`, [results](../../experiments/2026-11-22-p5-36-frame-order/results.md)): the stream-integrity check (opt-in `frame_times=`, ABSTAIN with a reason code, no `config_id` change) passes I1-I3: transport faults flagged 240 / 240, real streams flagged 0 / 160. It cannot see `rev_out` as P14-57 built it (0 / 80; a value fault). The `lm_direction` offer gate is a negative result: `rev_out` offers 10 / 80 and 10 / 80, real offers removed 10 / 80 and 10 / 80 (limits 4). Evidence 2026-11-22 (P5-36b, pre-registration `dab694f`, results `a7bfbc8`, [results](../../experiments/2026-11-22-p5-36b-two-direction-lm/results.md)): the two-direction LM-beam score (`lm_beam_direction`, threshold fit on val S only). LM guard `tcfg-26ae951a20a0cddd` passes (`rev_out` 0 / 80, real removed 4 / 80). Built-in guard `tcfg-39aac48688b8bd12` fails B2 (`rev_out` 1 / 80, real removed 6 / 80; `tau` 0.326). B3-B5 pass. Extra cost 0.1-0.25 s per sentence (median). The done-when needs both guards, so this gap stays open (`in_progress`). Scope question (b) is moot: the user chose route 3. Evidence 2026-11-23 (P5-37, results `2451892`, [results](../../experiments/2026-11-22-p5-37-fixed-threshold/results.md)): with the fixed threshold 0, both guards pass on the 781 decoder-seen pool sentences (built-in `rev_out` offers 1 / 781, real offers removed 1 / 781; LM 0 / 781 and 0 / 781; limits 39). This is weak evidence, as pre-stated, so the gap stays open. Open part: a built-in-guard result on clean new data. To close the gap: a user decision (option C: accept the LM-guard evidence; option D: close the `rev_out` route by design) or new data (option B or E).
- **Follow-ups:** gap 189 = [P5-37](#p5-37-fixed-threshold-0-rule-for-the-lm_beam_direction-offer-gate); gap 190 = [P14-60](#p14-60-ship-the-lm_beam_direction-offer-gate-in-the-willett-hw-manifests); gap 191 = [P5-38](#p5-38-faster-direction-gate-reuse-the-forward-decode); gap 192 = [P4-26](#p4-26-producer-frame-times-from-the-device-adapters-to-the-trust-layer).
- **Serves:** research labs, small teams.
- **Depends on:** P14-57 (done); the P14-57 `rev_out` test set; CPU.
- **Source:** P14-57 (2026-11-21, results `71f954e`, [results](../../experiments/2026-11-21-p14-57-direction-aware-offer/results.md)): a per-sentence time-direction statistic cannot stop log-prob frames reversed after the decoder (`rev_out`) at an acceptable real cost (real offers removed 11 / 80 and 17 / 80). `rev_out` can only come from a software fault, so a stream integrity check is the direct fix.
- **Done when:** frame indices or timestamps in the NTS stream must increase, and the trust layer rejects or flags a stream otherwise. The check is in the trust layer, it is tested on synthetic reversed streams, and the P14-57 `rev_out` test set gives <= 4 / 80 offers with <= 4 / 80 real offers removed. Optional second route: a forward-vs-reverse character-LM direction score.

#### P5-37 Fixed-threshold-0 rule for the lm_beam_direction offer gate
- **Gap:** 189 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P5-36b). Follow-up of P5-36.
- **Status:** `done` (2026-11-23), pass as weak evidence. Gap 189 closed. Evidence 2026-11-23 (P5-37 option A, chosen by the user; data audit `5d74a8e`, pre-registration `d8231f8`, results `2451892`, [results](../../experiments/2026-11-22-p5-37-fixed-threshold/results.md)): fixed `tau` 0 for `lm_beam_direction` on the 781 decoder-seen pool sentences passes for both guards: built-in `tcfg-39aac48688b8bd12` `rev_out` offers 1 / 781, real offers removed 1 / 781; LM `tcfg-f498c0637536daec` 0 / 781 and 0 / 781 (limits 39). C0-C2 hold; nulls S0 / S1 pass. Pre-stated: a pass is weak evidence (the decoder trained on the pool; pool greedy CER 0.218 vs test 0.305). Descriptive: the P5-36b fitted `tau` (0.326) removes 8 / 781 on the same records. Gap 181 (P5-36) stays `in_progress`; gap 190 (P14-60) does not start on this pass alone. No change to the library, gates, guard files, manifests or `config_id` values. Earlier: `blocked` 2026-11-22 on a user decision between options A-E (data audit `5d74a8e`: no clean unused `willett-hw` data); the user chose option A.
- **Serves:** research labs, small teams.
- **Depends on:** P5-36 (P5-36b code: offer-gate feature `lm_beam_direction`); new time-reversed (`rev_out`) draws and real inputs that no earlier step used (another Willett split or another dataset); CPU.
- **Source:** P5-36b (2026-11-22, results `a7bfbc8`, [results](../../experiments/2026-11-22-p5-36b-two-direction-lm/results.md)): the LM guard passes (`rev_out` 0 / 80, real offers removed 4 / 80), the built-in guard fails B2 (real removed 6 / 80) because its fitted `tau` (0.326) comes from a thin val tail. Post hoc, for information only: a fixed threshold 0 would give 1 and 2 real removed and 1 and 2 `rev_out` offers. The P14-57 test set is now used for that choice, so it cannot test it.
- **Done when:** a pre-registered rule with the fixed threshold 0 runs on `rev_out` draws and real inputs that no step of P14-57, P5-36 or P5-36b used, and gives for both `willett-hw` guards at most 5 % `rev_out` offers and at most 5 % real offers removed (4 / 80 or the same rate on the new set size); or numbers say why not. A pass gives gap 181 the evidence for both guards.

#### P5-38 Faster direction gate: reuse the forward decode
- **Gap:** 191 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P5-36b). Follow-up of P5-36.
- **Status:** `done` (2026-11-24, commit `0997a7c`; closed by explicit user decision, option A). Gap 191 closed for the LM guard. `LmReadout` search cache: the LM guard's gate reuses the forward search of its decode. LM-guard extra time per offer 0.128 -> 0.063 s. Identity: 332 / 332 and 746 / 746 decisions equal. The built-in guard is unchanged (0.243 -> 0.249 s), because its decode has no forward LM beam to reuse. That part moved to gap 214 = [P5-41](#p5-41-bit-identical-speed-up-of-the-built-in-guard-direction-gate).
- **Serves:** research labs, small teams.
- **Depends on:** P5-36 (P5-36b code); CPU. Low priority.
- **Source:** P5-36b (2026-11-22, results `a7bfbc8`, [results](../../experiments/2026-11-22-p5-36b-two-direction-lm/results.md)): the gate runs two new beam searches per offer. Extra cost median 0.25 s (built-in) and 0.11 s (LM) per sentence, about 0.43-0.75 of a guard decision. The gate is lazy, so a withhold costs nothing extra.
- **Done when:** the gate reuses the forward beam of the guard decode, so only the reverse beam is new; decisions are equal on the P5-36b val and test sets, and the new median extra time per sentence is measured and reported.

#### P5-39 Offer-gate identity in the guard identity
- **Gap:** 200 of the [open-gap list](open-gaps.md) (added 2026-11-23 by P14-60). Follow-up of P14-60, P14-54.
- **Status:** `in_progress` (2026-11-24; one code-fix agent runs gaps 200, 202, 205, 195 and 213; nothing committed yet).
- **Serves:** research labs, small teams.
- **Depends on:** P14-60 (done); CPU.
- **Source:** P14-60 (2026-11-23, commit `212da07`): `config_id` is computed from the frozen trust config only. By documented design an offer gate never changes it (as in P14-54). So two guards with different offer-gate lists can have the same `config_id`.
- **Done when:** the guard identity includes a digest of the offer-gate list (features, rules, thresholds, order), for example a gate digest in the audit record and in the manifest identity. Two guards that differ only in their gate lists get different identities. Existing `config_id` values do not change, or a change is documented with its reason. Tests cover both cases.

#### P5-40 Built-in direction gate on clean held-out data
- **Gap:** 201 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the gap 181 decision). Follow-up of P5-36, P5-37.
- **Status:** `todo`. Low priority.
- **Serves:** research labs, small teams.
- **Depends on:** a held-out block (retrain the built-in `willett-hw` decoder with a held-out block; GPU, days) or new public T5 handwriting data. Low priority.
- **Source:** user decision 2026-11-23 (option C, gap 181 closed): the built-in guard passed the fixed threshold 0 only on the 781 decoder-seen pool sentences (P5-37, results `2451892`: `rev_out` offers 1 / 781, real offers removed 1 / 781). This is accepted as weakly tested. The model card says "tested on training data only".
- **Done when:** a pre-registered run with the fixed threshold 0 on clean held-out data gives for the built-in guard at most 5 % `rev_out` offers and at most 5 % real offers removed, or numbers say why not. The model card then states the new result.

#### P5-41 Bit-identical speed-up of the built-in guard direction gate
- **Gap:** 214 of the [open-gap list](open-gaps.md) (added 2026-11-24 by the gap 191 user decision, option A). Follow-up of P5-38.
- **Status:** `todo`. Low priority.
- **Serves:** research labs, small teams.
- **Depends on:** P5-38 (done, commit `0997a7c`); CPU. Low priority.
- **Source:** gap 191 = P5-38 result (commit `0997a7c`): the built-in decode has no forward LM beam to reuse. So the built-in `willett-hw` guard's `lm_beam_direction` extra time per offer stayed 0.243 -> 0.249 s (LM guard 0.128 -> 0.063 s).
- **Done when:** the built-in guard's direction-gate extra time per offer drops measurably, with all decisions identical on the same identity check sets (332 / 332 and 746 / 746 in P5-38).

## P6. Public benchmark + leaderboard
**Goal:** one public place to compare neural text entry across modalities and datasets, with honest metrics.

### Deliverables
- **Metrics:** eWPM against a no-BCI baseline (always), CER, WER, ECE, coverage, wrong-commit rate, hallucination on null input, latency ([error metrics](../concepts/error-metrics.md)).
- **Tracks:** intracortical speech (B2T '25), intracortical handwriting (Willett), wrist sEMG (KT-sEMG, Toronto; emg2qwerty as research-only), MEG typing (SpanishBCBL, research-only).
- **Submission format = NeuralTextStream** (Arrow or JSON Lines). The harness scores any submission without the decoder code.
- **Licence-clean splits:** fixed split files; NC datasets are download-only; no data or weights in the repo.
- A static leaderboard page (GitHub Pages) generated from a results folder.
- Shuffled-input and null-input controls are required for every entry.

### Exit criteria
- The leaderboard is public with our baselines on at least 3 tracks.
- A submission reruns from one command.
- First outside submission: **externally blocked**.

**Effort:** 15–25 agent-days. **Depends on:** M5 harness, P4 replay adapters.

**Status (2026-11-11):** v0.1 is done as M5-01..03: [open benchmark](../concepts/open-benchmark.md) (3 tracks, NTS submissions, fixed splits, static leaderboard with our baselines).

**Status (2026-11-16): P6-01 done** (commit `1d4ff8c`): benchmark tracks v0.2 with licence-clean fixed splits for 7 datasets (B2T '25, B2T '24, Willett handwriting, Toronto sEMG, KT-sEMG; SpanishBCBL and emg2qwerty research only), hash-only split files and a `verify` command ([docs/benchmark-tracks.md](../../docs/benchmark-tracks.md), [results](../../experiments/2026-11-16-p6-01-tracks/results.md)). P6-01 also gives exact Toronto safe WPM and null-commit audits for B2T and MEG. Scorer and baselines of the new tracks: P6-02.

**Value-first link (2026-11-15):** [P14-05](#p14-05-headline-metric-safe-words-per-minute) adds a "safe WPM at α" column to this leaderboard. It is not a second leaderboard.

**Later extension:** [P13](#p13-public-benchmark-hub-added-2026-11-11) grows this leaderboard into a hub. P6 scope and dates do not change.

**Status (2026-11-17): P6-02 done** (commit `5133e04`): submission format v0.2 + one-command scorer with required controls ([docs](../../docs/benchmark-submission.md)); baselines on b2t24-t12, willett-hw, kt-semg, emg2qwerty. **P6-08 done** (2026-11-17): v0.2 entries for b2t25-t15, toronto-semg and spanishbcbl-meg, so all seven v0.2 tracks have entries. Follow-up gaps 25-31 below and in P14. **T15 split audit (2026-11-17):** no committed result scores an M4-x decoder on its own training trials; follow-up gaps 32 (P6-09), 33 (P6-10), 34 (P15-20), 35 (P14-15) ([audit](t15-split-audit.md)).

### Open-gap items (added 2026-11-17)
Follow-ups of P6-02 and P6-01. Full list: [open gaps](open-gaps.md). No existing item moved.

#### P6-05 KT-sEMG calibration large enough for a certified guard
- **Gap:** 25 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the P6-02 report). Follow-up of P6-01, P6-02.
- **Status:** `todo`.
- **Depends on:** P6-01 (done), P6-02 (done); P11-01 (a stronger decoder makes commits possible).
- **Source:** Commit `5133e04` (P6-02: KT-sEMG cal split has 89 bursts; the LTT half gets 34 items, 45 are needed at alpha 0.05, so no LTT guard can commit).
- **Gap detail:** The KT-sEMG cal split (89 bursts, 3 runs) gives the LTT step only 34 items. At alpha 0.05 LTT needs at least 45 items even with zero losses, so every LTT guard on this track is vacuous by construction.
- **Done when:** One of these is done and written in the track docs and the results: (a) the kt-semg baselines use CRC (no item minimum) or an LTT variant that tests on all non-fit items, with the arithmetic shown; or (b) a new track version moves more runs into `cal` (a new split rule, a new split digest, a version note, and v0.2 cards kept readable); or (c) the docs state with numbers why no certified guard is possible on this track. The kt-semg guard card then states which one applies.

#### P6-06 Input-level controls for the T12 and Willett entries
- **Gap:** 28 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the P6-02 report). Follow-up of P6-02.
- **Status:** `todo`.
- **Depends on:** P6-02 (done); for T12: the T12 v2 checkpoint + CPU decode; for Willett: a decoder of our own (P14-12 / P15-08). 2026-11-19: P14-33 (done) packages `willett-hw` (runs on the neural cube, so time-shuffled and zero inputs are possible); same split caveat as P14-12.
- **Source:** Commit `5133e04` (P6-02: T12 and Willett controls are decoder-output stand-ins: permuted frames / uniform log-probs, not neural input re-run through the decoder).
- **Gap detail:** The shuffled and zeros controls of the b2t24-t12 and willett-hw entries change the decoder output (frames permuted, uniform rows). They do not pass shuffled or zero neural input through the network. The manifests say so, but an input-level control is the stronger test.
- **Done when:** The b2t24-t12 entry has controls made by running the T12 v2 network on time-shuffled and on all-zero neural features of each test trial (CPU decode, no GPU), and the card shows both control results. The willett-hw entry gets input-level controls when it uses a decoder that we can rerun (P14-12 / P15-08); until then the manifest keeps the stand-in note.

#### P6-07 Rule: can partial-coverage entries rank against full ones?
- **Gap:** 30 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the P6-02 report). Follow-up of P6-02, P6-03.
- **Status:** `todo`.
- **Depends on:** P6-02 (done); P9 governance (who decides benchmark rules).
- **Source:** Commit `5133e04` (P6-02: the scorer accepts a declared subset and the board marks it `[partial: n/N units]`, but no rule says how such entries rank).
- **Gap detail:** The v0.2 scorer accepts a declared subset (`coverage.subset`) and the board marks the entry `[partial: n/N units]`. No rule says whether a partial entry can rank next to full ones. A subset can be easier than the full test set.
- **Done when:** The benchmark rules (docs/benchmark-submission.md and the board) state one rule, for example: partial entries are listed in a separate block and never ranked; or they rank only with a paired comparison on the same units. The leaderboard code applies it, a test checks it, and the rule is recorded as a benchmark decision (P9 process when it exists).

#### P6-08 v0.2-format entries for b2t25-t15, toronto-semg and spanishbcbl-meg
- **Gap:** 31 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the P6-02 report). Follow-up of P6-02.
- **Status:** `done`. Commit `b9fa645` (2026-11-17): 21 v0.2 entries rerun from the v0.1 decoders and policies (B2T ours + published x always-commit / plug-in / CRC / LTT; Toronto 3 regimes x always-commit / plug-in / CRC; MEG x 4, research only) plus a partial M4-12 + guard entry (103/816 units: only the decoder's held-out val_eval trials), all scored by `python -m fidetype.benchmark score`. CER, WER, wrong-commit, commit rate and safe WPM equal v0.1 on all 21; eWPM is 0.04-1.86 lower (one decision per unit, measured B2T speech time) ([results](../../experiments/2026-11-17-p6-02b-v02-entries/results.md)).
- **Depends on:** P6-02 (done).
- **Source:** Commit `5133e04` (P6-02 wrote v0.2 entries only for the four new tracks).
- **Gap detail:** The three tracks that have v0.1 entries (b2t25-t15, toronto-semg, spanishbcbl-meg) had no v0.2-format submission or score card, so the v0.2 board showed 'No entries yet' for them.
- **Done when:** Each of the three tracks has v0.2 submissions (units + both controls) built from the v0.1 decoders and policies, scored by `python -m fidetype.benchmark score`, with numbers that match v0.1 where the definitions agree and a written reason where they differ.

#### P6-09 Full-coverage M4-x entry on b2t25-t15 without train / test overlap
- **Gap:** 32 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the T15 split audit). Follow-up of P6-08.
- **Status:** `todo`.
- **Depends on:** P6-08 (done); the GPU queue (one retrain of the M4-13 recipe); P6-10 (done; the overlap check) helps; gap 174 = [P6-11](#p6-11-text-overlap-rule-for-tracks-whose-sentences-repeat-by-design) (text-overlap rule: a retrain would still overlap by text on about 428 units).
- **Source:** T15 split audit, 2026-11-17 ([page](t15-split-audit.md)). Commit `b9fa645` first saw it.
- **Gap detail:** The B2T '25 HDF5 `train` partition holds 366 (strict match; up to 368) of the 816 `b2t25-t15` test trials. Our M4-x decoders train on it. So no M4-x decoder can have a full-coverage entry: the P6-08 entry covers only the 103 test trials in `val_eval`.
- **Done when:** (a) An M4-x decoder is retrained on HDF5 `train` minus every trial that matches a `b2t25-t15` test trial (strict or possible match of the audit), and its full 816-unit entry is scored with `python -m fidetype.benchmark score`, with the removed-trial count in the manifest. Or (b) a new track variant built on the HDF5 `val_eval` partition is defined (split file, digest, version note), and the M4-x entries move there. The [audit](t15-split-audit.md) script then shows 0 decoder-train trials among the scored units.

#### P6-10 Train / test overlap check for benchmark entries
- **Gap:** 33 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the T15 split audit). Follow-up of P6-02, P6-08.
- **Status:** `done` (2026-11-21; commit `ddb0be3`, [results](../../experiments/2026-11-21-p6-10-overlap-check/results.md)). Gap 33 closed. `training_data` declaration in the v0.2 manifest. The scorer checks overlap by id, by the committed hash-only HDF5 map (possible id) and by text hash. The card gets `overlap_check` = pass / overlap / not checked, with a warning and an optional `--fail-on-overlap`. The board marks overlapping and unchecked entries. The map reproduces the T15 audit (366 / 102 / 98 / 109 strict; 810 HDF5 trials to leave out). New CLI commands `overlap-hashes` and `overlap-list`. Docs (docs/benchmark-submission.md, docs/benchmark-tracks.md, benchmark/README.md) and 9 tests. Retro check on 36 committed cards (none changed): no id overlap anywhere; M4-12 / M4-13 overlap by text on 16 / 103 units; 8 b2t25-t15 ours / published entries are not checked; 24 pass by id only. Deviation: a missing declaration reads "not checked" and is not refused, so older submissions stay scorable.
- **Follow-ups:** gap 174 = [P6-11](#p6-11-text-overlap-rule-for-tracks-whose-sentences-repeat-by-design) (text-overlap rule for tracks whose sentences repeat by design); gap 175 = [P6-12](#p6-12-training-data-of-the-published-card-et-al-2024-decoder-for-the-overlap-check) (training data of the published Card et al. 2024 decoder).
- **Depends on:** P6-02 (done); P6-01 (done).
- **Source:** T15 split audit, 2026-11-17 ([page](t15-split-audit.md)).
- **Gap detail:** The pkl track units and the HDF5 neural trials are the same trials in two forms. Anyone who trains on the public HDF5 `train` partition (the normal B2T '25 recipe) trains on about 45 % of the `b2t25-t15` test set. No tool checks this. The P6-08 agent found the overlap by chance.
- **Done when:** (1) The v0.2 submission manifest has a required `training_data` field (dataset + partitions, or "none"). (2) The repo has a hash-only map from B2T '25 HDF5 trials (session, block, trial) to `b2t25-t15` units, built by the audit match (no text). (3) `python -m fidetype.benchmark score` warns, and the board marks the entry, when the declared training data overlap the scored units. (4) docs/benchmark-tracks.md says which HDF5 trials an outside team must leave out. (5) A test checks the warning.

#### P6-11 Text-overlap rule for tracks whose sentences repeat by design
- **Gap:** 174 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P6-10). Follow-up of P6-10.
- **Status:** `todo`.
- **Depends on:** P6-10 (done); P9 governance (who decides benchmark rules).
- **Source:** P6-10 (commit `ddb0be3`, [results](../../experiments/2026-11-21-p6-10-overlap-check/results.md)): on b2t25-t15, 428 of 816 test sentences occur in HDF5 train. M4-12 / M4-13 overlap by text on 16 / 103 units, and a P6-09 retrain would still overlap on about 428 units.
- **Done when:** the benchmark rule says whether same-sentence / other-trial overlap disqualifies, only warns, or needs a track variant; the scorer applies that rule per track; and the M4 entries are re-marked to match. P6-09 depends on this item.

#### P6-12 Training data of the published Card et al. 2024 decoder for the overlap check
- **Gap:** 175 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P6-10). Follow-up of P6-10.
- **Status:** `todo`. May be externally limited (needs the paper's block lists).
- **Depends on:** P6-10 (done); the block lists of Card et al. 2024.
- **Source:** P6-10 (commit `ddb0be3`, [results](../../experiments/2026-11-21-p6-10-overlap-check/results.md)): the 8 b2t25-t15 ours / published entries read `overlap_check` "not checked", because the training data of the published Card et al. 2024 online decoder are not mapped. The mapping needs the paper's block lists.
- **Done when:** the training data of the published decoder are mapped to b2t25-t15 units (hash-only) or declared in the 8 manifests, and these entries get `overlap_check` pass or overlap; or the docs say with reasons why no mapping is possible.

## P7. Conformance + certification
**Goal:** anyone can prove that an implementation speaks NTS correctly.

**Status (2026-11-17):** P7-01 `done`: conformance kit `spec/conformance/kit/` (31 example files over every RC4 wire form: JSON Lines streams and decision logs, NPZ, LSL and WebSocket captures; verdict + rule ids per file) and the `nts-conform` CLI (per-rule report with location, JSON report, exit codes; kit mode checks an external validator's verdicts). Python = TypeScript = Rust on all 31 files; schema parity 0 mismatches. [Docs](../../docs/conformance.md), [concept](../concepts/conformance-suite.md#conformance-kit-and-nts-conform-p7-01). New gap 20 = P1-16 (MET-11 traceability).

**Status (2026-11-17, later):** P7-02 `done` (commit `ce7e085`): RC4 amendment 3 defines the implementation levels **NTS Core**, **NTS Full** and **NTS Trust-ready** (spec 9.6; CNF-2 … CNF-7) and the self-certification list (9.7, CNF-8). `nts-conform check` reports the producer level, `nts-conform kit` the consumer level (`--claim`, `--binding`, `--require-level`, `{level}` in `--cmd`). Kit 0.2.0 (36 files: K32 MET-11 warning, K33–K36 stream levels). Finer rule mapping for broad checks. [`spec/conformance/certified.json`](../../spec/conformance/certified.json): Python, TypeScript and Rust SDKs = consumers at NTS Trust-ready; text n-best adapter = producer at NTS Trust-ready; 7 frame adapters = producers at NTS Core (stream level provenance or trust-ready). Pull-request process in [docs/conformance.md](../../docs/conformance.md#self-certification). P1-16 (gap 20) closed with it. New gaps 23 = P7-05 (collector against the kit) and 24 = P7-06 (binding producers in the list).

### Deliverables
- **Conformance kit:** valid and invalid example files in each wire form (start from cases C1–C20 of [spec 7.1](../../spec/neuraltextstream-v0.1.md#71-conformance-cases)); a test runner CLI (`nts-conform`) for producers, consumers and collector components.
- **Levels:** "NTS Core" (frames), "NTS Full" (all event kinds), "Trust-ready" (score semantics + provenance + timing).
- **"Fidetype-compatible" mark:** self-certification first (a public list with a link to the passing CI run). Trademark use rules.
- Trademark registration of "Fidetype": **user-owned, externally blocked**.

### Exit criteria
- Every SDK and the collector pass the kit in CI.
- The first self-certified implementation outside our repo: **externally blocked**.

**Effort:** 15–25 agent-days. **Depends on:** P1, P2.

#### P7-05 The collector passes the kit in CI
- **Gap:** 23 of the [open-gap list](open-gaps.md). Follow-up of P7-01, P7-02.
- **Status:** `done` (2026-11-17, commit `2298e3e`, with P3-04). `fidetype-collector consume [--profile P] [--level L] FILE` reads the file through the collector's own input path (the `file` receiver, now also NPZ, then the `validate` processor at stream level L); exit 0 = accept. `nts-conform kit --claim text --require-level trust-ready --cmd "fidetype-collector consume -q --profile {profile} --level {level} {path}"`: consumer level **NTS Trust-ready** (text); 28 of 36 entries match; the 8 others (intent, control, LSL and WebSocket captures) are "not supported" (new gap 41 = P7-07). CI job `collector` runs it; `certified.json` lists `fidetype-collector` with its kit report. [Docs](../../docs/collector.md#the-collector-as-a-consumer-the-conformance-kit-p7-05-p7-07).
- **Depends on:** P3 collector (draft FEP-0006), P7-02 (`nts-conform kit --cmd`, levels).
- **Source:** P7-02 (2026-11-17): the P7 exit criterion says "every SDK and the collector pass the kit in CI". The three SDKs do (NTS Trust-ready, CI job `rust-parity`); the collector (`fidetype-collector`) is not run against the kit and has no entry in `spec/conformance/certified.json`.
- **Done when:** the collector has a consumer entry point that follows the kit contract (exit 0 = accept; a `{level}` option for stream levels), CI runs `nts-conform kit --cmd "... {path}" --require-level <level>` on it, and `certified.json` lists the collector with its kit report as evidence.

#### P7-06 Binding producers in the self-certification list
- **Gap:** 24 of the [open-gap list](open-gaps.md). Follow-up of P7-02.
- **Status:** `done` (2026-11-17, commit `f6a2024`). `nts-conform capture` records an `lsl-scenario/1` capture (`--lsl QUERY`: frames + events streams, or a decisions stream) or a `ws-scenario/1` capture (`--ws ws://HOST:PORT/nts`: a recording server; `--ws ws://HOST:PORT/decisions`: a subscriber); `--received` writes what the reference consumer reads (the input stream that a producer level needs, spec 9.6). `python -m fidetype.conformance.binding_producers` runs our LSL outlets (`replay_to_lsl`, `DecisionOutlet` of `LSLTrustRunner`) and our WebSocket producer (`replay_to_ws`) and `/decisions` channel (`WSServer` + `WSTrustRunner`) on synthetic input in one process on loopback (about 6 s). `certified.json`: `binding-lsl` and `binding-ws`, both NTS Trust-ready (text) with `nts-lsl/0.1` / `nts-ws/0.1`. CI job `live` regenerates the captures and checks them (`--require-level trust-ready` + binding). Docs: [conformance](../../docs/conformance.md#record-a-capture-from-a-live-producer-lsl-websocket). `fidetype live` has no outlet: new gap 36 = P14-16.
- **Depends on:** P7-02; the LSL outlet (`fidetype.adapters.lsl`), the WebSocket sender (`fidetype.adapters.ws`) and `fidetype live` (P14-04).
- **Source:** P7-02 (2026-11-17): the producer entries of `certified.json` are file producers. Our code that emits NTS over LSL or WebSocket has no producer evidence, because `nts-conform check` judges recorded captures (scenario JSON) and no tool records a capture from a live outlet yet.
- **Done when:** a tool records an LSL capture (`fidetype.conformance.lsl-scenario/1`) and a WebSocket capture (`ws-scenario/1`) from our own outlets (synthetic input, loopback, CI-safe), `nts-conform check` gives them a producer level with the binding, and `certified.json` lists the binding producers with that evidence.

#### P7-07 Collector consumer: intent and control profiles, LSL and WebSocket captures
- **Gap:** 41 of the [open-gap list](open-gaps.md). Follow-up of P7-05.
- **Status:** `done` (2026-11-17, commit `2984990`). `fidetype-collector consume` reads all suite profiles: `validate` runs the FEP-0003 / FEP-0005 rule functions of `fidetype.conformance.profiles` on headers, profile events and intent / control decisions (bounded windows of 512); LSL `inlet` captures replay into the `lsl` receiver (`capture.lsl_source`), WebSocket `ingest` captures into the `websocket` receiver's ingest core (`capture.play_ws_steps`, server not started), decision captures through `capture.received`; each capture also goes through the reference consumer of its binding profile. Kit: **36 / 36**, consumer level NTS Trust-ready for text, intent and control with `nts-lsl/0.1` and `nts-ws/0.1`; `certified.json` entry updated; CI job `collector` checks all entries and both bindings. [Docs](../../docs/collector.md#the-collector-as-a-consumer-the-conformance-kit-p7-05-p7-07).
- **Depends on:** P7-05 (done); the collector `validate` processor; the LSL and WebSocket receivers.
- **Source:** P7-05 (2026-11-17): the collector consumer reaches NTS Trust-ready for the profile `text` only. The `validate` processor has no intent (FEP-0003) or control (FEP-0005) checks, and the collector cannot read recorded LSL or WebSocket captures, so K19, K21, K23, K25, K26, K28, K29 and K31 give "not supported".
- **Done when:** the collector consumer gives the expected verdict on all 36 kit entries (intent and control checks in `validate`; a capture replay into the LSL and WebSocket receivers), and `certified.json` lists it with the profiles `text`, `intent`, `control` and both bindings.

## P8. Docs, website, demo
**Goal:** a newcomer gets a valid stream in 10 minutes and sees the value in one demo.

### Deliverables
- Website (GitHub Pages): spec (generated), SDK docs per language, the leaderboard, the FEP index. Structure, spec presentation (per-clause pages, rule-id anchors, status badges, versions, diffs), tool choice (Sphinx + MyST) and phased tasks: [docs site plan](docs-site-plan.md) (P8-06, 2026-11-14).
- Quickstarts: "emit NTS from your decoder in 10 lines" (Python, C, TS); "add calibrated confidence and abstention"; "replay a public dataset".
- Examples folder: one per adapter.
- **Flagship demo: three devices → the same stream → the same trust layer.** Replay of B2T '25 (implant), KT-sEMG (wrist EMG) and SpanishBCBL (MEG) into one collector; one trust config; one browser UI that shows the committed text, the n-best choices and the abstentions. A recorded video.

### Exit criteria
- A new user (tested by a fresh subagent with no context) reaches a valid stream from the quickstart alone.
- The demo runs from one command on a clean machine.

**Effort:** 15–25 agent-days; user: video voice-over or review (about 10 h). **Depends on:** P2, P3, P4.

**Value-first link (2026-11-15):** [P14-06](#p14-06-visible-demo-recorded-emg-to-text) is a smaller single-modality demo (recorded EMG → text). The three-device demo (P8-03) can reuse it. [P14-03](#p14-03-trust-layer-as-a-drop-in-wrapper) adds one quickstart to P8-02.

### Open-gap items (added 2026-11-19)

#### P8-07 Effort-weighted progress view on the dashboard
- **Gap:** 116 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P8-05 (dashboard: `tools/progress/build.js`).
- **Status:** `todo`.
- **Depends on:** —.
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" The progress dashboard counts items. A small fix and a large research item count the same. Negative results look like normal `done` items. `externally_blocked` items mix with the others in the totals.
- **Done when:** Each tracker item can carry a size (S / M / L or agent-days; old items get a default). The dashboard shows progress weighted by size next to the item count. Items with a negative or null result carry a flag in tracker.json and a visible mark. `externally_blocked` items have a separate total. The build stays offline and the compact tracker layout stays.

## P9. Governance + community
**Goal:** the rules that let other people trust and join the project.

### Deliverables
- **Licences** (the repo [`LICENSE`](../../LICENSE) is Apache-2.0 today; the spec header also says Apache-2.0). Options for the spec text:

  | Option | For | Against |
  |---|---|---|
  | Keep Apache-2.0 for spec and code | One licence; patent grant; OTel-style (rough, to check) | Unusual for prose |
  | CC BY 4.0 for the spec text, Apache-2.0 for schemas and code | BIDS-style (to check) | No patent grant on the spec |
  | Add a patent commitment (for example, an OWF-style agreement) | Device makers ask about patents | Legal work (**user-owned**) |

  Recommendation: keep Apache-2.0 for now; decide the patent question before spec 1.0 Stable.
- CONTRIBUTING, Code of Conduct, GOVERNANCE, SECURITY exist ([playbook](open-source-playbook.md#cheap-actions-now)). Add: a maintainer guide, triage labels, CODEOWNERS for adapters, a DCO check.
- **RFC process** = FEPs (P1).
- **Neutral home, later (options only):** LF AI & Data, NumFOCUS, the Linux Foundation directly, or a standards body path (IEEE SA). Conditions in [GOVERNANCE.md](../../GOVERNANCE.md): at least 3 maintainers from at least 2 employers, and outside adopters.

### Exit criteria
- Licence decision recorded. DCO check active. CODEOWNERS file exists.
- Second maintainer, foundation application, steering group: **externally blocked**.

**Effort:** 5–10 agent-days; about 20 h user decisions over time. **Depends on:** nothing technical.

## P10. Adoption plan
**Goal:** decoders and devices outside the project emit NeuralTextStream. This is the success metric ([playbook](open-source-playbook.md#success-metrics)).

### Order
| Step | Action | Who | State |
|---|---|---|---|
| 1 | Demo (P8) + public benchmark (P6) | Agents | In our control |
| 2 | **Paper 1** on arXiv (trust layer; cross-modality results) | Agents write; user submits | arXiv endorsement **externally blocked** |
| 3 | Targeted communities: NeurotechX, OpenBCI forum, BCI Society, Hacker News "Show HN", relevant subreddits and Discord servers | **User** posts; agents draft | **externally blocked / user-owned** |
| 4 | Direct contact with 5–10 groups: dataset labs (UC Davis, Stanford NPTL, Nokia Bell Labs, Toronto; [leads](public-datasets.md#university-labs-leads-only-no-outreach)), LSL maintainers, OpenBCI, AAC developers. Target list: [partner targets](partner-targets.md); drafts: `papers/outreach/` | **User** sends; agents draft | **externally blocked** |
| 5 | Day-0 support for each new public dataset or decoder paper ([playbook stage 2](open-source-playbook.md#stage-2-community-engine)) | Agents | In our control |
| 6 | Pilot with a device maker or AAC developer | User | **externally blocked** |

Also externally blocked: ethics approval, volunteers, user studies, peer review.

### Exit criteria
- At least one decoder outside the project emits NTS (**externally blocked**).
- At least one outside contribution merged (**externally blocked**).

**Effort:** 5–10 agent-days of drafting; 60+ h user time. **Depends on:** P6, P8, Paper 1.

## P11. Research track (in parallel)
**Goal:** keep the credibility base. Better decoders make the trust layer useful, not only safe.

### Deliverables
- **EMG decoders:** a causal ConvCTC on KT-sEMG and Toronto (clean); emg2qwerty for research.
- **Cross-subject pretraining** (MEG and EMG), then per-user fine-tuning.
- **LLM priors** with hallucination guards: an LM that helps but cannot commit text without neural evidence.
- **Results for papers:** P11 files results in `experiments/` and the wiki. Paper 1, Paper 2 and a spec / benchmark paper draw on them later in the PUB track.

### Exit criteria
- On at least one modality, the trust policy beats the no-BCI baseline in eWPM.
- Results filed in `experiments/` and the wiki. (Papers on arXiv and peer review are PUB items. They are not P11 exit criteria.)

**Effort:** ongoing; GPU-bound (one heavy job at a time on this PC). **Depends on:** GPU, datasets.

### Item status (added 2026-11-19)
- **P11-01** `done` (2026-11-19, emg2qwerty part; [results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md)): our own causal CTC decoder, greedy, no LM, our 8-user split. Personalised test CER 15.09 % (mean over 8 users; S1 <= 20 % pass), generic 53.52 % (S2 pass), 8 of 8 users better (S3), time-shuffled 0.986 (C1), 2,445 / 2,445 NTS streams `trust-ready` (N1), median emission delay 70 ms (L1). Stretch S1+ (<= 11.28 %) **failed**. The licence-clean KT-sEMG + Toronto part of the title moves to the new item P11-06 (gap 86); nothing is dropped.

#### P11-06 Licence-clean causal ConvCTC on KT-sEMG and Toronto
- **Gap:** 86 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-01). Follow-up of P11-01.
- **Status:** `todo`.
- **Depends on:** P11-01 (done); KT-sEMG and Toronto data (local, CC BY 4.0); GPU.
- **Source:** P11-01 ([results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md)): P11-01 was titled 'causal ConvCTC on KT-sEMG + Toronto; emg2qwerty research baseline'. Only the emg2qwerty part is done; its weights are research only (CC BY-NC-SA 4.0 data).
- **Done when:** A causal CTC decoder trained only on CC BY data (KT-sEMG, Toronto sEMG) is evaluated on their held-out splits (plan with criteria before training; no lookahead or a declared bounded lookahead), outputs NTS streams at level `trust-ready`, and its weights carry a licence flag that allows product use.

#### P11-07 CTC beam search with a character LM for the EMG decoder
- **Gap:** 87 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-01). Follow-up of P11-01.
- **Status:** `done` (2026-11-19).
- **Depends on:** P11-01 (done); a licence-clean text corpus for a character n-gram LM; CPU or GPU.
- **Source:** P11-01 ([results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md)): P11-01 decodes greedily with no LM (personalised test CER 15.09 %). The published Table 3 LM column (6-gram char LM) is 6.95 % for the fine-tuned model, 4.33 points better than its no-LM column.
- **Done when:** The P11-01 personalised models are decoded with a CTC prefix beam search and a character n-gram LM trained on licence-clean text (no emg2qwerty prompts from the test sessions), causally (no future frames beyond the LM step); the test CER (mean over 8 users) is reported against the Table 3 LM column, with a plan written before the test decode.
- **Result (2026-11-19):** [results](../../experiments/2026-11-20-p11-07-emg-beam-lm/results.md). Pre-registration `d168c51`, code `9e12a97`, amendment 1 `27f6d08`, results `1bd41d9`. Own CTC prefix beam with shallow fusion of the leak-free Tatoeba 6-gram on the intended text (Backspace pops, Enter resets), tuned on the 765 track-val tuning prompts (w 0.5, beta 1, beam 8). Session CER on the 8 track-test sessions, mean over users: greedy 14.66 % -> **10.10 %** (8 of 8 users better; pooled 10.17 %); beam 64 9.13 %; published fine-tuned no LM 11.28 %, LM 6.95 %. Intended-text CER 15.16 % -> 9.75 %. Lexicon term did not help (10.88 %). Time-shuffled control 0.985. Greedy reproduces P11-01 on its 16-session set (15.0898 %). 50 ms on CPU: fails at every beam (gap 37; new P3-12). P11-12 arm S with the new decoder: certified, 3.37 [1.92, 5.18] (P11-12: 4.10); new P11-14. Gap 87 closed.

#### P11-08 EMG decoder accuracy to the published fine-tuned no-LM CER
- **Gap:** 88 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-01). Follow-up of P11-01.
- **Status:** `todo`.
- **Follow-up:** gap 178 = [P11-25](#p11-25-revisit-the-p11-08-decoder-target-framing) restates the target of this item (P11-10, 2026-11-21: 11.28 % is a no-LM number with 100 ms future context in training; with LM the paper gives 6.95 %; the paper calls about 10 % CER or less usable). Done 2026-11-21: see the restated done-when below. The title keeps "no-LM CER" so that links stay valid; 11.28 % is the target only for a no-LM decoder with 100 ms lookahead.
- **Depends on:** P11-01 (done); GPU; the 95.7 GB feature cache (or a new one).
- **Source:** P11-01 ([results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md)): P11-01 stretch criterion S1+ failed: personalised test CER 15.09 % vs 11.28 % published. The generic model is best at step 30,000 of 150,000 (val CER 0.5457) and overfits after that, so a longer run does not help.
- **Done when (original, 2026-11-19; replaced by the restated text below on 2026-11-21, kept for history):** A pre-registered run tests at least one of: stronger regularisation or a shorter schedule for the generic model, 33 bins at 125 Hz (on a subset if the cache budget needs it), a bounded 100 ms lookahead (reported as non-causal by 100 ms); it reports the personalised test CER on the same 8 users, or a stated null result.
- **Done when (restated 2026-11-21 by P11-25, gap 178; [matched-target rule](frontier-decoder-quality.md#matched-emg-decoder-target-p11-25-2026-11-21)):** A pre-registered run tests at least one of: stronger regularisation or a shorter schedule for the generic model, 33 bins at 125 Hz (on a subset if the cache budget needs it), a bounded 100 ms lookahead (reported as non-causal by 100 ms). The plan states the decoder condition before the test decode: LM or no LM, and causal or lookahead in ms. The run reports the personalised test CER on the same 8 users, or a stated null result. (1) **Bar 1, matched target:** compare only with the published number of the same condition (paper Table 3, p. 9): no LM + 100 ms lookahead -> 11.28 %; 6-gram char LM + 100 ms lookahead -> 6.95 %. A causal decoder has no matched published number; report the difference to the published number with the same LM condition as indicative, and call it a harder condition. Never compare a with-LM CER with 11.28 %. (2) **Bar 2, usability:** report separately whether the CER is at or below about 10 % (paper p. 9), with the decoder condition stated.

#### P11-09 Trust config and streaming replay for the P11-01 EMG streams
- **Gap:** 89 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-01). Follow-up of P11-01, P14-10.
- **Status:** `done` (2026-11-19).
- **Depends on:** P11-01 (done); the local NTS streams and personalised models in derived/p11-01-emg-decoder/train/.
- **Source:** P11-01 ([results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md)): P11-01 plan step 3: a trust config for EMG (LTT on the personal val streams, commit gate, null controls; the M2-19 rule) is a follow-up. P11-01 evaluated whole sessions in causal chunks offline; no stream went through the collector or the trust layer at real time.
- **Done when:** A trust config fitted on held-out streams of the 8 users (not the test sessions) is frozen (`config_id`); the test streams replay at real time through the collector (validate -> guard) with added latency reported; wrong-commit rate with its CP95 bound, commit rate, null controls and eWPM / safe WPM are reported. This gives the P11-01 part of P14-10 and the data for a declared-subset emg2qwerty entry (P14-13).
- **Result (2026-11-19):** [results](../../experiments/2026-11-19-p11-09-emg-trust/results.md). P11-09 (2026-11-19, pre-registration `0c53d68`, amendments `f28416d` / `36a921c`, code `9220525`, results `e05b509`): trust guard `tcfg-4af5a234c1cf7826` (LTT, alpha 0.05, delta 0.1) on the 1,224 track-val prompts of the 8 users is certified (all null controls 0/300) and safe (0 wrong commits / 1,221 track-test prompts, CP95 [0, 0.003]) but vacuous: 0 commits, safe WPM v0.1 0.00 < no-BCI 2.93; top-1 exactly right on 2 / 1,221 prompts. Key error rate 0.179 [0.145, 0.214], eWPM 3.44 vs gaze 2.93. Real-time collector replay (240 prompts, 8 per-user streams): `added` p50 58.6 ms, p95 up to 222 ms: fails the 50 ms budget (built-in beam inside the collector = gap 37). Declared-subset emg2qwerty cards added (research only). New gap 102 (P11-11).

#### P11-10 Ingest the emg2qwerty paper as a wiki source page
- **Gap:** 90 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-01). Follow-up of P4-01, P11-01.
- **Status:** `done` (2026-11-21; commit `70807b0`). Gap 90 closed. emg2qwerty paper ingested ([source page](../sources/emg2qwerty.md)). 108 users, 346.4 h, keylogger labels. Table 3 p. 9: fine-tuned 11.28 % no LM / 6.95 % with LM; the paper calls about 10 % CER or less usable. Contradictions recorded: the Brain2Qwerty v2 "causal Conformer" (the paper uses a TDS ConvNet with 100 ms future context in training), the licence (the paper says CC BY-NC-SA 4.0; the repo README says CC BY-NC 4.0), and "affordable hardware" (the sEMG-RD is proprietary). The P11-01 "usable as is" claim got a dated correction note. The P11-07 comparison in the open-gap list now uses 6.95 % for with-LM.
- **Follow-ups:** gap 178 = [P11-25](#p11-25-revisit-the-p11-08-decoder-target-framing) (matched decoder target for P11-08 / gap 88); gap 179 = [P11-26](#p11-26-check-the-ctrl-labs-2024-generic-neuromotor-paper) (check the CTRL-labs 2024 generic neuromotor paper; low priority).
- **Depends on:** the paper PDF (references/papers, git-ignored).
- **Source:** P11-01 ([results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md)): The P11-01 comparison cites Table 3 through the plan and the entity page; the wiki has no source page for the paper (entity tag `paper-not-ingested`). Table 3 was checked against arXiv HTML on 2026-11-19.
- **Done when:** wiki/sources/emg2qwerty.md exists with citation, licence, TL;DR, Table 3 numbers with page / table, the split scheme and limits; the entity page, the P11-01 results and the frontier decoder page link it.

#### P11-11 Non-vacuous EMG safe WPM (commit unit or LM)
- **Gap:** 102 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-09; reopened 2026-11-19 by the orchestrator). Follow-up of P11-09, P11-07.
- **Status:** `done` (2026-11-19, closed by P11-12). Before: `in_progress` (partial): arm X non-vacuous under proposed v0.2 but failed null control V6 (6.2 % > 5 %); v0.1 0.07.
- **Depends on:** P11-09 (done); P11-12 (gap 104, done); P11-07 (character LM + beam) optional.
- **Source:** P11-09 ([results](../../experiments/2026-11-19-p11-09-emg-trust/results.md)): the certified guard on the P11-01 EMG decoder never commits. A COMMIT must equal the whole prompt key sequence, with the user's own errors and Backspace keys; at 17.9 % key errors the top-1 is exactly right on 2 / 1,221 prompts.
- **Done when:** a pre-registered EMG guard gives a non-vacuous certified safe WPM on held-out emg2qwerty prompts, with a commit unit the decoder can get right (word or key-prefix commits under the proposed v0.2, or the intended text after Backspace as the target) or with LM / lexicon decoding (P11-07), and the same controls as P11-09; or the result states with numbers why it stays vacuous.
- **Result (2026-11-19):** [results](../../experiments/2026-11-19-p11-11-emg-nonvacuous/results.md). Pre-registration `b412c76`, amendment 1 + code `5f54a45` (out-of-lexicon gate), results `766b2b3`. Target = intended text after Backspace; key CTC beam 64 n-best rescored with a leak-free Tatoeba 6-gram LM and a track-train lexicon. Word-prefix arm (learned prefix score, LTT alpha 0.05, delta 0.1): certified, **non-vacuous proposed-v0.2 safe WPM 4.23 [2.60, 6.34]** on the 1,221 track-test prompts (420 commits, 35 wrong, CP95 [0.020, 0.040]) > no-BCI 3.09 / 2.93, not clearly above; adopted v0.1 only 0.07. Sentence-level arms refused (time-shuffled null 19-20 / 300); the prefix arm fails the evaluation null control (6.2 %); raw-key track arm vacuous (no card). New gap 104 = P11-12.
- **Closed (2026-11-19) by P11-12** ([results](../../experiments/2026-11-20-p11-12-emg-nosignal-gate/results.md)): with the acoustic no-signal gate, the primary sentence arm S passes every P11-09 control and gives a certified, non-vacuous safe WPM v0.1 **4.10 [1.99, 6.60]** > no-BCI 3.09 (167 commits, 35 wrong = 0.029); test time-shuffled and zero-EMG commits 0 / 1,221.

#### P11-12 No-signal detector for the EMG intended-text guard
- **Gap:** 104 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-11; closed 2026-11-19). Follow-up of P11-11.
- **Status:** `done` (2026-11-19).
- **Depends on:** P11-11 (partial; gap 102 reopened, closes with this item); the P11-09 / P11-11 local files (`derived/p11-09`, `derived/p11-11`); CPU.
- **Source:** P11-11 ([results](../../experiments/2026-11-19-p11-11-emg-nonvacuous/results.md)): time-shuffled EMG decodes to one confident real word after the LM / lexicon rescoring (245 of 246 non-gated null outputs are one word). So the sentence-level guards are refused (19 and 20 / 300 null commits, allowed 15), and the certified prefix guard commits on 6.2 % of the null test inputs.
- **Done when:** a pre-registered no-signal gate that does not use the language side (for example a minimum word count, a decoded-words-per-second check against the user's calibration range, or an acoustic-only evidence score) makes the sentence-level guard pass all controls and keeps the prefix guard's evaluation null-commit rate at or below 5 %, on the same split; v0.1 and proposed v0.2 values reported.
- **Result (2026-11-19):** [results](../../experiments/2026-11-20-p11-12-emg-nosignal-gate/results.md). Pre-registration `f63da8a`, code `3a0572b`, results `a93aa50`. Gate (decoder argmax path only): greedy CTC key emissions >= 15 and 1.84 <= keys/s <= 17.28, fitted by a fixed rule on the 765-item calibration tuning part; it gates 0 % of time-shuffled tuning windows and 2.2 % of real test windows. All arms certified, safe, non-vacuous, all controls pass (calibrate input-level null 0 / 300; test time-shuffled and zero EMG 0 / 1,221): sentence S v0.1 **4.10 [1.99, 6.60]**, learned SL v0.1 5.08 [2.67, 7.96], prefix X proposed v0.2 4.25 [2.69, 6.30] (P11-11 null 6.2 % -> 0 %); no-BCI 3.09; none clearly above. Gaps 104 and 102 closed. No card (intended-text target): new gap 105 = P11-13.

#### P11-13 Intended-text scoring for the emg2qwerty track
- **Gap:** 105 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-12). Follow-up of P11-12, P6-02.
- **Status:** `done` (2026-11-19).
- **Depends on:** P11-12 (done); `fidetype.benchmark.scorecard` (submission v0.2); CPU.
- **Source:** P11-12 ([results](../../experiments/2026-11-20-p11-12-emg-nosignal-gate/results.md)): the certified EMG guards commit the intended text (Backspace applied), but the emg2qwerty track scorer compares commits to the raw key sequence. So the first non-vacuous certified EMG safe WPM (4.10 v0.1) has no score card and no leaderboard row.
- **Done when:** the emg2qwerty track (or a declared variant) can score an `intended` target (truth = key sequence with Backspace applied, the P11-11 `resolve` rule) in `fidetype.benchmark`, with tests; the P11-12 arm S gets a declared-subset card with a rerun recipe (code_ref); `python -m fidetype.benchmark.leaderboard --check` passes.
- **Result (2026-11-19):** [results](../../experiments/2026-11-20-p11-13-intended-text-cards/results.md). Code `698bbe8`, cards `ca73b5c`. Manifest field `target` (emg2qwerty only): `raw_keys` (default, `raw-keys/1`; old cards rescore equal) or `intended_text` (`intended-text/1`: Backspace applied by `registry.keycodes_to_intended_text`, tested equal to the P11-11 `resolve`; truth, outputs and the no-BCI reference all use the target text). Cards declare their target; the leaderboard shows each target in its own table with its own no-BCI row. Declared-subset cards (8 users, 1,221 prompts): arm S certified safe WPM v0.1 **4.10 [1.99, 6.56]** vs no-BCI 3.09; arm SL 5.08 [2.54, 7.95]; controls pass. Same value, commits and words as P11-12; CI differs only by cluster label order. Gap 105 closed.

#### P11-14 Guard confidence for the in-beam LM decoder
- **Gap:** 123 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P11-07). Follow-up of P11-07, P11-12.
- **Status:** `done` (2026-11-20).
- **Depends on:** P11-07 (done); P11-12 (done); CPU.
- **Source:** P11-07 ([results](../../experiments/2026-11-20-p11-07-emg-beam-lm/results.md)): with the in-beam LM decoder the top-1 intended text is right more often (32.4 % vs 24.0 %), but the certified safe WPM is lower (arm S 3.37 vs 4.10; SL 3.16 vs 5.08; error among commits 0.28 vs 0.21). The fused n-best is confident on wrong texts too.
- **Done when:** a pre-registered confidence for the in-beam decoder (for example an n-best temperature or LM-weight split, acoustic-only features, or a learned score with beam features) gives a certified, non-vacuous safe WPM v0.1 at least the P11-12 value on the same split, with the same gate and controls; or the result states with numbers why not.
- **Result (2026-11-20):** [results](../../experiments/2026-11-20-p11-14-emg-lm-confidence/results.md). Pre-registration `39f6432`, code + amendment 1 `a3d50eb`, card script `659616f`, results `db96a4e`, leaderboard `ecd3773`. Same split, gate, LTT and controls. Six primary candidates ({own n-best posterior P, acoustic-only posterior A, learned score L} x {decoder F, FL}); selection on the 765 calibration tuning items only chose **L-FL**. Certified safe WPM v0.1 **6.80 [4.49, 9.63]** (285 commits, 52 wrong = 0.043; controls 0 / 0 / 0 of 300 and 0 / 1,221 time-shuffled and zero EMG), above P11-12 S 4.10 and SL 5.08, and above P11-07 S 3.37 (reproduced exactly); the first EMG value with the CI above no-BCI 3.09 (correction 2026-11-21, P11-17: this CI holds for one calibration draw; with the calibration draw counted the value is 5.00 [0.00, 9.55], above 3.09 on average, not reliably; [results](../../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md)). The gain comes from the fused posterior over a wider competitor set (beam + no-LM 64-best; test AUROC 0.88 vs 0.81) and the LM log-prob per character; the acoustic-only posterior fails (AUROC 0.60, arm A 0.43). New intended_text card (scorer 6.80 [4.36, 9.65]). Gap 123 closed. Follow-ups: [P11-15](#p11-15-latency-cost-of-the-p11-14-confidence) (gap 125), [P11-16](#p11-16-p11-14-confidence-signals-for-prefix-commits) (gap 126).

#### P11-15 Latency cost of the P11-14 confidence
- **Gap:** 125 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P11-14). Follow-up of P11-14, P3-12.
- **Status:** `todo`.
- **Depends on:** P11-14 (done); P3-12 (gap 122); CPU.
- **Source:** P11-14 ([results](../../experiments/2026-11-20-p11-14-emg-lm-confidence/results.md)): the learned confidence L-FL needs a second beam (no LM, beam 64) and an exact CTC re-scoring of about 70 key sequences per window. The offline decision time with a memoised decode is p50 25 ms, p95 65 ms; the end-of-window cost of the second beam and the re-scoring was not measured.
- **Done when:** the end-of-window cost of the L-FL confidence is measured on the 1,221 evaluation windows (CPU, class `timing`), and a pre-registered cheaper competitor set (for example the in-beam beam at a larger width only, or the no-LM beam run in streaming form) is tested for the same certified value (within the CI) under the P3-12 50 ms rule; or the result states with numbers why not.

#### P11-16 P11-14 confidence signals for prefix commits
- **Gap:** 126 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P11-14). Follow-up of P11-14, P11-12.
- **Status:** `done` (2026-11-21; plan `ded01cf` before any number, code and tests `0575c8a`, results `82a96bc` + `0d0107c`, [results](../../experiments/2026-11-21-p11-16-emg-prefix-confidence/results.md)). Gap 126 closed. Primary arm LX-FL (learned prefix score from the P11-14 signals, FL decoder, certified with `ltt_prefix_threshold` outside `calibrate`): **proposed v0.2** 9.47 [6.97, 12.75] with one calibration (671 commits, 592 prefix, 46 wrong); adopted v0.1 only 2.60 [1.35, 4.27]. Calibration-inclusive (40 draws, proposed v0.2): 7.18 [0.00, 12.13], "above, but inside the combined interval" (33 certified, 7 above alpha: draws 7, 19, 21, 32, 35, 36, 39 with 62-69 wrong). BX-FL 6.62 [4.58, 9.12]; LS-FL 7.00. H1, H2, H3 pass (vs arm X 4.25 and L-FL 6.80); all controls pass; C0a, C0b, z0 pass. LX-FL beats L-FL in 32 / 40 same draws (mean +2.18). safe-wpm/0.2 is a proposal: the proposed v0.2 values are not headlines. No score card now; if the user adopts v0.2, a v0.2 card + rerun recipe for EMG LX-FL follows.
- **Depends on:** P11-14 (done); safe-wpm/0.2 (proposed, P14-26); CPU.
- **Source:** P11-14 ([results](../../experiments/2026-11-20-p11-14-emg-lm-confidence/results.md)): the wide-set fused posterior `p_fU` and the LM log-prob per character carry the confidence gain for sentence commits. Word-prefix commits (P11-12 arm X, proposed v0.2 4.25) still use the built-in learned prefix score on the old decoder.
- **Done when:** a pre-registered prefix guard on the in-beam decoder uses the P11-14 signals (per prefix: the wide-set fused mass of the prefix and the LM per character) and reports a certified proposed-v0.2 value with the P11-12 controls, compared with arm X (4.25) and with L-FL (6.80 v0.1); or the result states with numbers why not.
- **Follow-ups:** gap 165 = [P5-35](#p5-35-native-calibrate-path-for-external-per-prefix-scores) (native `calibrate` path for external per-prefix scores); gap 166 = [P11-21](#p11-21-calibration-inclusive-lower-end-above-309-for-the-lx-fl-prefix-guard) (calibration-inclusive lower end above 3.09 for the LX-FL prefix guard).

#### P11-17 Calibration-inclusive safe WPM interval for the EMG P11-14 L-FL guard
- **Gap:** 133 of the [open-gap list](open-gaps.md) (added 2026-11-20 after P15-29). Follow-up of P11-14, P15-29.
- **Status:** `done` (2026-11-21; plan `7922ecf` before any number, code and tests `eecbac8`, results `a0993be`, [results](../../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md)). K = 40 calibration draws x user-cluster bootstrap: **5.00 [0.00, 9.55]** against no-BCI 3.09 (P11-14 with one calibration: 6.80 [4.49, 9.63]). Pre-registered verdict: "above, but inside the combined interval" (mean above 3.09, lower end not). 9 / 40 draws (22.5 %) are above alpha on the test set (62-76 wrong commits, rate 0.051-0.062; the draws with the most commits, 301-339) and earn 0 by the credit rule; LTT allows at most delta = 10 %. 31 certified draws: mean 6.46, range 1.14-7.27. All null controls pass in every draw. Between-draw SD 2.94, within-draw SD 1.19. Library `calibration_draw_interval`: 5.00 [0.00, 7.84]. Exploratory: above-alpha draws keep their value 6.63 [1.87, 9.88]; certified only 6.46 [1.42, 9.74]; none clears 3.09. X4 code check exact (z0 = P11-14: 285 commits, 52 wrong, 6.8031). Public wording changed (README, overview, north star, index, safe WPM write-up, docs/safe-wpm.md 6b). The card `emg2qwerty__p11-14-intended-lfl-subset8__guard` stays unchanged (valid single-calibration value under v0.1). Follow-ups: [P11-18](#p11-18-why-225--of-the-emg-calibration-draws-are-above-alpha) (gap 158), [P11-19](#p11-19-lower-variance-emg-l-fl-guard-with-a-calibration-inclusive-lower-end-above-no-bci) (gap 159).
- **Depends on:** P11-14 (done); P15-29 method (done; `fidetype.benchmark.safe_wpm.calibration_draw_interval`); CPU.
- **Source:** P11-14 ([results](../../experiments/2026-11-20-p11-14-emg-lm-confidence/results.md)) gives the L-FL guard a certified safe WPM v0.1 of 6.80 [4.49, 9.63]. This CI resamples trials with the decisions fixed. P15-29 showed on T15 that calibration-draw variation can be larger than the trial variation (ratio 4.1). P15-29 measured T15 and T12 only.
- **Done when:** a pre-registered run applies `calibration_draw_interval` to the P11-14 L-FL guard (same split, gate, LTT and controls; K stated in advance) and reports the calibration-inclusive interval against the EMG no-BCI reference 3.09.
- **Note (2026-11-21, P11-18, results `0a75695`):** limit (b) confirmed: the bootstrap draws over-state the failures (9 / 40 above alpha vs 3 / 40 with partition-only draws). Partition-only interval 5.65 [0.00, 9.45]. The EMG public wording does not change.

#### P11-18 Why 22.5 % of the EMG calibration draws are above alpha
- **Gap:** 158 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-17). Follow-up of P11-17.
- **Status:** `done` (2026-11-21; plan `6ce4245` before any number, code and synthetic tests `7537199`, launcher fix `b70aac7`, results `0a75695`, [results](../../experiments/2026-11-21-p11-18-emg-above-alpha/results.md)). Gap 158 closed. Partition-only arm P (40 draws, val -> test): 3 / 40 above alpha (7.5 %, inside delta), all three at 62 / 1,221 wrong. Interval **5.65 [0.00, 9.45]** vs 3.09: "above, but inside the combined interval" (library 5.65 [0.00, 7.76]; V-a 6.19 [2.62, 9.61]; V-b 6.10 [2.56, 9.51]). Pooled val + test arm E (no session shift): 0 / 40 above alpha. P11-17 bootstrap: 9 / 40. Pre-registered verdict: "partly duplicates" (Fisher 9 / 40 vs 3 / 40, p = 0.057). Session shift present: optimism gap arm P +0.0126 vs arm E -0.0016 (Welch p = 3.6e-10). 0 significant exceedances (consistent with test-rate noise). X4 reproduction exact. Between-draw SD 1.98, within 1.26. Follow-up: gap 164 = [P11-20](#p11-20-shift-robust-calibration-for-the-emg-l-fl-guard).
- **Depends on:** P11-17 (done; `experiments/2026-11-21-p11-17-emg-calibration-ci/run.py`); CPU.
- **Source:** P11-17 ([results](../../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md)): 9 of 40 calibration draws (22.5 %) of the L-FL guard are above alpha on the test set. LTT allows at most delta = 10 %. Three causes can add up: bootstrap duplicates in the resampled LTT part (459 entries, about 290 distinct prompts), sampling noise of the test rate (SD about 0.006 near 0.05 with 1,221 prompts), and the val / test session shift. On T15 (P15-29) only 2 / 40 draws failed.
- **Done when:** a pre-registered run of the L-FL guard with K >= 40 partition-only draws (new splits of the 1,224 calibration prompts, no resampling) reports the above-alpha fraction and the calibration-inclusive interval against 3.09, and says whether the excess over delta comes from bootstrap duplicates in the LTT part or from test-rate noise plus the val / test session shift.

#### P11-19 Lower-variance EMG L-FL guard with a calibration-inclusive lower end above no-BCI
- **Gap:** 159 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-17). Follow-up of P11-17, P15-37, P15-34.
- **Status:** `done` (2026-11-22). Gap 159 closed. (plan `c71c9bc`, code `1a281e6`, amendment 1 `445c714` + code `fca492e`, amendment 2 + code `c3df8ad`, results `749f192`, [results](../../experiments/2026-11-21-p11-19-multi-split/results.md)): primary arm BX3 (3 split guards per draw, partition-only draws, P11-23 L-FL margin alpha'' 0.0314, each at delta / 3 = Bonferroni / P15-37 rule B; deploy the guard with the highest in-sample safe WPM, on calibration data only). Calibration-inclusive safe WPM v0.1 5.90 [3.45, 8.89] vs no-BCI 3.09: the lower end is above by 0.36 (narrow; normal approximation [3.10, 8.70]). 0 / 40 draws above alpha; C-null 0 commits. Whole-sentence commits, so v0.1 = v0.2 here. Honest note: the done-when names BMED-3 or AND arms in its parenthesis. The median arm BD3 gives 5.19 [2.90, 8.19] and AND (AN3) 4.37 [2.17, 7.28]; both are NOT above 3.09. BX3 is the pre-registered primary, a Bonferroni + selection rule of P15-37, chosen on calibration data only. The why-not branch is also met: floor F_w BX3 3.35 (S2 3.05); a normal lower end of 3.09 needs 7.9 users (8 exist) and 1,182 calibration prompts (1,224 exist). Safety cost: BX3 test rate mean 0.028, max 0.0434; 13 / 40 draws above 0.0314, none above 0.05. It holds under assumption (A2), on 8 users and one test set; the interval method (safe-wpm.md 6b) is still proposed. Disclosed: two amendments before any phase-2 number; two wrong header times; a smoke run before the code commit (X01 only). CPU run 21:35 -> 01:07 (3.5 h, 2 workers x 1 thread).
- **Follow-ups:** gap 183 = [P11-28](#p11-28-safety-headroom-of-the-emg-bx3-guard) (BX3 headroom, low priority). Gap 180 = [P11-27](#p11-27-native-n-best-score-differences-in-the-p11-20--p11-23-analyser-memos) got new evidence.
- **Depends on:** P11-17 (done); the P15-37 result (gap 141; multi-split method); P15-34 (done; safety-margin guard); CPU.
- **Source:** P11-17 ([results](../../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md)): 5.00 [0.00, 9.55]; between-draw SD 2.94 against within-draw 1.19. EMG shows the same calibration-variance problem as T15 (gaps 132, 141).
- **Done when:** a pre-registered run applies the P15-37 multi-split method (BMED-3 or AND arms, chosen on calibration data only) or a safety-margin guard (P15-34) to EMG L-FL and reports a calibration-inclusive interval whose lower end is above 3.09, or numbers show why that is not reachable.
- **Evidence (2026-11-21, P15-37, results `105c5d0`):** on T15 the guarantee-keeping multi-split rules (AND, Bonferroni + selection) do not lift the calibration-inclusive lower end (primary BMED-3 4.73 [2.60, 6.24]; between-draw SD only 4-15 % lower). This item stays open: EMG differs, because its zero draws come from above-alpha draws (9 / 40). Gap 158 = [P11-18](#p11-18-why-225--of-the-emg-calibration-draws-are-above-alpha) diagnoses that first.
- **Evidence (2026-11-21, P11-18, results `0a75695`):** the val / test session shift is a separate failure source (optimism gap arm P +0.0126 vs pooled arm E -0.0016, Welch p = 3.6e-10). Lower-variance methods do not remove it. The shift part is gap 164 = [P11-20](#p11-20-shift-robust-calibration-for-the-emg-l-fl-guard).
- **Note (2026-11-21, P11-20, results `8cbd7b7`):** with the shift margin (LTT at alpha' 0.0455) no EMG draw earns 0. The calibration-inclusive lower end is 2.62 < 3.09 (6.13 [2.62, 9.47]). The within-draw user-cluster spread and one low-commit draw (2.25) limit it. This item stays open.
- **Note (2026-11-21, P11-21, results `ecbc7b1`):** the LX-FL prefix guard (PROPOSED v0.2, partition-only draws, LX shift margin m_LX 0.0288) reaches 5.67 [3.43, 8.26] > 3.09 (gap 166 closed). This item is about the L-FL guard under the adopted v0.1, so it stays open.

#### P11-20 Shift-robust calibration for the EMG L-FL guard
- **Gap:** 164 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-18). Follow-up of P11-18, P11-17.
- **Status:** `done` (2026-11-21; plan `20b5993` before any number, code `d3511df`, results `8cbd7b7`, [results](../../experiments/2026-11-21-p11-20-emg-shift-robust/results.md)). Gap 164 closed. Margin m from the P11-01 personal-val sessions a -> b only (never track val / test): m = 0.0045, LTT at alpha' = 0.0455; the guarantee holds under the stated bounded-shift assumption (A). Arm S (40 partition-only draws, same partitions as P11-18): 0 / 40 above alpha on test (P11-18: 3 / 40); pre-registered conclusions "margin removes the excess" and "(A) not contradicted on test" (mean test rate 0.0331). McNemar vs P11-18 p = 0.25 (not significant); optimism gap still +0.0126. Interval **6.13 [2.62, 9.47]** vs no-BCI 3.09: "above, but inside the combined interval" (library 6.13 [2.85, 7.76]). No draw earns 0; the lower end is now limited by the user-cluster spread and one low-commit draw (2.25). Two-step gap a -> track val -0.0044 (the shift changes by session). Secondary K = 80: 8 / 80 above alpha; Fisher 9 / 40 vs 8 / 80 p = 0.060, so "partly duplicates" is not firm (reasons in results.md). Checks C1, C2, X5 pass. The EMG public wording does not change.
- **Depends on:** P11-18 (done; `experiments/2026-11-21-p11-18-emg-above-alpha/run.py`); CPU.
- **Source:** P11-18 ([results](../../experiments/2026-11-21-p11-18-emg-above-alpha/results.md)): on a new session the wrong-commit rate is about 1.3 points above the LTT in-sample rate (optimism gap arm P +0.0126 vs pooled arm E -0.0016, Welch p = 3.6e-10). 3 / 40 partition-only draws are above alpha; 0 / 40 without the shift. The "partly duplicates" verdict is not firm at K = 40 (Fisher p = 0.057).
- **Done when:** a pre-registered run tests a shift-robust calibration for the L-FL guard (for example a tighter alpha, a margin from the val / test gap, or calibration that includes data from a second session) and reports the above-alpha fraction on test with 40 partition-only draws and the calibration-inclusive interval against 3.09. Secondary: K >= 80 arm P draws to make the "partly duplicates" verdict firm (Fisher p < 0.05), or numbers say why not.
- **Follow-ups:** gap 169 = [P11-22](#p11-22-firm-duplicates-verdict-for-the-emg-l-fl-calibration-draws) (firm "duplicates" verdict, low priority); gap 170 = [P11-23](#p11-23-robustness-of-the-emg-shift-margin-across-session-steps) (shift margin across session steps).

#### P11-21 Calibration-inclusive lower end above 3.09 for the LX-FL prefix guard
- **Gap:** 166 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-16). Follow-up of P11-16, P11-18, P11-19.
- **Status:** `done` (2026-11-21; plan `95b1a91` before any number, code `beac437`, amendment 1 + code `99b7eb6`, analysis fix `fef0abb`, results `ecbc7b1`, [results](../../experiments/2026-11-21-p11-21-lx-margin/results.md)). Gap 166 closed. EMG LX-FL prefix guard with partition-only draws and an LX-specific shift margin (m_LX 0.0288, alpha_LX 0.0212). Calibration-inclusive proposed v0.2 safe WPM **5.67 [3.43, 8.26]** vs no-BCI 3.09: "clearly above after calibration uncertainty", the first EMG lower end above 3.09. 0 / 40 draws above alpha, all certified, null controls 0. Narrow: the lower end clears 3.09 by 0.34, and one draw is 2.96. LX-T (L-FL margin) 7.21 [4.78, 10.43]. LX-P (no margin) 8.80 [4.89, 12.26], 1 / 40 above alpha, fragile. H3: LX-P 1 / 40 vs P11-16 7 / 40, Fisher p = 0.028. It holds only under the PROPOSED safe-wpm v0.2 (the user decides adoption) and under assumption (A2). Disclosed deviation: check X2 failed (203 / 2,442 session a / b windows had native n-best scores up to 8e-5 off the P11-20 / P11-23 memo); Amendment 1 replaced it with the fresh-decode check X2' before any margin or arm number existed, and X2' passes. Some stage-1 log lines had been seen, and the amendment header says 18:20 but it was written at about 18:08; results.md states all of this. The public EMG wording ("above on average, not reliably") does not change; that is a user decision.
- **Follow-ups:** gap 180 = [P11-27](#p11-27-native-n-best-score-differences-in-the-p11-20--p11-23-analyser-memos) (memo score differences; low priority). Gap 159 = P11-19 stays open.
- **Depends on:** P11-16 (done); gap 159 methods; the user decision on safe-wpm/0.2 (for headline use only); CPU.
- **Source:** P11-16 ([results](../../experiments/2026-11-21-p11-16-emg-prefix-confidence/results.md)): calibration-inclusive proposed v0.2 7.18 [0.00, 12.13]; 7 / 40 draws above alpha earn 0; between-draw SD 3.47 against within-draw 1.24.
- **Done when:** a pre-registered run (for example partition-only draws, a margin below alpha, or gap 159 methods) reports the calibration-inclusive interval against 3.09 for the prefix guard: lower end above 3.09, or numbers say why not. Headline use depends on the v0.2 decision.

#### P11-22 Firm duplicates verdict for the EMG L-FL calibration draws
- **Gap:** 169 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-20). Follow-up of P11-20, P11-18, P11-17.
- **Status:** `todo`. Low priority.
- **Depends on:** P11-20 (done; `experiments/2026-11-21-p11-20-emg-shift-robust/run.py`); P11-17 bootstrap draws; CPU.
- **Source:** P11-20 ([results](../../experiments/2026-11-21-p11-20-emg-shift-robust/results.md)): K = 80 partition-only draws give 8 / 80 above alpha (exactly delta); one-sided Fisher 9 / 40 (P11-17 bootstrap) vs 8 / 80, p = 0.060, so "partly duplicates" is not firm. The fixed 40-draw bootstrap side limits the power: with 18 / 80 bootstrap draws (same rate) p would be 0.026.
- **Done when:** a pre-registered run adds >= 40 P11-17-style bootstrap draws (K_B >= 80) and tests bootstrap vs the 80 partition-only draws with a one-sided Fisher test (p < 0.05 = firm "duplicates"), or numbers say why not.

#### P11-23 Robustness of the EMG shift margin across session steps
- **Gap:** 170 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-20). Follow-up of P11-20.
- **Status:** `done` (2026-11-21; plan `a03b20c` before any number, code `75e9689`, results `8c2298a`, [results](../../experiments/2026-11-21-p11-23-shift-margin-steps/results.md)). Gap 170 closed. Check X6 passes (40 / 40 draws reproduce P11-20). m2 = 0.0185 (upper 95 % bound over users, worse direction a -> b; b -> a is -0.0018), so alpha'' = 0.0314. Spread verdict: "the one-step margin of P11-20 under-states the spread". Arm S2: 0 / 40 test draws above alpha, so "the margin removes the excess" and "(A2) is not contradicted on test". Interval 5.47 [2.44, 8.77] vs no-BCI 3.09: "above, but inside the combined interval". The EMG public wording does not change. The cost: commits 245 -> 206, safe WPM 6.13 -> 5.47.
- **Follow-ups:** gap 173 = [P11-24](#p11-24-tell-the-two-emg-shift-margins-apart-on-held-out-users-or-new-sessions) (tell the two margins apart on held-out users or new sessions).
- **Depends on:** P11-20 (done); P11-01 sessions outside track val / test; CPU.
- **Source:** P11-20 ([results](../../experiments/2026-11-21-p11-20-emg-shift-robust/results.md)): m = 0.0045 comes from one session step per user (sessions a -> b, the checkpoint-selection sessions of the personal models). The two-step gap a -> track val is -0.0044, so the step size changes between sessions (results limits a, b).
- **Done when:** a pre-registered run estimates m from several session steps per user (for example train-session pairs that the personal models do not use, or a -> b plus leave-one-user-out), reports the spread of the step sizes, and re-checks the arm S above-alpha fraction on test with a margin rule that covers that spread (for example an upper quantile).

#### P11-24 Tell the two EMG shift margins apart on held-out users or new sessions
- **Gap:** 173 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-23). Follow-up of P11-23, P11-20.
- **Status:** `todo`. May be externally limited by data (held-out users or new sessions outside the current track val / test).
- **Depends on:** P11-23 (done; `experiments/2026-11-21-p11-23-shift-margin-steps/run.py`); held-out-user or new-session EMG data; CPU.
- **Source:** P11-23 ([results](../../experiments/2026-11-21-p11-23-shift-margin-steps/results.md)): on the current test set both margins (m = 0.0045 of P11-20 and m2 = 0.0185 of P11-23) give 0 / 40 draws above alpha, so this test cannot show that the larger margin is needed.
- **Done when:** a held-out-user or new-session check of (A2) is pre-registered and run, and it reports which margin keeps the test error at or below alpha.

#### P11-25 Revisit the P11-08 decoder target framing
- **Gap:** 178 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-10). Follow-up of P11-10, P11-08.
- **Status:** `done` (2026-11-21). Gap 178 closed. The [matched-target rule](frontier-decoder-quality.md#matched-emg-decoder-target-p11-25-2026-11-21) has two bars: Bar 1 compares only with the published number of the same condition (no LM + 100 ms lookahead 11.28 %; LM + 100 ms lookahead 6.95 %; no published number for a causal decoder); Bar 2 is the usability line (CER at or below about 10 %). Our numbers: P11-01 15.09 % (no LM, causal), P11-07 10.10 % (LM, causal); no matched number exists yet. P11-08 done-when and gap 88 restated; P11-07 results got a correction note (H2 compared a with-LM CER with 11.28 %).
- **Depends on:** P11-10 (done); text only (no compute).
- **Source:** P11-10 (2026-11-21, commit `70807b0`, [source](../sources/emg2qwerty.md)): 11.28 % (Table 3, p. 9) is a no-LM number, and the paper's model has 100 ms future context in training. Any with-LM decoder must compare with 6.95 %. The paper calls about 10 % CER or less usable; this line should be a criterion.
- **Done when:** P11-08 and gap 88 state the matched target (no-LM vs LM, lookahead) and the usability criterion, and the frontier pages agree.

#### P11-26 Check the CTRL-labs 2024 generic neuromotor paper
- **Gap:** 179 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-10). Follow-up of P11-10.
- **Status:** `done` (2026-11-22). Gap 179 closed. (commit `aab52bd`, [source](../sources/generic-neuromotor-interface.md)): the CTRL-labs generic neuromotor interface paper is ingested (Kaifosh, Reardon & CTRL-labs, Nature 645, 702-711, 2025; paper CC BY-NC-ND 4.0; the 2024 bioRxiv preprint was not read: HTTP 429). Verdict: confusion confirmed. Brain2Qwerty v2 (p. 10) cites emg2qwerty (Sivakumar et al., 2024) for "a causal Conformer with low-latency to decode handwriting". That model is the CTRL-labs 15-layer causal Conformer (past-only local attention, FastEmit; Methods, PDF pp. 15-16). emg2qwerty uses a TDS ConvNet for typing. Contradiction notes updated on 4 pages. New licence contradiction recorded: the paper says data / code CC BY-NC-SA 4.0, the repo says CC BY-NC 4.0 (both non-commercial). No new gap.
- **Depends on:** P11-10 (done); the paper (bioRxiv 10.1101/2024.02.23.581779).
- **Source:** P11-10 (2026-11-21, commit `70807b0`, [source](../sources/emg2qwerty.md)): the contradiction notes record that Brain2Qwerty v2 calls the emg2qwerty model a "causal Conformer", but the emg2qwerty paper uses a TDS ConvNet with 100 ms future context in training. Brain2Qwerty v2 may have confused emg2qwerty with the CTRL-labs 2024 generic neuromotor paper (bioRxiv 10.1101/2024.02.23.581779).
- **Done when:** that paper is ingested or checked, and the contradiction notes are updated.

#### P11-27 Native n-best score differences in the P11-20 / P11-23 analyser memos
- **Gap:** 180 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P11-21). Follow-up of P11-21, P11-20, P11-23.
- **Status:** `todo`. Low priority.
- **Depends on:** P11-21 (done; `experiments/2026-11-21-p11-21-lx-margin/x2_fresh.py`); the P11-20 / P11-23 analyser memos; CPU.
- **Source:** P11-21 (2026-11-21, results `ecbc7b1`, [results](../../experiments/2026-11-21-p11-21-lx-margin/results.md)): check X2 found 203 of 2,442 session a / b windows whose native n-best scores in the P11-20 / P11-23 analyser memos differ by up to 8e-5 from fresh decodes (fresh decodes match under both the current code and the P11-20 code snapshot `d3511df`). The cause is not known.
- **Done when:** the cause is found, or the memos are rebuilt and the P11-20 / P11-23 draws are shown to be unchanged.
- **Evidence (2026-11-22, P11-19, results `749f192`):** memo-vs-fresh differences also occur in track val / test windows and between processes (signals up to 3e-8, native scores up to 3.8e-5). They changed no action in check X1' (2 x 3 x 1,221 actions). This item stays open.
- **Evidence (2026-11-22, P11-28, results `75ae30f`):** fresh decodes in different processes give L-model parameters that differ by about 1e-8 (at most 9.7e-9) between memo and fresh decode, so the model digests differ; check X5 shows no decision change (0 differing actions in 2 split guards). This item stays open.

#### P11-28 Safety headroom of the EMG BX3 guard
- **Gap:** 183 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P11-19). Follow-up of P11-19.
- **Status:** `done` (2026-11-22). Gap 183 closed on its headroom branch. (plan `84d465f`, code `a8877bf`, amendment 1 `bf06ee9`, results `75ae30f`, [results](../../experiments/2026-11-22-p11-28-bx3-headroom/results.md)): verdict "BX3 safety holds with headroom". BX3: 0 / 80 draws above 0.05 (40 P11-19 + 40 new); the one-sided CP95 bound on P(rate > 0.05) is 0.0368 (0.072 with 40 draws); the 95 % upper bound on the 90th percentile is 0.0393, so the headroom is 0.0107 ("clear"). The new 40 draws alone: 0 / 40, max 0.0410, headroom 0.0090 (replicated). Value: new 40 draws 5.99 [3.52, 8.96], pooled 80 draws 5.95 [3.49, 8.92] vs no-BCI 3.09. 31 / 80 draws are above alpha'' 0.0314, so selection uses most of the m2 margin but none of the claim. No secondary rule (BXS, BX2, BD3, J1, AN3) gives more margin and keeps the value pass. Checks X1', X5 (amended), X4, X6 and C-null pass. Limits: one test set of 8 users (with the users reweighted, the worst draw is above 0.05 in about 5 % of the weight vectors); J = 4 and a lower `commit_p` floor were not run (reasons in the plan). Disclosed: amendment 1 (X5 model digest descriptive, because the L-model parameters differ by about 1e-8, gap 180; all decisions equal) came before any phase-2 number; the amendment header time is wrong (says 10:25, written about 10:20); no real-data smoke run before the code commit. CPU only; chain 2 10:21:24-12:53:28.
- **Follow-ups:** gap 193 = [P11-29](#p11-29-bx3-safety-headroom-on-a-new-session-or-test-set) (BX3 headroom on a new session or test set, low priority). Gap 180 = [P11-27](#p11-27-native-n-best-score-differences-in-the-p11-20--p11-23-analyser-memos) got new evidence.
- **Depends on:** P11-19 (done; `experiments/2026-11-21-p11-19-multi-split/run.py`); more draws or a new session; CPU. Low priority.
- **Source:** P11-19 (2026-11-22, results `749f192`, [results](../../experiments/2026-11-21-p11-19-multi-split/results.md)): BX3 has the highest test rate of the arms (mean 0.028, max 0.0434); 13 / 40 draws are above the margin level 0.0314 on test, none above 0.05.
- **Done when:** a pre-registered check with more draws or a new session reports the BX3 test-rate headroom against 0.05, or shows whether J = 2 / 4 or a lower `commit_p` grid floor keeps the pass with more margin; or numbers say why not.

#### P11-29 BX3 safety headroom on a new session or test set
- **Gap:** 193 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P11-28). Follow-up of P11-28, P11-24.
- **Status:** `todo`. Low priority.
- **Serves:** research labs.
- **Depends on:** P11-28 (done); a new emg2qwerty session or test users outside the current split (may be limited by data); CPU. Low priority.
- **Source:** P11-28 (2026-11-22, results `75ae30f`, [results](../../experiments/2026-11-22-p11-28-bx3-headroom/results.md)): 0 / 80 draws above 0.05, headroom 0.0107, but all draws share one test set of 8 users. With the users reweighted, the worst draw is above 0.05 in about 5 % of the weight vectors. 31 / 80 draws are above alpha'' 0.0314.
- **Done when:** a pre-registered check on a new session or a new test set reports the BX3 exceedance count above 0.05, its CP95 bound and the headroom at the delta-quantile; or numbers say why not (for example, no usable new data).

## Publications (no deadline)
Added 2026-11-13 (user decision). Review and publishing run on outside timelines. The user expects them to take 50 to 60 times longer than planned. So the papers are a separate track, **PUB**.
- PUB has no due date. It never counts as late. It is not part of the M1–M7 target or of any phase window.
- No phase waits on PUB. Papers are not exit criteria of any phase.
- Research results go to `experiments/` and the wiki first. Papers draw on them later.
- Value-first link (2026-11-15): [P14-08](#p14-08-results-write-ups) writes public result pages that papers may cite. It adds no paper deadline.
- Tracker: milestone `PUB` (Paper 1 tasks M3-03 … M3-26, Paper 2 M4-04 and M4-05, spec / benchmark paper P11-04 and P11-05; ids unchanged).

## P12. Beyond text: intent and control (added 2026-11-11)
**Goal:** the standard and the trust layer cover all neural input, not only text. Text entry stays first. This phase comes after the text work and does not change its priority.

**Scope (user decision, 2026-11-11):**
| Output | Examples | Trust behaviour |
|---|---|---|
| **Discrete intent** | Clicks, selections; commands for a wheelchair, a robot arm, a smart home | COMMIT / OFFER / ABSTAIN, as for text. A wrong-commit limit per command class (a "stop" is safer than a "go") |
| **Continuous control** | 2D cursor movement (velocity or position) | Confidence-gated and rate-limited actuation: velocity scaling by confidence, a dead-man hold, a safe-stop when confidence or signal quality drops |
| **Decoded speech** | Phonemes, words, optional synthesis audio | Same as text for the token output |

### Design rule
- A **modality- and output-agnostic core** (stream header, frame, timing, provenance, `meta`) plus **output profiles**: *text* (today's NTS), *discrete intent*, *continuous control*.
- The text profile does not change. No field of spec v0.1 changes. A profile adds event kinds or conventions only, through FEPs.
- Spec v0.1 already has parts to build on: `vocab_type = "command"`, the `pointer` event (3.7) and the Apple BCI HID bridge sketch (6.5) ([spec](../../spec/neuraltextstream-v0.1.md)). A non-normative note in [spec section 10](../../spec/neuraltextstream-v0.1.md#10-open-questions) records the idea.
- Name: "NeuralTextStream" stays the name of the text profile. The name of the core (a sibling name or an umbrella name) is an open decision for the FEP.
- **Target interface:** [Apple BCI HID](../entities/apple-bci-hid.md) (BCIs as standard input devices: buttons, pointer). The P3 HID exporter grows into an intent and pointer bridge.

**Progress (2026-11-13):** deliverables 1 and 2 are drafted as [FEP-0003](../../spec/feps/0003-intent-events.md) with a reference intent trust layer, conformance profile `fep-0003` and a public-data evaluation. See [intent events](../concepts/intent-events.md).

### Deliverables
1. FEP: core + output profiles; mapping of the v0.1 `pointer` and `decision` events into the profiles.
2. Discrete-intent profile: command vocabularies (`intent.*` conventions, to define), a risk level per command class, COMMIT / OFFER / ABSTAIN for intents.
3. Continuous-control profile: pointer semantics with confidence; a trust policy for actuation (velocity scaling, dead-man hold, safe-stop, rate limits). A simulator test shows that the policy stops within a set time when confidence drops.
4. Speech profile notes (the token output reuses the text profile).
5. Apple BCI HID mapping for intents and pointer, with a replay test.
6. Evaluation data: **to survey**. Candidates to check: BCI Competition data sets (cursor and motor-imagery tasks), intracortical cursor and reach data on DANDI (for example the FALCON benchmark sets), BrainGate cursor data. This wiki has **not verified** their licences. Product work uses only CC0 / CC BY data ([licence rule](project-plan.md#licence-rule)).

### Exit criteria
- The profile FEP is accepted. The text profile passes the conformance kit unchanged.
- One discrete-intent replay and one cursor replay emit valid streams. The actuation policy passes its simulator safety tests.
- Tests with real assistive devices (wheelchair, robot arm) and users: **externally blocked** (hardware, ethics approval, volunteers).

### Open-gap items (added 2026-11-23)
#### P12-08 Certified accidental-click rate
- **Gap:** 211 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the frontier plan). Follow-up of P12-02, P12-06.
- **Status:** `externally_blocked`.
- **Serves:** research labs.
- **Depends on:** pre-registration `29c1dc9`; the user downloads the BrainGate drag-and-drop data by hand (Dryad doi:10.5061/dryad.98sf7m0v1, CC0, about 8.2 GB; a login is needed) into `C:\Users\zhang\bci-data\raw\braingate-dragdrop\`; CPU.
- **Source:** frontier plan (user "go", 2026-11-23), direction 5. Pre-registration `29c1dc9` ([plan](../../experiments/2026-11-23-certified-click-rate/plan.md); the plan said "proposed P12-07" (corrected to P12-08 on 2026-11-24), but P12-07 is already "tests with real assistive devices", so this item is P12-08). Public click decoders give no false-click rate and no bound.
- **Done when:** the pre-registered run reports H1 (the false-click rate stays at or below the stated alpha on held-out blocks) and H2 (bits per second at the same false-click rate against a fixed-threshold and a smoothing baseline), or numbers say why not.


**Effort:** 20–35 agent-days; about 8 h user review. **Depends on:** P1 1.0 RC, P2, P3, P5.

## P13. Public benchmark hub (added 2026-11-11)
**Goal:** "ImageNet for BCI text entry", later for all intent: a public, reproducible leaderboard. It **extends P6** and does not duplicate it. P6 builds the first leaderboard (tracks, NTS submissions, controls). P13 makes it a hub.

### Deliverables
| Part | Content | New compared with P6 |
|---|---|---|
| Datasets | Replay adapters for SpanishBCBL MEG (research-only), Brain-to-Text '25 (CC0), one EMG dataset (Toronto sEMG or KT-sEMG, commercially clean) | A versioned dataset registry; adapter hashes |
| Metrics | CER / WER, eWPM against no-BCI, wrong-commit rate | **Guarantee reporting:** each entry states its CRC / LTT bound (α, δ, method, number and scope of calibration items) and the measured wrong-commit rate on test |
| Controls | Shuffled input and zeros (null) input, required | Shown next to each score |
| Submission | NeuralTextStream files (Arrow or JSON Lines) | Submission by pull request; CI scores it |
| Site | Static site (GitHub Pages) | Per-track pages, history, a rerun command per entry |
| Later | Intent tracks after P12 (discrete intent, cursor) | Metrics to define (for example time to target, wrong-action rate) |

### Exit criteria
- Three tracks (MEG, implant, EMG) with guarantee columns and controls. Every entry reruns from one command.
- CI scores a pull-request submission with no manual step.
- Outside datasets or outside tracks: **externally blocked**.

**Effort:** 10–20 agent-days; about 6 h user review. **Depends on:** P6, P4 replay adapters; P12 for intent tracks.
**Status (2026-11-18): P13-01 done** (design). [docs/hub-design.md](../../docs/hub-design.md), [summary and open questions](hub-design.md), [diagram 18](../diagrams/index.html). Versioned dataset registry `src/fidetype/benchmark/hub/datasets-0.1.json` (schema `fidetype.hub.dataset/0.1`) with entries for SpanishBCBL (MEG, research only), Brain-to-Text '25 (implant, CC0) and Toronto sEMG (EMG, CC BY 4.0; EMG choice decided: Q1); stdlib checker `python -m fidetype.benchmark.hub` + `tests/test_hub_registry.py`. Replay contract RA-1 … RA-10 over file / LSL / WebSocket (reuses the existing adapters), rerun recipe and levels (`rescore`, `replay`, `full`), versioning table, dataset governance, outlines for P13-02 and P13-03, seven questions for the user. **Decisions (2026-11-18, [design](../../docs/hub-design.md#decisions-2026-11-18)):** Q1 Toronto sEMG; Q2 private truth store for CC0 / CC BY tracks, maintainer scores research-only tracks (implementation P13-03); Q3 decoded text outside git (PR holds a pointer + SHA-256); Q4 research-only tracks in a separate marked section; Q5 `rescore`-only entries may rank, level shown; Q6 (user) yes, a project site from this repo (`tools/site/build.js`, manual-only `pages.yml`): built locally as P13-08, not published; Q7 founder signs now, second reviewer later.
- **P13-01 done when:** a design doc defines the registry schema (id, version, licence + research-only flag, citation, checksum / verify, download; no re-hosting), the replay contract for the three hub datasets, the rerun recipe, the versioning rules, the PR flow and guarantee reporting outlines and dataset governance; a registry file with the three hub datasets passes a checker test; a diagram is linked. Met 2026-11-18.

### Open-gap items (added 2026-11-18)
Follow-ups of P13-01. Full list: [open gaps](open-gaps.md). No existing item moved.

#### P13-06 Hub command line and rerun recipe
- **Gap:** 78 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P13-01). Follow-up of P13-01.
- **Status:** `done` (2026-11-18, code `81df2af`, [design section 12](../../docs/hub-design.md#12-hub-command-line-and-rerun-recipes-p13-06)). Hub command line `python -m fidetype.benchmark.hub` / `fidetype hub` with `list`, `show`, `instructions` (prints the official source only; never downloads or re-hosts), `verify` (size + SHA-256 of local files, 1 MiB chunks), `check` (registry or one entry), `recipe` and `rerun` (level `rescore`). Rerun recipe `fidetype.hub.recipe/0.1` (dataset id / version / revision, track + split digest, adapter module + package version + source SHA-256 (RA-9), decoder, policy, scorer + metric versions, exact commands) in all 52 committed cards (backfill `tools/benchmark/add_rerun_recipes.py`; no other field changed) and in every new card (the scorer adds it). Leaderboard: `Rerun` column + a "Rerun recipes" block per track; site rebuilt locally, link check passes, not published. `fidetype hub rerun` gave the same card byte for byte (without the `rerun` block) for `b2t25-t15__published__ltt`, `b2t24-t12__t12v2__guard` and `toronto-semg__cnn-calib__crc`. Done-when parts (1) partly (no `replay`), (2) yes, (3) no, (4) no, (5) at level `rescore` only, (6) no: the rest is P13-10 (gap 82); recipe gaps are P13-11 (gap 83).
- **Depends on:** P13-01 (done); P6-10 for the `training_data` field.
- **Source:** P13-01 ([design](../../docs/hub-design.md#42-rules)): replay rules RA-4 (unit hash in the stream header), RA-7 (one test that replays a stream over file, LSL and WebSocket and compares the decisions) and RA-9 (adapter hash in the result) are not met. No command reads the registry, and result cards have no rerun recipe.
- **Done when:** (1) `fidetype hub list | info | verify | replay | rerun` exists and reads `datasets-0.1.json`; (2) score cards carry the rerun recipe of design section 5.1 with the adapter hash; (3) the three hub adapters write the track and unit hash into the header meta; (4) a test replays one stream over file, LSL and WebSocket and gets the same decisions; (5) `fidetype hub rerun` reproduces one committed `b2t25-t15` card byte for byte (level `replay`); (6) the dataset fields of `tracks.py` read from the registry without a change to any split file.

#### P13-07 Registry entries for the other v0.2 datasets and missing checksums
- **Gap:** 79 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P13-01). Follow-up of P13-01, P6-01.
- **Status:** `todo`.
- **Depends on:** P13-01 (done); local copies of the datasets (CPU, download only).
- **Source:** P13-01 (`src/fidetype/benchmark/hub/datasets-0.1.json`): only the three hub datasets are registered. The B2T '25 HDF5 zip (`t15_copyTask_neuralData.zip`) has no recorded size or SHA-256, and SpanishBCBL (316 files, no archive) has no per-file manifest; both rely on split fingerprints only.
- **Done when:** registry entries for B2T '24, Willett handwriting, KT-sEMG and emg2qwerty pass the checker and the test; the B2T '25 HDF5 form has its size and SHA-256; SpanishBCBL has a committed per-file size (and hash, where the source gives one) manifest with a verify command.

#### P13-08 Project site (local build)
- **Status:** `done` (2026-11-18). Hub decision Q6 (user): "i would like to have a site".
- **Deliverable:** `node tools/site/build.js` builds a static site into `_site/` (git-ignored) from repository files only: landing page from `README.md` (what Fidetype is, the north star, quick start), benchmark overview from the tracks v0.2 split files and `benchmark/site/leaderboard.json` (safe WPM v0.2 marked from the status line of its proposal), the generated leaderboard, the hub registry page from `datasets-0.1.json`, the certified list from `spec/conformance/certified.json` (with the evidence reports), the docs, `benchmark/README.md`, `spec/README.md` and the current NTS RC rendered from Markdown by `tools/site/md.js` (no dependencies; GitHub heading ids), and the demo, diagrams and progress pages. No JavaScript of ours, no external requests, no trackers; dark mode; phone width. Checked with headless Edge at 1280 px and 390 px; local link check passes.
- **Published (2026-11-21):** the site is live at https://zhangzibo.github.io/fidetype/ and deploys on every push to `main` (user decision, commit `f64b65a`). D6: the progress dashboard is public.
- **Not done here:** publishing. The maintainer runs `.github/workflows/pages.yml` by hand ([publishing checklist](../../docs/publishing-checklist.md) section G). A fuller docs site stays P8-05.

#### P13-09 Per-track leaderboard pages with stable anchors and history
- **Gap:** 80 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P13-08). Follow-up of P13-08, P6-03.
- **Status:** `done` (2026-11-18). The leaderboard generator (`python -m fidetype.benchmark leaderboard`) writes one page per track, `benchmark/site/tracks/<track>.html`, and `benchmark/site/history.json`. Stable anchors: `index.html#track-<track>` (track heading, now an `h3` with an `id`), `tracks/<track>.html`, `tracks/<track>.html#e-<card file name>` (one entry), `#entries`, `#history`, `#details`. The entry history comes from git (new module `fidetype.benchmark.entry_history`): for each commit that added or changed a card file (`git log --no-renames`), the card as it was at that commit gives the date, the commit, the changed top-level fields, the split version and digest, the scorer and metric versions, the rerun level, eWPM and safe WPM. Uncommitted cards get a "working tree" row; deleted cards are listed as removed; without git (or in a shallow clone) the page says that there is no history. The main page groups the tracks into v0.2 clean, research-only (separate, marked) and v0.1; each decoder cell links to its entry. Site: track pages at `benchmark/tracks/` with the safe WPM v0.2 PROPOSED bar; the benchmark overview links each track row to its page; local link check passes; not published. Tests: `tests/test_leaderboard_track_pages.py`. The guarantee columns of P13-02 are still open there. Follow-up: P13-12 (gap 84).
- **Depends on:** P13-08 (done); P13-02 for the guarantee columns.
- **Source:** P13-08 (2026-11-18): the generated leaderboard (`python -m fidetype.benchmark leaderboard`) is one long page. Its track headings have no `id`, so the site and the docs cannot link to one track. There is no per-track page and no history of entries over versions, which the P13 deliverable "Site" asks for.
- **Done when:** the leaderboard generator writes one page per track (or stable `id` anchors per track) with the entry history (date, split, scorer and metric versions); the site links each track row of the benchmark overview to it; the site link check passes.

#### P13-10 Hub replay command, unit key, transport test and replay-level rerun
- **Gap:** 82 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P13-06). Follow-up of P13-06.
- **Status:** `todo`.
- **Depends on:** P13-06 (done); local copies of the hub datasets (CPU only).
- **Source:** P13-06 (2026-11-18, [design section 12.5](../../docs/hub-design.md#125-not-done-here)): the hub command line and the recipes exist, but these P13-06 done-when parts are not met: no `fidetype hub replay`; rule RA-4 (track and unit hash in the stream header meta) not met by the three hub adapters; no RA-7 test that replays one stream over file, LSL and WebSocket and compares the decisions; the checked reruns are level `rescore`, not `replay`; the dataset fields of `tracks.py` do not read from the registry.
- **Done when:** (1) `fidetype hub replay <dataset> --data <path> --track <track>` writes NTS streams from the registered adapter; (2) the three hub adapters write the track and the unit hash into the header meta; (3) a test replays one stream over file, LSL and WebSocket and gets the same decisions; (4) `fidetype hub rerun` reproduces one committed `b2t25-t15` card byte for byte at level `replay`; (5) the dataset fields of `tracks.py` read from the registry with no change to any split file.

#### P13-11 Complete rerun recipes: weights hash, policy config id, hallucination cards
- **Gap:** 83 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P13-06). Follow-up of P13-06, P15-15.
- **Status:** `done` (2026-11-19, code `a7f0b6b`, fix `7b6cdd7`, [design 12.6](../../docs/hub-design.md#126-weights-hash-config-id-and-hallucination-recipes-p13-11)). A recipe holds a value or a reason for `decoder.weights_sha256` and `policy.config_id`; `check_recipe` accepts exactly one. 52 leaderboard cards: weights 30 filled / 22 reasons; `config_id` 6 filled (every guard card) / 46 reasons (16 always-commit, 30 TrustPipeline fits never frozen: P13-13). The weights stay outside the repo (hashed read only; `--runs` re-hashes them). Every hallucination card (32) has a `fidetype.hub.recipe/0.1` block at level `rescore` that passes `check_recipe`; all 32 commands reproduce their card; CI checks the recipes (`tests/test_hub_cli.py` in the pytest jobs and the `leaderboard` job). No released weights exist yet (P14-02): the hashes identify the local files. Follow-up: P13-13 (gap 85).
- **Depends on:** P13-06 (done); P14-02 for released weights.
- **Source:** P13-06 (2026-11-18): the backfilled recipes have `decoder.weights_sha256: null` (no weights released) and `policy.config_id: null` (the cards predate the frozen `config_id` of P5-23). The hallucination score cards (`benchmark/results/halluc-v0.1/`, `halluc-v0.2/`) have no `rerun` block; they rerun only with `python -m fidetype.benchmark.hallucination rescore`.
- **Done when:** every guard card records the frozen policy `config_id` (or says why none exists); a card with released weights records their SHA-256; every hallucination card carries a `fidetype.hub.recipe/0.1` block that passes `check_recipe`, and CI checks it.

#### P13-12 Leaderboard freshness check and same-commit history rows
- **Gap:** 84 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P13-09). Follow-up of P13-09.
- **Status:** `done` (2026-11-19, code `a7f0b6b`, [design 12.7](../../docs/hub-design.md#127-leaderboard-freshness-check-p13-12)). History base = the parent of the commit that holds the pages; card changes in that commit get a "this commit / with this page" row; the build falls back to base `HEAD` when the committed pages are stale. `python -m fidetype.benchmark.leaderboard --check` in the new CI job `leaderboard` (`fetch-depth: 0`, needed by `all-green`); it passed on the code commit (run 44486952789). The regeneration step is documented in `benchmark/README.md` and design 12.7.
- **Depends on:** P13-09 (done).
- **Source:** P13-09 (2026-11-18): the entry history reads git at generation time. A card that is committed together with its regenerated pages shows a "working tree, not committed" row until the next regeneration. No CI job regenerates the leaderboard outputs (`benchmark/site/`) and compares them with the committed files, and the CI checkout is shallow (no history).
- **Done when:** a CI job with a full-history checkout regenerates `benchmark/site/` and fails on a difference; the regeneration step after a card commit is documented (or automated) so that no committed track page keeps a stale "working tree" row.

#### P13-13 Frozen trust configs for the pre-P5-23 trust cards
- **Gap:** 85 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P13-11). Follow-up of P13-11.
- **Status:** `done` (2026-11-21; commit `1168b34`). Gap 85 closed. All 30 pre-P5-23 trust cards (b2t25-t15 ours / published, spanishbcbl-meg, toronto-semg; v0.1 / v0.2 pairs) were refit with the build-step settings and frozen in 15 configs. A pipeline built from the loaded file alone gives the same decisions as each card (0 differences on real input and on both controls). Thresholds and calibration scores are equal; no headline number changed. Every trust card now has `config_id` + `config_id_source`. The new `config_id_problems` check and tests (`tests/test_hub_cli.py`) flag any future trust card without a valid `config_id`. Limit: the toronto v0.1 cards hold only aggregates, so they are checked by commit count; their v0.2 twins are checked per unit. No new gaps.
- **Depends on:** P13-11 (done); the local decoder outputs of the build steps (CPU only).
- **Source:** P13-11 (2026-11-19, code `a7f0b6b`): 30 trust cards (CRC, LTT and plug-in policies on `b2t25-t15`, `b2t25-t15-copytask`, `spanishbcbl-meg`, `spanishbcbl-meg-async`, `toronto-semg`, `toronto-semg-composed`) record `config_id_reason`: the build steps (`experiments/2026-11-17-p6-02b-v02-entries/run.py` stages `b2t`, `meg`, `toronto`, and the v0.1 source experiments) fitted a TrustPipeline in memory and kept only the decisions.
- **Done when:** for each of the 30 cards, a refit with the build-step settings gives the same decisions as the card, `FrozenTrustConfig.from_pipeline` freezes it (numbers only, committed), and the recipe records its `config_id` and `config_id_source`; a card whose refit does not reproduce keeps a reason that says so.

#### P13-14 Rescore the tracks-v0.1 benchmark cards under safe-WPM v0.2
- **Gap:** 204 of the [open-gap list](open-gaps.md) (added 2026-11-23 by P14-61). Follow-up of P14-61, P13-13.
- **Status:** `todo`. Optional.
- **Serves:** research labs.
- **Depends on:** P14-61 (done); the per-trial sources of the tracks-v0.1 cards (local derived data); CPU. Optional.
- **Source:** P14-61 (2026-11-23, commit `38f1e50`): the leaderboard headline column is v0.2. The tracks-v0.1 cards keep their v0.1 numbers, because their per-trial sources are not all at hand.
- **Done when:** each tracks-v0.1 card has a v0.2 score next to its v0.1 score (the v0.1 number keeps its value and its label), or a recorded reason why its per-trial source cannot be rebuilt.

## P14. Value first: a useful toolkit (added 2026-11-15)
**Goal:** people install `fidetype` because it is useful today, not only because it is a format. The format spreads as a side effect, as with LangChain ([LangChain case study](../sources/case-study-langchain.md)). P14 adds user value and credibility. It does not change the scope, order or priority of P1–P13.

**User decision (2026-11-15):** adoption needs real user value and credibility. The user added this phase. No existing item moves, changes its ID or changes its priority. Where an existing item already covers a part, P14 references it and adds only the missing part.

**Audiences:** each item names the audiences that it serves. The five audiences, their pain today and what is built: [who uses Fidetype](who-uses-fidetype.md).

### Deliverables
| ID | Item | Builds on (existing items) | Serves |
|---|---|---|---|
| **P14-01** | Pretrained decoders + one-line load and decode, output in NTS | M4-12, P4-01, P11-01, P2-06, P5-03 | small teams, research labs |
| **P14-02** | Weight release decision and hosting (user-owned) | P14-01, P2-07, M7-09 | small teams, research labs |
| **P14-03** | Trust layer as a drop-in wrapper for any decoder + 10-minute quickstart | P4-07, P5-02, P5-07, M2-19, P8-02 | BCI companies, research labs, small teams |
| **P14-04** | Live decode from lab tools: LSL, BrainFlow, OpenBCI boards | P4-02, P14-01, P14-03; real boards: P4-06 | research labs, small teams |
| **P14-05** | Headline metric: safe words per minute at a guaranteed wrong-commit rate | P6-02, P6-03, P13-02 | research labs, BCI companies |
| **P14-06** | Visible demo: recorded EMG → text typed on screen, trust decisions shown | P14-01, P14-03, P8-05; later P8-03 | all audiences (first look); small teams |
| **P14-07** | Live demo with a real wristband (hardware: user decision) | P14-06, P4-05, P4-06 | BCI companies, small teams |
| **P14-08** | Results write-ups (credibility), linked to the paper track | P14-01, P14-05, PUB (P11-04, M4-04) | research labs, BCI companies, clinical trials |
| **P14-09** | Example AAC integration: NTS into an open-source AAC or text-entry app | P3 WebSocket exporter, P14-03, P14-06; pilot: P10-05 | AAC app makers |
| **P14-10** | Safe WPM on the remaining tracks (b2t24-t12, willett-hw, kt-semg, emg2qwerty, P11-01) (open gap 8, [details](#p14-10-safe-wpm-on-the-remaining-tracks-b2t24-t12-willett-hw-kt-semg-emg2qwerty-p11-01)) | P14-05, P6-01 (done), P6-02, P11-01 | research labs, BCI companies |
| **P14-12** | Willett-hw: word LM for exact-sentence commits and full test coverage (open gap 26, [details](#p14-12-willett-hw-word-lm-for-exact-sentence-commits-and-full-test-coverage)) | P6-02 (done); a word LM (for example the Tatoeba word LM of the T12 v2 recipe, or the published 50k-word n-gram); P15-08 (Willett decoder of our own, for full coverage) | research labs, BCI companies |
| **P14-13** | Conformant EMG baselines without oracle key timing (kt-semg, emg2qwerty) (open gap 27, [details](#p14-13-conformant-emg-baselines-without-oracle-key-timing-kt-semg-emg2qwerty)) | P11-01 (continuous EMG decoder); P4-10 (live key-onset detector) | research labs, BCI companies |
| **P14-14** | T12 safe WPM above the no-BCI reference (open gap 29, [details](#p14-14-t12-safe-wpm-above-the-no-bci-reference)) | M4-13 (stronger T15 recipe to port), P15-19 (usefulness on stronger decoders), P6-06 | research labs, BCI companies |
| **P14-15** | Word-decoder settings tuned without evaluation trials (T15) (gap 35, done: no effect on the re-split rows; [details](#p14-15-word-decoder-settings-tuned-without-evaluation-trials-t15)) | — | research labs, reviewers |
| **P14-18** | M4-x word-level results with word settings tuned without val_eval trials (T15) (gap 44, done 2026-11-17: effect, all changes favour edit 8, follow-up P14-21; [details](#p14-18-m4-x-word-level-results-with-word-settings-tuned-without-val_eval-trials-t15)) | P14-15 | research labs, reviewers |
| **P14-19** | Re-split published-gate rows, forward chain and downstream tables with per-fit word settings (gap 45, done 2026-11-17: re-split rows no effect, forward-chain prefix 0 corrected, follow-up P14-22; [details](#p14-19-re-split-published-gate-rows-forward-chain-and-downstream-tables-with-per-fit-word-settings)) | P14-15 | research labs, reviewers |
| **P14-21** | M4-x / M2-19 / P15-05..07 / P5-02 rows with the T15 word decoder tuned without val_eval (edit penalty 8) (gap 50, done 2026-11-18: effect on trust commit counts, no guarantee breaks, M4-13 safe WPM 2.28, follow-ups P14-24, P14-25; [details](#p14-21-m4-x-rows-with-the-t15-word-decoder-tuned-without-val_eval-edit-penalty-8)) | P14-18 | research labs, reviewers |
| **P14-22** | R3-level analyses on the re-split tables with per-fit word settings (open gap 51, [details](#p14-22-r3-level-analyses-on-the-re-split-tables-with-per-fit-word-settings)) | P14-19 | research labs, reviewers |
| **P14-23** | T15 safe WPM above the no-BCI reference with our causal decoder (gap 53, done 2026-11-19 by P15-22: 4.91 [4.25, 5.57] safe WPM v0.1, [details](#p14-23-t15-safe-wpm-above-the-no-bci-reference-with-our-causal-decoder)) | P14-05, M4-13 | research labs, BCI companies |
| **P14-24** | F2 and M4-13 trust-rerun rows with word-decoder edit penalty 8 (open gap 62, [details](#p14-24-f2-and-m4-13-trust-rerun-rows-with-word-decoder-edit-penalty-8)) | P14-21 | research labs, reviewers |
| **P14-25** | P3-08 collector replays with edit penalty 8 and a keep-awake (open gap 63, [details](#p14-25-p3-08-collector-replays-with-edit-penalty-8-and-a-keep-awake)) | P14-21 | research labs, reviewers |
| **P14-30** | Clean-machine README test of the pretrained decoders (P14-01 done criterion) (open gap 98, [details](#p14-30-clean-machine-readme-test-of-the-pretrained-decoders-p14-01-done-criterion)) | P14-01 | small teams, research labs |
| **P14-31** | Packaged trust config for t12-v2 (word trigram LM in the text decoder) (open gap 99, [details](#p14-31-packaged-trust-config-for-t12-v2-word-trigram-lm-in-the-text-decoder)) | P14-01 | small teams, research labs |
| **P14-32** | Toronto sEMG key-press CNN in the pretrained registry (open gap 100, [details](#p14-32-toronto-semg-key-press-cnn-in-the-pretrained-registry)) | P14-01 | small teams, research labs |
| **P14-33** | Willett handwriting decoder of our own in the pretrained registry (open gap 101, [details](#p14-33-willett-handwriting-decoder-of-our-own-in-the-pretrained-registry)) | P14-01 | small teams, research labs |
| **P14-34** | Language-agnostic pipeline audit (per-language config) (open gap 106, [details](#p14-34-language-agnostic-pipeline-audit-per-language-config)) | P14-01, P14-03, P14-05 | research labs, BCI companies, AAC app makers |
| **P14-35** | End-user typing UI (open gap 111, [details](#p14-35-end-user-typing-ui)) | P14-06, P14-09, P8-05 | AAC app makers, small teams |
| **P14-36** | Usability study of the typing UI (open gap 112, [details](#p14-36-usability-study-of-the-typing-ui)) | P14-35, M6-04 | AAC app makers, small teams |
| **P14-37** | Packaged installer for end users (open gap 115, [details](#p14-37-packaged-installer-for-end-users)) | P2-08, P14-35 | AAC app makers, small teams |
| **P14-38** | Language hook in safe WPM, the benchmark scorer and the hallucination protocol (open gap 117, [details](#p14-38-language-hook-in-safe-wpm-the-benchmark-scorer-and-the-hallucination-protocol)) | P14-34 | research labs, BCI companies |
| **P14-39** | Words per minute for scripts without spaces (open gap 118, [details](#p14-39-words-per-minute-for-scripts-without-spaces)) | P14-34 | research labs, BCI companies |
| **P14-40** | Per-language models and vocabulary registry (open gap 119, [details](#p14-40-per-language-models-and-vocabulary-registry)) | P14-34, P15-31, P15-32 | research labs, BCI companies, AAC app makers |
| **P14-41** | Trust guard for `willett-hw` (gap 121, done 2026-11-20, offer-only, [details](#p14-41-trust-guard-for-willett-hw)) | P14-33 | research labs |
| **P14-42** | Device and dataset adapter catalogue and contributor template (open gap 127, [details](#p14-42-device-and-dataset-adapter-catalogue-and-contributor-template)) | P4-15, P4-01, P4-02 | BCI companies, research labs, small teams (contributors) |
| **P14-43** | 10-minute tutorials (gap 128, done 2026-11-20, [details](#p14-43-10-minute-tutorials)) | P14-01, P14-03, P13-06 | small teams, research labs, newcomers |
| **P14-44** | Pretrained API newcomer ergonomics (gap 129, done 2026-11-20, [details](#p14-44-pretrained-api-newcomer-ergonomics)) | P14-43 | small teams, newcomers |
| **P14-45** | TrustGuard decisions to safe WPM in one call (gap 130, done 2026-11-20, [details](#p14-45-trustguard-decisions-to-safe-wpm-in-one-call)) | P14-43 | research labs, small teams |
| **P14-46** | Benchmark glue for custom splits and pretrained decoders (gap 131, done 2026-11-20, [details](#p14-46-benchmark-glue-for-custom-splits-and-pretrained-decoders)) | P14-43 | research labs, small teams |
| **P14-47** | Certified, non-vacuous trust guard for `willett-hw` (commits > 0) (open gap 138, [details](#p14-47-certified-non-vacuous-trust-guard-for-willett-hw-commits--0)) | P14-41 | research labs |
| **P14-48** | `willett-hw` with the same-LM readout and a no-signal gate (gap 144, done 2026-11-21, [details](#p14-48-willett-hw-with-the-same-lm-readout-and-a-no-signal-gate)) | P14-33, P15-25 | research labs |
| **P14-49** | No-signal gate for `willett-hw` that stops time-shuffled input (gap 145, done 2026-11-21, [details](#p14-49-no-signal-gate-for-willett-hw-that-stops-time-shuffled-input)) | P14-48, P11-12 | research labs |
| **P14-50** | Willett-blocked Tatoeba LM as the `willett-hw` LM readout (gap 146, done 2026-11-21, [details](#p14-50-willett-blocked-tatoeba-lm-as-the-willett-hw-lm-readout)) | P14-48, P15-38 | research labs |
| **P14-51** | Toy models for the xbody-ctc, crt-ctc and key-lda runtimes (gap 147, done 2026-11-21, [details](#p14-51-toy-models-for-the-xbody-ctc-crt-ctc-and-key-lda-runtimes)) | P14-44 | small teams, newcomers |
| **P14-52** | KT-sEMG item count from the key log alone (gap 148, done 2026-11-21, [details](#p14-52-kt-semg-item-count-from-the-key-log-alone)) | P14-44, P14-46 | small teams, research labs |
| **P14-53** | Tutorial 3 real mode re-run after the P14-46 changes (gap 149, done 2026-11-21, [details](#p14-53-tutorial-3-real-mode-re-run-after-the-p14-46-changes)) | P14-43, P14-46 | small teams, newcomers |
| **P14-54** | Frame-order-aware no-signal gate or offer check for `willett-hw` (gap 150, done 2026-11-21, [details](#p14-54-frame-order-aware-no-signal-gate-or-offer-check-for-willett-hw)) | P14-49, P5-31 | research labs |
| **P14-55** | Robustness check of the `willett-hw` gate C5 (gap 151, done 2026-11-21, [details](#p14-55-robustness-check-of-the-willett-hw-gate-c5)) | P14-49 | research labs |
| **P14-56** | Offer-control result in the packaged manifests and model cards (gap 153, done 2026-11-21, [details](#p14-56-offer-control-result-in-the-packaged-manifests-and-model-cards)) | P5-31, P14-01 | research labs, small teams |
| **P14-57** | Direction-aware offer check for `willett-hw` (gap 171, done 2026-11-21, negative result, [details](#p14-57-direction-aware-offer-check-for-willett-hw)) | P14-55, P14-54 | research labs |
| **P14-58** | C5 threshold rule that does not use the minimum real score (gap 172, done 2026-11-21, [details](#p14-58-c5-threshold-rule-without-the-minimum-real-score)) | P14-55, P14-49 | research labs |
| **P14-59** | Ship the P14-58 C5 threshold in the `willett-hw` manifest: user decision (open gap 182, [details](#p14-59-ship-the-p14-58-c5-threshold-in-the-willett-hw-manifest)) | P14-58, P14-56 | research labs |
| **P14-60** | Ship the `lm_beam_direction` offer gate in the `willett-hw` manifests, only if gap 189 passes (open gap 190, [details](#p14-60-ship-the-lm_beam_direction-offer-gate-in-the-willett-hw-manifests)) | P5-36, P14-56 | research labs |
| **P14-61** | Switch the scorer and the leaderboard to the adopted safe-WPM v0.2 (open gap 196, [details](#p14-61-switch-the-scorer-and-the-leaderboard-to-the-adopted-safe-wpm-v02)) | P14-26, P14-28, P15-29 | research labs, small teams |

#### P14-01 Pretrained decoders, one-line load and decode
- **Serves:** small teams, research labs ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** `pip install fidetype` gives decoders for the public datasets that we use. One line loads a model. One line decodes a recording into NTS.
- **Deliverable:** a `fidetype.pretrained` module (name to decide). Example shape: `m = fidetype.pretrained.load("t15-speech"); stream = m.decode(path)`. Models:

  | Model | Data | Data licence | Weights status |
  |---|---|---|---|
  | Implant speech (T15) | Brain-to-Text '25 | CC0 1.0 | Clean. Can ship after P14-02 |
  | Implant handwriting | Willett handwriting 2021 | CC0 1.0 | Clean. Needs a trained decoder first |
  | Wrist EMG typing (clean) | Toronto sEMG or KT-sEMG | CC BY 4.0 (attribution) | Clean, with attribution in the model card |
  | Wrist EMG typing (emg2qwerty) | emg2qwerty | CC BY-NC-SA 4.0 | **Research only.** Never in the wheel. Separate opt-in download. The user must accept the licence. The weights keep the share-alike terms |

  Licence sources: [`LICENSES/DATA.md`](../../LICENSES/DATA.md), [Willett handwriting](../entities/willett-handwriting-2021.md), [KT-sEMG](../entities/kt-semg-dataset.md), [emg2qwerty](../entities/emg2qwerty.md).
- **Rules:** weights are not in the git repository and not in the wheel. The package downloads them on first use and checks a SHA-256. Each model card states the data, the licence, the metrics and the limits. Each output stream carries `decoder.weights_sha256` and the licence flag of the [provenance ledger](../concepts/provenance-ledger.md) (P5-03). DATA.md rule 1 ("no trained weights") changes only after P14-02.
- **Depends on:** M4-12 (T15 decoder), P4-01 (replay adapters), P11-01 (EMG decoders), P2-06 (packaging), P5-03 (licence flags).
- **Done when:** on a clean machine, `pip install fidetype` and two lines decode one test file of each clean dataset into NTS that passes the conformance level `provenance`. A fresh subagent with no context does this from the README alone. The metrics in each model card match a rerun. No weights are in the repository.
- **Status (2026-11-19): in progress** (done criterion not met: the weights are not hosted, so the clean-machine README test waits for P14-02; gap 98 = P14-30). Built ([docs](../../docs/pretrained-decoders.md), code [`src/fidetype/pretrained/`](../../src/fidetype/pretrained/__init__.py), commit `2442cbd`): `fidetype.pretrained.load(name)` (alias `fidetype.decoders.load`) -> `.decode(file or array)` -> NTS streams at level `provenance` (`decoder.weights_sha256`, `data.licence`, `data.research_only`), `.guard()` -> the committed trust config, CLI `fidetype decoders list|info|path|verify|decode`. One manifest per model (input spec, files with SHA-256 + size + empty `url` slot, FEP-0010 licence keys, proposed weights licence, metrics, limits). Weights load from `weights=`, `FIDETYPE_PRETRAINED_DIR` or `~/.cache/fidetype/pretrained`; none in git or the wheel (CI checks the wheel). Licence gate: `emg2qwerty-p11-01` (CC BY-NC-SA 4.0) refuses without `accept_research_only=True`. NumPy runtimes, no torch. Models: `t15-m4-13`, `t12-v2`, `kt-semg-lda`, `emg2qwerty-p11-01` available locally; `willett-hw` (gap 101 = P14-33) and `toronto-semg-cnn` (gap 100 = P14-32) planned; T12 guard not packaged (gap 99 = P14-31). Rerun of the card metrics ([results](../../experiments/2026-11-19-p14-01-pretrained/results.md)): T15 val_eval PER 0.1210 (card 0.1210), guard decisions equal to P14-05 on 701 / 701 (104 commits, 17 wrong); T12 test PER 0.2695 (0.269); emg2qwerty generic prompt CER 0.5831 (0.5832); KT run28 key accuracy 0.242 (0.248, other timing path). Hosting = user step, [publishing checklist section J](../../docs/publishing-checklist.md).

#### P14-02 Weight release decision and hosting
- **Serves:** small teams, research labs ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** a recorded user decision on where the weights live (for example, GitHub release assets or a model hub) and on the change to DATA.md rule 1.
- **Deliverable:** the decision in the wiki. Agents prepare the model cards and the upload script. The user creates the accounts and does the upload.
- **Depends on:** P14-01, P2-07 (registry accounts), M7-09 (PyPI release).
- **Done when:** clean weights download from the chosen host with matching SHA-256. **`externally_blocked`** (user decision and accounts).
- **Decision (user, 2026-11-22, "all recommended"; [publishing checklist](../../docs/publishing-checklist.md) section J):** D10 host = GitHub release assets for the clean models; D11 licence = CC0-1.0 for `t15-m4-13`, `t12-v2`, `willett-hw` and CC-BY-4.0 for `kt-semg-lda`; D12 = the research-only `emg2qwerty-p11-01` weights are never hosted. DATA.md rule 1 and the manifest `weights_status` fields say so. Only the decision is recorded: no weights are uploaded and no release exists.
- **Next step (needs a final user yes before the upload):** checklist steps J-2 to J-5: check the SHA-256 of each local file, create the release `weights-v1` with the clean files and `LICENSE-WEIGHTS.md`, fill the manifest `url` fields, test the download. Status stays `externally_blocked` until the user says yes to the upload.

#### P14-03 Trust layer as a drop-in wrapper
- **Serves:** BCI companies, research labs, small teams ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** any team adds the trust layer to its own decoder with no change to the decoder. Bring your own logits or n-best lists. Get COMMIT / OFFER / WITHHOLD with a stated wrong-commit guarantee.
- **Deliverable:** one wrapper API (example shape: `guard = fidetype.trust.wrap(calibration_set, alpha=0.05)`; `decision = guard(logits_or_nbest)`); a calibration helper that fits on the user's own held-out data; a printed guarantee sheet (α, δ, method, number of calibration items, assumptions); a quickstart page "add trust to your decoder in 10 minutes". The wrapper reuses the [CTC-logits adapter](../concepts/ctc-logits-adapter.md) and the [text n-best adapter](../concepts/text-nbest-adapter.md). It adds no new trust maths.
- **Depends on:** P4-07 (generic adapters), P5-02 (guarantees), P5-07 (trust v5 recipe), M2-19 (re-tuned LTT config), P8-02 (quickstarts; this quickstart is one of them).
- **Done when:** a fresh subagent goes from the quickstart to a calibrated wrapper on its own logits in 10 minutes or less (timed). It works for logits and for n-best input. On two public replay sets, the held-out wrong-commit rate is at or below α at the stated confidence. Unit tests and the quickstart code run in CI.
- **Status (2026-11-15):** API done: `fidetype.trust.calibrate` / `wrap` / `load`, `TrustGuard.decide` ([`src/fidetype/trust/dropin.py`](../../src/fidetype/trust/dropin.py)); logits and n-best; Paper 1 v4 LTT recipe, commit gate always on, uniform + shuffled null controls refuse a failing config (`NullControlError`); guarantee sheet and JSONL audit log. Docs: [quickstart](../../docs/trust-quickstart.md), [guarantee sheet](../../docs/trust-guarantee.md). Tests in CI (`tests/test_trust_dropin.py`, includes the quickstart n-best route). **Done (2026-11-16):** timed fresh-agent quickstart run 9.0 min (target 10; fixes from it: Windows long-path clone note, honest install time, commit-gate warning on the sheet, plain-text reasons, optional `guard_settings`). Replay validation ([experiment](../../experiments/2026-11-16-p14-03-replay-validation/results.md)), alpha 0.05: T15 (by trial) 2/701 commits, wrong-commit 0.0029 [CP95 0.0003, 0.0103]; T12 (by session) 25/400 commits, 0.0375 [0.0211, 0.0611]; null controls pass on both. Both point estimates are below alpha (pre-declared rule); the T12 CP95 upper bound is above alpha (drift across sessions; one draw). API fix from the validation: `stream_texts=` for decoders whose tokens are not the text characters (frame temperature). Not covered: n-best input on a public set (synthetic only), non-implant modalities.

#### P14-04 Live decode from lab tools
- **Serves:** research labs, small teams ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** a lab that already uses LSL, BrainFlow or an OpenBCI board gets live NTS from one command.
- **Deliverable:** a CLI and API path (example shape: `fidetype live --source lsl|brainflow --board <id> --model <name> --trust <config>`). It joins the P4-02 adapters (LSL exists: `src/fidetype/adapters/lsl.py`; the BrainFlow → LSL bridge exists: `src/fidetype/adapters/brainflow_bridge.py`), a P14-01 model and the P14-03 wrapper. OpenBCI boards (Cyton, Ganglion) go through their BrainFlow board ids. P14-04 adds only the end-user path. The adapters stay in P4-02.
- **Note:** our pretrained models do not transfer to a new device or a new person without calibration. So the live test checks the plumbing (synthetic board, LSL replay of a public recording). Replay checks the decoding quality.
- **Depends on:** P4-02, P14-01, P14-03. Real boards: P4-06.
- **Done when:** in CI, the BrainFlow synthetic board and an LSL replay of a public recording each give valid NTS end to end, with trust decisions, from one command. The test on a real OpenBCI board is part of P4-06 (**externally blocked**, hardware).
- **Status (2026-11-16): done**, with one gap. `fidetype live --source {synthetic,brainflow,lsl}` ([docs](../../docs/live-decode.md), code `src/fidetype/live/`): ring buffer → key windows (onset markers or fixed hop) → model (KT-sEMG reference features + causal z-score + LDA) → key beam search → drop-in guard (`fidetype.trust.load`, n-best input) → one line per decision + NTS file (trust-ready and provenance pass). Packaged demo model and guard `builtin:synthetic-keys` (our synthetic signal, no real data); KT-sEMG model + guard made locally by `fidetype live train-kt` (CC BY 4.0, not committed); `replay-kt` / `replay-synthetic` publish over LSL. CI: core tests with no optional package, plus job `live` with the real BrainFlow Synthetic board and a real pylsl loopback. Added latency per window well below 1 ms, per decision a few ms ([results](../../experiments/2026-11-16-p14-04-live/results.md)). **Gap:** the CI LSL replay uses a synthetic recording, not a public one (a recording cannot go into the repository): P14-11.

#### P14-05 Headline metric: safe words per minute
- **Serves:** research labs, BCI companies ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** one number that says what a user gets: words per minute of committed text, at a wrong-commit rate that the trust layer guarantees (working name "safe WPM at α").
- **Deliverable:** a metric definition on [error metrics](../concepts/error-metrics.md): committed correct words per minute; the entry states α, δ and the method; the measured wrong-commit rate on test is shown next to it; the no-BCI eWPM baseline stays. The scorer computes it. The leaderboard shows it as a column. **No new leaderboard:** this is a column in the P6 leaderboard and in the P13 guarantee reporting.
- **Depends on:** P6-02 (scorer), P6-03 (leaderboard site), P13-02 (guarantee reporting).
- **Done when:** the scorer gives safe WPM for our baselines on at least 3 tracks. Entries whose measured wrong-commit rate is above their stated α are marked. The required shuffled and null controls are shown next to it.

#### P14-06 Visible demo: recorded EMG to text
- **Serves:** all audiences (first look); small teams ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** one short demo that shows the value in 30 seconds: wrist EMG goes in, text appears on screen, and each trust decision is visible.
- **Deliverable:** a browser page and one command. A recorded EMG session (clean data: Toronto sEMG or KT-sEMG; emg2qwerty only with a "research only" label) plays at real time → P14-01 model → P14-03 wrapper → text. Committed text, offered choices and withheld segments have different marks. A screenshot and an optional screen recording. The three-device demo (P8-03) can reuse it. It does not replace P8-03.
- **Depends on:** P14-01, P14-03, P8-05 (original UI work). Later P8-03.
- **Done when:** the demo runs from one command on a clean machine. A headless Edge screenshot shows text and trust marks. The page states the dataset, its licence and that the input is a recording.

#### P14-07 Live demo with a real wristband
- **Serves:** BCI companies, small teams ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** the P14-06 demo with a live EMG wristband.
- **Deliverable:** the device choice (user), the P4-05 EMG band adapter, a per-user calibration session, a recorded live run.
- **Depends on:** P14-06, P4-05, P4-06.
- **Done when:** a live run types text with trust marks on screen. **`externally_blocked`** (the hardware purchase is the user's decision).

#### P14-08 Results write-ups
- **Serves:** research labs, BCI companies, clinical trials ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** credibility. Each value-first claim has a public result that anyone can rerun.
- **Deliverable:** short result pages in `experiments/` and the wiki: the models of P14-01 (metrics per dataset, controls, limits) and the safe-WPM numbers of P14-05. Each page has the exact config, the controls and a one-command rerun. The papers in the PUB track (Paper 1, Paper 2 M4-04, spec / benchmark paper P11-04) may cite them later.
- **Rule:** write-ups are not papers. They have no peer review. PUB keeps **no deadline**. P14 adds no deadline to any paper item.
- **Depends on:** P14-01, P14-05. Links to PUB (P11-04, M4-04).
- **Done when:** each P14-01 model and the P14-05 metric has a result page, linked from its model card or leaderboard column. The [overview](../overview.md) cites them.

#### P14-09 Example AAC integration
- **Serves:** AAC app makers ([who uses Fidetype](who-uses-fidetype.md)).
- **Goal:** show that one standard input (NTS) lets any BCI drive an AAC app, as USB HID lets any keyboard drive any computer.
- **Deliverable:** an example integration of NTS into one open-source AAC or text-entry app. The app receives only COMMIT decisions (and, as an option, OFFER choices as a word list) from the collector WebSocket exporter. Candidates to check: Cboard (web AAC), Optikey (Windows eye-gaze keyboard), Dasher (text entry). This wiki has **not verified** their licences. Copyleft apps get a process-separated bridge only (WebSocket), as the P4 licence rule says. We copy no third-party code. The licence check comes first, before any code.
- **Depends on:** P3 WebSocket exporter (exists in collector v0, [collector](../concepts/collector.md)), P14-03 (trust wrapper), P14-06 (recorded EMG source). A pilot with a real AAC developer stays P10-05 (**externally blocked**).
- **Done when:** recorded EMG (or B2T '25 replay) → trust layer → the AAC app shows committed text, from one command, with a screenshot. The bridge has a replay test in CI. A short guide "connect your AAC app to NTS" exists. An upstream contribution to the app needs its maintainers: **externally blocked**.

### Exit criteria
- `pip install fidetype` plus two lines decode public data into NTS (P14-01). Clean weights are published (P14-02, externally blocked).
- The trust wrapper quickstart passes the fresh-agent 10-minute test (P14-03).
- One command gives live NTS from LSL and from the BrainFlow synthetic board (P14-04).
- The leaderboard shows safe WPM on 3 or more tracks (P14-05).
- The recorded EMG demo runs from one command (P14-06). The live wristband demo is externally blocked (P14-07).
- Every P14-01 model and the P14-05 metric has a result page (P14-08).
- One open-source AAC or text-entry app shows committed NTS text through the example bridge (P14-09).

**Effort:** 25–40 agent-days (our estimate); user: about 6 h (weight hosting decision, accounts, hardware decision). **Depends on:** M4-12, P4-01, P4-02, P4-07, P5-02, P6-02, P6-03, P11-01. **Window:** 2026-11-16 → 2027-03-31, before most of P10, as the rule "demo + benchmark before outreach" needs. Items that need the user or hardware have no date.

### Open-gap items (added 2026-11-16)
The user asked that known gaps are fixed later, not forgotten. These items come from agent reports of 2026-11-16. Full list: [open gaps](open-gaps.md). No existing item moved.

#### P14-10 Safe WPM on the remaining tracks (b2t24-t12, willett-hw, kt-semg, emg2qwerty, P11-01)
- **Gap:** 8 of the [open-gap list](open-gaps.md). Follow-up of P14-05.
- **Status:** `done` (2026-11-19).
- **Partly closed:** P6-01, commit `1d4ff8c`: exact Toronto safe WPM (participant CI) and null-commit audits at the CRC / LTT thresholds for B2T ours, B2T published and MEG.
- **Partly closed (2026-11-17):** P6-02, commit `5133e04`: scorer, baselines, safe WPM and null-commit audits for b2t24-t12 (0.48 certified), willett-hw (vacuous, partial 81/254), kt-semg (vacuous) and emg2qwerty (vacuous, research only). Only the P11-01 decoder is left (waits on the GPU). Follow-ups: P6-05, P6-06, P14-12, P14-13, P14-14.
- **Update (2026-11-19):** the P11-01 decoder exists ([results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md)): personalised test CER 15.09 %, 2,445 NTS streams `trust-ready`. No safe-WPM number yet: it needs a trust config on held-out streams (new item P11-09, gap 89) and a declared-subset track entry (P14-13). P14-10 stays open for this last part.
- **Depends on:** P14-05, P6-01 (done), P6-02, P11-01.
- **Source:** Commit `7d74c0f` (P14-05 safe WPM baselines; missing tracks and controls); partly closed by `1d4ff8c` (P6-01).
- **Done when:** The scorer, baselines and safe WPM exist for the tracks `b2t24-t12`, `willett-hw`, `kt-semg` and `emg2qwerty` (research only), and for the P11-01 decoder when it exists, each with its null-commit audit; or the result states why a track has no certified number. The scorer and baselines of these tracks come with P6-02. Part already closed by P6-01 (commit `1d4ff8c`): exact Toronto safe WPM with a participant CI, and null-commit audits for B2T ours, B2T published and MEG (the two B2T published entries still show "controls: no" because shuffled / zeros CER is not defined for a text-only decoder; P6-01 documents this).
- **Closed (2026-11-19):** the last part by P11-09 ([results](../../experiments/2026-11-19-p11-09-emg-trust/results.md)): the P11-01 decoder has a certified but vacuous safe WPM (0.00; 0 commits / 1,221; null-commit audit 0 / 1,221 on zero EMG; no-BCI 2.93) in the declared-subset card `emg2qwerty__p11-01-crt-subset8__guard`.

#### P14-11 CI: LSL replay of a public recording
- **Gap:** 18 of the [open-gap list](open-gaps.md) (added 2026-11-16 by P14-04). Follow-up of P14-04.
- **Status:** `done`. Commit `c3834c2` (2026-11-17): CI job `live-kt` downloads KT-sEMG run3 (53 MB, CC BY 4.0, Nokia) from Harvard Dataverse, checks SHA-256 (`tools/ci/kt-semg-run3.sha256`), caches it (`actions/cache`), trains an in-sample plumbing model, replays run3 over a pylsl loopback with `markers` and `detect` timing and checks `trust-ready` NTS with trust decisions and the replay attribution (`tools/ci/kt_lsl_replay.py`, one command). First CI run: PASS (3 decisions per timing). Nothing from the recording is committed.
- **Depends on:** P14-04 (done).
- **Source:** the P14-04 "done when" asks for an LSL replay of a public recording in CI. The repository rule forbids committed recordings, so the CI job `live` replays the synthetic typist instead. The KT-sEMG replay (`fidetype live replay-kt`) runs only on a machine with the data.
- **Done when:** a CI job downloads one small public recording with a clear licence (for example KT-sEMG `run3.csv`, 53 MB, CC BY 4.0, from Harvard Dataverse, SHA-256 checked, cached between runs), trains or loads a local model, replays the run over LSL and checks valid NTS with trust decisions from one command. Nothing from the recording is committed.

#### P14-12 Willett-hw: word LM for exact-sentence commits and full test coverage
- **Gap:** 26 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the P6-02 report). Follow-up of P14-10, P6-02.
- **Status:** `todo`.
- **Depends on:** P6-02 (done); a word LM (for example the Tatoeba word LM of the T12 v2 recipe, or the published 50k-word n-gram); P15-08 (Willett decoder of our own, for full coverage). 2026-11-19: P14-33 (done) packages one, `willett-hw` (greedy CER 0.305, local weights). Its training pool holds 193 of the 254 track test trials, so full coverage needs a retrain on the track train split (or a scoring on the P14-33 test blocks).
- **Source:** Commit `5133e04` (P6-02: 3 of 81 raw RNN sentences exactly right; the built-in word-list beam keeps no candidate on 59 of 81 trials; published RNN output covers only 81 of 254 test trials).
- **Gap detail:** The Willett entry uses the published real-time RNN output. Without a word LM only 3 of 81 sentences are exactly right, so the guard finds no certified threshold. The published output exists for only 81 of the 254 test trials (closed-loop trials), so the entry is partial.
- **Done when:** A willett-hw entry decodes with a word LM and reports exact-sentence accuracy and the guard result (certified or vacuous, with numbers). Full coverage of the 254 test trials needs our own decoder on the neural data (P15-08 or later); until then the entry stays marked `[partial: 81/254]` and the results say so.

#### P14-13 Conformant EMG baselines without oracle key timing (kt-semg, emg2qwerty)
- **Gap:** 27 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the P6-02 report). Follow-up of P6-02, P14-10.
- **Status:** `todo`.
- **Depends on:** P11-01 (continuous EMG decoder); P4-10 (live key-onset detector).
- **Source:** Commit `5133e04` (P6-02: the kt-semg and emg2qwerty LDA baselines take key times from the key log; the track task gives no key times at test).
- **Gap detail:** The P6-02 EMG baselines cut key windows at the logged key times (oracle timing). The track task does not allow this. So they are reference entries only, not conformant entries.
- **Done when:** kt-semg and emg2qwerty (research only) each have an entry whose decoder sees only the EMG at test (no key times): the P11-01 continuous decoder or a decoder with a causal onset detector (P4-10). The entry is scored with the v0.2 scorer with both controls, and the oracle-timing entries are marked `reference (oracle timing)` on the board.
- **Update (2026-11-19):** the P11-01 continuous decoder exists ([results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md), benchmark section). No entry yet, for three reasons: (1) its generic model trained on 96 of the 104 emg2qwerty track test sessions, so only a declared-subset entry on the 8 P11-01 test users is clean; (2) no writer maps its 98 ASCII-key CTC tokens to the track's `KeyboardEvent.code` units; (3) the guard needs a trust config (P11-09, gap 89).
- **Update (2026-11-19, P11-09):** emg2qwerty part done: declared-subset entries `emg2qwerty__p11-01-crt-subset8__guard` / `__always-commit` (8 track-test sessions; the decoder sees only the EMG; key-code writer `fidetype.adapters.emg2qwerty.tokens_to_codes` / `merge_to_key_ctc`; v0.2 scorer with both controls): key error rate 0.179 [0.145, 0.214], guard vacuous ([results](../../experiments/2026-11-19-p11-09-emg-trust/results.md)). Left: kt-semg, and the `reference (oracle timing)` mark on the board.

#### P14-14 T12 safe WPM above the no-BCI reference
- **Gap:** 29 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the P6-02 report). Follow-up of P14-10.
- **Status:** `todo`.
- **Depends on:** M4-13 (stronger T15 recipe to port), P15-19 (usefulness on stronger decoders), P6-06.
- **Source:** Commit `5133e04` (P6-02: only b2t24-t12 certifies commits; safe WPM 0.48 vs no-BCI 4.00; 17 commits, 9 wrong; decoder CER 0.30).
- **Gap detail:** Only the T12 entry certifies commits, and its safe WPM (0.48) is far below the no-BCI reference (4.00). The guard keeps the wrong-commit rate at 0.010, but the decoder (CER 0.30) gives few right sentences. This is a decoder limit, the same root cause as P15-19.
- **Done when:** A b2t24-t12 entry with a stronger decoder (the M4-13 recipe ported to T12, or a P11 / P15 decoder) reports safe WPM at alpha 0.05 with its certification status next to the no-BCI reference, with both controls passing. The item closes when the safe WPM is above the no-BCI reference, or when a result states with numbers which decoder accuracy that needs and why the current decoders do not reach it.

#### P14-15 Word-decoder settings tuned without evaluation trials (T15)
- **Gap:** 35 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the T15 split audit). Follow-up of P14-03.
- **Status:** `done` (2026-11-17, pre-registration `fc8478c`; [results](../../experiments/2026-11-17-p14-15-retune/results.md)). Re-split "B2T ours" rows: **no effect**. The fit-A re-tune changed the setting in 35 of 200 re-splits (8 of 50 R3), mostly exact WER ties; after rebuilding them, 0 of 80 primary metrics moved by their CI half-width (largest 0.27 of it). Tune without the 16 `val_eval` trials: edit penalty 8 instead of 12 (exact WER tie); without `val_eval` and `val_select`: unchanged. Follow-ups P14-18 (gap 44, M4 rows) and P14-19 (gap 45, published gate, forward chain, downstream tables).
- **Depends on:** — (CPU only).
- **Source:** T15 split audit, 2026-11-17 ([page](t15-split-audit.md)), issue D.
- **Gap detail:** The 3 settings of our phoneme-beam word decoder (`lm_weight`, `edit_penalty`, `word_bonus`; grid of 12) were tuned once on 400 fixed `b2t25-t15` `cal` trials (experiments/2026-11-10-b2t25-trust, `tune.json`). The Paper 1 re-splits put 179-224 of these trials into each test set of 818. 16 of the 400 are M4 `val_eval` trials, and every M4-x word-level result on `val_eval` uses these settings (P14-03 `decode_fn`). The bias is optimistic and probably small.
- **Done when:** The tune is rerun (a) inside fit-A of at least 10 Paper 1 re-splits (R3 / R4 split files), and (b) on the 400 trials minus the HDF5 `val_eval` and `val_select` trials. If the chosen settings never change, the item closes with "no effect" in the audit page. If they change, the affected tables are rerun, and the Paper 1 drafts and M4-x results pages get a note.

#### P14-16 `fidetype live` publishes over a binding (LSL, WebSocket)
- **Gap:** 36 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P7-06). Follow-up of P14-04, P7-06.
- **Status:** `done` (2026-11-17, commit `2fd39fc`). `fidetype live --publish TARGET` (repeatable): `lsl` / `lsl:NAME` (`NTSOutlet`, now shared with `replay_to_lsl`: frames stream `NAME` + events stream `NAME.events`; `DecisionOutlet`: `NAME.decisions`), `ws://HOST:PORT/nts` (`WSProducer`), `ws://HOST:PORT/decisions` (`WSServer` + `OutputHub`); `--publish-wait`, `--publish-linger`. Decisions go on the decisions channel only (FEP-0001 section 3 r4). A failed target stops with one log line; the decode goes on. `python -m fidetype.conformance.binding_producers --target live-lsl --target live-ws` runs the CLI in a child process on loopback and records it with `nts-conform capture`; both reach NTS Trust-ready with the binding. `certified.json`: `fidetype-live-lsl`, `fidetype-live-ws` (16 entries). CI job `live`: step "fidetype live publish captures (P14-16)". Docs: [live decode 8a](../../docs/live-decode.md#8a-publish-over-a-binding---publish-p14-16), [conformance](../../docs/conformance.md). New gap 42 = P14-17.
- **Depends on:** P14-04 (done), P7-06 (done: `nts-conform capture`).
- **Source:** P7-06 (2026-11-17): `fidetype live` reads raw signal over LSL but writes its NTS output (frames, hypotheses, trust decisions) only to a JSON Lines file or stdout. Other programs cannot subscribe to it live, and it has no binding producer evidence.
- **Done when:** `fidetype live` has options to publish its NTS frames + events and its trust decisions as LSL streams (FEP-0002) and / or to send them to a WebSocket server and serve `/decisions` (FEP-0004); a test captures them with `nts-conform capture` on loopback, `nts-conform check` gives a producer level with the binding, and `certified.json` lists `fidetype live` with that evidence.

#### P14-17 `fidetype live --out`: trust decisions in a separate decision log
- **Gap:** 42 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P14-16). Follow-up of P14-04, P14-16.
- **Status:** `done` (2026-11-17, commit `9de7e61, 1145f2e`). `fidetype live --out S.jsonl` writes a pure NTS input stream (no `trust_decision`); the new option `--decisions-out FILE` writes the FEP-0001 decision log (default with `--out`: `S.decisions.jsonl`; `none` = off). `nts-conform check` on both files: NTS Trust-ready. Validator disagreement: the v0.1 suite (`fidetype validate`, `fidetype-ts validate`, `fidetype-rs validate`) read a `trust_decision` line as an unknown event type and ignored it (6.2 rule 5); only the opt-in `fep-0001` profile tested TD-4. New core check `NTS-TD-INPUT` in all three SDKs, vector V97 (v0.1 97), RC4 amendment 4 (C.1 row TD-4). docs/live-decode.md section 8, the P14-11 CI replay (`tools/ci/kt_lsl_replay.py`: `nts-conform check --require-level trust-ready` on both files) and tests updated. certified.json: `fidetype-live-file` (producer, NTS Trust-ready, text). New gap 46 = P14-20.
- **Depends on:** P14-16 (done).
- **Source:** P14-16 (2026-11-17): the `--out` file of `fidetype live` holds the `trust_decision` events next to the frames and hypotheses. `nts-conform check` fails it (FEP1-TD-INPUT, FEP-0001 section 3 r4: no `trust_decision` in an input stream), so its producer level is none. `fidetype validate --level trust-ready` (the older check that docs/live-decode.md names) passes it. `--publish` already splits the two channels.
- **Done when:** `fidetype live --out` writes an input stream without `trust_decision` events, and a new option (for example `--decisions-out`) writes the FEP-0001 decision log; `nts-conform check` on both files gives NTS Trust-ready; docs/live-decode.md section 8 and the P14-11 CI replay use the new form; tests updated.

#### P14-18 M4-x word-level results with word settings tuned without val_eval trials (T15)
- **Gap:** 44 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P14-15). Follow-up of P14-15, P14-03.
- **Status:** `done` (2026-11-17, pre-registration `3d07cb4`; [results](../../experiments/2026-11-17-p14-18-19-followups/results.md)). **Effect, favourable:** with edit penalty 8, 14 of 166 metrics move by their CI half-width (M4-12 1 of 90: truth in n-best of shared L 40 ms; M4-01/02 11 of 72: WER at the frozen T 0.019-0.023 lower; P14-03: 2 wrong commits → 0). Every change favours edit 8, so the committed M4 rows are not optimistic. Notes on the M4-12, M4-01/02 and P14-03 pages. Downstream reruns: P14-21 (gap 50).
- **Depends on:** P14-15 (done). CPU only.
- **Source:** P14-15 ([results](../../experiments/2026-11-17-p14-15-retune/results.md)), step 3: without the 16 M4 `val_eval` trials (384 tune trials), the pre-registered rule picks edit penalty 8 instead of 12 (lm 1.0, bonus 3). It is an exact WER tie (0.16477), decided by truth-in-n-best (0.5469 vs 0.5443). Without `val_eval` and `val_select` (368) the paper point stays first.
- **Done when:** the M4-12 `fixed0` `val_eval` word-level decode (P14-03 `decode_fn`) is rerun with edit penalty 8, and the word WER and the P14-03 guard rows are compared with the committed ones. If every change is below its CI half-width, close with "no effect" on the M4 results pages; else rerun the affected M4-x / M2-19 / P15-05..07 / P5-02 rows and add notes.

#### P14-19 Re-split published-gate rows, forward chain and downstream tables with per-fit word settings
- **Gap:** 45 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P14-15, post hoc). Follow-up of P14-15.
- **Status:** `done` (2026-11-17, pre-registration `3d07cb4`; [results](../../experiments/2026-11-17-p14-18-19-followups/results.md)). Re-split tables (published gate, guard off; 35 rebuilt splits): **no effect** (0 of 240). **Forward chain: effect** (9 of 320, plug-in rows of "ours"): with the edit-8 day-1 prefix no day has a CP lower bound above α; LTT max V3 ours 2/13 → 1/13, published 1/13 → 0/13. Downstream: A2 day 34 (same prefix), two formal effects (joint LTT with 2 committing splits; population risk with a resampling-only CI); per-day, reuse, cleanup, no-guard, bonus, M3-01/02, trust v5: no effect. Correction notes on the pages and in `papers/paper1/correction-2026-11-17-p14-19.md`. Not covered: P14-22 (gap 51).
- **Depends on:** P14-15 (done). CPU only (about 1 h per 35 rebuilt splits).
- **Source:** P14-15 ([results](../../experiments/2026-11-17-p14-15-retune/results.md), post hoc): (1) `published_plus_fn` uses our word n-best (gate score and word confidences), so the "B2T published" re-split rows also depend on the word setting; the audit called them clean. (2) The R4 forward chain (V1, V2, V4) tests on whole days; the fit prefix "day 1 only" (30 trials, used by one test day in V1 and one in V4) picks edit penalty 8. (3) R4 population-risk, per-day, reuse, joint-LTT, no-guard, M2-18, M3-01/02, trust v5 and A2 read the same split tables (P14-15 found no effect on the guard-on "ours" tables).
- **Done when:** the published-gate tables of the 35 changed re-splits and the guard-off "ours" tables are rebuilt with each split's fit-A setting, the forward-chain day-1 prefix is rerun, and the same rule as P14-15 (change < CI half-width = no effect) is applied; "no effect" closes the item, else the tables get dated correction notes and the paper track gets a note.

#### P14-20 Streaming validators: `trust_decision` in a live input stream (TD-4)
- **Gap:** 46 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P14-17). Follow-up of P14-17.
- **Status:** `done` (2026-11-17). RC4 amendment 5, rule TD-14: an event-by-event consumer refuses a `trust_decision` between the header and `end` (ignored after `end`; a stream without a header is a decision log). Python `StreamingTrustLayer.push`, TypeScript / Rust `StreamValidator` and the collector `validate` processor do the same; parity test on the streaming cases S01-S06 (`spec/conformance/streaming/td-input.json`) in all three SDKs, plus V97 event by event.
- **Depends on:** P14-17 (done).
- **Source:** P14-17 (2026-11-17): the file validators of the three SDKs now refuse a `trust_decision` in an input stream (`NTS-TD-INPUT`, TD-4). The event-by-event validators still ignore it as an unknown event type: Python `StreamingTrustLayer.push`, TypeScript and Rust `StreamValidator` (and the collector `validate` processor on live input).
- **Done when:** the spec says what a streaming consumer does with a `trust_decision` in an input stream (refuse the event or ignore it and warn), and the three streaming validators do the same thing, with a parity test.

#### P14-21 M4-x rows with the T15 word decoder tuned without val_eval (edit penalty 8)
- **Gap:** 50 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P14-18). Follow-up of P14-18.
- **Status:** `done` (2026-11-18; pre-registration `095150c`, [results](../../experiments/2026-11-17-p14-21-edit8-rows/results.md)). Effect on 11 of 71 decided metrics (trust commit counts; no guarantee breaks). M4-13 safe WPM 2.23 -> 2.28, still below no-BCI 4.02. Deferred rows: P14-24, P14-25.
- **Depends on:** P14-18 (done). CPU only.
- **Source:** P14-18 ([results](../../experiments/2026-11-17-p14-18-19-followups/results.md)): with lm 1.0 / edit 8 / bonus 3, 14 of 166 M4 metrics move by their CI half-width (1 in M4-12, 11 in M4-01/02, 2 in P14-03). All of them favour edit 8.
- **Done when:** the M4-x word-level rows that use `val_eval` decodes of the B2T word decoder (M4-06 replays, M2-19, P15-05..07, P5-02, the M4-13 trust rows) are rerun with edit 8 or shown not to use the word decoder, compared with the P14-15 rule, and their pages carry dated notes.

#### P14-22 R3-level analyses on the re-split tables with per-fit word settings
- **Gap:** 51 of the [open-gap list](open-gaps.md) (added 2026-11-17 by P14-19). Follow-up of P14-19.
- **Status:** `todo`.
- **Depends on:** P14-19 (done). CPU only (no new decodes: the rebuilt tables exist in `derived/p14-18-19/tables`).
- **Source:** P14-19 ([results](../../experiments/2026-11-17-p14-18-19-followups/results.md)): the R4 analyses, M3-01/02, trust v5 and A2 were rerun; the R3 `repeated-splits` analyze (full output), `selective-risk`, `deployable-rule`, `v3-derived` and R4 `v4-derived` guard controls read the same tables but were not rerun. Paper 1 Fig. `fig:deploy`a uses the corrected forward chain.
- **Done when:** these analyses are rerun with the redirected loader of P14-19, compared with the P14-15 rule, and their pages (and the paper correction note, if needed) carry dated notes.

#### P14-23 T15 safe WPM above the no-BCI reference with our causal decoder
- **Gap:** 53 of the [open-gap list](open-gaps.md) (added 2026-11-17 by the M4-13 rows task). Follow-up of P14-05, M4-13.
- **Status:** `done` (2026-11-19, closed by P15-22, pre-registration `7557b54`, [results](../../experiments/2026-11-19-p15-22-llm-learned/results.md)): LLM rescoring (P15-05 B1) + the learned commit score gives a **certified safe WPM v0.1 of 4.91 [4.25, 5.57]** on all 701 `val_eval` trials (13 / 701 wrong, CP95 [0.0099, 0.0315]; controls 0 / 300 and 0 / 300), clearly above the no-BCI 4.02 (the lower end of the interval is above 4.02). Before: analysis done 2026-11-18 ([analysis](safe-wpm-bottleneck.md), exploratory): the guard factor (commits 87 of 257 exactly-right sentences, x 0.32) is as large as the decoder factor (x 0.34); a perfect guard at M4-13 gives 7.23. A sentence guard needs about 159 right commits (commit rate about 0.26, error among commits about 0.12) for 4.02. Levers registered as P14-26, P5-23, P5-24, P15-22, P14-27 (gaps 66-70); the item stays open until a pre-registered lever passes. P5-23 (2026-11-18, pre-registered, [results](../../experiments/2026-11-18-p5-23-learned-confidence/results.md)): learned commit score 2.64 on all 701 `val_eval` trials (p_top1 guard 2.23; +0.42 [0.07, 0.78]), still below 4.02. P5-24 (2026-11-18, pre-registered, [results](../../experiments/2026-11-18-p5-24-prefix-commits/results.md)): prefix commits 4.87 [4.43, 5.30] under the PROPOSED v0.2 (above 4.02); v0.1 0.53 literal / 1.03 complete-only. P14-28 (2026-11-18, pre-registered sensitivity, [results](../../experiments/2026-11-18-p14-28-reading-cost/results.md)): with 0.5 s + 0.3 s/word reading cost per commit the prefix guard keeps 4.67 [4.26, 5.07] under v0.2; break-even 5.99 s per commit. Not closed: v0.2 is not adopted and no v0.1 value is above 4.02.
- **Note (2026-11-20, P15-29):** the 4.91 [4.25, 5.57] CI resamples trials for one calibration draw. With calibration variation (K = 40) T15 gives 5.18 [0.00, 6.99]: above 4.02 on average, not reliably ([results](../../experiments/2026-11-20-p15-29-calibration-ci/results.md)). Follow-up: P15-34 (gap 132).
- **Depends on:** M4-13 (done); P14-21 (word decoder with edit 8); P6-09 (full-coverage entry). CPU for the guard; a stronger decoder may need the GPU.
- **Source:** M4-13 rows ([P14-05 results](../../experiments/2026-11-16-p14-05-safe-wpm/results.md)): on T15 `val_eval` (701) M4-13 + drop-in guard gives safe WPM 2.23 (certified; 104 commits, 17 wrong, error among commits 0.163), below the no-BCI reference 4.02. The partial v0.2 entry (103 units) gives 4.07 [2.51, 5.74] vs 4.12. The published Card et al. decoder gives 12.2-13.4.
- **Done when:** a T15 entry with our causal decoder reports a certified safe WPM above the no-BCI reference on all 701 `val_eval` trials (or a full-coverage track entry), with both controls passing; or a result states with numbers which commit rate and error among commits that needs and why the current decoder and guard do not reach it.


#### P14-24 F2 and M4-13 trust-rerun rows with word-decoder edit penalty 8
- **Gap:** 62 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P14-21). Follow-up of P14-21.
- **Status:** `todo`.
- **Depends on:** P14-21 (done). CPU; the LLM arms need more than 1.5 GB RAM (about 2.5-4.5 GB).
- **Source:** P14-21 ([results](../../experiments/2026-11-17-p14-21-edit8-rows/results.md)): P15-05, P15-06, P15-07 and the M4-13 trust reruns (P5-02 / P15-03 / F2 on M4-13, pre-registered with edit 12) use the B2T '25 word decoder, but were not rerun with edit 8.
- **Done when:** these rows are rerun with lm 1.0 / edit 8 / bonus 3 (edit-12 references first), compared with the P14-15 rule, and their pages carry dated notes.

#### P14-25 P3-08 collector replays with edit penalty 8 and a keep-awake
- **Gap:** 63 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P14-21). Follow-up of P14-21.
- **Status:** `todo`.
- **Depends on:** P14-21 (done). CPU, about 2 h real time (3 replays of 37 min).
- **Source:** P14-21: the edit-12 reference replay of M4-13 was cut by machine sleep (27 of 120 decisions, bench `duration` stop), so the edit-8 replays were not used. The prep reproduced exactly.
- **Done when:** the M4-13 reference replay reproduces 16 COMMIT / 104 OFFER / 3 wrong with a keep-awake held, and the edit-8 replays of M4-13 and M4-12 are compared with the P14-15 rule (the P14-21 queue outputs in `derived/p14-21/r6-*` may be reused).
#### P14-26 Safe WPM v0.2 proposal: prefix credit and a speech-time field
- **Gap:** 66 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P14-23). Follow-up of P14-05, P14-23.
- **Status:** `done` (2026-11-18, commit `00a64ba`, [proposal](../../docs/safe-wpm-v0.2-proposal.md)). v0.2 is PROPOSED, NOT ADOPTED: the user decides at the weekend; `metric_version="0.2"` switches it on; v0.1 stays the headline.
- **Depends on:** none (docs + scorer, CPU).
- **Source:** P14-23 [analysis](safe-wpm-bottleneck.md): `safe-wpm/0.1` credits only whole sentences and times the whole trial window. On T15 the window is 18.7 s per trial against 12.1 s of active speech (factor 1.51), and the correction penalty costs only 0.08 WPM.
- **Done when:** a pre-registered `safe-wpm/0.2` text defines (1) credit for a committed prefix that is a prefix of the truth, (2) the cost of a wrong prefix, (3) a `timing` field for speech-span or measured speech time next to the trial window, and (4) that v0.1 stays the headline column until the user accepts v0.2; the scorer computes both; tests; the leaderboard shows both with a note.

#### P14-27 Cost of causal smoothing on T15 and the decoder accuracy target
- **Gap:** 70 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P14-23). Follow-up of M4-13, P14-23.
- **Status:** `todo`.
- **Depends on:** GPU (after P11-01). One training run with centred smoothing, else the M4-13 recipe.
- **Source:** P14-23 [analysis](safe-wpm-bottleneck.md): M4-13 (causal) is 0.020 PER behind the published decoder (0.121 vs 0.101); if centred smoothing explains all of it, safe WPM gains at most about 0.7. At today's guard, 4.02 needs P(exact) about 0.66 (WER about 0.105, PER about 0.072).
- **Done when:** a pre-registered T15 run measures PER, WER, P(exact) and safe WPM with centred vs causal smoothing (same recipe, L 0), and the decoder accuracy target for safe WPM 4.02 is restated with the measured guard.

#### P14-28 Reading cost and short prefixes in safe WPM v0.2
- **Gap:** 75 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P5-24). Follow-up of P14-26, P5-24.
- **Status:** `done` (2026-11-18; scorer options + pre-registration `691d743`, [results](../../experiments/2026-11-18-p14-28-reading-cost/results.md), [proposal section 6](../../docs/safe-wpm-v0.2-proposal.md#6-reading-cost-p14-28)). Sensitivity (decisions fixed): T15 prefix 4.67 [4.26, 5.07] at 0.5 s + 0.3 s/word per commit; break-even 5.99 s per commit; m = 2 gives 4.07 at 0 s. Recommendation: adopt v0.2 with the `aac-gaze-v1` reading cost, keep m = 1. Follow-up: P14-29.
- **Depends on:** P14-26 (proposal done); the user decision on v0.2. CPU, docs + scorer.
- **Source:** P5-24 ([results](../../experiments/2026-11-18-p5-24-prefix-commits/results.md)): 181 of 465 T15 prefix commits are one word. v0.2 (like v0.1) adds no reading or checking time per commit, so many short commits may overstate the user's gain.
- **Done when:** a pre-registered sensitivity analysis reports v0.2 with a per-commit reading / checking time (from the `aac-gaze-v1` user model or the literature) and with a minimum prefix length, and the proposal states which variant it recommends.

#### P14-29 Measured checking time per commit for AAC and BCI users
- **Gap:** 77 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P14-28). Follow-up of P14-28.
- **Status:** `todo`.
- **Depends on:** full texts of Koester & Levine (1994, 1996) or other AAC timing studies; or a public BCI / AAC dataset with commit and confirm timestamps. CPU, literature.
- **Source:** P14-28 ([results](../../experiments/2026-11-18-p14-28-reading-cost/results.md)): the published values span about 0.01-1.35 s per commit plus 0.25-0.3 s per word, all from able-bodied users or our own `aac-gaze-v1` assumption. The T12 break-even (2.78 s per commit) is within reach of a slow user.
- **Done when:** the v0.2 reading cost default cites at least one measured checking time for AAC or BCI users (or states that none exists after a documented search), and the sensitivity table is re-read with it.

#### P14-30 Clean-machine README test of the pretrained decoders (P14-01 done criterion)
- **Gap:** 98 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P14-01). Follow-up of P14-01.
- **Status:** `externally_blocked`.
- **Depends on:** P14-02 (hosted weights; externally blocked, user); M7-09 (PyPI release).
- **Source:** P14-01 ([results](../../experiments/2026-11-19-p14-01-pretrained/results.md)): the registry, runtimes and reruns are done, but the weights are not hosted, so `pip install fidetype` + two lines cannot run on a clean machine yet; no fresh-agent README test was possible.
- **Done when:** on a clean machine, `pip install fidetype`, `load(name, download=True)` and `decode(file)` give NTS at level `provenance` for one test file of each clean dataset (T15, T12, KT-sEMG; Willett and Toronto when they exist), done by a fresh subagent from the README alone; SHA-256 checks pass.

#### P14-31 Packaged trust config for t12-v2 (word trigram LM in the text decoder)
- **Gap:** 99 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P14-01). Follow-up of P14-01.
- **Status:** `todo`.
- **Depends on:** P14-01 (done part); the Tatoeba word trigram LM of the T12 v2 recipe (experiments/2026-11-13-confirmatory-t12-v2/wordlm.py, about 170 MB pickle: needs a pickle-free format).
- **Source:** P14-01 ([results](../../experiments/2026-11-19-p14-01-pretrained/results.md)): `t12-v2` decodes, but `guard()` raises NoTrustConfig: the committed T12 guards (P6-02, P14-03) used a word decoder with a word trigram LM that is not packaged.
- **Done when:** `load("t12-v2").guard()` returns the committed T12 guard with its exact text decoder (pickle-free LM file listed in the manifest), and its decisions on the 400 test trials equal the P6-02 / P14-03 decisions.

#### P14-32 Toronto sEMG key-press CNN in the pretrained registry
- **Gap:** 100 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P14-01). Follow-up of P14-01.
- **Status:** `todo`.
- **Depends on:** P14-01 (done part); experiments/2026-11-11-emg-toronto (local CNN, CC BY 4.0 data).
- **Source:** P14-01 ([results](../../experiments/2026-11-19-p14-01-pretrained/results.md)): the manifest `toronto-semg-cnn` is `planned`: no NumPy runtime and no reader of the Toronto files yet.
- **Done when:** `load("toronto-semg-cnn").decode(<Toronto file>)` gives key streams at level `provenance`, and the cross-session key accuracy reruns (card 0.168).

#### P14-33 Willett handwriting decoder of our own in the pretrained registry
- **Gap:** 101 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P14-01). Follow-up of P14-01.
- **Status (2026-11-19): done** (gap 101 closed). Commit `b6dd77c`, [results](../../experiments/2026-11-19-p14-33-willett-hw/results.md), [docs](../../docs/pretrained-decoders.md). `willett-hw` v1 is `available`: P15-08 run R-all-s0 (random init, Willett CC0 data only, final step 3000), exported to `willett-hw.weights.npz` (34 MB, SHA-256 `66ac6590...`, local only; the exporter refuses a run whose `licence.json` is not clean). Runtime `xbody-ctc` (NumPy: per-session z-score -> linear stem -> the shared P11-01 causal trunk); reader `read_willett_session` (`t5.*` folder or `sentences.mat`). Weights licence CC0-1.0 **provisional** (user decision D11); language `en`; not hosted (gap 98). Card metric rerun with `load("willett-hw")` on CPU: test greedy CER **0.3051** (1,052 / 3,448), equal to the PyTorch value on 80 / 80 sentences (0 edits difference; tolerance 0.002). The card states: CER 0.305 is weak, seed 1 failed (0.920), no LM, descriptive only, and the split differs from the benchmark track `willett-hw` (193 of its 254 test trials are in this model's training pool). Guard not packaged: calibration on the val blocks was stopped by low machine memory -> P14-41 (gap 121). The PyTorch-on-CPU log-prob comparison did not run (same reason). P14-12 (gap 26) and P6-06 (gap 28) can now use this decoder.
- **Depends on:** P15-08 E1a (done 2026-11-19: a Willett decoder of our own exists; the clean-track run R-all-s0 is best on val 0.258 and test 0.305 greedy CER, CC0 data only; the same recipe fails on seed 1, 0.920; [results](../../experiments/2026-11-19-p15-08-e1-cross-body/results.md)); P14-01 (done part). **Can start.**
- **Source:** P14-01 ([results](../../experiments/2026-11-19-p14-01-pretrained/results.md)): the manifest `willett-hw` is `planned`: we have no trained Willett handwriting decoder yet.
- **Done when:** a `willett-hw` manifest with weights, a runtime and a reader; its card metric reruns with `load("willett-hw")`.

#### P14-34 Language-agnostic pipeline audit (per-language config)
- **Gap:** 106 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P14-01, P14-03, P14-05.
- **Status (2026-11-19): done** (gap 106 closed). Audit `857dcf1`, code `2b5c80f`, page [docs/language-support.md](../../docs/language-support.md). The audit lists about 40 English assumptions (file:line, impact for es / zh / ar / hi, config key, risk). `fidetype.lang` ([code](../../src/fidetype/lang.py)) is a registry of `Language` objects by BCP 47 tag (`en-US` -> `en`). `en` is the default and calls the existing `VOCAB`, `normalize_text` and `str.split`, so English outputs are bit-identical; `tests/test_lang.py` pins the charset, the normalisation of 23 hard strings (also `b2t25.normalize_words` and the LLM normaliser) and safe WPM v0.1 on a committed 40-trial fixture (exact `==`). `es` (provisional): 37-class vocabulary with `ñ á é í ó ú ü ¿ ¡`, Spanish normalisation, words by spaces, rates copied from `en`. `zh` (stub): `words()`, `wpm_counts()` and `load_trials_jsonl(language="zh")` raise `WordsNotDefinedError` (or report `not-defined`); no silent WPM. The tag is in the model manifest (optional `language`, default `en`, checked) and in the trust guard (`calibrate(language=)`, `TrustGuard.language`, saved only if not `en`, so English guard files are byte-identical). A Spanish config runs end to end on synthetic CTC input (calibrate, commits with `ñ`, safe WPM, save / load). Follow-ups (config keys in files of other items or in the spec): P14-38 (gap 117), P14-39 (gap 118), P14-40 (gap 119).
- **Depends on:** — (CPU only).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" All language results so far are English: T15, T12, Willett handwriting, emg2qwerty, KT-sEMG. Only the SpanishBCBL MEG replay adapter reads non-English data (research only). English assumptions are spread over the code, for example: character sets and CTC vocabularies, word lexicons, character and word LMs, safe WPM (`words(y)` counts words separated by spaces; the correction time uses 152 characters per minute), the hallucination benchmark protocol and the no-BCI gaze reference (`aac-gaze-v1`).
- **Done when:** An audit page lists each English assumption with its file and a fix. Each assumption becomes a per-language config value (a language tag, for example BCP 47, in the trust config and the model manifest). The English defaults give the same outputs as now (tests). A Spanish config loads end to end on synthetic input.

#### P14-35 End-user typing UI
- **Gap:** 111 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P14-06, P14-09, P8-05.
- **Status:** `todo`.
- **Depends on:** P14-06 (done: demo page); P3 WebSocket exporter; P14-03 (done).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" `demo/index.html` and `fidetype demo` show a recorded stream to a viewer. No app lets a user type with Fidetype. P14-09 connects an existing AAC app and P8-05 is the project site. Neither is our own typing UI.
- **Done when:** A local app (browser or desktop) receives decisions from the collector WebSocket exporter. It shows committed text, OFFER choices and confidence. The user accepts or rejects an offer and corrects committed text; each action goes back as feedback (for the P15 update loops). Accessibility: switch input, eye-gaze dwell selection, large targets, keyboard-only use, screen-reader labels (WCAG 2.2 AA, checked with an automated tool). A replay test runs in CI; a headless Edge screenshot shows the UI.

#### P14-36 Usability study of the typing UI
- **Gap:** 112 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P14-35, M6-04.
- **Status:** `externally_blocked`.
- **Depends on:** P14-35; ethics approval; volunteers, among them AAC users (external); M6-04 (real-user eWPM test; the sessions can be shared).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" The typing UI (P14-35) needs a test with real users. No item plans a usability study.
- **Done when:** A pre-registered study (tasks; measures such as SUS and task time; accessibility checks with switch and eye-gaze users) runs with consent. A results page reports the findings and the UI fixes. **`externally_blocked`** (ethics approval, volunteers).

#### P14-37 Packaged installer for end users
- **Gap:** 115 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P2-08, P14-35.
- **Status:** `todo`.
- **Depends on:** P14-35; code-signing certificates may be needed (user-owned, as P2-07).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" Today a user installs Fidetype with `pip` or `uv`. No one-click installer exists for a person who is not a developer (an AAC user or a carer).
- **Done when:** A Windows installer (first; macOS and Linux later) installs the collector, the typing UI and a pretrained model with no Python setup and adds a start-menu entry. An install test on a clean virtual machine passes. If code signing needs certificates, the page names that user step.
#### P14-38 Language hook in safe WPM, the benchmark scorer and the hallucination protocol
- **Gap:** 117 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P14-34). Follow-up of P14-34.
- **Status:** `todo`.
- **Depends on:** P14-34 (done: `fidetype.lang`).
- **Source:** [Language audit](../../docs/language-support.md), rows A3, A5, B1-B8 and section 5. These files were in edits by P15-29 and P11-13 during P14-34, so P14-34 added only `load_trials_jsonl(language=)`.
- **Done when:** `prefix_outcome`, the safe-WPM CLI, the benchmark scorer (track normaliser `lang:<tag>`, WER and `n_w`, user-model rates), the eWPM simulator and the hallucination fluency unit (per word with spaces, per character otherwise) take the language from `fidetype.lang`. A score card states `language` and `rates_source`. A language without word boundaries gives `not-defined`, not a number. All English cards and the `tests/fixtures/lang` pins stay bit-identical; `docs/safe-wpm.md` says where `words(y)` is defined.

#### P14-39 Words per minute for scripts without spaces
- **Gap:** 118 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P14-34). Follow-up of P14-34.
- **Status:** `todo`.
- **Depends on:** P14-34 (done).
- **Source:** [Language audit](../../docs/language-support.md), section 4.3. Mandarin (also Japanese, Thai) has no spaces between words. `len(text.split())` gives about one word per sentence. `fidetype.lang` now refuses (`WordsNotDefinedError`), but no definition exists.
- **Done when:** a written proposal (docs page) defines the rate for such scripts: a fixed, versioned word segmenter (licence-clean, its version in the score card) or a characters-per-minute metric with a stated cross-language conversion. It gives the no-BCI reference for the unit, implements it for `zh` in `fidetype.lang` with tests, and the user decides adoption (like safe WPM v0.2).

#### P14-40 Per-language models and vocabulary registry
- **Gap:** 119 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P14-34). Follow-up of P14-34, P15-31, P15-32.
- **Status:** `todo`.
- **Depends on:** P14-34 (done); a FEP for spec 12.4 vocabulary ids and the `NTS-VT-CHAR` grapheme rule (all three SDKs).
- **Source:** [Language audit](../../docs/language-support.md), rows A4, A6-A8, C1-C5, D7, D8. The char n-gram LM indexes 28 byte symbols; lexicons are CMUdict; LLM prompts say "English"; the simulator uses English letter frequencies and a US layout; the only registered `vocab_id` is `char.b2q-28`; `NTS-VT-CHAR` counts code points, so a Hindi grapheme vocabulary fails.
- **Done when:** the char LM takes its symbol table from `Language.vocab` (English LM files unchanged), a Spanish char LM trains from Tatoeba `spa` (CC BY 2.0 FR) with tests, `Language` holds the lexicon / grapheme-to-phoneme, LLM prompt language, letter frequencies and keyboard layout keys, and a FEP registers per-language `vocab_id`s (for example `char.es-37`) and states the code-point vs. grapheme rule, with validator vectors in all three SDKs.

#### P14-41 Trust guard for willett-hw
- **Gap:** 121 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P14-33). Follow-up of P14-33.
- **Status:** `done` (2026-11-20; pre-registration + memory fix `4565cc1`, results `b26341c`, [results](../../experiments/2026-11-20-p14-41-willett-guard/results.md)). Memory: the CTC prefix beam search kept every prefix ever made (`lm_score`, `_last_id`; T^2 growth on flat null frames, 17.9 GB in a synthetic probe) and the forced alignment held a (T, S) float64 array; both fixed exactly in `fidetype.lm.beam` (caches cut to the beam; frame-wise alignment in groups); run peak 1,194 MB. Guard `tcfg-39aac48688b8bd12` (106 val sentences, alpha 0.05, delta 0.1) returned but LTT not feasible (40 LTT items < 45): offer-only, as pre-stated. Test (80 sentences): 0 commits, 77 offers, 3 withholds; safe WPM v0.1 0.00 (vacuous). Controls pass: calibrate 0/300 uniform, 0/300 frame-shuffled, 0/106 time-shuffled input; test time-shuffled and zero 0/80. Packaged as a release file (local, SHA-256 in the manifest, `trust` set, commits: never). Offers on frame-shuffled frames 77/80 (new gap 136 = P5-31); vector beam path memory (new gap 137 = P5-32).
- **Follow-up:** the guard never commits (not certified, safe WPM vacuous). A certified, non-vacuous guard is tracked as gap 138 = [P14-47](#p14-47-certified-non-vacuous-trust-guard-for-willett-hw-commits--0).
- **Depends on:** P14-33 (done); free machine memory (CPU only).
- **Source:** P14-33 ([results](../../experiments/2026-11-19-p14-33-willett-hw/results.md)): the `guard` stage (`fidetype.trust.calibrate` on the 106 val sentences, 106 time-shuffled nulls, alpha 0.05, delta 0.1) was stopped because the machine was critically low on memory while other jobs ran. `willett-hw` has `trust: null`.
- **Done when:** a guard calibrated on the val blocks is a release file of `willett-hw` (SHA-256 in the manifest, `trust` set), with its decisions on the test blocks (real and time-shuffled input) reported; or a written refusal (null control) with numbers. With greedy CER 0.305 a guard that only offers is an acceptable result. Run it on a quiet machine or with a lower-memory calibration.

#### P14-42 Device and dataset adapter catalogue and contributor template
- **Gap:** 127 of the [open-gap list](open-gaps.md) (added 2026-11-20, user decision). Follow-up of P4-15, P4-01, P4-02.
- **Status:** `done` (2026-11-20).
- **Serves:** BCI companies, research labs, small teams (contributors).
- **Depends on:** P4-15 (gap 110: device support matrix from adapter metadata), P4-01, P4-02, P4-05 (consumer-device adapters), P8-05 (docs site).
- **Source:** User decision (2026-11-20) after a comparison with LangChain history (17,256 commits: about 38 % integrations, 31 % docs, 11 % core; 3,748 contributors). Fidetype has 395 commits and 1 author. The two largest gaps are integrations and docs.
- **Goal:** A catalogue page and a machine-readable registry list every adapter and reader in the repo. Each entry gives the device or dataset, the signal type, the status (tested, experimental or planned), the licence notes and the test coverage. Planned entries cover the common non-invasive devices and public BCI datasets (from P4-05, P4-15 and P18-01). A cookiecutter-style template and a new CONTRIBUTING.md section make a new adapter a PR of about 50 lines. Each new adapter must pass a standard conformance test on synthetic data (no real recordings).
- **Done when:** The registry and the catalogue page exist and list all current adapters and readers with the five fields. CI fails when the page and the registry differ. The template and the CONTRIBUTING.md section exist. The template is used to add at least 2 new adapters, and both pass the conformance test in CI.
- **Result (2026-11-20):** done. Code `8167853`, CI run 44722287677 green. Registry `fidetype.adapters.registry`: built from the `ADAPTER_INFO` dict of each adapter module (all of `fidetype.adapters` plus `fidetype.live.sources`, `fidetype.live.replay`, `fidetype.data.spanishbcbl`) and `fidetype/adapters/planned.py`. Fields: id, kind, target (device / dataset / format), signal, status (tested / experimental / planned), real devices tested (none for all), licence notes, tests, docs. Generated [docs/adapters.md](../../docs/adapters.md) and `docs/adapters.json`: 14 tested, 3 experimental, 16 planned (devices: Muse, Unicorn, Emotiv, Neurosity, Brain Products LSL, OpenBCI real board, EMG wristbands, fNIRS, OPM-MEG; formats / datasets: XDF, BrainVision, BIDS-EEG / MOABB, GDF, inner-speech EEG, ZuCo). `python -m fidetype.adapters.registry --check`; `tests/test_adapter_registry.py` runs it in the normal pytest job, so CI fails on a stale page (no workflow change). Conformance helpers `fidetype.adapters.testing` (`assert_source_conforms` for the `fidetype live` source protocol with NTS 4.1 / 4.2 meta rules; `assert_nts_conforms` wraps the NTS conformance suite; both check `ValueError` on bad input). Template `templates/adapter/` + `python -m fidetype.adapters.registry new <id>`; the scaffolded copy passes its own conformance test (test). [CONTRIBUTING.md 7.1](../../CONTRIBUTING.md#71-add-a-new-adapter-in-about-50-lines). Two new adapters from the template, synthetic files only: `edf` (EDF / EDF+ / BDF, 96 lines, 70 code lines; test 87 / 67) and `openbci-gui` (OpenBCI GUI v5 text, 67 lines, 43 code lines; test 61 / 45). EDF is above the 50-line goal. Both are `experimental` (no real file read yet: gap 134 = [P4-16](#p4-16-real-file-check-of-the-edf-and-openbci-gui-readers)); the `fidetype live` CLI cannot select them yet (gap 135 = [P4-17](#p4-17-file-reader-sources-in-the-fidetype-live-command)). Gap 127 closed.

#### P14-43 10-minute tutorials
- **Gap:** 128 of the [open-gap list](open-gaps.md) (added 2026-11-20, user decision). Follow-up of P14-01, P14-03, P13-06.
- **Status:** `done` (2026-11-20). Three tutorials in tutorials/ (01 decode with a pretrained decoder, 02 trust guard + safe WPM, 03 score on the benchmark), each a script with a synthetic mode (no download; toy model / simulated decoder made at run time) and a documented real-data mode; pages docs/tutorials.md, docs/tutorials-01-decode.md, docs/tutorials-02-trust.md, docs/tutorials-03-benchmark.md; smoke test tutorials/test_tutorials.py and CI workflow .github/workflows/tutorials.yml (Linux + Windows, clean venv). Commit e7b6cb1. CI: green (run 44723379731: ubuntu-latest 0.4 / 62.5 / 0.2 s, windows-latest 0.9 / 94.7 / 0.4 s, all under 10 min). local CPU (Ryzen 7 9800X3D desktop, Windows, Python 3.12): tutorial 1 0.4 s, tutorial 2 79.3 s, tutorial 3 0.4 s (pinned to 2 CPUs: 0.4 / 77.9 / 0.4 s; clean venv with numpy only: 1.6 / 77.5 / 0.4 s). real-data modes on the project machine (local weights, not in CI): T15 decode 5 trials 12.4 s; T15 guard + safe WPM 65 val_eval trials 48.3 s (10 commits, 5 wrong, safe WPM 1.49 above-alpha on this small subset; all 701 trials: 2.23 certified, P14-05); KT-sEMG run28 score 47.4 s (22 / 172 units, key error 0.748, vacuous). API friction: new gaps 129 (P14-44), 130 (P14-45), 131 (P14-46). Docs: [tutorials](../../docs/tutorials.md).
- **Serves:** small teams, research labs, newcomers.
- **Depends on:** P14-01 (pretrained decoders), P14-03 (trust drop-in), P14-05 (safe WPM), P13 benchmark scorer, P14-30 (gap 98: hosted weights; until then the CI smoke test uses synthetic data), P8-05 (docs site).
- **Source:** User decision (2026-11-20) after a comparison with LangChain history (17,256 commits: about 38 % integrations, 31 % docs, 11 % core; 3,748 contributors). Fidetype has 395 commits and 1 author. The two largest gaps are integrations and docs.
- **Goal:** Getting-started tutorials (scripts or notebooks) run in less than 10 minutes on a normal laptop CPU. They use only public or synthetic data and need no hardware. There are at least three: (1) decode text with a pretrained decoder; (2) add the trust guard and read the safe WPM; (3) score a decoder on the benchmark. Each tutorial runs in CI as a smoke test on synthetic data. They extend docs/getting-started.md and docs/trust-quickstart.md.
- **Done when:** The 3 tutorials pass in CI. Each run is timed, and each takes less than 10 minutes.

#### P14-44 Pretrained API newcomer ergonomics
- **Gap:** 129 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P14-43). Follow-up of P14-43, P14-01.
- **Status:** `done` (2026-11-20; commits `6f7fade`, `7c455b7`, `9ebf38a`; CI: tests run 44878237413 and tutorials run 44878237441, green): `toy_model` / `make_toy_manifest`, `n_items` plus a clear `IndexError`, `decode` / `decode_file` with deprecation (`decode(path)` warns), one guard entry point `model.decide(stream)`, the `[hdf5]` extra; tutorial 1 uses them. Follow-ups: gaps 147 = [P14-51](#p14-51-toy-models-for-the-xbody-ctc-crt-ctc-and-key-lda-runtimes), 148 = [P14-52](#p14-52-kt-semg-item-count-from-the-key-log-alone).
- **Source:** P14-43 ([tutorial 1](../../docs/tutorials-01-decode.md#api-friction-found-while-writing-this-tutorial)): (1) no toy-model helper: to try the API without weights, a user must know the GRU parameter names and write a manifest with a SHA-256 by hand; (2) no item count, and `decode_file(indices=...)` past the end raises a bare `IndexError`; (3) `decode()` returns one stream for an array and a list for a file; (4) the guard input differs per model (`stream.log_probs` vs `model.nbest(stream)`); (5) `h5py` comes with the extra `emg2qwerty`, also for T15 / T12 files.
- **Done when:** `fidetype.pretrained` has a documented toy model (for example `toy_model(runtime)`), an item count or a clear error for bad indices, one guard entry point per stream (for example `model.decide(stream)`), and an `h5py` extra with a neutral name; tutorial 1 uses them and still passes the P14-43 smoke test.

#### P14-45 TrustGuard decisions to safe WPM in one call
- **Gap:** 130 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P14-43). Follow-up of P14-43, P14-03, P14-05.
- **Status:** `done` (2026-11-20; commits `6f7fade`, `7c455b7`, `9ebf38a`; CI: tests run 44878237413 and tutorials run 44878237441, green): `fidetype.benchmark.safe_wpm.from_decisions(...)` gives exactly the report of the manual route (equality test in CI); tutorial 2 uses it. Module path: `fidetype.benchmark.safe_wpm`.
- **Source:** P14-43 ([tutorial 2](../../docs/tutorials-02-trust.md#api-friction-found-while-writing-this-tutorial)): from `TrustResult`s to safe WPM a user builds five parallel lists by hand, passes `guard.sheet.to_dict()` through two benchmark functions (`guarantee_from_sheet`, `controls_from_sheet`), and must pick the benchmark text normaliser for the correct / wrong test.
- **Done when:** one documented call (for example `fidetype.trust.safe_wpm(guard, results, truths, neural_s, normalizer=...)`) gives the same report as the manual route on the tutorial 2 data (exact equality test in CI), and tutorial 2 uses it.

#### P14-46 Benchmark glue for custom splits and pretrained decoders
- **Gap:** 131 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P14-43). Follow-up of P14-43, P6-02, P14-01.
- **Status:** `done` (2026-11-20; commits `6f7fade`, `7c455b7`, `9ebf38a`; CI: tests run 44878237413 and tutorials run 44878237441, green): `build_truth(split=)`, `KeyLdaDecoder.track_nbest` / `code_nbest` / `codes_from_text`, `scope` in `guarantee_from_sheet`, KT truth from the key logs only, and the cards in the package (`leaderboard.results_dir`, `committed_results`); tutorial 3 uses them. Follow-up: gap 149 = [P14-53](#p14-53-tutorial-3-real-mode-re-run-after-the-p14-46-changes).
- **Source:** P14-43 ([tutorial 3](../../docs/tutorials-03-benchmark.md#api-friction-found-while-writing-this-tutorial)): (1) `build_truth()` has no `split=` (custom or synthetic splits need hand-built truth rows; the tests monkeypatch `load_split`); (2) `kt-semg-lda` n-best text is screen text, the `kt-semg` track wants key codes, and no converter exists; (3) `guarantee_from_sheet()` output is not a valid submission guarantee (no `scope`, `calibration_split`); (4) `build_truth("kt-semg")` needs every `runN.csv` (about 20 GB) although the truth uses only key logs and start times; (5) the committed leaderboard cards are not in the package.
- **Done when:** `build_truth(..., split=)` exists; a pretrained model can give track-space n-best text (at least `kt-semg-lda`); a guard sheet converts to a valid submission guarantee in one call; KT truth needs only the key logs and start-time files; tutorial 3 uses these and still passes the P14-43 smoke test.

#### P14-47 Certified, non-vacuous trust guard for willett-hw (commits > 0)
- **Gap:** 138 of the [open-gap list](open-gaps.md) (added 2026-11-20 after P14-41). Follow-up of P14-41.
- **Status:** `todo`.
- **Evidence:** 2026-11-20 (P14-48, results `28870eb`): the LM-readout guard `tcfg-8fa3866deec917f3` is still offer-only (40 < 45 LTT); the offered top-1 improved from 0 / 80 to 12 / 77 exact.
- **Evidence:** 2026-11-21 (P14-49, results `dcc344b`): the guard on the Willett-blocked LM with gate C5, `tcfg-26ae951a20a0cddd`, is still offer-only (40 < 45 LTT), 0 commits; offered top-1 12 / 77 exact. 2026-11-21 (P5-31, `367ad72`): the dependency P5-31 is now available; both `willett-hw` guards fail the offer null control only on frame-shuffled frames (297 / 300 and 289 / 300); see gap 150 = [P14-54](#p14-54-frame-order-aware-no-signal-gate-or-offer-check-for-willett-hw).
- **Evidence:** 2026-11-21 (P14-54, results `2c0692f`): both `willett-hw` guards' offer lists now pass the offer null control with the `coherence` offer gate. Still 0 commits, so this item stays open.
- **Evidence:** 2026-11-21 (P14-55, results `0188deb`): gate robustness confirmed (C5 and both offer gates pass on 10 new null draws and new null types). Still 0 commits.
- **Serves:** research labs.
- **Depends on:** about 120 or more calibration sentences (more Willett handwriting data or a different split design); a stronger decoder (gap 26 = [P14-12](#p14-12-willett-hw-word-lm-for-exact-sentence-commits-and-full-test-coverage), gap 120 = [P15-33](#p15-33-e1-low-data-recipe-that-reads-the-target-signal-before-more-source-arms)); gap 136 = [P5-31](#p5-31-null-control-for-offers) (null control for offers).
- **Source:** P14-41 ([results](../../experiments/2026-11-20-p14-41-willett-guard/results.md)): the packaged `willett-hw` guard never commits. It is not certified: with 106 val sentences the LTT half has 40 items, and 45 are needed at alpha 0.05. Test safe WPM v0.1 is 0.00 (vacuous). Gap 121 closed under its pre-registered rule (an offer-only guard was acceptable). The user's standing rule keeps the gap tracked until it is truly met.
- **Done when:** a pre-registered run packages a `willett-hw` guard that is certified (LTT feasible) and commits on the test blocks (commits > 0) with a non-vacuous safe WPM v0.1, with the null controls passing (commits and, after P5-31, offers); or numbers say why not.


#### P14-48 willett-hw with the same-LM readout and a no-signal gate
- **Gap:** 144 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P15-25). Follow-up of P14-33 and P15-25.
- **Status:** `done` (2026-11-21; orchestrator decision: D1 is now met by the P14-49 gate C5, results `dcc344b`: N1' time-shuffled 2, zero 0, uniform 0 of 80 emit; N2 frame-shuffled CER 0.881. D2 re-stated for the Willett-blocked LM (overlap none). D3: guard `tcfg-26ae951a20a0cddd`, not certified, offer-only).
- **Evidence:** P14-48 run 2026-11-20 (pre-registration `59c32ea`, code `f14b5b4`, results `28870eb`, [results](../../experiments/2026-11-20-p14-48-willett-lm-readout/results.md)): opt-in F readout packaged (`m.text(stream, readout="lm")`, `fidetype.pretrained.lmreadout`); test CER 0.1734 ungated (= P15-25, 80 / 80 same text), 0.1760 gated; D2 and D3 met. N1 fails: the gate lets 13 / 80 time-shuffled test inputs emit text (limit 4); uniform and zero 0 / 80; N2 pass (frame-shuffled CER 0.883). Guard `tcfg-8fa3866deec917f3` re-calibrated: not certified (40 < 45 LTT), 0 commits, 77 offers (12 exact), safe WPM 0.00 vacuous; commit controls pass. Blocked by gap 145 = [P14-49](#p14-49-no-signal-gate-for-willett-hw-that-stops-time-shuffled-input); the Willett-blocked LM is gap 146 = [P14-50](#p14-50-willett-blocked-tatoeba-lm-as-the-willett-hw-lm-readout).
- **Serves:** research labs.
- **Depends on:** P15-25 (done); P14-33 (`willett-hw` package, R-ball-s0 weights); the P14-41 guard; feeds gap 138 = [P14-47](#p14-47-certified-non-vacuous-trust-guard-for-willett-hw-commits--0).
- **Source:** P15-25 ([results](../../experiments/2026-11-20-p15-25-e1-same-lm/results.md)): with decoder F (Tatoeba 6-gram, w 0.5, beta 1, beam 8) the packaged decoder falls from test CER 0.305 (greedy) to 0.173. On uniform log-probs F emits one token per frame (4,100 of 4,100), so the LM readout needs a no-signal gate before any commit.
- **Done when:** `willett-hw` offers the F readout with a no-signal gate (null controls pass), the card states the LM licence (CC BY 2.0 FR, attribution) and the test overlap, and the P14-41 guard is re-calibrated on the new readout with its numbers reported.

#### P14-49 No-signal gate for willett-hw that stops time-shuffled input
- **Gap:** 145 of the [open-gap list](open-gaps.md) (added 2026-11-20). Follow-up of P14-48, P11-12.
- **Status:** `done` (2026-11-21; pre-registration and code `76747e8`, results `dcc344b`, [results](../../experiments/2026-11-20-p14-49-willett-gate-blocked-lm/results.md)). Val-only selection chose gate C5 (logistic score: peak, neg-entropy, non-blank share, kps, log(1 + n_keys)). Test: time-shuffled 2 / 80, zero 0 / 80, uniform 0 / 80 emit; real gated 1 / 80; N2 pass (0.881). Packaged as the default LM-readout gate. Guard `tcfg-26ae951a20a0cddd`: not certified, offer-only. Frame-shuffled frames pass C5 (79 / 80): follow-up gap 150 = [P14-54](#p14-54-frame-order-aware-no-signal-gate-or-offer-check-for-willett-hw); robustness: gap 151 = [P14-55](#p14-55-robustness-check-of-the-willett-hw-gate-c5).
- **Serves:** research labs.
- **Depends on:** P14-48 (done run, gate failed N1); val blocks only; CPU. Blocks gap 144 = P14-48.
- **Source:** P14-48 ([results](../../experiments/2026-11-20-p14-48-willett-lm-readout/results.md)): the P11-12 count gate (n_keys >= 7, kps 0.425-2.834) lets 13 / 80 time-shuffled test inputs emit text (limit 4).
- **Ideas:** the share of non-blank frames, or the emission rate against the length of the LM text.
- **Done when:** a separately pre-registered, val-only gate gets time-shuffled, zero and uniform input each to at most 4 / 80 emitting, with real input gated at most 5 %.

#### P14-50 Willett-blocked Tatoeba LM as the willett-hw LM readout
- **Gap:** 146 of the [open-gap list](open-gaps.md) (added 2026-11-20). Follow-up of P14-48, P15-38.
- **Status:** `done` (2026-11-21; pre-registration and code `76747e8`, results `dcc344b`, [results](../../experiments/2026-11-20-p14-49-willett-gate-blocked-lm/results.md)). The manifest LM is the Willett-blocked LM (SHA-256 row `d7f6e829...059261`, local read-only, test overlap none). Test CER 0.1743 ungated (= P15-38 on 80 / 80), 0.1746 gated; null controls and guard re-measured.
- **Serves:** research labs.
- **Depends on:** P15-38 (done; local `derived\p15-38\eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz`, sha256 d7f6e829...); can be done with P14-49; CPU.
- **Source:** P14-48 and P15-38 (2026-11-20): the packaged readout uses `eng_tatoeba_6gram_mkn_noE2Q.npz`, which holds 13 of 80 Willett test sentences; P15-38 built an LM with every Willett text blocked.
- **Done when:** the Willett-blocked LM is the `willett-hw` LM readout (local release file with a SHA-256 row, no test overlap), and the CER, the null controls and the guard are re-measured.

#### P14-51 Toy models for the xbody-ctc, crt-ctc and key-lda runtimes
- **Gap:** 147 of the [open-gap list](open-gaps.md) (added 2026-11-20). Follow-up of P14-44.
- **Status:** `done` (2026-11-21; commit `8ab2cb2`; CI `tests` run 44895851514 green). `toy_model(runtime)` works for `gru-ctc`, `xbody-ctc`, `crt-ctc` and `key-lda` (random weights made in code, CC0, < 2 MB, nothing generated is committed). API now `toy_model(runtime="gru-ctc", folder=None)` (API not yet released). Tests: `tests/test_toy_models.py` (9) + `test_api_ergonomics`, 19 pass.
- **Serves:** small teams, newcomers.
- **Depends on:** P14-44 (done). Low priority.
- **Source:** P14-44 (2026-11-20, commits `6f7fade`, `9ebf38a`): `toy_model` exists only for the `gru-ctc` runtime.
- **Done when:** `toy_model(runtime)` works for `xbody-ctc`, `crt-ctc` and `key-lda`, with a test for each.

#### P14-52 KT-sEMG item count from the key log alone
- **Gap:** 148 of the [open-gap list](open-gaps.md) (added 2026-11-20). Follow-up of P14-44, P14-46.
- **Status:** `done` (2026-11-21; commit `05a3f08`; CI `tests` run 44895398281 green). `count_items("kt-semg-run")` / `n_items` read only `runN_keys.txt` and `runN_ts.txt` (the CSV is not opened; new `readers.count_kt_run`, `kt_semg.infer_utc_offset_from_keys`). The count equals `read_kt_run` on all 29 local runs; run28 count 2 ms vs 26.5 s. Tests: `tests/test_kt_count_items.py` (4). Two documented cases where the counts could differ (typing starts more than 1 h after the EMG start; a key press in the last 0.15 s) do not occur in the dataset.
- **Serves:** small teams, research labs.
- **Depends on:** P14-44, P14-46 (done). Low priority.
- **Source:** P14-44 / P14-46 (2026-11-20): KT-sEMG `n_items()` reads the whole `runN.csv`, although the count needs only the key log.
- **Done when:** KT-sEMG `n_items()` reads only the key log (and start-time file), with a test that it gives the same count.

#### P14-53 Tutorial 3 real mode re-run after the P14-46 changes
- **Gap:** 149 of the [open-gap list](open-gaps.md) (added 2026-11-20). Follow-up of P14-43, P14-46.
- **Status:** `done` (2026-11-21; commit `f797f0f`, [tutorial](../../docs/tutorials-03-benchmark.md); tutorials CI run 44888427226 green). Real mode on KT-sEMG run28 passes: 22 / 172 units, key error 0.748, eWPM 2.40 (no-BCI 2.82), 22 offers, 0 commits, safe WPM 0.00 (vacuous), all controls pass, status `scored`, 48.2 s on 2 CPUs. The key-log-only truth equals the committed truth file in all 172 rows; both committed `kt-semg` cards rescore exactly. eWPM 2.55 -> 2.40 because the tutorial now offers the top 3 instead of the top 1 (expected). Bug fixed: NaN in `card.json` -> strict JSON (null), with a test.
- **Serves:** small teams, newcomers.
- **Depends on:** P14-46 (done); local KT-sEMG data; CPU only.
- **Source:** P14-46 (2026-11-20): tutorial 3 now uses `build_truth(split=)`, key-log-only KT truth and track-space n-best; its real mode (KT-sEMG run28) was not re-run on the project machine.
- **Done when:** tutorial 3 real mode (KT-sEMG run28) runs on the project machine after the P14-46 changes, and its numbers are written in docs/tutorials-03-benchmark.md (same or explained).

#### P14-54 Frame-order-aware no-signal gate or offer check for willett-hw
- **Gap:** 150 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P14-49 and P5-31). Follow-up of P14-49, P5-31.
- **Status:** `done` (2026-11-21; CI `tests` run 44906980131 and `tutorials` run 44906980013 green; pre-registration `09def1e`, results `2c0692f`, [results](../../experiments/2026-11-21-p14-54-willett-order-gate/results.md)). Offer gate `coherence` (P5-33 `OfferGate`): built-in guard `tcfg-39aac48688b8bd12` threshold 0.004183, LM guard `tcfg-26ae951a20a0cddd` threshold 0.002821. Gated `recheck_offer_control` PASS for both: uniform 0 / 300, frame-shuffled 0 / 300 (were 297 / 300 and 289 / 300), time-shuffled 0 / 106, real 40 / 40. Test (80 sentences), each guard: real 77 / 80 offers, 0 removed by the gate; frame-shuffled 0 / 80 (was 77); time-shuffled 1 / 80; zero 0 / 80; uniform 0 / 80. Commits unchanged (0); guard files and `config_id` unchanged. Manifest `willett-hw.json`: `offer_gate` blocks on by default; gated `offer_control` (PASS) with `before_gate` kept. Limits: `coherence` checks only the frame order (not neural data of another task, not time-reversed streams); thresholds from 66 sentences of one participant.
- **Follow-up:** gap 151 = [P14-55](#p14-55-robustness-check-of-the-willett-hw-gate-c5) (done-when extended: new null types for the gate).
- **Evidence:** 2026-11-21 (P5-33, `9ce8006`, [results](../../experiments/2026-11-21-p5-33-withhold/results.md)): on `t15-m4-13` the frame-order feature `coherence` stopped frame-shuffled input fully (0 / 300 offers), against 275-287 / 300 for the per-frame features. Gap 152 closed; this `willett-hw` part stays open here.
- **Serves:** research labs.
- **Depends on:** P14-49, P5-31 (done); val blocks only; CPU. This is the `willett-hw` part of gap 152 = [P5-33](#p5-33-offer-policy-that-withholds-on-no-evidence-input-and-the-offer-control-default).
- **Source:** P14-49 (2026-11-21, results `dcc344b`, [results](../../experiments/2026-11-20-p14-49-willett-gate-blocked-lm/results.md)): frame-shuffled frames pass gate C5 on 79 / 80 test inputs and get offers on 77 / 80 (real 77 / 80). P5-31 re-check (`367ad72`): both `willett-hw` guards fail the offer null control only on frame-shuffled frames (297 / 300 and 289 / 300; real 40 / 40). The C5 features are per-frame statistics, so they cannot see the frame order.
- **Done when:** a separately pre-registered, val-only gate or offer check that reads the frame order makes both `willett-hw` guards pass `recheck_offer_control` on frame-shuffled frames (the P5-31 rule), with time-shuffled, zero and uniform input each still at most 4 / 80 emitting and real input gated at most 4 / 80; or numbers say why not. Then refresh the manifest `offer_control` blocks from the new re-check.

#### P14-55 Robustness check of the willett-hw gate C5
- **Gap:** 151 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P14-49). Follow-up of P14-49.
- **Status:** `done` (2026-11-21; pre-registration `34f3553`, results `0188deb`, [results](../../experiments/2026-11-21-p14-55-willett-gate-robustness/results.md)). Gap 151 closed. Every pre-registered rule passes. C5 over 10 new draws x 80: time-shuffled 26 / 800 emit, one-sided CP95 0.0448 (pass, small margin; cluster bootstrap 0.0475; one draw 5 / 80); near-uniform 0 / 800 (bound 0.0037); zero 0 / 80 (deterministic). Re-fit spread: no coefficient sign change over 200 half-splits and 10 re-fits; threshold `lo` ranges -1.43 to 2.00 (shipped -1.17). `coherence` offer gate, both guards, rules C1-C6 pass: time-shuffled 14 / 800 and 13 / 800, frame-shuffled 0, near-uniform 0, input time-reversed 2 / 80 and 1 / 80, real T5 `doNothing` 0 / 27, real T5 unseen straight-line session 0 / 80. Limit: log-prob frames reversed after the decoder (`rev_out`, software-fault-only input) get the same `coherence`, so the guards offer on 77 / 80 and 78 / 80. T15 / T12 data are not usable (different array and bin width). Deviation: `doNothing` has only 27 inputs (rule limit 1), stated. Nothing shipped changed; `config_id`s unchanged. No CI needed (experiment files only).
- **Follow-ups:** gap 171 = [P14-57](#p14-57-direction-aware-offer-check-for-willett-hw) (direction-aware offer check, low priority); gap 172 = [P14-58](#p14-58-c5-threshold-rule-without-the-minimum-real-score) (C5 threshold rule without the minimum real score, low priority).
- **Serves:** research labs.
- **Depends on:** P14-49 (done); CPU. Low priority.
- **Source:** P14-49 (2026-11-21, results `dcc344b`, limits): one participant, one draw of each null input, no CI. The test margin of N1' is 2 of 4. The fit used one draw of the time-shuffled input.
- **Done when:** the C5 emit counts are reported over at least 10 new draws of each null input with a 95 % upper bound on the emit rate, and C5 is re-fitted on other inner splits of the 66 val positions with the spread of its coefficients and threshold reported; or numbers say why not. Extension (2026-11-21, from P14-54): also re-check the `coherence` offer gate of both `willett-hw` guards on new null types (time-reversed streams, real data of another task or session) with a pre-registered rule.

#### P14-56 Offer-control result in the packaged manifests and model cards
- **Gap:** 153 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P5-31). Follow-up of P5-31, P14-01.
- **Status:** `done` (2026-11-21; commit `f2eb771`, updated by `9ce8006`). All four packaged guards carry the P5-31 offer-control result in their manifest (`trust.offer_control`; the `willett-hw` LM readout in `readouts.lm.trust.offer_control`) and in the `Manifest.card()` output. `tests/test_pretrained_offer_control.py` checks the values against the re-check JSON files; section in docs/pretrained-decoders.md; CHANGELOG entry. Since `9ce8006` the `t15-m4-13` block shows the gated re-check (pass) with the `before_gate` counts. The blocks are copied by hand: gaps 150 and 155 refresh them from their new re-checks.
- **Serves:** research labs, small teams.
- **Depends on:** P5-31 (done); can be done before gap 152 = P5-33; CPU.
- **Source:** P5-31 (2026-11-21, `367ad72`): the re-check results are only in `experiments/2026-11-21-p5-31-offer-control/results/recheck-*.json`. The manifests and model cards do not show them.
- **Done when:** each packaged manifest and model card shows the offer-control verdict and the offer counts per control (from `recheck_offer_control`), a test checks that the card values equal the result files, and docs/pretrained-decoders.md explains the field.

#### P14-57 Direction-aware offer check for willett-hw
- **Gap:** 171 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P14-55). Follow-up of P14-55, P14-54.
- **Status:** `done` (2026-11-21; negative result). Gap 171 closed. negative result, "numbers say why not" (pre-registration `e1f8573` 21:14, results `71f954e` 23:12, [results](../../experiments/2026-11-21-p14-57-direction-aware-offer/results.md)): the 0-threshold time-direction gate (`-nb_decay_asym`) fails its val limit (it removes 14 / 66 built-in and 19 / 66 LM real val offers; limit 3). Test (information only): `rev_out` offers 77 -> 11 and 78 -> 18 (limit <= 4); real offers removed 11 / 80 and 17 / 80 (limit 4); the P14-55 nulls keep their results (D3 pass); real LTT offers 33 and 32 of 40 (limit >= 36). Why: the per-sentence time direction is weak (79 % / 71 % majority sign). Nothing shipped. Deviations: run stopped with a STOP file at 22:49 and relaunched in the order p58 p57 score (no input or rule changed); a bug in the D3 repeat check was fixed after the first score run (no count changed).
- **Follow-ups:** gap 181 = [P5-36](#p5-36-frame-order-integrity-check-in-the-trust-layer) (frame-order integrity check in the trust layer).
- **Serves:** research labs.
- **Depends on:** P14-55 (done); val blocks only; CPU.
- **Source:** P14-55 ([results](../../experiments/2026-11-21-p14-55-willett-gate-robustness/results.md)): `coherence` is symmetric in time, so log-prob frames reversed after the decoder (`rev_out`) get the same `coherence` as real input (80 / 80); the guards offer on 77 / 80 (built-in) and 78 / 80 (LM). Only a software fault can make this input; it is outside the gap 150 null set, so no rule failed.
- **Done when:** a val-only pre-registered check stops log-prob-reversed input (`rev_out`) at <= 4 / 80 offers on test for both guards, removes <= 4 / 80 real offers, and keeps the P14-54 / P14-55 null results; or numbers say why not.

#### P14-58 C5 threshold rule without the minimum real score
- **Gap:** 172 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P14-55). Follow-up of P14-55, P14-49.
- **Status:** `done` (2026-11-21; pass). Gap 172 closed. (pre-registration `e1f8573`, results `71f954e`, [results](../../experiments/2026-11-21-p14-57-direction-aware-offer/results.md)): quantile_lo rule lo_new = max(HD_0.03(real S scores), Q_0.99(726 val time-shuffled scores)) = 0.5659 (shipped -1.1697). E1: new test time-shuffled draws d = 11..20 emit 0 / 800, CP95 0.0037 (limit 0.04); the shipped `lo` gives 18 / 800, CP95 0.0332. E2: real test gated 3 / 80 (limit 4; shipped 1 / 80). Nothing shipped. P14-58 stage 22:49:14-23:08:32.
- **Follow-ups:** gap 182 = [P14-59](#p14-59-ship-the-p14-58-c5-threshold-in-the-willett-hw-manifest) (ship `lo_new`: user decision).
- **Serves:** research labs.
- **Depends on:** P14-55 (done); val blocks only; CPU.
- **Source:** P14-55 ([results](../../experiments/2026-11-21-p14-55-willett-gate-robustness/results.md)): C5 time-shuffled emits 26 / 800, CP95 0.0448 (pass with a small margin; cluster bootstrap 0.0475; one draw 5 / 80). The threshold `lo` is the smallest real fit score: over 200 half-splits `lo` ranges from -1.43 to 2.00 (shipped -1.17), and the held-out real loss goes up to 9 / 33.
- **Done when:** a pre-registered C5 threshold rule gives time-shuffled emits with a CP95 upper bound <= 0.04 over >= 10 draws and real input gated <= 4 / 80 on test; or numbers say why not.

#### P14-59 Ship the P14-58 C5 threshold in the willett-hw manifest
- **Gap:** 182 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P14-58). Follow-up of P14-58, P14-56.
- **Status:** `done`. Done 2026-11-22, shipped (user decision "all recommended"; pre-registration `dedf60c`, results `75404c0`, [results](../../experiments/2026-11-22-p14-59-ship-lo/results.md); CPU only, 22:16-22:25): all three re-checks pass. RC1: the LM guard calibrated again with `lo_new` 0.5659 (decoder_version 3) = `tcfg-f498c0637536daec` (was `tcfg-26ae951a20a0cddd`); commit controls 0 / 300, 0 / 300, 0 / 106; 0 LTT commits; 0 test commits; real test gated 3 / 80; time-shuffled, zero, uniform emit 0 / 80. RC2: `coherence` offer gate refitted by the P14-54 rule = 0.003486 (was 0.002821); S rule pass; LTT offers 40 / 40; test nulls 0 / 80; frame-shuffled 0 / 80 vs real 77 / 80; 0 real offers removed. RC3: `recheck_offer_control` pass (0 / 300, 0 / 300, 0 / 106 vs real 40 / 40), commits match the sheet. Manifest `willett-hw` (new guard file `willett-hw.lm3.guard.json`), model card, tests, docs, changelog updated. Gap 182 closed.
- **Serves:** research labs.
- **Depends on:** P14-58 (done); the user decision (the real cost goes up); CPU.
- **Source:** P14-58 (2026-11-21, results `71f954e`, [results](../../experiments/2026-11-21-p14-57-direction-aware-offer/results.md)): `lo_new` 0.5659 gives 0 / 800 time-shuffled emits (CP95 0.0037) but gates 3 / 80 real test inputs (shipped `lo` -1.1697: 1 / 80). Shipping it changes the LM readout, the LM guard decoder, its `coherence` offer gate (fitted with the shipped C5) and the P14-56 offer-control block.
- **Done when:** the user decides. If yes: re-check the LM guard, its `coherence` offer gate (fitted with the shipped C5) and the P14-56 offer-control block of the LM readout, then change the manifest (new `config_id`). If no: record the reason.

#### P14-60 Ship the lm_beam_direction offer gate in the willett-hw manifests
- **Gap:** 190 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P5-36b). Follow-up of P5-36, P14-56.
- **Status:** `done` (2026-11-23, commit `212da07`). Gap 190 closed. Both `willett-hw` guards ship `coherence`, then `lm_beam_direction >= 0` (fixed threshold 0, not fitted). P14-56 re-checks pass for both: uniform 0 / 300, frame-shuffled 0 / 300, time-shuffled 0 / 106, real 40 / 40, commits match the sheet. Wiring on the 80 test sentences (information only): built-in real offers 77 -> 76, `rev_out` 77 -> 1; LM real 77 -> 75, `rev_out` 77 -> 2. pytest 1922 passed, 45 skipped; wording check 0. `config_id` values unchanged: built-in `tcfg-39aac48688b8bd12`, LM `tcfg-f498c0637536daec`. Behaviour change: both guards now need the local LM file. Started after the user closed gap 181 by decision (option C). Earlier note (2026-11-23): gap 189 passed only as weak evidence, so this item waited for that decision.
- **Follow-up:** gap 200 = [P5-39](#p5-39-offer-gate-identity-in-the-guard-identity) (an identity for the offer-gate list).
- **Serves:** research labs.
- **Depends on:** gap 189 = P5-37 (must pass first); P14-56 (done); CPU.
- **Source:** P5-36b (2026-11-22, results `a7bfbc8`, [results](../../experiments/2026-11-22-p5-36b-two-direction-lm/results.md)): the direction gate is in the library but not in any packaged gate list, guard file or manifest. `config_id` values unchanged.
- **Done when:** if gap 189 passes: the gate is in the manifest gate list of both `willett-hw` guards ~~(new `config_id`)~~, the `readout=` wiring passes it to the LM readout, the model cards state the gate, its rule and its cost, and the P14-56 offer-control blocks are re-checked and pass. If gap 189 fails: record the reason and close without a change.
- **Done-when amendment (user decision 2026-11-23, option A):** the clause "(new `config_id`)" is removed (struck through above). Reason: `config_id` is computed from the frozen trust config only, and by documented design an offer gate never changes it (as in P14-54). So the clause could not be met by any correct change. The gap that this leaves (two guards with different gate lists can share a `config_id`) is gap 200 = [P5-39](#p5-39-offer-gate-identity-in-the-guard-identity).

#### P14-61 Switch the scorer and the leaderboard to the adopted safe-WPM v0.2
- **Gap:** 196 of the [open-gap list](open-gaps.md) (added 2026-11-22 by the user decision on safe-WPM v0.2). Follow-up of P14-26, P14-28, P15-29.
- **Status:** `done` (2026-11-23, commit `38f1e50`; CI `tests` run 45325134496 green). Gap 196 closed. `safe-wpm/0.2` is the code default (with the `aac-gaze-v1` reading cost); v0.1 stays selectable and gives byte-identical numbers; the leaderboard headline column is v0.2; 25 old experiment scripts pin their metric version; no v0.1 number is re-labelled. Full suite 1931 passed, 46 skipped.
- **Follow-ups:** gap 202 = [P14-62](#p14-62-safe-wpm-wording-in-the-drop-in-module), gap 203 = [P14-63](#p14-63-several-commits-per-trial-extension-of-safe-wpm-v02), gap 204 = [P13-14](#p13-14-rescore-the-tracks-v01-benchmark-cards-under-safe-wpm-v02), gap 205 = [P14-64](#p14-64-headline-callers-of-calibration_draw_interval-use-partition-draws-and-k--80).
- **Serves:** research labs, small teams.
- **Depends on:** P14-26, P14-28, P15-29 (done); CPU.
- **Source:** user decision 2026-11-22 ("all recommended"): adopt `safe-wpm/0.2` with the reading cost (`aac-gaze-v1`, 0.5 s + 0.3 s per word per commit), calibration-inclusive intervals with K >= 80 draws, and partition-only draws. The docs say so ([docs/safe-wpm.md](../../docs/safe-wpm.md) sections 6a, 6b; [proposal](../../docs/safe-wpm-v0.2-proposal.md)). The code still says "proposed, not adopted": `V02_STATUS`, `CALIBRATION_INTERVAL`, the default `metric_version="0.1"`, the CLI help, the leaderboard banner and column, the site test (`tests/test_publishing_metadata.py`) and the track-page test.
- **Done when:** the scorer default is v0.2 with the adopted reading cost, the status strings say "adopted 2026-11-22", the leaderboard shows v0.2 as the headline column with a dated note and v0.1 as a second column, every v0.1 number keeps its value and its v0.1 label (no re-label), `calibration_draw_interval` warns when K < 80 or the draws are not partition-only, the tests and the generated pages are updated, and CI is green.

#### P14-62 safe-WPM wording in the drop-in module
- **Gap:** 202 of the [open-gap list](open-gaps.md) (added 2026-11-23 by P14-61). Follow-up of P14-61.
- **Status:** `in_progress` (2026-11-24; one code-fix agent runs gaps 200, 202, 205, 195 and 213; nothing committed yet). Low priority.
- **Serves:** research labs, small teams.
- **Depends on:** P14-61 (done); the gap 191 (P5-38) agent commits first, because it edits the same file; CPU. Low priority.
- **Source:** P14-61 (2026-11-23, commit `38f1e50`): `src/fidetype/trust/dropin.py` (about line 1703) still says "safe-wpm/0.2 (proposed)". safe-WPM v0.2 was adopted on 2026-11-22.
- **Done when:** the text says that v0.2 is adopted (2026-11-22), no behaviour changes, and the tests pass.

#### P14-63 Several-commits-per-trial extension of safe-WPM v0.2
- **Gap:** 203 of the [open-gap list](open-gaps.md) (added 2026-11-23 by P14-61). Follow-up of P14-61.
- **Status:** `todo`.
- **Serves:** research labs, small teams.
- **Depends on:** P14-61 (done); a user decision on an agent recommendation; CPU.
- **Source:** P14-61 (2026-11-23, commit `38f1e50`): the adopted v0.2 scorer covers one commit per trial. An extension for trials with several commits exists as an idea, but nobody decided to adopt it.
- **Done when:** a decision (adopt or not) is recorded in docs/safe-wpm.md with its reason. If adopted: the scorer and the tests implement it, and no earlier number is re-labelled.

#### P14-64 Headline callers of calibration_draw_interval use partition draws and K >= 80
- **Gap:** 205 of the [open-gap list](open-gaps.md) (added 2026-11-23 by P14-61). Follow-up of P14-61, P15-29.
- **Status:** `in_progress` (2026-11-24; one code-fix agent runs gaps 200, 202, 205, 195 and 213; nothing committed yet).
- **Serves:** research labs, small teams.
- **Depends on:** P14-61 (done); CPU.
- **Source:** P14-61 (2026-11-23, commit `38f1e50`): `calibration_draw_interval` warns when K < 80 or when the draws are not partition-only, but it does not refuse. The adopted v0.2 rule (user decision 2026-11-22) needs K >= 80 and partition-only draws for a headline result.
- **Done when:** every caller that makes a headline result (experiment scripts, the leaderboard build, docs examples) passes `draw_scheme="partition"` and K >= 80, or its result is labelled "not a headline". A test or a check finds no headline caller that breaks the rule.

## P15. Frontier (added 2026-11-15, leads)
**Goal:** move toward the [north star](north-star.md): a BCI that reads language from any body signal, teaches itself from daily use, and provably never puts words in the user's mouth. P15 runs the first experiments of the three frontier pillars and their follow-ups.

**User decision (2026-11-15):** "stop attaching this project to an existing project, find a new frontier that does not exist in BCI yet ... and go that route." P15 leads from now on. No existing item moves, changes its ID or is removed. Existing items become the base: the trust layer is the guarantee engine for F1 and F2; the decoders, adapters and datasets are the base for F3; the NTS spec, SDKs and collector are internal plumbing with a lower priority; the demo shows F1 / F2 progress ([mapping](north-star.md#how-existing-work-maps-in)).

**Pillars** (ranked by the prior-art and feasibility studies, [why new](north-star.md#why-this-is-new)):

| Pillar | Content | Novelty (study) | First experiment |
|---|---|---|---|
| **F1** (lead) | Safe self-improving BCI: the decoder learns from accept / reject / correction feedback, and a stated error bound stays valid through every update | High | E2 |
| **F2** | Faithful LLM decoding: run-time grounding check of LLM text against the neural evidence, risk-controlled hallucination bound, public hallucination benchmark | Medium-high | E3 |
| **F3** | Cross-body language model: shared character / phoneme output space across implant and EMG (later MEG/EEG), "new modality / new user with minutes of data" | High on paper, medium in practice | E1 |

**Rules:**
- Each experiment commits a `plan.md` with frozen success criteria **before** its runs (P14-03 pattern).
- No public novelty claim before P15-10 (focused literature check).
- One GPU job at a time. CPU work runs while the GPU trains.
- Clean track (CC0 + CC BY) and research-only track (emg2qwerty, SpanishBCBL) stay separate. Each checkpoint carries its data licences.
- Silent errors are always reported and never claimed as covered by a guarantee.
- Write-ups are not papers. Papers stay in PUB with no deadline.

### Deliverables
| ID | Item | Pillar | Depends on |
|---|---|---|---|
| **P15-00** | North star page + P15 scope (this phase, diagram, tracker) | all | — |
| **P15-01** | E2 CPU pilot: T12 replay simulator with a simulated user, feedback-only adaptation vs frozen | F1 | T12 v2 decoder, `fidetype.trust.online_risk` |
| **P15-02** | Decoder-update loop + re-calibration hooks in the trust layer (champion / challenger gate) | F1 | P15-01, P14-03, P5-02 |
| **P15-03** | E2 full runs on GPU: T12 (24 sessions), then T15 (45 sessions) | F1 | P15-02, GPU after M4-13 / P11-01 |
| **P15-04** | Online risk control with bandit (shown-only) feedback + a formal statement of what the guarantee covers | F1 | P15-02 |
| **P15-05** | E3: local LLM rescoring / constrained rewrite with a grounding check on T15 and T12 | F2 | local LLM install, M4-12, T12 v2 |
| **P15-06** | Risk-controlled hallucination bound at run time (CRC / LTT on a fluent-wrong loss) | F2 | P15-05 |
| **P15-07** | Public hallucination benchmark: null / scrambled / swapped-signal tracks | F2 | P15-05, P6-02 |
| **P15-08** | E1: Willett character CER at 10–100 % data with text-only, EMG and implant pretrained trunks | F3 | GPU, P11-01 weights (research arm) |
| **P15-09** | "New modality / new user with minutes of data" benchmark + reverse transfer (implant → EMG, E1b) | F3 | P15-08 |
| **P15-10** | Focused literature check before any public novelty claim | all | — |
| **P15-11** | Demo shows F1 / F2: a decoder that improves across sessions while the guarantee line stays | F1, F2 | P15-03 or P15-01, P15-06, P14-06 |
| **P15-12** | Frontier result write-ups (one per experiment, negative results included) | all | P15-01, P15-03, P15-05, P15-08 |
| **P15-13** | Update gate: PER-based non-inferiority challenger test (open gap 1, [details](#p15-13-update-gate-per-based-non-inferiority-challenger-test)) | F1 | M4-13 rerun result H3 (plan); P15-02 |
| **P15-14** | Certified hallucination bound on T12 (or proof that none is possible) (open gap 2, [details](#p15-14-certified-hallucination-bound-on-t12-or-proof-that-none-is-possible)) | F2 | M4-13; pre-registered V-single variant (plan); P15-06 |
| **P15-15** | Hallucination benchmark protocol 0.2: paired swapped / real commit-ratio pass rule (open gap 4, [details](#p15-15-hallucination-benchmark-protocol-02-paired-swapped--real-commit-ratio-pass-rule)) | F2 | P15-07 |
| **P15-16** | Hallucination benchmark baseline that commits often and checks the signal (open gap 4, [details](#p15-16-hallucination-benchmark-baseline-that-commits-often-and-checks-the-signal)) | F2 | P15-15; M4-13 / P11 decoders; P15-06 |
| **P15-17** | G3 audit: independent proof review and its fixes (open gap 6, [details](#p15-17-g3-audit-independent-proof-review-and-its-fixes)) | F1 | P15-04 |
| **P15-18** | Pilots store per-item null-control outputs (open gap 13, [details](#p15-18-pilots-store-per-item-null-control-outputs)) | all | — |
| **P15-19** | Show usefulness on stronger decoders (P5-01, P15-02, P5-02, P15-06) (open gap 14, [details](#p15-19-show-usefulness-on-stronger-decoders-p5-01-p15-02-p5-02-p15-06)) | all | M4-13 rerun queue, P11-01 |
| **P15-20** | Hallucination split halluc-v0.1 (T15): exact trial-index rule (open gap 34, [details](#p15-20-hallucination-split-halluc-v01-t15-exact-trial-index-rule)) | F2 | P15-07 |
| **P15-21** | Hallucination benchmark: absolute bound on unsupported swapped commits next to the ratio rule (open gap 52, [details](#p15-21-hallucination-benchmark-absolute-bound-on-unsupported-swapped-commits-next-to-the-ratio-rule)) | F2 | P15-15, P15-16 |
| **P15-23** | Update gate refuses a challenger without champion outputs (open gap 71, [details](#p15-23-update-gate-refuses-a-challenger-without-champion-outputs)) | F1 | P15-13 |
| **P15-24** | Same-decoder re-calibrations under the default-deny gate (open gap 72, [details](#p15-24-same-decoder-re-calibrations-under-the-default-deny-gate)) | F1 | P15-13, P5-01 |
| **P15-25** | E1 readout with the same character LM (open gap 91, [details](#p15-25-e1-readout-with-the-same-character-lm)) | F3 | P15-08 (E1a), P11-07 |
| **P15-26** | T12 replication of LLM rescoring + learned commit confidence (open gap 93, [details](#p15-26-t12-replication-of-llm-rescoring--learned-commit-confidence)) | F1, F2 | P15-22 |
| **P15-27** | Guard n-best top-1 differs from the pipeline top-1 on 9 of 701 trials (open gap 94, [details](#p15-27-guard-n-best-top-1-differs-from-the-pipeline-top-1-on-9-of-701-trials)) | F1 | P15-22 |
| **P15-28** | Recompute the M4-12 and T12 P15-05 / P15-06 / P15-07 WER values with the sorted grounding order (open gap 97, [details](#p15-28-recompute-the-m4-12-and-t12-p15-05--p15-06--p15-07-wer-values-with-the-sorted-grounding-order)) | F1 | P15-27 |
| **P15-29** | Safe WPM interval that includes the calibration draw (open gap 103, [details](#p15-29-safe-wpm-interval-that-includes-the-calibration-draw)) | F1 | P15-26 |
| **P15-33** | E1 low-data recipe that reads the target signal before more source arms (open gap 120, [details](#p15-33-e1-low-data-recipe-that-reads-the-target-signal-before-more-source-arms)) | F3 | P15-08 (E1a) |
| **P15-34** | Calibration-inclusive T15 safe WPM lower end above gaze typing (open gap 132, [details](#p15-34-calibration-inclusive-t15-safe-wpm-lower-end-above-gaze-typing)) | F1 / F2 | P15-29 |
| **P15-37** | Lower-variance calibration for the calibration-inclusive safe WPM (open gap 141, [details](#p15-37-lower-variance-calibration-for-the-calibration-inclusive-safe-wpm)) | F1 / F2 | P15-34 |
| **P15-35** | E1 synthetic-sentence augmentation for the minutes-scale recipe (test C2) (gap 139, done 2026-11-21, [details](#p15-35-e1-synthetic-sentence-augmentation-for-the-minutes-scale-recipe-test-c2)) | F3 | P15-33 |
| **P15-36** | E1 budget-matched recipe so that V1 and H1-H4 are valid (gap 140, done 2026-11-22, [details](#p15-36-e1-budget-matched-recipe-so-that-v1-and-h1-h4-are-valid)) | F3 | P15-33, P15-35 |
| **P15-38** | E1 LM readout with the Willett texts blocked from the LM (gap 143, done 2026-11-20, [details](#p15-38-e1-lm-readout-with-the-willett-texts-blocked-from-the-lm)) | F3 | P15-25 |
| **P15-41** | More seeds of the F-R20 recipe at minutes scale (gap 184, done 2026-11-22, negative result, [details](#p15-41-more-seeds-of-the-f-r20-recipe-at-minutes-scale)) | F3 | P15-36 |
| **P15-42** | Better forced aligners for arms R and S (open gap 185, [details](#p15-42-better-forced-aligners-for-arms-r-and-s)) | F3 | P15-36 |
| **P15-43** | C2 budget range of the F-R20 recipe (open gap 194, [details](#p15-43-c2-budget-range-of-the-f-r20-recipe)) | F3 | P15-41 |
| **P15-44** | `control_flags` label in the P15-41 script (open gap 195, low priority, [details](#p15-44-control_flags-label-in-the-p15-41-script)) | F3 | P15-41 |

#### P15-00 North star and P15 scope
- **Goal:** write down the new direction and plan the first round.
- **Deliverable:** [north star](north-star.md); this section; P15 in diagram 11 and in the tracker; overview, direction decision and README updated.
- **Done when:** the pages exist, the links check passes, and the tracker shows P15.

#### P15-01 E2 CPU pilot: self-improving replay on T12
- **Goal:** show on CPU that the replay simulator, the simulated user and feedback-only adaptation work end to end, while the GPU is busy.
- **Deliverable:** `experiments/2026-11-16-f1-e2-selfimprove-pilot/` with `plan.md` (frozen before runs), simulator code (replay in time order; accept / reject / retype; q_notice for silent errors; p_sloppy), a frozen trunk with a linear day-input layer, a small subset of T12 sessions, and `results.md`.
- **Depends on:** T12 v2 decoder, `fidetype.trust.online_risk` (`aci`), `SessionRiskMonitor`.
- **Done when:** frozen, feedback-only, oracle and self-training arms run on the subset; each session reports PER, commit rate, wrong-commit rate with CP intervals, silent-error rate and labels used; results are compared with the pre-registered criteria.
- **Result (2026-11-16, done):** [results](../../experiments/2026-11-16-f1-e2-selfimprove-pilot/results.md). 8 arms, 16 T12 days, own CPU decoder. S4 pass (feedback-p0.9 PER 0.470 vs frozen 0.686, CI95 of the difference [-0.249, -0.177]); S1-S3 and S6 pass in every guarded arm; S5 FAILS in every arm (uniform null streams commit: no M2-18 evidence gate in the loop); self-training collapses. Bound near vacuous (88-100 % of commits wrong). Main fix for P15-02 / P15-03: evidence gate + per-update null refusal.

#### P15-02 Decoder-update loop and re-calibration hooks
- **Goal:** the trust layer knows when the decoder changes, and a new decoder goes live only after a check.
- **Deliverable:** an update loop in `fidetype` (name to decide): each update gets a new `config_id`; `aci` runs across updates; an e-process monitor per session; a champion / challenger gate (`block_test` / `block_ltt` on recent feedback that the challenger did not train on); the commit gate and the uniform / shuffled null controls run again on every update; the ledger records each update. Hooks in `TrustGuard` / `OnlineTrustPolicy`.
- **Depends on:** P15-01, P14-03, P5-02.
- **Done when:** unit tests show that a worse challenger is refused, a challenger that fails the null controls is refused, and the `config_id` changes on every accepted update. Tests run in CI.
- **Result (2026-11-16, done):** `GuardedUpdateLoop` safe by construction (evidence gate default, null refusal on every update, champion / challenger, chained `config_id`); the three Done-when tests exist and run in CI. [Gated re-run](../../experiments/2026-11-16-f1-e2-selfimprove-pilot/results-gated.md): S5 passes (null commits 2/640 frozen, 0/640 feedback-p0.9; original 281 / 319), S1-S4 pass, but 89-100 % of commits are still wrong and the sign test has no power on top-1 exact loss. Hooks and ledger ([results](../../experiments/2026-11-16-p15-02-hooks/results.md)): `TrustGuardUpdater` swaps a `TrustGuard` config only on an accepted update (`commit_p` raised to the session threshold), `OnlinePolicyUpdater` swaps the `OnlineTrustPolicy` policy and floor; ledger entry kind `update` (proposed / accepted / rejected, hash-linked, `config_id` chain checked by `verify`). T12 replay smoke: 15 proposals, 13 accepted, 2 negative controls rejected with the guard unchanged, ledger verifies. Open for P15-03: a decoder strong enough to test the challenger gate on real data.

#### P15-03 E2 full runs on T12 and T15
- **Goal:** the F1 evidence on real multi-session data.
- **Deliverable:** T12 with 16–20 adapted sessions × 5 arms × 3 simulated-user settings × 2 seeds; then T15 (45 sessions over 20 months). Simulated accept rates calibrated with `t15_personalUse.pkl` (CC0) when it is local. Results page.
- **Depends on:** P15-02; the GPU after M4-13 and P11-01 (about 2026-11-19).
- **Progress (2026-11-18):** CPU part P15-03a done ([results](../../experiments/2026-11-17-p15-03-f1-m4-13/results.md)): champion / challenger replay on T15 with M4-12, M4-13 and a reversed decoder, 4 runs. H1, H4, H5, H6 pass; H2 and H3 fail with the feedback-r0.3 user (see P15-13). The GPU part stays open.
- **Done when:** the pre-registered criteria of the plan are evaluated on both datasets, including the self-training negative control and the silent-error rates. Cost about 3–8 GPU-h for T12.
- **GPU part (2026-11-23):** pre-registered as [P15-49](#p15-49-gpu-part-of-e2-self-teaching-on-t15) (gap 209, pre-registration `29c1dc9`).

#### P15-04 Bandit-feedback online risk control and guarantee statement
- **Goal:** a bound that uses only the feedback that the user actually gives (the truth is seen only for what was shown or corrected).
- **Deliverable:** an online risk-control method for shown-only feedback, based on the published bandit-feedback conformal work (cited, not copied); a written statement of what the guarantee covers and what it does not (silent errors, per-session vs long-run); evaluation on the P15-03 replays.
- **Depends on:** P15-02.
- **Done when:** the method runs on the T12 replay, its long-run wrong-commit rate is reported with intervals next to `aci`, and the scope statement is in the wiki. A proof is optional; if we claim a new theorem, a fresh-agent review checks it.
- **Result (2026-11-16, done):** [results](../../experiments/2026-11-16-p15-04-bandit/results.md), [scope of the guarantee](f1-guarantee-scope.md). New `fidetype.trust.bandit_risk` (`BanditCommitRiskControl`, `BanditTrustPolicy`): (G1) marginal and (G2) precision ACI need only commit labels, so they are valid with shown-only feedback for any sequence; (G3) forced exploration shown as an OFFER (never a commit) + IPW + Bennett / Ville gives an anytime-valid audit of the wrong commits of every grid threshold (design-based, 1 − δ over the coins). No new theorem claimed (standard tools, cited). Pre-registered replay (plan `d90a49b`): T12 long-run wrong-commit 0.0500 [CP95 0.0308, 0.0762] = `aci` (same 35 commits; bound fixed in advance 0.0875), T15 0.0471 [0.0326, 0.0655]; audit violations 0 / 200 seeds; naive shown-only precision estimate optimistic by up to 0.235, IPW within about 1 SE; silent errors (q_notice 0.9) raise the true rate 0.0500 → 0.0550, not covered. Precision target 0.5 not reachable on these decoders (2-7 commits).

#### P15-05 E3: LLM rescoring with a grounding check
- **Goal:** better text from an LLM, with nothing added that the neural evidence does not support.
- **Deliverable:** a local LLM route (llama.cpp or similar; Apache-2.0 or MIT model; 1.7–8B); arms n-gram / LLM rescoring / LLM rewrite limited to the n-best lattice; grounding by CTC forced-alignment log-prob (threshold τ) plus the guard signals; null, frame-shuffled and swapped-signal controls; T15 published logits as the reference decoder. `plan.md` first, then `results.md`.
- **Depends on:** local LLM install (a 1–10 GB download), M4-12 logits, T12 v2.
- **Result (2026-11-16, DONE: T15 + T12):** [results](../../experiments/2026-11-16-f2-e3-llm-grounding/results.md). Qwen2.5-1.5B (CPU), 8 arms. T15 (701 held out): LLM rescoring + grounding (B1) WER 0.3831 vs 0.3985 (CI95 of the difference [-0.0209, -0.0096]); S1-S3 pass, S4 fails (fluent-wrong commits 2 vs 0). T12 (400 held out, replication): B1 WER 0.3851 vs 0.3885 (CI95 [-0.0086, +0.0021]), 15 commits / 8 wrong (0.0200), fluent-wrong 4 vs 4; S1 fails, S2-S4 pass ("safe but no gain"). F2/E3 does not pass. Replicated on both sets: grounding takes swapped-signal commits to 0 in every arm (ungrounded up to 28 / 25), null 0/300; the 95 % coverage τ never changes the top-1 on true signals. Not replicated: the rescoring WER gain. Follow-up P15-06 (T12 needs a loader there).
- **Done when:** WER, sentence accuracy, wrong-commit rate, fluent-wrong rate and null / swapped commits are reported for all arms on T15 and T12, and compared with the pre-registered criteria.

#### P15-06 Risk-controlled hallucination bound
- **Goal:** a stated bound on the rate of committed text that the signal does not support.
- **Deliverable:** CRC / LTT calibration of τ and the commit threshold on a fluent-wrong loss; a guarantee-sheet entry (α, δ, method, items, assumptions), joined to the P14-03 drop-in wrapper.
- **Depends on:** P15-05.
- **Result (2026-11-16, DONE: T15 + T12; done-when NOT met on T12):** [results](../../experiments/2026-11-16-p15-06-halluc-bound/results.md). New `fidetype.trust.halluc_bound` + `calibrate(grounding=, llm=)`: joint LTT of (commit_p, τ_commit, τ_word) on a fluent-wrong loss, word-level forced-alignment check, sheet entry. Guarantee P(fluent-wrong ≤ 0.01 and wrong-commit ≤ 0.05) ≥ 0.9. On 701 held-out T15 trials the bound held in all 10 guards (fluent-wrong 0-0.0029); fluent-wrong commits B 2→0, C 5→1, D 3→1; swapped-signal commits 0 in every arm (also ungrounded: τ_commit = 0 alone stops them). H1-H4 pass for B1, but B1 never commits (utility 0 of 8 right commits): safe but costly. The `most_right` rule keeps 8 B1 commits (1 fluent-wrong). **T12** (400 held out): the bound is not certifiable in any arm: the LTT test half has 180 items, and α = 0.01 at δ = 0.1 needs at least 230 even with zero losses (0.99^180 = 0.164). Every guard falls back to never commit: 0 commits, null 0/300 + 0/300, swapped 0/400 (P15-05 T12: 15-25 commits, 4-7 fluent-wrong). H1 fails on T12. Next levers: more calibration data, α_h ≥ 0.0128, or one LTT half; a per-word commit (P15-05 / P15-06 follow-up).
- **Done when:** on held-out data of two public sets, the fluent-wrong commit rate is at or below α at the stated confidence, and the controls pass.

#### P15-07 Public hallucination benchmark
- **Goal:** a standard way to measure whether a brain-to-text decoder invents text.
- **Deliverable:** tracks for null, scrambled and swapped-signal inputs; the fluent-wrong metric; a scorer; baselines from P15-05 / P15-06. It is a set of tracks in the P6 leaderboard and the P13 hub, not a new leaderboard.
- **Depends on:** P15-05, P6-02.
- **Result (2026-11-16, DONE):** [results](../../experiments/2026-11-16-p15-07-halluc-bench/results.md), [docs](../../docs/hallucination-benchmark.md). New `fidetype.benchmark.hallucination` (protocol `fidetype.halluc/0.1`) + CLI `python -m fidetype.benchmark.hallucination controls | score | rescore`: deterministic null / scrambled / swapped tracks (the P15-05 / P15-06 recipe, seed 0), fluent-wrong metric (optional llama-cpp LLM; deterministic `conservative` fallback), Clopper-Pearson score card; split files with salted hashes only; outcomes with flags only (no text). Baselines on T15 (701) and T12 (400), 3 systems x 2 fluency modes; CI re-scores all 12 committed outcomes files. Null and scrambled: 0/300 everywhere. Swapped: systems without grounding commit as often as on real input (ratio 1.0); P14-03 guard fails on T12 (25/400, 10 leaks). P15-06 guard passes every track but never commits. Fluent-wrong (LLM): T15 P14-03 0, B0 2; T12 P14-03 4, B0 4 (of 8 wrong). Open: show the tracks on the P6 leaderboard / P13 hub; a baseline that commits often and checks the signal.
- **Done when:** the scorer runs in CI on our baselines for at least two datasets, and the track definitions are documented.

#### P15-08 E1: cross-body pretraining on Willett handwriting
- **Goal:** test whether a trunk pretrained on another body signal helps a low-data target more than text-only pretraining.
- **Deliverable:** Willett character CER at 10 / 25 / 50 / 100 % data; arms random / text-only / emg2qwerty (research track) / KT-sEMG (clean track) / optional T15 character head; same character LM; 2 seeds; licence tag on each checkpoint. `plan.md` first.
- **Depends on:** GPU (after P11-01), P11-01 weights for the emg2qwerty arm, CPU caches at a common frame rate.
- **Done when:** all arms run and the rule "an EMG-pretrained arm beats text-only by more than the seed spread at ≤ 25 % data" is evaluated. A null result is a valid outcome. Cost about 20–45 GPU-h.
- **Progress (2026-11-19, `in_progress`):** part 1 **E1a** pre-registered (`60620ab`, [plan](../../experiments/2026-11-19-p15-08-e1-cross-body/plan.md)), code `75c92a6`, GPU run launched 2026-11-19 10:28 (detached, about 10 h). Target Willett handwriting (new sensor + new user); shared output space = the P11-01 98-token character head; arms R random / T text-only (synthetic key renderings, 30,000 steps) / E P11-01 EMG trunk / S shuffled-weight control; labelled budgets 3, 10, 30, 100 min and all (506 min); 2 seeds; final-step test CER on the last block of each session, no LM. Primary H1: E beats T at ≥ 2 of {3, 10, 30} min (seed spread + paired bootstrap); V1 gate, C1 time-shuffle, C2 label-shuffle. Left after E1a: the clean-track KT-sEMG arm (needs a KT-sEMG trunk, P11-06 / gap 86), the optional T15 arm, and the same-LM readout (P15-25, gap 91).
- **Result E1a (2026-11-19, [results](../../experiments/2026-11-19-p15-08-e1-cross-body/results.md)): null for F3 at minutes scale.** V1 pass (E at all 0.395); **H1 fails** (E beats T at 0 of {3, 10, 30} min; at 10 and 30 min T is better, CI95 below 0); H2 and H3 fail; H4 partial (30 min only); C1 pass; **C2 fails** (label-deranged E at 30 min 0.836 vs normal 0.810), so at ≤ 30 min the decoders mostly output the label prior. Mean test CER R / T / E / S: 3 min 0.865 / 0.960 / 0.957 / 0.919; 10 min 1.327 / 0.863 / 0.884 / 0.922; 30 min 0.851 / 0.786 / 0.812 / 1.003; 100 min 0.837 / 0.777 / 0.767 / 0.919; all (506 min) 0.613 / 0.805 / 0.395 / 0.925. Descriptive: at full data the EMG trunk is the best and most stable arm (0.360 / 0.431; R 0.305 / 0.920; T fails at 0.80). One machine-sleep interrupt (S-b30-s0, resume at step 1000) lost or repeated no step. P15-08 stays `in_progress` (KT-sEMG arm); first fix the low-data recipe (P15-33, gap 120). 2026-11-20: P15-33 partial (recipe A: val-C2 pass, test C2 and V1 fail); next P15-35 / P15-36 (gaps 139, 140).
- **Note (2026-11-22, P15-36, results `01ee3b9`):** E1 is now valid under the budget-matched rule (F-R20 at 3 / 10 / 30 min, E1a at 100 min and all): V1 pass, C2 pass on 2 seeds. H1-H4 are each partial (1 win of 3 budgets; H1 wins at 3 min only). P15-08 stays `in_progress` (the KT-sEMG arm is missing).
- **Note (2026-11-22, P15-41, results `02aa679`):** H1 fails on 5 seeds at 10 and 30 min (d = 0.038 [−0.004, 0.081] and −0.002 [−0.034, 0.031]); the 3-min win has no valid control; C2 at 10 min fails on seeds 2-4. So at minutes scale there is no valid evidence that EMG pretraining beats text pretraining. P15-08 stays `in_progress` (the KT-sEMG arm is missing). Follow-up: gap 194 = [P15-43](#p15-43-c2-budget-range-of-the-f-r20-recipe).
- **Note (2026-11-23, P15-43, results `a98964c`):** C2 passes on every seed at none of 3 / 10 / 30 min (100 min not tested). So minutes-scale E1 is "no valid test" with F-R20: the P15-41 30-min null and the 3-min win are both invalid. F3 rests on the full-data result only (E 0.395, V1). P15-08 stays `in_progress` (the KT-sEMG arm is missing). Follow-ups: gaps 197-199 = [P15-45](#p15-45-c2-at-the-full-data-budget-of-e1), [P15-46](#p15-46-stronger-c2-readout-with-repeated-deranged-runs), [P15-47](#p15-47-100-min-c2-with-an-f-r20-recipe).
- **Full-data follow-up (2026-11-23):** [P15-50](#p15-50-f3-at-full-data-with-tuned-arms-and-repeated-deranged-controls) (gap 210, pre-registration `29c1dc9`): tuned R+ / E+ arms, K and I trunk arms, 3 deranged runs per seed.

#### P15-09 New-modality benchmark and reverse transfer
- **Goal:** a public test of "new sensor or new user with minutes of data".
- **Deliverable:** benchmark tracks with fixed data budgets (for example 2, 5, 10 minutes) for a new user and a new modality; the reverse direction E1b (pretrain on Willett + T15, fine-tune on KT-sEMG or one emg2qwerty user); clean and research tracks kept apart.
- **Depends on:** P15-08.
- **Done when:** the tracks and baselines exist, and the confound "cross-person vs cross-modality" is stated next to each result.

#### P15-10 Focused literature check
- **Goal:** make sure that each novelty claim is true before we state it in public.
- **Deliverable:** a wiki page with the exact claim wordings, the searches (Google Scholar, Semantic Scholar, citing papers of NDT3, BrainOmni, CORP, Tang & Huth 2023) and the result per claim; full-text reads of the closest papers.
- **Depends on:** nothing.
- **Done when:** each F1 / F2 / F3 claim is marked "holds", "narrow it" or "drop it", with sources. The README and any post use only claims marked "holds".
- **Result (2026-11-15, done):** [novelty check 2026-11](novelty-check-2026-11.md). F1: narrow it. F2: narrow it. F3: part 1 holds; "transfer to a new modality" drop it as written (CORTEG), keep only "for text". Safe wordings are in the [north star](north-star.md#verdicts-of-the-literature-check-p15-10-2026-11-15).

#### P15-11 Demo shows F1 / F2 progress
- **Goal:** a person sees in 30 seconds that the decoder improves and the guarantee holds.
- **Deliverable:** a view in the P14-06 demo: replayed sessions in time order, error rate going down, the wrong-commit line staying under α, update events (accepted / refused), and LLM suggestions held back when the signal does not support them. The page states that the input is a replay with a simulated user.
- **Depends on:** P15-01 (pilot data) or P15-03, P15-06, P14-06.
- **Done when:** it runs from one command; a headless Edge screenshot shows the view; no overflow at phone width.

#### P15-12 Frontier result write-ups
- **Goal:** credibility: each experiment has a public result that anyone can rerun.
- **Deliverable:** result pages in `experiments/` and the wiki for E2, E3, E1 and their follow-ups, with the plan, the exact config, the controls, a one-command rerun and the limits. Negative results are written up too.
- **Depends on:** P15-01, P15-03, P15-05, P15-08.
- **Done when:** each finished experiment has a result page linked from the [north star](north-star.md) and the [overview](../overview.md). Papers in PUB may cite them later; no paper deadline.
- **Progress (2026-11-18, `in_progress`):** six write-ups exist, linked from the [north star](north-star.md#frontier-result-write-ups-p15-12-2026-11-18) and the [overview](../overview.md): [E2 self-teaching](frontier-e2-self-teaching.md), [F1 online guarantees](frontier-f1-online-guarantees.md), [E3 hallucination](frontier-e3-hallucination.md), [decoder quality](frontier-decoder-quality.md), [safe WPM](frontier-safe-wpm.md), [personalisation and drift](frontier-personalisation-drift.md). Every finished experiment has a page. Left: E1 (P15-08, not run), the P15-03 GPU runs, and the P15-24 verdict (replay running); add them to the pages when they finish.

### Exit criteria (first round)
- E2 (F1) has a pilot and full results on T12 and T15, with the update gate in code (P15-01 … P15-04).
- E3 (F2) has results with a stated hallucination bound and a benchmark track (P15-05 … P15-07).
- E1 (F3) has a result, positive or null, with the text-only control (P15-08), and the new-modality benchmark exists (P15-09).
- Every public novelty claim passed P15-10.
- The demo shows F1 / F2 (P15-11). Each experiment has a write-up (P15-12).

**Effort:** 30–60 agent-days (our estimate); about 30–60 GPU-h in total; user: about 8 h (review of claims, LLM licence choice). **Depends on:** trust layer (P5, P14-03), decoders (M4-12 / M4-13, T12 v2, P11-01), the GPU queue. **Window:** 2026-11-16 → 2027-06-30 for the first round. Later rounds (joint model on one GPU, live user studies) come after it; user studies need ethics approval and volunteers (**externally blocked**).

### Open-gap items (added 2026-11-16)
The user asked that known gaps are fixed later, not forgotten. These items come from agent reports of 2026-11-16. Full list: [open gaps](open-gaps.md). No existing item moved.

#### P15-13 Update gate: PER-based non-inferiority challenger test
- **Gap:** 1 of the [open-gap list](open-gaps.md). Follow-up of P15-02, P15-03.
- **Status:** `done`. Done 2026-11-18 (code + pre-registration `e788029`, [results](../../experiments/2026-11-18-p15-13-gate-fix/results.md)): the default-deny non-inferiority gate (`GuardedUpdateLoop(challenger_test="noninferiority")`, default; unknown truth counts against the challenger; top-1 + CER tie-break; margins 0.1 / 0.1, level 0.05; the sign test stays as an option). Replay of P15-03a on M4-13, both users, 2 seeds: G1-G6 all pass. Broken decoder refused 4 / 4 (48 worse vs 0 better) and 4 / 4 against the weak champion M4-12 (probe W; the old sign test accepted it again with feedback-r0.3: 2 vs 0, p 0.25); worse M4-12 refused in 12 / 12 proposals; better M4-13 accepted 4 / 4 (feedback-r0.3 p 0.038, 0.026); phase-C wrong-commit 0.0082-0.0110 (118 commits); feedback-r0.3 runs now give 28-29 commits (P15-03a: 10-11). Cost: 1 of 8 same-decoder re-calibrations refused (gap 72). Contrast: P15-03a H3 failed. Before: in progress since `e788029`.
- **Depends on:** M4-13 rerun result H3 ([plan](../../experiments/2026-11-17-p15-03-f1-m4-13/plan.md)); P15-02.
- **Source:** Commit `97a2fc4` (trust reruns on M4-13, dry run): the gate accepted the reversed decoder (2 discordant pairs, p 0.25).
- **Done when:** The champion / challenger gate of `GuardedUpdateLoop` (`src/fidetype/trust/adaptive.py`) has a per-item PER (or other continuous loss) non-inferiority test next to the sign test, with a margin fixed in a plan before the runs. A unit test and a replay show that the gate refuses the reversed (broken) decoder of the P15-03a dry run, also when the champion is weak and there are few discordant pairs. The change is decided only after the pre-registered H3 result of the M4-13 rerun is read, and the H3 outcome is quoted in the results.

#### P15-14 Certified hallucination bound on T12 (or proof that none is possible)
- **Gap:** 2 of the [open-gap list](open-gaps.md). Follow-up of P15-06.
- **Status:** `done`. Done 2026-11-18 (pre-registration `97a2fc4`, results `053e329`, [F2 rerun results](../../experiments/2026-11-17-f2-m4-13/results.md), [summary](m4-13-trust-reruns.md)): the pre-registered variant V-single (one fixed-order test on all 360 non-fit T12 items) certifies B1 on T12 v2 at alpha_h 0.01, delta_h 0.1 (0.99^360 = 0.027 <= 0.1); held out (400): fluent-wrong 0.0025, wrong-commit 0.0050, controls 0. V1-V3 pass; V4 fails as written (`config_id` label only; P5-21). Not useful: 3 commits, 1 right. Also filed in the [P15-06 results](../../experiments/2026-11-16-p15-06-halluc-bound/results.md#update-2026-11-18-certified-t12-bound-v-single).
- **Depends on:** M4-13; pre-registered V-single variant ([plan](../../experiments/2026-11-17-f2-m4-13/plan.md)); P15-06.
- **Source:** Commit `958040a` (P15-06 T12: 180 LTT test items < 230 needed at α 0.01, δ 0.1).
- **Done when:** A certified fluent-wrong bound (α, δ stated) exists on held-out T12 data, or a written result shows that no certified bound is possible with the T12 data at the stated α and δ (with the arithmetic). The first try is the pre-registered V-single variant (no ordering split, test on all non-fit items) in the M4-13 rerun queue. The result is filed in the P15-06 results and on this page.

#### P15-15 Hallucination benchmark protocol 0.2: paired swapped / real commit-ratio pass rule
- **Gap:** 4 of the [open-gap list](open-gaps.md). Follow-up of P15-07.
- **Status:** `done` (2026-11-17; pre-registration `4e44c23`, code `40922c5`, [results](../../experiments/2026-11-17-p15-15-halluc-0.2/results.md)). Protocol `fidetype.halluc/0.2`: paired swapped / real test (r 0.5, alpha 0.05, m_min 25), verdict pass / fail / insufficient evidence; 0.1 kept. 10 of 12 committed entries change verdict; no baseline passes. Follow-up: P15-21 (gap 52).
- **Depends on:** P15-07.
- **Source:** Commit `bdefe45` (P15-07 done; fixed rule lets rarely-committing systems pass).
- **Done when:** Protocol `fidetype.halluc/0.2` replaces the fixed 0.05 swapped-commit rule with a pass rule on the swapped / real commit ratio, judged by a paired test on the same items. A system that rarely commits cannot pass only because it rarely commits. The docs, the scorer, the CI re-score of the committed outcomes and the score cards use the new rule; 0.1 results stay readable and are marked as the old protocol.

#### P15-16 Hallucination benchmark baseline that commits often and checks the signal
- **Gap:** 4 of the [open-gap list](open-gaps.md). Follow-up of P15-07.
- **Status:** `todo`.
- **Depends on:** P15-15; M4-13 / P11 decoders; P15-06.
- **Source:** Commit `bdefe45` (P15-07 open point).
- **Done when:** The benchmark has at least one baseline that commits on a useful part of the real-signal items (rate stated in a plan before the run) and also passes the null, scrambled and swapped tracks under the protocol 0.2 rule. If no such baseline exists on current decoders, the result says so and names the decoder it waits for.

#### P15-17 G3 audit: independent proof review and its fixes
- **Gap:** 6 of the [open-gap list](open-gaps.md). Follow-up of P15-04.
- **Status:** `done`. Commits `98daec3` and `2e4e38d` (2026-11-16): all review findings fixed; optional L5 (V uses 1/π) written down as a limit.
- **Partly closed:** Review part done, commit `4cd9cb5`: [G3 audit review](g3-audit-review.md), verdict "sound with fixes" (H1 high: delayed / out-of-order feedback can break the bound; M1 fixed public seed; M2 low-power tests; L1-L5).
- **Depends on:** P15-04.
- **Source:** Commit `4860e51` (P15-04 done; P15-04 done-when asks for a fresh-agent check of any new derivation); review `4cd9cb5`.
- **Done when:** A fresh agent with no context reviews the G3 derivation (forced exploration + IPW + Bennett / Ville audit) in `src/fidetype/trust/bandit_risk.py` against the [scope page](f1-guarantee-scope.md) and the cited papers, and the review is filed in the wiki (done: [G3 audit review](g3-audit-review.md)). The item closes when each issue of that review (H1, M1, M2, L1-L5) is fixed in code, tests or docs, or written as a limit on the scope page and the guarantee sheet. An outside human review, if wanted later, is a separate externally blocked step.

#### P15-18 Pilots store per-item null-control outputs
- **Gap:** 13 of the [open-gap list](open-gaps.md). Follow-up of P15-12.
- **Status:** `todo`.
- **Depends on:** —.
- **Source:** Commit `9cb7a81` (P5-01 replay used conservative proxies from the P15-02 counts).
- **Done when:** Every new pilot and replay stores per-item outputs of its null controls (uniform, shuffled, swapped where used) next to the real-signal outputs, in the local derived-data folder. The pre-registration template or the P15 rules say so, and the next P15 replay (P15-03 or later) does it, so later work does not need proxies.

#### P15-19 Show usefulness on stronger decoders (P5-01, P15-02, P5-02, P15-06)
- **Gap:** 14 of the [open-gap list](open-gaps.md). Follow-up of P5-01, P15-02, P5-02, P15-06.
- **Status:** `in_progress` (2026-11-18). M4-13 evidence ([summary](m4-13-trust-reruns.md)): P5-02 useful at precision 0.5 (104 commits, precision 0.837); P15-02 loop (P15-03a) useful with the oracle user (28-29 phase-C commits, precision 0.89-0.90) but the gate fails with partial feedback (P15-13); P15-06 non-vacuous on T15 (36 commits, 34 right) but costly (24 % of the right commits kept). Still needed: P5-01 on M4-13 and all four on the P11 decoders.
- **Depends on:** M4-13 rerun queue, P11-01.
- **Source:** Commits `9cb7a81`, `4355946`, `3dc84bf`, `958040a` (open points: weak decoder).
- **Done when:** P5-01 (personal trust), P15-02 (update loop), P5-02 (precision and online guards) and P15-06 (hallucination bound) are rerun on the M4-13 decoder and on the P11 decoders. Each rerun reports a useful operating point (commits that are mostly right, with the bound kept) or a stated null result. The current decoders are too weak (top-1 almost never right), so the safety results exist but the usefulness does not.

#### P15-20 Hallucination split halluc-v0.1 (T15): exact trial-index rule
- **Gap:** 34 of the [open-gap list](open-gaps.md) (added 2026-11-17 from the T15 split audit). Follow-up of P15-07.
- **Status:** `done` (2026-11-17). The split file states the rule exactly (`rule`, new fields `id_rule` and `id_sessions`: i = position inside the session's `val_eval` list, HDF5 `val` index = 2i + 1, 3 excluded trials keep their i). `fidetype.benchmark.hallucination.ids_from_rule` rebuilds the 701 ids; `tests/test_halluc_bench.py` checks them against the hashes (and against the local HDF5 file when present). `verify_split` with ids from the rule: no problem. Docs: [hallucination benchmark](../../docs/hallucination-benchmark.md#4-files-and-licences).
- **Depends on:** P15-07 (done).
- **Source:** T15 split audit, 2026-11-17 ([page](t15-split-audit.md)), issue C.
- **Gap detail:** `src/fidetype/benchmark/splits/halluc-v0.1/b2t25-t15-val-eval.json` says "odd-index trials per session (val_eval) ... Trial id = <session>|val|<i>". The 701 ids use `i` = the index inside `val_eval` (checked: 701/701). If someone reads `i` as the index inside the HDF5 `val` file, 358 of the 701 ids point to `val_select` (calibration) trials. The text hashes catch such a rebuild, but the rule text should not allow it.
- **Done when:** The rule text and docs/hallucination-benchmark.md state the index exactly (for example "i = position inside the session's val_eval list; the HDF5 val index is 2i + 1"), or protocol 0.2 uses ids that name the HDF5 file index. The split verify command still passes; a test rebuilds the ids from the rule.

#### P15-21 Hallucination benchmark: absolute bound on unsupported swapped commits next to the ratio rule
- **Gap:** 52 of the [open-gap list](open-gaps.md) (added 2026-11-17 from P15-15). Follow-up of P15-15.
- **Status:** `todo`.
- **Depends on:** P15-15 (done); P15-16 (the hole matters only for a system that commits often).
- **Source:** P15-15 results, 2026-11-17 ([results](../../experiments/2026-11-17-p15-15-halluc-0.2/results.md)).
- **Gap detail:** the 0.2 swapped rule bounds P(swapped commit) / P(real commit) <= 0.5. A system that commits on most real items can pass it with a high absolute rate of unsupported swapped commits. The test also treats the pairs as independent, but the language trial of swapped item j is real item perm[j].
- **Done when:** a pre-registered protocol version adds an absolute upper bound on the unsupported swapped-commit rate next to the ratio rule (or a written result shows why the ratio rule is enough), and a simulation or permutation check shows the pair-independence assumption keeps the error at most alpha on the committed outcome patterns. Old protocol results stay readable.

#### P15-22 LLM rescoring with learned and prefix confidence for safe WPM
- **Gap:** 69 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P14-23). Follow-up of P15-05, P14-23.
- **Status:** `done` (2026-11-19; pre-registration `7557b54`, code `9643804`, [results](../../experiments/2026-11-19-p15-22-llm-learned/results.md)). T15 `val_eval` 701, CPU, cache-only decisions. L1 = B1 + `confidence="learned"`: **4.91 [4.25, 5.57]** safe WPM v0.1, certified, 196 commits / 13 wrong, controls pass. H1 vs P5-23 learned (2.64): +2.27 [1.76, 2.81], **L1 beats**; H2 vs the LLM arm alone L0 (4.18; reproduces P15-05 B1 701 / 701): +0.73 [0.19, 1.27], **L1 beats**. Closes P14-23 (gap 53). L2 prefix (secondary): v0.2 7.14 [6.54, 7.70], with reading cost 6.75 [6.21, 7.26] (P5-24: 4.67). Hallucination protocol 0.2: L0 and L1 pass all tracks (0 swapped commits). Fluent-wrong L1 5 / 701 (L0 6). New gaps 93 = P15-26 (T12 replication), 94 = P15-27 (guard vs pipeline top-1).
- **Depends on:** P5-23; P5-24 for the prefix arm; P14-24 (edit 8); about 3 GB RAM for the LLM (P15-05 peak 2.96 GB). CPU.
- **Source:** P14-23 [analysis](safe-wpm-bottleneck.md) (exploratory): the committed P15-05 arms on M4-13, scored with safe-wpm v0.1, give 4.18 (B1 rescore + G), 4.69 (C1) and 4.77 (D1) against 4.02; not pre-registered for safe WPM, margins inside the usual half-width. LLM-rescored top-1 + a learned score gives 4.50.
- **Done when:** a pre-registered T15 replay reports safe WPM (v0.1 and, if P14-26 is accepted, v0.2) for LLM rescoring with the learned and prefix confidence, with controls, grounding and the fluent-wrong rate, and states whether it is above the no-BCI reference with its interval.

#### P15-23 Update gate refuses a challenger without champion outputs
- **Gap:** 71 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P15-13). Follow-up of P15-13.
- **Status:** `done` (2026-11-18, code `0254ebc`; default deny refuses a challenger without champion outputs; opt-out `allow_missing_champion=True`, recorded; unit tests incl. the update-hooks path and PersonalTrust; CHANGELOG).
- **Depends on:** none (CPU, code).
- **Source:** [P15-13 results](../../experiments/2026-11-18-p15-13-gate-fix/results.md#gap-decisions): when a champion exists but its outputs on the check block are not given, `GuardedUpdateLoop._challenger_test` returns None and the challenger can be accepted on the null controls and the block LTT alone. This contradicts "default deny".
- **Done when:** with the default gate, a challenger whose champion outputs are missing is refused with a clear reason (or needs an explicit, recorded opt-out); `TrustGuardUpdater` and `PersonalTrust` paths still pass; a unit test covers both cases; CHANGELOG notes the change.

#### P15-24 Same-decoder re-calibrations under the default-deny gate
- **Gap:** 72 of the [open-gap list](open-gaps.md) (added 2026-11-18 by P15-13). Follow-up of P15-13, P5-01.
- **Status:** `done` (2026-11-18: same-decoder re-calibration rule + pre-registration `0254ebc`, [results](../../experiments/2026-11-18-p15-24-recal-rule/results.md): R1-R7 pass; re-calibrations refused 0 of 8 (P15-13: 1 of 8); every broken or worse decoder still refused).
- **Depends on:** none (CPU).
- **Source:** [P15-13 results](../../experiments/2026-11-18-p15-13-gate-fix/results.md#descriptive-results) (D2): 1 of 8 re-calibrations of the same M4-13 decoder was refused (s1 oracle B6: top-1 changed on 3 of 48 items, 1 worse vs 2 better, p 0.081). With 48 check items and margin_abs 0.1 the absolute branch allows no worse item. A user whose data drift (P5-01 PersonalTrust) may then not be able to re-tune.
- **Done when:** a pre-registered check (for example the P5-01 replay) measures how often re-calibrations of the same decoder are refused, and a chosen remedy (larger check block, a re-calibration path that keeps the top-1 fixed, or a margin for re-calibrations fixed in a plan) keeps the refusal rate of real re-calibrations low without accepting the P15-13 broken or worse decoders.

#### P15-25 E1 readout with the same character LM
- **Gap:** 91 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P15-08). Follow-up of P15-08.
- **Status:** `done` (2026-11-20; pre-registration `885f9c5`, code `29798a7`, results `44c2d8a`, [results](../../experiments/2026-11-20-p15-25-e1-same-lm/results.md)). F (Tatoeba 6-gram, w 0.5, beta 1, beam 8, fixed in advance) on all 41 E1a runs; C0 exact (greedy edits equal on every sentence). H1 still **fails** (0 / 3; T better than E at 3, 10, 30 min); H2, H3 fail; H4 partial -> fail (30 min: Δ 0.075 < spread 0.077); V1 pass (0.271); C1 pass; C2 fails (0.811 vs 0.887). Full data: E 0.395 -> **0.271**, T 0.805 -> 0.783 (new H5 E beats T at all: pass, robust); R-ball-s0 0.305 -> **0.173**. L1 (LM helps decoders that read the signal) pass. FL (research-only lexicon) gives the same verdicts except H3 partial. F is primary (licence-clean; CER, not guarded commits), FL secondary: a stated deviation from the note below. New gaps 143 = [P15-38](#p15-38-e1-lm-readout-with-the-willett-texts-blocked-from-the-lm), 144 = [P14-48](#p14-48-willett-hw-with-the-same-lm-readout-and-a-no-signal-gate).
- **Depends on:** P15-08 E1a (weights local in `C:/Users/zhang/bci-data/derived/p15-08/runs/`); a licence-clean character LM and CTC beam search (P11-07, gap 87); CPU.
- **Source:** [E1a plan](../../experiments/2026-11-19-p15-08-e1-cross-body/plan.md#deviations-from-the-roadmap-item): the roadmap and the north star ask for "greedy CER and CER with the same character LM" (the same-LM rule), so that a gain cannot come from English character statistics alone. E1a reads out greedy CTC only, because no licence-clean character LM exists yet.
- **Done when:** every E1a arm and budget is re-scored with one character LM and one beam setting (fixed before the re-score), and the H1-H4 rules of the E1a plan are evaluated again on the LM CER next to the greedy CER.
- **Note (2026-11-20, P11-14):** use the P11-07 in-beam decoder FL (w 0.25, beta 1, lam 8, beam 8) for the LM CER, and the P11-14 confidence L-FL if any part commits under a guard: it gives the highest certified EMG value (6.80 [4.49, 9.63] with one calibration draw; 5.00 [0.00, 9.55] once the calibration draw is counted, P11-17). FL uses a research-only lexicon term; decoder F (licence-clean LM only, w 0.5) is the clean alternative (L-F 7.02, not the selected arm). Neither meets the 50 ms CPU budget yet (gaps 122, 125).

#### P15-26 T12 replication of LLM rescoring + learned commit confidence
- **Gap:** 93 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P15-22). Follow-up of P15-22.
- **Status:** `done` (2026-11-19; pre-registration `39e9419`, code `a719794`, `4b7c07c`, `83448eb`, [results](../../experiments/2026-11-19-p15-26-replication/results.md)). T15, four new calibration draws: L1 (B1 + learned) v0.1 5.58, 6.00, 5.23, 5.83 (c1, c2, c3, p1), all certified with the CI lower end above the no-BCI reference; **level and gain replicate (4 / 4 each)**; mean of five T15 values 5.51, SD 0.44 (P15-22 4.91 is the lowest). T12: L1 2.37 [1.34, 3.62] < 4.11: **does not replicate on T12**; H1 vs P5-23 +0.50 [0.05, 1.13], no clear difference; L2 prefix v0.2 + reading cost 4.95 (proposed metric, not decided). Protocol 0.2 passes in every unit. New gap 103 = P15-29.
- **Depends on:** P15-22 (done); the P15-05 T12 caches (`derived/f2-e3-llm-grounding/t12/`); a T12 loader with the word trigram LM (about 2.5-4 GB RAM with the LLM); CPU.
- **Source:** P15-22 ([results](../../experiments/2026-11-19-p15-22-llm-learned/results.md)): the 4.91 safe WPM (v0.1) comes from one participant (T15), one split and one seed. P5-23 replicated on T12 only as "no clear difference".
- **Done when:** a pre-registered T12 replay (fit_a + calibration sessions -> test sessions, as P5-23) reports safe WPM v0.1 (and v0.2) for B1 + learned and B1 + learned prefix against the P5-23 / P5-24 T12 guards, with controls and the hallucination protocol 0.2 check; and a second calibration draw (another seed) on T15 shows how much the 4.91 depends on the split.

#### P15-27 Guard n-best top-1 differs from the pipeline top-1 on 9 of 701 trials
- **Gap:** 94 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P15-22). Follow-up of P15-22, P15-05.
- **Status:** `done` (2026-11-19, code `296fb88`, [P15-22 addendum](../../experiments/2026-11-19-p15-22-llm-learned/results.md#addendum-2026-11-19-p15-27-check-of-the-9-trial-top-1-difference-gap-94); cause: `GroundingCheck.apply` did not re-sort after demotion; fixed with tests; no P15-22 decision or number changes, 4.91 stays; follow-up P15-28).
- **Depends on:** P15-22 (done; per-trial rows in `derived/p15-22/arm-*.json`). CPU, minutes.
- **Source:** P15-22 ([results](../../experiments/2026-11-19-p15-22-llm-learned/results.md)): in every LLM arm the top-1 text of `guard._last_nb` equals the first item of the decode_fn output on 692 of 701 trials. The decisions use the guard's view. The WER of the guard view is 0.1609, of the pipeline view 0.1617 (P15-05).
- **Done when:** a written check names the cause (for example re-sorting after calibration, ties, or candidate merging in the n-best conversion), states whether any committed decision depends on it, and either fixes it with a test or documents it in docs/trust-guarantee.md.


#### P15-28 Recompute the M4-12 and T12 P15-05 / P15-06 / P15-07 WER values with the sorted grounding order
- **Gap:** 97 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P15-27). Follow-up of P15-27, P15-05.
- **Status:** `todo`.
- **Depends on:** P15-27 (done); the local M4-12 and T12 caches of P15-05 / P15-06 / P15-07. CPU, cache-only.
- **Source:** P15-27 ([P15-22 addendum](../../experiments/2026-11-19-p15-22-llm-learned/results.md#addendum-2026-11-19-p15-27-check-of-the-9-trial-top-1-difference-gap-94)): before the fix, `GroundingCheck.apply` left a demoted (ungrounded) candidate first in the list, and the P15-05 family computed the B1 WER from that first item. T15 M4-13 B1: 0.1617 -> 0.1609 (S1 still pass). Decisions never used the unsorted list.
- **Done when:** the B1 (and P15-06 / P15-07 grounded) WER values on M4-12 and T12 are recomputed with the sorted order from the committed caches, each changed value gets a dated note next to the original (no silent overwrite), and the wiki pages that quote them (frontier-decoder-quality, frontier-e3-hallucination, m4-13-trust-reruns, north-star) are updated or confirmed.

#### P15-30 First non-English result: Spanish MEG through the trust layer
- **Gap:** 107 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P14-34, M1.
- **Status:** `todo`.
- **Depends on:** P14-34 (per-language config); SpanishBCBL MEG replay adapter (P4-01, done); a Spanish LM (M1 has a Tatoeba EN/ES character 6-gram, CC BY 2.0 FR); a SpanishBCBL decoder of our own (research-only data, CC BY-NC 4.0).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" SpanishBCBL is Spanish ([SpanishBCBL](../entities/spanishbcbl-dataset.md)). Our M1 MEG decoder ran on it, but no trust result and no safe WPM exist for any non-English data.
- **Done when:** A pre-registered run on SpanishBCBL gives certified safe WPM with the Spanish config, the shuffled and null controls and a Spanish no-BCI reference. The result is labelled research only. A negative result is reported as such.

#### P15-31 Non-Latin scripts: literature and public dataset scan
- **Gap:** 108 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P14-34, P15-10.
- **Status:** `todo`.
- **Depends on:** P14-34 (the audit names the script-dependent parts).
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" Every dataset we use is in the Latin alphabet (English, Spanish). Scripts such as Mandarin (pinyin input or characters), Arabic (right to left, joined letters) and Hindi (Devanagari) change the output unit, the CTC vocabulary size, word segmentation (Mandarin has no spaces) and the LM.
- **Done when:** A wiki question page lists published non-English BCI language decoding work and public datasets (modality, language, script, size, licence), in the format of [public datasets](public-datasets.md). It names the best first non-Latin target and the changes per script (output unit, segmentation, safe-WPM unit, LM). Each claim has a source.

#### P15-32 Multilingual LM grounding for the guard
- **Gap:** 109 of the [open-gap list](open-gaps.md) (added 2026-11-19 from a user question). Follow-up of P15-05, P15-06, P14-34.
- **Status:** `todo`.
- **Depends on:** P14-34; P15-30 (non-English data to test on); a local multilingual LLM with an open licence.
- **Source:** User question (2026-11-19): "is this for every language, all devices, UI, SDK, production integration?" The F2 LLM rescoring and grounding check (P15-05, P15-06, P15-22) use English models and English data only. A rescorer can push text toward a dominant language. The grounding check is not tested for this.
- **Done when:** The P15-05 rescoring and grounding check run with a multilingual LLM on English and Spanish data under one pre-registered plan. The swapped-signal and null controls pass per language. A cross-language control (signal from one language, LM prompt in the other) is reported. The hallucination bound holds per language, or the page says why not.

#### P15-33 E1 low-data recipe that reads the target signal before more source arms
- **Gap:** 120 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P15-08 E1a). Follow-up of P15-08.
- **Status:** `in_progress` (partial, 2026-11-20: val-C2 pass, test C2 and V1 fail; see Result).
- **Depends on:** P15-08 E1a (done part; local weights and cache in `C:/Users/zhang/bci-data/derived/p15-08/`); GPU.
- **Source:** [E1a results](../../experiments/2026-11-19-p15-08-e1-cross-body/results.md): C2 fails (label-deranged E at 30 min 0.836 vs normal 0.810) and the time-shuffled CER equals the normal CER at 30 min for every arm, so with ≤ 100 labelled minutes no arm reads the implant signal with the E1a recipe. Random init is unstable (R-b10-s1 1.839, R-all-s1 0.920). A KT-sEMG arm run with the same recipe would hit the same floor.
- **Done when:** a pre-registered pilot on the val block only (no test) picks a low-data recipe (for example frozen trunk + stem-only or low-LR fine-tuning, longer schedules, Willett-style synthetic sentences) under which at least one arm passes C2 at 30 min; then E1a's H1-H4 are rerun with that recipe (same splits, 2+ seeds) before the KT-sEMG arm.
- **Result (2026-11-20, [results](../../experiments/2026-11-20-p15-33-low-data-recipe/results.md)): partial, gap stays open.** Pre-registration `a2906d8`. Val-only search (recipes A-D x arms R, E, 30 min, seed 0) selected **A** (full fine-tune + strong regularisation and augmentation): arm E val CER 0.769, deranged 0.871 vs needed 0.869 (pass by 0.002); B / C (frozen trunk) and D (low LR) had no eligible arm. Test grid with A: **C2 fails** (deranged E 30 min 0.847 vs needed 0.873; normal 0.773); **V1 fails** (best at all = E 0.713 > 0.50; A over-regularises at full data, R 0.976); so **H1-H4 are inconclusive** (raw wins H1 1, H2 2, H3 1, H4 2). C1 pass. Descriptive: E at 3 / 10 / 30 min 0.858 / 0.780 / 0.766 (E1a 0.957 / 0.884 / 0.812); E time-shuffled at 30 min 0.92 vs 0.77 normal. GPU 8.75 h (≤ 10 h). New gaps 139 = [P15-35](#p15-35-e1-synthetic-sentence-augmentation-for-the-minutes-scale-recipe-test-c2), 140 = [P15-36](#p15-36-e1-budget-matched-recipe-so-that-v1-and-h1-h4-are-valid).

#### P15-34 Calibration-inclusive T15 safe WPM lower end above gaze typing
- **Gap:** 132 of the [open-gap list](open-gaps.md) (added 2026-11-20 after P15-29). Follow-up of P15-29.
- **Status:** `done` (2026-11-20; criterion **not met**; [results](../../experiments/2026-11-20-p15-34-margin-guard/results.md)). **Gap 132 closed 2026-11-21** (orchestrator decision) on the branch "or the numbers say why no such guard exists with the T15 data": P15-34 margin arms and the six guarantee-keeping multi-split rules of P15-37 plus R120 give lower ends of about 2.1-3.2; about 3.8 x more labelled calibration data would be needed. The criterion branch (lower end above 4.0153) was **not met**. The goal continues in gap 160 = [P15-39](#p15-39-labelled-t15-like-calibration-data-for-the-calibration-inclusive-safe-wpm). Primary A1 (alpha 0.05, delta 0.025) gives 4.90 [3.11, 6.44] with 40 / 40 draws certified; the lower end is below 4.0153. A safety margin removes no zero draw here and costs 0.45-0.77 WPM per draw; the between-draw spread grows. The P15-29 settings on 40 new draws give 5.35 [4.05, 6.81] (reference, descriptive). Follow-up: [P15-37](#p15-37-lower-variance-calibration-for-the-calibration-inclusive-safe-wpm) (gap 141).
- **Depends on:** P15-29 (done; `fidetype.benchmark.safe_wpm.calibration_draw_interval`); the P15-22 L1 pipeline (LLM rescoring + learned commit score); CPU.
- **Source:** P15-29 ([results](../../experiments/2026-11-20-p15-29-calibration-ci/results.md)): with 40 calibration draws the T15 L1 safe WPM v0.1 is 5.18 [0.00, 6.99]. 2 of 40 draws are above alpha on the test set and earn 0. Certified draws give 3.50-6.82. Variants that were not pre-registered give lower ends of about 3.6. So the lower end is not above the no-BCI 4.0153.
- **Options:** (1) a larger calibration set, so fewer draws commit too much and the between-draw spread falls; (2) a guard with a safety margin, for example a lower target alpha or a smaller delta, so that fewer draws are above alpha on the test set; (3) both. Choose the option and the rule before any number is computed.
- **Done when:** a pre-registered T15 run with `calibration_draw_interval` (K >= 40, same credit rule as P15-29) reports a calibration-inclusive safe WPM v0.1 interval whose lower end is above 4.0153, with the P15-22 controls passing; or the numbers say why no such guard exists with the T15 data.
- **Note (2026-11-21, P11-17):** EMG now shows the same calibration-variance problem (L-FL 5.00 [0.00, 9.55]; 9 / 40 draws above alpha). The EMG version is gap 159 = [P11-19](#p11-19-lower-variance-emg-l-fl-guard-with-a-calibration-inclusive-lower-end-above-no-bci).

#### P15-35 E1 synthetic-sentence augmentation for the minutes-scale recipe (test C2)
- **Gap:** 139 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P15-33). Follow-up of P15-33.
- **Status:** `done` (2026-11-21). Gap 139 closed. (attempt 1 pre-registration `218d889`, results `6cf8466`; attempt 2 = P15-35b pre-registration `3a95935`, results `e9699a7`, [results](../../experiments/2026-11-21-p15-35b-synthetic-on-top/results.md)): the val-only rule picked F-R20 (forced cut, 20 % of the batch items replaced by synthetic sentences, 4,000 steps, arm E). F-R20 is the only candidate that passes val-C2 with the margin (deranged 0.897 vs needed 0.875). Test C2 passes: deranged 0.877 vs needed 0.847 (normal 0.747). The control A4K (recipe A, 4,000 steps, no synthetic items) has normal val 0.738 but fails val-C2 with the margin (0.859 < 0.868). Seed 1 was skipped by the pre-set GPU-clock rule (6.20 h > 6.0 h). GPU 6.20 h (+ about 0.15 h smoke runs). Evidence 2026-11-22 (P15-36, results `01ee3b9`): the seed-1 F-R20 C2 run passes (deranged 0.870 vs needed 0.803, normal 0.703), so no separate replication gap is needed.
- **History:** P15-35 attempt 1 (2026-11-21, pre-registration `218d889`, results `6cf8466`): no synthetic candidate eligible on val (best E U50 0.813 vs recipe A 0.769), `no_recipe`, no test readout; 1.08 GPU h. Attempt 2 = P15-35b (pre-registration `3a95935`: synthetic sentences on top of recipe A, 4,000 steps, arm E, GPU cap 8.0 h) runs since 2026-11-21. Paused at the user's request at 15:49:08 on 2026-11-21 (`latest.pt` at step 1347 of arm F-R20/E-b30-s0; arm F+100 finished all 4000 steps; 2.54 GPU h so far); exact resume. Resumed at 16:16 on 2026-11-21 after the user allowed the GPU again (exactly at step 1347); at 17:30 arm F+50/E-b30-s0-labelshuf, step 2500 / 4000, 3.78 GPU h.
- **Depends on:** P15-33 (done part; local weights in `C:/Users/zhang/bci-data/derived/p15-33/`); GPU.
- **Source:** P15-33 ([results](../../experiments/2026-11-20-p15-33-low-data-recipe/results.md)): recipe A passed val-C2 by 0.002 only (0.871 vs 0.869); on test the deranged run is 0.847 vs needed 0.873 (normal 0.773), so C2 fails at 30 min.
- **Done when:** a pre-registered val-only pilot adds Willett-style synthetic sentences (character snippets of the budget sentences, cut at character times from a forced alignment of the budget data only, spliced into new sentences) and passes val-C2 with a margin set in advance; then test C2 passes at 30 min for at least one arm.

#### P15-36 E1 budget-matched recipe so that V1 and H1-H4 are valid
- **Gap:** 140 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P15-33). Follow-up of P15-33.
- **Status:** `done` (2026-11-22). Gap 140 closed. (plan `8790238`, code + addendum 1 (file names only) `81ba625`, results `01ee3b9`, [results](../../experiments/2026-11-22-p15-36-budget-matched/results.md)): a val-only rule, fixed before any test number, chose F-R20 at 3 / 10 / 30 min and E1a at 100 min and all (`selection.json` 04:30:59, first new test readout 04:31:13). V1 pass (E at all 0.395). C1 pass. C2 pass on seed 0 (0.877 vs 0.847) and seed 1 (0.870 vs 0.803). H1 (E vs T, primary) partial: a win at 3 min only (0.808 vs 0.888). H2 / H3 / H4 partial: a win at 30 min only. Arm E test CER at 3 / 10 / 30 / 100 min / all: 0.808 / 0.777 / 0.725 / 0.767 / 0.395, the best arm at every budget. Limits: 2 seeds; at 10 and 30 min E beats T by less than the seed spread; the R / S aligners are weak (lag at the 99-frame clip in 6 / 12 libraries); F-R20 not run at 100 min / all. GPU 6.00 h of the 8.0 h cap (launch 1 21:15:16-21:17:05, stopped at step 311 for the user's GPU pause; launch 2 23:15:44-05:13:44, exact resume at step 311). P15-08 stays `in_progress` (KT-sEMG arm).
- **Follow-ups:** gap 184 = [P15-41](#p15-41-more-seeds-of-the-f-r20-recipe-at-minutes-scale) (more seeds); gap 185 = [P15-42](#p15-42-better-forced-aligners-for-arms-r-and-s) (better R / S aligners).
- **Note (2026-11-23, P15-43, results `a98964c`):** the C2 pass at 30 min (seeds 0 and 1) does not hold on seeds 2-4 (deranged 0.849 / 0.889 / 0.860 vs needed 0.865 / 0.922 / 0.871). It was a small-sample pass.
- **Depends on:** P15-33, P15-35 (a minutes-scale recipe that passes test C2); GPU.
- **Source:** P15-33 ([results](../../experiments/2026-11-20-p15-33-low-data-recipe/results.md)): one recipe for all budgets; recipe A (picked for 30 min) over-regularises at 100 min and all (R 0.976, E 0.713 at all), so V1 fails and H1-H4 are inconclusive.
- **Done when:** a pre-registered budget-matched recipe rule (for example the minutes-scale recipe up to 30 min, the E1a recipe at 100 min and all), fixed before any test number, gives V1 pass and test C2 pass; H1-H4 of E1a are then evaluated under it (same splits, 2 seeds).

#### P15-37 Lower-variance calibration for the calibration-inclusive safe WPM
- **Gap:** 141 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P15-34). Follow-up of P15-34 and P15-29.
- **Status:** `done` (2026-11-21; gap 141 closed on the branch "shows with numbers which calibration size would be needed"; method + plan `4e81f16` before any number, code `6de1779`, stage S + addendum `77c3df6` before the main run, results `105c5d0`, [results](../../experiments/2026-11-21-p15-37-multi-split/results.md)). primary BMED-3 (3 splits at delta / 3, median guard; named before the main run) T15 calibration-inclusive safe WPM v0.1 **4.73 [2.60, 6.24]** (K = 40, all certified), below 4.0153: criterion not met. Same 40 draws: A0 (P15-29 settings) 5.26 [2.95, 6.89]; AND-2 4.82 [2.83, 6.29]; AND-3 4.55 [2.75, 5.89]; AND-4 4.37 [2.45, 5.78]; BMAX-2 5.39 [3.20, 6.83] (descriptive); BMAX-3 5.29 [2.10, 6.77] (1 above-alpha draw). R120 (P15-29 + P15-34 A0 + this A0, not blind) 5.26 [2.94, 6.91], 2 / 120 above alpha. Multi-split cuts the between-draw SD only 4-15 % (AND-3 0.78 vs A0 0.92; within-draw 0.34) and costs 0.44-0.89 WPM in the mean for AND / BMED. The P15-34 lower end 4.05 did not replicate (2.95 on the new draws). Projection (pre-registered, rough, assumes 1/sqrt(n)): about **2,760 calibration items** (3.8 x the 722 of `val_select`) are needed; exploratory certified-only SD gives about 1,580. method.md: only AND and Bonferroni + selection keep the LTT guarantee exactly (cross-fitting, jackknife+, CV+, cross-conformal and CRC do not at this size). Library: do not ship a multi-split `calibrate` now.
- **Follow-ups:** gap 160 = [P15-39](#p15-39-labelled-t15-like-calibration-data-for-the-calibration-inclusive-safe-wpm) (labelled T15-like calibration data, externally blocked); gap 161 = [P15-40](#p15-40-check-the-1n-assumption-of-the-calibration-size-projection) (check the 1/sqrt(n) assumption). Gap 159 = [P11-19](#p11-19-lower-variance-emg-l-fl-guard-with-a-calibration-inclusive-lower-end-above-no-bci) gets this result as evidence.
- **Depends on:** P15-29 / P15-34 (done; `calibration_draw_interval`); new labelled data or a calibration-procedure change; CPU.
- **Source:** P15-34 ([results](../../experiments/2026-11-20-p15-34-margin-guard/results.md)): on T15 the between-draw SD of the safe WPM (0.63-0.91) is 2-3 times the within-draw SD (0.34). A safety margin lowers every draw and widens the spread (A1 4.90 [3.11, 6.44]). The lower end of the P15-29 settings depends on the draw set: 0.00 in P15-29 (2 / 40 above-alpha draws), 4.05 on 40 new draws (none).
- **Options:** (1) more labelled calibration data that is not in `val_eval` (more T15-like sessions, other participants, other datasets); (2) a calibration procedure with lower variance, for example cross-fitting so that more of the 722 items take part in certification, with a proof that the guarantee still holds; (3) a pre-registered larger K (80 or more) for the P15-29 settings, so that the interval does not depend on one or two rare draws. Choose before any number is computed.
- **Done when:** a pre-registered run shows a calibration-inclusive T15 lower end above 4.0153 with the P15-29 credit rule, or shows with numbers which calibration size would be needed.
- **Note (2026-11-21, P11-17):** EMG shows the same calibration-variance problem (between-draw SD 2.94 vs within-draw 1.19). Gap 159 = [P11-19](#p11-19-lower-variance-emg-l-fl-guard-with-a-calibration-inclusive-lower-end-above-no-bci) applies this item's method to EMG L-FL when the result is in.

#### P15-39 Labelled T15-like calibration data for the calibration-inclusive safe WPM
- **Gap:** 160 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P15-37). Follow-up of P15-37, P15-34. Continues the goal of gaps 132 and 141 (closed).
- **Status:** `externally_blocked` (needs new labelled data).
- **Depends on:** about 1,600-2,800 labelled T15-like trials outside `val_eval`, or another participant or dataset with the same task; the P15-22 L1 pipeline; `calibration_draw_interval`; CPU.
- **Source:** P15-37 ([results](../../experiments/2026-11-21-p15-37-multi-split/results.md)): with the 722 `val_select` items no guarantee-keeping guard lifts the T15 calibration-inclusive lower end above 4.0153 (primary BMED-3 4.73 [2.60, 6.24]; R120 5.26 [2.94, 6.91]). The pre-registered projection needs about 2,760 calibration items (3.8 x 722); the exploratory certified-only figure is about 1,580.
- **Done when:** a pre-registered calibration-inclusive run on that data (P15-29 credit rule, K stated in advance) reports a lower end above 4.0153, or numbers say why not. The run also tests the projection.
- **Evidence (2026-11-21, P15-40, results `23ae9bd`):** the 1/sqrt(n) check gives b_D2 = 0.48 [0.12, 0.83] and a revised n* about 2,520 [1,080, 460,000] (P15-37: 2,764). A tighter exponent needs new data, so that part folds into this item.
- **Route (2026-11-23):** [P15-48](#p15-48-t15-calibration-hold-out-retrain) (gap 208) makes the labelled calibration data ourselves: it holds out 2,216 training trials by sentence group (pre-registration `29c1dc9`).

#### P15-40 Check the 1/n assumption of the calibration-size projection
- **Gap:** 161 of the [open-gap list](open-gaps.md) (added 2026-11-21 by P15-37). Follow-up of P15-37.
- **Status:** `done` (2026-11-21; plan `f83397a`, code and plan addendum `1d64217`, results `23ae9bd`, [results](../../experiments/2026-11-21-p15-40-sqrt-n-check/results.md)). Gap 161 closed. D2 between-draw SDs 1.234 / 1.089 / 0.884 at n = 361 / 481 / 722. Fitted exponent b_D2 = 0.48 [0.12, 0.83], consistent with 1/sqrt(n). Revised n* about 2,520 [1,080, 460,000] (P15-37: 2,764). D1 b = 0.75 gives n*_A about 1,770. The mean is not fixed below 722 (4.64 / 4.70 / 5.19). The design effect is not confirmed on certified-only draws. The P15-37 decision stands. A tighter exponent needs new data, so it folds into gap 160 (P15-39).
- **Depends on:** P15-37 (done; `experiments/2026-11-21-p15-37-multi-split/run.py`); CPU.
- **Source:** P15-37 ([results](../../experiments/2026-11-21-p15-37-multi-split/results.md)): the projection n* about 2,760 assumes that the between-draw SD falls as 1/sqrt(n) and that the mean and the within-draw SD stay fixed. Both assumptions are unverified.
- **Done when:** sub-sampling `val_select` (n = 361 / 481 / 722) on CPU reports the between-draw SD at each n, the fitted exponent and the revised n*.

#### P15-38 E1 LM readout with the Willett texts blocked from the LM
- **Gap:** 143 of the [open-gap list](open-gaps.md) (added 2026-11-20 by P15-25). Follow-up of P15-25.
- **Status:** `done` (2026-11-20; pre-registration and code `1dd2a1a`, results `fe3e564`, [results](../../experiments/2026-11-20-p15-38-e1-lm-willett-blocked/results.md)). Done 2026-11-20: the Tatoeba 6-gram rebuilt with all 907 Willett texts blocked (LM0 recipe check exact; LMa / LMb 0). F re-score of the 41 E1a runs: no verdict changes (H1 fail, H4 fail, H5 pass robust, V1 pass 0.273); max per-run CER change 0.0015; E full data 0.271 -> 0.273, R-ball-s0 0.1734 -> 0.1743. emg2qwerty: no Willett text overlaps; the P11-11 LM already blocks the EMG test texts, so no EMG re-measure. The `willett-hw` readout with this LM is gap 146 = [P14-50](#p14-50-willett-blocked-tatoeba-lm-as-the-willett-hw-lm-readout).
- **Depends on:** P15-25 (done; log-probs local in `C:/Users/zhang/bci-data/derived/p15-25/lp/`); the P11-11 LM build rule (`stage_lm`); CPU.
- **Source:** P15-25 ([results](../../experiments/2026-11-20-p15-25-e1-same-lm/results.md)): 13 of 80 Willett test sentences (5 of 47 unique texts), 9 of 106 val and 97 of 781 pool sentences occur in the Tatoeba English export. The P11-11 LM blocked only emg2qwerty texts. The arm comparison is fair (same LM for all), but the absolute LM CER can be optimistic.
- **Done when:** the Tatoeba 6-gram is rebuilt with every Willett sentence blocked (exact and containment, the P11-11 rule), the 41 E1a runs are re-scored with decoder F, and the change of each H verdict and of the full-data E / R CER is reported.

#### P15-41 More seeds of the F-R20 recipe at minutes scale
- **Gap:** 184 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P15-36). Follow-up of P15-36, P15-08.
- **Status:** `done` (2026-11-22; negative result). Gap 184 closed. (plan `043486f` 09:31:48, code `8f70f1e` 09:34:55, results `02aa679` 21:43:59, [results](../../experiments/2026-11-22-p15-41-more-seeds/results.md)): seeds 2-4 of F-R20 (arms E and T) at 3 / 10 / 30 min, pooled with seeds 0-1 of P15-36. H1 fails on 5 seeds (paired t): E vs T at 10 min d = 0.038 [−0.004, 0.081], at 30 min −0.002 [−0.034, 0.031]. The 3-min win (0.095 [0.066, 0.124], 5 / 5 seeds) has no valid control. C2 (arm E, 10 min, deranged labels) fails on seeds 2, 3 and 4 (seed 4: deranged 0.787 = normal 0.789), so H1 is flagged invalid and minutes-scale H1 is "not supported". H2-H4 were left out by the plan (R / S cost) and move to gap 185 (P15-42). GPU 7.82 h of the 8.0 h cap, one launch 09:35:12-17:24:15. P15-08 stays `in_progress`.
- **Follow-ups:** gap 194 = [P15-43](#p15-43-c2-budget-range-of-the-f-r20-recipe) (C2 budget range); gap 195 = [P15-44](#p15-44-control_flags-label-in-the-p15-41-script) (`control_flags` label, low priority); H2-H4 go to gap 185 = [P15-42](#p15-42-better-forced-aligners-for-arms-r-and-s).
- **Depends on:** P15-36 (done; local weights in `C:/Users/zhang/bci-data/derived/p15-36/`); GPU.
- **Source:** P15-36 (2026-11-22, results `01ee3b9`, [results](../../experiments/2026-11-22-p15-36-budget-matched/results.md)): H1 wins at 3 min only. At 10 and 30 min E beats T on average (0.777 vs 0.783, 0.725 vs 0.743), but by less than the seed spread (0.042, 0.044). Two seeds give a weak spread estimate.
- **Done when:** a pre-registered run with 3-5 seeds of F-R20 at 3 / 10 / 30 min (arms R, T, E, S) re-evaluates H1-H4 with the E1a rule; optionally F-R20 at 100 min checks the recipe boundary.

#### P15-42 Better forced aligners for arms R and S
- **Gap:** 185 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P15-36). Follow-up of P15-36, P15-35.
- **Status:** `todo`.
- **Depends on:** P15-36 (done); GPU.
- **Source:** P15-36 (2026-11-22, results `01ee3b9`, [results](../../experiments/2026-11-22-p15-36-budget-matched/results.md)): the forced-aligner lag hit the 99-frame clip in 6 of 12 R / S libraries, so for R and S the synthetic sentences may be close to noise. H2-H4 win only at 30 min, where R and S are poor and unstable.
- **Done when:** a pre-registered rule gives R and S usable aligners (lag inside the clip in every library), or uses the uniform cut for weak aligners, and H2-H4 are re-checked under it.

#### P15-43 C2 budget range of the F-R20 recipe
- **Gap:** 194 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P15-41). Follow-up of P15-41, P15-36.
- **Status:** `done` (2026-11-23; negative result, outcome C). Gap 194 closed. (plan `bd673ae`, code `6235d69`, results `a98964c`, [results](../../experiments/2026-11-23-p15-43-c2-30min/results.md)): C2 (arm E, deranged labels) passes on every seed at none of {3, 10, 30} min. 30 min fails on seeds 2-4 (deranged 0.849 / 0.889 / 0.860; needed 0.865 / 0.922 / 0.871); seeds 0 and 1 still pass. 3 min: seed 0 passes (+0.017), seed 1 fails (−0.066); the stop rule skipped seeds 2-4. 10 min failed already (P15-41). 100 min was not tested (no F-R20 100-min recipe), and we do not claim that it fails. So minutes-scale E1 is "no valid test" with F-R20: the P15-41 30-min null and the 3-min win are both invalid. F3 rests on the full-data result only (E 0.395, V1). GPU 2.22 h, one launch 2026-11-22 22:13:42 to 2026-11-23 00:26:40. P15-08 stays `in_progress`.
- **Follow-ups:** gap 197 = [P15-45](#p15-45-c2-at-the-full-data-budget-of-e1) (C2 at full data); gap 198 = [P15-46](#p15-46-stronger-c2-readout-with-repeated-deranged-runs) (stronger C2 readout); gap 199 = [P15-47](#p15-47-100-min-c2-with-an-f-r20-recipe) (100-min C2, low priority).
- **Serves:** research labs.
- **Depends on:** P15-41 (done; local weights and libraries); GPU.
- **Source:** P15-41 (2026-11-22, results `02aa679`, [results](../../experiments/2026-11-22-p15-41-more-seeds/results.md)): C2 (arm E, deranged labels) at 10 min fails on seeds 2, 3 and 4 (seed 4: deranged 0.787 = normal 0.789). P15-36 checked C2 at 30 min on seeds 0 and 1 only (pass). No new seed has a 30-min C2, and no seed has a 3-min C2.
- **Done when:** a pre-registered run reports C2 at 30 min for seeds 2-4 and the smallest budget in {3, 10, 30, 100} min where C2 passes on all 5 seeds (or that none does). E1 arm comparisons then use only budgets where C2 passes on every seed.

#### P15-44 control_flags label in the P15-41 script
- **Gap:** 195 of the [open-gap list](open-gaps.md) (added 2026-11-22 by P15-41). Follow-up of P15-41.
- **Status:** `in_progress` (2026-11-24; one code-fix agent runs gaps 200, 202, 205, 195 and 213; nothing committed yet). Low priority.
- **Serves:** research labs.
- **Depends on:** P15-41 (done); CPU. Low priority.
- **Source:** P15-41 (2026-11-22, results `02aa679`, [results](../../experiments/2026-11-22-p15-41-more-seeds/results.md)): in `experiments/2026-11-22-p15-41-more-seeds/p41.py` the `control_flags` strings read "C2 done on seed k" (the run status). `C2.<k>.pass` = false is the correct value.
- **Done when:** `control_flags` shows pass or fail for each control and seed, a test covers it, and the committed `summary.json` is regenerated from the stored numbers (no rerun) or carries a note.

#### P15-45 C2 at the full-data budget of E1
- **Gap:** 197 of the [open-gap list](open-gaps.md) (added 2026-11-23 by P15-43). Follow-up of P15-43, P15-36.
- **Status:** `done` (2026-11-23, results `273fba2`, [results](../../experiments/2026-11-23-p15-45-c2-full-data/results.md); pre-registration `20f9f5b`, code `d4f5990`). Gap 197 closed. **Outcome A:** C2 passes on all 5 seeds at the full-data budget (E1a recipe, budget all, arm E). Deranged test CER 0.979 / 0.866 / 0.953 / 0.896 / 0.876 vs needed 0.750; normal 0.360 / 0.431 / 0.329 / 0.420 / 0.366; min margin +0.116. Arm E 5-seed mean 0.381. C1 passes on the new seeds. 2.52 GPU h. The run used the E1a recipe, not F-R20 (the plan states this). The north-star F3 row now states that the full-data result has a valid label-deranged control.
- **Serves:** research labs.
- **Depends on:** P15-43 (done); the E1a full-data recipe (or F-R20 at the full budget); GPU, long (estimate the cost in the plan). Medium priority.
- **Source:** P15-43 (2026-11-23, results `a98964c`, [results](../../experiments/2026-11-23-p15-43-c2-30min/results.md)): C2 fails at 3, 10 and 30 min on at least one seed, so F3 rests on the full-data result only (E 0.395, V1). That result has no label-deranged control on more than one budget-matched seed set.
- **Done when:** a pre-registered run (GPU cost estimated in the plan) reports C2 (arm E, deranged labels; rule: deranged test CER >= max(0.75, normal + 0.10)) at the full-data budget on at least 3 seeds, with normal and deranged runs on the same seeds and pass or fail per seed. The F3 row of the north star then states whether the full-data result has a valid control.

#### P15-46 Stronger C2 readout with repeated deranged runs
- **Gap:** 198 of the [open-gap list](open-gaps.md) (added 2026-11-23 by P15-43). Follow-up of P15-43.
- **Status:** `todo`. Medium priority.
- **Serves:** research labs.
- **Depends on:** P15-43 (done; local per-sentence outputs in `C:/Users/zhang/bci-data/derived/p15-43/`); GPU for the extra deranged runs; CPU for the bootstrap. Medium priority.
- **Source:** P15-43 (2026-11-23, results `a98964c`, [results](../../experiments/2026-11-23-p15-43-c2-30min/results.md)): the C2 margins are near the threshold on every seed (fails −0.011 to −0.033; passes +0.030 and +0.067). One deranged run per seed cannot separate a true gap of about 0.08-0.10 from a gap of 0.10 or more.
- **Done when:** a pre-registered C2 rule uses several deranged runs per seed (the number fixed in the plan) and a paired sentence bootstrap CI of the deranged − normal test CER gap, with a pass rule stated before any number. It is applied to at least one E1 budget and reports pass or fail per seed with the CI. Later E1 checks use this rule.
- **Full-data follow-up (2026-11-23):** [P15-50](#p15-50-f3-at-full-data-with-tuned-arms-and-repeated-deranged-controls) (gap 210, pre-registration `29c1dc9`): tuned R+ / E+ arms, K and I trunk arms, 3 deranged runs per seed.

#### P15-47 100-min C2 with an F-R20 recipe
- **Gap:** 199 of the [open-gap list](open-gaps.md) (added 2026-11-23 by P15-43). Follow-up of P15-43, P15-36.
- **Status:** `todo`. Low priority.
- **Serves:** research labs.
- **Depends on:** P15-43 (done); a new, pre-registered F-R20 recipe choice at 100 min; about 12 GPU h. Low priority.
- **Source:** P15-43 (2026-11-23, results `a98964c`, [results](../../experiments/2026-11-23-p15-43-c2-30min/results.md)): 100 min was not tested, because no F-R20 100-min recipe exists. E1a already reported C2 failing at <= 100 min with its own recipe. Gaps 197 and 198 give more information per GPU hour.
- **Done when:** a pre-registered F-R20 recipe at 100 min reports C2 on all 5 seeds (pass or fail per seed), or numbers say why not (for example the GPU cost). The result says whether 100 min is the smallest budget where C2 passes on every seed.
- **Full-data follow-up (2026-11-23):** [P15-50](#p15-50-f3-at-full-data-with-tuned-arms-and-repeated-deranged-controls) (gap 210, pre-registration `29c1dc9`): tuned R+ / E+ arms, K and I trunk arms, 3 deranged runs per seed.

#### P15-48 T15 calibration hold-out retrain
- **Gap:** 208 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the frontier plan). Follow-up of P15-39, P15-37.
- **Status:** `todo`.
- **Serves:** research labs.
- **Depends on:** pre-registration `29c1dc9`; a free GPU (local, or rented once the user approves); CPU for the hold-out rule.
- **Source:** frontier plan (user "go", 2026-11-23), direction 2. Pre-registration `29c1dc9` ([plan](../../experiments/2026-11-23-t15-calibration-holdout/plan.md); `holdout.py` + 7 CPU tests): 2,216 trials held out by sentence group; calibration pool 2,688; safe-WPM v0.2 with K = 120; pass = lower end > 4.0153. It is the route for gap 160 = P15-39 with our own hold-out (no new outside data).
- **Done when:** the pre-registered run reports the calibration-inclusive safe-WPM v0.2 interval (K = 120) and whether its lower end is above 4.0153, or numbers say why not.

#### P15-49 GPU part of E2 self-teaching on T15
- **Gap:** 209 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the frontier plan). Follow-up of P15-03.
- **Status:** `todo`.
- **Serves:** research labs.
- **Depends on:** pre-registration `29c1dc9`; the run wrapper (gap 212 = P15-52); GPU (local or rented).
- **Source:** frontier plan (user "go", 2026-11-23), direction 1. Pre-registration `29c1dc9` ([plan](../../experiments/2026-11-23-e2-self-teaching-t15/plan.md)): T15, then T12 as stage 2; primary P1: FB-F WER change <= -0.02 on 2 / 2 seeds; the bound must hold through every accepted update. It is the open GPU part of P15-03.
- **Done when:** the pre-registered criteria are evaluated on T15 (and on T12 at stage 2), with the self-training and shuffled-label controls, and the wrong-commit bound is reported for every accepted update.

#### P15-50 F3 at full data with tuned arms and repeated deranged controls
- **Gap:** 210 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the frontier plan). Follow-up of P15-08, P15-45, P15-46, P15-47.
- **Status:** `in_progress` (GPU job since 2026-11-23 21:03:50; wrapper `88a3ab8`, no result; stage-1 recipe selection `3bb55f0`, val only, before any stage-2 test number). Stage 1 picked R+: lr 5e-4, 6000 steps (mean val CER 0.171); E+: lr 1e-3, 6000 steps (mean val CER 0.120). Several R cells were excluded by the pre-registered > 0.90 rule. At 2026-11-24 08:50 the T15 trunk pretraining (arm I) was at step 10,000 / 30,000; 11.7 GPU h used. Not done.
- **Serves:** research labs.
- **Depends on:** pre-registration `29c1dc9`; the run wrapper (gap 212 = P15-52); the local GPU after P15-45; the K arm needs P11-06 (gap 86).
- **Source:** frontier plan (user "go", 2026-11-23), direction 3. Pre-registration `29c1dc9` ([plan](../../experiments/2026-11-23-f3-full-data-controls/plan.md)): tuned R+ / E+ arms (same val-only rule), K (KT-sEMG trunk) and I (T15 trunk) arms, 3 deranged runs per seed. It applies the repeated-deranged rule of P15-46 (gap 198). The packaged `willett-hw` decoder is R seed 0 (CER 0.305), so "E beats R" at full data may only show an unstable R recipe.
- **Done when:** the pre-registered run reports H1-H4 (E+ vs R+, E+ vs T, K vs R+, I vs R+) per seed with the repeated deranged controls, and the F3 row of the north star states the result.

#### P15-51 GPU rental kit
- **Status:** `done` (2026-11-23, commit `aa91210`). Tooling only: no rental, no spend. `tools/rental/`: README with a step-by-step machine choice, CUDA setup script, a one-hour speed test of the T15 recipe (it imports the trainer unchanged and projects the GPU hours of the P15-48 hold-out retrain and the P15-49 E2 replay), an upload list with licences, and a ROCm-to-CUDA change list; 8 CPU tests.
- **User step:** the one-hour speed test on a rented machine needs the user's approval of a rental (not started).
- **Serves:** the project (GPU capacity for P15-48, P15-49).
- **Open:** gap 213 = [P2-17](#p2-17-lf-line-endings-for-shell-scripts) (LF rule for `*.sh`).

#### P15-52 Run wrappers for E2 and F3
- **Gap:** 212 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the frontier plan). Follow-up of P15-49, P15-50.
- **Status:** `in_progress` (2026-11-24). F3 part: wrapper `88a3ab8` (code + CPU tests, no result); it runs as the P15-50 GPU job. E2 part: an agent writes the wrapper now. The gap stays open for the E2 part.
- **Serves:** research labs.
- **Depends on:** pre-registration `29c1dc9`; CPU (a short GPU smoke into a scratch folder only).
- **Source:** plan agent report (2026-11-23, commits `29c1dc9`, `aa91210`): the E2 and F3 plans are committed, but their run wrappers are not written yet.
- **Done when:** each wrapper exists, calls the frozen trainers unchanged, has CPU tests, and passes a dry run (no result files), before any GPU launch.

## P16. Write side: emotion and memory (exploration) (added 2026-11-15, later)
**Goal:** find out, with evidence, whether a BCI can stimulate or replicate emotion or memory, and what part of that Fidetype could do safely. All Fidetype work so far is **read side** (signal → text). P16 looks at the **write side** (stimulation → brain state).

**User idea (2026-11-15, their words):** "after this is all done, i want to explore if we can stimulate emotion or replicate emotion through bci, or do some research on it, somewhere on the road map, like replicating memory or emotion ... this is my vague idea".

**Position:** P16 is a **later** phase. It starts after the P15 core work (E2, E3, E1 and their write-ups). No existing item moves, changes its ID or changes its priority. The scope is exploration: no item promises a result.

**Rules:**
- No stimulation of any person in this project without clinical partners, ethics approval and approved hardware (P16-05, **externally blocked**). The user owns ethics and partners.
- The user has no MEG or EEG hardware. P16-01 … P16-04 use public papers, public datasets and simulation only.
- Datasets: licence check first. Commit aggregate results only. Never commit raw recordings or participant data.
- P16-03 (ethics and safety) comes before the design study P16-04 is final, and before any outreach about P16-05.
- No medical claims. The pages describe research, not treatment.

### Deliverables
| ID | Item | Depends on | Status |
|---|---|---|---|
| **P16-01** | Literature review of write-side BCI for mood and memory | P15 core work | todo |
| **P16-02** | Read-side affect decoding on public datasets, with calibrated abstention | P16-01 (scope), trust layer (P14-03) | todo |
| **P16-03** | Ethics and safety page for write-side BCI | P16-01 | todo |
| **P16-04** | Design study: closed loop "detect state → stimulate → verify" (offline / simulation only) | P16-01, P16-02, P16-03 | todo |
| **P16-05** | Any real stimulation work | P16-03, P16-04, partners, ethics approval, hardware | **externally blocked** |
| **P16-06** | Beyond words: affect and memory-state decoding with the trust layer's signal checks (added 2026-11-23, user request) | research scope (agent runs 2026-11-23), P16-02, trust layer | todo |
| **P16-07** | Beyond words: image reconstruction decoding with signal checks (added 2026-11-23, user request) | P16-06 | todo |

#### P15-29 Safe WPM interval that includes the calibration draw
- **Gap:** 103 of the [open-gap list](open-gaps.md) (added 2026-11-19 by P15-26). Follow-up of P15-26.
- **Status:** `done` (2026-11-20; pre-registration `d7169cf`, code `8180a30`, results `c61d215`, [results](../../experiments/2026-11-20-p15-29-calibration-ci/results.md)). The method is a two-level bootstrap over 40 T15 calibration draws × 2,000 trial resamples (`safe_wpm.calibration_draw_interval`, docs/safe-wpm.md section 6b, PROPOSED reporting addition). Restated T15 headline: L1 v0.1 **5.18 [0.00, 6.99]**. The lower end is not above the no-BCI 4.0153: "above, but inside the combined interval". 2 / 40 draws are above alpha on the test set; the certified draws are 3.50-6.82. T12: 1.05 [0.00, 3.18], not above 4.11. Until the user adopts 6b, a leaderboard entry reports the conditional trial-bootstrap `ci`.
- **Depends on:** P15-26 (done; five T15 calibration draws with per-trial decisions in `derived/p15-26/`). CPU.
- **Source:** P15-26 ([results](../../experiments/2026-11-19-p15-26-replication/results.md)): the L1 safe WPM over five T15 calibration draws has SD 0.44 (4.91-6.00); the reported trial-bootstrap CI (half-width about 0.66) is conditional on one calibration. The P15-26 verdict stage also read a null CI from the `safe_wpm` block (reporting only; the write-up uses the paired-bootstrap interval).
- **Done when:** a documented method (for example a bootstrap over calibration redraws, or a cross-fit of calibration and evaluation) gives safe WPM entries an interval that includes the calibration draw; `docs/safe-wpm.md` says which interval a leaderboard entry reports; the P15-22 / P15-26 T15 headline is restated with it.

#### P16-01 Literature review: write-side BCI for mood and memory
- **Serves:** the project (decision input); research labs.
- **Goal:** know what works, what does not work and what is unknown before we plan anything.
- **Deliverable:** a wiki question page. Topics: closed-loop deep brain stimulation (DBS) for mood (for example Scangos et al. 2021, *Nature Medicine*); hippocampal memory prostheses (Berger, Hampson); closed-loop stimulation for memory (Kahana); the DARPA RAM programme; affective BCI (emotion decoding and neurofeedback). For each line of work: the method, the evidence level (number of participants, controls, replication), and a verdict "works / does not work / unknown". Sources get source pages as usual.
- **Depends on:** the P15 core work (time order only).
- **Done when:** the page exists with citations for each verdict, the links check passes, and the page names the open questions that P16-02 … P16-04 address.

#### P16-02 Read-side affect decoding on public datasets
- **Serves:** research labs; the project (first step toward any closed loop).
- **Goal:** measure how well we can **detect** an affective state from public EEG data. A closed loop cannot stimulate well if it cannot detect the state first.
- **Deliverable:** an experiment with `plan.md` (frozen before runs) and `results.md`. Candidate datasets: DEAP, SEED, DREAMER and others. This wiki has **not verified** their licences and access terms: the licence check comes first, before any download. Aggregate results only. The decoder uses the trust layer: it gives a label only when it is confident, and abstains otherwise, with a stated error bound (the same calibrated abstention as the text decoders, [P14-03](#p14-03-trust-layer-as-a-drop-in-wrapper)).
- **Depends on:** P16-01 (scope), trust layer (P5, P14-03).
- **Done when:** the licence check is in `references/README.md`; accuracy, abstention rate and the wrong-label rate with intervals are reported on at least one public dataset, with a cross-subject split and null controls; the limits (labels are self-reports, lab stimuli) are stated.

#### P16-03 Ethics and safety page for write-side BCI
- **Serves:** the project; any future partner.
- **Goal:** write down the risks before any design is final.
- **Deliverable:** a wiki page on consent (and consent that changes over time), identity and agency (a changed mood can change the person who consents), mood manipulation and coercion, dual use (for example interrogation or advertising), data protection for neural data, and the legal status of stimulation devices. It states the conditions under which P16-05 may start.
- **Depends on:** P16-01.
- **Done when:** the page exists, cites its sources, and P16-04 links to it.

#### P16-04 Design study: closed loop "detect state → stimulate → verify"
- **Serves:** research labs; the project (decision input for P16-05).
- **Goal:** describe what a closed-loop system needs, and how Fidetype guarantees could apply to stimulation decisions.
- **Deliverable:** a wiki page and a draw.io diagram. Parts: state detection (P16-02), the stimulation decision, the verification of the effect, and the safety limits. Analysis: how the trust layer maps to "stimulate / do not stimulate" (a commit gate with a bound on wrong stimulation decisions, abstention as the default, null controls, a ledger of each decision). Offline and simulation only: no device, no person.
- **Depends on:** P16-01, P16-02, P16-03.
- **Done when:** the page and the diagram exist; the page states which guarantees carry over, which do not, and what evidence a real study would need.

#### P16-05 Real stimulation work
- **Goal:** test a write-side idea in a real study, if P16-01 … P16-04 show that it is worth it and safe.
- **Deliverable:** none in this project alone. It needs clinical partners, ethics approval and approved hardware.
- **Depends on:** P16-03, P16-04; partners, ethics approval, hardware (the user owns these).
- **Done when:** a partner study exists with ethics approval. **`externally_blocked`**; it never counts as late.

#### P16-06 Beyond words: affect and memory-state decoding with signal checks
- **Gap:** 206 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the user request "beyond words"). Follow-up of P16-01, P16-02.
- **Status:** `in_progress` (2026-11-24). The beyond-words research agent scoped gaps 206 and 207 (report to the orchestrator; no wiki page committed yet).
- **Serves:** research labs.
- **Depends on:** the research scope (a research agent runs 2026-11-23); public datasets (licence check first); trust layer (P5, P14-03).
- **Source:** user request 2026-11-23: decode more than words (emotion / affect, memory state, images), and the user wants to build it. The existing P16 phase (emotion and memory) covers the write side and one read-side affect item (P16-02). A research agent scopes the track now.
- **Done when:** a wiki page scopes the track: public datasets with licences, tasks, and which trust-layer signal checks and null controls carry over. At least one pre-registered read-side run on a public dataset (affect or memory state) reports accuracy, abstention rate and wrong-label rate with intervals, and null controls (uniform, shuffled signal).

#### P16-07 Image reconstruction decoding with signal checks
- **Gap:** 207 of the [open-gap list](open-gaps.md) (added 2026-11-23 by the user request "beyond words"). Follow-up of P16-06.
- **Status:** `in_progress` (2026-11-24). An agent prepares the A1 EEG image check on CPU (nothing committed yet). The GPU check waits for a free GPU and a user choice.
- **Serves:** research labs.
- **Depends on:** P16-06 (scope); public datasets (licence check first); GPU (cost in the plan).
- **Source:** user request 2026-11-23 ("beyond words", images). No roadmap item covered image decoding before.
- **Done when:** the P16-06 page names public image datasets (with licences) and methods. A pre-registered run reports reconstruction quality against null controls (shuffled signal) and states when the system must abstain; or numbers say why it is not feasible now (for example hardware or GPU cost).

**Note (2026-11-23):** the user wants to build the "beyond words" read side (P16-06, P16-07). The P16 window (2027-07) and the rule "starts after the P15 core work" were set on 2026-11-15; any change of the order is a separate decision. No existing item moved.

### Exit criteria
- The literature review gives a verdict for each line of work (P16-01).
- One public affect dataset has a result with calibrated abstention (P16-02).
- The ethics and safety page exists (P16-03).
- The design study states what carries over from Fidetype to stimulation decisions (P16-04).
- P16-05 stays externally blocked until partners and ethics approval exist.

**Effort:** 10–20 agent-days (our estimate); user: about 6 h (review of the ethics page; decisions on partners). **Depends on:** the P15 core work; trust layer (P5, P14-03). **Window:** 2027-07-01 → 2027-12-31 for P16-01 … P16-04. P16-05 has no date.

## P17. Daily use: product, people and privacy (added 2026-11-20, after the roadmap)
**Goal:** turn the toolkit into a product that real people use every day, collect our own data under ethics approval, keep learning private, and find a clinical and regulatory path.

**Source:** user approval (2026-11-20) of the orchestrator's post-roadmap list ("P17+"). P17 and P18 come **after** the current roadmap (P1–P16). No existing item moves, changes its ID or changes its priority. P17 and P18 build on existing items and do not repeat them: P14-35 (typing UI), P14-37 (installer), P14-36 (usability study), P12 (intent and control profiles), P13 (benchmark hub), P15-30 … P15-32 (first non-English work), P5-04 (privacy) and P5-05 (on-device trust core) stay where they are.

**Rules:**
- The product never commits a word that the guard does not commit. The no-false-words guarantee is the product contract.
- Work with people (volunteers, users, patients) waits for ethics approval. Those items are **`externally_blocked`**. The user owns ethics boards, volunteers, partners and legal review.
- Publishing (a public service, a dataset, an app store entry) is the user's action. Agents prepare; the user publishes.
- Never commit raw recordings or participant data. Commit aggregate results only.
- No medical claims before P17-10 says which claims are allowed.

### Deliverables
| ID | Item | Depends on | Status |
|---|---|---|---|
| **P17-00** | Roadmap scope: add P17 and P18 | — | done |
| **P17-01** | Daily-use AAC app on the trust guard (installable, end-to-end UX) | P14-35, P14-37, P14-09, P14-03, P14-04, P5-05 | todo |
| **P17-02** | Multi-week home use of the app with real users | P17-01, P17-04 | **externally blocked** |
| **P17-03** | Own data-collection protocol, consent form and data plan | P5-04, P14-36, P18-01 | todo |
| **P17-04** | Ethics approval for our own data collection | P17-03, an ethics board | **externally blocked** |
| **P17-05** | Volunteer recordings under our protocol; consented public dataset | P17-04, P18-03 or P4-06 | **externally blocked** |
| **P17-06** | On-device learning: the F1 loop runs on the user's device | P15-02, P15-03, P15-13, P15-23, P15-24, P5-05 | todo |
| **P17-07** | Federated and self-supervised adaptation from daily use | P17-06, P18-04 | todo |
| **P17-08** | Hosted hub and leaderboard service: build and staging (not published) | P13-03, P13-08, P13-10, P6-03 | todo |
| **P17-09** | Hosted hub launch (user-owned) | P17-08, accounts and domain | **externally blocked** |
| **P17-10** | Regulatory map for a daily-use AAC BCI (desk study) | P17-01 (scope) | todo |
| **P17-11** | Clinical study or regulatory filing | P17-10, P17-04, partners, legal review | **externally blocked** |

#### P17-00 Roadmap scope: add P17 and P18
- **Status:** `done` (2026-11-20).
- **Done when:** P17 and P18 exist in the tracker, on this page and in diagram 11.

#### P17-01 Daily-use AAC app on the trust guard
- **Serves:** people who cannot speak or type easily; AAC developers.
- **Goal:** one installable app that joins live decode, the trust guard, an AAC-style screen, correction and settings. Today these parts exist as separate tools (P14-04, P14-03, P14-35, P14-37).
- **Depends on:** P14-35 (typing UI), P14-37 (installer), P14-09 (AAC integration), P14-03 (drop-in guard), P14-04 (live decode), P5-05 (on-device trust core).
- **Done when:** one installer per desktop OS (Windows, macOS, Linux) runs a full session from a replayed public recording and from an LSL source: decode → guard → COMMIT / OFFER / WITHHOLD shown → user correction logged. An end-to-end test runs in CI. A scripted accessibility check (keyboard-only use, screen-reader labels, switch access) passes. A test shows that no withheld text reaches the output.

#### P17-02 Multi-week home use of the app with real users
- **Goal:** measure daily use, not lab use.
- **Depends on:** P17-01, P17-04 (ethics approval); volunteers.
- **Done when:** at least 5 users use the app for at least 2 weeks each, with consent. A results page reports safe WPM, the measured wrong-commit rate against the bound, and use time per user (aggregates only). **`externally_blocked`** (ethics approval, volunteers).

#### P17-03 Own data-collection protocol, consent form and data plan
- **Goal:** be ready to record our own data the day ethics approval and a device exist.
- **Deliverable:** a protocol (tasks, device, session length, NTS format), a consent form (with withdrawal and data deletion), and a data management plan (de-identification, storage, access, licence of any release).
- **Depends on:** P5-04 (consent records, erasure), P14-36 (usability study plan), P18-01 (device).
- **Done when:** the three documents are in the repo; a fresh-agent review against a checklist (Declaration of Helsinki items, GDPR and neural-data law points) finds no open item; the package is ready to send to an ethics board.

#### P17-04 Ethics approval for our own data collection
- **Depends on:** P17-03; an ethics board (IRB or equivalent).
- **Done when:** an approval exists and its protocol number is recorded (no personal data in the repo). **`externally_blocked`** (the user owns this step).

#### P17-05 Volunteer recordings under our protocol
- **Goal:** data that we control, for gaps that public data does not fill (daily-use EMG, more languages).
- **Depends on:** P17-04; a working device (P18-03 or P4-06).
- **Done when:** at least 10 consented volunteers are recorded under the approved protocol. If the consent allows a release, a de-identified dataset with a data card and licence is ready, and the user publishes it. **`externally_blocked`** (ethics approval, volunteers, hardware).

#### P17-06 On-device learning
- **Goal:** the F1 self-improving loop runs on the user's device. Raw signals and text never leave the device. Only the update gate decides if a new decoder goes live.
- **Depends on:** P15-02, P15-03 (F1 loop and runs), P15-13, P15-23, P15-24 (update gate), P5-05 (on-device trust core).
- **Done when:** the app adapts on a laptop CPU from replayed public sessions (T12, T15 or EMG) with network access blocked in the test; the update gate and the wrong-commit bound hold as in P15-03; the adaptation cost per session is reported against a stated budget (our target: 10 CPU minutes).

#### P17-07 Federated and self-supervised adaptation from daily use
- **Goal:** find out if many users can improve a shared decoder without sharing raw data, and if unlabelled daily-use signal helps.
- **Depends on:** P17-06, P18-04.
- **Done when:** a pre-registered simulation on at least 2 public datasets compares local-only, federated (secure aggregation or differential privacy) and self-supervised arms. It reports CER and the guarantee per simulated user, a privacy budget (epsilon) or the reason none applies, and passing null controls.

#### P17-08 Hosted hub and leaderboard service: build and staging
- **Goal:** the P13 hub runs as a service, not only as a local build.
- **Depends on:** P13-03 (submission by pull request), P13-08 (project site), P13-10 (replay command), P6-03 (static leaderboard).
- **Done when:** one command deploys the hub to a local container; a staging dry run scores a sample submission end to end; a run book and a cost estimate are in `docs/`. Nothing is published.

#### P17-09 Hosted hub launch
- **Depends on:** P17-08; accounts, domain and hosting (user-owned).
- **Done when:** the user makes the service public and the first outside submission is scored (see P6-04). **`externally_blocked`** (the user publishes).

#### P17-10 Regulatory map for a daily-use AAC BCI
- **Goal:** know which rules apply before any clinical claim.
- **Deliverable:** a wiki question page: medical-device rules (for example FDA, EU MDR) and neural-data laws, per jurisdiction; wellness versus medical claims; the evidence a filing needs.
- **Depends on:** P17-01 (product scope).
- **Done when:** the page has a table per jurisdiction with citations, lists the claims we may and may not make, and marks legal review as user-owned.

#### P17-11 Clinical study or regulatory filing
- **Depends on:** P17-10, P17-04; clinical partners; legal review.
- **Done when:** a partner clinical study is registered, or a regulatory filing is made. **`externally_blocked`**; it never counts as late.

### Exit criteria
- The app installs on three desktop OSs and runs end to end with the guard (P17-01).
- On-device learning keeps the bound with no network (P17-06).
- The federated / self-supervised simulation has a pre-registered result (P17-07).
- The hosted hub runs in staging (P17-08).
- The protocol package and the regulatory map exist (P17-03, P17-10).
- P17-02, P17-04, P17-05, P17-09 and P17-11 stay externally blocked until outside people act.

**Effort:** 40–70 agent-days (our estimate); user: ethics, volunteers, partners, legal review, publishing. **Window:** 2028-01-01 → 2028-12-31 for the agent items. The externally blocked items have no date.

## P18. Reach: hardware, models, languages, outputs, standards (added 2026-11-20, after the roadmap)
**Goal:** widen the north star: more body signals (our own open EMG band), one model across bodies, more languages, outputs beyond text, and a formal standard. Every new output keeps the same no-false-words guarantee.

**Rules:** the same as P17. Hardware purchase and fabrication are user-owned. A standards body needs outside sponsors.

### Deliverables
| ID | Item | Depends on | Status |
|---|---|---|---|
| **P18-01** | Open low-cost EMG wristband reference design | P4-05, P4-10, P15-08 | todo |
| **P18-02** | Wristband driver and adapter (NTS over LSL) | P18-01, P4-02, P4-15 | todo |
| **P18-03** | Build and bench-test wristband prototypes | P18-01, P18-02, hardware purchase | **externally blocked** |
| **P18-04** | Cross-body foundation model pre-trained on public data | P15-08, P15-09, P15-25, P15-33 | todo |
| **P18-05** | Multilingual decoding beyond en / es (zh and others) | P15-30, P15-31, P15-32, P14-38, P14-39, P14-40 | todo |
| **P18-06** | Commands and cursor under a no-false-action guarantee | P12-02, P12-03, P12-06, P13-04 | todo |
| **P18-07** | Speech synthesis output under the guard | P12-04, P17-01, P14-03 | todo |
| **P18-08** | Standards submission package for NTS | P1 (1.0 Stable), P7-02, P9-01, P9-03 | todo |
| **P18-09** | Standards body work item | P18-08, outside sponsors | **externally blocked** |

#### P18-01 Open low-cost EMG wristband reference design
- **Goal:** a wristband that anyone can build, so EMG typing does not depend on one vendor.
- **Deliverable:** schematic, PCB layout, bill of materials and firmware under an open hardware licence (for example CERN-OHL-S).
- **Depends on:** P4-05 (EMG band adapters), P4-10 (onset detector), P15-08 (channel and sample-rate needs).
- **Done when:** KiCad files, a bill of materials with a total under a stated target (our target: US$150), and firmware that streams at least 8 channels at at least 1 kHz over BLE or USB are in the repo; ERC and DRC checks pass in CI; the licence is recorded.

#### P18-02 Wristband driver and adapter
- **Depends on:** P18-01, P4-02 (LSL / BrainFlow), P4-15 (device matrix).
- **Done when:** the driver emits NTS over LSL and passes the conformance kit against a firmware simulator (no hardware); replay and synthetic tests run in CI; the device appears in the device support matrix.

#### P18-03 Build and bench-test wristband prototypes
- **Depends on:** P18-01, P18-02; parts and fabrication (user-owned).
- **Done when:** at least 2 units are built; noise floor, signal-to-noise ratio and battery life are measured; the P14-07 live demo runs on the band. **`externally_blocked`** (hardware purchase).

#### P18-04 Cross-body foundation model
- **Goal:** one model, pre-trained on public EMG, handwriting, speech-BCI and EEG data, that a new user or a new body signal can fine-tune with minutes of data (F3 at scale).
- **Depends on:** P15-08 (E1a), P15-09 (new-modality benchmark), P15-25, P15-33 (low-data recipe).
- **Done when:** a pre-registered evaluation on the P15-09 benchmark shows that the model beats a per-modality baseline with the same labelled minutes on at least 3 of 4 modalities, with shuffled and label-deranged controls passing; the weights from licence-clean data are listed with their licences.

#### P18-05 Multilingual decoding beyond en / es
- **Goal:** decode Mandarin Chinese and at least one more language with another script, end to end, with a per-language guard.
- **Depends on:** P15-30 (Spanish), P15-31 (non-Latin scan), P15-32 (multilingual LM grounding), P14-38, P14-39, P14-40 (language hooks, WPM without spaces, per-language registry); `fidetype.lang` and [`docs/language-support.md`](../../docs/language-support.md).
- **Done when:** `zh` in `fidetype.lang` moves from stub to supported; one public non-Latin dataset runs through decoder and guard with a per-language wrong-commit bound and safe WPM (character-based for `zh`); `docs/language-support.md` reports the results. If no public dataset exists, the page says so and the item waits for P17-05.

#### P18-06 Commands and cursor under a no-false-action guarantee
- **Goal:** carry the guarantee from text to actions: a bound on wrong actions, with abstention as the default.
- **Depends on:** P12-02 (discrete intent), P12-03 (continuous control), P12-06 (dataset survey), P13-04 (intent tracks).
- **Done when:** on at least one public cursor or click dataset, a calibrated guard keeps the wrong-action rate at or below the stated alpha, with an interval and null controls; the result is an intent track in the hub.

#### P18-07 Speech synthesis output under the guard
- **Goal:** speak the user's words aloud, but only words the guard commits.
- **Depends on:** P12-04 (decoded-speech profile), P17-01 (app), P14-03 (guard).
- **Done when:** the app speaks only COMMIT decisions, and an OFFER only after the user confirms it; a test over the replay suite finds 0 spoken withheld items; the latency from commit to audio start is reported.

#### P18-08 Standards submission package for NTS
- **Goal:** prepare NeuralTextStream for a formal standards body (for example IEEE SA, ISO/IEC JTC 1, or a W3C or Linux Foundation group).
- **Depends on:** P1 (1.0 Stable), P7-02 (conformance levels), P9-01 (licence and patents), P9-03 (neutral home).
- **Done when:** a wiki page compares the candidate bodies and names one, with its process; the package (spec text in that body's template, conformance kit, implementer list, IPR statement) is in the repo and ready for the user.

#### P18-09 Standards body work item
- **Depends on:** P18-08; outside sponsors and members.
- **Done when:** the body accepts a work item (a PAR or equivalent). **`externally_blocked`**; it never counts as late.

### Exit criteria
- The wristband design and driver pass their CI checks (P18-01, P18-02).
- The foundation model has a pre-registered result (P18-04).
- One non-Latin language runs end to end with a per-language bound (P18-05).
- Actions and speech output keep the guarantee (P18-06, P18-07).
- The standards package is ready (P18-08).
- P18-03 and P18-09 stay externally blocked until outside people act.

**Effort:** 60–100 agent-days (our estimate); user: hardware, sponsors, publishing. **Window:** 2028-01-01 → 2029-06-30 for the agent items. The externally blocked items have no date.

## Sequencing
| Window | First (critical path) | In parallel |
|---|---|---|
| 2026-11-16 → 12-31 | P6 leaderboard; P1 proto + semconv registry; P4 replay adapters (B2T '25, KT-sEMG, Willett) | P9 licence + DCO; P11 decoders; P5 conformal risk control |
| 2027-01 → 02 | P2 Python, TS, Rust 1.0-rc; P1 1.0 RC | P3 collector skeleton; P8 quickstarts; P10 step 2 (Paper 1) |
| 2027-03 → 06 | P3 collector + OS exporter; P8 three-device demo; P7 conformance kit | P2 C core (after 1.0), C#, Kotlin; P4 LSL, BrainFlow, MNE, toolkits; P10 steps 3–4 (user) |
| 2027-07 → 12 | P5 product grade; P7 certification list | P10 steps 5–6; P11 papers; 1.0 Stable when outside reviewers exist; P12 intent profiles and P13 benchmark hub (added 2026-11-11, after the text work) |
| 2028 → 2029-06 (added 2026-11-20) | P17-01 daily-use app; P17-06 on-device learning; P18-04 foundation model | P17-03 protocol, P17-08 hub staging, P17-10 regulatory map; P18-01 / P18-02 wristband; P18-05 languages; P18-06 / P18-07 outputs; P18-08 standards package; externally blocked: P17-02, P17-04, P17-05, P17-09, P17-11, P18-03, P18-09 |

Rules:
- **Replay before hardware.** Every adapter has a replay test before anyone buys a device.
- **Schema before SDKs.** No SDK starts before the proto files exist; the SDKs generate code from them.
- **Demo + benchmark before outreach.** The user posts nothing before step 1 of P10 works.
- **One heavy GPU job at a time** (HANDOFF load limits). Spec, SDK and doc work is CPU-light and runs beside it.

## Risks
| Risk | Effect | Mitigation |
|---|---|---|
| **No adoption** | A spec that only we use is not a standard | Make emitting NTS cheap (10-line recipe); bridge LSL, BIDS, EMMA, HID; benchmark draws submissions; measure adopters, not stars |
| **A big company defines its own format** (for example, a device maker or an OS vendor) | We become a rival format | Bridge to it; never fight; offer NTS as the upstream format with confidence ([spec 9](../../spec/neuraltextstream-v0.1.md#9-relation-to-other-standards)) |
| **Licences** (NC data; unlicensed or copyleft code; vendor SDK terms) | Product weights or code get contaminated | Provenance ledger; own code only; process-separated adapters for copyleft; terms recorded before code |
| **Hardware access** | Real-device adapters stay untested | Dataset replay; BrainFlow synthetic board; loans or purchases (user-owned) |
| **Regulation** (neural-data laws; medical-device rules if we claim patient use) | Legal exposure; blocked pilots | Privacy by default; no medical claims; legal review before pilots (**user-owned**) |
| **Review bandwidth** (agents write 10× more code than one person can read) | Hidden bugs | Machine-checkable exit criteria; conformance kit; CI on every SDK; fresh-agent reviews |
| **Scope creep** | Nothing reaches 1.0 | Critical path above; SDKs 4–6 only after Python, TypeScript and Rust pass the kit |
| **Benchmark disputes** | Credibility loss | Exact configs; required controls; invite reruns ([playbook risks](open-source-playbook.md#risks)) |

## What the user owns
These steps need the user or outside people. They are tracked as `externally_blocked` and never count as late:
- Posting in communities; contacting labs, maintainers and companies.
- arXiv endorsement; peer review.
- Registry accounts and publish tokens (PyPI, crates.io, npm, NuGet, Maven, vcpkg/Conan).
- Hardware purchase or loans; vendor developer agreements.
- Ethics approval, volunteers, user studies.
- Legal review (neural-data laws, licences, patents, trademark).
- Foundation application; a second maintainer.

## Related pages
- [Project plan](project-plan.md) (v0.1: M0–M7)
- [Open-source playbook](open-source-playbook.md) (stages 0–5)
- [Architecture](architecture.md)
- [Direction decision](direction-decision.md)
- [Public datasets](public-datasets.md)
- [Neural input landscape 2026](../sources/neural-input-landscape-2026.md)
- [OpenTelemetry case study](../sources/case-study-opentelemetry.md)
- [LangChain case study](../sources/case-study-langchain.md) (the reason for P14: useful first)
- [Spec v0.1](../../spec/neuraltextstream-v0.1.md)
- [North star](north-star.md) (the reason for P15: frontier first)
- [Open gaps](open-gaps.md) (2026-11-16: known gaps registered as items)
- [Progress dashboard](../progress/index.html) (milestones P1–P18)
- [Apple BCI HID](../entities/apple-bci-hid.md)
- [Diagrams](../diagrams/index.html) (diagram 11: long-term roadmap)
