# Fidetype: when should a neural text-entry decoder commit?

*One-page summary for outreach. Draft, updated 2026-11-12 with the final Paper 1 numbers. The user is the sender and owns all outreach. Check every number against the linked result files before sending.*

## The problem
Brain and muscle decoders now produce text: intracortical speech BCIs, MEG typing decoders, wrist EMG. Many end in a language model. The language model writes fluent sentences, also from weak or no neural evidence. Few systems report how often they send (commit) a wrong sentence to the user. No common format carries calibrated confidence, alternatives and provenance to the application.

## What Fidetype is (Apache-2.0, https://github.com/zhangzibo/fidetype)
- **NeuralTextStream (NTS) v0.1**: an open, modality-neutral format for decoder output (per-frame token probabilities, n-best, calibrated confidence, provenance). [Spec](../../spec/neuraltextstream-v0.1.md)
- **A trust layer**: per sentence it decides to *commit*, *offer* the n-best, or *abstain*. A Learn-then-Test (LTT) threshold bounds the wrong-commit rate with high probability. An evidence guard rejects streams with no signal.
- **Tools**: a conformance suite (60 checks; opt-in profiles `fep-0001` for streaming trust events and `fep-0002` for NTS over LSL), a Python SDK, an offline demo (`fidetype demo`; [demo/index.html](../../demo/index.html)), and an open benchmark v0.1 with required null controls.

## Paper 1 results (offline, public data, safety first)
Paper 1: *"When should a neural text-entry decoder commit? Risk-controlled commits from a stream-level trust layer."* Status: **preprint in preparation; arXiv submission ready, arXiv endorsement pending.** PDF: [fidetype-paper1.pdf](https://github.com/zhangzibo/fidetype/blob/main/papers/paper1/final/fidetype-paper1.pdf). Data: Brain-to-Text '25 (CC0), one intracortical speech participant, 14 days; two decoders (ours, and the published sentence gated by agreement with ours). Target α = 0.05.

| Test | Result | Source |
|---|---|---|
| Always commit (baseline) | Wrong text for 61 % (ours) and 19 % (published) of sentences | Paper 1, Sect. 6.4 |
| Time order: calibrate on earlier days, test on later days | Pooled wrong-commit rate **0.010–0.027** in every design. 0–2 of 10–13 test days above α; **no day significantly above α** | Paper 1, Sect. 6.2, Tab. 1 |
| No-signal controls (300 uniform streams, our decoder) | Plain threshold: **198 of 300 committed** (all wrong). With the evidence guard: **0 of 300** (also 0 of 300 frame-shuffled) | Paper 1, Sect. 6.6 |
| Per-day scope | LTT bounds the mix of days, not each day. Day 34 (published gate): 0.102 | Paper 1, Sect. 6.3 |
| Remedy, "certify, then commit" | First ≥ 45 sentences offer-only (labels from the user's picks), then max(global, per-session LTT), plus a risk monitor. Day 34: 0.103 → **0.034**; 0 of 14 days above α; eWPM −2.2 % | [A2 results](../../experiments/2026-11-13-a2-per-session-risk/results.md) |
| Streaming layer = offline layer | Same decisions on **816/816** test trials (4 replays); each decision has a verified provenance-ledger entry | [M4-06](../../experiments/2026-11-13-m4-06-real-replay/results.md) |
| Live LSL input (BrainFlow Synthetic board, no text information) | 0 commits of 26 decisions; dropout, stream loss and reconnect handled | [M6-08](../../experiments/2026-11-13-m6-08-brainflow-live/results.md) |

Forearm sEMG (Toronto, CC BY 4.0) and MEG typing (SpanishBCBL, CC BY-NC 4.0, research only) are format and safety checks: no sEMG test participant above α; on MEG the layer committed nothing (0 of 637) and equals always offering.

## Limits we state up front
- **One intracortical participant so far.** A confirmatory test on a second participant is in progress. It has no results yet.
- The guarantee is for the mix of calibration days. A single session needs "certify, then commit". Current decoders commit few sentences under the guarantee (15 % and 39 %; 21 % and 8 % of those commits were wrong in random re-splits).
- All results are offline replays of public data. No live user study. No medical claim. Not peer-reviewed.

## What we ask of partners
Small, concrete steps: emit NTS from one decoder, run the conformance check on one stream, submit to the benchmark, or review the spec. We can write the adapter.
