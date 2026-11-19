---
title: Overview — non-invasive brain-to-text, where things stand
type: overview
tags: [synthesis, north-star, frontier]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code, brain-to-text-25-copytask]
updated: 2026-11-19
---

# Overview

*Synthesis based on 3 sources: [v1](sources/brain2qwerty-v1.md), [v2](sources/brain2qwerty-v2.md) and the [code](sources/brain2qwerty-code.md). It will be revised as more sources are ingested.*

## North star (2026-11-15)
The project now aims at a frontier that we did not find in BCI work: **a BCI that reads language from any body signal, teaches itself from daily use, and provably never puts words in the user's mouth** ([north star](questions/north-star.md)). The moonshot: anyone puts on any sensor (implant, wristband, cap) and communicates at conversation speed within minutes; it improves every day; it provably never says what they did not mean.

| Pillar | Content | Novelty (prior-art study, abstract level) |
|---|---|---|
| **F1** (lead) | Safe self-improving BCI: the decoder learns from accept / reject / correction feedback while a stated error bound stays valid through every update | High |
| **F2** | Faithful LLM decoding: a run-time grounding check against the neural evidence, a risk-controlled hallucination bound, a public hallucination benchmark | Medium-high |
| **F3** | Cross-body language model: one output space across implant and EMG (later MEG/EEG); a new modality or a new user with minutes of data | High on paper, medium in practice |

