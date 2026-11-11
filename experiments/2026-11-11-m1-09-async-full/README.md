# M1-09: async decoder on the full cache

Goal: reach about 0.59 greedy test CER in the **asynchronous** setting (no key times as inputs).

## Design
- Model: the M1-C ConvCTC recipe, unchanged. Stage r4a pretrains the keystroke head (`ctc_weight` 0). Stage r4b trains CTC + keystroke aux 0.5 from the r4a weights.
- Async: key times are only training labels of the aux head. Inference uses the sentence segment of the continuous MEG and no key times.
- Data: all 80 cached blocks (`subjects` null, `blocks` null), 19 participants. The split is the cache hash split by sentence, the same as M1-15 full-r1 (101 / 11 / 17 unique sentences; 4026 / 437 / 637 instances).
- Why this option: it is the cheapest one, and it is a proven recipe (0.619 greedy, 0.590 beam + LM on 20 blocks). 4x data improved M1-15 from 0.577 to 0.508. A run takes about 1 h, so one night also fits a medium-model variant.
- New: an opt-in EMA trend stop in `train.py` (`train.smooth_alpha` 0.3, `train.min_delta`). `best.pt` keeps the best raw val metric.
- Extra (only if the queue reaches it before 03:30): the same two stages with a medium model (`conv_dim` 320, `model_dim` 256, 4 Conformer layers).

## Smoke test (2026-11-10, 3 min each)
| run | s/epoch | GPU memory | trend |
|---|---|---|---|
| r4a-full | 22.4 | 3.76 GB | val key acc 0.38 at epoch 5 |
| r4b-full (init from smoke r4a) | 22–26 | about 3.8 GB | train loss 5.83 → 3.35, val CER 0.92 → 0.69 in 6 epochs |
| r4b-full-medium (no init) | 33 | 6.0 GB | val CER 0.84 → 0.73 in 3 epochs |

## Queue
`queue.ps1` here is a copy of `C:\Users\zhang\bci-data\runs\queue-2026-11-11-m1-09\queue.ps1` (the copy that runs).
Steps: train r4a-full, train r4b-full, `fidetype.decoders.infer --control` (greedy; real / shuffled / zeros; means over sentences, subjects and participants), then the beam + char LM (`experiments/2026-11-08-m1c2-beam-lm/run.py --run-name m1-09-r4b-full`: val grid `lm_weight` 0–1.0 × `insertion_bonus` 0–1.5, raw and frame-calibrated, then test once).

Outputs:
- runs: `C:\Users\zhang\bci-data\runs\m1-09-*`
- greedy metrics: `C:\Users\zhang\bci-data\streams\m1-09-r4b-full\metrics.json`
- beam + LM tables: `results/beam-m1-09-r4b-full/tables.md`
