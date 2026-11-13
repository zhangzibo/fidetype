"""M6-01: the Lab Streaming Layer adapter.

Unit tests use a fake inlet (no pylsl needed): header mapping, value
kinds, clock correction, out-of-order timestamps, gaps, loss and
reconnect, markers, the two-inlet merge, and equality with the file
replay path. The integration tests run a real outlet -> inlet loopback
on this machine and are skipped when pylsl / liblsl is not available.
Synthetic simulator streams only; no participant data.
"""

from __future__ import annotations

import json
import math
import sys
import threading
import uuid
from pathlib import Path

import numpy as np
import pytest

from fidetype.adapters import lsl as L
from fidetype.adapters.lsl import (
    GAP,
    LSLEventSource,
    LSLMapping,
    LSLStreamInfo,
    LSLStreamLost,
    LSLTrustRunner,
    LSLUnavailableError,
    build_header,
    to_log_probs,
)
from fidetype.conformance.io import write_jsonl
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events, replay
from fidetype.trust.testing import greedy_nbest

# A loose gate so that COMMIT, OFFER and ABSTAIN all occur.
CFG = FrozenTrustConfig(name="lsl-test").with_policy(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)


# --- helpers ---------------------------------------------------------------------


class FakeInlet:
    """Scripted :class:`fidetype.adapters.lsl.InletLike`.

    ``script`` items: ``(samples, stamps)`` for one chunk, or ``"lost"``.
    An exhausted script returns empty chunks.
    """

    def __init__(self, info: LSLStreamInfo, script=(), tc=0.0):
        self._info = info
        self.script = list(script)
        self.tc = tc
        self.tc_calls = 0
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
        self.tc_calls += 1
        return self.tc(self.tc_calls) if callable(self.tc) else self.tc

    def close(self):
        self.closed = True


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        self.t += 0.001
        return self.t


def _streams(n=4, seed=3):
    sents = sentences(40, seed=seed)
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=seed)
    return [sim.simulate(s, seed=11 * i).stream for i, s in enumerate(sents[:n])]


def _multi_file(tmp_path, streams, name="multi.jsonl"):
    """One JSONL file: utterances separated by segment_end, then end."""
    p0 = tmp_path / "_one.jsonl"
    events = []
    off = 0.0
    for k, st in enumerate(streams):
        write_jsonl(st, p0)
        evs = list(iter_events(p0))
        if k == 0:
            events.append(evs[0])
        for ev in evs[1:-1]:
            events.append({**ev, "t": round(ev["t"] + off, 9)})
        events.append({"type": "segment_end"})
        off = events[-2]["t"] + 1.0
    events[-1] = {"type": "end"}
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return p, events


def _native_infos(header: dict, srate: float, host="hostA"):
    h = {k: v for k, v in header.items() if k != "type"}
    V = len(h["vocab"])
    fr = LSLStreamInfo("nts", "NTS", V, srate, "double64", "sid-1", "uid-1", host,
                       channel_labels=list(h["vocab"]), fidetype={"nts_header": json.dumps(h), "values": "log_probs",
                                                                 "events_source_id": "sid-1.events"})
    ev = LSLStreamInfo("nts.events", "Markers", 1, 0.0, "string", "sid-1.events", "uid-2", host,
                       fidetype={"nts_header": json.dumps(h)})
    return fr, ev


def _fake_pair(events, base=50.0, chunk=7, tc=0.0, eps=1e-4):
    """Turn file events into scripted frames + events inlets (as replay_to_lsl would send them)."""
    head = events[0]
    fp = head.get("frame_period") or 0.04
    fr_info, ev_info = _native_infos(head, 1.0 / fp)
    t0 = next(e["t"] for e in events if e["type"] == "frame")
    frames, marks = [], []
    last = base - 1.0
    k = 0
    for e in events[1:]:
        if e["type"] == "frame":
            ts = base + (e["t"] - t0)
            frames.append(([(-math.inf if v is None else v) for v in e["log_probs"]], ts))
            last, k = ts, 0
        else:
            k += 1
            marks.append(([json.dumps(e)], last + eps * k))
    fscript = [([s for s, _ in frames[i:i + chunk]], [t for _, t in frames[i:i + chunk]])
               for i in range(0, len(frames), chunk)]
    # Markers arrive in single-sample chunks, interleaved by time with the frame chunks.
    return FakeInlet(fr_info, fscript, tc), FakeInlet(ev_info, [([s], [t]) for s, t in marks], tc)


