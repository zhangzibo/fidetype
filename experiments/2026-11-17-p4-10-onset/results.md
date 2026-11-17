---
title: P4-10 live key-onset detector for EMG - results
type: experiment
task: P4-10
updated: 2026-11-17
---

# P4-10 results: causal key-onset detectors on KT-sEMG

Pre-registration: [plan.md](plan.md), committed in `c3834c2` before any test run was read. Code: [`src/fidetype/live/onset.py`](../../src/fidetype/live/onset.py), [run.py](run.py). Numbers: [results/results.json](results/results.json), log: [results/run.log](results/run.log). Local outputs (not committed): `C:/Users/zhang/bci-data/derived/p4-10-onset/`. Data: KT-sEMG v1.1, copyright 2021 Nokia, CC BY 4.0. CPU only, 4 threads, background class, RAM < 1.5 GB (streaming CSV reader).

One deviation from the plan, plumbing only: the first `features --set test` call stopped at once (the feature helper did not pass `context`; step features do not depend on it). Fixed, then the stages ran in plan order. No method changed.

## Verdict

| Hypothesis | Rule | Result | Verdict |
|---|---|---|---|
| H1 detection | D-lin F1 at ±50 ms >= 0.70 (pooled) | **0.588** (run range 0.044 … 0.734) | **fail** |
| H2 learned beats baseline | D-lin > D-env on >= 5 of 6 runs | 6 of 6 (pooled 0.588 vs 0.461) | pass |
| H3 usefulness | effective key accuracy >= 0.8 x oracle | 0.229 vs 0.274 = **0.84 x** | pass |
| S safety | wrong-commit rate <= 0.05 | 0 commits in every arm (CP95 upper 0.021 over 172 decisions) | pass, **vacuous** |

The detector streams: on run26, `process()` on the raw CSV in 0.37 s chunks gives the same onsets as the cached evaluation path (D-lin 2444 = 2444, D-env 2569 = 2569).

## 1. Onset detection (6 test runs, 28,910 true key presses)

| Detector | Tolerance | Recall | Precision | F1 | False alarms / min |
|---|---|---|---|---|---|
| D-lin | ±25 ms | 0.501 | 0.276 | 0.356 | 316.6 |
| D-lin | **±50 ms** | **0.829** | **0.456** | **0.588** | 237.7 |
| D-lin | ±100 ms | 0.922 | 0.507 | 0.655 | 215.3 |
| D-env | ±25 ms | 0.353 | 0.233 | 0.281 | 279.2 |
| D-env | ±50 ms | 0.580 | 0.383 | 0.461 | 224.7 |
| D-env | ±100 ms | 0.707 | 0.467 | 0.563 | 194.1 |

Per run at ±50 ms (D-lin; timing error of matched pairs in ms):

| Run | True keys | Detected | Recall | Precision | F1 | median abs err | mean signed err | p90 abs err | FA / min in bursts | D-env F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| run24 | 11,519 | 13,977 | 0.804 | 0.662 | 0.726 | 21.5 | +6.1 | 40.5 | 161 | 0.603 |
| run25 | 13,335 | 16,738 | 0.827 | 0.659 | 0.734 | 21.3 | +5.1 | 40.7 | 166 | 0.616 |
| run26 | 107 | 2,444 | 0.944 | 0.041 | 0.079 | 17.7 | +8.5 | 34.5 | 461 | 0.043 |
| run27 | 230 | 9,140 | 0.900 | 0.023 | 0.044 | 18.4 | +2.8 | 37.1 | 398 | 0.020 |
| run28 | 808 | 3,817 | 0.938 | 0.199 | 0.328 | 16.3 | -0.6 | 36.6 | 412 | 0.219 |
| run29 | 2,911 | 6,427 | 0.897 | 0.406 | 0.559 | 15.8 | -0.3 | 37.3 | 257 | 0.404 |

- On the two runs with dense typing (run24, run25) D-lin reaches F1 0.73, above the H1 line, with 80 % recall and about 66 % precision.
- On the runs with little typing (run26: 107 keys, run27: 230 keys) recall stays high (0.90-0.94), but the detector fires on other forearm activity: precision 0.02-0.04. The pooled F1 fails H1 because of these false alarms.
- Matched onsets are close: median error 16-22 ms, 90 % within 41 ms.

## 2. End to end (live loop, oracle segment ends, 172 segments)

| Arm | Timing / guard | Windows | Key acc. (matched) | Key acc. (effective) | Mean top-1 CER | Decisions | Commit / offer / withhold | Offer hits |
|---|---|---|---|---|---|---|---|---|
| oracle | key-log onsets / P14-04 guard | 28,862 | 0.274 | 0.274 | 0.70 | 172 | 0 / 172 / 0 | 0 |
| **detect D-lin** | D-lin / guard re-calibrated on detect | 52,538 | 0.276 | **0.229** | 3.16 | 172 | 0 / 172 / 0 | 0 |
| detect D-env | D-env / guard re-calibrated on detect | 43,780 | 0.231 | 0.134 | 3.64 | 172 | 0 / 172 / 0 | 0 |
| detect D-lin, oracle guard | D-lin / P14-04 guard (shift check) | 52,538 | 0.276 | 0.229 | 3.16 | 172 | 0 / 172 / 0 | 0 |

- When a detected onset matches a key, its window decodes as well as the oracle window (0.276 vs 0.274): the timing error of about 20 ms does not hurt this decoder.
- The cost is in the counts: 17 % of the keys are missed, and about 28,600 of the 52,538 windows match no key (false alarms). The extra keys make the decoded text longer, so the top-1 CER is 4.5 times the oracle CER. H3 (key accuracy) does not see this cost.
- Guards: both re-calibrated guards (173 items each, the 6 P14-04 guard runs) pass both null controls; top-1 exact 0.000 on calibration, so no threshold is certified and they never commit. Every arm offers every segment, with no offer hit (as in P14-04 run28). The safety result is therefore vacuous: the decoder is too weak for any commit.

## What this closes
`fidetype live --timing detect` runs with a causal detector (`--onset envelope` with defaults from this tuning, or a trained `*.onset.json`). On the KT-sEMG test runs it finds onsets with recall 0.829 and 238 false alarms per minute at ±50 ms (D-lin), and the replay with detected onsets reports decisions and the wrong-commit rate next to the oracle run. This meets the P4-10 "done when".

## New gaps
- **Gap 21 (P4-12):** onset false alarms on forearm activity without typing (precision 0.02-0.04 on run26 / run27). Next: a typing-activity gate, negatives from idle periods in training, or a detector that shares the P11-01 decoder.
- **Gap 22 (P4-13):** segment ends still come from markers (oracle here). A pause-based segmenter on detected onsets is needed for a fully marker-free live run.

> **Our take:** the detector is good where the user types and bad where the user does other things with the hands. For a live product the second case matters most: a gate that knows "typing now" comes first. The key decoder, not the onset timing, still limits the text (top-1 exact 0 in every arm).
