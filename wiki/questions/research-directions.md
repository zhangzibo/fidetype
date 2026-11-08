---
title: What could this project do? (candidate directions)
type: question
tags: [planning, directions]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-07
---

# Candidate directions (as of 2026-11-07)

**Question asked:** Given no hardware, what could a long-term public BCI project realistically do, starting from Brain2Qwerty?

**Constraints:**
- No MEG or EEG hardware.
- The only public typing-MEG data is [SpanishBCBL](../entities/spanishbcbl-dataset.md).
- Meta's code is CC BY-NC.
- The user is undecided between research papers and a product.

## 1. Reproduce v1 on public data (foundation, recommended first step)
- Run the [code](../sources/brain2qwerty-code.md) on SpanishBCBL and match the paper's ~0.36 CER (Conv+Trans) and ~0.29 CER (with LM).
- This builds hands-on skill and gives us a baseline and our own clean pipeline.
- It is feasible on one GPU, at ~18 h per run on a 32 GB card.

## 2. Research problems the authors name as open (public data only)
| Direction | Why it matters | Source |
|---|---|---|
| **Causal / streaming decoding** | Real-time text, needed for any real use | [sync vs async](../concepts/synchronous-vs-asynchronous-decoding.md) |
| **Cross-subject / self-supervised encoder pretraining** | The authors' stated "priority". The encoder is the bottleneck (r = 0.78 with WER) | [data scaling](../concepts/data-scaling.md), [v2](../sources/brain2qwerty-v2.md) |
| **Sensor reduction / optimised selection** | The path to [OPM-MEG](../concepts/opm-meg.md) wearables | [v2](../sources/brain2qwerty-v2.md) Table 2 |
| **Hallucination-aware LLM decoding** | Fluent wrong sentences are dangerous for a patient | [NeuroLLM](../concepts/neuro-llm.md), [metrics](../concepts/error-metrics.md) |

## 3. Something buildable today
- [emg2qwerty](../entities/emg2qwerty.md): wrist-EMG typing with a large public dataset and affordable hardware. It is not strictly brain-based.
- Consumer [EEG](../concepts/eeg.md): accessible, but v1 shows 65% CER, so it is weak for typing.

## Open questions back to the user
- What GPU or compute is available?
- Is the leaning towards papers or a product?

## Next sources to ingest
1. Défossez et al. 2023 (BrainModule)
2. [emg2qwerty](../entities/emg2qwerty.md)
3. LibriBrain / PNPL 2025 (large public MEG)
4. Willett 2021 / 2023 and Jude 2026 (the invasive state of the art)
5. d'Ascoli 2025
6. Zhang 2025 (the companion typing neuroscience paper)
7. Boto 2018 (OPM-MEG)
