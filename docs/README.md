# Fidetype documentation

This folder holds the user documentation of NeuralTextStream (NTS) and Fidetype. The normative text is the spec in [`../spec/`](../spec/README.md). These pages explain how to use it.

The sections follow the plan for the future documentation site ([docs site plan](../wiki/questions/docs-site-plan.md), roadmap task P8-05). That site is not built yet. Each page here is plain Markdown, so the site can use it later without changes.

## Contents

| Section | Page | What it gives you |
|---|---|---|
| Get started | [getting-started.md](getting-started.md) | Install from a clone, run the demo, emit your first stream, run the trust layer |
| Live demo | [demo.md](demo.md) | One command: recorded decoder output replayed in the browser, each trust decision visible |
| Concepts | [concepts.md](concepts.md) | The NTS data model, profiles, bindings, the trust layer, conformance levels, terms |
| Trust for your decoder | [trust-quickstart.md](trust-quickstart.md), [trust-guarantee.md](trust-guarantee.md) | Add the trust layer to your own decoder in 10 minutes (logits or n-best in; commit / offer / withhold out); what the guarantee covers and how to read the audit log |
| Personalisation | [trust-personalisation.md](trust-personalisation.md) | One trust profile per user (hashed id, no text), anytime-valid drift tests, re-calibration only through the gated update path |
| SDKs | [sdks.md](sdks.md) | The three reference SDKs side by side, and the Python SDK guide |
| SDKs (per language) | [TypeScript](../sdk/typescript/README.md), [Rust](../sdk/rust/README.md) | Full guides of the other two SDKs |
| Collector | [collector.md](collector.md) | Run the Collector: receivers, processors, exporters, configuration |
| Conformance | [conformance.md](conformance.md) | Check a producer or a consumer; profiles and golden vectors |
| Semantic conventions | [semconv.md](semconv.md) | The registry of standard key names (`meta`, `trust_decision` objects): types, units, requirement levels, stability |
| Benchmark | [../benchmark/README.md](../benchmark/README.md) | Score neural text entry on public datasets; submit a result |
| Safe WPM | [safe-wpm.md](safe-wpm.md) | The headline metric: words per minute that the system types right by itself, at a certified wrong-commit rate |
| Hallucination benchmark | [hallucination-benchmark.md](hallucination-benchmark.md) | Null, scrambled and swapped-signal tracks and the fluent-wrong metric: does your decoder invent text? |
| Specification | [../spec/README.md](../spec/README.md) | All spec versions; the current draft is [NTS 1.0 RC4](../spec/nts-1.0-rc4.md) |
| Proposals (FEPs) | [../spec/README.md#proposals-feps](../spec/README.md#proposals-feps) | Enhancement proposals and how to write one |
| Releasing | [RELEASING.md](RELEASING.md) | Versioning policy and the release checklist of each SDK (maintainers) |
| Project | [../GOVERNANCE.md](../GOVERNANCE.md), [../CONTRIBUTING.md](../CONTRIBUTING.md) | Governance, decision process, how to contribute |

## Status in one table

| Part | State |
|---|---|
| NTS spec | 0.1 is the current release (Development). 1.0 RC4 is a **draft** for public comment |
| Python SDK `fidetype` | Reference SDK, trust layer, Collector, adapters. Version 0.0.1, **not on PyPI yet** |
| TypeScript SDK `@fidetype/sdk` | Ready, **not on npm yet** |
| Rust SDK `fidetype` (crate) | Ready (`no_std` core), **not on crates.io yet** |
| C SDK | Planned **after** NTS 1.0 (for embedded devices and FFI). Not started |
| Medical use | None. Fidetype is research software, not a medical device |

## Writing rules for these pages

- Write "80% ASD-STE100": short sentences, active voice, one idea per sentence, simple words. Keep exact technical terms.
- Show only commands that work today. CI runs most of them.
- Link to the spec for rules. Do not copy rule text here, so the two cannot disagree.
- Prefer a table or a diagram to long prose.
