"""P14-04 / P4-02: ``fidetype live`` (signal -> windows -> model -> trust guard -> NTS).

The core tests need no optional package: the synthetic source, the
BrainFlow path with :class:`FakeBoard` (driven by a fake clock), and the
CLI. Two integration tests use the real BrainFlow Synthetic board and a
real pylsl loopback; they skip when ``brainflow`` / ``pylsl`` are missing.
"""

from __future__ import annotations

import json
import threading
import time
import uuid

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.adapters import brainflow_bridge as B
from fidetype.adapters import lsl as L
from fidetype.adapters.kt_semg import KEY_VOCAB
from fidetype.conformance import check_file
from fidetype.live import sources as S
from fidetype.live.__main__ import main as live_main
from fidetype.live.build import collect_nbests
from fidetype.live.model import KeyWindowModel, RunningScaler, fit_model, load_model, resolve_asset
from fidetype.live.runner import LiveDecoder, make_writer, nbest_of_frames
from fidetype.live.synthetic import SyntheticTypist


@pytest.fixture(scope="module")
def model() -> KeyWindowModel:
    return load_model("builtin:synthetic-keys")


@pytest.fixture(scope="module")
def guard():
    return ft.load(resolve_asset("builtin:synthetic-keys", ".guard.json"))


# --- model --------------------------------------------------------------------------------


def test_builtin_assets_load(model, guard):
    assert model.channels == 16 and model.sample_rate == 250.0 and model.timing == "markers"
    assert len(model.weights_sha256) == 64
    assert guard.input_kind == "nbest"
    assert guard.sheet is not None and all(c.passed for c in guard.sheet.controls)


