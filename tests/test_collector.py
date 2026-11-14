"""P3: the collector v0 (FEP-0006): config, file -> validate -> trust -> redact -> jsonl, loss rules, WebSocket.

Synthetic simulator streams and hand-made frames only; no participant data.
The WebSocket tests run a real server on localhost (port 0) and are skipped
when ``websockets`` is not installed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import threading
import time
import urllib.error
import urllib.request

import pytest

from fidetype.adapters import ws as W
from fidetype.collector import Collector, ConfigError, load, parse
from fidetype.conformance.io import write_jsonl
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events, replay
from fidetype.trust.testing import greedy_nbest

CFG = FrozenTrustConfig(name="collector-test").with_policy(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)
#: The collector adds the commit gate (no blank COMMIT, TD-9) because it stamps spec_version "1.0".
CFG_GATED = CFG.with_commit_gate(min_chars=1)
LP = [math.log(0.9), math.log(0.07), math.log(0.03)]
HDR = {"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a", "b"], "vocab_type": "char", "blank_id": 0,
       "source": "t", "frame_period": 0.04, "meta": {"data.derived": True}}
ws_only = pytest.mark.skipif(not W.websockets_available(), reason="websockets not installed (pip install fidetype[ws])")


def _sim_events(tmp_path, n=4, seed=3):
    """One synthetic stream: n simulator utterances with segment_end between them, then end."""
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


def _frames(k0, n):
    return [{"type": "frame", "t": round((k0 + i) * 0.04, 6), "log_probs": LP} for i in range(n)]


def _write(path, events, raw_lines=()):
    """Write events as JSON Lines; ``raw_lines`` = {index: text} inserts raw text before event ``index``."""
    raw = dict(raw_lines)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for i, ev in enumerate(events):
            if i in raw:
                f.write(raw[i] + "\n")
            f.write(json.dumps(ev) + "\n")


def _config(tmp_path, inputs, processors=("check", "trust"), extra_proc=None, exporters=None, receiver=None,
            service=None):
    CFG.save(tmp_path / "trust.json")
    procs = {"check": {"type": "validate"},
             "trust": {"type": "trust", "config": "trust.json", "decoder": "greedy", "max_attempts": 1}}
    procs.update(extra_proc or {})
    return {
        "service": {"log": "quiet", **(service or {})},
        "receivers": {"in": receiver or {"type": "file", "paths": [str(p) for p in inputs]}},
        "processors": {k: procs[k] for k in processors},
        "exporters": exporters or {"log": {"type": "jsonl", "path": "out/decisions.jsonl"}},
        "pipelines": {"main": {"receivers": ["in"], "processors": list(processors),
                               "exporters": list((exporters or {"log": 0}).keys())}},
    }


def _run(tmp_path, d):
    col = Collector(parse(d, base_dir=tmp_path))
    col.run()
    return col


def _decisions(tmp_path, name="out/decisions.jsonl"):
    return [json.loads(x) for x in (tmp_path / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def _reference(events):
    layer = StreamingTrustLayer(CFG_GATED, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=1))
    return replay(events, layer, session_id="in-0")


# --- end to end ------------------------------------------------------------------------------


def test_file_trust_jsonl_matches_reference(tmp_path):
    evs = _sim_events(tmp_path)
    _write(tmp_path / "s.jsonl", evs)
    col = _run(tmp_path, _config(tmp_path, [tmp_path / "s.jsonl"]))
    got = _decisions(tmp_path)
    ref = [d.to_event() for d in _reference(evs)]
    assert len(got) == len(ref) == 4
    for g, r in zip(got, ref):
        for k in ("session", "seq", "utterance", "is_final", "action", "shown", "p_top1", "config_id", "input"):
            assert g[k] == r[k], k
        assert "ws" not in g  # a file stream has no WebSocket record
    m = col.metrics()["pipelines"]["main"]
    assert m["processors"]["check"]["invalid_events"] == 0
    assert m["processors"]["trust"]["final_decisions"] == 4
    assert col.state == "stopped"


def test_example_config_runs(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    cfg = load(root / "examples" / "collector" / "collector.toml")
    # write the outputs to tmp_path, not into the repository
    cfg.service["metrics_file"] = str(tmp_path / "metrics.json")
    cfg.service["log"] = "quiet"
    cfg.exporters["log"].options["path"] = str(tmp_path / "decisions.jsonl")
    cfg.pipelines["main"].exporters = ["log"]
    Collector(cfg).run()
    got = _decisions(tmp_path, "decisions.jsonl")
    assert got and all(d["type"] == "trust_decision" and "shown" not in d for d in got)
    assert json.loads((tmp_path / "metrics.json").read_text())["state"] == "stopped"


def test_two_files_two_streams_and_stdout(tmp_path, capsys):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write(a, [HDR, *_frames(0, 5), {"type": "end"}])
    _write(b, [HDR, *_frames(0, 3), {"type": "end"}])
    d = _config(tmp_path, [a, b], exporters={"out": {"type": "stdout"}})
    _run(tmp_path, d)
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [x["session"] for x in lines] == ["in-0", "in-1"]
    assert all(x["is_final"] for x in lines)


# --- privacy -----------------------------------------------------------------------------------


def test_redact_drop_removes_all_text(tmp_path):
    evs = _sim_events(tmp_path)
    _write(tmp_path / "s.jsonl", evs)
    ref = [d.to_event() for d in _reference(evs)]
    texts = {t for r in ref for t in r["shown"] if len(t) >= 3}
    assert texts  # the test means something only if there is text to remove
    d = _config(tmp_path, [tmp_path / "s.jsonl"], processors=("check", "trust", "privacy"),
                extra_proc={"privacy": {"type": "redact"}})
    _run(tmp_path, d)
    body = (tmp_path / "out" / "decisions.jsonl").read_text(encoding="utf-8")
    got = [json.loads(x) for x in body.splitlines()]
    assert len(got) == len(ref)
    assert all("shown" not in g and g["redaction"] == {"mode": "drop"} for g in got)
    for t in texts:
        assert t not in body


def test_redact_hmac_keeps_checkable_hash_not_text_or_key(tmp_path, monkeypatch):
    key = "unit-test-key-0123456789"
    monkeypatch.setenv("FT_TEST_REDACT_KEY", key)
    evs = _sim_events(tmp_path, n=2)
    _write(tmp_path / "s.jsonl", evs)
    ref = [d.to_event() for d in _reference(evs)]
    d = _config(tmp_path, [tmp_path / "s.jsonl"], processors=("check", "trust", "privacy"),
                extra_proc={"privacy": {"type": "redact", "mode": "hmac", "key_env": "FT_TEST_REDACT_KEY",
                                        "key_id": "k1"}})
    _run(tmp_path, d)
    body = (tmp_path / "out" / "decisions.jsonl").read_text(encoding="utf-8")
    got = [json.loads(x) for x in body.splitlines()]
    assert key not in body
    for g, r in zip(got, ref):
        assert "shown" not in g
        assert g["redaction"] == {"mode": "hmac-sha256", "key_id": "k1"}
        assert g["shown_hmac"] == [hmac.new(key.encode(), t.encode(), hashlib.sha256).hexdigest() for t in r["shown"]]


def test_redact_hmac_without_key_is_a_config_error(tmp_path, monkeypatch):
    monkeypatch.delenv("FT_MISSING_KEY", raising=False)
    d = _config(tmp_path, [tmp_path / "s.jsonl"], processors=("trust", "privacy"),
                extra_proc={"privacy": {"type": "redact", "mode": "hmac", "key_env": "FT_MISSING_KEY"}})
    _write(tmp_path / "s.jsonl", [HDR])
    with pytest.raises(ConfigError, match="FT_MISSING_KEY"):
        Collector(parse(d, base_dir=tmp_path))


# --- loss rules: never a final decision on a cut segment ---------------------------------------


def test_unreadable_line_cuts_the_utterance(tmp_path):
    seg = {"type": "segment_end"}
    evs = [HDR, *_frames(0, 5), seg, *_frames(10, 5), *_frames(15, 5), seg, *_frames(30, 5), {"type": "end"}]
    # a broken line inside utterance 1 (before event index 12: between its two frame runs)
    _write(tmp_path / "s.jsonl", evs, raw_lines={12: '{"type": "frame", "t": 0.5, "log_pro'})
    col = _run(tmp_path, _config(tmp_path, [tmp_path / "s.jsonl"]))
    got = _decisions(tmp_path)
    finals = [g for g in got if g["is_final"]]
    assert [g["input"]["t_range"][0] for g in finals] == [0.0, 1.2]  # utterances 0 and 2; utterance 1 is cut
    st = col.metrics()["pipelines"]["main"]
    assert st["receivers"]["in"]["bad_lines"] == 1
    assert st["processors"]["trust"]["aborted_utterances"] == 1
    assert st["processors"]["trust"]["skipped_after_gap"] == 5


def test_invalid_frame_cuts_the_utterance(tmp_path):
    bad = {"type": "frame", "t": 0.6, "log_probs": [0.0, 0.0, 0.0]}  # log-sum-exp = log 3, breaks FRM-3
    seg = {"type": "segment_end"}
    evs = [HDR, *_frames(0, 5), seg, *_frames(10, 4), bad, *_frames(16, 4), seg, *_frames(30, 3), {"type": "end"}]
    _write(tmp_path / "s.jsonl", evs)
    col = _run(tmp_path, _config(tmp_path, [tmp_path / "s.jsonl"]))
    finals = [g for g in _decisions(tmp_path) if g["is_final"]]
    assert [g["input"]["t_range"][0] for g in finals] == [0.0, 1.2]
    assert col.metrics()["pipelines"]["main"]["processors"]["check"]["invalid_events"] == 1


def test_eof_cut_gives_no_final_on_open_utterance(tmp_path):
    evs = [HDR, *_frames(0, 5), {"type": "segment_end"}, *_frames(10, 5)]  # no end event
    _write(tmp_path / "s.jsonl", evs)
    d = _config(tmp_path, [tmp_path / "s.jsonl"])
    d["receivers"]["in"]["eof"] = "cut"
    _run(tmp_path, d)
    assert len([g for g in _decisions(tmp_path) if g["is_final"]]) == 1
    # eof = "close" (default) closes the stream like `fidetype trust`: two finals
    d["receivers"]["in"]["eof"] = "close"
    _run(tmp_path, d)
    assert len([g for g in _decisions(tmp_path) if g["is_final"]]) == 2


def test_invalid_header_drops_the_stream(tmp_path):
    bad_hdr = {**HDR, "vocab": ["a", "a"]}  # duplicate tokens
    _write(tmp_path / "s.jsonl", [bad_hdr, *_frames(0, 5), {"type": "end"}])
    col = _run(tmp_path, _config(tmp_path, [tmp_path / "s.jsonl"]))
    assert _decisions(tmp_path) == []
    c = col.metrics()["pipelines"]["main"]["processors"]["check"]
    assert c["invalid_headers"] == 1 and c["dropped_no_header"] == 6


def test_tail_mode_cuts_open_stream_at_stop_and_health_endpoint(tmp_path):
    p = tmp_path / "live.jsonl"
    _write(p, [HDR, *_frames(0, 5), {"type": "segment_end"}, *_frames(10, 5)])
    d = _config(tmp_path, [p], service={"health": {"listen": "127.0.0.1:0"}})
    d["receivers"]["in"].update(follow=True, idle_timeout_s=60)
    col = Collector(parse(d, base_dir=tmp_path)).start()
    th = threading.Thread(target=col.run, daemon=True)
    th.start()
    try:
        base = f"http://127.0.0.1:{col.health_port}"
        deadline = time.time() + 10
        while time.time() < deadline:
            m = json.loads(urllib.request.urlopen(base + "/metrics", timeout=5).read())
            if m["pipelines"]["main"]["processors"]["trust"]["final_decisions"] >= 1:
                break
            time.sleep(0.05)
        assert json.loads(urllib.request.urlopen(base + "/healthz", timeout=5).read()) == {"status": "ok"}
        assert "127.0.0.1" not in json.dumps(m)  # no host in the metrics
    finally:
        col.request_stop()
        th.join(10)
    finals = [g for g in _decisions(tmp_path) if g["is_final"]]
    assert len(finals) == 1  # the second utterance was open at stop: cut, no final decision
    assert col.metrics()["pipelines"]["main"]["receivers"]["in"]["cut_streams"] == 1


def test_thin_keeps_finals_and_changes(tmp_path):
    from fidetype.collector.processors import ThinProcessor

    def td(seq, final, action, shown):
        return ("s", {"type": "trust_decision", "session": "s", "seq": seq, "utterance": 0, "is_final": final,
                      "action": action, "shown": shown, "p_top1": 0.5, "score_semantics": "calibrated_prob"})

    items = [td(0, False, "OFFER", ["a"]), td(1, False, "OFFER", ["a"]), td(2, False, "OFFER", ["ab"]),
             td(3, True, "COMMIT", ["ab"]), ("s", {"type": "frame", "t": 1.0, "log_probs": LP})]
    out = ThinProcessor("t", lambda m: None).process(items)
    assert [e.get("seq") for _, e in out] == [0, 2, 3, None]
    out = ThinProcessor("t", lambda m: None, keep_provisional="none").process(items)
    assert [e.get("seq") for _, e in out] == [3, None]


def test_validate_drops_bad_decisions():
    from fidetype.collector.processors import ValidateProcessor

    base = {"type": "trust_decision", "session": "s", "utterance": 0, "action": "COMMIT", "p_top1": 0.9,
            "score_semantics": "calibrated_prob", "shown": ["ab"]}
    items = [("s", {**base, "seq": 0, "is_final": True}),
             ("s", {**base, "seq": 1, "is_final": True}),                  # second final of utterance 0 (TD-6)
             ("s", {**base, "seq": 1, "utterance": 1, "is_final": True}),  # seq does not increase (TD-5)
             ("s", {**base, "seq": 2, "utterance": 2, "is_final": "yes"}),  # not a boolean (TD-F1)
             ("s", {**base, "seq": 3, "utterance": 3, "is_final": True})]
    v = ValidateProcessor("v", lambda m: None)
    out = v.process(items)
    assert [e["seq"] for _, e in out] == [0, 3]
    assert v.counts["invalid_decisions"] == 3


# --- configuration errors ----------------------------------------------------------------------


def _base(tmp_path):
    _write(tmp_path / "s.jsonl", [HDR])
    return _config(tmp_path, [tmp_path / "s.jsonl"])


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d["processors"]["trust"].update(colour="red"), r"processors\.trust: unknown key 'colour'"),
    (lambda d: d["pipelines"]["main"].update(processors=["check", "trsut"]),
     r"pipelines\.main\.processors\[1\]: unknown processor 'trsut' \(known: check, trust\)"),
    (lambda d: d["processors"]["trust"].update(type="trusty"), r"processors\.trust\.type: unknown processor type"),
    (lambda d: d["processors"]["trust"].pop("config"), r"processors\.trust: missing required key 'config'"),
    (lambda d: d["receivers"]["in"].update(token="abc"), r"secrets must not be in the configuration file"),
    (lambda d: d["exporters"]["log"].update(types=["trust_decision", "frame"]), r"TD-11"),
    (lambda d: d["pipelines"]["main"].update(exporters=[]), r"needs at least one exporter"),
    (lambda d: d["receivers"]["in"].update(eof="maybe"), r"receivers\.in\.eof: must be one of 'close', 'cut'"),
    (lambda d: d["processors"]["trust"].update(max_attempts="2"), r"max_attempts: must be an integer"),
    (lambda d: d.update(colour=1), r"<config>: unknown key 'colour'"),
    (lambda d: d["receivers"].update(spare={"type": "file", "paths": ["x"]}), r"receivers\.spare: defined but not used"),
    (lambda d: d["service"].update(health={"listen": "0.0.0.0:13133"}), r"service\.health\.listen: binds beyond localhost"),
    (lambda d: d["service"].update(health={"token": "abc"}), r"service\.health\.token: secrets must not be"),
    (lambda d: d["service"].update(health={"allow_unauthenticated": "yes"}), r"allow_unauthenticated: must be true"),
    (lambda d: d["exporters"].update(ws={"type": "websocket", "receiver": "in", "listen": "127.0.0.1:1"}),
     r"exporters\.ws\.listen: only valid for a standalone /decisions server"),
    (lambda d: d["exporters"].update(ws={"type": "websocket", "linger_s": -1}), r"exporters\.ws\.linger_s: must be >= 0"),
])
def test_config_errors_are_clear(tmp_path, mutate, match):
    d = _base(tmp_path)
    mutate(d)
    with pytest.raises(ConfigError, match=match):
        parse(d, base_dir=tmp_path)


def test_config_redact_before_trust_is_refused(tmp_path):
    d = _config(tmp_path, [tmp_path / "s.jsonl"], processors=("privacy", "trust"),
                extra_proc={"privacy": {"type": "redact"}})
    with pytest.raises(ConfigError, match="put redact after trust"):
        parse(d, base_dir=tmp_path)


def test_config_missing_trust_file_and_files(tmp_path):
    d = _base(tmp_path)
    d["processors"]["trust"]["config"] = "nope.json"
    with pytest.raises(ConfigError, match=r"processors\.trust\.config: trust configuration not found"):
        Collector(parse(d, base_dir=tmp_path))
    (tmp_path / "c.yaml").write_text("pipelines: {}\n")
    with pytest.raises(ConfigError, match=r"YAML is not supported \(it would need a new dependency, PyYAML\)"):
        load(tmp_path / "c.yaml")
    (tmp_path / "c.yml").write_text("pipelines: {}\n")
    with pytest.raises(ConfigError, match="YAML is not supported"):
        load(tmp_path / "c.yml")
    (tmp_path / "c.toml").write_text("[pipelines\n")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load(tmp_path / "c.toml")
    with pytest.raises(ConfigError, match="not found"):
        load(tmp_path / "missing.toml")


def test_cli_check_and_error_exit_codes(tmp_path, capsys):
    from fidetype.cli import main as cli

    CFG.save(tmp_path / "trust.json")
    _write(tmp_path / "s.jsonl", [HDR, *_frames(0, 3), {"type": "end"}])
    (tmp_path / "ok.toml").write_text(
        '[service]\nlog = "quiet"\n[receivers.in]\ntype = "file"\npaths = ["s.jsonl"]\n'
        '[processors.trust]\ntype = "trust"\nconfig = "trust.json"\ndecoder = "greedy"\n'
        '[exporters.log]\ntype = "jsonl"\npath = "out/d.jsonl"\n'
        '[pipelines.main]\nreceivers = ["in"]\nprocessors = ["trust"]\nexporters = ["log"]\n', encoding="utf-8")
    assert cli(["collector", "--config", str(tmp_path / "ok.toml"), "--check"]) == 0
    assert "pipeline main" in capsys.readouterr().out
    assert cli(["collector", "--config", str(tmp_path / "ok.toml")]) == 0
    assert len(_decisions(tmp_path, "out/d.jsonl")) == 1
    (tmp_path / "bad.toml").write_text('[pipelines.main]\nreceivers = ["nope"]\nexporters = []\n', encoding="utf-8")
    assert cli(["collector", "--config", str(tmp_path / "bad.toml")]) == 2
    assert "configuration error: pipelines.main.exporters" in capsys.readouterr().err


# --- WebSocket receiver and exporter -----------------------------------------------------------


def _ws_config(tmp_path):
    return _config(tmp_path, [], receiver={"type": "websocket", "listen": "127.0.0.1:0", "reorder_window": 0},
                   exporters={"log": {"type": "jsonl", "path": "out/decisions.jsonl"},
                              "live": {"type": "websocket", "receiver": "in"}})


@ws_only
def test_websocket_in_and_decisions_out(tmp_path):
    evs = _sim_events(tmp_path, n=3)
    col = Collector(parse(_ws_config(tmp_path), base_dir=tmp_path)).start()
    port = col.receiver("in").port
    got_live: list[dict] = []
    th = threading.Thread(target=col.run, kwargs={"duration_s": 30}, daemon=True)
    th.start()
    sub = threading.Thread(target=W.subscribe, args=(f"ws://127.0.0.1:{port}/decisions", got_live.append),
                           kwargs={"from_seq": 1, "max_decisions": 3, "duration_s": 20}, daemon=True)
    sub.start()
    W.replay_to_ws(evs, f"ws://127.0.0.1:{port}/nts", stream_id="dev-1", speed=0)
    sub.join(20)  # the subscriber stops after 3 decisions
    col.request_stop()
    th.join(30)
    got = _decisions(tmp_path)
    ref = [d.to_event() for d in _reference(evs)]
    assert [(g["action"], g["shown"]) for g in got] == [(r["action"], r["shown"]) for r in ref]
    assert all(g["session"] == "dev-1" and g["ws"]["binding"] == W.BINDING_VERSION for g in got)
    assert [d["ws_seq"] for d in got_live] == [1, 2, 3]


@ws_only
def test_websocket_gap_gives_no_final_on_cut_utterance(tmp_path):
    evs = _sim_events(tmp_path, n=3)
    # ws_seq k = event index k (the header has no ws_seq); lose one frame inside utterance 1
    seg_idx = [i for i, e in enumerate(evs) if e["type"] == "segment_end"]
    lost = seg_idx[0] + 3
    col = Collector(parse(_ws_config(tmp_path), base_dir=tmp_path)).start()
    port = col.receiver("in").port
    th = threading.Thread(target=col.run, kwargs={"max_streams": 1, "duration_s": 30}, daemon=True)
    th.start()
    W.replay_to_ws(evs, f"ws://127.0.0.1:{port}/nts", stream_id="dev-2", speed=0, lose=[lost])
    th.join(30)
    finals = [g for g in _decisions(tmp_path) if g["is_final"]]
    ref = [d.to_event() for d in _reference(evs) if d.final]
    assert len(ref) == 3 and len(finals) == 2
    assert [f["shown"] for f in finals] == [ref[0]["shown"], ref[2]["shown"]]


# --- v0.1 design decisions (FEP-0006) ----------------------------------------------------------


def test_eof_close_without_end_warns_once_and_counts(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write(a, [HDR, *_frames(0, 5)])                        # no end event
    _write(b, [HDR, *_frames(0, 5), {"type": "end"}])       # complete
    d = _config(tmp_path, [a, b], service={"log": "info"})
    logs: list[str] = []
    col = Collector(parse(d, base_dir=tmp_path), log=logs.append)
    col.run()
    warn = [m for m in logs if "ended without an end event" in m]
    assert len(warn) == 1 and "stream in-0" in warn[0] and "WARNING" in warn[0]
    rec = col.metrics()["pipelines"]["main"]["receivers"]["in"]
    assert rec["closed_without_end"] == 1 and rec["cut_streams"] == 0
    assert len([g for g in _decisions(tmp_path) if g["is_final"]]) == 2  # eof = "close" stays the default


def test_two_receivers_get_prefixed_stream_ids(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write(a, [HDR, *_frames(0, 5), {"type": "end"}])
    _write(b, [HDR, *_frames(0, 5), {"type": "segment_end"}, *_frames(10, 5)])  # no end: cut at EOF
    d = _config(tmp_path, [a])
    d["receivers"] = {"ra": {"type": "file", "paths": [str(a)]},
                      "rb": {"type": "file", "paths": [str(b)], "eof": "cut"}}
    d["pipelines"]["main"]["receivers"] = ["ra", "rb"]
    col = _run(tmp_path, d)
    got = _decisions(tmp_path)
    assert [(g["session"], g["utterance"]) for g in got if g["is_final"]] == [("ra/ra-0", 0), ("rb/rb-0", 0)]
    # the lost status of rb reached the trust session "rb/rb-0": its open utterance 1 has no decision
    assert col.metrics()["pipelines"]["main"]["processors"]["trust"]["aborted_utterances"] == 1


def _get(url, token=None):
    req = urllib.request.Request(url)
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_health_default_listen_is_localhost(tmp_path):
    d = _base(tmp_path)
    d["service"]["health"] = {}
    cfg = parse(d, base_dir=tmp_path)
    assert cfg.service["health"]["listen"] == "127.0.0.1:13133"
    d["service"]["health"] = {"listen": "0.0.0.0:13133", "allow_unauthenticated": True}
    parse(d, base_dir=tmp_path)  # accepted when the operator says so explicitly
    d["service"]["health"] = {"listen": "0.0.0.0:13133", "token_env": "FT_HEALTH_TOKEN"}
    parse(d, base_dir=tmp_path)  # accepted with a token


def test_health_open_bind_warns(tmp_path, monkeypatch):
    d = _base(tmp_path)
    d["service"].update(log="info", health={"listen": "0.0.0.0:0", "allow_unauthenticated": True})
    logs: list[str] = []
    col = Collector(parse(d, base_dir=tmp_path), log=logs.append)
    started = []
    monkeypatch.setattr(col, "_start_health", lambda host, port, token=None: started.append((host, token)))
    col.run()
    assert started == [("0.0.0.0", None)]  # no real bind beyond localhost in a test
    assert any("service.health: WARNING" in m and "without a token" in m for m in logs)


def test_health_bearer_token(tmp_path, monkeypatch):
    token = "health-test-token-0123456789"
    monkeypatch.setenv("FT_HEALTH_TOKEN", token)
    p = tmp_path / "live.jsonl"
    _write(p, [HDR, *_frames(0, 5)])
    d = _config(tmp_path, [p], service={"log": "info", "health": {"listen": "127.0.0.1:0",
                                                                  "token_env": "FT_HEALTH_TOKEN"},
                                        "metrics_file": "out/metrics.json"})
    d["receivers"]["in"].update(follow=True, idle_timeout_s=60)
    logs: list[str] = []
    col = Collector(parse(d, base_dir=tmp_path), log=logs.append).start()
    th = threading.Thread(target=col.run, daemon=True)
    th.start()
    try:
        base = f"http://127.0.0.1:{col.health_port}"
        assert _get(base + "/healthz")[0] == 401
        assert _get(base + "/metrics", token="wrong")[0] == 401
        assert _get(base + "/healthz", token=token) == (200, {"status": "ok"})
        code, m = _get(base + "/metrics", token=token)
        assert code == 200 and token not in json.dumps(m)
    finally:
        col.request_stop()
        th.join(10)
    assert all(token not in x for x in logs)
    assert token not in (tmp_path / "out" / "metrics.json").read_text(encoding="utf-8")


def test_health_token_env_missing_is_a_config_error(tmp_path, monkeypatch):
    monkeypatch.delenv("FT_NO_HEALTH_TOKEN", raising=False)
    d = _base(tmp_path)
    d["service"]["health"] = {"listen": "127.0.0.1:0", "token_env": "FT_NO_HEALTH_TOKEN"}
    with pytest.raises(ConfigError, match="FT_NO_HEALTH_TOKEN"):
        Collector(parse(d, base_dir=tmp_path)).start()


def test_decisions_carry_spec_version_and_pass_fep0001(tmp_path):
    from fidetype.conformance.profiles import fep0001

    evs = _sim_events(tmp_path)
    _write(tmp_path / "s.jsonl", evs)
    d = _config(tmp_path, [tmp_path / "s.jsonl"], processors=("check", "trust", "thin"),
                extra_proc={"thin": {"type": "thin", "keep_provisional": "all"}})
    d["processors"]["trust"]["max_attempts"] = 2  # provisional decisions too
    _run(tmp_path, d)
    got = _decisions(tmp_path)
    assert got and all(g["spec_version"] == "1.0" for g in got)
    assert list(got[0])[:2] == ["type", "spec_version"]
    rep = fep0001.check_file(tmp_path / "out" / "decisions.jsonl")
    assert rep.failures("core") == []


def test_blank_final_commit_is_gated_for_spec_1_0(tmp_path):
    """Frames that decode to blank only: the 0.1 policy commits ''. With spec_version 1.0 the gate forbids it."""
    from fidetype.conformance.profiles import fep0001

    _write(tmp_path / "s.jsonl", [HDR, *_frames(0, 5), {"type": "end"}])  # greedy -> "" (blank_id 0 wins)
    # the ungated reference commits a blank text: this is what TD-9 forbids for 1.x decisions
    layer = StreamingTrustLayer(CFG, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=1))
    raw = [x.to_event() for x in replay(list(iter_events(tmp_path / "s.jsonl")), layer, session_id="in-0")]
    assert raw[-1]["action"] == "COMMIT" and raw[-1]["shown"][0].strip() == ""
    assert fep0001.td_format_errors({**raw[-1], "spec_version": "1.0"})  # would fail TD-9
    logs: list[str] = []
    d = _config(tmp_path, [tmp_path / "s.jsonl"], service={"log": "info"})
    col = Collector(parse(d, base_dir=tmp_path), log=logs.append)
    col.run()
    got = _decisions(tmp_path)
    fin = [g for g in got if g["is_final"]]
    assert len(fin) == 1 and fin[0]["spec_version"] == "1.0" and fin[0]["action"] != "COMMIT"
    assert fin[0]["reason"].startswith("commit gate: empty text")
    assert fin[0]["config_id"] == CFG_GATED.config_id != CFG.config_id
    assert any(f"config_id {CFG.config_id} -> {CFG_GATED.config_id}" in m for m in logs)
    assert col.metrics()["pipelines"]["main"]["processors"]["trust"]["gated_commits"] == 1
    assert fep0001.check_file(tmp_path / "out" / "decisions.jsonl").failures("core") == []


def test_trust_config_gate_rules(tmp_path):
    from dataclasses import replace

    from fidetype.collector.processors import blank_safe_config

    assert blank_safe_config(CFG_GATED) is CFG_GATED                     # already blank-safe
    words = CFG.with_commit_gate(min_chars=0, min_words=1)
    assert blank_safe_config(words) is words                             # min_words 1 is blank-safe too
    loose = CFG.with_commit_gate(min_chars=0, min_words=0, max_guard_risk=0.5)
    fixed = blank_safe_config(loose)
    assert fixed.gate.min_chars == 1 and fixed.gate.max_guard_risk == 0.5
    replace(CFG, policy_class="always_commit").save(tmp_path / "always.json")
    d = _base(tmp_path)
    d["processors"]["trust"]["config"] = "always.json"
    with pytest.raises(ConfigError, match=r"processors\.trust: cannot build the trust layer: policy_class "
                                          r"'always_commit' can commit a blank text"):
        Collector(parse(d, base_dir=tmp_path))


@ws_only
def test_standalone_decisions_server_file_replay(tmp_path, monkeypatch):
    from websockets.exceptions import InvalidStatus
    from websockets.sync.client import connect

    token = "standalone-ws-token-0123456789"
    monkeypatch.setenv("FT_WS_TOKEN", token)
    evs = _sim_events(tmp_path, n=3)
    _write(tmp_path / "s.jsonl", evs)
    d = _config(tmp_path, [tmp_path / "s.jsonl"],
                exporters={"log": {"type": "jsonl", "path": "out/decisions.jsonl"},
                           "live": {"type": "websocket", "listen": "127.0.0.1:0", "token_env": "FT_WS_TOKEN",
                                    "linger_s": 30}},
                service={"log": "info", "metrics_file": "out/metrics.json"})
    logs: list[str] = []
    col = Collector(parse(d, base_dir=tmp_path), log=logs.append).start()
    port = col._exporters["live"].port
    th = threading.Thread(target=col.run, daemon=True)
    th.start()
    try:
        # the standalone server serves /decisions only: no NTS input path
        with pytest.raises(InvalidStatus):
            connect(f"ws://127.0.0.1:{port}/nts", subprotocols=[W.SUBPROTOCOL], open_timeout=5)
        got_live: list[dict] = []
        core = W.subscribe(f"ws://127.0.0.1:{port}/decisions", got_live.append, from_seq=1, token=token,
                           max_decisions=3, duration_s=20)
        assert th.is_alive()  # linger_s keeps the server open after the input is done
    finally:
        col.request_stop()
        th.join(30)
    assert not th.is_alive()
    logged = _decisions(tmp_path)
    ref = [x.to_event() for x in _reference(evs)]
    assert len(logged) == len(ref) == 3 and core.duplicates == 0
    assert [d["ws_seq"] for d in got_live] == [1, 2, 3]
    # the subscriber adds ws_seq (the channel) and _line (its own counter); the rest equals the log
    assert [{k: v for k, v in g.items() if k not in ("ws_seq", "_line")} for g in got_live] == logged
    assert [(g["action"], g["shown"]) for g in logged] == [(r["action"], r["shown"]) for r in ref]
    assert all(g["spec_version"] == "1.0" and "ws" not in g for g in logged)
    ex = col.metrics()["pipelines"]["main"]["exporters"]["live"]
    assert ex["exported"] == 3 and ex["standalone"] is True
    assert all(token not in x for x in logs)
    assert token not in (tmp_path / "out" / "metrics.json").read_text(encoding="utf-8")
