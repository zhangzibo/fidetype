---
title: Long-term roadmap — Fidetype as a full neural input standard
type: question
tags: [planning, roadmap, standard, spec, sdk, collector, adapters, benchmark, conformance, governance, adoption]
sources: [case-study-opentelemetry, case-study-langchain, case-study-sglang, neural-input-landscape-2026, brain2qwerty-code]
updated: 2026-11-10
---

# Long-term roadmap: Fidetype as a full neural input standard

**Question asked (2026-11-10):** The user decided that Fidetype aims for **full standardisation at OpenTelemetry scale**, and that we build all of it ourselves. Claude subagents write the code and the docs. The user does the outward-facing actions. The current milestones M1–M7 (due 2026-11-15) are only **v0.1**. What comes after v0.1?

**Diagram:** `11-roadmap-standard` on [the diagram page](../diagrams/index.html#s11).

**Context:** [project plan](project-plan.md) (M0–M7 = v0.1), [open-source playbook](open-source-playbook.md) (stages 0–5), [architecture](architecture.md), [direction decision](direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level), [spec v0.1](../../spec/neuraltextstream-v0.1.md), [public datasets](public-datasets.md), [progress dashboard](../progress/index.html) (milestones P1–P11).

## Summary
- v0.1 (M0–M7) gives one spec draft, one Python package, one trust core, a first benchmark and first adapters.
- After v0.1, the roadmap has **11 phases (P1–P11)**. Most of them run in parallel.
- The critical path is: **benchmark (P6) + spec 1.0 RC (P1) → Python + C SDKs (P2) → replay adapters (P4) → collector (P3) → "three devices, one stream" demo (P8) → paper and launch (P10)**.
- The gap to an OpenTelemetry-scale project is **not the core**. It is the **SDKs, adapters and integrations** (see [scale reference](#scale-reference)).
- **Dataset replay** lets us test devices we do not own. Real hardware, outreach, partners, ethics, user studies, peer review and arXiv endorsement depend on outside people. They are **`externally_blocked`** or user-owned.

> **Our take:** We can build a complete, tested standard stack without outside help. We cannot make it *a standard* without outside adopters. So the order is: make it real and testable first (P1–P8), then ask people to use it (P10).

## Where v0.1 ends
| v0.1 item (M0–M7) | State on 2026-11-10 | Carried into |
|---|---|---|
| NeuralTextStream spec v0.1 (Development) | Published. Frame core implemented; other event kinds are sketches | P1 |
| `fidetype` Python package (about 11.5k lines) | Decoders, LM, trust core, eval harness, first adapter (B2T '25) | P2, P3, P5 |
| Trust core v0 | Runs on the simulator, real MEG and B2T '25 | P5 |
| Benchmark v0.1 (M5) | Harness exists; leaderboard not yet | P6 |
| Validator; conformance cases C1–C20 | Validator exists; no suite | P7 |
| Adapters (M6) | B2T '25 replay in progress; LSL/BrainFlow not yet | P4 |
| OSS files, FEP template, GOVERNANCE.md | Done (commit 677ba0e) | P9 |
| Paper 1, Paper 2 (M3, M4) | Not written | P10, P11 |

## Scale reference
| Project | Size | How we know |
|---|---|---|
| **Fidetype `src/` today** | about **11.5k** Python lines (11,532 on disk; 10,795 committed) + 3.4k test lines | Counted 2026-11-10 |
| Brain2Qwerty (Meta, `references/repos/brain2qwerty`) | about **5.6k** Python lines (5,555) | Counted 2026-11-10 |
| LangChain | **hundreds of thousands** of lines (rough, not measured) | Rough figure |
| OpenTelemetry (spec + collector + SDKs) | **millions** of lines across **about 10 or more** languages (rough, not measured) | Rough figure |

- Our core is already twice the size of Brain2Qwerty. The core is not the gap.
- OpenTelemetry is large because of **one SDK per language**, a **collector with hundreds of components**, and **instrumentation for many libraries** ([OTel case study](../sources/case-study-opentelemetry.md)).
- Fidetype at spec 1.0 needs the same kind of breadth, but in a field of thousands of researchers, not millions of developers ([playbook, realistic expectations](open-source-playbook.md#realistic-expectations)).

**Our rough size target at spec 1.0** (our estimate, not a commitment):

| Part | Rough lines |
|---|---|
| Spec, schemas, semantic-convention registry, generated docs | 10–20k (mostly generated) |
| SDKs: Python, C core, Rust, TypeScript, C#/Kotlin bindings | 30–60k |
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
| **P10** | Adoption | Users outside the project | 5–10 / 60+ h | P6, P8, Paper 1 | 2027-01-15 → 2027-12-31 (mostly ext. blocked) |
| **P11** | Research track | Better decoders, papers | ongoing | GPU, datasets | 2026-11-16 → 2027-12-31 |

## P1. Spec to 1.0
**Goal:** NeuralTextStream 1.0. Every part has a stability level. A machine-readable schema is the source of truth. The prose spec and the docs are generated from it or checked against it.

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

## P2. Reference SDKs
**Goal:** any decoder or app can emit and read NTS in its own language, with the same behaviour everywhere.

### Deliverables
| SDK | Role | Package | Priority |
|---|---|---|---|
| **Python** (`fidetype`) | First-class. Research, decoders, trust layer, benchmark | PyPI | 1 |
| **C core** (`libnts`, C11) + C++ header wrapper | Devices, firmware, toolkit plugins (BCI2000, OpenViBE), a shared core for other bindings | vcpkg, Conan; nanopb for MCUs | 2 |
| **Rust** (`nts`) | Safe native core; collector components; WASM for the browser | crates.io | 3 |
| **TypeScript/JS** (`@fidetype/nts`) | Web apps, AAC web apps, WebSocket client, browser demo | npm | 3 |
| **C#** | Windows input (Text Services Framework), Unity | NuGet | 4 |
| **Kotlin** | Android input (IME), BLE devices | Maven Central | 4 |

- One **shared conformance suite** (P7) runs in the CI of every SDK.
- Same API shape in each language: `StreamWriter`, `StreamReader`, `validate()`, event types, semconv constants (generated).
- C# and Kotlin may wrap the C core or Rust (choose by a small FEP).

### Exit criteria
- Each SDK passes 100 % of the conformance kit in CI on Linux, Windows and macOS.
- Each SDK is published to its registry with a 0.x version and a compatibility-matrix entry.
- Python and C reach **1.0** with spec 1.0 RC.

**Effort:** 40–70 agent-days (about 6–12 per language). User: registry accounts and publish tokens (**user-owned**). **Depends on:** P1 schema (generated code).

## P3. Collector (pipeline)
**Goal:** a vendor-neutral process, like the OpenTelemetry Collector, that takes NTS from any source, applies processors, and sends results to any target. Configuration is a YAML file.

### Deliverables
| Stage | Components |
|---|---|
| **Receivers** | NTS gRPC, WebSocket, LSL, files; device adapters from P4 |
| **Processors** | Trust layer (calibration, conformal sets, decision policy), per-user calibration, LM rescoring, segmenter, **privacy filter** (drop or hash `meta` keys, enforce spec 5.4), rate limiter, provenance stamper |
| **Exporters** | **OS text input**: Windows TSF / IME, Android IME, macOS input method, Linux IBus; Apple BCI HID bridge (spec 6.5); **AAC apps** (WebSocket API for web AAC tools); files (Arrow, JSON Lines); analytics (Parquet, an optional OTLP export of latency metrics) |

- Language: Rust or Python for v1 (decide by FEP; Rust fits a long-running local service).
- A `contrib` folder for third-party components, as in OTel.
- Hard rule: an exporter to an OS input method sends **only committed** decisions. It logs the full NTS next to each output.

### Exit criteria
- One YAML config runs: B2T '25 replay → trust processor → file exporter and WebSocket exporter. End-to-end latency is measured and below 50 ms added (our target).
- At least one OS input exporter types committed text into a text field on Windows.
- Components have unit tests and a pipeline integration test in CI.

**Effort:** 30–50 agent-days; about 8 h user testing on the PC. **Depends on:** P2 (Python and C or Rust), P5 trust API.

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

- Each adapter has a replay test that runs in CI with no hardware.
- Licence rule: before any code, an agent records the licence or terms in the adapter README. Copyleft toolkits get **process-separated** adapters only. We copy no third-party code.

### Exit criteria
- Four replay adapters (two modalities with commercially clean data) emit valid NTS in CI.
- LSL and BrainFlow adapters pass a live test with the BrainFlow synthetic board.
- Each real-device adapter is tested on the device: **externally blocked** (needs hardware; the user has none today).

**Effort:** 30–60 agent-days; user: hardware purchase or loans (**user-owned**). **Depends on:** P1, P2; dataset downloads.

## P5. Trust layer to product grade
**Goal:** the trust layer works for one person, gives stated guarantees, records where each output came from, respects consent, and runs on the device.

### Deliverables
1. **Personalisation:** per-user calibration profiles; online recalibration from user corrections; drift detection.
2. **Safety guarantees:** conformal risk control for a wrong-commit limit (finite-sample, as in M2-13); adaptive conformal for non-exchangeable streams; a written guarantee sheet per policy (what holds, under which assumptions).
3. **Provenance ledger:** an append-only, hash-chained ledger: data → weights → calibration → each committed output. Licence flags (NC data cannot reach product weights; [licence rule](project-plan.md#licence-rule)).
4. **Privacy and consent:** consent records referenced by `consent.ref`; the privacy processor (P3); data minimisation defaults (`data.derived = true`, no raw samples); deletion on request.
5. **Neural-data law review** (information for design, not legal advice):

   | Jurisdiction | Instrument | Status in this wiki |
   |---|---|---|
   | Colorado | HB24-1058 (Aug 2024) | Cited in [landscape](../sources/neural-input-landscape-2026.md) |
   | California | SB 1223 (CCPA regulations from 1 Jan 2026) | Cited in [landscape](../sources/neural-input-landscape-2026.md) |
   | Montana | SB 163 (Oct 2025) | Cited in [landscape](../sources/neural-input-landscape-2026.md) |
   | Connecticut | SB 1295 (Jul 2026) | Cited in [landscape](../sources/neural-input-landscape-2026.md) |
   | Chile | Constitutional "neurorights" protection | **To check** (not verified in this wiki) |
   | EU | GDPR special-category data; AI Act | **To check** |
   | US federal | Proposed neural-data bills | **To check** |

6. **On-device operation:** a quantised trust core in the C/Rust SDK; runs on a phone or a Raspberry-Pi-class board; no network needed.

### Exit criteria
- On B2T '25 and two other replay sets, the wrong-commit rate stays below the set limit at the stated confidence level.
- The ledger reproduces the full lineage of one committed word.
- The trust core runs on-device with less than 20 ms per decision (our target).
- A legal review of the law table: **externally blocked** (needs a lawyer; user-owned).

**Effort:** 30–50 agent-days. **Depends on:** v0.1 trust core, P3 processors, P11 (better decoders make usefulness testable).

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

## P7. Conformance + certification
**Goal:** anyone can prove that an implementation speaks NTS correctly.

### Deliverables
- **Conformance kit:** valid and invalid example files in each wire form (start from cases C1–C20 of [spec 7.1](../../spec/neuraltextstream-v0.1.md#71-conformance-cases)); a test runner CLI (`nts-conform`) for producers, consumers and collector components.
- **Levels:** "NTS Core" (frames), "NTS Full" (all event kinds), "Trust-ready" (score semantics + provenance + timing).
- **"Fidetype-compatible" mark:** self-certification first (a public list with a link to the passing CI run). Trademark use rules.
- Trademark registration of "Fidetype": **user-owned, externally blocked**.

### Exit criteria
- Every SDK and the collector pass the kit in CI.
- The first self-certified implementation outside our repo: **externally blocked**.

**Effort:** 15–25 agent-days. **Depends on:** P1, P2.

## P8. Docs, website, demo
**Goal:** a newcomer gets a valid stream in 10 minutes and sees the value in one demo.

### Deliverables
- Website (GitHub Pages): spec (generated), SDK docs per language, the leaderboard, the FEP index.
- Quickstarts: "emit NTS from your decoder in 10 lines" (Python, C, TS); "add calibrated confidence and abstention"; "replay a public dataset".
- Examples folder: one per adapter.
- **Flagship demo: three devices → the same stream → the same trust layer.** Replay of B2T '25 (implant), KT-sEMG (wrist EMG) and SpanishBCBL (MEG) into one collector; one trust config; one browser UI that shows the committed text, the n-best choices and the abstentions. A recorded video.

### Exit criteria
- A new user (tested by a fresh subagent with no context) reaches a valid stream from the quickstart alone.
- The demo runs from one command on a clean machine.

**Effort:** 15–25 agent-days; user: video voice-over or review (about 10 h). **Depends on:** P2, P3, P4.

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
| 4 | Direct contact with 5–10 groups: dataset labs (UC Davis, Stanford NPTL, Nokia Bell Labs, Toronto; [leads](public-datasets.md#university-labs-leads-only-no-outreach)), LSL maintainers, OpenBCI, AAC developers | **User** sends; agents draft | **externally blocked** |
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
- **Papers:** Paper 1 (calibrated, abstaining brain-to-text across modalities), Paper 2 (causal decoding: latency vs accuracy), a spec / benchmark paper.

### Exit criteria
- On at least one modality, the trust policy beats the no-BCI baseline in eWPM.
- Papers on arXiv; peer review: **externally blocked**.

**Effort:** ongoing; GPU-bound (one heavy job at a time on this PC). **Depends on:** GPU, datasets.

## Sequencing
| Window | First (critical path) | In parallel |
|---|---|---|
| 2026-11-16 → 12-31 | P6 leaderboard; P1 proto + semconv registry; P4 replay adapters (B2T '25, KT-sEMG, Willett) | P9 licence + DCO; P11 decoders; P5 conformal risk control |
| 2027-01 → 02 | P2 Python 1.0-rc + C core; P1 1.0 RC | P3 collector skeleton; P8 quickstarts; P10 step 2 (Paper 1) |
| 2027-03 → 06 | P3 collector + OS exporter; P8 three-device demo; P7 conformance kit | P2 Rust, TS, C#, Kotlin; P4 LSL, BrainFlow, MNE, toolkits; P10 steps 3–4 (user) |
| 2027-07 → 12 | P5 product grade; P7 certification list | P10 steps 5–6; P11 papers; 1.0 Stable when outside reviewers exist |

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
| **Scope creep** | Nothing reaches 1.0 | Critical path above; SDKs 4–6 only after Python and C pass the kit |
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
- [Spec v0.1](../../spec/neuraltextstream-v0.1.md)
- [Progress dashboard](../progress/index.html) (milestones P1–P11)
- [Diagrams](../diagrams/index.html) (diagram 11: long-term roadmap)
