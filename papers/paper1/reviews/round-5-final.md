# Paper 1, review round 5 (final pre-submission check)

- **Manuscript:** "When should a neural text-entry decoder commit? Risk-controlled commits from a stream-level trust layer", draft v4 (`papers/paper1/draft-v4.pdf`, 22 pages; `draft-v4-supplement.pdf`, 17 pages; LaTeX in `papers/paper1/latex/`).
- **Target venue:** Journal of Neural Engineering (JNE).
- **Reviewer role:** referee doing a final pre-submission check (numbers, consistency, claims, references, language, journal requirements). I read both PDFs and the LaTeX sources before I opened `round-4-response.md`. I used that file only for the check in Section 7.
- **Date:** 2026-11-12. Tracker task: M3-22.

## 1. Recommendation

**Minor revision.** The science is stable and the claims are mostly in line with the evidence. I found no wrong number among the 32 that I traced. I found three framing or consistency problems that a JNE referee would flag (issues 1-3), and a set of small writing, formatting and reference items. All of them are writing fixes. None needs a new experiment. After these fixes, the manuscript is ready to submit, apart from the author decisions (Section 8).

## 2. Number trace (32 numbers)

Every value below matches its committed source file (rounding as printed). Paths are relative to `experiments/`.

| # | Location in v4 | Value | Source | OK |
|---|---|---|---|---|
| 1 | Abstract, Tab. 3 | always commit wrong 61% / 19% (0.610 / 0.194) | `2026-11-12-paper1-r3-analyses/unified-ci/results/ci.json` (0.6103, 0.1936) | yes |
| 2 | Abstract, Tab. 1, Sec. 6.2 | pooled LTT max 1.0-2.7% (0.010-0.027) | `r4/forward-chain/results.md` | yes |
| 3 | Abstract, Sec. 6.3, Tab. 2 | 4/50 = 0.08 [0.02, 0.19]; 1/50 = 0.02 [0.001, 0.11] | `r4/population-risk/results.md`; CP recomputed (0.022-0.192; 0.0005-0.106) | yes |
| 4 | Abstract, Tab. 2 | commit 15% / 39%; EAC 21% / 8% | `r4/joint-ltt/results/tables.md` R50 LTT max (0.147 / 0.392; 0.207 / 0.078) | yes |
| 5 | Abstract, Sec. 6.6 | 198 of 300 uniform streams (plain + LTT max, ours) | `r4/no-guard/results.md` | yes |
| 6 | Abstract, Sec. 6.3, Tab. S8 | day 34 about 10% (0.102; > alpha in 94%) | `r4/per-day/results.md` | yes |
| 7 | Sec. 6.3, Tab. S8 | fixed splits 8/50 = 0.16 [0.07, 0.29] | `r4/SUMMARY.md` item 2; CP recomputed | yes |
| 8 | Tab. 1 | ours V1 plug-in 5, CRC max 4, LTT max 2 of 12; commit 0.11 | `r4/forward-chain/results.md` | yes |
| 9 | Tab. 1 | published V2 joint LTT commit 0.06 (0.064) | `r4/forward-chain/results.md` | yes |
| 10 | Sec. 6.2 | highest single day 0.060 | `r4/forward-chain/results.md` | yes |
| 11 | Sec. 6.2 | 2 of 12 days, CP 0.02-0.48 | `r4/forward-chain/results.md` | yes |
| 12 | Sec. 6.3 | population exceedance 0.026 / 0.014 | `r4/population-risk/results.md`; Tab. 2 | yes |
| 13 | Sec. 6.3, S10 | McNemar p = 0.25 / 0.031 (3 and 6 discordant pairs) | recomputed: 2 x 0.5^3, 2 x 0.5^6 | yes |
| 14 | Sec. 6.3 | gains +0.114 (SE 0.005), +0.510 (SE 0.007) | `r4/cleanup/results.md` | yes |
| 15 | Sec. 6.3 | fixed-split gains +0.058 [0.034, 0.090], +0.125 [0.077, 0.188], +0.537 [0.439, 0.636] | `r4/cleanup/results.md` | yes |
| 16 | Tab. 3 | ours split A 20/82 commits wrong; 0.025; commit 0.10 | `r3/deployable-rule/results.md` (0.0245, 0.100) | yes |
| 17 | Tab. 3 | ours split B 0.052 (42/816 = 0.0515) | `r3/deployable-rule/results.md` | yes |
| 18 | Tab. 3 | published split A / B 0.029 / 0.031 (24/816, 25/816) | `r3/deployable-rule/results.md` | yes |
| 19 | Tab. 3 | zero-event bounds 0.0037 / 0.0054 / 0.0047 | recomputed 1 - 0.05^(1/n) | yes |
| 20 | Sec. 6.4 | sEMG trust - gaze [+2.71, +4.91] | `r3/unified-ci/results.md` | yes |
| 21 | Tab. 4, Sec. 6.5 | joint LTT beta 0.10: 0.072 (0.76), EAC 0.059, 0 of 12 | `r4/joint-ltt/results/tables.md` (published, guard, R50) | yes |
| 22 | Tab. 4, Sec. 6.5 | joint LTT beta 0.20: 0.318, EAC 0.062; LTT-sel 0.564, marginal 0.074, 0.76 | same table | yes |
| 23 | Sec. 6.5 | split A beta 0.20: commit 0.32, EAC 0.057 [0.032, 0.093] | `r4/joint-ltt/results.md` (fixed splits) | yes |
| 24 | Sec. 6.6, Tab. S19 | frozen v4: 0/300 shuffled and uniform; 29 and 115 of 300 real | `r4/v4-derived/results.md` | yes |
| 25 | Sec. 6.6 | guard off full fit 0.059 -> 0.036, [-0.035, -0.011], sign p = 0.021 | `r3/unified-ci/results.md` | yes |
| 26 | Sec. 6.8 | ECE 0.448 -> 0.067; AUROC 0.797 [0.773, 0.819], 0.710 [0.678, 0.744] | `r4/ece-auroc/results.md` | yes |
| 27 | Sec. 6.8, Tab. S14 | reuse +0.009, jackknife [+0.005, +0.013], Holm 0.004 | `r4/reuse/results.md`, `reuse.json` | yes |
| 28 | Tab. S14 | Wilcoxon 0.0027 (Holm 0.027) | `reuse.json` (0.002747); `results.md` prints 0.0028 (rounding in the md file only) | yes |
| 29 | Availability | 0.18-0.30 ms, 95th pct <= 1.06 ms, decoders 45-232 ms | `r3/runtime/results.md` | yes |
| 30 | Discussion | 95% of always-commit eWPM (18.65 / 19.61) | `r4/v4-derived/results.md` (95.1%) | yes |
| 31 | Sec. 4.2 | CRC n >= 19; LTT n >= 45 | recomputed: 1/(n+1) <= 0.05; 0.95^n <= 0.1 | yes |
| 32 | S6 | policy grid 1,980 points (11 x 5 x 6 x 3 x 2) | recomputed | yes |

