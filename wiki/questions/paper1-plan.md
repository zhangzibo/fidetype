---
title: Paper 1 plan (M3)
type: question
tags: [paper-1, m3, planning, ewpm, trust, conformal, provenance, cross-device]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain-to-text-25-copytask, toronto-semg-typing, conformal-risk-control, learn-then-test, adaptive-conformal-inference]
updated: 2026-11-11
---

# Paper 1 plan

**Question:** What does Paper 1 claim, which results back it, and what is still missing before submission?

**Draft v0 (2026-11-11):** the first full LaTeX draft is [papers/paper1/draft-v0.pdf](../../papers/paper1/draft-v0.pdf) (23 pages; source in `papers/paper1/latex/`, build notes in [papers/paper1/README.md](../../papers/paper1/README.md)). A guide for the author is [how-to-read-this-draft.md](../../papers/paper1/how-to-read-this-draft.md). It lists every red TODO in the draft and the decisions the user owns (venue, authors, arXiv endorsement, ethics wording). Style lessons from published papers: [style-notes.md](../../papers/paper1/style-notes.md). Data figures come from `papers/paper1/make_figures.py`, which reads only committed result files.

The full outline is in [papers/paper1/outline.md](../../papers/paper1/outline.md). It holds the title options, the abstract draft, the section plan with each table and figure, the related-work map, the limitations, the licence statement, the results inventory and the reproducibility plan.

## Claim in one paragraph
A vendor-neutral stream format ([NeuralTextStream](../../spec/neuraltextstream-v0.1.md)) and a decoder-agnostic trust layer make neural text entry **safer** on three device types. The trust layer has calibration, COMMIT / OFFER / ABSTAIN, [conformal risk control](../concepts/conformal-risk-control.md) with an online version for drift, and a [provenance ledger](../concepts/provenance-ledger.md). The three devices are MEG ([SpanishBCBL](../entities/spanishbcbl-dataset.md)), intracortical speech ([Brain-to-Text '25](../entities/brain-to-text-25.md)) and forearm sEMG ([Toronto](../entities/toronto-semg-typing-dataset.md)). The metrics are eWPM against gaze typing alone, wrong-commit rate and silent-error rate, with shuffled and null-input controls.

## Headline numbers (from the result pages)
| device | always commit → trust: wrong-commit | eWPM trust vs gaze only | page |
|---|---|---|---|
| intracortical (our decoder) | 0.610 → 0.059 | 11.55 vs 4.08 | [B2T '25](b2t25-trust-result.md) |
| intracortical (published gate) | 0.194 → 0.044 | 18.77 vs 4.08 | [B2T '25](b2t25-trust-result.md) |
| sEMG (3 conditions) | 0.54–0.96 → ≤ 0.004 | 8.02 / 4.68 / 4.08 vs 4.27 | [EMG Toronto](emg-toronto-trust-result.md) |
| MEG (async M1-09 streams) | 0.997 → 0 | 3.20 [3.07, 3.36] vs 3.155 (parity; CI over sentences) | [M1-09](m1-09-async-full-result.md#trust-layer-on-the-async-streams-g1-2026-11-11) |
| MEG (sync streams, secondary) | 1.0 → 0 | 3.23 [3.08, 3.40] vs 3.155 (parity) | [M1-15](m1-15-full-r1-r3-result.md) |

- CRC: mean wrong-commit 0.046–0.048 on B2T (target 0.05) ([M2-13](m2-13-conformal-result.md)).
- Drift: offline CRC 0.0625 (B2T) and 0.0635 (EMG); `aci_window` 0.0478 and 0.0490 ([M2-16](m2-16-online-recal-result.md)).
- Async MEG decoder: greedy CER 0.506 (participants 0.495) ([M1-09](m1-09-async-full-result.md)).

## Gaps before submission (short list)
1. ~~Run the trust harness on the async M1-09 streams~~ **Done 2026-11-11 (G1):** same safety result and parity with gaze typing; null input 0 % commits; CRC 0.0193 / LTT 0.0214 ([G1 results](../../experiments/2026-11-11-g1-async-meg-trust/results.md)).
2. **Multiple seeds** for the MEG and EMG decoders and the simulator.
3. **CIs over sentences and participants** for MEG (17 unique test sentences). Done for the trust rows in G1; still open for the CER rows.
4. **Natural-typing sEMG** ([KT-sEMG](../entities/kt-semg-dataset.md)), or keep it as a limitation.
5. **One ablation table** over the three devices (M3-02).
6. **eWPM sensitivity** to the user-model costs on all three devices.
7. Repeated fit/test splits for B2T and EMG; a B2T LM without the 64 Tatoeba-overlap sentences.
8. Source pages for the closest work (Huang 2025, Kim 2025, Cai 2024, Ernez 2023, Damri 2026, RAS).
9. ~~Figure scripts that read only committed JSON.~~ **Done 2026-11-11 (draft v0):** `papers/paper1/make_figures.py` (8 data figures) plus 3 TikZ diagrams. Reliability diagrams (F5) still need per-bin data in the harness output.
10. A user study (future work) and arXiv endorsement: both depend on outside people (`externally_blocked`).

## Venues
arXiv first (endorsement: externally blocked, the user owns it). Then *Journal of Neural Engineering* or *IEEE TNSRE*. A workshop version can run in parallel. NeurIPS Datasets & Benchmarks fits only after a public benchmark release (P13). CHI needs a user study.

> **Our take:** The paper is a **safety** paper with one clear usefulness result (intracortical) and one partial one (session-calibrated sEMG). MEG shows safety and parity only. State this in the abstract. Do not let the MEG decoder CER become the headline.

## Related pages
- [Project plan, M3](project-plan.md#m3-paper-1-calibrated-abstaining-brain-to-text-target-11-11--11-13)
- [Trust core v0 results](trust-core-v0-results.md)
- [Reading list](reading-list.md)
- [Error metrics](../concepts/error-metrics.md)
