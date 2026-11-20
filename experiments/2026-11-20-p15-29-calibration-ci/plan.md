---
title: P15-29 Safe WPM interval that includes the calibration draw - pre-registration
type: experiment
task: P15-29
updated: 2026-11-19
---

# P15-29: a safe-WPM interval that includes the calibration draw (pre-registration)

Written and committed **before** any number of this item was computed. Gap 103 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P15-29](../../wiki/questions/roadmap-standard.md#p15-29-safe-wpm-interval-that-includes-the-calibration-draw). Follow-up of [P15-26](../2026-11-19-p15-26-replication/plan.md) ([results](../2026-11-19-p15-26-replication/results.md)) and [P15-22](../2026-11-19-p15-22-llm-learned/plan.md).

## Problem
P15-22 and P15-26 report the safe WPM (`safe-wpm/0.1`) of the L1 guard (LLM rescoring arm B1 + learned commit score) with a **trial-bootstrap** 95 % CI. The decisions are fixed in that bootstrap. So the CI is conditional on one calibration. P15-26 found on T15, over five calibration draws, L1 values 4.91, 5.58, 6.00, 5.23, 5.83 (SD 0.44). That SD is about 2/3 of the trial-bootstrap half-width (about 0.66). The reported CIs leave this part out.

## Question
What is the 95 % interval of the L1 safe WPM v0.1 when it includes (1) the variation of the calibration sample and of the calibration split, and (2) the variation of the evaluation trials? Is its lower end above the no-BCI reference on T15 (4.02)?

## Method (primary): two-level bootstrap, fixed evaluation set

Evaluation set: fixed, as in P15-22 (T15 `val_eval`, 701 trials; T12 the 10 test sessions, 400 trials). Calibration set: as in P15-22 (T15 `val_select`, 722; T12 the 480-trial calibration pool).

**Outer level: calibration draws.** For draw k = 1, 2, ..., K:
1. Calibrate seed s_k = the first 8 hex digits of SHA-256(`"p15-29|<unit>|cal|<k>"`) as an integer (unit = `t15` or `t12`).
2. Split rule (same as `fidetype.trust.calibrate` and P15-26): o = `numpy.random.default_rng(s_k).permutation(n)`, `_split(n)` gives the parts fit (temperatures + conformal), policy grid, LTT. T15 n = 722: 180 / 271 / 271. T12 n = 480: 120 / 180 / 180.
3. Bootstrap of the calibration sample: inside each part separately, draw the same number of trials **with replacement** (rng = `default_rng` of the first 8 hex digits of SHA-256(`"p15-29|<unit>|boot|<k>"`)). The parts stay disjoint (no trial is in two parts).
4. Re-run the full guard calibration on this sample: `fidetype.trust.calibrate` with seed s_k, alpha 0.05, delta 0.1, `confidence="learned"` (`confidence_l2` 1.0), the commit gate, `null_trials` 300, `stream_texts` (phoneme targets). The input order is set so that the permutation of `calibrate` gives exactly the parts of step 3 (input position o[j] holds sample item j). So each draw re-fits the conformal threshold, the policy grid, the learned commit score and the LTT certification, and runs the null controls again.
5. Decide all evaluation trials with the new guard. Score `safe-wpm/0.1` (adopted, unchanged): measured trial durations, default correction rule, guarantee and controls from the guard sheet.

**Pipeline values are pinned** (stated limit): the frame temperature T, the grounding τ, the LLM weight λ and the fluent threshold stay at the P15-22 / P15-26 c0 values (T15: T 2.37015800035291, τ 0.06996627059278283, λ 1.0, fluent −7.88165954200173; T12: the committed P15-05 values T 2.528091520707864, τ 0.47419631304442217, λ 0.5, fluent −8.916451934532247). Reason: a new T changes every decoder input, so the decoder and the CPU LLM must run again on all trials (21-56 min per draw in P15-26). With pinned values all decodes of the real trials come from the cached P15-22 / P15-26 outputs (read only). Only the null-control inputs are new in each draw. Technique: inside `calibrate`, the frame-temperature fit returns the pinned T (a scoped swap of `fidetype.eval.harness.fit_frame_temperature`, as `fidetype.demo.live.emg_prepare` does). The guard checks that its frame temperature equals the pinned T.

**Inner level: trial bootstrap.** For each draw, the same B = 2,000 trial resamples of the evaluation set (multinomial weights from `numpy.random.default_rng(0)`, `integers(0, n, n)` per resample, as the P15-22 paired bootstrap). Decisions are fixed inside a draw.

**Credit rule per draw.** A draw adds its values only if its status is `certified`. A draw that is refused (a null control fails), `not-certified`, `above-alpha` or `vacuous` adds the value 0.0 for all B resamples (no certified words). The counts of each status are reported.

**Combined interval (primary).** Pool the K × B values. The interval is their 2.5th and 97.5th percentiles. The point value is the mean of the K draw values (each draw value = the full-evaluation-set safe WPM of that draw, or 0.0 by the credit rule). For K = 1 the interval is the conditional trial-bootstrap CI of P15-22.

**Number of draws.** Chosen by compute budget, fixed here: T15 K_max = 40, T12 K_max = 20. Draws run in a fixed order (k = 1, 2, ...). The analysis uses the longest prefix k = 1 ... K of finished draws at the earlier of (all draws done) and the cutoff **2026-11-20 06:00 local time**. Minimum K: T15 20, T12 10; if a minimum is not reached at the cutoff, the run goes on until it is. The cutoff and the minima never depend on a result.

## Cross-checks (reported, not decided)
- **X1 analytic variance decomposition.** Law of total variance: total variance = mean within-draw bootstrap variance + between-draw variance of the draw values (ddof 1). Normal interval: mean ± 1.96 × total SD. Also the ratio between-draw SD / within-draw SD.
- **X2 full-refit draws of P15-26.** The P15-26 draws c0, c1, c2, c3 use the same `val_eval` set and refit all pipeline values (T, τ, λ). Their per-trial decisions (read only, `derived/p15-26/c*/arm-llm_learned.json`) give the same combined interval with K = 4 (partition variation only, no resampling, but with the pipeline refit). p1 is left out (another evaluation set).
- **X3 effect of pinning.** Draws z1, z2, z3 = calibrate seeds 1, 2, 3 without resampling and with pinned values. They differ from the P15-26 c1, c2, c3 only by the pinned pipeline values. We report z_i − c_i.
- **X4 code check (must pass).** Draw z0 = seed 0, no resampling, pinned values. It must reproduce the P15-22 L1 decisions on T15 (701 / 701 same action and text; safe WPM 4.91) and the P15-26 T12 L1 decisions (400 / 400; 2.37). The library function with K = 1 on z0 must give the P15-22 conditional CI [4.25, 5.57]. A failed check stops that unit (no result from code that does not reproduce).

## Decision rule
Reference: the no-BCI reference of the evaluation set (T15 `val_eval` 4.0153; T12 4.1140, P15-26).

| outcome on T15 (primary) | verdict | what the headline may say |
|---|---|---|
| combined lower end > 4.0153 | **clearly above after calibration uncertainty** | "above gaze typing on T15; the interval includes the calibration draw" |
| mean > 4.0153 ≥ lower end | **above, but inside the combined interval** | the README must stop calling the T15 result "clearly above" |
| mean ≤ 4.0153 | **not above** | the T15 headline must change |

T12 (secondary): the same three-way verdict against 4.1140. Expectation (not a rule): T12 stays below 4.11 (P15-26: 2.37 [1.34, 3.62]).

Also reported: K used, statuses of the draws, the draw values (mean, median, SD, range), the fraction of draws above the reference, the mean commits and wrong commits, X1-X4.

## Library function (if the method works)
`fidetype.benchmark.safe_wpm.calibration_draw_interval(draws, n_words, n_chars, neural_s, ...)`: the combined interval above from per-draw `safe-wpm/0.1` decisions on one fixed evaluation set (credit rule, mixture percentiles, X1 decomposition). It is an **optional reporting addition**. It changes no adopted v0.1 rule or number. `docs/safe-wpm.md` gets a "proposed reporting addition" section; the user decides adoption. Tests cover: K = 1 equals the trial bootstrap, the credit rule, input checks, the decomposition.

## Order, limits, outputs
1. Commit this plan. Then commit `run.py`, `launch.py`, the library function and its tests (full pytest), and a smoke run on calibration subsets only (it never reads an evaluation set).
2. Run detached: one launcher, two worker processes (`python -m fidetype.utils.isolation run --class background --threads 4 -- python -I run.py worker <w>`), CPU only, no GPU. Job order: T15 z0-z3, T15 k 1-20, T12 z0, T12 k 1-10, T15 k 21-40, T12 k 11-20; worker w takes every second job. Each worker has its own copies of the caches. Keep-awake inside each worker.
3. Resumable: each finished draw is saved as `C:\Users\zhang\bci-data\derived\p15-29\<unit>\draw-<k>.json` and skipped on a rerun (a sleep loses at most one draw). Log + `DONE` file.
4. Per-trial decisions (with text) stay in the derived folder. The repo gets `results/results.json` (aggregates and per-draw summaries, no text) and `results/run.log`.
5. No change of the method, K rule, references or decision rule after this commit. Any later variant is a new item.

Known limits (stated before any result): (a) pinned pipeline values: the interval leaves out the variation of T, τ, λ (X2 and X3 show its size); (b) bootstrap duplicates inside the LTT part make the LTT test see n = 271 items that are not all distinct; this mimics the sampling variation of the calibration set, but a single draw's certificate is not a valid certificate; (c) one participant per unit, one decoder checkpoint; (d) the evaluation set is the same in every draw, so the evaluation-trial variation comes only from the inner bootstrap.
