---
title: P14-21 downstream T15 rows with word-decoder edit penalty 8 - pre-registration (addendum to P14-15 / P14-18)
type: experiment
task: P14-21
updated: 2026-11-17
---

# P14-21: downstream T15 rows with edit penalty 8 (pre-registration)

Written and committed **before** any run of this item. Addendum to the P14-15 plan ([plan.md](../2026-11-17-p14-15-retune/plan.md), commit `fc8478c`) and the P14-18 / P14-19 plan ([plan.md](../2026-11-17-p14-18-19-followups/plan.md), commit `3d07cb4`; [results](../2026-11-17-p14-18-19-followups/results.md)). Gap 50 of the [open-gap list](../../wiki/questions/open-gaps.md). CPU only (background class, 4 threads, one process at a time, RAM under 1.5 GB). No GPU.

**Why.** P14-15 (T2a): without the 16 `val_eval` tune trials, the tune rule picks **lm 1.0, edit penalty 8, bonus 3** for the B2T '25 word decoder (paper point: edit 12). P14-18 found 14 of 166 M4 metrics move by their CI half-width with edit 8, all in favour of edit 8. Here we rerun the downstream T15 rows that decode `val_eval` with this word decoder.

**What changes.** Only `edit_penalty` of the B2T '25 word decoder (`experiments/2026-11-10-b2t25-trust` `Decoders`, `PhonemeWordDecoder`): 12 → 8. lm weight 1.0 and bonus 3 stay. Log-probs, frozen trust configs, user model, seeds and code stay fixed. A step that *calibrates or fits* a guard or trust config as part of the row (M2-19 fit, P14-05 / P6-02b / P5-02 / P3-08 guard calibration on `val_select`) is redone with the edit-8 decoder, as P14-18 did for P14-03. A step that *uses* a frozen config (M4-13 eval) keeps the frozen config, as P14-18 did for the M4-12 rows.

**Same decision rule as P14-15 / P14-18 / P14-19:** **no effect** = every primary metric changes by less than its 95 % CI half-width; **effect** = at least one primary metric changes by its half-width or more. Committed numbers are never overwritten. Each affected results page gets a dated note; the original text stays.

**Separate from the M4-13 trust reruns.** The pre-registered M4-13 trust reruns (`experiments/2026-11-17-trust-reruns-m4-13/`, hidden queue running now) use edit 12 by their pre-registration. We do not change, stop or read them. Every number of this item is a separate, clearly labelled "edit 8" comparison.

## Rows rerun
Each row runs twice with the same code path: a **reference run (edit 12)** and the **edit-8 run**. The reference run must reproduce the committed numbers (counts exactly; rates, WER, eWPM and safe WPM to the printed precision) **before any edit-8 result of that row is read**. A `config_id` that differs while all decisions and counts agree is reported, not a failure (P14-18 saw this for P14-03). If a reference run does not reproduce the committed numbers, we stop that row and report it; no edit-8 result of that row is used.

| id | row (committed source) | what runs | primary metrics |
|---|---|---|---|
| R1 | **P14-05 safe WPM, T15 M4-13** (`2026-11-16-p14-05-safe-wpm`, stage `t15-m4-13`; safe WPM 2.23, 104 commits, 17 wrong) and **T15 M4-12** (stage `t15-m4-12-recompute`; 0.0, 2 commits, 2 wrong) | `stage_t15_compute`: drop-in guard (P14-03 recipe) calibrated on 722 `val_select`, decide 701 `val_eval`, `replay_block` | commit rate, wrong-commit rate, error among commits, safe WPM |
| R2 | **M4-13 eval trust rows** (`2026-11-15-m4-13-long-train/eval.py`, `results/eval.json`; gated 91 commits, 11 wrong, eWPM 9.94) | word quality at T = 1 and at the config frame T; frozen gated config `tcfg-4e6143e37d1642f3` and the ungated M2-19 config `tcfg-e7e8c472f6d9ab33` (not refitted) through `StreamingTrustLayer`; always-commit; 300-trial null controls | WER (T = 1, config T), sentence exact (T = 1, config T), truth in n-best (T = 1, config T); per config: commit rate, wrong-commit rate, error among commits, eWPM; always-commit wrong-commit rate and eWPM |
| R3 | **M2-19 trust retune** (`2026-11-15-m2-19-trust-retune`, `results/fit.json`, `eval.json`, `controls.json`) | stages `fit` (refit on `val_select` with the edit-8 decoder), `eval`, `controls`; decoders `dedicated_0` and `shared` | per eval condition (dedicated_0 LTT, dedicated_0 CRC, shared LTT) and the "old frozen" baseline: commit rate, wrong-commit rate, error among commits, eWPM; always-commit wrong-commit rate and eWPM |
| R4 | **P6-02b partial v0.2 entries** `b2t25-t15__m4-13__guard` (103 units, safe WPM 4.07 [2.51, 5.74]) and `b2t25-t15__m4-12__guard` (`2026-11-17-p6-02b-v02-entries`, `benchmark/results/v0.2/`) | `stage_t15_model` (guard on `val_select` minus track test units, 103 scored units, shuffled / zeros controls), then the one scorer command `python -m fidetype.benchmark score` into our folder | every score-card metric that has a CI in the committed card (CER, WER, eWPM, eWPM minus gaze, commit rate, wrong-commit rate, error among commits, silent error rate) and safe WPM |
| R5 | **P5-02 precision guarantee, T15** (`2026-11-16-p5-02-precision`, `results/results.json` `t15`) | `run_set("t15")`: base guard, 4 target precisions (0.5 / 0.8 / 0.9 / 0.95), resampling | base: held-out top-1-right rate and can-commit rate; per target: commit rate, wrong-commit rate, precision among commits |
| R6 | **P3-08 collector replay**, `m4-13` (`results/m4-13-summary.json`: 16 COMMIT / 104 OFFER, 3 wrong) and `m4-12` (`results/m4-12-summary.json`) | `prep` (n-best of `val_select`, `val_eval`, 200 shuffled nulls; `calibrate` with `input_kind="nbest"`; profile) and `replay` (120 trials at real time over the WebSocket binding into one collector) | commit rate (of 120), wrong-commit rate (of 120), error among commits. Latency is reported, not decided (it does not depend on the word decoder setting) |

