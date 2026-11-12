# Paper 1, round 1: response to the reviews

- Draft reviewed: v0 (`draft-v0.pdf`, 23 pages). Revised draft: v1 (`draft-v1.pdf`, 32 pages: main text pages 1–20, references 21–28, appendix 28–32).
- Reviews: [round-1-domain.md](round-1-domain.md) (BCI / neural engineering) and [round-1-methods.md](round-1-methods.md) (methods, statistics, writing).
- Rule for this round: fix everything that needs only writing, restructuring, re-analysis of committed result files, or figure changes. Items that need new runs are marked **deferred (R1 analysis)**. A parallel analysis writes them to `experiments/2026-11-12-paper1-r1-analyses/`. The paper marks each with a red `\todo{R1: ...}`.
- New re-analysis script: `papers/paper1/analysis_r1.py` → `papers/paper1/data/r1-derived.json`. It re-draws the committed CRC/LTT splits with the original seeds (it asserts that the means equal the committed means) and adds the error among commits, the 5th/90th percentiles and the pool (calibration-conditional) risk. It also derives exact commit counts from `trust.json` and the ledger summary.

Legend: **Done** = changed in v1. **Deferred** = waits for a new run. **Declined** = not done, with reason. **Author** = needs a decision by the author.

## A. Number mismatches (domain review §6)

| # | Item | Action |
|---|---|---|
| 1 | "1,718 trials over 14 days" | **Done.** §6.3: 1,718 trials over 15 days; 1,628 trials of the 125k vocabulary over 14 days; 90 50-word trials excluded; one sentence in both halves. |
| 2 | Abstract CRC "0.046–0.048" | **Done.** Abstract now says 0.048 (n_cal 408 only). |
| 3 | "max over 50-trial windows 0.10–0.12 for all methods" | **Done.** §7.6: 0.10–0.12 on our decoder, up to 0.18 on the published gate; i.i.d. reference median 0.120 and p95 0.180. Limitation 8 says 0.10–0.18. |
| 4 | MEG harness CER 0.522 vs 0.475 | **Done.** Table 2 has a "beam in the trust harness" row (0.522); §6.3 explains the fixed beam setting. |
| 5 | `p_detect_error` 0.9 in Table 8 does not act | **Done.** Removed. Table 8 now lists only parameters of the word model (and adds offer selection, retype and abstain costs from the code). |
| 6 | sEMG "0.022, the chance level" | **Done.** Table 2 and §7.1: majority 0.338, uniform 0.037, balanced accuracies 0.367 / 0.240 / 0.226, permuted 0.022 (balanced 0.032). |
| 7 | Fig. 8b "2%" vs text "2.5%" | **Done.** Figure labels now show one decimal below 10% (2.5%); text says 2.5–4%. |
| 8 | "plug-in gate" label in Table 5 | **Done.** Renamed "fixed gate" (the plug-in policy fitted on the fit data); the source's "plug-in re-tune" is not used. Decimals made consistent (3 d.p.). |
| 9 | "roughly doubled (8.02 vs 4.68)" | **Done.** "71% higher" (Discussion). |
| 10 | CRC eWPM change "−0.3%" | **Done.** Recomputed from unrounded split means: −0.29% (ours) → "−0.3%"; published +0.06%. |
| 11 | "The ledger traces every wrong commit" | **Done.** Ledger moved to Appendix E; text says "recorded", calls it a consistency check, and says silent errors would be missing in live use. |
| 12 | sEMG cross-subject participant CI missing | **Done.** Table 3: {3.83, 4.36} (trust), {3.19, 3.88} (always commit). |

## B. Domain review: major issues

