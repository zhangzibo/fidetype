---
title: P4-22 text-nbest CSV and JSON Lines readers on real decoder output
type: experiment
updated: 2026-11-22
---

# P4-22: the `text-nbest` file readers on real decoder output (gap 177)

Plan (committed before the run, `6039ad0`): [plan.md](plan.md). Code: [convert.py](convert.py), [run.py](run.py). Numbers: [results/results.json](results/results.json). CPU only, about 20 s. No training.

Run (repo root):
```
.venv\Scripts\python.exe -I experiments/2026-11-22-p4-22-nbest-readers/convert.py
.venv\Scripts\python.exe -I experiments/2026-11-22-p4-22-nbest-readers/run.py
```

## Honest scope

No tool on this machine writes decoder output as CSV or JSON Lines n-best files. So `convert.py` copies two real decoder outputs into these forms, unchanged (`csv` module quoting, scores as Python `repr`). The decoders are real; the file layout is ours.

| Id | Real decoder output | Files (in `bci-data/derived/p4-22`, not in the repo) |
|---|---|---|
| R1 | Card et al. 2024 online decoder, `decoded_sentence` of the 1,718 copy-task trials (`t15_copyTask.pkl`, Dryad SHA-256 checked) | `r1-online-1best.csv` (`id,text`), `r1-online-1best.jsonl` (`{"id","text"}`) |
| R2 | M4-06 decoder (CTC beam search + LM over the published RNN logits): 816 test trials, 10-best lists with FEP-0001 evidence | `r2-ours-nbest.csv` (`id,text,score`, one row per item), `r2-ours-nbest.jsonl` (`{"id","t_start","t_end","nbest"}`) |

## Result: PASS (all checks of the plan)

| File | C1 utterances / items | C2 exact round trip | C3 `read_nbest` same | C4 conformance failures | C5 stream `nbest` = source |
|---|---|---|---|---|---|
| `r1-online-1best.csv` | 1,718 / 1,718 | 1,718 / 1,718 | yes | 0 | - |
| `r1-online-1best.jsonl` | 1,718 / 1,718 | 1,718 / 1,718 | yes | 0 | - |
| `r2-ours-nbest.csv` | 816 / 8,158 | 816 / 816 (text, score) | yes | 0 | - |
| `r2-ours-nbest.jsonl` | 816 / 8,158 | 816 / 816 (text, score, `logp_acoustic`, `logp_lm`, `char_confidences`) | yes | 0 | 816 / 816 |

C4 is `check_stream_file`: the v0.1 suite (core) and the `fep-0001` profile, on the hypothesis-only stream that `write_stream` made from each read.

## Descriptive

| File | Bytes | SHA-256 |
|---|---|---|
| `r1-online-1best.csv` | 79,770 | `1c83fcda7c71fcecbb6037d7a8d9fe3bc9dd21ac5ac7a08a7ea564e9db0ea5fa` |
| `r1-online-1best.jsonl` | 114,121 | `f6951a12c646a87091f4aa48f8321b06dc3a4d4552eed3d4abd69b4e8caf42fc` |
| `r2-ours-nbest.csv` | 509,136 | `f8f1b336231a6d7d7ea098f09a1245d22f25d99ab807690d8cfe46ac8986104b` |
| `r2-ours-nbest.jsonl` | 6,375,801 | `81c93ec63285cd53315ad69709b9c02fc8e1d4c9790d6158d437ffef38abdf27` |

- The R1 CSV and R1 JSONL reads give the same stream (same SHA-256 `cb0d7cbb...`).
- CSV quoting cases in the real texts: 0 texts with a comma, 0 with a double quote, 0 with a leading or trailing space, 0 empty. So the real files do not exercise CSV quoting; the synthetic tests still cover it.

## Limits

- The file layout comes from our converter, not from a third-party tool. A real tool's own CSV (for example a Kaggle submission writer) may use other column names; `read_csv` takes `id_col`, `text_col`, `score_col` for that.
- The streams use `score_semantics = "none"`: the v0.1 writer has no `log` semantics, so the R2 log scores are kept as numbers without a declared meaning.
- One dataset family (B2T '25 / T15), English, no CSV quoting cases.
