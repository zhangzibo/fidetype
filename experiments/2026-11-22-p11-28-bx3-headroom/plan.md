---
title: P11-28 Safety headroom of the EMG BX3 guard - pre-registration
type: experiment
task: P11-28
updated: 2026-11-22
---

# P11-28: safety headroom of the EMG BX3 guard (pre-registration)

Written and committed **before** any number of this item was computed. Gap 183 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P11-28](../../wiki/questions/roadmap-standard.md#p11-28-safety-headroom-of-the-emg-bx3-guard). Base: [P11-19](../2026-11-21-p11-19-multi-split/plan.md) (plan `c71c9bc`, amendments `445c714` and `c3df8ad`, results `749f192`).

**RESEARCH ONLY.** emg2qwerty data is CC BY-NC-SA 4.0. The repo gets pooled aggregates and per-draw counts only: no per-user value, no text, no prompt id, no signal, no weights. Every output carries `data.licence = "CC-BY-NC-SA-4.0"` and `data.research_only = true`. Per-prompt files stay in `C:\Users\zhang\bci-data\derived\p11-28\`. All other derived folders (`p11-19`, `p11-23`, ...) are read only.

CPU only, **no GPU**, no new inference. 2 workers x 1 thread, isolation class `background`, low priority.

## Question
P11-19 arm BX3 (J = 3 Bonferroni split guards per draw, each at (alpha'' 0.0314, delta / 3); deploy the guard with the highest in-sample safe WPM on the 1,224 calibration prompts) passed its value target: 5.90 [3.45, 8.89] vs no-BCI 3.09. Its safety cost (committed numbers): test wrong-commit rate mean 0.0281, max 0.0434; 13 / 40 draws above alpha'' 0.0314; 0 / 40 above the claim 0.05. With 40 draws, 0 / 40 gives a one-sided 95 % Clopper-Pearson (CP) upper bound of 0.072 on the exceedance probability. The tail near 0.05 is not well measured. **Does BX3 keep the claim P(test rate > 0.05) <= delta = 0.1 with headroom, and how large is the headroom?**

## Options considered (choice and reason)
| Option | Run? | Reason |
|---|---|---|
| (1) More BX3 draws | **yes (primary)** | It measures the tail directly. 40 new draws (k = 41 ... 80, 120 split guards, about 3.4 h with 2 workers) fit the cap. 80 new draws (240 guards, about 6.7 h) do not fit the 5 h cap. The P11-19 draws k = 1 ... 40 are the same design and are pooled (read only). |
| (4) Selection rule with a safety tie-break | **yes (secondary, no extra compute)** | It uses the same split guards. Rule BXS below. It is a function of calibration data only, so the union bound still holds. |
| (2) J = 2 | **partly (secondary, no extra compute)** | A true J = 2 needs new guards at delta / 2. Rule BX2 (max of splits 1 and 2, both at delta / 3) uses the existing guards. It is conservative (2 x delta / 3 <= delta) and shows the effect of a smaller selection set. |
| (2) J = 4 | no | It needs 4 new guards per draw at delta / 4 (160 guards for 40 draws, about 4.5 h): with option (1) this is over the cap. More selection gives more selection optimism, so it is expected to lower the headroom, not raise it. A later item if needed. |
| (3) Lower `commit_p` grid floor | no | A lower floor lets the grid-floor guards (30 / 120 in P11-19) commit more. That raises value and the test rate. It targets value, not headroom. It also changes the guard (`fidetype.trust.policy` grid), not the calibration method. A later item if needed. |

## Fixed parts (as P11-19, unchanged)
Everything of the P11-19 split guard is unchanged: data, windows, decoder FL, gates, the 10 signals, the L model rule, `calibrate` settings, user null inputs, alpha'' = 0.0314 (P11-23 m2 = 0.0185, read only), the claim alpha = 0.05, delta = 0.1, J = 3, split delta = 0.1 / 3, safe WPM v0.1 with the default correction rule, no-BCI 3.09, the P11-17 credit rule and interval (B = 2,000 user-cluster weight vectors `cluster_weights(..., seed=0)`). The code imports the P11-19 `run.py` (read only) and calls its `run_guard`, `select`, `and_actions`, `score_actions` and `x1_compare`. Its module paths are redirected by the environment variables `P1119_OWN` = `derived\p11-28` and `P1119_OUT` = this folder's `results\`. The P11-19 folder and `derived\p11-19\` are never written.

**Fresh decodes only.** The window memo of this item starts **empty** (P11-19 amendment 1). No memo file of another item is copied.

### New draws
For k = 41 ... 80 and j = 1, 2, 3: seed s_kj = P11-19 `split_seed(k, j)` (j = 1: seed_of(`"p11-18|emg|cal|<k>"`); j = 2, 3: seed_of(`"p11-19|emg|split|<k>|<j>"`)); null seed = s_k1; `calibrate(..., alpha=0.0314, delta=0.1/3)`; guard name `p11-28-k<kk>-j<j>`. No seed of k = 41 ... 80 was used by any item before. The old draws k = 1 ... 40 are the P11-19 split files in `derived\p11-19\` (read only).

## Checks (run first)
| Id | Check | Rule |
|---|---|---|
| X1' (must pass) | the P11-19 X1' reproduction, repeated: this code with an empty memo reruns P11-23 S01 and S13 at (0.0314, delta 0.1) | same model digest, threshold, commits, wrong commits, value, statuses and all 3 x 1,221 actions and texts as `derived\p11-23\draw-S01.json` / `draw-S13.json`, and as the P11-19 files `split-XF01.json` / `split-XF13.json` |
| X5 (must pass) | the P11-19 phase-2 reproduction: this code reruns the P11-19 split guards k01-j2 and k13-j3 at (0.0314, delta / 3) | the same fields, plus `v_in`, as `derived\p11-19\split-k01-j2.json` / `split-k13-j3.json` (this justifies pooling old and new draws) |
| X1 (P11-19, with the P11-23 memo copy) | not repeated | it needs a copy of the P11-23 memo; this item uses fresh decodes only |
| X4 (must pass) | LTT wrong-commit recount equals the sheet count | every new non-refused split guard |
| X6 (must pass) | the analysis code rebuilds P11-19 BX3 from the old split files | the 40 old BX3 draws give the committed P11-19 test-rate mean 0.028112203112203117 and interval point value 5.898744142080952 (both from the committed `results.json`) to 1e-9 |
| C-null | every new BX3 draw: test time-shuffled and zero-EMG commits = 0 / 1,221 | reported |

If X1', X5, X4 or X6 fails, no arm result is reported and the gap stays open. An amendment, if any, is written before any arm number is looked at. A sleep or process restart does not change the X checks (each split guard is one checkpoint file).

## Hypotheses and decision rules (fixed here)
Notation: for a set of N BX3 draws, r_k = test wrong commits / 1,221 of the deployed guard; f = #{r_k > 0.05}.
- **CP bound** U(f, N) = one-sided 95 % Clopper-Pearson upper bound on P(r > 0.05).
- **Quantile bound** Q(N) = the distribution-free one-sided 95 % upper bound on the 90th percentile (the delta-quantile) of r: the order statistic r_(m) with the smallest m such that P(Bin(N, 0.9) <= m - 1) >= 0.95. For N = 80, m = 77 (the 4th largest rate); for N = 40, m = 40 (the largest). **Headroom** h = 0.05 - Q.

| Id | Rule (set: pooled 80 = P11-19 k 1-40 + new k 41-80) | Outcome |
|---|---|---|
| **H1 (primary, claim)** | U(f80, 80) <= delta = 0.10 (that is f80 <= 3) | pass: "the claim holds on this test set with 95 % confidence over calibration draws"; fail: "selection raises the risk above delta" |
| **H2 (primary, headroom)** | headroom h = 0.05 - Q(80) | h >= 0.005: **"clear headroom"**; 0 < h < 0.005: "thin headroom"; h <= 0: "no headroom". 0.005 is about one binomial SE of a rate near 0.03 on 1,221 prompts |
| H2-rep (replication) | the same on the 40 new draws only: f40, U(f40, 40), Q(40) = max r | reported; if f40 >= 2, the pooled result is labelled "not replicated on new draws" |
| H3 (value, replication) | BX3 calibration-inclusive interval on the 40 new draws, and on the pooled 80 | P11-17 verdict vs 3.09 ("clearly above" / "above, but inside" / "not above"). If the new-40 lower end <= 3.09: "the P11-19 value pass does not replicate on new draws" |

Descriptive (no decision): mean, SD, quantiles and max of r; #{r > 0.0314}; LTT in-sample rate and optimism gap; a normal-fit tail P(r > 0.05) = 1 - Phi((0.05 - mean) / SD); and **test-set uncertainty**: with the 2,000 user-cluster weight vectors, the weighted rate of every draw, the fraction of draws above 0.05 per weight vector, and its median and 95th percentile (all draws share one test set, so U and Q are conditional on it).

**Overall verdict for BX3** (pooled 80): H1 pass and "clear headroom" -> **"BX3 safety holds with headroom h"**; H1 pass and thin / no headroom -> **"the claim holds, but the headroom is thin"** (numbers say why: the selection optimism uses the margin m2); H1 fail -> **"BX3 does not keep the claim with margin"** (numbers say why).

### Secondary rules (same split guards; no extra compute)
| Rule | Deployed guard per draw | Guarantee |
|---|---|---|
| **BXS** (safety tie-break) | among the non-refused split guards, keep those whose LTT in-sample rate `ltt_rate` (on its own LTT part) is <= the median `ltt_rate` of the draw's non-refused split guards; deploy the kept guard with the highest v_in (ties: lowest j) | rule B (a function of calibration data only) |
| BX2 (smaller selection) | the split guard with the higher v_in of j = 1, 2 (ties: j = 1) | union bound 2 x delta / 3 <= delta |
| BD3, J1, AN3 | as P11-19 | as P11-19 |

For each rule (new 40 and pooled 80): f, U, Q, h, mean / max r, the value interval and verdict. A secondary rule **"keeps the pass with more margin"** if on the pooled 80 its Q is lower than the BX3 Q **and** its value lower end is > 3.09 (both). For BXS the new-40 numbers are the clean test (the rule was fixed before any per-split `ltt_rate` was read); the pooled 80 is reported too.

## Gap rule (what closes gap 183)
Gap 183 closes when results.md reports, with X1', X5, X4 and X6 passed: the BX3 test-rate headroom against 0.05 on 80 draws (H1, H2, H2-rep, the test-set uncertainty), the H3 value replication, and the BXS / BX2 comparison. This covers every branch of the done-when: "headroom reported" (H1 pass), "a rule keeps the pass with more margin" (secondary), or "numbers say why not" (H1 fail or thin headroom, with the numbers). If a must-pass check fails, the gap stays open.

## Compute cap
- CPU only; 2 worker processes x 1 thread, isolation class `background`; memory under about 4 GB in total.
- Phase 1: 4 guards (X1' x 2, X5 x 2), about 8 min. Phase 2: 120 guards at about 200 s each (P11-19: 176-268 s), about 3.4 h. **Cap: 5 h wall time.** A worker starts no new split guard after 4.6 h from the chain start. If the cap stops the run, results.md reports the complete draws only, as descriptive; no rule changes.
- Detached, from a `git archive` snapshot of the committed code; log `results/run.log`; checkpoint = one file per split guard (`derived\p11-28\split-<name>.json`, skipped on a rerun); `DONE` / `FAILED` files; `STOP` file (`derived\p11-28\STOP`: workers stop after the current split guard).

## What was done before this plan (disclosure)
Read: the gap 183 row and the P11-28 roadmap section; the P11-19 plan (with amendments), `run.py`, `launch.py`, `test_p11_19.py`, results.md and the head of `results/results.json` (the committed BX3 aggregates above); the P11-17 helpers `draw_order`, `cluster_weights`, `draw_values`, `combined_interval`. Not read: any P11-19 per-split file, any per-split `ltt_rate`, any per-draw BX3 test rate other than the committed aggregates. No guard, decision or score of this item was computed before this commit.

## Known limits (stated before any result)
- (a) All draws share one test set of 1,221 prompts (8 users). U and Q are conditional on it; the cluster bootstrap shows the test-set part only roughly (8 clusters).
- (b) (A2) and the margin m2 come from two sessions (P11-23 limit a).
- (c) Draws share the 1,224 calibration prompts; draws are not independent samples of new calibration sets.
- (d) The old 40 draws were seen as aggregates before this plan (they opened the gap). H2-rep on the new 40 is the clean replication.
- (e) Cross-process decode differences up to about 3e-8 (gap 180) may flip a decision near a threshold; X5 checks two guards only.

## Amendment 1 (2026-11-22 10:25, before any phase-2 split guard or any arm number existed)
**What happened.** The first chain (code `a8877bf`, launched 10:07) ran phase 1 and the checks, then stopped, as the plan requires. **X1' passed** (XF01 and XF13 equal P11-23 S01 / S13 and the P11-19 XF01 / XF13 files in every field, with 0 differing actions). **X5 failed on one field only**: the L-model digest of R-k01-j2 and R-k13-j3 differs from the P11-19 files. Threshold, commits, wrong commits, test value, statuses, `v_in` and all 3 x 1,221 actions and texts are equal (0 differing actions). The model parameters (`coef`, `intercept`, `mean`, `scale`, `hi`) differ by at most about 1e-8. This is the gap 180 effect (window analyses differ between processes by about 1e-9 to 3e-8; P11-19 amendments 1 and 2). The digest hashes the parameters at full precision, so a 1e-9 change gives a new digest. No phase-2 split guard and no arm number exists.

**Change (check definition only; no lever, rule, seed, level, metric or decision rule changes).** In X5 the model digest becomes **descriptive** (reported with the largest parameter difference). X5 must pass on: threshold, commits, wrong commits, test value, statuses, `v_in`, all actions and texts (0 differences), the model structure (`features`, `dropped`, `signs`, `n_fit`, `n_kept`, `l2` equal), and the model parameters within 1e-6. Reason: pooling the old and new draws needs the same decisions, and X5 shows them. X1' keeps the digest as a must-pass field (it passed). Chain: rerun from a new code snapshot; the 4 phase-1 files are kept (skipped), the checks run again, then phase 2 and the analysis. The 5 h cap counts from the first launch (10:07); the worker cap of 4.6 h restarts with the new chain, so the wall-time cap is checked by hand and reported.