The first experiments (E2 for F1, E3 for F2, E1 for F3) are in roadmap phase [P15](questions/roadmap-standard.md#p15-frontier-added-2026-11-15-leads). The novelty ratings come from abstract-level searches; the focused literature check ([P15-10](questions/novelty-check-2026-11.md)) narrowed the wordings.

**Frontier results so far (2026-11-18, write-ups of [P15-12](questions/north-star.md#frontier-result-write-ups-p15-12-2026-11-18)):**
- [E2 self-teaching (F1)](questions/frontier-e2-self-teaching.md): feedback lowers PER in a T12 replay, and the wrong-commit bound holds through every update. The update gate first failed with partial feedback (P15-03a H2, H3); the default-deny gate fixed it (P15-13, G1-G6 pass). The GPU runs have not run.
- [F1 online guarantees](questions/frontier-f1-online-guarantees.md): the `aci` bound holds with shown-only feedback; a new IPW audit has 0 / 200 violations; an independent review found one high issue, now fixed.
- [E3 hallucination (F2)](questions/frontier-e3-hallucination.md): E3 fails its pre-registered rule (S4, fluent-wrong commits) on both T15 decoders. Grounding stops every swapped-signal commit. A certified fluent-wrong bound exists on T15 and T12. The M4-13 bound guard is the first entry that passes all hallucination-benchmark tracks.
- [Decoder quality](questions/frontier-decoder-quality.md): M4-13 (PER 0.1210) made the guarantees useful on T15 without a method change.
- [Safe WPM](questions/frontier-safe-wpm.md): since P15-22 (2026-11-19), LLM rescoring plus a learned commit score gives 4.91 [4.25, 5.57] under the adopted v0.1, certified and pre-registered. This is above gaze typing (4.02), and the lower end of the interval is also above it (earlier best 2.64). One participant, one split, one seed, offline replay, not a user study; replication is gap 93 (P15-26). Under the proposed, not adopted v0.2, a hybrid guard (P5-28) shows the first right word about 5 times sooner (2.7 s vs 14.0 s) at 4.89; its WPM gain is not robust.
- [Personalisation and drift](questions/frontier-personalisation-drift.md): drift-triggered re-calibration halves the label cost.
- E1 (F3, P15-08) is running on the GPU. It has no result yet. Its EMG base decoder (P11-01) gives 15.09 % CER personalised and 53.52 % generic on emg2qwerty, with no LM ([results](../experiments/2026-11-16-p11-01-emg-decoder/results.md)).

> **Our take:** the findings below (trust layer, guarantees, decoders, datasets) are the foundation of the north star. The trust layer becomes the guarantee engine for F1 and F2. The decoders and the datasets are the base for F3. The NTS spec and SDKs stay as internal plumbing.

## The state of the art (non-invasive, typing)
Meta's Brain2Qwerty decodes what healthy people type from [MEG](concepts/meg.md):
- **v1 (2026)**, keystroke-locked: **29% CER**.
- **v2 (2026)**, continuous decoding with a [CTC](concepts/ctc.md) encoder feeding a [NeuroLLM](concepts/neuro-llm.md): **39% WER**. The best subject reaches 22% WER, and 28% of their sentences are word-perfect.

For comparison, invasive implants reach **<2% WER** for typing (Jude et al. 2026), so the gap is still large.

## What we believe so far
1. **MEG beats EEG by more than 2×** on this task ([EEG](concepts/eeg.md) gives 65% CER vs 29%). Modality matters as much as the model.
2. **The signal is motor.** The decoder reads motor-cortex activity from finger movements, and its errors follow the keyboard layout. It decodes the *act of typing*, not thought.
3. **Data is the lever.** Performance is log-linear in recording hours with no plateau, and sentence diversity matters separately from volume ([data scaling](concepts/data-scaling.md)).
4. **Data volume is what makes continuous decoding work.** The async encoder goes from 0.59 to 0.25 CER with 10× more data per subject ([sync vs async](concepts/synchronous-vs-asynchronous-decoding.md)).
5. **LLMs help meaning but can hallucinate.** They give better WER and SemER but worse CER ([error metrics](concepts/error-metrics.md)).
6. **Wearables look plausible.** Halving the sensor count costs about 6 points of WER ([OPM-MEG](concepts/opm-meg.md)).

## What our own experiments show (2026-11-08)
- **With small data, a CTC decoder needs a keystroke hint.** CTC alone learned only a text prior. A keystroke auxiliary loss makes it use the MEG (greedy test CER 0.619, target 0.59) ([decoder M1 results](questions/decoder-m1-results.md)). A beam with a Spanish char LM, tuned on val, lowers it to 0.590; greedy stays at 0.619, and the true sentence is never in the 20-best ([M1-C2](../experiments/2026-11-08-m1c2-beam-lm/results.md)).
- **Sentence context helps a little at this data size (2026-11-10).** With oracle key timing, a Conv + Transformer keystroke decoder reaches test CER 0.577 greedy and 0.488 with the char LM. The per-key logistic regression gives 0.597 / 0.531. The Transformer itself adds only about 0.02 CER; v1 got 0.31 from it. The model overfits the about 200 unique training sentences ([M1-15 r2](questions/decoder-m1-results.md#m1-15-r2-sentence-context-decoder-trained-to-the-val-plateau-2026-11-10)).
- **More data helps the sentence-context decoder (2026-11-10).** On the full cache (19 participants, the same 101 training sentences), test CER is 0.508 greedy and 0.447 with the LM (0.497 / 0.437 on the r2 test instances). A causal version costs nothing. Part of the gain (about 0.013 CER) is template memorisation: 6 of 17 test sentences have a close variant in train. The no-signal floor is about 0.69 CER, not 1.0. All M1-15 runs use oracle key timing, so the async M1 target is still open ([M1-15 full-r1 and r3](questions/m1-15-full-r1-r3-result.md)).
- **More data makes the async decoder reach the v2 number (2026-11-11).** The async ConvCTC with a keystroke aux loss, on all 80 cached blocks with a medium model, gives test CER 0.506 greedy (0.495 over participants) and 0.475 with the LM. v2's async encoder gives 0.59 on SpanishBCBL. Our inputs match v2's async setting (segment from the first key − 0.4 s, no key times). But our training also uses key times as labels, and the test split differs. Async now equals our sync decoder at greedy (−0.002) ([M1-09](questions/m1-09-async-full-result.md)).
- **The trust layer is safe on real MEG, but not yet useful.** It stops all wrong and hallucinated commits. But at key accuracy 0.39, no BCI policy beats gaze typing alone (2.96 vs 3.14 eWPM; with the r2 decoder 3.06 vs 3.14; with the full-cache decoder 3.23 vs 3.15, CI [3.08, 3.40], so parity) ([trust core v0 results](questions/trust-core-v0-results.md#7-per-word-offer-and-partial-correction-2026-11-08)).
- **Each trust decision can carry an auditable provenance record (2026-11-11).** A hash-chained JSON Lines ledger records the stream hash, frame range, decoder, LM, calibration and policy version of every decision, and links user corrections to it. No raw signal is stored. On the B2T '25 replay it traced all 48 (plug-in) and 39 (CRC) wrong commits, at about 0.1 ms per decision ([provenance ledger](concepts/provenance-ledger.md)).

- **A causal decoder loses accuracy mostly in the first 40 ms of lookahead (2026-11-14).** Our own causal GRU-CTC on the [Brain-to-Text '25](sources/brain-to-text-25-copytask.md) T15 data (CC0), val 701 trials: shared model greedy PER 0.6565 at lookahead L = 0, 0.4449 at 40 ms, 0.3687 at 500 ms. A model trained with L = 500 ms gives its phonemes 180 ms *earlier* (median) than a model trained with L = 0. So the declared `latency` is an upper bound on signal use, not the delay the user sees. Compute does not depend on L. The decoder was under-trained (published T15 decoder: PER 0.0954) ([lookahead vs accuracy and latency](questions/lookahead-latency-accuracy.md)).
- **Interim, in progress: the retrained L = 0 decoder is much closer to the published one (M4-12, 2026-11-14).** The dedicated L = 0 model now reaches greedy PER **0.2574** on T15 val (701 trials). Before it was 0.6954; the published decoder gives 0.0954. Through the frozen trust configuration it makes 0 commits and 0 wrong commits (all 701 trials are OFFER; eWPM 5.94 vs gaze 4.02). Source: `experiments/2026-11-14-m4-12-decoder-retrain/results/accuracy.json`. The other lookahead conditions are not retrained yet.

> **Our take:** Usefulness needs a stronger decoder, and every speed claim needs a no-BCI baseline. M4-12 shows that the gap to the published decoder was mostly training, not the causal design. The frozen trust configuration still commits nothing, so the next question is whether it can commit safely on a decoder at this level.

## The big open problems
The north-star pillars add three open problems: keeping an error bound valid while the decoder learns from its own outputs (F1); checking LLM text against the neural evidence at run time (F2); moving to a new sensor or a new person with minutes of data (F3).

1. **Real-time causal decoding**: v2 still waits for the end of the sentence. Our own causal decoder runs on implant data (see above), but not yet on non-invasive data.
2. **Patients with no movement**: going from overt typing to attempted or imagined typing, without labels.
3. **Cross-subject generalisation**: the encoder is the bottleneck.
4. **Hardware**: moving from cryogenic MEG to room-temperature [OPM-MEG](concepts/opm-meg.md).
5. **Data**: only one small public typing-MEG dataset exists ([SpanishBCBL](entities/spanishbcbl-dataset.md)), and the larger one is embargoed ([EnglishBCBL](entities/englishbcbl-dataset.md)). All public non-invasive brain typing data is NC. Commercially clean data with text and timing exists only for implants (CC0, [Brain-to-Text '25](entities/brain-to-text-25.md)) and wrist sEMG typing (CC BY 4.0, [KT-sEMG](entities/kt-semg-dataset.md), [Toronto](entities/toronto-semg-typing-dataset.md)) ([public datasets survey](questions/public-datasets.md)).

> **Our take (2026-11-10):** Wrist sEMG typing is the natural **second testbed modality** after MEG: the most typing data ([emg2qwerty](entities/emg2qwerty.md), 346 h, NC), two CC BY sets, and a consumer device. Brain-to-Text '25 is the licence-clean testbed for the trust layer on real decoder output.

## Project direction
**2026-11-15: new north star.** The user asked for a new frontier instead of a copy of an existing project. P15 Frontier now leads; the paragraphs below are the earlier history and stay for the record ([north star](questions/north-star.md), [decision](questions/direction-decision.md#north-star-decision-2026-11-15-frontier-route)).

On 2026-11-07 we chose **trustworthy neural text entry**. On 2026-11-08 the user named the project **Fidetype** (package `fidetype`). We build a layer that makes text from any neural decoder reliable: it calibrates confidence, abstains or asks when it is not sure, offers n-best choices, guards against LLM hallucination, and works in real time.

On 2026-11-08 the user widened the scope to an OpenTelemetry-level project. Fidetype now aims to be **the vendor-neutral standard and trust layer for neural input**: text or intent decoded from wrist EMG, EEG, MEG/OPM-MEG or implants. NeuralTextStream becomes a modality-agnostic and vocabulary-agnostic spec ([spec v0.1](../spec/neuraltextstream-v0.1.md)), and adapters for every modality are first-class. Research MEG stays the credibility base and the hardest test case for Paper 1. Success is the number of decoders and devices that emit NeuralTextStream. The user accepts a multi-year horizon and the need for outside partners ([scope decision](questions/direction-decision.md#scope-decision-2026-11-08-neural-input-opentelemetry-level)).
- The decision and the evidence: [direction-decision](questions/direction-decision.md).
- The six-layer design and the roadmap: [architecture](questions/architecture.md).
- Project plan: milestones M0–M7, tasks, risks and the working process: [project-plan](questions/project-plan.md).
- **Publications decoupled (2026-11-13).** Paper writing and publishing are a separate track (PUB) with no deadline. Review and publishing run on outside timelines. The research and engineering roadmap never waits on a paper. Research results go to `experiments/` and the wiki first; papers draw on them later. M3 is now "Trust-layer validation (research)" and M4 "Causal / streaming decoder (research)": [project plan, PUB](questions/project-plan.md#pub-publications-no-deadline).
- Open-source path: NeuralTextStream as a vendor-neutral spec, credibility from Paper 1 and benchmarks, a company later. Success means decoders that emit NeuralTextStream, not stars: [open-source playbook](questions/open-source-playbook.md).
- **State of the standard (2026-11-14).** The spec, the runtime and the first generic adapters exist:
  - **NTS 1.0 RC2** ([spec](../spec/nts-1.0-rc2.md), DRAFT for public comment) folds v0.1 and FEP-0001 … FEP-0005 into one document with rule ids. New in RC2: rule TD-12 (no blank candidates) and 1.x headers accepted in all three SDKs. 1.0 Stable needs outside review (externally blocked) ([NTS specification](concepts/nts-spec.md), [FEP process](concepts/fep-process.md), [`trust_decision` event](concepts/trust-decision.md)).
  - **SDKs:** Python, TypeScript and Rust give the same verdicts on all golden vectors. All three are ready to publish, not published. The C core is not started ([roadmap P2](questions/roadmap-standard.md#p2-reference-sdks)).
  - **Collector** (P3, draft FEP-0006): one service with receivers (file, WebSocket, LSL), processors (validate, trust, redact, thin) and exporters ([collector](concepts/collector.md)).
  - **Generic decoder-output adapters** (P4-07, commit bcabf04): the [CTC-logits adapter](concepts/ctc-logits-adapter.md) turns (T, V) CTC scores of any decoder into NTS; the [text n-best adapter](concepts/text-nbest-adapter.md) turns text-only decoder output into a hypothesis-only stream. Our lookahead GRU outputs pass trust-ready (1,402/1,402), and the CTC adapter equals the B2T '25 adapter on 1,718 published trials.
  - **Trust guarantees:** a start-of-session guarantee from [CRC](concepts/conformal-risk-control.md) or [Learn then Test](concepts/learn-then-test.md), and in-session re-calibration with [adaptive conformal inference](concepts/adaptive-conformal-inference.md).
- **Long-term roadmap (2026-11-10).** The user decided on full standardisation at OpenTelemetry scale, built by us. M0–M7 are only v0.1. Eleven phases follow (P1–P11): spec 1.0, SDKs in six languages, a collector, adapters, a product-grade trust layer, a benchmark, conformance, docs and demo, governance, adoption and research. The gap to OpenTelemetry scale is mostly SDKs, adapters and integrations, not the core: [roadmap-standard](questions/roadmap-standard.md).

## Where this project might fit
See [research directions](questions/research-directions.md).
