"""M6-14: the LSL reconnect runs off the trust loop.

The M6-13 soak test found that a reconnect blocked the loop for up to
6.1 s (the resolve ran inside ``poll()``). Now a worker thread resolves
and opens the new inlet. These tests use fake inlets and a fake
resolver that sleeps (no pylsl needed). The real-LSL loopback check
runs only when pylsl / liblsl is available.
"""

from __future__ import annotations

import json
import threading
import time
import uuid

import numpy as np
import pytest

from fidetype.adapters import lsl as L
from fidetype.adapters.lsl import LSLEventSource, LSLMapping, LSLStreamInfo, LSLStreamLost, LSLTrustRunner
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer
from fidetype.trust.testing import RefCharLM, greedy_nbest

CFG = FrozenTrustConfig(name="lsl-reconnect-test").with_policy(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)
SRATE = 25.0
VOCAB = ["<b>", "a", "b"]
#: The loop's stall bound while a reconnect is in progress (task M6-14).
MAX_STALL_S = 0.050


class FakeInlet:
    """Scripted inlet: items are ``(samples, stamps)`` chunks or ``"lost"``."""

    def __init__(self, info, script=()):
        self._info = info
        self.script = list(script)
        self.closed = False

    def info(self):
        return self._info

    def pull_chunk(self, timeout, max_samples):
        if not self.script:
            return [], []
        it = self.script.pop(0)
        if it == "lost":
            raise LSLStreamLost("fake loss")
        return it

    def time_correction(self, timeout):
        return 0.0

    def close(self):
        self.closed = True


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        self.t += 0.001
        return self.t


def _info():
    h = {"spec_version": "0.1", "vocab": VOCAB, "vocab_type": "char", "blank_id": 0, "source": "x",
         "frame_period": 1 / SRATE, "meta": {}}
    return LSLStreamInfo("f", "NTS", 3, SRATE, "float32", "f1", "u", "hostA", channel_labels=VOCAB,
                         fidetype={"nts_header": json.dumps(h)})


def _rows(text: str) -> list[list[float]]:
    """CTC-like frames for ``text`` over {blank, a, b}: blank, char, blank, ..."""
    out = []
    for ch in text:
        for k in (0, VOCAB.index(ch), 0):
            p = np.full(3, 0.05)
            p[k] = 0.9
            out.append(list(np.log(p / p.sum())))
    return out


def _chunks(rows, t0, chunk=4):
    ts = [t0 + i / SRATE for i in range(len(rows))]
    return [(rows[i:i + chunk], ts[i:i + chunk]) for i in range(0, len(rows), chunk)], ts[-1] + 1 / SRATE


def _events_info():
    return LSLStreamInfo("e", "Markers", 1, 0.0, "string", "e1", "u2", "hostA")


def _marker(ev, t):
    return ([json.dumps(ev)], [t])


def _scenario():
    """Utterance 1 complete, utterance 2 cut by a loss; after the restart utterances 3 and 4.

    Returns (primary, events, fresh, fresh_events_items). Boundaries come
    on the events inlet; the items for after the restart are appended
    to the events inlet only when the fresh primary is attached.
    """
    p1, t = _chunks(_rows("ab"), 100.0)
    p2, t2 = _chunks(_rows("ba"), t + 0.2)
    primary = FakeInlet(_info(), [*p1, *p2[:2], "lost"])
    ev = FakeInlet(_events_info(), [_marker({"type": "segment_end"}, t + 0.1)])
    f3, t3 = _chunks(_rows("aab"), 200.0)
    f4, t4 = _chunks(_rows("b"), t3 + 0.2)
    fresh = FakeInlet(_info(), [*f3, *f4])
    after = [_marker({"type": "segment_end"}, t3 + 0.1), _marker({"type": "segment_end"}, t4 + 0.1),
             _marker({"type": "end"}, t4 + 0.2)]
    return primary, ev, fresh, after


def _run(mode: str, resolve_delay_s: float, poll_timeout: float = 0.01, max_wall_s: float = 20.0):
    primary, ev, fresh, after = _scenario()

    def reopen():
        time.sleep(resolve_delay_s)  # the slow resolve + open
        return fresh

    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=1))
    src = LSLEventSource(primary, ev, LSLMapping(merge_window_s=1e9, reconnect_mode=mode), clock=Clock(),
                         reopen_primary=reopen)
    out: list[dict] = []
    runner = LSLTrustRunner(layer, src, sink=out.append, keep=True)
    stalls: list[float] = []
    reconnecting_stalls: list[float] = []
    appended = False
    t_end = time.monotonic() + max_wall_s
    while not runner.summary.ended and time.monotonic() < t_end:
        lost = src.primary.lost_since is not None
        t0 = time.perf_counter()
        runner.step(poll_timeout)
        dt = time.perf_counter() - t0
        stalls.append(dt)
        if lost:
            reconnecting_stalls.append(dt)
        if not appended and src.stats.reconnects:
            ev.script.extend(after)
            appended = True
        elif appended and not ev.script and not fresh.script:
            break  # all delivered; the merge holds the tail until the drain
    runner.finish()
    src.close()
    return runner, out, src, stalls, reconnecting_stalls


