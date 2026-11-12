---
title: "Toronto sEMG typing dataset (Achituve et al. 2025, Borealis)"
type: source
tags: [dataset, emg, forearm, typing, keystroke, cc-by, licence-clean, cross-subject, trust-eval]
sources: [toronto-semg-typing]
updated: 2026-11-11
---

# Toronto sEMG typing dataset (`EMG typing dataset.zip`)

## Citation and links
- **Paper:** I. Achituve, Y. Beutel, J. Eby, E. Fetaya, D. Koivisto, J. Zariffa. "Electromyographic typing gesture classification dataset for neurotechnological human-machine interfaces." *Scientific Data* 12:440 (2025). https://doi.org/10.1038/s41597-025-04763-w (not read in full; facts below come from the files).
- **Data:** University of Toronto Dataverse (Borealis), https://doi.org/10.5683/SP3/KV65VI, version 1 (released 2024-11-04). One file: `EMG typing dataset.zip`, file id 836662.
- **Licence:** **CC BY 4.0** (Borealis API `license` field, checked 2026-11-11). Commercial use: yes, with attribution.
- **Code:** `ANSLab-UHN/sEMG-TypingDatabase` is **CC BY-SA 4.0**. A copy is also inside the zip. We read one line of it to learn the keylog alignment convention. **We copy nothing.** Our RHD reader follows the published Intan RHD2000 file format description.
- **Local raw path (outside the repo, never committed):** `C:\Users\zhang\bci-data\raw\toronto-semg\EMG_typing_dataset.zip` (2,766,730,294 bytes; MD5 `27d052ee…5c698f6d` = Borealis digest; SHA-256 `73c4f925…5de7ef3`). Extracted data files: `...\toronto-semg\extracted\`. Full digests: [`references/README.md`](../../references/README.md).
- **Safety:** we listed the zip first (no absolute paths, no `..`). The zip also holds a `.git` folder, 23 `.py`, 22 `.pyc` and 7 `.ipynb` files. We did not extract them.

## TL;DR
19 adults typed **isolated key presses** on a keyboard while 16 bipolar sEMG channels (8 per forearm) recorded at 2 kHz. Each recording is one trial: 5 presses of the space bar, then 10 presses of one letter, paced by a metronome. Two sessions on different days. A keylogger gives the time of each press. **There is no free or copied text.** So the data fits a key-press classifier and an adapter test. For a trust-layer test, sentences must be **composed** from single presses.

## Key facts (checked on the files, 2026-11-11)
| Item | Value |
|---|---|
| Participants / sessions | 19 (folders P1–P19) × 2 days (T1, T2) |
| Recordings | 1,968 `.rhd` files (Intan RHD2000 format v3.0, 128-sample blocks). About 2 per letter per session (49–52 per session) |
| Signal | 16 amplifier channels, 2,000 Hz, hardware band 7.7–500 Hz, notch off. About 16.4 s per file |
| Labels | `Keylogs.txt` per session (wall-clock time per key, ms resolution) + `LAG_TIMINGS.csv` (`Filename,Lag,Error` per file) |
| Alignment rule | key time in file = keylog time − file start time (from the file name) + `Lag` |
| Key presses (windows we cut) | 29,824: 10,093 space, 732–799 per letter |
| Pace | median inter-press interval 0.792 s (letters within a trial) ≈ 75.8 presses/min |
| EMG peak vs aligned key time | +0.08 s (mean rectified signal over all presses) |
| `Lag` alignment error | 134 files < 0.05, 642 < 0.1, 700 < 0.2, 270 < 0.4, 222 ≥ 0.4 (unit not stated; we read it as seconds) |
| Files marked `Used = No` in `Warnings.csv` | 179. None of them is in `CleanData` (already removed by the authors) |
| Published baseline (features + classifier, in the zip) | cross-session accuracy per participant 0.030–0.267; cross-participant 0.060–0.248 (26 letters) |

## Limitations
- **Isolated, paced key presses.** Real typing has context effects between keys and a faster pace. A decoder trained here may not transfer to free typing.
- Overt typing on a physical keyboard. Not attempted or imagined movement.
- The keylog alignment has a residual error. For 492 of 1,968 files it is ≥ 0.2 (s, as we read it).
- The participant numbers in `Warnings.csv` (1–20) are not the folder numbers (P1–P19).
- No text, so eWPM needs composed sentences (see the experiment). Composed sentences have no inter-key context.

## Feeds
- Entity: [Toronto sEMG typing dataset](../entities/toronto-semg-typing-dataset.md).
- Concepts: [CTC](../concepts/ctc.md), [Error metrics](../concepts/error-metrics.md).
- Result: [EMG Toronto trust result](../questions/emg-toronto-trust-result.md).
- Code: `src/fidetype/adapters/toronto_semg.py` (RHD reader, keylog alignment, NeuralTextStream forms). Experiment: [`experiments/2026-11-11-emg-toronto/`](../../experiments/2026-11-11-emg-toronto/results.md).
