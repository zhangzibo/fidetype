# Paper 1: response to review round 4 (draft v3 -> draft v4)

- **Date:** 2026-11-12. Tracker task: M3-21.
- **Draft:** `papers/paper1/draft-v4.pdf` (main text, references, Appendix A; 22 pages: main text pp. 1-15, references pp. 15-20, Appendix A pp. 21-22) and `papers/paper1/draft-v4-supplement.pdf` (Supplementary Sections S1-S22, 17 pages). LaTeX: `latex/main.tex`, `latex/supplement.tex`, `latex/sections/*.tex`; build with `bash papers/paper1/build.sh`.
- **Reviews answered:** `reviews/round-4-editor.md` (Ed-) and `reviews/round-4-stats.md` (St-).
- **New numbers:** all come from `experiments/2026-11-12-paper1-r4-analyses/` (M3-20). Two small additions in `v4-derived/` (M3-21): the frozen v4 configuration on the control streams (`guard_controls.py`) and three small derived numbers (`derived.py`). Supplementary tables are written from the committed JSON files by `papers/paper1/make_supp_tables.py`.
- **New title:** "When should a neural text-entry decoder commit? Risk-controlled commits from a stream-level trust layer" ("decoder-agnostic" -> "stream-level").
- **Length:** main text 6,533 words + 1,250 words in tables, figure captions and algorithm (7,783 in all; approximate count by `papers/paper1/wordcount.py`, texcount is not installed); abstract 249 words including the headings and the trial registration. v3: about 10,000 + 355-word abstract.
- Status words: **done**, **partly** (the reason for the rest is given), **declined** (with reason). Section, table and figure numbers refer to v4. "S" numbers are in the supplement.

v4 numbering: Tab. 1 = time-ordered tests; Tab. 2 = random re-splits; Tab. 3 = fixed test sets; Tab. 4 = error among commits; Tab. 5 = user model (App. A). Fig. 1 = teaser; Fig. 2 = across days (new); Fig. 3 = user model. Sec. 6.2 = time order; 6.3 = re-splits and scope; 6.4 = fixed test sets, sEMG, MEG; 6.5 = error among commits; 6.6 = controls; 6.7 = speed; 6.8 = calibration and other components.

## 1. Main changes in one list

1. **Deployment test in time order (new Sec. 5.3, Sec. 6.2, Tab. 1, Fig. 2a, Tab. S7).** Calibration always comes before the test data, over 14 days, in four designs (previous day; two previous days; all earlier days; first half of the test day). LTT max: pooled wrong-commit 0.010-0.027; above alpha on 0-2 of 10-13 test days; no day with a CP lower bound above alpha. Contribution 2 is now this test.
2. **"Repeated deployments" are now "random re-splits"** everywhere; we say that they are exchangeable by construction and check the theorems on one pool (Sec. 5.3, Tab. 2 caption).
3. **Scope of the guarantee (Sec. 4.2 "Scope of the guarantee", Sec. 6.3, Fig. 2b, Tab. S8, Discussion).** LTT bounds the risk over the mix of days. The published gate's day 34 ran at 0.102 over re-splits (0.16 in the fixed splits). "The per-deployment guarantee is the one a user experiences" is withdrawn. Remedy named: per-session (Mondrian) calibration with >= 45 items per session, or a session-start block.
4. **Frozen configuration changed (Sec. 7 last paragraph).** The v3 frozen configuration (plain threshold, no guard) committed 198/300 uniform (no-information) streams on our decoder, all wrong. v4 freezes the **guarded** configuration + LTT max; it committed 0/300 frame-shuffled and 0/300 uniform streams on both decoders (new `v4-derived/guard_controls.py`, Tab. S19). New git tag `paper1-v4-frozen-config` on the v4 commit; the tag `paper1-v3-frozen-config` (commit 65359dc) is kept unchanged for the record, and Sec. 7 says that it must not be used.
5. **Joint rule replaced by joint LTT** (fixed 20-point grid, Bonferroni, max of the two p-values; Sec. 4.3, Alg. S1, Tab. 4). LTT-sel is the reference selective controller; SGR is a comparison with its guarantee "as stated in Theorem 3.2" of Geifman and El-Yaniv. Joint LTT with beta = 0.10 almost never commits; beta = 0.20 is usable only on the published gate.
6. **Published gate described as a two-decoder agreement signal** (Sec. 4.1, abstract, Discussion); the published sentence alone never commits; the bonus 2.0 was set by hand (commit 3fb8154) and its sensitivity is in Tab. S11.
7. **Abstract rewritten** (249 words): rule chosen after the re-splits; exceedance CIs instead of "(allowed: 10 %)"; no reuse p-value; trial registration NCT00912041.
8. **Main text cut** to about 7,800 words with all v3 appendices moved to a separate supplement (S1-S22, cross-references through `xr-hyper`). Appendix A in the main paper keeps Algorithm 1 and the user-model table, as the editor suggested.
9. **Guard-off rows** in Tab. 2 and Tab. 3; guard presented as an input-validity check that real data do not test (Sec. 4.1, Sec. 6.6, Discussion).
10. **References:** LTT -> Annals of Applied Statistics 2025; Brain2Qwerty v2 -> arXiv:2608.18114; Lévy et al. DOI verified (issue added); conformal selection (Jin & Candès 2023; Gui, Jin & Ren 2024) and ASR confidence (Jiang 2005) added. Every changed or new entry has a verification URL comment in `refs.bib`.

