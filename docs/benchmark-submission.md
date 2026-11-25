# Benchmark submission format v0.2 and the scorer

How to submit a result on a benchmark track, and how one command scores it into a score card.

**Status:** Alpha ([status levels](glossary.md#status-levels))

This page defines how you submit a result on a [v0.2 benchmark track](benchmark-tracks.md) and how one command scores it.

- Code: [`src/fidetype/benchmark/scorecard.py`](../src/fidetype/benchmark/scorecard.py) (format, truth, scorer). The metrics come from [`scoring.py`](../src/fidetype/benchmark/scoring.py) and [`safe_wpm.py`](../src/fidetype/benchmark/safe_wpm.py).
- Tests: [`tests/test_benchmark_scorer.py`](../tests/test_benchmark_scorer.py) and [`tests/test_benchmark_overlap.py`](../tests/test_benchmark_overlap.py) (synthetic data only).
- Train / test overlap check: [`src/fidetype/benchmark/overlap.py`](../src/fidetype/benchmark/overlap.py). See [Train / test overlap check](#train--test-overlap-check).
- Baselines: [`experiments/2026-11-16-p6-02-scorer/results.md`](../experiments/2026-11-16-p6-02-scorer/results.md). v0.2 entries for b2t25-t15, toronto-semg and spanishbcbl-meg (v0.1 decoders rerun in this format): [`experiments/2026-11-17-p6-02b-v02-entries/results.md`](../experiments/2026-11-17-p6-02b-v02-entries/results.md). Score cards: [`benchmark/results/v0.2/`](../benchmark/results/v0.2/). Board: [`benchmark/site/`](../benchmark/site/).

## The three commands

```bash
# 1. Check the submission against the committed split file. No data needed.
python -m fidetype.benchmark check <track> <submission>

# 2. Rebuild the truth from your own download (local file with truth text: never commit it).
python -m fidetype.benchmark truth <track> --data <path> --out truth.jsonl

# 3. Score: validate, check the required controls, print the score card.
python -m fidetype.benchmark score <track> <submission> --truth truth.jsonl --out card.json
python -m fidetype.benchmark score <track> <submission> --data <path>          # same, truth rebuilt on the fly
```

`<track>` is one of `b2t25-t15`, `b2t24-t12`, `willett-hw`, `toronto-semg`, `kt-semg`, `spanishbcbl-meg`, `emg2qwerty`. `--data` is the same path as for `verify` ([benchmark tracks](benchmark-tracks.md)). The v0.1 form `score <submission> --truth ...` still works for the v0.1 tracks.

From Python:

| Need | Call |
|---|---|
| Truth for your own split (a new dataset, a synthetic test) | `scorecard.build_truth(track, data, split=my_split)`; pass the same split to `check_submission` and `score` |
| `kt-semg` truth without the EMG files | `build_truth("kt-semg", data)` needs only `runN_keys.txt` and `runN_ts.txt` (the CLI `truth` too). `verify` still needs every `runN.csv` |
| A guarantee block from a drop-in guard | `safe_wpm.guarantee_from_sheet(guard, calibration_split="cal")`: it has `scope` (default "marginal over decisions exchangeable with the calibration items"), so it is valid in `submission.json` |
| `kt-semg` rows from `kt-semg-lda` | `model.track_nbest(stream)`: n-best texts in key codes (the track text space) |
| The committed cards, offline | `leaderboard.committed_results("v0.2")` (they ship in the wheel; `leaderboard.results_dir()` gives the folder) |

| Exit code | Meaning |
|---|---|
| 0 | Scored. All required controls are present and pass |
| 1 | Scored, but a required control is missing or fails. The card says which |
| 2 | Rejected: the submission breaks the format or does not match the split |

## The submission folder

```
my-entry/
  submission.json          the manifest
  units.jsonl              one row per scored unit        (or streams/<unit>.jsonl, one NTS stream per unit)
  controls/shuffled.jsonl  the same decoder + policy on time-shuffled input
  controls/zeros.jsonl     the same decoder + policy on all-zero (null) input
```

### Unit keys

Every row names its unit with the **salted unit hash** `h` of the track split file (`src/fidetype/benchmark/splits/tracks-v0.2/<track>.json`). Use the entries of the scored unit set with split `test`. `python -m fidetype.benchmark.tracks select <track> --data <path> --split test` gives you the local id of each unit; `fidetype.benchmark.tracks.id_hash(track, local_id)` gives its key.

| Track | Scored unit | Key |
|---|---|---|
| `b2t25-t15`, `b2t24-t12`, `willett-hw`, `spanishbcbl-meg` | trial | `h` |
| `toronto-semg` | composed sentence | `h` |
| `kt-semg` | typing burst (segment) | `h` |
| `emg2qwerty` | prompt inside a test session | `<session h>#<prompt index>` (prompts with >= 3 in-vocabulary key presses) |

### One row of `units.jsonl`

```json
{"unit": "3f9c0b6a1d2e4f58", "action": "commit",
 "nbest": [{"text": "the decoded text", "score": 0.93}, {"text": "the decoded test", "score": 0.04}],
 "offer_k": 3, "score_semantics": "calibrated_prob", "latency_s": 0.31}
```

| Key | Rule |
|---|---|
| `unit` | Required. The unit key |
| `action` | `commit`, `offer` or `abstain` (default `commit`): the decision of your trust policy |
| `nbest` | `nbest[0].text` is your top-1 text (used for [CER and WER](glossary.md#cer-wer), for every action). `nbest[:offer_k]` are the choices of an OFFER. A commit or an offer needs at least one item |
| `offer_k` | Optional. The number of shown choices (default 3) |
| `score_semantics`, `latency_s` | Optional. `latency_s` is your decision latency; the card reports its median and p95 |
| `x-...` | Optional. Your own keys |

Any other key is refused. So a row cannot carry truth text by accident (NTS spec 5.3, leakage rule). The first line may be a header `{"schema": "fidetype.benchmark.units/0.2", "track": ..., "kind": "real"}`. The helper `fidetype.benchmark.scorecard.write_submission(folder, manifest, rows, controls)` writes all files.

**Text space.** Write the text as the track compares it:

| Track | Text | Normaliser of the scorer |
|---|---|---|
| `b2t25-t15`, `b2t24-t12` | words | lower case, punctuation as in the v0.1 B2T track |
| `willett-hw`, `toronto-semg` | characters | whitespace collapsed |
| `spanishbcbl-meg` | characters | `char28` (as v0.1) |
| `kt-semg`, `emg2qwerty` | space-separated W3C `KeyboardEvent.code` names, for example `KeyH KeyI Space` | one character per key, so **CER = key error rate** |

**Scoring target (`emg2qwerty` only).** The manifest field `target` selects what the scorer compares. Both sides (truth and every output text) go through the same normaliser, and the no-BCI reference and safe WPM use the same target text.

| `target` | Version | Normaliser | What is compared |
|---|---|---|---|
| `raw_keys` (default) | `raw-keys/1` | `keycodes` | The key sequence as typed. `Backspace` and `Enter` are keys. CER = key error rate |
| `intended_text` | `intended-text/1` | `keycodes_intended` | The text the typist meant. CER = character error rate of that text |

Rule `intended-text/1` (`fidetype.benchmark.registry.keycodes_to_intended_text`), left to right over the key codes:

1. A character key appends its character. `Space` appends a space.
2. `Backspace` removes the last character, if there is one. A leading `Backspace` does nothing.
3. `Enter` is ignored.
4. At the end, runs of spaces become one space, and the ends are stripped.

Examples: `KeyH KeyX Backspace KeyI` -> `hi`; `Backspace KeyA` -> `a`; `KeyH KeyI Space Backspace KeyO` -> `hio`. This is the same rule as the code of our emg2qwerty experiments (a test checks this). Write the outputs as key codes in both cases: an intended text `hi o` is `KeyH KeyI Space KeyO`. A raw-key output is also valid under `intended_text`: the scorer applies the rule to it.

A manifest without `target` scores exactly as before, with the default. On tracks with one target, `target` must be absent. A card from a manifest with `target` has a `target` block (name, version, normaliser, rule). The leaderboard never ranks the two targets in one table: each target gets its own table and its own no-BCI reference, and an `intended_text` entry carries `[target: intended_text]` in its name. Cards without a `target` block count as `raw_keys`.

Known limit: the eWPM user model keeps the track rate (301.33 keys/min) for the neural time of both targets. Safe WPM does not use it: it uses the measured `neural_s` of each prompt.

**NTS streams instead of rows.** You can give `streams/<unit>.jsonl` (or `.npz`) files instead of `units.jsonl`. The file name is the unit key. The scorer reads the last final `hypothesis` event as in v0.1 ([benchmark README](../benchmark/README.md)), and it runs the conformance suite on each file (`--gate` rejects files below `trust-ready`).

### `submission.json`

Schema `fidetype.benchmark.submission/0.2`. All v0.1 fields stay. New fields: `regime` and `controls` (required), `training_data` (required for a checked entry), `coverage` and `target` (optional).

```json
{
 "schema": "fidetype.benchmark.submission/0.2",
 "track": "b2t24-t12",
 "benchmark_version": "0.2",
 "decoder": {"name": "...", "version": "...", "url": "...", "weights_licence": "...",
             "training_data": ["..."], "training_regime": "..."},
 "policy": {"name": "...", "description": "..."},
 "guarantee": {"method": "ltt", "alpha": 0.05, "delta": 0.1, "n_cal": 293,
               "scope": "marginal over test trials", "calibration_split": "cal"},
 "regime": "cross-session",
 "controls": {"shuffled": "how the shuffled input was made", "zeros": "how the null input was made"},
 "coverage": {"subset": "why some units have no output"},
 "training_data": {"sources": [{"dataset": "b2t24-t12", "partitions": ["train"], "use": "train"},
                               {"dataset": "b2t24-t12", "partitions": ["cal"], "use": "calibration"}]},
 "submitter": {"name": "...", "contact": "..."},
 "notes": "..."
}
```

| Field | Rule |
|---|---|
| `regime` | `cross-session`, `session-calibrated`, `cross-subject`, `personalised` or `other` |
| `controls` | One sentence per control: how you made the input. Say if the control is at the input level (signal) or at the decoder output level (a stand-in) |
| `coverage` | Leave it out if you cover every scored unit. With `{"subset": "<reason>"}` the scorer accepts missing units, scores only the covered ones, and the board marks the entry `[partial: n/N units]` |
| `guarantee` | As v0.1. [Safe WPM](glossary.md#safe-wpm) is certified only for `crc` or `ltt` ([LTT](glossary.md#ltt-learn-then-test)) with `alpha` ([alpha](glossary.md#alpha-delta)). If the scored units come from several users, sessions or days, say in `scope` that the bound covers the pool and not each user, session or day ([trust guarantee, section 4](trust-guarantee.md#4-what-is-not-guaranteed)) |
| `target` | `emg2qwerty` only: `raw_keys` (default) or `intended_text` (see the text space above). Leave it out on every other track |
| `training_data` | `"none"`, or the data that the decoder, its tuning and its calibration used. See [Train / test overlap check](#train--test-overlap-check). Without it the card says `overlap: not checked` and the board marks the entry `[overlap not checked]` |

## What the scorer checks

1. The manifest (schema, track, decoder licence, regime, guarantee fields).
2. Every unit key is a scored unit of the track (test split). No duplicates. The key form fits the track.
3. Every scored unit has an output, unless `coverage.subset` is declared.
4. The truth matches the split: for every truth row, the id hash, the fingerprint and the group hash must equal the split entry. A changed or other dataset version is refused.
5. The controls: present, complete (same units as the real run), and passing.
6. The train / test overlap: the declared `training_data` against the scored units. `check` compares unit ids and partitions. `score` also compares the text. An overlap gives a warning. It does not change a number or the status.

## The score card

| Item | Definition |
|---|---|
| CER / WER (key error on key tracks) | Edit distance of `nbest[0]` over the truth length, pooled over units |
| eWPM, no-BCI eWPM, difference | Simulated user `aac-gaze-v1` at the track rate; no-BCI = gaze typing at 20 chars/min |
| Safe WPM v0.2 @ alpha (headline), Safe WPM v0.1 @ alpha | [safe WPM](safe-wpm.md): committed right words per minute with a correction penalty, only under a certified CRC / LTT bound. Status `certified`, `above-alpha`, `vacuous` or `not-certified`. v0.2 (adopted 2026-11-22; card block `safe_wpm_v02`) adds prefix credit and a reading cost of 0.5 s + 0.3 s per committed word per commit. v0.1 (card block `safe_wpm`) is the earlier rule |
| Wrong-commit | Wrong commits / all units (the quantity CRC / LTT control) |
| Error among commits | Wrong commits / commits |
| Commit rate | Commits / all units |
| CIs | Percentile cluster bootstrap (B = 2000, seed 0) over the track CI unit (the split group: day, session, participant, run or user; MEG: sentence x participant) |
| Controls | `shuffled` and `zeros` pass if their top-1 CER is higher than on real input (lower 95 % bound of the paired gap > 0). `null_commit` passes if the commit rate on zeros is at most 5 % |
| Timing | Measured per unit from the truth where the track has it (speech duration, neural bins, key times). Else the track rate model. The submission cannot set it |
| Status | `scored` only if all three controls pass; else `scored: controls missing` or `scored: controls failed` |
| Overlap check | Key `overlap_check`: `status` (`pass`, `overlap` or `not checked`), `passed` (true, false or null), `n_overlapping_units`, `by_kind`, `by_use` and one finding per source and partition. See below |

The card holds no text. Research-only tracks (`spanishbcbl-meg`, `emg2qwerty`) carry a `RESEARCH ONLY` note, and the board marks them.

### Track rate model (eWPM neural input rate)

| Track | Rate | Source |
|---|---|---|
| `b2t25-t15` | 159.27 chars/min | measured T15 speech rate (v0.1) |
| `b2t24-t12` | 303.98 chars/min | measured T12 speech rate of the decoder-train trials |
| `willett-hw` | 67.64 chars/min | measured: characters / (go cue to sentence end), 254 test trials |
| `toronto-semg` | 75.76 chars/min | one key per 0.792 s (v0.1) |
| `kt-semg` | 390.56 keys/min | measured key times of the 172 test bursts |
| `spanishbcbl-meg` | 152 chars/min | Brain2Qwerty v1 typing rate (v0.1) |
| `emg2qwerty` | 301.33 keys/min | measured: keys / (first to last key-down time), 15 867 test prompts |

## Train / test overlap check

An entry must not be scored on units that it trained on, tuned on or calibrated on. The scorer checks this from the `training_data` field of `submission.json`. The check is version `overlap-check/1`.

### The declaration

```json
"training_data": "none"
```

Use `"none"` only if the decoder, its tuning and its calibration used no data of this dataset.

```json
"training_data": {
 "sources": [
  {"dataset": "b2t25-hdf5", "partitions": ["train"], "use": "train", "exclude": "track-test-matches"},
  {"dataset": "b2t25-t15", "partitions": ["cal"], "use": "calibration"},
  {"dataset": "tatoeba-en", "use": "train", "note": "char LM"}
 ],
 "unit_ids": {"tune": ["<16-hex unit hash>"]},
 "text_hashes": {"train": ["<16-hex text hash>"]},
 "file": "training_data.json"
}
```

| Key | Rule |
|---|---|
| `sources[].dataset` | The track slug or its dataset id: `partitions` are split names of the track split file (`train`, `val`, `cal`, `test`, `holdout`). `b2t25-hdf5` (track `b2t25-t15` only): the B2T '25 HDF5 neural files, partitions `train`, `val`, `test`, and our M4 halves `val_select`, `val_eval`. Any other name is *external* data |
| `sources[].use` | `train`, `tune` (model choice, hyper-parameters, checkpoints) or `calibration` (guard, CRC, LTT) |
| `sources[].exclude` | `b2t25-hdf5` only: `"track-test-matches"` (you left out every HDF5 trial that matches a test unit) or a list of HDF5 trial hashes |
| `unit_ids` | Unit hashes (the split `h`) per use. Use it for single trials |
| `text_hashes` | Salted hashes of the normalised sentences per use. Use it for text corpora, for example the text of a language model |
| `file` | Optional JSON file next to `submission.json` with more `unit_ids` and `text_hashes` (long lists) |

Make the hashes with one command. The input files are local. Never commit them.

```bash
python -m fidetype.benchmark overlap-hashes <track> --ids my_ids.txt --texts my_sentences.txt --use train --out hashes.json
```

### What the check compares

| Kind | How | Needs |
|---|---|---|
| `id` | Declared unit hashes, and the units of declared partitions, against the scored unit keys | nothing (`check` and `score`) |
| `possible id` | A declared HDF5 trial matches a test unit, but the match has more than one candidate | the committed map |
| `text` | The same normalised sentence: declared text hashes against the text hashes of the scored units (from the truth); for `b2t25-hdf5`, the committed map | the truth (`score`) or the map |

A track partition (for example `cal`) is checked by id only. To check its sentences too, add their `text_hashes`.

### The result

| `status` | `passed` | When |
|---|---|---|
| `pass` | true | No scored unit is in the declared data. `"none"` also gives `pass` |
| `overlap` | false | At least one scored unit is in the declared data. The card gets a `WARNING` note. The board marks the entry `[TRAIN/TEST OVERLAP: n/N units]` |
| `not checked` | null | No `training_data` field, or a source of this dataset does not resolve (an unknown partition). Never `pass` |

External sources (another dataset) do not stop a `pass`. The block lists them under `unchecked`. The check does not change any metric or the status. `score --fail-on-overlap` gives exit code 1 on `overlap`.

Example line of the card text:

```
  overlap: FAIL, 4/18 units (tune unit_ids id 4)
```

The B2T '25 HDF5 trials to leave out are in [benchmark tracks](benchmark-tracks.md#train--test-overlap-b2t25-t15-and-the-hdf5-files).

### Committed entries (checked 2026-11-21)

The cards in `benchmark/results/v0.2/` were scored before the overlap check existed, so they have no `overlap_check` block. We ran the check on them with declarations that we wrote from their `decoder.training_data` text (details: [overlap check record](../experiments/2026-11-21-p6-10-overlap-check/results.md)). By id, no entry overlaps. By text, the two entries `b2t25-t15__m4-12__guard.json` and `b2t25-t15__m4-13__guard.json` on `b2t25-t15` overlap: 16 of their 103 scored units have the same sentence as a trial in the HDF5 `train` partition. The cards stay as they are.

> **Our take:** the controls are the part that makes a number believable. A decoder that commits on zero input, or whose CER does not get worse on shuffled input, does not decode the signal. So the exit code is 1 until both controls are there and pass.

## Versioning

The format and the scorer are version 0.2 (`SCORER_VERSION`). A change to a rule, a normaliser or a rate gives a new version; old cards keep their version field.
