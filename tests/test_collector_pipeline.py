"""P3-04: collector pipeline integration test and latency budget; P3-02 segmenter and guard; P3-03 os_text stub;
P7-05: the collector consumer against the conformance kit.

The integration tests run a real collector from a TOML file (``fidetype.collector.bench``):
receiver (WebSocket, file; LSL if pylsl is installed) -> validate -> segment -> guard (per-user profile,
online ACI) -> exporters (NTS stream file, decision log, os_text stub, WebSocket /decisions). The outputs
must reach producer level NTS Trust-ready with ``nts-conform``, and the p95 added latency of the gated
profiles must stay below the budget (50 ms) times ``FIDETYPE_LATENCY_TOLERANCE`` (default 1.0).
"""

from __future__ import annotations

import json
import math
import os
import string
from pathlib import Path

import numpy as np
import pytest

from fidetype.collector import bench as B
from fidetype.collector.config import ConfigError, parse
from fidetype.collector.consume import consume, kit_validator
from fidetype.collector.consume import main as consume_main
from fidetype.collector.exporters import OsTextExporter, committed_text
from fidetype.collector.latency import BUDGET_MS, LatencyRecorder, quantiles, trigger_stamps
from fidetype.collector.processors import GuardProcessor, SegmenterProcessor, decision_errors, strip_binding_keys
from fidetype.collector.receivers import FileReceiver, status

ws = pytest.importorskip("websockets")

#: CI tolerance of the latency gate (docs/collector.md, "Latency budget"). 1.0 = the budget itself.
TOLERANCE = float(os.environ.get("FIDETYPE_LATENCY_TOLERANCE", "1.0"))
VOCAB = ["_"] + list(string.ascii_lowercase) + [" "]


def _log(_m: str) -> None:
    pass


def _frame(t: float, top: int, V: int = len(VOCAB)) -> dict:
    row = np.full(V, -6.0)
    row[top] = 0.0
    row -= np.log(np.exp(row).sum())
    return {"type": "frame", "t": t, "log_probs": [float(v) for v in row]}


def _header(**kw) -> dict:
    return {"type": "header", "spec_version": "1.0", "vocab": VOCAB, "vocab_type": "char", "blank_id": 0,
            "source": "test", "meta": {}, **kw}


# --- segmenter ------------------------------------------------------------------------------------


def test_segmenter_cuts_on_blank_run_pause_length_and_end():
    seg = SegmenterProcessor("seg", _log, blank_frames=3, pause_s=0.5, max_frames=10)
    items = [("s", _header())]
    t = 0.0
    for top in [1, 0, 2, 0, 0, 0, 0, 3]:  # a, blank, b, 4 blanks (cut after 3), c
        items.append(("s", {**_frame(t, top), "ws_t_recv": 100.0 + t}))
        t += 0.02
    items.append(("s", _frame(t + 1.0, 4)))  # a pause > 0.5 s: cut before this frame
    items += [("s", _frame(t + 1.02 + 0.02 * i, 5)) for i in range(10)]  # 11 frames since the cut: length cut
    items.append(("s", {"type": "end"}))
    out = [ev for _, ev in seg.process(items)]
    ends = [ev for ev in out if ev["type"] == "segment_end"]
    reasons = [e["reason"] for e in ends]
    assert reasons[0] == "segmenter: 3 blank frames" and ends[0]["t"] == pytest.approx(0.1)
    assert ends[0]["ws_t_recv"] == pytest.approx(100.1)  # the stamps of the frame that caused the cut
    assert reasons[1].startswith("segmenter: pause") and ends[1]["t"] == pytest.approx(0.14)
    assert reasons[2] == "segmenter: 10 frames"
    assert reasons[3] == "segmenter: end of stream" and out[-1]["type"] == "end"
    assert seg.stats()["added_boundaries"] == 4


def test_segmenter_keeps_source_boundaries_and_resets_on_gap():
    seg = SegmenterProcessor("seg", _log, blank_frames=2)
    items = [("s", _header()), ("s", _frame(0.0, 1)), ("s", _frame(0.02, 0)), status("s", "gap"),
             ("s", _frame(0.04, 0)), ("s", _frame(0.06, 1)), ("s", {"type": "segment_end", "t": 0.06}),
             ("s", _frame(0.08, 0)), ("s", _frame(0.1, 0))]
    out = [ev for _, ev in seg.process(items)]
    assert [e.get("reason") for e in out if e["type"] == "segment_end"] == [None]  # blanks only: no cut
    assert seg.stats()["source_boundaries"] == 1


