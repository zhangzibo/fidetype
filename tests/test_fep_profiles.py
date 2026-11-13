"""M4-07 / M6-09: the opt-in conformance profiles fep-0001 and fep-0002, the decode declaration
check of the streaming trust layer, and the FEP-0002 rules of the LSL adapter.

All streams are synthetic (fixed seeds). No pylsl needed.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math

import numpy as np
import pytest

from fidetype.adapters import lsl as L
from fidetype.conformance.__main__ import main as cli
from fidetype.conformance.profiles import PROFILE_NAMES, get_profile
from fidetype.conformance.profiles import fep0001 as P1
from fidetype.conformance.profiles import fep0002 as P2
from fidetype.conformance.vectors import _frames, _header, run_consumer
from fidetype.streams.vocab import VOCAB
from fidetype.trust.declaration import compare_declaration, validate_declaration
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.policy import Action
from fidetype.trust.streaming import StreamEventError, StreamingConfig, StreamingTrustLayer, replay
from fidetype.trust.testing import greedy_nbest

CFG = FrozenTrustConfig(name="fep-test", frame_temperature=1.25).with_policy(
    commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)


def _manifest(name):
    prof = get_profile(name)
    return prof, json.loads((prof.vectors_dir() / "manifest.json").read_text(encoding="utf-8"))


# --- golden vectors ---------------------------------------------------------------------


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_committed_vectors_match_the_generator(name, tmp_path):
    prof, committed = _manifest(name)
    m = prof.write_vectors(tmp_path)
    assert m == committed
    for v in m["vectors"]:
        assert (tmp_path / v["file"]).read_bytes() == (prof.vectors_dir() / v["file"]).read_bytes().replace(b"\r\n", b"\n"), v["id"]


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_reference_consumer_passes_all_vectors(name):
    prof, m = _manifest(name)
    outcomes = run_consumer(prof.consume, prof.vectors_dir())
    assert [o.vid for o in outcomes if not o.ok] == []
    assert len(outcomes) == len(m["vectors"])
    ids = [v["id"] for v in m["vectors"]]
    assert len(set(ids)) == len(ids)
    assert {v["expect"] for v in m["vectors"]} == {"accept", "reject"}


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_accept_everything_consumer_fails(name):
    prof, _ = _manifest(name)
    outcomes = run_consumer(lambda p: {}, prof.vectors_dir())
    assert any(not o.ok for o in outcomes)


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_each_reject_vector_fails_its_named_check(name):
    prof, m = _manifest(name)
    for v in m["vectors"]:
        rep = prof.check_file(prof.vectors_dir() / v["file"])
        fails = [r.check_id for r in rep.failures("core")]
        if v["expect"] == "accept":
            assert fails == [], v["id"]
        else:
            assert v["failing_check"] in fails, (v["id"], fails)


def test_fep0001_covers_every_check():
    prof, m = _manifest("fep-0001")
    named = {v["failing_check"] for v in m["vectors"] if v["expect"] == "reject"}
    assert named == {c[0] for c in P1.CHECKS} - {"FEP1-PARSE"}  # PARSE: v0.1 V41 covers NaN tokens


def test_fep0002_vectors_need_no_pylsl(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "pylsl", None)
    prof, _ = _manifest("fep-0002")
    assert all(o.ok for o in run_consumer(prof.consume, prof.vectors_dir()))


# --- the trust layer against the fep-0001 profile -------------------------------------------


def _hyp(hid, final, text="ab", **kw):
    return {"type": "hypothesis", "id": hid, "is_final": final, "score_semantics": "none",
            "nbest": [{"text": text, "score": -1.0, "char_confidences": [0.9] * len(text)},
                      {"text": text + "c", "score": -1.6}], **kw}


def _log(decisions):
    return [{**d.to_event(), "_line": i + 1} for i, d in enumerate(decisions)]


def test_layer_output_is_a_valid_decision_log():
    V = len(VOCAB)
    events = [_header()]
    for k in range(4):
        events += [{**f, "t": round(f["t"] + 2.0 * k, 6)} for f in _frames(6, V, seed=k)]
        events.append({"type": "segment_end"})
    events.append({"type": "end"})
    strict = CFG.with_policy(commit_p=0.999, commit_max_risk=1.0, abstain_risk=1.01, offer_max_k=0)
    hyp_events = [_header(), _hyp("h1", False), _hyp("h2", True, revision_of="h1"), {"type": "segment_end"},
                  _hyp("h3", False, text="ba"), {"type": "segment_end"}, _hyp("h4", True, text="ab"),
                  _hyp("h5", True, text="ba"), {"type": "end"}]
    runs = [
        (StreamingTrustLayer(CFG, decode_fn=greedy_nbest, streaming=StreamingConfig(partial_every_frames=2)), events),
        (StreamingTrustLayer(CFG), hyp_events),
        (StreamingTrustLayer(strict, streaming=StreamingConfig(max_attempts=2)), hyp_events),  # ASK, retry
    ]
    actions = set()
    for layer, evs in runs:
        ds = replay(evs, layer, session_id="s1")
        assert ds
        actions |= {(d.final, d.action) for d in ds}
        log = _log(ds)
        res = P1.check_events(log)
        assert [r.check_id for r in res if r.status == "fail"] == []
        assert P1.stream_kind(log) == "decisions"
        assert P1.acted_texts(log) == [d.shown[0] for d in ds if d.final and d.action == Action.COMMIT]
    assert {(True, Action.ASK), (True, Action.COMMIT), (False, Action.COMMIT)} <= actions


def test_layer_reads_accept_vectors_and_refuses_bad_declarations():
    prof, m = _manifest("fep-0001")
    for v in m["vectors"]:
        evs, _ = P1.read_events(prof.vectors_dir() / v["file"])
        if P1.stream_kind(evs) != "input" or v.get("failing_check") in ("FEP1-TD-INPUT", "FEP1-V01-CORE"):
            continue
        evs = [{k: x for k, x in e.items() if k != "_line"} for e in evs]
        layer = StreamingTrustLayer(CFG)
        if v["expect"] == "accept":
            replay(evs, layer)
        elif v["failing_check"] in ("FEP1-DECL", "FEP1-SCORE"):
            with pytest.raises(StreamEventError):
                replay(evs, layer)


# --- decode declaration -------------------------------------------------------------------------


def _decl(**kw):
    d = {"decoder": "acme-beam", "decoder_version": "2.1", "frame_temperature": 1.25, "params": {"beam": 8},
         "config_id": CFG.config_id}
    d.update(kw)
    return {k: v for k, v in d.items() if v is not None}


def _run(decl=None, hyp_decl=None, **streaming):
    head = _header(**({"decode_declaration": decl} if decl is not None else {}))
    h = _hyp("h1", True, **({"decode_declaration": hyp_decl} if hyp_decl is not None else {}))
    layer = StreamingTrustLayer(CFG, streaming=StreamingConfig(**streaming))
    (d,) = replay([head, h], layer)
    return d


def test_declaration_validation_and_compare():
    assert validate_declaration(_decl()) == []
    assert validate_declaration("x") and validate_declaration({"frame_temperature": 1.0})
    assert validate_declaration(_decl(frame_temperature=0)) and validate_declaration(_decl(frame_temperature=True))
    assert validate_declaration(_decl(params=[1])) and validate_declaration(_decl(config_id=3))
    assert compare_declaration(_decl(), CFG.config_id, 1.25) == []
    assert compare_declaration({"decoder": "x"}, None, 1.25)  # default temperature 1.0
    assert compare_declaration({"decoder": "x"}, None, 1.0) == []
    m = compare_declaration(_decl(), "tcfg-other", 1.25, {"decoder": "acme-beam", "params": {"beam": 16, "lm": "kenlm"}})
    assert len(m) == 3 and any("config_id" in x for x in m)


def test_declaration_match_keeps_the_decision():
    base = _run()
    d = _run(_decl())
    assert d.decision == base.decision and d.inputs == base.inputs
    assert base.provenance["declaration"] == {"status": "absent", "mode": "warn"}
    assert d.provenance["declaration"]["status"] == "match" and d.provenance["declaration"]["where"] == "header"
    assert d.to_event()["declaration"]["status"] == "match"


def test_declaration_mismatch_warn_and_abstain(caplog):
    base = _run()
    assert base.action != Action.ABSTAIN
    with caplog.at_level(logging.WARNING, logger="fidetype.trust.streaming"):
        w = _run(_decl(frame_temperature=1.0))
    assert w.decision == base.decision
    assert w.provenance["declaration"]["status"] == "mismatch"
    assert "frame_temperature" in w.provenance["declaration"]["mismatches"][0]
    assert "decode declaration does not match" in caplog.text
    a = _run(_decl(frame_temperature=1.0), declaration_check="abstain")
    assert a.action == Action.ABSTAIN and a.decision.reason.startswith("decode declaration mismatch")
    assert _run(_decl(config_id="tcfg-0000000000000000"), declaration_check="abstain").action == Action.ABSTAIN
    assert _run(_decl(), declaration_check="abstain").decision == base.decision


def test_declaration_override_require_expected_off():
    # A hypothesis declaration replaces the header one.
    d = _run(_decl(frame_temperature=1.0), hyp_decl=_decl(), declaration_check="abstain")
    assert d.action != Action.ABSTAIN and d.provenance["declaration"]["where"] == "hypothesis"
    assert _run(require_declaration=True, declaration_check="abstain").action == Action.ABSTAIN
    exp = {"decoder": "acme-beam", "params": {"beam": 16}}
    assert _run(_decl(), expected_decoder=exp, declaration_check="abstain").action == Action.ABSTAIN
    assert _run(_decl(params={"beam": 16}), expected_decoder=exp, declaration_check="abstain").action != Action.ABSTAIN
    off = _run(_decl(frame_temperature=1.0), declaration_check="off")
    assert "declaration" not in off.provenance and "declaration" not in off.to_event()
    with pytest.raises(ValueError):
        StreamingConfig(declaration_check="strict")


def test_declaration_not_applied_on_frames_route_and_bad_form_refused():
    V = len(VOCAB)
    evs = [_header(decode_declaration=_decl(frame_temperature=9.0)), *_frames(5, V), {"type": "end"}]
    (d,) = replay(evs, StreamingTrustLayer(CFG, decode_fn=greedy_nbest,
                                           streaming=StreamingConfig(declaration_check="abstain")))
    assert "declaration" not in d.provenance
    with pytest.raises(StreamEventError, match="FEP-0001 section 4"):
        StreamingTrustLayer(CFG).push(_header(decode_declaration={"frame_temperature": 1.0}))
    layer = StreamingTrustLayer(CFG)
    layer.push(_header())
    with pytest.raises(StreamEventError):
        layer.push(_hyp("h1", True, decode_declaration={"decoder": "x", "frame_temperature": -1}))


# --- FEP-0002 adapter rules -------------------------------------------------------------------------


def _info(**kw):
    h = {k: v for k, v in P2.HEADER.items() if k != "type"}
    base = dict(name="acme.nts", type="NTS", channel_count=len(VOCAB), nominal_srate=8.0, channel_format="double64",
                source_id="acme-1", channel_labels=list(VOCAB),
                fidetype={"nts_header": json.dumps(h), "values": "log_probs", "binding": L.BINDING_VERSION})
    base.update(kw)
    return L.LSLStreamInfo(**base)


def test_info_xml_round_trip():
    info = _info(hostname="somewhere", channel_units=["log_prob"] * len(VOCAB))
    back = L.LSLStreamInfo.from_xml(L.info_to_xml(info))
    assert back.name == info.name and back.nominal_srate == 8.0 and back.fidetype == info.fidetype
    assert back.channel_labels[0] == "<blank>" and back.channel_labels[1:3] == ["a", "b"]


def test_binding_and_native_frame_rules():
    h, _ = L.build_header(_info(), L.LSLMapping())
    assert h["lsl"]["binding"] == "nts-lsl/0.1" and h["lsl"]["event_clock"] == "source" and h["clock_domain"] == "lsl"
    no_binding = {k: v for k, v in _info().fidetype.items() if k != "binding"}
    assert L.build_header(_info(fidetype=no_binding), L.LSLMapping())[0]["lsl"]["binding"] == "nts-lsl/0.1"
    bad = [
        _info(fidetype={**_info().fidetype, "binding": "nts-lsl/2.0"}),
        _info(fidetype={**_info().fidetype, "event_clock": "gps"}),
        _info(channel_format="int32"),
        _info(channel_labels=list(reversed(VOCAB))),
        _info(nominal_srate=25.0),
    ]
    for info in bad:
        with pytest.raises(ValueError):
            L.build_header(info, L.LSLMapping())
    # The space token may read back as an empty label; that is not a mismatch.
    labels = list(VOCAB)
    labels[labels.index(" ")] = ""
    L.build_header(_info(channel_labels=labels, channel_format="float32"), L.LSLMapping())
    # Foreign streams keep the M6-01 behaviour (integer formats allowed, no nts_header).
    L.build_header(L.LSLStreamInfo("p", "Probs", 2, 10.0, "int16", channel_labels=["a", "b"]), L.LSLMapping())


def test_event_clock_lsl_corrects_marker_times():
    src = L.LSLEventSource(L.ScriptedInlet(_info()), clock=lambda: 1.0)
    ev = src.marker_event(json.dumps({"type": "hypothesis", "id": "h", "is_final": True, "score_semantics": "none",
                                      "nbest": [], "t_start": 10.0, "t_end": 11.0, "flag": True}), 50.25, 0.25, "lsl")
    assert ev["t_start"] == 10.25 and ev["t_end"] == 11.25 and ev["lsl_t"] == 50.25 and ev["flag"] is True
    ev = src.marker_event(json.dumps({"type": "segment_end", "t": 10.0}), 50.25, 0.25, "source")
    assert ev["t"] == 10.0


def test_replay_maps_event_times_to_the_lsl_clock():
    e = {"type": "hypothesis", "t_start": 2.0, "t_end": 3.0, "id": "h"}
    out = L._to_lsl_clock(e, base=100.0, t_file0=1.0, speed=2.0)
    assert out["t_start"] == 100.5 and out["t_end"] == 101.0 and e["t_start"] == 2.0
    assert L._to_lsl_clock(e, 100.0, 1.0, 0.0)["t_end"] == 102.0


def test_decisions_desc_and_producer_info_checks():
    d = L.decisions_desc("tcfg-1")
    assert d == {"role": "trust_decisions", "event_type": "trust_decision", "spec": "FEP-0001",
                 "binding": "nts-lsl/0.1", "config_id": "tcfg-1"}
    dec = L.LSLStreamInfo("fidetype.decisions", "Markers", 1, 0.0, "string", fidetype=d)
    assert not [r for r in P2.check_info(dec) if r.status == "fail"]
    assert not [r for r in P2.check_info(_info()) if r.status == "fail"]
    bad = [r.check_id for r in P2.check_info(_info(type="EEG", channel_format="int8")) if r.status == "fail"]
    assert bad == ["FEP2-FRAMES"]
    ev = L.LSLStreamInfo("acme.nts.events", "Markers", 1, 0.0, "string", fidetype={"nts_header": "{}", "event_clock": "x"})
    fails = {r.check_id for r in P2.check_info(ev) if r.status == "fail"}
    assert fails == {"FEP2-BINDING", "FEP2-DESC"}


def test_scripted_inlet_loss():
    inlet = L.ScriptedInlet(_info(), [([[0.0]], [1.0]), "lost"], time_correction=0.5)
    assert inlet.pull_chunk(0, 1) == ([[0.0]], [1.0]) and inlet.time_correction(1) == 0.5
    with pytest.raises(L.LSLStreamLost):
        inlet.pull_chunk(0, 1)
    assert inlet.pull_chunk(0, 1) == ([], [])


# --- command line ---------------------------------------------------------------------------------


def test_cli_profiles(tmp_path, capsys):
    assert cli(["--profile", "fep-0001"]) == 0
    assert "40/40 golden vectors" in capsys.readouterr().out
    assert cli(["consumer", "--profile", "fep-0002"]) == 0
    assert "FEP-0002 profile fep-0002 consumer conformance: PASS" in capsys.readouterr().out
    vdir = get_profile("fep-0001").vectors_dir()
    assert cli(["check", "--profile", "fep-0001", str(vdir / "f22-log-preview-then-commit.jsonl")]) == 0
    assert cli(["check", "--profile", "fep-0001", str(vdir / "f36-td-two-finals.jsonl"), "--json", str(tmp_path / "r.json")]) == 1
    rep = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert rep["schema"] == "fidetype.conformance.profile-report/1" and not rep["ok"]
    assert cli(["vectors", "--profile", "fep-0002", "--out", str(tmp_path / "v")]) == 0
    assert (tmp_path / "v" / "manifest.json").exists()
    capsys.readouterr()
    assert cli(["list", "--profile", "fep-0001", "--markdown"]) == 0
    assert "`FEP1-TD-FINAL`" in capsys.readouterr().out
    assert cli(["consumer"]) == 0  # v0.1 unchanged
    assert "52/52" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli([])
