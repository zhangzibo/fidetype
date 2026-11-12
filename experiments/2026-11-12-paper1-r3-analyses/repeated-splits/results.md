# R3 item 1 (+ item 8): repeated deployment splits

Review items: stats review M5 (top priority), M1(b, c), M2; editor M5(b, c). Script: [run.py](run.py). Config: [config.json](config.json). Numbers: [results/repeated_splits.json](results/repeated_splits.json) (aggregates, per-day), [results/per_split.json](results/per_split.json) (every split), [results/splits-b2t.json](results/splits-b2t.json) (B2T assignments + temperatures), [results/tables.md](results/tables.md).

## What we did
- **B2T '25 (ours, published gate), R = 50.** For each split, every day's 1,628 main-vocabulary trials were permuted at random and split day-stratified into fit-A (1/4, about 405), clean calibration (1/4, about 405) and test (1/2, about 818). The whole pipeline (frame and sentence temperatures, conformal sets, guard, policy grid) was fitted on fit-A only (the paper's fit-A recipe). Reused calibration = fit-A itself.
- **sEMG (session-calibrated, cross-session, cross-subject), R = 50.** For each split, every participant's fit sentences were permuted and split participant-stratified into fit-A (1/2: temperatures, conformal), fit-B1 (1/4: policy grid) and fit-B2 (1/4: clean calibration). Test = the fixed 551 composed test sentences (separate keystroke pool and test-decoder logits). Reused calibration = fit-B1 (the policy-grid data, same size as fit-B2).
- Rules on each test set: fit-A plug-in, pure CRC, CRC max-rule (λ = max(λ_plug-in, λ_CRC)), LTT pure and max-rule; each on clean and on reused calibration data. α = 0.05, δ = 0.1.
- **Deviation (for compute):** the fitted frame temperature was rounded to 0.02 (B2T; largest change 0.0094, 0.27 %) or 0.01 (sEMG; largest change 0.005) so that decodes could be cached and shared. The snap step for B2T was changed from 0.01 to 0.02 after the temperature stage and before any B2T table was built. Both the fitted and the used values are in `per_split.json`.
- The splits re-use one finite data set per device. The spread over splits is split-to-split variation (fit + calibration + test assignment) for this participant / these participants. It is not a CI for new data.

## Results: test wrong-commit over 50 splits

| condition | rule | mean [p05, p95] | share of splits > α | commit rate | error among commits (pooled) | eWPM |
|---|---|---|---|---|---|---|
| B2T ours | plug-in (fit-A) | 0.0440 [0.021, 0.072] | 0.34 | 0.186 | 0.237 | 11.08 |
| | CRC pure (clean) | **0.0456** [0.026, 0.068] | 0.34 | 0.192 | 0.237 | 11.09 |
| | CRC max-rule (clean) | 0.0368 [0.021, 0.059] | 0.14 | 0.166 | 0.221 | 11.08 |
| | LTT pure (clean) | 0.0344 [0.017, 0.056] | 0.16 | 0.158 | 0.217 | 11.07 |
| | LTT max-rule (clean) | **0.0304** [0.016, 0.052] | **0.08** | 0.147 | 0.207 | 11.07 |
| | CRC pure (reused) | 0.0546 [0.037, 0.085] | 0.58 | 0.213 | 0.256 | 11.10 |
| B2T published | plug-in (fit-A) | 0.0394 [0.021, 0.060] | 0.22 | 0.433 | 0.091 | 18.54 |
| | CRC pure (clean) | **0.0489** [0.029, 0.075] | 0.42 | 0.478 | 0.102 | 18.60 |
| | CRC max-rule (clean) | 0.0357 [0.021, 0.055] | 0.14 | 0.418 | 0.085 | 18.52 |
| | LTT pure (clean) | 0.0342 [0.021, 0.051] | 0.06 | 0.410 | 0.083 | 18.51 |
| | LTT max-rule (clean) | **0.0307** [0.020, 0.047] | **0.02** | 0.392 | 0.078 | 18.49 |
| | CRC pure (reused) | 0.0497 [0.032, 0.073] | 0.48 | 0.482 | 0.103 | 18.61 |
| sEMG session-cal. | plug-in / CRC pure / CRC max / LTT max | 0.0146 / 0.0286 / 0.0125 / 0.0106 | 0.00 / 0.06 / 0.00 / 0.00 | 0.116 / 0.187 / 0.105 / 0.093 | 0.126 / 0.153 / 0.119 / 0.115 | 8.01 / 8.04 / 8.01 / 8.00 |
| sEMG cross-session | plug-in / CRC pure / CRC max / LTT max | 0.0082 / 0.0248 / 0.0068 / 0.0057 | 0.04 / 0.14 / 0.00 / 0.00 | 0.019 / 0.043 / 0.016 / 0.015 | 0.44 / 0.58 / 0.41 / 0.38 | 4.68 |
| sEMG cross-subject | all rules | 0 | 0 | 0 (never commits) | — | 4.07 |

Monte-Carlo SE of the mean over splits: about 0.002 (B2T). The full-fit plug-in of the paper (0.0588) is above the fit-A plug-in mean (0.044); the paper's split A (0.0245) lies near the 5th percentile and split B (0.0600) near the 90th.

## Guarantee verdict
- **CRC (mean target):** the mean clean pure-CRC test rate is 0.0456 (B2T ours) and 0.0489 (published), both ≤ α = 0.05 (SE about 0.002); sEMG 0.029 / 0.025. This is what the CRC guarantee promises (control of the mean over calibration draws). Single splits went above α in 34–42 % of B2T splits: CRC does not bound a single deployment.
- **LTT (high-probability target, ≤ δ = 0.1 of splits above α):** LTT max-rule went above α in 8 % (ours) and 2 % (published) of splits: consistent with δ = 0.1. LTT pure: 16 % (ours; binomial test vs 0.1, p = 0.12) and 6 % (published). The test half is only a proxy for the population risk, so test-sampling noise (SE ≈ 0.008) adds to the share above α.
- **Max rule:** it is never worse than the plug-in, and it lowers the mean (0.044 → 0.037; 0.039 → 0.036).

## Binding (does CRC change the plug-in operating point?)

| condition | CRC constraint active on cal. | CRC stricter than plug-in | max rule changes a test decision | plug-in already certified by the cal. bound | mean cal. bound at plug-in λ [p05, p95] |
|---|---|---|---|---|---|
| B2T ours | 0.98 | 0.56 | 0.54 | 0.50 | 0.049 [0.020, 0.078] |
| B2T published | 1.00 | 0.34 | 0.34 | 0.66 | 0.042 [0.017, 0.068] |
| sEMG session-cal. | 0.98 | 0.26 | 0.22 | 0.84 | 0.032 [0.008, 0.071] |
| sEMG cross-session | 0.66 | 0.40 | 0.06 | 0.94 | 0.017 [0.008, 0.049] |
| sEMG cross-subject | 0.00 | — | 0.00 | 1.00 | 0.0075 |

The paper's split A (CRC not binding) is not typical: on B2T ours the max rule changed the plug-in decisions in about half of the splits.

## Data reuse (paired by split: reused − clean test wrong-commit)

| condition | pure CRC: mean diff [p05, p95]; reused higher | Wilcoxon p | CRC max-rule: mean diff; reused higher / lower | MDE80 of the mean diff |
|---|---|---|---|---|
| B2T ours | **+0.0091** [−0.020, +0.040]; 35 of 49 | 0.003 | +0.0066; 26 / 1 | 0.008 |
| B2T published | +0.0009 [−0.029, +0.029]; 26 of 49 | 0.72 | +0.0035; 15 / 3 | 0.007 |
| sEMG session-cal. | −0.0016; 23 of 46 | 0.71 | +0.0019; 9 / 1 | 0.008 |
| sEMG cross-session | +0.0073; 18 of 31 | 0.036 (sign p 0.47) | +0.0012; 3 / 0 | 0.008 |

- Calibrating on the data that fitted the pipeline raised the mean CRC test rate on B2T ours from 0.0456 to 0.0546 (above α), and the share of splits above α from 0.34 to 0.58. On the published gate and sEMG the effect is small or absent.
- The reuse effect (+0.009 on B2T ours) is small next to the single-split spread: one deployment detects a shift of 0.035 (B2T ours), 0.038 (published) or 0.040–0.057 (sEMG) with 80 % power (one-sided 5 %).

## Item 8: plug-in operating point and per-day results
- B2T ours fit-A plug-in over 50 splits: commit rate 0.186 [0.130, 0.259], wrong-commit 0.044 [0.021, 0.072], plug-in λ 0.54 [0.40, 0.60]. Published: commit 0.433 [0.356, 0.506], wrong-commit 0.039 [0.021, 0.060].
- Per-day test results over the splits (plug-in and CRC max-rule) and the per-day rows of the paper's full-fit trust pipeline are in [results/tables.md](results/tables.md). Full-fit trust − always offer eWPM was positive on 12 of 14 days (ours; day 27 = 0, day 74 = −0.28) and on 14 of 14 days (published); see `unified-ci` for the sign tests.
- The frame temperature fitted on random within-day fit-A sets was 3.51 [3.40, 3.66], lower than the 3.78–3.82 fitted on the first half of each day in the paper's splits.

## Interpretation
> **Our take:** (1) The CRC guarantee holds in the deployment protocol as stated: the mean over repeated splits is ≤ α for both B2T decoders and all sEMG conditions. (2) It does not hold per deployment, and the paper must say this in the abstract: a third or more of single B2T deployments exceed α under CRC or the plug-in. LTT with the max rule is the row that controls the share of bad deployments (8 % / 2 %, ≤ δ = 0.1), at a cost of about 0.01 eWPM. (3) Data reuse has a real but small effect on our own decoder (+0.009, p = 0.003; it moves the mean above α), and none on the published gate or sEMG. So "data reuse can push CRC above α" is supported for one decoder; "the earlier 0.0625 was caused by reuse" is not (the reuse effect is a quarter of one split's spread). (4) Recommended primary safety row: LTT max-rule (clean), with CRC max-rule next to it, reported as mean and 5th–95th percentile over the 50 splits.