def _run_fake(primary, events_inlet=None, mapping=None, decode=greedy_nbest, steps=100000, cfg=CFG, **kw):
    layer = StreamingTrustLayer(cfg, decode_fn=decode, streaming=StreamingConfig(max_attempts=1))
    # Watermark merge only (no time-out): the fake inlets deliver faster than real time.
    src = LSLEventSource(primary, events_inlet, mapping or LSLMapping(merge_window_s=1e9), clock=Clock(), **kw)
    out = []
    runner = LSLTrustRunner(layer, src, sink=out.append, keep=True)
    inlets = [primary] + ([events_inlet] if events_inlet is not None else [])
    for _ in range(steps):
        runner.step(0.0)
        if runner.summary.ended or not any(i.script for i in inlets):
            break
    runner.step(0.0)
    runner.finish()
    return runner, out


def _same_decisions(a, b, exact=True):
    assert [d.final for d in a] == [d.final for d in b]
    for x, y in zip(a, b):
        assert x.action == y.action and x.shown == y.shown
        if exact:
            assert x.decision == y.decision and x.inputs == y.inputs
        else:
            assert abs(x.inputs.p_top1 - y.inputs.p_top1) < 1e-4


# --- optional dependency -------------------------------------------------------------


def test_imports_without_pylsl(monkeypatch):
    monkeypatch.setitem(sys.modules, "pylsl", None)  # "import pylsl" now raises ImportError
    assert not L.pylsl_available()
    with pytest.raises(LSLUnavailableError, match=r"fidetype\[lsl\]"):
        L.require_pylsl()
    with pytest.raises(LSLUnavailableError):
        L.resolve(name="x", timeout=0.1)
    # The pure parts work without pylsl.
    info = LSLStreamInfo("p", "Probs", 2, 10.0, "float32", channel_labels=["a", "b"])
    h, values = build_header(info, LSLMapping())
    assert h["vocab"] == ["a", "b"] and values == "log_probs"
    assert L.main(["list", "--wait", "0.1"]) == 2  # clear error, exit code 2


# --- stream info and header ------------------------------------------------------------


XML = """<?xml version="1.0"?>
<info><name>dec</name><type>NTS</type><channel_count>3</channel_count><channel_format>float32</channel_format>
<source_id>src-9</source_id><nominal_srate>25</nominal_srate><version>1.1</version><created_at>12.5</created_at>
<uid>u-1</uid><hostname>someones-laptop</hostname>
<desc><channels>
<channel><label>&lt;blank&gt;</label><unit>log_prob</unit><type>nts.log_prob</type></channel>
<channel><label>a</label><unit>log_prob</unit></channel><channel><label>b</label><unit>log_prob</unit></channel>
</channels><fidetype><values>log_probs</values>
<nts_header>{"spec_version": "0.1", "vocab": ["&lt;blank&gt;", "a", "b"], "vocab_type": "char", "blank_id": 0,
"source": "d", "frame_period": 0.04, "clock_domain": "trial", "meta": {"device.modality": "emg"}}</nts_header>
</fidetype></desc></info>"""


