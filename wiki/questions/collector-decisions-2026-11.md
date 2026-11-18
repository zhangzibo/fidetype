---
title: Collector decisions (2026-11)
type: question
tags: [collector, config, toml, python, rust, decision, roadmap]
sources: []
updated: 2026-11-17
---

# Collector decisions (2026-11)

**Question:** two P3 items waited for a user decision: the collector config format (gap 40 = P3-09) and the language of collector v1 (P3-01). On 2026-11-17 the user gave both decisions to the orchestrator. This page records them.

| # | Item | Decision | Status |
|---|---|---|---|
| 1 | Config format (P3-09, gap 40; P3-01, P3 exit criterion) | **TOML or JSON**, as [FEP-0006](../../spec/feps/0006-collector.md) section 6 says. No YAML. | decided 2026-11-17; P3-09 `done` |
| 2 | Collector v1 language (P3-01) | **Python**. A Rust core can come later. | decided 2026-11-17 |

## Decision 1: TOML or JSON, not YAML

The roadmap said "one YAML config". FEP-0006 section 6 said "TOML and JSON only". The roadmap now follows FEP-0006.

Reasons:
- FEP-0006 made this choice on purpose. A spec decision changes only by a FEP amendment, not by a roadmap line.
- TOML has explicit types. YAML 1.1 parsers change some plain values into other types: `NO` (the country code of Norway) becomes `false`, and `0755` can become an octal number. A config error of this kind is silent.
- TOML is in the Python standard library (`tomllib`, Python 3.11+). YAML needs a new dependency (PyYAML).
- JSON covers configs that a program writes (for example `fidetype.collector.bench`).

Changes:
- [Roadmap](roadmap-standard.md#p3-collector-pipeline): the P3 goal, the P3 exit criterion and the P3-09 item now say "TOML/JSON (FEP-0006)". The tracker title of P3-01 says the same.
- Gap 40 = P3-09 is closed in [open gaps](open-gaps.md).
- No code changes. The collector already reads TOML and JSON (`src/fidetype/collector/config.py`).

> **Our take:** if users ask for YAML later, an optional extra (`fidetype[yaml]`) with a strict loader is possible. It needs a FEP-0006 amendment first.

## Decision 2: Python for collector v1

Reasons:
- The collector, the trust layer, the adapters and the tests exist in Python today.
- Python meets the latency budget. The P3-04 integration test measured p95 added latency of about 1–3 ms for the gated profiles at 50 Hz (budget 50 ms). The B2T '25 replay (P3-08) measured p95 added 2.43 ms.
- A rewrite in Rust now gives no measured gain and delays P3.

Later:
- A Rust core can follow for embedded or on-device use, if a measured need appears. P5-05 (on-device trust core) already plans C or Rust.
- One known slow path is the logits guard with its built-in CTC beam search (p95 104–108 ms, gap 37 = P3-06). The plan for it is incremental decoding, not a language change.

## Related pages
- [Long-term standard roadmap](roadmap-standard.md) (P3)
- [Open gaps](open-gaps.md)
- [Collector](../concepts/collector.md)
- [FEP-0006](../../spec/feps/0006-collector.md)
