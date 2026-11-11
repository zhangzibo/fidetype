---
title: Open-source growth playbook
type: question
tags: [planning, open-source, growth, governance, standards, open-core, foundation]
sources: [case-study-sglang, case-study-langchain, case-study-opentelemetry]
updated: 2026-11-08
---

# Open-source growth playbook

**Question asked:** How does Fidetype grow as an open-source project, and how does it become the standard for trustworthy neural text entry?

> **Status (2026-11-08):** The user chose the OpenTelemetry-level target on 2026-11-08: Fidetype aims to be the vendor-neutral standard and trust layer for neural input from any modality ([scope decision](direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level)). Cheap actions done 2026-11-08 (commit 677ba0e). Only the GitHub Pages site is still open ([cheap actions](#cheap-actions-now)).

**Diagram:** `10-open-source-path` on [the diagram page](../diagrams/index.html#s10).

**Case studies:** [SGLang](../sources/case-study-sglang.md), [LangChain](../sources/case-study-langchain.md), [OpenTelemetry](../sources/case-study-opentelemetry.md) (with BIDS).

**Context:** [direction decision](direction-decision.md), [architecture](architecture.md) (the open-core split), [project plan](project-plan.md) (milestones M0–M7).

## Thesis
Fidetype combines three models:

| Model | What we copy | What it gives Fidetype |
|---|---|---|
| **OpenTelemetry / BIDS** | A vendor-neutral spec | **The standard.** NeuralTextStream becomes a spec that any decoder emits |
| **SGLang** | A paper + reproducible benchmarks + day-0 support | **Credibility.** Day-0 support for new datasets and decoders |
| **LangChain** | Open core, a paid layer on top | **The company**, later. We avoid LangChain's churn and hidden magic |

## The three projects compared
| | [SGLang](../sources/case-study-sglang.md) | [LangChain](../sources/case-study-langchain.md) | [OpenTelemetry](../sources/case-study-opentelemetry.md) |
|---|---|---|---|
| **Origin** | Research lab (LMSYS / Berkeley / Stanford). A paper (NeurIPS 2024). Filled a gap between vLLM and TensorRT-LLM | A side project, built in about a week. Arrived about 5 weeks before ChatGPT | A merger of two rival standards (OpenTracing + OpenCensus), May 2019 |
| **Growth driver** | Reproducible benchmarks. Day-0 model support (DeepSeek V3/R1) | Integrations first. Speed. The founder's posting on X | Neutrality. Vendors compete on the backend, not on instrumentation |
| **Governance** | CODEOWNERS, weekly meetings, quarterly roadmaps. No documented governance | Company-led | Elected Governance Committee (9 seats, at most 2 per company). Technical Committee, SIGs, OTEPs |
| **Money** | Apache-2.0 under non-profit LMSYS. Spin-out RadixArk sells hosted and RL services | Open core. MIT library free. Paid LangSmith | No company. Vendors earn on their own backends |
| **Foundation** | PyTorch Ecosystem (Mar 2025). No foundation | None | CNCF: Sandbox 2019-05, Incubating 2021-08-26, Graduated 2026-05-21 |
| **Size (2026-11-08)** | 38,583 stars | 149,213 stars | 12,000+ contributors, 2,800+ companies (all time) |

## Stages
Diagram 10 shows these stages from left to right.

### Stage 0: Credibility core (now → Paper 1)
Borrows from: SGLang (paper + benchmarks), OpenTelemetry (spec + stability levels), LangChain (lesson: no churn).
- [ ] Paper 1 with a reproducible benchmark harness ([project plan, M3](project-plan.md#m3-paper-1-calibrated-abstaining-brain-to-text-target-11-11--11-13)).
- [x] NeuralTextStream spec v0.1 as a document, with stability levels. *(done 2026-11-08: [spec/neuraltextstream-v0.1.md](../../spec/neuraltextstream-v0.1.md), commit 677ba0e)*
- [ ] A validator and conformance tests. *(Partly there: `fidetype.streams` already validates streams.)*
- [ ] A small, stable core API with semver from day one.
- [ ] No hidden prompts or magic. Everything is inspectable.
- [x] Apache-2.0 licence. *(done)*

**Exit criteria:** Paper 1 on arXiv. The benchmark reruns from one command. Spec v0.1 published.

### Stage 1: Launch moment (tied to the Paper 1 arXiv release)
Borrows from: SGLang (benchmarks against incumbents), LangChain (recipes, integrations).
- [ ] A public trust leaderboard and benchmark ([project plan, M5](project-plan.md#m5-open-benchmark-v01-target-11-13--11-14)).
- [ ] A "10-line recipe": add calibrated confidence and abstention to your decoder.
- [ ] Adapters for what people already use:
  - [ ] [LSL](../entities/lab-streaming-layer.md)
  - [ ] [BIDS](../entities/bids.md)
  - [ ] Brain2Qwerty-style decoder outputs
  - [ ] Meta's NeuralBench
- [ ] Announcements: X/Bluesky, BCI mailing lists, the BCI Society meeting, NeurIPS/ICLR workshops.

**Exit criteria:** the leaderboard is public. At least one outside decoder runs through the recipe.

### Stage 2: Community engine
Borrows from: SGLang (partner-owned backends, cadence, day-0), LangChain (integrations first).
- [ ] Integrations first. Invite labs to own their adapters (CODEOWNERS, their own CI).
- [ ] Day-0 support for new datasets and papers. Examples: EnglishBCBL when the embargo lifts ([EnglishBCBL](../entities/englishbcbl-dataset.md)), Meta's next paper, OPM datasets ([OPM-MEG](../concepts/opm-meg.md)).
- [ ] A fixed cadence:
  - [ ] a release every 2 weeks, with contributor credit;
  - [ ] a public quarterly roadmap;
  - [ ] office hours.
- [ ] Publish exact benchmark configs. Invite rivals to rerun them.

**Exit criteria:** external contributors on each release. At least one lab owns an adapter.

### Stage 3: Standard
Borrows from: OpenTelemetry (spec repo, proposals, semantic conventions), BIDS (extension proposals, bridges).
- [ ] Move the spec into its own repo.
- [ ] Start "FEPs" (Fidetype Enhancement Proposals).
- [ ] Define semantic conventions (shared field names).
- [ ] Get co-authors for spec v1.0: 2–3 decoder labs or companies, plus 1 clinical/academic group.
- [ ] Build bridges to LSL and BIDS. Possibly write a BIDS extension proposal.
- [ ] Engage [IEEE P2731](../entities/ieee-p2731.md) and IEEE P2794.
- [ ] Rule: never create a rival format where one exists. Bridge, don't fight.

**Exit criteria:** spec v1.0 with outside co-authors. Decoders outside our team emit NeuralTextStream.

### Stage 4: Foundation
Borrows from: OpenTelemetry (neutral trademark home, company cap), BIDS (elected steering group).
- [ ] Start only when there are ≥3 maintainers from ≥2 employers and outside adopters exist.
- [ ] Apply to **LF AI & Data** Sandbox (best fit) or **NumFOCUS** (for the scientific-Python library) ([requirements](../sources/case-study-opentelemetry.md#better-fits-for-fidetype)).
- [ ] Move the trademark to a neutral home.
- [ ] Elect a steering group with a company cap.

**Exit criteria:** accepted by a foundation. Elected steering group in place.

### Stage 5: Company
Borrows from: LangChain (open core), SGLang (non-profit project first, company second: LMSYS → RadixArk).
- [ ] An open-core paid layer on top ([architecture, open-core split](architecture.md#open-core-split)):
  - [ ] hosted trust and audit dashboards;
  - [ ] clinical compliance reports;
  - [ ] per-device calibration profiles;
  - [ ] OEM integrations.
- [ ] Keep the project neutral before the company exists.
- [ ] **Decide the trademark question before Stage 4.** If the project trademark moves to a foundation, the company may need its own brand.

**Exit criteria:** paying customers. The open project stays neutral and keeps outside maintainers.

> **Our take:** Stages 0–2 overlap with milestones M3–M5 of the [project plan](project-plan.md). Stages 3–5 depend on outside people and have no dates. They are "externally blocked" in the sense of the plan's timeline policy.

## Realistic expectations
- BCI is a niche field. Here "like OpenTelemetry" means *the standard in a field of a few thousand researchers and dozens of companies*. It does not mean 100k stars.
- Stars are a side effect, not the goal. Even a few thousand stars would mean field dominance.

### Success metrics
| Metric | Why it matters |
|---|---|
| Number of labs and companies whose decoders emit NeuralTextStream | The direct measure of a standard |
| Citations of the paper and the spec | Credibility in a research field |
| External contributors | The project lives without us |
| Adoption by at least one device maker | The path to the company stage |

## Cheap actions now
Low effort, high signal. **All done on 2026-11-08 (commit 677ba0e), except the project site.**
- [x] [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
- [x] [`CODE_OF_CONDUCT.md`](../../CODE_OF_CONDUCT.md) (Contributor Covenant)
- [x] [`GOVERNANCE.md`](../../GOVERNANCE.md): founder-led now, with a written path to neutral governance
- [x] [`SECURITY.md`](../../SECURITY.md)
- [x] [`spec/neuraltextstream-v0.1.md`](../../spec/neuraltextstream-v0.1.md), with stability levels
- [x] Issue and PR templates ([`.github/ISSUE_TEMPLATE/`](../../.github/ISSUE_TEMPLATE/), [`PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md))
- [x] A public roadmap issue ([#1](https://github.com/zhangzibo/fidetype/issues/1))
- [x] GitHub Discussions
- [x] A [`CITATION.cff`](../../CITATION.cff) file
- [ ] A project site, later (GitHub Pages)

> **Our take:** A CoC and a governance document are entry rules for NumFOCUS and the foundations ([OpenTelemetry case study](../sources/case-study-opentelemetry.md#foundation-path)). Writing them now costs an hour and removes a later blocker.

## The BCI standards landscape
| Standard | What it covers | Stream format for decoder output? | Our stance |
|---|---|---|---|
| [IEEE P2731](../entities/ieee-p2731.md) | BCI terminology. Authorised 2018-09-27. Still unpublished | No | Engage. Use its terms |
| IEEE P2794 | Neural-interface reporting (2022) | No | Engage |
| [BIDS](../entities/bids.md) | Neuroimaging data at rest. 850+ datasets on OpenNeuro | No (files, not streams) | Bridge. Possibly a BIDS extension proposal |
| [Lab Streaming Layer](../entities/lab-streaming-layer.md) | Real-time raw-signal transport. No formal governance doc found (**UNVERIFIED**) | No (raw signals) | Bridge. An adapter |
| **NeuralTextStream** (ours) | Decoder output: timestamped character log-probabilities ([architecture](architecture.md#neuraltextstream-explained-simply)) | Yes | The open niche |

> **Our take:** No standard covers the decoder-output stream. This is the niche. Because BIDS and LSL already cover the layers next to it, NeuralTextStream must connect to both and replace neither.

## Risks
| Risk | Seen in | Mitigation |
|---|---|---|
| **Trademark tension.** A foundation owns the project name, so the company cannot use it as its brand | OTel (trademark at the LF) vs a company model | Decide before Stage 4. Pick a separate company brand early if needed |
| **Neutrality.** A VC-backed company employs the maintainers. Rivals stop trusting the spec | SGLang / RadixArk | Neutral project first. Written governance. Company cap on seats. Foundation home |
| **Benchmark disputes.** Comparisons that are not apples to apples | SGLang | Publish exact configs. Invite rivals to rerun them |
| **Churn and hidden magic.** Breaking changes, hidden prompts, dependency bloat | LangChain (Octomind, Jun 2024) | Semver from day one. Small core. Everything inspectable. Optional extras for heavy dependencies |
| **Issue backlog.** Too many open issues for the maintainers | SGLang (about 6.5k open) | Templates, triage labels, partner-owned adapters |
| **Rival format.** We split the field instead of joining it | OTel's origin (two projects) | Bridge to LSL and BIDS. Engage IEEE |
| **Unverified adoption claims** | SGLang ("400k GPUs", UNVERIFIED) | Report only adoption we can check |

## Related pages
- [Direction decision](direction-decision.md)
- [Architecture](architecture.md)
- [Project plan](project-plan.md)
- [Long-term roadmap](roadmap-standard.md) (phases P1–P11 after v0.1)
- Case studies: [SGLang](../sources/case-study-sglang.md), [LangChain](../sources/case-study-langchain.md), [OpenTelemetry](../sources/case-study-opentelemetry.md)
- Entities: [BIDS](../entities/bids.md), [Lab Streaming Layer](../entities/lab-streaming-layer.md), [IEEE P2731](../entities/ieee-p2731.md)
- [Diagrams](../diagrams/index.html) (diagram 10: open-source path)