def test_info_from_xml_and_native_header():
    info = LSLStreamInfo.from_xml(XML)
    assert info.name == "dec" and info.channel_count == 3 and info.nominal_srate == 25.0
    assert info.channel_labels == ["<blank>", "a", "b"] and info.channel_units[0] == "log_prob"
    assert info.source_id == "src-9" and info.uid == "u-1"
    h, values = build_header(info, LSLMapping(), lsl_extra={"time_correction_s": 0.001})
    assert h["type"] == "header" and h["vocab"] == ["<blank>", "a", "b"] and h["blank_id"] == 0
    assert h["clock_domain"] == "lsl"  # LSL times replace the producer's clock
    assert h["meta"] == {"device.modality": "emg"}  # the producer's meta is kept as is
    assert h["lsl"]["stream"]["source_id"] == "src-9" and h["lsl"]["time_correction_s"] == 0.001
    assert "someones-laptop" not in json.dumps(h)  # never write the host name


def test_foreign_header():
    info = LSLStreamInfo("probs", "Probabilities", 3, 50.0, "float32", "s", channel_labels=["rest", "left", "right"])
    h, values = build_header(info, LSLMapping(vocab_type="command", blank="rest", values="probs"))
    assert h["vocab"] == ["rest", "left", "right"] and h["blank_id"] == 0 and values == "probs"
    assert h["frame_period"] == pytest.approx(0.02) and h["vocab_type"] == "command"
    assert h["meta"]["adapter.name"] == "fidetype.adapters.lsl" and h["meta"]["data.derived"] is True
    assert h["source"] == "lsl:probs"
    h2, _ = build_header(info, LSLMapping(vocab=["x", "y", "z"], blank=2))
    assert h2["vocab"] == ["x", "y", "z"] and h2["blank_id"] == 2 and h2["vocab_type"] == "other"
    with pytest.raises(ValueError, match="channel labels"):
        build_header(LSLStreamInfo("raw", "EEG", 3, 250.0, "float32"), LSLMapping())
    with pytest.raises(ValueError, match="3 channels"):
        build_header(info, LSLMapping(vocab=["x", "y"]))
    with pytest.raises(ValueError, match="blank"):
        build_header(info, LSLMapping(blank="nope"))
    mk = LSLStreamInfo("m", "Markers", 1, 0.0, "string")
    hm, _ = build_header(mk, LSLMapping())
    assert hm["vocab"] == [] and hm["blank_id"] is None


def test_value_kinds():
    p = np.array([[0.7, 0.2, 0.1], [1.0, 0.0, 0.0]])
    lp = to_log_probs(p, "probs")
    assert np.allclose(np.exp(lp), p) and lp[1, 1] == -math.inf
    lg = np.array([[2.0, 1.0, -3.0]])
    out = to_log_probs(lg, "logits")
    assert abs(np.log(np.exp(out).sum()) ) < 1e-12
    with pytest.raises(ValueError):
        to_log_probs(-p, "probs")


def test_mapping_rejects_bad_settings():
    for kw in ({"values": "x"}, {"clock": "x"}, {"on_gap": "x"}, {"out_of_order": "x"}, {"gap_factor": 1.0},
               {"vocab_type": "x"}, {"plain_markers": "x"}):
        with pytest.raises(ValueError):
            LSLMapping(**kw)


# --- equality with the file replay path (fake inlets) -------------------------------------


def test_fake_loopback_equals_file_replay(tmp_path):
    p, events = _multi_file(tmp_path, _streams(5))
    ref = replay(p, StreamingTrustLayer(CFG, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=1)))
    assert len(ref) == 5
    fr, ev = _fake_pair(events)
    runner, out = _run_fake(fr, ev)
    _same_decisions(runner.kept, ref)
    assert {d.action for d in ref} >= {d.action for d in runner.kept}
    assert all(e["type"] == "trust_decision" and e["is_final"] for e in out)
    rec = out[0]["lsl"]
    assert rec["clock"] == "receiver" and rec["utterance"]["gaps"] == 0
    assert [e["lsl"]["utterance"]["frames"] for e in out] == [e["input"]["frame_range"][1] for e in out]
    assert all(e["lsl"]["utterance"]["gaps"] == 1 for e in out[1:])  # the 1 s pause between utterances
    assert rec["streams"][0]["source_id"] == "sid-1" and rec["streams"][1]["type"] == "Markers"
    assert runner.summary.rejected_events == 0 and runner.source.stats.late_releases == 0


