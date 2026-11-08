---
title: Model soup (per-subject LoRA averaging)
type: concept
tags: [training, lora, cross-subject]
sources: [brain2qwerty-v2]
updated: 2026-11-07
---

# Model soup

A model soup is a set of fine-tuned models whose **weights are averaged** into a single model (Wortsman et al. 2022). Brain2Qwerty v2 applies the idea per subject. It trains **one LoRA adapter per subject**, treating each subject's MEG signature as a separate "task", then averages the adapters uniformly into a single adapter that is used for everyone ([v2](../sources/brain2qwerty-v2.md), §2.3).

## Evidence (Fig. 4D–E)
- **Joint LoRA** (one adapter trained on all subjects) works best at small rank: r = 2 gives WER 0.43. At higher ranks it overfits the roughly 2.7k unique sentences.
- **Per-subject and soup adapters** improve smoothly as the rank grows. The soup is best at r = 128, with WER 0.43, and trains faster.
- The **soup keeps improving with LLM size** (Qwen3 0.6B → 1.7B → 4B, then LoRA on all layers), while joint training plateaus around WER 0.41.
- The final v2 model uses Qwen3-4B with soup adapters at r = 128 on all linear layers. The released code instead uses a single TinyLlama adapter at r = 2 ([code](../sources/brain2qwerty-code.md)).

Related: [NeuroLLM](neuro-llm.md)
