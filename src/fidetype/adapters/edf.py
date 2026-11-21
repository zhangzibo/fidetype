"""EDF / EDF+ / BDF file reader -> a signal source for ``fidetype live`` (P14-42, from the adapter template).

EDF (European Data Format, 16-bit) and BDF (BioSemi, 24-bit) are open,
documented formats (https://www.edfplus.info/specs/). Many EEG, EMG and
sleep systems export them. This reader is our own code (Apache-2.0),
with no dependency beyond NumPy. It reads continuous files (EDF, EDF+C,
BDF); EDF+D (discontinuous) raises ``ValueError``. The ``EDF/BDF
Annotations`` signal becomes markers. Samples are in physical units
(``channel_units``: the file's physical dimension, for example ``uV``).

Checked on real files (P4-16): PhysioNet EEGMMIDB EDF+C (ODC-By 1.0) and
the MNE-Python test EDF+C / BDF files (BSD-3-Clause) give the same values
as MNE within one digital step (``tests/test_adapter_files_real.py``,
local data only).

Privacy: the header fields "patient" and "recording" can hold personal
data. The reader never copies them into ``meta``.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Sequence

import numpy as np

from fidetype.live.sources import ArraySource

ADAPTER_INFO = {
    "id": "edf", "kind": "file-reader", "signal": "any", "status": "tested",
    "file_patterns": ["*.edf", "*.bdf"],
    "target": "EDF, EDF+ (continuous) and BDF files (many EEG, EMG and sleep systems)",
    "licence": "Code Apache-2.0; open format, no third-party code. Data: the licence of each file.",
    "tests": ["tests/test_adapter_edf.py", "tests/test_adapter_files_real.py"], "docs": "docs/adapters.md#edf",
}


def _s(raw: bytes) -> str:
    return raw.decode("ascii", "replace").strip()


def read_edf(path: str | PathLike[str], channels: Sequence[str] | None = None) -> dict:
    """Read a file. Return ``signal`` (N, C) float32, ``sample_rate``, ``labels``, ``units``, ``markers``, ``format``."""
    b = Path(path).read_bytes()
    bdf = b[:8] == b"\xffBIOSEMI"
    if not (bdf or b[:8] == b"0       ") or len(b) < 256:
        raise ValueError("not an EDF or BDF file (bad version field, or shorter than 256 bytes)")
    try:
        hdr, ns = int(_s(b[184:192])), int(_s(b[252:256]))
        nrec, dur = int(_s(b[236:244])), float(_s(b[244:252]))
        if ns < 1 or hdr != 256 * (ns + 1) or len(b) < hdr or dur <= 0:
            raise ValueError(f"signals {ns}, header bytes {hdr}, record {dur} s, file {len(b)} bytes")
        cols = {}
        off = 256
        for name, w in (("label", 16), ("trans", 80), ("dim", 8), ("pmin", 8), ("pmax", 8), ("dmin", 8),
                        ("dmax", 8), ("filt", 80), ("n", 8), ("res", 32)):
            cols[name] = [_s(b[off + i * w: off + (i + 1) * w]) for i in range(ns)]
            off += w * ns
        n = [int(v) for v in cols["n"]]
        p0, p1, d0, d1 = (np.array(cols[k], float) for k in ("pmin", "pmax", "dmin", "dmax"))
    except ValueError as e:
        raise ValueError(f"bad EDF header: {e}") from e
    if _s(b[192:236]).startswith("EDF+D"):
        raise ValueError("EDF+D (discontinuous) files are not supported")
    bps = 3 if bdf else 2
    rec_bytes = sum(n) * bps
    nrec = (len(b) - hdr) // rec_bytes if nrec < 0 else nrec
    if len(b) < hdr + nrec * rec_bytes:
        raise ValueError(f"file is truncated: {nrec} records need {hdr + nrec * rec_bytes} bytes, file has {len(b)}")
    raw = np.frombuffer(b, np.uint8, nrec * rec_bytes, hdr).reshape(nrec, sum(n) * bps)
    is_ann = [lab in ("EDF Annotations", "BDF Annotations") for lab in cols["label"]]
    want = [i for i in range(ns) if not is_ann[i] and (channels is None or cols["label"][i] in channels)]
    if not want or len({n[i] for i in want}) != 1:
        raise ValueError(f"need >= 1 signal with one sample rate; samples per record: {[n[i] for i in want]}")
    starts = np.cumsum([0] + n) * bps
    sig, markers = [], []
    for i in range(ns):
        blk = raw[:, starts[i]:starts[i + 1]].reshape(-1)
        if is_ann[i]:
            for tal in blk.tobytes().decode("utf-8", "replace").split("\x00"):
                onset, *texts = tal.split("\x14")
                markers += [(float(onset.split("\x15")[0]), t) for t in texts if t and onset]
        elif i in want:
            d = blk.view("<i2").astype(float) if not bdf else (
                blk.reshape(-1, 3).astype(np.int32) @ [1, 256, 65536]).astype(float)
            d = d - (d >= 2 ** 23) * 2 ** 24 if bdf else d
            sig.append((d - d0[i]) * (p1[i] - p0[i]) / ((d1[i] - d0[i]) or 1.0) + p0[i])
    return {"signal": np.stack(sig, 1).astype(np.float32), "sample_rate": n[want[0]] / dur, "markers": sorted(markers),
            "labels": [cols["label"][i] for i in want], "units": [cols["dim"][i] for i in want],
            "format": "BDF" if bdf else (_s(b[192:236])[:5] if b[192:196] == b"EDF+" else "EDF")}


def open_source(path: str | PathLike[str], modality: str = "eeg", channels: Sequence[str] | None = None,
                speed: float = 0.0, chunk_s: float = 0.1) -> ArraySource:
    """An EDF / BDF file as a signal source (``speed`` 0: as fast as possible; 1: real time)."""
    r = read_edf(path, channels)
    meta = {"device.modality": modality, "device.channel_count": len(r["labels"]), "edf.format": r["format"]}
    src = ArraySource(r["signal"], r["sample_rate"], r["markers"], speed, chunk_s, 0.0, f"edf:{Path(path).name}",
                      modality, meta)
    src.info.update(channel_labels=r["labels"], channel_units=r["units"])
    return src
