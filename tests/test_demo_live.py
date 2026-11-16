"""Tests of the live replay demo (P14-06): config, key decoding, tracks, server and event flow.

Synthetic data only (fidetype.demo simulator and hand-made decision logs). No dataset is read.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
import pytest

from fidetype import demo
from fidetype.adapters import ws as W
from fidetype.conformance.io import write_jsonl
from fidetype.demo.live import config as C
from fidetype.demo.live import keys as K
from fidetype.demo.live import tracks as T
from fidetype.demo.live.__main__ import main as live_main
from fidetype.streams.spec import NeuralTextStream

ws_only = pytest.mark.skipif(not W.websockets_available(), reason="websockets not installed (pip install fidetype[ws])")


# --- fixtures ----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def nts_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Four synthetic NTS stream files, their truth map and the packaged demo trust config."""
    d = tmp_path_factory.mktemp("nts")
    texts = demo.demo_phrases()[:4]
    truth = {}
    for i, (t, cond) in enumerate(zip(texts, ("strong", "strong", "no-signal", "good"))):
        st = demo.make_stream(t, cond, seed=900 + i)
        st.frame_times = st.frame_times[:40]
        st.log_probs = st.log_probs[:40]
        name = f"u{i:02d}.jsonl"
        write_jsonl(st, d / name)
        truth[name] = {"text": t}
    (d / "truth.json").write_text(json.dumps(truth), encoding="utf-8")
    demo.load_config().save(d / "trust.json")
    return d


def nts_spec(d: Path, **kw) -> dict:
    spec = {"id": "syn-nts", "kind": "nts-streams", "title": "Synthetic NTS files",
            "dataset": {"name": "synthetic", "licence": "Apache-2.0"},
            "streams_dir": str(d), "trust_config": str(d / "trust.json"), "decoder": "greedy",
            "truth": {"format": "json-map", "path": str(d / "truth.json"), "field": "text"},
            "preview_every_frames": 10, "gap_s": 0.0}
    spec.update(kw)
    return spec


def decision(action: str, shown: list[str], key_i: int, p: float = 0.5) -> dict:
    return {"type": "trust_decision", "session": "s", "seq": 0, "utterance": key_i, "is_final": True,
            "action": action, "reason": "test", "p_top1": p, "score_semantics": "calibrated_prob", "set_size": 1,
            "guard_risk": 0.1, "config_id": "tcfg-test", "shown": shown,
            "input": {"kind": "frames", "t_range": [0.1, 0.5]}, "t_signal_end": 0.5, "latency_s": 0.01}


@pytest.fixture()
def log_dir(tmp_path: Path) -> Path:
    keys = ["a|val|0", "a|val|1", "a|val|2", "a|val|3"]
    decs = [decision("COMMIT", ["hello world"], 0), decision("COMMIT", ["hello word"], 1),
            decision("OFFER", ["good morning"], 2), decision("ABSTAIN", [], 3)]
    (tmp_path / "log.json").write_text(json.dumps({"keys": keys, "decisions": decs}), encoding="utf-8")
    truth = {"a|val|0": "Hello world.", "a|val|1": "hello world", "a|val|2": "good morning", "a|val|3": "yes"}
    (tmp_path / "truth.json").write_text(json.dumps(truth), encoding="utf-8")
    return tmp_path


def log_spec(d: Path) -> dict:
    return {"id": "log", "kind": "trust-log", "title": "Recorded decisions",
            "dataset": {"name": "synthetic", "licence": "CC0-1.0"},
            "decisions": str(d / "log.json"), "truth": {"format": "json-map", "path": str(d / "truth.json")},
            "gap_s": 0.0}


# --- config --------------------------------------------------------------------------------------


def test_default_config_loads_and_lists_the_tracks() -> None:
    cfg, base = C.load()
    ids = [t["id"] for t in cfg["tracks"]]
    assert base is None
    assert {"t15", "emg2qwerty", "synthetic", "p11-01-emg"} <= set(ids)
    assert set(cfg["default_tracks"]) <= set(ids)
    emg = next(t for t in cfg["tracks"] if t["id"] == "emg2qwerty")
    assert emg["dataset"]["research_only"] is True
    assert next(t for t in cfg["tracks"] if t["id"] == "p11-01-emg")["enabled"] is False


def test_expand_uses_the_data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(C.DATA_ENV, str(tmp_path))
    assert C.expand("${DATA}/x/y.json", None) == tmp_path / "x" / "y.json"
    assert C.expand("rel.json", tmp_path) == tmp_path / "rel.json"
    with pytest.raises(C.DemoConfigError):
        C.expand("${NOT_SET_FIDETYPE_X}/a", None)


