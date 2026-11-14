---
name: feedback-agent-load-limit
description: Parallel subagent limit raised on 2026-11-13 to 4 at once (1 GPU job); timing jobs isolated with CPU pinning instead of serialising
metadata:
  node_type: memory
  type: feedback
  originSessionId: e302da03-a5c8-4516-ad74-22c8d774436b
  modified: 2026-11-14T03:48:31.470Z
---

On 2026-11-13 the user asked to raise the subagent limit and to fix timing interference with better code instead of running fewer agents.

Rule now: at most **4 subagents at once**, at most **1 GPU/heavy training job**. The PC has 31 GB RAM and 16 logical cores, and RAM was never the bottleneck.

**Why:** the old limit (2 at once) slowed the roadmap. The real limits are the single GPU, latency measurements that other jobs distort, and edit clashes in tracker.json/HANDOFF.md.

**How to apply:**
- Run latency/timing experiments pinned to dedicated cores. Run other jobs on the remaining cores with limited threads, through the CPU-isolation helper (once it exists).
- Brief agents to cap their thread counts (OMP/MKL/torch threads) and to edit shared files surgically, or to use per-task tracker fragments if the tooling supports them.

Related: [[feedback-orchestrator-mode]]
