---
title: Text n-best adapter
type: concept
tags: [adapter, hypothesis, nbest, neuraltextstream, p4]
sources: [brain-to-text-25-copytask]
updated: 2026-11-14
---

# Text n-best adapter

Task **P4-01** (part). `fidetype.adapters.text_nbest` turns the **text** output of any decoder into a NeuralTextStream. Many public decoders give only text: one sentence per trial, or an n-best list with scores (for example a Kaggle-style `id,text` submission file). They have no frame matrix, so the [CTC-logits adapter](ctc-logits-adapter.md) cannot carry them.

Licence: our own code (Apache-2.0). No third-party code.

## Stream form
The output is a **hypothesis-only** stream ([spec 1.0 RC2](../../spec/nts-1.0-rc2.md) 4.7, HDR-12):

| Line | Content |
|---|---|
| `header` | `vocab = []`, `blank_id = null`, `vocab_type = "char"`, decoder `meta` (no text), optional `decode_declaration` (4.7.3) |
| per utterance | one `hypothesis` (`id`, `nbest` best first, `is_final`, `score_semantics`, optional `t_start` / `t_end`), then one `segment_end` (`unit = "utterance"`) |
| last | `end` |

The [streaming trust layer](streaming-trust-layer.md) reads this form on its hypothesis route.

## Inputs
- **CSV** with a header row. Default columns `id`, `text`; optional score column. Rows with the same id form one n-best list, in row order.
- **JSON Lines**: `{"id", "nbest": [{"text", "score", ...}]}` or `{"id", "text", "score"}` per line. `NaN` and `Infinity` are refused (GEN-2).
- **Python**: `Utterance(nbest, id=, t_start=, t_end=)` or `utterances_from_texts(texts)`.

## Rules the adapter enforces
- A missing score becomes 0.0 with `score_semantics = "none"` (EVD-3 asks for a finite number).
- `uncalibrated_prob` / `calibrated_prob`: every score in [0, 1] (DEC-2). `power` and `strength` are refused (they need a `score_range`).
- Evidence keys pass through and are checked: `char_confidences` (one value in [0, 1] per code point, EVD-1), `logp_acoustic` and `logp_lm` (≤ 0, EVD-4).
- Ids are unique (HYP-1). An utterance without an id gets `h<n>`.
- Offline decoder: `causal = false` and no `latency` (MET-5).
- `meta` holds no text. `stream.id` is an opaque content hash.
- `check_stream_file(path, level)` runs the v0.1 suite and the `fep-0001` profile on the written file.

```
python -m fidetype.adapters.text_nbest submission.csv --modality intracortical \
    --decoder-name my-decoder --decoder-version 1 --out stream.jsonl --level trust-ready
```

## Results (2026-11-14, CPU only)

| Check | Result |
|---|---|
| Published T15 online decoder sentences (`decoded_sentence` of the [B2T '25 copy task](../sources/brain-to-text-25-copytask.md)), 1,718 trials, one stream | **trust-ready** + `fep-0001` profile pass; 0 empty texts; 419 kB |
| Unit tests `tests/test_adapter_text_nbest.py` | 11 passed |

> **Our take:** text-only output is the weakest input for a trust layer. It has no per-frame evidence, so the layer can only use the n-best scores. The adapter still matters: it lets text-only decoders join the stream, the collector and the [open benchmark](open-benchmark.md) without a rewrite. Decoders that can give frames should use the CTC-logits adapter.

## Limits and open points
- The hypothesis-only stream is not registered as an `adapter:` conformance target. The suite targets hold `NeuralTextStream` objects (the frame core), not event lists. The unit tests and `check_stream_file` check the written files instead.
- No provisional (`is_final = false`) revision chains from files yet. The Python API can set `is_final`.
- `StreamWriter` in the SDK refuses `vocab = []`, so this module writes its own JSON Lines. HDR-12 allows V = 0; the SDK writer could follow (follow-up).

## Related
- [CTC-logits adapter](ctc-logits-adapter.md), [roadmap P4](../questions/roadmap-standard.md#p4-device-and-toolkit-adapters), [NTS specification](nts-spec.md), [conformance suite](conformance-suite.md).
