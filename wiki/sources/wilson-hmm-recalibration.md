---
title: "Long-term unsupervised recalibration of cursor iBCIs with a hidden Markov model (Wilson et al. 2025)"
type: source
tags: [implant, intracortical, cursor, t5, unsupervised, recalibration, pseudo-labels, hmm, f1]
sources: [wilson-hmm-recalibration]
updated: 2026-11-24
---

# Wilson et al. 2025: HMM target inference for recalibration

## Citation and links
- G. H. Wilson, E. A. Stein, F. Kamdar, D. T. Avansino, T. K. Pun, R. Gross, ..., J. M. Henderson, F. R. Willett (15 authors). "Long-term unsupervised recalibration of cursor-based intracortical brain–computer interfaces using a hidden Markov model." *Nature Biomedical Engineering* 10(7):1466–1484; online 2025-12-08, issue July 2026. https://doi.org/10.1038/s41551-025-01536-z (PMC13375652). Preprint bioRxiv 10.1101/2023.02.03.527022.
- **Licence:** CC BY 4.0 (article text).
- **Local raw path:** `references/papers/wilson_2025_natbiomedeng_s41551-025-01536-z.pdf` (53 pages, SHA-256 `c3cf1afeb4d02edb13af3832eebda56627a563b41279aa4ea939897ca9f4d699`) + `.txt`. Downloaded 2026-11-24. Git-ignored.
- Data: [BrainGate recalibration dataset](../entities/braingate-recalibration-dataset.md) (Dryad, CC0).

## TL;DR
A hidden Markov model infers which target the user moves the cursor to. The decoder is then retrained on these inferred targets, with no labels (method PRI-T, "probabilistic retrospective inference of targets"). Over five years of T5 data, target inference keeps working, while methods that only match data distributions drift away.

## Key facts
| Item | Value | Where |
|---|---|---|
| Method | "a hidden Markov model to infer which targets users are moving towards during iBCI use and we retrain the system using these inferred targets"; Viterbi path + marginal-probability weights | Abstract; Fig. 2 |
| Main finding | "target inference recalibration methods appear capable of long-term unsupervised recalibration, whereas recently proposed data-distribution-matching approaches appear to accumulate compounding errors over time" | Abstract |
| Data | "73 recording sessions spanning five years" (2016–2021), T5; offline personal-use data from T11 | Results; Methods |
| Closed loop | 28 days with T5; fixed decoder trial times 6.83 ± 3.03 s (day 14) and 3.61 ± 2.12 s (day 28) | Results; Discussion |
| Open-loop gain | "0.14 ± 0.078 increase in correlation or 81% relative improvement" over FA stabilisation (week 2) | Results |
| Limit of all methods | "all methods fail when day pairs are separated by large amounts of time" | Results |

## Limitations (stated)
- Single closed-loop participant; "T5's neural signals are unusually unstable relative to those of other iBCI users" is one hypothesis.
- More hyperparameters and a Viterbi search cost.
- Cursor control, not text. No error bound.

## Why it matters for us
It supports our F1 arm choice: labels inferred from the task (our accept / retype feedback) are safer than self-training or distribution matching. It is a warning for any unsupervised arm in E2.

## Feeds
- [BrainGate recalibration dataset](../entities/braingate-recalibration-dataset.md)
- [CORP](corp.md), [Card et al. 2026](card-2026-home-use.md)
- [E2 self-teaching write-up](../questions/frontier-e2-self-teaching.md)
