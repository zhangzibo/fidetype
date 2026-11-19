# Fidetype

![tests](https://github.com/zhangzibo/fidetype/actions/workflows/tests.yml/badge.svg)

**Fidetype** is an open research project toward a brain-computer interface (BCI) that reads language from any body signal, teaches itself from daily use, and provably never puts words in the user's mouth ([where we are going](#where-we-are-going)). Its foundation, available today:

**NeuralTextStream (NTS)** is an open, vendor-neutral format for the output of neural input decoders: text, intents and control signals decoded from brain or muscle signals (EMG, EEG, MEG, implants). **Fidetype** is the project around it: the spec, SDKs, a Collector, a conformance suite and a **trust layer** that decides when decoded text is safe to use.

*Name:* *fides* (Latin: trust) + type.

> **Status:** NTS 1.0 is a **draft release candidate** ([RC4](spec/nts-1.0-rc4.md), open for comment). The Python, TypeScript and Rust SDKs pass the full conformance suite in CI, but **no package is published yet** (version 0.0.1). Fidetype is research software. **It is not a medical device.** APIs can change.

## Where we are going

**North star (2026-11-15):** a BCI that reads language from any body signal, teaches itself from daily use, and provably never puts words in the user's mouth. The long-term goal: a person puts on any sensor (implant, wristband or cap) and communicates at conversation speed within minutes; the system improves every day; it never says what the person did not mean.

Three research pillars lead the work ([north star](wiki/questions/north-star.md), roadmap phase [P15](wiki/questions/roadmap-standard.md#p15-frontier-added-2026-11-15-leads)):

| Pillar | Question |
|---|---|
| **F1** Safe self-improving BCI | Can a decoder learn from the user's accept / reject / correction actions while its stated error bound stays valid through every update? |
| **F2** Faithful language-model decoding | Can a language model improve decoded text while a run-time check, with a stated bound, stops text that the neural signal does not support? |
| **F3** Cross-body language model | Can one shared output space let a new sensor or a new user start with minutes of data? |

**Status (2026-11-18): first results, not answers.** All results below are pre-registered replays on public, offline data (mainly the T12 and T15 implant datasets). They are **not user studies**. Negative results are kept. The evidence is in the [result write-ups](wiki/questions/north-star.md#frontier-result-write-ups-p15-12-2026-11-18).

| Pillar | First results | Not run yet or open |
|---|---|---|
| **F1** | The default-deny update gate passes G1–G6: it refuses worse and broken decoders under partial feedback, which the earlier gate did not ([E2 write-up](wiki/questions/frontier-e2-self-teaching.md)). The same-decoder re-calibration rule passes R1–R7: 0 of 8 re-calibrations refused, every broken or worse decoder still refused ([P15-24 results](experiments/2026-11-18-p15-24-recal-rule/results.md)). The wrong-commit bound holds with feedback on shown items only, and an audit of other thresholds has 0 / 200 violations ([online guarantees](wiki/questions/frontier-f1-online-guarantees.md)). | The full GPU runs of E2 (P15-03). The weak decoders give few commits, so some results are safe but not yet useful. |
| **F2** | LLM rescoring lowers WER on T15. The grounding check stops every swapped-signal commit. A certified fluent-wrong bound commits 36 sentences on T15 (34 right). This guard is the first system to pass all tracks of hallucination protocol 0.2 ([E3 write-up](wiki/questions/frontier-e3-hallucination.md)). | E3 **fails** its main pre-registered rule (S4: fluent-wrong commits not above the n-gram arm). The WER gain does not replicate on T12. |
| **F3** | None. | E1 cross-body pretraining (P15-08) is **not run yet**. |

Safe WPM (words per minute that the guard commits right) is the user-value test. Under the adopted metric `safe-wpm/0.1`, the best value is 2.64, below gaze typing (4.02). Under `safe-wpm/0.2` it is 4.87, but **v0.2 is PROPOSED, not adopted** ([safe WPM write-up](wiki/questions/frontier-safe-wpm.md)). The trust layer, the decoders and NTS below are the foundation of this work.

## Why NTS exists

Text decoders for neural signals now work in research labs. Each lab and each device vendor uses its own output format, so every consumer (an app, a UI, a benchmark, a safety check) must be rewritten for every decoder. Decoders also make errors, and their language models can write fluent text that the person did not intend.

NTS takes the role for neural input that [OpenTelemetry](https://opentelemetry.io/) takes for software telemetry:

| OpenTelemetry has | NTS / Fidetype has |
|---|---|
| A data model and semantic conventions | The NTS data model: frames of probabilities over a declared vocabulary, hypotheses, segments, `meta` conventions ([spec](spec/nts-1.0-rc4.md)) |
| A wire protocol (OTLP) | Bindings: JSON Lines, NPZ, Lab Streaming Layer (LSL), WebSocket |
| SDKs in many languages | Python (reference), TypeScript, Rust (`no_std` core) |
| The Collector (receivers → processors → exporters) | The Fidetype Collector ([FEP-0006](spec/feps/0006-collector.md)) |
| A spec compliance matrix | A conformance suite with golden vectors; all three SDKs must give the same verdict |
| OTEPs (enhancement proposals) | FEPs (Fidetype Enhancement Proposals) |

Who has a reason to use it, and what is built for each audience today: [who uses Fidetype](wiki/questions/who-uses-fidetype.md).

NTS adds one thing that telemetry does not need: a **trust layer**. For each utterance it decides COMMIT, OFFER (show choices), ASK or ABSTAIN, with a calibrated, auditable reason. Every decision is a `trust_decision` event in the same format.

## Architecture

```
 decoder / device            SDK                    Collector                         consumer
 (EMG, EEG, MEG,   ──▶  write NTS events   ──▶  receivers ──▶ processors ──▶ exporters  ──▶  app, UI,
  implant, replay)      (Python / TS / Rust)    file, WS,     validate, trust,  JSON Lines,   benchmark,
                                                LSL           thin, redact      stdout, WS,   decision log
                                                                                LSL
                                     trust layer: COMMIT / OFFER / ASK / ABSTAIN  (trust_decision events)
```

| Part | What it does | Where |
|---|---|---|
| Spec | Defines the events, the bindings, the conformance levels and the trust decision rules | [`spec/`](spec/README.md) |
| SDKs | Write, read and check NTS streams; track trust decisions | [Python](src/fidetype/), [TypeScript](sdk/typescript/README.md), [Rust](sdk/rust/README.md) |
| Collector | One service that wires inputs, processing and outputs from one TOML or JSON file | `fidetype collector` ([guide](docs/collector.md)) |
| Trust layer | Calibration, conformal sets, a hallucination guard and a decision policy | `fidetype.trust` ([concept](docs/concepts.md#trust-layer)) |
| Conformance | Golden vectors and checks for producers and consumers, per profile | [`spec/conformance/`](spec/conformance/) ([guide](docs/conformance.md)) |
| Benchmark | Scores neural text entry from NTS files on public datasets | [`benchmark/`](benchmark/README.md) |

More: [docs/concepts.md](docs/concepts.md) and the [diagram page](wiki/diagrams/index.html) (open it through `node tools/serve.js`).

## Quick start

The packages are not on PyPI, npm or crates.io yet. Use a clone:

```sh
git clone https://github.com/zhangzibo/fidetype.git
cd fidetype
```

**Windows:** some committed result files have long paths. If `git clone` fails with `Filename too long`, clone with `git -c core.longpaths=true clone https://github.com/zhangzibo/fidetype.git`, or clone into a short folder (for example `C:\src`).

**Python** (3.12 or later; the reference SDK, the trust layer and the Collector):

```sh
pip install .                     # or: uv sync --extra dev   (adds pytest: uv run pytest -q)
fidetype demo --fast              # offline demo: the trust layer on synthetic decoder streams
fidetype demo live                # browser demo: replay of recorded decoder output with trust decisions (docs/demo.md)
fidetype conformance --profile fep-0001
fidetype collector --config examples/collector/collector.toml --check
```

**TypeScript** (Node 18 or later; zero runtime dependencies):

```sh
cd sdk/typescript && npm ci && npm run build && npm test && npm run conformance
```

**Rust** (1.81 or later; `no_std` + `alloc` core):

```sh
cd sdk/rust && cargo test && cargo run --bin fidetype-rs -- conformance
```

Next steps: [Getting started](docs/getting-started.md) (emit a stream from your decoder, run the trust layer) and the [SDK guides](docs/sdks.md).

## Documentation

| Read | For |
|---|---|
| [docs/](docs/README.md) | The documentation index: getting started, concepts, SDK guides, Collector, conformance, releasing |
| [spec/nts-1.0-rc4.md](spec/nts-1.0-rc4.md) | The normative NTS 1.0 RC4 draft (rules with stable ids, for example `TD-9`) |
| [spec/README.md](spec/README.md) | All spec versions, FEPs, stability levels, conformance profiles |
| [wiki/](wiki/index.md) | The research knowledge base: sources, concepts, results |
| [Roadmap](wiki/questions/roadmap-standard.md) | Phases P1–P16, from v0.1 to a full standard and the P15 frontier research; live progress on the [dashboard](wiki/progress/index.html) |

## How NTS relates to other projects

| Project | What it is | Relation to NTS |
|---|---|---|
| [OpenTelemetry](https://opentelemetry.io/) | Vendor-neutral telemetry: data model, protocol, SDKs, Collector | The structural model for NTS. No OpenTelemetry code or text is used |
| [Lab Streaming Layer](https://labstreaminglayer.readthedocs.io/) (LSL) | Transport for time series and markers, with clock sync | A transport. NTS defines what goes over it ([FEP-0002](spec/feps/0002-nts-over-lsl.md)) |
| [BCI2000](https://www.bci2000.org/) | A general BCI research platform: acquisition, signal processing, applications | A full system. NTS is only the decoder output contract, so a platform like this can emit it |
| [BIDS](https://bids.neuroimaging.io/) | A storage standard for neuroimaging datasets | Covers recorded data at rest. NTS covers live and replayed decoder output |

## Repository layout

```
spec/         NTS spec (v0.1, 1.0 RC1-RC4), FEPs, proto3 files, JSON schemas, conformance vectors
src/fidetype/ Python reference SDK: streams, trust layer, conformance, collector, adapters, benchmark, demo
sdk/          TypeScript SDK (sdk/typescript) and Rust SDK (sdk/rust)
tests/        Python tests (pytest)
examples/     runnable examples: Python scripts, Collector configs, WebSocket browser page
docs/         user documentation (start at docs/README.md)
benchmark/    open benchmark v0.1: results and leaderboard
demo/         prebuilt static demo page (open in a browser)
experiments/  research experiments: plan.md, results.md and aggregate results per run
papers/       our own papers (paper 1: final draft, waiting for an arXiv endorsement)
wiki/         LLM-maintained research knowledge base, diagrams, progress dashboard
references/   catalogue of third-party sources (the files themselves are not committed)
tools/        build scripts: diagrams, progress dashboard, proto schema, hygiene check
```

## Contributing

- Read [CONTRIBUTING.md](CONTRIBUTING.md): setup, tests, writing style, DCO sign-off.
- Spec changes go through a **FEP**: copy [`spec/feps/0000-template.md`](spec/feps/0000-template.md) and open a pull request. The process is in [GOVERNANCE.md](GOVERNANCE.md#4-spec-changes-feps).
- Comment on the RC with an issue or a Discussion (label `spec-1.0-rc`; name the rule id).
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities as [SECURITY.md](SECURITY.md) says.

## Licence and data rules

- The repository is licensed **Apache-2.0** ([LICENSE](LICENSE)). Committed results that quote CC BY-NC data keep the terms of that data ([LICENSES/DATA.md](LICENSES/DATA.md)).
- The repository contains **no raw recordings, no participant data and no trained weights**. Datasets are download-only from their original sources. Some are CC BY-NC (research only). Details: [LICENSES/DATA.md](LICENSES/DATA.md).
- Fidetype contains no code from Meta's Brain2Qwerty (CC BY-NC 4.0). The project started from that research, but it is independent and **not affiliated with or endorsed by Meta**.
- Cite Fidetype with [CITATION.cff](CITATION.cff).
