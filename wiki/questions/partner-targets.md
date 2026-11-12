---
title: Partner targets for outreach (M7-02)
type: question
tags: [outreach, partners, adoption, standards, neuraltextstream]
sources: [neural-input-landscape-2026, brain-to-text-25-copytask, toronto-semg-typing]
updated: 2026-11-11
---

# Partner targets for outreach

**Question:** Which outside organisations should hear about NeuralTextStream (NTS) and the trust layer first? What can we offer each one? Through which public channel? When?

**Answer in short:** 15 targets in five groups. Priority 1 goes to groups whose data or devices we already use, or whose format we bridge: UC Davis Neuroprosthetics Lab, OpenBCI, Lab Streaming Layer (LSL), and Synchron (Apple BCI HID path). No target is "now". The roadmap rule is **demo + benchmark before outreach** ([roadmap P10](roadmap-standard.md#p10-adoption-plan)). The earliest step is after the benchmark page is public.

> **The user is the sender.** Agents draft. The user decides, sends and owns every contact. Agents send nothing, post nothing and contact no one. Message templates: [`papers/outreach/`](../../papers/outreach/README.md).

## Rules for this list
- Only **public organisational channels**: official contact pages and forms, developer portals, partner pages, GitHub issues or discussions, lab pages, working-group pages. No personal email addresses. No private data about individuals.
- Web research on 2026-11-11. Company facts change fast. **The user checks each URL and fact on the day of sending.**
- Company facts below come from press coverage and company pages, not peer review. They are context, not claims we repeat in messages.

## Timing levels
| Level | Condition | State on 2026-11-11 |
|---|---|---|
| **after benchmark page** | `benchmark/site/` is public (GitHub Pages) and the README quickstart works | Leaderboard built locally; GitHub Pages **not enabled** (needs the user's consent) |
| **after preprint** | Paper 1 is on arXiv | Draft v1 exists ([paper1-plan](paper1-plan.md)); arXiv endorsement **externally blocked** |
| **now** | — | Not used. See the roadmap rule above |

## Targets
Priority: 1 = first wave, 2 = second wave, 3 = later or opportunistic.

### Implant BCI companies
| # | Organisation | What they do | Why NTS / trust matters to them | What we can offer | Public channel (type) | Prio | Timing |
|---|---|---|---|---|---|---|---|
| 1 | **Synchron** | Endovascular implant (Stentrode). First company to integrate with Apple's BCI HID protocol (announced May 2025; iPad demo Aug 2025) ([MassDevice](https://www.massdevice.com/synchron-debuts-bci-controlled-ipad-apple/)) | Apple BCI HID carries a strength value, not a calibrated probability ([Apple BCI HID](../entities/apple-bci-hid.md)). NTS can sit upstream of HID and carry confidence and provenance | NTS → BCI HID bridge design; trust gate on their decoded selections or text; conformance check of their stream | Official site contact (synchron.com footer) and company LinkedIn (company page) | 1 | after preprint |
| 2 | **Paradromics** | High-channel-count implant (Connexus). Connect-One early feasibility study; first implant June 2026; first speech use reported Sept 2026 (company-reported, one participant) ([MassDevice](https://www.massdevice.com/paradromics-first-study-participant-uses-bci-for-real-time-speech/)). APEX partnership program for academic researchers (March 2026) ([Paradromics](https://www.paradromics.com/news/paradromics-launches-apex-partnership-program-to-boost-neurotechnology-discovery)) | Speech decoders that commit text need a wrong-commit bound before home use. Our B2T '25 result is on the same kind of data | Trust gate evaluation on their decoder output (offline, their data stays with them); NTS emitter recipe | Official contact page paradromics.com/contact (company form). APEX targets academics, not us | 2 | after preprint |
| 3 | **Blackrock Neurotech** | Utah array maker; MoveAgain platform. Its arrays are used by many academic BCI labs (BrainGate, Pittsburgh) | A common output format across the labs that use their hardware | NTS adapter for decoders on their platform; benchmark entry | Official site contact page blackrockneurotech.com (company form; check URL) | 2 | after preprint |

Watch list (no first contact planned): **Neuralink** (VOICE speech trial; no public partnership channel found; no peer-reviewed speech results found on 2026-11-11), **Precision Neuroscience** (Layer 7, 510(k) cleared for up to 30 days, 2025; Series D Sept 2026) ([Fierce Biotech](https://www.fiercebiotech.com/medtech/fda-clears-precision-neurosciences-minimally-invasive-brain-computer-interface-implant)). Revisit when either one publishes decoded-text output or a developer channel.

### Consumer EMG / EEG makers
| # | Organisation | What they do | Why NTS / trust matters to them | What we can offer | Public channel (type) | Prio | Timing |
|---|---|---|---|---|---|---|---|
| 4 | **Meta Reality Labs (Meta Neural Band)** | Wrist sEMG band shipped with Ray-Ban Display. Developer preview since about May 2026; raw EMG stays on device, only discrete events leave it ([Meta developers blog](https://developers.meta.com/blog/build-for-display-glasses/)) ([Meta Neural Band](../entities/meta-neural-band.md)) | Handwriting / typing from EMG commits text. A confidence + abstain layer fits the "discrete events" design | NTS profile for EMG key / gesture events; trust layer on sEMG typing ([EMG result](emg-toronto-trust-result.md)); benchmark track | Meta for Developers portal (developer program); `facebookresearch/emg2qwerty` GitHub (repo issues, research side) | 2 | after preprint |
| 5 | **OpenBCI** | Open-source EEG / EMG hardware (Cyton, Galea). Large hobby and research community | Open community with no shared text-output format. BrainFlow already reads their boards ([BrainFlow](../entities/brainflow.md)) | BrainFlow / LSL → NTS adapter; a quickstart for their community | openbci.com community forum (public forum); github.com/OpenBCI (GitHub) | 1 | after benchmark page |
| 6 | **Emotiv** | Consumer EEG headsets; Cortex API; partner tiers ([Emotiv developer](https://www.emotiv.com/developer)) | App developers on Cortex get mental-command outputs with no calibrated confidence | NTS emitter for Cortex outputs (intent profile, [roadmap P12](roadmap-standard.md#p12-beyond-text-intent-and-control-added-2026-11-11)) | emotiv.com/partner-with-us (partner page) | 3 | after preprint |
| 7 | **Neurable** | EEG in headphones; licenses its platform to OEMs (April 2026); dev kit and partner tracks ([Neurable partner page](https://www.neurable.com/partner)) | OEM partners need a vendor-neutral output format | Format bridge for their API events; no text-entry claim | neurable.com/partner (partner form) | 3 | after preprint |
| 8 | **g.tec medical engineering** | Research and clinical EEG BCI (Unicorn, P300 spellers); used in research in many countries ([g.tec](https://www.gtec.at/2025/03/10/solutions-for-neurotechnology/)) | P300 / SSVEP spellers commit characters. A trust layer and a shared format help their research users | NTS adapter for speller output; benchmark track for spellers (future) | gtec.at contact page and country directory (company form) | 2 | after preprint |

### Assistive technology / AAC
| # | Organisation | What they do | Why NTS / trust matters to them | What we can offer | Public channel (type) | Prio | Timing |
|---|---|---|---|---|---|---|---|
| 9 | **Tobii Dynavox** | Largest AAC maker (eye gaze, touch). Distributes Control Bionics' sEMG NeuroNode (2026) ([StockWireX](https://stockwirex.com/?p=46428)) | AAC software is where neural text lands. Our eWPM metric uses gaze typing as the no-BCI reference | NTS input path into AAC software; eWPM vs gaze baseline methods | tobiidynavox.com (company contact / partner page; check URL) | 2 | after preprint |

### BCI research labs with public data or decoders
| # | Organisation | What they do | Why NTS / trust matters to them | What we can offer | Public channel (type) | Prio | Timing |
|---|---|---|---|---|---|---|---|
| 10 | **UC Davis Neuroprosthetics Lab** | Intracortical speech BCI (BrainGate2 site); Brain-to-Text '25 data, CC0 ([B2T '25](../entities/brain-to-text-25.md)) | We already scored their published decoder output: wrong commits 0.194 → 0.044 at −4.3 % eWPM ([B2T '25 result](b2t25-trust-result.md)). They can check our use of their data | Their result on our benchmark track; NTS adapter for their data format; ask for correction of any misuse | github.com/Neuroprosthetics-Lab (GitHub); UC Davis Health lab page | 1 | after benchmark page |
| 11 | **Stanford NPTL / BrainGate consortium** | Intracortical handwriting and speech BCIs; CC0 datasets ([Willett 2021](../entities/willett-handwriting-2021.md)) | Benchmark culture; their data is a planned track | Willett handwriting track; NTS adapter | braingate.org/contact-us (consortium contact page); Stanford NPTL lab page | 2 | after benchmark page |
| 12 | **Meta FAIR Brain2Qwerty team** | MEG / EEG typing decoding; SpanishBCBL data and code, CC BY-NC 4.0 ([Meta FAIR](../entities/meta-fair-brain-ai.md)) | Our MEG track reproduces their setting. Their decoders could emit NTS | MEG benchmark track; trust results on MEG streams; a check of our dataset use | github.com/facebookresearch/brain2qwerty (repo issues) | 2 | after preprint |
| 13 | **University of Toronto / KITE-UHN (sEMG typing dataset)** | Forearm sEMG typing data, CC BY 4.0 ([Toronto sEMG](../entities/toronto-semg-typing-dataset.md)) | We built our EMG track on their data | Their dataset as a benchmark track; feedback on our composed-sentence caveat | Dataset record (Borealis, doi:10.5683/SP3/KV65VI, listed contact); lab page | 2 | after benchmark page |

### Standards bodies and open infrastructure
| # | Organisation | What they do | Why NTS / trust matters to them | What we can offer | Public channel (type) | Prio | Timing |
|---|---|---|---|---|---|---|---|
| 14 | **IEEE EMBS BCI working groups: P2731 (unified BCI terminology, data-sharing framework) and P2794 (reporting standards for in-vivo neural interface research)** | P2731 is an active PAR (2018); its plan includes a data-file framework ([sagroups P2731](https://sagroups.ieee.org/2731)). P2794 is an active PAR (2022) ([IEEE P2794](https://standards.ieee.org/ieee/2794/11108/)) ([IEEE P2731](../entities/ieee-p2731.md)) | Neither covers decoded output with confidence. NTS could map to P2731 terms and P2794 reporting items | A mapping table NTS ↔ P2731 terms; NTS as input to the data-sharing work; join as observer | sagroups.ieee.org/2731 and sagroups.ieee.org/2794 (WG pages; listserv / observer membership) | 2 | after preprint |
| 15 | **Lab Streaming Layer (LSL) maintainers** | De-facto transport for research biosignals ([LSL](../entities/lab-streaming-layer.md)) | NTS over LSL is our first transport. A wrong mapping would split the ecosystem | LSL stream-metadata profile for NTS; LSL ↔ NTS bridge with tests | github.com/sccn/labstreaminglayer (issues), forum.labstreaminglayer.org (forum), LSL Slack #users (public invite) | 1 | after benchmark page |

Also from the landscape, lower priority: Nokia Bell Labs (KT-sEMG, CC BY 4.0; [KT-sEMG](../entities/kt-semg-dataset.md)), Pittsburgh RNEL / CMU (Blackrock arrays; cursor and grasp decoders, intent profile later), Cognixion (EEG + AR AAC).

## Order of contact
| Wave | Targets | Gate |
|---|---|---|
| 1 | UC Davis (10), LSL (15), OpenBCI (5) | Benchmark page public; README quickstart tested by a fresh agent |
| 2 | Synchron (1), Stanford / BrainGate (11), Toronto (13), IEEE WGs (14), Meta FAIR (12) | Paper 1 on arXiv |
| 3 | Paradromics (2), Blackrock (3), Meta Reality Labs (4), g.tec (8), Tobii Dynavox (9) | A reply or a public adopter from waves 1–2 |
| 4 | Emotiv (6), Neurable (7) | Intent profile (P12) exists |

> **Our take:** Labs and open infrastructure first. They can verify our claims on their own data, and a public "works with B2T '25 / LSL / BrainFlow" note makes the company messages credible. Companies are more likely to answer a concrete artefact (a conformance report on their format, a bridge) than a pitch. Our strongest numbers are on intracortical data, so the implant and lab messages lead with them. Our MEG and EEG evidence is weak (no gain over gaze typing), so the consumer EEG messages make no speed claim.

## Related
- [Roadmap P10: adoption plan](roadmap-standard.md#p10-adoption-plan) · [Open-source playbook](open-source-playbook.md) · [Neural input landscape 2026](../sources/neural-input-landscape-2026.md) · [Public datasets survey](public-datasets.md)
- Outreach drafts: [`papers/outreach/`](../../papers/outreach/README.md)
