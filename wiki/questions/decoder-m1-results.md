---
title: Decoder M1 results (first real runs, keystroke decoder and keystroke loss use MEG)
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
- **Update (2026-11-08, M1-C):** a [keystroke auxiliary loss](#ctc-decoder--keystroke-auxiliary-loss-m1-c-2026-11-08) makes the async CTC decoder use the MEG. Shuffled-MEG gap +0.116 to +0.156 CER (CI excludes 0). Best test CER 0.619. The 0.59 target is still not met.
- **Update (2026-11-08, M1-C2):** the [beam + char LM](#m1-c2-beam--char-lm-on-the-r4b-streams-2026-11-08), tuned on val, gives test CER **0.590** [0.576, 0.604] on the r4b streams. Shuffled-MEG gap +0.132 (CI excludes 0). Greedy CER is still 0.619.
- **Update (2026-11-08):** a [synchronous keystroke decoder](#synchronous-keystroke-decoder-2026-11-08) (oracle key timing) does use the MEG: test key accuracy 0.390 (controls 0.10–0.11), greedy CER 0.59 (controls 0.77).

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

## Synchronous keystroke decoder (2026-11-08)
Source: [M2-10 results](../../experiments/2026-11-08-m2-real-keystroke/results.md). Code: `src/fidetype/decoders/keystroke.py`.

- **Setting:** synchronous, with oracle key timing from the keyboard log (the v1 setting). One window per key press: −0.2..+0.3 s, 10 bins, 306 channels.
- **Model:** per-subject multinomial logistic regression. It beat a shared MLP on val (key accuracy 0.419 vs 0.336).
- **Data:** 20 cached blocks, 11 subjects. Train 947 trials / 38 204 keys; test 209 trials / 17 unique sentences.

| input (test) | key acc | greedy CER vs typed | greedy CER vs target |
|---|---|---|---|
| real MEG | **0.390** | **0.590** | 0.597 |
| control: shuffled MEG | 0.111 | 0.774 | 0.774 |
| control: labels permuted at train time | 0.099 | 0.767 | 0.768 |

- Chance (majority class) is 0.13. Both controls are at chance. **This is the first real neural decoding in the project.**
- With the `RETUNED` LM beam (`lm_weight = 0.5`): test CER 0.531, WER 1.023. The true sentence is never in the n-best.
- Greedy CER 0.59 meets the M1 number (≈0.59). **But it does so in the synchronous oracle-timing setting, not in the async setting** of the v2 target. The CTC decoder above is still the async path.

## CTC decoder + keystroke auxiliary loss (M1-C, 2026-11-08)
Source: [M1-C results](../../experiments/2026-11-08-m1c-decoder-aux/results.md). Code: `src/fidetype/decoders/` (`conv_ctc.py`, `dataset.py`, `train.py`, `infer.py`).

**Question:** if we add a direct per-keystroke loss, does the async CTC decoder use the MEG?

**Answer: yes.** With the keystroke loss, real MEG gives a test CER 0.116 to 0.156 lower than shuffled MEG. The 95 % CI excludes zero. Without the loss, on the same data and model, the gap is zero.

### Method
- A key press at sample `s` (100 Hz) maps to encoder frame `s // 4` (40 ms frames).
- A linear head (27 classes: a–z and space) reads the frame features. The read-out is shifted 1 frame (40 ms) after the key and mean-pooled over 3 frames.
- Two heads (`aux_key_layer = "both"`): one on the conv-stack frames, one on the Conformer output.
- Total loss: `ctc_weight × (0.3 CTC_final + 0.7 CTC_aux) + aux_keystroke_weight × CE_keys`.
- The keystroke heads are not used for decoding. They do not change the CTC logits (tested).
- r4: r4a trains on the keystroke loss only. r4b starts from r4a and trains with CTC + 0.5 × keystroke loss.
- The gap CI is a paired bootstrap over sentences (10,000 resamples) of "shuffled CER − real CER".

**Data:** 20 pinned blocks, 11 subjects (S1, S3, S5, S9, S11, S12, S15, S16, S18, S19, S25). Segments train / val / test 947 / 114 / 209. This is about twice the M1-B 5-subject data.

### Results (test, CER against the target, greedy CTC)
| Run | Params | Keystroke loss | Real MEG | Shuffled MEG | Zeros | Gap [95 % CI] | Key acc real / shuffled (conv, Conformer) |
|---|---|---|---|---|---|---|---|
| r0 baseline (M1-B config) | 10.65 M | no | 0.670 | 0.669 | 0.851 | −0.001 [−0.006, +0.004] | – |
| r1 small | 3.54 M | no | 0.684 | 0.681 | 0.833 | −0.002 [−0.008, +0.003] | – |
| r2 small, weight 0.5 | 3.55 M | yes | 0.628 | 0.744 | 0.906 | **+0.116** [+0.103, +0.130] | 0.378/0.099, 0.415/0.107 |
| r3 small, weight 1.0 | 3.55 M | yes | 0.639 | 0.754 | 0.880 | **+0.116** [+0.102, +0.129] | 0.389/0.092, 0.418/0.107 |
| r4b small, weight 0.5, keystroke-pretrained | 3.55 M | yes | **0.619** | 0.776 | 1.000 | **+0.156** [+0.141, +0.172] | 0.377/0.097, 0.411/0.107 |

- Mean over subjects (test CER): r0 0.669, r1 0.682, r2 0.635, r3 0.648, r4b 0.624.
- The majority-class key accuracy is 0.132 (test).
- **The M1 target (greedy CER near 0.59) is still not met.** The best test CER is 0.619.
- Example (r4b, S15): target "el cuaderno presenta las divisiones enteras", output "el cuaer preta las daicioos eitrs". M1-B gave outputs like "las ... as".
- Each run is one seed. Differences of about 0.01 are within noise.

> **Our take:** The keystroke loss causes the MEG use. r1 and r2 have the same model, data, augmentation and optimiser. Only the loss differs. Twice the data alone (r0, r1) does not help.

> **Our take:** The CER gain is smaller than the gap. Shuffled-MEG CER goes up (0.68 → 0.74–0.78), because the model now depends on the MEG. Real-MEG CER goes down only 0.04–0.06 (0.670 → 0.619). In r4b, zeros give CER 1.000: the model emits nothing without MEG.

> **Our take:** The keystroke heads read 38–44 % of keys from real MEG. This is close to the [sanity check](#sanity-check-2026-11-08-signal-present) letter window (0.31–0.49) and the [synchronous keystroke decoder](#synchronous-keystroke-decoder-2026-11-08) (0.390).

### M1-C2: beam + char LM on the r4b streams (2026-11-08)
Source: [M1-C2 results](../../experiments/2026-11-08-m1c2-beam-lm/results.md).

- **Setting:** `RETUNED` beam (beam 256, 20-best, no top-k cut) + Spanish Tatoeba 6-gram char LM, on the r4b streams. `lm_weight` and `insertion_bonus` tuned on real-MEG val only. Test decoded once.
- **Controls:** shuffled MEG and zeros, CPU re-run of the r4b checkpoint (same derangement as M1-C).

| decoder (test, 209 sentences) | real MEG [95 % CI] | shuffled MEG | zeros | gap shuffled − real [95 % CI] |
|---|---|---|---|---|
| greedy | 0.619 [0.607, 0.632] | 0.775 | 1.000 | +0.156 [+0.141, +0.171] |
| beam, no LM | 0.605 [0.592, 0.618] | 0.745 | 0.844 | +0.140 [+0.125, +0.156] |
| beam + LM, RETUNED as is (w 1.25, bonus 1.0) | 0.633 [0.618, 0.647] | 0.783 | 0.828 | +0.150 [+0.133, +0.167] |
| **beam + LM, val-tuned (w 0.25, bonus 1.0)** | **0.590** [0.576, 0.604] | 0.723 | 0.765 | **+0.132** [+0.117, +0.147] |

- Val CER (same rows): 0.605, 0.591, 0.613, 0.570.
- Val-tuned beam vs greedy (test, paired): −0.029 [−0.037, −0.021]. The true sentence is never in the 20-best.
- The RETUNED weight 1.25 makes CER worse (+0.013): the LM writes short, fluent, wrong Spanish.

> **Our take:** Test CER 0.590 with beam + LM reaches the M1 number (≈ 0.59), and the decoder still uses the MEG (gap CI excludes 0). But the v2 target is a greedy CER. Our greedy CER is still 0.619. Report this as "0.59 with beam + LM", not as the M1 target met.

**Process-exit hang fixed.** On ROCm/Windows, a process that ran MIOpen convolutions does not end after `sys.exit`. It spins one CPU core. `train.hard_exit()` calls `TerminateProcess`. See [compute setup](compute-setup.md).

**Resolved (2026-11-08):** S1 and S18 are one person (P01), as the dataset card says. The 11 subject IDs are 10 participants. No train/test leakage (splits are by sentence). Test mean CER over participants differs from the mean over subject IDs by at most 0.003 (r4b 0.621). See [SpanishBCBL repeated participants](spanishbcbl-repeated-participants.md).

## M1-15 code ready: sentence-context keystroke decoder (2026-11-09)
Code: `src/fidetype/decoders/sentence_context.py` (+ `train_sentence.py`, `infer_sentence.py`). Plan: [M1-15 experiment](../../experiments/2026-11-09-m1-15-sentence-context/README.md). **Not trained on real MEG yet.**

- Same setting as the synchronous decoder: oracle key timing, one −0.2..+0.3 s window per key.
- Per-key conv encoder (participant layer) → key embedding → Transformer over the keys of one sentence → 27 classes. This is the v1 Conv + Trans idea ([v1](../sources/brain2qwerty-v1.md), Fig. 2: CER 0.67 → 0.36), in our own code.
- Non-causal (v1) or causal mode (`lookahead_keys = 0`: the output at key i uses keys 0..i only).
- Output: the same CTC-form keystroke streams as above, so the beam + char LM and the trust core read them unchanged.
- Controls: shuffled-sentence MEG and zeros. Metrics: greedy and beam + LM CER, per-participant means.

## Next steps
- [x] **Sanity check:** keystroke-locked left/right-hand and character decoding with a linear model, v1-style. Signal present ([above](#sanity-check-2026-11-08-signal-present)).
- [x] **CTC decoder + keystroke auxiliary loss** ([above](#ctc-decoder--keystroke-auxiliary-loss-m1-c-2026-11-08)): the decoder now uses the MEG; best test CER 0.619.
- [ ] **M1-C follow-ups:** 3 seeds for r1, r2 and r4b; ~~the `RETUNED` beam + char LM on the r4b streams~~ (done, M1-C2: test CER 0.590); re-run r4a/r4b on the full cache; try other read-out shifts and pooling.
- [x] **Keystroke-synchronous decoder + trust core on real MEG** ([above](#synchronous-keystroke-decoder-2026-11-08)).
- [ ] **Sentence-context keystroke decoder** (Transformer over key embeddings, v1 Conv+Trans style). Code ready ([M1-15](#m1-15-code-ready-sentence-context-keystroke-decoder-2026-11-09)); GPU run pending.
- [ ] **Retrain on the full cache** (all subjects) when preprocessing and the download are complete (`config-real.json`, subjects `null`).
- [x] **Low-data tuning:** a smaller model, more dropout and time masking, fewer Conformer layers. *(M1-C r1: 3.54 M params; alone it does not help, test CER 0.684, gap −0.002)*
- [ ] **Cross-subject pretraining** and a per-subject fine-tune (joint training was best in v2, Table 1).
- [x] Beam CER with the char LM, after the beam re-tune, for the CTC decoder. Report it with the same controls. (Keystroke decoder: 0.531. CTC r4b: 0.590, gap +0.132; [M1-C2](#m1-c2-beam--char-lm-on-the-r4b-streams-2026-11-08).)

## ROCm / MIOpen notes
- MIOpen searches kernels for each new input shape. Fixes: `MIOPEN_FIND_MODE=FAST` and lengths padded to a multiple of 100 samples.
- CPU contention with preprocessing slows training 10x or more. Use `train.torch_threads = 4`.
- `FIDETYPE_CONV_IMPL=gemm` is a fallback without MIOpen.

Details: [compute setup](compute-setup.md#training-notes-from-the-m1-b-decoder-2026-11-08).

## Related pages
- [M1-B decoder experiment](../../experiments/2026-11-08-m1b-decoder/results.md)
- [M1-C keystroke auxiliary loss experiment](../../experiments/2026-11-08-m1c-decoder-aux/results.md)
- [M1-C2 beam + char LM experiment](../../experiments/2026-11-08-m1c2-beam-lm/results.md)
- [CTC](../concepts/ctc.md)
- [Brain2Qwerty v2](../sources/brain2qwerty-v2.md) (data scaling, async encoder)
- [Data scaling](../concepts/data-scaling.md)
- [Error metrics](../concepts/error-metrics.md)
- [Trust core v0 results](trust-core-v0-results.md)
- [Project plan](project-plan.md#m1-baseline-decoder-target-11-09--11-11)
- [Compute setup](compute-setup.md)
