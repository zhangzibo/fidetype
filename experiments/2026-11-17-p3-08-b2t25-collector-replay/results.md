---
title: P3-08 Brain-to-Text '25 replay through the collector - results
type: experiment
task: P3-08
updated: 2026-11-17
---

# P3-08: B2T '25 (T15) replay through the collector, latency against the 50 ms budget

Code: [run.py](run.py). Numbers: [`results/m4-12-summary.json`](results/m4-12-summary.json) (aggregates only: latency, decision counts, conformance levels). Log: `results/run.log`. Per-trial files (n-best texts, truths, decisions, collector outputs): `C:\Users\zhang\bci-data\derived\p3-08-collector-replay\m4-12\` only.

## Outcome: **PASS**. p95 added latency **2.43 ms** (budget 50 ms); outputs reach producer level **NTS Trust-ready**

## Set-up

| Item | Value |
|---|---|
| Data | Brain-to-Text '25, participant T15 (Card et al. 2024, CC0). Replay: 120 `val_eval` trials, spread evenly over the 701 (`np.linspace`); calibration: 722 `val_select` trials. No M4 decoder trained on these trials ([split audit](../../wiki/questions/t15-split-audit.md)). |
| Decoder (before the collector) | M4-12 fixed0 phoneme log-probs (41 symbols, 80 ms frames; checkpoint SHA-256 `2b92ab33...51fd5`), then the P14-03 word decoder (phoneme beam 64 + lexicon + character 6-gram LM) -> 10-best word lists |
| Stream | NTS header (phoneme vocab, `frame_period` 0.08, provenance meta); per trial: frames, the final n-best `hypothesis`, a `segment_end`; 0.5 s pause between trials. 26,394 frames, 2,171.5 s |
| Transport | WebSocket binding (`/nts`, 127.0.0.1), sent **at real time** (frames at their `t`) by `WSProducer` |
| Collector | `fidetype.collector.bench.run` with one TOML file: `validate` (stream level provenance) -> `segment` (no rule fires; the source has the boundaries) -> `guard` (per-user profile, online ACI, passthrough) -> JSON Lines NTS stream + JSON Lines decision log + `os_text` stub + WebSocket `/decisions` |
| Trust step | `fidetype.trust.calibrate` on the `val_select` n-best lists: input kind n-best, alpha 0.05, delta 0.1, seed 0; null control: the decoder's n-best on 200 time-shuffled `val_select` trials (0/200 commits) and the uniform control (0/300). Config `tcfg-c5fd95a99143f814` |
| Machine | Windows 11 laptop, CPU only, isolation runner class `background`, 4 threads |

## Latency (ms, 120 decision steps)

| Stage | p50 | p95 | p99 | max |
|---|---|---|---|---|
| `receive` | 0.047 | 0.085 | 0.237 | 5.24 |
| `processor.check` (validate) | 0.008 | 0.013 | 0.044 | 0.050 |
| `processor.seg` | 0.002 | 0.003 | 0.004 | 0.005 |
| `processor.guard` | 1.32 | 2.31 | 3.00 | 3.23 |
| exporters (nts / log / aac / typing, p95) | 0.061 / 0.059 / 0.004 / 0.003 | | | |
| `pipeline` | 1.40 | 2.38 | 3.06 | 3.37 |
| **`added`** (budget number) | **1.45** | **2.43** | **3.37** | 7.82 |
| `e2e` (from `ws_t_sent`) | 1.73 | 2.64 | 3.64 | 12.67 |

The numbers agree with the synthetic `implant-speech` WebSocket bench (p95 1.27 ms): the guard on a 10-best list is almost all of the time.

## Decisions and conformance

| Item | Value |
|---|---|
| Decisions / segments | 120 / 120 (one final decision per trial) |
| Actions | OFFER 120, COMMIT 0, ABSTAIN 0 |
| Typed by `os_text` | 0 (commits only: yes) |
| Wrong commits | 0 |
| `nts-conform` | producer level NTS Trust-ready; stream export `pass-with-warnings` (stream level provenance; one advisory warning `NTS-VT-PHONEME`: the B2T symbol set is neither ARPAbet nor IPA), decision log `pass` |

> **Our take:** the collector side meets the budget with a wide margin on real implant data at real time. The trust side is vacuous here: the M4-12 decoder is weak, so the calibrated guard commits nothing (0 of 271 LTT items in-sample; the sheet warns). This is the known root cause of gap 14 (P15-19), not a collector issue.

## Re-run with the M4-13 decoder

When the M4-13 queue has written `derived/m4-13/logprobs-m4-13-long0-val_eval.npz` (and the trust-reruns queue the `val_select` decode):

```
.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- ^
    .venv\Scripts\python.exe -I experiments/2026-11-17-p3-08-b2t25-collector-replay/run.py prep --decoder m4-13
.venv\Scripts\python.exe -I experiments/2026-11-17-p3-08-b2t25-collector-replay/run.py replay --decoder m4-13
```

It writes `results/m4-13-summary.json`. `--trials 0` replays all 701 `val_eval` trials (about 3.6 h); `--receiver lsl` uses the LSL binding instead.

## Limits

- 120 of 701 trials (a fixed, even spread), one run. The latency sample is 120 decision steps.
- The decoder and its language model run before the collector (as in the bench profile `implant-speech`); their time is not collector latency.
- Same host, loopback WebSocket. The full pytest suite (4 threads) ran on the same laptop during the first 12 minutes of this replay, so the tail numbers are, if anything, pessimistic. A first replay at 02:32 stopped with the agent session; this run started at 03:11.
