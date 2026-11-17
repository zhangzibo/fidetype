---
title: P14-15 word-decoder settings re-tuned without evaluation trials - pre-registration
type: experiment
task: P14-15
updated: 2026-11-17
---

# P14-15: re-tune the B2T word-decoder settings without evaluation trials (pre-registration)

Written and committed **before** any re-tune run. Gap 35 of the [open-gap list](../../wiki/questions/open-gaps.md), issue D of the [T15 split audit](../../wiki/questions/t15-split-audit.md). CPU only.

## Why
Our phoneme-beam word decoder for B2T '25 (T15) has 3 settings: `lm_weight`, `edit_penalty`, `word_bonus` (grid of 12: 0.5 / 1.0 x 4 / 8 / 12 x 3 / 6). [b2t25-trust](../2026-11-10-b2t25-trust/run.py) `stage_tune` chose them once (lm 1.0, edit 12, bonus 3) on 400 fixed track `cal` trials (rng seed 0, raw streams; criterion: lowest pooled WER, then highest truth-in-10-best). Two problems:

1. The Paper 1 re-splits (R3: 50 splits, R4: 200 splits, the first 50 equal R3) permute all 1,628 trials per day into fit-A (1/4), clean calibration (1/4) and test (1/2, 818). 179-224 of the 400 tune trials land in each test set. The "B2T ours" rows of these analyses (and the M2-18, M3-01/02, trust v5 and A2 re-split tables built on the same split tables) use the fixed settings.
2. 16 of the 400 tune trials are M4 `val_eval` trials and 16 are `val_select` trials (HDF5 match of the audit). Every M4-x word-level result uses the same settings.

Already checked (no new run): the fixed splits A and B (R3 [b2t-retune](../2026-11-12-paper1-r3-analyses/b2t-retune/results.md)) select the paper point on fit-A. The R1 clean-drift pooled re-splits fit on the fit-A of these fixed splits, so their decoder is the fit-A decoder too.

## Method (reuses the original code)
- **Grid decodes (stage `grid`).** The tune uses raw streams (no temperature). So the word n-best of one trial at one grid point does not depend on the split. We decode all 1,628 main-vocabulary trials (`ctx.fit + ctx.test` of R1 `common.b2t_ctx`) once at each of the 12 grid points with the original classes (`b2t25-trust` `Decoders`, `make_wdec`, `phonemes`; `CONFIG["word_decoder_fixed"]`). Per trial and grid point we keep: word edit distance of the top-1 to the truth words, number of truth words, truth in n-best. Local file only: `C:\Users\zhang\bci-data\derived\p14-15-retune\` (the top-1 texts stay there; nothing with text goes into the repo).
- **Tune (stage `tune`).** For a trial set S, the tune result per grid point = pooled WER over S (sum of edits / sum of truth words, = `pooled`), truth-in-n-best rate; choice = `min(rows, key=(wer, -truth_in_nbest))` in the original grid order (same tie rule as `stage_tune`).
- **Sanity checks (must pass before any result is read):** (a) S = the 400 original tune trials reproduces all 12 rows of `b2t25-trust/results/tune.json` (WER and truth-in-n-best within 1e-12) and the choice (1.0, 12, 3); (b) S = fit-A of the fixed splits A and B reproduces the R3 b2t-retune rows (`retune.json`). If a check fails, we stop and report; no result is used.
- **Tune sets:**
  - **T1:** fit-A of each of the 200 R4 re-splits (`C:\Users\zhang\bci-data\cache\paper1-r4\splits-b2t-200.json`; r < 50 = the R3 splits). fit-A is the only part of a re-split that the pipeline fits on; it never contains a test or clean-calibration trial of the same split (checked per split).
  - **T2a:** the 400 tune trials minus the 16 M4 `val_eval` trials (384).
  - **T2b:** the 400 tune trials minus the 16 `val_eval` and the 16 `val_select` trials (368; roadmap wording).
  The M4 part of each tune trial comes from the audit match table (`derived\t15-split-audit\match.json`, strict match).

## Decision rule (frozen)
**Step 1: settings.** For each tune set, record the chosen point and whether it equals (1.0, 12, 3).
- If the choice equals the paper point on all 200 re-splits (T1) and on T2a and T2b: **no effect**. The item closes; the audit page and the results pages get a "no effect" line.

**Step 2 (only re-splits where T1 changes the choice): recompute the affected rows.** For each such split we rebuild the "b2t-ours" guard-on item tables (fit-A, clean cal, test) with the split's own chosen setting, with the same table builder (R3 `repeated-splits` `b2t_tables` code path: `pipe.fit(A, A)`, frame temperature snapped to 0.02, `M13.item_table`). Splits whose choice did not change keep their committed tables (same decoder, deterministic code: identical tables). Then we rerun the R3 aggregation code (`split_policies`, `aggregate`) for R = 50 (r < 50) and R = 200.
- **Primary metrics:** for each of the 8 policies of the R3 tables (plug-in, CRC / LTT pure and max rule on clean calibration, CRC / LTT on reused calibration): mean test wrong-commit, mean commit rate, mean eWPM, pooled error among commits, share of splits with wrong-commit > alpha (0.05). For R = 50 and R = 200 separately (80 metrics).
- **CI half-width** of a mean metric = 1.96 x SD over splits / sqrt(R) of the **original** per-split values (the Monte-Carlo SE that R3 reports). For a share = the half-width of the Wilson 95 % interval of the original share with R splits. For the pooled error among commits = the half-width of the Wilson 95 % interval of the original pooled rate over all commits of all splits.
- **No effect:** every primary metric changes by less than its CI half-width.
- **Effect:** at least one primary metric changes by its CI half-width or more. Then: (1) the committed R3 / R4 tables keep their numbers and get a dated correction note with the recomputed numbers (`experiments/2026-11-12-paper1-r3-analyses/repeated-splits/results.md`, `experiments/2026-11-12-paper1-r4-analyses/split-tables/results.md` and the result pages of the affected R4 analyses, M2-18 / M3-01/02 re-split pages); (2) a note in the paper folder (`papers/paper1/`), clearly marked as a correction note, informs the paper track; no paper text is changed; (3) the downstream analyses that read the split tables (R4 population-risk, per-day, reuse, joint-LTT, no-guard, cleanup; M2-18, M3-01/02, trust v5, A2) are a new gap, unless the change touches no split they use.

**Step 3 (only if T2a or T2b changes the choice):** the M4-x word-level results used the paper point. We do not rerun them here. The M4 results pages and the audit page get a dated note with the new choice, its tune WER and the paper point's tune WER on the same set, and a new gap registers the M4 reruns. If T2a and T2b keep the paper point: no effect on M4 rows.

Also reported (not part of the decision): the rank of the paper point and the WER gap to the chosen point per split; the number of distinct choices.

## Outputs
- Repo: `experiments/2026-11-17-p14-15-retune/` (`plan.md`, `run.py`, `results.md`, `results/*.json` with counts, WER values, choices and metrics only).
- Local only: `C:\Users\zhang\bci-data\derived\p14-15-retune\` (grid decodes, any rebuilt item tables, logs).
- Run: `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-17-p14-15-retune/run.py --stage <grid|tune|rebuild|analyze>`. RAM under 1.5 GB. If step 2 needs many new decodes, we first estimate the time and run it detached.
