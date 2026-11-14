---
title: Public datasets for intent and control (survey 2026-11-13)
type: question
tags: [dataset, licence, intent, control, cursor, emg, eeg, ecog, implant, survey, p12]
sources: [toronto-semg-typing]
updated: 2026-11-13
---

# Public datasets for intent and control (P12-06)

**Question:** Which public datasets can test "intent beyond text" (discrete choice, click / select, menu selection, gesture commands) and continuous pointer control? Which ones are licence-clean (CC0 / CC BY) and small enough (under 5 GB) for our work?

**Scope:** desk research only. We downloaded nothing. A subagent read each licence on the dataset hosting page or its official API on 2026-11-13 (Dryad API field `license`, DANDI `spdx:` licence, Zenodo / PhysioNet / figshare licence fields, GitHub `LICENSE`). The rows say where a value is inferred. This page adds to the [2026-11-10 dataset survey](public-datasets.md), which covers text decoding.

Related: [intent events](../concepts/intent-events.md) (FEP-0003, P12-01/02), [FEP-0003](../../spec/feps/0003-intent-events.md), roadmap [P12](roadmap-standard.md#p12-beyond-text-intent-and-control-added-2026-11-11).

## How we score the fit
FEP-0003 has two output profiles that need data:

| Profile | What the data must give | Extra value |
|---|---|---|
| **Intent** (P12-02) | Discrete labels per decision unit (class, key, target, gesture), enough units per user for calibration | A **rest / idle class** (the `null` intent), so we can test "no COMMIT on no-signal input" |
| **Control** (P12-03) | Continuous 2D cursor or effector position / velocity with time stamps; ideally closed-loop (the user saw the cursor) | Target positions (to score errors); click or hold events (both profiles at once) |

Fit score: **3** = direct fit (labels as the profile needs them), **2** = fit after a recast (for example reach direction as a discrete choice), **1** = weak fit (context only), **0** = no fit. Licence flags: **[NC]** non-commercial, **[ND]** no derivatives, **[SA]** share-alike, **[NO LICENCE]** no licence on the host page.

## Implant (intracortical)
| Dataset | Modality | Task | Participants | Size | Licence (verified) | Intent | Control |
|---|---|---|---|---|---|---|---|
| [BrainGate multi-gesture drag-and-drop](https://datadryad.org/dataset/doi:10.5061/dryad.98sf7m0v1) | Utah arrays | Held hand gestures (1/2/4 s) for click-and-hold and drag-and-drop, alone and with 2D cursor control | 2 humans | 8.2 GB | CC0 1.0 | 3 | 3 |
| [BrainGate long-term unsupervised recalibration](https://datadryad.org/dataset/doi:10.5061/dryad.1jwstqk6g) | Utah arrays | Closed-loop 2D cursor, sessions 2016-2020, online recalibration | 1 human (T5) | 1.69 GB | CC0 1.0 | 1 | 3 |
| [BrainGate preparatory encoding](https://datadryad.org/dataset/doi:10.5061/dryad.brv15dvr9) | Utah arrays | Open-loop delayed movements + closed-loop cursor | 3 humans (T5, T11, T16) | 1.54 GB | CC0 1.0 | 2 | 3 |
| [BrainGate MINDFUL (instability at home)](https://datadryad.org/dataset/doi:10.5061/dryad.n2z34tn5s) | Utah arrays | At-home cursor control, fixed decoders over 142 and 28 days | 2 humans | 0.41 GB | CC0 1.0 | 1 | 3 |
| [NoMAD latent alignment](https://datadryad.org/dataset/doi:10.5061/dryad.q83bk3jtp) | 192 ch binned spikes (NWB) | Cursor task with `cursor_pos`, `cursor_vel`, targets | 1 (page unclear: human T11 or monkey) | 0.25 GB | CC0 1.0 | 1 | 3 |
| [NLB MC_RTT](https://dandiarchive.org/dandiset/000129) | M1 spikes | Self-paced reaches to random targets on an 8x8 grid, not trial-segmented | 1 NHP | 51 MB | CC-BY-4.0 | 1 | 3 |
| [NLB MC_Maze](https://dandiarchive.org/dandiset/000128) ([Large](https://dandiarchive.org/dandiset/000138)) | M1 + PMd spikes | Delayed center-out reaches through a maze | 1 NHP | 694 MB (149 MB) | CC-BY-4.0 | 2 | 2 |
| [NLB Area2_Bump](https://dandiarchive.org/dandiset/000127) | Area 2 spikes | Center-out manipulandum cursor reaches with bumps | 1 NHP | 1.8 GB | CC-BY-4.0 | 1 | 2 |
| [O'Doherty NHP reaching](https://zenodo.org/records/583331) | M1 (some S1) | Self-paced reaches, 8x8 grid, fingertip at 250 Hz | 2 NHP | 24.0 GB | CC BY 4.0 | 1 | 3 |
| [FALCON H1](https://dandiarchive.org/dandiset/000954) | Human intracortical | 7-DoF reach and grasp (open-loop) | 1 human (metadata says 3) | 102 MB | CC-BY-4.0 | 0 | 2 |
| [FALCON H2](https://dandiarchive.org/dandiset/000950) | Human intracortical (T5) | Handwriting | 1 human | 1.2 GB | CC-BY-4.0 | 2 | 0 |
| [FALCON M1-A](https://dandiarchive.org/dandiset/000941) | M1 spikes | Reach-to-grasp, 4 objects x 8 positions | NHP (metadata: 3) | 312 MB | CC-BY-4.0 | 2 | 1 |
| [FALCON M2](https://dandiarchive.org/dandiset/000953) | M1 spikes | 2-DoF finger velocity to cued targets | 1 NHP | 15.9 GB | CC-BY-4.0 (draft dandiset, no published version) | 1 | 2 |
| [Willett handwriting](https://datadryad.org/stash/dataset/doi:10.5061/dryad.wh70rxwmv) | Utah arrays | Attempted handwriting, 43,501 characters | 1 human (T5) | 1.41 GB | CC0 1.0 | 2 | 0 |
| [Willett speech (B2T '24)](https://datadryad.org/stash/dataset/doi:10.5061/dryad.x69p8czpq) | Utah arrays | Attempted speech + orofacial movement task | 1 human (T12) | ~80 GB (API, all versions) | CC0 1.0 | 1 | 0 |

No BrainGate cursor dandiset was found on DANDI. The public BrainGate cursor data are on Dryad.

## ECoG
| Dataset | Modality | Task | Participants | Size | Licence (verified) | Intent | Control |
|---|---|---|---|---|---|---|---|
| [Miller ECoG library](https://purl.stanford.edu/zk881ps0522) | ECoG | 16 experiments, 204 datasets; includes `fingerflex` and `joystick_track` (task list inferred from secondary sources) | 34 patients | not stated | CC BY-SA 4.0 **[SA]** | 2 | 2 |
| [BCI Competition IV set 4](https://www.bbci.de/competition/iv/) | ECoG 48-64 ch | Flexion of each of 5 fingers + dataglove | 3 | not stated | **[NO LICENCE]** (terms checkbox, cite) | 2 | 1 |

## EEG
| Dataset | Modality | Task | Participants | Size | Licence (verified) | Intent | Control |
|---|---|---|---|---|---|---|---|
| [PhysioNet EEG Motor Movement/Imagery (EEGMMIDB)](https://physionet.org/content/eegmmidb/1.0.0/) | EEG 64 ch | Real + imagined fist L/R, both fists vs feet; rest events (T0) | 109 | 3.4 GB (1.9 GB zip) | ODC-By 1.0 | 3 | 0 |
| [Stieger 2021 SMR cursor](https://figshare.com/articles/dataset/Human_EEG_Dataset_for_Brain-Computer_Interface_and_Meditation/13123148) | EEG 64 ch | Online SMR cursor: 1D L/R, 1D U/D, 2D to 4 targets | 62 | 377 GB | CC BY 4.0 | 2 | 3 |
| [BNCI 002-2025](https://bnci-horizon-2020.eu/database/data-sets) | EEG 60 + EOG 4 | Continuous 2D trajectory tracking from attempted movement (from title) | 20 | not stated | CC BY 4.0 | 0 | 3 |
| [BNCI 001-2025 / 001-2024](https://bnci-horizon-2020.eu/database/data-sets) | EEG + EOG + movement | Discrete reaches (speed, distance, direction) / handwritten characters by kinematics | 20 / 20 | not stated | CC BY 4.0 | 2 | 2 |
| [BCI Competition IV 2a / 2b](https://bnci-horizon-2020.eu/database/data-sets) (BNCI 001-2014, 004-2014) | EEG 22 ch / 3 ch | 4-class / 2-class motor imagery | 9 / 9 | not stated | BNCI: CC BY-ND 4.0 **[ND]**; [bbci.de](https://www.bbci.de/competition/iv/): **[NO LICENCE]** | 3 | 0 |
| [BCI Competition IV set 1](https://www.bbci.de/competition/iv/) | EEG 64 ch | Uncued MI, 2 classes + idle | 7 | not stated | **[NO LICENCE]** | 3 | 0 |
| [BCI Competition III set II](https://www.bbci.de/competition/iii/) | EEG 64 ch | 6x6 P300 speller (36-way selection) | 2 | not stated | **[NO LICENCE]** | 3 | 0 |
| [BNCI 008-2014 / 003-2015](https://bnci-horizon-2020.eu/database/data-sets) | EEG | P300 speller (ALS patients / healthy) | 8 / 10 | not stated | CC BY-NC-ND 4.0 **[NC][ND]** | 3 | 0 |
| [OpenBMI / Lee2019](https://gigadb.org/dataset/100542) | EEG | MI 2-class, ERP speller, SSVEP 4-class | 54 | not stated (~0.5-0.7 GB per file) | **[NO LICENCE]** for the data (GigaDB API) | 3 | 0 |
| [Tsinghua SSVEP benchmark + BETA](https://bci.med.tsinghua.edu.cn/download.html) | EEG | 40-target SSVEP speller (count from the papers) | 35 + 70 | not stated | **[NO LICENCE]** | 3 | 0 |

BNCI rule of thumb (from the BNCI list): the 2014-2015 sets are mostly CC BY-NC-ND 4.0 or CC BY-ND 4.0. The sets from 2017 on are CC BY 4.0.

## EMG (forearm and wrist)
| Dataset | Modality | Task | Participants | Size | Licence (verified) | Intent | Control |
|---|---|---|---|---|---|---|---|
| [GRABMyo](https://physionet.org/content/grabmyo/1.1.0/) | sEMG forearm + wrist | 16 hand / finger gestures + rest | 43 | 9.4 GB | CC BY 4.0 | 3 | 0 |
| [Hyser HD-sEMG](https://physionet.org/content/hd-semg/2.0.0/) | HD-sEMG | 34 gestures; finger force tracking | 20 | 142.8 GB | ODC-By 1.0 | 3 | 1 |
| [Meta generic neuromotor interface](https://github.com/facebookresearch/generic-neuromotor-interface) | Wrist sEMG | Discrete gestures (~64 h), handwriting (~141 h), wrist angle with cursor-to-target stages (~77 h; likely 1D) | 100 per task | not stated | CC BY-NC 4.0 **[NC]** | 3 | 2 |
| [Meta emg2qwerty](https://github.com/facebookresearch/emg2qwerty) | Wrist sEMG | Touch typing, keylogger labels | 108 | not stated | README: CC-BY-NC-4.0; LICENSE file: CC BY-NC-SA 4.0 **[NC]** | 2 | 0 |
| [Meta emg2pose](https://github.com/facebookresearch/emg2pose) | Wrist sEMG + mocap | Hand pose regression | 193 | 431 GiB (mini ~600 MiB) | CC-BY-NC-SA-4.0 **[NC][SA]** | 0 | 1 |
| [Ninapro DB1-DB10](https://ninapro.hevs.ch/) | sEMG (+ glove, IMU) | 6-52 movement classes per DB | 10-77 per DB | not stated | **[NO LICENCE]** ("cite the article") | 3 | 1 |
| [Côté-Allard Myo armband](https://github.com/UlysseCoteAllard/MyoArmbandDataset) | Myo 8 ch | 7 classes incl. neutral | 22 + 18 | not stated | GPL-3.0 (repo licence) | 3 | 0 |
| [CSL-HDEMG](https://www.uni-bremen.de/en/csl/research/motion-recognition) | HD-sEMG | Finger motions (27 in the paper) | not stated | over 2 GB | **[NO LICENCE]** ("cite this paper") | 3 | 0 |
| putEMG ([paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6720505/)) | sEMG 24 ch | 7 gestures + idle | 44 | not stated | CC BY-NC 4.0 **[NC]** (from the paper; host page TLS error, not read) | 3 | 0 |
| CapgMyo | HD-sEMG 128 ch | 8 gestures + finger movements | 23 | unknown | **not verified** (host site down) | 3 | 0 |

> **Contradiction:** the [2026-11-10 survey](public-datasets.md) and the emg2qwerty README give CC BY-NC 4.0. The emg2qwerty `LICENSE` file is CC BY-NC-SA 4.0. Both are non-commercial. Treat it as the stricter CC BY-NC-SA 4.0 until Meta clarifies.

## Recommendations
Rule: CC0 / CC BY (or ODC-By, also attribution only), under 5 GB, verified licence.

### Top 3 for P12-03 (continuous control)
| Rank | Dataset | Why | Licence | Size |
|---|---|---|---|---|
| 1 | [BrainGate long-term unsupervised recalibration](https://datadryad.org/dataset/doi:10.5061/dryad.1jwstqk6g) | Human, **closed-loop** 2D cursor over four years: real user feedback, decoder drift, recalibration. Tests velocity scaling, safe-stop and drift alarms | CC0 1.0 | 1.69 GB |
| 2 | [NLB MC_RTT](https://dandiarchive.org/dandiset/000129) | Continuous, not trial-segmented reaching with targets: a clean benchmark with fixed splits (Neural Latents Benchmark). Tests the actuation policy on a known decoder baseline | CC-BY-4.0 | 51 MB |
| 3 | [BNCI 002-2025](https://bnci-horizon-2020.eu/database/data-sets) | **Non-invasive** (EEG) continuous 2D trajectory, 20 participants. Low SNR: the case where confidence gating matters most | CC BY 4.0 | not stated (check before download) |

Next candidates: [BrainGate MINDFUL](https://datadryad.org/dataset/doi:10.5061/dryad.n2z34tn5s) (CC0, 0.41 GB, at-home use) and [NoMAD](https://datadryad.org/dataset/doi:10.5061/dryad.q83bk3jtp) (CC0, 0.25 GB, `cursor_vel` ready). [Stieger 2021](https://figshare.com/articles/dataset/Human_EEG_Dataset_for_Brain-Computer_Interface_and_Meditation/13123148) is the best non-invasive closed-loop cursor set (CC BY 4.0, 62 people), but it is 377 GB.

### Top 3 for intent evaluation
| Rank | Dataset | Why | Licence | Size |
|---|---|---|---|---|
| 1 | [PhysioNet EEGMMIDB](https://physionet.org/content/eegmmidb/1.0.0/) | 109 people, discrete commands (L / R / both fists / feet) **plus rest events**: a real `null` intent for the no-signal rule. Many users for cross-user calibration tests | ODC-By 1.0 | 3.4 GB |
| 2 | [BrainGate preparatory encoding](https://datadryad.org/dataset/doi:10.5061/dryad.brv15dvr9) | 3 human implant users; delayed movements recast as discrete direction choice, plus closed-loop cursor (both profiles in one set) | CC0 1.0 | 1.54 GB |
| 3 | [BNCI 001-2025](https://bnci-horizon-2020.eu/database/data-sets) | EEG, 20 people, discrete reaches by direction / distance / speed: a menu-like N-way choice with kinematics | CC BY 4.0 | not stated (check before download) |

Strong fit but over 5 GB: [BrainGate multi-gesture drag-and-drop](https://datadryad.org/dataset/doi:10.5061/dryad.98sf7m0v1) (CC0, 8.2 GB) has click-and-hold gestures **with** 2D cursor control. It is the best single set for both profiles together (and for the P12-05 HID mapping). [GRABMyo](https://physionet.org/content/grabmyo/1.1.0/) (CC BY 4.0, 9.4 GB) is the best licence-clean EMG gesture set with a rest class.

> **Our take:** the clean sets for both profiles are implant (Dryad CC0, DANDI CC BY) or EEG (PhysioNet, BNCI 2017+). The famous gesture and speller sets (BCI Competition, Ninapro, Tsinghua SSVEP, OpenBMI) have no licence, and all Meta wrist-EMG releases are non-commercial. Use those only for non-commercial research comparisons, never in product work or shipped fixtures.

> **Our take:** for the intent profile, a rest class matters more than the class count. The P12-02 result showed that a decoder's zero-input output acts on 37 % of presses without a no-signal reference ([intent events](../concepts/intent-events.md)). EEGMMIDB and GRABMyo have recorded rest; most speller sets do not.

## Open points
- Sizes "not stated" (BNCI sets) need a check of the file list before any download.
- FALCON H1/H2 pages give 3 subjects in metadata but one participant in the text.
- NoMAD: the page names both a human (T11) and a monkey.
- putEMG and CapgMyo host pages could not be read; their licences are unverified on the host.
