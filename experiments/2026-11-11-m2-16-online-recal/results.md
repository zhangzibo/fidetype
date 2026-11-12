---
title: "M2-16: in-session re-calibration of the commit guarantee under drift"
type: experiment
updated: 2026-11-11
---

# M2-16: online re-calibration of the COMMIT threshold

Goal: keep the wrong-commit rate at α = 0.05 when the data drifts inside a session. In M2-13, offline conformal risk control (CRC), calibrated on the earlier half of each day of Brain-to-Text '25, gave **0.0625** on the later half. The guarantee of CRC needs exchangeable data, and drift breaks it.

- Code: `src/fidetype/trust/online_risk.py` (our own implementation): `OnlineCommitRiskControl`, `OnlineTrustPolicy`, `weighted_crc_threshold`. Exported from `fidetype.trust`. Tests: `tests/test_trust_online_risk.py` (20). Full CPU suite: **294 passed, 4 skipped** (it includes the parallel M2-09 tests).
- Scripts: [run.py](run.py) (CPU, 26 s), [emg_items.py](emg_items.py) (CPU, 207 s). Settings: [config.json](config.json), fixed before the first run. Tables: [results/tables.md](results/tables.md). Numbers: `results/online.json`. EMG per-trial items (scores and outcomes, no text): `results/items-emg-*.json`.
- Run: `.venv\Scripts\python.exe -I experiments/2026-11-11-m2-16-online-recal/emg_items.py`, then `... run.py`.
- Concept: [conformal risk control, "Online re-calibration under drift"](../../wiki/concepts/conformal-risk-control.md). Wiki result: [m2-16-online-recal-result](../../wiki/questions/m2-16-online-recal-result.md).

## Main finding
- **The drift case now holds.** B2T '25, our decoder, calibrate on the earlier halves, run the later halves in time order: offline CRC 0.0625 → window CRC **0.0453**, decayed CRC **0.0417**, ACI on the level (`aci_window`) **0.0478**, threshold ACI (`aci`) **0.0502** (41 wrong commits of 816; the target is 40.8). With feedback 10 trials late: 0.0417 / 0.0404 / 0.0466 / 0.0502.
- **The EMG cross-session case also broke offline CRC, and the online methods fix it.** Toronto sEMG, `xsession`: offline CRC (pure, n = 285) 0.0635 → window 0.0508, decay 0.0399, `aci` 0.0526, `aci_window` 0.0490.
- **The eWPM cost is small.** B2T ours: offline CRC 11.553 → 11.49–11.52 (−0.3 % to −0.6 %). The old gate is 11.546. Published gate: 18.80 → 18.74–18.80. EMG `calib`: the online methods give 8.07–8.08 vs the old gate 8.02 (they commit more, still ≤ 0.05).
- **Guarantees differ.** `aci` and `aci_window` have a deterministic long-run bound for *any* sequence. The run reports it (certificate). The window methods have no such bound: they are approximate.
- **Short windows are not controlled.** The maximum wrong-commit over 50-trial windows stays 0.10–0.12 for all methods. That is the same as an i.i.d. Bernoulli(0.05) sequence (median 0.120). No method can make every 50-trial window ≤ 0.05 at this commit rate.
- **Silent errors break the observed-loss guarantee.** If the controller sees only the errors that the simulated user notices, `aci` gives 0.0515 (B2T ours), 0.0635 (EMG `xsession`), 0.0581 (EMG `calib`). The certificate on the *observed* losses still holds (≤ 0.052). Silent errors must be budgeted separately.

## Feedback model
| action | what the user does | what the system learns | when |
|---|---|---|---|
| COMMIT, right | keeps the text | c = 0, only if "no correction" means right | after a timeout |
| COMMIT, wrong | deletes or corrects | c = 1 | delay d (the user must notice it) |
| COMMIT, wrong, not noticed | nothing (silent error) | looks like c = 0 | never |
| OFFER | picks a candidate or retypes | the final text is the truth: c is known; realised loss 0 | when the item ends |
| ASK | repeats the attempt | nothing new for this attempt | — |
| ABSTAIN / gives up | nothing | truth unknown; realised loss 0 | — |

- **Realised loss** (L = c if committed, else f) is known for every item. `aci` needs only this.
- **Full feedback** (c also for items that did not commit) needs the user's final text. The window methods and the window part of `aci_window` need it. Items with unknown truth are left out of the window (a selection bias).

