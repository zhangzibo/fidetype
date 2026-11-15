---
title: M4-01/02 latency rerun on a quiet machine - results
type: experiment
task: M4-02R
updated: 2026-11-15
---

# M4-02R: M4-01/02 latency rerun on a quiet machine

Plan (written before the run): [plan.md](plan.md). Original run: [M4-01/02 results](../2026-11-13-m4-01-02-lookahead/results.md). Code: [rerun.py](rerun.py), which calls the original `run.py` stages unchanged (`stage_latency(force=True)`, `stage_emission()`), plus a parameterised copy of the same timed loop for the M4-12 checkpoints. Numbers: `results/latency.json` (primary), `results/secondary.json` (M4-12), `results/emission.json`, `results/inputs.json` (input SHA-256, status, action counts). Log: `results/run.log`. Wiki: [lookahead vs accuracy and latency](../../wiki/questions/lookahead-latency-accuracy.md).

## When and where
- Run: 2026-11-15 05:41:43 to 06:12:38 (1,855 s). Start condition: the M6-15 soak DONE file (03:36) and the M4-12 `PHASE1` marker (05:40:14). The M4-12 queue held all GPU and CPU work until this run wrote `latency-rerun.DONE` (06:12:38). No other job ran.
- CPU class: **timing**, cores 8, 10, 12, 14, timing lock held, above-normal priority (same as M4-01/02). Keep-awake on during the run.

## Measurement environment
| run | foreign load on the timing cores | SMT siblings busy | machine load | clean |
|---|---|---|---|---|
| M4-01/02 (2026-11-14) | 5.77 % | 25.23 % | 39.46 % | **no** (limit 5 %) |
| **this run, primary** | **1.77 %** | 11.27 % | 29.45 % | **yes** |
| this run, secondary (8 blocks) | 1.56 % to 2.03 % | 10.25 % to 10.86 % | - | yes (all 8) |

The primary result is a clean benchmark by the isolation rule.

## Primary: original M4-01/02 checkpoints (shared model, 200 trials, the same trials)
| L (ms) | decoder push per 20 ms bin p50 / p95 (ms), new (old) | trust push per frame p50 / p95 (ms), new (old) | end of utterance total p50 / p95 / max (ms), new (old) |
|---|---|---|---|
| 0 | 0.04 / 2.23 (0.04 / 2.01) | 0.20 / 0.29 (0.24 / 0.33) | 86.0 / 162.4 / 273.3 (79.8 / 148.3 / 280.6) |
| 40 | 0.08 / 2.08 (0.09 / 1.96) | 0.17 / 0.28 (0.24 / 0.34) | 101.6 / 171.3 / 249.5 (99.6 / 188.9 / 262.6) |
| 100 | 0.06 / 2.08 (0.08 / 2.06) | 0.19 / 0.28 (0.25 / 0.36) | 99.1 / 158.6 / 259.2 (107.5 / 201.0 / 281.0) |
| 200 | 0.07 / 2.08 (0.09 / 2.10) | 0.17 / 0.28 (0.25 / 0.36) | 99.2 / 163.4 / 248.8 (103.1 / 180.3 / 274.4) |
| 300 | 0.07 / 2.09 (0.09 / 2.11) | 0.18 / 0.28 (0.25 / 0.36) | 96.7 / 170.2 / 234.6 (99.4 / 193.3 / 256.3) |
| 500 | 0.06 / 2.08 (0.07 / 1.99) | 0.18 / 0.28 (0.24 / 0.34) | 96.9 / 171.4 / 291.2 (99.5 / 173.0 / 272.1) |

- **Compute vs L: confirmed flat.** Decoder p95 2.08 to 2.23 ms per bin at every L. Trust p95 0.28 to 0.29 ms per frame. End-of-utterance p50 86.0 to 101.6 ms. The decoder flush at the end costs 0.56 ms or less (max, L = 500 ms).
- The quiet machine lowered the trust-layer cost by about 20 % (p95 0.33-0.36 → 0.28-0.29 ms) and the end-of-utterance p95 at most L (for example L 100: 201.0 → 158.6 ms). The decoder p95 per bin did not drop (about 2.1 ms; L 0 is 2.23 vs 2.01). So the per-bin p95 is set by the GRU step itself, not by the foreign load.
- The conclusions of M4-01/02 stand: about 2 ms + 0.3 ms per 80 ms frame, far below real time. The final decision after the end of the utterance does not wait for L.
- NumPy streaming vs torch batch logits: max abs log-prob difference 1.23e-04 to 1.62e-04 (the same as before).

### Trust (frozen config `tcfg-f5ca0020b3b8fce2`)
- **0 commits.** Streaming final actions counted in this run: 200/200 OFFER at every L. This equals the M4-01/02 accuracy stage (701/701 OFFER, 0 commits).

