---
title: M4-12 decoder retrain - pre-declared plan
type: experiment-plan
task: M4-12
updated: 2026-11-14
---

# M4-12: retrain the causal lookahead decoder closer to the published T15 recipe (plan, written before the full runs)

## Why
M4-01/02 trained our causal GRU-CTC (`fidetype.decoders.lookahead_gru`) on Brain-to-Text '25 T15 (CC0). Greedy PER on `val_eval` (701 trials): shared L 0 0.6565, shared L 500 ms 0.3687, dedicated L 0 0.6954, dedicated L 500 ms 0.3487 ([results](../2026-11-13-m4-01-02-lookahead/results.md)). The best epoch was the last one (30 of 30) in all runs. We cannot trust the lookahead curve until the decoder is much closer to the published one.

## Comparison target
- The published baseline code (`Neuroprosthetics-Lab/nejm-brain-to-text`, **no licence**: we read `rnn_args.yaml`, `rnn_model.py`, `rnn_trainer.py`, `data_augmentations.py` and the training README for facts only, and copy no code) says its baseline RNN reaches an aggregate PER of **10.1 % on the validation partition** (README).
- Our `val_eval` is the odd-index half of the same validation partition (`data_val.hdf5` of each session). So **0.101** is the closest like-for-like target.
- **0.0954** is a different number: the greedy PER of the **online** decoder output in `t15_copyTask.pkl` (1,718 copy-task trials, 15 sessions). We report both, but 0.101 is the fair target.

## Diagnosis (ours vs the published baseline)
| item | M4-01/02 (ours) | published baseline | effect (our judgement) |
|---|---|---|---|
| training length | 4,560 steps, about 53 trials per batch = about 0.24 M trial passes (30 epochs) | 120,000 steps x 64 = 7.68 M trial passes (about 950 epochs) | **main cause**: 3 % of the published training; LR reached 0 at the end, best = last epoch |
| peak LR, schedule | 5e-4, 500 warmup, cosine to 0 | 5e-3, 1,000 warmup, cosine to 1e-4 | **main cause**: 10x lower LR |
| Adam eps | 1e-8 | 0.1 | large eps damps steps of rare-gradient weights; part of the published recipe |
| weight decay | 1e-5 on all | 1e-3 on weights, 0 on biases and day layers | minor |
| init | PyTorch default (uniform) | Xavier (input weights, output), orthogonal (recurrent) | minor to medium |
| input dropout after day layer | none | 0.2 | regularisation (matters with long training) |
| augmentation | noise sd 0.8, offset sd 0.2 | noise sd 1.0, offset sd 0.2, random cut 0-3 bins | minor |
| smoothing | **causal** half-Gaussian, sd 2 bins | **centred** Gaussian, sd 2 bins, taps > 0.01 kept (about ±4 bins = ±80 ms), train and eval | the published decoder sees about 80 ms of future input; we keep causal smoothing (our definition of L), so a gap at L = 0 is expected |
| model | 5 x 768 GRU, patch 14, stride 4, day layer (identity init, softsign) | same | none |
| dropout 0.4 | after every GRU layer incl. the last | between GRU layers only | minor; not changed (model code stays unchanged) |
| batching | all days mixed, length buckets | 4 days per batch | unknown; not changed |
| CTC | blank 0, mean, `zero_infinity` | blank 0, mean | none |
| split | `val_eval` = odd half of `data_val` | `data_val` (all) | comparable |

**Evidence that the GRU stack, not the lookahead mechanism, was the bottleneck:** the dedicated L 0 model's train CTC loss stopped at 2.43 (epoch 30), while the dedicated L 500 ms model reached 0.81 with the same GRU. The only difference is the linear lookahead branch. So the L 0 model **under-fits** (high train loss, val PER still falling). The large M4-02 gain from 0 to 40 ms is therefore partly "a linear future branch helps a GRU that did not learn", not a property of the data.

**Lookahead implementation at L = 0:** the branch adds `tanh(la_out.bias + la_emb[0])`, a constant per unit, which the output bias can absorb. Causality is proved by `tests/test_causal_lookahead.py`. We do not expect it to hurt L = 0.

## What we change (training only; the model class, decode, NumPy streaming and evaluation code stay the same)
| setting | new value |
|---|---|
| step budget | **10,000 steps**, batch 96 (cap 86,400 padded bins per batch) = about 0.96 M trial passes, about 119 epochs (4x M4-01; 12.5 % of the published trial passes) |
| LR | peak 5e-3, 1,000 warmup steps, cosine to 1e-4 at step 10,000 |
| optimiser | AdamW, betas (0.9, 0.999), eps 0.1; weight decay 1e-3 on weight matrices, 0 on biases, lookahead embedding and day layer |
| init | Xavier uniform GRU input weights and output layer, orthogonal recurrent weights (per gate), zero biases |
| input dropout | 0.2 after the day layer (training only) |
| augmentation | white noise sd 1.0, constant offset sd 0.2 (before the causal smoothing), random cut 0-3 bins at the trial start |
| validation | `val_select` greedy PER every 1,000 steps (and at the end); `best.pt` = lowest mean `val_select` PER over the run's eval L |

