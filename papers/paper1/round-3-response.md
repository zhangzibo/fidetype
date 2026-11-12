# Paper 1: response to review round 3 (draft v2 -> draft v3)

- **Date:** 2026-11-12. Tracker task: M3-18.
- **Draft:** `papers/paper1/draft-v3.pdf` (37 pages: main text pages 1-17 including the ethics statement, references, appendices A-Q). LaTeX in `latex/`.
- **Reviews answered:** `reviews/round-3-editor.md` (Ed-) and `reviews/round-3-stats.md` (St-).
- **New numbers:** all come from `experiments/2026-11-12-paper1-r3-analyses/` (M3-17). One small new script: `v3-derived/` (paired eWPM cost of the guaranteed rule over the 50 repeated splits).
- **New title:** "When should a neural text-entry decoder commit? Risk-controlled commits from a decoder-agnostic trust layer" (15 words; was 25).
- Status words: **done**, **partly** (some of the request is done; the reason for the rest is given), **declined** (with reason).
- Section numbers refer to draft v3. "Tab." and "Fig." numbers are v3 numbers.

## 1. Main changes in one list

1. The primary, guaranteed row is now **LTT with the max rule on clean calibration data**. Abstract, Fig. 1, Tab. 1, Tab. 2, Sec. 7.2, Discussion and Conclusion lead with it. The plug-in row is labelled "no guarantee".
2. New Tab. 2: **50 repeated deployment splits** (fit-A / clean calibration / test re-drawn and the whole pipeline refitted). CRC holds as a mean (0.046 / 0.049) but 34-42 % of single deployments exceed alpha. LTT max rule: mean 0.030 / 0.031, above alpha in 8 % / 2 % of deployments.
3. The 0.0588 -> 0.0245 change is now attributed correctly: it comes from the policy-grid choice on fit-A. Temperatures and CRC contribute nothing (Sec. 7.2).
4. New Sec. 5.4, Sec. 7.3 and Tab. 3: **selective-risk controllers** (SGR, LTT-sel, joint). Beta = 0.10 is reachable only for the published gate.
5. The data-reuse claim is corrected: the effect is real but small and only on our decoder (+0.009, p = 0.003). "Never significantly above" is removed. Holm-corrected p-values are given. The power is stated (Sec. 7.4, Tab. 16).
6. sEMG near-variant exclusion is reported in Tab. 1, Sec. 7.2, Limitation 2 and App. I.
7. MEG: no sentence-level guarantee is possible; the paper says so. Sentence-grouped results are in App. K. The three seeds are reported (Sec. 7.1, Tab. 7).
8. One bootstrap (seed 20261112, B = 2000) for every CI; day sign tests; exact zero-event bounds; run time per decision.
9. Algorithms 1-2 (App. B) and full definitions (Sec. 5) let a reader re-implement the layer.
10. AAC / BCI user-priority references (all verified on the web; verification URL in a comment above each `refs.bib` entry).
11. Main text restructured: 3 contributions; format, devices table, architecture figure, online details, controls figure and the clean-vs-reused table moved to the appendix.

## 2. Handling editor (round-3-editor.md)

### Major

