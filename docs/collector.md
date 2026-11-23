# Collector

How to run the Fidetype Collector: one service that reads NTS from several sources, runs processors on it and writes the results to several targets.

**Status:** Alpha ([status levels](glossary.md#status-levels))

The [Collector](glossary.md#collector) reads NeuralTextStream ([NTS](glossary.md#nts-neuraltextstream)) input from several sources, runs processors on it, and writes the results to several targets. One TOML or JSON file wires it. The design copies the structure of the OpenTelemetry Collector (receivers → processors → exporters). The text and the code are our own.

The Collector is a reference version (v0) in the Python package. The design is the draft [FEP-0006](../spec/feps/0006-collector.md) (a [FEP](glossary.md#fep) is an enhancement proposal). It is not part of NTS 1.0, because it does not change the format.

```
 file  ----> receiver --\                                                   /--> jsonl (NTS stream, decision log)
 ws /nts --> receiver ---+--> validate --> segment --> trust | guard --> thin --> redact --+--> stdout
 LSL -----> receiver --/                                                     +--> ws /decisions
                                                                             +--> LSL decisions outlet
                                                                             \--> os_text (stub)
```

## Run it

```sh
fidetype collector --config examples/collector/collector.toml --check   # check the file, print the pipelines
fidetype collector --config examples/collector/collector.toml           # run it
```

`fidetype-collector` is the same command. Run the example from the repository root. Relative paths in a configuration resolve against the folder of the configuration file. The example reads a synthetic conformance vector and uses a toy trust configuration. Fit a real one with `fidetype.calibrate(...)`.

## Components

| Kind | Types | Job |
|---|---|---|
| Receiver | `file` (JSON Lines, also tail mode; NPZ), `websocket` (FEP-0004 `/nts`), `lsl` (FEP-0002) | Read a source. Turn every loss into a `gap` or `lost` status |
| Processor | `validate`, `segment`, `trust`, `guard`, `thin`, `redact`, `privacy` | Check events, add segment ends, make trust decisions, drop previews, remove or hash decoded text, filter `meta` keys per a privacy policy |
| Exporter | `jsonl`, `stdout`, `websocket` (`/decisions`), `lsl`, `os_text` (`stub` backend only) | Write items out. Never change them |
| Pipeline | any number | Connect named receivers, processors and exporters |
| Service | `[service]` | Log level, metrics file, health endpoint (`/healthz`, `/metrics`, localhost by default), `latency = true` (per-stage latency) |

Examples: [`collector.toml`](../examples/collector/collector.toml) (file input) and [`collector-lsl.toml`](../examples/collector/collector-lsl.toml) (LSL input; needs the `lsl` extra). Each key is explained in comments in the files.

### Component options

| Component | Keys | What it does |
|---|---|---|
| `segment` processor | `pause_s`, `blank_frames`, `max_frames`, `unit` | Adds a `segment_end` when the time between two frames is more than `pause_s`, after `blank_frames` blank frames in a row (after a non-blank frame), or after `max_frames` frames. Causal. A `segment_end` from the source passes through. |
| `guard` processor | `guard` or `profile`, `online`, `online_options`, `passthrough`, `save_profile`, `audit_keep` | The drop-in trust guard ([trust quickstart](trust-quickstart.md)). `profile` loads a per-user profile ([personalisation](trust-personalisation.md)) with its drift tests. `online = "aci"` (or `aci_window`, `window`, `bandit`) adds the online controller. One decision per segment. `passthrough = true` also passes the input events on (without the `ws_*` binding keys), so a `jsonl` exporter can write the NTS stream next to the decision log. |
| `os_text` exporter | `backend = "stub"`, `path`, `separator` | Types **only** final text COMMITs (never OFFER, ASK, ABSTAIN or a provisional decision). The stub types into memory and writes one line per typed text with the full decision next to it. Real backends (Windows TSF, Android IME, macOS, IBus) are not written yet. |
| `privacy` processor | `policy`, `key_env`, `key_id`, `subject_index` | `subject_index` writes one line per stream (session + HMAC code of `subject.id`; needs `key_env`) so that an erasure request finds the subject's outputs. Filters header `meta` keys per a policy file (keep / drop / hash per key or `namespace.*`; default for other keys; PII scan) and, with `text = "drop"` or `"hash"`, the decoded text (then it must come after the trust step). Without `policy` the built-in default keeps the provenance keys and drops `subject.*`, `session.*`, `user.*` and unknown keys. See [provenance and privacy](provenance-and-privacy.md) |
| `jsonl` exporter path `{session}` | `path = "out/streams/{session}.nts.jsonl"` | One file per stream / decision session, so an erasure can delete a whole session file. See [provenance and privacy](provenance-and-privacy.md) section 8 |
| Input-event `jsonl` file without `{session}` | refused | When the pipelines of the exporter can carry more than one stream (several receivers, several file paths, a websocket or LSL receiver), `--check` refuses the file. Reason: the streams would follow one another in one file (several headers, no stream id). That file is not one NTS stream, `nts-conform` cannot check it, and an erasure can only delete it whole. Use `path = "out/streams/{session}.nts.jsonl"`. A decision log is not affected (each line names its session) |
| `trust` processor, `ledger.anchor` | `{ dir = "out/anchors", key_env = "...", every_n = 100, every_s = 60 }` | Signed anchors (Ed25519, extra `[sign]`) on stop and every N entries / T seconds; key from an environment variable or a key file only. See [provenance and privacy](provenance-and-privacy.md) section 4.1a |
| Any exporter, `refuse_research_only` | `refuse_research_only = true`, `unknown_licence = "refuse"` (default) or `"pass"` | Drops each decision whose `input.research_only` is `true` (FEP-0010 TD-15), so a product build (for example `os_text`) types nothing that depends on non-commercial data. A decision without the key has an **unknown** licence: `"refuse"` drops it too, `"pass"` exports it. Counters `research_only_refused` and `licence_unknown_refused` in `/metrics`; one log line at the first drop of each kind. On a `jsonl` or `stdout` exporter of input events the option acts **per stream**: the stream header gives the licence (`meta` `data.licence` and `data.research_only`, the same flags that a trust layer copies into `input.research_only`). A research-only stream is dropped whole (header and every event up to its `end`); a stream without either key, or an event before any header, follows the `unknown_licence` rule. Counters `research_only_streams_refused`, `research_only_events_refused`, `licence_unknown_streams_refused`, `licence_unknown_events_refused`. A refused stream writes no file (per-session `{session}` files and a single file alike). Default (option absent): every item goes out, as before. See [provenance and privacy](provenance-and-privacy.md) section 2 |
| `trust` processor, `ledger.lineage` | a lineage spec file | Writes sources and artifacts (with licences) into the ledger at start; each decision then carries licence flags |
| `[service] latency` | `latency = true`, `latency_budget_ms` | Records the time of each stage (section "Latency budget"). The numbers are in `/metrics` and in `metrics_file` (`latency_ms`). |

The `guard` processor uses the same parts as `fidetype live` ([live decode](live-decode.md)): `TrustGuard.decide`, and the key beam search `nbest_of_frames` for key frames. For an n-best guard the segment input is the last final `hypothesis`; for a logits guard it is the frames of the segment.

## Safety and privacy rules

| Rule | What the Collector does |
|---|---|
| No final decision on a cut segment | A gap or a lost input drops the open utterance without a decision |
| No silent drop | An unreadable line or an invalid event becomes a `gap` status |
| Decoded text is personal data | The `redact` processor removes `shown` or replaces it with an HMAC (key from an environment variable) |
| `meta` holds only what the policy allows (SEC-3, SEC-4) | The `privacy` processor drops or hashes `meta` keys per a policy file and drops a value that looks like an e-mail address, a phone number or an IP address |
| No secrets in files | Tokens and keys come only from environment variables. A key in the file is a configuration error |
| No blank final COMMIT | The `trust` processor adds a commit gate if the configuration has none (rule TD-9). The `guard` processor always has the gate |
| Only committed text reaches the OS | The `os_text` exporter types final COMMITs only and logs the full decision next to each typed text |

## Integration test and latency budget

`python -m fidetype.collector.bench` runs the full pipeline from one TOML file on synthetic input at a realistic rate. The test file [`tests/test_collector_pipeline.py`](../tests/test_collector_pipeline.py) runs the same code in CI.

```
receiver (websocket /nts | file | lsl)
  -> validate (stream level provenance) -> segment -> guard (per-user profile, online ACI, passthrough)
  -> jsonl NTS stream + jsonl decision log + os_text stub (+ websocket /decisions)
```

```sh
python -m fidetype.collector.bench --out bench-out                                  # all profiles, WebSocket + file
python -m fidetype.collector.bench --profile emg-key --receiver lsl --json r.json   # needs the lsl extra
```

Each run checks:

- `nts-conform` gives the outputs (NTS stream file + decision log) the producer level **NTS Trust-ready** (claim `text`).
- The `os_text` stub typed exactly the final COMMITs.
- One decision per segment; the `/metrics` file holds the latency numbers.

### Profiles

| Profile | Input | Guard | Gated |
|---|---|---|---|
| `implant-speech` | CTC character frames at 50 Hz (20 ms) and the decoder's final n-best `hypothesis` after each utterance (the decoder and its language model run before the collector, as in a B2T '25 replay). No source boundaries: the segmenter cuts after 6 blank frames | n-best guard, calibrated on synthetic n-best lists | yes |
| `emg-key` | One key-posterior frame per key over the 32-key KT-sEMG vocabulary, sent at 50 Hz (faster than any typist), and a `segment_end` per phrase | `builtin:synthetic-keys` (the guard of `fidetype live`) on the key beam search | yes |
| `implant-logits` | The implant frames without the hypothesis | logits guard: its built-in CTC prefix beam search (beam 64, lexicon, n-best confidences) runs **inside** the collector | no (reported) |

All input is synthetic and our own. It contains no participant data.

### Stages

| Stage | From | To |
|---|---|---|
| `receive` | the receive stamp of the trigger event: `ws_t_recv` (WebSocket server) or `_fidetype_t_recv` (LSL receiver: the time the sample was pulled from the inlet) | the receiver's poll returns |
| `processor.<name>`, `exporter.<name>` | start of the call | end of the call |
| `pipeline` | poll returns | the last exporter returns |
| **`added`** (the budget number) | the trigger event is available (its receive stamp; for file input: the poll return) | the last exporter returns |
| `e2e` | `ws_t_sent` of the trigger event (producer on the same host) | the last exporter returns |

The trigger event of a step is the last boundary (`segment_end`, `end`) of the batch. A boundary that the segmenter adds carries the stamps of the frame that caused it. One sample per step that wrote a decision. The clock is `time.perf_counter`.

### Results

Measured on 2026-11-17 on a Windows 11 laptop (CPU, 12 segments per run), with the default settings:

| Profile | Input | `added` p95 | Budget (p95 < 50 ms) |
|---|---|---|---|
| implant-speech | WebSocket, file, LSL | about 1 ms | PASS |
| emg-key | WebSocket, file, LSL | 1 to 3 ms | PASS |
| implant-logits | WebSocket, file, LSL | about 100 to 125 ms | over (not gated) |

- Almost all of the added time is the `guard` stage (the trust decision; for `emg-key` also the key beam search). `validate`, `segment` and the exporters take less than 0.3 ms per step at p95. The WebSocket `e2e` time (with the loopback transport) is 0.2 to 0.3 ms above `added`.
- `implant-logits` does not meet the budget: the guard's built-in CTC beam search (n-best confidences over 64 texts) takes 60 to 110 ms per segment. This is decoding work, not collector overhead. It is an open item: decode during the frames, not at the boundary.
- A replay of real [B2T '25](glossary.md#b2t-25-brain-to-text-25) data (participant [T15](glossary.md#t12-t15)) at real time over WebSocket, 120 trials: p95 `added` 2.43 ms, producer level NTS Trust-ready. Details: [replay record](../experiments/2026-11-17-p3-08-b2t25-collector-replay/results.md).

The tables of each measurement step are in [Evidence and history](#evidence-and-history) at the end of this page.

### LSL input: receive stamps, heartbeat and merge window

The LSL receiver stamps each event with the time when the LSL source pulled its sample from the inlet (`_fidetype_t_recv`, `time.perf_counter` clock, never written out). `receive` and `added` count from this stamp. So the time that the inlet merge window (`merge_window_s`) holds an event is part of the budget number.

A frames stream and an events stream go through one merge. The merge holds an event until the other stream has passed its time, or until `merge_window_s` ends. `LSLEventSource.poll` waits at most until the merge window of the oldest held event ends.

Between markers the events stream is idle. Without more information, every frame would wait for the full merge window. NTS 1.0 RC4 amendment 5 adds two binding rules ([FEP-0002](../spec/feps/0002-nts-over-lsl.md) section 6 rules 7 and 8):


- **LSL-C7 heartbeat.** An empty events-stream sample is a heartbeat. It is not an NTS event, but it tells the consumer that the events stream has passed its timestamp. `NTSOutlet` (used by `replay-to-lsl`, the bench and `fidetype live --publish lsl`) sends one after each frame, with the frame's timestamp. The merge then releases the frame at once.
- **LSL-C8 equal times.** At equal times the merge gives the frame first. `NTSOutlet` now stamps a marker with the timestamp of the frame before it (before: that time plus a small step). So a `segment_end` leaves the merge as soon as its last frame has arrived, not at the next frame.
- `LSLEventSource.poll` waits on the inlet that holds the oldest item back (for a held frame: the events inlet), so the heartbeat ends the wait.

Why the order stays right: a frame at time t is released only when the events inlet has a sample at t or later. Events-stream timestamps do not decrease (LSL-C7, MUST), so no later marker has a time before t; a later marker at exactly t goes after the frame anyway (LSL-C8). A marker at time t is released only when the frames inlet has a frame at t or later. Frame times increase strictly (LSL-C4), so every later frame comes after t. The merge window is not needed for the order; it only limits the wait for a producer that sends no heartbeat.

The bench now runs LSL input at the **receiver default** window (0.05 s; `LSL_MERGE_WINDOW_S = None`). `--no-lsl-heartbeat` gives a producer without heartbeats, for comparison.

- With heartbeats the LSL `added` latency is the same as for WebSocket and file input (the guard, 1 to 2 ms). The merge window no longer counts.
- Without heartbeats implant-speech waits for the full window (each frame is held). emg-key passes without heartbeats too: a marker stamped with the frame time also moves the events watermark to that frame, so the frames before it leave the merge with it (LSL-C8), and the closing marker does not wait for the next frame.
- A producer of another vendor that sends no heartbeat still gets the 0.05 s wait. For it, choose `merge_window_s` below the budget (for example 0.02 s; bench option `--lsl-merge-window`, `LSL_MERGE_WINDOW_S`). A window shorter than the time skew between the two LSL streams can release events out of order (counted as `late_releases`).

### The CI gate and its tolerance

- The test `test_pipeline_websocket_at_50_hz_within_budget` (both gated profiles, WebSocket input, 8 segments), the file and LSL tests, and the bench step of the `collector` job check the gated profiles against the **limit = 50 ms x `FIDETYPE_LATENCY_TOLERANCE`**.
- The default tolerance is **1.0** (the budget itself). CI sets it to 4 on macOS only (job `conformance-os`; larger scheduler jitter). Our local p95 is 1 to 3 ms for WebSocket and file input. For LSL input the p95 is about 1 to 3 ms at the receiver default window (0.05 s), because the producer sends heartbeats. The LSL test runs both gated profiles. Set `FIDETYPE_LATENCY_TOLERANCE=2` only on a machine that is known to be slow, and say so in the report.
- The guard imports its parts when it starts, so the first decision has no import cost.

#### Gate modes

The gate has two modes (`fidetype.collector.latency.gate_mode`, `gate_verdict`; bench `run_gated`, option `--gate`):

| Mode | Default when | Median rule (p50 of `added` and of `pipeline` < limit) | Tail rule (p95 of `added` < limit) |
|---|---|---|---|
| `strict` | not on CI (local machine) | the one run | the same one run; no repeat |
| `ci` | `GITHUB_ACTIONS=true` or `CI=true` / `1` | **every** run; a median failure is never repeated | at least **one of 3** runs; a new run (fresh collector, folder `attempt-<k>`) only after a tail-only failure |

- `FIDETYPE_LATENCY_GATE=strict` or `=ci` overrides the default. Use `strict` to check a quiet CI machine as strictly as a local one.
- Why: a gated run has only 8 to 12 decision steps. Then the p95 is in practice the slowest step. One thread stall of the shared runner in one step moves the p95 above 50 ms, while our own processing stays near 1 ms. Two CI failures had this cause (table in [Evidence and history](#evidence-and-history)).


- The second of these failures shows the split: `receive` (the trigger event waits in the receiver queue: thread wake-up under runner load) holds the tail; the guard p95 was 0.93 ms. The gate report now prints which stage holds the tail (`receive` or `pipeline`) and the numbers of each run.
- What the `ci` mode still catches: a slow step of our code, or a wait in our receive path that happens on each decision, moves the median (strict on every run). A slow path in a part of the steps repeats in each independent run, so 3 runs fail. Only a rare stall that does not repeat passes.
- What it does not catch: a rare slow path of our code that hits fewer than about 1 in 12 steps and only in some runs. The local `strict` gate and the bench tables above are the check for it.
- The CI job `collector` runs the pipeline tests with the `lsl` extra (so the LSL test runs), prints the bench report, and runs the kit against the collector consumer (next section).

## The collector as a consumer: the conformance kit

`fidetype-collector consume [--profile P] [--level L] FILE` reads one file or capture through the collector's own input path and checks it with the `validate` processor at stream level `L`. Exit 0 = accept, 1 = reject, 2 = usage error. This is the kit contract of [`nts-conform kit`](conformance.md):

```sh
nts-conform kit --require-level trust-ready --binding nts-lsl/0.1 --binding nts-ws/0.1 \
  --cmd "fidetype-collector consume --profile {profile} --level {level} {path}"
```

| Kit file | Receiver | Checks |
|---|---|---|
| JSON Lines stream or decision log, NPZ (`v0.1`, `fep-0001`, `fep-0003`, `fep-0005`) | `file` | `validate`: header, frames, events, decisions; FEP-0003 and FEP-0005 rules |
| LSL capture, kind `inlet` (`fep-0002`) | `lsl`, on an LSL source that plays the recorded inlets (no network) | the reference LSL consumer (binding rules), then `validate` |
| WebSocket capture, kind `ingest` (`fep-0004`) | `websocket`; the server is not started, the recorded steps go into its ingest core | the reference WebSocket consumer (binding rules, refusals), then `validate` |
| LSL `decisions` and WebSocket `subscribe` captures | the decisions that the reference subscriber reads | the reference consumer, then `validate` (decision rules) |

- The intent (FEP-0003) and control (FEP-0005) rules in `validate` are the rule functions of `fidetype.conformance.profiles` (not a copy). They see the newest 512 profile events of a stream and the newest 512 decisions of a session (bounded memory).
- Loss inside a capture (`gap`, `lost`) does not reject it: the binding defines it, and the collector handles it (no decision on a cut utterance). A file receiver loss (an unreadable line) still rejects a file.

Result (2026-11-17): **36 / 36** kit entries give the expected verdict. Consumer level **NTS Trust-ready** for `text`, `intent` and `control`, with the bindings `nts-lsl/0.1` and `nts-ws/0.1`. `certified.json` lists `fidetype-collector` with these profiles and bindings. An earlier version gave 28 / 36 (`text` only, no bindings).

Full rule list and design notes: [wiki/concepts/collector.md](../wiki/concepts/collector.md).

## Evidence and history

<details>
<summary>Evidence and history</summary>

These are the measurement steps behind the [Results](#results). They are kept as a record.

**Step 1: first run (2026-11-17).** For LSL input these numbers start at the poll return, so they do not include the inlet merge-window wait. `added` latency in milliseconds.

| Profile | Receiver | p50 | p95 | p99 | Budget |
|---|---|---|---|---|---|
| implant-speech | websocket | 1.05 | 1.27 | 1.27 | PASS |
| implant-speech | file | 0.69 | 1.12 | 1.32 | PASS |
| implant-speech | lsl | 0.81 | 1.11 | 1.19 | PASS |
| emg-key | websocket | 1.85 | 2.34 | 2.37 | PASS |
| emg-key | file | 1.01 | 1.16 | 1.21 | PASS |
| emg-key | lsl | 1.59 | 2.23 | 2.55 | PASS |
| implant-logits | websocket | 64.2 | 104.1 | 107.4 | over (not gated) |
| implant-logits | file | 62.5 | 108.0 | 109.6 | over (not gated) |
| implant-logits | lsl | 66.8 | 107.3 | 117.4 | over (not gated) |

**Step 2: LSL receive stamps.** From this step on, `receive` and `added` count from the LSL receive stamp. `LSLEventSource.poll` now waits at most until the merge window of the oldest held event ends (before: it waited for the next sample, one frame period, 20 ms at 50 Hz). The bench set `merge_window_s = 0.02` for LSL input. The receiver default stayed 0.05 s. Same laptop; the B2T '25 replay ran at the same time.

| Profile | Run | `merge_window_s` | p50 | p95 | p99 | Budget |
|---|---|---|---|---|---|---|
| implant-speech | first run (poll return, no merge wait) | 0.05 | 0.81 | 1.11 | 1.19 | PASS |
| implant-speech | stamps only | 0.05 | 61.1 | 61.3 | 61.3 | over |
| implant-speech | stamps only | 0.02 | 40.4 | 41.1 | 41.2 | PASS |
| implant-speech | stamps + poll wait bound | 0.05 | 58.0 | 60.4 | 60.6 | over |
| implant-speech | **stamps + poll wait bound (bench default)** | **0.02** | **21.2** | **26.8** | **30.2** | **PASS** |
| emg-key | first run (poll return, no merge wait) | 0.05 | 1.59 | 2.23 | 2.55 | PASS |
| emg-key | stamps only | 0.05 | 21.6 | 63.6 | 103.7 | over |
| emg-key | stamps only | 0.02 | 21.6 | 36.3 | 50.3 | PASS |
| emg-key | stamps + poll wait bound | 0.05 | 21.3 | 35.8 | 49.1 | PASS |
| emg-key | **stamps + poll wait bound (bench default)** | **0.02** | **21.6** | **22.9** | **23.3** | **PASS** |
| implant-logits | first run | 0.05 | 66.8 | 107.3 | 117.4 | over (not gated) |
| implant-logits | stamps + poll wait bound | 0.02 | 74.5 | 114.8 | 119.3 | over (not gated) |

The same run for the other receivers (no change expected): implant-speech websocket 1.07 / 1.27 / 1.32, file 0.55 / 0.71 / 0.72; emg-key websocket 1.84 / 2.33 / 2.46, file 1.40 / 2.05 / 2.17; implant-logits websocket 59.0 / 97.3 / 100.4, file 64.2 / 96.2 / 100.1 (p50 / p95 / p99 ms).

**Step 3: LSL heartbeat and equal times.** The bench now runs LSL input at the receiver default window (0.05 s; `LSL_MERGE_WINDOW_S = None`). `--no-lsl-heartbeat` gives a producer without heartbeats, for comparison. implant-logits gives 13 decisions for 12 segments with and without this change (the same at commit `4350b2d`).

| Profile | Run | `merge_window_s` | p50 | p95 | p99 | Budget |
|---|---|---|---|---|---|---|
| implant-speech | receive stamps + poll wait bound | 0.05 | 58.0 | 60.4 | 60.6 | over |
| implant-speech | receive stamps + poll wait bound (old bench default) | 0.02 | 21.2 | 26.8 | 30.2 | PASS |
| implant-speech | no heartbeat, marker at frame time | 0.05 | 63.5 | 63.7 | 63.9 | over |
| implant-speech | **heartbeat + equal times (receiver and bench default)** | **0.05** | **0.96** | **1.07** | **1.10** | **PASS** |
| emg-key | receive stamps + poll wait bound | 0.05 | 21.3 | 35.8 | 49.1 | PASS |
| emg-key | receive stamps + poll wait bound (old bench default) | 0.02 | 21.6 | 22.9 | 23.3 | PASS |
| emg-key | no heartbeat, marker at frame time | 0.05 | 2.34 | 2.77 | 2.96 | PASS |
| emg-key | **heartbeat + equal times (receiver and bench default)** | **0.05** | **1.74** | **2.89** | **3.36** | **PASS** |
| implant-logits | receive stamps + poll wait bound | 0.02 | 74.5 | 114.8 | 119.3 | over (not gated) |
| implant-logits | heartbeat + equal times | 0.05 | 61.3 | 123.7 | 147.3 | over (not gated) |

**CI failures that led to the `ci` gate mode.**

| CI run | Job | Profile / input | `receive` p95 | `pipeline` p95 | `added` p50 | `added` p95 | Rerun |
|---|---|---|---|---|---|---|---|
| 44673291448 (commit `8180a30`) | pytest windows-latest py3.12 | emg-key / websocket (8 steps) | not printed | not printed | not printed | 320.7 | green |
| 44913077810 attempt 1 (commit `03d2308`) | collector (ubuntu) | implant-speech / websocket (12 steps) | 52.8 (max 117.2) | 1.27 | 1.09 | 54.1 | green |

</details>
