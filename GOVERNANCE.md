# Fidetype governance

Fidetype aims to become a vendor-neutral standard for neural input. A standard needs neutral governance. This file states the current model and the written path to neutral governance. The path follows [OpenTelemetry](https://opentelemetry.io/) and [BIDS](https://bids.neuroimaging.io/).

## 1. Current state: founder-led
- Fidetype is **founder-led** (BDFL model). The founder is [@zhangzibo](https://github.com/zhangzibo).
- The founder is the only maintainer today. The founder makes the final decision when there is no consensus.
- The founder commits to move to the neutral model below. This file is the record of that commitment.

## 2. Path to neutral governance
| Stage | Condition to start | Change |
|---|---|---|
| **1. Maintainers by merit** | Now | The maintainers invite regular contributors with good, sustained contributions to become maintainers. Adapter owners can become code owners of their adapters. |
| **2. Technical Steering Group (TSG)** | ≥ 3 maintainers from ≥ 2 employers | The TSG replaces the founder as the final decision maker. Decisions are by majority of the TSG. |
| **3. Elected steering group** | Outside adopters exist (decoders outside the project emit NeuralTextStream) | Contributors elect the steering group for fixed terms. **At most 2 seats per organisation.** |
| **4. Neutral foundation** | The steering group agrees | Fidetype applies to a neutral home: **LF AI & Data** or **NumFOCUS**. The **trademark moves to that foundation.** |

Each stage keeps the rules of the earlier stages, unless the new body changes them by a recorded vote.

## 3. Decision process
1. **Lazy consensus.** A proposal (an issue, a PR or a FEP) is accepted if no maintainer objects within **7 days**. Small changes need only one maintainer approval.
2. **Vote.** If a maintainer objects and the discussion does not resolve it, any maintainer can call a vote. The vote is open for 7 days. A simple majority of the maintainers who vote decides.
3. **Tie or founder stage.** In stage 1, the founder breaks a tie. From stage 2, the TSG decides.

Record each vote in the issue or the PR.

## 4. Spec changes: FEPs
- A change to a spec in [`spec/`](spec/) needs a FEP (Fidetype Enhancement Proposal). The template is [`spec/feps/0000-template.md`](spec/feps/0000-template.md).
- A FEP follows the decision process above. A FEP that changes a **Stable** part needs an explicit vote, not only lazy consensus.
- Accepted FEPs stay in `spec/feps/` as the record.
- Details: [CONTRIBUTING.md, section 8](CONTRIBUTING.md#8-spec-changes-feps).

## 5. Stability levels
Each spec part and each public API has one level:

| Level | Meaning |
|---|---|
| **Development** | Can change or go away in any release |
| **Stable** | No breaking change within one major version (semver) |
| **Deprecated** | Still supported. Removed after its support window (at least 12 months for Stable parts) |
| **Removed** | Gone |

Today, all parts are at Development.

## 6. Code of conduct
All participants follow the [Code of Conduct](CODE_OF_CONDUCT.md). The maintainers enforce it.

## 7. Changes to this file
A change to this file follows the decision process. It needs an explicit vote from stage 2 onward.
