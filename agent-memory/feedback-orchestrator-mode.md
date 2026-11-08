---
name: feedback-orchestrator-mode
description: "Main chat is orchestrator only — all real work (writing, code, tool use) goes to subagents"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 19d95f58-e133-4c8d-b470-5e0c39e4120e
  modified: 2026-11-08T07:24:29.842Z
---

The main conversation acts only as the **orchestrator**. It plans, delegates, reviews results, and talks to the user. All actual work goes to subagents (Agent tool): writing files, wiki pages, generating code, running commands, research, web fetches, and edits.

**Why:** On 2026-11-07 the user asked for this to always be the case from then on. Their aim is to keep the main chat focused on oversight and understanding (see [[feedback-output-style]]).
**How to apply:**
- Give each subagent a complete brief: the goal, the files, the conventions in CLAUDE.md, and the output style. Delegate independent tasks in parallel.
- In the main chat, only read subagent reports and summarise them for the user. Do no tool work there yourself, beyond a trivial check of a subagent's result when needed.
- Verify that the reported work happened before you tell the user it is done.
