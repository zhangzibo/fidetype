# Live decode from lab tools: `fidetype live`

One command reads a live signal, decodes it and puts the trust guard on top. You get one trust decision per segment (commit, offer or withhold) and, if you ask, a valid NeuralTextStream (NTS) file.

```
signal source  ->  windows  ->  model  ->  key beam search  ->  trust guard  ->  decisions + NTS
(LSL, BrainFlow,   (key onset   (one key    (n-best list per    (commit / offer /
 OpenBCI, synth)    or fixed)    posterior)  segment)            withhold)
```

Roadmap items: P14-04 (this path) and P4-02 (LSL and BrainFlow adapters, synthetic-board test). Code: [`src/fidetype/live/`](../src/fidetype/live/). Tests: [`tests/test_live.py`](../tests/test_live.py).

> **Read this first.** Our models do not transfer to a new person, a new device or a new electrode position without training and calibration. The live path checks the plumbing and the trust decisions. Decoding quality comes from replay of public data ([benchmark tracks](benchmark-tracks.md)). Fidetype is research software, not a medical device.

## 1. Install (1 minute)

From a clone of the repository:

```bash
uv sync                                    # core: the synthetic source works with numpy only
uv sync --extra lsl --extra brainflow      # LSL (pylsl, MIT) and BrainFlow (MIT) sources
```

`pylsl` and `brainflow` are optional. Without them, `--source lsl` and `--source brainflow` stop with an install hint (exit code 2).

## 2. First run: synthetic typist (no hardware, no data)

```bash
fidetype live --source synthetic
```

The synthetic source makes a 16-channel, 250 Hz signal in which each key press leaves a burst with a key-specific pattern. The packaged model `builtin:synthetic-keys` decodes it; its guard `builtin:synthetic-keys` is calibrated on 600 synthetic utterances. Output (real time, about 43 s for 10 utterances):

```
[    4.54s] OFFER    [well land under]  p=0.56 keys=15 decide=4.5 ms added=4.7 ms
[    9.61s] COMMIT   "well call group"  p=0.71 keys=15 decide=1.0 ms added=1.1 ms
...
[fidetype.live] stop (end of source): 10 decisions (8 commit, 2 offer, 0 withhold), ...
[fidetype.live] latency per window: compute p50 0.2 ms, ...
```

- `COMMIT "text"`: the guard lets the text go through by itself.
- `OFFER [a | b | c]`: show the choices to the user; the user picks.
- `WITHHOLD`: show nothing.
- `p`: calibrated probability that the top text is right. `keys`: windows in the segment.
- `decide` / `added`: latency (section 6).

Useful options: `--speed 0` (no pacing), `--json` (one JSON object per decision), `--no-text` (no decoded text on screen), `--out s.nts.jsonl` (NTS file; the trust decisions go to `s.nts.decisions.jsonl`, section 8), `--summary s.json` (counts and latency), `--null` (signal without key bursts: the guard must never commit).

The synthetic signal is our own. It contains no participant data. The model decodes only this signal.

## 3. BrainFlow and OpenBCI boards

```bash
fidetype live --source brainflow --board-id -1 --duration 20 --out bf.nts.jsonl   # BrainFlow Synthetic board
fidetype live --source brainflow --board cyton --serial-port COM3                  # OpenBCI Cyton (board id 0)
fidetype live --source brainflow --board ganglion --serial-port COM4               # OpenBCI Ganglion (board id 1)
```

- The board is read in the same process through the BrainFlow bridge ([`brainflow_bridge.py`](../src/fidetype/adapters/brainflow_bridge.py)): board open, time stamps, and a trial clock that ends a segment every `--trial-s` seconds (default 2).
- A board has no key-onset markers. So `--source brainflow` uses **fixed timing**: one window every `hop_s` seconds (model card; `--hop` changes it).
- `--kind eeg|emg|exg` selects the board channels. The model must have the same channel count and sample rate as the board; else the command stops with a clear message.
- The BrainFlow Synthetic board makes sine waves and noise. They carry no text. The correct output is **no commit**. The command prints a note about this.
- Real OpenBCI boards are **not tested** (no hardware; roadmap P4-06, externally blocked). The support level of each source and reader is in the [device support matrix](device-support.md).

The NTS header carries the board as vendor keys `brainflow.board_id` and `brainflow.board_name` (NTS MET-3; roadmap P4-09).

