# Paper 1, round 4: statistics and reproducibility review

Reviewer: independent (statistics, conformal / risk-control methods, computational reproducibility).
Manuscript: `papers/paper1/draft-v3.pdf` (LaTeX `papers/paper1/latex/`, commit `65359dc`).
Date: 2026-11-12. CPU only. I wrote this assessment before I read any earlier review or response file.

## 1. Summary

The paper puts a stream-only commit rule on top of three neural text-entry decoders. It sets the commit threshold with LTT and a max rule, and it reports the wrong-commit rate, the commit rate and the error among commits (EAC). It repeats the fit / calibration / test assignment 50 times on Brain-to-Text '25 (B2T) and sEMG. It also tests selective controllers (SGR, LTT-sel, joint), a reuse condition, and online controllers.

The statistical core is mostly correct and very reproducible. I re-derived every guarantee. I re-implemented CRC and LTT from scratch and reproduced all 400 thresholds and test rates of the 100 B2T repeated splits exactly. Three committed analyses re-ran to byte-identical outputs. 34 of the 36 numbers I traced match.

The main problems are about interpretation, not arithmetic:

- The "repeated deployments" are random permutations within days. They are exchangeable by construction. They check the theorems on one pool of data. They do not test a deployment, where calibration precedes use in time.
- The paper says that "a user lives in one deployment". But the per-day risk under the primary rule is not controlled. For the published gate, day 34 has a pooled wrong-commit rate of 0.102 under the LTT max rule (my computation, Section 5.4).
- The joint rule `max(λ_SGR, λ_CRC max)` does not inherit the SGR guarantee, because the selective risk is not monotone in λ. The Discussion recommends this rule, and the frozen configuration uses an untested variant of it.
- The primary rule was chosen after the 50 splits were seen. The abstract then reports that rule's numbers from the same splits.

## 2. Recommendation

**Major revision.** Most fixes are wording. One cheap CPU analysis (forward-in-time calibration across days, plus per-day rates) is needed to support the word "deployment", or the claim must be narrowed. The numbers are trustworthy. The framing of contribution 2 and the selective / joint recommendation are not yet.

## 3. Check of the stated guarantees (Task 1)

