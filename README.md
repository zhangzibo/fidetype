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

**Status (2026-11-19): first results, not answers.** All results below are pre-registered replays on public, offline data (mainly the T12 and T15 implant datasets). They are **not user studies**. Negative results are kept. The evidence is in the [result write-ups](wiki/questions/north-star.md#frontier-result-write-ups-p15-12-2026-11-18).

| Pillar | First results | Not run yet or open |
|---|---|---|
| **F1** | The default-deny update gate passes G1–G6: it refuses worse and broken decoders under partial feedback, which the earlier gate did not ([E2 write-up](wiki/questions/frontier-e2-self-teaching.md)). The same-decoder re-calibration rule passes R1–R7: 0 of 8 re-calibrations refused, every broken or worse decoder still refused ([P15-24 results](experiments/2026-11-18-p15-24-recal-rule/results.md)). The wrong-commit bound holds with feedback on shown items only, and an audit of other thresholds has 0 / 200 violations ([online guarantees](wiki/questions/frontier-f1-online-guarantees.md)). | The full GPU runs of E2 (P15-03). The weak decoders give few commits, so some results are safe but not yet useful. |
| **F2** | LLM rescoring lowers WER on T15. The grounding check stops every swapped-signal commit. A certified fluent-wrong bound commits 36 sentences on T15 (34 right). This guard is the first system to pass all tracks of hallucination protocol 0.2 ([E3 write-up](wiki/questions/frontier-e3-hallucination.md)). LLM rescoring plus a learned commit score also passes protocol 0.2 ([P15-22 results](experiments/2026-11-19-p15-22-llm-learned/results.md)). | E3 **fails** its main pre-registered rule (S4: fluent-wrong commits not above the n-gram arm). The WER gain does not replicate on T12. The safe-WPM result is above gaze typing on T15 on average, but not reliably once the calibration variation is counted (5.18 [0.00, 6.99], [P15-29 results](experiments/2026-11-20-p15-29-calibration-ci/results.md)). It is not above gaze typing on T12 ([P15-26 results](experiments/2026-11-19-p15-26-replication/results.md)). With the learned commit score, the fluent-wrong rate is not certified (gap 74). |
| **F3** | First test done (E1a, [results](experiments/2026-11-19-p15-08-e1-cross-body/results.md)). With all 506 labelled minutes of Willett handwriting, a trunk pretrained on EMG (our P11-01 decoder) trains reliably (CER 0.360 / 0.431 on 2 seeds), where random init fails on one seed and text-only pretraining fails on both. This is descriptive, not the pre-registered question. | The pre-registered F3 question **fails**: with 3 to 100 labelled minutes no arm reads the implant signal (best CER 0.767), and the EMG trunk does not beat text-only pretraining. "A new sensor with minutes of data" is not supported yet (next: a low-data recipe, P15-33). |

Safe WPM (words per minute that the guard commits right) is the user-value test. Under the adopted metric `safe-wpm/0.1`, LLM rescoring plus a learned commit score gives **4.91 [4.25, 5.57]** on T15 with one calibration draw, certified and pre-registered ([P15-22 results](experiments/2026-11-19-p15-22-llm-learned/results.md)). This interval resamples only the test trials. It does **not** include the variation between calibration draws. P15-29 measured that variation with 40 calibration draws, pre-registered ([P15-29 results](experiments/2026-11-20-p15-29-calibration-ci/results.md)). With it, T15 gives **5.18 [0.00, 6.99]**. So the result is above the no-BCI gaze-typing reference (4.02) on average, but **not reliably**: the interval contains 4.02. 2 of the 40 draws are above alpha on the test set and earn 0 by the pre-registered rule. The 38 certified draws give 3.50–6.82, and 36 of the 40 draws are above 4.02. Two variants that were not pre-registered also have a lower end below 4.02 (5.52 [3.61, 7.11] and 5.45 [3.60, 7.01]). The earlier best v0.1 value was 2.64. On T12 it is **not** above gaze typing: 2.37 [1.34, 3.62] against 4.11 ([P15-26 results](experiments/2026-11-19-p15-26-replication/results.md)), and 1.05 [0.00, 3.18] with calibration draws, because the T12 decoder is too weak (35 / 400 top-1 exact). The EMG result of P11-14 is 6.80 [4.49, 9.63] with one calibration draw ([results](experiments/2026-11-20-p11-14-emg-lm-confidence/results.md)). P11-17 counted the calibration draw (40 draws, pre-registered, [P11-17 results](experiments/2026-11-21-p11-17-emg-calibration-ci/results.md)): EMG gives **5.00 [0.00, 9.55]**. So the EMG result is also above the no-BCI reference (3.09) on average, but **not reliably**: 9 of the 40 draws are above alpha on the test set and earn 0 by the pre-registered rule. Limits: offline replay of public data, not a user study. Under `safe-wpm/0.2` with a reading cost, a hybrid guard shows the first right word about 5 times sooner (median 2.7 s, against 14.0 s) at 4.89 [4.49, 5.27]. Its WPM gain over the one-commit guard (4.67) is not robust. Streaming commits alone give less (2.34) ([P5-28 results](experiments/2026-11-19-p5-28-hybrid-prefix/results.md)). **v0.2 is PROPOSED, not adopted** ([safe WPM write-up](wiki/questions/frontier-safe-wpm.md)). The trust layer, the decoders and NTS below are the foundation of this work.

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
| Devices | Which devices, recording files and public datasets work, on what data each adapter ran, known limits. Generated from the adapter metadata | [Device support matrix](docs/device-support.md) |

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

**Pretrained decoders** (load, decode, NTS out; [docs](docs/pretrained-decoders.md)). The weights are not in the package and not hosted yet: put the release files in the cache folder that `fidetype decoders path` shows, or pass `weights=<folder>`.

```python
import fidetype.pretrained as ftp                         # same as fidetype.decoders.load

m = ftp.load("t15-m4-13")                                 # T15 speech (CC0 data); SHA-256 checked
streams = m.decode_file("t15.2023.08.13/data_val.hdf5")   # Brain-to-Text '25 file -> one NTS stream per trial
print(m.decide(streams[0]).action)                        # one guard call for every model: commit / offer / withhold
```

`fidetype decoders list` shows the models and their licence flags. A research-only model (emg2qwerty, CC BY-NC-SA 4.0) loads only with `accept_research_only=True`.

**TypeScript** (Node 18 or later; zero runtime dependencies):

```sh
cd sdk/typescript && npm ci && npm run build && npm test && npm run conformance
```

**Rust** (1.81 or later; `no_std` + `alloc` core):

```sh
cd sdk/rust && cargo test && cargo run --bin fidetype-rs -- conformance
```

Next steps: [Getting started](docs/getting-started.md) (emit a stream from your decoder, run the trust layer), the [10-minute tutorials](docs/tutorials.md) (decode with a pretrained decoder, add the trust guard and read the safe WPM, score a decoder on the benchmark; CPU only, synthetic mode needs no download) and the [SDK guides](docs/sdks.md).

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
