# Paper 1: arXiv submission sheet

Use this sheet to fill the arXiv form. Copy each value exactly.

## Files in this folder

| File | What it is |
|---|---|
| `arxiv-source.zip` | **Upload this file.** LaTeX source of the combined document (main text + supplement), with `main.bbl`. |
| `fidetype-paper1-arxiv.pdf` | Local build of the zip. arXiv must show the same document (37 pages). |
| `fidetype-paper1.pdf` | Main paper only (22 pages). For journals and for sharing. |
| `fidetype-paper1-supplement.pdf` | Supplement only (17 pages). For journals and for sharing. |
| `arxiv/` | The unzipped source. `make-arxiv.sh` writes it and the zip. |
| `make-arxiv.sh` | Rebuilds the package and checks it: `bash papers/paper1/final/make-arxiv.sh` |

The zip was unzipped into an empty folder and built again without the `.bib` file (as arXiv does). Result: 0 undefined references or citations, 0 multiply defined labels, 0 overfull lines, no `??` in the text.

pdfLaTeX check (2026-11-12): the zip was also built from scratch with **pdflatex** (portable TinyTeX, TeX Live 2026; three passes, no BibTeX, reads `main.bbl`), which is what arXiv runs. Result: 37 pages, 0 undefined references or citations, 0 duplicate anchors, 0 overfull lines, no `??`. The text equals the Tectonic build except for ligatures and hyphenation. `main.tex` starts with `\pdfoutput=1` (arXiv recommends it). `fidetype-paper1-arxiv.pdf` is this pdflatex build.

## Form values

**Title** (one line, no line break):

```
When should a neural text-entry decoder commit? Risk-controlled commits from a stream-level trust layer
```

**Authors:**

```
Zibo Zhang
```

Affiliation (if the form asks): `Independent researcher`. Do not give an e-mail address in the paper. arXiv uses your account e-mail only for contact; it does not print it.

**Abstract** (plain text, no LaTeX; 1,650 characters, limit 1,920):

```
Objective. Neural text-entry decoders often end in a language model that writes fluent sentences from weak neural evidence. We ask when such a system should send (commit) a sentence without confirmation, and whether wrong commits can be bounded. Approach. A trust layer reads the decoder's per-frame output stream, calibrates its confidence, and commits, offers alternatives or abstains. A Learn-then-Test threshold, never below a speed-tuned threshold, bounds the wrong-commit rate with high probability. The rule was chosen after the random re-splits below; all inference is exploratory. We test it offline on one intracortical speech participant (Brain-to-Text '25, 14 days; our decoder, and the published sentence gated by agreement with it), calibrating before testing in time. Forearm sEMG and MEG typing serve as format and safety checks. Main results. Always committing sent wrong text for 61% and 19% of sentences. Calibrated on earlier days, the rule's pooled wrong-commit rate was 1.0-2.7% (target 5%); no day was significantly above 5%. Over 50 random re-splits, 8% (95% CI 2-19%) and 2% (0.1-11%) exceeded 5%; the rule committed 15% and 39% of sentences, and 21% and 8% of commits were wrong. The bound covers the mix of days: one day ran at 10%. On our decoder, a plain threshold committed 198 of 300 no-information streams; with an evidence guard, none. Significance. A stream-level commit rule kept wrong commits rare across days for one participant. It needs an input-validity check and per-session calibration, and commits few sentences with current decoders. Clinical trial registration: BrainGate2, ClinicalTrials.gov NCT00912041.
```

**Comments:**

```
37 pages (main text, references and Appendix A: 23 pages; supplementary material: 14 pages), 9 figures. Code: https://github.com/zhangzibo/fidetype (tag paper1-v4-frozen-config)
```

**Primary category:** `cs.HC` (Human-Computer Interaction).

**Cross-lists:** `q-bio.NC`, `stat.ML`, `eess.SP`.

- Alternative primary: `q-bio.NC` (Neurons and Cognition), if you want neuroscience readers first. Then cross-list `cs.HC`, `stat.ML`, `eess.SP`.
- A first submission to a category can need an endorsement. If arXiv asks for one, the submission waits. This is outside our control.

**Licence:** `Creative Commons Attribution 4.0 International (CC BY 4.0)`. The paper text already says CC BY 4.0 (Ethics, data and code availability).

**Optional fields:**

- MSC class: `62G15; 92C55` (tolerance and confidence regions; biomedical signal processing). You can leave it empty.
- ACM class: `H.5.2; I.2.7` (user interfaces; natural language processing). You can leave it empty.
- Journal reference, DOI: leave empty.
- Report number: leave empty.

## Upload steps

1. Log in at https://arxiv.org and click **Start New Submission**.
2. Accept the terms. Select the licence **CC BY 4.0**. Select the primary category **cs.HC**.
3. On **Add Files**, upload `papers/paper1/final/arxiv-source.zip`. Do not unpack it. arXiv unpacks it.
4. Check the file list. It must show `main.tex`, `main.bbl` and the folders `sections/`, `generated/`, `figures/`. Do not delete `main.bbl`: arXiv does not run BibTeX for you.
5. Click **Process**. arXiv compiles with pdfLaTeX. Wait for "Your files were processed successfully".
6. Click **View** on the arXiv-built PDF. Compare it with `fidetype-paper1-arxiv.pdf`:
   - 37 pages;
   - author "Zibo Zhang", "Independent researcher", no e-mail;
   - no `??` in the text and no red text;
   - the reference list is complete (it ends on page 22 or 23);
   - "Supplementary material" starts on page 24, with Sections S1-S22.
7. On **Metadata**, paste the title, authors, abstract and comments from this sheet. Add the cross-lists.
8. On **Preview**, check everything again. Click **Submit**.
9. arXiv announces new papers on the next working day (cut-off 14:00 US Eastern time). You get an e-mail with the arXiv identifier.

## If arXiv fails to compile

- Open the arXiv log. Look for the first `! ` line.
- A missing package is unlikely: all packages are in TeX Live (geometry, lmodern, microtype, tikz, algorithmicx, natbib, hyperref, cleveref, adjustbox, enumitem, subcaption).
- If arXiv reports a missing figure, check that `figures/` is in the upload.
- Rebuild the package with `bash papers/paper1/final/make-arxiv.sh` and upload it again.

## After the arXiv announcement

- Put the arXiv identifier in `README.md` of the paper and in `HANDOFF.md`.
- For a journal, use `fidetype-paper1.pdf` and `fidetype-paper1-supplement.pdf` (separate files, cross-references by xr-hyper).