## 2. Handling editor (round-4-editor.md)

### Major

| Item | Status | What we did (where) |
|---|---|---|
| Ed-M1 "repeated deployment" does not test deployment; add cross-day test | **done** | Forward-chaining analysis (R4 `forward-chain/`): designs V1 (fit days 1..k-2, calibrate k-1, test k), V4 (two previous days), V2 (fit days 1-3, calibrate all earlier), V3 (session start: first half of the test day). Sec. 5.3, Sec. 6.2, Tab. 1, Fig. 2a, Tab. S7 (all rules, guard on/off). LTT max: 0-2 of 10-13 days above alpha, none significantly; pooled 0.010-0.027. Plug-in: up to 6/10 days. Contribution 2 reworded to "a time-ordered test of the guarantee on one participant" plus the scope result. Re-splits renamed and described as a Monte-Carlo check under exchangeability (Sec. 5.3, Sec. 6.3, Tab. 2). The "first n trials of the test day" variant is V3 (half a day); the 20-trial session-start CRC result is in S10. |
| Ed-M2 published gate is not stream-only; bonus provenance; sensitivity | **done** | Sec. 4.1 "Gate on a published sentence: a two-decoder agreement signal"; abstract: "published sentence, gated by agreement with our decoder"; Discussion "Strong decoders still need a gate": "agreement with a light reference decoder on the same stream". Bonus: set by hand in commit 3fb8154, never tuned (Sec. 4.1, S11). Sensitivity for bonus 0, 0.5, 1, 2, 4 (Tab. S11): LTT max 0.022-0.039 on the fixed splits, 0.022-0.033 over re-splits. Published sentence alone: 0 commits (= always offer, 18.11 eWPM). |
| Ed-M3 cross-modality and "decoder-agnostic" over-claim | **done** | Title: "stream-level" instead of "decoder-agnostic". Abstract: intracortical first; sEMG and MEG "serve as format and safety checks" in one sentence. Introduction (end of contributions) and Sec. 5.2 say that sEMG/MEG show the format works across devices, not the commit rule. MEG detail moved to S17 (main text keeps 3 sentences in Sec. 6.4). |
| Ed-M4 speed claim ambiguous | **done** | "At little speed cost" removed from abstract, introduction and conclusion. The comparator "same fitted policy without commits" is defined in Sec. 5.1 (lambda = +inf, same fit-A pipeline); gains +0.114 (MC SE 0.005) / +0.510 (0.007) and fixed-split CIs in Sec. 6.3; Gain column in Tab. 2; no-commit row in Tab. 4. Discussion: "within the uncertainty of the user model, and slower than always committing for the published decoder". Always-commit claim limited to the 9-variant table (published 9/9, ours 5/9; Sec. 6.7, Tab. S2). |
| Ed-M5 resampled-split p-value | **done** | Removed from the abstract. Sec. 6.8 reports +0.009 with an overlap-respecting day jackknife CI [+0.005, +0.013] and Holm over 12 comparisons (p = 0.004), "conditional on this data pool", and the 200-split value (+0.003, n.s.). Full 12-row table with Wilcoxon (labelled conditional), jackknife and Holm: Tab. S14. We used the delete-a-day jackknife (whose SE includes the split overlap) rather than the Nadeau-Bengio correction; both address the same problem, and the jackknife was already computed in M3-20. |
| Ed-M6 primary system contains a harmful component; frozen config differs | **done** | Plain-threshold rows in Tab. 2 (re-splits) and Tab. 3 (fixed splits). The plain threshold was run on the control streams (R4 `no-guard/`): 198/300 uniform streams committed on our decoder. We therefore keep the guard, present it as an input-validity check (Sec. 4.1, 6.6, Discussion), give its formulas only in Algorithm 1, and freeze the guarded configuration (Sec. 7). The frozen v4 configuration on the controls: 0/300 frame-shuffled, 0/300 uniform (Tab. S19, `v4-derived/guard_controls.py`). |
| Ed-M7 length | **done** | Main text about 7,800 words incl. floats (v3 about 10,000); abstract 249 words. Cuts applied: (1) abstract; (2) "Metrics and standards" -> two sentences, NWB/BCI2000/OpenViBE/IEEE moved to S18; (3) Sec. 4 stream interface merged into Sec. 3 (one paragraph); (4) online controllers: one sentence in Sec. 4.3, detail in S15; (5) fixed-split drift/Holm history moved to S14; (6) the "not from CRC" paragraph -> two sentences in Sec. 6.4, detail in S7; (7) speed section: one figure and four sentences; (8) MEG -> S17; (9) hardware/latency repetition removed (one sentence in the availability statement); (10) appendices -> separate supplement, Algorithm 1 and Tab. 5 kept in Appendix A. |

