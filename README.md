# Fidetype

![tests](https://github.com/zhangzibo/fidetype/actions/workflows/tests.yml/badge.svg)

**An open trust layer for neural text entry: calibrated, abstaining, hallucination-aware BCI text decoding.**

**Name:** *fides* (Latin: trust) + type.

> Status: early research (milestone M0). Only the first component exists today. Most parts below are **planned**.

## What it does
Brain-computer interfaces (BCIs) and other neural input devices (MEG, EEG, wrist EMG, implants) can now decode text. But they make errors. Their AI language models can also write fluent sentences that are wrong. Fidetype sits between any decoder and the user. Its goal is to make the decoded text reliable. When it is complete, Fidetype will:

- calibrate the confidence of the decoder;
- give n-best choices;
- abstain, or ask the user, when it is not sure;
- flag text that the language model invented (hallucinated text);
- work in real time.

Every decoder sends its output in one standard format, the **NeuralTextStream**. So Fidetype does not depend on one device or one decoder.

## Why
Non-invasive text decoders now work in the lab:
- Meta's Brain2Qwerty v1 reaches **29% character error rate (CER) with MEG** ([source notes](wiki/sources/brain2qwerty-v1.md)).
- Brain2Qwerty v2 adds a large language model (LLM). It reaches a mean **word error rate (WER) of 39%** ([source notes](wiki/sources/brain2qwerty-v2.md)).

These error rates are still high. Decoders are often over-confident, so their scores do not show when they are wrong. An LLM can turn a noisy signal into a fluent sentence that the person did not intend. For a patient, a fluent wrong sentence can be worse than no sentence. Fidetype addresses this problem.

## Architecture
Fidetype has six layers, from data in (bottom) to shared infrastructure (top):

1. **Sources / adapters**: dataset replay, a noisy-decoder simulator, and (planned) live devices through Lab Streaming Layer (LSL).
2. **Decoders** (planned): our own conv + CTC decoder with a causal (streaming) mode. Any decoder that emits NeuralTextStream can plug in.
3. **Trust core** (planned): calibration, streaming language-model fusion, conformal sets, a hallucination guard, and a decision policy (commit, offer choices, ask, or abstain).
4. **Interaction** (planned): a UI with confidence and an n-best picker, and a simulated user for offline evaluation.
5. **Evaluation harness**: CER, WER, calibration error (ECE) today; (planned) conformal coverage, latency, hallucination rate and **effective words per minute**.
6. **Infrastructure** (planned): a dataset registry with licence tags and a provenance ledger.

Details: [wiki/questions/architecture.md](wiki/questions/architecture.md).

Diagrams: [wiki/diagrams/index.html](wiki/diagrams/index.html). Open the diagram page through a local server:

```sh
node tools/serve.js        # then open http://127.0.0.1:8000/wiki/diagrams/index.html
```

## Status and roadmap
| Milestone | Content | Status |
|---|---|---|
| M0 | Setup: package, NeuralTextStream spec v0.1, noisy-decoder simulator, metrics (CER, WER, ECE), 41 tests | In progress |
| M1 | Baseline decoder on public MEG data (SpanishBCBL) | Planned |
| M2 | Trust core v0 | Planned |
| M3 | Paper 1: "Calibrated, abstaining brain-to-text", with the new metric effective words per minute | Planned |
| M4 | Paper 2: causal / streaming decoder | Planned |
| M5 | Open benchmark v0.1: harness, fixed splits, leaderboard, licence audit | Done (2026-11-11) |
| M6–M7 | Device adapters, pilots | In progress |

- Full plan: [wiki/questions/project-plan.md](wiki/questions/project-plan.md).
- Actual progress: [wiki/progress/index.html](wiki/progress/index.html) (a generated dashboard; it also opens through `node tools/serve.js`).

## Quick start
You need Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra dev                       # create .venv and install fidetype + pytest
uv run pytest -q                          # run the tests (41 tests)
uv run python examples/simulate_demo.py   # simulate noisy decoders at four error levels
```

Use the simulator from Python:

```python
from fidetype.eval.metrics import cer, ctc_greedy_decode, expected_calibration_error
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig

sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=0)
res = sim.simulate("please close the window before you leave")
hyp = ctc_greedy_decode(res.stream)
print(hyp, cer(res.text, hyp), expected_calibration_error(res.peak_confidence, res.peak_correct))
```

The presets `perfect`, `best`, `median` and `worst` target a CER of 0.00, 0.17, 0.28 and 0.41. A `confidence_temperature` below 1 makes the simulated decoder over-confident.

## Repository layout
```
src/fidetype/
  streams/    NeuralTextStream spec, vocabulary, noisy-decoder simulator, test corpus
  eval/       metrics: CER, WER, CTC greedy decode, ECE