def test_hypothesis_only_marker_stream():
    head = {"type": "header", "spec_version": "0.1", "vocab": [], "vocab_type": "char", "blank_id": None,
            "source": "llm-decoder", "meta": {}}
    info = LSLStreamInfo("hyp", "Markers", 1, 0.0, "string", "h1", "u", "hostA",
                         fidetype={"nts_header": json.dumps({k: v for k, v in head.items() if k != "type"})})
    hyps = [
        {"type": "hypothesis", "id": "a1", "is_final": False, "score_semantics": "none",
         "nbest": [{"text": "hello", "score": -1.0}]},
        {"type": "hypothesis", "id": "a2", "revision_of": "a1", "is_final": True, "score_semantics": "none",
         "nbest": [{"text": "hello world", "score": -0.5}, {"text": "hello word", "score": -2.5}]},
        {"type": "end"},
    ]
    inlet = FakeInlet(info, [([json.dumps(h)], [10.0 + i]) for i, h in enumerate(hyps)])
    runner, out = _run_fake(inlet, decode=None)
    ref = replay([head] + hyps, StreamingTrustLayer(CFG, streaming=StreamingConfig(max_attempts=1)))
    _same_decisions(runner.kept, ref)
    assert [e["is_final"] for e in out] == [False, True]
    assert out[1]["input"]["hypothesis_id"] == "a2"


def test_plain_markers():
    info = LSLStreamInfo("txt", "Markers", 1, 0.0, "string", "t1")
    marks = ["hello there", "not json {", "{bad json", "trial_end", "help me"]
    inlet = FakeInlet(info, [([m], [5.0 + i]) for i, m in enumerate(marks)])
    m = LSLMapping(plain_markers="hypothesis", boundary_markers=("trial_end",), merge_window_s=0.0)
    runner, out = _run_fake(inlet, mapping=m, decode=None, steps=20)
    texts = [e["shown"] for e in out if e["is_final"]]
    assert len(texts) == 3  # three text markers, each one final 1-best hypothesis
    st = runner.source.stats
    assert st.bad_markers == 1 and st.markers == 5
    m2 = LSLMapping(merge_window_s=0.0)  # default: plain strings are ignored
    runner2, out2 = _run_fake(FakeInlet(info, [([x], [5.0 + i]) for i, x in enumerate(marks)]), mapping=m2,
                              decode=None, steps=20)
    assert out2 == [] and runner2.source.stats.ignored_markers == 4


# --- clock correction ----------------------------------------------------------------------


def _frames_inlet(n=20, srate=25.0, stamps=None, tc=0.0, host="hostA", V=3, script_extra=()):
    vocab = ["<b>", "a", "b"][:V]
    h = {"spec_version": "0.1", "vocab": vocab, "vocab_type": "char", "blank_id": 0, "source": "x",
         "frame_period": 1 / srate, "meta": {}}
    info = LSLStreamInfo("f", "NTS", V, srate, "float32", "f1", "u", host, channel_labels=vocab,
                         fidetype={"nts_header": json.dumps(h)})
    row = list(np.log([0.6, 0.3, 0.1][:V]) - np.log(sum([0.6, 0.3, 0.1][:V])))
    stamps = list(stamps if stamps is not None else 100.0 + np.arange(n) / srate)
    return FakeInlet(info, [([row] * len(stamps), stamps), *script_extra], tc), stamps


