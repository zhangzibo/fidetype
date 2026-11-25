---
title: Penn RAM and PEERS memory datasets (OpenNeuro)
type: entity
tags: [dataset, ieeg, eeg, memory, free-recall, cc0, licence-clean, openneuro, bids]
sources: []
updated: 2026-11-24
---

# Penn RAM and PEERS memory datasets

Public memory-task recordings from the Computational Memory Lab (Kahana lab, University of Pennsylvania) on OpenNeuro, in [BIDS](bids.md). Used by experiment [B1](../../experiments/2026-11-24-b1-memory-state-gate/plan.md). Context: [Beyond words](../questions/beyond-words.md#memory-state).

- **Licence:** **CC0** for all four datasets below (`"License": "CC0"` in each `dataset_description.json`, read through the OpenNeuro API on 2026-11-24). No signature, no request form. Commercial use: allowed by CC0.
- **Funding (FR1):** DARPA RAM N66001-14-2-4032; NIH R01-NS-106611, U01-NS-113198.
- **Population (RAM):** epilepsy patients with clinical intracranial electrodes (subdural grids / strips and depth electrodes), recorded at several US hospitals. Electrode placement is clinical, so each subject has a unique montage.

| OpenNeuro id | Name | Snapshot | Subjects | Modality, task | Size |
|---|---|---|---|---|---|
| [ds004789](https://openneuro.org/datasets/ds004789) | Delayed Free Recall of Word Lists (RAM FR1) | 3.1.0, 2024-04-22, doi:10.18112/openneuro.ds004789.v3.1.0 | 280 (574 sessions per `CHANGES`) | iEEG, `FR1` | 618,808,962,711 bytes (618.8 GB), 7,425 files |
| [ds004809](https://openneuro.org/datasets/ds004809) | Categorized Free Recall (RAM catFR1) | 2.2.0, 2024-04-23 | 258 | iEEG, `catFR1` | 512.4 GB |
| [ds005557](https://openneuro.org/datasets/ds005557) | Free Recall with Closed-Loop Stimulation at Encoding (Encoding Classifier) | 1.0.0, 2024-10-06 | 18 | iEEG, `FR3` | 37.2 GB, 418 files |
| [ds004395](https://openneuro.org/datasets/ds004395) | Penn Electrophysiology of Encoding and Retrieval Study (PEERS) | 2.0.0, 2023-06-01 | 364 | scalp EEG, `ltpFR`, `ltpFR2`, `VFFR` | 9,583.3 GB |

## FR1 file layout (from the API file tree and one format check)
- Per session: `acq-bipolar_ieeg.edf` and `acq-monopolar_ieeg.edf` (+ `channels.tsv`, `ieeg.json`), `events.tsv` / `events.json`, MNI electrode coordinates, `beh/` copy of the events.
- The README says monopolar recordings "should always be re-referenced before analysis"; bipolar recordings use "a paired scheme". All voltages are scaled to V.
- Of all 618.8 GB, the bipolar EDF files are 323.3 GB. 23 subjects have no bipolar EDF. 74 subjects have at least 3 sessions with a bipolar EDF (167.9 GB).
- `events.tsv` columns: `onset`, `duration`, `sample`, `trial_type` (`WORD`, `REC_WORD`, `REC_WORD_VV`, `ORIENT`, `DISTRACT_START`, ...), `item_name`, `serialpos`, `list`, `answer`, `experiment`, `session`, `subject`. There is **no "recalled" column**; the label comes from matching `WORD` to `REC_WORD` in the same list. In one checked file, `sample` and `onset * fs` differ by a near-constant offset (about 282,345 samples at 500 Hz); B1 checks the alignment before use.
- Sampling rates 500, 1000 or 1600 Hz (Ezzyat et al. 2018); one checked session: 500 Hz, 54 ECoG + 18 sEEG bipolar channels.

## Known results on these data
- Ezzyat et al. 2018 (RAM, 25 patients): encoding classifier mean AUC 0.61 on new sessions. Li, Pazdera & Kahana 2024 (PEERS4 in ds004395, 88 analysed): encoding mean AUC 0.59 / 0.60. Details and citations: [Beyond words](../questions/beyond-words.md#memory-state).

## Use in Fidetype
- **B1** (pre-registered 2026-11-24): 30 FR1 subjects, bipolar files only, 56.79 GB. Data stays outside the repo (`C:/Users/zhang/bci-data/raw/penn-ram-fr1/`); only aggregates are committed.
- ds005557 is a candidate for an offline audit of real closed-loop stimulation decisions (B2, idea only).
