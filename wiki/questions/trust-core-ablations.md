---
title: "Trust-core ablations: what each module of the frozen v4 configuration does (M3-01, M3-02)"
type: question
tags: [trust-core, ablation, calibration, guard, ltt, crc, commit-gate, session-risk, declaration, meg, simulator, b2t25, emg, paper1]
sources: [brain-to-text-25-copytask, toronto-semg-typing, learn-then-test, conformal-risk-control]
updated: 2026-11-14
---

# Trust-core ablations (M3-02) and the MEG / simulator runs (M3-01)

**Question asked:** With the Paper 1 frozen v4 configuration as the baseline, what happens when we turn each trust-core module off (or keep it alone)? And does the trust layer work end to end on SpanishBCBL MEG and on the simulator?

**Short answer:** No module is enough alone. Each module covers a different failure. Only the full composition (calibration + guard + LTT with the max combine) has 0 commits on every signal-destroying control of the real datasets and a re-split exceedance at or below δ. On MEG, the decoder is too weak: v4 makes **0 commits** in all five runs, which is the correct result. On the simulator, the layer runs end to end (streaming = batch, 1,800 of 1,800), but v4 **commits on 1-16 % of frame-shuffled simulator streams**. That is a new limit of the guard.

Experiment: [M3-01 / M3-02 results](../../experiments/2026-11-14-m3-01-02-ablations/results.md) (pre-declared [plan](../../experiments/2026-11-14-m3-01-02-ablations/plan.md); full [tables](../../experiments/2026-11-14-m3-01-02-ablations/results/tables.md)). CPU only, cached Paper 1 decodes, no retraining.

## Setup
- Baseline = Paper 1 v4 (git tag `paper1-v4-frozen-config`): frame + sentence calibration, guard on, policy grid on fit-A, LTT (α 0.05, δ 0.1) on a clean calibration half, final threshold = max(grid, LTT).
- Data: B2T '25 T15 ([source](../sources/brain-to-text-25-copytask.md); our decoder and the published gate; fixed splits A / B + 200 re-splits), Toronto sEMG ([source](../sources/toronto-semg-typing.md); calib / xsession / xsubject; fixed split + 50 re-splits), SpanishBCBL MEG ([dataset](../entities/spanishbcbl-dataset.md); 5 provenance runs, aggregated only), simulator (median / worst × confidence distortion 0.5 / 1 / 2).
- The baseline reproduces Paper 1 exactly (same λ and counts on all four fixed B2T splits; MEG 0 commits, eWPM 3.20).

## Module effects (one line each)

| module | turned off (or changed) | what it protects against | evidence |
|---|---|---|---|
| LTT risk control | plug-in or CRC threshold | rate above α on a new split | B2T re-splits > α: 31 % / 27 % (plug-in), 19 % / 18 % (CRC) vs 7.5 % / 5.5 % (v4); published fixed splits +0.018 |
| max combine | LTT λ alone | too low a threshold when LTT is loose | sEMG wrong commits 0.004 → 0.022 / 0.031, 3/200 frame-shuffled commits |
| guard | off | no-information input on strong LM decoders | B2T ours: 198/300 uniform commits; simulator: 73-81 % empty commits on zero input. On real B2T data the guard costs a little (re-splits > α without it: 0/200 ours, 1/200 published) |
| calibration | off | over-confident weak decoders; decode quality | MEG: 21 commits, 20 wrong (+ shuffled-MEG commits); B2T ours A 0.0245 → 0.0527; simulator −2.4 to −7.5 eWPM |
| conformal sets | off | (speed only) | eWPM −0.03 to −0.10, no safety change |
| commit gate B (M2-18, opt-in) | on | empty commits | 0 B2T commits blocked; sEMG 1 / 7 / 0 blocked |
| session monitor (M2-17, opt-in) | on | a bad session | 1 alarm in 14 published sessions; inert elsewhere |
| declaration check | off vs abstain | producer decoding at the wrong temperature | raw-decoding producer: B2T wrong commits 0.052-0.099 (all above α); "abstain" gives 0 commits but eWPM 3.55 < gaze 4.08 |

> **Our take:** The modules are not redundant. LTT holds the rate on real data; the guard and the commit gate hold the controls; calibration keeps a weak decoder from committing confident garbage. The R1 ablation (pre-v4 recipe) said "the guard should be optional". With the controls in the picture, that is wrong for strong-LM decoders: the guard is what rejects uniform input. Keep the full composition as the default.

