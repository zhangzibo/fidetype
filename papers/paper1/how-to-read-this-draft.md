# How to read this draft (Paper 1, draft v3)

This guide is for you, the author. The current draft is [`draft-v3.pdf`](draft-v3.pdf) (37 pages: main text 1-17 with the ethics statement, references 17-25, appendices A-Q 26-37). The earlier drafts ([v0](draft-v0.pdf), [v1](draft-v1.pdf), [v2](draft-v2.pdf)) stay for comparison. The paper is in normal academic English. This guide is in simple English. Sections 1-7 below were written for v1; section and figure numbers there refer to v1.

## What changed in v3 (review round 3)

Two reviewers read v2 ([editor](reviews/round-3-editor.md), [statistics](reviews/round-3-stats.md)). Both said "major revision". The point-by-point answer is [round-3-response.md](round-3-response.md). The new numbers are in the [R3 analyses SUMMARY](../../experiments/2026-11-12-paper1-r3-analyses/SUMMARY.md).

- **New title:** "When should a neural text-entry decoder commit? Risk-controlled commits from a decoder-agnostic trust layer" (15 words).
- **The guaranteed rule leads.** The primary row is now LTT with the max rule on clean calibration data. Over 50 repeated deployments it gave a mean wrong-commit rate of 3.0 % (our decoder) and 3.1 % (published), above 5 % in only 8 % and 2 % of deployments. The plug-in row (5.9 %) is labelled "no guarantee".
- **CRC holds only on average.** Its mean is <= 5 %, but 34-42 % of single deployments exceed 5 %. This is what CRC promises; LTT is the per-deployment guarantee.
- **The old 0.059 -> 0.0245 story was wrong.** The change came from the policy grid fitted on fit-A, not from CRC.
- **Error among commits.** A guaranteed "at most 1 wrong in 10 committed sentences" is possible only for the published decoder (Table 3). Our decoder, sEMG and MEG then commit nothing.
- **Data reuse:** real but small, and only on our decoder (+0.9 percentage points). We no longer say that reuse caused the old drift result. No Holm-corrected test is significant.
- **sEMG near-variant exclusion** is now reported: speeds drop (8.02 -> 6.97 eWPM), and gaze typing beats the layer on the cross-subject decoder.
- **MEG:** no guarantee for new sentences is possible (needs >= 19 calibration sentences). Three seeds: CER 0.533 +/- 0.051; the layer commits nothing on every seed.
- **New in the paper:** Algorithms 1-2 (App. B); repeated-deployment table (Table 2); selective-risk table (Table 3); AAC / BCI user-priority references (all checked on the web); one bootstrap for all CIs; day sign tests; exact zero-event bounds; run time (0.18-0.30 ms per decision).
- **Moved to the appendix:** devices table, architecture figure, controls figure, clean-vs-reused table, online results.
- **Figure 1** has a square-root y-axis, so the region near 5 % is readable, and green diamonds for the guaranteed rule.

**Still open (red `[TODO]` in the PDF):** your author items (authors, ethics wording, funding, AI statement) and the archive DOI. **Next step:** round-4 fresh reviews. **Big open experiment:** a second intracortical participant for a confirmatory test of the frozen configuration (git tag `paper1-v3-frozen-config`).

## What changed in v2 (review round 2)

The new analyses ([SUMMARY](../../experiments/2026-11-12-paper1-r1-analyses/SUMMARY.md)) changed the story. Full list: [reviews/round-2-changes.md](reviews/round-2-changes.md).

- **No more drift claim.** With clean calibration data (not used to fit anything else), offline CRC met its target up to noise (B2T 0.025 / 0.060, sEMG 0.040 / 0.056). The old 0.0625 came from reusing fit data. The paper now reports this as a lesson. Online re-calibration is a *safeguard*, not a fix.
- **Safety, not speed, is the main claim.** The layer cuts wrong commits (61% → 5.9%, 19% → 4.4%). It is only 1.6% / 3.6% faster than always offering. Always committing is often as fast or faster under other user models, and gaze typing with word completion beats it on MEG and weak sEMG. New title subtitle: "Risk-controlled commit decisions from a decoder-agnostic trust layer".
- **Guard.** It raised wrong commits on B2T. We keep it in the reported configuration (it was fixed before the tests; the version without it was never run on the control streams) and show the plain threshold next to it. We recommend the plain threshold for the future.
- **New:** main table with all baselines at the right CI unit; user-model sensitivity figure (Fig. 3); clean-calibration table (Table 3); ablation table, leakage check and small-n CRC table in the appendix.
- **Length:** main text 20 → 15 pages; 5 main figures, 3 main tables.

**Still open:** MEG seeds 1–2 (GPU job, one red `\todo{seeds}`); Card et al. supplement check; your author items (authors, funding, AI statement, ethics wording); tag + DOI; run time per decision.

