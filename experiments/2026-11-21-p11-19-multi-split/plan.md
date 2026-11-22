---
title: P11-19 Multi-split EMG L-FL guard with a calibration-inclusive lower end above no-BCI - pre-registration
type: experiment
task: P11-19
updated: 2026-11-21
---

# P11-19: multi-split EMG L-FL sentence guard, calibration-inclusive lower end vs no-BCI 3.09 (pre-registration)

Written and committed **before** any number of this item was computed. Gap 159 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-19](../../wiki/questions/roadmap-standard.md#p11-19-lower-variance-emg-l-fl-guard-with-a-calibration-inclusive-lower-end-above-no-bci). Bases: [P11-17](../2026-11-21-p11-17-emg-calibration-ci/plan.md) (interval and credit rule), [P11-18](../2026-11-21-p11-18-emg-above-alpha/plan.md) (partition-only draws), [P11-20](../2026-11-21-p11-20-emg-shift-robust/plan.md) and [P11-23](../2026-11-21-p11-23-shift-margin-steps/plan.md) (L-FL shift margin), [P15-37](../2026-11-21-p15-37-multi-split/method.md) (guarantee-keeping multi-split rules), [P11-21](../2026-11-21-p11-21-lx-margin/plan.md) (the same target for the LX-FL prefix guard).

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates and per-draw counts only: no per-user value, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-19\`. All other derived folders are read only.

CPU only, **no GPU**, no new inference. 2 workers x 1 thread, isolation class `background`.

## Scope: commit unit, metric version, done-when
| Item | Value |
|---|---|
| Guard | P11-14 arm **L-FL** (learned confidence `Learned.fit` on the 10 signals, decoder FL), certified by `fidetype.trust.calibrate` (LTT) |
| Commit unit | the **whole sentence** (one commit per prompt; credit only if the committed text equals the intended text) |
| Metric version | **`safe-wpm/0.1` (adopted)**. For sentence-level policies v0.1 and the proposed v0.2 give the same value ([docs/safe-wpm.md](../../docs/safe-wpm.md) section 6a). So this item does **not** depend on the v0.2 proposal (unlike P11-21). |
| Interval | the calibration-inclusive two-level interval of `docs/safe-wpm.md` section 6b (a PROPOSED reporting addition, not adopted), with the P11-17 user-cluster inner level |
| Done-when (gap 159) | "a pre-registered run applies the P15-37 multi-split method (BMED-3 or AND arms, chosen on calibration data only) or a safety-margin guard (P15-34) to EMG L-FL and reports a calibration-inclusive interval whose lower end is above 3.09, **or numbers show why that is not reachable**." |

The safety-margin branch is already used by P11-20 (6.13 [2.62, 9.47]) and P11-23 (5.47 [2.44, 8.77]); neither lower end is above 3.09. This item applies the **multi-split branch on top of the P11-23 margin**. Both branches of the done-when are covered: the target branch (lower end > 3.09) and the "why not reachable" branch (a pre-registered why-not analysis, below, reported whatever H1 gives).

## What limits the L-FL lower end today (committed numbers only)
| Item | Draws, level | Interval | Draws above alpha | between / within SD |
|---|---|---|---|---|
| P11-17 | bootstrap, 0.05 | 5.00 [0.00, 9.55] | 9 / 40 | 2.94 / 1.19 |
| P11-18 arm P | partition-only, 0.05 | 5.65 [0.00, 9.45] | 3 / 40 | |
| P11-20 arm S | partition-only, 0.0455 (m 0.0045) | 6.13 [2.62, 9.47] | 0 / 40 | 1.14 / 1.31 |
| P11-23 arm S2 | partition-only, 0.0314 (m2 0.0185) | 5.47 [2.44, 8.77] | 0 / 40 | 1.07 / 1.23 |

From the committed P11-23 `results.json` (per-draw rows, already public): the S2 draw values range 2.25-7.03 (median 5.70); 22 / 40 S2 thresholds are at **0.30, the lowest point of the `commit_p` grid** (`fidetype.trust.policy`); at that threshold the commits still range from 66 (S13, 2.25) to 243. So in about half the draws LTT is not the active limit: the grid floor is, and the value then depends on how well the refitted L model ranks the prompts. The low draws (S13 2.25; S03, S06, S12, S27 about 3.6) come from this model-fit and partition variation.

Two parts limit the lower end, with zero draws already removed by partition-only draws plus the margin:
1. **Between-draw spread** (SD 1.07): low draws from unlucky partitions / model fits.
2. **Within-draw user-cluster spread** (SD 1.23, 8 users): fixed by the data and the guard. With a normal approximation, even with zero between-draw spread the lower end is about mean - 1.96 x 1.23; at the S2 mean 5.47 this is 3.06 < 3.09. **So a method that only removes between-draw spread cannot reach the target at the S2 mean.** The mean must also rise.

## Lever (this item): Bonferroni + selection over J = 3 splits (P15-37 rule B), on top of the P11-23 margin
P15-37 method.md (B): calibrate J split guards g_1 ... g_J on J different partitions of the same calibration set, each by LTT at (alpha_LTT, delta / J). Deploy g_j-hat, where j-hat is **any function of the calibration data**. By the union bound, P(R(g_j-hat) > alpha_LTT) <= P(some R(g_j) > alpha_LTT) <= J x delta / J = delta. With the P11-23 margin and assumption (A2) (R_test(g) <= R_val(g) + m2 for each g_j), P(R_test(g_j-hat) > 0.05) <= delta = 0.1.

Why this lever can lift both parts: selection by calibration value avoids an unlucky partition / model fit (part 1) and raises the mean (needed for part 2). In the grid-floor draws the stricter delta / 3 costs nothing. This is a hypothesis, not a result: on T15 (P15-37) BMAX-2 gained only +0.12 and BMAX-3 had one above-alpha draw.

### Fixed parts (as P11-14 / P11-17 / P11-18 / P11-23, unchanged)
Data, windows, target, decoder FL, the no-signal gate, the OOV gate, the competitor set and the 10 signals; the L model rule (P11-17 `fit_model`: `Learned.fit` on the committable fit + policy prompts); `calibrate` settings (LTT, `confidence="p_top1"`, `input_kind="logits"`, key-CTC vocabulary, `audit_text=False`, automatic uniform and frame-shuffled null trials; user null inputs = the 300 input-level time-shuffled calibration windows `sorted(default_rng(s_k).choice(1224, 300, replace=False))`, as P11-18 / P11-23); safe WPM v0.1 with the default correction rule; no reading cost; no-BCI reference 3.09; the P11-17 credit rule; the claim alpha = 0.05, delta = 0.1. **Margin: m2 = 0.0185, alpha'' = 0.0314** from P11-23 (`derived\p11-23\margin.json`, read only; it reads no track-val or track-test window, P11-23 "Why the guarantee still holds"). It is not re-estimated. The P11-17 / P11-18 / P11-20 / P11-23 runners are imported for their pure helpers only; their `own()`, `log()` and memo files are never written. The window memo of this item starts from a read-only copy of the P11-23 memos (`derived\p11-23\feat-w0.pkl`, `feat-w1.pkl`; window-content keys) and is saved only in `derived\p11-19\`.

### Split guards (track val, 1,224 prompts)
For draw k = 1 ... 40 and split j = 1, 2, 3:
- seed s_k1 = seed_of(`"p11-18|emg|cal|<k>"`) (the P11-18 / P11-20 / P11-23 partition of draw k); s_k2 = seed_of(`"p11-19|emg|split|<k>|2"`); s_k3 = seed_of(`"p11-19|emg|split|<k>|3"`). seed_of(tag) = first 8 hex digits of SHA-256(tag), as an integer.
- Partition: P11-17 `draw_order(1224, s_kj, None)`, split 306 / 459 / 459, no resampling; L model refitted on fit + policy; `calibrate(..., alpha=0.0314, delta=0.1/3, seed=s_kj, null_inputs=<the draw-k user nulls>)`.
- Record per split guard: status (guard / refused), sheet, threshold, feasible, model digest, controls, decisions on the 1,224 calibration prompts (real) and on the 1,221 test prompts (real, time-shuffled, zero EMG).
- **In-sample value v_kj** = the safe-WPM v0.1 formula on all 1,224 calibration prompts with the guard's real decisions (commit and correct; no certification step). A refused guard has no in-sample value and is never deployed.

### Arms (track val -> track test, K = 40 draws)
| Arm | Role | Deployed rule per draw |
|---|---|---|
| **BX3** | **primary** | the split guard with the **highest** v_kj (ties: lowest j). Rule B with selection on calibration data only. |
| BD3 | secondary (the rule named in the done-when) | the split guard with the **median** v_kj (with 2 non-refused guards: the lower one; with 1: that one) |
| AN3 | descriptive | AND of the 3 split guards: commit only if all 3 commit the same text (P15-37 rule A; R(AND) <= R(g_k1) pointwise, so AND of delta / 3 guards also keeps the claim). Any refused split guard: AND refused. |
| S2 | reference (read only, no new run) | P11-23 arm S2 (one guard per draw at (0.0314, 0.1); the j = 1 partition) |

Not run, and why: AND of full-delta split guards (it needs 80 more calibrations, about 1.8 h, and it can only lower commits; the target needs a higher mean); J = 2 or 4 (one J keeps the compute cap; J = 3 is the P15-37 primary size); a lower `commit_p` grid floor (it changes the guard, not the calibration method; outside the done-when; a later item).

Scoring per draw (all arms): the guarantee dict of the deployed guard carries the **claim** alpha = 0.05, delta = 0.1, plus `ltt_alpha` 0.0314, `split_delta` 0.1 / 3, `rule`, `J`. **Above alpha:** test wrong commits / 1,221 > 0.05 (>= 62 wrong). **Credit (P11-17 rule):** a draw adds its value only if the deployed guard (for AN3: every split guard) passed its calibrate controls, the safe WPM status is `certified`, and V6 passes (test time-shuffled and zero-EMG commit rates <= 5 %); else 0.0.

## Checks
| Id | Check | Rule |
|---|---|---|
| X1 (must pass) | **exact reproduction of P11-23**: this code at (0.0314, delta 0.1) with seeds s_1,1 and s_13,1 and the P11-23 guard names reruns S01 and S13 | same model digest, threshold, commits, wrong commits, value and all 3 x 1,221 actions and texts as `derived\p11-23\draw-S01.json` and `draw-S13.json` |
| X2'' (must pass; gap 180) | fresh decodes: an analyser with an **empty memo** analyses 100 track-val + 100 track-test real windows (`default_rng(1919).choice`, sorted, per session) and 50 time-shuffled test windows (`default_rng(1920)`) | status, top-1, native n-best texts and scores (1e-9) and the 10 signals (1e-9) equal the memo entries this item uses |
| X3 (must pass) | split-1 partitions are the S2 partitions | `draw_info.sha_desired` of split 1 = P11-23 S_k, 40 / 40 |
| X4 (must pass) | the LTT wrong-commit recount with `R.same` equals the sheet `ltt_wrong_commits` | every non-refused split guard |
| C-null (must pass for "clearly above") | every BX3 draw: test time-shuffled and zero-EMG commits = **0 / 1,221** | stricter than V6 |
| C-cal | calibrate controls <= 15 / 300 | library allowance; a refused split guard is never deployed |

If X1, X2'', X3 or X4 fails, no arm result is reported and the gap stays open (an amendment, if any, is written before any arm number is looked at).

## Hypotheses and decision rules (fixed here)
- **H1 (primary):** the arm BX3 calibration-inclusive safe-WPM v0.1 interval (40 draws x the P11-17 B = 2,000 user-cluster weight vectors `cluster_weights(..., seed=0)`; non-credited draws earn 0.0; pooled 2.5 / 97.5 percentiles; point = mean of the draw values) has its **lower end above 3.09**.

| Outcome of H1 (P11-17 verdict rule) | conclusion |
|---|---|
| lower end > 3.09 and C-null passes | **"clearly above after calibration uncertainty"** (target met; gap 159 closes on its target branch) |
| mean > 3.09 >= lower end | "above, but inside the combined interval" (target not met) |
| mean <= 3.09 | "not above" |

If C-null fails, the verdict is at best "above, but inside the combined interval".

- **H2 (safety of BX3):** f = draws above alpha of 40. 0 or 1: "multi-split keeps the excess removed"; 2 to 4: "within delta"; >= 5: "selection raises the risk". (A2) is "not contradicted on test" if the mean test rate <= 0.05 and f <= 4.
- **H3 (secondary):** the BD3 verdict. If BD3 is "clearly above" but BX3 is not, the target is **not** met (one primary).
- **Paired (descriptive):** BX3 vs S2 per draw: value up / same / down, mean paired difference, exact McNemar on above-alpha; the same for BD3 and AN3; how often j-hat = 1 (the S2 partition).

### Why-not analysis (fixed now; reported whatever H1 gives)
For BX3, BD3, AN3 and S2:
1. Decomposition (P11-17 X1): mean, between-draw SD sigma_b, within-draw SD sigma_w, normal interval; the number of zero draws; the 3 lowest draw values with commits and thresholds; the count of thresholds at the grid floor 0.30.
2. **Floor F_w = mean - 1.96 x sigma_w**: the normal-approximation lower end with zero between-draw spread. If F_w <= 3.09, no calibration-variance method can reach the target at that mean; only a higher mean or a smaller user spread can.
3. **Data that would be needed** (rough, normal approximation; assumptions stated in results.md): with h = (mean - 3.09) / 1.96,
   - users: n_u* = 8 x sigma_w^2 / (h^2 - sigma_b^2) if h > sigma_b (sigma_w proportional to 1 / sqrt(number of users), calibration fixed); else "not reachable by more users alone";
   - calibration prompts: n_cal* = 1,224 x sigma_b^2 / (h^2 - sigma_w^2) if h > sigma_w (sigma_b proportional to 1 / sqrt(n), P15-37 / P15-40 law); else "not reachable by more calibration data alone".

If H1 fails, results.md names the limiting part with these numbers. That is the "numbers show why it is not reachable" branch of the done-when.

Expectation (not a rule): BX3 has a higher mean than S2 (about +0.5) and a smaller sigma_b; sigma_w stays about 1.2; the lower end is near 3.09, and it may land on either side. F_w for S2 is about 3.06 (above), so S2 alone could not pass.

## Metrics
Per arm: f (above alpha), above ltt_alpha (descriptive), significant exceedances (>= 75 wrong), test rate, LTT in-sample rate, optimism gap, commits, wrong commits, thresholds, statuses, control counts, in-sample values, j-hat distribution; interval, decomposition, F_w, n_u*, n_cal*, the library `calibration_draw_interval` (secondary; prompt-level inner level) and the verdict vs 3.09. Split guards: count refused / infeasible, thresholds at the grid floor, per-split mean value on test (descriptive).

## Compute cap
- CPU only; 2 worker processes x 1 thread, isolation class `background`; peak memory under about 4 GB in total.
- 2 X1 draws + 120 split calibrations at about 150-165 s each (the P11-23 S2 draw time), plus 250 fresh analyses for X2''. Expected about 2.8 h wall time. **Cap: 5 h wall time.** If the cap is reached, the run stops; results.md reports what finished and the arms over the finished draws only as descriptive; no rule changes.
- Detached, from a `git archive` snapshot of the committed code (other agents change `src/`); log `results/run.log`; checkpoint = one file per finished split guard (`derived\p11-19\split-k<kk>-j<j>.json`, skipped on a rerun); `DONE` / `FAILED` files; a `STOP` file (`derived\p11-19\STOP`: workers stop after the current split guard).

## Gap rule
**Gap 159 closes** when results.md reports, under this plan with X1, X2'', X3 and X4 passed, the arm BX3 calibration-inclusive interval vs 3.09 with its verdict and the why-not analysis. If the lower end is above 3.09 (and C-null passes), it closes on the target branch. If not, it closes on the "numbers show why" branch only if the why-not analysis names the limiting part and the data needed; the orchestrator / user may instead keep it open. If a must-pass check fails, results.md says why and the gap stays open.

## What was done before this plan (disclosure)
Reading of the gap 159 row and the tracker entry; the P11-17, P11-18, P11-20, P11-21, P11-23 and P15-37 plans and results; the P11-17 and P11-23 `run.py`, the P11-21 `launch.py` and `x2_fresh.py`; `docs/safe-wpm.md` sections 1, 6a, 6b; `dropin._split`, `calibrate` parameters, the `commit_p` grid in `trust/policy.py`, and `safe_wpm.certification`. From committed results files only: the P11-23 S2 per-draw values, commits, thresholds and run times, and the P11-23 `margin.json` (alpha'' 0.0314). **Not known:** any multi-split guard, any in-sample value, any BX3 / BD3 / AN3 number. No guard, decision or score of this item was computed before this commit.

## Order and outputs
1. Commit and push this plan. Then commit `run.py`, `launch.py` and a test on synthetic data.
2. Run: X2'' and X1 first (the chain stops if either fails), then the 120 split guards (2 workers), then `analyse` (X3, X4, arms, intervals, why-not analysis).
3. The repo gets `results/results.json` (aggregates, per-draw pooled counts) and `results/run.log`. No change of levers, arms, seeds, rules or metrics after this commit; a later variant is a new item.

## Known limits (stated before any result)
- (a) The margin m2 comes from two directions between the same two sessions (P11-23 limit a); (A2) is an assumption, and one test set checks it.
- (b) Sessions a and b selected the decoder checkpoints (slightly in-sample).
- (c) Pinned decoder, gate, LM, lexicon and arm choice were tuned on track-val prompts.
- (d) All draws share the same 1,224 calibration and 1,221 test prompts; the spread is split variation only.
- (e) 8 users: the within-draw user-cluster spread is fixed by the data.
- (f) The interval method (section 6b) is a proposed reporting addition, not adopted.
- (g) The split-2 and split-3 partitions of a draw overlap the split-1 partition (same 1,224 prompts); the union bound does not need independence.

## Amendment 1 (2026-11-21 about 21:35, before any split guard of phase 2, any in-sample value or any arm number existed)
**What happened.** The first chain (code `1a281e6`, launched 21:16) ran X1 and the checks stage, then stopped, as the plan requires, because X2'' failed. **X1 passed** (X01 = P11-23 S01 and X13 = P11-23 S13: same model digest, threshold, commits, wrong commits, value and all 3 x 1,221 actions and texts). **X2'' failed:** 14 of the 250 sample windows (track val, track test, time-shuffled test) differ between a fresh decode (empty memo) and the P11-23 memo copy. No phase-2 split guard, no in-sample value, no arm draw and no interval was computed. Before the code commit, a scratch smoke run computed X01 only (it matched P11-23 S01); its files stay in the agent scratch folder.

**Diagnosis (read-only script in the agent scratch folder).** In all 14 windows the status, top-1 and n-best texts are equal. The native n-best scores differ by up to about 3e-5, and some of the signals `p_nb`, `p_fU`, `p_aU`, `ac_gap` differ by about 1e-9 to 3e-8 (tolerance 1e-9). This is the gap 180 effect (P11-21 amendment 1: stored memo entries differ a little from fresh decodes), now also seen in track windows and in the signals.

**Change (memo source and check definitions only; no lever, arm, seed, level, rule, metric or decision rule changes).**
- **Fresh decodes.** The window memo of this item starts **empty**; it is not copied from P11-23. Every window analysis of phase 1 and phase 2 is a fresh decode by the run code. The first memo files (P11-23 copy plus X1 additions) are moved to `derived\p11-19\memo-p1123-copy\` and are not used again. The first X1 files and `checks.json` are kept in the same folder as the record of the first run.
- **X1 (must pass): kept as run.** It passed under the P11-23 memo copy, so the code reproduces P11-23 exactly on the memo that P11-23 used.
- **X1' (descriptive, new):** the same two draws again with the fresh memo (XF01, XF13). Report: equal threshold, commits, wrong commits, value and actions (count of differing actions), model digest equal or not. If any action differs, the paired BX3 / BD3 / AN3 vs S2 comparisons are labelled "approximate (memo world vs fresh world)"; arm J1 (split 1 at delta / 3, fresh) is then the clean paired reference for the Bonferroni cost.
- **X2f (must pass, replaces X2''):** the same 250 sample windows (seeds 1919 / 1920), analysed by a second analyser with an empty memo, equal the entries of this item's fresh run memo exactly (status, top-1, native texts and scores within 1e-9, the 10 signals within 1e-9). This shows that the fresh decodes of this item are reproducible. The original X2'' comparison with the P11-23 memo is reported as a descriptive count (14 / 250).
- Chain: phase 1 (XF01, XF13), checks (X1 from the first run, X1', X2f), phase 2, analyse, from a new code snapshot.

## Amendment 2 (2026-11-21 21:45, before any phase-2 split guard, in-sample value or arm number existed)
**Time correction for amendment 1:** its header says "about 21:35"; it was written at about 21:21 (the relaunch log shows 21:23).

**What happened.** The second chain (code `fca492e`) ran XF01 and XF13 with the fresh memo and the checks stage. **X1 passed** (first run) and **X1' is exact**: with fresh decodes, XF01 and XF13 give the same model digest, threshold, commits, wrong commits, value and all 3 x 1,221 actions as P11-23 S01 and S13 (0 differing actions). **X2f failed**: of the 250 sample windows, 159 are not in the run memo under their raw-window key (the guard path decodes windows through `calibrate` / `decide`, so many entries have other keys), and 17 of the 85 present entries differ from a second fresh analyser. The checks stage then stopped with an error in the descriptive X2'' count (a missing key). No phase-2 guard and no arm number exists.

**Diagnosis (read-only script in the agent scratch folder).** In one script process, two empty-memo analysers give identical analyses of 200 sample windows, in forward and in reverse order, and on a second pass (0 differences). So fresh decodes in a fresh process are deterministic and order-independent. The worker-process entries differ from them in a few windows by the small amounts seen in amendment 1 (signals about 1e-9 to 3e-8, native scores about 1e-5). The cause is a state difference between processes that we did not find (gap 180). It changes no decision in X1'.

**Change (check definitions only; no lever, arm, seed, level, rule, metric or decision rule changes).**
- **X2f becomes descriptive:** report the present / not-present counts, the mismatch count and the maximum signal and native-score differences (crash fixed).
- **Must-pass reproduction = X1 and X1'** (decision-level, exact, both already passed). The arms are computed in the fresh world, so the reported decisions do not depend on the P11-23 memo.
- Limit added: window analyses can differ between processes by up to about 3e-8 in the signals (gap 180); X1' shows no decision change in 2 x 3 x 1,221 actions, but a flip near a threshold in other draws cannot be excluded.
