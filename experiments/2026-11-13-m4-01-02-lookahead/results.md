---
title: M4-01 / M4-02 causal lookahead decoder - results
type: experiment
task: M4-01, M4-02
updated: 2026-11-14
---

# M4-01 / M4-02: causal decoder with a lookahead L, and accuracy and latency against L

Data: Brain-to-Text '25, participant T15, `t15_copyTask_neuralData` (CC0). Settings: [config.json](config.json). Decoder: `fidetype.decoders.lookahead_gru` (our own code, M4-01, commit `25ebb0c`; causality tests in `tests/test_causal_lookahead.py`). Full tables: [results/tables.md](results/tables.md). Numbers: `results/accuracy.json`, `results/emission.json`, `results/latency.json`. Log: `results/run.log`. Wiki page: [lookahead latency vs accuracy](../../wiki/questions/lookahead-latency-accuracy.md).

## How to run
1. GPU (`C:\venvs\fidetype-rocm`): `queue.ps1` runs `prep.py`, then `train.py` and `decode.py` for `shared`, `dedicated_0`, `dedicated_25` (about 1 h 50 min per model, 30 epochs). Checkpoints and logits stay in `C:\Users\zhang\bci-data` (not in the repo).
2. CPU (repo `.venv`), background class:
   `python -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-13-m4-01-02-lookahead/run.py accuracy emission` (about 20 min).
3. Latency: `.venv\Scripts\python.exe -I experiments/2026-11-13-m4-01-02-lookahead/run.py latency-force` (about 13 min). The stage takes the timing class itself (`isolated("timing")`: cores 8, 10, 12, 14, timing lock, above-normal priority).
4. `run.py tables figure`.

## Design (as declared in config.json before the runs)
- One model, three runs. `shared`: L drawn per batch from {0, 2, 5, 10, 15, 25} bins. `dedicated_0`: L = 0 only. `dedicated_25`: L = 25 bins (500 ms) only.
- L values: 0, 50, 100, 200, 300, 500 ms, as `floor(ms / 20)` bins. So "50 ms" is 2 bins = **40 ms**.
- Output frame k reads bins up to `t_k + L` only (`t_k` = last bin of its 14-bin patch; stride 4 bins = 80 ms). Stamp = end of bin `t_k`. NTS `latency` = `decoder.lookahead_s` = L x 20 ms; `decoder.causal = true`.
- Evaluation set: `val_eval` = odd-index dataset `val` trials, 701 trials (3 with an out-of-vocabulary word are not used), 41 sessions. Checkpoint choice used the even-index trials only.
- Trust: the frozen Paper 1 v4 config `tcfg-f5ca0020b3b8fce2` (M4-06), applied unchanged through `StreamingTrustLayer` (frames route). It was fitted on another decoder's logits.

## Results

### Accuracy (val_eval, 701 trials)
| model | L (ms) | greedy PER | WER (T = 1) | sentence exact (T = 1) | WER (frozen T 3.815) |
|---|---|---|---|---|---|
| shared | 0 | 0.6565 | 0.8907 | 0.000 | 0.9307 |
| shared | 40 | 0.4449 | 0.6791 | 0.006 | 0.7189 |
| shared | 100 | 0.4097 | 0.6310 | 0.004 | 0.6824 |
| shared | 200 | 0.3858 | 0.5979 | 0.016 | 0.6477 |
| shared | 300 | 0.3768 | 0.5803 | 0.017 | 0.6376 |
| shared | 500 | 0.3687 | 0.5728 | 0.014 | 0.6383 |
| dedicated_0 | 0 | 0.6954 | 0.9307 | 0.000 | 0.9996 |
| dedicated_25 | 500 | 0.3487 | 0.5405 | 0.034 | 0.5345 |

