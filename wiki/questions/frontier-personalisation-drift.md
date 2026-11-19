---
title: "Frontier write-up: per-user trust, drift detection and gated re-calibration (P5-01, P5-09, P5-10, P5-11)"
type: question
tags: [frontier, f1, personalisation, drift, conformal-test, recalibration, t12, write-up, negative-result, pre-registration]
sources: []
updated: 2026-11-18
---

# Personalisation and drift: can the trust layer notice that a user's data changed, and re-calibrate only then?

Write-up for roadmap item [P15-12](roadmap-standard.md#p15-12-frontier-result-write-ups). It joins P5-01 (profiles, drift tests, gated re-calibration), P5-09 (spread bets), P5-10 (guard-risk test in `PersonalTrust`) and P5-11 (online guards through the drop-in API; written up in the [F1 online guarantees page](frontier-f1-online-guarantees.md#p5-11-the-same-controllers-through-the-drop-in-api)). It supports F1: a self-improving BCI must also know when its calibration is stale.

## Question
Do the conformal drift tests keep their false-alarm level? Do they find real drift on T12? Does drift-triggered re-calibration cost fewer labels than daily re-calibration, at the same safety?

## Short answer
- **The drift tests keep their level** on synthetic data and on T12 with the day order destroyed (P5-01 S1, R2; P5-09 S1, S4).
- **On T12 the decoder confidence `p_top1` does not drift, but the guard risk does.** A test on the guard risk alarms 4 times in 16 days.
- **Drift-triggered re-calibration halves the label cost** of daily re-calibration (384 vs 768 labels) at the same commits and wrong-commit rate.
- **This decoder cannot show usefulness:** top-1 is right on 2 of 6,720 items, so every commit is wrong.
- **Negative results:** the P5-01 score test never detects a spread change (200 / 200 missed); the P5-09 fix costs power on small mean shifts (S3 fail).

## Pre-registration and design
| step | plan | design | page |
|---|---|---|---|
| P5-01 | [plan](../../experiments/2026-11-16-p5-01-personal/plan.md), `bec214c` (with the code) | synthetic sweep (false alarms, detection delay) + T12 replay (16 days, 6,720 items, frozen pilot decoder) with arms A0 static, A1 daily, A2 drift (`p_top1` + risk), A2g drift + guard risk | [results](../../experiments/2026-11-16-p5-01-personal/results.md) |
| P5-09 | [plan](../../experiments/2026-11-16-p5-09-drift-spread/plan.md), `3def17e` | `ConformalDriftTest(spread=True)` vs default, paired streams | [results](../../experiments/2026-11-16-p5-09-drift-spread/results.md) |
| P5-10 | [plan](../../experiments/2026-11-16-p5-01-personal/plan-p5-10.md), `3def17e` | `PersonalTrust(guard_risk_test=True)` on the P5-01 replay | [results section](../../experiments/2026-11-16-p5-01-personal/results.md#p5-10-guard-risk-test-through-personaltrust-2026-11-16) |

## Verdicts

**P5-01**

| id | criterion | result |
|---|---|---|
| S1 | synthetic false-alarm rate <= level + 3 SE | **pass** (score test 0.011 at 0.01, 0.048 at 0.05; risk test 0.004, 0.038) |
| R1 | A2 wrong-commit rate <= 0.05 | **pass** (0 / 6,720; A2 never commits) |
| R2 | permutation null alarm rate <= 0.096 | **pass** (scores 0.040; risk 0.000, trivial) |
| R3 | A2 check-block labels < A1 (768) | **pass** (A2 96, A2g 384) |
| R4 | A2 days above alpha <= A0 | **pass** (0 vs 0) |
| R5 | no threshold change outside `finish_update` or a tightening | **pass** |

| arm | commits / wrong | wrong-commit rate [CP95] | check-block labels | offer-only items |
|---|---|---|---|---|
| A0 static | 0 / 0 | 0 [0, 0.0005] | 96 | 118 |
| A1 daily | 15 / 15 | 0.0022 [0.0012, 0.0037] | 768 | 932 |
| A2 drift (`p_top1` + risk) | 0 / 0 | 0 | 96 | 118 |
| A2g drift + guard risk | 15 / 15 | 0.0022 [0.0012, 0.0037] | **384** | 118 |

**P5-09 (spread bets)**

| id | criterion | result |
|---|---|---|
| S1 | false-alarm rate <= level + 3 SE | **pass** (0.007 at 0.01; 0.040 at 0.05) |
| S2 | detect sd 1 → 2 (>= 95 %) and sd 1 → 0.5 (>= 90 %) | **pass** (200 / 200 and 200 / 200; default test: 4 / 200 and 5 / 200) |
| S3 | mean-shift cost: delay ratio <= 1.25; detected share at −0.25 sd >= default − 0.10 | **FAIL** (one part): ratios 1.16 and 1.14 pass; at −0.25 sd 0.445 vs 0.61 |
| S4 | T12 permutation null alarm rate <= 0.096 | **pass** (`p_top1` 0.045, guard risk 0.030) |

**P5-10:** P10-1 to P10-3 **pass**. The guard-risk alarms through `PersonalTrust` are the A2g alarms, item for item (697, 1,794, 2,159, 6,647). With `spread=True` the guard-risk test alarms only 2 times: on T12 the drift is mainly a shift of the centre.

## Negative results, stated plainly
- Every commit in the T12 replay is wrong (top-1 right on 2 of 6,720 items). The safety numbers test validity and plumbing, not a typing gain.
- The default score test misses every spread change at the same centre.
- Spread bets lose power on small mean shifts (−0.25 sd: 0.445 vs 0.61 detected).
- The replay used conservative proxies for the shuffled null control, because the pilot stored no per-item null outputs (gap 13).
- Silent errors are not covered: the risk test sees only corrected commits.

## What changed in the library
| change | commit |
|---|---|
| `fidetype.trust.drift` (`ConformalDriftTest`, risk test), `fidetype.trust.personal` (`PersonalTrust`), user guide [docs/trust-personalisation.md](../../docs/trust-personalisation.md) | `bec214c` |
| opt-in `spread=True` (default unchanged) | `3def17e` |
| opt-in `PersonalTrust(guard_risk_test=True)` (default unchanged) | `3def17e` |
| `PersonalTrust` re-calibrations always give champion outputs (P15-23); same-decoder re-calibration rule (P15-24; R1-R7 pass, 0 of 8 re-calibrations refused, [results](../../experiments/2026-11-18-p15-24-recal-rule/results.md)) | `0254ebc` |

## Limits
- One frozen, weak decoder; one participant (T12); one seed for the replay.
- The drift tests watch the score and the observed loss, not the truth of withheld items.
- No decoder update happens in this replay; it changes only the guard calibration.

> **Our take:** drift detection is a cheap way to keep a guard current: half the labels of daily re-calibration with the same safety. On T12 the right signal to watch is the guard risk, not the confidence. Usefulness needs the same replay on a stronger decoder (P5-01 on M4-13, gap 14).

## Still open
| gap | item | what |
|---|---|---|
| 14 | [P15-19](roadmap-standard.md#p15-19-show-usefulness-on-stronger-decoders-p5-01-p15-02-p5-02-p15-06) | P5-01 on M4-13 and the P11 decoders |
| 19 | [P5-12](roadmap-standard.md#p5-12-spread-aware-drift-test-without-the-small-shift-cost) | spread-aware drift test without the small-shift cost |
| 13 | [P15-18](roadmap-standard.md#p15-18-pilots-store-per-item-null-control-outputs) | per-item null-control outputs in pilots |

## Rerun
`experiments/2026-11-16-p5-01-personal/synth.py` (CPU, about 67 s; no data needed), `replay.py`, `replay_p5_10.py` (need the local P15-01 per-trial records), `experiments/2026-11-16-p5-09-drift-spread/synth.py`.

## Related pages
[Trust personalisation](../concepts/trust-personalisation.md), [per-session risk control](per-session-risk-control.md), [E2 self-teaching write-up](frontier-e2-self-teaching.md), [F1 online guarantees write-up](frontier-f1-online-guarantees.md), [north star](north-star.md).
