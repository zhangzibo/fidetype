---
title: Discrete intent events with per-class risk control (P12-01 / P12-02, FEP-0003)
type: experiment
updated: 2026-11-13
---

# Intent events: per-class risk control on public sEMG data and a simulator

First test of the FEP-0003 intent profile and the reference intent trust layer (`fidetype.trust.intent`). Public data only.

- Spec: [FEP-0003](../../spec/feps/0003-intent-events.md). Wiki: [intent-events](../../wiki/concepts/intent-events.md).
- Scripts: [eval_intents.py](eval_intents.py) (CPU, 347 s, isolation class `background`), [shuffle_control.py](shuffle_control.py) (CPU, 4 s; time-shuffled EMG control).
- Numbers: `results/summary.json` (aggregates only), all rows in [results/tables.md](results/tables.md). Log: `results/run.log`.
- Derived control logits (outside the repo): `C:\Users\zhang\bci-data\runs\p12-intent\`.

## Data
| Source | What | Licence |
|---|---|---|
| Toronto sEMG typing (Achituve et al. 2025) | 29,824 key presses, 19 participants, 2 days. We reuse the per-press 27-way logits of the M6-07 CNN decoders ([M6-07](../2026-11-11-emg-toronto/results.md)). **Recast:** each press is one decision unit, "which of 27 keys" | CC BY 4.0 |
| Simulator (`fidetype.trust.intent_sim`) | **Synthetic.** 12 intents with a null `rest` intent; 10 % rest trials, 10 % no-signal trials (truth "no intent"); a signal-quality index; miscalibrated softmax | none (our code) |

The sEMG data has no rest windows, so its vocabulary has no null intent. Risk classes of the 27 keys are a fixed, arbitrary declaration made before any result: `key.a`-`key.e` irreversible (stand-ins for "send", "call", "delete"), `key.space` safe, the other 21 keys undoable.

## Protocol
- Per participant and session (group): R random splits of the presses into thirds: fit (temperature), calibration (one threshold per risk class), test. R = 100 (`calib`) or 50 (others). n per third about 260.
- Limits per decision unit: safe alpha 0.10, undoable 0.05, irreversible 0.01. LTT with delta 0.1 split over the 3 classes (Bonferroni); CRC as the alternative.
- Defaults: data-free COMMIT floor p >= 0.5; irreversible intents are armed (OFFER, `confirm_required`), not committed. "Wrong irreversible" = wrong arms (an execution also needs a confirmation, so the wrong-execution rate is at most this).
- `nosignalref`: fit with a no-signal reference (the decoder's output on an all-zero window plus the uniform row; no labels). Each class threshold goes just above the reference's top-1 probability of that class.
- Controls on the test thirds, with the configuration fitted on clean data: `uniform` (no signal), `zero` (decoder output on zero EMG), `timeshuffled` (CNN on EMG with permuted time samples; never used in a fit), `pairshuffled` (outputs permuted across presses: breaks exchangeability). Plus `permuted-decoder`: the label-permuted-training decoder of M6-07, calibrated and tested on its own outputs.

## Main result (sEMG, session-calibrated decoder `calib`, top-1 accuracy 0.299)
Means over 1,900 test sets.

| configuration | input | act rate | commit precision | OFFER rate (truth in offer) | wrong safe | wrong undoable (share of test sets > alpha) | wrong irreversible |
|---|---|---|---|---|---|---|---|
| LTT | clean | 0.082 | 0.733 | 0.10 (0.904) | 0.0002 | 0.0218 (0.03) | 0 (never armed) |
| LTT | uniform | **0** | - | 0 | 0 | 0 | 0 |
| LTT | zero input | **0.371** | 0.026 | 0 | 0 | **0.3612 (0.75)** | 0 |
| LTT | time-shuffled | 0.017 | 0.230 | 0.04 | 0 | 0.0128 (0.04) | 0 |
| LTT | pair-shuffled | 0.082 | 0.075 | 0.10 | 0.0079 | 0.0681 (0.68) | 0 |
| **LTT + no-signal ref** | clean | 0.057 | 0.796 | 0.12 (0.905) | 0.0002 | 0.0115 (0.01) | 0 (never armed) |
| **LTT + no-signal ref** | zero input | **0** | - | 0.12 | 0 | 0 | 0 |
| **LTT + no-signal ref** | time-shuffled | 0.006 | 0.291 | 0.04 | 0 | 0.0044 (0.00) | 0 |
| **LTT + no-signal ref** | pair-shuffled | 0.057 | 0.096 | 0.12 | 0.0080 | 0.0432 (0.34) | 0 |
| CRC + no-signal ref | clean | 0.067 | 0.776 | 0.12 (0.912) | 0.0002 | 0.0134 (0.02) | 0.0029 (0.08) |
| CRC + no-signal ref | zero input | 0 | - | 0.12 | 0 | 0 | 0 |

Other decoders (LTT + no-signal ref, clean): cross-session act rate 0.022, wrong undoable 0.0073; cross-subject act rate 0.040, wrong undoable 0.0131; zero input 0 in both. The label-permuted decoder (accuracy 0.022, chance 0.037) acts on 0 of its presses with LTT and CRC.

## Simulator (synthetic, 200 sessions, LTT)
| gate | input | act rate | commit precision | wrong safe | wrong undoable | wrong irreversible |
|---|---|---|---|---|---|---|
| none | clean | 0.690 | 0.874 | 0.0477 | 0.0307 | 0.0018 |
| none | no-signal trials only | **0.405** | 0 | 0.2340 | 0.1612 | 0.0102 |
| none | uniform | 0 | - | 0 | 0 | 0 |
| quality >= 0.5 | clean | 0.650 | 0.933 | 0.0244 | 0.0147 | 0.0008 |
| quality >= 0.5 | no-signal trials only | **0** | - | 0 | 0 | 0 |
| quality >= 0.5 | pair-shuffled | 0.622 | 0.082 | 0.2482 | 0.2664 | 0.0559 |

CRC (quality gate, clean): wrong 0.0244 / 0.0237 / 0.0046, act rate 0.723.

## Findings
1. **Risk-control validity holds on clean data.** In every setting (sEMG `calib`, cross-session, cross-subject, simulator; LTT and CRC) the mean wrong-commit rate of each class is at or below its alpha. LTT keeps the share of test sets above alpha small (undoable 0.01-0.05 on sEMG). CRC is marginal: its means are closer to alpha and more single test sets exceed it (undoable up to 0.21; synthetic irreversible mean 0.0097 for alpha 0.01), as its guarantee says.
2. **Irreversible intents rarely pass.** With about 260 calibration units, LTT at alpha 0.01 and delta 0.033 is infeasible for the sEMG irreversible class in every fit, so it never arms; the user selects such intents from an OFFER list (truth in offer about 0.90). CRC arms 1 % of presses with wrong arms 0.0029 on average. A real deployment needs more calibration units or a stronger decoder for direct irreversible arming.
3. **Uniform input never commits** (all settings), because of the 0.5 floor and calibration.
4. **No-signal input that the calibration did not contain can commit often.** The CNN's zero-input output is one confident key (an undoable letter). A configuration fitted only on clean presses acts on 37 % (LTT) / 45 % (CRC) of zero-input presses, 97 % of them wrong. This is the intent form of the M2-18 empty-commit failure. Risk control cannot see it: the bound covers data like the calibration data. **Defences that work:** a no-signal reference at fit time (zero-input acts 0; clean act rate 0.082 -> 0.057), or a signal-quality gate (simulator no-signal trials 0.405 -> 0). FEP-0003 section 6 rule 6 makes the controls a required report and the reference a SHOULD.
5. **Time-shuffled EMG** keeps some key information (top-1 precision 0.23-0.29, above chance 0.04) because amplitude per channel stays. The layer acts on 0.6-1.7 % of these presses with wrong rates below alpha.
6. **Pair-shuffled outputs break the guarantee**, as expected: real-looking confident outputs that do not match the truth (wrong undoable 0.043-0.068, above alpha in 34-68 % of test sets). The guarantee needs exchangeable calibration data; drift or a changed decoder needs re-calibration or online monitoring (`fidetype.trust.online_risk`, `session_risk`).
7. **The data-free floor matters for lax classes.** Without it (`ltt-nofloor`) LTT gives the safe class threshold 0.00 and safe commits rise (sEMG cross-subject wrong safe 0.0006 -> 0.0190, still below 0.10).

## Limits
- The sEMG recast uses **oracle key timing** and isolated presses (as M6-07). Each press is a 27-way choice; a real menu or device has its own timing and error costs.
- The risk-class map is arbitrary. The numbers show the method, not a device.
- No rest class in the sEMG data, so the null-intent rule is tested only on synthetic data.
- The confirmation step is evaluated as "wrong arms" (an upper bound of wrong executions). A real confirmation channel would also have its own error rate.
- Per-class guarantees are per decision unit and assume exchangeable units within a session.