Why not 120,000 steps: on this GPU (RX 7800 XT, ROCm on Windows) one step takes about 1.5 s at batch 96 (smoke test). MIOpen cannot run the GRU backward on this build, a hand-written GRU loop was 2x slower (2.00 vs 1.04 s per step at batch 64 x 900 bins) and bf16 autocast was 7x slower (7.38 s). Batch 128 filled the 16 GB GPU and spilled into shared memory (5.66 s per step). 120,000 steps at batch 64 would take about 43 h per model.

## Runs (in this order, one GPU job at a time)
| run | L | why |
|---|---|---|
| `dedicated_0` (`m4-12-fixed0`) | 0 | like-for-like with the published decoder |
| `dedicated_25` (`m4-12-fixed25`) | 25 bins = 500 ms | the other end of the curve |
| `shared` (`m4-12-shared`) | drawn per batch from {0, 2, 5, 10, 15, 25} bins | the full curve 0, 40, 100, 200, 300, 500 ms from one model |
| `dedicated_10` (`m4-12-fixed10`) | 10 bins = 200 ms | optional middle value, only if GPU time allows |

Estimated GPU time: about 4.3 h per run (10,000 x 1.5 s + validation), about 13 h for the first three, about 17 h with `dedicated_10`.

## Stopping rule
- Each run trains for the fixed budget of 10,000 steps. No early stopping. `best.pt` (lowest `val_select` PER) is the model we decode.
- We do not change any hyperparameter after this plan is committed, with one pre-declared fallback: if a run's output collapses (all-blank greedy output on `val_select`, or a NaN loss) or `dedicated_0` has `val_select` PER > 0.80 at step 2,000, we stop it and restart that run once with peak LR 2.5e-3. We record this as a deviation.
- `val_eval` is decoded once per final model (as M4-01/02). We do not tune on it.

## Evaluation (same code as M4-01/02)
- `decode.py` and `run.py` are copies of the M4-01/02 files with only the paths changed (same greedy PER, same word route at T = 1 and at the frozen T, same frozen trust config, same emission analysis).
- Stages: `accuracy`, `emission`, `tables`, `figure`. **No `latency` stage** (the timing cores are busy with a soak test; compute does not depend on the weights in any case).
- We rerun the accuracy + emission stages on the new models if `dedicated_0` val_eval PER is at least 0.15 lower than the M4-01/02 value (0.6954). Otherwise we report the PER only.
- We report: PER / WER per L, old vs new, and the gap to 0.101 (validation partition) and 0.0954 (online copy task). "Close" = val_eval PER at L 0 within 0.05 of 0.101.

## Expected outcome (declared before the runs)
- `dedicated_0` val_eval PER well below 0.6954; we guess 0.15 to 0.30. A residual gap to 0.101 is expected (12.5 % of the published training, causal smoothing, no 4-days-per-batch sampling).
- The lookahead gain from 0 to 40 ms will shrink a lot. The gain to 500 ms will stay, but be smaller in absolute PER.

## Files
`config.json` (all settings), `train.py` (new trainer), `t15.py` (copy, new config), `decode.py` and `run.py` (copies of M4-01/02, paths only), `queue.ps1` (GPU queue). Checkpoints, logits and logs stay in `C:\Users\zhang\bci-data` (never in the repo).

## Addendum 2026-11-14 23:51 (written before these runs start)
- Request: keep the GPU busy overnight and fill the middle of the curve with dedicated models at 200 ms and 300 ms.
- 200 ms = 10 bins is the run `dedicated_10` (`m4-12-fixed10`), already in this plan as optional. It is now **required**.
- 300 ms = 15 bins is a **new** run `dedicated_15` (`m4-12-fixed15`). Same recipe, budget, checkpoint rule and stopping rule as the other runs (config.json, `train` block unchanged).
- Queue order: `dedicated_25` (resumed at step 6328 after a pause on user request) → `shared` → `dedicated_10` → `dedicated_15`. The first CPU pass (accuracy, emission, tables, figure) runs while `dedicated_15` trains. A second pass adds `dedicated_15`. Then `C:\Users\zhang\bci-data\runs\m4-12-queue.DONE`.
- Status before this addendum: `dedicated_0` done (val_eval greedy PER 0.2574). No other run had been decoded on val_eval.
- Launch: `launch_queue.py` (CREATE_NO_WINDOW, new process group, job breakaway). The queue holds a keep-awake request while it runs.

## Addendum 2 2026-11-14 23:55 (queue order; before `shared` starts)
- Request: leave a quiet machine overnight for another agent's latency re-run.
- New order: `dedicated_25` → `shared` → CPU stages (accuracy, emission, tables, figure) → write `C:\Users\zhang\bci-data\runs\m4-12-queue.PHASE1` → **hold** (no GPU or CPU work; keep-awake stays on) until `C:\Users\zhang\bci-data\runs\latency-rerun.DONE` exists or 2026-11-15 08:30, whichever is first → `dedicated_10` → `dedicated_15` → CPU stages → `m4-12-queue.DONE` (only at the very end).
- Applied without stopping `dedicated_25`: the running queue stops at its next job boundary (stop file); a hand-over queue (`launch_queue.py --after-pid`) waits for it to exit and continues with the new script.
- No change to the recipe, budgets or evaluation.
