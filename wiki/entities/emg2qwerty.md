---
title: emg2qwerty (wrist-EMG typing dataset)
type: entity
tags: [dataset, emg, typing, public, nc-licence, downloaded, replay-adapter, paper-not-ingested, p11-01-decoder]
sources: [brain2qwerty-v1, brain2qwerty-v2, neural-input-landscape-2026]
updated: 2026-11-19
---

# emg2qwerty

> **Partial page.** Facts below were checked on the repo page and the download server on 2026-11-10 ([public datasets survey](../questions/public-datasets.md)). The data is downloaded (2026-11-15). The file facts and the replay adapter below come from our own checks (2026-11-15). The paper itself is not ingested yet.

- **Citation**: Sivakumar et al., *emg2qwerty: A large dataset with baselines for touch typing using surface electromyography*, NeurIPS 2024 (arXiv 2410.20081).
- **Code and data**: https://github.com/facebookresearch/emg2qwerty (archived, read-only). Data: `https://fb-ctrl-oss.s3.amazonaws.com/emg2qwerty/emg2qwerty-data-2021-08.tar.gz`.
- **Licence**: non-commercial. The repo README says "emg2qwerty is CC-BY-NC-4.0 licensed". The `LICENSE` file in the same repo is **Attribution-NonCommercial-ShareAlike 4.0 International** (checked 2026-11-14). It is not commercially usable. Use it only for research and benchmarks ([landscape report](../sources/neural-input-landscape-2026.md#data-warning)).

> **Contradiction:** README = CC BY-NC 4.0; `LICENSE` file = CC BY-NC-SA 4.0. We follow the stricter one (BY-NC-SA): no commercial use, and derived data that we share must keep the same licence. Research use is fine under both.
- **Size**: 108 users, 1,135 session files, 346 hours (repo). The archive is **308.4 GB** (HTTP `Content-Length` 308,382,645,571 bytes). A BIDS copy on NEMAR (NM000104) is said to be about 239 GB (unverified).
- **Format**: one HDF5 file per session. Each has left and right sEMG, the prompted text, keylogger ground truth and their timestamps (repo). Exact layout: [replay adapter](#replay-adapter-p4-01-2026-11-15).
- **Signal**: 2 kHz. Two wristbands with 16 differential channels each, 32 in total (secondary sources). About 5.26 million keystrokes (secondary, unverified).
- **What it measures**: surface EMG from the **wrist** while people type. This is muscle activity, not brain activity, so it is not a BCI in the strict sense.
- **Relevance**:
  - Both Brain2Qwerty papers cite it as the model for **continuous, causal decoding**. v2 points to its low-latency causal Conformer as a template for real-time decoding ([v1](../sources/brain2qwerty-v1.md), [v2](../sources/brain2qwerty-v2.md)).
  - It is the *largest public* typing dataset of any modality. It can be decoded with the same CTC machinery, and the hardware (EMG wristbands) is affordable.

## Sibling Meta datasets
All Meta EMG datasets are NC. All are HDF5 at 2 kHz.

| Dataset | Content | Size | Licence |
|---|---|---|---|
| emg2qwerty | typing, 108 users, 346 h | 308.4 GB archive, 339.4 GB extracted | CC-BY-NC-4.0 (README) / CC-BY-NC-SA-4.0 (LICENSE file) |
| generic-neuromotor-interface | discrete gestures, handwriting (98.8 / 31.5 / 10.4 h train/val/test), wrist; 100 users per task | not checked | CC-BY-NC-4.0 |
| emg2pose | hand pose, 193 users, 370 h | 462.8 GB (431 GiB) | CC-BY-NC-SA-4.0 |

## Commercially clean alternatives
- [KT-sEMG (Nokia)](kt-semg-dataset.md): CC BY 4.0, 32 ch at 2000 Hz, ms keystroke timestamps, one typist, 21.0 GB.
- [Toronto sEMG typing](toronto-semg-typing-dataset.md): CC BY 4.0, 16 ch at 2 kHz, 19 people, 2.77 GB.

> **Our take:** emg2qwerty stays the research benchmark for the EMG adapter. It cannot train product weights. For licence-clean EMG work use KT-sEMG and the Toronto set. For licence-clean trust-layer evaluation on real decoded text, use [Brain-to-Text '25](brain-to-text-25.md).

## Download status (P4-01, 2026-11-15)
- **Downloaded and extracted on 2026-11-15.** The user approved the 308.4 GB download.
- Download: 14:05 to 17:07 (one `curl -C -` attempt, about 28 MB/s). The archive size is **308,382,645,571 bytes**. This equals the HTTP `Content-Length`.
- No checksum is published. We computed our own SHA-256 of the archive: `7b2d827d0068b838e0a15ffe9d5ddddbdc315f55ba1b667636c84e6b510d7581`. It identifies our copy only. It does not prove that the server copy is correct.
- Local path: `C:\Users\zhang\bci-data\raw\emg2qwerty\extracted\emg2qwerty-data-2021-08\` (outside the repo).
- Content: **1,136 files, 339,359,730,313 bytes (339.4 GB)**. These are 1,135 HDF5 session files and one `metadata.csv`. All files are in one folder.
- Check: the names and sizes of all 1,136 files on disk equal the `tar -tvzf` listing. Then we deleted the archive to save 308 GB.
- Manifest (SHA-256 + full listing): `C:\Users\zhang\bci-data\raw\emg2qwerty.manifest.txt`.
- `metadata.csv` aggregates (read with `awk`, no code from the archive): 1,135 sessions, **108 users**, **346.4 h**, **5,262,671 keystrokes**. These agree with the repo (108 users, 1,135 sessions, 346 hours) and with the secondary figure of about 5.26 million keystrokes.
- Columns of `metadata.csv`: `user`, `session`, `condition`, `duration_mins`, `num_keystrokes`, `num_prompts`, `quality_check_tags`.
- Treat the files as untrusted data. Open HDF5 only with `h5py` in `python -I`. Never unpickle. Run no code from the archive.

> **Our take:** the extracted copy uses 339 GB of disk. A new download is 3 h. Keep the extracted copy until the EMG adapter work is done.

## Replay adapter (P4-01, 2026-11-15)
Module: `fidetype.adapters.emg2qwerty` (our own code, Apache-2.0; no Meta code read or copied). Optional extra `[emg2qwerty]` = h5py (BSD-3-Clause). Tests: `tests/test_adapter_emg2qwerty.py` (8 tests, synthetic HDF5 files built in the test). Conformance target: `adapter:emg2qwerty`.

**File facts that we found** (all 1,135 files; attributes and the first and last sample only).

| Item | Value |
|---|---|
| Layout | One group `emg2qwerty`. One dataset `timeseries`: a 1-D compound array, one row per sample, fields `emg_right` (16 × float32), `time` (float64, unix s), `emg_left` (16 × float32). Contiguous, not compressed |
| Size per file | Up to 5,701,122 rows (about 775 MB) |
| Attributes | `session_name`, `user` (8-digit pseudonym), `condition` (always `on_keyboard`), `daq_sample_rate` `"2000.0"`, `daq_channels` `"16"`, `schedule`, `duration_mins`, `quality_check_tags`, `keystrokes` (JSON), `prompts` (JSON) |
| Keystrokes | `{ascii, key, start, end}`. `key` = a character or `Key.<name>`. `start` = key-down, `end` = key-up, on the same unix clock as `time`. Sorted by `start` |
| Prompts | 173,387 `text_prompt` items with `payload = {prompt_num, text}`. The text ends with `⏎` (Enter). Other items: `Intro`, `emg_left`, `emg_right`, `Metadata`, `Instructions`. Text prompts do not overlap |
| Sample clock | Steps of 0.45–0.55 ms (2 kHz) |
| Key presses in the files | 5,258,056. `metadata.csv` says 5,262,671 (4,615 more; cause not known) |
| Outside the recording | 2,975 key presses (0.057 %) |
| Inside a text prompt | 99.3–100 % of the key presses of a session (2 sessions checked) |
| Key classes | Top: `Key.space` 565,541, `e` 510,447, `Key.backspace` 226,653, `Key.enter` 172,723. Keys outside the 32 classes (arrows, digits, modifiers, `=`, `;`, ...) are < 0.2 % |
| Quality tags | 579 of 1,135 sessions have a tag (`high-backspaces`, `contact artifact`, `long-duration`, `outlier artifact`, ...) |
| Alignment | EMG power (first difference) peaks 60–120 ms **before** the logged key-down (2 sessions). This agrees with [KT-sEMG](kt-semg-dataset.md) (about 0.1 s) |

Keys and samples share one unix clock. So no time-zone or offset inference is necessary.

**What the stream holds.** The dataset has no decoder output. A replay stream comes from a decoder that classifies one EMG window per key press (oracle key-down times from the keylogger).

| Item | Value |
|---|---|
| Unit | One stream per text prompt (key presses with key-down inside `[prompt.start, prompt.end]`) |
| Frames | One frame per key press. Time = seconds from the first EMG sample of the session |
| Vocabulary | The 32 W3C `KeyboardEvent.code` classes of the KT-sEMG adapter (same `fidetype.vocab_id`). `vocab_type = key`, no blank |
| Channels | 32: left band 0–15, then right band 16–31 |
| Causality | With a window latency: `decoder.causal = true`, `decoder.lookahead_s` = 0.05 s. Without: `causal = false` |
| Provenance | `decoder.weights_sha256`, opaque `stream.id` (SHA-256 of slug, session name, prompt index and weights tag; 32 hex), adapter name and version, `fidetype.replay` = slug, arXiv id, licence `CC-BY-NC-SA-4.0`, attribution, `research_only: true`, session ordinal, prompt index |
| Not in the stream | User id, session name, dates, prompt text, typed text |

**Safe loading.** h5py opens the file read-only. The adapter reads only the numeric dataset and string attributes. The JSON logs go through `json.loads` (NaN and infinity refused) and a check of each field. Attribute size limit: 64 MB. No pickles, no code from the archive. The EMG is read in blocks of 262,144 rows, so memory stays at tens of MB for any file.

**Reference decoder.** The KT-sEMG `LdaKeyDecoder` (shrinkage 0.1) on log-RMS features: 32 channels × 2 sub-windows of [−150 ms, +50 ms] around key-down, z-scored per session without labels. numpy only, no GPU. It is a baseline for replay tests, not a result.

**Real-data baseline** (local, nothing committed; outputs in `C:\Users\zhang\bci-data\derived\p4-01-emg2qwerty\`). Command: `python -I -m fidetype.adapters.emg2qwerty baseline <data folder> --users 8 --sessions-per-user 2 --out <folder>`. Subset rule: users sorted by id; the first 8 users with at least 2 sessions; their first 2 sessions in name order (16 sessions). Per session: fit on the first half of the key presses, replay the second half. Aggregate numbers only.

| Count | Value |
|---|---|
| Users / sessions | 8 / 16 |
| Key presses inside the recordings | 78,187 |
| Test key presses in the vocabulary | 38,923 |
| Key accuracy, session-calibrated | **0.5353** |
| Majority-class rate (class from the fit half) | 0.0961 |
| Per-session accuracy (min / median / max) | 0.414 / 0.5324 / 0.662 |
| Streams (prompts with ≥ 3 test presses) | 1,392 |
| Frames | 39,006 |
| Streams at level `provenance` | 1,392 / 1,392 |
| Same user, other session (fit on session 1, test on session 2; 8 pairs, 39,106 keys) | 0.5108 (majority 0.1047) |

Full dataset summary from `metadata.csv` (command `summary`): 1,135 sessions, 108 users, 346.4 h, 5,262,671 keystrokes, 175,347 prompts. Sessions per user: 1 / 12 / 18 (min / median / max).

> **Our take:** A simple windowed LDA reaches 0.54 on 32 keys with oracle timing. The same-user cross-session number (0.51) is much better than on KT-sEMG (0.13 cross-run). The emg2qwerty bands seem to sit in a more repeatable place. The real benchmark task (continuous CTC decoding without key times, across users) is much harder. This baseline exists only so that the trust layer has real-data streams to replay.

**Next step:** ingest the paper and repo (read only; the code is NC, do not copy it; gap 90). The continuous CTC decoder (output through the [CTC-logits adapter](../concepts/ctc-logits-adapter.md)) is done: see the next section.

## Continuous decoder (P11-01, done 2026-11-19)
Our own causal CTC decoder (ring-TCN, 8.75 M parameters, no lookahead) was trained on one GPU (2026-11-17 to 2026-11-19). Plan and pre-registered criteria: [P11-01 plan](../../experiments/2026-11-16-p11-01-emg-decoder/plan.md). Results: [P11-01 results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md). All our numbers: test sessions of our own split (8 users), greedy CTC, no LM. Published numbers: paper Table 3 (checked against the paper on 2026-11-19).

| Model | Ours, no LM, test CER (mean ± SD over 8 users) | Published, no LM, test | Published, 6-gram char LM, test |
|---|---|---|---|
| Generic | 53.52 ± 15.31 % | 55.38 ± 4.10 % | 51.78 ± 4.61 % |
| Personalised (fine-tuned from generic) | **15.09 ± 6.54 %** | 11.28 ± 4.45 % | 6.95 ± 3.61 % |

- Pre-registered: S1 (personalised <= 20.0 %) **pass**; S1+ (<= 11.28 %) **fail**; S2 (generic <= 60 %), S3 (8 of 8 users better after personalisation), C1 (time-shuffled CER 0.986), N1 (2,445 / 2,445 NTS streams `trust-ready`), L1 (no lookahead; median emission delay 70 ms, p90 110 ms) **pass**.
- The conditions differ from the paper: other test users and splits, 12 log bands at 100 Hz, no lookahead, greedy decoding. The comparison is indicative.
- The generic model is best at step 30,000 of 150,000 (val CER 0.5457). After that it overfits.
- Weights and per-user values stay local in `C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train\`. They are research only (NC data).
- Open: licence-clean decoder (gap 86), LM + beam search (gap 87), accuracy to 11.28 % (gap 88), trust config + streaming replay (gap 89), paper ingest (gap 90). See [open gaps](../questions/open-gaps.md).

> **Our take:** about 15 % key errors after 18 min of fine-tuning per user, with no lookahead and no LM. This is our first non-implant decoder that is strong enough to make trust-layer tests useful.

Related: [Meta Neural Band](meta-neural-band.md) · [Synchronous vs asynchronous decoding](../concepts/synchronous-vs-asynchronous-decoding.md) · [CTC](../concepts/ctc.md) · [Public datasets survey](../questions/public-datasets.md)
