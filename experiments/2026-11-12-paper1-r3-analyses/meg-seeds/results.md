# R3 item 10: MEG decoder seeds 0 / 1 / 2

Review items: stats review M5 (seeds), editor M8 (`\todo{seeds}`). Script: [run.py](run.py). Numbers: [results/seed_cer.json](results/seed_cer.json), [results/cer.md](results/cer.md), [results/seed_trust.json](results/seed_trust.json), [results/trust.md](results/trust.md), per-seed harness / item / split files in `results/seed-<k>/`.

## What we did
- The round-1 GPU queue (`../2026-11-12-paper1-r1-analyses/gpu-seeds`) trained seeds 1 and 2 of the Paper 1 MEG decoder (r4a → r4b full-medium; only the seed differs) and ran greedy, beam and beam + LM decoding with controls. It finished at 01:49 (QUEUE DONE). Seed 0 = the paper's decoder.
- We collected the test CER per seed and ran the G1 trust harness (G1 settings: fit on val, 637 test instances; stages harness without user-model sensitivity, item table, CRC splits) on the seed-1 and seed-2 streams. Example sentences were removed from the committed harness files.

## Results: test CER (637 instances, mean over sentences)

| decoder | seed 0 | seed 1 | seed 2 | mean ± SD |
|---|---|---|---|---|
| greedy | 0.506 | 0.502 | 0.592 | 0.533 ± 0.051 |
| beam + LM (val-tuned) | 0.475 | 0.467 | 0.567 | 0.503 ± 0.056 |
| shuffled MEG, greedy | 0.760 | 0.745 | 0.732 | 0.746 ± 0.014 |
| zeros, greedy | 0.925 | 0.948 | 0.819 | 0.897 ± 0.069 |

Seed 2 stopped early at a worse validation CER (best val CER typed 0.579 at epoch 58, vs about 0.49 for seed 1). All seeds stay far from the shuffled control (gap ≥ 0.14).

## Results: trust layer per seed

| seed | always commit eWPM / wrong-commit | trust eWPM / wrong-commit / commit rate | gaze eWPM | trust − gaze, two-way CI | eligible | true sentence in 10-best |
|---|---|---|---|---|---|---|
| 0 | 2.58 / 0.997 | 3.20 / 0 / 0 | 3.15 | [−0.11, +0.26] | 0.024 | 0.016 |
| 1 | 2.55 / 0.994 | 3.16 / 0 / 0 | 3.15 | [−0.15, +0.23] | 0.036 | 0.019 |
| 2 | 2.35 / 1.000 | 2.96 / 0 / 0 | 3.15 | **[−0.30, −0.05]** | 0.002 | 0.000 |

- On every seed the trust layer committed nothing (0 / 637; one-sided 95 % upper bound 0.0047), while always commit was wrong 99.4–100 % of the time.
- Sentence-grouped CRC (11 of 17 calibration sentences, instance level): mean test wrong-commit 0.019 / 0.032 / 0.000 (seeds 0 / 1 / 2).
- Trust − gaze: about 0 on seeds 0 and 1; on the weaker seed 2 gaze typing is faster (the layer only offers, and offering costs reading time).

## Interpretation
> **Our take:** For the paper: "Over three training seeds the test CER was 0.533 ± 0.051 (greedy) and 0.503 ± 0.056 (beam + LM); seed 2 was worse (0.592 / 0.567). On every seed the trust layer committed no MEG sentence, and its speed was at or below gaze typing (seed 2: −0.30 to −0.05 eWPM)." The MEG safety result (no commits) is stable over seeds; the MEG speed result is not in favour of the layer.
