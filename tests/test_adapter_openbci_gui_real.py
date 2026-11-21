"""Real-file check of the ``openbci-gui`` reader on GUI v5+ files with seconds stamps (P4-18, gap 157). Local data only.

The files are public and openly licensed, but they are never in the
repository (see ``references/README.md``, "Downloaded datasets"). Each test
is skipped when its file is absent. Root: ``FIDETYPE_P4_18_DATA``
(default ``C:/Users/zhang/bci-data/raw/p4-18``).

- ``silent-speech-nepali/OpenBCI-RAW-2021-05-13_15-21-21.txt``: GitHub
  Bot-Ro-Bot/Silent-Speech-Recognition-in-Nepali, GPL-3.0. Cyton, 8 ch,
  250 Hz, GUI v5.0 layout (no ``Marker Channel``), Unix seconds, 20 real
  Sample Index jumps (30 samples lost).
- ``mendeley-cp586sfzrt/OpenBCI-RAW-2026-05-07_14-48-12.txt``: Mendeley Data
  cp586sfzrt v4 (five-class imagined alphabet), CC BY 4.0. Cyton + Daisy,
  16 ch, 125 Hz, ``Marker Channel`` present but all zero, Unix seconds,
  Sample Index steps of 2, no drop.

Second reader: the Python ``csv`` module (EXG values within 0.005 uV plus
float32 rounding; drops recomputed from the index and time stamp columns
by a separate, plain loop). Each file also goes through the source
conformance helper and ``fidetype live --source file --speed 0``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

from fidetype.adapters import openbci_gui
from fidetype.adapters.testing import assert_nts_conforms, assert_source_conforms

ROOT = Path(os.environ.get("FIDETYPE_P4_18_DATA", "C:/Users/zhang/bci-data/raw/p4-18"))
NEPALI = "silent-speech-nepali/OpenBCI-RAW-2021-05-13_15-21-21.txt"
DAISY = "mendeley-cp586sfzrt/OpenBCI-RAW-2026-05-07_14-48-12.txt"
# file -> (SHA-256, channels, sample rate, rows, index step, packet drops, samples lost, board)
FILES = {
    NEPALI: ("0ae208d88a11b183b967477f1d5b899060b60ffe3cd7c086e4b5909f65cef08a", 8, 250.0, 55011, 1, 20, 30,
             "OpenBCI_GUI$BoardCytonSerial"),
    DAISY: ("fbace3efd34b9d342480c59651eea26994ceea79e3df3e635aaeec1b25e87453", 16, 125.0, 64082, 2, 0, 0,
            "OpenBCI_GUI$BoardCytonSerialDaisy"),
}
F32 = 2.0 ** -23


def _path(name: str) -> Path:
    p = ROOT / name
    if not p.is_file():
        pytest.skip(f"{name} not downloaded (P4-18 local data, see references/README.md)")
    assert hashlib.sha256(p.read_bytes()).hexdigest() == FILES[name][0], f"{name}: not the recorded file"
    return p


def _csv(p: Path) -> tuple[list[str], list[list[str]]]:
    with p.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.reader(fh) if row and not row[0].startswith("%")]
    return [c.strip() for c in rows[0]], rows[1:]


@pytest.mark.parametrize("name", list(FILES))
def test_real_gui_v5_matches_csv(name):
    p = _path(name)
    _, ch, fs, n, step, n_drop, lost, board = FILES[name]
    r = openbci_gui.read_openbci_gui(p)
    names, rows = _csv(p)
    exg = [i for i, c in enumerate(names) if c.startswith("EXG Channel")]
    ref = np.array([[float(row[i]) for i in exg] for row in rows])
    assert r["signal"].shape == (n, ch) == ref.shape and r["sample_rate"] == fs and r["board"] == board
    np.testing.assert_array_less(np.abs(r["signal"] - ref), 0.005 + F32 * np.abs(ref) + 1e-12)
    stamp0 = float(rows[0][names.index("Timestamp")])
    assert 1.5e9 < stamp0 < 2e9 and r["t0"] == stamp0  # Unix seconds, read as seconds
    # Drops by a plain loop over the index column (the reader uses NumPy and its own code path).
    idx = [int(float(row[0])) for row in rows]
    jumps = [(k, (idx[k] - idx[k - 1]) % 256 // step - 1) for k in range(1, n) if (idx[k] - idx[k - 1]) % 256 != step]
    assert r["index_checked"] and r["gaps"] == jumps and len(jumps) == n_drop and sum(m for _, m in jumps) == lost
    # Times: the next row after a drop is later by the lost samples; the whole file spans rows + lost samples.
    assert r["times"][-1] - r["t0"] == pytest.approx((n - 1 + lost) / fs, abs=1e-6)
    span = float(rows[-1][names.index("Timestamp")]) - stamp0
    assert abs(span - (n - 1 + lost) / fs) < 1.0  # the PC stamps agree within the packet jitter and clock drift


def test_real_marker_channel_is_read_but_all_zero():
    """The Daisy file has a Marker Channel column (GUI v5.1+ layout); every value is 0, so no markers."""
    p = _path(DAISY)
    names, rows = _csv(p)
    assert "Marker Channel" in names
    assert {float(row[names.index("Marker Channel")]) for row in rows} == {0.0}
    assert openbci_gui.read_openbci_gui(p)["markers"] == []


def test_real_drops_error_mode():
    p = _path(NEPALI)
    with pytest.raises(ValueError, match=r"packet drop: 20 Sample Index jumps, 30 samples lost \(first: 10 before"):
        openbci_gui.read_openbci_gui(p, on_drop="error")
    assert openbci_gui.read_openbci_gui(_path(DAISY), on_drop="error")["gaps"] == []


@pytest.mark.parametrize("name", list(FILES))
def test_real_gui_v5_source_conforms(name):
    p = _path(name)
    _, ch, fs, n, _, n_drop, lost, _ = FILES[name]
    res = assert_source_conforms(lambda: openbci_gui.open_source(p), require_units=True, expect_channels=ch,
                                 expect_rate=fs)
    assert res.n_samples == n
    src = openbci_gui.open_source(p)
    assert src.info["meta"]["openbci.packet_drops"] == n_drop and src.info["meta"]["openbci.samples_lost"] == lost
    src.start()
    gaps = []
    while (c := src.poll()) is not None:
        if c.gap is not None:
            gaps.append(c.gap)
    assert len(gaps) == n_drop and sum(g["missing_frames"] for g in gaps) == lost
    assert all(g["cause"] == "sample_index" and g["t_end"] > g["t_start"] for g in gaps)


@pytest.mark.parametrize("name", list(FILES))
def test_real_gui_v5_through_fidetype_live(name, tmp_path, capsys):
    p = _path(name)
    from test_adapter_files_real import _toy_model

    from fidetype.live.__main__ import main as live_main

    _, ch, fs, _, _, n_drop, _, _ = FILES[name]
    model, out, summ = _toy_model(tmp_path / "toy", ch, fs), tmp_path / "f.nts.jsonl", tmp_path / "s.json"
    rc = live_main(["--source", "file", "--path", str(p), "--model", str(model), "--guard", "builtin:synthetic-keys",
                    "--speed", "0", "--no-text", "--segment-s", "1", "--out", str(out), "--summary", str(summ)])
    err = capsys.readouterr().err
    assert rc == 0, err
    s = json.loads(summ.read_text(encoding="utf-8"))
    assert s["source"] == "file" and s["timing"] == "fixed" and s["decisions"] >= 1
    st = [e for e in map(json.loads, out.read_text(encoding="utf-8").splitlines()) if e.get("type") == "lsl_status"]
    assert len(st) == n_drop and all(e["lsl_cause"] == "sample_index" for e in st)
    assert_nts_conforms(lambda: [out], level="trust-ready")
