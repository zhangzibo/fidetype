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


# --- P4-18: Sample Index jumps (packet drops) ------------------------------------------------------------------


def _edit_rows(path, drop=(), index=None):
    """Delete the data rows ``drop`` (0-based, before deletion) and/or rewrite the Sample Index as ``index(i)``."""
    lines = path.read_text(encoding="utf-8").splitlines()
    head, rows = lines[:5], lines[5:]
    if index is not None:
        rows = [", ".join([f"{index(i):.6f}", *r.split(", ")[1:]]) for i, r in enumerate(rows)]
    rows = [r for i, r in enumerate(rows) if i not in set(drop)]
    path.write_text("\n".join(head + rows) + "\n", encoding="utf-8")


def _gap_chunks(src):
    src.start()
    out = []
    while (c := src.poll()) is not None:
        if c.gap is not None:
            out.append((c.gap, float(c.times[0])))
    return out


def test_openbci_gui_index_wrap_is_not_a_drop(tmp_path):
    """Cyton: 0..255 then 0 again (600 rows, two wraps); Daisy: steps of 2 with wraps. No gap, no error."""
    p = tmp_path / "OpenBCI-RAW-wrap.txt"
    _write_gui(p, n=600)
    r = A.read_openbci_gui(p, on_drop="error")
    assert r["gaps"] == [] and r["index_checked"]
    np.testing.assert_allclose(r["times"] - T0, np.arange(600) / 250.0, atol=1e-6)
    d = tmp_path / "OpenBCI-RAW-daisy.txt"
    _write_gui(d, n=600, ch=16, fs=125.0, board="OpenBCI_GUI$BoardCytonSerialDaisy")
    _edit_rows(d, index=lambda i: (2 * i) % 256)
    assert A.read_openbci_gui(d, on_drop="error")["gaps"] == []


def test_openbci_gui_packet_drop_gap_mode(tmp_path):
    """Rows 100..102 lost (3 samples) and row 400 lost (1): times after each drop move on; gap chunks carry LSL-G3."""
    p = tmp_path / "OpenBCI-RAW-drop.txt"
    exg = _write_gui(p, n=600, marker_at=(450,))
    _edit_rows(p, drop=(100, 101, 102, 400))
    r = A.read_openbci_gui(p)
    assert r["gaps"] == [(100, 3), (397, 1)]
    keep = [i for i in range(600) if i not in (100, 101, 102, 400)]
    np.testing.assert_allclose(r["times"] - T0, np.array(keep) / 250.0, atol=1e-6)  # true sample times
    np.testing.assert_allclose(r["signal"], exg[keep], atol=1e-5)
    assert [round(t - T0, 6) for t, _ in r["markers"]] == [1.8]  # marker on sample 450 keeps its time
    res = assert_source_conforms(lambda: A.open_source(p), require_units=True, expect_rate=250.0)
    assert res.n_samples == 596
    src = A.open_source(p, chunk_s=0.5)
    assert src.info["meta"]["openbci.packet_drops"] == 2 and src.info["meta"]["openbci.samples_lost"] == 4
    gaps = _gap_chunks(src)
    assert [(g["missing_frames"], g["cause"], round(g["t_start"] - T0, 6), round(g["t_end"] - T0, 6),
             round(t - T0, 6)) for g, t in gaps] == [(3, "sample_index", 0.396, 0.412, 0.412),
                                                   (1, "sample_index", 1.596, 1.604, 1.604)]
    assert all(g["stream"] == "openbci-gui:OpenBCI-RAW-drop.txt" for g, _ in gaps)


def test_openbci_gui_packet_drop_error_mode(tmp_path):
    p = tmp_path / "OpenBCI-RAW-drop.txt"
    _write_gui(p, n=600)
    _edit_rows(p, drop=(100, 101, 102))
    with pytest.raises(ValueError, match=r"packet drop: 1 Sample Index jumps, 3 samples lost \(first: 3 before data row 100\)"):
        A.read_openbci_gui(p, on_drop="error")
    with pytest.raises(ValueError, match="packet drop"):
        A.open_source(p, on_drop="error")
    with pytest.raises(ValueError, match="on_drop must be one of"):
        A.read_openbci_gui(p, on_drop="ignore")


def test_openbci_gui_drop_across_a_wrap_and_daisy_drop(tmp_path):
    """A drop over the 255 -> 0 wrap counts mod 256; on Daisy (step 2) one lost row is an index step of 4."""
    p = tmp_path / "OpenBCI-RAW-wrapdrop.txt"
    _write_gui(p, n=600)
    _edit_rows(p, drop=(254, 255, 256, 257))  # index 253 -> 2
    assert A.read_openbci_gui(p)["gaps"] == [(254, 4)]
    d = tmp_path / "OpenBCI-RAW-daisy.txt"
    _write_gui(d, n=600, ch=16, fs=125.0, board="OpenBCI_GUI$BoardCytonSerialDaisy")
    _edit_rows(d, index=lambda i: (2 * i) % 256, drop=(127, 300, 301))  # 252 -> 0 over the wrap; 598 -> 604
    r = A.read_openbci_gui(d)
    assert r["gaps"] == [(127, 1), (299, 2)]
    keep = [i for i in range(600) if i not in (127, 300, 301)]
    np.testing.assert_allclose(r["times"] - T0, np.array(keep) / 125.0, atol=1e-6)


