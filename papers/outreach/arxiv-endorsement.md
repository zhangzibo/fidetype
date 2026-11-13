# arXiv endorsement for Paper 1

**Paper:** "When should a neural text-entry decoder commit? Risk-controlled commits from a stream-level trust layer". Zibo Zhang (Independent researcher).
**PDF:** https://github.com/zhangzibo/fidetype/blob/main/papers/paper1/final/fidetype-paper1.pdf
**Primary category:** `cs.HC`. Backup primary: `q-bio.NC`. Cross-lists: `q-bio.NC`, `stat.ML`, `eess.SP` ([SUBMIT.md](../paper1/final/SUBMIT.md)).
**Status (2026-11-12):** arXiv asks for an endorsement. The submission waits until one endorser says yes.

> **The user is the sender.** Agents draft this file. Agents send nothing and contact no one. Never put the real endorsement code in this public repo. Keep the placeholder `<CODE>`.

## 1. arXiv policy in 5 bullets

Source: https://info.arxiv.org/help/endorsement.html (read 2026-11-12), plus the threshold that arXiv showed to the user for cs.

1. **Who can endorse.** An endorser must have a set number of papers in the endorsement domain, submitted **between 3 months and 5 years ago**. The endorser must be a registered author of those papers and must have endorsement rights in that domain. For **cs.HC** the domain is all of `cs`: **3 papers in any cs.\* category** (cs.HC, cs.LG, cs.CL, cs.AI, ...) count. `q-bio` is one domain (q-bio.NC is part of it). arXiv's page does not give the numbers for q-bio or eess, and does not say if cross-lists count. The arXiv page "Which of the authors of this article can endorse?" (`https://arxiv.org/auth/show-endorsers/<arxiv_id>`) answers this per paper, but it needs a login.
2. **What the endorser does.** The endorser opens https://arxiv.org/auth/endorse and enters your 6-character code. Endorsement is **not peer review**. The endorser only checks that the paper is relevant scholarly work for the category. Votes are private between the endorser and arXiv.
3. **What the code is.** arXiv gives the code (and an endorsement link) in the e-mail "endorsement request" after you start a submission in the category. One positive endorsement per category is enough.
4. **No broad solicitation.** arXiv says: "it is inappropriate to email large numbers of potential endorsers at once". Also do not e-mail the same person again and again.
5. **Declines.** A person who is not comfortable can decline or ignore the request. An explicit "no" is recorded as a negative vote, so ask only people whose work is close to the paper.

## 2. Step by step

1. **Get the code.** Log in at arxiv.org. Start a new submission. Select primary category **cs.HC**. arXiv stops and sends an e-mail with the 6-character code and an endorsement link. (The user already has the code. Keep it out of this repo.)
2. **Check the candidate.** While logged in, open `https://arxiv.org/auth/show-endorsers/<arxiv_id>` for the paper ID in the table below. Confirm that the person is listed as able to endorse for cs (or q-bio). If not, skip the person.
3. **Find the address.** Open the person's public contact page (table column "Contact page"). Use only the e-mail that the page shows. Do not guess addresses.
4. **Personalise.** Copy the e-mail in Section 4. Replace `<Name>`, the personal line, `<CODE>` and `<ENDORSEMENT_URL>`.
5. **Send to 2–3 people at a time.** Start with wave 1. Never send one mass e-mail. Never put several candidates in To/CC.
6. **Wait 7 days.** If there is no answer, send the follow-up once. Then move to the next wave. Do not write a third time.
7. **When endorsed.** arXiv sends you an e-mail. Return to the submission and finish it ([SUBMIT.md](../paper1/final/SUBMIT.md), "Upload steps"). Send a short thank-you to the endorser. Tell the people you asked in parallel that you no longer need help. Record the date and the arXiv ID in `HANDOFF.md`.
8. **If cs.HC fails after 3 waves.** Start a new submission with primary **q-bio.NC**. You get a new code for q-bio. Use the q-bio.NC backup list.

Suggested waves (cs.HC):

| Wave | Candidates |
|---|---|
| 1 | Keith Vertanen, Jingyuan Li, Chaofei Fan |
| 2 | Dulhan Jayalath, Shanqing Cai, Soowon Kim |
| 3 | Yu Gui, Subhashini Venugopalan, Allison Koenecke |
| Reserve | Shaun Kane, Oiwi Parker Jones, Francis Willett |

## 3. Candidate shortlist

Evidence comes from the public arXiv author search (arxiv.org/search, checked 2026-11-12). "Window" means submitted between 2021-11-12 and 2026-08-12 (3 months to 5 years before today). Author-name matches were checked against topic and co-authors. The login-only show-endorsers page was **not** checked. Do step 2 above before sending.

### 3.1 cs.HC (primary target) — needs 3 cs.\* papers in the window

