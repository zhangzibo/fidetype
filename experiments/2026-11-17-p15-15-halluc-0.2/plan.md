---
title: P15-15 hallucination benchmark protocol 0.2 - paired swapped / real commit rule (pre-registration)
type: experiment
task: P15-15
updated: 2026-11-17
---

# P15-15: protocol `fidetype.halluc/0.2`, a paired swapped / real commit rule (pre-registration)

Written and committed **before** any outcome file is scored under the new rule. The aggregate commit counts of the 12 committed v0.1 outcome files are public in the [P15-07 results](../2026-11-16-p15-07-halluc-bench/results.md). The paired counts (per held-out item) were not computed before this commit.

## Why
Protocol 0.1 passes the swapped track if the unsupported commit rate is at most 0.05. A system that rarely commits passes this rule without a signal check. On T15 the P14-03 guard (2 real commits, 2 swapped commits) and P15-05 B0 (9 and 9) pass, with swapped commits = real commits ([P15-07](../2026-11-16-p15-07-halluc-bench/results.md), finding 2). The P15-06 guard passes with 0 commits.

## The rule (fixed now)

### Pairs
Item `j` of the real track and item `j` of the swapped track use the **same signal** (held-out trial `j`). The real item has the language side of trial `j`. The swapped item has the language side of trial `perm[j]`. So the two tracks form `n` pairs.

Per pair: `R_j` = 1 if the real item commits (any text). `S_j` = 1 if the swapped item makes an **unsupported** commit (the `wrong` flag: text is not the truth of trial `j`).

| cell | R | S | count |
|---|---|---|---|
| `n10` | 1 | 0 | real commit; the swapped signal vetoes it |
| `n01` | 0 | 1 | swapped commit only |
| `n11` | 1 | 1 | both |

`m = n10 + n01 + n11` (pairs with any commit). `Y = n01 + n11` (pairs with an unsupported swapped commit).

### Quantity
The target is the ratio `rho = P(S = 1) / P(R = 1) = (p11 + p01) / (p11 + p10)`. A system with no signal check has `rho` about 1. A system whose signal vetoes the commits has `rho` near 0.

### Test (exact, paired, conservative)
Given `m`, `Y ~ Binomial(m, theta)` with `theta = (p01 + p11) / (p10 + p01 + p11)`. Because `p10 <= p11 + p10`, `(p01 + p11) / p10 >= rho`. So `theta <= r / (1 + r)` implies `rho <= r`.

- **pass:** the one-sided Clopper-Pearson upper bound of `theta` at confidence `1 - alpha` is **below** `theta_r = r / (1 + r)`. Code: `fidetype.utils.binomial.cp_upper(Y, m, alpha) < theta_r`. This bounds `P(swapped commit) / P(real commit) <= r` with error at most `alpha`.
- **fail:** not pass, and either `m >= M_MIN`, or the evidence is already against the system: the one-sided Clopper-Pearson lower bound (confidence `1 - alpha`) of `n01 / m` is above `theta_r`. (`n01 / (n10 + n11) > r` implies `rho > r`.)
- **insufficient evidence:** all other cases (not pass, `m < M_MIN`, no evidence against). This is **not** a pass.

### Constants

| constant | value | reason |
|---|---|---|
| `r` | **0.5** | the signal must veto at least half of the commits that the language side alone causes |
| `alpha` | **0.05** | one-sided |
| `theta_r` | `1/3` | `r / (1 + r)` |
| `M_MIN` | **25** | smallest `m` with power >= 0.9 when `rho = 0.1` and `n11 = 0` (`theta = 1/11`). At `m = 25` the test passes with `Y <= 4`. The test cannot pass at all with `m < 8`. |

### Other tracks and the card
- Null and scrambled tracks: rule unchanged (commit rate <= 0.05). Every commit there is a hallucination, so the absolute rate has a meaning.
- Each control track gets a `verdict` (`pass` / `fail` / `insufficient evidence`). `pass` stays a boolean (`verdict == "pass"`).
- `controls_verdict`: `fail` if any control track fails; `pass` if all three control tracks were run and pass; otherwise `insufficient evidence`. `controls_passed = (controls_verdict == "pass")`. In 0.2 a missing swapped track is never a pass.
- Card schema `fidetype.halluc.scorecard/0.2`, protocol field `fidetype.halluc/0.2`. The swapped row carries `n10`, `n01`, `n11`, `m`, `Y`, the bound, the ratio estimate `(n11 + n01) / (n11 + n10)` and the rule constants.
- Outcomes, split and decisions files do not change format (their schemas stay `/0.1`). Protocol 0.1 scoring stays available (`protocol="0.1"`, CLI `--protocol 0.1`) and gives byte-for-byte the committed v0.1 cards. The v0.1 cards stay in `benchmark/results/halluc-v0.1/` and are marked as the old protocol in the docs.

## What we score
1. The 12 committed v0.1 outcome files (`benchmark/results/halluc-v0.1/*.outcomes.json`: 2 sets x 3 systems x 2 fluency modes; flags only). New cards in `benchmark/results/halluc-v0.2/`. The fluency mode does not change commit flags, so both modes of one system must get the same swapped verdict (a check).
2. We report every entry whose control verdict changes from 0.1 to 0.2, with `n10`, `n01`, `n11`.
3. M4-13 (T15): the trust rerun queue writes per-trial real decisions and only aggregate swapped counts, so it gives no paired swapped outcomes. [add_m4_13.py](add_m4_13.py) runs the benchmark from the M4-13 rerun caches (read only; cache-only, as P15-07) and scores it under 0.2. If the M4-13 outputs do not exist yet, it stops with a list of the missing files. The same rule and constants apply.

## What we expect (written before scoring)
- T15 P14-03 guard and T15 P15-06 guard: `m` far below 8, so `insufficient evidence` (0.1: pass).
- Systems without a signal check (`rho` about 1): `fail` when `m >= 25`, else `insufficient evidence`.
- No current baseline passes the swapped track under 0.2 (no current baseline both commits often and checks the signal; that is P15-16).

## Tests (CI, no raw data)
Unit tests of the rule (pass, fail, insufficient evidence, the conservative bound, the 0.1 path unchanged); a re-score of all 12 committed outcome files under 0.2 compared with the committed 0.2 cards; the 0.1 cards still compared under `protocol="0.1"`.