## Methods
| name | rule | guarantee | feedback |
|---|---|---|---|
| old gate | `commit_p` from the M6-06 / M1-15 / M6-07 grid fit, fixed | none | none |
| offline CRC | CRC on the earlier data, fixed (M2-13) | E[L] ≤ α, exchangeable data only | none in session |
| offline LTT | LTT, δ = 0.1, fixed | P(R ≤ α) ≥ 0.9, exchangeable data only | none in session |
| `window` | weighted CRC on the last 200 items with known truth (offline items first) | approximate: α + B Σ w̃_i d_TV (Farinhas et al. 2024) | full |
| `decay` | weighted CRC, weights 0.99^age, no window limit | approximate, as above | full |
| `aci` | λ_{t+1} = max(0, λ_t + 0.05 (L_t − α)), start at the offline CRC λ | (1/T) Σ L_t ≤ α + (λ_{T+1} − λ_1) / (η T), any sequence | realised loss |
| `aci_window` | window CRC (200) at level α_t; α_{t+1} = min(2α, α_t + 0.005 (α − L_t)) | (1/T) Σ L_t ≤ α + (α_1 − α_{T+1}) / (γ T), any sequence | full (window), realised (α_t) |

The `aci` bound can also be fixed in advance: if scores are ≤ 1 and the non-commit loss is 0, λ never exceeds 1 + η (1 − α)(1 + d). So (1/T) Σ L_t ≤ α + (1 − λ_1 + η (1 + d)) / (η T) ("prior" in the tables).

## Setting
| item | value |
|---|---|
| Data | M2-13 per-trial items: B2T '25 our decoder and published-sentence gate (fit half 812, test half 816, 14 days), MEG M1-15 full-r1 (val 437, test 637). New: Toronto sEMG composed sentences, the M6-07 `c_trust` pipeline rebuilt exactly (fit-B 285, test 551 per condition; test wrong-commit and eWPM reproduce M6-07: 0.0036 / 4.677, 0.0036 / 8.024, 0.0000 / 4.080) |
| Order | B2T: dataset order inside each day, days ascending (we assume the file order is the trial order; the data has no trial time stamp). MEG: participant by participant. EMG: participant by participant, each in plan order |
| Upstream (fixed) | temperatures, conformal sets, guard, other policy thresholds as in M2-13 / M6-07 |
| Loss | 1 if the commit is wrong, else 0; non-commit loss 0 (no OFFER_WORDS) |
| Metrics | realised wrong-commit (from the simulated user), maximum over 50-trial windows, share of 50-trial windows > α, commit rate, eWPM (exact per-trial mix of both outcomes, as in M2-13), silent error |
| Protocols | `drift`: warm start on the earlier data, test data in order. `shuffled`: the same, test order random (20 times). `fullday` (B2T): all 1628 trials in order, cold start (never commit until the feedback allows it) |

## Results: B2T '25, our decoder, drift (n 816)
| method | wrong-commit | max rolling-50 | commit rate | eWPM | certificate |
|---|---|---|---|---|---|
| old gate | 0.0588 | 0.120 | 0.232 | 11.546 | — |
| offline CRC | **0.0625** | 0.120 | 0.244 | 11.553 | — |
| offline LTT | 0.0466 | 0.100 | 0.195 | 11.515 | — |
| window (d 0) | **0.0453** | 0.100 | 0.183 | 11.490 | — |
| decay (d 0) | **0.0417** | 0.100 | 0.176 | 11.500 | — |
| aci (d 0) | **0.0502** | 0.120 | 0.191 | 11.510 | 0.0502 (prior 0.0637) |
| aci_window (d 0) | **0.0478** | 0.100 | 0.194 | 11.489 | 0.0478 |
| window (d 10) | 0.0417 | 0.100 | 0.180 | 11.502 | — |
| decay (d 10) | 0.0404 | 0.100 | 0.172 | 11.496 | — |
| aci (d 10) | 0.0502 | 0.120 | 0.197 | 11.518 | 0.0509 (prior 0.0763) |
| aci_window (d 10) | 0.0466 | 0.100 | 0.199 | 11.520 | 0.0471 |
| aci (d 10, noticed errors only) | 0.0515 | 0.120 | 0.199 | 11.517 | 0.0496 |
| aci_window (d 10, noticed only) | 0.0478 | 0.100 | 0.202 | 11.517 | 0.0459 |

i.i.d. Bernoulli(0.05) reference, n 816: max rolling-50 median 0.120, p95 0.180.

`aci` step size (d 0): η 0.01 / 0.02 / 0.05 / 0.1 / 0.2 → 0.0527 / 0.0515 / 0.0502 / 0.0502 / 0.0502; eWPM 11.53 / 11.50 / 11.51 / 11.50 / 11.49. Small η gives more slack (prior bound 0.114 at η 0.01).

