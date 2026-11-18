---
title: P14-21 downstream T15 rows with word-decoder edit penalty 8 - results
type: experiment
task: P14-21
updated: 2026-11-18
---

# P14-21: results

Pre-registration: [plan.md](plan.md) (commit `095150c`, before any run). Script: [run.py](run.py) (stages `r1`-`r6`, `compare`, `queue`), launcher [launch.py](launch.py). Numbers: [results/p14-21.json](results/p14-21.json) (every metric: committed, edit-12 reference, edit 8, half-width, decision). Local only: `C:\Users\zhang\bci-data\derived\p14-21\` (guards, decisions, n-best caches, score cards, collector outputs, logs). CPU only: one hidden queue, background class, 4 threads, 2026-11-17 21:44 to 2026-11-18 10:06. Without the replays the stages took 2 h. The R6 replays took 13 h, because the machine slept during one of them.

Setting: the B2T '25 word decoder with lm 1.0, edit 8 and bonus 3. The reference runs use the paper point, edit 12. A wrapper on `PhonemeWordDecoder.__init__` changes only the paper point. Every stage logged one changed decoder, and the built decoder had the requested edit penalty.

## Decisions (pre-registered rule: effect = a primary metric moves by its 95 % CI half-width or more)
**Overall: effect.** 11 of 71 decided metrics move by their half-width or more. The 11 effects come from three rows: R2 (4), R3 (6) and R5 (1). R1 and R4 show no effect. R6 is not used, because its reference replay was interrupted (see Checks).

| row | decided metrics | effects | short result |
|---|---|---|---|
| R1 P14-05 safe WPM (M4-13, M4-12) | 7 | 0 | **M4-13: 2.23 → 2.28** (certified; 104 → 99 commits, 17 → 15 wrong). M4-12: 2 → 0 commits, value 0 → 0 |
| R2 M4-13 eval, frozen M2-19 configs | 16 | 4 | gated: **91 → 12 commits, 11 → 1 wrong**; eWPM 9.94 → 9.72 (no effect) |
| R3 M2-19 refit + eval | 22 | 6 | dedicated_0 LTT / CRC: 9 → 21 commits, 6 → 15 wrong; shared LTT: 9 → 28, 7 → 18; all still under α = 0.05 |
| R4 v0.2 partial entries (103 units) | 16 | 0 | M4-13: safe WPM 4.07 → 3.47 [2.26, 4.88], 19 → 18 commits, 3 → 4 wrong; M4-12: 0 commits both |
| R5 P5-02 T15 | 10 | 1 | base guard: units that can commit at commit_p 0: 673 → 0 (701); all 4 precision targets stay infeasible, 0 commits |
| R6 P3-08 replays | 0 (not used) | — | reference replay interrupted; edit-8 numbers below are for information only |

**Gap 53 (P14-23) answer: no.** Edit 8 does not move the M4-13 T15 safe WPM toward the no-BCI 4.02. On 701 `val_eval` trials it is 2.28 (certified; wrong-commit 0.0214, CP95 [0.012, 0.035]; error among commits 0.152). The change is +0.058, and the half-width is 0.46. The partial v0.2 entry goes down: 4.07 → 3.47, which is below its no-BCI 4.12, but the change is inside its CI.

## Checks (before any edit-8 result of a row was read)
| row | edit-12 reference vs committed |
|---|---|
| R1 | M4-13 and M4-12 blocks reproduced exactly (value, status, commits, wrong). Config ids equal the committed ones |
| R2 | all word-quality, trust, always-commit and control numbers reproduced; committed M4-13 word cache read only, 0 misses |
| R3 | all 3 config ids, λ̂, final commit_p, eval rows, baselines and controls reproduced; committed M2-19 cache read only, 0 misses |
| R4 | both score cards (all metrics, CIs, safe WPM) and stage info (616 calibration units, 103 scored) reproduced |
| R5 | base counts and all 4 targets reproduced |
| R6 prep | both decoders: all 722 + 701 + 200 n-best lists equal the committed local files; guard sheets equal (M4-13 `tcfg-aee7fe896ecfca23`, threshold 0.74; M4-12 `tcfg-c5fd95a99143f814`, 0.3) |
| R6 replay (M4-13) | **not reproduced.** The machine slept during the reference replay. Wall time was 33,053 s against a 2,172 s stream. The bench stopped on its `duration` limit after 27 of 120 decisions (3 COMMIT / 24 OFFER, 0 wrong), so the run is incomplete. The decisions it did make do not contradict the committed run, but the plan rule applies: R6 is stopped and not used. M4-12 depends on this replay, so it is not used either |

## R1: P14-05 safe WPM (guard recalibrated on `val_select` with edit 8)
| decoder | committed (edit 12) | edit 8 | half-widths |
|---|---|---|---|
| M4-13 | 2.23 certified; 104 commits, 17 wrong; commit threshold 0.73 | **2.28 certified**; 99 commits, 15 wrong; threshold 0.58 | safe WPM 0.46; commit rate 0.026; wrong-commit 0.012; error among commits 0.071 |
| M4-12 | 0.0 certified; 2 commits, 2 wrong | 0.0 vacuous; 0 commits | commit and wrong-commit rate 0.0048 |

The M4-12 change matches P14-18 (P14-03: 2 wrong commits → 0).

## R2: M4-13 eval with the frozen M2-19 configs (decoder changed, configs not refitted)
| metric | committed | edit 8 | half-width |
|---|---|---|---|
| WER T = 1 / config T | 0.1880 / 0.1874 | 0.1925 / 0.1932 | 0.015 |
| sentence exact T = 1 | 0.365 | 0.350 | 0.036 |
| truth in n-best T = 1 | 0.526 | 0.531 | 0.037 |
| gated `tcfg-4e6143e37d1642f3`: commits / wrong | 91 / 11 | **12 / 1** | commit rate 0.025, wrong-commit 0.0095 |
| gated eWPM | 9.94 | 9.72 | 0.51 |
| ungated: commits / wrong, eWPM | 92 / 11, 9.94 | **12 / 1**, 9.72 | as above |
| always commit: wrong-commit rate, eWPM | 0.632, 9.90 | 0.648, 9.70 | 0.036, 0.58 |

- Null controls (300 trials): gated uniform 0 → 0 and frame-shuffled 0 → 0, so they still pass.
- The edit-8 n-best gives a lower top-1 probability (P5-02 items: mean `p_top1` 0.160 → 0.142). So fewer trials pass the frozen commit threshold.
- **Secondary (not decided):** the "whole chain" variant uses the edit-8 M2-19 `dedicated_0` LTT config (from R3) with the same commit gate (`tcfg-f410c34a141b762c`). It gives 103 commits, 18 wrong (0.0257, CP95 [0.015, 0.040]), error among commits 0.175 and eWPM 9.77.

## R3: M2-19 refit on `val_select` with edit 8
| condition | committed: commits / wrong (CP95 upper), eWPM | edit 8 | λ̂ / final commit_p |
|---|---|---|---|
| dedicated_0 LTT | 9 / 6 (0.019), 6.03 | **21 / 15** (0.035), 6.01 | 0.33 / 0.4 → 0.27 / 0.3 |
| dedicated_0 CRC | 9 / 6, 6.03 | **21 / 15**, 6.01 | 0.31 / 0.4 → 0.26 / 0.3 |
| shared LTT | 9 / 7, 5.94 | **28 / 18** (0.040), 5.91 | 0.33 / 0.4 → 0.29 / 0.3 |
| old frozen (M4-06 config), both decoders | 0 commits | 0 commits | — |

- The held-out wrong-commit rate stays under α = 0.05 in every condition, so the guarantee holds. With edit 8 the refit commits more, but most of the extra commits are wrong: error among commits is 0.64-0.71. This change is not an effect, because its half-width is about 0.25.
- Controls (300 trials, dedicated_0 LTT config, no commit gate): frame-shuffled 0 → **3 commits**, and uniform 186 → 211. This config never had a gate. M4-13 and later rows use the M2-18 gate, and with the gate these controls stay at 0 (R2).

## R4: v0.2 partial entries (103 scored `val_eval` units)
| entry | metric | committed | edit 8 | half-width (card CI) |
|---|---|---|---|---|
| `b2t25-t15__m4-13__guard` | CER / WER | 0.067 / 0.113 | 0.081 / 0.128 | 0.016 / 0.025 |
| | eWPM | 12.83 | 12.12 | 1.69 |
| | commits / wrong | 19 / 3 | 18 / 4 | commit rate 0.056, wrong-commit 0.024 |
| | safe WPM | 4.07 [2.51, 5.74] | 3.47 [2.26, 4.88] | 1.61 |
| `b2t25-t15__m4-12__guard` | CER / WER, eWPM | 0.204 / 0.300, 7.33 | 0.210 / 0.304, 7.23 | 0.020 / 0.029, 0.67 |

The commit threshold of the M4-13 guard goes from 0.51 to 0.39. The committed cards in `benchmark/results/v0.2/` are not changed.

## R5: P5-02 precision guarantee, T15
- With edit 8, the base guard's grid fit picks `commit_max_risk` 0.1 (was 1.0). Its LTT threshold is 0.0 (was 0.22), and the sentence temperature is 12.61 (was 11.96). So at commit_p 0 the guard gate blocks every held-out unit: 673 → 0 of 701 can commit. This is the one effect in R5.
- Top-1 right: 59 → 54 of 701 (no effect). The 4 precision targets (0.5 / 0.8 / 0.9 / 0.95) stay infeasible with 0 commits. The resampling finds no feasible draw. The P5-02 conclusion ("no T15 precision target is feasible with this decoder") does not change.

## R6: P3-08 collector replays (information only; not used)
| decoder | committed | edit-12 reference | edit 8 |
|---|---|---|---|
| M4-13 | 16 COMMIT / 104 OFFER, 3 wrong; p95 added 1.97 ms | interrupted: 3 / 24 of 120, 0 wrong | 18 / 102, 4 wrong; p95 added 2.23 ms; Trust-ready |
| M4-12 | 0 / 120 | no reference replay (plan) | 0 / 120; p95 added 2.56 ms; Trust-ready |

I saw the edit-8 numbers in the same printout that showed the failed reference. They do not enter any decision. New gap 63 reruns the comparison on a machine that cannot sleep during the replay.

> **Our take:** edit 8 is not a free improvement for the trust rows. Its word-level gains (P14-18) are small, and on M4-13 the WER is slightly worse (0.188 → 0.193, inside the CI). The effects are trust effects, and they come from a mismatch. A config fitted on the edit-12 n-best commits far less on edit-8 n-best (R2), and a refit on edit-8 n-best commits more but mostly wrong (R3). Both stay inside α, so no guarantee breaks. The committed rows are therefore not optimistic for the main safety claim. They are setting-dependent in commit volume. For gap 53 the result is clear: the word-decoder setting is not the limit. M4-13 + guard stays near 2.2-2.3 safe WPM because only 14 % of trials commit and 15-16 % of those are wrong. A better acoustic model or a better guard input is needed (P14-23).

## Deviations from the plan
- **Comparator fix before the write-up.** In its first pass, `compare` counted R1 M4-12 safe WPM 0 → 0 as an effect. The trial-bootstrap CI of a constant 0 has zero width, and the test `|Δ| ≥ hw` is true when both are 0. We fixed the test so that a change of exactly 0 is never an effect. The fixed pass also marks rows whose reference failed as "not used". The saved outputs were not rerun. The table above uses the fixed pass. The overall decision ("effect") is the same in both passes.
- **R6.** The reference replay was interrupted by machine sleep and was not rerun in this item (the plan stops the row). Gap 63 registers the rerun. Note: the queue holds no keep-awake. The P3-08 bench measures wall time, so a future replay needs `SetThreadExecutionState` or a machine with sleep disabled.
- No other deviation.

## New gaps
- **62 = P14-24:** P15-05, P15-06, P15-07 and the M4-13 trust-rerun rows (P5-02 / P15-03 / F2 on M4-13) with edit 8. The LLM arms need more than 1.5 GB RAM. The trust reruns were pre-registered with edit 12 and were not committed when this item started; their edit-12 results are now written up ([summary](../../wiki/questions/m4-13-trust-reruns.md)).
- **63 = P14-25:** P3-08 collector replays with edit 8, with a keep-awake. The reference replay of this item was interrupted.

## Limits
- One participant and one split. CI half-widths are conditional (Wilson / trial bootstrap), as in P14-15 / P14-18.
- R2 keeps the frozen configs by design (P14-18 precedent). It measures a decoder swap under a fixed config, not a retuned system. The secondary chain variant is the retuned view.
