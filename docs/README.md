# Fidetype documentation

How to install, use and extend Fidetype: the toolkit that turns brain and muscle signals into text, with a trust layer that types a word only when it is sure.

**Status:** Alpha. The NTS format and conformance suite: Release Candidate. Pretrained decoders: Development ([status levels](glossary.md#status-levels))

Fidetype is research software. **It is not a medical device.** Every page here is plain Markdown. The same pages make the [documentation site](https://zhangzibo.github.io/fidetype/docs/). Words that you may not know are in the [glossary](glossary.md).

## Get started

Pick your role. Each path needs no hardware: the first steps use synthetic or public data.

| You are | You want to | Start here | Then |
|---|---|---|---|
| Researcher | Decode public BCI datasets, measure decoders, compare results | [Getting started](getting-started.md) | [Pretrained decoders](pretrained-decoders.md), [benchmark](../benchmark/README.md), [tutorials](tutorials.md) |
| App builder | Put a decoder in an app and type only text that you can trust | [Trust quickstart](trust-quickstart.md) (10 minutes) | [Guarantee sheet](trust-guarantee.md), [live demo](demo.md), [live decode](live-decode.md) |
| Contributor | Write a producer or consumer, add a device, change the format | [Getting started](getting-started.md) | [Conformance](conformance.md), [adapters](adapters.md), [CONTRIBUTING.md](../CONTRIBUTING.md) |

## Concepts

| Page | What it explains |
|---|---|
| [Concepts](concepts.md) | The NTS data model, profiles, bindings, the trust layer, conformance, the Collector |
| [Glossary](glossary.md) | Every term in plain words, and the status levels |
| [Safe WPM](safe-wpm.md) | The headline metric: words per minute that the system types right by itself, at a certified wrong-commit rate |
| [Trust guarantee](trust-guarantee.md) | What the trust guard promises, under which assumptions, and how to read the audit log |
| [Provenance and privacy](provenance-and-privacy.md) | The lineage of each output, licence flags, consent references, deletion on request |

## How-to guides

| Task | Page |
|---|---|
| Add the trust layer to your own decoder | [Trust quickstart](trust-quickstart.md) |
| Load a pretrained decoder for a public dataset | [Pretrained decoders](pretrained-decoders.md) |
| Decode a live signal (LSL, BrainFlow / OpenBCI, a file or a synthetic source) | [Live decode](live-decode.md) |
| Check which devices, files and datasets work | [Device support](device-support.md), [adapters](adapters.md) |
| Show trust decisions in the browser | [Live demo](demo.md) |
| Keep one trust profile per user and detect drift | [Trust personalisation](trust-personalisation.md) |
| Run inputs, trust and outputs as one service | [Collector](collector.md) |
| Use another language than English | [Language support](language-support.md) |
| Score a decoder and submit a result | [Benchmark](../benchmark/README.md), [tracks](benchmark-tracks.md), [submission](benchmark-submission.md) |
| Test whether a decoder invents text | [Hallucination benchmark](hallucination-benchmark.md) |
| Use TypeScript or Rust | [SDKs](sdks.md), [TypeScript](../sdk/typescript/README.md), [Rust](../sdk/rust/README.md) |

## Tutorials

[Tutorials](tutorials.md): three 10-minute tutorials, each a tested script on a laptop CPU, no hardware.

1. [Decode text with a pretrained decoder](tutorials-01-decode.md)
2. [Add the trust guard and read the safe WPM](tutorials-02-trust.md)
3. [Score a decoder on the benchmark](tutorials-03-benchmark.md)

## Reference

| Page | Content |
|---|---|
| [Specification](../spec/README.md) | All NTS spec versions; the current draft is [NTS 1.0 RC4](../spec/nts-1.0-rc4.md). The spec is normative: if a page here disagrees with it, the spec is right |
| [Proposals (FEPs)](../spec/README.md#proposals-feps) | Enhancement proposals and how to write one |
| [Semantic conventions](semconv.md) | The registry of standard key names: types, units, requirement levels, stability |
| [Conformance](conformance.md) | The conformance kit, `nts-conform`, implementation levels, the self-certification list |
| [SDKs](sdks.md) | The Python, TypeScript and Rust SDKs side by side, and the Python API guide |
| [Command line](getting-started.md#command-line-summary) | The `fidetype` commands |
| [Changelog](../CHANGELOG.md) | What changed in each release |

## Status of the parts

The same levels as the [README status table](../README.md#status):

| Part | Status | Install |
|---|---|---|
| Trust layer | Alpha | in the Python package |
| Python SDK `fidetype` | Alpha | `pip install fidetype` |
| TypeScript SDK `@fidetype/sdk` | Alpha | `npm install @fidetype/sdk` |
| Rust SDK `fidetype` (crate, `no_std` core) | Alpha | `cargo add fidetype` |
| Collector | Alpha | in the Python package |
| Benchmark and leaderboard | Alpha | in the Python package |
| NTS format and conformance suite | Release Candidate. 1.0 RC4 is a draft for public comment | [spec](../spec/README.md) |
| Pretrained decoders | Development. The loader and model cards work; the weights are not downloadable yet | in the Python package |
| C SDK | Planned after NTS 1.0 (embedded devices, FFI). Not started | — |
| Medical use | None. Fidetype is not a medical device | — |

What works and what does not, with the research evidence: [research status](../RESEARCH.md).

## Design records

These pages record designs and the decisions behind them. They are not user guides.

| Page | Content |
|---|---|
| [Benchmark hub design](hub-design.md) | The versioned dataset registry and replay adapters |
| [Safe WPM v0.2 proposal](safe-wpm-v0.2-proposal.md) | Prefix credit, speech time and reading cost (adopted 2026-11-22) |
| [Archive](archive/) | Old records, kept for history |

## For maintainers

| Page | Content |
|---|---|
| [Releasing](RELEASING.md) | Versioning policy and the release checklist of each SDK |
| [Publishing checklist](publishing-checklist.md) | The first public release, step by step |
| [Governance](../GOVERNANCE.md), [Contributing](../CONTRIBUTING.md), [Security](../SECURITY.md) | Decision process, how to contribute, how to report a vulnerability |

## Writing rules for these pages

- Start each page with one sentence that says what it gives the reader, then a status line.
- Write "80% ASD-STE100": short sentences, active voice, one idea per sentence, simple words. Keep exact technical terms. Define a term on first use or link it to the [glossary](glossary.md).
- Show only commands that work today. CI runs most of them.
- Link to the spec for rules. Do not copy rule text here, so the two cannot disagree.
- No internal task codes, issue numbers or calibration-run ids in user pages. Link the internal record instead ("Details: ..."). CI checks this: `node tools/hygiene/wording.js`.
- Prefer a table or a diagram to long prose.
