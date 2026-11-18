---
title: M4-13 long decoder training run - results
type: experiment
task: M4-13
updated: 2026-11-17
---

# M4-13: long training run of the causal T15 decoder (L 0)

Plan (committed before training, `01cea4b`): [plan.md](plan.md). Settings: [config.json](config.json). Numbers: [results/eval.json](results/eval.json) (aggregates only), [results/eval.log](results/eval.log), val_select curve [results/val_select_curve.jsonl](results/val_select_curve.jsonl). Wiki: [lookahead vs accuracy and latency](../../wiki/questions/lookahead-latency-accuracy.md#m4-13-long-training-run-2026-11-17-l-0).

Data: Brain-to-Text '25, participant T15 (CC0). Model: `fidetype.decoders.lookahead_gru`, dedicated L 0 (causal, no lookahead), causal smoothing. Recipe: M4-12 plus 115,000 steps x batch 64 (about 6.97 M trial passes, 91 % of the published 7.68 M), cosine LR 5e-3 -> 1e-4 over the full budget.

## Headline
| measure (val_eval, 701 trials) | M4-12 dedicated L 0 | **M4-13** | published |
|---|---|---|---|
| greedy PER | 0.2574 | **0.1210** (2,392 edits / 19,765 phonemes) | 0.101 (validation partition, baseline README); 0.0954 (online copy-task output) |
| WER (T = 1, our word decoder) | 0.3998 | **0.1880** | — |
| CER (T = 1) | — | 0.1193 | — |
| sentence exact (T = 1) | 0.090 | **0.365** (256/701) | — |
| truth in n-best (T = 1) | — | 0.526 | — |

- **"Close" by the pre-declared rule: YES.** 0.1210 <= 0.151 (0.101 + 0.05). The gap to 0.101 is 0.020 (1.20x). Against the online output 0.0954 it is 1.27x.
- PER fell by 0.136 against M4-12 (53 % relative).
- Word decoder at the config frame T (1.2385): WER 0.1874, sentence exact 0.368.

## Training
| fraction | step | val_select greedy PER |
|---|---|---|
| 5 % | 5,750 | 0.2548 |
| 10 % | 11,500 | 0.1900 |
| 15 % | 17,250 | 0.1603 |
| 20 % | 23,000 | 0.1471 |
| **25 %** | 28,750 | **0.1392** |
| 35 % | 40,250 | 0.1300 |
| **50 %** | 57,500 | **0.1252** |
| 65 % | 74,750 | 0.1229 |
| **75 %** | 86,250 | **0.1211** |
| 90 % | 103,500 | 0.1209 |
| **100 %** | 115,000 | **0.1204** (best = last; decoded) |

- val_select (722 even-index `val` trials) and val_eval agree (0.1204 vs 0.1210).
- The curve is flat after about 75 % (0.1211 -> 0.1204). More steps of this recipe would give little.
- Train CTC loss: 0.159 at 25 %, 0.063 at 50 %, about 0.040 at the end. val_select CTC loss (sum per trial) was lowest at 20 % (16.85) and rose to 19.73 at the end, while greedy PER kept falling. So the model became over-confident on its errors (overfitting in the loss), but its top-1 path still improved to the last step.
- GPU time: 40.56 h of training (mean 1.27 s per step), plus 25 s decode and 5 min CPU evaluation. Wall time 2026-11-15 14:56 to 2026-11-17 09:31, with one pause of 1.7 h (step 1,974; the user needed the GPU). The resume continued at the exact step.

## Trust (M2-19 config, NOT refitted; val_eval 701)
| config | commits (rate) | wrong-commit (rate) [CP95] | error among commits [CP95] | empty commits | eWPM | stream = batch |
|---|---|---|---|---|---|---|
| **M2-19 LTT + M2-18 commit gate** `tcfg-4e6143e37d1642f3` | **91 (0.130)** | **11 (0.0157) [0.0079, 0.0279]** | 0.121 [0.062, 0.206] | 0 | **9.94** | 701/701 |
| M2-19 LTT, no gate `tcfg-e7e8c472f6d9ab33` | 92 (0.131) | 11 (0.0157) [0.0079, 0.0279] | 0.120 | 0 | 9.94 | 701/701 |
| always commit | 701 | 443 (0.632) | — | — | 9.90 | — |
| gaze typing alone | — | — | — | — | 4.02 | — |

- The LTT guarantee (alpha 0.05) holds on this draw: wrong-commit 0.0157, CP95 upper 0.0279 < 0.05.
- With the M4-12 decoder the same config committed 7 to 9 of 701 trials (most wrong). Now it commits 13 % of trials, and 88 % of the commits are right.
- eWPM 9.94 against 6.03 (M2-19), 9.90 (always commit) and 4.02 (gaze).
- The config was fitted on the M4-12 decoder, so it is conservative for this decoder (a frame T and a commit threshold from a worse model).

### Null controls (300-trial draw of val_eval, seed 0)
| input | gated: commits | ungated: commits (empty) |
|---|---|---|
| real | 39/300 | 39/300 |
| frame-shuffled | **0/300** | 2/300 (0 empty; both wrong) |
| uniform (jitter 0.05) | **0/300** | 186/300 (162 empty) |

The gated config passes both controls (the 2026-11-15 rule). Without the gate, uniform input commits 186/300 again, and frame-shuffled input commits 2/300.

## Our take
> **Our take:** The gap to the published decoder was mostly training length. With 91 % of the published trial passes, the causal decoder (no centred smoothing, no lookahead) reaches PER 0.1210 against 0.101. The remaining 0.020 can come from the centred smoothing of the published decoder (about 80 ms of future input), 4-days-per-batch sampling, or recipe details. We did not test these separately.

> **Our take:** The trust layer now has value. The frozen M2-19 config with the gate commits 13 % of trials with 12 % error among commits, and the user rate rises from 4.02 (gaze) to 9.94 eWPM. Always-commit gives almost the same eWPM (9.90) but 63 % wrong commits, so the trust layer gives the same speed with 40x fewer wrong commits. A re-tune on this decoder (with the gate and both controls, per the 2026-11-15 rule) should commit more.

> **Our take:** The decoder is no longer the main limit for the trust results. The next steps: re-tune trust on this decoder (val_select only), re-check lookahead with this recipe if GPU time allows, and test centred vs causal smoothing to measure the cost of the real-time rule.

## Limitations
- One participant, one seed, one training run. No run-to-run spread.
- val_select chose the checkpoint, but best = last step, so there was no real choice.
- The trust config was fitted on another decoder (M4-12). The word decoder settings were tuned on the online logits (M2-10).
- Error among commits has a wide CI (91 commits).
- The guarantee is for the mix of 41 sessions, not per session.

## Deviations from the plan
- None in the recipe, budget or evaluation after the plan commit.
- 4-days-per-batch sampling was not used (smoke-tested before the plan: 5.4-6.0 s per step, not feasible; recorded in the plan).
- One pause on user request (step 1,974, 15:41-17:25 on 2026-11-15), resumed from `latest.pt`.
- Claude Code stopped the agent's wait loop twice because the system was low on memory. The training job was not affected.

## Note 2026-11-18: P14-21 rerun with word-decoder edit penalty 8

P14-21 ([results](../2026-11-17-p14-21-edit8-rows/results.md)) reran this evaluation with the word decoder at edit penalty 8 (frozen M2-19 configs kept). Reference (edit 12) reproduced every number. **Effect on the trust rows:** gated config 91 -> 12 commits, 11 -> 1 wrong (commit-rate half-width 0.025); eWPM 9.94 -> 9.72 (no effect); WER T = 1 0.188 -> 0.193 (no effect); gated null controls still 0 / 300. The frozen config was fitted on edit-12 n-best lists; edit-8 lists have lower top-1 probability, so fewer trials pass. With the edit-8 M2-19 config + gate: 103 commits, 18 wrong (CP95 upper 0.040), eWPM 9.77. The numbers above stay as committed.
