---
title: P5-42 - a multi-user safety check and a per-user bound in calibrate - results
type: experiment-results
task: P5-42 (gap 221)
plan: plan.md (ad51861)
updated: 2026-11-25
---

# P5-42: multi-user check and per-user bound in `calibrate`: results

**Short answer.** `calibrate` now takes `users=` (opt-in, code `41e050b`). The user check catches the pure B1-type leak in 20 of 20 synthetic runs and passes real within-user signal in 19 of 20. The per-user bound keeps every user at or below alpha in 20 of 20 runs, where the pooled guard lets one user exceed alpha in 13 of 20. One pre-registered rule **fails**: case C (within-user signal plus large base-rate differences) gets the verdict `fail` in 8 of 20 runs (the rule allows at most 2). On the three emg2qwerty guards the check says `partial` for all three (E-S, E-SL and also E-LFL). The per-user bound `"each"` is certified for all three, but it commits only 2-8 of 1,221 test prompts (0 wrong); `"all"` is refused (too few items per user). No shipped guard or card changed.

## Run record
| item | value |
|---|---|
| plan | `ad51861` (committed alone, before any code) |
| code | `41e050b` (`src/fidetype/trust/user_check.py`, `dropin.py`, `tests/test_trust_user_check.py`, `synth.py`, `run_e2q.py`); full suite 2,003 passed, 46 skipped |
| library for the runs | clean copy of `src/` at `41e050b` (`derived/p5-42/src-41e050b`) |
| compute | CPU only, 1 thread per process, at most 3 processes; synthetic 17.7 min (2 workers), emg2qwerty 12.4 min (1 process); no GPU; `derived/p15-50` not touched |
| data written | `C:/Users/zhang/bci-data/derived/p5-42/` only; the repo gets `results/synth.json` (synthetic data) and `results/e2q.json` (aggregates only: no per-user value, no text, no id) |
| disclosure | before the registered run, one smoke run per case on seed 101 (not a registered seed) was seen. In it case C had the verdict `fail`. No rule, threshold or code changed after it |

## Design (as built)
| option | default | what it does |
|---|---|---|
| `users=` | `None` | one user (or session) id per input; no change of the split; not `groups=` |
| `user_check=` | `"warn"` | label null on the LTT items, score level: labels permuted inside each user (NW) and over the pool (NP), 200 runs each, the same LTT step. `fail`: `p_user > 0.05` (real certificate not above NW). `partial`: one-sided MWU `p_leak < 0.01` (NW > NP). `"refuse"` raises `NullControlError` on `fail` |
| `user_bound=` | `"pooled"` | `"each"` / `"all"`: per-user LTT on each user's LTT items at delta or delta / K; final threshold = max(pooled, user thresholds); enters `config_id` only then |

Opt-in rules O1-O3 (unit tests): **pass**. The three reference `config_id` values of `83da5d1` are unchanged, `users=None` gives the same guard file, `users=` with `"pooled"` gives the same `config_id`, threshold and decisions, and the `groups=` tests pass unchanged.

## Synthetic validation (4 users x 300 items, 20 runs per case)
| case | data | result | rule | verdict |
|---|---|---|---|---|
| A: pure base-rate leak | margin from the user only | `k_real >= 1` in 20 / 20; `fail` in 20 / 20 (median NW commits = real commits in 17 runs) | validity >= 15; `fail` >= 90 % | **pass** |
| B: within-user signal, no user effect | right with probability z, margin from z | `pass` 19, `fail` 1 | `pass` >= 18 | **pass** |
| C: signal + base-rate difference | user mean of z 0.35 - 0.9 | `partial` 12, `fail` 8 | not `fail` >= 18 | **FAIL** |
| D: one overconfident user | as B, one user right with probability 0.6 z | pooled guard: that user > alpha on 3,000 test items per user in 13 / 20; `"all"`: all users <= alpha + 0.01 in 20 / 20 (0 refused); test commits median 1,711 (pooled) vs 141.5 (`"all"`) | validity >= 10; rule >= 16 | **pass** |

How to read the failures of the `fail` verdict:
- **Case C.** In the 8 `fail` runs the real certificate is above the NW median (for example 127 vs 102), but not above the NW runs in 95 % of cases (p_user 0.12-0.96). Most certified commits come from the users with a high rate of right texts; labels with only each user's base rate certify almost as many. So the verdict is correct by its definition ("the certificate is not larger than what each user's base rate alone gives"), but the pre-registered expectation was wrong. In `"refuse"` mode such a guard would be refused although it has within-user signal.
- **Case B (1 run) and case D (7 runs; not a rule).** These are weak certificates (17-44 commits) where NW **and** NP certify about as many commits (NW and NP medians equal, and at or near the real count). The certificate is label-blind, not user-driven: the top-score items commit under any labels, which the guarantee allows (it bounds wrong commits over all items). The verdict `fail` does not separate "user" from "no signal" (stated in the plan limits and in the docs).

