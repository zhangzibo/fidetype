"""M6-16: the LSL inlet ``open_timeout`` and the fast reconnect (``reconnect_resolver = "continuous"``).

Unit tests use fake pylsl objects (no network). The real-LSL test is skipped when pylsl / liblsl is
not available; its stream names start with ``test-collector-m616-`` and a random id.
"""

from __future__ import annotations

import json
import threading
import time
import types
import uuid

import numpy as np
import pytest

from fidetype.adapters import lsl as L
from fidetype.adapters.lsl import LSLMapping, LSLResolveError

lsl_only = pytest.mark.skipif(not L.pylsl_available(), reason="pylsl / liblsl not available")


def test_default_and_validation():
    assert L.DEFAULT_OPEN_TIMEOUT_S == 1.0 and LSLMapping().open_timeout_s == 1.0
    assert LSLMapping().reconnect_resolver == "continuous" and LSLMapping().reconnect_mode == "thread"
    with pytest.raises(ValueError, match="open_timeout_s"):
        LSLMapping(open_timeout_s=0)
    with pytest.raises(ValueError, match="reconnect_resolver"):
        LSLMapping(reconnect_resolver="fast")
    assert L.PylslInlet.__init__.__defaults__[0] == L.DEFAULT_OPEN_TIMEOUT_S


def test_open_first_retries_a_timed_out_open():
    calls = {"find": 0, "open": 0}

    def find(left):
        calls["find"] += 1
        return f"info{calls['find']}"

    def opener(info, ot):
        calls["open"] += 1
        assert ot == 0.2
        if calls["open"] < 3:
            raise TimeoutError("stale info")
        return ("inlet", info)

    assert L._open_first(find, 0.2, 5.0, opener=opener) == ("inlet", "info3")

    def always(info, ot):
        raise TimeoutError("no answer")

    t0 = time.monotonic()
    with pytest.raises(LSLResolveError, match="did not open within 0.2 s"):
        L._open_first(find, 0.2, 0.3, opener=always)
    assert time.monotonic() - t0 < 2.0


class _Info:
    def __init__(self, uid):
        self._uid = uid

    def uid(self):
        return self._uid

    def name(self):
        return "n"

    def source_id(self):
        return "sid"


class _FakeInlet:
    def __init__(self, info, open_timeout=None):
        self.opened = info
        self.open_timeout = open_timeout

    def info(self):
        return types.SimpleNamespace(uid=self.opened.uid())


def _fake_pylsl(monkeypatch, results):
    """``results``: a callable (call number) -> list of uids the continuous resolver sees."""
    made = []

    class CR:
        def __init__(self, pred, forget_after):
            self.pred, self.forget_after, self.n = pred, forget_after, 0
            made.append(self)

        def results(self):
            self.n += 1
            return [_Info(u) for u in results(self.n)]

    monkeypatch.setattr(L, "require_pylsl", lambda: types.SimpleNamespace(ContinuousResolver=CR))
    monkeypatch.setattr(L, "PylslInlet", _FakeInlet)
    return made


def test_reopener_prefers_a_new_outlet_over_stale_info(monkeypatch):
    made = _fake_pylsl(monkeypatch, lambda n: ["old"] if n < 4 else ["old", "new"])
    r = L._Reopener({"source_id": "sid", "name": None}, "old", LSLMapping(open_timeout_s=0.3, reconnect_interval_s=1.0))
    inlet = r()
    assert inlet.opened.uid() == "new" and inlet.open_timeout == 0.3
    assert made[0].pred == "source_id='sid'" and made[0].forget_after == L._Reopener.FORGET_AFTER_S
    assert r.uid == "new" and r._cr is None  # a fresh resolver for the next loss


