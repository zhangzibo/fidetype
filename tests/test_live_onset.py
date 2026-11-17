"""P4-10: causal key-onset detectors (``fidetype live --timing detect``). No data, no optional package."""

from __future__ import annotations

import json

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.conformance import check_file
from fidetype.live import onset as O
from fidetype.live import sources as S
from fidetype.live.__main__ import main as live_main
from fidetype.live.build import kt_chunks, kt_markers
from fidetype.live.model import load_model, resolve_asset
from fidetype.live.runner import LiveDecoder, make_writer


def _bursts(fs: float = 2000.0, c: int = 4, n_s: float = 20.0, seed: int = 0):
    """Noise with short high-energy bursts (40 ms) at random times: a stand-in for key EMG."""
    rng = np.random.default_rng(seed)
    n = int(n_s * fs)
    x = rng.normal(0, 1.0, size=(n, c)).astype(np.float32)
    on = np.sort(rng.uniform(2.0, n_s - 1.0, size=30))
    on = on[np.concatenate([[True], np.diff(on) > 0.2])]
    for t in on:
        i = int(t * fs)
        x[i:i + int(0.04 * fs)] += rng.normal(0, 6.0, size=(int(0.04 * fs), c)).astype(np.float32)
    return x, np.arange(n) / fs, on


def _chunks(x, t, sizes):
    i, k = 0, 0
    while i < len(t):
        j = min(len(t), i + sizes[k % len(sizes)])
        yield x[i:j], t[i:j]
        i, k = j, k + 1


def test_front_end_does_not_depend_on_chunking():
    x, t, _ = _bursts(n_s=3.0)
    a = O.FrontEnd(2000.0, 4)
    fa, ta = a.process(x, t)
    b = O.FrontEnd(2000.0, 4)
    parts = [b.process(xx, tt) for xx, tt in _chunks(x, t, [7, 333, 1, 50])]
    fb = np.concatenate([p[0] for p in parts])
    tb = np.concatenate([p[1] for p in parts])
    assert np.allclose(fa, fb) and np.allclose(ta, tb)
    assert len(fa) == len(t) // 10 and np.isclose(ta[0], t[9])


def test_block_scaler_is_causal_and_chunk_free():
    rng = np.random.default_rng(1)
    x = rng.normal(3.0, 2.0, size=(1000, 3))
    a = O.BlockScaler(np.zeros(3), np.ones(3), update_n=100).transform(x)
    s = O.BlockScaler(np.zeros(3), np.ones(3), update_n=100)
    b = np.concatenate([s.transform(x[i:i + 37]) for i in range(0, 1000, 37)])
    assert np.allclose(a, b)
    assert np.allclose(a[:100], x[:100])  # the first block uses the prior only (mean 0, sd 1)
    assert abs(a[-100:].mean()) < 0.5  # later blocks adapt


def test_peak_picker_threshold_and_refractory():
    s = np.array([0, 1, 3, 1, 0, 2, 0, 0, 5, 4, 0], float)
    t = np.arange(len(s)) * 0.01
    assert O.PeakPicker(1.5, 0.0).push(s, t) == pytest.approx([0.02, 0.05, 0.08])
    assert O.PeakPicker(1.5, 0.04).push(s, t) == pytest.approx([0.02, 0.08])  # 0.05 is 30 ms after 0.02
    pk = O.PeakPicker(1.5, 0.0)
    got = pk.push(s[:3], t[:3]) + pk.push(s[3:], t[3:])  # one step of look-ahead across chunks
    assert got == pytest.approx([0.02, 0.05, 0.08])


def test_envelope_detector_finds_bursts():
    x, t, on = _bursts()
    det = O.EnvelopeDetector(2000.0, 4, theta=3.0, lag_s=0.0)
    found = []
    for xx, tt in _chunks(x, t, [400, 123]):
        found += det.process(xx, tt)
    m = O.match_onsets(on, found, 0.05)
    assert m["recall"] >= 0.9 and m["precision"] >= 0.9, m
    assert np.median(np.abs(m["errors"])) < 0.02


