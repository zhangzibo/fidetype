---
name: project-bci-research-goal
description: "Fidetype (package fidetype, GitHub zhangzibo/fidetype): long-term public BCI project started 2026-11-07 from Meta's Brain2Qwerty; direction = trustworthy neural text entry"
metadata:
  node_type: memory
  type: project
  originSessionId: 19d95f58-e133-4c8d-b470-5e0c39e4120e
  modified: 2026-11-08T06:50:07.157Z
---

The user started stealth-project on 2026-11-07 as a long-term, public brain-computer-interface project. It was inspired by Meta FAIR's Brain2Qwerty (MEG typing decoding, v1 Nature Neuroscience 2026 and v2 preprint). Possible outcomes are research papers or a real-world application. The user first wanted to begin with research, with the direction open. On 2026-11-07 the direction was chosen: **trustworthy neural text entry**, a decoder-agnostic trust layer (calibration, abstention, hallucination checks, provenance) on top of brain-to-text decoders. On 2026-11-08 the user named the project **Fidetype**: package `fidetype`, GitHub repo zhangzibo/fidetype (renamed from stealth-project). The plan targets M0 by 2026-11-09 and M1-M7 by 2026-11-15 (the user's target), tracked in `wiki/progress/tracker.json`.

**Why:** BCI has been a long-held interest. The user thinks it is the next big field after AI and is under-invested.
**How to apply:** Research is kept as a Karpathy-style LLM wiki: the raw sources are in `references/` and the pages I maintain are in `wiki/`. The schema is in `CLAUDE.md`. `references/papers/` and `references/repos/` are git-ignored because of licences. Meta's code is CC BY-NC 4.0, so anything that might go commercial needs its own implementation. Also note the user has no MEG/EEG hardware, so prefer directions that work with public data. The machine has an AMD RX 7800 XT (16 GB, no CUDA, so it needs ROCm), a Ryzen 7 9800X3D, 31 GB RAM and about 1.1 TB free on C:. The user considers this a weak GPU.
