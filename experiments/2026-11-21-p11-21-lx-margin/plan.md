---
title: P11-21 Calibration-inclusive lower end above 3.09 for the EMG LX-FL prefix guard - pre-registration
type: experiment
task: P11-21
updated: 2026-11-21
---

# P11-21: calibration-inclusive lower end above 3.09 for the EMG LX-FL prefix guard (pre-registration)

Written and committed **before** any number of this item was computed. Gap 166 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-21](../../wiki/questions/roadmap-standard.md#p11-21-calibration-inclusive-lower-end-above-309-for-the-lx-fl-prefix-guard). Bases: [P11-16](../2026-11-21-p11-16-emg-prefix-confidence/plan.md) (the LX-FL guard and its 40 bootstrap draws), [P11-18](../2026-11-21-p11-18-emg-above-alpha/plan.md) (partition-only draws), [P11-20](../2026-11-21-p11-20-emg-shift-robust/plan.md) (shift margin), [P11-23](../2026-11-21-p11-23-shift-margin-steps/plan.md) (margin rule over two step directions and the user spread), [P11-17](../2026-11-21-p11-17-emg-calibration-ci/plan.md) (interval and credit rule). Gap 159 (P11-19) is the L-FL sentence guard. This item works only on the LX-FL prefix guard, so it does not duplicate gap 159.

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates and per-draw counts only: no per-user value, no text, no prompt id, no signal, no weights. Per-user step sizes are given only as unlabelled spread statistics. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-21\`. All other derived folders are read only.

**`safe-wpm/0.2` is a PROPOSAL. It is not adopted.** Every value of this item is a proposed-v0.2 value (prefix commits get credit). No headline uses it before the user adopts v0.2.

CPU only, **no GPU**. No new inference.

## Done-when (roadmap)
A pre-registered run reports the calibration-inclusive interval against 3.09 for the prefix guard: lower end above 3.09, or numbers say why not.

## What limits the lower end today (from committed results)
| Item | Guard, draws | Interval | Draws above alpha (earn 0) |
|---|---|---|---|
| P11-16 | LX-FL, bootstrap draws, LTT at 0.05 | 7.18 [0.00, 12.13] | 7 / 40 |
| P11-17 | L-FL, bootstrap draws | 5.00 [0.00, 9.55] | 9 / 40 |
| P11-18 | L-FL, partition-only draws | 5.65 [0.00, 9.45] | 3 / 40 |
| P11-20 | L-FL, partition-only, margin m 0.0045 | 6.13 [2.62, 9.47] | 0 / 40 |
| P11-23 | L-FL, partition-only, margin m2 0.0185 | 5.47 [2.44, 8.77] | 0 / 40 |

Three limits follow:
1. **Zero draws.** A draw above alpha earns 0, and zeros pull the 2.5th percentile to 0. Two causes were found for L-FL: bootstrap duplicates in the LTT part (P11-18) and the val / test session shift (P11-18, P11-20). For L-FL, partition-only draws plus a shift margin removed all zero draws.
2. **Spread of the certified draws.** For L-FL with the margin, the lower end (about 2.4 to 2.6) came from the within-draw user-cluster spread (SD 1.23) and one low-commit draw (2.25), around a mean of only 5.5 to 6.1.
3. **Calibration size.** The between-draw SD falls about as 1 / sqrt(n) (P15-37, P15-40). The track-val session has only 1,224 prompts. **This lever is not reachable on current data** without a new calibration population, so this item does not test it.

LX-FL starts higher: its certified P11-16 draws have a median of 8.63 and a within-draw SD of 1.24. So if the two L-FL fixes (partition-only draws and a shift margin) also remove the LX-FL zero draws, and the margin does not cost too much value, the lower end can rise above 3.09. This item tests that. **The levers are: (1) partition-only outer draws, (2) a shift margin below alpha estimated for the LX-FL guard itself with the P11-23 rule.** The commit unit (word prefix) and the prefix score (the P11-16 LX model, refitted per draw) stay fixed. They are what makes LX-FL strong; changing them is a new item.

Levers not used, and why:
- More calibration data (sessions a / b added to track val): the decoder checkpoints were selected on sessions a and b, and a mixed calibration population changes the shift to the test session in a way that no step of this design measures.
- A new prefix score or commit unit: not limited by the results above.

## Fixed parts (as P11-16, unchanged)
Data, splits, windows, target, decoder FL, the no-signal gate, the OOV gate, the competitor set U, the 11 prefix features `FEATS16` and signs, the LX model rule (`PLearned.fit`, l2 1.0, sign constraints with backward elimination; rows = all prefix rows of the committable fit + policy items), the decision rule (monotone prefix scores, `longest_prefix`), certification with `commit_score.ltt_prefix_threshold` (delta 0.1, `DEFAULT_LTT_GRID`) outside `calibrate`, the calibrate controls (`dropin._run_controls` with the draw's random state: uniform and frame-shuffled, 300 trials each; user null inputs; allowance 15 / 300), the guarantee sheet (`ext_sheet`; the claim alpha = 0.05), proposed safe WPM v0.2 with the default correction rule, no reading cost, no-BCI reference 3.09, the P11-17 credit rule. The P11-16 runner is imported for its pure helpers and `A16` analyser; its `own()`, `log()` and memo files are never written. The analyser memo of this item starts from a read-only copy of the P11-16 memo (window-content keys, so this is exact) and is saved only in `derived\p11-21\`.

## Stage 1: LX-FL shift steps on sessions a and b (no track-val or track-test data)
The P11-20 session a / b prompts and log-probs (`derived\p11-20\prompts-ab.json`, `derived\p11-20\lp\u<i>-{a,b}-real.npy`, read only; P11-20 checks C1 and C2 passed on them) are analysed with the P11-16 `A16` analyser (the U fused scores and the prefix LM are needed; the P11-20 / P11-23 memos lack them).

Two directions, J = 40 partition-only draws each (P11-17 `draw_order(n, s, None)` with `_split(n)` sizes; the LX model fitted on fit + policy; `ltt_prefix_threshold` at alpha = 0.05 on the LTT part; calibrate controls uniform and frame-shuffled from the calibration-session windows, no user null inputs, as P11-23 `null_inputs=None`):
- **A01-A40, d = a -> b**: seeds seed_of(`"p11-20|emg|m|<j>"`) (the P11-20 / P11-23 seeds; same partitions as the L-FL A draws).
- **B01-B40, d = b -> a**: seeds seed_of(`"p11-23|emg|ba|<j>"`).

seed_of(tag) = first 8 hex digits of SHA-256(tag), as an integer.

A draw "has a guard" if the threshold is finite and its calibrate controls pass. For each guard, record pooled and per-user counts (per-user local only): the LTT part (n, commits, wrong commits) and the whole evaluation session (n, commits, wrong commits). A commit is wrong if `safe_wpm.prefix_outcome(text, truth, complete)["correct"]` is false (the LTT loss of `ltt_prefix_threshold` uses the same rule; check X4).

**Margin rule (the P11-23 rule, unchanged):** pooled gap g_{d,j} = wrong_Y / n_Y - wrong_L / n_L; s_d = mean_j g_{d,j}; leave-one-user-out means s_{d,-u}; jackknife SE_d over the 8 users; U_d = s_d + 1.8946 x SE_d; **m_LX = max(0, max_d U_d)**; **alpha_LX = floor((0.05 - m_LX) x 10^4) / 10^4**. If a direction has fewer than 30 guards, or m_LX >= 0.05, arm LX-M is not run and the item reports why (outcome "margin not estimable").

Why the guarantee holds: as P11-23 section "Why the guarantee still holds". m_LX reads no track-val or track-test window and is fixed before the arm LX-M calibration. LTT at alpha_LX keeps its exact guarantee on the calibration population. Under assumption (A2) R_test(g) <= R_val(g) + m_LX, P(R_test(g) > 0.05) <= delta. (A2) is an assumption; arm LX-M on track test is a check of it.

## Arms on track val -> track test (K = 40 partition-only draws each)
Draw k of every arm uses the P11-18 arm P partition: seed s_k = seed_of(`"p11-18|emg|cal|<k>"`), `draw_order(1224, s_k, None)`, split 306 / 459 / 459, no resampling, the LX model refitted on fit + policy, calibrate controls with the draw's random state, user null inputs = 300 input-level time-shuffled calibration windows picked by `default_rng(s_k).choice(1224, 300, replace=False)` (as P11-18). Decisions on all 1,221 test prompts: real, time-shuffled, zero EMG.

| Arm | Role | LTT level |
|---|---|---|
| **LX-M** | **primary** | alpha_LX (LX-specific margin from stage 1) |
| LX-P | secondary: lever 1 alone | 0.05 (no margin) |
| LX-T | secondary: robustness to the L-FL margin | 0.0314 (P11-23 alpha'', m2 = 0.0185) |

If alpha_LX = 0.0314, arm LX-M equals arm LX-T by construction (same seeds, same level); then LX-T is not run again and reports the LX-M draws. If alpha_LX = 0.05 (m_LX = 0), LX-M equals LX-P in the same way.

Scoring per draw: the sheet keeps alpha = 0.05 (the claim); `ltt_alpha` and the margin are recorded beside it. **Above alpha:** test wrong commits / 1,221 > 0.05 (>= 62 wrong). **Credit (P11-17 rule):** a draw adds its value only if the calibrate controls pass, the safe WPM status is `certified`, and V6 passes; else it adds 0.0.

## Checks
| Id | Check | Rule |
|---|---|---|
| X1 (must pass) | **exact reproduction of P11-16**: this code with the P11-16 seeds and bootstrap seeds reruns P11-16 draws k01 and k07 (one certified, one above alpha) | same model digest, threshold, commits, prefix commits, wrong commits, raw value and all 3 x 1,221 actions as `derived\p11-16\draw-k01.json` and `draw-k07.json` |
| X2 (must pass) | session a / b analyses equal the P11-14 analyser outputs in the P11-23 memo (read only) | for every a / b window: same status, top-1, native n-best (1e-9) and the 10 signals (1e-9); fU softmax of the top text = `p_fU` (1e-9) |
| X3 (must pass) | the stage-1 a / b windows are the P11-20 windows | prompt counts per session = P11-20 `prompts-ab.json` counts |
| X4 (must pass) | the recount of LTT wrong commits with `prefix_outcome` equals `ltt_prefix_threshold` `empirical_risk` x n | in every draw with a guard |
| C-null (must pass for "clearly above") | every primary draw: test time-shuffled and zero-EMG commits = **0 / 1,221** | stricter than V6 (<= 5 %) |
| C-cal | calibrate controls (uniform, frame-shuffled, user null) <= 15 / 300 | library allowance; a failed draw earns 0 |

If X1, X2, X3 or X4 fails, no margin and no arm result are reported, and the gap stays open.

## Hypotheses and decision rules (fixed here)
- **H1 (primary):** arm LX-M calibration-inclusive proposed-v0.2 interval (40 draws x the same B = 2,000 user-cluster weight vectors as P11-16 / P11-17; non-credited draws earn 0.0; pooled 2.5 / 97.5 percentiles; point = mean of draw values) has its **lower end above 3.09**.

| Outcome of H1 (P11-17 verdict rule) | conclusion |
|---|---|
| lower end > 3.09 and C-null passes | **"clearly above after calibration uncertainty"** (target met) |
| mean > 3.09 >= lower end | "above, but inside the combined interval" (target not met) |
| mean <= 3.09 | "not above" |

If C-null fails, the verdict can be at best "above, but inside the combined interval".

- **H2 (primary arm safety):** f_LXM = draws above alpha of 40. 0 or 1: "margin removes the excess"; 2 to 4: "within delta, excess not removed"; >= 5: "margin not enough". (A2) is "not contradicted on test" if the mean test rate <= 0.05 and f_LXM <= 4; else "(A2) fails on test".
- **H3 (lever 1 alone, secondary):** f_LXP < 7 (P11-16 bootstrap count). Reported with a one-sided Fisher test (7 / 40 vs f_LXP / 40); descriptive, no gate.
- **Robustness (secondary):** the arm LX-T interval verdict. If H1 is met but LX-T is not "clearly above", results.md says: "met with the LX-specific margin; not robust to the larger L-FL margin".
- **Why-not analysis (fixed now, reported whatever H1 gives):** X1-style decomposition of each arm interval (between-draw SD, within-draw SD, normal interval); the count of zero draws; the lowest credited draw values and their commits; for LX-M, the lower end that the 40 credited raw values would give with zero draws counted at their raw value (descriptive). If H1 fails, results.md names the limiting part (zero draws, low certified draws, or within-draw user spread) with these numbers, and states what data would lift it (number of users for the within-draw part; calibration size n from the 1 / sqrt(n) law for the between-draw part).

Expectation (not a rule): m_LX is near the L-FL m2 (0.0185) or smaller, because LX-FL commits more sure prefixes. LX-M keeps 0 or 1 draws above alpha, loses part of its value (fewer commits), and its lower end is above 3.09.

## Metrics
Stage 1: X2, X3; per direction: guards, s_d, SE_d, U_d, per-draw gap spread, leave-one-user-out spread, per-user spread (unlabelled), LTT and evaluation rates, commits, thresholds, control commits; m_LX, alpha_LX; comparison with the L-FL m2 0.0185. Arms: f (above alpha), above ltt_alpha (descriptive), significant exceedances (>= 75 wrong), test rate, LTT in-sample rate, optimism gap, commits, prefix commits, wrong commits, thresholds, statuses, control counts; paired with P11-16 (same k, bootstrap) and between arms (wrong count down / same / up; exact McNemar on above-alpha); interval, decomposition, library `calibration_draw_interval` (secondary; prompt-level inner level) and verdict vs 3.09.

## Compute cap
- CPU only; 2 worker processes x 1 thread, isolation class `background`; peak memory about 1.5 GB per worker (total under 4 GB).
- 200 LX draws (80 stage 1 + 3 x 40 arms, fewer if an arm equals another) at about 25 s each, plus about 2,442 new a / b window analyses and up to 1,224 new null windows: expected about 1 h of wall time. **Cap: 4 h wall time.** If the cap is reached, the run stops and results.md reports what finished; no rule changes.
- Detached, from a `git archive` snapshot of the committed code; log `results/run.log`; checkpoint = one file per finished draw (`derived\p11-21\draw-<name>.json`, skipped on a rerun); `DONE` / `FAILED` files and a `STOP` file (`derived\p11-21\STOP`: workers stop after the current draw).

## Gap rule
**Gap 166 closes** when results.md reports, under this plan with X1-X4 passed, the arm LX-M calibration-inclusive interval vs 3.09 with its verdict, and (if the lower end is not above 3.09) the why-not analysis with the numbers above. If a must-pass check fails, or arm LX-M cannot run (margin rule), results.md says why, and the gap stays open.

## What was done before this plan (disclosure)
Reading of the gap 166 and 159 entries, the roadmap row, the P11-16 / P11-17 / P11-18 / P11-20 / P11-23 / P15-37 / P15-40 plans and results, the P11-16 and P11-23 `run.py` and `launch.py`, `dropin._run_controls` and `commit_score.ltt_prefix_threshold`. Listing of the P11-16 / P11-20 / P11-23 derived folders, the P11-16 `feat.status.json` and the draw run times (about 25 s), and the row count and field names of `prompts-ab.json` (2,442 rows). **Not known:** any LX-FL number on sessions a / b, m_LX, alpha_LX, any LX-FL partition-only draw, any arm result. No draw, guard or score of this item was computed before this commit.

## Order and outputs
1. Commit and push this plan. Then commit `run.py`, `launch.py` and a test on synthetic data.
2. Run: stage 1 (2 workers), `margin` (X1-X3 first), arms (2 workers), `analyse`.
3. The repo gets `results/results.json` (aggregates, per-draw pooled counts, unlabelled spread statistics) and `results/run.log`. No change of levers, arms, seeds, rules or metrics after this commit; a later variant is a new item.

## Known limits (stated before any result)
- (a) The margin is estimated from two directions between the same two sessions (P11-23 limit a); the backward step is not a real time step.
- (b) Sessions a and b selected the decoder checkpoints (slightly in-sample).
- (c) (A2) is an assumption; one test set checks it.
- (d) Pinned decoder, gate, LM, lexicon and the LX feature set were chosen on track-val prompts (P11-16 limits).
- (e) All draws share the same 1,224 calibration and 1,221 test prompts; the spread is split variation only.
- (f) 8 users: the within-draw user-cluster spread is fixed by the data.
- (g) Proposed v0.2 only; the adopted v0.1 value of LX-FL is much lower (P11-16: 2.60).
