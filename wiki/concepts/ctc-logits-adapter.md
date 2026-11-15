---
title: CTC-logits adapter
type: concept
tags: [adapter, ctc, neuraltextstream, sdk, p4]
sources: [brain-to-text-25-copytask]
updated: 2026-11-14
---

# CTC-logits adapter

Task **P4-01** (part). `fidetype.adapters.ctc_logits` turns the frame output of **any** [CTC](ctc.md) decoder into a valid NeuralTextStream ([spec 1.0 RC2](../../spec/nts-1.0-rc2.md) sections 3, 4.2, 5). Most public neural and EMG text decoders end in a CTC layer. So one generic adapter covers many decoders, and a decoder author does not need to read the spec first.

Licence: our own code (Apache-2.0). It reads file formats only. It uses and copies no third-party code.

## Why this adapter first
- It needs no GPU and no new data. It runs on decoder outputs that exist.
- The dataset adapters ([B2T '25](../entities/brain-to-text-25.md), [Toronto sEMG](../entities/toronto-semg-typing-dataset.md), SpanishBCBL) each repeat the same steps: normalise, stamp times, build `meta`. This module does these steps once, for every decoder.
- The [Python SDK](python-sdk.md) `make_stream` takes one clean matrix. Real decoders give batches, padding, probabilities or raw logits, and their own vocabulary files. This adapter handles those forms.

## What it accepts

| Input | Forms |
|---|---|
| Scores | `logits`, `log_probs` (natural log, `-inf` allowed), `probs`, or `auto` (detected per matrix) |
| Shape | `(T, V)`; batch `(B, T, V)` or `(T, B, V)` (PyTorch `CTCLoss` order) with per-item lengths; padding never reaches a stream |
| Arrays | NumPy, or a torch tensor (duck-typed; torch is not imported) |
| Files | `.npy` (one matrix), `.npz` (one matrix per key); read with `allow_pickle=False` |
| Vocabulary | JSON list; JSON `{token: id}` map (Hugging Face CTC tokenizer form: blank = `<pad>`, `\|` → space); `tokens.txt` (`token` or `token id` per line, k2 / icefall / sherpa form) |

## What it writes
- FRM-3 normalised frames. Logits get `log_softmax`. Probabilities get `log` (0 → `-inf`).
- Frame times: `t0 + frame_period · t` (default `t0` = one frame period), or explicit times.
- `latency` = the decoder lookahead, copied to `meta["decoder.lookahead_s"]`. Spec MET-5: a bounded lookahead window is **causal** with `latency` = the window. An offline (full-sequence) decoder is `causal = false` and has **no** `latency`. The adapter refuses the mixed case.
- Optional frame temperature T: `log_softmax(log_probs / T)`. T ≠ 1 is a calibration step, so `calibration.applied = true` and `decoder.calibration_method = "temperature"` (check TR-CALIB).
- `meta` from `stream_meta`: modality, decoder name and version, causal flag, language, LM, `data.derived`, adapter name and version, optional `decoder.weights_sha256`, and an opaque content-hash `stream.id`. An `.npz` key does not go into `meta` (a key can name a session).

```
python -m fidetype.adapters.ctc_logits logprobs.npz --vocab vocab.json \
    --frame-period 0.08 --t0 0.28 --latency 0 --modality intracortical \
    --decoder-name my-gru --decoder-version 1 --weights model.safetensors \
    --out streams/ --level trust-ready
```

The command line checks each written stream with the [conformance suite](conformance-suite.md) and exits with 1 if one stream does not reach the level.

## Results (2026-11-14, CPU only)

| Check | Result |
|---|---|
| Our [lookahead GRU](../questions/lookahead-latency-accuracy.md) outputs on T15 (`logprobs-m4-01-la-fixed0.npz`, L 0; `…fixed25.npz`, L 500 ms), 701 val_eval trials each | 1,402 / 1,402 streams reach **trust-ready**; about 10 s per file |
| Published T15 online RNN logits ([B2T '25 copy task](../sources/brain-to-text-25-copytask.md)), 1,718 trials, generic adapter vs `fidetype.adapters.b2t25` | Same frame times on 1,718 / 1,718; max \|Δ log-prob\| 7.6e-6 (float32 rounding) |
| Conformance target `adapter:ctc-logits` (batch with lengths, HF vocabulary with probabilities, lookahead with temperature, offline) | 5 / 5 streams reach **provenance** |
| Unit tests `tests/test_adapter_ctc_logits.py` | 26 passed |

The decoder outputs and the dataset stay local (`C:/Users/zhang/bci-data`, not committed).

> **Our take:** the B2T '25 adapter can become a thin wrapper of this module (vocabulary + timing + `meta`). We did not change it now, because its tests and the benchmark depend on its exact output. The result above shows that both give the same stream.

## Limits and open points
- Frame timing is the caller's claim. The adapter cannot check that `t0` and `frame_period` match the model. The B2T '25 values are **inferred** (14-bin patch, stride 4).
- No sparse (top-k) frames yet. Large vocabularies (BPE, words) give large dense JSON lines.
- No `.pt` / pickle input, on purpose (a pickle can run code). Convert to `.npy` first.
- `vocab_type` defaults to `char`. Give `phoneme`, `word` or `other` for other tokens (HDR-14: the meaning, not the spelling).

## Related
- [Text n-best adapter](text-nbest-adapter.md): the same job for decoders that give text only.
- [Roadmap P4](../questions/roadmap-standard.md#p4-device-and-toolkit-adapters), [NTS specification](nts-spec.md), [Python SDK](python-sdk.md), [conformance suite](conformance-suite.md).
