---
title: P14-60 ship the lm_beam_direction offer gate in the willett-hw manifest - results
type: experiment
task: P14-60
updated: 2026-11-23
---

# P14-60 (gap 190): ship `lm_beam_direction >= 0` in both `willett-hw` guards (2026-11-23)

Roadmap: [P14-60](../../wiki/questions/roadmap-standard.md#p14-60-ship-the-lm_beam_direction-offer-gate-in-the-willett-hw-manifests). Start: user decision 2026-11-23, option C for gap 181 (close it by decision: LM-guard evidence of [P5-36b](../2026-11-22-p5-36b-two-direction-lm/results.md) plus the [P5-37](../2026-11-22-p5-37-fixed-threshold/results.md) pool pass). Rule: the P5-37 fixed threshold 0, not fitted. CPU only.

## What shipped

| Item | Value |
|---|---|
| Gate list, built-in guard (`trust.offer_gate`) | `coherence >= 0.004183090472992479`, then `lm_beam_direction >= 0` |
| Gate list, LM guard (`readouts.lm.trust.offer_gate`) | `coherence >= 0.003485725778021531`, then `lm_beam_direction >= 0` |
| `readout=` wiring | `PretrainedDecoder.guard` / `XBodyCtcDecoder.guard` build the gates with `fidetype.pretrained.manifest_offer_gates`; a `lm_beam_direction` gate gets `m.lm_readout()` (for `readout="lm"`: the same object as the guard's `decode_fn`, built once). Missing LM file: `NoTrustConfig` with a hint |
| `config_id` | **unchanged**: built-in `tcfg-39aac48688b8bd12`, LM `tcfg-f498c0637536daec`. An offer gate is not part of the frozen config (library design; P14-54 shipped its gate the same way). See "Deviation" |
| Guard files | unchanged (bytes and SHA-256) |
| Model card | one `offer gate` line per gate, plus a `card` line with the rule, the cost and the evidence; built-in: "Tested on training data only"; new `limits` entry |

## Re-checks (P14-56 offer-control blocks, P5-31 rule)

`recheck_offer_control` of each guard built from the packaged manifest (both gates on), same inputs as P14-54 / P14-59 (106 val log-probs, 106 time-shuffled val inputs of P14-41).

| Guard | real (LTT) | uniform | frame-shuffled | time-shuffled | commits match sheet | verdict | time |
|---|---|---|---|---|---|---|---|
| built-in `tcfg-39aac48688b8bd12` | 40 / 40 | 0 / 300 | 0 / 300 | 0 / 106 | yes (0 LTT commits) | **PASS** | 3,016 s |
| LM `tcfg-f498c0637536daec` | 40 / 40 | 0 / 300 | 0 / 300 | 0 / 106 | yes (0 LTT commits) | **PASS** | 113 s |

Same counts as the coherence-only re-checks; the direction gate removes no LTT real offer. Files: [results/recheck-builtin-gated.json](results/recheck-builtin-gated.json), [results/recheck-lm-gated.json](results/recheck-lm-gated.json). The manifest `offer_control` blocks now cite these files (`checked` 2026-11-23); `before_gate` is kept.

## Wiring check (information only)

80 test sentences, decisions of the packaged guards with coherence only and with the shipped list. The test set was used before (P5-36b post hoc), so this is not evidence for the rule; it shows the gate is applied. [results/wiring.json](results/wiring.json).

| Guard | real offers (coherence only -> shipped) | `rev_out` offers (coherence only -> shipped) |
|---|---|---|
| built-in | 77 -> 76 (1 removed) | 77 -> 1 |
| LM | 77 -> 75 (2 removed) | 77 -> 2 |

These equal the P5-36b post-hoc counts at threshold 0 (1 / 1 and 2 / 2). Every change was OFFER -> WITHHOLD (asserted).

## Deviation from the done-when

The done-when says "(new `config_id`)". The library computes `config_id` from the frozen trust config only; an offer gate never changes it (docs/trust-guarantee.md section 5b; P14-54 and P5-33 shipped their gates with unchanged ids). A new id would need a new calibration or a change to that rule, which the gate does not justify. So the ids stay. The audit header of a guard lists its offer gates, so a log still shows which gate list was active. This part needs a decision: amend the done-when, or open a follow-up that puts the gate list into an identity.

## Tests

`tests/test_pretrained_offer_control.py` (gate lists, card lines, readout wiring with a stub, parser refusals for bad list items, `manifest_offer_gates` errors), plus the trust and pretrained test modules. Run log: [results/run.log](results/run.log).
