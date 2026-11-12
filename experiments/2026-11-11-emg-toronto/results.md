---
title: Forearm sEMG key-press decoder + trust layer on the Toronto sEMG typing dataset (M6-07)
type: experiment
updated: 2026-11-11
---

# Third device type: forearm surface EMG (Toronto sEMG typing)

First test of the NeuralTextStream (NTS) spec and the trust layer on **non-invasive wearable EMG**, after MEG (SpanishBCBL) and intracortical speech (Brain-to-Text '25). Data: Toronto sEMG typing dataset (Achituve et al. 2025, Borealis, **CC BY 4.0**), 19 participants, 2 days each, 16 forearm channels at 2 kHz.

- Code: adapter `src/fidetype/adapters/toronto_semg.py` (own Intan RHD reader, keylog alignment, key-press stream and its CTC form). Tests: `tests/test_adapter_toronto_semg.py` (10). Suite: 249 passed, 4 skipped.
- Scripts: [prep.py](prep.py) (CPU, 46 s), [train.py](train.py) (GPU, 9 runs, 48 min wall), [launch.ps1](launch.ps1) (detached, AC sleep never → restored to 30 min), [trust.py](trust.py) (CPU, about 20 min). Settings: [config.json](config.json). Tables: [results/tables.md](results/tables.md). Numbers: `results/decoder.json`, `results/trust.json`. Log: `results/run.log` (the lines before "full run" are a smoke test with 8 sentences per participant).
- Raw data and cache (outside the repo): `C:\Users\zhang\bci-data\raw\toronto-semg\`, `C:\Users\zhang\bci-data\cache\toronto-semg\v1\` (29,824 windows, 639 MB), runs `C:\Users\zhang\bci-data\runs\emg-toronto\`.
- Source page: [wiki/sources/toronto-semg-typing.md](../../wiki/sources/toronto-semg-typing.md). Wiki result: [emg-toronto-trust-result](../../wiki/questions/emg-toronto-trust-result.md).

## Main finding
The adapter needed **no spec change**. The trust layer works unchanged on EMG. In all three decoder conditions it cuts wrong commits from 0.54–0.96 to ≤ 0.004 **and** raises eWPM over always-commit:

| condition (decoder) | key acc (letters) | always commit LM top-1: eWPM / wrong-commit | trust: eWPM / wrong-commit | CRC (α 0.05) | LTT (α 0.05, δ 0.1) | gaze only |
|---|---|---|---|---|---|---|
| session-calibrated (`calib`) | 0.299 (0.375) | 7.81 / 0.541 | **8.02** / **0.004** | 7.98 / 0.004 | 7.98 / 0.004 | 4.27 |
| cross-session (`xsession`) | 0.168 (0.249) | 4.10 / 0.882 | **4.68** / **0.004** | 4.68 / 0.004 | 4.68 / 0.004 | 4.27 |
| cross-subject (`xsubject`) | 0.209 (0.228) | 3.53 / 0.962 | **4.08** / **0.000** | 4.08 / 0.000 | 4.08 / 0.000 | 4.27 |

- Only the session-calibrated decoder beats gaze typing alone clearly (8.02 vs 4.27; paired CI of trust − gaze [+3.38, +4.16] over sentences, [+2.66, +4.85] over participants).
- Cross-session: trust is 0.41 eWPM above gaze (sentence CI [+0.26, +0.56]; participant CI [−0.04, +0.96]: not significant over people). Cross-subject: trust is **below** gaze (−0.19, CI [−0.28, −0.09]).
- The trust gain comes from **OFFER**, not from COMMIT: the policy commits 0–4 % of sentences. The user picks the right sentence from the offered n-best (truth in n-best 0.64 / 0.21 / 0.08).
- **Important limit: composed sentences.** The data has isolated key presses only. Every number above is for sentences built from single, metronome-paced presses (see "Setting"). Real typing would differ.

## Setting
| item | value |
|---|---|
| Data | 1,968 recordings, 29,824 key presses (10,093 space; 732–799 per letter). The 179 `Used = No` files of `Warnings.csv` are not in `CleanData` |
| Alignment | key time = keylog time − file start time + `Lag` (`LAG_TIMINGS.csv`). Mean rectified EMG peaks +0.08 s after the aligned time |
| Preprocessing | HP 20 Hz, notch 60 Hz, LP 450 Hz (zero phase), decimate to 1 kHz; per-session channel scale (label-free). Window −0.35..+0.35 s; the model sees a 0.5 s crop (random shift ±50 ms in training) |
| Timing | **Oracle key timing** (from the keylogger), one frame per key press. Not a real-time setting. The window uses 0.25 s after the press, so `decoder.causal = false` |
| Model | Our own small 1-D CNN (4 conv layers, 64–128 channels, mean + max pool, 27-way head; about 0.15 M parameters). Class-balanced cross-entropy (so the output acts as a scaled likelihood for LM fusion), AdamW, one-cycle LR, up to 60 epochs, early stop on val loss (patience 15). Linear baseline: logistic regression on log-RMS (16 channels × 10 bins) |
| Splits (no leakage) | `xsession`: train day 1 (T1) of all 19, test day 2 (T2). `calib`: train T1 + one half of the T2 recordings, test the other half, cross-fitted (`calib_a` trains on the first T2 recording of each letter and predicts the later ones; `calib_b` the reverse). `xsubject`: 4 folds of participants, train both days of the others. Val = 10 % of the training **files** (hash) |
| Stream | Canonical: `vocab_type="key"`, 27 tokens `KeyA`…`KeyZ`, `Space` (W3C `KeyboardEvent.code`), `blank_id=null`, one frame per press. For the trust core: CTC form, 28 tokens (`char.b2q-28`), blank mass 1e-3 on key frames, one blank frame between two presses (keeps "ll" apart). No text in `meta` |
| Sentences | Tatoeba English sentences that were **held out** of the char 6-gram LM's training (5,000; 4,135 with 12–50 characters, only `a`–`z` and space, ≥ 2 words). Fit and test texts are disjoint |
| Composition | Per participant: 30 fit sentences from presses of the **first** T2 recording of each letter, 30 test sentences from the **later** recordings (fewer if a letter is missing: 570 fit, 551 test). One real press window per character; frames 0.792 s apart (the median inter-press interval) |
| Decoder for text | CTC prefix beam (vector search, beam 64, 10-best, space rules, bonus 1.0) + English Tatoeba char 6-gram; `lm_weight` picked on fit half A by CER (1.0 / 1.0 / 1.5) |
| Trust fit | Fit sentences shuffled, then split: half A → frame T, sentence T, conformal; half B → policy grid (plug-in, limit 0.05). For CRC / LTT: the last half of B (n = 142) calibrates `commit_p` (`combine="max"`); the grid uses the first half |
| User model | `UserConfig.aac_gaze(chars_per_min = 75.8)` (the data's press rate). Gaze-only baseline: 20 chars/min |
| CIs | 95 %, 1000 resamples over sentences `[...]` and over participants `{...}` |

## Decoder (day-2 key presses, 27 classes)
Chance: majority (space) 0.338, uniform 0.037, letters uniform 0.038.

| run | acc | letters | space | balanced | top-5 | NLL | participants (min–max) |
|---|---|---|---|---|---|---|---|
| `calib` (CNN, cross-fitted) | **0.299** | 0.375 | 0.151 | 0.367 | 0.772 | 2.121 | 0.171–0.454 |
| `xsubject` (CNN, 4 folds) | 0.209 | 0.228 | 0.172 | 0.226 | 0.672 | 2.833 | 0.099–0.386 |
| `xsession` (CNN) | 0.168 | 0.249 | 0.010 | 0.240 | 0.571 | 2.751 | 0.059–0.248 |
| `xsession_linear` (log-RMS + logistic) | 0.162 | 0.177 | 0.132 | 0.175 | 0.525 | 2.944 | 0.092–0.305 |
| control: `xsession_permuted` (labels permuted in training) | 0.022 | 0.034 | 0.000 | 0.032 | 0.137 | 3.313 | 0.008–0.035 |

- The permuted-label control is at chance. Zero input gives one fixed key (`f`, `j` or `k`).
- The dataset's own feature baseline (in the zip): cross-session letter accuracy 0.030–0.267 per participant, cross-participant 0.060–0.248. Our CNN is in the same range (not a like-for-like comparison: different windows, class sets and splits).
- Cross-session space accuracy is only 0.010: the balanced loss gives space a uniform prior, and its EMG differs between days. The LM restores most spaces.

## Trust harness (test 551 composed sentences)
| condition | policy | eWPM [sent] {participant} | wrong-commit | silent error | CER | WER | exact | COMMIT / OFFER |
|---|---|---|---|---|---|---|---|---|
| calib | (a) greedy commit | 3.09 | 1.000 | 0.094 | 0.619 | 0.989 | 0.000 | 1.00 / 0 |
| calib | (b) LM top-1 commit | 7.81 [7.36, 8.30] {6.60, 9.01} | 0.541 | 0.060 | 0.123 | 0.214 | 0.459 | 1.00 / 0 |
| calib | (c) trust | **8.02** [7.63, 8.45] {6.90, 9.15} | **0.004** | 0.000 | 0.123 | 0.214 | 0.459 | 0.04 / 0.96 |
| calib | (c) CRC | 7.98 [7.62, 8.38] | 0.004 | 0.000 | | | | 0.04 / 0.96 |
| calib | (c) LTT | 7.98 [7.62, 8.38] | 0.004 | 0.000 | | | | 0.04 / 0.96 |
| calib | (d) trust, no calibration | 8.15 [7.77, 8.59] | 0.045 | 0.000 | 0.116 | 0.212 | 0.461 | 0.28 / 0.72 |
| xsession | (b) LM top-1 commit | 4.10 [3.89, 4.34] {3.59, 4.70} | 0.882 | 0.149 | 0.398 | 0.579 | 0.118 | 1.00 / 0 |
| xsession | (c) trust = CRC = LTT | **4.68** [4.52, 4.86] {4.21, 5.25} | **0.004** | 0.000 | 0.398 | 0.579 | 0.118 | 0.02 / 0.98 |
| xsession | (d) no calibration | 4.75 | 0.013 | 0.004 | 0.387 | 0.577 | 0.156 | 0.04 / 0.96 |
| xsubject | (b) LM top-1 commit | 3.53 [3.37, 3.72] | 0.962 | 0.167 | 0.479 | 0.681 | 0.038 | 1.00 / 0 |
| xsubject | (c) trust = CRC = LTT | 4.08 [3.98, 4.20] | **0.000** | 0.000 | 0.479 | 0.681 | 0.038 | 0 / 1.00 |
| xsubject | (d) no calibration | 4.76 | 0.005 | 0.000 | 0.369 | 0.562 | 0.116 | 0.01 / 0.99 |
| all | gaze typing only | 4.27 | 0 | 0 | | | | |

Paired trust − always-commit (sentence CI): eWPM calib [+0.05, +0.38], xsession [+0.44, +0.72], xsubject [+0.43, +0.67]; wrong-commit calib [−0.58, −0.49], xsession [−0.91, −0.85], xsubject [−0.98, −0.94]. All CIs over participants agree in sign.

**CRC / LTT.** With n = 142 calibration sentences both are feasible. Thresholds on `p_top1`: xsession CRC 0.204 (bound 0.049), LTT 0.23; calib CRC 0.448, LTT 0.49. The policy grid already chose a stricter `commit_p` (0.3 and 0.7), so `combine="max"` keeps the grid value and the test results equal the plug-in policy (calib: −0.04 eWPM, CI [−0.13, +0.05]). xsubject: no calibration sentence could be committed (the guard blocks them), so CRC returns "never commit" and LTT 0.0; the policy commits nothing either way. Test wrong-commit stays far below α = 0.05 in all cases.

**Calibration.** Frame T 1.25 (calib), 1.78 (xsession), 2.17 (xsubject): the CNN is over-confident across days and people. Sentence ECE before → after: 0.154 → 0.148, 0.328 → 0.072, 0.500 → 0.083. Character ECE after: 0.021–0.022. AUROC "top-1 wrong" from −p_top1: 0.83 / 0.76 / 0.67; guard risk 0.65 / 0.56 / 0.50.

**Frame calibration hurts the beam a little.** `lm_weight` was tuned on raw streams. The policies (b) and (c) decode frame-calibrated (flatter) streams, so the LM gets relatively more weight: CER 0.479 vs 0.369 without calibration (xsubject), 0.398 vs 0.387 (xsession), 0.123 vs 0.116 (calib). Policy (d) is therefore faster, but its wrong-commit rate (0.045 in calib) is close to the limit. Next time: tune `lm_weight` after the frame temperature.

## Null audit (200 random test sentences; commit rate / wrong-commit rate)
| condition | policy | real | other sentence's stream | frame-shuffled | zeros input | label-permuted decoder |
|---|---|---|---|---|---|---|
| calib | always commit | 1.00 / 0.57 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| calib | trust, CRC, LTT | 0.04 / 0.01 | 0.04 / 0.04 | **0.00** | **0.00** | **0.00** |
| xsession | always commit | 1.00 / 0.88 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| xsession | trust, CRC, LTT | 0.03 / 0.01 | 0.03 / 0.03 | 0.00 | 0.00 | 0.00 |
| xsubject | always commit | 1.00 / 0.95 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| xsubject | trust, CRC, LTT | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

- Always-commit writes a wrong sentence on every null input.
- Trust commits nothing on frame-shuffled, zeros and permuted-decoder streams.
- The "other sentence" stream is real EMG of another sentence. The trust policy commits it as often as real input (as on Brain-to-Text '25): the stream alone cannot know what the user intended.

## Spec check
No breaking change and no new field. The canonical stream uses the existing `vocab_type="key"` with `blank_id = null` (spec section 8.2, "wrist-EMG keyboard decoder"). The CTC form is an adapter-level view (`char.b2q-28`). Meta uses only section-4 keys plus `fidetype.*` keys (`fidetype.timing`, `fidetype.composed`, `fidetype.vocab_id`, `fidetype.ctc_form`). Two notes for a later spec version: (1) a convention for **composed / synthetic** streams (here `fidetype.composed`) would help benchmarks; (2) the key-press-per-frame form has irregular frame times in real use, which the spec already allows (`frame_period` absent).

## Limitations
- **Composed sentences from isolated, metronome-paced key presses.** No inter-key context, no natural pace. The eWPM numbers show how the trust layer behaves on real EMG evidence, not real EMG typing speed.
- Oracle key timing; a real device must also detect presses.
- Within a test pool, a press can appear in several sentences (only about 10 presses per letter per pool).
- The `calib` decoder trains on half of the test day; the composed test sentences use the other half (other recordings, same electrode placement). This is "calibrate at the start of a session", not a new session.
- The decoder is small and not tuned (one seed, one architecture).