> **Our take:** "Marginal wrong-commit ≤ α" can hold while every commit is wrong. MEG without calibration committed 21 items, 20 wrong, yet 20/637 = 0.031 < α, so LTT accepted it. Paper 1 already reports the error among commits; this case shows why it matters (see the joint-LTT rule in Paper 1 R4).

## M3-01 outcomes
- **MEG (SpanishBCBL):** 0 commits in all 5 provenance runs (Paper 1 run, 2 seeds, r4b-full, r5-medium). The decoder is too weak: top-1 sentence correct 0-5 of 637, truth in the n-best 0-12 of 637, CER 0.48-0.63, and every eligible calibration item is wrong. The one-sided 95 % bound on the wrong-commit rate is 0.0047 per run. eWPM 2.95-3.20 vs gaze 3.15. Controls 0 commits; streaming = batch 3,185/3,185. This is a valid safety result, not a usefulness result.
- **Simulator:** v4 wrong-commit 0.013-0.047 (≤ α) at commit 0.40-0.75 and eWPM 23.5-25.1; always-commit 0.10-0.32. The frozen config replayed through `StreamingTrustLayer` gives the batch decisions exactly. The frame temperature fit recovers the distortion (2.00-2.01 for 0.5, 0.50-0.51 for 2.0).

## Surprises
1. **Frame-shuffled simulator streams pass the v4 guard** (1-16 of 100 committed, all wrong). Simulator frames are sharp, independent key peaks; shuffling keeps them confident, and the in-domain LM builds a fluent sentence. Real streams do not do this (0 commits on B2T, sEMG, MEG). A temporal-structure check would be a guard extension; not applied.
2. **The declaration check in "abstain" mode is safe but too costly**: no offers at all. An "offer-only" mode is the better reaction to a mismatch (suggestion, not applied).
3. Commit gate B and the session monitor change almost nothing on Paper 1 data. Their targets (empty commits on T12, a bad day) are rare here.

## Open items
- Guard extension for shuffled-but-confident input (simulator finding). P5-07: handled at the policy level by the control-aware grid fit (simulator frame-shuffled commits 40 → 3 of 600); a per-stream feature stays future work.
- `declaration_check="offer-only"` mode: **done** in P5-07 (B2T mismatch: 0 commits at eWPM 11.34 vs 3.55 for "abstain").
- Error-among-commits bound as a default secondary check (MEG without calibration).

## Follow-up: the v5 candidate recipe (P5-07)
The weak points found here and in M2-18 / P12 led to a v5 candidate recipe (`fidetype.trust.recipe_v5`, pre-declared [plan](../../experiments/2026-11-14-trust-v5-candidate/plan.md), [results](../../experiments/2026-11-14-trust-v5-candidate/results.md)). Four switchable changes on top of v4: (a) commit gate B on, (b) control-aware grid fit (a grid point must commit ≤ 1 % of uniform, frame-shuffled and zero stand-in copies of the grid-fit streams), (d) no-signal reference floor, (e) declaration check "offer-only"; (c) 0.8 instead of 1.0 in the grid was tested and dropped.

| change | where it acts | real-data cost |
|---|---|---|
| (a) gate B | T12 dry run: uniform 335 → 0, zero stand-in 334 → 0, empty commits 655 → 0 | none measurable (eWPM change ≤ 0.001) |
| (b) control-aware fit | simulator frame-shuffled commits 40 → 3 of 600 | none on real fixed splits (the controls do not bind once the gate is on) |
| (c) 0.8 for 1.0 | — | can raise wrong commits (sEMG calib 2/21 → 13/74): dropped |
| (d) no-signal floor | redundant with (a) on text data | none |
| (e) offer-only | declaration mismatch: 0 commits, offers kept | — |

> **Our take:** On Paper 1 data v5 = v4 (same commits on all four B2T splits). Its value is on the failures v4 has: no-signal input when the fit picks `commit_max_risk` 1.0 (T12), and confident shuffled input (simulator).

## Related pages
- [Trust core v0 results](trust-core-v0-results.md): the first ablations (pre-v4, not clean).
- [Per-session risk control](per-session-risk-control.md): the monitor and block-LTT methods.
- [Confirmatory test on T12](confirmatory-t12.md): the empty-commit failure behind commit gate B.
- [Paper 1 plan](paper1-plan.md).
- [Conformal risk control](../concepts/conformal-risk-control.md), [streaming trust layer](../concepts/streaming-trust-layer.md), [NeuroLLM](../concepts/neuro-llm.md).
