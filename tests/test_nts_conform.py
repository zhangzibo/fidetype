"""P7-01: the conformance kit (spec/conformance/kit/) and the nts-conform command line.

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
N_KIT = 31


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


# Rule ids that the spec defines but Appendix C.1 has no row for (open gap 20: MET-11 from RC4 amendment 1).
KNOWN_UNTRACED = {"MET-11"}


def test_every_defined_rule_has_a_traceability_row():
    import re

    from fidetype.conformance.rules import spec_path

    text = spec_path().read_text(encoding="utf-8")
    defined = set(re.findall(r"\*\*\[([A-Z]{2,4}-[A-Z]{0,2}\d+)\]\*\*", text[:text.index("## Appendix C")]))
    missing = defined - set(load_rule_map()["rules"])
    assert missing == KNOWN_UNTRACED, f"rule ids without an Appendix C.1 row: {sorted(missing)}"
