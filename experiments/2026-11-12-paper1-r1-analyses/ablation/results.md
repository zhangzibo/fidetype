# R1 item 3: unified ablation (G5)

Review items: methods review Major 8 (temperature on decoding vs on confidence; guard hurts on B2T); domain review M7 (all ablations on all conditions; sEMG cross-subject without calibration; LM weight re-tuned after calibration). CPU only. Date: 2026-11-11.

Each variant is refitted on the condition's fit data and scored on the same test items. CI at the condition's unit (B2T day, sEMG participant, MEG two-way), B = 2000. Full table with CIs, paired differences, top-1 CER, temperatures and ECE: `results/tables.md`.

## eWPM / wrong-commit per variant (point)
| variant | B2T ours | B2T published | sEMG calib | sEMG xsession | sEMG xsubject | MEG async |
|---|---|---|---|---|---|---|
| trust (full) | 11.55 / 0.059 | 18.77 / 0.044 | 8.02 / 0.004 | 4.68 / 0.004 | 4.08 / 0 | 3.20 / 0 |
| no calibration (no temperature) | 11.57 / 0.071 | 18.73 / 0.043 | 8.15 / **0.045** | 4.75 / 0.013 | **4.76** / 0.005 | 3.04 / 0.005 |
| temperature on confidence only (decode raw) | 11.54 / 0.074 | 18.74 / 0.047 | 8.07 / 0.018 | 4.76 / 0.007 | **4.75** / 0 | 3.04 / 0 |
| temperature on the beam only (no sentence T) | 11.50 / 0.076 | 18.66 / 0.032 | 8.11 / 0.040 | 4.67 / 0.018 | 4.07 / 0.044 | 3.20 / 0 |
| no guard | 11.51 / **0.036** | 18.62 / **0.025** | = trust | = trust | = trust | = trust |
| no conformal sets (offer top-k) | 11.53 / 0.059 | = trust | 8.07 / 0.020 | = trust | = trust | = trust |
| OFFER_WORDS off (BASE_GRID reference) | 11.25 / 0.032 | 18.62 / 0.025 | 7.98 / 0.004 | 4.64 / 0 | 4.08 / 0 | 3.20 / 0 |
| OFFER_WORDS on (BASE_GRID) | 11.32 / 0.054 | 18.59 / 0.026 | 7.99 / 0.015 | 4.64 / 0.005 | 4.08 / 0 | 3.20 / 0 |
| CRC off → on (clean pipelines, `clean-drift`) | 0.0245 → 0.0245 | 0.0478 → 0.0478 | 0.004 → 0.040 | 0.004 → 0.056 | 0 → 0 | 0 → 0.028 (val split, `baselines`) |
| LM weight re-tuned after calibration: trust | — | — | 8.02 / 0.004 (same weight) | 4.73 / 0.013 (w 1.0 → 0.5) | **4.84** / 0.002 (w 1.5 → 0.5) | 3.14 / 0 (M1-09 beam) |
| gaze typing only | 4.08 | 4.08 | 4.27 | 4.27 | 4.27 | 3.15 |

## Answer
1. **The frame temperature changes decoding, not only confidence.** On sEMG cross-subject, decoding the raw stream gives top-1 CER 0.369 vs 0.479 calibrated, and trust eWPM 4.75–4.76 (no calibration or confidence-only) vs 4.08 with the temperature in the beam; paired Δ [+0.38, +1.07]. Both raw variants beat gaze typing (4.27). Re-tuning the LM weight on the calibrated streams fixes it: trust **4.84** [4.25, 5.51], CER 0.360. So "cross-subject stays below gaze" is an artefact of the LM weight tuned on raw streams. The same direction, smaller, on sEMG cross-session (4.73–4.76 vs 4.68) and MEG (raw stream CER 0.483 vs 0.522, but eWPM 3.04 vs 3.20).
2. **The sentence temperature is what keeps wrong commits low.** Without it (`beam_only`), wrong commits rise on 4 of 6 conditions (B2T ours 0.076, sEMG calib 0.040, cross-session 0.018, cross-subject 0.044) and sentence ECE returns to the raw level (0.45 / 0.15 / 0.33 / 0.50). Confidence-only calibration keeps ECE low (0.093, 0.054, 0.162, 0.103, 0.086) with the raw decode.
3. **The guard hurts on both B2T decoders and does nothing elsewhere.** No guard: B2T ours wrong-commit 0.036 vs 0.059 (Δ [−0.036, −0.011]) at Δ eWPM [−0.10, +0.04]; published 0.025 vs 0.044 (Δ [−0.034, −0.006]) at −0.15 eWPM. On sEMG and MEG, removing it changes nothing (the fitted grid already sets commit_max_risk 1).
4. **Conformal sets matter little.** Offering the top-k without the set: −0.02 eWPM (B2T ours), +0.05 eWPM but wrong-commit 0.004 → 0.020 (sEMG calib), no change elsewhere.
5. **OFFER_WORDS helps only B2T ours** (+0.07 eWPM [+0.03, +0.11] vs the same small grid, at +0.022 wrong-commit); on the published gate it costs −0.03 eWPM; on sEMG / MEG no effect.
6. **CRC on top of the plug-in fit** changes nothing on B2T (the plug-in threshold is already at the CRC threshold) and raises wrong commits to near α on sEMG calib / cross-session and MEG for ≤ +0.09 eWPM.

> **Our take:** the layer's safety comes from the sentence-level temperature plus a threshold, not from the guard. The guard should be optional (default off for strong decoders), and the frame temperature should be applied to the confidence, not before the beam, unless the LM weight is re-tuned on the calibrated stream. The Discussion claim "the weak cross-subject decoder stayed at or below gaze typing" must be corrected (4.84 with a re-tuned LM weight).

## Variants
See `policies.py`. `conf_only`: the frame temperature is fitted but not applied before the beam; the sentence temperature and the conformal sets are fitted on the raw decodes (guard confidences from the raw stream). `beam_only`: the frame temperature is applied before the beam; the sentence calibrator stays identity. `no_conformal`: the policy sees all candidates as the "set", so OFFER shows the fitted top `offer_max_k`. OFFER_WORDS on/off both use `BASE_GRID` (224 configs; × 35 OFFER_WORDS configs) so they are comparable. LM re-tune: sEMG LM weight chosen on fit-A CER with the frame-calibrated streams (grid 0.5–3); MEG = the M1-09 validation choice on calibrated streams (lm 0.25, bonus 0).

## Files
`run.py`, `config.json`; `results/ablation-*.json` (points, CIs, paired differences, decoder stats per variant); `results/tables.md`.
Reproduce: `.venv\Scripts\python.exe -I experiments/2026-11-12-paper1-r1-analyses/ablation/run.py --conds emg-calib,emg-xsession,emg-xsubject` (and `meg-async`, `b2t-ours,b2t-published`), then `report.py`.
