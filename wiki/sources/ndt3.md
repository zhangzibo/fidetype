---
title: "NDT3: a generalist intracortical motor decoder (Ye et al. 2025)"
type: source
tags: [implant, intracortical, foundation-model, pretraining, scaling, transformer, motor, f3]
sources: [ndt3]
updated: 2026-11-24
---

# NDT3 (Ye et al. 2025)

## Citation and links
- J. Ye, F. Rizzoglio, X. Ma, A. Smoulder, H. Mao, G. Blumenthal, ..., L. Wehbe, R. A. Gaunt (23 authors). "A Generalist Intracortical Motor Decoder." NeurIPS 2025 Main Conference Track (doi 10.52202/085713-3692). Preprint bioRxiv 10.1101/2025.02.02.634313.
- **Licence:** preprint CC BY-NC (bioRxiv API `cc_by_nc`); we store no PDF. Code `joel99/ndt3`: MIT. Weights (Hugging Face `joel99/ndt3`): CC BY-NC 4.0 (non-commercial).
- **Local raw path:** none. NeurIPS 2025 proceedings abstract and PDF read on 2026-11-24 (not stored).

## TL;DR
An autoregressive Transformer pretrained on about 2,000 hours of intracortical spiking paired with motor variables, from over 30 monkeys and humans. Fine-tuned NDT3 beats from-scratch models **only when the downstream task has less than about 1.5 hours of data**. Above that, it matches them.

## Key facts
| Item | Value | Where |
|---|---|---|
| Pretraining | "2000 hours of neural population spiking activity paired with diverse motor covariates from over 30 monkeys and humans" (exact: 1,750 h, rounded to 2 kh) | Abstract; §2 |
| Data-regime result | tuned NDT3 "improve[s] over task-specific models trained from scratch when task data is under 1.5 hours, and match[es] them beyond this limit" | §1, Fig. 1B |
| Scaling note | "further scaling of NDT-style neural decoders will mainly be productive at downstream data scales <1.5 hours" | §3.1 |
| Limits of scale | "scaling autoregressive Transformers seems unlikely to resolve limitations stemming from sensor variability and output stereotypy" | proceedings PDF |
| Compute | 350M / 2 kh model: about 20K A100-hours; 45M / 200 h: 480 A100-hours | proceedings PDF |
| Evaluation | four human and four monkey datasets; downstream monkeys held out from pretraining | proceedings PDF |

## Limitations (stated)
- Transfer is "pathologically sensitive to shifts in data input dimensions"; scale "does not improve generalization to new behaviors".
- The largest model uses private pretraining data. Weights are non-commercial.

## Why it matters for us
- It sets the expected data regime for any pretraining gain: below about 1.5 h. Our P15-50 runs at about 8.4 h, so the expected outcome is no gain. This is not evidence against F3 (a low-data claim).
- The NC weight licence keeps NDT3 out of any shippable product weights.

## Feeds
- [North star F3](../questions/north-star.md#f3-cross-body-language-model-e1)
- [Data scaling](../concepts/data-scaling.md)
- [POSSM](possm.md), [Levin et al. 2026](levin-cross-brain-transfer.md), [FALCON](falcon-benchmark.md)