### Minor

| Item | Status | Where |
|---|---|---|
| 1 truncated Introduction (unescaped %) | **done** | Introduction rewritten; a script scan of all .tex files (sections, main, supplement, generated tables, TikZ) finds no unescaped % in text. |
| 2 stale Fig. 4 | **done** | Redrawn as Fig. S1 with the LTT max rule and "risk over the calibration mix of sessions"; guard labelled "input validity". |
| 3 Figs 2-3 show plug-in; Fig. 2c compressed | **done** | User-model figure (now Fig. 3) caption starts "plug-in layer, full fit; not the guaranteed rule"; panel (c) uses a symmetric-log axis. The calibration / trade-off figure moved to S12 (Fig. S3) with "full-fit plug-in pipeline; not the guaranteed rule". |
| 4 Fig. 1 axis; commit rate | **partly** | Commit-rate labels added for the plug-in and guaranteed markers. We kept the signed square-root axis: a log axis cannot show the zero-rate always-offer points and the near-1 always-commit points together without an offset that is harder to read. |
| 5 Table 1 overloaded | **done** | v4 Tab. 3: 256-sentence rows and gaze + completion values moved to Tab. S6 and S4; always-offer rows for sEMG moved to Tab. S6. Gaze + completion is now given as point values in S4 (marked as such). Guard-off rows were added (Ed-M6). |
| 6 "> beta = 0" small-sample handling | **done** | Tab. 4 gives ">beta" as "committing re-splits with EAC above beta, k of n" and the share with no commit next to the commit rate. |
| 7 ground truth in a copy task | **done** | Sec. 5.2: the data file has no per-trial participant ratings (keys checked in `src/fidetype/adapters/b2t25.py`), so the cue-based label cannot be checked against the participant's judgement. |
| 8 frame temperature raises per-frame ECE | **partly** | Sec. 6.8 states that we did not resolve why and names the difference between the two criteria. No new analysis. |
| 9 source of 159.3 cpm; 6 s pause | **done** | Sec. 5.1: characters of the cue sentences / sum of the `speech_duration_s` field; the file does not say whether the 6 s pause is included, and we add no time for it, which favours the neural input. |
| 10 fixed-sequence LTT needs no correction | **done** | Sec. 4.2. |
| 11 joint rule uses CRC; frozen config unclear | **done** | Joint LTT replaces max(SGR, CRC max) (Sec. 4.3, Tab. 4); the frozen configuration names it (Sec. 7). |
| 12 seed 2 at the 0.14 boundary | **done** | S5 gives the per-seed gaps 0.254, 0.243, 0.140 (`v4-derived/derived.py`); the boundary sentence is gone from the main text. |
| 13 worked binomial example | **done** | S2: 0/40 -> 0.056, 3/40 -> 0.159 (one-sided exact 90 %); 0.124 and 0.248 at delta/20 (`v4-derived/derived.py`). |
| 14 Huggins "90 % accuracy" | **done** | Discussion: users were asked about accuracy in general; the beta reading is marked as our interpretation. |
| 15 pointer to policy grid; commit hash | **done** | Sec. 7 points to S6 (policy grid). Tags: `paper1-v4-frozen-config` on the v4 commit (the commit hash is in HANDOFF.md and in the commit log; a paper cannot contain the hash of the commit that adds it); `paper1-v3-frozen-config` = 65359dc. |
| 16 lambda-hat notation | **done** | Alg. S1 uses lambda-hat_CRC, lambda-hat_LTT, lambda-hat_joint, lambda-hat_SGR. |
| 17 MEG beam detail | **done** | Moved to S13 / S17. |
| 18 AI-assistance statement | **partly** | Kept as a red author TODO (author decision); listed in how-to-read-this-draft.md. |
| 19 draft header; IOP template | **partly** | "Draft v3 ... not for distribution" and the date line removed. The IOP template switch is left for the submission step (the preamble block marked CLASS in both files); listed as an author decision. |
| 20 code archive | **partly** | Red TODO kept (Zenodo DOI for the paper commit and the per-split item tables); needs the author's go. |

