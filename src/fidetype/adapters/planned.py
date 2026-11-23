"""Planned adapters (P14-42): devices and public datasets that have **no code yet**.

The registry (:mod:`fidetype.adapters.registry`) shows these rows as
``planned``. A planned row is never support. When an adapter exists, its
module declares its own ``ADAPTER_INFO`` and the row moves out of this
list (the registry refuses an id that is both planned and implemented).

Licence notes say "not checked" until somebody reads the licence of the
SDK, protocol or dataset. Check it before you write the adapter.
Sources of the list: roadmap P4-05 (consumer-device adapters), P4-15
(device support matrix), P18-01 / P18-02 (open EMG wristband).
"""

from __future__ import annotations

_R = "wiki/questions/roadmap-standard.md"

PLANNED: list[dict] = [
    # --- devices (non-invasive) ---
    {"id": "muse", "kind": "device-source", "signal": "eeg", "target": "Interaxon Muse 2 / Muse S headband (4-channel EEG)",
     "licence": "Not checked. BrainFlow lists Muse boards (BrainFlow is MIT).", "roadmap": "P4-05",
     "docs": f"{_R}#p4-15-device-support-matrix-generated-from-adapter-metadata"},
    {"id": "openbci-cyton-board", "kind": "device-source", "signal": "eeg",
     "target": "OpenBCI Cyton / Ganglion on a real board (code exists in brainflow; a real-board test does not)",
     "licence": "BrainFlow is MIT. Needs hardware (externally blocked).", "roadmap": "P4-06",
     "docs": "wiki/entities/brainflow.md"},
    {"id": "unicorn", "kind": "device-source", "signal": "eeg", "target": "g.tec Unicorn Hybrid Black (8-channel EEG)",
     "licence": "Not checked (vendor SDK and LSL app).", "roadmap": "P4-05", "docs": _R},
    {"id": "emotiv", "kind": "device-source", "signal": "eeg", "target": "Emotiv EPOC X / Insight",
     "licence": "Not checked. The vendor SDK is proprietary; an adapter may need a vendor licence.", "roadmap": "P4-05",
     "docs": _R},
    {"id": "neurosity-crown", "kind": "device-source", "signal": "eeg", "target": "Neurosity Crown (8-channel EEG)",
     "licence": "Not checked (vendor SDK; BrainFlow lists the board).", "roadmap": "P4-05", "docs": _R},
    {"id": "brainvision-lsl", "kind": "device-source", "signal": "eeg",
     "target": "Brain Products amplifiers (LiveAmp, actiCHamp) through their LSL connector",
     "licence": "Not checked (vendor LSL connector). The LSL path itself exists (lsl-signal-source).",
     "roadmap": "P4-05", "docs": "wiki/concepts/lsl-input.md"},
    {"id": "emg-wristband", "kind": "device-source", "signal": "emg",
     "target": "Open low-cost sEMG wristband (our reference design) as NTS over LSL",
     "licence": "Our own design (planned open hardware licence).", "roadmap": "P18-02",
     "docs": f"{_R}#p18-02-wristband-driver-and-adapter"},
    {"id": "consumer-emg-band", "kind": "device-source", "signal": "emg",
     "target": "Consumer sEMG wristbands (for example Myo-class bands)",
     "licence": "Not checked (vendor protocols; some bands are discontinued).", "roadmap": "P4-05", "docs": _R},
    {"id": "fnirs-lsl", "kind": "device-source", "signal": "fnirs", "target": "fNIRS systems that stream LSL (for example NIRx, Artinis)",
     "licence": "Not checked (vendor software).", "roadmap": "P4-05", "docs": _R},
    {"id": "opm-meg", "kind": "device-source", "signal": "opm-meg", "target": "OPM-MEG systems (wearable MEG)",
     "licence": "Not checked (vendor software; lab hardware only).", "roadmap": "P4-05", "docs": _R},
    # --- file formats and public datasets ---
    {"id": "xdf", "kind": "file-reader", "signal": "any", "target": "XDF files (LabRecorder recordings of LSL streams)",
     "licence": "Open format. pyxdf licence not checked (a reader of our own needs no dependency).",
     "roadmap": "P14-42", "docs": "wiki/concepts/lsl-input.md"},
    {"id": "brainvision-file", "kind": "file-reader", "signal": "eeg", "target": "BrainVision files (.vhdr / .eeg / .vmrk)",
     "licence": "Open format; not checked.", "roadmap": "P14-42", "docs": _R},
    {"id": "bids-eeg", "kind": "dataset-reader", "signal": "eeg",
     "target": "BIDS-EEG datasets (for example OpenNeuro EEG studies) and MOABB-listed BCI datasets",
     "licence": "Per dataset (often CC0 or CC BY 4.0); check each one. MOABB licence not checked.", "roadmap": "P14-42",
     "docs": _R},
    {"id": "gdf", "kind": "file-reader", "signal": "eeg", "target": "GDF files (for example BCI Competition IV 2a / 2b)",
     "licence": "Open format. Competition data terms not checked.", "roadmap": "P14-42", "docs": _R},
    {"id": "inner-speech-eeg", "kind": "dataset-replay", "signal": "eeg",
     "target": "Public inner / imagined speech EEG datasets (for example 'Thinking out loud', Kara One)",
     "licence": "Not checked; check each dataset.", "roadmap": "P14-42", "docs": _R},
    {"id": "zuco", "kind": "dataset-replay", "signal": "eeg", "target": "ZuCo (EEG and eye tracking during natural reading)",
     "licence": "Not checked.", "roadmap": "P14-42", "docs": _R},
]
