---
title: P15-56 signal-check tracks - results (truncated, noise mix, near-miss swap) on the 10 shipped baselines
type: experiment
task: P15-56
gap: 232
updated: 2026-11-27
---

# P15-56 results: signal-check tracks on the 10 shipped baselines

Pre-registration: [plan.md](plan.md) (commit 81af859). Code: commit 01ff0ff (`fidetype.benchmark.hallucination`, tests `tests/test_halluc_signal_checks.py`, docs [section 1.2](../../docs/hallucination-benchmark.md)). Runner: [run.py](run.py). CPU only, 2026-11-25 09:37 to 12:03 (about 2.5 h).

## Run checks
- All 10 pre-registered systems are scored, each in both fluency modes (`llm-table` and `conservative`): 20 signal outcomes files and 20 signal cards in [results/](results/).
- **Check 1 (real-track replay):** passed for all 10 systems. No system was stopped. Every system has `status: ok` in `results/results.json`.
- **Check 2 (near-miss edits):** the per-item assert passed. Edits: T15 sets 366 items with 1 edit, 335 with 2 edits; T12 217 with 1, 183 with 2.
- **Check 3 (fluency modes):** the two modes give the same verdicts and the same paired cells for every system and level (as the plan expected).
- The committed files hold flags, counts and metadata only. They hold no sentence text and no participant data. The per-trial texts and caches stay in `C:/Users/zhang/bci-data/derived/p15-56/` (not in the repo).

## Verdict table
Cell: verdict (`Y` / `m`), with `Y = n01 + n11` (unsupported commits paired with the real track) and `m = n10 + n01 + n11`. Pass rule (pre-registered): one-sided 95 % Clopper-Pearson upper bound of `Y / m` < 1/3. Fail: not pass and `m ≥ 25` (or the `n01` share bound is above 1/3). Else: insufficient evidence (IE). `truncated_75` has no pass rule; the cell shows unsupported / all commits.

| Set | System | Real commits | trunc 25 | trunc 50 | trunc 75 (no rule) | noise 25 | noise 50 | noise 75 | near miss | Card verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| T15 M4-13 | `m4-13-p15-05-A0_ngram` | 104 | pass (11/114) | pass (19/119) | 28/125 | pass (0/104) | pass (0/104) | pass (0/104) | **fail** (104/104) | **fail** |
| T15 M4-13 | `m4-13-p15-05-B0_rescore` | 141 | pass (2/142) | pass (18/155) | 24/90 | pass (0/141) | pass (0/141) | pass (0/141) | **fail** (60/192) | **fail** |
| T15 M4-13 | `m4-13-p15-06-B1_rescore_G` | 36 | pass (0/36) | pass (2/36) | 7/18 | pass (0/36) | pass (0/36) | pass (0/36) | pass (0/36) | **pass** |
| T15 M4-13 | `m4-13-p15-06-B1_rescore_G@single` | 36 | pass (0/36) | pass (2/36) | 7/18 | pass (0/36) | pass (0/36) | pass (0/36) | pass (0/36) | **pass** |
| T15 M4-12 | `p14-03-guard` | 2 | IE (2/4) | IE (2/4) | 2/6 | IE (3/5) | IE (0/2) | IE (0/2) | IE (2/2) | IE |
| T15 M4-12 | `p15-05-B0_rescore` | 9 | pass (0/9) | IE (2/11) | 5/6 | pass (0/9) | pass (0/9) | pass (0/9) | IE (5/13) | IE |
| T15 M4-12 | `p15-06-B1_rescore_G` | 0 | IE (0/0) | IE (0/0) | 0/0 | IE (0/0) | IE (0/0) | IE (0/0) | IE (0/0) | IE |
| T12 v2 | `p14-03-guard` | 25 | pass (1/26) | **fail** (12/35) | 10/19 | pass (0/25) | pass (0/25) | pass (0/25) | **fail** (25/25) | **fail** |
| T12 v2 | `p15-05-B0_rescore` | 15 | pass (1/15) | IE (7/22) | 9/16 | pass (0/15) | pass (0/15) | pass (0/15) | IE (5/16) | IE |
| T12 v2 | `p15-06-B1_rescore_G` | 0 | IE (0/0) | IE (0/0) | 0/0 | IE (0/0) | IE (0/0) | IE (0/0) | IE (0/0) | IE |

Totals: 2 systems pass all three tracks, 3 fail, 5 have insufficient evidence. The two systems with 0 real commits (`p15-06-B1_rescore_G` on T15 M4-12 and on T12) have `m = 0` on every level. They give no evidence at all; their IE is not a pass.

### Extra counts (from the cards)

