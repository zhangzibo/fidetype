# R3 item 6: sEMG rows without the 295 near-variant test sentences

Review item: editor M6 (and number-check row 21). Script: [run.py](run.py). Numbers: [results/emg_exclusion.json](results/emg_exclusion.json), [results/tables.md](results/tables.md).

## What we did
- 295 of the 551 sEMG test sentences have a near variant in the character-LM training text (round-1 leakage analysis, `build_report.json`).
- We recomputed every main sEMG policy row on the 256 kept sentences, with the original LM (test-set exclusion only; no refit). Policies: always commit, always offer, plain thresholds, trust (plug-in), fit-A plug-in, clean CRC / LTT (pure and max rule), gaze typing. Inputs: the committed per-item arrays and clean item tables.
- 95 % CIs: participant-cluster bootstrap, unified seed 20261112, B = 2000.

## Results (trust eWPM; always-commit wrong-commit)

| condition | trust eWPM, all 551 | trust eWPM, 256 kept [CI] | trust − gaze, 256 kept [CI] | always-commit wrong-commit, all → kept |
|---|---|---|---|---|
| session-calibrated | 8.02 | 6.97 [5.94, 8.09] | [+1.82, +3.92] | 0.541 → 0.664 |
| cross-session | 4.68 | 4.08 [3.77, 4.42] | [−0.37, +0.27] | 0.882 → 0.961 |
| cross-subject | 4.08 | 3.69 [3.50, 3.92] | **[−0.66, −0.23]** | 0.962 → 0.992 |

- Templated (near-variant) sentences are much easier: trust eWPM on the 295 near-variant sentences is 9.31 / 5.40 / 4.52.
- Trust wrong-commit on the kept set: 1 of 256 (session-calibrated; CP95 upper 0.018), 0 of 256 (cross-session, cross-subject; CP95 upper 0.012).
- Pure CRC on the kept set: 0.047 (session-calibrated, 12 of 38 commits wrong) and 0.051 (cross-session, 13 of 14 commits wrong). The max rule equals the plug-in in all three conditions.
- **Changed conclusion:** on the cross-subject decoder, gaze typing is faster than the trust layer on the kept sentences (difference [−0.66, −0.23]); on all 551 it was [−0.45, +0.10]. On cross-session the difference stays around 0.

## Interpretation
> **Our take:** The sEMG speed numbers depend on the templated sentences. The paper should report the 256-sentence exclusion row next to the main sEMG rows (or in Limitation 2 with these numbers), and say that the LM-rebuild result (≤ 0.04 eWPM) and the test-exclusion result (−1.05 / −0.59 / −0.39 eWPM) are two different analyses. The safety result does not change: the trust layer still commits almost nothing on sEMG.