def test_clock_correction_receiver_and_sender():
    inlet, stamps = _frames_inlet(tc=2.5)
    src = LSLEventSource(inlet, mapping=LSLMapping(), clock=Clock())
    evs = [e for e in src.poll(0) if e["type"] == "frame"]
    assert [e["t"] for e in evs] == pytest.approx([t + 2.5 for t in stamps])
    rec = src.provenance()
    assert rec["clock"] == "receiver" and rec["time_correction_s"] == 2.5 and rec["updates"] >= 1
    assert src.header()["lsl"]["time_correction_s"] == 2.5
    inlet2, _ = _frames_inlet(tc=2.5)
    src2 = LSLEventSource(inlet2, mapping=LSLMapping(clock="sender"), clock=Clock())
    evs2 = [e for e in src2.poll(0) if e["type"] == "frame"]
    assert [e["t"] for e in evs2] == pytest.approx(stamps)
    assert inlet2.tc_calls == 0 and src2.provenance()["time_correction_s"] is None


def test_clock_refresh_and_shared_host_offset():
    calls = iter([1.0, 1.0001, 1.0002, 1.0003, 1.0004, 1.0005])
    inlet, _ = _frames_inlet(tc=lambda k: next(calls), script_extra=[([[0.0, -50.0, -50.0]], [200.0])])
    src = LSLEventSource(inlet, mapping=LSLMapping(clock_refresh_s=0.0), clock=Clock())
    src.poll(0)
    src.poll(0)
    rec = src.provenance()
    assert rec["updates"] >= 2 and rec["spread_s"] == pytest.approx(rec["spread_s"]) and rec["spread_s"] > 0
    # Two inlets from the same host share one offset (a stable merge order).
    fr, ev = _fake_pair(list(iter_events_from_stream()), tc=0.0)
    fr.tc, ev.tc = 3.0, 3.0004
    src2 = LSLEventSource(fr, ev, LSLMapping(merge_window_s=0.0, clock_refresh_s=1e9), clock=Clock())
    out = []
    for _ in range(200):
        out += src2.poll(0)
    marks = [e for e in out if e["type"] in ("segment_end", "end")]
    frames = [e for e in out if e["type"] == "frame"]
    assert marks and ev.tc_calls == 0  # the events inlet used the frames inlet's offset
    assert marks[-1]["lsl_t"] > frames[-1]["t"]


def iter_events_from_stream():
    st = _streams(1)[0]
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.jsonl"
        write_jsonl(st, p)
        return list(iter_events(p))


# --- order, gaps, loss -------------------------------------------------------------------------


def test_out_of_order_timestamps():
    stamps = [10.0, 10.04, 10.04, 10.038, 9.5, 10.08, 10.12]
    inlet, _ = _frames_inlet(stamps=stamps)
    src = LSLEventSource(inlet, mapping=LSLMapping(), clock=Clock())
    ts = [e["t"] for e in src.poll(0) if e["type"] == "frame"]
    assert all(b > a for a, b in zip(ts, ts[1:]))  # NTS: strictly increasing
    assert len(ts) == 6 and src.stats.clamped == 2 and src.stats.dropped_out_of_order == 1
    inlet, _ = _frames_inlet(stamps=stamps)
    src = LSLEventSource(inlet, mapping=LSLMapping(out_of_order="drop"), clock=Clock())
    assert len([e for e in src.poll(0) if e["type"] == "frame"]) == 4
    inlet, _ = _frames_inlet(stamps=stamps)
    src = LSLEventSource(inlet, mapping=LSLMapping(out_of_order="error"), clock=Clock())
    with pytest.raises(ValueError, match="does not increase"):
        src.poll(0)


def _gap_events(on_gap):
    stamps = list(100.0 + np.arange(10) * 0.04) + list(101.0 + np.arange(10) * 0.04)
    end_info = LSLStreamInfo("e", "Markers", 1, 0.0, "string", "e1", "u2", "hostA")
    inlet, _ = _frames_inlet(stamps=stamps)
    ev = FakeInlet(end_info, [([json.dumps({"type": "end"})], [102.0])])
    return inlet, ev, LSLMapping(on_gap=on_gap, merge_window_s=0.0)