### References (editor Sec. 6)

| Ref | Status | Result |
|---|---|---|
| Jude et al. 2026 volume/issue/pages | **verified** | 29(10):2613-2622 confirmed at api.crossref.org/works/10.1038/s41593-026-02218-y. No change. |
| Lévy et al. DOI | **verified** | doi.org/10.1038/s41593-026-02303-2 resolves to nature.com (Nature Neuroscience 29(10):2438-2444, online 29 Jun 2026; Crossref record). Issue number added. |
| Brain2Qwerty v2 arXiv | **done** | arXiv:2608.18114 exists (arxiv.org/abs/2608.18114; same title and authors, 29 Jun 2026); the entry now cites arXiv. Our round-3 statement "no arXiv version" was wrong. |
| LTT outdated | **done** | Now Annals of Applied Statistics 19(2):1641-1662, 2025, doi 10.1214/24-AOAS1998 (Crossref). Key renamed `angelopoulos2025ltt`. |
| Damri ICLR 2026 title | **declined (checked)** | The ICLR 2026 proceedings page gives "Confident and Adaptive Generative Speech Recognition via Risk Control", without "Conformal"; our entry already has this title. The OpenReview page could not be opened (bot check); the proceedings page is the cited verification URL. |
| Conformal selection (Jin & Candès 2023; Gui, Jin & Ren 2024) | **done** | Added to Sec. 2 and the Discussion as the comparator for the expected error among commits (JMLR 24(244); NeurIPS 37, doi 10.52202/079017-2350). Not run as an analysis (future work, Discussion). |
| ASR confidence (Jiang 2005) | **done** | Sec. 2 (Speech Communication 45(4):455-470). |
| Kim et al. differentiation | **done** | Sec. 2: Kim et al. accept or abstain on single EEG classifications; neither they nor Huang et al. bound the rate of wrong sentences sent. |
| Nadeau & Bengio | **not added** | We used the delete-a-day jackknife instead of a corrected resampled t-test (Ed-M5). |

