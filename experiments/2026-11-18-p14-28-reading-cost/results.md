---
title: P14-28 reading cost and short prefixes in the proposed safe-wpm v0.2 - results (sensitivity)
type: experiment
task: P14-28
updated: 2026-11-18
---

# P14-28: reading cost per commit and minimum prefix length (results)

Pre-registration: [plan.md](plan.md), commit `691d743` (scorer options, tests, plan and [`run.py`](run.py) in the same commit; pushed before the run). Aggregates: [`results/results.json`](results/results.json); log: [`results/run.log`](results/run.log). Per-cell tables (no text): `C:\Users\zhang\bci-data\derived\p14-28\` (local only).

> **SENSITIVITY ANALYSIS, NOT A NEW TEST.** The script re-scores the fixed P5-24 per-trial decisions (no fitting, no new decisions, no new calibration). The P5-24 verdict does not change. The metric is the **proposed** safe-wpm/0.2 (not adopted). v0.1 numbers do not change.

Check: the cell (0 s, m = 1) gives the P5-24 values to 1e-9 (T15 4.87 / 2.64, T12 4.76 / 1.87); trial durations 218.286 min (T15) and 36.537 min (T12), as P5-24. All cells: status `certified` for both arms (a minimum length only removes commits).

## T15 (`val_eval` 701, primary; no-BCI 4.02)

| reading cost per commit | m | prefix safe WPM v0.2 [95 % CI] | prefix commits | sentence guard | Δ prefix − sentence [95 % CI] |
|---|---|---|---|---|---|
| 0 s (v0.2 as proposed) | 1 | **4.87** [4.43, 5.30] | 465 | 2.64 | +2.22 [1.84, 2.59] |
| 0.5 s | 1 | 4.78 [4.36, 5.20] | 465 | 2.63 | +2.15 [1.77, 2.52] |
| 1 s | 1 | 4.70 [4.29, 5.11] | 465 | 2.62 | +2.08 [1.70, 2.44] |
| 2 s | 1 | 4.55 [4.15, 4.94] | 465 | 2.60 | +1.95 [1.58, 2.30] |
| 3 s | 1 | 4.40 [4.02, 4.77] | 465 | 2.58 | +1.82 [1.47, 2.17] |
| **`aac-gaze-v1` verify: 0.5 s + 0.3 s/word** | 1 | **4.67 [4.26, 5.07]** | 465 | 2.60 | **+2.07 [1.70, 2.43]** |
| KLM M: 1.35 s | 1 | 4.65 [4.24, 5.05] | 465 | 2.61 | +2.03 [1.66, 2.39] |
| KLM M + reading 238 wpm: 1.35 s + 0.252 s/word | 1 | 4.55 [4.16, 4.94] | 465 | 2.58 | +1.97 [1.61, 2.32] |
| 0 s | 2 | 4.07 [3.61, 4.51] | 284 | 2.64 | +1.43 [1.05, 1.81] |
| 1 s | 2 | 3.98 [3.54, 4.41] | 284 | 2.62 | +1.36 [1.00, 1.74] |
| 3 s | 2 | 3.82 [3.41, 4.22] | 284 | 2.58 | +1.24 [0.89, 1.60] |
| `aac-gaze-v1` | 2 | 3.94 [3.51, 4.36] | 284 | 2.60 | +1.35 [0.99, 1.72] |
| 0 s | 3 | 3.04 [2.59, 3.49] | 164 | 2.64 | +0.39 [0.03, 0.76] |
| 3 s | 3 | 2.93 [2.51, 3.35] | 164 | 2.58 | +0.35 [−0.00, 0.70] |
| `aac-gaze-v1` | 3 | 2.97 [2.54, 3.41] | 164 | 2.60 | +0.38 [0.02, 0.73] |

All 24 cells per set are in `results/results.json` and `results/run.log`.

- **m = 2 removes 181 one-word commits.** They held 177 right words and 4 wrong commits (credited words 1,073 → 896; wrong commits 13 → 9). m = 3 removes 301 commits (credited words 666; 4 wrong).
- Reading time at the `aac-gaze-v1` cell (m = 1): 9.4 min on 218.3 neural minutes.

### Break-even (T15, prefix guard to the no-BCI 4.02)

| m | fixed cost per commit c* (w = 0) | per-word cost w* (c = 0) |
|---|---|---|
| 1 | **5.99 s** | **2.52 s/word** |
| 2 | 0.58 s | 0.18 s/word |
| 3 | none (below 4.02 already at 0 s) | none |

- The prefix guard equals the sentence guard only at about 43 s per commit (m = 1).

## T12 (test 400, replication; no-BCI 4.11)

| reading cost | m | prefix [95 % CI] | commits | sentence | Δ [95 % CI] |
|---|---|---|---|---|---|
| 0 s | 1 | 4.76 [3.84, 5.78] | 133 | 1.87 | +2.89 [1.89, 3.99] |
| `aac-gaze-v1` | 1 | 4.51 [3.66, 5.42] | 133 | 1.82 | +2.69 [1.74, 3.69] |
| KLM M + reading | 1 | 4.33 [3.52, 5.18] | 133 | 1.81 | +2.52 [1.58, 3.48] |
| 3 s | 1 | 4.07 [3.32, 4.85] | 133 | 1.80 | +2.26 [1.36, 3.18] |
| `aac-gaze-v1` | 2 | 2.97 [2.11, 3.89] | 53 | 1.82 | +1.15 [0.11, 2.16] |
| `aac-gaze-v1` | 3 | 1.64 [0.89, 2.44] | 22 | 1.82 | −0.19 [−1.09, 0.76] |

- Break-even (m = 1): c* = 2.78 s per commit, w* = 1.70 s per word. With m = 2 or 3 the prefix guard is below 4.11 already at 0 s. On T12, 80 of 133 commits are one word.

## Pre-registered statements

| # | statement | result |
|---|---|---|
| 1 | T15 prefix at `aac-gaze-v1`, m = 1, > 4.02 and CI lower bound > 4.02 (**robust**) | 4.67 [4.26, 5.07]: **robust** |
| 2 | break-even c* (m = 1) below 1.35 s (**fragile**) | c* = 5.99 s: **not fragile** |
| 3 | prefix beats sentence (Δ CI above 0) at `aac-gaze-v1`, m = 1 | +2.07 [1.70, 2.43]: **yes** (T12: +2.69 [1.74, 3.69], yes) |
| rule | m = 2 better than m = 1 at `aac-gaze-v1`? | no (3.94 < 4.67): a minimum length does not help; no guard follow-up |

## Recommendation (per the pre-registered rule)
- **Adopt a default reading cost for v0.2: the `aac-gaze-v1` verify cost, 0.5 s per commit + 0.3 s per committed word, on every commit.** T15 prefix: 4.87 → 4.67 [4.26, 5.07], still above 4.02. Sentence guards also pay it (2.64 → 2.60).
- **Keep `min_prefix_words = 1` in the metric.** A minimum length removes right words and costs more than any reading cost in the literature range. It is not a fix for short commits.
- With a non-zero reading cost, v0.2 no longer equals v0.1 for sentence policies (rule 6). The proposal says so.

## Notes and limits
- One participant per set, one split, one seed. CIs are conditional on the fixed decisions (they do not include the calibration draw).
- The reading costs come from able-bodied HCI and reading studies and from our own user model. No published value is for BCI users who check a committed word. The Koester & Levine list-search times (spinal cord injury users) were not available in full text here. Slow readers or users with fatigue can have a larger cost; the break-even (6 s per commit on T15, 2.8 s on T12) is the number to compare against.
- The no-BCI reference (gaze typing at 20 chars/min) has no reading cost added.
- A one-word right prefix is cheap to check (0.8 s at `aac-gaze-v1`) compared with typing the word by gaze (about 15 s at 4 WPM). This is why short commits keep their value under any cost in the literature range.
- Memory: the script reads only `.npy` headers and JSON files; run time under 1 s per set. Peak memory was not recorded (no `psutil`); it is far below 1 GB.

> **Our take:** the T15 v0.2 gain of prefix commits is not an artefact of free reading time. A cost of more than four KLM mental operators (6 s) per commit is needed to erase it. The weak point of v0.2 is elsewhere: T12 (break-even 2.8 s; CI already includes 4.11) and the one-participant evaluation. If the user adopts v0.2, the reading cost should come with it, so that a guard cannot gain by spraying many tiny commits.
