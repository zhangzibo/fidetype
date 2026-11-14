---
name: project-spec-docs-style
description: "User wants the NTS spec documentation modeled on mature reference docs (Python docs, the C standard, the OpenTelemetry spec); RC1 page is only a start"
metadata:
  node_type: memory
  type: project
  originSessionId: e302da03-a5c8-4516-ad74-22c8d774436b
  modified: 2026-11-14T18:44:14.221Z
---

On 2026-11-14 the user saw the NTS 1.0 RC1 spec as a rendered page and said the documentation could take its structure and style from Python's documentation, the C standard, or the OpenTelemetry specification, and that the RC1 page "can be a start".

**Why:** the goal is an OpenTelemetry-scale standard. Its documentation must read like a mature reference, not a single long draft file.

**How to apply:** when planning the spec docs site (roadmap P8-05, GitHub Pages + original UI), study how those three docs are organised (separate reference / tutorial / how-to parts, per-section pages, stable anchors, versioned docs) and use their structure. Use their structure only, never their text or branding. Do not start the site without the user's go-ahead; it is roadmap work.

Related: [[project-bci-research-goal]]