### Ethics and limitations

| Item | Status | Where |
|---|---|---|
| Trial registration | **done** | End of abstract and the ethics statement: BrainGate2, ClinicalTrials.gov NCT00912041 (verified on clinicaltrials.gov; Card et al. NEJM 2024 names it). |
| Ethics TODO; CC0, consent, IRB, data descriptor | **partly** | Ethics statement now says: secondary analysis, de-identified CC0 data, original trial consent and IRB approval, data descriptor cited. The final wording stays an author TODO (confirm with the JNE office). |

### Must-fix list (editor Sec. 9)
1 done; 2 done; 3 done; 4 done; 5 done (the frozen configuration is now the guarded one, because the plain threshold failed the controls); 6 done; 7 partly (registration done; author TODOs and template switch remain for the author); 8 done; 9 done.

## 3. Statistics reviewer (round-4-stats.md)

### Major

| Item | Status | What we did (where) |
|---|---|---|
| St-M1 re-splits are not deployments | **done** | (a) renamed "random re-splits" throughout; "exchangeable by construction" in Sec. 5.3 and the Tab. 2 caption. (b) forward-in-time analysis added (Tab. 1, Fig. 2a, Tab. S7). (c) contribution 2 now the time-ordered test. |
| St-M2 per-session risk not controlled | **done** | Per-day table (Tab. S8) and Fig. 2b: published day 34 = 0.102 (50 re-splits; 0.098 with 200), above alpha in 94 % of re-splits; fixed splits 8/50 = 0.16 [0.07, 0.29]. Sec. 4.2 "Scope of the guarantee", S21 and the Discussion say that LTT bounds the day mixture. The sentence "the per-deployment guarantee is the one a user experiences" is withdrawn. Remedy: per-session (Mondrian) LTT with >= 45 items per session (feasible here only on day 76) or a session-start block. |
| St-M3 joint rule has no selective guarantee; SGR | **done** | Joint LTT (max of the two p-values, 20-point grid, Bonferroni; R4 `joint-ltt/`) replaces max(SGR, CRC max) in Sec. 4.3, Alg. S1, Tab. 4 and the frozen configuration (secondary rules beta 0.10 and 0.20). LTT-sel is the reference selective controller. SGR: "guarantee as stated in their Theorem 3.2; its bisection chooses the tested thresholds from the data" (Sec. 4.3, S21). The recommendation of the old joint rule is removed. |
| St-M4 rule chosen after the splits; "(allowed: 10 %)"; App. R population risk | **done** | (a) abstract: "The rule was chosen after the random re-splits below; all inference is exploratory"; also Sec. 4.2 "Primary rule". (b) "(allowed: 10 %)" removed; shares with CP intervals in the abstract, Sec. 6.3 and Tab. 2 (all ">alpha" shares now have CIs). The LTT-vs-CRC ranking is qualified with McNemar (50 re-splits: p = 0.25 ours, 0.031 published). (c) with-replacement population exceedance: 4.7 % [3.8, 5.7] / 4.1 % [3.3, 5.1] (S10), replacing the biased 0.5 % / 1.5 %; population column in Tab. 2. |
| St-M5 reuse reported selectively | **done** | All 12 comparisons with Wilcoxon (conditional), jackknife and Holm in Tab. S14. Main text (Sec. 6.8): "on our decoder ... conditional on this data pool", jackknife Holm p = 0.004; no p-value in the abstract. The Discussion paragraph on reuse was cut; the principle stays in Sec. 4.3 ("Separate data"). |
| St-M6 decoder grid tuned on trials later used in the re-splits | **partly** | Listed as exception (2) in S19 and in Sec. 4.3. The optional re-tune on fit-A for 5-10 re-splits was not run (CPU time; the R3 check on the two fixed splits selected the same setting). |

