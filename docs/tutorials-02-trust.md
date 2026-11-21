# Tutorial 2: add the trust guard and read the safe WPM

Time: about 80 s (synthetic mode), about 50 s (real data, 65 trials). Script: [`tutorials/02_trust_and_safe_wpm.py`](../tutorials/02_trust_and_safe_wpm.py). Index: [tutorials](tutorials.md).

At the end you can calibrate a trust guard on your own decoder output, get COMMIT / OFFER / WITHHOLD for new utterances, read the guarantee sheet, and compute the safe WPM: words per minute that the system types right by itself, at a certified wrong-commit rate.

## Run it

```sh
python tutorials/02_trust_and_safe_wpm.py                    # synthetic mode
```

The last line is `TUTORIAL 2 PASS (synthetic): safe WPM status certified, ...`.

## What the synthetic mode does

A small simulated CTC decoder (`toy_decoder`) makes noisy scores for 16 short phrases. Each utterance gets a random noise level, so some outputs are wrong. Replace `toy_decoder` with your own model.

| Step | Code | What you see |
|---|---|---|
| 1. Labelled output | 400 `(T, 28)` logits + the true texts | The calibration set |
| 2. Calibrate | `ft.calibrate(logits, texts, vocab=..., blank="_", lexicon=..., alpha=0.05, delta=0.1)` | The guarantee sheet: P(wrong-commit rate <= 0.05) >= 0.9, the split 100 fit + 150 grid + 150 LTT, the commit threshold, both null controls `PASS`, assumptions, warnings |
| 3. Decide | `guard.decide(x, utterance_id=...)` | 300 new utterances. The run gave 111 commit, 0 offer, 189 withhold |
| 4. Safe WPM | `sw.from_decisions(results, truths, neural_s, guard)` | One line: value, status, test wrong-commit rate with its Clopper-Pearson 95 % interval, number of commits, unguarded WPM, no-BCI reference |
| 5. Keep | `guard.write_audit()`, `guard.save()`, `ft.load()` | The audit log (one record per decision) and the guard file (numbers only, no signal, no text) |

The safe WPM part:

```python
from fidetype.benchmark import safe_wpm as sw

rep = sw.from_decisions(results, truths, neural_s, guard,   # TrustResults, true texts, seconds of signal each
                        normalizer=None,                    # None: whitespace only; "words": the T15 track rule
                        timing="how neural_s was measured")
print(sw.format_line(rep))
```

The script also computes the report the old way (five lists, `guarantee_from_sheet`, `controls_from_sheet`) and checks that both reports are equal. It prints `same report as the manual route ...: True`, and the tutorial fails if they differ. Synthetic output (2026-11-20; the numbers change with the data): the status was `certified`, 0 wrong commits in 300, CP95 [0, 0.0122]. The value is a **toy number**. The toy decoder "speaks" 150 characters per minute (4 frames of 100 ms per character) and its errors are random. It says nothing about a real BCI.

How to read the status ([safe WPM definition](safe-wpm.md)):

| Status | Meaning |
|---|---|
| `certified` | The policy has a certified bound, and the measured wrong-commit rate is at or below alpha |
| `above-alpha` | Certified bound, but the measured rate on these trials is above alpha. The leaderboard marks such entries |
| `vacuous` | The policy committed nothing. Safe, but the value is 0 |
| `not-certified` | No CRC / LTT bound. `value` is None; `unguarded_wpm` is for reference only |

## Real data

| What | Value |
|---|---|
| Dataset | Brain-to-Text '25, participant T15, CC0 1.0 ([doi:10.5061/dryad.dncjsxm85](https://doi.org/10.5061/dryad.dncjsxm85), `t15_copyTask_neuralData.zip`) |
| Model and guard | `t15-m4-13` and its packaged guard `tcfg-1016759f08a3f9a1` (alpha 0.05, delta 0.1). The guard needs three text files (CMU dictionary, Tatoeba character 6-gram LM, Tatoeba word counts) next to the weights |
| Extra package | `pip install ".[hdf5]"` (gives `h5py`) |
| Weights | not hosted yet (gap 98): `--weights <folder>` or `FIDETYPE_PRETRAINED_DIR` |

```sh
python tutorials/02_trust_and_safe_wpm.py --model t15-m4-13 --weights <folder> \
    --data <b2t25>/t15.2023.08.13/data_val.hdf5 <b2t25>/t15.2023.08.18/data_val.hdf5 <b2t25>/t15.2023.08.20/data_val.hdf5
```

The script decodes the odd `val` trials (the `val_eval` half; the guard was calibrated on the even half), at most `--n` (25) per file. It counts the trials with `model.n_items(path)` and decides with `model.decide(stream, guard=guard)`. Neural time = trial length in 20 ms bins. A commit is right when its words equal the true words after the `words` normalisation of the benchmark (`normalizer="words"`).

Output on the project machine (2026-11-20, 48 s): 65 trials, 10 commit, 55 offer, 0 withhold; 5 wrong commits (0.0769, CP95 [0.0254, 0.1705]); safe WPM 1.49, status **`above-alpha`**; no-BCI reference 4.13.

> **Read this result with care.** 65 trials from the first three sessions are a small sample. The bound is on the rate over many utterances like the calibration data, not on every subset. On all 701 `val_eval` trials the same guard gives 104 commits, 17 wrong (0.0243, CP95 [0.0142, 0.0385]), safe WPM 2.23, status `certified` ([safe WPM](safe-wpm.md), P14-05). The tutorial shows the status that your sample gives; it does not hide it.

## API friction (found while writing this tutorial)

Gap 130 (roadmap P14-45) listed these points. `fidetype.benchmark.safe_wpm.from_decisions` fixes them, and this tutorial uses it:

| Friction | Fix |
|---|---|
| Five parallel lists by hand (committed, correct, words, characters, seconds) | `from_decisions(results, truths, neural_s, guard)` takes the `TrustResult`s, the true texts and the durations |
| The guard sheet went through two functions (`guarantee_from_sheet`, `controls_from_sheet`) | `from_decisions` reads the guarantee and the controls from the guard, its `GuaranteeSheet` or the sheet dict. Both functions also take a guard now |
| The comparison with the truth needed a separate choice of normaliser | `normalizer=`: `None` (whitespace only, the guard rule), a track normaliser name (for example `"words"`), or a callable. It also counts the words and characters |
