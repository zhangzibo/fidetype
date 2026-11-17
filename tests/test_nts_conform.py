"""P7-01: the conformance kit (spec/conformance/kit/) and the nts-conform command line.

P7-02 (levels, certified list) and P1-16 (MET-11 advisory check): see the tests at the end.

All kit files are synthetic and small. No raw data, no network, no GPU.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from fidetype.conformance import nts_conform as NC
from fidetype.conformance.kit import VERDICTS, WIRE_FORMS, build_kit, kit_dir, load_index, write_kit
from fidetype.conformance.rules import load_rule_map, render_rule_map, rule_map_path, rules_for

KIT = kit_dir()
N_KIT = 36  # P7-01: 31; P7-02 / P1-16 (kit 0.2.0): K32-K36


def test_kit_dir_is_the_repository_copy():
    assert KIT == Path(__file__).resolve().parents[1] / "spec" / "conformance" / "kit"
    assert len(load_index()["entries"]) == N_KIT


def test_committed_kit_matches_the_generator(tmp_path):
    idx = write_kit(tmp_path)
    assert idx == load_index()
    for e in idx["entries"]:
        a, b = tmp_path / e["path"], KIT / e["path"]
        if e["format"] == "npz":
            try:
                with np.load(a, allow_pickle=False) as za, np.load(b, allow_pickle=False) as zb:
                    assert sorted(za.files) == sorted(zb.files)
                    for k in za.files:
                        np.testing.assert_array_equal(za[k], zb[k])
            except ValueError:  # the pickled-object entry
                assert e["id"] == "K05"
        else:
            assert a.read_bytes() == b.read_bytes().replace(b"\r\n", b"\n"), e["id"]
    for prof in {e["profile"] for e in idx["entries"]}:
        assert json.loads((tmp_path / prof / "manifest.json").read_text(encoding="utf-8")) == \
            json.loads((KIT / prof / "manifest.json").read_text(encoding="utf-8"))


def test_rule_map_is_up_to_date():
    assert rule_map_path().read_text(encoding="utf-8").replace("\r\n", "\n") == render_rule_map(), \
        "spec/conformance/kit/rule-map.json is stale: run nts-conform rules --write"
    rm = load_rule_map()
    assert "FRM-3" in rm["checks"]["NTS-NORM"]
    assert "HDR-1" in rm["checks"]["NTS-JSONL-HEADER"]
    assert rm["checks"]["NTS-NPZ-DTYPE"] == ["FIL-5"]
    assert {"INT-D1", "INT-D2", "INT-D3", "INT-D4"} <= set(rm["checks"]["FEP3-DECL"])  # range "INT-D1 … INT-D4"


def test_rules_for_narrows_to_rules_named_in_the_message():
    assert rules_for("NTS-EVT-HYPOTHESIS", "line 3: t_start must be a number (HYP-5)") == ["HYP-5"]
    assert set(rules_for("NTS-EVT-HYPOTHESIS", "no rule named")) == {"HYP-1", "HYP-5"}
    assert rules_for("NO-SUCH-CHECK") == []


def test_kit_covers_every_wire_form_and_verdict():
    es = load_index()["entries"]
    assert {e["wire_form"] for e in es} == set(WIRE_FORMS)
    assert {e["verdict"] for e in es} == set(VERDICTS)
    assert len({e["id"] for e in es}) == len(es)
    rules = load_rule_map()["rules"]
    for e in es:
        assert e["rules"], e["id"]
        assert all(r in rules for r in e["rules"]), (e["id"], [r for r in e["rules"] if r not in rules])
        if e["verdict"] == "reject":
            assert e["failing_checks"] and e["schema_class"], e["id"]
        if e["verdict"] == "accept-with-warnings":
            assert e["warning_checks"], e["id"]


def test_reference_passes_the_whole_kit():
    rep = NC.run_kit()
    bad = [f"{r['id']}: {r['detail']}" for r in rep["entries"] if not r["ok"]]
    assert not bad, "\n".join(bad)
    assert rep["passed"] == rep["total"] == N_KIT


def test_reject_entries_report_their_rules():
    for e in load_index()["entries"]:
        tr = NC.conform_file(KIT / e["path"])
        if e["verdict"] == "reject":
            failed_rules = {r for x in tr.fails for r in x.rules}
            assert failed_rules & set(e["rules"]), (e["id"], failed_rules)
        else:
            assert not tr.fails, e["id"]


def test_detect_wire_forms():
    forms = {e["id"]: NC.detect(KIT / e["path"]) for e in load_index()["entries"]}
    assert forms["K01"] == ("jsonl-stream", ["v0.1", "fep-0001"])
    assert forms["K03"] == ("npz", ["v0.1"])
    assert forms["K16"] == ("jsonl-decision-log", ["fep-0001"])
    assert forms["K19"] == ("jsonl-stream", ["v0.1", "fep-0001", "fep-0003"])
    assert forms["K21"] == ("jsonl-decision-log", ["fep-0003"])
    assert forms["K23"] == ("jsonl-stream", ["v0.1", "fep-0001", "fep-0005"])
    assert forms["K25"] == ("jsonl-decision-log", ["fep-0005"])
    assert forms["K26"] == ("lsl-capture", ["fep-0002"])
    assert forms["K28"] == ("lsl-decisions-capture", ["fep-0002"])
    assert forms["K29"] == ("ws-capture", ["fep-0004"])
    assert forms["K31"] == ("ws-decisions-capture", ["fep-0004"])


def test_cli_check_exit_codes_and_json(tmp_path, capsys):
    good, bad = KIT / "v0.1" / "k01-text-stream.jsonl", KIT / "v0.1" / "k08-unnormalised-frame.jsonl"
    assert NC.main(["check", str(good)]) == 0
    out = tmp_path / "r.json"
    assert NC.main(["check", str(good), str(bad), "--json", str(out)]) == 1
    text = capsys.readouterr().out
    assert "FRM-3" in text and "NTS-NORM" in text and "frame 1" in text
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["schema"] == NC.REPORT_SCHEMA and rep["ok"] is False and rep["spec"] == "NTS 1.0 RC4 (draft)"
    t_good, t_bad = rep["targets"]
    assert t_good["verdict"] == "pass" and t_bad["verdict"] == "fail"
    assert t_bad["rules"]["FRM-3"] == "fail"
    assert NC.main(["check", str(tmp_path / "missing.jsonl")]) == 2
    (tmp_path / "x.txt").write_text("hi", encoding="utf-8")
    assert NC.main(["check", str(tmp_path / "x.txt")]) == 2


def test_cli_check_locations_and_levels(capsys):
    assert NC.main(["check", str(KIT / "fep-0003" / "k20-intent-undeclared.jsonl")]) == 1
    text = capsys.readouterr().out
    assert "INT-E2" in text and "line 2" in text
    # The kit streams reach provenance; a stream without provenance keys warns at core and fails at provenance.
    assert NC.main(["check", str(KIT / "fep-0002" / "k26-lsl-capture.json"), "--level", "provenance"]) == 0
    capsys.readouterr()


def test_cli_check_higher_level_failure_is_a_warning(tmp_path, capsys):
    lines = (KIT / "v0.1" / "k01-text-stream.jsonl").read_text(encoding="utf-8").splitlines()
    hdr = json.loads(lines[0])
    hdr["meta"] = {"device.modality": "emg", "decoder.causal": True, "data.derived": True, "language": "en"}
    f = tmp_path / "s.jsonl"
    f.write_text("\n".join([json.dumps(hdr), *lines[1:]]) + "\n", encoding="utf-8")
    assert NC.main(["check", str(f)]) == 0
    assert "WARN" in capsys.readouterr().out
    assert NC.main(["check", str(f), "--level", "provenance"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_cli_check_stdin(monkeypatch, capsys):
    data = (KIT / "v0.1" / "k02-sparse-frames.jsonl").read_bytes()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(data)))
    assert NC.main(["check", "-"]) == 0
    assert "stdin.jsonl" in capsys.readouterr().out


def test_cli_check_directory(capsys):
    assert NC.main(["check", str(KIT / "fep-0004")]) == 1  # K30 is a reject entry
    assert "2/3 targets pass" in capsys.readouterr().out


def _producer_validator(path: Path, profile: str) -> None:
    if NC.conform_file(path).fails:
        raise ValueError("rejected")


def test_kit_mode_with_impl_cmd_and_verdicts(tmp_path, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "kit_impl_mod", type(sys)("kit_impl_mod"))
    sys.modules["kit_impl_mod"].check = _producer_validator
    sys.modules["kit_impl_mod"].accept_all = lambda path: None
    assert NC.main(["kit", "--impl", "kit_impl_mod:check"]) == 0
    assert NC.main(["kit", "--impl", "kit_impl_mod:accept_all"]) == 1
    capsys.readouterr()
    # An external program: exit 0 = accept. Our own CLI is a correct validator.
    cmd = f'"{sys.executable}" -m fidetype.conformance.nts_conform check {{path}}'
    out = tmp_path / "k.json"
    assert NC.main(["kit", "--profile", "fep-0004", "--cmd", cmd, "--json", str(out)]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["schema"] == NC.KIT_REPORT_SCHEMA and rep["total"] == 3 and rep["ok"]
    # A verdicts file: one wrong verdict and one missing entry.
    v = {e["id"]: e["expect"] for e in load_index()["entries"]}
    v["K08"] = "accept"
    del v["K31"]
    vf = tmp_path / "v.json"
    vf.write_text(json.dumps(v), encoding="utf-8")
    out2 = tmp_path / "k2.json"
    assert NC.main(["kit", "--verdicts", str(vf), "--json", str(out2)]) == 1
    rep2 = json.loads(out2.read_text(encoding="utf-8"))
    assert sorted(r["id"] for r in rep2["entries"] if not r["ok"]) == ["K08", "K31"]


def test_cli_list_and_build(tmp_path, capsys):
    assert NC.main(["list", "--markdown"]) == 0
    text = capsys.readouterr().out
    assert text.count("\n| K") == N_KIT
    assert NC.main(["build", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "kit.json").is_file() and (tmp_path / "rule-map.json").is_file()
    assert NC.main(["rules", "--check"]) == 0


def test_build_kit_has_no_duplicate_files():
    ks = build_kit()
    assert len({k.path for k in ks}) == len(ks) == N_KIT


@pytest.mark.parametrize("prof", ["v0.1", "fep-0001", "fep-0002", "fep-0003", "fep-0004", "fep-0005"])
def test_profile_manifests_use_the_vector_format(prof):
    man = json.loads((KIT / prof / "manifest.json").read_text(encoding="utf-8"))
    assert man["schema"] == "fidetype.conformance.vectors/1" and man["profile"] == prof
    for v in man["vectors"]:
        assert v["expect"] in ("accept", "reject") and (KIT / prof / v["file"]).is_file()


# Rule ids that the spec defines but Appendix C.1 has no row for. Empty since amendment 3 (P1-16 closed gap 20).
KNOWN_UNTRACED: set[str] = set()


def test_every_defined_rule_has_a_traceability_row():
    import re

    from fidetype.conformance.rules import spec_path

    text = spec_path().read_text(encoding="utf-8")
    defined = set(re.findall(r"\*\*\[([A-Z]{2,4}-[A-Z]{0,2}\d+)\]\*\*", text[:text.index("## Appendix C")]))
    missing = defined - set(load_rule_map()["rules"])
    assert missing == KNOWN_UNTRACED, f"rule ids without an Appendix C.1 row: {sorted(missing)}"


# --- P1-16: MET-11 modality match (advisory, three SDKs) -----------------------------------------------------


def test_modality_match_is_a_warning_never_a_reject():
    from fidetype.conformance import check_file

    vdir = KIT.parent / "v0.1"
    want = {"V93": True, "V94": True, "V95": False, "V96": True}
    for vid, warns in want.items():
        f = next(vdir.glob(f"{vid.lower()}-*"))
        rep = check_file(f)
        r = next(x for x in rep.results if x.check_id == "NTS-MODALITY-MATCH")
        assert (r.outcome == "warn") is warns, (vid, r.outcome, r.message)
        assert rep.passes("core"), vid
    # The rule map traces the check to MET-11, and a finding names MET-11 only.
    assert load_rule_map()["checks"]["NTS-MODALITY-MATCH"] == ["MET-11"]
    tr = NC.conform_file(KIT / "v0.1" / "k32-modality-mismatch.jsonl")
    w = [r for r in tr.warns if r.check == "NTS-MODALITY-MATCH"]
    assert len(w) == 1 and w[0].rules == ["MET-11"] and "emg.placement" in w[0].message


@pytest.mark.parametrize("meta, status", [
    ({"device.modality": "emg", "emg.placement": "wrist"}, "pass"),
    ({"device.modality": "opm-meg", "meg.sensor_types": ["magnetometer"]}, "pass"),
    ({"device.modality": "ecog", "implant.areas": ["M1"]}, "pass"),
    ({"device.modality": "intracortical", "emg.placement": "wrist"}, "fail"),
    ({"device.modality": "other", "meg.sensor_types": ["magnetometer"]}, "fail"),
    ({"emg.placement": "wrist"}, "skip"),  # no device.modality: MET-11 cannot be checked
    ({"device.modality": "ultrasound", "emg.placement": "wrist"}, "skip"),  # a value of a newer minor version
    ({"device.modality": "eeg", "acme.gain": 2}, "skip"),  # no modality keys
])
def test_modality_match_rules(tmp_path, meta, status):
    from fidetype.conformance.checks import c_modality_match
    from fidetype.conformance.io import read_raw

    lines = (KIT / "v0.1" / "k01-text-stream.jsonl").read_text(encoding="utf-8").splitlines()
    hdr = json.loads(lines[0])
    hdr["meta"] = meta
    f = tmp_path / "s.jsonl"
    f.write_text("\n".join([json.dumps(hdr), *lines[1:]]) + "\n", encoding="utf-8")
    assert c_modality_match(read_raw(f))[0] == status


# --- P7-02: finer rule mapping -----------------------------------------------------------------------------


def test_broad_checks_name_the_rule_of_the_finding():
    tr = NC.conform_file(KIT / "fep-0002" / "k27-lsl-channel-count.json")
    by = {r.check: r.rules for r in tr.fails}
    assert by["FEP2-CONSUME"] == ["LSL-F2"]  # P7-01 listed all 17 rules of FEP2-CONSUME
    assert by["FEP2-FRAMES"] == ["LSL-F2", "LSL-F3"]
    assert rules_for("FEP1-TD-FORMAT", "line 1: a COMMIT with shown needs at least one text (rule 8)") == ["TD-8"]
    assert rules_for("FEP5-SAFETY", "line 2: motion after a stop without a new engagement (rule 5)") == ["CTL-S5"]
    assert rules_for("FEP3-SAFETY", "line 1: irreversible COMMIT without confirmation_of (rule 4)") == ["INT-S4"]
    assert len(rules_for("FEP2-CONSUME", "no pattern matches this")) == 17  # unknown message: the full list


def test_refine_table_is_valid_and_covers_the_vectors():
    from fidetype.conformance.rules import REFINE

    rm = load_rule_map()
    assert rm["refine"] == {c: [[p, r] for p, r in pats] for c, pats in sorted(REFINE.items())}
    for c, pats in REFINE.items():
        assert c in rm["checks"], c
        for _, rules in pats:
            for r in rules:
                assert "{1}" in r or r in rm["rules"], (c, r)
    # Every broad finding of every golden vector and kit file is narrowed, except the one listed here.
    known_broad = {("I07", "FEP3-DECL")}  # the declaration is not an object: all of INT-D1 ... INT-D4 apply
    broad = set()
    for m in KIT.parent.glob("*/manifest.json"):
        for v in json.loads(m.read_text(encoding="utf-8"))["vectors"]:
            for r in NC.conform_file(m.parent / v["file"], "provenance").results:
                if r.outcome != "pass" and r.check in REFINE and len(r.rules) > 3 and r.rules == rm["checks"][r.check]:
                    broad.add((v["id"], r.check))
    assert broad == known_broad


# --- P7-02: implementation levels --------------------------------------------------------------------------


def test_levels_json_is_up_to_date_and_places_every_rule():
    from fidetype.conformance.levels import level_rules, levels_path, render_levels

    assert levels_path().read_text(encoding="utf-8").replace("\r\n", "\n") == render_levels(), \
        "spec/conformance/levels.json is stale: run nts-conform levels --write"
    r = level_rules()
    assert r["unplaced"] == [] and r["process"] == ["FEP-1"]
    assert "MET-11" in r["core"] and "CNF-3" not in r["core"] and {"CNF-3", "CNF-4"} <= set(r["trust-ready"]["adds"])
    assert "INT-S4" in r["trust-ready"]["adds"] and "LSL-F2" in r["bindings"]["nts-lsl/0.1"]
    assert "HYP-1" in r["full"]["text"] and "INT-E2" in r["full"]["intent"] and "CTL-4" in r["full"]["control"]


def test_kit_stream_levels_match_the_checker():
    from fidetype.conformance.io import load_stream

    for e in load_index()["entries"]:
        if not e.get("stream_level"):
            assert e["verdict"] == "reject" or e["wire_form"] not in ("jsonl-stream", "npz"), e["id"]
            continue
        assert NC.conform_file(KIT / e["path"]).stream_level == e["stream_level"], e["id"]
        if e["profile"] == "v0.1":
            assert load_stream(KIT / e["path"]).level == e["stream_level"], e["id"]
    levels = {e["id"]: e.get("stream_level") for e in load_index()["entries"]}
    assert (levels["K33"], levels["K34"], levels["K35"], levels["K36"]) == ("core", "trust-ready", "core", "core")


def test_reference_consumer_level_is_trust_ready():
    rep = NC.run_kit()
    lv = rep["level"]
    assert lv["level"] == "trust-ready" and lv["levels"] == {"core": True, "full": True, "trust-ready": True}
    assert lv["bindings"] == {"nts-lsl/0.1": True, "nts-ws/0.1": True}
    assert rep["kit_version"] == "0.2.0" and rep["spec"] == "NTS 1.0 RC4 (draft)"


def _verdict_only(path: Path, profile: str) -> None:
    if NC.conform_file(path).fails:
        raise ValueError("rejected")


def _with_level(path: Path, profile: str, level: str = "core") -> None:
    tr = NC.conform_file(path)
    if tr.fails:
        raise ValueError("rejected")
    order = ("core", "trust-ready", "provenance")
    if tr.form in ("jsonl-stream", "npz") and order.index(tr.stream_level) < order.index(level):
        raise ValueError(f"below {level}")


def test_consumer_level_with_and_without_stream_levels(tmp_path, monkeypatch):
    mod = type(sys)("kit_level_mod")
    mod.verdict_only, mod.with_level = _verdict_only, _with_level
    monkeypatch.setitem(sys.modules, "kit_level_mod", mod)
    r1 = NC.run_kit(validator=NC._impl_validator("kit_level_mod:verdict_only"))
    assert r1["level"]["level"] == "full" and r1["ok"]
    assert "does not report stream levels" in " ".join(r1["level"]["why_not_higher"])
    r2 = NC.run_kit(validator=NC._impl_validator("kit_level_mod:with_level"))
    assert r2["level"]["level"] == "trust-ready" and r2["ok"]
    # Claim only the text profile: the intent and control entries do not count.
    v = {e["id"]: e["expect"] for e in load_index()["entries"]}
    v["K20"] = "accept"  # a wrong verdict on an intent entry
    r3 = NC.run_kit(verdicts=v, claim=["text"])
    assert r3["level"]["level"] == "full" and not r3["ok"]
    assert NC.run_kit(verdicts=v)["level"]["level"] == "core"
    v["K08"] = "accept"  # a wrong verdict on a Core entry
    assert NC.run_kit(verdicts=v)["level"]["level"] is None
    # A verdicts file with stream levels.
    vl = {e["id"]: ({"verdict": e["expect"], "level": e["stream_level"]} if e.get("stream_level") else e["expect"])
          for e in load_index()["entries"]}
    f = tmp_path / "v.json"
    f.write_text(json.dumps(vl), encoding="utf-8")
    verdicts, levels = NC._verdicts_file(str(f))
    assert NC.run_kit(verdicts=verdicts, levels=levels)["level"]["level"] == "trust-ready"
    levels["K34"] = "provenance"
    r5 = NC.run_kit(verdicts=verdicts, levels=levels)
    assert r5["level"]["level"] == "full" and "K34" in " ".join(r5["level"]["why_not_higher"])


def test_producer_levels():
    def lv(*paths, claim=None):
        return NC.build_report([NC.conform_file(KIT / p) for p in paths], "core", claim)["producer"]

    assert lv("v0.1/k03-frames.npz")["level"] == "core"  # NPZ carries only the frame core
    assert lv("v0.1/k01-text-stream.jsonl")["level"] == "trust-ready"  # hypothesis + stream level provenance
    a = lv("v0.1/k01-text-stream.jsonl", "v0.1/k34-trust-ready-no-provenance.jsonl")
    assert a["level"] == "full" and "k34" in " ".join(a["why_not_higher"])
    b = lv("v0.1/k01-text-stream.jsonl", claim=["text", "intent"])
    assert b["level"] == "core" and "intent" in " ".join(b["why_not_higher"])
    c = lv("v0.1/k01-text-stream.jsonl", "fep-0003/k19-intent-stream.jsonl", "fep-0005/k25-control-decision-log.jsonl")
    assert c["level"] == "trust-ready" and c["covered"] == ["text", "intent", "control"]
    assert lv("fep-0001/k16-text-decision-log.jsonl")["level"] is None  # no input stream
    assert lv("v0.1/k01-text-stream.jsonl", "v0.1/k08-unnormalised-frame.jsonl")["level"] is None
    assert lv("v0.1/k01-text-stream.jsonl", "fep-0002/k26-lsl-capture.json")["bindings"] == ["nts-lsl/0.1"]


def test_cli_levels_and_require_level(capsys):
    assert NC.main(["levels"]) == 0
    assert "NTS Trust-ready" in capsys.readouterr().out
    assert NC.main(["levels", "--check"]) == 0
    capsys.readouterr()
    k01, k03 = str(KIT / "v0.1" / "k01-text-stream.jsonl"), str(KIT / "v0.1" / "k03-frames.npz")
    assert NC.main(["check", k01, "--require-level", "trust-ready"]) == 0
    assert "[producer level: NTS Trust-ready" in capsys.readouterr().out
    assert NC.main(["check", k03, "--require-level", "full"]) == 1
    assert NC.main(["check", k03, "--require-level", "core"]) == 0
    assert "stream level provenance" in capsys.readouterr().out
    assert NC.main(["kit", "--require-level", "trust-ready"]) == 0
    assert "[consumer level: NTS Trust-ready" in capsys.readouterr().out


# --- P7-02: self-certification list --------------------------------------------------------------------------


def test_certified_list_matches_its_evidence(capsys):
    from fidetype.conformance.certified import check_certified, load_certified

    assert check_certified() == []
    doc = load_certified()
    ids = {e["id"]: e for e in doc["entries"]}
    for sdk in ("fidetype-python", "fidetype-typescript", "fidetype-rust"):
        assert ids[sdk]["class"] == "consumer" and ids[sdk]["level"] == "trust-ready", sdk
    assert all(e["repository"] == "https://github.com/zhangzibo/fidetype" for e in doc["entries"])  # ours only
    assert NC.main(["certified", "--check"]) == 0
    capsys.readouterr()


def test_certified_check_finds_a_wrong_claim(tmp_path):
    import shutil

    from fidetype.conformance.certified import certified_path, check_certified, load_certified

    shutil.copytree(certified_path().parent / "certified", tmp_path / "certified")
    doc = load_certified()
    e = next(x for x in doc["entries"] if x["class"] == "producer" and x["level"] == "core")
    e["level"], e["level_title"] = "trust-ready", "NTS Trust-ready"
    doc["entries"][1]["kit_version"] = "9.9.9"
    p = tmp_path / "certified.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    probs = check_certified(p)
    assert any("does not reach NTS Trust-ready" in x for x in probs)
    assert any("kit_version" in x for x in probs)
