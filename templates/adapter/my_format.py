"""my-format reader -> a signal source for ``fidetype live`` (made from the adapter template, P14-42).

TODO: say in 2-4 short sentences what this adapter reads (device, file
format or dataset), where the format is documented, and its licence.
State what the adapter does NOT support. Our own code (Apache-2.0).

Template rules (delete this block when done):
- Copy with ``python -m fidetype.adapters.registry new my-format``.
- Keep heavy dependencies optional: import them inside the function and
  add an extra to ``pyproject.toml``.
- Bad input raises ``ValueError`` with a clear message.
- Never put truth text or personal data (names, birth dates, ...) in ``meta``.
- Then run: ``python -m fidetype.adapters.registry`` (updates docs/adapters.md).
- A file reader keeps ``open_source(path, modality=..., speed=..., ...)``:
  ``fidetype live --source file`` calls it with ``speed`` (and ``modality``
  when the user gives ``--modality``).
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path

import numpy as np

from fidetype.live.sources import ArraySource

# The registry reads this dict. Fields: see fidetype/adapters/registry.py. Status: "experimental" until
# the adapter has read real files or a real device; then "tested". A "file-reader" also gives
# "file_patterns": the file-name globs (case-insensitive) with which `fidetype live --source file --path FILE`
# picks this reader (`--reader my-format` picks it by id). A device source has no file_patterns.
# Support (P4-15, docs/device-support.md): "synthetic-only" until it has run on real data. Then "replay-only"
# (real files or a public dataset) or "real-device" (also fill "hardware_tested"), and list the test or result
# that shows it in "real_data_evidence". The registry refuses a claim without evidence.
ADAPTER_INFO = {
    "id": "my-format", "kind": "file-reader", "signal": "eeg", "status": "experimental",
    "file_patterns": ["*.my-format.npz"],
    "target": "TODO: the device, file format or dataset",
    "licence": "Code Apache-2.0. TODO: licence of the format, SDK or data.",
    "tests": ["tests/test_adapter_my_format.py"], "docs": "docs/adapters.md",
    "support": "synthetic-only", "transport": ["file"], "real_data_evidence": [],
    "test_covers": "CI: synthetic files made by the test.",
    "limits": "TODO: what does not work yet (no real file read, missing format variants, ...).",
}


def read_my_format(path: str | PathLike[str]) -> dict:
    """Read one file. Return ``signal`` (N, C), ``sample_rate`` (Hz), ``labels``, ``units``, ``markers``.

    TODO: replace this example (an ``.npz`` file with ``signal``, ``sample_rate``, ``labels``, ``units``).
    """
    try:
        with np.load(path, allow_pickle=False) as z:
            sig, fs = np.asarray(z["signal"], np.float32), float(z["sample_rate"])
            labels, units = [str(x) for x in z["labels"]], [str(x) for x in z["units"]]
    except (OSError, KeyError) as e:
        raise ValueError(f"not a my-format file: {e}") from e
    if sig.ndim != 2 or sig.shape[0] == 0 or fs <= 0 or not len(labels) == sig.shape[1] == len(units):
        raise ValueError(f"bad my-format file: signal {sig.shape}, sample rate {fs}, {len(labels)} labels")
    return {"signal": sig, "sample_rate": fs, "labels": labels, "units": units, "markers": []}


def open_source(path: str | PathLike[str], modality: str = "eeg", speed: float = 0.0,
                chunk_s: float = 0.1) -> ArraySource:
    """The file as a signal source (``speed`` 0: as fast as possible; 1: real time)."""
    r = read_my_format(path)
    meta = {"device.modality": modality, "device.channel_count": len(r["labels"])}  # NTS 4.2 keys only
    src = ArraySource(r["signal"], r["sample_rate"], r["markers"], speed, chunk_s, 0.0,
                      f"my-format:{Path(path).name}", modality, meta)
    src.info.update(channel_labels=r["labels"], channel_units=r["units"])
    return src
