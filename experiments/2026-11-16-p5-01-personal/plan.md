---
title: P5-01 personalisation - drift detection and gated re-calibration - plan
type: experiment
task: P5-01
updated: 2026-11-16
---

# P5-01: per-user profiles, drift detection, gated re-calibration (plan)

Written and committed **before** any synthetic sweep or replay run. Code: `src/fidetype/trust/drift.py` and `src/fidetype/trust/personal.py` (new), tests `tests/test_trust_personal.py`. Roadmap item: [P5 deliverable 1](../../wiki/questions/roadmap-standard.md#p5-trust-layer-to-product-grade).

## Questions
1. Do the two drift tests keep their false-alarm level (anytime valid) on synthetic data, and how long is the detection delay for changes of a given size?
2. On a real multi-day replay (T12, 16 days, frozen decoder): what does drift-triggered re-calibration through the gated loop give, compared with no re-calibration and with daily re-calibration? Does the wrong-commit rate stay at or below alpha? How many labelled items does it spend? Do the tests give false alarms when the day order is destroyed?

## Methods (fixed now)
- **Score test**: `ConformalDriftTest` (smoothed conformal p-values against reference + all earlier live scores; Simple Jumper betting martingale, eps in {-1, 0, 1}, jump J = 0.01; Vovk, Nouretdinov, Gammerman 2003; Vovk 2021; Vovk et al. 2021 COPA). Alarm when the capital reaches 1 / level (Ville).
- **Risk test**: `RiskDriftTest` on the per-item observed loss L = 1 (wrong commit seen by the user) else 0; H0 `E[L_t | past] <= alpha`; betting e-process (Waudby-Smith and Ramdas 2024) with bets c / alpha, c in {0, 0.025, 0.05, 0.1, 0.2, 0.4}, same jump rule.

## Part S: synthetic sweep (script `synth.py`, seed 20261116)
- S-FA (false alarms): score test, reference 200 and 2,000 live N(0, 1) scores; risk test, 2,000 Bernoulli(alpha = 0.05) losses (the boundary of H0). Levels 0.01 and 0.05; 1,000 runs per cell.
- S-DELAY (delay): level 0.01. Score test: reference 200, 500 null live items, then a mean shift of 0.25, 0.5, 1.0 (sd units, down) and a scale change (sd 2); at most 5,000 items after the change. Risk test: 300 items at rate 0.02, then rate 0.10, 0.20, 0.50; at most 5,000 items after. 200 runs per cell. Report median, 90th percentile and the share never detected.
- **Pass rules**: S1: every false-alarm rate <= level + 3 SE (binomial SE at the level). S2 (descriptive, no pass rule): the delay table.

## Part R: T12 replay (script `replay.py`)
### Data (read only, no new decoding)
- Decoded outputs of the F1 / E2 pilot, `frozen` arm (one fixed decoder for all days): `C:/Users/zhang/bci-data/derived/f1-e2-pilot/replay/frozen/records-S08.pkl` ... `S23.pkl` (16 days, 6,720 items, record order). Fields used: `id`, `score` (= `p_top1`, -inf without text), `text_ok`, `right`, `truth_known`. No text field is read.
- Guard risk per item (needed by the evidence gate): the P15-02 gated re-run of the same arm, `C:/Users/zhang/bci-data/derived/f1-e2-pilot-gated/replay/frozen/records-S*.pkl` (same items, same scores). The script checks that ids and scores match item by item and stops if not.
- Per-day null-control results of this decoder: `experiments/2026-11-16-f1-e2-selfimprove-pilot/results/rerun-gated/arms/frozen.json` (committed aggregates: `lambda_session`, `null_raw`, `uniform_guard_risk_min`).
- Outputs: `C:/Users/zhang/bci-data/derived/p5-01-personal/` (per-item decisions). The repository gets aggregates only (`results/*.json`, `results.md`).

### Fixed settings
alpha 0.05, delta 0.1, check block n = 48 labelled items (as in the pilot), loop defaults otherwise (`GuardedUpdateLoop`: evidence gate `CommitGate(min_chars=1, max_guard_risk=1.0)`, eta 0.05, gamma 0.1, null rule floor(alpha * n)). Drift levels: score 0.005, risk 0.005 (library defaults, total 0.01), jump 0.01, two-sided score test. Simulated user: every commit is seen (q_notice 1.0), so the observed loss of a commit = 1 - `right`. An item is a label for a check block only if `truth_known`.

### Null controls in the replay (proxies, conservative)
The pilot stored no per-item null outputs, and this replay does no new decoding. Each proposal therefore gets these proxy null inputs (20 + 20):
- **uniform**: 20 items with score 1.0 and the measured uniform guard risk of the day (`uniform_guard_risk_min`; 1.0 on every day in P15-02). The evidence gate must refuse them.
- **shuffled**: P15-02 counted k_d commits of 20 frame-shuffled inputs on day d at threshold lambda_d. If the proposed threshold is >= lambda_d of every day the check block covers, the proxy has k = max k_d items that commit at any threshold (an upper bound, by monotonicity in the threshold) and 20 - k items that never commit. If the proposed threshold is lower than lambda_d, the outcome is unknown: all 20 proxy items commit (the control fails).
- This is a replay limitation: the proxies use measured outcomes of the same decoder, not new null decodes. It is stated in the results.

### Arms
| Arm | Re-calibration rule |
|---|---|
| A0 static | Check block = first 48 labelled items of S08 (offer-only while collecting). No later re-calibration (one loop session for all days). |
| A0 rule for a rejected first block | If the first block of A0, A2 or A2g is rejected, the arm stays offer-only and the next 48 labelled items form a new block, until one is accepted. |
| A1 daily | Each day: new loop session; check block = first 48 labelled items of the day (offer-only while collecting). The P15-02 schedule. |
| A2 drift | Start as A0. Then the score test (on `p_top1`, reference = the scores of the 48 check-block items) and the risk test run on every item. Score alarm: propose (keep the current threshold while the next 48 labelled items are collected). Risk alarm: tighten at once (offer-only) and propose. A proposal = new loop session + new version + the 48 new labelled items as the check block + proxy null controls + `finish_update`. Accepted: new threshold, tests restart with the new check-block scores as reference. Rejected: the champion is re-checked on the same block with the same proxies; the proposal stays open and collects the next 48 labelled items. |
| A2g drift + guard risk | As A2, plus a second conformal test on the guard risk of each item (levels: p_top1 0.0025, guard risk 0.0025, risk 0.005; total 0.01). A guard-risk alarm proposes. |

Decisions: `GuardedUpdateLoop.decide(score, text=<placeholder if text_ok>, guard_risk=...)`, `observe(decision, loss)`. A threshold changes only through `finish_update` (no direct writes).

### Permutation null (real data, no drift by construction)
200 random permutations (seeds 0..199) of all 6,720 items. Score test on `p_top1` at level 0.05: reference = first 48 items of the permuted stream, test on the rest. Risk test at level 0.05 on the A0-rule losses of the permuted stream (commit iff score >= the A0 threshold and the gate passes; loss = commit and not right), H0 true if the pooled rate is <= alpha (reported).

### Metrics (per arm)
Commits, wrong commits, wrong-commit rate over all items with CP95, per-day rates, days with rate > alpha, labelled items spent on check blocks, proposals / accepted / rejected, alarms (test, item index, day), share of offer-only items.

### Pre-registered criteria
- **R1** (validity): A2 overall wrong-commit rate <= alpha (point estimate; CP95 reported).
- **R2** (real-data false alarms): in the permutation null, the alarm rate of each test <= 0.05 + 3 SE (SE at 0.05 with 200 runs: 0.0154).
- **R3** (label cost): A2 spends fewer check-block labels than A1 (A1: 16 x 48 = 768).
- **R4** (safety vs static): A2 days with rate > alpha <= A0 days with rate > alpha.
- **R5** (no bypass): in A2 / A2g, every change of the commit threshold comes from an accepted `finish_update` or a tightening (audit count check).
- Descriptive: where the alarms fall; A2g vs A2.

### Expected (written before the runs)
The frozen decoder is weak (top-1 right 2 of 6,720 items). Every commit is wrong, so the wrong-commit rate is the commit rate. P15-02 measured a daily commit rate of about 1 %, so R1 should pass and the risk test should not alarm. The guard risk falls over the days (share of items below 1.0: 0.85 on S8, 0.34 on S23; a look at the data while writing this plan), so A2g may alarm and A2 may not. The replay tests the plumbing and validity on real non-stationary data; it cannot show a usefulness gain with this decoder.

## Rules
CPU only, RAM < 1.5 GB, run via `python -m fidetype.utils.isolation run --class background --threads 4`. No other experiment folder is changed. A change to this plan after a run is written as a dated amendment below, never in place.
