"""Tests of the NeuralTextStream v0.1 conformance suite (M5-10)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from fidetype.conformance import (
    LEVELS,
    StreamRejected,
    check_adapter,
    check_file,
    check_stream,
    check_table,
    load_stream,
    read_raw,
    write_jsonl,
)
from fidetype.conformance.__main__ import main as cli
from fidetype.conformance.vectors import build_vectors, default_vectors_dir, run_consumer, write_vectors
from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import VOCAB

VDIR = default_vectors_dir()
MANIFEST = json.loads((VDIR / "manifest.json").read_text(encoding="utf-8"))
VECTORS = {v["id"]: v for v in MANIFEST["vectors"]}


def _stream(T=8, meta=None, **kw):
    rng = np.random.default_rng(0)
    x = rng.standard_normal((T, len(VOCAB)))
    lp = x - np.log(np.exp(x).sum(axis=1, keepdims=True))
    args = dict(log_probs=lp, frame_times=np.arange(T) * 0.04, vocab=list(VOCAB), blank_id=0, source="unit-test",
                meta=meta if meta is not None else {}, frame_period=0.04)
    args.update(kw)
    return NeuralTextStream(**args)


GOOD_META = {"device.modality": "eeg", "decoder.causal": True, "data.derived": True, "language": "en",
             "decoder.name": "x", "decoder.version": "1", "stream.id": "abc123", "decoder.weights_sha256": "0" * 64}


# --- golden vectors -------------------------------------------------------------------


def test_manifest_covers_all_spec_cases():
    cases = {v["spec_case"] for v in MANIFEST["vectors"] if v["spec_case"]}
    assert cases == {f"C{i}" for i in range(1, 21)}
    assert len(MANIFEST["vectors"]) >= 50
    assert all((VDIR / v["file"]).exists() for v in MANIFEST["vectors"])


def test_committed_vectors_match_the_generator(tmp_path):
    m = write_vectors(tmp_path)
    assert m == MANIFEST
    for v in m["vectors"]:
        a, b = tmp_path / v["file"], VDIR / v["file"]
        if v["format"] == "jsonl":
            assert a.read_bytes() == b.read_bytes().replace(b"\r\n", b"\n"), v["id"]
        else:  # zip timestamps differ; compare the arrays
            try:
                with np.load(a, allow_pickle=False) as za, np.load(b, allow_pickle=False) as zb:
                    assert sorted(za.files) == sorted(zb.files)
                    for k in za.files:
                        np.testing.assert_array_equal(za[k], zb[k])
            except ValueError:  # the pickled-object vector
                assert v["id"] == "V26"


def test_reference_consumer_passes_all_vectors():
    outcomes = run_consumer(load_stream, VDIR)
    bad = [o for o in outcomes if not o.ok]
    assert not bad, bad


@pytest.mark.parametrize("vid", sorted(VECTORS))
def test_vector_fails_its_named_check(vid):
    v = VECTORS[vid]
    rep = check_file(VDIR / v["file"])
    core_fails = [r.check_id for r in rep.results if r.status == "fail" and r.blocks("core")]
    if v["expect"] == "accept":
        assert not core_fails, core_fails
        assert "core" in rep.levels
    else:
        assert v["failing_check"] in core_fails, (v["failing_check"], core_fails)
        assert rep.level == "none"


def test_accept_everything_consumer_fails():
    outcomes = run_consumer(lambda p: {}, VDIR)
    assert sum(not o.ok for o in outcomes) == sum(v["expect"] == "reject" for v in MANIFEST["vectors"])


def test_frame_core_validator_agrees_except_meta_rules():
    """NeuralTextStream.from_npz covers the frame core only (spec 7)."""
    meta_only = {"V30", "V31", "V32", "V33"}  # 4.2 types, lookahead, 5.3 leakage: beyond validate()
    for v in MANIFEST["vectors"]:
        if v["format"] != "npz":
            continue
        try:
            NeuralTextStream.from_npz(VDIR / v["file"])
            got = "accept"
        except (ValueError, KeyError):
            got = "reject"
        if v["id"] in meta_only:
            assert got == "accept"
        else:
            assert got == v["expect"], v["id"]


def test_loaded_values():
    c = load_stream(VDIR / VECTORS["V20"]["file"])
    assert c.stream.vocab_type == "char" and c.vocab_type_defaulted
    c = load_stream(VDIR / VECTORS["V35"]["file"])
    assert np.isneginf(c.stream.log_probs).sum() == 1
    c = load_stream(VDIR / VECTORS["V38"]["file"])
    assert c.ignored_events == 1 and c.stream.n_frames == 2
    with pytest.raises(StreamRejected) as e:
        load_stream(VDIR / VECTORS["V17"]["file"])
    assert e.value.clause == "5.1.4"


# --- checks --------------------------------------------------------------------------


def test_every_check_cites_a_clause():
    rows = check_table()
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    for r in rows:
        assert r["clause"] and r["level"] in (*LEVELS, "advisory") and r["keyword"]


def test_levels_are_cumulative():
    rep = check_stream(_stream(meta=GOOD_META))
    assert rep.levels == ["core", "trust-ready", "provenance"]
    rep = check_stream(_stream(meta={k: v for k, v in GOOD_META.items() if k != "stream.id"}))
    assert rep.levels == ["core", "trust-ready"]
    rep = check_stream(_stream(meta={}))
    assert rep.levels == ["core"]


def test_truth_leak_check():
    s = _stream(meta=GOOD_META | {"acme.hint": "hola mundo bonito"})
    rep = check_stream(s, truth=["hola mundo bonito"])
    r = next(r for r in rep.results if r.check_id == "NTS-LEAK-TRUTH")
    assert r.status == "fail" and rep.level == "none"
    rep = check_stream(_stream(meta=GOOD_META), truth=["hola mundo bonito"])
    assert next(r for r in rep.results if r.check_id == "NTS-LEAK-TRUTH").status == "pass"


def test_privacy_and_free_text_heuristics():
    rep = check_stream(_stream(meta=GOOD_META | {"subject.name": "Ana", "acme.contact": "ana@example.org"}))
    r = next(r for r in rep.results if r.check_id == "NTS-PRIVACY")
    assert r.status == "fail" and "subject.name" in r.message and "e-mail" in r.message
    rep = check_stream(_stream(meta=GOOD_META | {"notes": "x"}))
    assert next(r for r in rep.results if r.check_id == "NTS-FREE-TEXT").outcome == "warn"
    assert "core" in rep.levels  # advisory only


def test_offline_decoder_with_latency_is_flagged():
    s = _stream(meta=GOOD_META | {"decoder.causal": False}, latency=0.2)
    rep = check_stream(s)
    assert next(r for r in rep.results if r.check_id == "TR-OFFLINE-LATENCY").status == "fail"
    assert rep.level == "core"


def test_calibration_consistency():
    from fidetype.trust.calibration import TemperatureScaler

    s = _stream(meta=GOOD_META)
    cal = TemperatureScaler(temperature=1.5).transform_stream(s)
    rep = check_stream(cal)
    assert next(r for r in rep.results if r.check_id == "TR-CALIB").status == "pass"
    assert next(r for r in rep.results if r.check_id == "PV-CALIB-ID").status == "pass"
    flat = _stream(meta=GOOD_META | {"calibration_temperature": 1.5})
    assert next(r for r in check_stream(flat).results if r.check_id == "TR-CALIB").status == "fail"


def test_jsonl_round_trip(tmp_path):
    s = _stream(meta=GOOD_META, latency=0.1)
    lp = s.log_probs.copy()
    lp[0] = -np.inf
    lp[0, 0] = 0.0
    s = _stream(meta=GOOD_META, latency=0.1, log_probs=lp)
    p = tmp_path / "s.jsonl"
    write_jsonl(s, p, events=[{"type": "decision", "t": 0.1, "label": "a", "score": 0.5,
                               "score_semantics": "uncalibrated_prob"}])
    c = load_stream(p)
    np.testing.assert_allclose(c.stream.log_probs, s.log_probs, atol=1e-5)
    assert c.stream.latency == 0.1 and c.stream.meta == s.meta and len(c.events) == 1
    assert read_raw(p).has_end


def test_nan_meta_refused_by_reference_writer(tmp_path):
    with pytest.raises(ValueError):
        _stream(meta={"acme.x": float("nan")}).to_npz(tmp_path / "x.npz")


# --- adapters ------------------------------------------------------------------------


def test_adapters_reach_trust_ready():
    reps = check_adapter("all")
    assert {r.target.split(":")[1] for r in reps} == {"spanishbcbl", "b2t25", "toronto"}
    for r in reps:
        assert "trust-ready" in r.levels, (r.target, [x.to_dict() for x in r.results if x.outcome == "fail"])
        if ":b2t25:" in r.target:
            # The published B2T '25 decoder weights have no hash: only PV-WEIGHTS fails.
            fails = [x.check_id for x in r.results if x.status == "fail" and x.level != "advisory"]
            assert fails == ["PV-WEIGHTS"]
        else:
            assert r.level == "provenance", r.target


def test_spanishbcbl_latency_and_meta():
    from fidetype.adapters.spanishbcbl_meg import segment_stream

    lp = np.log(np.full((5, 28), 1 / 28))
    s = segment_stream(lp, 0.04, subject="S1", session="ses1", lookahead_frames=2, conformer_layers=4)
    assert s.latency == pytest.approx(0.32) and s.meta["decoder.lookahead_s"] == pytest.approx(0.32)
    assert s.meta["decoder.causal"] is True and s.frame_period == 0.04
    off = segment_stream(lp, 0.04, subject="S1", session="ses1")
    assert off.latency is None and off.meta["decoder.causal"] is False


def test_toronto_latency_marks_causal():
    from fidetype.adapters import toronto_semg as T

    lg = np.zeros((3, 27))
    s = T.keypress_stream(lg, [1.0, 2.0, 3.0], T.stream_meta("P1", "T2"), latency=0.3)
    assert s.meta["decoder.causal"] is True and s.meta["decoder.lookahead_s"] == 0.3
    s = T.keypress_stream(lg, [1.0, 2.0, 3.0], T.stream_meta("P1", "T2"))
    assert s.meta["decoder.causal"] is False and s.latency is None


# --- command line ----------------------------------------------------------------------


def test_cli_check_file_and_json(tmp_path, capsys):
    out = tmp_path / "r.json"
    assert cli(["check", str(VDIR / VECTORS["V01"]["file"]), "--json", str(out)]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["schema"] == "fidetype.conformance.report/1" and rep["level"] == "trust-ready"
    assert rep["badge"]["message"] == "trust-ready"
    assert "[NeuralTextStream v0.1 conformance: TRUST-READY]" in capsys.readouterr().out
    assert cli(["check", str(VDIR / VECTORS["V01"]["file"]), "--level", "provenance"]) == 1
    assert cli(["check", str(VDIR / VECTORS["V08"]["file"])]) == 1


def test_cli_adapter_and_list(capsys):
    assert cli(["check", "adapter:toronto", "--level", "provenance"]) == 0
    assert cli(["list", "--markdown"]) == 0
    assert "`NTS-NORM`" in capsys.readouterr().out


def test_cli_consumer_external_command(tmp_path):
    script = tmp_path / "reader.py"
    script.write_text(
        "import sys, json\n"
        "from fidetype.conformance import load_stream\n"
        "try:\n"
        "    c = load_stream(sys.argv[1])\n"
        "except Exception as e:\n"
        "    print(e, file=sys.stderr); sys.exit(1)\n"
        "print(json.dumps({'n_frames': c.stream.n_frames, 'vocab_type': c.stream.vocab_type}))\n",
        encoding="utf-8",
    )
    # run on a 6-vector subset to keep the test fast
    sel = tmp_path / "vec"
    sel.mkdir()
    keep = [VECTORS[k] for k in ("V01", "V04", "V08", "V20", "V38", "V41")]
    for v in keep:
        (sel / v["file"]).write_bytes((VDIR / v["file"]).read_bytes())
    (sel / "manifest.json").write_text(json.dumps(MANIFEST | {"vectors": keep}), encoding="utf-8")
    cmd = f'"{sys.executable}" "{script}" {{path}}'
    assert cli(["consumer", "--vectors", str(sel), "--cmd", cmd]) == 0


def test_build_vectors_ids_unique():
    ids = [v.vid for v in build_vectors()]
    assert len(ids) == len(set(ids))