def test_linear_detector_fit_stream_equals_batch(tmp_path):
    x, t, on = _bursts(seed=2)
    C, ctx = 4, 6
    raw = O.LinearOnsetDetector(2000.0, C, np.zeros(ctx * C), 0.0, np.zeros(C), np.ones(C), context=ctx)
    st, stt = raw.steps(x, t)
    mu, sd = st.mean(0), st.std(0) + 1e-9
    det = O.LinearOnsetDetector(2000.0, C, np.zeros(ctx * C), 0.0, mu, sd, context=ctx, delay_s=0.03)
    z = det.scaler.transform(st)
    rows, drop = det.stack(z)
    tt = stt[drop:] - 0.03
    y = np.min(np.abs(tt[:, None] - on[None, :]), axis=1) <= 0.01
    w, b = O.fit_linear(rows, y)
    d1 = O.LinearOnsetDetector(2000.0, C, w, b, mu, sd, context=ctx, delay_s=0.03, theta=0.0)
    p = O.save_onset(d1, tmp_path / "d.onset.json")
    d2 = O.load_onset(p, 2000.0, C)
    a = d1.process(x, t)
    bb = []
    for xx, tt2 in _chunks(x, t, [999, 20, 3001]):
        bb += d2.process(xx, tt2)
    assert len(a) == len(bb) and np.allclose(a, bb)
    m = O.match_onsets(on, a, 0.05)
    assert m["f1"] >= 0.8, m
    with pytest.raises(ValueError, match="channel"):
        O.load_onset(p, 2000.0, C + 1)


def test_match_onsets_is_one_to_one():
    m = O.match_onsets([1.0, 1.04, 2.0], [1.02, 1.03, 3.0], 0.05)
    assert m["tp"] == 2 and m["fp"] == 1 and m["fn"] == 1
    assert m["f1"] == pytest.approx(4 / 6)
    assert sorted(np.round(np.abs(m["errors"]), 3)) == [0.01, 0.02]


def test_load_onset_envelope_defaults_and_bad_file(tmp_path):
    d = O.load_onset("envelope", 2000.0, 32)
    assert d.kind == "envelope" and d.params["theta"] == O.ENVELOPE_DEFAULTS["theta"]
    bad = tmp_path / "x.onset.json"
    bad.write_text(json.dumps({"schema": "other"}))
    with pytest.raises(ValueError, match="schema"):
        O.load_onset(bad, 2000.0, 32)


# --- detect timing in the live loop ------------------------------------------------------------------


@pytest.fixture(scope="module")
def model():
    return load_model("builtin:synthetic-keys")


@pytest.fixture(scope="module")
def guard():
    return ft.load(resolve_asset("builtin:synthetic-keys", ".guard.json"))


def test_detect_timing_on_synthetic(tmp_path, model, guard):
    src = S.SyntheticSource(6, seed=7, speed=0)
    det = O.EnvelopeDetector(src.fs, src.x.shape[1], theta=2.0, lag_s=0.0)
    out = tmp_path / "det.nts.jsonl"
    w = make_writer(str(out), model, src.info, guard, "synthetic", "detect")
    dec = LiveDecoder(model, guard, src, timing="detect", detector=det, writer=w)
    st = dec.run()
    w.close()
    assert st.onsets > 0 and st.decisions >= 3 and st.decisions + st.empty_segments == 6
    assert st.frames == st.onsets - st.late_keys
    true = [t for u in src.utterances for t in u.key_times]
    found = O.EnvelopeDetector(src.fs, src.x.shape[1], theta=2.0).process(src.x, np.arange(len(src.x)) / src.fs)
    assert O.match_onsets(true, found, 0.05)["recall"] > 0.15  # 250 Hz, noisy synthetic keys: a weak case
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert evs[0]["meta"]["fidetype.live"]["timing"] == "detect"
    assert not check_file(out).failures("trust-ready")


def test_detect_timing_needs_a_detector(model, guard):
    with pytest.raises(ValueError, match="onset detector"):
        LiveDecoder(model, guard, S.SyntheticSource(1, seed=0, speed=0), timing="detect")


def test_cli_detect_timing(tmp_path, capsys):
    out, summ = tmp_path / "c.nts.jsonl", tmp_path / "c.json"
    rc = live_main(["--source", "synthetic", "--utterances", "3", "--speed", "0", "--timing", "detect",
                    "--onset", "envelope", "--json", "--out", str(out), "--summary", str(summ)])
    assert rc == 0
    s = json.loads(summ.read_text())
    assert s["timing"] == "detect" and s["decisions"] >= 1 and s["decisions"] + s["empty_segments"] >= 3 and s["onsets"] > 0
    assert not check_file(out).failures("trust-ready")
    assert live_main(["--source", "synthetic", "--timing", "detect", "--onset", str(tmp_path / "none.json")]) == 2


def test_kt_chunks_and_markers():
    class E:
        def __init__(self, t: float) -> None:
            self.t = t

    ev = [E(x) for x in (1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 5.0, 5.2)]
    assert kt_chunks([(0, 7), (7, 9)], 3) == [(0, 3), (3, 7), (7, 9)]
    mk = kt_markers(ev, [(0, 3), (3, 7)])
    ends = [t for t, m in mk if m == "segment_end"]
    assert ends == pytest.approx([1.5, 2.7])  # half way to the next key, else 0.5 s
