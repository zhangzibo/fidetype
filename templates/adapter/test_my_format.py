"""Conformance test of the my-format adapter (made from the adapter template, P14-42).

Synthetic data only: never commit real recordings or participant data.
TODO: make ``_write`` produce a small file in your format.
"""

from __future__ import annotations

import numpy as np

from fidetype.adapters import my_format as A
from fidetype.adapters.testing import assert_source_conforms


def _write(path, n=500, fs=250.0, ch=4):
    """A small synthetic file: sine waves plus noise (TODO: write your format here)."""
    t = np.arange(n) / fs
    sig = np.stack([10 * np.sin(2 * np.pi * (k + 1) * t) for k in range(ch)], 1)
    sig += np.random.default_rng(0).standard_normal(sig.shape)
    np.savez(path, signal=sig, sample_rate=fs, labels=[f"C{k}" for k in range(ch)], units=["uV"] * ch)
    return sig


def test_my_format_conforms(tmp_path):
    good, bad = tmp_path / "ok.npz", tmp_path / "bad.npz"
    sig = _write(good)
    bad.write_bytes(b"not a file of this format")
    res = assert_source_conforms(lambda: A.open_source(good), require_units=True, expect_channels=4,
                                 expect_rate=250.0, bad_inputs=[lambda: A.open_source(bad)])
    assert res.n_samples == sig.shape[0]


def test_my_format_values(tmp_path):
    sig = _write(tmp_path / "ok.npz")
    r = A.read_my_format(tmp_path / "ok.npz")
    np.testing.assert_allclose(r["signal"], sig, atol=1e-4)  # TODO: the tolerance of your format
