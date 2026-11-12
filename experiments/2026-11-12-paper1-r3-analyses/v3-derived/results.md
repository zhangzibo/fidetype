# Draft v3: derived numbers (M3-18)

Script: [run.py](run.py) (CPU, seconds). Input: `../repeated-splits/results/per_split.json` (committed). Output: [results/v3_derived.json](results/v3_derived.json), [results/tables.md](results/tables.md).

## What we did
- Per repeated deployment split (R = 50), paired eWPM difference between each rule and the same fit-A policy with commits switched off (lambda = +inf). The beta = 0.05 selective controllers commit nothing in every split, so their eWPM is this no-commit policy.
- Paired eWPM difference of the LTT max rule against the CRC max rule and the plug-in rule.

## Results (used in the v3 abstract and Section 7.2)
| condition | LTT max rule - no commit | LTT max - CRC max | LTT max - plug-in |
|---|---|---|---|
| B2T ours | +0.114 [+0.063, +0.164], > 0 in 50/50 | -0.010 | -0.018 |
| B2T published | +0.510 [+0.439, +0.599], > 0 in 50/50 | -0.036 | -0.055 |
| sEMG session-cal. | +0.033 [+0.011, +0.056] | -0.003 | -0.007 |
| sEMG cross-session | -0.001 [-0.007, +0.004] | 0.000 | 0.000 |

Values: mean [5th, 95th percentile] over splits.

## Interpretation
> **Our take:** The guaranteed rule is faster than the same policy without commits in every B2T deployment, and it costs about 0.01 (ours) to 0.04 (published) eWPM against the CRC max rule.
