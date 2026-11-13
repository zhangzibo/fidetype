"""Tests of the SDK surface (M7-01): fidetype top-level API, writer, CLI, demo."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import fidetype
from fidetype import cli, demo
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig

ROOT = Path(__file__).resolve().parents[1]


def _sim(text: str = "hello world", seed: int = 0):
    return NoisyDecoderSimulator(SimConfig(target_cer=0.1, frame_rate_hz=25.0), seed=seed).simulate(text).stream


def test_public_names_resolve():
    for name in fidetype.__all__:
        assert getattr(fidetype, name) is not None, name
    assert fidetype.TrustLayer is fidetype.StreamingTrustLayer
    with pytest.raises(AttributeError):
        fidetype.no_such_name  # noqa: B018


def test_import_is_lazy():
    code = "import sys, fidetype; print('fidetype.trust.streaming' in sys.modules, 'fidetype.conformance' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.split() == ["False", "False"]


def test_make_write_read_validate(tmp_path):
    st = _sim()
    meta = fidetype.stream_meta(modality="eeg", decoder_name="t", decoder_version="1")
    s = fidetype.make_stream(st.log_probs, frame_times=st.frame_times, frame_period=0.04, source="t", meta=meta)
    for ext in (".jsonl", ".npz"):
        p = fidetype.write_stream(s, tmp_path / f"s{ext}")
        back = fidetype.read_stream(p)
        np.testing.assert_allclose(back.log_probs, s.log_probs, atol=1e-5)
        assert fidetype.validate(p).passes("trust-ready")
    full = fidetype.stream_meta(modality="eeg", decoder_name="t", decoder_version="1", weights_sha256="0" * 64,
                                stream_id="auto", adapter_name="a", adapter_version="1")
    s2 = fidetype.make_stream(st.log_probs, frame_period=0.04, source="t", meta=full)
    assert fidetype.validate(s2).level == "provenance"
    with pytest.raises(fidetype.StreamRejected):
        fidetype.validate(fidetype.make_stream(st.log_probs, source="t"), level="trust-ready")


def test_make_stream_normalize_logits():
    s = fidetype.make_stream(np.random.default_rng(0).normal(size=(5, len(fidetype.VOCAB))), normalize=True)
    np.testing.assert_allclose(np.exp(s.log_probs).sum(axis=1), 1.0, atol=1e-5)


def test_stream_writer_live_and_checks(tmp_path):
    st = _sim()
    meta = fidetype.stream_meta(modality="eeg", decoder_name="t", decoder_version="1")
    p = tmp_path / "live.jsonl"
    with fidetype.open_stream(p, "w", source="t", meta=meta, frame_period=0.04) as w:
        for t, row in zip(st.frame_times, st.log_probs):
            w.frame(t, row)
        with pytest.raises(ValueError):
            w.frame(0.0, st.log_probs[0])                # time goes back
        with pytest.raises(ValueError):
            w.frame(99.0, np.zeros(len(fidetype.VOCAB)))  # does not sum to 1
        w.frame(99.0, logits=np.zeros(len(fidetype.VOCAB)))
        w.segment_end(99.0)
    events = list(fidetype.open_stream(p))
    assert events[0]["type"] == "header" and events[-1]["type"] == "end"
    assert fidetype.validate(p).passes("core")


def test_hypothesis_route_with_writer():
    buf = io.StringIO()
    w = fidetype.StreamWriter(buf, source="t", meta={})
    w.hypothesis([("the boy found a red box", 0.9), "the boy found a red fox"], is_final=True,
                 score_semantics="uncalibrated_prob")
    w.end()
    layer = fidetype.StreamingTrustLayer(demo.load_config(), streaming=fidetype.StreamingConfig(max_attempts=1))
    finals = [d for line in buf.getvalue().splitlines() for d in layer.push(json.loads(line)) if d.final]
    assert len(finals) == 1 and finals[0].action in tuple(fidetype.Action)


def test_frozen_config_roundtrip(tmp_path):
    cfg = demo.load_config()
    cfg.save(tmp_path / "c.json")
    assert fidetype.FrozenTrustConfig.load(tmp_path / "c.json").config_id == cfg.config_id


def test_cli_dispatch(capsys, tmp_path):
    assert cli.main([]) == 0
    assert "validate" in capsys.readouterr().out
    assert cli.main(["version"]) == 0
    assert fidetype.__version__ in capsys.readouterr().out
    assert cli.main(["nope"]) == 2
    assert cli.main(["trust", "--help"]) == 0
    capsys.readouterr()
    from fidetype.demo.__main__ import _write_streams

    files = _write_streams(tmp_path)
    cfg, nosig = files[-1], tmp_path / "demo-04-no-signal.jsonl"
    assert cli.main(["validate", str(nosig)]) == 0
    capsys.readouterr()
    assert cli.main(["trust", "--config", str(cfg), "--decoder", "demo", "--max-attempts", "1", str(nosig)]) == 0
    decisions = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.strip()]
    assert decisions[-1]["is_final"] and decisions[-1]["action"] == "ABSTAIN"


def test_demo_guard_catches_no_signal():
    utts = list(demo.iter_session(partial_every_frames=None))
    assert len(utts) == len(demo.SESSION)
    for u in utts:
        if u["condition"] == "no-signal":
            assert u["final"]["action"] == "ABSTAIN"
            assert u["baseline"]["outcome"] == "commit-wrong"
    tot = demo.run_totals(5)
    for cond in ("no-signal", "shuffled"):
        assert tot[cond]["trust_wrong_commit_rate"] == 0.0
        assert tot[cond]["always_commit_wrong_commit_rate"] == 1.0


def test_demo_terminal_and_page(tmp_path, capsys):
    from fidetype.demo.__main__ import main

    html, log = tmp_path / "d.html", tmp_path / "d.json"
    assert main(["--fast", "--totals", "3", "--no-color", "--html", str(html), "--json", str(log)]) == 0
    out = capsys.readouterr().out
    assert "FINAL ABSTAIN" in out
    page = html.read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>") or page.lower().startswith("<!doctype html>")
    assert "http://" not in page and "https://" not in page.split("<script>")[-1]
    assert json.loads(log.read_text(encoding="utf-8"))["schema"] == demo.LOG_SCHEMA


@pytest.mark.parametrize("script", ["emit_ctc_stream.py", "hypothesis_stream.py", "streaming_trust.py"])
def test_examples_run(script, tmp_path):
    args = [sys.executable, str(ROOT / "examples" / script)]
    if script == "emit_ctc_stream.py":
        args.append(str(tmp_path))
    r = subprocess.run(args, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
