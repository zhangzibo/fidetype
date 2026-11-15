---
title: M4-13 long decoder training run - pre-declared plan
type: experiment-plan
task: M4-13
updated: 2026-11-15
---

# M4-13: long training run of the causal T15 decoder (plan, written before the run)

## Why
- M4-12 retrained our causal GRU-CTC decoder (`fidetype.decoders.lookahead_gru`) on Brain-to-Text '25, participant T15 (CC0). Dedicated L 0: greedy PER **0.2574** on `val_eval` (701 trials). The published baseline gives **0.101** on the validation partition (README of `nejm-brain-to-text`; facts only, no code copied). See [M4-12 results](../2026-11-14-m4-12-decoder-retrain/results.md).
- M4-12 ran 10,000 steps x batch 96, about 12.5 % of the published trial passes (120,000 x 64). The best step was the last step. M4-12 named training length and 4-days-per-batch sampling as the likely causes of the gap.
- M2-19 showed that the trust layer cannot add value at this decoder accuracy ([M2-19 results](../2026-11-15-m2-19-trust-retune/results.md)). The decoder is the bottleneck.
- Lookahead gave no accuracy gain in M4-12. So this run is **L 0 only** (causal, no lookahead).

## Recipe
The M4-12 recipe ([config](../2026-11-14-m4-12-decoder-retrain/config.json)), with these changes only:

| setting | M4-12 | **M4-13** |
|---|---|---|
| step budget | 10,000 | **115,000** |
| batch | 96 (cap 86,400 padded bins) | **64** (same cap), as the published recipe |
| trial passes | about 0.79 M (102 batches per epoch, mean 79 trials per batch) | **about 6.97 M** (133 batches per epoch, mean 60.6 trials per batch; about 865 epochs; 91 % of the published 7.68 M) |
| LR | 5e-3 peak, 1,000 warmup, cosine to 1e-4 at step 10,000 | 5e-3 peak, 1,000 warmup, **cosine to 1e-4 at step 115,000** |
| runs | 5 models (L 0 … 500 ms) | **one model, dedicated L 0** (`m4-13-long0`) |
| validation | `val_select` every 1,000 steps | `val_select` every 5 % of the budget (5,750 steps) |
| pause | stop file read at validation only | pause / stop file read **after every step** |

Unchanged: model (5 x 768 GRU, patch 14, stride 4, day layers, dropout 0.4), **causal** half-Gaussian smoothing (sd 2 bins), AdamW (eps 0.1; weight decay 1e-3, 0 on biases and day layers), Xavier / orthogonal init, input dropout 0.2, white noise sd 1.0, offset sd 0.2, random cut 0-3 bins, grad clip 10, CTC (blank 0, mean), splits, seed 0.

**We do not use centred smoothing.** The published decoder smooths with a centred Gaussian (about ±80 ms of future input). That breaks our real-time rule (L 0 = no future input). So a residual gap stays possible.

## 4-days-per-batch sampling: smoke-tested, not feasible
The published recipe draws each batch from 4 days. We wrote two versions of it (`train.py`, sampler `days` and `days_band`) and timed them on this GPU (RX 7800 XT, ROCm on Windows, native GRU without MIOpen):

| sampler (batch 64) | s per step | trials per s |
|---|---|---|
| `days`: 4 random days, 16 random trials per day | 5.95 | about 11 |
| `days_band`: 4 random days, 16 trials per day at one shared length quantile | 5.4 | about 12 |
| `bucket` (M4-12 batches: all days mixed, length buckets, cap 86,400 bins) | 1.33-1.42 | about 45 |
| worst case: the 64 longest trials (160,000 padded bins) | 7.7-8.0 | — |

With 4-day batches, each batch mixes short and long trials, so the padded length (and the GPU time) is about 4x larger. In about 45 h this gives only about 27,000 steps (1.7 M trial passes). That is fewer trial passes than the M4-12 batches would give in one quarter of the time. So we keep the M4-12 `bucket` batches. **The 4-days-per-batch question stays open** (deviation from the published recipe; recorded in results).

The smoke test also found a ROCm / Windows problem: `F.ctc_loss` with GPU length tensors raised a size mismatch with the lengths of the previous batch. `train.py` now passes the length tensors on the CPU (same loss values).

