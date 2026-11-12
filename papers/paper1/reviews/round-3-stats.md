# Paper 1, review round 3: statistics, risk control and reproducibility

- **Draft:** `papers/paper1/draft-v2.pdf` (commit `7cec5f1`). The PDF is byte-identical to `latex/build/main.pdf` built from the committed LaTeX.
- **Reviewer profile:** statistics, conformal prediction and risk control, computational reproducibility.
- **Date:** 2026-11-12.
- **Scope:** `latex/sections/*.tex`, `src/fidetype/trust/{risk_control,online_risk}.py`, `make_figures.py`, `analysis_r1.py`, `experiments/2026-11-12-paper1-r1-analyses/*` and the experiment folders they read.
- **Independence:** I wrote sections 1–6 before I read the earlier reviews. Section 7 is the only part written after I read them. (Earlier, a search showed me two lines of `round-2-changes.md`. That file is a change list, not a review.)
- All scratch work is in the session scratchpad. I edited no paper or code file in the repo.

## 1. Summary

The paper defines a per-frame decoder output format (NeuralTextStream) and a stream-only trust layer. The layer chooses commit, offer or abstain. Conformal risk control (CRC), Learn-then-Test (LTT) or online updates set the commit threshold. The authors test the layer offline on one intracortical participant (Brain-to-Text '25), composed sEMG sentences and MEG typing. Draft v2 has a safety-first framing. The primary outcome is the marginal wrong-commit rate. The draft also adds a "clean calibration" protocol and concludes that the within-day drift reported earlier was an artefact of data reuse.

The computational side is strong. The paper-level derivations reproduce exactly from committed files. My own independent code for CRC, LTT and the exchangeable-reference test gives the same numbers to 4 decimals. The code states its guarantees and assumptions carefully, and the formal statements in §4.4–4.5 are correct.

The inference has weaknesses that the safety framing makes important:

1. **The drift claim goes past the evidence.** The data-reuse explanation is not shown. The abstract says no clean result was significantly above the exchangeable reference, but one was (p = 0.012).
2. **CRC is not binding in most clean rows** (B2T split A, the published gate and MEG). The text credits CRC with reductions that come from refitting the pipeline on fit-A.
3. **The headline safety numbers come from the plug-in policy.** That policy has no guarantee and exceeded α (0.059).
4. **Some CRC analyses break the exchangeability or separate-data assumptions** that the paper states:
   - MEG instances are clustered by sentence.
   - The sEMG session-calibrated condition uses different decoders for calibration and test.
   - Calibration data partly overlap the decoder-tuning data.
5. **All results come from one fit/calibration realisation.** The fit-to-fit spread (0.0245 vs 0.0600 for the same decoder) is as large as the effects.

## 2. Recommendation

**Major revision.** The paper is reproducible, and its formal statements are correct. The main changes are in how the paper interprets and states its results (§4, M1–M3), plus one cheap CPU experiment (M5) that tests the CRC guarantee directly under the deployment protocol. The paper is not ready for submission while M1–M3 are open, because the abstract contains a false statement (M1).

## 3. Reproducibility findings

### 3.1 Method

1. I exported the committed tree with `git archive HEAD` into a fresh scratch repository. The export has no git-ignored data, so a script that reads an uncommitted file fails there.
2. I ran `analysis_r1.py` and `make_figures.py` in the export with the repo `.venv`, CPU only (`CUDA_VISIBLE_DEVICES=""`). Then I compared the outputs with the committed files.
3. I wrote an independent re-implementation of CRC, LTT (exact binomial, fixed sequence), the exchangeable reference, a day-stratified version of that reference and the day-cluster bootstrap. It does not import `fidetype`. I ran it on the committed clean-drift item tables.
4. I re-ran `experiments/2026-11-12-paper1-r1-analyses/clean-drift/run.py` in the export. It used a scratch copy of the local decode cache, because raw data and decode caches are not in git.

### 3.2 Re-run diffs

| Output | Re-run result vs committed file | Verdict |
|---|---|---|
| `papers/paper1/data/r1-derived.json` | Byte-identical. The script's own asserts (re-drawn split means = committed means) pass. | reproduces |
| `figures/fig1_teaser.pdf` | Differs in 7 bytes, all in `/CreationDate`. Identical after that field is removed. | reproduces |
| `figures/fig_risk_coverage.pdf` | same (7 bytes, CreationDate only) | reproduces |
| `figures/fig_selective_risk.pdf` | same | reproduces |
| `figures/fig_crc_splits.pdf` | same | reproduces |
| `figures/fig_user_model.pdf` | same | reproduces |
| `figures/fig_null_audit.pdf` | same | reproduces |
| `figures/fig_ece.pdf` | same | reproduces |
| Tab. 3 offline columns (CRC λ, test rate, commit, LTT, exchangeable mean / p05 / p95 / p), from committed `clean-drift/results/items-*.json` with my own code | All 7 conditions agree to 4 decimals. Examples: ours-A λ 0.3075 → 0.0245, p 0.012; ours-B λ 0.4083 → 0.0600, p 0.210; published-A 0.0478, p 0.540; sEMG x-session λ 0.2036 → 0.0563, p 0.299; sEMG calib 0.0399, p 0.596. Day-bootstrap CI for ours-A: [0.0145, 0.0352] vs paper [0.014, 0.035]. | reproduces (independent code) |
| `clean-drift/results/*` re-run from cached decodes (CPU) | All 9 result JSONs (`clean_drift_b2t.json`, `clean_drift_emg.json`, 7 `items-*.json`) are byte-identical. Only `run.log` (time stamps) differs. Runtime about 3 min, because the decodes were cached. | reproduces (from cached decodes; the decoding itself was not re-run) |

### 3.3 Inputs and traceability

- **Committed inputs only:** yes. Both scripts ran in a tree that holds only committed files and produced identical outputs. `make_figures.py` logged "MEG trust source: G1 async (committed)", so it did not use the markdown fallback.
- **Experiment-level results** (`baselines.json`, `clean_drift_*.json`, `user-model-*.json`, ...) need the raw datasets and a decode cache outside the repo (`C:/Users/zhang/bci-data/...`). An outside reader cannot regenerate them without downloading the data. Document this, with the data hashes and the exact commands, in the paper's code-availability statement.
- **Numbers traced:** I sampled 40 numbers (§6). 36 trace exactly. Four are wrong or stale:
  - the published-gate gain 0.66 should be 0.65;
  - "49 of 54" counts 6 trivial rows;
  - the MEG adapter has 156 lines, not 148;
  - two CIs for the same quantity differ between tables because the bootstrap seeds differ.
- **Draft hygiene:** 8 `\todo` markers remain in the PDF. One of them is in Results (MEG seeds).

## 4. MAJOR issues

### M1. The clean-drift section claims more than the data show, and the abstract states something false. [WRITING + NEW-EXP]

**Location:** abstract; §1 contribution 2; §7.7 (title and text); Discussion "Data reuse can fake a drift failure"; Conclusion.

**Why it is a problem:**

1. **The abstract is false as written.** It says clean CRC was "never significantly above the rate for exchangeable data". In split A, the observed rate 0.0245 is above the exchangeable reference (mean 0.018, 5–95% range [0.0135, 0.0221]; one-sided p = 0.012). §7.7 qualifies this ("no value *above α*…"), but the abstract and the section title ("No detectable shift") do not.
2. **Split A shows a real calibration-vs-test difference.** At the CRC threshold, the calibration set had 2/401 wrong commits and the test half had 20/816 (Fisher two-sided p = 0.020). A day-stratified permutation reference gives p = 0.016. CRC "survived" here only because it was not binding (M2).
3. **The data-reuse explanation is not shown.**
   - Split B: clean 0.0600 vs reused 0.0625.
   - sEMG cross-session: clean 0.0563 vs reused 0.0635.
   - Two of the three binding clean results are still above α and almost equal to the reused values.
   - Reused vs clean also changes two things at once: the pipeline (fitted on 812 vs 411 trials) and the calibration data.
   - In the committed M2-13 items, the reuse effect is small and not significant. In-sample fit-half rates are 0.0456 vs test 0.0588 at λ = 0.5 (Fisher p = 0.27); I found p = 0.16–0.74 over λ ∈ [0.3, 0.7].
   - The mechanism in the Discussion ("their scores look better calibrated than new scores, and the threshold is too permissive") is plausible but not shown.
4. **The test has low power.** The exchangeable 5–95% range is [0.029, 0.071] for B2T and [0.018, 0.080] for sEMG. A real shift of +0.02 absolute (a 40% relative excess) would usually go undetected. "No detectable shift" is not evidence of no shift.
5. **No multiplicity correction:** six one-sided tests, uncorrected (see M6).

**Fix:**

- (a) Rewrite the abstract, §7.7 title and Discussion. Suggested text: "With clean calibration, offline CRC gave 0.025–0.060; the two values above α (0.060, 0.056) were within the range of exchangeable splits (p ≥ 0.21). One split showed a calibration-vs-test difference (p = 0.012; not significant after Holm correction over six tests) where CRC was not binding. The earlier 0.0625 is within the clean protocol's split-to-split range; we therefore neither claim within-day drift nor that data reuse caused it. Reusing fit data for calibration is invalid in principle, and the clean protocol is the one we report."
- (b) If you want to keep a causal statement about reuse, run a controlled test (CPU, cached decodes). Over R ≥ 50 random partitions of each day's fit half into fit-A and cal:
  - fit the pipeline on fit-A;
  - calibrate CRC on (i) fit-A itself (reuse) and (ii) cal (clean);
  - compare the test-rate distributions, paired by partition.
  This isolates reuse from pipeline size.
- (c) Report a power statement, i.e. the smallest shift detectable at 80% power given the reference spread.
- (d) Use the day-stratified permutation reference for B2T.

### M2. CRC is not binding in most clean rows, so the CRC rows test the pipeline refit, not CRC. [WRITING + ANALYSIS]

**Location:** Tab. 2 rows "trust, CRC (clean cal.)"; §7.2 ("With CRC on the clean calibration set (split A), the rate fell to 0.0245…"); Tab. 3; Tab. 7 last row; §7.6 MEG sentence.

**Why it is a problem:**

| Case | CRC bound on the calibration set | What decided the rate |
|---|---|---|
| B2T ours, split A | (n R̂ + 1)/(n + 1) = **0.0075**, far below α | The fit-A guard and policy rules. λ̂ is the lowest eligible calibration score, so CRC commits every eligible item. LTT picks λ = 0.00, which is why LTT (0.0270) > CRC (0.0245) in Tab. 3. |
| Published gate | binding | CRC equals the fit-A plug-in exactly: ablation `crc_on − crc_off` = [0.00, 0.00] for both decoders. |
| MEG | not binding | Only 2.4% of items are eligible. CRC commits all of them. |

So the fall from 0.059 (trust) to 0.0245 comes from refitting temperatures, guard and policy on 411 instead of 812 trials, not from CRC. The text says it comes from CRC. Tab. 2 also shows only split A. Split B gives 0.0600 > α for the same decoder, so showing only A looks like selection.

**Fix:**

- Show both splits in Tab. 2, or the mean over the repeated partitions of M5.
- Add a column for the CRC bound on the calibration set, or a "binding?" flag.
- Rewrite the §7.2 sentence. For example: "Refitting the pipeline on fit-A gave 0.0245 (split A) and 0.0600 (split B); CRC on the clean calibration set was not binding in split A and left the plug-in threshold almost unchanged in split B."
- State which rule the CRC rows use: pure CRC (that is what the code does) or the deployable max(λ_tuned, λ̂_CRC). On sEMG the two rules differ: pure CRC commits 24% / 9%, and the max rule would give the plug-in's 4% / 2%.

### M3. The headline numbers come from a policy with no guarantee, but the title and abstract call the decisions risk-controlled. [WRITING]

**Location:** title; abstract "Main results"; §1; Fig. 1; Discussion; Conclusion.

**Why it is a problem:** "Cut wrong commits from 61% to 5.9%" and "4.4%" are plug-in results. That policy has no finite-sample guarantee, and on B2T ours it exceeded α (0.059 > 0.05). The risk-controlled rows come from a different pipeline (fit-A). A reader of the abstract will think the 5.9% is risk-controlled.

**Fix:** pick one of these:

- Make the clean CRC/LTT rows the primary safety result in the abstract and Fig. 1, with the plug-in as a secondary row.
- Keep the plug-in as primary, but say in the abstract that it has no guarantee and exceeded α on B2T ours, and quote the CRC/LTT rows with their split range.

LTT is the natural primary row for a safety paper: 0.027 / 0.052 (ours A / B) and 0.029 / 0.031 (published A / B), with a high-probability statement.

### M4. Some reported CRC/LTT analyses break the exchangeability or separate-data assumptions. [WRITING + ANALYSIS]

**Location:** §4.4 "separate-data requirement" ("Every CRC and LTT result in this paper meets this requirement"); §6.2 calibration data; Tab. 8 (MEG rows); Appendix "How to state the guarantees".

**Why it is a problem:**

- (a) **MEG items are clustered by sentence.** The 637 test instances come from 17 sentences typed by 19 people, and the clean calibration set has 5 sentences (199 instances). Instance-level CRC is valid only if calibration and new items are exchangeable. Instances of one sentence are strongly dependent, so the unit is the sentence. With 5 calibration sentences, sentence-level CRC is infeasible (n < 19). The random instance-level splits in Tab. 8 put the same sentences in calibration and test. G1 already ran sentence-grouped splits (`experiments/2026-11-11-g1-async-meg-trust/results.md`: CRC 0.0194, p95 0.0377), but the paper does not report them.
- (b) **sEMG session-calibrated uses different decoders.** Calibration logits come from decoder run `calib_b` and test logits from `calib_a` (cross-fitted; `emg-toronto/trust.py` `CONDITIONS`). The score function differs between calibration and test, so the two sets are not exchangeable by design. The eligible-wrong rate is 0.748 on calibration vs 0.541 on test. CRC was conservative here only because the calibration decoder was worse.
- (c) **"Disjoint from all fitted parts" is not strictly true.**
  - B2T: the word-decoder grid (LM weight, edit penalty, word bonus) was tuned on a random 400 of the 812 fit trials (`b2t25-trust/run.py` `stage_tune`). About half of each clean calibration set overlaps the tuning set.
  - MEG: the decoder checkpoint was early-stopped on validation CER (`m1-09` configs, `early_stop_metric: val_cer_typed`). The validation data include the 5 calibration sentences.
  The effects are probably small (12-point WER grid; checkpoint choice). But the paper's central lesson is about data reuse, so the claim must be exact.
- (d) **The sEMG online order is artificial** (participant by participant). The "long-run" online numbers on sEMG are therefore not a temporal sequence. The limitations cover B2T order only.
- (e) LTT needs i.i.d. sampling, a stronger assumption than exchangeability. In the pool-risk analysis, splits sample without replacement from a finite pool, which makes the binomial test conservative. That is fine, but say so.

**Fix:**

- Replace "every CRC and LTT result meets this requirement" with a precise per-device list of what each calibration set was and was not used for.
- For MEG, report sentence-grouped splits only. Say that instance-level CRC on 5 sentences carries no guarantee for new sentences.
- For sEMG calib, state the different-decoder design or calibrate on items from the test decoder.
- For B2T, re-tune the decoder grid on fit-A only, or show that the grid choice is the same on fit-A.

### M5. All results come from one fit/calibration realisation; fit-to-fit variance is large and the CIs leave it out. [NEW-EXP (CPU) + WRITING]

**Location:** Tab. 2, Tab. 3, §6.3 statistics, Limitations 4.

**Why it is a problem:**

- The same plug-in recipe fitted on two halves of the same fit data gave 0.0245 (split A) and 0.0600 (split B). This spread is larger than the gap between the plug-in and CRC, and comparable to α.
- Every CI in Tab. 2–3 is a bootstrap over test days or participants with the fitted pipeline and the threshold held fixed. So the CIs leave out pipeline-fit variability and calibration-set variability. CRC's guarantee is marginal over the calibration draw, so a CI conditional on one calibration set does not test it.
- No experiment shows the CRC marginal guarantee holding under the deployment protocol. The random splits of the test pool only check the implementation, as §7.6 says.
- The MEG seed results are still a TODO.

**Fix:**

- Repeat the deployment protocol over R ≥ 50 random within-day partitions of the B2T fit half into fit-A and cal (and R random B1/B2 partitions for sEMG). For each repeat, record the test rate of the plug-in, pure CRC, max-rule CRC and LTT. Report:
  - the mean (the CRC target);
  - the share of repeats with population risk > α (the LTT target; use the test half as a proxy);
  - the spread.
  The decode caches exist, so this is CPU-only and about R × 10 min for B2T.
- Say in every caption that the CIs are conditional on the fitted pipeline and λ.

### M6. Statistical reporting details. [ANALYSIS + WRITING]

**Location:** §6.3; all tables.

**Problems and fixes:**

1. **Few clusters.** The B2T bootstrap uses 14 day clusters of unequal size (50–169 trials). Percentile cluster bootstraps with this few clusters usually under-cover.
   - For the key paired differences (trust − always offer), add a day-level sign or permutation test, or a wild cluster bootstrap, e.g. "positive on k of 14 days".
2. **Zero-event rates.** These get [0, 0] or [0, 0.009] bootstrap CIs, which are not real 95% bounds.
   - Give exact upper bounds, e.g. 0/551 → 95% upper bound 0.0067 (Clopper–Pearson; rule of three 0.0054); 0/300 control trials → 0.012. Note that clustering makes even these optimistic.
3. **Multiplicity.** Tab. 3 has six one-sided tests and no correction. The baselines, ablation and user-model tables show many intervals. The paper says these are "descriptive and not corrected", which is acceptable.
   - Apply Holm to the Tab. 3 p-values; ours-A then becomes non-significant (0.012 × 6 = 0.072). Do not use "significantly" anywhere else.
4. **The p-value definition differs.** The caption says "share of these splits at least as high as observed". The code uses (k + 1)/(B + 1). The numbers are almost the same.
   - Make the caption match the code.
5. **Post-hoc endpoints.** The paper says the primary endpoints were chosen after the first evaluation runs, and the safety-first framing was adopted after the speed claim failed (round 2).
   - Call the endpoints "pre-specified in revision 1, after the first runs" in the abstract-level summary, or call all inference exploratory.
6. **CIs differ between tables for the same quantity.**
   - B2T ours trust eWPM: Tab. 2 [10.82, 12.38] vs ablation [10.81, 12.36].
   - MEG trust − gaze: [−0.11, +0.26] in `baselines` vs [−0.11, +0.27] in `user-model`.
   - The user-model bootstrap uses B = 1000, but §6.3 says B = 2000.
   - Compute each quantity once (one seed, one B) and reuse it everywhere, or state the per-table B.
7. **Error among commits** is a ratio with a random denominator. The bootstrap handles it, but for small commit counts (sEMG 2/21, 2/10, 1/6) give the counts only, not "0.10".

### M7. A reader cannot re-implement the trust layer from the paper and appendix. [WRITING]

**Location:** §5.1–5.4; Tab. 10; App. "Per-device settings".

**Why it is a problem:** these parts are missing or under-specified:

- **Conformal sets.** They appear in Tab. 10 (set size 3.4), the ablation and Fig. 3, but the paper never defines them: no nonconformity score, coverage level or fitting data.
- **"Calibrated acoustic posterior" of a character** (guard low-evidence term). The paper does not say how per-character posteriors are obtained from a CTC stream (alignment? peak frames?), or how they are obtained for the phoneme-to-word path.
- **"Posterior-weighted word agreement"** (guard inconsistency term): no formula.
- **Frame-temperature fit:** "greedy CTC peak frames" needs a definition (which frames? blank handling?).
- **Policy grid:** values only "in the repository". The objective's tie-breaking, the abstain-risk rule and the offer_words marking rule are not given.
- **Score definition:** "the other policy rules allow a commit" lists no rules.
- **Notation:** the table lacks L, R, R̂, p̂_top1 and the guard risk. γ and N appear only in the appendix.

**Fix:**

- Add an "Algorithm 1: trust decision" box and an "Algorithm 2: fitting" box with all formulas.
- Add a table of grid values, and a precise s_i definition: s_i = p̂_top1 if guard_risk ≤ g_max ∧ … else −∞.
- Define the conformal set or drop it from the main text (the ablation shows it changes little).
- The online-method table (Tab. 12) and the CRC/LTT text are re-implementable as written; my independent code matched.

## 5. MINOR issues

| # | Location | Issue | Fix | Tag |
|---|---|---|---|---|
| m1 | Abstract, §7.2 | Published trust − always offer: 18.767 − 18.114 = **0.653**, written as "0.66" (rounded from the rounded table values). CI [0.53, 0.80] is right. | Write 0.65. | WRITING |
| m2 | §7.3 | "Unchanged in 49 of 54 condition–variant pairs" counts the 6 main rows, which cannot change. The non-trivial count is **43 of 48**. The 5 changes are sEMG-calib ×4 (0.004 → 0.020) and sEMG-x-session p_miss 0.2 (→ 0). | Write "43 of 48 variants". | WRITING |
| m3 | §7.6, Tab. 8, Fig. 9 | One paragraph mixes 500-split numbers (`smallcal`: P>α 0.43 / 0.46, p90 0.069 / 0.071) with 200-split numbers (`r1-derived`: pool risk 0.5% / 1.5% / 33% / 29%; Fig. 9). The 200-split P>α is 0.445 / 0.415. | Say which split set each number comes from, or use one set. | WRITING |
| m4 | Tab. 3 | Tab. 3 uses `\ci` brackets for the 5th–95th percentile range of the reference and for bootstrap CIs, side by side. | Use another notation for the reference range, e.g. "0.018 (0.014–0.022)". | WRITING |
| m5 | Tab. 3, §7.7 | LTT gives a *higher* rate than CRC in ours-A (0.0270 vs 0.0245) because neither is binding and the LTT grid reaches 0.00. Readers will find this odd. | One sentence, plus the binding flag of M2. | WRITING |
| m6 | App. "How to state the guarantees" | The aci bound "(1 − λ₁ + η)/(ηT)" leaves out the delay. Tab. 12 note b has η(1 + d). | Add "with no feedback delay; with delay d replace η by η(1 + d)". | WRITING |
| m7 | §7.6 | "On sEMG, 9 of 18 participants never committed": the condition (session-calibrated) is not named, and 18 vs 19 participants is not explained (one participant has too few test sentences). | Name the condition and the exclusion. | WRITING |
| m8 | §6.2 | "The policy grid uses the first 142 sentences of half B": half B is a random permutation (`emg_condition`), so these are random. | Write "a random half". | WRITING |
| m9 | §3, §5.2 | K = 10, but the published gate ranks 11 candidates (published + our 10). | Say so where K is defined. | WRITING |
| m10 | §7.4 | ECE and AUROC have no CIs. τ_s = 20.0 sits on the search boundary for MEG and sEMG x-subject, so the sentence calibrator flattens the confidence there. | Add day / participant bootstrap CIs; mention the boundary in the text, not only in the Tab. 10 caption. | ANALYSIS |
| m11 | §5.5, §7.7 | "Long-run only" is abstract. The data show short-window excess: ours-A aci rolling max 0.085, 18% of rolling windows above α (`clean_drift_b2t.json`, `roll_max`, `roll_share_gt_alpha`). | Report max rolling-50 rates for the online methods. | WRITING |
| m12 | §7.7 | Noticed-errors-only runs: the paper gives B2T split B (0.0527) and sEMG x-session (0.0581). sEMG session-calibrated also went above α (0.0563), and the published gate reached 0.0502. | Report all of them, or give the range 0.027–0.058. | WRITING |
| m13 | Tab. 3 caption | "Clean CRC [CI]" is a CI with λ held fixed. | Write "95% CI over days or participants, conditional on the calibration set". | WRITING |
| m14 | §4.4 | The deployable max rule is valid (a) when λ_tuned is fixed before calibration, and (b) when tuned on the calibration data under λ ≥ λ̂ (`crc_tune` in M2-13). The loss is pointwise non-increasing, so both hold. | State both cases in one sentence. | WRITING |
| m15 | §4 format | Adapter sizes: `spanishbcbl_meg.py` has **156** lines at HEAD (148 at `73c253d`, before the benchmark commit). The other two match (412, 568). | Update, and define the count (physical lines incl. blanks and docstrings). | WRITING |
| m16 | Results, Ack., title page | 8 `\todo` markers remain. One is in Results (MEG seed SDs; seeds 1–2 are being trained now). | Fill them in, or move them to Limitations before submission. | WRITING |
| m17 | §3 | c_i is defined as top-1 ≠ truth. The reported rates use the simulated user's `wrong_commit`; the code asserts that the two are equal for every commit. | One clause: "for committed items the simulated wrong commit equals c_i". | WRITING |
| m18 | §7.2 | The "trust" and "CRC" rows use different pipelines (812-trial vs 411-trial fit), so their paired difference mixes two changes. The caption says this, but the text compares them directly. | Say so in the text. | WRITING |
| m19 | Code (not the paper) | CRC uses "commit if s ≥ λ", a left-continuous loss, while Thm. 1 of Angelopoulos et al. assumes right-continuity. The docstring argument is correct: the commit set is a subset of the paper's "s > λ" set at the inf, so the loss is pointwise ≤ and the result stays valid. | None needed; the paper's "valid and slightly conservative" is right. | — |

**Correct as stated (checked against code and the cited results):**

- CRC rule and bound, B = 1, L(+∞) = f = 0 ≤ α.
- n < 1/α − 1 = 19 infeasibility.
- LTT fixed-sequence with exact binomial p-values P(Bin(n, α) ≤ nR̂), which is super-uniform under H₀: R > α.
- LTT infeasible below n = 45 (0.95^45 = 0.0994 < 0.1; 0.95^44 = 0.105).
- The aci identity (1/T)ΣL_t ≤ α + (λ_{T+1} − λ₁)/(ηT), with the lower clip only raising λ.
- The a-priori bound with scores ≤ 1 and f ≡ 0 (λ ≤ 1 + η(1 − α)(1 + d); code uses ηB(1 + d)).
- The aci_window identity with the upper clip only lowering α_t.
- The statement that silent errors fall outside all bounds.
- Test-sampling SE ≈ √(0.05·0.95/408) = 0.011.

## 6. Traced-number table (40 numbers)

Paths are relative to the repo root. R1 = `experiments/2026-11-12-paper1-r1-analyses`. ✓ = exact (after the paper's rounding). ✗ = differs.

| # | Paper location | Paper value | File | File value | |
|---|---|---|---|---|---|
| 1 | Abstract, Tab. 2 | trust WC 0.059 [0.045, 0.071] (B2T ours) | R1/baselines/results/baselines.json `b2t-ours.point.trust` | 0.0588 [0.045, 0.071] | ✓ |
| 2 | Tab. 2 | always commit 0.610 [0.569, 0.648] | same, `always_commit` | 0.6103 [0.569, 0.648] | ✓ |
| 3 | §7.2 | 48 of 189 commits wrong | papers/paper1/data/r1-derived.json `ledger_replay_b2t_ours` | 48 / 189 | ✓ |
| 4 | Abstract, §7.2 | +0.18 [+0.12, +0.24] vs always offer | baselines.json diff `trust-never_commit` | 0.177 [0.12, 0.24] | ✓ |
| 5 | Abstract, §7.2 | published +0.66 [+0.53, +0.80] | baselines.json `b2t-published` | 18.7671 − 18.1139 = **0.653**; CI [0.53, 0.80] | ✗ (0.65) |
| 6 | §7.2 | −4.3% vs always commit, [−1.01, −0.67] | baselines.json `b2t-published` | (19.612 − 18.767)/19.612 = 4.31%; [−1.01, −0.67] | ✓ |
| 7 | Tab. 2 | 36/386, 0.09 | baselines.json `b2t-published.point.trust` | 0.0441·816 = 36; 0.473·816 = 386; 0.093 | ✓ |
| 8 | §7.2, Tab. 2 | CRC split A 0.0245, commit 0.10, EAC 0.24 | R1/clean-drift/results/clean_drift_b2t.json `b2t-ours/alternate` | 0.0245, 0.100, 0.244 | ✓ |
| 9 | §7.2 | CRC − always offer [+0.07, +0.16] | baselines.json diff `crc-never_commit` | [0.07, 0.16] | ✓ |
| 10 | §7.2 | sEMG commits 21, 10, 0 of 551 | baselines.json `emg-*.point.trust.commit_rate` | 0.038, 0.018, 0 (×551 = 21, 10, 0) | ✓ |
| 11 | §7.2 | sEMG calib trust − gaze [+2.73, +4.84] | baselines.json `emg-calib` diff | [2.73, 4.84] | ✓ |
| 12 | §7.2 | vs gaze + completion [+0.74, +2.99] | R1/user-model/results/tables.md (emg-calib, main) | [0.74, 2.99] | ✓ |
| 13 | §7.2 | MEG trust − gaze [−0.11, +0.26]; sentences [−0.05, +0.15]; participants [−0.08, +0.22] | baselines.json `meg-async` (`bootstrap`, `bootstrap_sentences`, `bootstrap_participants`) | [−0.11, 0.26]; [−0.05, 0.15]; [−0.08, 0.22] | ✓ (user-model gives [−0.11, 0.27]; see M6.6) |
| 14 | §7.2, Tab. 2 | MEG CRC commits 3.0%, 95% wrong, WC 0.028 [0.008, 0.061] | baselines.json `meg-async.point.crc` | 0.030, 0.947, 0.0283 [0.008, 0.061] | ✓ |
| 15 | §7.4 | sentence ECE 0.448 → 0.067; τ_f 3.78; token ECE 0.090 → 0.130 | experiments/2026-11-10-b2t25-trust/results/tables.md (w_c_trust) | 0.448 / 0.067; 3.781; 0.090 / 0.130 | ✓ |
| 16 | §7.4 | AUROC 0.797 (p̂_top1), guard 0.702 | same row | 0.797, 0.702 | ✓ |
| 17 | §7.4 | sEMG ECE 0.154 / 0.328 / 0.500 → 0.148 / 0.072 / 0.083; AUROC 0.83 / 0.76 / 0.67 | experiments/2026-11-11-emg-toronto/results/tables.md | identical (0.828, 0.755, 0.674) | ✓ |
| 18 | §7.5 | guard AUROC frame-shuffled 0.981, uniform 0.998 | b2t25-trust/results/tables.md (null audit, w_c_trust) | 0.981, 0.998 | ✓ |
| 19 | §7.5 | MEG AUROC 0.92 / 1.00 / 1.00 / 0.47 | experiments/2026-11-11-g1-async-meg-trust/results/null-audit-async.json | 0.916, 1.0, 1.0, 0.472 | ✓ |
| 20 | §7.5 | MEG always commit 85–100% fluent | same file, `policies.commit.*.fluent_rate` | 0.848 – 1.0 | ✓ |
| 21 | Tab. 3 | ours-A exch. ref. 0.018 [0.014, 0.022], p 0.012 | clean_drift_b2t.json `exchangeable_reference` | 0.0182 [0.0135, 0.0221], 0.01199 | ✓ (also my independent code) |
| 22 | Tab. 3 | ours-B 0.0600 [0.049, 0.071], p 0.21 | same, `b2t-ours/chrono` | 0.0600 [0.0491, 0.0712], 0.210 | ✓ |
| 23 | Tab. 3 | sEMG x-session 0.0563, LTT 0.0309, p 0.30 | R1/clean-drift/results/run.log | 0.0563, 0.0309, 0.299 | ✓ |
| 24 | Tab. 3 | Reused 0.0625 / 0.0635 | experiments/2026-11-11-m2-16-online-recal/results/tables.md | 0.0625, 0.0635 | ✓ |
| 25 | §7.7 | aci certificate / a priori 0.043 / 0.068 (ours-A) | R1/clean-drift/results/tables.md | 0.0428 / 0.0682 | ✓ |
| 26 | §7.7 | delay 10 changes online rates by ≤ 0.009 | clean_drift_*.json (max \|d0 − d10\|) | 0.00907 | ✓ |
| 27 | §7.7 | noticed-only aci 0.0527 / 0.0581, certificate 0.0509 / 0.0499 | clean-drift tables.md / clean_drift_emg.json | 0.0527 (cert 0.0509) / 0.0581 (cert 0.0499) | ✓ |
| 28 | §7.3 | published: always commit faster by 0.46–1.47 | R1/user-model/results/tables.md (b2t-published) | 0.46 (sel. ×0.5) … 1.47 (sel. ×2) | ✓ |
| 29 | §7.3 | WC unchanged in 49 of 54 pairs, max 0.059 | user-model-*.json `variants.*.point.trust.wrong_commit` | 43 of 48 non-main unchanged; max 0.0588 | ✗ (wording, m2) |
| 30 | §7.3 | MEG misspecified 1.18 vs refit 2.75 | user-model tables.md (MEG, symmetric p_miss 0.2) | 1.18 / 2.75 | ✓ |
| 31 | §7.3 | gaze + LM glance 3.16 / 4.84 | user-model tables.md | 3.16 / 4.84 | ✓ |
| 32 | §7.3 | MEG fallback 40: [−1.36, −0.89]; fallback 10: [+0.21, +0.45] | user-model tables.md | same | ✓ |
| 33 | Tab. 8 | CRC n = 20: 0.0308, p90 0.089, never 0.17 | R1/smallcal/results/tables.md | 0.0308, 0.0892, 0.17 | ✓ |
| 34 | §7.6 | LTT p90 0.052 / 0.054; CRC p90 0.069 / 0.071 | smallcal tables.md (500 splits) | 0.0515 / 0.0539; 0.0686 / 0.0711 | ✓ |
| 35 | §7.6 | pool risk > α: LTT 0.5% / 1.5%; CRC 33% / 29% | r1-derived.json `splits_m213.*.408` | 0.005 / 0.015; 0.33 / 0.29 | ✓ |
| 36 | §7.6 | session-start CRC 0.009 / 0.025, commit 0.04 / 0.32, 6 of 14 days | smallcal tables.md (per session) | 0.0088 / 0.0252; 0.040 / 0.324; 6 / 14 | ✓ |
| 37 | App. leakage | 22 exact / 310 near; 849 / 910 removed; 295 / 2,895 | R1/leakage/results.md | same | ✓ |
| 38 | App. audit | 1,723 entries; 48/48 and 39/39 | experiments/2026-11-11-m2-09-provenance/results/summary.json; r1-derived.json | 1723; 48 / 189, 39 / 160 | ✓ |
| 39 | §6.2 | 1,718 trials / 15 days; 1,628 used; 90 excluded | R1/fixchecks/results.md | same | ✓ |
| 40 | §4, Discussion | adapters 148 / 412 / 568 lines | `src/fidetype/adapters/*.py` (`wc -l` at HEAD) | **156** / 412 / 568 | ✗ (stale, m15) |

I did not trace: the conformance-suite counts (60 checks, 52 vectors), the ledger timing (0.1 ms, 1.1 kB) and the MEG decoder CERs (0.506 / 0.475). For the CER values, files with these values exist (`experiments/2026-11-09-m1-15-*/metrics-*`, `m1-09` analysis), but I did not check that they come from the same run.

## 7. Top-8 actions

1. **Fix the abstract and the §7.7 / Discussion drift claims (M1).** Remove "never significantly above", and keep the p = 0.012 split. Change "the drift was a data-reuse artefact" to "neither drift nor a reuse effect is distinguishable from split-to-split variation". Add a power statement. [WRITING]
2. **Repeat the deployment protocol over ≥ 50 random fit-A / cal partitions (M5, M1b)** for B2T (both decoders) and sEMG, with reuse vs clean calibration paired by partition. Report the mean test rate, the share > α and the spread for plug-in, pure CRC, max-rule CRC and LTT. This is the experiment that tests the paper's guarantee claim and its data-reuse claim. CPU only, cached decodes. [NEW-EXP]
3. **Mark CRC binding / non-binding** (calibration bound column) and show both splits in Tab. 2. Rewrite §7.2 so that the 0.059 → 0.0245 change is credited to the fit-A refit, not CRC (M2). [WRITING + ANALYSIS]
4. **Make a risk-controlled row (LTT or CRC, clean) the primary safety result**, or label the plug-in headline as having no guarantee and exceeding α (M3). [WRITING]
5. **State the assumptions exactly per device (M4):**
   - MEG: report only sentence-grouped CRC/LTT, and say instance-level CRC on 5 sentences has no guarantee for new sentences;
   - sEMG calib: different decoders for calibration and test;
   - B2T decoder tuned on fit trials that overlap the calibration set (re-tune on fit-A or show it does not matter);
   - MEG checkpoint selected on validation.
   [WRITING + ANALYSIS]
6. **Tighten the inference (M6):**
   - Holm over the Tab. 3 tests;
   - day-level sign or permutation tests next to the 14-cluster bootstrap for the key paired differences;
   - exact upper bounds for zero-event rates;
   - one bootstrap (seed, B) per quantity reused in all tables;
   - say in captions that CIs are conditional on the fitted pipeline and λ.
   [ANALYSIS]
7. **Add Algorithm boxes and full definitions (M7)** for the guard, per-character posteriors, conformal sets, the policy grid and the score s_i, so that a reader can re-implement the layer from the paper. [WRITING]
8. **Correct the stale or inaccurate numbers** (m1 0.66 → 0.65; m2 49/54 → 43/48; m15 148 → 156; m3 the 500 vs 200 split sets). Report the omitted noticed-only excesses (m12) and the rolling-window maxima (m11). Fill or move the 8 TODOs (m16). [WRITING]

## 8. Resolved vs still open, compared with the earlier reviews

I wrote this section last, after reading `round-1-methods.md`, `round-1-domain.md` (headings and majors), `round-1-response.md` (skimmed) and `round-2-changes.md`. I did not use `round-3-editor.md` (a parallel review).

| Earlier item | Status in v2 | Note |
|---|---|---|
| Methods M1 / domain M3: null-input over-claim | **Resolved** | Signal-destroying and intent-mismatch controls are now separate everywhere. |
| Methods M2 / domain M2: commit rate and error among commits | **Resolved** | In Tab. 2 and Tab. 8. A selective-risk controller is still not run; the paper says so. |
| Domain M1: always-offer and plain-threshold baselines | **Resolved** | In Tab. 2, with paired CIs. |
| Methods M3: drift confounded with data reuse | **Partly resolved; the interpretation now goes too far the other way** | The clean protocol was run and reproduces exactly. But v2 says the excess "came from data reuse", which the data do not show (split B 0.0600 ≈ reused 0.0625; sEMG 0.0563). The abstract misstates the p = 0.012 split. Some reuse remains: the B2T decoder grid used fit trials that overlap the calibration set, and the MEG checkpoint was selected on validation. See M1, M4c. |
| Methods M4 / domain M9: over-interpreted guarantees | **Mostly resolved** | Random splits are now called an implementation check. Added: the LTT 90th percentile and pool risk, aci certificates with a-priori bounds, the Tab. 12 footnotes (f ≡ 0, delay, α_max clip, skip mode) and correct guarantee wording. Open: the delay is missing from the appendix wording (m6). The sentence-level exchangeability unit for MEG is not addressed (M4a). |
| Methods M5 / domain M4: user model | **Resolved** | Eight variants, symmetric offers, misspecified user and word completion are reported, and speed is now secondary. |
| Methods M6: inferential language | **Mostly resolved** | "Parity" removed; MEG two-way CI and sEMG participant CIs are primary; "71% higher". Open: few-cluster bootstrap caveats and zero-event bounds (M6). |
| Methods M7 / domain M11: one seed, one split, few clusters | **Open** | MEG seeds are still a TODO. Repeated B2T fit/test assignments were not run. v2 shows why they matter: the plug-in gate gave 0.0245 vs 0.0600 on two fit halves (M5). |
| Methods M8 / domain M7: ablation | **Resolved** | Unified ablation. The guard result is reported, and the reason for keeping the pre-specified configuration is sound. New selective-reporting risk: Tab. 2 shows only CRC split A (M2). |
| Methods M9: published-sentence gate uses our decoder | **Resolved** | §5.2 and the Discussion describe it. |
| Methods M10: primary endpoints, multiplicity | **Partly resolved** | Endpoints are named and their post-hoc timing is disclosed. The Tab. 3 p-values are not corrected for multiplicity (M6.3). |
| Domain M8: leakage | **Resolved** | Appendix G, with a clean-LM re-run. |
| Methods minor 2 (s ≥ λ discretisation) | **Resolved** | "valid and slightly conservative". |
| Methods minor 4 (LTT > CRC explanation) | **Open** | Now visible in Tab. 3 ours-A as well (m5). |
| Methods minor 8–9 (ECE / AUROC CIs) | **Open** | The paper states they were not computed (m10). |
| Methods minor 10 / writing item 10: grids, guard weights, notation | **Partly resolved** | A settings table and a notation table were added. Conformal sets, per-character posteriors and the policy grid are still not specified in the paper (M7). |

**New in v2, not raised before:**

- the false "never significantly above" statement in the abstract (M1);
- the improvement credited to CRC that comes from the fit-A refit, with CRC not binding (M2);
- the plug-in headline under a "risk-controlled" title (M3);
- the different decoders for sEMG-calib calibration and test (M4b);
- the 0.66 → 0.65 rounding (m1) and "49 of 54" (m2);
- the stale adapter line count (m15);
- inconsistent B and seeds across tables (M6.6).
