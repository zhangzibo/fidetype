# Paper 1, review round 4: handling editor

- **Manuscript:** "When should a neural text-entry decoder commit? Risk-controlled commits from a decoder-agnostic trust layer", draft v3 (`papers/paper1/draft-v3.pdf`, 37 pages; LaTeX in `papers/paper1/latex/`).
- **Target venue:** Journal of Neural Engineering (JNE).
- **Reviewer role:** handling editor (BCI text entry, AAC, HCI evaluation). Independent read. I wrote this assessment before I opened any earlier review or response. Afterwards I skimmed `round-3-response.md` only to check claimed fixes (see the last section).
- **Date:** 2026-11-12.

## 1. Summary

The paper asks when a neural text-entry system should send ("commit") a decoded sentence without confirmation. A "trust layer" reads the per-frame output stream of a decoder. It calibrates confidence with two temperatures, builds a K-best list with a CTC beam search and a character LM, and then commits, offers alternatives or abstains. The commit threshold is the larger of an eWPM-tuned threshold and a Learn-then-Test (LTT) threshold ("max rule"). The calibration data are disjoint from the fitting data. The evaluation is offline:

- one intracortical participant (T15, Brain-to-Text '25 copy task), with the authors' own phoneme-to-word decoder and a "gate" on the published sentence;
- forearm sEMG key presses composed into Tatoeba sentences (19 participants, oracle timing);
- MEG typing (19 participants) with a weak decoder, framed as a negative control.

Main results: on the intracortical data, LTT with the max rule gives a mean wrong-commit rate of 0.030 / 0.031 over 50 repeated splits, with 8% / 2% of splits above alpha = 0.05. It commits 15% / 39% of sentences, and 21% / 8% of those commits are wrong. Pure CRC holds only on average (34-42% of splits above alpha). A selective target (error among commits <= 0.10) is reachable only for the published decoder. On sEMG and MEG the layer commits almost nothing. Speed effects are small and depend on the user model.

The paper is careful, honest about its limits and much improved in statistical hygiene. Its core contribution is an applied evaluation of known risk-control methods (CRC, LTT, SGR) as a commit rule. It is not a new method. The evidence for the commit decision comes from one participant in a copy task. The "repeated deployment" test uses exchangeable splits, so it cannot show how the guarantee behaves across days, which is the deployment question that matters. Several framing choices (the title word "decoder-agnostic", "reads only the stream" for the published gate, "at little speed cost") go beyond the evidence. The manuscript is also too long for JNE, and it still has a rendering bug in the Introduction and five author TODOs.

## 2. Recommendation

**Major revision.**

The work could suit JNE as a careful methods-evaluation paper, but only if (a) the authors add a temporal (cross-day) deployment test on the data they already have, (b) the claims are brought in line with the evidence (stream-only, decoder-agnostic, speed, significance of the reuse effect), and (c) the main text is cut to about 7,000-8,000 words, with most appendices moved to supplementary material. None of these needs new participants. (a) needs only re-analysis.

## 3. Assessment by criterion

| Criterion | Judgement |
|---|---|
| Novelty | Moderate to low on method: CRC, LTT, SGR, temperature scaling and the max rule are all published, and the authors say so (Sec. 1, Sec. 2). The novelty is the problem framing (commit vs offer vs abstain for neural text entry), the marginal vs selective risk distinction and the evaluation protocol. |
| Significance | Potentially high for clinical BCI text entry, where an unconfirmed wrong sentence is a real harm. Today it is limited by n = 1 participant, a copy task, within-day exchangeable splits and simulated users. |
| Claims vs evidence | Mostly calibrated. Exceptions: Major 1-5. |
| Clarity / structure | Dense but precise. Too long (Major 7). The STE style helps. Some sections repeat (latency, frozen configuration, MEG caveats). |
| Figures / tables | Table 1 is overloaded. Fig. 2 and Fig. 3 show the plug-in rule, not the primary rule. Fig. 4 (App. C) is stale. |
| Related work | Good on BCI and conformal basics. Conformal selection / FDR-type control of the error among selected items is missing. One reference is outdated (LTT is now published), and one could not be verified (Lévy et al. DOI). |
| Ethics / limitations | The Limitations section is good. The ethics text still has TODOs. The JNE trial-registration requirement is not met. |

## 4. Major issues

### M1. The "repeated deployment" test does not test deployment; add a cross-day (temporal) test.

- **Location:** Sec. 6.3 ("Repeated deployment splits"), Sec. 7.2, Table 2, contribution 2 (Sec. 1), Discussion ("Which guarantee to deploy").
- **Problem:** Each of the 50 repeats permutes every day's trials and splits them day-stratified into fit-A / calibration / test. So calibration and test are exchangeable by construction. The experiment then checks the LTT and CRC theorems under conditions where they must hold. It confirms them: about 8% vs delta = 0.1, and the test-rate exceedance includes test-sampling noise. The paper itself says that random splits "check the implementation, not the assumption" (Sec. 6.3, App. Q), and this applies equally to the day-stratified repeats. But contribution 2 is worded as "a test of the guarantee under repeated deployment", and the Discussion draws deployment advice from it ("a user lives in one deployment"). A real deployment calibrates on earlier sessions and runs on later ones. Within-day drift is not detectable on these data (Sec. 7.4), but cross-day drift is the known failure mode of intracortical decoders. The paper's own references on decoder instability [53-57] say so.
- **Fix:** You have 14 days with about 116 trials each, so a forward-chaining analysis is feasible now. For k = 4..13: fit on days 1..k-2, calibrate on day k-1 (or on days k-2..k-1), and test on day k (and on days k+1..14). Report the wrong-commit rate, the commit rate, the error among commits and the share of test days above alpha, for the LTT max rule, the CRC max rule and the plug-in rule. Also add a "calibrate on the first n trials of the test day" variant, a realistic session-start calibration (App. Q already has a 20-trial version). Then reword contribution 2 as "split-to-split variation under exchangeability" and present the temporal result as the deployment test. If the guarantee fails across days, that is the most useful finding the paper could report.

### M2. The published-decoder gate does not read "only the stream", and its confidence comes from the authors' own decoder.

- **Location:** Abstract ("A trust layer reads only the decoder's per-frame output stream"), Sec. 5.2 ("Gate on a published sentence"), Sec. 8 ("Strong decoders still need a gate"), Fig. 1a, Table 1, Table 3.
- **Problem:** For the published decoder, the gate places the published sentence on top of the authors' own phoneme-to-word K-best list with score = (best own score + 2.0). It gives each published word the acoustic confidence of the aligned word in the authors' own top candidate. So p-hat_top1 for the published sentence is a function of the authors' decoder's score spread, and the guard measures agreement between two decoders. The input is the stream plus the published text plus a reference decoder. This is a legitimate and interesting design (decoder agreement as a commit signal), but it is not a stream-only confidence of the published decoder. The provenance of the bonus value 2.0 is not given. All results for "a strong decoder" (the only condition that reaches beta = 0.10) depend on this construction.
- **Fix:** (i) In the abstract and Sec. 1, say that for the published decoder the layer gates the published text by agreement with a reference decoder run on the same stream. (ii) State how 2.0 was chosen (a priori? tuned on fit data? on test?) and add a sensitivity row (for example 0, 1, 2, 4) in the appendix. (iii) In Sec. 8, write "agreement with a light reference decoder" rather than "only the stream". (iv) Reconsider "decoder-agnostic" in the title (see M3).

### M3. Cross-modality and "decoder-agnostic" claims are stronger than the evidence.

- **Location:** Title, Abstract (Approach), Sec. 1 ("This work"), Table 13 ("Commit decision tested? weakly / no").
- **Problem:** The commit decision is tested non-trivially on one participant and two decoders, one of which is gated through the other (M2). sEMG uses sentences composed from isolated presses with oracle timing, no inter-key context and templated Tatoeba text (295/551 near variants). There the layer commits 2-9% of sentences, and those few commits have EAC 0.38-0.44 on cross-session (Table 2). MEG is a decoder with 0.3% exact top-1, so the "negative control" framing is post hoc. It shows only what the signal-destroying controls already show: the layer does not commit garbage. What the paper shows across modalities is format compatibility (one adapter per device, the same code), not that the commit rule works across decoders.
- **Fix:** Change "decoder-agnostic" in the title to "stream-level" (or drop it). In the abstract, put the intracortical result first and describe sEMG and MEG in one sentence as format and safety checks. Consider moving MEG fully to the appendix. That would shorten the paper and remove the need for the sentence-clustering caveats in the main text.

### M4. The speed claim "at little speed cost" is ambiguous, and in one case it is wrong in direction.

- **Location:** Abstract (Significance), Sec. 1 (last paragraph), Conclusion.
- **Problem:** Against always offering, the guaranteed rule is faster by 0.11 and 0.51 eWPM, about 1% and 3%. These gains are far below any plausible perceptual or clinical threshold, and they rest on unmeasured costs (Table 5: 8 of 10 parameters are assumptions). Against always committing, the published decoder loses about 1 eWPM (18.65 vs 19.61, Table 1), and always commit was the fastest policy in all 9 user-model variants (Sec. 7.5). Also, the comparator "the same fitted policy without commits" (abstract, Sec. 7.2) is not defined in Sec. 6.1, and its values do not appear in Table 2.
- **Fix:** Name the comparator every time: "at little speed cost relative to always offering; slower than always committing for the published decoder". Define "same policy without commits" in Sec. 6.1 and add an always-offer (or no-commit) row with eWPM to Table 2. In the Significance sentence, say that speed effects are within the uncertainty of the user model.

### M5. The p-value for the data-reuse effect treats overlapping resamples as independent replicates.

- **Location:** Abstract ("+0.9 percentage points, p = 0.003"), Sec. 7.4 (Wilcoxon p = 0.003, 0.036, 0.72, 0.71).
- **Problem:** The 50 repeats re-draw fit, calibration and test sets from the same 1,628 trials. They overlap heavily, so they are not independent. A Wilcoxon signed-rank test across them has an inflated type-I error. This is the known problem of resampled-split tests (Dietterich 1998; Nadeau and Bengio 2003). The paper says that the spread is "not a CI for new data" (Table 2 caption), but it still puts the p-value in the abstract.
- **Fix:** Remove the p-value from the abstract and report the effect with its 5th-95th percentile range (which includes 0: -0.020 to +0.040). If a test is kept, use a corrected resampled t-test (Nadeau-Bengio variance correction) or a day-level paired test, and call it descriptive. The effect is also small (a quarter of one deployment's spread), so I suggest that the abstract drop it entirely. The methodological message ("calibration data must play no other role") rests on theory, not on this p-value.

### M6. The primary system contains a component that the paper shows to be harmful, and the frozen configuration differs from the reported one.

- **Location:** Sec. 5.2 (guard), Sec. 7.6 ablation (3), Sec. 8 ("A frozen configuration").
- **Problem:** The guard raised wrong commits on real intracortical data (0.059 -> 0.036 without it; day sign test p = 0.021), and it changed nothing elsewhere. The guard also defines the eligibility in s_i. All headline numbers therefore come from a configuration that the authors themselves no longer recommend, and the frozen configuration for the confirmatory test drops the guard. The readers' takeaway is unclear: which system is the contribution?
- **Fix:** Keep the pre-specified results (good practice), but add the plain-threshold + LTT max rule row to Table 1 and Table 2 (the repeated splits), because that is the configuration you will carry forward. Present the guard in the main text as a negative result with one sentence, and move its formulas fully to the appendix. Also run the plain threshold on the control streams (Sec. 7.6 says it was not run). Otherwise the frozen configuration has no evidence that it rejects signal-destroying streams.

### M7. Length and structure: too long for JNE; cut about 25-30% of the main text and move appendices to supplementary material.

- **Location:** Whole manuscript. Main text is about 10,000 words (pages 1-17, including tables and captions). The appendices (A-Q, 17 sections, pages 25-37) add about 6,700 words. The abstract has 355 words.
- **Problem:** JNE asks that research papers are "not normally more than 12,000 words (14 journal pages)". In one-column 11pt this draft is already 16-17 pages of main text. With the appendices in the body it is well above the limit. The main text also repeats itself: the latency appears in both Sec. 8 and Sec. 11; the MEG non-guarantee caveat appears in Sec. 7.2, Sec. 8, Lim. 2 and App. K; the 256-sentence sEMG numbers appear in Sec. 7.2, Table 1, Lim. 2 and App. I.
- **Fix (concrete cuts, about 2,500-3,000 words):**
  1. Abstract to 250 words or fewer. Drop the reuse p-value (M5), the sEMG/MEG detail and the "conformal risk control met the target only on average" sentence (keep the 34-42% in the text).
  2. Sec. 2: compress "Metrics and standards" to two sentences. Move NWB, BCI2000, OpenViBE and IEEE to the format appendix, because the format is no longer a contribution.
  3. Sec. 4 (stream interface): merge into Sec. 5 as one paragraph.
  4. Sec. 5.5 and the online part of Sec. 7.4: move to the supplement and keep one sentence each.
  5. Sec. 7.4 fixed-split paragraph (the 0.0245 / 0.0600 / 0.0625 history, Holm, exchangeable reference): move to the supplement and keep the 50-split result.
  6. Sec. 7.2: shorten the "difference to the fit-A rows does not come from CRC" paragraph to two sentences. It is about the plug-in rule, which is no longer primary.
  7. Sec. 7.5: keep Fig. 2 and three sentences.
  8. Sec. 7.7 and the MEG parts of Sec. 7.2: shorten if MEG moves to the appendix (M3).
  9. Sec. 11: remove the hardware and latency repetition.
  10. Move appendices A-Q to a supplementary file. Keep only Algorithm 1 and Table 5 (the user model) in the main paper or in a short appendix.

## 5. Minor issues

1. **Rendering bug, Introduction last paragraph (PDF p. 2):** the sentence ends "the wrong-commit rate stayed at or below 5" and then stops. In `sections/introduction.tex` line 18, "5%" is unescaped, so LaTeX treats the rest of the line as a comment. Write `5\%` (and `92\%`, `98\%`). A grep finds no other unescaped `%` in the sections, but re-check after edits.
2. **Fig. 4 (App. C) is stale:** it shows lambda-hat = max(lambda_tuned, lambda_CRC) with "CRC: E[wrong commit] <= alpha". The primary rule is now LTT. Redraw it, or delete it, since Algorithm 1 covers it.
3. **Figs. 2 and 3 use the plug-in layer / full-fit pipeline,** not the primary rule. Say this in the first line of each caption, or regenerate the figures with the LTT max rule. In Fig. 2c the B2T published points (about +13 eWPM) compress all other conditions. Use a split axis or per-row scaling.
4. **Fig. 1:** the signed square-root axis with "always offer drawn just below 0" is hard to read, and sEMG guaranteed markers are "not drawn". Consider a log10(rate + 0.005) axis or a broken axis. Give the commit rate as marker size or as a label, because a low wrong-commit rate means little without it.
5. **Table 1 is overloaded** (24 rows, mixed counts and rates, the 256-sentence sensitivity rows). Move the 256-sentence rows and the gaze-completion values to the supplement. Give gaze + completion a CI or mark it as a point value.
6. **"Error among commits" small-sample handling:** Table 3 reports "> beta = 0" when SGR committed nothing in 64% of splits. State that splits without commits count as not exceeding. Otherwise the 0 looks better than it is.
7. **Ground truth in a copy task:** a "wrong" sentence is any mismatch with the cue after normalisation. In a copy task, the participant can misread or misspeak the cue. Card et al. collected participant correctness ratings. Say whether these are in the file. If they are, report agreement between the cue-based label and the participant's rating.
8. **Frame temperature raises per-frame ECE** (0.090 -> 0.130, Sec. 7.6) although it minimises cross-entropy on the fit peaks. Explain why in one sentence (the blank targets for inserted peaks? a fit/test difference?).
9. **Sec. 6.1:** "the intracortical rate comes from copy-task speech durations". Give the source of 159.3 cpm (which field of the file) and say that it excludes the 6 s finalisation pause, if it does. That pause is part of the original interface's commit latency.
10. **Sec. 5.3:** say explicitly that the LTT fixed-sequence test uses one pre-specified ordering, so no multiplicity correction is needed. Readers from BCI will ask.
11. **Sec. 5.4 / Table 3:** Joint = max(lambda_SGR, lambda_CRC,max) uses CRC, while the primary marginal rule is LTT. Why not max(lambda_SGR, lambda_LTT,max)? The frozen configuration (Sec. 8) says "joint selective constraint" without saying which marginal rule. Make it consistent.
12. **Sec. 7.1:** "all seeds stayed at least 0.14 below the shuffled control". Seed 2 greedy is 0.592 vs 0.732 shuffled (difference exactly 0.140 at three decimals). The claim holds, but it sits on the boundary. Give the per-seed differences (0.254, 0.243, 0.140) instead, which is more informative.
13. **Sec. 7.3:** "exact binomial bounds on 10-80 calibration commits are wide". Give one worked number, for example the 90% upper bound for 0/40 or 3/40.
14. **Discussion, "Who sets alpha":** "asked for at least 90% accuracy [12, 13], which suggests beta <= 0.10". Huggins et al. asked about accuracy in general, not per committed sentence. Mark this as your interpretation.
15. **Sec. 8 frozen configuration** refers to the "policy grid of Table 8". The grid is in the App. F text; Table 8 has the fitted values. Fix the pointer. Also give the commit hash of the tag, not only its name.
16. **Notation:** Algorithm 2 step 9 uses lambda-hat for both the CRC and LTT outputs. Use subscripts.
17. **Sec. 6.2 (MEG):** "with the validation-tuned beam the layer also committed nothing (3.14 instead of 3.20 eWPM)". This detail belongs in the appendix.
18. **Ethics / Acknowledgements:** the AI-assistance statement is a TODO. JNE/IOP policy expects disclosure in the methods or acknowledgements. Write it before submission.
19. **Draft header:** remove "Draft v3 ... not for distribution" and the date line from the title block. Switch to the IOP template before submission. The class comment says that this is still to do.
20. **Code URL:** `github.com/zhangzibo/fidetype` is a personal account. Archive it (Zenodo DOI) and cite the archived version. This is also a TODO.

## 6. References: spot-check (web, 2026-11-12)

| Ref | Claim in bib | Result |
|---|---|---|
| [5] Jude et al., Nat. Neurosci. 2026 | "Restoring rapid natural bimanual typing..." | **Exists.** Published online 16 March 2026, doi 10.1038/s41593-026-02218-y. The volume/issue/pages (29(10):2613-2622) were not confirmed; check them. |
| [6] Lévy et al., Nat. Neurosci. 29:2438-2444, 2026, doi 10.1038/s41593-026-02303-2 | Brain2Qwerty v1 journal version | **Not verified.** The preprint exists (arXiv:2502.17480). Web sources disagree on the venue (one says Nature, one Nature Neuroscience), and I found no page that resolves this DOI. Check the DOI on doi.org before submission. |
| [7] Brain2Qwerty v2, Meta PDF | web PDF | A listing gives arXiv:2608.18114 for "Accurate decoding of natural sentences from non-invasive brain recordings" (I did not confirm it on arxiv.org). If it exists, cite arXiv instead of a web PDF. |
| [9] Eby et al., Sci. Data 12:440, 2025 | sEMG dataset | **Correct** (15 March 2025, doi 10.1038/s41597-025-04763-w). |
| [24] Angelopoulos et al., LTT, arXiv 2021 | LTT | **Outdated.** Published in Annals of Applied Statistics, 2025 (pp. 1641-1662, doi 10.1214/24-AOAS1998). Update the entry, because it is the paper's primary method. |
| [25] Kim, Ko, Lee, arXiv:2511.07890 | confidence-aware EEG speech decoding | **Correct** (13-class overt speech, ensembles + calibration + accept/abstain). Note that it already uses selective accept/abstain in a BCI. That is close to your framing, so differentiate it explicitly. |
| [27] Damri and Laufer-Goldshtein, ICLR 2026 | LTT for generative ASR | **Exists.** The ICLR site title adds "Conformal" ("...via Conformal Risk Control"). Use the final title. |
| [57] Wilson et al., Nat. BME 2026 | HMM recalibration | **Exists** (online 8 Dec 2025, doi 10.1038/s41551-025-01536-z). |
| [69] Ernez et al., PMLR 204, 2023 | conformal ASR | **Exists** (proceedings.mlr.press/v204/ernez23a). |

**Missing related work (suggested):**

- Conformal selection with FDR control: Jin and Candès, "Selection by prediction with conformal p-values", JMLR 2023. Also Gui, Jin and Ren, "Conformal alignment: knowing when to trust foundation models with guarantees", NeurIPS 2024. Both control the fraction of wrong items among those selected, which is your "error among commits". They are the natural comparator to SGR/LTT-sel in expectation form and may commit more at the same beta.
- ASR word and utterance confidence estimation (for example Jiang, "Confidence measures for speech recognition: a survey", Speech Communication 2005). The commit/offer/abstain decision is the classic accept/confirm/reject in spoken dialogue. You cite Bohus and Rudnicky; one more line on ASR confidence is enough.
- Corrected resampled tests (Nadeau and Bengio 2003), if you keep any test over repeated splits (M5).

## 7. Ethics and limitations

- The Limitations section is honest and complete. Keep it.
- **Trial registration:** JNE requires "articles relying on clinical trials" to quote the trial registration number at the end of the abstract. The intracortical data come from BrainGate2 (NCT00912041). Add it to the abstract, or ask the editorial office whether secondary analysis of public data is exempt.
- The ethics paragraph has a TODO on secondary use of public clinical-trial data. State that the data are CC0, de-identified, and used under the original consent and IRB. Cite the data descriptor [34].
- The audit-log example (Fig. 6) quotes a cue sentence. The CC0 argument is fine.

## 8. Number consistency (abstract vs tables vs text)

I checked these values against each other:

- 61% / 19%
- 3.0% / 3.1%
- 8% / 2%
- 15% / 39% committed
- EAC 21% / 8%
- 34-42%
- sEMG <= 9%
- +0.9 pp
- Fig. 1 caption commit and EAC values
- Table 3 values in Sec. 7.3
- 96% of always-commit eWPM (18.77 / 19.61)
- 71% (8.02 / 4.68)
- the LTT n = 45 and CRC n = 19 feasibility limits

All are consistent. Two exceptions:

1. The abstract's "0.11 and 0.51 eWPM faster than the same policy without commits" cannot be checked from any table (M4).
2. "at least 0.14 below the shuffled control" is a rounding edge case (minor 12).

## 9. Must fix before submission

1. Fix the truncated Introduction sentence (the unescaped `%` in `introduction.tex` line 18).
2. Add a cross-day / forward-chaining deployment test on Brain-to-Text '25, and reword contribution 2 (M1).
3. Describe the published-decoder gate correctly (reference-decoder agreement, not stream-only), justify the 2.0 bonus and add a sensitivity check (M2). Drop or replace "decoder-agnostic" in the title (M3).
4. Remove the resampled-split p-value from the abstract, or correct it (M5). Name the comparator in every speed claim and add the no-commit row to Table 2 (M4).
5. Add the plain-threshold + LTT max rule rows (the frozen configuration) to Tables 1-2 and run it on the control streams (M6).
6. Cut the main text to about 7,000-8,000 words and the abstract to 250 words or fewer, and move appendices to supplementary material (M7).
7. Resolve all five TODOs (authors, ethics wording, DOI archive, funding, AI-assistance statement). Add the BrainGate2 registration number. Switch to the IOP template.
8. Verify the Lévy et al. DOI, update LTT to its Annals of Applied Statistics version, and add conformal-selection references.
9. Redraw or remove the stale Fig. 4. Label Figs. 2-3 as plug-in, or regenerate them with the primary rule.

## 10. Check of claimed round-3 fixes (after my assessment)

I skimmed `papers/paper1/round-3-response.md` and checked a sample of claims against v3:

- **Present as claimed:**
  - LTT max rule as the primary row (abstract, Table 1, Table 2, Sec. 7.2)
  - selective controllers (Sec. 5.4, Table 3)
  - correct attribution of 0.059 -> 0.0245 to the policy grid (Sec. 7.2)
  - Holm correction and power statement (Sec. 7.4)
  - sEMG test-set exclusion separated from the LM rebuild (Lim. 2, App. I)
  - MEG sentence-level infeasibility (Sec. 7.2, App. K)
  - unified bootstrap
  - Algorithms 1-2
  - frozen-configuration tag `paper1-v3-frozen-config` (exists locally and on origin)
- **Claimed "done" but incomplete:**
  - Ed-M9 / main text restructure: the main text is still about 10,000 words and 16-17 pages (M7).
  - The Fig. 1 / decision-flow update did not reach Fig. 4, which still shows the CRC max rule (minor 2).
  - "Every CI from one bootstrap" holds, but gaze + completion still has no CI in Table 1.
- **Claimed "no change" that should change:** "Ref B2Q v2 web PDF: we found no arXiv version". A listing gives arXiv:2608.18114. Re-check it.
- **New in v3 and not caught:** the truncated Introduction sentence (the `%` bug). It appears in the very paragraph that states the paper's claim.
