"""Toy models for every pretrained runtime (P14-51, gap 147): gru-ctc, xbody-ctc, crt-ctc, key-lda.

Each toy model has random weights. The tests check that ``toy_model(runtime)`` loads through the
normal loader checks, decodes the input of the real model of that runtime into a valid NTS
stream, and has no trust config. Synthetic data only. Our own code (Apache-2.0).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import fidetype.conformance as C
import fidetype.pretrained as ftp
from fidetype.pretrained.toy import TOY_NAMES, TOY_RUNTIMES

RNG = np.random.default_rng(0)


def _check_stream(m, st, n_vocab: int) -> None:
    assert st.log_probs.ndim == 2 and st.log_probs.shape[1] == n_vocab
    assert np.all(np.isfinite(st.log_probs))
    np.testing.assert_allclose(np.exp(st.log_probs).sum(axis=1), 1.0, atol=1e-4)
    assert C.check(st).passes("provenance")
    assert isinstance(m.text(st), str)
    with pytest.raises(ftp.NoTrustConfig):
        m.decide(st)


def test_toy_runtimes_cover_every_runtime():
    from fidetype.pretrained import RUNTIMES

    assert set(TOY_RUNTIMES) == set(RUNTIMES)


def test_toy_xbody_ctc(tmp_path):
    m = ftp.toy_model("xbody-ctc", folder=tmp_path)
    assert m.manifest.runtime == "xbody-ctc" and m.name == TOY_NAMES["xbody-ctc"]
    assert m.sessions == ("toy.2026.01.01", "toy.2026.01.02")
    x = RNG.poisson(1.0, (120, 192)).astype(np.float32)  # 1.2 s of threshold crossings, 10 ms bins
    st = m.decode(x, session=m.sessions[1])
    assert st.log_probs.shape[0] == 120
    _check_stream(m, st, 98)
    with pytest.raises(ValueError, match="unknown session"):
        m.decode(x, session="t5.2019.05.08")
    # causal: the first frames do not change when later input changes
    y = x.copy()
    y[60:] = 0
    np.testing.assert_allclose(m.decode(y, session=1).log_probs[:60], st.log_probs[:60], atol=1e-5)


def test_toy_crt_ctc(tmp_path):
    m = ftp.toy_model("crt-ctc", folder=tmp_path)
    assert m.manifest.runtime == "crt-ctc" and m.name == TOY_NAMES["crt-ctc"] and m.sessions == ()
    assert not m.research_only  # a toy model has no research-only data (the real emg2qwerty model has)
    emg = RNG.standard_normal((2000, 32)).astype(np.float32)  # 1 s of 2 kHz EMG, two 16-electrode bands
    st = m.decode(emg)
    assert st.log_probs.shape[0] == (2000 - 64) // 20 + 1
    _check_stream(m, st, 98)
    with pytest.raises(ValueError, match="fixed input of 32"):
        ftp.make_toy_manifest(tmp_path / "bad", runtime="crt-ctc", n_in=16)


def test_toy_key_lda(tmp_path):
    m = ftp.toy_model("key-lda", folder=tmp_path)
    assert m.manifest.runtime == "key-lda" and m.name == TOY_NAMES["key-lda"] and m.sessions == ()
    assert m.model.sample_rate == 2000.0 and m.model.channels == 32
    emg = RNG.standard_normal((6000, 32)).astype(np.float32)  # 3 s of 2 kHz EMG
    st = m.decode(emg, times=[0.5, 1.0, 1.5, 2.0])
    assert st.log_probs.shape[0] == 4  # one frame per key press
    _check_stream(m, st, 32)
    assert m.guard_input(st) == m.nbest(st)  # the guard of a key model reads the n-best list
    with pytest.raises(ValueError, match="times="):
        m.decode(emg)


@pytest.mark.parametrize("runtime", TOY_RUNTIMES)
def test_toy_files_are_checked_and_seeded(tmp_path, runtime):
    path = ftp.make_toy_manifest(tmp_path / "a", runtime=runtime, seed=3)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["task"] == "tutorial" and doc["trust"] is None and doc["runtime"] == runtime
    assert all(f["url"] is None for f in doc["files"])
    # same seed -> same weights bytes; the weights stay small (no large file in a temp folder)
    doc_b = json.loads(ftp.make_toy_manifest(tmp_path / "b", runtime=runtime, seed=3).read_text(encoding="utf-8"))
    assert [f["sha256"] for f in doc["files"]] == [f["sha256"] for f in doc_b["files"]]
    assert all(f["size"] < 2_000_000 for f in doc["files"])
    # a changed weights file is refused by load()
    w = tmp_path / "a" / next(f["name"] for f in doc["files"] if f["role"] == "weights")
    b = bytearray(w.read_bytes())
    b[len(b) // 2] ^= 0xFF
    w.write_bytes(bytes(b))
    with pytest.raises(ftp.WeightsMismatch):
        ftp.load(str(path), weights=tmp_path / "a")


def test_toy_model_argument_errors(tmp_path):
    with pytest.raises(ValueError, match="pass the folder as folder="):
        ftp.toy_model(tmp_path)  # the first argument is the runtime (P14-51)
    with pytest.raises(ValueError, match="toy runtimes"):
        ftp.toy_model("no-such-runtime")
    with pytest.raises(ValueError, match="session name"):
        ftp.make_toy_manifest(tmp_path, runtime="xbody-ctc", sessions=[])
