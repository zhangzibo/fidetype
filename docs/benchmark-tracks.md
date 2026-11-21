# Benchmark tracks v0.2

This page defines the seven benchmark tracks of the Fidetype open benchmark (roadmap item P6-01). Each track is one scored task on one public dataset. Each track has a fixed, versioned split file. The split files hold **only salted hashes**: no text, no signals, no plain trial ids.

- Code: [`src/fidetype/benchmark/tracks.py`](../src/fidetype/benchmark/tracks.py)
- Split files: [`src/fidetype/benchmark/splits/tracks-v0.2/`](../src/fidetype/benchmark/splits/tracks-v0.2/)
- How to submit: [benchmark-submission.md](benchmark-submission.md) (format v0.2 + one-command scorer, P6-02), [`benchmark/README.md`](../benchmark/README.md)
- Metrics: [safe WPM](safe-wpm.md), [hallucination benchmark](hallucination-benchmark.md), [error metrics](../wiki/concepts/error-metrics.md)
- Data licences: [`LICENSES/DATA.md`](../LICENSES/DATA.md)

## The tracks

| Track | Modality | Dataset | Licence | Scored unit (test) | Open splits | CI unit |
|---|---|---|---|---|---|---|
| `b2t25-t15` | intracortical speech | Brain-to-Text '25, T15 copy task | CC0 1.0 | 816 trials | cal 812 | day |
| `b2t24-t12` | intracortical speech | Brain-to-Text '24 competitionData, T12 | CC0 1.0 | 880 trials | train 7900, cal 880 (holdout 1200: no labels, not scored) | session |
| `willett-hw` | intracortical handwriting | Willett 2021, T5 sentences | CC0 1.0 | 254 trials (81 with RNN output) | train 527, val 62, cal 124 | session |
| `toronto-semg` | forearm sEMG | Toronto typing gestures | CC BY 4.0 | 551 composed sentences (490 recordings) | train 985 rec., cal 493 rec. / 570 sentences | participant |
| `kt-semg` | forearm sEMG | KT-sEMG (Nokia) | CC BY 4.0 | 172 typing bursts in 6 runs | train 20 runs, cal 3 runs / 89 bursts | run |
| `spanishbcbl-meg` | MEG | SpanishBCBL | CC BY-NC 4.0, **research only** | 637 trials | train 4026, val 437 | sentence x participant |
| `emg2qwerty` | wrist sEMG | emg2qwerty (Meta) | CC BY-NC-SA 4.0, **research only** | 104 sessions (one per user) | train 927, val 104 | user |

`python -m fidetype.benchmark.tracks list` prints this list. `info <track>` prints the full definition: task, metrics, controls, timing, licence, attribution, split rule and counts.

**Research-only tracks.** SpanishBCBL and emg2qwerty forbid commercial use. Their results, and weights trained on them, are research-only. emg2qwerty also keeps the share-alike terms. Fidetype ships no data and no weights from either dataset.

**Same trials as v0.1.** `b2t25-t15`, `toronto-semg` (sentence set) and `spanishbcbl-meg` hold the same trials and splits as the v0.1 tracks `b2t25-t15-copytask`, `toronto-semg-composed` and `spanishbcbl-meg-async`. The tests check this from the committed files alone. So the v0.1 results stay valid on v0.2.

## Split rules

| Track | Rule |
|---|---|
| `b2t25-t15` | 125k-vocabulary trials. Per post-implant day, in file order: first half -> cal, second half -> test |
| `b2t24-t12` | Official partitions. `train/` -> train, but the last block of each train session -> cal. `test/` -> test. `competitionHoldOut/` -> holdout (labels not released) |
| `willett-hw` | Sessions in date order. Last 3 sessions: first third of the trials -> cal, the rest -> test. Earlier sessions: last 10 % -> val, the rest -> train |
| `toronto-semg` | Recordings: T1 -> train; T2, first recording of a letter -> cal; T2, later recordings -> test. Sentences: the v0.1 composed set |
| `kt-semg` | Runs in start-time order: last 6 -> test, 3 before -> cal, rest -> train. Bursts: key presses split at pauses > 2 s, >= 5 keys |
| `spanishbcbl-meg` | Split by sentence (SHA-1 bucket of the normalised text, 80/10/10). No test sentence is in train |
| `emg2qwerty` | Our own rule (the upstream split lists are not copied). Per user with >= 4 sessions: last session -> test, second last -> val, rest -> train. Other users: all train |

> **Our take:** test data always comes later in time than training data (later days, sessions, runs or recordings), except in SpanishBCBL, which splits by sentence. This is on purpose: a real user meets drift.

## What every entry reports

| Item | Rule |
|---|---|
| Metrics | CER, WER (key error rate on key tracks), eWPM [95 % CI] next to the no-BCI reference, safe WPM at alpha 0.05, wrong-commit rate, error among commits, commit rate |
| Required controls | Time-shuffled input and zero (null) input. Both must give a higher CER than real input. The null input must commit on at most 5 % of trials. Entries without them show "controls: no". The scorer exits with code 1 until all three pass ([submission format](benchmark-submission.md)) |
| Optional controls | Hallucination tracks (null, scrambled, swapped signal) on the intracortical speech tracks |
| Timing | Measured per trial where the data has it (speech duration, neural bins, key times). Else the track rate model, and the entry says so |
| Regime | Cross-session, session-calibrated, cross-subject or personalised |
| Licence | The licence of the weights. Research-only data gives research-only weights |
| Target | `emg2qwerty` only: `raw_keys` (default, the typed key sequence) or `intended_text` (Backspace applied, rule `intended-text/1`). The card declares it; the board shows each target in its own table ([submission format](benchmark-submission.md)) |