def test_openbci_gui_full_index_cycle_lost_uses_the_stamps(tmp_path):
    """258 rows lost: the index alone says 2 (mod 256); the Timestamp jump adds the whole cycle."""
    p = tmp_path / "OpenBCI-RAW-cycle.txt"
    _write_gui(p, n=900)
    _edit_rows(p, drop=range(300, 558))
    r = A.read_openbci_gui(p)
    assert r["gaps"] == [(300, 258)]
    assert round(float(r["times"][300] - T0), 6) == 558 / 250.0


def test_openbci_gui_repeated_row_and_bad_steps_raise(tmp_path):
    p = tmp_path / "OpenBCI-RAW-rep.txt"
    _write_gui(p, n=300)
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(lines[:106] + [lines[105]] + lines[106:]) + "\n", encoding="utf-8")  # row 100 twice
    for mode in ("gap", "error"):
        with pytest.raises(ValueError, match="repeats index 100"):
            A.read_openbci_gui(p, on_drop=mode)
    d = tmp_path / "OpenBCI-RAW-daisy-odd.txt"
    _write_gui(d, n=300, ch=16, fs=125.0, board="OpenBCI_GUI$BoardCytonSerialDaisy")
    _edit_rows(d, index=lambda i: (2 * i + (i >= 150)) % 256)  # one step of 3 on a step-2 board
    with pytest.raises(ValueError, match="steps by 3, not a multiple of 2"):
        A.read_openbci_gui(d)
    w = tmp_path / "OpenBCI-RAW-step5.txt"
    _write_gui(w, n=300)
    _edit_rows(w, index=lambda i: (5 * i) % 256)
    with pytest.raises(ValueError, match="most common step is 5"):
        A.read_openbci_gui(w)


def test_openbci_gui_ganglion_index_is_not_checked(tmp_path):
    """Ganglion files use other index rules: no check, no gap, the meta says so."""
    p = tmp_path / "OpenBCI-RAW-g.txt"
    _write_gui(p, n=400, ch=4, fs=200.0, board="OpenBCI_GUI$BoardGanglionBLE")
    _edit_rows(p, drop=(100, 101))
    r = A.read_openbci_gui(p, on_drop="error")
    assert r["gaps"] == [] and not r["index_checked"]
    assert A.open_source(p).info["meta"]["openbci.sample_index_checked"] is False


def test_cli_openbci_gui_drop_writes_a_gap_record(tmp_path, capsys):
    """fidetype live on a file with a drop: one gap_abort status record with cause sample_index (spec LSL-G3)."""
    import json

    from fidetype.live.__main__ import main as live_main

    rec, out = tmp_path / "OpenBCI-RAW-drop.txt", tmp_path / "f.nts.jsonl"
    _write_gui(rec, n=1500, ch=16)
    _edit_rows(rec, drop=(700, 701))
    rc = live_main(["--source", "file", "--path", str(rec), "--speed", "0", "--segment-s", "1", "--json",
                    "--out", str(out)])
    cap = capsys.readouterr()
    assert rc == 0, cap.err
    st = [e for e in map(json.loads, out.read_text(encoding="utf-8").splitlines()) if e.get("type") == "lsl_status"]
    assert len(st) == 1 and st[0]["status"] == "gap_abort" and st[0]["missing_frames"] == 2
    assert st[0]["lsl_cause"] == "sample_index" and round(st[0]["t_end"] - T0, 6) == 2.808


def test_array_source_gaps_real_time_pacing():
    """ArraySource with gaps at speed 1: pacing counts the lost frames; no chunk spans a gap; bad gaps raise."""
    from fidetype.live.sources import ArraySource

    now = [0.0]
    src = ArraySource(np.zeros((100, 2)), 100.0, speed=1.0, chunk_s=0.1, gaps=[(50, 20)], clock=lambda: now[0])
    src.start()
    now[0] = 0.6  # frames 0..59 are due; rows 0..49 are frames 0..49, row 50 is frame 70
    c = src.poll(timeout=0)
    assert c.samples.shape[0] == 50 and c.gap is None
    assert src.poll(timeout=0).samples.shape[0] == 0  # row 50 (frame 70) is not due yet
    now[0] = 0.8
    c = src.poll(timeout=0)
    assert c.gap == {"t_start": 0.49, "t_end": 0.7, "missing_frames": 20, "stream": "array", "cause": "sample_index"}
    np.testing.assert_allclose(c.times, np.arange(70, 80) / 100.0)
    for bad in ([(0, 1)], [(100, 1)], [(10, 0)]):
        with pytest.raises(ValueError, match="gaps"):
            ArraySource(np.zeros((100, 2)), 100.0, gaps=bad)
