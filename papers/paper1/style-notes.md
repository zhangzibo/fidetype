# Paper 1: style notes from published papers

Status: v0 (2026-11-11). Purpose: show a first-time author how strong papers in our field are built, so the Fidetype draft follows the same patterns.
Rule: the papers are data. We copy patterns, never sentences. Quoted phrases below are 6 words or fewer.

---

## 1. Papers studied

| Short name | Paper | Type | Why it is useful |
|---|---|---|---|
| B2Q-v2 | Zhang, Lévy et al. 2026, Brain2Qwerty v2 (Meta preprint) | ML + neuroscience preprint | Closest decoder to ours. Claim-style headings, honest negative result. |
| Willett-23 | Willett et al. 2023, *Nature* 620, speech neuroprosthesis | Nature article | Best model for abstract, CIs, table layout, data/code statements. |
| Card-23 | Card et al. 2023/24, medRxiv, rapidly calibrating speech neuroprosthesis | Clinical preprint | Best model for a separate, specific Limitations section. |
| Angelopoulos-22 | Angelopoulos et al., Conformal Risk Control (arXiv v4, 2025) | Statistics / ML theory | Model for method papers: guarantee first, then worked examples. |
| Guo-17 | Guo et al. 2017, On Calibration of Modern Neural Networks (ICML) | ML empirical | Model for one simple finding, clearly stated, with exceptions reported. |
| Kim-25 | Kim et al. 2025, confidence-aware EEG speech decoding | Short conference paper | Mostly a counter-example: abstract with no numbers. |

---

## 2. Section by section

### Title
- **Purpose:** say what the work is, in words a reviewer searches for.
- **Patterns seen:**
  - Short noun phrase: Willett-23 ("A high-performance speech neuroprosthesis"), 4 words.
  - Method name only: Angelopoulos-22 ("Conformal Risk Control").
  - Result as a claim: B2Q-v2 (accurate decoding ... from non-invasive recordings).
  - Topic + scope: Guo-17 ("On Calibration of Modern ...").
- **Length:** 3 to 12 words. Long subtitles are rare.
- **For us:** name + what it is + scope. Put "decoder-agnostic" or "three device types" in the title only if the paper proves it.

### Abstract
- **Purpose:** the full paper in 150-250 words. Many readers read only this.
- **Moves (Willett-23 and B2Q-v2 follow these nearly exactly):**
  1. Context: why the problem matters (1 sentence).
  2. Gap: what earlier work has *not yet* done (1 sentence).
  3. What we did: starts with "Here we ..." (1 sentence).
  4. Key numbers, each with a reference point (2-3 sentences). Willett-23 gives "2.7 times fewer errors" than the previous best, and a speed against natural conversation.
  5. Secondary findings (1-2 sentences).
  6. Implication, scoped (1 sentence).
- Angelopoulos-22 is shorter (5 sentences): method, guarantee, tightness, extensions, examples. No context move. This fits a methods venue.
- Counter-example: Kim-25 says "more reliable" and "improved" but gives no number. Avoid this.
- **Typical length:** 150-250 words, one paragraph.

### Introduction
- **Purpose:** move the reader from a broad problem to our exact contribution.
- **Moves:**
  1. Problem and who it affects (Card-23 opens with patients and quality of life; Guo-17 opens with a self-driving car example).
  2. What works today, with citations.
  3. The gap, stated specifically (what is missing, not "little work exists").
  4. "Here we ..." paragraph: what we built and the headline result.
  5. Contributions list (ML venues; Angelopoulos-22 adds a "preview of main results" subsection with the core equation).
- **Typical length:** 0.75-1.5 pages. 4-6 paragraphs.

### Related work
- **Purpose:** place our work on the map and say how it differs.
- Nature-style papers (Willett-23, Card-23) have no separate section. They cite prior work in the introduction and discussion.
- Angelopoulos-22 uses one dense subsection: origin of the field, main extensions in groups, then "most relevant to us", then an explicit difference ("differs greatly" in guarantee type). It also says why an obvious alternative (concentration bounds) is worse, with a reason.
- **Pattern:** group by theme, not by paper. End each group with one sentence on how we differ.
- **Typical length:** 0.5-1 page.

