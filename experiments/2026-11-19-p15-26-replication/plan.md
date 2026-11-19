---
title: P15-26 Replication of the P15-22 headline (T15 calibration draws + T12) - pre-registration
type: experiment
task: P15-26
updated: 2026-11-19
---

# P15-26: replication of LLM rescoring + learned commit confidence (pre-registration)

Written and committed **before** any number of this item was computed or read. Gap 93 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P15-26](../../wiki/questions/roadmap-standard.md#p15-26-t12-replication-of-llm-rescoring--learned-commit-confidence). Follow-up of [P15-22](../2026-11-19-p15-22-llm-learned/plan.md) (pre-registration `7557b54`, [results](../2026-11-19-p15-22-llm-learned/results.md)).

P15-22 gave the LLM arm + learned commit score (**L1**) a certified `safe-wpm/0.1` value of **4.91 [4.25, 5.57]** on T15 `val_eval` (701 trials), above the no-BCI reference 4.02. That number comes from one participant, one calibration split and one seed. This item tests whether it replicates.

CPU only (background class, 4 threads, one process per stage). **No GPU.** The LLM runs on the CPU (llama-cpp-python, `n_gpu_layers` 0). RAM target under 5 GB per process (P15-22 peak 2.53 GB; the T12 loader peaked at 2.34 GB without the LLM).

## Questions
- **(a) T15 calibration draws.** Does L1 stay above the no-BCI reference when the calibration draw changes: (a-c) the fit / certify split inside `val_select`, and (a-p) the split of all T15 validation trials into calibration and evaluation?
- **(b) T12.** Does the same L1 pipeline give a certified safe WPM above the no-BCI reference on the second participant (T12 v2 decoder, 10 later test sessions), and does it beat the P5-23 learned guard there?

## Fixed for all parts
- Pipeline: the P15-05 `Pipeline` class of [`experiments/2026-11-16-f2-e3-llm-grounding/run.py`](../2026-11-16-f2-e3-llm-grounding/run.py), imported **unchanged**, arm B1 (`rescore: true, rewrite: null, ground: true`). LLM Qwen2.5-1.5B-Instruct GGUF Q4_K_M (Apache-2.0, SHA-256 checked), CPU, 4 threads, seed 0.
- Guards: `fidetype.trust.calibrate` with alpha 0.05, delta 0.1, the commit gate, `null_trials` 300, `stream_texts` (phoneme targets) so the frame temperature is fitted inside `calibrate` as in P15-22.
- Arms per evaluation unit (a "unit" is one draw or T12):

| arm | decode_fn | `calibrate(...)` | role |
|---|---|---|---|
| **L1 `llm_learned`** | B1 | `confidence="learned"` (`confidence_l2` 1.0) | **primary** |
| L0 `llm` | B1 | default (`p_top1`) | reference for H2 |
| R1' `ngram_learned` | P15-05 arm A0 (base n-gram n-best, no LLM, no grounding; the same decoder output as the P5-23 decode_fn) | `confidence="learned"` | the P5-23 learned guard on the same calibration (T15 draws only) |
| L2 `llm_prefix` | B1 | `confidence="learned", commit_unit="prefix"` | secondary, **T12 only** (v0.2, proposed) |

- Safe WPM: `fidetype.benchmark.safe_wpm.safe_wpm`, `safe-wpm/0.1` (adopted, unchanged), measured trial durations (20 ms neural bins), default correction rule, guarantee and controls from the guard sheet. Trial-bootstrap 95 % CI (decisions fixed, conditional on the calibration).
- Paired comparisons: paired percentile trial bootstrap of the safe WPM difference, 2,000 resamples, seed 0, half-width hw = (97.5th − 2.5th percentile) / 2 (the P15-22 code).
- **No-BCI reference** (the definition of the T15 4.02): gaze typing of every evaluation sentence at 20 chars/min, `no_bci_wpm` = 20 × words / characters of the evaluation truths (P14-05, `docs/safe-wpm.md`). It depends only on the evaluation texts, so it is fixed here:

| unit | evaluation set | no-BCI reference |
|---|---|---|
| T15 c1, c2, c3 | `val_eval` 701 | **4.0153** (the "4.02") |
| T15 p1 | the p1 evaluation set (701) | **4.0005** |
| T12 | trust pool of the 10 test sessions (400) | **4.11** (P14-05; the script recomputes it; a mismatch is reported and the recomputed value is used) |

## Part (a): T15 calibration draws

Data: T15 M4-13 long0 log-probs, `val_select` 722 (calibration in P15-22) and `val_eval` 701 (evaluation in P15-22), loader `common.load_t15("m4-13")` of the M4-13 trust reruns, texts whitespace-normalised, phoneme targets as P14-03.

### Draws (fixed here)
Four draws. All four are run and reported.

| draw | calibration set | evaluation set | `calibrate` seed | split hashes (SHA-256 of the sorted positions, first 16 hex) |
|---|---|---|---|---|
| **c1** | `val_select` 722 | `val_eval` 701 | 1 | score-fit `bcbc9f41affce5a0`, certify `7301b55487e33bc9` |
| **c2** | `val_select` 722 | `val_eval` 701 | 2 | score-fit `6c4953f83f65f929`, certify `6c389cf380dd30c7` |
| **c3** | `val_select` 722 | `val_eval` 701 | 3 | score-fit `d8f686737ff07fa5`, certify `713099bd5a9ac403` |
| **p1** | 722 of the 1,423 pooled trials | the other 701 | 0 | pool = `val_select` (positions 0-721) then `val_eval` (722-1422); permutation `numpy.random.default_rng(s).permutation(1423)` with s = the first 16 hex of SHA-256(`"p15-26|t15|pool|p1"`) as an integer (11118116894105730765); calibration = sorted first 722 (`3d0342243119a38c`, 368 from `val_select`), evaluation = sorted last 701 (`597f37bd70ec02f1`, 347 from `val_eval`); inner seed-0 split of the calibration list: score-fit `8fdc279ebbb6e526`, certify `186ba508a9fa6aef` |

The script recomputes every hash; a mismatch stops the run.

Known bias of p1 (stated before any number): the M4-13 checkpoint `best.pt` was chosen by `val_select` PER over 20 validations. In p1, 354 of the 701 evaluation trials come from `val_select`. This can make p1 slightly optimistic. The c-draws keep the clean `val_eval` evaluation.

### Pipeline values per draw ("same pipeline, same rules")
P15-05 fitted the pipeline values on the calibration set only. A draw refits them the same way, on its own calibration set:
1. Frame temperature T: fitted inside `calibrate` on the fit part (the guard of R1' is calibrated first; all guards of the draw must have the same T, else the draw stops).
2. Grounding τ and LLM weight λ: P15-05 `stage_ground_prep` (unchanged) on all calibration items, tempered with T (τ at 95 % coverage of the true-text deficits; λ from the grid {0.1, 0.25, 0.5, 1.0, 2.0} by calibration WER).
3. Fluent threshold (used only for the fluent-wrong count): P15-05 `stage_prep`, the median LLM log-prob per word of the calibration truths. For the c-draws this is the committed value (same truths).

### Code check (draw c0, not a result)
Before c1, the same code runs draw **c0** = the P15-22 split (`val_select` → `val_eval`, seed 0) with the refit steps above. It must reproduce the committed values: T 2.37015800035291, τ 0.06996627059278283, λ 1.0, fluent threshold −7.88165954200173, and the P15-22 decisions of L1 (701 / 701 same action and text; 196 commits, 13 wrong) and the P5-23 R1 decisions for R1' (113 commits, 10 wrong). A mismatch is reported as a finding and stops part (a) (no draw result is used from code that does not reproduce).

## Part (b): T12
- Data and split: T12 v2 confirmatory log-probs, the P5-23 / P15-05 T12 split: calibration = trust pool of the 14 fit_a + calibration sessions (480), evaluation = trust pool of the 10 test sessions (400). `calibrate` seed 0; split hashes must equal P5-23: score-fit `630db9ca864af56f`, certify `3fe1b31e8e46a035`.
- Decoder: the P15-05 T12 word route (B2T '25 word decoder with the T12 tuned setting + the word trigram LM, `data_t12` of P15-05, LRU memos reduced for RAM; a memo never changes a result).
- Pipeline values: the committed P15-05 T12 values, fitted on the T12 calibration pool only (`experiments/2026-11-16-f2-e3-llm-grounding/results/results-t12.json`): T 2.528091520707864, τ 0.47419631304442217, λ 0.5, fluent threshold −8.916451934532247. The frame temperature of each guard must equal T (else reported; cached decodes then do not apply).
- Caches: copies of the P15-05 T12 base n-best and LLM caches (`derived/f2-e3-llm-grounding/t12/`) and the P15-06 T12 LLM cache (`derived/f2-reruns-m4-13/p15-06-t12-single/`), merged into **our** folder. On a miss, the decoder or the CPU LLM runs and the new entry goes into our copy. The number of misses is reported.
- References (read only, committed pre-registered per-trial decisions, same 400 trials):
  - **R1-T12** P5-23 learned guard: `derived/p5-23/decisions-p5-23-t12-v2-learned.json` (committed v0.1 1.87, 31 commits / 15 wrong).
  - **R2-T12** P5-24 prefix guard: `derived/p5-24/decisions-p5-24-t12-v2-prefix.json` (committed v0.2 4.76).
  - Row check: the 400 truths must equal R1-T12 and R2-T12 row by row, else the run stops.
- Reference check: L0 must reproduce the committed P15-05 T12 B1 decisions (`derived/f2-e3-llm-grounding/t12/trials-t12-B1_rescore_G.json`: 15 commits, 8 wrong). A mismatch is reported; the rules use the recomputed L0.

## Hallucination protocol 0.2
`fidetype.halluc/0.2` (P15-15) with the P15-07 tracks (null 300, scrambled 300, swapped = all evaluation trials, paired), both fluency modes (LLM table, conservative):
- T15 c-draws: L1 only, with the committed T15 control indices and swap permutation (`src/fidetype/benchmark/splits/halluc-v0.1/b2t25-t15-val-eval.json`, `verify_split`).
- T15 p1: L1 only, controls made with `make_controls` seed 0 on the p1 evaluation set (no committed split exists).
- T12: L0, L1, L2 with the committed T12 split (`b2t24-t12-test.json`, `verify_split`). L2 is descriptive only (the protocol counts a right prefix as a wrong commit).
- Reported: real commits, swapped unsupported commits with CP95, n10 / n01 / n11, the swapped verdict and the controls verdict.

## Outcomes and decision rules

### Primary metric
L1 `safe-wpm/0.1` value per unit, with status, trial-bootstrap 95 % CI, wrong commits / all evaluation trials with the two-sided 95 % Clopper-Pearson interval.

### Two tests per unit
- **Test A (level).** A passes iff all of: L1 calibrates (both null controls pass, else refused); status `certified`; **safety holds** (observed wrong-commit rate ≤ 0.05); L1 passes hallucination protocol 0.2 (swapped verdict and controls verdict "pass" in the LLM-table fluency mode); and **L1 v0.1 > the no-BCI reference of the unit**. We also say if the lower CI end is above the reference ("clearly above") or not ("above, inside the interval").
- **Test G (gain over the n-gram learned guard).** H1 = L1 − R1' (T15 draws) or L1 − R1-T12 (T12), v0.1, the P15-22 rule: "L1 beats the other" iff L1 controls pass, L1 safety holds and Δ > hw; "the other beats L1" iff Δ < −hw; "no clear difference" iff |Δ| ≤ hw; "L1 fails safety / a control" otherwise. G passes iff "L1 beats the other".
- Secondary, reported with the same rule, not decided: H2 = L1 − L0 per unit.

### Verdicts
- **Part (a):** level verdict over the four draws c1, c2, c3, p1: **replicates** iff A passes in all four; **partly replicates** iff A passes in one to three; **does not replicate** iff A passes in none. The same three-way verdict for G. We also report the L1 values of c0 (= P15-22), c1, c2, c3, p1: mean, SD and range (the split dependence of 4.91).
- **Part (b):** level verdict **replicates on T12** iff A passes on T12, else **does not replicate on T12**; gain verdict **gain replicates on T12** iff G passes, else **gain does not replicate on T12**.
- **Headline claim** (what the README and the frontier page may say):

| part (a) level | part (b) level | claim |
|---|---|---|
| replicates | replicates | "above gaze typing, replicated on two participants and four calibration draws" |
| replicates | does not replicate | "above gaze typing on T15 (stable over calibration draws); **not replicated on T12**" |
| partly replicates | any | "above gaze typing on T15 in some calibration draws only; the 4.91 depends on the split" |
| does not replicate | any | "the P15-22 result **did not replicate**; P15-22 was a favourable draw" |

A failed replication is a real negative result. It goes into `results.md`, the frontier page and the open-gap list in plain words, and the orchestrator is told that the README claim must change. It is never hidden or re-run with other settings.

Expectation (not a rule, written so the result can be compared): T12 decoding is much worse than T15 (P15-05 T12 B1 WER 0.385 against 0.162 on T15; 15 commits of 400). We expect T12 L1 to stay **below** 4.11 and test A on T12 to fail. We have no strong expectation for the T15 draws; the P15-22 interval half-width (0.66) suggests values roughly between 4.2 and 5.6.

### Secondary (reported, not decided)
1. T12 L2 (prefix) under the proposed `safe-wpm/0.2`, plain and with the `aac-gaze-v1` reading cost (0.5 s per commit + 0.3 s per committed word), paired L2 − R2-T12 (v0.2 + reading cost). v0.2 values never decide anything while v0.2 is not adopted.
2. Per arm and unit: commits, wrong commits, error among commits, threshold, in-sample LTT commits, top-1 exact rate, recall of exactly-right trials, AUROC of the commit score, fluent-wrong commits of L0 / L1, fitted weights, run time, peak memory, cache misses.
3. The between-draw spread compared with the P15-22 bootstrap half-width (does the conditional CI under-state the uncertainty?).

## Order, limits, outputs
1. Commit this plan before any stage runs. Then commit `run.py`, `launch.py` and a smoke test (`val_select` / T12 calibration subsets only; it never reads an evaluation set) after the full pytest.
2. Run detached: `launch.py` starts one detached launcher (`CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`). It runs each stage in its own process via `python -m fidetype.utils.isolation run --class background --threads 4 -- python -I run.py <stage>`, in this order: `t12`, `c0`, `c1`, `c2`, `c3`, `p1`, `verdict`. Keep-awake (`SetThreadExecutionState`) inside each stage.
3. Resumable: each finished arm is saved to `C:\Users\zhang\bci-data\derived\p15-26\<unit>\arm-<name>.json` and each finished unit to `unit.json`; both are skipped on a rerun. Caches persist. A `DONE` file marks the end of all stages.
4. A stage that is killed (for example for low memory) is **not** restarted automatically. The launcher records its exit code and goes on with the next stage; the dead stage is reported as not run. If c0 does not reproduce, the c- and p-draw stages stop.
5. Per-trial decisions (with text) stay in the derived folder (local). The repo gets `results/results.json` (aggregates only), `results/guard-*.json` (configuration + sheet, no text), `results/halluc/` (flags only) and `results/run.log`.
6. No change of arms, draws, metric, references or rules after this commit. Any later variant is a new item with its own plan.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including any failure.
