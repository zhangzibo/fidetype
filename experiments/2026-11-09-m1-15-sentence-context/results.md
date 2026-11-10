---
title: M1-15 r1 sentence-context keystroke decoder (first real-MEG run)
type: experiment
updated: 2026-11-09
---

# M1-15 r1: sentence-context keystroke decoder

**Question:** does a Transformer over the key embeddings of one sentence lower the CER of the synchronous keystroke decoder (M2-10 logistic regression: greedy 0.597, beam + LM 0.531, test, vs target)?

**Answer (r1): not yet.** r1 is **undertrained**. It trained for only about **5 minutes** (9 of 150 planned epochs). The PC went into sleep during the run, and the wall-clock `max_minutes` limit ended it after the wake-up. In those 9 epochs:

- Test greedy CER vs target is **0.619** (M2-10: 0.597). It is worse than the per-key logistic regression.
- Test beam + LM CER vs target is **0.532** (M2-10: 0.531). It is level.
- The model uses the MEG: shuffled − real gap **+0.172** [+0.158, +0.186] greedy, **+0.219** [+0.200, +0.238] beam + LM (test, CIs exclude 0).
- Val CER was still falling at epoch 8, and the learning rate never started to decay. A full run (r2) is necessary before any conclusion.

Files: `results/metrics.json` (copy of the inference metrics, all splits and conditions), `results/train_curve.json` (per-epoch val metrics), `results/train_log.txt`, `results/infer_log.txt`. Checkpoints and streams stay outside the repo: `C:\Users\zhang\bci-data\runs\m1-15-sentence-context-r1\`, `C:\Users\zhang\bci-data\streams\m1-15-sentence-context-r1\`.

## Set-up
| Item | Value |
|---|---|
| Code | `b56056e` (`src/fidetype/decoders/sentence_context.py`, `train_sentence.py`, `infer_sentence.py`). Config: [config.json](config.json) as is (non-causal, `lookahead_keys: null`). |
| Model | Per-key conv encoder (participant layer, 4 dilated blocks, width 256) → 10 time bins → key embedding (192) → Transformer over keys (4 layers, 4 heads, FFN 512) → 27 classes. Extra per-key conv head (loss weight 0.3). 3.70 M parameters. |
| Setting | Synchronous, oracle key timing (the v1 and M2-10 setting). Not a real-time device setting. |
| Data | 20 pinned blocks, 11 subject IDs, 10 participants (S1/S18 = P01). Train / val / test 947 / 114 / 209 sentences. Same split as M1-C and M2-10. |
| Training | RX 7800 XT, bf16, batch 16, AdamW lr 3e-4, warm-up 300 steps, cosine over 150 epochs, patience 20, `max_minutes` 60. Started 20:27:42, stopped 22:00:06 at epoch 9, step 547. Best val CER typed 0.6003 at epoch 8 (`best.pt`). |
| Inference | `infer_sentence --control --lm spa_tatoeba_6gram_mkn.npz --lm-weights 0.25 0.5 1.0 1.25 2.0`. 22:01–22:05, exit 0. |
| Greedy | argmax per key. |
| Beam + LM | `RETUNED` CTC prefix beam (beam 256, 20-best, `insertion_bonus` 1.0), Spanish Tatoeba 6-gram char LM, raw streams (no frame calibration). `lm_weight` picked on real-MEG val (mean over participants, CER vs target). |
| Controls | Shuffled MEG = the key windows of another sentence of the same split (seed-0 derangement), cycled to the same key count. Zeros = all windows zero. |
| CIs | Paired bootstrap over sentences, 10,000 resamples, of "shuffled CER − real CER". |

### Why the run stopped early
- The system event log shows **S3 sleep from 20:32:38 to 22:00:03** (Kernel-Power 42 / 107, Power-Troubleshooter 1). The queue log also has no line between 20:31:42 and 22:00:04.
- `train_sentence.py` checks `max_minutes` with `time.time()` (wall clock). Sleep time counts. At the wake-up, 92 minutes had passed, so the run stopped at once with status `stopped`.
- Real compute time: about **4.9 min** (epochs of 22–50 s). The queue did not prevent sleep (the AC sleep timeout is 30 min).

## Results

### Metric definitions (read before comparing)
- **CER vs target** = edit distance to the prompted sentence. **CER vs typed** = edit distance to what the participant actually typed (with their typos). M1-C and M1-C2 report vs target. M2-10 reports both.
- Three averages exist: mean over sentences (M1-C, M1-C2, M2-10 and the gap CIs use this), mean over participants (the headline line in `infer.log` and the training val metric), and mean over subject IDs.
- The tables below use **mean over sentences, CER vs target**, unless they say otherwise. This matches the baselines.

### Test (209 sentences), mean over sentences
| decoder | input | CER vs target | CER vs typed | WER vs target |
|---|---|---|---|---|
| greedy | real MEG | **0.619** | 0.614 | 0.983 |
| greedy | shuffled MEG | 0.791 | 0.791 | 1.084 |
| greedy | zeros | 0.845 | 0.845 | 1.000 |
| beam + LM (w 1.0) | real MEG | **0.532** | 0.525 | 0.895 |
| beam + LM (w 1.0) | shuffled MEG | 0.751 | 0.753 | 1.167 |
| beam + LM (w 1.0) | zeros | 0.735 | — | — |

Gap shuffled − real (test, paired, 95 % CI):
- greedy: vs target **+0.172** [+0.158, +0.186]; vs typed +0.177 [+0.163, +0.191].
- beam + LM: vs target **+0.219** [+0.200, +0.238]; vs typed +0.228 [+0.209, +0.247].
- No bootstrap resample is ≤ 0.

### Val (114 sentences), mean over sentences
| decoder | real MEG | shuffled MEG | zeros (mean over participants) | gap shuffled − real [95 % CI] |
|---|---|---|---|---|
| greedy | 0.600 | 0.768 | 0.832 | +0.168 [+0.148, +0.190] |
| beam + LM (w 1.0) | 0.498 | 0.730 | 0.728 | +0.232 [+0.204, +0.260] |

Val is optimistic for beam + LM: the weight was picked there. Val `lm_weight` scores (mean over participants, CER vs target): 0.25 → 0.546, 0.5 → 0.533, **1.0 → 0.524**, 1.25 → 0.529, 2.0 → 0.561.

### Mean over participants (the `infer.log` headline numbers)
| split | greedy real (target / typed) | beam + LM real (target / typed) | greedy shuffled | greedy zeros |
|---|---|---|---|---|
| val | 0.610 / 0.600 | 0.524 / 0.510 | 0.767 | 0.832 |
| test | 0.623 / 0.617 | 0.542 / 0.534 | 0.786 | 0.844 |

### Per participant (test, CER vs target)
| participant | n | greedy real | beam + LM real | greedy shuffled |
|---|---|---|---|---|
| P01 (S1 + S18) | 43 | 0.630 | 0.520 | 0.798 |
| P03 | 15 | 0.657 | 0.541 | 0.786 |
| P05 | 3 | 0.592 | 0.568 | 0.724 |
| P09 | 13 | 0.672 | 0.578 | 0.807 |
| P11 | 26 | 0.673 | 0.599 | 0.776 |
| P12 | 13 | 0.701 | 0.663 | 0.795 |
| P15 | 26 | 0.548 | 0.441 | 0.797 |
| P16 | 13 | 0.559 | 0.441 | 0.810 |
| P19 | 25 | 0.629 | 0.592 | 0.779 |
| P25 | 32 | 0.565 | 0.479 | 0.793 |

Every participant is below its shuffled control. P15, P16 and P25 are best; P12 is worst (as in M2-10, where S12 had the lowest key accuracy).

### Conv-only head vs Conv + Transformer (val key accuracy, during training)
| epoch | final head (Conv + Trans) | per-key conv head (Conv only) |
|---|---|---|
| 5 | 0.366 | 0.339 |
| 6 | 0.382 | 0.352 |
| 7 | 0.400 | 0.372 |
| 8 (best) | 0.397 | 0.387 |

- The Transformer adds +0.01 to +0.03 key accuracy at epochs 5–8. The gap shrinks as training goes on.
- `infer_sentence.py` decodes only the final head. No CER for the conv-only head exists for r1.
- Both heads are below the M2-10 logistic regression (val key accuracy 0.419).

### Comparison with the baselines (test, mean over sentences, CER vs target)
| decoder | setting | greedy | beam + LM | gap shuffled − real |
|---|---|---|---|---|
| M2-10 logistic regression ([results](../2026-11-08-m2-real-keystroke/results.md)) | sync, oracle timing | 0.597 (typed 0.590) | 0.531 (frame-calibrated, w 0.5) | greedy shuffled 0.774 (≈ +0.18) |
| M1-C r4b CTC ([M1-C](../2026-11-08-m1c-decoder-aux/results.md), [M1-C2](../2026-11-08-m1c2-beam-lm/results.md)) | async, no timing | 0.619 | 0.590 [0.576, 0.604] (w 0.25, bonus 1.0) | +0.156 greedy, +0.132 beam |
| **M1-15 r1 (this run, 9 epochs)** | sync, oracle timing | **0.619** (typed 0.614) | **0.532** (w 1.0, bonus 1.0) | **+0.172** greedy, **+0.219** beam |

- The like-for-like baseline is M2-10 (same synchronous setting, same keys). M1-C is an async decoder; it does not use the key times.
- The M2-10 beam used frame-calibrated streams. r1 used raw streams. M2-10 found frame temperature ≈ 1.01, so this changes little.
- The M2-10 shuffled control takes another trial of the same subject. The M1-15 control takes another sentence of the same split. Both are at chance-level CER (0.77–0.79).

### WER above 1.0
WER values above 1 (for example `wer_target` 1.123 for beam + LM on zeros, or val WER 1.12–1.45 in early epochs) are **expected, not a bug**:
- WER = (substitutions + deletions + insertions) / words in the target. Insertions have no upper limit, so WER can pass 1.
- The decoder gets about 1 word in 10 right. A wrong space splits a word into two wrong words: one substitution plus one insertion. 20 % of test greedy sentences have WER > 1, but the hypothesis has 0.99× as many words as the target on average.
- With the LM, the beam outputs 1.16× as many words as the target (test). On zeros and shuffled MEG, the LM writes many short words, so WER is 1.12–1.17.
- Greedy zeros give exactly 1.000: the output is one class for every key (no space), so it is one wrong word plus deletions.

## Training curve
| epoch | val CER typed (mean over participants) | val CER target | val key acc | train loss | lr at epoch end |
|---|---|---|---|---|---|
| 0 | 0.839 | 0.833 | 0.145 | 3.948 | 6.0e-05 |
| 1 | 0.742 | 0.742 | 0.229 | 3.543 | 1.2e-04 |
| 2 | 0.685 | 0.686 | 0.305 | 3.259 | 1.8e-04 |
| 3 | 0.657 | 0.663 | 0.335 | 3.076 | 2.4e-04 |
| 4 | 0.659 | 0.663 | 0.340 | 2.951 | 3.0e-04 |
| 5 | 0.634 | 0.639 | 0.366 | 2.842 | 3.0e-04 |
| 6 | 0.613 | 0.618 | 0.382 | 2.751 | 3.0e-04 |
| 7 | 0.602 | 0.612 | 0.400 | 2.678 | 3.0e-04 |
| 8 | **0.600** | 0.610 | 0.397 | 2.604 | 3.0e-04 |

- **Verdict: undertrained.** Val CER fell 0.034 from epoch 5 to 7 and 0.002 from epoch 7 to 8. Train loss still fell about 0.07 per epoch. The run stopped right after the warm-up (300 steps = epoch 5), at the peak learning rate. The cosine decay over 150 epochs never started.
- No clear sign of overfitting yet. Val CE fell from 2.773 (epoch 0) to 2.047 (epoch 7) and stayed level at epoch 8 (2.050). See `results/train_curve.json`.

> **Our take:** The epoch-8 numbers are a lower bound on what this model can do. The flattening at epoch 8 is at peak lr, so it does not show the plateau. A longer run with the lr decay will very likely lower val CER more. We do not know by how much.

## Recommendation for r2
- **Same config as r1** (non-causal), full schedule: `epochs` 150, `patience_evals` 20, `max_minutes` **120** as a safety cap only. At 22–28 s per epoch (with eval), 150 epochs take about 60–70 min. Early stopping will likely end the run before that.
- **Prevent sleep during the run.** Either the launcher calls `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` for the training process, or the run starts with `powercfg /change standby-timeout-ac 0` and restores 30 after. Better: also count `max_minutes` as active time, not wall clock (the sleep gap in r1 was 87 min).
- Keep the 20 pinned blocks for r2, so that the result compares with M2-10 and M1-C. Use the full cache (now 80 cached blocks) in a later run.
- Then add the conv-only head to `infer_sentence.py` (`--head conv`), so the Conv vs Conv + Trans ablation has a CER, not only key accuracy.
- Naming: the README planned "r2" as the causal run (`lookahead_keys: 0`). The full-length rerun now takes the name r2; the causal run moves to r3.

## Trust-layer check (eWPM)
The M2-14 real-MEG harness ([OFFER_WORDS](../2026-11-08-m2-offer-words/results.md), part b) ran unchanged on the M1-15 r1 streams: `RETUNED` beam, `lm_weight` 0.5, `n_best` 10, frame calibration, fit on val, user `aac_gaze()`. Script: [ewpm_check.py](ewpm_check.py). Output: `results/ewpm/real.json`. CPU only, 250 s.

| policy (test, 209 trials) | eWPM | wrong-commit | silent error | KSR | M2-14 (logistic regression streams) |
|---|---|---|---|---|---|
| always commit LM top-1 | 2.38 | 1.000 | 0.230 | 0.03 | 2.31 |
| trust, no OFFER_WORDS | **2.98** | 0.000 | 0.000 | −0.03 | 2.96 |
| trust + OFFER_WORDS | 2.96 | 0.005 | 0.005 | −0.03 | 2.96 |
| diag: OFFER_WORDS always | 2.89 | 0.000 | 0.000 | 0.10 | 2.86 |
| gaze typing only (no BCI) | **3.14** | 0 | 0 | 0.00 | 3.14 |

- Trust − commit: sentence CI [+0.37, +0.92] eWPM.
- Harness decoder numbers: CER 0.531, system word accuracy 0.123 (M2-14: 0.10), top-1 sentence accuracy 0.000, n-best miss rate 1.000.
- The user-model variants give the same order. Gaze only stays the fastest in every variant (for example fallback 40 cpm: trust 4.83, gaze only 6.29).

> **Our take:** The r1 streams do not change the trust picture. The true sentence is still never in the n-best. So the policy still OFFERs every sentence, and the user still types about as much as without the BCI. The BCI still costs time against gaze typing (2.98 vs 3.14). This check becomes useful only when a decoder gets a real share of sentences right in the n-best.

## Limits
- One seed, 9 epochs. Differences of about 0.01 are within noise.
- Oracle key timing. The decoder knows when each key was pressed. A real device would not.
- The LM weight grid had 5 values. The bonus was fixed at 1.0.

## Reproduce
```powershell
.\experiments\2026-11-09-m1-15-sentence-context\launch.ps1 -Config experiments\2026-11-09-m1-15-sentence-context\config.json -RunName m1-15-sentence-context-r1
C:\venvs\fidetype-rocm\Scripts\python.exe -m fidetype.decoders.infer_sentence --run-dir C:/Users/zhang/bci-data/runs/m1-15-sentence-context-r1 --control --lm C:/Users/zhang/bci-data/lm/spa_tatoeba_6gram_mkn.npz --lm-weights 0.25 0.5 1.0 1.25 2.0
```
