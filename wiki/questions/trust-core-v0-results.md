---
title: Trust core v0 results (simulator + char LM)
type: question
tags: [trust-core, calibration, conformal, hallucination, ewpm, language-model, paper-1]
sources: [brain2qwerty-v2]
updated: 2026-11-08
---

# Trust core v0 results (simulator + char LM)

**Question asked:** What did the first trust-core run show, and what does it change for Paper 1?

## Summary
- We ran the full trust core (calibration, conformal sets, hallucination guard, decision policy, simulated user, effective WPM) on simulator streams.
- The trust policy cuts wrong commits by about 5–20×. It costs 7–16 % effective WPM (eWPM) against "always commit the LM top-1".
- On shuffled or flat input, the trust policy commits no fluent text. Always-commit commits fluent text 98–100 % of the time.
- The character LM gives the largest single gain. But LM fusion breaks the calibration of the character confidences.
- All numbers come from the simulator. No real decoder output is in this page yet.

Raw results:
- [M2 trust core on the simulator](../../experiments/2026-11-08-m2-trust-sim/results.md) (full tables: [tables.md](../../experiments/2026-11-08-m2-trust-sim/results/tables.md)).
- [CTC beam + 6-gram char LM](../../experiments/2026-11-08-lm-beam/results.md).
- [M1-A data layer](../../experiments/2026-11-08-m1a-data/results.md) (the SpanishBCBL splits that Paper 1 will use).

## 1. M2 simulator experiment

### Setup
| Item | Value |
|---|---|
| Streams | Noisy-decoder simulator. Presets best / median / worst × `confidence_temperature` 0.5 / 1.0 / 2.0 (9 conditions) |
| Sentences | 120 calibration, 120 validation, 120 test per condition (template sentences) |
| Decoder | `ReferenceDecoder`: segment beam with a 5-gram Witten–Bell char LM. The LM is in-domain, so its CER (0.03–0.06) is optimistic |
| Policies | (a) commit greedy CTC; (b) commit LM top-1; (c) trust policy, fit on validation for max eWPM with wrong-commit ≤ 0.05; (d) = (c) without calibration; (e) = (c) without the guard |
| Simulated user | Default `UserConfig`: 152 chars/min, p_detect_error 0.9, select-and-correct on. The time costs are assumptions |

### Main numbers (test set)
| Metric | (a) greedy commit | (b) LM top-1 commit | (c) trust policy |
|---|---|---|---|
| eWPM | 13.6–17.5 | 21.4–23.9 | 19.6–22.3 |
| Wrong-commit rate | 1.00 | 0.29–0.47 | 0.02–0.09 |
| eWPM cost of (c) against (b) | — | — | 1.5–3.7 (7–16 %) |

- The LM is the most important part. (b) beats (a) by 6–9 eWPM in every condition.
- The validation limit (0.05) does not hold exactly on test: the worst test value is 0.09. The grid fit on 120 sentences has no finite-sample guarantee.

### Null-input audit (median, T = 1.0)
| Pipeline | Real input: fluent and committed | Shuffled input | Uniform (flat) input |
|---|---|---|---|
| Trust policy | 0.233 | 0.000 | 0.000 |
| Always commit LM top-1 | 1.000 | 0.983 | 1.000 |
| Always commit greedy | 0.000 (not fluent) | 0.000 | 0.000 |

- The LM writes fluent text from noise. The trust policy blocks all of it.

### Calibration
- The frame temperature fit recovers the inverse of the simulator distortion: 1.99–2.01 for T = 0.5, and 0.50–0.51 for T = 2.0.
- Character ECE falls from 0.16–0.39 to 0.012–0.021 (distorted conditions).
- Sentence ECE falls from 0.25–0.34 to 0.09–0.16. The fitted sentence temperature is 6–9, so the raw n-best scores are very over-confident.

### Conformal coverage
- Coverage in the n-best sense is 0.83–0.99 (target 0.9).
- The n-best list misses the truth in 28–37 % of sentences. So strict coverage is only 0.57–0.71.
- **Recall is the bottleneck, not the set construction.**

### Guard
- The guard catches null input (see the audit above).
- On real input, the guard AUROC for a wrong top-1 is only 0.57–0.71.
- The n-best-inconsistency signal alone does better: AUROC 0.65–0.88.

