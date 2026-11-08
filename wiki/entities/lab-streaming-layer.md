---
title: Lab Streaming Layer (LSL)
type: entity
tags: [standard, streaming, real-time, tooling]
sources: [case-study-opentelemetry]
updated: 2026-11-08
---

# Lab Streaming Layer (LSL)

LSL is the de facto tool for real-time streams in neuroscience labs. It comes from SCCN at UCSD. It moves raw signals (EEG, markers, other sensors) between programs with time synchronisation. It does not define a format for decoder output ([OpenTelemetry case study](../sources/case-study-opentelemetry.md#bci-and-neuro-standards)).

- **Governance:** we found no formal governance document. **UNVERIFIED.**
- **Use in Fidetype:** M6 plans an LSL input ([project plan](../questions/project-plan.md#m6-device-adapters-target-11-14--11-15)). The architecture lists LSL for live devices in layer 1 ([architecture](../questions/architecture.md#the-six-layers)).

> **Our take:** LSL carries the raw signal. NeuralTextStream carries the decoder output. They fit together. We bridge to LSL (an adapter, and possibly an LSL stream type for NeuralTextStream). We do not compete with it. See the [open-source playbook](../questions/open-source-playbook.md).

Related: [BIDS](bids.md), [IEEE P2731](ieee-p2731.md).