def _view(out):
    return [(e["seq"], e["is_final"], e["action"], e.get("shown"), tuple(e["input"]["frame_range"])) for e in out]


# --- the stall ---------------------------------------------------------------------------


def test_slow_resolve_does_not_stall_the_loop():
    runner, out, src, stalls, rc = _run("thread", resolve_delay_s=1.0)
    assert runner.summary.ended and src.stats.lost == 1 and src.stats.reconnects == 1
    assert len(rc) >= 20  # the loop kept stepping while the worker slept
    assert max(rc) < MAX_STALL_S, f"max stall while reconnecting {max(rc) * 1e3:.1f} ms"
    assert max(stalls) < MAX_STALL_S


def test_inline_mode_still_blocks():
    """The old path (kept for the conformance profile) blocks for the whole resolve."""
    runner, out, src, stalls, rc = _run("inline", resolve_delay_s=0.3)
    assert runner.summary.ended and src.stats.reconnects == 1
    assert max(rc) >= 0.29


# --- the semantics -----------------------------------------------------------------------


@pytest.mark.parametrize("delay", [0.0, 0.2])
def test_restart_mid_utterance_same_decisions_as_inline(delay):
    ref_runner, ref, *_ = _run("inline", resolve_delay_s=0.0)
    runner, out, src, *_ = _run("thread", resolve_delay_s=delay)
    assert _view(out) == _view(ref)
    assert [e["seq"] for e in out] == list(range(len(out)))  # no hole, no duplicate
    assert runner.summary.aborted_utterances == ref_runner.summary.aborted_utterances == 1
    finals = [e for e in out if e["is_final"]]
    assert len(finals) == 3  # utterances 1, 3, 4; the cut utterance 2 gives no decision
    # No final decision covers frames of the cut utterance (frames 6..13 before the loss).
    assert all(e["lsl"]["reconnects"] == (0 if i == 0 else 1) for i, e in enumerate(finals))


def test_other_inlet_is_served_while_reconnecting():
    """Markers of the events inlet still come out while the primary is away."""
    p, _ = _chunks(_rows("a"), 100.0)
    primary = FakeInlet(_info(), [*p, "lost"])
    ev = FakeInlet(_events_info(), [])
    gate = threading.Event()

    def reopen():
        gate.wait(5.0)
        raise RuntimeError("not there yet")

    src = LSLEventSource(primary, ev, LSLMapping(merge_window_s=1e9, reconnect_timeout_s=30.0), clock=Clock(),
                         reopen_primary=reopen)
    got = []
    for _ in range(5):
        got += src.poll(0.01)
    assert any(e.get("status") == "lost" for e in got)
    ev.script.append(_marker({"type": "segment_end", "note": "x"}, 300.0))
    seen = []
    for _ in range(5):
        t0 = time.perf_counter()
        seen += src.poll(0.01)
        assert time.perf_counter() - t0 < MAX_STALL_S
    assert any(e.get("type") == "segment_end" for e in seen)
    gate.set()
    src.close()


def test_stop_signal_is_seen_while_reconnecting():
    p, _ = _chunks(_rows("ab"), 100.0)
    primary = FakeInlet(_info(), [*p[:2], "lost"])
    gate = threading.Event()

    def reopen():
        gate.wait(10.0)  # a resolve that does not come back soon
        raise RuntimeError("gone")

    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest)
    src = LSLEventSource(primary, mapping=LSLMapping(reconnect_timeout_s=60.0), clock=Clock(), reopen_primary=reopen)
    runner = LSLTrustRunner(layer, src)
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()
    t0 = time.monotonic()
    s = runner.run(stop=stop, poll_timeout=0.02)
    assert s.stop_reason == "stopped" and time.monotonic() - t0 < 0.3 + 0.2
    assert s.aborted_utterances == 1 and s.final_decisions == 0  # the cut utterance gives no decision
    src.close()
    gate.set()


def test_reconnect_timeout_still_raises_and_cancels_the_worker():
    p, _ = _chunks(_rows("a"), 100.0)
    primary = FakeInlet(_info(), [*p, "lost"])
    calls = {"n": 0}

    def reopen():
        calls["n"] += 1
        time.sleep(0.01)
        raise RuntimeError("not visible")

    src = LSLEventSource(primary, mapping=LSLMapping(reconnect_timeout_s=0.2, reconnect_interval_s=0.0),
                         clock=time.perf_counter, reopen_primary=reopen)
    t0 = time.monotonic()
    with pytest.raises(LSLStreamLost, match="within 0.2 s"):
        for _ in range(10000):
            t1 = time.perf_counter()
            src.poll(0.01)
            assert time.perf_counter() - t1 < MAX_STALL_S
    assert time.monotonic() - t0 < 1.0 and calls["n"] >= 2
    assert src.primary.reconnector is None