| Item | Status | What we did (where) |
|---|---|---|
| Ed-M1 headline is not risk-controlled; 0.059 -> 0.0245 credited to CRC | **done** | Abstract, Fig. 1, Tab. 1 and Sec. 7.2 lead with the LTT max rule (repeated mean 0.030 / 0.031; fixed splits 0.025 / 0.052 and 0.029 / 0.031). Plug-in labelled "no guarantee". Sec. 7.2 states that the change comes from the fit-A policy grid (commit threshold 0.3 / guard 0.1 vs 0.5 / 0.5), that full-fit temperatures with the fit-A policy also give 0.0245, and that CRC changed nothing (not binding in split A; bound 0.0075). "Bounds" is used only for guaranteed rows. |
| Ed-M2 Table 2 shows pure CRC; no recommended rule | **done** | One recommended rule (LTT max rule; CRC max rule next to it) stated in Sec. 5.3 with the reason. Tab. 1 shows the guaranteed rule per condition; pure CRC / LTT moved to App. G (Tab. 9) and labelled as filling the risk budget. |
| Ed-M3 evaluate a selective-risk controller | **done** | Sec. 5.4 (SGR, LTT-sel, joint), Sec. 7.3, Tab. 3, Fig. 3c with a beta = 0.10 line. Result: beta = 0.10 only for the published gate (11 % commits, EAC 0.069, none in 64 % of deployments); ours, sEMG and MEG commit nothing. The joint rule is recommended (Discussion). |
| Ed-M4 clinical premise needs BCI/AAC evidence; Card et al. TODO | **done** | Introduction paragraph 2 (Huggins 2011, 2015; Blabe 2015; Kubler 2014; Valencia 2023; Kane 2017). Card et al. interaction resolved in Sec. 2: sentence finalised by a 6 s pause or an eye-gaze button, read aloud, rated afterwards; no confirmation before text-to-speech (source: open preprint of Card et al.; NEJM supplement was not accessible). Discussion: who sets alpha and beta, how to explain it, context dependence, semantic-severity loss as next target. Kunz 2025 and Wairagkar 2025 cited. |
| Ed-M5(a) second intracortical participant | **declined (for now)** | New data and decoder work; outside the scope of this revision (CPU only). Named in Limitation 1 and in the confirmatory-test paragraph (Sec. 8). |
| Ed-M5(b) repeat the fit/test assignment | **done** | 50 repeated day-stratified splits, Sec. 6.3, Tab. 2, Sec. 7.2. |
| Ed-M5(c) per-day results | **partly** | Day sign tests in Sec. 7.2 (12 of 13 days, 14 of 14). The per-day table is in `repeated-splits/results/tables.md`; no per-day figure was added (page limit). |
| Ed-M5(d) retitle | **done** | New title. It no longer lists three modalities. The single participant is in the abstract (Main results, first sentence), Fig. 1 panel title and the first sentence of the Discussion. |
| Ed-M6 sEMG leakage exclusion mis-described | **done** | Limitation 2 now separates the LM rebuild (<= 0.04 eWPM) from the test-set exclusion (8.02 -> 6.97, 4.68 -> 4.08, 4.08 -> 3.69; cross-subject gaze now faster, [-0.66, -0.23]). Rows "trust, 256 non-templated" in Tab. 1; full analysis in App. I with the reason why 551 stays primary. |
| Ed-M7 freeze one configuration, test on untouched data | **partly** | Sec. 8 "A frozen configuration for a confirmatory test" writes the configuration down; git tag `paper1-v3-frozen-config`. All current results are called exploratory (Sec. 6.4). No untouched data were evaluated (needs Ed-M5a or new sessions). |
| Ed-M8 remove TODOs | **partly** | Filled: MEG seeds (Sec. 7.1, Tab. 7), Card et al. (Sec. 2), run time (Sec. 8, Sec. 11). Remaining 5 TODOs are author decisions we cannot make: author list, ethics wording, archive DOI, funding, AI-assistance wording. |
| Ed-M9 focus and restructure | **done** | 3 contributions (format and release now one sentence). Format section shortened to one paragraph; devices table and architecture figure moved to App. L. Sec. 7.4 recast as a "clean vs reused calibration" comparison without history. Tab. 1 shows the primary policies; the rest in App. G. Single-participant caveat is the first sentence of the Discussion. Online details moved to App. M. |

### Minor