### Minor

| Item | Status | Where |
|---|---|---|
| m1 0/816 bound | **done** | Tab. 3 caption: 0.0037 (one-sided). |
| m2 MEG CIs | **done** | Tab. 3: trust [3.01, 3.44], gaze [3.02, 3.31]. The teaser figure already used the unified two-way bootstrap (`base_row` in `make_figures.py`); the unused `meg_rows` helper, which read the sentence-bootstrap interval, now also reads the unified file. |
| m3 left-continuity argument | **done** | Sec. 4.2 (CRC bullet): the threshold is a minimum over a finite set of scores, so the bound holds for "commit if s >= lambda-hat" as implemented. |
| m4 Alg. 1 conditions | **done** | Alg. 1: empty list -> abstain before the guard; offer needs "C does not contain the 'other' option". The optional maximum commit set size is mentioned in S2. |
| m5 SGR "< beta" | **done** | Alg. S1 says "< beta (strict, as in the code)". |
| m6 snapping 0.27 % / 0.38 % | **done** | Sec. 5.3. |
| m7 reference range per split | **done** | S14: 0.029-0.071 (split B, published) and 0.014-0.022 (split A). |
| m8 Tab. 4 over committing splits | **done** | Tab. 4 ">beta" column gives "k of n committing re-splits". |
| m9 sEMG test fixed | **done** | Sec. 5.3 and Tab. S9 caption. |
| m10 sEMG cross-session no-commit share | **done** | Sec. 6.3 and Tab. S9 caption (34 %). |
| m11 pure CRC stops at the lowest eligible score | **done** | Sec. 4.2 (CRC bullet) and S7 (0.3075; 20 vs 22 wrong). |
| m12 "CRC met the target only on average" | **done** | Removed from the abstract; Sec. 6.3: "CRC met its own target, the mean ..., and, as designed, many single re-splits were above alpha". |
| m13 SGR statement unit and assumption | **done** | S21. |
| m14 wild-cluster / BCa intervals | **declined** | Optional; not run. The day-level sign tests remain the check on the 14-cluster bootstrap. |

### Reproducibility notes (St-Sec. 7)
- Figure PDFs are now byte-identical across re-runs (`metadata={"CreationDate": None}` in `make_figures.py`; checked on `fig_deploy.pdf`).
- The per-split item tables are derived numbers in a local cache; the availability statement now names them as part of the planned Zenodo archive (author TODO).

### Must-fix list (stats Sec. 9)
1 done; 2 done; 3 done; 4 done; 5 done; 6 done (m1, m2); 7 done as a listed exception (re-tune not run).

## 4. Items not fully addressed (and why)
- **Author decisions** (red TODOs): authors and affiliations; funding; AI-assistance wording; final ethics wording; Zenodo archive DOI. IOP template switch at submission.
- **Per-session control** is named as the remedy but not achieved: per-day LTT needs >= 45 calibration items per day, which this design cannot supply (S9).
- **Decoder-grid re-tune on random re-splits** (St-M6), **wild-cluster/BCa intervals** (St-m14) and **conformal selection as an analysis** were not run.
- **Frame-temperature ECE paradox** (Ed minor 8): explained only as a difference of criteria.
- **Fig. 1 axis** kept as signed square root (reason above).

## 5. New numbers computed in this round (M3-21)
- Frozen v4 configuration (guard + LTT max, split A) on the B2T controls: ours 29/300 real, 0/300 frame-shuffled, 0/300 uniform; published 115/300 real, 0/300, 0/300; refit reproduces the committed split-A test rates 0.0245 / 0.0294 (`v4-derived/guard_controls.*`).
- Selective-bound worked example (0/40 -> 0.056; 3/40 -> 0.159), MEG seed gaps (0.254, 0.243, 0.140), published split-A share of always-commit eWPM (95.1 %) (`v4-derived/derived.json`).
- All other numbers come from the committed M3-20 files.
