---
title: Overview — non-invasive brain-to-text, where things stand
type: overview
tags: [synthesis]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-10
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

## What our own experiments show (2026-11-08)
- **With small data, a CTC decoder needs a keystroke hint.** CTC alone learned only a text prior. A keystroke auxiliary loss makes it use the MEG (greedy test CER 0.619, target 0.59) ([decoder M1 results](questions/decoder-m1-results.md)). A beam with a Spanish char LM, tuned on val, lowers it to 0.590; greedy stays at 0.619, and the true sentence is never in the 20-best ([M1-C2](../experiments/2026-11-08-m1c2-beam-lm/results.md)).
- **Sentence context helps a little at this data size (2026-11-10).** With oracle key timing, a Conv + Transformer keystroke decoder reaches test CER 0.577 greedy and 0.488 with the char LM. The per-key logistic regression gives 0.597 / 0.531. The Transformer itself adds only about 0.02 CER; v1 got 0.31 from it. The model overfits the about 200 unique training sentences ([M1-15 r2](questions/decoder-m1-results.md#m1-15-r2-sentence-context-decoder-trained-to-the-val-plateau-2026-11-10)).
- **More data helps the sentence-context decoder (2026-11-10).** On the full cache (19 participants, the same 101 training sentences), test CER is 0.508 greedy and 0.447 with the LM (0.497 / 0.437 on the r2 test instances). A causal version costs nothing. Part of the gain (about 0.013 CER) is template memorisation: 6 of 17 test sentences have a close variant in train. The no-signal floor is about 0.69 CER, not 1.0. All M1-15 runs use oracle key timing, so the async M1 target is still open ([M1-15 full-r1 and r3](questions/m1-15-full-r1-r3-result.md)).
- **The trust layer is safe on real MEG, but not yet useful.** It stops all wrong and hallucinated commits. But at key accuracy 0.39, no BCI policy beats gaze typing alone (2.96 vs 3.14 eWPM; with the r2 decoder 3.06 vs 3.14; with the full-cache decoder 3.23 vs 3.15, CI [3.08, 3.40], so parity) ([trust core v0 results](questions/trust-core-v0-results.md#7-per-word-offer-and-partial-correction-2026-11-08)).

> **Our take:** Usefulness needs a stronger decoder, and every speed claim needs a no-BCI baseline.

## The big open problems
1. **Real-time causal decoding**: v2 still waits for the end of the sentence.
2. **Patients with no movement**: going from overt typing to attempted or imagined typing, without labels.
3. **Cross-subject generalisation**: the encoder is the bottleneck.
4. **Hardware**: moving from cryogenic MEG to room-temperature [OPM-MEG](concepts/opm-meg.md).
5. **Data**: only one small public typing-MEG dataset exists ([SpanishBCBL](entities/spanishbcbl-dataset.md)), and the larger one is embargoed ([EnglishBCBL](entities/englishbcbl-dataset.md)). All public non-invasive brain typing data is NC. Commercially clean data with text and timing exists only for implants (CC0, [Brain-to-Text '25](entities/brain-to-text-25.md)) and wrist sEMG typing (CC BY 4.0, [KT-sEMG](entities/kt-semg-dataset.md), [Toronto](entities/toronto-semg-typing-dataset.md)) ([public datasets survey](questions/public-datasets.md)).

> **Our take (2026-11-10):** Wrist sEMG typing is the natural **second testbed modality** after MEG: the most typing data ([emg2qwerty](entities/emg2qwerty.md), 346 h, NC), two CC BY sets, and a consumer device. Brain-to-Text '25 is the licence-clean testbed for the trust layer on real decoder output.

## Project direction
On 2026-11-07 we chose **trustworthy neural text entry**. On 2026-11-08 the user named the project **Fidetype** (package `fidetype`). We build a layer that makes text from any neural decoder reliable: it calibrates confidence, abstains or asks when it is not sure, offers n-best choices, guards against LLM hallucination, and works in real time.

On 2026-11-08 the user widened the scope to an OpenTelemetry-level project. Fidetype now aims to be **the vendor-neutral standard and trust layer for neural input**: text or intent decoded from wrist EMG, EEG, MEG/OPM-MEG or implants. NeuralTextStream becomes a modality-agnostic and vocabulary-agnostic spec ([spec v0.1](../spec/neuraltextstream-v0.1.md)), and adapters for every modality are first-class. Research MEG stays the credibility base and the hardest test case for Paper 1. Success is the number of decoders and devices that emit NeuralTextStream. The user accepts a multi-year horizon and the need for outside partners ([scope decision](questions/direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level)).
- The decision and the evidence: [direction-decision](questions/direction-decision.md).
- The six-layer design and the roadmap: [architecture](questions/architecture.md).
- Project plan: milestones M0–M7, tasks, risks and the working process: [project-plan](questions/project-plan.md).
- Open-source path: NeuralTextStream as a vendor-neutral spec, credibility from Paper 1 and benchmarks, a company later. Success means decoders that emit NeuralTextStream, not stars: [open-source playbook](questions/open-source-playbook.md).
- **Long-term roadmap (2026-11-10).** The user decided on full standardisation at OpenTelemetry scale, built by us. M0–M7 are only v0.1. Eleven phases follow (P1–P11): spec 1.0, SDKs in six languages, a collector, adapters, a product-grade trust layer, a benchmark, conformance, docs and demo, governance, adoption and research. The gap to OpenTelemetry scale is mostly SDKs, adapters and integrations, not the core: [roadmap-standard](questions/roadmap-standard.md).

## Where this project might fit
See [research directions](questions/research-directions.md).