| # | Status | Where / what |
|---|---|---|
| 1 sEMG term; composed; per-decoder statement | **done** | Abstract uses "sEMG" and "composed"; per-decoder speed claims removed from the abstract. |
| 2 user-model statement on gain over always commit | **done** | Sec. 7.5: disappears with miss 0 and symmetric offers at miss 0.05; remains at miss 0.2 (CIs given). |
| 3 silent-error range | **done** | Sec. 7.5: "up to 0.17, except on MEG". |
| 4 refitted wrong-commit rates not shown | **partly** | Sec. 7.5 gives the count (43 of 48) and the 5 changes. No new figure column (space). |
| 5 sentence-temperature CI | **done** | Sec. 7.6: paired [+0.001, +0.036]. |
| 6 500 vs 200 splits; Fig. 8 delta sentence | **done** | App. Q names each split set; Fig. 8 caption rewritten. |
| 7 9 of 18 participants | **done** | App. Q: session-calibrated; one participant has only 11 test sentences. |
| 8 replay "39 of 39 (CRC)" | **done** | App. L: labelled as the earlier reused-data CRC (160 commits, 0.048). |
| 9 silent 0.002; duplicate CIs | **done** | Silent 0.003; one bootstrap for all CIs. |
| 10 "Exch. ref." notation | **done** | Tab. 16 uses "0.018 (0.014-0.022)". |
| 11 Table 1 column order | **done** | Devices table: intracortical, sEMG, MEG. |
| 12 159.3 cpm copy task | **done** | Sec. 6.1. |
| 13 LP1 non-BCI, variation | **done** | Sec. 6.1. |
| 14 MEG insertion bonus | **partly** | Explanation shortened to one sentence (Sec. 6.2). We kept the harness setting because the seed runs use it; the validation-tuned beam also commits nothing (3.14 eWPM). |
| 15 App. "longer schedule" sentence | **done** | App. K: "We selected the training schedule by validation CER." |
| 16 shorten guard in main text | **done** | Sec. 5.2 one sentence; formulas in Algorithm 1. |
| 17 "96 % of speed" wording | **done** | Sec. 8: "96 % of the always-commit eWPM under the main simulated user". |
| 18 line counts | **done** | Removed from the main text; App. L gives 412 / 568 / 156 physical lines with the definition. |
| 19 notation for selective risk | **done** | Prose: "error among commits"; tables: "EAC" (Sec. 3, Tab. 4). |
| 20 audit figure, item-level quotation | **done** | Fig. 6 caption and Sec. 11: public CC0 copy-task cue, not the participant's words; CC0 allows quotation. |
| 21 personal repo URL / DOI | **partly** | DOI is an author TODO (Sec. 11). |
| 22 colours across figures | **partly** | Fig. 1 now uses green for the guaranteed rule and blue for plug-in. A full colour audit of Figs 2-3 was not done. |

### Figures and references

| Item | Status | Where / what |
|---|---|---|
| Fig. 1 hides the safety region; no CRC marker; labels collide | **done** | Signed square-root y-axis; alpha labelled; guaranteed-rule markers (green); commit rate and EAC in the caption; labels moved. |
| Fig. 2 merge with decision flow | **declined** | Architecture moved to App. L instead (Fig. 5); decision logic is now Algorithm 1. |
| Fig. 3 sign convention, split axes, "(miss 0.05)" | **partly** | Panel titles say "> 0: trust faster"; row label "symmetric (miss 0.05)". Panel (c) axis not split. |
| Fig. 4a published gate ECE; reliability diagram | **partly** | Published ECE 0.102 -> 0.058 in Sec. 7.6 text; no reliability diagram and no ECE CIs (not computed). |
| Fig. 4b / 4c operating points; promote 4c | **partly** | beta = 0.10 line added to 4c; selective results now have their own Tab. 3. Operating points not drawn. |
| Fig. 5 (controls) | **partly** | Moved to App. O; zero-event bounds added in Sec. 7.7. Bars not redesigned. |
| Ref keys achituve / dataset authors | **done** | Dataset creator corrected to Zariffa (DataCite record). |
| Ref Jude 2026 full authors | **done** | 16 authors from Crossref. |
| Refs P2731/P2794 stray ", ." | **done** | URL moved to the `url` field; year added. |
| Ref CRC arXiv DOI | **done** | arXiv DOI removed; ICLR entry with arXiv note. |
| Ref LSL no DOI | **no change** | The entry has the bioRxiv DOI 10.1101/2024.02.13.580071. |
| Ref B2Q v2 web PDF | **no change** | We found no arXiv / bioRxiv version. |
| Missing works (SGR, Bates RCPS, Huggins, Kubler, Valencia, Kane, Koester & Levine, Moses, Metzger, Kunz, Wairagkar) | **done** | All added and verified (Crossref / PubMed / publisher; URL comment above each entry). Peters et al. 2015 was not added (not verified). |

