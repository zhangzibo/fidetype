---
title: P5-35 native calibrate path for external per-prefix scores - results
type: experiment
task: P5-35
updated: 2026-11-21
---

# P5-35: the P11-16 LX-FL guard through `calibrate(prefix_score=...)` (results)

Code: [run.py](run.py). Counts: [results/results.json](results/results.json). Library: `fidetype.trust.FrozenPrefixScore` ([external_score.py](../../src/fidetype/trust/external_score.py)), `calibrate(..., commit_unit="prefix", prefix_score=)`, `load(..., prefix_score=)`. Docs: [trust-guarantee.md section 10b.1](../../docs/trust-guarantee.md).

**RESEARCH ONLY** (emg2qwerty data: CC BY-NC-SA 4.0). This page and `results.json` hold counts only: no text, no per-user value, no id. The P11-16 code and its derived files were read only (the window memo was loaded and never saved). The guard file is in `C:\Users\zhang\bci-data\derived\p5-35\` (not committed).

Run: 2026-11-21 09:18 to 09:20, CPU only (isolation class `background`, 2 threads). No GPU. Run time 146 s (calibrate 57 s).

## Outcome
**Pass. The native path reproduces LX-FL exactly: same threshold 0.86, same LTT record, same null-control counts, and the same decisions on all 3 x 1,221 test prompts. The guard now has a `TrustGuard` file, a guarantee sheet and `config_id` `tcfg-618d4ca57bb9326b`.**

## What was run
1. The frozen P11-16 LX-FL model (sign-constrained logistic on 11 features per prefix, fitted by P11-16 on the fit + policy-grid items of the seed split) was wrapped as a `FrozenPrefixScore` (name `p11-16-LX-FL`, version 1, digest `pfx-1b156e8ff596d88c22840bd2`). The spec holds the model weights and the FL decoder settings. The function returns no score if the FL analysis fails or if its top-1 words differ from the guard's top-1 words.
2. `fidetype.trust.calibrate` with the P11-16 BX-FL settings (same 1,224 calibration windows, seed, alpha 0.05, delta 0.1, decoder `GuardFn("BL-FL")`, 300 user null inputs) and `commit_unit="prefix", prefix_score=score`. Calibrate fitted no score.
3. Decisions with the new guard on the 1,221 track-test prompts (real, time-shuffled, zero EMG), compared with `decisions-LX-FL.json` of P11-16. Then save, reload with the same score, and decide again.

## Checks
| Check | Native path | P11-16 | Result |
|---|---|---|---|
| Threshold | 0.86 | 0.86 | equal |
| LTT items, empirical risk, p-value, commit rate | 459, 0.03268, 0.04882, 0.5447 | 459, 0.03268, 0.04882, 0.5447 | equal |
| Null controls (commits of 300; limit 15) | uniform 0, shuffled 5, user 0 | 0, 5, 0 | equal, pass |
| Real prompts: commits (prefix), wrong | 671 (592), 46 | 671 (592), 46 | equal |
| Same commit text and word count | 1,221 / 1,221 real; 1,221 / 1,221 time-shuffled; 1,221 / 1,221 zero EMG | | equal |
| Same action (commit / offer / withhold) | 1,221 / 1,221 for each input kind | | equal |
| Time-shuffled and zero-EMG commits | 0 and 0 | 0 and 0 | equal |
| Commit gate | 0 LTT items blocked; 0 top-1 word mismatches; 0 failed analyses | | |
| Reload with the same score | 1,221 / 1,221 same decisions (real) | | equal |
| Reload without the score | `ValueError` | | refused |
| Old guards unchanged | default n-best, learned sentence, learned prefix and logits guards: same `config_id` and same file content (without the time stamp) as the code at `9e039c7` | | equal |

Other sheet facts: in-sample LTT 250 commits, 15 wrong; 52 of the 459 LTT items have no score (no top-1 text). Frame temperature 1.0 (not fitted: own `decode_fn`, no `stream_texts`; as BX-FL). The P5-31 offer null control fails in warn mode (shuffled 60 / 300 offers vs real 157 / 459), as for the other EMG guards. This does not change commits or the bound.

> **Our take:** the external path adds what LX-FL lacked (a guard file, a sheet, a `config_id`, the library controls inside `calibrate`) and changes no decision. It does not add a frame temperature for LX-FL: the FL decoder is a user `decode_fn`, so the temperature stays 1.0 unless `stream_texts=` is given. The guard-risk gate is now on, but it blocked no LTT item and no test commit here. The value claims of P11-16 (proposed safe WPM v0.2 9.47 for one calibration) are unchanged, because the decisions are the same.
