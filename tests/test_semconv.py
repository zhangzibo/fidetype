"""Tests of the semantic-convention registry tool (tools/semconv/semconv.py, roadmap P1-04).

Each check must pass on the real registry and must fail on a seeded fault.
Needs PyYAML (skipped without it). CI job "semconv" runs it with PyYAML.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("semconv_tool", ROOT / "tools" / "semconv" / "semconv.py")
sc = importlib.util.module_from_spec(_spec)
sys.modules["semconv_tool"] = sc
_spec.loader.exec_module(sc)


@pytest.fixture(scope="module")
def base():
    return sc.load()


@pytest.fixture
def reg(base):
    return copy.deepcopy(base)


def attr(reg, key, container="header.meta"):
    return next(a for a in reg.attributes if a["key"] == key and a["_container"] == container)


def has(errs, *needles):
    return any(all(n in e for n in needles) for e in errs)


# --- the real registry -------------------------------------------------------------------


def test_real_registry_passes_all_checks(base):
    errs, usage = sc.run_checks(base)
    assert errs == []
    assert usage.get("device.modality", 0) > 0


def test_generated_doc_is_up_to_date(base):
    _, usage = sc.run_checks(base)
    assert sc.DOC.read_text(encoding="utf-8").replace("\r\n", "\n") == sc.render(base, usage)


def test_render_lists_every_key_and_open_question(base):
    text = sc.render(base)
    for a in base.attributes:
        assert f"`{a['key']}`" in text
    for q in base.manifest["open_questions"]:
        assert q["id"] in text
    assert sc.render(base) == text  # deterministic


def test_registry_covers_spec_tables(base):
    assert len(base.in_container("header.meta")) == 32  # 24 keys of RC4 3.4 + 8 modality keys (FEP-0009)
    assert len(base.in_container("trust_decision.input")) == 14
    assert len(base.in_container("trust_decision.declaration")) == 5
    planned = {n["name"] for n in base.manifest["namespaces"] if n["status"] == "planned"}
    assert planned == {"eeg", "fnirs"}
    assert not [a for a in base.attributes if a["_namespace"] in planned]  # no invented modality keys


# --- modality keys (FEP-0009, RC4 amendment) -----------------------------------------------

MODALITY_KEYS = {
    "emg.placement": "non_empty_string", "emg.derivation": "non_empty_string",
    "meg.sensor_types": "non_empty_string_list",
    "implant.array_type": "non_empty_string", "implant.array_count": "integer_min_1",
    "implant.features": "non_empty_string_list", "implant.bin_s": "finite_number_min_0",
    "implant.areas": "non_empty_string_list",
}


def test_modality_keys_present_with_validators(base):
    got = {a["key"]: a["validator"] for a in base.in_container("header.meta") if a["_namespace"] in ("emg", "meg", "implant")}
    assert got == MODALITY_KEYS
    for k in MODALITY_KEYS:
        a = attr(base, k)
        assert a["stability"] == "development" and "MET-11" in a["rules"]
        assert not a.get("requirement")  # all optional
    assert attr(base, "implant.bin_s")["unit"] == "s"
    reserved = {n["name"] for n in base.manifest["namespaces"] if n["status"] == "reserved"}
    assert {"emg", "meg", "implant"} <= reserved


def test_modality_keys_used_in_accept_vectors(base):
    _, usage = sc.run_checks(base)
    for k in MODALITY_KEYS:
        assert usage.get(k, 0) >= 1, k


@pytest.mark.parametrize("value,ok", [
    (["magnetometer"], True), ([], True), (["a", "b"], True),
    ("magnetometer", False), (["magnetometer", ""], False), ([1], False), (None, False),
])
def test_value_ok_string_list(base, value, ok):
    assert sc.value_ok(attr(base, "meg.sensor_types"), value) is ok


def test_spec_list_of_non_empty_strings_type():
    assert sc.parse_spec_types("list of non-empty strings", 1) == [("string[]", "non_empty_string_list", None)]


def test_structure_string_list_validator_needs_list_type(reg):
    attr(reg, "implant.areas")["type"] = "string"
    assert has(sc.check_structure(reg), "implant.areas", "non_empty_string_list needs type string[]")


def test_structure_registered_values_on_string_list_allowed(base):
    assert attr(base, "implant.features")["registered_values"]
    assert not [e for e in sc.check_structure(base) if "registered_values" in e]


def test_spec_missing_modality_row_found(reg):
    spec = reg.spec_path.read_text(encoding="utf-8")
    row = next(line for line in spec.splitlines() if line.startswith("| `implant.bin_s`"))
    assert has(sc.check_spec(reg, spec.replace(row + chr(10), "")), "implant.bin_s", "not in spec")


def test_sdk_string_list_validator_mismatch_found(reg):
    src = _sources()
    a, b = src["rust"]
    src["rust"] = (a.replace('("implant.areas", t_str_list)', '("implant.areas", t_str)'), b)
    assert has(sc.check_sdks(reg, src), "rust", "implant.areas")


# --- 1. structure --------------------------------------------------------------------------


def test_structure_unknown_type(reg):
    attr(reg, "device.vendor")["type"] = "text"
    assert has(sc.check_structure(reg), "device.vendor", "unknown type")


def test_structure_duplicate_key(reg):
    reg.attributes.append(copy.deepcopy(attr(reg, "stream.id")))
    assert has(sc.check_structure(reg), "stream.id", "duplicate")


def test_structure_key_outside_namespace(reg):
    attr(reg, "lm.name")["key"] = "model.name"
    assert has(sc.check_structure(reg), "model.name", "MET-1")


def test_structure_bad_unknown_value(reg):
    attr(reg, "device.modality")["unknown_value"] = "ultrasound"
    assert has(sc.check_structure(reg), "unknown_value")


def test_structure_condition_needed(reg):
    attr(reg, "language")["requirement"][0].pop("condition")
    assert has(sc.check_structure(reg), "language", "condition")


# --- 2. spec -------------------------------------------------------------------------------


def test_spec_missing_key(reg):
    reg.attributes.remove(attr(reg, "consent.ref"))
    assert has(sc.check_spec(reg), "consent.ref", "not in the registry")


def test_spec_extra_key(reg):
    extra = copy.deepcopy(attr(reg, "device.vendor"))
    extra["key"] = "device.serial"
    reg.attributes.append(extra)
    assert has(sc.check_spec(reg), "device.serial", "not in spec")


def test_spec_type_mismatch(reg):
    attr(reg, "device.invasive")["type"] = "string"
    assert has(sc.check_spec(reg), "device.invasive", "type")


def test_spec_validator_implied_by_type(reg):
    attr(reg, "device.channel_count")["validator"] = "finite_number_min_0"
    assert has(sc.check_spec(reg), "device.channel_count", "integer_min_1")


def test_spec_enum_values(reg):
    attr(reg, "device.modality")["values"] = ["emg", "eeg"]
    assert has(sc.check_spec(reg), "device.modality", "values")


def test_spec_enum_fallback(reg):
    attr(reg, "status", "trust_decision.declaration")["unknown_value"] = "absent"
    assert has(sc.check_spec(reg), "status", "fallback")


def test_spec_unknown_rule(reg):
    attr(reg, "stream.id")["rules"].append("MET-99")
    assert has(sc.check_spec(reg), "MET-99")


def test_spec_text_change_is_found(reg):
    spec = reg.spec_path.read_text(encoding="utf-8")
    spec = spec.replace("| `consent.ref` | non-empty string |", "| `consent.ref` | boolean |")
    assert has(sc.check_spec(reg, spec), "consent.ref", "type")


def test_spec_planned_namespaces(reg):
    reg.manifest["namespaces"].append({"name": "ultrasound", "status": "planned"})
    assert has(sc.check_spec(reg), "planned namespaces")


def test_parse_spec_types():
    assert sc.parse_spec_types("integer, string, string", 3) == [("int", None, None), ("string", None, None), ("string", None, None)]
    assert sc.parse_spec_types("[integer, integer]", 1) == [("int[2]", None, None)]
    assert sc.parse_spec_types("string (64 lowercase hex)", 2) == [("string", None, None)] * 2
    assert sc.parse_spec_types("`header` or `hypothesis`", 1) == [("enum", None, ["header", "hypothesis"])]
    assert sc.parse_spec_types("integer ≥ 1", 1) == [("int", "integer_min_1", None)]
    assert isinstance(sc.parse_spec_types("quaternion", 1), str)


# --- 3. proto, 4. schema -------------------------------------------------------------------


def test_proto_container_not_struct(reg):
    reg.containers["header.meta"]["proto"] = "neuraltextstream.v1.Header.source"
    assert has(sc.check_proto(reg), "header.meta", "not google.protobuf.Struct")


def test_proto_missing_related_field(reg):
    attr(reg, "decoder.lookahead_s")["related_fields"] = ["neuraltextstream.v1.Header.lookahead"]
    assert has(sc.check_proto(reg), "decoder.lookahead_s", "no field lookahead")


def test_schema_bad_pointer(reg):
    reg.containers["trust_decision.input"]["json_schema"] = "#/$defs/TrustDecision/properties/inputs"
    assert has(sc.check_schema(reg), "trust_decision.input", "does not resolve")


def test_schema_not_object(reg):
    reg.containers["header.meta"]["json_schema"] = "#/$defs/Header/properties/source"
    assert has(sc.check_schema(reg), "header.meta", "not object")


# --- 5. SDK tables -------------------------------------------------------------------------


def _sources():
    return {lang: (a.read_text(encoding="utf-8"), b.read_text(encoding="utf-8")) for lang, (a, b) in sc.SDK_TABLES.items()}


def test_sdk_tables_read_all_keys():
    for lang, (a, b) in _sources().items():
        table, mods = sc.sdk_table(lang, a, b)
        assert len(table) == 32, lang  # 24 + 8 modality keys (FEP-0009)
        assert "other" in mods, lang


def test_sdk_missing_key_found(reg):
    src = _sources()
    a, b = src["rust"]
    src["rust"] = (a.replace('    ("consent.ref", t_str),\n', ""), b)
    assert has(sc.check_sdks(reg, src), "rust", "consent.ref", "not in the validator")


def test_sdk_validator_mismatch_found(reg):
    src = _sources()
    a, b = src["typescript"]
    src["typescript"] = (a.replace('"device.invasive": tBool', '"device.invasive": tStr'), b)
    assert has(sc.check_sdks(reg, src), "typescript", "device.invasive")


def test_sdk_planned_namespaces_found(reg):
    src = _sources()
    a, b = src["typescript"]
    src["typescript"] = (a, b.replace('["eeg", "fnirs"]', '["eeg"]'))
    assert has(sc.check_sdks(reg, src), "typescript", "PLANNED_NAMESPACES")


def test_spec_non_empty_string_type():
    assert sc.parse_spec_types("non-empty string", 2) == [("string", "non_empty_string", None)] * 2


def test_sdk_modalities_found(reg):
    src = _sources()
    a, b = src["python"]
    src["python"] = (a.replace('"fnirs", "other")', '"other")'), b.replace('"fnirs", "other")', '"other")'))
    assert has(sc.check_sdks(reg, src), "python", "MODALITIES")


# --- 6. suite check ids --------------------------------------------------------------------


def test_unknown_check_id(reg):
    attr(reg, "stream.id")["checks"].append("NTS-NOPE")
    assert has(sc.check_check_ids(reg), "NTS-NOPE")


def test_check_level_must_match_scope(reg):
    attr(reg, "device.modality")["requirement"][0]["scope"] = "provenance"
    assert has(sc.check_check_ids(reg), "TR-MODALITY", "provenance")


# --- 7. vectors ----------------------------------------------------------------------------


def test_value_ok(base):
    assert sc.value_ok(attr(base, "device.channel_count"), 2.0)  # GEN-5: an integer may be written as 2.0
    assert not sc.value_ok(attr(base, "device.channel_count"), 0)
    assert not sc.value_ok(attr(base, "device.invasive"), 1)
    assert not sc.value_ok(attr(base, "decoder.name"), "")
    assert not sc.value_ok(attr(base, "device.modality"), "ultrasound")
    assert sc.value_ok(attr(base, "device.modality"), "ultrasound", newer_minor=True)  # VER-8
    assert not sc.value_ok(attr(base, "decoder.weights_sha256"), "ABC")
    assert sc.value_ok(attr(base, "language"), "en-US")


def test_bad_vector_value_found(base, tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"vectors": [
        {"id": "X1", "file": "x1.jsonl", "format": "jsonl", "expect": "accept"},
        {"id": "X2", "file": "x2.jsonl", "format": "jsonl", "expect": "reject"}]}), encoding="utf-8")
    hdr = {"type": "header", "spec_version": "1.0", "meta": {"device.channel_count": 0}}
    (d / "x1.jsonl").write_text(json.dumps(hdr) + "\n", encoding="utf-8")
    (d / "x2.jsonl").write_text(json.dumps(hdr) + "\n", encoding="utf-8")
    errs, usage = sc.check_vectors(base, tmp_path)
    assert len(errs) == 1 and "X1" in errs[0]
    assert usage == {"device.channel_count": 1}


# --- 8. CLI ----------------------------------------------------------------------------------


def test_cli_check_passes(capsys):
    assert sc.main(["--check"]) == 0
    assert "semconv: OK" in capsys.readouterr().out