@pytest.mark.parametrize("on_gap", ["mark", "segment", "abort"])
def test_gaps(on_gap):
    inlet, ev, m = _gap_events(on_gap)
    runner, out = _run_fake(inlet, ev, mapping=m)
    finals = [e for e in out if e["is_final"]]
    assert runner.source.stats.gaps == 1
    if on_gap == "mark":
        assert len(finals) == 1 and finals[0]["lsl"]["utterance"]["gaps"] == 1
        assert finals[0]["input"]["frame_range"] == [0, 20]
    elif on_gap == "segment":
        assert [e["input"]["frame_range"] for e in finals] == [[0, 10], [0, 10]]
    else:
        assert len(finals) == 1 and finals[0]["input"]["frame_range"] == [0, 10]
        assert runner.summary.aborted_utterances == 1
        assert runner.layer.session_state("lsl")["aborted_utterances"] == 1


def test_gap_event_is_ignored_by_v01_consumers():
    inlet, ev, m = _gap_events("mark")
    src = LSLEventSource(inlet, ev, m, clock=Clock())
    out = []
    for _ in range(10):
        out += src.poll(0)
    g = [e for e in out if e["type"] == GAP]
    assert len(g) == 1 and g[0]["missing_frames"] == pytest.approx(round((101.0 - 100.36) / 0.04) - 1)
    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest)
    for e in out:
        layer.push(e)  # the layer ignores the extension event (spec 6.2 rule 5)


def test_loss_aborts_and_reconnects():
    inlet, stamps = _frames_inlet(n=8, script_extra=["lost"])
    fresh, _ = _frames_inlet(n=12, tc=0.0)
    end = LSLStreamInfo("e", "Markers", 1, 0.0, "string", "e1", "u2", "hostA")
    fresh.script.append(([[0.0, -40.0, -40.0]], [100.0 + 12 / 25]))  # one more frame after reconnect
    tries = {"n": 0}

    def reopen():
        tries["n"] += 1
        if tries["n"] == 1:
            raise RuntimeError("not visible yet")
        return fresh

    ev = FakeInlet(end, [])
    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=1))
    src = LSLEventSource(inlet, ev, LSLMapping(merge_window_s=0.0, reconnect_interval_s=0.0), clock=Clock(),
                         reopen_primary=reopen)
    out = []
    logs = []
    runner = LSLTrustRunner(layer, src, sink=out.append, keep=True, log=logs.append)
    for _ in range(10):
        runner.step(0.0)
    assert out == []  # the cut utterance gave no decision
    assert runner.summary.aborted_utterances == 1 and src.stats.lost == 1 and src.stats.reconnects == 1
    assert any("lost" in x for x in logs) and any("reconnected" in x for x in logs)
    ev.script.append(([json.dumps({"type": "end"})], [200.0]))
    for _ in range(5):
        runner.step(0.0)
    assert len(out) == 1 and out[0]["input"]["frame_range"] == [0, 13]
    assert out[0]["lsl"]["reconnects"] == 1


def test_loss_without_reconnect_raises():
    inlet, _ = _frames_inlet(n=4, script_extra=["lost"])
    src = LSLEventSource(inlet, mapping=LSLMapping(reconnect_timeout_s=0.0), clock=Clock())
    runner = LSLTrustRunner(StreamingTrustLayer(CFG, decode_fn=greedy_nbest), src)
    runner.step(0)
    runner.step(0)
    with pytest.raises(LSLStreamLost):
        runner.step(0)


def test_merge_waits_for_the_other_inlet():
    """A marker that arrives before the frames of its time is held back."""
    vocab = ["<b>", "a", "b"]
    fr, _ = _frames_inlet(stamps=[])
    fr.script = [([], []), ([[0.0, -60.0, -60.0]] * 3, [10.0, 10.04, 10.08])]
    ev = FakeInlet(LSLStreamInfo("e", "Markers", 1, 0.0, "string", "e1", "u2", "hostA"),
                   [([json.dumps({"type": "segment_end"})], [10.05])])
    src = LSLEventSource(fr, ev, LSLMapping(merge_window_s=1e9), clock=Clock())
    first = src.poll(0)
    assert [e["type"] for e in first] == ["header"]  # the marker waits for the frames inlet
    second = src.poll(0)
    assert [e["type"] for e in second] == ["frame", "frame", "segment_end"]  # released up to the watermark
    assert [e["type"] for e in src.drain()] == ["frame"]
    assert vocab


