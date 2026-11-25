---
title: "FALCON: few-shot algorithms for consistent neural decoding benchmark (Karpowicz et al. 2024)"
type: source
tags: [benchmark, implant, intracortical, few-shot, recalibration, handwriting, t5, h2, dandi, cc-by, f3]
sources: [falcon-benchmark]
updated: 2026-11-24
---

# FALCON benchmark (Karpowicz et al. 2024)

## Citation and links
- B. M. Karpowicz, J. Ye, C. Fan, P. Tostado-Marcos, F. Rizzoglio, C. Washington, ..., R. A. Gaunt, J. L. Collinger, C. Pandarinath (22 authors). "Few-shot Algorithms for Consistent Neural Decoding (FALCON) Benchmark." NeurIPS 2024 Datasets and Benchmarks Track (doi 10.52202/079017-2439). https://proceedings.neurips.cc/paper_files/paper/2024/hash/8c2e6bb15be1894b8fb4e0f9bcad1739-Abstract-Datasets_and_Benchmarks_Track.html . Preprint bioRxiv 10.1101/2024.09.15.613126.
- **Licence:** paper: no Creative Commons licence (bioRxiv API `cc_no`); we store no PDF. Data: CC BY 4.0 (DANDI). Code `snel-repo/falcon-challenge`: MIT.
- **Local raw path:** none. Proceedings abstract and PDF read on 2026-11-24 (not stored); DANDI API read on 2026-11-24.

## TL;DR
Five multi-session decoding datasets (H1 human reach, H2 human handwriting, M1 and M2 monkey, B1 birdsong). Each has **held-in** sessions for training and later **held-out** sessions with only a few calibration trials. The test labels are private on an EvalAI server, which needs causal, open-loop predictions.

## Key facts
| Item | Value | Where |
|---|---|---|
| H2 task | T5 (BrainGate2), "open-loop attempted handwriting"; 192 channels, 20 ms bins; letters, 4 punctuation marks, ">" for space | §A.3.6 |
| H2 sessions | "21 held-in sessions over 287 days (7-45 minutes of calibration data each) and 5 held-out sessions over 176 days (1-2 minutes of calibration data provided)" | §A.3.6 |
| H2 dates | held-in `ses-20220518` to `ses-20230228`; held-out 2023-04-17 to 2023-10-09 (DANDI file names). So H2 is **new T5 data**, not the [Willett 2021](../entities/willett-handwriting-2021.md) recordings (our inference from the dates; the paper cites Willett 2021 for the protocol) | DANDI 000950 |
| Few-shot rule | "For held-out sessions, only 3 trials are released for few-shot calibration"; 40 % of trials reserved for evaluation | §A.3.6 |
| Metric (H2) | word error rate (WER) | §2 |
| H2 baselines (held-out WER) | oracle RNN 0.15, + LM 0.03; zero-shot RNN 0.53, + LM 0.37; CORP (test-time adaptive) 0.11 | Table 1 |
| Evaluation | "private evaluation data"; EvalAI challenge 2319, 6-hour limit per submission | Abstract; README |
| Data licences | H2 DANDI 000950 v0.241029.1403, M1-A 000941: `spdx:CC-BY-4.0`; M2 000953 and H1 000954: drafts with CC-BY-4.0 metadata | DANDI API |

## Limitations (stated)
- "it evaluates open loop prediction, not closed loop iBCI control".
- Constrained behaviour with trial structure; too little subject diversity to test new subjects.

## Why it matters for us
- It is the **community protocol for minutes-scale F3** on handwriting. Our own E1 protocol is bespoke; numbers on FALCON H2 can be compared with other groups ([Chen et al. 2026](chen-falcon-h2-fewshot.md)).
- The F3 small-data pre-registration uses it: [plan](../../experiments/2026-11-25-f3-small-data-falcon/plan.md).
- A public test-set score needs the EvalAI server; local work can use only the held-in data and the 3 released held-out calibration trials.

## Feeds
- [Willett 2021 handwriting](../entities/willett-handwriting-2021.md), [intent datasets survey](../questions/intent-datasets-survey.md), [public datasets](../questions/public-datasets.md)
- [Chen et al. 2026](chen-falcon-h2-fewshot.md), [CORP](corp.md), [NDT3](ndt3.md)
