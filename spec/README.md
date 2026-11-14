# Fidetype specifications

This folder holds the written specifications of Fidetype. A spec is the normative contract. The Python code in `src/fidetype/` is the reference implementation.

| Spec | Version | Status | What it defines |
|---|---|---|---|
| [NeuralTextStream](neuraltextstream-v0.1.md) | 0.1 | Development | The output of any neural input decoder: a probability distribution over a declared vocabulary at each time frame (the core), plus Development event kinds for decisions, text hypotheses, pointer movement and signal quality |

## Why a written spec
- Any decoder, from any lab or company, can emit the same format.
- Any consumer (the Fidetype trust layer, a UI, a benchmark) can read it without knowing the decoder.
- The spec does not depend on one modality (EMG, EEG, MEG, implants) or one vocabulary (characters, keys, words, phonemes, commands).

The model is OpenTelemetry (a data model plus semantic conventions) and BIDS (80/20, adoption first).

## Conformance
Check a producer or a consumer with the conformance suite (levels core, trust-ready, provenance; each check cites its spec clause):

```bash
python -m fidetype.conformance check my_stream.npz --level trust-ready
python -m fidetype.conformance consumer --cmd "my-reader {path}"   # exit 0 = accept
```

The golden vectors are in [`conformance/v0.1/`](conformance/v0.1/). Details: [wiki/concepts/conformance-suite.md](../wiki/concepts/conformance-suite.md).

The TypeScript SDK ([`sdk/typescript/`](../sdk/typescript/README.md)) runs the same vectors for every profile and gives the same verdict as the Python reference (`npm run cross-check`). The JSON schemas in [`schemas/`](schemas/) are structural; its TypeScript types are generated from them.

Opt-in profiles test draft FEPs on top of v0.1. They do not change the v0.1 levels or vectors:

```bash
fidetype conformance --profile fep-0001     # streaming trust events: vectors in conformance/fep-0001/
fidetype conformance --profile fep-0002     # NTS over LSL: scenario vectors in conformance/fep-0002/
fidetype conformance --profile fep-0003     # output profiles + discrete intent events: vectors in conformance/fep-0003/
fidetype conformance --profile fep-0004     # NTS over WebSocket: scenario vectors in conformance/fep-0004/
```

## Proposals (FEPs)
| FEP | Title | Status | Conformance profile |
|---|---|---|---|
| [0001](feps/0001-streaming-trust-events.md) | Streaming trust events (`segment_end`, evidence fields, decode declaration, `trust_decision`) | Draft | `fep-0001` (40 vectors) |
| [0002](feps/0002-nts-over-lsl.md) | NeuralTextStream over LSL (binding `nts-lsl/0.1`) | Draft | `fep-0002` (31 vectors) |
| [0003](feps/0003-intent-events.md) | Output profiles (core, text, intent, control) and discrete intent events (risk classes, confirmation, undo, `intent_feedback`, intent `trust_decision`) | Draft | `fep-0003` (44 vectors); JSON schemas in `schemas/fep-0003/` |
| [0004](feps/0004-nts-over-websocket.md) | NeuralTextStream over WebSocket (binding `nts-ws/0.1`: framing, `ws_seq` order and gaps, resume, back-pressure, auth hook, decisions channel) | Draft | `fep-0004` (37 vectors) |
| [0005](feps/0005-control-events.md) | Continuous-control events (control profile: `control_declaration` units / frame / rate / uncertainty, `control`, `control_enable`, control `trust_decision` with gain / hold / stop, safety rules) | Draft | `fep-0005` (42 vectors) |

## Stability levels
| Level | Meaning |
|---|---|
| Development | Can change in any release |
| Stable | No breaking change within a major version |
| Deprecated | Still works. Removed after its support window |
| Removed | No longer in the spec |

## How to change a spec
1. Open an issue or a Discussion to test the idea.
2. Copy [`feps/0000-template.md`](feps/0000-template.md) to `feps/NNNN-short-title.md`. Use the next free number.
3. Open a pull request with the FEP. The process is in [GOVERNANCE.md](../GOVERNANCE.md#4-spec-changes-feps).
4. When the FEP is accepted, update the spec, the reference implementation and the changelog in the same release.

## Layout
```
spec/
  README.md                   this file
  neuraltextstream-v0.1.md    the NeuralTextStream spec
  conformance/v0.1/           golden test vectors (manifest.json + small synthetic .npz / .jsonl files)
  conformance/fep-0001/       golden vectors of the opt-in FEP-0001 profile (.jsonl)
  conformance/fep-0002/       golden vectors of the opt-in FEP-0002 profile (LSL scenarios, .json)
  conformance/fep-0003/       golden vectors of the opt-in FEP-0003 profile (.jsonl)
  conformance/fep-0004/       golden vectors of the opt-in FEP-0004 profile (WebSocket scenarios, .json)
  conformance/fep-0005/       golden vectors of the opt-in FEP-0005 profile (.jsonl)
  schemas/nts-v0.1/           JSON schemas (draft 2020-12, structural) of the v0.1 JSON Lines events
  schemas/fep-0001/           JSON schemas of the FEP-0001 objects (segment_end, n-best item, decode_declaration, trust_decision)
  schemas/fep-0003/           JSON schemas (draft 2020-12) of the FEP-0003 objects
  schemas/fep-0005/           JSON schemas (draft 2020-12) of the FEP-0005 objects
  feps/                       Fidetype Enhancement Proposals
    0000-template.md          the template for a new FEP
    0001-streaming-trust-events.md
    0002-nts-over-lsl.md
    0003-intent-events.md
    0004-nts-over-websocket.md
    0005-control-events.md
```
