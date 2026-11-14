"""M6-08: BrainFlow -> LSL bridge, toy signal decoders, and the raw-signal path into the trust layer.

The unit tests use :class:`FakeBoard` and recording outlets (no brainflow,
no pylsl). The integration test at the end needs both and skips otherwise.
"""

from __future__ import annotations

import math
import threading
import time
import uuid

import numpy as np
import pytest

from fidetype.adapters import brainflow_bridge as B
from fidetype.adapters import lsl as L
from fidetype.adapters.lsl import LSLEventSource, LSLMapping, LSLStreamInfo, LSLTrustRunner, ScriptedInlet
from fidetype.decoders.toy_signal import ToySignalDecoder, toy_signal_decoder
from fidetype.streams.vocab import VOCAB
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer


class RecOutlet:
    def __init__(self) -> None:
        self.chunks: list[tuple[np.ndarray, list[float]]] = []
        self.samples: list[tuple[list, float]] = []

    def push_chunk(self, x, timestamp=0.0, pushthrough=True):
        self.chunks.append((np.asarray(x), list(timestamp)))

    def push_sample(self, x, timestamp=0.0, pushthrough=True):
        self.samples.append((list(x), float(timestamp)))


class Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _bridge(trial_s=1.0, pauses=(), n_eeg=4, packet=4, **kw):
    wall = Clock(1_700_000_000.0)
    board = B.FakeBoard(n_eeg=n_eeg, packet=packet, clock=wall)
    outs: dict = {}

    def outlets(sd, sid, esid):
        outs.update(sd=sd, sid=sid, esid=esid, sig=RecOutlet(), mk=RecOutlet())
        return outs["sig"], outs["mk"]

    lsl_clock = lambda: wall.t - 1_699_999_000.0  # noqa: E731 - LSL clock = wall - const
    cfg = B.BridgeConfig(name="test.bf", trial_s=trial_s, pauses=pauses, **kw)
    br = B.BrainFlowBridge(board, board.descr, -1, cfg, outlets=outlets, lsl_clock=lsl_clock, wall_clock=wall)
    return br, board, wall, outs


def _drive(br, wall, seconds, dt=0.02):
    br.start()
    for _ in range(int(round(seconds / dt))):
        wall.t += dt
        br.step()


# --- bridge ---------------------------------------------------------------


def test_board_id_from_name():
    assert B.board_id_from_name("synthetic") == B.SYNTHETIC_BOARD_ID == -1
    assert B.board_id_from_name("-1") == -1
    assert B.board_id_from_name(" 0 ") == 0


def test_stream_desc_follows_fep0002_raw_signal():
    br, board, wall, outs = _bridge()
    sd = outs["sd"]
    assert sd["type"] == "EEG" and sd["srate"] == 250.0
    assert sd["labels"] == ["E1", "E2", "E3", "E4"] and sd["rows"] == [1, 2, 3, 4]
    f = sd["fidetype"]
    assert f["role"] == "signal" and f["binding"] == L.BINDING_VERSION
    assert f["events_source_id"] == outs["esid"] == outs["sid"] + ".markers"
    assert "nts_header" not in f  # a raw signal stream: the consumer needs a signal decoder
    # names that do not match the channel count fall back to ch<N>
    d = dict(board.descr, eeg_names="Fz")
    assert B.stream_desc(d, -1, B.BridgeConfig(), "x")["labels"] == ["ch1", "ch2", "ch3", "ch4"]
    with pytest.raises(ValueError):
        B.stream_desc(board.descr, -1, B.BridgeConfig(kind="emg"), "x")


def test_bursty_board_stamps_become_regular():
    br, board, wall, outs = _bridge()
    _drive(br, wall, 3.0)
    ts = np.concatenate([c[1] for c in outs["sig"].chunks])
    x = np.concatenate([c[0] for c in outs["sig"].chunks])
    assert x.shape[1] == 4 and x.dtype == np.float32 and len(ts) == br.stats.samples > 700
    step = np.diff(ts)
    p = 1 / 250
    assert step.min() > 0.5 * p - 1e-9 and step.max() < 2.5 * p  # no false gap for an LSL consumer
    assert br.stats.jumps == 0


