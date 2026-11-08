---
title: Overview — non-invasive brain-to-text, where things stand
type: overview
tags: [synthesis]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-08
---

# Overview

*Synthesis based on 3 sources: [v1](sources/brain2qwerty-v1.md), [v2](sources/brain2qwerty-v2.md) and the [code](sources/brain2qwerty-code.md). It will be revised as more sources are ingested.*

## The state of the art (non-invasive, typing)
Meta's Brain2Qwerty decodes what healthy people type from [MEG](concepts/meg.md):
- **v1 (2026)**, keystroke-locked: **29% CER**.
- **v2 (2026)**, continuous decoding with a [CTC](concepts/ctc.md) encoder feeding a [NeuroLLM](concepts/neuro-llm.md): **39% WER**. The best subject reaches 22% WER, and 28% of their sentences are word-perfect.

For comparison, invasive implants reach **<2% WER** for typing (Jude et al. 2026), so the gap is still large.

## What we believe so far
1. **MEG beats EEG by more than 2×** on this task ([EEG](concepts/eeg.md) gives 65% CER vs 29%). Modality matters as much as the model.
2. **The signal is motor.** The decoder reads motor-cortex activity from finger movements, and its errors follow the keyboard layout. It decodes the *act of typing*, not thought.
3. **Data is the lever.** Performance is log-linear in recording hours with no plateau, and sentence diversity matters separately from volume ([data scaling](concepts/data-scaling.md)).
4. **Data volume is what makes continuous decoding work.** The async encoder goes from 0.59 to 0.25 CER with 10× more data per subject ([sync vs async](concepts/synchronous-vs-asynchronous-decoding.md)).
5. **LLMs help meaning but can hallucinate.** They give better WER and SemER but worse CER ([error metrics](concepts/error-metrics.md)).
6. **Wearables look plausible.** Halving the sensor count costs about 6 points of WER ([OPM-MEG](concepts/opm-meg.md)).

## The big open problems
1. **Real-time causal decoding**: v2 still waits for the end of the sentence.
2. **Patients with no movement**: going from overt typing to attempted or imagined typing, without labels.
3. **Cross-subject generalisation**: the encoder is the bottleneck.
4. **Hardware**: moving from cryogenic MEG to room-temperature [OPM-MEG](concepts/opm-meg.md).
5. **Data**: only one small public typing-MEG dataset exists ([SpanishBCBL](entities/spanishbcbl-dataset.md)), and the larger one is embargoed ([EnglishBCBL](entities/englishbcbl-dataset.md)).

## Project direction
On 2026-11-07 we chose **trustworthy neural text entry**. On 2026-11-08 the user named the project **Fidetype** (package `fidetype`). We build a layer that makes text from any neural decoder reliable: it calibrates confidence, abstains or asks when it is not sure, offers n-best choices, guards against LLM hallucination, and works in real time.

On 2026-11-08 the user widened the scope to an OpenTelemetry-level project. Fidetype now aims to be **the vendor-neutral standard and trust layer for neural input**: text or intent decoded from wrist EMG, EEG, MEG/OPM-MEG or implants. NeuralTextStream becomes a modality-agnostic and vocabulary-agnostic spec ([spec v0.1](../spec/neuraltextstream-v0.1.md)), and adapters for every modality are first-class. Research MEG stays the credibility base and the hardest test case for Paper 1. Success is the number of decoders and devices that emit NeuralTextStream. The user accepts a multi-year horizon and the need for outside partners ([scope decision](questions/direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level)).
- The decision and the evidence: [direction-decision](questions/direction-decision.md).
- The six-layer design and the roadmap: [architecture](questions/architecture.md).
- Project plan: milestones M0–M7, tasks, risks and the working process: [project-plan](questions/project-plan.md).
- Open-source path: NeuralTextStream as a vendor-neutral spec, credibility from Paper 1 and benchmarks, a company later. Success means decoders that emit NeuralTextStream, not stars: [open-source playbook](questions/open-source-playbook.md).

## Where this project might fit
See [research directions](questions/research-directions.md).