- PER falls fast and then flattens. Of the total shared-model drop from L = 0 to L = 500 ms (0.6565 → 0.3687), 0.2116 comes from the first 40 ms.
- The dedicated L = 500 ms model is better than the shared model at 500 ms (PER 0.3487 vs 0.3687). The dedicated L = 0 model is worse than the shared model at 0 (0.6954 vs 0.6565).
- **All numbers are poor.** The published T15 decoder (also a unidirectional GRU, stamped with latency 0) has greedy PER 0.0954 on its own online output ([source page](../../wiki/sources/brain-to-text-25-copytask.md)). Our L = 0 models are about 7x worse. The best epoch was the last epoch (30 of 30) in all three runs, and val PER still fell. So our decoder is under-trained and not tuned. The size of the lookahead gain may come partly from this, not from causality alone.

### Trust outcomes (frozen config, not refitted)
- **0 commits** in all 8 conditions: 701/701 OFFER. Wrong-commit 0 (CP95 [0.000, 0.005]). Stream = batch harness 701/701 in all conditions.
- eWPM: shared 3.47 (L 0), 4.13, 4.27, 4.44, 4.48, 4.48 (L 500); dedicated_0 3.38; dedicated_25 5.15. Gaze typing alone: 4.02. Always-commit: 2.57 to 4.56 eWPM at wrong-commit 0.9629 to 1.0.
- So with L = 0 the trust layer is slower than gaze alone (OFFER of bad lists costs time). From L = 40 ms it is faster than gaze. The config never commits because it was fitted on a much better decoder; this test says nothing about the commit side.

### Emission timing (greedy CTC path, matched phonemes)
"Ready" = stamp of the phoneme's first greedy frame + L. Medians; full IQRs in [results/tables.md](results/tables.md).

| comparison | emission stamp Δ (ms) | ready time Δ (ms) | n phonemes |
|---|---|---|---|
| shared L 40 / 100 / 200 / 300 / 500 vs shared L 0 | 0 | +40 / +100 / +200 / +300 / +500 | 5944 to 6094 |
| dedicated_0 vs shared L 0 | +240 | +240 | 4732 |
| dedicated_25 (L 500) vs dedicated_0 | −680 | **−180** | 5120 |
| dedicated_25 (L 500) vs shared L 0 | −480 | +20 | 5802 |

- The shared model emits each phoneme at the same frame for every L. So its real delay is exactly the nominal L.
- The dedicated L = 500 ms model emits phonemes 680 ms earlier than the dedicated L = 0 model (median). Its phonemes are ready **180 ms earlier**, although it declares 500 ms of lookahead. A CTC model without lookahead learns to emit late (it waits for evidence). A model with lookahead moves its emissions forward. So the declared `latency` is an upper bound on signal use, not the delay that a user sees.
- The IQRs are wide (dedicated_25 vs dedicated_0: ready Δ [−540, 260] ms). Both L = 0 models are weak (PER about 0.7), so the matched phoneme sets are smaller and biased to easy phonemes.
- The last emitted phoneme is 3.12 to 3.68 s (median) before the end of the trial in all conditions. We did not check whether this is silence at the end of the trials or missed final phonemes.

### Compute latency (shared model, 200 random val_eval trials, NumPy streaming decoder + StreamingTrustLayer with the incremental CTC beam and word decoder)
| L (ms) | decoder push per 20 ms bin p50 / p95 (ms) | trust push per frame p50 / p95 (ms) | end of utterance total p50 / p95 / max (ms) | same action as accuracy stage |
|---|---|---|---|---|
| 0 | 0.04 / 2.01 | 0.24 / 0.33 | 79.8 / 148.3 / 280.6 | 200/200 |
| 40 | 0.09 / 1.96 | 0.24 / 0.34 | 99.6 / 188.9 / 262.6 | 200/200 |
| 100 | 0.08 / 2.06 | 0.25 / 0.36 | 107.5 / 201.0 / 281.0 | 200/200 |
| 200 | 0.09 / 2.10 | 0.25 / 0.36 | 103.1 / 180.3 / 274.4 | 200/200 |
| 300 | 0.09 / 2.11 | 0.25 / 0.36 | 99.4 / 193.3 / 256.3 | 200/200 |
| 500 | 0.07 / 1.99 | 0.24 / 0.34 | 99.5 / 173.0 / 272.1 | 200/200 |