| Set | System | Near-miss commits (all) | of which = near-miss text | of which = truth | trunc 25 / 50 / 75: proper-prefix commits | trunc 50 / 75: full-sentence commits |
|---|---|---|---|---|---|---|
| T15 M4-13 | `A0_ngram` | 104 | 104 | 0 | 141 / 173 / 97 | 2 / 9 |
| T15 M4-13 | `B0_rescore` | 81 | 52 | 21 | 28 / 88 / 66 | 3 / 14 |
| T15 M4-13 | `B1_rescore_G` (both) | 3 | 0 | 3 | 2 / 13 / 11 | 2 / 7 |
| T15 M4-12 | `p14-03-guard` | 2 | 2 | 0 | 15 / 8 / 4 | 0 / 0 |
| T15 M4-12 | `B0_rescore` | 7 | 4 | 2 | 4 / 0 / 1 | 0 / 0 |
| T12 v2 | `p14-03-guard` | 25 | 25 | 0 | 8 / 19 / 9 | 0 / 0 |
| T12 v2 | `B0_rescore` | 5 | 5 | 0 | 5 / 16 / 7 | 0 / 0 |

Noise mix: no system commits at any level, except T15 M4-12 `p14-03-guard` at λ = 0.25 (6 commits, 3 wrong).

## Pre-registered expectations against the result
| Expectation (plan) | Result |
|---|---|
| Systems without grounding (`p14-03-guard`, `B0`, `A0`) fail `near_miss` where `m ≥ 25` | Holds. `A0` (m 104), M4-13 `B0` (m 192) and T12 `p14-03-guard` (m 25) fail. The three other non-grounded systems have `m` < 25 and get IE. |
| Systems that never or rarely commit get IE on most tracks | Holds for the systems with 0 or 2 real commits. The systems with 9 and 15 real commits pass some levels with `Y = 0` (the rule allows a pass from `m` = 8 when `Y` = 0). |
| No prediction for grounded systems on `truncated` and `noise_mix` | M4-13 `B1` passes both. M4-12 and T12 `B1` have no real commits. |

## Reading

**Near-miss swap: grounding is the difference.** Systems without a signal check follow the language side. `A0_ngram` commits the near-miss text in all 104 cases where it commits on real data. T12 `p14-03-guard` does the same in 25 of 25. LLM rescoring (`B0`) moves away from the near-miss text in some cases (21 of 81 commits are the truth), but 60 commits are still unsupported, and it fails. The grounded system (`B1_rescore_G`, M4-13) commits the near-miss text **0** times. Its 3 near-miss commits are all the true sentence. It passes `near_miss` with `Y` = 0 of `m` = 36.

**Truncated: mostly prefixes, one fail.** Most commits on truncated inputs are proper word prefixes of the truth, which the signal supports. With many real commits, the T15 M4-13 systems pass the 25 % and 50 % levels. T12 `p14-03-guard` fails `truncated_50`: 12 of its 31 commits are not prefixes (10 of them on items where the real track does not commit). At 75 % (no rule), full-sentence commits appear (`B0` 14, `B1` 7). This agrees with the plan's reason for no rule: some speech ends before 75 % of the frames.

**Noise mix: almost no commits.** At λ = 0.25 and above, the guards abstain on nearly every item. So the noise-mix levels pass for every system that has enough real commits, and they separate no systems.

**Cross-reference (a fact from the committed cards).** M4-13 `B1_rescore_G` and `B1_rescore_G@single` also pass the protocol 0.2 controls (`benchmark/results/halluc-v0.2/`). They are the only baselines that pass both the four protocol 0.2 tracks and the three signal-check tracks.

> **Post-hoc (not pre-registered):** The noise-mix levels are too strong to be informative for these guards. λ = 0.25 already removes all commits. Weaker levels (for example λ = 0.05 and 0.10) would test whether a guard commits wrong text on a mildly degraded signal. They need a new pre-registration and a protocol version bump. They must not change this card.

> **Post-hoc (not pre-registered):** T15 M4-12 `p14-03-guard` commits more often on degraded inputs than on real inputs: 2 real commits, but 17 on `truncated_25` and 6 on `noise_mix_25` (3 wrong). The plan's diagnostic "the commit rate should not rise with λ" holds between the noise levels (6, 0, 0), but not against the real track (λ = 0). The numbers are small (IE), but the direction is wrong for a guard.

> **Post-hoc (not pre-registered):** `A0_ngram` commits more on truncated inputs (152, 192) than on real inputs (104). Most of these are short proper prefixes. Short texts seem easier to commit for this guard. This is allowed by the rule (prefixes are supported), but a user who reads a prefix as a full sentence gets wrong text.

> **Our take:** The near-miss track does what the plan wanted: it separates the grounded guard from the others on the same decoder input, with a clear margin (0 against 60 or 104 unsupported commits). The truncated track adds a small signal. The noise-mix track, at these levels, adds none.

## Gap 232 done-when
"The three tracks exist with fixed seeds and docs, and the 10 shipped systems are scored on them (or a system is reported as stopped by check 1)." **Met.** The tracks and docs are in commit 01ff0ff. All 10 systems are scored in both fluency modes. No system was stopped.
