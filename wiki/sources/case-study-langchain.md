---
title: "Case study: LangChain (open-source growth)"
type: source
tags: [open-source, growth, case-study, open-core, funding, llm-frameworks]
sources: [case-study-langchain]
updated: 2026-11-08
---

# Case study: LangChain

## Citation and links
- **Project:** LangChain, a framework for LLM applications. https://github.com/langchain-ai/langchain
- **Licence:** MIT (the library). LangSmith is a paid product.
- **Raw source:** none saved in `references/`. This page summarises a verified web-research report (2026-11-08). Numbers are as of 2026-11-08.
- **Key links:**
  - Star growth in 2023: https://star-history.com/blog/best-of-2023
  - Seed round: https://www.langchain.com/blog/announcing-our-10m-seed-round-led-by-benchmark
  - Series B: https://blog.langchain.com/series-b
  - Criticism (Octomind, Jun 2024): https://octomind.dev/blog/why-we-no-longer-use-langchain-for-building-our-ai-agents

## TL;DR
LangChain was a side project that arrived about 5 weeks before ChatGPT. It grew by integrations, speed and the founder's constant posting. It became an open-core company: the free library creates a need, and the paid LangSmith meets it. Its main weakness was too much abstraction and churn. The team answered with a package split, LangGraph and a 1.0 rewrite.

## Numbers
| Item | Value |
|---|---|
| Stars | 149,213 |
| Forks | 25,097 |
| Contributors | About 3,751, including anonymous ones |
| Repo created | 2022-10-17 |
| First commit | 2022-10-24, by Harrison Chase |
| Stars gained in 2023 | About 70k |
| Integrations | "1000+" (self-claimed) |
| Developers | Over 1M (self-claimed, Oct 2025) |
| Monthly downloads | 80M (self-claimed, Oct 2025) |

### Funding
| Round | Amount | Lead | Date |
|---|---|---|---|
| Seed | $10M | Benchmark | Apr 2023 |
| Series A | $25M | Sequoia | Feb 2024 |
| Series B | $125M, $1.25B valuation | IVP | Oct 2025 |

## Origin
- A side project. It pulled out common patterns that the founder saw at meetups.
- It was built in about a week and launched with a Twitter thread.
- ChatGPT came out about 5 weeks later. LangChain was already there.

## Growth timeline
| Date | Event |
|---|---|
| 2022-10 | Repo created, first commit, Twitter launch |
| 2023 | Company formed. LangChain.js. LangSmith beta. About 70k stars gained |
| 2023-12 | Split into core, community and partner packages |
| 2024 | LangGraph. LangSmith GA |
| 2025-10 | 1.0. Series B |

## Adoption drivers
1. **Integrations first.** Each vendor promoted the project to its own users.
2. **Speed.** Support for new APIs within days.
3. **The founder's constant posting on X.**
4. **Templates and recipes.**
5. **Hackathons and ambassadors.**
6. **"Standard abstraction" positioning.**

## Community and governance
- Company-led. The company owns the repo and the roadmap.
- The partner packages let vendors maintain their own integrations.

## Money
- **Open core.** The MIT library is free.
- The paid LangSmith does tracing, evals and deployment. It also works without the framework.
- The library creates the pain (debugging LLM chains). The paid tool solves it.

## Criticisms and limitations
- Too much abstraction.
- Hidden prompts.
- Breaking changes.
- Dependency bloat.
- Public example: "Why we no longer use LangChain" by Octomind, Jun 2024.

**The team's response:**
- the package split (core, community, partners);
- LangGraph, a low-level runtime;
- a 1.0 rewrite with no hidden prompts;
- unified docs.

## Lessons for Fidetype
1. **Integrations first.** Adapters for LSL, BIDS and existing decoder outputs bring users who already have data.
2. **Speed matters.** Support new datasets and papers fast.
3. **Recipes beat reference docs.** A "10-line recipe" shows the value at once.
4. **Open core works when the paid part solves a real pain.** For us: hosted trust and audit dashboards, clinical compliance reports.
5. **Do not copy the churn.** Use semver from day one. Keep the core API small and stable.
6. **No hidden magic.** In a medical-adjacent field, every prompt, threshold and decision must be inspectable.

> **Our take:** We copy LangChain's business model and its integrations-first growth, but not its engineering style. A trust layer that hides its own logic would contradict its purpose.

## Feeds
- [Open-source growth playbook](../questions/open-source-playbook.md)
- Other case studies: [SGLang](case-study-sglang.md), [OpenTelemetry](case-study-opentelemetry.md)
