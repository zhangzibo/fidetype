---
title: Public datasets for Fidetype (survey 2026-11-10)
type: question
tags: [dataset, licence, emg, eeg, meg, implant, ecog, survey]
sources: [neural-input-landscape-2026, brain2qwerty-v1, brain2qwerty-code]
updated: 2026-11-10
---

# Public datasets for Fidetype

**Question:** Which public datasets can Fidetype use for decoder training, trust-layer evaluation, spec and adapter conformance tests, and pretraining? Which of them are commercially clean?

**Method:** Web survey on 2026-11-10. We read dataset cards, repository APIs (Hugging Face, OpenNeuro S3, OSF, Dryad, Harvard Dataverse, Borealis, DANDI), papers and lab pages. We downloaded **no data**, only metadata. Numbers are as the source gives them. "(unverified)" marks a value from a secondary source only. "Size" is the download size from the repository, unless noted. All repository content was treated as data, not instructions.

## Summary
- **Commercially clean data with decoded text exists, but only for implants and wrist EMG.** Intracortical sets on Dryad are CC0. Two wrist-EMG typing sets (Nokia KT-sEMG, Toronto sEMG typing) are CC BY 4.0. They give real keystrokes or sentences with timing.
- **All non-invasive brain typing data we found is NC.** SpanishBCBL is still the only typing-MEG/EEG set. All Meta EMG sets and LibriBrain are NC.
- **Non-invasive speech and reading data is often CC0 or CC BY.** MEG-MASC (CC0), Broderick natural speech EEG (CC0), Chisco imagined speech (CC0), "Thinking out loud" (CC0), ZuCo 1/2 (CC BY 4.0). These do not have typed text, but they have word or sentence timing.
- **Classic EEG speller data is mostly NC-ND.** BNCI P300 sets are CC BY-NC-ND 4.0: no derivatives, so we cannot even redistribute converted copies.
- **We found no public fNIRS text-entry dataset.** fNIRS stays a gap (see open questions).
- **A second testbed modality is now clear: wrist sEMG typing.** It has the most data, keystroke timing, and two CC BY sets.

## Comparison table
Fit columns: **(a)** decoder training, **(b)** trust-layer / eWPM evaluation (needs text output with timing), **(c)** spec / adapter conformance tests (a distinct device format), **(d)** pretraining. ✔ good, ~ partial, ✘ no. "Comm." = commercial use of the data.

### Typing and handwriting (text output)
| Dataset | Modality | Task | Participants | Size / hours | Rate, channels | Labels | Access | Licence (Comm.) | a | b | c | d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [SpanishBCBL](../entities/spanishbcbl-dataset.md) | MEG + EEG | typing | 19 usable MEG, 20 EEG | 280.4 GB on HF (API); MEG 21.5 h, EEG 17.7 h | MEG 1000 Hz, 306 ch; EEG 1 kHz, 64 ch | keystrokes + times, sentences | open (HF, not gated) | CC BY-NC 4.0 (no) | ✔ | ✔ | ✔ | ~ |
| [emg2qwerty](../entities/emg2qwerty.md) | wrist sEMG (2 bands) | typing | 108 | 308.4 GB tar.gz (HTTP header); 346 h, 1,135 sessions | 2 kHz, 2 × 16 ch | prompts, keylogger keys + timestamps | open (S3) | CC BY-NC 4.0 (no) | ✔ | ✔ | ✔ | ✔ |
| [KT-sEMG (Nokia)](../entities/kt-semg-dataset.md) | forearm sEMG | free typing | 1 typist | 21.0 GB (88 files, API); >148,000 keystrokes | 2000 Hz, 2 × 16 ch | keystrokes, ms timestamps | open (Harvard Dataverse) | CC BY 4.0 (yes, attribution) | ✔ | ~ | ✔ | ~ |
| [Toronto sEMG typing](../entities/toronto-semg-typing-dataset.md) | forearm sEMG | typing (letters + space) | 19 | 2.77 GB (1 zip, API); 2 sessions each | 2 kHz, 16 ch | keylogger letters + timestamps | open (Borealis) | CC BY 4.0 (yes, attribution) | ✔ | ~ | ✔ | ~ |
| generic-neuromotor-interface (Meta) | wrist sEMG | handwriting, gestures, wrist | 100 per task | handwriting 98.8 / 31.5 / 10.4 h (train/val/test) | 2 kHz | prompt start/end times; text labels unclear | open (script) | CC BY-NC 4.0 (no) | ✔ | ~ | ✔ | ✔ |
| emg2pose (Meta) | wrist sEMG | hand pose | 193 | 462.8 GB tar (HTTP header); 370 h | 2 kHz | joint angles | open (S3) | CC BY-NC-SA 4.0 (no) | ✘ | ✘ | ✔ | ✔ |
| [Willett 2021 handwriting](../entities/willett-handwriting-2021.md) | intracortical (2 × 96 Utah) | attempted handwriting | 1 (T5) | 1.41 GB; 10.7 h, 1,000 sentences, 43,501 characters | binned spikes | sentences, characters, real-time outputs | open (Dryad) | CC0 (yes) | ✔ | ✔ | ✔ | ~ |
| FALCON H2 | intracortical | handwriting (benchmark copy) | — | 1.22 GB (DANDI 000950) | binned | characters | open (DANDI) | CC BY 4.0 (yes) | ✔ | ~ | ✔ | ✘ |

