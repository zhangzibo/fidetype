---
title: "Case study: OpenTelemetry (open standard and foundation path)"
type: source
tags: [open-source, standards, case-study, governance, foundation, bci-standards]
sources: [case-study-opentelemetry]
updated: 2026-11-08
---

# Case study: OpenTelemetry

## Citation and links
- **Project:** OpenTelemetry (OTel), a vendor-neutral standard for traces, metrics and logs. https://opentelemetry.io
- **Licence:** Apache-2.0. The trademark sits with the Linux Foundation.
- **Raw source:** none saved in `references/`. This page summarises a verified web-research report (2026-11-08). Numbers are as of 2026-11-08.
- **Key links:**
  - CNCF graduation: https://opentelemetry.io/blog/2026/otel-graduates/
  - LF AI & Data: https://lfaidata.foundation/
  - NumFOCUS projects: https://numfocus.org/projects-overview
  - IEEE P2731: https://standards.ieee.org/ieee/2731/
  - BIDS history paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC10516110/

## TL;DR
OpenTelemetry came from a merger of two rival standards. It succeeded because no single company owns it, and because vendors compete on the backend, not on instrumentation. Its design separates a spec, a protocol, an API, SDKs and shared field names. Its governance caps the seats of any one company. For BCI, no stream-format standard exists yet. BIDS is the closest analogue in neuroscience.

## Numbers
| Item | Value |
|---|---|
| CNCF Sandbox | 2019-05 |
| CNCF Incubating | 2021-08-26 |
| CNCF Graduated | **2026-05-21** |
| Contributors (all time) | 12,000+ |
| Companies (all time) | 2,800+ |
| CNCF activity rank | 2nd most active of 240+ projects, after Kubernetes |
| Vendors that accept OTLP natively | 102 of 105 listed |
| Collector stars | 7,741 |
| Spec stars | 4,389 |
| Python SDK stars | 2,703 |

## Origin
- Two rival standards existed: OpenTracing (CNCF) and OpenCensus (Google/Microsoft).
- They merged in May 2019, because "the biggest problem was that there were two projects".
- Bridges kept both working. Both parent projects were frozen.
- Google, Microsoft, LightStep and Uber drove the merger.

## Design
| Part | Purpose |
|---|---|
| Spec | Defines the behaviour of all implementations |
| Semantic conventions | Shared field names. A separate repo since 2023. Changes are described by a schema |
| OTLP | The wire protocol |
| API vs SDK split | Libraries depend on the small API. Apps choose an SDK |
| Many SDKs | One per language |
| Collector + contrib repo | A vendor-agnostic pipeline. Vendors add their parts in contrib |
| Stability levels | Development / Stable / Deprecated / Removed |
| Support windows | 3 years for APIs |

### Process and governance
- **OTEPs:** proposals for changes.
- **SIGs:** working groups per area.
- **Technical Committee.**
- **Governance Committee:** 9 elected seats, at most 2 per company.

## Why vendors joined
1. No one owns it. The trademark sits with the Linux Foundation, and company caps apply.
2. Instrumentation is a shared cost, not a differentiator.
3. Vendors compete on the backend.
4. A standard makes the market bigger for all.

## Foundation path
### CNCF
| Level | Requirement |
|---|---|
| Sandbox | Apache-2.0, a CoC, the trademark transferred to the LF, ≥3 maintainers from ≥2 employers |
| Incubating | 5–7 adopters |
| Graduated | A security audit |

The CNCF scope is a poor fit for BCI.

### Better fits for Fidetype
| Foundation | Requirements | Link |
|---|---|---|
| **LF AI & Data** | Sandbox needs a member sponsor and an OpenSSF badge. Incubation needs ≥2 organisations | https://lfaidata.foundation/ |
| **NumFOCUS** | Affiliation, or fiscal sponsorship. Fiscal sponsorship needs a CoC and a 3–5 person leadership group, not all from one institution | https://numfocus.org/projects-overview |

## BCI and neuro standards
| Standard | Status | Stream format? |
|---|---|---|
| [IEEE P2731](../entities/ieee-p2731.md) (BCI terminology) | Authorised 2018-09-27. Still unpublished | No |
| IEEE P2794 (neural-interface reporting, 2022) | — | No |
| [BIDS](../entities/bids.md) | Community standard. 850+ datasets on OpenNeuro | Files at rest, not live streams |
| [Lab Streaming Layer](../entities/lab-streaming-layer.md) | De facto lab streaming tool (SCCN/UCSD). No formal governance doc found (**UNVERIFIED**) | Raw signal transport, not decoder output |

Neither IEEE effort defines a stream format. This is an open niche.

### BIDS: the best analogue
- 2014: a first post. 2015: an INCF-backed meeting. 2016: a *Scientific Data* paper. 2018: INCF endorsement.
- 2019: the founder left. An elected 5-person steering group took over.
- BEPs (BIDS Extension Proposals) add new modalities: MEG, EEG, iEEG and more.
- 850+ datasets on OpenNeuro.
- A schema-driven validator.
- Its principles: "adoption is crucial", "don't reinvent the wheel", 80/20.

## Criticisms and limitations
- The report gives no major criticisms of OTel.
- The foundation path is slow: Sandbox to Graduated took 7 years.
- LSL governance status is **UNVERIFIED**.

## Lessons for Fidetype
1. **Make NeuralTextStream a spec, not only code.** Separate the spec, the validator, the reference library and the adapters.
2. **Use stability levels and support windows** from the first version.
3. **Shared field names (semantic conventions)** let different decoders interoperate.
4. **Neutrality brings vendors.** Decoder companies will emit a format only if no rival owns it. A foundation and a company cap give this.
5. **Never create a rival format where one exists.** OTel itself came from ending a split. Bridge to LSL and BIDS; do not fight them.
6. **Plan the foundation step early.** The entry rules (≥3 maintainers, ≥2 employers, a CoC) are cheap to prepare.
7. **Copy BIDS for the community model:** proposals for extensions, a validator, an elected steering group, and the 80/20 rule.

> **Our take:** The trust layer itself is like an OTel SDK: a shared cost that decoder makers do not want to rebuild. Decoder companies compete on their decoders, as OTel vendors compete on their backends. This is why a neutral standard can work here.

## Feeds
- [Open-source growth playbook](../questions/open-source-playbook.md)
- [BIDS](../entities/bids.md), [Lab Streaming Layer](../entities/lab-streaming-layer.md), [IEEE P2731](../entities/ieee-p2731.md)
- Other case studies: [SGLang](case-study-sglang.md), [LangChain](case-study-langchain.md)
