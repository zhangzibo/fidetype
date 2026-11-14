---
title: P5-07 trust v5 candidate recipe - results
type: experiment
task: P5-07
updated: 2026-11-14
---

# P5-07: trust v5 candidate recipe (results)

The plan ([plan.md](plan.md), commit `6283109`) was committed before the first run. CPU only, no retraining, cached decoder outputs (new decodes = only the fit-time control copies). Full tables: [results/tables.md](results/tables.md); criteria check: [results/criteria.json](results/criteria.json) (both made by [tables.py](tables.py)). Numbers: `results/*.json` (aggregates only: no text, no signals, no participant ids). Logs: `results/run-*.log`.

Code: `fidetype.trust.recipe_v5` (`TRUST_V5_CANDIDATE`, `V5Options`, `V5Pipeline`, `fit_trust_v5`, `freeze_v5`), `StreamingConfig(declaration_check="offer-only")`. Tests: `tests/test_trust_v5_recipe.py` (13, synthetic). `PAPER1_V4_RECIPE` and all existing config ids are unchanged.

Run (repo root; each under `python -m fidetype.utils.isolation run --class background --threads 1 --`, at most 4 at a time):
`run_b2t.py --which ours|published --stage fixed|small`, `run_emg.py`, `run_t12.py --part val|pool`, `run_meg.py`, `run_sim.py`, `run_splits.py --cond ... [--worker w --nworkers 2]`, then `run_splits.py --stage summary` and `tables.py`.

## Checks
- **v4 reproduces M3-02 / Paper 1 exactly** on all four B2T fixed splits and all three sEMG conditions (asserted: same wrong commits and commits), and on T12 (dry run 22 commits, 11 wrong, uniform 335/400, as M2-18; pool 1 commit, as M3-28) and MEG (0 commits). So the sweep engine (one grid sweep with 0.8 added, selection on the v4 values) equals the v4 grid fit.
- **Library = experiment.** `fit_trust_v5` (the library function) gives the same final `commit_p`, the same policy and the same test commits as arm "v5" on B2T split A (both decoders) and all 6 simulator conditions. The frozen v5 configuration (`freeze_v5`) through `StreamingTrustLayer` equals the batch commits on 816/816 (B2T, hypothesis route) and 300/300 per simulator condition (frames route). v5 config ids differ from the v4-recipe ids of the same numbers (for example B2T ours split A `tcfg-ea9e216b75f54cd4`).

## 1. Main result: v4 vs v5 on the fixed splits

Wrong commits / commits · eWPM on the test set; "ctl" = the worst signal-destroying test-time control (commits / n). **Bold** = Holm-corrected exact McNemar p < 0.05 vs v4.

| set (n test) | v4 | v5 | v4 ctl | v5 ctl | never commit eWPM |
|---|---|---|---|---|---|
| B2T ours A (816) | 20/82 · 11.48 | 20/82 · 11.48 | 0/300 | 0/300 | 11.42 |
| B2T ours B (816) | 42/157 · 11.54 | 42/157 · 11.54 | 0/300 | 0/300 | 11.41 |
| B2T published A (816) | 24/329 · 18.65 | 24/329 · 18.65 | 0/300 | 0/300 | 18.11 |
| B2T published B (816) | 25/339 · 18.68 | 25/339 · 18.68 | 0/300 | 0/300 | 18.11 |
| sEMG calib (551) | 2/21 · 7.98 | 2/20 · 7.98 | 0/200 | 0/200 | 7.96 |
| sEMG xsession (551) | 2/10 · 4.68 | 1/3 · 4.68 | 0/200 | 0/200 | 4.67 |
| sEMG xsubject (551) | 0/0 · 4.08 | 0/0 · 4.08 | 0/200 | 0/200 | 4.08 |
| T12 validation dry run (400) | 11/22 · 7.09 | 11/22 · 7.09 | **335/400 uniform**, 334/400 zero stand-in | 3/400 frame-shuffled; uniform and zero 0/400 | 7.08 |
| T12 trust pool (400) | 0/1 · 7.14 | 0/1 · 7.14 | 0/400 | 0/400 | 7.13 |
| MEG, 5 runs (637 each) | 0/0 · 2.95-3.20 | 0/0 · same | 0/637 | 0/637 | same |
| sim median / 1.0 (300) | 14/211 · 24.79 | 12/200 · 24.73 | 4/100 fs | **2/100** fs | 23.67 |
| sim median / 0.5 | 14/224 · 24.96 | 6/181 · 24.78 | 3/100 | 1/100 | 23.81 |
| sim median / 2.0 | 5/209 · 25.14 | 4/92 · 24.48 | 1/100 | 0/100 | 23.99 |
| sim worst / 1.0 | 8/133 · 23.69 | 3/72 · 23.38 | 10/100 | 0/100 | 23.03 |
| sim worst / 0.5 | 4/121 · 23.45 | 11/80 · 23.17 | 6/100 | 0/100 | 22.85 |
| sim worst / 2.0 | 13/131 · 23.49 | 13/74 · 23.19 | 16/100 | 0/100 | 22.98 |

