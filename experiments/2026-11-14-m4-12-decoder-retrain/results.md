---
title: M4-12 decoder retrain - results
type: experiment
task: M4-12
updated: 2026-11-15
---

# M4-12: causal lookahead decoder retrained with a published-like recipe

Plan (written before the runs, with two dated addenda): [plan.md](plan.md). Settings: [config.json](config.json). Full tables: [results/tables.md](results/tables.md). Numbers: `results/accuracy.json`, `results/emission.json`. Log: `results/run.log`. Wiki: [lookahead vs accuracy and latency](../../wiki/questions/lookahead-latency-accuracy.md#m4-12-retrained-decoder-2026-11-15-supersedes-the-m4-0102-accuracy-numbers).

Data and model as M4-01/02: Brain-to-Text '25, T15 (CC0), `fidetype.decoders.lookahead_gru` unchanged. Same splits (`val_eval` = 701 odd-index `val` trials). Same evaluation code (`decode.py`, `run.py` copied, only paths changed). Only the training recipe changed (see the plan): 10,000 steps x batch 96, LR 5e-3 cosine to 1e-4, AdamW eps 0.1, weight decay 1e-3 (0 on biases and day layer), Xavier / orthogonal init, input dropout 0.2, noise sd 1.0 + offset 0.2 + random cut 0-3 bins.

## Diagnosis (summary; the full table is in the plan)
1. **Too little training.** M4-01 ran 4,560 steps (about 0.24 M trial passes, 30 epochs). The published baseline runs 120,000 x 64 = 7.68 M trial passes. M4-01 had 3 % of that, and its LR schedule reached 0 at the end. So "best epoch = last epoch" meant "the schedule ended", not "the model converged".
2. **LR 10x lower** than the published recipe (5e-4 vs 5e-3), Adam eps 1e-8 vs 0.1.
3. **The L 0 model under-fitted.** Train CTC loss 2.43 (dedicated L 0) vs 0.81 (dedicated L 500 ms) at the end of M4-01, with the same GRU. The linear lookahead branch did the work that the badly trained GRU could not do.
4. Smaller items: init, input dropout, augmentation strength, weight decay.
5. Not causes: CTC blank handling, frame lengths, the split (val_eval is half of the same validation partition), the causal mask (tests prove it; at L 0 the branch adds a constant).
6. **A residual gap is expected:** the published decoder smooths with a centred Gaussian (about ±80 ms), so it sees about 80 ms of future input. We keep causal smoothing.

## Results

### Training (val_select = even-index val trials, checkpoint selection only)
| run | L | best val_select PER (step) | final train CTC loss | GPU time (h) |
|---|---|---|---|---|
| `m4-12-fixed0` | 0 | 0.2561 (10,000) | 0.8499 | 3.85 |
| `m4-12-fixed25` | 500 ms | 0.3024 (10,000) | 1.0076 | 4.1 (active; wall time includes a 4 h PC sleep and a 1 h pause) |
| `m4-12-shared` | {0 … 500 ms} | mean of L 0 / 200 / 500 ms: 0.2577 (10,000) | 0.8531 | 3.93 |
| `m4-12-fixed10` | 200 ms | 0.2590 (10,000) | 0.8512 | 3.83 |
| `m4-12-fixed15` | 300 ms | 0.2587 (10,000) | 0.8496 | 3.82 |

- val_select PER fell slowly at the end in all runs (fixed0: 0.2595 → 0.2578 → 0.2561 at steps 8,000 / 9,000 / 10,000). The best step is again the last, but the gains per 1,000 steps are now about 0.002 (in M4-01 they were still about 0.01 per epoch).
- Step time 1.36 to 1.47 s (RX 7800 XT, ROCm, native GRU without MIOpen).

### Accuracy (val_eval, 701 trials), old (M4-01/02) vs new (M4-12)
| model | L (ms) | greedy PER old | **greedy PER new** | WER (T = 1) old | **WER (T = 1) new** | sentence exact (T = 1) new |
|---|---|---|---|---|---|---|
| shared | 0 | 0.6565 | **0.2634** | 0.8907 | **0.4049** | 0.088 |
| shared | 40 | 0.4449 | **0.2614** | 0.6791 | **0.4034** | 0.086 |
| shared | 100 | 0.4097 | **0.2623** | 0.6310 | **0.4032** | 0.084 |
| shared | 200 | 0.3858 | **0.2612** | 0.5979 | **0.4006** | 0.080 |
| shared | 300 | 0.3768 | **0.2608** | 0.5803 | **0.4030** | 0.083 |
| shared | 500 | 0.3687 | **0.2617** | 0.5728 | **0.4013** | 0.087 |
| dedicated_0 | 0 | 0.6954 | **0.2574** | 0.9307 | **0.3998** | 0.090 |
| dedicated_10 | 200 | — | **0.2594** | — | **0.3923** | 0.101 |
| dedicated_15 | 300 | — | **0.2599** | — | **0.3998** | 0.090 |
| dedicated_25 | 500 | 0.3487 | **0.2988** | 0.5405 | **0.4565** | 0.068 |

*dedicated_10 (200 ms) and dedicated_15 (300 ms) were added by plan addendum 1 (no M4-01/02 counterpart).*

- **Gap to the published decoder.** Best L 0 model (dedicated_0): PER 0.2574. Published baseline on the validation partition: 0.101 (README). Published online copy-task output: 0.0954. So we are at about 2.5x the published PER (2.7x the online number). The old models were about 7x. We did **not** get close by the pre-declared rule (within 0.05 of 0.101).
- **The lookahead curve is now flat.** Shared model: PER 0.2634 at L 0 and 0.2608 to 0.2623 for L 40 to 500 ms. The whole range is 0.0026, smaller than the gap between two runs with the same L (shared L 0 0.2634 vs dedicated L 0 0.2574). WER (T = 1) 0.4049 → 0.4013.
- **Dedicated models at 200 and 300 ms equal L 0** (PER 0.2594 and 0.2599 vs 0.2574; WER (T = 1) 0.3923 and 0.3998 vs 0.3998). **The dedicated L 500 ms model is worse** (PER 0.2988; train loss 1.0076 vs about 0.85 for all other runs). In M4-01/02 it was the best model. So a long fixed lookahead (25 bins x 64 projected features into the branch) slows training with this recipe; up to 300 ms it is neutral.
- So the large M4-02 gain from lookahead (0.6565 → 0.3687) was an artefact of the under-trained GRU. With a better trained GRU, our lookahead branch adds nothing measurable.

### Trust outcomes (frozen config `tcfg-f5ca0020b3b8fce2`, not refitted)
- 0 commits in all conditions (701/701 OFFER, wrong-commit 0, CP95 [0.000, 0.005]). Stream = batch 701/701 everywhere.
- eWPM 5.77 to 6.02 (old 3.38 to 5.15); gaze alone 4.02. Now every condition is faster than gaze alone, also at L 0. Always-commit eWPM 5.31 to 5.62.

### Emission timing (greedy CTC path, matched phonemes, median [IQR])
| comparison | emission stamp Δ (ms) | ready time Δ (ms) | n phonemes |
|---|---|---|---|
| shared L 40 / 100 / 200 / 300 / 500 vs shared L 0 | 0 | +40 / +100 / +200 / +300 / +500 | 14,646 to 14,872 |
| dedicated_0 vs shared L 0 | 0 [0, 80] | 0 [0, 80] | 14,415 |
| dedicated_10 (L 200) vs dedicated_0 | −80 [−80, 0] | +120 [120, 200] | 14,317 |
| dedicated_15 (L 300) vs dedicated_0 | −80 [−80, 0] | +220 [220, 300] | 14,309 |
| dedicated_25 (L 500) vs dedicated_0 | −400 [−960, −320] | **+100** [−460, 180] | 13,190 |

- The dedicated L 500 ms model still emits phonemes earlier (−400 ms median) than the L 0 model. But now its phonemes are ready **100 ms later**, not 180 ms earlier as in M4-02. The M4-02 "ready earlier" result came from the weak L 0 model, which emitted late (+240 ms vs the shared model then; 0 ms now).
- The declared `latency` (L) stays an upper bound on signal use. The measured ready delay of the dedicated L 500 ms model is 100 ms (median), so it is not a good estimate of the user delay either.
- Dedicated 200 / 300 ms models emit one frame (80 ms) earlier than L 0 and are ready 120 / 220 ms later: they convert part of their lookahead into earlier emission, but less than in M4-02.
- The last emitted phoneme is 2.32 to 2.72 s (median) before the trial end (M4-02: 3.12 to 3.68 s).

## What this means
- Our lookahead mechanism (a linear branch over the next L bins, added to the GRU output) does not help a well trained causal GRU on T15. The data may still contain useful future context: the published decoder uses about 80 ms (centred smoothing) and is 2.5x better. But the gap is mostly not from lookahead: a shared model with 500 ms of lookahead is not better than L 0.
- The remaining gap is more likely training length (12.5 % of the published trial passes) and recipe details (4 days per batch, no dropout after the last GRU layer, AMP) than causality.
- For Paper 2 / NTS: "lookahead buys accuracy" is **not** supported by our data. Only the bookkeeping result stands (declared `latency` = upper bound; measure the ready time).

## Limitations
- One participant, one seed per run. No repeat to measure run-to-run spread (shared L 0 vs dedicated L 0 differ by 0.0060).
- 10,000 steps (12.5 % of the published trial passes); best step = last step in every run, so all models could still improve a little.
- One lookahead design. A different design (for example a delayed output, or the GRU reading future bins) could behave differently.
- Frozen trust config, fitted on another decoder: no commit-side result.
- No latency stage (the timing cores were busy; compute does not depend on the weights, see M4-02).

## Deviations from the plan
- Smoke-test changes before the plan commit: batch 128 filled the 16 GB GPU (5.66 s per step), so batch 96 / cap 86,400 bins; the hand-written GRU was slower, so `fast_gru` = false.
- `dedicated_25`: the PC slept 17:57-21:57 (Sleep from the Start menu, see the M6-15 log) and the queue was paused 22:44-23:49 on user request (GPU needed). Training resumed from `latest.pt` both times (step 4,391 and 6,328). `train_sec` in its status includes the sleep (8.03 h); active time is about 4.1 h.
- The queue was restarted three times to change how it starts (no visible windows), to add `dedicated_15` (addendum 1) and to add a hold for another agent's quiet-machine latency run (addendum 2). Recipe and budgets did not change.

## Incident: overwritten M4-01/02 trust files (2026-11-15)
- The copied `run.py` wrote its per-trial trust decisions to the shared derived folder `C:\Users\zhang\bci-data\derived\m4-01-02-lookahead\` with the M4-01/02 file names (`trust-<model>-L<bins>.json`). The model keys (`shared`, `dedicated_0`, `dedicated_25`) are the same in both experiments.
- So the M4-12 accuracy stage overwrote all 8 M4-01/02 trust files: `trust-dedicated_0-L0.json` at 2026-11-14 16:15, `trust-dedicated_25-L25.json` and the six `trust-shared-L*.json` between 2026-11-15 05:23 and 05:40. The latency re-run agent found it. The M4-01/02 per-trial originals are lost. Their aggregate numbers survive in the committed M4-01/02 `results/accuracy.json` and `results.md`. The M4-01/02 logprobs, params and decode files were not touched (their names carry the run name).
- Fix (06:18, before the next accuracy stage): `run.py` now writes trust files and its word-decode cache to `C:\Users\zhang\bci-data\derived\m4-12-decoder-retrain\` (`own_derived_dir` in config.json). We moved the 8 M4-12 trust files there and copied the cache. Shared inputs (features, texts, logprobs) are still read from the M4-01/02 folder.

## GPU time
About 19.6 h of training (fixed0 3.85, fixed25 about 4.1 active, shared 3.93, fixed10 3.83, fixed15 3.82), plus about 0.5 h for benchmarks and smoke tests, plus about 2 min of GPU decoding per model. The queue ended 2026-11-15 13:58 (`m4-12-queue.DONE`, ok=True).

## Note 2026-11-17 (P14-15): word-decoder settings
The word-decoder settings (lm 1.0, edit penalty 12, bonus 3) were tuned on 400 B2T track `cal` trials; 16 of them are `val_eval` trials ([T15 split audit](../../wiki/questions/t15-split-audit.md), issue D). A re-tune without these 16 trials picks edit penalty 8 (an exact WER tie, decided by truth-in-n-best); without `val_eval` and `val_select` the setting stays the same ([P14-15 results](../2026-11-17-p14-15-retune/results.md)). The word-level numbers on this page are not changed. Gap 44 (P14-18) reruns the M4-12 `val_eval` word decode with edit penalty 8.

## Correction note 2026-11-17 (P14-18): word decode with edit penalty 8
Pre-registered rerun ([P14-18/19 results](../2026-11-17-p14-18-19-followups/results.md), plan `3d07cb4`) of all 10 conditions with the setting tuned without the 16 `val_eval` tune trials (lm 1.0, **edit penalty 8**, bonus 3). The reference runs with edit 12 reproduced every number on this page. Result: **effect on 1 of 90 metrics**. Truth in n-best (frozen T) of shared L 40 ms is 0.121 → 0.148 (half-width 0.024). All other changes are below their half-widths, for example dedicated_0 WER (T = 1) 0.3998 → 0.3976 (half-width 0.0173), WER (frozen T) 0.4105 → 0.4041, eWPM 5.94 → 6.03, and still 0 commits. Every change favours edit 8, so the numbers on this page are not optimistic. The numbers above are not changed. Gap 50 (P14-21) reruns the downstream M4-x rows.
