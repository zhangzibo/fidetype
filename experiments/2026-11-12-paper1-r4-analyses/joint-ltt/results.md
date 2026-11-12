# R4 item 4: joint LTT, a joint rule with a valid guarantee

Reviews: stats M3, editor m11. Tables: [results/tables.md](results/tables.md). Data: [results/joint_ltt.json](results/joint_ltt.json), per split [results/per_split.json](results/per_split.json).

## Procedure (fixed before the run)
For each λ on the grid 0.05, 0.10, ..., 1.00 (20 points; the R3 LTT-sel grid):
- H0(λ): R_marg(λ) > α or R_sel(λ) > β.
- p_marg = P(Bin(n, α) ≤ n R̂(λ)) (0/1 losses, exact). p_sel = P(Bin(n_λ, β) ≤ k_λ), conditional on the n_λ calibration commits (1 if n_λ = 0).
- p(λ) = max(p_marg, p_sel). Reject if p(λ) ≤ δ / 20 (Bonferroni; valid although R_sel is not monotone).
- λ̂ = the smallest rejected λ (+∞ if none). FWER ≤ δ for the union null, so with probability ≥ 1 − δ both risks of λ̂ are within target (i.i.d. calibration items). No max rule (raising λ keeps the marginal bound, not the selective one).
- Sensitivity: grid step 0.01 (100 points, δ/100). α = 0.05, δ = 0.1, β ∈ {0.10, 0.20}.

## Results: repeated splits (test set)

| condition | guard | R | rule | commit | wrong-commit mean | splits > α [CP95] | EAC pooled | committing splits with EAC > β | eWPM |
|---|---|---|---|---|---|---|---|---|---|
| B2T published | on | 200 | **joint LTT β=0.10** | 0.072 (none in 76 %) | 0.0046 | 0 [0, 0.02] | 0.065 | 2 of 48 [0.01, 0.14] | 18.09 |
| B2T published | on | 200 | joint LTT β=0.20 | 0.319 | 0.0195 | 0 [0, 0.02] | 0.061 | 0 of 194 | 18.41 |
| B2T published | on | 200 | LTT max (reference) | 0.394 | 0.0303 | 0.06 | 0.077 | | 18.51 |
| B2T published | off | 200 | **joint LTT β=0.10** | 0.059 (none in 81 %) | 0.0040 | 0 | 0.068 | | 18.08 |
| B2T published | off | 200 | joint LTT β=0.20 | 0.322 | 0.0205 | 0 | 0.064 | | |
| B2T ours | on / off | 200 | joint LTT β=0.10 | 0 (never commits) | 0 | 0 | — | — | 10.99 / 10.98 |
| B2T ours | on / off | 200 | joint LTT β=0.20 | 0.002 | 0.0004 | 0 | 0.22 / 0.24 | | |
| sEMG (all 3) | on / off | 50 | joint LTT β=0.10, 0.20 | 0 | 0 | 0 | — | — | |

- On the published gate, joint LTT β = 0.10 gives the same aggregate numbers as LTT-sel β = 0.10 (the marginal test does not bind at these λ). It commits less than SGR (0.112) and the R3 joint rule (0.111).
- Grid step 0.01 commits less (published β = 0.10: 0.045), because Bonferroni over 100 points is stricter.
- R = 50 rows (the paper's splits) agree: published β = 0.10 commit 0.072, wrong-commit 0.0043, EAC 0.059, 0 of 12 committing splits above β.

## Results: fixed splits

| condition | rule | λ | wrong-commit [CP95] | commit (n) | EAC [CP95] | eWPM |
|---|---|---|---|---|---|---|
| B2T published, split A | joint LTT β=0.10 | +∞ | 0 [0, 0.005] | 0 | — | 18.11 |
| B2T published, split A | joint LTT β=0.20 | 0.80 | 0.0184 [0.010, 0.030] | 0.321 (262) | 0.057 [0.032, 0.093] | 18.54 |
| B2T published, split B | joint LTT β=0.20 | 0.80 | 0.0159 [0.009, 0.027] | 0.319 (260) | 0.050 [0.027, 0.084] | 18.53 |
| B2T ours, A / B | joint LTT β=0.10, 0.20 | +∞ | 0 | 0 | — | 11.42 / 11.41 |
| sEMG, MEG | joint LTT β=0.10, 0.20 | +∞ | 0 | 0 | — | = always offer |

## For the reviser (frozen configuration)
- Joint LTT is the only joint rule here with a valid guarantee for both targets. It is the candidate frozen rule (`config.json`: guard off, joint LTT, α 0.05, β 0.10, δ 0.1, grid 0.05).
- Cost: with β = 0.10 it commits nothing on our decoder, sEMG and MEG, and 6-7 % on the published gate (no commit in 76-81 % of splits; nothing in either fixed split). The frozen rule then equals "always offer" for every condition except, sometimes, the published gate. With β = 0.20 the published gate commits 32 % with EAC 0.06.
- In forward-chaining (item 1), joint LTT β = 0.10 committed nothing with single-day calibration.
- Make LTT-sel (not SGR) the reference selective controller; state SGR's guarantee as given by Geifman & El-Yaniv (2017).