def test_model_roundtrip_and_sha_check(tmp_path, model):
    m2 = KeyWindowModel(model.lda, {k: v for k, v in model.card.items() if k not in ("weights", "weights_sha256")},
                        scaler_prior=model.scaler_prior)
    npz, js = m2.save(tmp_path / "m")
    m3 = load_model(js)
    z = np.random.default_rng(0).normal(size=(3, 2 * 16))
    assert np.allclose(m3.log_proba(z), model.log_proba(z))
    npz.write_bytes(npz.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA-256"):
        load_model(js)


def test_running_scaler_is_causal():
    x = np.random.default_rng(1).normal(5.0, 2.0, size=(50, 3))
    a = RunningScaler(np.zeros(3), np.ones(3), n0=5).update_transform(x)
    b = RunningScaler(np.zeros(3), np.ones(3), n0=5).update_transform(x[:20])
    assert np.allclose(a[:20], b)  # row k uses only rows before k
    assert abs(a[-10:].mean()) < 1.0  # the statistics adapt to the stream


def test_fit_model_decodes_synthetic():
    card = {"name": "t", "version": "0", "sample_rate": 250.0, "channels": 8,
            "window": {"pre_s": 0.15, "post_s": 0.05, "n_sub": 2}}
    tmp = KeyWindowModel(None, card)  # type: ignore[arg-type]

    def data(seed: int, n: int):
        t = SyntheticTypist(channels=8, seed=seed, noise=4.0)
        u = list(t.utterances(n))
        sig = t.render(u)
        return tmp.features(sig, [x for v in u for x in v.key_times]), np.array([c for v in u for c in v.key_classes])

    X, y = data(1, 120)
    m = fit_model([X], [y], card)
    Xt, yt = data(2, 40)
    acc = np.mean(np.argmax(m.log_proba(m.new_scaler().update_transform(Xt)), 1) == yt)
    assert acc > 0.9


def test_nbest_of_frames_renders_keys():
    lp = np.full((3, len(KEY_VOCAB)), -20.0)
    for i, k in enumerate(("KeyH", "KeyI", "Space")):
        lp[i, KEY_VOCAB.index(k)] = 0.0
    nb = nbest_of_frames(lp, np.arange(3) * 0.2)
    assert nb[0]["text"] == "hi"


# --- live loop: synthetic source ------------------------------------------------------------


def test_synthetic_end_to_end_valid_nts(tmp_path, model, guard):
    src = S.SyntheticSource(12, seed=7, speed=0)
    out, dlog = tmp_path / "live.nts.jsonl", tmp_path / "live.nts.decisions.jsonl"
    w = make_writer(str(out), model, src.info, guard, "synthetic", decisions=str(dlog))
    got = []
    dec = LiveDecoder(model, guard, src, writer=w, on_decision=got.append)
    st = dec.run()
    w.close()
    assert st.decisions == 12 == len(got)
    assert st.frames == sum(len(u.key_times) for u in src.utterances)
    assert st.commits + st.offers + st.withholds == 12
    assert st.commits >= 1
    for d, u in zip(got, src.utterances):
        if d.action == "commit":
            assert d.text == u.text  # every commit on this seed is right
    rep = check_file(out)
    assert not rep.failures("trust-ready"), rep.failures("trust-ready")
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    kinds = [e["type"] for e in evs]
    assert kinds[0] == "header" and kinds[-1] == "end"
    assert kinds.count("trust_decision") == 0 and kinds.count("hypothesis") == 12  # TD-4 (P14-17)
    decisions = [json.loads(x) for x in dlog.read_text(encoding="utf-8").splitlines()]
    assert len(decisions) == 12 and {d["type"] for d in decisions} == {"trust_decision"}
    assert evs[0]["vocab_type"] == "key" and evs[0]["meta"]["fidetype.live"]["source"] == "synthetic"
    s = st.as_dict()
    assert s["frame_ms"]["n"] == st.frames and s["decision_ms"]["n"] == 12


def test_segment_end_never_before_the_rounded_last_frame(model, guard):
    """FEP-0001 SEG rule 5 after rounding (P14-17, CI live-kt): StreamWriter writes frame t with 9 decimals."""
    import io

    src = S.SyntheticSource(1, seed=7, speed=0)
    buf = io.StringIO()
    w = make_writer(buf, model, src.info, guard, "synthetic")
    dec = LiveDecoder(model, guard, src, writer=w)
    t = 202.31685470750003  # the CI case: rounds up to 202.316854708
    lp = np.log(np.full(len(KEY_VOCAB), 1.0 / len(KEY_VOCAB)))
    w.frame(t, lp)
    dec._last_frame_t = round(t, 9)
    dec._decide(t)  # empty segment
    dec.seg_frames, dec.seg_times = [lp], [t]
    dec._decide(t)  # segment with a decision
    evs = [json.loads(x) for x in buf.getvalue().splitlines()]
    ends = [e["t"] for e in evs if e["type"] == "segment_end"]
    assert len(ends) == 2 and all(x >= round(t, 9) for x in ends)


def test_synthetic_null_input_never_commits(model, guard):
    src = S.SyntheticSource(30, seed=11, speed=0, null=True)
    dec = LiveDecoder(model, guard, src)
    st = dec.run()
    assert st.decisions == 30 and st.commits == 0


def test_real_time_pacing(model, guard):
    src = S.SyntheticSource(1, seed=3, speed=4.0)  # 4x real time
    t0 = time.perf_counter()
    st = LiveDecoder(model, guard, src).run()
    wall = time.perf_counter() - t0
    dur = src.x.shape[0] / src.fs
    assert st.decisions == 1
    assert wall >= 0.7 * dur / 4.0


def test_collect_mode_matches_live(model, guard):
    a = collect_nbests(model, S.SyntheticSource(4, seed=5, speed=0))
    dec = LiveDecoder(model, guard, S.SyntheticSource(4, seed=5, speed=0))
    dec.run()
    assert [nb[0]["text"] for nb in a] == [d.nbest[0]["text"] for d in dec.decisions]


def test_checks_refuse_mismatch(model, guard):
    src = S.SyntheticSource(1, seed=0, speed=0, channels=8)
    with pytest.raises(ValueError, match="channels"):
        LiveDecoder(model, guard, src)
    class LogitsGuard:
        input_kind = "logits"

    with pytest.raises(ValueError, match="n-best"):
        LiveDecoder(model, LogitsGuard(), S.SyntheticSource(1, seed=0, speed=0))


def test_fixed_timing_and_segment_s(model, guard):
    src = S.SyntheticSource(3, seed=2, speed=0)
    dec = LiveDecoder(model, guard, src, timing="fixed", hop_s=0.25, segment_s=2.0)
    st = dec.run()
    dur = src.x.shape[0] / src.fs
    assert st.frames >= int((dur - 0.3) / 0.25) - 1
    assert st.decisions >= int(dur / 2.0)


# --- BrainFlow path (FakeBoard, fake clock; no brainflow needed) ---------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.t = 1_700_000_000.0

    def __call__(self) -> float:
        return self.t


def test_brainflow_source_with_fake_board(tmp_path, model, guard):
    clk = FakeClock()
    board = B.FakeBoard(n_eeg=16, clock=clk)
    src = S.BrainFlowSource(-1, trial_s=1.0, poll_s=0.0, board=board, descr=board.descr,
                            lsl_clock=lambda: clk.t - 1_699_999_000.0, wall_clock=clk)
    assert src.info["channels"] == 16 and src.info["meta"]["brainflow.board_id"] == "-1"
    out = tmp_path / "bf.nts.jsonl"
    w = make_writer(str(out), model, src.info, guard, "brainflow")
    dec = LiveDecoder(model, guard, src, timing="fixed", writer=w)
    src.start()
    for _ in range(int(6.5 / 0.04)):
        clk.t += 0.04
        dec.feed(src.poll(0.0))
    src.close()
    w.close()
    assert dec.stats.decisions >= 5
    assert dec.stats.commits == 0  # sine waves + noise carry no text
    assert not check_file(out).failures("trust-ready")
    head = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert head["meta"]["brainflow.board_id"] == "-1"
    assert not any(k.startswith("device.board") for k in head["meta"])  # P4-09: vendor namespace only


# --- CLI ------------------------------------------------------------------------------------


def test_cli_synthetic(tmp_path, capsys):
    out, summ = tmp_path / "s.nts.jsonl", tmp_path / "s.json"
    rc = live_main(["--source", "synthetic", "--utterances", "4", "--speed", "0", "--json", "--out", str(out),
                    "--summary", str(summ)])
    assert rc == 0
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert len(lines) == 4 and {x["action"] for x in lines} <= {"commit", "offer", "withhold"}
    s = json.loads(summ.read_text())
    assert s["decisions"] == 4 and s["source"] == "synthetic"
    assert not check_file(out).failures("trust-ready")
    assert s["decisions_out"] == str(tmp_path / "s.nts.decisions.jsonl")


def test_decisions_path():
    from fidetype.live.__main__ import decisions_path

    assert decisions_path("a/s.nts.jsonl", None) == "a/s.nts.decisions.jsonl"
    assert decisions_path("s.ndjson", None) == "s.ndjson.decisions.jsonl"
    assert decisions_path("s.jsonl", "d.jsonl") == "d.jsonl"
    assert decisions_path(None, "d.jsonl") == "d.jsonl"
    assert decisions_path("s.jsonl", "none") is None and decisions_path(None, None) is None


def test_cli_out_is_input_stream_and_decision_log_is_separate(tmp_path, capsys):
    """P14-17 (gap 42): --out has no trust_decision (TD-4); --decisions-out is a FEP-0001 decision log."""
    from fidetype.conformance import nts_conform as NC

    out, dlog = tmp_path / "s.nts.jsonl", tmp_path / "decisions.jsonl"
    rc = live_main(["--source", "synthetic", "--utterances", "3", "--speed", "0", "--json", "--out", str(out),
                    "--decisions-out", str(dlog)])
    assert rc == 0
    assert "decision log written" in capsys.readouterr().err
    kinds = [json.loads(x)["type"] for x in out.read_text(encoding="utf-8").splitlines()]
    assert "trust_decision" not in kinds and kinds[0] == "header" and kinds[-1] == "end"
    decisions = [json.loads(x) for x in dlog.read_text(encoding="utf-8").splitlines()]
    assert len(decisions) == 3 and {d["type"] for d in decisions} == {"trust_decision"}
    targets = [NC.conform_file(out), NC.conform_file(dlog)]
    assert [t.form for t in targets] == ["jsonl-stream", "jsonl-decision-log"]
    rep = NC.build_report(targets, "core")
    assert rep["ok"], [r for t in rep["targets"] for r in t.get("results", []) if r.get("outcome") == "fail"]
    assert rep["producer"]["level"] == "trust-ready"
    # the v0.1 validator (fidetype validate) agrees: the stream file reaches trust-ready
    assert not check_file(out).failures("trust-ready")


def test_cli_decisions_out_none_and_decisions_only(tmp_path):
    out = tmp_path / "s.nts.jsonl"
    assert live_main(["--source", "synthetic", "--utterances", "2", "--speed", "0", "--no-text", "--out", str(out),
                      "--decisions-out", "none"]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s.nts.jsonl"]
    dlog = tmp_path / "only.decisions.jsonl"
    assert live_main(["--source", "synthetic", "--utterances", "2", "--speed", "0", "--no-text",
                      "--decisions-out", str(dlog)]) == 0
    assert [json.loads(x)["type"] for x in dlog.read_text(encoding="utf-8").splitlines()] == ["trust_decision"] * 2


def test_cli_via_fidetype_entry(capsys):
    from fidetype.cli import main

    assert main(["live", "--source", "synthetic", "--utterances", "2", "--speed", "0", "--no-text"]) == 0
    o = capsys.readouterr().out
    assert o.count("keys=") == 2 and '"' not in o


def test_cli_needs_guard_for_own_model(tmp_path, model):
    m2 = KeyWindowModel(model.lda, {k: v for k, v in model.card.items() if k not in ("weights", "weights_sha256")},
                        scaler_prior=model.scaler_prior)
    _, js = m2.save(tmp_path / "own")
    assert live_main(["--source", "synthetic", "--model", str(js), "--speed", "0"]) == 2


# --- optional: real BrainFlow Synthetic board and real LSL loopback --------------------------------

brainflow_only = pytest.mark.skipif(not B.brainflow_available(), reason="brainflow not installed")
lsl_only = pytest.mark.skipif(not L.pylsl_available(), reason="pylsl / liblsl not available")


@brainflow_only
def test_brainflow_synthetic_board_one_command(tmp_path, capsys):
    out = tmp_path / "bf.nts.jsonl"
    summ = tmp_path / "bf.json"
    rc = live_main(["--source", "brainflow", "--board-id", "-1", "--trial-s", "1", "--duration", "4.5", "--json",
                    "--out", str(out), "--summary", str(summ)])
    assert rc == 0
    s = json.loads(summ.read_text())
    assert s["decisions"] >= 3 and s["commits"] == 0
    assert not check_file(out).failures("trust-ready")


@lsl_only
def test_lsl_loopback_one_command(tmp_path, capsys):
    from fidetype.live.replay import publish_signal

    name = f"fidetype-test-live-{uuid.uuid4().hex[:8]}"
    src = S.SyntheticSource(4, seed=7)
    mk = list(src.markers)
    stop = threading.Event()
    th = threading.Thread(target=publish_signal, args=(src.x, src.fs, mk, name),
                          kwargs={"speed": 2.0, "wait_consumers": 20.0, "linger_s": 0.5, "stop": stop}, daemon=True)
    th.start()
    out, summ = tmp_path / "lsl.nts.jsonl", tmp_path / "lsl.json"
    try:
        rc = live_main(["--source", "lsl", "--stream-name", name, "--max-decisions", "4", "--duration", "40",
                        "--json", "--out", str(out), "--summary", str(summ)])
    finally:
        stop.set()
        th.join(10)
    assert rc == 0
    s = json.loads(summ.read_text())
    assert s["decisions"] == 4
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    for d, u in zip(lines, src.utterances):
        if d["action"] == "commit":
            assert d["text"] == u.text
    assert not check_file(out).failures("trust-ready")