## The split file format

Schema `fidetype.benchmark.tracksplit/0.2`. One entry per unit:

```json
{"u": "trial", "h": "3f9c0b6a1d2e4f58", "s": "test", "g": "a1b2c3d4e5f6", "fp": "0c1d2e3f4a5b6c7d"}
```

| Field | Content |
|---|---|
| `u` | The unit set: trial, recording, sentence, run, segment or session |
| `h` | `sha256("<salt>\|<local id>")[:16]`. The loader rebuilds the local id from your download |
| `s` | The split |
| `g` | `sha256("<salt>\|group\|<group>")[:12]`: the cluster for the confidence intervals |
| `fp` | `sha256("<salt>\|fp\|<local id>\|<payload>")[:16]`. The payload is the normalised truth and / or a size. It checks your copy. It does not give the text back |

The salt is `fidetype/tracks/0.2/<track>`. It is public. It only makes the hashes differ between files, as in [`splits/halluc-v0.1`](../src/fidetype/benchmark/splits/halluc-v0.1/). The file header carries the licence, the research-only flag, the rule, the counts and a digest of all entries.

## Verify your copy, then select a split

```bash
# 1. check that your download matches the split hashes (exit code 1 on a mismatch)
python -m fidetype.benchmark.tracks verify b2t24-t12 --data <path>/competitionData
python -m fidetype.benchmark verify kt-semg --data <path>/kt-semg            # same command

# 2. list the local units of a split with their adapter input (a local file: never commit it)
python -m fidetype.benchmark.tracks select willett-hw --data <path>/handwritingBCIData --split test --out test-units.jsonl
```

`--data` per track: the `t15_copyTask.pkl` file; the `competitionData` folder; the `handwritingBCIData` folder; the Toronto extracted folder (add `--cache <window cache> --sentences <eng_tatoeba_heldout.txt>` for the sentence set); the KT-sEMG folder; the SpanishBCBL preprocessing cache; the `emg2qwerty-data-2021-08` folder.

`verify` reports missing units, fingerprint mismatches (other data or another version), split mismatches and group mismatches. Extra local units are allowed. In Python:

```python
from fidetype.benchmark import tracks
rep = tracks.verify("willett-hw", "<path>/handwritingBCIData")
units = tracks.select("willett-hw", "<path>/handwritingBCIData", "test")
for u in units:          # u.ref = {"file", "index", ...}: the input of the adapter
    ...                  # fidetype.adapters.willett_handwriting.load_sentences(u.ref["file"]) -> trial_stream(...)
```

Each track names its adapter call (`info <track>`, field `adapter`).

## Train / test overlap: b2t25-t15 and the HDF5 files

The `b2t25-t15` track scores trials of `t15_copyTask.pkl`. The B2T '25 neural data (`t15_copyTask_neuralData.zip`, HDF5 files `data_train.hdf5`, `data_val.hdf5`, `data_test.hdf5` per session) hold the **same trials** in another form ([T15 split audit](../wiki/questions/t15-split-audit.md)). The normal B2T '25 recipe trains on HDF5 `train`. That partition holds 366 of the 816 test trials (368 with the less exact matches). So a decoder trained on all of HDF5 `train` is trained on about 45 % of the test set.

**Rule.** Before you train, tune or calibrate on the HDF5 files for a `b2t25-t15` entry, leave out every HDF5 trial that matches a test unit. Then declare it in `submission.json` with `"exclude": "track-test-matches"` ([submission format](benchmark-submission.md#train--test-overlap-check-p6-10)).

| HDF5 file | Trials to leave out | Strict match | Possible match (one of several candidates) |
|---|---|---|---|
| `data_train.hdf5` | 368 | 366 | 2 |
| `data_val.hdf5` | 209 | 200 | 9 |
| `data_test.hdf5` (no labels) | 233 | 100 | 133 |
| All | **810** | 666 | 144 |

The list is the committed hash-only map [`splits/overlap-maps/b2t25-t15__b2t25-hdf5.json`](../src/fidetype/benchmark/splits/overlap-maps/b2t25-t15__b2t25-hdf5.json). It holds salted hashes of (session, `block_num`, `trial_num`), the partition, the matched unit hash and the match quality. It holds no text and no plain trial ids. This command prints the trials of your own copy (local output):

```bash
python -m fidetype.benchmark overlap-list --hdf5 <path>/hdf5_data_final > leave_out.tsv   # session, partition, block_num, trial_num, match
```

Exit code 0 means that all 810 trials of the map were found in your copy.

**Same sentence, other trial.** The copy task repeats sentences across days. 428 of the 816 test units have a sentence that also occurs in HDF5 `train` (any day), and 209 in HDF5 `val`. If you leave out only the matched trials, the overlap check still reports these units as `text` overlap. The map holds this per unit, so `score` reports it without your text.

Build script and counts: [`experiments/2026-11-21-p6-10-overlap-check/`](../experiments/2026-11-21-p6-10-overlap-check/results.md). The map uses the match rule of the audit (session date, normalised sentence, frame count).

## Checks we ran on the local copies (2026-11-16)

All seven tracks: `verify` OK on the maintainer copies (Brain-to-Text '24 from the Zenodo 8047896 copy of the Dryad DOI). The three v0.1-equivalent tracks: 0 mismatches against the v0.1 split files.

## Versioning

A split never changes inside a version. A new rule, a new dataset version or a fixed bug gives a new version (`tracks-v0.3`). The old files stay, so old results stay comparable.