| Item | Action |
|---|---|
| M1 always-offer / threshold baselines | **Done (partly).** Always-offer rows for B2T '25 (11.37, 18.11 from the committed item tables) in Table 3 and as triangles in Fig. 1; MEG trust = always offer (OFFER rate 1.00), stated. §7.2 and the Discussion are re-framed as trust vs always offer (+1.6% and +3.6% speed for 59 and 44 wrong commits per 1,000). The no-guard row (plain threshold on calibrated p_top1) is reported in §7.3. **Deferred:** sEMG always-offer rows, CI of trust − always offer, raw-p_top1 threshold row. |
| M2 commit precision / selective risk | **Done.** New §3 defines both rates. Tables 3 and 4 have commit rate and error among commits (with counts: 48/189, 36/386, 2/21, 2/10). New Fig. 4c plots selective risk from the committed items. Discussion paragraph "Marginal vs selective risk". **Deferred:** selective-risk controller (LTT on error among commits). Commit-precision CIs: declined for now; counts are shown instead because n is small. |
| M3 claims exceed evidence | **Done.** New title (no "across MEG"); structured abstract says one implant participant, composed EMG, MEG never commits; MEG is called a negative control everywhere; "unchanged" replaced by "the same implementation, re-fitted per device"; Table 1 row "commit decision tested?"; new Table 9 lists the per-device fitted values and adapter sizes; the published-gate construction is described (§5.2). |
| M4 user model / baseline | **Done (writing).** §6.2 now has the exact silent-error mechanism, the commit/offer asymmetry, the fact that fluency plays no role, and the population mismatch; `p_detect_error` removed; the MEG sensitivity table is in Appendix D (Table 11) and cited in §7.2. **Deferred:** LM-assisted gaze baseline, sensitivity grid on B2T and sEMG, fluency-dependent miss variant. |
| M5 related work | **Done.** New paragraphs: error handling in BCI spellers (dynamic stopping, LM spellers, ErrPs, no-control state, myoelectric rejection), adaptive decoders (CLDA, self-calibration, alignment, unsupervised recalibration), dialogue confirmation, utility metrics / practical bit rate, LM-assisted gaze typing, BIDS/NWB/BCI2000/OpenViBE/P2794, CTRL-labs Nature 2025, Huang 2025, Damri 2026. Novelty claim narrowed (Intro ¶2–3). 33 references added, all verified (§G). Card et al. confirmation: the local preprint shows only display + text-to-speech; a `\todo` asks to check the supplement. |
| M6 decoder–stream mismatches, decoder metrics | **Done.** Table 2: harness CER 0.522, WER 0.842/0.809, exact 2/637, truth in 10-best 1.6%, text-only floor 0.688, sEMG balanced accuracy and both chance levels, sEMG sentence CER/WER/exact; SOTA context sentence (0.29 sync, 0.59 v2 async); within-subject MEG split stated in §6.3. |
| M7 selective reporting (calibration, guard) | **Done.** §7.3 retitled "calibration fixes sentence-level ECE but can hurt decoding"; reports token ECE 0.090 → 0.130, sEMG cross-subject uncalibrated 4.76 > gaze 4.27, the CER change from the frame temperature, guard hurting on B2T (0.059 vs 0.036), guard AUROCs; guard called optional. **Deferred:** unified ablation, LM weight re-tuned after calibration. |
| M8 leakage, independence | **Done (writing).** §6.3: sEMG near-duplicates not checked, same corpus as the LM; press reuse; participant CIs primary; cross-fitting described; B2T 64 Tatoeba sentences and one overlap. **Deferred:** LM rebuilds and re-runs. |
| M9 calibration-set size, guarantee wording | **Done (writing).** Guarantee wording rewritten (W9); "this session" removed; the "two CRC numbers on sEMG" paragraph moved into the method (pure vs combined CRC defined in §5.4 and used consistently). n_cal 100 numbers reported. **Deferred:** n_cal 20–50 and within-day calibration. |
| M10 length, focus, internal IDs | **Done (partly).** Contributions 6 → 4; format section cut to one page; conformance, ledger, audit entry, notation table, online-methods table, CRC-split figure moved to the appendix; Fig. 5 (MEG CER) and Fig. 6 (eWPM bars) and Fig. 4 (online loop) removed; internal IDs (M1-09, M1-15, r4b, r5, G-ids, "plug-in (M6-06)") removed from the text. Main text is still about 20 pages in this 11-pt one-column class (see §H). |
| M11 seeds, splits, clusters | **Deferred.** Stated as a limitation and in §6.5; MEG CER intervals over instances are no longer used for inference. |

