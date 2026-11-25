---
title: Novelty check 2026-11 — the three north-star claims (P15-10)
type: question
tags: [planning, north-star, novelty, prior-art, literature-check, conformal, online-learning, hallucination, cross-modality, p15]
sources: [adaptive-conformal-inference, continual-calibration, conformal-gating-mi-bci, corteg-eeg-to-ecog, card-2026-home-use, corp, wilson-hmm-recalibration, roy-input-affine-recalibration, probabilistic-co-control, confidence-ordering-reversal, damri-risk-controlled-asr, levin-cross-brain-transfer, chen-falcon-h2-fewshot, falcon-benchmark, possm, ndt3, mona-lisa]
updated: 2026-11-24
---

# Novelty check 2026-11 (P15-10)

**Question:** are the three novelty claims of the [north star](north-star.md) true, as written, before we state them in public? Roadmap task [P15-10](roadmap-standard.md#p15-10-focused-literature-check).

**Answer in one table:**

| Claim | Verdict | Main reason |
|---|---|---|
| **C1** (F1) | **Holds with narrower wording** | No BCI work found. But the guarantee mechanism is not new: online conformal bounds already stay valid when a model is refit ([ACI](../sources/adaptive-conformal-inference.md); [continual calibration](../sources/continual-calibration.md)) |
| **C2** (F2) | **Holds with narrower wording** | No run-time grounding check with a bound for brain-decoded text found. But run-time conformal abstention in a BCI exists ([conformal gating](../sources/conformal-gating-mi-bci.md), closed-set commands) |
| **C3** (F3) | **Part 1 holds; part 2 falsified as written** | No implant + EMG + MEG/EEG text model found. But transfer to a new recording modality **is** reported ([CORTEG](../sources/corteg-eeg-to-ecog.md), EEG → ECoG), only not for text |

Only the "safe public wording" lines below may go into the README or a post.

## Method
- **Date:** 2026-11-15. **Scope:** published papers and preprints up to that date.
- **Claims tested (exact wording from the task):**
  - C1: "No published BCI work updates the decoder from user feedback while keeping a stated error bound valid through each update."
  - C2: "No published work checks brain-decoded text against the neural evidence at run time with a risk-controlled hallucination bound."
  - C3: "No published model is trained jointly on implant + EMG + MEG/EEG language data for text, or reports transfer to a new modality."
- **Search tools and what worked:**

| Tool | Use | Result |
|---|---|---|
| Web search (several engines behind one tool) | 3–5 phrasings per claim | worked |
| arXiv API (`export.arxiv.org`) | 26 field queries (title / abstract / all) | worked |
| Europe PMC REST (covers PubMed, bioRxiv, medRxiv, Research Square) | 5 Boolean queries; abstracts by DOI | worked |
| OpenAlex (forward citations) | citing papers of CORP, DietCORP, ALIGN, NoMAD, Card 2024, BIT, BrainOmni, NeuGPT, NDT3, Tang & Huth 2023, ACI, conformal factuality, conformal abstention, both semi-bandit conformal papers | worked; recent arXiv citations are incomplete |
| Semantic Scholar graph API | search and citations | **refused** (HTTP 429 on every call); not retried |
| OpenReview API | 7 keyword searches | partial: titles returned once, then a challenge page (HTTP 403); not retried |
| Google Scholar | — | not used (no automated access) |
| bioRxiv full text, nature.com, PMC HTML | full-text reads | refused (429 / login / browser check); used Europe PMC full text or abstracts instead |

- **Full texts read (arXiv HTML or Europe PMC XML):** CORP, DietCORP, ALIGN, Gibbs & Candès ACI (ar5iv), continual calibration, CORTEG, NeuGPT, NOBEL, "Decoding the Multimodal Mind", SemKey, the Brain-to-Language survey (2609.27650, all four parts), Fu et al. 2026 (theorem T4). **Abstract only:** conformal gating (JNE, paywalled), Probabilistic Co-Control (bioRxiv refused), BIT-LLM, the semi-bandit papers, conformal abstention, conformal factuality, Fogg et al. 2026, Swanson et al. 2026.
- **Limit:** "not found" means "not found with these tools on this date". Google Scholar and Semantic Scholar were not available. A paper under review and not yet public cannot be found.

## C1 (F1): safe self-improving BCI

### What the sources say
**BCI decoders that learn from use (no bound):**
- [CORP](https://arxiv.org/abs/2311.03611) (NeurIPS 2023) "continually retrains the decoder using these corrected outputs", "updating the decoder after every sentence". Guards: a replay buffer, noise augmentation and a loss threshold. It states no error bound and no update gate. It notes "we lack a validation set" and "One limitation of CORP lies in its dependence on the accuracy of the pseudo-labels" (Results).
- [DietCORP](https://arxiv.org/abs/2507.02800) (NeurIPS 2025): "Only the patch embedding module is adapted" (Section 3.7); the only safeguard is gradient-norm clipping to 0.5. No bound, no gate, no rollback.
- [ALIGN](https://arxiv.org/abs/2603.18299) (2026), Section 2: pseudo-labels "may become systematically inaccurate, leading to runaway error compounding". ALIGN gives no formal bound.
- Card et al. 2024 (NEJM) update the decoder with sentences that the user confirmed by eye tracking (as summarised in the [Brain-to-Language survey](https://arxiv.org/abs/2609.27650)). No bound is reported.
- The systematic review of iBCI recalibration (Swanson et al., *J. Neural Eng.* 2026, [doi](https://doi.org/10.1088/1741-2552/ae7694)) reports manual, semi-automatic and automatic recalibration. Its abstract names no error guarantee.
- Gu et al. 2026 (*npj Biomed. Innov.*, [doi](https://doi.org/10.1038/s44385-026-00119-0)) call for a protocol that says when adaptation may go ahead and when to fall back to an earlier decoder. This is a governance argument, not a bound.
- Fu et al. 2026 (*Front. Hum. Neurosci.*, PMC13624153), theorem T4: closed-loop learning converges toward the Bayes error under Markov and capacity assumptions. It is a convergence statement for a model, not a stated error bound that a deployed decoder keeps through each update.

**Guarantees that survive model updates (not BCI):**
- [Gibbs & Candès](../sources/adaptive-conformal-inference.md), Section 2: "we assume that at each time t we are given a fitted score function" S_t, and the functions "should be regularly re-estimated". Proposition 4.1 bounds the long-run miscoverage for any sequence; the proof does not use stationarity. Their experiments refit the model at each step (GARCH, Section 2.2).
- [Continual calibration](../sources/continual-calibration.md) (2026) refits the conformal threshold after each fine-tuning step. Theorem 6 gives exact finite-sample coverage with a held-out labelled buffer. LLMs, not BCI.
- Semi-bandit online conformal ([Ge, Bastani & Bastani 2024](https://arxiv.org/abs/2405.13268); [OCP-Unlock+](https://arxiv.org/abs/2604.17984), ICLR 2026) keeps long-run coverage when the label is seen only if it is inside the shown set. No BCI use found.

**Conformal methods in BCI (static decoder):**
- [Conformal gating](../sources/conformal-gating-mi-bci.md) (Xing & Nagarajan, JNE 2026): conformal command gate across sessions; fixed DeepConvNet.
- [ConformalHDC](https://arxiv.org/abs/2602.21446) (2026): split conformal on hippocampal spikes; finite-sample coverage under exchangeability.
- [Confidence-aware EEG speech](https://arxiv.org/abs/2511.07890) (2025): selective abstention; it lists conformal guarantees and online adaptation as future work.
- Geometry-aware conformal motor decoding (COPA 2026, from the earlier sweep).

### Verdict: holds with narrower wording
No found BCI work updates its decoder from user feedback **and** states an error bound that stays valid across those updates. The BCI part of C1 holds. But the bare idea "a bound that stays valid while the model changes" is old in general ML (ACI 2021) and active in 2026 (continual calibration). C1 must not suggest a new statistical result.

> **Our take:** the novelty is the composition in a BCI: feedback-driven decoder updates + an update gate + an online risk bound whose scope is stated (long-run or alarm, not per session) + silent errors reported outside the bound. Card 2024 and CORP are the closest "learns from use" systems. ACI and continual calibration are the closest "bound through updates" methods. We must cite all four.

**Safe public wording (C1):** "To our knowledge (literature check of 2026-11-15), no published BCI study updates its decoder from user feedback and reports a stated error bound — for example a long-run limit on the wrong-commit rate — that stays valid across those updates. We use known online conformal methods (Gibbs & Candès 2021) for the bound; what is new is applying them, with an update gate, to a self-improving BCI."

Do **not** say: "first guarantee for an adaptive model", "first conformal BCI", "provably safe learning".

## C2 (F2): faithful LLM decoding

### What the sources say
**Faithfulness in brain-to-text is tested offline only:**
- [Jo et al. 2024](https://arxiv.org/abs/2405.06459): EEG-to-text models score the same or better on noise (also cited this way in the [survey](https://arxiv.org/abs/2609.27650), Parts 2–3).
- [BIT-LLM](https://icml.cc/virtual/2026/poster/65031) (ICML 2026, fMRI-to-text): "We conduct perturbation-based sanity checks by zeroing fMRI inputs or shuffling voxel values". This is an offline test; no per-output check, no abstention, no bound.
- [SemKey](https://arxiv.org/abs/2603.03312) (2026, EEG-to-text) names "Signal Neglect" and uses a "Noise Input Test" (Section 4.2). It has no per-output verifier and no stated bound (no conformal or risk control in the text).
- [GLIM](https://arxiv.org/abs/2505.17099) (2025) treats hallucination as posterior collapse and changes training and evaluation. No run-time check.
- The [Brain-to-Language survey](https://arxiv.org/abs/2609.27650) (2026-09) asks for "a significant margin over noise- and shuffled-input baselines". We found no section on run-time hallucination checks or guarantees in it.
- [From Neurons to Conversation](https://arxiv.org/abs/2609.36736) (review, 2026-09) names the trade-off between "language-model fluency and faithful neural evidence" and asks for "safeguards against unintended decoding". It proposes no method.

**Closest BCI uncertainty work:**
- Probabilistic Co-Control (Huang, …, Mishne, Gilja; bioRxiv 2026, [doi](https://doi.org/10.64898/2026.04.02.715749)): CTC decoders are "systematically over-confident"; a cross-entropy objective gives better calibration (ECE, resolution), better LM re-ranking and "reliable error detection". Calibration metrics, no stated bound, and no check of LLM text against the neural evidence (abstract only; full text refused).
- [Conformal gating](../sources/conformal-gating-mi-bci.md) (JNE 2026): run-time conformal abstention for 2- and 4-class EEG commands. No text and no language model.

**Hallucination bounds for text LLMs (not neural):** [conformal factuality](https://arxiv.org/abs/2402.10978) (ICML 2024), [conformal abstention](https://arxiv.org/abs/2405.01563) (2024) and many 2025–2026 follow-ups. In the citing papers of both (OpenAlex, filtered by brain / EEG / neural / speech) we found no brain-decoding paper.

### Verdict: holds with narrower wording
No found work checks LLM-produced brain-decoded text against the neural evidence at run time with a stated, distribution-free bound on the rate of unsupported words. Two narrowings are necessary. (1) Run-time conformal abstention already exists in a BCI for closed-set commands, so the claim must name LLM-generated or LLM-rescored **text**. (2) Hallucination bounds exist for text LLMs, so the claim must name the **neural evidence** as the reference.

> **Our take:** C2 is the clearest gap. But it is now a named problem (BIT-LLM, SemKey, Co-Control, two 2026 reviews), so the window may be short. The Co-Control group (Gilja, Mishne) is the most likely to publish a guarantee next.

**Safe public wording (C2):** "To our knowledge (literature check of 2026-11-15), no published brain-to-text system checks language-model output against the neural evidence at run time with a stated, distribution-free bound on the rate of unsupported (hallucinated) words that it commits. Earlier work tests faithfulness offline (noise or shuffled inputs) or bounds errors for closed-set BCI commands."

Do **not** say: "first hallucination control for BCIs", "first risk-controlled BCI", "first BCI abstention".

## C3 (F3): cross-body model

### What the sources say
**Largest modality unions found (none has implant + EMG + MEG/EEG):**

| Work | Modalities | Text task | Held-out modality test |
|---|---|---|---|
| [BrainOmni](https://arxiv.org/abs/2505.18185) (NeurIPS 2025) | EEG + MEG | no (says "unseen EEG and MEG devices") | new devices, not a new modality |
| [NOBEL](https://arxiv.org/abs/2602.21522) (2026) | EEG + MEG + fMRI (+ stimuli) | text answers, mostly classification; NSD captions | none ("Every evaluated modality appears in training") |
| ["Decoding the Multimodal Mind"](https://arxiv.org/abs/2505.10356) (ACL Findings 2026) | fMRI + MEG + EEG | perceived-stimulus text | none |
| [Brain-OF](https://arxiv.org/abs/2602.23410) (2026) | fMRI + EEG + MEG | no | not reported (abstract) |
| [iBrain](https://arxiv.org/abs/2609.06960) (2026) | iEEG + spikes | no | not reported (abstract) |
| [Inoue et al.](https://arxiv.org/abs/2506.13835) (Interspeech 2025) | EEG + EMG | word classes | none |
| [NeuGPT](https://arxiv.org/abs/2410.20916) (2024) | **MEG only** in experiments | MEG-MASC text | none |
| [BIT](https://arxiv.org/abs/2511.21740), [Fogg et al. 2026](https://doi.org/10.64898/2026.07.23.739430) | intracortical only | yes | cross-species / cross-person, not cross-modality |

> **Contradiction:** our earlier sweep and the [north star](north-star.md) said NeuGPT covers "six brain modalities to text". The NeuGPT full text uses only MEG (MEG-MASC) for brain-to-text; the other modalities appear only in the motivation and in future plans ("we plan to include ECoG and fMRI data"). We now use the full-text reading.

**Transfer to a new recording modality:** [CORTEG](../sources/corteg-eeg-to-ecog.md) (2026) adapts a scalp-EEG foundation model to ECoG and stereo-EEG, with 10–30 min calibration per new patient. Tasks: finger trajectory, audio envelope, sEEG word-vs-non-word classification. No text decoding. Its related work also cites a pilot EEG → ECoG study and fMRI → EEG / MEG → EEG transfers. A pre-trained EEG-to-MEG generative framework (arXiv 2602.06990, title only) also points the same way. The [survey](https://arxiv.org/abs/2609.27650) lists transfers between speech **modes** (overt → whispered / inner / mouthed), which are not recording modalities.

### Verdict: part 1 holds; part 2 falsified as written
- Part 1 ("trained jointly on implant + EMG + MEG/EEG language data for text"): **holds**. No such model found.
- Part 2 ("or reports transfer to a new modality"): **false as written**, because CORTEG reports EEG → ECoG / sEEG transfer. It holds only as "transfer to a new recording modality **for text decoding**".

> **Our take:** F3's real gap is narrow and the field moves fast (BrainOmni → NOBEL → CORTEG in 18 months). "Text from a new modality with minutes of data" is still open. We should claim it only after we show it, and we must name the cross-person confound.

**Safe public wording (C3):** "To our knowledge (literature check of 2026-11-15), no published model is trained jointly on implanted, EMG and MEG/EEG recordings for text output, and no published study reports text decoding from a recording modality that the model did not see in training. Cross-modality transfer exists for other tasks (for example scalp EEG to ECoG, CORTEG 2026)."

Do **not** say: "first cross-modality transfer", "first multimodal brain-to-text model".

## Update 2026-11-24 (literature check)
A second check on 2026-11-24 (F1 + F2 and F3 reports, scratch notes, not committed) found new close work. Every number below was checked again on the primary source before filing. The source pages hold the quotes.

| Claim | Verdict now | New closest work | Change |
|---|---|---|---|
| **C1** (F1) | Holds, **narrower again** | [Card et al. 2026](../sources/card-2026-home-use.md): the real T15 home system fine-tunes continuously and keeps a checkpoint "only if validation performance improved"; T15 rates every sentence. [CORP](../sources/corp.md), [Wilson et al. 2025](../sources/wilson-hmm-recalibration.md), [Roy et al. 2026](../sources/roy-input-affine-recalibration.md): learning or recalibration from use, no bound | An update gate exists in daily BCI use. Our novelty is the **statistical** gate and the bound, not the gate |
| **C2** (F2) | Holds | [Probabilistic Co-Control](../sources/probabilistic-co-control.md) (full text now read), [confidence-ordering reversal](../sources/confidence-ordering-reversal.md) (MEG, no guarantee), [Damri & Laufer-Goldshtein 2026](../sources/damri-risk-controlled-asr.md) (LTT for LLM ASR correction, not neural). ACI is used in an EEG speech-perception preprint (chen d. 2026, Research Square, doi 10.21203/rs.3.rs-11134147/v1; Europe PMC abstract checked 2026-11-24: Gibbs-Candès ACI "repairs coverage to ∼99% in 2/3 subjects" on speech-perception EEG, 3 subjects; not ingested) | Add "first conformal / ACI in speech BCI" to the do-not-say list |
| **C3** (F3) | Part 1 holds | [Levin et al. 2026](../sources/levin-cross-brain-transfer.md): cross-person transfer of intracortical speech and handwriting decoders, gains below 200 target sentences; [Chen et al. 2026](../sources/chen-falcon-h2-fewshot.md) on [FALCON H2](../sources/falcon-benchmark.md); [POSSM](../sources/possm.md) (monkey → T5 classification); [NDT3](../sources/ndt3.md) (gains below about 1.5 h); [MONA LISA](../sources/mona-lisa.md) (EMG-audio shared latent space) | Add "Cross-person transfer of intracortical text decoders exists (Levin et al. 2026)" to the closest works. Still no text decoding from a held-out recording modality found |

### Claim-wording rules (from 2026-11-24)
Never say, in public or in a paper:
- "first cross-person transfer" of BCI decoders ([Levin et al. 2026](../sources/levin-cross-brain-transfer.md));
- "first conformal BCI for speech" or "first ACI in speech BCI" (chen d. 2026, EEG speech-envelope tracking with ACI);
- "first gated decoder update", "first BCI that learns from daily use" ([Card et al. 2026](../sources/card-2026-home-use.md), [CORP](../sources/corp.md)).

**F1 novelty, the only form to use:** "a statistically tested update gate (stated level, null controls) plus a stated long-run wrong-commit bound". Cite Card 2026 as the closest real system.

**Safe public wording (C1, replaces the 2026-11-15 line):** "To our knowledge (literature checks of 2026-11-15 and 2026-11-24), no published BCI study updates its decoder from user feedback behind a statistically tested update gate (a test at a stated level, with null controls) and reports a stated long-run bound on the wrong-commit rate that stays valid across those updates. Real BCI systems already fine-tune from daily use and keep an update only if validation improves (Card et al. 2026); we use known online conformal methods (Gibbs & Candès 2021) for the bound."

### Corrections to this page
> **Contradiction:** the C2 section above (from the abstract) says that Co-Control's cross-entropy objective "gives better calibration (ECE, resolution)". The full text shows that CE alone has a **higher** ECE than CTC (0.051 vs 0.025, under-confident), better resolution and AUPR, and a small PER cost (0.232 vs 0.212). Only the CTC ⊗ CE fusion lowers ECE ([source page](../sources/probabilistic-co-control.md)). Both readings are kept; the full-text one is the one to use.

> **Our take:** the F3 picture shifted. The sources agree that transfer is a **low-data effect** (Levin: < 200 sentences; NDT3: < 1.5 h) and that the working mechanism is **per-signal encoders + small per-session input layers + a shared output space** (Levin, Chen, Roy, MONA LISA). A shared input trunk across modalities has text evidence nowhere. F3 stays a product goal ("any body signal, one output format, one trust layer"); its modelling claim becomes this mechanism.

## Effect on the north star
- The pillars and experiments do not change.
- The three safe wordings replace the gap table wording in the [north star](north-star.md#why-this-is-new).
- F2 now looks as strong as F1 on novelty. F1 keeps the lead for feasibility (our data, our code).

## Related pages
- [North star](north-star.md), [roadmap P15](roadmap-standard.md#p15-frontier-added-2026-11-15-leads)
- Sources: [ACI](../sources/adaptive-conformal-inference.md), [continual calibration](../sources/continual-calibration.md), [conformal gating](../sources/conformal-gating-mi-bci.md), [CORTEG](../sources/corteg-eeg-to-ecog.md)
- [Conformal risk control (concept)](../concepts/conformal-risk-control.md), [per-session risk control](per-session-risk-control.md), [M2-16 online re-calibration](m2-16-online-recal-result.md)
