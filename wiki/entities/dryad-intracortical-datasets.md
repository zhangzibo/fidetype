---
title: Dryad intracortical brain-to-text datasets (CC0)
type: entity
tags: [dataset, implant, intracortical, handwriting, speech, cc0, licence-clean]
sources: [neural-input-landscape-2026]
updated: 2026-11-10
---

# Dryad intracortical datasets

These are public intracortical brain-to-text datasets on Dryad. Dryad deposits are under **CC0**. They are the only commercially clean decoded-text data from brain recordings that we found ([landscape report](../sources/neural-input-landscape-2026.md#data-warning)). Sizes were checked on the Dryad pages on 2026-11-10 ([public datasets survey](../questions/public-datasets.md)).

| Dataset | Content | Size | DOI | Page |
|---|---|---|---|---|
| Willett et al. 2021, handwriting | Attempted handwriting, T5. 10.7 h, 1,000 sentences, 43,501 characters | 1.41 GB | doi:10.5061/dryad.wh70rxwmv | [Willett 2021 handwriting](willett-handwriting-2021.md) |
| Willett et al. 2023 / Brain-to-Text '24 | Attempted speech, T12. 12,100 sentences, 20 ms bins. Includes 3-gram and 5-gram LMs | 80.44 GB (competitionData 3.67 GB) | doi:10.5061/dryad.x69p8czpq | — |
| Card et al. / Brain-to-Text '25 | Attempted speech, T15. 11,000+ trials, 45 sessions, RNN logits, pretrained RNN | 11.59 GB | doi:10.5061/dryad.dncjsxm85 | [Brain-to-Text '25](brain-to-text-25.md) |
| Kunz et al., inner speech | Inner speech in motor cortex | not checked | doi:10.5061/dryad.gf1vhhn1j | — |

**Code licences:** the related GitHub repos have no licence (`nejm-brain-to-text`, `speechBCI`) or `NOASSERTION` (`handwritingBCI`). The data is CC0, but we must write our own loaders.

> **Our take:** These datasets are the key data asset for the trust layer. A decoder (for example the pretrained RNN) produces real decoded text with real errors. We can then evaluate calibration, conformal sets, the guard and the policy on it with no NC licence trap. Offline replay of these datasets is adapter priority 3 ([architecture](../questions/architecture.md#adapter-priority-2026-11-08)). The data is invasive, so it does not replace non-invasive data for Paper 1.

Related: [emg2qwerty](emg2qwerty.md), [SpanishBCBL dataset](spanishbcbl-dataset.md), [KT-sEMG](kt-semg-dataset.md).