## Step budget and time
- Measured (smoke test, bucket sampler, batch 64): 1.33-1.42 s per step. M4-12 long runs: 1.36-1.47 s per step.
- 115,000 steps x 1.42 s = 45.4 h, plus about 20 validations (about 15 s each) and checkpoints. **Expected 45-47 h of GPU time.** Wall time is longer if the user pauses the job.
- No early stopping. The run trains the full budget. `best.pt` = lowest `val_select` PER over the 20 validations; we decode `best.pt` (as M4-12).
- Fallback (as M4-12, pre-declared): if the loss is NaN, or the greedy output on `val_select` is all blank at the 5 % validation, we stop and restart once with peak LR 2.5e-3. We record it as a deviation.

## Checkpoints, pause, resume
- `latest.pt` (model, optimiser, step, best) every 4 minutes and at each validation. Resume (`--resume`) continues at the exact step. The batch sequence is a function of (seed, step), so a resume repeats the same batches.
- `pause` file in the run folder: after the current step, write `latest.pt`, status `paused`, exit (GPU free in seconds). `stop` file: the same with status `stopped`. A hard kill loses at most 4 minutes.
- Launch: `launch.py` (CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB) starts `queue.ps1`. The queue holds a keep-awake request (`SetThreadExecutionState`) while it runs. Commands are in `queue.ps1` and HANDOFF.md.
- Outputs: `C:\Users\zhang\bci-data\runs\m4-13-long0\` (checkpoints, logs) and `C:\Users\zhang\bci-data\derived\m4-13\` (log-probs, per-trial decisions). The M4-01/02 derived folder is read only (features, texts). Nothing else is written.

## Evaluation
**During training (progress only):** greedy PER on `val_select` (722 even-index `val` trials) every 5,750 steps. We report the PER at **25 %, 50 %, 75 % and 100 %** of the budget (steps 28,750 / 57,500 / 86,250 / 115,000). We do not change anything based on these numbers.

**At the end, once:** `decode.py` (GPU) decodes `best.pt` on `val_eval` (701 odd-index `val` trials). `eval.py` (CPU) then runs the M4-12 accuracy logic and the M2-19 trust / control logic:
1. greedy PER (phonemes); word route WER, sentence exact, truth in n-best at T = 1 and at the frame T of the trust config;
2. trust: the M2-19 dedicated L 0 LTT config `tcfg-e7e8c472f6d9ab33` **with the M2-18 commit gate on** (min_chars 1, min_words 0, max_guard_risk 1.0 = `tcfg-4e6143e37d1642f3`), not refitted. Streaming trust layer (frames route), stream = batch check, commits, wrong-commit with CP95, empty commits, eWPM. The ungated config, always-commit and gaze are reference rows;
3. null controls: a 300-trial draw of `val_eval` (seed 0): real, frame-shuffled, uniform (jitter 0.05), gated and ungated.

`val_eval` is used once. We do not tune anything on it. The trust config is not refitted in this task (a re-tune on the new decoder is a separate task and must follow the 2026-11-15 rule: commit gate on and both null controls passed).

## Success rule (as M4-12 pre-declared)
- **"Close"** = `val_eval` greedy PER at L 0 within 0.05 of 0.101, so **PER <= 0.151**.
- We also report the gain over M4-12 (0.2574) and the ratio to 0.101 and to 0.0954 (online copy-task output, a different measure).

## Expected outcome (declared before the run)
- `val_eval` PER below 0.2574. Our guess: 0.15 to 0.22. The M4-12 curve flattened at about 0.002 per 1,000 steps near the end of its (short) cosine schedule, so a longer schedule helps, but causal smoothing and the batching difference may keep us above 0.151.
- Trust (frozen, gated): few commits; the uniform and frame-shuffled controls give 0 commits with the gate.

## What we report
- `val_select` PER curve (20 points) and train loss; GPU hours; s per step; pauses.
- `val_eval`: greedy PER, WER (T = 1 and config T), sentence exact; against M4-12 0.2574, published 0.101 and 0.0954; the "close" verdict.
- Trust with the gated M2-19 config: commits, wrong-commit [CP95], error among commits, empty commits, eWPM, stream = batch; always-commit and gaze; the null controls.
- Deviations (4-day sampling not used; anything else).
- Aggregates only in the repo (`results/eval.json`, `results.md`). No per-trial text, no checkpoints.

## Files
`config.json`, `t15.py` (paths; read-only inputs, own output folder), `train.py`, `decode.py`, `eval.py`, `queue.ps1`, `launch.py`.
