# v4-derived: small extra numbers for draft v4

Task: M3-21 (Paper 1 revision round 4 -> draft v4). CPU only. Item tables come from the R4 cache (outside the repo); no signals or texts are written here.

## 1. Frozen v4 configuration on the control streams ([guard_controls.py](guard_controls.py))
Split A fit-A pipeline (alternate trials of each day's fit half), **guard on**, clean calibration (the other half), 300 Brain-to-Text '25 control trials (same draw and seed as `no-guard/`). Results: [results/guard_controls.md](results/guard_controls.md), [results/guard_controls.json](results/guard_controls.json), log [results/guard_controls.log](results/guard_controls.log).

| decoder | rule (guard on) | split-A test wrong-commit | real | other trial | frame-shuffled | uniform |
|---|---|---|---|---|---|---|
| ours | LTT max (frozen v4) | 0.0245 (commit 0.100) | 29/300 | 29/300 | **0/300** | **0/300** |
| ours | joint LTT beta 0.10 | 0 | 0/300 | 0/300 | 0/300 | 0/300 |
| published | LTT max (frozen v4) | 0.0294 (commit 0.403) | 115/300 | 0/300 | **0/300** | **0/300** |
| published | joint LTT beta 0.20 | 0.0184 (commit 0.321) | 87/300 | 0/300 | 0/300 | 0/300 |

- Consistency check: the refitted split-A test rates equal the committed clean-drift values (0.0245, 0.0294).
- Compare guard off (`no-guard/`, frozen v3): ours 198/300 uniform and 3/300 frame-shuffled committed, all wrong.
- One-sided 95 % CP upper bound for 0/300: 0.0099.

## 2. Small numbers ([derived.py](derived.py) -> [results/derived.json](results/derived.json))
- Selective bound worked example (supplement S2): 0/40 calibration commits -> one-sided exact 90 % upper bound 0.056; 3/40 -> 0.159 (0.124 and 0.248 at delta/20).
- MEG seed gaps to the shuffled control (greedy CER): 0.254, 0.243, 0.140 (seeds 0, 1, 2).
- Published gate, fixed split A: guaranteed rule keeps 95.1 % of always-commit eWPM (18.65 / 19.61).