## 0. What changed in v1 (review round 1)

Two reviewers read v0 ([domain](reviews/round-1-domain.md), [methods](reviews/round-1-methods.md)). Both said "major revision". The point-by-point answer is [reviews/round-1-response.md](reviews/round-1-response.md).

- **New title.** "When should a neural text-entry decoder commit? A decoder-agnostic, risk-controlled trust layer evaluated on intracortical, EMG and MEG data". "Fidetype" is no longer in the title.
- **Honest scope.** The commit decision is tested on one implant participant. The EMG sentences are composed. MEG is a *negative control*: the layer correctly never commits. "Unchanged" is now "the same code, re-fitted per device" (new Table 9).
- **New baseline: always offer.** On B2T '25 the trust layer is only 1.6% faster than always offering (published gate: 3.6%), for 59 (44) wrong commits per 1,000 sentences.
- **New metric: error among commits.** One committed sentence in four is wrong on our B2T decoder; under CRC on MEG, 92% of the few commits are wrong. The paper now says the guarantee bounds wrong commits per attempt, not per commit.
- **Guarantees stated with their assumptions.** Random-split CRC is an implementation check. LTT is checked with its real target (calibration-conditional risk). ACI certificates and a-priori bounds are printed.
- **Controls in two classes.** Signal-destroying streams: never committed. Real stream of another sentence: cannot be detected.
- **Problem setting section** with clean notation; structured abstract; 33 new verified references; the related work now covers BCI spellers, ErrPs, adaptive decoders, dialogue systems.
- **Figures.** Removed: MEG CER bars, eWPM bars, online loop. New: selective-risk panel (Fig. 4c), MEG guard AUROC (Fig. 5c), always-offer points in Fig. 1. Ledger, conformance and the CRC-split figure moved to the appendix.
- **New script** `analysis_r1.py` re-draws the committed CRC splits and computes the new derived numbers into `data/r1-derived.json`.

**Still open from the reviews (red `[TODO: R1: ...]` in the PDF):** the parallel analysis run (clean drift baseline, always-offer rows for sEMG, selective-risk controller, unified ablation, user-model sensitivity on all devices, LM-assisted gaze baseline, LM leakage rebuilds, small-n CRC, seeds and repeated splits, reliability diagrams, one-word tolerance). These come in round 2.

**Your decisions now:** (1) keep or drop "Fidetype" in the title; (2) length: the main text is about 20 pages in this class; choose what moves to the appendix if the venue needs ~14 (candidates in the response, §H); (3) authors and affiliations; (4) ethics wording (now names the BrainGate2 trial); (5) AI-assistance statement.

## 1. Read in this order

1. **Figure 1** (page 3) and the **abstract** (page 1). Together they tell the whole story.
2. **Section 1, Introduction.** The problem, the three gaps, and the six contributions.
3. **Section 6, Results.** The numbers. Look at Table 4 and Figures 6–10.
4. **Section 8, Limitations.** What we do not claim.
5. The rest: format (3), trust layer (4), protocol (5), discussion (7), ethics (9), availability (10), appendix.

Red text in brackets, `[TODO: ...]`, marks an open item. Section 4 of this guide lists them all.

## 2. What each section is for

| Section | Its job | What a reviewer checks |
|---|---|---|
| Title | Say what the paper is about, in one line | Is it specific? Does it promise more than the results show? |
| Abstract | Context → gap → what we did → 2–3 key numbers → what it means | Are the numbers the same as in the results? Is the scope honest? |
| 1 Introduction | Why the problem matters; what is missing; our contributions | Is the gap real? Is the closest prior work named? |
| 2 Related work | Place our work among other work; say how we differ | Are important papers missing? Is the difference stated fairly? |
| 3 Format (NTS) | Describe the stream format so another lab can use it | Is it complete and clear? Is it really vendor-neutral? |
| 4 Trust layer | Describe the method well enough to reproduce it | Are all choices stated? Are the guarantees stated with their assumptions? |
| 5 Evaluation protocol | Say how we measure: metrics, user model, data splits, controls, statistics | Is there leakage? Is the baseline fair? Is the CI unit correct? |
| 6 Results | Report what we found, with CIs and controls | Do the numbers support each claim? Are negative results shown? |
| 7 Discussion | Say what the results mean, and what they do not mean | Does it over-claim? |
| 8 Limitations | List every important weakness, honestly | Are the weak points named before the reviewer finds them? |
| 9 Ethics and licences | Data use is legal and ethical | Licences, consent, re-identification, redistribution |
| 10 Code and data availability | Others can repeat the work | Is the code public? Is the exact version tagged? |
| 11 Conclusion | Short summary and next steps | Same claims as the abstract, no new ones |
| References | Every source we use | Real, correct, complete |
| Appendix | Details that do not fit in the main text | User-model values, decoder details, extra tables |