Empty COMMITs: v4 655 (T12 dry run controls), v5 **0** on every test and control set. No v5 vs v4 difference is significant after Holm on any set.

## 2. What each change does (ablations)

All 10 arms on all sets: [tables.md](results/tables.md) section 1-2. Summary:

| change | effect on real data | effect on controls | verdict |
|---|---|---|---|
| (a) gate B | Removes commits at guard risk 1.0: sEMG xsession 10 → 3 commits (wrong 2 → 1), sEMG calib 21 → 20; 0 changes on B2T (5 / 14 blockable test items were not committed anyway), T12, MEG. eWPM change ≤ 0.001 | **The change that fixes T12**: uniform 335 → 0, zero stand-in 334 → 0, frame-shuffled 6 → 3; 655 → 0 empty commits | keep |
| (b) control-aware grid fit | No change on B2T, sEMG, MEG, T12 when the gate is on (the v4 grid point already passes the controls once empty / risk-1.0 texts are gated). **Without the gate** (v4 + b), T12 dry run moves to `commit_max_risk` 0.5: test 11/22 → **0/9** wrong (Holm p < 0.05), uniform 335 → 0 | **Simulator: frame-shuffled commits 1-16 % → 0-2 %** (6 conditions: 40 → 3 of 600). The grid moves away from `commit_max_risk` 1.0 in 4 of 6 conditions | keep (only change that acts on W3) |
| (c) 0.8 for 1.0 | Can make things **worse**: sEMG calib v4 + c 13/74 wrong (Holm p < 0.05 vs 2/21) because the fit then picks a lower `commit_p`; v5 + c 5/49. sEMG xsession 0 commits | sEMG calib 1/200 frame-shuffled | **drop** |
| (d) no-signal floor | With the gate on: no effect anywhere (floor below the other two parts, or −inf). Without the gate: T12 dry run floor = +inf (the uniform reference has empty texts at p_top1 1.0), so v4 + d **never commits** (eWPM 7.08 vs 7.09) | Without the gate, T12 uniform 335 → 0 | redundant with (a) on text data; keep only as an option |
| (e) declaration offer-only | — (mismatch only) | — | keep (section 4) |

Ablations of v5: v5 − a (no gate) = v4 + b plus floor; on T12 its test result is 0/9, on all other sets equal to v5. v5 − b = v4 + a on every set (so (b) adds safety only on the simulator). v5 − d = v5 on every set.

## 3. Repeated splits and 240-trial fit sets

Every split refitted (sweep + all arms). Share of splits with test wrong-commit > α (CP95), mean test wrong-commit, mean eWPM; "down / up" = splits where v5 has fewer / more wrong commits than v4.

| condition (R) | v4: share > α · mean wc · eWPM | v5: share > α · mean wc · eWPM | v5 down / up | v4 + c: share > α · mean wc |
|---|---|---|---|---|
| B2T ours (50) | 0.080 [0.022, 0.192] · 0.0304 · 11.07 | 0.080 · 0.0300 · 11.06 | 9 / 0 | 0.080 · 0.0300 |
| B2T published (50) | 0.020 [0.001, 0.106] · 0.0307 · 18.49 | 0.020 · 0.0307 · 18.49 | 0 / 0 | 0.020 · 0.0312 |
| sEMG calib (50) | 0 · 0.0106 · 8.00 | 0 · 0.0089 · 8.00 | 15 / 0 | **0.020** · 0.0183 (34 up) |
| sEMG xsession (50) | 0 · 0.0057 · 4.68 | 0 · 0.0012 · 4.68 | 28 / 0 | 0 · 0 |
| sEMG xsubject (50) | 0 · 0 · 4.07 | 0 · 0 · 4.07 | 0 / 0 | 0 · 0 |