@pytest.mark.parametrize("bad", [
    {}, {"schema": C.SCHEMA, "tracks": []},
    {"schema": C.SCHEMA, "tracks": [{"id": "A B", "kind": "synthetic", "title": "x", "dataset": {"name": "n", "licence": "l"}}]},
    {"schema": C.SCHEMA, "tracks": [{"id": "a", "kind": "video", "title": "x", "dataset": {"name": "n", "licence": "l"}}]},
    {"schema": C.SCHEMA, "tracks": [{"id": "a", "kind": "synthetic", "title": "x", "dataset": {"name": "n"}}]},
])
def test_config_check_rejects_bad_configs(bad: dict) -> None:
    with pytest.raises(C.DemoConfigError):
        C.check(bad)


def test_missing_data_gives_a_clear_status(tmp_path: Path) -> None:
    spec = nts_spec(tmp_path / "nowhere")
    st, msg = T.make_track(spec, None).status()
    assert st == "missing" and "nowhere" in msg
    spec["prepare"] = {"kind": "emg2qwerty", "makes": ["streams_dir"]}
    st, msg = T.make_track(spec, None).status()
    assert st == "not-prepared" and "--prepare syn-nts" in msg


# --- key streams ---------------------------------------------------------------------------------


def key_stream(codes: list[str], p: float = 0.9) -> NeuralTextStream:
    from fidetype.adapters.kt_semg import KEY_VOCAB

    V = len(KEY_VOCAB)
    lp = np.full((len(codes), V), np.log((1 - p) / (V - 1)))
    for i, c in enumerate(codes):
        lp[i, KEY_VOCAB.index(c)] = np.log(p)
    return NeuralTextStream(log_probs=lp.astype(np.float32), frame_times=np.arange(len(codes)) * 0.2,
                            vocab=list(KEY_VOCAB), blank_id=None, vocab_type="key")


def test_render_keys_applies_backspace_and_keeps_double_letters() -> None:
    codes = ["KeyH", "KeyE", "KeyL", "KeyL", "KeyO", "KeyX", "Backspace", "Space", "Enter", None, "Period"]
    text, conf = K.render_keys(codes, [0.5] * len(codes))
    assert text == "hello ."
    assert len(conf) == len(text)
    assert K.greedy_keys(key_stream(["KeyL", "KeyL"])) == "ll"


def test_key_nbest_ranks_the_clean_text_first() -> None:
    nb = K.key_nbest(key_stream(["KeyH", "KeyI", "Space", "KeyY", "KeyO", "KeyU"]))
    assert nb.candidates[0].text == "hi you"
    assert len({c.text for c in nb.candidates}) == len(nb.candidates)
    assert all(len(c.char_confidences) == len(c.text) for c in nb.candidates)


def test_key_frame_temperature_and_split() -> None:
    from fidetype.demo.live.emg_prepare import key_frame_temperature, split_files

    st = key_stream(["KeyA", "KeyB", "KeyC", "KeyA"], p=0.99)
    ts = key_frame_temperature([st, st], [["KeyA", "KeyB", "KeyC", None], ["KeyB", "KeyB", "KeyC", "KeyA"]])
    assert np.isfinite(ts.temperature) and ts.temperature > 0
    cal, rep = split_files(["s001-p003.jsonl", "s000-p001.jsonl", "s000-p002.jsonl", "s001-p004.jsonl",
                            "s001-p005.jsonl"])
    assert cal == ["s000-p001.jsonl", "s001-p003.jsonl"]
    assert rep == ["s000-p002.jsonl", "s001-p004.jsonl", "s001-p005.jsonl"]


# --- tracks --------------------------------------------------------------------------------------


def test_outcome_rules() -> None:
    n = K.normalize
    assert T.outcome("COMMIT", ["Hi  there"], "hi there", n) == "commit-correct"
    assert T.outcome("COMMIT", ["hi"], "hi there", n) == "commit-wrong"
    assert T.outcome("COMMIT", ["hi"], None, n) == "commit-wrong"  # null input: nothing was meant
    assert T.outcome("OFFER", ["a", "hi there"], "hi there", n) == "offer-hit"
    assert T.outcome("ASK", [], "x", n) == "withhold"
    assert T.outcome("OFFER", ["a"], None, n, known=False) == "unknown"


