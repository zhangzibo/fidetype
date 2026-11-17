"""P3: the collector's LSL receiver and LSL decisions exporter (FEP-0006 sections 2 and 4, spec 8.2).

Unit tests use the scripted LSL inlets of ``fidetype.adapters.lsl`` (no network, no pylsl). The
loopback test (outlet -> collector -> decisions outlet -> inlet) runs real LSL on this machine and
is skipped when pylsl / liblsl is not available. Its stream names start with ``test-collector-``
and a random id, so they never meet other LSL streams on the machine. Synthetic data only.
"""

from __future__ import annotations

import json
import math
import socket
import threading
import time
import uuid

import pytest

from fidetype.adapters import lsl as L
from fidetype.adapters.lsl import LSLEventSource, LSLMapping, LSLStreamInfo, ScriptedInlet
from fidetype.collector import Collector, ConfigError, parse
from fidetype.collector import exporters as E
from fidetype.collector import processors as P
from fidetype.collector import receivers as R
from fidetype.collector.service import Pipeline
from fidetype.trust.frozen import FrozenTrustConfig

CFG = FrozenTrustConfig(name="collector-lsl-test").with_policy(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)
VOCAB = ["<blank>", "a", "b"]
HDR = {"spec_version": "0.1", "vocab": VOCAB, "vocab_type": "char", "blank_id": 0, "source": "t",
       "frame_period": 0.04, "meta": {"data.derived": True}}
ROW_A = [math.log(0.05), math.log(0.9), math.log(0.05)]  # greedy decodes "a"
lsl_only = pytest.mark.skipif(not L.pylsl_available(), reason="pylsl / liblsl not available")


