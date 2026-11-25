---
title: P6-01 benchmark tracks v0.2 + side jobs - results
type: experiment
task: P6-01
updated: 2026-11-16
---

# P6-01: benchmark tracks v0.2, exact Toronto safe WPM, null-commit audits

Track definitions and split rules: [docs/benchmark-tracks.md](../../docs/benchmark-tracks.md). Code: [`fidetype.benchmark.tracks`](../../src/fidetype/benchmark/tracks.py). Side jobs: [run.py](run.py) (CPU, background class, 4 threads), [update_results.py](update_results.py). Aggregates: `results/*.json`. Per-trial files (no text): `C:\Users\zhang\bci-data\derived\p6-01-tracks\` only. No GPU.

## 1. Tracks and splits (committed files: hashes only)

| Track | Licence | Unit sets and counts | `verify` on our copy |
|---|---|---|---|
| `b2t25-t15` | CC0 1.0 | trial: cal 812, test 816 | OK (1628) |
| `b2t24-t12` | CC0 1.0 | trial: train 7900, cal 880, test 880, holdout 1200 | OK (10860) |
| `willett-hw` | CC0 1.0 | trial: train 527, val 62, cal 124, test 254 | OK (967) |
| `toronto-semg` | CC BY 4.0 | recording: train 985, cal 493, test 490; sentence: cal 570, test 551 | OK (3089) |
| `kt-semg` | CC BY 4.0 | run: train 20, cal 3, test 6; segment: cal 89, test 172 | OK (290) |
| `spanishbcbl-meg` | CC BY-NC 4.0, research only | trial: train 4026, val 437, test 637 | OK (5100) |
| `emg2qwerty` | CC BY-NC-SA 4.0, research only | session: train 927, val 104, test 104 | OK (1135) |

v0.1 equivalence (from the committed files, also a test): `b2t25-t15` 1628 / 1628, `toronto-semg` sentences 1121 / 1121, `spanishbcbl-meg` 5100 / 5100 ids hash to the same split; 0 mismatches.

## 2. Toronto sEMG safe WPM, exact per trial (alpha 0.05, CRC)

The CRC pipeline of `experiments/2026-11-11-emg-toronto/trust.py` was rebuilt (same plan, seed, LM weight, fit). Its commit rate, wrong-commit rate and eWPM equal the committed aggregates exactly for all three conditions. Timing stays the track rate model (composed sentences: 0.792 s per character).

| Condition | Safe WPM [95 % CI, participants] | Before (aggregate approx.) | Commits (wrong) | Test wrong-commit [CP95] | No-BCI |
|---|---|---|---|---|---|
| CNN session-calibrated + CRC | 0.55 [0.28, 0.86] | 0.58 | 21 (2) | 0.0036 [0.0004, 0.013] | 4.27 |
| CNN cross-session + CRC | 0.25 [0.06, 0.46] | 0.27 | 10 (2) | 0.0036 [0.0004, 0.013] | 4.27 |
| CNN cross-subject + CRC | 0.00 (vacuous) | 0.00 | 0 | 0.000 | 4.27 |

## 3. Null-commit audits at the entry's own CRC / LTT threshold

Before, these entries showed "controls: no" with `null_commit: missing`. The audit rebuilds the fitted trust pipeline, computes the M2-13 commit score on null inputs and applies the entry's threshold. On real input the scores equal the committed item files exactly (check in the JSON).

| Entry | lambda | Real | Null input (zeros stand-in) | Frame shuffled | Other trial / sentence | Controls now |
|---|---|---|---|---|---|---|
| B2T ours + CRC | 0.4893 | 68/300 | uniform 0/300 | 0/300 | 68/300 (all wrong) | **yes** |
| B2T ours + LTT | 0.5400 | 50/300 | uniform 0/300 | 0/300 | 50/300 (all wrong) | **yes** |
| B2T published + CRC | 0.6717 | 149/300 | uniform 0/300 | 0/300 | 0/300 | no (shuffled / zeros CER: text-only decoder) |
| B2T published + LTT | 0.7200 | 132/300 | uniform 0/300 | 0/300 | 0/300 | no (same reason) |
| MEG ConvCTC-M + CRC | 0.1024 | 14/637 | zeros MEG 0/637 (uniform 0/637; shuffled MEG 0/637) | 5/637 | 14/637 | **yes** |
| MEG ConvCTC-M + LTT | 0.0000 | 15/637 | zeros MEG 0/637 (uniform 0/637; shuffled MEG 0/637) | 8/637 | 15/637 | **yes** |

`update_results.py` wrote these into `benchmark/results/v0.1/` and rebuilt `benchmark/site/` (not published).

## Our take
> **Our take:** the exact Toronto values are a little lower than the approximation and now have a CI. They stay far below the no-BCI reference (4.27): the sEMG decoders commit too rarely to give safe words.

> **Our take:** "other trial" commits as often as real input for our B2T decoder. That is expected: the swapped stream is a real trial, so the decoder types that trial's sentence with confidence. It is wrong only for the label. The hallucination benchmark's swapped track (P15-07) measures this directly. The published-sentence gate does not commit there, because its fixed text no longer matches the stream.

## Limitations
- The Toronto timing is the rate model, not natural typing time (the data has isolated presses only).
- Audits use 300 B2T test trials (the earlier audit set); the CP95 upper bound on 0/300 is 0.012.
- The new tracks have split files and loaders; the scorer and baselines for `b2t24-t12`, `willett-hw`, `kt-semg` and `emg2qwerty` come with P6-02.

## Correction 2026-11-25: word count field of the per-trial files
The writer of the Toronto per-trial files unpacked its `zip` in the wrong order, so the field `n_words` held the correct flag (0 or 1), not the word count of the sentence. The writer is fixed (`trial_rows` in [run.py](run.py)), and a test checks it ([tests/test_toronto_trial_rows.py](../../tests/test_toronto_trial_rows.py)). The three local files were rebuilt on 2026-11-25 with `run.py --stages toronto` (the old files are kept in `old-before-2026-11-25/`). Checks: every other field is the same as before; `n_words` and `n_chars` equal the counts of the truth file; the aggregates (`results/toronto-safe-wpm.json`) are the same as the committed ones except the run times; `tools/benchmark/add_safe_wpm_v02_tracks01.py` (now with a word-count check) reproduces every stored safe WPM block. **No stored number changed:** the v0.1 block was computed from the arrays, not from the file, and the v0.2 tool takes the counts from the truth file.

## Rerun (repo root)
```bash
.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-16-p6-01-tracks/run.py --stages toronto,b2t-null,meg-null
.venv\Scripts\python.exe -I experiments/2026-11-16-p6-01-tracks/update_results.py
```
Run time: Toronto 126 s, B2T 380 s, MEG 500 s.
