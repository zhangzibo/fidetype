# R3 item 3: deployable rule rows and the attribution of 0.059 → 0.0245

Review items: editor M1, M2; stats review M2, M3, m5, m18. Script: [run.py](run.py). Numbers: [results/deployable.json](results/deployable.json), [results/tables.md](results/tables.md).

## What we did
- Recommended rule: fit-A plug-in gate, then clean calibration with the **max rule** λ = max(λ_plug-in, λ_CRC) (CRC; LTT next to it). This is `risk_control_combine = "max"` in the code.
- Rows for B2T ours and published gate (split A = `alternate`, split B = `chrono`), sEMG (3 conditions) and MEG, from the committed clean item tables (MEG: the baselines val-A / val-B split, rebuilt from cached decodes).
- For each row: the calibration bound (n R̂(λ) + 1)/(n + 1), whether the CRC constraint is active, and whether the max rule changes a test decision.
- Attribution on B2T ours: we crossed the full-fit pipeline (812 trials) and the fit-A pipeline (411 trials) — calibration (temperatures, conformal, guard) vs policy-grid configuration.
- CIs: unified bootstrap (seed 20261112, B = 2000) at the condition's unit, conditional on the fitted pipeline and the threshold.

## Results: deployable rule (CRC max-rule), test set

| condition | wrong-commit [CI] | wrong / n (CP95 upper) | commit rate | error among commits | eWPM [CI] | CRC binding? |
|---|---|---|---|---|---|---|
| B2T ours, split A | 0.0245 [0.015, 0.035] | 20/816 (0.035) | 0.100 | 0.244 | 11.48 [10.79, 12.29] | no (bound 0.0075; λ_CRC 0.3075 commits the same items as λ 0.30) |
| B2T ours, split B | 0.0600 [0.049, 0.071] | 49/816 (0.076) | 0.212 | 0.283 | 11.54 [10.84, 12.35] | yes (bound 0.0498; plug-in bound 0.0572 > α); 4 fewer commits, same wrong count |
| B2T published, split A | 0.0478 [0.029, 0.071] | 39/816 (0.062) | 0.491 | 0.097 | 18.79 [17.13, 20.37] | active, but plug-in already certified (0.0498): no test decision changes |
| B2T published, split B | 0.0478 [0.029, 0.071] | 39/816 (0.062) | 0.485 | 0.098 | 18.78 [17.13, 20.36] | as split A (plug-in bound 0.0473) |
| sEMG session-calibrated | 0.0036 [0.000, 0.009] | 2/551 (0.011) | 0.038 | 2/21 | 7.98 [6.95, 9.11] | = plug-in (λ_CRC 0.448 < 0.70) |
| sEMG cross-session | 0.0036 [0.000, 0.009] | 2/551 (0.011) | 0.018 | 2/10 | 4.68 [4.19, 5.25] | = plug-in (λ_CRC 0.204 < 0.30) |
| sEMG cross-subject | 0 | 0/551 (0.0054) | 0 | 0/0 | 4.08 [3.82, 4.37] | = plug-in (never commits) |
| MEG (instance level) | 0 | 0/637 (0.0047) | 0 | 0/0 | 3.20 [3.01, 3.44] | = plug-in (λ 0.5; no guarantee for new sentences) |

LTT max-rule: B2T ours 0.0245 (A) / **0.0515** (B); published 0.0294 / 0.0306 at commit 0.40 / 0.42 and error among commits 0.073 / 0.074; elsewhere = plug-in. Pure CRC (fills the risk budget): sEMG 0.040 / 0.056 (61 % of commits wrong on cross-session), MEG 0.028 (18 of 19 commits wrong).

## Results: attribution (B2T ours, test wrong-commit / commit rate)

| step | split A | split B |
|---|---|---|
| full-fit plug-in (paper trust row) | 0.0588 / 0.232 | 0.0588 / 0.232 |
| full-fit calibration + fit-A policy configuration | **0.0245** / 0.099 | **0.0600** / 0.221 |
| fit-A calibration + full-fit policy configuration | 0.0625 / 0.245 | 0.0588 / 0.233 |
| fit-A plug-in | 0.0245 / 0.100 | 0.0600 / 0.217 |
| fit-A + CRC max-rule (deployable) | 0.0245 / 0.100 | 0.0600 / 0.212 |

- The whole change 0.0588 → 0.0245 comes from the **policy-grid configuration** chosen on fit-A (split A: commit_p 0.3, commit_max_risk 0.1; full fit: commit_p 0.5, commit_max_risk 0.5). The refitted temperatures and conformal sets change nothing (full-fit calibration with the fit-A configuration gives 0.0245 too). **CRC contributes 0.0000** in both splits.
- Split B picks commit_p 0.4, commit_max_risk 0.3 and gives 0.0600. Over 50 repeated splits the fit-A plug-in varies widely (see `repeated-splits`).

## Interpretation
> **Our take:** Write in §7.2: "Refitting the pipeline on fit-A gave 0.0245 (split A) and 0.0600 (split B). The difference to the full-fit 0.0588 comes from the policy-grid choice (guard limit and commit threshold), not from the temperatures and not from CRC. On the clean calibration set CRC was not binding in split A and removed 4 commits (no wrong ones) in split B." For the main table, the deployable rule equals the plug-in in every condition except B2T ours split B, where it is 0.0600 > α. LTT with the max rule is the only row that stays at or below α in both B2T splits (0.0245 / 0.0515 ≈ α).
