---
title: M1-A data layer, SpanishBCBL cache
type: experiment
updated: 2026-11-08
---

# M1-A: SpanishBCBL loader and preprocessing cache

Milestone M1-A builds the data layer for the M1 decoder. This page reports the first cache run.
The code is our own. We read the Brain2Qwerty loader (CC BY-NC) only to learn the file quirks.

- Loader: `src/fidetype/data/spanishbcbl.py` (discovery, log parsing, clock alignment, text).
- Pipeline and cache: `src/fidetype/data/preprocess.py`.
- CLI: `tools/data/preprocess_spanishbcbl.py`.
- Tests: `tests/test_data_spanishbcbl.py`.
- Summary tables: `summarize_cache.py` in this folder. It reads only the sidecars.
- Cache: `C:\Users\zhang\bci-data\cache\spanishbcbl\v1\` (outside the repo; the data is CC BY-NC).

## Status (2026-11-08 14:00)

- The cache job runs detached. It started at 13:40 with 47 blocks from 14 complete subjects (S1, S3, S5, S9, S10, S11, S12, S15, S16, S18, S19, S22, S24, S25). S25 ran first.
- When we wrote this page, 6 blocks were cached: S25 (all 4 blocks), S1 ses2 block1 and S5 ses1 block1. Large blocks finish at a rate of about 1 per 5–7 min. We expect the job to end after about 3–4 h.
- S25 is complete and valid. It has 4 blocks and 264 trials. Each data array has shape [306, T] in float16. All sidecars pass `validate_sidecar`, and the integration test passes.
- After the download ends, run the same command again. It skips the cached blocks and adds the new subjects.

Commands (PowerShell):

```powershell
# Check
Get-Content C:\Users\zhang\bci-data\cache\spanishbcbl\v1\_preprocess.log -Tail 20
# Stop the launcher process tree (its PID is in _preprocess.pid)
taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\cache\spanishbcbl\v1\_preprocess.pid)
# Resume or extend (idempotent); run from the repo root
Start-Process C:\venvs\fidetype-rocm\Scripts\python.exe -ArgumentList 'tools\data\preprocess_spanishbcbl.py','--workers','2','--mem-budget-gb','14' -WindowStyle Hidden
```

## Pipeline

| Step | Setting | Flag in `PreprocConfig` |
|---|---|---|
| 1. Load | `read_raw_fif(allow_maxshield=True)`; MNE reads the `-1.fif` split parts | — |
| 2. Bad channels | `find_bad_channels_maxwell` (origin from the head shape, `h_freq=40`) | `maxwell_bads` |
| 3. tSSS | `maxwell_filter`, `st_duration=10`, one `destination` per subject (dev_head_t of its first block); no fine-cal or cross-talk files exist | `tsss`, `st_duration`, `common_destination` |
| 4. Notch | 50 and 100 Hz | `notch` |
| 5. Band-pass | 0.5–45 Hz (preset `v1`: 0.1–20 Hz) | `l_freq`, `h_freq` |
| 6. Resample | 100 Hz (preset `v1`: 50 Hz) | `sfreq_out` |
| 7. Channels | 306 MEG channels (102 mag, 204 grad). We pick them right after tSSS, before the filters. The output is the same, and it uses less time and memory | `pick_meg` |
| 8. Scaling | Per block and channel: (x − median) / IQR, clamp at ±5 | `robust_scale`, `clamp` |

The config version is `spanishbcbl-preproc-r1-5e8418ccd5`. It is a hash of the config plus a code revision number.
The CLI skips a block when its sidecar has the same version.

## Cache format

One pair of files per block: `<cache>/<subject>/<session>_<block>.npz` and `.json`.
For example `S25/ses1_block1.npz`. `session` is `ses1` or `ses2` (rank of the date folder). `block` is `block1` or `block2`.

`.npz` (written with `np.savez`, no pickle):

| Key | Type | Content |
|---|---|---|
| `data` | float16 [306, T] | Scaled MEG data at `sfreq`. Values are in [−5, 5] |
| `sfreq` | float64 scalar | 100.0 (preset `v1`: 50.0) |
| `ch_names` | str [306] | `MEG0113`, … in MNE order |
| `ch_types` | str [306] | `mag` or `grad` |
| `ch_pos` | float32 [306, 3] | Sensor positions (`info["chs"][i]["loc"][:3]`, device frame, metres) |

`.json` sidecar (schema 1):

| Key | Content |
|---|---|
| `schema`, `subject` (`S25`), `participant` (`P25`; S18 → `P01`, S14 → `P04`, S10/S21 → `P05`), `session`, `block` | Identity |
| `source` | fif path, split parts, log used, session folder, notes, raw sfreq, duration |
| `preprocessing` | `version`, full `config`, MNE version, destination `dev_head_t` |
| `qc` | `alignment` (matched fractions, slope, drift, residual median/p95/max), `bad_channels`, `peak_23hz_before`/`_after`/`_removed`, `log_reassigned`, `timings_s`, `peak_memory_gb` |
| `sfreq`, `n_times` | Output rate and length of `data` |
| `segments` | One entry per trial (see below) |

Each segment:

| Key | Content |
|---|---|
| `trial_idx` | Trial index in the log (0–65) |
| `is_training` | True for trials 0 and 1 (visual feedback). Keep them out of test metrics |
| `start_sample`, `end_sample` | Slice of `data` (end exclusive): first key press − 0.4 s to last key press + 0.5 s. The last key press is usually Return |
| `target_text` | Log sentence, `normalize_text` (lower case, no accents, single spaces) |
| `typed_text` | CookedKey sequence, backspace applied, then normalised |
| `key_samples` | Key-press samples relative to `start_sample`. All key presses, including Return and other keys |
| `key_chars` | Per key press: `a`–`z`, `" "`, `<bs>`, `<ret>` or `<?>` (dead accent keys, punctuation) |
| `key_target_chars` | Per key press: the target character from the difflib alignment, or null (insertion, erased key, backspace, return, other key) |
| `split` | `train`, `val` or `test` from `assign_split(target_text)` |
| `n_keys_unmatched` | Key presses without a MEG trigger match (their time comes from the clock fit) |

`<cache>/_index.json` lists all cached blocks with their QC and split counts. `<cache>/_excluded.json` lists all skipped files with the reason.
Load a block with `fidetype.data.preprocess.load_cached_block(path)`.

## Split rule

`assign_split(text)` hashes `normalize_text(text)` with SHA-1. The first 8 hex digits mod 100 give the bucket: < 80 train, < 90 val, else test.
So every repetition of a sentence, in any subject, falls in the same split. The rule needs no state and no list of sentences.

## File discovery

- Discovery finds **81 typing blocks** in 24 subject IDs. It excludes 79 files. `_excluded.json` lists each excluded file with its reason.
- Name rules:
  - These names are typing blocks: `block1`, `Block1`, `bolck2` (typo), `block22` and `block2_1` (retries), and names with prefixes (`d2_block1`, `03_11123_block2`).
  - `<stem>-1.fif` is a split part of `<stem>.fif`.
  - These files are excluded: localizers (`tapping`, `typing`, `Typing`, `typing_s2`), `block2fail`, `testdavid` and `Emptyroom`.
- Some sessions have more than one recording of a block. The highest retry number wins: S18 `block1_1`, S20 `block2_1`, S21 `block2_2`. S1 session 1 uses `Block3` as block 2, because `Block2` is a short, aborted run.
- Duplicate folders are skipped: `02__2810/220412`, `04_3660/230405` and `14_9876/231115`. (`04_3660/230405` is a copy of `05_3660/230405`, which is S5.) S8 has its 2 sessions in 2 folders (`08_11374` and `8_11374`). The session number is the rank of the date over all folders of a subject number.
- S1 and S2 use log names of the form `S<N>-session<k>-<b>.mat`. In session 2, the block number in the name is swapped. S1 ses2 block1 matched 100 % of its keys with `S1-session2-2.mat`, so the swap is confirmed.
- As a guard, the pipeline tries the other logs of the session when fewer than 90 % of the keys match. It records the result in `log_reassigned`.
- Blocks without a log are excluded: S3 ses2 block1, S5 ses1 block2, S5 ses2 block1, S6 ses2 block2 and block3, S8 ses2 block2, S9 ses2 block1, S21 ses2 block2, and all of S13 (S13 has no logs). S23 is excluded because of a metallic implant.

## QC so far

Per subject:

| Subject | Participant | Blocks | Trials (test) | Keys | Key match | Residual median (ms) | Residual p95, worst block (ms) | Bad channels per block | 23 Hz peak before → after tSSS (dB, median) | Time per block (s, median) | Peak RAM (GB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | P01 | 1 | 66 (64) | 2961 | 1.0000 | 0.28 | 0.70 | 10 | 8.2 → 0.0 | 423 | 15.4 |
| S5 | P05 | 1 | 66 (64) | 2233 | 1.0000 | 0.18 | 0.54 | 16 | 6.0 → 0.2 | 296 | 11.9 |
| S25 | P25 | 4 | 264 (256) | 10377 | 0.9999 | 0.33 | 0.97 | 4, 3, 5, 2 | 11.9 → 0.9 | 181 | 7.6 |

Per block:

| Block | Duration (s) | Segments | Key match | Residual p95 (ms) | Bad channels | 23 Hz before / after (dB) | tSSS (s) | Total (s) |
|---|---|---|---|---|---|---|---|---|
| S1/ses2_block1 | 1240 | 66 | 1.0000 | 0.70 | MEG0312, MEG0711–0713, MEG0721–0723, MEG1221, MEG1741, MEG1743 | 8.2 / 0.0 | 221 | 423 |
| S5/ses1_block1 | 768 | 66 | 1.0000 | 0.54 | MEG0121–0123, MEG0132, MEG0133, MEG0211, MEG0222, MEG0333, MEG0343, MEG0711–0713, MEG1821, MEG2433, MEG2621, MEG2643 | 6.0 / 0.2 | 130 | 296 |
| S25/ses1_block1 | 908 | 66 | 1.0000 | 0.91 | MEG0522, MEG1213, MEG2141, MEG2613 | 15.9 / 0.4 | 389 | 477 |
| S25/ses1_block2 | 979 | 66 | 1.0000 | 0.95 | MEG0522, MEG2141, MEG2613 | 14.8 / 1.3 | 91 | 186 |
| S25/ses2_block1 | 982 | 66 | 0.9997 | 0.97 | MEG0431–0433, MEG0522, MEG2141 | 9.1 / 0.7 | 89 | 176 |
| S25/ses2_block2 | 779 | 66 | 1.0000 | 0.91 | MEG0522, MEG2141 | 8.5 / 1.0 | 65 | 137 |

- Alignment: 15 570 of 15 571 key presses match a MEG trigger within 20 ms. The clock slope is 1.0005 (a drift of 0.5 ms per s), as in the M0 inspection. The one unmatched key gets its time from the clock fit.
- The S25 numbers are the same as in the M0 inspection. For example, S25 ses1 block1 matches 2548 of 2548 events, with a p95 residual of 0.91 ms.
- To get the current tables, run `python experiments/2026-11-08-m1a-data/summarize_cache.py`.

## The 23.3 Hz peak

- We measure the peak on the median magnetometer PSD (a 60 s window from 120 s, Welch, 8192-point FFT). The prominence is the peak height above the median of a ring 1.5–5 Hz away.
- Before tSSS, the prominence is 6.0–15.9 dB. After tSSS, it is 0.0–1.3 dB. **tSSS removes the peak in all 6 blocks.** (`peak_23hz_removed` is true when the value after tSSS is below 3 dB.)
- So the peak comes from an external source. It does not need a notch filter.

## Sentences and splits

These counts come from the logs of all 81 blocks. They need no MEG data.

| Split | Unique sentences | Trials | Test trials (training trials removed) |
|---|---|---|---|
| train | 184 | 4229 | 4086 |
| val | 16 | 449 | 442 |
| test | 24 | 653 | 641 |
| **All** | **224** | **5331** | **5169** |

- In the 51 blocks of the subjects that are complete now, there are 198 sentences: train 160 sentences / 2671 trials, val 15 / 282, test 23 / 400.
- In the 6 cached blocks, there are 140 sentences: train 110 / 312 trials, val 12 / 34, test 18 / 50.
- The typed text equals the target text in 2203 of 5331 trials (41 %). The logs have only 125 backspaces in 206 107 key presses.

## Timing and memory per block

- Step times: bad-channel scan 70–200 s, tSSS 65–390 s, filters and resample about 10 s, write less than 1 s.
- With 2 parallel workers, a 13–16 min block takes 140–190 s and a 21 min block takes 420 s. tSSS takes most of the time.
- Peak RAM is about 5–6 × the .fif size: 7.6 GB for a 1.2 GB block, and 15.4 GB for a 3.2 GB block (main file plus split part).
- The cache uses about 55 MB per 15 min block (float16).

## Known problems

1. **Memory.**
   - The first run (3 workers, no thread limit) stalled for 2 h. Other agents used about 13 GB of RAM at the same time, and the machine paged. We stopped the run and restarted it with 2 workers and a 14 GB budget.
   - The CLI now has four guards:
     - It starts a block only when the estimated RAM of the running blocks stays below `--mem-budget-gb`. The estimate is 5.5 × the .fif size + 1 GB.
     - It waits when the free physical RAM is less than the estimate.
     - It limits the BLAS threads per worker.
     - It uses a new process for each block.
   - The default of 3 workers is safe only when the machine has no other large jobs.
2. **Bad channels.** S5 ses1 block1 has 16 bad channels, and S1 ses2 block1 has 10. The Maxwell scan finds them without fine-calibration and cross-talk files. tSSS reconstructs the bad channels, so the output still has 306 channels. Check these blocks before you use per-channel results.
3. **Typed text and target text differ in 59 % of trials.** `key_target_chars` comes from a difflib alignment. It handles substitutions and insertions well. For a transposition, it can pair a key with the wrong target character (for example, "ejectua" typed for "ejecuta").
4. **Few sentences.** The dataset has only 224 unique sentences. The hash split gives 184/16/24 sentences (82/7/11 %), not exactly 80/10/10. At the sentence level, the val and test sets are small.
5. **Segments include non-text keys.** `key_samples` includes Return and dead keys (`<?>`). Their `key_target_chars` are null. Each segment ends 0.5 s after the last key press, which is usually Return.
6. **No calibration files.** SSS runs without fine-calibration and cross-talk files, because the dataset has none.
7. **`ch_pos` is in the device frame.** After tSSS, the data is in the subject's destination head position, but the sensor positions stay in the device frame. This is correct for a sensor-space model.
8. **One block from a test run.** The first cached block (S25 ses1 block1) came from a test run with the same config version. Its sidecar has no `peak_memory_gb`.
