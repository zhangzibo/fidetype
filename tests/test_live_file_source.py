"""``fidetype live --source file`` picks the file reader from the adapter registry (P4-17, gap 135).

Synthetic files only: an EDF+ file of the synthetic typist (with its
keypress / segment_end markers as EDF annotations) and an OpenBCI GUI
file. No real recordings, no participant data.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from test_adapter_edf import _write_edf
from test_adapter_openbci_gui import _write_gui

from fidetype.adapters import registry as R
from fidetype.conformance import check_file
from fidetype.live.__main__ import main as live_main
from fidetype.live.sources import SyntheticSource


def _typist_edf(path, n_utt=4):
    """The synthetic typist (16 ch, 250 Hz) as an EDF+ file; its markers become EDF annotations."""
    src = SyntheticSource(n_utt, seed=7)
    fs = src.fs
    n = int(np.ceil(src.x.shape[0] / fs) * fs) + int(fs)  # whole 1 s records; 1 s of zeros after the last marker
    sig = np.zeros((n, src.x.shape[1]))
    sig[: src.x.shape[0]] = src.x
    _write_edf(path, sig, fs=fs, ann=list(src.markers), phys=4000.0, ann_n=200)
    return src


def test_registry_picks_the_reader_by_file_name():
    assert [e["id"] for e in R.file_readers()] == ["edf", "openbci-gui"]
    assert R.pick_file_reader("a/rec.EDF")["id"] == "edf"
    assert R.pick_file_reader("rec.bdf")["id"] == "edf"
    assert R.pick_file_reader("OpenBCI-RAW-2026-11-21_10-00-00.txt")["id"] == "openbci-gui"
    assert R.pick_file_reader("renamed.txt", "openbci-gui")["id"] == "openbci-gui"  # by id: no name match needed
    with pytest.raises(ValueError, match="no file reader matches"):
        R.pick_file_reader("rec.xyz")
    with pytest.raises(ValueError, match="no file reader with id"):
        R.pick_file_reader("rec.edf", "no-such-reader")
    two = [dict(e, id=f"{e['id']}-copy") for e in R.file_readers()] + R.file_readers()
    with pytest.raises(ValueError, match="more than one file reader"):
        R.pick_file_reader("rec.edf", entries=two)


def test_open_file_source_refuses_an_unknown_option(tmp_path):
    p = tmp_path / "OpenBCI-RAW-x.txt"
    _write_gui(p, n=250)
    with pytest.raises(ValueError, match="does not take the option"):
        R.open_file_source(p, channels=["EXG Channel 0"])  # only the edf reader takes channels
    entry, src = R.open_file_source(p, modality=None, speed=0.0)  # None = not passed
    assert entry["id"] == "openbci-gui" and src.info["channels"] == 8


def test_registry_needs_file_patterns_for_a_file_reader():
    edf = next(e for e in R.collect() if e["id"] == "edf")
    errs = "\n".join(R.validate([{k: v for k, v in edf.items() if k != "file_patterns"}]))
    assert "needs file_patterns" in errs


def test_cli_edf_file_decodes_the_synthetic_typist(tmp_path, capsys):
    rec, out, summ = tmp_path / "typist.edf", tmp_path / "f.nts.jsonl", tmp_path / "f.json"
    _typist_edf(rec)
    rc = live_main(["--source", "file", "--path", str(rec), "--speed", "0", "--json", "--out", str(out),
                    "--summary", str(summ)])
    cap = capsys.readouterr()
    assert rc == 0, cap.err
    assert "file reader edf" in cap.err
    lines = [json.loads(x) for x in cap.out.splitlines()]
    assert len(lines) == 4 and {x["action"] for x in lines} <= {"commit", "offer", "withhold"}
    assert any(x["action"] == "commit" for x in lines)  # the builtin model reads the typist from the file
    s = json.loads(summ.read_text())
    assert s["decisions"] == 4 and s["source"] == "file" and s["timing"] == "markers"
    assert not check_file(out).failures("trust-ready")
    head = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert head["meta"]["fidetype.live"]["source"] == "file" and head["meta"]["edf.format"] == "EDF+C"
    assert head["meta"]["fidetype.file_reader"] == "edf"


def test_cli_openbci_gui_file_without_markers_uses_fixed_timing(tmp_path, capsys):
    rec = tmp_path / "renamed-recording.txt"  # the name matches no pattern: pick the reader by id
    _write_gui(rec, n=1000, ch=16)  # Cyton + Daisy: 16 channels, as the builtin model
    rc = live_main(["--source", "file", "--reader", "openbci-gui", "--path", str(rec), "--speed", "0",
                    "--segment-s", "1", "--json"])
    cap = capsys.readouterr()
    assert rc == 0, cap.err
    assert "file reader openbci-gui" in cap.err and "fixed timing" in cap.err
    assert len(cap.out.splitlines()) >= 3  # one decision per 1 s segment


@pytest.mark.parametrize("args, msg", [
    ([], "needs --path"),
    (["--path", "no-such-file.edf"], "no such file"),
    (["--path", "{tmp}/x.xyz"], "no file reader matches"),
    (["--path", "{tmp}/x.edf", "--reader", "nope"], "no file reader with id"),
])
def test_cli_file_source_errors(tmp_path, capsys, args, msg):
    (tmp_path / "x.xyz").write_bytes(b"x")
    (tmp_path / "x.edf").write_bytes(b"x")
    rc = live_main(["--source", "file", "--speed", "0", *[a.replace("{tmp}", str(tmp_path)) for a in args]])
    assert rc == 2 and msg in capsys.readouterr().err


def test_cli_bad_file_is_a_clear_error(tmp_path, capsys):
    bad = tmp_path / "bad.edf"
    bad.write_bytes(b"0       " + b"x" * 300)
    assert live_main(["--source", "file", "--path", str(bad), "--speed", "0"]) == 3
    assert "cannot open the file source" in capsys.readouterr().err