## C. Domain review: minor issues

| # | Action |
|---|---|
| 1 | **Done.** Fig. 5 removed; rows in Table 2. |
| 2 | **Done.** Fig. 6 removed. Robustness matrix **deferred** (needs the sensitivity grid). |
| 3 | **Done.** Fig. 5c is now the MEG guard-risk AUROC per control (committed `null-audit-async.json`). |
| 4 | **Done.** Fig. 10b kept in the main text as panel (b) of Fig. 6 (it is the only plot of all methods); Table 5 is the exact record. Fig. 4 (online loop) removed. |
| 5 | **Done.** Architecture fonts enlarged (footnotesize, no forced resize unless wider than the text), label overlap fixed. |
| 6 | **Done.** Fig. 1 labels moved, legend below, y-axis "wrong commits / all sentences", MEG "commits 0%". |
| 7 | **Deferred** (reliability diagrams need per-bin output). |
| 8 | **Done.** Intro cites Fig. 1 before Fig. 2. |
| 9 | **Done.** "within-session drift" replaced by "shift between halves"; MEG participant order called a sequence across participants. |
| 10 | **Done.** §5.5 says realised loss needs the user to correct; oracle in copy task; ErrPs as implicit signal. |
| 11 | **Deferred** (one-word-edit tolerance); limitation 10. |
| 12 | **Done (writing).** §6.1 says eWPM does not price silent errors; silent-error rate reported. Cost-weighted utility **deferred**. |
| 13 | **Done.** Table 9 (per-device settings) and §5.1–5.2 (guard weights 1, threshold 0.5, top 5, temperature search). |
| 14 | **Done.** §4 states one optional field, provenance keys, v0.1 Development release by the same authors, adapter line counts 148 / 412 / 568. |
| 15 | **Done.** "71% higher". |
| 16 | **Done.** Discussion no longer says "at no speed cost" for the published gate (−4.3%). |
| 17 | **Done.** "trust 4.08 vs gaze 4.27". |
| 18 | **Done.** §6.3: no per-key timing at inference, oracle sentence bounds, cannot train for a user who cannot type. |
| 19 | **Done.** "fixed gate"; decimals consistent. |
| 20 | **Done.** Limitations grouped into "validity of the evidence" and "scope of the system". |
| 21 | **Done (partly).** BrainGate2 pilot clinical trial stated (verified in the local Card preprint). **Author:** final wording, venue policy, AI statement. |
| 22 | **Done.** OpenTelemetry analogy dropped. |
| 23 | **Done.** Structured abstract (Objective / Approach / Main results / Significance), about 300 words. |
| 24 | **Done.** BIDS, NWB, BCI2000, OpenViBE, IEEE P2794 (+ Eiber et al. 2021) cited. |

## D. Methods review: major issues

