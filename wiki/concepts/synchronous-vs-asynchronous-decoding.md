---
title: Synchronous vs asynchronous decoding
type: concept
tags: [decoding, real-time, ctc]
sources: [brain2qwerty-v1, brain2qwerty-v2]
updated: 2026-11-11
---

# Synchronous vs asynchronous decoding

- **Synchronous**: you classify a window *time-locked to a known event*, such as each keystroke. This needs the event timings, which a real user doesn't provide, so **it can't run live**. Brain2Qwerty v1 works this way, with a −0.2…+0.3 s window per key ([v1](../sources/brain2qwerty-v1.md)).
- **Asynchronous**: you decode a symbol sequence from a *continuous* signal with no event timings. This can in principle run in real time. Brain2Qwerty v2 does it with a [CTC](ctc.md)-trained Conformer ([v2](../sources/brain2qwerty-v2.md)).

## Evidence (v2, Fig. 1D–E)
Encoder CER, synchronous vs asynchronous:

| Dataset | Sync CER | Async CER |
|---|---|---|
| SpanishBCBL (~1 h/subject) | 0.39 | 0.59 |
| EnglishBCBL (~10 h/subject) | 0.23 | 0.25 |

Asynchronous decoding is the harder problem. With enough data, though, it nearly catches up: **"the scale of the dataset is a decisive factor enabling asynchronous decoding"**. See [data scaling](data-scaling.md).

## Still not real-time
v2 is asynchronous but **not causal**. The Conformer and the LLM both see the whole sentence, so output only appears once the sentence ends. A truly streaming decoder is still open work. The authors point to the causal Conformer in [emg2qwerty](../entities/emg2qwerty.md) as a template.

> **Our take:** A causal, low-latency MEG typing decoder that shows text as you go is an open problem with a clear definition. It is directly motivated by both papers and can be trained on public data (SpanishBCBL). It is a strong candidate for a first research contribution.

> **Our result (2026-11-11):** our async ConvCTC reaches test CER 0.506 greedy on SpanishBCBL (19 participants), with the same segment bounds as v2 and no key times at inference. Its training uses key times as aux-loss labels ([M1-09](../questions/m1-09-async-full-result.md)).

Related: [CTC](ctc.md) · [NeuroLLM](neuro-llm.md) · [M1-09 result](../questions/m1-09-async-full-result.md)