- v5 is never worse than v4 on any of the 250 re-splits; it has fewer wrong commits on 52 of them, all from gate B (v4 + a alone: 8 / 0 / 6 / 28 / 0 down). 0 empty commits in all arms.
- `commit_max_risk` 1.0 is still chosen in 28 % (ours), 26 % (published), 98 % (sEMG calib) and 66 % (sEMG xsession) of the v5 fits; with the gate this is safe (see section 5).
- Without the gate, the control-aware fit (v4 + b) moves B2T ours away from 1.0 in every split, and the share > α rises to 0.100 (2 up, 13 down): stricter guard limits change the LTT input, not only the controls.
- (c) again moves the fit to a lower `commit_p`: sEMG calib 34 splits up, 1 split > α.

**240-trial fit sets** (B2T split A, 10 random 240-trial fit-A draws, calibration and test unchanged): v5 = v4 within 3 commits per decoder over all draws (ours 364/1504 vs 365/1506 wrong / commits; published 243/3338 vs 246/3357). Median relative eWPM change 0.000; no draw below the never-commit eWPM. T12 (240 fit trials): v5 = v4 on the test sets (dry run 11/22, pool 0/1). No collapse.

## 4. Declaration check (e)

A producer that decodes the raw stream (temperature 1.0) sends n-best lists to the frozen v5 configuration (hypothesis route):

| set | warn (no change) | abstain | **offer-only** |
|---|---|---|---|
| B2T ours A | 228 commits, 65 wrong (0.080 > α) · 11.55 | 0 commits · 3.55 | 0 commits · **11.34** |
| B2T published A | 419 commits, 42 wrong · 18.81 | 0 · 3.55 | 0 · **18.11** |
| simulator (6 conditions) | 0-199 commits | 0 · 0.00 (default user loses the sentence on ABSTAIN) | 0 · 0.0-23.68 (= the offer-only eWPM of the mismatched n-best) |

Offer-only gives 0 commits on every mismatched stream (816/816 and 300/300 decisions are OFFER) and keeps eWPM near the never-commit level of a matched configuration (B2T ours 11.34 vs 11.42; published 18.11 vs 18.11). With a matched declaration the check changes 0 decisions (B2T stream 816/816 = batch, 0 mismatches).

## 5. Stability of the grid choice (200 bootstrap resamples of the grid-fit set)

| set | v4 rule: share `commit_max_risk` 1.0 | v4: distinct winners (top share) | v5 rule: share 1.0 | v5: distinct winners (top share) |
|---|---|---|---|---|
| B2T ours A / B | 0.04 / 0.20 | 8 (0.37) / 8 (0.28) | same | same |
| B2T published A / B | 0.18 / 0.30 | 4 (0.79) / 4 (0.69) | same | same |
| sEMG calib / xsession | 1.00 / 0.97 | 3 (0.58) / 2 (0.97) | 1.00 / 0.97 | 1 (1.00) / 2 (0.97) |
| T12 dry run / pool | 0.98 / 0.24 | 2 (0.98) / 4 (0.60) | same | same |
| simulator (6) | 0-1.00 (mean 0.54) | 4-10 | 0-0.01 | 1-6 |

The v5 rule does not make the B2T, T12 or MEG grid choice more stable: with the gate on, the controls do not bind there, so the same point wins. `commit_max_risk` 1.0 still wins in 98 % of T12 dry-run resamples, but with the gate it no longer commits on no-signal input. On the simulator, the v5 rule removes 1.0 completely and halves the number of distinct winners.

## 6. Pre-declared criteria

From [results/criteria.json](results/criteria.json):

