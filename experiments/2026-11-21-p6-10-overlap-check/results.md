# P6-10 (gap 33): train / test overlap check for benchmark entries

Date: 2026-11-21. CPU only, 2 threads. Data: local `t15_copyTask.pkl` and the B2T '25 HDF5 files (read only). Nothing in this folder holds text or plain trial ids.

## What we built

| Done-when item (roadmap P6-10) | Where |
|---|---|
| (1) `training_data` field in the v0.2 manifest (`"none"` or sources + partitions, unit hashes, text hashes) | [`overlap.py`](../../src/fidetype/benchmark/overlap.py) `parse_declaration`; [`scorecard.py`](../../src/fidetype/benchmark/scorecard.py) `parse_manifest`, `manifest_dict` |
| (2) Hash-only map B2T '25 HDF5 trial -> `b2t25-t15` unit | [`splits/overlap-maps/b2t25-t15__b2t25-hdf5.json`](../../src/fidetype/benchmark/splits/overlap-maps/b2t25-t15__b2t25-hdf5.json), built by [`build_map.py`](build_map.py) |
| (3) `score` warns; the board marks the entry | card key `overlap_check`, a `WARNING` note, a stderr warning, `--fail-on-overlap`; board marks `[TRAIN/TEST OVERLAP: n/N units]` and `[overlap not checked]` |
| (4) docs/benchmark-tracks.md says which HDF5 trials to leave out | [section](../../docs/benchmark-tracks.md#train--test-overlap-b2t25-t15-and-the-hdf5-files); command `overlap-list` |
| (5) A test checks the warning | [`tests/test_benchmark_overlap.py`](../../tests/test_benchmark_overlap.py) (9 tests, synthetic data + committed hash files) |

The field is "required" in this sense: without it the card says `not checked` (never `pass`) and the board marks the entry. The scorer does not refuse such a manifest, so older submission folders still score. A refusal would need a new submission schema version.

## The map reproduces the audit

| Count | Map (this run) | T15 split audit (2026-11-17) |
|---|---|---|
| Test units with a strict match in HDF5 `train` / `val_select` / `val_eval` / `test` | 366 / 102 / 98 / 109 | 366 / 102 / 98 / 109 |
| Same, strict + possible | 368 / 106 / 103 / 214 | "up to 368" / "<= 106" / "<= 103" / n/a |
| Test units whose sentence is in HDF5 `train` (any day) | 428 | 428 |
| HDF5 trials to leave out (train / val / test) | 368 / 209 / 233 = 810 | n/a |

Counts: [`results/map-counts.json`](results/map-counts.json). `overlap-list` on our copy finds all 810 trials of the map.

## Check on the committed entries

Script: [`retro_check.py`](retro_check.py). Output: [`results/retro-check.json`](results/retro-check.json). The cards have no `training_data` field, so we wrote one declaration per entry family from the card text and the experiment pages. No truth was read: track partitions are checked by id. The HDF5 map also gives the text check. **No card was changed.**

| Entries | Declared (our reading) | Result |
|---|---|---|
| `b2t25-t15__m4-12__guard`, `b2t25-t15__m4-13__guard` (103 units, partial) | train: HDF5 `train`; tune: HDF5 `val_select`; calibration: HDF5 `val_select` minus test matches | **overlap: 16 / 103 units, kind `text`** (same sentence as an HDF5 `train` trial). id 0, possible id 0 |
| `b2t25-t15__ours__*` (4), `b2t25-t15__published__*` (4) | train: published online RNN of Card et al. 2024 (training blocks not mapped); tune / calibration: track `cal` | **not checked** (the published decoder's training data do not resolve). Track `cal`: id 0 |
| `b2t24-t12` (2), `willett-hw` (2), `kt-semg` (2), `spanishbcbl-meg` (4), `toronto-semg` (9), `emg2qwerty` (7) | track `train` (willett: `train` + `val`); calibration on `cal` or `val`; external LM text where used | pass (ids only, text not compared) |

> **Our take:** the id results for the full-coverage entries follow from the split rules: a test unit is never in `train`, `val` or `cal`. The check only adds value there when an entry declares text hashes or unit ids. The real finding is the text overlap of the M4 entries. The M4 decoders trained on 16 trials that have the same sentence as a scored unit, but are other trials (other days). This is how the copy task works: 428 of the 816 test sentences occur in HDF5 `train`. So even the P6-09 retrain (HDF5 `train` minus the 810 matched trials) would fail a strict text rule on 428 units. The benchmark needs a rule for sentences that repeat by design. We propose a new gap for it. We did not change the M4 cards.

## Commands

```bash
set OMP_NUM_THREADS=2
.venv\Scripts\python.exe -I experiments/2026-11-21-p6-10-overlap-check/build_map.py      # 4 s
.venv\Scripts\python.exe -I experiments/2026-11-21-p6-10-overlap-check/retro_check.py    # 2 s
.venv\Scripts\python.exe -m fidetype.benchmark overlap-list --hdf5 C:\Users\zhang\bci-data\brain-to-text-25\neural\extracted\hdf5_data_final > leave_out.tsv   # local file
```