`r3` = `2026-11-12-paper1-r3-analyses`, `r4` = `2026-11-12-paper1-r4-analyses`.

Also checked: all values in Tab. 3 ("k/n" columns against the rates), Tab. 1 EAC against pooled rate / commit rate, Tab. S7 against `forward-chain`, "4 of 6 conditions" against Tab. S13, "54 condition-variant pairs" (6 x 9), and the abstract word count (249 words by `papers/paper1/wordcount.py`).

## 3. Internal consistency

- No "??" in either PDF. Builds of v4 report no undefined or multiply defined references or citations.
- All main-to-supplement references resolve to the right item (S4, S7, S10, S11, S12, S15-S19, S21; Tables S1, S3-S9, S11, S13, S14, S20; Figures S3, S6; Algorithm S1). Supplement-to-main references (Table 5, Sections 6.3/6.6) are right.
- Problems: issues 4, 5, 6, 8, 9, 10, 13, 14 below.

## 4. Claims against evidence

- **Guarantee scope.** Correct and consistent: "bounds the risk over the mix of days, not each day" (Sec. 4.2, 6.3, Discussion, Limitations, S21, abstract).
- **Per-day scope.** Correct. The day-34 result is in the abstract, Fig. 2b, Sec. 6.3, Tab. S8.
- **Guard / control finding.** The control result is correct (0/300 with the guard; 198/300 without it, our decoder). The statement about the guard on real data is overstated (issue 1).
- **Stream-level framing.** Correct. The paper says that sEMG and MEG test the format, not the commit rule (Sec. 1, 5.2), and that the published gate is a two-decoder agreement signal (Sec. 4.1). One abstract phrase mixes the gate into the always-commit baseline (issue 2).
- **Speed.** Correct and hedged: about 1% and 3%, depends on the user model, always commit is faster on the published decoder (Sec. 1, 6.3, 6.7, Discussion).
- **Pre-registration / exploratory status.** Correct: "all inference is exploratory" (abstract, Sec. 5.4, Sec. 7).

