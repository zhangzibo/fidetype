"""P5-16 (signed anchors written by the Collector and the trust layers) and P5-17 (no mixed-stream files).

Synthetic data only. Keys are throwaway keys made in the test; no key file is in the repository.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fidetype.collector import Collector, ConfigError, parse
from fidetype.trust import anchor as A
from fidetype.trust.policy import Action, Decision, PolicyInputs
from fidetype.trust.provenance import ProvenanceLedger, body_digest, entry_hash, main, read_entries, verify

needs_sign = pytest.mark.skipif(not A.signing_available(), reason='needs cryptography (pip install "fidetype[sign]")')
ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "spec" / "conformance" / "fep-0001" / "f01-segments.jsonl"
TRUST = ROOT / "examples" / "collector" / "trust-example.json"
CTX = {"decoder": {"name": "dec", "version": "1"}, "calibration": {"id": "cal-1"}, "policy": {"version": "p1"}}
KEY_ENV = "FT_TEST_ANCHOR_KEY"


def _decide(led, cid, text):
    led.record_decision(context_id=cid, decision=Decision(Action.COMMIT, (text,), "p"),
                        inputs=PolicyInputs(texts=(text,), p_top1=0.95, set_indices=(0,), guard_risk=0.01))


def _rechain(entries, old, new):
    """The attack: edit a body text, then recompute every digest and hash so that the chain verifies again."""
    out, prev = [], None
    for e in entries:
        e = json.loads(json.dumps(e).replace(old, new))
        if prev is not None:
            e["prev_hash"] = prev
        if "salt" in e:
            e["body_sha256"] = body_digest(e["salt"], e["body"])
        e["hash"] = prev = entry_hash(e)
        out.append(e)
    return out


# --- P5-16 API --------------------------------------------------------------------------------


@needs_sign
def test_auto_anchor_catches_a_rewrite_after_the_last_manual_anchor(tmp_path):
    priv, pub = A.generate_key()
    led = ProvenanceLedger(tmp_path / "l.jsonl", text_mode="store")
    cid = led.record_context(CTX)
    _decide(led, cid, "before the manual anchor")
    manual = A.sign_anchor(A.make_anchor(led.entries), priv)
    with A.AutoAnchor(led, priv, tmp_path / "anchors", every_n=2) as auto:
        for i in range(5):
            _decide(led, cid, f"later text {i}")
    assert auto.closed and auto.written == 3  # 2 + 2 entries, then the last one at close (on_stop)
    files = A.anchor_files(tmp_path / "anchors")
    assert len(files) == 3 and A.newest_anchor(tmp_path / "anchors")["seq"] == led.head["seq"]
    newest = A.newest_anchor(tmp_path / "anchors")
    assert A.verify_anchored(led.entries, newest, pub).ok
    # The attacker rewrites an entry written after the manual anchor and recomputes the chain.
    forged = _rechain(read_entries(tmp_path / "l.jsonl"), "later text 3", "forged text 3")
    assert verify(forged).ok
    assert A.verify_anchored(forged, manual, pub, allow_growth=True).ok  # the manual anchor does not cover it
    res = A.verify_anchored(forged, newest, pub, allow_growth=True)
    assert not res.ok and any("another hash" in e for e in res.errors)
    # CLI: --anchor <directory> checks the newest anchor.
    (tmp_path / "f.jsonl").write_text("".join(json.dumps(e) + "\n" for e in forged), encoding="utf-8")
    (tmp_path / "pub.pem").write_bytes(pub)
    assert main(["verify", str(tmp_path / "l.jsonl"), "--anchor", str(tmp_path / "anchors"),
                 "--public-key", str(tmp_path / "pub.pem"), "--allow-growth"]) == 0
    assert main(["verify", str(tmp_path / "f.jsonl"), "--anchor", str(tmp_path / "anchors"),
                 "--public-key", str(tmp_path / "pub.pem"), "--allow-growth"]) == 1


@needs_sign
def test_auto_anchor_timer_keep_and_rules(tmp_path, monkeypatch):
    priv, pub = A.generate_key()
    now = [0.0]
    led = ProvenanceLedger(None)
    auto = A.AutoAnchor(led, priv, tmp_path / "a", every_s=10.0, keep=2, clock=lambda: now[0])
    cid = led.record_context(CTX)
    assert auto.tick() is None and auto.written == 0  # no time passed
    now[0] = 11.0
    assert auto.tick() is not None and auto.written == 1
    now[0] = 30.0
    assert auto.tick() is None  # no new entry: nothing to anchor
    _decide(led, cid, "x")  # the timer has passed: this entry triggers an anchor
    _decide(led, cid, "y")
    now[0] = 45.0
    auto.tick()
    auto.close()
    assert auto.written == 3 and len(A.anchor_files(tmp_path / "a")) == 2  # keep = 2
    assert led.on_append == []  # close stops listening
    assert "BEGIN" not in repr(auto) and "PRIVATE" not in json.dumps(auto.stats())
    for bad in ({"every_n": 0}, {"every_s": 0}, {"keep": 0}):
        with pytest.raises(ValueError):
            A.AutoAnchor(led, priv, tmp_path / "b", **bad)
    monkeypatch.setenv(KEY_ENV, priv.decode())
    assert A.key_id(A.load_private_key(key_env=KEY_ENV)) == A.key_id(pub)
    monkeypatch.setenv(KEY_ENV, "not a key")
    with pytest.raises(ValueError) as e:
        A.load_private_key(key_env=KEY_ENV)
    assert "not a key" not in str(e.value) and KEY_ENV in str(e.value)
    with pytest.raises(ValueError, match="exactly one"):
        A.load_private_key()


# --- P5-16 Collector --------------------------------------------------------------------------


def _collector_config(tmp_path, anchor):
    return {
        "service": {"log": "quiet", "metrics_file": "out/metrics.json"},
        "receivers": {"in": {"type": "file", "paths": [str(VECTOR)]}},
        "processors": {"trust": {"type": "trust", "config": str(TRUST), "decoder": "greedy",
                                 "ledger": {"path": "out/ledger.jsonl", "text_mode": "hash", "anchor": anchor}}},
        "exporters": {"log": {"type": "jsonl", "path": "out/decisions.jsonl"}},
        "pipelines": {"main": {"receivers": ["in"], "processors": ["trust"], "exporters": ["log"]}},
    }


@needs_sign
def test_collector_writes_signed_anchors(tmp_path, monkeypatch, capsys):
    priv, pub = A.generate_key()
    monkeypatch.setenv(KEY_ENV, priv.decode())
    logs: list[str] = []
    cfg = _collector_config(tmp_path, {"dir": "out/anchors", "key_env": KEY_ENV, "every_n": 2})
    cfg["service"]["log"] = "info"
    col = Collector(parse(cfg, base_dir=tmp_path), log=logs.append)
    col.run()
    out = tmp_path / "out"
    ents = read_entries(out / "ledger.jsonl")
    files = A.anchor_files(out / "anchors")
    assert len(files) >= 2 and A.newest_anchor(out / "anchors")["seq"] == ents[-1]["seq"]  # on stop: the head
    assert A.verify_anchored(ents, A.newest_anchor(out / "anchors"), pub).ok
    m = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert m["anchors"][0]["anchors_written"] == len(files) and m["anchors"][0]["key_id"] == A.key_id(pub)
    # The key is never in a log, the metrics, an anchor or the ledger.
    secret = priv.decode().splitlines()[1]
    body = "\n".join(logs) + capsys.readouterr().err + "".join(p.read_text(encoding="utf-8") for p in out.rglob("*.json*"))
    assert secret not in body and "PRIVATE KEY" not in body
    # A rewrite of the newest decision entry fails against the automatic anchor.
    seq = max(e["seq"] for e in ents if e["kind"] == "decision")
    forged = [dict(e) for e in ents]
    forged[seq] = json.loads(json.dumps(forged[seq]))
    forged[seq]["body"]["note"] = "edited"
    forged = _rechain(forged, "<never in a ledger>", "")  # recompute the chain after the edit
    assert verify(forged).ok
    assert not A.verify_anchored(forged, A.newest_anchor(out / "anchors"), pub, allow_growth=True).ok


@needs_sign
def test_collector_key_file_option(tmp_path):
    k, p = tmp_path / "k.pem", tmp_path / "k.pub.pem"
    A.write_key_pair(k, p)
    col = Collector(parse(_collector_config(tmp_path, {"dir": "anc", "key_file": str(k), "on_stop": True}),
                          base_dir=tmp_path))
    col.run()
    assert len(A.anchor_files(tmp_path / "anc")) == 1
    assert A.verify_anchored(tmp_path / "out" / "ledger.jsonl", A.newest_anchor(tmp_path / "anc"), p.read_bytes()).ok


def test_collector_anchor_config_rules(tmp_path, monkeypatch):
    def bad(anchor, match):
        with pytest.raises(ConfigError, match=match):
            parse(_collector_config(tmp_path, anchor), base_dir=tmp_path)

    bad({"key_env": KEY_ENV}, "missing required key 'dir'")
    bad({"dir": "a"}, "exactly one of key_env")
    bad({"dir": "a", "key_env": KEY_ENV, "key_file": "k.pem"}, "exactly one of key_env")
    bad({"dir": "a", "key": "-----BEGIN PRIVATE KEY-----"}, "secrets must not be in the configuration")
    bad({"dir": "a", "key_env": KEY_ENV, "every_n": 0}, "every_n: must be >= 1")
    bad({"dir": "a", "key_env": KEY_ENV, "every_s": -1}, "every_s: must be > 0")
    bad({"dir": "a", "key_env": KEY_ENV, "on_stop": False}, "with on_stop = false")
    bad({"dir": "out/ledger.jsonl", "key_env": KEY_ENV}, "must not be the ledger file")
    bad({"dir": "a", "key_env": KEY_ENV, "every": 3}, "unknown key 'every'")
    if A.signing_available():
        monkeypatch.delenv(KEY_ENV, raising=False)
        with pytest.raises(ConfigError, match="empty or not set"):
            Collector(parse(_collector_config(tmp_path, {"dir": "a", "key_env": KEY_ENV}), base_dir=tmp_path))


# --- P5-17 ------------------------------------------------------------------------------------

INPUT = ["header", "frame", "segment_end", "end"]


def _streams_config(receivers, path, pipelines=None):
    return {
        "service": {"log": "quiet"},
        "receivers": receivers,
        "exporters": {"nts": {"type": "jsonl", "path": path, "types": INPUT}},
        "pipelines": pipelines or {"main": {"receivers": list(receivers), "exporters": ["nts"]}},
    }


@pytest.mark.parametrize("receivers, why", [
    ({"in": {"type": "file", "paths": ["a.jsonl", "b.jsonl"]}}, "reads 2 files"),
    ({"a": {"type": "file", "paths": ["a.jsonl"]}, "b": {"type": "file", "paths": ["b.jsonl"]}}, "2 receivers"),
    ({"in": {"type": "websocket", "listen": "127.0.0.1:0"}}, "websocket receiver"),
    ({"in": {"type": "lsl", "stream_name": "x"}}, "lsl receiver"),
])
def test_input_event_file_without_session_is_refused_when_streams_can_mix(tmp_path, receivers, why):
    with pytest.raises(ConfigError, match=r"exporters\.nts\.path: a file of input events would mix streams") as e:
        parse(_streams_config(receivers, "out/s.jsonl"), base_dir=tmp_path)
    assert why in str(e.value) and "{session}" in str(e.value)
    parse(_streams_config(receivers, "out/s/{session}.jsonl"), base_dir=tmp_path)  # one file per stream: fine


def test_input_event_file_without_session_is_fine_for_one_stream(tmp_path):
    rec = {"in": {"type": "file", "paths": ["a.jsonl"]}}
    parse(_streams_config(rec, "out/s.jsonl"), base_dir=tmp_path)
    # A decision log is always fine: each line names its session (TD-11).
    d = _streams_config({"in": {"type": "file", "paths": ["a.jsonl", "b.jsonl"]}}, "out/s/{session}.jsonl")
    d["exporters"]["log"] = {"type": "jsonl", "path": "out/decisions.jsonl"}
    d["pipelines"]["main"]["exporters"].append("log")
    parse(d, base_dir=tmp_path)


def test_input_event_exporter_shared_by_two_pipelines_is_refused(tmp_path):
    rec = {"a": {"type": "file", "paths": ["a.jsonl"]}, "b": {"type": "file", "paths": ["b.jsonl"]}}
    pls = {"one": {"receivers": ["a"], "exporters": ["nts"]}, "two": {"receivers": ["b"], "exporters": ["nts"]}}
    with pytest.raises(ConfigError, match="2 receivers"):
        parse(_streams_config(rec, "out/s.jsonl", pls), base_dir=tmp_path)


def test_example_configs_use_session_for_input_event_files():
    from fidetype.collector.config import read_file

    for p in sorted((ROOT / "examples" / "collector").glob("*.toml")):
        text = p.read_text(encoding="utf-8")
        assert "{session}" in text, p
        parse(read_file(p), base_dir=p.parent)
