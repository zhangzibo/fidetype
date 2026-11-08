---
title: W3C EMMA (Extensible MultiModal Annotation)
type: entity
tags: [standard, w3c, multimodal, speech, confidence, n-best]
sources: [neural-input-landscape-2026]
updated: 2026-11-08
---

# W3C EMMA

EMMA is a W3C markup language that annotates the interpreted input of speech and other multimodal systems. It is the closest non-neural precedent for NeuralTextStream ([landscape report](../sources/neural-input-landscape-2026.md#novelty-verdict)).

| Item | Value |
|---|---|
| EMMA 1.0 | W3C Recommendation, 2009 |
| EMMA 2.0 | Working Draft since 2015 |
| Confidence | `emma:confidence` |
| N-best | `emma:one-of` lists |
| Other | Lattices; timestamps |
| Neural input | Not covered |

## What NeuralTextStream takes from EMMA
| EMMA | NeuralTextStream |
|---|---|
| `emma:confidence` | `decision` score, plus `score_semantics` to say what the score means |
| `emma:one-of` | `nbest[]` with `is_final` and `revision_of` |
| Timestamps | `t_signal_start`, `t_signal_end`, `t_decoded`, `t_emitted`, `clock_domain` |

The positioning is: **NTS = "EMMA for neural input, OpenTelemetry-style"** ([OpenTelemetry case study](../sources/case-study-opentelemetry.md)).

> **Our take:** EMMA shows that a confidence and n-best format for recognised input is a solved design problem for speech. It did not become a live ecosystem: 2.0 has stayed a draft since 2015. So we copy its data model, not its delivery. NeuralTextStream adds what EMMA lacks: a streaming wire binding, semantic conventions for devices and decoders, and a declared meaning for each score.

Related: [Apple BCI HID](apple-bci-hid.md), [IEEE P2731](ieee-p2731.md).