## 5. References

- All 76 (main) and 20 (supplement) printed references are cited. 13 entries in `refs.bib` are never cited; `unsrtnat` does not print them, so they are not orphans in the PDFs (no change needed).
- Web spot-check (6): Wolpaw et al. 2002 (Clin. Neurophysiol. 113(6):767-791, doi 10.1016/S1388-2457(02)00057-3; issue and DOI missing in v4); Card et al. data (Dryad doi 10.5061/dryad.dncjsxm85; DOI present in `refs.bib` but not printed); Jude et al. 2026 (Nat. Neurosci., doi 10.1038/s41593-026-02218-y; correct); Damri and Laufer-Goldshtein, ICLR 2026 (OpenReview ck5T7QeiDh; correct, see issue 16); Wilson et al. (Nat. Biomed. Eng., doi 10.1038/s41551-025-01536-z, online Dec 2025; correct); Zariffa, Borealis dataset (doi 10.5683/SP3/KV65VI, v1.0, 2024, CC BY 4.0; DOI not printed). Extra checks: Willett et al. 2023 (Nature 620(7976):1031-1036), Cai et al. 2024 (Nat. Commun. 15:9449), Metzger et al. 2022 (Nat. Commun. 13:6510): volume and pages missing in v4. Lévy et al. 2026 (doi 10.1038/s41593-026-02303-2) was not found by the search engine; the Crossref check recorded in `refs.bib` (round 4) stands.

## 6. Issues

Severity: **M** = must fix before submission (a referee would flag it); **m** = minor; **c** = cosmetic or information only.

