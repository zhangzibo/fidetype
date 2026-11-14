---
title: NeuralTextStream conformance suite
type: concept
tags: [spec, neuraltextstream, conformance, testing, standard, adapters, provenance]
sources: [brain-to-text-25-copytask, toronto-semg-typing]
updated: 2026-11-12
---

# NeuralTextStream conformance suite

## What it is
The **conformance suite** tests whether an implementation follows the [NeuralTextStream v0.1 spec](../../spec/neuraltextstream-v0.1.md). It has two parts:

- **Producer checks.** Is a stream that an adapter or a decoder emits valid? The suite runs every check on the stream and reports the highest **level** that the stream reaches.
- **Consumer checks.** Does a reader accept the valid streams and reject the invalid ones? The suite has **52 golden test vectors** with expected outcomes.

Every check cites the spec clause that it tests. It is our own code (Apache-2.0): `src/fidetype/conformance/`. The golden vectors are committed in [`spec/conformance/v0.1/`](../../spec/conformance/v0.1/) (`manifest.json` plus small synthetic `.npz` and `.jsonl` files). This is task M5-10. It is the first step of roadmap phase P7 ([roadmap](../questions/roadmap-standard.md)).

## Levels
The levels are cumulative. A stream reaches a level only if it also reaches all lower levels.

| Level | Meaning | What it checks (spec clauses) |
|---|---|---|
| **core** | The stream is valid. A consumer MUST accept it. | All MUST rules: structure (5.1), values and normalisation (5.2), NPZ form (6.1), JSON Lines form (6.2), sparse frames (3.3), types of the defined `meta` keys (4.1, 4.2), `decoder.lookahead_s` = `latency` (4.2), Development events (3.5–3.9). Heuristic leakage (5.3) and privacy (5.4) checks. |
| **trust-ready** | A trust layer can use the stream safely. | `source` names the producer (3.2); `device.modality` (4.2); `decoder.causal` (3.2, 4.2); an offline decoder omits `latency` (3.2); `data.derived = true` (5.4.4); `calibration.applied` agrees with the calibration keys (4.2); text vocabularies state `language` (4.2); a `char` vocabulary has one character per token (3.1). |
| **provenance** | A decision can be traced to the models that made it. | `stream.id` (4.3.1); `decoder.name` and `decoder.version` (4.3.2); `decoder.weights_sha256` (4.2, 4.3.2); `adapter.name` and `adapter.version` together (4.2); `decoder.calibration_id` if calibrated (3.5.3); pseudonymous ids (5.4.2, heuristic). |
| *advisory* | Good practice. A warning only. It never blocks a level. | NPZ dtypes (6.1), namespaced keys (4.1), free-text notes (5.4.3), W3C key codes (3.1), ARPAbet / IPA phonemes (3.1), one-hot rows (2.4.4), `frame_period` agrees with the frame steps (3.2), labels in `vocab` (3.5), lines after `end` (6.2). |

Each check has a keyword: `MUST` or `SHOULD` copies the spec text. `PROFILE` marks a requirement that the suite adds for a level; its clause names the spec text that motivates it. Run `python -m fidetype.conformance list --markdown` for the full list of 60 checks.

> **Our take:** "trust-ready" and "provenance" are profiles, not new spec rules. The spec stays at v0.1 with no breaking change. If the profiles prove useful, a FEP can make them part of the spec.

## How a third party runs it
Install the package (`pip install -e .` in a checkout), then:

```bash
# Producer: check stream files (NPZ or JSON Lines), or a folder of them
python -m fidetype.conformance check my_stream.npz --level trust-ready
python -m fidetype.conformance check out/streams/ --json report.json
# Optional: fail if a ground-truth line appears in the header or meta (5.3.1)
python -m fidetype.conformance check my_stream.jsonl --truth truth.txt

# Consumer in any language: exit 0 = accept, non-zero = reject;
# optional JSON on stdout ({"n_frames": ..., "vocab_type": ...}) is compared too
python -m fidetype.conformance consumer --cmd "node my_reader.js {path}"
# Consumer in Python: a function that returns a value (accept) or raises (reject)
python -m fidetype.conformance consumer --impl my_pkg.reader:load

# Our own adapters on synthetic inputs (no data needed)
python -m fidetype.conformance check adapter:all
```