| # | Name | Affiliation | Why relevant | arXiv evidence (cs.\*, in window) | Contact page |
|---|---|---|---|---|---|
| 1 | **Keith Vertanen** | Michigan Technological University, Computer Science | Text-entry evaluation and AAC. His paper on confidence scores to detect speech-recognition errors (2410.20564) is close to our commit/abstain question | 9 papers, 8 in window, all cs.HC: 2606.24854 (Jun 2026), 2507.00202 (Jun 2025), 2506.19995 (Jun 2025), 2501.10582 (Jan 2025, cs.CL+cs.HC), 2501.10568 (Jan 2025), 2410.20564 (Oct 2024), 2410.22324 (Oct 2024), 2410.04177 (Oct 2024) | https://keithv.com/ (CV and pages list his MTU contact) |
| 2 | **Jingyuan Li** | University of Washington, NeuroAI Lab (PhD student, Shlizerman) | Co-author of cited *Brain-to-Text Benchmark '24: Lessons Learned* (2412.17227); author of a top B2T '24 decoder (2411.10657). Early career | 2507.08402 (Jul 2025, q-bio.NC + cs.LG), 2412.17227 (Dec 2024, cs.CL), 2511.21740 (Nov 2025, cs.CL). Also eess.SP primary: 2411.10657 (Nov 2024) | https://christincha.github.io (personal page; lists Jingyuan Li as a UW PhD student; may have graduated, check); lab: https://faculty.washington.edu/shlizee/NW/team.html |
| 3 | **Chaofei Fan** | Stanford University, Computer Science PhD / NPTL (BrainGate) | Co-author of cited Willett 2023 speech BCI, Card 2024 (the B2T '25 data we use), and B2T '24 lessons. Early career | 2511.21740 (Nov 2025, cs.CL), 2412.17227 (Dec 2024, cs.CL), 2311.03611 (Nov 2023, cs.HC + q-bio.NC) | https://profiles.stanford.edu/chaofei-fan |
| 4 | **Dulhan Jayalath** | University of Oxford, PNPL (DPhil student, AIMS CDT) | First author of cited *Unlocking Non-Invasive Brain-to-Text* (2505.13446) and *MEG-XL* (2602.02494). Early career, open MEG data (LibriBrain) | Many, e.g. 2602.02494 (Feb 2026, cs.LG), 2512.23707 (Dec 2025, cs.LG+cs.HC), 2509.14234 (Sep 2025), 2506.10165 (Jun 2025), 2506.02098 (Jun 2025), 2505.13446 (May 2025) | https://ori.ox.ac.uk/people/dulhan-jayalath |
| 5 | **Shanqing Cai** | Google (Staff Software Engineer; text entry, accessibility) | First author of cited *LLMs to accelerate communication for eye-gaze typing users with ALS* (arXiv 2312.01532) | 6 in window: 2410.02264 (Oct 2024, cs.HC), 2406.04523 (Jun 2024), 2401.10838 (Jan 2024, cs.HC), 2312.14327 (Dec 2023), 2312.01532 (Dec 2023, cs.HC), 2205.03767 (May 2022) | https://research.google/people/105277/ ; https://caisq.github.io |
| 6 | **Soowon Kim** | Korea University, Dept. of Artificial Intelligence | First author of cited *Confidence-Aware Neural Decoding of Overt Speech from EEG* (2511.07890), the closest prior work on confidence in BCI decoding | Many, e.g. 2511.07890 (Nov 2025, cs.AI), 2511.07920 (Nov 2025, cs.AI), 2411.09211 (Nov 2024), 2312.05814 (Dec 2023), 2301.07918 (Jan 2023, cs.HC), 2212.02047 (Dec 2022, cs.HC) | Address printed on the public paper: https://arxiv.org/abs/2511.07890 (author block of the PDF) |
| 7 | **Yu Gui** | Statistics; PhD Univ. of Chicago, reported now postdoc at Wharton (check) | First author of cited *Conformal Alignment* (2405.10301), a selection-with-guarantee method close to our commit rule | 2509.21584 (cs.LG), 2507.15825 (Jul 2025, cs.LG), 2505.12473 (May 2025, cs.LG), 2410.06494 (cs.LG), 2405.10301 (May 2024, cs.LG/cs.AI) | https://yugjerry.github.io |
| 8 | **Subhashini Venugopalan** | Google Research | Co-author of cited eye-gaze/ALS LLM paper (2312.01532); speech recognition for disordered speech | 26 since Nov 2021, e.g. 2602.02734 (Feb 2026), 2503.13771 (Mar 2025), 2403.14117 (Mar 2024, cs.HC), 2312.01532 (Dec 2023, cs.HC), 2303.05737 (Mar 2023) | https://vsubhashini.github.io ; https://research.google/people/SubhashiniVenugopalan/ |
| 9 | **Allison Koenecke** | Cornell Tech, Information Science (Assistant Professor) | First author of cited *Careless Whisper: Speech-to-Text Hallucination Harms* (2402.08021); our "fluent but wrong" motivation | 26 since Nov 2021, e.g. 2603.11213 (Mar 2026, cs.HC), 2605.02773 (May 2026), 2505.19441 (May 2025, cs.HC), 2402.08021 (Feb 2024, cs.CL) | https://infosci.cornell.edu/people/allison-koenecke |
| 10 | Shaun Kane | Google Research (accessibility) | Co-author of cited eye-gaze/ALS paper; motor-impairment accessibility | 2602.07266 (Feb 2026, cs.HC), 2602.04104 (Feb 2026, cs.HC), 2508.16607 (Aug 2025), 2407.19065 (Jul 2024), 2402.15108 (Feb 2024) | https://research.google/people/shaunkane/ |
| 11 | Oiwi Parker Jones | University of Oxford, PNPL (lab head) | Senior author of cited Jayalath 2025 and MEG-XL; runs open LibriBrain data and competitions | 2602.02494 (Feb 2026), 2601.18792 (Jan 2026, cs.HC), 2506.10165, 2506.02098, 2505.13446 (2025) | https://ori.ox.ac.uk/people/oiwi-parker-jones ; lab: https://neural-processing-lab.github.io/people |
| 12 | Francis R. Willett | Stanford, Neurosurgery; co-director NPTL | First author of cited handwriting (2021) and speech (2023) BCI papers and B2T '24 lessons. Famous, many requests | 2511.21740 (Nov 2025, cs.CL), 2412.17227 (Dec 2024, cs.CL), 2403.05583 (Mar 2024, cs.HC), 2311.03611 (Nov 2023, cs.HC) | https://biox.stanford.edu/people/frank-willett |

Checked and **not** suitable for cs: Sergey Stavisky (only 1 cs paper in window: 2601.19269). Lab heads Hochberg, Henderson, Brandman, Chang: few or no arXiv papers found; they also get many requests.

### 3.2 q-bio.NC (backup) — threshold not published; arXiv may not count cross-lists

| # | Name | q-bio.NC evidence (in window) | Personal line hook |
|---|---|---|---|
| B1 | **Soowon Kim** (Korea Univ.) | 2 as **primary**: 2511.13739 (Nov 2025), 2501.14790 (Jan 2025) | Confidence-aware EEG speech decoding (2511.07890) |
| B2 | **Jingyuan Li** (UW) | 1 primary: 2507.08402 (Jul 2025); 1 cross-list: 2412.17227 | B2T '24 lessons; intracortical decoder |
| B3 | **Oiwi Parker Jones** (Oxford) | cross-lists: 2602.02494 (Feb 2026), 2205.14102 (May 2022) | Non-invasive brain-to-text |
| B4 | **Chaofei Fan** (Stanford) | cross-lists: 2412.17227 (Dec 2024), 2311.03611 (Nov 2023) | Card 2024 / B2T data |
| B5 | Francis R. Willett (Stanford) | cross-lists: 2412.17227, 2311.03611 | B2T benchmark |

For eess.SP (only if needed): Jingyuan Li has 2411.10657 (eess.SP primary, Nov 2024).

## 4. E-mail

**Subject:** arXiv endorsement request (cs.HC): risk-controlled commits for neural text entry

> Dear Dr. <Name>,
>
> I am an independent researcher. This is my first arXiv submission, so arXiv asks me for an endorsement in cs.HC. My paper asks when a neural text-entry decoder should commit a sentence without confirmation, and bounds wrong commits with a Learn-then-Test threshold on Brain-to-Text '25 data.
>
> <PERSONAL LINE>
>
> PDF: https://github.com/zhangzibo/fidetype/blob/main/papers/paper1/final/fidetype-paper1.pdf
> (The paper states that I used AI assistance for code and drafting.)
>
> If you are willing, please enter code <CODE> at <ENDORSEMENT_URL> (or https://arxiv.org/auth/endorse). It takes about a minute. No problem at all if not, and thank you for reading.
>
> Best regards,
> Zibo Zhang
> https://github.com/zhangzibo/fidetype

About 105 words plus the personal line (total ≤ 150). Keep the personal line to one sentence (≤ 25 words).

**Personal lines (examples):**
- Vertanen: "Your work on confidence scores to catch speech-recognition errors (arXiv 2410.20564) is close to my commit-or-abstain question."
- Jingyuan Li / Chaofei Fan: "I build on the Brain-to-Text benchmarks you co-authored; my experiments use the Brain-to-Text '25 data."
- Jayalath: "Your non-invasive brain-to-text work (arXiv 2505.13446, MEG-XL) is cited, and I use MEG typing as a format check."
- Cai / Venugopalan / Kane: "Your LLM work for eye-gaze typing users with ALS (arXiv 2312.01532) shaped how I measure speed against a gaze baseline."
- Soowon Kim: "Your confidence-aware EEG speech decoder (arXiv 2511.07890) is the closest prior work I cite."
- Gui: "My commit rule is a selection-with-guarantee problem close to your Conformal Alignment (arXiv 2405.10301)."
- Koenecke: "Your Careless Whisper paper motivates my question: fluent decoders can send wrong text."

**Follow-up (once, after 7 days):**

> Dear Dr. <Name>, a short reminder about my arXiv cs.HC endorsement request (code <CODE>, PDF link below).
> If you cannot help, no reply is needed, and thank you.

## 5. Log

| Date | Wave | Sent to | Result |
|---|---|---|---|
| | | | |