def test_reopener_takes_the_old_uid_after_a_while_and_times_out(monkeypatch):
    _fake_pylsl(monkeypatch, lambda n: ["old"])
    monkeypatch.setattr(L._Reopener, "SAME_UID_AFTER_S", 0.1)
    r = L._Reopener({"source_id": "sid"}, "old", LSLMapping(reconnect_interval_s=0.03))
    with pytest.raises(LSLResolveError, match="no new LSL stream"):
        r()  # the first try is too early for the old uid
    time.sleep(0.12)
    assert r().opened.uid() == "old"  # the same outlet is still there (a network break)

    _fake_pylsl(monkeypatch, lambda n: [])
    r = L._Reopener({"source_id": "sid"}, "old", LSLMapping(reconnect_interval_s=0.05))
    t0 = time.monotonic()
    with pytest.raises(LSLResolveError):
        r()
    assert time.monotonic() - t0 < 0.5  # one try is bounded by reconnect_interval_s

    _fake_pylsl(monkeypatch, lambda n: ["a", "b"])
    with pytest.raises(LSLResolveError, match="2 LSL streams match"):
        L._Reopener({"source_id": "sid"}, "old", LSLMapping())()


def test_reopener_oneshot_uses_resolve(monkeypatch):
    _fake_pylsl(monkeypatch, lambda n: pytest.fail("the continuous resolver must not run"))
    seen = {}

    def fake_resolve(name=None, type=None, source_id=None, timeout=10.0):
        seen.update(source_id=source_id, timeout=timeout)
        return _Info("x")

    monkeypatch.setattr(L, "resolve", fake_resolve)
    r = L._Reopener({"source_id": "sid"}, "old", LSLMapping(reconnect_resolver="oneshot", reconnect_interval_s=0.4))
    assert r().opened.uid() == "x" and seen == {"source_id": "sid", "timeout": 0.4}


@lsl_only
def test_real_lsl_restart_reconnects_fast():
    """A real outlet goes away for 1.5 s and comes back (same source_id). M6-16: about 2.4 s, was about 6.2 s."""
    from fidetype.adapters.lsl import LSLTrustRunner
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.streaming import StreamingTrustLayer
    from fidetype.trust.testing import greedy_nbest

    pl = L.require_pylsl()
    vocab, srate = ["<b>", "a", "b"], 25.0
    name = f"test-collector-m616-{uuid.uuid4().hex[:8]}"
    sid = f"{name}-sid"
    h = {"spec_version": "0.1", "vocab": vocab, "vocab_type": "char", "blank_id": 0, "source": "x",
         "frame_period": 1 / srate, "meta": {}}

    def make_outlet():
        info = pl.StreamInfo(name, "NTS", 3, srate, "float32", sid)
        d = info.desc().append_child("fidetype")
        d.append_child_value("nts_header", json.dumps(h))
        d.append_child_value("binding", L.BINDING_VERSION)
        return pl.StreamOutlet(info)

    row = list(np.log([0.9, 0.05, 0.05]))
    state = {"outlet": make_outlet(), "run": True}
    lock = threading.Lock()

    def produce():
        while state["run"]:
            with lock:
                if state["outlet"] is not None:
                    state["outlet"].push_sample(row)
            time.sleep(1 / srate)

    threading.Thread(target=produce, daemon=True).start()
    src = L.open_source(name=name, timeout=10.0, events="none", mapping=LSLMapping(reconnect_timeout_s=20.0))
    cfg = FrozenTrustConfig(name="m6-16").with_policy(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)
    runner = LSLTrustRunner(StreamingTrustLayer(cfg, decode_fn=greedy_nbest), src)
    killed_at = rec_after = None
    steps = []
    t_end = time.monotonic() + 20.0
    try:
        while time.monotonic() < t_end:
            t0 = time.perf_counter()
            runner.step(0.02)
            if killed_at is not None and rec_after is None:
                steps.append(time.perf_counter() - t0)
            if killed_at is None and src.stats.frames > 25:
                with lock:
                    state["outlet"] = None
                killed_at = time.monotonic()
                threading.Timer(1.5, lambda: state.__setitem__("outlet", make_outlet())).start()
            if killed_at is not None and rec_after is None and src.stats.reconnects:
                rec_after = time.monotonic() - killed_at
                break
    finally:
        state["run"] = False
        src.close()
    assert rec_after is not None and rec_after < 4.5, rec_after  # the one-shot path took about 6.2 s
    assert max(steps) < 0.25 and runner.summary.aborted_utterances <= 1  # M6-14 holds
