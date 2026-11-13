# M6-08: BrainFlow Synthetic board → LSL → trust layer (live)

Date: 2026-11-12. Task M6-08 (P4 exit check). Script: `run.py`. Raw numbers: `results.json`. Per-run decisions and summaries: `out/` (the raw process logs stay local; their `[fidetype.lsl]` lines are in `results.json`).

## Set-up
- **Source**: BrainFlow 5.24.0 (MIT), Synthetic board (board id -1): 16 EEG channels, 250 Hz, fake data (sine waves + noise). No hardware.
- **Bridge** (process 1): `fidetype lsl brainflow-bridge --board synthetic --trial-s 4`. It sends an `EEG` stream (16 × float32, 250 Hz, labels Fz … F8, unit `microvolts`, `desc/fidetype/role = signal`) and a `Markers` stream with `segment_end` every 4 s.
- **Consumer** (process 2): `fidetype lsl run --stream-name NAME --signal-decoder toy-<mode> --decoder demo --max-attempts 1 --config src/fidetype/demo/trust-config-demo.json`.
- **Toy signal decoder** (`fidetype.decoders.toy_signal`). It does **not** decode text. 25 frames/s over the 28-token character vocab.
  - `flat`: near-uniform frames. They do not depend on the signal.
  - `features`: frames from per-channel log variance × a fixed random matrix. They change with the signal but carry no text information.
- **Expected result**: no COMMIT. The input has no text information.
- One Windows 11 PC (16 logical CPUs), Python 3.12.16, pylsl 1.18.6, CPU only. Both processes on localhost.

## Timeline (seconds after the consumer starts)

| t | Event | What it tests |
|---|---|---|
| 0 | Consumer starts and waits for the stream | start order (consumer first) |
| 2 | Bridge #1 starts | connect |
| 22–25 | Bridge #1 discards the board data for 3 s | gap (dropout) |
| 40 | Bridge #1 is killed (TerminateJobObject, no clean shutdown) | stream loss |
| 44 | Bridge #2 starts with the same `source_id` | reconnect |
| 64 | Bridge #2 stops cleanly (`--duration 20`) | clean stop |
| 70 | Consumer stops (`--duration 70`) | clean exit |

## Results

