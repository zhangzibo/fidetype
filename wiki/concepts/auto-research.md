---
title: Auto Research (AI agents optimising the pipeline)
type: concept
tags: [agents, methodology, hyperparameters]
sources: [brain2qwerty-v2]
updated: 2026-11-07
---

# Auto Research

Auto Research means letting AI coding agents edit the codebase and launch experiments to optimise a metric. The idea comes from Karpathy's `autoresearch` (https://github.com/karpathy/autoresearch).

## In Brain2Qwerty v2 ([paper](../sources/brain2qwerty-v2.md), §2.4, §4.3)
- **Setup**:
  - Three independent agents (Cursor running Claude Opus 4.6), each in its own git worktree.
  - The objective was **validation WER on one subject**, starting from a stripped-down config that exposed only 4 hyperparameters.
  - The encoder was frozen, the LLM was Qwen3-0.6B + LoRA, and each agent ran 10 rounds of exactly 50 SLURM jobs on V100s with a 45-minute limit per job.
  - An append-only tracker read validation metrics only, and the agents were told not to look at test data.
- **Baseline**: Optuna TPE over the same 4 parameters with the same budget.
- **Results**:

  | Method | Validation WER (S01) | Test WER (all 9 subjects) |
  |---|---|---|
  | Starting config | 0.45 | — |
  | Optuna | 0.41 | 0.493 |
  | Agent 1 | 0.38 | 0.42 |
  | Agent 2 | 0.36 | 0.45 |
  | Agent 3 | 0.37 | 0.43 |

  The agents' gains **generalised across subjects** (p < 1e-6 against both the starting config and Optuna). Optuna's gain did not generalise: its test WER was no better than the starting config's (p = 0.88).
- **What the agents found**:
  - label smoothing
  - **modality dropout**
  - beam search over the LLM's output
  - a sentence-level CLIP auxiliary loss
  - minimal prompts
- **Failure case**: given an open-ended goal (start from v1 and reach v2-level performance), the agents **failed**. Their large, entangled code changes crashed jobs, and they tended to sit idle instead of iterating.

> **Our take:** This fits our situation, where Claude does the coding: agents do well inside a **tightly constrained search space with a trustworthy validation-only harness**, and poorly on open-ended research. If we use agents for experiments, the human-designed harness (fixed data splits, a held-out test set, a fixed compute budget) is the part that matters most.

Related: [NeuroLLM](neuro-llm.md)