def test_pause_discards_and_makes_one_jump():
    br, board, wall, outs = _bridge(pauses=[(1.0, 0.5)])
    t0 = wall.t
    br._paused = lambda now: 1.0 <= wall.t - t0 < 1.5  # type: ignore[method-assign]
    br.board.start_stream()
    for _ in range(150):
        wall.t += 0.02
        br.step()
    ts = np.concatenate([c[1] for c in outs["sig"].chunks])
    big = np.diff(ts) > 2.5 / 250
    assert br.stats.discarded > 100 and br.stats.jumps == 1 and big.sum() == 1
    assert 0.4 < np.diff(ts)[big][0] < 0.6


class _SteadyBoard(B.FakeBoard):
    """A board that makes samples at a steady rate (monotonic clock) and stamps them with the wall clock.

    This is how the BrainFlow Synthetic board behaved in the M6-13 soak test when Windows set the wall
    clock: the data kept flowing, and the board stamps moved with the wall clock.
    """

    def __init__(self, mono: Clock, wall: Clock, **kw) -> None:
        super().__init__(clock=wall, **kw)
        self.mono = mono

    def start_stream(self) -> None:
        super().start_stream()
        self.m0 = self.mono()

    def get_board_data(self) -> np.ndarray:
        due = int((self.mono() - self.m0) * self.srate)
        k = max(0, due - self.n)
        d = np.zeros((self.descr["num_rows"], k))
        for ch in self.descr["eeg_channels"]:
            d[ch] = self.rng.standard_normal(k)
        d[self.descr["timestamp_channel"]] = self.clock() - (k - 1 - np.arange(k)) / self.srate
        self.n += k
        return d


@pytest.mark.parametrize("step_s", [-1.361, +1.4])
def test_wall_clock_step_does_not_shift_stamps(step_s):
    """M6-13: a wall-clock step (Windows time sync) must not move the LSL stamps or make a false gap."""
    mono, wall = Clock(500.0), Clock(1_700_000_000.0)
    board = _SteadyBoard(mono, wall, n_eeg=4)
    sig = RecOutlet()
    cfg = B.BridgeConfig(name="test.bf", trial_s=None)
    br = B.BrainFlowBridge(board, board.descr, -1, cfg, outlets=lambda sd, sid, esid: (sig, RecOutlet()),
                           lsl_clock=mono, wall_clock=wall)
    br.start()
    for i in range(500):  # 10 s, step at 5 s
        mono.t += 0.02
        wall.t += 0.02
        if i == 250:
            wall.t += step_s
        br.step()
    ts = np.concatenate([c[1] for c in sig.chunks])
    step = np.diff(ts)
    p = 1 / 250
    assert br.stats.clock_steps == 1 and br.stats.jumps == 0
    assert step.min() > 0 and step.max() < 2.5 * p  # monotonic, no false gap
    lag = np.asarray(br.stats.push_lag_s[-100:])
    assert np.abs(lag).max() < 0.05  # the stamps stay on the LSL clock (before the fix: about |step_s|)


def test_slow_wall_clock_drift_is_followed():
    mono, wall = Clock(500.0), Clock(1_700_000_000.0)
    board = _SteadyBoard(mono, wall, n_eeg=4)
    sig = RecOutlet()
    br = B.BrainFlowBridge(board, board.descr, -1, B.BridgeConfig(name="t", trial_s=None),
                           outlets=lambda sd, sid, esid: (sig, RecOutlet()), lsl_clock=mono, wall_clock=wall)
    br.start()
    for _ in range(3000):  # 60 s, the wall clock runs 500 ppm slow (slewing)
        mono.t += 0.02
        wall.t += 0.02 * (1 - 500e-6)
        br.step()
    assert br.stats.clock_steps == 0 and br.stats.jumps == 0
    assert np.abs(np.asarray(br.stats.push_lag_s[-100:])).max() < 0.01


def test_trial_markers_on_boundaries_and_during_dropout():
    br, board, wall, outs = _bridge(trial_s=1.0)
    t0 = wall.t
    br._paused = lambda now: 2.1 <= wall.t - t0 < 3.6  # type: ignore[method-assign]
    br.board.start_stream()
    for _ in range(250):
        wall.t += 0.02
        br.step()
    mk = outs["mk"].samples
    assert [m[0] for m in mk] == [[B.SEGMENT_END]] * len(mk) and br.stats.markers == len(mk) >= 4
    times = [m[1] for m in mk]
    assert np.allclose(np.diff(times), 1.0)  # a fixed trial clock, also through the dropout
    first = outs["sig"].chunks[0][1][0]
    assert abs(times[0] - (first + 1.0)) < 1e-9


