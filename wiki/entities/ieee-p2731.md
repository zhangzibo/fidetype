---
title: IEEE P2731 (BCI terminology standard)
type: entity
tags: [standard, ieee, terminology]
sources: [case-study-opentelemetry, neural-input-landscape-2026]
updated: 2026-11-08
---

# IEEE P2731

https://standards.ieee.org/ieee/2731/

IEEE P2731 is a draft IEEE standard for BCI terminology ([OpenTelemetry case study](../sources/case-study-opentelemetry.md#bci-and-neuro-standards)).

| Item | Value |
|---|---|
| Scope | A unified terminology for BCI |
| Authorised | 2018-09-27 |
| Status (2026-11-08) | Still unpublished |
| Stream format | Not defined |

A related project is **IEEE P2794** (neural-interface reporting, 2022). It also defines no stream format.

> **Our take:** Neither IEEE effort covers decoder output streams. This is the niche for NeuralTextStream. We should engage both working groups and use their terms. See the [open-source playbook](../questions/open-source-playbook.md).

## Related venues
| Venue | What it does | Status |
|---|---|---|
| **ISO/IEC JTC 1/SC 43** | The ISO/IEC subcommittee for BCI. Its work items are a venue where NTS could be proposed | Has BCI work items |
| **ISO/IEC TS 27571:2026** | Non-invasive BCI raw data (SC 43). Raw data only, not decoded output | **UNVERIFIED** (iso.org returned 403) |
| **Joint CEN-CLC BCI committee** | A European BCI standards committee | Proposed in late 2025 |

Source: [neural input landscape report](../sources/neural-input-landscape-2026.md#regulatory-angle).

> **Our take:** SC 43 may be a stronger venue than the IEEE groups, because it already has a BCI document (TS 27571). TS 27571 covers raw data, so NTS would sit next to it, not compete with it. We should propose NTS there only after it has real adopters.

Related: [BIDS](bids.md), [Lab Streaming Layer](lab-streaming-layer.md), [Apple BCI HID](apple-bci-hid.md), [W3C EMMA](w3c-emma.md).