| Statement (location) | Verdict | Note |
|---|---|---|
| CRC: λ̂ = inf{λ : n/(n+1) R̂ + 1/(n+1) ≤ α}; E[L_{n+1}] ≤ α under exchangeability (§5.3) | Correct | B = 1. Code takes the minimum over calibration scores and +∞. This choice is ≥ the continuum infimum, so it is valid and conservative. (Example: split A, λ_CRC = 0.3075 is the lowest eligible calibration score; LTT at λ = 0.00 commits 2 more test items.) |
| CRC never commits for n < 19 (§5.3) | Correct | 1/(n+1) > 0.05 for n ≤ 18. |
| LTT fixed sequence 1.00 → 0.00, p = P(Bin(n, α) ≤ n R̂), Pr(R(λ̂) ≤ α) ≥ 1 − δ (§5.3, Alg. 2) | Correct | The binomial p-value is super-uniform for H0: R ≥ α with 0/1 losses. Fixed-sequence testing needs a pre-set order, not monotonicity. Code matches Alg. 2. |
| LTT cannot commit below n = 45 | Correct | 0.95^44 = 0.105 > 0.1; 0.95^45 = 0.099. |
| Max rule keeps both guarantees, also if λ_tuned depends on calibration data (§5.3) | Correct | L is pointwise non-increasing in λ. For LTT, R(λ') ≤ R(λ̂) for all λ' ≥ λ̂. |
| "Left-continuous loss … subset of {s > λ'} for λ' < λ" (§5.3, last paragraph) | Conclusion right, argument unclear | The valid argument: λ̂ and the (n+1)-point oracle threshold are both minima over a finite set of scores, so the oracle condition is attained. No right-continuity is needed. Rewrite the sentence (minor m3). |
| SGR at level δ/⌈log₂ m⌉ (§5.4, Alg. 2) | Stated as in Geifman & El-Yaniv | The union bound runs over thresholds that the bisection chooses from the data. The binomial bound conditions on a random number of accepted items. The guarantee holds only as far as the original lemma holds. LTT-sel (fixed grid, Bonferroni) gives a clean FWER guarantee. See major issue M3. |
| LTT-sel: P(Bin(n_λ, β) ≤ k_λ) ≤ δ/20 over grid 0.05…1.00 | Correct | Under i.i.d. data and a fixed λ, the errors among commits given n_λ are binomial. Bonferroni is valid for a non-monotone risk. Code matches. |
| Joint = max(λ_SGR, λ_CRC max) "targets both" (§5.4, §7.3, Discussion) | **Not valid as a joint guarantee** | The marginal bound carries over (monotone loss). The selective bound does not: Pr(wrong ∣ s ≥ λ) can rise when λ rises. See M3. |
| aci: (1/T)ΣL_t ≤ α + (λ_{T+1} − λ_1)/(ηT); a-priori form with delay d (Tab. 11, App. P) | Correct | max(0,·) clipping only raises λ, so the inequality direction holds. λ can grow only after a commit, which needs s ≥ λ_t with s ≤ 1. That gives the 1 + η(1 + d) term. Code: `lam_max = inf` by default, so the upper clip does not run. |
| aci_window: bound with (α_1 − α_{T+1})/(γT) | Correct | The min(2α, ·) clip only lowers α_t. |
| Clopper–Pearson "one-sided 95 % upper bounds" for zero rates (Tab. 1 caption, §7.2, §7.7) | **One value is mislabelled** | 0.0045 for 816 items is the two-sided 97.5 % bound. The one-sided 95 % bound is 0.0037. The 637 / 551 / 300 / 200 values are one-sided and correct. See m1. |
| Holm over six tests | Correct | 6 × 0.0120 = 0.072. Valid under any dependence. |
| Permutation p = (k+1)/(B+1) against the exchangeable reference | Correct | The observed split is one draw from the same split distribution under H0. The day-stratified variant is the right reference for B2T. |
| Percentile cluster bootstrap, 14 days | Stated with caveats | Fine as stated. The paper adds day-level sign tests, which is good. |

Algorithms 1–2 against the code (`risk_control.py`, `online_risk.py`, `common3.py`, `policy.py`, `guard.py`): CRC, LTT, SGR, LTT-sel, the guard formula (max of low-evidence share and 1 − consistency over the top 5, clipped to [0, 1]) and the policy order all match. Small gaps:

- Alg. 1 omits two code conditions: the offer needs `not includes_other`, and the commit has an optional `commit_max_set` (None by default).
- Alg. 1 says "low ← 1 if y₁ empty". The code returns ABSTAIN before the guard if there is no candidate.
- The code accepts SGR at `b < β` (strict). The paper says ≤ β.

## 4. Number tracing (Task 2)

I traced 36 numbers. 34 match the committed files exactly (to the rounding shown). File abbreviations: RS = `repeated-splits/results/tables.md` and `per_split.json`; UCI = `unified-ci/results/tables.md` and `ci.json`; V3 = `v3-derived/results/tables.md`; DR = `deployable-rule/results/tables.md`; SR = `selective-risk/results/tables.md`; UM = `unified-ci/results/rerun/user-model/results/tables.md`.

| # | Location | Manuscript | File value | OK |
|---|---|---|---|---|
| 1 | Abstract | always commit 61 % / 19 % | 0.6103 / 0.1936 (UCI) | yes |
| 2 | Abstract, Tab. 2 | LTT max mean 3.0 % / 3.1 % | 0.0304 / 0.0307 (RS) | yes |
| 3 | Abstract, Tab. 2 | 8 % / 2 % of splits > α | 0.08 / 0.02 (RS) | yes |
| 4 | Abstract | commit 15 % / 39 % | 0.147 / 0.392 (RS) | yes |
| 5 | Abstract | EAC 21 % / 8 % | 0.207 / 0.078 pooled (RS) | yes |
| 6 | Abstract, §7.2 | +0.11 / +0.51 eWPM vs no commits, in every split | +0.114 [0.063, 0.164] / +0.510 [0.439, 0.599], share 1.00 (V3) | yes |
| 7 | Abstract | CRC: 34–42 % of splits > α | 0.34 / 0.42 (RS) | yes |
| 8 | Abstract | sEMG ≤ 9 % committed | 0.093 (RS, LTT max) | yes |
| 9 | Abstract, §7.4 | reuse +0.9 pp, p = 0.003 | +0.0091, Wilcoxon 0.00275; 35/14, sign p 0.0038 (RS; I recomputed it) | yes |
| 10 | §7.2 | CRC pure mean 0.046 / 0.049, MC SE ≈ 0.002 | 0.0456 / 0.0489; SD 0.0140 / 0.0152 over √50 = 0.0020 / 0.0021 | yes |
| 11 | §7.2 | LTT max − CRC max: 0.010 / 0.036 eWPM | −0.010 / −0.036 (V3) | yes |
| 12 | §7.2 | plug-in commit 0.13–0.26, WC 0.021–0.072 | [0.130, 0.259], [0.0213, 0.0724] (RS) | yes |
| 13 | Tab. 1 | plug-in 0.059 [0.045, 0.070], 48/189 | 0.0588 [0.045, 0.070], commit 0.232 (UCI) | yes |
| 14 | Tab. 1 | guaranteed A 0.025 [0.015, 0.035], 20/82 | 20/816, commit 0.100, EAC 0.244 (DR) | yes |
| 15 | Tab. 1 | guaranteed B 0.052 [0.043, 0.059], 42/157 | 42/816, 0.192, 0.268 (DR) | yes |
| 16 | Tab. 1 | published A / B 0.029 / 0.031, 24/329, 25/339 | 0.0294 / 0.0306 (DR) | yes |
| 17 | Tab. 1 | published plug-in 0.044 [0.027, 0.068], 36/386 | 0.0441 [0.027, 0.068], commit 0.473 (UCI) | yes |
| 18 | Tab. 1 | always commit eWPM 11.45 [10.70, 12.31]; 19.61 [17.81, 21.32] | same (UCI) | yes |
| 19 | Tab. 1 | sEMG trust 8.02 [6.93, 9.19]; guaranteed 7.98 [6.95, 9.11] | same (UCI, DR) | yes |
| 20 | **Tab. 1** | **MEG trust 3.20 [3.02, 3.44]** | **3.20 [3.01, 3.44]** in UCI (`ci.json` 3.0148, 3.4389). [3.02, 3.44] is the round-1 `baselines/results/tables.md` value | **no** |
| 21 | **Tab. 1** | **MEG gaze 3.15 [3.03, 3.31]** | **3.15 [3.02, 3.31]** in UCI (3.0245, 3.3052); [3.03, …] is round 1 | **no** |
| 22 | Tab. 1 | MEG always commit 2.58 [2.31, 2.88], 0.997 | same (UCI) | yes |
| 23 | §7.2 | sEMG vs gaze [+2.71, +4.91], [−0.07, +0.97], [−0.44, +0.09] | same (UCI) | yes |
| 24 | §7.2 | vs completion [+0.82, +2.99] | same (UM) | yes |
| 25 | §7.2 | MEG vs gaze [−0.10, +0.25], sentences [−0.04, +0.15], participants [−0.08, +0.22]; completion [−1.13, −0.64] | same (UCI, UM) | yes |
| 26 | §7.2 | day sign tests 12/13 p 0.003; 14/14 p 0.0001; 7/7 p 1.0; 1/13 | 12/1 0.0034; 14/0 0.0001; 7/7 1.0; 1/13 (UCI) | yes |
| 27 | §7.3, Tab. 4 | SGR β = 0.10: 0.112, none 0.64, EAC 0.069, marginal 0.008 | 0.112 / 0.64 / 0.069 / 0.0077 (SR) | yes |
| 28 | §7.3, Tab. 4 | β = 0.20: SGR 0.617, 0.088; joint 0.418, 0.085 | same (SR) | yes |
| 29 | §7.4 | reuse: published +0.001 p 0.72; sEMG −0.002 p 0.71; +0.007 p 0.036, sign 0.47 | 0.0009 / 0.716; −0.0016 / 0.714; 0.0073 / 0.036 / 0.473 (RS; recomputed) | yes |
| 30 | §7.4 | MDE80 0.035 / 0.038 / 0.040–0.057 | 0.0348 / 0.0378 / 0.0396, 0.0569 (RS) | yes |
| 31 | §7.4, Tab. 12 | Holm 0.072; p 0.012 / 0.014 | 0.0719 / 0.0120 / 0.0140 (UCI) | yes |
| 32 | Tab. 12 | clean CRC 0.0245, 0.0600, 0.0478, 0.0490, 0.0563, 0.0399; LTT pure 0.0270 … 0.0218 | same (UCI) | yes |
| 33 | Tab. 8 | MEG CRC pure 0.028 [0.006, 0.061], 18/19 | same (UCI) | yes |
| 34 | §7.7 | 0/300 → 0.0099; 0/200 → 0.015; 0/637 → 0.0047 | 0.0099 / 0.0149 / 0.0047 (UCI) | yes |
| 35 | App. N | 1/256 → one-sided upper 0.018 | 0.0184 (I recomputed it) | yes |
| 36 | Discussion | 96 % of always-commit eWPM; 71 % higher (8.02 vs 4.68) | 18.77/19.61 = 0.957; 8.02/4.68 = 1.714 | yes |

Other small mismatches found during tracing (minor issues m1, m2, m6):

- Tab. 1 caption: "0.0045 (816 items)" is labelled one-sided. It is the two-sided bound; the one-sided value is 0.0037.
- §6.3: "the largest change was 0.27 %" (frame-temperature snapping). This holds for B2T (0.267 %). For sEMG session-calibrated the largest relative change in `per_split.json` is 0.384 %, and cross-session 0.275 %.
- §7.4: "the 5th–95th percentile range of the reference is 0.029–0.071 on Brain-to-Text '25". This holds for split B and the published gate. For split A the range is 0.014–0.022 (Tab. 12).

## 5. Major issues

**M1. "Repeated deployments" are exchangeable re-splits, not deployments.** (Abstract; Introduction contribution 2; §6.3; §7.2 heading; Discussion "Which guarantee to deploy"; Conclusion.)
Each repeat permutes every day's trials at random before it splits them. Calibration and test items are therefore exchangeable within day by construction. Under that design, CRC must hold on average and LTT must hold with probability 1 − δ, as known theorems say. The 50 repeats are a Monte-Carlo check of those theorems conditional on one participant's pool. They are not "a test of the guarantee under the way such a rule would be deployed" (Introduction). In a real deployment the calibration block comes before use: earlier trials, earlier days or a session-start block. The only time-ordered evidence in the paper is fixed split B (early half of each day's fit trials as fit-A) and the small session-start analysis (App. R).
*Fix:* (a) Rename the design "random re-splits" or "repeated random splits" throughout. Say in the abstract that they are exchangeable by construction. (b) Add a cheap forward-in-time analysis on the existing B2T arrays. For example, calibrate on all trials of days ≤ d (or on the first k trials of day d) and test on day d + 1, for d = 1…13. Report the share of days above α for LTT max and CRC max. This is the analysis that answers the question in the title. (c) If (b) is not done, narrow contribution 2 to "behaviour of the guarantees over random re-splits of one participant's data".

**M2. Per-session risk is not controlled, so "a user lives in one deployment" does not support LTT as stated.** (Discussion "Which guarantee to deploy"; §5.3 "the per-deployment guarantee is the one a user experiences"; App. Q.)
The LTT guarantee is about the population risk of the mixture of 14 days. A user meets one day (session) at a time. I computed per-day test rates under the primary rule (LTT max, clean calibration) from the cached item tables (`C:/Users/zhang/bci-data/cache/paper1-r3/splits/`, outside the repo) and `splits-b2t.json`, pooled over the 50 splits. Published gate: day 34 has 0.102 (about 50 test trials per split). The other days have 0.007–0.048. Our decoder: 0.000–0.049 on all days. The committed RS table shows the same pattern for CRC max (published day 34: 0.108 mean). So the per-deployment guarantee does not give per-session control. On the published gate, one day in 14 ran at twice α under the paper's primary rule.
*Fix:* Report per-day (per-session) wrong-commit rates for the primary rule in a table or a figure panel. State in §5.3, App. Q and the Discussion that LTT bounds the risk of the calibration distribution (here, the day mixture), not each session. Name per-session or group-conditional calibration (for example, Mondrian / group-wise LTT per day, which needs ≥ 45 items per session) as the remedy. Then reconsider the sentence "the per-deployment guarantee is the one a user experiences".

**M3. The joint rule has no selective guarantee, and SGR's guarantee is weaker than the text implies.** (§5.4 "Joint … targets both"; §7.3 "the joint rule kept both targets"; Discussion "the joint rule … is the one to recommend"; frozen configuration "joint selective constraint with β = 0.10"; App. Q SGR statement.)
(a) Raising λ above λ_SGR keeps the marginal bound, but it can raise Pr(wrong ∣ commit). The selective risk is not monotone in λ, so the SGR bound at λ_SGR says nothing about max(λ_SGR, λ_CRC max). "Kept both targets" is an empirical result over 18 committing splits (β = 0.10) or 50 splits (β = 0.20, where joint equals CRC max). It is not a guarantee. (b) SGR's δ/⌈log₂ m⌉ correction runs over thresholds that the bisection picks from the same data. The binomial bound then conditions on a data-dependent number of accepted items. LTT-sel avoids both problems. (c) The frozen configuration pairs the selective constraint with LTT max, but the paper tested it only with CRC max. So the configuration to be confirmed was never run.
*Fix:* Replace "joint" with a valid joint procedure. One option is LTT with two risks: test H0(λ): R_marg(λ) > α or R_sel(λ) > β with p(λ) = max(p_marg, p_sel) over the fixed grid, with Bonferroni over the grid (the selective risk is not monotone). This gives FWER control for both targets at once. Run it on the 50 splits (CPU, item tables exist), and freeze that rule. Make LTT-sel, not SGR, the reference selective controller. State SGR's guarantee "as given by Geifman & El-Yaniv (2017), Lemma …".

**M4. Choosing the primary rule after the 50 splits, and the "allowed: 10 %" wording.** (Abstract; §5.3 "We chose it in this revision because … the repeated deployments showed …"; §7.2.)
(a) LTT max was chosen as the primary row after the 50 splits were seen, and the abstract then reports its numbers from those splits. The theory gives an a-priori reason for LTT, so the bias is probably small. It must still be said in the abstract, not only in §6.4 ("All inference is exploratory").
(b) "8 % and 2 % of deployments exceeded 5 % (allowed: 10 %)" compares a share of test-set exceedances with δ. LTT's δ is about the population risk, and test-sampling noise (SE about 0.008) adds to the share. In addition, 4/50 has a 95 % Clopper–Pearson interval of [0.022, 0.192] and 1/50 has [0.001, 0.106]. Fifty splits cannot show that the share is ≤ 0.10. They also cannot separate LTT max (4/50) from CRC max (7/50, [0.058, 0.267]).
(c) App. R reports the "population" exceedance of LTT on the 200 test-pool splits (0.5 % / 1.5 %). There, "risk on the whole pool" includes the calibration items (408 of 816, half the pool). Those items are the ones on which the threshold was chosen, so this risk is biased low. It is not the population risk of the i.i.d. theory.
*Fix:* (a) Add "chosen after these splits; exploratory" next to the abstract numbers. (b) Replace "(allowed: 10 %)" with "consistent with the δ = 0.1 target; 95 % CI for the share [0.02, 0.19]", and give CIs for all ">α" shares in Tab. 2. (c) To compute the risk that LTT really bounds, draw calibration sets *with replacement* from the pool and evaluate the chosen threshold on the full empirical distribution. The i.i.d. theory then holds exactly for the empirical distribution, and its population risk is known. Use this in App. R in place of the pool-including-calibration rate.

**M5. The reuse result is reported selectively and generalised too far.** (Abstract "+0.9 percentage points, p = 0.003"; §7.4; Discussion "Calibration data must play no other role".)
RS reports 12 reuse comparisons (4 conditions × 3 rule pairs). The paper reports one rule pair (pure CRC). Among the other results: for CRC max, reuse raises the rate with much stronger evidence (ours +0.0066, Wilcoxon 1.1 × 10⁻⁵; published +0.0035, p = 0.0014). For sEMG session-calibrated LTT pure, reuse *lowered* the rate (−0.0038, p = 0.020; sign 15/33). The Wilcoxon test over 50 random splits of one pool is valid only conditional on that pool. It is a test about these 1,628 trials and this decoder, not about calibration reuse in general. The abstract p-value reads as a general finding.
*Fix:* Report all three rule pairs per condition in one table, with Holm over the 12 tests (ours, pure CRC: Holm-adjusted p ≈ 0.03, still small). In the abstract, write "on our decoder, over random re-splits of this participant's data". Keep the Discussion's conclusion, which rests on the principle and not on the p-value.

**M6. The decoder hyperparameters in the repeated splits were tuned on trials that become calibration and test items.** (§5.4 "Separate data"; App. O; §6.3.)
The word-decoder grid (LM weight, edit penalty, word bonus) was tuned on a random 400 of the original 812 fit trials. In the 50 re-splits these trials are permuted into fit-A, calibration and test: about 100 into calibration and 200 into test per split. The re-tune check (`b2t-retune`) covers only the two fixed splits. The grid is small (12 points), so the bias is likely small. But App. O lists the exceptions as complete, and this one is missing.
*Fix:* Add it as exception (4) for the repeated splits. Optionally re-run the 12-point retune on fit-A for 5–10 splits to show that the choice is stable.

## 6. Minor issues

- **m1.** Tab. 1 caption: "one-sided 95 % upper bounds 0.0045 (816 items)" → 0.0037 (0.0045 is the two-sided CP upper bound; `unified-ci/results/tables.md`, column "CP95 two-sided").
- **m2.** Tab. 1 MEG rows: trust (= always offer) [3.02, 3.44] → [3.01, 3.44]; gaze [3.03, 3.31] → [3.02, 3.31]. These two values come from the round-1 bootstrap. They contradict §6.4 ("one quantity has one interval in every table"); Tab. 8 already uses [3.01, 3.43] for MEG CRC pure. Check that the teaser figure's MEG error bars use the unified bootstrap (`make_figures.py` prints "MEG trust source: G1 async").
- **m3.** §5.3, last paragraph: rewrite the left-continuity argument (Section 3 above).
- **m4.** Alg. 1: add "and C does not contain the 'other' option" to the offer condition. Note that an empty candidate list gives ABSTAIN before the guard.
- **m5.** §5.4 and Alg. 2: SGR accepts on b < β in the code. Write "< β" or change the code.
- **m6.** §6.3: "the largest change was 0.27 %" → "0.27 % (B2T), 0.38 % (sEMG)".
- **m7.** §7.4: "the 5th–95th percentile range of the reference is 0.029–0.071 on Brain-to-Text '25" holds for split B and the published gate only. Split A: 0.014–0.022.
- **m8.** Tab. 4: say that ">β" and "EAC" are computed over the splits that committed (18 of 50 for SGR at β = 0.10). "Never exceeded β" rests on 18 splits.
- **m9.** Tab. 2 and §7.2: sEMG repeated splits keep the 551 test sentences fixed. Their spread is calibration and fit variation only, not test variation. Say this in the Tab. 2 caption.
- **m10.** sEMG cross-session: 34 % of re-splits never committed under any rule (RS "no-commit splits 0.34"). Report it next to the means (0.006 mean wrong-commit), because the mean mixes zero-commit and committing splits.
- **m11.** Pure CRC on split A "fills the risk budget" (§5.3) but stops at the lowest eligible calibration score (0.3075). Test items below that score are never committed. Say this, because it is why pure CRC (20 wrong) is stricter than LTT at λ = 0.00 (22 wrong) in Tab. 8.
- **m12.** The abstract's "CRC met the target only on average" is the expected property, not a finding. A first-time reader will think CRC failed. Write "as designed, CRC bounds the mean; 34–42 % of single splits exceeded α".
- **m13.** App. Q, SGR sentence: give the unit and the assumption ("i.i.d. calibration sentences, separate from all fitted parts"), as you did for LTT and CRC.
- **m14.** The 14-cluster percentile bootstrap is honest but thin. For the two headline paired differences, consider adding a wild-cluster or BCa interval as a check. Optional.

## 7. Reproducibility check (Task 3)

All runs used the repo `.venv`, CPU only. All outputs went to the session scratch directory. `git status` was clean after each run.

| Analysis | How | Result |
|---|---|---|
| `experiments/2026-11-12-paper1-r3-analyses/v3-derived/run.py` | Copied the script and `per_split.json` to scratch and ran it there | `v3_derived.json` and `tables.md` **byte-identical** to the committed files |
| `unified-ci/run.py --stage assemble` (Tab. 2/3 CIs, Holm, day-stratified reference, sign tests, CP bounds) | Imported the module, redirected `OUT` to scratch, read the committed reruns | `ci.json` (641,777 bytes) and `tables.md` **byte-identical**; run time about 5 s |
| `papers/paper1/make_figures.py` (all 7 figures) | Copy with `OUT` → scratch | All 7 PDFs have the same size; each differs in exactly 4 bytes, the `CreationDate` timestamp (`D:20261112022454` vs `D:20261112020202`). Content identical. |
| Independent CRC / LTT | My own implementation (not the repo's functions) on the 100 cached B2T item tables (ours + published, 50 splits each) | All 400 thresholds (CRC pure, LTT pure, CRC max, LTT max) and their test wrong-commit rates match `per_split.json` exactly (0 mismatches) |
| Tab. 2 aggregates | Recomputed from `per_split.json` | Means, p05/p95, ">α" shares, commit rates and pooled EAC match for all 5 conditions × 6 rules |
| Reuse tests, CP bounds, Holm | scipy, by hand | Match (Section 4, rows 9, 29, 31, 34, 35) |

Reproducibility is very good. One limit: the B2T item tables of the repeated splits live outside the repo (`C:/Users/zhang/bci-data/cache/paper1-r3/splits/`). A third party cannot re-run the per-split thresholds without the decode cache and several hours of decoding. They are derived numbers (no raw signals), so consider releasing them in a data archive (for example Zenodo) with the paper. For the figure PDFs, set `SOURCE_DATE_EPOCH` (or `metadata={'CreationDate': None}`) so that a re-run is byte-identical.

## 8. Are the conclusions over- or under-stated? (Task 4)

Over-stated:
- "Test of the guarantee under repeated deployment" and "a high-probability guarantee … the one a user experiences" (M1, M2). The 50 splits re-use one participant's 1,628 trials under within-day exchangeability. They show split-to-split variation of a known procedure. They do not show validity under time order, across sessions or across people. The per-day breakdown shows that per-session risk can be 2α under the primary rule.
- The joint rule as "the one to recommend" (M3): it has no guarantee for the error among commits.
- "8 % and 2 % (allowed: 10 %)" (M4): 50 splits cannot confirm δ-level control, and the ranking of LTT max over CRC max rests on 4 vs 7 events.
- The reuse p = 0.003 in the abstract (M5): conditional on one pool, one of 12 comparisons, and the wording reads general.

Fairly stated or under-stated:
- The limitations section, the exploratory label, the Holm result ("no test significant"), the MEG negative-control framing and the no-guarantee-for-new-sentences statement are honest and correct.
- Speed claims are hedged correctly.
- The population view supports the paper more than its test-set exceedances do. Test-set exceedance includes test noise, and the finite-pool partition makes calibration and test rates dependent. A with-replacement design (M4c) would probably show lower exceedance for LTT and give the paper a cleaner and stronger statement.

Multiple comparisons: Holm over the six exchangeable-reference tests is right. The reuse family (12 tests), the per-day sign tests and the user-model CIs (48 condition–variant pairs) are uncorrected. That is acceptable for an exploratory paper only if the abstract does not quote an uncorrected p-value as a finding.

## 9. Must fix before submission

1. M1: rename "deployments" to random re-splits, and either add the forward-in-time (calibrate on earlier days, test on the next day) analysis or narrow contribution 2.
2. M2: report per-day rates for the primary rule, and correct "the per-deployment guarantee is the one a user experiences".
3. M3: replace the joint rule with a valid joint LTT (max of the two p-values, fixed grid), re-run it, and freeze that rule. Do not recommend a rule without a guarantee.
4. M4: say "chosen after the splits" in the abstract, remove "(allowed: 10 %)", add CIs to the ">α" shares, and fix the App. R population-risk computation.
5. M5: give the full reuse table with Holm, and qualify the abstract p-value.
6. m1, m2: correct the 816-item bound (0.0037) and the two MEG CIs in Tab. 1, so that the "one bootstrap" claim is true.
7. M6: list the decoder-grid overlap as an exception for the repeated splits.

## 10. Verification of round-3 claimed fixes

I read `papers/paper1/round-3-response.md` only after I wrote Sections 1–9, and only to check claimed fixes.

| Claimed fix (response row) | Status in draft v3 |
|---|---|
| St-M6.2 zero-event bounds "exact one-sided 95 %" | **Partly.** 0/300, 0/200, 0/637 and 0/551 are correct. The Tab. 1 caption also has "0.0045 (816 items)", which is the two-sided bound (m1). |
| St-M6.6 "one bootstrap for Tab. 1 …" | **Partly.** Two MEG CIs in Tab. 1 are still round-1 values (m2). All other Tab. 1 CIs I checked match `ci.json`. |
| St-M6.3 multiplicity, Holm on six tests | Done for those six tests. The reuse family is still uncorrected (M5). |
| St-M1(a) drift claims, "never significantly above" removed | Done. §7.4 wording matches `unified-ci` (0.012 / 0.014, Holm 0.072). |
| Ed-M3 selective controllers; "joint rule is recommended" | Done as an analysis. The recommendation has no guarantee (M3). |
| Ed-M5(c) per-day results "partly" | Still partly. The per-day table covers plug-in and CRC max only, not the primary LTT max rule. That table shows the day-34 problem (M2), and the text does not discuss it. |
| m19 left-continuity sentence | Added, but the argument is unclear (m3). |
| St-M7 Algorithms 1–2 | Done. They match the code, apart from the small gaps in Section 3. |
