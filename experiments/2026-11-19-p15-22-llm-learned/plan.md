---
title: P15-22 LLM rescoring with the learned commit confidence (and prefix commits) for safe WPM - pre-registration
type: experiment
task: P15-22
updated: 2026-11-19
---

# P15-22: LLM rescoring + learned commit confidence (pre-registration)

Written and committed **before** any evaluation number of this item was computed or read. Gap 69 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P15-22](../../wiki/questions/roadmap-standard.md#p15-22-llm-rescoring-with-learned-and-prefix-confidence-for-safe-wpm). Follow-up of P15-05 (E3, LLM rescoring with grounding), P5-23 (learned commit score) and P5-24 (prefix commits). The exploratory [P14-23 analysis](../../wiki/questions/safe-wpm-bottleneck.md) estimated about 4.50 safe WPM for "LLM-rescored top-1 + a learned score" and 4.18 for the committed P15-05 B1 arm under `safe-wpm/0.1`. Those numbers had selection effects; they are not claims and they do not enter any choice here.

CPU only (background class, 4 threads, one process). **No GPU.** RAM target under 4 GB (word decoder + LLM if it loads).

## Question
Does the learned commit score of P5-23 give more safe WPM when the decoder output is the P15-05 LLM-rescored and grounded n-best (arm B1) instead of the n-gram n-best, with the wrong-commit guarantee and the null controls still met?

## Arms (T15 only)
All arms use the same decoder outputs, the same pipeline, the same calibration items, seed 0, alpha 0.05, delta 0.1, the same commit gate and `null_trials` 300.

| arm | pipeline (decode_fn) | `calibrate(...)` | role |
|---|---|---|---|
| **L0 `llm`** | P15-05 B1: n-gram n-best → LLM rescoring → CTC grounding | default (`confidence="p_top1"`) | the LLM arm alone (reproduction of the committed P15-05 M4-13 B1 guard) |
| **L1 `llm_learned`** | the same B1 pipeline | `confidence="learned"` (`confidence_l2` 1.0) | **primary** |
| **L2 `llm_prefix`** | the same B1 pipeline | `confidence="learned", commit_unit="prefix"` | secondary (prefix commits, scored with the proposed v0.2) |

References (read only, per-trial decisions of committed pre-registered runs, same 701 `val_eval` trials):

| reference | file | committed value |
|---|---|---|
| **R1** P5-23 learned guard (n-gram n-best) | `C:\Users\zhang\bci-data\derived\p5-23\decisions-p5-23-t15-m4-13-learned.json` | v0.1 2.64 (113 commits / 10 wrong) |
| **R2** P5-24 prefix guard (n-gram n-best) | `C:\Users\zhang\bci-data\derived\p5-24\decisions-p5-24-t15-m4-13-prefix.json` | v0.2 4.87; v0.2 + `aac-gaze-v1` reading cost 4.67 (P14-28) |

### Pipeline (fixed here; nothing is refitted)
- Code: the P15-05 `Pipeline` class of [`experiments/2026-11-16-f2-e3-llm-grounding/run.py`](../2026-11-16-f2-e3-llm-grounding/run.py), imported **unchanged**, with arm B1 (`rescore: true, rewrite: null, ground: true`).
- Fixed values from the committed P15-05 M4-13 rerun ([`results-t15.json`](../2026-11-17-f2-m4-13/results/results-t15.json), fitted on `val_select` only): LLM weight λ = 1.0, grounding τ = 0.06996627059278283, fluent threshold −7.88165954200173 log-prob per word, grounding `max_variants` 16, `demote_margin` 1.0.
- LLM: Qwen2.5-1.5B-Instruct GGUF Q4_K_M (Apache-2.0, SHA-256 `6a1a2eb6...`), llama-cpp-python, CPU, 4 threads, seed 0. Scores come from the committed P15-05 / P15-06 M4-13 caches (copied into our folder; the originals stay read only). On a cache miss the model loads on the CPU once (lazy) and the new score goes into **our** cache. The number of misses is reported.
- Base n-best: the committed P15-05 M4-13 cache (copied). On a miss the B2T '25 word decoder (lm 1.0, edit 12, bonus 3, `tune.json`) decodes the input. The number of misses is reported.
- Word decoder setting: edit 12, as P15-05, P5-23 and P5-24. Edit 8 is **not** part of this plan (see "P14-24" below).

### Data and split (same as P5-23)
- T15 M4-13 long0 log-probs: calibration `val_select` 722 (`derived\trust-reruns-m4-13\logprobs-m4-13-long0-val_select.npz`), evaluation `val_eval` 701 (`derived\m4-13\logprobs-m4-13-long0-val_eval.npz`), texts whitespace-normalised, phoneme targets as P14-03 (loader `common.load_t15("m4-13")` of the M4-13 trust reruns).
- `calibrate` split with `numpy.random.default_rng(0).permutation(722)`: score-fit part 451 (SHA-256 first 16 hex `285b8c0d9baf5a41`), certify (LTT) part 271 (`fadfd84557fcb24b`). The script recomputes both hashes; a mismatch stops the run.
- Trial durations: P14-05 `t15_durations` (20 ms neural bins per `val_eval` trial), as P5-23.
- **Row check:** the 701 truth texts of our loader must equal, row by row, the truths in R1 and R2. Otherwise the run stops (no paired result).

## Outcomes

### Primary: safe WPM v0.1 of L1
`fidetype.benchmark.safe_wpm.safe_wpm` (`safe-wpm/0.1`, the ADOPTED version, unchanged): measured trial durations, default correction rule (2 s + 0.79 s per truth character per wrong commit), guarantee and controls from the guard sheet. Status must be `certified`.

### Safety (per arm)
Wrong commits / all 701 items (for L2: wrong prefix commits, `wrong-prefix-commit`), with the two-sided 95 % Clopper-Pearson interval. **Safety holds** iff the observed rate ≤ 0.05. **Clear violation** iff the CP lower bound > 0.05.

### Controls (per arm)
The two null controls of `calibrate` (uniform, shuffled; 300 inputs each; pass iff commits ≤ 15). A failed control refuses the arm (`NullControlError`): no guard, no result.

### Paired comparisons and decision rule
Paired percentile trial bootstrap of the safe WPM difference (2,000 resamples of the 701 trials, seed 0, the same resample for both sides, decisions fixed, conditional on the calibration). Half-width hw = (97.5th − 2.5th percentile) / 2.

| id | comparison | metric |
|---|---|---|
| **H1** | L1 − R1 (does the LLM add to the learned guard?) | v0.1 |
| **H2** | L1 − L0 (does the learned score add to the LLM arm?) | v0.1 |

Verdict per comparison (X = L1):

| verdict | condition |
|---|---|
| **X beats the other** | L1 controls pass **and** L1 safety holds **and** Δ > hw |
| the other beats X | L1 controls pass and safety holds and Δ < −hw |
| no clear difference | L1 controls pass and safety holds and \|Δ\| ≤ hw |
| L1 fails safety / a control | observed L1 wrong-commit rate > 0.05, or an L1 control fails (refused) |

The P15-22 headline is the pair (H1 verdict, H2 verdict) and the L1 v0.1 value with its interval. P15-22 closes with the write-up whatever the verdicts (roadmap "done when": report safe WPM v0.1 and v0.2, controls, grounding, the fluent-wrong rate, and whether the value is above the no-BCI reference).

### P14-23 (gap 53) link
P14-23 closes iff **L1** (the primary arm) gives a **certified** v0.1 safe WPM **above 4.02** on all 701 `val_eval` trials with both controls passing (the P14-23 "done when"). We also say whether the lower end of the L1 trial-bootstrap 95 % interval is above 4.02 ("clearly above") or not ("above, inside the interval").
L0 is a reproduction of a committed guard whose v0.1 value (4.18) was already seen in the exploratory analysis. Its value is reported. **L0 alone does not close P14-23**, whatever its value, because its number was known before this plan.

### Reference checks (before any result is read)
- **L0** must reproduce the committed P15-05 M4-13 B1 decisions (`derived\f2-reruns-m4-13\p15-05\trials-t15-B1_rescore_G.json`: 154 commits, 12 wrong): count of the 701 trials with the same action and text. A mismatch is reported as a finding; the rules still use the recomputed L0.
- Split hashes and the row check (above).
- The frame temperature of each guard equals the committed `ground_prep` value 2.37015800035291 (else the cached decodes do not apply; reported).

### Secondary (reported, not decided)
1. **Proposed `safe-wpm/0.2`** (not adopted) for L1 and L2: (a) plain, (b) with the `aac-gaze-v1` reading cost 0.5 s per commit + 0.3 s per committed word (P14-28). Paired v0.2 + reading cost: L2 − R2, L2 − L1. Also L2 under v0.1 (literal: a partial prefix is a wrong commit) and v0.1 counting complete commits only. Whether L1 / L2 v0.2 values are above 4.02 is reported; v0.2 values never close P14-23 while v0.2 is not adopted.
2. **Hallucination protocol 0.2 check** (`fidetype.halluc/0.2`, P15-15) for L0, L1 and L2: the P15-07 tracks on the 701 `val_eval` trials (null 300, scrambled 300, swapped 701, paired), with the committed T15 control indices and swap permutation (`src/fidetype/benchmark/splits/halluc-v0.1/b2t25-t15-val-eval.json`; checked with `verify_split`), both fluency modes (LLM table, conservative). Reported: real commits, swapped unsupported commits, n10 / n01 / n11, the 0.2 swapped verdict, the controls verdict, and the absolute unsupported swapped-commit rate with CP95 (open gap 72 concern). Expectation (not a rule): L0 and L1 pass the swapped track because grounding blocks swapped commits. For L2 the protocol counts a right prefix as a wrong commit; its card is descriptive only.
3. **Fluent-wrong and hallucination rate** per arm on the 701 held-out trials, with the P15-05 definitions: a fluent-wrong commit is a wrong commit whose LLM log-prob per word ≥ the fluent threshold; the hallucination rate is the share of shown words (commits and first offers) that are wrong and not in the base n-best word bag. Compared with L0 and with the committed A0 (2 fluent-wrong) and B1 (6). Not decided: the learned score cannot use the joint fluent-wrong bound (`llm=` is refused, gap 74).
4. Per arm: commits, wrong commits, error among commits, threshold, in-sample LTT commits, top-1 exact rate, recall of exactly-right trials, AUROC of the commit score and of `p_top1` for "top-1 exactly right", fitted weights and dropped features, run time, peak memory, cache misses.

## P14-24 (gap 62, edit 8)
Not included. The edit-8 rows need new base decodes of all 1,423 trials with another word-decoder setting, new LLM calls for every new n-best text, and the P14-24 comparison protocol (edit-12 references first, P14-15 rule) for P15-05 / P15-06 / P15-07 and the trust reruns. That is a separate run; it does not fit this one. Gap 62 stays open. T12 is also not part of this plan (the P15-22 "done when" names T15 only).

## Order, limits, outputs
1. Commit this plan before any stage runs. Then commit `run.py` (after a smoke test on `val_select` subsets only, which never touches `val_eval`) and the full pytest.
2. Run detached: `launch.py` → `python -m fidetype.utils.isolation run --class background --threads 4 -- python -I run.py all` with `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` and a keep-awake (`SetThreadExecutionState`) inside the run. Stages: `t15` (arms L0, L1, L2), `halluc` (protocol 0.2 tracks), `verdict` (rule above, no data access).
3. Resumable: each finished arm is saved to `C:\Users\zhang\bci-data\derived\p15-22\arm-<name>.json` and skipped on a rerun; the caches persist. A `DONE` file marks the end.
4. Per-trial decisions (with text) stay in `C:\Users\zhang\bci-data\derived\p15-22\` (local). The repo gets `results/results.json` (aggregates), `results/guard-*.json` (configuration + sheet, no text) and `results/run.log`.
5. A stage that is killed for low memory is not retried automatically; it is reported as not run.
6. No change of arms, features, split, metric, rule or references after this commit. Any later variant (an LLM feature in the score, edit 8, T12, the joint fluent-wrong bound with a learned score) is a new item with its own plan.

Write-up: `results.md` in this folder, with the verdicts and numbers as computed, including a failure.
