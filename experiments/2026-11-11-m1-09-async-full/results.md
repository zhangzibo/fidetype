# M1-09 results: async decoder on the full cache (2026-11-11)

Queue `C:\Users\zhang\bci-data\runs\queue-2026-11-11-m1-09\` ran from 23:31 on 2026-11-10 to 02:45 on 2026-11-11 ("QUEUE DONE", all exit codes 0, AC sleep restored to 30 min). No suspend gap in any train log. Design: [README.md](README.md). Wiki page: [M1-09 async full result](../../wiki/questions/m1-09-async-full-result.md).

## Summary
- **The async decoder now meets the M1 number.** Medium model, test CER vs target: greedy **0.506** (mean over sentences), **0.495** (mean over the 19 participants); beam + char LM (val-tuned) **0.475** / **0.462**. Brain2Qwerty v2's async encoder on SpanishBCBL: 0.59 ± 0.02.
- **The decoder uses the MEG.** Shuffled MEG 0.760 greedy (gap +0.254 [+0.241, +0.265]), zeros 0.925.
- **The near-variant effect is small.** On the 11 test sentences with no close train variant: greedy 0.519 (participants 0.508), beam + LM 0.492 (0.479).
- **The inference setting is the v2 async setting** (see section 1). The training differs: our aux loss uses the key times as training labels.
- **Async now equals our sync decoder at greedy.** Medium async − M1-15 full-r1 sync, same 637 instances: greedy −0.002 [−0.011, +0.007]; beam + LM +0.028 [+0.016, +0.041].

## 1. Async check (code read, 2026-11-11)
What the model gets at inference (`fidetype.decoders.infer.run_inference`, `ConvCTC.forward`):

| input | given at inference? | source |
|---|---|---|
| MEG segment `x` [306, T] at 100 Hz | yes | `MEGSegments.__getitem__`, `augment=None` at inference |
| segment boundaries: first key press − 0.4 s to last key press + 0.5 s | yes (from the keyboard log) | `preprocess.build_segments` (`seg_pre_s` 0.4, `seg_post_s` 0.5) |
| segment length `T` (so, the sentence duration) | yes | `lengths` argument |
| participant index (per-subject affine layer) | yes | `subjects` argument |
| per-key press times, key count, key labels | **no** | `ConvCTC.forward(x, lengths, subjects)` has no key argument |

- The key times (`key_pos`) and key labels go only to (a) the keystroke-head training loss and (b) `_key_hits`, which reports the head accuracy at the true key times. `_key_hits` reads the model output after the forward pass. It does not change the CTC logits or the stream.
- Self-conditioning uses the model's own intermediate CTC softmax, not labels.
- The beam + LM step reads only the saved streams (log-probabilities) and the Tatoeba char LM.
- Training uses augmentation: start jitter ±0.3 s (kept ≥ 0.1 s before the first key), end extension 0–0.1 s, time stretch 0.9–1.1.

What Brain2Qwerty v2 gives its async encoder ([v2 preprint](../../wiki/sources/brain2qwerty-v2.md)):
- "MEG signals were segmented from 400 ms before sentence onset (first key pressed) through sentence offset (last key released), with the segment duration extended by a uniformly sampled buffer of 400–500 ms" (Methods 4.2, p. 12). Training crops "up to 400 ms from the pre-onset baseline" (p. 12–13).
- The encoder is BrainModule (with a per-subject layer) + Conformer + CTC, "without requiring onset timing of each keystroke" (p. 3).
- SpanishBCBL async CER 0.59 ± 0.02 (Fig. 1E, p. 2; text p. 3); Fig. 1C/F: 19 participants, about 20 h. "CER is computed per sentence, then averaged within each subject, and finally averaged across subjects" (Fig. 1 caption, p. 2).

Comparison:

| item | v2 async (0.59) | M1-09 | same? |
|---|---|---|---|
| segment start | first key − 400 ms | first key − 0.4 s | yes |
| segment end | last key **release** + 400–500 ms | last key **press** + 0.5 s | nearly (≤ about 0.1 s) |
| per-key times at inference | no | no | yes |
| per-subject layer | yes | yes | yes |
| non-causal (offline) Conformer | yes | yes | yes |
| key times in training | no (CTC only, two CTC heads) | **yes**: keystroke aux loss and r4a key pretraining | **no** |
| data | 19 participants, about 20 h | 19 participants, 80 blocks (S1/ses1_block1 missing) | about the same |
| split | own 80/10/10 hash of the sentence text | cache hash split, 101 / 11 / 17 unique sentences | no (different test sentences) |
| metric | CER, per sentence → subject → mean over subjects | CER vs target; we give sentence, subject and participant means | close: compare with our mean over participants |

> **Our take:** the inference inputs match v2's async setting. Both decoders get the segment bounds from the keyboard log, so neither is a free-running decoder (a real-time system also needs sentence onset detection). The one real difference is the training supervision: we use key times as training labels, v2 does not. For a typing-based calibration this is available. The M1 criterion is about the decoding setting, so we count it as met. We state the training difference next to every comparison with v2.

## 2. Training
| run | stop | best epoch | active min | best val |
|---|---|---|---|---|
| r4a-full (small, key pretraining) | trend stop, epoch 50 | 32 | 20.6 | key err 0.523 (key acc 0.47) |
| r4b-full (small) | trend stop, epoch 90 | 74 | 35.9 (cap 120) | CER typed 0.533 |
| r4a-full-medium | trend stop, epoch 51 | 47 | 27.2 | key err 0.502 (key acc 0.49) |
| r4b-full-medium | **epoch cap 100** | 79 | 51.8 (cap 120) | CER typed 0.494 |

The medium r4b stopped at the epoch cap, not by trend. Its smoothed val CER was 0.5027 at epoch 69, 0.4988 at epoch 79 and 0.4985 at epoch 99. The cosine LR was at its floor (6e-6) at the end. So it was close to a plateau, but the stop did not fire. r5 (section 6) tests a longer schedule.

## 3. Test results (CER vs target, 637 instances, 17 unique sentences)
| decoder | input | small: sentences | small: participants | medium: sentences | medium: participants |
|---|---|---|---|---|---|
| greedy | real MEG | 0.553 | 0.546 | **0.506** | **0.495** |
| greedy | shuffled MEG | 0.761 | 0.763 | 0.760 | 0.761 |
| greedy | zeros | 0.922 | 0.922 | 0.925 | 0.924 |
| beam + LM, val-tuned | real MEG | 0.524 | 0.514 | **0.475** | **0.462** |
| beam + LM, val-tuned | shuffled MEG | 0.716 | 0.715 | 0.732 | 0.731 |
| beam + LM, val-tuned | zeros | 0.731 | 0.730 | 0.771 | 0.769 |

- Medium, CIs over instances: greedy 0.506 [0.495, 0.518]; beam + LM 0.475 [0.461, 0.489]. Shuffled − real: +0.254 [+0.241, +0.265] greedy, +0.257 [+0.243, +0.271] beam. Mean over subjects: 0.505 / 0.473.
- Medium − small (paired): greedy −0.047 [−0.054, −0.039]; beam + LM −0.049 [−0.058, −0.039].
- Beam settings chosen on val: medium w 0.25, bonus 0, frame-calibrated (T 3.29); small w 0.25, bonus 0, calibrated (T 2.78). The `RETUNED` preset as is: medium 0.493, small 0.554.
- The true sentence is in the n-best for about 1 % of test instances (medium 0.009). WER stays high: 0.842 greedy, 0.809 beam + LM.
- Keystroke head at the true key times (diagnostic only, not an inference input): medium conformer-head key accuracy 0.513 (chance 0.134).
- Note: the "mean over participants" column in `results/beam-*/tables.md` equals the mean over subjects. `labels.jsonl` had no participant field, so the beam script fell back to the subject. The participant means above come from `analysis/analyse.py`. `infer.py` now writes the participant into `labels.jsonl` (from r5 on).

## 4. Near variants and per participant (`analysis/analyse.py`, CPU)
Same rule as M1-15: a test sentence is "close" if a train sentence is within CER 0.25 (6 sentences, 199 instances); else "far" (11 sentences, 438 instances).

| run | decoder | all | close | far (sentences) | far (participants) | far 95 % CI |
|---|---|---|---|---|---|---|
| small | greedy | 0.553 | 0.549 | 0.555 | 0.548 | [0.544, 0.566] |
| small | beam + LM | 0.524 | 0.509 | 0.531 | 0.520 | [0.517, 0.545] |
| medium | greedy | 0.506 | 0.477 | **0.519** | **0.508** | [0.506, 0.533] |
| medium | beam + LM | 0.475 | 0.438 | **0.492** | **0.479** | [0.475, 0.509] |

- Far-sentence shuffled gap (medium): +0.240 [+0.226, +0.254] greedy, +0.242 [+0.225, +0.259] beam.
- The close − far gap is 0.006 for the small model but 0.042 for the medium model (greedy). So the medium model learns the sentence templates more. The effect on the headline is 0.013 greedy and 0.017 beam CER.

Per participant (medium, test; 19 participants, 16–66 instances each):

| decoder | mean ± SEM | median | range | participants ≤ 0.59 | participants ≤ 0.50 |
|---|---|---|---|---|---|
| greedy | 0.495 ± 0.020 | 0.501 | 0.312–0.621 | 17 of 19 | 9 of 19 |
| beam + LM | 0.462 ± 0.022 | 0.466 | 0.254–0.599 | 18 of 19 | 11 of 19 |

Small model: greedy 0.546 ± 0.017 (range 0.390–0.669; 13 of 19 ≤ 0.59).

## 5. Like for like
**vs M1-C (20 blocks).** All 209 M1-C test instances are in the M1-09 test set (same cache hash split).

| decoder | M1-C (20 blocks) | M1-09 small | M1-09 medium | medium − M1-C (paired) |
|---|---|---|---|---|
| greedy, sentences | 0.619 | 0.546 | 0.494 | −0.125 [−0.142, −0.109] |
| greedy, participants | 0.621 | 0.549 | 0.484 | |
| beam + LM, sentences | 0.590 | 0.515 | 0.461 | −0.130 [−0.150, −0.110] |
| beam + LM, participants | 0.597 | 0.517 | 0.445 | |

On the far sentences of these 209 instances (143): medium − M1-C −0.105 [−0.125, −0.086] greedy, −0.103 [−0.127, −0.080] beam.

**vs M1-15 full-r1 (sync, oracle key times), same 637 instances:** greedy −0.002 [−0.011, +0.007] (no difference); beam + LM +0.028 [+0.016, +0.041] (sync better).

## 6. Caveats
- **Only 17 unique test sentences.** The CIs are over 637 instances. They do not include the variance across sentences, so they are too narrow for a claim about new sentences.
- **Different test split from v2.** Our 0.495 and v2's 0.59 use different test sentences. We cannot say that we beat v2. We can say that we reach the same range or better in the same input setting.
- **Training labels differ** (key times, see section 1).
- **One seed.** No seed variance yet.
- **The val set chose the checkpoint and the beam settings.** Test was decoded once per setting.
- **The no-signal floor is not 1.0.** Text-only decoding with a known length gives about 0.69 ([M1-15 analysis](../2026-11-09-m1-15-sentence-context/results-full-r1-r3.md)). Here the decoder knows only the segment duration; zeros give 0.925 greedy and 0.771 beam + LM.

## 7. r5: longer medium run (launched 2026-11-11 17:36)
- Config `config-r5-medium.json`: medium r4b, init from `m1-09-r4a-full-medium/best.pt`, epochs 200 (cosine over 200), `max_minutes` 180 active, patience 20, EMA trend stop (alpha 0.3, min_delta 0.002).
- Queue `queue-r5.ps1` (copy that runs: `C:\Users\zhang\bci-data\runs\queue-2026-11-11-m1-09-r5\queue.ps1`, PID 28220; training PID 25648): train → `infer --control` → beam + LM (same grid). Hard stop 01:00 on 2026-11-12. AC sleep never until the end; the finally block restores 30 min. The queue does not put the PC to sleep.
- Expected: training ≤ 200 epochs × about 30 s ≈ 100 min (max 180 min), then about 10 min inference and about 40 min beam. Results about 20:15 (latest about 21:45).

## Files
- `results/beam-m1-09-r4b-full/`, `results/beam-m1-09-r4b-full-medium/`: beam tables, val grid, per-sentence CER.
- `analysis/analyse.py` (writes `analysis/analysis.json`, git-ignored like the M1-15 one; rerun the script to rebuild it).
- Greedy metrics: `C:\Users\zhang\bci-data\streams\m1-09-r4b-full*\metrics.json`. Runs: `C:\Users\zhang\bci-data\runs\m1-09-*`.
