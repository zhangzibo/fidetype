---
title: "Frontier write-up: decoder quality, M4-12 to M4-13, and what it did to the guarantees"
type: question
tags: [frontier, decoder, t15, emg, p11-01, m4-12, m4-13, trust, usefulness, write-up, negative-result, pre-registration]
sources: [brain-to-text-25-copytask]
updated: 2026-11-19
---

# Decoder quality: did a stronger decoder turn safe-but-useless guarantees into useful ones?

Write-up for roadmap item [P15-12](roadmap-standard.md#p15-12-frontier-result-write-ups). It covers the two T15 decoder runs M4-12 and M4-13 and their effect on the F1 / F2 trust results. Details of the trust reruns are in [M4-13 trust reruns](m4-13-trust-reruns.md).

## Question
Our early trust results were safe but useless: the guards almost never committed, because the decoder top-1 was rarely right. Is the decoder the main limit? If we train the causal T15 decoder close to the published recipe, do the same pre-registered trust methods give useful operating points?

## Short answer
- **M4-12 failed its pre-declared "close" rule.** Greedy PER 0.2574 vs published 0.101 (rule: within 0.05). The main cause was too little training (12.5 % of the published trial passes).
- **M4-13 passed it.** With 91 % of the published trial passes, greedy PER is 0.1210 (published 0.101; rule limit 0.151). The decoder stays causal (no lookahead, causal smoothing).
- **The guarantees became useful on T15, without a method change.** The precision guarantee went from 0 commits to 104 (precision 0.837); the fluent-wrong bound from 0 commits to 36 (34 right).
- **Not on T12.** The T12 decoder did not change, and its certificates still give 3 commits.
- **One defect was not fixed by a better decoder:** the update gate under partial feedback (see [E2 write-up](frontier-e2-self-teaching.md)).

## Pre-registration and design

| run | plan | design | GPU time |
|---|---|---|---|
| M4-12 | [plan](../../experiments/2026-11-14-m4-12-decoder-retrain/plan.md), `c34b087` | published-like recipe, 10,000 steps x batch 96, LR 5e-3 cosine, AdamW eps 0.1, dropout and noise as published; 5 lookahead settings | about 3.8-4.1 h per run |
| M4-13 | [plan](../../experiments/2026-11-15-m4-13-long-train/plan.md), `01cea4b` | M4-12 recipe at L 0, 115,000 steps x batch 64 (about 6.97 M trial passes, 91 % of the published 7.68 M) | 40.56 h |

Data: Brain-to-Text '25, participant T15 (CC0). Model `fidetype.decoders.lookahead_gru`. Held out: `val_eval` (701 odd-index `val` trials); checkpoint selection on `val_select` (722).

## Results (val_eval, 701)

| measure | M4-01 (before) | M4-12 dedicated L 0 | **M4-13** | published |
|---|---|---|---|---|
| greedy PER | 0.6954 | 0.2574 | **0.1210** | 0.101 (validation); 0.0954 (online output) |
| WER (T = 1, our word decoder) | 0.9307 | 0.3998 | **0.1880** | - |
| sentence exact | - | 0.090 | **0.365** | - |
| pre-declared "close" rule (<= 0.151) | - | **fail** | **pass** | - |

The M4-13 val_select curve is flat after about 75 % of the budget (0.1211 → 0.1204). The remaining 0.020 gap can come from the centred smoothing of the published decoder (about 80 ms of future input) or recipe details. We did not test these separately.

## What the stronger decoder did to the trust results
All rows use methods fixed before M4-13 existed (pre-registration `97a2fc4` for the reruns).

| result | M4-12 | M4-13 | page |
|---|---|---|---|
| frozen M2-19 guard + commit gate | 7-9 commits of 701, most wrong | 91 commits, 11 wrong; eWPM 9.94 vs gaze 4.02 | [M4-13 results](../../experiments/2026-11-15-m4-13-long-train/results.md) |
| precision guarantee, target 0.5 (P5-02) | no threshold certified, 0 commits | 104 commits, 17 wrong, precision 0.837 [0.751, 0.902]; P1-P3 pass | [P5-02 rerun](../../experiments/2026-11-17-p5-02-precision-m4-13/results.md) |
| precision targets 0.8 / 0.9 / 0.95 | infeasible | **still infeasible** | same |
| LLM rescoring + grounding (P15-05 B1) | WER 0.3831; 10 commits | WER 0.1617; 154 commits, 12 wrong | [E3 write-up](frontier-e3-hallucination.md) |
| fluent-wrong bound (P15-06 B1) | 0 commits (vacuous) | 36 commits, 34 right | same |
| safe WPM, drop-in guard (`safe-wpm/0.1`) | 0.00 | 2.23 (no-BCI 4.02) | [safe-WPM write-up](frontier-safe-wpm.md) |
| update gate with partial feedback | broken decoder accepted (dry run) | worse and broken decoders accepted (H2, H3 fail) | [E2 write-up](frontier-e2-self-teaching.md) |

**Negative results, stated plainly.**
- M4-12 missed its target by a factor of about 2.5 in PER.
- Precision targets of 0.8 or more are still not certifiable with 271 LTT items on M4-13 (gap 58).
- Certified safe WPM on M4-13 (2.23) is still below gaze typing (4.02).
- An incident: the M4-12 accuracy stage overwrote the 8 M4-01/02 per-trial trust files (shared folder, same file names). Their aggregates survive in the committed results. `run.py` now writes to its own folder.

## What changed in the library
- No trust method changed. The decoder module `fidetype.decoders.lookahead_gru` is unchanged; only the training recipe changed.
- Checkpoints and log-probs stay outside the repo (`C:/Users/zhang/bci-data/derived/`).

## Limits
- One participant, one seed, one training run each. No run-to-run spread.
- The word decoder settings were tuned on the online logits (M2-10). P14-21 later reran the downstream rows with settings tuned without `val_eval` trials; no guarantee broke.
- The HDF5 `train` partition holds part of the benchmark track test trials ([T15 split audit](t15-split-audit.md)); the `val_eval` results here are not affected.

> **Our take:** decoder strength was the main limit for the precision and hallucination guarantees. The methods did not change; only the decoder log-probs did. The gate defect and the gap to gaze typing need other levers (gate design, commit design, metric), not only a better decoder.

## Still open
| gap | item | what |
|---|---|---|
| 14 | [P15-19](roadmap-standard.md#p15-19-show-usefulness-on-stronger-decoders-p5-01-p15-02-p5-02-p15-06) | usefulness on stronger decoders (P5-01 on M4-13; all on P11 decoders) |
| 58 | [P5-20](roadmap-standard.md#p5-20-certified-precision-at-a-useful-target-08-or-more) | certified precision 0.8 or more |
| 70 | [P14-27](roadmap-standard.md#p14-27-cost-of-causal-smoothing-on-t15-and-the-decoder-accuracy-target) | cost of causal smoothing; decoder accuracy target |
| 29 | [P14-14](roadmap-standard.md#p14-14-t12-safe-wpm-above-the-no-bci-reference) | a stronger T12 decoder |
| 32 | [P6-09](roadmap-standard.md#p6-09-full-coverage-m4-x-entry-on-b2t25-t15-without-train--test-overlap) | M4-x benchmark entry without train / test overlap |

## Second modality: the EMG decoder (P11-01, 2026-11-19)
The same question for wrist EMG. P11-01 trained our own causal CTC decoder on [emg2qwerty](../entities/emg2qwerty.md) (research only, NC data). Pre-registration: [plan](../../experiments/2026-11-16-p11-01-emg-decoder/plan.md); results: [P11-01 results](../../experiments/2026-11-16-p11-01-emg-decoder/results.md).

| measure (test, greedy CTC, no LM, our 8-user split) | ours | published, no LM (Table 3) |
|---|---|---|
| generic CER, mean ± SD over 8 users | 53.52 ± 15.31 % | 55.38 ± 4.10 % |
| personalised (fine-tuned) CER | **15.09 ± 6.54 %** | 11.28 ± 4.45 % |
| time-shuffled control | 0.986 | - |
| emission delay, median / p90 | 70 / 110 ms (no lookahead) | - (their model uses 100 ms of future input) |

- Pre-registered primary rule S1 (<= 20.0 %) **passes**. The stretch rule S1+ (<= 11.28 %) **fails**.
- The generic model overfits after step 30,000 of 150,000. A longer run would not help (gap 88).
- No trust result exists yet on these streams. A trust config (gap 89) is the next step. It tests whether the M4-13 effect (a stronger decoder makes the guarantees useful) also holds on EMG.

> **Our take:** a second modality now has a decoder in the useful range. The trust-layer claims can be tested on EMG, not only on T15. The EMG weights cannot ship (NC data); a licence-clean decoder is gap 86.

| gap | item | what |
|---|---|---|
| 86 | [P11-06](roadmap-standard.md#p11-06-licence-clean-causal-convctc-on-kt-semg-and-toronto) | licence-clean EMG decoder |
| 87 | [P11-07](roadmap-standard.md#p11-07-ctc-beam-search-with-a-character-lm-for-the-emg-decoder) | LM + beam search for EMG |
| 88 | [P11-08](roadmap-standard.md#p11-08-emg-decoder-accuracy-to-the-published-fine-tuned-no-lm-cer) | accuracy to 11.28 % |
| 89 | [P11-09](roadmap-standard.md#p11-09-trust-config-and-streaming-replay-for-the-p11-01-emg-streams) | trust config + streaming replay on EMG |

## Related pages
[Lookahead vs accuracy and latency](lookahead-latency-accuracy.md), [M4-13 trust reruns](m4-13-trust-reruns.md), [Brain-to-Text '25 copy task](../sources/brain-to-text-25-copytask.md), [north star](north-star.md), [emg2qwerty](../entities/emg2qwerty.md).
