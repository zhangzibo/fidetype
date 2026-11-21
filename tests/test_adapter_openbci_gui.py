"""Conformance test of the OpenBCI GUI recording adapter (made from the adapter template, P14-42).

Synthetic files only, in the OpenBCI GUI v5 text layout. No real
recordings, no participant data.
"""

from __future__ import annotations

import numpy as np
import pytest

from fidetype.adapters import openbci_gui as A
from fidetype.adapters.testing import assert_source_conforms

T0 = 1_700_000_000.0


def _write_gui(path, n=500, fs=250.0, ch=8, marker_at=(), board="OpenBCI_GUI$BoardCytonSerial"):
    """A synthetic GUI v5 file: EXG sine waves, accel, a Marker Channel, packet time stamps."""
    rng = np.random.default_rng(1)
    t = np.arange(n) / fs
    exg = np.stack([50 * np.sin(2 * np.pi * (k + 1) * t) for k in range(ch)], 1) + rng.standard_normal((n, ch))
    cols = (["Sample Index"] + [f"EXG Channel {k}" for k in range(ch)] + [f"Accel Channel {k}" for k in range(3)]
            + ["Marker Channel", "Timestamp", "Timestamp (Formatted)"])
    lines = ["%OpenBCI Raw EXG Data", f"%Number of channels = {ch}", f"%Sample Rate = {fs:g} Hz", f"%Board = {board}",
             ", ".join(cols)]
    for i in range(n):
        stamp = T0 + (i // 4 * 4) / fs  # packet stamps: repeat inside a packet of 4 samples
        mk = 1.0 if i in marker_at else 0.0
        vals = [i % 256, *exg[i], 0.0, 0.0, 1.0, mk, stamp]
        lines.append(", ".join(f"{v:.6f}" for v in vals) + ", 2023-11-14 22:13:20.000")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return exg


def test_openbci_gui_conforms(tmp_path):
    good, bad = tmp_path / "OpenBCI-RAW-ok.txt", tmp_path / "bad.txt"
    exg = _write_gui(good, marker_at=(100, 300))
    bad.write_text("%OpenBCI Raw EEG Data\n%Sample Rate = 250 Hz\n0, 1.0, 2.0\n", encoding="utf-8")  # v3: no names
    res = assert_source_conforms(lambda: A.open_source(good), require_units=True, expect_channels=8,
                                 expect_rate=250.0, bad_inputs=[lambda: A.open_source(bad)])
    assert res.n_samples == 500
    assert [(round(t - T0, 6), m) for t, m in res.markers] == [(0.4, "1"), (1.2, "1")]
    r = A.read_openbci_gui(good)
    np.testing.assert_allclose(r["signal"], exg, atol=1e-5)
    assert r["t0"] == T0 and r["board"] == "OpenBCI_GUI$BoardCytonSerial"


def test_openbci_gui_ganglion_and_bad_inputs(tmp_path):
    p = tmp_path / "g.txt"
    _write_gui(p, ch=4, fs=200.0, board="OpenBCI_GUI$BoardGanglionBLE")
    assert A.open_source(p).info["channel_labels"] == [f"EXG Channel {k}" for k in range(4)]
    lines = p.read_text(encoding="utf-8").splitlines()
    cases = {"no-rate": [ln for ln in lines if "Sample Rate" not in ln],
             "ragged": lines[:10] + [lines[10] + ", 9.9"],
             "text-in-number": lines[:10] + [lines[10].replace("0.", "x.", 1)],
             "no-rows": lines[:5]}
    for name, ls in cases.items():
        (tmp_path / name).write_text("\n".join(ls) + "\n", encoding="utf-8")
        with pytest.raises(ValueError):
            A.read_openbci_gui(tmp_path / name)


def test_openbci_gui_millisecond_stamps(tmp_path):
    """P4-16: the GUI sample files write Unix milliseconds; t0 must be seconds (else float64 spacing breaks)."""
    p = tmp_path / "OpenBCI-RAW-ms.txt"
    _write_gui(p, n=500)
    lines = p.read_text(encoding="utf-8").splitlines()
    out = lines[:5]
    for ln in lines[5:]:
        v = ln.split(", ")
        v[-2] = f"{float(v[-2]) * 1000:.0f}"  # Timestamp column in ms, as OpenBCI_GUI-v6-*.txt
        out.append(", ".join(v))
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    assert A.read_openbci_gui(p)["t0"] == T0
    res = assert_source_conforms(lambda: A.open_source(p), require_units=True, expect_rate=250.0)
    assert res.n_samples == 500


def test_openbci_gui_v4_file_has_a_clear_message(tmp_path):
    """P4-16: a GUI v4 file (no column-name line; last column a clock time) names the layout in the error."""
    p = tmp_path / "v4.txt"
    p.write_text("%OpenBCI Raw EEG Data\n%Sample Rate = 250 Hz\n0, 1.0, 2.0, 1557936053329, 12:00:53.329\n",
                 encoding="utf-8")
    with pytest.raises(ValueError, match="no column-name line"):
        A.read_openbci_gui(p)