## 3a. Recording files: `--source file`

```bash
fidetype live --source file --path rec.edf --speed 0                       # EDF / EDF+ / BDF: reader edf
fidetype live --source file --path OpenBCI-RAW-2026-11-21.txt --speed 1     # OpenBCI GUI v5: reader openbci-gui
fidetype live --source file --reader openbci-gui --path renamed.txt         # pick the reader by its id
```

- The command picks the **file reader from the adapter registry** ([`registry.py`](../src/fidetype/adapters/registry.py)). Each `file-reader` adapter declares `file_patterns` (file-name globs, case-insensitive) in its `ADAPTER_INFO`. The command uses the one reader whose pattern matches the file name. `--reader ID` picks a reader by id: use it for a renamed file, or when more than one pattern matches. The list of readers and patterns is in [the adapter catalogue](adapters.md#file-readers-for-fidetype-live).
- No match, two matches, an unknown id, a missing file or no `--path`: the command stops with exit code 2 and a message. A file that the reader cannot read (bad header, truncated file): exit code 3.
- `--speed 1` (default) plays the file in real time. `--speed 0` reads it as fast as possible. `--modality` sets the NTS `device.modality` (default: the reader's).
- Timing: the file markers (for example EDF+ annotations `keypress` and `segment_end`) drive the windows as with `--source synthetic`. A file with no `keypress` markers gets **fixed timing** and a note; give `--segment-s` to end segments. Other file markers (for example the PhysioNet EDF+ annotations `T0`, `T1`, `T2`) open no window.
- The model must have the same channel count and sample rate as the file; else the command stops with a clear message.
- The NTS header has `fidetype.live.source = "file"`, `fidetype.file_reader` (the reader id) and the reader's own meta keys (for example `edf.format`). The readers never copy personal header fields (EDF "patient", "recording") into `meta`.
- Both readers are `tested` (P4-16): they read real public files outside the repository (PhysioNet EEGMMIDB EDF+, the MNE-Python test EDF+ and BDF files, the OpenBCI GUI sample file) and give the same values as a second reader (MNE; the Python `csv` module) within the format resolution. Test: `tests/test_adapter_files_real.py` (skipped when the files are absent). The OpenBCI GUI sample files write the `Timestamp` column in milliseconds; the reader reads a first stamp above 1e11 as milliseconds.
- A new reader joins with no change to the command: see [CONTRIBUTING.md 7.1](../CONTRIBUTING.md#71-add-a-new-adapter-in-about-50-lines).

## 4. LSL streams

```bash
fidetype live --source lsl --stream-name MyEMG --model my.model.json --guard my.guard.json
```

- Find the signal stream with `--stream-name`, `--stream-type` or `--source-id`.
- Markers: `--markers auto` (default) reads the stream named by `desc/fidetype/events_source_id` of the signal stream (the BrainFlow bridge and the replay commands set it). `--markers <name>` reads that marker stream; `--markers none` reads none.
- Marker strings: `keypress` (a key onset; never the key itself) and `segment_end`. A plain-string marker stream from your stimulus program works.
- Times are corrected to the receiver clock with LSL `time_correction()`.
- **Reconnect (P4-11).** When the signal or marker stream is lost, `fidetype live` resolves both again (same `source_id`, else name and type; the reconnect code of `fidetype lsl run`, with backoff: 0.05 s, x2, at most 2 s between tries). Options: `--max-reconnects N` (default 5 per run; 0 = end the run at a loss), `--reconnect-timeout S` (default 30 s per loss), `--reconnect-backoff F` (default 2). A stream that comes back with another channel count or rate ends the run.
- **No decision on a cut input** (spec LSL-G2). At a loss the decoder drops the open segment, the pending key onsets and the signal buffer (no window spans the gap). It also drops the first segment after the gap, up to the next `segment_end` (its start can be inside the gap). A time jump of more than 2.5 sample periods inside a live stream is handled the same way (LSL-G1).
- **Gap record in the NTS file** (LSL-G1 `abort` mode, LSL-G3 fields): one event per gap,

  ```json
  {"type": "lsl_status", "status": "gap_abort", "t_start": 1012.31, "t_end": 1015.92, "missing_frames": 7219,
   "stream": "MyEMG", "lsl_cause": "lost"}
  ```

  `t_start` = last sample before the gap, `t_end` = first sample after it, `missing_frames` = missing samples, `lsl_cause` = `lost` or `timestamp` (a file reader can give `sample_index`: an OpenBCI GUI packet drop, P4-18). A consumer drops its open utterance there. A run that ends while the stream is lost writes `{"type": "lsl_status", "status": "lost", ...}`. The file keeps its one header (JSONL rule 6.2.1); the run summary counts `losses`, `gaps`, `dropped_segments` and `dropped_frames`.

Test the LSL path on one machine with no data:

```bash
fidetype live replay-synthetic &                                   # synthetic typist -> LSL
fidetype live --source lsl --stream-name fidetype.replay.synthetic
```

## 5. Replay a public recording over LSL: KT-sEMG

KT-sEMG is forearm sEMG of natural typing (32 channels, 2000 Hz; copyright 2021 Nokia, **CC BY 4.0**, [doi:10.7910/DVN/AV6XIR](https://doi.org/10.7910/DVN/AV6XIR)). Download it as described in [benchmark tracks](benchmark-tracks.md). Then:

```bash
# one time: train the demo model and calibrate its guard (about 15 min CPU; one run in RAM at a time)
fidetype live train-kt --data ~/bci-data/raw/kt-semg --out ~/bci-data/derived/kt-live

# terminal 1: publish test run run28 (EMG + keypress / segment_end markers); --speed 3 = 3x real time
fidetype live replay-kt --data ~/bci-data/raw/kt-semg --run run28 --speed 3

# terminal 2: decode it
fidetype live --source lsl --stream-name fidetype.replay.kt-semg \
    --model ~/bci-data/derived/kt-live/kt-semg-lda.model.json \
    --guard ~/bci-data/derived/kt-live/kt-semg-lda.guard.json --out kt.nts.jsonl
```

- Splits: the runs of benchmark track `kt-semg` (tracks v0.2). The model trains on train runs, the guard calibrates on other train runs plus the `cal` runs, and the replay uses a `test` run.
- The model is the KT-sEMG reference decoder (log-RMS window features, shrinkage LDA) with a causal running z-score. It is a weak baseline. Expect mostly offers and withholds.
- Key onsets come from the key log of the recording (oracle timing, as in the P4-01 replay streams). To find them in the EMG instead, add `--timing detect` (section 5a).
- The trained files stay on your machine. We do not ship KT-sEMG weights.
- Our run: see [the results](../experiments/2026-11-16-p14-04-live/results.md).

## 5a. Key onsets from the signal: `--timing detect` (P4-10)

A real EMG board sends no key markers. `--timing detect` finds the key onsets in the signal with a causal detector ([`fidetype.live.onset`](../src/fidetype/live/onset.py), numpy only) and cuts one key window per onset. `keypress` markers are then ignored; `segment_end` markers (or `--segment-s`) still end the segments.

```bash
fidetype live --source lsl --stream-name fidetype.replay.kt-semg --timing detect --onset envelope \
    --model kt-semg-lda.model.json --guard kt-semg-lda.guard.json
```

| `--onset` | Detector | Training |
|---|---|---|
| `envelope` (default) | mean log energy over channels (first difference, 5 ms blocks, 20 ms window) as a z-score against an adaptive baseline; onset = upward crossing of `theta`, refractory 60 ms | none; defaults tuned on KT-sEMG cal run21 |
| `PATH.onset.json` | linear (binary shrinkage LDA) on 200 ms of per-channel log energy; onset = local maximum above `theta`, 50 ms after the onset | trained per dataset (`experiments/2026-11-17-p4-10-onset/run.py`) |

- The detector adds about 10 ms (envelope: none) to the window wait, because the key window already needs `post_s` = 50 ms after the onset.
- A guard calibrated with `markers` timing is not calibrated for `detect` timing (other frames). Re-calibrate the guard with `detect` timing.
- Results on the 6 KT-sEMG test runs at ±50 ms ([P4-10 results](../experiments/2026-11-17-p4-10-onset/results.md)): linear detector recall 0.829, precision 0.456, F1 0.588 (0.73 on the two runs with dense typing; many false alarms on runs with little typing); envelope F1 0.461. Matched onsets: median error about 20 ms.

## 5b. CI: replay of a public recording (P14-11)

The CI job `live-kt` downloads KT-sEMG `run3` (77 s, 53 MB; copyright 2021 Nokia, CC BY 4.0, doi:10.7910/DVN/AV6XIR) from Harvard Dataverse, checks the SHA-256 values in [`tools/ci/kt-semg-run3.sha256`](../tools/ci/kt-semg-run3.sha256), caches the files (`actions/cache`), trains an **in-sample plumbing model** on run3 (`train-kt --fit-run run3 --guard-run run3 --guard-chunk-keys 5`; its guard never commits), replays run3 over a pylsl loopback with `markers` and with `detect` timing, and checks three things: `nts-conform check --require-level trust-ready` passes on the NTS file and the decision log together (`--out` + `--decisions-out`, section 8), the NTS file has no trust decision and the decision log has them, and the header has the replay attribution. Nothing from the recording is committed. Run it locally:

```bash
python tools/ci/kt_lsl_replay.py --cache ~/.cache/fidetype-ci/kt-semg --work /tmp/kt
```

## 6. Latency

The command reports two numbers per window and per decision:

| Number | What it measures |
|---|---|
| `compute` | CPU time of the step: window features + scaler + LDA (window), or beam search + guard (decision) |
| `added` | Wall time from the moment the last needed sample arrived (end of the source poll) to the moment the output is written. This is what Fidetype adds on top of the source |

Measured values are in [the results](../experiments/2026-11-16-p14-04-live/results.md). The window size itself (`pre_s + post_s`, 0.2 s) and the source's own delay (LSL buffering, board packets) come on top.

## 7. Bring your own model and guard

A model is two files: `<name>.model.json` (model card: `sample_rate`, `channels`, `window` {`pre_s`, `post_s`, `n_sub`}, `timing` `markers` or `fixed`, `hop_s`, training data and licence, `weights_sha256`) and `<name>.weights.json` (LDA weights as JSON arrays; no pickle). `fidetype.live.model.fit_model` trains one from window features and key labels. `load_model` checks the SHA-256.

The guard is a drop-in trust guard ([trust quickstart](trust-quickstart.md)) calibrated on **n-best input** made by the same live loop. Use `fidetype.live.build.collect_nbests(model, source)` to get the n-best lists of labelled recordings, then `fidetype.trust.calibrate(nbests, texts, input_kind="nbest", null_inputs=...)`. `make_synthetic` and `train_kt` in [`build.py`](../src/fidetype/live/build.py) are two worked examples. A guard calibrated for another decoder voids the guarantee.

Python API:

```python
import fidetype.trust as ft
from fidetype.live.model import load_model, resolve_asset
from fidetype.live.runner import LiveDecoder
from fidetype.live.sources import SyntheticSource

model = load_model("builtin:synthetic-keys")
guard = ft.load(resolve_asset("builtin:synthetic-keys", ".guard.json"))
dec = LiveDecoder(model, guard, SyntheticSource(5, speed=0), on_decision=print)
stats = dec.run()
```

## 8. What the NTS file holds

`--out` writes JSON Lines (spec 6.2) with [`StreamWriter`](../src/fidetype/writer.py): a `header` (vocab = 32 W3C `KeyboardEvent.code` names, `vocab_type` `key`, no blank, `latency` = `post_s`, `meta` with decoder, weights SHA-256, `stream.id`, `fidetype.live` {source, timing, model, trust config id}), one `frame` per window, `lsl_status` gap records (section 4), then per segment a final `hypothesis` (the n-best list) and `segment_end`, and `end`. The file is a pure NTS input stream: it has no `trust_decision` (spec TD-4).

The trust decisions go to a separate **decision log** (FEP-0001; spec 6.1): JSON Lines, one `trust_decision` per line, no header. The option is `--decisions-out FILE`. With `--out S.jsonl` and no `--decisions-out`, the log is `S.decisions.jsonl` (for example `s.nts.jsonl` -> `s.nts.decisions.jsonl`). `--decisions-out none` turns the log off. `--decisions-out` without `--out` writes only the log. Each decision names its hypothesis (`hypothesis_id` = the `id` of the final `hypothesis` in the NTS file).

```bash
fidetype live --source synthetic --speed 0 --out s.nts.jsonl                     # writes s.nts.jsonl + s.nts.decisions.jsonl
nts-conform check s.nts.jsonl s.nts.decisions.jsonl --require-level trust-ready  # producer level: NTS Trust-ready
```

> **Changed in P14-17 (2026-11-17).** Before, `--out` put the `trust_decision` events into the NTS file, next to the input events. `nts-conform check` failed that file (FEP1-TD-INPUT, TD-4), but `fidetype validate` passed it: the v0.1 suite read `trust_decision` as an unknown event type and ignored it. Now the v0.1 suite has the core check `NTS-TD-INPUT` (all three SDKs, vector V97), and both tools reject such a file. Old files: move the `trust_decision` lines to a separate file. `--publish` used the split before P14-17 (section 8a).

## 8a. Publish over a binding: `--publish` (P14-16)

`--publish TARGET` sends the output of the run to other programs in real time. Repeat the option for more targets. `--out` and `--decisions-out` still write the files (section 8).

| Target | Binding | What goes out | Extra |
|---|---|---|---|
| `lsl` or `lsl:NAME` | nts-lsl/0.1 (FEP-0002) | LSL streams `NAME` (type `NTS`: one channel per key, one sample per frame), `NAME.events` (type `Markers`: header in the stream description, hypotheses, `segment_end`, `lsl_status`, `end`) and `NAME.decisions` (`role = trust_decisions`). Default `NAME`: `fidetype.live`. | `[lsl]` |
| `ws://HOST:PORT/nts` | nts-ws/0.1 (FEP-0004) | `fidetype live` connects to a WebSocket server and sends its NTS stream (`WSProducer`: resend on resume). | `[ws]` |
| `ws://HOST:PORT/decisions` | nts-ws/0.1 (FEP-0004 section 7) | `fidetype live` serves its trust decisions on this address (`WSServer` + `OutputHub`; `ws_seq` numbers, resume with `from_seq`). Port 0 = a free port; the log gives the URL. | `[ws]` |

```bash
fidetype live --source synthetic --publish lsl                                   # LSL outlets
fidetype live --source synthetic --publish ws://127.0.0.1:8765/nts     --publish ws://127.0.0.1:8766/decisions --publish-wait 10                    # WebSocket
nts-conform capture --lsl fidetype.live --out live.capture.json                  # record it (other terminal)
```

- The `trust_decision` events go on the decisions channel only (`NAME.decisions`, `/decisions`). They are not in the NTS stream: FEP-0001 section 3 r4 allows no `trust_decision` in an input stream.
- `--publish-wait S`: before the decode starts, wait up to S seconds for a consumer on each target (default 0). `--publish-linger S`: keep the outlets open S seconds after the end, so that consumers get the last events (default 1).
- A target that fails (for example, the server stops) stops with one log line. The decode, the other targets and `--out` go on. `--summary` lists the events sent per target, or the failure.
- Serve `/decisions` on `127.0.0.1` unless you need other machines. The channel has no token and no TLS here; for that, use the reference server (`python -m fidetype.adapters.ws run`, [FEP-0004](../spec/feps/)) with `--publish ws://HOST:PORT/nts`.
- The outlets are the ones of the adapters: [`NTSOutlet`, `DecisionOutlet`](../src/fidetype/adapters/lsl.py), [`WSProducer`, `WSServer`](../src/fidetype/adapters/ws.py). Code: [`src/fidetype/live/publish.py`](../src/fidetype/live/publish.py). Tests: [`tests/test_live_publish.py`](../tests/test_live_publish.py).
- Evidence: `python -m fidetype.conformance.binding_producers --out DIR --target live-lsl --target live-ws` runs the CLI in a child process on loopback and records it with `nts-conform capture`; `nts-conform check DIR/live-lsl` (or `DIR/live-ws`) gives NTS Trust-ready with the binding. The self-certification list has `fidetype-live-lsl` and `fidetype-live-ws` ([conformance](conformance.md)). CI job `live` runs it.

## 9. Limits

- Onset detection (`--timing detect`): tested on one typist (KT-sEMG); see the P4-10 results for its recall and false alarms. Segment ends still come from markers or `--segment-s`.
- BrainFlow boards have no reconnect in `fidetype live` (only `--source lsl`).
- `--publish`: one NTS stream per run; a WebSocket target has no token or TLS option in `fidetype live` yet.
- Real OpenBCI boards: untested (P4-06, hardware).
- File readers (`--source file`): tested on synthetic files only (P4-16). A file is read into memory at the start; very long recordings need enough RAM.
- The CI replay of KT-sEMG run3 uses an in-sample model: it checks plumbing, not accuracy.
- The trust guarantee holds only for the decoder, device, user and session type of the calibration data ([trust guarantee](trust-guarantee.md)).
