# Fidetype: an open trust layer and stream format for neural text entry

*One-page summary for outreach. Draft, 2026-11-11. The user is the sender and owns all outreach. Check every number against the linked result pages before sending.*

## The problem
Brain and muscle decoders now produce text: intracortical speech BCIs, MEG typing decoders, wrist EMG. Each one has its own output format. Few report how often the system commits a wrong sentence to the user, and none share a way to carry calibrated confidence, alternatives and provenance to the application.

## What Fidetype is
- **NeuralTextStream (NTS) v0.1**: an open, modality-neutral format for decoder output. It carries per-frame token probabilities, n-best hypotheses, calibrated confidence and provenance. It works for characters, phonemes and keys. [Spec](../../spec/neuraltextstream-v0.1.md)
- **A trust layer**: a decoder-agnostic policy that reads NTS and decides per sentence to *commit*, *offer* the n-best to the user, or *abstain*. It can use conformal risk control (CRC) to bound the wrong-commit rate.
- **A conformance suite**: 60 checks, each tied to a spec clause, at three levels (core, trust-ready, provenance). `python -m fidetype.conformance check <stream>`.
- **An open benchmark v0.1**: three tracks, 21 baseline entries, fixed splits, required null controls, and speed measured against a no-BCI baseline (gaze typing). It ships no data and no weights. [Benchmark](../../benchmark/README.md)
- Apache-2.0 code: https://github.com/zhangzibo/fidetype

## Results so far (three device types, public datasets only)
| Device type (dataset, licence) | Result | Source |
|---|---|---|
| Intracortical speech (Brain-to-Text '25, CC0; 816 test trials) | On the decoder output published with the dataset (WER 0.043), the trust gate cut wrong commits from **0.194 to 0.044** of trials, at **−4.3 % eWPM** (19.61 → 18.77). It also rejected streams that belong to another sentence | [B2T '25 result](../../wiki/questions/b2t25-trust-result.md) |
| Forearm sEMG (Toronto sEMG typing, CC BY 4.0; 551 test sentences, 19 people) | Wrong commits 0.54–0.96 → ≤ 0.004, and higher eWPM than always-commit in all three decoder conditions. Sentences are **composed** from isolated key presses | [EMG result](../../wiki/questions/emg-toronto-trust-result.md) |
| MEG typing (SpanishBCBL, CC BY-NC 4.0, research only) | Our async decoder: test CER 0.506. The trust layer stops wrong commits, but **no gain over gaze typing** (3.23 vs 3.15 eWPM, parity) | [M1-09](../../wiki/questions/m1-09-async-full-result.md), [trust core](../../wiki/questions/trust-core-v0-results.md) |

## Caveats we state up front
- **Always-offer baseline.** A trivial policy that always offers the n-best and never commits has zero wrong commits. On B2T '25 it reaches 11.37 and 18.11 eWPM; the trust layer is only **+1.6 % and +3.6 % faster**, at 59 and 44 wrong commits per 1,000 trials. On MEG the trust layer *is* always-offer. The value is a controlled, auditable trade-off, not a large speed gain. ([Paper 1 review response](../paper1/reviews/round-1-response.md))
- The 0.044 is a share of all trials. Among committed sentences, about 9 % are still wrong (commit rate 0.471). On the benchmark's fixed day-split, CRC missed its 0.05 target (0.062) because of drift across the day. ([Benchmark](../../wiki/concepts/open-benchmark.md))
- All results are offline replays of public data. No live user study. No medical claim.
- Paper 1 is a draft, not peer-reviewed and not yet on arXiv.

## What we ask of partners
Small, concrete steps: emit NTS from one decoder, run the conformance check on one stream, submit to the benchmark, or review the spec. We can write the adapter.