## 3. Statistics reviewer (round-3-stats.md)

### Major

| Item | Status | What we did (where) |
|---|---|---|
| St-M1(a) abstract false; drift claims too strong | **done** | "Never significantly above" removed. Sec. 7.4: split A p = 0.012 (day-stratified 0.014), Holm 0.072 (0.084); no test significant after correction; "we claim neither within-day drift nor that data reuse caused the earlier 0.0625"; drift, reuse and split variation cannot be fully separated. Section title changed. |
| St-M1(b) controlled reuse test | **done** | 50 paired repeats: pure CRC reused - clean +0.0091 (Wilcoxon p = 0.003; 35 of 49) on ours; +0.0009 (p = 0.72) published; sEMG -0.0016 / +0.0073 (sign p 0.47). Sec. 7.4, Tab. 2 last row. |
| St-M1(c) power statement | **done** | Sec. 7.4: one deployment detects 0.035 (ours), 0.038 (published), 0.040-0.057 (sEMG) at 80 % power; reference range 0.029-0.071. |
| St-M1(d) day-stratified reference | **done** | Sec. 6.3, Sec. 7.4. |
| St-M2 CRC not binding; only split A shown | **done** | Both splits in Tab. 1 (guaranteed rule) and Tab. 16; "Bound" column in Tab. 16; binding shares over 50 repeats in Sec. 7.2 (max rule changed decisions in 54 % / 34 %); Sec. 7.2 sentence rewritten as suggested; pure CRC vs max rule stated. |
| St-M3 headline from the plug-in | **done** | LTT max rule is primary (as suggested). |
| St-M4(a) MEG clustered by sentence | **done** | Sec. 7.2 and App. K: sentence-level CRC needs >= 19 sentences (LTT 45); data have 5 / 11 / 17; "no guarantee for new sentences"; sentence-grouped results (0.016-0.019, p95 <= 0.038; EAC 0.91-0.94). Instance-level random MEG splits remain only in App. Q as an implementation check. |
| St-M4(b) sEMG calib different decoders | **done** | App. N and Sec. 5.3 (short): stated as a design property. Not re-calibrated on test-decoder items. |
| St-M4(c) calibration overlaps tuning data | **partly** | B2T: re-tuning on fit-A selects the same grid point; rows unchanged (App. N). MEG checkpoint selection on validation: stated, not redone (needs GPU). |
| St-M4(d) sEMG online order artificial | **done** | App. M and Limitation 4. |
| St-M4(e) LTT i.i.d., sampling without replacement | **done** | App. N. |
| St-M5 one realisation; CIs omit fit variance | **done** | 50 repeated deployments (Tab. 2); every caption and Sec. 6.4 say CIs are conditional on the fitted pipeline and threshold; MEG seeds reported. |
| St-M6.1 few clusters | **done** | Day sign tests (Sec. 7.2, Sec. 7.6); sEMG participant sign test (Sec. 7.2). |
| St-M6.2 zero-event bounds | **done** | Exact one-sided 95 % bounds: 0/300 -> 0.0099, 0/200 -> 0.015, 0/637 -> 0.0047, 0/551 -> 0.0054 (Tab. 1 caption, Sec. 7.2, Sec. 7.7). |
| St-M6.3 multiplicity | **done** | Holm on the six tests (Tab. 16); "significantly" not used elsewhere. |
| St-M6.4 p-value definition | **done** | (k+1)/(B+1) in Sec. 6.3 and Tab. 16 caption. |
| St-M6.5 post-hoc endpoints | **done** | Sec. 6.4: endpoints named in revision 1 after the first runs; all inference exploratory; the choice of the LTT max rule as primary row made in revision 3. |
| St-M6.6 CIs differ between tables | **done** | One bootstrap (seed 20261112, B = 2000) for Tab. 1, Tab. 9, Tab. 16, ablation, user model, leakage; figures regenerated from the unified files. |
| St-M6.7 small commit counts | **done** | Counts when fewer than 30 commits (2/21, 2/10, 1/6, 18/19). |
| St-M7 re-implementability | **done** | Algorithm 1 (decision, guard formulas, per-character confidence), Algorithm 2 (temperatures, conformal set, policy grid fit with tie rule, CRC, LTT, SGR, max rule, fit sets); grid values in App. F; s_i defined in Sec. 5.3; conformal set defined in Sec. 5.2; notation table extended (App. A). |

