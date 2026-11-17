---
title: P15-02 update hooks and ledger records - replay smoke test
type: experiment
task: P15-02
updated: 2026-11-16
---

# P15-02: update hooks in the trust layer and a ledger record per update (smoke test)

Roadmap: [P15-02](../../wiki/questions/roadmap-standard.md#p15-02-decoder-update-loop-and-re-calibration-hooks). Code: [`src/fidetype/trust/update_hooks.py`](../../src/fidetype/trust/update_hooks.py), [`adaptive.py`](../../src/fidetype/trust/adaptive.py) (`ledger=`, `add_listener`, `reject_proposal`), [`provenance.py`](../../src/fidetype/trust/provenance.py) (entry kind `update`), [`online_risk.py`](../../src/fidetype/trust/online_risk.py) (`swap_policy`, `commit_floor`). Script: [smoke.py](smoke.py). Aggregates: [results/smoke.json](results/smoke.json). Docs: [quickstart section](../../docs/trust-quickstart.md#later-update-the-decoder-safely-p15-02).

## What was built
| Part | Behaviour |
|---|---|
| `TrustGuardUpdater` | Runs `GuardedUpdateLoop` for a candidate `TrustGuard`: block LTT on a fresh check block, uniform + shuffled null controls through the commit gate, sign test against the live guard. Accepted: the candidate config goes into the same guard object, `commit_p = max(candidate, session threshold)`. Rejected (also a failed `calibrate`): the guard does not change |
| `OnlinePolicyUpdater` | On an accepted update: `OnlineTrustPolicy.swap_policy(...)` and `commit_floor` = session threshold. The ACI controller keeps its state. Rejected: no change |
| Ledger `update` entries | Every proposal and decision: stage `proposed` / `accepted` / `rejected`, link to the proposal by hash, `parent_config_id` -> `config_id` chain. `verify` checks the rules. No text, ids hashed |

## Smoke test (T12 pilot records, read only)
Input: the per-trial records of the [P15-01 pilot](../2026-11-16-f1-e2-selfimprove-pilot/results.md) (frozen and feedback-p0.9 arms, 16 T12 days). No decoder runs. Live guard: n-best `calibrate` on the frozen arm, days S08-S10 (837 items). Each day S11-S23: a candidate calibrated on the feedback arm's previous day, checked on the 48 phase-B items, then the live guard decides phase C.

| Check | Result |
|---|---|
| Proposals / accepted / rejected | 15 / 13 / 2 |
| Every proposal has a decision | yes |
| Ledger `verify` (31 entries, with head anchor) | pass |
| Guard config changed on each accept | yes (13 of 13) |
| Negative control (a): candidate whose decoder commits on null input, via `propose_calibration` | rejected (`NullControlError`, shuffled 18/60 > 3); guard unchanged |
| Negative control (b): same failure, candidate built with quiet nulls, then checked by the loop | rejected (`null controls failed (shuffled 27/60 > 3)`); guard unchanged |
| Null controls of the 13 accepted updates | 0/60 uniform, 0/60 shuffled in each |
| Phase-C commits of the live guard | 0 of 4,432 items |

Run time 110 s on CPU (background class, 4 threads).

## Limits
- This is a plumbing test, not an evaluation. Stand-ins: n-best scores come from the top-1 posterior only; the null input is near-flat random scores; unknown truth is skipped in calibration and counts as wrong in the check block.
- The pilot decoder is weak (top-1 exact near 0). Both decoders are wrong on every check item, so the sign test never has a discordant pair and no candidate is rejected as worse on real data. The "worse challenger" path is covered by unit tests only (`tests/test_trust_update_hooks.py`).
- The guard never commits in phase C, so the smoke says nothing about the commit rate or precision after an update.

> **Our take:** the hooks and the ledger work end to end on real recorded outputs. The useful test of the gate (a better decoder that commits, with discordant check items) needs P15-03 (stronger decoder, GPU).