## 3. What reviewers will look at first in this paper

- **Do the decoders really use the brain signal?** Yes: the shuffled and zero-input controls (Table 3, Figure 5).
- **Is the MEG result useful or only safe?** Only safe. The draft says this in the abstract, the results, the discussion and the limitations. The MEG trust layer commits nothing, also on real input. So the MEG null-input test shows a closed gate, not null detection. Keep this honesty.
- **Is the comparison with Brain2Qwerty v2 fair?** It is not head-to-head (other test split; we use key times as training labels). The draft says so every time.
- **Are the CIs over the right unit?** MEG trust CIs are now over the 17 unique sentences (cluster bootstrap). The MEG CER CIs are still over instances (TODO G3).
- **eWPM depends on a simulated user.** Only two of its values are measured (Cai et al. 2024). The others are assumptions (Appendix A). Reviewers will ask for a sensitivity analysis (TODO G6) and for a user study (G14).
- **One implant participant, one seed, one split.** Named in the limitations. Seeds and repeated splits are TODO G2 / G7.

## 4. The open items (TODOs) and why they are open

| TODO | Where | Why it is open | Who |
|---|---|---|---|
| Authors, affiliations, e-mail | title | Your decision | you |
| Funding; AI-assistance statement wording | acknowledgements | Depends on you and on the venue policy | you |
| Ethics statement wording | Section 9 | You sign it; venue rules differ for secondary use of public data | you |
| OpenTelemetry analogy: keep or drop | Section 7 | Fits a standards audience; may look off-topic in a neuro journal | you |
| Tag `paper1-v1` and archive (Zenodo DOI) | Section 10 | Do it just before submission | Claude, after your go |
| G2 / G7 seeds and repeated splits | Sections 5, 6, 8 | Every run has one seed | Claude (compute) |
| G3 sentence-level CIs for MEG CER; day CIs for drift | Sections 5, 6 | Partly done (trust rows done in G1) | Claude |
| G4 natural-typing sEMG (KT-sEMG) | Section 8 | Our sEMG sentences are composed from single key presses | Claude, or keep as limitation |
| G5 unified ablation table | Section 6.8 | Reviewers ask which module matters | Claude |
| G6 eWPM sensitivity to the user model | Sections 5, A | eWPM depends on assumed time costs | Claude |
| G8 more MEG test sentences (k-fold) | Appendix B | Only 17 unique test sentences | Claude (GPU) |
| G9 remove 64 Tatoeba-overlap sentences from the LM | Section 8 | Possible small leak on B2T '25 | Claude |
| G10 closest related work (Huang 2025, Damri 2026) | Sections 1, 2 | No wiki source page yet; we cite only what we have read | Claude (ingest) |
| BIDS citation | Section 2 | Not yet read | Claude (ingest) |
| G12 run time per decision | Section 10 | Only the ledger cost is measured | Claude |
| G14 user study | Section 8 | Needs ethics approval and volunteers | externally blocked |
| F5 reliability diagrams | Section 6.3 | The committed JSON has no per-bin data | Claude (harness change) |
| Appendix D–F | Appendix C | Extra tables; fill before submission | Claude |

**References.** 18 entries in `latex/refs.bib` carry `% TODO-verify`. Most are venue names that we know but did not see in our local copy (for example "NeurIPS 2019"). Check each one on the publisher page before submission. No reference was invented.

## 5. What you must decide

1. **Venue.** The outline recommends: arXiv first, then *Journal of Neural Engineering* (or IEEE TNSRE), with a workshop version in parallel. The LaTeX is a plain article class; switching to the IOP template is a small change (see `README.md`).
2. **Author list and affiliation.** Who is an author, in which order, and which affiliation (independent researcher is allowed). Name a corresponding author and e-mail.
3. **arXiv endorsement.** A first-time submitter in cs or q-bio may need an endorsement from an existing arXiv author. This is an outside dependency (tracker: externally blocked).
4. **Ethics statement wording.** The draft says: public, de-identified data; no new data; no new approval needed. Check that this is true for your situation and acceptable to the venue.
5. **AI-assistance statement.** Most venues now ask for one. The draft has a first version in the acknowledgements.
6. **Title.** The draft uses option 1 of the outline (descriptive). Options 2–4 are in `outline.md`, section 2.

## 6. How to give feedback

- Write comments in the PDF, or list them by section and line in a message.
- Say which claims feel too strong or too weak.
- Mark any sentence you do not understand. If you do not understand it, a reviewer may not either.

## 7. How the draft was made

- Every number comes from a committed result file or wiki result page. `make_figures.py` makes the data figures from committed JSON only; the drift trace is recomputed and checked against the committed values.
- `style-notes.md` lists what we learned from published papers (structure, number reporting, captions, limitations).
- Build steps and the toolchain are in `README.md`.
