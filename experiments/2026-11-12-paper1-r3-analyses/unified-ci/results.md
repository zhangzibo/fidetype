# R3 item 7: unified CIs and inference checks

Review items: stats review M6 (1–4, 6), M1(c, d), m13; editor number check. Script: [run.py](run.py). Numbers: **[results/ci.json](results/ci.json)** (cite this file), [results/tables.md](results/tables.md); re-runs in `results/rerun/<ablation|user-model|leakage>/results/`.

## What we did
1. **One bootstrap for the whole paper:** seed 20261112, B = 2000, percentile 95 %, at the condition's unit (B2T 14 day clusters; sEMG 19 participant clusters; MEG two-way 17 sentences × 19 participants, plus sentence-only and participant-only). The same seed and unit give the same resampling weights, so one quantity now has one CI in every table. Sources: Tab. 2 from the committed baselines arrays; Tab. 3 from the committed clean item tables; ablation, user model and leakage by re-running the round-1 scripts with the bootstrap patched (cached decodes; the point values reproduce the round-1 values exactly). All CIs are conditional on the fitted pipeline and the threshold (St-m13).
2. **Holm** over the six Tab. 3 one-sided tests; plain and **day-stratified** exchangeable reference for B2T (2,000 permutations within day).
3. **Cluster-level tests:** exact sign test and sign-flip permutation test (exact for 14 days) on per-day (B2T) or per-participant (sEMG) paired differences.
4. **Exact bounds** for zero-event rates (Clopper-Pearson).

## Results
- **Consistency fixed.** B2T ours trust eWPM: [10.83, 12.34] in Tab. 2 and in the ablation (was [10.82, 12.38] vs [10.81, 12.36]). MEG trust − gaze: [−0.10, +0.25] in baselines and user model (was [−0.11, +0.26] vs [−0.11, +0.27]). The user model now uses B = 2000 (was 1000).
- **Key paired CIs (unified):** trust − always offer +0.18 eWPM [+0.12, +0.24] (ours), [+0.53, +0.80] (published); trust − always commit [−0.14, +0.33] (ours), [−1.01, −0.66] (published); no guard − trust wrong-commit [−0.035, −0.011] (ours), [−0.034, −0.007] (published); sEMG trust − gaze [+2.71, +4.91] / [−0.07, +0.97] / [−0.44, +0.09]; MEG trust − gaze two-way [−0.10, +0.25], sentences [−0.04, +0.15], participants [−0.08, +0.22].
- **Holm (Tab. 3):** ours split A p = 0.0120 → **0.072** (day-stratified reference: p = 0.014 → 0.084). All other tests: Holm-adjusted p = 1.0. No Tab. 3 test is significant after correction.
- **Day-level tests (B2T, 14 days):**

| difference | eWPM: days + / − | sign p | sign-flip p | wrong-commit: days + / − | sign p |
|---|---|---|---|---|---|
| ours: trust − always offer | 12 / 1 (1 zero) | 0.003 | 0.004 | 12 / 0 | 0.0005 |
| ours: trust − always commit | 7 / 7 | 1.0 | 0.60 | 0 / 14 | 0.0001 |
| ours: no guard − trust | 6 / 7 | 1.0 | 0.72 | 1 / 9 | 0.021 |
| published: trust − always offer | 14 / 0 | 0.0001 | 0.0001 | 11 / 0 | 0.001 |
| published: trust − always commit | 1 / 13 | 0.002 | 0.0004 | 0 / 14 | 0.0001 |
| published: no guard − trust | 1 / 13 | 0.002 | 0.0004 | 3 / 8 | 0.23 |

  sEMG participants (19): trust − gaze, session-calibrated 18 / 1 (p 0.0001); cross-session 11 / 8 (sign p 0.65; sign-flip p 0.038); cross-subject 8 / 11 (p 0.65).
- **Zero-event bounds (items independent; optimistic under clustering):**

| rate | k / n | one-sided 95 % upper | Clopper-Pearson two-sided 95 % | rule of three |
|---|---|---|---|---|
| B2T controls, trust | 0 / 300 | 0.0099 | [0, 0.0122] | 0.0100 |
| sEMG controls, trust | 0 / 200 | 0.0149 | [0, 0.0183] | 0.0150 |
| MEG controls / test, trust | 0 / 637 | 0.0047 | [0, 0.0058] | 0.0047 |
| sEMG cross-subject test, trust | 0 / 551 | 0.0054 | [0, 0.0067] | 0.0054 |

  Every Tab. 2 wrong-commit count with its exact two-sided interval is in `tables.md` (e.g. sEMG trust 2 / 551 → [0.0004, 0.0130]).

## Interpretation
> **Our take:** Cite `ci.json` for every CI in the paper, state "seed 20261112, B = 2000, percentile, conditional on the fitted pipeline and threshold" once in §6.3, and drop "significantly" for the Tab. 3 split-A result (Holm 0.072). The day-level sign tests confirm the main paired claims without relying on a 14-cluster bootstrap: the layer beats always offer on 12 of 13 non-tied days (ours) and 14 of 14 (published); against always commit it is a tie on our decoder (7 / 7 days) and loses on 13 of 14 days on the published gate. For zero events, report the exact one-sided bound (e.g. 0 / 300 → ≤ 0.010).
