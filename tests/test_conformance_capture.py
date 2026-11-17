"""Tests of ``nts-conform capture`` and the binding producer evidence (roadmap P7-06).

Unit tests use no network. The WebSocket end-to-end tests bind 127.0.0.1 only. The LSL
end-to-end test runs a real pylsl loopback and skips without pylsl (CI job ``live``).
"""

from __future__ import annotations

import json
import socket
import threading
import time

import pytest

from fidetype.adapters import lsl as L
from fidetype.adapters import ws as W
from fidetype.conformance import capture as C
from fidetype.conformance import nts_conform as NC
from fidetype.conformance.kit import kit_dir

ws_only = pytest.mark.skipif(not W.websockets_available(), reason="websockets not available")
lsl_only = pytest.mark.skipif(not L.pylsl_available(), reason="pylsl / liblsl not available")


def _kit(name):
    return json.loads((kit_dir() / name).read_text(encoding="utf-8"))


# --- unit tests (no network) ----------------------------------------------------------------------


def test_parse_query():
    assert C.parse_query("fidetype.nts") == {"name": "fidetype.nts"}
    assert C.parse_query("type=NTS, source_id=abc") == {"type": "NTS", "source_id": "abc"}
    with pytest.raises(ValueError):
        C.parse_query("host=x")
    with pytest.raises(ValueError):
        C.parse_query("type=")


def test_sanitize_info_xml_drops_host_fields():
    xml = ("<info><name>n</name><type>NTS</type><channel_count>2</channel_count><channel_format>float32"
           "</channel_format><source_id>s</source_id><nominal_srate>25</nominal_srate><created_at>123.4</created_at>"
           "<uid>abc-uid</uid><session_id>default</session_id><hostname>my-laptop</hostname>"
           "<v4address>192.168.1.7</v4address><desc><channels><channel><label>a</label></channel></channels>"
           "<fidetype><binding>nts-lsl/0.1</binding></fidetype></desc></info>")
    out = C.sanitize_info_xml(xml)
    for secret in ("my-laptop", "192.168.1.7", "abc-uid", "123.4"):
        assert secret not in out
    info = L.LSLStreamInfo.from_xml(out)
    assert (info.name, info.channel_count, info.nominal_srate, info.channel_labels) == ("n", 2, 25.0, ["a"])
    assert info.fidetype == {"binding": "nts-lsl/0.1"}


def test_recording_core_records_steps_and_never_a_token():
    rec = C._RecordingCore(W.IngestCore())
    rec.open(1, ["nts-ws.0.1"], "Bearer secret-token", 10.0)
    hdr = {**W.json.loads(W.dumps({"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a"],
                                   "vocab_type": "char", "blank_id": 0, "source": "t", "frame_period": 0.04})),
           "ws": {"binding": "nts-ws/0.1", "stream_id": "x"}}
    rec.message(1, W.dumps(hdr), 10.1)
    rec.message(1, '{"type": "ws_auth", "token": "secret-token"}', 10.2)
    rec.message(1, "not json", 10.3)
    rec.message(1, b"\x01", 10.4)
    rec.message(1, W.dumps({"type": "end", "ws_seq": 1}), 10.5)
    rec.disconnect(1, 10.6)
    steps = rec.steps
    assert "secret-token" not in json.dumps(steps)
    assert [next(k for k in ("open", "msg", "raw", "binary", "close") if k in s) for s in steps] == \
        ["open", "msg", "msg", "raw", "binary", "msg", "close"]
    assert steps[0]["at"] == 0.0 and steps[-1]["at"] == pytest.approx(0.6)
    assert all(a["at"] <= b["at"] for a, b in zip(steps, steps[1:]))
    assert rec.saw_end and rec.closed == 1


@pytest.mark.parametrize("name,kind,first", [("fep-0002/k26-lsl-capture.json", "inlet", "header"),
                                             ("fep-0002/k28-lsl-decisions.json", "decisions", "trust_decision"),
                                             ("fep-0004/k29-ws-session.json", "ingest", "header"),
                                             ("fep-0004/k31-ws-decisions.json", "subscribe", "trust_decision")])