def test_board_marker_channel_becomes_plain_marker():
    br, board, wall, outs = _bridge(trial_s=None)
    br.start()
    board.insert_marker(7)
    for _ in range(5):
        wall.t += 0.02
        br.step()
    assert outs["mk"].samples[0][0] == ["brainflow_marker:7"] and br.stats.board_markers == 1


def test_stats_dict_and_parse_pause():
    br, board, wall, outs = _bridge()
    _drive(br, wall, 0.5)
    d = br.stats.as_dict()
    assert d["samples"] > 0 and "push_lag_ms" in d and "push_lag_s" not in d
    assert B.parse_pause("20:3") == (20.0, 3.0)
    with pytest.raises(ValueError):
        B.parse_pause("5:0")


# --- toy decoder ----------------------------------------------------------


def test_toy_decoder_frames_and_header():
    dec = ToySignalDecoder(250.0, 4, mode="flat")
    assert dec.window == 10 and math.isclose(dec.header["frame_period"], 0.04)
    m = dec.header["meta"]
    assert m["decoder.toy"] is True and m["decoder.text_information"] == "none" and m["fidetype.synthetic"]
    assert dec.header["vocab"] == list(VOCAB) and dec.header["blank_id"] == 0
    t = 10.0 + np.arange(25) / 250
    out = dec.process(np.zeros((25, 4)), t) + dec.process(np.zeros((5, 4)), 10.1 + np.arange(5) / 250)
    assert len(out) == 3 and [o[0] for o in out] == sorted({o[0] for o in out})
    for _, lp in out:
        assert lp.shape == (len(VOCAB),) and math.isclose(np.exp(lp).sum(), 1.0, rel_tol=1e-9)
    with pytest.raises(ValueError):
        ToySignalDecoder(0.0, 4)
    with pytest.raises(ValueError):
        toy_signal_decoder("words", 250.0, 4)


def test_toy_flat_ignores_signal_features_follow_it():
    rng = np.random.default_rng(0)
    t = np.arange(500) / 250
    a, b = rng.standard_normal((500, 4)), 50 * rng.standard_normal((500, 4))
    f1 = [lp for _, lp in ToySignalDecoder(250, 4, "flat", seed=3).process(a, t)]
    f2 = [lp for _, lp in ToySignalDecoder(250, 4, "flat", seed=3).process(b, t)]
    assert np.allclose(f1, f2)  # flat: the signal does not matter
    assert max(np.exp(lp).max() for lp in f1) < 2.0 / len(VOCAB)  # near uniform
    x = np.concatenate([a[:250], 30 * a[250:]])
    g = np.array([lp for _, lp in ToySignalDecoder(250, 4, "features", seed=3).process(x, t)])
    assert g.std(axis=0).mean() > 0.05  # features: frames change with the signal


# --- raw-signal path without the network ------------------------------------


def _scripted_signal(outs, srate=250.0) -> tuple[ScriptedInlet, ScriptedInlet]:
    sd = outs["sd"]
    si = LSLStreamInfo("test.bf", sd["type"], len(sd["labels"]), srate, "float32", outs["sid"],
                       channel_labels=sd["labels"], channel_units=[B.UNIT] * len(sd["labels"]),
                       fidetype={k: str(v) for k, v in sd["fidetype"].items()})
    mi = LSLStreamInfo("test.bf.markers", "Markers", 1, 0.0, "string", outs["esid"],
                       fidetype={"role": "signal_markers", "binding": L.BINDING_VERSION})
    sig = ScriptedInlet(si, [(c[0].tolist(), c[1]) for c in outs["sig"].chunks])
    mk = ScriptedInlet(mi, [([m[0]], [m[1]]) for m in outs["mk"].samples])
    return sig, mk


