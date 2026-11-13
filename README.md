# Fidetype

![tests](https://github.com/zhangzibo/fidetype/actions/workflows/tests.yml/badge.svg)

**An open trust layer for neural text entry: calibrated, abstaining, hallucination-aware BCI text decoding.**

**Name:** *fides* (Latin: trust) + type.

> Status: research software, v0.0.1 (pre-alpha). The NeuralTextStream spec v0.1, the trust core, the streaming trust layer, the conformance suite, the open benchmark, LSL input and a Python SDK with an offline demo exist. The API can still change.

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
| M6–M7 | Device adapters (LSL input done), SDK + offline demo (done 2026-11-12), pilots | In progress |

- Full plan: [wiki/questions/project-plan.md](wiki/questions/project-plan.md).
- Actual progress: [wiki/progress/index.html](wiki/progress/index.html) (a generated dashboard; it also opens through `node tools/serve.js`).

## Quick start
You need Python 3.12. Install from a clone (the package is not on PyPI yet):

```sh
pip install .                 # or: uv sync --extra dev   (adds pytest; then: uv run pytest -q)
fidetype demo                 # offline demo: the trust layer on synthetic decoder streams (about 30 s)
fidetype demo --fast --html demo.html   # no waiting; also write the static demo page
```

The demo needs no data and no network. It shows the trust layer commit, offer and abstain phrase by phrase. It also shows the key safety result: on a flat (no-signal) stream the decoder's language model still writes fluent text, "always commit" types it, and the trust layer abstains. A prebuilt page is in [demo/index.html](demo/index.html) (open it in a browser; no server).

### Emit a stream from your decoder, run the trust layer
Your CTC decoder gives one row of log-probabilities per frame over `fidetype.VOCAB` (blank first). Write the rows as a NeuralTextStream, check it, and feed it to the streaming trust layer:

```sh
fidetype demo --write-streams demo-streams    # gives demo-streams/trust-config-demo.json (a frozen config)
```

```python
import fidetype
from fidetype.demo import build_decoder, make_stream   # stand-ins for your decoder

log_probs = make_stream("the boy found a red box", "strong", seed=0).log_probs   # (T, V) from your decoder
meta = fidetype.stream_meta(modality="eeg", decoder_name="my-ctc", decoder_version="1.0")
with fidetype.open_stream("utt.jsonl", "w", source="my-ctc", meta=meta, frame_period=0.04) as w:
    for i, row in enumerate(log_probs):
        w.frame(0.04 * i, row)                 # or w.frame(t, logits=raw_scores)
print(fidetype.validate("utt.jsonl").level)    # "trust-ready"

config = fidetype.FrozenTrustConfig.load("demo-streams/trust-config-demo.json")
layer = fidetype.TrustLayer(config, decode_fn=build_decoder())   # the decoder the config was fitted with
for event in fidetype.open_stream("utt.jsonl"):
    for d in layer.push(event):
        print("final" if d.final else "preview", d.action.value, d.shown)
```

A frozen configuration is valid only with the `decode_fn` it was fitted with (the demo config: the demo beam search + LM). With another decoder its guarantee does not hold. For real use, fit your own configuration on labelled calibration data of the same user: `fidetype.calibrate(streams, texts, decode_fn).save("trust.json")`. More: [examples/](examples/) (CTC log-probs, hypothesis-only stream, streaming trust, LSL bridge) and the SDK page [wiki/concepts/python-sdk.md](wiki/concepts/python-sdk.md).

### Command line
```
fidetype validate FILE [--level trust-ready]       conformance check (= python -m fidetype.conformance check)
fidetype trust --config trust.json FILE            trust_decision JSON Lines (= python -m fidetype.trust.streaming replay)
fidetype demo [--fast] [--html F] [--json F]       offline demo
fidetype conformance | lsl | benchmark | ledger    the full tools; the python -m entry points still work
fidetype lsl run|replay-to-lsl|list                LSL input -> trust_decision JSON Lines (needs the [lsl] extra)
fidetype lsl brainflow-bridge --board synthetic    BrainFlow board -> LSL raw-signal stream (needs [lsl,brainflow])
```

## Repository layout
```
src/fidetype/
  __init__.py public SDK API (lazy imports); api.py, writer.py, cli.py (the `fidetype` command)
  streams/    NeuralTextStream spec, vocabulary, noisy-decoder simulator, test corpus
  trust/      trust core, frozen config, streaming trust layer, provenance ledger
  conformance/ benchmark/ adapters/   conformance suite, open benchmark, adapters (LSL, datasets)
  demo/       offline demo (synthetic streams, frozen demo config, static page)
  eval/       metrics: CER, WER, CTC greedy decode, ECE
demo/         prebuilt static demo page + decision log (`fidetype demo --html`)
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
