"""M6-11: the WebSocket adapter (FEP-0004).

Unit tests run the sans-IO cores (no ``websockets`` needed): order,
gaps, reorder, resume, take-over, auth, the output hub and the subscriber
checks. The integration tests run a real server and client on localhost
(port 0, so the OS picks a free port) and are skipped when ``websockets``
is not installed. Synthetic simulator streams only; no participant data.

CI: the ``dev`` extra includes ``[ws]``, so the integration tests run in CI.
"""

from __future__ import annotations

import builtins
import importlib
import json
import math
import socket
import sys
import threading
import time
import urllib.request

import pytest

from fidetype.adapters import ws as W
from fidetype.conformance.io import write_jsonl
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events, replay
from fidetype.trust.testing import greedy_nbest

CFG = FrozenTrustConfig(name="ws-test").with_policy(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)
LP = [math.log(0.9), math.log(0.07), math.log(0.03)]
HDR = {"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a", "b"], "vocab_type": "char", "blank_id": 0,
       "source": "t", "frame_period": 0.04, "meta": {}}


def _layer(decode=greedy_nbest):
    return StreamingTrustLayer(CFG, decode_fn=decode, streaming=StreamingConfig(max_attempts=1))


def _events(tmp_path, n=4, seed=3):
    """One stream: n simulator utterances with segment_end between them, then end."""
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=seed)
    evs, off = [], 0.0
    for k, s in enumerate(sentences(40, seed=seed)[:n]):
        write_jsonl(sim.simulate(s, seed=11 * k).stream, tmp_path / "_one.jsonl")
        e = list(iter_events(tmp_path / "_one.jsonl"))
        if k == 0:
            evs.append(e[0])
        evs += [{**ev, "t": round(ev["t"] + off, 9)} for ev in e[1:-1]]
        evs.append({"type": "segment_end"})
        off = evs[-2]["t"] + 1.0
    evs[-1] = {"type": "end"}
    return evs


def _same(a, b):
    assert [d.final for d in a] == [d.final for d in b]
    for x, y in zip(a, b):
        assert x.action == y.action and x.shown == y.shown
        assert x.decision == y.decision and x.inputs == y.inputs


def _fr(k, seq=None):
    return {"type": "frame", "t": round(k * 0.04, 6), "log_probs": LP, "ws_seq": k + 1 if seq is None else seq}


def _items(eff):
    return [(sid, e) for sid, e in eff.items]


# --- optional dependency -----------------------------------------------------------------------


def test_imports_without_websockets(monkeypatch):
    real = builtins.__import__

    def fake(name, *a, **kw):
        if name == "websockets" or name.startswith("websockets."):
            raise ImportError("no websockets")
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake)
    for m in [m for m in sys.modules if m == "websockets" or m.startswith("websockets.")]:
        monkeypatch.delitem(sys.modules, m)
    mod = importlib.reload(W)
    assert not mod.websockets_available()
    with pytest.raises(mod.WSUnavailableError, match=r"fidetype\[ws\]"):
        mod.WSServer().start()
    core = mod.IngestCore()  # the sans-IO parts still work
    core.open(1)
    assert core.message(1, {**HDR, "ws": {"stream_id": "s"}}).sends[0][1]["type"] == "ws_welcome"
    monkeypatch.undo()
    importlib.reload(W)


# --- IngestCore ---------------------------------------------------------------------------------


def _core(**kw):
    core = W.IngestCore(W.IngestSettings(**kw))
    core.open(1)
    eff = core.message(1, {**HDR, "ws": {"stream_id": "s1"}}, 0.0)
    return core, eff


def test_handshake_welcome_and_header_item():
    core, eff = _core()
    assert eff.sends == [(1, {"type": "ws_welcome", "binding": "nts-ws/0.1", "role": "ingest", "stream_id": "s1",
                              "seq": 0, "resumed": False, "ack_every": 64, "window": 4096})]
    assert [e["type"] for _, e in eff.items] == ["ws_status", "header"]
    assert "ws" not in eff.items[1][1]


