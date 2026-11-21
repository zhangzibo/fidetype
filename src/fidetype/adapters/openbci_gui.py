"""OpenBCI GUI recording reader -> a signal source for ``fidetype live`` (P14-42, from the adapter template).

The OpenBCI GUI (v5 and later) saves a text file ``OpenBCI-RAW-*.txt``
(the sample files of the GUI: ``OpenBCI_GUI-*.txt``): ``%`` header lines
(``Sample Rate = 250 Hz``, ``Board = ...``), one column-name line
(``Sample Index, EXG Channel 0, ..., Timestamp, ...``) and one
comma-separated row per sample. EXG values are microvolts. The
reader keeps the EXG channels; a ``Marker Channel`` column (non-zero
values) becomes markers. Times: the first ``Timestamp`` plus
``index / sample_rate``. GUI v5 writes Unix seconds; the sample files of
the GUI (v6 layout) write Unix milliseconds, so a first stamp above
``1e11`` is read as milliseconds (P4-16). The packet stamps of the file
are not used, because they repeat inside a packet. Older GUI files (v4 and
before, no column-name line) raise ``ValueError``. Checked on the GUI
sample file ``OpenBCI_GUI-v6-blinks-jawClench-alpha.txt`` (P4-16). Our
own code (Apache-2.0), NumPy only.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path

import numpy as np

from fidetype.live.sources import ArraySource

ADAPTER_INFO = {
    "id": "openbci-gui", "kind": "file-reader", "signal": "eeg", "status": "tested",
    "file_patterns": ["OpenBCI-RAW-*.txt", "OpenBCI_GUI-*.txt"],
    "target": "OpenBCI GUI v5+ raw recordings (Cyton, Cyton + Daisy, Ganglion)",
    "licence": "Code Apache-2.0; no OpenBCI code used. Data: the licence of each recording.",
    "tests": ["tests/test_adapter_openbci_gui.py", "tests/test_adapter_files_real.py"],
    "docs": "docs/adapters.md#openbci-gui",
}


#: A first ``Timestamp`` above this is Unix milliseconds (1e11 s is year 5138; 1e11 ms is 1973).
MS_STAMP_ABOVE = 1e11


def _is_number(v: str) -> bool:
    try:
        float(v)
    except ValueError:
        return False
    return True


def read_openbci_gui(path: str | PathLike[str]) -> dict:
    """Read a GUI file. Return ``signal`` (N, C) float32, ``sample_rate``, ``labels``, ``t0``, ``markers``, ``board``."""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    head = {k.strip().lstrip("%").strip(): v.strip() for k, _, v in
            (ln.partition("=") for ln in lines if ln.startswith("%") and "=" in ln)}
    body = [ln for ln in lines if ln.strip() and not ln.startswith("%")]
    try:
        fs = float(head["Sample Rate"].split()[0])
        names = [c.strip() for c in body[0].split(",")]
        if names and _is_number(names[0]):
            raise ValueError("no column-name line (GUI v4 or older file); only the GUI v5+ layout is read")
        exg = [i for i, c in enumerate(names) if c.startswith("EXG Channel")]
        num = [c != "Timestamp (Formatted)" for c in names]
        rows = np.array([[float(v) if ok and v.strip() else np.nan for v, ok in zip(ln.split(","), num, strict=True)]
                         for ln in body[1:]])
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"not an OpenBCI GUI v5 file ({type(e).__name__}: {e})") from e
    if not exg or rows.ndim != 2 or rows.shape[0] == 0 or fs <= 0:
        raise ValueError("not an OpenBCI GUI v5 file: no 'EXG Channel' columns, no samples or bad sample rate")
    t0 = float(rows[0, names.index("Timestamp")]) if "Timestamp" in names else 0.0
    t0 = t0 / 1000.0 if t0 > MS_STAMP_ABOVE else t0  # milliseconds (GUI sample files), else seconds
    mk = []
    if "Marker Channel" in names:
        col = rows[:, names.index("Marker Channel")]
        mk = [(t0 + i / fs, f"{col[i]:g}") for i in np.flatnonzero(np.nan_to_num(col))]
    return {"signal": rows[:, exg].astype(np.float32), "sample_rate": fs, "labels": [names[i] for i in exg],
            "t0": t0, "markers": mk, "board": head.get("Board", "")}


def open_source(path: str | PathLike[str], modality: str = "eeg", speed: float = 0.0,
                chunk_s: float = 0.1) -> ArraySource:
    """An OpenBCI GUI file as a signal source (``speed`` 0: as fast as possible; 1: real time)."""
    r = read_openbci_gui(path)
    meta = {"device.modality": modality, "device.vendor": "OpenBCI", "device.channel_count": len(r["labels"]),
            "openbci.board": r["board"] or "unknown"}
    src = ArraySource(r["signal"], r["sample_rate"], r["markers"], speed, chunk_s, r["t0"],
                      f"openbci-gui:{Path(path).name}", modality, meta)
    src.info.update(channel_labels=r["labels"], channel_units=["microvolts"] * len(r["labels"]))
    return src
