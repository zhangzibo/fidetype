---
title: P6-02b v0.2-format entries for b2t25-t15, toronto-semg and spanishbcbl-meg - results
type: experiment
task: P6-08
updated: 2026-11-17
---

# P6-02b: v0.2 entries for the three tracks that had only v0.1 entries (closes gap 31 = P6-08)

Runner: [run.py](run.py). Score cards (aggregates, no text): [`benchmark/results/v0.2/`](../../benchmark/results/v0.2/). Table of all new cards: [results/tables.md](results/tables.md). Stage checks: [results/stages.json](results/stages.json). Submissions (they hold decoded text) and truth files: `C:\Users\zhang\bci-data\derived\p6-02b-v02-entries\` only. CPU only, no GPU. Peak RSS about 0.9 GB.

## What was done

The v0.1 entries of these tracks came from committed per-trial arrays (no text) or from aggregates. A v0.2 submission needs text, a decision and both control runs for every unit. So [run.py](run.py) reruns the **same** pipelines on the existing decoder outputs (read only):

| Track | Decoder output (read only) | Pipeline and fit | Policies (thresholds) | Controls |
|---|---|---|---|---|
| b2t25-t15 | published RNN logits in `t15_copyTask.pkl` (CC0) | v0.1 B2T trust pipeline (`experiments/2026-11-10-b2t25-trust`), fit on the 812 cal trials | always-commit; plug-in gate; CRC 0.4893 / LTT 0.54 (ours); CRC 0.6717 / LTT 0.72 (published): the v0.1 thresholds | ours: frame-shuffled and near-uniform logits (input of our word decoder; the RNN is not ours). Published: the same streams, but the text is fixed |
| spanishbcbl-meg (**research only**) | M1-09 r4b async streams + the M1-09 control outputs | G1 pipeline, fit on the 437 val trials | always-commit; plug-in; CRC 0.1024; LTT 0.0 | **input level**: the network rerun on time-shuffled MEG and on zero MEG |
| toronto-semg | M6-07 key-window logits (3 regimes) | M6-07 plan, LM weight and fits (fit halves A / B) | always-commit; plug-in; CRC | key windows shuffled; CNN logits of an all-zero window (input level) |
| b2t25-t15, **partial** | M4-12 val_select / val_eval log-probs | drop-in guard (P14-03 recipe) on 616 val_select trials | drop-in guard (LTT, n_LTT 231) | decoder output level (frames permuted / uniform) |

Each submission is scored with the one command `python -m fidetype.benchmark score <track> <submission> --truth <truth>`.

**Reproduction check.** On every gated entry the per-unit commit scores equal the committed v0.1 per-trial scores (B2T ours, B2T published, MEG: `scores_equal_v01_items` true; same commit counts 189 / 199 / 159, 386 / 405 / 364, 0 / 14 / 15). Toronto commit counts equal the v0.1 rates (21, 10, 0 of 551).

## v0.1 vs v0.2 (alpha 0.05)

| v0.2 entry | CER v0.1 / v0.2 | WER | Wrong-commit | Commit rate | Safe WPM (v0.2 status) | eWPM | Controls v0.2 (shuf / zeros / null) |
|---|---|---|---|---|---|---|---|
| `b2t25-t15__ours__always-commit` | 0.095 / 0.095 | 0.149 / 0.149 | 0.610 / 0.610 | 1.000 / 1.000 | n/a / n/a (not-certified) | 11.45 / 11.35 | pass / pass / fail |
| `b2t25-t15__ours__trust` | 0.095 / 0.095 | 0.149 / 0.149 | 0.059 / 0.059 | 0.232 / 0.232 | n/a / n/a (not-certified) | 11.55 / 11.23 | pass / pass / pass |
| `b2t25-t15__ours__crc` | 0.095 / 0.095 | 0.149 / 0.149 | 0.062 / 0.062 | 0.244 / 0.244 | 4.90 / 4.90 (above-alpha) | 11.55 / 11.24 | pass / pass / pass |
| `b2t25-t15__ours__ltt` | 0.095 / 0.095 | 0.149 / 0.149 | 0.047 / 0.047 | 0.195 / 0.195 | 4.05 / 4.05 (certified) | 11.51 / 11.17 | pass / pass / pass |
| `b2t25-t15__published__always-commit` | 0.031 / 0.031 | 0.043 / 0.043 | 0.194 / 0.194 | 1.000 / 1.000 | n/a / n/a (not-certified) | 19.55 / 19.60 | fail / fail / fail |
| `b2t25-t15__published__trust` | 0.031 / 0.031 | 0.043 / 0.043 | 0.044 / 0.044 | 0.473 / 0.473 | n/a / n/a (not-certified) | 18.77 / 16.93 | fail / fail / pass |
| `b2t25-t15__published__crc` | 0.031 / 0.031 | 0.043 / 0.043 | 0.049 / 0.049 | 0.496 / 0.496 | 13.42 / 13.42 (certified) | 18.80 / 17.06 | fail / fail / pass |
| `b2t25-t15__published__ltt` | 0.031 / 0.031 | 0.043 / 0.043 | 0.040 / 0.040 | 0.446 / 0.446 | 12.24 / 12.24 (certified) | 18.73 / 16.78 | fail / fail / pass |
| `spanishbcbl-meg__convctc-m-async__always-commit` | 0.522 / 0.522 | 0.902 / 0.902 | 0.997 / 0.997 | 1.000 / 1.000 | n/a / n/a (not-certified) | 2.58 / 2.51 | pass / pass / fail |
| `spanishbcbl-meg__convctc-m-async__trust` | 0.522 / 0.522 | 0.902 / 0.902 | 0.000 / 0.000 | 0.000 / 0.000 | n/a / n/a (not-certified) | 3.20 / 3.11 | pass / pass / pass |
| `spanishbcbl-meg__convctc-m-async__crc` | 0.522 / 0.522 | 0.902 / 0.902 | 0.020 / 0.020 | 0.022 / 0.022 | 0.03 / 0.03 (certified) | 3.20 / 3.11 | pass / pass / pass |
| `spanishbcbl-meg__convctc-m-async__ltt` | 0.522 / 0.522 | 0.902 / 0.902 | 0.022 / 0.022 | 0.024 / 0.024 | 0.03 / 0.03 (certified) | 3.20 / 3.11 | pass / pass / pass |
| `toronto-semg__cnn-calib__always-commit` | 0.123 / 0.123 | 0.214 / 0.214 | 0.541 / 0.541 | 1.000 / 1.000 | n/a / n/a (not-certified) | 7.81 / 7.77 | pass / pass / fail |
| `toronto-semg__cnn-calib__trust` | 0.123 / 0.123 | 0.214 / 0.214 | 0.004 / 0.004 | 0.038 / 0.038 | n/a / n/a (not-certified) | 8.02 / 7.87 | pass / pass / pass |
| `toronto-semg__cnn-calib__crc` | 0.123 / 0.123 | 0.214 / 0.214 | 0.004 / 0.004 | 0.038 / 0.038 | 0.55 / 0.55 (certified) | 7.98 / 7.87 | pass / pass / pass |
| `toronto-semg__cnn-xsession__always-commit` | 0.398 / 0.398 | 0.579 / 0.579 | 0.882 / 0.882 | 1.000 / 1.000 | n/a / n/a (not-certified) | 4.10 / 4.06 | pass / pass / fail |
| `toronto-semg__cnn-xsession__trust` | 0.398 / 0.398 | 0.579 / 0.579 | 0.004 / 0.004 | 0.018 / 0.018 | n/a / n/a (not-certified) | 4.68 / 4.63 | pass / pass / pass |
| `toronto-semg__cnn-xsession__crc` | 0.398 / 0.398 | 0.579 / 0.579 | 0.004 / 0.004 | 0.018 / 0.018 | 0.25 / 0.25 (certified) | 4.68 / 4.63 | pass / pass / pass |
| `toronto-semg__cnn-xsubject__always-commit` | 0.479 / 0.479 | 0.681 / 0.681 | 0.962 / 0.962 | 1.000 / 1.000 | n/a / n/a (not-certified) | 3.53 / 3.41 | pass / pass / fail |
| `toronto-semg__cnn-xsubject__trust` | 0.479 / 0.479 | 0.681 / 0.681 | 0.000 / 0.000 | 0.000 / 0.000 | n/a / n/a (not-certified) | 4.08 / 4.03 | pass / pass / pass |
| `toronto-semg__cnn-xsubject__crc` | 0.479 / 0.479 | 0.681 / 0.681 | 0.000 / 0.000 | 0.000 / 0.000 | 0.00 / 0.00 (vacuous) | 4.08 / 4.03 | pass / pass / pass |

New entry (no v0.1 counterpart):

| v0.2 entry | Units | CER | WER | eWPM | No-BCI | Safe WPM | Wrong-commit | Commits | Controls |
|---|---|---|---|---|---|---|---|---|---|
| `b2t25-t15__m4-12__guard` | **103 / 816 (partial)** | 0.204 | 0.300 | 7.33 | 4.12 | 0.00 (vacuous) | 0.000 | 0 | pass / pass / pass |

## What differs and why

| Item | Same? | Reason |
|---|---|---|
| CER, WER, wrong-commit, commit rate, safe WPM | **identical** on all 21 entries | same text, same decisions |
| eWPM | 0.04 to 1.86 lower in v0.2 | different definition. The v0.2 scorer simulates one decision per unit (an offer shows the top 3 texts) and uses the measured speech time per trial on b2t25-t15. The v0.1 numbers came from the multi-attempt harness of each experiment (retries, its own fallback) at the track rate model. The largest gap is B2T published + gate (18.80 -> 17.06): in v0.1 the harness user could retry; in v0.2 a withheld trial ends as one offer |
| Controls, B2T ours | now **pass / pass** (v0.1: aggregate audit on 300 trials) | per-unit controls on all 816 trials; CER gap CI above 0 |
| Controls, B2T published | now **fail / fail** (v0.1: "missing") | text-only decoder: the published sentence does not depend on our input, so the CER cannot rise. The null-commit control passes for the gated entries (0 commits on near-uniform input). The manifests say this |
| Controls, MEG and Toronto | pass / pass, as v0.1 | MEG controls are now input level per unit (were per-sentence CERs of the same M1-09 control run) |
| Null-commit, always-commit entries | fail (1.000) | by design: they commit on zero input |
| Plug-in "trust" entries | listed, never certified | as v0.1 (no guarantee) |

## M4-12 / M4-13 on b2t25-t15: why only partial

The b2t25-t15 track scores the copy-task trials of `t15_copyTask.pkl` (second half of each day). Our causal T15 decoders (M4-12, M4-13) use the B2T '25 HDF5 partitions. Matched by day and sentence:

| Decoder partition | b2t25-t15 test trials in it |
|---|---|
| train (decoder training) | about 368 |
| val_select (checkpoint choice and guard calibration) | 106 |
| val_eval (held out) | 103 |

So the decoder trained on about 368 test trials. Only the 103 val_eval trials are scored (declared subset, `[partial: 103/816]` on the board). The 106 val_select trials that are track test units are removed from the guard calibration (616 of 722 kept). The guard (`tcfg-065ec812c6cd643e`, n_LTT 231) commits on none of the 103 trials: safe WPM 0.00 (vacuous). This agrees with P14-05 (val_eval 701: 2 commits, both wrong).

> **Our take:** a full-coverage M4-x entry on b2t25-t15 needs a decoder retrained without the track test trials, or a track variant built on the HDF5 val_eval partition. The partial entry must not rank against full ones (open rule: gap 30 = P6-07).

### M4-13: one command when its outputs exist

The M4-13 queue writes `derived/m4-13/logprobs-m4-13-long0-val_eval.npz`; the trust-reruns queue writes `derived/trust-reruns-m4-13/logprobs-m4-13-long0-val_select.npz`. Then (repo root, about 6 min CPU):

```bash
.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-17-p6-02b-v02-entries/run.py t15-m4-13 score-m4-13 table
.venv\Scripts\python.exe -m fidetype.benchmark leaderboard
```

It stops with a clear message if a log-prob file is missing. It writes `benchmark/results/v0.2/b2t25-t15__m4-13__guard.json`.

## Our take

> **Our take:** the v0.2 format reproduces every v0.1 number that has the same definition. The certified numbers stand: B2T published CRC 13.42 / LTT 12.24, B2T ours LTT 4.05 (CRC 4.90 is above alpha: cal / test drift within a day), Toronto 0.55 / 0.25 / 0, MEG 0.03 (research only).

> **Our take:** the stricter per-unit controls change two verdicts. B2T ours now passes both CER controls on all trials. The B2T published entries fail them, which is the honest result for a text-only decoder: its text does not depend on any input we can change.

## Rerun (repo root)

```bash
python -m fidetype.benchmark truth b2t25-t15 --data <t15_copyTask.pkl> --out C:/Users/zhang/bci-data/derived/p6-02b-v02-entries/truth/b2t25-t15.jsonl
python -m fidetype.benchmark truth spanishbcbl-meg --data <cache/spanishbcbl/v1> --out .../truth/spanishbcbl-meg.jsonl
python -m fidetype.benchmark truth toronto-semg --data <toronto extracted> --cache <cache/toronto-semg/v1> --sentences <eng_tatoeba_heldout.txt> --out .../truth/toronto-semg.jsonl
.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-17-p6-02b-v02-entries/run.py toronto b2t meg t15-m4-12 score table
.venv\Scripts\python.exe -m fidetype.benchmark leaderboard
```

Times (CPU, background class, 4 threads): toronto 11 min, b2t 13 min, meg 9 min, t15-m4-12 6 min, score 1 min.
