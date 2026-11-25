---
title: Beyond words - affect, memory state and images from body signals
type: question
tags: [affect, emotion, memory, image-decoding, eeg, ieeg, fmri, meg, datasets, licence, null-controls, trust-layer, p16]
sources: []
updated: 2026-11-24
---

# Beyond words: what can a body signal tell besides words?

**Question (user, 2026-11-23):** can Fidetype read more than words from brain and body signals: emotion (affect), memory state, images? What is real, what is hype, and where does a calibrated trust gate add something new? Roadmap: [P16-06](roadmap-standard.md#p16-06-beyond-words-affect-and-memory-state-decoding-with-signal-checks) (affect and memory state) and [P16-07](roadmap-standard.md#p16-07-image-reconstruction-decoding-with-signal-checks) (images).

**Method.** An earlier research agent wrote a draft note (2026-11-23, not committed). This page keeps only claims that we checked on 2026-11-24 against the primary page (paper full text or abstract, dataset API, licence page). Where the draft was wrong, the page gives the checked value; the list is in [Checks of the draft note](#checks-of-the-draft-note). No paper on this page has its own source page yet. The links go to the primary pages. The licences of the papers are in [`references/README.md`](../../references/README.md).

## Short answer
| Area | What works today (published) | What does not work | Licence-clean public data | Our experiment |
|---|---|---|---|---|
| **Images** (seen, not imagined) | 7T fMRI: 300-way image / brain retrieval 98.3 % / 98.8 % with 40 h of one person's data; EEG: 200-way zero-shot top-1 about 14-29 % | Mental imagery is much worse; reconstructions that "look right" carry little brain information | THINGS-EEG2 (CC BY 4.0), THINGS-MEG / THINGS-fMRI (CC0) | **A1** (ready, queued on GPU) |
| **Memory state** ("this word will likely be recalled") | iEEG mean AUC 0.61; scalp EEG mean AUC 0.59-0.60 | Reading memory **content** | Penn RAM FR1 iEEG and PEERS scalp EEG (both CC0) | **B1** (pre-registered, CPU) |
| **Affect** (emotion) | Cross-subject EEG binary valence about 69 % on seen film clips | Much of the cross-subject accuracy recognises the **video**, not the emotion | No EEG emotion set with a verified open licence; Emo-FilM fMRI (CC0) | candidate only (below) |

> **Our take:** the strongest common thread is not a better decoder. All three areas have weak, confounded signals and strong priors (a diffusion model, a video identity, a serial-position effect). The thing that is missing in the literature is a **per-decision, calibrated claim**: "this output is supported by the signal, and such claims are wrong at most a stated share of the time", plus proof that the claim does not appear on null input. That is the Fidetype trust layer ([Learn then Test](../concepts/learn-then-test.md), [conformal risk control](../concepts/conformal-risk-control.md), [trust decision](../concepts/trust-decision.md)).

## Affect (emotion)

### What the sources say
| Work | Signal and setting | Number (as the source gives it) | Checked on |
|---|---|---|---|
| FACED, Chen et al., *Sci Data* 10:740 (2023), [PMC10600242](https://pmc.ncbi.nlm.nih.gov/articles/PMC10600242/) | 32-channel EEG, 123 subjects, 28 film clips, 9 emotion categories | cross-subject binary (DE + SVM) **69.3 ± 1.5 %**, intra-subject 78.8 ± 1.0 %; 9-class cross-subject 35.2 ± 1.0 % (CLISA 42.4 ± 1.2 %), intra-subject 51.1 ± 0.9 % | full text |
| Xu & Plataniotis, "How Much of Cross-Subject EEG Emotion Recognition Is Stimulus Memorization?", [arXiv:2610.28422](https://arxiv.org/abs/2610.28422) (20 Oct 2026) | released FACED / SEED classifiers, re-tested on unseen videos | stimulus identity "linearly recoverable at six to fifteen times chance" (FACED-2 probe 26.97-58.54 % vs chance 4.17 %); "each released classifier loses two to forty-four points once the test videos are unseen" (FACED-2: CLISA +17.90, MSHCL +5.35, DAEST +26.12, Table 1); MSHCL on SEED-3 "reaches 48.19% against a published 89.3" (footnote) | abstract + HTML |
| Khan et al., "The Role of Review Process Failures in Affective State Estimation: An Empirical Investigation of DEAP Dataset", [arXiv:2508.02417](https://arxiv.org/abs/2508.02417) (2025) | DEAP literature review and re-analysis | flaws, among them "data leakage from improper segmentation", "can inflate the classification accuracy by up to 46%" | abstract |
| Sani et al., *Nat Biotechnol* (2018), doi:10.1038/nbt.4200 | intracranial, 7 epilepsy patients, mood self-reports over days | "an initial line of evidence indicating the feasibility of mood state decoding"; decoders "largely recruited neural signals from limbic regions" | Europe PMC abstract |
| Scangos et al., *Nat Med* (2021), doi:10.1038/s41591-021-01480-w, [PMC11219029](https://pmc.ncbi.nlm.nih.gov/articles/PMC11219029/) | one person with treatment-resistant depression, personalised biomarker, closed-loop deep brain stimulation | "rapid and sustained improvement in depression"; "n-of-1 study" | Europe PMC abstract only |

> **Our take:** most published cross-subject emotion accuracies above 90 % are on seen stimuli. Under a held-out video and held-out subject split, the honest number is much lower; the size of the drop depends on the model (2 to 44 points). For a trust gate, this is the ideal case: a weak, confounded signal, where abstention and null controls matter more than architecture. The held-out **video** split is the area-specific null control.

> **Contradiction:** SEED-3 MSHCL: published 89.3 % vs 48.19 % in the re-test by Xu & Plataniotis. We keep both numbers; we did not re-run either.

### Affect datasets and licences (checked 2026-11-24)
| Dataset | Licence / terms | Signature or request? | Size | Fit |
|---|---|---|---|---|
| **FACED** (Synapse `syn50614194`) | paper: "open-access for research purposes"; the paper itself is CC BY 4.0, but **no data licence** was found (the Synapse API entity has no licence or terms field) | Synapse account; terms unknown | not shown | best EEG candidate **once the data licence is confirmed** |
| **SEED** family (SJTU BCMI) | licence PDF: "only ... for academic research"; no commercial use, incl. "training or proving the efficiency of commercial systems"; no distribution | **yes**: a signed PDF; "the director of the institution or principal investigators ... should be given instead of a student" | — | not usable by the user alone |
| **DEAP** (QMUL) | EULA page not reachable on 2026-11-24 (TLS error) | signed EULA (per the draft note; **not verified**) | — | not usable until checked |
| **DREAMER** (Zenodo 546113) | no licence field on the record | **yes**: access request (name, institution, position, reason); files "restricted" | the record shows "3.8 TB" (looks wrong for 23 people; not checked) | not usable now |
| **WESAD** (UCI 465) | UCI: "See linked dataset for licensing information"; the Siegen page now redirects to a general page | no | not shown | licence **not verified**; body signals, not brain |
| **Emo-FilM** (OpenNeuro `ds004892`, v1.0.2) | **CC0** (`dataset_description.json`) | no | **141.4 GB** (141,395,545,706 bytes), 30 participants; OpenNeuro modalities `mri`, `beh` (no EEG in this snapshot) | **best licence-clean affect candidate** (fMRI) |

**Best affect experiment candidate (task 3; no plan yet):** **C1-fMRI on Emo-FilM** (Morgenroth et al., *Sci Data* 12:684 (2025), doi:10.1038/s41597-025-04803-5; OpenNeuro [ds004892](https://openneuro.org/datasets/ds004892), CC0, 141.4 GB, 30 participants, 14 films + rest). Task: a gated read of the film-time emotion annotations from fMRI, with held-out **film** and held-out participant splits (the stimulus-memorisation control of Xu & Plataniotis). We have not yet read the annotation format or the paper full text. The EEG option stays **FACED**, after its data licence is confirmed.

## Memory state

### What the sources say
| Work | Signal and setting | Number (as the source gives it) | Checked on |
|---|---|---|---|
| Ezzyat et al., "Closed-loop stimulation of temporal cortex rescues functional networks and improves memory", *Nat Commun* 9:365 (2018), doi:10.1038/s41467-017-02753-0 (CC BY 4.0) | iEEG, **25** epilepsy patients, delayed free recall; L2 logistic regression on log power, 8 frequencies 3-180 Hz, 0-1366 ms after word onset, C = 2.4 x 10^-4 | classifier from record-only sessions, tested on NoStim lists of new closed-loop sessions: **mean AUC = 0.61**, t(28) = 7.5, P < 10^-7 (N = 29 stimulation targets); lateral temporal stimulation when P(recall) < 0.5: relative recall probability **+15 %** (t(3828) = 2.31, P = 0.02) | full text |
| Li, Pazdera & Kahana, "EEG decoders track memory dynamics", *Nat Commun* (2024), doi:10.1038/s41467-024-46926-0 (CC BY 4.0) | scalp EEG, 98 participants, 24 sessions each (88 analysed), leave-one-session-out | encoding **mean AUC 0.59** (event re-sampling) / **0.60** (all events); retrieval (correct recall vs intrusion) 0.57 / 0.59; null = "classifiers trained with randomly-shuffled training labels" within session; data: OpenNeuro ds004395 (PEERS4) | full text |
| Hampson et al., "Developing a hippocampal neural prosthetic to facilitate human memory encoding and recall", *J Neural Eng* (2018), doi:10.1088/1741-2552/aaaed7, [PMC6576290](https://pmc.ncbi.nlm.nih.gov/articles/PMC6576290/) | hippocampal CA1 stimulation from a MIMO model, delayed match-to-sample | short-term / working memory **+37 %**; short- and long-term retention **+35 %** | Europe PMC abstract |

> **Our take:** these classifiers detect a **state** ("this word will likely be recalled"), never memory **content**. At AUC about 0.6, a calibrated gate will mostly abstain. A measured "the gate speaks on k % of words with precision p" is still new: the papers report AUC, not a per-decision error bound. The Kahana-lab label-permutation null is the same idea as our signal checks; it carries over directly.

### Memory datasets and licences (OpenNeuro API, 2026-11-24)
All four are **CC0** in `dataset_description.json`; no signature. Details: [Penn RAM and PEERS datasets](../entities/penn-ram-memory-datasets.md).

| Dataset | Content | Size (latest snapshot) |
|---|---|---|
| [ds004789](https://openneuro.org/datasets/ds004789) v3.1.0 | RAM FR1 iEEG, 280 subjects, delayed free recall | 618.8 GB (B1 subset: 56.79 GB) |
| [ds004809](https://openneuro.org/datasets/ds004809) v2.2.0 | RAM catFR1 iEEG, 258 subjects, categorised free recall | 512.4 GB |
| [ds005557](https://openneuro.org/datasets/ds005557) v1.0.0 | RAM FR3 iEEG, 18 subjects, closed-loop stimulation at encoding | 37.2 GB |
| [ds004395](https://openneuro.org/datasets/ds004395) v2.0.0 | PEERS scalp EEG, 364 subjects | 9,583.3 GB |

### B1: pre-registered
[B1 plan](../../experiments/2026-11-24-b1-memory-state-gate/plan.md) (committed before any iEEG data was downloaded): 30 hash-ranked FR1 subjects with at least 3 bipolar sessions; frozen per-subject decoder with the Ezzyat features; a precision LTT gate on the next session ("good encoding moment" with precision at least base rate + 0.10); null controls; CPU only, about 1-3 h; download 56.79 GB.

**Which null controls carry over (a finding of the B1 design).** The Ezzyat features are log power **averaged over time**. Time reversal and per-epoch phase randomisation keep a channel's power spectrum, so they keep these features. For this feature set they are **invariance checks, not safety nulls**. The safety nulls are: label permutation end to end, noise shaped to the session-mean spectrum, and shuffled signal across words.

## Images

### What the sources say
| Work | Signal / data | Number (as the source gives it) | Checked on |
|---|---|---|---|
| MindEye2, Scotti et al., ICML 2024, [arXiv:2403.11207](https://arxiv.org/abs/2403.11207) (v3), code MIT | 7T fMRI, NSD, 300-way retrieval (chance 0.3 %) | 1 h of data: image retrieval **57.4 %**, brain retrieval **79.0 %**, CLIP 2-way 79.2 %, PixCorr 0.195; 40 h: image **98.3 %**, brain **98.8 %**, CLIP 93.0 %, PixCorr 0.322 (Table 1, v3) | HTML v3 |
| Benchetrit, Banville & King, ICLR 2024, [arXiv:2310.19812](https://arxiv.org/abs/2310.19812) | MEG, 4 participants, THINGS-MEG | top-5 retrieval **70.33 ± 2.80 %** (VGG-19; chance 2.5 %); large set "around ... 13%" (chance 0.21 %); "a 7X improvement of image-retrieval over classic linear decoders"; NSD vs MEG CLIP 0.917 vs 0.811, PixCorr 0.305 vs 0.090 (MEG averaged across trials and subjects) | HTML v3 |
| NICE, Song et al., ICLR 2024, [arXiv:2308.13234](https://arxiv.org/abs/2308.13234), code MIT | EEG, THINGS-EEG2, 200-way zero-shot (chance 0.5 %) | NICE 13.8 % top-1 / 39.5 % top-5; NICE-GA 15.6 % / 42.8 % (abstract); subject-independent 6.2 % / 21.4 % | HTML v3 |
| ATM, Li et al., [arXiv:2403.07721](https://arxiv.org/abs/2403.07721) (v7), code MIT | EEG / MEG, THINGS | ATM-S within-subject top-1 **28.64 ± 6.39 %**, top-5 58.47 % (Table 8); leave-one-subject-out 11.84 % / 33.73 %; THINGS-MEG 5.88 % / 19.25 % (Table 6) | HTML v7 (tables via extraction) |
| CrossPT-EEG, Zhu et al., [arXiv:2406.07151](https://arxiv.org/abs/2406.07151) (v2) | EEG, 16 participants, 4,000 ImageNet images | coarse 40-class and fine 8-class classification (best averages 0.566-0.938 by setting, Tables 2-3); **no reconstruction experiment**; data "will be publicly released after the review stage" | HTML v2 |
| NSD-Imagery, Kneeland et al., CVPR 2025, [arXiv:2506.06898](https://arxiv.org/abs/2506.06898) | 7T fMRI during mental imagery | "All the methods do show a drop ... when reconstructing mental images" (MindEye2 human 2AFC 56.96 % imagery vs 83.05 % vision, Table 2); "simple linear decoding architectures ... generalize better to mental imagery" | HTML v1 |

### How much comes from the brain, how much from the generator prior?
| Work | What it measures | Finding |
|---|---|---|
| BrainBits, Mayo et al., NeurIPS 2024, [arXiv:2411.02783](https://arxiv.org/abs/2411.02783) | fMRI compressed through a learned bottleneck | "it takes surprisingly little information from the brain to produce reconstructions with high fidelity"; Brain-Diffuser with a 50-dim bottleneck "achieves 75%, 95%, 100%, and 89% of the original performance" (DreamSim, CLIP, SSIM, PixCorr); effective dimension "about 16" |
| Shirakawa et al. (Kamitani lab), [arXiv:2405.10078](https://arxiv.org/abs/2405.10078) (v5, 14 May 2025) | data with no category overlap between train and test | NSD has about 40 semantic clusters "with considerable overlap between the training and test sets"; quality "substantially degrades" without overlap; realism "stems from a combination of classification into trained categories and inauthentic image generation (hallucination)" |
| Kikuchi, "Brain Control" (BC), [github.com/yukik8/brain-control](https://github.com/yukik8/brain-control) (MIT; paper PDF in the repo, "arXiv: coming soon") | how consistently a decoder turns repeated presentations of one stimulus into the same output | final images of MindEye2, MindEye1, Brain-Diffuser: BC 1.25-1.87, "shuffled controls ≈ 1"; "a category-only version of each decoder still reaches BC up to 1.30". BC does not measure correctness |

> **Contradiction:** MindEye2 retrieval columns. Our draft note and older copies of the paper have image 79.0 / brain 57.4 at 1 h. The v3 table and the repo README ("Retrieval metric correction": the labels "should be exchanged") give image 57.4 / brain 79.0. We use v3.

> **Contradiction:** Shirakawa et al. v5 says text-guided methods "failed to achieve the same level of performance" and quality "substantially degrades"; it also says Brain-Diffuser "remained more robust" (from an extracted section). "Fail" overstates it. We keep "degrades".

> **Our take (the gap):** BrainBits, Shirakawa et al. and Kikuchi BC **measure** prior dominance on average. In what we read, no work gives a **per-image calibrated decision** ("this output is supported by the brain signal, with P(wrong claim) <= alpha") plus a test that shuffled, noise or time-reversed input gives at most alpha claims. That is the Fidetype COMMIT / OFFER / ABSTAIN pattern moved from text to images. The novelty wording must stay narrow: "the prior hallucinates" is prior art.

### A1: pre-registered and ready
[A1 plan](../../experiments/2026-11-24-a1-things-eeg2-image-gate/plan.md): trust-gated zero-shot image identification on THINGS-EEG2 (subjects 1 and 2), own ATM-S re-implementation, calibration on held-out training concepts, test on the 200 new concepts; nulls trial-shuffled, time-reversed, spectrum-matched noise. Data: [THINGS-EEG2](../entities/things-eeg2-dataset.md). Queued on the local GPU.

### Image data and licences
| Dataset | Licence / terms | Size | Note |
|---|---|---|---|
| [THINGS-EEG2](../entities/things-eeg2-dataset.md) (OSF 3jk45) | CC BY 4.0 | A1 uses 23.6 GB | THINGS images: research use only, never committed |
| THINGS-MEG (OpenNeuro ds004212) | CC0 (draft note; **not re-checked** on 2026-11-24) | 255.2 GB (draft note) | Meta's decoder code is likely CC BY-NC; write our own |
| THINGS-fMRI (OpenNeuro ds004192) | CC0 (draft note; **not re-checked**) | 105.8 GB (draft note) | — |
| NSD (AWS registry) | "Terms & Conditions for the NSD dataset" + NSD Data Access Agreement form | not shown | click-through; research and education only, no redistribution (draft note; the terms page itself was not re-read) |

## Where a calibrated trust gate adds something new
| Trust-layer part | Images | Memory state | Affect |
|---|---|---|---|
| COMMIT with a precision bound ([precision LTT](../concepts/learn-then-test.md)) | "this is image k" | "good encoding moment" | "valence positive" |
| OFFER (conformal set) | short image list | rarely useful (2 classes) | 2-9 classes |
| ABSTAIN by default | yes | yes (most words) | yes (most trials) |
| shuffled-signal null | yes | yes (words) | yes |
| time-reversed / phase-randomised | **safety null** (time-locked features) | **invariance check only** (time-averaged power) | depends on features (DE is power-based: invariance check) |
| label permutation end to end | — | yes (Kahana-lab practice) | yes |
| area-specific confound split | held-out concept cluster | held-out session; behaviour-only baseline (serial position) | held-out **video** and subject |

> **Our take:** the important design lesson from B1 is that a null control is only a null for the features that it destroys. Every plan must say, before the run, which nulls are safety nulls for its feature set.

## Ranked experiments (2026-11-24)
| Rank | ID | Area | Data (licence) | State |
|---|---|---|---|---|
| 1 | A1 | EEG image identity gate | THINGS-EEG2 (CC BY 4.0) | pre-registered, code done, queued on GPU |
| 2 | B1 | iEEG encoding-state gate | Penn RAM FR1 (CC0) | pre-registered (this task), CPU |
| 3 | A2 | MindEye2 "brain or prior" audit + per-image gate | NSD (click-through terms) | idea; needs the user to accept the NSD terms |
| 4 | C1-fMRI | affect gate with held-out films | Emo-FilM (CC0) | candidate; annotation format not read |
| 5 | B2 | offline audit of real closed-loop stimulation decisions | RAM FR3 ds005557 (CC0, 37.2 GB) | idea; links to P16-04 |
| 6 | C1-EEG | affect gate with held-out videos | FACED (data licence unknown) | blocked on licence |

## What is not possible (state it in public)
- **Reading memory content.** Memory classifiers detect a state, at AUC about 0.6.
- **Reading private thoughts.** Image decoders work on images that a person **sees**, trained on many hours of that person's data, mostly within trained categories. Mental imagery is clearly worse (NSD-Imagery).
- **Reading emotion in daily life.** Lab labels are self-reports of film-clip feelings. Cross-subject results on unseen videos drop sharply.
- **Decoding without cooperation.** All decoders here need the person's own training data and cooperation.
- **"Looks right" is not proof.** Diffusion priors produce plausible images from little brain information (BrainBits, Shirakawa et al.).
- **Stimulation.** Out of scope without partners, ethics approval and hardware ([P16-05](roadmap-standard.md#p16-05-real-stimulation-work), externally blocked). Ezzyat, Hampson and Scangos are small clinical studies in implanted patients.

## Ethics and privacy
- Affect and memory-state outputs are sensitive inferences. See the [neural-data law table](neural-data-law.md): EU AI Act Art. 5(1)(f) bans emotion inference at work and in education (except medical or safety reasons); several US states treat neural data as sensitive.
- Inference must be opt-in, per purpose, and revocable. No covert inference. No use in hiring, insurance, policing, advertising or interrogation.
- The trust layer helps privacy: ABSTAIN by default, no output on null input, a ledger of each claim, no raw signals in logs.
- Publish null-input and prior-attribution numbers next to every demo image.
- Respect dataset terms (no redistribution: NSD, SEED). Aggregate results only in the public repo.
- No medical claims. Mood and memory results are research, not diagnosis or therapy.

## What the user must decide or do
1. **NSD** (for A2): read and accept the NSD terms and fill the access form. Research and education only.
2. **FACED**: confirm the data licence on Synapse (needs an account). Until then, C1-EEG is blocked.
3. **SEED / DEAP**: only with an academic partner who can sign. Otherwise skip them.
4. **B1 download**: 56.79 GB to local disk (267 GB free on C: on 2026-11-24). CPU only.

## Checks of the draft note
Values in the draft note (2026-11-23) that the primary pages do **not** support:
| Draft claim | Checked value |
|---|---|
| MindEye2 1 h: image retrieval 79.0 %, brain 57.4 %; 40 h: 98.8 % / 98.3 % | swapped: image 57.4 % / brain 79.0 %; 40 h image 98.3 % / brain 98.8 % (v3 Table 1) |
| EEG-ImageNet (Zhu et al.): classification "~60 %", reconstruction 2-way "~64 %"; HF dataset CC BY 4.0 | the paper is now "CrossPT-EEG"; no reconstruction experiment; no single "~60 %" figure; the data licence is not stated in the paper ("will be publicly released after the review stage") |
| arXiv:2508.02417: leakage inflates DEAP accuracy "by over 20 percentage points" | abstract: flaws "can inflate the classification accuracy by up to 46%" (the 20-point phrase was not found) |
| Sensors doi:10.3390/s26175327: identity 0.998, emotion about 0.55 | not verifiable (publisher page refused access); not used |
| Scangos 2021: "accuracy: mean = 0.77, s.d. = 0.09", MADRS baseline 36/54, 11/13 trials | not verifiable from the abstract (full text not available to us); not used |
| NICE: 15.6 % / 42.8 % as "NICE" | these are NICE-GA (abstract); base NICE is 13.8 % / 39.5 % |
| Benchetrit large set 12.29 % | the text says "around ... 13%"; 12.29 is in an appendix table (extraction only) |
| Shirakawa: text-guided reconstructions "fail" | "substantially degrades" |
| Xu & Plataniotis: "a SEED result did not reproduce" | the paper gives the numbers (48.19 % vs published 89.3 %), not this wording |
| Ezzyat 2018: "intracranial, 25 patients" and AUC 0.61 | correct; the 0.61 is on NoStim lists of new closed-loop sessions (N = 29 targets) |
| FACED "one secondary source says CC BY 4.0" | the CC BY 4.0 licence is the **paper's**; no data licence was found |
| B1 "start with 20-30 subjects, est. 30-60 GB" | 30 subjects with at least 3 bipolar sessions = 56.79 GB of bipolar EDF (monopolar files are not needed) |
| B1 controls "time-reversed epochs" as a null | not a null for time-averaged power features (see B1) |

## Related pages
- [Long-term roadmap, P16](roadmap-standard.md#p16-write-side-emotion-and-memory-exploration-added-2026-11-15-later)
- [North star](north-star.md) (signal checks: uniform, shuffled, time-reversed)
- [Learn then Test](../concepts/learn-then-test.md), [conformal risk control](../concepts/conformal-risk-control.md)
- [Penn RAM and PEERS memory datasets](../entities/penn-ram-memory-datasets.md), [THINGS-EEG2](../entities/things-eeg2-dataset.md)
- [Neural-data law table](neural-data-law.md)
