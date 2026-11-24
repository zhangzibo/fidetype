---
title: Certified accidental-click rate for an intracortical click decoder, with its cost in bits per second - pre-registration (plan only)
type: experiment-plan
task: P12-08 (frontier direction 5, HORIZONTAL; CPU) # id corrected 2026-11-24: P12-07 was already taken; earlier text said "proposed P12-07"
updated: 2026-11-23
---

# Certified accidental clicks: can a click gate keep false clicks below a stated rate, and what does it cost in BPS? (pre-registration, plan only)

Written **before** the data is on disk and before any number exists. **Blocked on a manual download by the user** (see "What the user must do"). CPU only; no GPU, no rental.

## Hypothesis
- **H1.** A risk-controlled click gate keeps the false-click rate at or below a stated alpha on held-out blocks of intracortical sessions.
- **H2.** At the same false-click rate, the certified gate gives a higher replayed throughput (bits per second) than a fixed-threshold or a smoothing post-filter baseline.

Why it matters: public click decoders report speed and say "fewer accidental clicks", but give no rate and no bound. This extends the trust layer from text to discrete control (`fidetype.trust.intent`, FEP-0003).

## Data and licence
| item | value |
|---|---|
| Dataset | BrainGate multi-gesture drag-and-drop, Dryad doi:10.5061/dryad.98sf7m0v1: held hand gestures (1 / 2 / 4 s) for click-and-hold and drag-and-drop, alone and with 2D cursor control; 2 participants; about 8.2 GB ([dataset survey](../../wiki/questions/intent-datasets-survey.md)) |
| Licence | **CC0 1.0** (Dryad API metadata) |
| Status | **Not downloaded.** Dryad file downloads need a login (the API answered 401 for other BrainGate sets) |
| Optional | NLB MC_RTT (CC BY 4.0, local) for a cursor-only sanity check of the replay code (no clicks) |
| Own outputs | `C:/Users/zhang/bci-data/derived/click-cert/` only |
| **Copy to a rented cloud machine?** | Allowed (CC0), but **not needed**: the plan is CPU only and runs locally |

## What the user must do (by hand)
1. Log in to Dryad in a browser and download every file of doi:10.5061/dryad.98sf7m0v1 (about 8.2 GB).
2. Put them, unchanged, in `C:\Users\zhang\bci-data\raw\braingate-dragdrop\`.
3. Tell the orchestrator. An agent then checks each file against the SHA-256 digests of the Dryad API (readable without a login), adds the catalogue row to `references/README.md`, and runs stage 0.

## Stage 0: data audit (before any decoder; it can stop the plan)
Count per participant and session: sessions, blocks, trials, cued click (or hold) onsets, total no-click time, the bin size and the feature type (threshold crossings, spike-band power), and whether cue and cursor times are present. Committed as `audit.json` (counts only).

**Feasibility stop (fixed now):** go on only if, per participant, there are >= 3 sessions, and the calibration part (below) has >= 200 no-click windows and >= 50 cued clicks. Else stop with outcome **N** ("not testable on this dataset") and record why.

## Splits (fixed now)
Per session, blocks in time order: the first 40 % of blocks train the decoder, the next 30 % calibrate the gate, the last 30 % are the test. (If a session has fewer than 3 blocks, its trials in time order are split the same way.) A secondary cross-session variant: calibrate on session k, test on session k + 1, with `aci` across sessions.

## Decoder and gate (our own code)
- **Decoder:** per participant and session, a regularised logistic regression on causally smoothed binned features (half-Gaussian, SD 2 bins; history of 5 bins), output p(click) per bin. No deep model (CPU, small data).
- **Event rule:** a click is emitted when p(click) >= lambda for h consecutive bins (h = the hold time; h fixed at 3 bins), with a refractory period of 500 ms.
- **Loss unit:** a 1-s no-click window = a 1-s window that holds no cued click onset +- 500 ms. Loss 1 if the rule emits a click in the window. A cued click counts as correct if a click is emitted within [onset, onset + 1.5 s].
- **Certified gate:** LTT (`fidetype.trust.risk_control.ltt_threshold`, alpha **0.02**, delta 0.1) on the calibration no-click windows over a lambda grid (0.50 to 0.995, 50 steps); the most permissive certified lambda. The intent layer's frozen config (`fit_intent_config`) holds it.
- **Baselines:** (B0) fixed threshold lambda 0.5, h 3; (B1) smoothing post-filter: a moving average of p(click) over w bins, then threshold; w and the threshold are chosen on the calibration part to match the gate's **calibration** false-click rate (not certified).

## Throughput (offline replay; formula fixed now)
BPS = log2(N − 1) x max(S_c − S_i, 0) / t, with N = 35 x 35 grid targets (Webgrid-style), S_c the correct clicks, S_i the false clicks plus the missed cued clicks, and t the test-block time. Cursor motion is replayed as recorded; only the click decision changes. A missed cued click adds a 2-s retry time. This is an offline replay of a closed-loop task, not closed-loop use.

## Controls
- **Time-shuffled neural input** (bins permuted within each test trial): the certified gate must emit **0 correct clicks above chance** and keep its false-click rate <= alpha.
- **Zero input:** no clicks.

## Primary metric
Per test session: the false-click rate of the certified gate (no-click windows with a click / all no-click windows) with its Clopper-Pearson 95 % interval.

## Pass / fail rules (fixed now)
| id | rule | pass if |
|---|---|---|
| **P1** (primary) | test false-click rate of the certified gate | <= 0.02 (point) on >= 80 % of test sessions, **and** the pooled CP95 upper bound <= 0.03 |
| **P2** | certified gate BPS − B1 BPS, at matched calibration false-click rate | > 0 with a paired trial-bootstrap CI95 above 0 (2,000 resamples, seed 0), pooled over sessions |
| P3 | controls | shuffled: false-click rate <= 0.02 and correct clicks not above chance (binomial test, level 0.05); zero input: 0 clicks |
| D | cross-session `aci` variant: long-run false-click rate vs alpha + slack; BPS cost of the gate vs B0 | descriptive |

## Outcomes
| outcome | condition | meaning |
|---|---|---|
| **A** | P1, P2, P3 pass | A certified accidental-click rate on intracortical data, with a throughput gain over a smoothing filter at the same rate |
| **B** | P1, P3 pass; P2 fails | The bound holds; it costs throughput against a tuned smoothing filter. We report the BPS price of the guarantee |
| **C** | P1 fails | The within-session bound does not transfer to the later blocks (drift); the cross-session `aci` result says if online re-calibration fixes it |
| **X** | P3 fails | The decoder reads something other than the neural signal; no claim |
| **N** | feasibility stop, or no download | Not testable |

## Seeds
Deterministic decoder fit (seed 0); bootstrap seed 0. No other randomness.

## Compute estimate
CPU only: audit < 1 h; decoders + gates + replay about 2-6 CPU-h (4 threads). Local, free. No GPU, no rental.

## Where it may honestly fail
- The dataset may have few click events per session, or hold gestures that are not clicks (feasibility stop).
- The cue time is not the intent time; the tolerance windows are a modelling choice.
- Offline replay of a closed-loop task: a user would adapt to the gate.
- Two participants; the result is per participant, not a population claim.
- A simple logistic decoder may be much weaker than the decoders used online; the bound still holds, but BPS will be low.

## Order and outputs
1. Commit this plan (this commit). 2. After the user's download: digest check, catalogue row, stage 0 audit (commit). 3. If feasible: code + CPU tests, then the run. 4. `results/results.json` (aggregates), `results.md`. No neural data in the repo.
