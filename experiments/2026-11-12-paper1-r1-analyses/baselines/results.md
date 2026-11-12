# R1 item 2: baselines and selective risk

Review items: domain review M1 (always-offer and plain-threshold baselines), M2 (commit precision); methods review Major 2 (commit rate, error among commits, MEG CRC), Major 6 (CI units). CPU only. Date: 2026-11-11.

All six conditions of the Paper 1 main table. Every policy is refitted on the condition's own fit data and scored on the same test items. The trust rows reproduce the paper exactly (B2T 11.546 / 0.0588 and 18.767 / 0.0441; sEMG 8.024 / 4.677 / 4.080; MEG 3.203 / 0).

## Main numbers (point; CI at the right unit in `results/tables.md`)
EAC = error among commits = P(wrong | commit). WC = wrong-commit = P(commit and wrong).

| condition | always commit: eWPM / WC | never commit (always offer): eWPM | trust: eWPM / WC / commit rate / EAC | trust − never commit eWPM [CI] | CRC (clean cal): WC / commit / EAC | LTT (clean cal): WC / EAC |
|---|---|---|---|---|---|---|
| B2T ours | 11.45 / 0.610 | 11.37 | 11.55 / 0.059 / 0.232 / **0.254** [0.19, 0.32] | +0.18 [+0.12, +0.24] (day) | 0.0245 / 0.100 / 0.244 | 0.0270 / 0.259 |
| B2T published gate | 19.61 / 0.194 | 18.11 | 18.77 / 0.044 / 0.473 / **0.093** [0.06, 0.14] | +0.66 [+0.53, +0.80] (day) | 0.0478 / 0.491 / 0.097 | 0.0294 / 0.073 |
| sEMG session-cal. | 7.81 / 0.541 | 8.01 | 8.02 / 0.004 / 0.038 / 0.095 [0, 0.22] | +0.015 [+0.01, +0.03] (participant) | 0.0399 / 0.241 / 0.165 | 0.0218 / 0.119 |
| sEMG cross-session | 4.10 / 0.882 | 4.67 | 4.68 / 0.004 / 0.018 / 0.200 [0, 0.50] | +0.004 [−0.00, +0.01] | 0.0563 / 0.093 / **0.608** | 0.0309 / 0.567 |
| sEMG cross-subject | 3.53 / 0.962 | 4.08 | 4.08 / 0 / 0 / — | 0 | 0 / 0 / — | 0 / — |
| MEG async | 2.58 / 0.997 | 3.20 | 3.20 / 0 / 0 / — | 0 (identical policy) | 0.0283 / 0.030 / **0.947** | 0.0000 / 0.000 (1 commit) |

Plain thresholds (refit, no guard): calibrated p_top1: B2T ours 11.51 / WC 0.036 / EAC 0.215; published 18.62 / 0.025 / 0.064; sEMG and MEG equal to trust. Raw p_top1: B2T ours never commits (11.39); published 18.68 / 0.033 / 0.078; sEMG calib 8.15 / 0.045 / 0.160; sEMG cross-subject **4.76** (no commits; the raw stream decodes better, see `ablation`); MEG 3.04 / 0.005 / 0.75.

## Answer
1. **"Never commit / always offer" is almost as fast as trust.** The value of the calibrated commit decision over always-offer is +0.18 eWPM (+1.6 %) on B2T ours and +0.66 (+3.6 %) on the published gate (both day-cluster CIs exclude 0), +0.015 on sEMG session-calibrated, and 0 on sEMG cross-session, cross-subject and MEG, where trust *is* always-offer. The price is a wrong-commit rate of 0.059 / 0.044 of all sentences.
2. **Error among commits** under trust: 0.25 (B2T ours), 0.09 (published), 0.10 / 0.20 (sEMG; 21 and 10 commits), undefined on MEG and sEMG cross-subject (no commits). Under CRC on clean calibration data: 0.24, 0.10, 0.17, **0.61** (sEMG cross-session), **0.95** (MEG). Random-split CRC (M2-13 / G1, n_cal 408): 0.25 (B2T ours), 0.10 (published), **0.92** (MEG; 2.1 % commits).
3. **A plain threshold on calibrated p_top1 (no guard) is safer than trust on both B2T decoders** (WC 0.036 vs 0.059; 0.025 vs 0.044; paired day-cluster CIs [−0.036, −0.011] and [−0.034, −0.006]) at −0.03 and −0.15 eWPM. On sEMG and MEG it equals trust.
4. **MEG CI units.** trust − gaze: two-way [−0.11, +0.26], sentences [−0.05, +0.15], participants [−0.08, +0.22]. sEMG primary unit = participant: trust − gaze session-cal. [+2.73, +4.84], cross-session [−0.05, +0.98], cross-subject [−0.45, +0.10].

> **Our take:** the honest headline comparator is always-offer, not always-commit. The trust layer's measurable speed gain over always-offer exists only where the decoder's top-1 is often right (B2T); there it costs about one wrong sentence in four commits (ours) or one in eleven (published). CRC on MEG and sEMG cross-session "spends" its budget on commits that are mostly wrong; the deployable rule is max(λ_tuned, λ_CRC), as the methods review says.

## Notes
- CRC / LTT rows use clean calibration data: B2T fit-A / fit-B `alternate` split (`clean-drift`), so their pipeline is fitted on 411 trials, not 812; sEMG fit-B2 (143); MEG val split by sentence (6 sentences fit everything, 5 sentences / 199 instances calibrate; seed 0).
- "never commit" = the trust grid with `commit_p` 1.01 only, refitted (offer size, abstain rules and fallback are refitted).

## Files
`run.py`, `config.json`; `results/baselines.json` (points, all CIs, paired differences, clean thresholds, random-split selective risk); `results/arrays-*.json` (per-item outcome arrays: correct words, time, wrong commit, commit flag, silent error; no text); `results/tables.md`.
Reproduce (after `clean-drift`): `.venv\Scripts\python.exe -I experiments/2026-11-12-paper1-r1-analyses/baselines/run.py`, then `... -X utf8 experiments/2026-11-12-paper1-r1-analyses/report.py`.
