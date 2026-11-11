---
title: Toronto sEMG typing dataset (Achituve et al. 2025)
type: entity
tags: [dataset, emg, typing, cc-by, licence-clean, cross-subject]
sources: []
updated: 2026-11-10
---

# Toronto sEMG typing dataset

- **Citation**: Achituve, Beutel, Eby, Fetaya, Koivisto, Zariffa, *Electromyographic typing gesture classification dataset for neurotechnological human-machine interfaces*, Scientific Data 12:440 (2025), doi:10.1038/s41597-025-04763-w.
- **Link**: https://doi.org/10.5683/SP3/KV65VI (University of Toronto Dataverse, Borealis)
- **Licence**: **CC BY 4.0** (Borealis API, verified 2026-11-10). Commercial use: yes, with attribution. The baseline code `ANSLab-UHN/sEMG-TypingDatabase` is **CC BY-SA 4.0**. Do not copy it into our code.
- **Participants**: 19 uninjured adults (5 male, 14 female, 31 ± 7 years), 2 sessions on different days.
- **Signal**: 16 bipolar sEMG channels (8 pairs per arm), 2 kHz, filtered 10–500 Hz.
- **Labels**: keylogger with a timestamp per key press. 27 classes (26 letters + space).
- **Size**: one zip, 2.77 GB (Borealis API). Hours: not stated.

## Fit for Fidetype
| Use | Fit | Why |
|---|---|---|
| (a) decoder training | ✔ | Cross-subject and cross-session |
| (b) trust-layer / eWPM | ~ | Key timing yes. Text structure not checked |
| (c) adapter conformance | ✔ | A third EMG layout (16 bipolar channels) |
| (d) pretraining | ~ | Small |

> **Our take:** Small, but the only commercially clean EMG typing set with many people. Use it for cross-subject tests of an EMG adapter, together with [KT-sEMG](kt-semg-dataset.md).

Related: [emg2qwerty](emg2qwerty.md) · [Public datasets survey](../questions/public-datasets.md)