## Results: other data (drift protocol, delay 0)
| data | offline CRC | window | decay | aci | aci_window | old gate |
|---|---|---|---|---|---|---|
| B2T published: wrong-commit / eWPM | 0.0490 / 18.799 | 0.0429 / 18.765 | 0.0392 / 18.741 | 0.0478 / 18.796 | 0.0453 / 18.771 | 0.0441 / 18.767 |
| EMG `xsession` | **0.0635** / 4.657 | 0.0508 / 4.669 | 0.0399 / 4.670 | 0.0526 / 4.667 | 0.0490 / 4.668 | 0.0036 / 4.677 |
| EMG `calib` | 0.0417 / 8.100 | 0.0490 / 8.082 | 0.0454 / 8.074 | 0.0490 / 8.077 | 0.0490 / 8.074 | 0.0036 / 8.024 |
| EMG `xsubject` | 0 / 4.080 (no item can commit) | 0 / 4.080 | 0 / 4.080 | 0 / 4.080 | 0 / 4.080 | 0 / 4.080 |
| MEG M1-15 full-r1 | 0.0220 / 3.226 | 0.0141 / 3.226 | 0.0188 / 3.226 | 0.0173 / 3.230 | 0.0141 / 3.226 | 0 / 3.229 |

- EMG offline CRC here is the pure CRC threshold. M6-07 combined it with the grid threshold (`combine="max"`), which gave 0.004. So the M6-07 numbers are not wrong: the stricter grid threshold hid the drift.
- EMG `xsession` with the online methods: eWPM 4.66–4.67 vs the old gate 4.677. On EMG, almost all eWPM comes from OFFER, so the commit threshold changes eWPM very little.
- MEG: all commits are wrong (as in M2-13). The online methods spend part of the α budget and gain nothing. They bound the risk; they do not minimise it.

## Results: exchangeable control (B2T ours, test order shuffled, mean of 20)
| method | wrong-commit | commit rate | eWPM |
|---|---|---|---|
| offline CRC | 0.0625 | 0.244 | 11.553 |
| window | 0.0502 | 0.200 | 11.521 |
| decay | 0.0444 | 0.184 | 11.507 |
| aci | 0.0510 | 0.203 | 11.524 |
| aci_window | 0.0492 | 0.197 | 11.520 |

The shuffled order does not remove the drift: the later halves as a whole have more errors at the same confidence than the earlier halves. The online methods correct this level shift, at about −0.3 % eWPM.

## Results: full-day sequences, cold start (B2T ours, 1628 trials)
| method | wrong-commit (all) | max rolling-50 | eWPM (all) | later halves: wrong-commit / eWPM |
|---|---|---|---|---|
| old gate (in-sample fit) | 0.0522 | 0.120 | 11.125 | 0.0588 / 11.546 |
| window | 0.0516 | 0.140 | 11.104 | 0.0588 / 11.516 |
| decay | 0.0455 | 0.140 | 11.096 | 0.0539 / 11.510 |
| aci | **0.0442** | 0.100 | 11.107 | 0.0502 / 11.524 |
| aci_window | 0.0491 | 0.140 | 11.103 | 0.0551 / 11.510 |

Without any calibration block, `aci` and `aci_window` meet α over the full 14 days. The window methods do not (0.0516). On the later halves only, all methods are at or above α: the gate cannot know about the jump at the day's midpoint until errors arrive. Published gate: all online methods 0.040–0.050 over all trials (old gate 0.043).

## Notes and limits
- **Long-run, not per window.** The `aci` / `aci_window` bounds are about the average over the whole stream. The slack is O(1 / (η T)). For T = 816 and η = 0.05 the prior bound is 0.064, but the realised certificate was 0.050.
- `aci` tracks α: it converges to α, not below. If a margin is needed, run it at α' < α (for example α − the expected silent-error rate).
- **Silent errors.** The guarantee is about the losses the system observes. With noticed-only feedback the true rate can exceed α (EMG 0.058–0.064). Measure the silent-error rate and lower α' by it, or use `missing="pessimistic"` with a timeout.
- The window methods need full feedback. In real use, OFFER picks and retyped text give it; ABSTAIN does not.
- One B2T participant, one decoder seed, order assumed from the file. EMG sentences are composed from single key presses (M6-07 limit). MEG: degenerate (no right top-1). M1-09 async streams: not run (the top-1 sentence is also almost never right, so the result would be the MEG one).
- Settings were fixed in `config.json` before the first run. The "noticed-only" rows and the EMG table formatting were added after the first run; no setting changed.