def test_strip_binding_keys():
    ev = {"type": "header", "ws": {"binding": "nts-ws/0.1"}, "ws_seq": 1, "ws_t_recv": 2.0, "vocab": ["a"]}
    assert strip_binding_keys(ev) == {"type": "header", "vocab": ["a"]}
    plain = {"type": "frame", "t": 0.0}
    assert strip_binding_keys(plain) is plain


# --- guard processor ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def implant_profile(tmp_path_factory) -> Path:
    return B.write_profile("implant-speech", tmp_path_factory.mktemp("prof") / "profile.json")


def _nbest_stream(texts: list[str], gap_after: int | None = None) -> list:
    rng = np.random.default_rng(0)
    items = [("u", {**_header(), "ws": {"binding": "nts-ws/0.1"}})]
    for i, t in enumerate(texts):
        items.append(("u", {**_frame(0.1 * i, 1), "ws_seq": i}))
        items.append(("u", {"type": "hypothesis", "id": f"h{i}", "is_final": True, "score_semantics": "none",
                            "nbest": B.implant_nbest(t, rng)}))
        if gap_after == i:
            items.append(status("u", "gap", "test"))
        items.append(("u", {"type": "segment_end", "t": 0.1 * i}))
    items += [("u", {"type": "end"}), status("u", "closed")]
    return items


@pytest.mark.parametrize("online", [None, "aci"])
def test_guard_processor_profile_decisions_are_valid(implant_profile, online):
    g = GuardProcessor("guard", _log, profile_path=implant_profile, online=online, passthrough=True)
    texts = ["yes please", "thank you", "i need help", "good morning"]
    out = g.process(_nbest_stream(texts, gap_after=1))
    decs = [ev for _, ev in out if ev["type"] == "trust_decision"]
    # utterance 1 is cut by the gap: no decision for it, and the next segment_end only closes the skip
    assert [d["utterance"] for d in decs] == [0, 2, 3] and [d["seq"] for d in decs] == [0, 1, 2]
    for d in decs:
        assert d["spec_version"] == "1.0" and d["is_final"] is True and d["session"] == "u"
        assert d["config_id"] == g.config_id
        assert decision_errors(d) == []
    passed = [ev for _, ev in out if ev["type"] != "trust_decision"]
    assert passed[0]["type"] == "header" and not any(k == "ws" or k.startswith("ws_") for e in passed for k in e)
    st = g.stats()
    assert st["profile"] is True and st["online"] == online and st["aborted_segments"] == 1
    for d in decs:  # the feedback path (online controller and the profile's drift tests)
        g.feedback("u", d["utterance"], texts[d["utterance"]])
    assert g.personal.monitor is not None


def test_guard_processor_refuses_a_wrong_vocabulary(tmp_path):
    prof = B.write_profile("emg-key", tmp_path / "p.json")
    g = GuardProcessor("guard", _log, profile_path=prof)
    items = [("k", _header(vocab_type="key", blank_id=None)), ("k", _frame(0.0, 1)),
             ("k", {"type": "segment_end"})]
    assert g.process(items) == [] and g.stats()["unusable_segments"] == 1


def test_guard_config_rules(tmp_path):
    base = {"receivers": {"in": {"type": "file", "paths": ["x.jsonl"]}},
            "exporters": {"out": {"type": "os_text"}},
            "pipelines": {"main": {"receivers": ["in"], "processors": ["g"], "exporters": ["out"]}}}

    def cfg(procs, order=None):
        d = json.loads(json.dumps(base))
        d["processors"] = procs
        d["pipelines"]["main"]["processors"] = order or list(procs)
        return d

    with pytest.raises(ConfigError, match="exactly one of 'guard'"):
        parse(cfg({"g": {"type": "guard"}}))
    with pytest.raises(ConfigError, match="exactly one of 'guard'"):
        parse(cfg({"g": {"type": "guard", "guard": "a.json", "profile": "b.json"}}))
    with pytest.raises(ConfigError, match="online"):
        parse(cfg({"g": {"type": "guard", "guard": "a.json", "online": "magic"}}))
    with pytest.raises(ConfigError, match="segment"):
        parse(cfg({"g": {"type": "guard", "guard": "a.json"}, "s": {"type": "segment", "max_frames": 5}}))
    with pytest.raises(ConfigError, match="at least one of"):
        parse(cfg({"g": {"type": "segment"}}))
    with pytest.raises(ConfigError, match="at most one trust step"):
        parse(cfg({"g": {"type": "guard", "guard": "a.json"}, "t": {"type": "trust", "config": "c.json"}}))
    with pytest.raises(ConfigError, match="redact"):
        parse(cfg({"r": {"type": "redact"}, "g": {"type": "guard", "guard": "a.json"}}))
    with pytest.raises(ConfigError, match="backend"):
        d = cfg({"g": {"type": "segment", "max_frames": 5}})
        d["exporters"]["out"]["backend"] = "windows-tsf"
        parse(d)
    with pytest.raises(ConfigError, match="latency"):
        d = cfg({"g": {"type": "segment", "max_frames": 5}})
        d["service"] = {"latency": "yes"}
        parse(d)
    ok = cfg({"s": {"type": "segment", "blank_frames": 4}, "g": {"type": "guard", "profile": "p.json",
                                                                  "online": "aci", "passthrough": True}})
    assert parse(ok).processors["g"].type == "guard"


