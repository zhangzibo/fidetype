---
title: Decoder M1 results (first real runs, no MEG use yet)
type: question
tags: [decoder, ctc, meg, spanishbcbl, evaluation, controls, rocm]
sources: [brain2qwerty-v2]
updated: 2026-11-08
---

# Decoder M1 results: first real runs

**Question asked:** Does our own conv + CTC decoder decode typed text from SpanishBCBL MEG? Does it reach the M1 target?

## Summary
- The pipeline works end to end: cache -> training -> NeuralTextStream files.
- The best test greedy CER is **0.670** (5 subjects, about 2.5 h of MEG).
- With the MEG of another trial, the CER is **0.669**. So the model **does not use the MEG yet**. The CER comes from a Spanish text prior.
- The M1 target (greedy CER near 0.59, the v2 async encoder on SpanishBCBL with all data) is **not met**.
- The main suspect is data volume: about 2.5 h of roughly 20 h. The sanity check (2026-11-08) shows that the cache holds keystroke signal: linear hand decoding reaches 0.83–0.96 (chance 0.60).

Full details: [M1-B decoder results](../../experiments/2026-11-08-m1b-decoder/results.md).

## Setup
| Item | Value |
|---|---|
| Model | Our own conv + CTC decoder (`src/fidetype/decoders/`). No Meta code. |
| Stages | Spatial 306 -> 256; per-subject affine layer; 5 dilated residual blocks (width 320); stride-4 downsample to 25 Hz; aux CTC head with self-conditioning; 4-layer Conformer (d = 256, our own code); final CTC head |
| Parameters | 10.06 M (1 subject), 10.32 M (5 subjects) |
| Loss | 0.3 x CTC(final) + 0.7 x CTC(aux), as in v2 |
| Causal mode | `lookahead_frames` (tested). The runs below are offline. |
| Data | SpanishBCBL cache v1 (tSSS, 0.5–45 Hz, 100 Hz). Split by a hash of the sentence. Practice trials excluded. |
| Decoding | Greedy CTC, best checkpoint by val CER |
| Hardware | RX 7800 XT, ROCm 7.2.1, bf16. 1.74 GB peak, 3.3 s per epoch (5 subjects) |

The design follows the v2 "Encoder Async" ([v2](../sources/brain2qwerty-v2.md)), at about 10 M parameters.

## Results (test, CER against the target text)
| Run | Subjects | Train / val / test segments | Real MEG | Shuffled MEG | Zeros |
|---|---|---|---|---|---|
| `m1-baseline-2026-11-08-1subj` | S25 | 202 / 22 / 32 | 0.707 | 0.711 * | 0.854 * |
| `m1-baseline-2026-11-08-5subj` | S1, S3, S5, S11, S25 | 477 / 56 / 100 | **0.670** (control run: 0.671) | **0.669** | 0.858 |

\* For the S25 run, the control CER is against the typed text (real = 0.709 on that scale).

- 5-subject test WER is 1.043. It is above 1 because the model emits more "words" than the target has.
- The output is mostly high-frequency Spanish letters (a, s, l, e, i, o) and spaces. Example: target "las funciones leen los archivos", output "las as cioieia elas eas".
- On train, real MEG beats shuffled MEG by a wide margin (S25: 0.557 vs 0.677). The model memorises the training trials. It does not generalise to new sentences.

