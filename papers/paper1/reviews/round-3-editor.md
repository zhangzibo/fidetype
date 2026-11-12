# Paper 1, review round 3: handling editor (Journal of Neural Engineering)

- **Manuscript:** "When should a neural text-entry decoder commit? Risk-controlled commit decisions from a decoder-agnostic trust layer, evaluated on intracortical, EMG and MEG data" (draft v2, 11 Nov 2026, `papers/paper1/draft-v2.pdf`, 29 pages: 15 main text + references + appendices A–M).
- **Reviewer role:** handling editor with a clinical BCI / assistive-technology (AAC) background.
- **Date:** 2026-11-12.
- **Method:** I read the LaTeX source (`latex/main.tex`, `latex/sections/*.tex`, `latex/refs.bib`), rendered all 29 pages and every data figure to PNG (PyMuPDF), and checked numbers against the committed result files in `experiments/2026-11-12-paper1-r1-analyses/*/results/`, `experiments/2026-11-10-b2t25-trust/`, `experiments/2026-11-11-m1-09-async-full/` and `papers/paper1/data/r1-derived.json`. I wrote Sections 1–8 before I opened the earlier reviews. Section 9 (resolved vs still open) was written last, after I read `reviews/round-1-*.md` and `reviews/round-2-changes.md`.

---

## 1. Summary of the submission

The authors ask when a sentence-level neural text-entry system should **commit** a decoded sentence (send it without confirmation) instead of **offering** alternatives or **abstaining**. They define a per-frame output format (NeuralTextStream, NTS) and a "trust layer" that reads only this stream. The layer calibrates the stream (frame and sentence temperatures), builds a K-best list with a character LM, applies an optional "neural-evidence guard", and chooses an action. A commit threshold is set by a plug-in grid search, by conformal risk control (CRC), by Learn-then-Test (LTT) or by online ACI-type updates. The controlled quantity is the **marginal** wrong-commit rate P(commit and wrong). Speed is measured by a simulated gaze-typing user (eWPM).

The evaluation is offline, on public data:

- **Intracortical speech (Brain-to-Text '25, participant T15, 816 test trials over 14 days):** the only non-trivial test. The layer reduced wrong commits from 0.610 to 0.059 (own decoder) and from 0.194 to 0.044 (gated published sentence). One committed sentence in four (own decoder) or eleven (published) was still wrong. Speed gain over "always offer" was 1.6 % and 3.6 %.
- **Forearm sEMG (19 typists, sentences composed from isolated key presses):** the layer committed 0–4 % of sentences, i.e. it was almost "always offer".
- **MEG typing (19 typists, 17 unique test sentences):** the decoder is too weak (2/637 top-1 correct); the layer never committed. This is used as a negative control.

Secondary findings: the guard did not help on real data (it raised wrong commits); an apparent within-day drift in the authors' earlier analysis was an artefact of calibrating on data that had also fitted the pipeline; CRC controls the mean but not single sessions; signal-destroying control streams are never committed, while a real stream of a different intended sentence cannot be detected.

The paper is honest, careful, and much more self-critical than most submissions. The question is real and relevant for JNE readers. But in its current form the central claim ("risk-controlled commit decisions") is only partly supported by the configuration the paper headlines, the evidence base is effectively one participant, and the clinical motivation and user model need more work before a clinical/AAC reader would accept the framing.

---

## 2. Decision

**Major revision.**

Reasons:

1. **The headline number does not come from a risk-controlled rule.** The abstract and Fig. 1 report the plug-in "trust" configuration (wrong-commit 0.059 [0.045, 0.071]). This configuration has no finite-sample guarantee, and its point estimate is above the stated target α = 0.05 (in `r1-derived.json` its pool risk is above α in 100 % of splits). The configuration that is actually risk-controlled (fit-A pipeline + clean CRC) gives 0.0245 at a 10 % commit rate, and it is the row a reader should see first. The title promises "risk-controlled commit decisions"; the abstract must deliver that number first.
2. **The non-trivial evidence is one implant participant in a copy task**, with one fit/test split in file order. Halving the fit data (fit-A) changed the plug-in operating point from 0.059 / 23 % commits to 0.0245 / 10 % commits, so the split-to-split and fit-to-fit variance of the headline operating point is large and unquantified.
3. **The clinical premise and the user model are under-motivated.** The harm "wrong text sent without confirmation" is argued from ASR hallucinations, not from BCI/AAC evidence, and the open TODO on whether T15 confirmed sentences before text-to-speech is exactly the fact the premise depends on. The marginal-risk target lets one committed sentence in four be wrong; an AAC specialist will see this as unacceptable for unconfirmed output, and the paper does not show what α or what selective-risk level users would accept.
4. **Unresolved TODOs** (seeds, ethics wording, archive DOI, Card et al. supplement, run time) make the manuscript not yet reviewable as a final version.

None of these needs new data collection with humans. Most are re-analysis of committed item files plus writing. One request (a second intracortical participant from public data) is new computation and is the most valuable single addition.

---

## 3. Assessment against the editor's questions

### 3.1 Contribution: clear, important, new?

- **Clear:** mostly. The problem statement (Section 3) and the two error quantities are very well defined. The contribution list (four items: layer, guarantees, protocol, format/release) is too broad for one JNE paper. The format and audit log (items 1 and 4) are infrastructure; the JNE-relevant claim is items 2 and 3.
- **Important:** yes. Commit-vs-confirm is a real design decision in current speech and typing neuroprostheses, and few papers report the "always offer" comparator or the error among commits.
- **New:** moderately. Risk control for selective prediction exists (Geifman & El-Yaniv 2017 already give a high-probability selective-risk bound; Bates et al. 2021 RCPS; Angelopoulos et al. CRC/LTT; Damri & Laufer-Goldshtein 2026 for generative ASR). The novelty is (a) the application to BCI text entry, (b) the stream-only setting across devices, and (c) the demonstration that data reuse can fake drift. Point (c) is a useful methods caution. The paper should say plainly that the statistical machinery is not new.
- **Is the central claim supported?** "Safety first" is supported in the weak sense that the layer reduced wrong commits relative to always committing on one participant, and reduced to always offering on weak decoders. "Risk-controlled" is supported only for the CRC rows, which the paper treats as secondary. "Decoder-agnostic, three device types" is supported for the software interface (adapters work) but not for the commit decision, which was tested non-trivially on one device and one person.

### 3.2 Clinical and user relevance

- **Simulated user:** the fallback speed (20 cpm) and the word-selection time (4.5 s) are matched to one eye-gaze user with ALS (LP1 in Cai et al. 2024). Everything else is assumed: reading time, miss probability 0.05, a rational user who picks the cheapest of pick/fix/retype after an offer with perfect error detection, no fatigue, no attention lapses, no time-of-day effects, no communication-partner effects. The sensitivity analysis is good practice, and its result (speed rankings flip) is reported honestly. But for a person with late-stage ALS, the dominant costs are fatigue, gaze calibration drift, and the cost of reading and verifying text; these are not modelled. A clinician will also note that a person with ALS who is able to type 159 characters per minute with a speech BCI is not the same person who types 20 cpm with gaze, so mixing the BCI rate and the gaze fallback rate in one user is itself an assumption.
- **Gaze baseline fairness:** "gaze typing alone" is error-free with no reading time (favours it); "gaze + word completion" uses a context-free unigram with three slots (disfavours it relative to modern AAC, which uses n-gram or LLM prediction, e.g. Cai et al. 2024 itself, SpeakFaster). On MEG and weak sEMG, even this weak completion baseline wins. A stronger, realistic AAC baseline (n-gram or LLM word prediction) would probably widen this gap. The paper should say so and should not describe the unigram baseline as "simple" without noting that clinical AAC is stronger.
- **What an AAC specialist would object to:**
  1. Error among commits of 0.25 (own decoder) and 0.95 (MEG CRC commits). A user who sees one in four "confident" sentences go out wrong will stop trusting commits and will check every one, which turns commit into offer and removes the speed gain.
  2. No treatment of **authorship and agency**: the AAC literature on LLM-assisted output (e.g. Valencia et al. CHI 2023; Kane et al. CHI 2017) shows users care about text sent "in their name" even when it is close to right. Exact-match loss treats a near-miss and a meaning-reversing error equally; a clinician cares about the second much more (e.g. "I want to stop" vs "I want to start").
  3. No discussion of **who chooses α** in practice, how it is explained to users and families, and whether it should differ by context (chatting vs medical decisions). The discussion says "the user or clinician chooses α" in one sentence.
  4. The copy-task setting removes the user's own intent and its variation. In free communication, the "truth" for calibration and online feedback is not available unless the user corrects, which the paper acknowledges for online feedback but not for the offline CRC calibration set.
- **Is the harm motivated with evidence?** Not yet. The only evidence cited is ASR hallucination harm (Koenecke et al. 2024) and a general sentence. There is relevant BCI/AAC user-priority evidence: surveys of potential BCI users with ALS rank accuracy above speed and state minimum acceptable accuracies (Huggins et al. 2011, 2015); this is exactly the evidence the "safety first" framing needs, and it would also help to justify α = 0.05.

### 3.3 Structure, readability, figures, length, abstract, title

- **Flow:** the argument is logical (problem → format → layer → protocol → results → discussion), but the main text carries too many sub-results for a first-time reader: four risk-control methods, four online methods, eight user-model variants, nine ablation variants, two deployment splits, the drift re-analysis, and the format/audit log. The key result is spread over Table 2 (24 rows), Fig. 1 and Fig. 3.
- **Sections 7.6–7.7** (CRC on random splits; clean drift) read as a correction of the authors' own earlier unpublished analysis ("In our earlier analysis..."). A JNE reader never saw that analysis. Recast this as a deliberate demonstration: "calibrating on fit data (reused) vs on held-out data (clean)", with both shown as conditions.
- **Length:** 15 pages main text plus 14 pages of references and appendices is long but acceptable for JNE. The main text could lose 2–3 pages by moving the online re-calibration details (Section 5.5, Table 3 online columns) and the format paragraph to the appendix.
- **Abstract:** accurate and number-rich, but dense (about 280 words, 20+ numbers). It leads with the plug-in configuration (see Major 1). It mixes "EMG" (abstract) and "sEMG" (body). It should state the single-participant limitation explicitly in Main results, not only as "one intracortical speech participant" in Approach.
- **Title:** too long (25 words, three lines). It claims "risk-controlled" (see Major 1) and "evaluated on intracortical, EMG and MEG data", which suggests three tests of the commit decision when there is one. Suggested: "When should a neural text-entry decoder commit? Risk-controlled commit decisions, tested on one intracortical participant with EMG and MEG controls" or shorter: "Risk-controlled commit decisions for neural text entry".
- **Figures and tables:** see Section 6. In short: Fig. 1 hides the region of interest (all trust points are squeezed into 0–0.06 on a 0–1 axis); Fig. 3 shows speed only, although its section title is about wrong-commit rates; Fig. 5 spends half its ink on bars that are 1.0 by definition. Table 2 is complete but too long for the main text.

### 3.4 Honesty and framing

- **Strengths:** the authors report the always-offer comparator, the error among commits next to every result, the guard's negative ablation, the fact that gaze + word completion beats the layer on weak decoders, the data-reuse error in their earlier analysis, and the post-hoc nature of the endpoints. This is exemplary and unusual.
- **Over-claiming:**
  - "bounds how often wrong text is sent" (abstract, significance; introduction; conclusion) is said of a configuration that has no bound and exceeds α on the test set (Major 1).
  - "decoder-agnostic ... evaluated on intracortical, EMG and MEG" (title) suggests generality that the data do not show (Major 5).
  - "With CRC on the clean calibration set (split A), the rate fell to 0.0245" (Section 7.2) attributes the fall to CRC. In the source, the fit-A plug-in policy alone gives exactly the same 0.0245 (CRC λ 0.3075 vs plug-in λ 0.30; `baselines/results/tables.md`, `clean-drift/results/tables.md`). The fall came from re-fitting the pipeline on fit-A, not from CRC.
- **Under-reported:** the sEMG leakage exclusion analysis (Limitation 2) — see Major 6 and the number check (row 21). Removing the LM's near-variant sentences *from the LM* changes trust eWPM by ≤ 0.04, but removing the 295 near-variant sentences *from the test set* drops trust eWPM from 8.02 to 6.97 (session-calibrated) and from 4.68 to 4.08 (cross-session). The text says "removing them changed trust eWPM by at most −0.04", which a reader will understand as the second analysis.
- **Post-hoc endpoints:** handled transparently (Section 6.3), but the consequences are not drawn. The configuration was changed after test-set inspection across revisions (guard kept despite being harmful; plain threshold recommended for the future; LM weight re-tuned). All B2T test data are now "seen". A reader needs one frozen, pre-specified configuration evaluated on data the authors have not yet looked at (Major 7).
- **Limitations** are proportionate and specific. The single-participant limitation should move up into the abstract and the first paragraph of the discussion.

### 3.5 Number spot-check

I checked 32 numbers (Section 7). All but a handful match the source files exactly or to rounding. The mismatches are wording/attribution problems, not data errors, with one exception of substance (leakage, row 21). Details in Section 7.

### 3.6 References

- **Missing key works:**
  - **Selective-risk control:** Geifman & El-Yaniv 2017 (already cited) contains the "selection with guaranteed risk" (SGR) algorithm, which bounds the error among accepted items with probability 1−δ. This is the selective-risk controller the discussion says was not evaluated; it should be run, or at least named. Also Bates et al. 2021, "Distribution-free, risk-controlling prediction sets" (J. ACM), the high-probability counterpart that LTT generalises.
  - **BCI/AAC user priorities:** Huggins, Wren & Gruis 2011, "What would brain-computer interface users want? Opinions and priorities of potential users with amyotrophic lateral sclerosis" (ALS); Huggins et al. 2015 (spinal cord injury users); Peters et al. 2015 or similar "BCI users speak up" work; Kübler et al. 2014 user-centred design for BCI.
  - **AAC authorship and LLM-generated text:** Valencia et al. CHI 2023 ("Less is more": LLM suggestions in AAC and user agency); Kane et al. CHI 2017 ("At times avuncular and cantankerous": AAC users and their communication partners); Kristensson et al. CHI 2020 or Vertanen & Kristensson on sentence retrieval in AAC.
  - **Word-prediction cost:** Koester & Levine 1994/1996 (the cognitive cost of scanning word-prediction lists), which bears directly on the "no glance cost" assumption.
  - **Speech neuroprostheses with explicit confirmation or unintended output:** Moses et al. 2021 (NEJM); Metzger et al. 2023 (Nature); Kunz et al. 2025 (Cell, inner speech and unintended decoding; directly relevant to "wrong text sent in their name"); Wairagkar et al. 2025 (Nature, instantaneous voice synthesis, where there is no confirmation step at all).
- **References that look wrong or weak:**
  - BibTeX key `achituve2025emg` for a paper whose first author is Eby (ref [8]) and `achituve2024data` for the dataset (ref [81], "Idan Achituve et al.") — check that the dataset's author list is correct and consistent with [8].
  - Ref [4] (Jude et al. 2026) lists "Justin J. Jude, Hadar Levi-Aharoni, et al." — give the full author list as for the other entries.
  - Refs [76] and [77] (IEEE P2731, P2794) print a stray ", ." after the URL.
  - Ref [21] (CRC, ICLR 2024) prints an arXiv DOI as the DOI; use the OpenReview/ICLR entry.
  - Ref [17] (LSL, bioRxiv 2024) has no DOI.
  - Ref [6] (Brain2Qwerty v2) is a company web PDF; if an arXiv/bioRxiv version exists, cite it.

---

## 4. MAJOR issues

**M1. The headline configuration is not the risk-controlled one, and it exceeds α.** [ANALYSIS + WRITING]
- *Where:* Abstract (Main results, Significance); Section 1 last paragraph; Fig. 1; Table 2 "trust" rows; Section 7.2; Discussion first paragraph; Conclusion.
- *Why:* The abstract reports 5.9 % (own decoder) from the plug-in policy, which Section 5.3 says "has no guarantee on new data". Its point estimate (0.0588) and most of its CI are above α = 0.05; in `r1-derived.json` (`splits_m213/b2t-ours/*/old/pool_risk_share_above_alpha = 1.0`) and Fig. 8 the "fixed gate" sits above α. At the same time the Significance says the rule "bounds how often wrong text is sent". The paper's own recommended deployable rule is max(λ_tuned, λ_CRC) (Section 5.4); on B2T ours this rule equals the clean-CRC row (λ_CRC 0.3075 > λ_plug-in 0.30), which gives 0.0245 at a 10 % commit rate. Also, Section 7.2 attributes the fall from 0.059 to 0.0245 to CRC, but the fit-A plug-in policy without CRC gives exactly 0.0245 (`baselines/results/tables.md`, row "trust, fit-A pipeline (plug-in)"); the change came from re-fitting on fewer data.
- *Fix:* (a) Make the pre-specified, risk-controlled pipeline (fit-A + clean CRC, and LTT next to it) the primary row in the abstract, Fig. 1 and Table 2; show the plug-in policy as a secondary "no guarantee" row. (b) State in Section 7.2 that on B2T the CRC threshold coincided with the fit-A plug-in threshold, so CRC certified rather than changed the operating point; and explain why the full-fit and fit-A plug-in operating points differ so much (0.059 / 23 % vs 0.0245 / 10 %). (c) Use "bounds" only for rows that carry a bound.

**M2. Table 2's "trust, CRC" rows are pure CRC, not the deployable rule; the paper does not say which rule it recommends.** [ANALYSIS + WRITING]
- *Where:* Section 5.4 (deployable rule), Table 2 (CRC rows), Table 8 last rows, Section 7.6 last sentence.
- *Why:* Section 5.4 recommends max(λ_tuned, λ_CRC). Table 2 reports pure CRC, which on sEMG raises the wrong-commit rate ten-fold (session-cal. 0.004 → 0.040; cross-session 0.004 → 0.056 with 61 % of commits wrong) and on MEG commits text that is 95 % wrong. A clinical reader of Table 2 will conclude that CRC makes the system less safe.
- *Fix:* Add one row per condition for the deployable rule (and say that on sEMG and MEG it equals the plug-in row). Move pure CRC to the appendix as a check of the guarantee, or label it "pure CRC (fills the risk budget)". State one recommended rule in the abstract and discussion.

**M3. Marginal risk alone is not a clinically acceptable target; evaluate a selective-risk controller.** [ANALYSIS]
- *Where:* Sections 3, 7.4 ("commit trade-off"), 7.6, Discussion "Marginal vs selective risk".
- *Why:* The user experiences the error among commits: 0.25 (own decoder), 0.09–0.10 (published), 0.61 (sEMG cross-session CRC), 0.93–0.95 (MEG CRC). A rule that lets one in four "committed" sentences be wrong will not be trusted by users, and an AAC specialist will not deploy it. The paper says a selective-risk controller is "a natural complement that we did not evaluate", but the SGR algorithm of Geifman & El-Yaniv (2017, already cited) or LTT on the conditional risk with a minimum number of commits can be run directly on the committed item files (`clean-drift/results/items-*.json`, `m2-13` splits).
- *Fix:* Add a selective-risk controller (target error among commits, e.g. ≤ 0.10, with δ = 0.1) and report, per condition, the commit rate it allows and its eWPM. Likely outcome: the published gate commits a substantial share, the own decoder commits little, sEMG/MEG commit nothing. This makes the safety claim much stronger and more clinically meaningful. Consider making the joint constraint (marginal ≤ α and selective ≤ β) the recommended rule.

**M4. The clinical harm and the "commit without confirmation" premise need BCI/AAC evidence.** [WRITING]
- *Where:* Section 1 first paragraph; Section 2 (TODO on Card et al.); Discussion.
- *Why:* The premise is motivated from ASR hallucination harm only. Whether the T15 system confirmed sentences before text-to-speech (open TODO in Section 2) decides whether "commit" corresponds to current clinical practice or to a hypothetical faster mode. User-priority surveys (Huggins et al. 2011, 2015) give the accuracy–speed trade-off that potential users with ALS state, which is the natural anchor for α and for the selective-risk target. The AAC literature on authorship (Valencia et al. 2023; Kane et al. 2017) shows why a wrong sentence "in their name" matters beyond eWPM.
- *Fix:* Resolve the Card et al. TODO and describe the real interaction. Add one paragraph in the introduction with BCI/AAC user evidence, and a paragraph in the discussion on who sets α, how it is explained, and whether it should depend on context. Note that exact-match loss treats harmless near-misses and meaning-changing errors the same, and name a semantic-severity loss as future work.

**M5. The evidence for the commit decision is one participant and one split; quantify the variance and add a second participant if at all possible.** [NEW-EXP + ANALYSIS]
- *Where:* Title; abstract; Sections 6.2, 7.2; Limitation 1 and 4.
- *Why:* All non-trivial commit evidence comes from T15 in a copy task, with one fit/test split in file order. The fit-A re-fit showed that the plug-in operating point moves from 23 % to 10 % commits when the fit data are halved, so the operating point is unstable. sEMG is composed from isolated presses with oracle timing; MEG is a negative control. "Evaluated on intracortical, EMG and MEG data" over-states the generality.
- *Fix:* (a) **New computation, strongly recommended:** add a second intracortical participant from public data. The Willett et al. 2023 speech dataset (T12, Brain-to-Text '24 benchmark) is public; a baseline RNN produces phoneme logits that can be mapped to NTS with the existing adapter. Even a modest decoder gives a second non-trivial test. (b) **Re-analysis:** repeat the B2T fit/test assignment (e.g. 20 random day-stratified halves, or leave-one-day-out) and report the spread of the commit rate, wrong-commit rate and error among commits for the plug-in and CRC pipelines. (c) Report per-day results (14 days) as a supplementary figure; days are the natural unit of clinical variation. (d) Retitle as suggested in Section 3.3.

**M6. sEMG leakage: the exclusion analysis is mis-described and its result is not reported.** [WRITING + ANALYSIS]
- *Where:* Limitation 2; Appendix G.
- *Why:* 295 of 551 sEMG test sentences have a near variant in the LM training text. Rebuilding the LM without them changed trust eWPM by ≤ 0.04 (reported). But excluding these 295 sentences from the test set (`leakage/results/tables.md`, "Exclusion" lines) drops trust eWPM from 8.02 to 6.97 (session-calibrated) and from 4.68 to 4.08 (cross-session), and always-commit wrong-commit rises from 0.54 to 0.66. Templated sentences are much easier; the main sEMG numbers depend on them. Limitation 2's "removing them changed trust eWPM by at most −0.04" reads as the exclusion result.
- *Fix:* Report both analyses in Appendix G with CIs, state the exclusion result in Limitation 2, and either report sEMG on the 256 non-templated sentences as a sensitivity row in Table 2 or explain why the full set is the right primary population.

**M7. Freeze one pre-specified configuration and evaluate it on untouched data.** [ANALYSIS (+ NEW-EXP if M5a is done)]
- *Where:* Section 6.3; Section 7.4 "Why the guard stays".
- *Why:* The primary endpoints were chosen after the first evaluation runs; the guard was kept although the test-set ablation showed it raises wrong commits; the authors already say a future configuration should use the plain threshold. Every revision has looked at the same B2T test half again. The honest handling is commendable, but the reader still lacks one result that was not shaped by test-set feedback.
- *Fix:* Write down (in the paper and in a dated repository tag) the final configuration (e.g. plain calibrated threshold + clean CRC, α = 0.05, plus the selective constraint from M3), and evaluate it once on data never used in development: the second participant from M5a, or if that is not possible, the 90 excluded 50-word-vocabulary trials as a small task-shift check (clearly labelled), or sEMG participants held out from all fitting. Report this as the confirmatory result; call everything else exploratory.

**M8. Remove all TODO markers and complete the reproducibility items.** [WRITING]
- *Where:* Title block (authors), Section 2 (Card et al.), Section 7.1 (MEG seeds), Section 11 (ethics wording, Zenodo DOI, run time per decision), Acknowledgements (funding, AI wording).
- *Why:* A manuscript with eight visible TODOs cannot go to external review. The ethics statement on secondary use of BrainGate2 trial data must be final; JNE requires it.
- *Fix:* Complete each item or delete the sentence. For MEG seeds: report all three seeds or state that one seed is used and remove the TODO. Give trust-layer run time per decision (it matters for real-time use).

**M9. Focus and re-structure for a first-time JNE reader.** [WRITING]
- *Where:* Contribution list; Sections 4, 5.5, 7.6, 7.7; Table 2; Discussion.
- *Why:* The paper tries to be four papers: a format specification, a risk-control method, a clinical evaluation protocol, and a self-correction of an earlier drift claim. The JNE claim is the commit decision and its evaluation protocol.
- *Fix:* (a) Reduce the contribution list to two or three items; move NTS details and the audit log to the appendix (keep one paragraph and Fig. 2). (b) Recast Section 7.7 as a deliberate "reused vs clean calibration" comparison without the history ("In our earlier analysis"). (c) Split Table 2: a main-text table with the three primary policies per condition (always commit, always offer, recommended risk-controlled rule) plus gaze baselines; move the rest to the appendix. (d) Put the single-participant caveat in the first sentence of the discussion.

---

## 5. MINOR issues

1. **Abstract:** "EMG" in the abstract and title, "sEMG" in the body; use one term. Mention that the sEMG sentences are composed from isolated presses. "under most user-model variants not faster than always committing" is true for the published gate (9/9) and for the own decoder (5/9 when the main user is counted as not significantly faster); state it per decoder.
2. **Section 7.3:** "On sEMG and MEG, the gain over always committing came from offers and disappeared with miss probability 0 or symmetric offers." Under symmetric offers with miss probability 0.2 the gain remains: MEG [+1.25, +1.83], sEMG cross-subject [+0.96, +1.70], sEMG session-cal. [+0.10, +0.45] (`user-model/results/tables.md`). Restrict the statement to the symmetric-offer variant with miss probability 0.05.
3. **Section 7.3:** "Silent errors rose under symmetric offers (0.02–0.17)" does not hold for MEG (0 in both variants) or sEMG cross-subject with miss 0.2 (0.005). Qualify.
4. **Section 7.3 / Fig. 3:** the section title says wrong-commit rates do not depend on the user model, but no figure or table shows the refitted wrong-commit rates ("unchanged in 49 of 54 pairs"). Add a column to Fig. 3 or a table in Appendix C.
5. **Section 7.4, ablation:** "without it [sentence temperature], the rate rose on 4 of 6 conditions" — give the paired CIs; for B2T ours the paired difference is [0.000, 0.036] (`ablation/results/tables.md`), i.e. borderline.
6. **Section 7.6:** mixes 500-split numbers (Table 12) and 200-split numbers (pool risk; Fig. 8); say which is which. Fig. 8's caption says "the 90th percentile matches δ = 0.1", but LTT bounds the population risk, not the test rate of a finite split; the test rate includes test-sampling noise. Rephrase.
7. **Section 7.6:** "on sEMG, 9 of 18 participants never committed" — name the condition (session-calibrated) and explain why 18, not 19, participants.
8. **Appendix J (replay):** "39 of 39 (CRC)" wrong commits imply a CRC operating point of 39/816 = 0.048, not the clean CRC (0.0245, 20 wrong). Label which CRC (reused-data, from the earlier pipeline) was replayed, or re-run the replay with the clean CRC.
9. **Table 2:** silent-error rate for B2T ours trust is 0.0025 in the source and prints as 0.002; use three significant digits or 0.003. The CI of the clean CRC row is [0.015, 0.035] in Table 2 and [0.014, 0.035] in Table 3 (two bootstrap runs of the same quantity); use one.
10. **Table 3:** "Exch. ref." uses the same bracket notation as a CI but means [5th, 95th percentile]; use a different notation, e.g. "0.018 (0.014–0.022)".
11. **Table 1:** column order (MEG, intracortical, sEMG) differs from every other table and figure (intracortical, sEMG, MEG). Use one order.
12. **Section 6.1:** the neural input rate of 159.3 cpm for the intracortical data comes from copy-task speech durations; say that free communication will be slower (planning time).
13. **Section 6.1:** "matched to one eye-gaze user with ALS" — state that LP1's speeds come from a non-BCI setting and that the variation across gaze users is large.
14. **Section 6.2 (MEG):** the trust harness keeps an insertion bonus that the authors know is wrong for calibrated streams (CER 0.522 vs 0.475). Since MEG never commits either way, simply use the validation-tuned beam and drop the explanation.
15. **Appendix I:** "A longer training schedule gave the same validation CER and is not reported." The longer run (r5) had a worse test CER (0.516 / 0.484 vs 0.506 / 0.475, paired CIs excluding 0; `experiments/2026-11-11-m1-09-async-full/results.md`). Selection by validation is fine, but say that the test CER of the alternative was worse, or omit the sentence. (Note added after reading round 1: the methods reviewer asked to report r5 only as a validation-equal alternative, not as a test comparison. The cleanest wording is the selection rule alone: "we selected the schedule by validation CER".)
16. **Section 5.2:** the guard is described in detail and then shown to be harmful. Shorten its description in the main text and move the formula to the appendix.
17. **Section 8, "Strong decoders still need a gate":** "kept 96 % of its speed" — say "96 % of the always-commit eWPM under the main simulated user".
18. **Section 8:** "adapters of 148 to 568 lines" — line counts are not a meaningful measure of adapter effort for a JNE reader; drop or move to the appendix.
19. **Notation:** "Err. | commit" and "error among commits" and "selective risk" are three names for one quantity; pick one for tables and one for prose.
20. **Ethics:** the audit-report example (Fig. 7) prints a cue sentence and trial id of T15. It is a public CC0 copy-task cue, not the participant's own words; say so in the caption (it already says "public CC0 cue sentence") and confirm that the dataset terms allow item-level quotation.
21. **Data availability:** the repository URL uses a personal account (`github.com/zhangzibo/fidetype`); JNE prefers an archived DOI (already a TODO).
22. **Figures:** use the same colour for the same condition in all figures (B2T ours is dark blue in Figs 3 and 4 but the trust layer is also blue in Figs 1 and 5).

---

## 6. Figure-by-figure comments

| Figure | Earns its place? | Comments and concrete fixes |
|---|---|---|
| **Fig. 1** (teaser: wrong commits vs eWPM, 3 panels) | Yes, but it hides the key result | The y-axis runs 0–1, so all trust points, the α line and the always-offer triangles are squeezed into the bottom 5 % of each panel; the difference between 0.059, 0.044 and 0.025 (and whether they are above α) cannot be read. Labels collide in (b) ("cross-subject" is clipped at the panel edge; the cross-session label overlaps its marker). In (c) the "commits 0%" annotation points at overlapping markers. The figure omits the risk-controlled configuration and the error among commits, both of which the paper says must always be reported. **Fix:** use a broken or log y-axis (or an inset 0–0.1 with the α line), add the CRC/deployable-rule marker, and print commit rate and error among commits next to each trust marker. |
| **Fig. 2** (architecture) | Marginal | Clear, but the audit-log box and the device list give the format more weight than the decision. Merge with Fig. 6 (decision flow) into one figure: stream → calibration → candidates → commit rule (with the risk controller) → user. |
| **Fig. 3** (user-model forest plot) | Yes | Good design. State the sign convention in the panel titles ("> 0: trust faster"). Panel (c)'s x-axis is dominated by B2T (≈ +13); use per-panel or split axes so the sEMG/MEG differences near 0 are readable. Add the refitted wrong-commit rate per variant (the section's claim). Row label "symmetric offer" should say "(miss 0.05)". |
| **Fig. 4a** (sentence ECE) | Yes | Add the published gate (ECE 0.102 → 0.058 in `b2t25-trust/results.md`). ECE without CIs or reliability diagrams is weak; add a reliability diagram for B2T ours in the appendix (the text admits it was not computed). |
| **Fig. 4b** (marginal risk vs commit rate) | Yes | The MEG dotted curve is invisible near the origin; the sEMG cross-session curve leaves the axis at about 0.3 commit rate. Mark the operating points of the plug-in and CRC rules on each curve. |
| **Fig. 4c** (selective risk vs commit rate) | Yes — this is the clinically most important panel | It is the smallest panel in the paper. Promote it (larger, main text), add a horizontal line at a selective target (e.g. 0.10), and mark where each decoder crosses it (feeds M3). The MEG curve is missing from the panel but listed in the legend of 4b. |
| **Fig. 5a, b** (controls: commit rates) | Partly | The orange "always commit" bars are 1.0 by definition and carry no information; the trust bars (22 %, 2.5 %, 0 %) are the content. Replace with a small table or a dot plot of trust commit rate per control, and show all three sEMG conditions. |
| **Fig. 5c** (MEG guard AUROC) | Partly | A different quantity (AUROC) in the same figure as commit rates is confusing; move to the appendix or to a separate small panel with its own caption. Label the dotted line ("chance 0.5"). |
| **Fig. 6** (decision flow, appendix) | Yes (appendix) | Fine; see Fig. 2 merge suggestion. |
| **Fig. 7** (audit entry, appendix) | Marginal | Useful as an illustration of provenance, but not needed for the JNE claim. Keep in the appendix. |
| **Fig. 8** (CRC/LTT over random splits, appendix) | Yes (appendix) | Good. Fix the δ sentence in the caption (Minor 6). The "fixed gate" (plug-in) above α at both n is the clearest visual evidence for M1; mention it in the text. |
| **Table 2** | Yes, but too long | 24 rows and 7 columns; split as in M9(c). Mark the recommended rule in bold. |
| **Table 3** | Yes | Good. Notation for "Exch. ref." (Minor 10). Online columns could move to the appendix. |
| **Tables 4–12** (appendix) | Yes | Table 8 is very useful; add the paired CIs it refers to in the repository, at least for the wrong-commit column. |

---

## 7. Number check (abstract, results, tables vs source files)

Paths are relative to the repo root. "✓" = matches to the printed precision.

| # | Paper location | Paper value | Source value | Source path | Result |
|---|---|---|---|---|---|
| 1 | Abstract; §7.2; Table 2 | B2T ours always commit 0.610; trust 0.059 [0.045, 0.071] | 0.6103; 0.0588 [0.0451, 0.0711] | `experiments/2026-11-12-paper1-r1-analyses/baselines/results/tables.md` | ✓ |
| 2 | §7.2 | 23 % committed, 48 of 189 wrong, error among commits 0.25 [0.19, 0.32] | commit 0.232; n_commit 189, n_wrong 48; 0.254 [0.194, 0.320] | `papers/paper1/data/r1-derived.json`; baselines tables | ✓ |
| 3 | Abstract; §7.2 | +0.18 eWPM (1.6 %) vs always offer [0.12, 0.24] | 11.55 − 11.37 = 0.18; 1.58 %; [0.12, 0.24] | baselines tables | ✓ |
| 4 | §7.2 | trust − always commit [−0.16, +0.33] | [−0.16, 0.33] | baselines tables | ✓ |
| 5 | Abstract; §7.2 | Published: 0.194 → 0.044 [0.027, 0.067], 36/386, 0.09 | 0.1936; 0.0441 [0.0266, 0.0671]; 36/386; 0.093 | baselines tables; r1-derived | ✓ |
| 6 | §7.2 | Published: −4.3 % vs always commit [−1.01, −0.67]; +0.66 eWPM (3.6 %) [0.53, 0.80] | (19.61 − 18.77)/19.61 = 4.3 %; [−1.01, −0.67]; 0.66, 3.6 %; [0.53, 0.80] | baselines tables | ✓ |
| 7 | §7.2; Table 2 | Clean CRC split A: 0.0245, commit 0.10, vs always offer [+0.07, +0.16], error among commits 0.24 | 0.0245; 0.100; [0.07, 0.16]; 0.244 | baselines tables | ✓ value — **but** the fit-A plug-in without CRC gives the identical 0.0245 (λ 0.30 vs CRC λ 0.3075); the text attributes the fall to CRC (M1) |
| 8 | §7.2; Table 2 | sEMG commits 21, 10, 0 of 551; wrong-commit 0.004, 0.004, 0 | 21, 10, 0; 0.0036, 0.0036, 0 | r1-derived (`whole_test/semg/*/c_trust`) | ✓ |
| 9 | §7.2 | sEMG session-cal. vs gaze [+2.73, +4.84]; vs gaze + completion [+0.74, +2.99] | [2.73, 4.84]; [0.74, 2.99] | baselines tables; `user-model/results/tables.md` | ✓ |
| 10 | §7.2 | sEMG CRC commit 0.24 and 0.09; cross-session 61 % of CRC commits wrong | 0.241, 0.093; 0.608 | baselines tables | ✓ |
| 11 | §7.2; Table 2 | MEG: 1.6 % in 10-best; always commit 0.997; trust − gaze [−0.11, +0.26]; sentences [−0.05, +0.15]; participants [−0.08, +0.22] | 0.016; 0.9969; [−0.11, 0.26]; [−0.05, 0.15]; [−0.08, 0.22] | Table 6 source; baselines tables | ✓ |
| 12 | §7.2 | MEG gaze + completion faster [−1.14, −0.64]; CRC committed 3.0 %, 95 % wrong | [−1.14, −0.64]; 0.030; 0.947 | user-model tables; baselines tables | ✓ |
| 13 | §7.1 | MEG CER 0.506 / 0.475; shuffled 0.760; zeros 0.925; text-only 0.688; v2 0.59 ± 0.02 | 0.506 / 0.475; 0.760; 0.925; ≈ 0.69; 0.59 ± 0.02 | `experiments/2026-11-11-m1-09-async-full/results.md` | ✓ |
| 14 | §7.1 | B2T top-1 right 39 % (ours), 81 % (published); WER 0.149 / 0.043 | 0.390; 0.806 | Table 6 / r1 analyses | ✓ |
| 15 | §7.1 | sEMG balanced accuracy 0.367, 0.240, 0.226; uniform 0.037; permuted 0.032 | 0.367, 0.240, 0.226; 1/27 = 0.037; 0.032 | `experiments/2026-11-12-paper1-r1-analyses/fixchecks/results/tables.md` | ✓ |
| 16 | §7.3 | Own decoder: always commit at least as fast in 5 of 8 variants (list given) | fallback 40, selection ×2, p_miss 0, symmetric, symmetric 0.2 (equal 10.77) | user-model tables | ✓ |
| 17 | §7.3 | Published: always commit fastest in all 9, by 0.46–1.47 eWPM | differences 0.46 (sel ×0.5) to 1.47 (sel ×2) | user-model tables | ✓ |
| 18 | §7.3 | Glance cost: gaze + completion 3.16 (MEG), 4.84 (sEMG); MEG misspecified 1.18 vs 2.75; MEG flips [−1.36, −0.89] / [+0.21, +0.45] | 3.16; 4.84; 1.18 vs 2.75; [−1.36, −0.89]; [0.21, 0.45] | user-model tables; `user-model/results.md` | ✓ |
| 19 | §7.3 | "gain over always committing ... disappeared with miss probability 0 or symmetric offers" (sEMG, MEG) | symmetric, miss 0.2: MEG [+1.25, +1.83], sEMG x-subject [+0.96, +1.70], sEMG session-cal. [+0.10, +0.45] | user-model tables | **Mismatch (wording)** — true only for the symmetric variant with miss 0.05 (Minor 2) |
| 20 | §7.3 | Silent errors under symmetric offers 0.02–0.17 | MEG 0 / 0; sEMG x-subject (miss 0.2) 0.0054 | user-model tables | **Mismatch (range)** — not true for all conditions (Minor 3) |
| 21 | Limitation 2; App. G | 295 of 551 near variants; "removing them changed trust eWPM by at most −0.04" | LM rebuild: 8.02 → 7.98, 4.68 → 4.65, 4.08 → 4.09 ✓. **Test-set exclusion** (256 kept): trust 8.02 → 6.97 (session-cal.), 4.68 → 4.08 (cross-session); always-commit wrong-commit 0.54 → 0.66 | `experiments/2026-11-12-paper1-r1-analyses/leakage/results/tables.md` (lines "Exclusion (original LM, 256 kept / 295 removed test items)") | **Substantive omission / ambiguous wording** (M6) |
| 22 | §7.4 | Sentence ECE 0.448 → 0.067; frame T 3.78; peak ECE 0.090 → 0.130; AUROC 0.797; guard AUROC 0.702 | 0.448 → 0.067; 3.781; 0.090 → 0.130; 0.797; 0.702 | `experiments/2026-11-10-b2t25-trust/results/tables.md` | ✓ |
| 23 | §7.4 | No guard: 0.059 → 0.036 [−0.036, −0.011], eWPM [−0.10, +0.04]; published 0.044 → 0.025 [−0.034, −0.006], eWPM [−0.20, −0.10] | [−0.0360, −0.0108]; [−0.10, 0.04]; [−0.0337, −0.0055]; [−0.20, −0.10] | `ablation/results/tables.md`; baselines tables | ✓ |
| 24 | §7.5 | Guard AUROC frame-shuffled 0.981, uniform 0.998 | 0.981, 0.998 | `b2t25-trust/results/tables.md` | ✓ |
| 25 | §7.6; Table 12 | n_cal 408: P>α 43 % / 46 %; LTT p90 0.052 / 0.054; CRC p90 0.069 / 0.071; n_cal 20: p90 0.089, never 17 % | 0.43 / 0.46; 0.0515 / 0.0539; 0.0686 / 0.0711; 0.0892; 0.17 | `smallcal/results/tables.md` (500 splits) | ✓ (but mixed with 200-split numbers in the same paragraph; Minor 6) |
| 26 | §7.6 | Pool risk above α: LTT 0.5 %, CRC 33 % (ours) | 0.005; 0.33 | r1-derived (`splits_m213/b2t-ours/408/{ltt,crc}/pool_risk_share_above_alpha`) | ✓ |
| 27 | §7.6 | Session-start 20 trials: CRC 0.009 / 0.025, commit 0.04 / 0.32, 6 of 14 days never; sEMG 9 of 18 never | 0.0088 / 0.0252; 0.040 / 0.324; 6/14; emg-calib 9/18 | smallcal tables (per session) | ✓ (condition and 18 vs 19 unexplained; Minor 7) |
| 28 | §7.7; Table 3 | Clean CRC 0.0245, 0.0600, 0.0478, 0.0490, 0.0563, 0.0399; p 0.012, 0.21, 0.54, 0.50, 0.30, 0.60 | identical | `clean-drift/results/tables.md` | ✓ |
| 29 | Table 3 | Exch. ref. B2T ours A 0.018 [0.014, 0.022]; sEMG x-sess. 0.045 [0.018, 0.080]; aci cert/a priori A 0.043 / 0.068 | 0.0182 [0.0135, 0.0221]; 0.0451 [0.0181, 0.0799]; 0.0428 / 0.0682 | clean-drift tables | ✓ |
| 30 | §7.7 | Noticed-only feedback: aci 0.0527 (B), 0.0581 (sEMG x-sess.); certificates 0.0509, 0.0499 | 0.0527 / 0.0509; 0.0581 / 0.0499 | clean-drift tables | ✓ |
| 31 | Discussion | 71 % higher eWPM (8.02 vs 4.68); 96 % of speed (published) | 8.02/4.68 = 1.714; 18.77/19.61 = 0.957 | baselines tables | ✓ |
| 32 | Table 2 / Table 3 / App. J | Silent B2T ours trust 0.002; clean CRC CI [0.015, 0.035] (T2) vs [0.014, 0.035] (T3); replay "39 of 39 (CRC)" | 0.0025; [0.0145, 0.0352] vs [0.0139, 0.0346]; replay CRC n_commit 160, n_wrong 39 (= 0.048, not the clean CRC 0.0245) | baselines tables; clean-drift tables; r1-derived (`ledger_replay_b2t_ours/crc`) | **Minor inconsistencies** (Minor 8, 9) |

**Summary of the number check:** 32 items, 27 exact, 5 with problems. No fabricated or wrong data values. The problems are (i) one substantive omission (sEMG test-set exclusion, row 21), (ii) one attribution error (CRC vs fit-A re-fit, row 7), and (iii) wording/rounding issues (rows 19, 20, 32).

---

## 8. Top-8 actions (in order of priority)

1. **Lead with the risk-controlled rule** (M1, M2): make the pre-specified fit-A + clean CRC (= deployable rule on B2T) the primary row in abstract, Fig. 1, Table 2; show the plug-in policy as "no guarantee"; add the deployable-rule rows; correct the attribution of 0.059 → 0.0245 to CRC.
2. **Add a selective-risk controller** (M3): SGR (Geifman & El-Yaniv 2017) or conditional LTT on the committed item files; report the commit rate and eWPM it allows at error-among-commits ≤ 0.10; promote Fig. 4c.
3. **Add a second intracortical participant** (M5a, NEW-EXP): Willett et al. 2023 / Brain-to-Text '24 public data via a baseline RNN and the existing adapter; use it as the confirmatory test of a frozen configuration (M7).
4. **Quantify split variance on B2T** (M5b–c): repeated day-stratified fit/test assignments and per-day results for plug-in and CRC pipelines.
5. **Ground the clinical premise** (M4): resolve the Card et al. confirmation TODO; add BCI/AAC user-priority and authorship evidence (Huggins 2011/2015; Valencia 2023; Kane 2017); discuss who sets α and why exact-match loss is a limitation.
6. **Report the sEMG leakage exclusion honestly** (M6): both analyses in Appendix G, the exclusion result in Limitation 2, a sensitivity row in Table 2.
7. **Clear all TODOs and finish reproducibility** (M8): authors, ethics wording, MEG seeds, DOI, run time, funding, AI statement.
8. **Re-structure and re-title** (M9, §3.3): narrower contribution list, history-free drift section, shorter Table 2, redesigned Fig. 1 (zoomed safety axis), shorter title that names the single-participant evidence.

---

## 9. Resolved vs still open (written last, after reading the earlier reviews)

I read `round-1-domain.md` (D-Mx), `round-1-methods.md` (Mx), `round-1-response.md` and `round-2-changes.md` only after Sections 1–8 were written. Sections 1–8 were not changed after this reading, except for one note added to Minor 15.

### 9.1 Round-1 domain review

| Item | Status in v2 | Comment |
|---|---|---|
| D-M1 "always commit" is a strawman; add always offer and plain threshold | **Resolved** | Both in Table 2, Fig. 1 and the abstract. Exemplary. |
| D-M2 report commit precision; consider a selective-risk controller | **Partly resolved** | Error among commits is reported everywhere. The selective-risk controller (marked optional in round 1) was not run; I now rate it major (my M3), because it is cheap and it is what makes the safety claim clinically meaningful. |
| D-M3 claims exceed evidence ("three device types") | **Partly resolved** | Abstract and §1 say one participant; MEG is a negative control; "re-fitted per device". The title still reads "evaluated on intracortical, EMG and MEG data" (my M5, §3.3). |
| D-M4 user model and baseline do not fit the populations; no LM in gaze baseline | **Partly resolved** | Word-completion baseline and 8 variants added. The fluency-dependent miss-probability variant was not run. The completion baseline is a context-free unigram, weaker than clinical AAC (my §3.2). |
| D-M5 related work misses BCI speller / ErrP / adaptation literature | **Resolved** for BCI error handling | New gap: BCI/AAC user-priority and authorship literature (my M4). |
| D-M6 decoder metrics and stream mismatches | **Resolved** | Table 6, harness CER explained. |
| D-M7 selective reporting in calibration and ablation | **Resolved** | Unified ablation; guard decision explained transparently. |
| D-M8 leakage checks | **Partly resolved** | LM rebuild done. The test-set exclusion result (8.02 → 6.97 eWPM on sEMG session-cal.) exists in the result files but is not reported, and Limitation 2's wording suggests the opposite (my M6). Participant clusters are now primary (resolved). |
| D-M9 small n_cal, within-day calibration, guarantee wording | **Resolved** | n_cal 20/50/100/408, session-start block, wording fixed. |
| D-M10 length, focus, TODOs | **Mostly resolved** | 20 → 15 pages, 5 main figures. TODOs down from 25 to 8, but 8 remain (my M8). Format/audit content is still more prominent than needed (my M9). |
| D-M11 single seed, single split | **Open** | MEG seeds still training; repeated B2T fit/test assignments not run. The fit-A re-fit shows the operating point moves a lot (my M5b). |
| D minor 6 (Fig. 1 labels overlap) | **Open** | Labels still collide in panel (b). |
| D minor 7 (reliability diagrams) | **Open** | Admitted in text. |
| D minor 11 (exact-match loss sensitivity) | **Open** | Listed as a limitation only. |
| D minor 12 (price silent errors) | **Open** | Not addressed beyond reporting the rate. |
| D minor 21 (ethics, secondary trial data) | **Open** | Still a TODO. |
| D §5 abstract asks: name always offer, commit precision, one participant, composed EMG, MEG negative control | **Mostly resolved** | "Composed" is still missing from the abstract's main results. |

### 9.2 Round-1 methods review

| Item | Status in v2 | Comment |
|---|---|---|
| M1 null-input claim contradicts results | **Resolved** | Signal-destroying vs intent-mismatch controls, named consistently. |
| M2 report commit rate and error among commits | **Resolved** | |
| M3 drift confounded with data reuse; order assumed | **Resolved** | Clean calibration and an exchangeable reference; the drift claim was withdrawn. A model response to review. I suggest re-framing the section without the history (my M9b). |
| M4 guarantees over-interpreted | **Mostly resolved** | Precise wording in §5.4 and App. L. Remaining slip: Fig. 8 caption ties the 90th percentile of test rates to δ (my Minor 6). Larger remaining issue: the abstract says the rule "bounds" wrong text while headlining an unbounded plug-in configuration (my M1; not raised in round 1). |
| M5 user model unvalidated and asymmetric | **Resolved as analysis** | Sensitivity grid and symmetric-offer variant. Two text statements about it do not match the tables (my Minor 2, 3). |
| M6 inferential language too strong | **Mostly resolved** | "No detectable difference" used correctly. |
| M7 seeds, splits, r5 test selection | **Partly resolved** | r5 wording changed as requested; seeds and repeated splits open. |
| M8 ablation incomplete | **Resolved** | |
| M9 black-box gate uses own decoder | **Resolved** | Construction stated in §5.2 and the discussion. |
| M10 no primary endpoints; multiplicity | **Resolved in writing** | Endpoints named and declared post hoc. Consequence not yet drawn: no confirmatory test on untouched data (my M7). |

### 9.3 New in this round (not raised before)

- **M1:** the headline configuration has no guarantee and exceeds α; the 0.059 → 0.0245 fall is a fit-A re-fit effect, not a CRC effect.
- **M2:** Table 2 shows pure CRC, not the recommended deployable rule.
- **M4:** clinical/AAC evidence for the harm and for α; the Card et al. confirmation question.
- **M5a:** a second intracortical participant from public data.
- **M6:** the unreported sEMG test-set exclusion result.
- **Number-check findings:** Minor 2, 3, 7, 8, 9 (user-model wording, silent-error range, 18 vs 19 participants, replayed CRC label, rounding/CI duplicates).

Overall: v2 responded thoroughly and honestly to round 1. Of the 21 round-1 majors, 12 are resolved, 8 are partly or mostly resolved, and 1 is open (D-M11, seeds and repeated splits; the same request is the open part of M7). The remaining distance to acceptance is mainly in framing (lead with the guaranteed rule, name the single participant in the title), one cheap analysis (selective-risk control), one honesty fix (sEMG exclusion), the clinical motivation, and, ideally, one confirmatory test on a second participant.