def test_runner_skips_bad_events_and_idle_flush():
    inlet, _ = _frames_inlet(n=5)
    bad = [[0.0, 0.0, 0.0]]  # does not sum to 1
    inlet.script.append((bad, [200.0]))
    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest)
    src = LSLEventSource(inlet, mapping=LSLMapping(), clock=Clock())
    out = []
    runner = LSLTrustRunner(layer, src, sink=out.append)
    runner.step(0)
    runner.step(0)
    assert runner.summary.rejected_events == 1 and out == []
    src.clock.t += 10.0
    runner.step(0, idle_flush_s=1.0)
    assert len(out) == 1 and runner.summary.idle_flushes == 1
    with pytest.raises(Exception):
        inlet.script.append((bad, [300.0]))
        LSLTrustRunner(layer, src, on_bad_event="raise").step(0)


def test_run_stops_and_aborts_pending():
    inlet, _ = _frames_inlet(n=5)
    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest)
    runner = LSLTrustRunner(layer, LSLEventSource(inlet, mapping=LSLMapping(), clock=Clock()))
    s = runner.run(duration_s=0.05, poll_timeout=0.0)
    assert s.stop_reason == "duration" and s.aborted_utterances == 1 and s.final_decisions == 0


class _MeanDecoder:
    """Toy raw-signal decoder: one frame per 5 samples; channel 0 > 0 means "a"."""

    header = {"spec_version": "0.1", "vocab": ["<b>", "a"], "vocab_type": "char", "blank_id": 0,
              "source": "toy", "frame_period": 0.02, "meta": {"device.modality": "eeg"}}

    def process(self, samples, times):
        out = []
        for i in range(0, len(samples) - 4, 5):
            p = 0.9 if samples[i:i + 5, 0].mean() > 0 else 0.1
            out.append((float(times[i + 4]), np.log([1 - p, p])))
        return out


def test_signal_decoder_route():
    info = LSLStreamInfo("eeg", "EEG", 4, 250.0, "float32", "eeg-1", "u", "h",
                         channel_labels=["C3", "C4", "Cz", "Pz"], channel_units=["microvolts"] * 4)
    n = 50
    sig = np.zeros((n, 4))
    sig[10:20, 0] = 1.0
    inlet = FakeInlet(info, [(sig.tolist(), list(1.0 + np.arange(n) / 250.0))])
    src = LSLEventSource(inlet, mapping=LSLMapping(), signal_decoder=_MeanDecoder(), clock=Clock())
    evs = src.poll(0)
    h = evs[0]
    assert h["vocab"] == ["<b>", "a"] and h["meta"]["device.channel_count"] == 4
    assert h["lsl"]["stream"]["type"] == "EEG"
    frames = [e for e in evs if e["type"] == "frame"]
    assert len(frames) == 10
    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest)
    for e in evs:
        layer.push(e)
    d = layer.end_of_utterance()
    assert d and d[0].final


def test_abort_utterance_on_layer():
    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest)
    assert layer.abort_utterance("nobody") == 0
    inlet, _ = _frames_inlet(n=6)
    for e in LSLEventSource(inlet, mapping=LSLMapping(), clock=Clock()).poll(0):
        layer.push(e, "s")
    assert layer.abort_utterance("s") == 6
    assert layer.end_of_utterance("s") == []
    st = layer.session_state("s")
    assert st["aborted_utterances"] == 1 and st["buffered_frames"] == 0 and st["has_header"]