@pytest.mark.parametrize("mode", ["flat", "features"])
def test_bridge_to_trust_layer_never_commits_on_toy_input(mode):
    from fidetype.demo import build_decoder, load_config

    br, board, wall, outs = _bridge(trial_s=2.0, n_eeg=4)
    t0 = wall.t
    br._paused = lambda now: 5.0 <= wall.t - t0 < 5.5  # type: ignore[method-assign]
    br.board.start_stream()
    for _ in range(int(12.0 / 0.02)):
        wall.t += 0.02
        br.step()
    sig, mk = _scripted_signal(outs)
    dec = toy_signal_decoder(mode, 250.0, 4, seed=1)
    layer = StreamingTrustLayer(load_config(), decode_fn=build_decoder(), streaming=StreamingConfig(max_attempts=1))
    src = LSLEventSource(sig, mk, LSLMapping(merge_window_s=1e9), signal_decoder=dec, clock=Clock(1e6))
    got: list = []
    runner = LSLTrustRunner(layer, src, sink=got.append)
    for _ in range(10_000):
        runner.step(0.0)
        if not sig.script and not mk.script:
            break
    runner.finish()
    finals = [e for e in got if e["is_final"]]
    assert len(finals) >= 4
    assert all(e["action"] != "COMMIT" for e in finals)
    h = src.header()
    assert h["meta"]["decoder.toy"] is True and h["lsl"]["stream"]["type"] == "EEG"
    assert src.stats.gaps == 1 and sum(e["lsl"]["utterance"]["gaps"] for e in finals) == 1


def test_open_source_accepts_a_decoder_factory(monkeypatch):
    calls = []

    def factory(info):
        calls.append(info.nominal_srate)
        return ToySignalDecoder(info.nominal_srate, info.channel_count)

    info = LSLStreamInfo("x", "EEG", 2, 250.0, "float32", "sid")

    class FakePl:
        local_clock = staticmethod(time.perf_counter)

    monkeypatch.setattr(L, "require_pylsl", lambda: FakePl)
    monkeypatch.setattr(L, "resolve", lambda *a, **k: info)
    monkeypatch.setattr(L, "PylslInlet", lambda si: ScriptedInlet(si))
    src = L.open_source("x", events="none", signal_decoder=factory)
    assert calls == [250.0] and isinstance(src.signal_decoder, ToySignalDecoder)


def test_cli_has_bridge_and_signal_decoder(capsys):
    with pytest.raises(SystemExit):
        L.main(["brainflow-bridge", "--help"])
    assert "--trial-s" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        L.main(["run", "--help"])
    assert "toy-features" in capsys.readouterr().out


# --- live integration (needs brainflow and pylsl) ---------------------------

live = pytest.mark.skipif(not (B.brainflow_available() and L.pylsl_available()),
                          reason="brainflow and pylsl not available")


@live
def test_live_synthetic_board_through_lsl():
    from fidetype.demo import build_decoder, load_config

    name = f"fidetype-test-bf-{uuid.uuid4().hex[:8]}"
    board, descr = B.open_board(B.SYNTHETIC_BOARD_ID)
    br = B.BrainFlowBridge(board, descr, B.SYNTHETIC_BOARD_ID,
                           B.BridgeConfig(name=name, source_id=name, trial_s=1.5))
    stop = threading.Event()
    th = threading.Thread(target=br.run, kwargs={"stop": stop}, daemon=True)
    th.start()
    try:
        src = L.open_source(name, events="auto", timeout=10.0,
                            signal_decoder=lambda info: toy_signal_decoder("flat", info.nominal_srate,
                                                                           info.channel_count))
        layer = StreamingTrustLayer(load_config(), decode_fn=build_decoder(),
                                    streaming=StreamingConfig(max_attempts=1))
        got: list = []
        runner = LSLTrustRunner(layer, src, sink=got.append)
        s = runner.run(duration_s=8.0, until_end=False)
        src.close()
    finally:
        stop.set()
        th.join(5)
    finals = [e for e in got if e["is_final"]]
    assert s.final_decisions >= 3 and all(e["action"] != "COMMIT" for e in finals)
    assert s.source["gaps"] == 0 and s.source["samples"] > 1000
    assert src.header()["lsl"]["stream"]["channel_count"] == 16
    assert s.e2e_latency_ms["p50"] < 500
