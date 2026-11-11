---
title: Decoder M1 results (first real runs, keystroke decoder and keystroke loss use MEG)
type: question
tags: [decoder, ctc, meg, spanishbcbl, evaluation, controls, rocm]
sources: [brain2qwerty-v2]
updated: 2026-11-10
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
- **Update (2026-11-09, M1-15 r1):** a [sentence-context keystroke decoder](#m1-15-r1-sentence-context-keystroke-decoder-first-real-run-2026-11-09) trained only 9 epochs (the PC slept). Test greedy CER 0.619, beam + LM 0.532 (logistic regression: 0.597 / 0.531). It uses the MEG (gap +0.172). r2 with the full schedule is next.
- **Update (2026-11-10, M1-15 r2):** [trained to the end of the val trend](#m1-15-r2-sentence-context-decoder-trained-to-the-val-plateau-2026-11-10) (43 epochs, 13 min). Test greedy CER **0.577**, beam + LM **0.488**. This is the first decoder below the like-for-like logistic regression (0.597 / 0.531). Gap +0.214 greedy. Sentence context adds only 0.025 CER over the Conv-only head (0.602). The model overfits from about epoch 12–19.

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

## M1-15 r2: sentence-context decoder trained to the val plateau (2026-11-10)
Source: [M1-15 results, r2](../../experiments/2026-11-09-m1-15-sentence-context/results.md#r2-results-2026-11-10).

- Same model and 20 pinned blocks as r1. New: plateau LR schedule, stop on the smoothed val CER trend, sleep prevented (`keep_awake`), `max_minutes` in active time. 43 epochs, 13.0 active min, no suspend gap. `best.pt` = epoch 19.
- Metric: test (209 sentences), CER vs target, mean over sentences. LM weight picked on val.

| decoder (test) | setting | greedy | beam + LM | gap shuffled − real (greedy; beam) |
|---|---|---|---|---|
| M2-10 logistic regression | sync, oracle timing | 0.597 | 0.531 (w 0.5) | ≈ +0.18; — |
| M1-C r4b CTC (+ M1-C2) | async | 0.619 | 0.590 | +0.156; +0.132 |
| M1-15 r1 (9 epochs) | sync, oracle timing | 0.619 | 0.532 (w 1.0) | +0.172; +0.219 |
| M1-15 r2, Conv-only head | sync, oracle timing | 0.602 | 0.503 (w 1.0) | +0.205; +0.259 |
| **M1-15 r2, Conv + Trans** | sync, oracle timing | **0.577** | **0.488** (w 1.25) | **+0.214** [+0.200, +0.228]; **+0.258** [+0.238, +0.278] |

- Mean over participants (test, final head): greedy 0.577, beam + LM 0.493. Controls: shuffled 0.791 / 0.746, zeros 0.841 / 0.750.
- r2 vs r1 (paired, same sentences): greedy −0.042 [−0.051, −0.033], beam + LM −0.044 [−0.059, −0.029]. Every participant improved.
- **Sentence context gain** (Conv only → Conv + Trans, test): greedy −0.025 [−0.031, −0.018], beam + LM −0.015 [−0.027, −0.002]. v1 had 0.67 → 0.36 ([v1](../sources/brain2qwerty-v1.md), Fig. 2).
- **Training curve:** val CE is lowest at epoch 12 (1.991) and rises to 2.498 at epoch 42. Val CER stays flat (0.557–0.573 from epoch 16). Train key accuracy reaches 0.81, val 0.44. The trend stop fired correctly. The 4 LR cuts (every 5 evals after the last gain) did not lower val CER.
- No test sentence is decoded exactly (CER 0 share 0.000).
- Trust harness (M2-14 set-up, CPU) on the r2 streams: trust **3.06** eWPM, always commit 2.49, gaze typing only **3.14** (r1: 2.98 / 2.38 / 3.14). The true sentence is in the 10-best for 1 of 209 test trials. Still no BCI gain. See [results](../../experiments/2026-11-09-m1-15-sentence-context/results.md#trust-layer-check-on-the-r2-streams-ewpm) and [trust core v0 results](trust-core-v0-results.md).

> **Our take:** r2 is a real but small step. With oracle key timing, sentence context plus a char LM brings test CER to 0.488. The Transformer's own share is small (0.015–0.025), because about 200 unique training sentences are too few to learn sentence structure; the model memorises them. The next lever is data (the full cache), not more epochs or schedule tuning. r2 greedy is below 0.59 only in the synchronous setting, so the async M1 target is still open.

## M1-15 r1: sentence-context keystroke decoder, first real run (2026-11-09)
Source: [M1-15 results](../../experiments/2026-11-09-m1-15-sentence-context/results.md).

- **r1 is undertrained.** The PC went into S3 sleep from 20:32:38 to 22:00:03. `max_minutes` (60) counts wall-clock time, so the run stopped after the wake-up. Real compute: about 5 min, 9 of 150 epochs, at peak learning rate. Best val CER typed 0.6003 at epoch 8.
- Metric below: test, mean over sentences, CER vs target (as M1-C and M2-10).

| decoder (test, 209 sentences) | setting | greedy | beam + LM | gap shuffled − real (greedy; beam) |
|---|---|---|---|---|
| M2-10 logistic regression | sync, oracle timing | 0.597 | 0.531 (w 0.5) | ≈ +0.18; — |
| M1-C r4b CTC (+ M1-C2) | async | 0.619 | 0.590 (w 0.25, bonus 1.0) | +0.156; +0.132 |
| **M1-15 r1, 9 epochs** | sync, oracle timing | **0.619** | **0.532** (w 1.0, bonus 1.0) | **+0.172** [+0.158, +0.186]; **+0.219** [+0.200, +0.238] |

- Controls (test): shuffled MEG 0.791 greedy / 0.751 beam + LM; zeros 0.845 / 0.735. Every participant is below its shuffled control.
- Mean over participants (test): greedy 0.623, beam + LM 0.542 (vs target).
- Conv-only head vs Conv + Transformer (val key accuracy, epoch 8): 0.387 vs 0.397. The Transformer adds +0.01 to +0.03 at epochs 5–8. Both are below the M2-10 logistic regression (val 0.419).
- WER above 1 (up to 1.17 for controls) is expected: insertions have no upper limit, and a wrong space makes two wrong words.
- Trust harness (M2-14 set-up, CPU) on the r1 streams: trust 2.98 eWPM, always commit 2.38, gaze typing only 3.14. The true sentence is never in the n-best. See [trust core v0 results](trust-core-v0-results.md).

> **Our take:** r1 does not beat the like-for-like baseline (M2-10) yet: greedy is worse (0.619 vs 0.597), beam + LM is level (0.532 vs 0.531). It is far below v1's Conv + Trans (0.36). But 9 epochs at peak lr say little about the model. The next run (r2) trains the full schedule, with sleep prevented.

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
- [ ] **Sentence-context keystroke decoder** (Transformer over key embeddings, v1 Conv+Trans style). Code ready ([M1-15](#m1-15-code-ready-sentence-context-keystroke-decoder-2026-11-09)). r1 ran 9 epochs only ([r1](#m1-15-r1-sentence-context-keystroke-decoder-first-real-run-2026-11-09): greedy 0.619, beam + LM 0.532). r2 trained to the plateau ([r2](#m1-15-r2-sentence-context-decoder-trained-to-the-val-plateau-2026-11-10): greedy 0.577, beam + LM 0.488). Next: r3 causal (`lookahead_keys: 0`), then the full cache.
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