Output:

- a short human summary: one line per target, the failed checks with their clause, and a badge line, for example `[NeuralTextStream v0.1 conformance: TRUST-READY] core:PASS trust-ready:PASS provenance:FAIL (...)`;
- with `--json`, a machine-readable report (schema `fidetype.conformance.report/1`): per target the level, the counts and every check with id, level, keyword, clause, outcome and message. The report also holds a [shields.io endpoint](https://shields.io/badges/endpoint-badge) badge object;
- the exit code is 0 if every target reaches `--level` (default `core`).

A consumer in another language can also use the vectors without Python: read `spec/conformance/v0.1/manifest.json`, load each file, and compare with `expect` and `expected`.

## Golden vectors
52 vectors: 32 NPZ and 20 JSON Lines. They cover all 20 cases C1–C20 of spec 7.1 and these edge cases:

| Group | Examples |
|---|---|
| Size | empty stream (T = 0, NPZ and JSON Lines), single frame |
| Values | NaN, +inf, a row of only `-inf`, raw logits (unnormalised), a row that sums to 2, JSON `NaN` token |
| Forward compatibility | unknown NPZ key, unknown header / frame / `meta` keys, unknown event type (all accepted and ignored); future minor version `"0.2"` (rejected, see A6) |
| `vocab_type` variants | `char` with CTC blank, `command` without blank, `key` (W3C codes), `phoneme` CTC (ARPAbet + SIL) |
| `meta` rules | valid provenance keys, bad `decoder.weights_sha256`, `decoder.lookahead_s` ≠ `latency`, unknown `device.modality`, NaN in `meta_json`, a `target_text` key (leakage) |
| Serialisation | pickled object array, missing `meta_json`, header not first, header without `vocab_type`, short frame, boolean `blank_id`, lines after `end`, sparse frames (valid and unnormalised) |
| Events | valid decision / hypothesis / pointer / signal_quality; C17, C18, C20; bad `clock_domain` |

The reference consumer (`fidetype.conformance.io.load_stream`) passes 52 / 52. The frame-core validator `NeuralTextStream.from_npz` agrees on all NPZ vectors except 4 `meta`-rule vectors (V30–V33). That is by design: spec 7 says the validator covers the frame core only.

## Results on our adapters
Synthetic inputs (fixed seed, no data from people). The table shows the level **before** and **after** the M5-10 fixes.

| Adapter | Stream forms | Before | After | What remains |
|---|---|---|---|---|
| SpanishBCBL MEG ConvCTC (`fidetype.adapters.spanishbcbl_meg`, used by `fidetype.decoders.infer`) | `char` CTC, offline and causal | core | **provenance** | — |
| Brain-to-Text '25 (`fidetype.adapters.b2t25`) | `phoneme` CTC; one-character symbol form | trust-ready | **trust-ready** | `PV-WEIGHTS`: the published online decoder has no weights file to hash. Advisory: the symbol form keeps `vocab_type = "phoneme"` with letter tokens (A3). |
| Toronto sEMG (`fidetype.adapters.toronto_semg`) | `key` stream; `char` CTC form; offline and with a window latency | trust-ready (core with a latency) | **provenance** (when the caller gives the weights hash and a stream id) | — |

## Bugs found and fixed
1. **MEG producer had no semantic conventions.** `fidetype.decoders.infer` wrote only flat keys (`subject`, `split`, `frame_period_s`, ...): no `device.modality`, no `decoder.causal`, no `data.derived`, no `language`, and the frame period only in `meta`. New adapter module `fidetype.adapters.spanishbcbl_meg` writes the 4.2 keys, the `frame_period` field, `latency` = lookahead × layers × frame period in causal mode, the dataset keys under `spanishbcbl.`, a weights hash of the checkpoint and an opaque `stream.id`.
2. **Toronto: a latency with `decoder.causal = false`.** `keypress_stream(..., latency=x)` kept `decoder.causal = false`. By the 4.2 definition a decoder that uses no signal after `t + latency` is causal. Now it sets `decoder.causal = true` and `decoder.lookahead_s = latency`.
3. **Calibrated streams said "not calibrated".** `TemperatureScaler.transform_stream` added only a flat `calibration_temperature`. The default of `calibration.applied` is `false`, so the stream claimed that no calibration step ran. Now it sets `calibration.applied = true`, `decoder.calibration_method = "temperature"` and `decoder.calibration_id`.
4. **NaN in `meta`.** `NeuralTextStream.to_npz` wrote NaN into `meta_json` and `from_npz` read it. NaN is not a JSON value (4.1). Both now refuse it.
5. **Provenance keys.** The B2T '25 and Toronto adapters now write `adapter.name`, `adapter.version` and `calibration.applied = false`. B2T '25 writes an opaque `stream.id` (hash of the dataset digest, trial index and logits). Toronto takes `weights_sha256` and `stream_id` as optional arguments.

## Spec ambiguities found
The suite found 10 points where the spec text is unclear. They are listed as informative open questions in [spec section 10, item 12](../../spec/neuraltextstream-v0.1.md#10-open-questions) (A1–A10). The most important: what `decoder.causal = true` means without `latency` (A1); whether custom keys may live in a defined namespace such as `decoder.*` (A2); encoded vocabularies (A3); whether a v0.1 consumer must reject a future minor version (A6); whether NPZ dtypes are normative (A7).

## Opt-in FEP profiles (M4-07, M6-09)
A profile tests one draft FEP on top of v0.1. It does not change the v0.1 levels or the 52 v0.1 vectors.

| Profile | FEP | Checks | Vectors | Wiki |
|---|---|---|---|---|
| `fep-0001` | [Streaming trust events](../../spec/feps/0001-streaming-trust-events.md) | 10 (`FEP1-*`) | 40 JSON Lines (12 accept, 28 reject) | [Streaming trust layer](streaming-trust-layer.md#conformance-profile-fep-0001-m4-07) |
| `fep-0002` | [NTS over LSL](../../spec/feps/0002-nts-over-lsl.md) | 6 (`FEP2-*`) | 31 JSON scenarios (15 accept, 16 reject) | [LSL input](lsl-input.md#conformance-profile-fep-0002) |

```bash
fidetype conformance --profile fep-0001                       # reference consumer over the profile vectors
fidetype conformance consumer --profile fep-0002 --cmd "my-reader {path}"
fidetype conformance check --profile fep-0001 decisions.jsonl
fidetype conformance list --profile fep-0002
```

Code: `src/fidetype/conformance/profiles/` (`fep0001.py`, `fep0002.py`). Tests: `tests/test_fep_profiles.py`.

## Limits
- Leakage (5.3) and privacy (5.4) checks are heuristics. They find clear signs (a `target_text` key, an e-mail address). They cannot prove that a stream is clean. With `--truth`, the suite also searches the header for the real truth texts.
- The suite checks the NPZ and JSON Lines forms. WebSocket (6.3), LSL (6.4) and the HID bridge (6.5) are sketches and have no checks yet.
- The vocabulary registry (3.4) has one entry (`char.b2q-28`). Other `vocab_id` values are skipped.

## Related
- Spec: [NeuralTextStream v0.1](../../spec/neuraltextstream-v0.1.md), sections 7 and 10.
- [Provenance ledger](provenance-ledger.md): the consumer side of the provenance keys.
- [Long-term standard roadmap](../questions/roadmap-standard.md): phase P7 (conformance and certification).
- [Architecture](../questions/architecture.md): where NeuralTextStream sits.
- Adapters: [Brain-to-Text '25](../entities/brain-to-text-25.md), [Toronto sEMG typing dataset](../entities/toronto-semg-typing-dataset.md).

## Used by
- [TypeScript SDK](typescript-sdk.md): runs the same golden vectors (all profiles) and gives the same verdict as the Python reference on every vector (`npm run cross-check`).
- [Rust SDK](rust-sdk.md): the same vectors, the same verdict and "ok" on all 167 (`cross-check.mjs --rust BIN`), and the Python verdict on 16,141 fuzz mutants.
- [Open benchmark v0.1](open-benchmark.md): every submitted stream must reach the `trust-ready` level (the entry gate).
