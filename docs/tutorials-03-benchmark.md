# Tutorial 3: score a decoder on the benchmark

Time: about 1 s (synthetic mode), about 50 s (real data, one test run). Script: [`tutorials/03_score_benchmark.py`](../tutorials/03_score_benchmark.py). Index: [tutorials](tutorials.md).

At the end you can write a benchmark submission (format v0.2) with its two required controls, check it, score it with the one-command scorer, read the score card, and see the leaderboard row of your entry.

## Run it

```sh
python tutorials/03_score_benchmark.py                       # synthetic mode
```

The last line is `TUTORIAL 3 PASS (synthetic): card status scored, ...`.

## What the synthetic mode does

It uses the track `kt-semg` (forearm sEMG typing; the text is W3C `KeyboardEvent.code` names, so CER is the key error rate).

> **The synthetic "decoder" is a simulation, not a decoder.** It copies the true keys and replaces some of them at random. We use it because this tutorial teaches the format and the scorer, not decoding. Its numbers are toy numbers on a fake split. They are **not comparable** with the leaderboard.

| Step | Code | What you see |
|---|---|---|
| 1. Fake data and split | `write_fake_kt()`, `TR.local_units()`, `TR.make_split()` | 12 fake runs (key logs only, no EMG): 3 train, 3 cal, 6 test runs; 60 scored test units |
| 2. Truth | rows from `TR.select_units(split, units, "test")` and `TR.id_hash()` | One row per scored unit, keyed by the salted unit hash. Local only: never commit or share it |
| 3. Decode | `SC.unit_row(key, [top1, top2], scores, action=...)` | One row per unit on real input, on time-shuffled input and on all-zero input |
| 4. Submission | `SC.manifest_dict(...)`, `SC.write_submission(...)` | `submission.json`, `units.jsonl`, `controls/shuffled.jsonl`, `controls/zeros.jsonl` |
| 5. Check | `SC.check_submission(track, folder, split)` | Format, unit keys and controls are complete. No truth needed |
| 6. Score | `SC.score(track, folder, truth, split=split)`, `SC.score_card_text(card)` | Key error, eWPM vs the no-BCI reference (with CIs), safe WPM, wrong-commit rate, error among commits, commit rate, controls, coverage, status `scored` |
| 7. Rank | `leaderboard.row(card)`, `leaderboard.cells(row)` | The row that the leaderboard would show |

Synthetic score card (2026-11-20; toy numbers):

```text
kt-semg  kt-semg/tutorial-simulated/commit-if-clean  (60 units; CI unit run)
  key error 0.225 [0.175, 0.278]
  eWPM 6.05 [5.14, 6.90]   no-BCI 4.19 [4.11, 4.26]   difference 1.86 [0.96, 2.67]
  safe WPM: n/a (not-certified)
  wrong-commit 0.050 [0.017, 0.083]   error among commits 0.250 [0.067, 0.500]   commit rate 0.200 [0.100, 0.267]
  controls: shuffled pass, zeros pass, null-commit pass (0.000)
  coverage 60/60   status: scored
```

The safe WPM is `n/a (not-certified)`: the simple policy "commit if clean" has no CRC / LTT bound. A guard from [tutorial 2](tutorials-02-trust.md) gives one.

The required controls: `shuffled` and `zeros` must each give a higher top-1 CER than real input, and the commit rate on zeros must be at most 5 %. Without them, the status is `scored: controls missing` and the scorer exits with code 1.

## Real data

| What | Value |
|---|---|
| Dataset | KT-sEMG v1.1, copyright 2021 Nokia, CC BY 4.0 ([doi:10.7910/DVN/AV6XIR](https://doi.org/10.7910/DVN/AV6XIR)) |
| Download size | the full dataset, about 20 GB (all `runN.csv`, `runN_keys.txt`, `runN_ts.txt`) |
| Model | `kt-semg-lda` and its guard (release files, not hosted yet: gap 98) |
| Split | the committed `kt-semg` split; the truth is rebuilt from your download with `SC.build_truth()` and checked against it |

```sh
python tutorials/03_score_benchmark.py --data <kt-semg folder> --weights <kt-semg-lda folder> --runs run28
```

The script decodes the test runs that you name (default: the first one) and declares a partial entry (`coverage.subset`). Controls: the EMG circularly shifted by half the run (`shuffled`) and all-zero EMG (`zeros`).

Output on the project machine (2026-11-20, 47 s): 22 of 172 units (run28), key error 0.748, eWPM 2.55 (no-BCI 2.82), 0 commits, safe WPM 0.00 `vacuous`, all controls pass, status `scored`. The CIs are one point wide, because one run is one CI cluster. The decoder is weak (about one key in four is right); the guard offers and never commits, which is correct for this decoder. In a clone, step 6 also prints the committed `kt-semg` entries, so you see your row next to them with the mark `[partial: 22/172 units]`.

To submit from the command line instead of Python, see [benchmark submission](benchmark-submission.md) (`python -m fidetype.benchmark check | truth | score`).

## API friction (found while writing this tutorial)

These points are open gap 131 (roadmap P14-46).

- `build_truth()` always reads the committed split. With your own split (a new dataset, or this synthetic mode) you build the truth rows by hand; the tests monkeypatch `load_split`.
- The pretrained decoder and the benchmark use different text spaces: `kt-semg-lda` gives screen text in its n-best, and the track wants key codes. No converter exists, so the tutorial submits the greedy keys only.
- The guarantee from a guard sheet (`guarantee_from_sheet`) is not a valid submission guarantee: the manifest also needs `scope` and `calibration_split`.
- `build_truth("kt-semg")` needs every `runN.csv` file (about 20 GB), although the truth uses only the key logs and the start times.
- The committed leaderboard cards are in the git repository, not in the package, so `pip install` users cannot compare their row with the leaderboard offline.
