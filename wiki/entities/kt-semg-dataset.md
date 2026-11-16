---
title: KT-sEMG dataset (Nokia, keyboard typing sEMG)
type: entity
tags: [dataset, emg, typing, cc-by, licence-clean]
sources: []
updated: 2026-11-14
---

# KT-sEMG (Keyboard Typing via Surface Electromyography)

- **Citation**: Crouch, Zheng, Eggleston, *Natural Typing Recognition via Surface Electromyography*, arXiv 2109.10743 (Nokia Bell Labs).
- **Link**: https://doi.org/10.7910/DVN/AV6XIR (Harvard Dataverse)
- **Licence**: "copyright 2021 Nokia. Licensed under the Creative Commons Attribution 4.0 International license. SPDX-License-Identifier: CC-BY-4.0" (Dataverse terms, verified 2026-11-10). Commercial use: **yes, with attribution**.
- **Signal**: forearm sEMG from custom sleeves, 16 channels per arm (32 total), 2000 Hz.
- **Format**: per run, a CSV of the 32 channels at 2000 Hz (`runNN.csv`), a keystroke log with millisecond timestamps (`runNN_keys.txt`), and a start-time file (`runNN_ts.txt`).
- **Size**: 88 files, 21.0 GB (Dataverse API).
- **Participants**: one "nonprofessional typist" doing natural typing (paper).
- **Volume**: "over 148,000 labeled gestures" (keystrokes). The paper used 1,960 valid 15-second blocks. Hours: not stated (unverified).
- **Paper result**: CTC-trained conv + LSTM, "almost 91% character-level accuracy", processing time under 100 ms.

