---
title: North star — a BCI that teaches itself and never puts words in your mouth
type: question
tags: [planning, north-star, frontier, self-improving, online-learning, conformal, risk-control, hallucination, llm, cross-modality, emg, implant, roadmap]
sources: [adaptive-conformal-inference, conformal-risk-control, brain-to-text-25-copytask, brain2qwerty-v2, continual-calibration, conformal-gating-mi-bci, corteg-eeg-to-ecog]
updated: 2026-11-22
---

# North star (2026-11-15)

**Question asked (user, 2026-11-15):** "Stop attaching this project to an existing project. Find a new frontier that does not exist in BCI yet. Think big, outside the boundaries of what is possible, and go that route." The user also said that "OpenTelemetry" meant *a big project that many people use*, not *the same subject as OpenTelemetry*.

**Answer in one line:** we build **a BCI that reads language from any body signal, teaches itself from daily use, and provably never puts words in the user's mouth.**

**Roadmap:** phase [P15 Frontier](roadmap-standard.md#p15-frontier-added-2026-11-15-leads) leads from 2026-11-15. P1–P14 stay as they are. **Later: [P16 write side](roadmap-standard.md#p16-write-side-emotion-and-memory-exploration-added-2026-11-15-later)** (emotion and memory, exploration; after the P15 core work). **Diagram:** `11-roadmap-standard` on [the diagram page](../diagrams/index.html#s11).

## The moonshot
A person puts on **any sensor**: an implant, a wristband or a cap. Within **minutes**, they communicate at **conversation speed**. The system **gets better every day** from normal use. It **provably never says what they did not mean**.

Today no system does any one of these three things well. Each part below is a research step toward it.

| Part of the moonshot | What it needs | Pillar |
|---|---|---|
| "provably never says what they did not mean" | A stated error bound that stays valid while the system changes | F1, F2 |
| "gets better every day" | The decoder learns from the user's accept / reject / correction actions | F1 |
| "conversation speed" | A language model that fills gaps, but only with text that the signal supports | F2 |
| "any sensor, within minutes" | One shared output space across body signals, so a new sensor or a new user needs little data | F3 |

## Why this is new
Two studies on 2026-11-15 (local scratch notes, not committed) checked the prior art and our feasibility. The prior-art study read abstracts, proceedings pages and some secondary summaries (about 30 searches per direction). **It did not read full papers.** A "not found" result means "not found in these searches", not "does not exist".

> **Rule:** in public (README, post, paper) use only the safe wordings in [Verdicts of the literature check](#verdicts-of-the-literature-check-p15-10-2026-11-15) below. The check is [P15-10](novelty-check-2026-11.md) (done 2026-11-15).

### What the sources say (abstract level)
**F1, learning from feedback with a guarantee:**
- [CORP](https://arxiv.org/abs/2311.03611) (NeurIPS 2023) uses language-model-corrected outputs as pseudo-labels to update an intracortical handwriting decoder for 403 days (one participant). It states no error bound.
- [DietCORP](https://arxiv.org/abs/2507.02800) (NeurIPS 2025) does the same for speech and updates only one layer. It states no error bound.
- [ALIGN](https://arxiv.org/abs/2603.18299) (2026) warns that pseudo-label adaptation can compound its own errors when the first error rate is high.
- Online conformal methods ([adaptive conformal inference](../sources/adaptive-conformal-inference.md), rolling risk control, [conformal risk control](../concepts/conformal-risk-control.md)) keep a long-run bound for any sequence. They treat the model as given. Newer work gives coverage with bandit (shown-only) feedback, for example [OCP-Unlock+](https://arxiv.org/abs/2604.17984) (ICLR 2026). It is not applied to BCI.
- A 2026 preprint on [continual calibration](https://www.alphaxiv.org/abs/2604.23987) reports that coverage can fail before accuracy during repeated LLM fine-tuning (secondary summary only).
- Conformal methods in BCI so far are static: offline split conformal or selective prediction, for example [geometry-aware conformal motor decoding](https://proceedings.mlr.press/v329/bonini26a.html) (COPA 2026).

**F2, faithful language-model decoding:**
- [Jo et al. 2024](https://arxiv.org/abs/2405.06459) show that EEG-to-text models score the same or better on pure noise.
- BIT-LLM (ICML 2026, secondary summary only) tests whether an fMRI-to-text model uses the signal by removing or scrambling it. This is an offline evaluation, not a run-time check.
- [Brain-to-Text '24 lessons](https://arxiv.org/abs/2412.17227): the top pipelines rescore with LLMs. The competitions score accuracy only.
- Brain2Qwerty v2 adds an LLM on MEG and gets better WER but worse CER ([NeuroLLM](../concepts/neuro-llm.md), [v2](../sources/brain2qwerty-v2.md)).
- Conformal factuality and abstention exist for text LLMs, for example [conformal abstention](https://arxiv.org/abs/2405.01563). None was found for brain-decoded text.

**F3, one language model across body signals:**
- [NDT3](https://www.biorxiv.org/content/10.1101/2025.02.02.634313) (NeurIPS 2025): intracortical motor, many subjects. Its authors doubt that scale alone fixes sensor variability.
- [BIT](https://arxiv.org/abs/2511.21740) (2025–2026): cross-species intracortical speech with an audio LLM. Implant only.
- [BrainOmni](https://arxiv.org/abs/2505.18185) (NeurIPS 2025): EEG + MEG. [iBrain](https://arxiv.org/abs/2609.06960) (2026): iEEG + spikes. [NeuGPT](https://arxiv.org/abs/2410.20916) (2024): framed as six brain modalities to text, low quality, no cross-modality transfer result.
  > **Contradiction:** the NeuGPT full text uses only MEG (MEG-MASC) for brain-to-text ([novelty check](novelty-check-2026-11.md#c3-f3-cross-body-model)). The abstract-level line above is kept for the record.
- Meta's [generic neuromotor interface](https://doi.org/10.1038/s41586-025-09255-w) (Nature 2025) and [emg2qwerty](../entities/emg2qwerty.md): wrist EMG only. [Inoue et al.](https://arxiv.org/abs/2506.13835) (Interspeech 2025): EEG + EMG, word classes, no implant (secondary summary only).

### The gaps found
| Pillar | Gap in the prior art found | Novelty (study rating) |
|---|---|---|
| **F1** | Decoder self-improvement from feedback exists. Online risk control exists. **No BCI work found joins them**: a decoder that learns from user feedback while a stated error bound stays valid through each update | **High** |
| **F2** | Faithfulness is tested only offline. **No run-time grounding check** of LLM text against the neural evidence, and **no hallucination-rate guarantee**, was found for brain-decoded text. No standard hallucination benchmark | **Medium-high** (high for the guarantee; low for "semantic decoding with LLMs") |
| **F3** | No model found joins implant + EMG + MEG/EEG for text. **No transfer to a new modality** for text is reported | **High on paper, medium in practice** (fast trend, compute, NC data, a null result is likely for MEG/EEG) |

### Verdicts of the literature check (P15-10, 2026-11-15)
The focused check is in [novelty check 2026-11](novelty-check-2026-11.md). It read the full text of the closest papers. It changed two of the three gap statements above.

| Pillar | Verdict | Closest works | Safe public wording |
|---|---|---|---|
| **F1** | Holds with narrower wording | CORP, Card 2024 (learn from use, no bound); [ACI](../sources/adaptive-conformal-inference.md) and [continual calibration](../sources/continual-calibration.md) (bound through model updates, not BCI) | "To our knowledge (literature check of 2026-11-15), no published BCI study updates its decoder from user feedback and reports a stated error bound — for example a long-run limit on the wrong-commit rate — that stays valid across those updates. We use known online conformal methods (Gibbs & Candès 2021) for the bound; what is new is applying them, with an update gate, to a self-improving BCI." |
| **F2** | Holds with narrower wording | BIT-LLM, SemKey (offline faithfulness tests); Probabilistic Co-Control 2026 (calibration, no bound); [conformal gating](../sources/conformal-gating-mi-bci.md) (run-time conformal abstention for closed-set EEG commands) | "To our knowledge (literature check of 2026-11-15), no published brain-to-text system checks language-model output against the neural evidence at run time with a stated, distribution-free bound on the rate of unsupported (hallucinated) words that it commits. Earlier work tests faithfulness offline (noise or shuffled inputs) or bounds errors for closed-set BCI commands." |
| **F3** | Part 1 holds; part 2 ("transfer to a new modality") **false as written** | [CORTEG](../sources/corteg-eeg-to-ecog.md) (EEG → ECoG / sEEG transfer, no text); NOBEL, BrainOmni (non-invasive unions, no held-out modality) | "To our knowledge (literature check of 2026-11-15), no published model is trained jointly on implanted, EMG and MEG/EEG recordings for text output, and no published study reports text decoding from a recording modality that the model did not see in training. Cross-modality transfer exists for other tasks (for example scalp EEG to ECoG, CORTEG 2026)." |

Never say in public: "first conformal BCI", "first guarantee for an adaptive model", "first hallucination control for BCIs", "first cross-modality transfer".

> **Our take:** F1 is the strongest lead. It is new as a composition, it needs no new hardware, it fits our CC0 data, and it builds directly on code that we already have (online re-calibration in [M2-16](m2-16-online-recal-result.md), [per-session risk control](per-session-risk-control.md), the [provenance ledger](../concepts/provenance-ledger.md)). The claim must be "first BCI application with a decoder-update gate", not "a new conformal theorem", unless we prove one. F2 extends the same guarantee engine to LLM output. F3 is the largest idea and the riskiest. We start it small, on one GPU, with strong controls.

## Frontier result write-ups (P15-12, 2026-11-18)
One write-up per experiment line. Each page gives the question, the pre-registration and its commit, the design, every pre-registered verdict with numbers, the negative results, the library changes, the limits and the open gaps.

| write-up | pillar | steps | main pre-registered verdicts | status |
|---|---|---|---|---|
| [E2 self-teaching](frontier-e2-self-teaching.md) | F1 | P15-01, P15-02, P15-03a, P15-13, P15-23, P15-24 | P15-01 S4 pass, **S5 fail**; P15-02 S5 pass; P15-03a **H2, H3 fail**; P15-13 G1-G6 pass; P15-24 R1-R7 pass | P15-24 done; GPU runs (P15-03) not run |
| [F1 online guarantees](frontier-f1-online-guarantees.md) | F1 | P15-04, G3 review + fixes (P15-17), P5-11 | R1, R3-R5 pass; review "sound with fixes" (H1 fixed) | done |
| [E3 hallucination](frontier-e3-hallucination.md) | F2 | P15-05, P15-06, P15-14, P15-07, P15-15, M4-13 reruns | **S4 fails on M4-12 and M4-13**; bound H1-H4 pass on T15; T12 certified by V-single; M4-13 B1 first pass of all tracks (protocol 0.2) | done; P15-16 open |
| [Decoder quality](frontier-decoder-quality.md) | base | M4-12, M4-13 | M4-12 "close" rule **fail** (PER 0.2574); M4-13 pass (0.1210) | done |
| [Safe WPM](frontier-safe-wpm.md) | value | P14-05, P14-23, P5-23, P5-24, P14-28, P5-27, P5-28, P15-22, P15-26, P15-29, P11-17 | learned beats current (2.64); prefix beats sentence (4.87, v0.2); single beats stream (2.34, v0.2); hybrid beats single (4.89, v0.2, WPM gain not robust; first right word 2.7 s vs 14.0 s); P15-22 LLM + learned 4.91 [4.25, 5.57] v0.1 with one calibration draw (gap 53 closed); [P15-26](../../experiments/2026-11-19-p15-26-replication/results.md): 4 new T15 calibration draws 5.23–6.00; **[P15-29](../../experiments/2026-11-20-p15-29-calibration-ci/results.md): with calibration variation 5.18 [0.00, 6.99], above 4.02 on average only** | T15 **not reliably** above gaze typing: the calibration-inclusive interval contains 4.02 (2 / 40 draws above alpha earn 0; the single-draw CI 4.91 [4.25, 5.57] does not include calibration variation; gap 132, P15-34); not above gaze typing on T12 (2.37 [1.34, 3.62] vs 4.11; 1.05 [0.00, 3.18] with calibration draws; decoder too weak, 35 / 400 top-1 exact); EMG P11-14 6.80 [4.49, 9.63] with one calibration draw, **5.00 [0.00, 9.55] once the calibration draw is counted** ([P11-17](../../experiments/2026-11-21-p11-17-emg-calibration-ci/results.md)): above no-BCI 3.09 on average, not reliably (gaps 158, 159); v0.2 proposed, not adopted |
| [Personalisation and drift](frontier-personalisation-drift.md) | F1 | P5-01, P5-09, P5-10, P5-11 | P5-01 all pass; P5-09 **S3 fail** (small-shift cost) | done |
| E1 cross-body (F3) | F3 | P15-08 | E1a done 2026-11-19 ([results](../../experiments/2026-11-19-p15-08-e1-cross-body/results.md)) | **null at minutes scale**: H1 fails (EMG trunk does not beat text-only at 3-30 min), C2 fails (no arm reads the signal with ≤ 100 min); at full data the EMG trunk is the most stable arm (descriptive). P15-36 ([results](../../experiments/2026-11-22-p15-36-budget-matched/results.md)): budget-matched recipe, V1 and C2 pass on 2 seeds, H1-H4 each partial. P15-41 ([results](../../experiments/2026-11-22-p15-41-more-seeds/results.md); 5 seeds of F-R20, arms E and T): H1 fails. E vs T at 10 min d = 0.038 [−0.004, 0.081], at 30 min −0.002 [−0.034, 0.031]. The 3-min win (0.095 [0.066, 0.124]) has no valid control. The label-deranged control at 10 min fails on all 3 new seeds (seed 4: deranged = normal). So at minutes scale there is no valid evidence that EMG pretraining beats text pretraining (next: gap 194 = P15-43) |

## The three pillars and their first experiments
The feasibility study numbers the experiments by direction, not by rank: **E2 is the F1 experiment, E3 is the F2 experiment, E1 is the F3 experiment.** We keep these names so the notes and the experiment folders match.

| Pillar | Rank | First experiment | Cost (est.) | Can start |
|---|---|---|---|---|
| F1 Safe self-improving BCI | 1 (lead) | E2 | 3–8 GPU-h; CPU pilot now | CPU pilot now (planned folder `experiments/2026-11-16-f1-e2-selfimprove-pilot/`) |
| F2 Faithful LLM decoding | 2 | E3 | 0 GPU-h (CPU, 1.7–4B model) to 1–3 GPU-h | Now, on CPU, after a local LLM install |
| F3 Cross-body language model | 3 | E1 | 20–45 GPU-h + a few CPU-h | Caches on CPU now; GPU after about 2026-11-19 |

The GPU is busy until about 2026-11-18 / 19 (M4-13, then P11-01). Rule: one GPU job at a time.

The success criteria below are **proposed**. Each experiment freezes them in its own `plan.md` and commits it **before** the runs, as P14-03 did.

### F1: safe self-improving BCI (E2)
**Goal:** the decoder learns from accept / reject / correction feedback, and the stated wrong-commit bound stays valid through every update.

**Method (replay in time order, T12, 24 sessions over 4 months, CC0):**
1. Train the base decoder on the first K sessions (K = 4–8).
2. For each later trial: decoder → n-best → trust policy → COMMIT / OFFER / WITHHOLD.
3. A simulated user knows the intended text. OFFER: accept if the truth is in the list, else reject (and retype with probability p_retype). Wrong COMMIT: the user corrects it with probability q_notice, else it is a **silent error**. Noise: accept a near miss with probability p_sloppy.
4. Learn from feedback between sessions: accepted and retyped items become labels; rejects are a negative signal only. Update a day-specific input layer first, then the last layers.
5. Keep the guarantee: each update gets a new `config_id`; online risk control (`aci`) runs across updates; a per-session e-process monitor raises an alarm; a new decoder goes live only if it passes a block test on recent feedback that it did not train on (champion / challenger); the commit gate and the uniform / shuffled null controls run again after each update.

**Arms:** frozen decoder; feedback-only adaptation; oracle recalibration (all labels); self-training on commits only (negative control: shows confirmation bias); calibration block only.

**Controls:** frozen arm; oracle arm (upper bound); self-training arm; null inputs after each update; 2 seeds; 3 simulated-user settings.

**Metrics per session:** PER / WER, commit rate, wrong-commit rate with Clopper-Pearson intervals, silent-error rate, eWPM, labels used.

**Proposed success criteria:**
- The feedback-only arm has a lower PER than the frozen arm on the later sessions, by more than the seed spread.
- The long-run wrong-commit rate of every deployed configuration stays at or below α plus the stated finite-sample slack of `aci`.
- No deployed update fails the null controls.
- The self-training arm is reported, even if it looks good.
- Silent errors and the share of items with known truth are reported separately.

**Cost:** 3–8 GPU-h; the CPU pilot (frozen trunk, linear input layer, small subset) runs now.

**Blockers:** no decoder-update loop code yet; no "re-calibrate after update" hook in `TrustGuard` / `OnlineTrustPolicy`; `t15_personalUse.pkl` (real user ratings, to set the simulated accept rate) is not local.

**Follow-ups:** online risk control with **bandit feedback** (we see the truth only for what we showed); a formal statement of what the guarantee covers (both done in P15-04: [F1 guarantee scope](f1-guarantee-scope.md)); T15 (45 sessions over 20 months) as the second dataset.

**CPU pilot result (2026-11-16, [P15-01](../../experiments/2026-11-16-f1-e2-selfimprove-pilot/results.md)):** feedback-only adaptation lowers PER from 0.686 (frozen) to 0.470 over 16 T12 days; the wrong-commit bound holds through every daily update (also under bad updates); self-training collapses; but uniform null inputs commit in every arm (no evidence gate yet) and 88-100 % of commits are wrong, so this is a working harness, not F1 evidence.

**M4-13 rerun (2026-11-18, [P15-03a](../../experiments/2026-11-17-p15-03-f1-m4-13/results.md), [summary](m4-13-trust-reruns.md)):** with real decoders of different quality, the champion / challenger gate accepts M4-13 and keeps the wrong-commit bound (0.0055-0.0082) in all 4 runs. It refuses the worse M4-12 and a time-reversed decoder with an oracle user, but accepts both with the feedback-r0.3 user (H2, H3 fail). A feedback-aware non-inferiority test is open (P15-13).

### F2: faithful language-model decoding (E3)
**Goal:** an LLM improves the decoded text, and a run-time check makes sure that it adds nothing that the neural evidence does not support, with a risk-controlled bound on hallucinated commits.

**Method (T15 published logits + our M4-12 logits; T12 v2):**
1. Arms: n-gram LM (current); + LLM rescoring of the n-best; + LLM rewrite limited to the n-best lattice.
2. Grounding checks: (a) the CTC forced-alignment log-prob of the final text under the neural emissions must not fall below the top-1's by more than τ; (b) the existing guard signals (`lm_acoustic_gap`, `low_evidence_frac`); (c) the trust gate commits only when calibrated.
3. Bound: calibrate τ and the commit threshold with CRC / LTT on a "fluent but wrong" loss.

**Controls:** uniform and frame-shuffled null inputs; **swapped-signal** input (the neural data of another sentence); text-only LLM baseline; the published T15 logits as a strong reference decoder.

**Metrics:** WER, sentence accuracy, wrong-commit rate, **fluent-wrong rate** (committed sentences that are wrong but have a high LM score), commits on null and swapped inputs.

**Proposed success criteria:**
- The LLM arm improves WER or sentence accuracy over the n-gram arm at the same α.
- Its held-out wrong-commit rate stays at or below α at the stated confidence.
- Null and swapped-signal commits stay at the P14-03 control level (about 0 per 300).
- Its fluent-wrong rate is not higher than the n-gram arm's.

**Cost:** CPU only with a 1.7–4B model (hours of CPU), or under 1 GPU-h per arm with an 8B model.

**Blockers:** no local LLM stack (no `transformers`, no llama.cpp); a 1–10 GB model download; LLM licences differ (prefer Apache-2.0 or MIT).

**Result (2026-11-16, T15 + T12, [P15-05](../../experiments/2026-11-16-f2-e3-llm-grounding/results.md)):** on T15, LLM rescoring lowers WER 0.3985 -> 0.3831 under the bound (wrong-commit 0.0029, null 0/300), but fluent-wrong commits are 2 vs 0 (S4 fails). The T12 replication gives no significant WER gain (0.3885 -> 0.3851, CI95 [-0.0086, +0.0021]) with the bound, controls and fluent-wrong count held (4 vs 4). On both sets the grounding check stops all swapped-signal commits (ungrounded up to 28 of 701 and 25 of 400) but does not block fluent text on the true signal. E3 does not pass its pre-registered criteria (next: P15-06).

**M4-13 rerun (2026-11-18, [F2 reruns](../../experiments/2026-11-17-f2-m4-13/results.md), [summary](m4-13-trust-reruns.md)):** on T15, LLM rescoring + grounding lowers WER 0.1827 -> 0.1617 with 154 commits (12 wrong); S4 fails again (fluent-wrong 6 vs 2). The fluent-wrong bound now commits 36 sentences (34 right; fluent-wrong 1 / 701) and is the first entry that passes all tracks of the hallucination benchmark 0.2. On T12 the pre-registered V-single variant gives a certified bound (closes P15-14), but only 3 commits.

**Follow-ups:** a **public hallucination benchmark** with null / scrambled / swapped-signal tracks as standard tracks (it joins the P6 leaderboard and the P13 hub; it does not replace them).

### F3: cross-body language model (E1)
**Goal:** one shared output space (characters, plus phonemes for speech implants) across implant and EMG first, later MEG/EEG. A new modality or a new user then needs only minutes of data.

**Method (Willett handwriting, CC0, native character target):**
1. Data fractions: 10 / 25 / 50 / 100 % of the training sentences. Held out: the last block of each session.
2. Arms (same architecture, a new input stem each time): random init; trunk pretrained on **text only**; trunk pretrained on **emg2qwerty** keys (research only); trunk pretrained on **KT-sEMG** (CC BY, the licence-clean version); optional: trunk pretrained on T15 with a character head.
3. Readout: greedy CER and CER with the same character LM; 2 seeds.

**Controls:** the text-only pretraining arm and the same-LM rule. Without them a gain can come from English character statistics, not from the signal.

**Proposed success criterion (from the study):** an EMG-pretrained arm beats the text-only arm by more than the seed spread at 25 % data or less.

**Cost:** about 20–45 GPU-h (1–2 GPU days) + a few CPU-h for caches; under 20 GB of new cache.

**Blockers:** the GPU queue; the emg2qwerty arm needs the P11-01 weights; three implant datasets are three different people with three tasks.

**Licence tracks:** a **clean track** (CC0 + CC BY: T15, T12, Willett, KT-sEMG, Toronto, about 98 h) and a **research-only track** (adds emg2qwerty, CC BY-NC-SA, and SpanishBCBL, CC BY-NC). Each checkpoint carries its data licences. Clean-track weights can ship; research-track weights never ship.

**Follow-ups:** the reverse direction (implant → EMG, E1b); a public **"new modality / new user with minutes of data"** benchmark; a joint model on one GPU before any larger scale; MEG only later (Spanish, low sentence diversity, weak decoder, NC).

## Honest risks
| Risk | Effect | What we do |
|---|---|---|
| **Weak base decoders** (our T15 PER 0.257 vs published 0.101; T12 7.75 % right sentences) | A gain may come from fixing the decoder, not from the new method | Use the published T15 logits as a strong reference; report frozen and oracle arms |
| **Silent errors** (a wrong commit that the user does not correct) | Outside every guarantee that uses feedback | Report them separately; simulate several q_notice values; never claim they are covered |
| **Guarantee scope** | Only long-run (`aci`) and alarm (e-process) bounds hold across updates. A per-session finite-sample bound needs a fresh labelled block after each update | State the scope on every result; no "per-session" claim without a fresh block |
| **Selected labels** (the decoder trains on what the trust layer chose to show) | Biased updates; runaway errors (ALIGN's warning) | Champion / challenger gate on held-back feedback; self-training arm as a negative control |
| **Licences** (emg2qwerty NC-SA, SpanishBCBL NC) | Research weights cannot ship | Separate clean and research tracks; licence tags on every checkpoint |
| **Compute** (one RX 7800 XT, busy until about 2026-11-19) | Foundation-scale pretraining is out of reach | One-GPU scale first; CPU work while the GPU trains |
| **Mixed person and modality effects** (T5, T12, T15 are different people and tasks) | "Cross-modality" gains may be "cross-person" gains | Name the confound; add within-person controls where data allows |
| **Fast-moving field** (bandit conformal, continual calibration, BIT-LLM in 2026) | Others may publish first | Cite them; claim the composition and the BCI evidence; literature check before any public claim |
| **Null results** (especially F3 on MEG/EEG) | Months with no positive result | Pre-registered criteria; publish negative results as write-ups |

## How existing work maps in
| Existing work | Role under the north star |
|---|---|
| Trust layer (CRC, LTT, online `aci`, e-process monitor, commit gate, null controls, drop-in wrapper [P14-03](roadmap-standard.md#p14-03-trust-layer-as-a-drop-in-wrapper)) | The **guarantee engine** for F1 and F2 |
| [Provenance ledger](../concepts/provenance-ledger.md) | Links each correction to its decision: the feedback log for F1 |
| Decoders (T15 M4-12 / M4-13, T12 v2, P11-01 EMG, MEG ConvCTC), [adapters](../concepts/ctc-logits-adapter.md), dataset replay | The **base** for F3 and the test decoders for F1 / F2 |
| NTS spec, SDKs, collector, conformance (P1–P3, P7) | Internal plumbing and the way results flow to other tools. Kept, lower priority |
| Live demo (P14-06) | Shows F1 / F2 progress: a decoder that improves across sessions while the guarantee line stays |
| Benchmark (P6, P13) | Gets the F2 hallucination tracks and the F3 "new modality, minutes of data" track |

## Related pages
- [Roadmap: P15 Frontier](roadmap-standard.md#p15-frontier-added-2026-11-15-leads)
- [Direction decision](direction-decision.md#north-star-decision-2026-11-15-frontier-route)
- [Overview](../overview.md)
- [Who uses Fidetype](who-uses-fidetype.md)
- [M2-16 online re-calibration](m2-16-online-recal-result.md), [per-session risk control](per-session-risk-control.md)
- [Public datasets](public-datasets.md), [Willett handwriting](../entities/willett-handwriting-2021.md), [Brain-to-Text '25](../entities/brain-to-text-25.md), [KT-sEMG](../entities/kt-semg-dataset.md), [emg2qwerty](../entities/emg2qwerty.md)
