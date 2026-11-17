---
title: P14-18 and P14-19 word-setting follow-ups - pre-registration (addendum to P14-15)
type: experiment
task: P14-18, P14-19
updated: 2026-11-17
---

# P14-18 / P14-19: word-setting follow-ups of P14-15 (pre-registration)

Written and committed **before** any run of this item. Addendum to the P14-15 plan ([plan.md](../2026-11-17-p14-15-retune/plan.md), commit `fc8478c`; [results](../2026-11-17-p14-15-retune/results.md)). Gaps 44 and 45 of the [open-gap list](../../wiki/questions/open-gaps.md). CPU only (background class, 4 threads, one process at a time, RAM under 1.5 GB).

Same decision rule as P14-15: **no effect** = every primary metric changes by less than its 95 % CI half-width; **effect** = at least one primary metric changes by its half-width or more. Committed numbers are never overwritten. Each affected results page gets a dated note.

## Part 1: P14-18 (gap 44): M4 word-level rows with edit penalty 8
P14-15 (T2a): without the 16 M4 `val_eval` tune trials, the tune rule picks **lm 1.0, edit penalty 8, bonus 3** (paper point: edit 12). We rerun the M4 word-level evaluation with this setting. Everything else stays fixed (log-probs, frozen trust config, user model, seeds, code).

**Runs.**
- **A. M4-12 accuracy rows** (`experiments/2026-11-14-m4-12-decoder-retrain/run.py`, functions `load_items`, `word_quality`, the frames-route `StreamingTrustLayer` + harness replay of `stage_accuracy`): all 10 conditions, `dedicated_0` (`m4-12-fixed0`, L 0) first. The original decoder (`b2t25-trust` `Decoders`) is built with edit penalty 8; a fresh word-decode cache in our own folder (the M4-12 cache stores no setting key).
- **B. M4-01/02 accuracy rows** (`experiments/2026-11-13-m4-01-02-lookahead/run.py`, same functions): all 8 conditions.
- **C. P14-03 guard rows, T15** (`experiments/2026-11-16-p14-03-replay-validation/run.py`, `data_t15` + the `run_set` steps): `calibrate` on 722 `val_select` trials, `decide` on 701 `val_eval` trials, alpha 0.05 and 0.10, `decode_fn` = the same word decoder with edit penalty 8.
- **Reference runs (same code path, edit penalty 12):** every condition of A and B, and C. They must reproduce the committed numbers (M4-12 and M4-01/02 `results/accuracy.json`, P14-03 `results/results.json`; equal to the printed precision, counts exactly). For A and B the reference run reads the committed word-decode cache of that experiment read-only (a cache miss is decoded with edit 12 and counted). They also give the per-trial values for the CIs. If a reference run does not reproduce the committed numbers, we stop and report; no result of that condition is used.

**Primary metrics** (per condition / alpha):
- A and B: WER at T = 1 (`words_T1`), WER at the frozen T, sentence exact (frozen T), truth in n-best (frozen T), trust commit rate, trust wrong-commit rate, trust eWPM, always-commit wrong-commit rate and eWPM.
- C: held-out wrong-commit rate, commit rate, error among commits, eWPM.

**CI half-width** (of the committed value, n = 701 trials):
- rates of trials (sentence exact, truth in n-best, commit rate, wrong-commit rate): Wilson 95 % half-width of the committed rate; error among commits: Wilson with n = committed commits (if 0 commits: a change from 0 commits to any commit counts as a change of 1.0 against a half-width of the Wilson interval of 0 / 701 for the commit rate; i.e. the commit rate decides);
- WER (pooled ratio) and eWPM: half of the width of the 95 % percentile trial-bootstrap interval (2,000 resamples, seed 0) of the edit-12 per-trial values from the reference run.

**Decision.** No effect on all primary metrics: gap 44 closes with "no effect" notes on the M4-12, M4-01/02 and P14-03 results pages. Effect: dated correction notes with the new numbers on the affected pages, and a new gap for the downstream M4-x / M2-19 / P15-05..07 / P5-02 rows.

## Part 2: P14-19 (gap 45): published gate, guard-off tables, forward chain, downstream
P14-15 rebuilt only the guard-on "ours" tables of the 35 re-splits whose fit-A tune changed the setting (`p14-15-retune/results/tune.json`, T1). Here:

**Step 1. Rebuild** (code path of P14-15 `stage_rebuild` and R4 `split-tables` `b2t_tables`: `pipe.fit(A, A)`, frame T snapped to 0.02, `M13.item_table`; decoder `b2t25-trust` `Decoders` with the split's own fit-A setting; reuse / cal / test tables). For each of the 35 changed splits:
- `published-g1` (guard on, published gate, margin 2.0) — the "B2T published" re-split rows;
- `ours-g0` and `published-g0` (guard off);
- for the 8 changed splits with r < 50: `published-m0`, `-m0.5`, `-m1`, `-m4` (R4 bonus sensitivity);
- for the 8 changed splits with r < 50: the trust v5 split rows (`trust-v5-candidate/run_splits.py`: `fit_sweep` + `evaluate_split`, both decoders).
- **Forward chain:** the R4 forward-chain prefix 0 (fit = day 1 only, 30 trials), 4 tables (ours / published x guard on / off), with lm 1.0, edit 8, bonus 3 (P14-15 post hoc). Prefixes 1..12 keep the paper point (P14-15) and keep their tables.
- **Check before use:** the code path with the paper setting reproduces the committed `published-g1` table of split 0 (first 100 test items, all arrays, T, plug-in lambda) and the committed forward-chain prefix-0 "ours" guard-on table (all arrays). If a check fails, we stop and report.
- Grid decodes of P14-15 (`derived/p14-15-retune/grid.pkl`) are raw-stream decodes (T = 1). The tables need decodes at each split's frame temperature, so they are not reused for tables; they are only the source of the tune choices (already done in P14-15).

**Step 2. Primary analysis** (P14-15 step 2, R3 `split_policies`, 8 policies x 5 metrics: mean wrong-commit, mean commit rate, mean eWPM, pooled error among commits, share of splits with wrong-commit > alpha):
- `b2t-published` guard on: R = 50 and R = 200;
- `b2t-ours` guard off and `b2t-published` guard off: R = 50 and R = 200;
- the changed splits use the rebuilt tables, all others the committed ones. CI half-widths exactly as P14-15 (MC: 1.96 x SD / sqrt(R) of the original per-split values; Wilson for the share and the pooled error among commits).
- **Forward chain:** rerun of the R4 `forward-chain` analysis (all variants, prefix 0 replaced). Primary metrics: per condition (4) and variant (V1, V2, V3, V4) and main rule (plug-in, CRC max, LTT max, joint LTT b0.10 / b0.20): pooled wrong-commit (half-width of its exact CP95 interval), share of days above alpha (half-width of its CP95), pooled commit rate (Wilson, n = test trials of the variant), mean day eWPM (1.96 x SD over days of the original per-day eWPM / sqrt(days)).

**Step 3. Downstream tables.** Each downstream analysis that reads the split tables is rerun with its own code; the loader is redirected so that the changed splits read the rebuilt tables (guard-on "ours": the P14-15 tables, read only) and the forward-chain prefix 0 reads the rebuilt prefix. Outputs go to our local folder only. Analyses: R4 population-risk, per-day, reuse, joint-LTT, no-guard (Tab. 2 rows), cleanup, bonus-sensitivity (repeated part); M3-01/02 repeated-split arms (`abl.split_arm_outcomes`); trust v5 split summary (`summarise_splits` with the 8 rebuilt rows); A2 per-session risk (re-split and forward-chain parts).
- **Not affected (no rerun):** M2-18 T15 and every fixed-split row (splits A and B: their fit-A tune keeps the paper point, P14-15 sanity check (b)); full-fit rows (the fit set holds the 400 tune trials and no test trial).
- **Rule for step 3:** we compare every numeric value of each committed result JSON with the rerun. A value with a CI in the same record (a sibling `*_cp95` / `*_ci` / `ci` pair, or a reported MC SE x 1.96) is a primary metric: effect if the change is at least the half-width of that committed CI. Means over splits without a reported CI: half-width = 1.96 x SD / sqrt(R) of the committed per-split values where the per-split values are in the result files; otherwise the value is "no CI": we report its largest absolute and relative change, and it does not enter the decision. p-values and other test statistics are reported, not decided on.

**Decision.** No effect in steps 2 and 3: gap 45 closes with "no effect" notes on the R3 / R4 / M3-01/02 / trust v5 / A2 results pages. Effect: dated correction notes on the affected results pages with the recomputed numbers, a clearly marked correction note in `papers/paper1/` for the paper track (no paper text changed), and a new gap for any analysis not covered here.

## Order and time limits
One detached queue, background class, 4 threads: (1) P14-19 rebuild + checks (about 2 h), (2) forward-chain prefix 0, (3) P14-18 runs A (`dedicated_0` first), C, then the rest of A and B (reference + edit 8 per condition), (4) analyses. Heavy decoding should end before 09:00 (another CPU queue starts at about 09:15). If a part does not finish, its rows are reported as not run, and a new gap registers them.

## Outputs
- Repo: `experiments/2026-11-17-p14-18-19-followups/` (`plan.md`, `run.py`, `results.md`, `results/*.json` with counts, rates and metrics only; no text, no trial ids).
- Local only: `C:\Users\zhang\bci-data\derived\p14-18-19\` (rebuilt tables, decode caches, per-trial values, downstream reruns, logs).