## Local copy (P4-01, 2026-11-14)
- **Source**: Harvard Dataverse `doi:10.7910/DVN/AV6XIR`, version 1.1 (released 2021-09-28). Public: no login, no guestbook, no restricted files (Dataverse API, 2026-11-14). Terms: CC BY 4.0, copyright 2021 Nokia.
- **Files**: 88 (README.txt, and per run `runNN.csv`, `runNN_keys.txt`, `runNN_ts.txt`). Total **20,982,743,251 bytes** as original files. Dataverse ingested `run2.csv` and `run3.csv` as tables, so the API shows 20,996,304,401 bytes; we download those two with `?format=original`.
- **Checksums**: Dataverse gives an MD5 for each file. The list (id, name, size, MD5) is in `C:\Users\zhang\bci-data\raw\kt-semg.manifest.tsv`.
- **Local path**: `C:\Users\zhang\bci-data\raw\kt-semg\` (outside the repo, never committed).
- **Download / resume**: `bash C:/Users/zhang/bci-data/scripts/kt-semg-download.sh` (skips complete files, resumes partial files with `curl -C -`). Log: `C:\Users\zhang\bci-data\raw\kt-semg.download.log`.
- **Check**: `bash C:/Users/zhang/bci-data/scripts/verify-p4-01.sh`.
- **Status**: **done** (2026-11-14 17:35). 88 of 88 files match the Dataverse size and MD5; total 20,982,743,251 bytes. Plain CSV and text, no archive to extract. The first pass got the ingested `.tab` form of `run2.csv` and `run3.csv` (a CRLF bug in the manifest); both were downloaded again as originals and now match.

## Replay adapter (P4-01, 2026-11-14)
Module: `fidetype.adapters.kt_semg` (our own code, Apache-2.0). Tests: `tests/test_adapter_kt_semg.py` (synthetic data only). Conformance target: `adapter:kt-semg`.

**File facts that we found.**
- `runN.csv`: tab-separated, header `Time` + 32 channel names, 2000 rows per second. The `Time` column has 6 significant digits, so it loses resolution after 100 s. The adapter uses row index / 2000.
- `runN_keys.txt`: `<char> <unix time>` per key press. A space line is the space bar. Upper case = shifted letter. `\x08` = Backspace. `\r` = Enter; 9 Enter presses are written as `\r\n` and split over two lines. The reader joins them.
- `runN_ts.txt`: local wall-clock start time without a time zone. The adapter infers the whole-hour UTC offset that puts the key presses inside the recording. The sample runs gave UTC-4 and UTC-5 (US daylight and standard time). At least 99.56 % of the key presses then fall inside the recording.
- EMG power near the key presses peaks about 0.1 s before the logged key time (two runs checked). This supports the alignment.

**What the stream holds.** The dataset has no decoder output. A replay stream comes from a decoder that classifies one EMG window per key press (oracle key times from the key log, as for the [Toronto set](toronto-semg-typing-dataset.md)).

| Item | Value |
|---|---|
| Unit | One stream per typing burst (key presses split at pauses > 2 s) |
| Frames | One frame per key press, time in seconds from the first EMG sample |
| Vocabulary | 32 W3C `KeyboardEvent.code` names: `KeyA`–`KeyZ`, `Space`, `Period`, `Comma`, `Quote`, `Backspace`, `Enter`. `vocab_type = key`, no blank |
| Other keys | Digits, `;`, `/`, `[`, `^` (< 0.1 %) still get a frame; they are not decoder classes |
| Causality | With a window latency: `decoder.causal = true`, `decoder.lookahead_s` = window after the key. Without: `causal = false` |
| Provenance | `decoder.weights_sha256`, opaque `stream.id`, adapter name and version, `fidetype.replay` = slug, DOI, licence, Nokia attribution, run ordinal, segment index |
| Not in the stream | Typed text, run numbers, dates |

**Reference decoder.** `LdaKeyDecoder`: shrinkage LDA on log-RMS features (32 channels × 2 sub-windows of [-150 ms, +50 ms]), features z-scored per run without labels. numpy only, no GPU. It is a baseline for replay tests, not a result. The [emg2qwerty adapter](emg2qwerty.md#replay-adapter-p4-01-2026-11-15) reuses this vocabulary and this decoder.

**Real-data validation** (local, nothing committed). Sample of 7 of 29 runs. Per run, the LDA is fit on the first half of the key presses; streams are made for the second half (session-calibrated).

| Count | Value |
|---|---|
| Runs in the sample | 7 |
| Key presses inside the recordings | 12,870 |
| Streams (bursts with ≥ 5 presses) | 55 |
| Frames | 6,421 |
| Streams at level `provenance` | 55 / 55 (0 failed checks) |
| Key accuracy, second halves (in-vocabulary keys, 6,428) | 0.4975 |
| Majority-class rate | 0.1823 |

A cross-run test (fit on 3 runs, test on 3 other runs) gave key accuracy 0.1325, below the majority rate 0.1891 (17 / 17 streams `provenance`).

> **Our take:** The sleeves move between days, so a simple decoder does not transfer across runs. Session calibration works. A CTC decoder on continuous EMG (the paper's method) is the next step if we need a strong KT-sEMG decoder.

## Fit for Fidetype
| Use | Fit | Why |
|---|---|---|
| (a) decoder training | ✔ | Continuous EMG + keystrokes. CTC works (paper) |
| (b) trust-layer / eWPM | ~ | Keystroke timing yes. Free typing, so no fixed target sentences (unverified) |
| (c) adapter conformance | ✔ | Plain CSV format, distinct from HDF5 (emg2qwerty) and FIF (MEG) |
| (d) pretraining | ~ | One person |

> **Our take:** This is the only commercially clean EMG typing set with a large keystroke count. One typist limits cross-subject claims, so pair it with the [Toronto set](toronto-semg-typing-dataset.md) (19 people). Second download after [Brain-to-Text '25](brain-to-text-25.md).

Related: [emg2qwerty](emg2qwerty.md) · [Meta Neural Band](meta-neural-band.md) · [Public datasets survey](../questions/public-datasets.md)