| # | Sev. | Location | Issue | Fix |
|---|---|---|---|---|
| 1 | M | Sec. 6.6 (last sentences), Discussion "A commit rule needs an input-validity check", Limitation 3 | "The re-splits and time-ordered tests above show the same direction" and "it raised wrong commits on real data" overstate the evidence. Guard off vs on: re-splits ours 0.031 vs 0.030 (published 0.024 vs 0.031); time order ours V1 0.018 vs 0.022 but V2 0.028 vs 0.027 and V3 0.018 vs 0.015; fixed split A ours 0.040 vs 0.025 (guard off higher). Only the full-fit pipeline shows a significant rise (0.036 -> 0.059). | Say: the guard did not lower wrong commits on real data; it raised them in the full-fit pipeline; elsewhere the guard-off rates were lower on the published gate and similar on our decoder (higher in fixed split A). |
| 2 | M | Abstract, Main results | (a) "19% (published sentence, gated by agreement with our decoder)" attaches the gate to the always-commit baseline, which has no gate. (b) "The rule committed 15% and 39% ...; 21% and 8% of commits were wrong" does not say that these are re-split means. (c) "A plain confidence threshold committed 198 of 300 no-information streams" does not say "our decoder". | Rewrite the three sentences; keep <= 250 words. |
| 3 | M | Sec. 7, last paragraph | "tagged paper1-v4-frozen-config ... on the commit that adds this draft (draft v4)" becomes false in any later version. | "on the commit that added draft v4; later versions changed only the text". |
| 4 | m | Sec. 1, contribution 1 | "Algorithm SS1": the source writes `S\ref{}` and the label already carries the prefix S. | Use `\ref` only. |
| 5 | m | Supplement contents | Section numbers S10-S22 run into their titles ("S10Random re-splits"; 13 overfull boxes). | Widen the number box of the TOC. |
| 6 | m | Supplement S6 | The policy-grid sentence runs 42 pt into the margin (one long inline set). | Allow line breaks (split the sets). |
| 7 | m | Sec. 5.1; Table 5 | "4.5 s ... both values are matched to one eye-gaze user"; Table 5 "sum matched to 4.7 s". The model gives 4.5 s, the measurement is 4.7 s, so they are not matched. | "close to the measured 4.7 s". |
| 8 | m | Sec. 4 (first paragraph) | "fitted values and the policy grid: Table S5": the grid is in the text of Section S6, not in Table S5. | "Table S5 and Section S6". |
| 9 | m | Supplement, first paragraph | "Tables 1-4 ... point to the main paper": the main paper also has Table 5. | "Tables 1-5". |
| 10 | m | Sec. 6.6 | "the full-fit layer and sEMG were the same (0 of 200 sentences per control; bound 0.015)": the full-fit B2T layer has 300 streams per control, not 200. | Separate the two counts. |
| 11 | m | Sec. 6.6, intent mismatch | Only our decoder is reported; the published gate committed 0 of 300 "other trial" streams (Tab. S19). | Add the published-gate count with a pointer to Table S19. |
| 12 | m | Table 3 caption | "counts if fewer than 30 commits", but counts are shown for every B2T row. | "wrong/commits in brackets; count only when fewer than 30 commits". |
| 13 | m | Figure S5 caption | "plug-in gate" reads as the published gate, but the entry is our decoder's full-fit plug-in layer (tau_s 4.5551, threshold 0.5 = Table S5 "ours"). | "plug-in layer, our decoder". |
| 14 | m | S10 (population risk); Tab. S19 text | "The pool-including-calibration design that draft v3 reported": internal draft numbers do not belong in a submitted manuscript. | "an earlier version of this analysis". Tab. S19 keeps the tag names, which are public. |
| 15 | m | References | Wolpaw 2002: no issue, no DOI. Card et al. data and Zariffa data: DOI not printed (`@misc` + `unsrtnat`). Willett 2023, Cai 2024, Metzger 2022: no volume or pages. | Complete the entries (verified values in Section 5). |
| 16 | c | Ref. Damri and Laufer-Goldshtein | The ICLR virtual poster page says "... via Conformal Risk Control"; the OpenReview / proceedings title is "... via Risk Control" (the title we use). | No change; the proceedings title is the citable one. |
| 17 | m | Title page | JNE asks for keywords; there are none. | Add a keywords line after the abstract. |
| 18 | c | `main.tex`, `supplement.tex`, `build.sh` comments | Stale comments ("Draft v4", "Sections S1-S24"). | Update comments (no change to the PDF). |
| 19 | c | Build log | hyperref "Invalid page number (0)" warnings (from the external-document labels). | Information only; harmless. |
| 20 | c | `refs.bib` | 13 uncited entries. | No change (not printed). |
| 21 | c | Language | Prose is clear academic English; sentences are short. Two long sentences in Sec. 6.3 and Sec. 6.6 are dense but correct. The abstract is 249 words (JNE: structured abstract, within its limit). | Shortened as part of issues 1 and 10. |

### Issues that need new analysis (not fixable in a writing pass)

These are known from earlier rounds. I agree with the authors' current handling (stated as limitations).

| # | Issue | Why open |
|---|---|---|
| A1 | Confirmatory test of the frozen configuration | Needs new data (a second participant or new sessions). |
| A2 | Per-session risk control | Per-day LTT needs >= 45 calibration items per day; the data cannot supply it. |
| A3 | Decoder-grid re-tune inside the random re-splits (round-4 St-M6) | Optional CPU re-run; listed as exception (2) in S19. |
| A4 | Wild-cluster / BCa intervals for the headline paired differences | Optional; day sign tests are the current check. |
| A5 | Conformal selection (FDR control) as a comparator | Named as future work in the Discussion. |
| A6 | Frame temperature raises per-frame ECE | Explained only as a difference of criteria. |

## 7. Check of the round-4 response

I skimmed `papers/paper1/round-4-response.md` after the review above. The claimed fixes are present in v4: time-ordered test (Tab. 1, Fig. 2a, Tab. S7); "random re-splits" naming; scope of the guarantee (Sec. 4.2, Tab. S8, S21); guarded frozen configuration and both tags (Sec. 7, Tab. S19); joint LTT (Sec. 4.3, Alg. S1, Tab. 4); two-decoder agreement gate and bonus sensitivity (Sec. 4.1, Tab. S11); abstract with registration number; main text 7,795 words (6,545 text + 1,250 floats); 0.0037 bound; MEG CIs [3.01, 3.44] / [3.02, 3.31]; the three new references. Gaps:

