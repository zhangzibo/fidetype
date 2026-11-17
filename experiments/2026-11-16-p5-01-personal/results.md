---
title: P5-01 personalisation - drift detection and gated re-calibration - results
type: experiment
task: P5-01
updated: 2026-11-16
---

# P5-01: per-user profiles, drift detection, gated re-calibration (results)

Plan (pre-registered, committed before any run): [plan.md](plan.md), commit `bec214c`. Code in the same commit: `src/fidetype/trust/drift.py`, `src/fidetype/trust/personal.py`, tests `tests/test_trust_personal.py` (17 tests). Numbers: [results/synth.json](results/synth.json), [results/replay.json](results/replay.json), [results/permutation.json](results/permutation.json). Per-item decisions only in `C:\Users\zhang\bci-data\derived\p5-01-personal\` (not in the repo). User guide: [docs/trust-personalisation.md](../../docs/trust-personalisation.md). CPU only: synthetic sweep 67 s, replay 19 s.

## Outcome

| id | criterion | result |
|---|---|---|
| **S1** | synthetic false-alarm rate <= level + 3 SE, both tests, levels 0.01 and 0.05 | **pass** (table below) |
| **R1** | A2 wrong-commit rate <= alpha 0.05 | **pass**: 0 / 6,720 (A2 never commits; see below) |
| **R2** | permutation null: alarm rate <= 0.05 + 3 SE (0.096), both tests | **pass**: scores 0.040, risk 0.000 (the risk part is trivial: 0 commits at the A0 threshold) |
| **R3** | A2 check-block labels < A1 (768) | **pass**: 96 (A2), 384 (A2g) |
| **R4** | A2 days with rate > alpha <= A0 days | **pass**: 0 vs 0 |
| **R5** | no threshold change outside `finish_update` or a tightening | **pass**: 0 changes outside, A2 and A2g |

Short version:
- **The drift tests keep their level.** Synthetic false-alarm rates are at or below the level (0.011 at 0.01; 0.048 at 0.05 for the score test). On real T12 data with the day order destroyed, the score test alarms in 4.0 % of 200 permutations at level 0.05.
- **`p_top1` of the frozen T12 decoder does not drift** over 16 days (median 0.118 to 0.120 each day). The score test on `p_top1` never alarms (A2 = A0). **The guard risk drifts strongly** (share of items below the gate limit: 0.85 on S8, 0.34 on S23). A conformal test on the guard risk (A2g) alarms 4 times (S9, S12, S13, S23).
- **Drift-triggered re-calibration halves the label cost of daily re-calibration** at the same commits and the same wrong-commit rate: A2g 384 labels, 15 commits, rate 0.0022 [CP95 0.0012, 0.0037]; A1 768 labels, 15 commits, same rate. A2g also has fewer offer-only items (118 vs 932): it keeps the live threshold while it collects a check block.
- **This decoder cannot show usefulness.** Top-1 is right on 2 of 6,720 items, so every commit is wrong. All numbers here test validity and plumbing, not a gain in typing.
- **A known gap of the score test:** it does not see a change of spread at the same centre (scale change sd 1 -> 2: never detected in 200 runs). See open issues.

## Part S: synthetic sweep

False alarms (1,000 runs each; score test: reference 200, 2,000 live N(0, 1) items; risk test: 2,000 Bernoulli(0.05) losses, the boundary of H0):

| test | level | false-alarm rate | limit (level + 3 SE) |
|---|---|---|---|
| scores | 0.01 | 0.011 | 0.0194 |
| risk | 0.01 | 0.004 | 0.0194 |
| scores | 0.05 | 0.048 | 0.0707 |
| risk | 0.05 | 0.038 | 0.0707 |

Detection delay at level 0.01 (200 runs each; items after the change; at most 5,000):

| change | median | 90th percentile | never detected |
|---|---|---|---|
| score mean -0.25 sd | 536 | > 5,000 | 63 / 200 |
| score mean -0.5 sd | 99 | 164 | 0 / 200 |
| score mean -1.0 sd | 46 | 58 | 0 / 200 |
| score sd 1 -> 2 (same mean) | never | never | 200 / 200 |
| loss rate 0.02 -> 0.10 (alpha 0.05) | 492 | 894 | 0 / 200 |
| loss rate 0.02 -> 0.20 | 84 | 136 | 0 / 200 |
| loss rate 0.02 -> 0.50 | 16 | 24 | 0 / 200 |

The score test gets 500 null items before the change, so these delays include the cost of a long quiet period (the Simple Jumper keeps a part of the capital ready).

## Part R: T12 replay (16 days, 6,720 items, 5,390 labelled, frozen decoder)

| arm | commits | wrong | wrong-commit rate [CP95] | worst day | days > alpha | check-block labels | proposals (accepted) | offer-only items |
|---|---|---|---|---|---|---|---|---|
| A0 static | 0 | 0 | 0 [0, 0.0005] | 0 | 0 | 96 | 2 (1) | 118 |
| A1 daily | 15 | 15 | 0.0022 [0.0012, 0.0037] | 0.0091 | 0 | 768 | 16 (9) | 932 |
| A2 drift (`p_top1` + risk) | 0 | 0 | 0 [0, 0.0005] | 0 | 0 | 96 | 2 (1) | 118 |
| A2g drift + guard risk | 15 | 15 | 0.0022 [0.0012, 0.0037] | 0.0173 | 0 | 384 | 8 (5) | 118 |

What happened:
- **A0 / A2:** the first S8 block gave threshold 0.16; the shuffled null proxy failed (0.16 is below the P15-02 threshold of S8, 0.25, so the outcome is unknown and counts as a fail by the pre-registered rule). The second block gave 0.25 and passed. 0.25 is above almost every `p_top1` (90th percentile about 0.14), so these arms never commit. No drift alarm in A2: neither `p_top1` nor the observed loss changed.
- **A1:** 9 of 16 daily blocks accepted; 7 rejected by the conservative shuffled proxy (the new threshold was below the P15-02 threshold of that day). A rejected day is offer-only (932 offer-only items).
- **A2g:** guard-risk alarms at item 697 (S9), 1,794 (S12), 2,159 (S13) and 6,647 (S23). Each alarm proposed a re-calibration; 4 of 6 proposals passed. The risk test never alarmed (observed loss rate far below alpha), so the guard was never tightened.
- The loop's own session monitor (gamma 0.1) never alarmed.

### Null controls in the replay are proxies
The pilot stored no per-item null outputs. As pre-registered, each proposal used (a) uniform proxies at the measured uniform guard risk (1.0 on every day; the gate refuses all of them) and (b) shuffled proxies from the P15-02 per-day counts, valid only at thresholds at or above the P15-02 threshold of the day (below it: counted as a fail). This is conservative: it rejects some proposals that a real null decode might pass. It uses measured outcomes of the same decoder, not new decodes.

## Open issues
1. **Scale change.** The score test bets on the mean of the conformal p-values. A wider or narrower score spread at the same centre gives uniform-looking mean p-values and is not detected. A fix: add betting functions on `|p - 1/2|` (for example `1 + eps * (|2p - 1| - 1/2)`); the guarantee stays the same. Not done here (not pre-registered). *Update 2026-11-16: done by P5-09 ([results](../2026-11-16-p5-09-drift-spread/results.md)), opt-in.*
2. **`p_top1` is the wrong signal on T12.** The trust input that drifts is the guard risk, not the confidence. `PersonalTrust` watches only `p_top1` by default; the guard-risk test is in `drift.py` but not wired into `PersonalTrust` yet. *Update 2026-11-16: wired in by P5-10 (opt-in), see the note below.*
3. **A weak decoder.** A non-vacuous usefulness test needs a decoder with right commits (P11 / M4-13 / P5-02 reruns).
4. **Real null decodes in replays.** Store per-item null outputs in future pilots, so that replays can run the real shuffled control.
5. Silent errors are not covered (the risk test sees only corrected commits).

## P5-10: guard-risk test through PersonalTrust (2026-11-16)

Dated addendum. The numbers above stay as they were. [Plan](plan-p5-10.md) (committed in `3def17e` before the run). Script: [replay_p5_10.py](replay_p5_10.py) (CPU, 1.4 s). Numbers: [results/replay-p5-10.json](results/replay-p5-10.json). Code: `PersonalTrust(guard_risk_test=True)` (opt-in; default unchanged; [docs](../../docs/trust-personalisation.md) section 4.1).

| id | criterion | result |
|---|---|---|
| **P10-1** | the four P5-01 arms, run again with the unchanged code, give identical numbers and alarms | **pass**: A0, A1, A2, A2g identical to `results/replay.json` |
| **P10-2** | the guard-risk alarms through `PersonalTrust` are the A2g alarms, each with a `drift_alarm` history entry | **pass**: items 697 (S9), 1,794 (S12), 2,159 (S13), 6,647 (S23); 4 entries, test `guard_risk`, action `propose` |
| **P10-3** | default `PersonalTrust` alarms as A2 | **pass**: no alarm (as A2) |

New arms (same 6,602 items that the P5-01 arms fed to their drift tests; a new controller per segment, with the reference block, seed and levels of the P5-01 arm):

| arm | `PersonalTrust` settings | segments | alarms (test, item, day) |
|---|---|---|---|
| A2p | `guard_risk_test=True`, levels 0.0025 / 0.005 / 0.0025 | 8 (A2g) | guard risk: 697 S9, 1,794 S12, 2,159 S13, 6,647 S23 |
| A2d | default (0.005 / 0.005) | 2 (A2) | none |
| A2ps (report only) | default + `spread=True` | 2 (A2) | none |
| A2gs (report only) | A2p + `spread=True` | 8 (A2g) | guard risk: 1,799 S12, 2,157 S13 |

What this shows and does not show:
- The alarm path through `PersonalTrust` (decide -> guard-risk test -> alarm -> history entry -> open proposal) gives the same alarms as the P5-01 research arm, item for item.
- The guard is a stub that replays the recorded decisions: this replay has no decoder inputs, so `PersonalTrust` cannot re-calibrate here. Each segment starts where the P5-01 arm accepted an update. The re-calibration path of `PersonalTrust` is covered by the unit tests (P5-01) only.
- With `spread=True` (P5-09) the guard-risk test loses two of four alarms on T12: here the drift is a shift of the centre, and the spread bets cost power on that.
- The roadmap text names `RiskDriftTest` for the guard risk. The guard risk is a per-item score, not a loss with a limit alpha, so the code uses the conformal test, as A2g did.
