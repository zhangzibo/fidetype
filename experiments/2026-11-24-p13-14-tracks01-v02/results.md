---
title: P13-14 rescore of the tracks-v0.1 benchmark cards under safe-WPM v0.2 - results
type: experiment
task: P13-14
updated: 2026-11-24
---

# P13-14: the tracks-v0.1 cards get a safe-WPM v0.2 block (results)

Gap 204. CPU only. No GPU, no new decoding, no new derived output (the tool reads local files and writes only the committed cards).

## Result

All **21 of 21** tracks-v0.1 cards now have a `safe_wpm_v02` block (the adopted headline, with the `aac-gaze-v1` reading cost) next to their `safe_wpm` block. Every `safe_wpm` (v0.1) block keeps its value and its label. **No card is left without a v0.2 value.** No status changes (certified stays certified, above-alpha stays above-alpha, vacuous stays vacuous, not-certified stays not-certified).

| Card | Safe WPM v0.1 (unchanged) | Safe WPM v0.2 (new headline) | Reading time (min) |
|---|---|---|---|
| b2t25-t15-copytask / published + CRC | 13.42 [11.72, 15.08] certified | **12.27 [10.77, 13.69]** certified | 16.28 |
| b2t25-t15-copytask / published + LTT | 12.24 [10.98, 13.45] certified | **11.28 [10.17, 12.32]** certified | 14.47 |
| b2t25-t15-copytask / ours + CRC | 4.90 [4.10, 5.62] above alpha | **4.70 [3.95, 5.38]** above alpha | 7.70 |
| b2t25-t15-copytask / ours + LTT | 4.05 [3.22, 4.77] certified | **3.91 [3.13, 4.59]** certified | 6.06 |
| spanishbcbl-meg-async / CRC | 0.03 [0.00, 0.17] certified | 0.03 [0.00, 0.17] certified | 0.51 |
| spanishbcbl-meg-async / LTT | 0.03 [0.00, 0.17] certified | 0.03 [0.00, 0.16] certified | 0.55 |
| toronto-semg-composed / session-calibrated + CRC | 0.55 [0.28, 0.86] certified | 0.55 [0.28, 0.86] certified | 0.86 |
| toronto-semg-composed / cross-session + CRC | 0.25 [0.06, 0.46] certified | 0.25 [0.06, 0.46] certified | 0.42 |
| toronto-semg-composed / cross-subject + CRC | 0.00 vacuous | 0.00 vacuous | 0.00 |
| 3 plug-in trust cards with per-trial data (B2T ours, B2T published, MEG) | n/a (no certified bound) | n/a (no certified bound) | 7.26, 15.44, 0.00 |
| 9 cards without a bound and without per-trial data (3 always-commit B2T / MEG, 3 Toronto commit, 3 Toronto plug-in trust) | n/a (no certified bound) | n/a (no certified bound) | not computed |

Headline changes (the leaderboard headline column, old -> new): the column showed "v0.1 only (not rescored)" for all 21 cards. It now shows the v0.2 values above. Measured against the v0.1 numbers, the largest change is the published Card et al. decoder + CRC: 13.42 -> 12.27 (-1.15). The order of the entries inside each track does not change.

> **Our take:** the drop is the reading time of the adopted v0.2 (0.5 s + 0.3 s per committed word). It is largest where the system commits most words (the published decoder commits about half of all trials). Our own B2T word decoder + LTT goes from 4.05 to 3.91. Both values were already below the track no-BCI reference 4.08, so no claim changes.

## Method

Tool: [`tools/benchmark/add_safe_wpm_v02_tracks01.py`](../../tools/benchmark/add_safe_wpm_v02_tracks01.py). It follows the same rule as `tools/benchmark/add_safe_wpm_v02.py` (the 36 tracks-v0.2 cards of commit `38f1e50`): score the card again, check that the fresh v0.1 block is identical to the stored one, then add `safe_wpm_v02` + `safe_wpm_headline` and the v0.2 metric in `rerun.scorer.metrics`. It reuses that tool's `with_v02` (same key order). The difference: the tracks-v0.1 cards have no submission folder, so the hub `rescore` path does not apply. The tool rebuilds the per-trial arrays that the original build steps used:

| Cards | Per-trial source (read only) | Original build step |
|---|---|---|
| B2T '25 copy task, CRC / LTT / plug-in (6) | committed items files `experiments/2026-11-11-m2-13-conformal/results/items-b2t-*.json` (threshold refit, commit rate checked against the card); local truth `b2t25-truth.jsonl`; measured speech durations from the local `t15_copyTask.pkl` | `experiments/2026-11-16-p14-05-safe-wpm/run.py tracks` |
| SpanishBCBL MEG async, CRC / LTT / plug-in (3) | committed `experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json`; local `meg-truth.jsonl`; track rate model | the same |
| Toronto sEMG composed, CRC (3) | local per-trial CRC decisions `derived/p6-01-tracks/toronto-<cond>-crc-trials.jsonl`; local `emg-truth.jsonl` | `experiments/2026-11-16-p6-01-tracks/run.py` |
| No bound, no per-trial numbers (9) | none needed | the v0.1 block holds only "not-certified"; the v0.2 block states the same status, with a `basis` line |

Checks:
- For each of the 12 per-trial cards, the fresh v0.1 block (B = 2000, seed 0) is identical to the stored block, apart from the `note` / `basis` lines that later steps added (these are carried over to the v0.2 block).
- Each card file is in the scorer's JSON form before and after the change.
- The leaderboard (`benchmark/site/`) is regenerated. The dated column note now says that the tracks-v0.1 entries have their v0.2 value since 2026-11-24.

Finding (local file, no effect on any number): in the P6-01 per-trial Toronto files the field `n_words` holds the correct flag (0 or 1), not the word count (a variable mix-up in the file writer). The stored v0.1 block was computed before the file was written, from the right counts. The tool takes word and character counts from the truth file, and the fresh v0.1 block matches the stored one.

Rerun: `C:\venvs\fidetype-rocm\Scripts\python.exe -I tools/benchmark/add_safe_wpm_v02_tracks01.py` (dry run; `--write` updates the cards), then `python -m fidetype.benchmark leaderboard --results benchmark/results/v0.1 benchmark/results/v0.2 --out benchmark/site`.

## Limits

The v0.2 values use the same decisions, timing and CI unit as the v0.1 values. They inherit every limit of the v0.1 values: rate-model timing for MEG and Toronto, conditional CIs (one calibration), and the cards' own controls. The new blocks are trial-bootstrap CIs, not the calibration-draw interval of docs/safe-wpm.md section 6b.

## Gap status

Gap 204 (P13-14): done-when met. Each tracks-v0.1 card has a v0.2 score next to its v0.1 score; the v0.1 numbers keep their values and labels. No card needs a "cannot rebuild" reason.