# --- os_text stub -----------------------------------------------------------------------------------


def test_os_text_types_only_final_commits(tmp_path):
    ex = OsTextExporter("typing", _log, path=tmp_path / "typed.jsonl")
    ex.start()
    base = {"type": "trust_decision", "spec_version": "1.0", "session": "s", "utterance": 0}
    items = [("s", {**base, "seq": 0, "is_final": False, "action": "COMMIT", "shown": ["provisional"]}),
             ("s", {**base, "seq": 1, "is_final": True, "action": "OFFER", "shown": ["a", "b"]}),
             ("s", {**base, "seq": 2, "is_final": True, "action": "COMMIT", "shown": ["  "]}),
             ("s", {**base, "seq": 3, "is_final": True, "action": "COMMIT", "shown": ["hello"]}),
             ("s", {**base, "seq": 4, "is_final": True, "action": "COMMIT", "shown": ["world"]}),
             ("s", {"type": "frame", "t": 0.0})]
    ex.export(items)
    ex.stop()
    assert ex.typed == ["hello", "world"] and ex.stats()["not_committed"] == 3
    lines = [json.loads(x) for x in (tmp_path / "typed.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["typed"] for x in lines] == ["hello", " world"] and lines[1]["decision"]["seq"] == 4
    assert committed_text({"type": "trust_decision", "is_final": True, "action": "COMMIT", "profile": "intent",
                           "shown": ["x"]}) is None
    with pytest.raises(ValueError, match="not implemented"):
        OsTextExporter("x", _log, backend="windows-tsf")


# --- latency helpers --------------------------------------------------------------------------------


def test_latency_recorder_and_trigger_stamps():
    assert quantiles([])["p95"] is None
    q = quantiles([1.0] * 99 + [100.0])
    assert q["n"] == 100 and q["p50"] == 1.0 and q["max"] == 100.0
    items = [("s", {"type": "frame", "ws_t_recv": 1.0, "ws_t_sent": 0.9}),
             ("s", {"type": "segment_end", "ws_t_recv": 2.0, "ws_t_sent": 1.95}),
             ("s", {"type": "frame", "ws_t_recv": 3.0})]
    assert trigger_stamps(items) == (2.0, 1.95)
    assert trigger_stamps(items[2:]) == (3.0, None)
    assert trigger_stamps([("s", {"type": "frame"})]) == (None, None)
    rec = LatencyRecorder(maxlen=3)
    for v in (0.001, 0.002, 0.003, 0.004):
        rec.add("added", v)
    s = rec.summary()
    assert s["stages"]["added"]["n"] == 3 and s["within_budget"] is True


# --- NPZ input and the consumer (P7-05) ---------------------------------------------------------


def test_file_receiver_reads_npz_and_refuses_pickles():
    kit = Path(__file__).resolve().parents[1] / "spec" / "conformance" / "kit" / "v0.1"
    r = FileReceiver("f", [kit / "k03-frames.npz", kit / "k05-npz-pickled.npz"], _log)
    r.start()
    items = []
    while not r.done:
        items += r.poll(0.0)
    evs0 = [ev for sid, ev in items if sid == "f-0"]
    assert evs0[0]["type"] == "header" and evs0[-2]["type"] == "end" and evs0[-1]["status"] == "closed"
    assert sum(ev["type"] == "frame" for ev in evs0) > 0
    evs1 = [ev for sid, ev in items if sid == "f-1"]
    assert evs1[0]["status"] == "lost" and evs1[-1]["status"] == "closed"


def test_collector_consumer_reaches_trust_ready_on_the_kit_for_text():
    from fidetype.conformance.nts_conform import _impl_validator, run_kit

    rep = run_kit(validator=_impl_validator("fidetype.collector.consume:kit_validator"),
                  name="collector", claim=["text"])
    lv = rep["level"]
    assert lv["levels"]["trust-ready"] is True, lv
    wrong = {e["id"] for e in rep["entries"] if not e["ok"]}
    # out of scope (documented): intent / control profiles and the LSL / WebSocket captures
    assert wrong <= {"K19", "K21", "K23", "K25", "K26", "K28", "K29", "K31"}, wrong


def test_consume_cli_exit_codes(capsys):
    kit = Path(__file__).resolve().parents[1] / "spec" / "conformance" / "kit"
    assert consume_main([str(kit / "v0.1" / "k01-text-stream.jsonl"), "--level", "provenance", "-q"]) == 0
    assert consume_main([str(kit / "v0.1" / "k33-core-only.jsonl"), "--level", "trust-ready"]) == 1
    assert "reject" in capsys.readouterr().out
    assert consume_main([str(kit / "missing.jsonl")]) == 2
    assert consume(kit / "fep-0003" / "k19-intent-stream.jsonl", "fep-0003")[0].startswith("profile fep-0003")
    with pytest.raises(ValueError):
        kit_validator(kit / "fep-0001" / "k17-commit-empty-shown.jsonl", "fep-0001")


# --- integration runs (P3-04) -----------------------------------------------------------------------


def _check_run(r: dict, gated: bool) -> None:
    assert r["producer_errors"] == []
    assert r["stop_reason"] in ("max_streams", "input done")  # LSL: stop_at_end ends the receiver
    conf = r["conformance"]
    assert conf["producer_level"] == "trust-ready", conf
    assert all(t["verdict"] != "fail" for t in conf["targets"]), conf
    assert r["decisions"] >= r["segments"] - 1  # one decision per segment (a noisy segment can split or merge)
    assert r["typed_only_commits"] is True and r["typed"] == r["committed"]
    lat = r["latency_ms"]
    added = lat["stages"]["added"]
    assert added["n"] >= r["segments"] - 1
    for k in ("processor.check", "processor.seg", "processor.guard", "exporter.nts", "exporter.log",
              "exporter.typing", "pipeline"):
        assert lat["stages"][k]["n"] > 0, k
    if gated:
        assert added["p95"] < BUDGET_MS * TOLERANCE, (
            f"{r['profile']}/{r['receiver']}: p95 added latency {added['p95']} ms >= budget "
            f"{BUDGET_MS} ms x tolerance {TOLERANCE}")


@pytest.mark.parametrize("profile", B.GATED_PROFILES)
def test_pipeline_websocket_at_50_hz_within_budget(tmp_path, profile):
    r = B.run(profile, "websocket", tmp_path, n_utterances=8).report
    _check_run(r, gated=True)
    assert r["latency_ms"]["stages"]["e2e"]["n"] > 0 and r["latency_ms"]["stages"]["receive"]["n"] > 0
    metrics = json.loads((tmp_path / f"{profile}-websocket" / "metrics.json").read_text(encoding="utf-8"))
    assert "latency_ms" in metrics["pipelines"]["main"]


def test_pipeline_file_input(tmp_path):
    r = B.run("implant-speech", "file", tmp_path, n_utterances=6).report
    _check_run(r, gated=True)
    stream = (tmp_path / "implant-speech-file" / "out" / "stream.nts.jsonl").read_text(encoding="utf-8")
    assert "ws_" not in stream and "segmenter: 6 blank frames" in stream


def test_pipeline_lsl_input(tmp_path):
    from fidetype.adapters.lsl import pylsl_available

    if not pylsl_available():
        pytest.skip("pylsl is not installed (extra 'lsl')")
    r = B.run("emg-key", "lsl", tmp_path, n_utterances=6).report
    _check_run(r, gated=True)


def test_pipeline_logits_guard_is_reported(tmp_path):
    """implant-logits: the guard's own CTC beam search runs in the collector. Checked, reported, not gated."""
    r = B.run("implant-logits", "file", tmp_path, n_utterances=4).report
    _check_run(r, gated=False)
    assert math.isfinite(r["latency_ms"]["stages"]["processor.guard"]["p95"])