## Key lesson: always report the shuffled-MEG control
**A CER equal to the shuffled-input CER means no neural decoding.** A CER of 0.67 looks like partial decoding. It is not: a text prior gives the same number. From now on, every decoder result reports the real, shuffled and zero-input CER side by side (`infer.py --control`). See [control conditions](../concepts/error-metrics.md#control-conditions).

This is the decoder-side twin of the trust layer's null-input audit ([trust core v0 results](trust-core-v0-results.md#null-input-audit-median-t--10)). The audit checks that the trust policy does not commit fluent text for shuffled or flat input. Here the same idea shows that the decoder itself has not yet learned to use the input.

> **Our take:** This result is a good argument for the trust layer. A plain decoder plus a language model would output fluent Spanish from this model, with no brain signal behind it.

## Likely causes
1. **Data volume.** About 2.5 h of MEG, roughly 0.5 h per subject. v2 shows that CER is log-linear in recording hours, and that the async encoder needs volume: CER 0.59 at about 1 h per subject ([v2](../sources/brain2qwerty-v2.md), Fig. 1D–F; [data scaling](../concepts/data-scaling.md)). We have about half of that per subject, and far fewer subjects.
2. **Model size vs data.** 10 M parameters for 477 segments. With 1 subject, both the default (10.1 M) and a small model (3.3 M, dropout 0.3) overfit in under 40 epochs.
3. **Signal in the cache (ruled out on 2026-11-08).** If the preprocessing or alignment loses the keystroke signal, no model can decode it. The [sanity check](#sanity-check-2026-11-08-signal-present) shows that the signal is present.

> **Our take:** Cause 1 is the most likely. The sanity check passed, so causes 1 and 2 remain.

## Sanity check (2026-11-08): signal present
A linear ridge classifier decodes keystroke-locked epochs (−0.5..+0.5 s, 306 channels, 5-fold CV grouped by trial). Full details: [M1 sanity results](../../experiments/2026-11-08-m1-sanity/results.md).

| Subject | Keys | Hand peak (time) | Hand window −0.2..+0.3 | Letter peak | Letter window | Chance hand / letter |
|---|---|---|---|---|---|---|
| S1 | 4917 | 0.836 (+50 ms) | 0.931 | 0.245 | 0.399 | 0.60 / 0.137 |
| S3 | 2252 | 0.718 (+50 ms) | 0.875 | 0.206 | 0.306 | 0.60 / 0.144 |
| S5 | 1892 | 0.674 (−10 ms) | 0.832 | 0.218 | 0.313 | 0.60 / 0.133 |
| S11 | 4817 | 0.689 (−10 ms) | 0.842 | 0.252 | 0.335 | 0.60 / 0.138 |
| S16 | 2442 | 0.843 (+60 ms) | 0.957 | 0.296 | 0.492 | 0.60 / 0.136 |
| S25 | 8769 | 0.801 (−10 ms) | 0.934 | 0.239 | 0.437 | 0.60 / 0.135 |

- Both controls (shuffled labels; random times at least 0.25 s from any key) are at chance for every subject.
- The peaks fall between −10 and +60 ms. v1's linear hand peak was 74 % at +40 ms ([v1](../sources/brain2qwerty-v1.md)).
- The evoked GFP is 2–4.5× above baseline near the key press. At random times it is flat.
- **Verdict:** the cache and the alignment are correct. Cause 3 above is ruled out. The CTC failure comes from data volume or the model.

## Next steps
- [x] **Sanity check:** keystroke-locked left/right-hand and character decoding with a linear model, v1-style. Signal present ([above](#sanity-check-2026-11-08-signal-present)).
- [ ] **CTC decoder + keystroke auxiliary loss** (running: `experiments/2026-11-08-m1c-decoder-aux/`).
- [ ] **Keystroke-synchronous decoder + trust core on real MEG** (running: `experiments/2026-11-08-m2-real-keystroke/`).
- [ ] **Retrain on the full cache** (all subjects) when preprocessing and the download are complete (`config-real.json`, subjects `null`).
- [ ] **Low-data tuning:** a smaller model, more dropout and time masking, fewer Conformer layers.
- [ ] **Cross-subject pretraining** and a per-subject fine-tune (joint training was best in v2, Table 1).
- [ ] Beam CER with the char LM, after the beam re-tune. Report it with the same controls.

## ROCm / MIOpen notes
- MIOpen searches kernels for each new input shape. Fixes: `MIOPEN_FIND_MODE=FAST` and lengths padded to a multiple of 100 samples.
- CPU contention with preprocessing slows training 10x or more. Use `train.torch_threads = 4`.
- `FIDETYPE_CONV_IMPL=gemm` is a fallback without MIOpen.

Details: [compute setup](compute-setup.md#training-notes-from-the-m1-b-decoder-2026-11-08).

## Related pages
- [M1-B decoder experiment](../../experiments/2026-11-08-m1b-decoder/results.md)
- [Brain2Qwerty v2](../sources/brain2qwerty-v2.md) (data scaling, async encoder)
- [Data scaling](../concepts/data-scaling.md)
- [Error metrics](../concepts/error-metrics.md)
- [Trust core v0 results](trust-core-v0-results.md)
- [Project plan](project-plan.md#m1-baseline-decoder-target-11-09--11-11)
- [Compute setup](compute-setup.md)
