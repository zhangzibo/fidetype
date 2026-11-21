"""Real-file check of the ``edf`` and ``openbci-gui`` readers (P4-16, gap 134). Local data only.

The files are public and openly licensed, but they are never in the
repository (see ``references/README.md``, "Downloaded datasets"). Each test
is skipped when its file is absent. Root: ``FIDETYPE_P4_16_DATA``
(default ``C:/Users/zhang/bci-data/raw/p4-16``).

- ``physionet-eegmmidb/S001R01.edf``, ``S001R04.edf``: PhysioNet EEG Motor
  Movement/Imagery v1.0.0, ODC-By 1.0 (EDF+C, 64 ch, 160 Hz, annotations).
- ``mne-testdata/test.edf``, ``test.bdf``: MNE-Python test files, BSD-3-Clause
  (EDF+C 139 ch 512 Hz; BioSemi BDF 73 ch 2048 Hz).
- ``openbci-gui-samples/OpenBCI_GUI-v6-blinks-jawClench-alpha.txt``: OpenBCI
  GUI sample file, MIT (Cyton, 8 ch, 250 Hz).

Second reader: MNE for EDF / BDF; the Python ``csv`` module for the GUI
text. The values must agree within half the format resolution (one EDF /
BDF digital step; 0.01 uV, the 2 decimals of the GUI file) plus the
float32 rounding of the reader output. Each file also goes through the
source conformance helper and ``fidetype live --source file --speed 0``
(a toy model of the right shape; the NTS output must reach trust-ready).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

from fidetype.adapters import edf, openbci_gui
from fidetype.adapters.testing import assert_nts_conforms, assert_source_conforms

ROOT = Path(os.environ.get("FIDETYPE_P4_16_DATA", "C:/Users/zhang/bci-data/raw/p4-16"))
GUI = "openbci-gui-samples/OpenBCI_GUI-v6-blinks-jawClench-alpha.txt"
# file -> (SHA-256, channels, sample rate, samples, markers)
FILES = {
    "physionet-eegmmidb/S001R01.edf": ("4743b736131a7e147c150e8b37711029b6cda5e356c4b3e8261a03cdcaaf8b0c",
                                       64, 160.0, 9760, 1),
    "physionet-eegmmidb/S001R04.edf": ("3d161f88e1c00632585287d2ce584c2bc0f08862438eb255ea8723e00fac693d",
                                       64, 160.0, 20000, 30),
    "mne-testdata/test.edf": ("5a8b7af7a82a4c626cbc2feb3f4efbff8a29794f5a29e4517ca0c4ed4da14d58", 139, 512.0, 3072, 5),
    "mne-testdata/test.bdf": ("d97eb2809b8314bf097493b8e2b04140b86722e0de749a563fa6bab2bc63554a", 73, 2048.0, 2048, 0),
    GUI: ("cc5f303bba1270a9a236b42497dfec531c8a1e91d8540eab1e097848940395d3", 8, 250.0, 22490, 0),
}
EDF_FILES = [f for f in FILES if f != GUI]
F32 = 2.0 ** -23  # float32 relative rounding (half an ulp is 2**-24; keep one ulp of margin)


def _path(name: str) -> Path:
    p = ROOT / name
    if not p.is_file():
        pytest.skip(f"{name} not downloaded (P4-16 local data, see references/README.md)")
    assert hashlib.sha256(p.read_bytes()).hexdigest() == FILES[name][0], f"{name}: not the recorded file"
    return p


def _edf_resolution(p: Path) -> dict[str, float]:
    """label -> physical units per digital step, from the header (independent of the reader)."""
    b = p.read_bytes()
    ns = int(b[252:256])

    def col(field: int, w: int) -> list[str]:
        return [b[256 + field * ns + i * w: 256 + field * ns + (i + 1) * w].decode("ascii").strip() for i in range(ns)]

    lab, pmin, pmax, dmin, dmax = col(0, 16), col(104, 8), col(112, 8), col(120, 8), col(128, 8)
    return {lab[i]: (float(pmax[i]) - float(pmin[i])) / (float(dmax[i]) - float(dmin[i])) for i in range(ns)}


@pytest.mark.parametrize("name", EDF_FILES)
def test_real_edf_matches_mne(name):
    p = _path(name)
    mne = pytest.importorskip("mne")
    _, ch, fs, n, n_mk = FILES[name]
    r = edf.read_edf(p)
    assert r["signal"].shape == (n, ch) and r["sample_rate"] == fs and len(r["markers"]) == n_mk
    raw = (mne.io.read_raw_bdf if p.suffix == ".bdf" else mne.io.read_raw_edf)(p, preload=True, stim_channel=None,
                                                                               verbose="error")
    assert raw.info["sfreq"] == fs and raw.ch_names == r["labels"]
    res = _edf_resolution(p)
    scale = {"uV": 1e6, "mV": 1e3}
    for j, lab in enumerate(r["labels"]):
        ref = raw.get_data(picks=[j])[0] * scale.get(r["units"][j], 1.0)
        tol = 0.5 * abs(res[lab]) + F32 * np.abs(ref)
        np.testing.assert_array_less(np.abs(r["signal"][:, j].astype(float) - ref), tol + 1e-12, err_msg=lab)
    ann = [(round(float(t), 6), d) for t, d in zip(raw.annotations.onset, raw.annotations.description)]
    assert [(round(t, 6), m) for t, m in r["markers"]] == ann


def test_real_openbci_gui_matches_csv():
    p = _path(GUI)
    _, ch, fs, n, _ = FILES[GUI]
    r = openbci_gui.read_openbci_gui(p)
    with p.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.reader(fh) if row and not row[0].startswith("%")]
    names = [c.strip() for c in rows[0]]
    exg = [i for i, c in enumerate(names) if c.startswith("EXG Channel")]
    ref = np.array([[float(row[i]) for i in exg] for row in rows[1:]])
    assert r["signal"].shape == (n, ch) == ref.shape and r["sample_rate"] == fs
    np.testing.assert_array_less(np.abs(r["signal"] - ref), 0.005 + F32 * np.abs(ref) + 1e-12)
    assert r["t0"] == float(rows[1][names.index("Timestamp")]) / 1000.0  # this file writes milliseconds
    assert r["board"] == "OpenBCI_GUI$BoardCytonSerial" and r["markers"] == []


@pytest.mark.parametrize("name", list(FILES))
def test_real_file_source_conforms(name):
    p = _path(name)
    _, ch, fs, n, n_mk = FILES[name]
    mod = openbci_gui if name == GUI else edf
    res = assert_source_conforms(lambda: mod.open_source(p), require_units=True, expect_channels=ch, expect_rate=fs)
    assert res.n_samples == n and len(res.markers) == n_mk


def _toy_model(stem: Path, ch: int, fs: float) -> Path:
    """A random LDA model with the file's shape: a plumbing test of the CLI, not a decoder."""
    from fidetype.live.model import builtin_dir, fit_model

    card = json.loads((builtin_dir() / "synthetic-keys.model.json").read_text(encoding="utf-8"))
    card.update(name="p4-16-toy", channels=ch, sample_rate=fs, modality="eeg",
                training={"data": "random numbers (test only)", "licence": "Apache-2.0"})
    nv, d = len(card["vocab"]), ch * card["window"]["n_sub"]
    x = np.random.default_rng(0).standard_normal((nv * 10, d))
    _, js = fit_model([x], [np.repeat(np.arange(nv), 10)], card).save(stem)
    return js


@pytest.mark.parametrize("name", list(FILES))
def test_real_file_through_fidetype_live(name, tmp_path, capsys):
    p = _path(name)
    from fidetype.live.__main__ import main as live_main

    _, ch, fs, n, _ = FILES[name]
    model, out, summ = _toy_model(tmp_path / "toy", ch, fs), tmp_path / "f.nts.jsonl", tmp_path / "s.json"
    rc = live_main(["--source", "file", "--path", str(p), "--reader", "openbci-gui" if name == GUI else "edf",
                    "--model", str(model), "--guard", "builtin:synthetic-keys", "--speed", "0", "--no-text",
                    "--segment-s", "0.25" if fs > 1000 else "1", "--out", str(out), "--summary", str(summ)])
    err = capsys.readouterr().err
    assert rc == 0, err
    assert "fixed timing" in err  # no file has 'keypress' markers
    s = json.loads(summ.read_text(encoding="utf-8"))
    assert s["source"] == "file" and s["timing"] == "fixed" and s["decisions"] >= 1
    assert_nts_conforms(lambda: [out], level="trust-ready")
