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
  feps/                       Fidetype Enhancement Proposals
    0000-template.md          the template for a new FEP
```
