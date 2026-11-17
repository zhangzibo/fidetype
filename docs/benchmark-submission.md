# Benchmark submission format v0.2 and the scorer

This page defines how you submit a result on a [v0.2 benchmark track](benchmark-tracks.md) and how one command scores it (roadmap item P6-02).

- Code: [`src/fidetype/benchmark/scorecard.py`](../src/fidetype/benchmark/scorecard.py) (format, truth, scorer). The metrics come from [`scoring.py`](../src/fidetype/benchmark/scoring.py) and [`safe_wpm.py`](../src/fidetype/benchmark/safe_wpm.py).
- Tests: [`tests/test_benchmark_scorer.py`](../tests/test_benchmark_scorer.py) (synthetic data only).
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
| `nbest` | `nbest[0].text` is your top-1 text (used for CER and WER, for every action). `nbest[:offer_k]` are the choices of an OFFER. A commit or an offer needs at least one item |
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

**NTS streams instead of rows.** You can give `streams/<unit>.jsonl` (or `.npz`) files instead of `units.jsonl`. The file name is the unit key. The scorer reads the last final `hypothesis` event as in v0.1 ([benchmark README](../benchmark/README.md)), and it runs the conformance suite on each file (`--gate` rejects files below `trust-ready`).

### `submission.json`

Schema `fidetype.benchmark.submission/0.2`. All v0.1 fields stay. New fields: `regime` and `controls` (required), `coverage` (optional).

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
 "submitter": {"name": "...", "contact": "..."},
 "notes": "..."
}
```

| Field | Rule |
|---|---|
| `regime` | `cross-session`, `session-calibrated`, `cross-subject`, `personalised` or `other` |
| `controls` | One sentence per control: how you made the input. Say if the control is at the input level (signal) or at the decoder output level (a stand-in) |
| `coverage` | Leave it out if you cover every scored unit. With `{"subset": "<reason>"}` the scorer accepts missing units, scores only the covered ones, and the board marks the entry `[partial: n/N units]` |
| `guarantee` | As v0.1. Safe WPM is certified only for `crc` or `ltt` with `alpha` |

## What the scorer checks

1. The manifest (schema, track, decoder licence, regime, guarantee fields).
2. Every unit key is a scored unit of the track (test split). No duplicates. The key form fits the track.
3. Every scored unit has an output, unless `coverage.subset` is declared.
4. The truth matches the split: for every truth row, the id hash, the fingerprint and the group hash must equal the split entry. A changed or other dataset version is refused.
5. The controls: present, complete (same units as the real run), and passing.

## The score card

| Item | Definition |
|---|---|
| CER / WER (key error on key tracks) | Edit distance of `nbest[0]` over the truth length, pooled over units |
| eWPM, no-BCI eWPM, difference | Simulated user `aac-gaze-v1` at the track rate; no-BCI = gaze typing at 20 chars/min |
| Safe WPM @ alpha | [safe WPM](safe-wpm.md): committed exactly-right words per minute with a correction penalty, only under a certified CRC / LTT bound. Status `certified`, `above-alpha`, `vacuous` or `not-certified` |
| Wrong-commit | Wrong commits / all units (the quantity CRC / LTT control) |
| Error among commits | Wrong commits / commits |
| Commit rate | Commits / all units |
| CIs | Percentile cluster bootstrap (B = 2000, seed 0) over the track CI unit (the split group: day, session, participant, run or user; MEG: sentence x participant) |
| Controls | `shuffled` and `zeros` pass if their top-1 CER is higher than on real input (lower 95 % bound of the paired gap > 0). `null_commit` passes if the commit rate on zeros is at most 5 % |
| Timing | Measured per unit from the truth where the track has it (speech duration, neural bins, key times). Else the track rate model. The submission cannot set it |
| Status | `scored` only if all three controls pass; else `scored: controls missing` or `scored: controls failed` |

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

> **Our take:** the controls are the part that makes a number believable. A decoder that commits on zero input, or whose CER does not get worse on shuffled input, does not decode the signal. So the exit code is 1 until both controls are there and pass.

## Versioning

The format and the scorer are version 0.2 (`SCORER_VERSION`). A change to a rule, a normaliser or a rate gives a new version; old cards keep their version field.
