---
title: M1-C2 RETUNED beam + Spanish char LM on the M1-C r4b CTC streams
type: experiment
updated: 2026-11-08
---

# M1-C2: beam + char LM on the r4b CTC decoder

**Question:** does the re-tuned CTC prefix beam with the Spanish char LM lower the CER of the M1-C r4b decoder (greedy test CER 0.619)? Does the decoder still use the MEG after the LM?

**Answer:** the beam with the RETUNED settings as they are (`lm_weight` 1.25, `insertion_bonus` 1.0) makes the CER worse: test 0.633 (greedy 0.619). With `lm_weight` and `insertion_bonus` tuned on val only, test CER is **0.590** [0.576, 0.604] (paired change vs greedy −0.029 [−0.037, −0.021]). The shuffled-MEG gap stays clearly positive: +0.132 [+0.117, +0.147]. The true sentence is never in the 20-best list.

- Script: [run.py](run.py). Raw numbers: `results/results.json` (all metrics and CIs), `results/grid_val.json` (val grid), `results/per_sentence_cer.json`, log `results/run_log.txt`. Generated table: `results/tables.md`.
- Control log-probs and decode caches live outside the repo: `C:\Users\zhang\bci-data\streams\m1c2-r4b-controls\`.

## Set-up

| Item | Value |
|---|---|
| Decoder | M1-C r4b (`m1c-r4-small-aux0.5-pretrained`, `best.pt`, epoch 38), 3.55 M parameters. See [M1-C](../2026-11-08-m1c-decoder-aux/results.md). |
| Real-MEG streams | The M1-C GPU (bf16) streams, `C:\Users\zhang\bci-data\streams\m1c-r4-small-aux0.5-pretrained\{val,test}`. |
| Control streams | CPU fp32 re-run of `best.pt`. Shuffled = the MEG of another segment of the same split, the same seed-0 derangement as `infer.meg_control`. Zeros = all-zero input. A CPU re-run of real MEG gives the same greedy CER as the GPU streams (val 0.605, test 0.619). |
| Data | The 20 pinned M1-C blocks, 11 subjects. Val 114, test 209 sentences. |
| LM | 6-gram MKN char LM, Spanish Tatoeba (`spa_tatoeba_6gram_mkn.npz`), the same LM as the keystroke decoder ([M2-10](../2026-11-08-m2-real-keystroke/results.md)). It was trained without the SpanishBCBL sentences. |
| Beam | `RETUNED` from `src/fidetype/lm/beam.py` (vector search, beam 256, 20-best, no top-k cut, `prune_logp` −6, space rules), `align=False`. |
| Settings | (1) greedy; (2) beam, no LM (`lm=None`, bonus 0); (3) beam + LM, RETUNED as is (w 1.25, bonus 1.0); (4) beam + LM, val-tuned. |
| Val tuning | Grid on real-MEG val only: `lm_weight` {0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0} × `insertion_bonus` {0, 0.5, 1.0, 1.5, 2.0} × {raw streams, frame-temperature-calibrated streams (T fitted on val)}. Pick: lowest val CER. Chosen: **raw, w 0.25, bonus 1.0** (val CER 0.570). The same setting decodes all test conditions. Test was decoded once. |
| Metric | CER vs the target text, mean over sentences (as in M1-C). 95 % CI: bootstrap over sentences, 10,000 resamples. Gaps are paired over sentences. |
| Compute | CPU only (no GPU), 3 worker processes of 1 thread each. Wall time: 230 s control log-probs + 614 s grid and evaluation, about 14 min in total. Peak RAM of the beam stage: 0.48 GB (all processes). |

## Results

### Test (209 sentences)

| decoder | real MEG [95 % CI] | shuffled MEG | zeros | gap shuffled − real [95 % CI] | WER real | mean over subjects real |
|---|---|---|---|---|---|---|
| greedy | 0.619 [0.607, 0.632] | 0.775 | 1.000 | +0.156 [+0.141, +0.171] | 0.915 | 0.624 |
| beam, no LM | 0.605 [0.592, 0.618] | 0.745 | 0.844 | +0.140 [+0.125, +0.156] | 0.933 | 0.612 |
| beam + LM, RETUNED as is (w 1.25, b 1.0) | 0.633 [0.618, 0.647] | 0.783 | 0.828 | +0.150 [+0.133, +0.167] | 0.853 | 0.634 |
| **beam + LM, val-tuned (w 0.25, b 1.0)** | **0.590** [0.576, 0.604] | 0.723 | 0.765 | **+0.132** [+0.117, +0.147] | 0.938 | 0.597 |

Change vs greedy (real MEG, paired): beam no LM −0.014 [−0.019, −0.010]; RETUNED as is +0.013 [+0.005, +0.022]; val-tuned −0.029 [−0.037, −0.021].

### Val (114 sentences)

| decoder | real MEG [95 % CI] | shuffled MEG | zeros | gap shuffled − real [95 % CI] | WER real | mean over subjects real |
|---|---|---|---|---|---|---|
| greedy | 0.605 [0.587, 0.622] | 0.775 | 1.000 | +0.170 [+0.150, +0.190] | 0.893 | 0.617 |
| beam, no LM | 0.591 [0.573, 0.608] | 0.749 | 0.846 | +0.159 [+0.139, +0.179] | 0.910 | 0.605 |
| beam + LM, RETUNED as is | 0.613 [0.594, 0.631] | 0.780 | 0.839 | +0.168 [+0.145, +0.189] | 0.850 | 0.627 |
| beam + LM, val-tuned | 0.570 [0.550, 0.589] | 0.723 | 0.756 | +0.153 [+0.133, +0.174] | 0.903 | 0.586 |

The val-tuned row is optimistic on val (it was picked there). Pooled CER (edit distance / total characters) is within 0.001 of the mean over sentences in every row (test val-tuned: 0.590).

- True sentence in the 20-best list: 0.000 in every beam row (real MEG, val and test). Sentence accuracy: 0.000.
- Frame temperature fitted on real val: T = 2.579. The CTC decoder is over-confident at its peak frames. Calibrated streams were not better: the best calibrated cell is w 0.25, bonus 0 (val 0.571, raw best 0.570).

### Val grid (real MEG, CER, raw streams)

| w \ bonus | 0.0 | 0.5 | 1.0 | 1.5 | 2.0 |
|---|---|---|---|---|---|
| 0.25 | 0.591 | 0.579 | **0.570** | 0.588 | 0.634 |
| 0.5 | 0.611 | 0.588 | 0.572 | 0.573 | 0.589 |
| 0.75 | 0.637 | 0.603 | 0.578 | 0.573 | 0.578 |
| 1.0 | 0.663 | 0.619 | 0.600 | 0.576 | 0.573 |
| 1.25 | 0.680 | 0.651 | 0.613 | 0.590 | 0.577 |
| 1.5 | 0.701 | 0.666 | 0.630 | 0.604 | 0.585 |
| 2.0 | 0.743 | 0.707 | 0.669 | 0.631 | 0.606 |

The calibrated-stream grid is in `results/tables.md`.

### Example decodes (test, S1, real MEG)

| target | greedy | beam + LM, RETUNED as is | beam + LM, val-tuned |
|---|---|---|---|
| la fuerza atrae el electron primero | la dorrxosrla cioussnto prere | la tocar la cuento pero | la torciar la cius sento priere |
| los ninos mayores acaba la escuela | los riaridess epas aela | los tres de la sala | los iria ries sepas sanielas |
| el algoritmo de los controles recorre el nodo | elos lgamo deloste fis | los gato de los dias | los la modelos te ama finas |

## Interpretation

> **Our take:** The RETUNED weights were tuned on simulator streams with CER near 0.1. On this decoder (CER near 0.6), w 1.25 lets the LM replace the MEG evidence with short, fluent, wrong Spanish ("los tres de la sala"). WER drops (0.915 → 0.853), but CER rises. This is the same pattern as the keystroke decoder, where w 0.5 was best on val ([M2-10](../2026-11-08-m2-real-keystroke/results.md)).

> **Our take:** Most of the gain comes from the search and the insertion bonus, not from the LM. Beam without LM already gives −0.014. A small LM weight (0.25) with bonus 1.0 adds −0.015. The CTC decoder deletes many characters (its outputs are short), and the bonus counters that.

> **Our take:** Test CER 0.590 reaches the M1 number (≈ 0.59). But the M1 target is the v2 async encoder's **greedy** CER. Our greedy CER is still 0.619. So this is "0.59 with beam + LM", not a like-for-like match. The CI [0.576, 0.604] includes 0.59.

> **Our take:** The decoder still uses the MEG after the LM: the gap is +0.132 [+0.117, +0.147]. The gap is a bit smaller than with greedy (+0.156), because the LM gives the same text prior to real and shuffled input. Zeros now give 0.765 instead of 1.000: with the bonus, the beam emits LM text when the decoder emits nothing.

## Limits

- One decoder seed, one LM. Differences below about 0.01 are within noise.
- The best val cell is at the edge of the grid (w 0.25). A smaller weight (or w 0 with a bonus) was not tried. The val surface is flat near the best cell (0.570–0.573 for four cells).
- The LM is open-domain Tatoeba Spanish. The SpanishBCBL sentences are a small, fixed set. An in-domain LM would lower the CER much more, but it would also leak the test sentences. We did not do that.
- Control streams are CPU fp32, real streams GPU bf16. The CPU re-run of real MEG gives the same greedy CER (0.619 test), so the comparison is fair.

## Reproduce

```powershell
$env:HIP_VISIBLE_DEVICES='-1'; $env:CUDA_VISIBLE_DEVICES='-1'
C:\venvs\fidetype-rocm\Scripts\python.exe experiments/2026-11-08-m1c2-beam-lm/run.py                  # all stages, about 14 min CPU
C:\venvs\fidetype-rocm\Scripts\python.exe experiments/2026-11-08-m1c2-beam-lm/run.py --stages eval    # reuse the control log-probs and the val grid
```

The decode caches (`cache_grid.jsonl`, `cache_eval.jsonl` in the data folder) make a re-run skip finished decodes. Delete them to decode again.

## Next steps

1. Seeds for r4b (3 seeds), then the same beam + LM. This tells if 0.590 is stable.
2. Retrain r4a/r4b on the full cache when M1-A ends. Re-tune w and bonus on val for the new decoder.
3. Extend the val grid below w 0.25 and try a length or deletion model, because the bonus does most of the work.
4. Greedy CER is the M1 metric. Improve the decoder itself (data, read-out shift, pooling) to reach greedy 0.59.
