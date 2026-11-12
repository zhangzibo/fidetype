---
title: Trust layer on forearm EMG (Toronto sEMG typing, M6-07)
type: question
tags: [emg, trust, ewpm, adapter, cross-device, conformal, crc, ltt]
sources: [toronto-semg-typing]
updated: 2026-11-11
---

# Does the trust layer work on wearable EMG?

**Short answer: yes, with one large caveat.** On forearm sEMG key presses from 19 people, the trust layer cuts wrong commits from 0.54–0.96 to ≤ 0.004 and raises eWPM over always-commit in all three decoder conditions. The NeuralTextStream spec needed **no change**. The caveat: the [dataset](../sources/toronto-semg-typing.md) has only isolated key presses, so all sentences are **composed** from single presses. Full details: [experiment results](../../experiments/2026-11-11-emg-toronto/results.md).

## Results (test: 551 composed sentences, 19 participants)
| decoder condition | key acc | always commit LM top-1: eWPM / wrong-commit | trust: eWPM / wrong-commit | gaze only |
|---|---|---|---|---|
| session-calibrated (day 1 + half of day 2) | 0.299 | 7.81 / 0.541 | **8.02 / 0.004** | 4.27 |
| cross-session (day 1 only) | 0.168 | 4.10 / 0.882 | **4.68 / 0.004** | 4.27 |
| cross-subject (no user data) | 0.209 | 3.53 / 0.962 | **4.08 / 0.000** | 4.27 |

([experiment](../../experiments/2026-11-11-emg-toronto/results.md), tables "Trust harness")

- Trust − always-commit, eWPM (sentence CI): +0.05..+0.38, +0.44..+0.72, +0.43..+0.67. Wrong-commit: −0.49 to −0.98.
- Only the session-calibrated decoder clearly beats gaze typing (trust − gaze [+3.38, +4.16]). Cross-session is above gaze over sentences but not over participants. Cross-subject is below gaze.
- The policy commits only 0–4 % of sentences. The speed gain comes from OFFER: the user picks from the n-best.
- **CRC and LTT** (M2-13) were feasible with 142 calibration sentences (CRC thresholds 0.20 / 0.45, bound 0.049). The fitted policy was already stricter, so the results equal the plug-in policy. They never made the policy worse by more than 0.04 eWPM.
- **Controls.** Label-permuted decoder: key accuracy 0.022 (chance). Null audit: always-commit writes a wrong sentence on 100 % of frame-shuffled, zeros-input and permuted-decoder streams; trust commits 0 %. The stream of another real sentence is committed as often as real input, as on [Brain-to-Text '25](b2t25-trust-result.md).

> **Our take:** This is the third device type (after [MEG](trust-core-v0-results.md) and [intracortical speech](b2t25-trust-result.md)) where the same trust core, unchanged, removes almost all wrong commits. EMG sits between the two others: like MEG, the decoder alone is weak; like B2T '25, a per-session calibration makes the LM top-1 right for about half of the sentences. The finding that matters for a product: **per-session calibration doubles eWPM** over a decoder trained on another day (8.02 vs 4.68). The trust layer makes the weak conditions safe, but it cannot make them fast.

> **Our take:** The composed-sentence setting is optimistic in one way (each press is a clean, isolated gesture with oracle timing) and pessimistic in another (no inter-key context that a sequence decoder could use). Real typing data with a licence-clean source is the next step: [KT-sEMG](../entities/kt-semg-dataset.md) (CC BY, natural typing, one typist).

## Spec
No breaking change. The canonical stream is `vocab_type="key"` (W3C key codes, `blank_id = null`), one frame per press. The trust core uses a derived CTC character form with blank frames between presses. A future convention for composed / synthetic streams (`fidetype.composed` here) would help benchmarks.

## Open questions
1. Does the gain hold on natural typing? Test on KT-sEMG.
2. How few calibration presses does the session-calibrated decoder need?
3. Tune `lm_weight` after the frame temperature (frame calibration raised CER from 0.369 to 0.479 in the cross-subject condition).

Related: [Toronto sEMG typing (entity)](../entities/toronto-semg-typing-dataset.md) · [Public datasets survey](public-datasets.md) · [M2-13 conformal result](m2-13-conformal-result.md) · [B2T '25 trust result](b2t25-trust-result.md)