> **Our take:** the check does what B1 needs (A: 20 / 20), and `partial` is the right word for C. A follow-up should split `fail` into "user" (NW > NP) and "label-blind" (NP also reaches the real count), and perhaps add a within-user association test before `"refuse"` is advised. Until then, `"warn"` (the default) is the safe use.

## emg2qwerty: the three pooled-guard-check arms (calibration data as there, 8 users, 459 LTT items)
| guard | E0: `config_id`, LTT commits / wrong | E1 verdict | real commits | NW / NP median (max) | p_user | p_leak | pooled-guard check, full recipe: NW / NP median, MWU p |
|---|---|---|---|---|---|---|---|
| E-S | same (71 / 16) | **partial** | 71 | 25 / 18 (38 / 31) | 0.005 | 2e-46 | 23 / 18, 0.0086 |
| E-SL | same (80 / 16) | **partial** | 80 | 29 / 19 (45 / 32) | 0.005 | 7e-61 | 25.5 / 20.5, 0.0028 |
| E-LFL | same (108 / 16) | **partial** | 108 | 28 / 20 (35 / 28) | 0.005 | 8e-46 | 0 / 0, 0.14 |

- **E0: pass** (all three `config_id` values, thresholds and LTT counts equal the pooled-guard check's reproduction).
- **E1.** E-S and E-SL: `partial`, as expected and as the full-recipe nulls found (F1). E-LFL: `partial`, **not** the expected `pass`. The difference is method: the full-recipe null refits the learned confidence on permuted labels (it then certifies almost nothing), while the score-level null keeps the fitted score. That score carries the user (it uses the key rate, and the personal decoders), so NW > NP. No arm is `fail`: every real certificate is far above all 200 NW runs.

| guard | pooled guard on test (1,221): commits / wrong; users > alpha (point); users CP upper > 2 alpha | `"each"`: threshold (pooled), LTT commits, test commits / wrong; users > alpha; CP upper > 2 alpha | `"all"` |
|---|---|---|---|
| E-S | 167 / 35; 1; 1 | 0.83 (0.55), 0, 2 / 0; 0; 0 | refused: needs 86 LTT items per user, every user has fewer |
| E-SL | 194 / 31; 2; 2 | 0.94 (0.61), 2, 8 / 0; 0; 0 | refused (same) |
| E-LFL | 285 / 52; 1; 1 | 0.98 (0.63), 5, 8 / 0; 0; 0 | refused (same) |

- **E2.** The per-user bound removes the per-user exceedance (F2), but at a large cost: 2-8 commits instead of 167-285. About 57 LTT items per user on average (459 / 8) give a strict per-user LTT (it must see almost no wrong commit in each user). `"all"` needs 86 per user and is refused, as expected. (The pooled-guard check's results table gives "1 of 8" for E-SL; its `summary.json` and this run give 2.)

## Done-when of gap 221
| part | status |
|---|---|
| `calibrate` takes user groups | yes (`users=`) |
| (a) NW-vs-NP null; warns or refuses when NW certifies more than NP | yes: `partial` warns; `fail` warns or refuses (`user_check="refuse"`) |
| (b) per-user target or per-user / stratified LTT when each user has enough items | yes: `user_bound="each"` / `"all"`, `ValueError` with too few items |
| tests cover a synthetic B1-type leak | yes (`test_b1_type_leak_is_flagged`, `..._refused_in_refuse_mode`) |
| docs/trust-guarantee.md states the scope | yes, section 10d |

The done-when is met. One pre-registered synthetic rule (C) failed; it shows a limit of the `fail` verdict, not a fault of the bound.

## Caveats
- Score-level null: the temperatures and the learned scores are not refitted on permuted labels (E-LFL shows that this can change the answer).
- Synthetic data are n-best lists from one generator; 4 users.
- emg2qwerty: 8 users, one calibration split (seed 0), track-test only; per-user values are not reported (research-only data).
- p_user has a floor of 1 / 201 = 0.005 (200 runs).

## Files
- `results/synth.json`: all synthetic runs and rule results.
- `results/e2q.json`: emg2qwerty aggregates (no per-user value).
- Local only: `C:/Users/zhang/bci-data/derived/p5-42/` (per-arm records with per-user tables, logs, library copy).