def test_text_and_dict_messages_give_the_same_items():
    core, _ = _core()
    a = core.message(1, json.dumps(_fr(0)), 0.0)
    b = core.message(1, _fr(1), 0.0)
    assert [e["ws_seq"] for _, e in a.items + b.items] == [1, 2]


def test_reorder_window_and_gap_timeout():
    core, _ = _core(reorder_window=4, reorder_timeout_s=0.25)
    assert core.message(1, _fr(1), 0.0).items == []  # seq 2 held (seq 1 missing)
    eff = core.message(1, _fr(0), 0.01)
    assert [e["ws_seq"] for _, e in eff.items] == [1, 2] and core.stats.reordered == 1
    core.message(1, _fr(3), 0.1)  # seq 4 held, seq 3 missing
    assert core.tick(0.2).items == []
    eff = core.tick(0.4)
    st = [e for _, e in eff.items if e["type"] == "ws_status"]
    assert st[0]["status"] == "gap" and st[0]["missing"] == 1 and core.stats.gaps == 1
    assert [e["ws_seq"] for _, e in eff.items if e["type"] == "frame"] == [4]


def test_window_overflow_is_a_gap():
    core, _ = _core(reorder_window=2)
    for k in (2, 3):
        core.message(1, _fr(k), 0.0)
    eff = core.message(1, _fr(4), 0.0)  # 3 held > window 2
    assert core.stats.gaps == 1 and core.stats.missing_events == 2
    assert [e["ws_seq"] for _, e in eff.items if e["type"] == "frame"] == [3, 4, 5]


def test_acks_by_count_by_time_and_at_end():
    core, _ = _core(ack_every=3, ack_interval_s=0.1)
    acks = []
    for k in range(4):
        acks += [m["seq"] for _, m in core.message(1, _fr(k), 0.0).sends]
    assert acks == [3]
    assert [m["seq"] for _, m in core.tick(0.2).sends] == [4]
    assert [m["seq"] for _, m in core.message(1, {"type": "end", "ws_seq": 5}, 0.3).sends] == [5]


def test_resume_lossless_and_timeout():
    core, _ = _core(resume_timeout_s=2.0)
    core.message(1, _fr(0), 0.0)
    core.message(1, _fr(1), 0.0)
    assert core.disconnect(1, 0.5).items[0][1]["status"] == "disconnected"
    core.open(2)
    eff = core.message(2, {**HDR, "ws": {"stream_id": "s1", "resume": True}}, 1.0)
    assert eff.sends[0][1]["seq"] == 2 and eff.sends[0][1]["resumed"] is True
    assert [e["status"] for _, e in eff.items] == ["resumed"]  # no second header for the layer
    eff = core.message(2, {"type": "ws_batch", "events": [_fr(1), _fr(2)]}, 1.0)
    assert core.stats.duplicates == 1 and [e["ws_seq"] for _, e in eff.items] == [3]
    core.disconnect(2, 2.0)
    assert core.tick(3.9).items == []
    eff = core.tick(4.0)
    assert eff.items[0][1]["status"] == "lost" and "s1" not in core.streams


def test_take_over_closes_the_old_connection():
    core, _ = _core()
    core.open(2)
    eff = core.message(2, {**HDR, "ws": {"stream_id": "s1", "resume": True}}, 0.1)
    assert (1, W.CLOSE_TAKEN_OVER, "taken_over") in eff.closes
    assert core.message(1, _fr(0), 0.2).items == []  # the old connection is ignored


@pytest.mark.parametrize("msg,code", [
    (b"\x00", W.CLOSE_BINARY), ("{not json", W.CLOSE_INVALID), ('{"type": "frame", "t": NaN}', W.CLOSE_INVALID),
    ({"type": "frame", "t": 0.0, "log_probs": [0, 0, 0]}, W.CLOSE_INVALID),
    ({"type": "ws_batch", "events": [_fr(0), _fr(2)]}, W.CLOSE_INVALID),
    ({"type": "ws_batch", "events": [{"type": "ws_ack", "ws_seq": 1}]}, W.CLOSE_INVALID),
    ("x" * (W.MAX_MESSAGE_BYTES + 1), W.CLOSE_TOO_BIG),
])
def test_refusals(msg, code):
    core, _ = _core()
    eff = core.message(1, msg, 0.0)
    assert eff.closes and eff.closes[0][1] == code
    assert eff.sends[0][1]["type"] == "ws_error"


