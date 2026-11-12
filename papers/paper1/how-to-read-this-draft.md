# How to read this draft (Paper 1, draft v0)

This guide is for you, the author. It explains what each part of a science paper does, what reviewers check, where the open items (TODOs) are, and what you must decide. The draft itself is [`draft-v0.pdf`](draft-v0.pdf) (23 pages). The paper is in normal academic English. This guide is in simple English.

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
