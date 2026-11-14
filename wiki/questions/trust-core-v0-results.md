---
title: Trust core v0 results (simulator, char LM, first real MEG, per-word OFFER)
type: question
tags: [trust-core, calibration, conformal, hallucination, ewpm, language-model, paper-1, offer-words, user-model]
sources: [brain2qwerty-v2, brain-to-text-25-copytask]
updated: 2026-11-13
---

# Trust core v0 results (simulator + char LM)

**Question asked:** What did the first trust-core run show, and what does it change for Paper 1?

## Summary
- We ran the full trust core (calibration, conformal sets, hallucination guard, decision policy, simulated user, effective WPM) on simulator streams.
- The trust policy cuts wrong commits by about 5–20×. It costs 7–16 % effective WPM (eWPM) against "always commit the LM top-1".
- On shuffled or flat input, the trust policy commits no fluent text. Always-commit commits fluent text 98–100 % of the time.
- The character LM gives the largest single gain. But LM fusion breaks the calibration of the character confidences.
- Sections 1–5 come from the simulator. Section 6 is the first run on real MEG decoder output.
- **Update (2026-11-08, [beam re-tune](#5-beam-re-tune-2026-11-08)):** the old n-best misses were search errors. With the `RETUNED` beam, the trust policy matches always-commit speed (25.3 vs 25.8 eWPM) with about 3× fewer wrong commits (0.033 vs 0.108).
- **Update (2026-11-08, [real MEG](#6-real-meg-first-test-2026-11-08)):** on real MEG, the trust policy cuts wrong commits from 100 % to 0 % and fluent hallucination on null input from 83–100 % to 0 %. But no candidate is ever correct, so the test is degenerate: it shows safety, not usefulness.
- **Update (2026-11-08, [per-word OFFER](#7-per-word-offer-and-partial-correction-2026-11-08)):** a new action OFFER_WORDS gives +0.4 to +1.7 eWPM at the worst simulator preset (paired CIs exclude 0) and no change at the median preset. On real MEG, the fit never selects it. **No BCI policy on real MEG beats gaze typing alone** (trust 2.96 vs gaze 3.14 eWPM).

- **Update (2026-11-10, [cross-device](#8-cross-device-intracortical-speech-2026-11-10)):** on intracortical speech logits (Brain-to-Text '25, CC0), the test is not degenerate. Trust cuts wrong commits 0.610 → 0.059 (our decoder, eWPM 11.45 → 11.55) and 0.194 → 0.044 (published decoder, eWPM 19.61 → 18.77). All BCI policies beat gaze typing alone (4.08).

- **Update (2026-11-13, [ablations](trust-core-ablations.md)):** clean ablations of the frozen v4 configuration (M3-02) on B2T, sEMG, MEG and the simulator replace the unclean ablations of section 1. No module is enough alone; on MEG v4 makes 0 commits in all five runs; frame-shuffled simulator streams pass the guard (1-16 %).

Raw results:
- [M2-10 trust core on real MEG](../../experiments/2026-11-08-m2-real-keystroke/results.md) (tables: [tables.md](../../experiments/2026-11-08-m2-real-keystroke/results/tables.md)).
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
- **Revised claim:** "far fewer wrong and hallucinated commits for a small speed cost", not "higher eWPM". See [project plan, M3](project-plan.md#m3-trust-layer-validation-research-calibrated-abstaining-brain-to-text-target-11-11--11-13).
- eWPM depends on the user time model. We need time costs from the literature or from real data (Cai et al. 2024, see the [reading list](reading-list.md)) before we report eWPM numbers.
- Fix n-best recall first. Re-tune the beam (`prune_topk`, insertion bonus). Without the truth in the list, no policy can commit. **Done** on the simulator: see [section 5](#5-beam-re-tune-2026-11-08).
- The SpanishBCBL test split has only 24 unique sentences ([M1-A results](../../experiments/2026-11-08-m1a-data/results.md)). Use cross-validation or multiple seeds.
- Check the RAS formula (arXiv 2604.24278) before we cite the comparison.
- The hallucination result connects to [NeuroLLM](../concepts/neuro-llm.md): a strong language prior writes fluent text that the neural evidence does not support. The null-input audit is our direct test of this risk.

## 5. Beam re-tune (2026-11-08)
Source: [beam re-tune results](../../experiments/2026-11-08-beam-retune/results.md). Simulator data only.

### Diagnosis: a search error, not a model error
- With the old settings (beam 16, `prune_topk = 10`), **every** missed truth is a search error. The true sentence has a higher score than the 16th hypothesis, but the search dropped it.
- The per-frame top-10 cut is the largest cause. It removes a true character at all its frames in 90 % of the median sentences.
- The beam width is the second cause. A true character with weak evidence falls 5–10 nats behind. The LM gives the score back only at the end of the word. A beam of 16 cannot keep it for that long.
- The cut and the beam must change together. A beam of 64 with the top-10 cut gives recall@10 0.130 only.

### Sweep highlights (median Tatoeba test set, 200 sentences)
| Setting | r@10 | oracle CER@10 | CER@1 | ms |
|---|---|---|---|---|
| Old default (beam 16, top-10, w 1.0, bonus 2.0) | 0.075 | 0.188 | 0.210 | 37 |
| Beam 256, no top-k cut (w 1.0, bonus 2.0) | 0.400 | 0.096 | 0.149 | 218 |
| **RETUNED** (beam 256, no top-k, w 1.25, bonus 1.0, numpy search) | **0.470** | **0.078** | **0.126** | 148 |
| RETUNED, beam 512 | 0.520 | 0.072 | 0.123 | 238 |

- Best preset: r@10 0.180 → 0.715. Worst preset: 0.025 → 0.195.
- About half of the remaining misses are model errors. A wider beam cannot fix those.
- The old defaults of `ctc_prefix_beam_search` do not change. Callers opt in with `**RETUNED`.

### Trust pipeline: reference vs old beam vs new beam (median, T = 1.0, test)
| Decoder | n-best miss rate | Trust policy (c) eWPM | (c) wrong-commit | (c) COMMIT share | Always-commit (b) eWPM | (b) wrong-commit |
|---|---|---|---|---|---|---|
| Reference (5-gram segment beam) | 0.275 | 21.88 | 0.033 | 0.23 | 23.89 | 0.317 |
| Old beam (`fidetype.lm` defaults) | 0.708 | 16.27 | 0.000 | 0.00 | 20.42 | 0.758 |
| **New beam (RETUNED)** | **0.000** | **25.33** | 0.033 | 0.86 | 25.78 | 0.108 |

- In all four conditions, the miss rate falls to 0.00–0.03 (old beam 0.71–0.92, reference 0.28–0.34). Strict conformal coverage is 0.91–0.94, above the 0.9 target.
- The M2 cross-check reported an old-beam miss rate of 0.733 for this condition. The test-split row above gives 0.708.

### Revised headline
**The trust policy now matches always-commit speed (25.3 vs 25.8 eWPM) with about 3× fewer wrong commits (0.033 vs 0.108).** This holds for median, T = 1.0, on the simulator. It replaces the earlier "small speed cost" claim for this decoder.

> **Our take:** The trust layer did not change. Only the n-best recall changed. So the old eWPM cost was a recall problem in the decoder, not a cost of the trust policy.

### Open problems
- **The wrong-commit limit is exceeded on test:** 0.058–0.075 in three of four conditions, against the 0.05 validation target. The grid fit on 120 sentences has no finite-sample guarantee. The new beam commits more often, so this matters more now. Next: conformal risk control. **Done in M2-13** ([result](m2-13-conformal-result.md)): on B2T '25, CRC gives a mean test wrong-commit of 0.046–0.048.
- **The guard needs re-tuning.** Its combined risk has AUROC 0.49–0.68 for a wrong top-1. n-best inconsistency alone gives 0.78–0.90, and `p_top1` 0.75–0.91.
- **Frame calibration is required before the beam.** Without it (T = 0.5, always-commit), both LM beams commit a wrong text in almost every sentence. The CTC prefix probability sums the evidence of all frames of a peak, so the LM cannot overrule an over-confident stream.
- **Word-level alternatives need a per-word OFFER action.** Three choices per word reach the truth more often than three whole sentences (Tatoeba 0.465 vs 0.38). The simulated user cannot choose words yet, so the harness cannot measure this. *(Done: see [section 7](#7-per-word-offer-and-partial-correction-2026-11-08).)*

## 6. Real MEG, first test (2026-11-08)
Source: [M2-10 results](../../experiments/2026-11-08-m2-real-keystroke/results.md).

### Setup
- **Decoder:** a synchronous keystroke decoder (`fidetype.decoders.keystroke`). The key-press times come from the keyboard log (oracle timing, the Brain2Qwerty v1 setting). This is not a real-time device setting.
- Features: −0.2..+0.3 s around each key press, 306 channels, 10 bins. Model: per-subject multinomial logistic regression. It beat a shared MLP on val (key accuracy 0.419 vs 0.336).
- Data: 20 cached blocks, 11 subjects. Train 947 trials / 38 204 keys. Val 114 trials / 11 sentences. Test 209 trials / 17 unique sentences.
- The decoder emits a CTC-form NeuralTextStream with no text in `meta`. The trust pipeline is fitted on val. Beam: `RETUNED`, frame-calibrated, `lm_weight = 0.5` (best on val), n-best 10.

### Decoder (test)
| input | key acc | greedy CER vs typed | greedy CER vs target |
|---|---|---|---|
| real MEG | **0.390** | 0.590 | 0.597 |
| control: shuffled MEG | 0.111 | 0.774 | 0.774 |
| control: labels permuted at train time | 0.099 | 0.767 | 0.768 |

- Majority-class chance is 0.13. Both controls are at chance. So the decoder uses the MEG.
- With the LM beam: test CER **0.531**, WER 1.023.
- **The true sentence is in the n-best in 0 % of trials**, at every beam setting.

### Trust pipeline (test, 209 trials)
| policy | wrong-commit | commits | eWPM |
|---|---|---|---|
| (b) always commit LM top-1 | 100 % (83 % fluent Spanish) | all | 9.61 |
| (c) trust policy | **0 %** | none (always OFFER) | 9.70 |
| (d) no calibration | 1 % | 1 % | 9.69 |
| (e) no guard; (f) inconsistency + p_top1 only | 0 % | none | 9.70 |

- The 95 % CI of the eWPM difference (c) − (b) crosses 0: [−0.11, +0.35] (trial bootstrap).
- eWPM comes from the simulated user only. No candidate is right, so eWPM measures correction time only.

### Null-input audit and guard
| input | LM top-1: fluent commits | trust variants (c, e, f): fluent commits |
|---|---|---|
| real MEG | 83 % | 0 % |
| shuffled MEG | 84 % | 0 % |
| frame-shuffled stream | 86 % | 0 % |
| uniform stream | 100 % | 0 % |

| guard AUROC (combined risk) | value |
|---|---|
| top-1 CER above median | 0.85 |
| uniform vs real | 0.98 |
| shuffled MEG vs real | about 0.5 (no signal separates them) |

- On real MEG, the evidence term carries the guard. n-best inconsistency and `p_top1` are near chance. This is the opposite of the simulator.
- The shuffled-MEG stream is real classifier output for real key presses. Its confidence statistics are the same as real, so no signal detects it.
- **Conformal coverage is 0**, because the truth is never in the n-best. The calibrator correctly makes the set the full list. Word-level coverage is 0.27.

### Caveat: a degenerate test
No candidate is ever correct. So the best policy is to commit nothing, and the trust policy finds that. This is a real safety result: the trust layer did not let the LM's fluent text through. But it does not show usefulness. It cannot show that the policy picks the correct commits from the wrong ones. That needs a stronger decoder, whose LM top-1 is right for a real share of sentences.

> **Our take:** Next: a sentence-context decoder (v1 went from Conv 0.67 to Conv+Trans 0.36 CER), the full cache, and a per-word OFFER with partial correction in the user model. Known bug: `TemperatureScaler.transform_stream` drops `vocab_type`, `frame_period` and `latency` from the stream.

## 7. Per-word OFFER and partial correction (2026-11-08)
Source: [OFFER_WORDS results](../../experiments/2026-11-08-m2-offer-words/results.md) (all tables: [tables.md](../../experiments/2026-11-08-m2-offer-words/results/tables.md)). Code: `src/fidetype/trust/policy.py`, `src/fidetype/interact/simulated_user.py`, `src/fidetype/eval/harness.py`, `src/fidetype/eval/ewpm.py`. Tests: `tests/test_trust_offer_words.py`.

### What changed
- **New action `OFFER_WORDS`:** show the top-1 sentence. Highlight each word slot with confidence below `word_conf_threshold`. Show the `offer_words_k` best alternatives for each highlighted slot.
- Slot confidence: the mass of the top-1 word in its own slot of `word_alternatives` (calibrated sentence posteriors).
- The policy fit searches `word_conf_threshold` × `offer_words_min_conf` (7 × 5) with `OFFER_WORDS_GRID`.
- **Word-level user model** (`UserConfig.aac_gaze()`): the user fixes wrong words one by one, selects from alternatives, misses an unhighlighted wrong word with `p_miss_unflagged` (0.05), and retypes the sentence if that is cheaper. Fallback typing is 20 chars/min (gaze keyboard, Cai et al. 2024).
- An OFFER_WORDS sentence counts as a **wrong commit** if an unhighlighted word is wrong. So the 0.05 wrong-commit limit still applies.
- Defaults are unchanged (`offer_words=False`, `UserConfig()`). A before/after harness snapshot is identical.

### Simulator (test, eWPM)
| condition | always commit | trust | trust + OFFER_WORDS | OW − trust (paired CI) | OW rate | gaze only |
|---|---|---|---|---|---|---|
| median/T=0.5 | 24.55 (wc 0.100) | 24.45 (wc 0.067) | 24.41 (wc 0.067) | [−0.16, 0.05] | 0.10 | 4.10 |
| median/T=1.0 | 24.44 (wc 0.100) | 24.48 (wc 0.033) | 24.84 (wc 0.042) | [−0.07, 0.85] | 0.14 | 4.10 |
| worst/T=0.5 | 21.04 (wc 0.250) | 19.49 (wc 0.050) | **20.45** (wc 0.058) | **[0.36, 1.57]** | 0.63 | 4.10 |
| worst/T=1.0 | 19.95 (wc 0.333) | 19.40 (wc 0.025) | **20.46** (wc 0.042) | **[0.40, 1.74]** | 0.73 | 4.10 |

wc = wrong-commit rate.

- At the worst preset, OFFER_WORDS replaces most sentence OFFERs. It closes the gap to always commit with 6–8× fewer wrong commits.
- At the median preset, 86–90 % of sentences are committed. OFFER_WORDS has little to replace.
- OFFER_WORDS on every sentence with all slots highlighted halves eWPM (12.2–12.7). The highlight threshold is necessary.
- The word-level user makes always commit much faster at T = 0.5 (24.55 vs 17.17 with the old user). So the eWPM cost of the trust policy depends on the correction model.

### Real MEG (test, 209 trials, user `aac_gaze()`)
| policy | eWPM | wrong-commit | silent error | KSR |
|---|---|---|---|---|
| always commit LM top-1 | 2.31 | 1.000 | 0.254 | 0.02 |
| trust, no OFFER_WORDS | 2.96 | 0.000 | 0.000 | −0.04 |
| trust + OFFER_WORDS | 2.96 (identical; OW rate 0) | 0.000 | 0.000 | −0.04 |
| diag: OFFER_WORDS always, all slots | 2.86 | 0.000 | 0.000 | 0.09 |
| **gaze typing only (no BCI)** | **3.14** | 0 | 0 | 0.00 |

- The policy fit never selects OFFER_WORDS (0 of 209 trials). System word accuracy is 0.10. In the forced row, the true word is among the 3 alternatives of a wrong highlighted slot only 7 % of the time.
- Trust − always commit: +0.65 eWPM (sentence CI [0.51, 0.79]). The gain comes from silent errors: with `p_miss_unflagged` 0, always commit is level with trust (3.00 vs 2.96).
- **No BCI policy beats gaze typing alone (3.14 eWPM)**, in every user-model variant.
- These eWPM values use the new `aac_gaze()` user. The section 6 values (9.61 / 9.70) use the old sentence-level user. Do not compare them directly.

> **Our take:** OFFER_WORDS helps when the decoder is close: most words right, a few uncertain words, and the right word among the alternatives. The simulator worst preset (system word accuracy 0.96–0.97) is that regime. Real MEG (0.10) is not. The action does not rescue a weak decoder, and the fit correctly refuses it.

> **Our take:** The more important real-data result is the comparison with gaze typing. At key accuracy 0.39, the BCI costs the user time. Paper 1 must report eWPM against a no-BCI fallback baseline, not only against other BCI policies.

**Limits:** the word-model time values are partly assumptions. Only the per-slot sum (4.5 s) and the 20 chars/min fallback are matched to Cai et al. 2024. `p_miss_unflagged` has no measurement. Real MEG has 17 test sentences and oracle key timing. The simulator uses one seed per condition.

## 8. Cross-device: intracortical speech (2026-11-10)
Full page: [B2T '25 trust result](b2t25-trust-result.md). Experiment: [2026-11-10-b2t25-trust](../../experiments/2026-11-10-b2t25-trust/results.md). Source: [copy-task logits](../sources/brain-to-text-25-copytask.md).

- Device: 256-electrode intracortical speech BCI (T15). Stream: phoneme CTC (41 tokens), 80 ms frames, `vocab_type="phoneme"`. Adapter `fidetype.adapters.b2t25` (our code).
- Words: our licence-clean route (phoneme beam → CMUdict lookup → Tatoeba word unigram → char 6-gram). Test WER 0.149; published decoder 0.043.
- User: `aac_gaze()` with the measured speech rate (159.3 chars/min). Fit 812 trials, test 816.

| policy | eWPM [trial CI] | wrong-commit | silent error |
|---|---|---|---|
| always commit our top-1 | 11.45 [10.95, 12.04] | 0.610 | 0.044 |
| trust (ours) | 11.55 [11.03, 12.06] | 0.059 | 0.002 |
| always commit published | 19.61 [18.68, 20.51] | 0.194 | 0.025 |
| trust gate on published | 18.77 [17.88, 19.62] | 0.044 | 0.004 |
| gaze typing only | 4.08 | 0 | 0 |

- AUROC "top-1 wrong": −p_top1 0.797 (word), 0.884 (phoneme); guard risk 0.702 / 0.825. Word confidence vs word wrong: 0.844. Sentence ECE 0.448 → 0.067 (frame T 3.78).
- The guard did not help here: without it, wrong commits were 0.036 at the same eWPM.
- Null input: shuffled / uniform streams → 0 % commits. Another trial's real stream → 22 % commits (ours), 0 % (published gate).

> **Our take:** The MEG result showed safety only. This one shows usefulness too: the trust core passes correct commits and blocks most wrong ones, on a second device, with the spec unchanged.

## Related pages
- [Trust-core ablations](trust-core-ablations.md): M3-01 / M3-02, frozen v4 baseline.
- [OFFER_WORDS experiment](../../experiments/2026-11-08-m2-offer-words/results.md)
- [M2-10 real-MEG experiment](../../experiments/2026-11-08-m2-real-keystroke/results.md)
- [Beam re-tune experiment](../../experiments/2026-11-08-beam-retune/results.md)
- [Decoder M1 results](decoder-m1-results.md): the decoder-side shuffled-MEG control
- [Architecture](architecture.md): the six layers, NeuralTextStream, effective WPM.
- [Project plan](project-plan.md): M2 known gaps and the M3 revised claim.
- [Error metrics](../concepts/error-metrics.md): CER, WER and why they disagree.
- [NeuroLLM](../concepts/neuro-llm.md): LLM hallucination in brain-to-text.
- [SpanishBCBL dataset](../entities/spanishbcbl-dataset.md).