def test_auth_hook():
    core = W.IngestCore(auth=W.token_checker("s3cret"))
    core.open(1, authorization="Bearer s3cret")
    assert core.message(1, {**HDR}, 0.0).sends[0][1]["type"] == "ws_welcome"
    core.open(2)
    eff = core.message(2, {**HDR}, 0.0)
    assert eff.closes[0][1] == W.CLOSE_POLICY
    core.open(3)
    assert core.message(3, {"type": "ws_auth", "token": "s3cret"}, 0.0).closes == []
    assert core.message(3, {**HDR}, 0.0).sends[0][1]["stream_id"] == "anon-2"
    # The token never appears in any output.
    assert "s3cret" not in json.dumps([m for _, m in eff.sends])
    assert W.bearer_token("bearer  abc ") == "abc" and W.bearer_token("Basic abc") is None


def test_runner_drops_the_tail_of_a_cut_utterance():
    """A gap aborts the open utterance; the frames after it up to segment_end are dropped too."""
    out = []
    r = W.WSTrustRunner(_layer(), sink=out.append)
    evs = [("s", dict(HDR))] + [("s", _fr(k)) for k in range(3)]
    evs += [("s", {"type": W.WS_STATUS, "status": "gap"}), ("s", _fr(5, 6)), ("s", {"type": "segment_end", "ws_seq": 7})]
    evs += [("s", _fr(k, k + 1)) for k in range(7, 10)] + [("s", {"type": "end", "ws_seq": 11})]
    r.handle(evs)
    assert r.summary.aborted_utterances == 1 and r.summary.skipped_after_gap == 1
    assert [d["is_final"] for d in out] == [True] and out[0]["session"] == "s" and out[0]["ws"]["stream_id"] == "s"


# --- output side -----------------------------------------------------------------------------------


def test_output_hub_resume_missed_and_overflow():
    hub = W.OutputHub("decisions", history=3, queue_size=2)
    for k in range(5):
        hub.publish({"type": "trust_decision", "n": k})
    sub, welcome, replay_ = hub.subscribe({"type": "ws_subscribe", "from_seq": 2})
    assert welcome["seq"] == 5 and welcome["first_available"] == 3 and welcome["missed"] == 1
    assert [m["ws_seq"] for m in replay_] == [3, 4, 5]
    for k in range(3):
        hub.publish({"type": "trust_decision"})
    assert sub.overflow and hub.dropped_subscribers == 1
    with pytest.raises(ValueError):
        hub.subscribe({"type": "ws_subscribe", "binding": "nts-ws/2.0"})
    with pytest.raises(ValueError):
        hub.subscribe({"type": "ws_subscribe", "from_seq": 0})


def test_subscriber_core():
    c = W.SubscriberCore()
    td = lambda s, seq, utt, fin=True: {"type": "trust_decision", "session": "a", "seq": seq, "utterance": utt,  # noqa: E731
                                        "is_final": fin, "action": "COMMIT", "shown": ["x"], "p_top1": 0.9,
                                        "score_semantics": "calibrated_prob", "ws_seq": s}
    c.receive({"type": "ws_welcome"})
    assert c.receive(td(1, 0, 0)) is None
    assert c.receive(td(3, 2, 2)) == ("resubscribe", 2)
    c.receive({"type": "ws_welcome", "seq": 3})
    c.receive(td(2, 1, 1))
    c.receive(td(3, 2, 2))
    s = c.finish()
    assert s["decisions"] == 3 and s["gaps"] == [2] and s["acted"] == ["x", "x", "x"]


# --- integration: a real server and client on localhost --------------------------------------------

ws_only = pytest.mark.skipif(not W.websockets_available(), reason="websockets not installed (pip install fidetype[ws])")


