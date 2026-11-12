# Paper 1: detailed outline and results inventory

Status: **outline v0 (2026-11-11)**, updated 2026-11-11 for gap G1 (async MEG trust numbers). Milestone M3. Not yet a draft.
Wiki plan page: [wiki/questions/paper1-plan.md](../../wiki/questions/paper1-plan.md).

Rules for this file:
- Every number below is copied from a wiki result page or an experiment `results.md`. The source is named next to it. Do not round it again in the draft.
- CIs are 95 % bootstrap CIs. The unit of resampling is given where the source gives it: `[trial]`, `{day}`, `[sent]`, `{participant}`, or "instances".
- "Our take" items are interpretation, not results.

---

## 1. Working claim

A vendor-neutral stream format for neural decoder output (NeuralTextStream, NTS) plus a decoder-agnostic trust layer (calibration; COMMIT / OFFER / ABSTAIN; conformal risk control with an online, drift-robust version; a provenance ledger) makes neural text entry **safer** across three device types: MEG typing (SpanishBCBL), intracortical speech (Brain-to-Text '25, T15) and forearm sEMG key presses (Toronto). We measure safety as the wrong-commit rate and usefulness as effective WPM (eWPM) against a no-BCI gaze-typing baseline, with shuffled-input and null-input controls.

What the paper does **not** claim:
- It does not claim a better decoder than Brain2Qwerty v2 (different test split, see section 5.2).
- It does not claim that the BCI is faster than gaze typing on MEG (parity only).
- It does not claim a per-session or per-window guarantee (the guarantees are marginal or long-run averages).
- It does not claim results with live users (all eWPM comes from a simulated user).

## 2. Title options

1. **Fidetype: a vendor-neutral stream format and trust layer for safer neural text entry across MEG, intracortical and EMG decoders** (descriptive, recommended for arXiv)
2. *Know when to commit: decoder-agnostic calibration, abstention and risk control for brain-to-text* (claim-first)
3. *Trust before text: conformal wrong-commit control for neural text entry on three device types* (statistics-first; fits a conformal / ML venue)
4. *NeuralTextStream: an open format and trust layer for neural input, evaluated on MEG, intracortical and sEMG decoders* (standards-first; fits a benchmark or software venue)

## 3. Abstract draft (about 200 words)

> Neural text-entry decoders, from non-invasive MEG to intracortical arrays and wearable EMG, now produce fluent text, but they rarely signal when that text is wrong, and each device reports confidence in its own format. We present Fidetype, an open, vendor-neutral stream format for per-frame decoder output (NeuralTextStream) and a decoder-agnostic trust layer that reads only this stream. The layer calibrates confidence, chooses between committing, offering choices and abstaining, bounds the expected wrong-commit rate with conformal risk control, keeps that bound under within-session drift with online re-calibration from user corrections, and records each decision in a hash-chained provenance ledger. We apply the same layer, unchanged, to three device types with public data: MEG typing (19 participants), intracortical speech (one participant) and forearm sEMG key presses (19 participants). We report effective words per minute against a gaze-typing baseline, with shuffled and null-input controls. The layer cut wrong commits from 0.610 to 0.059 on intracortical speech with no measurable speed cost, from 0.54–0.96 to at most 0.004 on sEMG, and from 1.0 to 0 on MEG, and it committed no text from null input. Conformal risk control brought the mean wrong-commit rate to 0.046–0.048 (target 0.05); under drift, online re-calibration held it at 0.048–0.049 where offline calibration gave 0.0625–0.0635. On MEG, the system only reached parity with gaze typing.

(Word count: about 215. Numbers: B2T [b2t25-trust-result](../../wiki/questions/b2t25-trust-result.md); EMG [emg-toronto-trust-result](../../wiki/questions/emg-toronto-trust-result.md); CRC [m2-13-conformal-result](../../wiki/questions/m2-13-conformal-result.md); drift `aci_window` [m2-16-online-recal-result](../../wiki/questions/m2-16-online-recal-result.md); MEG parity and null input: async M1-09 streams, [G1 async trust](../../experiments/2026-11-11-g1-async-meg-trust/results.md) (G1 closed: trust 3.20 vs gaze 3.155 eWPM, trust − gaze CI over sentences [−0.04, +0.15]; 0 % commits on null input). The MEG sentence of the abstract stays true for the async decoder.)

## 4. Contributions

1. **A vendor-neutral stream format (NTS v0.1)** for neural decoder output: per-frame distributions over a declared vocabulary (characters, keys, phonemes), with timing, calibration and provenance semantic conventions. Three adapters (our own code) map MEG CTC output, intracortical phoneme logits and sEMG key-press classifiers into it. No breaking change was needed across the three device types ([spec](../../spec/neuraltextstream-v0.1.md); [B2T result](../../wiki/questions/b2t25-trust-result.md) "Spec"; [EMG result](../../wiki/questions/emg-toronto-trust-result.md) "Spec").
2. **A decoder-agnostic trust layer** that reads only NTS: frame and sentence temperature calibration, a hallucination guard (neural-evidence agreement), and a COMMIT / OFFER / OFFER_WORDS / ABSTAIN policy fitted for maximum eWPM under a wrong-commit limit. It also works as a **gate on a black-box LM-rescored decoder** (the published B2T '25 sentences).
3. **Finite-sample and drift-robust wrong-commit control.** Conformal risk control (CRC) and Learn-then-Test (LTT) for the COMMIT threshold, and an online controller (`window`, `decay`, `aci`, `aci_window`) that re-calibrates from user feedback, with a long-run bound for any sequence for `aci` and `aci_window`.
4. **A privacy-preserving provenance ledger**: an append-only, SHA-256 hash-chained record of every trust decision and user correction, without raw signals, that traces each wrong commit to the exact decoder, LM, calibration and policy versions.
5. **A cross-device evaluation protocol**: eWPM against a no-BCI gaze-typing baseline, wrong-commit and silent-error rates, shuffled / zeros / permuted / frame-shuffled / other-sentence controls, on three public datasets of three device types. Includes our own async MEG decoder that reaches v2's async SpanishBCBL CER range in the v2 input setting.
6. **Open release** under Apache-2.0: spec, reference implementation (`fidetype`), adapters, experiment scripts and configs.

## 5. Section-by-section outline with figure / table plan

Target length: about 9 pages main text + appendix (journal) or 9 pages (conference). Figures F1–F7, tables T1–T7. Figure scripts do not exist yet; see section 10.

### 5.1 Introduction (about 1 page)
- Problem: neural text entry is moving from labs to products (implants, wristbands, OPM-MEG). Decoders with an LM stage produce fluent but wrong text. A wrong committed sentence costs a user more than a slow one.
- Gap 1: no standard format for decoded neural output with honest confidence (Apple BCI HID gives a 0–255 strength, W3C EMMA has no per-frame distributions; [spec](../../spec/neuraltextstream-v0.1.md) section 2.2).
- Gap 2: no decoder-agnostic layer that decides *when to commit*, with a statistical guarantee, across devices.
- Gap 3: error rates (CER/WER) do not show whether the BCI saves the user time. A no-BCI baseline is rarely reported ([error metrics](../../wiki/concepts/error-metrics.md)).
- Contributions list (section 4). Teaser result sentence.
- **F1 (teaser):** wrong-commit rate vs eWPM per device, always-commit vs trust, with the gaze-only eWPM as a vertical line. Data: T3 rows.

### 5.2 Background and related work (about 1 page; full map in section 6)
- Brain-to-text decoders: MEG typing (Brain2Qwerty v1/v2), intracortical speech and handwriting, sEMG typing.
- Calibration and selective prediction; conformal prediction and risk control; online conformal under shift.
- Hallucination in LM-assisted decoding; text-entry and AAC metrics.
- Interoperability standards: BCI HID, EMMA, LSL, BIDS, IEEE P2731.

### 5.3 NeuralTextStream (about 1 page)
- Data model: frame core (time × vocabulary log-probabilities, `vocab_type`, `blank_id`, `frame_period`, `latency`), meta semantic conventions (`device.*`, `decoder.*`, `lm.*`, `adapter.*`, `calibration.*`), stability levels.
- The three adapters and the vocabulary each one uses (T1).
- Provenance meta keys (optional, non-breaking, 2026-11-11).
- **T1: Device and stream summary.**

| device | dataset (licence) | participants | test unit | decoder | NTS `vocab_type` | frame |
|---|---|---|---|---|---|---|
| MEG (typing) | SpanishBCBL (CC BY-NC 4.0) | 19 (test) | 637 instances, 17 unique sentences | own async ConvCTC, medium | char CTC | per MEG frame |
| intracortical (speech) | Brain-to-Text '25 copy task (CC0) | 1 (T15) | 816 trials, 14 days | published online logits; own word route | phoneme CTC, 41 tokens | 0.08 s |
| forearm sEMG (key presses) | Toronto sEMG typing (CC BY 4.0) | 19 | 551 composed sentences | own CNN | key (W3C codes), `blank_id = null` | one per press |

Sources: [M1-09](../../wiki/questions/m1-09-async-full-result.md), [B2T experiment](../../experiments/2026-11-10-b2t25-trust/results.md) "Setting", [EMG result](../../wiki/questions/emg-toronto-trust-result.md).

- **F2: architecture diagram** (adapter → NTS → calibration → guard → policy → CRC / online controller → user; ledger on the side). Base: `wiki/diagrams/06-architecture-layers.drawio` and `07-data-flow.drawio`; make a paper version.

### 5.4 Trust layer (about 1.5 pages)
- Calibration: frame temperature, sentence temperature; ECE.
- Candidate generation: CTC prefix beam + char 6-gram LM (Tatoeba), n-best.
- Guard: neural-evidence agreement of each candidate.
- Policy: actions COMMIT / OFFER / OFFER_WORDS / ABSTAIN; fit for max eWPM with wrong-commit ≤ 0.05 on fit data.
- Risk control: CRC (E[wrong-commit] ≤ α) and LTT (P(R ≤ α) ≥ 1 − δ) for the COMMIT threshold; `combine="max"` with the tuned threshold ([CRC concept](../../wiki/concepts/conformal-risk-control.md)).
- Online re-calibration: feedback table (which user actions reveal the truth), the four methods and their bounds ([M2-16](../../wiki/questions/m2-16-online-recal-result.md), "Methods").
- Provenance ledger: entry kinds, hash chain, privacy rules ([provenance ledger](../../wiki/concepts/provenance-ledger.md)).
- **T2: Online methods and guarantees** (copy the methods table from M2-16).

### 5.5 Evaluation protocol (about 1 page)
- eWPM definition: correct words per minute after the simulated user's corrections and selections ([architecture](../../wiki/questions/architecture.md)); KSR; wrong-commit (a committed sentence ≠ truth, or an OFFER_WORDS sentence with a wrong unhighlighted word); silent error (wrong commit the user does not notice, `p_miss_unflagged` 0.05).
- User model `UserConfig.aac_gaze()`: fallback gaze keyboard 20 chars/min and per-slot selection 4.5 s matched to Cai et al. 2024; neural input speed per device (B2T: measured 159.3 chars/min) ([trust core v0 results](../../wiki/questions/trust-core-v0-results.md) section 7; [B2T experiment](../../experiments/2026-11-10-b2t25-trust/results.md) "Setting").
- Baseline: gaze typing only (no BCI).
- Controls: shuffled MEG, zeros, labels permuted at train time, frame-shuffled stream, uniform stream, real stream of another sentence.
- Splits: MEG by sentence hash (no test sentence in train or LM text); B2T first / second half of each day; EMG composed held-out Tatoeba sentences.
- Statistics: bootstrap CIs, paired differences; resampling unit per dataset (trial, day, sentence, participant).

### 5.6 Results
**5.6.1 Decoders and controls (MEG decoder is ours; show that it uses the signal)**
- **T4: decoder quality.**

| device | decoder | metric | real input | controls |
|---|---|---|---|---|
| MEG | M1-09 medium async, greedy | CER vs target | 0.506 (participants 0.495 ± 0.020 SEM) | shuffled 0.760, zeros 0.925; gap +0.254 [+0.241, +0.265] (instances) |
| MEG | M1-09 medium, beam + LM | CER | 0.475 (participants 0.462 ± 0.022) | — |
| MEG | far sentences only (11) | CER greedy / beam | 0.519 / 0.492 | — |
| MEG | v2 Encoder Async (reference) | CER | 0.59 ± 0.02 (own split) | — |
| B2T | our word route | WER | 0.149 | — |
| B2T | published decoder | WER | 0.043 (0.0434 pooled, 1,718 trials) | — |
| EMG | CNN session-calibrated / cross-session / cross-subject | key accuracy | 0.299 / 0.168 / 0.209 | label-permuted 0.022 |

Sources: [M1-09](../../wiki/questions/m1-09-async-full-result.md) "Main numbers"; [B2T](../../wiki/questions/b2t25-trust-result.md); [EMG](../../wiki/questions/emg-toronto-trust-result.md).

**5.6.2 Main result: safety and speed on three devices**
- **T3: trust harness, test sets.**

| device / condition | policy | eWPM [CI] | wrong-commit | silent error |
|---|---|---|---|---|
| B2T, our decoder | always commit top-1 | 11.45 [10.95, 12.04] {10.72, 12.32} | 0.610 [0.574, 0.645] | 0.044 |
| | trust | 11.55 [11.03, 12.06] {10.85, 12.38} | 0.059 [0.043, 0.075] | 0.002 |
| B2T, published decoder | always commit | 19.61 [18.68, 20.51] {17.76, 21.45} | 0.194 [0.167, 0.222] | 0.025 |
| | trust gate | 18.77 [17.88, 19.62] {17.05, 20.46} | 0.044 [0.031, 0.059] | 0.004 |
| B2T | gaze only | 4.08 [4.04, 4.12] | 0 | 0 |
| EMG session-calibrated | always commit LM top-1 | 7.81 [7.36, 8.30] {6.60, 9.01} | 0.541 | 0.060 |
| | trust | 8.02 [7.63, 8.45] {6.90, 9.15} | 0.004 | 0.000 |
| EMG cross-session | always commit LM top-1 | 4.10 [3.89, 4.34] {3.59, 4.70} | 0.882 | 0.149 |
| | trust | 4.68 [4.52, 4.86] {4.21, 5.25} | 0.004 | 0.000 |
| EMG cross-subject | always commit LM top-1 | 3.53 [3.37, 3.72] | 0.962 | 0.167 |
| | trust | 4.08 [3.98, 4.20] | 0.000 | 0.000 |
| EMG | gaze only | 4.27 | 0 | 0 |
| **MEG, async M1-09 (main)** | always commit LM top-1 | 2.58 [2.41, 2.76] {2.41, 2.79} | 0.997 | 0.235 |
| | trust | 3.20 [3.07, 3.36] {3.08, 3.37} | 0 | 0 |
| MEG, sync M1-15 full-r1 (secondary) | always commit LM top-1 | 2.71 [2.54, 2.90] {2.54, 2.90} | 1.0 | 0.199 |
| | trust | 3.23 [3.08, 3.40] {3.12, 3.37} | 0 | 0 |
| MEG | gaze only | 3.155 [3.02, 3.29] {3.15, 3.16} | 0 | 0 |

Brackets: B2T `[trial] {day}`; EMG `[sent] {participant}`; MEG `[unique sentence] {participant}` (cluster bootstrap; the two-way sentence × participant CI is in the G1 results). MEG paired (async): trust − commit [+0.49, +0.75]; trust − gaze +0.05 [−0.04, +0.15] (sentences), [−0.07, +0.22] (participants), [−0.11, +0.26] (two-way); sync trust − gaze [−0.02, +0.18] (sentences). Paired: B2T trust − commit eWPM [−0.11, +0.30], wrong-commit [−0.587, −0.516]; published gate − commit eWPM [−0.98, −0.72] (−4.3 %), wrong-commit [−0.175, −0.126]; EMG trust − commit eWPM [+0.05, +0.38] / [+0.44, +0.72] / [+0.43, +0.67]; EMG session-calibrated trust − gaze [+3.38, +4.16].
Sources: [B2T experiment](../../experiments/2026-11-10-b2t25-trust/results.md) "Trust harness, word level"; [EMG experiment](../../experiments/2026-11-11-emg-toronto/results.md) "Trust harness"; MEG [G1 async trust](../../experiments/2026-11-11-g1-async-meg-trust/results.md) (async and sync rows from the same script; the sync row reproduces [M1-15 full-r1](../../wiki/questions/m1-15-full-r1-r3-result.md) "Trust layer" exactly).
**Note in the text:** the main MEG row is the async M1-09 decoder of T4 (G1 closed). The sync row is secondary: it shows the result does not depend on oracle key timing.

- **F3: eWPM per policy per device, with gaze-only line** (bar or dot plot with CIs). Data: T3.
- **F4: wrong-commit vs commit rate (risk–coverage) per device**, for −p_top1 and the guard score. Data: harness `trust.json` per experiment; AUROC B2T −p_top1 0.797 (word) / 0.884 (phoneme); EMG 0.83 / 0.76 / 0.67.

**5.6.3 Null-input and hallucination controls**
- **T5: commits on null input.**

| device | input | always commit | trust |
|---|---|---|---|
| **MEG (async M1-09, main)** | real / shuffled MEG / zeros MEG / other sentence / frame-shuffled / uniform: commits (fluent) | 100 % (85 % / 92 % / 100 % / 85 % / 89 % / 100 %) | 0 % in all |
| MEG (M2-10 sync keystroke decoder, secondary) | real / shuffled MEG / frame-shuffled / uniform: fluent commits | 83 % / 84 % / 86 % / 100 % | 0 % in all |
| B2T | frame-shuffled, uniform | 100 % | 0 % |
| B2T | real stream of another sentence | — | 22 % (ours), 0 % (published gate) |
| EMG | frame-shuffled, zeros, permuted decoder | 100 % wrong | 0 % |
| EMG | real stream of another sentence | — | as often as real input |

Sources: [G1 async trust](../../experiments/2026-11-11-g1-async-meg-trust/results.md) "Null-input audit" (async; guard-risk AUROC null vs real: shuffled 0.92, zeros / uniform 1.00, other sentence 0.49); [trust core v0](../../wiki/questions/trust-core-v0-results.md) section 6; [B2T](../../wiki/questions/b2t25-trust-result.md); [EMG](../../wiki/questions/emg-toronto-trust-result.md) "Controls".
- Discussion point: no stream-only signal can detect a real stream of a different intended sentence. This is a limit of any decoder-agnostic layer.

**5.6.4 Calibration**
- B2T sentence ECE 0.448 → 0.067 (frame T 3.78). EMG sentence ECE 0.154 → 0.148, 0.328 → 0.072, 0.500 → 0.083 (frame T 1.25 / 1.78 / 2.17). Simulator: character ECE 0.16–0.39 → 0.012–0.021. LM fusion makes confidences over-confident (ECE 0.053 / 0.099 / 0.177).
- **F5: reliability diagrams**, before / after, B2T and EMG cross-session.

**5.6.5 Finite-sample risk control (CRC / LTT)**
- **T6: CRC / LTT on B2T and MEG (n_cal 408, 200 splits).** Copy the M2-13 main table: B2T ours old gate 0.0586 → CRC 0.0483 → LTT 0.0345 (eWPM 11.57 / 11.53 / 11.52); published 0.0441 / 0.0478 / 0.0345 (18.77 / 18.78 / 18.70); MEG async M1-09 (G1) 0 / 0.0193 / 0.0214 (eWPM 3.204 / 3.199 / 3.199; p95 CRC 0.031, LTT 0.035; splits grouped by sentence or participant: CRC 0.0194 / 0.0201); MEG sync M1-15 (secondary) 0.0000 / 0.0186 / 0.0207 (3.23 / 3.22 / 3.22). p95: CRC 0.071–0.076, LTT 0.056–0.061; 41–45 % of CRC splits above 0.05 ([M2-13](../../wiki/questions/m2-13-conformal-result.md)).
- EMG: CRC / LTT feasible with n = 142; equal to the plug-in policy (thresholds xsession CRC 0.204, bound 0.049).
- **F6: distribution of test wrong-commit over 200 splits** (violin per method, α line). Data: `experiments/2026-11-11-m2-13-conformal/results/splits.json`.

**5.6.6 Drift and online re-calibration**
- **T7: drift protocol** (copy the M2-16 results table): B2T ours offline CRC 0.0625 → window 0.0453 / decay 0.0417 / aci 0.0502 / aci_window 0.0478; EMG cross-session 0.0635 → 0.0508 / 0.0399 / 0.0526 / 0.0490; eWPM B2T 11.553 → 11.490–11.510; EMG 4.657 → 4.667–4.670. MEG async (G1): offline CRC 0.0204 → `aci` 0.0188, `aci_window` 0.0078 (degenerate: every commit is wrong).
- Robustness: feedback 10 trials late 0.0404–0.0502 (B2T ours); cold start `aci` 0.0442, `aci_window` 0.0491; max over 50-trial windows 0.10–0.12 for all methods (i.i.d. Bernoulli(0.05) median 0.120); noticed-only feedback `aci` 0.0515 (B2T), 0.0635 (EMG).
- **F7: running wrong-commit rate over the later half of the session**, offline CRC vs `aci` vs `aci_window`, B2T ours. Data: `experiments/2026-11-11-m2-16-online-recal/results/online.json`.
- Note the reported contradiction: M6-07 CRC 0.004 (with `combine="max"`) vs M2-16 offline CRC 0.0635 (pure threshold) on EMG cross-session. Both are right; explain once.

**5.6.7 Provenance audit**
- B2T replay: 1,723 entries, `verify` passes; ledger wrong commits = harness, 48 / 48 (plug-in) and 39 / 39 (CRC); silent 2 / 1; all tamper cases detected (edit, edit with re-hash, delete, reorder; tail cut with head anchor); about 0.1 ms and about 1.1 kB per decision ([provenance ledger](../../wiki/concepts/provenance-ledger.md)). Short text box with one anonymised audit entry.

**5.6.8 Ablations**
- Available now: B2T trust without calibration wrong-commit 0.071 vs 0.059 (eWPM 11.57 vs 11.55); without guard 0.036 (11.51) — the guard did not help on B2T. EMG without calibration: higher wrong-commit (calib 0.045 vs 0.004) and higher eWPM (8.15 vs 8.02). Simulator: thresholds fitted on validation absorb most of what calibration and the guard add. OFFER_WORDS: +0.4 to +1.7 eWPM at the worst simulator preset, never selected on real MEG.
- Needed: one unified ablation table over the three devices (gap G5).

### 5.7 Discussion (about 0.75 page)
- The trust layer turns a fixed decoder into a safer one; it does not make a weak decoder fast. EMG cross-subject and MEG stay at or below gaze typing.
- Product-relevant: a strong LM-rescored decoder (WER 4 %) still commits a wrong sentence 19 % of the time; the gate keeps 96 % of its speed and cuts wrong commits to 4 % ([B2T](../../wiki/questions/b2t25-trust-result.md), "Our take").
- Per-session calibration matters more than the trust layer for speed on EMG (8.02 vs 4.68 eWPM).
- How to state guarantees: "expected wrong-commit ≤ 0.05 for this user in this session given n calibration sentences" (CRC); "long-run average over T items" (online); silent-error rate next to it.
- What standardisation buys: one gate, three devices, no code change per device beyond the adapter.

### 5.8 Limitations (section 7 below, condensed to about 0.5 page)

### 5.9 Conclusion and future work
- User study with gaze-typing users (needs ethics approval; externally blocked); streaming decoder (Paper 2, M4); spec conformance suite and v1.0; benchmark hub (P13).

### Appendix plan
- A. NTS v0.1 field list and the three adapter mappings.
- B. User model parameters and their sources; eWPM sensitivity (fallback 10 / 20 / 40 chars/min, selection time, `p_miss_unflagged`).
- C. MEG decoder details (ConvCTC, keystroke aux loss, async check table from M1-09), leakage checks (hash split, LM text filter, near-variant analysis).
- D. Full CRC / LTT tables at n_cal 100 and 408; online-method hyper-parameters.
- E. Simulator results (trust core v0 sections 1, 5, 7), as supplementary evidence only.
- F. Provenance schema and an example audit report.

## 6. Related work map

Existing wiki source pages are linked. Items marked **to add** have no source page yet (most are in the [reading list](../../wiki/questions/reading-list.md)); they need a source page before the draft cites them.

| topic | have (wiki source / entity page) | to add |
|---|---|---|
| Non-invasive typing decoding | [Brain2Qwerty v1](../../wiki/sources/brain2qwerty-v1.md), [v2](../../wiki/sources/brain2qwerty-v2.md), [code](../../wiki/sources/brain2qwerty-code.md); [SpanishBCBL](../../wiki/entities/spanishbcbl-dataset.md) | Défossez et al. 2023; Jayalath et al. 2025 (non-invasive brain-to-text); MEG-XL (Jayalath & Parker Jones 2026); LibriBrain |
| Intracortical text | [Brain-to-Text '25 copy task](../../wiki/sources/brain-to-text-25-copytask.md), [B2T '25 entity](../../wiki/entities/brain-to-text-25.md), [Willett handwriting 2021](../../wiki/entities/willett-handwriting-2021.md) | Card et al. 2024 (NEJM) as a source page; Willett et al. 2023 (speech); Willett et al. 2021 paper; Jude et al. 2026 (typing); Metzger et al. 2023; B2T '24 lessons (Willett et al. 2024) |
| sEMG typing | [Toronto sEMG typing](../../wiki/sources/toronto-semg-typing.md), [KT-sEMG](../../wiki/entities/kt-semg-dataset.md), [emg2qwerty](../../wiki/entities/emg2qwerty.md), [Meta Neural Band](../../wiki/entities/meta-neural-band.md) | Sivakumar et al. 2024 (emg2qwerty paper) as a source page |
| Calibration / uncertainty in BCI | — | **Huang et al. 2025 (co-control BCI, closest work)**; **Kim et al. 2025 (confidence-aware EEG speech decoding)**; Benster et al. 2024; Guo et al. 2017; Ovadia et al. 2019 |
| Conformal / risk control | [CRC](../../wiki/sources/conformal-risk-control.md), [LTT](../../wiki/sources/learn-then-test.md), [ACI](../../wiki/sources/adaptive-conformal-inference.md), [conformal PID](../../wiki/sources/conformal-pid-control.md), [rolling RC](../../wiki/sources/rolling-risk-control.md), [beyond exchangeability](../../wiki/sources/conformal-beyond-exchangeability.md), [non-exchangeable CRC](../../wiki/sources/non-exchangeable-crc.md), [covariate shift](../../wiki/sources/conformal-covariate-shift.md) | Angelopoulos & Bates 2021 (gentle intro); **Ernez et al. 2023 (conformal ASR)**; **Damri & Laufer-Goldshtein 2026 (risk-controlled generative ASR)**; Quach et al. 2024 (conformal LM); Mohri & Hashimoto 2024 |
| Selective prediction / abstention | — | Geifman & El-Yaniv 2017; Chow 1970; Hendrycks & Gimpel 2017; Abbasi Yadkori et al. 2024 |
| Hallucination in LM-assisted decoding | [NeuroLLM concept](../../wiki/concepts/neuro-llm.md) | Farquhar et al. 2024; Koenecke et al. 2024 (Careless Whisper); Chen et al. 2023 (HyPoradise) |
| Text-entry / AAC metrics | [error metrics concept](../../wiki/concepts/error-metrics.md) | **Cai et al. 2024 (user-model basis)**; Dal Seno et al. 2010 (utility metric); Wolpaw et al. 2002 (ITR); Yuan et al. 2013; Soukoreff & MacKenzie 2003; **RAS, Huang et al. 2026 (check formula first)** |
| Standards / interoperability | [Apple BCI HID](../../wiki/entities/apple-bci-hid.md), [W3C EMMA](../../wiki/entities/w3c-emma.md), [LSL](../../wiki/entities/lab-streaming-layer.md), [BIDS](../../wiki/entities/bids.md), [IEEE P2731](../../wiki/entities/ieee-p2731.md), [BrainFlow](../../wiki/entities/brainflow.md); [OpenTelemetry case study](../../wiki/sources/case-study-opentelemetry.md); [neural input landscape 2026](../../wiki/sources/neural-input-landscape-2026.md) | Kothe et al. 2024 (LSL paper); NeuralBench (Banville et al. 2026); MOABB |
| Provenance / audit | [provenance ledger concept](../../wiki/concepts/provenance-ledger.md) | IEC 62304 traceability text (we have not read it; do not cite without reading); a tamper-evident log reference (e.g. Crosby & Wallach 2009, Certificate Transparency RFC 6962) |
| CTC / decoding | [CTC concept](../../wiki/concepts/ctc.md), [sync vs async](../../wiki/concepts/synchronous-vs-asynchronous-decoding.md) | Graves et al. 2006; Hannun et al. 2014 (prefix beam + LM); Gulati et al. 2020 (Conformer) |

Closest-work positioning (M3-03): Huang et al. 2025 (calibration and alternatives improve brain-to-text fusion; no guarantee, one device), Kim et al. 2025 (ensembles + calibration + abstention on EEG; one device, no LM gate), Damri & Laufer-Goldshtein 2026 (risk-controlled LM correction for ASR; not neural, not online). Our difference: one format and one layer across three device types, finite-sample and drift-robust wrong-commit control, eWPM against a no-BCI baseline, provenance.

## 7. Limitations (candid; the paper section)

1. **One implant participant.** B2T '25 is T15 only, copy task, online logits we cannot re-run. CIs over trials and over 14 days, not over people.
2. **17 unique MEG test sentences** (637 instances, 19 participants). Instance-level CIs understate sentence-level variance. 6 of 17 test sentences have a close train variant (about 0.013 greedy CER effect); "far" numbers are reported next to the headline.
3. **MEG test split differs from v2**; our async decoder uses key times as training labels (aux loss) though not as inputs. "0.495 vs 0.59" is not a head-to-head result.
4. **MEG decoder only reaches parity with gaze typing** (async M1-09: trust 3.20 vs gaze 3.155 eWPM; trust − gaze [−0.04, +0.15] over sentences; sync M1-15: 3.23). On MEG the trust layer shows safety, not usefulness. The true sentence is in the 10-best for 1.6 % (async) / 0.6 % (sync) of trials. Trial-level CIs would make the sync result look like a small gain ([+0.03, +0.12]); we report sentence-level CIs.
5. **Composed EMG sentences.** The Toronto data has isolated key presses only; sentences are composed from single presses with oracle timing and no inter-key context. Natural typing is untested.
6. **No live users.** All eWPM values come from a simulated user. Several time costs are literature-based assumptions; only the 20 chars/min fallback and the 4.5 s per-slot sum are matched to Cai et al. 2024; `p_miss_unflagged` has no measurement. On MEG, a 40 chars/min fallback makes gaze typing clearly faster (6.31 vs 5.15).
7. **Silent errors** (wrong commits the user does not notice) are outside every guarantee. With noticed-only feedback, `aci` gave 0.0515 (B2T) and 0.0635 (EMG).
8. **Guarantees are marginal or long-run.** CRC bounds the mean over sessions (41–45 % of splits exceed 0.05); online bounds are long-run averages; 50-trial windows reach 0.10–0.12.
9. **Stream-only gating cannot detect intent mismatch.** A real stream of another sentence is committed as often as real input (B2T ours 22 %; EMG same as real).
10. **One seed** for every decoder and harness run; one fit/test split for B2T and EMG trust.
11. **Simple LMs.** Char 6-gram + word unigram (Tatoeba). 64 of 1,628 B2T cue sentences occur in Tatoeba English (possible small leak, not removed).
12. **Provenance is tamper-evident, not tamper-proof**; no signing; wrong commits are known only after a correction in live use.

## 8. Ethics and data-licence statement (draft)

> This study uses only public, de-identified datasets. No new data were collected and no human-subject experiment was run, so no new ethics approval was required. We did not attempt re-identification. Raw recordings and participant data are not redistributed; our repository contains code, configurations, derived summary statistics and audit logs only.

| dataset / resource | licence | use in the paper | note |
|---|---|---|---|
| SpanishBCBL (Lévy et al. 2026, HF `bcbl190626/SpanishBCBL`) | CC BY-NC 4.0 | MEG decoder training and evaluation | Research only. Weights trained on it are not released for commercial use |
| Brain-to-Text '25 copy-task logits (Card et al. 2024, Dryad doi:10.5061/dryad.dncjsxm85) | CC0 1.0 | trust evaluation (intracortical) | Companion code has no licence; we wrote our own loader |
| Toronto sEMG typing (Achituve et al. 2025, Borealis doi:10.5683/SP3/KV65VI) | CC BY 4.0 | EMG decoder and trust evaluation | Attribution required. Baseline code CC BY-SA 4.0, not used |
| Tatoeba English / Spanish sentences | CC BY 2.0 FR (some CC0) | char n-gram LMs, composed EMG sentences | Attribution: "Sentences from Tatoeba (https://tatoeba.org), by the Tatoeba contributors, CC BY 2.0 FR." |
| CMUdict (commit 7479086) | BSD-2-Clause style | phoneme → word lexicon (B2T) | Keep the copyright notice |
| Brain2Qwerty code (Meta) | CC BY-NC 4.0 | read only; not copied | Our decoders are our own implementations |
| Fidetype code and spec | Apache-2.0 | all methods | — |

Sources: [references/README.md](../../references/README.md), [src/fidetype/lm/corpora.md](../../src/fidetype/lm/corpora.md), dataset entity pages. Mention: the authors used AI coding agents under human review (state in acknowledgements per venue policy).

## 9. Results inventory

Status key: **final** = usable as is (with the stated scope); **needs rerun** = the number must be recomputed with a different input or protocol; **needs seeds** = needs repeated seeds or splits before submission; **needs CI** = needs a CI with a better resampling unit.

| # | claim | number(s) | source file | status |
|---|---|---|---|---|
| R1 | NTS v0.1 needs no breaking change across 3 device types | char CTC, phoneme CTC, key vocabularies; one optional harness field (`Item.stream_text`); optional provenance meta keys | `spec/neuraltextstream-v0.1.md`; `wiki/questions/b2t25-trust-result.md`; `wiki/questions/emg-toronto-trust-result.md` | final (descriptive); add conformance-suite result when the parallel work lands |
| R2 | Async MEG decoder in the v2 input setting | greedy 0.506, participants 0.495 ± 0.020 SEM; beam + LM 0.475 / 0.462 | `experiments/2026-11-11-m1-09-async-full/results.md`; `wiki/questions/m1-09-async-full-result.md` | needs seeds; needs CI (sentence level) |
| R3 | MEG decoder uses the signal | shuffled 0.760, zeros 0.925; gap +0.254 [+0.241, +0.265] (instances) | same | final for the claim; CI unit instances |
| R4 | Near-variant effect is small | far sentences 0.519 / 0.492; effect about 0.013 greedy, 0.017 beam | same | final |
| R5 | Longer training does not help | r5 − r4b greedy +0.009 [+0.003, +0.015] | same, section 7 | final (appendix only) |
| R6 | MEG trust: safe, parity with gaze | async M1-09: always 2.58, trust 3.20 [3.07, 3.36] (sentences) {3.08, 3.37} (participants), gaze 3.155; wrong-commit 0.997 → 0; trust − gaze [−0.04, +0.15]. Sync M1-15 (secondary): 2.71 / 3.23 [3.08, 3.40] | `experiments/2026-11-11-g1-async-meg-trust/results.md`; `wiki/questions/m1-09-async-full-result.md` | **final** (G1 done; sentence, participant and two-way CIs done); needs seeds |
| R7 | MEG null input: no fluent commits | async M1-09: always commit 100 % commits, 85–100 % fluent (real, shuffled, zeros, other sentence, frame-shuffled, uniform); trust 0 %. Sync M2-10: 83–100 % / 0 % | `experiments/2026-11-11-g1-async-meg-trust/results.md` | **final** (G1 done) |
| R8 | B2T trust cuts wrong commits at no speed cost | 0.610 → 0.059 [0.043, 0.075]; eWPM 11.45 → 11.55; paired eWPM [−0.11, +0.30] | `experiments/2026-11-10-b2t25-trust/results.md` (`results/trust.json`) | final for one participant; needs seeds (repeated fit/test splits) |
| R9 | B2T published-sentence gate | 0.194 → 0.044; eWPM 19.61 → 18.77 (−4.3 %) | same | final; needs seeds (splits) |
| R10 | All B2T BCI policies beat gaze | gaze 4.08; trust − gaze [+6.96, +7.97]; gate − gaze [+13.81, +15.53] | same | final |
| R11 | Confidence predicts errors (B2T) | AUROC −p_top1 0.797 word / 0.884 phoneme; word conf 0.844; ECE 0.448 → 0.067 | same, "Calibration and error prediction" | final |
| R12 | B2T null input | shuffled / uniform 0 % commits; other sentence 22 % (ours), 0 % (gate) | same, "Null-input audit" (300 random trials) | final |
| R13 | EMG trust cuts wrong commits; eWPM up | wrong-commit 0.541 / 0.882 / 0.962 → 0.004 / 0.004 / 0.000; eWPM 7.81 → 8.02, 4.10 → 4.68, 3.53 → 4.08 | `experiments/2026-11-11-emg-toronto/results.md` (`results/trust.json`) | needs seeds (decoder: one seed); composed sentences (G4) |
| R14 | Only session-calibrated EMG beats gaze | trust − gaze [+3.38, +4.16]; gaze 4.27 | same | final with scope |
| R15 | EMG calibration | sentence ECE 0.154 → 0.148, 0.328 → 0.072, 0.500 → 0.083; AUROC 0.83 / 0.76 / 0.67 | same, "Calibration" | final |
| R16 | EMG null input | always commit 100 % wrong on null streams; trust 0 %; permuted decoder key acc 0.022 | same; `wiki/questions/emg-toronto-trust-result.md` | final |
| R17 | CRC fixes the mean wrong-commit (B2T) | ours 0.0586 → CRC 0.0483, LTT 0.0345; published 0.0441 → 0.0478 / 0.0345; p95 CRC 0.071–0.076, LTT 0.056–0.061 | `experiments/2026-11-11-m2-13-conformal/results.md` (`results/splits.json`) | final (200 splits) |
| R18 | CRC cost is small | −0.3 % eWPM (ours), +0.1 % (published) at n_cal 408 | same | final |
| R19 | CRC spends budget on useless MEG commits | async M1-09: CRC 0.0193, LTT 0.0214, old gate 0; eWPM 3.199 vs 3.204; grouped by sentence / participant: CRC 0.0194 / 0.0201. Sync: 0.0186 / 0.0207 | `experiments/2026-11-11-g1-async-meg-trust/results.md` | **final** (G1 done; sentence- and participant-grouped splits done) |
| R20 | Drift breaks offline CRC | B2T 0.0625; EMG cross-session 0.0635 | `experiments/2026-11-11-m2-16-online-recal/results.md` | final (one time order) |
| R21 | Online re-calibration restores the target | `aci_window` 0.0478 (B2T), 0.0490 (EMG); `aci` 0.0502 / 0.0526; eWPM cost ≤ 0.6 % | same (`results/online.json`) | final; add CI over sessions / days (G3) |
| R22 | Online robustness | delay 10: 0.0404–0.0502; cold start `aci` 0.0442, `aci_window` 0.0491; 50-trial max 0.10–0.12; noticed-only `aci` 0.0515 / 0.0635 | same | final |
| R23 | Provenance ledger traces all wrong commits | 48 / 48, 39 / 39; 1,723 entries; all tamper cases detected; about 0.1 ms, about 1.1 kB per decision | `experiments/2026-11-11-m2-09-provenance/results.md` (`results/summary.json`) | final |
| R24 | Ablations (partial) | B2T no-calibration 0.071, no-guard 0.036; EMG no-calibration calib 0.045 / 8.15 eWPM | B2T and EMG `results.md` | **incomplete** (G5) |
| R25 | Simulator: trust matches always-commit speed with 3× fewer wrong commits | 25.3 vs 25.8 eWPM; 0.033 vs 0.108 | `experiments/2026-11-08-beam-retune/results.md` | supplementary; needs seeds (one per condition) |
| R26 | OFFER_WORDS helps only near-correct decoders | worst preset +0.4 to +1.7 eWPM ([0.36, 1.57], [0.40, 1.74]); MEG never selected | `experiments/2026-11-08-m2-offer-words/results.md` | supplementary; needs seeds |
| R27 | eWPM depends on the user model | MEG: 40 cpm fallback gaze 6.31 vs 5.15 | `experiments/2026-11-09-m1-15-sentence-context/results-full-r1-r3.md` | **incomplete**: sensitivity on all three devices (G6) |

## 10. Gaps before submission

Ordered by importance. Items marked (ext) depend on outside people (`externally_blocked` in the tracker).

| id | gap | why the paper needs it | how |
|---|---|---|---|
| G1 | ~~Trust harness on the M1-09 async streams~~ **DONE 2026-11-11** | — | Done: harness, null audit, CRC / LTT, online on `m1-09-r4b-full-medium` streams: [G1 async trust](../../experiments/2026-11-11-g1-async-meg-trust/results.md). R6, R7, R19 updated |
| G2 | **Multiple seeds** | Every decoder and trust run is one seed | MEG ConvCTC × 3 seeds (about 3 GPU runs; one heavy job at a time); EMG CNN × 3 seeds per condition; simulator × 5 seeds |
| G3 | **CIs over sentences and participants** (partly done) | MEG CIs are over instances of 17 sentences | Done for R6 (sentence, participant, two-way) and R19 (grouped splits) in G1. Still open: R2, R3 (CER) and day/session CIs for R20–R21 |
| G4 | **Natural-typing sEMG (KT-sEMG, CC BY 4.0)** | EMG sentences are composed from isolated presses | New adapter + decoder on KT-sEMG (one typist); or state as limitation only |
| G5 | **Unified ablation table** (M3-02) | Reviewers will ask which module matters | Calibration, guard, conformal sets, OFFER_WORDS, CRC on/off × 3 devices, same seeds |
| G6 | **eWPM user-model sensitivity on all devices** | eWPM depends on assumed costs | Fallback 10 / 20 / 40 chars/min, selection time × 0.5 / 2, `p_miss_unflagged` 0 / 0.05 / 0.2; report whether the ranking of policies changes |
| G7 | **Repeated fit/test splits for B2T and EMG trust** | One split each | 20–50 random day-stratified (B2T) / participant-stratified (EMG) splits |
| G8 | **More MEG test sentences** | 17 unique sentences | k-fold by sentence hash (or by sentence family) over the 224 sentences |
| G9 | **Remove the 64 Tatoeba-overlap B2T cue sentences from the LM** | Possible small leak | Rebuild the char LM / unigram without them; rerun R8–R12 |
| G10 | **Related-work source pages** | Closest work has no source page | Ingest Huang 2025, Kim 2025, Cai 2024, Ernez 2023, Damri 2026, RAS (check formula), Guo 2017, Geifman 2017 |
| G11 | **Spec conformance result** | Supports contribution 1 | Cite the conformance suite (parallel task) for the three adapters |
| G12 | **Trust-layer runtime per decision** | Real-time claim | Measure fit and decide time per sentence on CPU (only the ledger cost is measured) |
| G13 | **Figure scripts** | Reproducibility | `papers/paper1/figures/make_figures.py` reading the experiment JSON files (section 11) |
| G14 | **User study** (ext) | eWPM is simulated | Future work. Needs ethics approval and volunteers (gaze-typing users) |
| G15 | **arXiv endorsement** (ext) | First-time submitter in cs / q-bio may need it | User owns it (M3-07) |

## 11. Reproducibility plan

Principle: every table and figure is generated by a script from committed JSON results. Raw data stay outside the repo; each dataset has a fetch note with SHA-256 in [references/README.md](../../references/README.md).

| artefact | regenerate with | inputs (outside repo) | committed results |
|---|---|---|---|
| T1, T4 (MEG rows), R2–R5 | `tools/data/preprocess_spanishbcbl.py`; `experiments/2026-11-11-m1-09-async-full/queue.ps1` (configs `config-r4a-full-medium.json`, `config-r4b-full-medium.json`); `analysis/analyse.py` | SpanishBCBL raw + cache (`C:\Users\zhang\bci-data\...`) | `experiments/2026-11-11-m1-09-async-full/results/`, `analysis/analysis.json` |
| T3 / T5 / T6 / T7 MEG rows, R6, R7, R19 | `experiments/2026-11-11-g1-async-meg-trust/run.py` + `config.json` (+ `--streams sync` for the secondary row), `tables.py` | M1-09 and M1-15 streams, M1-09 control log-probs | `experiments/2026-11-11-g1-async-meg-trust/results/` |
| T5 MEG null rows, R7 | `experiments/2026-11-08-m2-real-keystroke/run.py` + `config.json` | cache | `results/tables.md` |
| T3 / T5 B2T rows, F4, R8–R12 | `python -I experiments/2026-11-10-b2t25-trust/run.py` + `config.json` | `t15_copyTask.pkl` (SHA-256 in references) + CMUdict + Tatoeba LM | `results/trust.json`, `tables.md` |
| T3 / T5 EMG rows, R13–R16 | `experiments/2026-11-11-emg-toronto/prep.py` → `train.py` (`launch.ps1`) → `trust.py` + `config.json` | Toronto zip (SHA-256 in references) | `results/decoder.json`, `trust.json` |
| T6, F6, R17–R19 | `experiments/2026-11-11-m2-13-conformal/run.py` + `config.json` | items from B2T and MEG runs | `results/items-*.json`, `splits.json` |
| T7, F7, R20–R22 | `experiments/2026-11-11-m2-16-online-recal/run.py` + `emg_items.py` + `config.json` | items | `results/online.json`, `items-emg-*.json` |
| R23 audit | `experiments/2026-11-11-m2-09-provenance/run.py`; `python -m fidetype.trust.provenance verify|report` | B2T items | `results/summary.json`, `ledger-hash-head.json`, `audit-report.md` |
| R25–R26 (appendix) | `experiments/2026-11-08-beam-retune/run.py`, `2026-11-08-m2-offer-words`, `2026-11-08-m2-trust-sim/run.py` | Tatoeba corpora | each `results/` |
| F1–F7 | **to write:** `papers/paper1/figures/make_figures.py` (matplotlib, reads only committed JSON) | none | `papers/paper1/figures/*.pdf` (our own figures; may be committed) |

Release checklist: tag the commit used for the paper (`paper1-v1`); pin the environment (`uv.lock`, `pyproject.toml`); record hardware (AMD RX 7800 XT, ROCm) and run times; state seeds; publish the NTS streams of the B2T and EMG runs only where the source licence allows (B2T CC0, Toronto CC BY with attribution); never publish SpanishBCBL-derived weights for commercial use.

## 12. Target venues

| venue | fit | note |
|---|---|---|
| **arXiv** (cs.HC or cs.LG, cross-list q-bio.NC / eess.SP) | First. Fast, open, sets priority for the spec and the trust layer | Endorsement may be needed: **externally_blocked**, user owns it (M3-07) |
| **Journal of Neural Engineering** | Strong. BCI-engineering readership; accepts methods on public data across modalities | Recommended primary journal; slower review |
| **IEEE TNSRE** | Strong. Assistive communication and rehabilitation; eWPM vs gaze typing is on topic | Good alternative to JNE; needs clinical framing |
| **NeurIPS Datasets & Benchmarks** | Medium–strong if framed as a benchmark (NTS + harness + controls + 3 datasets) | Needs P13-style public benchmark release and seeds (G2, G7) |
| **NeurIPS / ICLR workshops** (e.g. "Data on the Brain and Mind", where Huang et al. 2025 appeared) | Good for early feedback; non-archival | Can run in parallel with arXiv |
| **COPA (Conformal and Probabilistic Prediction)** | Good for the online drift-robust risk-control part alone | Narrow audience for the spec |
| **CHI** | Weak now: CHI expects a user study | Revisit after G14 (live users) |
| **JOSS** | Good for the `fidetype` software itself | Complementary short paper; not the science claim |

Recommendation: arXiv preprint, then JNE (or TNSRE), with a workshop version in parallel. Re-assess NeurIPS D&B once the benchmark hub (P13) exists.
