---
title: Dryad intracortical brain-to-text datasets (CC0)
type: entity
tags: [dataset, implant, intracortical, handwriting, speech, cc0, licence-clean]
sources: [neural-input-landscape-2026]
updated: 2026-11-08
---

# Dryad intracortical datasets

These are public intracortical brain-to-text datasets on Dryad. Dryad deposits are under **CC0**. They are the only commercially clean decoded-text data we found ([landscape report](../sources/neural-input-landscape-2026.md#data-warning)).

| Dataset | Content | DOI |
|---|---|---|
| Willett et al. 2021, handwriting | Intracortical recordings during attempted handwriting | doi:10.5061/dryad.wh70rxwmv |
| Brain-to-Text '24 | Intracortical speech-to-text benchmark data | — |
| Card et al. / Brain-to-Text '25 | Intracortical speech-to-text data, with a pretrained RNN | doi:10.5061/dryad.dncjsxm85 |

> **Our take:** These datasets are the key data asset for the trust layer. A decoder (for example the pretrained RNN) can produce real decoded text with real errors. We can then evaluate calibration, conformal sets, the guard and the policy on it with no NC licence trap. This makes commercially clean trust-layer evaluation possible. Offline replay of these datasets is adapter priority 3 ([architecture](../questions/architecture.md#adapter-priority-2026-11-08)). The data is invasive, so it does not replace non-invasive data for Paper 1.

Related: [emg2qwerty](emg2qwerty.md), [SpanishBCBL dataset](spanishbcbl-dataset.md).
