# R4 item 1: forward-chaining (time-ordered) deployment on B2T '25

Reviews: editor M1, stats M1. Tables: [results/tables.md](results/tables.md). Data: [results/forward_chain.json](results/forward_chain.json). Item tables (cache, outside the repo): `C:/Users/zhang/bci-data/cache/paper1-r4/forward/` (13 prefixes x 2 decoders x guard on / off = 52 files, no failed fit).

## Design
- 14 post-implant days (30-208 main-vocabulary trials each). Order inside a day = file order (the only time order in the pickle).
- For each prefix j, the pipeline is fitted on all trials of days 1..j (`pipe.fit(F, F)`, the fit-A recipe). Item tables are built for every later day.
- Calibration data always come before the test data in time:
  - **V1:** fit days 1..k-2, calibrate on day k-1, test day k (12 test days).
  - **V4:** fit days 1..k-3, calibrate on days k-2 and k-1 (11 test days).
  - **V2:** fit once on days 1-3, calibrate on all earlier non-fit days 4..k-1, test day k (10 test days).
  - **V3 (session start):** fit days 1..k-1, calibrate on the first half of day k, test on its second half (13 test days).
- Rules: plug-in, CRC max, LTT max, CRC / LTT pure, joint LTT (β 0.10, 0.20). α = 0.05, δ = 0.1. Guard on (paper) and guard off (plain threshold).
- Per test day: wrong-commit rate with exact Clopper-Pearson 95 % CI, commit rate, error among commits (EAC), eWPM. "Days > α" counts days with a test rate above α.

## Results (days above α; pooled wrong-commit [CP95] over all test trials of the variant)

| condition | variant | plug-in | CRC max | **LTT max** | joint LTT β=0.10 |
|---|---|---|---|---|---|
| ours, guard | V1 | 5/12, 0.052 [0.041, 0.065] | 4/12, 0.036 | **2/12** (days 74, 95), 0.022 [0.015, 0.031] | 0/12, commits nothing |
| ours, guard | V4 | 5/11, 0.060 | 4/11, 0.042 | **0/11**, 0.027 | 0/11, nothing |
| ours, guard | V2 | 6/10, 0.057 | 4/10, 0.046 | **1/10** (day 88), 0.027 | 0/10, nothing |
| ours, guard | V3 | 5/13, 0.058 | 3/13, 0.029 | **2/13** (days 34, 76), 0.015 | 0/13, nothing |
| ours, no guard | V1 | 1/12, 0.038 | 0/12, 0.029 | **0/12**, 0.018 | 0/12, nothing |
| ours, no guard | V3 | 3/13, 0.043 | 2/13, 0.025 | **2/13**, 0.018 | 0/13 |
| published, guard | V1 | 1/12, 0.023 | 1/12, 0.021 | **0/12**, 0.016 [0.010, 0.024] | 0/12, nothing |
| published, guard | V2 | 0/10, 0.024 | 0/10, 0.023 | **0/10**, 0.023 | 0/10, 0.0016 (commit 0.064) |
| published, guard | V3 | 1/13, 0.028 | 1/13, 0.020 | **1/13** (day 34), 0.010 | 0/13 |
| published, no guard | V1 | 1/12, 0.016 | 0/12, 0.015 | **0/12**, 0.010 | 0/12 |

- Under LTT max, no test day had a CP lower bound above α in any variant. The highest single-day LTT max rate was 0.060 (ours, guard).
- The plug-in rule had one day with a CP lower bound above α (ours: day 46 in V1, day 48 in V4, day 34 in V3).
- Share of days above α under LTT max: 0-2 of 10-13 (e.g. 2/12 = 0.17, CP95 [0.02, 0.48]). With 12 test days, this cannot confirm or exclude δ-level control per day.
- Joint LTT with β = 0.10 commits nothing when one day (30-208 trials) calibrates: the selective test cannot reject on so few commits. With V2 (larger calibration) the published gate commits 6.4 %.
- Staleness (V1 threshold applied 2-12 days later): see tables.md; the LTT max rate stays near 0.02-0.03 on average.

## Interpretation (for the reviser)
- In forward time order, the LTT max rule kept the pooled wrong-commit rate at 0.010-0.027 (all variants, both decoders, guard on or off). Per day, it was above α on 0-2 of 10-13 days, and never significantly above α. This is the deployment test the reviewers asked for. It supports "the rule held across days in time order on one participant"; it does not show per-day control (see per-day item 2).
- The plug-in rule failed more often in time order (up to 6/10 days above α with the guard on).
- The guard-on configuration of ours had more days above α than guard off (V1: 2/12 vs 0/12).

## sEMG: no session-order version
The Toronto sEMG data have isolated, metronome-paced key presses, not typed text. Composed fit sentences use presses of the first day-2 recording of each letter; test sentences use the later day-2 recordings. So every sEMG split already calibrates on an earlier recording than the test data. Inside a pool there is no time order (sentences are composed from presses drawn at random), and only day-2 sessions are used. A forward chain over sessions is therefore not possible without a new composition design.