### Speech (attempted, perceived, imagined) and reading
| Dataset | Modality | Task | Participants | Size / hours | Rate, channels | Labels | Access | Licence (Comm.) | a | b | c | d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [Brain-to-Text '25 (Card et al.)](../entities/brain-to-text-25.md) | intracortical (256 ch) | attempted speech | 1 (T15, ALS) | 11.59 GB; 11,000+ copy-task trials, 45 sessions | 20 ms bins, 512 features | cue sentences, phoneme/word outputs, RNN logits (test labels withheld) | open (Dryad) | CC0 (yes) | ✔ | ✔ | ✔ | ~ |
| Brain-to-Text '24 (Willett 2023) | intracortical | attempted speech | 1 (T12) | 80.44 GB incl. LMs (competitionData 3.67 GB); 12,100 sentences | 20 ms bins | sentences, BCI output | open (Dryad) | CC0 (yes) | ✔ | ✔ | ✔ | ~ |
| Inner speech (Kunz et al.) | intracortical | inner + attempted speech | — | not checked | — | — | open (Dryad doi:10.5061/dryad.gf1vhhn1j) | CC0 (yes) | ~ | ~ | ✘ | ✘ |
| LibriBrain | MEG (306 ch) | speech listening | 1 | ≥ 347.9 GB on HF (API, tree may be partial); > 50 h | not checked | word, phoneme, sentence timing columns | open (HF, not gated) | CC BY-NC 4.0 (no) | ✔ | ✘ | ~ | ✔ |
| MEG-MASC | MEG | speech listening | 27 | about 2 h each | BIDS | word + phoneme timestamps | open (OSF ag3kj + part 2) | CC0 (part 1, OSF API); part 2 not checked | ✔ | ✘ | ~ | ✔ |
| Armeni 2022 | MEG | speech listening | 3 | about 10 h each, 30–34 h | — | word timing | DUA (Radboud) | DUA, not open | ✔ | ✘ | ✘ | ✔ |
| MOUS (Schoffelen 2019) | MEG + fMRI | Dutch reading/listening | 204 | — | — | word events | DUA (Donders RU-DI-HD, unverified) | DUA | ~ | ✘ | ✘ | ✔ |
| Broderick natural speech | EEG 128 ch | speech listening | 19 (unverified) | 14.84 GB (Dryad) | 512 Hz | stimulus text + timing | open (Dryad; also OpenNeuro ds004408) | CC0 (yes) | ~ | ✘ | ~ | ✔ |
| Chisco | EEG (high density) | imagined speech (Chinese) | 5 (3 in paper + 2 added) | > 900 min per subject; > 20,000 sentences | not checked | sentence text per trial | open (OpenNeuro ds005170) | CC0 (yes) | ✔ | ~ | ~ | ✔ |
| "Thinking out loud" | EEG 136 ch | inner speech (4 words, Spanish) | 10 | > 9 h, > 5,600 trials | — | word class | open (OpenNeuro ds003626) | CC0 (yes) | ~ | ✘ | ~ | ~ |
| ZuCo 1.0 / 2.0 | EEG 128 ch + eye tracking | natural reading | ZuCo 2.0: 18 | ZuCo 2.0: 739 sentences | — | word-level fixations | open (OSF q3zws, 2urht) | CC BY 4.0 (yes) | ~ | ✘ | ✔ | ✔ |
| Du-IN sEEG | sEEG | word reading (Chinese, 61 words) | 12 | — | — | word class | open (HF liulab-repository/Du-IN) | CC BY 4.0 (unverified) | ~ | ✘ | ~ | ~ |
| Verwoert 2022 | sEEG | word production (Dutch) | 10 | 1103 electrodes total | — | words + audio | open (OSF nrgx6) | CC BY 4.0 (yes) | ~ | ✘ | ~ | ~ |
| Brain Treebank | sEEG | speech listening (films) | 10 | 43.5 h, 38,572 sentences | — | sentence/word timing | open | CC BY 4.0 (yes) | ~ | ✘ | ~ | ✔ |
| Chang lab CV syllables | ECoG 256 ch | syllable production | 4 (DANDI) | 55.6 GB (DANDI 000019) | — | syllable events, no audio | open (DANDI) | CC BY 4.0 (yes) | ~ | ✘ | ✔ | ~ |

### Classic EEG spellers (MOABB)
| Dataset | Task | Participants | Licence (Comm.) | Fit |
|---|---|---|---|---|
| BNCI 2014-008 (ALS), 2014-009, 2015-003, 2015-012 | P300 spellers | 8–10 each | CC BY-NC-ND 4.0 (no; no derivatives) | (c) only, and only by reference |
| BigP3BCI (studies A–F, via MOABB/NEMAR) | P300 speller | 8–10 per study | CC BY 4.0 (from NEMAR page) | (a), (b) for letter selection, (c) |
| Tsinghua SSVEP benchmark (Wang 2016), BETA (Liu 2020) | 40-target SSVEP speller | 35 / 70 | terms not stated ("freely available") | (a), (c) — licence unclear |

### Pretraining corpora
| Corpus | Modality | Size | Access | Licence (Comm.) |
|---|---|---|---|---|
| TUH EEG Corpus (TUEG v2.0.2) | clinical EEG | 26,846 recordings (NEDC page); 27,062 h (secondary) | signed PDF form, then rsync | not stated (unclear) |
| HBN EEG | EEG | — | — | not verified |
| Cam-CAN | MEG | — | online DUA | DUA; no redistribution |
| emg2pose + generic-neuromotor-interface + emg2qwerty | sEMG | > 1,000 h combined | open | NC (no) |
| LibriBrain + MEG-MASC | MEG | > 100 h | open | NC / CC0 |

Model-scale context (secondary sources): LaBraM used about 2,500 h from about 20 datasets. CBraMod used a cleaned subset of TUEG, about 9,000 h. REVE reports about 60,000 h from 92 datasets.

## Ranked shortlist (top 5)
| # | Dataset | Modality | Size | Licence | Why |
|---|---|---|---|---|---|
| 1 | [Brain-to-Text '25](../entities/brain-to-text-25.md) | intracortical speech | 11.59 GB (or 58 MB for the logits file alone) | CC0 | Real decoded text with RNN logits per trial and cue sentences. A pretrained RNN is included. Best licence-clean data for trust-layer (b) evaluation. |
| 2 | [KT-sEMG (Nokia)](../entities/kt-semg-dataset.md) | forearm sEMG | 21.0 GB | CC BY 4.0 | Commercially usable EMG typing with ms keystroke timestamps. Plain CSV format: a good second adapter. One typist only. |
| 3 | [emg2qwerty](../entities/emg2qwerty.md) | wrist sEMG | 308.4 GB | CC BY-NC 4.0 | Largest typing dataset of any modality (108 users, 346 h). The research benchmark for causal EMG typing. NC: research only. |
| 4 | [Willett 2021 handwriting](../entities/willett-handwriting-2021.md) | intracortical handwriting | 1.41 GB | CC0 | Small and clean. Character output with real-time BCI outputs. A second decoder type for the spec (characters, not phonemes). |
| 5 | [Toronto sEMG typing](../entities/toronto-semg-typing-dataset.md) | forearm sEMG | 2.77 GB | CC BY 4.0 | 19 participants, 2 sessions each: the only commercially clean cross-subject EMG typing data. Small. |

> **Our take:** The ranking puts licence first and text-with-timing second, because Fidetype is a trust layer and a standard. Raw volume comes third. Brain-to-Text '25 and the two CC BY EMG sets make a commercially clean path possible for both invasive and wearable input. emg2qwerty and SpanishBCBL stay as research benchmarks.

> **Our take:** Wrist sEMG should become the **second testbed modality** after MEG. It has a consumer device ([Meta Neural Band](../entities/meta-neural-band.md)), the largest typing data, and the only non-invasive commercially clean typing data.

Close runners-up: MEG-MASC (CC0 MEG, pretraining), Chisco (CC0 imagined speech, sentence labels), ZuCo (CC BY reading EEG with eye tracking; a multimodal stream test), LibriBrain (largest single-subject MEG, NC).

> Intent and cursor-control datasets (P12-06, 2026-11-13) are in [intent and control datasets](intent-datasets-survey.md). That survey re-read the emg2qwerty licence: the `LICENSE` file is CC BY-NC-SA 4.0, the README says CC BY-NC 4.0.

## Licence warnings
1. **All Meta EMG data is NC.** emg2qwerty and generic-neuromotor-interface are CC BY-NC 4.0. emg2pose is CC BY-NC-SA 4.0 (share-alike too). LibriBrain and SpanishBCBL are CC BY-NC 4.0. Research only ([licence rule](project-plan.md#licence-rule)).
2. **BNCI P300 sets are CC BY-NC-ND 4.0.** "No derivatives" forbids sharing converted files. Use them only by download-and-convert on the user's machine.
3. **CC0 data, unlicensed code.** The Dryad data and the pretrained RNN are CC0. But `Neuroprosthetics-Lab/nejm-brain-to-text` and `fwillett/speechBCI` have **no licence** on GitHub (API: `null`), and `fwillett/handwritingBCI` is `NOASSERTION`. We must write our own loaders. Do not copy their code.
4. **CC BY needs attribution, and CC BY-SA spreads.** KT-sEMG and the Toronto set need attribution in the provenance ledger. The Toronto baseline code (`ANSLab-UHN/sEMG-TypingDatabase`) is CC BY-SA 4.0: do not copy it into Apache/MIT code.
5. **DUA data cannot be redistributed.** Armeni 2022, MOUS, Cam-CAN, TUEG. TUEG needs a signed form; its commercial terms are not stated.
6. **Licence not stated:** Tsinghua SSVEP benchmark and BETA. Treat as unusable for products until confirmed.

> **Contradiction:** The NeuroSketch paper (arXiv 2512.09524) lists Du-IN on OpenNeuro "ds005170". But OpenNeuro ds005170 is **Chisco** (its `dataset_description.json` says `"Name": "Chisco"`). The Du-IN licence (CC BY 4.0) is therefore unverified.

> **Resolved (2026-11-10):** `references/README.md` listed SpanishBCBL as "gated, ~262 GB". The HF API on 2026-11-10 reports `gated=False` and 280.4 GB for the whole repo. `references/README.md` now gives the API values. The older ~262 GB figure was probably a subset (for example, MEG only); we keep 280.4 GB as the whole-repo size.

## Recommended next actions
1. **First download: Brain-to-Text '25, in two steps.** Step 1 is done (2026-11-10): see [B2T '25 trust result](b2t25-trust-result.md).
   - Step 1: `t15_copyTask.pkl` (57.79 MB). It has, per evaluation trial, the cue sentence, the decoded phonemes and words, the duration and the RNN logits (1,718 trials). This is enough for a first trust-layer run on real CC0 decoder output, with no GPU.
   - Step 2: `t15_copyTask_neuralData.zip` (11.05 GB) + `t15_pretrained_rnn_baseline.zip` (484.94 MB), to get frame-level timing and to rerun the decoder. Disk: about 12 GB of 882 GB free on C:. Put it under `C:\Users\zhang\bci-data\`.
   - Code: `fidetype.adapters.b2t25` (own code) that reads the pickle and emits NeuralTextStream events (phoneme logits → CTC beam → word n-best with per-word times and confidences). Then run the M2 trust harness (calibration, conformal sets, policy, eWPM) on it.
2. **Second download: KT-sEMG (21.0 GB).** Code: `fidetype.adapters.kt_semg` (CSV at 2000 Hz + keystroke log with ms timestamps). Train a small causal ConvCTC on it (our M1-B code). Emit NeuralTextStream. This tests the spec on a second modality with a commercially clean licence.
3. Later: emg2qwerty adapter (HDF5) for the research benchmark. Use the 308 GB archive only when disk and time allow; check whether a per-user subset is available first.
4. Ask the Card / Stavisky lab for a code licence (see the [lead list](#university-labs-leads-only-no-outreach)) — only when outreach starts.

## University labs (leads only, no outreach)
| Lab | What they share | Why it matters |
|---|---|---|
| UC Davis Neuroprosthetics Lab (Stavisky, Brandman; Card et al.) | Brain-to-Text '25, CC0 | Commercially clean decoded text; challenge host |
| Stanford NPTL (Willett, Henderson, Shenoy legacy) | Handwriting 2021, speech 2023 / B2T '24, inner speech | CC0 data; benchmark culture |
| Nokia Bell Labs (Crouch et al.) | KT-sEMG, CC BY 4.0 | Industrial EMG typing; possible standards partner |
| Univ. of Toronto / KITE-UHN (Zariffa; Bar-Ilan, Fetaya) | sEMG typing, CC BY 4.0 | Cross-subject EMG typing |
| PNPL, Oxford (LibriBrain) | LibriBrain MEG, NC; Armeni loader | MEG speech benchmark and competition |
| NYU / Meta (Gwilliams, King) | MEG-MASC, CC0 | MEG speech with phoneme timing |
| Trinity College Dublin / Rochester (Lalor) | Natural speech EEG, CC0 | Speech EEG baselines |
| ETH / UZH (Hollenstein, Langer) | ZuCo 1/2, CC BY 4.0 | EEG + eye tracking: a multimodal stream case |
| Maastricht (Herff; Verwoert) | sEEG word production, CC BY 4.0 | Speech sEEG |
| UCSF Chang lab | CV syllables on DANDI, CC BY 4.0; sentence data not public | Leading ECoG speech lab |
| Temple NEDC (Picone, Obeid) | TUH EEG Corpus | Largest EEG pretraining corpus |

## Open questions
1. Does Brain-to-Text '25 `t15_copyTask.pkl` give per-frame logits with timing, or only per-trial? This decides whether step 1 can measure latency.
2. KT-sEMG: how many hours, and is the typing copied or free text? The paper says one "nonprofessional typist"; the README may say more.
3. emg2qwerty: is there a per-user download (the NEMAR/eegdash BIDS copy, NM000104, is said to be about 239 GB, unverified)?
4. Is there any public fNIRS text-entry or speech dataset with a clean licence? None found.
5. Licence of the Tsinghua SSVEP benchmark, HBN EEG and MEG-MASC part 2.
6. Do the Dryad CC0 datasets carry any patent or consent restriction that affects products? CC0 covers copyright only.

Related: [Neural input landscape](../sources/neural-input-landscape-2026.md) · [Dryad intracortical datasets](../entities/dryad-intracortical-datasets.md) · [Architecture: adapter priority](architecture.md#adapter-priority-2026-11-08) · [Project plan](project-plan.md)

> **Update 2026-11-11:** the Toronto sEMG set is downloaded and has an adapter (`fidetype.adapters.toronto_semg`). It holds isolated key presses only, no text. Result: [EMG Toronto trust result](emg-toronto-trust-result.md).
