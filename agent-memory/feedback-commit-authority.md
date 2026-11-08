---
name: feedback-commit-authority
description: Claude decides what to commit and push in stealth-project without asking each time; still never commits third-party/data/secret files
metadata:
  node_type: memory
  type: feedback
  originSessionId: 19d95f58-e133-4c8d-b470-5e0c39e4120e
  modified: 2026-11-08T08:00:06.594Z
---

The user gave standing authority on 2026-11-07 ("you can judge what gets committed and pushed"). Claude decides what to commit and push to `main` in stealth-project and does not ask each time.

**Why:** The user does not want a confirmation prompt for every commit. Claude, as the orchestrator, should own repo hygiene.
**How to apply:**
- **Commit and push freely:** wiki pages, diagrams, our own code, configs, docs, and small licensed tools such as the draw.io viewer.
- **Never commit:**
  - third-party PDFs or code (references/papers/, references/repos/)
  - datasets or recordings
  - model weights
  - secrets
  - large binaries
  The repo is public.
- **Still ask first:** history rewrites, force-push, deleting meaningful files, or publishing anything outside this repo.
- **Delegate the work:** the git work itself goes to a subagent, per [[feedback-orchestrator-mode]].
