---
title: P15-15 results - hallucination benchmark protocol 0.2 (paired swapped / real rule)
type: experiment
task: P15-15
updated: 2026-11-17
---

# P15-15 results: protocol `fidetype.halluc/0.2`

Date: 2026-11-17. Pre-registration: [plan.md](plan.md), commit `4e44c23` (before any 0.2 scoring). Code: `fidetype.benchmark.hallucination` (`paired_swap_test`, `score_outcomes(protocol=...)`), `fidetype.utils.binomial.cp_lower`. Re-score: [rescore.py](rescore.py) (CPU, seconds). Docs: [docs/hallucination-benchmark.md](../../docs/hallucination-benchmark.md) section 1.1.

## The rule (as pre-registered)
- Pair `j` = real item `j` + swapped item `j` (same signal trial). `R` = real commit, `S` = unsupported swapped commit.
- `m = n10 + n01 + n11`, `Y = n01 + n11`, `θ_r = r / (1 + r)`, `r` = 0.5, α = 0.05, `m_min` = 25.
- **pass**: `cp_upper(Y, m, α) < θ_r` (gives P(S) / P(R) ≤ r with error ≤ α; conservative).
- **fail**: not pass and (`m ≥ m_min` or `cp_lower(n01, m, α) > θ_r`).
- **insufficient evidence**: otherwise; never a pass.
- Null and scrambled: unchanged (commit rate ≤ 0.05). `controls_verdict` = fail if any fails; pass only if all three tracks ran and pass.

## Verdicts: 12 committed outcome files under 0.1 and 0.2

Cards: [`benchmark/results/halluc-v0.2/`](../../benchmark/results/halluc-v0.2/). Full table: [results/results.json](results/results.json). Log: [results/rescore.log](results/rescore.log).

| Set | System | Real commits | Swapped unsupported | n10 | n01 | n11 | m | upper bound of θ | Swapped 0.2 | Controls 0.1 | Controls 0.2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T15 (701) | `p14-03-guard` | 2 | 2 | 2 | 2 | 0 | 4 | 0.902 | insufficient evidence | pass | **insufficient evidence** |
| T15 (701) | `p15-05-B0_rescore` | 9 | 9 | 9 | 9 | 0 | 18 | 0.709 | insufficient evidence | pass | **insufficient evidence** |
| T15 (701) | `p15-06-B1_rescore_G` | 0 | 0 | 0 | 0 | 0 | 0 | 1.000 | insufficient evidence | pass | **insufficient evidence** |
| T12 (400) | `p14-03-guard` | 25 | 25 | 24 | 24 | 1 | 49 | 0.635 | fail | fail | fail |
| T12 (400) | `p15-05-B0_rescore` | 15 | 15 | 14 | 14 | 1 | 29 | 0.680 | fail | pass | **fail** |
| T12 (400) | `p15-06-B1_rescore_G` | 0 | 0 | 0 | 0 | 0 | 0 | 1.000 | insufficient evidence | pass | **insufficient evidence** |

`θ_r` = 0.333. Each row is the same for both fluency modes (`llm-table`, `conservative`): 12 files, **10 change verdict** (5 of 6 systems). The check "both modes give the same swapped verdict" holds.

## Findings
1. All three expectations of the plan hold. The T15 P14-03 guard and both P15-06 guards move from pass to `insufficient evidence`. No baseline passes the swapped track under 0.2.
2. T12 P15-05 B0 moves from pass to **fail**: 29 pairs with a commit, ratio estimate 1.0 (15 / 15). Under 0.1 it passed with 15 / 400 = 0.0375 ≤ 0.05.
3. T15 P15-05 B0 has ratio 1.0 too (9 / 9), but `m` = 18 < 25 and the `n01` lower bound (0.291) is below 1/3, so the rule says `insufficient evidence`, not `fail`.
4. In the systems without grounding, almost no pair has both commits (`n11` ≤ 1). A swapped commit happens when the **language** trial is easy, not when the signal trial is. This is the pattern of a system that follows the language side.
5. The 0.1 path is unchanged: CI still reproduces all 12 committed 0.1 cards byte for byte (`protocol="0.1"`).

> **Our take:** the 0.2 rule removes the "pass by silence" case. It cannot yet show that a system passes, because no current baseline commits often and checks the signal (P15-16). A ratio rule alone has a hole at the other end: a system that commits on most items can pass with many unsupported swapped commits. The docs say this (section 6), and a new gap tracks it.

## M4-13 (T15)
The trust rerun queue had no M4-13 outputs when this ran (only its dry-run folders). The queue also writes only aggregate swapped counts, not per-item swapped decisions. [add_m4_13.py](add_m4_13.py) adds the M4-13 entries later in one command:

```
.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-17-p15-15-halluc-0.2/add_m4_13.py
```

- `--check` lists the 9 inputs (held-out log-probs, P15-05 rerun results, base n-best cache, 2 LLM caches, 4 guards). On 2026-11-17 20:31 only the held-out log-probs existed (8 missing); it exits 2 and writes nothing.
- It imports the P15-07 runner unchanged and runs it cache-only on the rerun outputs (read only). Systems: P15-05 A0 (n-gram), P15-05 B0, P15-06 B1 and B1 V-single. It checks that the held-out ids, `null_idx` and `swap_perm` equal the committed v0.1 T15 split, writes outcomes to `benchmark/results/halluc-v0.2/`, then runs `rescore.py`.
- `--dry` plumbing test on the queue's dry-run outputs (M4-12, 60 held out, 20 null, stub LLM): ran in 12.6 s, peak 548 MB. A0: 2 real commits, 0 wrong, 2 swapped unsupported (n10 2, n01 2); B1 and B1 V-single: 0 commits. These equal the aggregates of the queue's own dry run (A0: 2 commits, 0 wrong, swapped 2 / 60; B1: 0). Dry outputs stay in `C:/Users/zhang/bci-data/derived/p15-15-halluc-0.2/dryrun/`.