def test_trust_log_track_replays_recorded_decisions(log_dir: Path) -> None:
    tr = T.make_track(log_spec(log_dir), None)
    assert tr.status()[0] == "ok"
    tr.load()
    assert len(tr) == 4
    msgs = list(tr.utterance(0))
    assert msgs[0][1]["type"] == "demo_utterance"
    t_dec, m = msgs[-1]
    assert m["type"] == "demo_decision" and m["outcome"] == "commit-correct"
    assert t_dec == pytest.approx(0.51)
    assert m["latency_ms"] == pytest.approx(10.0)
    s = tr.summary()
    assert (s["n"], s["commit"], s["offer"], s["withhold"], s["wrong_commit"]) == (4, 2, 1, 1, 1)
    assert s["wrong_commit_rate"] == 0.25 and s["error_among_commits"] == 0.5
    assert s["offer_hit"] == 1
    assert s["always_commit_wrong"] == 2  # utterance 1 (wrong) and 3 (nothing shown)
    lo, hi = s["wrong_commit_cp95"]
    assert 0 < lo < 0.25 < hi < 1


def test_nts_streams_track_runs_the_trust_layer(nts_dir: Path) -> None:
    tr = T.make_track(nts_spec(nts_dir), None)
    tr.load()
    assert len(tr) == 4
    msgs = list(tr.utterance(0))
    real = [m for _, m in msgs if m is not None]
    assert real[0]["type"] == "demo_utterance" and real[0]["truth"] == demo.demo_phrases()[0]
    assert any(m["type"] == "demo_preview" for m in real)
    times = [t for t, _ in msgs]
    assert times == sorted(times)
    dec = real[-1]
    assert dec["type"] == "demo_decision"
    assert dec["decision"]["type"] == "trust_decision" and dec["decision"]["is_final"] is True
    assert dec["outcome"] in ("commit-correct", "commit-wrong", "offer-hit", "offer-miss", "withhold")
    s = tr.summary()
    assert s["n"] == 4 and s["commit"] + s["offer"] + s["withhold"] == 4
    assert s["config_ids"] == [demo.load_config().config_id]


def test_nts_streams_track_without_truth_reports_unknown(nts_dir: Path) -> None:
    spec = nts_spec(nts_dir)
    del spec["truth"]
    tr = T.make_track(spec, None)
    tr.load()
    s = tr.summary()
    assert "always_commit_wrong" not in s and "no ground truth" in s["note"]


def test_nts_streams_track_rejects_files_outside_the_folder(nts_dir: Path, tmp_path: Path) -> None:
    (tmp_path / "list.json").write_text(json.dumps({"replay": ["../escape.jsonl"]}), encoding="utf-8")
    spec = nts_spec(nts_dir, files={"path": str(tmp_path / "list.json"), "key": "replay"})
    with pytest.raises(C.DemoConfigError):
        T.make_track(spec, None).load()


# --- server + event flow -----------------------------------------------------------------------------


def _collect(url: str, path: str, until: str, timeout: float = 30.0) -> list[dict]:
    import time

    from websockets.sync.client import connect

    out: list[dict] = []
    with connect(url + path, subprotocols=[W.SUBPROTOCOL], open_timeout=5,
                 origin=url.replace("ws://", "http://")) as c:
        c.send(json.dumps({"type": "ws_subscribe", "binding": W.BINDING_VERSION, "from_seq": 1}))
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            m = json.loads(c.recv(timeout=max(0.05, end - time.monotonic())))
            out.append(m)
            if m.get("type") == until:
                return out
    raise AssertionError(f"no {until} message within {timeout} s")


@ws_only
def test_server_serves_page_state_and_events(nts_dir: Path, log_dir: Path) -> None:
    from fidetype.demo.live.server import DemoServer

    tracks = [T.make_track(nts_spec(nts_dir), None), T.make_track(log_spec(log_dir), None)]
    for t in tracks:
        t.load()
    with DemoServer(tracks, port=0, speed=20.0) as srv:
        assert srv.url.startswith("http://127.0.0.1:")
        html = urllib.request.urlopen(srv.url, timeout=5).read().decode("utf-8")
        assert "Replay of recorded data" in html and "prefers-color-scheme: dark" in html
        wsurl = f"ws://127.0.0.1:{srv.port}"
        msgs = _collect(wsurl, "/events", "demo_decision")
        assert msgs[0]["type"] == "ws_welcome"
        dec = [m for m in msgs if m.get("type") == "demo_decision"][0]
        assert dec["counts"]["n"] >= 1 and dec["track"] in ("syn-nts", "log")
        assert "commit_correct" in dec["counts"]
        assert any(m.get("type") == "demo_utterance" for m in msgs)
        d2 = _collect(wsurl, "/decisions", "trust_decision")
        assert d2[-1]["type"] == "trust_decision" and "/" in d2[-1]["session"]
        sm = _collect(wsurl, "/events", "demo_summary")
        assert sm[-1]["summary"]["n"] in (4,)
        st = json.loads(urllib.request.urlopen(srv.url + "state/state.json", timeout=5).read())
        assert st["schema"] == "fidetype.live-demo-state/0.1"
        assert {t["id"] for t in st["tracks"]} == {"syn-nts", "log"}
        assert all(t["dataset"]["licence"] for t in st["tracks"])


