---
title: P15-05 (F2 / E3) LLM rescoring and rewrite with a grounding check - results
type: experiment
task: P15-05
updated: 2026-11-16
---

# P15-05: faithful LLM decoding with a run-time grounding check (results, T15 and T12)

Plan (written before the runs): [plan.md](plan.md). Pillar F2, experiment E3 ([north star](../../wiki/questions/north-star.md#f2-faithful-language-model-decoding-e3), [roadmap P15-05](../../wiki/questions/roadmap-standard.md#p15-05-e3-llm-rescoring-with-a-grounding-check)). Aggregates: [results/results-t15.json](results/results-t15.json), [results/summary-t15.json](results/summary-t15.json), log [results/run.log](results/run.log). Report script: [report.py](report.py). T12 (second set, run after the [T12 addendum](plan.md#t12-addendum-written-2026-11-16-after-the-t15-run-and-before-any-t12-run)): see [T12 replication](#t12-replication-2026-11-16) and [Overall P15-05 verdict](#overall-p15-05-verdict-t15--t12) at the end. Per-trial outputs: `C:\Users\zhang\bci-data\derived\f2-e3-llm-grounding\` only.

## Verdict
- **F2/E3 does not pass** the pre-registered rule. The primary arm B1 passes S1, S2 and S3, and fails S4 (2 fluent-wrong commits against 0 for A0).
- **LLM rescoring helps.** WER 0.3985 -> 0.3831 (-0.0154, 95 % interval [-0.0209, -0.0096]); sentence accuracy 0.084 -> 0.110.
- **The grounding check blocks text from the wrong signal.** In the swapped-signal control it takes the commits from 9 / 28 / 23 (B0 / C0 / D0) to 0 in every grounded arm.
- **The grounding check does not block LLM text on the true signal.** On the 701 held-out trials it changed no top-1 in any arm. The free-rewrite top-1, with words that are in no base candidate, always passed `tau`.

## Fitted values (on `val_select`, before `val_eval`)
| item | value |
|---|---|
| frame temperature T (A0 calibration) | 1.2889 |
| `tau` (95 % split-conformal quantile of the true-text deficits) | 0.0806 nats / frame |
| true-text deficit quantiles 0.5 / 0.9 / 0.95 / 0.99 | 0.0061 / 0.0550 / 0.0804 / 0.1412 |
| true texts that pass at `tau` / without labels | 0.9515 / 0 |
| LLM weight `lambda` (grid WER 0.1: 0.3818, 0.25: 0.3744, 0.5: 0.3686, **1.0: 0.3671**, 2.0: 0.3707) | 1.0 |
| base `val_select` WER (tempered input) | 0.3856 |
| fluent threshold (median LLM log-prob per word, true `val_select` texts) | -7.882 |

## Arm table (held-out `val_eval`, 701 trials, alpha 0.05, delta 0.1)
| arm | WER | sent. acc | dWER vs A0 [95 %] | commits | wrong | wrong-commit rate [CP95] | offers | halluc. rate (unsup. / shown) | fluent-wrong | uniform | shuffled | swapped commits (not truth of signal) | swapped = truth of language trial |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 n-gram | 0.3985 | 0.084 | - | 2 | 2 | 0.0029 [0.0003, 0.0103] | 699 | 0.0000 (0/4659) | 0 | 0/300 | 0/300 | 2 (2) | 0 |
| A1 n-gram + G | 0.3985 | 0.084 | +0.0000 [+0.0000, +0.0000] | 2 | 2 | 0.0029 [0.0003, 0.0103] | 699 | 0.0000 (0/4659) | 0 | 0/300 | 0/300 | **0 (0)** | 0 |
| B0 rescore | 0.3831 | 0.110 | -0.0154 [-0.0209, -0.0096] | 9 | 2 | 0.0029 [0.0003, 0.0103] | 692 | 0.0000 (0/4658) | 2 | 0/300 | 0/300 | 9 (9) | 7 |
| **B1 rescore + G** | **0.3831** | **0.110** | **-0.0154 [-0.0209, -0.0096]** | 10 | 2 | 0.0029 [0.0003, 0.0103] | 691 | 0.0000 (0/4658) | **2** | 0/300 | 0/300 | **0 (0)** | 0 |
| C0 lattice rewrite | 0.3874 | 0.103 | -0.0111 [-0.0176, -0.0046] | 28 | 9 | 0.0128 [0.0059, 0.0242] | 673 | 0.0000 (0/4641) | 5 | 0/300 | 0/300 | 28 (28) | 19 |
| C1 lattice rewrite + G | 0.3874 | 0.103 | -0.0111 [-0.0176, -0.0046] | 29 | 9 | 0.0128 [0.0059, 0.0242] | 672 | 0.0000 (0/4653) | 5 | 0/300 | 0/300 | **0 (0)** | 0 |
| D0 free rewrite (hazard) | 0.3822 | 0.111 | -0.0163 [-0.0233, -0.0095] | 23 | 6 | 0.0086 [0.0031, 0.0185] | 678 | 0.0121 (56/4629) | 3 | 0/300 | 0/300 | 23 (23) | 17 |
| D1 free rewrite + G | 0.3822 | 0.111 | -0.0163 [-0.0233, -0.0095] | 26 | 6 | 0.0086 [0.0031, 0.0185] | 675 | 0.0080 (37/4650) | 3 | 0/300 | 0/300 | **0 (0)** | 0 |

- No arm withheld; every non-commit is an offer. No committed text had an unsupported word (all unsupported words are in first offered choices).
- Built-in `calibrate` controls (from `val_select`, allowed 15 / 300): all 8 arms pass (uniform 0, shuffled 0 or 1).
- C: 105 lattice rewrites had a word outside the base 10-best and were discarded (C0 and C1 the same).
- Grounded vs ungrounded arm, held out: top-1 differs in 0 trials (A, B, C, D); the action differs in 0 / 1 / 1 / 3 trials; the shown text (commit or first offer) differs in 0 / 3 / 22 / 48 trials. The grounding demotes some lower candidates, so the guard's offer order changes, but never the pipeline top-1.
- Swapped signal, ungrounded: most of these commits are the exact truth of the *other* trial (B0 7 / 9, C0 19 / 28, D0 17 / 23). The trust gate alone sees only how confident the n-best is, so a confident list from the wrong context commits.

## Pre-registered checks (plan.md)
| check | B1 (primary) | C1 (secondary) |
|---|---|---|
| S1 accuracy: WER < A0 and bootstrap upper bound < 0 | **pass** (-0.0154 [-0.0209, -0.0096]) | pass (-0.0111 [-0.0176, -0.0046]) |
| S2 bound: guard returned, wrong-commit rate <= 0.05 | **pass** (0.0029, CP95 upper 0.0103) | pass (0.0128, CP95 upper 0.0242) |
| S3 controls: uniform, shuffled <= 1 / 300; swapped unsupported <= 2 / 701 | **pass** (0, 0, 0) | pass (0, 0, 0) |
| S4 hallucination: rate <= A0 and fluent-wrong <= A0 | **fail** (rate 0 = 0; fluent-wrong 2 > 0) | fail (rate 0 = 0; fluent-wrong 5 > 0) |
| F2/E3 pass (all four) | **no** | no |

Per the plan: S1 passes, so this is not "safe but no gain". It is "gain, bound and controls hold, fluent-wrong criterion fails".

## Key findings
1. **Rescoring with a 1.5B LLM lowers WER by 1.5 points** (3.9 % relative) and raises sentence accuracy by 2.6 points. The interval excludes 0. The lattice rewrite (C) gains less than plain rescoring. The free rewrite (D) gains about the same as B but adds unsupported words.
2. **The grounding check is a strong mismatched-evidence filter.** With the language side from another trial, every grounded arm committed 0 / 701 (ungrounded: 2 to 28). It costs nothing in WER, wrong-commit rate or null controls on true signals.
3. **The grounding check, as set (`tau` = 95 % coverage of true texts), is too loose for within-signal hallucination.** In D it never demoted the top-1 rewrite. The hallucination rate falls only through the offer order (56 -> 37 unsupported words, 0.0121 -> 0.0080), not to 0. A per-frame deficit of 0.08 nats is wide enough for a word swap with a similar phoneme string.
4. **S4 fails on small counts.** B1 commits 10 (A0: 2), with 2 wrong in both. The 2 wrong B1 commits are fluent by the LLM measure; the 2 wrong A0 commits are not. The LLM makes the decoder more confident, so it commits more, and its wrong commits read well. This is the exact risk that F2 names. The counts are too small to call it a rate effect, but the pre-registered rule says fail, and we keep that.
5. The wrong-commit bound held in all arms (CP95 upper <= 0.0242 < 0.05).

## What this means for F2
- An LLM can add accuracy under the existing trust bound, and a CTC grounding check reliably stops text that comes from the wrong signal. Both are new pieces of evidence for the F2 claim.
- The run-time check does **not** yet give the "never puts words in the user's mouth" property on the true signal: a coverage-set `tau` lets fluent, phonetically close text through. A stated bound on unsupported or fluent-wrong commits needs its own calibration (P15-06), not the 95 % true-text quantile.
- The swapped-signal control is the most useful new benchmark track (P15-07): without grounding, the trust gate commits the other trial's exact sentence up to 19 times in 701.

## What P15-06 should do
- Calibrate the commit decision on a **fluent-wrong loss** (and an unsupported-word loss) with CRC / LTT, jointly with `tau`, instead of fixing `tau` at 95 % true-text coverage. Search `tau` over a grid that includes much smaller values (the true-text median deficit is 0.006).
- Apply the grounding check to the **committed text only** at the commit step (a commit-gate condition: deficit of the commit text <= `tau_commit`), so that a strict `tau_commit` blocks fluent-wrong commits while offers keep the loose `tau`.
- Add a word-level check: each committed word must be in the base lattice or have a per-word CTC deficit below a threshold (the sentence-level per-frame deficit dilutes a one-word swap).
- Join it to the P14-03 drop-in wrapper as a `grounding=` option, with a guarantee-sheet entry (alpha, delta, loss, method, items). Report on two public sets: T15 plus T12 v2 (not run here).
- Keep the swapped-signal control as a required check, with its "equal to the truth of the language trial" count.

## Deviations from the plan
- **T12 v2 was not run with T15** (plan: "only if time allows"). It ran later under the T12 addendum: see [T12 replication](#t12-replication-2026-11-16).
- The swapped-signal check counted commits "not truth of signal" as planned; we also report commits equal to the truth of the language trial (planned as "leak").
- `report.py` (not run before) needed two fixes: it read held-out truths by loading all logits and decoders (changed to read only the text keys, same order as `run.data_t15`), and it read a wrong key name in the guarantee-sheet controls (`commits` -> `n_commit`). Values are unchanged.
- Grounded arms reuse the LLM caches of the ungrounded arms, so their run times (30-170 s) are not comparable with the ungrounded ones (1,800-2,500 s).

## Limits
- One participant, one split, one LLM (Qwen2.5-1.5B-Instruct, Q4_K_M), CPU only.
- Commit counts are small (2 to 29 of 701). The fluent-wrong difference (2 vs 0) is not a measured rate difference.
- "Unsupported word" uses the base 10-best as the support set; the D1 rate depends on this choice.
- `tau` is a coverage statement on true texts, not a bound on hallucinated commits.

## T12 replication (2026-11-16)
Second set, under the [T12 addendum](plan.md#t12-addendum-written-2026-11-16-after-the-t15-run-and-before-any-t12-run) (written before the T12 run, commit `419fe9e`). Same `run.py`, model file, arms, prompts and grids. Data: T12 (Brain-to-Text '24, CC0), M3-28 v2 GRU-CTC recorded log-probs. Fit: 480 trials of the 14 `fit_a` + `calibration` sessions. Held out: 400 trials of the 10 `test` sessions (split by session, in time order). Aggregates: [results/results-t12.json](results/results-t12.json), [results/summary-t12.json](results/summary-t12.json), log [results/run-t12.log](results/run-t12.log). Per-trial outputs: `C:\Users\zhang\bci-data\derived\f2-e3-llm-grounding\t12\` only.

### Fitted values (on the 480 fitting trials, before the held-out set)
| item | T12 | T15 (for comparison) |
|---|---|---|
| frame temperature T (A0 calibration) | 2.5281 | 1.2889 |
| `tau` (95 % split-conformal quantile of the true-text deficits) | 0.4742 nats / frame | 0.0806 |
| true-text deficit quantiles 0.5 / 0.9 / 0.95 / 0.99 | 0.0975 / 0.3218 / 0.4261 / 0.7186 | 0.0061 / 0.0550 / 0.0804 / 0.1412 |
| true texts that pass at `tau` / without labels | 0.9521 / 4 | 0.9515 / 0 |
| LLM weight `lambda` (T12 grid WER 0.1: 0.4582, 0.25: 0.4579, **0.5: 0.4563**, 1.0: 0.4563, 2.0: 0.4595; tie -> smaller) | 0.5 | 1.0 |
| base fitting-split WER (tempered input) | 0.4591 | 0.3856 |
| fluent threshold (median LLM log-prob per word, true fitting texts) | -8.916 | -7.882 |

### Arm table (held out, 400 trials, alpha 0.05, delta 0.1)
| arm | WER | sent. acc | dWER vs A0 [95 %] | commits | wrong | wrong-commit rate [CP95] | offers | halluc. rate (unsup. / shown) | fluent-wrong | uniform | shuffled | swapped commits (not truth of signal) | swapped = truth of language trial |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 n-gram | 0.3885 | 0.077 | - | 25 | 15 | 0.0375 [0.0211, 0.0611] | 375 | 0.0000 (0/2382) | 4 | 0/300 | 0/300 | 25 (25) | 10 |
| A1 n-gram + G | 0.3885 | 0.077 | +0.0000 [+0.0000, +0.0000] | 25 | 15 | 0.0375 [0.0211, 0.0611] | 375 | 0.0000 (0/2382) | 4 | 0/300 | 0/300 | **0 (0)** | 0 |
| B0 rescore | 0.3851 | 0.087 | -0.0034 [-0.0086, +0.0021] | 15 | 8 | 0.0200 [0.0087, 0.0390] | 385 | 0.0000 (0/2383) | 4 | 0/300 | 0/300 | 15 (15) | 7 |
| **B1 rescore + G** | **0.3851** | **0.087** | **-0.0034 [-0.0086, +0.0021]** | 15 | 8 | 0.0200 [0.0087, 0.0390] | 385 | 0.0000 (0/2383) | **4** | 0/300 | 0/300 | **0 (0)** | 0 |
| C0 lattice rewrite | 0.3898 | 0.098 | +0.0013 [-0.0078, +0.0105] | 23 | 10 | 0.0250 [0.0121, 0.0455] | 377 | 0.0000 (0/2381) | 6 | 0/300 | 0/300 | 23 (23) | 13 |
| C1 lattice rewrite + G | 0.3898 | 0.098 | +0.0013 [-0.0078, +0.0105] | 23 | 10 | 0.0250 [0.0121, 0.0455] | 377 | 0.0000 (0/2376) | 6 | 0/300 | 0/300 | **0 (0)** | 0 |
| D0 free rewrite (hazard) | 0.3885 | 0.087 | +0.0000 [-0.0102, +0.0107] | 25 | 13 | 0.0325 [0.0174, 0.0549] | 375 | 0.0105 (25/2373) | 7 | 0/300 | 0/300 | 25 (25) | 12 |
| D1 free rewrite + G | 0.3885 | 0.087 | +0.0000 [-0.0102, +0.0107] | 25 | 13 | 0.0325 [0.0174, 0.0549] | 375 | 0.0101 (24/2374) | 7 | 0/300 | 0/300 | **0 (0)** | 0 |

- No arm withheld; every non-commit is an offer. No committed text had an unsupported word (`unsupported_committed_words` is 0 in all arms).
- Built-in `calibrate` controls (fitting split, allowed 15 / 300): all 8 arms pass (uniform 0, shuffled 0).
- C: 55 lattice rewrites had a word outside the base 10-best and were discarded (C0 and C1 the same).
- Top-1 changed against the base decode: B 93, C 266, D 279 of 400.
- Grounded vs ungrounded arm, held out (from the per-trial files): the top-1 differs in 0 trials (A, B, C, D); the action differs in 0 / 0 / 0 / 0; the shown text (commit or first offer) differs in 0 / 0 / 3 / 3.
- The A0 wrong-commit CP95 upper bound (0.0611) is above alpha, as in P14-03 T12 (same set; drift across sessions; one draw). The point rate (0.0375) is below alpha. S2 uses the point rate, as pre-registered.
- Precision is low in every arm: 15 of 25 A0 commits and 8 of 15 B1 commits are wrong.

### Pre-registered checks, T12 (addendum limits)
| check | B1 (primary) | C1 (secondary) |
|---|---|---|
| S1 accuracy: WER < A0 and bootstrap upper bound < 0 | **fail** (-0.0034 [-0.0086, +0.0021]) | fail (+0.0013 [-0.0078, +0.0105]) |
| S2 bound: guard returned, wrong-commit rate <= 0.05 | **pass** (0.0200, CP95 upper 0.0390) | pass (0.0250, CP95 upper 0.0455) |
| S3 controls: uniform, shuffled <= 1 / 300; swapped unsupported <= 2 / 400 | **pass** (0, 0, 0) | pass (0, 0, 0) |
| S4 hallucination: rate <= A0 and fluent-wrong <= A0 | **pass** (rate 0 = 0; fluent-wrong 4 = 4) | fail (rate 0 = 0; fluent-wrong 6 > 4) |
| T12 pass (all four) | **no** | no |

Per the plan: S1 fails and S2-S4 pass, so B1 on T12 is **"safe but no gain"** (a valid negative result).

### T15 vs T12
| effect | T15 (701 held out) | T12 (400 held out) | replicated? |
|---|---|---|---|
| Grounding stops swapped-signal commits | ungrounded 2 / 9 / 28 / 23 (A0-D0) -> 0 in every grounded arm | ungrounded 25 / 15 / 23 / 25 -> 0 in every grounded arm | **yes** |
| Swapped commits equal to the truth of the language trial (ungrounded A0-D0) | 0 / 7 / 19 / 17 | 10 / 7 / 13 / 12 | yes (the trust gate alone commits the other trial's sentence) |
| Grounding changes the top-1 on true signals | 0 trials in every arm | 0 trials in every arm | yes (`tau` at 95 % coverage is too loose on both sets) |
| LLM rescoring lowers WER (B1 - A0) | -0.0154 [-0.0209, -0.0096] | -0.0034 [-0.0086, +0.0021] | **no** (same sign; the interval includes 0) |
| Sentence accuracy A0 -> B1 | 0.084 -> 0.110 | 0.077 -> 0.087 | direction only |
| B1 commits / wrong (A0) | 10 / 2 (2 / 2) | 15 / 8 (25 / 15) | no: on T12 rescoring commits less, not more |
| Fluent-wrong commits A0 / B1 / C1 / D1 | 0 / 2 / 5 / 3 | 4 / 4 / 6 / 7 | partly: rewrites (C, D) add fluent-wrong commits on both sets; B1 adds them only on T15 |
| Free-rewrite unsupported words D0 -> D1 | 0.0121 -> 0.0080 | 0.0105 -> 0.0101 | yes (grounding lowers them only a little; none committed) |
| Null controls (uniform, shuffled), all arms | 0 / 300, 0 / 300 | 0 / 300, 0 / 300 | yes |

Reading of the comparison:
1. **The grounding check as a mismatched-evidence filter replicates.** On both sets, with the language side from another trial, no grounded arm committed. Without grounding, the trust gate committed up to 28 (T15) and 25 (T12) times, often the exact sentence of the other trial.
2. **The rescoring gain does not replicate at the pre-registered level.** On T12 the gain is about a quarter of the T15 gain, and it is not significant. On T12 the fitted `lambda` is smaller (0.5) and the fitting split is harder (base WER 0.4591), so the LLM prior has less weight.
3. **Fluent-wrong commits stay the open risk.** The rewrite arms add fluent-wrong commits on both sets. On T12 the B1 count equals A0 (4 = 4) only because rescoring lowered the commits (25 -> 15). The grounding check at 95 % coverage never blocks fluent text on the true signal. Its `tau` on T12 (0.47 nats / frame) is about 6 times the T15 value.

### Deviations (T12)
- The first T12 start (01:23:59) stopped during A0. It was restarted at 01:30:58 with the smaller decoder LRU memos (commit `5d8ff78`, RAM < 4 GB; results unchanged). No held-out result came from the first start. The only `prep done` line (fluent threshold) is from the first start; the restart logged no prep line. The fluent threshold is fitted on the fitting split only.
- `report.py t12` ran without a code change.

## Overall P15-05 verdict (T15 + T12)
- **F2/E3 does not pass.** The rule needs a pass on both sets. T15 fails S4 (fluent-wrong 2 vs 0). T12 fails S1 (no significant WER gain) and passes S2-S4. T12 is a replication; it cannot change the T15 result.
- **What holds on two participants and two datasets:** the trust bound (point rate <= alpha in every arm), the null controls (0 / 300 everywhere), and the grounding check against swapped signals (0 commits in every grounded arm, against 2-28 without it).
- **What does not hold:** a stable WER gain from a 1.5B LLM (T15 yes, T12 no), and any protection against fluent-wrong commits on the true signal from a 95 %-coverage `tau`.
- **P15-05 is done:** all arms are reported on T15 and T12 with WER, sentence accuracy, wrong-commit rate, fluent-wrong commits and null / swapped commits, and compared with the pre-registered criteria.
- **Follow-up: P15-06** (commits `7abbff1`, `9a8bb14`; [results](../2026-11-16-p15-06-halluc-bound/results.md)) calibrates a fluent-wrong bound jointly with `tau_commit` and a word-level check. It has T15 results only. **P15-06 T12 still needs a T12 loader** in its own `run.py` (it reads the cached P15-05 T15 artefacts). The P15-05 T12 caches in `C:\Users\zhang\bci-data\derived\f2-e3-llm-grounding\t12\` now exist for it.
