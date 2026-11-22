---
title: Synchronous vs asynchronous decoding
type: concept
tags: [decoding, real-time, ctc]
sources: [brain2qwerty-v1, brain2qwerty-v2, emg2qwerty, generic-neuromotor-interface]
updated: 2026-11-22
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
v2 is asynchronous but **not causal**. The Conformer and the LLM both see the whole sentence, so output only appears once the sentence ends. A truly streaming decoder is still open work. The authors point to a causal Conformer as a template and cite [emg2qwerty](../entities/emg2qwerty.md) for it. That model is in the [CTRL-labs generic neuromotor interface paper](../sources/generic-neuromotor-interface.md), not in emg2qwerty.

> **Contradiction:** the [emg2qwerty paper](../sources/emg2qwerty.md) has no Conformer. Its baseline is a TDS ConvNet with a 1 s receptive field. It trains with 900 ms past and 100 ms future context and is tested on whole sessions (Sec. 5.1–5.2, pp. 7–8). We read this as near-causal (100 ms lookahead), not strictly causal. Our P11-01 EMG decoder has no lookahead ([P11-01 results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md)).

**Verdict (2026-11-22, P11-26): confusion confirmed.** The CTRL-labs paper (Nature 2025) decodes handwriting from wrist sEMG with a 15-layer causal Conformer. Self-attention sees only a fixed window of past steps (16 steps in layers 1–10, 8 in layers 11–15). CTC with FastEmit reduces streaming latency, and decoding is greedy ([source](../sources/generic-neuromotor-interface.md), Methods, PDF pp. 15–16). This is the real causal template.

> **Our take:** A causal, low-latency MEG typing decoder that shows text as you go is an open problem with a clear definition. It is directly motivated by both papers and can be trained on public data (SpanishBCBL). It is a strong candidate for a first research contribution.

> **Our result (2026-11-11):** our async ConvCTC reaches test CER 0.506 greedy on SpanishBCBL (19 participants), with the same segment bounds as v2 and no key times at inference. Its training uses key times as aux-loss labels ([M1-09](../questions/m1-09-async-full-result.md)).

> **Our result (2026-11-14):** a causal GRU-CTC decoder with a lookahead L of 0 to 500 ms on intracortical T15 data: accuracy improves most in the first 40 ms; a model trained with L = 500 ms emits phonemes earlier than one trained with L = 0 ([lookahead vs accuracy and latency](../questions/lookahead-latency-accuracy.md)).

Related: [CTC](ctc.md) · [NeuroLLM](neuro-llm.md) · [M1-09 result](../questions/m1-09-async-full-result.md) · [Lookahead vs accuracy and latency](../questions/lookahead-latency-accuracy.md)
