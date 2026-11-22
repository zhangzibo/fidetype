"""OpenBCI GUI recording reader -> a signal source for ``fidetype live`` (P14-42, from the adapter template).

The OpenBCI GUI (v5 and later) saves a text file ``OpenBCI-RAW-*.txt``
(the sample files of the GUI: ``OpenBCI_GUI-*.txt``): ``%`` header lines
(``Sample Rate = 250 Hz``, ``Board = ...``), one column-name line
(``Sample Index, EXG Channel 0, ..., Timestamp, ...``) and one
comma-separated row per sample. EXG values are microvolts. The
reader keeps the EXG channels; a ``Marker Channel`` column (non-zero
values) becomes markers. Times: the first ``Timestamp`` plus
``(row + samples lost before the row) / sample_rate``. GUI v5 writes
Unix seconds; the sample files of the GUI (v6 layout) write Unix
milliseconds, so a first stamp above ``1e11`` is read as milliseconds
(P4-16). The packet stamps of the file
are not used, because they repeat inside a packet. Older GUI files (v4 and
before, no column-name line) raise ``ValueError``.

**Packet drops (P4-18).** On a Cyton board the ``Sample Index`` counts
0..255 and wraps (a wrap is not a drop). It steps by 1 (Cyton) or by 2
(Cyton + Daisy: one row per two radio packets). An index step ``d`` other
than that is a drop of ``((d - step) mod 256) / step`` rows (the same
index twice is an error, unless the stamps show one full cycle lost). If the ``Timestamp`` column shows
that whole index cycles were lost too, they are added. ``on_drop``:

- ``"gap"`` (default): keep every row. Rows after a drop get the correct
  later times, and the result lists the drops in ``gaps`` as
  ``(row, missing_frames)``. ``open_source`` gives them to
  ``fidetype.live.sources.ArraySource``, so the first chunk after a
  drop carries ``gap`` (LSL-G3 fields, ``cause`` = ``"sample_index"``) and
  ``fidetype live`` cuts the open segment there (spec LSL-G2).
- ``"error"``: a drop raises ``ValueError`` (row and size in the message).

Other boards (Ganglion and others) have other index rules; their index
is not checked (``index_checked`` False). Real files read: the GUI
sample file ``OpenBCI_GUI-v6-blinks-jawClench-alpha.txt`` (P4-16; ms
stamps), a Cyton GUI v5.0 file with 20 drops (seconds stamps) and a
Cyton + Daisy GUI v5+ file with a ``Marker Channel`` (all zero) (P4-18).
Our own code (Apache-2.0), NumPy only.
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
    "tests": ["tests/test_adapter_openbci_gui.py", "tests/test_adapter_files_real.py",
              "tests/test_adapter_openbci_gui_real.py"],
    "docs": "docs/adapters.md#openbci-gui",
    "support": "replay-only", "transport": ["file"],
    "real_data_evidence": ["tests/test_adapter_files_real.py", "tests/test_adapter_openbci_gui_real.py"],
    "test_covers": "CI: synthetic GUI files and packet drops (Sample Index jumps). Real: the OpenBCI "
                   "GUI v6 sample file (Cyton, millisecond time stamps) and two GUI v5 recordings "
                   "(Cyton 8 ch; Cyton + Daisy 16 ch), local tests.",
    "limits": "No real recording with non-zero markers (P4-19). The Ganglion Sample Index rule is not"
              " checked (P4-20). GUI v4 files are refused. A file, not a live board.",
}


#: A first ``Timestamp`` above this is Unix milliseconds (1e11 s is year 5138; 1e11 ms is 1973).
MS_STAMP_ABOVE = 1e11


def _is_number(v: str) -> bool:
    try:
        float(v)
    except ValueError:
        return False
    return True


#: The Cyton ``Sample Index`` wraps after 255.
INDEX_CYCLE = 256

ON_DROP = ("gap", "error")


def find_drops(index: np.ndarray, stamps: np.ndarray | None, fs: float) -> tuple[int, list[tuple[int, int]]]:
    """Packet drops in a Cyton ``Sample Index`` column. Return ``(step, [(row, missing_frames), ...])``.

    ``step`` is 1 (Cyton) or 2 (Cyton + Daisy), the most common step mod 256.
    Row ``row`` follows ``missing_frames`` lost rows. ``stamps`` (seconds, or
    None) adds whole lost index cycles when the time jump shows them.
    """
    idx = np.asarray(index, dtype=np.int64)
    if idx.size < 2:
        return 1, []
    d = np.diff(idx) % INDEX_CYCLE
    vals, counts = np.unique(d, return_counts=True)
    step = int(vals[np.argmax(counts)])
    if step not in (1, 2):
        raise ValueError(f"Sample Index: the most common step is {step}, not 1 (Cyton) or 2 (Cyton + Daisy)")
    cycle = INDEX_CYCLE // step
    drops = []
    for k in np.flatnonzero(d != step):
        dk = int(d[k])
        if dk % step:
            raise ValueError(f"Sample Index: data row {k + 1} steps by {dk}, not a multiple of {step}")
        miss = ((dk - step) % INDEX_CYCLE) // step  # rows lost, modulo one index cycle
        has_t = stamps is not None and bool(np.isfinite(stamps[k:k + 2]).all())
        seen = (stamps[k + 1] - stamps[k]) * fs if has_t else None  # rows that the time stamps show
        if dk == 0:  # the same index again: a repeated row, or one full index cycle lost
            if seen is None or seen < cycle / 2:
                raise ValueError(f"Sample Index: data row {k + 1} repeats index {int(idx[k + 1])}")
            miss = cycle - 1
        if seen is not None:
            miss += cycle * max(0, int(round((seen - (miss + 1)) / cycle)))
        drops.append((int(k + 1), int(miss)))
    return step, drops


def read_openbci_gui(path: str | PathLike[str], on_drop: str = "gap") -> dict:
    """Read a GUI file. Return ``signal`` (N, C) float32, ``sample_rate``, ``labels``, ``t0``, ``markers``,
    ``board``, ``gaps`` (``(row, missing_frames)``), ``index_checked`` and ``times`` (N,) float64 seconds."""
    if on_drop not in ON_DROP:
        raise ValueError(f"on_drop must be one of {ON_DROP}, got {on_drop!r}")
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
    board = head.get("Board", "")
    t0 = float(rows[0, names.index("Timestamp")]) if "Timestamp" in names else 0.0
    scale = 1e-3 if t0 > MS_STAMP_ABOVE else 1.0  # milliseconds (GUI sample files), else seconds
    t0 *= scale
    gaps: list[tuple[int, int]] = []
    checked = "Cyton" in board and "Sample Index" in names
    if checked:
        idx = rows[:, names.index("Sample Index")]
        if not np.isfinite(idx).all():
            raise ValueError("not an OpenBCI GUI v5 file: empty or non-numeric Sample Index values")
        stamps = rows[:, names.index("Timestamp")] * scale if "Timestamp" in names else None
        _, gaps = find_drops(idx, stamps, fs)
        if gaps and on_drop == "error":
            r, m = gaps[0]
            raise ValueError(f"packet drop: {len(gaps)} Sample Index jumps, {sum(g[1] for g in gaps)} samples lost "
                             f"(first: {m} before data row {r}); read with on_drop='gap' to keep the file with gaps")
    add = np.zeros(rows.shape[0], np.int64)
    for r, m in gaps:
        add[r] += m
    times = t0 + (np.arange(rows.shape[0]) + np.cumsum(add)) / fs
    mk = []
    if "Marker Channel" in names:
        col = rows[:, names.index("Marker Channel")]
        mk = [(float(times[i]), f"{col[i]:g}") for i in np.flatnonzero(np.nan_to_num(col))]
    return {"signal": rows[:, exg].astype(np.float32), "sample_rate": fs, "labels": [names[i] for i in exg],
            "t0": t0, "markers": mk, "board": board, "gaps": gaps, "index_checked": checked, "times": times}


def open_source(path: str | PathLike[str], modality: str = "eeg", speed: float = 0.0,
                chunk_s: float = 0.1, on_drop: str = "gap") -> ArraySource:
    """An OpenBCI GUI file as a signal source (``speed`` 0: as fast as possible; 1: real time).

    Packet drops (``on_drop``, module docstring) become ``gap`` chunks; the
    meta keys ``openbci.packet_drops`` and ``openbci.samples_lost`` count them.
    """
    r = read_openbci_gui(path, on_drop)
    meta = {"device.modality": modality, "device.vendor": "OpenBCI", "device.channel_count": len(r["labels"]),
            "openbci.board": r["board"] or "unknown", "openbci.sample_index_checked": r["index_checked"],
            "openbci.packet_drops": len(r["gaps"]), "openbci.samples_lost": sum(m for _, m in r["gaps"])}
    src = ArraySource(r["signal"], r["sample_rate"], r["markers"], speed, chunk_s, r["t0"],
                      f"openbci-gui:{Path(path).name}", modality, meta, gaps=r["gaps"], gap_cause="sample_index")
    src.info.update(channel_labels=r["labels"], channel_units=["microvolts"] * len(r["labels"]))
    return src