class Clock:
    """A fake clock that moves 1 s per call, so the merge window always passes."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def _frames_info(uid="u1") -> LSLStreamInfo:
    return LSLStreamInfo("f", "NTS", 3, 25.0, "float32", "fsid", uid, "hostA", channel_labels=VOCAB,
                         fidetype={"nts_header": json.dumps(HDR), "binding": L.BINDING_VERSION})


def _events_info() -> LSLStreamInfo:
    return LSLStreamInfo("f.events", "Markers", 1, 0.0, "string", "esid", "ue", "hostA",
                         fidetype={"binding": L.BINDING_VERSION, "event_clock": "lsl"})


def _chunk(t0: float, n: int, step: float = 0.04):
    return [ROW_A] * n, [round(t0 + i * step, 6) for i in range(n)]


def _marks(*pairs):
    return [[json.dumps(e)] for e, _ in pairs], [t for _, t in pairs]


EMPTY = ([], [])
SEG = {"type": "segment_end"}
END = {"type": "end"}


class Capture(E.Exporter):
    type = "capture"

    def __init__(self) -> None:
        super().__init__("cap", lambda m: None)
        self.items: list = []

    def export(self, items):
        self.items += items


def _pipeline(tmp_path, source_factory, stop_at_end=True, stream_id=None):
    CFG.save(tmp_path / "trust.json")
    logs: list[str] = []
    rec = R.LSLReceiver("live", logs.append, source_factory, stream_id=stream_id, stop_at_end=stop_at_end)
    trust = P.TrustProcessor("trust", logs.append, tmp_path / "trust.json", decoder="greedy", max_attempts=1)
    cap = Capture()
    pl = Pipeline("main", [rec], [P.ValidateProcessor("check", logs.append), trust], [cap])
    rec.start()
    return pl, rec, trust, cap, logs


def _run(pl, steps=50):
    for _ in range(steps):
        if pl.done:
            break
        pl.step(0.0)
    pl.finish()


def _finals(cap):
    return [ev for _, ev in cap.items if ev.get("type") == "trust_decision" and ev.get("is_final")]


# --- receiver: loss, reconnect, gaps ----------------------------------------------------------


def test_loss_mid_utterance_gives_no_final_and_reconnect_goes_on(tmp_path):
    frames = ScriptedInlet(_frames_info(), [_chunk(10.0, 5), _chunk(11.0, 3), "lost"])
    events = ScriptedInlet(_events_info(), [_marks((SEG, 10.17)), EMPTY, EMPTY, EMPTY])
    fresh = ScriptedInlet(_frames_info("u2"), [_chunk(20.0, 5)])
    events.script += [EMPTY, _marks((SEG, 20.17), (END, 20.18))]

    def factory():
        return LSLEventSource(frames, events, LSLMapping(reconnect_mode="inline", on_gap="abort"),
                              reopen_primary=lambda: fresh, clock=Clock())

    pl, rec, trust, cap, logs = _pipeline(tmp_path, factory)
    _run(pl)
    fin = _finals(cap)
    assert len(fin) == 2, fin  # utterance 0 and the one after the reconnect; the cut one has none
    assert all(d["session"] == "live-0" and d["shown"] == ["a"] for d in fin)
    st = rec.stats()
    assert st["lost_streams"] == 1 and st["reconnects"] == 1 and st["headers"] == 2 and st["done"]
    # the jump 10.16 -> 11.00 follows a segment_end: it cuts no utterance
    assert st["gaps_between_utterances"] == 1 and st["gaps"] == 0
    assert trust.stats()["aborted_utterances"] == 1
    assert not any(ev.get("type") == R.STATUS for _, ev in cap.items)  # status items never leave
    assert "hostA" not in json.dumps(st) and "hostA" not in json.dumps([ev for _, ev in cap.items])


class StepClock:
    """A fake source clock that moves ``step`` seconds per call (the merge window passes after a few polls)."""

    def __init__(self, step: float) -> None:
        self.t, self.step = 1000.0, step

    def __call__(self) -> float:
        self.t += self.step
        return self.t


def test_receive_stamp_counts_the_merge_window_wait(tmp_path):
    """P3-07: events carry the pull time; ``receive`` and ``added`` include the inlet merge-window wait."""
    from fidetype.collector.latency import LatencyRecorder

    frames = ScriptedInlet(_frames_info(), [_chunk(10.0, 5)])
    events = ScriptedInlet(_events_info(), [EMPTY, EMPTY, EMPTY, _marks((SEG, 10.17), (END, 10.18))])

    def factory():
        return LSLEventSource(frames, events, LSLMapping(reconnect_mode="inline", merge_window_s=0.05),
                              clock=StepClock(0.01))

    pl, rec, trust, cap, logs = _pipeline(tmp_path, factory)
    pl.latency = LatencyRecorder()
    _run(pl)
    assert len(_finals(cap)) == 1
    s = pl.latency.summary()["stages"]
    # the segment_end waits in the merge until its time passes: the receive stage sees that wait
    assert s["receive"]["n"] >= 1 and s["receive"]["max"] >= 1.0 and s["added"]["max"] >= s["receive"]["max"]


@pytest.mark.parametrize("on_gap", ["abort", "mark"])
def test_gap_inside_an_utterance(tmp_path, on_gap):
    rows = [ROW_A] * 6
    stamps = [10.0, 10.04, 10.08, 10.40, 10.44, 10.48]  # a gap of 8 periods inside the utterance
    frames = ScriptedInlet(_frames_info(), [(rows, stamps), _chunk(11.0, 3)])
    events = ScriptedInlet(_events_info(), [_marks((SEG, 10.49)), _marks((SEG, 11.09), (END, 11.10))])

    def factory():
        return LSLEventSource(frames, events, LSLMapping(on_gap=on_gap), clock=Clock())

    pl, rec, trust, cap, _ = _pipeline(tmp_path, factory)
    _run(pl)
    fin = _finals(cap)
    st = rec.stats()
    if on_gap == "abort":
        assert len(fin) == 1 and st["gaps"] == 1  # only the utterance after the gap
        assert fin[0]["input"]["t_range"][0] >= 11.0
        assert trust.stats()["aborted_utterances"] == 1 and trust.stats()["skipped_after_gap"] == 3
    else:
        assert len(fin) == 2 and st["gaps_marked"] == 1 and st["gaps"] == 0
    assert not any(ev.get("type") == L.GAP for _, ev in cap.items)


def test_shutdown_inside_an_utterance_and_give_up(tmp_path):
    # Shutdown: the open utterance gets no decision.
    frames = ScriptedInlet(_frames_info(), [_chunk(10.0, 5)])
    pl, rec, trust, cap, _ = _pipeline(tmp_path, lambda: LSLEventSource(frames, None, LSLMapping(), clock=Clock()))
    for _ in range(3):
        pl.step(0.0)
    pl.finish()
    assert _finals(cap) == [] and trust.stats()["aborted_utterances"] == 1

    # No reopen: the source gives up at once; the receiver is done, no decision on the cut utterance.
    frames = ScriptedInlet(_frames_info(), [_chunk(10.0, 5), "lost"])
    pl, rec, trust, cap, logs = _pipeline(tmp_path, lambda: LSLEventSource(frames, None, LSLMapping(), clock=Clock()))
    _run(pl)
    assert rec.done and _finals(cap) == [] and rec.stats()["lost_streams"] == 1
    assert any("not reconnected" in m for m in logs)


def test_stop_at_end_false_keeps_reading_and_stream_id(tmp_path):
    frames = ScriptedInlet(_frames_info(), [_chunk(10.0, 3), EMPTY, _chunk(20.0, 3)])
    head2 = {"type": "header", **HDR}
    events = ScriptedInlet(_events_info(), [_marks((SEG, 10.09), (END, 10.10)), _marks((head2, 19.0)),
                                            _marks((SEG, 20.09), (END, 20.10))])
    pl, rec, trust, cap, _ = _pipeline(
        tmp_path, lambda: LSLEventSource(frames, events, LSLMapping(), clock=Clock()), stop_at_end=False,
        stream_id="dev-1")
    for _ in range(6):
        pl.step(0.0)
    assert not rec.done and rec.stats()["ended_streams"] == 2
    fin = _finals(cap)
    assert len(fin) == 2 and {d["session"] for d in fin} == {"dev-1"}


# --- exporter -----------------------------------------------------------------------------------


class FakeOutlet:
    instances: list["FakeOutlet"] = []

    def __init__(self, name, source_id=None, config_id=None):
        self.name, self.source_id, self.config_id = name, source_id, config_id
        self.pushed: list = []
        FakeOutlet.instances.append(self)

    def push(self, ev):
        self.pushed.append(ev)


@pytest.mark.parametrize("no_text", [False, True])
def test_lsl_exporter_decisions_only_and_no_text(no_text):
    logs: list[str] = []
    ex = E.LSLExporter("dec", logs.append, stream_name="test-collector-x", config_id="tcfg-1", no_text=no_text,
                       outlet_factory=FakeOutlet)
    ex.start()
    o = FakeOutlet.instances[-1]
    assert (o.name, o.config_id) == ("test-collector-x", "tcfg-1")
    d = {"type": "trust_decision", "spec_version": "1.0", "seq": 0, "is_final": True, "action": "COMMIT",
         "shown": ["hello"]}
    items = [("s", {"type": R.STATUS, "status": "gap", "stream": "s"}), ("s", {"type": "frame", "t": 0.0}),
             ("s", d), ("s", {**d, "seq": 1, "is_final": False})]
    ex.export(items)
    assert len(o.pushed) == 2 and all(e["type"] == "trust_decision" for e in o.pushed)
    if no_text:
        assert all("shown" not in e and e["redaction"] == {"mode": "drop"} for e in o.pushed)
        assert "hello" not in json.dumps(o.pushed) and not any("WARNING" in m for m in logs)
        assert d["shown"] == ["hello"]  # the item itself is not changed
    else:
        assert o.pushed[0] == d and any("SEC-7" in m for m in logs)
    assert ex.stats() == {"type": "lsl", "exported": 2, "text_removed": 2 if no_text else 0, "no_text": no_text}


# --- configuration ----------------------------------------------------------------------------


def _lsl_config(receiver=None, exporter=None):
    return {
        "service": {"log": "quiet"},
        "receivers": {"live": receiver or {"type": "lsl", "stream_name": "test-collector-cfg"}},
        "processors": {"trust": {"type": "trust", "config": "trust.json", "decoder": "greedy"}},
        "exporters": {"dec": exporter or {"type": "lsl", "stream_name": "test-collector-cfg-dec", "no_text": True}},
        "pipelines": {"main": {"receivers": ["live"], "processors": ["trust"], "exporters": ["dec"]}},
    }


@pytest.mark.parametrize("rec, msg", [
    ({"type": "lsl"}, "give at least one of stream_name"),
    ({"type": "lsl", "stream_name": "x", "on_gap": "skip"}, "receivers.live.on_gap"),
    ({"type": "lsl", "stream_name": "x", "open_timeout_s": 0}, "receivers.live.open_timeout_s: must be > 0"),
    ({"type": "lsl", "stream_name": "x", "reconnect_mode": "fast"}, "receivers.live.reconnect_mode"),
    ({"type": "lsl", "stream_name": "x'y"}, "without a single quote"),
    ({"type": "lsl", "stream_name": "x", "host": "pc1"}, "unknown key 'host'"),
    ({"type": "lsl", "stream_name": "x", "gap_factor": 1.0}, "gap_factor: must be > 1"),
])
def test_lsl_receiver_config_errors(rec, msg):
    with pytest.raises(ConfigError, match=msg):
        parse(_lsl_config(receiver=rec))


def test_lsl_exporter_config_errors():
    with pytest.raises(ConfigError, match="exporters.dec.no_text"):
        parse(_lsl_config(exporter={"type": "lsl", "no_text": "yes"}))
    with pytest.raises(ConfigError, match="unknown key 'hostname'"):
        parse(_lsl_config(exporter={"type": "lsl", "hostname": "pc1"}))


def test_service_builds_lsl_parts_and_takes_config_id(tmp_path, monkeypatch):
    CFG.save(tmp_path / "trust.json")
    monkeypatch.setattr(L, "pylsl_available", lambda: True)
    col = Collector(parse(_lsl_config(receiver={"type": "lsl", "source_id": "sid-1", "on_gap": "mark",
                                                "open_timeout_s": 0.5, "stream_id": "dev-1"}),
                          base_dir=tmp_path))
    ex = col._exporters["dec"]
    trust = col.pipelines[0].processors[0]
    assert isinstance(ex, E.LSLExporter) and ex.no_text and ex.config_id == trust.config_id  # LSL-X1
    rec = col.receiver("live")
    assert isinstance(rec, R.LSLReceiver) and rec.sid == "dev-1"
    monkeypatch.setattr(L, "pylsl_available", lambda: False)
    with pytest.raises(ConfigError, match="needs pylsl"):
        Collector(parse(_lsl_config(), base_dir=tmp_path))


# --- real LSL loopback: outlet -> collector -> decisions outlet -> inlet --------------------------


def _sim_file(tmp_path):
    evs = [{"type": "header", **HDR}]
    t = 0.0
    for k in range(3):
        for _ in range(6):
            evs.append({"type": "frame", "t": round(t, 6), "log_probs": ROW_A})
            t += 0.04
        evs.append(SEG)
        t += 1.0  # a pause between utterances (a frame gap after a boundary)
    evs.append(END)
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
    return p


@lsl_only
def test_lsl_loopback_collector(tmp_path):
    p = _sim_file(tmp_path)
    CFG.save(tmp_path / "trust.json")
    tag = uuid.uuid4().hex[:8]
    name, dec_name = f"test-collector-{tag}", f"test-collector-dec-{tag}"
    procs = {"check": {"type": "validate"},
             "trust": {"type": "trust", "config": "trust.json", "decoder": "greedy", "max_attempts": 1}}

    def cfg(receiver, exporters):
        return {"service": {"log": "quiet"}, "receivers": {"in": receiver}, "processors": procs,
                "exporters": exporters,
                "pipelines": {"main": {"receivers": ["in"], "processors": ["check", "trust"],
                                       "exporters": list(exporters)}}}

    # Reference: the same file through the file receiver.
    ref_col = Collector(parse(cfg({"type": "file", "paths": [str(p)], "stream_id": "in-0"},
                                  {"log": {"type": "jsonl", "path": "ref.jsonl"}}), base_dir=tmp_path))
    ref_col.run()
    ref = [json.loads(x) for x in (tmp_path / "ref.jsonl").read_text(encoding="utf-8").splitlines()]

    ready = threading.Event()
    th = threading.Thread(target=L.replay_to_lsl, args=(p, name), daemon=True,
                          kwargs={"speed": 0.0, "channel_format": "double64", "wait_consumers_s": 20.0,
                                  "linger_s": 1.0, "ready": ready})
    th.start()
    assert ready.wait(10)
    col = Collector(parse(cfg({"type": "lsl", "stream_name": name, "resolve_timeout_s": 10.0},
                              {"dec": {"type": "lsl", "stream_name": dec_name},
                               "log": {"type": "jsonl", "path": "lsl.jsonl"}}), base_dir=tmp_path))
    col.start()  # opens the decisions outlet and the inlets; nothing is processed yet
    inlet = L.PylslInlet(L.resolve(name=dec_name, timeout=10.0))
    info = inlet.info()
    assert info.type == "Markers" and info.channel_format == "string" and info.nominal_srate == 0
    trust = col.pipelines[0].processors[1]
    assert info.fidetype["role"] == "trust_decisions" and info.fidetype["event_type"] == "trust_decision"
    assert info.fidetype["config_id"] == trust.config_id and info.fidetype["binding"] == L.BINDING_VERSION
    assert col._exporters["dec"].outlet.outlet.wait_for_consumers(10.0)
    samples: list = []
    stop = threading.Event()

    def read():  # the subscriber reads while the collector runs; the outlet goes away at the stop
        while not stop.is_set():
            try:
                s, _ = inlet.pull_chunk(0.05, 100)
            except L.LSLStreamLost:
                return
            samples.extend(x[0] for x in s)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    t0 = time.monotonic()
    reason = col.run(duration_s=30.0)
    assert reason == "input done" and time.monotonic() - t0 < 30.0
    got_log = [json.loads(x) for x in (tmp_path / "lsl.jsonl").read_text(encoding="utf-8").splitlines()]
    reader.join(5.0)
    stop.set()
    inlet.close()
    th.join(30)
    got = [json.loads(x) for x in samples]
    assert len(got) == len(got_log) == len(ref) >= 3
    key = ("seq", "utterance", "is_final", "action", "shown", "config_id", "spec_version")
    assert [{k: d.get(k) for k in key} for d in got] == [{k: d.get(k) for k in key} for d in ref]
    assert sum(d["is_final"] for d in got) == 3
    st = col.metrics()["pipelines"]["main"]["receivers"]["in"]
    assert st["gaps"] == 0 and st["gaps_between_utterances"] == 2 and st["lost_streams"] == 0
    host = socket.gethostname()
    assert host not in json.dumps(got) and host not in json.dumps(col.metrics())  # LSL-C3