### Minor

| # | Status | Where / what |
|---|---|---|
| m1 0.66 -> 0.65 | **done** | The number left the abstract; Tab. 1 values unchanged (18.77 vs 18.11). |
| m2 49/54 -> 43/48 | **done** | Sec. 7.5 with the 5 changes listed. |
| m3 500 vs 200 splits | **done** | App. Q. |
| m4 Tab. 3 notation | **done** | Tab. 16. |
| m5 LTT > CRC in ours-A | **done** | Shown with the "Bound" column (0.0075: not binding) in Tab. 16; Sec. 7.2 explains non-binding. |
| m6 aci delay | **done** | App. P. |
| m7 9 of 18 | **done** | App. Q. |
| m8 "first 142 sentences" | **done** | Sec. 6.3: "a random half". |
| m9 K = 10 vs 11 | **done** | Sec. 3. |
| m10 ECE / AUROC CIs; tau_s at bound | **partly** | tau_s bound now in Sec. 5.1 and Sec. 7.6 text. CIs not computed (stated). |
| m11 rolling-window maxima | **done** | App. M: 0.06-0.08 / 0.10-0.12 / 0.12-0.18; 18 % of aci windows above alpha (ours, split A). |
| m12 all noticed-only runs | **done** | App. M: 0.0270, 0.0527, 0.0502, 0.0581, 0.0563 (range 0.027-0.058 in Sec. 7.4). |
| m13 caption "conditional on the calibration set" | **done** | Tab. 16 and Tab. 1 captions. |
| m14 max rule validity, both cases | **done** | Sec. 5.3. |
| m15 adapter lines 156 | **done** | App. L with definition. |
| m16 TODOs | **partly** | See Ed-M8. |
| m17 c_i equals simulated wrong commit | **done** | Sec. 3. |
| m18 trust vs CRC rows use different pipelines | **done** | Sec. 7.2 attribution paragraph. |
| m19 left-continuity | **done** | One sentence in Sec. 5.3. |

## 4. Items not fully addressed (summary)

| Item | Reason |
|---|---|
| Second intracortical participant / confirmatory test (Ed-M5a, Ed-M7) | Needs new data and decoder work; next step. Frozen configuration written and tagged. |
| MEG checkpoint re-selection without calibration sentences (St-M4c) | Needs GPU retraining. Stated in App. N and Limitation 2 scope. |
| Author TODOs (authors, ethics wording, DOI, funding, AI wording) | Author decisions. |
| ECE / AUROC CIs, reliability diagram (St-m10, Ed Fig. 4a) | Not computed; stated in Sec. 7.6. |
| Per-day figure, refitted wrong-commit column in Fig. 2, colour audit, Fig. 5 redesign | Page budget; numbers are in the text or repository. |

## 5. Numbers computed in this revision

Only one new script: `experiments/2026-11-12-paper1-r3-analyses/v3-derived/run.py` (inputs: committed `repeated-splits/results/per_split.json`). It gives the paired eWPM gain of the LTT max rule over the same policy without commits: +0.114 [+0.063, +0.164] (ours) and +0.510 [+0.439, +0.599] (published), positive in 50 of 50 splits; and its cost against the CRC max rule (-0.010 / -0.036 eWPM). All other numbers come from the M3-17 result files or earlier committed outputs.
