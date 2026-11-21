---
title: P15-34 Calibration-inclusive T15 safe WPM with a safety-margin guard - results
type: experiment
task: P15-34
updated: 2026-11-20
---

# P15-34: a guard with a safety margin, interval over calibration draws (results)

Pre-registration: [plan.md](plan.md), commit `025e928`. It was committed and pushed before any number was computed. Stage S (lever selection on `val_select` only) and the plan addendum that names the four arms are in commit `d7f224b`. Both were committed before the main run started. Code: [`run.py`](run.py), [`launch.py`](launch.py). Aggregates (no text): [`results/selection.json`](results/selection.json), [`results/results.json`](results/results.json). Log: [`results/run.log`](results/run.log). Per-trial decisions (with text) are local only, in `C:\Users\zhang\bci-data\derived\p15-34\`.

Run details:
- Stage S: 2026-11-20 05:10-05:15 (248 s, peak 2.52 GB), calibration data only.
- Main run: 2026-11-20 05:15-09:51, detached. Two workers, background class, 4 threads each, **CPU only**. Peak private memory 2.84 GB and 2.87 GB per worker (total under 6 GB).
- Code: a `git archive` snapshot of `025e928`, because another agent had uncommitted changes in `src/fidetype/trust/dropin.py`, `streaming.py` and `pretrained/_crt.py`.
- All 40 new draws of all four arms finished. No draw was refused. No null control failed.

## Lever choice
- **Larger calibration set: not possible.** T15 has labelled trials only in `train` (the decoder was trained on them), `val_select` (722, calibration) and `val_eval` (701, evaluation). The competition test split has no labels.
- **Safety margin: used.** Stage S ranked 28 (alpha', delta') arms in a bootstrap world on the LTT items of 4 seeds ([selection.json](results/selection.json)). No arm had a predicted lower end above 4.0153 (best 2.69). The arm rule chose:

| arm | alpha' | delta' | role | stage S prediction |
|---|---|---|---|---|
| A0 | 0.05 | 0.1 | reference (P15-29 settings) | 5.07 [0.00, 7.00] |
| **A1** | 0.05 | 0.025 | **primary** | 4.86 [2.69, 6.78] |
| A2 | 0.04 | 0.1 | secondary (alpha margin) | 4.86 [2.69, 6.78] |
| A3 | 0.05 | 0.01 | secondary (delta margin) | 4.63 [2.67, 6.63] |

## Verdict (pre-registered rule)

| arm | safe WPM v0.1 [95 %], calibration + trials, K = 40 | certified / above-alpha / vacuous / refused | lower end > 4.0153? | verdict |
|---|---|---|---|---|
| **A1 (primary)** | **4.90 [3.11, 6.44]** | 40 / 0 / 0 / 0 | **no** | **above, but inside the combined interval** |
| A2 (secondary) | 4.90 [3.11, 6.44]; 1.25th percentile 2.90 | 40 / 0 / 0 / 0 | no (Bonferroni) | above, but inside the combined interval |
| A3 (secondary) | 4.58 [2.47, 6.17]; 1.25th percentile 2.31 | 40 / 0 / 0 / 0 | no (Bonferroni) | above, but inside the combined interval |
| A0 (reference, no test) | 5.35 [4.05, 6.81] | 40 / 0 / 0 / 0 | yes (by 0.03) | descriptive only |

**The pre-registered criterion is not met.** The primary arm A1 has a lower end of 3.11, below the no-BCI 4.0153. Gap 132 stays open.

The "strict" scores (sheet alpha alpha') are equal to the claimed scores in every arm: no draw had a test wrong-commit rate above its alpha' (maximum 0.0385 in A1 and A2, 0.0342 in A3).

## Why the margin does not help (the trade-off)

| arm | mean commits | mean wrong commits | max test wrong-commit rate | draw values: mean, SD, range | draws <= 4.0153 | SD between / within draws |
|---|---|---|---|---|---|---|
| A0 | 215.3 | 16.8 | 0.0456 | 5.35, 0.63, 4.14-6.68 | 0 / 40 | 0.63 / 0.35 |
| A1 = A2 | 194.9 | 13.4 | 0.0385 | 4.90, 0.78, 2.93-6.26 | 6 / 40 | 0.78 / 0.34 |
| A3 | 181.0 | 11.4 | 0.0342 | 4.58, 0.91, 2.43-6.08 | 10 / 40 | 0.91 / 0.33 |

- The margin does what it should for safety: fewer wrong commits, lower wrong-commit rates.
- But on these 40 draws no A0 draw was above alpha. So the margin removed no zero draw (paired: 0 draws changed from `above-alpha` to `certified`).
- It cost value in every draw: mean paired difference to A0 is -0.45 (A1, A2) and -0.77 (A3). No draw gained.
- It also widened the spread between draws (SD 0.63 to 0.78 to 0.91). More draws fall below 4.0153 (6 / 40 in A1, 10 / 40 in A3).
- The between-draw SD is about 2 to 3 times the within-draw (trial bootstrap) SD in every arm. The lower end is set by the calibration-sample variation, not by the evaluation trials.
- A1 and A2 give the same threshold in every draw. With exact binomial LTT on 271 items, (alpha 0.05, delta 0.025) and (alpha 0.04, delta 0.1) accept the same grid points here. Stage S showed the same tie.

## The reference arm A0 and P15-29 (descriptive, not a test)
- A0 uses the P15-29 settings on 40 **new** calibration draws. It gives 5.35 [4.05, 6.81] with 40 / 40 certified. P15-29 gave 5.18 [0.00, 6.99] with 2 / 40 `above-alpha` draws.
- So with the same settings, the lower end moved from 0.00 to 4.05 only because of which 40 draws were taken. Above-alpha draws are rare (the LTT allows up to delta = 10 %). With K = 40, one such draw holds 2.5 % of the pooled mass, and that alone puts the 2.5th percentile at or near 0.
- Pooling the two A0-type sets (K = 80; not pre-registered, argued without a new computation): 2 / 80 = 2.5 % of the pooled mass is 0.0. The certified P15-29 draws k14 (3.50) and k35 (3.87) add more mass below 4.0153. So the pooled 2.5th percentile is below 4.0153.
- A0 was pre-registered as a reference without a test. Its lower end does not count as meeting the criterion and does not change any public claim.

> **Our take:** a safety margin is the wrong lever for this goal on T15. The P15-29 zeros come from rare unsafe draws (about 1 in 20 to 1 in 40 here). A margin removes them only at a cost in every draw, and the cost is larger than the gain, because the between-draw spread (SD 0.6-0.9) is already as large as the distance from the mean to 4.0153. To get a lower end clearly above 4.0153 the spread must fall. That needs more calibration items (the spread comes from 180 fit + 271 LTT items, and from bootstrap duplicates, limit (b)) or a lower-variance calibration procedure. Without new labelled T15 data that is not in `val_eval`, we expect no guard to pass this criterion honestly. New gap 139 ([P15-35](../../wiki/questions/roadmap-standard.md#p15-35-lower-variance-calibration-for-the-calibration-inclusive-safe-wpm)) records this.

## Cross-checks

| check | result |
|---|---|
| **X4 code check (must pass)** | **passes.** z0 (seed 0, no resampling, A0) = the P15-22 decisions on 701 / 701 trials, safe WPM 4.91. The library with K = 1 gives [4.25, 5.57] = the P15-22 CI. Threshold 0.82, 196 commits, 13 wrong = the P15-29 z0. |
| Stage S check | the recomputed LTT threshold equals the guard threshold for seeds 0-3 (0.82, 0.75, 0.69, 0.75). |
| z0 with the margin arms | A1 = A2 3.96 (152 commits, 6 wrong), A3 3.18 (121, 4). On the seed-0 split every margin arm is below 4.0153. |
| Null controls | every draw of every arm passes (allowed 15 of 300). |

## Notes and limits
- The P15-29 limits apply: (a) pinned pipeline values (T, tau, lambda), (b) duplicates in the resampled LTT part (a single draw's certificate is not a valid certificate; the spread may be over-stated a little), (c) one participant and one decoder checkpoint, (d) the same evaluation set in every draw.
- (e) For A2 (alpha' 0.04) the claimed guarantee is the weaker statement at alpha 0.05 that the alpha' certificate implies. Here it changes no status.
- Stage S leaves out the variation of the learned-score fit. It ranked A1 = A2 above A3, as the main run did. It predicted above-alpha draws for A0 (5.5 % of its draws); none occurred in these 40 draws, so A0 ranked last in stage S and first in the main run.
- `docs/safe-wpm.md` is unchanged. No rule change is proposed. One reporting point for the user to decide (proposal only): with the 6b method, K = 40 makes the lower end jump to 0 for a single non-certified draw. A report could give K and the number of non-credited draws next to the interval, or use a larger K (for example 80 or more) when a lower end near a reference matters.
- Public claims: unchanged. The T15 headline from P15-29 ("above gaze typing on average, not reliably above") stays. README, overview, north-star and frontier-safe-wpm need no correction.