### Emission timing (not a wall-clock measure)
- `stage_emission()` on the same stored logits gave a file byte-for-byte identical to the M4-01/02 `emission.json`. Dedicated L 500 ms vs dedicated L 0: emission stamp −680 ms, ready time **−180 ms** (median, n 5,120). Shared model: ready = +L exactly. This confirms only that the inputs did not change. Emission timing depends on frame stamps, not on machine load.

## Secondary: M4-12 retrained checkpoints (separate condition)
The M4-12 decoders are much better: val_eval greedy PER dedicated L 0 0.2574, dedicated L 500 ms 0.2988, shared 0.2608 to 0.2634 across L ([M4-12 results](../2026-11-14-m4-12-decoder-retrain/results/tables.md)).

| model / L (ms) | decoder push per bin p50 / p95 (ms) | trust push per frame p50 / p95 (ms) | end total p50 / p95 / max (ms) | final actions | foreign load |
|---|---|---|---|---|---|
| dedicated L 0 | 0.04 / 2.11 | 0.16 / 0.26 | 100.2 / 181.7 / 351.2 | 200 OFFER | 1.70 % |
| dedicated L 500 | 0.06 / 2.10 | 0.18 / 0.26 | 98.8 / 172.7 / 257.8 | 200 OFFER | 1.56 % |
| shared L 0 | 0.04 / 2.09 | 0.19 / 0.29 | 98.9 / 169.4 / 208.9 | 200 OFFER | 1.68 % |
| shared L 40 | 0.08 / 1.70 | 0.21 / 0.32 | 100.6 / 167.7 / 310.5 | 200 OFFER | 2.03 % |
| shared L 100 | 0.07 / 1.70 | 0.22 / 0.32 | 97.7 / 171.1 / 221.6 | 200 OFFER | 1.70 % |
| shared L 200 | 0.08 / 1.71 | 0.22 / 0.32 | 99.8 / 172.1 / 283.3 | 200 OFFER | 1.90 % |
| shared L 300 | 0.08 / 1.71 | 0.21 / 0.31 | 99.6 / 175.1 / 227.8 | 200 OFFER | 1.76 % |
| shared L 500 | 0.06 / 1.70 | 0.22 / 0.32 | 101.4 / 173.8 / 283.2 | 200 OFFER | 1.87 % |

- Compute is flat in L for the retrained models too (same architecture, so the same cost is expected). NumPy vs torch: max abs log-prob difference 3.62e-05 to 5.34e-05.
- **Trust: 0 commits** in all 8 conditions (200/200 OFFER). The M4-12 accuracy stage also gave 0 commits (701/701) for the shared model at every L. The frozen config still does not commit, even on the better decoder.
- **Emission timing: the M4-01/02 "180 ms earlier" result does not hold for the retrained decoders.** Dedicated L 500 ms vs dedicated L 0: emission stamp −400 ms (IQR [−960, −320]), but ready time **+100 ms** (IQR [−460, +180]), n 13,190 matched phonemes. So the L 500 ms model emits earlier, but by less than its 500 ms lookahead, and its phonemes are ready 100 ms **later** (median) than those of the L 0 model.

> **Our take:** The M4-01/02 result "a model trained with lookahead is ready earlier than a model without it" came from an under-trained L 0 model that emitted late (PER 0.6954). With a better L 0 decoder (PER 0.2574) the lookahead model is ready about 100 ms later. The general point still holds: the declared `latency` (500 ms) is an upper bound on signal use and not the delay a user sees (here +100 ms, not +500 ms). But the sign of the effect depends on the decoder. Do not quote the −180 ms figure without this caveat.

## Deviations from the plan
1. **The accuracy-stage reference files were overwritten.** The M4-12 phase-1 CPU stage (2026-11-15 05:26 to 05:40) rewrote `DER/trust-shared-L*.json` with M4-12 shared-model decisions, just before this run. So the original stage's `same_action_as_accuracy_stage` (200/200 in `latency.json`) compares the M4-01/02 streaming decisions with M4-12 decisions. It matches only because both are all OFFER. It is not a valid check. Instead, `rerun.py` counted the final streaming actions directly. A thin subclass of `StreamingTrustLayer` reads the decisions after each `push` returns (`results/inputs.json`, `primary_streaming_actions`). The overhead is one empty-list check per push. The M4-01/02 shared-model trust files are lost. The aggregate numbers stay in the committed M4-01/02 `accuracy.json`.
2. The wait condition changed during the night (coordinator): `m4-12-queue.PHASE1` in place of `m4-12-queue.DONE`, a budget to 08:30 with a hard stop, and `latency-rerun.DONE` always written. The run ended at 06:12, so no step was skipped.
3. The secondary condition includes the M4-12 shared model (timed at every L), in addition to the two dedicated models.

## Limitations
- One machine (Ryzen 7 9800X3D), one run, 200 trials per condition. No LM rescoring.
- The secondary emission result uses greedy paths and exact matches only, as in M4-01/02. The IQR is wide ([−460, +180] ms).
- The frozen trust config never commits on either decoder, so this test still says nothing about the commit side.