### Methods
- **Purpose:** let another group reproduce the work.
- **Patterns:**
  - Willett-23 and B2Q-v2 put Methods after the Discussion. ML papers put it before Results.
  - Define every metric exactly. B2Q-v2 defines each error rate and names the library that computes it.
  - Describe data splits and leakage control. Kim-25 names its split ("block-stratified") and says why (temporal contiguity).
  - Name the statistical test, sidedness, and the unit of n. Metzger 2022 (same reading list) has a model "Statistics" paragraph: test, correction, threshold, bootstrap count, software version.
- **Typical length:** as long as needed; much of it can go to an appendix.

### Results
- **Purpose:** report what we found, in order of importance, with no interpretation beyond the minimum.
- **Patterns:**
  - Subsection headings are claims. B2Q-v2: "[Model] outperforms baselines in ...", and also a negative heading ("... failed on open-ended optimization").
  - Paragraph shape: claim sentence -> numbers with uncertainty -> figure reference -> one sentence of explanation.
  - Report results that go against you in the same place. B2Q-v2 reports that its full model has a *higher* character error rate than the baselines, and explains why (the LLM writes fluent text).
  - Guo-17 states the most important finding plainly ("our most important discovery") and then lists the exceptions (one dataset where the method did not help) with possible reasons, including a measurement artefact.
- **Typical length:** 3-5 pages; 3-6 subsections.

