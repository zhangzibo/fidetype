---
title: BIDS (Brain Imaging Data Structure)
type: entity
tags: [standard, neuroimaging, data-format, community, governance]
sources: [case-study-opentelemetry]
updated: 2026-11-08
---

# BIDS (Brain Imaging Data Structure)

https://pmc.ncbi.nlm.nih.gov/articles/PMC10516110/ (history and governance paper)

BIDS is a community standard for how to organise neuroimaging data on disk. It covers MRI and, through extensions, MEG, EEG, iEEG and more. It describes data at rest, not live streams ([OpenTelemetry case study](../sources/case-study-opentelemetry.md#bids-the-best-analogue)).

| Item | Value |
|---|---|
| Start | A 2014 post. An INCF-backed meeting in 2015 |
| Paper | *Scientific Data*, 2016 |
| Endorsement | INCF, 2018 |
| Governance | An elected 5-person steering group, after the founder left in 2019 |
| Extensions | BEPs (BIDS Extension Proposals) |
| Adoption | 850+ datasets on OpenNeuro |
| Tooling | A schema-driven validator |
| Principles | "adoption is crucial", "don't reinvent the wheel", 80/20 |

> **Our take:** BIDS is the best model for how NeuralTextStream can become a standard in neuroscience. We bridge to BIDS (an adapter, and possibly a BIDS extension proposal). We do not build a rival format. See the [open-source playbook](../questions/open-source-playbook.md).

Related: [Lab Streaming Layer](lab-streaming-layer.md), [IEEE P2731](ieee-p2731.md), [SpanishBCBL dataset](spanishbcbl-dataset.md).
