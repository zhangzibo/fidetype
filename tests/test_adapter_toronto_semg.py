"""Tests for the Toronto sEMG typing adapter (RHD reader, keylog, streams)."""

from __future__ import annotations

import json
import os
import struct
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from fidetype.adapters import toronto_semg as T
from fidetype.eval.metrics import ctc_greedy_decode
from fidetype.streams.spec import NeuralTextStream

REAL_ROOT = Path(os.environ.get("TORONTO_SEMG_ROOT", "C:/Users/zhang/bci-data/raw/toronto-semg/extracted/CleanData"))


# --- a minimal RHD writer (test only) ---------------------------------------------


def _qs(s: str) -> bytes:
    b = s.encode("utf-16-le")
    return struct.pack("<I", len(b)) + b


def write_rhd(path: Path, amp: np.ndarray, version=(3, 0), fs=2000.0, n_aux=3, n_supply=1, ts0=0) -> None:
    """Write a small RHD file: ``amp`` is (C, N) uint16 raw codes."""
    C, n = amp.shape
    N = 128 if version[0] >= 3 else 60
    assert n % N == 0
    h = struct.pack("<I", T.RHD_MAGIC) + struct.pack("<hh", *version) + struct.pack("<f", fs)
    h += struct.pack("<h", 0) + struct.pack("<ffffff", 1.0, 7.7, 500.0, 1.0, 7.7, 500.0)
    h += struct.pack("<h", 0) + struct.pack("<ff", 1000.0, 1000.0)
    h += _qs("") + _qs("") + _qs("")
    h += struct.pack("<h", 0)  # temp sensors (>= 1.1)
    h += struct.pack("<h", 0)  # eval board mode (>= 1.3)
    if version[0] > 1:
        h += _qs("n/a")
    h += struct.pack("<h", 1)  # one signal group
    h += _qs("Port A") + _qs("A") + struct.pack("<hhh", 1, C + n_aux + n_supply, C)

    def chan(name, typ, order):
        return _qs(name) + _qs(name) + struct.pack("<hhhh", order, order, typ, 1) + struct.pack("<hhhhhh", 0, 0, 0, 0, 0, 0) + struct.pack("<ff", 0, 0)

    for c in range(C):
        h += chan(f"A-{c:03d}", 0, c)
    for a in range(n_aux):
        h += chan(f"A-AUX{a + 1}", 1, a)
    for s in range(n_supply):
        h += chan(f"A-VDD{s + 1}", 2, s)
    body = bytearray()
    for b in range(n // N):
        body += np.arange(ts0 + b * N, ts0 + (b + 1) * N, dtype="<i4").tobytes()
        body += amp[:, b * N : (b + 1) * N].astype("<u2").tobytes()  # channel-major within a block
        body += np.zeros((n_aux, N // 4), "<u2").tobytes()
        body += np.zeros(n_supply, "<u2").tobytes()
    path.write_bytes(h + bytes(body))


def test_read_rhd_roundtrip(tmp_path):
    rng = np.random.default_rng(0)
    raw = rng.integers(30000, 35000, size=(16, 256)).astype(np.uint16)
    p = tmp_path / "A_220901_104337.rhd"
    write_rhd(p, raw, ts0=10)
    r = T.read_rhd(p)
    assert r.version == (3, 0) and r.sample_rate == 2000.0
    assert r.amplifier_uv.shape == (16, 256)
    assert r.channel_names[0] == "A-000" and len(r.channel_names) == 16
    np.testing.assert_allclose(r.amplifier_uv, 0.195 * (raw.astype(np.float32) - 32768), rtol=1e-6)
    assert np.all(np.diff(r.timestamps) == 1) and r.timestamps[0] == 10
    assert r.duration_s == pytest.approx(256 / 2000)
    assert r.bandwidth_hz[1] == pytest.approx(500.0)


def test_read_rhd_v1_blocks(tmp_path):
    raw = np.full((4, 120), 32768, np.uint16)
    p = tmp_path / "x.rhd"
    write_rhd(p, raw, version=(1, 3), n_aux=0, n_supply=0)
    r = T.read_rhd(p)
    assert r.amplifier_uv.shape == (4, 120) and np.all(r.amplifier_uv == 0)


def test_read_rhd_rejects_bad_files(tmp_path):
    p = tmp_path / "bad.rhd"
    p.write_bytes(b"\x00" * 64)
    with pytest.raises(T.RhdFormatError):
        T.read_rhd(p)
    raw = np.full((16, 128), 32768, np.uint16)
    q = tmp_path / "trunc.rhd"
    write_rhd(q, raw)
    q.write_bytes(q.read_bytes()[:-7])  # not a whole block
    with pytest.raises(T.RhdFormatError):
        T.read_rhd(q)
    with pytest.raises(T.RhdFormatError):
        T.read_rhd(q, max_bytes=100)


# --- keylog and alignment ---------------------------------------------------------

KEYLOG = """Python 3.10.6 (tags/v3.10.6)
= RESTART: C:\\somewhere\\KeyloggerV2.py
 2022-09-01 10:43:40,000 - Key.space
 2022-09-01 10:43:41,500 - Key.space
 2022-09-01 10:43:43,000 - 'a'
 2022-09-01 10:43:44,000 - 'q'
 2022-09-01 10:43:45,250 - 'A'
 2022-09-01 10:43:46,000 - Key.shift
 2022-09-01 10:44:30,000 - 'a'
"""


def test_keylog_and_key_events(tmp_path):
    (tmp_path / "Keylogs.txt").write_text(KEYLOG, encoding="utf-8")
    (tmp_path / "LAG_TIMINGS.csv").write_text("Filename,Lag,Error\nA_220901_104337,-0.5,0.1\nbad,x,y\n", encoding="utf-8")
    kl = T.parse_keylog(tmp_path / "Keylogs.txt")
    assert len(kl) == 7 and kl[0].char == " " and kl[3].char == "q" and kl[5].char is None
    lags = T.load_lag_timings(tmp_path / "LAG_TIMINGS.csv")
    assert lags == {"A_220901_104337": (-0.5, 0.1)}
    letter, start = T.parse_recording_name("A_220901_104337")
    assert letter == "a" and start == datetime(2022, 9, 1, 10, 43, 37)
    rec = T.RecordingInfo("P1", "T1", "A_220901_104337", letter, start, tmp_path / "x.rhd")
    ev = T.key_events(rec, kl, lag_s=-0.5, duration_s=16.0, margin_s=0.35)
    # 'q' (wrong key) and Key.shift dropped; 10:44:30 is after the end.
    assert [(round(e.t, 3), e.char) for e in ev] == [(2.5, " "), (4.0, " "), (5.5, "a"), (7.75, "a")]


def test_key_label():
    assert T.key_label("Key.space") == " " and T.key_label("'Z'") == "z"
    assert T.key_label("Key.enter") is None and T.key_label("'1'") is None


# --- streams ------------------------------------------------------------------------


def _logits_for(text: str, peak: float = 6.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    lg = rng.normal(0, 0.5, (len(text), 27))
    lg[np.arange(len(text)), T.chars_to_ids(text)] += peak
    return lg


def test_keypress_stream_valid_and_no_text():
    text = "hello all"
    s = T.keypress_stream(_logits_for(text), np.arange(1, len(text) + 1) * 0.8, T.stream_meta("P1", "T2"))
    assert s.vocab_type == "key" and s.blank_id is None and s.vocab[0] == "KeyA" and s.vocab[-1] == "Space"
    np.testing.assert_allclose(np.logaddexp.reduce(s.log_probs, axis=1), 0, atol=1e-4)
    assert T.greedy_keys(s) == text
    blob = json.dumps(s.meta)
    assert "hello" not in blob and s.meta["device.modality"] == "emg" and s.meta["data.derived"] is True
    assert s.meta["decoder.causal"] is False and s.meta["subject.id"] == "P1"


def test_ctc_form_keeps_double_letters_and_roundtrips(tmp_path):
    text = "all good"
    s = T.keypress_stream(_logits_for(text), T.compose_times(len(text), 0.79))
    c = T.to_ctc_char_stream(s)
    assert c.n_frames == 2 * len(text) - 1 and c.blank_id == 0 and c.vocab_type == "char"
    assert np.all(np.diff(c.frame_times) > 0)
    np.testing.assert_allclose(np.logaddexp.reduce(c.log_probs.astype(np.float64), axis=1), 0, atol=1e-4)
    assert ctc_greedy_decode(c) == text  # "ll" and "oo" survive the CTC collapse
    back = T.from_ctc_char_stream(c)
    np.testing.assert_allclose(back.log_probs, s.log_probs, atol=1e-4)
    np.testing.assert_allclose(back.frame_times, s.frame_times)
    assert back.meta["fidetype.vocab_id"] == T.KEY_VOCAB_ID
    p = tmp_path / "s.npz"
    c.to_npz(p)
    r = NeuralTextStream.from_npz(p)
    assert r.vocab == c.vocab and r.blank_id == 0
    p2 = tmp_path / "k.npz"
    s.to_npz(p2)
    assert NeuralTextStream.from_npz(p2).blank_id is None


def test_ctc_form_edge_cases():
    one = T.keypress_stream(_logits_for("a"), [0.5])
    assert T.to_ctc_char_stream(one).n_frames == 1
    empty = T.keypress_stream(np.zeros((0, 27)), np.zeros(0))
    assert T.to_ctc_char_stream(empty).n_frames == 0
    with pytest.raises(ValueError):
        T.keypress_stream(np.zeros((2, 26)), [0.1, 0.2])
    with pytest.raises(ValueError):  # times must increase strictly
        T.keypress_stream(np.zeros((2, 27)), [0.1, 0.1])
    with pytest.raises(ValueError):
        T.to_ctc_char_stream(one, key_blank=0.0)


def test_text_helpers():
    assert T.is_typeable("the cat") and not T.is_typeable("the  cat") and not T.is_typeable("don't")
    assert list(T.chars_to_ids("az ")) == [0, 25, 26]
    with pytest.raises(ValueError):
        T.chars_to_ids("A")


@pytest.mark.skipif(not REAL_ROOT.exists(), reason="Toronto sEMG data not downloaded")
def test_real_recording():
    recs = T.list_recordings(REAL_ROOT)
    assert len(recs) == 1968
    r0 = recs[0]
    rec = T.read_rhd(r0.path)
    assert rec.amplifier_uv.shape[0] == 16 and rec.sample_rate == 2000.0
    sdir = r0.path.parent.parent
    ev = T.key_events(r0, T.parse_keylog(sdir / "Keylogs.txt"), T.load_lag_timings(sdir / "LAG_TIMINGS.csv")[r0.stem][0], rec.duration_s)
    chars = [e.char for e in ev]
    assert chars.count(r0.letter) >= 8 and chars.count(" ") >= 3