### Ablations, and why they are not clean
- Without calibration (d), eWPM is often *higher* than (c).
- Without the guard (e), eWPM is about the same as (c).
- Reason: the policy thresholds are fit on validation data. They absorb most of what calibration and the guard add. Also, the simulator has only 120 test sentences and one seed. An eWPM difference below about 1 is likely noise.

> **Our take:** These ablations do not show that calibration and the guard are useless. They show that this setup cannot separate their effect. Paper 1 needs ablations with fixed thresholds, more seeds, and real decoder output.

## 2. LM findings (CTC prefix beam + 6-gram char LM)
| Simulator preset | Greedy CER | Beam + LM CER | Greedy WER | Beam + LM WER |
|---|---|---|---|---|
| best | 0.171 | 0.094 | 0.567 | 0.239 |
| median | 0.281 | 0.200 | 0.729 | 0.386 |
| worst | 0.417 | 0.343 | 0.879 | 0.566 |

Source: [LM beam results](../../experiments/2026-11-08-lm-beam/results.md). LM: 6-gram modified Kneser–Ney on Tatoeba English / Spanish (CC BY 2.0 FR). The SpanishBCBL target sentences are removed from the training text.

- **CER gains.** The LM cuts the CER by 0.07–0.08 absolute. The best LM weight is 1.0 on this calibrated simulator. A real, over-confident decoder will need a different weight.
- **n-best oracle.** The top-10 oracle CER is only 0.03 below the 1-best (median 0.200 → 0.167). The 10 hypotheses are often near copies. So the trust layer should offer alternatives per word or per region, not whole sentences.
- **Calibration broken by fusion.** Without the LM, the frame posterior stays calibrated (ECE ≤ 0.015). With the LM, the fused confidence is over-confident (ECE 0.053 / 0.099 / 0.177 for best / median / worst). The frame posterior becomes under-confident.
- **Cross-check.** With the `fidetype.lm` beam at default settings, the n-best misses the truth in 73 % of lists (median, T = 1.0), against 28 % for the reference decoder. Then the trust policy cannot commit. eWPM falls to 16.27, and the guard AUROC is below 0.5 (0.431–0.462).
- **Speed.** 91 ms per 40-character sentence (beam 16, pure Python).

## 3. Design decisions
| Decision | Reason |
|---|---|
| Calibrate at the **frame level, before LM fusion** | LM fusion breaks calibration. A frame temperature recovers the true distortion exactly. A post-fusion fit must then only correct the sentence scores |
| Guard risk = **max(evidence score, n-best inconsistency)** (`combine="max"` in `fidetype.trust.guard`) | Inconsistency alone has a higher AUROC. The evidence term still catches null input |
| Use **frame confidences** for the guard, not fused ones | Fused confidences carry the LM prior. The guard must measure the neural evidence only |
| Re-calibrate per session | Real decoders drift between sessions. `session_recalibration` exists for this |

## 4. What this means for Paper 1
- **Revised claim:** "far fewer wrong and hallucinated commits for a small speed cost", not "higher eWPM". See [project plan, M3](project-plan.md#m3-paper-1-calibrated-abstaining-brain-to-text-target-11-11--11-13).
- eWPM depends on the user time model. We need time costs from the literature or from real data (Cai et al. 2024, see the [reading list](reading-list.md)) before we report eWPM numbers.
- Fix n-best recall first. Re-tune the beam (`prune_topk`, insertion bonus). Without the truth in the list, no policy can commit.
- The SpanishBCBL test split has only 24 unique sentences ([M1-A results](../../experiments/2026-11-08-m1a-data/results.md)). Use cross-validation or multiple seeds.
- Check the RAS formula (arXiv 2604.24278) before we cite the comparison.
- The hallucination result connects to [NeuroLLM](../concepts/neuro-llm.md): a strong language prior writes fluent text that the neural evidence does not support. The null-input audit is our direct test of this risk.

## Related pages
- [Decoder M1 results](decoder-m1-results.md): the decoder-side shuffled-MEG control
- [Architecture](architecture.md): the six layers, NeuralTextStream, effective WPM.
- [Project plan](project-plan.md): M2 known gaps and the M3 revised claim.
- [Error metrics](../concepts/error-metrics.md): CER, WER and why they disagree.
- [NeuroLLM](../concepts/neuro-llm.md): LLM hallucination in brain-to-text.
- [SpanishBCBL dataset](../entities/spanishbcbl-dataset.md).
