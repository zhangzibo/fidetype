# Paper 1, draft v0: review round 1 (methods, statistics, writing)

- Reviewer role: demanding peer reviewer. Expertise: statistics, conformal prediction and risk control, ML evaluation methodology, scientific writing.
- Material read: `latex/main.tex`, all `latex/sections/*.tex`, the figure PDFs (rendered to PNG), `src/fidetype/trust/risk_control.py`, `src/fidetype/trust/online_risk.py`, `src/fidetype/interact/simulated_user.py`, and the `results.md` files of `experiments/2026-11-10-b2t25-trust`, `2026-11-11-emg-toronto`, `2026-11-11-m2-13-conformal`, `2026-11-11-m2-16-online-recal`, `2026-11-11-g1-async-meg-trust`, plus `wiki/questions/m1-09-async-full-result.md`.
- No paper file was edited.
- Tags used below: **[NEW-EXP]** = needs a new run (with a rough cost); **[ANALYSIS]** = re-analysis of results that already exist in the repo; **[WRITING]** = text, tables or figures only.

---

## 1. Summary of the submission

The paper proposes (i) NeuralTextStream (NTS), a per-frame output format for neural text-entry decoders, and (ii) a trust layer that reads only NTS. The layer calibrates confidence with temperatures, filters candidates with a neural-evidence guard, and chooses commit / offer / abstain. It sets the commit threshold with conformal risk control (CRC) or Learn-then-Test (LTT), and re-tunes that threshold online (window CRC, decayed CRC, ACI on the threshold, ACI on the level). A hash-chained ledger records decisions. The layer is tested on public data from three device types: MEG typing (SpanishBCBL, 19 participants, 17 unique test sentences), intracortical speech (Brain-to-Text '25, one participant) and forearm sEMG (Toronto, 19 participants, composed sentences). Speed is measured as eWPM of a simulated gaze-typing user. The main claims: wrong commits drop from 0.54–0.997 to at most 0.059; CRC brings the mean wrong-commit rate to about 0.048; online methods keep it near 0.05 under "within-session drift"; null inputs produce no commits; MEG reaches "parity" with gaze typing.

The engineering is careful and the paper is unusually honest about its negative results (MEG commits nothing; the null audit on MEG is uninformative; the guard does not help on B2T). The code that implements CRC, LTT and ACI is correct in the places I checked (Section 6). The weaknesses are in (a) how the guarantees are stated and what the experiments actually test, (b) a data-reuse confound in the drift experiment, (c) the choice of risk measure, (d) the heavy dependence of every speed claim on an unvalidated, structurally asymmetric user model, and (e) inferential language ("parity", "no measurable cost", "committed no text from null input") that the statistics do not support. The prose is accurate but telegraphic and reads like an internal report in places.

## 2. Recommendation

**Major revision.** Reasons:

1. The central statistical claim about drift (offline CRC fails, online methods restore control) is confounded: the offline CRC calibration set is the same fit half that was used to fit the temperatures and the policy grid (Major 3). This must be resolved before the drift result can be published.
2. The headline safety metric, the marginal wrong-commit rate P(commit and wrong), can be made small by not committing. Without the commit rate and the error rate among commits next to it, the reader cannot tell safety from abstention. Under CRC on our B2T decoder, about one in four commits is still wrong (0.048 / 0.194) (Major 2).
3. Two claims in the abstract are contradicted by the paper's own results: "committed no text from null input" (the other-sentence control was committed at 22 %) and "parity with gaze typing" (a non-significant difference is not equivalence; the result reverses under two plausible user-model settings that the repo already contains) (Majors 1, 5, 6).
4. The guarantees are mostly stated correctly in Section 4, but the Results and figure captions over-interpret them (LTT "controls the tail"; `aci` "sat at the target, as its bound predicts"), and the random-split CRC experiment is presented as evidence when it is, by the CRC theorem, an implementation check (Major 4).

None of this is fatal. Most fixes are analysis or writing. Three need cheap CPU re-runs (Majors 3, 5, 8). Seeds and more MEG test sentences need GPU time (Major 7).

---

## 3. MAJOR issues

### Major 1. The abstract's null-input claim contradicts the results  [WRITING]
- **Location:** Abstract ("it committed no text from null input"); Sec. 5.4 (Controls) lists "the real stream of a different sentence" among the null streams; Sec. 6.5 ("The trust layer committed 0% of null inputs on all three devices" then "One control it cannot pass ... committed 22% of items").
- **Why:** By the paper's own definition, the other-sentence stream is a null input, and the layer committed 22 % of them on B2T and "as often as for real input" on sEMG. On MEG the 0 % is a closed gate, not a detection result (the paper says so in 6.5, but the abstract counts it as a success).
- **Fix:** Split the controls into two named classes and use the names everywhere. (a) *Signal-destroying controls* (frame-shuffled, uniform, zero-input, permuted-label decoder): no commits on B2T and sEMG, where the layer does commit on real input. (b) *Intent-mismatch control* (real stream of another sentence): not detectable by a stream-only layer; committed at the real-input rate. Abstract: "...committed no text from signal-free streams on the two devices where it commits real text; it cannot detect a real stream of a different intended sentence."

### Major 2. The risk measure hides how many commits are wrong; report commit rate and error-among-commits  [ANALYSIS; optional NEW-EXP]
- **Location:** Abstract, Fig. 1, Table 4 (`tab:main`), Sec. 6.2, Sec. 6.6, Discussion "How to state the guarantees".
- **Why:** The controlled quantity is the marginal rate R(λ) = P(commit ∧ wrong). It is driven to 0 by never committing (MEG; sEMG cross-subject). The user-facing quantity is the conditional error P(wrong | commit), the false-commit proportion. From the repo's numbers:

  | condition | wrong-commit (marginal) | commit rate | wrong among commits |
  |---|---|---|---|
  | B2T ours, plug-in | 0.059 | 0.23 | ≈ 0.25 |
  | B2T ours, CRC (n_cal 408) | 0.0483 | 0.194 | ≈ 0.25 |
  | B2T ours, LTT | 0.0345 | 0.156 | ≈ 0.22 |
  | B2T published gate, plug-in | 0.044 | 0.471 | ≈ 0.09 |
  | MEG, CRC | 0.0193 | 0.021 | ≈ 0.92 (almost all commits wrong) |

  A reader who sees "wrong-commit 0.048" will think 5 % of committed sentences are wrong. On our B2T decoder it is about 25 %. On MEG under CRC it is about 92 %. The MEG CRC row shows the problem directly: marginal risk control "spends the budget" on commits that are nearly always wrong. Both quantities are legitimate, but the paper must say which one it controls and show the other.
- **Fix:**
  1. Add "commit rate" and "error among commits" columns to Table 4 and Table `tab:crc`, and add commit rate to the Fig. 1 caption, or replace Fig. 1 with commit rate on the x-axis and error among commits on the y-axis, with eWPM as a third panel. [ANALYSIS]
  2. In Sec. 4.4, define R(λ) explicitly as P(s ≥ λ, top-1 wrong) and say in one sentence why it was chosen (it is monotone in λ, so CRC applies; selective risk is not monotone).
  3. Optional [NEW-EXP, CPU, minutes]: also control the selective risk P(wrong | commit) ≤ α′ with LTT. The hypothesis H0: R_sel(λ) > α′ can be tested with a binomial p-value conditional on the number of commits, and fixed-sequence testing still gives FWER control. This would answer the obvious reviewer question "why should the user accept 25 % wrong commits?".
  4. Remove the MEG CRC row from the "success" narrative. It is the clearest example of control without utility. Say that `max(λ_tuned, λ_CRC)` is the deployable rule, because it avoids these commits.

### Major 3. The offline-CRC "drift" failure is confounded with data reuse; the order is assumed, not known  [NEW-EXP, CPU, < 1 h; WRITING]
- **Location:** Sec. 4.4 ("The other parts of the pipeline ... are fitted on separate data"); Sec. 6.6 / `tab:drift` ("offline CRC gave 0.0625"); `fig:drift`; abstract ("offline calibration gave 0.0625–0.0635").
- **Why:**
  - In `experiments/2026-11-10-b2t25-trust/results.md` the B2T fit is "`TrustPipeline.fit(fit, fit)`: frame T and sentence T on the first half of `fit`, conformal on the second half, policy on all of `fit`". The M2-13 "one-shot" and M2-16 drift protocols then calibrate offline CRC on that same 812-trial fit half. CRC needs calibration data that played no role in fitting the score function or the other gating rules. Here the temperatures that produce p̂_top1 and the guard/offer thresholds that decide which items get s_i = −∞ were all fit on the calibration data. In-sample temperatures make the fit-half scores look better calibrated than test scores, and that alone can push the test rate above α.
  - For sEMG the drift row uses "offline CRC (pure, n = 285)" = all of fit-half B, and half B is also the policy-grid data (`emg-toronto/results.md`, "Trust fit"). The same confound applies.
  - The paper's own "shuffled order" control (`m2-16-online-recal/results.md`) gives offline CRC 0.0625 with the test order randomised. So the failure is not temporal drift *within* the test stream. It is a level difference between the calibration set and the test set. That difference may be a between-half shift, a reuse effect, or both. The paper calls it "within-session drift" and "time order".
  - The B2T file has no trial time stamps. `m2-16-online-recal/results.md` says "we assume the file order is the trial order". The paper says "in time order" without this caveat.
  - Sec. 4.4 states that the other parts are fitted on separate data. For the drift experiment that statement is false.
- **Fix:**
  1. [NEW-EXP] Re-run the offline-CRC baseline with a clean split: divide the fit half into fit-A (temperatures, conformal sets, guard, policy grid) and fit-B (CRC calibration only), for example by alternating trials within each day. Report offline CRC on the test half again. If it still exceeds α, the shift claim stands. If not, the drift narrative must change. Do the same for sEMG (calibrate on the 142-sentence half of B that the grid did not use; that split already exists for the M6-07 CRC rows).
  2. [WRITING] Rename the phenomenon to what was measured: "a shift between the first and second half of each recording day". Add the shuffled-order control to `tab:drift` as a row, because it is the experiment that identifies the shift as a level change.
  3. [WRITING] Add "trial order is taken from the file order; the data has no time stamps" to Sec. 5.3 and to the `fig:drift` caption.
  4. [WRITING] The MEG row of `tab:drift` concatenates participants ("participant order"). That is a between-participant sequence, not a session. Move it to a footnote or label it accordingly.

### Major 4. The guarantees are stated correctly in Sec. 4 but over-interpreted in Sec. 6 and in captions  [WRITING; ANALYSIS]
- **Location:** Sec. 6.6 and `fig:crc` caption ("CRC controls the mean, LTT also the tail"); Sec. 6.7 ("`aci` sat at the target (0.0502 and 0.0526), as its bound predicts"); `tab:online`; `fig:online` caption; Discussion "How to state the guarantees".
- **Why, point by point:**
  - **The random-split CRC experiment is an implementation check, not evidence.** A random split of a fixed pool of 816 trials is exchangeable *conditional on the pool*. The CRC theorem therefore guarantees that the mean over all splits is ≤ α for this pool. A mean of 0.0483 confirms that the code is right. It says nothing about new sessions, days or users. The ± se over 200 overlapping splits also ignores the variation of the pool itself. Say this explicitly. The informative contrasts are the plug-in rule (0.0586, above α in 86 % of splits) and the non-exchangeable deployment case.
  - **LTT is about the population risk R(λ̂), not the realised test-split rate.** LTT gives P(R(λ̂) ≤ α) ≥ 1 − δ = 0.9 over calibration draws. The paper reports the 95th percentile of the *empirical* rate on a 408-item test part. That quantity mixes calibration randomness with test-sampling noise (se about 0.011 at n_test 408, as `m2-13-conformal/results.md` notes). So "LTT also controls the tail" is not what the figure shows. 14 % of LTT splits exceed α, which is more than δ = 0.1. That is not a violation, but a reader will think it is. Fixes: (a) report the 90th percentile, not the 95th, because δ = 0.1; (b) estimate the calibration-conditional risk R(λ̂) for each split on the full complement or on a large held-out pool, and plot its distribution; (c) state in one sentence why the empirical share can exceed δ. [ANALYSIS]
  - **The `aci` bound is an upper bound, not a prediction of "at target".** ACI tends to α because the update equalises the average loss with α. The bound only limits the excess. Also, 0.0526 on sEMG is above α. The a-priori bound at T = 816, η = 0.05 is α + (1 − λ_1 + η)/(ηT) ≈ 0.064 (`prior 0.0637` in `m2-16-online-recal/results.md`). That is *weaker* than the 0.0625 that offline CRC achieved. The realised certificate (0.0502) is computed after the fact. The paper should print both numbers. Without them, "a long-run bound for any sequence" sounds stronger than it is at this T.
  - **Assumptions missing from `tab:online`:** (i) the `aci` bound is useful only if λ_t stays bounded, which needs scores ≤ 1 and non-commit loss f = 0 (with OFFER_WORDS, f can be 1 and λ may not be bounded); (ii) with feedback delay d the a-priori slack grows to η(1 + d) (the code's `prior_bound` has this; the paper does not); (iii) the code clips α_t at α_max = 2α for `aci_window`, which the paper's update rule omits (the clip keeps the bound valid, but the reported rule should match the code); (iv) with `missing="skip"` the bound covers only items whose feedback arrived.
  - **Window and decay methods** are described as "approximate". Say what the approximation is: the Barber et al. / Farinhas et al. bound α + Σ w̃_i d_TV(Z, Z^(i)), which is not computable. In practice these methods have no guarantee under drift. The paper treats them as alternatives of equal standing in the abstract range "0.040–0.053".
  - **Discussion, guarantee wording.** "the expected wrong-commit rate is at most 0.05 for this user in this session" reads as conditional on the session. CRC is marginal over the calibration draw and the new item. Suggested wording in Section 5, passage W9.
- **Fix:** Rewrite the captions and the Discussion paragraph (Section 5 gives text). Add the certificate and a-priori bound columns to `tab:drift`. Report the LTT 90th percentile and, if feasible, the conditional risk. Add the four assumptions to `tab:online` as a footnote.

### Major 5. Every speed claim depends on an unvalidated and asymmetric user model; the repo already shows reversals  [ANALYSIS + NEW-EXP, CPU, a few hours]
- **Location:** Sec. 5.1–5.2, App. A, Sec. 6.2, abstract, Discussion; TODO G6.
- **Why:**
  - **Asymmetry that favours the trust layer.** In `simulated_user.py`, under OFFER "the user looks at the candidates on purpose here, so the error is always seen", and the choice between fix, repeat and full retype is the minimum of the *true* costs ("a rational user who can judge the cost after reading"). Under COMMIT, each wrong unflagged word is missed with p_miss_unflagged = 0.05 and becomes a silent error that lowers the correct-word count. So the model gives offers a perfect, cost-optimal user and gives commits a fallible one. That asymmetry is defensible as a hypothesis, but it is not measured, and it decides the comparison.
  - **The repo already shows that it decides the comparison.** In `g1-async-meg-trust/results.md` (user-model sensitivity, async MEG): with p_miss_unflagged = 0, always-commit gives 3.24 eWPM and trust gives 3.20. The "+0.62 over always-commit" therefore comes entirely from an unmeasured parameter. With a 40 cpm fallback (the measured field user FP1 in Cai et al.), gaze typing beats trust (6.31 vs 5.15). With slow selection, gaze beats trust (3.15 vs 3.00; CI over sentences [−0.23, −0.08]). Only the 40 cpm case reaches the paper (Limitations item 6).
  - **On MEG the "trust layer" is an always-offer policy** (OFFER rate 1.00, `g1` results). Its eWPM is the eWPM of the offer model, not of any trust decision.
  - **Circularity.** The policy thresholds are tuned to maximise eWPM under the same simulated user that scores them. The sensitivity runs refit per variant. That measures best-case performance under each model, not robustness to a wrong model.
  - **Construct validity.** The MEG and sEMG neural inputs need overt motor typing (152 and 75.8 characters per minute by healthy typists). The fallback and selection costs are those of an eye-gaze user with ALS. No real user has both. Say this plainly, as the code docstring already does ("the model mixes the decoder's input rate with the fallback rate of the target users").
- **Fix:**
  1. [ANALYSIS] Move the existing MEG sensitivity table (`g1`, "User-model sensitivity") into the main paper or the appendix, and cite it where "parity" and "+0.62 over always-commit" appear.
  2. [NEW-EXP, CPU] Run G6 on B2T and sEMG with the same grid (fallback 10/20/40 cpm; selection ×0.5/×2; p_miss_unflagged 0/0.05/0.2), *and* a symmetric variant where offers also have a miss probability and a non-oracle retype rule (for example, always fix the closest candidate).
  3. [NEW-EXP, CPU] Evaluate a misspecified user: fit the policy under `aac_gaze()` and score it under each variant without refitting. Report the policy ranking (trust vs always-commit vs gaze-only) under each.
  4. [WRITING] State the construct-validity caveat in Sec. 5.2 and in the abstract ("a simulated user that pairs each device's input rate with the costs of an eye-gaze typist").

### Major 6. Inferential language is stronger than the statistics  [ANALYSIS + WRITING]
- **Location:** Abstract ("no measurable speed cost", "reached parity"); Sec. 6.2 ("this is parity, not a gain"); Limitations 4; Discussion ("roughly doubled").
- **Why and fix:**
  - **"Parity" is an equivalence claim.** A CI that contains 0 does not show equivalence. Equivalence needs a margin set in advance (for example ±10 % of gaze eWPM) and a TOST or a CI contained in the margin. With the margin ±0.32 eWPM (10 %), the sentence CI [−0.04, +0.15] and even the two-way CI [−0.11, +0.26] are inside it, so the claim can be rescued, but only with a stated margin. The repo's G1 results call the two-way CI "the honest one for trust vs gaze". The paper reports only the sentence and participant CIs. Report the two-way CI as primary for MEG. Per participant, 10 of 19 above gaze is a sign-test p ≈ 1; it supports "no difference", not "parity".
  - **"No measurable speed cost"** on B2T rests on a trial-level CI of [−0.11, +0.30] eWPM. Say what the CI excludes: "the 95 % CI excludes a slowdown larger than 0.11 eWPM (1 %)". Also give the day-cluster CI of the paired difference, which exists in `b2t25-trust/results/tables.md`. Trials within a day are correlated.
  - **sEMG sentence-level CIs overstate independence.** The 551 test sentences are composed from a limited pool of real press windows per participant ("30 test sentences from the later recordings" of each letter), so windows are reused across sentences. The participant cluster is the honest unit. The repo shows that the cross-session trust − gaze difference is significant over sentences ([+0.26, +0.56]) but not over participants ([−0.04, +0.96]). Make participant CIs primary for sEMG.
  - **"Roughly doubled"** (8.02 vs 4.68) is a factor of 1.71. Say "71 % higher".
  - **MEG CER intervals** are still over instances, with the "0.495 ± 0.020 SEM over participants" mixed in. Use sentence-cluster CIs (G3) or drop the intervals.

### Major 7. One seed, one split, one implant participant, 17 MEG sentences: the uncertainty that matters is not in any interval  [NEW-EXP, GPU]
- **Location:** Sec. 5.5, Limitations 1, 2, 10; TODOs G2, G7, G8.
- **Why:** All intervals are over test items, sentences or participants with one trained decoder and one fit/test split. For the MEG decoder, the selection between the r4b and r5 schedules was reported on test ("A longer training schedule did not help (r5 minus r4b ...)"); `m1-09-async-full-result.md` shows that the two were equal on validation and r4b was kept after the test result was known. That is mild test-set selection.
- **Fix:** (1) At least 3 decoder seeds for MEG and sEMG; report the seed SD next to every headline number. (2) Repeat the B2T fit/test split with several within-day assignments (for example, alternate halves). (3) K-fold over MEG sentence hashes (G8) so that the test set covers more than 17 sentences. (4) [WRITING] State the model-selection rule (validation CER) and report r5 only as a validation-equal alternative, not as a test comparison.

### Major 8. The ablation section is incomplete, and one omitted result changes a Discussion claim  [ANALYSIS + NEW-EXP, CPU]
- **Location:** Sec. 6.9; Discussion "A trust layer makes a fixed decoder safer, not faster".
- **Why:**
  - In `emg-toronto/results.md`, cross-subject "(d) trust, no calibration" gives 4.76 eWPM, above gaze typing (4.27), and its CER is lower (0.369 vs 0.479). Calibrated trust gives 4.08, below gaze. So the frame temperature changes the beam-search output, not only the confidence. "Calibration" in the ablation therefore confounds two effects: decoding quality and confidence quality. The Discussion's claim that the weak cross-subject decoder "stayed at or below gaze typing" holds only for the calibrated variant.
  - On B2T the guard *increases* wrong commits (0.059 with guard vs 0.036 without, at the same eWPM). The paper mentions this in one clause. The guard is a named contribution, so the reader needs to know when it helps (MEG low-evidence, published gate) and when it hurts.
- **Fix:** [NEW-EXP] The unified ablation table (G5), with "temperature applied to the beam" and "temperature applied only to the confidence" as two separate rows. [WRITING] Report the cross-subject no-calibration result and correct the Discussion.

### Major 9. The "black-box gate" on the published decoder uses our own decoder  [WRITING]
- **Location:** Contribution 2; Sec. 6.2; Discussion "Strong decoders still need a gate".
- **Why:** In `b2t25-trust/results.md` the gate puts the published sentence on top of *our* 10-best (score = our best + 2.0) and gives each published word the acoustic confidence of the aligned word in *our* top-1. So the gate needs a second decoder that runs on the stream. "This gate needed only the stream and the text" is true for the inputs, but the method also needs a reference decoder with its own lexicon and LM.
- **Fix:** Describe the construction in Sec. 4.2 in two sentences. In the Discussion, say "needed only the stream, the text and a light reference decoder, not the vendor's weights".

### Major 10. No primary endpoints; many uncorrected comparisons  [WRITING]
- **Location:** Sec. 5.5 and throughout.
- **Why:** The paper reports more than 50 intervals over 3 devices × several conditions × several policies × several methods, with no designated primary outcome and no multiplicity statement. Some choices were made after the first runs (for example, the "noticed-only" rows and the headline choice of `aci_window` in the abstract, whose range 0.048–0.049 is the best of four methods).
- **Fix:** Name two primary endpoints per device (wrong-commit rate of trust; eWPM difference trust − gaze), state that all other intervals are descriptive, and give the four online methods equal weight in the abstract ("0.048–0.053", not "0.048–0.049"). State which settings were fixed before which runs (the configs record this; say it in Sec. 5).

---

## 4. MINOR issues

1. **CRC loss definition (Sec. 4.4).** The sentence "made monotone in λ by taking max(c_i, f_i)" is hard to parse. Write the loss as one equation (passage W6).
2. **Commit rule and discretisation.** The paper's CRC formula uses an infimum over a continuum; the code commits on s ≥ λ and takes the minimum over unique calibration scores ∪ {+∞}. This is valid and slightly conservative (the docstring explains why), but the paper should say it in one sentence, because CRC's theorem assumes a right-continuous loss and "s ≥ λ" gives a left-continuous one.
3. **Infeasible case.** CRC's theorem needs L_i(λ_max) ≤ α. At λ = +∞ the loss is f_i, which can be 1 with OFFER_WORDS. The paper says "f_i ... 0 here"; add that the guarantee needs f ≡ 0 (or mean f ≤ α) when the result is "never commit".
4. **LTT vs CRC on MEG.** LTT has a higher mean (0.0214) than CRC (0.0193). The reason is that LTT tests a fixed grid down to λ = 0, while CRC only considers calibration scores, so test items scoring below the lowest calibration score commit under LTT but not under CRC. One sentence avoids a reader's suspicion of a bug.
5. **Decay method.** "We use N = 200, ρ = 0.99" suggests that the decay method is also windowed. The config uses no window cap for `decay`. Clarify.
6. **CRC calibration size vs per-session use.** The Discussion recommends a short session-start calibration block as the CRC calibration set. CRC needs n ≥ 19 to commit at all, B2T days have 22–37 test trials, and the drift result shows that an early-session block did not transfer to the later half of the same day. Either qualify the recommendation or link it to the online methods.
7. **Temperature fitting.** "minimising the negative log-likelihood of the truth" for CTC frames: say that this is the CTC loss, on which data, with which optimiser and bounds. Say how T_s is fitted.
8. **ECE.** Give the binning (number and type of bins). With a few hundred sentences, ECE is noisy; give a bootstrap CI or a reliability diagram (TODO F5).
9. **AUROC values** (0.797, 0.884, 0.844; sEMG 0.83/0.76/0.67) have no CIs.
10. **Guard weights and grids.** "the maximum of the two weighted signals" and "a small grid" are not reproducible. Put the weights and the grids in an appendix table.
11. **eWPM definition.** "Correct words in the final text" needs a formula (n − word edit distance, clipped at 0, as in the code) and the ratio-of-sums form.
12. **Gaze-only baseline** is an error-free typist with no reading, verification or correction time. State this; it slightly favours gaze typing, which partly offsets Major 5.
13. **sEMG LM match.** Test sentences come from held-out Tatoeba sentences and the LM is trained on other Tatoeba sentences. Same corpus, same style. This favours LM-heavy decoding. Mention it next to the composed-sentence limitation.
14. **B2T leakage.** "One sentence occurs in both" fit and test (b2t25 results) and 64 cue sentences occur in Tatoeba. Report the result without these (G9) or quantify the effect.
15. **MEG validation set** has only 11 sentences, and all trust components are fit on it. Say so in Sec. 5.3.
16. **Silent-error rate** should have a CI wherever it is used as a budget (Discussion suggests running ACI at α − silent rate).
17. **Short-window comparison.** "as for an i.i.d. Bernoulli(0.05) sequence (median 0.120)" is a good reference. Give its 95th percentile (0.180) too, so the reader sees that the observed 0.10–0.12 is typical, not extreme.
18. **Fig. 1** has a different x-range per panel; the MEG panel's gaze line and trust marker overlap. Use a shared y-axis label and annotate "commits 0 %" on the MEG trust marker.
19. **`fig:drift` (b)** omits the MEG row that `tab:drift` contains, and has no uncertainty. Add day-cluster bars or state that the values are single runs.
20. **`tab:crc`** caption says "408 calibration trials" for MEG, where the units are instances and n_test is 229, not 408. State n_test per row.
21. **Ledger "found the same wrong commits as the harness"** is a consistency check of the replay, not a detection result (the corrections are oracle ground truth). Say "recorded", not "found".
22. **Ethics.** SpanishBCBL is CC BY-NC; you train a decoder on it and release code under Apache-2.0. Say that the released code contains no SpanishBCBL-derived weights (Table 9 implies this, but say it in the availability statement).
23. **Contribution count.** Six contributions in one paper dilutes the message. Consider merging 4 (ledger) and 6 (release) into the format/layer contributions.

---

## 5. Writing

### 5.1 General assessment

- **Register.** The draft follows the repo's ASD-STE100 house style: short declarative sentences, many semicolon lists, almost no connectives. The result is precise but choppy. A journal reader needs topic sentences that say why a paragraph exists, and transitions that say how it relates to the previous one. Results paragraphs are strings of numbers (6.1 has 14 numbers in 8 sentences).
- **Internal jargon.** Internal codes leak into the paper: M1-09, M1-15, r4b, r5, r4a, "80 cached blocks", G-numbers in TODOs, "medium" model, `UserConfig.aac_gaze()`, module paths. Replace with descriptive names ("our asynchronous decoder", "the synchronous control decoder with oracle key times") and keep code identifiers for the availability section.
- **Notation clashes.** T = number of frames (Sec. 3), number of items in a session (Sec. 4.5) and, as T_f / T_s, temperatures. n = n-best size (n = 10) and calibration size. k = offer size and the Hick–Hyman argument. Fix: frames F (or T_frames), session length T, temperatures τ_f, τ_s, n-best size K, offer size k, calibration size n.
- **Terminology drift.** One concept, one word:
  - test unit: "item" (generic), "trial" (B2T), "instance" (MEG), "sentence" (sEMG) are used interchangeably; e.g. MEG is "trials" in Sec. 6.6 and "instances" in Table 2.
  - policy: "trust", "trust layer", "trust gate", "gate", "plug-in gate", "old gate" (repo), "trust policy". Define *trust policy (plug-in)*, *trust policy + CRC*, *trust policy + LTT*, *gate on the published sentence* once and reuse.
  - "session-calibrated" vs "session-cal."; "Brain-to-Text '25" vs "B2T '25"; "NTS" vs "NeuralTextStream"; "COMMIT" (code) vs small-caps commit (paper); "eWPM" vs "words per minute" (abstract).
- **Headings.** Claim-style subsection headings in Results are good. Two of them over-claim: "Conformal risk control fixes the mean wrong-commit rate" (it guarantees it, under exchangeability, which the experiment satisfies by construction) and "Online re-calibration restores the target under drift" (`aci` gave 0.0526 on sEMG).
- **Intro motivation.** The first paragraph motivates the problem well. The three "gap" paragraphs are good in structure, but the second gap ends in a TODO for the two closest works, so the novelty claim is currently unsupported. The intro never states the *problem formulation* (what an item is, what an action is, what a wrong commit is, what the user pays). A short "Problem setting" subsection at the start of Sec. 4 would fix the piecemeal notation.
- **Abstract.** About 250 words and about 18 numbers, three ranges. It is accurate in most places but reads as a list. It contains the null-input over-claim (Major 1) and "parity" (Major 6). A rewrite is in W1.
- **Discussion.** It is the strongest section in voice. Two paragraphs over-claim (W10, and "worth more than any downstream policy").

### 5.2 Quoted passages and proposed rewrites

**W1. Abstract (whole).**
> Original (excerpt): "The layer reduced the wrong-commit rate from 0.610 to 0.059 on intracortical speech with no measurable speed cost, from 0.54--0.96 to at most 0.004 on EMG, and from 0.997 to 0 on MEG, and it committed no text from null input. Conformal risk control brought the mean wrong-commit rate to 0.046--0.048 (target 0.05). Under drift, online re-calibration held it at 0.048--0.049, where offline calibration gave 0.0625--0.0635. On MEG, where the decoder almost never proposed the right sentence, the layer committed nothing, and the system only reached parity with gaze typing (difference $+0.05$ words per minute, 95\% CI over sentences $[-0.04, +0.15]$)."

> Proposed: "Neural text-entry decoders, from non-invasive magnetoencephalography (MEG) to intracortical arrays and forearm electromyography (EMG), now produce fluent text, but they rarely signal when that text is wrong, and each reports confidence in its own format. We present Fidetype, an open stream format for per-frame decoder output (NeuralTextStream) and a decoder-agnostic trust layer that reads only this stream. The layer calibrates confidence, decides whether to commit a sentence, offer alternatives or abstain, and sets its commit threshold with conformal risk control so that the expected rate of wrong commits stays below a target; an online variant re-tunes the threshold from user corrections. We apply the same layer, unchanged, to public data from three device types and score it with a simulated eye-gaze user against a gaze-typing baseline. On intracortical speech (one participant), the layer cut wrong commits from 61% to 6% of sentences without slowing the user (95% CI of the speed change: −1% to +3%); on sEMG (19 participants) it cut them from 54–96% to under 1%. Conformal calibration held the mean wrong-commit rate at 0.048 for a target of 0.05, and online re-calibration held it at 0.045–0.053 where a threshold calibrated earlier in the day reached 0.063. On MEG the decoder almost never ranked the right sentence first, so the layer committed nothing; speed was indistinguishable from gaze typing. The layer committed no text from signal-free streams, but, reading only the stream, it cannot detect a real signal for a different intended sentence."

Why: one claim per sentence, every number tied to a unit, no "parity", the null-input claim qualified, the user model named as simulated. (Adjust the drift numbers after Major 3.)

**W2. Introduction, paragraph 1, the motivating claim.**
> Original: "This stage improves the error rate, but it also makes wrong output look right: a fluent wrong sentence is harder to notice than a garbled one, as known from automatic speech recognition \citep{koenecke2024careless}. For a user who depends on the interface to communicate, a wrong sentence that is committed and sent costs more than a slow one."

> Proposed: "This stage lowers the error rate, but it changes the kind of error: when the neural evidence is weak, the language model still returns a grammatical sentence. In speech recognition, such fluent but unsupported output has caused documented harm \citep{koenecke2024careless}, because a reader has no cue that it is wrong. For a person who depends on the interface to communicate, a wrong sentence that is sent in their name can cost more than a slow one."

Why: the original attributes a perceptual claim ("harder to notice") to a source that documents harm from hallucination; "as known from" is vague; the rewrite keeps the claim inside what the citation supports.

**W3. Introduction, gap 2.**
> Original: "We know of no layer that works across device types, decides between committing, offering alternatives and abstaining, and states a finite-sample bound on how often it commits wrong text."

> Proposed: "What is missing is a decision rule that is independent of the decoder: one that chooses between committing, offering alternatives and abstaining, and that comes with a finite-sample bound on how often it commits wrong text. Such a rule must work on any device whose decoder exposes per-frame probabilities."

Why: states the gap as a property of the needed solution rather than as the authors' knowledge, which reviewers can always contest; and only after the closest work (G10) is positioned.

**W4. Contribution 3.**
> Original: "\textbf{Finite-sample and drift-robust wrong-commit control}: conformal risk control (CRC) and Learn-then-Test (LTT) for the commit threshold \citep{...}, and an online controller that re-calibrates from user feedback, with a long-run bound that holds for any sequence of items for two of its variants \citep{...}."

> Proposed: "\textbf{Wrong-commit control with stated guarantees.} We set the commit threshold with conformal risk control (expected-risk bound under exchangeability) or Learn-then-Test (high-probability bound), and we re-tune it online from user corrections with adaptive conformal updates, which bound the long-run average of the observed wrong-commit rate for any sequence of sentences."

Why: "drift-robust" over-claims (silent errors and short windows are not covered); naming the type of each guarantee in the contribution list prevents the over-reading that Major 4 describes.

**W5. Sec. 3, "Honest probabilities".**
> Original: "\paragraph{Honest probabilities.} A producer must emit the decoder's own output and must not sharpen or smooth the probabilities for display; calibration is the consumer's job. A number is a probability only if the stream says so."

> Proposed: "\paragraph{Unmodified probabilities.} A producer must emit the decoder's own output distribution and must not sharpen or smooth it, for example for display. Calibration is left to the consumer, which can fit it on data with known truth. A field is interpreted as a probability only if the stream declares it as one in \code{calibration.*}."

Why: "honest" is a moral word with no technical meaning; the rewrite says what the rule is, why it exists and where the declaration lives.

**W6. Sec. 4.4, loss definition.**
> Original: "Let $s_i$ be the score of item $i$ ($\hat p_{\mathrm{top1}}$ if the other policy rules allow a commit, else $-\infty$) and $\lambda$ the commit threshold. The loss is $L_i(\lambda) = c_i$ if $s_i \ge \lambda$ (with $c_i = 1$ if the top candidate is wrong) and $f_i$ otherwise (the loss of the non-commit action, 0 here), made monotone in $\lambda$ by taking $\max(c_i, f_i)$."

> Proposed: "For item $i$, let $c_i \in \{0,1\}$ indicate that the top candidate is wrong, and let $f_i \in \{0,1\}$ be the wrong-commit loss of the action taken when the layer does not commit ($f_i = 0$ for \act{offer} and \act{abstain}; \act{offer\_words} can have $f_i = 1$). The commit score $s_i$ is the calibrated $\hat p_{\mathrm{top1}}$ when the guard and the other rules allow a commit, and $-\infty$ otherwise. The layer commits when $s_i \ge \lambda$, and we use the loss
\[ L_i(\lambda) = \max(c_i, f_i)\,\mathbb{1}[s_i \ge \lambda] + f_i\,\mathbb{1}[s_i < \lambda], \]
which upper-bounds the true loss and is non-increasing in $\lambda$, as conformal risk control requires. The controlled risk is $R(\lambda) = \mathbb{E}[L(\lambda)]$; with $f \equiv 0$, it is the probability that a sentence is committed \emph{and} wrong."

Why: one equation replaces three parentheticals; it states the commit rule (≥), the monotonicity argument and the meaning of the risk (Major 2).

**W7. Sec. 4.4, combining thresholds.**
> Original: "Any threshold above $\hat\lambda$ keeps the guarantee, so the layer can combine CRC with the \ewpm{}-tuned threshold as $\hat\lambda = \max(\lambda_{\mathrm{tuned}}, \hat\lambda_{\mathrm{CRC}})$. The other parts of the pipeline (temperatures, guard, other thresholds) are fitted on separate data."

> Proposed: "Because $L_i$ is non-increasing in $\lambda$, any threshold at or above $\hat\lambda_{\mathrm{CRC}}$ has a loss no larger than that of $\hat\lambda_{\mathrm{CRC}}$ on every item, so the bound still holds even if the larger threshold is chosen on the same calibration data. We therefore deploy $\max(\lambda_{\mathrm{tuned}}, \hat\lambda_{\mathrm{CRC}})$, where $\lambda_{\mathrm{tuned}}$ maximises \ewpm{}. The guarantee also requires that the temperatures, the guard and the other policy thresholds be fitted on data disjoint from the calibration set; \cref{sec:protocol} lists the split used for each experiment."

Why: gives the actual reason (pointwise dominance), and turns the "separate data" sentence into a checkable commitment (Major 3).

**W8. Sec. 6.1, decoder paragraph.**
> Original: "On the 11 test sentences with no close training variant, CER was 0.519 (greedy) and 0.492 (beam + LM), so near-variant sentences changed the headline by about 0.013 and 0.017. A longer training schedule did not help (r5 minus r4b, greedy $+0.009$ \ci{+0.003}{+0.015})."

> Proposed: "Six of the 17 test sentences have a close variant in the training set. Excluding them raised the CER only slightly, to 0.519 (greedy) and 0.492 (beam search with LM), so memorisation of near variants explains at most 0.02 of the reported CER. We selected the training schedule on validation CER; a longer schedule gave the same validation CER and is not reported further."

Why: removes internal codes and the word "headline"; says what the check rules out; avoids presenting a test-set model comparison (Major 7).

**W9. Discussion, "How to state the guarantees".**
> Original: "With CRC: ``the expected wrong-commit rate is at most 0.05 for this user in this session, given $n$ calibration sentences, if the session does not drift''; individual sessions can exceed it. With LTT: ``with probability at least 0.9, the wrong-commit rate is at most 0.05''. With online re-calibration: ``the average wrong-commit rate over the $T$ items of this session is at most 0.05 plus a term of order $1/T$, for errors the system observes''."

> Proposed: "With CRC: ``if the calibration sentences and later sentences are exchangeable, then, averaged over the choice of the $n$ calibration sentences and over a new sentence, the probability that the new sentence is committed wrongly is at most 0.05''. A single session can exceed 0.05. With LTT: ``under the same assumption, with probability at least 0.9 over the calibration sentences, the long-run wrong-commit rate at the chosen threshold is at most 0.05''. With adaptive online re-calibration: ``for any sequence of sentences, the average observed wrong-commit rate over the first $T$ sentences is at most $0.05 + (1 - \lambda_1 + \eta)/(\eta T)$'', which is 0.064 for $T = 816$ and $\eta = 0.05$. All three statements count only the errors the system observes, so each should be reported with the measured silent-error rate."

Why: makes the probability space explicit, gives the online constant (Major 4), and replaces "for this user in this session", which suggests a conditional guarantee that CRC does not give.

**W10. Discussion, "Per-session calibration matters more than the gate for speed".**
> Original: "On sEMG, a decoder that saw half a session of the user's data roughly doubled \ewpm{} over one trained on another day (8.02 vs 4.68). The trust layer made both safe; only calibration made one fast. For a product, a short calibration block at the start of each session is worth more than any downstream policy, and the same block can serve as the calibration set for CRC."

> Proposed: "On sEMG, a decoder trained with half a session of the user's own data gave 71% higher \ewpm{} than one trained on another day (8.02 vs 4.68). The trust layer made both safe, but only the in-session data made the system fast. Decoder adaptation, not the commit policy, set the speed. A session-start block could serve both purposes, but our drift results show that a threshold calibrated early in a day can be too permissive later the same day, so such a block should seed an online controller rather than fix the threshold."

Why: corrects "roughly doubled"; "calibration" here meant decoder adaptation, which collides with the paper's use of "calibration" for temperature scaling; removes "worth more than any downstream policy", which no experiment tests; reconciles the advice with the drift result (Minor 6).

**W11. Sec. 6.5, the other-sentence control.**
> Original: "One control it cannot pass: given the \emph{real} stream of another sentence, the trust layer on our B2T decoder committed 22\% of items, the same rate as for real input, and on sEMG it committed as often as for real input. The published-sentence gate committed 0\% in this case, because the published text did not match the other sentence's stream. A layer that sees only the stream cannot detect that the user intended a different sentence."

> Proposed: "The intent-mismatch control behaves differently. Given the real stream of another sentence, the trust policy on our B2T decoder committed 22% of items, the same rate as on matched input, and on sEMG it also committed at the matched rate. This is expected: the stream is genuine neural evidence, only for a sentence the user did not intend, and nothing in the stream reveals the intent. The gate on the published sentence committed none of these items, but only because its text came from the matched trial and disagreed with the mismatched stream; this is a property of the test construction, not a capability of the gate."

Why: names the control class (Major 1), explains why the result is expected, and prevents the reader from crediting the published-sentence gate with intent detection.

**W12. Sec. 6.6, CRC splits.**
> Original: "CRC controls the mean, not every split: 41--45\% of CRC splits were above 0.05 and the 95th percentile was 0.071--0.076. LTT lowered the 95th percentile to 0.056--0.061."

> Proposed: "Because a random split of one pool is exchangeable by construction, the mean over splits is guaranteed to be at most α; the observed 0.0483 confirms the implementation rather than testing the assumption. Individual splits vary: the test rate exceeded 0.05 in 41–45% of CRC splits. Part of this spread is test-sampling noise (standard error about 0.011 with 408 test items). LTT, which bounds the population risk with probability 0.9, reduced the 90th percentile of the test rate from [x] to [y]; its calibration-conditional risk, estimated on [the complement], exceeded α in [z]% of splits (δ = 0.1)."

Why: says what the experiment can and cannot show, and aligns the reported percentile with δ (Major 4). Numbers in brackets need the re-analysis.

**W13. Sec. 6.7, ACI result.**
> Original: "\texttt{aci\_window} stayed below 0.05 in every drift case (0.0478 and 0.0490) and \texttt{aci} sat at the target (0.0502 and 0.0526), as its bound predicts."

> Proposed: "\texttt{aci\_window} ended below 0.05 in both cases (0.0478 and 0.0490). \texttt{aci} ended at 0.0502 and 0.0526: the update drives the long-run rate towards α, and its certificate after the fact was 0.0502 and [·], within the a-priori bound of 0.064 for 816 items."

Why: a bound does not "predict" a value; 0.0526 is above target; the certificate and a-priori bound must be visible.

**W14. Fig. 1 caption title.**
> Original: "\textbf{The same trust layer removes almost all wrong commits on three device types.}"

> Proposed: "\textbf{The same trust layer turns frequent wrong commits into rare ones on three device types; on MEG it does so by not committing.}"

Why: the figure is the paper's first visual claim; the MEG panel otherwise reads as a success of the same kind.

---

## 6. Formula / code consistency

Checked `src/fidetype/trust/risk_control.py` and `online_risk.py` against Sec. 4.4–4.5 and `tab:online`.

| # | Item | Paper | Code | Verdict |
|---|---|---|---|---|
| 1 | CRC rule | inf{λ : (n/(n+1)) R̂_n(λ) + 1/(n+1) ≤ α} | `bound = (n*risk + B)/(n+1)`, B = 1, min over unique finite scores ∪ {+∞} | **Match** (B = 1). Code commits on s ≥ λ and discretises to calibration scores. This is valid and slightly conservative compared with the paper's continuous infimum; the paper should say so (Minor 2). |
| 2 | Monotone loss | "made monotone ... by taking max(c_i, f_i)" | `_as_arrays` returns `np.maximum(c, f)`; loss = max(c,f) if s ≥ λ else f | **Match.** Non-increasing in λ, upper bound of the true loss. |
| 3 | Infeasible n | none for n < 1/α − 1 = 19 | at λ = +∞, bound = (n·mean f + 1)/(n+1); infeasible ⇒ threshold +∞, `feasible=False` | **Match** when f ≡ 0. With f > 0, "never commit" can have loss > α and the CRC premise L(λ_max) ≤ α fails (Minor 3). |
| 4 | LTT | H0: R(λ) > α along a decreasing grid, exact binomial p-values, fixed-sequence | grid 1.00 → 0.00 step 0.01, fixed before data; `binomial_pvalue` = P(Bin(n, α) ≤ ⌊n R̂⌋); stop at first p > δ; HB p-value if losses are not 0/1 | **Match.** The binomial p-value is valid (super-uniform under H0). The HB fallback uses the Bentkus term e·P(Bin ≤ ⌈nR̂⌉), consistent with LTT Prop. 3. The paper could mention the HB fallback. |
| 5 | `max(λ_tuned, λ̂)` | "keeps the guarantee" | `apply(combine="max")` | **Correct** for both CRC and LTT, by pointwise monotonicity of L and of R, even if λ_tuned is chosen on the calibration data. The paper should give this reason (W7). |
| 6 | Separate data for upstream parts | "fitted on separate data" | Not enforced by the code; experiments: B2T and sEMG offline-CRC drift baselines reuse the fit data | **Mismatch between claim and experiment** (Major 3). |
| 7 | `aci` update | λ_{t+1} = max(λ_min, λ_t + η(L_t − α)) | same, plus optional `lam_max` (off by default; certificate = nan if it binds) | **Match.** |
| 8 | `aci` bound | (1/T)ΣL_t ≤ α + (λ_{T+1} − λ_1)/(ηT) | `certificate = alpha + (lam_t - lam_1)/(eta*T)`; `prior_bound` = α + (score_max − λ_1 + ηB(1+d))/(ηT) | **Match** for the identity. The paper omits the a-priori bound, the delay term (1 + d), and the condition f ≡ 0 for boundedness (Major 4). |
| 9 | `aci_window` update | α_{t+1} = α_t + γ(α − L_t) | `alpha_t = min(alpha_max, alpha_t + gamma*(alpha - loss))`, α_max = 2α | **Partial mismatch**: the paper omits the upper clip. The clip only lowers α_t, so the stated bound (α_1 − α_{T+1})/(γT) remains valid. Report the clip. |
| 10 | `aci_window` lower boundedness | not discussed | argued in the docstring: below CRC feasibility (≈ 1/(W+1)) nothing commits, so α_t rises | Add one sentence; the bound is otherwise not obviously finite. |
| 11 | `window` / `decay` | "CRC on the last N items"; "weighted CRC, weights ρ^age" | `weighted_crc_threshold`, test weight 1; offline items form the oldest history; items with unknown truth are excluded; `decay` config has `window: null` | **Match**, but the paper should say that unknown-truth items are excluded (selection bias, as the docstring states), and that `decay` is not windowed. |
| 12 | Online loss with OFFER_WORDS | not discussed | committed: max(c,f); not committed: f; `OnlineTrustPolicy` sets f = c when the fallback is OFFER_WORDS | Consistent with the offline loss. |
| 13 | Missing feedback | "Feedback can arrive late and out of order" | `missing="skip"` (default) drops commits with no feedback from the bound; `"pessimistic"` counts them as wrong | The paper should state which mode the experiments used and that "skip" restricts the bound to observed items. |
| 14 | Silent errors | "outside them" | noticed-only experiment feeds back c = 0 for missed errors | **Consistent.** The repo reports that the observed-loss certificate still held (≤ 0.052) while the true rate was 0.0515–0.0635. Put this sentence in the paper; it shows the precise failure mode. |

No arithmetic error found in the code paths I checked. The guarantees themselves are implemented correctly; the problems are in the experimental use (row 6) and in the reporting (rows 8, 9, 13).

---

## 7. Prioritised top-10 action list

| # | Action | Type | Effort |
|---|---|---|---|
| 1 | Re-run the offline-CRC drift baseline with calibration data disjoint from the data used for temperatures, guard and policy grid (B2T: split the fit half; sEMG: use the 142-sentence half of B). Add the shuffled-order control to `tab:drift`, disclose that trial order is the file order, and rename "within-session drift" to the measured between-half shift unless the clean run supports more. (Major 3) | **NEW-EXP** (CPU, < 1 h) + WRITING | S |
| 2 | Fix the null-input over-claim: split controls into signal-destroying vs intent-mismatch everywhere; correct the abstract and Sec. 6.5. (Major 1) | WRITING | XS |
| 3 | Add commit rate and error among commits to Table 4, `tab:crc` and Fig. 1; define R(λ) explicitly; optionally add LTT control of selective risk. (Major 2) | ANALYSIS (+ optional NEW-EXP, CPU) | S |
| 4 | Correct the guarantee statements: random-split CRC is an implementation check; LTT reported as 90th percentile and calibration-conditional risk; print `aci` certificates and the a-priori bound (0.064 at T = 816); list the assumptions (f ≡ 0, delay, α_max clip, missing-feedback mode) under `tab:online`; rewrite the Discussion wording (W9, W12, W13). (Major 4, code rows 8–13) | ANALYSIS + WRITING | S |
| 5 | Bring the existing MEG user-model sensitivity into the paper (p_miss = 0 reverses trust > always-commit; 40 cpm and slow selection reverse "parity"); run G6 on B2T and sEMG, plus a symmetric-offer variant and a misspecified-user evaluation without refitting; state the construct-validity caveat. (Major 5) | ANALYSIS + **NEW-EXP** (CPU, hours) | M |
| 6 | Replace "parity" and "no measurable cost" with CI statements against a pre-stated margin; use the two-way CI for MEG, day-cluster CIs for B2T paired differences, participant CIs as primary for sEMG; fix "roughly doubled". (Major 6) | ANALYSIS + WRITING | S |
| 7 | Designate primary endpoints; give the four online methods equal weight in the abstract; state which settings were fixed before which runs; disclose the r4b/r5 selection and use validation-only selection language. (Majors 7, 10) | WRITING | XS |
| 8 | Unified ablation (G5), separating the temperature's effect on decoding from its effect on confidence; report the cross-subject no-calibration result (4.76 > gaze 4.27) and correct the Discussion; discuss when the guard hurts. (Major 8) | **NEW-EXP** (CPU) + WRITING | M |
| 9 | Seeds and splits: ≥ 3 decoder seeds (MEG, sEMG), repeated B2T fit/test assignments, MEG k-fold over sentence hashes (G2, G7, G8). (Major 7) | **NEW-EXP** (GPU, days) | L |
| 10 | Writing pass: rewrite the abstract (W1); add a "Problem setting" subsection with clean notation (frames F, session length T, temperatures τ, n-best K, offer size k, calibration size n); remove internal codes (M1-09, r4b, G-ids); fix terminology (item/trial/instance/sentence; trust policy vs gate); describe the published-sentence gate's use of our reference decoder (Major 9); apply W2–W14. | WRITING | M |

**Split by type.** Writing/analysis only: items 2, 3 (main part), 4, 6, 7, 10, and the analysis half of 5. New experiments: 1 (cheap, and the most important), 5 (cheap), 8 (cheap), 9 (expensive), and the optional selective-risk LTT in 3.

**What I would need to see to recommend acceptance:** items 1–7 done, 8 at least for B2T and sEMG, and 9 at least as 3 seeds for the MEG decoder with the trust results re-scored per seed.
