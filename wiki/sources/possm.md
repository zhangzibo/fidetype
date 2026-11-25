---
title: "POSSM: generalizable, real-time neural decoding with hybrid state-space models (Ryoo et al. 2025)"
type: source
tags: [implant, intracortical, state-space, real-time, causal, pretraining, cross-species, handwriting, speech, t5, t12, f3]
sources: [possm]
updated: 2026-11-24
---

# POSSM (Ryoo et al. 2025)

## Citation and links
- A. H.-W. Ryoo, N. H. Krishna, X. Mao, M. Azabou, E. L. Dyer, M. G. Perich, G. Lajoie. "Generalizable, real-time neural decoding with hybrid state-space models." NeurIPS 2025. arXiv:2506.05320 (v2, 2025-11-07). https://arxiv.org/abs/2506.05320
- **Licence:** CC BY 4.0 (arXiv licence link).
- **Local raw path:** `references/papers/ryoo_2025_possm_arxiv_2506.05320v2.pdf` (28 pages, SHA-256 `186ca140e94dc60d1a2358154bbd4dfc43d339709873f885cc2d52d6245a6c0b`) + `.txt` (pdftotext -enc UTF-8; Table 2 is garbled in the text, use the arXiv HTML). Downloaded 2026-11-24. Git-ignored.

## TL;DR
POSSM tokenises single spikes (as POYO does), uses cross-attention to read a chunk, and a recurrent state-space backbone to carry state over time. It is causal and fast. Pretraining on monkey reaching data helps a human handwriting classification task.

## Key facts
| Item | Value | Where |
|---|---|---|
| Speed | "comparable to state-of-the-art Transformers, at a fraction of the inference cost (up to 9× faster on GPU)"; CPU about 2.44–5.65 ms per chunk | Abstract; §3 |
| Pretraining data | "four NHP reaching datasets": Perich et al. 2025, O'Doherty et al. 2020, Churchland et al. 2012, NLB'21 (Maze); 148 sessions, 26,032 units | §3.1 |
| Handwriting task | Willett 2021 T5 data, single characters and lines, **classification** (not sentence decoding) | §3.2 |
| Table 2 (accuracy %) | from scratch: POSSM-S4D 92.11 ± 6.66, POSSM-Mamba 92.95 ± 4.96, POSSM-GRU 95.82 ± 3.41; NHP-pretrained + fine-tuned: o-POSSM-S4D 97.25 ± 2.88, o-POSSM-Mamba 97.73 ± 2.13, o-POSSM-GRU 97.37 ± 2.32 | Table 2 |
| Stated gain | "2% for POSSM-GRU and more than 5% for both POSSM-S4D and POSSM-Mamba" | §3.2 |
| Speech | Willett 2023 / Brain-to-Text '24 data (T12), PER without LM: GRU 30.06, POSSM-GRU 27.32; multi-input variants 21.74 vs 19.80 | Table 3 |

> **Contradiction:** the F3 literature report (2026-11-24, scratch notes) listed o-POSSM-S4D as 97.73 ± 2.56 and o-POSSM-GRU as 97.25 ± 2.30. Table 2 gives the values above (S4D 97.25 ± 2.88, Mamba 97.73 ± 2.13, GRU 97.37 ± 2.32). The text's "2%" for GRU is 1.55 points in the table (95.82 → 97.37); a relative reading also gives about 1.6 %. We use the table.

## Limitations
- The handwriting result is classification of isolated characters, not open-vocabulary text.
- The speech result has no LM and is on T12, not T15.
- No dedicated limitations section found.

## Why it matters for us
- The best-supported pretraining source for T5 handwriting is **monkey motor cortex**, not EMG. An "M" arm (NHP motor data, CC BY on DANDI) is a cheap, licence-clean F3 arm.
- POSSM is a causal design; it fits our real-time NTS path.

## Feeds
- [North star F3](../questions/north-star.md#f3-cross-body-language-model-e1)
- [NLB MC_RTT](nlb-mc-rtt.md) (one of the pretraining sets), [Willett 2021 handwriting](../entities/willett-handwriting-2021.md)
- [NDT3](ndt3.md), [Levin et al. 2026](levin-cross-brain-transfer.md)
