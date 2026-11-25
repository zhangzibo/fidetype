---
title: "Parameter-efficient cross-session calibration of intracortical speech decoders, T12 and T15 (Roy et al. 2026)"
type: source
tags: [implant, intracortical, speech, t12, t15, recalibration, input-layer, parameter-efficient, f1, f3]
sources: [roy-input-affine-recalibration]
updated: 2026-11-24
---

# Roy, Tabassum & Mozumder 2026: input-affine recalibration

## Citation and links
- D. Roy, F. Tabassum, R. Mozumder. "Rapid parameter-efficient calibration for cross-session intracortical speech decoding across multiple datasets." Research Square preprint v1, 2026-10-14 (under review at *Scientific Reports*; not peer reviewed). https://doi.org/10.21203/rs.3.rs-11038178/v1
- **Licence:** CC BY 4.0 ("This work is licensed under a Creative Commons Attribution 4.0 International License", PDF cover).
- **Local raw path:** `references/papers/roy_2026_researchsquare_rs-11038178-v1.pdf` (22 pages, SHA-256 `096485598e8f19e393034718e7ebde921bbeb287df647946571fb4747bbd4b14`) + `.txt`. Downloaded 2026-11-24. Git-ignored.

## TL;DR
For a new session, train only a 256 × 256 affine map plus bias at the decoder input (65,792 parameters) on the first 40 or 80 labelled trials. Freeze the rest. On T12 this lowers macro PER in every held-out session. On T15 the gain is smaller and not significant.

## Key facts
| Item | Value | Where |
|---|---|---|
| What is trained | "a 256 × 256 affine transformation and bias at the neural input, while the recurrent encoder and CTC classifier remained frozen"; "Only 65,792 parameters (<0.05% of either model)" | Abstract; §2.6 |
| Budget | first 40 or 80 labelled trials of each held-out session; 200 steps fixed before held-out evaluation | Abstract; Methods |
| T12 | macro PER 0.4211 → 0.3732 ± 0.0004 (K = 40, **11.37 % relative**); 0.4219 → 0.3565 ± 0.0006 (K = 80, **15.51 % relative**); p = 0.03125 for both | §2.2 |
| T15 | 0.6324 → 0.6152 ± 0.0041 (K = 40, 2.72 % relative, p = 0.546875); 0.6123 → 0.5508 ± 0.0004 (K = 80, 10.05 % relative, p = 0.15625); "neither T15 condition fell below the nominal 0.05" | §2.4 |
| Backbone | 5-layer bidirectional GRU, 1,024 units per direction (offline, not streaming) | Methods |
| Data | T12 (Willett et al. 2023): 24 sessions, 9,680 trials; T15 (Card et al. 2024 release): 45 sessions, 9,498 trials | Methods |
| Cost | 7.5 s (T12) to 23.5 s (T15) per calibration on a GPU | §2.6 |

## Limitations (stated)
- Two participants, offline only, PER only (no LM, no WER).
- Supervised: needs 40 or 80 labelled trials. "These observations do not imply that neural drift is itself affine."
- p values are nominal (four comparisons, no multiplicity adjustment).

## Why it matters for us
- It is the closest baseline for update 1 of E2 (a day layer on 24 phase-A items). Our update is in the same family.
- It agrees with [Levin et al. 2026](levin-cross-brain-transfer.md) and [Chen et al. 2026](chen-falcon-h2-fewshot.md): a small per-session input map on a frozen trunk is the working pattern.
- Its T15 baseline PER (about 0.61–0.63) is much weaker than the published T15 decoder, so its numbers are not comparable to ours.

## Feeds
- [E2 self-teaching write-up](../questions/frontier-e2-self-teaching.md)
- [Brain-to-Text '25](../entities/brain-to-text-25.md)
- [Novelty check, 2026-11-24 update](../questions/novelty-check-2026-11.md#update-2026-11-24-literature-check)
