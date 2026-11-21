"""Conformance test of the EDF / BDF adapter (made from the adapter template, P14-42).

Synthetic files only: ``_write_edf`` writes EDF+ and BDF files from the
public format description (https://www.edfplus.info/specs/). No real
recordings, no participant data.
"""

from __future__ import annotations

import numpy as np
import pytest

from fidetype.adapters import edf as A
from fidetype.adapters.testing import assert_source_conforms


def _write_edf(path, sig, fs=256.0, rec_s=1.0, bdf=False, ann=(), reserved="EDF+C", phys=1000.0, ann_n=None):
    """Write (N, C) microvolts in [-phys, phys] as EDF+ (16 bit) or BDF (24 bit), plus an annotation signal."""
    n_rec, spr, ch = sig.shape[0] // int(fs * rec_s), int(fs * rec_s), sig.shape[1]
    dmax = 2 ** 23 - 1 if bdf else 32767
    ann_n = ann_n or (30 if bdf else 60)  # samples per record of the annotation signal (90 / 120 bytes)
    labels = [f"EEG C{k}" for k in range(ch)] + ["BDF Annotations" if bdf else "EDF Annotations"]
    f = lambda v, w: str(v).ljust(w)[:w].encode("ascii")  # noqa: E731
    head = (b"\xffBIOSEMI" if bdf else f("0", 8)) + f("X X X X", 80) + f("Startdate X X X X", 80)
    head += f("01.01.00", 8) + f("00.00.00", 8) + f(256 * (ch + 2), 8) + f("24BIT" if bdf else reserved, 44)
    head += f(n_rec, 8) + f(rec_s, 8) + f(ch + 1, 4)
    cols = [(16, labels), (80, [""] * (ch + 1)), (8, ["uV"] * ch + [""]), (8, [-phys] * ch + [-1]),
            (8, [phys] * ch + [1]), (8, [-dmax - 1] * (ch + 1)), (8, [dmax] * (ch + 1)), (80, [""] * (ch + 1)),
            (8, [spr] * ch + [ann_n]), (32, [""] * (ch + 1))]
    for w, vals in cols:
        head += b"".join(f(v, w) for v in vals)
    dig = np.round((sig + phys) / (2 * phys) * (2 * dmax + 1) - dmax - 1).astype(np.int64)
    body = b""
    for r in range(n_rec):
        for k in range(ch):
            d = dig[r * spr:(r + 1) * spr, k]
            body += (d.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3].tobytes() if bdf
                     else d.astype("<i2").tobytes())
        tal = f"+{r * rec_s:g}\x14\x14\x00".encode()
        tal += b"".join(f"+{t:g}\x14{txt}\x14\x00".encode() for t, txt in ann if r * rec_s <= t < (r + 1) * rec_s)
        body += tal.ljust(ann_n * (3 if bdf else 2), b"\x00")
    path.write_bytes(head + body)


def _sig(n=768, ch=3, fs=256.0):
    t = np.arange(n) / fs
    return np.stack([100 * np.sin(2 * np.pi * (k + 2) * t) for k in range(ch)], 1)


@pytest.mark.parametrize("bdf", [False, True])
def test_edf_conforms(tmp_path, bdf):
    good, bad = tmp_path / "ok.edf", tmp_path / "bad.edf"
    sig = _sig()
    _write_edf(good, sig, bdf=bdf, ann=[(0.5, "keypress"), (2.25, "segment_end")])
    bad.write_bytes(b"0       " + b"x" * 300)
    res = assert_source_conforms(lambda: A.open_source(good), require_units=True, expect_channels=3,
                                 expect_rate=256.0, bad_inputs=[lambda: A.open_source(bad)])
    assert res.n_samples == 768
    assert res.markers == [(0.5, "keypress"), (2.25, "segment_end")]
    r = A.read_edf(good)
    step = 2000 / (2 ** 24 if bdf else 2 ** 16)
    np.testing.assert_allclose(r["signal"], sig, atol=step)
    assert r["units"] == ["uV"] * 3 and r["format"] == ("BDF" if bdf else "EDF+C")


def test_edf_privacy_and_channels(tmp_path):
    p = tmp_path / "ok.edf"
    _write_edf(p, _sig())
    src = A.open_source(p, channels=["EEG C1"])
    assert src.info["channels"] == 1 and src.info["channel_labels"] == ["EEG C1"]
    assert "X X X X" not in repr(src.info)  # the patient and recording fields never reach meta


def test_edf_bad_inputs(tmp_path):
    p = tmp_path / "x.edf"
    _write_edf(p, _sig())
    data = p.read_bytes()
    cases = {"short": data[:100], "truncated": data[:-200], "bad-number": data[:236] + b"abc     " + data[244:]}
    for name, b in cases.items():
        (tmp_path / name).write_bytes(b)
        with pytest.raises(ValueError):
            A.read_edf(tmp_path / name)
    _write_edf(tmp_path / "d.edf", _sig(), reserved="EDF+D")
    with pytest.raises(ValueError, match="EDF\\+D"):
        A.read_edf(tmp_path / "d.edf")
    with pytest.raises(ValueError, match="one sample rate"):
        A.read_edf(p, channels=["no such channel"])