| | `toy-flat` | `toy-features` |
|---|---|---|
| Final decisions | 13 | 13 |
| COMMIT / OFFER / ABSTAIN | **0** / 0 / 13 | **0** / 0 / 13 |
| Reason (all) | `guard risk 1.00 >= 0.80` | `guard risk 1.00 >= 0.80` |
| p_top1 range (the decoder's own confidence) | 0.15–0.74 | 0.19–0.59 |
| Samples / frames received | 13 218 / 1 320 | 12 946 / 1 293 |
| Gaps found / decisions with a gap | 1 / 1 | 1 / 1 |
| Stream losses (signal + markers) / reconnects | 4 / 2 | 4 / 2 |
| Aborted utterances (no decision on a cut input) | 2 (kill, clean stop) | 2 |
| Clamped / dropped / late samples, rejected events | 0 / 0 / 0, 0 | 0 / 0 / 0, 0 |
| Consumer exit code / stop reason | 0 / duration | 0 / duration |
| LSL transport p50 / p95 | 11.5 / 21.1 ms | 11.5 / 21.2 ms |
| e2e, steady (10 decisions) p50 / p95 / max | 32.8 / 45.7 / 46.6 ms | 38.1 / 45.1 / 49.7 ms |
| e2e, all 13 decisions p50 / p95 / max | 32.7 / 174.2 / 365.8 ms | 37.5 / 182.7 / 382.3 ms |
| Trust layer (decode + guard + policy) p50 / max | 21.9 / 24.6 ms | 25.7 / 33.3 ms |
| Consumer CPU (one core = 100 %) | 2.39 % (1.67 s in 70 s) | 2.19 % (1.53 s) |
| Bridge CPU | 2.34 % (1.36 s in 58 s) | 2.37 % (1.38 s) |
| Bridge push lag (stamp → push) p50 / p95 | 1.6 / 3.4 ms | 1.5 / 3.4 ms |

Definitions:
- **e2e** = consumer LSL clock when the final decision is written − LSL time of the `segment_end` marker that closed the utterance. It includes BrainFlow buffering, the bridge poll (20 ms), LSL, the merge wait, the toy decoder, the beam + LM decode and the trust core.
- **steady** = not next to a dropout. A decision is not steady if its utterance has a gap, or if the signal stopped for more than 1 s after it (the dropout and the kill).
- **transport** = receive time − (LSL timestamp + clock correction), per sample.
- **CPU** = user + kernel time of the Windows job object that holds the process (the venv launcher and the real interpreter).

## Behaviour at start, gap, loss, reconnect and stop
- **Start**: the consumer waited for the stream (`--resolve-timeout 20`) and connected to both streams when bridge #1 started.
- **Gap**: the 3-s dropout gave exactly one `gap` (step > 2.5 sample periods) in each run. The bursty BrainFlow stamps (samples in packets about 16 ms apart) gave no false gap: the bridge smooths the stamps. The trial boundary inside the dropout came 0.25 s late (`trial_hold_s`), so its decision had e2e ≈ 370 ms. The next utterance (25 frames, with the gap) got its own decision. It was an ABSTAIN.
- **Kill**: the consumer saw both streams as lost, **aborted the open utterance** (no decision) and tried to reconnect.
- **Reconnect**: after bridge #2 started, the consumer reconnected by `source_id` and sent a new header. The first utterance after the reconnect was short (66 and 38 frames): the inlet gets only the samples sent after it opens.
- **Clean stop**: bridge #2 stopped. The consumer aborted the open utterance, kept trying to reconnect, and stopped at `--duration` with exit code 0.

## Finding: liblsl `pull_chunk(timeout)` added latency (fixed)
The first full run (`results-before-pull-fix.json`) had transport p50 37 ms and steady e2e p50 57–61 ms. The bridge pushed within 1.5 ms of the stamp, so the delay was on the consumer side. liblsl's `pull_chunk(timeout > 0)` waits until `max_samples` samples are there or until the timeout ends. On a 250 Hz stream with a 50 ms poll, it waited the full 50 ms on most polls. `PylslInlet.pull_chunk` now pulls with timeout 0 and sleeps 2 ms between empty pulls. After the fix: transport p50 11.5 ms (from 37), steady e2e p50 33–38 ms (from 57–61). Consumer CPU went from about 1.4 % to about 2.3 % of one core. The M6-01 numbers in [lsl-input](../../wiki/concepts/lsl-input.md) were measured before this change.

## What this shows, and what it does not
- The full live path works with a BrainFlow board: bridge → LSL → signal decoder → streaming trust layer → `trust_decision` JSON Lines, in two processes, with a dropout, a hard kill, a reconnect and a clean stop.
- On a no-information input, the guard abstained 26 of 26 times. "Always commit" would have typed 26 texts that the user never meant. The demo beam + LM writes fluent text even from these frames. An offline check with the same toy decoders (4-s windows of random 16-channel signal) gave top-1 texts such as "a young girl checked the broken cleaned the boy packed …" (`flat`) and "my mother took the boy packed the nurse took the driver carried …" (`features`).
- It does **not** show that Fidetype decodes text from EEG. The toy decoder carries no text information by design. A positive control (COMMIT on real text information over LSL) is the M6-01 loopback (12/12 COMMIT, equal to the file replay).
- The demo config was fitted for the demo simulator. With a real EEG decoder, fit a new config.
- One machine only. Synthetic board only (no Bluetooth or serial link, no real noise). Short runs (13 decisions per mode).

## Reproduce
```
uv pip install -e ".[lsl,brainflow]"      # or: pip install "fidetype[lsl,brainflow]"
python experiments/2026-11-13-m6-08-brainflow-live/run.py            # about 2.5 min, both modes
python experiments/2026-11-13-m6-08-brainflow-live/run.py --quick    # half-length timeline
```
Manual, two shells:
```
fidetype lsl brainflow-bridge --board synthetic --trial-s 4                    # shell 1
fidetype lsl run --config src/fidetype/demo/trust-config-demo.json \
  --stream-name fidetype.brainflow --signal-decoder toy-flat --decoder demo --max-attempts 1   # shell 2
```
