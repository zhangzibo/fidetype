"""Tests of ``fidetype live --publish`` (roadmap P14-16).

Unit tests use no network. The WebSocket end-to-end tests bind 127.0.0.1 only and need no
hardware. The LSL end-to-end test runs a real pylsl loopback and skips without pylsl (CI job
``live``). The end-to-end tests run the CLI in a child process and record it with
``nts-conform capture`` (:mod:`fidetype.conformance.binding_producers`).
"""

from __future__ import annotations

import json
import socket

import pytest

from fidetype.adapters import lsl as L
from fidetype.adapters import ws as W
from fidetype.conformance import nts_conform as NC
from fidetype.live import publish as P
from fidetype.live.__main__ import main as live_main

ws_only = pytest.mark.skipif(not W.websockets_available(), reason="websockets not available")
lsl_only = pytest.mark.skipif(not L.pylsl_available(), reason="pylsl / liblsl not available")


# --- unit tests (no network) ----------------------------------------------------------------------


def test_parse_target():
    assert P.parse_target("lsl") == ("lsl", "fidetype.live")
    assert P.parse_target("lsl:my.stream") == ("lsl", "my.stream")
    assert P.parse_target("ws://127.0.0.1:8765/nts") == ("ws-nts", "ws://127.0.0.1:8765/nts")
    assert P.parse_target("ws://127.0.0.1:0/decisions") == ("ws-decisions", "ws://127.0.0.1:0/decisions")
    for bad in ("lsl:", "udp://x:1", "ws://127.0.0.1:8765/events", "ws://127.0.0.1/decisions",
                "wss://127.0.0.1:1/decisions", "ws://127.0.0.1:x/nts"):
        with pytest.raises(ValueError):
            P.parse_target(bad)


class _Rec:
    def __init__(self, target, fail_on=None):
        self.target, self.fail_on, self.events, self.sent, self.closed = target, fail_on, [], 0, False

    def event(self, ev):
        if ev.get("type") == self.fail_on:
            raise OSError("gone")
        self.events.append(ev)
        self.sent += 1

    def wait(self, timeout):
        return True

    def close(self):
        self.closed = True


def test_event_tee_copies_and_isolates_failures(tmp_path):
    ok, bad, logs = _Rec("ok"), _Rec("bad", fail_on="frame"), []
    f = (tmp_path / "out.jsonl").open("w", encoding="utf-8", newline="\n")
    d = (tmp_path / "out.decisions.jsonl").open("w", encoding="utf-8", newline="\n")
    tee = P.EventTee([ok, bad], f, log=logs.append, decisions_file=d)
    tee.write(json.dumps({"type": "header"}) + "\n")
    tee.write(json.dumps({"type": "frame", "t": 0.0}) + "\n")
    tee.write('{"type": "trust_decision", "is_final": true}\n{"type": "en')  # a line in two writes
    tee.write('d"}\n')
    assert [e["type"] for e in ok.events] == ["header", "frame", "trust_decision", "end"]
    assert bad.closed and [e["type"] for e in bad.events] == ["header"] and len(logs) == 1
    out = tee.finish()
    assert out["ok"] == {"sent": 4} and "OSError" in out["bad"]["failed"]
    # P14-17: the stream file has no trust_decision (TD-4); the decision log has only decisions
    lines = (tmp_path / "out.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["type"] for x in lines] == ["header", "frame", "end"]
    dl = (tmp_path / "out.decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["type"] for x in dl] == ["trust_decision"] and tee.decisions == 1


def test_bad_publish_target_exits_2(capsys):
    assert live_main(["--source", "synthetic", "--speed", "0", "--utterances", "1", "--publish", "udp://x:1"]) == 2
    assert "unknown --publish target" in capsys.readouterr().err


# --- WebSocket (127.0.0.1, no hardware) -----------------------------------------------------------


def _closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@ws_only
def test_unreachable_server_does_not_stop_the_decode(tmp_path, capsys):
    out, summ = tmp_path / "s.nts.jsonl", tmp_path / "summary.json"
    rc = live_main(["--source", "synthetic", "--speed", "0", "--utterances", "2", "--out", str(out),
                    "--summary", str(summ), "--publish", f"ws://127.0.0.1:{_closed_port()}/nts",
                    "--publish-linger", "0"])
    assert rc == 0
    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["type"] == "header" and lines[-1]["type"] == "end"
    assert not any(e["type"] == "trust_decision" for e in lines)  # P14-17: decisions in the decision log
    dlog = tmp_path / "s.nts.decisions.jsonl"
    assert [json.loads(x)["type"] for x in dlog.read_text(encoding="utf-8").splitlines()] == ["trust_decision"] * 2
    pub = json.loads(summ.read_text(encoding="utf-8"))["published"]
    assert list(pub.values())[0]["failed"]
    assert "the decode goes on" in capsys.readouterr().err


@ws_only
def test_live_ws_binding_evidence(tmp_path):
    from fidetype.conformance.binding_producers import write_evidence

    files = write_evidence("live-ws", tmp_path, timeout=30.0)
    rep = NC.build_report([NC.conform_file(f) for f in files], "core")
    assert rep["ok"], [t["target"] for t in rep["targets"] if not t["ok"]]
    assert rep["producer"]["level"] == "trust-ready" and rep["producer"]["bindings"] == ["nts-ws/0.1"]
    stream = [json.loads(x) for x in files[1].read_text(encoding="utf-8").splitlines()]
    types = [e["type"] for e in stream]
    assert types[0] == "header" and types[-1] == "end" and "frame" in types
    assert "trust_decision" not in types  # FEP-0001 section 3 r4: decisions go on /decisions only
    assert stream[0]["meta"]["adapter.name"] == "fidetype.live"
    decisions = [json.loads(x) for x in files[3].read_text(encoding="utf-8").splitlines()]
    assert len(decisions) == 4 and all(d["is_final"] for d in decisions)
    sub = json.loads(files[2].read_text(encoding="utf-8"))
    assert sub["messages"][0]["type"] == "ws_welcome" and sub["messages"][0]["config_id"] == decisions[0]["config_id"]


# --- LSL (real pylsl loopback; skips without pylsl) -----------------------------------------------


@lsl_only
def test_live_lsl_binding_evidence(tmp_path):
    from fidetype.conformance.binding_producers import write_evidence

    files = write_evidence("live-lsl", tmp_path, timeout=30.0)
    rep = NC.build_report([NC.conform_file(f) for f in files], "core")
    assert rep["ok"], [t["target"] for t in rep["targets"] if not t["ok"]]
    assert rep["producer"]["level"] == "trust-ready" and rep["producer"]["bindings"] == ["nts-lsl/0.1"]
    cap = json.loads(files[0].read_text(encoding="utf-8"))
    assert set(cap["inlets"]) == {"primary", "events"}
    stream = [json.loads(x) for x in files[1].read_text(encoding="utf-8").splitlines()]
    assert "trust_decision" not in [e["type"] for e in stream] and stream[-1]["type"] == "end"
    dec = json.loads(files[2].read_text(encoding="utf-8"))
    assert dec["kind"] == "decisions" and len(dec["samples"]) == 4
