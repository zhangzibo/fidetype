---
title: FEP process (Fidetype Enhancement Proposals)
type: concept
tags: [spec, governance, fep, standard, process, conformance]
sources: []
updated: 2026-11-14
---

# FEP process

A **FEP** (Fidetype Enhancement Proposal) is the written proposal for a change to a spec in `spec/`. It plays the role of a PEP in Python or an RFC at the IETF. The FEP files are in [`spec/feps/`](../../spec/feps/). The rules are in [GOVERNANCE.md section 4](../../GOVERNANCE.md#4-spec-changes-feps), [CONTRIBUTING.md section 8](../../CONTRIBUTING.md#8-spec-changes-feps) and [NTS 1.0 RC2 section 11.6](../../spec/nts-1.0-rc2.md#116-change-process-and-fep-lifecycle).

## Steps
| Step | What happens | Where |
|---|---|---|
| 1. Idea | Open an issue or a Discussion to test the idea | [spec/README.md](../../spec/README.md#how-to-change-a-spec) |
| 2. Write | Copy `0000-template.md` to `NNNN-short-title.md` (next free number). Fill in all sections | [template](../../spec/feps/0000-template.md) |
| 3. Propose | Open a pull request with the FEP alone | CONTRIBUTING.md section 8 |
| 4. Decide | Lazy consensus: accepted if no maintainer objects in 7 days. Else a 7-day vote. A change to a **Stable** part always needs an explicit vote | GOVERNANCE.md sections 3 and 4 |
| 5. Implement | A second pull request changes the spec, the reference implementation, the tests and the changelog in one release | CONTRIBUTING.md section 8 |

Small fixes (typos, broken links, clearer wording with the same meaning) do not need a FEP.

## Template sections
Summary, Motivation (a real device, decoder or dataset), Proposal (RFC 2119 words, field names, types, stability level), Examples, Compatibility, Reference implementation, Alternatives (does LSL, BIDS, IEEE P2731 or OpenTelemetry already solve it?), Privacy and leakage, Open questions.

## Lifecycle
| State | Meaning (RC2 section 11.6) |
|---|---|
| Draft | Proposed. Anything can change |
| Under review | Open for comment, with a reference implementation and conformance vectors |
| Accepted | The maintainers agreed. The change is planned for a release |
| Implemented | In the reference implementation and the vectors, in all SDKs that claim the profile |
| Final | Part of a released spec version |
| Rejected / Withdrawn | Not adopted. The FEP stays as the record |

Rule **FEP-1**: each FEP needs a reference implementation and conformance vectors before it is Implemented. Each FEP has an opt-in conformance profile (`fep-0001` …) that tests it without changing the v0.1 levels ([conformance suite](conformance-suite.md)).

## FEPs so far (2026-11-14)
| FEP | Subject | Status | Wiki page |
|---|---|---|---|
| [0001](../../spec/feps/0001-streaming-trust-events.md) | Streaming trust events (`segment_end`, evidence fields, decode declaration, `trust_decision`) | Draft (in 1.0 RC2) | [`trust_decision` event](trust-decision.md), [streaming trust layer](streaming-trust-layer.md) |
| [0002](../../spec/feps/0002-nts-over-lsl.md) | NTS over LSL (`nts-lsl/0.1`) | Draft (in 1.0 RC2) | [LSL input](lsl-input.md) |
| [0003](../../spec/feps/0003-intent-events.md) | Output profiles and discrete intent events | Draft (in 1.0 RC2) | [intent events](intent-events.md) |
| [0004](../../spec/feps/0004-nts-over-websocket.md) | NTS over WebSocket (`nts-ws/0.1`) | Draft (in 1.0 RC2) | [WebSocket input](websocket-input.md) |
| [0005](../../spec/feps/0005-control-events.md) | Continuous-control events | Draft (in 1.0 RC2) | [control events](control-events.md) |
| [0006](../../spec/feps/0006-collector.md) | The collector (reference architecture, not a format change) | Draft (not in 1.0) | [collector](collector.md) |

RC2 folds FEPs 0001–0005 into one document and proposes them for **Under review** ([NTS specification](nts-spec.md)). Source: [spec/README.md](../../spec/README.md#proposals-feps).

> **Our take:** All six FEPs so far come from the maintainers, and the founder is the only maintainer (GOVERNANCE.md section 1). So lazy consensus is not yet a real check. The process becomes meaningful when outside decoder groups write or review FEPs (roadmap P1-07 and P9, [roadmap](../questions/roadmap-standard.md)). The rule "reference implementation and vectors first" (FEP-1) is the part that already works: every FEP so far has a conformance profile.

## Related
- [NTS specification](nts-spec.md)
- [Conformance suite](conformance-suite.md)
- [Long-term roadmap, P1 and P9](../questions/roadmap-standard.md)
- [Open-source playbook](../questions/open-source-playbook.md)
