---
title: P14-28 reading cost and short prefixes in the proposed safe-wpm v0.2 - pre-registration
type: experiment
task: P14-28
updated: 2026-11-18
---

# P14-28: reading cost per commit and minimum prefix length (pre-registration)

Written and committed **before** any number of this item was computed. Gap 75 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P14-28](../../wiki/questions/roadmap-standard.md#p14-28-reading-cost-and-short-prefixes-in-safe-wpm-v02). Metric: the **proposed** [safe-wpm/0.2](../../docs/safe-wpm-v0.2-proposal.md) (P14-26). **v0.2 is not adopted**; the user decides at the weekend. CPU only (background class, 4 threads, RAM target under 1 GB). No GPU, no LLM, no fitting.

> **This is a sensitivity analysis, not a new test of the guard.** It re-scores the fixed per-trial decisions of P5-24 under different user-cost assumptions. The decisions, thresholds and certificates do not change. The P5-24 verdict stays as it is.

**Disclosure.** While writing this plan, the author made one rough estimate from the published P5-24 totals (T15 prefix: 1,073 credited words, 218.3 neural minutes, 2.2 correction minutes, 465 commits): a fixed cost of about 6 s per commit brings 4.87 down to 4.02. No per-trial value was computed.

## Question
How much of the T15 v0.2 gain of certified prefix commits (4.87 vs no-BCI 4.02; sentence guard 2.64) remains when every commit costs the user reading / checking time, and when very short prefix commits are not allowed?

## Inputs (read only)
- Decisions: `C:\Users\zhang\bci-data\derived\p5-24\decisions-p5-24-{t15-m4-13,t12-v2}-{sentence,prefix}.json` (P5-24, commit `7f97a44`).
- Guard sheets: `experiments/2026-11-18-p5-24-prefix-commits/results/guard-p5-24-*-{sentence,prefix}.json` (guarantee and controls).
- Trial durations: number of 20 ms bins per trial, read from the `.npy` headers of the P5-24 data files (T15: `derived\m4-01-02-lookahead`, keys of `derived\m4-13\logprobs-m4-13-long0-val_eval.npz`; T12: the T12 v2 test sessions). Checked before this plan: 701 trials, 218.286 min; 400 trials, 36.537 min (= P5-24).
- Outputs: per-cell tables (no text) in `C:\Users\zhang\bci-data\derived\p14-28\`; aggregates in `results/` here. Script: [`run.py`](run.py) as committed with this plan.

## Scorer options (committed with this plan)
`safe_wpm(..., metric_version="0.2", read_s_per_commit=c, read_s_per_word=w, min_prefix_words=m)`:
- **Reading cost.** Every commit, right or wrong, prefix or complete, adds `c + w * k_i` seconds (k_i = words of the committed text). The no-BCI reference does not change.
- **Minimum prefix length m.** A prefix commit (not complete) with k_i < m becomes no commit: 0 words, no penalty, no reading time. Complete commits are not affected. This only removes commits, so the wrong-commit rate cannot rise and the certificate still holds.
- Defaults (0 s, 0 s/word, m = 1) give exactly the published v0.2 values. The options are refused with v0.1.

## Reading-cost values (from the literature; fixed here)

| source | value | how it maps to a commit | certainty |
|---|---|---|---|
| Card, Moran & Newell (1980, 1983), keystroke-level model | mental operator M = 1.35 s; Kieras: 0.6-1.35 s, "use 1.2 s" | one M per commit (decide to accept) | standard HCI constant; not measured on BCI users |
| Brysbaert (2019), meta-analysis of 190 studies | silent reading 238 wpm (non-fiction) = 0.252 s/word | per committed word | adult readers, not AAC users |
| Fidetype `aac-gaze-v1` user model (`simulated_user.py`, from Cai et al. 2024) | verify a commit: 0.5 s per candidate + 0.3 s per word (200 wpm) | per commit + per word | project assumption, checked against Cai et al. 2024 selection times |
| Trnka et al. (2008), simulated AAC (1.5 s key delay), 28 participants | 2.26 s per keystroke without prediction vs 2.59 (basic) / 2.95 (advanced) with prediction | overhead 0.33-0.69 s per keystroke (lists checked at many keystrokes, not only at commits) | per keystroke, not per commit; indirect |
| Chitnis et al. (2024), inline autocomplete, N = 9 | about 21 ms per suggestion (9 ms right, 50 ms wrong) | lower bound for fast typists | small study; able-bodied typists |
| Koester & Levine (1994, 1996), word prediction with SCI users | list search slower for SCI users than for able-bodied users; prediction slowed SCI users | qualitative | **exact seconds not obtained** (full text not available here) |
| Li & Feit (2026), simulation | gaze shift to the suggestion bar 200 ms (SD 100) | part of a fixed cost | simulation parameter |

## Grid (fixed here)
For each set (T15 primary, T12 replication) and each arm (**sentence** = P5-23 learned guard, **prefix** = P5-24 guard), safe WPM v0.2 at:
- **Grid:** c in {0, 0.5, 1, 2, 3} s per commit, w = 0, times m in {1, 2, 3} (15 cells).
- **Named user models:** (a) `aac-gaze-v1` verify: c = 0.5, w = 0.3; (b) KLM M: c = 1.35, w = 0; (c) KLM M + silent reading: c = 1.35, w = 60/238 = 0.252; each times m in {1, 2, 3} (9 cells).
- Per cell: value and status; 95 % percentile trial bootstrap CI (B 2,000, seed 0, decisions fixed); commits, wrong commits, credited words, reading minutes, dropped prefix commits; paired Δ prefix − sentence with its CI.
- **Break-even:** the fixed cost c* (w = 0) and the per-word cost w* (c = 0) where the prefix value falls to the no-BCI reference (T15 4.02, T12 4.11), for m = 1, 2, 3 (closed form); and the fixed cost where prefix = sentence (m = 1, bisection).
- Check: the cell (0, 0, 1) must give the P5-24 values (T15 4.87 / 2.64, T12 4.76 / 1.87) to 1e-9; the script asserts it.

## Pre-registered statements
1. **Robust above no-BCI** (T15) iff the prefix value at the `aac-gaze-v1` cell with m = 1 is > 4.02 **and** its CI lower bound is > 4.02. Otherwise **not robust**.
2. **Fragile** iff the break-even fixed cost c* (m = 1) is below 1.35 s (one KLM M per commit). Otherwise **not fragile**.
3. **Prefix still beats sentence** at a cell iff the paired Δ CI lies above 0. Reported for all cells; the `aac-gaze-v1` m = 1 cell is the one quoted.

## Recommendation rule (fixed here, before numbers)
- **Default reading cost for v0.2:** the `aac-gaze-v1` verify cost, **0.5 s per commit + 0.3 s per committed word**, charged on every commit of every v0.2 entry (prefix and sentence policies alike). Reason: it is the project's existing user model (the eWPM simulated user already charges it), it lies inside the literature range above (below one KLM M for one word, above the able-bodied autocomplete value), and it treats one-word commits as costly relative to their credit. This changes the v0.2 rule-6 property: with a non-zero reading cost, v0.2 no longer equals v0.1 for sentence policies. The proposal must say so.
- If statement 1 says **not robust**, the proposal must say that "above the no-BCI reference" does not hold under a realistic reading cost.
- **Minimum prefix length:** recommend **m = 1** in the metric (the metric must not drop right text); report m = 2, 3 only as a guard design option. If the m = 2 prefix value at the `aac-gaze-v1` cell is higher than at m = 1, say that a guard-level minimum length helps the user and file a follow-up for the guard.
- The user decides. The recommendation is written into the proposal; no default in code changes in this item (the scorer default stays 0 until the user adopts v0.2).

## Not in scope
New decisions, new guards, LLM features, streaming (P5-27), the v0.1 numbers (they do not change).
