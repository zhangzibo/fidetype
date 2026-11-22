# P4-22: the `text-nbest` CSV and JSON Lines readers on real decoder output (plan, 2026-11-22)

Roadmap: [P4-22](../../wiki/questions/roadmap-standard.md#p4-22-text-nbest-csv-and-json-lines-readers-on-real-decoder-output-files) (gap 177). CPU only. No training. This plan is written before any run.

## Problem

P4-15 (commit `ffc74f4`) found: `read_csv` and `read_jsonl` of `fidetype.adapters.text_nbest` ran on synthetic files only. Only `normalise_item` saw real n-best lists (P5-33).

## Honest statement about the input files

No tool on this machine writes decoder output as CSV or JSON Lines n-best files. The real decoder outputs that exist locally are in other containers:

| Id | Real decoder output | Container | Size |
|---|---|---|---|
| R1 | Card et al. 2024 online decoder: `decoded_sentence` of the 1,718 copy-task trials | `t15_copyTask.pkl` (Dryad, CC0, SHA-256 pinned in `fidetype.adapters.b2t25`) | 1-best per trial |
| R2 | Our M4-06 decoder (CTC beam search + LM over the published RNN logits, frozen frame temperature): 816 test trials | NTS hypothesis streams `bci-data/derived/m4-06-real-replay/streams/hyp-ours/trial-*.jsonl` | 8,158 n-best items with `score`, `logp_acoustic`, `logp_lm`, `char_confidences` |

So [convert.py](convert.py) writes these real outputs into the two file forms. It changes no text and no number. It writes only to `C:\Users\zhang\bci-data\derived\p4-22`:

| File | Form | Source |
|---|---|---|
| `r1-online-1best.csv` | `id,text` (the Kaggle-style submission columns), csv module quoting | R1 |
| `r1-online-1best.jsonl` | `{"id", "text"}` per line | R1 |
| `r2-ours-nbest.csv` | `id,text,score`, one row per n-best item, best first, score as Python `repr` | R2 |
| `r2-ours-nbest.jsonl` | `{"id", "t_start", "t_end", "nbest": [...]}` per line, items as in the stream | R2 |

Then [run.py](run.py) reads each file with the public readers (`read_csv`, `read_jsonl`, and `read_nbest`), writes a stream with `write_stream`, and checks it.

## Pass criteria (all must pass)

| # | Check | Pass |
|---|---|---|
| C1 | Counts | R1 CSV and R1 JSONL: 1,718 utterances, 1,718 items. R2 CSV and R2 JSONL: 816 utterances, 8,158 items |
| C2 | Exact round trip | For every utterance: same id order; every item text `==` the source text; R2 scores `==` the source float64; R2 JSONL `logp_acoustic`, `logp_lm`, `char_confidences` `==` the source. 100 % |
| C3 | `read_nbest` dispatch | `read_nbest` on each file gives the same utterances as the direct reader |
| C4 | Stream conformance | `write_stream` succeeds for the 4 reads (decoder metadata as in the source; `score_semantics = "none"`, because the v0.1 writer has no `log` semantics); `check_stream_file` returns 0 failures for each |
| C5 | Stream content | In the stream written from R2 JSONL: the `nbest` of each `hypothesis` event `==` the source `nbest`, 816 / 816 |

Descriptive (no pass rule): the number of texts with a comma, a double quote, a leading or trailing space, or no characters (the CSV quoting cases); file sizes and SHA-256 of the derived files.

## Privacy and licence

- The derived files hold decoded text. They stay in `bci-data/derived/p4-22`. The repository gets counts, hashes and check results only.
- B2T '25 data are CC0. We still do not commit decoded text.
- No new committed test needs real data. The existing synthetic tests stay.
