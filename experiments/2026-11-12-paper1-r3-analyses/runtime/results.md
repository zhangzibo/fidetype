# R3 item 9: trust-layer run time per decision

Review item: editor M8 (run-time TODO). Script: [run.py](run.py). Numbers: [results/runtime.json](results/runtime.json), [results/tables.md](results/tables.md).

## What we did
- For each device, the main trust pipeline was fitted as in the paper (cached decodes). For every test item, three trust-layer steps were timed separately with `time.perf_counter_ns`, 3 passes: frame temperature on the stream, `analyze` (sentence / character calibration, conformal set, guard, policy inputs), `decide` (policy). The decoder is not part of the layer; it was timed on 10 uncached items for scale.
- Hardware: AMD Ryzen 7 9800X3D (8 cores, 16 threads), 31.2 GB RAM, Windows 11 (10.0.26200), Python 3.12.16, NumPy 2.5.4, **one thread**. A GPU training job and other CPU analyses ran at the same time, so the numbers are upper bounds for an idle machine.

## Results (ms per decision)

| device | trust layer, median | trust layer, 95th pct | of which frame T / analyze / decide (median) | decoder (beam + LM), median |
|---|---|---|---|---|
| B2T ours | 0.30 | 1.04 | 0.16 / 0.11 / 0.003 | 232 |
| B2T published gate | 0.28 | 0.49 | 0.16 / 0.11 / 0.003 | (our decoder) |
| sEMG session-cal. | 0.19 | 0.99 | 0.08 / 0.10 / 0.002 | 67 |
| sEMG cross-session | 0.18 | 0.96 | 0.08 / 0.10 / 0.002 | 72 |
| sEMG cross-subject | 0.19 | 0.89 | 0.08 / 0.10 / 0.002 | 45 |
| MEG | 0.24 | 1.06 | 0.12 / 0.11 / 0.002 | 185 |

## Interpretation
> **Our take:** The trust layer costs about 0.2–0.3 ms per decision (95th percentile ≈ 1 ms) on one CPU thread, i.e. 0.1–0.5 % of the decoder time. Suggested sentence for §11: "On one CPU thread (AMD Ryzen 7 9800X3D), the trust layer took a median of 0.18–0.30 ms per decision (95th percentile ≤ 1.1 ms), against 45–232 ms for the beam-search decoder."
