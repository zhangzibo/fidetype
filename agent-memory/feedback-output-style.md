---
name: feedback-output-style
description: "Default output style — explain in ~80% ASD-STE100 (Simplified Technical English); prefer diagrams, HTML pages, explainer videos over plain prose"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 19d95f58-e133-4c8d-b470-5e0c39e4120e
  modified: 2026-11-08T07:16:07.312Z
---

Write explanations "80% of the way to ASD-STE100". The user finds this much easier to read. The rules:
- Short sentences: about 20 words or fewer for procedures, and about 25 for descriptions.
- Active voice.
- One instruction per sentence.
- One meaning per word, using simple common words.
- No idioms or filler.

Don't apply the full spec rigidly; keep precise technical terms where they are needed.

When something is easier to see than to read, go up this ladder of output formats:
1. Diagrams (ASCII or SVG) instead of long prose.
2. An HTML page or artifact for anything substantial or interactive.
3. A bespoke explainer video, 3Blue1Brown-style. Use Manim or similar, with free local TTS unless the user supplies an API key. Offer this for deep topics.

**Why:** The user adopted Karpathy's tips on making LLM output easier to understand as the default. As the LLM does more of the legwork, the user's job moves to oversight and understanding, so readability matters most.
**How to apply:** Use this in every chat explanation and in new [[project-bci-research-goal]] wiki pages. Use visuals proactively. Large, custom, disposable artifacts are encouraged.