def test_late_inlet_after_close_is_closed():
    p, _ = _chunks(_rows("a"), 100.0)
    primary = FakeInlet(_info(), [*p, "lost"])
    fresh = FakeInlet(_info(), [])
    gate = threading.Event()

    def reopen():
        gate.wait(5.0)
        return fresh

    src = LSLEventSource(primary, mapping=LSLMapping(), clock=Clock(), reopen_primary=reopen)
    for _ in range(3):
        src.poll(0.0)
    worker = src.primary.reconnector
    assert worker is not None and not worker.done()
    src.close()
    gate.set()
    worker.thread.join(2.0)
    assert worker.done() and fresh.closed


def test_mapping_rejects_bad_reconnect_mode():
    with pytest.raises(ValueError):
        LSLMapping(reconnect_mode="async")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        LSLMapping(reconnect_handoff_s=-1.0)


# --- the demo decoder's LM memo is bounded -------------------------------------------------


def test_refcharlm_memo_is_bounded_and_values_do_not_change():
    texts = ["the quick brown fox", "jumps over the lazy dog", "a b c d e f g"]
    big = RefCharLM(5, cache_size=None).fit(texts)
    small = RefCharLM(5, cache_size=16).fit(texts)
    rng = np.random.default_rng(0)
    letters = "abcdefghijklmnopqrstuvwxyz "
    for _ in range(300):
        s = "".join(rng.choice(list(letters), size=int(rng.integers(1, 12))))
        assert small.score_sentence(s) == big.score_sentence(s)
    assert len(small._cache) <= 16 and len(big._cache) > 16
    assert RefCharLM(5)._cache.maxsize == RefCharLM.CACHE_SIZE


# --- real LSL loopback (optional) ------------------------------------------------------------

lsl_only = pytest.mark.skipif(not L.pylsl_available(), reason="pylsl / liblsl not available")


@lsl_only
def test_real_lsl_producer_restart_does_not_stall_the_loop():
    """A real outlet goes away and comes back (same source_id) while the loop polls."""
    pl = L.require_pylsl()
    name = f"fidetype-rc-{uuid.uuid4().hex[:8]}"
    sid = f"{name}-sid"
    h = {"spec_version": "0.1", "vocab": VOCAB, "vocab_type": "char", "blank_id": 0, "source": "x",
         "frame_period": 1 / SRATE, "meta": {}}

    def make_outlet():
        info = pl.StreamInfo(name, "NTS", 3, SRATE, "float32", sid)
        d = info.desc().append_child("fidetype")
        d.append_child_value("nts_header", json.dumps(h))
        d.append_child_value("values", "log_probs")
        d.append_child_value("binding", L.BINDING_VERSION)
        ch = info.desc().append_child("channels")
        for v in VOCAB:
            c = ch.append_child("channel")
            c.append_child_value("label", v)
            c.append_child_value("unit", "log_prob")
        return pl.StreamOutlet(info)

    row = list(np.log([0.9, 0.05, 0.05]))
    state = {"outlet": make_outlet(), "run": True}
    lock = threading.Lock()

    def produce():
        while state["run"]:
            with lock:
                o = state["outlet"]
                if o is not None:
                    o.push_sample(row)
            time.sleep(1 / SRATE)

    th = threading.Thread(target=produce, daemon=True)
    th.start()
    src = L.open_source(name=name, timeout=10.0, events="none",
                        mapping=LSLMapping(merge_window_s=0.05, reconnect_timeout_s=20.0))
    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest)
    runner = LSLTrustRunner(layer, src)
    stalls = []
    t_end = time.monotonic() + 25.0
    killed_at = None
    try:
        while time.monotonic() < t_end:
            t0 = time.perf_counter()
            runner.step(0.02)
            dt = time.perf_counter() - t0
            if killed_at is not None and src.stats.reconnects == 0:
                stalls.append(dt)
            if killed_at is None and src.stats.frames > 25:
                with lock:
                    state["outlet"] = None  # the producer stops (outlet destroyed)
                killed_at = time.monotonic()
                threading.Timer(1.5, lambda: state.__setitem__("outlet", make_outlet())).start()
            if src.stats.reconnects and src.stats.frames > 60:
                break
    finally:
        state["run"] = False
        src.close()
    assert src.stats.lost >= 1 and src.stats.reconnects >= 1
    assert stalls and max(stalls) < 0.25, f"max stall {max(stalls) * 1e3:.1f} ms"