class Live:
    def __init__(self, ingest=None, decode=greedy_nbest, **settings):
        self.layer = _layer(decode)
        self.server = W.WSServer(ingest or W.IngestSettings(), W.ServerSettings(port=0, **settings)).start()
        self.out = []
        self.runner = W.WSTrustRunner(self.layer, self.server, sink=self.out.append, hub=self.server.decisions,
                                      events_hub=self.server.events, keep=True)
        self.url = self.server.url

    def run(self, send, **kw):
        th = threading.Thread(target=send, daemon=True)
        th.start()
        s = self.runner.run(duration_s=kw.pop("duration_s", 30.0), poll_timeout=0.01, **kw)
        th.join(10)
        self.server.stop()
        return s


@ws_only
@pytest.mark.parametrize("batch", [1, 8])
def test_loopback_equals_batch_replay(tmp_path, batch):
    evs = _events(tmp_path)
    ref = replay(evs, _layer())
    live = Live()
    res = {}
    s = live.run(lambda: res.setdefault("rs", W.replay_to_ws(evs, live.url + "/nts", "sim-1", speed=0, batch=batch)),
                 max_streams=1)
    assert s.stop_reason == "max_streams"
    _same(live.runner.kept, ref)
    assert s.rejected_events == 0 and s.aborted_utterances == 0
    assert res["rs"].events == len(evs) - 1
    assert all(e["session"] == "sim-1" and e["ws"]["binding"] == "nts-ws/0.1" for e in live.out)
    assert [e["ws_seq"] for e in live.out] == list(range(1, len(live.out) + 1))


