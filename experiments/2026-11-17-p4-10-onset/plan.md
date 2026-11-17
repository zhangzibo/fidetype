---
title: P4-10 live key-onset detector for EMG - pre-registration
type: experiment
task: P4-10
updated: 2026-11-17
---

# P4-10: live key-onset detector on KT-sEMG (pre-registration)

Written and committed **before** any detector touches a test run of track `kt-semg`. Detector development uses train and cal runs only. Code: `src/fidetype/live/onset.py` (detectors, matching), [run.py](run.py) (this evaluation).

## Why
`fidetype live` with `markers` timing needs a `keypress` marker at each key onset. In the KT-sEMG replay the markers come from the key log (oracle timing). A real board gives no markers, so boards fall back to `fixed` timing (P14-04). Gap 16 of the [open-gap list](../../wiki/questions/open-gaps.md).

## Data
KT-sEMG v1.1 (copyright 2021 Nokia, CC BY 4.0), 32 ch, 2000 Hz, raw at `C:/Users/zhang/bci-data/raw/kt-semg/` (read only). Run split = benchmark track `kt-semg` (tracks v0.2, `fidetype.benchmark.tracks`):

| Role | Runs | Use |
|---|---|---|
| Detector training (learned detector only) | train runs `run1`, `run2`, `run3`, `run4`, `run8`, `run10` | fit |
| Detector tuning | cal run `run21` | threshold and lag for both detectors |
| Guard re-calibration for `detect` timing | the 6 guard runs of the P14-04 `kt-semg-lda` guard (`run14`, `run15`, `run16`, `run19`, `run22`, `run23`) | E2E only |
| **Test** | test runs `run24` … `run29` (6 runs) | all reported numbers |

Truth onsets: every key press of the key log inside the recording (`fidetype.live.build.kt_run_events`: the adapter's UTC-offset rule, margin 0.15 s), not only the keys of typing bursts.

## Detectors (both causal, numpy only)
Common front end: first difference per channel (removes DC and drift), mean square per 5 ms block (10 samples), log energy over the last 20 ms (4 blocks). Frame rate 200 Hz.

- **D-env (baseline, unsupervised):** score = mean over channels of the log energy, minus a baseline. Baseline and scale: exponential means (time constant 2 s) updated only on frames below the threshold (and after 0.5 s above it; first 1 s: baseline only). Onset when the z-score crosses `theta` upward; refractory 60 ms; reported time = crossing time + `lag`.
- **D-lin (primary, learned):** 10 ms steps (2 blocks averaged), the last 20 steps (200 ms) of 32 channels = 640 features, causal standardisation (running mean and variance with forgetting, statistics of past chunks only). Binary shrinkage LDA (shrinkage 0.1): positive when a key press lies within ±10 ms of `t - 50 ms` (the detector looks 50 ms past the onset; the key window of the decoder needs `post_s` = 50 ms after the onset anyway). Negatives subsampled 1 in 4 for the fit. Onset at a local maximum of the score above `theta` (confirmed 10 ms later), refractory 60 ms; time = `t - 50 ms + lag`.
- Tuning rule (both, on `run21` only): `theta` = the grid value with the highest F1 at ±50 ms (grid: D-lin 41 quantiles of its score on `run21`, 0.50 … 0.999; D-env 41 values of `theta` from 0.5 to 8.0); then `lag` = minus the median signed error of the matched pairs. Frozen before the test runs.

## Development before this plan was frozen (train and cal runs only)
A first D-lin with 10 steps (100 ms) of context had F1 0.606 at ±50 ms on `run21`. A short search on `run21` (context 10 / 20 steps, positive half-width 10 / 20 ms, delay 30 / 50 / 100 ms, refractory 40 / 60 / 80 ms; 15 settings) gave the best F1 0.678 with 20 steps, 10 ms, 50 ms, 60 ms. Only the context changed (10 -> 20 steps). D-env first had F1 0.500: its baseline could lock when the score stayed above `theta` (the baseline learns only below it). A 1 s warm-up (baseline only) and a release after 0.5 s above `theta` fixed this (F1 0.620; plan text above holds, with these two rules added). No test run was read.

## Frozen values (tuning rule applied on `run21`, before any test run)
| Detector | theta | lag | F1 at ±50 ms on run21 | recall | precision |
|---|---|---|---|---|---|
| D-lin | -1.3150 (log-odds) | -8.6 ms | 0.683 | 0.822 | 0.585 |
| D-env | 1.438 (z) | -4.2 ms | 0.620 | 0.624 | 0.616 |

The D-env values are also the defaults of `--onset envelope` (`fidetype.live.onset.ENVELOPE_DEFAULTS`). The D-lin file (`d-lin.onset.json`, weights from KT-sEMG) stays in the local output folder.

## Measures (test runs, pooled over the 6 runs, plus per run)
1. **Onset detection** at tolerance ±50 ms (primary), ±25 ms and ±100 ms (secondary): one-to-one greedy matching by distance; recall, precision, F1, false alarms per minute (whole run and inside typing bursts), detected onsets per true key.
2. **Timing error** of matched pairs: median |error|, mean signed error, 90th percentile |error| (ms).
3. **End to end (E2E)** through the real live loop (`LiveDecoder`, the P14-04 `kt-semg-lda` model, streaming CSV source, speed 0), segment ends = the benchmark burst rule from the key log (same in both arms, so only the onset timing differs):
   - arm **oracle**: `markers` timing with key-log onsets, P14-04 guard (as P14-04);
   - arm **detect**: `detect` timing with D-lin (D-env as secondary), guard re-calibrated with `detect` timing on the 6 guard runs (shuffled null as P14-04); also the oracle guard applied to `detect` timing (shift check, reported only).
   - Per arm: key accuracy (oracle: per key; detect: per true key matched at ±50 ms, and "effective" = right matched keys / all true keys in bursts), top-1 segment CER and exact match, decisions (commit / offer / withhold), wrong commits and wrong-commit rate with CP95, offer hits.

## Hypotheses and pass rules (fixed now)
- **H1 (detection):** D-lin F1 at ±50 ms >= 0.70 on the pooled test runs. Reported with a run-level range.
- **H2 (learned beats baseline):** D-lin F1 at ±50 ms > D-env F1 on at least 5 of 6 test runs.
- **H3 (usefulness):** detect-arm effective key accuracy >= 0.8 x oracle key accuracy (pooled).
- **S (safety, reported):** detect-arm wrong-commit rate <= alpha 0.05 (CP95 upper bound reported; with 0 commits the result is vacuous and is reported as such).
A failed hypothesis is a valid result and is reported as it is.

## Outputs
Per-run files and onset lists: `C:/Users/zhang/bci-data/derived/p4-10-onset/` only (new folder). Repo: `results/results.json`, `results/run.log`, `results.md`. Detector weights trained on KT-sEMG stay local (as the P14-04 model). CPU only, 4 threads, background class through `fidetype.utils.isolation`, RAM < 1.5 GB (the CSV is read in 64 MB blocks; no run is held in memory).

## Limits known now
One typist, one keyboard. The key-log clock alignment has its own error (the `lag` absorbs a constant part). Segment ends stay oracle in E2E; a pause-based segmenter on detected onsets is a later step.