| Item | Action |
|---|---|
| Major 1 null-input over-claim | **Done.** Controls split into "signal-destroying" and "intent-mismatch" (§6.4, §7.4, Fig. 5, abstract, conclusion). W11 applied. |
| Major 2 risk measure | **Done.** As domain M2; R(λ) defined by one equation (W6) with the reason (monotone); MEG CRC row presented as "control without utility" (92% of commits wrong); deployable rule max(λ_tuned, λ_CRC) explained. **Deferred:** selective-risk LTT. |
| Major 3 drift confound | **Done (writing).** §5.4 states that the drift baselines violate the separate-data requirement; §7.6, Table 5, Fig. 6 and Limitation 6 carry the caveat; shuffled-order control added to Table 5 as a row; phenomenon renamed "shift between halves"; file order disclosed; MEG moved out of the table. **Deferred:** clean-calibration re-run (the most important pending analysis). |
| Major 4 guarantee over-interpretation | **Done.** Random-split CRC called an implementation check (W12); LTT reported with the 90th percentile and the calibration-conditional (pool) risk from re-drawn splits (0.5% / 1.5% of LTT splits above α, within δ); aci certificate and a-priori bound printed (0.0502 / 0.0637; 0.0478 / 0.0593; 0.0526 / 0.0809) with W13; Table 12 footnotes list f ≡ 0, delay, α_max clip, lower boundedness, skip mode, window selection bias; window/decay described as having no guarantee under shift; abstract gives the range of all four methods. |
| Major 5 user model | **Done (writing + existing data).** MEG sensitivity table in the appendix and cited where parity and +0.62 appear; asymmetry and construct-validity caveat in §6.2; MEG trust = always offer stated. **Deferred:** grid on B2T/sEMG, symmetric variant, misspecified user. |
| Major 6 inferential language | **Done.** "parity" removed; MEG two-way CI primary ([−0.11, +0.26]); post-hoc ±10% margin stated as post hoc → "no detectable difference"; B2T day-cluster CI of the paired difference {−0.17, +0.33} and "excludes a slowdown larger than about 1.5%"; sEMG participant CIs primary; 10 of 19 kept as descriptive. MEG CER instance CIs removed. |
| Major 7 seeds, r4b/r5 | **Done (writing).** r5 test comparison removed; "selected on validation CER; a longer schedule gave the same validation CER" (W8). **Deferred:** seeds, repeated splits, k-fold. |
| Major 8 ablations | **Done (writing).** Cross-subject no-calibration result reported and the Discussion corrected; guard hurting on B2T discussed. **Deferred:** unified ablation separating the temperature's effect on decoding from its effect on confidence. |
| Major 9 published gate is not black-box | **Done.** §5.2 "Gate on a published sentence" describes the construction (our 10-best, +2.0 bonus, word alignment); contribution 1 and the Discussion say "needs a light reference decoder, not the vendor's weights". |
| Major 10 primary endpoints | **Done.** §6.5 names two primary endpoints per device, says the rest is descriptive and uncorrected, and states which settings were fixed before which runs (noticed-only rows added later). |

## E. Methods review: minor issues

| # | Action |
|---|---|
| 1 | **Done** (W6 equation). |
| 2 | **Done.** §5.4: search over calibration scores and +∞, commit on s ≥ λ, valid and slightly conservative. |
| 3 | **Done.** §5.4: CRC needs mean f ≤ α; we use f ≡ 0. |
| 4 | **Done.** §7.5 explains why LTT commits more than CRC on MEG. |
| 5 | **Done.** decay "on all past items" (not windowed). |
| 6 | **Done.** Discussion "Decoder adaptation set the speed" (W10): n ≥ 19, early-day thresholds too permissive, seed an online controller. |
| 7 | **Done.** §5.1: frame temperature by cross-entropy on greedy CTC peak frames (not the full CTC loss); sentence temperature by binary NLL; golden-section search on log τ in [0.05, 20]; data used per device in §6.3. |
| 8 | **Done (partly).** ECE binning (15 equal-width bins). ECE CI / reliability diagrams **deferred**. |
| 9 | **Declined for now:** AUROC CIs not computed; the text says so. Can be added with the deferred harness re-runs. |
| 10 | **Done.** Table 9 + guard description. |
| 11 | **Done.** eWPM formula (strict, ratio of sums). Note: the reviewer's "n − word edit distance" is the code's lenient variant, not the reported one. |
| 12 | **Done.** §6.2: gaze baseline is error-free with no reading/correction time and no LM. |
| 13 | **Done.** §6.3 and Limitation 2. |
| 14 | **Done (writing).** §6.3 discloses; rebuild **deferred**. |
| 15 | **Done.** §6.3: 11 validation sentences fit all MEG trust parts. |
| 16 | **Deferred.** Silent-error CIs exist in the B2T tables only for main policies; a CI for the ACI budget suggestion needs the new runs. |
| 17 | **Done.** p95 0.180 given. |
| 18 | **Done.** Shared y label, "commits 0%". |
| 19 | **Done.** Fig. 6 caption: single runs, no uncertainty; MEG out of the panel. Day-cluster CIs **deferred**. |
| 20 | **Done.** Table 4 states n_test per row (408, 408, 229) and "instances" for MEG. |
| 21 | **Done.** "recorded", consistency check. |
| 22 | **Done.** Availability: no SpanishBCBL-derived weights released (checked: only synthetic conformance vectors are committed). |
| 23 | **Done.** 6 → 4 contributions. |