**Reference checks per row.**
- R1: committed `t15-m4-13` and `t15-m4-12-recompute` blocks of `results/safe-wpm.json` (value, status, commits, wrong commits).
- R2: committed `results/eval.json` (word quality, both trust configs, always-commit, controls). The reference reads the committed M4-13 word-decode cache **read only** (a cache miss is decoded with edit 12 and counted).
- R3: committed `fit.json` (config ids, λ̂, final commit_p), `eval.json`, `controls.json`. The reference reads the committed M2-19 word-decode cache read only (misses counted).
- R4: committed score cards (all metric values and CIs, commits) and `results/stages.json` (`n_cal_used`, `n_scored`, commits).
- R5: committed `results.json` `t15` (base counts; per target: commit_p, feasible, commits, wrong).
- R6: the `prep` reference must give the same n-best lists as the committed local files `derived/p3-08-collector-replay/<decoder>/nbest-*.json` (read only; all three lists, exact) and the same guard sheet (commit threshold, controls) as the committed `guard-sheet.json`. One reference `replay` of `m4-13` must reproduce 16 COMMIT / 104 OFFER / 3 wrong commits. (The replay decisions depend only on the profile and the event order; the M4-13 reference replay checks this. To save 37 min, `m4-12` has no reference replay; its edit-8 replay is read if its `prep` reference passes and the M4-13 reference replay passes.)

## CI half-widths (of the committed value)
- rates of trials / units (commit rate, wrong-commit rate, sentence exact, truth in n-best, top-1-right, can-commit, silent error): Wilson 95 % half-width of the committed rate, n = trials of the row (701, 120, 103);
- error among commits and precision among commits: Wilson with n = committed commits. If the committed or the new run has 0 commits, this metric is not compared; the commit rate decides (P14-18 counted 2 → 0 commits as an effect through this metric; we name the case here);
- WER (pooled ratio), eWPM and safe WPM (rows R1, R2, R3, R6): half of the width of the 95 % percentile trial-bootstrap interval (2,000 resamples, seed 0) of the edit-12 per-trial values from the reference run (safe WPM: the `fidetype.benchmark.safe_wpm` point estimate with trial weights);
- R4: the CI of the committed score card (half of its width). If that CI has zero width (for example 0 commits, [0, 0]), the Wilson half-width of the committed rate with n = 103 units.
- Reported only, not decided: frame temperatures, λ̂, commit thresholds, config ids, null-control counts (but a null control that changes from pass to fail is reported as a finding), P5-02 resampling violation rates, P3-08 latency.

**Gap 53 (P14-23) question.** For R1 M4-13 we also report the edit-8 safe WPM and its status against the no-BCI reference 4.02 (and R4 against 4.12). This is a report, not part of the effect rule.

**Secondary (reported, not in the decision).** R2 with the edit-8 M2-19 `dedicated_0` LTT config (from R3) plus the same M2-18 commit gate: the "whole chain with edit 8" variant.

## Rows not rerun (and why)
- **M4-06 real replays**, the P14-05 `tracks` stage and the P6-02b `b2t` entries: B2T '25 copy-task **fixed split A** (fit / test = halves of each day), not `val_eval`. The split's own fit-A tune keeps lm 1.0 / edit 12 / bonus 3 (P14-15 sanity check, R3 `b2t-retune`), so P14-19 did not rerun fixed-split rows either.
- P14-05 / P5-02 `t12`, P6-02b `meg` / `toronto`: other decoders (no B2T '25 word decoder).
- M4-12, M4-01/02, P14-03 rows: done in P14-18.
- **P15-05, P15-06, P15-07** (F2 LLM grounding, hallucination bound and benchmark): they use the word decoder (every arm starts from its base n-best), but all arms except A0 / A1 need the Qwen2.5-1.5B LLM. Edit 8 changes the base n-best, so the read-only LLM cache misses. LLM + decoder need about 2.5-4.5 GB RAM (their plans), above the 1.5 GB cap of this run. Not run here; a new gap registers them.
- **M4-13 trust reruns** (P5-02 / P15-03 / F2 on M4-13): pre-registered with edit 12, still running, not committed. Not run here; the same new gap registers their edit-8 comparison after they are committed.

## Order and time limits
One detached queue (`launch.py` → `run.py --stage queue`), background class, 4 threads, one child process per stage and setting: R1 (M4-13 first, then M4-12), R2, R3, R4, R5, then R6 (real-time replays last: about 3 x 37 min). Estimated total about 4-5 h. A stage that fails or is killed for low memory is not retried; its rows are reported as not run and a new gap registers them.

## Outputs
- Repo: `experiments/2026-11-17-p14-21-edit8-rows/` (`plan.md`, `run.py`, `launch.py`, `results.md`, `results/*.json` with counts, rates and metrics only; no text, no trial ids).
- Local only: `C:\Users\zhang\bci-data\derived\p14-21\` (guards, decisions, n-best caches, per-trial values, score cards, collector outputs, logs). Other experiments' folders and derived folders are read only.
