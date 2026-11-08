---
title: "Case study: SGLang (open-source growth)"
type: source
tags: [open-source, growth, case-study, benchmarks, governance, llm-serving]
sources: [case-study-sglang]
updated: 2026-11-08
---

# Case study: SGLang

## Citation and links
- **Project:** SGLang, a fast serving engine for LLMs. https://github.com/sgl-project/sglang
- **Paper:** Zheng, Sheng, Stoica, Gonzalez et al., "SGLang: Efficient Execution of Structured Language Model Programs". arXiv 2312.07104, NeurIPS 2024.
- **Licence:** Apache-2.0.
- **Raw source:** none saved in `references/`. This page summarises a verified web-research report (2026-11-08). Numbers are as of 2026-11-08.
- **Key links:**
  - v0.2 blog post: https://lmsys.org/blog/2024-07-25-sglang-llama3/
  - PyTorch Ecosystem: https://pytorch.org/blog/sglang-joins-pytorch/
  - RadixArk valuation: https://techcrunch.com/2026/01/21/sources-project-sglang-spins-out-as-radixark-with-400m-valuation-as-inference-market-explodes
  - RadixArk seed round: https://siliconangle.com/2026/05/05/nvidia-amd-back-100m-round-ai-tooling-startup-radixark/

## TL;DR
A research group built SGLang to fill a clear technical gap. A paper and reproducible benchmarks gave it credibility. Day-0 support for new models (DeepSeek V3/R1) gave it the largest growth. Hardware partners own their backends. The project stays non-profit (LMSYS), and a separate company (RadixArk) employs maintainers.

## Numbers
| Item | Value |
|---|---|
| Stars | 38,583 |
| Forks | 10,270 |
| Contributors | About 2,224, including anonymous ones (the API under-counts named accounts) |
| First commit | 2023-10-09, by Ying Sheng |
| Repo public | 2024-01-08 |
| Latest release | v0.5.23, 2026-11-02 |
| Releases in the last 12 months | About 33 |
| Star curve | About 2.6k (Jun 2024), 6.5k (Dec 2024), about 29k (Jun 2026). **UNVERIFIED** |

## Origin
- Authors: Lianmin Zheng, Ying Sheng, Ion Stoica, Joseph Gonzalez and others. They work at LMSYS / Berkeley Sky Computing Lab and Stanford.
- The paper introduces RadixAttention and a compressed FSM. It reports up to 6.4× throughput.
- It filled a gap between two incumbents:
  - vLLM was easy to use, but it reused prefixes poorly for multi-call LLM programs.
  - TensorRT-LLM was fast, but it was NVIDIA-only and hard to use.

## Growth timeline
| Date | Event |
|---|---|
| 2023-10 | First commit |
| 2023-12 | Paper on arXiv (2312.07104) |
| 2024-01 | Repo public |
| 2024-07 | v0.2 blog post: up to 3.1× vLLM on Llama-70B |
| 2024-12 → 2025-01 | Day-0 support for DeepSeek V3/R1. The sharpest star jump |
| 2025-03 | Joins the PyTorch Ecosystem. xAI serves Grok 3 on it. Azure serves DeepSeek on AMD with it. 300+ contributors |
| 2026-01 | Spin-out company RadixArk. About $400M valuation reported |
| 2026-05 | RadixArk $100M seed, led by Accel and Spark, with NVIDIA and AMD |
| 2026-11-12 → 13 | First SGLang Summit |

## Adoption drivers
1. **Reproducible benchmarks** with each release, against the incumbents.
2. **Day-0 model support**, built together with the model labs.
3. **An OpenAI-compatible API**, with a one-line install and launch.
4. **Academic credibility**: NeurIPS and the LMSYS brand.
5. **Partner-owned backends**: AMD, NVIDIA and NPU makers own their directories in CODEOWNERS. They run their own nightly CI.
6. **Talks and meetups.**

## Community and governance
- A detailed CODEOWNERS file.
- Release notes credit every contributor and every new contributor.
- AI-tool subscriptions for long-term contributors.
- Slack, a weekly dev meeting and weekly office hours.
- Quarterly public roadmap issues.
- Heavy CI on donated hardware.
- **No documented governance.**

## Money
- SGLang stays Apache-2.0 under the non-profit LMSYS.
- RadixArk employs maintainers. It sells hosted services and RL services.

## Criticisms and limitations
| Criticism | Note |
|---|---|
| Benchmark disputes | Some comparisons were not apples to apples. Fix: publish exact configs and invite rivals to rerun them. |
| Issue backlog | About 6.5k open issues. |
| Self-reported adoption | Claims such as "400k GPUs" are **UNVERIFIED**. |
| Neutrality risk | A VC-backed company now employs the maintainers. |
| Governance | No documented governance. |

## Lessons for Fidetype
1. **Fill one clear gap and measure it.** SGLang showed a number (throughput) against named incumbents. For us the number is calibration, abstention quality and effective WPM against plain decoders.
2. **Benchmarks must be reproducible.** Publish the exact configs with each release. Invite rivals to rerun them. This prevents most disputes.
3. **Day-0 support is the growth engine.** For us this means support for each new BCI dataset or decoder paper on the day it comes out.
4. **Let partners own their part.** Decoder labs and device makers can own their adapters in CODEOWNERS and run their own CI.
5. **A paper gives credibility.** Paper 1 is our equivalent of the NeurIPS paper.
6. **Keep the project neutral before a company exists.** LMSYS (non-profit) came first; RadixArk came later.
7. **Write governance early.** SGLang has none. That is a weak point we can avoid at low cost.

> **Our take:** SGLang is the closest model for our first two years. It is a research-lab project that won by numbers and speed, not by marketing. But its field is far larger than BCI, so its star counts are not a target for us.

## Feeds
- [Open-source growth playbook](../questions/open-source-playbook.md)
- Other case studies: [LangChain](case-study-langchain.md), [OpenTelemetry](case-study-opentelemetry.md)