def test_received_of_the_kit_captures(tmp_path, name, kind, first):
    sc = _kit(name)
    assert sc["kind"] == kind
    evs = C.received(sc)
    assert evs and evs[0]["type"] == first
    if first == "header":
        assert sum(e["type"] == "frame" for e in evs) == 6
    out = C.write_received(sc, tmp_path / "r.jsonl")
    form, _ = NC.detect(out)
    assert form == ("jsonl-stream" if first == "header" else "jsonl-decision-log")
    assert NC.conform_file(out).ok_core


def test_received_refuses_other_json():
    with pytest.raises(ValueError):
        C.received({"schema": "x", "kind": "inlet"})


def test_cli_usage_errors(capsys):
    assert NC.main(["capture", "--ws", "http://127.0.0.1:1/nts", "--out", "x.json"]) == 2
    assert NC.main(["capture", "--ws", "ws://127.0.0.1:1/other", "--out", "x.json"]) == 2
    assert NC.main(["capture", "--lsl", "host=x", "--out", "x.json"]) == 2
    assert "capture:" in capsys.readouterr().err


# --- WebSocket end to end (127.0.0.1) -------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@ws_only
def test_cli_records_a_ws_producer(tmp_path, capsys):
    from fidetype.conformance.binding_producers import source_events

    port = _free_port()
    out, rcv = tmp_path / "ws.json", tmp_path / "ws.received.jsonl"
    res = {}
    th = threading.Thread(target=lambda: res.update(rc=NC.main(
        ["capture", "--ws", f"ws://127.0.0.1:{port}/nts", "--seconds", "20", "--out", str(out),
         "--received", str(rcv)])), daemon=True)
    th.start()
    evs = source_events()
    for _ in range(100):  # wait for the recording server
        try:
            W.replay_to_ws(evs, f"ws://127.0.0.1:{port}/nts", stream_id="cli", speed=0.0)
            break
        except (OSError, W.WSRefused):
            time.sleep(0.05)
    th.join(20)
    assert res.get("rc") == 0
    sc = json.loads(out.read_text(encoding="utf-8"))
    assert sc["schema"] == C.WS_SCHEMA and sc["kind"] == "ingest"
    assert NC.main(["check", str(out), str(rcv), "--require-level", "trust-ready"]) == 0
    assert "bindings nts-ws/0.1" in capsys.readouterr().out


@ws_only
def test_ws_binding_evidence(tmp_path):
    from fidetype.conformance.binding_producers import write_evidence

    files = write_evidence("ws", tmp_path)
    assert [f.name for f in files] == ["ws-ingest.capture.json", "ws-ingest.received.jsonl",
                                       "ws-decisions.capture.json", "ws-decisions.received.jsonl"]
    rep = NC.build_report([NC.conform_file(f) for f in files], "core")
    assert rep["ok"], [t["target"] for t in rep["targets"] if not t["ok"]]
    assert rep["producer"]["level"] == "trust-ready" and rep["producer"]["bindings"] == ["nts-ws/0.1"]
    sub = json.loads(files[2].read_text(encoding="utf-8"))
    assert sub["messages"][0]["type"] == "ws_welcome"
    assert sum(m["type"] == "trust_decision" and m["is_final"] for m in sub["messages"]) == 2  # two utterances


# --- LSL end to end (real pylsl loopback) ---------------------------------------------------------


@lsl_only
def test_lsl_binding_evidence(tmp_path):
    from fidetype.conformance.binding_producers import write_evidence

    files = write_evidence("lsl", tmp_path)
    rep = NC.build_report([NC.conform_file(f) for f in files], "core")
    assert rep["ok"], [t["target"] for t in rep["targets"] if not t["ok"]]
    assert rep["producer"]["level"] == "trust-ready" and rep["producer"]["bindings"] == ["nts-lsl/0.1"]
    cap = json.loads(files[0].read_text(encoding="utf-8"))
    assert set(cap["inlets"]) == {"primary", "events"}
    assert sum(len(c["samples"]) for c in cap["inlets"]["primary"]["chunks"]) == 40
    assert "<hostname />" in cap["inlets"]["primary"]["info_xml"]
    dec = json.loads(files[2].read_text(encoding="utf-8"))
    assert dec["kind"] == "decisions" and len(dec["samples"]) == len(dec["timestamps"]) >= 2