# --- integration: real LSL loopback on this machine ----------------------------------------------

lsl_only = pytest.mark.skipif(not L.pylsl_available(), reason="pylsl / liblsl not available")


def _loopback(path, channel_format="double64", decode=greedy_nbest, speed=0.0):
    name = f"fidetype-test-{uuid.uuid4().hex[:8]}"
    ready = threading.Event()
    res = {}

    def send():
        res["rs"] = L.replay_to_lsl(path, name, speed=speed, channel_format=channel_format, wait_consumers_s=20.0,
                                    linger_s=1.0, ready=ready)

    th = threading.Thread(target=send, daemon=True)
    th.start()
    assert ready.wait(10)
    src = L.open_source(name=name, timeout=10.0, mapping=LSLMapping(merge_window_s=0.05))
    layer = StreamingTrustLayer(CFG, decode_fn=decode, streaming=StreamingConfig(max_attempts=1))
    out = []
    runner = LSLTrustRunner(layer, src, sink=out.append, keep=True)
    s = runner.run(duration_s=60.0, poll_timeout=0.02)
    src.close()
    th.join(30)
    return runner, out, s, res["rs"]


@lsl_only
@pytest.mark.parametrize("fmt", ["double64", "float32"])
def test_lsl_loopback_equals_file_replay(tmp_path, fmt):
    p, _ = _multi_file(tmp_path, _streams(4))
    ref = replay(p, StreamingTrustLayer(CFG, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=1)))
    runner, out, s, rs = _loopback(p, fmt)
    assert s.stop_reason == "end", s
    assert rs.frames == sum(1 for e in iter_events(p) if e["type"] == "frame")
    _same_decisions(runner.kept, ref, exact=(fmt == "double64"))
    assert s.rejected_events == 0 and s.aborted_utterances == 0
    assert s.source["late_releases"] == 0 and s.source["dropped_out_of_order"] == 0
    assert all(e["lsl"]["clock"] == "receiver" and e["lsl"]["time_correction_s"] is not None for e in out)


@lsl_only
def test_lsl_loopback_hypothesis_stream(tmp_path):
    head = {"type": "header", "spec_version": "0.1", "vocab": [], "vocab_type": "char", "blank_id": None,
            "source": "llm", "meta": {}}
    evs = [head]
    for k in range(3):
        evs.append({"type": "hypothesis", "id": f"p{k}", "is_final": False, "score_semantics": "none",
                    "nbest": [{"text": "ab"[: k % 2 + 1], "score": -1.0}]})
        evs.append({"type": "hypothesis", "id": f"f{k}", "is_final": True, "score_semantics": "none",
                    "nbest": [{"text": "a b c", "score": -0.2 * k}, {"text": "a b d", "score": -1.0}]})
    evs.append({"type": "end"})
    p = tmp_path / "h.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
    ref = replay(p, StreamingTrustLayer(CFG, streaming=StreamingConfig(max_attempts=1)))
    runner, out, s, rs = _loopback(p, decode=None)
    assert rs.frames == 0 and rs.events == len(evs) - 1
    _same_decisions(runner.kept, ref)


@lsl_only
def test_decision_outlet_roundtrip():
    pl = L.require_pylsl()
    name = f"fidetype-dec-{uuid.uuid4().hex[:8]}"
    out = L.DecisionOutlet(name, config_id="tcfg-x")
    inlet = L.PylslInlet(L.resolve(name=name, timeout=10.0))
    assert inlet.info().fidetype["role"] == "trust_decisions" and inlet.info().type == "Markers"
    assert out.outlet.wait_for_consumers(10.0)
    ev = {"type": "trust_decision", "seq": 0, "is_final": True, "action": "COMMIT"}
    got = []
    for _ in range(50):
        out.push(ev)
        s, ts = inlet.pull_chunk(0.1, 10)
        got += s
        if got:
            break
    assert json.loads(got[0][0]) == ev
    assert pl.local_clock() > 0
    inlet.close()