def test_server_refuses_public_bind(log_dir: Path) -> None:
    from fidetype.demo.live.server import DemoServer

    with pytest.raises(ValueError):
        DemoServer([T.make_track(log_spec(log_dir), None)], host="0.0.0.0")


# --- command line --------------------------------------------------------------------------------------


def _config_file(tmp_path: Path, tracks: list[dict], default: list[str] | None = None) -> Path:
    p = tmp_path / "demo.json"
    p.write_text(json.dumps({"schema": C.SCHEMA, "default_tracks": default or [t["id"] for t in tracks],
                             "tracks": tracks}), encoding="utf-8")
    return p


def test_cli_check_and_missing_data_messages(tmp_path: Path, log_dir: Path, capsys: pytest.CaptureFixture) -> None:
    missing = nts_spec(tmp_path / "absent")
    cfg = _config_file(tmp_path, [missing, log_spec(log_dir)], default=["syn-nts"])
    assert live_main(["--config", str(cfg), "--check"]) == 0
    out = capsys.readouterr().out
    assert "syn-nts" in out and "missing" in out and "log" in out
    assert live_main(["--config", str(cfg), "--tracks", "syn-nts", "--no-browser", "--duration", "0.1"]) == 2
    err = capsys.readouterr().err
    assert "not found" in err and "Nothing was started" in err
    assert live_main(["--config", str(cfg), "--no-browser", "--duration", "0.1"]) == 2
    assert "--tracks synthetic" in capsys.readouterr().err
    assert live_main(["--config", str(cfg), "--tracks", "nope"]) == 2


@ws_only
def test_cli_runs_a_track_for_a_short_time(tmp_path: Path, log_dir: Path, capsys: pytest.CaptureFixture) -> None:
    cfg = _config_file(tmp_path, [log_spec(log_dir)])
    assert live_main(["--config", str(cfg), "--no-browser", "--port", "0", "--duration", "0.5", "--speed", "5"]) == 0
    assert "http://127.0.0.1:" in capsys.readouterr().out


def test_demo_command_dispatches_live(capsys: pytest.CaptureFixture) -> None:
    from fidetype.demo.__main__ import main as demo_main

    assert demo_main(["live", "--check"]) == 0
    assert "synthetic" in capsys.readouterr().out


# --- page and entry points (P14-06 redesign) -----------------------------------------------------------


def test_counts_separate_correct_and_wrong_commits() -> None:
    from fidetype.demo.live.server import _Counts

    c = _Counts()
    for action, out in [("COMMIT", "commit-correct"), ("COMMIT", "commit-wrong"), ("COMMIT", "unknown"),
                        ("OFFER", "offer-hit"), ("ABSTAIN", "withhold")]:
        c.add(action, out)
    d = c.as_dict()
    assert (d["commit"], d["commit_correct"], d["wrong_commit"]) == (3, 1, 1)
    assert (d["offer"], d["offer_hit"], d["withhold"], d["n"]) == (1, 1, 1, 5)


def test_page_uses_plain_words_and_no_external_resources() -> None:
    from fidetype.demo.live.server import web_dir

    html = (web_dir() / "index.html").read_text(encoding="utf-8")
    for words in ("Typed", "Suggested", "Held back", "Typed correctly", "Typed wrong", "Details for engineers",
                  "Replay of recorded data, not live decoding", "Research use only", "Synthetic data, not a recording"):
        assert words in html, words
    assert "<link" not in html and "<script src" not in html and "@import" not in html
    assert 'name="viewport"' in html and 'data-theme="dark"' in html


def test_python_dash_m_fidetype_runs_the_cli() -> None:
    import subprocess
    import sys

    r = subprocess.run([sys.executable, "-m", "fidetype", "version"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.startswith("fidetype ")
    r = subprocess.run([sys.executable, "-m", "fidetype", "demo", "live", "--check"], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0 and "synthetic" in r.stdout
