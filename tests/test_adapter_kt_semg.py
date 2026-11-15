"""Tests for the KT-sEMG adapter (synthetic fixtures only)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from fidetype.adapters import kt_semg as K
from fidetype.conformance import check_stream


def test_key_vocab_and_codes():
    assert len(K.KEY_VOCAB) == 32 and K.KEY_VOCAB[0] == "KeyA" and K.KEY_VOCAB[26] == "Space"
    assert K.key_class("a") == 0 == K.key_class("A") and K.key_class(" ") == 26
    assert K.KEY_VOCAB[K.key_class("\x08")] == "Backspace" and K.KEY_VOCAB[K.key_class("\r")] == "Enter"
    assert K.key_code("4") == "Digit4" and K.key_class("4") is None and K.key_code("~") is None


KEYS = (b"a 1571419437.768938\n"
        b"  1571419438.0\n"            # space bar
        b"\x08 1571419438.5\n"         # backspace
        b"\r\n 1571419439.25\n"        # Enter logged as CRLF: split over two lines
        b"\r 1571419440.0\n"           # Enter logged as CR
        b"E 1571419441.125\r\n"        # CRLF line end
        b"garbage line\n"
        b"\n")


def test_parse_keys_handles_space_backspace_and_enter():
    ks = K.parse_keys(KEYS)
    assert [k.char for k in ks] == ["a", " ", "\x08", "\r", "\r", "E"]
    assert ks[3].unix_s == pytest.approx(1571419439.25) and ks[0].code == "KeyA" and ks[5].code == "KeyE"


def test_start_time_and_utc_offset():
    st = K.parse_start_time("2019-10-18 13:23:49.445\n")
    assert st == datetime(2019, 10, 18, 13, 23, 49, 445000)
    true_start = st.replace(tzinfo=timezone(timedelta(hours=-4))).timestamp()
    keys = true_start + np.linspace(5, 120, 50)
    assert K.infer_utc_offset_hours(st, keys, 128.0) == -4
    assert K.start_unix(st, -4) == pytest.approx(true_start)
    with pytest.raises(ValueError, match="no UTC offset"):
        K.infer_utc_offset_hours(st, keys + 1800, 10.0)
    with pytest.raises(ValueError):
        K.parse_start_time("yesterday")


def _write_csv(path, emg, fs=2000.0):
    names = [f"i1 {c + 1}" for c in range(8)] + [f"i2 {c + 1}" for c in range(8)] + \
            [f"i1b {c + 1}" for c in range(8)] + [f"i2b {c + 1}" for c in range(8)]
    lines = ["Time\t" + "\t".join(names)]
    for n, row in enumerate(emg):
        lines.append(f"{n / fs:g}\t" + "\t".join(f"{v:g}" for v in row))
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def test_read_emg_csv_chunks_and_errors(tmp_path):
    rng = np.random.default_rng(0)
    emg = rng.normal(0, 1, (301, 32)).round(4)
    p = tmp_path / "run7.csv"
    _write_csv(p, emg)
    rec = K.read_emg_csv(p, chunk_bytes=997)  # many chunks, rows cut at chunk edges
    assert rec.emg.shape == (301, 32) and rec.channel_names[0] == "i1 1" and rec.channel_names[-1] == "i2b 8"
    np.testing.assert_allclose(rec.emg, emg, atol=1e-4)
    assert rec.duration_s == pytest.approx(301 / 2000)
    bad = tmp_path / "bad.csv"
    bad.write_text("Time\ta\tb\n0\t1\t2\n", encoding="ascii")
    with pytest.raises(ValueError, match="header"):
        K.read_emg_csv(bad)
    p.write_text(p.read_text().replace("\n0.001\t", "\n0.001\tx", 1), encoding="ascii")
    with pytest.raises(ValueError):
        K.read_emg_csv(p)
    with pytest.raises(ValueError, match="too large"):
        K.read_emg_csv(p, max_bytes=10)


def test_list_runs(tmp_path):
    for n in (10, 2):
        for suffix in (".csv", "_keys.txt", "_ts.txt"):
            (tmp_path / f"run{n}{suffix}").write_text("")
    (tmp_path / "run3.csv").write_text("")  # incomplete run
    assert [r.run for r in K.list_runs(tmp_path)] == [2, 10]


def test_key_events_and_segments():
    ks = [K.KeyPress(100.0 + t, c) for t, c in ((0.1, "a"), (1.0, "b"), (1.0, "c"), (2.0, "d"), (9.0, "e"), (20, "f"))]
    ev = K.key_events(ks, start_s=100.0, duration_s=10.0, margin_s=0.2)
    assert [(round(e.t, 3), e.char) for e in ev] == [(1.0, "b"), (2.0, "d"), (9.0, "e")]  # duplicate time dropped
    assert K.segment_events([0, 0.5, 1.0, 4.0, 4.2, 9.0], max_gap_s=2.0) == [(0, 3), (3, 5), (5, 6)]
    assert K.segment_events([0, 0.5, 1.0, 4.0, 4.2, 9.0], max_gap_s=2.0, min_len=2) == [(0, 3), (3, 5)]
    assert K.segment_events([]) == []


def _synthetic_emg(seed=0, n_keys=240, fs=2000.0):
    """Each key class drives its own channel group: a separable toy problem."""
    rng = np.random.default_rng(seed)
    classes = rng.integers(0, 6, n_keys)
    times = 0.5 + 0.4 * np.arange(n_keys)
    N = int((times[-1] + 1.0) * fs)
    emg = rng.normal(0, 1.0, (N, 32)).astype(np.float32)
    for t, c in zip(times, classes):
        a = int((t - 0.1) * fs)
        emg[a:a + 200, 5 * c:5 * c + 5] *= 6.0
    return emg, times, classes


def test_window_features_and_lda_decoder(tmp_path):
    emg, times, y = _synthetic_emg()
    X = K.standardize_run(K.window_features(emg, times))
    assert X.shape == (len(times), 64) and np.isfinite(X).all()
    n = len(y) // 2
    dec = K.LdaKeyDecoder.fit(X[:n], y[:n], shrinkage=0.3)
    lp = dec.predict_log_proba(X[n:])
    assert lp.shape == (len(y) - n, 32)
    np.testing.assert_allclose(np.logaddexp.reduce(lp, axis=1), 0, atol=1e-9)
    assert np.mean(lp.argmax(1) == y[n:]) > 0.9
    sha = dec.save(tmp_path / "w.npz")
    assert len(sha) == 64
    np.testing.assert_allclose(K.LdaKeyDecoder.load(tmp_path / "w.npz").predict_log_proba(X[n:]), lp)
    # windows at the recording edge are clipped, not an error
    edge = K.window_features(emg, [0.0, len(emg) / 2000.0 + 5])
    assert np.isfinite(edge).all() and np.all(edge[1] == 0)
    with pytest.raises(ValueError):
        K.LdaKeyDecoder.fit(X[:3], np.array([0, 1, 40]))


def test_keypress_stream_meta_and_conformance():
    text = "hi, you."
    lg = np.random.default_rng(1).normal(0, 1, (len(text), 32))
    lg[np.arange(len(text)), [K.key_class(c) for c in text]] += 5
    times = np.arange(1, len(text) + 1) * 0.3
    meta = K.stream_meta(run_index=2, segment_index=1, weights_sha256="0" * 64, stream_id=K.opaque_stream_id("x"))
    s = K.keypress_stream(lg, times, meta, latency=0.05)
    assert s.vocab_type == "key" and s.blank_id is None and s.latency == 0.05
    assert s.meta["decoder.causal"] is True and s.meta["decoder.lookahead_s"] == 0.05
    assert K.greedy_codes(s)[:3] == ["KeyH", "KeyI", "Comma"]
    blob = json.dumps(s.meta)
    assert "hi, you" not in blob and "subject.id" not in s.meta and "session.id" not in s.meta
    assert s.meta["fidetype.replay"]["run_index"] == 2 and s.meta["fidetype.replay"]["licence"] == K.LICENCE
    rep = check_stream(s, "kt", [text])
    assert rep.level == "provenance", [f.to_dict() for f in rep.failures()]
    off = K.keypress_stream(lg, times, meta)
    assert off.latency is None and off.meta["decoder.causal"] is False and "decoder.lookahead_s" not in off.meta
    assert check_stream(off, "kt-off", [text]).level == "provenance"
    with pytest.raises(ValueError):
        K.keypress_stream(lg[:, :27], times, meta)