| id | result | detail |
|---|---|---|
| S1 not less safe on real data | **pass** | no real fixed split has v5 significantly worse (largest change: −0.0018, sEMG xsession 2 → 1 wrong of 551); repeated splits: v5 share > α = v4 share on all 5 conditions |
| S2 0 empty commits | **pass** | 0 on every test and control set, every split (v4: 655 on the T12 dry-run controls) |
| S3 controls ≤ 1 % | **fail (1 of 65 control sets)** | sim median / 1.0 frame-shuffled: v5 2/100 (v4 4/100). Every real-data control set passes; the other 5 simulator conditions pass (0-1/100) |
| S4 no collapse on 240-trial fits | **pass** | T12 v5 eWPM ≥ never-commit; B2T 240 draws: median change 0.000, 0 draws below never-commit |
| S5 cost (reported) | — | real fixed splits: 0 to −0.06 % eWPM (sEMG calib −0.0001, xsession −0.0003 relative); repeated splits ≤ 0.06 %; simulator −0.06 to −0.66 eWPM (−0.2 % to −2.6 %) |

## 7. Recommendation

**By the pre-declared rule, v5 does not become the default yet**: S3 fails on one synthetic control set by one commit (2/100 frame-shuffled at a 1 % limit; v4 had 4/100). S1, S2 and S4 pass, and S5 shows no real-data cost.

Per change (rule of plan section 7):
- **(a) gate B: keep.** It is the change that removes the T12 failure (uniform 335 → 0, empty 655 → 0) and it lowers wrong commits on 52 of 250 re-splits, at no measurable eWPM cost.
- **(b) control-aware grid fit: keep.** It is the only change that acts on frame-shuffled simulator input (40 → 3 of 600) and costs nothing on real fixed splits. Its fit-time limit (≤ 1 % of at most 200 copies) is not tight enough for a test-time 1 % limit on 100 streams; that is the S3 miss.
- **(c) 0.8 instead of 1.0: drop.** It does not help any control and it can raise wrong commits (sEMG calib fixed split 2/21 → 13/74, Holm p < 0.05; 34 of 50 re-splits up).
- **(d) no-signal floor: keep as an option (zero cost), but it is redundant with (a)** on all our text data: with the gate on it never binds; without the gate it blocks all commits on T12 (floor +inf).
- **(e) declaration "offer-only": keep.** 0 commits on mismatched hypotheses, eWPM 11.34 vs 3.55 for "abstain" on B2T.

Recommendation for new configurations:
1. Use the v5 candidate (`V5Options()`: a + b + d + e, c off) as the **recommended opt-in recipe now**. On all real data it equals v4 or is safer, never slower by more than 0.06 %.
2. Keep v4 as the library default until one pre-declared follow-up passes: the same evaluation with a stricter fit-time control limit (for example ≤ 0.5 %, or 400 copies per kind) on the simulator, and a frame-shuffled test-time control with more streams. If that passes S3, make v5 the default and make FEP-0001 rule 9 (no empty COMMIT) a MUST.
3. Do not use (c).

## Deviations from the plan
- None in data, arms or metrics. The evaluation of (e) used the frozen **v5** configuration (as planned); the "abstain" row of M3-02 used v4 and gives the same 0 commits / 3.55 eWPM.
- T12 (both parts) is reported as exploratory, as planned; the pool test set had been used once by M3-28.

## Limitations
- On B2T, T12 and the simulator the test-time zero stand-in and uniform controls are the same kind as the fit-time copies (different streams). The out-of-kind checks (real zero input on sEMG and MEG, shuffled MEG) had 0 commits for v4 too, so they cannot show a v5 gain.
- The real-data sets rarely trigger the failures v5 targets: only the T12 dry run (W1) and the simulator (W3). The ablation verdicts rest on these two.
- Simulator streams have no temporal structure inside a key, and the LM is in-domain, so frame-shuffled simulator streams are a hard, partly artificial control.
- Fixed-split McNemar tests are conditional on one fitted pipeline per split. Repeated splits share trials (descriptive).
- Another agent's uncommitted, value-neutral change (edit-distance cache bound in `trust/guard.py`, `trust/_align.py`) was in the working tree; the exact v4 reproduction shows no effect.
