# Tutorial 3: score a decoder on the benchmark

Write a benchmark submission with its required controls, score it and read the score card.

**Status:** Alpha ([status levels](glossary.md#status-levels)). The benchmark format can still change.

Time: about 1 s (synthetic mode), about 50 s (real data, one test run). Script: [`tutorials/03_score_benchmark.py`](../tutorials/03_score_benchmark.py). Index: [tutorials](tutorials.md).

At the end you can write a benchmark submission (format v0.2) with its two required controls, check it, score it with the one-command scorer, read the score card, and see the leaderboard row of your entry.

## Run it

```sh
python tutorials/03_score_benchmark.py                       # synthetic mode
```

The last line is `TUTORIAL 3 PASS (synthetic): card status scored, ...`.

## What the synthetic mode does

It uses the track `kt-semg` (forearm [sEMG](glossary.md#eeg-meg-emg-semg) typing from the [KT-sEMG](glossary.md#kt-semg) dataset; the text is W3C `KeyboardEvent.code` names, so [CER](glossary.md#cer-wer) is the key error rate).

> **The synthetic "decoder" is a simulation, not a decoder.** It copies the true keys and replaces some of them at random. We use it because this tutorial teaches the format and the scorer, not decoding. Its numbers are toy numbers on a fake split. They are **not comparable** with the leaderboard.

| Step | Code | What you see |
|---|---|---|
| 1. Fake data and split | `write_fake_kt()`, `TR.local_units(track, folder, keys_only=True)`, `TR.make_split()` | 12 fake runs (key logs and start times only, no EMG files): 3 train, 3 cal, 6 test runs; 60 scored test units |
| 2. Truth | `SC.build_truth(track, folder, split=split)` | One row per scored unit, keyed by the salted unit hash. Local only: never commit or share it |
| 3. Decode | `SC.unit_row(key, [top1, top2], scores, action=...)` | One row per unit on real input, on time-shuffled input and on all-zero input |
| 4. Submission | `SC.manifest_dict(...)`, `SC.write_submission(...)` | `submission.json`, `units.jsonl`, `controls/shuffled.jsonl`, `controls/zeros.jsonl` |
| 5. Check | `SC.check_submission(track, folder, split)` | Format, unit keys and controls are complete. No truth needed |
| 6. Score | `SC.score(track, folder, truth, split=split)`, `SC.score_card_text(card)` | Key error, eWPM vs the no-BCI reference (with CIs), safe WPM, wrong-commit rate, error among commits, commit rate, controls, coverage, status `scored` |
| 7. Rank | `leaderboard.row(card)`, `leaderboard.cells(row)` | The row that the leaderboard would show. Real mode adds the committed cards: `leaderboard.committed_results("v0.2")` (in the package, so it also works after `pip install`) |

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

The safe WPM is `n/a (not-certified)`: the simple policy "commit if clean" has no certified bound (CRC or [LTT](glossary.md#ltt-learn-then-test)). A guard from [tutorial 2](tutorials-02-trust.md) gives one.

The required controls: `shuffled` and `zeros` must each give a higher top-1 CER than real input, and the commit rate on zeros must be at most 5 %. Without them, the status is `scored: controls missing` and the scorer exits with code 1.

## Real data

| What | Value |
|---|---|
| Dataset | KT-sEMG v1.1, copyright 2021 Nokia, CC BY 4.0 ([doi:10.7910/DVN/AV6XIR](https://doi.org/10.7910/DVN/AV6XIR)) |
| Download size | the truth needs only `runN_keys.txt` and `runN_ts.txt` (small). Decoding needs the `runN.csv` EMG file of each run that you decode (the full dataset is about 20 GB) |
| Model | `kt-semg-lda` and its guard (release files, not hosted yet; [details](tutorials.md#where-the-weights-come-from)) |
| Split | the committed `kt-semg` split; the truth is rebuilt from your download with `SC.build_truth()` (key logs only) and checked against it |

```sh
python tutorials/03_score_benchmark.py --data <kt-semg folder> --weights <kt-semg-lda folder> --runs run28
```

The script decodes the test runs that you name (default: the first one) and declares a partial entry (`coverage.subset`). Each row has the top 3 of `model.track_nbest(stream)` (key codes, the track text space) and the guard action of `model.decide(stream)`. The guarantee block is `guarantee_from_sheet(guard, calibration_split="cal")`. Controls: the EMG circularly shifted by half the run (`shuffled`) and all-zero EMG (`zeros`).

Output on the project machine (2026-11-21; 48.2 s, pinned to 2 CPUs):

```text
kt-semg  kt-semg/kt-semg-lda (tutorial 3)/packaged guard  (22 units; CI unit run)
  key error 0.748 [0.748, 0.748]
  eWPM 2.40 [2.40, 2.40]   no-BCI 2.82 [2.82, 2.82]   difference -0.42 [-0.42, -0.42]
  safe WPM @ 0.05: 0.00 (vacuous)
  wrong-commit 0.000 [0.000, 0.000]   error among commits n/a   commit rate 0.000 [0.000, 0.000]
  controls: shuffled pass, zeros pass, null-commit pass (0.000)
  coverage 22/172 (partial)   status: scored
```

| Value | Result |
|---|---|
| Truth | 172 scored test units in runs 24-29, rebuilt from the key logs and start times only |
| Decoded | run28: 22 bursts, 22 scored units covered |
| Actions | 22 offers (top 3 key-code texts each), 0 commits, 0 withholds |
| Offers with the true text in the list | 0 / 22 |
| Controls | shuffled key error 0.877, zeros 0.882 (both higher than 0.748: pass); commit rate on zeros 0.000 (pass) |
| Guarantee | LTT, alpha 0.05, delta 0.1, 65 calibration items, `scope` and `calibration_split` set |

The CIs are one point wide, because one run is one CI cluster. The decoder is weak (about one key in four is right). The guard offers and never commits, which is correct for this decoder. Step 6 also prints the committed `kt-semg` entries, so you see your row next to them with the mark `[partial: 22/172 units]`.

Checks of this run against the committed cards:

- The new truth (key logs only) is equal to the truth file that made the committed `kt-semg` cards: the same 172 units, and no row differs in any field.
- With the new truth, the committed submissions `kt-semg__lda-oracle__guard` and `kt-semg__lda-oracle__always-commit` rescore to their committed cards (metrics, controls, safe WPM, coverage, status: equal).
- The key error (0.748) is the same as before the API fixes below. The eWPM went from 2.55 to 2.40. Reason: the rows now offer the top 3 texts of `track_nbest()`, not only the greedy text. All 3 are wrong, and the simulated user reads each one before it types the text. When we cut the same submission to the top 1 text, the eWPM is 2.55 again. So the change is expected, not a bug.
- Bug found and fixed: `card.json` held the token `NaN` (error among commits, no commits), which is not valid JSON. The tutorial now writes the card as the scorer CLI does (`to_jsonable`: NaN becomes `null`). Test: `tutorials/test_tutorials.py::test_tutorial3_card_json_is_strict_json`.

To submit from the command line instead of Python, see [benchmark submission](benchmark-submission.md) (`python -m fidetype.benchmark check | truth | score`).

## API friction (found while writing this tutorial)

A newcomer test of this tutorial found these points. The API now has a fix for each one, and this tutorial uses them:

| Friction | Fix |
|---|---|
| `build_truth()` always read the committed split | `SC.build_truth(track, data, split=...)` (default: the committed split) |
| `kt-semg-lda` gives screen text in its n-best; the track wants key codes | `model.track_nbest(stream)` (key codes, `Backspace` kept); `fidetype.adapters.kt_semg.code_nbest(stream)` for any key stream; `codes_from_text(text)` converts screen text (lossy: no `Backspace`) |
| `guarantee_from_sheet()` gave no `scope` | it adds `scope` (default "marginal over decisions exchangeable with the calibration items"); `calibration_split=` names the benchmark split; it also takes the guard itself |
| `build_truth("kt-semg")` needed every `runN.csv` (about 20 GB) | the truth reads only `runN_keys.txt` and `runN_ts.txt` (`keys_only=True` is the default in `build_truth`; `verify` still checks the CSVs) |
| The committed leaderboard cards were not in the package | they ship in the wheel: `leaderboard.committed_results("v0.2")`, `leaderboard.results_dir()` |