- The response (Ed-M6) says that the guard is presented "as an input-validity check that real data do not test". This is present, but the sentences in Sec. 6.6 / Discussion that the guard "raised wrong commits on real data" and that other tests "show the same direction" go beyond the R4 numbers (issue 1).
- The response (Ed-m19) leaves the IOP template switch to submission; still open (author decision).
- The Damri title was "declined (checked)"; the virtual poster page uses another title (issue 16, no change).

## 8. Author decisions before submission (not reviewer items)

Authors and affiliations; funding statement; final AI-assistance wording; final ethics wording (confirm with the JNE office); Zenodo archive DOI for the paper commit and per-split item tables; switch to the IOP JNE template; arXiv first or JNE directly (arXiv endorsement may be needed); cover letter and suggested reviewers.

## 9. Round-5 status (after the fix pass, draft v5)

Draft v5: `papers/paper1/draft-v5.pdf` (22 pages) and `draft-v5-supplement.pdf` (17 pages). Both builds are clean: 0 undefined references or citations, 0 multiply defined labels, 0 overfull boxes (v4: 15 in the supplement). No scientific result changed. All author TODO markers are kept. Word count (`wordcount.py`): abstract 250; main text 6,632 + 1,254 in floats = 7,886.

| # | Status | What changed (v5) |
|---|---|---|
| 1 | fixed | Sec. 6.6: "the guard did not lower wrong commits"; full-fit rise kept with its CI and sign test; guard-off rates lower on the published gate in 6 of 7 comparisons, mixed on our decoder (lower 2, similar 2, higher 3; split A 0.040 vs 0.025). Discussion and Limitation 3: "did not lower wrong commits on real data (raised them with the full-fit pipeline)". |
| 2 | fixed | Abstract: the gate is named in Approach ("our decoder, and the published sentence gated by agreement with it"); always commit "61% and 19%"; commit and EAC numbers attached to the re-splits; "On our decoder, a plain threshold committed 198 of 300". 250 words. |
| 3 | fixed | Sec. 7: "on the commit that added draft v4 of this manuscript; later versions changed only the text". Tags unchanged. |
| 4 | fixed | "Algorithm S1 in the supplement". |
| 5 | fixed | Supplement TOC number box widened (etoolbox patch of `\l@section`). |
| 6 | fixed | S6 grid sets can break across lines. |
| 7 | fixed | Sec. 5.1 and Table 5: speed measured; 4.5 s "close to the measured 4.7 s". |
| 8 | fixed | Sec. 4: "fitted values: Table S5; policy grid: Section S6". |
| 9 | fixed | Supplement: "Tables 1-5". |
| 10 | fixed | Sec. 6.6: full-fit layer and sEMG counts separated. |
| 11 | fixed | Sec. 6.6: "The published gate committed none of these 300 streams (Table S19)." |
| 12 | fixed | Table 3 caption. |
| 13 | fixed | Figure S5 caption: "full-fit plug-in layer, our decoder". |
| 14 | fixed | S10: "an earlier version of this analysis". |
| 15 | fixed | `refs.bib`: Wolpaw 113(6) + DOI; Willett 2023 620(7976):1031-1036; Cai 2024 15:9449; Metzger 2022 13:6510; Dryad and Borealis DOIs printed. Verification comments added. |
| 16 | no change | Proceedings title kept (checked). |
| 17 | fixed | Keywords line after the abstract (7 keywords). |
| 18 | fixed | Comments in `main.tex`, `supplement.tex`, `build.sh`. |
| 19 | open (cosmetic) | hyperref "Invalid page number (0)" warnings remain (39 in `main.log`); no effect on the PDF. |
| 20 | no change | Uncited `refs.bib` entries are not printed. |
| 21 | fixed | Covered by 1, 2 and 10. |
| A1-A6 | open | Need new data or new analysis (Section 6); stated as limitations or future work. |

Counts: 21 issues found (3 M, 13 m, 5 c). Fixed 18; no change needed 2 (16, 20); open 1 (19, cosmetic). In addition, 6 known items (A1-A6) stay open because they need new data or new analysis.
