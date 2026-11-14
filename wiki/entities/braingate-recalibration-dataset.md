---
title: BrainGate long-term unsupervised recalibration dataset (Wilson et al. 2025, Dryad)
type: entity
tags: [dataset, implant, intracortical, utah-array, cursor, closed-loop, human, cc0, licence-clean, p12]
sources: []
updated: 2026-11-14
---

# BrainGate long-term unsupervised recalibration dataset

- **Citation**: G. Wilson, E. Stein, F. Kamdar, D. Avansino, T. Pun, R. Gross, T. Hosman, T. Singer-Clark, A. Kapitonava, L. Hochberg, J. Simeral, K. Shenoy, S. Druckmann, J. Henderson, et al., "Long-term unsupervised recalibration of cursor BCIs", *Nature Biomedical Engineering* (2025), doi:10.1038/s41551-025-01536-z. Preprint doi:10.1101/2023.02.03.527022.
- **Link**: https://doi.org/10.5061/dryad.1jwstqk6g (Dryad, version 4, published 2025-05-29). Code: https://github.com/guyhwilson/nonstationarities (not used; we write our own loaders).
- **Licence**: **CC0 1.0** (Dryad API `license` field, re-checked 2026-11-14; it matches the [P12-06 survey](../questions/intent-datasets-survey.md)). No extra usage notes in the Dryad metadata.
- **Content (from the Dryad abstract)**: closed-loop 2D cursor sessions of participant **T5** (historical sessions 2016-2020 and new online tests of recalibration methods), plus parameter-optimisation results and cursor simulations. Four data formats, described in the README. Personal-use data of T11 is **not** included, because it may contain PHI.
- **Files (Dryad API)**: `PRIT_paper_data.tar.gz` (1,685,533,203 bytes) and `README.md` (10,938 bytes), with SHA-256 digests (see [`references/README.md`](../../references/README.md)).
- **Status**: **not downloaded.** On 2026-11-14 the Dryad file API answered HTTP 401 ("must have current bearer token"). A Dryad API account, or a manual browser download by the user to `C:\Users\zhang\bci-data\raw\braingate-recal\`, is needed. We did not try to bypass this.

## Data handling (when downloaded)
- CC0 has no legal conditions. We still follow the community norms: cite the paper and the Dryad DOI; never try to re-identify the participant; never commit raw data (aggregate numbers only, as for all data in this public repo).
- Check the SHA-256 against the Dryad digest. List the tar before extraction (no absolute paths, no `..`), extract only data files, and read pickles or MATLAB files with safe loaders.

## Fit for Fidetype
| Use | Fit | Why |
|---|---|---|
| Control profile (FEP-0005) evaluation | ✔ | **Human, closed loop**: the user saw the cursor and corrected it. Real decoder drift over years |
| Drift alarms, recalibration | ✔ | Sessions over four years, with recalibration tests |
| Click (intent profile) | ? | Not stated in the abstract; check the README |

> **Our take:** the best licence-clean human cursor set we found. It should repeat the P12-03 MC_RTT tests on human closed-loop data, where the per-tick speed bound may behave differently (see [control events](../concepts/control-events.md)).

Related: [Dryad intracortical datasets](dryad-intracortical-datasets.md) · [NLB MC_RTT](../sources/nlb-mc-rtt.md) · [Intent and control datasets](../questions/intent-datasets-survey.md)