tests/        pytest tests
examples/     small runnable scripts
wiki/         research knowledge base (see "Research notes")
  diagrams/   draw.io diagrams + generated index.html
  progress/   tracker.json + generated progress dashboard
references/   catalogue of raw sources (third-party files are not committed)
tools/        local server, draw.io viewer build, progress dashboard build
notebooks/    experiments
data/         local datasets (git-ignored, never committed)
```

## Open benchmark v0.1
Score neural text entry from NeuralTextStream files, with fixed splits, required controls and eWPM next to a no-BCI reference. Three tracks: SpanishBCBL MEG (research only), Brain-to-Text '25 (CC0), Toronto sEMG (CC BY). No data and no weights are shipped.

```bash
python -m fidetype.benchmark tracks
python -m fidetype.benchmark prepare b2t25-t15-copytask --data t15_copyTask.pkl --out truth.jsonl
python -m fidetype.benchmark score my-submission --truth truth.jsonl --out result.json
python -m fidetype.benchmark leaderboard
```

Leaderboard: [benchmark/site/leaderboard.md](benchmark/site/leaderboard.md) (also `benchmark/site/index.html`). How to submit: [benchmark/README.md](benchmark/README.md). Concept: [wiki/concepts/open-benchmark.md](wiki/concepts/open-benchmark.md).

## Data and licences
- All code in this repository is **Apache-2.0**.
- Some research datasets (SpanishBCBL; emg2qwerty, not used yet) are **CC BY-NC**. We use them for research and benchmarks only. We do not redistribute them. All datasets are download-only: you fetch them from the original source. Details and the M5-03 audit: [LICENSES/DATA.md](LICENSES/DATA.md).
- **Provenance rule:** product model weights come only from CC0 data or from our own consented data. A provenance ledger (planned) records which data trained which weights.
- Meta's Brain2Qwerty code is CC BY-NC. Fidetype contains no Meta code. Our decoder will be our own implementation.

## Research notes
The [wiki/](wiki/) folder is an LLM-maintained knowledge base. It follows Andrej Karpathy's [LLM-wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). The human selects the sources and asks the questions. An LLM agent writes and maintains the pages. Start at [wiki/overview.md](wiki/overview.md) or [wiki/index.md](wiki/index.md).

## Project goals and governance
- **Goal:** become the vendor-neutral standard for the confidence of neural input. Any decoder, on any device, emits one open format. Any consumer can read and check it.
- **Spec:** the NeuralTextStream format is a written spec in [spec/](spec/) (v0.1, Development). Changes go through FEPs (Fidetype Enhancement Proposals).
- **Governance:** founder-led today, with a written path to neutral governance and a foundation home: [GOVERNANCE.md](GOVERNANCE.md).
- **Contribute:** [CONTRIBUTING.md](CONTRIBUTING.md). All participants follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

**Cite:** if you use Fidetype, cite it with the metadata in [CITATION.cff](CITATION.cff) (GitHub shows a "Cite this repository" button).

## Acknowledgements
Fidetype is inspired by Meta FAIR's [Brain2Qwerty](https://facebookresearch.github.io/brain2qwerty/) research. Fidetype is an independent project. It is **not affiliated with or endorsed by Meta**.

## Licence
[Apache License 2.0](LICENSE).