- Compute does not grow with L. Per 80 ms frame the work is about 2 ms (decoder) + 0.4 ms (trust layer). That is far below real time.
- At the end of an utterance the decoder does not wait for L: it flushes and masks the missing future bins (as in training). The flush costs 0.4 ms or less. The end cost (about 80 to 108 ms p50) is the word decoder's final pass, not L.
- So L delays the **partial** (live) output by L. It does not delay the **final** decision after the end of the utterance.
- NumPy streaming vs torch batch logits: max abs log-prob difference 1.23e-04 to 1.62e-04 (first 20 trials). Same action as the accuracy stage: 200/200 at every L.
- **The measurement environment was not clean** by the isolation rule: foreign load on the timing cores 5.77 % (limit 5 %), SMT siblings of the timing cores busy 25.23 %. Other agents ran tests at the same time. An earlier run (before the record fix, kept outside the repo) gave the same picture (bin push p95 2.00 to 2.31 ms, end total p50 85.6 to 108.5 ms). The ms-level numbers are good enough for the conclusion above, but are not a clean benchmark.

## Deviations from the plan
1. `latency` was run as `latency-force`. The stage waits for `C:\Users\zhang\bci-data\soak\m6-13\DONE`. The M6-13 soak test is done (HANDOFF, 2026-11-13 23:20) and no soak process runs, but it never wrote that file.
2. Two bugs in `run.py stage_latency` were fixed before the reported run: (a) the header stream used an all-zero log-prob row, which `NeuralTextStream` refuses (rows must log-sum-exp to 0); now a uniform row. (b) `res["measurement_env"]` was read inside the `isolated()` block, but `isolated()` fills the record on exit; so the first run saved an empty record. That run was repeated; its output is kept at `C:\Users\zhang\bci-data\runs\m4-02-latency-run1-norecord.json`.
3. The latency stage was not wrapped in `python -m fidetype.utils.isolation run --class timing`, because the stage takes the timing lock itself and a nested lock would block. The timed block runs pinned to the timing cores with the lock held (`timing_lock_held: true` in `latency.json`).
4. `stage_figure` (right panel) now uses the dedicated L = 0 model as the reference. With the shared model as reference the panel was only the line y = x.

## Limitations
- One participant (T15), one seed, 30 epochs. The decoder is far from the published one (PER 0.0954). Retest the curve with a decoder near that level before using the numbers in a paper.
- Only L = 0 and L = 500 ms have dedicated models. The shared model's curve may understate what dedicated models give at middle L.
- The frozen trust config was not fitted to this decoder, so no commit-side result.
- Emission timing uses the greedy path and exact matches only.
- Compute latency: one machine (Ryzen 7 9800X3D), not clean (see above), no LM rescoring of the word lists.

## Note 2026-11-17 (P14-15): word-decoder settings
The word-decoder settings (lm 1.0, edit penalty 12, bonus 3) were tuned on 400 B2T track `cal` trials; 16 of them are `val_eval` trials ([T15 split audit](../../wiki/questions/t15-split-audit.md), issue D). A re-tune without these 16 trials picks edit penalty 8 (an exact WER tie, decided by truth-in-n-best); without `val_eval` and `val_select` the setting stays the same ([P14-15 results](../2026-11-17-p14-15-retune/results.md)). The word-level numbers on this page are not changed. Gap 44 (P14-18) reruns the M4-12 `val_eval` word decode with edit penalty 8.

## Correction note 2026-11-17 (P14-18): word decode with edit penalty 8
Pre-registered rerun ([P14-18/19 results](../2026-11-17-p14-18-19-followups/results.md)) of all 8 conditions with lm 1.0, **edit penalty 8**, bonus 3 (tuned without the M4 `val_eval` trials). The reference runs with edit 12 reproduced every word-level number on this page. **Effect on 11 of 72 metrics.** WER at the frozen T is 0.019-0.023 lower for shared L 40-500 ms (for example L 40 ms 0.7189 → 0.7003, half-width 0.0156). eWPM is +0.10 for L 100 and 500 ms, and sentence exact / truth in n-best are slightly higher. WER at T = 1 does not move by its half-width. All changes favour edit 8. These rows are superseded by M4-12; the numbers above are not changed.