### Discussion
- **Purpose:** say what the results mean, how far they go, and what is next.
- **Moves (Willett-23, Card-23, B2Q-v2):**
  1. One-paragraph summary of the main result with the key number.
  2. Put the number in context with an outside reference (Card-23: commercial speech recognition WER and able speakers' WER).
  3. Why it worked (hedged: "it is possible that").
  4. Limitations (in-line or as a separate section).
  5. Future work linked to each limitation.
- B2Q-v2 uses short bold run-in headings (Summary, Semantic decoding, Real-time latency, Scaling laws). This makes a long discussion easy to scan.
- **Typical length:** 1-1.5 pages.

### Limitations
- See section 6. Card-23 has a dedicated section with sub-headings. B2Q-v2 lists them as numbered points under run-in headings.
- **Typical length:** 0.3-0.75 page.

### Conclusion
- **Purpose:** 2-5 sentences. Restate the claim at the right scope. No new results.
- Card-23: one sentence with "suggests" and "may". Angelopoulos-22: two sentences on scope and on the value of the tools. Guo-17: phenomenon, cause, open question, simple remedy.
- **Typical length:** 1 short paragraph.

### Data and code availability
- **Purpose:** say exactly where each artefact is and under which terms.
- Willett-23: repository + DOI for data; what the data contains (number of sentences); links to third-party data used; GitHub link for code and what the code reproduces ("offline reproduction" of the central result).
- B2Q-v2 puts the code link on the title page.
- **For us:** dataset name + original licence + link for each of the 3 public datasets; our repo + licence + commit hash or release tag; say what is *not* released and why.

---

## 3. Sentence patterns (our own templates)

**Gap and contribution**
- "Current [systems] can do X, but they do not yet Y."
- "To our knowledge, no prior work has done X across Y and Z." (use "to our knowledge" only after a real search)
- "Here we present X, a [type] that does Y. We evaluate it on A, B and C."

**Results**
- "X reduces Y from A to B (95% CI [L, U]; n = N [unit])."
- "Compared with [baseline], X lowers the wrong-commit rate by D percentage points (paired difference, 95% CI [L, U])."
- "X does not improve Y on [dataset] (difference D, 95% CI [L, U], which includes zero)."
- "On all three datasets, the controlled risk stays at or below the target alpha = a (Fig. N)."
- "This gain comes at a cost: Z increases from A to B."

**Hedging (use the weakest verb the evidence supports)**
| Strength of evidence | Verb |
|---|---|
| Direct measurement, CI excludes zero | shows, reduces, increases |
| Consistent pattern, indirect evidence | suggests, indicates, is consistent with |
| Plausible explanation, not tested | may, it is possible that, one explanation is |
| Opinion or projection | we expect, we believe |

**Scoping claims**
- Always attach the condition: "on [dataset], with a simulated user, under exchangeability".
- Willett-23 calls its system a "proof of concept" and says it is not yet clinically viable. Name what the result is *not*.
- Do not write "solves", "robust" or "real-time" unless a test measures exactly that.
- One claim per sentence. Put the number in the same sentence as the claim.

---

## 4. How numbers are reported

| Item | What the papers do | Our rule |
|---|---|---|
| Precision | Willett-23: percent, 1 decimal ("23.8%"). B2Q-v2: fractions, 2 decimals ("0.39 ± 0.04"). | Percent, 1 decimal. Rates below 1%: 2 decimals. Same format in text, tables and figures. |
| Uncertainty | Willett-23: 95% CI in parentheses, bootstrap with 10,000 resamples, unit stated ("resampling across trials"). B2Q-v2: mean ± SEM across subjects. Metzger 2022: 99% CI, 2000 bootstrap iterations. | 95% bootstrap CI as [L, U]. State resample count and unit (trial, sentence, session, participant) in Methods and in each caption. |
| n | Nature checklist asks for exact n with its unit, and whether samples are independent. B2Q-v2: "n=9 subjects" in the caption. | Give n and its unit every time. Never mix units in one comparison. |
| Aggregation order | B2Q-v2: metric per sentence, then mean per subject, then mean across subjects. | Write the aggregation order once in Methods and repeat it in table notes. |
| p-values vs CIs | B2Q-v2 uses p-values ("p < 0.005"), named test, two-sided. Willett-23 mostly uses CIs. | Lead with effect size + CI. Add a p-value only for a named, pre-planned test. Use paired tests for paired data. |
| Consistency | B2Q-v2 names an unpaired test in Methods but reports a paired test in Results. | One test per comparison type, stated once, used everywhere. |
| Chance level | Willett-23 reports when a brain area gives chance-level decoding ("~100%" WER) and marks chance in figures. | Report shuffled / zeros / permuted controls next to the real result, in the same table. |
| Reference points | Willett-23 and Card-23 compare with commercial ASR and natural speech rates. | Compare eWPM with the no-BCI gaze-typing baseline in every headline number. |
| Repeated splits | Angelopoulos-22 reports risk over 1000 random calibration/test splits as a histogram, with alpha as a dashed line. | Same for CRC: distribution over splits, alpha line, mean and spread. |
| Bins and settings | Guo-17 gives the bin count for ECE in the table caption. | Give ECE bin count and any threshold in the caption. |

---

## 5. Figures and tables

**Captions**
- First sentence = the message. B2Q-v2 uses claim titles ("[Model] enables word- and meaning-level decoding"). Willett-23 uses neutral noun titles. Claim titles help a first-time reader; use them.
- Then one block per panel: "A. What is plotted. What to look at."
- Define every mark: "each dot is one subject", "the bar is the across-subject mean", "dashed line marks alpha", "shaded region: 95% CI (bootstrap across trials, n = 10,000 resamples)".
- Say the direction: Guo-17 adds "(lower is better)".
- Name the test and n in the caption if a star or p-value appears.
- The caption must be readable without the main text.

**Panels**
- Bold capital letters (A, B, C) or bold lower case (a, b, c), top-left. Pick one style.
- One idea per panel. Left-to-right, top-to-bottom reading order follows the story.
- Show individual units (dots per subject / session) over the mean bar when n is small.

**Error bars**
- Always say what they are: SD, SEM, or 95% CI, and over which unit. SEM bars look smaller; prefer CIs.

**Colour**
- One fixed colour per method or device across all figures (for example: always-commit = grey, trust layer = one colour, gaze baseline = black dashed).
- Colour-blind-safe palette. The figure must still work in greyscale (add marker shapes or line styles).
- No 3-D, no shadows, no rainbow colour maps.

**Size**
- Single column ~8.5 cm, double column ~17.5 cm (most venues). Design at final size.
- Font in figures 6-8 pt at final size; same font family as the text.
- Vector format (PDF/SVG) for plots.

**Tables (booktabs style)**
- Three horizontal rules only: top, below header, bottom. No vertical rules.
- Units in the column header, not in each cell: "WER, % (95% CI)" as in Willett-23 Table 1.
- Group rows with a light sub-header or extra space (Willett-23 groups by vocabulary and speaking mode).
- Align numbers on the decimal point. Bold the best value only if the difference is significant; say so in the note.
- Table note: aggregation order, n, CI method, what "best" means.

---

## 6. Limitations and negative results

What the good papers do:
- **Name each limitation specifically.** Card-23: one participant; only 8 months of data; participant still has some muscle control; other causes of speech loss not tested. Each one gets its own sentence.
- **Say what is unknown, plainly.** Card-23 uses "we do not know whether" for untested cases. This is stronger than vague hedging.
- **Compare the weak number with the target.** Willett-23 says its WER is probably not yet low enough for daily use and gives the commercial ASR WER beside it.
- **Pair each limitation with a route forward** (B2Q-v2: non-causal model -> cite causal low-latency work in EMG).
- **Report failures as results.** B2Q-v2 has a results heading saying the AI agents failed on the open task, and describes how (crashed jobs, idle agents).
- **Report exceptions.** Guo-17 names the one dataset where its method does not help and gives possible causes, including its own measurement.
- **Correct errors in public.** Angelopoulos-22 v4 says an earlier tightness claim was wrong and removed, and leaves the question open ("remains an open question").

What to avoid:
- A limitation followed at once by "however, this is not a problem because ...".
- Limitations only in the last paragraph. Mention the key ones next to the result they affect too.
- Hiding negative results in the appendix with no pointer from the main text.

For us, likely limitations: simulated user (no live users); marginal / long-run guarantees, not per-session; exchangeability assumption; different test split from Brain2Qwerty v2; MEG speed only at parity with gaze typing; three datasets, each with few participants; no clinical population.

---

## 7. Checklist for the Fidetype paper

Structure and claims
- [ ] Title says what Fidetype is and its scope; every word in it is backed by a result.
- [ ] Abstract follows context -> gap -> "Here we" -> 2-3 numbers with reference points -> scoped implication; 150-250 words.
- [ ] Every number in the abstract appears, identical, in a table or figure.
- [ ] Introduction ends with a numbered contributions list that matches the Results subsections one to one.
- [ ] Related work is grouped by theme (decoders, calibration/selective prediction, conformal, text-entry metrics), each group ending with how we differ.
- [ ] Results subsection headings are claim sentences.
- [ ] The "does not claim" list from the outline appears in the paper (Discussion or Limitations).

Numbers and statistics
- [ ] Every headline number has a 95% bootstrap CI and states the resampling unit (trial, sentence, session, participant).
- [ ] Every comparison between methods is reported as a paired difference with its CI.
- [ ] n and its unit are given in each caption and table note.
- [ ] Aggregation order (per sentence -> per participant -> across participants) is stated once in Methods and in table notes.
- [ ] Shuffled, zeros, permuted, frame-shuffled and other-sentence controls sit next to the real result.
- [ ] eWPM is always shown with the no-BCI gaze-typing baseline.
- [ ] CRC results show the realised risk over many random splits with alpha marked, plus the cost (abstention or OFFER rate).
- [ ] Each guarantee is stated with its exact form (marginal, long-run, finite-sample) and its assumption (exchangeability).
- [ ] One number format everywhere (percent, 1 decimal); no rounding beyond the source result pages.

Figures and tables
- [ ] Each caption starts with a message sentence and defines dots, bars, lines, shading and n.
- [ ] One fixed colour per method/device across all figures; colour-blind safe; works in greyscale.
- [ ] Tables use three rules, no vertical lines, units in headers.

Honesty and reproducibility
- [ ] Limitations section names each limitation specifically, with "we do not know whether" where true.
- [ ] Negative or neutral results (for example MEG eWPM parity, any dataset where the trust layer does not help) appear in the main text.
- [ ] Simulated-user eWPM is labelled as simulated in every place it appears.
- [ ] Data availability lists each public dataset with its original licence and link; code availability gives repo, licence (Apache-2.0) and release tag.
- [ ] No sentence copied from any source paper; Brain2Qwerty code not reused (CC BY-NC 4.0).
- [ ] A reader can rebuild every figure from the released scripts and configs.