@ws_only
def test_loopback_drop_and_resume_equals_batch(tmp_path):
    evs = _events(tmp_path)
    ref = replay(evs, _layer())
    live = Live()
    res = {}
    n = len(evs)
    s = live.run(lambda: res.setdefault("rs", W.replay_to_ws(evs, live.url + "/nts", "sim-2", speed=0, batch=4,
                                                             drop_at=[n // 5, n // 2])), max_streams=1)
    _same(live.runner.kept, ref)
    assert res["rs"].reconnects == 2 and s.ingest["resumes"] == 2 and s.aborted_utterances == 0


@ws_only
def test_loopback_lost_events_abort_the_utterance(tmp_path):
    evs = _events(tmp_path, n=3)
    ref = replay(evs, _layer())
    live = Live(W.IngestSettings(reorder_timeout_s=0.05))
    s = live.run(lambda: W.replay_to_ws(evs, live.url + "/nts", "sim-3", speed=0, lose=[20, 21]), max_streams=1)
    assert s.ingest["gaps"] == 1 and s.ingest["missing_events"] == 2
    assert s.aborted_utterances == 1 and s.skipped_after_gap > 0
    finals = [d for d in live.runner.kept if d.final]
    assert len(finals) == len([d for d in ref if d.final]) - 1  # the cut first utterance has no decision
    _same(finals, [d for d in ref if d.final][1:])


@ws_only
def test_loopback_resume_timeout_drops_the_stream():
    live = Live(W.IngestSettings(resume_timeout_s=0.2))

    def send():
        p = W.WSProducer(live.url + "/nts", HDR, stream_id="gone").connect()
        for k in range(5):
            p.send({"type": "frame", "t": k * 0.04, "log_probs": LP})
        p.flush()
        time.sleep(0.1)
        p.drop()

    s = live.run(send, duration_s=1.5)
    assert s.ingest["lost_streams"] == 1 and s.aborted_utterances == 1 and s.final_decisions == 0


@ws_only
def test_decisions_channel_and_resubscribe(tmp_path):
    evs = _events(tmp_path, n=3)
    live = Live()
    got = []
    stop = threading.Event()

    def sub():
        W.subscribe(live.url + "/decisions", got.append, stop=stop, duration_s=20)

    th = threading.Thread(target=sub, daemon=True)
    th.start()
    time.sleep(0.3)
    s = live.run(lambda: W.replay_to_ws(evs, live.url + "/nts", "sim-4", speed=0), max_streams=1)
    time.sleep(0.1)
    stop.set()
    th.join(5)
    assert [e["ws_seq"] for e in got] == [e["ws_seq"] for e in live.out] and len(got) == s.decisions
    assert [e["shown"] for e in got] == [e["shown"] for e in live.out]


@ws_only
def test_resubscribe_replays_from_seq(tmp_path):
    evs = _events(tmp_path, n=3)
    live = Live()
    live.server.stopping.clear()
    th = threading.Thread(target=lambda: W.replay_to_ws(evs, live.url + "/nts", "sim-5", speed=0), daemon=True)
    th.start()
    live.runner.run(duration_s=30, max_streams=1, poll_timeout=0.01)
    th.join(10)
    got = []
    core = W.subscribe(live.url + "/decisions", got.append, from_seq=2, duration_s=1.0)
    live.server.stop()
    assert [e["ws_seq"] for e in got] == list(range(2, len(live.out) + 1)) and core.gaps == []


@ws_only
def test_refused_connections():
    from websockets.exceptions import InvalidStatus
    from websockets.sync.client import connect

    live = Live(token="s3cret")
    try:
        with pytest.raises(W.WSRefused, match="auth"):
            W.WSProducer(live.url + "/nts", HDR, token="wrong").connect()
        p = W.WSProducer(live.url + "/nts", HDR, token="s3cret").connect()
        assert p.welcome["type"] == "ws_welcome"
        p.close(wait_ack_s=0.5)
        with pytest.raises(InvalidStatus):
            connect(live.url + "/nts", open_timeout=5)  # no subprotocol: HTTP 400
        with pytest.raises(InvalidStatus):
            connect(live.url + "/other", subprotocols=[W.SUBPROTOCOL], open_timeout=5)
    finally:
        live.server.stop()


@ws_only
def test_static_example_route(tmp_path):
    (tmp_path / "index.html").write_text("<p>hi</p>", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("no", encoding="utf-8")
    live = Live(static={"/": str(tmp_path)})
    try:
        base = f"http://127.0.0.1:{live.server.port}"
        with urllib.request.urlopen(base + "/") as r:
            assert r.read() == b"<p>hi</p>" and r.headers["Content-Type"].startswith("text/html")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/../secret.txt")
    finally:
        live.server.stop()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@ws_only
def test_cli_run_replay_subscribe(tmp_path, capsys):
    from fidetype.cli import main as cli

    evs = _events(tmp_path, n=2)
    f = tmp_path / "s.jsonl"
    f.write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
    cfg = tmp_path / "cfg.json"
    CFG.save(cfg)
    port = _free_port()
    rc = {}
    th = threading.Thread(target=lambda: rc.setdefault("run", cli(["ws", "run", "--config", str(cfg), "--port", str(port),
                                                                   "--decoder", "greedy", "--max-streams", "1",
                                                                   "--duration", "30", "--summary",
                                                                   str(tmp_path / "sum.json")])), daemon=True)
    th.start()
    url = f"ws://127.0.0.1:{port}"
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    assert cli(["ws", "replay-to-ws", str(f), "--url", url + "/nts", "--speed", "0", "--batch", "16"]) == 0
    th.join(30)
    assert rc["run"] == 0
    ref = replay(evs, StreamingTrustLayer(CFG, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=2)))
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    assert [(e["action"], e["shown"]) for e in lines] == [(d.action.value, list(d.shown)) for d in ref]
    assert json.loads((tmp_path / "sum.json").read_text())["final_decisions"] == sum(d.final for d in ref)


@ws_only
def test_loopback_later_header_in_one_stream(tmp_path):
    """Several NTS streams (header ... end) in one WebSocket stream: a later header is an ordinary event."""
    a, b = _events(tmp_path, n=1, seed=3), _events(tmp_path, n=1, seed=4)
    evs = a + b
    ref = replay(evs, _layer())
    live = Live()
    s = live.run(lambda: W.replay_to_ws(evs, live.url + "/nts", "multi", speed=0), max_streams=2)
    _same(live.runner.kept, ref)
    assert s.rejected_events == 0 and s.ingest["streams"] == 1 and len(ref) == 2