## F. Methods review: rewrites W1–W14 and code table

| Item | Action |
|---|---|
| W1 abstract | **Done**, adapted to a JNE structured abstract; keeps "simulated", the control classes, and the four-method range. |
| W2 motivating claim | **Done.** |
| W3 gap | **Done**, positioned after the closest work. |
| W4 contribution 3 | **Done** (now contribution 2). |
| W5 "honest probabilities" | **Done** ("Unmodified probabilities"). |
| W6, W7 | **Done.** |
| W8 | **Done.** |
| W9 | **Done.** |
| W10 | **Done.** |
| W11 | **Done.** |
| W12 | **Done**, with the brackets filled from `r1-derived.json` (p90 0.0515 / 0.0542 vs 0.0686; pool risk above α in 0.5% / 1.5% of LTT splits). |
| W13 | **Done** (certificate equals realised value; a-priori 0.064 / 0.081). |
| W14 | **Done.** |
| Code rows 6, 8, 9, 10, 11, 13, 14 | **Done** in §5.4, §5.5 and Table 12 footnotes (separate-data requirement and its violation, prior bound with delay, α_max clip, lower boundedness, unknown-truth exclusion, missing-feedback mode, noticed-only certificate 0.0496 / 0.0518). |
| Notation (F, T, τ, K, k, n) | **Done.** New §3 "Problem setting"; Table 7 (notation) in Appendix A. |
| Terminology | **Done.** item (generic) / trial / instance / sentence defined in §3; "trust layer" (the system), "trust policy", "fixed gate", "gate on the published sentence"; "audit log" for the ledger. |

## G. References

- 18 existing `% TODO-verify` entries resolved against Crossref, publisher, OpenReview or NeurIPS pages. Corrections that change the paper: `achituve2025emg` first author is **Eby** (order Eby, Beutel, Koivisto, Achituve, Fetaya, Zariffa); `spanishbcbl` title is "DECOMEG — Brain Activity During Typing (MEG & EEG)"; W3C EMMA title fixed; IEEE P2731 title and URL fixed; the Apple page has no date (year removed).
- 33 new verified entries: schreuder2013dynamic, throckmorton2013bayesian, mainsah2015dynamic, speier2016nlp, orhan2012rsvp, oken2014rsvp, schalk2000errp, ferrez2008errp, dalseno2010errp, spuler2012errp, chavarriaga2014errare, scheme2013rejection, orsborn2014clda, jarosiewicz2015selfcal, degenhart2020stabilization, fan2023plugandplay, wilson2023recal (journal version, Nat Biomed Eng 2026), mason2000asynchronous, zhang2008asynchronous, aloise2011asynchronous, dalseno2010utility, townsend2010checkerboard, bohus2005error (Interspeech 2005, rejection thresholds), ctrllabs2025generic, ward2000dasher, huang2025cocontrol, damri2026risk, gorgolewski2016bids, rubel2022nwb, schalk2004bci2000, renard2010openvibe, ieeep2794, eiber2021reporting.
- Three abstracts were not retrieved (jarosiewicz2015selfcal, degenhart2020stabilization, ctrllabs2025generic); the paper cites them only for what their titles state.

## H. Not done in this round and why

- **Length.** Main text is about 20 pages in the 11-pt one-column draft class (v0: about 17), because the reviewers asked for many additions (problem setting, baselines, error among commits, assumptions, two related-work paragraphs, 33 references). The IOP JNE template is denser. Further cuts are an **author** decision; candidates: move §7.6 (online) to the appendix with a half-page summary, shorten related work to one page, move Table 2 (decoders) to the appendix.
- **All new runs** listed as Deferred above. They come from `experiments/2026-11-12-paper1-r1-analyses/` in round 2.
