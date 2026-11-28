# Fidetype

![tests](https://github.com/zhangzibo/fidetype/actions/workflows/tests.yml/badge.svg)

**Open-source toolkit for brain and body-signal typing.**

Fidetype is an open-source toolkit for turning brain and muscle signals (EEG, MEG, EMG and implant recordings) into text. Its **trust layer** types text only when it is confident, and it reports how often it is wrong. It works with your own decoder: you keep your model, and Fidetype decides when its output is safe to use.

Fidetype is research software. It is **not a medical device**. All results so far come from offline tests on public datasets, not from studies with users.

*Name:* *fides* (Latin: trust) + type.

## Install

```sh
pip install fidetype          # Python 3.12+: SDK, trust layer, Collector, benchmark
npm install @fidetype/sdk     # TypeScript SDK (Node 18+ and browsers)
cargo add fidetype            # Rust SDK (no_std + alloc core)
```

## Quick start

Wrap any decoder that gives a ranked list of texts with scores. This example uses a fake decoder, so it needs no data and runs in a few seconds:

```python
import random
import fidetype.trust as ft

PHRASES = ["yes", "no thanks", "i need help", "thank you", "good morning", "open the window"]
rng = random.Random(0)

def my_decoder(meant, signal=True):
    """Stand-in for your decoder: a ranked list of (text, log score)."""
    noise = rng.random() if signal else 1.0
    texts = [meant] + rng.sample([p for p in PHRASES if p != meant], 3) if signal else rng.sample(PHRASES, 4)
    scores = [0.0] + [-6 * (1 - noise) * rng.uniform(0.5, 1.5) for _ in range(3)]
    if rng.random() < 0.3 * noise:
        scores[1] = 0.5                       # a decoder error: a wrong text wins
    return sorted(zip(texts, scores), key=lambda c: -c[1])

meant = [rng.choice(PHRASES) for _ in range(400)]       # labelled calibration data
guard = ft.calibrate([my_decoder(t) for t in meant], meant, alpha=0.05,
                     null_inputs=[my_decoder("", signal=False) for _ in range(100)])
r = guard(my_decoder("i need help"))
print(r.action, r.text)                                 # commit i need help
```

`calibrate` sets the guard so that, with probability at least 1 − `delta` (default 90 %) over the calibration draw, at most `alpha` (here 5 %) of all utterances become wrong commits. The rate is over all utterances, not over commits only: a guard that commits rarely can still have many wrong commits among the few it makes. `calibrate` also refuses guards that commit on no-signal input. Each result is `commit` (use the text), `offer` (show the choices) or `withhold` (show nothing). Next: [add trust to your decoder in 10 minutes](docs/trust-quickstart.md), then [what the guarantee says](docs/trust-guarantee.md).

## Status

| Component | Status | What it does |
|---|---|---|
| **Trust layer** | Alpha | Decides commit, offer or withhold for each utterance, with a stated wrong-commit bound and an audit log |
| **Python SDK** | Alpha | Writes, reads and checks NTS streams; reference for the other SDKs |
| **TypeScript SDK** | Alpha | The same for Node and browsers; passes the full conformance suite |
| **Rust SDK** | Alpha | The same for embedded and native code; passes the full conformance suite |
| **Collector** | Alpha | One service that connects inputs, processing and outputs from one config file |
| **Benchmark** | Alpha | Scores neural text entry from NTS files on public datasets, with a leaderboard |
| **NTS format and conformance suite** | Release Candidate | The NTS 1.0 RC4 draft, open for comment, with test vectors |
| **Pretrained decoders** | Development | The loader and model cards work; the weights are not downloadable yet |

**NTS** (NeuralTextStream) is the open file and stream format that Fidetype uses for decoder output. The six levels (Development, Alpha, Beta, Release Candidate, Stable, Deprecated) are defined in the [glossary](docs/glossary.md#status-levels).

## Who it is for

- **Researchers with a decoder:** add the trust layer to your model output ([trust quickstart](docs/trust-quickstart.md)) and score it on public data ([benchmark](benchmark/README.md)).
- **App builders** (communication aids, text-entry UIs): read NTS streams and act on trust decisions ([getting started](docs/getting-started.md), [SDK guides](docs/sdks.md), [Collector](docs/collector.md)).
- **Contributors:** improve the code, the docs or the spec ([CONTRIBUTING.md](CONTRIBUTING.md), [spec](spec/README.md)).

## Why Fidetype

- **Safe output.** A decoder and its language model can write fluent text that the person did not mean. The trust layer stops it and says how often it fails.
- **Any signal, any decoder.** EEG, MEG, EMG and implants use the same format and the same trust layer, so one app works with every decoder.
- **Honest numbers.** The benchmark reports *safe WPM* (words per minute that the guard commits correctly) next to a no-BCI baseline, with confidence intervals.
- **Open.** Apache-2.0 code, an open spec, and three SDKs that must agree on every conformance test.

## What Fidetype is not

- Not a medical device, and not approved for clinical use.
- Not a decoder you can download today: you bring your own model (pretrained weights are planned).
- Not a dataset host: it ships no recordings and no participant data.
- Not a full BCI platform such as BCI2000: it covers decoder output, trust decisions and scoring.

## How it works

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
| Devices | Which devices, files and public datasets work, and their known limits | [Device support matrix](docs/device-support.md) |

The design follows [OpenTelemetry](https://opentelemetry.io/), which does the same job for software telemetry:

| OpenTelemetry has | NTS / Fidetype has |
|---|---|
| A data model and semantic conventions | The NTS data model: frames of probabilities over a declared vocabulary, hypotheses, segments, `meta` conventions ([spec](spec/nts-1.0-rc4.md)) |
| A wire protocol (OTLP) | Bindings: JSON Lines, NPZ, Lab Streaming Layer (LSL), WebSocket |
| SDKs in many languages | Python (reference), TypeScript, Rust (`no_std` core) |
| The Collector (receivers → processors → exporters) | The Fidetype Collector |
| A spec compliance matrix | A conformance suite with golden vectors; all three SDKs must give the same verdict |
| OTEPs (enhancement proposals) | FEPs (Fidetype Enhancement Proposals) |

### How NTS relates to other projects

| Project | What it is | Relation to NTS |
|---|---|---|
| [OpenTelemetry](https://opentelemetry.io/) | Vendor-neutral telemetry: data model, protocol, SDKs, Collector | The structural model for NTS. No OpenTelemetry code or text is used |
| [Lab Streaming Layer](https://labstreaminglayer.readthedocs.io/) (LSL) | Transport for time series and markers, with clock sync | A transport. NTS defines what goes over it ([FEP-0002](spec/feps/0002-nts-over-lsl.md)) |
| [BCI2000](https://www.bci2000.org/) | A general BCI research platform: acquisition, signal processing, applications | A full system. NTS is only the decoder output contract, so a platform like this can emit it |
| [BIDS](https://bids.neuroimaging.io/) | A storage standard for neuroimaging datasets | Covers recorded data at rest. NTS covers live and replayed decoder output |

## Documentation

- [Documentation index](docs/README.md): getting started, concepts, tutorials, SDK guides, Collector, conformance.
- [Glossary](docs/glossary.md): the terms used in the docs.
- [NTS specification](spec/README.md): all spec versions, enhancement proposals and stability levels.
- [Website](https://zhangzibo.github.io/fidetype/): the docs, the benchmark leaderboard and a demo.

## Research status

Fidetype grew out of research on reading text from brain signals. On public implant and EMG datasets, the trust layer keeps its wrong-commit bound, and it blocks text that the signal does not support. The typing speed gain over a no-BCI baseline is still small and not yet reliable for most setups. Read [RESEARCH.md](RESEARCH.md) for what works, what failed, and the roadmap.

## Contributing

- Read [CONTRIBUTING.md](CONTRIBUTING.md): setup, tests, writing style, DCO sign-off.
- Spec changes go through a FEP: copy [`spec/feps/0000-template.md`](spec/feps/0000-template.md) and open a pull request ([process](GOVERNANCE.md#4-spec-changes-feps)).
- Comment on the spec draft with an issue or a Discussion (label `spec-1.0-rc`; name the rule id).
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities as [SECURITY.md](SECURITY.md) says.

Folders such as `wiki/`, `experiments/` and `papers/` hold internal research records. You do not need them to use Fidetype.

## Licence and data rules

- The code is licensed **Apache-2.0** ([LICENSE](LICENSE)). Committed results that quote CC BY-NC data keep the terms of that data ([LICENSES/DATA.md](LICENSES/DATA.md)).
- The repository contains **no raw recordings, no participant data and no trained weights**. You download datasets from their original sources. Some are CC BY-NC (research only).
- Fidetype contains no code from Meta's Brain2Qwerty (CC BY-NC 4.0). The project started from that research, but it is independent and **not affiliated with or endorsed by Meta**.

## Citation

Cite Fidetype with [CITATION.cff](CITATION.cff) (GitHub shows a "Cite this repository" button).
